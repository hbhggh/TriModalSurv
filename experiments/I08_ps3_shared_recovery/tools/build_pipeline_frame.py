"""生成 I08 全流程合并 frame：数据集 → 冻结 encoder（特征压缩）→ token → PS3 融合（特征交互）→ pooled → 算子 A/B/C → 风险。

合并 index.excalidraw 里的「PS3-style backbone 定稿（2026-10-09）」与「PS3-style + 算子 A1·B1·C1 总体框架（I08）」，
两张原图不动，新 frame 放在 I08 frame 右侧。数值只取自 I07 model.py / README、原定稿 frame 文字与 I08 config.yaml。

用法：python3 build_pipeline_frame.py <源.excalidraw> <输出.excalidraw>
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from excalidraw_kit import Canvas, append_frame  # noqa: E402

FRAME_ID = 'i08-pipeline-frame'
X0, Y0 = 1400.0, 14384.0
W, H = 4320.0, 1255.0
F = 18                                   # 框内字号
MOD = (('rna', 'RNA', '#ebfbee'), ('wsi', 'WSI', '#e7f5ff'), ('text', 'Text', '#fff4e6'))
ROW_Y, ROW_H = (200, 460, 720), 230      # 三模态行（相对 Y0）


def build(c):
    t, box, arrow, rect = c.text, c.box, c.arrow, c.rect
    X, Y = X0, Y0
    els = []

    # 冻结边界放最底层（先画）
    els.append(rect(X + 385, Y + 165, 1750, 825, 'transparent', dashed=True, stroke='#868e96'))
    els.append(t(X + 395, Y + 998, '冻结 I07（②–⑤ 与 ⑩）：eval()，requires_grad = False；来源 i07-ps3-20261011 的 25 个 tri ckpt（5 癌 × 5 折）', 18, '#868e96'))

    els.append(t(X + 18, Y + 17, 'I08 全流程框架：数据集 → 特征压缩 → 特征交互 → 算子 A·B·C → 风险（2026-11-06）', 36, '#e03131'))
    els.append(t(X + 18, Y + 71, '合并「PS3-style backbone 定稿（2026-10-09）」与「PS3-style + 算子 A1·B1·C1 总体框架（I08）」；形状记作 [B, token 数, 维度]，d = 256，r = 32'))

    stages = ((20, '① 数据集产生'), (400, '② 特征压缩：冻结 encoder'), (750, '③ token 构造'),
              (1230, '④ 特征交互：PS3 注意力'), (1760, '⑤ 模态汇聚'), (2180, '⑥ 路由'), (2500, '⑦ 算子 A'),
              (2990, '⑧ 算子 B'), (3500, '⑨ 解码 + 拼接'), (3920, '⑩ 风险头'))
    for dx, label in stages:
        els.append(t(X + dx, Y + 122, label, 20, '#1971c2'))

    raw = ('RNA 原始数据\nGDC STAR-Counts\ntpm_unstranded\n每人一个基因表达向量',
           'WSI 原始数据\nTCGA DX 诊断切片\n20×，256 px patch',
           '病理报告\nTCGA 病理报告文本\n→ I06 结构化 payload\n（Claude Opus 5.5 浓缩，\n  已冻结）')
    enc = ('无预训练 encoder\n（通路 SNN 在 ③）',
           '冻结 UNI2-h\n（MahmoodLab）\n每个 patch → 1536 维\n[N_patch, 1536]',
           '冻结 NeuML\nbioclinical-modernbert\n逐字段编码\n"字段名: 值"\n每个字段 → 768 维 [F, 768]')
    tok = ('log2(1+TPM)\n→ 50 个 Hallmark 基因集\n按基因 z-score（只用 train 拟合）\n每条通路 2 层 SNN → 256\n+ 模态嵌入 e_rna\nP ∈ R^{B×50×256}',
           '每张切片 MiniBatchKMeans\n→ 128 个中心（无序集合）\n不足补零 + mask [B,128]\nLinear 1536 → 256，无位置编码\n+ 模态嵌入 e_wsi\nH ∈ R^{B×128×256}',
           'Linear 768 → 256 + 字段身份嵌入\nnot mentioned → [NOT_MENTIONED]\n+ 模态嵌入 e_text\nT ∈ R^{B×F×256}\nF：BLCA 14 · BRCA 16 · LUAD 13\n    LGG 15 · UCEC 13')
    pool = 'f_β：Linear + ReLU\n→ LayerNorm\n→ 对有效 token 求均值\np_{m} ∈ R^{{B×256}}'
    for i, (m, name, fill) in enumerate(MOD):
        y = Y + ROW_Y[i]
        els += box(X + 20, y, 330, ROW_H, fill, raw[i], size=F)
        els += box(X + 400, y, 300, ROW_H, fill, enc[i], size=F)
        els += box(X + 750, y, 420, ROW_H, fill, tok[i], size=F)
        els += box(X + 1760, y, 360, ROW_H, fill, pool.replace('{m}', m).replace('{{B×256}}', '{B×256}'), size=F)
        mid = y + ROW_H / 2
        els.append(arrow([(X + 350, mid), (X + 400, mid)]))
        els.append(arrow([(X + 700, mid), (X + 750, mid)]))
        els.append(arrow([(X + 1170, mid), (X + 1230, mid)]))
        els.append(arrow([(X + 1700, mid), (X + 1760, mid)]))
        els.append(arrow([(X + 2120, mid), (X + 2180, Y + 600)]))

    els += box(X + 1230, Y + 200, 470, 750, '#f3f0ff',
               'PS3 融合（单层，沿用 PS3）\n\n'
               'Z = [P | H | T]\n   ∈ R^{B×(178+F)×256}\n\n'
               'Q、K、V：Linear 256 → 256\n'
               'logits = QKᵀ/√256 + b_m\n'
               '（b_m：key 所属模态的可学习偏置）\n'
               'key mask：WSI 补零位\n'
               '缺失模态的 token 整段不进入\n（query 与 key 都去掉）\n\n'
               '单一 row-wise softmax\n= 9 个块：3 个模态内 + 6 个跨模态\n\n'
               'h = LN(Z + Dropout(A·V))\n'
               'h = LN(h + FFN(h))\n'
               '输出 ∈ R^{B×(178+F)×256}', size=F)

    els += box(X + 2180, Y + 530, 260, 140, '#fff9db', '路由\nΩ 是否三模态全有？\n（7 种场景）', size=F)
    els.append(t(X + 1762, Y + 172, '两次前向：全部 → p^F；Ω → p^Ω', 16))

    els += box(X + 2500, Y + 200, 420, 420, '#ffe3e3',
               '算子 A：A1 低秩正交共享基\n（推理时参与，可训练）\n\n'
               'x = p^Ω_m − μ^Ω_{Ω,m}\nz_m = U_mᵀ x ∈ R^{B×r}\n'
               'U_m ∈ R^{256×r}，U_mᵀU_m = I_r\n正交参数化，PCA 初始化\n'
               'x_res = x − U_m z_m（不恢复）\n每模态一套，r = 32 → 24,576\n\n'
               '来源：ShaSpec [R2] 的共享/特有思路', size=F)
    els += box(X + 2990, Y + 200, 440, 420, '#fff3bf',
               '算子 B：B1 按缺失模式线性恢复\n（推理时参与，可训练）\n\n'
               '输入：可见 z 按 rna→wsi→text 拼接\n      ∈ R^{B×k·r}，k = |Ω|\n'
               'ẑ_u = R_{Ω→u}·[z_m] + b_{Ω,u}\n      ∈ R^{B×r}\n'
               '6 种 Ω，9 个 (Ω, u) 映射 → 12,576\n只恢复共享部分，不生成剩余\n\n'
               '来源：ShaSpec Eq.4 [R2] + P-b-P [R9]', size=F)
    els += box(X + 3500, Y + 200, 360, 200, '#e3fafc',
               '解码（无新参数）\np̂_u = μ^F_u + U_u ẑ_u\n      ∈ R^{B×256}\nμ^F 只用本折 train', size=F)
    els += box(X + 3500, Y + 460, 360, 220, '#f1f3f5',
               '拼接 [rna | wsi | text]\n∈ R^{B×768}\n可见位：p^Ω_m 原样\n缺失位：p̂_u', size=F)
    els += box(X + 3920, Y + 460, 360, 220, '#f8f9fa',
               '冻结风险头（I07）\nLinear(768 → 1)\n→ risk ∈ R^{B}\n越大 = 预后越差\nI08 训练：六模式 Cox 等权', size=F)

    els.append(arrow([(X + 2440, Y + 560), (X + 2500, Y + 470)], width=2, color='#e03131'))
    els.append(t(X + 2448, Y + 680, 'Ω 缺失（6 种）→ A、B', 16, '#e03131'))
    els.append(arrow([(X + 2920, Y + 410), (X + 2990, Y + 410)]))
    els.append(t(X + 2924, Y + 382, 'z [B,r]', 16))
    els.append(arrow([(X + 3430, Y + 300), (X + 3500, Y + 300)]))
    els.append(t(X + 3434, Y + 272, 'ẑ [B,r]', 16))
    els.append(arrow([(X + 3680, Y + 400), (X + 3680, Y + 460)]))
    els.append(t(X + 3690, Y + 418, 'p̂ [B,256]', 16))
    els.append(arrow([(X + 3860, Y + 570), (X + 3920, Y + 570)]))

    # 可见模态原样直送（W1-4）、完整直通
    els.append(arrow([(X + 2440, Y + 645), (X + 3500, Y + 645)], width=2, color='#2f9e44'))
    els.append(t(X + 2930, Y + 650, '可见模态 p^Ω_m 原样直送（W1-4）', 16, '#2f9e44'))
    els.append(arrow([(X + 2310, Y + 670), (X + 2310, Y + 740), (X + 4100, Y + 740), (X + 4100, Y + 680)],
                     width=2, color='#1971c2'))
    els.append(t(X + 3420, Y + 712, 'Ω 完整：直通原 I07，逐患者恒等', 16, '#1971c2'))

    els += box(X + 2500, Y + 790, 1400, 175, '#ffffff',
               '算子 C：C1 模态对齐 + 恢复一致性（只在训练期计算，无参数，推理时不走）\n'
               'C1-a  L_modal = E_{i,m<n}[1 − cos(z^F_m, z^F_n)]，λ_m = 0.1：改自 ShaSpec DAO（Eq.8）[R2]，配对取法同 PRIME L_align [R1]\n'
               'C1-b  L_cons = E (1/r)‖ẑ^Ω_u − sg(U_uᵀ x^F_u)‖²，λ_c = 1.0：本项目，常规潜空间回归监督\n'
               '总目标 L = L_Cox^missing（6 模式等权）+ λ_a·L_anchor + λ_m·L_modal + λ_c·L_cons\n'
               '梯度只更新 U、R、b；I07 全部冻结；训练 / 选模只用本折 train / val',
               dashed=True, stroke='#e03131', size=17)
    els.append(arrow([(X + 2700, Y + 790), (X + 2700, Y + 620)], dashed=True, color='#e03131'))
    els.append(arrow([(X + 3200, Y + 790), (X + 3200, Y + 620)], dashed=True, color='#e03131'))
    els.append(t(X + 2708, Y + 752, 'z^F（L_modal）', 16, '#e03131'))
    els.append(t(X + 3208, Y + 752, 'ẑ vs sg(U_uᵀx^F_u)（L_cons）', 16, '#e03131'))
    els.append(arrow([(X + 1940, Y + 950), (X + 1940, Y + 1040), (X + 2450, Y + 1040), (X + 2450, Y + 900),
                      (X + 2500, Y + 900)], dashed=True, color='#e03131'))
    els.append(t(X + 1950, Y + 1048, '训练时 p^F_m（完整前向，只作目标）', 16, '#e03131'))

    els += box(X + 20, Y + 1085, 4260, 150, '#fff9db',
               '维度速查（详见 experiments/I08_ps3_shared_recovery/interface.md 与 config.yaml）\n'
               '· 人群：TCGA 5 癌（BLCA、BRCA、LUAD、LGG、UCEC）三模态完整患者；5 折 train / val / test = 70 / 10 / 20（按事件分层，种子 2026）\n'
               '· token：P 50 ｜ H 128（带 mask）｜ T F = 13–16 → 拼接 178+F 个；隐藏维 d = 256；I07 用 Cox 损失训练，bs = 64\n'
               '· I08：冻结 I07；可训练 U_m × 3（256 × 32）+ R、b × 9 = 37,152 参数；C 只在训练期；test 锁定\n'
               '· 颜色：绿 RNA ｜ 蓝 WSI ｜ 橙 Text ｜ 紫 PS3 融合 ｜ 灰虚线 = 冻结 I07 ｜ 红 = 算子 A ｜ 黄 = 算子 B ｜ 红虚线 = 算子 C ｜ 绿线 = 可见直送 ｜ 蓝线 = 完整直通',
               size=F)

    return els, c.frame(X, Y, W, H, 'I08 全流程（数据 → encoder → 交互 → 算子）')


def main(src, out):
    append_frame(src, out, Canvas(FRAME_ID, 'i08p', 20261107), X0, Y0, W, H, build)


if __name__ == '__main__':
    main(*sys.argv[1:3])
