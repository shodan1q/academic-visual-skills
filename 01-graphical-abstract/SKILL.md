---
name: graphical-abstract-lite
description: 依据论文/研究描述、实验记录和源数据（txt/md/pdf/csv/xlsx）制作单页 Graphical Abstract（图形摘要）：先做“面板—要点”映射（研究问题→方法→核心结果→结论，哪些上图、哪些只进图注），科学实体与空间/因果关系按材料摆放，核心结果用真实源数据编码（柱长=数值，带单位与误差），图例、单位、比例尺齐全、色盲友好；交付分层可编辑 SVG（每个元素 id + 来源）+ 真实渲染 PNG/PDF + 来源映射 + 导出检查 + 源文件级修改记录。精简版：标准库脚本，无安装。不用于：正文写作、统计分析、实验设计、纯装饰插画。
---

# Graphical Abstract 图形摘要（精简版）

## 路径与预算
- 输入 `/input/case.json`（+ task.md 与材料，路径以 case.json 为准，先 `ls -R /input`）；工作目录 `/app/work`；交付 `/app/output`；本 Skill 在 `/skills/weekly-skill`（下文 `$S`）。环境变量 `CASE_JSON`/`WORK_DIR`/`OUT_DIR` 若存在一律优先。
- 预算 64 次请求、900 秒：目标 ≤ 30 次调用。渲染命令前加 `timeout`。只用 python 改文件，不用 `sed -i`。Python 3.8 兼容（f-string 花括号里不放反斜杠）。
- 工具：`python3 $S/scripts/svgfig.py`（build 规格→SVG，含 bars 数据小图；edit 改源；diff 记改动）；`python3 $S/scripts/export_check.py`（tools 探测、render 出 PNG/PDF、check 自检）。

## 步骤
1. **读任务（1–2 次）**：读 case.json 全文和 task.md 的“组织方具体输入修订”。记下 case_id（键 `case_id`/`caseId`/`id`）、画布尺寸/比例/格式/dpi/语言要求（未给时用 1200×700 px 横版；写明 Elsevier 时用 1328×531 px 以上）、是否有修改请求、output contract 全部字段（键可为 output_contract/outputContract/deliverables/中文；字段可为 snake/camel/中文/properties+required）。
2. **骨架（第 3 次调用以内）**：写 `/app/output/result.json`：case_id + 每个 contract 字段（先填一句“生成中”）+ `"status":"partial"` + `"status_reasons":["生成中"]`。同时 `timeout 60 python3 $S/scripts/export_check.py tools` 看渲染器和中文字体。
3. **读全部材料（2–5 次）**：文本/MD/CSV 直接读；PDF 用 `pdftotext -layout f.pdf -`（无则 python fitz/pypdf，再无则记缺口）；XLSX 用 python zipfile 解 `xl/sharedStrings.xml` 与 `xl/worksheets/sheet1.xml`。**图上要用的数值必须从数据文件读出**（记下文件、行、列），不从摘要文字里抄近似值；两者不一致记为冲突。图片读不了写“未读出”。
4. **面板—要点映射 `/app/work/panel_map.md`（1–2 次）**：
   - 四个面板：①研究问题 ②方法/路线 ③核心结果 ④结论。每个面板列 1–3 个要点：`要点 | 上图形式(实体/箭头/柱/文字) | 来源 文件:行 | 原文短引`。
   - 实体表：`id | 名称（照抄）| 类型(分子/细胞/组织/材料/器件/样本/人群) | 位置/层级 | 尺度 | 来源`；关系表：`from | to | 类型(作用/处理/产生/抑制/包含) | 方向依据 | 来源`。
   - “只进图注”清单：统计细节、样本量、次要结果、限定条件——放进 `figure_caption.md`，不挤上图。
   - 结论措辞强度与证据一致：材料只说“相关/提示”就不写“证明/导致”。
5. **写规格 `/app/output/figure_spec.json` 并 build（2–4 次）**：用一小段 python 读源数据生成 `bars` 项（value、err、单位、src=文件:行），再写其余 panels/nodes/edges/texts/legend，`python3 $S/scripts/svgfig.py build /app/output/figure_spec.json /app/output/figure.svg`。所有 WARN（缺 src、溢出、边穿节点、无图例、负值）改到消失或写进 uncertainties。
6. **数据回读 + 渲染（1–2 次）**：`python3 -c "import xml.etree.ElementTree as E;[print(e.get('id'),e.get('data-value'),e.get('height')) for e in E.parse('/app/output/figure.svg').iter() if e.get('data-value')]"`，逐项与数据文件比对（高度/数值比例应一致），结果写进 data_mapping。然后 `timeout 300 python3 $S/scripts/export_check.py render /app/output/figure.svg --dpi 300` → figure.png + figure.pdf + export_log.jsonl。失败照实记录，不伪造预览。
7. **来源与图注（1–2 次）**：`figure_source_map.md`（元素 id | 图上文字/数值/单位 | 面板 | 来源 文件:位置 | 原文短引 | 人工确认?），以 `figure_elements.tsv` 为底稿；`figure_caption.md`（一句话主旨、四面板读图顺序、图例与单位、误差含义、只进图注的信息）。
8. **源文件级编辑**：有修改请求就照做；没有就做一次“演示编辑”（如改结论措辞或某面板标题），另存并在 change_log 标“演示，不属于正式图”。优先改 spec（另存 `figure_spec_v2.json`）重建 `figure_v2.svg`；材料自带 SVG 或单个属性用 `svgfig.py edit in.svg out.svg <id> --text "新文字" --set fill=#xxxxxx`（多行用 `\n`）。然后 `svgfig.py diff 旧.svg 新.svg` 写进 change_log，并 render 新版本。
9. **填 result.json 并自检（2–3 次）**：按“result.json 规则”填写，运行 `python3 $S/scripts/export_check.py check`，FAIL 改到 PASS；再对照 `$S/resources/checklist.md`。

## 版式与编码规则
- **阅读顺序**：四个 panel 左→右（横版）或 Z 形 2×2，标题带序号“1 问题 / 2 方法 / 3 结果 / 4 结论”（语言随任务）；panel 之间用 `step` 箭头串起主线；视觉焦点给核心结果（最大面板或强调色）。
- **实体与空间关系**：层级（分子 ⊂ 细胞 ⊂ 组织；样本 → 处理 → 测量）用嵌套或上下位置表达；作用方向用边类型（activate 促进、inhibit 抑制、transport 转移/递送、flow 物料/样本流、step 流程、indirect 推测）；示意尺寸不按比例时在图注写“示意，未按比例”；材料有尺度/比例尺时用 `line` 边画比例尺并标注数值与单位。
- **数据编码**：核心数值只用一种主通道（柱长，`bars`），柱从 0 开始，单位写在 `unit` 或标题；误差 `err` 的含义（SD/SEM/CI）写进图注；组名与数据表一致；不同组用色盲友好色（#0072B2 #E69F00 #009E73 #CC79A7 #56B4E9 #D55E00），并靠标签区分以便灰度打印。负值或对数数据不适合 bars，改用文字数值并说明。
- **图例**：每种边类型、每种填充色、每个数据系列都进 legend，文字说明含义与单位。
- **文字**：标题 ≤ 15 词，每个面板 ≤ 25 词；字号 ≥ 12 px（标题 20–24）；中文可直接写（字体栈含 CJK）。图上不写 id、文件名、行号、TODO。
- 不出现材料里没有的实体、数值、单位、p 值或结论。

## spec 示例（节点 cx/cy 为中心；panel/bars/legend 的 x/y 为左上角）
```json
{"canvas":{"w":1200,"h":700,"title":"<一句话主旨，来自材料>","src":"materials/abs.md:L1"},
 "panels":[{"id":"p1-problem","x":20,"y":60,"w":270,"h":560,"title":"1 <问题>","src":"materials/abs.md:L2"},
  {"id":"p2-method","x":315,"y":60,"w":270,"h":560,"title":"2 <方法>","src":"materials/methods.md:L4"},
  {"id":"p3-result","x":610,"y":60,"w":330,"h":560,"title":"3 <核心结果>","fill":"#FFF8EC","src":"materials/data.csv"},
  {"id":"p4-concl","x":965,"y":60,"w":215,"h":560,"title":"4 <结论>","src":"materials/abs.md:L9"}],
 "nodes":[{"id":"n-sample","label":"<样本/对象>","cx":155,"cy":260,"shape":"ellipse","w":180,"h":80,"src":"materials/abs.md:L3"},
  {"id":"n-treat","label":"<处理/方法>","cx":450,"cy":260,"w":200,"h":70,"src":"materials/methods.md:L5"},
  {"id":"n-concl","label":"<结论句，强度同证据>","cx":1072,"cy":300,"w":180,"h":160,"shape":"round","src":"materials/abs.md:L9"}],
 "edges":[{"id":"e-12","from":"n-sample","to":"n-treat","type":"step","src":"materials/methods.md:L5"}],
 "bars":[{"id":"c-main","x":630,"y":150,"w":290,"h":300,"title":"<指标>","unit":"<单位>",
   "items":[{"label":"<对照>","value":1.0,"err":0.1,"src":"materials/data.csv:row2"},{"label":"<处理>","value":2.0,"err":0.2,"color":"#D55E00","src":"materials/data.csv:row3"}]}],
 "texts":[{"id":"t-n","text":"<n 与误差含义，若必须上图>","x":630,"y":600,"fs":12,"src":"materials/data.csv"}],
 "legend":{"x":630,"y":470,"items":[{"edge":"step","label":"<研究流程>"},{"fill":"#D55E00","label":"<处理组>"}]}}
```
其他键：`shape` rect|round|band|ellipse|circle|diamond、`fill`、`fs`、`bold`、`italic`（基因名斜体）；边 `via`、`elbow`、`label`、`from/to` 也可是 `[x,y]` 坐标（画比例尺、指示线）；bars 的 `max` 固定刻度上限、`text` 覆盖数值标签。

## result.json 规则
- 必有：`case_id`、每个 contract 字段、`status`、`status_reasons`、`artifacts`（路径相对 /app/output，带 role：source/preview/export/record）、`panel_map`（四面板要点 + 只进图注清单，内嵌）、`entities`、`relations`、`source_map`（内嵌表 + `figure_source_map.md`）、`data_mapping`（每根柱：组、数值、误差及含义、单位、通道=长度、数据文件行列、回读高度是否一致）、`export_checks`（格式、画布 px、dpi、PNG 尺寸、PDF 矢量与否、字体嵌入、中文字体、最小字号、色盲/灰度、渲染器）、`change_log`、`versions`（skill lite-1.0、材料文件名、渲染器）、`uncertainties`、`material_gaps`、`needs_human_confirmation`。
- 字段映射按含义：要“源文件/路径”的填 svg + spec 路径；要“导出件”的填 png/pdf 路径加 export_checks；要“来源/修改记录”的填 source_map + change_log 内嵌表并附文件路径；看不懂的字段填最接近内容并在 `run_notes` 说明。
- 任何字段不得留空、TODO、“生成中”。**status 只写一个词**：contract 列了可选词用它的；否则 complete / partial / failed。complete = 四要素齐全、预览与来源映射齐全且无未决冲突；有缺口或待确认 = partial（原因逐条写进 status_reasons）；没出图 = failed。

## 异常处理
| 情况 | 处置 |
|---|---|
| 缺关键数值（只有“显著提高”无数据） | 结果面板用文字陈述+“数值未提供”，不画柱；列 material_gaps，status partial |
| 摘要文字与数据表数值不一致 | 图按数据表，冲突写 uncertainties 与待确认 |
| 实体名歧义（缩写、基因/蛋白） | 照抄材料原写法，列待确认 |
| 要点太多、文字溢出、画布超限 | 次要要点移到图注；缩短措辞；仍溢出再加大画布 |
| 无渲染器 / 渲染失败 / 无中文字体 | 保留 SVG，记录 export_log；改英文或记录方框风险；status partial |

## 不做的事
不编造数值、实体、关系或结论；不把相关画成因果；不用装饰图标替代材料中的实体；不只交位图；图上不留内部 id/文件名/TODO；不伪造渲染结果或人工确认。
