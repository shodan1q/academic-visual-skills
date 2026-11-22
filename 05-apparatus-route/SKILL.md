---
name: apparatus-route-figure-lite
description: 按装置/路线工单（artifacts/figure-workorder.json，apparatus_and_technical_route）和原始论文、装置清单、方法段落、工艺步骤或研究计划画成实验装置图、工艺流程图或技术路线图：先抽“部件—接口—连接—步骤—流向—阶段”结构化清单，再按规则布图（编号与正文一致、并行支路、回流与终止条件、物料/能量/信息流用不同颜色线型、阶段与里程碑的依赖）；不凭空补连接；交付分层可编辑 SVG（每个元素 id + 来源）+ 真实渲染 PNG/PDF + 像素级自检 + content_map + 工单逐条对照 + 分类异常 + 源文件级修改记录。精简版：标准库脚本，无安装。不用于：数据分析拟合、判断方案是否合理、论文排版。
---

# 实验装置与技术路线图（精简版 1.1）

## 路径与预算
- 输入 `/input/case.json`（+ task.md 与材料，路径以 case.json 为准，先 `ls -R /input`）；工作目录 `/app/work`；交付 `/app/output`；本 Skill 在 `/skills/weekly-skill`（下文 `$S`）。环境变量 `CASE_JSON`/`WORK_DIR`/`OUT_DIR` 若存在一律优先。
- 预算 64 次请求、900 秒：本流程约 10–14 次调用，不要超过 30 次。渲染命令前加 `timeout`。只用 python 改文件，不用 `sed -i`。Python 3.8 兼容（f-string 花括号里不放反斜杠）。
- 脚本：`svgfig.py`（spec→分层 SVG + `figure_content_map.json`；edit；diff）、`export_check.py`（tools、render、check）、`pixcheck.py`（解码渲染出的 PNG 查尺寸、字号、填色、标签、对比度、图例）。
- 输入常见：`source/*.pdf` 原始论文、`artifacts/figure-workorder.json` 工单、`data/*.csv`。

## 步骤
1. **读任务与工单（1–2 次）**：`ls -R /input; cat /input/case.json; tail -40 <task.md>; cat <工单 artifacts/*workorder*.json>`。记下 case_id（键 `case_id`/`caseId`/`id`）、output_contract 全部字段、工单**每一个键/每一条要求**（图型、必须出现的内容、尺寸 width_mm/dpi/min_font_pt/格式、语言、edit_request）。工单每一行在第 8 步对应 compliance_checks 的一项。
2. **骨架（第 3 次调用以内，一条命令）**：
   `python3 -c "import json,os;c=json.load(open(os.environ.get('CASE_JSON','/input/case.json')));o=os.environ.get('OUT_DIR','/app/output');os.makedirs(o,exist_ok=True);f=c.get('output_contract') or [];f=list(f) if not isinstance(f,dict) else list(f.get('properties',f));r={k:'生成中' for k in f};r.update(case_id=c.get('case_id',c.get('caseId',c.get('id'))),status='partial',status_reasons=['生成中']);json.dump(r,open(o+'/result.json','w'),ensure_ascii=False,indent=1)" && timeout 60 python3 $S/scripts/export_check.py tools`
   骨架里的“生成中”会被 check 判 FAIL——它只是预算耗尽时的保底，不是完成。
3. **读源（1–3 次）**：PDF `pdftotext -layout x.pdf /app/work/src.txt`；没有 pdftotext 用 `python3 -c "import fitz,sys;open(sys.argv[2],'w').write('\n'.join(p.get_text() for p in fitz.open(sys.argv[1])))" x.pdf /app/work/src.txt`（或 pypdf；都没有 → exceptions `material_missing`）。先 `grep -n -i -E "<工单点名的图号或关键词>" /app/work/src.txt` 定位，再读那几段全文；CSV 直接读，XLSX 用 python zipfile。以后所有出处都写 `src.txt:L<行号>` 或 `文件:row<行号>`。图片内容读不了写“未读出”，不猜。
4. **结构化清单 `/app/work/ir.md`（1 次）**，每行带 `src.txt:L行 | 原文短引`：
   - 部件：`id | 名称（照抄）| 数量 | 型号/参数/单位 | 接口(入口/出口)`；同类多件分别编号（泵 1、泵 2）。
   - 连接：`id | from 部件.接口 | to 部件.接口 | 介质(液/气/电/热/信号/废料) | 方向依据`。**原文没写的连接不画**，exceptions `material_missing`。
   - 步骤（合成路线/工艺）：`编号(与原文一致) | 起始物/中间体 → 产物 | 试剂与用量(照抄) | 条件(溶剂、温度 °C、时间 h、气氛、压力，照抄单位) | 产率/转化率 | 下一步 | 并行/循环/终止条件`。化学名、缩写、上下标（H₂O、Pd/C）照抄；单位不换算。
   - 阶段（技术路线）：`阶段 | 目标 | 方法 | 输入 | 输出/里程碑 | 依赖的前序阶段`。
   - 正文与表格/图注对同一步的顺序或条件说法不同 → 按正文编号画，exceptions `contradiction` 写两处出处。
5. **写 spec 并 build（2–3 次）**：`/app/output/figure_spec.json`，`canvas.width_mm` 设为工单宽度；`python3 $S/scripts/svgfig.py build /app/output/figure_spec.json /app/output/figure.svg`（同时写 `figure_content_map.json`：部件/步骤元素、连接/箭头关系，各带 src）。需要两张图（装置 + 路线）就各写一个 spec，后续每步对两张图都做。**WARN 全部改到消失**（缺 src、溢出、边穿部件、图例缺项、未知 id）；确实不能改的写进 exceptions。对照 ir.md 核对 content_map：部件数、连接数、步骤顺序、每个条件标签与原文一字不差。
6. **导出 + 看像素（1–2 次）**：`timeout 300 python3 $S/scripts/export_check.py render /app/output/figure.svg --dpi <工单 dpi 或 300> && python3 $S/scripts/pixcheck.py /app/output/figure.svg --workorder <工单路径>`。pixcheck 解码 PNG（运行时看不见图片，靠它）：PNG 宽 = width_mm × dpi、最小字号 ≥ min_font_pt、不空白不裁切、每个节点按声明颜色渲染且标签有墨迹、标签/底色对比度、图例色块与线型和图面一致。FAIL → 改 spec 重 build 重渲染；渲染器全失败 → 保留 SVG，exceptions `run_failure`，status partial，不伪造 PNG。
7. **源文件级修改（1–2 次）**：工单 edit_request（或任务里的修改要求）照做；没有就做一次演示编辑（改一个标签措辞），change_log 标“演示，不属于正式图”。复制 spec 为 `figure_spec_v2.json` 改对应元素，build 到 `figure_v2.svg`（单属性改动也可 `svgfig.py edit in.svg out.svg <id> --text "新文字" --set fill=#xxxxxx`），然后 `python3 $S/scripts/svgfig.py diff figure.svg figure_v2.svg > /app/output/edit_diff.json`，对 v2 再 render + pixcheck。新颜色/线型要同时加进 legend。修改请求引入原文没有的内容 → 照做，exceptions `user_request_not_in_source`，元素 src 写“工单 edit_request”。
8. **组装 result.json 并自检（2–3 次）**：运行下方模板（改 `<…>` 处），再 `python3 $S/scripts/export_check.py check`，FAIL 改到 PASS；对照 `$S/resources/checklist.md`。

## result.json 组装模板（第 8 步）
```python
import json,os; O=os.environ.get("OUT_DIR","/app/output"); L=lambda p:json.load(open(os.path.join(O,p),encoding="utf-8"))
r=L("result.json"); cm=L("figure_content_map.json"); px=L("figure_pixel_check.json")
ex=[json.loads(l) for l in open(os.path.join(O,"export_log.jsonl"),encoding="utf-8")]; d=L("edit_diff.json") if os.path.exists(os.path.join(O,"edit_diff.json")) else {"changes":[]}
r.update(status="partial", status_reasons=["<逐条：未决矛盾/缺口；全部解决才写 complete>"],
 editable_source={"svg":"figure.svg","spec":"figure_spec.json","layers":["panels","edges","nodes","data","text","legend"],"edited":["figure_spec_v2.json","figure_v2.svg"],"how_to_edit":"改 spec 后 svgfig.py build，或 svgfig.py edit 按 id 改"},
 export_artifact=[{k:e.get(k) for k in ("svg","png","pdf","png_method","pdf_is_vector","pdf_fonts","canvas_px","dpi")} for e in ex]+[{"pixel_check":"figure_pixel_check.json","png_px":px.get("export_png_px"),"dpi":px.get("export_dpi"),"min_font_pt":px.get("min_font_pt"),"fails":px["fails"]}],
 content_map=dict(cm,file="figure_content_map.json",ir="<第 4 步的表，内嵌>"),
 compliance_checks=[{"requirement":"<工单原文一行>","result":"<pass/partial/fail 选一>","element_ids":["<SVG 里真实存在的 id>"],"evidence":"<怎么满足、出处>"},
   {"requirement":"rendered pixel check","result":"pass" if not px["fails"] else "fail","element_ids":[],"evidence":"figure_pixel_check.json"}],
 exceptions=[{"category":"<material_missing/undecidable/contradiction/run_failure/user_request_not_in_source 选一>","detail":"<…>","handling":"<…>"}],
 change_log=[{"version":"v2","request":"<修改请求原文>","svg_changes":d["changes"]}],
 versions={"skill":"<skill 名> 1.1","materials":"<文件名与 sha256>","renderer":ex[-1].get("png_method")},
 artifacts=[{"path":p,"role":"source" if p.endswith((".svg",".json")) else "export" if p.endswith((".png",".pdf")) else "record"} for p in sorted(os.listdir(O)) if p!="result.json"])
json.dump(r,open(os.path.join(O,"result.json"),"w",encoding="utf-8"),ensure_ascii=False,indent=1)
```
- compliance_checks：工单每一行一项（不合并、不省略），外加本文件的规则项；`element_ids` 必须是 SVG 里真实存在的 id（check 会核对，写错即 FAIL）。
- contract 字段名不同就按含义映射：源文件/路径 → editable_source；导出件 → export_artifact；来源/元素/映射 → content_map；检查/合规 → compliance_checks；异常/不确定/缺口 → exceptions。看不懂的字段填最接近内容并在 `run_notes` 说明。
- **status 只写一个词**：contract 给了词表就用它的；否则 complete / partial / failed。exceptions 里有未决 contradiction / undecidable / material_missing → partial；没出图 → failed。材料缺失、无法判断、运行失败用不同 category 分别写。

## 画图规则
**装置图**
- 部件名称、数量与 ir.md 完全一致；同类部件用相同形状、不同编号；容器/反应器用 `round` 或 `ellipse`，泵/阀等小部件用 `circle`（w=h≈60），仪器/控制器用 `rect`，判断/切换用 `diamond`。
- 每条连接一条边，from/to 按介质流动方向；介质 → 边类型与颜色固定：液体 `flow` #0072B2、气体 `flow` + `"color":"#009E73"`、热/能量 `flow` + `"color":"#D55E00"`、电/控制信号 `signal`（虚线 #E08214）、废料/排出 `flow` + `"color":"#777777"`。参数（流速、温度、电压）作边或部件标签，原样带单位。
- 管路用 `elbow` 或 `via` 走直角，不穿过其他部件；分流/合流画成从同一部件出发的多条边，回流边从侧面 `via` 绕回并标“回流”。
**步骤流程图**
- 主序列单方向（上→下或左→右），节点标签以正文编号开头（“1 …”“2 …”），编号与正文逐条对应；并行支路用 3a/3b 同行并排；循环用 `via` 回到起点并在边标签写次数或条件（照抄）；终止/判断用 `diamond`，出边标签写“是/否”或条件。
**合成路线 / 反应流程**
- 化合物（起始物、中间体、产物）= 节点，标签写原文编号与名称（如“**2** 4-bromoanisole”）；每步反应 = 一条 `step` 边，箭头方向即反应方向；边标签两行：第 1 行试剂与当量，第 2 行条件（溶剂, 温度, 时间, 气氛），产率写在产物节点或边标签末尾，全部照抄原文与单位（用 `"label":"Pd(PPh<sub>3</sub>)<sub>4</sub> (5 mol%), K<sub>2</sub>CO<sub>3</sub>\ntoluene/H<sub>2</sub>O, 90 °C, 12 h; 78%"`）。
- 多步一锅、并行分支、收敛步骤按原文画；原文没给的条件/产率留空并记 exceptions，不估值。
**技术路线图**
- 阶段 = 从左到右的列（`panels`，标题“阶段 1 …”），每列内自上而下放 目标 → 方法 → 输出/里程碑（节点）；阶段间依赖用 `step` 箭头从前序输出指向后续方法；并列研究内容放同一列不同行，不加箭头。
- 时间、样本量、指标只写材料给出的；没有就不写。
**图例与版式**
- 用到的每种边类型/颜色、部件类别色都进图例；颜色用色盲友好色（#0072B2 #E69F00 #009E73 #CC79A7 #56B4E9 #D55E00），语义同时靠线型区分。
- 画布默认 1200×800 px；字号按打印宽度换算 pt = fs × width_mm / canvas.w × 2.835，须 ≥ 工单 min_font_pt（pixcheck 会算）；中文可直接写（字体栈含 CJK）。图上不写 id、文件名、行号。
- **行内标记**（所有标签、标题、边标签、柱标签）：`<i>Ifnb1</i>` 斜体、`H<sub>2</sub>O` 下标、`Ca<sup>2+</sup>` 上标，渲染为可编辑 tspan；一个标记不要跨行。基因名、基因型（`<i>Sting1</i><sup>−/−</sup>`）、化学式按此照原文写。
- **画布宽度先算**：边标签、图例、数值标签固定 12 px，打印字号 = 12 × width_mm / canvas.w × 2.835 pt；要 ≥ min_font_pt 就取 canvas.w ≤ width_mm × 34 / min_font_pt（180 mm、6 pt → ≤ 1020 px）。build 会对“边标签压住节点”告警：拆行、缩短或拉开节点。

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

## 异常处理
| 情况 | 处置 |
|---|---|
| 部件参数缺失 | 标签只写名称，参数记 exceptions `material_missing`，不估值 |
| 连接或接口没写、两处描述冲突 | 不画该连接（或按更具体的一处画并注明），exceptions `undecidable`/`contradiction` |
| 步骤顺序有歧义（正文与表格不同） | 按正文编号画，exceptions `contradiction` |
| 部件过多（> 25）、画布溢出 | 拆成总图 + 局部放大子图（panel a/b），或加大画布 |
| 无渲染器 / 渲染失败 / 无中文字体 | 保留 SVG，记录 export_log；改英文或记录方框风险；exceptions `run_failure`，status partial |

## 不做的事
不编造部件、连接、参数或步骤；不把并列画成先后、把先后画成并列；不只交位图；图上不留内部 id/文件名/TODO；不伪造渲染结果或人工确认。
