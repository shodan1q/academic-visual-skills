---
name: source-data-chart-lite
description: 从源数据（csv/xlsx/统计输出/实验记录）生成或修改科研数据图表——柱状、折线、散点、箱线、热图、多面板：每个图元的数值来自源数据的具体行列（不抄摘要里的近似值），按期刊/模板调样式（字号、线宽、配色、尺寸、dpi），校验标注（轴标签与单位量级、图例与系列、误差线含义、显著性只来自统计输出、样本量），并从生成的 SVG 回读图元做数据—图元核对；交付可编辑源（绘图脚本 + 数据副本 + 文字可编辑的 SVG）+ 真实 PNG/PDF + 图元→源数据映射 + 源级修改记录。精简版：标准库脚本，matplotlib 有则用、无则回退。不用于：选择统计方法、实验设计、示意图/机制图。
---

# 科研数据图表生成与编辑（精简版）

## 路径与预算
- 输入 `/input/case.json`（+ task.md 与材料，路径以 case.json 为准，先 `ls -R /input`）；工作目录 `/app/work`；交付 `/app/output`；本 Skill 在 `/skills/weekly-skill`（下文 `$S`）。环境变量 `CASE_JSON`/`WORK_DIR`/`OUT_DIR` 若存在一律优先。
- 预算 64 次请求、900 秒：目标 ≤ 30 次调用。渲染/绘图命令前加 `timeout 120`。只用 python 改文件，不用 `sed -i`。Python 3.8 兼容（f-string 花括号里不放反斜杠）。
- 工具：`python3 $S/scripts/chartkit.py`（table 读表带行列号、marks 图元回读核对、svgchart 无 matplotlib 时的回退、diff 记改动）；`python3 $S/scripts/export_check.py`（tools 探测、render SVG→PNG/PDF、check 自检）。

## 步骤
1. **读任务（1–2 次）**：读 case.json 全文和 task.md 的“组织方具体输入修订”。记下 case_id（键 `case_id`/`caseId`/`id`）、图型、要画的变量/分组/面板、误差类型、显著性要求、目标期刊或模板（尺寸 mm/in、dpi、字号、字体、配色、格式）、是否有修改请求、output contract 全部字段（键可为 output_contract/outputContract/deliverables/中文；字段可为 snake/camel/中文/properties+required）。
2. **骨架（第 3 次调用以内）**：写 `/app/output/result.json`：case_id + 每个 contract 字段（先填一句“生成中”）+ `"status":"partial"` + `"status_reasons":["生成中"]`。同时 `timeout 60 python3 $S/scripts/export_check.py tools`（看 matplotlib、渲染器、中文字体）。
3. **读数据（1–3 次）**：`python3 $S/scripts/chartkit.py table <file.xlsx|csv> --out /app/work`（xlsx 每个 sheet 存成 csv，打印 Sheet!行号）。PDF 表格用 `pdftotext -layout`。统计输出、图注草稿、实验记录全部读完。
4. **数据映射 `/app/work/datamap.md`（1–2 次）**：每个图元一行：`图元 id | 系列/组 | 数值 | 单位与量级 | 来源 文件!列+行 | 复算方式(均值/SD/SEM/n)`。均值、SD、SEM、n 用 python 从原始行复算并标“复算”；汇总表与原始数据不一致记为冲突。再过下方“标注规则”。
5. **写可编辑源（2–4 次）**：把用到的数据原样复制到 `/app/output/chart_data.csv`（注明来自哪个文件/sheet），写 `/app/output/make_chart.py`（模板见下），`timeout 120 python3 /app/output/make_chart.py` → chart.svg / chart.pdf / chart.png + chart_marks_expected.csv + export_log.jsonl。matplotlib 不可用：写 svgchart 规格 `/app/output/chart_spec.json`，`python3 $S/scripts/chartkit.py svgchart chart_spec.json chart.svg`，再 `timeout 300 python3 $S/scripts/export_check.py render /app/output/chart.svg`，图元 id 为 `mark-<系列>-<序号>`。
6. **数据—图元回读核对（1 次）**：`python3 $S/scripts/chartkit.py marks /app/output/chart.svg /app/output/chart_marks_expected.csv`（对数轴加 `--log`）。必须 PASS；结果原样写进 result.json 的 `mark_check`。期望值 csv 必须由数据计算得到，不能从画好的图元读。
7. **记录（1–2 次）**：`chart_source_map.md`（图元 id | 图上数值/标签 | 来源 文件!行列 | 复算方式 | 一致?）；`chart_caption.md`（图注：图型、误差含义、n 与统计单位、检验方法与 p 值来源、显著性符号含义、数据文件）。
8. **源级编辑**：有修改请求就照做；没有就做一次“演示编辑”（如改 STYLE 里的 y 轴标签或配色），另存 `chart_v2.*` 并在 change_log 标“演示，不属于正式图”。做法：改 STYLE/数据 → `python3 make_chart.py chart_v2`（脚本第一个参数是输出名）→ `chartkit.py diff chart.svg chart_v2.svg` → 把改动和 diff 写进 change_log → 对 v2 再跑 marks。不得在 PNG 上改。
9. **填 result.json 并自检（2–3 次）**：按“result.json 规则”填写，运行 `python3 $S/scripts/export_check.py check`，FAIL 改到 PASS；再对照 `$S/resources/checklist.md`。

## make_chart.py 模板（照此改，保留 gid、STYLE、期望值与导出记录）
```python
import csv, json, os, statistics as st, sys
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
HERE = os.path.dirname(os.path.abspath(__file__))
HAVE = {f.name for f in fm.fontManager.ttflist}   # 中文必须把已安装的 CJK 字体放第一位，否则变方框
CJK = [f for f in ("Noto Sans CJK SC", "Source Han Sans SC", "WenQuanYi Micro Hei", "SimHei", "Microsoft YaHei", "PingFang SC", "Arial Unicode MS") if f in HAVE]
STYLE = {"size_in": (3.5, 3.0), "fs": 9, "dpi": 300, "colors": ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#56B4E9", "#D55E00"],
         "font": CJK[:1] + ["Arial", "Liberation Sans", "DejaVu Sans"], "ylabel": "<量 (单位)>"}
print("CJK font:", CJK[:1] or "NONE -> use English labels")
plt.rcParams.update({"svg.fonttype": "none", "pdf.fonttype": 42, "font.family": "sans-serif",
                     "font.sans-serif": STYLE["font"], "font.size": STYLE["fs"], "axes.unicode_minus": False})
rows = list(csv.DictReader(open(os.path.join(HERE, "chart_data.csv"), encoding="utf-8")))
groups = ["<组1>", "<组2>"]                       # 顺序与材料一致
vals = {g: [float(r["<数值列>"]) for r in rows if r["<分组列>"] == g] for g in groups}
mean = [st.mean(vals[g]) for g in groups]; sd = [st.stdev(vals[g]) for g in groups]   # 或 SEM = sd/sqrt(n)
fig, ax = plt.subplots(figsize=STYLE["size_in"])
ids = ["bar-%d" % k for k in range(len(groups))]
for b, i in zip(ax.bar(groups, mean, yerr=sd, capsize=4, color=STYLE["colors"][:len(groups)], edgecolor="black", linewidth=0.6), ids):
    b.set_gid(i)                                   # 每个图元一个 gid -> SVG 里的 id
for k, g in enumerate(groups):                     # 原始点（n 小时建议画）
    ax.scatter([k] * len(vals[g]), vals[g], s=10, color="black", zorder=3, gid="pts-%d" % k)
ax.set_ylabel(STYLE["ylabel"]); ax.spines[["top", "right"]].set_visible(False); fig.tight_layout()
stem = os.path.join(HERE, sys.argv[1] if len(sys.argv) > 1 else "chart")
for ext in ("svg", "pdf", "png"):
    fig.savefig(stem + "." + ext, dpi=STYLE["dpi"])
with open(stem + "_marks_expected.csv", "w", encoding="utf-8") as f:     # 期望值来自数据，不来自图元
    f.write("id,value\n" + "".join("%s,%s\n" % (i, m) for i, m in zip(ids, mean)))
    f.write("".join("pts-%d,%s\n" % (k, ";".join(str(v) for v in vals[g])) for k, g in enumerate(groups)))
with open(os.path.join(HERE, "export_log.jsonl"), "a", encoding="utf-8") as f:
    f.write(json.dumps({"stem": os.path.basename(stem), "formats": ["svg", "pdf", "png"], "dpi": STYLE["dpi"], "size_in": STYLE["size_in"],
                        "svg_fonttype": "none", "pdf_fonttype": 42, "matplotlib": matplotlib.__version__}) + "\n")
```
- 折线/散点：`ax.plot(x, y, marker="o", gid="line-<系列>")`、`ax.scatter(..., gid="pts-<系列>")`，期望值写 `line-<系列>,y1;y2;…`。箱线/热图：marks 不适用，在脚本里回读 `ax.get_children()` 或打印矩阵与数据比对，结论写进 mark_check。
- 多面板：`fig, axs = plt.subplots(1, n)`，面板字母 `ax.text(-0.15, 1.05, "a", transform=ax.transAxes, fontweight="bold")`；gid 加面板前缀。
- 显著性括线：`ax.plot([x1,x1,x2,x2],[y-h,y,y,y-h])` + `ax.text`，符号与 p 值只取自统计输出。

## 标注规则（每条在 datamap.md 下写结论）
1. 轴标签 = 量 + 单位（量级换算写进单位，如 ×10³ cells/mL）；刻度范围包住全部数据与误差线；柱状图从 0 开始；对数轴要说明。
2. 图例项 = 系列，名称与数据表原文一致，数量一致；单系列不放图例。
3. 误差线含义（SD/SEM/95% CI）写在图注，并用数据核对（SEM = SD/√n）；材料说法矛盾时按数据画并列入待确认。
4. 显著性标记只画统计输出里存在的比较；符号阈值写在图注；材料没有检验就不画星号。
5. n 写明统计单位（动物/患者/样地，而不是细胞或技术重复）。
6. 科学实体名（基因斜体、物种、化合物）照抄材料；中文标签要确认字体存在（`tools` 的 cjk_fonts），否则改英文并记录。
7. 期刊尺寸：单栏约 3.5 in（85–89 mm）、双栏约 7.1 in（180 mm）；导出字号 6–9 pt；线宽 ≥ 0.5 pt；配色色盲友好，灰度可分。

## result.json 规则
- 必有：`case_id`、每个 contract 字段、`status`、`status_reasons`、`artifacts`（路径相对 /app/output，带 role：source/data/preview/export/record）、`data_trace`/`source_map`（图元 → 文件!行列 → 数值 → 复算方式，内嵌表 + `chart_source_map.md`）、`mark_check`（marks 输出）、`annotation_check`（7 条标注规则逐条结论）、`export_checks`（格式、尺寸 in/mm、dpi、PNG 像素、SVG 文字可编辑、PDF 字体嵌入 Type42、中文字体、色盲/灰度）、`change_log`、`versions`（skill lite-1.0、matplotlib 版本、数据文件名与 sheet）、`uncertainties`、`material_gaps`、`needs_human_confirmation`。
- 字段映射按含义：要“源文件/路径”的填 `make_chart.py` + `chart_data.csv` + `chart.svg`；要“导出件”的填 png/pdf/svg 路径加 export_checks；要“映射/表”的给内嵌表并附文件路径；看不懂的字段填最接近内容并在 `run_notes` 说明。
- 任何字段不得留空、TODO、“生成中”。**status 只写一个词**：contract 列了可选词（含 enum）用它的；否则 complete / partial / failed。complete = 图、预览、mark_check PASS、标注核对通过且无未决冲突；有缺口或待确认 = partial（原因逐条写进 status_reasons）；没出图 = failed。

## 异常处理
| 情况 | 处置 |
|---|---|
| 缺列、空值、非数字 | 跳过并在 datamap 写明行号与原因；影响结论的写 material_gaps |
| 量级异常（单位不一、相差 10³） | 不擅自换算；按材料单位画并列待确认 |
| sheet 名/列名与任务描述不符 | 按实际文件，写 uncertainties |
| 标签过长或遮挡 | 换行、旋转刻度 30°、缩短（原名进图注） |
| matplotlib 缺失 | 走 svgchart + render；仍失败则交 SVG 并 status partial |
| 字体缺失 / 导出失败 | 记录 export_log 与原因，不伪造预览 |

## 不做的事
不编造或“美化”数值；不画统计输出里没有的显著性；不从图上反读值当数据；不只交 PNG；图上不留内部 id/TODO；不伪造回读或渲染结果。
