---
name: sci-schematic-editable-lite
description: 把来源材料（原始论文 PDF、figure 工单 figure-workorder.json、数据表、研究/流程描述）画成或改成可逐条核对的科研关系示意图——结构/层级（包含）图、谱系/上下游图、实验流程图、因果机制链条。包含用嵌套分组表达并由脚本核对（节点必须完全落在所属组内、子组不出界、兄弟组不交叠），流程序号与箭头方向一致，激活/抑制/信号/物料流各有固定线型，证据强度（间接/未验证）单独编码；分类颜色与图例由脚本直接读 CSV 生成（类别数=图例色块数，改一处颜色全图与图例同步）。交付分层可编辑 SVG + JSON 规格 + 真实 PNG/PDF + 像素级自检 + 工单逐条对照 + 源文件级修改记录。精简版：3 个标准库脚本，无安装。不用于：统计计算、海报/封面美化、艺术插画、正文写作。
---

# 科研关系示意图（精简版）

## 路径与预算
- 输入 `/input/case.json`、task.md、材料（常见：`source/*.pdf` 原始论文、`artifacts/figure-workorder.json` 工单、`data/*.csv`）。先 `ls -R /input`，路径以 case.json 为准。工作目录 `/app/work`，交付 `/app/output`，本 Skill 在 `/skills/weekly-skill`（下文 `$S`）。环境变量 `CASE_JSON`/`WORK_DIR`/`OUT_DIR` 若存在一律优先。
- 预算 64 次请求 / 900 秒，**目标 20–30 次调用**。渲染加 `timeout`。只用 python 改文件，不用 `sed -i`。Python 3.8 兼容。
- 脚本：`svgfig.py`（spec→SVG + content_map；edit；diff）、`export_check.py`（tools、render、check）、`pixcheck.py`（看渲染像素）。

## 步骤
1. **读任务（1 次）**：一条命令 `cat` case.json、工单 JSON（任何 `*workorder*`/`*.json` 工单）、task.md 末尾“组织方具体输入修订”，并 `sha256sum` 所有材料（记入 versions）。记下：case_id（`case_id`/`caseId`/`id`）、要画/改哪张图（如 figure03 的哪几个子图）、**must_show 每一项**、层级/分组要求、命名规则、导出格式/宽度 mm/dpi/最小字号、**修改请求**、output_contract 全部字段。
2. **骨架（第 2 次调用）**：写 `/app/output/result.json`：case_id + 每个 contract 字段填 `"生成中"` + `"status":"partial"` + `"status_reasons":["生成中"]`；同一命令跑 `timeout 60 python3 $S/scripts/export_check.py tools`。（check 会把残留的“生成中”判 FAIL，最后必须替换。）
3. **读源（1–3 次）**：PDF 用 `pdftotext -layout f.pdf /app/work/src.txt`（无则 python fitz/pypdf；都没有 → exceptions 记“材料无法读取”）；先 `grep -n -i -E "fig(ure)?\.? ?3|<工单关键词>" /app/work/src.txt` 定位**图注和对应结果段、方法段**，再 `sed -n` 读这些段落全文（摘要、结果、方法里同一参数都要看，矛盾常在这里）。CSV 直接 `cat`。图片读不了就写“未读出”，不猜。材料自带 SVG 要求修改 → 走第 7 步，不重画。
4. **定实体与关系（在写 spec 时完成，不另开文件）**：每个实体定 `kind`、所属组 `comp`、显示名（同义名放 `aliases`）、`src`（`src.txt:L行号`）；每条关系定 `type`、方向、`evidence`、`src`。逐条过下方“关系语法”。拿不准的进 exceptions，不自行补全。
5. **spec → build（2–4 次）**：写 `/app/output/figure_spec.json`，`python3 $S/scripts/svgfig.py build /app/output/figure_spec.json /app/output/figure.svg`（同时生成 `figure_content_map.json`，含实体、关系、由嵌套自动导出的 `contains` 关系、图例、数据映射）。**WARN 全部改到消失**（缺 src/kind、组未命名、节点不完全在所属组内、节点画在别的组里、子组出界、兄弟组交叠、step 方向与序号相反、两条边重叠、穿节点、穿图例、边标签被遮、标签溢出、图例缺项/多项、颜色无图例）；确实不能改的写进 exceptions。
6. **导出 + 看像素（1–2 次）**：`timeout 300 python3 $S/scripts/export_check.py render /app/output/figure.svg --dpi <工单dpi或300>`，同一命令接 `python3 $S/scripts/pixcheck.py /app/output/figure.svg`。pixcheck FAIL（填色没按声明渲染、标签不可见、节点颜色在图例里找不到、边样式无图例）→ 改 spec 重 build 重渲染。渲染器全失败：保留 SVG，记录 export_log，status partial，不伪造 PNG。
7. **源文件级修改（2–3 次）**：工单/任务有修改请求就照做；没有就做一次“演示编辑”（换一个标签措辞），change_log 标“演示，不属于正式图”。复制 spec 为 `figure_spec_v2.json` 改后 build 到 `figure_v2.svg`（会重新换行与查错）。**改某一类别的颜色 = 改 `canvas.categories.colors` 里那一个类别**，该类所有节点和图例色块一起变；不要逐个节点 `--set fill`（图例会脱节）。材料自带 SVG 或单属性改动才用 `svgfig.py edit in.svg out.svg <id> --text "新标签" --set fill=#hex`。然后 `svgfig.py diff figure.svg figure_v2.svg > /app/output/edit_diff.json`，render + pixcheck 新版本。修改请求引入材料里没有的内容：照做，exceptions 记 `user_request_not_in_source`，节点 src 写“工单 edit_request”。
8. **写 result.json 并自检（2–3 次）**：用下方模板脚本从 content_map / pixel_check / export_log / edit_diff 自动组装（不要手抄表格），补上 compliance_checks 与 exceptions；运行 `python3 $S/scripts/export_check.py check`，FAIL 改到 PASS；对照 `$S/resources/checklist.md` 扫一遍。

## 关系语法（结构画错比画丑更致命）
| 材料措辞 | spec 写法 | 图形 |
|---|---|---|
| 含有、由…组成、属于、位于…内（器官⊃组织⊃细胞；平台⊃模块） | 外层 `panels`，内层 panel 写 `parent`，节点写 `comp`=最内层组 id | 嵌套框；**不用箭头表示包含** |
| 并列、同级、几组平行处理 | 同一 `comp`、同一行（`canvas.grid` + `col,row`）、同尺寸 | 无箭头 |
| 实验/处理步骤、时间顺序 | `step`，标签以序号开头 “1 …”“2 …”，序号=材料顺序（build 查方向） | 实心箭头，单一阅读方向 |
| 物料/样本流、分化/产生（A 产生 B、谱系） | `flow`，标签写原文动词（如 “gives rise to”） | 蓝色粗实线箭头 |
| 分泌因子、信号传递（A 分泌 X 作用于 B） | `signal`，标签写因子名 | 橙色虚线箭头 |
| 激活、促进、诱导、支持 | `activate` | 绿色实心箭头 |
| 抑制、阻断、抑制分化 | `inhibit`（“A 被 B 抑制”画 B ⊣ A） | 红色 T 端 |
| 结合、相互作用 | `bind` | 圆点端，无方向 |
| 只说相关、对应 | `line`（图注说明无方向） | 无端点 |
- **证据强度与 type 正交**：`evidence: direct`（默认）/ `indirect`（点线）/ `hypothesis`（点划线，“未检验”“可能”）。不把推测画成实线。
- 边的两端可以是节点 id，也可以是 panel id（“TA 细胞 → 分泌谱系”这类指向整组的关系）。
- 同一实体在两个子图各出现一次（如 a 的层级与 b 的谱系）：两个节点，同一显示名与同一 `data` 键，id 不同。
- 层级深度与材料一致：不把子项提升为同级，不把同级画成包含；分组框只框住材料说同组的元素。一个元素同时属于“结构组”和“谱系类别”时：结构用嵌套表达，谱系用颜色（categories）表达，两者不要混用。
- 图上不出现材料里没有的实体、浓度、时间点、数值或单位；数值与单位照抄并在 src 指明行。多子图时 panel 标题用 “a”“b”“c” 前缀，与图注一致。

## 图例与数据映射
- 图例只需给 `legend:{x,y,title}`：用到的每种 type、每种 evidence、每个数据类别**自动补齐**；手写的项图上没用会报 WARN。
- **分类着色一律用 `canvas.categories`**：`{"csv":"/input/data/x.csv","key":"cell_type","column":"lineage","colors":{"stem":"#009E73","secretory":"#E69F00"},"title":"Lineage (Table S2)","show":"n_cells","fmt":"n = {}"}`；节点写 `"data":"<key 列的值>"`。脚本读 CSV：每个类别一色（未给的用 Okabe–Ito 补）、图例按表中类别逐个列出、`show` 列的数值原样追加到标签第二行，并在 content_map 记 类别/颜色/显示值/文件 sha256。**不要手挑数据色、不要手抄表中数字。**
- 连续数值着色用 `canvas.colorscale`：`{"csv":…,"key":…,"value":"<列>","breaks":[…],"colors":[…],"title":"<量与单位>"}`。没有数据的节点自动白色，图例出现 “no value in x.csv”。
- 非数据的分组色（如阶段底色）在 legend.items 写 `{"fill":"#hex","label":"含义"}`。色盲友好；深色填充自动白字。
- 期刊尺寸：`canvas.width_mm` 写物理宽度；有效字号 pt = px × (width_mm×3.78/W) × 0.75。180 mm 双栏时 W ≤ 1000 才能让 12 px 的边标签/图例 ≥ 6 pt；85 mm 单栏 W ≈ 400–470。

## spec 示例（节点 cx/cy 为中心；panel/legend 的 x/y 为左上角）
```json
{"canvas":{"w":1000,"h":870,"width_mm":180,"title":"<图题，来自材料>","src":"src.txt:L<图注行>",
  "categories":{"csv":"/input/data/t.csv","key":"cell_type","column":"lineage","colors":{"<类别1>":"#009E73"},"title":"<类别名 (Table)>","show":"n_cells","fmt":"n = {}"}},
 "panels":[{"id":"p-a","x":20,"y":50,"w":470,"h":470,"title":"a  <层级>","src":"src.txt:L30"},
  {"id":"p-org","parent":"p-a","x":35,"y":85,"w":440,"h":420,"title":"<整体>","src":"src.txt:L10"},
  {"id":"p-d1","parent":"p-org","x":50,"y":120,"w":200,"h":370,"title":"<组 1>","fs":14,"src":"src.txt:L11"},
  {"id":"p-c","x":20,"y":540,"w":740,"h":310,"title":"c  <流程>","src":"src.txt:L32"}],
 "nodes":[{"id":"n-x","label":"<细胞类型>","kind":"cell_type","comp":"p-d1","data":"<CSV key>","cx":150,"cy":200,"w":160,"h":64,"src":"src.txt:L11"},
  {"id":"s1","label":"1 <步骤>","kind":"step","comp":"p-c","cx":95,"cy":640,"w":130,"h":70,"src":"src.txt:L25"},
  {"id":"s2","label":"2 <步骤>","kind":"step","comp":"p-c","cx":240,"cy":640,"w":130,"h":70,"src":"src.txt:L26"}],
 "edges":[{"id":"e-s12","from":"s1","to":"s2","type":"step","src":"src.txt:L25-26"},
  {"id":"e-inh","from":"n-reg","to":"p-sec","type":"inhibit","src":"src.txt:L20"},
  {"id":"e-hyp","from":"n-a","to":"n-b","type":"activate","evidence":"hypothesis","src":"src.txt:L21"}],
 "texts":[{"id":"t-note","text":"* <矛盾或条件注>","x":35,"y":835,"fs":12,"src":"src.txt:L26; L40"}],
 "legend":{"x":785,"y":545,"title":"Legend"}}
```
其他键：`shape` rect|round|band|ellipse|circle|diamond、`fill`、`fs`、`bold`、`aliases`；边 `via:[[x,y]]`、`elbow:"hv"|"vh"`、`both`、`width`。kind：cell_type cell tissue organ organism sample material reagent condition instrument step process data concept group gene mrna protein complex small_molecule。gene/mrna 自动斜体。图上不写 id、文件名、行号。

## result.json 组装模板（第 8 步，按需改值后运行）
```python
import json,os; O=os.environ.get("OUT_DIR","/app/output"); L=lambda p:json.load(open(os.path.join(O,p),encoding="utf-8"))
r=L("result.json"); cm=L("figure_content_map.json"); px=L("figure_pixel_check.json")
ex=[json.loads(l) for l in open(os.path.join(O,"export_log.jsonl"),encoding="utf-8")]
r.update(status="partial", status_reasons=["<逐条：未决矛盾/缺口；全部解决才写 complete>"],
 editable_source={"svg":"figure.svg","spec":"figure_spec.json","layers":["panels","edges","nodes","data","text","legend"],"edited":["figure_v2.svg","figure_spec_v2.json"],"how_to_edit":"改 spec 后 svgfig.py build；类别颜色改 canvas.categories.colors；或 svgfig.py edit 按 id 改"},
 export_artifact=[{k:e.get(k) for k in ("png","pdf","png_method","pdf_is_vector","pdf_fonts","canvas_px","dpi")} for e in ex],
 content_map=dict(cm,file="figure_content_map.json"),
 compliance_checks=[{"requirement":"<工单 must_show/导出/修改请求原文一项>","result":"pass|partial|fail","element_ids":["<SVG 中的 id>"],"evidence":"<怎么满足>"},
   {"requirement":"pixel inspection","result":"pass" if not px["fails"] else "fail","element_ids":[],"evidence":"figure_pixel_check.json"}],
 exceptions=[{"category":"material_missing|undecidable|contradiction|run_failure|user_request_not_in_source","detail":"…","handling":"…"}],
 change_log=[dict(c,version="v2",reason="<修改请求原文>") for c in L("edit_diff.json")["changes"]],
 versions={"skill":"sci-schematic-editable-lite 1.1","materials_sha256":{"<文件>":"<sha>"},"renderer":ex[-1].get("png_method")},
 artifacts=[{"path":p,"role":"source" if p.endswith((".svg",".json")) else "export"} for p in sorted(os.listdir(O)) if p!="result.json"])
json.dump(r,open(os.path.join(O,"result.json"),"w",encoding="utf-8"),ensure_ascii=False,indent=1)
```
- contract 字段名不同就按含义映射：源文件/路径 → editable_source；导出件 → export_artifact；来源/元素/映射 → content_map；检查/合规 → compliance_checks；异常/不确定/缺口 → exceptions；修改记录 → change_log。看不懂的字段填最接近内容并在 `run_notes` 说明。
- compliance_checks 必须覆盖工单每一项（每条 must_show、层级/分组、格式/宽度/dpi/最小字号、修改请求），`element_ids` 必须是 SVG 里真实存在的 id（check 会核对）。
- **status 只写一个词**：contract 给了词表就用它的；否则 complete / partial / failed。exceptions 里有未决项 → partial；没出图 → failed。“材料缺失、无法判断、运行失败”分别用不同 category 写。

## 异常处理
| 情况 | 处置 |
|---|---|
| 摘要/结果/方法对同一参数说法不一（天数、浓度、顺序） | 图上按更具体或出现更多的那处并加星号脚注，两处原文写进 exceptions: contradiction，status partial |
| 方向或关系类型没写清、“未检验” | `line` 或 `evidence: hypothesis`，exceptions: undecidable |
| 材料提到但数据表没有的实体（如只在成像中见到） | 不进数据着色；画不画按工单“不得新增”判断，写 exceptions: material_missing |
| 数据表类别与正文类别对不上 | 图例按数据表（categories），差异写 contradiction，不新增类别 |
| 修改请求引入材料没有的内容 | 照做、src 标工单，exceptions: user_request_not_in_source |
| 要求 EPS/TIFF/CMYK 而工具不支持 | 交付 SVG/PDF/PNG，缺项写 exceptions: run_failure |
| 元素 > 25 不可读 | 拆子图 a/b/c，或把非核心分支合并为一个节点并在 aliases 列出 |
| 渲染器或中文字体缺失 | 保留 SVG + export_log，改英文标签或记 tofu 风险，status partial |

## 不做的事
不编造实体、关系、数值、单位或来源；不把推测画成确定；不用箭头表示包含；不手挑数据颜色；不只交位图；图上不留 id/文件名/TODO；不伪造渲染、像素检查或人工确认。
