---
name: bio-pathway-figure-lite
description: 把机制材料（论文段落/PDF、实验记录、实体表、数据表）画成可逐条核对的生物机制图或信号通路图：实体命名规范（基因斜体/蛋白正体/物种前缀/复合物）、相互作用语义（激活、抑制、结合、修饰、转运、间接/推测各有不同箭头）、区室与跨膜位置、图例与数据编码一致；交付分层可编辑 SVG（每个元素有 id 和来源）+ 真实渲染的 PNG/PDF + 来源映射 + 源文件级修改记录。精简版：标准库脚本，无安装。不用于：统计图表数值计算、艺术插画、论文写作。
---

# 生物机制图与通路图（精简版）

## 路径与预算
- 输入 `/input/case.json`（+ task.md 与材料，路径以 case.json 为准，先 `ls -R /input`）；工作目录 `/app/work`；交付 `/app/output`；本 Skill 在 `/skills/weekly-skill`（下文 `$S`）。环境变量 `CASE_JSON`/`WORK_DIR`/`OUT_DIR` 若存在一律优先。
- 预算 64 次请求、900 秒：目标 ≤ 30 次调用。每次渲染命令前加 `timeout 120`。只用 python 改文件，不用 `sed -i`。Python 3.8 兼容（f-string 花括号里不放反斜杠）。
- 工具：`python3 $S/scripts/svgfig.py`（build 规格→SVG、edit 改源、diff 记改动）；`python3 $S/scripts/export_check.py`（tools 探测、render 出 PNG/PDF、check 自检）。

## 步骤
1. **读任务（1–2 次）**：读 case.json 全文和 task.md 的“组织方具体输入修订”。记下 case_id（键 `case_id`/`caseId`/`id`）、图型与画布/格式/分辨率要求、是否有“修改/编辑”请求、output contract 全部字段（键可为 output_contract/outputContract/deliverables/中文；字段可为 snake/camel/中文/properties+required）。
2. **骨架（第 3 次调用以内）**：写 `/app/output/result.json`：case_id + 每个 contract 字段（先填一句“生成中”）+ `"status":"partial"` + `"status_reasons":["生成中"]`。同时 `timeout 60 python3 $S/scripts/export_check.py tools` 看渲染器和中文字体。
3. **读全部材料（2–5 次）**：文本/MD/CSV 直接读；PDF 用 `pdftotext -layout f.pdf -`（无则 python fitz/pypdf，再无则记为缺口）；XLSX 用 python zipfile 解 `xl/sharedStrings.xml`+`xl/worksheets/sheet1.xml`。图片读不了就写“未读出”，不猜内容。若材料给了现成 SVG/drawio 要求修改，走第 8 步，不重画。
4. **实体—关系表 `/app/work/er.md`（1–2 次）**：每行一个实体：`id | 显示名 | 类型(基因/mRNA/蛋白/复合物/家族/小分子/细胞/区室) | 区室 | 来源 文件:行 | 原文短引`；每行一个关系：`id | 上游 | 下游 | 语义 | 方向依据 | 证据强度(直接/间接/推测) | 来源 | 短引`。先过下方“机制图规则”，有歧义写进待确认，不自行补全。
5. **写规格 `/app/output/figure_spec.json` 并 build（2–4 次）**：`python3 $S/scripts/svgfig.py build /app/output/figure_spec.json /app/output/figure.svg`（spec 就是可编辑源，同时生成 `figure_elements.tsv`）。所有 WARN（缺 src、标签溢出、边穿过节点、无图例、未知 id）都要改到消失或写进 result.json 的 uncertainties。
6. **渲染（1 次）**：`timeout 300 python3 $S/scripts/export_check.py render /app/output/figure.svg --dpi 300` → figure.png + figure.pdf + export_log.jsonl。失败照实记录（哪个渲染器、报错），不伪造预览。
7. **来源与图注（1–2 次）**：`figure_source_map.md`（表：元素 id | 图上文字/数值 | 类型 | 来源 文件:位置 | 原文短引 | 人工确认?）以 `figure_elements.tsv` 为底稿；`figure_caption.md`（图注：读图顺序、图例含义、证据强度、只进图注不上图的信息）。
8. **源文件级编辑**：任务有修改请求就照做；没有就做一次“演示编辑”（如把某节点改成图例已有的另一种强调色），文件另存，change_log 标“演示，不属于正式图”。做法：自己生成的图优先改 spec（另存 `figure_spec_v2.json`）重新 build 到 `figure_v2.svg`（会重新换行、查溢出），单个属性或材料自带的 SVG 用 `svgfig.py edit in.svg out.svg <id> --text "新标签" --set fill=#xxxxxx`（多行标签用 `\n`）；然后 `svgfig.py diff 旧.svg 新.svg` 把 changes 写进 change_log，再 render 新版本。材料自带 SVG 时复制到 output 后用 edit 改，保持其余字节不变。
9. **填 result.json 并自检（2–3 次）**：按“result.json 规则”填写，运行 `python3 $S/scripts/export_check.py check`，FAIL 改到 PASS；再对照 `$S/resources/checklist.md` 过一遍。

## 机制图规则（每条都对照 er.md）
**命名**
- 人基因/mRNA 斜体全大写（*TP53*），蛋白正体（p53/TP53）；小鼠基因首字母大写斜体（*Trp53*）。spec 里基因节点设 `"italic": true`。物种不明写待确认。
- 显示名照抄材料；同义名/旧名只用一个，其余写进图注；家族成员与复合物不混用（复合物用一个圆角框，成员在标签内或并排紧贴）。
- 不出现材料里没有的基因、蛋白、修饰位点、浓度、时间点、数值。
**相互作用 → 边类型（svgfig 内置，颜色与端点固定）**
| 材料措辞 | type | 图形 |
|---|---|---|
| 激活、促进、诱导、上调 | activate | 实线 + 实心箭头 |
| 抑制、阻断、下调、拮抗 | inhibit | 实线 + T 形端 |
| 结合、相互作用、形成复合物 | bind | 实线 + 圆点端（无方向） |
| 磷酸化/泛素化/乙酰化等修饰 | modify | 空心箭头 + 标签（+P、+Ub） |
| 转运、入核、分泌、募集到… | transport | 虚线 + 箭头 |
| 间接、可能、推测、未验证 | indirect | 点线 + 箭头（灰） |
- 方向 = 因果方向（上游 from → 下游 to）；“A 被 B 抑制”是 B ⊣ A。只说“相关”时用 `line` 并在图注说明无方向。
- 一个关系只画一条边；证据只来自间接实验就用 indirect，不升级为 activate。
**区室与拓扑**
- 自上而下：胞外 → 膜 → 胞质 → 核（或材料指定的区室）；区室用 `panels`，膜用窄条 panel。跨膜受体节点中心放在膜条上；配体在胞外；转录因子入核用 transport 边跨区室。
- 主通路自上而下或自左向右单向流动；反馈环用 `via` 绕到侧边；边穿过节点（WARN）必须改。
**图例与数据编码**
- 图里用到的每种边类型、每种填充色都在 legend 里出现一次，文字说明语义；颜色编码数据（表达量、显著性）时 legend 写清分档和单位，数值来自数据表并在 source map 指明行列。
- 配色用色盲友好色（Okabe–Ito：#0072B2 #E69F00 #009E73 #CC79A7 #56B4E9 #D55E00）；语义靠端点和线型区分，灰度打印仍可读。

## spec 示例（坐标为像素；节点 cx/cy 是中心，panel/legend 的 x/y 是左上角）
```json
{"canvas":{"w":1000,"h":680,"title":"<图题，来自材料>"},
 "panels":[{"id":"p-extra","x":20,"y":60,"w":740,"h":120,"title":"Extracellular","src":"materials/a.md:L3"},
  {"id":"p-mem","x":20,"y":185,"w":740,"h":28,"fill":"#F2D7B6","src":"materials/a.md:L3"},
  {"id":"p-cyto","x":20,"y":218,"w":740,"h":260,"title":"Cytoplasm","src":"materials/a.md:L4"}],
 "nodes":[{"id":"n-lig","label":"<配体>","cx":380,"cy":125,"shape":"circle","w":80,"h":60,"src":"materials/a.md:L5"},
  {"id":"n-rec","label":"<受体>","cx":380,"cy":199,"w":120,"h":48,"shape":"round","src":"materials/a.md:L5"},
  {"id":"n-gene","label":"<基因>","cx":380,"cy":420,"italic":true,"src":"materials/a.md:L9"}],
 "edges":[{"id":"e-bind","from":"n-lig","to":"n-rec","type":"bind","src":"materials/a.md:L5"},
  {"id":"e-act","from":"n-rec","to":"n-gene","type":"activate","label":"<条件>","src":"materials/a.md:L7"}],
 "texts":[{"id":"t-note","text":"<短注>","x":30,"y":665,"fs":11,"src":"materials/a.md:L10"}],
 "legend":{"x":780,"y":70,"title":"Legend","items":[{"edge":"bind","label":"binding"},{"edge":"activate","label":"activation"}]}}
```
其他键：节点 `shape` rect|round|band|ellipse|circle|diamond、`fill`、`fs`、`bold`；边 `via:[[x,y],…]`、`elbow:"hv"|"vh"`、`both:true`、`width`；网格布局 `canvas.grid{x0,y0,dx,dy}` + 节点 `col,row`。中文标签可直接写（字体栈已含 CJK）。标签里不写 id、文件名、行号。

## result.json 规则
- 必有：`case_id`、每个 contract 字段、`status`、`status_reasons`、`artifacts`（路径相对 /app/output，含 role：source/preview/export/record）、`entities`（er.md 实体表内嵌）、`relations`（关系表内嵌）、`source_map`（内嵌表 + `figure_source_map.md`）、`data_mapping`（颜色/线宽/大小 ↔ 数据 ↔ 来源；没有数据编码写一句说明）、`export_checks`（格式、画布 px、dpi、PNG 尺寸、PDF 是否矢量、字体是否嵌入、中文字体、最小字号、色盲/灰度、渲染器）、`change_log`（版本、改了哪些 id、前→后、原因）、`versions`（skill 版本 lite-1.0、材料文件名、渲染器）、`uncertainties`、`material_gaps`、`needs_human_confirmation`。
- 字段映射按含义：要“源文件/路径”的填 `figure.svg`（或路径列表 + spec）；要“导出件”的填 png/pdf 路径加 export_checks；要“来源/修改记录”的填 source_map + change_log 内嵌表并附文件路径。看不懂的字段按说明填最接近的内容并在 `run_notes` 说明。
- 任何字段不得留空、TODO、“生成中”。**status 只写一个词**：contract 列了可选词就用它的；否则 complete / partial / failed。complete = 图、预览、来源映射齐全且无未决歧义；有缺口或待确认 = partial（原因逐条写进 status_reasons）；没有出图 = failed。

## 异常处理
| 情况 | 处置 |
|---|---|
| 关系方向/作用类型材料没写清 | 用 indirect 或 line，图注说明，列入 needs_human_confirmation |
| 同名基因与蛋白、物种不明 | 按材料原写法，列待确认，不擅自改大小写 |
| 数据与文字矛盾 | 两处都记进 uncertainties，图按数据表画并注明 |
| 节点过多不可读（> 25） | 合并非核心分支到一个“其他”节点并在图注列出，或拆子图 a/b |
| 标签溢出/边穿节点 | 调 w/h、坐标或 via，直到 build 无 WARN |
| 无渲染器/渲染失败 | 保留 SVG，记录 export_log，status partial，不伪造 PNG |
| 无中文字体 | 改用英文标签或记录 tofu 风险 |

## 不做的事
不编造实体、关系、数值或来源；不把推测画成实线；不只交位图；不在图上留内部 id、文件名、TODO；不伪造渲染结果或人工确认。
