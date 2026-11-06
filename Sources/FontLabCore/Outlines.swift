import Foundation
import AppKit
import CoreText
import CryptoKit

extension Probe {
    /// Export actual Chinese UI outlines through public Core Text APIs. The local
    /// JSONL is experimental input only, not a redistributable replacement font.
    public static func exportChineseOutlines(to url: URL) throws -> [String: Any] {
        guard !FileManager.default.fileExists(atPath: url.path) else {
            throw LabError.message("输出文件已存在：\(url.path)")
        }
        let ui = CTFontCreateUIFontForLanguage(.system, 13, "zh-Hans" as CFString)!
        let line = CTLineCreateWithAttributedString(NSAttributedString(string: "文", attributes: [NSAttributedString.Key(kCTFontAttributeName as String): ui]))
        let run = (CTLineGetGlyphRuns(line) as! [CTRun])[0]
        let resolved = (CTRunGetAttributes(run) as NSDictionary)[kCTFontAttributeName] as! CTFont
        let units = Int(CTFontGetUnitsPerEm(resolved))
        // Resizing a UI font can silently switch Text -> Display. Keep the exact
        // resolved instance and scale its paths, rather than creating another font.
        let font = resolved
        var pathScale = CGAffineTransform(scaleX: CGFloat(units) / CTFontGetSize(font), y: CGFloat(units) / CTFontGetSize(font))
        let count = CTFontGetGlyphCount(font)
        var header = info(font)
        header["unitsPerEm"] = units
        header["format"] = "FontLab-CGPath-JSONL-v1"
        if let sourceURL = CTFontCopyAttribute(font, kCTFontURLAttribute) as? URL {
            header["sourceSHA256"] = SHA256.hash(data: try Data(contentsOf: sourceURL)).map { String(format: "%02x", $0) }.joined()
        }
        var characters = Array("文中文系统设置".utf16)
        var glyphs = [CGGlyph](repeating: 0, count: characters.count)
        CTFontGetGlyphsForCharacters(font, &characters, &glyphs, characters.count)
        var validation: [String: Int] = [:]
        for (character, glyph) in zip(characters, glyphs) { validation[String(character)] = Int(glyph) }
        header["validationGlyphs"] = validation
        FileManager.default.createFile(atPath: url.path, contents: nil)
        let handle = try FileHandle(forWritingTo: url)
        defer { try? handle.close() }
        func writeLine(_ object: Any) throws {
            try handle.write(contentsOf: JSONSerialization.data(withJSONObject: object, options: [.sortedKeys]))
            try handle.write(contentsOf: Data([10]))
        }
        try writeLine(header)
        for index in 0..<count {
            var commands: [[Double]] = []
            if let path = CTFontCreatePathForGlyph(font, CGGlyph(index), &pathScale) {
                path.applyWithBlock { pointer in
                    let element = pointer.pointee
                    let n: Int
                    switch element.type {
                    case .moveToPoint, .addLineToPoint: n = 1
                    case .addQuadCurveToPoint: n = 2
                    case .addCurveToPoint: n = 3
                    case .closeSubpath: n = 0
                    @unknown default: n = 0
                    }
                    var command = [Double(element.type.rawValue)]
                    for j in 0..<n { command.append(Double(element.points[j].x)); command.append(Double(element.points[j].y)) }
                    commands.append(command)
                }
            }
            try writeLine(["id": index, "commands": commands])
        }
        try handle.synchronize()
        return header
    }
}
