---
name: apparatus-route-figure-lite
description: 把装置清单、装配说明、方法段落、工艺步骤或研究计划画成实验装置图、工艺流程图或技术路线图：先抽“部件—接口—连接—步骤—流向—阶段”结构化清单，再按规则布图（编号与正文一致、并行支路、回流与终止条件、物料/能量/信息流用不同颜色线型、阶段与里程碑的依赖）；不凭空补连接；交付分层可编辑 SVG（每个元素 id + 来源）+ 真实渲染 PNG/PDF + 来源映射 + 源文件级修改记录。精简版：标准库脚本，无安装。不用于：数据分析拟合、判断方案是否合理、论文排版。
---

# 实验装置与技术路线图（精简版）

## 路径与预算
- 输入 `/input/case.json`（+ task.md 与材料，路径以 case.json 为准，先 `ls -R /input`）；工作目录 `/app/work`；交付 `/app/output`；本 Skill 在 `/skills/weekly-skill`（下文 `$S`）。环境变量 `CASE_JSON`/`WORK_DIR`/`OUT_DIR` 若存在一律优先。
- 预算 64 次请求、900 秒：目标 ≤ 25 次调用。脚本每次结尾打印 `[elapsed N s]`：超过 600 s 就跳过可选步骤（第二轮美化、第 7 步图注细节），直接第 9 步；超过 780 s 只做 `fill` + 写完 result.json。渲染命令前加 `timeout`。只用 python 改文件，不用 `sed -i`。Python 3.8 兼容（f-string 花括号里不放反斜杠）。每次回复只写一个文件，单个 spec / 脚本控制在约 8 KB 内。
- 工具：`python3 $S/scripts/svgfig.py`（build 规格→SVG、edit 改源、diff 记改动）；`python3 $S/scripts/export_check.py`（init 骨架+探测、pdf 抽文本、render 出 PNG/PDF、fill 回填、check 自检）。脚本不会抛出 traceback；输出里的 FAIL/WARN 是要处理的内容。

## 步骤
1. **读任务（1–2 次）**：读 case.json 全文和 task.md 的“组织方具体输入修订”。记下 case_id（键 `case_id`/`caseId`/`id`）、要画的图型（装置图 / 步骤流程图 / 技术路线图，可能多个）、画布/格式/语言要求、是否有修改请求、output contract 全部字段（键可为 output_contract/outputContract/deliverables/中文；字段可为 snake/camel/中文/properties+required）。
2. **骨架（第 3 次调用以内，一条命令）**：`timeout 60 python3 $S/scripts/export_check.py init` —— 从 case.json 写 `/app/output/result.json` 骨架（case_id + 每个 contract 字段填“生成中” + `"status":"partial"`），已有合法 result.json 则不动；同时打印渲染器和中文字体。骨架只是中途被截断时的保底，“生成中”到第 9 步必须全部换成真实内容。
3. **读全部材料（2–5 次）**：文本/MD/CSV 直接读；PDF 用 `timeout 240 python3 $S/scripts/export_check.py pdf f.pdf --grep "apparatus|pump|chamber|perfus|setup|device|step|stage|workflow|fig(ure)?\.? ?3|装置|步骤|阶段"`（落盘到 `/app/work/<名>.txt`，打印页数、章节/图注行号地图和命中行；内部按 pdftotext → fitz → pypdf 回退，带超时），再用 `sed -n 'A,Bp' /app/work/<名>.txt` 读方法段、图注和对应结果段（每次 ≤ 120 行）；**不要把整篇 PDF 一次打印出来**；抽不出文本记缺口；XLSX 用 python zipfile 解 `xl/sharedStrings.xml` 与 `xl/worksheets/sheet1.xml`。图片读不了写“未读出”。材料给了现成 SVG/drawio 并要求修改：走第 8 步，不重画。
4. **结构化清单 `/app/work/ir.md`（1–2 次）**，每类一张表，每行带 `来源 文件:行 | 原文短引`：
   - 部件：`id | 名称（照抄）| 数量 | 型号/参数/单位 | 接口(入口/出口)`；同类多件分别编号（泵 1、泵 2）。
   - 连接：`id | from 部件.接口 | to 部件.接口 | 介质(液/气/电/热/信号/废料) | 方向依据`。**材料没写的连接不画**，列入 material_gaps。
   - 步骤：`编号(与正文一致) | 动作 | 条件(温度/时间/转速，照抄) | 下一步 | 并行/循环/终止条件`。
   - 阶段（技术路线）：`阶段 | 目标 | 方法 | 输入 | 输出/里程碑 | 依赖的前序阶段`。
5. **写规格 `/app/output/figure_spec.json` 并 build（2–4 次）**：`python3 $S/scripts/svgfig.py build /app/output/figure_spec.json /app/output/figure.svg`（spec 即可编辑源，同时生成 `figure_elements.tsv`）。需要两张图（如装置 + 路线）就各写一个 spec（figure_apparatus / figure_route）。所有 WARN（缺 src、溢出、边穿部件、无图例、未知 id）改到消失或写进 uncertainties。
6. **渲染（1 次，所有图一起）**：`timeout 260 python3 $S/scripts/export_check.py render /app/output/figure.svg [第二张图.svg] --dpi 300` → 每张图 PNG + PDF + export_log.jsonl（每个渲染器 ≤ 60 s，整条命令约 ≤ 200 s，卡死过的渲染器本次运行内不再尝试）。末行 `RENDER INCOMPLETE` 时最多重试一次（如修好 XML 后），之后照实记录、保留 SVG，不伪造预览。
7. **来源与图注（1–2 次）**：`figure_source_map.md`（元素 id | 图上文字/参数 | 类型 | 来源 文件:位置 | 原文短引 | 人工确认?），以 `figure_elements.tsv` 为底稿；`figure_caption.md`（图注：读图顺序、编号与正文段落对照表、图例含义、只进图注的参数）。
8. **源文件级编辑**：有修改请求就照做；没有就做一次“演示编辑”（如改一个部件标签或给某条流线换成图例已有颜色），另存并在 change_log 标“演示，不属于正式图”。自己生成的图优先改 spec（另存 `figure_spec_v2.json`）重建 `figure_v2.svg`；材料自带 SVG 或单个属性用 `svgfig.py edit in.svg out.svg <id> --text "新标签" --set stroke=#xxxxxx`（多行用 `\n`）。然后 `python3 $S/scripts/svgfig.py diff 旧.svg 新.svg > /app/output/figure_edit_diff.json`（fill 会把它写进 change_log），并 `timeout 200 python3 $S/scripts/export_check.py render <新版本.svg>`。两张图时只对一张做演示编辑。
9. **填 result.json 并自检（2–3 次）**：先 `python3 $S/scripts/export_check.py fill`（从磁盘回填空着的 artifacts / export_checks / source_map / change_log / versions，不覆盖已写内容），再用一小段 python（`json.load` → `update` → `json.dump(..., ensure_ascii=False)`）按“result.json 规则”写其余字段，然后 `python3 $S/scripts/export_check.py check`。FAIL 最多改两轮；仍改不掉的写进 status_reasons，status 用 partial，结束。再对照 `$S/resources/checklist.md`。

## 画图规则
**装置图**
- 部件名称、数量与 ir.md 完全一致；同类部件用相同形状、不同编号；容器/反应器用 `round` 或 `ellipse`，泵/阀等小部件用 `circle`（w=h≈60），仪器/控制器用 `rect`，判断/切换用 `diamond`。
- 每条连接一条边，from/to 按介质流动方向；介质 → 边类型与颜色固定：液体 `flow` #0072B2、气体 `flow` + `"color":"#009E73"`、热/能量 `flow` + `"color":"#D55E00"`、电/控制信号 `signal`（虚线 #E08214）、废料/排出 `flow` + `"color":"#777777"`。参数（流速、温度、电压）作边或部件标签，原样带单位。
- 管路用 `elbow` 或 `via` 走直角，不穿过其他部件；分流/合流画成从同一部件出发的多条边，回流边从侧面 `via` 绕回并标“回流”。
**步骤流程图**
- 主序列单方向（上→下或左→右），节点标签以正文编号开头（“1 …”“2 …”），编号与正文逐条对应；并行支路用 3a/3b 同行并排；循环用 `via` 回到起点并在边标签写次数或条件（照抄）；终止/判断用 `diamond`，出边标签写“是/否”或条件。
**技术路线图**
- 阶段 = 从左到右的列（`panels`，标题“阶段 1 …”），每列内自上而下放 目标 → 方法 → 输出/里程碑（节点）；阶段间依赖用 `step` 箭头从前序输出指向后续方法；并列研究内容放同一列不同行，不加箭头。
- 时间、样本量、指标只写材料给出的；没有就不写。
**图例与版式**
- 用到的每种边类型/颜色、部件类别色都进图例；颜色用色盲友好色（#0072B2 #E69F00 #009E73 #CC79A7 #56B4E9 #D55E00），语义同时靠线型区分。
- 画布默认 1200×800 px，字号 ≥ 12 px；中文可直接写（字体栈含 CJK）。图上不写 id、文件名、行号。

## spec 示例（节点 cx/cy 为中心；panel/legend 的 x/y 为左上角）
```json
{"canvas":{"w":1200,"h":620,"title":"<图题>"},
 "nodes":[{"id":"n-tank","label":"<储液罐>","cx":150,"cy":300,"shape":"round","w":130,"h":90,"src":"materials/m.md:L3"},
  {"id":"n-pump1","label":"<泵 1>","cx":380,"cy":300,"shape":"circle","w":70,"h":70,"src":"materials/m.md:L4"},
  {"id":"n-reactor","label":"<反应器>\n<温度 单位>","cx":620,"cy":300,"shape":"round","w":150,"h":100,"src":"materials/m.md:L5"},
  {"id":"n-ctrl","label":"<控制器>","cx":620,"cy":120,"src":"materials/m.md:L7"}],
 "edges":[{"id":"e-l1","from":"n-tank","to":"n-pump1","type":"flow","width":3,"src":"materials/m.md:L4"},
  {"id":"e-l2","from":"n-pump1","to":"n-reactor","type":"flow","width":3,"label":"<流速 单位>","src":"materials/m.md:L4"},
  {"id":"e-s1","from":"n-ctrl","to":"n-reactor","type":"signal","label":"<控温>","src":"materials/m.md:L7"},
  {"id":"e-back","from":"n-reactor","to":"n-tank","type":"flow","color":"#777777","via":[[620,460],[150,460]],"label":"<回流>","src":"materials/m.md:L6"}],
 "legend":{"x":900,"y":80,"title":"Legend","items":[{"edge":"flow","label":"<液体>"},{"edge":"signal","label":"<控制信号>"},{"edge":"flow","color":"#777777","label":"<回流/废液>"}]}}
```
其他键：`panels[{id,x,y,w,h,title,fill}]`、`texts[{id,text,x,y,fs,w,anchor}]`、`canvas.grid{x0,y0,dx,dy}` + 节点 `col,row`、边 `elbow:"hv"|"vh"`、`both`、`width`。边类型 activate inhibit bind modify transport indirect flow signal step line。

## result.json 规则
- 必有：`case_id`、每个 contract 字段、`status`、`status_reasons`、`artifacts`（路径相对 /app/output，带 role：source/preview/export/record）、`components`、`connections`、`steps`/`stages`（ir.md 各表内嵌）、`source_map`（内嵌表 + `figure_source_map.md`）、`data_mapping`（颜色/线型 ↔ 介质或类别；参数 ↔ 来源）、`export_checks`（格式、画布 px、dpi、PNG 尺寸、PDF 矢量与否、字体嵌入、中文字体、最小字号、色盲/灰度、渲染器）、`change_log`、`versions`（skill lite-1.0、材料文件名、渲染器）、`uncertainties`、`material_gaps`、`needs_human_confirmation`。
- 字段映射按含义：要“源文件/路径”的填 svg + spec 路径；要“导出件”的填 png/pdf 路径加 export_checks；要“来源/修改记录”的填 source_map + change_log 内嵌表并附文件路径；看不懂的字段填最接近内容并在 `run_notes` 说明。
- 任何字段不得留空、TODO、“生成中”。**status 只写一个词**：contract 列了可选词用它的；否则 complete / partial / failed。complete = 图、预览、来源映射齐全且无未决冲突；有缺口或待确认 = partial（原因逐条写进 status_reasons）；没出图 = failed。

## 异常处理
| 情况 | 处置 |
|---|---|
| 部件参数缺失 | 标签只写名称，参数列 material_gaps，不估值 |
| 连接或接口没写、两处描述冲突 | 不画该连接（或按更具体的一处画并注明），列待确认 |
| 步骤顺序有歧义（正文与表格不同） | 按正文编号画，冲突写 uncertainties |
| 部件过多（> 25）、画布溢出 | 拆成总图 + 局部放大子图（panel a/b），或加大画布 |
| 无渲染器 / 渲染失败 / 无中文字体 | 保留 SVG，记录 export_log；改英文或记录方框风险；status partial；不反复重试 |
| PDF 抽不出文本 / 材料打不开 | 记 material_gaps，只用能读到的材料，status partial |
| 时间不够（elapsed > 600 s） | 不再新增图或美化；`fill` → 写完 result.json → `check`，未完成部分写进 status_reasons |

## 不做的事
不编造部件、连接、参数或步骤；不把并列画成先后、把先后画成并列；不只交位图；图上不留内部 id/文件名/TODO；不伪造渲染结果或人工确认。
