# bbag124 PDF → Word 校对清单

源文件：`/Users/wuhao/Downloads/bbag124 (1).pdf`（12 页）。

SHA-256：`715927361c19420f7f60f952acfc2db4635daa9857e4575e6d8175b4033ae43b`

输出：`bbag124_editable.docx`。单栏流式正文，Table 1 使用横向页面；本机最终渲染为 16 页。正文唯一来源为上述 PDF；保留原作者、单位、方法、结果与引用，不使用网页补全文。

## 逐页与结构核对

| 源 PDF 页 | 内容 | Word 中的位置（最终渲染页） | 检查结果 |
|---|---|---|---|
| 1 | 期刊、DOI、发布日期、文章类型、题名、7 位作者、4 个单位、通讯作者、收稿/修订/接受日期、版权、Abstract、Keywords、Introduction | 1–2 | 已保留；清除下载水印 |
| 2 | Introduction 续文；Methods；Dataset and experimental design；cohort、partitioning、4:2:4 split、missing modality assessment | 2–3 | 已保留；恢复 1–3 原生编号列表 |
| 3 | Data split sensitivity；Ethical considerations；Problem formulation；三类预处理；Batch processing；Adaptive gated fusion；公式 (1)–(4) | 3–5 | 正文、3 条模态列表及公式齐全 |
| 4 | Gating、weighted fusion、hybrid architecture、loss、evaluation；公式 (5)–(15)；Results 开头 | 5–6 | 正文与公式齐全；页末句接回下一页续文 |
| 5 | Figure 1 与题注；Experimental framework 续文 | 6–7 | 图与题注齐全；跨栏句子已接回 |
| 6 | Figure 2；fusion performance、missing modalities、cross-institutional stability | 8–9 | 图与正文齐全 |
| 7 | Figure 3、Figure 4；stability 续文；data split sensitivity | 9–10 | 两图、两题注、正文齐全 |
| 8 | Data split sensitivity 续文；Discussion | 10–11 | 正文齐全 |
| 9 | Table 1 | 12 | 原生 Word 表；全部数字逐格核对 |
| 10 | Discussion 续文；5 条 Key Points；Acknowledgments；Author contributions；Supplementary material；Conflicts of interest；Funding 开头 | 13–14 | 章节及 5 条项目符号齐全 |
| 11 | Funding 续文；Data availability；References 1–23 | 14–15 | 正文齐全；参考文献连续编号 |
| 12 | References 24–42 | 15–16 | 42 条齐全；参考文献 32 的跨栏续文已接回 |

图保留原图号次序，置于相应段落附近；原刊双栏和分页造成的断句改为连续正文。未添加原 PDF 中不存在的章节或补充材料。

## Table 1 核对

- 原生表格：12 列、36 行（1 行表头、2 行分组、22 行 split 结果、11 行变化值）。
- 列顺序：Method、Split、UCEC、LUAD、LGG、BRCA、BLCA、PAAD、COAD、READ、KIRC、GBM。
- 分组原文：`Three modality methods (text, RNA, image)`；`Two modality methods (text, image)`。
- 330 个数值格与 PDF 提取并视觉核对后的记录逐格一致：220 格均值±标准差、110 格带 ↑/↓ 的变化值。
- 21 个加粗数值格与原表一致；7:1:2 / 4:2:4 顺序保留。
- 变化值行的 Split 保持原文空白；未重新计算变化值。
- 保留原表中的方法拼写，包括 `LiMOE`、`MuIT`、`Cross Attn Fusion`；Ours 数字未替换。

## 公式与图片

| 对象 | 源 PDF 页 | Word 页 | 编辑方式 / 文件 |
|---|---|---|---|
| 公式 (1)、(2) | 3 | 4 | 原生 OMML |
| 公式 (3)、(4) | 3 | 5 | 原生 OMML |
| 公式 (5)–(9) | 4 | 5 | 原生 OMML |
| 公式 (10)–(15) | 4 | 6 | 原生 OMML；(11) 保留两行 |
| Figure 1 | 5 | 7 | `figures/fig1.png`；题注为独立 Caption 段落 |
| Figure 2 | 6 | 8 | `figures/fig2.png`；题注为独立 Caption 段落 |
| Figure 3 | 7 | 9 | `figures/fig3.png`；题注为独立 Caption 段落 |
| Figure 4 | 7 | 10 | `figures/fig4.png`；题注为独立 Caption 段落 |

共 63 个 OMML 对象：15 条编号公式、48 处行内公式。式 (12) 的原始维度标记、式 (13)/(14) 不同的系数均照录。四张图由原 PDF 对应图像边界裁出，单独嵌入且可替换；没有整页截图，也没有公式或表格截图。

## 可编辑性与最终校对

- [x] 正文为 Word 段落，可直接键入修改；没有嵌套文本框、编辑保护或扫描页。
- [x] Title、Heading 1、Heading 2、Normal、Caption、Reference 样式已设置；正文为 Times New Roman。
- [x] 参考文献为连续 1–42 的原生编号列表；正文方括号引用保留，与原文编号对应。
- [x] Table 1 数值、±、↑↓、列次序、分组和加粗逐格核对。
- [x] 15 条编号公式及行内公式保留；未见丢失或截断。
- [x] Figure 1–4 与各自题注对应，无图号错位。
- [x] 最终 16 页已渲染并逐页查看，未见正文重叠、表格溢出或文字截断。
- [x] 已检查漏段与抽取断词；未发现未解决的漏句、错数字或明显抽取错字。

仅修复 PDF 抽取引入的断词、断行和多余空格。原文可辨认但不规则的措辞照录，例如 `transparency Fourth`、`lab members of for`、`editing.Yifan`，以及参考文献 10 的 `In: In Proceedings`；没有润色或科学纠错。

## 未解决标记

| 标记 | 数量 | 位置 |
|---|---:|---|
| `[EQN-TODO]` | 0 | 无 |
| `[OCR-UNCERTAIN]` | 0 | 无 |
