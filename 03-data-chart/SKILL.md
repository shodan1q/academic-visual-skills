---
name: source-data-chart-lite
description: 按图表工单（如 artifacts/figure-workorder.json，source_value_chart）和原始论文/源数据（csv/xlsx）生成或修改科研数据图表——柱状（分组、带个体点）、折线、散点：数值、误差线、n 一律从源数据行复算，轴标签/单位/误差含义/显著性只取自原文图注；从生成的 SVG 回读柱高、误差线长度、点位置与数据对账，再解码渲染出的 PNG 查颜色、尺寸、字号、色盲可分；交付可编辑源（make_chart.py + chart_config.json + chart_data.csv + 文字可编辑 SVG）、真实 PNG/PDF、图元→源数据行号映射、工单逐条对照、源文件级修改记录与分类异常。精简版：标准库脚本 + matplotlib 模板。不用于：选择统计方法、实验设计、示意图/机制图。
---

# 科研数据图表生成与编辑（精简版 1.1）

## 路径与预算
- 输入 `/input/case.json`、task.md、材料（常见：`source/*.pdf` 原始论文、`artifacts/figure-workorder.json` 工单、`data/*.csv|xlsx` 源数据）。先 `ls -R /input`，路径以 case.json 为准。工作目录 `/app/work`，交付 `/app/output`，本 Skill 在 `/skills/weekly-skill`（下文 `$S`）。环境变量 `CASE_JSON`/`WORK_DIR`/`OUT_DIR` 若存在一律优先。
- 预算 64 次请求、900 秒：本流程约 10–14 次调用，不要超过 30 次。渲染/绘图前加 `timeout 120`。只用 python 改文件，不用 `sed -i`。Python 3.8 兼容。
- 工具：`resources/make_chart_template.py`（绘图源模板，只改 JSON 配置）、`scripts/chartkit.py`（table / marks / diff / svgchart）、`scripts/pixcheck.py`（看渲染像素）、`scripts/export_check.py`（tools / render / check）。

## 步骤
1. **读任务与工单（1–2 次）**：`ls -R /input; cat /input/case.json; tail -40 <task.md>; cat <工单>`。记下 case_id（键 `case_id`/`caseId`/`id`）、output_contract 全部字段、工单每一项（图型、x/系列/y、单位、误差要求、must_show、export 的 width_mm/dpi/formats/min_font_pt、edit_request）。**工单每个键都是一条要核对的要求**，第 8 步逐条写进 compliance_checks。
2. **骨架（第 3 次调用以内，一条命令）**：
   `python3 -c "import json,os;c=json.load(open(os.environ.get('CASE_JSON','/input/case.json')));o=os.environ.get('OUT_DIR','/app/output');os.makedirs(o,exist_ok=True);f=c.get('output_contract') or [];f=list(f) if not isinstance(f,dict) else list(f.get('properties',f));r={k:'生成中' for k in f};r.update(case_id=c.get('case_id',c.get('caseId',c.get('id'))),status='partial',status_reasons=['生成中']);json.dump(r,open(o+'/result.json','w'),ensure_ascii=False,indent=1)" && timeout 60 python3 $S/scripts/export_check.py tools`
   骨架里的“生成中”会被 check 判 FAIL——它只是预算耗尽时的保底，不是完成。
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
5. **出图（1 次）**：`cd /app/output && timeout 120 python3 make_chart.py`。打印每个图元的均值、误差、n、CSV 行号和 WARN（n 与原文不符、空值被排除、字体缺字）。WARN 不能消掉的（数据本身如此）一律进 exceptions。matplotlib 不可用 → 见“异常处理”。
6. **对账 + 看像素（1 次）**：
   `python3 $S/scripts/chartkit.py marks chart.svg chart_marks_expected.csv && python3 $S/scripts/pixcheck.py chart.svg --workorder <工单路径>`
   marks 用同一 SVG 里的 y 轴刻度标签标定像素↔数值，再回读柱长、误差线全长（上限−下限）、个体点/折线顶点位置，与数据计算的期望值比较（偏差 > 轴长 1 % 即 MISMATCH；读不到刻度才退回拟合），写 `chart_mark_check.json`；pixcheck 解码 PNG：宽度 = width_mm×dpi、不空白不裁切、每根柱渲染色 = 声明的系列色、系列色在图上出现且无多余颜色、protan/deutan/tritan 模拟与灰度下可分、最小字号 ≥ min_font_pt，写 `chart_pixel_check.json`。任何 FAIL → 改 chart_config.json 重跑第 5–6 步。
7. **源文件级修改（1–2 次）**：把工单 edit_request（或任务里的修改要求）写成 `edit_v2.json`（只含要改的键，如 `{"colors": {"DMXAA": "#D55E00"}, "ylabel": "..."}`）；没有修改要求就做一次演示编辑（改 ylabel 措辞），change_log 标“演示，不属于正式图”。然后：
   `timeout 120 python3 make_chart.py chart_v2 edit_v2.json && python3 $S/scripts/chartkit.py diff chart.svg chart_v2.svg > edit_diff.json && python3 $S/scripts/chartkit.py marks chart_v2.svg chart_v2_marks_expected.csv && python3 $S/scripts/pixcheck.py chart_v2.svg --workorder <工单路径>`
   修改请求引入原文没有的内容（新数值、新显著性）→ 照做但 exceptions 记 `user_request_not_in_source`；与色盲规则冲突（如红/绿两系列）→ 照做、pixcheck 的 FAIL 原样写进 exceptions，并另给一个合规备选色。
8. **组装 result.json 并自检（2–3 次）**：运行下方模板（按本案改 `<…>` 处），再 `python3 $S/scripts/export_check.py check`，FAIL 改到 PASS；对照 `$S/resources/checklist.md`。

## result.json 组装模板（第 8 步）
```python
import json,os; O=os.environ.get("OUT_DIR","/app/output"); L=lambda p:json.load(open(os.path.join(O,p),encoding="utf-8"))
r=L("result.json"); cm=L("chart_content_map.json"); mk=L("chart_mark_check.json"); px=L("chart_pixel_check.json")
ex=[json.loads(l) for l in open(os.path.join(O,"export_log.jsonl"),encoding="utf-8")]; d=L("edit_diff.json") if os.path.exists(os.path.join(O,"edit_diff.json")) else {"changes":[]}
r.update(status="partial", status_reasons=["<逐条：未决矛盾/缺口；全部解决才写 complete>"],
 editable_source={"script":"make_chart.py","config":"chart_config.json","data":"chart_data.csv","svg":"chart.svg","edited":["edit_v2.json","chart_v2.svg"],
   "how_to_rerun":"cd /app/output && python3 make_chart.py [stem] [override.json]","svg_text_editable":True,"data_sha256":cm["data"]["sha256"]},
 export_artifact=[{"file":e["stem"]+"."+f,"format":f,"dpi":e["dpi"],"size_mm":e["size_mm"],"fonts":e["fonts"],"pdf_fonttype":e["pdf_fonttype"]} for e in ex for f in e["formats"]]
   +[{"pixel_check":"chart_pixel_check.json","png_px":px["export_png_px"],"expected_width_px":px.get("expected_width_px"),"min_font_pt":px["min_font_pt"],"colour_vision":px["colour_vision"],"fails":px["fails"]}],
 content_map=dict(cm,file="chart_content_map.json",mark_check={"verdict":mk["verdict"],"samples":mk["samples"],"file":"chart_mark_check.json"}),
 compliance_checks=[{"requirement":"<工单/任务原文一项>","result":"<pass/partial/fail 选一>","element_ids":["<SVG 里的 id，如 bar-0-1、err-0-1、pts-0-1、sig-0、ylabel、legend>"],"evidence":"<怎么满足、出处>"},
   {"requirement":"data-to-mark check","result":"pass" if mk["verdict"]=="PASS" else "fail","element_ids":[],"evidence":"chart_mark_check.json: %d samples"%mk["samples"]},
   {"requirement":"rendered pixel check","result":"pass" if not px["fails"] else "fail","element_ids":[],"evidence":"chart_pixel_check.json"}],
 exceptions=[{"category":"<material_missing/undecidable/contradiction/run_failure/user_request_not_in_source/data_excluded 选一>","detail":"<…>","handling":"<…>"}],
 change_log=[{"version":"v2","request":"<修改请求原文>","override":L("edit_v2.json") if os.path.exists(os.path.join(O,"edit_v2.json")) else {},"svg_changes":d["changes"]}],
 versions={"skill":"source-data-chart-lite 1.1","data_sha256":{cm["data"]["origin"]:cm["data"]["origin_sha256"]},"matplotlib":ex[-1].get("matplotlib")},
 artifacts=[{"path":p,"role":"source" if p.endswith((".py",".json",".csv")) else "export" if p.endswith((".svg",".pdf",".png")) else "record"} for p in sorted(os.listdir(O)) if p!="result.json"])
json.dump(r,open(os.path.join(O,"result.json"),"w",encoding="utf-8"),ensure_ascii=False,indent=1)
```
- compliance_checks 覆盖工单每一项（图型、x/系列/y、单位、误差、must_show 每条、export 每个参数、edit_request）和下方 7 条标注规则；`element_ids` 必须是 SVG 里真实存在的 id（check 会核对）。
- contract 字段名不同就按含义映射：源文件/路径 → editable_source；导出件 → export_artifact；来源/映射/数据 → content_map；检查/合规/校验 → compliance_checks；异常/不确定/缺口 → exceptions。看不懂的字段填最接近内容并在 `run_notes` 说明。
- **status 只写一个词**：contract 给了词表就用它的；否则 complete / partial / failed。exceptions 里有未决 contradiction / undecidable / material_missing → partial；没出图 → failed。材料缺失、无法判断、运行失败用不同 category 分别写。

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
| 标签过长或遮挡 | `x_labels` 加 `\n`、缩短（原名进图注）；pixcheck 的裁切 WARN 要处理 |
| 图型不是柱/线/散点（箱线、热图） | 照模板写法自己画，保留 gid 与 expected csv，content_map 手写；marks 不适用的写进 compliance_checks |
| matplotlib 缺失 | 写 `chart_spec.json`，`chartkit.py svgchart chart_spec.json chart.svg`，`timeout 300 python3 $S/scripts/export_check.py render chart.svg --dpi <dpi>`，期望值只写 `mark-*` 柱/点，再跑 marks + pixcheck；status partial |
| 字体缺失 / 导出失败 | 记录 export_log 与原因，exceptions `run_failure`，不伪造预览 |

## 不做的事
不编造或“美化”数值；不画原文没有的显著性；不从图片反读数值当数据；不只交 PNG；图上不留内部 id/TODO；不伪造回读、像素检查或渲染结果。
