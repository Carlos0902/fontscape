// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "Fontscape",
    platforms: [.macOS(.v14)],
    products: [
        .executable(name: "Fontscape", targets: ["FontLab"]),
        .executable(name: "fontlab-probe", targets: ["FontLabCLI"])
    ],
    targets: [
        .target(name: "FontHook", publicHeadersPath: "include", linkerSettings: [.linkedFramework("AppKit")]),
        .target(name: "FontLabCore", dependencies: ["FontHook"]),
        .executableTarget(name: "FontLabCLI", dependencies: ["FontLabCore"]),
        .executableTarget(name: "FontLab", dependencies: ["FontLabCore"])
    ]
)
