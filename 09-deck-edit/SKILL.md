---
name: academic-pptx-generate-edit-lite
description: 学术 PPT 生成与编辑（轻量版）。当任务给出论文/研究材料、目标模板（target-template.pptx）、可能的初始稿（starting-deck.pptx）和工作单（artifacts/slide-workorder.json：模式 generate/edit/adapt、总页数、编辑指令、源内容保留、模板继承），要求交付原生可编辑的 /app/output/presentation.pptx、真实 PDF 导出、页级主张-来源映射、时长与修改记录时使用。核心：按工作单逐条执行编辑（压缩、扩写、换受众/语言、插图表、调序、删改页），未要求改动的页原样保留，母版版式不动；每轮存版本、出文字差异、写明改了什么为什么改如何回退；页面数字逐个回查原文。自带纯标准库 pptx_kit.py（无需 python-pptx）。不用于：论文精读、绘图算法、文字润色、PPT 软件开发。
---

# 学术 PPT 生成与编辑（轻量版）

## 路径（环境变量优先）
案例 `$CASE_JSON`（默认 `/input/case.json`）；同目录或 `/input` 下还有 `material.json`、`artifacts/slide-workorder.json`、`target-template.pptx`、
`starting-deck.pptx`、论文/数据。工作目录 `$WORK_DIR`（`/app/work`）；交付 `$OUT_DIR`（`/app/output`）；Skill 在 `$SKILL_DIR`（`/skills/weekly-skill`）。
`K=$SKILL_DIR/scripts/pptx_kit.py`。改文件用 python，不用 `sed -i`。最终文件名默认 `$OUT_DIR/presentation.pptx` + `presentation.pdf`（工作单另有规定从其规定）。

## 三个可核验的保证（交付时逐条给证据）
1. **只改被要求改的**：每处改动都对应一条指令 E?（change_log 一行一条）；指令没要求的改动一律不做，发现的问题写成"建议"。
2. **保留页原样**：保留页用 `{"keep": i}` 整页复制（文字、图片、备注都不动）；checker `--baseline v0.pptx --keep-map 新:旧` 逐页比对文字并写
   `version_diff.md`，保留页文字有变即 FAIL。
3. **每个版本可复跑、可回退**：`spec_vK.json` + `vK.pptx` + `diff_v(K-1)_vK.txt` 都留在 `versions/`；回退 = 用上一版 spec 重建。

## 步骤（目标 ≤ 30 次调用；先交骨架再完善）
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
   **只有**指令要求核对/更正事实（"check against the paper""fix numbers""与原文一致"之类），或某页按指令要从论文重新写，才在那一页用论文的值；
   其他不一致**不改**，在 corrections.md 和 change_log 里写成"建议更正（未执行：不在编辑指令内）"，并列入 exceptions.undecidable。保留页永远不改。
5. **页级计划**（写 `$WORK_DIR/plan.md`）：`页 | 动作(keep/edit/new/delete) | 对应指令 E? | 叙事角色 | 主张句 | 来源（文件+Fig/Table/Sec/页码）| 视觉 | 秒数`。
   - generate：封面→问题/缺口→方法（≤ 4 条）→结果（每个关键图/表一页，标题写结论句，配原图裁剪或原生表格）→局限→结论；一页一个主张，正文 ≤ 5 条。
   - edit：从 v0 出发，**只动指令点名的页**；其余 `{"keep": i}` 原样保留。
   - adapt：每一页都迁到目标模板版式，内容不改。
   页数必须等于工作单总页数；秒数合计 ≈ 时长。
   版式与字号：正文进版式里**面积最大**的 body/obj 占位符，出处用 `source_note`（进模板的来源/注释占位符，没有就页脚上方小字）；
   **字号阶梯**：标题 = 母版标题；正文 ≥ 工作单下限（没给就 18 pt）；表格 ≥ 14；图注 14；出处 11–12。
6. **执行编辑**（spec 写法，`template` 规则：edit → starting-deck；generate/adapt → target-template）：
   - 保留：`{"keep": 3}`；小改字：`{"keep": 3, "replace": {"原句": "新句"}, "notes": "..."}`（跨 run 也能替换；未命中会 WARN）。
   - 压缩/扩写/换受众/换语言：按版式新建该页（`layout` + `title` + `body`），**术语、符号、变量名、单位与论文一致**；换语言时专有名词首次出现保留原文括注。
     新建页、表格、图注可写下标/上标：`Al_{2}O_{3}`、`cm^{-1}`、`Ce^{3+}`（幻灯片上显示为真下标/上标，文字检查照常）；edit 模式跟随初始稿写法（初始稿写纯文本 "Al2O3" 就保持一致）。`replace` 只接受纯文本。
   - 插图表：有原始数值 → 原生 `table`（逐格照抄，表头带单位）；只有原图 → `python3 $K figcrop paper.pdf 页 "Fig. 3" $WORK_DIR/fig3.png` 后 `image`+`caption`。
     figcrop 只裁图本身（题注不进图片、白边已去，图在页上更大），并打印论文题注原文 → `caption` 写 `"Paper Fig. 3: <题注要点>"`；
     打印 `WARN no figure pixels` = PDF 里没有这张图 → 不放，记 material_gaps。没有数据也没有原图 → 不画。**不重画没有数据支撑的曲线，不放占位图。**
   - 调序/删页：spec 里的顺序就是新页序，没列的原页即删除（删前确认不是 source preservation 要求保留的页）。
7. **构建一轮 = 一个版本**（每轮 2–3 次）：`spec` 存为 `$WORK_DIR/spec_v1.json`，`"out": "$WORK_DIR/v1.pptx"`；`python3 $K build $WORK_DIR/spec_vK.json | tee $WORK_DIR/build.log`（spec 顶层加 `"min_pt": 18`；新建页每页打印 `placed slide N: body->ph ...`，核对正文进了大占位符），WARN 是提示：最多重建 2 轮
   （溢出→删字/拆页/换版式，不压字号），剩下的写进 uncertainty。保留页不传 `notes`（kit 原样带过原备注）。然后出差异：`python3 $K inspect $WORK_DIR/v1.pptx --full > $WORK_DIR/v1.txt; diff -u $WORK_DIR/v0.txt $WORK_DIR/v1.txt > $WORK_DIR/diff_v0_v1.txt`
   核对 diff：只出现指令要求的改动；出现计划外改动（保留页文字变了、页码以外的变化）就修 spec 重建。改坏了回退 = 用上一版 spec 重建。
8. **定稿与渲染**（1–2 次）：`cp $WORK_DIR/vN.pptx $OUT_DIR/presentation.pptx`；然后
   `python3 $K render $OUT_DIR/presentation.pptx` → `presentation.pdf`、`preview/slide-*.png`、pdffonts 实测、`render.json`（soffice 两次尝试各限 120 s、换 profile；pdftoppm/pdftocairo 限时；找不到 LibreOffice 也不报错，照实写进 render.json 的 errors）。
   render 的 status 不是 `rendered` → 不声称有预览，result 的 status 写 partial，原因进 exceptions.run_failures。能看图就打开 2–3 张**改过的页**的 PNG 目检（100 dpi）。
   有初始稿时同一次调用里再渲染改前版本供对照：`python3 $K render $WORK_DIR/v0.pptx && mkdir -p $OUT_DIR/versions && cp $WORK_DIR/v0.pdf $OUT_DIR/versions/v0_before.pdf`（失败不影响交付）。
9. **记录 + 组装 + 自检**（2–3 次）：`date -u +%FT%TZ > $WORK_DIR/t_end`；plan.md、各版 spec、diff、corrections.md 复制到 `$OUT_DIR/versions/`；写 `content_map.json`、`change_log.md`（`轮次 | 指令 E? | 页 | 改前 | 改后 | 理由 | 回退方式`，建议更正另列一节）、`time_record.json`。
   把已知事实写进 `$WORK_DIR/facts.json`（只写有的：`content_map`、`exceptions`{material_missing, undecidable, run_failures}、`uncertainty`、`change_log`、`status_reasons`，以及 `versions`、`time_record`、
   `instructions_done`：`{"E1": "slide 3: 8 条压成 4 条（diff_v0_v1.txt）", ...}` 每条指令一句：页号 + 做了什么 + 证据文件；没做的写 "not done: 原因"）。然后 `python3 $SKILL_DIR/scripts/check_result.py --assemble` → 按含义填满 contract 的**每一个**键（任何键名、中文名、嵌套子字段；facts 里同名键原样采用；缺的文件自动跳过，不留骨架字样），再跑
   `python3 $SKILL_DIR/scripts/check_result.py --template <模板文件> --slides N --paper $WORK_DIR/paper.txt --paper-advisory --min-pt <下限> --source $WORK_DIR/v0.txt --baseline $WORK_DIR/v0.pptx --keep-map <保留页 新:旧,…> --edit-map <改动页 新:旧,…>`
   checker 最后一步会把自己的判定写回 result.json：compliance 列表里追加 `by: check_result.py` 的行（页数、模板逐字节、保留页、数字回查、图表号、备注、导出、字号、每条指令 E?）和 `checker_record`（命令、FAIL/WARN 原文）；
   所以它必须**最后**跑（assemble 之后），重跑会替换旧行；不要手改这些行。`version_diff.md` 给出每个改动页的改前/改后行（- / +）和被删页。
   指令要求核对事实时去掉 --paper-advisory。`--keep-map` 写全部保留页（如 `1:1,2:2,9:8`），`--edit-map` 写改动页对应的原页（如 `3:3,10:8`，照 plan.md；新增页不写）：保留页文字变了 → FAIL，结果写进 `$OUT_DIR/version_diff.md`；论文不一致在 advisory 下只报 WARN（就是建议更正清单）。checker 还写 `$OUT_DIR/slide_audit.md`；两个文件都复制到 `versions/`。FAIL 修，最多两轮；修不了的（没有渲染器、材料缺失）就 status=partial 写明原因。build/checker 的 WARN 是提示，不要为清 WARN 反复重建。

## 编辑规则（每条针对一种已知失败）
1. **不整段塞**：论文段落改写成短语；单页 ≤ 5 条要点；build 溢出 WARN 清零。
2. **数字零改写**：数值、单位、n、条件照原文；不取整；自己算的数标"由 Table X 计算"。checker 数字回查小数缺失 = FAIL。
3. **图注与图上标注一致**：caption 写原文编号（含子图字母）；编号必须在题注列表里。
4. **不碰母版**：只用模板版式与占位符；不写字体颜色；checker `--template` 逐字节比对必须 PASS。
5. **改一页不坏别页**：保留页走 keep；`version_diff.md` 里保留页全部 identical；diff 里只能有计划内改动；页码字段会自动重算（diff 里页码数字变化属正常）。
6. **版本可回退**：每轮 spec_vK.json + vK.pptx + diff 都保留；change_log 每条：`轮次 | 指令 E? | 页 | 改前 | 改后 | 理由 | 回退方式`。
7. **备注**：每页 2–4 句（过渡、强调、追问时的证据位置、秒数），不复述页面；保留页的原备注原样带过（kit 默认）。
8. **缺口照实**：指令与材料冲突、证据不足、页数装不下——写 exceptions，按"材料缺失 / 无法判断 / 运行失败"分开。

## 交付物（`$OUT_DIR`）
`presentation.pptx`、`presentation.pdf`、`preview/*.png`、`slide_audit.md`、`corrections.md`、`content_map.json`（主张-来源）、`plan.md`（页级计划 + 秒数）、`change_log.md`、
`time_record.json`（开始/结束时间、各页秒数与合计）、`versions/`（spec_v*.json、diff_*.txt、v0_before.pdf；pptx 中间版可留在 work）、`version_diff.md`（逐页改前/改后）、`result.json`。

content_map 每行：`{"slide": 4, "action": "edit|keep|new", "instruction": "E2", "claim": "标题原文", "sources": [{"file": "paper.pdf",
"locator": "Table 2, p.5", "quote": "..."}], "numbers": [...], "visual": "原生表格 | 原图 Fig. 3 裁剪 | 保留原页图片", "seconds": 60}`。

## result.json 映射（保留 contract 全部根字段；任何键名风格按含义对应）
实际写入用 `check_result.py --assemble`（它按含义映射任意键名）；下面是各键应含的内容，写进 facts.json 的同名键会原样采用。
- `editable_source` → `{"pptx": "/app/output/presentation.pptx", "spec": 最终 spec, "rebuild": "python3 pptx_kit.py build spec_vN.json", "mode", "slides", "template", "versions": [...]}`
- `export_artifact` → `{"pdf": "/app/output/presentation.pdf", "png": [...], "pages", "renderer", "fonts": pdffonts 实测, "substitutions", "slide_audit": 路径}`
- `content_map` → 逐页主张-来源（内联）+ 文件路径；另附 `time_record`、`change_log` 路径
- `compliance_checks` → 列表：模式正确、页数 = N、每条指令 E? 已执行（逐条）、保留页未被改动（diff 依据）、模板继承（逐字节）、溢出、数字回查、
  备注、PDF 页数、字体实测；每项 `PASS/FAIL/WARN + 依据`。这些行由 checker 自动写入（见第 9 步），facts 里只需补 checker 测不到的（如"换受众措辞"）。
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
| soffice 缺失/超时/崩溃 | render 已自动换 profile 重试；仍失败 → status=partial，render.json 的 errors 进 exceptions.run_failures，不声称有预览 |
| 没有 python-pptx | 正常，pptx_kit.py 纯标准库 |
