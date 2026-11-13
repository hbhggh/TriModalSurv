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
