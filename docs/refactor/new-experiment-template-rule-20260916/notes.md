# 新实验骨架规则固化

用户确认：以后每次新建实验 ID，使用 `experiments/_template/` 的 6 文件骨架。本次仅追加项目规则，不创建具体新 ID。

核验：6/6 模板文件存在；AGENTS.md 原有 7907 字节完整保留；新增链接均存在；CLAUDE.md 通过 `@AGENTS.md` 使用唯一规则源。

### Bug Post-Mortem
- **现象**: 首次追加脚本在解析时出现 `SyntaxError: bytes can only contain ASCII literal characters`，没有执行写盘。
- **根因**: 在 Python 的 bytes 字面量里直接使用中文标题。
- **修复**: 改为 Unicode 字符串调用 `.encode()`，重新执行并核验追加前缀。
- **Prevention Rule**: 含非 ASCII 文本的字节比较使用显式 UTF-8 编码，不直接写入 bytes 字面量。
