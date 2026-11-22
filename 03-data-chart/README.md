# source-data-chart-lite：科研数据图表生成与编辑（精简版 1.1）

## 用途
按图表工单（如 `artifacts/figure-workorder.json`，类型 source_value_chart）和原始论文 / 源数据，生成或修改能直接投稿的数据图（分组柱 + 个体点、折线、散点），并保证“画得像也画得准”：
- 均值、SD/SEM/CI、n 由模板从数据行复算，每个图元带 CSV 行号与样本 id；空值自动排除并写进图注。
- 轴标签、单位、误差含义、显著性、n 的统计单位只取自原文图注 / 方法段，配置里每项带出处。
- 从生成的 SVG 用 y 轴刻度标定后回读柱长、误差线全长、点位置，与数据对账；再解码渲染出的 PNG，查尺寸、柱色、图例色、色盲 / 灰度可分、最小字号（运行时模型看不见图片）。
- 交付可编辑源（`make_chart.py` + `chart_config.json` + `chart_data.csv` + 文字可编辑 SVG）、真实 PNG/PDF、`chart_content_map.json`、工单逐条对照、源文件级修改（override JSON + SVG 差异）和分类异常。

不负责：统计方法选择与显著性计算是否成立、实验设计、示意图/机制图。

## 文件
| 路径 | 作用 |
|---|---|
| `SKILL.md` | 运行时说明：约 10 次调用的 8 步流程、配置示例、result.json 组装模板、7 条标注规则、异常处理 |
| `resources/make_chart_template.py` | matplotlib 绘图源模板：只改 JSON 配置；分组柱/折线/散点、误差线、个体点、显著性括线、图例、gid；输出 svg/pdf/png、期望值 csv、content map、图注、导出日志；支持 override JSON 做源级修改；同配置重跑 SVG 字节一致 |
| `scripts/chartkit.py` | `table` 读 csv/xlsx（无 openpyxl 也行，带行号）；`marks` 刻度标定的图元回读对账；`diff` 元素级修改差异；`svgchart` 无 matplotlib 时的回退 |
| `scripts/pixcheck.py` | 解码 PNG（标准库）：宽度 = mm × dpi、空白/裁切、柱色 = 声明色、系列色出现且无多余颜色、protan/deutan/tritan 模拟与灰度、最小字号、content map 告警 |
| `scripts/export_check.py` | `tools` 探测；`render` SVG → PNG/PDF 回退链；`check` 核对 result.json、contract、预览、对账与像素检查结果、异常分类 |
| `resources/checklist.md` | 交付前核对清单 |
| `examples/README.md` | 最小调用示例（示例，合成数据） |
| `benchmark/EVALUATION.md` | 设计理由、旧版问题、改后实测、每条机制拦住什么（内部合成案例，无正式评测结果） |

## 依赖
- Python 3.8+ 标准库；matplotlib ≥ 3.4（推荐，模板用）；缺失时 `svgchart` + 任一渲染器（rsvg-convert、cairosvg、inkscape、Chrome、ImageMagick、LibreOffice）。
- PDF 文本：pdftotext，或 PyMuPDF（fitz）/ pypdf。
- 字体：模板优先用配置里的字体（默认 Arial → Liberation Sans → Helvetica → DejaVu Sans），中文自动加已安装的 CJK 字体；实际所用字体写进 export_log 与 content map。

## 调用方式
```bash
export S=/skills/weekly-skill            # 本地测试时另设 CASE_JSON / WORK_DIR / OUT_DIR
cp $S/resources/make_chart_template.py /app/output/make_chart.py
cp /input/data/source.csv /app/output/chart_data.csv           # 再写 /app/output/chart_config.json
cd /app/output && timeout 120 python3 make_chart.py
python3 $S/scripts/chartkit.py marks chart.svg chart_marks_expected.csv
python3 $S/scripts/pixcheck.py chart.svg --workorder /input/artifacts/figure-workorder.json
timeout 120 python3 make_chart.py chart_v2 edit_v2.json && python3 $S/scripts/chartkit.py diff chart.svg chart_v2.svg > edit_diff.json
python3 $S/scripts/export_check.py check
```

## 输出（/app/output）
`make_chart.py`、`chart_config.json`、`chart_data.csv`、`chart.svg/.pdf/.png`、`chart_marks_expected.csv`、`chart_mark_check.json`、`chart_pixel_check.json`、`chart_content_map.json`、`chart_caption.md`、`export_log.jsonl`、`edit_v2.json` + `chart_v2.*` + `edit_diff.json`、`result.json`（case_id、status、editable_source、export_artifact、content_map、compliance_checks、exceptions、change_log、versions、artifacts）。

## 限制
- 模板覆盖柱、折线、散点；箱线、热图、多面板需照模板写法自行绘制，marks 不适用部分写进 compliance_checks。
- 不评价统计方法，只保证图上统计标注都有出处；图注未写误差类型时记 undecidable。
- pixcheck 不识别缺字方框，缺字依靠 matplotlib 的告警（模板记录，pixcheck 判 FAIL）。

## 维护
版本 1.1（2026-11）：加入工单与 contract 字段、绘图模板、刻度标定对账、误差线对账、像素检查、子树级 diff、骨架/嵌套 JSON 检查修正。改动后按 `benchmark/EVALUATION.md` 第 4 节重跑。
