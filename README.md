# Fontscape

原生 macOS 字体预览与试用工具。导入自己的字体，查看中英文效果、安装为当前用户字体，并在本应用内试用系统字体 API 替换。

**公开测试版：不提供实体 Mac 的一键全系统字体替换。** 系统卷替换已在 macOS 26.6.2 虚拟机中验证，研究代码保留在仓库中。公开应用不会关闭 SIP、修改启动快照，或向 Finder 等其他进程注入代码。

## 下载与安装

从 [Releases](https://github.com/Carlos0902/fontscape/releases) 下载 ZIP，解压后把 `Fontscape.app` 拖入“应用程序”，再打开。

- macOS 14 或更高版本。
- 通用包包含 arm64 与 x86_64。Apple Silicon 已在 macOS 26.6.2 实测；Intel 仅完成交叉构建，尚未真机验证。
- 预览、安装/卸载、应用内试用和兼容性检查均不需要 Python、Homebrew 或 Xcode。
- 当前没有 Developer ID 签名或 Apple 公证。首次打开可能被 Gatekeeper 拦截；核对本仓库 Release 和 SHA256 后，可按 macOS 正常流程在“系统设置 → 隐私与安全性”选择“仍要打开”。不要关闭 Gatekeeper 或 SIP。受组织管理的 Mac 可能不允许打开未公证应用。
- 不捆绑任何字体，请自行导入有权使用的 TTF、OTF、TTC 或 OTC。

## 使用

1. 点“导入字体”，选择字体文件。应用复制字体到自己的支持目录，原文件不变。
2. 编辑预览文字并调整字号。TTC/OTC 目前只预览第一个字体面。
3. “安装到当前用户”让支持选择字体的应用使用它；按钮随后可卸载该字体。已有应用可能需要重启才能刷新字体列表。**安装为用户字体不会把 Finder、菜单栏等换成该字体。**
4. “试用 AppKit Hook”仅改变 Fontscape 自己的三个 NSFont API 请求。点“恢复 AppKit”或退出应用即可结束试用。固定字重字体无法提供真实的多字重变化。
5. “运行兼容性检查”在独立子进程加载字体、验证本应用试用和恢复，完成后可打开 JSON 报告。结果只代表已检查的 API，不表示整个系统已换字体。

## 恢复与卸载

- 结束本应用试用：点“恢复 AppKit”/“恢复本应用”或退出 Fontscape。
- 卸载 Fontscape 安装的字体：重新导入同一文件，点“卸载当前用户字体”。应用只管理自己登记、哈希匹配的安装，不删除其他字体。
- 安装记录与字体副本：`~/Library/Application Support/Fontscape/`。先卸载已安装字体，再移除应用。**字体仍持久注册时不要直接删除支持目录。**
- 报告位于该目录的 `Experiments/`；字体副本位于 `Imports/`，安装记录为 `installed-fonts.json`。
- 检查进程退出后，进程内注册和 Hook 自然消失。用户安装是持久操作，需要主动卸载。

## 当前边界

| 功能 | 状态 |
|---|---|
| 导入与真实字体预览 | 原生实现 |
| 当前用户字体安装/卸载 | 原生 Core Text，持久注册，有所有权记录 |
| 本应用内试用 | 普通、粗体、带字重的 NSFont API；直接 Core Text 不经过 Hook |
| 原生兼容性报告 | 独立进程检查并核验恢复 |
| 整个 macOS 一键换字体 | 不在公开应用中提供 |
| 多字体面、多字重编辑 | 尚未提供完整支持 |
| 正式签名、公证、自动更新 | 尚未提供 |

## 从源码构建

安装 Apple Command Line Tools，然后：

```sh
git clone https://github.com/Carlos0902/fontscape.git
cd fontscape
zsh scripts/build-app.sh
open dist/Fontscape.app
```

构建与打包使用系统 Swift、codesign、ditto，以及构建时的 Python 3 做 JSON 冒烟检查。Python 不属于用户运行时依赖。

命令行探针：

```sh
swift build -c release
.build/release/fontlab-probe snapshot
.build/release/fontlab-probe check /absolute/path/to/font.ttf
```

`check` 只影响其自身进程；退出前核对试用恢复。更高影响范围的名称别名实验仍在 `scripts/experiment.py`，需要 `requirements.txt` 中的 fontTools，并会临时修改当前用户字体目录，普通用户无需运行。

## 系统替换研究

在隔离虚拟机中已验证整包 SFNS + PingFang UI 替换、冷启动和检查点恢复，并修复了一部分图标与间距问题。仍有缺字回退、地区字形、字偶规则和真实多字重限制。**没有验证实体主机部署的可靠性。**

高级脚本有 VirtualMac 与 disposable marker 检查。不要删除这些检查后在实体主机运行。旧研究工具依赖实验目录、导出轮廓和明确的字体版本，不是通用安装器。详见 [高级实验说明](docs/ADVANCED.md)。

仓库及 Release 不包含 Apple 字体、用户提供的字体、导出轮廓、生成的系统字体候选、虚拟机或私人报告。研究生成物仅留在本地 `artifacts/`。

实测范围与未覆盖环境见 [验证记录](docs/VALIDATION.md)。

## 开发与发布

公开应用：`Sources/FontLab/`；字体检查：`Sources/FontLabCore/`；NSFont 试用：`Sources/FontHook/`；命令行：`Sources/FontLabCLI/`。

发布前运行 `scripts/build-app.sh`，生成 Universal ZIP；GitHub Actions 也会构建并检查包内探针。默认 ad-hoc 签名仅供测试，不能代替 Developer ID 与公证。发布包附 SHA256 校验文件。发现问题时请提供系统版本、架构、操作步骤和去除个人路径后的日志，不要提交私有字体或凭据。

代码采用 [MIT License](LICENSE)。导入字体的授权由各字体自己的许可决定。
