---
name: bio-pathway-figure-lite
description: 把机制材料（原始论文 PDF、figure 工单 figure-workorder.json、数据表）画成或改成可逐条核对的生物机制图/信号通路图。实体带类型与区室（基因斜体带启动子箭头、蛋白圆角框、复合物八角框、受体跨在脂双层膜带上、核为双层核膜），布局由脚本按区室与因果顺序自动排（不写坐标；反馈环走外侧通道；字号按期刊宽度自动保证最小 pt），相互作用语义与证据强度分开编码（间接抑制也能画），节点颜色直接从 CSV 计算并自动生成图例，交付分层可编辑 SVG + JSON 规格 + 真实 PNG/PDF + 像素级自检 + 工单逐条对照 + 源文件级修改记录。精简版：3 个标准库脚本，无安装。不用于：统计计算、艺术插画、论文写作。
---

# 生物机制图与通路图（精简版）

版本 lite-1.5。

## 路径与预算
- 输入 `/input/case.json`、task.md、材料（常见：`source/*.pdf` 原始论文、`artifacts/figure-workorder.json` 工单、`data/*.csv`）。先 `ls -R /input`，路径以 case.json 为准。工作目录 `/app/work`，交付 `/app/output`，本 Skill 在 `/skills/weekly-skill`（下文 `$S`）。环境变量 `CASE_JSON`/`WORK_DIR`/`OUT_DIR` 若存在一律优先。
- 预算 64 次请求 / 900 秒，**目标 20–30 次调用**。渲染加 `timeout`。只用 python 改文件，不用 `sed -i`。Python 3.8 兼容。
- 脚本：`svgfig.py`（spec→自动布局→SVG + content_map；edit；diff）、`export_check.py`（skeleton、tools、render、assemble、check）、`pixcheck.py`（看渲染像素，只给提示）。
- 任何脚本或外部工具不可用、报错：记录原因，换下一条路或跳过，同一步重试不超过 2 次。

## 步骤
1. **读任务（1 次）**：一条命令 `cat` case.json、工单 JSON、task.md 末尾“组织方具体输入修订”，并 `sha256sum` 所有材料（记入 versions）。记下：case_id（`case_id`/`caseId`/`id`）、**工单要画/改的机制范围**（以工单的 task/requirements 为准；任务文字里的 “figure03” 是任务类别代号，不是论文的 Figure 3，不要去重画论文某张图，除非工单点名）、必需区室、必需关系类型、反馈/分支、命名规则（物种）、导出格式/宽度 mm/dpi/最小字号、**修改请求**、output_contract 全部字段。
2. **骨架（第 2 次调用）**：`python3 $S/scripts/export_check.py skeleton; timeout 60 python3 $S/scripts/export_check.py tools`。skeleton 认得各种 contract 写法（列表、properties/required、字段对象、中文/驼峰键），写出 case_id + 每个字段“生成中”+ status partial；第 8 步 assemble 会全部替换。
3. **读源（1–3 次）**：PDF 用 `pdftotext -layout f.pdf /app/work/src.txt`（无则 python fitz/pypdf；都没有 → exceptions 记“材料无法读取”）；先 `wc -l src.txt; grep -n -i -E "<工单里的分子名/关键词，用|隔开>" src.txt | head -80` 定位**讲这条机制的 Results 段落（和相关图注）**，再用 `sed -n 'a,bp'` 读这些段落全文（不整篇 cat）。每条关系都要回到原句确认方向、作用类型、位点、是否直接。CSV 直接读。图片内容读不了就写“未读出”，不猜。材料自带 SVG 要求修改 → 走第 7 步，不重画。
4. **决定再画（在写 spec 时完成，不另开文件）**：对每个实体定 `kind`、`comp`、显示名（同义名放 `aliases`）、`src`；对每条关系定 `type`、方向、`evidence`、`src`。逐条过下方“机制规则”。拿不准的进 exceptions，不自行补全。
5. **spec → build（2–3 次）**：写 `/app/output/figure_spec.json`（**不写任何坐标**，格式见下方示例），`python3 $S/scripts/svgfig.py build /app/output/figure_spec.json /app/output/figure.svg`。脚本自动排版：区室按 panels 顺序自上而下，区室内按边的因果顺序分行，自动找出反馈边并从外侧通道绕行，被挡住的边走行间/列间空白通道，一个节点上的多条线自动分开落点，箭头/T 端/圆点端是普通图形（任何渲染器都画得出），长标签自动换行，字号保证 ≥ `min_font_pt`；版面自动收成接近一页的比例（过高时把不分叉的连续步骤横排在同一行、拉开列距、图例分组排在图下）；同一来源指向多个目标的同名边标签（如三条 “transcription”）只写一次；同时写 `figure_content_map.json` 和 `figure_resolved_spec.json`（排好的坐标）。输出末行给出边交叉数和最小字号 pt。spec 写法有出入也不会中断：`source/target`、`compartment`、`name`、“phosphorylation / inhibits / translocation” 这类措辞会被归一成标准键和 type，缺 id 自动补，认不出的逐条 WARN（指向不存在节点的边不画）。WARN 先改语义类的（缺 src/kind、transport 连了不同实体、图例缺项、颜色分档接近白色），**最多再 build 两轮**；版面类 WARN（标签压线等）可加提示后重建一次：`"col": n` 固定列、`"rank": n` 固定行序、边 `"feedback": true`；剩下的写进 exceptions（assemble 也会补录），不为它循环。
6. **导出 + 看像素（1–2 次）**：`timeout 300 python3 $S/scripts/export_check.py render /app/output/figure.svg --dpi <工单dpi或300>; python3 $S/scripts/pixcheck.py /app/output/figure.svg`。render 依次试 rsvg-convert / cairosvg / inkscape / chrome / magick / soffice，都没有时退到内置渲染（有 matplotlib 出 PNG+PDF，否则出标准库矢量 PDF，export_log 有 note）；没有 PNG 记 run_failure，不重试、不伪造。pixcheck 只给提示（退出码 0）：标签不可见、节点颜色无图例色块这类明显问题改一次 spec；其余记录即可。读不了 PNG 时它写 `skipped` 并跳过。
7. **源文件级修改（2–3 次）**：工单/任务有修改请求就照做；没有就做一次“演示编辑”（换一个标签措辞或颜色），notes.json 的 edit_request 写“演示编辑（不属于正式图）：…”。自己生成的图：**复制 `figure_resolved_spec.json` 为 `figure_spec_v2.json`**（坐标已固定，改动不会让整图重排），只改对应节点/边的 label、fill、`stroke`、`"dash": true`（虚线边框）、src，build 到 `figure_v2.svg`（中间文件别留在输出目录）；材料自带 SVG 或单属性改动：`svgfig.py edit in.svg out.svg <id> --text "新标签" --set fill=#BBBBBB`。改颜色时在 spec_v2 的 legend.items 加 `{"fill":"#hex","label":"含义"}`（自加项排在最后，旧 id 不变）。带 `data` 的节点颜色由数据决定：要改成分组色就删掉该节点的 `data` 并在 exceptions 说明它不再显示数据。然后 `svgfig.py diff figure.svg figure_v2.svg > /app/output/edit_diff.json`，render + pixcheck 新版本。修改请求引入材料里没有的内容（如新位点、新数值）：照做，但在 exceptions 记 `user_request_not_in_source`，节点 src 写“工单 edit_request”。
8. **组装 result.json 并自检（1–3 次）**：把只有你能判断的内容写进 `/app/work/notes.json`（格式见下），再 `python3 $S/scripts/export_check.py assemble /app/work/notes.json`。assemble 读 OUT_DIR 里已有的文件（content_map、pixel_check、export_log、edit_diff、spec、caption、source_map；**缺哪个都不报错**），按含义填好**每个 contract 字段**（字段名是什么都行），然后自动运行 check。FAIL 只改它点名的那一处，再跑 assemble，最多 2 轮；WARN 记录或忽略。对照 `$S/resources/checklist.md` 扫一遍。预算快用完时先跑一次 assemble（没有 notes.json 也能填满所有字段）。

## 机制规则（读者会逐条核对）
**实体与命名**
- `kind`：gene / mrna / protein / complex / family / small_molecule / ion / cell / process。kind 决定图元（基因=直角框+启动子箭头且斜体，蛋白=圆角框，复合物=八角框，家族=叠框，小分子=椭圆），图例“Entities”自动列出。翻译后修饰状态用 `"mods":["P"]`（或 "Ub"/"Ac"/"Me"）画成节点角标，修饰反应本身仍用 modify 边。人：基因 *TP53*、蛋白 p53/TP53；小鼠：基因 *Ifnb1*（首字母大写），蛋白 IFN-β / STING（全大写）。物种不明 → exceptions。
- 同一分子出现在两个区室（如 STING 在 ER 与 Golgi、IRF3 在胞质与核）画两个节点，同一显示名，id 不同。
- 同义名/旧名（MITA、TMEM173）只上一个显示名，其余写 `aliases`；家族与成员、复合物与亚基不混用（复合物一个节点，标签写全成员如 “IFNAR1/IFNAR2”）。
- 图上不出现材料里没有的分子、位点、数值、时间点。
**关系 → `type`（颜色和端点由脚本固定）**
| 材料措辞 | type | 图形 |
|---|---|---|
| 激活、促进、诱导、上调、转录诱导、表达 | activate | 实线实心箭头 |
| 抑制、阻断、降解、拮抗 | inhibit | 实线 T 端 |
| 结合、募集、形成复合物 | bind | 圆点端，无方向 |
| 磷酸化/泛素化等修饰，效应未说明 | modify | 空心箭头 + 标签 “+P S388” |
| 修饰且效应已说明（泛素化→降解） | 按效应用 activate/inhibit | 标签写 “+Ub → degradation” |
| 入核、出核、跨膜转位、分泌 | transport | 虚线箭头，**只连同一实体的两个区室副本** |
| 只说“相关”、无方向 | line | 无端点 |
- 方向 = 因果方向；“A 被 B 抑制”画 B ⊣ A。转录因子入核：IRF3(胞质) –transport→ IRF3(核) –activate→ *Ifnb1*；基因到蛋白：*Ifnb1* –activate(“expression”)→ IFN-β，分泌另用 transport 连 IFN-β 的两个副本或在标签说明。
- **证据强度与 type 正交**：`evidence: direct`（实线，默认）/ `indirect`（点线）/ `hypothesis`（点划线）。“仅过表达观察到、应视为间接”= `type: inhibit, evidence: indirect`；“未检验是否直接”= `evidence: hypothesis`。不把间接画成实线，也不把抑制降成灰箭头。
- 同一对节点有两种关系（结合 + 磷酸化）：画两条边并给一条 `via` 绕开，否则 build 报重叠。
**区室与拓扑**
- panels 按自上而下的顺序列出：胞外 → 质膜 → 胞质 → 核膜 → 核。细胞器（ER、Golgi、线粒体、内体）写 `"in":"p-cy"` 成为胞质里的子框。标题含 membrane/envelope/膜（或 `"membrane":true`）的 panel 画成脂双层窄带，其上的节点自动加高、跨在膜上；标题含 nucleus 的画双层核膜。
- 节点写 `comp` = 所在 panel id；跨膜受体的 `comp` 是膜带；配体在胞外；同一分子在两个区室各一个节点。
- 主链上→下；从下方区室产生的分子（如核内基因表达出的反馈蛋白）自动放在本区室底部，反馈边从外侧通道返回，不横穿主链。
**图例与数据编码**
- 图例只需给 `legend:{x,y,title}`：用到的每种 type、每种 evidence、颜色分档会**自动补齐**；自己手写的项若图上没用会报 WARN。
- 数据上色一律用 `canvas.colorscale`：`{"csv":"/input/data/x.csv","key":"gene","value":"log2FC_6h","breaks":[-1,1,3,5],"colors":["#2166AC","#CCCCCC","#FDDBC7","#EF8A62","#B2182B"],"title":"log2FC, 6 h (Table S3)"}`，节点写 `"data":"<key 列的值>"`。脚本读 CSV 取值→分档→填色→图例，并在 content_map 记 值/分档/颜色/文件 sha256。不要手挑数据色。没有数据的分子自动白色，图例出现 “no data”；所以中间档不要用近白色（用 #CCCCCC），否则 build 报 WARN。
- 其他颜色只用于分组时，legend items 里写 `{"fill":"#hex","label":"含义"}`。色盲友好（Okabe–Ito / RdBu），深色填充时标签自动变白。

## spec 示例（自动布局：不写 x/y/w/h/cx/cy；宽度、最小字号照抄工单）
```json
{"canvas":{"width_mm":180,"min_font_pt":6,"title":"<图题，来自材料>","src":"src.txt:L<图注行>",
  "colorscale":{"csv":"/input/data/de.csv","key":"gene","value":"log2FC","breaks":[-1,1,3],"colors":["#2166AC","#CCCCCC","#F4A582","#B2182B"],"title":"log2FC (Table S1)"}},
 "panels":[{"id":"p-ex","title":"Extracellular space","src":"src.txt:L12"},
  {"id":"p-pm","title":"Plasma membrane","src":"src.txt:L12"},
  {"id":"p-cy","title":"Cytoplasm","src":"src.txt:L5"},
  {"id":"p-er","title":"ER","in":"p-cy","src":"src.txt:L6"},
  {"id":"p-nu","title":"Nucleus","fill":"#EAF2FA","src":"src.txt:L9"}],
 "nodes":[{"id":"n-lig","label":"<配体>","kind":"protein","comp":"p-ex","src":"src.txt:L12"},
  {"id":"n-rec","label":"<受体1/受体2>","kind":"complex","comp":"p-pm","mods":["P"],"src":"src.txt:L12"},
  {"id":"n-tf-c","label":"<TF>","kind":"protein","comp":"p-cy","data":"<Tf>","src":"src.txt:L8"},
  {"id":"n-tf-n","label":"<TF>","kind":"protein","comp":"p-nu","data":"<Tf>","src":"src.txt:L8"},
  {"id":"n-gene","label":"<Gene1>","kind":"gene","comp":"p-nu","data":"<Gene1>","src":"src.txt:L9"},
  {"id":"n-fb","label":"<Gene1 产物>","kind":"protein","comp":"p-cy","data":"<Gene1>","src":"src.txt:L10"}],
 "edges":[{"id":"e-bind","from":"n-lig","to":"n-rec","type":"bind","src":"src.txt:L12"},
  {"id":"e-p","from":"n-rec","to":"n-tf-c","type":"modify","label":"+P S388","src":"src.txt:L7"},
  {"id":"e-imp","from":"n-tf-c","to":"n-tf-n","type":"transport","label":"nuclear import","src":"src.txt:L8"},
  {"id":"e-tx","from":"n-tf-n","to":"n-gene","type":"activate","label":"transcription","src":"src.txt:L9"},
  {"id":"e-ex","from":"n-gene","to":"n-fb","type":"activate","label":"expression","src":"src.txt:L10"},
  {"id":"e-fb","from":"n-fb","to":"n-rec","type":"inhibit","evidence":"indirect","src":"src.txt:L10"}],
 "texts":[{"id":"t-note","text":"<图下注：数据取值说明、示意未按比例等>","src":"src.txt:L11"}]}
```
其他键：节点 `shape`（覆盖 kind 图元）、`fill`、`stroke`、`dash`、`fs`、`bold`、`aliases`、`xref`（只写材料给出的 ID）、`col`/`rank`（排版提示）；边 `feedback`、`both`、`width`；`canvas.legend_at` "right"|"bottom"（默认自动选能满足最小字号的一种）。手写坐标（cx/cy、panel x/y/w/h、via）仍支持，但只在改材料自带的图时用。图上不写 id、文件名、行号。

## notes.json（第 8 步；只写判断，文件信息由 assemble 自动收集）
```json
{"status": "complete", "status_reasons": ["工单 6 项全部满足；2 条已记录的科学保留见 exceptions"],
 "compliance_checks": [{"requirement": "<工单/任务原文一项>", "result": "pass", "element_ids": ["p-pm", "n-rec", "e-imp"], "evidence": "怎么满足 + 出处（src.txt:L12）"}],
 "exceptions": [{"category": "undecidable", "detail": "TBK1→IRF3 是否直接未检验", "handling": "evidence: hypothesis，图注说明"}],
 "edit_request": "<修改请求原文；演示编辑写“演示编辑（不属于正式图）：…”>", "summary": "<一句话：画了哪张图、多少实体/关系>",
 "fields": {"<某个 contract 字段>": "<只在你想亲自指定该字段内容时写>"}}
```
- compliance_checks 必须覆盖工单每一项（区室、必需关系类型、反馈/分支、命名、格式/宽度/dpi/最小字号、修改请求）；result 用 pass / partial / fail；`element_ids` 写 SVG 里真实存在的 id（check 核对，不存在只给 WARN）。最小字号：build 输出末行和 content_map 的 `layout.fonts.min_pt` 直接给出 pt 值，照抄进 evidence。assemble 会自动追加像素检查一行。
- exceptions 的 category：material_missing / undecidable / contradiction / run_failure / user_request_not_in_source。跳过的像素检查（check_skipped）、缺失的导出格式（run_failure）、build 剩下的版面提示（layout_note），assemble 会自动补录（已写过的不重复）。
- 字段映射（自动）：源文件/spec/svg → editable_source；导出/预览/渲染 → export_artifact；来源/映射/实体/关系/元素 → content_map（含 entities、relations、compartments、legend、data_encoding）；检查/合规/QA → compliance_checks；异常/不确定/问题/缺口 → exceptions；修改/历史 → change_log（含 edit_diff）；图注 → caption；状态 → 一个词；认不出的字段填运行摘要 + 文件清单并记进 `run_notes`。
- **status 只写一个词**：contract 给了词表，assemble 换成它的词；否则 complete / partial / failed。**complete** = SVG + PNG + PDF 都已生成、工单每一项都在 compliance_checks 里且为 pass；原文本身没说清的地方（undecidable / contradiction）已经在图上按证据强度画出并写进 exceptions，这属于如实交付，不降为 partial。**partial** = 有工单项 fail/partial、缺导出格式或材料读不了（status_reasons 逐条写）；没出图 → assemble 强制 failed。notes.json 不写 status 时 assemble 按这条规则自动判断。“材料缺失、无法判断、运行失败”分别用不同 category 写。

## 异常处理
| 情况 | 处置 |
|---|---|
| 方向/作用类型没写清 | `line` 或 `evidence: hypothesis`，exceptions: undecidable |
| 同名基因与蛋白、物种不明 | 按材料写法，`kind` 按语境定，exceptions 记依据 |
| 正文/摘要与数据表矛盾 | 颜色按数据表（colorscale），两处原文都写进 exceptions: contradiction |
| 修改请求引入材料没有的内容 | 照做、src 标工单，exceptions: user_request_not_in_source |
| 节点 > 25 不可读 | 非核心分支合并为一个节点并在 aliases/图注列出，或拆 a/b 两个 panel |
| 渲染器缺失 | render 自动用内置渲染（matplotlib → 标准库矢量 PDF）；没有 PNG 记 run_failure，status partial，不重试 |
| 中文字体缺失 | 保留 SVG + export_log，改英文标签或记 tofu 风险（标准库 PDF 不含中文字形），status partial |

## 不做的事
不编造实体、关系、位点、数值或来源；不把间接画成实线；不手挑数据颜色；不只交位图；图上不留 id/文件名/TODO；不伪造渲染、像素检查或人工确认。
