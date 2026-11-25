---
name: paper-to-academic-pptx-lite
description: 论文转学术 PPT（轻量版）。当任务给出论文/研究材料（PDF、文本、图表数据）和目标模板（target-template.pptx/.potx，可能还有 slide-workorder.json、页数/时长/听众约束），要求交付可编辑 PPTX + PDF/PNG 导出 + 页级证据映射 + 讲稿备注 + 渲染与修改记录时使用。核心：按论文自身贡献重建主线（不按段落搬运），一页一个主张，每页挂到原文图/表/章节/页码并附原文短引，在模板母版与占位符内排版，备注不重复页面，数字逐个回查原文。只写一个 spec.json，页面、证据映射、页级大纲、修改记录都由它生成。纯标准库可运行（自带 pptx_kit.py，无需 python-pptx）。不用于：论文精读结论生成、科研绘图美化、学术写作润色。
---

# 论文转学术 PPT（轻量版）

版本 1.5（2026-11）

## 路径（环境变量优先）
案例 `$CASE_JSON`（默认 `/input/case.json`），材料在 `/input` 下（可能有 `material.json`、`artifacts/slide-workorder.json`、
`target-template.pptx`、`starting-deck.pptx`、论文 PDF）；工作目录 `$WORK_DIR`（`/app/work`）；交付 `$OUT_DIR`（`/app/output`）；
本 Skill 在 `$SKILL_DIR`（`/skills/weekly-skill`）。`K=$SKILL_DIR/scripts/pptx_kit.py`，`C=$SKILL_DIR/scripts/check_result.py`。

## 做法一句话
**你只写一个文件：`$WORK_DIR/spec.json`**（主线 + 每页的标题/要点/图表/备注/证据/时长 + 异常）。`build` 用它生成 PPTX，并在
`$OUT_DIR` 自动写出 `content_map.json`（页级证据映射，含原文短引核对结果和每个数字在论文的页码）、`plan.md`（主线+页级大纲+时长）、
`change_log.md`、`spec.json`（复跑源）。不要另外手写这些文件，时间花在读论文和写好 spec 上。

## 步骤（约 12–16 次调用；每一步的产物都留在磁盘上，随时可交）
1. **读输入**（1 次）：`cat $CASE_JSON; find /input -maxdepth 3 -type f | head -60`，把 material.json、slide-workorder.json、task.md 读完。记下：
   case_id、`output_contract` 全部字段、模式（generate/edit/adapt）、**总页数**（"exactly N" 就正好 N 页）、听众、时长、语言、正文字号下限、
   是否要备注、页脚文字、"source preservation / template inheritance" 之类硬规则。
2. **骨架 + 论文地图 + 模板**（1 次，三条命令连写）：
   `python3 $C --init; python3 $K paper <论文.pdf> $WORK_DIR; python3 $K inspect <模板.pptx>`
   - `--init` 先写出含 case_id 和全部 contract 字段的 result.json（status: partial）。
   - `paper` 写 `paper_flow.txt`（**阅读顺序**，双栏不串行：读正文、抄短引用它）和 `paper.txt`（保留版面：看表格用它），并打印页数、
     各页起始行号、节标题、**全部 Fig./Table 题注+页码**、每页位图数（raster=0 = 矢量图，用 figcrop 取）。
   - `inspect` 列版式名、占位符、主题字体、母版字号。封面→Title Slide 类；正文/图/表→Title and Content 类；对比→Two Content 类。
     spec 的 `layout` 写 inspect 列出的**原名**（写了模板里没有的名字时 build 按页面需要自动选版式并打印 note）。
   - PDF 加密：有 qpdf 就 `qpdf --decrypt`；扫描件（paper 报 almost no text layer）：有 tesseract 就 pdftoppm+OCR；都没有 → 写 partial 并说明。
3. **读论文**（1–3 次）：`sed -n` 分段读 paper_flow.txt：Abstract、Intro 末段（we propose / contributions）、方法要点、每个关键图表所在段、
   Conclusion、Limitations/Discussion。长论文不必整篇贴出，按节标题和行号挑着读；表格数值到 paper.txt 里看。
4. **取图**（1 次，多张图一条命令连写）：`python3 $K figcrop <论文.pdf> <页> "Figure 2" $WORK_DIR/fig2.png`
   按题注定位、去白边、**题注不进图片**（打印出题注原文：缩写后写进 spec 的 `caption`）；多面板图连同 (a)(b) 子图注整体裁出，
   正文绕排的窄图只裁图所在的一侧。看它打印的尺寸和裁剪区文字：应是坐标轴/图例/面板字母。出现 `WARN crop is tiny` 或整段正文 = 裁错了
   → 换页码/写法重试一次，或用 `pdfimages -png -f 页 -l 页 <论文.pdf> $WORK_DIR/pimg` 取原始位图。取不到的图进 exceptions，不画替代曲线、不放占位图。
   **每组关键结果尽量带原图或原表**：方法页用论文的总览/流程图，结果页用数据图或原生表格；全是文字的结果页说服力最弱。
5. **写 spec.json 并 build**（1–2 次）：格式见下面的例子（`python3 $K` 不带参数打印全部字段）。
   `python3 $K build $WORK_DIR/spec.json 2>&1 | tee $WORK_DIR/build.log`
   页数多时可分两个文件写：`build spec.json slides2.json`（第二个文件的 slides 接在后面）。
   build 逐页打印 `placed slide N: ...`（正文进了哪个占位符、多少磅）和 WARN。**WARN 是提示，最多改两轮**：溢出→删字或拆页；
   `quote not found`→到 paper_flow.txt 里照抄一小句；`no evidence`→补上；改不掉的写进 spec 的 `uncertainty`。
6. **渲染 + 组装 + 自检**（1 次，三条命令连写）：
   `python3 $K render $OUT_DIR/presentation.pptx; python3 $C --assemble; python3 $C --paper $WORK_DIR/paper.txt --template <模板.pptx> --min-pt <下限> --slides <N>`
   - render：LibreOffice 出 PDF + `preview/slide-*.png` + pdffonts 实测 + `render.json`（两次尝试各限 120 s；没有渲染器也不报错，照实记录）。
   - `--assemble`：读 spec/记录文件/render.json，按含义填满 contract 的**每一个**键（任何键名、中文名、嵌套都行）。
   - checker：页数、模板母版逐字节比对、数字回查、图表编号对题注、备注、字号、导出页数；结果写回 result.json 的 compliance_checks，
     并写 `slide_audit.md`。FAIL 修（最多两轮）；修不了的（没有渲染器、材料缺失）→ status 写 partial 并写明原因。
7. **看图**（能看图时 1 次）：打开 2–3 张 `preview/slide-*.png`（一张图页、一张表页、一张文字页）。文字出框、图太小、半页空白 → 改 spec 重做第 5–6 步一次。

edit / adapt 模式（有 starting-deck 时）：`template` 填要沿用的那个 pptx；`python3 $K inspect starting-deck.pptx --full > $WORK_DIR/start_text.txt`；
不改的页写 `{"keep": i}`，改字写 `{"keep": i, "replace": {"旧": "新"}}`；旧 deck 的数字和图表号先对论文核实，不一致以论文为准并写进
`change`；checker 加 `--source $WORK_DIR/start_text.txt`。

## spec.json 例子（内容为示例）
```json
{"template": "/input/target-template.pptx", "out": "/app/output/presentation.pptx",
 "footer": "工作单给的页脚文字", "slide_numbers": true, "min_pt": 18, "duration_min": 12,
 "formulas": ["Co3O4", "CeO2"],
 "storyline": {"problem": "低温 CO 氧化需要非贵金属催化剂（Sec. 1, p.1）", "method": "Ce 掺杂 Co3O4，共沉淀法（Sec. 2）",
   "evidence": ["Table 1：T50 285→243 °C", "Fig. 2：250 °C 下 50 h 不失活"], "conclusion": "1 wt% Ce 最优（Sec. 5）", "limits": "未测含水气氛（Sec. 4）"},
 "slides": [
  {"layout": "Title Slide", "role": "title", "title": "Ce 掺杂 Co3O4 的低温 CO 氧化", "subtitle": "作者（期刊 年份）\n组会论文汇报",
   "seconds": 30, "notes": "开场一句话点出核心结论……"},
  {"layout": "Title and Content", "role": "result", "title": "1 wt% Ce 使 T50 从 285 °C 降到 243 °C",
   "table": [["样品", "T50 (°C)", "X250 (%)"], ["Co3O4", "285", "61.0"], ["**1Ce**", "**243**", "**92.4**"]],
   "body": ["2Ce 反而变差：掺杂量有最优值"], "caption": "原文 Table 1（n = 3 均值）", "source_note": "Paper Table 1, Sec. 3.1, p.4",
   "evidence": [{"locator": "Table 1, p.4", "quote": "T50 decreases from 285 °C to 243 °C"}], "seconds": 80,
   "notes": "先看 1Ce 一行，再指出 2Ce 变差。被问误差：原文只给均值（Table 1 脚注）。"},
  {"layout": "Title and Content", "role": "result", "title": "1Ce 在 250 °C 下 50 h 不失活",
   "image": "/app/work/fig2.png", "caption": "原文 Fig. 2：250 °C 稳定性测试，50 h", "body": ["转化率保持 **92%** 以上", "条件：1% CO，GHSV 30 000 h-1"],
   "source_note": "Paper Fig. 2, Sec. 3.2, p.5", "evidence": [{"locator": "Fig. 2, Sec. 3.2, p.5", "quote": "no deactivation within 50 h"}],
   "seconds": 70, "confidence": "high", "notes": "过渡：活性高还不够，要看稳定性……"}],
 "exceptions": {"material_missing": ["补充材料 Fig. S3 未提供"], "undecidable": ["氧空位机理只有 XPS 间接证据"], "run_failures": []},
 "uncertainty": ["Fig. 2 为页面截图裁剪，不是重绘"]}
```
- 每页的 `evidence.quote` = 从 paper_flow.txt **照抄**的一小句（≤ 15 个词，含该页的关键数字最好）；build 会在论文里查它并写核对结果。
- `source_note` 是页面上可见的出处（进模板的来源占位符或页脚上方小字）；`role` 用 title/problem/method/result/conclusion/limits。
- 单位指数自动上标（写 `mA cm-2`、`h-1` 即可）；化学式列进 `formulas` 自动下标；其他上下标写 `Ce^{3+}`、`T_{50}`。
- **版面由 build 负责，你只管内容**：标题写完整的结论句即可，放不下模板字号时自动缩到占位符内（同一版式全篇同一字号，不低于 24 pt）并在
  短语边界断行；图 + 要点自动在"上图下文 / 左文右图"里选图更大的排法；正文、图下要点、表格字号按空间自动取（不低于 `min_pt`）。
  这些调整逐条写进 change_log.md（"size fit ..."），母版/版式/主题不动。不要写 `font_size`、`image_box` 去手调，除非 build 报 WARN。
- 一页放一张图或一张表；图旁/图下要点 ≤ 3 条。模板的"图片版式"占位符小，只放接近方形的图。

## 页面写法（听众打开 PDF 第一眼看到的就是这些）
- **证据页**（每组关键结果一页）：标题 = 带关键数字的结论句（中文 ≤ 26 字，英文 ≤ 12 词）；一张原图或一张原生表 + 1–3 条要点
  （每条 ≤ 20 字，关键数字 `**加粗**`，写清条件：圈数/倍率/温度/数据集/样本数）。
- **表格页**：原生表格只留支撑主张的列和行（≤ 5 列、≤ 7 行，其余进备注），数值逐格从 paper.txt 抄，表头带单位，主张所在行加粗。
- **文字页**（动机/方法/局限/结论）：3–5 条，每条带具体对象、条件或数字；"已有方案 vs 本文"用两栏（body/body2）。
- 必备页：题目、问题/动机、方法（1–2）、结果（每组关键证据 1 页）、结论、局限（可与结论合页）；页数按工作单，没给就 ≈ 1 页/分钟。

## 内容规则（每条针对一种常见失败）
1. **主线不是目录**：页序按"问题→方法→证据→结论"，不按论文章节逐段搬；Related Work 最多 1 页或并入动机。贡献以作者原话为准。
2. **标题写主张**：结果页标题是一句结论，不是 "Results"；方法页标题说做法。
3. **数字零改写**：数值、单位、样本量、p 值、条件照原文，不取整、不换算。自己算的数（"提升 15%"）要么删，要么标"由 Table 1 计算"并给算式。
4. **图表编号对齐**：页上写"原文 Fig. 3b / Table 2"，编号必须在题注列表里；补充材料写 "Fig. S2" 并说明是否提供。
5. **示意图不是数据**：流程图/概念图的 caption 写"示意图，非实测数据"。
6. **他人结果**：文献里的数写"[n] 报道"，不混进本文贡献页。
7. **备注不重复页面**：每页 notes 2–4 句：过渡语、要强调的一点、被问到时的补充证据（原文位置）。与页面文字重合过半就重写。
8. **模板约束**：只用模板版式与占位符；不改母版/主题/字体/配色；页脚、页码沿用模板（`footer`、`slide_numbers`）；不加装饰。
9. **缺口不编造**：图提取失败、公式是图片、数据缺失、页数放不下全部证据 → 写进 `exceptions` 并说明取舍。

## result.json（由 `--assemble` 写；需要改口径时把同名键写进 spec.json 或 `$WORK_DIR/facts.json`）
- 可编辑源 / editable_source → pptx、spec、复跑命令、页数、各页标题；导出 / export_artifact → pdf、png、页数、渲染器版本、pdffonts 字体、替代字体。
- 证据映射 / content_map → 每页：主张、证据定位+原文短引+核对结果、数字及其论文页码、视觉来源、备注摘要、时长、置信度。
- 合规检查 / compliance_checks → checker 逐项 PASS/WARN/FAIL + 依据；exceptions → 材料缺失 / 无法判断 / 运行失败**分开列**。
- **status 只写一个词**：contract 给了取值就用它的词，否则 complete / partial / failed。complete = pptx 与 pdf 都有、页数合规、checker PASS、
  每页有证据；否则 partial（原因在 status_reasons）；没产出 pptx 才是 failed。不声称没做过的检查，不写没产生的文件。

## 异常处理速查
| 情况 | 做法 |
|---|---|
| 没有 python-pptx | 正常，pptx_kit.py 纯标准库 |
| soffice 缺失/超时/崩溃 | render 自动换 profile 重试一次；仍失败 → status=partial，render.json 的 errors 自动进 exceptions.run_failures，不声称有预览 |
| 模板缺某版式/占位符 | 换最接近的版式；仍放不下 → `image_box`/`table_box`（英寸）显式定位，在 `uncertainty` 说明 |
| 页数超限 | 合并支撑性细节、移到备注；不删主线必需页 |
| 中文字体缺失 | 不改模板字体；render.json 记录实际替代字体 |
| figcrop 找不到题注 / 没有 poppler | 看它打印的块开头，换写法（"Fig. 2"/"图 2"）或换页；仍失败 → 原生表格/文字页 + exception（不会抛 traceback） |
| spec 里的图片文件不存在 | build 不中断：该页不带图并打印 WARN，content_map 记"NOT inserted"；补裁图后重建，或写进 exceptions.material_missing |
| spec.json 语法错 | build 会指出行号；常见是字符串里的引号没转义或多了逗号 |
| 时间快用完 | 先保证第 5、6 步各跑过一次（pptx + result.json 已在磁盘上），再做改进 |

更多：`resources/checklist.md`（交付前核对表）、`resources/pptx_xml.md`（不经 kit 直接改 XML 的配方）、`examples/README.md`（完整示例）。
