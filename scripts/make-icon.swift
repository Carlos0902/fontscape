import AppKit
let directory = URL(fileURLWithPath: CommandLine.arguments[1])
try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
for size in [16, 32, 128, 256, 512] {
    for scale in [1, 2] {
        let pixels = size * scale
        let image = NSImage(size: NSSize(width: pixels, height: pixels))
        image.lockFocus()
        let p = CGFloat(pixels)
        let rect = NSRect(x: p * 0.06, y: p * 0.06, width: p * 0.88, height: p * 0.88)
        NSColor(calibratedRed: 0.16, green: 0.35, blue: 0.32, alpha: 1).setFill()
        NSBezierPath(roundedRect: rect, xRadius: p * 0.19, yRadius: p * 0.19).fill()
        let font = NSFont(name: "Georgia", size: p * 0.67) ?? .systemFont(ofSize: p * 0.67)
        let attrs: [NSAttributedString.Key: Any] = [.font: font, .foregroundColor: NSColor(calibratedWhite: 0.96, alpha: 1)]
        let label = "F" as NSString
        let bounds = label.size(withAttributes: attrs)
        label.draw(at: NSPoint(x: (p - bounds.width) / 2, y: (p - bounds.height) / 2 + p * 0.025), withAttributes: attrs)
        image.unlockFocus()
        let rep = NSBitmapImageRep(data: image.tiffRepresentation!)!
        let suffix = scale == 2 ? "@2x" : ""
        try rep.representation(using: .png, properties: [:])!.write(to: directory.appendingPathComponent("icon_\(size)x\(size)\(suffix).png"))
    }
}
