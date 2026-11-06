import SwiftUI
import AppKit

struct AppKitSample: NSViewRepresentable {
    let revision: Int
    func makeNSView(context: Context) -> NSTextField { NSTextField(labelWithString: "") }
    func updateNSView(_ view: NSTextField, context: Context) {
        view.stringValue = "文件  编辑  显示  窗口  帮助\nmacOS · alpha beta gamma · 0123456789"
        view.font = NSFont.systemFont(ofSize: 22)
        view.maximumNumberOfLines = 2
        view.lineBreakMode = .byWordWrapping
        view.textColor = .labelColor
    }
}

struct ContentView: View {
    @StateObject private var model = LabModel()
    @State private var sample = "你好，macOS\nThe quick brown fox jumps over the lazy dog.\n文件 编辑 显示 窗口 帮助  0123456789"
    @State private var size: Double = 28
    private let accent = Color(red: 0.19, green: 0.39, blue: 0.36)
    var body: some View {
        HStack(spacing: 0) {
            VStack(alignment: .leading, spacing: 22) {
                Label("Fontscape", systemImage: "textformat.abc").font(.title.bold())
                Text("macOS 字体预览与试用").foregroundStyle(.secondary)
                Divider()
                step("01", "进程内注册", "仅影响本应用", "checkmark.shield")
                step("02", "兼容性检查", "原生检查 · 结果导出", "square.stack.3d.up")
                step("03", "AppKit Hook", "仅限可控进程", "point.3.connected.trianglepath.dotted")
                step("04", "系统卷研究", "仅隔离虚拟机实验", "lock.shield")
                Spacer()
                Text(model.systemDetails).font(.caption).foregroundStyle(.secondary).textSelection(.enabled)
                Text(model.protection).font(.caption).foregroundStyle(.secondary)
                Text("实验结果仅代表已测 API 与进程。\nFinder、Dock、系统设置等需独立验证。")
                    .font(.caption).foregroundStyle(.secondary)
            }
            .padding(28).frame(width: 275, alignment: .leading)
            .background(Color(nsColor: .controlBackgroundColor))
            Divider()
            ScrollView {
                VStack(alignment: .leading, spacing: 24) {
                    HStack {
                        VStack(alignment: .leading, spacing: 5) {
                            Text("让字体选择看得见").font(.largeTitle.weight(.semibold))
                            Text("导入字体、预览中英文，并管理当前用户的字体安装。").foregroundStyle(.secondary)
                        }
                        Spacer()
                        Button("导入字体…", action: model.chooseFont).buttonStyle(.borderedProminent).tint(accent).disabled(model.busy)
                    }
                    VStack(alignment: .leading, spacing: 12) {
                        HStack {
                            Image(systemName: "textformat").font(.title).foregroundStyle(accent)
                            VStack(alignment: .leading) {
                                Text(model.fontFamily).font(.title2.weight(.medium))
                                Text(model.fontName).font(.caption.monospaced()).foregroundStyle(.secondary)
                            }
                            Spacer()
                            if model.selectedURL != nil { Label("进程内已注册", systemImage: "checkmark.circle.fill").font(.caption).foregroundStyle(accent) }
                        }
                        if model.selectedURL != nil {
                            Button(model.userInstalled ? "卸载当前用户字体" : "安装到当前用户", action: model.toggleUserInstall).disabled(model.busy)
                        }
                        if !model.details.isEmpty { Text(model.details).font(.caption).foregroundStyle(.secondary).textSelection(.enabled) }
                        Divider()
                        HStack { Text("字体预览").font(.headline); Spacer(); Text("\(Int(size)) pt").monospacedDigit(); Slider(value: $size, in: 16...44).frame(width: 140) }
                        Text(sample)
                            .font(model.selectedURL == nil ? .system(size: size) : .custom(model.fontName, size: size))
                            .lineSpacing(12).frame(maxWidth: .infinity, minHeight: 155, alignment: .leading).textSelection(.enabled)
                        TextField("编辑预览文字", text: $sample, axis: .vertical).textFieldStyle(.roundedBorder).lineLimit(2...4)
                    }.padding(24).background(.background, in: RoundedRectangle(cornerRadius: 16))
                    VStack(alignment: .leading, spacing: 14) {
                        HStack {
                            Text("可控应用内 Hook").font(.headline)
                            Spacer()
                            Button(model.hooked ? "恢复 AppKit" : "试用 AppKit Hook", action: model.toggleHook)
                                .disabled(model.selectedURL == nil || model.busy)
                        }
                        AppKitSample(revision: model.demoRevision).frame(height: 76)
                        Text("上方控件实际调用 NSFont.systemFont。当前单字重原型会让 regular、bold、weighted 请求共用导入字重；Core Text 直接调用不经过这三个 Hook。")
                            .font(.caption).foregroundStyle(.secondary)
                    }.padding(24).background(.background, in: RoundedRectangle(cornerRadius: 16))
                    VStack(alignment: .leading, spacing: 14) {
                        HStack {
                            Text("字体兼容性检查").font(.headline)
                            Spacer()
                            if model.busy { ProgressView().controlSize(.small) }
                            Button("运行兼容性检查", action: model.runExperiment).disabled(model.selectedURL == nil || model.busy)
                        }
                        Text("在独立进程中检查字体加载与 AppKit 试用，保存报告。无需 Python，不修改其他应用或系统字体。")
                            .font(.callout).foregroundStyle(.secondary)
                        HStack { Text(model.lastResult).font(.caption); Spacer(); Button("打开报告", action: model.revealReports).disabled(model.reportURL == nil) }
                    }.padding(24).background(.background, in: RoundedRectangle(cornerRadius: 16))
                    HStack(alignment: .top) {
                        Image(systemName: "info.circle").foregroundStyle(accent)
                        Text(model.message).font(.callout).textSelection(.enabled)
                        Spacer()
                        Button("恢复本应用", action: model.rollback).disabled(model.busy)
                    }
                    Text("全系统替换目前仅在独立虚拟机验证。此公开版本提供字体预览、用户安装与应用内试用；高级系统卷实验请阅读仓库文档。")
                        .font(.caption).foregroundStyle(.secondary)
                }.padding(32)
            }.background(Color(nsColor: .windowBackgroundColor))
        }
        .frame(minWidth: 1080, minHeight: 760)
        .onAppear {
            if let index = CommandLine.arguments.firstIndex(of: "--font"), CommandLine.arguments.count > index + 1 {
                model.importFont(URL(fileURLWithPath: CommandLine.arguments[index + 1]))
            }
        }
    }
    private func step(_ number: String, _ title: String, _ subtitle: String, _ symbol: String) -> some View {
        HStack(alignment: .top, spacing: 12) {
            Text(number).font(.caption.monospaced()).foregroundStyle(accent).padding(7).background(accent.opacity(0.09), in: RoundedRectangle(cornerRadius: 7))
            VStack(alignment: .leading, spacing: 5) { Label(title, systemImage: symbol).font(.headline); Text(subtitle).font(.caption).foregroundStyle(.secondary) }
        }
    }
}
