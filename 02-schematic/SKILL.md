---
name: sci-schematic-editable-lite
description: 把来源材料（原始论文 PDF、figure 工单 workorder JSON、数据表、研究/流程/结构描述）画成或改成科研示意图——实验流程图、结构/层级关系图、概念或机制链条图：先从图注、正文和原图里的文字标签抽取可核对的实体—关系清单，再按关系语法（包含=嵌套分区、并列=同行同尺寸、上下游/时序=箭头方向、因果=激活/抑制）写成结构规格，脚本自动排版（分区嵌套、网格对齐、图例分栏、画布自动扩展不裁切）；图例与数据表分类严格一致并能随数据重绘；交付分层可编辑 SVG（每个元素 id + 来源）+ 自动生成的 content_map + 真实渲染 PNG/PDF + 导出参数检查 + 源文件级修改记录。精简版：标准库脚本，无安装。不用于：统计图表数值计算、海报/封面美化、艺术插画、正文写作。
---

# 科研示意图生成与编辑（精简版）

## 路径与预算
- 输入 `/input/case.json`（+ task.md 与材料，路径以 case.json 为准，先 `ls -R /input`）；工作目录 `/app/work`；交付 `/app/output`；本 Skill 在 `/skills/weekly-skill`（下文 `$S`）。环境变量 `CASE_JSON`/`WORK_DIR`/`OUT_DIR` 若存在一律优先。
- 预算 64 次请求、900 秒：目标 ≤ 25 次调用。渲染命令前加 `timeout`。只用 python 改文件，不用 `sed -i`。Python 3.8 兼容（f-string 花括号里不放反斜杠）。
- 工具：`python3 $S/scripts/svgfig.py`（build 规格→自动排版的分层 SVG + content_map；edit 改源；diff 记改动）；`python3 $S/scripts/export_check.py`（tools 探测、figtext 找图注与原图标签、render 出 PNG/PDF、check 自检）；`pixcheck.py`（可选，只给提示）。
- 任何脚本或外部工具不可用、报错：记录原因，换下一条路或跳过，不在同一步反复重试超过 2 次。

## 步骤
1. **读任务（1–2 次）**：`ls -R /input`，读 case.json 全文、task.md 的“组织方具体输入修订”，以及工单（`find /input -iname '*workorder*'`，有就 `cat`）。记下 case_id（键 `case_id`/`caseId`/`id`）、要画/改哪张图（如 figure03 → 图号 3）、图型（流程/结构/机制）、子图划分、工单里**必须出现的每一项**（must_show 一类）、导出要求（宽度 mm、dpi、格式、最小字号）、修改请求、output contract 全部字段（键可为 output_contract/outputContract/deliverables/中文；字段可为 snake/camel/中文/properties+required）。
2. **骨架（第 3 次调用以内）**：写 `/app/output/result.json`：case_id + 每个 contract 字段（先填“生成中”）+ `"status":"partial"` + `"status_reasons":["生成中"]`。同时 `timeout 60 python3 $S/scripts/export_check.py tools` 看渲染器和中文字体。骨架只是保底：check 会把残留的“生成中”判 FAIL，最后必须换成真实内容。
3. **读材料（2–4 次）**：PDF 先落盘 `pdftotext -layout f.pdf /app/work/src.txt`（无则 python fitz/pypdf，再无则记为缺口），然后 `python3 $S/scripts/export_check.py figtext /app/work/src.txt <图号>`：打印该图图注（带行号）、**原图里画着的文字标签**（矢量图的标签在 PDF 文本层里）和所有引用该图的行号。再用 `sed -n '<起>,<止>p'` 读这些引用段落和方法段（摘要、结果、方法对同一参数的说法都看一眼，矛盾常在这里）；不要把整篇 PDF 一次打印出来。文本/MD/CSV 直接读；XLSX 用 python zipfile 解 `xl/sharedStrings.xml` 与 `xl/worksheets/sheet1.xml`。出处写 `src.txt:L行号` 或 `文件:row行号`。原图是位图、没有标签可读时照实写“原图标签未读出，依据图注与正文”。材料给了现成 SVG/drawio 并要求修改：走第 8 步，不重画。
4. **实体—关系清单 `/app/work/er.md`（1 次）**：实体行 `id | 显示名 | 类型 | 所在分区(层级) | 来源 | 原文短引`；关系行 `id | from | to | 关系类型 | 依据 | 来源 | 短引`。**原图标签是金标准的名字**：图上实体的写法与 figtext 列出的标签一致（材料里的别名放 `aliases`）；原图标签里有、你没画的，要么补上，要么写进 exceptions 说明原因。工单要求而原图没有的元素（如合成酶）照工单画，src 指向正文或数据表。再加一行“数值核对”：图上要出现的数量（几个、几种）、时间、浓度、阈值，在摘要/结果/方法/图注里各写了什么；说法不一致就记 exceptions: contradiction。过下方“关系语法”；矛盾或缺失写进待确认，不自行补全。
5. **写结构规格 `/app/output/figure_spec.json` 并 build（2–3 次）**：**只写结构，不写坐标**——子图 panel → 分区 panel（`parent`）→ 节点（`comp`）；需要二维排布的分区写 `"layout":"grid"`，节点写分区内的 `col,row`（0 起）。脚本按内容自动定尺寸、嵌套、对齐，图例放在图下方并分栏，脚注 texts 排在最下，画布自动扩展、不会裁切（见“spec 示例”）。`python3 $S/scripts/svgfig.py build /app/output/figure_spec.json /app/output/figure.svg`，输出末行给出画布尺寸和最小字号（pt）。WARN（缺 src、边穿节点、连线交叉、标签溢出、图例缺项等）改结构（换 col/row、调整节点顺序、给边加 `elbow:"hv"/"vh"` 或 `via`）后再 build，最多再 build 两轮；改不掉的写进 uncertainties。`NOTE:` 行只是告知，不用处理。
6. **渲染（1 次）**：`timeout 300 python3 $S/scripts/export_check.py render /app/output/figure.svg --dpi 600`（工单要 300 dpi 就用 300）→ figure.png + figure.pdf + export_log.jsonl。脚本依次尝试 rsvg-convert / cairosvg / inkscape / chrome / magick / soffice，有一个能用就行。要 TIFF/EPS 时用 `magick figure.png figure.tiff` 或 `inkscape`/`soffice`，不可用就记缺口。全部失败照实记录，保留 SVG，不伪造预览。可在同一命令后接 `; timeout 120 python3 $S/scripts/pixcheck.py /app/output/figure.svg`（看渲染像素：标签可见、填色、图例同色，只输出 WARN）；明显问题顺手改一次，其余记录即可。
7. **来源与图注（1 次）**：`figure_source_map.md`（元素 id | 图上文字/数值/单位 | 类型 | 来源 文件:位置 | 原文短引 | 人工确认?），以 `figure_content_map.json` 为底稿用一小段 python 生成；`figure_caption.md`（图注：读图顺序、子图 a/b 含义、图例含义、只进图注不上图的信息）。
8. **源文件级编辑（2 次）**：任务或工单有修改请求就照做；没有就做一次“演示编辑”（如改一个标签措辞或把一组颜色换成图例已有的色），change_log 标“演示，不属于正式图”。自己生成的图改 spec（另存 `figure_spec_v2.json`）重建 `figure_v2.svg`（自动重排、不溢出）；改某一类别颜色就改 `canvas.categories.colors` 里那一项，图例同步变；同名实体在每个子图里都要改。材料自带 SVG 或单个属性用 `svgfig.py edit in.svg out.svg <id> --text "新标签" --set fill=#xxxxxx`（多行用 `\n`）。然后 `svgfig.py diff figure.svg figure_v2.svg > /app/output/edit_diff.json`：`changed_ids`/`content_changes` 应只含预期的文字与颜色改动（多出来的要查），`layout_only_changes` 是标签变宽引起的自动重排坐标；两者照实写进 change_log，并 render 新版本。修改请求引入材料里没有的内容：照做，uncertainties 记“来自修改请求、材料未见”，元素 src 写“修改请求”。
9. **填 result.json 并自检（2–3 次）**：按“result.json 规则”用一小段 python 填写（从 content_map、export_log、edit_diff 读，不手抄长表），运行 `python3 $S/scripts/export_check.py check`，FAIL 改到 PASS（WARN 能改就改）；再对照 `$S/resources/checklist.md`。compliance_checks 的 pass 只写图上真能看到的：build/pixcheck 有未解决的相关 WARN 时写 partial。预算快用完时先保证 result.json 没有“生成中”，再交。

## 关系语法（结构画错比画丑更致命）
| 关系 | 画法（svgfig） |
|---|---|
| 包含 / 位于 / 组成（细胞⊃膜/胞质；平台⊃模块） | 分区 panel 嵌套：内层写 `"parent":"<外层 id>"`，节点写 `"comp":"<所在分区 id>"`；脚本把它们画成框中框并写进 content_map（`contains`）。不用箭头表示包含 |
| 跨分区的层次（胞外 → 膜 → 胞质 → 核） | 父 panel 默认竖排（`"layout":"col"`）各分区，顺序 = panels 列表顺序；膜可写 `"fill":"#F2D7B6"` |
| 并列 / 同级 / 分组比较 | 同一分区、同一行（row 相同）；不加箭头 |
| 上下游 / 流程 / 时序 | `step` 箭头，单一阅读方向；步骤标签前加序号“1 …”，与材料顺序一致；流程分区用 `"layout":"row"` 或 grid |
| 物料/样本流、分化/产生 | `flow`（可 `width:3`）；合成/转录/表达 `produce`；信号、分泌因子 `signal`（虚线） |
| 磷酸化传递 / 修饰 | `phospho`（磷酸转移，方向 = 磷酸基团流向）；其他修饰 `modify` |
| 因果促进 / 抑制 | `activate` 实心箭头 / `inhibit` T 形端；“A 被 B 抑制”画 B ⊣ A |
| 结合 / 对应 / 无方向关联 | `bind`（圆点端）或 `line`（无端点） |
| 推测 / 间接 / 未验证 | 边加 `"evidence":"indirect"`（点线）或 `"hypothesis"`（点划线），图注写明证据；不把推测画成实线 |
- 图例文字默认按边类型生成；材料有更准确的说法时给该类型任一条边写 `"legend":"<图例文字>"`（如 `"legend":"phosphate flow (kinase mode)"`）。
- 层级深度与材料一致：不把子项提升为同级，不把同级画成包含。分区只框住材料说在该处的元素。边的两端也可以是 panel id（指向整组的关系）。
- 同一状态的两个版本（如低/高密度、野生型/突变体）画成两个结构相同的子图 a/b：分区与节点顺序一致，读者能逐个对比。
- 不出现材料中没有的实体、基因名、浓度、时间点、数值或单位；数值与单位原样照抄并在 src 指明位置。

## 图例与数据映射
- 一个分类 = 一种颜色，类别数 = 图例色块数；类别名与数据表原文一致；用到的每种边类型、证据线型自动进图例（写 `"legend":{"title":"Legend"}` 即可，不写坐标）。
- 分类着色来自 CSV：`"canvas":{"categories":{"csv":"/input/data/x.csv","key":"<行名列>","column":"<类别列>","colors":{"<类别>":"#009E73"},"title":"<类别名 (表名)>"}}`，节点写 `"data":"<key 列的值>"`；脚本按表逐类出色和图例，记进 content_map。可选 `"show":"<数值列>","fmt":"n = {}"` 把表中数值原样追加到标签。没有数据着色就不用。
- 颜色用色盲友好的 Okabe–Ito：#0072B2 #E69F00 #009E73 #CC79A7 #56B4E9 #D55E00 #F0E442；语义靠线型/端点区分，灰度打印可读。非数据的节点底色要在 legend.items 写 `{"fill":"#hex","label":"含义"}`。
- 期刊尺寸：`canvas.width_mm` 写工单宽度（单栏 85、双栏 180），`canvas.min_font_pt` 写工单最小字号（没写默认 6.5）；SVG/PDF 即为真实物理宽度，build 会自动放大全部文字直到最小字号达标，末行报告画布、最小字号 pt 和放大倍数。不要为了字号把子图改成竖排或删内容；出现 “figure is dense” 时才考虑每行少放节点或拆子图。

## spec 示例（全部自动排版；节点不写 cx/cy，分区不写 x/y/w/h）
```json
{"canvas":{"width_mm":180,"min_font_pt":6,"title":"<图题>","categories":{"csv":"/input/data/table1.csv","key":"<名称列>","column":"<类别列>","title":"<类别名> (Table 1)"}},
 "panels":[
  {"id":"p-a","title":"a  <子图 a 标题>","src":"src.txt:L84"},
  {"id":"a-out","parent":"p-a","title":"<外层分区，如 Extracellular>","src":"src.txt:L27"},
  {"id":"a-mem","parent":"p-a","title":"<膜/边界分区>","fill":"#F2D7B6","src":"src.txt:L27"},
  {"id":"a-cyt","parent":"p-a","title":"<内层分区，如 Cytoplasm>","layout":"grid","src":"src.txt:L27"},
  {"id":"p-b","title":"b  <子图 b 标题>","src":"src.txt:L86"}],
 "nodes":[
  {"id":"a-l1","label":"<配体>","kind":"small_molecule","comp":"a-out","data":"<表中名称>","src":"data/table1.csv:row2"},
  {"id":"a-r1","label":"<受体>","kind":"protein","comp":"a-mem","src":"src.txt:L27"},
  {"id":"a-x","label":"<中继蛋白>","kind":"protein","comp":"a-cyt","col":1,"row":0,"src":"src.txt:L29"},
  {"id":"a-y","label":"<调控子~P>","kind":"protein","comp":"a-cyt","col":1,"row":1,"src":"src.txt:L29"},
  {"id":"a-g","label":"<靶基因>","kind":"gene","comp":"a-cyt","col":0,"row":2,"src":"src.txt:L31"},
  {"id":"a-z","label":"<另一靶基因>","kind":"gene","comp":"a-cyt","col":2,"row":2,"src":"src.txt:L38"}],
 "edges":[
  {"id":"a-e1","from":"a-r1","to":"a-x","type":"phospho","src":"src.txt:L29"},
  {"id":"a-e2","from":"a-x","to":"a-y","type":"phospho","src":"src.txt:L29"},
  {"id":"a-e3","from":"a-y","to":"a-g","type":"inhibit","src":"src.txt:L31"},
  {"id":"a-e4","from":"a-y","to":"a-z","type":"activate","evidence":"hypothesis","label":"proposed","src":"src.txt:L38"}],
 "texts":[{"id":"t-note","text":"* <矛盾或证据说明，原文两处都引>","src":"src.txt:L31; L93"}],
 "legend":{"title":"Legend"}}
```
- 排版规则：顶层子图默认横排（`canvas.layout` 可改 `col`）；只含分区的 panel 竖排；只含节点的分区 ≤ 4 个横排一行，多了自动成网格；有 `row` 的节点按 grid 放（列 = col、行 = row，空格留白）。`order` 可调兄弟顺序；`gap`/`vgap` 调间距；`cols` 定网格列数。
- 想让箭头竖直：上下游节点放同一 col。边穿过别的节点时脚本先自动试 L 形折线，仍穿过才 WARN。
- 显式坐标仍可用（节点 `cx,cy,w,h`，panel `x,y,w,h`），只在局部微调时用。
- 其他键：`shape` rect|round|ellipse|circle|diamond、`fill`、`fs`、`bold`、`aliases`（同义名）；`kind` 可选：cell_type cell tissue organ organism sample material reagent condition instrument step process data concept group gene mrna protein complex small_molecule（gene/mrna 自动斜体）；边 `label`、`via:[[x,y]]`、`elbow:"hv"|"vh"`、`both`、`evidence`、`legend`；边类型 activate inhibit bind phospho produce modify transport indirect flow signal step line。中文可直接写。图上不写 id、文件名、行号。

## result.json 规则
- 必有：`case_id`、每个 contract 字段、`status`、`status_reasons`、`artifacts`（路径相对 /app/output，带 role：source/preview/export/record）、`entities` 与 `relations`（er.md 内嵌）、`source_map`（内嵌表 + `figure_source_map.md` + `figure_content_map.json`）、`data_mapping`（类别/数值 → 颜色/形状/线型 → 数据表行列；无数据编码写一句说明）、`export_checks`（格式、画布 px、width_mm、dpi、PNG 尺寸、PDF 矢量与否、字体嵌入、中文字体、最小字号 px 与 pt——取 content_map 的 `export_geometry`、色盲/灰度、渲染器）、`change_log`、`versions`（skill lite-1.3、材料文件名与 sha256、渲染器）、`uncertainties`、`material_gaps`、`needs_human_confirmation`。
- 有工单时加 `compliance_checks`：工单每一项要求一行 `{"requirement":"<原文>","result":"pass/partial/fail 选一","element_ids":["<SVG 里真实存在的 id>"],"evidence":"<怎么满足>"}`。有原图标签时再加一行“与原图标签一致”：列出原图标签中已画/未画的项。
- 字段映射按含义：要“源文件/路径”的填 `figure.svg` + spec 路径；要“导出件”的填 png/pdf 路径加 export_checks；要“来源/元素/映射”（如 content_map、source_map）的填 content_map 内容并附文件路径；要“检查/合规”的填 compliance_checks；要“异常/不确定/缺口”（如 exceptions）的按 `{"category":"material_missing/undecidable/contradiction/run_failure","detail":…,"handling":…}` 逐条写；要“修改记录”的填 change_log 内嵌表并附文件路径；看不懂的字段填最接近内容并在 `run_notes` 说明。
- 任何字段不得留空、TODO、“生成中”。**status 只写一个词**：contract 列了可选词用它的；否则 complete / partial / failed。complete = 图、预览、来源映射齐全且无未决矛盾；有缺口或待确认 = partial（原因逐条写进 status_reasons）；没出图 = failed。

## 异常处理
| 情况 | 处置 |
|---|---|
| 材料前后描述矛盾（顺序、数量、单位、天数） | 按更具体/有数据的那处画并加星号脚注（texts，不写坐标），另一处原文写进 uncertainties 与待确认 |
| 关系方向或类型没写清 | 用 `line` 或 `evidence:"hypothesis"`，图注说明，列待确认 |
| 数据表类别与文字类别对不上 | 图例按数据表；差异列为冲突；不新增类别 |
| 原图标签与正文用词不同 | 图上用原图标签，正文写法进 `aliases`，source_map 两处都引 |
| 要求的格式（EPS/TIFF/CMYK）工具不支持 | 交付可得的 SVG/PDF/PNG，缺项写 material_gaps 与 status_reasons |
| 边穿节点/连线交叉/元素过多 | 调 col/row 或顺序、加 elbow；一张子图 > 20 个节点时拆子图 |
| 无渲染器或无中文字体 | 保留 SVG，记录 export_log；改英文标签或记录方框风险；status partial |
| 脚本报错或 pixcheck 读不了 PNG | 记录原因，按上面换路或跳过，继续往下做 |

## 不做的事
不编造实体、关系、数值、单位或来源；不把推测画成确定；不用箭头表示包含；不只交位图；图上不留内部 id/文件名/TODO；不伪造渲染结果、像素检查或人工确认；不为排版删掉工单要求的结构（分区、子图、图例）。
