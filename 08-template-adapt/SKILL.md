---
name: academic-pptx-template-adapter-lite
description: 学术 PPT 模板与格式适配（轻量版）。任务给出目标模板（target-template.pptx/.potx）和要套进去的内容（旧模板 deck、论文 PDF、提纲，可能有 slide-workorder.json 规定页数/时长/字号/页脚），要求交付真正继承目标母版与版式的可编辑 PPTX、PDF/PNG 导出、页级证据映射、讲稿备注、渲染与修改记录时使用。核心：读模板结构定"角色→版式→占位符"表和字号阶梯；旧 deck 的数字与图号先和论文对账（以论文为准，记录更正）；按"问题→方法→证据→结论→局限"排页、标题写主张；内容写进最大的正文占位符、来源写进模板的来源/注释占位符；溢出靠删字/拆页/换版式；导出后逐页审计。自带纯标准库 pptx_kit.py 与 check_result.py（无需 python-pptx）。不用于：改写论文结论、科研绘图、语言润色。
---

# 学术 PPT 模板与格式适配（轻量版）

## 路径（环境变量优先）
案例 `$CASE_JSON`（默认 `/input/case.json`），材料在 `/input`；工作目录 `$WORK_DIR`（`/app/work`）；交付 `$OUT_DIR`（`/app/output`）；
Skill 在 `$SKILL_DIR`（`/skills/weekly-skill`）。`K=$SKILL_DIR/scripts/pptx_kit.py`，`C=$SKILL_DIR/scripts/check_result.py`。改文件用 python，不用 `sed -i`。

## 什么叫"真的套用了模板"（交付后会被逐页复核，checker 会验）
- 母版、版式、主题部件原样来自目标模板（逐字节一致）；每页 rels 指向目标版式；模板样例页删除。
- 标题/正文/图注写进版式**占位符**（`<p:ph>` 的 type/idx 与版式一致），字体、颜色、位置靠继承；run 上不写字体名和颜色。
- 页脚、页码用版式的 ftr/sldNum 占位符（spec 的 `footer`、`slide_numbers`），不自己画文本框。
- 页内文字、数字、图号与**论文**一致（旧 deck 只是排版来源，不是事实来源）。

## 步骤（目标 ≤ 25 次调用；每步做完就更新 result.json）
1. **读输入**（1–2 次）：`cat $CASE_JSON; find /input -maxdepth 3 -type f | head -60`，读 material/workorder/task.md。记下 case_id、
   `output_contract` 全部字段、页数（"exactly N"）、时长、听众、语言、页脚、字号下限、备注要求、导出要求、其他硬规则。
   入口：有 starting deck → **adapt**（迁移 + 对账）；只有论文 + 模板 → **generate**（建主线）；要求在原 deck 上小改 → **edit**（`keep`）。
2. **骨架**（第 3 次调用内）：`python3 $C --init` → result.json 含 case_id、每个 contract 字段、`status: partial`。
3. **读模板 + 工具探测**（1 次）：
   `python3 $K inspect <模板>; for t in soffice pdftoppm pdftotext pdffonts; do command -v $t >/dev/null || echo "missing $t"; done`
   写 `$WORK_DIR/template_spec.md`：尺寸；**角色→版式→占位符表**（封面/节/要点/双栏/图/表/结论 各用哪个版式、正文进哪个 idx——
   选面积最大的 body/obj；名字含 Source/Note/Ref/来源 的小占位符专放出处；pic 占位符放图、同版式的小 body 放图注。模板的"图片版式"若图片占位符小
   （< 页宽 2/3），只给接近方形的图用，宽图（宽高比 ≥ 1.45）进正文版式，见"页面模式"）；
   主题字体（latin/ea）与主题色；**字号阶梯**：标题=母版标题字号，正文 ≥ 工作单下限（没给就 18 pt），表格 ≥ 14，图注 14，出处 11–12。
   模板缺某角色的版式：用最接近的版式 + `image_box/table_box`，写进 compliance。
4. **读内容**（1–2 次）：`python3 $K paper paper.pdf $WORK_DIR` → 写 `paper.txt`（`\f` 分页），打印各节标题+页码、**全部 Fig./Table 题注+页码**
   （双栏右栏的也在）、每页位图数；之后按需 `sed -n` 读相关段，不整篇贴进对话。
   adapt：`python3 $K inspect starting-deck.pptx --full > $WORK_DIR/start_text.txt`；`unzip -o -q starting-deck.pptx 'ppt/media/*' -d $WORK_DIR/start`。
5. **事实对账**（adapt 必做，1 次）：旧 deck 里每个数字、单位、图/表号、引用号，在 paper.txt 里找到对应句（grep）。写
   `$WORK_DIR/corrections.md`：`旧页 | deck 写法 | 论文写法 + 位置 | 处理`。不一致**以论文为准**并记入 change_log；论文里找不到的内容
   标 "deck-only, unverified" 或删掉；图号按题注内容对（deck 的 "Fig. 3 光照曲线" 若论文 Fig. 2 才是光照曲线，改成 Fig. 2）。
6. **页级大纲**（写 `$WORK_DIR/plan.md`，每页一行）：`页 | 角色 | 主张标题 | 证据位置(Fig/Table/Sec/页) | 版式 | 视觉 | 备注要点 | 秒`。
   顺序"问题→方法→关键证据(每组 1 页)→结论→局限"；结果页标题写结论句，不写 "Results"；页数按工作单（没给按 ≈1 页/分钟）。
   adapt：旧 deck **每一页**都有去向（迁移/拆分/合并/删除+理由），过载页拆开，不能只做前几页。
7. **写 spec 并构建**（2–4 次）：`$WORK_DIR/spec.json`，然后 `python3 $K build $WORK_DIR/spec.json | tee $WORK_DIR/build.log`。
   ```json
   {"template": "/input/target-template.pptx", "out": "/app/output/presentation.pptx", "footer": "工作单页脚", "slide_numbers": true, "min_pt": 18,
    "slides": [
     {"layout": "封面版式名", "title": "论文题目", "subtitle": ["作者 | 场合"], "notes": "开场 2 句 + 时长"},
     {"layout": "要点版式名", "title": "主张句", "body": ["要点", "  二级要点"], "source_note": "Paper Sec. 2, p.1", "notes": "..."},
     {"layout": "图版式名", "title": "主张句", "image": "/app/work/start/ppt/media/image1.png", "caption": "Fig. 2 原题注", "source_note": "Paper Fig. 2, p.2", "notes": "..."},
     {"layout": "要点版式名", "title": "主张句", "table": [["Catalyst", "T50 (°C)"], ["A", "285"]], "caption": "Table 1 原题注", "source_note": "Paper Table 1, p.2", "notes": "..."}]}
   ```
   其他键：`body2`（双栏右列）、`ph: {"idx": [...]}`（指定占位符）、`image_box/table_box`（英寸）、`keep`/`replace`（edit 模式）。
   **图源**：旧 deck 的图（`$WORK_DIR/start/ppt/media/`）先按内容和论文题注对上号；论文里的图用 `python3 $K figcrop paper.pdf 页 "Fig. 2" $WORK_DIR/fig2.png`
   （去白边、**题注不进图片**，打印题注原文写到 `caption`；打印 `WARN no figure pixels` = PDF 里没有这张图 → 不放，记 material_gaps）。
   **字号**：正文不写 `font_size`（用模板字号，放不下时 build 自动降到能放下的最大字号，≥ `min_pt`，placed 行标 auto-fit）；表格不写 `table_size`
   （build 按内容选 ≥ 14 pt 的最大字号并分配列宽）。下标/上标写 `Al_{2}O_{3}`、`cm^{-1}`、`Ce^{3+}`（页上是真下标/上标；旧 deck 的 "C"、"cm-1" 顺手改成论文写法并记 corrections）。
   build 每页打印 `placed slide N: body->ph obj idx1 ... 9.0x4.7in 32pt`——**核对正文进了大占位符、出处进了来源占位符**。WARN 是提示，最多重建 2 轮：
   溢出 → 删冗余字（不删数字和结论）→ 拆页（页数允许时）→ 换容量更大的版式 → 最后才 `font_size`，且不低于下限；两轮后剩下的写进 uncertainty。
8. **渲染**（1 次）：`python3 $K render $OUT_DIR/presentation.pptx`（adapt/edit 在同一次调用里再渲染旧稿供对照：
   `cp /input/starting-deck.pptx $WORK_DIR/v0.pptx && python3 $K render $WORK_DIR/v0.pptx && mkdir -p $OUT_DIR/versions && cp $WORK_DIR/v0.pdf $OUT_DIR/versions/v0_before.pdf`，失败不影响交付）→ `presentation.pdf`、`preview/slide-*.png`、pdffonts 实测、`render.json`（soffice 两次尝试各限 120 s、换 profile；pdftoppm/pdftocairo 限时；找不到 LibreOffice 也不报错，照实写进 render.json 的 errors）。
   render 的 status 不是 `rendered` → 不声称有预览，result 的 status 写 partial，原因进 exceptions.run_failures。能看图就打开 2–3 张**图/表页**的 PNG（100 dpi）目检：
   图的坐标轴字能读、表格不挤在页顶、拆开的页不空半页。
9. **记录 + 组装 + 自检**（2–3 次）：写 `content_map.json`、`change_log.md`，`template_spec.md`/`plan.md`/`corrections.md` 复制到 `$OUT_DIR`。
   把已知事实写进 `$WORK_DIR/facts.json`（只写有的：`content_map`、`compliance_checks`、`exceptions`{material_missing, undecidable, run_failures}、`uncertainty`、`change_log`、`status_reasons`）。然后 `python3 $SKILL_DIR/scripts/check_result.py --assemble` → 按含义填满 contract 的**每一个**键（任何键名、中文名、嵌套子字段；facts 里同名键原样采用；缺的文件自动跳过，不留骨架字样），再跑
   `python3 $C --template <模板> --paper $WORK_DIR/paper.txt --source $WORK_DIR/start_text.txt --slides N --min-pt <下限> --baseline /input/starting-deck.pptx --edit-map <新页:旧页,…>`
   generate 去掉 --source/--baseline/--edit-map。`--edit-map` 照 plan.md 写每个新页来自旧 deck 哪一页（拆页写两次，如 `7:7,8:7`；新增页不写）→ `$OUT_DIR/version_diff.md`
   逐页列出旧稿删掉的行（-）和新稿加的行（+）：这就是可逐页核对的修改记录。checker 同时写 `$OUT_DIR/slide_audit.md`（逐页：版式、占位符、散装框、图片比例误差、最小字号、备注、PDF 丢字），
   并在**最后**把判定写回 result.json：合规列表追加 `by: check_result.py` 的行（页数、模板逐字节、数字回查、图表号、备注、导出、字号、逐页修改记录）和 `checker_record`
   （命令、FAIL/WARN 原文）——所以它必须在 assemble 之后跑，重跑会替换旧行，不要手改这些行；facts 里只写 checker 测不到的（页脚页码、版式覆盖）。FAIL 修，最多两轮；修不了的（没有渲染器、材料缺失）就 status=partial 写明原因。build/checker 的 WARN 是提示，不要为清 WARN 反复重建。

## 页面模式（听众和读者打开 PDF 第一眼看到的就是这些）
- **图页**：宽图（宽高比 ≥ 1.45）放正文版式（`image` + `caption` + `body` 1–2 条要点），build 自动排成上图满宽、下方要点；模板的图片版式只放接近方形的图。
  build 报 `figure is only ...` → 换正文版式。`caption` 写论文编号 + 题注要点（"Fig. 2. CO conversion vs temperature, four catalysts"），`source_note` 写位置。
- **表格页**：原生表格，只留支撑主张的列和行（≤ 5 列、≤ 7 行），主张所在行加粗（单元格写 `**243**`）；表下 1 条结论要点，不留半页空白。
- **过载页**（旧 deck 一页 > 6 条或 > 2 行的长句）：按"证据 / 解释与边界"拆成两页，每页 3–4 条短句，标题各写一个主张；拆分写进 corrections/change_log。
- **文字页**：3–5 条，每条带对象、条件或数字；少于 3 条就并页或配论文的图/表。标题是主张句（"Pt/Al_{2}O_{3} 在 250 °C 以下被 CO 自中毒"），不写 "Method"、"Results"。
- **旧 deck 的话题标题**（"Light-off curves"）改成主张句，旧图号按论文题注改正，数字以论文为准——这三类改动都会出现在 version_diff.md 里，供逐页核对。页面上只写论文的正确值；"旧稿写的是 96%" 这类更正说明写进备注和 corrections.md，不上页（旧的错数上页会被 checker 当成带错）。

## 规则（每条针对一种已知失败）
1. **不覆盖模板**：不改母版/版式/主题，不在 run 上写字体颜色，不加装饰形状；checker `--template` 必须 PASS。
2. **论文优先**：数字、单位、条件、样本量照论文；旧 deck 的错误不带进新稿（checker `--paper` 抓"只在旧 deck 出现的数字"和"图号与题注内容不符"）。
   自己算的数写"由 Table 1 计算"；他人工作的数写"[n] 报道"，不混进本文结果。
3. **不靠缩字硬塞**：字号阶梯见第 3 步；放不下就删字、拆页、换版式，写进 change_log。
4. **图不变形、号不错位**：图片只做等比缩放（kit 默认，checker 查比例误差 > 3%）；图注保留论文编号与写法，整册统一（"Fig. N" 或 "图 N"）。
5. **整册一致**：所有页的标题都在 ph:title；每页有页脚和连续页码；每张内容/图/表页有出处（source_note）；备注每页都有。
6. **备注是讲稿**：2–4 句：过渡语、要强调的一点、被追问时的补充证据位置、本页时长；不复读页面。
7. **缺口不编造**：取不到的图、论文没有的数、模板缺的版式、字体替换，写 exceptions，不画替代图、不补造数。

## 交付物（`$OUT_DIR`）
`presentation.pptx`、`presentation.pdf`、`preview/slide-*.png`、`slide_audit.md`、`template_spec.md`、`plan.md`、`corrections.md`（adapt）、
`content_map.json`、`change_log.md`、`version_diff.md`（adapt：逐页改前/改后）、`versions/v0_before.pdf`（旧稿渲染，对照用）、`spec.json`（复跑：`python3 pptx_kit.py build spec.json`）、`result.json`。

content_map 每行：`{"slide": 5, "role": "结果", "claim": "标题原文", "layout": "图版式名", "placeholders": {"title": "title", "image": "pic idx1", "caption": "body idx2", "source": "body idx13"},
"from": "starting-deck slide 5（adapt）| null", "evidence": [{"source": "paper.pdf", "locator": "Fig. 2, p.2", "quote": "题注或原句短引"}],
"numbers": ["243 °C"], "corrections": ["deck 'Fig. 3' -> paper Fig. 2"], "notes_summary": "...", "confidence": "high|medium|low"}`。

## result.json 映射（按含义对应任何键名风格；嵌套按子字段填；文件字段给绝对路径）
实际写入用 `check_result.py --assemble`（它按含义映射任意键名）；下面是各键应含的内容，写进 facts.json 的同名键会原样采用。
- 可编辑演示文件 / editable_presentation / editable_source → `{"pptx", "spec", "rebuild": 命令, "slides": N, "template": 模板路径, "layouts_used": [...],
  "slide_structure": [{"slide", "role", "claim", "layout", "visual", "notes": true}], "template_result": "N 个母版/版式/主题部件逐字节一致；N 页全部用模板版式"}`
- 页级证据映射 / slide_evidence_map / content_map → content_map 内联列表 + 文件路径
- 渲染与版本记录 / render_and_version_record / export → `{"pptx", "pdf", "png": [...], "pages", "renderer": soffice 版本, "fonts": pdffonts 实测,
  "substitutions": 替代字体, "slide_audit": slide_audit.md 路径, "change_log": [...], "build_runs": N, "checker": "PASS/FAIL 摘要"}`
- compliance_checks → 模板继承、版式覆盖全部页、正文占位符、字号下限、溢出 WARN 清零、图片比例、编号对账、页脚页码、备注、PDF 页数、字体，每项 `PASS/FAIL/WARN + 依据`
- 另写 `source_map`、`uncertainty`、`material_gaps`、`exceptions`（**材料缺失 / 无法判断 / 运行失败分开列**）、`status_reasons`。
- **status 只写一个词**：contract 有取值就用它的；否则 complete / partial / failed。complete = 页数合规、PDF 页数一致、checker PASS；否则 partial。

## 异常处理速查
| 情况 | 做法 |
|---|---|
| 模板是 .potx / 没有 notesMaster | 直接当 template 用；kit 自动改主部件类型、补最小 notesMaster，原母版不动 |
| 正文跑进小占位符 | 看 build 的 `placed` 行；用 `"ph": {"1": [...]}` 指定 idx |
| 模板缺图/表版式或缺占位符 | 最接近的版式 + `image_box`/`table_box`；记 compliance |
| 原 deck 有图表对象/SmartArt/EMF | 取其 PNG 预览或按论文数据建原生表格；写 exception |
| 原页内容装不下 | 删冗余 → 拆页 → 换版式；都不行写 exception，不压字号 |
| 字体缺失（如中文 ea 字体） | 不改模板字体；把 pdffonts 的替代名写进 substitutions |
| soffice 缺失/超时/崩溃 | render 已自动换 profile 重试；仍失败 → status=partial，render.json 的 errors 进 exceptions.run_failures，不声称有预览 |
| 论文是扫描件/加密 | pdftotext 近空 → 有 tesseract 就 OCR，否则只用 deck 内容并全部标 unverified，status=partial |
