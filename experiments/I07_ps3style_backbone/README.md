# I07：PS3-style 三模态骨架的完整模态基线与单模态拆解

研究计划书在仓库外（未发表研究方向）。本目录目前只有 Phase 0 数据准备：

| 脚本 | 产物 |
|---|---|
| `prep/cohort.py` | 三模态完整人群清单 `cohort.csv`、逐癌种排除统计 |
| `prep/splits.py` | 5 折 × train/val/test = 70/10/20（按事件分层，种子 2026）|
| `prep/wsi_tokens.py` | 每人 128 个 UNI2-h token + mask（每张切片各自 MiniBatchKMeans，沿用 NPJ 规则）|
| `prep/rna_genes.py` | log2(1+TPM) 的 Hallmark 基因矩阵与通路下标（z-score 在训练时按折拟合）|
| `prep/text_fields.py` | I06 payload 逐字段 NeuML 向量 + not_mentioned mask |

`assets/msigdb/h.all.v2023.2.Hs.symbols.gmt`：MSigDB Hallmark 基因集 v2023.2（CC BY 4.0，Liberzon et al. 2015），
sha256 `8ff1f036f0988c99d42cf9e5ea24d355f10b8ece5e0d4f6edf26a0458f480780`。

## 接口契约与超参数

- `contract.py`：输入 `data.Part`（`wsi [N,128,1536]`、`wsi_mask`、`rna [N,G]`、`text [N,F,768]`、`text_nm`、`time`、`event`），
  `event` = 1 表示死亡（不用 censorship 记法）；模型输出 `{'risk': [N], 'pooled': {...}}`，risk 越大预后越差。
  数据加载、验证与评估入口逐项核对，违约即报错。
- `config.yaml`：全部训练超参数，键与类型由 `contract.CONFIG_TYPES` 强制；`run.json` 记录其 sha256。
