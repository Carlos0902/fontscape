import SwiftUI
import AppKit

@MainActor enum FontscapeWork { static var pendingSystemOperations = 0 }
@MainActor final class FontscapeAppDelegate: NSObject, NSApplicationDelegate {
    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        guard FontscapeWork.pendingSystemOperations > 0 else { return .terminateNow }
        let alert = NSAlert()
        alert.messageText = "字体操作尚未完成"
        alert.informativeText = "请等待后台操作结束后再退出。写入或回滚系统字体时中途结束，可能需要使用独立恢复备份。"
        alert.addButton(withTitle: "继续等待"); alert.runModal()
        return .terminateCancel
    }
}
@main struct FontLabApp: App {
    @NSApplicationDelegateAdaptor(FontscapeAppDelegate.self) var delegate
    var body: some Scene {
        WindowGroup { ContentView() }.windowStyle(.titleBar)
            .commands { CommandGroup(replacing: .newItem) {} }
    }
}
