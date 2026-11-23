---
name: academic-talk-content-organizer-lite
description: 学术汇报内容组织（轻量版）。当任务给出论文/研究材料、听众（组会/答辩/评审/会议）、时长、页数和模板，要求把内容组织成可讲的学术 PPT（可编辑 PPTX + PDF 导出 + 页级证据映射 + 讲稿 + 问答准备 + 取舍记录）时使用。核心：先把"汇报目标"和"听众"写成可检查的约束，再据此定页数、叙事顺序、每页唯一主张及其证据强度，并准备追问与备用页；每个论断都能回到原文位置，取舍过程可复核。自带纯标准库 pptx_kit.py（无需 python-pptx）。不用于：论文精读、写作润色、科研绘图。
---

# 学术汇报内容组织（轻量版）

## 路径（环境变量优先）
案例 `$CASE_JSON`（默认 `/input/case.json`），材料在 `/input`（可能有 `material.json`、`artifacts/slide-workorder.json`、`target-template.pptx`、
`starting-deck.pptx`、论文 PDF/文本）；工作目录 `$WORK_DIR`（`/app/work`）；交付 `$OUT_DIR`（`/app/output`）；Skill 在 `$SKILL_DIR`
（`/skills/weekly-skill`）。`K=$SKILL_DIR/scripts/pptx_kit.py`。改文件用 python，不用 `sed -i`。

## 模式
generate = 材料+模板新建；edit = `template` 填 starting-deck，未改页 `{"keep": i}` 原样保留；adapt = `template` 填 target-template，
starting-deck 每页都迁过去（`python3 $K inspect starting-deck.pptx --full > $WORK_DIR/start_text.txt` 抽文字，`unzip -o starting-deck.pptx 'ppt/media/*' -d $WORK_DIR/start` 取图）。
有 starting-deck 时它只是素材，不是事实来源：其中每个数字、图/表号先在论文里核对，不一致**以论文为准**，写 `$WORK_DIR/corrections.md`（旧页 | deck 写法 | 论文写法+位置 | 处理）。

## 步骤（目标 ≤ 30 次调用；先交骨架再完善）
1. **读输入**（2 次）：`cat $CASE_JSON`；`find /input -maxdepth 3 -type f | head -60`；读完 material.json、slide-workorder.json、task.md。
   记下 case_id、`output_contract` 全部字段、模式、**总页数**（exactly N 就正好 N）、**听众**、**时长**、**场合**、语言、模板、问答要求。
2. **骨架**（第 3 次调用内）：`python3 $SKILL_DIR/scripts/check_result.py --init` → result.json 含 case_id、每个 contract 字段、`status: partial`；之后每步更新。
3. **读材料**（2 次）：`pdftotext -layout paper.pdf $WORK_DIR/paper.txt`（`\f` 分页）；列题注与页码：
   `python3 -c "import re,sys;[print(i,l.strip()[:90]) for i,p in enumerate(open(sys.argv[1]).read().split('\f'),1) for l in p.splitlines() if re.match(r'\s*(Fig(ure)?\.?|Table|图|表)\s*S?\d',l)]" $WORK_DIR/paper.txt`
   加密/扫描件：qpdf / tesseract 可用就处理，否则列 exception。
4. **汇报目标卡**（写 `$WORK_DIR/talk_plan.md`，这是本题的核心，不要跳过）：
   - **目标**写成可检查的一句话："让<听众>在<N>分钟后认可/理解<X>，依据是<哪几组证据>"。按场合定侧重点：
     组会→方法细节与进度、下一步；开题/中期→问题意义、可行性、风险；答辩→创新点与边界；评审/基金→结论强度、证据、影响；会议 talk→一个核心发现。
   - **听众画像**：先验知识（同行/跨领域/评委）、最关心什么、最可能质疑什么 → 决定背景页比例（同行 ≤ 1 页，跨领域 1–2 页）与术语解释范围。
   - **页数与时长**：工作单页数为准；否则 ≈ 1 页/分钟（封面、致谢不计时）。每页分配秒数，合计 = 时长 ±10%。
   - **结论强度**：每条要上页的结论标 证据强度 **强**（本文直接测得、有重复/统计）/ **中**（单一表征、作者推断）/ **弱**（推测、展望、他人工作）。
     弱证据不能做结果页标题；页面措辞强度与证据强度一致（"表明/提示/可能"）。
5. **取舍表**（写进 talk_plan.md）：列出论文的全部候选内容（每个图表、每个结论、方法细节），逐条标 上页 / 进备注 / 进备用页 / 不讲，
   并写理由（服务目标？听众需要？时长允许？）。这张表就是"取舍过程可复核"的证据。
6. **叙事与页级大纲**（写 `$WORK_DIR/plan.md`）：`页 | 角色 | 主张句（标题）| 证据（Fig/Table/Sec/页码）| 证据强度 | 视觉 | 过渡句 | 秒数`。
   主骨架 问题→方法→结果→结论，但按目标调整铺垫（例：评审先给结论再给证据；组会在结果后加"下一步/风险"）。
   每页**唯一主张**；相邻两页之间要有过渡句（写进备注）。
7. **问答准备**（写 `$OUT_DIR/qa_prep.md`）：5–8 个最可能的追问，覆盖 机制、数据（样本量/误差/统计）、对照、局限、可推广性；
   每题给：回答要点（只用材料里的事实）、引用的原文位置、可翻到的页/备用页编号。材料答不了的写"材料未提供，如实说明"。
   备用页（backup）放在正文页之后，计入总页数前先看工作单是否允许；不允许就只写进 qa_prep.md。
8. **看模板并构建**（3–5 次）：`python3 $K inspect <模板>` 选版式；需要的原图 `python3 $K figcrop paper.pdf 页 "Fig. 2" $WORK_DIR/fig2.png`
   （打印裁剪区内文字核对）；表格做成原生 `table`，数值逐格照抄。写 `$WORK_DIR/spec.json`（`"out": "$OUT_DIR/presentation.pptx"`），
   `python3 $K build $WORK_DIR/spec.json | tee $WORK_DIR/build.log`。内容/图/表页加 `"source_note": "Paper Table 1, p.3"`（页上可见出处，进模板的来源占位符或页脚上方小字），
   spec 顶层加 `"min_pt": 18`。build 每页打印 `placed slide N: body->ph obj idx1 ...`：核对正文进了版式里**面积最大**的占位符。
   **字号阶梯**：标题 = 母版标题；正文 ≥ 工作单下限（没给就 18 pt）；表格 ≥ 14；图注 14；出处 11–12。**WARN 是提示：最多重建 2 轮**（删字/拆页/换版式），剩下的写进 uncertainty（溢出→删字/拆页/换版式，
   `font_size` 不低于阶梯）。备注 = 过渡句 + 强调点 + 追问时指向的证据 + 秒数。
9. **渲染**（1 次）：`python3 $K render $OUT_DIR/presentation.pptx` → `presentation.pdf`、`preview/slide-*.png`、pdffonts 实测、`render.json`（soffice 两次尝试各限 120 s、换 profile；pdftoppm/pdftocairo 限时；找不到 LibreOffice 也不报错，照实写进 render.json 的 errors）。
   render 的 status 不是 `rendered` → 不声称有预览，result 的 status 写 partial，原因进 exceptions.run_failures。能看图就打开 2–3 张 PNG 目检。
10. **记录 + 组装 + 自检**（2–3 次）：写 `content_map.json`、`change_log.md`，`talk_plan.md`/`plan.md` 复制到 `$OUT_DIR`。
   把已知事实写进 `$WORK_DIR/facts.json`（只写有的：`content_map`、`compliance_checks`、`exceptions`{material_missing, undecidable, run_failures}、`uncertainty`、`change_log`、`status_reasons`，以及本题专有的 `audience_goal`、`selection_log`、`qa_prep`（按 contract 的实际键名写））。然后 `python3 $SKILL_DIR/scripts/check_result.py --assemble` → 按含义填满 contract 的**每一个**键（任何键名、中文名、嵌套子字段；facts 里同名键原样采用；缺的文件自动跳过，不留骨架字样），再跑
   `python3 $SKILL_DIR/scripts/check_result.py --paper $WORK_DIR/paper.txt --template <模板> --min-pt <下限> [--slides N] [--source $WORK_DIR/start_text.txt]`
   有 starting-deck 才加 --source。checker 还查主张标题和页型覆盖，并写 `$OUT_DIR/slide_audit.md`。FAIL 修，最多两轮；修不了的（没有渲染器、材料缺失）就 status=partial 写明原因。build/checker 的 WARN 是提示，不要为清 WARN 反复重建。

## 内容规则
1. 不是压缩论文：页面只放服务目标的内容；被砍掉的内容在取舍表里有去向和理由。
2. 每个论断能回到材料：content_map 每页写 locator（Fig/Table/Sec/页码）和原句短引；不能回溯的句子删掉。
3. 数字零改写：数值、单位、n、条件照抄；自己算的数标"由 Table X 计算"并写算式；他人结果写"[n] 报道"。
4. 标题是主张句，强度匹配证据（强→"使/提高"；中→"表明"；弱→"可能/提示"）；"首次""显著"只有原文这么说且有依据才用。
5. 备注不复述页面；问答要点与页面口径一致（同一个数、同一个结论措辞）。
6. 模板约束：只用模板版式和占位符，不改母版/主题/配色，页脚页码沿用模板；不放占位图、不编造曲线。
7. 缺口照实：时长装不下、证据不足以支撑目标、材料缺图——写进 exceptions，并在 talk_plan 说明对目标的影响。

## 交付物（`$OUT_DIR`）
`presentation.pptx`、`presentation.pdf`、`preview/*.png`、`slide_audit.md`、`talk_plan.md`（目标、听众画像、页数时长分配、证据强度、取舍表）、`plan.md`、
`qa_prep.md`、`content_map.json`、`change_log.md`、`spec.json`、`result.json`。

content_map 每行：`{"slide": 4, "role": "结果", "claim": "...", "evidence_strength": "强|中|弱", "evidence": [{"source": "paper.pdf",
"locator": "Table 1, p.3", "quote": "..."}], "numbers": [...], "seconds": 60, "transition": "...", "qa_refs": ["Q2"]}`。

## result.json 映射（任何键名风格按含义对应；嵌套按子字段填）
实际写入用 `check_result.py --assemble`（它按含义映射任意键名）；下面是各键应含的内容，写进 facts.json 的同名键会原样采用。
- 演示文件 / editable_source → `{"pptx", "spec", "rebuild", "slides", "layouts_used"}`；导出 / export_artifact → `{"pdf", "png", "pages", "renderer", "fonts", "substitutions", "slide_audit"}`
- 页级证据映射 / content_map → content_map 内联列表 + 文件路径；合规检查 / compliance_checks → 页数、时长合计、模板继承、备注、溢出、数字回查、
  预览页数、字体，每项 `PASS/FAIL/WARN + 依据`；另加 `audience_goal`（目标句+听众画像）、`selection_log`（取舍表）、`qa_prep`（问题列表+文件路径）。
- exceptions / 不确定性 → 材料缺失、无法判断、运行失败**分开列**；另写 `source_map`、`change_log`、`uncertainty`、`material_gaps`、`status_reasons`。
- **status 只写一个词**：contract 有取值就用它的，否则 complete / partial / failed。complete = pptx+pdf、页数合规、checker PASS、每页有证据、
  问答准备齐；否则 partial；没有 pptx 才是 failed。

## 异常处理速查
| 情况 | 做法 |
|---|---|
| 没给听众/时长 | 从场合推断并写进 talk_plan 的"假设"，列入 uncertainty |
| 页数上限装不下全部证据 | 按目标保留主线证据，其余进备注/备用页/qa_prep，取舍表写理由 |
| 证据撑不起要求的结论强度 | 降低措辞强度，在 exceptions 写明"材料仅支持到 X" |
| 模板缺版式 | 换最接近版式；`image_box`/`table_box` 显式定位并记录 |
| soffice 缺失/超时/崩溃 | render 已自动换 profile 重试；仍失败 → status=partial，render.json 的 errors 进 exceptions.run_failures，不声称有预览 |
| 没有 python-pptx | 正常，pptx_kit.py 纯标准库 |
