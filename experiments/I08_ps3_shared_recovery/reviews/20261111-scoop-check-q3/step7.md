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
