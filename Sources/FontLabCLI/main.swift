import Foundation
import CoreText
import FontLabCore

do {
    let args = Array(CommandLine.arguments.dropFirst())
    let command = args.first ?? "snapshot"
    var result: [String: Any]
    switch command {
    case "check":
        guard args.count == 2 else { throw LabError.message("用法：fontlab-probe check FONT") }
        let url = URL(fileURLWithPath: args[1])
        let fileFont = try Probe.rawFont(at: url)
        let name = CTFontCopyPostScriptName(fileFont) as String
        let before = Probe.snapshot()
        var ownsRegistration = false
        do { try Probe.register(url); ownsRegistration = true }
        catch {
            let matched = CTFontCreateWithName(name as CFString, 24, nil)
            guard let actual = CTFontCopyAttribute(matched, kCTFontURLAttribute) as? URL,
                  try Data(contentsOf: actual) == Data(contentsOf: url) else { throw error }
        }
        defer { Probe.removeHook(); if ownsRegistration { try? Probe.unregister(url) } }
        guard Probe.installHook(name: name) else { throw LabError.message("无法试用该字体") }
        let changed = Probe.snapshot()
        for key in ["appkitSystem", "appkitBold", "appkitWeighted"] {
            guard (changed[key] as? [String: Any])?["postscript"] as? String == name else {
                throw LabError.message("字体试用未覆盖 \(key)")
            }
        }
        Probe.removeHook()
        let restored = Probe.snapshot()
        guard try Probe.json(before) == Probe.json(restored) else { throw LabError.message("恢复核验未通过") }
        result = ["font": Probe.info(fileFont), "before": before, "hook": changed, "restored": restored,
                  "scope": "owned child process only", "restorationVerified": true]
    case "export-chinese-outlines":
        guard args.count == 2 else { throw LabError.message("用法：fontlab-probe export-chinese-outlines OUTPUT.jsonl") }
        result = try Probe.exportChineseOutlines(to: URL(fileURLWithPath: args[1]))
    case "render-system":
        guard args.count == 2 else { throw LabError.message("用法：fontlab-probe render-system OUTPUT.png") }
        let font = CTFontCreateUIFontForLanguage(.system, 13, "zh-Hans" as CFString)!
        try Probe.renderPNG(font, to: URL(fileURLWithPath: args[1]))
        result = Probe.info(font)
    case "render-file":
        guard args.count == 3 else { throw LabError.message("用法：fontlab-probe render-file FONT OUTPUT.png") }
        let font = try Probe.rawFont(at: URL(fileURLWithPath: args[1]))
        try Probe.renderPNG(font, to: URL(fileURLWithPath: args[2]))
        result = Probe.info(font)
    case "raw":
        guard args.count == 2 else { throw LabError.message("用法：fontlab-probe raw FONT_PATH") }
        result = Probe.info(try Probe.rawFont(at: URL(fileURLWithPath: args[1])))
    case "snapshot": result = Probe.snapshot(names: Array(args.dropFirst()))
    case "process", "hook":
        guard args.count == 2 else { throw LabError.message("用法：fontlab \(command) FONT_PATH") }
        let url = URL(fileURLWithPath: args[1])
        let name = CTFontCopyPostScriptName(try Probe.font(at: url)) as String
        let before = Probe.snapshot(names: [name])
        try Probe.register(url)
        defer { Probe.removeHook(); try? Probe.unregister(url) }
        let registered = Probe.snapshot(names: [name])
        var hook: [String: Any] = [:]
        if command == "hook" {
            guard Probe.installHook(name: name) else { throw LabError.message("Hook 安装失败") }
            hook = Probe.snapshot(names: [name])
            Probe.removeHook()
        }
        let restored = Probe.snapshot(names: [name])
        try Probe.unregister(url)
        result = ["before": before, "registered": registered, "hook": hook, "hookRestored": restored,
                  "afterUnregister": Probe.snapshot(names: [name]), "font": Probe.info(try Probe.font(at: url))]
    case "scope":
        guard args.count == 2 else { throw LabError.message("用法：fontlab scope FONT_PATH") }
        result = ["scope": CTFontManagerGetScopeForURL(URL(fileURLWithPath: args[1]) as CFURL).rawValue]
    case "register", "unregister":
        guard args.count == 3, ["session", "persistent"].contains(args[1]) else { throw LabError.message("用法：fontlab register|unregister session|persistent FONT_PATH") }
        let url = URL(fileURLWithPath: args[2])
        let scope: CTFontManagerScope = args[1] == "session" ? .session : .persistent
        if command == "register" { try Probe.register(url, scope: scope) }
        else { try Probe.unregister(url, scope: scope) }
        result = ["operation": command, "scope": args[1], "path": url.path, "success": true]
    default: throw LabError.message("命令：snapshot [NAMES…] | process FONT | hook FONT | register|unregister session|persistent FONT")
    }
    FileHandle.standardOutput.write(try Probe.json(result)); print("")
} catch {
    fputs("\(error.localizedDescription)\n", stderr); exit(1)
}
