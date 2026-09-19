### Bug Post-Mortem
- **现象**: 首次共享 GPU 发车前的 `pgrep -af` 输出了当前核验 shell，可能被误读为已有 S0-force 任务。
- **根因**: 正则表达式同时出现在正在执行的 shell 命令行中，进程搜索没有限制为 Python 评测进程。
- **修复**: 改为 `ps` 后限定 Python 进程与完整 `source/run.py` 路径；第二次核验确认没有目标 Python 进程。
- **Prevention Rule**: 发车去重只能匹配目标解释器进程，不能用会匹配自身命令行的宽泛 `pgrep` 结果作为运行证据。

### Bug Post-Mortem
- **现象**: 四机只读扫描命令因嵌套 `awk` 的引号未闭合而在本机退出，未发出远端查询。
- **根因**: JavaScript 字符串、SSH 单引号和 `awk` 单引号同时嵌套，转义边界错误。
- **修复**: 将 GPU 状态查询与 Python 目标进程去重拆成独立的远端命令，取消嵌套 `awk`。
- **Prevention Rule**: SSH 诊断命令不得在同一字符串嵌套三层单引号；跨机扫描优先拆为无过滤状态查询和独立去重查询。
