# source-data-chart-lite：科研数据图表生成与编辑（精简版）

## 用途
从表格、统计输出或实验记录出发，生成或修改能直接投稿的数据图表（柱状、折线、散点、箱线、热图、多面板），并保证“画得像也画得准”：每个图元的数值能回到源数据的具体行列；从生成的 SVG 回读图元几何、与源数据做线性核对；轴标签与单位、图例与系列、误差线含义、显著性、样本量逐条校验；交付可编辑源（绘图脚本 + 数据副本 + 文字可编辑的 SVG）、真实 PNG/PDF、图元→源数据映射和源级修改记录。

不负责：统计方法选择与显著性计算是否成立、实验设计、示意图/机制图。

## 文件
| 路径 | 作用 |
|---|---|
| `SKILL.md` | 智能体执行说明：≤ 30 次调用的 9 步流程、make_chart.py 模板（gid、STYLE、CJK 字体选择、期望值文件、导出记录）、7 条标注规则、result.json 规则、异常处理 |
| `scripts/chartkit.py` | 标准库：`table` 读 csv/xlsx（xlsx 不依赖 openpyxl，打印 Sheet!行号并存 csv）；`marks` 从 SVG 按 id 回读柱长/点位置，分别线性拟合，残差 > 2 % 判 FAIL；`svgchart` matplotlib 缺失时的柱/线/散点 SVG 回退；`diff` 元素级改动（过滤 matplotlib 哈希 id 噪声） |
| `scripts/export_check.py` | 标准库：`tools` 探测 matplotlib、渲染器、中文字体；`render` SVG → PNG/PDF（回退路径用）；`check` 核对 result.json 与全部交付物 |
| `resources/checklist.md` | 交付前人工核对清单 |
| `examples/README.md` | 最小调用示例（示例，合成数据） |
| `benchmark/EVALUATION.md` | 设计理由、规则与失败形态对照、内部合成测试记录（无正式分数） |

## 依赖
- Python 3.8+ 标准库；matplotlib（推荐，≥ 3.4）存在时走模板，缺失时走 `svgchart` + `render`。
- 渲染器自动探测（rsvg-convert、cairosvg、inkscape、Chrome、ImageMagick、LibreOffice）。中文需要已安装的 CJK 字体（模板会自动选用并打印）。

## 调用方式
```bash
export S=/skills/weekly-skill            # 本地测试时另设 CASE_JSON / WORK_DIR / OUT_DIR
python3 $S/scripts/export_check.py tools
python3 $S/scripts/chartkit.py table /input/materials/data.xlsx --out /app/work
timeout 120 python3 /app/output/make_chart.py                   # -> chart.svg/.pdf/.png + chart_marks_expected.csv
python3 $S/scripts/chartkit.py marks /app/output/chart.svg /app/output/chart_marks_expected.csv
timeout 120 python3 /app/output/make_chart.py chart_v2          # 修改 STYLE/数据后输出新版本
python3 $S/scripts/chartkit.py diff /app/output/chart.svg /app/output/chart_v2.svg
python3 $S/scripts/export_check.py check
```

## 输出（/app/output）
`make_chart.py`、`chart_data.csv`、`chart.svg`（文字可编辑）、`chart.pdf`（Type 42 字体）、`chart.png`、`chart_marks_expected.csv`、`chart_source_map.md`、`chart_caption.md`、`export_log.jsonl`、`chart_v2.*` 与 diff、`result.json`（含 data_trace、mark_check、annotation_check、export_checks、change_log）。

## 方法要点
1. 数值只从数据文件读（带 Sheet!行号），派生量用 python 复算并标注。
2. 每个图元设 gid → SVG id；期望值由数据计算写入 csv；`marks` 回读 SVG 几何做线性拟合（柱长与点位置分开拟合，支持对数轴），把“看起来对”变成可复核的数字。
3. 样式集中在 STYLE 字典，改样式、改标签、换数据都是重跑脚本，不在位图上修。
4. 标注规则：单位与量级、图例与系列、误差含义、显著性来源、n 的统计单位、实体命名、期刊尺寸。

## 限制
- `marks` 支持柱、点、折线顶点；箱线图、热图需在脚本里另行回读并写结论。
- 不评价统计方法是否恰当，只保证图上的统计标注都有出处。
- matplotlib 与 svgchart 的外观不同；svgchart 只覆盖柱/线/散点。

## 维护
版本 lite-1.0（2026-11）。改动脚本后用 examples/README.md 的示例重跑 table → make_chart → marks → check。
