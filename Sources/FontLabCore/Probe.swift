import AppKit
import CoreText
import CryptoKit
import FontHook

public enum LabError: LocalizedError {
    case message(String)
    public var errorDescription: String? { if case let .message(s) = self { return s }; return nil }
}

public enum Probe {
    public static let sample = "你好，macOS · 文件 编辑 显示 窗口 帮助 · The quick brown fox 0123456789"
    /// Decode the file directly, bypassing name matching for same-name system candidates.
    public static func rawFont(at url: URL) throws -> CTFont {
        guard let provider = CGDataProvider(url: url as CFURL), let graphics = CGFont(provider) else {
            throw LabError.message("无法直接解码字体：\(url.path)")
        }
        return CTFontCreateWithGraphicsFont(graphics, 24, nil, nil)
    }
    public static func font(at url: URL) throws -> CTFont {
        guard let descriptors = CTFontManagerCreateFontDescriptorsFromURL(url as CFURL) as? [CTFontDescriptor], let first = descriptors.first else {
            throw LabError.message("无法读取字体：\(url.path)")
        }
        return CTFontCreateWithFontDescriptor(first, 24, nil)
    }
    public static func register(_ url: URL, scope: CTFontManagerScope = .process) throws {
        var error: Unmanaged<CFError>?
        guard CTFontManagerRegisterFontsForURL(url as CFURL, scope, &error) else {
            throw LabError.message(error?.takeRetainedValue().localizedDescription ?? "注册失败")
        }
    }
    public static func unregister(_ url: URL, scope: CTFontManagerScope = .process) throws {
        var error: Unmanaged<CFError>?
        guard CTFontManagerUnregisterFontsForURL(url as CFURL, scope, &error) else {
            throw LabError.message(error?.takeRetainedValue().localizedDescription ?? "注销失败")
        }
    }
    public static func info(_ font: CTFont) -> [String: Any] {
        let bytes = glyphImage(font)
        return ["postscript": CTFontCopyPostScriptName(font) as String,
                "fullName": CTFontCopyFullName(font) as String,
                "family": CTFontCopyFamilyName(font) as String,
                "size": CTFontGetSize(font),
                "url": (CTFontCopyAttribute(font, kCTFontURLAttribute) as? URL)?.path ?? "",
                "glyphCount": CTFontGetGlyphCount(font),
                "renderMethod": "native-instance-scaled-to-24pt-v2",
                "renderSHA256": SHA256.hash(data: bytes).map { String(format: "%02x", $0) }.joined()]
    }
    public static func glyphImage(_ font: CTFont) -> Data {
        let width = 1400, height = 90
        var data = Data(count: width * height * 4)
        data.withUnsafeMutableBytes { buffer in
            let ctx = CGContext(data: buffer.baseAddress, width: width, height: height, bitsPerComponent: 8, bytesPerRow: width * 4, space: CGColorSpaceCreateDeviceRGB(), bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)!
            ctx.setFillColor(CGColor(gray: 1, alpha: 1)); ctx.fill(CGRect(x: 0, y: 0, width: width, height: height))
            // Keep the requested UI instance: copying it at 24pt may change the
            // underlying Text/Display face. Scale the drawing context instead.
            let scale = 24 / max(CTFontGetSize(font), 1)
            ctx.scaleBy(x: scale, y: scale)
            let text = NSAttributedString(string: sample, attributes: [NSAttributedString.Key(kCTFontAttributeName as String): font, .foregroundColor: NSColor.black])
            ctx.textPosition = CGPoint(x: 12 / scale, y: 34 / scale)
            CTLineDraw(CTLineCreateWithAttributedString(text), ctx)
        }
        return data
    }
    public static func renderPNG(_ font: CTFont, to url: URL) throws {
        let data = glyphImage(font)
        guard let provider = CGDataProvider(data: data as CFData),
              let image = CGImage(width: 1400, height: 90, bitsPerComponent: 8, bitsPerPixel: 32,
                                  bytesPerRow: 5600, space: CGColorSpaceCreateDeviceRGB(),
                                  bitmapInfo: CGBitmapInfo(rawValue: CGImageAlphaInfo.premultipliedLast.rawValue),
                                  provider: provider, decode: nil, shouldInterpolate: false, intent: .defaultIntent),
              let png = NSBitmapImageRep(cgImage: image).representation(using: .png, properties: [:]) else {
            throw LabError.message("无法生成字体渲染图")
        }
        try png.write(to: url, options: .atomic)
    }
    public static func runs(_ font: CTFont, text: String) -> [[String: Any]] {
        let line = CTLineCreateWithAttributedString(NSAttributedString(string: text, attributes: [NSAttributedString.Key(kCTFontAttributeName as String): font]))
        return (CTLineGetGlyphRuns(line) as! [CTRun]).map { run in
            let attributes = CTRunGetAttributes(run) as NSDictionary
            let actual = attributes[kCTFontAttributeName] as! CTFont
            let range = CTRunGetStringRange(run)
            return ["range": [range.location, range.length], "font": info(actual)]
        }
    }
    public static func snapshot(names: [String] = []) -> [String: Any] {
        let system = NSFont.systemFont(ofSize: 13)
        let ui = CTFontCreateUIFontForLanguage(.system, 13, "zh-Hans" as CFString)!
        var result: [String: Any] = [
            "appkitSystem": info(system), "appkitBold": info(NSFont.boldSystemFont(ofSize: 13)),
            "appkitWeighted": info(NSFont.systemFont(ofSize: 13, weight: .medium)),
            "coreTextUI": info(ui),
            "chineseFallback": runs(ui, text: "系统设置 文件 编辑 显示 窗口 帮助"),
            "latinFallback": runs(ui, text: "The quick brown fox 0123456789"),
            "emojiFallback": runs(ui, text: "😀")]
        result["byName"] = Dictionary(uniqueKeysWithValues: names.map { ($0, info(CTFontCreateWithName($0 as CFString, 13, nil))) })
        return result
    }
    public static func installHook(name: String) -> Bool { FLInstallHook(name) }
    public static func removeHook() { FLRemoveHook() }
    public static func json(_ value: Any) throws -> Data { try JSONSerialization.data(withJSONObject: value, options: [.prettyPrinted, .sortedKeys, .withoutEscapingSlashes]) }
    public static func write(_ value: Any, to url: URL) throws { try json(value).write(to: url, options: .atomic) }
}
