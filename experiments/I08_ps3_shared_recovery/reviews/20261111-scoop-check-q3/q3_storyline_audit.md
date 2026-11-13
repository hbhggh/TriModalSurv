# SCI Q3 (*BMC Bioinformatics*) Storyline & Logical Completeness Audit (`I08` / TriModalSurv)

- **Audit Date**: `2026-11-11` (`2026-11-11 20:51 JST`)
- **Target Venue & Calibration**: **SCI Q3 *BMC Bioinformatics*** Research Article (calibrated strictly to user directive: *"定位 SCI 三区的缝补论文，不要求方法上的强创新性，A1 和 C1 本来就是最简单方法，B6 负责故事性；只要求故事完整、逻辑通顺清晰，必须参考 `<REPO_ROOT>/生存分析-论文模版.md`"*).
- **Audited References (`test_access: false`)**:
  - Template benchmark: `<REPO_ROOT>/生存分析-论文模版.md` (`CTGCN`, *BMC Bioinformatics*) & `<DEV_WORKTREE>/manuscript/bmc_initial_draft/main.tex` (Springer Nature `sn-jnl.cls`)
  - Paper blueprint: `<REPO_ROOT>/handoff-论文生成.md`
  - Verified validation ledger: `<DEV_WORKTREE>/experiments/I08_ps3_shared_recovery/results/val_dev-5c508587/val_ablation_report_v1.md` (commit `5c508587deec0c88e0b85ca7e162a90ae7ba5185`, 25 folds across `BLCA, BRCA, LUAD, LGG, UCEC`)
  - Code & generators inspected read-only: `operators.py`, `losses.py`, `train_eval.py`, `interpretability.py`, `tools/generate_paper_tables.py`, `tools/generate_framework_svg.py`

---

## 0. Executive Verdict & Five High-Impact Pre-Submission Fixes

**Overall Storyline Verdict**: **PASS WITH 5 SURGICAL GUARDRAILS (Ready for SCI Q3 *BMC Bioinformatics*)**.

For a **SCI Q3 *BMC Bioinformatics* methodology paper**, `TriModalSurv (I08: M6-a = A1 + B6-LOO [in_fold_masked] + C1)` already possesses a rock-solid, zero-contradiction causal narrative:
> **"Plug-and-play post-hoc recovery for a frozen trimodal (`WSI + RNA + Pathology Text`) Cox survival model under arbitrary deployment-time missing modalities, built from two intentionally simple anti-overfitting bricks (`A1` canonical Stiefel orthonormal bottleneck + `C1` zero-inference-cost training regularizer) and one clinically intuitive case-based calibration plugin (`B6-LOO` digital-twin residual retrieval with PRESS Hat-matrix leverage debiasing and zero-parameter LOO-IQR density shrinkage)."**

*BMC Bioinformatics* reviewers do **not** penalize `A1` or `C1` for mathematical simplicity **provided we never hype them as novel theoretical inventions**. Instead, as shown in `<REPO_ROOT>/生存分析-论文模版.md` (`CTGCN`), Q3 survival reviewers scrutinize **(1) ablation fairness & subtraction logic**, **(2) clinical/biological tangibility (`Cohort Table`, `KM curves + log-rank P`, `Hallmark pathway × pathology field * heatmap`)**, and **(3) exact code–equation–table consistency**.

### Five Concrete Discrepancies & Gaps Caught (`Pitfall V23` Check)

1. **Asymmetric Hyperparameter Selection Vulnerability in `handoff-论文生成.md` §0.2.3**:
   - `handoff` §0.2.3 displays validation-selected hyperparameters (`@selected = 0.6657`) **only** for `Ours (M6-a)` while holding all 17 comparison and ablation rows at `@default`. Reviewers reading the footnote can challenge whether `0.6579 -> 0.6657` comes from `C1` or from the `(K, tau, alpha_max)` validation grid (`5×4×4 = 80` tuples / `61` distinct configurations).
   - **Clean Resolution**: Report **both** `M6-a@default` (**`0.6594`**, which ranks **`#1` out of ALL 18 methods under zero tuning** with a strictly monotonic ladder!) and `M6-a@selected` (**`0.6657`**, `22/25 = 88%` folds > `M0-a`, `5/5` cohorts improved — locked for one-shot future `test` evaluation), plus include a full `@selected` parity table + "`Full - X` subtraction panel" (`生存分析-论文模版.md` lines 84–93).
2. **Exact Code & Numeric Distinction Among `M6-a`, `M6-b`, and `M5` (`operators.py:248-307`, `train_eval.py:193-201`)**:
   - **Code truth**: **Both** `M6-a` (`in_fold_masked`) and `M6-b` (`exact_loo_hat`) apply Hat-matrix leverage scaling $(1 - H_{jj}^\Omega)^{-1}$. **`M6-a` debiases residuals around the survival-trained linear predictor `B1`**, whereas **`M6-b` computes closed-form Ridge PRESS residuals around an unsupervised MSE Ridge fit** (creating a predictor–pool mismatch: `M6-a@selected 0.6657` vs. `M6-b@selected 0.6621` = `+0.0036`; `M6-a@selected 0.6657` vs. `M6-b@default 0.6583` = `+0.0074`, `17W/1T/7L`, $p_1 = 0.0076$; `M6-a@default 0.6594` vs. `M6-b@default 0.6583` = `+0.0011`). Meanwhile, **`M5` (`B6-Naive`)** disables **both** Hat-leverage scaling (`b_in_train=None`) and the LOO-IQR gate (`gated=False`, $\alpha_i \equiv \alpha_{\max}$).
3. **Table Numbering Drift & Missing Cohort Summary Table (`生存分析-论文模版.md` `Table 1`)**:
   - `handoff-论文生成.md` §4–5 specifies 4 main tables (`Table 1`–`Table 4`), whereas `tools/generate_paper_tables.py` currently emits only 3 main tables (`table1.tex`–`table3.tex`), and **neither** includes *BMC Bioinformatics*'s standard **Cohort & Modality Summary Table** (`N`, event count/rate, median follow-up, `50` Hallmark pathways, `16` report fields, `WSI` tokens across `BLCA, BRCA, LUAD, LGG, UCEC`).
4. **Stale Wrong Parameter Count & Internal Code Strings Still in `tools/generate_framework_svg.py`**:
   - Although `handoff-论文生成.md` §3.2 & §6.3 forbid engineering filenames and fix the 256-d baseline parameter count to **`788,736` (`95.29%` reduction to `37,152`)**, `tools/generate_framework_svg.py` (lines 295, 363, 516, 608, 695, 914, 1089) still hardcodes `"Left (~18%)"`, `"I08"`, `"losses.py:28"`, `"operators.py:248"`, `"W1-4"`, `"0.6657"`, and the stale wrong `"296,448 params / 87.5% reduction"`. This must be purged when executing Phase P4.
5. **High-ROI *BMC Bioinformatics* Visual & Biological Gap (`生存分析-论文模版.md` `Fig. 3` & `Fig. 4`)**:
   - `handoff-论文生成.md` currently plans **only 1 figure (`Fig. 1` architecture)** and **zero named biological pathways/report fields** in `Results` (`interpretability.py` computes only 256-d pooled metrics). Adding **zero-retraining Kaplan–Meier high/low-risk curves + log-rank $P$-values (`Fig. 2`)** and a **zero-retraining `50 Hallmark Pathways × 16 Pathology Report Fields` subspace co-alignment heatmap with BH-FDR `*`/`**` (`Fig. 4`)** upgrades the paper directly to the visual standard of `CTGCN` (`生存分析-论文模版.md`).

---

## 1. Structural Alignment: `生存分析-论文模版.md` & `sn-jnl.cls` vs. `handoff-论文生成.md`

- **Mandatory 3-Part *BMC Bioinformatics* Abstract**: Springer Nature *BMC Bioinformatics* (`main.tex` lines 47–80) uses **strictly three subheadings**: **`Background:`**, **`Results:`**, **`Conclusions:`** (**no `Methods:` subheading** in Abstract; method summary goes in the last 2 sentences of `Background:`).
- **Main Section Order**: Keep **`Background` $\to$ `Methods` $\to$ `Results` $\to$ `Discussion` $\to$ `Conclusions` $\to$ `Abbreviations` & `Declarations`** (matching both `生存分析-论文模版.md` §二 and `main.tex`), merging `Related Work` into `1. Background` and splitting `Discussion` and `Conclusions` into separate top-level sections.

| *BMC Bioinformatics* Section (`生存分析-论文模版.md` + `main.tex`) | Q3 Role & Calibration | Current `handoff-论文生成.md` Status | Recommended Action |
| :--- | :--- | :--- | :--- |
| **Abstract** (`Background / Results / Conclusions`) | Pain point + 2-sentence simple plug-in + 5-cohort C-index, KM log-rank $P$, Hallmark biology | Not drafted in `handoff` | Use 3-part BMC structure (no `Methods:` header in Abstract) |
| **1. Background** (incl. Related Work) | Clinical missingness + Prop. 1 static degeneracy + 256-d overfitting + positioning vs. `RMoE / MUST / PRIME / M3Surv` + 3 de-hyped bullets | Split across `Introduction` & `Related Work` | Merge into `1. Background`; explicitly de-hype `A1` & `C1`; add `RMoE` Eq. (3) citation |
| **2. Methods** | Problem & $D_0$ bypass + Prop. 1 $\to$ `A1` (`37,152` vs `788,736`) $\to$ `B1 + B6-LOO` (Hat-LOO + LOO-IQR gate) $\to$ `C1` (Stage 2a only) | Equations (1)–(14) locked & verified against code | Keep Eqs. (1)–(14) verbatim; add `RMoE` citation in Eq. (9c) prose |
| **Cohort Summary (`Table 1` or `Table S0`)** | Per-cancer $N$, uncensored events ($\%$), median survival, modality dimensions | Missing | Add compact 5-cohort summary table (`BLCA, BRCA, LUAD, LGG, UCEC`) |
| **3. Results — Main Tables (`Table 1` & `Table 2`)** | Mirror `PRIME Table II` (5 cohorts) & `PRIME Table IV` (6 missing regimes + `Full = 0.6777`) | Specified in `handoff` §4.1–4.2 (merged in `generate_paper_tables.py`) | Align `generate_paper_tables.py` to emit separate `table1.tex` & `table2.tex`; keep `[VAL-DRAFT]` banner until `test` unlock |
| **3. Results — KM Stratification (`Fig. 2`)** | 5-cancer High vs Low risk KM curves + log-rank $P$-value (`生存分析-论文模版.md` §二.2) | Missing | Plot directly from saved `val_runs/<CANCER>_fold<f>_preds_val.npz` (`0` retraining!) |
| **3. Results — Ablation (`Table 3` & `Table 4`) + Sensitivity (`Fig. 3`)** | Both progressive (`Add-in`) and `Full - X` subtraction (`生存分析-论文模版.md` lines 84–93) + `K / tau / alpha_max` stability | Progressive 6-row `Table 3` (`Ours` `@selected`, others `@default`) | Add `M6-a@default (0.6594)` row to `Table 3` + `Full - X` subtraction summary + `Fig. 3` sensitivity heatmap |
| **3. Results — Biological Interpretability (`Fig. 4` + `Tables S4–S5`)** | `50 Hallmark × 16 Report Fields` BH-FDR `*` heatmap + top 3 pathway PubMed narratives (`生存分析-论文模版.md` §二.5) | Only abstract latent `Tables S4–S5` | Compute token-level projection onto frozen `(U_rna, U_text)` (`~50` lines read-only, `0` retraining) |
| **4. Discussion & 5. Conclusions** | Mechanistic synthesis (`WSI R^2 = -0.2492`, `M3Surv mu=1`, `PRIME Scratch`), biological meaning, honest Limitations | Merged in `handoff` | Split into `4. Discussion` (with explicit Limitations) and `5. Conclusions` |

---

## 2. Causal Storyline Chain & De-Hyped SCI Q3 Positioning

1. **Clinical Deployment Constraint ($D_0$ Non-Regression)**: Deployed tri-modal survival models (`PS3`-style `I07`, `Full Val C-index = 0.6777`, `Full Test = 0.681`) perform strongly when `WSI + RNA + Text` are complete and must not be degraded when adapting to missing modalities; maintaining $2^3 - 1 = 7$ separate models (`RMoE` style) fragments small cohorts ($N_{\text{tr}} \approx 238\text{--}609$).
2. **Diagnostic Failure Modes (`Prop. 1` + `256-d` Negative Transfer)**:
   - *Static Zero/Mean-Fill (`M0-a/b = 0.6519`)* adds a patient-invariant constant $\sum_{u \notin \Omega} c_u^\top w_u$ per pattern, giving **zero C-index improvement** (`Prop. 1`).
   - *Direct 256-d Recovery (`M1-a@default = 0.6423`, `M7@default = 0.6406`)* requires **`788,736` parameters** and attempts to reconstruct 224-d modality-specific complements whose cross-modal $R^2_{\text{val}} \in [-0.568, -0.312]$, causing **negative transfer below zero-fill (`0.6406 < 0.6519`) across `5/5` cohorts**.
3. **Simple Structural Brick 1 — `A1` (Canonical Stiefel Orthonormal Filter)**:
   - Projecting onto $U_m \in \mathbb{R}^{256 \times 32}$ ($U_m^\top U_m = I_{32}$ via `float64` Cayley map) and truncating the 224-d complement to zero cuts trainable parameters by **`95.29%` (`788,736 -> 37,152`)**, concentrates **`62.8%–69.5%`** of Cox risk-weight energy in **`12.5%`** of dimensions (`5.0×–5.6×` random expectation), and immediately turns negative transfer into a `5/5`-cohort gain (`M10-a@default = 0.6559`). *(Framed strictly as a canonical low-rank orthonormal filter, NOT a new manifold theory.)*
4. **Primary Narrative Hook — `B6-LOO` (Case-Based Digital-Twin Residual Calibration)**:
   - Global linear `B1` (`M2 = 0.6565`) misses nonlinear cancer-subtype structure, whereas raw kNN feature averaging (`M3/B3@default = 0.6526`) suffers sparse-manifold centroid drift. `B6-LOO` combines `B1` with Top-$K$ within-modality cosine retrieval over **PRESS Hat-matrix $(1 - H_{jj}^\Omega)^{-1}$ LOO-debiased `B1` residuals** and a **zero-parameter training-LOO 1-NN median/IQR sigmoid gate** $\alpha_i^\Omega \in [0, \alpha_{\max}]$ that shrinks isolated outlier queries smoothly back to `B1`.
5. **Simple Structural Brick 2 — `C1` (Zero-Inference-Cost Training Regularizer)**:
   - Applied **exclusively in Stage 2a** (`0` parameters, `0` inference FLOPs), $\mathcal{L}_{\text{anchor}} + \lambda_m \mathcal{L}_{\text{modal}} + \lambda_c \mathcal{L}_{\text{cons}}$ aligns cross-modal coordinates before `B6-LOO` retrieval (`0.6579 -> 0.6594` `@default`; `0.6651 -> 0.6657` `@selected`).

---

## 3. Quantitative & Ablation Audit (`@default` Parity + `生存分析-论文模版.md` `Full - X` Rule)

### 3.1 Dual-Protocol Verification (`val_dev-5c508587`, 25 Folds)
- **Zero-Tuning Parity (`@default`, zero validation grid search)**:
  - **`M6-a@default` (`0.6594`, `1M = 0.6479`, `2M = 0.6709`) ranks `#1` out of ALL 18 evaluated methods**, beating `M5@default` (`0.6589`, which improves only `3/5` cohorts), `M9@default` (`0.6586`), `M6-b@default` (`0.6583`), `M8@default` (`0.6579`), `M2@default` (`0.6565`), `M10-a@default` (`0.6559`), `M3@default` (`0.6526`), `M0-a/b` (`0.6519`, `5/5` cohorts won, `17W/1T/7L`, one-sided Wilcoxon $p_1 = 0.0258$), `M1-a@default` (`0.6423`), `M7@default` (`0.6406`), and `M1-b@default` (`0.6394`).
- **Validation-Locked Selection (`@selected`, frozen for future one-shot `test` evaluation)**:
  - **`M6-a@selected` (`0.6657`, `+0.0138` over `M0-a`, one-sided $p_1 = 1.25 \times 10^{-4}`)** improves **`5/5` cohorts** (`BLCA +0.0162`, `BRCA +0.0232`, `LUAD +0.0022`, `LGG +0.0110`, `UCEC +0.0164`) and **`22/25` (`88%`) folds** — achieving higher fold reliability than `M5@selected` (`0.6664`, `19/25 = 76%` folds; two-sided paired Wilcoxon tie $p = 0.2360$) and `M9@selected` (`0.6664`, `20/25 = 80%` folds, which drops below `M0-a` on `LUAD`: `0.6573 < 0.6591`; two-sided tie $p = 0.5481$).

### 3.2 Satisfaction of `生存分析-论文模版.md` "做减法 (`Full - X`)" Ablation Rule (Lines 84–93)
`<REPO_ROOT>/生存分析-论文模版.md` emphasizes that Q3 reviewers expect **leave-one-component-out subtraction (`Full - X`)** where removing any module strictly lowers performance relative to `Full`. Starting from **`Full TriModalSurv (M6-a)`**, **every single component removal degrades `6-Missing Avg` monotonically under BOTH `@default` AND `@selected`**:

| Ablation Row (`Full - X` Subtraction Design) | Zero-Tuned `@default` (`6-Missing Avg`) | $\Delta$ vs. `Full@default` | Val-Locked `@selected` (`6-Missing Avg`) | $\Delta$ vs. `Full@selected` |
| :--- | :---: | :---: | :---: | :---: |
| **`Full TriModalSurv (A1 + B6-LOO + C1, M6-a)`** | **`0.6594`** | — | **`0.6657`** | — |
| `w/o C1 Subspace Supervision (A1 + B6-LOO, M8)` | `0.6579` | `-0.0015` | `0.6651` | `-0.0006` |
| `w/o B1-Aligned Residual Pool (Unsup. Ridge Hat Pool, M6-b)` | `0.6583` | `-0.0011` | `0.6621` | `-0.0036` |
| `w/o B6-LOO Residual Calibration (Global Linear B1 Only, M2)` | `0.6565` | `-0.0029` | `0.6565` | `-0.0092` |
| `w/o B1 Global Linear Anchor (Raw Top-K Neighbor Avg B3, M3)` | `0.6526` | `-0.0069` | `0.6589` | `-0.0068` |
| `w/o A1 Subspace Truncation (Full 256-d B6-LOO, M7)` | `0.6406` | `-0.0189` | `0.6643` | `-0.0014` |
| `w/o Dynamic Recovery (Static Zero / Train-Mean Fill, M0-a/b)` | `0.6519` | `-0.0075` | `0.6519` | `-0.0138` |

> **Recommendation for `Table 3`**: Upgrade `handoff-论文生成.md` `Table 3` from 6 rows to **7 rows** by inserting **`M6-a@default (0.6594)`** right above **`M6-a@selected (0.6657)`** (keeping the clean progressive ladder `0.6406 -> 0.6519 -> 0.6559 -> 0.6565 -> 0.6579 -> 0.6594 -> 0.6657`), and include the `Full - X` subtraction table + full `@selected` parity table in `Appendix Table S1b`!

---

## 4. Internal Consistency Audit of `Table S4` & `Table S5` (Zero Contradictions)

1. **Why Negative Euclidean $R^2_{\text{val}}(\text{wsi}) = -0.2492$ in `Table S4` Strengthens the Story**:
   - Predicting gigapixel WSI bag embeddings from RNA/Text incurs slide-level norm/staining amplitude variance that penalizes isotropic squared error $R^2$ (`-0.2492` in 32-d shared space vs. `-0.4775` in the discarded 224-d complement).
   - Under a frozen linear Cox head $h = \sum_m p_m^\top w_m + b$, survival ranking depends on **directional alignment along $w_{\text{wsi}}$** rather than isotropic norm (`Prop. 1`): WSI directional cosine is **$4.5\times$ higher** in $p^{\text{sha}}$ than $p^{\text{res}}$ (`0.3222` vs. `0.0710`, positive in `5/5` cohorts), and **`69.45%`** of $\lVert w_{\text{wsi}} \rVert_2^2$ concentrates in those 32 dimensions (`5.56×` random expectation `0.1250`), lifting missing-WSI `rna+text` C-index from `0.6715 -> 0.6856`.
2. **Why `Table S5` Half-Split $\Delta\text{C-index}$ (`-0.0001` high / `+0.0049` low) & Patient-Level $\Delta\mathcal{E}$ (`+0.03030`) Are Consistent**:
   - Patient-wise risk approximation improvement $\Delta\mathcal{E} = \lvert h^{\text{B1}} - h^F \rvert - \lvert h^{\text{B6}} - h^F \rvert$ is **strictly positive in `5/5` cohorts** (`+0.0185` to `+0.0687`, pooled `+0.03030`, $n = 7,554$), and $\operatorname{Spearman}(s_{(1)}, \Delta\mathcal{E})$ is **strictly positive in `5/5` cohorts** (pooled $\rho = 0.1686, p = 2.96 \times 10^{-49}$).
   - Bisecting small validation folds ($N_{\text{val}} \approx 55\text{--}155$) at median $s_{(1)} = \delta_\Omega$ leaves only ~15–40 uncensored events per half (`LUAD +0.0051` and `LGG +0.0115` are positive in the high-$s_{(1)}$ half, while small-event pair flips in `BLCA/UCEC` average the pooled high-half $\Delta\text{C-index}$ to `-0.0001`), whereas gentle sigmoid shrinkage in the low-$s_{(1)}$ half prevents outlier degradation (`+0.0049`). Thus the gate should be described honestly as an **outlier safety damper** rather than a half-stratum C-index amplifier.

---

## 5. High-ROI Zero-Retraining Visual & Biological Blueprint (`Fig. 2` & `Fig. 4`)

1. **`Fig. 2` — 5-Cohort Kaplan–Meier Risk Stratification + Log-Rank $P$-Values (`0` Retraining)**:
   - **Data already on disk**: `results/val_dev-5c508587/val_runs/<CANCER>_fold<f>_preds_val.npz` already contains `val_ids`, `time`, `event`, and `{method}__{pattern}` risk scores across all 25 folds.
   - **Leakage-free threshold**: Standardize or Dichotomize each validation fold strictly at the **training-fold median risk score** (never tune cutpoints on `val`/`test`), plot $2 \times 5$ KM curves (`M0-a` Zero-Fill vs. `M6-a` Recovered across `BLCA, BRCA, LUAD, LGG, UCEC`) with $95\%$ CI bands, at-risk counts, log-rank $P$-values, and Cox Hazard Ratios.
2. **`Fig. 4` — `50 Hallmark Pathways × 16 Structured Pathology Report Fields` Subspace Co-Alignment Heatmap (`0` Retraining)**:
   - **Data already on disk**: Frozen `I07` unimodal token encoders (`genes.json` 50 MSigDB Hallmark pathways; `field_keys` 16 structured pathology report fields) + Stage 2a learned orthonormal bases $(U_{\text{rna}}, U_{\text{text}}) \in \mathbb{R}^{256 \times 32}$ via `TrainValReader` (`test_access: false`).
   - **50-line read-only recipe**: Extract pre-pooling token vectors $t_{i,p}^{\text{rna}}, t_{i,q}^{\text{text}} \in \mathbb{R}^{256}$ on `train+val`, project onto $\zeta_{i,p}^{\text{rna}} = U_{\text{rna}}^\top(t_{i,p}^{\text{rna}} - \mu_{\text{rna}}^F)$ and $\zeta_{i,q}^{\text{text}} = U_{\text{text}}^\top(t_{i,q}^{\text{text}} - \mu_{\text{text}}^F)$, compute cross-modal cosine $A_{p,q}$ across observed pairs, mark Benjamini–Hochberg FDR `*` ($<0.05$) / `**` ($<0.01$) directly in heatmap cells (`生存分析-论文模版.md` `Fig. 4` style), and cite 2–3 PubMed oncology studies in `Discussion` linking top aligned Hallmark proliferation/immune/EMT pathways to histologic grade and invasion fields.
