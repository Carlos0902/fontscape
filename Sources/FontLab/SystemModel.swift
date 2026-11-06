import SwiftUI
import AppKit
import SystemFontEngine

@MainActor final class SystemModel: ObservableObject {
    @Published var state: [String: Any] = [:]
    @Published var busy = false
    @Published var log = "操作日志显示在这里。"
    @Published var packageURL: URL?
    @Published var spacing = 6.0
    @Published var showGuide = false
    private let support = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0].appendingPathComponent("Fontscape/SystemPackages", isDirectory: true)
    private var executableDirectory: URL { Bundle.main.executableURL!.deletingLastPathComponent() }
    var packageSummary: String {
        guard let url = packageURL,
              let data = try? Data(contentsOf: url.appendingPathComponent("manifest.json")),
              let value = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let percent = value["hanSpacing"] as? Double else { return "替换包信息不可读，请重新载入。" }
        let name = value["donorPostScript"] as? String ?? "来源 SHA256 " + String((value["donorSHA256"] as? String ?? "未知").prefix(16))
        return "包内字体：\(name) · 汉字字距 +\(Int((percent * 100).rounded()))% em"
    }
    var supported: Bool { state["supported"] as? Bool == true }
    var ready: Bool { state["protectionsReady"] as? Bool == true }
    var transaction: [String: Any]? { state["transaction"] as? [String: Any] }
    var verified: Bool { state["bootVerified"] as? Bool == true }
    var summary: String {
        let machine = (state["model"] as? String ?? "未知设备").hasPrefix("VirtualMac") ? "虚拟机" : "实体 Mac（尚未实测）"
        let phase = transaction?["phase"] as? String ?? "无字体替换事务"
        let result = transaction == nil ? "" : (verified ? " · 本次启动字体哈希已核验" : " · 尚未确认新启动生效")
        return "\(machine) · \(state["architecture"] as? String ?? "—") · \(state["osBuild"] as? String ?? "—")\n\(state["sip"] as? String ?? "")\n\(state["authenticatedRoot"] as? String ?? "")\n\(phase)\(result)"
    }
    init() {
        if let path = UserDefaults.standard.string(forKey: "systemFontPackage"), FileManager.default.fileExists(atPath: path) { packageURL = URL(fileURLWithPath: path) }
        refresh()
    }
    func refresh() {
        guard !busy else { return }
        busy = true
        DispatchQueue.global(qos: .userInitiated).async {
            do {
                let state = try SystemFontEngine.inspect()
                DispatchQueue.main.async { self.state = state; self.busy = false }
            } catch { DispatchQueue.main.async { self.log = error.localizedDescription; self.busy = false } }
        }
    }
    func choosePackage() {
        let panel = NSOpenPanel(); panel.canChooseDirectories = true; panel.canChooseFiles = false
        if panel.runModal() == .OK, let url = panel.url {
            do {
                let package = try JSONDecoder().decode(FontPackage.self, from: Data(contentsOf: url.appendingPathComponent("manifest.json")))
                try package.validate()
                for file in package.files {
                    guard try fontDigest(at: url.appendingPathComponent(file.candidate)) == file.candidateSHA256 else { throw SystemFontError.refused("替换包文件哈希不匹配。") }
                }
                packageURL = url; UserDefaults.standard.set(url.path, forKey: "systemFontPackage")
                log = "替换包已载入。应用前仍会核对当前系统字体与备份。"
            } catch { log = error.localizedDescription }
        }
    }
    func build(font: URL?) {
        guard !busy, let font, supported else { return }
        let arch = state["architecture"] as? String == "arm64" ? "aarch64" : "x86_64"
        let resources = Bundle.main.resourceURL!
        let python = resources.appendingPathComponent("Runtime/\(arch)/bin/python3")
        let script = resources.appendingPathComponent("Tools/system-build.py")
        guard FileManager.default.isExecutableFile(atPath: python.path) else { log = "内置字体构建组件缺失，请重新下载完整应用。"; return }
        let output = support.appendingPathComponent(UUID().uuidString)
        do { try FileManager.default.createDirectory(at: support, withIntermediateDirectories: true) } catch { log = error.localizedDescription; return }
        let environment = ["PYTHONPATH": resources.appendingPathComponent("Runtime/fonttools").path, "PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1", "PATH": "/usr/bin:/bin:/usr/sbin:/sbin"]
        execute(python, args: ["-B", "-s", script.path, font.path, output.path, String(spacing / 100), executableDirectory.appendingPathComponent("fontlab-probe").path], environment: environment) { success in
            if success {
                self.packageURL = output; UserDefaults.standard.set(output.path, forKey: "systemFontPackage")
                self.log = "替换包已生成，尚未写入系统字体。可点击应用替换包。\n" + self.log
            }
        }
    }
    private func confirmation(restoring: Bool) -> Bool {
        let verb = restoring ? "回滚" : "替换"
        let keyword = restoring ? "rollback" : "apply"
        let alert = NSAlert(); alert.alertStyle = .warning; alert.messageText = "\(verb)当前启动系统的字体"
        alert.informativeText = "这会写入 SFNS 与 PingFang UI，并创建启动快照。实体 Mac 尚未验证，失败可能无法启动。继续前必须有独立的整机备份或可启动的虚拟机检查点；字体备份不能代替整机恢复。\n\n输入“\(verb)”或“\(keyword)”确认，随后由 macOS 请求管理员授权。完成后需要完全关机再启动。"
        let field = NSTextField(frame: NSRect(x: 0, y: 0, width: 360, height: 24)); field.placeholderString = "\(verb) / \(keyword)"
        alert.accessoryView = field; alert.addButton(withTitle: "继续\(verb)"); alert.addButton(withTitle: "取消")
        alert.showsSuppressionButton = true; alert.suppressionButton?.title = "我已准备好独立整机备份或关机检查点"
        guard alert.runModal() == .alertFirstButtonReturn else { return false }
        let text = field.stringValue.trimmingCharacters(in: .whitespacesAndNewlines)
        guard (text == verb || text.lowercased() == keyword), alert.suppressionButton?.state == .on else {
            log = "未执行\(verb)：请勾选备份确认，并输入“\(verb)”或“\(keyword)”。"
            return false
        }
        return true
    }
    func apply() {
        guard !busy, supported, ready, let packageURL, confirmation(restoring: false) else { return }
        privileged(["apply", packageURL.path])
    }
    func rollback() {
        guard !busy, supported, ready, transaction != nil, confirmation(restoring: true) else { return }
        privileged(["rollback"])
    }
    func archive() {
        guard !busy, verified, transaction?["phase"] as? String == "rollbackPrepared" else { return }
        privileged(["archive"])
    }
    private func privileged(_ args: [String]) {
        func quote(_ value: String) -> String { "'" + value.replacingOccurrences(of: "'", with: "'\"'\"'") + "'" }
        let command = ([executableDirectory.appendingPathComponent("fontscape-system").path] + args).map(quote).joined(separator: " ")
        let literal = command.replacingOccurrences(of: "\\", with: "\\\\").replacingOccurrences(of: "\"", with: "\\\"")
        execute(URL(fileURLWithPath: "/usr/bin/osascript"), args: ["-e", "do shell script \"\(literal)\" with administrator privileges"], environment: nil) { success in
            self.refresh()
            if success { self.log = (args.first == "archive" ? "备份已保留并归档。" : "启动快照已准备。请完全关机再启动，打开应用并刷新状态；看到本次启动核验通过后才算生效。") + "\n" + self.log }
        }
    }
    private func execute(_ url: URL, args: [String], environment: [String: String]?, completion: @escaping (Bool) -> Void) {
        busy = true; FontscapeWork.pendingSystemOperations += 1; log = "操作进行中，请勿关机或退出应用…"
        DispatchQueue.global(qos: .userInitiated).async {
            let process = Process(); process.executableURL = url; process.arguments = args
            if let environment { process.environment = environment }
            let pipe = Pipe(); process.standardOutput = pipe; process.standardError = pipe
            do {
                try process.run()
                while true {
                    let data = pipe.fileHandleForReading.availableData
                    if data.isEmpty { break }
                    let text = String(decoding: data, as: UTF8.self)
                    DispatchQueue.main.async { self.log = String((self.log + "\n" + text).suffix(10000)) }
                }
                process.waitUntilExit(); let success = process.terminationStatus == 0
                DispatchQueue.main.async { FontscapeWork.pendingSystemOperations -= 1; self.busy = false; self.log = (success ? "操作已完成。\n" : "操作未完成，请保留日志与备份。\n") + self.log.replacingOccurrences(of: "操作进行中，请勿关机或退出应用…", with: ""); completion(success) }
            } catch { DispatchQueue.main.async { FontscapeWork.pendingSystemOperations -= 1; self.busy = false; self.log = error.localizedDescription; completion(false) } }
        }
    }
    func revealPackage() { if let packageURL { NSWorkspace.shared.open(packageURL) } }
}
