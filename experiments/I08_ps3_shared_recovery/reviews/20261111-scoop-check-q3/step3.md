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
