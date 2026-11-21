---
name: academic-pptx-generate-edit-lite
description: 学术 PPT 生成与编辑（轻量版）。当任务给出论文/研究材料、目标模板（target-template.pptx）、可能的初始稿（starting-deck.pptx）和工作单（artifacts/slide-workorder.json：模式 generate/edit/adapt、总页数、编辑指令、源内容保留、模板继承），要求交付原生可编辑的 /app/output/presentation.pptx、真实 PDF 导出、页级主张-来源映射、时长与修改记录时使用。核心：按工作单逐条执行编辑（压缩、扩写、换受众/语言、插图表、调序、删改页），未要求改动的页原样保留，母版版式不动；每轮存版本、出文字差异、写明改了什么为什么改如何回退；页面数字逐个回查原文。自带纯标准库 pptx_kit.py（无需 python-pptx）。不用于：论文精读、绘图算法、文字润色、PPT 软件开发。
---

# 学术 PPT 生成与编辑（轻量版）

## 路径（环境变量优先）
案例 `$CASE_JSON`（默认 `/input/case.json`）；同目录或 `/input` 下还有 `material.json`、`artifacts/slide-workorder.json`、`target-template.pptx`、
`starting-deck.pptx`、论文/数据。工作目录 `$WORK_DIR`（`/app/work`）；交付 `$OUT_DIR`（`/app/output`）；Skill 在 `$SKILL_DIR`（`/skills/weekly-skill`）。
`K=$SKILL_DIR/scripts/pptx_kit.py`。改文件用 python，不用 `sed -i`。最终文件名默认 `$OUT_DIR/presentation.pptx` + `presentation.pdf`（工作单另有规定从其规定）。

## 步骤（目标 ≤ 32 次调用；先交骨架再完善）
1. **读输入**（2–3 次）：`date -u +%FT%TZ > $WORK_DIR/t_start`；`cat $CASE_JSON`；`find /input -maxdepth 3 -type f | head -60`；
   **全文**读 material.json 和 slide-workorder.json。逐字记下：case_id、`output_contract` 全部根字段、**mode**、**总页数**（exactly N）、
   每条编辑指令（编号 E1、E2…，原文照抄）、**source preservation**（哪些页/内容必须原样）、**template inheritance**（以哪个文件为模板）、听众、时长、语言。
2. **骨架**（第 3 次调用内）：`python3 $SKILL_DIR/scripts/check_result.py --init` → result.json 含 case_id、每个 contract 根字段、`status: partial`；之后每步更新。
3. **看文件**（2 次）：`python3 $K inspect target-template.pptx`（版式、占位符、主题、母版字号）；有初始稿就
   `python3 $K inspect starting-deck.pptx --full > $WORK_DIR/v0.txt`（每页按角色列文字、表格行、图片、备注）并 `cp starting-deck.pptx $WORK_DIR/v0.pptx`。
4. **读材料**（1–2 次）：`pdftotext -layout paper.pdf $WORK_DIR/paper.txt`（`\f` 分页）；列题注与页码：
   `python3 -c "import re,sys;[print(i,l.strip()[:90]) for i,p in enumerate(open(sys.argv[1]).read().split('\f'),1) for l in p.splitlines() if re.match(r'\s*(Fig(ure)?\.?|Table|图|表)\s*S?\d',l)]" $WORK_DIR/paper.txt`
   数据表（CSV/XLSX）也读进来；加密/扫描件按工具情况处理，否则列 exception。
   **初始稿对账**（有 v0 时，1 次）：v0 里每个数字、图/表号在 paper.txt 里核对（grep），写 `$WORK_DIR/corrections.md`（页 | v0 写法 | 论文写法+位置 | 处理）。
   要编辑/新建的页一律**以论文为准**；source preservation 要求原样保留的页**不改**，把不一致写进 exceptions.undecidable 和 change_log（"建议更正，未执行：保留要求"）。
5. **页级计划**（写 `$WORK_DIR/plan.md`）：`页 | 动作(keep/edit/new/delete) | 对应指令 E? | 叙事角色 | 主张句 | 来源（文件+Fig/Table/Sec/页码）| 视觉 | 秒数`。
   - generate：问题→方法→结果（每组关键证据一页）→结论/局限；一页一个主张，正文 ≤ 5 条。
   - edit：从 v0 出发，**只动指令点名的页**；其余 `{"keep": i}` 原样保留。
   - adapt：每一页都迁到目标模板版式，内容不改。
   页数必须等于工作单总页数；秒数合计 ≈ 时长。
   版式与字号：正文进版式里**面积最大**的 body/obj 占位符，出处用 `source_note`（进模板的来源/注释占位符，没有就页脚上方小字）；
   **字号阶梯**：标题 = 母版标题；正文 ≥ 工作单下限（没给就 18 pt）；表格 ≥ 14；图注 14；出处 11–12。
6. **执行编辑**（spec 写法，`template` 规则：edit → starting-deck；generate/adapt → target-template）：
   - 保留：`{"keep": 3}`；小改字：`{"keep": 3, "replace": {"原句": "新句"}, "notes": "..."}`（跨 run 也能替换；未命中会 WARN）。
   - 压缩/扩写/换受众/换语言：按版式新建该页（`layout` + `title` + `body`），**术语、符号、变量名、单位与论文一致**；换语言时专有名词首次出现保留原文括注。
   - 插图表：有原始数值 → 原生 `table`（逐格照抄，表头带单位）；只有原图 → `python3 $K figcrop paper.pdf 页 "Fig. 3" $WORK_DIR/fig3.png` 后 `image`+`caption`
     （写"原文 Fig. 3"）；没有数据也没有原图 → 不画，记 exception。**不重画没有数据支撑的曲线，不放占位图。**
   - 调序/删页：spec 里的顺序就是新页序，没列的原页即删除（删前确认不是 source preservation 要求保留的页）。
7. **构建一轮 = 一个版本**（每轮 2–3 次）：`spec` 存为 `$WORK_DIR/spec_v1.json`，`"out": "$WORK_DIR/v1.pptx"`；`python3 $K build $WORK_DIR/spec_vK.json | tee $WORK_DIR/build.log`（spec 顶层加 `"min_pt": 18`；新建页每页打印 `placed slide N: body->ph ...`，核对正文进了大占位符），**每条 WARN 都处理**
   （溢出→删字/拆页/换版式，不压字号）。然后出差异：`python3 $K inspect $WORK_DIR/v1.pptx --full > $WORK_DIR/v1.txt; diff -u $WORK_DIR/v0.txt $WORK_DIR/v1.txt > $WORK_DIR/diff_v0_v1.txt`
   核对 diff：只出现指令要求的改动；出现计划外改动（保留页文字变了、页码以外的变化）就修 spec 重建。改坏了回退 = 用上一版 spec 重建。
8. **定稿与导出**（2 次）：`cp $WORK_DIR/vN.pptx $OUT_DIR/presentation.pptx`；`cd $OUT_DIR && timeout 120 soffice --headless -env:UserInstallation=file:///tmp/lo_profile --convert-to pdf presentation.pptx`；
   `mkdir -p preview && timeout 60 pdftoppm -png -r 50 presentation.pdf preview/slide`；`pdffonts presentation.pdf`。失败照实记录。
9. **记录与自检**（3 次）：`date -u +%FT%TZ > $WORK_DIR/t_end`；把 plan.md、各版 spec、diff 文件复制到 `$OUT_DIR/versions/`；写 `content_map.json`、`change_log.md`；填 result.json；
   `python3 $SKILL_DIR/scripts/check_result.py --template <模板文件> --slides N --paper $WORK_DIR/paper.txt --min-pt <下限> [--source $WORK_DIR/v0.txt --preserved <保留页的新页号,逗号分隔>]`。
   --paper 抓"只在 v0 里出现的数字"和"图号与论文题注内容不符"（保留页上只报 WARN，照实写进 exceptions）；checker 同时写 `$OUT_DIR/slide_audit.md`
   （逐页版式、占位符、散装框、图片比例误差、最小字号、备注、PDF 丢字），复制一份到 `versions/`。FAIL 必须修，最多两轮。

## 编辑规则（每条针对一种已知失败）
1. **不整段塞**：论文段落改写成短语；单页 ≤ 5 条要点；build 溢出 WARN 清零。
2. **数字零改写**：数值、单位、n、条件照原文；不取整；自己算的数标"由 Table X 计算"。checker 数字回查小数缺失 = FAIL。
3. **图注与图上标注一致**：caption 写原文编号（含子图字母）；编号必须在题注列表里。
4. **不碰母版**：只用模板版式与占位符；不写字体颜色；checker `--template` 逐字节比对必须 PASS。
5. **改一页不坏别页**：保留页走 keep；diff 里只能有计划内改动；页码字段会自动重算（diff 里页码数字变化属正常）。
6. **版本可回退**：每轮 spec_vK.json + vK.pptx + diff 都保留；change_log 每条：`轮次 | 指令 E? | 页 | 改前 | 改后 | 理由 | 回退方式`。
7. **备注**：每页 2–4 句（过渡、强调、追问时的证据位置、秒数），不复述页面；保留页的原备注原样带过（kit 默认）。
8. **缺口照实**：指令与材料冲突、证据不足、页数装不下——写 exceptions，按"材料缺失 / 无法判断 / 运行失败"分开。

## 交付物（`$OUT_DIR`）
`presentation.pptx`、`presentation.pdf`、`preview/*.png`、`slide_audit.md`、`corrections.md`、`content_map.json`（主张-来源）、`plan.md`（页级计划 + 秒数）、`change_log.md`、
`time_record.json`（开始/结束时间、各页秒数与合计）、`versions/`（spec_v*.json、diff_*.txt；pptx 中间版可留在 work）、`result.json`。

content_map 每行：`{"slide": 4, "action": "edit|keep|new", "instruction": "E2", "claim": "标题原文", "sources": [{"file": "paper.pdf",
"locator": "Table 2, p.5", "quote": "..."}], "numbers": [...], "visual": "原生表格 | 原图 Fig. 3 裁剪 | 保留原页图片", "seconds": 60}`。

## result.json 映射（保留 contract 全部根字段；任何键名风格按含义对应）
- `editable_source` → `{"pptx": "/app/output/presentation.pptx", "spec": 最终 spec, "rebuild": "python3 pptx_kit.py build spec_vN.json", "mode", "slides", "template", "versions": [...]}`
- `export_artifact` → `{"pdf": "/app/output/presentation.pdf", "png": [...], "pages", "renderer", "fonts": pdffonts 实测, "substitutions", "slide_audit": 路径}`
- `content_map` → 逐页主张-来源（内联）+ 文件路径；另附 `time_record`、`change_log` 路径
- `compliance_checks` → 列表：模式正确、页数 = N、每条指令 E? 已执行（逐条）、保留页未被改动（diff 依据）、模板继承（逐字节）、溢出、数字回查、
  备注、PDF 页数、字体实测；每项 `PASS/FAIL/WARN + 依据`
- `exceptions` → `{"material_gaps": [...], "undecidable": [...], "run_failures": [...]}`；另写 `uncertainty`、`status_reasons`。
- **status 只写一个词**：contract 有取值就用它的；否则 complete / partial / failed。complete = 全部指令执行、页数正确、checker PASS、PDF 存在；
  否则 partial（原因写 status_reasons）；没有 pptx 才是 failed。

## 异常处理速查
| 情况 | 做法 |
|---|---|
| 工作单与 task.md 冲突 | 以工作单为准，冲突写 exceptions.undecidable |
| 指令要的数据材料里没有 | 不编造，该页写"材料未提供"或不做，记 material_gaps |
| starting-deck 里有图表对象/SmartArt | 保留页 keep 原样；需要编辑时改为原生表格或图片并记录 |
| 模板缺版式/占位符 | 换最接近版式，`image_box/table_box` 显式定位并记录 |
| soffice 失败 | 换 profile 目录重试一次；仍失败记录原因，status=partial |
| 没有 python-pptx | 正常，pptx_kit.py 纯标准库 |
