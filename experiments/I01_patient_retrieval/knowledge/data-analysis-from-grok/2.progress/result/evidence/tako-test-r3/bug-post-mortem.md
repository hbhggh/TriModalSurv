# GPU 门禁阻断：Post-Mortem

- **现象**: 原 `test` 在产生任何正式格点前退出，错误为“目标GPU存在其他计算进程，禁止抢占”。
- **根因**: 评测器以 `nvidia-smi --query-compute-apps=pid` 作为硬门禁；GPU 利用率或剩余显存均不能替代“无计算 PID”。
- **修复**: 连续两次确认 GPU4 无计算 PID 后，保留原 `accel-test.yaml`（SHA `15dfb52fa466cf611a6401d1d5ec0c792b8f3c59384c0e39b08410b07dc1c387`）启动仅 test 的 r3 进程；test 与独立审计均通过。
- **Prevention Rule**: 每次 GPU 评测发车前连续两次核验目标卡的计算 PID；存在任何外部 PID 时等待或换空卡，禁止用 util/显存低替代空卡判定。
