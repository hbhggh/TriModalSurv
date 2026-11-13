"""生成 I08 总体框架 frame（PS3-style + A1·B1·C1），追加进一份 .excalidraw 的副本。

用法：python3 build_framework_frame.py <源.excalidraw> <输出.excalidraw>
- 只追加新元素（新 frame 放在原 PS3 frame 右侧），不改任何已有元素；守卫见 excalidraw_kit.append_frame。
- 样式沿用原 PS3 frame：Excalifont（fontFamily 5）、20 px、lineHeight 1.25、圆角矩形、同一套浅色填充。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from excalidraw_kit import Canvas, append_frame  # noqa: E402

FRAME_ID = 'i08-abc-framework-frame'
X0, Y0 = -1500.0, 14384.0
W, H = 2730.0, 1190.0


def build(c):
    text, box, arrow = c.text, c.box, c.arrow
    X, Y = X0, Y0
    els = []
    els.append(text(X + 18, Y + 17, 'PS3-style + 算子 A1·B1·C1 总体框架（I08，2026-11-06）', 36, '#e03131'))
    els.append(text(X + 18, Y + 71, '冻结 I07 → pooled p_m ∈ R^{B×256} → 完整：直通原风险头 ｜ 缺失：A 共享坐标 → B 按缺失模式恢复 → 解码填缺失位 → 冻结风险头；C 只在训练期'))

    els += box(X + 16, Y + 136, 420, 615, '#f8f9fa',
               '冻结 PS3-style 骨架（I07）\n\ntoken：P 50 ｜ H 128 ｜ T 13–16\nPS3 融合：9 个注意力块\n单一 row-wise softmax + b_m\n→ f_β → LayerNorm\n→ 有效 token 均值\n\n每名患者前向：\npresent = 全部 → p^F_m\npresent = Ω → p^Ω_m（m ∈ Ω）\n\neval()，requires_grad = False\n25 个 tri ckpt（5 癌 × 5 折）\n来源：i07-ps3-20261011')
    for i, (name, fill) in enumerate((('rna', '#ebfbee'), ('wsi', '#e7f5ff'), ('text', '#fff4e6'))):
        y = Y + 136 + i * 130
        els += box(X + 500, y, 300, 110, fill, f'p_{name} ∈ R^{{B×256}}\n（pooled[{name}]）')
        els.append(arrow([(X + 436, y + 55), (X + 500, y + 55)]))
    els += box(X + 500, Y + 600, 300, 90, '#fff9db', '路由：Ω 是否三模态全有？\n（7 种场景）')
    els.append(arrow([(X + 650, Y + 506), (X + 650, Y + 600)]))

    els += box(X + 880, Y + 136, 420, 360, '#ffe3e3',
               '算子 A：A1 低秩正交共享基\n（推理时参与，可训练）\n\nx = p^Ω_m − μ^Ω_{Ω,m}\nz_m = U_mᵀ x ∈ R^{B×r}\nU_m ∈ R^{256×r}，U_mᵀU_m = I_r\n正交参数化，PCA 初始化\nx_res = x − U_m z_m（不恢复）\n每模态一套，r = 32 → 24,576\n来源：ShaSpec [R2] 的共享/特有思路')
    els.append(arrow([(X + 800, Y + 191), (X + 880, Y + 230)]))
    els.append(arrow([(X + 800, Y + 321), (X + 880, Y + 316)]))
    els.append(arrow([(X + 800, Y + 451), (X + 880, Y + 400)]))

    els += box(X + 1380, Y + 136, 440, 360, '#fff3bf',
               '算子 B：B1 按缺失模式线性恢复\n（推理时参与，可训练）\n\n输入：可见 z 按 rna→wsi→text 拼接\n      ∈ R^{B×k·r}，k = |Ω|\nẑ_u = R_{Ω→u}·[z_m] + b_{Ω,u}\n      ∈ R^{B×r}\n6 种 Ω，9 个 (Ω, u) 映射 → 12,576\n只恢复共享部分，不生成剩余\n来源：ShaSpec Eq.4 [R2] + P-b-P [R9]')
    els.append(arrow([(X + 1300, Y + 316), (X + 1380, Y + 316)]))
    els.append(text(X + 1306, Y + 286, 'z [B,r]', 16))

    els += box(X + 1900, Y + 136, 360, 200, '#e7f5ff',
               '解码（无新参数）\np̂_u = μ^F_u + U_u ẑ_u\n      ∈ R^{B×256}\nμ^F 只用本折 train')
    els.append(arrow([(X + 1820, Y + 236), (X + 1900, Y + 236)]))
    els.append(text(X + 1826, Y + 206, 'ẑ [B,r]', 16))
    els += box(X + 1900, Y + 380, 360, 200, '#f3f0ff',
               '拼接 [rna | wsi | text]\n∈ R^{B×768}\n可见位：p^Ω_m 原样\n缺失位：p̂_u')
    els.append(arrow([(X + 2080, Y + 336), (X + 2080, Y + 380)]))
    els.append(text(X + 2090, Y + 342, 'p̂ [B,256]', 16))
    els += box(X + 2340, Y + 380, 370, 200, '#f8f9fa',
               '冻结风险头（I07）\nLinear(768 → 1)\n→ risk ∈ R^{B}\n越大 = 预后越差')
    els.append(arrow([(X + 2260, Y + 480), (X + 2340, Y + 480)]))

    # 可见模态原样直送（W1-4）
    els.append(arrow([(X + 800, Y + 490), (X + 840, Y + 530), (X + 1900, Y + 530)], width=2, color='#2f9e44'))
    els.append(text(X + 1000, Y + 538, '可见模态 p^Ω_m 原样直送风险头（W1-4）', 18, '#2f9e44'))
    # 缺失分支进入 A
    els.append(arrow([(X + 800, Y + 630), (X + 960, Y + 496)], width=2, color='#e03131'))
    els.append(text(X + 820, Y + 640, 'Ω 缺失（6 种）→ A、B', 18, '#e03131'))
    # 完整直通
    els.append(arrow([(X + 650, Y + 690), (X + 650, Y + 770), (X + 2525, Y + 770), (X + 2525, Y + 580)], width=2,
                     color='#1971c2'))
    els.append(text(X + 1640, Y + 738, 'Ω = 三模态完整：直通原 I07 前向，逐患者恒等（不经 A/B）', 18, '#1971c2'))

    els += box(X + 880, Y + 830, 1380, 160, '#ffffff',
               '算子 C：C1 模态对齐 + 恢复一致性（只在训练期计算，无参数，推理时不走）\n'
               'C1-a  L_modal = E_{i,m<n}[1 − cos(z^F_m, z^F_n)]，λ_m = 0.1：改自 ShaSpec DAO（Eq.8）[R2]，配对取法同 PRIME L_align [R1]\n'
               'C1-b  L_cons = E (1/r)‖ẑ^Ω_u − sg(U_uᵀ x^F_u)‖²，λ_c = 1.0：本项目，常规潜空间回归监督\n'
               '总目标 L = L_Cox^missing（6 模式等权）+ λ_a·L_anchor + λ_m·L_modal + λ_c·L_cons\n'
               '梯度只更新 U、R、b；I07 全部冻结；训练 / 选模只用本折 train / val',
               dashed=True, stroke='#e03131', size=18)
    els.append(arrow([(X + 1090, Y + 830), (X + 1090, Y + 496)], dashed=True, color='#e03131'))
    els.append(arrow([(X + 1600, Y + 830), (X + 1600, Y + 496)], dashed=True, color='#e03131'))
    els.append(text(X + 1100, Y + 700, 'z^F（L_modal）', 16, '#e03131'))
    els.append(text(X + 1610, Y + 700, 'ẑ vs sg(U_uᵀx^F_u)（L_cons）', 16, '#e03131'))
    els.append(arrow([(X + 226, Y + 751), (X + 226, Y + 910), (X + 880, Y + 910)], dashed=True, color='#e03131'))
    els.append(text(X + 240, Y + 920, '训练时 p^F_m（完整前向，只作目标）', 16, '#e03131'))

    els += box(X + 16, Y + 1020, 2694, 150, '#fff9db',
               '接口要点（详见 experiments/I08_ps3_shared_recovery/interface.md 与 config.yaml）\n'
               '· 位置：pooled 之后、风险头之前（旧 B4）；完整直通，缺失分支只填缺失位\n'
               '· 冻结：I07 全部参数 / buffer / 风险头（eval）｜ 可训练：U_m × 3（256 × r）、R_{Ω→u} 与 b_{Ω,u} × 9 ｜ r = 32 → 37,152 参数\n'
               '· 均值 μ^F、μ^Ω 只用本折 train；选模：本折 val 六模式平均 Cox 损失；候选 r ∈ {16, 32} × λ_m ∈ {0.05, 0.1}；test 锁定\n'
               '· 颜色：灰 = 冻结 I07 ｜ 红 = 算子 A ｜ 黄 = 算子 B ｜ 红虚线 = 算子 C（训练期）｜ 绿 = 可见直送 ｜ 蓝 = 完整直通')

    return els, c.frame(X, Y, W, H, 'I08 PS3-style + A1·B1·C1 框架')


def main(src, out):
    append_frame(src, out, Canvas(FRAME_ID, 'i08', 20261106), X0, Y0, W, H, build)


if __name__ == '__main__':
    main(*sys.argv[1:3])
