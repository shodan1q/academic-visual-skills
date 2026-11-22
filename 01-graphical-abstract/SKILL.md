---
name: graphical-abstract-lite
description: 按图形摘要工单（artifacts/figure-workorder.json，graphical_abstract）和原始论文/源数据（pdf/txt/csv/xlsx）制作单页 Graphical Abstract（图形摘要）：先做“面板—要点”映射（研究问题→方法→核心结果→结论，哪些上图、哪些只进图注），科学实体与空间/因果关系按材料摆放，核心结果用真实源数据编码（柱长=数值，带单位与误差），图例、单位、比例尺齐全、色盲友好；交付分层可编辑 SVG（每个元素 id + 来源）+ 真实渲染 PNG/PDF + 像素级自检 + content_map + 工单逐条对照 + 分类异常 + 源文件级修改记录。精简版：标准库脚本，无安装。不用于：正文写作、统计分析、实验设计、纯装饰插画。
---

# Graphical Abstract 图形摘要（精简版 1.1）

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
4. **一眼读懂的故事（写在 `/app/work/panel_map.md`，1 次）**：
   - 一句话主旨（照论文结论的强度）+ 3–4 个面板：①问题 ②方法/对象 ③核心结果 ④结论/意义（工单另有面板要求以工单为准）。每面板 1–3 个要点：`要点 | 上图形式(实体/箭头/柱/文字) | 来源 src.txt:L行 或 文件:row行 | 原文短引`。
   - **图上每一句话、每个数字、每个实体都要能回到原文或数据行**；做不到的不上图。核心数值从数据文件读（不抄摘要近似值），两者不一致 → 按数据画，exceptions `contradiction`。
   - 实体名照抄（基因斜体 `italic`、蛋白正体、物种/化合物原写法）；关系方向有原文依据；相关不画成因果，结论措辞不比原文强。
   - 统计细节、n、次要结果、限定条件只进 `figure_caption.md`。
5. **写 spec 并 build（2–3 次）**：用一小段 python 读源数据生成 `bars` 项（value、err、unit、src=文件:row），再写 panels/nodes/edges/texts/legend 到 `/app/output/figure_spec.json`；`canvas.width_mm` 设为工单宽度。`python3 $S/scripts/svgfig.py build /app/output/figure_spec.json /app/output/figure.svg`（同时写 `figure_content_map.json`：元素、关系、数据值，各带 src）。**WARN 全部改到消失**（缺 src、标签溢出、边穿节点、图例缺项、负值）；确实不能改的写进 exceptions。核对 content_map 的 data 与数据文件逐项一致。
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

## 版式与编码规则
- **阅读顺序**：四个 panel 左→右（横版）或 Z 形 2×2，标题带序号“1 问题 / 2 方法 / 3 结果 / 4 结论”（语言随任务）；panel 之间用 `step` 箭头串起主线；视觉焦点给核心结果（最大面板或强调色）。
- **实体与空间关系**：层级（分子 ⊂ 细胞 ⊂ 组织；样本 → 处理 → 测量）用嵌套或上下位置表达；作用方向用边类型（activate 促进、inhibit 抑制、transport 转移/递送、flow 物料/样本流、step 流程、indirect 推测）；示意尺寸不按比例时在图注写“示意，未按比例”；材料有尺度/比例尺时用 `line` 边画比例尺并标注数值与单位。
- **数据编码**：核心数值只用一种主通道（柱长，`bars`），柱从 0 开始，单位写在 `unit` 或标题；误差 `err` 的含义（SD/SEM/CI）写进图注；组名与数据表一致；不同组用色盲友好色（#0072B2 #E69F00 #009E73 #CC79A7 #56B4E9 #D55E00），并靠标签区分以便灰度打印。负值或对数数据不适合 bars，改用文字数值并说明。
- **图例**：每种边类型、每种填充色、每个数据系列都进 legend，文字说明含义与单位。
- **文字**：标题 ≤ 15 词，每个面板 ≤ 25 词；字号按打印宽度换算：pt = fs × width_mm / canvas.w × 2.835，须 ≥ 工单 min_font_pt（pixcheck 会算）；180 mm 宽、1200 px 画布时 fs ≥ 14；中文可直接写（字体栈含 CJK）。图上不写 id、文件名、行号、TODO。
- 不出现材料里没有的实体、数值、单位、p 值或结论。
- **行内标记**（所有标签、标题、边标签、柱标签）：`<i>Ifnb1</i>` 斜体、`H<sub>2</sub>O` 下标、`Ca<sup>2+</sup>` 上标，渲染为可编辑 tspan；一个标记不要跨行。基因名、基因型（`<i>Sting1</i><sup>−/−</sup>`）、化学式按此照原文写。
- **画布宽度先算**：边标签、图例、数值标签固定 12 px，打印字号 = 12 × width_mm / canvas.w × 2.835 pt；要 ≥ min_font_pt 就取 canvas.w ≤ width_mm × 34 / min_font_pt（180 mm、6 pt → ≤ 1020 px）。build 会对“边标签压住节点”告警：拆行、缩短或拉开节点。

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

## 异常处理
| 情况 | 处置 |
|---|---|
| 缺关键数值（只有“显著提高”无数据） | 结果面板用文字陈述+“数值未提供”，不画柱；exceptions `material_missing`，status partial |
| 摘要文字与数据表数值不一致 | 图按数据表，exceptions `contradiction`（两处出处） |
| 实体名歧义（缩写、基因/蛋白） | 照抄材料原写法，exceptions `undecidable` |
| 要点太多、文字溢出、画布超限 | 次要要点移到图注；缩短措辞；仍溢出再加大画布 |
| 无渲染器 / 渲染失败 / 无中文字体 | 保留 SVG，记录 export_log；改英文或记录方框风险；exceptions `run_failure`，status partial |

## 不做的事
不编造数值、实体、关系或结论；不把相关画成因果；不用装饰图标替代材料中的实体；不只交位图；图上不留内部 id/文件名/TODO；不伪造渲染结果或人工确认。
