# 高级系统字体实验

0.3 公开应用已集成系统替换与回滚；它需要用户在目标 Recovery 手动准备保护配置。正式操作入口、适用版本与限制见 [操作指引](SYSTEM_GUIDE.md)。以下历史代码仍是研究工具，不是面向实体主机的通用部署步骤。

## 研究中实际验证的范围

环境为 Apple Silicon、macOS 26.6.2（25G83）的独立 Tart VM。原始 CI 镜像 SIP 为 disabled，authenticated-root 为 enabled。系统卷试验只在客体经授权关闭 authenticated-root 后进行，主机保护保持开启。

- 用户级名称覆盖未改变所测系统 UI 字体解析。
- 自有进程内 NSFont Hook 有效，直接 Core Text 不经过它。
- 整包替换 SFNS 与 PingFang UI 的 32 个字体面后，可见中文/英文系统 UI 变化。
- 以新的启动会话、实际字体文件哈希及渲染结果交叉核对，不能把 bless 退出成功当成启动成功。
- 恢复检查点与字体 API 对照已验证。后续改进保护系统符号，调整字宽、重音和上下标。
- 源字体只有 Medium，不能据此声称具备真正的 Regular/Bold/Light。部分字形由原生重音和 donor 组件组合，必须单独标记。

这些结果不外推到其他 macOS 版本、Intel 或实体主机。

## 工具与依赖

构建候选的 Python 工具需要 fontTools。它们以本地系统字体为参考，生成物包含 Apple 回退轮廓，不随仓库分发。`artifacts/` 中的原始报告、导出 JSONL 与候选字体不公开上传，所以历史工具可能需要先重新生成指定输入。

- `experiment.py`：字体别名实验、意图日志与恢复；会临时修改当前用户可用字体，普通用户不需要运行。
- `build-compatible-v*.py`：版本化 SFNS 研究候选与度量策略。
- `build-full-*.py`：整包候选实验，依赖本机导出的原生轮廓。
- `adjust-han-spacing.py`：仅调整汉字 advance，保留轮廓与非汉字度量。
- `guest-system-font.py`、`guest-full-fonts.py`：客体安装研究，默认或入口保护不可删除。
- `vm-lab.py`：固定实验 VM 名称的本地管理工具。不是其他用户已有 VM 的管理器。

## 实验隔离

使用 host-only 网络，关闭剪贴板和 USB 共享，仅只读共享测试包，不挂载主机 HOME 或物理磁盘。不要导入个人 Apple ID、密码或工作数据。开始前保留原始镜像和已验证可启动的关机克隆。

字体文件恢复不等于系统保护恢复。恢复安全启动配置以完整关机检查点恢复为准。任何失败都保留日志，在 VM 中处理；不要把修复动作指向主机。

## 发布纪律

不提交 `.build/`、`dist/`、`artifacts/`、虚拟机、字体、导出轮廓或带个人路径的原始报告。源码不保证每个历史研究脚本可脱离既定夹具运行；公开用户入口是 Fontscape.app。
