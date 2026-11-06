import Foundation
import Darwin

public enum SystemFontEngine {
    public static let store = URL(fileURLWithPath: "/Library/Application Support/Fontscape/SystemFonts", isDirectory: true)
    static let statusURL = store.appendingPathComponent("status.json")
    static let receiptURL = store.appendingPathComponent("transaction/receipt.json")
    static let fm = FileManager.default

    public static func command(_ path: String, _ args: [String] = []) throws -> Data {
        let p = Process(); p.executableURL = URL(fileURLWithPath: path); p.arguments = args
        p.environment = ["PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "LC_ALL": "C"]
        let out = Pipe(); p.standardOutput = out
        // Error output goes to a file so a full stderr pipe cannot deadlock privileged operations.
        let errors = fm.temporaryDirectory.appendingPathComponent("fontscape-error-" + UUID().uuidString)
        guard fm.createFile(atPath: errors.path, contents: nil, attributes: [.posixPermissions: 0o600]) else { throw SystemFontError.refused("无法创建诊断日志。") }
        defer { try? fm.removeItem(at: errors) }
        let handle = try FileHandle(forWritingTo: errors); defer { try? handle.close() }
        p.standardError = handle
        try p.run(); let data = out.fileHandleForReading.readDataToEndOfFile(); p.waitUntilExit()
        guard p.terminationStatus == 0 else {
            let error = (try? String(contentsOf: errors, encoding: .utf8)) ?? ""
            throw SystemFontError.refused("\(path) 失败 (\(p.terminationStatus))：\(error.suffix(3000))\(String(decoding: data.suffix(3000), as: UTF8.self))")
        }
        return data
    }
    static func string(_ path: String, _ args: [String]) throws -> String {
        String(decoding: try command(path, args), as: UTF8.self).trimmingCharacters(in: .whitespacesAndNewlines)
    }
    static func plist(_ args: [String]) throws -> [String: Any] {
        guard let value = try PropertyListSerialization.propertyList(from: command("/usr/sbin/diskutil", args), format: nil) as? [String: Any] else { throw SystemFontError.refused("无法读取 APFS 信息。") }; return value
    }
    static func protectionDisabled(_ status: String) -> Bool {
        let first = status.components(separatedBy: .newlines).first?.trimmingCharacters(in: .whitespacesAndNewlines).lowercased() ?? ""
        return first.range(of: "^(system integrity protection|authenticated root) status: disabled\\.?$", options: .regularExpression) != nil
    }
    static func bootID() throws -> String { try string("/usr/sbin/sysctl", ["-n", "kern.bootsessionuuid"]) }
    static func build() throws -> String { try string("/usr/bin/sw_vers", ["-buildVersion"]) }
    static func architecture() throws -> String { (try? string("/usr/sbin/sysctl", ["-n", "hw.optional.arm64"])) == "1" ? "arm64" : "x86_64" }
    static func systemVolume() throws -> [String: Any] {
        let root = try plist(["info", "-plist", "/"])
        let layout = try plist(["apfs", "list", "-plist"])
        guard let bootDevice = root["DeviceIdentifier"] as? String, let containers = layout["Containers"] as? [[String: Any]] else { throw SystemFontError.refused("无法识别启动卷。") }
        let matches = containers.flatMap { $0["Volumes"] as? [[String: Any]] ?? [] }.filter {
            guard let device = $0["DeviceIdentifier"] as? String, let roles = $0["Roles"] as? [String] else { return false }
            return roles.contains("System") && (bootDevice == device || bootDevice.hasPrefix(device + "s"))
        }
        guard matches.count == 1, let device = matches[0]["DeviceIdentifier"] as? String else { throw SystemFontError.refused("无法唯一定位当前启动系统卷。") }
        let info = try plist(["info", "-plist", "/dev/" + device])
        guard info["VolumeUUID"] as? String != nil else { throw SystemFontError.refused("系统卷缺少 UUID。") }
        return info
    }
    public static func inspect() throws -> [String: Any] {
        let os = try build(), arch = try architecture()
        let sip = try string("/usr/bin/csrutil", ["status"])
        let auth = try string("/usr/bin/csrutil", ["authenticated-root", "status"])
        let model = try string("/usr/sbin/sysctl", ["-n", "hw.model"])
        let volume = try systemVolume()
        var state: [String: Any] = ["osBuild": os, "architecture": arch, "model": model,
            "supported": os == "25G83" && arch == "arm64", "sip": sip, "authenticatedRoot": auth,
            "protectionsReady": protectionDisabled(sip) && protectionDisabled(auth),
            "volumeUUID": volume["VolumeUUID"]!, "bootSession": try bootID(),
            "fonts": Dictionary(uniqueKeysWithValues: FontPackage.targets.map { ($0, (try? fontDigest(at: URL(fileURLWithPath: $0))) ?? "unavailable") })]
        if let data = try? Data(contentsOf: statusURL), let saved = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
            state["transaction"] = saved
            state["bootVerified"] = bootMatches(saved, current: state)
        }
        return state
    }
    static func bootMatches(_ saved: [String: Any], current: [String: Any]) -> Bool {
        guard ["installPrepared", "rollbackPrepared"].contains(saved["phase"] as? String ?? ""),
              let expected = saved["expected"] as? [String: String], Set(expected.keys) == Set(FontPackage.targets),
              let before = saved["bootSession"] as? String, let now = current["bootSession"] as? String, before != now,
              let uuid = saved["volumeUUID"] as? String, uuid == current["volumeUUID"] as? String,
              saved["osBuild"] as? String == current["osBuild"] as? String,
              let actual = current["fonts"] as? [String: String] else { return false }
        return expected.allSatisfy { actual[$0.key] == $0.value }
    }
    static func json(_ value: Any, to url: URL) throws {
        try JSONSerialization.data(withJSONObject: value, options: [.prettyPrinted, .sortedKeys]).write(to: url, options: .atomic)
        try fm.setAttributes([.posixPermissions: 0o644], ofItemAtPath: url.path)
        let handle = try FileHandle(forWritingTo: url); try handle.synchronize(); try handle.close()
    }
    static func requireRoot() throws { guard geteuid() == 0 else { throw SystemFontError.refused("此操作需要系统管理员授权。") } }
    static func secureDirectory(_ url: URL, mode: Int = 0o700) throws {
        if fm.fileExists(atPath: url.path) {
            let attr = try fm.attributesOfItem(atPath: url.path)
            guard attr[.type] as? FileAttributeType == .typeDirectory, (attr[.ownerAccountID] as? NSNumber)?.intValue == 0,
                  ((attr[.posixPermissions] as? NSNumber)?.intValue ?? 0) & 0o022 == 0 else { throw SystemFontError.refused("拒绝使用所有权或权限不安全的备份目录：\(url.path)") }
        } else { try fm.createDirectory(at: url, withIntermediateDirectories: false, attributes: [.posixPermissions: mode]) }
    }
    static func prepareStore() throws {
        // Parent Application Support exists on supported macOS installations.
        try secureDirectory(URL(fileURLWithPath: "/Library/Application Support/Fontscape"), mode: 0o755)
        try secureDirectory(store, mode: 0o755)
    }
    static func exclusiveLock<T>(_ body: () throws -> T) throws -> T {
        try requireRoot(); try prepareStore()
        let lock = store.appendingPathComponent("lock").path
        let fd = open(lock, O_RDWR | O_CREAT | O_NOFOLLOW, 0o600)
        guard fd >= 0 else { throw SystemFontError.refused("无法打开事务锁。") }
        defer { close(fd) }
        guard flock(fd, LOCK_EX | LOCK_NB) == 0 else { throw SystemFontError.refused("已有字体操作正在执行。") }
        defer { flock(fd, LOCK_UN) }
        return try body()
    }
    static func checkState(_ expectedVolume: String? = nil) throws -> [String: Any] {
        let state = try inspect()
        guard state["supported"] as? Bool == true else { throw SystemFontError.refused("此引擎只支持 Apple Silicon / macOS 26.6.2 (25G83)。") }
        guard state["protectionsReady"] as? Bool == true else { throw SystemFontError.refused("系统保护尚未准备好。请阅读应用内指引，在 Recovery 中手动调整；本应用不会自动修改保护配置。") }
        if let expectedVolume, state["volumeUUID"] as? String != expectedVolume { throw SystemFontError.refused("备份属于其他系统卷，拒绝写入。") }
        return state
    }
    static func mountedSystemVolume() throws -> (URL, Bool) {
        let volume = try systemVolume(), device = volume["DeviceIdentifier"] as! String
        let mounts = try string("/sbin/mount", [])
        if let line = mounts.components(separatedBy: .newlines).first(where: { $0.hasPrefix("/dev/" + device + " on ") }),
           let range = line.range(of: " on "), let end = line.range(of: " (", options: .backwards) {
            let path = String(line[range.upperBound..<end.lowerBound])
            guard path != "/" else { throw SystemFontError.refused("拒绝把当前根快照作为可写系统卷。") }
            let url = URL(fileURLWithPath: path)
            let actual = try plist(["info", "-plist", path])
            guard actual["VolumeUUID"] as? String == volume["VolumeUUID"] as? String,
                  actual["DeviceIdentifier"] as? String == device else { throw SystemFontError.refused("已挂载卷身份不匹配。") }
            return (url, false)
        }
        let url = URL(fileURLWithPath: "/private/tmp/fontscape-system-" + UUID().uuidString)
        try fm.createDirectory(at: url, withIntermediateDirectories: false, attributes: [.posixPermissions: 0o700])
        do {
            _ = try command("/sbin/mount_apfs", ["-o", "nobrowse", "/dev/" + device, url.path])
            let actual = try plist(["info", "-plist", url.path])
            guard actual["VolumeUUID"] as? String == volume["VolumeUUID"] as? String,
                  actual["DeviceIdentifier"] as? String == device else { throw SystemFontError.refused("挂载系统卷身份不匹配。") }
        } catch { _ = try? command("/sbin/umount", [url.path]); _ = removeEmptyMountpoint(url); throw error }
        return (url, true)
    }
    // Never use recursive file removal on a mountpoint. rmdir fails on a
    // mounted or nonempty directory, including when unmount was unsuccessful.
    static func removeEmptyMountpoint(_ url: URL) -> Bool { rmdir(url.path) == 0 }
    static func readRegular(_ url: URL) throws -> Data {
        let fd = open(url.path, O_RDONLY | O_NOFOLLOW)
        guard fd >= 0 else { throw SystemFontError.refused("无法读取普通文件：\(url.path)") }
        let handle = FileHandle(fileDescriptor: fd, closeOnDealloc: true)
        var st = stat(); guard fstat(fd, &st) == 0, (st.st_mode & S_IFMT) == S_IFREG,
              st.st_size > 0, st.st_size < 800_000_000 else { throw SystemFontError.refused("字体文件类型或大小无效。") }
        return try handle.readToEnd() ?? Data()
    }
    static func writeFont(_ data: Data, to url: URL) throws {
        // O_NOFOLLOW and no O_CREAT: only the two existing, allowlisted system-font files can be written.
        let fd = open(url.path, O_WRONLY | O_NOFOLLOW)
        guard fd >= 0 else { throw SystemFontError.refused("无法打开目标字体：\(url.path)") }
        let handle = FileHandle(fileDescriptor: fd, closeOnDealloc: true)
        var st = stat(); guard fstat(fd, &st) == 0, (st.st_mode & S_IFMT) == S_IFREG else { throw SystemFontError.refused("系统字体目标类型异常。") }
        try handle.truncate(atOffset: 0); try handle.write(contentsOf: data); try handle.synchronize()
        guard fchmod(fd, 0o644) == 0, fchown(fd, 0, 0) == 0, try fontDigest(at: url) == fontDigest(data) else { throw SystemFontError.refused("写入字体后的核验失败。") }
    }
    public static func apply(package url: URL) throws -> [String: Any] {
        try exclusiveLock {
            let state = try checkState()
            guard !fm.fileExists(atPath: receiptURL.path) else { throw SystemFontError.refused("已有未归档事务。请先回滚并完成启动核验，再归档备份。") }
            let package = try JSONDecoder().decode(FontPackage.self, from: readRegular(url.appendingPathComponent("manifest.json")))
            try package.validate()
            let candidates = try package.files.map { file -> Data in
                let data = try readRegular(url.appendingPathComponent(file.candidate))
                guard fontDigest(data) == file.candidateSHA256 else { throw SystemFontError.refused("候选字体校验失败。") }; return data
            }
            // A package must be based on the exact active originals, never a previous replacement.
            let originals = try package.files.map { file -> Data in
                let data = try readRegular(URL(fileURLWithPath: file.target))
                guard fontDigest(data) == file.sourceSHA256 else { throw SystemFontError.refused("当前字体已更改或系统版本不匹配，请先恢复原系统字体。") }; return data
            }
            let transaction = receiptURL.deletingLastPathComponent(); try secureDirectory(transaction)
            for (i, file) in package.files.enumerated() {
                let backup = transaction.appendingPathComponent(file.candidate)
                try originals[i].write(to: backup, options: .withoutOverwriting)
                let handle = try FileHandle(forWritingTo: backup); try handle.synchronize(); try handle.close()
                guard try fontDigest(at: backup) == file.sourceSHA256 else { throw SystemFontError.refused("备份校验失败，未写入系统字体。") }
            }
            var receipt: [String: Any] = ["phase": "prepared", "osBuild": try build(), "volumeUUID": state["volumeUUID"]!,
                "bootSession": state["bootSession"]!, "files": try JSONSerialization.jsonObject(with: JSONEncoder().encode(package.files)),
                "created": ISO8601DateFormatter().string(from: Date()), "expected": Dictionary(uniqueKeysWithValues: package.files.map { ($0.target, $0.candidateSHA256) })]
            try json(receipt, to: receiptURL); try json(receipt, to: statusURL)
            return try mutate(files: package.files, bytes: candidates, rollbackBytes: originals, state: &receipt, restoring: false)
        }
    }
    static func mutate(files: [FontFile], bytes: [Data], rollbackBytes: [Data], state: inout [String: Any], restoring: Bool) throws -> [String: Any] {
        let (mount, ownMount) = try mountedSystemVolume()
        defer { if ownMount { _ = try? command("/sbin/umount", [mount.path]); _ = removeEmptyMountpoint(mount) } }
        _ = try command("/sbin/mount", ["-uw", mount.path])
        let targets = files.map { mount.appendingPathComponent(String($0.target.dropFirst())) }
        // Validate every underlying file before changing any file.
        for (i, file) in files.enumerated() {
            let actual = try fontDigest(at: targets[i])
            guard [file.sourceSHA256, file.candidateSHA256].contains(actual) || (restoring && ["writing", "restoring", "needsRecovery"].contains(state["phase"] as? String ?? "")) else { throw SystemFontError.refused("底层系统卷字体不是事务中记录的版本，停止写入。") }
        }
        var attempted = [Int]()
        do {
            state["phase"] = restoring ? "restoring" : "writing"; try json(state, to: receiptURL); try json(state, to: statusURL)
            for i in files.indices { attempted.append(i); try writeFont(bytes[i], to: targets[i]) }
            _ = try command("/bin/sync")
            state["blessOutput"] = String(decoding: try command("/usr/sbin/bless", ["--mount", mount.path, "--bootefi", "--create-snapshot", "--verbose"]), as: UTF8.self)
            state["phase"] = restoring ? "rollbackPrepared" : "installPrepared"
            state["bootSession"] = try bootID()
            try json(state, to: receiptURL); try json(state, to: statusURL)
            return state
        } catch {
            state["error"] = error.localizedDescription
            var failures = [String]()
            for i in attempted { do { try writeFont(rollbackBytes[i], to: targets[i]) } catch { failures.append(error.localizedDescription) } }
            // Selection of a partly prepared snapshot may be ambiguous. Never label this 'rolled back'.
            state["phase"] = "needsRecovery"; state["fileRecoveryErrors"] = failures
            try? json(state, to: receiptURL); try? json(state, to: statusURL)
            throw SystemFontError.refused("系统字体操作未完成。原文件恢复错误：\(failures.joined(separator: "; "))。请保留备份，按恢复指引处理。\(error.localizedDescription)")
        }
    }
    public static func rollback() throws -> [String: Any] {
        try exclusiveLock {
            var receipt = try JSONSerialization.jsonObject(with: readRegular(receiptURL)) as! [String: Any]
            guard let uuid = receipt["volumeUUID"] as? String, let os = receipt["osBuild"] as? String,
                  os == (try build()), let raw = receipt["files"] else { throw SystemFontError.refused("备份版本或事务记录无效。") }
            _ = try checkState(uuid)
            let files = try JSONDecoder().decode([FontFile].self, from: JSONSerialization.data(withJSONObject: raw))
            // Reuse the strict allowlist validation for stored manifests too.
            let package = ["format": 1, "osBuild": os, "architecture": "arm64", "hanSpacing": 0, "files": raw] as [String: Any]
            try JSONDecoder().decode(FontPackage.self, from: JSONSerialization.data(withJSONObject: package)).validate()
            let backups = try files.map { file -> Data in
                let data = try readRegular(receiptURL.deletingLastPathComponent().appendingPathComponent(file.candidate))
                guard fontDigest(data) == file.sourceSHA256 else { throw SystemFontError.refused("原始字体备份校验失败，拒绝回滚。") }; return data
            }
            receipt["expected"] = Dictionary(uniqueKeysWithValues: files.map { ($0.target, $0.sourceSHA256) })
            return try mutate(files: files, bytes: backups, rollbackBytes: backups, state: &receipt, restoring: true)
        }
    }
    public static func archive() throws -> [String: Any] {
        try exclusiveLock {
            let state = try inspect()
            guard state["bootVerified"] as? Bool == true, let transaction = state["transaction"] as? [String: Any],
                  transaction["phase"] as? String == "rollbackPrepared" else { throw SystemFontError.refused("仅在回滚后重新启动且原始字体核验通过时，才能归档事务。") }
            let destination = store.appendingPathComponent("archive-" + UUID().uuidString)
            try fm.moveItem(at: receiptURL.deletingLastPathComponent(), to: destination)
            try fm.removeItem(at: statusURL)
            return ["archived": true, "backupPreserved": true]
        }
    }
}
