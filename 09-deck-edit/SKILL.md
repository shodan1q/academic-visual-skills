---
name: academic-pptx-generate-edit-lite
description: 学术 PPT 生成与编辑（轻量版）。当任务给出论文/研究材料、目标模板（target-template.pptx）、可能的初始稿（starting-deck.pptx）和工作单（artifacts/slide-workorder.json：模式 generate/edit/adapt、总页数、编辑指令、源内容保留、模板继承），要求交付原生可编辑的 /app/output/presentation.pptx、真实 PDF 导出、页级主张-来源映射、时长与修改记录时使用。核心：按工作单逐条执行编辑（压缩、扩写、换受众/语言、插图表、调序、删改页），只改文字的指令在原页原位改（该页的图片、表格、手工文本框和位置一律不动），未要求改动的页原样保留，母版版式不动；每轮存版本，修改记录由脚本对比两个文件逐页逐形状生成（改前/改后、指令原文、理由、回退方式）；页面数字逐个回查原文。自带纯标准库脚本（无需 python-pptx）：deck_flow.py 三条命令 start / build / finish 走完全流程。不用于：论文精读、绘图算法、文字润色、PPT 软件开发。
---

# 学术 PPT 生成与编辑（轻量版，v1.5）

## 路径（环境变量优先）
案例 `$CASE_JSON`（默认 `/input/case.json`）；同目录或 `/input` 下还有 `material.json`、`artifacts/slide-workorder.json`、`target-template.pptx`、
`starting-deck.pptx`、论文/数据。工作目录 `$WORK_DIR`（`/app/work`）；交付 `$OUT_DIR`（`/app/output`）；Skill 在 `$SKILL_DIR`（`/skills/weekly-skill`）。
改文件用 python 或 heredoc 整体重写，不做就地流编辑。交付文件名默认 `presentation.pptx` / `presentation.pdf`（工作单另有规定：`export DELIVER_NAME=xxx.pptx`）。

## 快速路径：6 步，约 8–12 次调用（时间只有 900 s，先交付再完善）
```bash
F=$SKILL_DIR/scripts/deck_flow.py; K=$SKILL_DIR/scripts/pptx_kit.py
python3 $F start                       # ① 一次读完全部输入（见下）
python3 $K figcrop /input/paper.pdf 4 "Fig. 3" $WORK_DIR/fig3.png      # ② 只在要插论文原图时
# ③ 写 $WORK_DIR/plan.md 和 $WORK_DIR/spec_v1.json（一次调用写完）
python3 $F build $WORK_DIR/spec_v1.json      # ④ 构建 + 与 v0 的文字 diff + 立即复制到 $OUT_DIR/presentation.pptx
# ⑤ 写 $WORK_DIR/facts.json、corrections.md（一次调用写完）
python3 $F finish --slides N --min-pt 18 [--fact-check]   # ⑥ 渲染 + 修改记录 + result.json + 自检（保留页/改动页对应关系自动从 spec 推出）
```
三个可核验的保证（build / finish 自动给出证据）：**只改被要求改的**（改文字走原位编辑 `keep` + `set`，该页其余形状逐字节不变；
change_log.md 每个改动页写明"N 个形状里几个没动、动了哪个"）；**保留页原样**（`{"keep": i}` 整页复制，逐页比对）；
**每个版本可复跑可回退**（`versions/spec_vK.json` + `v0.pptx`，每条改动给出具体回退写法）。

### ① start（1 次调用，输出要全文读完）
打印：输入文件清单；工作单与 material 全文；**编号好的编辑指令 E1、E2…**（原文，存 `instructions.json`；plan / facts 里就用这些编号）；模板的版式/占位符/主题/母版字号；初始稿每页文字、表格、图片、备注（存 `v0.txt`，原件存 `v0.pptx`）；
论文文字（`paper.txt`，`[p.N]` = PDF 页；长论文只列题注，正文用 `sed -n`/`grep -n` 分段读）；**初始稿对论文的预检**（`precheck.md`：论文里找不到的数字、
图表号与题注内容不符——只是候选，逐条在 paper.txt 里核实）。同时写好 result.json 骨架（status partial）。
从工作单逐字记下：case_id、**mode**（generate / edit / adapt）、**总页数**、每条编辑指令、**source preservation**（哪些页、哪些图/文本框必须原样）、
**template inheritance**（以哪个文件为模板）、听众、时长、语言、字号下限。数据表（CSV/XLSX）另行读入；PDF 无文字层 → 记 material_gaps。

### ③ plan.md + spec_v1.json
`plan.md` 一页一行：`页 | 动作(keep/edit/new/delete) | 指令 E? | 叙事角色 | 主张句 | 来源（文件 + Fig/Table/Sec + 页码）| 视觉 | 秒数`；页数 = 工作单总页数，秒数合计 ≈ 时长。
- **edit**：模板 = 初始稿（`"template": "$WORK_DIR/v0.pptx"`）；**只动指令点名的页**，其余 `{"keep": i}`；点名的页按下表选**动得最少**的写法。
- **generate**：模板 = target-template；封面→问题/缺口→方法（≤ 4 条）→结果（每个关键图/表一页，标题写结论句）→局限→结论。
- **adapt**：模板 = target-template；每页迁到对应版式，内容不改。

**edit 模式：按指令类型选写法（从上往下，能用上面的就不用下面的）**
| 指令 | spec 写法 | 该页其余内容 |
|---|---|---|
| 没点名的页 | `{"keep": i}` | 整页原样 |
| 只改备注 | `{"keep": i, "notes": "新备注"}` | 页面逐字节不变 |
| 改个别词、数字、图表号 | `{"keep": i, "replace": {"旧文字": "新文字"}}` | 不变 |
| 压缩 / 扩写 / 改写 / 换受众 / 换语言 / 改标题（只动文字） | `{"keep": i, "set": {"title": "结论句", "body": ["要点 1", "  二级", "要点 3"]}, "notes": "…"}` | 图片、表格、手工文本框、位置、字体格式都不变 |
| 在原页加一张图 / 删掉某个形状 / 补出处行 | `{"keep": i, "image": "/app/work/fig3.png", "image_box": [x, y, w, h], "caption": "…"}` / `"remove": ["形状名或其中的文字"]` / `"source_note": "Paper Sec. 2, p.2"` | 不变 |
| 整页换成图或表、原页内容基本不要了 | 按版式新建：`{"layout": "…", "from": i, "title": …, "table"/"image": …}`（`from` = 它替换的原页号） | 重建 |
| 新增页 | 按版式新建（不写 `from`） | - |
| 调序 / 删页 | spec 里的顺序就是新页序；没列的原页即删除 | - |

`set` 的键：`title`、`subtitle`、`body`（该页文字最多的那个文本形状）、`source_note`、占位符 idx（如 `"13"`）、形状名、或形状里的一段文字。
build 会打印 `set slide N: … -> shape '…': 6 paragraph(s) -> 3`，对不上会 WARN 并列出该页形状名。

spec 写法（路径写绝对路径；完整字段见 `pptx_kit.py` 文件头）：
```json
{"template": "/app/work/v0.pptx", "out": "/app/work/v1.pptx", "footer": "沿用初始稿页脚原文", "slide_numbers": true, "min_pt": 18,
 "slides": [
  {"keep": 1}, {"keep": 2},
  {"keep": 3, "set": {"body": ["压缩后的要点 1", "要点 2", "要点 3"]}, "source_note": "Paper Sec. 2.1–2.3, p.1–2", "notes": "E1：8 条压成 3 条；过渡；约 60 s"},
  {"keep": 5, "replace": {"Fig. 3  Light-off": "Fig. 2  Light-off"}},
  {"layout": "版式名（照 start 的输出）", "from": 6, "title": "一句结论", "image": "/app/work/fig3.png", "caption": "Paper Fig. 3: 题注要点",
   "source_note": "Paper Fig. 3, p.4", "notes": "E2：文字页换成原图；追问时的证据位置；约 75 s"},
  {"layout": "…", "title": "一句结论", "body": ["一行结论或提醒（≤ 2 行时表格占满宽度，这行排在表格下面）"],
   "table": [["Catalyst", "T50 (°C)"], ["Pt/Al2O3", "285"]], "caption": "Table 2 (paper): …", "table_size": 18, "source_note": "Paper Table 2, p.4", "notes": "…"},
  {"layout": "…", "title": "…", "body": ["要点 1", "  二级要点", "要点 3"], "source_note": "Paper Sec. 2.1, p.2", "notes": "…"}]}
```
- 保留页不传 notes（原备注原样带过）。改动页都写 `source_note`（论文章节/图表号 + 页码），页面上就能看到证据位置。`replace` 是纯文本替换（跨 run 可替换；未命中会 WARN）。
- 重建页要沿用原页里的图：`"image": "ppt/media/xxx.png"`（start 输出里 `[picture]` 那一行的路径）。
- 压缩/扩写/换受众/换语言：**术语、符号、变量名、单位与论文一致**；换语言时化学式、单位、数字不变。
  新建页可写 `Al_{2}O_{3}`、`cm^{-1}`、`Ce^{3+}`（真下标/上标）；edit 模式跟随初始稿写法（初始稿写 "Al2O3" 就保持一致）。
- 插图表：有数值 → 原生 `table`（逐格照抄，表头带单位）；只有原图 → `figcrop`（只裁图本身，题注不进图片，打印题注原文；
  打印 `WARN no figure pixels` = PDF 里没有这张图 → 不放，记 material_gaps）。**不重画没有数据支撑的曲线，不放占位图。**
- 删页前先确认该页不在 source preservation 里。
- 字号：正文 ≥ 工作单下限（没给就 18 pt）；表格 ≥ 14；图注 14；出处 11–12；不写字体、颜色；正文进版式里面积最大的占位符（build 打印 `placed` 行）。
- **事实更正的边界**：只有指令要求核对/更正（"check against the paper""fix numbers"之类），或某页按指令从论文重写，才在那一页用论文的值，并逐条写进
  `corrections.md`（`页 | 初始稿写法 | 论文写法 + 位置 | 处理`）。其余预检候选**不改**，写成"建议更正（未执行：不在指令内）"并列入 exceptions.undecidable。保留页永远不改。

### ④ build（每轮 1 次调用 = 一个版本）
`python3 $F build $WORK_DIR/spec_vK.json` → 构建、存 `vK.txt`、打印与 v0（和上一版）的 diff、把 deck/spec/diff 复制进 `$OUT_DIR`（从此刻起始终有可交付的稿）。
核对 diff：只出现指令要求的改动（页码数字变化属正常）。再看末尾的 **edit scope** 段：每个改动页"几个形状没动 / 改了哪个 / 哪些没带过来"。
`SCOPE WARN: slide N was rebuilt and lost baseline shapes …` = 重建把原页的图、表或手工文本框弄丢了：指令没要求删它们 → 改成 `keep` + `set` 原位编辑。
有计划外改动或 WARN（溢出→删字/拆页/换版式，不压字号）→ 改 spec 存成 `spec_v(K+1).json` 再 build，最多 2 轮，剩下的写进 uncertainty。构建失败不会覆盖上一版。

### ⑤ facts.json（+ corrections.md）
```json
{"content_map": [{"slide": 3, "action": "edit|keep|new", "instruction": "E1", "claim": "标题原文",
   "sources": [{"file": "paper.pdf", "locator": "Sec. 2.1, p.1", "quote": "原文短句"}], "numbers": ["0.5 wt%"], "visual": "原生表格 | 原图 Fig. 3 裁剪 | 保留原页", "seconds": 60}],
 "instructions_done": {"E1": "slide 3: 8 条压成 4 条（versions/diff_v0_v1.txt）", "E4": "not done: 论文没有 Table 2"},
 "exceptions": {"material_gaps": [], "undecidable": [], "run_failures": []},
 "uncertainty": ["…"], "template": "starting-deck.pptx", "mode": "edit"}
```
content_map 每页一行（保留页也写，来源可指向初始稿页）；**每个改动页的 `instruction` 必须写对应的 E 编号**（修改记录靠它把改动和指令对上，
漏写会被列为"没有指令依据的改动"）。instructions_done 每条指令一句：页号 + 做了什么 + **为什么这样改**，没做的写 `not done: 原因`。
`change_log.md` 不用手写：finish 对比 v0 与成稿自动生成（逐页：指令原文、你写的理由、改前/改后文字、哪些形状没动/改了/没带过来、具体回退写法、被删页、版本表）。
想补充说明（如"建议更正（未执行）"）就写 `$WORK_DIR/change_log.md`，会作为"Author's log"放在自动记录前面。

### ⑥ finish（1 次调用，必须最后跑）
`--slides` 总页数；`--min-pt` 字号下限；指令要求核对事实时加 `--fact-check`（论文不一致 = FAIL；不加则只是建议清单）。保留页/改动页的新旧对应关系
自动从 spec 推出（`keep`、`from`；不必再传 `--keep-map/--edit-map`）。它依次：LibreOffice 导出 PDF + 100 dpi PNG + pdffonts 实测（限时，失败照实写 render.json）；渲染初始稿存
`versions/v0_before.pdf` 供逐页对照；写 change_log.md（见上）；复制 plan/spec/diff/corrections；写 time_record.json；按含义填满 contract 的**每一个**根字段（任意键名）；跑 checker，
把判定写回 result.json（`by: check_result.py` 的行 + `checker_record`）并写 `version_diff.md`（逐页改前/改后）、`slide_audit.md`。
FAIL → 修 spec 重 build 再 finish，最多两轮；修不了的（没有渲染器、材料缺失）在 facts.json 写 `"status": "partial"` + `status_reasons` 后再 finish 一次。
WARN 是提示，逐条看一遍，不为清 WARN 反复重建。不要手改 checker 写的行。

## 编辑规则（每条针对一种已知失败）
1. **不整段塞**：段落改写成短语；单页 ≤ 5 条要点；溢出 WARN 清零。
2. **数字零改写**：数值、单位、n、条件照原文；不取整；自己算的数标"由 Table X 计算"。
3. **图注与图上标注一致**：caption 写原文编号（含子图字母）；编号必须在 start 列出的题注里。
4. **不碰母版**：只用模板版式与占位符；checker 逐字节比对母版/版式/主题。
5. **改一页不坏别页，改一处不坏同页**：保留页走 keep；只改文字走 keep + set；change_log.md 里保留页全部 identical，改动页没有无故丢失的形状。
6. **版本可回退**：每轮一个 spec_vK.json；change_log 每条有回退写法，`versions/v0.pptx` 是原稿。
7. **备注**：改动页和新页每页 2–4 句（过渡、强调、追问时的证据位置、秒数），不复述页面。
8. **缺口照实**：指令与材料冲突、证据不足、页数装不下——写 exceptions，按"材料缺失 / 无法判断 / 运行失败"分开；不编造数据和软件状态。

## 交付物（`$OUT_DIR`）与 result.json
`presentation.pptx`、`presentation.pdf`、`preview/*.png`、`result.json`、`content_map.json`、`plan.md`、`change_log.md`、`corrections.md`、`time_record.json`、
`version_diff.md`、`slide_audit.md`、`render.json`、`versions/`（spec_v*.json、diff_v*.txt、v0.pptx、v0.txt、v0_before.pdf、change_summary.json、instructions.json、precheck.md）。
result.json 保留 contract 全部根字段：`editable_source`（pptx、最终 spec、重建命令、版本列表）、`export_artifact`（pdf、png、页数、渲染器、字体实测与替换）、
`content_map`（逐页主张-来源）、`compliance_checks`（页数、模板继承、保留页、数字回查、图表号、备注、导出、字号、每条指令一行，PASS/FAIL/WARN + 依据）、
`exceptions`（material_gaps / undecidable / run_failures），另有 `uncertainty`、`status_reasons`、`checker_record`。
**status 只写一个词**：contract 有取值就用它的；否则 complete（全部指令执行、页数正确、checker PASS、PDF 存在）/ partial / failed（没有 pptx）。

## 异常处理速查
| 情况 | 做法 |
|---|---|
| 工作单与 task.md 冲突 | 以工作单为准，冲突写 exceptions.undecidable |
| 指令要的数据/图材料里没有 | 不编造；该页写"材料未提供"或不做，记 material_gaps，instructions_done 写 not done |
| 初始稿里有图表对象/SmartArt | keep 原样（同页文字仍可用 set/replace 原位改）；要改图表本身时改为原生表格或图片并记录 |
| `set` 找不到形状（WARN 列出形状名） | 换成列出的形状名或该形状里的一段原文；仍不行再按版式重建并在 uncertainty 说明 |
| 模板缺版式/占位符、槽位不足 | 换最接近版式，`image_box/table_box`（英寸）显式定位并记录 |
| 页数超限或装不下 | 合并/拆页以满足总页数，取舍写进 plan.md 与 uncertainty |
| soffice 缺失/超时/崩溃、字体缺失 | finish 自动换 profile 重试并限时；仍失败 → status=partial，原因进 run_failures，不声称有预览；字体替换照 pdffonts 实测写明 |
| deck_flow.py 某步不适用 | 底层命令可单独用：`pptx_kit.py inspect/build/figcrop/render`、`check_result.py --init / --assemble / --template … --baseline …`（见各文件头和 `resources/`） |
