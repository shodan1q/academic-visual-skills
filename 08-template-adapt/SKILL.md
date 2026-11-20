---
name: academic-pptx-template-adapter-lite
description: 学术 PPT 模板与格式适配（轻量版）。当任务给出目标模板（target-template.pptx/.potx）以及要套用的内容（旧模板的 starting-deck.pptx、论文或提纲，可能有 slide-workorder.json 规定页数/版式/字号/页脚），要求交付真正继承目标母版与版式的可编辑 PPTX、PDF/PNG 导出、逐页版式映射、合规检查与修改记录时使用。核心：先读模板结构（母版、版式、占位符、主题字体颜色、字号阶梯），每页内容写进正确版式的占位符而不是浮动文本框；溢出靠删字/拆页/换版式解决而不是压字号；图片等比放入容器；整册页脚页码编号一致；导出后用实测核对字体与页数。自带纯标准库 pptx_kit.py（无需 python-pptx）。不用于：改写论文内容、科研绘图、语言润色。
---

# 学术 PPT 模板与格式适配（轻量版）

## 路径（环境变量优先）
案例 `$CASE_JSON`（默认 `/input/case.json`），材料在 `/input`（`material.json`、`artifacts/slide-workorder.json`、`target-template.pptx`、
`starting-deck.pptx`、论文等）；工作目录 `$WORK_DIR`（`/app/work`）；交付 `$OUT_DIR`（`/app/output`）；Skill 在 `$SKILL_DIR`
（`/skills/weekly-skill`）。`K=$SKILL_DIR/scripts/pptx_kit.py`。改文件用 python，不用 `sed -i`。

## 关键原理（判断"真的套用了模板"的标准）
- 母版、版式、主题（`ppt/slideMasters`、`ppt/slideLayouts`、`ppt/theme`）原样来自目标模板，**一个字节都不改**；新页面的 rels 指向这些版式。
- 标题/正文写进版式的**占位符**（`<p:ph type/idx>` 与版式一致），位置、字号、字体、颜色从版式和主题继承；文字 run 里**不写**字体名、颜色、字号
  （除非工作单规定）。`pptx_kit.py build` 默认就这样做；旧 deck 里的手工格式（字体、颜色、位置）不要带过来。
- 页脚、页码、日期用版式里的 ftr/sldNum/dt 占位符（spec 的 `footer`、`slide_numbers`、`date`），不是自己画文本框。

## 步骤（目标 ≤ 30 次调用；先交骨架再完善）
1. **读输入**（2 次）：`cat $CASE_JSON`；`find /input -maxdepth 3 -type f | head -60`；读完 material.json、slide-workorder.json、task.md。
   记下 case_id、`output_contract` 全部字段、模式（adapt/generate/edit）、总页数、指定版式/字号/字体/页脚规则、导出要求。
2. **骨架**（第 5 次调用内）：`$OUT_DIR/result.json` = case_id + 每个 contract 字段占位 + `"status": "partial"`。
3. **读模板**（1 次）：`python3 $K inspect target-template.pptx`。写 `$WORK_DIR/template_spec.md`：幻灯片尺寸；每个版式的名字和占位符
   （type、idx、位置英寸、字号）；主题字体（major/minor，latin/ea）与主题色；母版标题/正文字号；是否有页脚、页码、日期占位符；样例页内容。
   这就是"字号与间距阶梯"的来源：标题、正文一级、二级、图注字号都以母版/版式为准，**不得低于母版正文字号的 80%**（工作单另有规定从其规定）。
4. **读内容来源**（1–2 次）：adapt 模式 `python3 $K inspect starting-deck.pptx --full`（每页按角色列出 ph:title/ph:obj/text、表格行、图片、备注），
   `unzip -o starting-deck.pptx 'ppt/media/*' -d $WORK_DIR/start` 取图；论文来源 `pdftotext -layout paper.pdf $WORK_DIR/paper.txt`。
5. **逐页版式映射表**（写 `$WORK_DIR/layout_map.md`，覆盖**每一页**，不能只做封面和前几页）：
   `原页 | 原角色/内容摘要 | 目标版式 | 标题→ph | 正文→ph(idx) | 图/表→容器(占位符或 box) | 备注 | 处理说明`。
   映射规则：封面→Title Slide/标题幻灯片；节标题→Section Header；要点→Title and Content；左右对比/图文并列→Two Content 或 Comparison；
   整页大图→Picture with Caption/图片与标题 或 Title Only + `image_box`。模板缺对应版式：用最接近的版式，`image_box/table_box` 显式定位，在说明里写清。
   原页内容一字不改地带过来（数字、单位、图号、引用编号、备注），除非工作单要求改。
6. **写 spec 并构建**（2–4 次）：`$WORK_DIR/spec.json`，`"template": 目标模板`，`"out": "$OUT_DIR/presentation.pptx"`（以工作单为准），
   每页 `layout` 用 layout_map 的版式名；原图用 `image`（kit 会按容器等比缩放、不拉伸），原表格优先原生 `table`（逐格照抄），表/图题用 `caption`。
   `python3 $K build $WORK_DIR/spec.json`。**每条 WARN 都处理**：
   - 溢出：先删冗余字（不删数字和结论）→ 拆成两页（页数允许时）→ 换容量更大的版式；最后才用 `font_size`，且不低于第 3 步的下限。
   - 版式没有该占位符：换版式；replace 未命中：查原文。处理过程逐条写 change_log。
7. **导出**（2 次）：`cd $OUT_DIR && timeout 120 soffice --headless -env:UserInstallation=file:///tmp/lo_profile --convert-to pdf presentation.pptx`；
   `mkdir -p preview && timeout 60 pdftoppm -png -r 50 presentation.pdf preview/slide`；`pdffonts presentation.pdf`（主题字体是否嵌入、被什么替代）。
8. **批量一致性核对**（1–2 次）：`python3 $K inspect $OUT_DIR/presentation.pptx` 逐页确认：标题都在 `ph:title`、页脚/页码每页都有且页码连续、
   没有 `text` 类型的散装正文框（图注除外）、图片数与原 deck 一致、备注都迁移了。
9. **记录与自检**（2–3 次）：写 `content_map.json`（逐页：原页 → 新页、版式、迁移的内容与来源）、`compliance_checks`、`change_log.md`，填 result.json；
   `python3 $SKILL_DIR/scripts/check_result.py --template <目标模板> [--slides N] [--source $WORK_DIR/paper.txt 或 $WORK_DIR/start_text.txt]`。
   adapt 模式把 `inspect starting-deck.pptx --full` 的输出存成 `$WORK_DIR/start_text.txt` 当数字回查来源。FAIL 必须修。

## 格式规则（每条针对一种已知失败）
1. **不覆盖模板**：不改母版/版式/主题；不在 run 上写字体、颜色；不加装饰形状；checker `--template` 必须 PASS（逐字节比对）。
2. **不靠缩字硬塞**：字号下限见第 3 步；页面放不下就删字、拆页或换版式，处理结果写 change_log。
3. **图片不变形**：只用等比缩放（kit 默认）；原图分辨率太低（宽 < 600 px 放整页）写 exception；矢量图（EMF/SVG）先转 PNG 并记录。
4. **编号一致**：图表编号、引用编号与原 deck/论文一致，整册统一写法（"Fig. 3"/"图 3" 只用一种，跟工作单或模板语言）。
5. **整册一致**：每页标题位置来自同一组版式；页脚文字统一；页码连续；中英文混排时中文用主题 ea 字体、英文用 latin 字体（都靠继承）。
6. **全部页都迁移**：页数 = 原 deck 页数（或工作单页数）；不能只改封面和前几页；样例页删除。
7. **导出可核对**：PDF 页数 = 幻灯片数；pdffonts 实测写进记录；字体被替代就照实写替代名，不说"已嵌入原字体"。

## 交付物（`$OUT_DIR`）
`presentation.pptx`、`presentation.pdf`、`preview/*.png`、`layout_map.md`、`template_spec.md`、`content_map.json`、`change_log.md`、`spec.json`、`result.json`。

content_map 每行：`{"slide": 5, "from": "starting-deck slide 5", "layout": "Two Content", "placeholders": {"title": "ph title", "body": "idx 1", "image": "idx 2 box"},
"content": ["标题原文", "图 image3.png（等比缩放 0.62）"], "source": "starting-deck.pptx slide 5 / paper.pdf Fig. 3 p.6", "notes_migrated": true, "issues": []}`。

## result.json 映射（任何键名风格按含义对应；嵌套按子字段填）
- 演示文件 / editable_source → `{"pptx", "spec", "rebuild", "slides", "layouts_used", "template": 目标模板路径}`
- 导出 / export_artifact → `{"pdf", "png", "pages", "renderer", "fonts": pdffonts 实测, "substitutions"}`
- 映射 / content_map → 逐页映射内联 + 文件路径
- 合规 / compliance_checks → 列表：模板继承（逐字节）、版式覆盖全部页、无散装正文框、字号下限、溢出 WARN 清零、图片等比、编号一致、页脚页码连续、
  备注迁移、PDF 页数、字体实测；每项 `PASS/FAIL/WARN + 依据`
- exceptions → 材料缺失、无法判断、运行失败**分开列**；另写 `source_map`、`change_log`、`uncertainty`、`material_gaps`、`status_reasons`。
- **status 只写一个词**：contract 有取值就用它的；否则 complete / partial / failed。complete = 全部页迁移、checker PASS、PDF 页数正确；否则 partial。

## 异常处理速查
| 情况 | 做法 |
|---|---|
| 模板是 .potx | 直接当 template 用，kit 会把主部件类型改成 .pptx |
| 模板没有 notesMaster | kit 自动补最小 notesMaster（新 theme 副本），原母版不动 |
| 原 deck 有图表对象/SmartArt | 不能可靠迁移：取其 PNG 预览或数据表重建为原生表格，写 exception |
| 原页内容装不下目标版式 | 先删冗余、再拆页、再换版式；都不行写 exception，不压字号 |
| 中文字体缺失 | 不改模板字体；记录 pdffonts 的替代字体 |
| soffice 失败 | 换 profile 目录重试一次；仍失败记录原因，status=partial |
