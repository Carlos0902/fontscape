# 内置构建工具

Fontscape 0.3 的系统字体构建运行于普通用户子进程。Release 内包含以下工具，不在线安装运行时依赖：

- CPython 3.12.16，使用 [python-build-standalone](https://github.com/astral-sh/python-build-standalone) 的 20261026 arm64 install-only stripped 分发；来源、固定 SHA256 与提取规则记录在 `scripts/bundle-runtime.py`。标准库许可证保留于 `Contents/Resources/Runtime/aarch64/lib/python3.12/LICENSE.txt`。运行时中其他组件适用各自许可，随包保留的上游许可文本位于 `Contents/Resources/Runtime/LICENSES/`，源码副本位于 `docs/runtime-licenses/`。
- [fontTools 4.60.2](https://github.com/fonttools/fonttools)，从 PyPI 的 pure-Python wheel 获取，许可证保留于 `Contents/Resources/Runtime/fonttools/fonttools-4.60.2.dist-info/licenses/`。

构建时下载并核对固定 SHA256 的 fontTools wheel，发行包移除了 CPython 分发中的 pip 包和构建命令。没有内置 Apple 字体或 HanNews 字体，字体候选仅由用户在本机生成，不应再次分发。

源码的 MIT 许可证不改变上述第三方组件及用户字体的许可。
