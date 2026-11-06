# Fontscape

原生 macOS 字体工具：导入与预览、当前用户安装、本应用内试用，以及**系统字体替换和原始字体回滚**。

**0.3 公开测试版的系统替换只接受 Apple Silicon / macOS 26.6.2（25G83）及已验证的原始字体版本。替换、冷启动、回滚流程在虚拟机测试；实体 Mac 尚未验证。** 需要手动在 Recovery 准备系统保护配置和独立整机备份，不能把本应用视为任意 Mac 的稳定换字体工具。

## 下载

前往 [v0.3.0-beta.2](https://github.com/Carlos0902/fontscape/releases/tag/v0.3.0-beta.2)，下载 Universal ZIP，解压后将 `Fontscape.app` 拖入“应用程序”。预览与用户字体功能支持 macOS 14+；Intel 仅完成交叉构建，系统替换不支持 Intel。

- 不需要安装 Python、Homebrew 或 Xcode。系统字体构建器内置离线 CPython 与 fontTools。
- 目前是 ad-hoc 签名，没有 Developer ID 签名和 Apple 公证。核对 Release 来源与 SHA256；首次被 Gatekeeper 阻止时，按 macOS 正常流程在“系统设置 → 隐私与安全性”选择“仍要打开”。不要关闭 Gatekeeper。组织管理策略可能不允许打开。
- 不包含任何字体，请自行导入有权使用的字体。系统替换包包含本机 Apple 字体衍生内容，请勿上传、分享或提交到本仓库。
- 在虚拟机内使用时，把 ZIP 复制到客体再解压；不要直接从共享文件夹运行 app。部分虚拟机共享文件系统不能正确复制运行时符号链接。

## 全系统替换与回滚

完整步骤在 [操作与恢复指引](docs/SYSTEM_GUIDE.md)，应用内“操作与恢复指引”提供同一份离线文档。**执行前先读完整篇，尤其是无法启动时的恢复方式。**

1. **准备恢复来源**：虚拟机先保留可启动的关机克隆；实体 Mac 先做独立可恢复的整机备份。应用的两个字体备份不能代替整机恢复。
2. **生成替换包**：导入同时包含中文和西文的单字体 TrueType TTF，滚动至“全系统字体替换”。刷新并核对当前设备、`arm64` 和 `25G83`，设置汉字间距（默认从原始宽度增加 **6% em**），点击“用当前字体生成替换包”。此步骤不修改系统文件，可能持续数分钟并需数 GB 临时空间。
3. **手动准备 Recovery**：严格在目标测试系统的恢复环境中，按指引调整 SIP 与 authenticated-root；回到目标系统刷新状态。应用不会自动关闭保护或改变安全启动策略。两项未明确 disabled 时不能应用。
4. **备份并应用**：点击“备份并应用替换包”，阅读确认框、确认独立备份、输入“替换”或 `apply`，完成 macOS 管理员授权。引擎保存并校验原始字体、记录系统卷 UUID，再写入并创建快照。
5. **确认生效**：`installPrepared` 只表示快照准备完成。完全关机再启动，重新打开应用并刷新，确认“本次启动字体哈希已核验”，再检查实际界面。
6. **回滚**：在同一系统卷内点“恢复原始系统字体”，输入“回滚”或 `rollback`并授权。出现 `rollbackPrepared` 后完全关机再启动、刷新核验。核验通过后才能“归档已验证的回滚”；归档会保留备份。

备份和事务记录位于 `/Library/Application Support/Fontscape/SystemFonts/`，由 root 管理。不要手动删除、编辑或用于其他系统卷。系统更新前先回滚并核验；更新后本版可能拒绝旧替换包。

**字体回滚不等于系统保护恢复。** 恢复字体后的自制快照不自动成为 Apple 密封快照。恢复完整原系统并确认启动后，才能按指引恢复原安全配置；不要直接在修改后的启动链上重新开启 authenticated-root 并假定一定可启动。无法进入桌面时，应用按钮不可用，必须使用事前整机备份、可启动克隆或 Apple Recovery 流程。

## 覆盖范围与限制

| 功能 | 范围 |
|---|---|
| 系统替换 | SFNS.ttf 与 PingFangUI.ttc 的 32 个中文字体面；不代表所有应用与所有字体都被替换 |
| 符号与排版 | 保留 SFNS 原生符号及字宽；修复部分复合字形和字偶问题，仍需人工检查 |
| 汉字间距 | 可选 0–10% em，默认 6%；从原始字体生成，不叠加旧调整 |
| 多字重 | 源轮廓用于多个请求字重，不能产生真实的 Regular/Bold/Light |
| 未覆盖中文 | 使用导出的简体常规字形回退，地区字形和上下文排版可能不同 |
| 其他应用 | 应用自带字体、Emoji、其他回退字体不在此两文件的覆盖范围 |
| 支持配置 | arm64 / 25G83 / 指定原始字体哈希；Intel、其他系统或已修改源字体会被拒绝 |
| 恢复 | 原字体备份、同卷同版本校验、启动会话和文件哈希核验；没有任意故障下自动恢复启动的保证 |

## 普通字体功能

1. “导入字体”复制字体到本应用支持目录，原文件保持不变。预览支持 TTF、OTF、TTC、OTC；集合目前只预览第一个字体面，系统构建器只接受 TrueType TTF。
2. 编辑预览文字和字号。“安装到当前用户”可供支持选择字体的应用使用；再次点击可卸载。**用户级安装不会改变 Finder 或菜单栏字体。**
3. “试用 AppKit Hook”只影响 Fontscape 自己的三个 NSFont API。点击恢复或退出即可结束；直接 Core Text 不经过这些 Hook。
4. “运行兼容性检查”在独立子进程验证加载、试用和恢复，生成 JSON 报告；不代表其他应用或系统已换字体。

用户字体安装记录、导入副本、报告与生成包位于 `~/Library/Application Support/Fontscape/`。卸载应用前先卸载由它安装的用户字体。系统替换若仍生效，先回滚并验证；不能直接删除系统字体备份目录。

## 构建与验证

需要 Apple Command Line Tools、Python 3 和网络（仅构建时下载固定的 CPython 发行包及 fontTools）。打包后的应用不需要网络安装这些依赖。

```sh
git clone https://github.com/Carlos0902/fontscape.git
cd fontscape
zsh scripts/check-system-engine.sh
zsh scripts/build-app.sh
open dist/Fontscape.app
```

生成 `dist/Fontscape-0.3.0-beta.2-macos-universal.zip` 与 `SHA256SUMS.txt`。打包脚本核验三个原生可执行文件、签名、内置运行时及说明文档；GitHub Actions 也执行这些检查。系统构建器只在 arm64 使用，其内置 Python 为 arm64。

运行只读状态检查：

```sh
swift build -c release
.build/release/fontscape-system inspect
.build/release/fontlab-probe snapshot
```

`fontscape-system apply`、`rollback`、`archive` 为应用调用的管理员入口，版本、原始字体、路径和卷校验不应移除。请通过应用的确认流程操作。引擎不接受任意系统路径。

实测范围见 [验证记录](docs/VALIDATION.md)，历史研究见 [高级实验说明](docs/ADVANCED.md)。旧脚本依赖本地夹具，不是公开应用的日常入口。仓库不含字体、轮廓导出、虚拟机或私人报告；生成物留在本地 `artifacts/`。

代码采用 [MIT License](LICENSE)。内置组件说明见 [第三方工具](docs/THIRD_PARTY.md)，字体受各自许可约束。报告问题请附系统版本、架构、操作步骤、事务阶段及去除个人路径的日志，不要提交私有字体或凭据。
