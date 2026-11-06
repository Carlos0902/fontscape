import SwiftUI

struct SystemFontView: View {
    let font: URL?
    @StateObject private var model = SystemModel()
    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                Text("全系统字体替换 · 实验功能").font(.headline)
                Spacer()
                Button("操作与恢复指引") { model.showGuide = true }
                Button("刷新状态", action: model.refresh).disabled(model.busy)
            }
            Text("已验证环境为 Apple Silicon / macOS 26.6.2 (25G83) 虚拟机。实体 Mac 尚未验证；其他系统版本与 Intel 会被阻止。更换系统字体不能覆盖应用自带字体及所有缺字回退。")
                .font(.callout).foregroundStyle(.secondary)
            Text(model.summary).font(.caption.monospaced()).textSelection(.enabled)
            HStack {
                Text("汉字字距 +\(Int(model.spacing))% em")
                Slider(value: $model.spacing, in: 0...10, step: 1).frame(width: 130).disabled(model.busy)
                Spacer()
                Button("用当前字体生成替换包") { model.build(font: font) }.disabled(font == nil || !model.supported || model.busy)
                Button("载入已有替换包…", action: model.choosePackage).disabled(model.busy)
            }
            Text("仅支持含中西文字形的 TrueType TTF。生成使用本机原始字体与内置工具，无需安装 Python。默认从原始汉字字宽增加 6% em，未在前次间距上累加。生成可能持续数分钟。")
                .font(.caption).foregroundStyle(.secondary)
            if let url = model.packageURL {
                HStack { Text("替换包：\(url.lastPathComponent)").font(.caption); Button("显示文件", action: model.revealPackage) }
            }
            HStack {
                Button("备份并应用替换包…", action: model.apply).disabled(model.packageURL == nil || !model.supported || !model.ready || model.busy || model.transaction != nil)
                Button("恢复原始系统字体…", action: model.rollback).disabled(model.transaction == nil || !model.supported || !model.ready || model.busy)
                Button("归档已验证的回滚", action: model.archive).disabled(!model.verified || model.transaction?["phase"] as? String != "rollbackPrepared" || model.busy)
                if model.busy { ProgressView().controlSize(.small) }
            }
            if !model.ready { Text("系统保护未满足写入条件。请先阅读指引；应用不会自动关闭 SIP 或 authenticated-root。").font(.caption).foregroundStyle(.orange) }
            ScrollView { Text(model.log).font(.caption.monospaced()).textSelection(.enabled).frame(maxWidth: .infinity, alignment: .leading) }.frame(height: 115)
        }
        .padding(24).background(.background, in: RoundedRectangle(cornerRadius: 16))
        .sheet(isPresented: $model.showGuide) {
            VStack(alignment: .leading) {
                HStack { Text("全系统替换与恢复").font(.title2); Spacer(); Button("关闭") { model.showGuide = false } }
                ScrollView {
                    Text((try? String(contentsOf: Bundle.main.resourceURL!.appendingPathComponent("SYSTEM_GUIDE.md"), encoding: .utf8)) ?? "操作文档缺失，请重新下载完整应用。")
                        .font(.system(size: 13)).textSelection(.enabled).frame(maxWidth: .infinity, alignment: .leading)
                }
            }.padding(24).frame(width: 760, height: 650)
        }
    }
}
