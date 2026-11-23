---
name: paper-to-academic-pptx-lite
description: 论文转学术 PPT（轻量版）。当任务给出论文/研究材料（PDF、文本、图表数据）和目标模板（target-template.pptx/.potx，可能还有 slide-workorder.json、页数/时长/听众约束），要求交付可编辑 PPTX + PDF/PNG 导出 + 页级证据映射 + 讲稿备注 + 渲染与修改记录时使用。核心：按论文自身贡献重建主线（不按段落搬运），一页一个主张，每页挂到原文图/表/章节/页码，在模板母版与占位符内排版，备注不重复页面，数字逐个回查原文。纯标准库也能运行（自带 pptx_kit.py，无需 python-pptx）。不用于：论文精读结论生成、科研绘图美化、学术写作润色。
---

# 论文转学术 PPT（轻量版）

## 路径（环境变量优先）
案例 `$CASE_JSON`（默认 `/input/case.json`），材料都在 `/input` 下（可能有 `material.json`、`artifacts/slide-workorder.json`、
`target-template.pptx`、`starting-deck.pptx`、论文 PDF）；工作目录 `$WORK_DIR`（`/app/work`）；交付 `$OUT_DIR`（`/app/output`）；
本 Skill 在 `$SKILL_DIR`（`/skills/weekly-skill`）。`K=$SKILL_DIR/scripts/pptx_kit.py`。改文件用 python，不用 `sed -i`。

## 三种模式（看 case/工作单里的 mode；没写就按有无 starting-deck 判断）
- **generate**：论文 + 模板 → 新建全部页（下面的默认流程）。
- **edit**：spec 的 `template` 填 starting-deck；没要求改的页用 `{"keep": i}` 原样保留（source preservation），改的页用 keep+`replace`
  或按模板版式新建；每轮另存 `presentation_v1.pptx`…，最终版名按工作单。
- **adapt**：`template` 填 target-template；先 `python3 $K inspect starting-deck.pptx --full` 抽每页文字（按角色）/表格行/图/备注，`unzip -o starting-deck.pptx 'ppt/media/*' -d $WORK_DIR/start`
  取图，**每一页**都迁到目标版式（不只封面）。旧 deck 只是排版来源：它的每个数字、图/表号先在 paper.txt 里核对（grep），不一致**以论文为准**，
  写 `$WORK_DIR/corrections.md`（`旧页 | deck 写法 | 论文写法+位置 | 处理`）并记入 change_log。edit/adapt 都把 inspect 输出存成 `$WORK_DIR/start_text.txt`。

## 步骤（目标 ≤ 25 次调用；先交骨架，再逐步替换）
1. **读输入**（2 次）：`cat $CASE_JSON`；`find /input -maxdepth 3 -type f | head -60`；把 `material.json`、`slide-workorder.json`、task.md
   全读完。记下：case_id（case_id/caseId/id）、`output_contract` 全部字段、**模式**（generate/edit/adapt）、**总页数**（"exactly N"
   就必须正好 N 页）、听众、时长、语言、模板路径、是否要备注、"source preservation / template inheritance" 之类硬规则。
2. **骨架**（第 3 次调用内）：`python3 $SKILL_DIR/scripts/check_result.py --init` → result.json 含 case_id、每个 contract 字段、`status: partial`；之后每步更新。
3. **工具探测 + 论文地图**（2 次）：
   `for t in pdftotext pdftoppm pdfimages pdffonts soffice tesseract qpdf; do command -v $t >/dev/null && echo "have $t"; done; python3 -c "import pptx" 2>/dev/null && echo have python-pptx`
   `python3 $K paper paper.pdf $WORK_DIR` → 写 `paper.txt`（`\f` 分页），打印页数、各节标题+页码、**全部 Fig./Table 题注+页码**（双栏右栏的题注也在）、
   每页位图数（raster=0 说明是矢量图，只能用 figcrop 取）。之后按需 `sed -n` 读 paper.txt 的相关段，不整篇贴进对话。
   PDF 加密：有 qpdf 就 `qpdf --decrypt`，没有就列为 exception。扫描件（paper 报 "almost no text layer"）：有 tesseract 就 pdftoppm+OCR，否则只能写 partial。
4. **主线卡**（1 次，写 `$WORK_DIR/storyline.md`）：问题/缺口 → 方法 → 关键证据（2–4 组，各挂 Fig/Table/Sec + 页码）→ 结论 → 局限。
   贡献以作者原话为准（Abstract、Intro 的 "we propose/contributions"、Conclusion），**主结论与支撑细节分开**；他人工作（Intro/Related Work 引用的数）
   不能写成本文结果。
5. **页级大纲**（写 `$WORK_DIR/plan.md`，每页一行）：`页 | 角色 | 主张句（标题）| 证据（Fig/Table/Sec/页码/原句短引）| 视觉 | 备注要点 | 时长(秒)`。
   页数：按工作单；没给就按时长 ≈ 1 页/分钟，上限内取舍。必备页：题目、问题/动机、方法（1–2）、结果（每组关键证据 1 页）、结论/局限、（致谢/Q&A 按模板）。
6. **看模板**（1 次）：`python3 $K inspect target-template.pptx`：版式名、占位符 type/idx/位置、主题字体颜色、母版字号、样例页。
   为每页选版式（封面→Title Slide/标题幻灯片；正文→Title and Content；左右对比→Two Content；节→Section Header）。模板样例页不保留（除非工作单要求）。
   正文进版式里**面积最大**的 body/obj 占位符；名字含 Source/Note/Ref/来源 的小占位符放出处（spec 的 `source_note`），图片版式的小 body 放图注。
   **字号阶梯**：标题 = 母版标题字号；正文 ≥ 工作单下限（没给就 18 pt）；表格 ≥ 14；图注 14；出处 11–12。
7. **图表素材**（2–4 次）：原图用 `python3 $K figcrop paper.pdf 页 "Figure 2" $WORK_DIR/fig2.png`（按题注定位，自动去白边，**图注不进图片**，
   打印题注原文与宽高比：题注写到 spec 的 `caption`，可编辑可读）。核对打印的裁剪区文字：应是坐标轴/图例/面板字母；出现整段正文说明裁错了，
   改用 `pdfimages -list` 找原始位图（`pdfimages -png -f 页 -l 页 paper.pdf $WORK_DIR/pimg`）。表格优先做成**原生表格**（spec 的 `table`），
   数值逐格从 paper.txt 抄，表头保留单位。示意图/流程图只能当示意（caption 写"示意图，非实测数据"）。没法取到的图写进 exceptions，不画替代曲线。
8. **写 spec 并构建**（2–4 次）：写 `$WORK_DIR/spec.json`（格式见 `python3 $K` 的帮助），`"out": "$OUT_DIR/presentation.pptx"`（工作单另有文件名就用它），
   `python3 $K build $WORK_DIR/spec.json | tee $WORK_DIR/build.log`。内容/图/表页加 `"source_note": "Paper Fig. 2, p.5"`（页上可见的出处），spec 顶层加 `"min_pt": 18`。
   build 每页打印 `placed slide N: body->ph obj idx1 ...`：核对正文进了大占位符。**WARN 是提示：最多重建 2 轮**（删字/拆页/换版式），剩下的写进 uncertainty：溢出→删字/拆页/换大版式（`font_size` 不低于字号阶梯）；
   没有占位符→换版式；replace 未命中→查原文。两轮后剩余的 WARN 写进 uncertainty。
9. **渲染**（1 次）：`python3 $K render $OUT_DIR/presentation.pptx` → `presentation.pdf`、`preview/slide-*.png`、pdffonts 实测、`render.json`（soffice 两次尝试各限 120 s、换 profile；pdftoppm/pdftocairo 限时；找不到 LibreOffice 也不报错，照实写进 render.json 的 errors）。
   render 的 status 不是 `rendered` → 不声称有预览，result 的 status 写 partial，原因进 exceptions.run_failures。能看图就打开 2–3 张 PNG 目检。
10. **记录 + 组装 + 自检**（2–3 次）：写 `content_map.json`（每页一行，见下）、`change_log.md`、`plan.md` 复制到 `$OUT_DIR`。
   把已知事实写进 `$WORK_DIR/facts.json`（只写有的：`content_map`、`compliance_checks`、`exceptions`{material_missing, undecidable, run_failures}、`uncertainty`、`change_log`、`status_reasons`）。然后 `python3 $SKILL_DIR/scripts/check_result.py --assemble` → 按含义填满 contract 的**每一个**键（任何键名、中文名、嵌套子字段；facts 里同名键原样采用；缺的文件自动跳过，不留骨架字样），再跑
   `python3 $SKILL_DIR/scripts/check_result.py --paper $WORK_DIR/paper.txt --template <模板路径> --min-pt <下限> [--slides N] [--source $WORK_DIR/start_text.txt]`
   有旧 deck 才加 --source（抓只在旧 deck 出现的数字、图号与题注不符）。checker 还查主张标题（"Results" 这类话题标题报 WARN）和页型覆盖，并写 `$OUT_DIR/slide_audit.md`（逐页偏差记录）。FAIL 修，最多两轮；修不了的（没有渲染器、材料缺失）就 status=partial 写明原因。build/checker 的 WARN 是提示，不要为清 WARN 反复重建。

## 页面模式（听众和读者打开 PDF 第一眼看到的就是这些）
- **证据页**（每组关键结果一页）：Title and Content 版式；标题 = 带关键数字的结论句（中文 ≤ 26 字，最多 2 行）；`image`（或 `table`）+ `body` 1–3 条
  要点（每条 ≤ 20 字，关键数字加粗 `**88.8%**`，写条件：圈数/倍率/温度/样本数）。宽图（宽高比 ≥ 1.45）或 ≥ 4 列的表，build 自动排成**上图满宽、下方要点**；
  `caption` 写 "原文 Fig. 2a–b：<题注要点+条件>"，`source_note` 写 "Paper Fig. 2, Sec. 3.1, p.3"。
- 模板的"图片版式"（图片占位符小、标题在下方）只放接近方形的图；宽的多面板图放它会缩成看不清的小图，build 报 `figure is only ...` → 换 Title and Content。
- **表格页**：原生表格只留支撑主张的列和行（≤ 5 列、≤ 7 行，其余进备注），把主张所在的行/数加粗（单元格写 `**99.62**`）；build 自动选字号（≥ 14）和按内容分配列宽。
- **文字页**（动机/方法/局限）：3–5 条，每条带具体对象、条件或数字；"已有方案 vs 本文"用两栏版式（body/body2）。少于 3 条就并页或配原文的图/表，不留半页空白。
  文字页**不写 `font_size`**：build 用模板字号，估算放不下时自动降到能放下的最大字号（≥ `min_pt`，placed 行标 auto-fit）。
- 每页只讲一件事；同一张图的两个面板讲两件事且页数允许时，可分两页各裁一个面板（figcrop 后用 `image_box` 或拆图都要在 caption 写清面板号）。

## 内容规则（每条都针对一种已知失败）
1. **主线不是目录**：页序按"问题→方法→证据→结论"，不是按论文章节逐段搬；Related Work 最多 1 页或并入动机。
2. **标题写主张**：结果页标题是一句结论（"1 wt% Ce 使 T50 降低 42 °C"），不是 "Results"；方法页标题说做法。
3. **单页密度**：正文 ≤ 5 条要点、每条 ≤ 2 行，二级要点 ≤ 2 层；论文长句改写成短语，但术语、符号、单位与原文一致。
4. **数字零改写**：数值、单位、样本量、p 值、条件（温度、数据集、划分）照原文；不取整、不换算；每个数在 content_map 有原文出处。
   原文没有的数（"提升约 50%" 这类自己算的）要么删，要么标"由 Table 1 计算"并给算式。
5. **图表编号对齐**：页面上写"原文 Fig. 3 / Table 2"，引用的编号必须在题注列表里存在；子图写全（Fig. 3b）；从补充材料来的写 "Fig. S2"。
6. **他人结果**：引用文献里的数要写"[n] 报道"，不能混进本文贡献页（checker 对论文里只出现在 [n] 旁、页上又没标出处的数报 WARN）。
7. **备注不重复页面**：每页 notes 写 2–4 句：过渡语、要强调的一点、被问到时的补充证据（原文位置）、本页时长。和页面文字重合超过一半就重写。
8. **模板约束**：只用模板版式与占位符；不改母版/主题/字体/配色；页脚、页码沿用模板（spec 设 `footer`、`slide_numbers`）；不加装饰性文本框。
9. **缺口不编造**：图提取失败、公式是图片、数据缺失、页数不够放下全部证据——写 exceptions 并说明取舍，不补造数据、不放占位图。

## 交付物（`$OUT_DIR`）
`presentation.pptx`（可编辑）、`presentation.pdf`、`preview/slide-*.png`、`slide_audit.md`、`content_map.json`、`plan.md`（复制 work 里的大纲，含时长）、
`change_log.md`（构建次数、每次改了什么、WARN 如何处理、字体实测）、`spec.json`（复跑：`python3 pptx_kit.py build spec.json`）、`result.json`。

content_map 每行：`{"slide": 3, "role": "结果", "claim": "标题原文", "evidence": [{"source": "paper.pdf", "locator": "Table 1, p.2",
"quote": "T50 drops from 285 °C to 243 °C"}], "numbers": ["285 °C", "243 °C"], "visual": "原生表格（Table 1 数值）| 原图裁剪 fig2.png | 无",
"notes_summary": "...", "confidence": "high|medium|low", "uncertainty": "..."}`。

## result.json 映射（任何键名风格都按含义对应；嵌套字段按子字段填）
实际写入用 `check_result.py --assemble`（它按含义映射任意键名）；下面是各键应含的内容，写进 facts.json 的同名键会原样采用。
- 演示文件 / editable_source / 可编辑演示文件 → `{"pptx": "/app/output/presentation.pptx", "spec": ".../spec.json", "rebuild": "命令", "slides": N, "layouts_used": [...]}`
- 导出 / export_artifact / 渲染 → `{"pdf": ".../presentation.pdf", "png": [...], "pages": N, "renderer": "LibreOffice 版本", "fonts": "pdffonts 实测", "substitutions": [...], "slide_audit": ".../slide_audit.md"}`
- 证据映射 / content_map / 页级证据映射 → content_map 内联列表 + 文件路径
- 合规检查 / compliance_checks → 列表：页数、模板继承（checker 的 template 行）、备注齐全、无溢出 WARN、数字回查、预览页数、字体，每项 `PASS/FAIL/WARN + 依据`
- 渲染与版本记录 → 源文件、导出件、字体/模板、slide_audit.md、构建与修改记录（含 corrections.md）；exceptions / 不确定性 → 材料缺失、无法判断、运行失败**分开列**
- 另写 `source_map`、`change_log`、`uncertainty`、`material_gaps`、`status_reasons`。
- **status 只写一个词**：contract 列了取值就用它的词，否则 complete / partial / failed。complete = pptx+pdf 都有、页数合规、checker PASS、
  每页有证据；否则 partial（原因写 status_reasons）；没产出 pptx 才是 failed。

## 异常处理速查
| 情况 | 做法 |
|---|---|
| 没有 python-pptx | 正常，pptx_kit.py 纯标准库 |
| soffice 缺失/超时/崩溃 | render 已自动换 profile 重试；仍失败 → status=partial，render.json 的 errors 进 exceptions.run_failures，不声称有预览 |
| 模板缺某版式/占位符 | 换最接近的版式；仍放不下 → 用 `image_box`/`table_box` 显式定位，并在 compliance 里说明 |
| 页数超限 | 合并支撑性细节、移到备注，绝不删主线必需页 |
| 中文字体缺失 | 不改模板字体；在 render 记录写实际替代字体（pdffonts） |
| figcrop 找不到题注 | 看打印的块开头，换写法（"Figure 2"/"图 2"）或换页；仍失败则用原生表格/文字页并列 exception |
