import AppKit
import CoreText
import Foundation

func info(_ font: CTFont) -> [String: String] {
    ["postscript": CTFontCopyPostScriptName(font) as String,
     "url": (CTFontCopyAttribute(font, kCTFontURLAttribute) as? URL)?.path ?? ""]
}
let result: [String: Any] = [
    "appkit": info(NSFont.systemFont(ofSize: 13)),
    "bold": info(NSFont.boldSystemFont(ofSize: 13)),
    "weighted": info(NSFont.systemFont(ofSize: 13, weight: .medium)),
    "coreText": info(CTFontCreateUIFontForLanguage(.system, 13, "zh-Hans" as CFString)!)
]
FileHandle.standardOutput.write(try JSONSerialization.data(withJSONObject: result, options: [.prettyPrinted, .sortedKeys]))
print("")
