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
