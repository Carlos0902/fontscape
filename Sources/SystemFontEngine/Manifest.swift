import Foundation
import CryptoKit

public enum SystemFontError: LocalizedError {
    case refused(String)
    public var errorDescription: String? { if case .refused(let message) = self { return message }; return nil }
}
public struct FontFile: Codable, Equatable {
    public let target: String
    public let candidate: String
    public let sourceSHA256: String
    public let candidateSHA256: String
}
public struct FontPackage: Codable {
    public let format: Int
    public let osBuild: String
    public let architecture: String
    public let hanSpacing: Double
    public let files: [FontFile]
    public static let targets = ["/System/Library/Fonts/SFNS.ttf", "/System/Library/PrivateFrameworks/FontServices.framework/Resources/Reserved/PingFangUI.ttc"]
    public static let sourceHashes = [
        targets[0]: "2bfd40dc72e6759e248f82a52a40d551338979fffc9b5c070e685b4b7ad19e66",
        targets[1]: "13b201d63324db59de86956c11c46d1f0ad9ac0aeaa0b9d035c012a794062db7"
    ]
    // These are the unmodified Apple fonts used by the verified 25G83 workflow.
    // A new OS/font revision requires a reviewed profile, rather than bypassing this check.
    public func validate() throws {
        guard format == 1, osBuild == "25G83", architecture == "arm64", hanSpacing.isFinite,
              (0...0.10).contains(hanSpacing), files.count == 2,
              Set(files.map(\.target)) == Set(Self.targets),
              Set(files.map(\.candidate)).count == 2 else {
            throw SystemFontError.refused("不支持的替换包：仅支持 arm64 / macOS 26.6.2 (25G83)，且必须包含两个完整字体文件。")
        }
        for file in files {
            guard Self.sourceHashes[file.target] == file.sourceSHA256,
                  ["SFNS.ttf", "PingFangUI.ttc"].contains(file.candidate),
                  URL(fileURLWithPath: file.target).lastPathComponent == file.candidate,
                  [file.sourceSHA256, file.candidateSHA256].allSatisfy({ $0.range(of: "^[0-9a-f]{64}$", options: .regularExpression) != nil }) else {
                throw SystemFontError.refused("替换包路径或哈希无效。")
            }
        }
    }
}
public func fontDigest(_ data: Data) -> String { SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined() }
public func fontDigest(at url: URL) throws -> String { fontDigest(try Data(contentsOf: url, options: .mappedIfSafe)) }
