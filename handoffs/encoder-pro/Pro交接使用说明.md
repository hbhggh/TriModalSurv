# Pro 交接包使用说明

当前版本：v2。[版本说明](Pro证据/v2版本说明.md)明确“原型检索方法”指包含固定路由的完整方法，4/5归属于此方法整体。v1保留在旧commit及本机版本归档，不覆盖历史实验。

## 交接顺序

1. 将 [结构化Prompt](给ChatGPT-Pro的结构化Prompt.md) 作为本轮任务发送。
2. 同时提供 [先验知识](Encoder实验先验知识-Pro版.md) 和 `Pro证据/` 全部附件。ZIP只是传输容器；若网页不能读取ZIP，先本地解压，再上传MD、PDF、PNG、CSV及必要代码。
3. 要求接收者先列出已读/未能读取的证据。不假定私有GitHub链接或SVG格式一定可被网页读取；PNG是SVG的查看备份，不替代原图。
4. 只让Pro检索和筛选k1/k2及P/B；用户选择后再交Claude核验、落地。本轮跳过Gemini。

## 包内材料与优先级

| 材料 | 用途 |
| --- | --- |
| 两份Pro MD | 最新任务与事实底稿，优先于历史文档中的旧任务描述 |
| [原始需求](Pro证据/原始需求-innovation-Encoder.md) | 原始输入原样保留；已更正描述见Pro MD |
| [参考SVG](Pro证据/Framework-encoder-tabel.excalidraw.svg)／[PNG](Pro证据/Framework-encoder-tabel.png) | encoder行、五癌列的严格参考；原图“齐全”旧注释不适用 |
| [完整论文PDF](Pro证据/main.pdf)／[Table 1来源](Pro证据/table1.tex) | 指定None/Proto.†基线；完整论文其余内容不自动视为已核实事实 |
| [基线明细](Pro证据/None基线明细.md)／[CSV](Pro证据/none_baseline.csv) | 25个聚合实验读数及五癌均值；不是患者级数据 |
| [300格聚合投影](Pro证据/aggregate_rows.json) | 从原归档白名单字段抽取，可核对历史4/5，不包含患者预测 |
| [历史方法原文](Pro证据/实验先验知识与公式说明-历史原文.md) | P1–P13与历史代码路径；旧时点描述须与当前Pro版区分 |
| [代码说明](Pro证据/代码与来源说明.md) | 必要代码配置只读快照及来源，不能作为完整可运行环境 |
| [source_manifest](Pro证据/source_manifest.json) | 来源路径、来源字节哈希、当前HEAD与摘录方式 |
| [package_manifest](Pro证据/package_manifest.json) | 包内文件校验；清单不包含其自身，避免自引用 |

## 本地校验

在解压后的根目录执行：

```sh
python3 Pro证据/verify_package.py
```

仅检查文件哈希、相对导航链接、矩阵完整性、None均值与TeX对应关系；不加载模型、不联网、不训练、不评测。

## 保存与隐私

- 归档目标：私有仓库 `hbhggh/TriModalSurv`，独立分支 `encoder-pro-handoff`，目录 `handoffs/encoder-pro/`。不合并main、不改变可见性。
- 上传对象只有本包。无患者级预测、TCGA患者ID清单、原始RNA/文本/WSI、特征缓存、checkpoint或凭证。
- 用户授权包含完整未发表论文；上传ChatGPT附件是用户后续自行操作，本次未打开或发送网页对话。
- 固定commit链接与ZIP SHA见本机 `Pro交付核验.md`，该收据位于包外，避免commit/hash自引用。
- v2中的PDF、TeX摘录和方法原文保持v1证据字节；本机main.tex后续编辑单独记录，不被本包静默替换。接收者以新Pro文档理解术语，以源快照核对实际实现。
