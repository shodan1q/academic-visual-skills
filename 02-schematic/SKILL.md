---
name: sci-schematic-editable-lite
description: 把来源材料（原始论文 PDF、figure 工单 workorder JSON、数据表、研究/流程/结构描述）画成或改成科研示意图——实验流程图、结构/层级关系图、概念或机制链条图：先抽取可核对的实体—关系清单，再按关系语法（包含=嵌套、并列=对齐同级、上下游/时序=箭头方向、因果=激活/抑制）布局；图例与数据表分类严格一致并能随数据重绘；交付分层可编辑 SVG（每个元素 id + 来源）+ 自动生成的 content_map + 真实渲染 PNG/PDF + 导出参数检查 + 源文件级修改记录。精简版：标准库脚本，无安装。不用于：统计图表数值计算、海报/封面美化、艺术插画、正文写作。
---

# 科研示意图生成与编辑（精简版）

## 路径与预算
- 输入 `/input/case.json`（+ task.md 与材料，路径以 case.json 为准，先 `ls -R /input`）；工作目录 `/app/work`；交付 `/app/output`；本 Skill 在 `/skills/weekly-skill`（下文 `$S`）。环境变量 `CASE_JSON`/`WORK_DIR`/`OUT_DIR` 若存在一律优先。
- 预算 64 次请求、900 秒：目标 ≤ 30 次调用。渲染命令前加 `timeout`。只用 python 改文件，不用 `sed -i`。Python 3.8 兼容（f-string 花括号里不放反斜杠）。
- 工具：`python3 $S/scripts/svgfig.py`（build 规格→SVG + content_map、edit 改源、diff 记改动）；`python3 $S/scripts/export_check.py`（tools 探测、render 出 PNG/PDF、check 自检）；`pixcheck.py`（可选，只给提示）。
- 任何脚本或外部工具不可用、报错：记录原因，换下一条路或跳过，不在同一步反复重试超过 2 次。

## 步骤
1. **读任务（1–2 次）**：`ls -R /input`，读 case.json 全文、task.md 的“组织方具体输入修订”，以及工单（`find /input -iname '*workorder*'`，有就 `cat`）。记下 case_id（键 `case_id`/`caseId`/`id`）、图型（流程/结构/机制）、要画/改哪张图、工单里**必须出现的每一项**（must_show 一类）、目标尺寸（宽度 mm、dpi、格式、最小字号）、修改/编辑请求、output contract 全部字段（键可为 output_contract/outputContract/deliverables/中文；字段可为 snake/camel/中文/properties+required）。
2. **骨架（第 3 次调用以内）**：写 `/app/output/result.json`：case_id + 每个 contract 字段（先填“生成中”）+ `"status":"partial"` + `"status_reasons":["生成中"]`。同时 `timeout 60 python3 $S/scripts/export_check.py tools` 看渲染器和中文字体。骨架只是保底：check 会把残留的“生成中”判 FAIL，最后必须换成真实内容。
3. **读材料（2–5 次）**：PDF 先落盘 `pdftotext -layout f.pdf /app/work/src.txt`（无则 python fitz/pypdf，再无则记为缺口），再 `grep -n -i -E "fig(ure)?\.? ?3|<工单关键词>" /app/work/src.txt` 定位图注、对应结果段和方法段，用 `sed -n '<起>,<止>p'` 读这些段落（摘要、结果、方法对同一参数的说法都看一眼，矛盾常在这里）；不要把整篇 PDF 一次打印出来。文本/MD/CSV 直接读；XLSX 用 python zipfile 解 `xl/sharedStrings.xml` 与 `xl/worksheets/sheet1.xml`。出处写 `src.txt:L行号` 或 `文件:row行号`。图片读不了就写“未读出”，不猜内容。材料给了现成 SVG/drawio 并要求修改：走第 8 步，不重画。
4. **实体—关系清单 `/app/work/er.md`（1–2 次）**：实体行 `id | 显示名 | 类型 | 属性(数量/尺寸/条件/单位) | 所属分组/层级 | 来源 | 原文短引`；关系行 `id | from | to | 关系类型(包含/并列/上下游/时序/因果+/因果−/结合/对应) | 依据 | 来源 | 短引`。过下方“关系语法”；矛盾或缺失写进待确认，不自行补全。
5. **写规格 `/app/output/figure_spec.json` 并 build（2–4 次）**：`python3 $S/scripts/svgfig.py build /app/output/figure_spec.json /app/output/figure.svg`（spec 即可编辑源；同时生成 `figure_content_map.json`：实体、关系、由嵌套导出的包含关系、图例、数据映射，各带 src）。分类着色来自数据表时用 `canvas.categories` 让脚本读 CSV（见“图例与数据映射”），不手抄颜色和数字。WARN（缺 src、标签溢出、边穿节点、节点不在所属组内、图例缺项等）能改就改，最多再 build 两轮；改不掉的写进 uncertainties。`NOTE:` 行只是建议，可忽略。
6. **渲染（1 次）**：`timeout 300 python3 $S/scripts/export_check.py render /app/output/figure.svg --dpi 300`（工单/期刊要 600 dpi 就用 600）→ figure.png + figure.pdf + export_log.jsonl。脚本会依次尝试 rsvg-convert / cairosvg / inkscape / chrome / magick / soffice，有一个能用就行。要 TIFF/EPS 时用 `magick figure.png figure.tiff` 或 `inkscape`/`soffice`，不可用就记缺口。全部失败照实记录，保留 SVG，不伪造预览。可选：同一命令后接 `; timeout 120 python3 $S/scripts/pixcheck.py /app/output/figure.svg`，它看渲染像素（标签是否可见、填色、图例同色），只输出 WARN；明显问题（标签看不见）顺手改一次，其余记录即可，不为它循环。
7. **来源与图注（1–2 次）**：`figure_source_map.md`（元素 id | 图上文字/数值/单位 | 类型 | 来源 文件:位置 | 原文短引 | 人工确认?），以 `figure_content_map.json` 为底稿用一小段 python 生成；`figure_caption.md`（图注：读图顺序、子图编号、图例含义、只进图注不上图的信息）。
8. **源文件级编辑**：任务或工单有修改请求就照做；没有就做一次“演示编辑”（如改一个标签措辞或把一组颜色换成图例已有的色），change_log 标“演示，不属于正式图”。自己生成的图优先改 spec（另存 `figure_spec_v2.json`）重建 `figure_v2.svg`（重新换行、查溢出）；改某一类别颜色就改 `canvas.categories.colors` 里那一项，图例同步变。材料自带 SVG 或单个属性用 `svgfig.py edit in.svg out.svg <id> --text "新标签" --set fill=#xxxxxx`（多行用 `\n`）。然后 `svgfig.py diff figure.svg figure_v2.svg > /app/output/edit_diff.json` 写进 change_log，并 render 新版本。修改请求引入材料里没有的内容：照做，uncertainties 记“来自修改请求、材料未见”，元素 src 写“修改请求”。
9. **填 result.json 并自检（2–3 次）**：按“result.json 规则”用一小段 python 填写（从 content_map、export_log、edit_diff 读，不手抄长表），运行 `python3 $S/scripts/export_check.py check`，FAIL 改到 PASS（WARN 能改就改）；再对照 `$S/resources/checklist.md`。预算快用完时先保证 result.json 没有“生成中”，再交。

## 关系语法（结构画错比画丑更致命）
| 关系 | 画法（svgfig） |
|---|---|
| 包含 / 属于 / 组成（器官⊃组织⊃细胞；平台⊃模块） | 外层 `panels` 嵌套内层 panel（内层写 `"parent":"<外层 id>"`）或 nodes（写 `"comp":"<所属 panel id>"`），内层完全落在外层矩形内；不用箭头表示包含 |
| 并列 / 同级 / 分组比较 | 同一行或同一列、同尺寸、同形状（用 `canvas.grid` + `col,row`），不加箭头 |
| 上下游 / 流程 / 时序 | `step` 箭头，单一阅读方向（左→右或上→下）；步骤在标签前加序号“1 …”，序号与材料顺序一致 |
| 物料/样本流、分化/产生 | `flow`（粗实线，可用 `width:3`），标签写原文动词；信息/信号、分泌因子 `signal`（虚线），标签写因子名 |
| 因果促进 / 抑制 | `activate` 实心箭头 / `inhibit` T 形端；“A 被 B 抑制”画 B ⊣ A |
| 结合 / 对应 / 无方向关联 | `bind`（圆点端）或 `line`（无端点），图注说明无方向 |
| 推测 / 间接 / 未验证 | 边加 `"evidence":"indirect"`（点线）或 `"hypothesis"`（点划线），图注写明证据；不把推测画成实线 |
- 层级深度与材料一致：不把子项提升为同级，不把同级画成包含。分组边界（panel）只框住材料说同组的元素。边的两端也可以是 panel id（指向整组的关系）。
- 不出现材料中没有的实体、基因名、浓度、时间点、数值或单位；数值与单位原样照抄并在 src 指明位置。
- 多子图时 panel 标题用 “a”“b” 前缀，子图编号与图注一致。

## 图例与数据映射
- 一个分类 = 一种颜色（或形状），类别数 = 图例色块数；类别名与数据表原文一致；用到的每种边类型也进图例（只写 `legend:{x,y,title}` 时脚本会按用到的边类型、证据强度、数据类别自动补齐）。
- 分类着色来自 CSV：`"canvas":{"categories":{"csv":"/input/data/x.csv","key":"<行名列>","column":"<类别列>","colors":{"<类别>":"#009E73"},"title":"<类别名 (表名)>"}}`，节点写 `"data":"<key 列的值>"`；脚本按表逐类出色和图例，记进 content_map。可选 `"show":"<数值列>","fmt":"n = {}"` 把表中数值原样追加到标签。没有数据着色就不用。
- 颜色用色盲友好的 Okabe–Ito：#0072B2 #E69F00 #009E73 #CC79A7 #56B4E9 #D55E00 #F0E442；语义靠形状/线型区分，灰度打印可读。非数据的分组底色在 legend.items 写 `{"fill":"#hex","label":"含义"}`。
- 期刊尺寸：在 `canvas` 里写 `"width_mm": D`，SVG/PDF 即为真实物理宽度。有效字号 pt = 字号px × (D×3.78/W) × 0.75，须 ≥ 6–7 pt：单栏 85 mm 画布宽 W ≈ 340–420 px、字号 ≥ 12 px；双栏 180 mm 画布宽 ≈ 700–850 px、字号 ≥ 11 px。计算写进 export_checks。

## spec 示例（节点 cx/cy 为中心；panel/legend 的 x/y 为左上角）
```json
{"canvas":{"w":1000,"h":560,"width_mm":180,"title":"<图题>","grid":{"x0":140,"y0":180,"dx":240,"dy":150}},
 "panels":[{"id":"p-a","x":20,"y":60,"w":960,"h":250,"title":"a  <分组/层级名>","src":"src.txt:L2"}],
 "nodes":[{"id":"n-s1","label":"1 <步骤1>","kind":"step","comp":"p-a","col":0,"row":0,"src":"src.txt:L3"},
  {"id":"n-s2","label":"2 <步骤2>","kind":"step","comp":"p-a","col":1,"row":0,"fill":"#56B4E9","src":"src.txt:L4"},
  {"id":"n-s3","label":"3 <步骤3>","kind":"step","comp":"p-a","col":2,"row":0,"shape":"diamond","w":160,"h":80,"src":"src.txt:L5"}],
 "edges":[{"id":"e-12","from":"n-s1","to":"n-s2","type":"step","src":"src.txt:L3-4"},
  {"id":"e-23","from":"n-s2","to":"n-s3","type":"flow","width":3,"label":"<物料/条件>","src":"src.txt:L4"}],
 "texts":[{"id":"t-unit","text":"<单位或条件注>","x":30,"y":545,"fs":12,"src":"src.txt:L6"}],
 "legend":{"x":40,"y":340,"title":"Legend","items":[{"edge":"step","label":"<步骤顺序>"},{"fill":"#56B4E9","label":"<类别名>"}]}}
```
其他键：`shape` rect|round|band|ellipse|circle|diamond、`fill`、`fs`、`bold`、`aliases`（同义名）；`kind` 可选：cell_type cell tissue organ organism sample material reagent condition instrument step process data concept group gene mrna protein complex small_molecule（gene/mrna 自动斜体）；边 `via:[[x,y]]`、`elbow:"hv"|"vh"`、`both`、`evidence`；边类型 activate inhibit bind modify transport indirect flow signal step line。中文可直接写。图上不写 id、文件名、行号。

## result.json 规则
- 必有：`case_id`、每个 contract 字段、`status`、`status_reasons`、`artifacts`（路径相对 /app/output，带 role：source/preview/export/record）、`entities` 与 `relations`（er.md 内嵌）、`source_map`（内嵌表 + `figure_source_map.md` + `figure_content_map.json`）、`data_mapping`（类别/数值 → 颜色/形状/线型 → 数据表行列；无数据编码写一句说明）、`export_checks`（格式、画布 px、dpi、PNG 尺寸、PDF 矢量与否、字体嵌入、中文字体、最小字号及换算 pt、色盲/灰度、渲染器）、`change_log`、`versions`（skill lite-1.2、材料文件名与 sha256、渲染器）、`uncertainties`、`material_gaps`、`needs_human_confirmation`。
- 有工单时加 `compliance_checks`：工单每一项要求一行 `{"requirement":"<原文>","result":"pass/partial/fail 选一","element_ids":["<SVG 里真实存在的 id>"],"evidence":"<怎么满足>"}`。
- 字段映射按含义：要“源文件/路径”的填 `figure.svg` + spec 路径；要“导出件”的填 png/pdf 路径加 export_checks；要“来源/元素/映射”（如 content_map、source_map）的填 content_map 内容并附文件路径；要“检查/合规”的填 compliance_checks；要“异常/不确定/缺口”（如 exceptions）的按 `{"category":"material_missing/undecidable/contradiction/run_failure","detail":…,"handling":…}` 逐条写；要“修改记录”的填 change_log 内嵌表并附文件路径；看不懂的字段填最接近内容并在 `run_notes` 说明。
- 任何字段不得留空、TODO、“生成中”。**status 只写一个词**：contract 列了可选词用它的；否则 complete / partial / failed。complete = 图、预览、来源映射齐全且无未决矛盾；有缺口或待确认 = partial（原因逐条写进 status_reasons）；没出图 = failed。

## 异常处理
| 情况 | 处置 |
|---|---|
| 材料前后描述矛盾（顺序、数量、单位、天数） | 按更具体/有数据的那处画并加星号脚注，另一处原文写进 uncertainties 与待确认 |
| 关系方向或类型没写清 | 用 `line` 或 `evidence:"hypothesis"`，图注说明，列待确认 |
| 数据表类别与文字类别对不上 | 图例按数据表；差异列为冲突；不新增类别 |
| 要求的格式（EPS/TIFF/CMYK）工具不支持 | 交付可得的 SVG/PDF/PNG，缺项写 material_gaps 与 status_reasons |
| 标签溢出/边穿节点/元素过多 | 调尺寸、坐标、via；元素 > 25 时拆子图 a/b |
| 无渲染器或无中文字体 | 保留 SVG，记录 export_log；改英文标签或记录方框风险；status partial |
| 脚本报错或 pixcheck 读不了 PNG | 记录原因，按上面换路或跳过，继续往下做 |

## 不做的事
不编造实体、关系、数值、单位或来源；不把推测画成确定；不用箭头表示包含；不只交位图；图上不留内部 id/文件名/TODO；不伪造渲染结果、像素检查或人工确认。
