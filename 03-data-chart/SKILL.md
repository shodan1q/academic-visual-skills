---
name: source-data-chart-lite
description: 按图表工单（如 artifacts/figure-workorder.json，source_value_chart）和原始论文/源数据（csv/xlsx）生成或修改科研数据图表——柱状（分组、带个体点）、折线、散点：数值、误差线、n 一律从源数据行复算，轴标签/单位/误差含义/显著性只取自原文图注；从生成的 SVG 回读柱高、误差线长度、点位置与数据对账，再解码渲染出的 PNG 查颜色、尺寸、字号、色盲可分；交付可编辑源（make_chart.py + chart_config.json + chart_data.csv + 文字可编辑 SVG）、真实 PNG/PDF、图元→源数据行号映射、工单逐条对照、源文件级修改记录与分类异常。精简版：标准库脚本 + matplotlib 模板。不用于：选择统计方法、实验设计、示意图/机制图。
---

# 科研数据图表生成与编辑（精简版 1.2）

## 路径与预算
- 输入 `/input/case.json`、task.md、材料（常见：`source/*.pdf` 原始论文、`artifacts/figure-workorder.json` 工单、`data/*.csv|xlsx` 源数据）。先 `ls -R /input`，路径以 case.json 为准。工作目录 `/app/work`，交付 `/app/output`，本 Skill 在 `/skills/weekly-skill`（下文 `$S`）。环境变量 `CASE_JSON`/`WORK_DIR`/`OUT_DIR` 若存在一律优先。
- 预算 64 次请求、900 秒：本流程约 10–14 次调用，不要超过 30 次。渲染/绘图前加 `timeout 120`。只用 python 改文件，不用 `sed -i`。Python 3.8 兼容。
- 工具：`resources/make_chart_template.py`（绘图源模板，只改 JSON 配置）、`scripts/chartkit.py`（table / marks / diff / svgchart）、`scripts/pixcheck.py`（看渲染像素，只给提示）、`scripts/export_check.py`（skeleton / tools / render / assemble / check）。
- 任何脚本或外部工具不可用、报错：记录原因，换下一条路或跳过，同一步重试不超过 2 次。

## 步骤
1. **读任务与工单（1–2 次）**：`ls -R /input; cat /input/case.json; tail -40 <task.md>; cat <工单>`。记下 case_id（键 `case_id`/`caseId`/`id`）、output_contract 全部字段、工单每一项（图型、x/系列/y、单位、误差要求、must_show、export 的 width_mm/dpi/formats/min_font_pt、edit_request）。**工单每个键都是一条要核对的要求**，第 8 步逐条写进 compliance_checks。
2. **骨架（第 3 次调用以内，一条命令）**：`python3 $S/scripts/export_check.py skeleton; timeout 60 python3 $S/scripts/export_check.py tools`
   skeleton 认得各种 contract 写法（列表、properties/required、字段对象、中文/驼峰键），写出 case_id + 每个字段“生成中”+ status partial。“生成中”只是预算耗尽时的保底；第 8 步 assemble 会全部替换。
3. **读源（1–3 次）**：
   - 论文：`pdftotext -layout x.pdf /app/work/src.txt`；没有 pdftotext 用 `python3 -c "import fitz,sys;open(sys.argv[2],'w').write('\n'.join(p.get_text() for p in fitz.open(sys.argv[1])))" x.pdf /app/work/src.txt`（或 pypdf；都没有 → exceptions `material_missing`），再 `grep -n -i -E "fig(ure)?\.? ?<号>|mean|s\.e\.m|s\.d\.|sem|n ?= ?[0-9]|P ?[<=]|anova|t-test|wilcoxon|normali|fold|relative" /app/work/src.txt`，把**目标图的图注全文**和对应结果段、方法段读完。逐项抄下：y 量与单位/归一化、误差线含义、n 及其单位（小鼠/患者/培养）、检验方法与每个显著性符号及其比较对象、实体名写法（基因斜体、蛋白正体、化合物全名）。每项记“src.txt 第 N 行”。
   - 数据：`python3 $S/scripts/chartkit.py table <csv|xlsx> --out /app/work`（带行号；xlsx 每个 sheet 存成 csv）。看清列名、分组取值、空值/非数字、单位列。
4. **写配置（1 次）**：`cp $S/resources/make_chart_template.py /app/output/make_chart.py; cp <源数据或 sheet csv> /app/output/chart_data.csv`，再写 `/app/output/chart_config.json`（键见模板 CONFIG；不改 Python）。示例：
```json
{"data_origin": "/input/data/fig3b_source.csv", "kind": "bar", "x": "genotype", "x_order": ["WT", "Sting1-/-"],
 "x_labels": {"Sting1-/-": "$\\mathit{Sting1}^{-/-}$"}, "series": "treatment", "series_order": ["vehicle", "DMXAA"],
 "y": "Ifnb1_rel", "id_col": "sample_id", "error": "sem", "points": true, "n_declared": 4,
 "ylabel": "$\\mathit{Ifnb1}$ mRNA (fold vs WT vehicle)", "width_mm": 89, "height_mm": 65, "dpi": 600, "font_pt": 7,
 "sig": [{"a": ["WT", "vehicle"], "b": ["WT", "DMXAA"], "label": "***", "src": "src.txt L18 (Fig. 3 legend)"}],
 "caption": "<从图注照抄的说明，含检验方法>",
 "src": {"ylabel": "src.txt L9-10 (Methods: normalised to Actb, fold vs WT vehicle)", "error": "src.txt L17 'mean ± s.e.m.'", "n_declared": "src.txt L17", "x_labels": "src.txt L7 Sting1-/-"}}
```
   - `error` 必须等于图注所写（s.e.m.→`sem`，s.d.→`sd`，95% CI→`ci95`）；图注没写 → `sem` 以外都不猜，写 exceptions `undecidable` 并在 status_reasons 说明。
   - `sig` 只放原文报告过的比较，符号照抄；原文写 NS 的比较可不画或画 `NS`，都要在 compliance_checks 说明。没有统计 → `[]`。
   - 颜色默认 Okabe-Ito（色盲友好）；工单/修改请求指定颜色才写 `colors`。长标签用 `x_labels` 换行（`\n`）。
5. **出图（1 次）**：`cd /app/output && timeout 120 python3 make_chart.py`。打印每个图元的均值、误差、n、CSV 行号和 WARN（n 与原文不符、空值被排除、字体缺字）。数据本身造成的 WARN 不要“修”，写进 exceptions（assemble 也会自动补录）。matplotlib 不可用 → 见“异常处理”。
6. **对账 + 看像素（1 次）**：
   `python3 $S/scripts/chartkit.py marks chart.svg chart_marks_expected.csv; python3 $S/scripts/pixcheck.py chart.svg --workorder <工单路径>`
   marks 用同一 SVG 里的 y 轴刻度标签标定像素↔数值，再回读柱长、误差线全长（上限−下限）、个体点/折线顶点位置，与数据计算的期望值比较（偏差 > 轴长 1 % 即 MISMATCH；读不到刻度才退回拟合），写 `chart_mark_check.json`。marks MISMATCH = 数据画错，改 chart_config.json 重跑第 5–6 步，**最多 2 轮**；仍不过就在 exceptions 写 `run_failure` 并点名 `chart_mark_check.json`，继续往下。
   pixcheck 只给提示（退出码恒为 0）：解码 PNG 看宽度 = width_mm×dpi、不空白不裁切、柱渲染色 = 声明色、系列色出现且无多余颜色、protan/deutan/tritan 与灰度可分、最小字号 ≥ min_font_pt，写 `chart_pixel_check.json`。明显问题（宽度/dpi 不对、红绿配色、字号低于下限）改一次；其余 WARN 记录即可，不为它循环。没有 PNG 或读不了时它写 `skipped` 并跳过。
7. **源文件级修改（1–2 次）**：把工单 edit_request（或任务里的修改要求）写成 `edit_v2.json`（只含要改的键，如 `{"colors": {"DMXAA": "#D55E00"}, "ylabel": "..."}`）；没有修改要求就做一次演示编辑（改 ylabel 措辞），notes.json 的 edit_request 写“演示编辑（不属于正式图）：…”。然后：
   `timeout 120 python3 make_chart.py chart_v2 edit_v2.json && python3 $S/scripts/chartkit.py diff chart.svg chart_v2.svg > edit_diff.json && python3 $S/scripts/chartkit.py marks chart_v2.svg chart_v2_marks_expected.csv; python3 $S/scripts/pixcheck.py chart_v2.svg --workorder <工单路径>`
   修改请求引入原文没有的内容（新数值、新显著性）→ 照做但 exceptions 记 `user_request_not_in_source`；与色盲规则冲突（如红/绿、两系列同色）→ 照做、pixcheck 的 WARN 原样写进 exceptions，并另给一个合规备选色，不再改图。
8. **组装 result.json 并自检（1–3 次）**：把只有你能判断的内容写进 `/app/work/notes.json`（格式见下），然后
   `python3 $S/scripts/export_check.py assemble /app/work/notes.json`
   assemble 读 OUT_DIR 里已有的文件（content map、mark/pixel check、export_log、edit_diff、edit_v2、caption；**缺哪个都不报错**），按含义把**每个 contract 字段**填好（字段名是什么都行），再自动运行 check。FAIL 只改它点名的那一处（notes.json 或对应文件），再跑 assemble，最多 2 轮；WARN 记录或忽略。预算快用完时先跑一次 assemble（没有 notes.json 也能填满所有字段），再继续改进。

## notes.json（第 8 步；只写判断，文件信息由 assemble 自动收集）
```json
{"status": "partial", "status_reasons": ["WT/DMXAA 只有 3 个可用值，图注写 n = 4"],
 "compliance_checks": [{"requirement": "<工单/任务原文一项>", "result": "pass", "element_ids": ["bar-0-1", "err-0-1", "pts-0-1", "sig-0", "ylabel", "legend"], "evidence": "怎么满足 + 出处（src.txt L17）"}],
 "exceptions": [{"category": "contradiction", "detail": "图注 n = 4，WT/DMXAA 可用 3 行（row 8 S07 为空）", "handling": "按数据画，图注写实际 n"}],
 "edit_request": "<修改请求原文>", "summary": "<一句话：画了什么、来自哪张表>",
 "fields": {"<某个 contract 字段>": "<只在你想亲自指定该字段内容时写>"}}
```
- compliance_checks 覆盖工单每一项（图型、x/系列/y、单位、误差、must_show 每条、export 每个参数、edit_request）和下方 7 条标注规则；result 用 pass / partial / fail；`element_ids` 写 SVG 里真实存在的 id（check 核对，不存在只给 WARN）。assemble 会自动追加 data-to-mark 与像素检查两行。
- exceptions 的 category：material_missing / undecidable / contradiction / run_failure / user_request_not_in_source / data_excluded。content map 里的 n 不符、被排除的行、缺失的导出格式、跳过的像素检查，assemble 会自动补录（已写过的不重复）。
- 字段映射（自动）：源文件/脚本/spec → editable_source；导出/预览/渲染 → export_artifact；来源/映射/数据/元素 → content_map；检查/校验/合规/QA → compliance_checks；异常/不确定/问题/缺口 → exceptions；修改/版本历史 → change_log；图注 → caption；状态 → 一个词；认不出的字段填运行摘要 + 文件清单并记进 `run_notes`。
- **status 只写一个词**：contract 给了词表，assemble 会换成它的词；否则 complete / partial / failed。exceptions 里有未决 contradiction / undecidable / material_missing → partial；没出图 → assemble 强制 failed。材料缺失、无法判断、运行失败用不同 category 分别写。

## 标注规则（每条在 compliance_checks 写结论与出处）
1. 轴标签 = 量 + 单位/归一化方式（照方法段；量级换算写进单位，如 ×10³ cells/mL）；柱状图 y 从 0 开始；对数轴要在图注说明。
2. 图例项 = 系列，名称与数据表取值或原文写法一致；单系列不放图例；颜色与图例同源（模板自动，pixcheck 复核）。
3. 误差线含义照图注；SEM = SD/√n 由模板按实际可用行数计算；图注 n 与可用行数不符 → exceptions `contradiction`（不改数据、不补值）。
4. 显著性只画原文报告的比较，符号与阈值照抄，图注写检验方法；本 Skill 不重算 p 值。
5. n 写明统计单位（小鼠/患者/样地，不是孔或技术重复）；被排除的行（空值、失败孔）由模板写进图注和 content_map，并记 exceptions `data_excluded`。
6. 实体名照原文：基因斜体（`$\\mathit{Ifnb1}$`），蛋白正体，基因型上标 `^{-/-}`，化合物用原文缩写并在图注给全名；中文标签先看 tools 的 cjk_fonts，缺字体改英文并记录。
7. 原文文字里的近似数（“约 40 倍”）与数据复算不符 → 按数据画，exceptions `contradiction` 写两处出处。

## 异常处理
| 情况 | 处置 |
|---|---|
| 缺列 / 列名与工单不符 | 模板会报列不存在：按实际列名改配置，写 exceptions `contradiction` 或 `material_missing` |
| 空值、非数字 | 模板自动排除并记行号；exceptions `data_excluded` |
| 量级异常（单位不一、相差 10³） | 不擅自换算；按材料单位画并列 `undecidable` |
| 标签过长或遮挡 | `x_labels` 加 `\n`、缩短（原名进图注）；pixcheck 报裁切时改一次 |
| 图型不是柱/线/散点（箱线、热图） | 照模板写法自己画，保留 gid 与 expected csv，content_map 手写；marks 不适用的写进 compliance_checks |
| matplotlib 缺失 | 自己按数据算均值/误差（写出算式与行号），写 `chart_spec.json`，`chartkit.py svgchart chart_spec.json chart.svg`，`timeout 300 python3 $S/scripts/export_check.py render chart.svg --dpi <dpi>`；期望值 `chart_marks_expected.csv` 只写 `mark-*` 柱/点，再跑 marks + pixcheck；status partial |
| 没有 SVG 渲染器（rsvg/cairosvg/inkscape/chrome/magick/soffice 都无） | render 自动退到内置渲染：有 matplotlib 出 PNG+PDF，否则出标准库矢量 PDF（base-14 字体，非拉丁字形显示为 ?，export_log 有 note）；没有 PNG 就记 run_failure，不重试、不伪造 |
| 字体缺失 / 导出失败 | 记录 export_log 与原因，exceptions `run_failure`，不伪造预览 |

## 不做的事
不编造或“美化”数值；不画原文没有的显著性；不从图片反读数值当数据；不只交 PNG；图上不留内部 id/TODO；不伪造回读、像素检查或渲染结果。
