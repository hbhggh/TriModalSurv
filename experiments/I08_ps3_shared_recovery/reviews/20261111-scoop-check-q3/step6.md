# Step 6 — Structured 4-Axis Comparison & Overlap Roll-Up

- **Step Number**: 6
- **Step Name**: Compare Against the Decomposed Novelty (`level = 5 - axes_matching`)
- **Timestamp**: 2026-11-11 20:48 JST
- **Overall Roll-Up Verdict**: **`Level 3 — Medium Overlap` (`2 / 4` axes matching in the worst case; `0 / 12` full-text papers and `0 / 152` searched papers match Axis 2 [Core mechanism] or Axis 3 [Key insight])**.

---

## 1. Canonical Structured Comparison List (`Proposed Work` vs. `12` Full-Text Verified Prior Works)

- **Proposed work — TriModalSurv (`I08`: `M6-a = A1 + B6-LOO [in_fold_masked] + C1`)**
  - Title: *Post-Hoc Shared-Subspace Recovery and Case-Based Residual Calibration for Incomplete Trimodal Cancer Survival Prediction*
  - Date: `2026-11`
  - Source: `<DEV_WORKTREE>/experiments/I08_ps3_shared_recovery`
  - Problem framing: Two-stage post-pooling missing-modality recovery attached between 256-d pooled tokens and the frozen linear Cox head of a frozen `PS3`-style tri-modal (`WSI + RNA + Pathology Text`) survival backbone, handling all 7 availability regimes (bit-exact `Full` identity bypass $D_0$ + 6 single/double missingness patterns) across 5 TCGA cohorts (`BLCA`, `BRCA`, `LUAD`, `LGG`, `UCEC`; 5-fold 70/10/20 CV C-index).
  - Core mechanism: Stage 2a (`A1 + B1 + C1`) learns Cayley-parameterized Stiefel orthogonal bases $U_m \in \mathbb{R}^{256 \times 32}$ ($U_m^\top U_m = I_{32}$) with training-only $\mathcal{L}_{\text{anchor}} + \lambda_m \mathcal{L}_{\text{modal}} + \lambda_c \mathcal{L}_{\text{cons}}$ and pattern-specific linear maps `B1`, truncating the 224-d orthogonal complement of missing slots to zero while passing visible slots through intact (`37,152` params, $-95.29\%$); Stage 2b (`B6-LOO`) freezes Stage 2a and performs zero-retraining Top-$K$ within-modality cosine retrieval over PRESS Hat-matrix $(1 - H_{jj}^\Omega)^{-1}$ LOO-debiased `B1` prediction residuals gated by a closed-form training-LOO 1-NN median/IQR sigmoid gate $\alpha_i^\Omega \in [0, \alpha_{\max}]$.
  - Key insight: Static zero/mean fill is C-index-degenerate in frozen linear Cox heads (Proposition 1), while full-space 256-d recovery (`788,736` params) overfits modality-private noise (`0.6406 < 0.6519`); truncating the 224-d complement concentrates $62.8\%\text{--}69.5\%$ of Cox weight energy in $12.5\%$ of dimensions, and retrieving Hat-LOO prediction residuals around continuous `B1` with IQR density shrinkage eliminates raw-kNN centroid drift, $(1 - H_{jj}^\Omega)$ self-fit shrinkage, and outlier corruption.
  - Application domain: Tri-modal (`WSI + RNA + Pathology Report`) cancer survival prognosis on TCGA (`BLCA`, `BRCA`, `LUAD`, `LGG`, `UCEC`) under arbitrary deployment-time modality missingness.

- **Prior work 1 — RMoE (`[searched]`, `[verified from full text]`)**
  - Title: *Retrieval-based Mixture-of-Experts for Patient-Specific Cancer Survival Prediction with Incomplete Multimodal Data*
  - Date: `2026-09`
  - Source: *MICCAI 2026*, LNCS 16887 (`https://papers.miccai.org/miccai-2026/0893-Paper2015.html` · `doi:10.1007/978-3-032-38172-9_51`)
  - Problem framing: End-to-end 2-modal (`WSI + Genomics`, no Text) discrete-time NLL survival trained from scratch under 60% training missingness across 3 two-modality settings. (`Partial`)
  - Core mechanism: Epoch-rebuilt memory bank with unconstrained $\ell_2$-normalized cross-modal keys, risk-label-filtered retrieval of **raw full-dimensional neighbor features** ($\sum_{j \in \mathcal{N}_k} \pi_j g_j$), and 3 separate hazard heads ($H^p, H^g, H^{pg}$) routed at the logit level by $\alpha = \sigma(\gamma(s_{(1)} - \delta))$ with fixed $\delta = 0.4, \gamma = 10$. (`Differ`)
  - Key insight: Cross-modal raw-feature retrieval from risk-matched patients plus unimodal/multimodal logit routing mitigates 60% missingness without population prototypes. (`Partial`)
  - Application domain: Bimodal `WSI + Genomics` TCGA survival (`BLCA`, `BRCA`, `UCEC`). (`Match`)
  - **Overlap Score**: `2 axes matching` (conservative rollup of `1 Match + 2 Partial`, `Core mechanism = Differ`) → **`Level 3 — Medium Overlap`** (*two axes differ*).

- **Prior work 2 — MUST (`[searched]`, `[verified from full text]`)**
  - Title: *MUST: Modality-Specific Representation-Aware Transformer for Diffusion-Enhanced Survival Prediction with Missing Modality*
  - Date: `2026-03`
  - Source: *CVPR 2026* / `arXiv:2603.26071v1` (`https://arxiv.org/abs/2603.26071`)
  - Problem framing: End-to-end 2-modal (`WSI + Genomics`, no Text) discrete-time NLL survival trained on complete pairs and tested on 2 single-missing patterns across 5 TCGA cohorts (`BLCA`, `BRCA`, `GBMLGG`, `LUAD`, `UCEC`). (`Partial`)
  - Core mechanism: Softly penalized rank-64 $P_\cap = B_\cap B_\cap^\top$ decomposition **retaining** 256-d private vectors $\hat{u}_m = (I - P_\cap) u_m$ in a 768-d MLP, paired with **two 1,000,000-step 4-layer Transformer Latent Diffusion Models** (`50 DDIM steps × 5 draws = 879 ms/patient`) to generate missing $\tilde{u}_m$. (`Differ`)
  - Key insight: Retains and stochastically hallucinates $(I - P_\cap)$ modality-specific complements via heavy latent diffusion rather than truncating private noise or retrieving Hat-LOO shared residuals. (`Differ`)
  - Application domain: Bimodal `WSI + Multi-omics` TCGA survival (`BLCA`, `BRCA`, `GBMLGG`, `LUAD`, `UCEC`). (`Match`)
  - **Overlap Score**: `2 axes matching` (`1 Match + 1 Partial`) → **`Level 3 — Medium Overlap`** (*two axes differ*).

- **Prior work 3 — PRIME (`[model-recall]`, `[verified from full text]`)**
  - Title: *PRIME: Prototype-Driven Multimodal Pretraining for Cancer Prognosis with Missing Modalities*
  - Date: `2026-04`
  - Source: `arXiv:2604.04999v1` (`https://arxiv.org/abs/2604.04999`)
  - Problem framing: Label-free pan-cancer SSL pretraining on 32 TCGA cohorts ($N = 10,439$, 200 epochs) followed by downstream 5-fold FT/LP adaptation on 5 tri-modal cohorts (`UCEC`, `LUAD`, `LGG`, `BRCA`, `BLCA`) across 7 test regimes. (`Partial [strong]`)
  - Core mechanism: Pre-fusion $128 \times 512$ MHCA tokenizers, $K_c = 128$ learnable sequence prototypes synthesizing missing token sequences via consensus mixtures (`Eqs. 3–6`) + refinement Transformers + Sparse MoE Transformer (`Eqs. 8–9`) + Dirichlet/InfoNCE SSL (`Eqs. 10–16`). (`Differ`)
  - Key insight: Large-scale 32-cancer SSL over shared sequence prototypes enables transferable token imputation (whereas training PRIME from scratch without pan-cancer data drops to `0.623 FT / 0.595 LP`, below `Early 0.627`). (`Differ`)
  - Application domain: Tri-modal (`WSI + RNA + Pathology Text`) TCGA prognosis (`UCEC`, `LUAD`, `LGG`, `BRCA`, `BLCA`). (`Match`)
  - **Overlap Score**: `2 axes matching` (`1 Match + 1 Partial`) → **`Level 3 — Medium Overlap`** (*two axes differ*).

- **Prior work 4 — M3Surv (`[model-recall]`, `[verified from full text]`)**
  - Title: *M3Surv: Fusing Multi-slide and Multi-omics for Memory-augmented robust Survival prediction*
  - Date: `2025-10` / `2026`
  - Source: *Medical Image Analysis*, Vol. 107 (2026), Art. `103846` (`doi:10.1016/j.media.2025.103846`)
  - Problem framing: End-to-end 2-branch (`FF+FFPE WSI` + `3-Omics`, no Text) NLL survival trained on complete pairs and evaluated under inference-time branch missingness (plus frozen `MCAT`/`SurvPath` plug-in in `Sec. 4.3`). (`Partial`)
  - Core mechanism: Dual-slide hypergraphs + mutual cross-attention + momentum $k$-means cluster-centroid memory bank (`Eqs. 8–10`) performing hard $\mu = 1$ raw-feature substitution (`\mu > 1` degrades accuracy). (`Differ`)
  - Key insight: Multi-slide FF/FFPE hypergraph modeling + single-nearest cluster prototype substitution buffers missing pathology or omics branches. (`Differ`)
  - Application domain: Dual-slide `FF+FFPE WSI` + `3-Omics` survival on 5 TCGA cohorts + `APH-LC` (no clinical text). (`Partial [strong]`)
  - **Overlap Score**: `2 axes matching` (conservative) → **`Level 3 — Medium Overlap`** (*two axes differ*).

- **Prior work 5 — DisPro (`[searched]`, `[verified from full text]`)**
  - Title: *Distilled Prompt Learning for Incomplete Multimodal Survival Prediction*
  - Date: `2025-06`
  - Source: *CVPR 2025* (`doi:10.1109/cvpr52734.2025.00481` · `arXiv:2503.01653v2`)
  - Problem framing: End-to-end 2-modal (`WSI + 330 RNA pathways`, no clinical reports) discrete-time NLL survival (`bs=1`) under incomplete/complete training and 3 test regimes. (`Partial`)
  - Core mechanism: CoOp-style MIL unimodal hazard-bin prompts (`UniPro`) + `BioBERT-v1.2` placeholder prompting (`MultiPro`) + `UniPro Distillation` (`Eqs. 3–12`). (`Differ`)
  - Key insight: Explicitly rejects training-sample retrieval and distills LLM unimodal class prompts to inject modality-specific distributions. (`Differ`)
  - Application domain: Bimodal `WSI + RNA` TCGA survival (`BLCA`, `BRCA`, `COADREAD`, `LUAD`, `UCEC`). (`Match`)
  - **Overlap Score**: `2 axes matching` (conservative) → **`Level 3 — Medium Overlap`** (*two axes differ*).

- **Prior work 6 — LD-CVAE (`[searched]`, `[verified from full text]`)**
  - Title: *Robust Multimodal Survival Prediction with Conditional Latent Differentiation Variational AutoEncoder*
  - Date: `2025-06`
  - Source: *CVPR 2025*, pp. 10384–10393 (`doi:10.1109/cvpr52734.2025.00971`)
  - Problem framing: End-to-end unidirectional 2-modal (`WSI -> missing Genomics` only; no Text) NLL survival trained on complete pairs across 5 TCGA cohorts. (`Partial`)
  - Core mechanism: Nyström `VIB-Trans` + 6-branch Markov-chain `LD-CVAE` + Gaussian `PoE` + diagonal Wasserstein alignment + MCAT co-attention (`Eqs. 5–14`). (`Differ`)
  - Key insight: Differentiating shared genomic posteriors into 6 functional groups conditioned on VIB-compressed WSIs improves variational synthesis of missing genomics. (`Differ`)
  - Application domain: Bimodal `WSI + Genomics` TCGA survival (`BLCA`, `BRCA`, `GBMLGG`, `LUAD`, `UCEC`). (`Match`)
  - **Overlap Score**: `2 axes matching` (conservative) → **`Level 3 — Medium Overlap`** (*two axes differ*).

- **Prior work 7 — ProSurv (`[searched]`, `[verified from full text]`)**
  - Title: *Prototype-Guided Cross-Modal Knowledge Enhancement for Adaptive Survival Prediction*
  - Date: `2025-10` (arXiv `2025-03`)
  - Source: *MICCAI 2025*, LNCS pp. 522–532 (`doi:10.1007/978-3-032-04978-0_50` · `arXiv:2503.10726`)
  - Problem framing: End-to-end 2-modal (`WSI + Genomics`, no Text) NLL survival modifying complete features via $(F + F_{\text{trans}})/2$ (`Eq. 5`). (`Partial`)
  - Core mechanism: Survival-interval prototype banks $B_p, B_g \in \mathbb{R}^{4 \times 32 \times d}$ + full-$\mathbb{R}^d$ cross-attention MSE translation + ungated concatenation. (`Differ`)
  - Key insight: Population survival-bin prototypes guide cross-modal feature translation without patient retrieval. (`Differ`)
  - Application domain: Bimodal `WSI + Genomics` TCGA survival (`BRCA`, `BLCA`, `STAD`, `CRAD`). (`Match`)
  - **Overlap Score**: `1 axis matching` → **`Level 4 — Low Overlap`** (*three axes differ*).

- **Prior work 8 — MurreNet (`[searched]`, `[verified from full text]`)**
  - Title: *MurreNet: Modeling Holistic Multimodal Interactions Between Histopathology and Genomic Profiles for Survival Prediction*
  - Date: `2025-07`
  - Source: *MICCAI 2025* (`doi:10.1007/978-3-032-05182-0_39` · `arXiv:2507.04891v1`)
  - Problem framing: Strictly 100% complete paired 2-modal (`WSI + Genomics`) survival fusion (`Eq. 2` fails if a modality is missing). (`Differ`)
  - Core mechanism: Bilinear co-attention (`MRD`) + sample-wise vector Gram-Schmidt retaining `[f_{s,orth}, f_c]` (`DHOF`, `Eq. 5`) + intra-modal MSE autoencoder (`Eq. 9`). (`Differ`)
  - Key insight: Prevents common features from suppressing specific features in complete paired fusion. (`Differ`)
  - Application domain: Complete paired `WSI + Genomics` TCGA survival (`BLCA`, `BRCA`, `COADREAD`, `LUAD`, `UCEC`, `STAD`). (`Match`)
  - **Overlap Score**: `1 axis matching` → **`Level 4 — Low Overlap`** (*three axes differ*).

- **Prior work 9 — PS3 (`[searched]`, `[verified from full text]`)**
  - Title: *PS3: A Multimodal Transformer Integrating Pathology Reports with Histology Images and Biological Pathways for Cancer Survival Prediction*
  - Date: `2025-09`
  - Source: *ICCV 2025* (`arXiv:2509.20022v1`)
  - Problem framing: Complete-only tri-modal (`WSI + 50 Hallmark Pathways + Pathology Reports`) Cox survival (`0` missing-modality support). (`Differ`)
  - Core mechanism: GMM WSI + self-attention Text + SNN Pathway prototypes + 9-block cross-attention + mean-pooled linear Cox layer (`Eq. 14`). (`Differ`)
  - Key insight: Balanced token prototype counts prevent WSI dominance in complete tri-modal fusion. (`Differ`)
  - Application domain: Complete tri-modal `WSI + RNA + Pathology Report` TCGA survival. (`Match`)
  - **Overlap Score**: `1 axis matching` → **`Level 4 — Low Overlap`** (*enabling upstream backbone*).

- **Prior work 10 — LWR (`[searched]`, `[verified from full text]`)**
  - Title: *Latent World Recovery for Multimodal Learning with Missing Modalities*
  - Date: `2026-06`
  - Source: `arXiv:2606.12362v1`
  - Problem framing: Unsupervised incomplete tabular multi-omics representation learning (`5 omics`, no WSI/Text) + external `XGBoost`/`coxph`. (`Differ`)
  - Core mechanism: Modality VAEs + observed-only attention fusion (excludes missing slots) + mini-batch stop-grad KL neighborhood loss (`Eq. 12`). (`Differ`)
  - Key insight: Imputation-free observed-omics aggregation with mini-batch relational KL avoids generative reconstruction error. (`Differ`)
  - Application domain: Tabular multi-omics on 17 TCGA cohorts and cell lines. (`Partial`)
  - **Overlap Score**: `1 axis matching` (conservative) → **`Level 4 — Low Overlap`** (*three axes differ*).

- **Prior work 11 — CalMRL (`[model-recall]`, `[verified from full text]`)**
  - Title: *Calibrated Multimodal Representation Learning with Missing Modalities*
  - Date: `2026-07`
  - Source: *ICML 2026*, PMLR 306 (`arXiv:2511.12034`)
  - Problem framing: Continual encoder alignment on incomplete multimedia (`VAST / MSR-VTT / AudioCaps`), evaluated on complete test splits. (`Differ`)
  - Core mechanism: Batch Probabilistic PCA EM linear imputation (`Eq. 7`) + Gramian SVD leading-singular-value alignment (`Eqs. 8–9`). (`Differ`)
  - Key insight: Linear-Gaussian posterior imputation bounds Davis–Kahan singular-vector anchor shift during alignment (`Theorem 1`). (`Differ`)
  - Application domain: General multimedia video/audio-text retrieval and classification. (`Differ`)
  - **Overlap Score**: `0 axes matching` → **`Level 5 — No Overlap (most novel)`** (*all four axes differ*).

- **Prior work 12 — LAPE (`[web-verified Q4 recovery]`, `[verified from full text]`)**
  - Title: *Laplace-Calibrated Nearest-Neighbor Anchor Interpolation for Post-Hoc Confidence Calibration*
  - Date: `2026-10`
  - Source: *NeurIPS 2026* / `arXiv:2610.30652v1`
  - Problem framing: Post-hoc multi-class classification confidence calibration (`ECE`) on complete inputs. (`Differ`)
  - Core mechanism: Simplex interpolation between global class probabilities and Laplace-smoothed kNN label counts via $V$-fold cross-fitting + per-query grid search. (`Differ`)
  - Key insight: Local Laplace-smoothed label counts shrink overconfident softmax predictions on complete views. (`Differ`)
  - Application domain: Standard vision/tabular classification calibration. (`Differ`)
  - **Overlap Score**: `0 axes matching` → **`Level 5 — No Overlap (most novel)`** (*all four axes differ*).

---

## 2. Summary Overlap Matrix & Worst-Case Roll-Up

| Prior Work | Provenance & Verification | Axis 1 (`Framing`) | Axis 2 (`Mechanism`) | Axis 3 (`Insight`) | Axis 4 (`Domain`) | Axes Matching | Scoop-Check Level (`5 - k`) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **RMoE** (*MICCAI* 2026) | `[searched]` · Full Text | Partial | **Differ** | Partial | Match | `2 / 4` | **Level 3 — Medium Overlap** |
| **MUST** (*CVPR* 2026) | `[searched]` · Full Text | Partial | **Differ** | **Differ** | Match | `2 / 4` | **Level 3 — Medium Overlap** |
| **PRIME** (`arXiv` Apr 2026) | `[model-recall]` · Full Text | Partial | **Differ** | **Differ** | Match | `2 / 4` | **Level 3 — Medium Overlap** |
| **M3Surv** (*MedIA* 2026) | `[model-recall]` · Full Text | Partial | **Differ** | **Differ** | Partial | `2 / 4` | **Level 3 — Medium Overlap** |
| **DisPro** (*CVPR* 2025) | `[searched]` · Full Text | Partial | **Differ** | **Differ** | Match | `2 / 4` | **Level 3 — Medium Overlap** |
| **LD-CVAE** (*CVPR* 2025) | `[searched]` · Full Text | Partial | **Differ** | **Differ** | Match | `2 / 4` | **Level 3 — Medium Overlap** |
| **ProSurv** (*MICCAI* 2025) | `[searched]` · Full Text | Partial | **Differ** | **Differ** | Match | `1 / 4` | **Level 4 — Low Overlap** |
| **MurreNet** (*MICCAI* 2025) | `[searched]` · Full Text | **Differ** | **Differ** | **Differ** | Match | `1 / 4` | **Level 4 — Low Overlap** |
| **PS3** (*ICCV* 2025) | `[searched]` · Full Text | **Differ** | **Differ** | **Differ** | Match | `1 / 4` | **Level 4 — Low Overlap** |
| **LWR** (`arXiv` Jun 2026) | `[searched]` · Full Text | **Differ** | **Differ** | **Differ** | Partial | `1 / 4` | **Level 4 — Low Overlap** |
| **CalMRL** (*ICML* 2026) | `[model-recall]` · Full Text | **Differ** | **Differ** | **Differ** | **Differ** | `0 / 4` | **Level 5 — No Overlap** |
| **LAPE** (*NeurIPS* 2026) | `[Q4 recovery]` · Full Text | **Differ** | **Differ** | **Differ** | **Differ** | `0 / 4` | **Level 5 — No Overlap** |

- **Worst-Case Roll-Up Across All Candidates**: **`Level 3 — Medium Overlap`** (`max axes_matching = 2`; **zero** papers reach `Level 1` or `Level 2`, and **zero** papers collide on `Axis 2` Core Mechanism or `Axis 3` Key Insight).
