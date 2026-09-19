### Bug Post-Mortem
- **现象**: 结果审核首次重发时，`setsid claude ...` 立即报 `zsh: command not found: setsid`，没有产生 Claude 审核结论。
- **根因**: 当前 macOS 环境未提供 Linux 常见的 `setsid` 命令；后台保活方式未经本机可用性核验。
- **修复**: 改用 macOS 可用的 `nohup claude ...`，将只读审核的标准输出写入临时文件，结束后再写入正式审核记录。
- **Prevention Rule**: macOS 上后台审核优先使用 `nohup`；启动后必须核验 PID、输出文件大小和最终退出状态，不能把启动命令成功提交当作审核完成。

### Bug Post-Mortem
- **现象**: 改用 `nohup` 后，Claude 审核仍立即退出且输出文件为空。
- **根因**: 命令先用 `< prompt-file` 提供审查内容，又在末尾追加 `< /dev/null`，后一个重定向覆盖了前者。
- **修复**: 删除末尾的 `/dev/null` 标准输入重定向，只保留审查 prompt 文件作为 stdin；新 PID 已存活。
- **Prevention Rule**: 后台 CLI 命令只能声明一个 stdin 来源；每次发车后先检查 prompt 非空、PID 存活和输出是否开始增长。

### Bug Post-Mortem
- **现象**: `claude -p` 仅通过标准输入提供 prompt 时静默退出，未返回可归档 verdict。
- **根因**: 当前 CLI 调用方式要求将审查文本作为位置参数；stdin 不是该模式下可靠的 prompt 来源。
- **修复**: 将完整审查 prompt 作为 `claude -p` 的位置参数，并以 `tee` 同步保存完整输出。
- **Prevention Rule**: Claude 审核固定使用位置参数传入 prompt；结束后同时核验退出码与非空输出，再写入正式审核文件。

### Bug Post-Mortem
- **现象**: 第二次前台 Claude 审核超过调用窗口后虽已结束，但输出没有持久化，无法得到可复核 verdict。
- **根因**: 审核进程的标准输出只连接短生命周期调用通道，没有并行写入审计文件。
- **修复**: 后续复审在启动时用 `tee` 写入唯一临时输出文件；仅在退出码为零且文件非空时归档。
- **Prevention Rule**: 预计超过交互窗口的 Claude 审核必须先持久化标准输出；未验证输出文件前不把审核视为完成。
