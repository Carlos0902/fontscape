import Foundation
import SystemFontEngine

do {
    let args = Array(CommandLine.arguments.dropFirst())
    let result: [String: Any]
    switch args.first ?? "inspect" {
    case "inspect": guard args.count <= 1 else { throw SystemFontError.refused("inspect 不接受参数") }; result = try SystemFontEngine.inspect()
    case "apply": guard args.count == 2 else { throw SystemFontError.refused("用法：fontscape-system apply PACKAGE") }; result = try SystemFontEngine.apply(package: URL(fileURLWithPath: args[1]))
    case "rollback": guard args.count == 1 else { throw SystemFontError.refused("rollback 不接受路径") }; result = try SystemFontEngine.rollback()
    case "archive": guard args.count == 1 else { throw SystemFontError.refused("archive 不接受路径") }; result = try SystemFontEngine.archive()
    default: throw SystemFontError.refused("命令：inspect | apply PACKAGE | rollback | archive")
    }
    FileHandle.standardOutput.write(try JSONSerialization.data(withJSONObject: result, options: [.prettyPrinted, .sortedKeys])); print("")
} catch { fputs("\(error.localizedDescription)\n", stderr); exit(1) }
