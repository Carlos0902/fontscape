import SwiftUI
@main struct FontLabApp: App {
    var body: some Scene {
        WindowGroup { ContentView() }.windowStyle(.titleBar)
            .commands { CommandGroup(replacing: .newItem) {} }
    }
}
