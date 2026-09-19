请用中文对本次两份新增文档作只读复审，不修改文件、不训练、不运行实验、不派子agent。可用Read/Glob/Grep。用户要求patient-fixed-padmask-v2 K=128的完整map及可粘贴Grok诊断prompt；旧两结果报告保留，含none参与总排名，三臂并排标红。不要写分数，输出PASS或CONCERNS及可操作问题与行号。不得将未亲自复算描述成你验证通过。

必须全文读取：
/Users/wuhao/Desktop/TriModalSurv/experiments/I01_patient_retrieval/results/patient-fixed-padmask-v2-总实验map.md
/Users/wuhao/Desktop/TriModalSurv/experiments/I01_patient_retrieval/results/Grok-patient-fixed-padmask-v2-诊断prompt.md
/Users/wuhao/Desktop/TriModalSurv/experiments/I01_patient_retrieval/results/_experiment_map_audit/verify_documents.py

必要时抽读：
/Users/wuhao/Desktop/TriModalSurv/experiments/I01_patient_retrieval/results/_grouped_report_audit/verification.json
/Users/wuhao/Desktop/TriModalSurv/experiments/I01_patient_retrieval/results/legacy-tako-formal-20260915/raw/tako-formal/formal-verification.json
/Users/wuhao/Desktop/TriModalSurv/experiments/I01_patient_retrieval/results/legacy-tako-formal-20260915/raw/tako-formal/evidence/formal/diagnostics/preflight.json
/Users/wuhao/.codex/worktrees/774f/TriModalSurv/code/NPJ/model/patient_retrieval_bank.py
/Users/wuhao/.codex/worktrees/774f/TriModalSurv/code/NPJ/model/fusion_model.py
/Users/wuhao/.codex/worktrees/774f/TriModalSurv/code/NPJ/scripts/eval_patient_retrieval.py
/Users/wuhao/.codex/worktrees/774f/TriModalSurv/collab/20260915-M3Surv-fixed-bank/repair-r2/source-before/main_survival.py
/Users/wuhao/.codex/worktrees/774f/TriModalSurv/collab/20260915-M3Surv-fixed-bank/formal-preflight/provenance/scripts/c_unit.sh

重点：K128不是K8；零训练与历史50轮区分，未来200/patience15/B选模不混；历史9月15日源码重建不是训练时快照；A选模仅此证据强度；padmask只检索模型WSI不变，双缺同donor；none保留天然缺失；两口径结果、seed321绝对/213增益、LGG绝对/UCEC增益正确；valid=1不等于置信度1；不把假设当因果，不默认gating/CAP必要；实际代码片段和配置足够供Grok诊断；没有把工程PASS或test挑seed当学术成功。

执行者已实际跑只读verify_documents.py：75JSON/300读数/600artifact哈希/25组配对ckpt/40癌格表行/12源码节选/本地链接检查PASS，旧两结果hash未变。你不必通过Bash重算，但请检查叙述与证据是否一致。末尾写清你的审查边界。
