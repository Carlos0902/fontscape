// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "Fontscape",
    platforms: [.macOS(.v14)],
    products: [
        .executable(name: "Fontscape", targets: ["FontLab"]),
        .executable(name: "fontlab-probe", targets: ["FontLabCLI"]),
        .executable(name: "fontscape-system", targets: ["FontscapeSystem"])
    ],
    targets: [
        .target(name: "FontHook", publicHeadersPath: "include", linkerSettings: [.linkedFramework("AppKit")]),
        .target(name: "FontLabCore", dependencies: ["FontHook"]),
        .target(name: "SystemFontEngine"),
        .executableTarget(name: "FontscapeSystem", dependencies: ["SystemFontEngine"]),
        .executableTarget(name: "FontLabCLI", dependencies: ["FontLabCore"]),
        .executableTarget(name: "FontLab", dependencies: ["FontLabCore", "SystemFontEngine"])
    ]
)
