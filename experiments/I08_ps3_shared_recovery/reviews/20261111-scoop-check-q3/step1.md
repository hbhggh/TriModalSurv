# Step 1 — Decompose the Novelty

- **Step Number**: 1
- **Step Name**: Decompose the Novelty (SCI Q3 System & Storyline Calibration)
- **Timestamp**: 2026-11-11 17:40:53 JST
- **Target Work**: `TriModalSurv` (`<DEV_WORKTREE>/experiments/I08_ps3_shared_recovery`, main configuration `M6-a`: `A1 + B6-LOO [in_fold_masked] + C1`)
- **Target Venue Calibration**: SCI Q3 (*BMC Bioinformatics* Research Article; calibrated per `<REPO_ROOT>/生存分析-论文模版.md` and `<REPO_ROOT>/AGENTS.md` — basic building blocks `A1` and `C1` are intentionally lightweight canonical operators; novelty and anti-collision evaluation focus on the integrated two-stage pipeline and the `B6-LOO` patient-level residual calibration hook)

---

## Inputs

### 1. Research Problem
In tri-modal cancer survival prediction integrating whole-slide histopathology images (`WSI`), transcriptomic pathway profiles (`RNA`), and structured clinical pathology reports (`Text`), deployment-time patients frequently lack one or two modalities across six non-empty missingness patterns (`rna`, `wsi`, `text`, `rna+wsi`, `rna+text`, `wsi+text`). Over a frozen tri-modal fusion backbone (`I07 PS3-style`) with a linear Cox proportional hazards head:
1. **Static Imputation Degeneracy (Proposition 1)**: Filling missing pooled slots with zero vectors (`M0-a`) or training-set mean vectors (`M0-b`) adds an identical patient-invariant scalar offset $\sum_{u \notin \Omega} c_u^\top w_u$ to every patient sharing missingness pattern $\Omega$, leaving relative risk ordering and C-index strictly unchanged (`0.6519` across 25 folds) and failing to leverage patient-specific observed modalities.
2. **Full-Space High-Dimensional Sensitivity**: Directly regressing all $d = 256$ pooled dimensions per missing pattern requires $788,736$ parameters across 9 directional mappings, making estimation highly sensitive to regularization on small per-cancer cohorts ($N_{\text{tr}} \approx 238\text{--}609$) and causing negative transfer under default hyperparameters (`M7@default = 0.6406`, `M1-a@default = 0.6423` vs. `M0-a = 0.6519`) by attempting to hallucinate modality-specific noise.

### 2. Claimed Novelty (Q3-Calibrated Contribution)
A lightweight, two-stage post-pooling **Patient-Level Dynamic Shared-Subspace Recovery (`A1 + B6-LOO + C1`)** framework attached between the pooled layer and frozen linear Cox head of a tri-modal survival backbone:
- **Stage 2a (`A1 + B1 + C1`)**: Uses Cayley-parameterized Stiefel orthogonal bases $U_m \in \mathbb{R}^{256 \times 32}$ ($U_m^\top U_m = I_{32}$) driven by training-only orthogonal energy anchoring ($\mathcal{L}_{\text{anchor}}$), cross-modal cosine alignment ($\mathcal{L}_{\text{modal}}$), and stop-gradient recovery consistency ($\mathcal{L}_{\text{cons}}$) to isolate a 32-d cross-modally predictable prognostic subspace while truncating the 224-d orthogonal complement to zero for missing modalities and passing visible modalities through intact (`37,152` parameters, $95.29\%$ compression).
- **Stage 2b (`B6-LOO` Plug-in — Primary Narrative Hook)**: Freezes Stage 2a coordinates and linear predictors (`B1`), constructs a leave-one-out leverage-debiased training prediction-residual pool $e_{j,u}^{\text{LOO},\Omega} = (z_{j,u}^F - \hat{z}_{j,u}^{\text{B1},\Omega}) / \max(1 - H_{jj}^\Omega, 10^{-4})$ via closed-form ridge Hat-matrix diagonals, retrieves Top-$K$ similar training patients using per-visible-modality mean cosine similarity, and applies a zero-parameter IQR-scaled density gate $\alpha_i^\Omega \in [0, \alpha_{\max}]$ to dynamically calibrate individual nonlinear deviations while bypassing complete tri-modal inputs (`Full`) bit-exactly.

---

## Four Atomic Axes

- **Problem framing**: Post-hoc / two-stage inference-time missing-modality recovery over a frozen tri-modal (`WSI + RNA + Pathology Text`) cancer survival backbone (`PS3-style`), taking pattern-shifted visible pooled features $p_{i,m}^\Omega \in \mathbb{R}^{256}$ ($m \in \Omega$) and outputting hazard scores across all 7 availability regimes (1 identity-bypass `Full` regime + 6 single/double missingness patterns) evaluated by C-index on 5 TCGA cohorts (`BLCA`, `BRCA`, `LUAD`, `LGG`, `UCEC`; 5-fold 70/10/20 cross-validation, complete training data).
- **Core mechanism**: (1) Per-modality Cayley Stiefel orthogonal subspace projection (`A1`, $256 \to 32$, $U_m^\top U_m = I_{32}$) with 224-d orthogonal complement truncation for missing slots, untouched visible passthrough, and training-only `C1` supervision ($\mathcal{L}_{\text{anchor}} + \lambda_m \mathcal{L}_{\text{modal}} + \lambda_c \mathcal{L}_{\text{cons}}$) plus pattern-specific linear recovery (`B1`); combined with (2) **`B6-LOO` plug-in calibration** — zero-retraining Top-$K$ per-modality mean-cosine retrieval over **PRESS Hat-matrix LOO-debiased `B1` training prediction residuals** modulated by a parameter-free training-LOO nearest-neighbor median/IQR sigmoid gate $\alpha_i^\Omega$, plus an explicit hard identity bypass ($D_0$) for complete tri-modal inputs.
- **Key insight**: Separating *what is cross-modally predictable* from *modality-specific observation noise* via an orthogonal 32-d subspace captures $62.8\%\text{--}69.5\%$ of frozen Cox head weight energy in $12.5\%$ of dimensions without regularization-sensitive overfitting; furthermore, retrieving **LOO-debiased prediction error residuals around a global linear predictor (`B1 + B6-LOO`)** rather than directly averaging neighbor raw features/prototypes (`B3 / RMoE / M3Surv`) eliminates in-sample residual shrinkage bias and local centroid boundary drift, while IQR density gating prevents outlier queries from being corrupted by distant neighbors.
- **Application domain**: Multimodal computational pathology, transcriptomics, and clinical text cancer survival prognosis (TCGA `BLCA`, `BRCA`, `LUAD`, `LGG`, `UCEC` cohorts) under arbitrary deployment-time modality missingness.
