import SwiftUI
import AppKit
import CoreText
import CryptoKit
import FontLabCore
import UniformTypeIdentifiers

@MainActor final class LabModel: ObservableObject {
    @Published var userInstalled = false
    @Published var selectedURL: URL?
    @Published var fontName = "尚未导入字体"
    @Published var fontFamily = "选择一个 TTF、OTF 或 TTC 文件"
    @Published var details = ""
    @Published var systemDetails = ""
    @Published var message = "从进程内预览开始，逐步验证更大范围。"
    @Published var hooked = false
    @Published var busy = false
    @Published var reportURL: URL?
    @Published var demoRevision = 0
    @Published var lastResult = "尚未运行"
    @Published var protection = "系统保护状态未读取"
    var registered: URL?
    let support = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0].appendingPathComponent("Fontscape", isDirectory: true)

    init() {
        let snap = Probe.snapshot()
        let sys = snap["coreTextUI"] as! [String: Any]
        let cn = (snap["chineseFallback"] as! [[String: Any]])[0]["font"] as! [String: Any]
        systemDetails = "macOS \(ProcessInfo.processInfo.operatingSystemVersionString)\n西文：\(sys["postscript"]!)\n中文：\(cn["postscript"]!)"
        let task = Process(); let pipe = Pipe()
        task.executableURL = URL(fileURLWithPath: "/usr/bin/csrutil")
        task.arguments = ["status"]; task.standardOutput = pipe; task.standardError = pipe
        if (try? task.run()) != nil {
            let data = pipe.fileHandleForReading.readDataToEndOfFile(); task.waitUntilExit()
            protection = String(decoding: data, as: UTF8.self).trimmingCharacters(in: .whitespacesAndNewlines)
        }
        let reports = support.appendingPathComponent("Experiments")
        if let dirs = try? FileManager.default.contentsOfDirectory(at: reports, includingPropertiesForKeys: [.contentModificationDateKey]) {
            reportURL = dirs.filter { FileManager.default.fileExists(atPath: $0.appendingPathComponent("report.json").path) }
                .sorted { ((try? $0.resourceValues(forKeys: [.contentModificationDateKey]).contentModificationDate) ?? .distantPast) > ((try? $1.resourceValues(forKeys: [.contentModificationDateKey]).contentModificationDate) ?? .distantPast) }.first
            if reportURL != nil { lastResult = "已有实验报告" }
        }
        if let path = UserDefaults.standard.string(forKey: "lastImportedFont"), FileManager.default.fileExists(atPath: path) { importFont(URL(fileURLWithPath: path)) }
    }
    func chooseFont() {
        let panel = NSOpenPanel()
        panel.allowedContentTypes = ["ttf", "otf", "ttc", "otc"].compactMap { UTType(filenameExtension: $0) }
        panel.canChooseDirectories = false
        if panel.runModal() == .OK, let url = panel.url { importFont(url) }
    }
    func importFont(_ source: URL) {
        guard !busy else { return }
        do {
            let importedFont = try Probe.font(at: source)
            let bytes = try Data(contentsOf: source)
            let hash = SHA256.hash(data: bytes).map { String(format: "%02x", $0) }.joined()
            let directory = support.appendingPathComponent("Imports", isDirectory: true)
            try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
            let dest = directory.appendingPathComponent(hash + "." + source.pathExtension.lowercased())
            if !FileManager.default.fileExists(atPath: dest.path) { try bytes.write(to: dest, options: .withoutOverwriting) }
            if registered != dest {
                if CTFontManagerGetScopeForURL(dest as CFURL) != .persistent { try Probe.register(dest) }
                Probe.removeHook(); hooked = false
                if let old = registered { try? Probe.unregister(old) }
                registered = dest
            }
            UserDefaults.standard.set(dest.path, forKey: "lastImportedFont")
            selectedURL = dest
            userInstalled = ownedInstalls()[dest.path] == hash && CTFontManagerGetScopeForURL(dest as CFURL) == .persistent
            fontName = CTFontCopyPostScriptName(importedFont) as String
            fontFamily = CTFontCopyFamilyName(importedFont) as String
            details = "\(CTFontGetGlyphCount(importedFont).formatted()) 个字形 · 原文件保持不变\nSHA-256 \(hash.prefix(16))…"
            if CTFontCopyVariationAxes(importedFont) == nil {
                details += "\n此文件为固定字重；真实多字重替换需提供对应字重或变量字体。"
            }
            message = "已在本应用进程内注册，可预览和测试。"
            demoRevision += 1
        } catch { message = "导入失败：\(error.localizedDescription)" }
    }
    func toggleHook() {
        guard selectedURL != nil, !busy else { return }
        if hooked { Probe.removeHook(); hooked = false; message = "已恢复本应用的 AppKit 字体 API。" }
        else {
            hooked = Probe.installHook(name: fontName)
            message = hooked ? "本应用的 3 个 NSFont API 已切换。其他进程不受此 Hook 控制。" : "Hook 安装失败。"
        }
        demoRevision += 1
    }
    func rollback() {
        Probe.removeHook(); hooked = false; demoRevision += 1
        message = "本应用 AppKit 字体 API 已恢复。已安装的用户字体可通过卸载按钮单独管理。"
    }
    func runExperiment() {
        guard let font = selectedURL, !busy else { return }
        let cli = Bundle.main.executableURL!.deletingLastPathComponent().appendingPathComponent("fontlab-probe")
        guard FileManager.default.fileExists(atPath: cli.path) else {
            message = "兼容性检查组件缺失，请重新下载完整应用。"; return
        }
        rollback()
        busy = true; lastResult = "实验进行中"
        message = "正在独立检查进程中验证字体加载、系统字体请求与本应用试用能力。"
        let output = support.appendingPathComponent("Experiments/" + UUID().uuidString, isDirectory: true)
        do { try FileManager.default.createDirectory(at: output.deletingLastPathComponent(), withIntermediateDirectories: true) }
        catch { busy = false; message = error.localizedDescription; return }
        DispatchQueue.global(qos: .userInitiated).async {
            let process = Process()
            process.executableURL = cli
            process.arguments = ["check", font.path]
            let pipe = Pipe(); process.standardOutput = pipe; process.standardError = pipe
            do {
                try process.run()
                let data = pipe.fileHandleForReading.readDataToEndOfFile()
                process.waitUntilExit()
                try FileManager.default.createDirectory(at: output, withIntermediateDirectories: true)
                if process.terminationStatus == 0 { try data.write(to: output.appendingPathComponent("report.json"), options: .atomic) }
                let log = String(decoding: data, as: UTF8.self)
                try? data.write(to: output.deletingLastPathComponent().appendingPathComponent(output.lastPathComponent + ".log"))
                let code = process.terminationStatus
                let reportData = try? Data(contentsOf: output.appendingPathComponent("report.json"))
                let report = reportData.flatMap { try? JSONSerialization.jsonObject(with: $0) as? [String: Any] }
                let conclusions = report?["hook"] as? [String: Any]
                let summary: String
                if code == 0, let conclusions = conclusions {
                    _ = conclusions
                    summary = "字体可加载，本应用内试用检查已完成并恢复。该结果不表示 Finder 或其他应用已换字体。"
                } else { summary = log.suffix(1400).description }
                DispatchQueue.main.async {
                    self.busy = false; self.reportURL = output
                    self.lastResult = code == 0 ? "检查完成 · 试用已恢复" : "检查未通过 · 请查看日志"
                    self.message = summary
                }
            } catch {
                DispatchQueue.main.async { self.busy = false; self.message = error.localizedDescription; self.lastResult = "启动失败" }
            }
        }
    }
    private var installLedger: URL { support.appendingPathComponent("installed-fonts.json") }
    private func ownedInstalls() -> [String: String] {
        guard let data = try? Data(contentsOf: installLedger), let value = try? JSONDecoder().decode([String:String].self, from: data) else { return [:] }
        return value
    }
    func toggleUserInstall() {
        guard let url = selectedURL, !busy else { return }
        do {
            var ledger = ownedInstalls()
            let digest = SHA256.hash(data: try Data(contentsOf: url)).map { String(format: "%02x", $0) }.joined()
            if userInstalled {
                guard ledger[url.path] == digest else { throw LabError.message("安装记录不匹配，停止卸载。") }
                try Probe.unregister(url, scope: .persistent)
                ledger.removeValue(forKey: url.path)
                try JSONEncoder().encode(ledger).write(to: installLedger, options: .atomic)
                userInstalled = false
                // A reopened app may have relied solely on the persistent registration.
                if CTFontManagerGetScopeForURL(url as CFURL) != .process { try Probe.register(url) }
                demoRevision += 1
                message = "已卸载由 Fontscape 安装的当前字体；进程内预览仍可用。"
            } else {
                guard CTFontManagerGetScopeForURL(url as CFURL) != .persistent else { throw LabError.message("字体已存在于持久注册中，请通过原安装来源管理。") }
                // Record intent before registration, so interrupted installs remain recoverable.
                ledger[url.path] = digest
                try JSONEncoder().encode(ledger).write(to: installLedger, options: .atomic)
                do { try Probe.register(url, scope: .persistent) }
                catch { ledger.removeValue(forKey: url.path); try? JSONEncoder().encode(ledger).write(to: installLedger, options: .atomic); throw error }
                userInstalled = true; message = "已安装为当前用户字体，支持选字体的应用可使用它。系统 UI 字体不因此改变。"
            }
        } catch { message = error.localizedDescription }
    }
    func revealReports() {
        NSWorkspace.shared.open(reportURL ?? support.appendingPathComponent("Experiments"))
    }
}
