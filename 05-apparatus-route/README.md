# apparatus-route-figure-lite：实验装置与技术路线图（精简版）

## 用途
把装置清单、装配说明、方法段落、工艺描述或研究计划画成别人能看懂、能核对的实验装置图、步骤流程图或技术路线图。先抽出“部件—接口—连接—步骤—流向—阶段”结构化清单，再按固定规则布图：部件名称与数量照抄、连接只画材料写了的、介质流向用固定颜色线型、步骤编号与正文一致、并行/循环/终止条件可见、阶段与里程碑的依赖清楚。交付可编辑的 JSON 规格与分层 SVG、真实渲染的 PNG/PDF、来源映射和源文件级修改记录。

不负责：数据分析与数值拟合、判断实验方案是否合理、论文排版与投稿格式适配。

## 文件
| 路径 | 作用 |
|---|---|
| `SKILL.md` | 智能体执行说明：≤ 30 次调用的 9 步流程、结构化清单格式、装置/流程/路线三类画图规则、spec 示例、result.json 规则、异常处理 |
| `scripts/svgfig.py` | 标准库：`build` 规格 → 分层 SVG（id、data-src、flow/signal/step 等语义边、直角走线 elbow/via、自动换行、图例、`width_mm`、溢出/穿部件/via 点告警、元素来源表）；`edit` 按 id 改文字/属性；`diff` 元素级改动 |
| `scripts/export_check.py` | 标准库：`tools` 探测渲染器与中文字体；`render` SVG → PNG/PDF（6 种渲染器依次尝试，PDF 字体嵌入检查），写 export_log.jsonl；`check` 核对 result.json 与全部交付物 |
| `resources/checklist.md` | 交付前人工核对清单 |
| `examples/README.md` | 最小调用示例（示例，合成数据） |
| `benchmark/EVALUATION.md` | 设计理由、规则与失败形态对照、内部合成测试记录（无正式分数） |

## 依赖
- Python 3.8+ 标准库；渲染器自动探测（rsvg-convert、cairosvg、inkscape、Chrome、ImageMagick、LibreOffice），全部缺失时保留 SVG 并如实记录。`pdffonts` 可选。
- 字体栈：Arial/Helvetica + Noto Sans CJK SC / Source Han Sans SC / WenQuanYi Micro Hei / PingFang SC / Microsoft YaHei。

## 调用方式
```bash
export S=/skills/weekly-skill            # 本地测试时另设 CASE_JSON / WORK_DIR / OUT_DIR
python3 $S/scripts/export_check.py tools
python3 $S/scripts/svgfig.py build /app/output/figure_spec.json /app/output/figure.svg
timeout 300 python3 $S/scripts/export_check.py render /app/output/figure.svg --dpi 300
python3 $S/scripts/svgfig.py edit /app/output/figure.svg /app/output/figure_v2.svg e-feed2 --set stroke-width=4
python3 $S/scripts/svgfig.py diff /app/output/figure.svg /app/output/figure_v2.svg
python3 $S/scripts/export_check.py check
```

## 输出（/app/output）
`figure_spec.json`、`figure.svg`（分层）、`figure.png`、`figure.pdf`、`figure_elements.tsv`、`figure_source_map.md`、`figure_caption.md`（含编号—正文对照）、`export_log.jsonl`、修改后的 `figure_v2.*` 与 diff、`result.json`（含 components、connections、steps/stages、data_mapping、export_checks、change_log）。需要装置图 + 路线图时各一套。

## 方法要点
1. 结构化中间表示（部件、连接、步骤、阶段四张表）先于画图；每行带来源与原文短引。
2. 不补连接：材料没写的接口/管路不画，进 material_gaps 并在图上或图注说明。
3. 介质 → 颜色/线型固定，图例自动生成；管路用直角走线，穿过部件或 via 点落在部件内都会告警。
4. 步骤编号照抄正文，并行 3a/3b、循环回边、判断菱形；技术路线按阶段列布局，依赖用箭头。
5. 修改在源上做，diff 证明其余元素不变。

## 限制
- 部件用通用形状（圆角框、圆、菱形）表示，不提供逼真的仪器图标。
- 坐标由智能体给出，脚本只告警，不自动排版。
- 不判断方案是否合理，只保证图与材料一致、缺口可见。

## 维护
版本 lite-1.0（2026-11）。改动脚本后用 examples/README.md 的示例重跑 build → render → check。
