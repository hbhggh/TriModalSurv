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
