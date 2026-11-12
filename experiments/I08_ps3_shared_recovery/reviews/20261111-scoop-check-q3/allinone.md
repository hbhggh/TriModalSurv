# TriModalSurv (`I08`) — Master `/scoop-check` & SCI Q3 (*BMC Bioinformatics*) Storyline Audit (`allinone.md`)

- **Generated**: `2026-11-11`
- **Target Work**: `<DEV_WORKTREE>/experiments/I08_ps3_shared_recovery` (`M6-a = A1 + B6-LOO [in_fold_masked] + C1`)
- **Overall `/scoop-check` Verdict**: **`Level 3 — Medium Overlap`** (`2 / 4` axes matching at worst across `152` `[searched]` papers and `12` `[verified from full text]` PDFs; `0` collisions on `Axis 2` Core Mechanism or `Axis 3` Key Insight)
- **Overall SCI Q3 Storyline Verdict**: **PASS WITH 5 SURGICAL GUARDRAILS** (calibrated to `<REPO_ROOT>/生存分析-论文模版.md` and `<REPO_ROOT>/handoff-论文生成.md`)

---

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

---

# Step 2 — Literature Search Log (`paper-search` + Targeted Web Search)

- **Audit Date**: `2026-11-11` (`2026-11-11 20:34 JST`)
- **Target System**: `TriModalSurv` (`<DEV_WORKTREE>/experiments/I08_ps3_shared_recovery`, main model `M6-a = A1 + B6-LOO [in_fold_masked] + C1`)
- **Search Tooling**: `<SKILLS_ROOT>/paper_search/scripts/search_papers.py` (searching `arxiv`, `dblp`, `open_alex`, `openreview`, `semantic_scholar`, `crossref`) supplemented by `search_web` for newly accepted `MICCAI 2026`, `CVPR 2026`, and `ICML 2026` full-text OpenAccess PDFs.

---

## 1. Executed `paper-search` Queries & Per-Source Hit Counts

Five structured multi-source queries (`Q1`–`Q5`, comprising 7 distinct search strings across problem, domain, mechanism, and targeted competitor angles) were executed:

| Query ID | Exact Query String(s) | Year Window | `per-source hits` (`arxiv`, `dblp`, `open_alex`, `openreview`, `semantic_scholar`, `crossref`) | Unique Papers |
| :--- | :--- | :---: | :--- | :---: |
| **Q1** (Problem + Domain) | `"missing modality multimodal cancer survival prediction"` | `2023–2026` | `arxiv=10, dblp=0, open_alex=10, openreview=0, semantic_scholar=10, crossref=10` | `33` (7 merged) |
| **Q2** (Tri-Modal WSI+RNA+Text) | `"incomplete multimodal survival pathology genomics text"` | `2023–2026` | `arxiv=10, dblp=0, open_alex=10, openreview=0, semantic_scholar=0, crossref=10` | `26` (4 merged) |
| **Q3** (`A1` Orthogonal Subspace) | `"orthogonal subspace projection missing modality representation recovery"` | `2022–2026` | `arxiv=10, dblp=0, open_alex=10, openreview=0, semantic_scholar=0, crossref=10` | `30` (0 merged) |
| **Q4** (`B6-LOO` kNN Residual Gate) | `"nearest neighbor residual calibration incomplete multimodal learning"` | `2021–2026` | `arxiv=0, dblp=0, open_alex=10, openreview=0, semantic_scholar=0, crossref=10` | `20` (0 merged) |
| **Q5** (Targeted 2024–2026 Competitors) | `"Retrieval-Based Mixture-of-Experts incomplete multimodal survival"` ; `"MurreNet multimodal cancer survival"` ; `"ProSurv prototype missing modality survival"` | `2024–2026` | `arxiv=16, dblp=0, open_alex=24, openreview=0, semantic_scholar=0, crossref=24` | `60` (4 merged) |

- **Deduplicated Union Across `Q1`–`Q5`**: **`152` unique papers** (`[searched]` pool).

---

## 2. Connector Errors & Rate-Limit Disclosure (Required by `paper-search` Protocol)

Per `<SKILLS_ROOT>/paper_search/SKILL.md` ("Never hide a broken source; surface connector `[source] Error ...` lines"), the following upstream API issues occurred during execution and were mitigated via `open_alex`, `crossref`, `arxiv`, and targeted `search_web` fallback:

1. **`[dblp]` (`Q1`–`Q5`)**:
   - `[dblp] Error on query '...': Expecting value: line 1 column 1 (char 0)` (DBLP endpoint returned an empty/non-JSON body across all queries).
2. **`[semantic_scholar]` (`Q2`–`Q5`)**:
   - Succeeded on `Q1` (`10` hits), then hit unauthenticated public API rate limits (`HTTP 429 Client Error` after 4 exponential-backoff retries `3s / 6s / 12s`) on `Q2`–`Q5`.
3. **`[arxiv]` (`Q4` & one sub-query of `Q5`)**:
   - Succeeded on `Q1` (`10` hits), `Q2` (`10` hits), `Q3` (`10` hits), and two sub-queries of `Q5` (`16` hits total); returned `503 Server Error: Service Unavailable` / `HTTP 429` on `Q4` and a `300.0s` read timeout on the `"MurreNet multimodal cancer survival"` sub-query of `Q5` (`MurreNet` was captured by `open_alex` and `crossref` via `doi:10.1007/978-3-032-05182-0_39`).

---

## 3. Supplemental Targeted Web & Local Repository Discovery

To ensure zero blind spots on late-2025 / 2026 conference proceedings and local benchmark PDFs:
1. **Targeted OpenAccess PDF Verification (`search_web` + `fetch_paper.sh`)**:
   - `RMoE` (Lim et al., *MICCAI* 2026): retrieved full text from `https://papers.miccai.org/miccai-2026/paper/2015_paper.pdf` (also indexed in `Q5` via `doi:10.1007/978-3-032-38172-9_51`).
   - `ProSurv` (Liu et al., *MICCAI* 2025): retrieved full text from `https://arxiv.org/pdf/2503.10726` (indexed in `Q5`).
   - `MUST` (Kim & Hwang, *CVPR* 2026): retrieved full text from `https://arxiv.org/pdf/2603.26071` (indexed in `Q3`).
   - `MurreNet` (Liu et al., *MICCAI* 2025): retrieved full text PDF (`doi:10.1007/978-3-032-05182-0_39`, indexed in `Q5`).
   - `DisPro` (Xu et al., *CVPR* 2025): retrieved CVF OpenAccess full text (`doi:10.1109/cvpr52734.2025.00481`, indexed in `Q5`).
   - `CalMRL` (*ICML* 2026): retrieved OpenReview/arXiv full text (`[model-recall]` / targeted web verification for cross-modal calibration comparison).
2. **Local Reference Benchmark PDFs (`<LIT_DIR>`) & Q4 Recovery**:
   - `PRIME` (Yu et al., `arXiv:2604.04999v1`, 2026-04-05, local `Prime.pdf`) — extracted full text (`58.9 KB`, 1,536 lines; note: corrects preliminary working label *Briefings in Bioinformatics* 2025, which belongs to the same UMN group's separate paper Song et al., *Briefings in Bioinformatics* 2026, `doi:10.1093/bib/bbag124`, `[searched]` `#3`).
   - `M3Surv` (Qu et al., *Medical Image Analysis*, Vol. 107, 2026, Art. `103846`, `doi:10.1016/j.media.2025.103846`, local `M3Surv.pdf`) — extracted full text (`75.9 KB`, 1,588 lines; note: journal extension of *MICCAI* 2025 `M2Surv` `arXiv:2506.19324`, `[searched]` `#1`, correcting preliminary working label *NeurIPS* 2025).
   - `LAPE` (Wang, Yu & Ming, `arXiv:2610.30652v1`, 2026-10-22, *NeurIPS* 2026) — fetched full text (`215 KB`) to cover the `arxiv` HTTP 503 gap on `Q4`.

---

## 4. Key High-Signal Papers Surfaced in the `152`-Paper `[searched]` Pool

1. **PS3** — Raza, Azam, Qaiser & Rajpoot (2025, `arXiv:2509.20022`) [`Q1/Q2`] — *Tri-modal WSI + Pathology Report + Biological Pathway survival backbone (complete-data assumption; our frozen backbone)*.
2. **RMoE** — Lim, Kang, Jung, Jo et al. (2026, *MICCAI*, `doi:10.1007/978-3-032-38172-9_51`) [`Q5`] — *Retrieval-Based Mixture-of-Experts for incomplete 2-modal WSI+genomic survival*.
3. **DisPro** — Xu, Zhou, Zhao, Chen et al. (2025, *CVPR*, `doi:10.1109/cvpr52734.2025.00481`) [`Q5`] — *Distilled Prompt Learning for incomplete multimodal survival prediction*.
4. **MUST** — Kim & Hwang (2026, *CVPR* / `arXiv:2603.26071`) [`Q3`] — *Modality-specific representation-aware Transformer + conditional diffusion for missing-modality survival*.
5. **ProSurv** — Liu, Cai, Wang, Fan et al. (2025, *MICCAI* / `arXiv:2503.10726`) [`Q5`] — *Prototype-guided cross-modal knowledge enhancement for unimodal/incomplete survival*.
6. **MurreNet** — Liu, Cai, Li, Xu et al. (2025, *MICCAI*, `doi:10.1007/978-3-032-05182-0_39`) [`Q5`] — *Shared/specific representation decoupling + reconstruction for histopathology-genomic survival*.
7. **LD-CVAE** — Zhou, Tang, Zuo, Wan et al. (2025, *CVPR*, `doi:10.1109/cvpr52734.2025.00971`) [`Q1/Q2`] — *Conditional Latent Differentiation VAE for missing genomic survival*.
8. **HMSP** — Yang, Hu & He (2025, *IEEE MedAI*, `doi:10.1109/medai67139.2025.00013`) [`Q1/Q2`] — *Hierarchical multimodal semantic fusion of pathology-text-genomic representations*.
9. **Memory-Augmented Hypergraph** — Qu, Yang, Di, Gao et al. (2025, *MICCAI*, `arXiv:2506.19324`) [`Q1/Q2`] — *Memory-augmented incomplete multimodal survival via cross-slide and gene-attentive hypergraph learning*.
10. **Cancer-Type-Aware Gated Fusion** — Song, Zhan, Xie, Wang et al. (2026, *Briefings in Bioinformatics*) [`Q1`] — *Adaptive gated fusion for incomplete multimodal cancer survival*.
11. **CIMA** — Bu, Niu, Li, Xu et al. (2026, *AAAI*) [`Q1`] — *Cyclic modality generation and multi-grained alignment for survival*.
12. **EMMS** — Xing, Mo, Wang, Huang et al. (2026, *MICCAI* / `arXiv:2606.20757`) [`Q1/Q5`] — *Evidential fusion network for multimodal survival under missing modalities*.
13. **S2U-Surv** — Yao, Jia, Liu et al. (2026, *Pattern Recognition*, `doi:10.1016/j.patcog.2026.115268`) [`Q1/Q2`] — *Seen-to-unseen sample-specific generation for incomplete multimodal survival*.
14. **FGICL** — Wang, Cui, Tang & Zhang (2026, *ICBIC*, `doi:10.1145/3809986.3810062`) [`Q1/Q2`] — *Transformer feature generation + in-context learning for incomplete survival*.
15. **Contrastive VAE for NSCLC** — Zanitti, Miskovic, Trovò et al. (2026, `arXiv:2602.17402`) [`Q5`] — *Contrastive VAE on WSI + RNA + methylation for NSCLC missing modalities*.
16. **NSCLC Missing-Aware MDL** — Ruffini, Caruso et al. (2026, *npj Digital Medicine*) [`Q1`] — *CT + WSI + clinical missing-aware survival in NSCLC*.
17. **PaRaChute** — Caforio, Poles & Santambrogio (2026, *WACV*, `doi:10.1109/wacv61042.2026.00077`) [`Q1/Q5`] — *Pathology-radiology missing-modality survival fusion*.
18. **Latent World Recovery (LWR)** — Wang, Ren, Butler et al. (2026, `arXiv:2606.12362`) [`Q3`] — *Shared latent space fusion of available modalities without reconstructing private noise*.
19. **HGCN + Online MAE** — Hou, Lin, Yu, Qin et al. (2023, *IEEE TMI*, `doi:10.1109/TMI.2023.3253760`) [`Q1`] — *Online masked autoencoder + hybrid GCN for incomplete survival*.
20. **CAMR** — Wu, Shi, Wang & Li (2023, *Bioinformatics*, `doi:10.1093/bioinformatics/btad025`) [`Q1`] — *Cross-aligned multimodal representation learning for cancer survival*.

---

# Step 3 — Abstract-Level Screening & Triage (`[searched]` + `[model-recall]`)

- **Audit Date**: `2026-11-11`
- **Screening Rule (`scoop-check` Step 3)**: Score every relevant candidate from Step 2 (`152` deduplicated `[searched]` papers) plus non-overlapping `[model-recall]` / local reference papers (`PRIME`, `M3Surv`, `CalMRL`) on a `0–4` abstract-level overlap scale against the 4 decomposed axes (`Problem framing`, `Core mechanism`, `Key insight`, `Application domain`). Promote all papers with preliminary overlap `>= 2` (and key survival competitors) to Step 5 full-text PDF verification.

---

## 1. Abstract-Level Triage Table (23 Relevant Candidates)

| # | Paper (Short Name) | Year / Venue | Provenance | Prelim Axis Hits (`0–4`) | Triage Decision & Rationale |
| :---: | :--- | :--- | :---: | :---: | :--- |
| 1 | **RMoE** (Lim et al.) | 2026 *MICCAI* | `[searched]` (`Q5`) | **2 / 4** (`Axis 1` Partial, `Axis 2` Partial) | **Promote to Full Text** — Closest retrieval + sigmoid density-gated incomplete survival competitor (`2-modal` WSI+RNA, end-to-end). |
| 2 | **MUST** (Kim & Hwang) | 2026 *CVPR* | `[searched]` (`Q3`) | **2 / 4** (`Axis 1` Partial, `Axis 3` Partial) | **Promote to Full Text** — Explicit shared vs. modality-specific representation decomposition + missing-modality survival on TCGA. |
| 3 | **MurreNet** (Liu et al.) | 2025 *MICCAI* | `[searched]` (`Q5`) | **2 / 4** (`Axis 1` Partial, `Axis 2` Partial) | **Promote to Full Text** — Orthogonal shared/specific decoupling + cross-modal reconstruction for TCGA survival. |
| 4 | **DisPro** (Xu et al.) | 2025 *CVPR* | `[searched]` (`Q5`) | **2 / 4** (`Axis 1` Partial, `Axis 3` Partial) | **Promote to Full Text** — Distilled prompt + prototype knowledge transfer for incomplete multimodal TCGA survival. |
| 5 | **PRIME** (Yu et al., `Prime.pdf`) | 2026 *arXiv* (`2604.04999v1`) | `[model-recall]` (Local PDF) | **2 / 4** (`Axis 1` Partial, `Axis 4` Match) | **Promote to Full Text** — Closest 3-modal (`WSI+RNA+Text`) 5-cohort TCGA survival benchmark (32-cancer SSL prototype + Sparse MoE). |
| 6 | **M3Surv** (Qu et al., `M3Surv.pdf`) | 2026 *Med. Image Anal.* (`107:103846`) | `[model-recall]` (Ext. of `[searched]` `M2Surv`) | **2 / 4** (`Axis 1` Partial, `Axis 4` Partial) | **Promote to Full Text** — Dual-slide + 3-omics $k$-means prototype memory bank across TCGA cohorts. |
| 7 | **ProSurv** (Liu et al.) | 2025 *MICCAI* | `[searched]` (`Q5`) | **1–2 / 4** (`Axis 1` Partial) | **Promote to Full Text** — Survival-bin prototype banks for complete-train / unimodal-inference TCGA survival. |
| 8 | **CalMRL** (Liu et al.) | 2026 *ICML* | `[model-recall]` (Web PDF) | **1–2 / 4** (`Axis 2` Triage) | **Promote to Full Text** — Tests whether recent ICML missing-modality calibration uses Hat-matrix LOO residuals or quantile gating. |
| 9 | **PS3** (Raza et al.) | 2025 *ICCV* (`arXiv:2509.20022`) | `[searched]` (`Q1/Q2`) | **1 / 4** (`Axis 4` Match) | **Promote to Full Text** — Exact frozen tri-modal backbone (`WSI + RNA + Pathology Report`); verify complete-modality assumption. |
| 10 | **LD-CVAE** (Zhou et al.) | 2025 *CVPR* | `[searched]` (`Q1/Q2`) | **2 / 4** (`Axis 1` Partial, `Axis 4` Match) | **Promote to Full Text** — 2-modal `WSI->Genomics` conditional VAE generative sampling on 5 TCGA cohorts; verify exact mechanism. |
| 11 | **HMSP** (Yang et al.) | 2025 *IEEE MedAI* | `[searched]` (`Q1/Q2`) | **1 / 4** (`Axis 3` Partial) | **Abstract-Verified (`Level 4`)** — Uses WSI+Text+Genomic modalities end-to-end via hierarchical semantic fusion when molecular data are missing; no frozen backbone, no `A1`, no `B6-LOO`. |
| 12 | **Memory-Augmented Hypergraph** (Qu et al.) | 2025 *MICCAI* | `[searched]` (`Q1/Q2`) | **1 / 4** (`Axis 1` Partial) | **Abstract-Verified (`Level 4`)** — End-to-end FFPE+FF WSI + genomic hypergraph memory bank; no text modality, no post-pooling residual retrieval. |
| 13 | **Cancer-Type-Aware Framework** (Song et al.) | 2026 *Brief. Bioinform.* | `[searched]` (`Q1`) | **1 / 4** (`Axis 1` Partial) | **Abstract-Verified (`Level 4`)** — End-to-end adaptive gated fusion across cancer types; fuses available modalities rather than post-pooling Stiefel residual recovery on a frozen backbone. |
| 14 | **CIMA** (Bu et al.) | 2026 *AAAI* | `[searched]` (`Q1`) | **1 / 4** (`Axis 1` Partial) | **Abstract-Verified (`Level 4`)** — 2-modal histopathology+genomics cyclic modality generation + multi-grained alignment; generative decoder, not `B6-LOO`. |
| 15 | **EMMS** (Xing et al.) | 2026 *MICCAI* | `[searched]` (`Q1/Q5`) | **1 / 4** (`Axis 1` Partial) | **Abstract-Verified (`Level 4`)** — Evidential uncertainty fusion (`Dirichlet / Dempster-Shafer` style) without latent feature recovery or frozen Cox preservation. |
| 16 | **S2U-Surv** (Yao et al.) | 2026 *Pattern Recognit.* | `[searched]` (`Q1/Q2`) | **1 / 4** (`Axis 1` Partial) | **Abstract-Verified (`Level 4`)** — Sample-specific generative synthesis from seen to unseen modalities (`end-to-end`), no Hat-matrix LOO residual retrieval. |
| 17 | **FGICL** (Wang et al.) | 2026 *ICBIC* | `[searched]` (`Q1/Q2`) | **1 / 4** (`Axis 2` Weak) | **Abstract-Verified (`Level 4`)** — End-to-end Transformer feature generator + in-context learning; parametric sequence decoder, not closed-form Hat-matrix LOO residual kNN. |
| 18 | **Contrastive VAE NSCLC** (Zanitti et al.) | 2026 *arXiv* (`2602.17402`) | `[searched]` (`Q5`) | **1 / 4** (`Axis 1` Partial) | **Abstract-Verified (`Level 4`)** — End-to-end contrastive VAE on WSI + RNA + DNA methylation in single cancer (`NSCLC`). |
| 19 | **NSCLC Missing-Aware MDL** (Ruffini et al.) | 2026 *npj Digit. Med.* | `[searched]` (`Q1`) | **1 / 4** (`Axis 1` Partial) | **Abstract-Verified (`Level 4`)** — CT + WSI + clinical missing-aware architecture in NSCLC; no frozen tri-modal backbone or `B6-LOO`. |
| 20 | **PaRaChute** (Caforio et al.) | 2026 *WACV* | `[searched]` (`Q1/Q5`) | **1 / 4** (`Axis 1` Partial) | **Abstract-Verified (`Level 4`)** — Pathology + radiology end-to-end fusion; different modality triad and mechanism. |
| 21 | **Latent World Recovery (LWR)** (Wang et al.) | 2026 *arXiv* (`2606.12362`) | `[searched]` (`Q3`) | **1 / 4** (`Axis 2` Weak) | **Check in Step 5 (`L-3`)** — Aligns modality embeddings into a shared latent world and fuses available modalities; verify non-survival scope and lack of `B6-LOO`. |
| 22 | **HGCN + Online MAE** (Hou et al.) | 2023 *IEEE TMI* | `[searched]` (`Q1`) | **1 / 4** (`Axis 1` Partial) | **Abstract-Verified (`Level 4`)** — Classic patient-graph + online masked autoencoder end-to-end survival baseline. |
| 23 | **SELECTOR / CAMR** (Pan et al. / Wu et al.) | 2024 *CBM* / 2023 *Bioinform.* | `[searched]` (`Q1`) | **1 / 4** (`Axis 1` Partial) | **Abstract-Verified (`Level 4`)** — Convolutional MAE / cross-aligned representation learning on end-to-end 2-modal survival. |

---

## 2. Key Takeaway from Abstract Triage (`Q4` Mechanism Check)

- Across all `152` unique papers returned by `Q1`–`Q5`—specifically including `Q4` (`"nearest neighbor residual calibration incomplete multimodal learning"`) and `Q3` (`"orthogonal subspace projection missing modality representation recovery"`)—**zero papers** combine:
  1. Post-pooling frozen tri-modal (`WSI + RNA + Pathology Report`) survival recovery with strict complete-data invariance ($D_0$),
  2. Stiefel orthogonal projection with intentional zero-truncation of the unrecoverable orthogonal complement (`A1`), and
  3. Global linear cross-modal regression (`B1`) corrected by **Hat-matrix leverage-debiased LOO prediction-error residual Top-$K$ retrieval** and **closed-form zero-parameter LOO-IQR quantile gating** (`B6-LOO`).
- **9 papers** (`RMoE`, `MUST`, `MurreNet`, `DisPro`, `PRIME`, `M3Surv`, `ProSurv`, `CalMRL`, `PS3`) are promoted to full-text PDF verification in Steps 4–5 to guarantee exact equation-level boundary statements.

---

# Step 4 — Model-Recall Supplementation & Search Coverage Audit

- **Step Number**: 4
- **Step Name**: Model-Recall Supplementation & Search Coverage Audit
- **Timestamp**: 2026-11-11 20:47 JST
- **Protocol (`scoop-check` Step 4)**: List ONLY papers recalled from domain knowledge or local reference files that were **not** already returned in the `152`-paper `paper-search` union (`Q1`–`Q5`), tag each `[model-recall]`, verify existence via extracted full-text PDF / publisher record, and audit search recall coverage.

---

## 1. Search Recall Verification (`[searched]` vs. `[model-recall]`)

Out of our primary survival and mechanism competitor checklist, **`9` of the `13` deep-dive/structured papers WERE directly captured by `paper-search` (`[searched]`)**:
- `PS3` (Raza et al., *ICCV* 2025, `arXiv:2509.20022v1`) — found in `Q1/Q2` (`#038`).
- `RMoE` (Lim et al., *MICCAI* 2026, `doi:10.1007/978-3-032-38172-9_51`) — found in `Q5`.
- `MUST` (Kim & Hwang, *CVPR* 2026, `arXiv:2603.26071v1`) — found in `Q3` (`#060`).
- `MurreNet` (Liu et al., *MICCAI* 2025, `doi:10.1007/978-3-032-05182-0_39`) — found in `Q5`.
- `DisPro` (Xu et al., *CVPR* 2025, `doi:10.1109/cvpr52734.2025.00481`) — found in `Q5` (`#036`).
- `ProSurv` (Liu et al., *MICCAI* 2025, `arXiv:2503.10726`) — found in `Q5`.
- `LD-CVAE` (Zhou et al., *CVPR* 2025, `doi:10.1109/cvpr52734.2025.00971`) — found in `Q1/Q2` (`#035`).
- `LWR` (Wang et al., `arXiv:2606.12362v1`, Jun 2026) — found in `Q3` (`#059`).
- `M2Surv` (Qu et al., *MICCAI* 2025, `arXiv:2506.19324`, precursor to `M3Surv`) — found in `Q1/Q2` (`#001`).
- Plus `Song et al.` (*Briefings in Bioinformatics* 2026, `doi:10.1093/bib/bbag124`, `#003`), `Ruffini et al.` (*npj Digital Medicine* 2026, `#004`), `HMSP` (*IEEE MedAI* 2025, `#037`), `S2U-Surv` (*Pattern Recognition* 2026, `#045`), `CIMA` (*AAAI* 2026), `EMMS` (*MICCAI* 2026), `MoME` (*MICCAI* 2024), `HGCN+MAE` (*IEEE TMI* 2023), and `CAMR` (*Bioinformatics* 2023) — all `[searched]`.

Only **4 full-text deep-dive papers** (`PRIME`, `M3Surv`, `CalMRL`, `LAPE`) fell outside the `Q1`–`Q5` top-10 per-source cutoff due to `semantic_scholar` HTTP 429 on `Q2`–`Q5` and `arxiv` HTTP 503 on `Q4`, and are explicitly supplemented below.

---

## 2. Non-Overlapping `[model-recall]` & `Q4`-Recovery Entries (100% Full-Text Verified)

1. **PRIME** — Kai Yu, Shuang Zhou, Yiran Song, Zaifu Zhan, Jie Peng, Kaixiong Zhou, Tianlong Chen, Feng Xie, Meng Wang, Huazhu Fu, Mingquan Lin & Rui Zhang (`arXiv:2604.04999v1`, 2026-04-05; `[model-recall]`, `[verified from full text]` via `<LIT_DIR>/Prime/Prime.pdf`)
   - **Verification**: Full text (`58.9 KB`, 10 pages / 1,536 lines) extracted and verified in Step 5 (`https://arxiv.org/abs/2604.04999`). *(Bibliographic correction: `Prime.pdf` is `arXiv:2604.04999v1` [Apr 2026], NOT *Briefings in Bioinformatics* 2025; the same UMN group's *Briefings in Bioinformatics* 2026 article is Song et al., `doi:10.1093/bib/bbag124`, captured at `[searched]` `#003`.)*
   - **Why recalled**: Closest 3-modal (`WSI + RNA + Pathology Text`) 5-cohort TCGA incomplete survival benchmark referenced in `<REPO_ROOT>/handoff-论文生成.md`; missed by `Q1/Q2` top-10 cutoff after `semantic_scholar` hit HTTP 429 on `Q2`.

2. **M3Surv** — Mingcheng Qu, Guang Yang, Donglin Di, Yue Gao, Yang Song & Lei Fan (*Medical Image Analysis*, Vol. 107, 2026, Art. `103846`, `doi:10.1016/j.media.2025.103846`; `[model-recall]`, `[verified from full text]` via `<LIT_DIR>/M3Surv/M3Surv.pdf`)
   - **Verification**: Full text (`75.9 KB`, 11 pages / 1,588 lines) extracted and verified in Step 5. *(Bibliographic correction: `M3Surv.pdf` is *Medical Image Analysis* Vol. 107 [2026, online 16 Oct 2025], journal extension of *MICCAI* 2025 `M2Surv` `arXiv:2506.19324` [`[searched]` `#001`], NOT *NeurIPS* 2025.)*
   - **Why recalled**: Extended journal version of `[searched]` `M2Surv` evaluating a momentum $k$-means prototype memory bank across TCGA survival cohorts (including a frozen `MCAT`/`SurvPath` plug-in experiment in `Sec. 4.3`).

3. **CalMRL** — Xiaohao Liu, Xiaobo Xia, Jiaheng Wei, Shuo Yang, Xiu Su, See-Kiong Ng & Tat-Seng Chua (*ICML* 2026, PMLR 306, `arXiv:2511.12034`; `[model-recall]`, `[verified from full text]`)
   - **Verification**: Full text (`128 KB`, 1,433 lines including Appendices A–F) downloaded and extracted in Step 5 (`https://github.com/Xiaohao-Liu/CalMRL`).
   - **Why recalled**: Tests whether any 2026 top-ML missing-modality "calibration" paper uses Hat-matrix LOO linear prediction-error residuals (`(1 - H_{jj})^{-1}`) or IQR quantile gating (`B6-LOO`).

4. **LAPE** — Xihao Wang, Chengyao Yu & Ruixing Ming (`arXiv:2610.30652v1`, 2026-10-22, *NeurIPS* 2026; `[web-verified Q4 recovery]`, `[verified from full text]`)
   - **Verification**: Full text (`215 KB`) fetched via `search_web` + `fetch_paper.sh` in Step 5 to close the `arxiv` HTTP 503 gap on `Q4` (`"nearest neighbor residual calibration..."`).
   - **Why recalled / recovered**: Tests whether post-hoc kNN calibration with out-of-fold fitting in general ML overlaps with `B6-LOO` (verified `0/4` overlap: complete-view classification probability simplex smoothing via $V$-fold cross-fitting + per-query grid search; zero missing modalities, zero Hat-matrix PRESS residuals, zero survival).

5. **Classical Building-Block Provenance References (`[model-recall]`, textbook/foundational — intentionally NOT claimed as novel in `I08`)**:
   - **DSN (Domain Separation Networks)** — Bousmalis et al. (*NeurIPS* 2016) & **MISA** — Hazarika et al. (*ACM MM* 2020): Canonical shared/private orthogonal subspace decomposition in multimodal learning. Cited transparently so `A1` (`Cayley` Stiefel orthogonal projection) is positioned as a canonical mathematical filter, while our task-specific finding is **intentional zero-truncation of the 224-d orthogonal complement** ($\hat{p}_{i,u}^\Omega = \mu_u^F + U_u \hat{z}_{i,u}^\Omega$) rather than private-branch reconstruction under survival supervision.
   - **Allen PRESS / Cook & Weisberg Hat-Matrix Leverage Identity** — Allen (*Technometrics* 1974); Cook & Weisberg (1982): Classical closed-form leave-one-out linear regression residual identity $e_j^{(-j)} = (y_j - \hat{y}_j)/(1 - H_{jj})$. `B6-LOO` adapts this classical statistical leverage-debiasing identity into a **directional cross-modal latent residual retrieval bank with closed-form LOO-IQR density shrinkage** for incomplete tri-modal cancer survival.

---

# Step 5 — Full-Paper Deep Dive & Mechanism Verification (`12` PDFs + `4` Abstract/Metadata Records)

- **Step Number**: 5
- **Step Name**: Full-Paper Deep Dive (Fetch, Read & Extract 8 Verified Fields + Closest-Passage Quotes)
- **Timestamp**: 2026-11-11 20:48 JST
- **Coverage Summary**:
  - **12 Full-Text PDFs Downloaded / Extracted & Read End-to-End** (`[verified from full text]`): `RMoE` (*MICCAI* 2026), `MUST` (*CVPR* 2026), `PRIME` (`arXiv:2604.04999v1`, Apr 2026), `M3Surv` (*Medical Image Analysis* 2026), `DisPro` (*CVPR* 2025), `LD-CVAE` (*CVPR* 2025), `ProSurv` (*MICCAI* 2025), `MurreNet` (*MICCAI* 2025), `PS3` (*ICCV* 2025), `LWR` (`arXiv:2606.12362v1`, Jun 2026), `CalMRL` (*ICML* 2026), and `LAPE` (*NeurIPS* 2026 / `arXiv:2610.30652v1`).
  - **4 Additional Recent Survival Papers Verified at Abstract / Publisher-Index Level**: `Song et al.` (*Briefings in Bioinformatics* 2026), `HMSP` (*IEEE MedAI* 2025), `Ruffini et al.` (*npj Digital Medicine* 2026), and `S2U-Surv` (*Pattern Recognition* 2026).

---

## Global Operator Collision Summary Across All `152` `[searched]` Papers + `12` Full-Text PDFs

1. **Post-pooling Cayley/Stiefel orthogonal projection ($U_m^\top U_m = I_{32}$) + $(d-r)$-d orthogonal complement zero-truncation over a frozen tri-modal (`WSI + RNA + Pathology Text`) Cox survival backbone with $D_0$ complete-data invariance**: **`0 / 152` papers, `0 / 12` PDFs (100% un-scooped)**.
2. **PRESS / Hat-matrix $(1 - H_{jj}^\Omega)^{-1}$ leave-one-out leverage-debiased linear prediction-error residual Top-$K$ retrieval (`B6-LOO`)**: **`0 / 152` papers, `0 / 12` PDFs (100% un-scooped)**.
3. **Closed-form zero-parameter training-LOO 1-NN median & IQR quantile density gate ($\delta_\Omega = Q_{0.50}^{\text{LOO}}, \gamma_\Omega = \operatorname{clip}(1.349/\operatorname{IQR}_\Omega, 5, 30)$) shrinking local residuals back to a global linear cross-modal predictor (`B1`) inside a single frozen Cox head**: **`0 / 152` papers, `0 / 12` PDFs (100% un-scooped)**. *(Crucial formula guardrail: `RMoE` Eq. 3 uses bare $\alpha = \sigma(\gamma(s - \delta))$ with fixed heuristic $\delta=0.4, \gamma=10$ to route $2^M-1$ expert logits — explicitly cited and differentiated below.)*

---

## Part A — 12 Full-Text Verified Papers (`[verified from full text]`)

### 1. **RMoE** (Lim et al., *MICCAI* 2026) — `[searched]` `[verified from full text]`
- **Title**: *Retrieval-based Mixture-of-Experts for Patient-Specific Cancer Survival Prediction with Incomplete Multimodal Data*
- **Authors**: Minjoo Lim, Bogyeong Kang, Hyun Jung Lee, Eunjung Jo, Keun-Soo Heo, Mingxia Liu, Tae-Eui Kam
- **Venue (verified)**: *MICCAI 2026*, Springer LNCS vol. 16887 (`https://papers.miccai.org/miccai-2026/0893-Paper2015.html` · `doi:10.1007/978-3-032-38172-9_51`)
- **Problem framing (verified)**: End-to-end **2-modal (`WSI + Genomics`, no clinical text)** discrete-time NLL survival model trained from scratch (`batch_size=1`, 50 epochs) under **60% random training-time missingness** (`30%` WSI-missing, `30%` genomics-missing, `40%` complete) and evaluated on 3 two-modality patterns (`WSI-only`, `Genomics-only`, `WSI+Genomics`). Memory bank $\mathcal{M}$ is rebuilt every epoch.
- **Core mechanism (verified)**: Stores $\mathcal{M}_j = (p_j, g_j, z_j^p, z_j^g, \text{risk}_j, \text{idx}_j)$ with unconstrained $\ell_2$-normalized cross-modal projection keys $z_j^p, z_j^g$ trained via risk-group supervised contrastive loss $\mathcal{L}_c$ (`Eq. 2`). Restricts training-time retrieval to candidates sharing ground-truth risk bin $\text{risk}_j = \text{risk}_n$ and aggregates **raw full-dimensional neighbor features** $g_n^{\text{retr}} = \sum_{j \in \mathcal{N}_k} \pi_j g_j$ (`Eq. 1`, $s_j = (z_n^p)^\top z_j^g$, $k=5, \tau=0.1$). Trains **3 separate survival expert heads** ($H^p, H^g, H^{pg}$, scaling as $2^M - 1$) and interpolates unimodal vs. multimodal logits via $\alpha = \sigma(\gamma(s - \delta))$ (`Eq. 3`, $s = \max_{j \in \mathcal{N}_k} s_j$) with **fixed constants $\delta = 0.4, \gamma = 10$**.
- **Key insight (verified)**: Cross-modal retrieval of raw features from prognostically similar patients captures patient-specific dependencies missed by static population prototypes, while 1-NN similarity routing down-weights low-confidence retrievals toward a unimodal expert.
- **Application domain (verified)**: Bimodal `WSI + Genomics` survival prediction on 3 TCGA cohorts (`BLCA` $N=378$, `BRCA` $N=1007$, `UCEC` $N=478$; 5-fold CV C-index).
- **Assumptions & scope**: Strictly 2-modal (3 modalities would require $2^3 - 1 = 7$ heads and $6$ cross-modal key pairs); requires ground-truth survival interval labels during training retrieval; zero Stiefel projection, zero `B1` linear anchor, zero Hat-matrix LOO residuals, and heuristic $(\delta=0.4, \gamma=10)$ logit routing rather than closed-form LOO-IQR residual shrinkage.
- **Closest-passage evidence**:
  - `Sec. 2, Eq. 1, p. 4`: *"We then retrieve the missing genomic representation $g_n^{\text{retr}}$ from $\mathcal{M}$ as a weighted sum of top-$k$ neighbors: $g_n^{\text{retr}} = \sum_{j \in \mathcal{N}_k} \pi_j g_j, \pi_j = \text{softmax}(s_j / \tau), s_j = (z_n^p)^\top z_j^g$."*
  - `Sec. 2, Eq. 3, p. 5 & Sec. 3, p. 6`: *"The reliability-aware router $\mathcal{R}$ converts $s$ into a mixing weight $\alpha \in (0, 1)$: $\alpha = \sigma(\gamma(s - \delta))$ ... If one modality is missing, $\mathcal{R}$ interpolates between the unimodal expert and the multimodal expert ... we use a confidence threshold $\delta$ of 0.4 and a slope $\gamma$ of 10."*
- **Refined overlap**: `Problem framing: Partial` · `Core mechanism: Differ` (narrow sub-formula overlap on $\sigma(\gamma(s_{(1)} - \delta))$ explicitly guarded) · `Key insight: Partial` · `Application domain: Match` → **`2 / 4` axes matching (`Level 3 — Medium Overlap`)**.

---

### 2. **MUST** (Kim & Hwang, *CVPR* 2026) — `[searched]` `[verified from full text]`
- **Title**: *MUST: Modality-Specific Representation-Aware Transformer for Diffusion-Enhanced Survival Prediction with Missing Modality*
- **Authors**: Kyungwon Kim, Dosik Hwang
- **Venue (verified)**: *CVPR 2026* / `arXiv:2603.26071v1` (`2026-03-27`, `https://arxiv.org/abs/2603.26071`)
- **Problem framing (verified)**: End-to-end **2-modal (`WSI + Genomics`, no Text)** discrete-time NLL ($K=4$ intervals) survival model trained on complete paired data and evaluated on complete + 2 single-modality missing patterns (`missing G`, `missing P`) across 5 TCGA cohorts (`BLCA`, `BRCA`, `GBMLGG`, `LUAD`, `UCEC`; 5-fold CV C-index).
- **Core mechanism (verified)**: Encodes `UNI2-h` WSI patches (`TransMIL`) and 6 hallmark multi-omic groups (`RNA+CNV+SNV` MLPs), applies bidirectional cross-attention (`Eq. 7`), and defines unconstrained rank-64 $P_\cap = B_\cap B_\cap^\top$ ($B_\cap \in \mathbb{R}^{256 \times 64}$, `Eq. 8`) with soft penalties ($\mathcal{L}_{\text{decomp}}, \mathcal{L}_{\text{shared}}, \mathcal{L}_{\text{orth}}$, `Eqs. 13–15`), **retaining** the 256-d private vectors $\hat{u}_P = (I - P_\cap) u_P, \hat{u}_G = (I - P_\cap) u_G$ inside a concatenated 768-d MLP hazard head (`Eq. 11`). Freezes encoders and trains **two separate 4-layer Transformer Conditional Latent Diffusion Models (`LDM`) for 1,000,000 steps each** (`Eq. 19`); at missing-modality inference, computes $\tilde{c} = g_P - (I - P_\cap) u_P$ (`Eq. 20`) and runs **50-step DDIM $\times$ 5 stochastic draws (`879 ms/patient`, `1.8 GB VRAM`)** to synthesize $\tilde{u}_G$ (`Eqs. 21–22`).
- **Key insight (verified)**: Assumes linearly unreachable $(I - P_\cap)$ modality-specific components must be retained in the survival head and stochastically synthesized via conditional latent diffusion—diametrically opposite to `I08`'s proof that 224-d private complements have negative out-of-sample $R^2$ and should be truncated to zero while calibrating 32-d shared coordinates via `B6-LOO`.
- **Application domain (verified)**: Bimodal `WSI + Multi-omics` TCGA survival (`BLCA`, `BRCA`, `GBMLGG`, `LUAD`, `UCEC`).
- **Assumptions & scope**: Strictly 2-modal; heavy 2 $\times$ 1M-step diffusion training + 879 ms/patient inference; authors note (`Sec. 4.2, p. 7`) LDM smoothing attenuates structured genomic variations and alters risk rankings without $D_0$ invariance (`missing P` C-index exceeds `complete` on 3/5 cohorts).
- **Closest-passage evidence**:
  - `Sec. 3.3, Eq. 11, p. 4`: *"we concatenate the modality-specific components from each modality with the shared component and feed them to a prediction head ... $h_{\text{score}} = \phi([\hat{u}_P ; \hat{c}; \hat{u}_G])$."*
  - `Sec. 4.1, p. 6 & Sec. 4.2, p. 7`: *"MUST requires $\le 70\text{ms}$ per patient with complete data and $879\text{ms}$ (50 DDIM steps $\times$ 5 samples) with $1.8\text{GB}$ memory when a modality is missing ... The smoothing inherent in LDM generation ... may attenuate functionally important variations in well-structured genomic features."*
- **Refined overlap**: `Problem framing: Partial` · `Core mechanism: Differ` · `Key insight: Differ` · `Application domain: Match` → **`2 / 4` conservative (`Level 3 — Medium Overlap`)**.

---

### 3. **PRIME** (Yu et al., `arXiv:2604.04999v1`, Apr 2026) — `[model-recall]` `[verified from full text]`
- **Title**: *PRIME: Prototype-Driven Multimodal Pretraining for Cancer Prognosis with Missing Modalities*
- **Authors**: Kai Yu, Shuang Zhou, Yiran Song, Zaifu Zhan, Jie Peng, Kaixiong Zhou, Tianlong Chen, Feng Xie, Meng Wang, Huazhu Fu, Mingquan Lin, Rui Zhang
- **Venue (verified)**: `arXiv:2604.04999v1 [cs.LG]` (`2026-04-05`, `https://arxiv.org/abs/2604.04999` — *not* *Briefings in Bioinformatics* 2025)
- **Problem framing (verified)**: **Upstream pan-cancer label-free self-supervised pretraining (`SSL`)** across **32 TCGA cancers ($N = 10,439$: $7,675$ complete + $2,764$ incomplete, 200 epochs)** over frozen unimodal extractors (`Marugoto ViT`, `BulkRNABert`, `BioClinicalBERT`), followed by downstream 5-fold (70/10/20) fine-tuning (`FT`) or linear probing (`LP`) on 5 complete tri-modal TCGA cohorts (`UCEC`, `LUAD`, `LGG`, `BRCA`, `BLCA`) evaluated under 7 test-time regimes (`Full, LI, LR, LT, OI, OR, OT`) on discrete-time NLL OS C-index, `3yOS` AUROC, and `3yRec` AUROC.
- **Core mechanism (verified)**: Projects each observed modality via MHCA (`Eq. 2`) to $T_q = 128$ tokens of dim $D = 512$, maintains $K_c = 128$ learnable sequence prototypes $C_k \in \mathbb{R}^{128 \times 512}$ (`Eqs. 3–5`), imputes missing token sequences pre-fusion as convex mixtures $\sum_{k=1}^{128} \bar{q}_{i,k} C_k$ followed by modality-specific refinement Transformers (`Eqs. 6–7`), and fuses `[I; R; T]` (`384 × 512`) via alternating Vanilla and Sparse MoE Transformer blocks (`Eqs. 8–9`) pretrained with paired InfoNCE + Dirichlet-dropout view InfoNCE (`Eqs. 10–16`).
- **Key insight (verified)**: Pan-cancer SSL across $10,439$ partially observed patients with shared sequence prototypes and MoE routing yields transferable representations. Crucially, **without 32-cancer SSL pretraining**, `PRIME Scratch (FT = 0.623, LP = 0.595)` underperforms simple early concatenation (`0.627`) (`Table II, p. 6`), demonstrating that high-dimensional ($128 \times 512$) prototype synthesis overfits single-cancer sample sizes!
- **Application domain (verified)**: Identical tri-modal (`WSI + RNA + Pathology Text`) oncology prognosis domain and 5 downstream TCGA cohorts (`UCEC`, `LUAD`, `LGG`, `BRCA`, `BLCA`).
- **Assumptions & scope**: Requires $N = 10,439$ 32-cancer pretraining corpus; replaces the fusion backbone rather than wrapping a frozen Cox model post-pooling; downstream missingness training (`LP+Missing`) degrades `Full` performance (`0.689 -> 0.679` on Task-2, `0.629 -> 0.622` on Task-3; `Sec. IV-D3, p. 7`); zero Stiefel truncation, zero Hat-matrix LOO residuals, zero IQR gate.
- **Closest-passage evidence**:
  - `Sec. III-C3, Eq. 6, p. 4`: *"For any missing modality $m \notin S_i$, we dynamically impute its token sequence using a mixture of the shared prototypes driven by the consensus distribution: $U_i^{(m)} = \sum_{k=1}^{K_c} \bar{q}_{i,k} C_k$."*
  - `Sec. IV-D3, p. 7`: *"Introducing modality dropout at downstream training (LP+Missing) further improves robustness under missingness, sometimes at a small cost on the full-modality score."*
- **Refined overlap**: `Problem framing: Partial (strong)` · `Core mechanism: Differ` · `Key insight: Differ` · `Application domain: Match` → **`2 / 4` axes matching (`Level 3 — Medium Overlap`)**.

---

### 4. **M3Surv** (Qu et al., *Medical Image Analysis* 2026) — `[model-recall]` `[verified from full text]`
- **Title**: *M3Surv: Fusing Multi-slide and Multi-omics for Memory-augmented robust Survival prediction*
- **Authors**: Mingcheng Qu, Guang Yang, Donglin Di, Yue Gao, Yang Song, Lei Fan
- **Venue (verified)**: *Medical Image Analysis*, Vol. 107 (2026), Art. `103846` (`doi:10.1016/j.media.2025.103846`, online 16 Oct 2025; journal extension of *MICCAI* 2025 `M2Surv` `arXiv:2506.19324`, `[searched]` `#001`)
- **Problem framing (verified)**: **2-branch (`FF+FFPE Dual-Slide Pathology` + `Genomics/Transcriptomics/Proteomics 3-Omics`, NO clinical text)** discrete-time NLL survival model trained on complete paired data and tested under inference-time pathology or omics missingness (`30%–100%`), plus an inference plug-in test on frozen `MCAT`/`SurvPath` (`Sec. 4.3, Fig. 7d`).
- **Core mechanism (verified)**: Intra/inter-slide hypergraphs (`Eqs. 2–6`) + mutual cross-attention (`Eq. 7`) + **training-set $k$-means cluster-centroid memory bank** updated by epoch EMA (`Eqs. 8–9`, $\theta = 0.75$) that substitutes **raw missing-branch features** via top-$\mu$ similarity lookup (`Eq. 10`). Crucially, `Sec. 4.3 (p. 8)` reports that **averaging $\mu > 1$ prototypes degrades C-index due to inter-cluster noise, forcing $\mu = 1$** (hard 1-NN cluster centroid replacement).
- **Key insight (verified)**: Dual-slide hypergraph fusion + momentum $k$-means raw-feature cluster prototypes buffer complete-branch absence at inference. Its $\mu > 1$ degradation empirically motivates `B6-LOO` retrieving **LOO-debiased linear residuals** rather than raw cluster centroids!
- **Application domain (verified)**: Dual-slide `FF+FFPE WSI` + `3-Omics` survival on 5 TCGA cohorts (`BLCA`, `BRCA`, `CRAD`, `HNSC`, `STAD`) + in-house `APH-LC` (`Sec. 5, p. 10` explicitly lists clinical notes as future work).
- **Assumptions & scope**: Requires paired FF+FFPE slides + proteomics; no text modality; hard $\mu=1$ raw centroid substitution with zero Stiefel projection, zero `B1` linear anchor, zero Hat-matrix LOO debiasing, and zero IQR outlier gate.
- **Closest-passage evidence**:
  - `Sec. 4.3, p. 8`: *"The best average performance was consistently achieved at $\mu = 1$, and using more prototypes ($\mu > 1$) appeared to introduce noise from less-related patient clusters, slightly degrading performance."*
  - `Sec. 5, p. 10`: *"First, integrating additional modalities such as radiology images or clinical notes could further enhance predictive performance."*
- **Refined overlap**: `Problem framing: Partial` · `Core mechanism: Differ` · `Key insight: Differ` · `Application domain: Partial (strong)` → **`2 / 4` conservative (`Level 3 — Medium Overlap`)**.

---

### 5. **DisPro** (Xu et al., *CVPR* 2025) — `[searched]` `[verified from full text]`
- **Title**: *Distilled Prompt Learning for Incomplete Multimodal Survival Prediction*
- **Authors**: Yingxue Xu, Fengtao Zhou, Chenyu Zhao, Yihui Wang, Can Yang, Hao Chen
- **Venue (verified)**: *CVPR 2025* (`doi:10.1109/cvpr52734.2025.00481` · `arXiv:2503.01653v2`)
- **Problem framing (verified)**: End-to-end **2-modal (`WSI + 330 RNA pathways`, $M=2$, no real clinical pathology reports)** discrete-time NLL survival (`batch_size=1`, 50 epochs) under 60% incomplete and 0% complete (`Table 1`) training sets, tested on `P-only`, `G-only`, `P+G` across 5 TCGA cohorts (`BLCA`, `BRCA`, `COADREAD`, `LUAD`, `UCEC`).
- **Core mechanism (verified)**: Stage 1 (`UniPro`, `Eqs. 3–7`) learns 8 discrete hazard-bin $\times$ censorship CoOp prompt sequences (`[8, 255/256, 768]`) via `BioBERT-v1.2`; Stage 2 (`MultiPro`, `Eqs. 8–12`) selects top tokens via `UniPro Scoring`, inserts learnable placeholders `[H_p], [H_g]`, and infers missing tokens inside `BioBERT-v1.2` (`~110M` params) supervised by `UniPro Distillation`.
- **Key insight (verified)**: Explicitly **rejects training-sample retrieval** (`Sec. 1, p. 1–2`) and tries to compensate *both* modality-common and modality-specific distributions via LLM prompt distillation—opposite to `I08`'s truncation of 224-d modality-specific noise + `B6-LOO` residual retrieval.
- **Application domain (verified)**: Bimodal `WSI + RNA` TCGA survival (`BLCA`, `BRCA`, `COADREAD`, `LUAD`, `UCEC`).
- **Assumptions & scope**: $M=2$ only (`BioBERT` processes synthetic prompt prefixes, not patient pathology reports); heavy LLM fine-tuning (`bs=1`); alters complete-modality path; zero Stiefel projection, zero LOO residuals, zero IQR gate.
- **Closest-passage evidence**:
  - `Sec. 1, pp. 1–2`: *"the goal of retrieval-based imputation methods is to fill in missing modalities by seeking the most similar sample ... The reason is that an individual sample exhibits considerable randomness..."*
  - `Sec. 3.3, pp. 4–5`: *"To compensate for modality-specific knowledge, we re-use the unimodal prompts $T_g$ learned in stage 1 ... to supervise the learning of imputed representations."*
- **Refined overlap**: `Problem framing: Partial` · `Core mechanism: Differ` · `Key insight: Differ` · `Application domain: Match` → **`2 / 4` conservative (`Level 3 — Medium Overlap`)**.

---

### 6. **LD-CVAE** (Zhou et al., *CVPR* 2025) — `[searched]` `[verified from full text]`
- **Title**: *Robust Multimodal Survival Prediction with Conditional Latent Differentiation Variational AutoEncoder*
- **Authors**: Junjie Zhou, Jiao Tang, Yingli Zuo, Peng Wan, Daoqiang Zhang, Wei Shao
- **Venue (verified)**: *CVPR 2025*, pp. 10384–10393 (`doi:10.1109/cvpr52734.2025.00971`)
- **Problem framing (verified)**: End-to-end **unidirectional 2-modal (`WSI -> missing Genomics` only; cannot handle missing WSI or clinical text)** discrete-time NLL survival trained on complete data (`Sec. 4.2, p. 10389`) across 5 TCGA cohorts (`BLCA`, `BRCA`, `GBMLGG`, `LUAD`, `UCEC`).
- **Core mechanism (verified)**: Compresses `CTransPath` WSI bags via Nyström `VIB-Trans` (`Eq. 5`), models 6 functional genomic posteriors via Markov-chain `LD-CVAE` + Product-of-Experts (`PoE`) + diagonal Wasserstein alignment (`Eqs. 6–12`), decodes $\tilde{X}$, and runs MCAT co-attention (`Eq. 14`) even when genuine genomics is present.
- **Key insight (verified)**: Differentiating shared genomic posteriors into 6 function-specific posteriors conditioned on VIB-compressed WSIs improves variational synthesis of missing genomic embeddings.
- **Application domain (verified)**: Bimodal `WSI + Genomics` TCGA survival (`BLCA`, `BRCA`, `GBMLGG`, `LUAD`, `UCEC`).
- **Assumptions & scope**: Assumes WSI is universally present; generative VAE synthesis of full genomic features; alters complete-data path; zero Stiefel truncation, zero `B6-LOO`.
- **Closest-passage evidence**:
  - `Sec. 1, p. 10385`: *"LD-CVAE that can reconstruct the genomic embeddings with diverse biological functions from WSIs ... even with the missing genomic data."*
- **Refined overlap**: `Problem framing: Partial` · `Core mechanism: Differ` · `Key insight: Differ` · `Application domain: Match` → **`2 / 4` conservative (`Level 3 — Medium Overlap`)**.

---

### 7. **ProSurv** (Liu et al., *MICCAI* 2025) — `[searched]` `[verified from full text]`
- **Title**: *Prototype-Guided Cross-Modal Knowledge Enhancement for Adaptive Survival Prediction*
- **Authors**: Fengchun Liu, Linghan Cai, Zhikang Wang, Zhiyuan Fan, Jin-gang Yu, Hao Chen, Yongbing Zhang
- **Venue (verified)**: *MICCAI 2025*, LNCS pp. 522–532 (`doi:10.1007/978-3-032-04978-0_50` · `arXiv:2503.10726`)
- **Problem framing (verified)**: End-to-end **2-modal (`WSI + Genomics`, no Text)** discrete-time NLL survival supporting complete and unimodal inference; **modifies complete-modality features** via $(F_p^i + F_{g2p}^i)/2$ (`Eq. 5`).
- **Core mechanism (verified)**: Learnable survival-bin prototype banks $B_p, B_g \in \mathbb{R}^{4 \times 32 \times d}$ updated via censoring-aware contrastive loss (`Eq. 2`), scaled dot-product cross-attention translation into full $\mathbb{R}^d$ under MSE loss (`Eqs. 3–4`), and ungated concatenation (`Eq. 6`).
- **Key insight (verified)**: Population-level survival-interval prototype banks summarize dataset-wide modality statistics for cross-modal translation without patient kNN retrieval.
- **Application domain (verified)**: Bimodal `WSI + Genomics` TCGA survival (`BRCA`, `BLCA`, `STAD`, `CRAD`).
- **Assumptions & scope**: 2-modal only; population prototypes without patient residual retrieval, Hat-LOO debiasing, Stiefel truncation, or confidence gating; violates $D_0$ on complete data.
- **Closest-passage evidence**:
  - `Sec. 2.5, pp. 5–6, Eqs. 5–6`: *"we fuse the original features with the corresponding translated features using an averaging function ... $H_p = \phi(\text{Concat}(F_p^i, F_{p2g}^i))$."*
- **Refined overlap**: `Problem framing: Partial` · `Core mechanism: Differ` · `Key insight: Differ` · `Application domain: Match` → **`1 / 4` axes matching (`Level 4 — Low Overlap`)**.

---

### 8. **MurreNet** (Liu et al., *MICCAI* 2025) — `[searched]` `[verified from full text]`
- **Title**: *MurreNet: Modeling Holistic Multimodal Interactions Between Histopathology and Genomic Profiles for Survival Prediction*
- **Authors**: Mingxin Liu, Chengfei Cai, Jun Li, Pengbo Xu, Jinze Li, Jiquan Ma, Jun Xu
- **Venue (verified)**: *MICCAI 2025* (`doi:10.1007/978-3-032-05182-0_39` · `arXiv:2507.04891v1`)
- **Problem framing (verified)**: **Strictly 100% complete paired 2-modal (`WSI + Genomics`)** NLL survival fusion on 6 TCGA cohorts (`Table 1 & 2`: `P. ✓, G. ✓`). **Downgraded from abstract triage**: zero missing-modality support (`Eq. 2` bilinear co-attention $A = \text{Linear}(h_p^o)^\top \text{Linear}(h_g^o)$ cannot execute if a modality is absent).
- **Core mechanism (verified)**: Specific MLP + bilinear co-attention common encoders (`MRD`, `Eqs. 1–2`), Nyström Transformer decoders, sample-wise 1D vector Gram-Schmidt orthogonalization retaining `[f_{s,orth}, f_c]` (`DHOF`, `Eq. 5`), and intra-modal autoencoding MSE loss (`Eq. 9`).
- **Key insight (verified)**: Prevents shared features from suppressing modality-specific cues during *complete* paired fusion.
- **Application domain (verified)**: Complete paired `WSI + Genomics` TCGA survival (`BLCA`, `BRCA`, `COADREAD`, `LUAD`, `UCEC`, `STAD`).
- **Assumptions & scope**: Requires complete paired inputs at test time; retains specific branch; zero missing-modality recovery.
- **Closest-passage evidence**:
  - `Sec. 2.3, Eq. 5, p. 5`: *"$f_{s,\text{orth}}^{(i,j)} = f_s^{(i,j)} - f_{s,\text{proj}}^{(i,j)}$ ... a fully-connected layer is employed to produce the final multimodal representation $f_{mm}$."*
- **Refined overlap**: `Problem framing: Differ` · `Core mechanism: Differ` · `Key insight: Differ` · `Application domain: Match` → **`1 / 4` axes matching (`Level 4 — Low Overlap`)**.

---

### 9. **PS3** (Raza et al., *ICCV* 2025) — `[searched]` `[verified from full text]`
- **Title**: *PS3: A Multimodal Transformer Integrating Pathology Reports with Histology Images and Biological Pathways for Cancer Survival Prediction*
- **Authors**: Manahil Raza, Ayesha Azam, Talha Qaiser, Nasir Rajpoot
- **Venue (verified)**: *ICCV 2025* (`arXiv:2509.20022v1`, p. 1 footnote: `* Accepted at ICCV 2025`)
- **Problem framing (verified)**: **Complete-modality-only** end-to-end tri-modal (`WSI + 50 Hallmark Pathways + Pathology Reports`) Cox survival prediction (`0` occurrences of `missing`/`imput*` across 16 pages). Serves as the **enabling upstream architecture** motivating `I07/I08`.
- **Core mechanism (verified)**: GMM WSI prototypes ($N_H=16$), self-attention text prototypes ($N_T$), and SNN pathway prototypes ($N_P=50$) fused via 9 intra/cross-attention blocks (`Eq. 12`), per-modality LayerNorm + mean pooling, concatenation, and linear Cox head $f_{\text{risk}}$ (`Eq. 14` — directly confirming `I08` Proposition 1's architectural premise!).
- **Key insight (verified)**: Balanced prototype token counts prevent gigapixel WSIs from dominating concise text and pathway tokens during complete tri-modal fusion.
- **Application domain (verified)**: Complete tri-modal `WSI + RNA + Pathology Report` TCGA survival (`BLCA`, `LUAD`, `KIRC`, `STAD`, `CRC`, `HNSC`).
- **Assumptions & scope**: Requires all 3 modalities for every patient (`Table 2` two-modality rows retrain separate networks from scratch).
- **Closest-passage evidence**:
  - `Sec. 3.5, Eq. 14, p. 6`: *"The final patient-level representation is obtained by concatenating these averaged modality-specific embeddings, which are then passed through a linear layer $f_{\text{risk}}$."*
- **Refined overlap**: `Problem framing: Differ` · `Core mechanism: Differ` · `Key insight: Differ` · `Application domain: Match` → **`1 / 4` axes matching (`Level 4 — Low Overlap`, Upstream Backbone)**.

---

### 10. **LWR (Latent World Recovery)** (Wang et al., `arXiv:2606.12362v1`, Jun 2026) — `[searched]` `[verified from full text]`
- **Title**: *Latent World Recovery for Multimodal Learning with Missing Modalities*
- **Authors**: Hui Wang, Tianyu Ren, Joseph Butler, Christopher Baker, Karen Rafferty, Simon McDade
- **Venue (verified)**: `arXiv:2606.12362v1` (`2026-06-10`)
- **Problem framing (verified)**: Unsupervised incomplete tabular multi-omics representation learning (`mRNA, miRNA, methylation, CNV, RPPA`; **no WSI or clinical text**) with missingness at train and test, evaluated downstream via external `XGBoost` and `coxph`.
- **Core mechanism (verified)**: Modality VAEs + observed-only attention fusion (`Eqs. 4–6`, excluding missing slots without imputation) + mini-batch stop-gradient KL neighborhood alignment during training (`Eq. 12`). Zero test-time neighbor retrieval, zero Stiefel projection, zero LOO residuals, zero IQR gate.
- **Key insight (verified)**: Aggregating only observed omics embeddings with training-time mini-batch relational KL avoids generative reconstruction error.
- **Application domain (verified)**: Tabular multi-omics across 17 TCGA cohorts and cell lines (`Table 6`: attention fusion `0.631` underperforms uniform mean `0.640` on survival).
- **Closest-passage evidence**:
  - `Sec. 1, p. 2`: *"Missing modalities are not replaced by zero vectors, mask tokens, or imputed features; they are excluded from the fusion operation."*
- **Refined overlap**: `Problem framing: Differ` · `Core mechanism: Differ` · `Key insight: Differ` · `Application domain: Partial` → **`1 / 4` axes matching (`Level 4 — Low Overlap`)**.

---

### 11. **CalMRL** (Liu et al., *ICML* 2026) — `[model-recall]` `[verified from full text]`
- **Title**: *Calibrated Multimodal Representation Learning with Missing Modalities*
- **Authors**: Xiaohao Liu, Xiaobo Xia, Jiaheng Wei, Shuo Yang, Xiu Su, See-Kiong Ng, Tat-Seng Chua
- **Venue (verified)**: *ICML 2026*, PMLR 306 (`arXiv:2511.12034` · `https://github.com/Xiaohao-Liu/CalMRL`)
- **Problem framing (verified)**: Continual contrastive encoder alignment on incomplete multimedia (`VAST-150K`, `MSR-VTT`, `AudioCaps`) evaluated exclusively on **complete-modality test splits** (`Appendix C.1`) for video/audio retrieval and classification.
- **Core mechanism (verified)**: Batch Probabilistic PCA EM (`Eqs. 2–6`) linearly imputing training-batch embeddings $\hat{z}^{m'} = W^{m'} m + \mu^{m'}$ (`Proposition 2, Eq. 7`) before Gramian SVD leading-singular-value maximization (`Eqs. 8–9`). Zero Hat-matrix LOO residuals, zero neighbor retrieval, zero IQR gate, zero Stiefel truncation.
- **Key insight (verified)**: Linear-Gaussian posterior mean imputation bounds Davis–Kahan singular-vector anchor shift $\lVert u_1 - u_1^\Omega \rVert$ during encoder alignment (`Theorem 1`).
- **Application domain (verified)**: General multimedia video-audio-subtitle-text retrieval and classification (zero medical/survival).
- **Closest-passage evidence**:
  - `Sec. 3, Eq. 7, p. 4 & Appendix C.1, p. 18`: *"$\hat{z}^{m'} = W^{m'} m + \mu^{m'}$ ... For the testing splits, the complete modalities are provided."*
- **Refined overlap**: **`0 / 4` axes matching (`Level 5 — No Overlap`)**.

---

### 12. **LAPE** (Wang, Yu & Ming, *NeurIPS* 2026 / `arXiv:2610.30652v1`) — `[web-verified Q4 recovery]` `[verified from full text]`
- **Title**: *Laplace-Calibrated Nearest-Neighbor Anchor Interpolation for Post-Hoc Confidence Calibration* (verified `arXiv:2610.30652v1`, `2026-10-22`)
- **Authors**: Xihao Wang, Chengyao Yu, Ruixing Ming
- **Venue (verified)**: `arXiv:2610.30652v1` (*NeurIPS* 2026)
- **Problem framing (verified)**: Post-hoc multi-class classification probability calibration (`ECE / Brier`) on **complete inputs** (`ImageNet / CIFAR / tabular`), with zero missing modalities and zero survival analysis.
- **Core mechanism (verified)**: Interpolates a classifier's predicted probability simplex anchor with Laplace-smoothed kNN class-label frequencies (`Eq. 2`), using $V$-fold cross-fitting (`Sec. 3.2`) and per-query grid search (`Algorithm 1`). Zero cross-modal regression, zero ridge Hat-matrix $(1-H_{jj})^{-1}$ PRESS residuals, zero IQR density gate.
- **Key insight (verified)**: Laplace-smoothed local class counts shrink overconfident softmax probabilities toward empirical local accuracy on complete feature spaces.
- **Application domain (verified)**: Standard vision/tabular classification confidence calibration.
- **Closest-passage evidence**:
  - Verified from `lape_2610_30652.txt` (`Sec. 3.1–3.2`, `Eq. 2`, `Alg. 1`): operates purely on probability simplexes $\Delta^{C-1}$ of complete inputs via $V$-fold cross-fitting rather than cross-modal latent subspaces or Hat-matrix linear residuals.
- **Refined overlap**: **`0 / 4` axes matching (`Level 5 — No Overlap`)**.

---

## Part B — 4 Additional Survival Missing-Modality Papers (`Abstract / Metadata Verified`)

1. **`[003]` Song et al. (2026)** — *A cancer-type-aware framework for robust multimodal survival prediction under missing modalities*, *Briefings in Bioinformatics* (`doi:10.1093/bib/bbag124`) `[searched]` `[abstract-verified]`: End-to-end pan-cancer survival (`10` TCGA cancers) **mandating WSI as a universally available anchor modality** with imputation-free adaptive gated fusion; fails when WSI is missing (`rna`, `text`, `rna+text`) and uses zero Stiefel truncation or `B6-LOO` → **`1 / 4` (`Level 4 — Low Overlap`)**.
2. **`[037]` Yang, Hu & He (2025)** — *HMSP: Hierarchical Multimodal Semantic Fusion of Pathology-Text-Genomic Representations for Robust Survival Prediction*, *IEEE MedAI 2025* (`doi:10.1109/medai67139.2025.00013`) `[searched]` `[abstract-verified]`: End-to-end tri-modal (`WSI + Text + Genomics/IHC`) hierarchical fusion with Cone-Based Hyperbolic (`H-Cone`) regularization using reports solely as a unidirectional surrogate when genomics are absent → **`2 / 4` conservative (`Level 3 — Medium Overlap`)**.
3. **`[004]` Ruffini et al. (2026)** — *Handling missing modalities in multimodal survival prediction for non-small cell lung cancer*, *npj Digital Medicine* (`doi:10.1038/s41746-026-02783-3`) `[searched]` `[abstract-verified]`: End-to-end `CT + WSI + Clinical tabular` imputation-free intermediate fusion in NSCLC (no RNA or text reports) → **`1 / 4` (`Level 4 — Low Overlap`)**.
4. **`[045]` Yao et al. (2026)** — *S2U-Surv: From seen to unseen sample-specific generation for incomplete multimodal survival prediction*, *Pattern Recognition* (`doi:10.1016/j.patcog.2026.115268`, paywalled ScienceDirect) `[searched]` `[metadata-verified]`: Parametric sample-specific cross-modal feature generation ("seen to unseen") rather than orthogonal complement truncation or Hat-matrix LOO residual retrieval → **`2 / 4` conservative (`Level 3 — Medium Overlap`)**.

---

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

---

# Step 7 — Crisp Delta Statements, Formula Guardrails & SCI Q3 Boundary Prose

- **Step Number**: 7
- **Step Name**: State a Crisp Delta (Calibrated for SCI Q3 *BMC Bioinformatics*)
- **Timestamp**: 2026-11-11 20:49 JST

---

## 1. Overall One-Sentence `/scoop-check` Delta

> Unlike prior incomplete multimodal cancer survival methods that retrain end-to-end 2-modal encoders from scratch with raw neighbor feature averaging and $2^M - 1$ separate hazard heads (**RMoE**, *MICCAI* 2026), train two 1,000,000-step latent diffusion models (`879 ms/patient`) to synthesize unrecoverable modality-private complements (**MUST**, *CVPR* 2026), require 32-cancer self-supervised pretraining ($N = 10,439$) over $128 \times 512$ sequence prototypes (**PRIME**, `arXiv:2604.04999`), or substitute hard $\mu = 1$ $k$-means cluster centroids without clinical text (**M3Surv**, *Med. Image Anal.* 2026), **TriModalSurv (`I08`)** attaches post-hoc to a **frozen per-cancer tri-modal (`WSI + RNA + Pathology Text`) Cox survival backbone**, uses a lightweight Cayley–Stiefel orthogonal bottleneck (`A1 + C1`, `37,152` params, $-95.29\%$) to **zero-truncate** the 224-d modality-private noise complement, and calibrates a pattern-specific linear predictor (`B1`) via zero-retraining **PRESS Hat-matrix $(1 - H_{jj}^\Omega)^{-1}$ leave-one-out residual Top-$K$ retrieval and closed-form LOO-IQR density gating (`B6-LOO`)**, guaranteeing bit-exact complete-data invariance ($D_0$) across all six missing-modality regimes.

---

## 2. Per-Competitor Verified Deltas (`Top 5` Closest Level-3 Neighbors)

1. **Delta vs. `RMoE` (Lim et al., *MICCAI* 2026 — closest retrieval + sigmoid-gate neighbor)**:
   - `RMoE` trains an end-to-end 2-modal (`WSI + Genomics`, no Text) system under 60% training missingness, retrieves **raw full-dimensional neighbor features** ($\sum_{j \in \mathcal{N}_k} \pi_j g_j$, `Eq. 1`) using ground-truth risk-bin filtering during training, and interpolates $2^M - 1 = 3$ separate survival heads at the logit level via $\alpha = \sigma(\gamma(s_{(1)} - \delta))$ with fixed heuristic constants ($\delta = 0.4, \gamma = 10$, `Eq. 3`).
   - `TriModalSurv` operates post-hoc over a **frozen 3-modal (`WSI + RNA + Text`) backbone and 1 frozen Cox head**, truncates 224-d private variance via $U_m^\top U_m = I_{32}$ (`A1`), retrieves **Hat-matrix $(1 - H_{jj}^\Omega)^{-1}$ LOO-debiased linear prediction residuals** around continuous `B1` (directly outperforming `RMoE`-style raw neighbor averaging `M3/B3`: `0.6594` vs. `0.6526` `@default`, `0.6657` vs. `0.6589` `@selected`), and calibrates $(\delta_\Omega, \gamma_\Omega)$ **in closed form with zero tunable gate thresholds** from training-LOO 1-NN median and IQR so isolated queries shrink smoothly back to `B1` rather than dropping cross-modal recovery.

2. **Delta vs. `MUST` (Kim & Hwang, *CVPR* 2026 — closest shared/private subspace neighbor)**:
   - `MUST` retains the 256-d modality-specific complement $\hat{u}_m = (I - P_\cap) u_m$ in an end-to-end 2-modal MLP head (`Eq. 11`) and trains two 1M-step Transformer Latent Diffusion Models (`50 DDIM steps × 5 draws = 879 ms/patient`) to hallucinate missing $\tilde{u}_m$, which over-smooths structured genomic features (`Sec. 4.2`) and alters complete-data risk rankings.
   - `TriModalSurv` demonstrates that the 224-d orthogonal complement exhibits negative cross-modal $R^2_{\text{val}} \in [-0.568, -0.312]$ (`Table S4`) and causes 256-d negative transfer on single-cancer cohorts (`M7@default = 0.6406 < M0-a = 0.6519`), **truncates it to zero**, preserves complete patients bit-exactly ($D_0$), and calibrates 32-d shared nonlinearities non-parametrically via `B6-LOO` in sub-millisecond matrix lookups.

3. **Delta vs. `PRIME` (Yu et al., `arXiv:2604.04999v1`, Apr 2026 — closest 3-modal 5-cohort benchmark neighbor)**:
   - `PRIME` requires upstream pan-cancer self-supervised pretraining across **32 TCGA cancers ($N = 10,439$, 200 epochs)** to learn $128 \times 512$ pre-fusion sequence prototypes + Sparse MoE fusion; trained from scratch on individual cancer cohorts without external pretraining (`PRIME Scratch FT = 0.623, LP = 0.595`), it underperforms simple early concatenation (`0.627`), and its missingness-adapted `LP+Missing` trades off `Full` performance (`Sec. IV-D3`).
   - `TriModalSurv` requires **zero external pan-cancer pretraining**, operating strictly post-pooling on single-cancer training folds ($N_{\text{tr}} \approx 238\text{--}609$) with `37,152` parameters and bit-exact `Full` preservation ($D_0$).

4. **Delta vs. `M3Surv` (Qu et al., *Medical Image Analysis* 2026 — closest memory-bank neighbor)**:
   - `M3Surv` fuses dual-slide `FF+FFPE WSI` + `3-Omics` (excluding clinical text) and substitutes raw pre-fusion features from a $k$-means cluster-centroid memory bank (`Eq. 10`), where averaging $\mu > 1$ prototypes degrades C-index due to inter-cluster noise (`Sec. 4.3, p. 8`), forcing hard $\mu = 1$ centroid replacement.
   - `TriModalSurv` handles all 6 tri-modal (`WSI + RNA + Text`) missingness patterns and shifts retrieval from raw cluster centroids to **continuous `B1` + Top-$K$ Hat-LOO residuals + LOO-IQR density shrinkage (`B6-LOO`)**, allowing multi-neighbor ($K=10$) smoothing without cluster quantization noise.

5. **Delta vs. `DisPro` (*CVPR* 2025) & `LD-CVAE` (*CVPR* 2025)**:
   - Both are end-to-end 2-modal (`WSI + Genomics`, no real clinical reports) discrete-NLL architectures (`DisPro` fine-tuning `~110M`-param `BioBERT` CoOp prompts at `bs=1` while rejecting neighbor retrieval; `LD-CVAE` restricted unidirectionally to `WSI -> missing Genomics`), whereas `TriModalSurv` is a frozen-backbone post-hoc 3-modal Cox plug-in handling all 6 missing subsets symmetrically with `37,152` parameters.

---

## 3. Mandatory Citation & Formula Guardrails Before Manuscript Submission

1. **`RMoE` Eq. (3) Guardrail (CRITICAL)**:
   - **Never** describe $\alpha_i^\Omega = \alpha_{\max}\sigma(\gamma_\Omega(s_{i,(1)}^\Omega - \delta_\Omega))$ as a newly invented sigmoid gating formula. Cite **Lim et al. (*MICCAI* 2026)** in `Methods §2.3` as the inspiration for thresholded 1-NN similarity sigmoid gating, and emphasize our **three task-specific innovations**: (i) **zero-parameter closed-form LOO-IQR calibration** ($\delta_\Omega = Q_{0.50}^{\text{LOO}}, \gamma_\Omega = \operatorname{clip}(1.349/\operatorname{IQR}_\Omega, 5, 30)$) vs. fixed $\delta=0.4, \gamma=10$; (ii) **single-head latent residual shrinkage** back to global linear `B1` vs. $2^M-1$ multi-head logit routing; and (iii) **PRESS Hat-leverage LOO residual pooling** vs. raw neighbor feature averaging (`M3/B3`).
2. **Exact `.bib` Metadata Guardrail (Correcting Preliminary Labels)**:
   - `PRIME`: Cite as `Yu K, Zhou S, Song Y, Zhan Z, et al. PRIME: Prototype-Driven Multimodal Pretraining for Cancer Prognosis with Missing Modalities. arXiv preprint arXiv:2604.04999, 2026.` (**Do NOT cite as *Briefings in Bioinformatics* 2025!** Cite `Song Y, Zhan Z, Xie F, ..., Zhang R, Lin M. Briefings in Bioinformatics, 2026, bbag124` separately if referencing their universal-WSI gated fusion paper.)
   - `M3Surv`: Cite as `Qu M, Yang G, Di D, Gao Y, Song Y, Fan L. M3Surv: Fusing Multi-slide and Multi-omics for Memory-augmented robust Survival prediction. Medical Image Analysis, 2026, 107: 103846.` (**Do NOT cite as *NeurIPS* 2025!**)
   - `PS3`: Cite as `Raza M, Azam A, Qaiser T, Rajpoot N. PS3: A Multimodal Transformer Integrating Pathology Reports with Histology Images and Biological Pathways for Cancer Survival Prediction. In: Proceedings of the IEEE/CVF International Conference on Computer Vision (ICCV), 2025 (arXiv:2509.20022).`
3. **De-Hyped `A1` & `C1` Framing Guardrail (SCI Q3 Calibration)**:
   - Explicitly cite classical shared/private orthogonality (`Bousmalis et al., NeurIPS 2016`; `Hazarika et al., ACM MM 2020`) for `A1` and classical PRESS leverage residuals (`Allen, Technometrics 1974`; `Cook & Weisberg, 1982`) for $(1 - H_{jj}^\Omega)^{-1}$, framing `A1` and `C1` honestly as canonical low-variance structural building blocks rather than overclaimed theoretical inventions.

---

## 4. Ready-to-Paste SCI Q3 *BMC Bioinformatics* Background / Related-Work Positioning Paragraph

```latex
Existing approaches to incomplete multimodal cancer survival prediction generally
fall into three paradigms, each facing practical barriers when deployed on
moderate-sized per-cancer cohorts ($N_{\text{tr}} \approx 238\text{--}609$) with
three heterogeneous modalities (WSI, transcriptomics, and clinical pathology
reports). First, \emph{generative and prompt-distillation frameworks}—including
conditional variational autoencoders (LD-CVAE~\cite{zhou2025ldcvae}), BioBERT
prompt distillation (DisPro~\cite{xu2025dispro}), and latent diffusion models
that synthesize modality-specific orthogonal complements (MUST~\cite{kim2026must})—require
end-to-end retraining on bi-modal (WSI + genomics) inputs, incur substantial
sampling latency, and alter complete-modality predictions; on single-cancer
cohorts, attempting to reconstruct unshared high-dimensional features readily
injects modality-specific variance. Second, \emph{parametric prototype and
pan-cancer pretraining architectures} such as ProSurv~\cite{liu2025prosurv} and
PRIME~\cite{yu2026prime} synthesize missing representations from learned
population codebooks, but either overwrite complete-modality features or rely on
large-scale pan-cancer self-supervised pretraining ($N = 10{,}439$ across 32
cancers in PRIME) to avoid single-cohort over-fitting. Third, \emph{memory-bank
and retrieval-based methods} such as M3Surv~\cite{qu2026m3surv} and
RMoE~\cite{lim2026rmoe} retrieve raw training features or $k$-means centroids
and, in RMoE, route logits across $2^M - 1$ separate hazard heads via a
heuristic similarity sigmoid ($\delta=0.4, \gamma=10$); however, averaging raw
neighbor features suffers from cluster boundary drift (forcing hard $\mu=1$
replacement in M3Surv), while maintaining $2^M - 1 = 7$ separate survival heads
fragments tri-modal training cohorts. In contrast, our plug-in attaches
post-pooling to a \emph{single frozen} tri-modal Cox backbone (\texttt{PS3}~\cite{raza2025ps3}),
uses a canonical Stiefel orthonormal bottleneck (\texttt{A1}+\texttt{C1},
$95.29\%$ parameter reduction) to truncate unrecoverable 224-dimensional private
complements to zero, and retrieves \emph{leave-one-out Hat-leverage-debiased
linear prediction residuals} gated by closed-form LOO-IQR empirical density
statistics (\texttt{B6-LOO}) while guaranteeing exact complete-data invariance ($D_0$).
```

---

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
