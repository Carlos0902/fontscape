import Foundation
var assertions = 0
func expectThrows<T>(_ value: @autoclosure () throws -> T) {
    do { _ = try value(); fatalError("Expected operation to be rejected") } catch { assertions += 1 }
}
func expectEqual<T: Equatable>(_ left: T, _ right: T) { precondition(left == right); assertions += 1 }
import Foundation

final class ManifestChecks {
    func manifest(_ edit: (inout [String: Any]) -> Void = { _ in }) throws -> FontPackage {
        let files = FontPackage.targets.map { ["target": $0, "candidate": URL(fileURLWithPath: $0).lastPathComponent,
            "sourceSHA256": FontPackage.sourceHashes[$0]!, "candidateSHA256": String(repeating: "a", count: 64)] }
        var value: [String: Any] = ["format": 1, "osBuild": "25G83", "architecture": "arm64", "hanSpacing": 0.06, "files": files]
        edit(&value)
        return try JSONDecoder().decode(FontPackage.self, from: JSONSerialization.data(withJSONObject: value))
    }
    func testReviewedProfileAccepted() throws { try manifest().validate() }
    func testRejectsOtherBuildAndArchitecture() throws {
        expectThrows(try manifest { $0["osBuild"] = "25G84" }.validate())
        expectThrows(try manifest { $0["architecture"] = "x86_64" }.validate())
    }
    func testRejectsPartialAndDuplicateTargets() throws {
        expectThrows(try manifest { $0["files"] = Array(($0["files"] as! [[String: String]]).prefix(1)) }.validate())
        expectThrows(try manifest { let f = ($0["files"] as! [[String: String]])[0]; $0["files"] = [f,f] }.validate())
    }
    func testRejectsTraversalAndForeignSystemPath() throws {
        for key in ["candidate", "target"] {
            expectThrows(try manifest { var f = $0["files"] as! [[String: String]]; f[0][key] = "../../etc/passwd"; $0["files"] = f }.validate())
        }
    }
    func testRejectsUnreviewedOriginalAndInvalidDigest() throws {
        for key in ["sourceSHA256", "candidateSHA256"] {
            expectThrows(try manifest { var f = $0["files"] as! [[String: String]]; f[0][key] = "invalid"; $0["files"] = f }.validate())
        }
        expectThrows(try manifest { var f = $0["files"] as! [[String: String]]; f[0]["sourceSHA256"] = String(repeating: "b", count: 64); $0["files"] = f }.validate())
    }
    func testSpacingLimits() throws {
        for spacing in [-0.01,0.11] { expectThrows(try manifest { $0["hanSpacing"] = spacing }.validate()) }
        for spacing in [0,0.06,0.10] { try manifest { $0["hanSpacing"] = spacing }.validate() }
    }
    func testRefusesSymlinkAndEmptyInput() throws {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: root) }
        let file = root.appendingPathComponent("font"), link = root.appendingPathComponent("link")
        try Data([1,2,3]).write(to: file)
        try FileManager.default.createSymbolicLink(at: link, withDestinationURL: file)
        expectEqual(try SystemFontEngine.readRegular(file), Data([1,2,3]))
        expectThrows(try SystemFontEngine.readRegular(link))
        try Data().write(to: file); expectThrows(try SystemFontEngine.readRegular(file))
    }
}

let tests = ManifestChecks()
try tests.testReviewedProfileAccepted()
try tests.testRejectsOtherBuildAndArchitecture()
try tests.testRejectsPartialAndDuplicateTargets()
try tests.testRejectsTraversalAndForeignSystemPath()
try tests.testRejectsUnreviewedOriginalAndInvalidDigest()
try tests.testSpacingLimits()
try tests.testRefusesSymlinkAndEmptyInput()
print("System-font engine checks passed: \(assertions) rejection/data assertions plus accepted-profile checks")

let expected = FontPackage.sourceHashes
var saved: [String: Any] = ["phase": "installPrepared", "expected": expected, "bootSession": "before", "volumeUUID": "volume", "osBuild": "25G83"]
var current: [String: Any] = ["fonts": expected, "bootSession": "after", "volumeUUID": "volume", "osBuild": "25G83"]
precondition(SystemFontEngine.bootMatches(saved, current: current))
current["bootSession"] = "before"; precondition(!SystemFontEngine.bootMatches(saved, current: current))
current["bootSession"] = "after"; current["volumeUUID"] = "another"; precondition(!SystemFontEngine.bootMatches(saved, current: current))
current["volumeUUID"] = "volume"; current["fonts"] = [String:String](); precondition(!SystemFontEngine.bootMatches(saved, current: current))
current["fonts"] = expected; saved["expected"] = [String:String](); precondition(!SystemFontEngine.bootMatches(saved, current: current))
saved["expected"] = expected; saved["phase"] = "needsRecovery"; precondition(!SystemFontEngine.bootMatches(saved, current: current))
print("Boot verification: new session, same volume, complete matching files and committed phase required")

precondition(SystemFontEngine.protectionDisabled("System Integrity Protection status: disabled."))
precondition(SystemFontEngine.protectionDisabled("Authenticated Root status: disabled"))
precondition(!SystemFontEngine.protectionDisabled("System Integrity Protection status: enabled (Custom Configuration).\nFilesystem Protections: disabled"))
precondition(!SystemFontEngine.protectionDisabled("unknown disabled"))
print("Protection status: only explicit disabled status accepted")
