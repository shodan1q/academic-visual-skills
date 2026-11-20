# sci-schematic-editable-lite：科研示意图生成与编辑（精简版）

## 用途
把研究描述、实验流程、结构说明和数据表画成（或改成）能直接进论文、答辩稿和基金本子的示意图：实验流程图、结构/层级关系图、概念或机制链条图。重点是**结构正确**：包含、并列、上下游、时序、因果各有固定画法；图例与数据表的分类一一对应并可随数据重绘；交付可编辑的 JSON 规格与分层 SVG、真实渲染的 PNG/PDF、期刊尺寸与字号检查、来源映射和源文件级修改记录。

不负责：统计图表的数值计算与统计方法、海报封面等版式美化、艺术插画、正文写作。

## 文件
| 路径 | 作用 |
|---|---|
| `SKILL.md` | 智能体执行说明：≤ 30 次调用的 9 步流程、关系语法表、图例与期刊尺寸规则、spec 示例、result.json 规则、异常处理 |
| `scripts/svgfig.py` | 标准库：`build` 规格 → 分层 SVG（id、data-src、10 种语义边、自动换行、图例、`width_mm` 物理尺寸、溢出/穿节点/via 点告警、元素来源表）；`edit` 按 id 改文字/属性；`diff` 元素级改动 |
| `scripts/export_check.py` | 标准库：`tools` 探测渲染器与中文字体；`render` SVG → PNG/PDF（6 种渲染器依次尝试，PDF 字体嵌入检查），写 export_log.jsonl；`check` 核对 result.json 与全部交付物 |
| `resources/checklist.md` | 交付前人工核对清单 |
| `examples/README.md` | 最小调用示例（示例，合成数据） |
| `benchmark/EVALUATION.md` | 设计理由、规则与失败形态对照、内部合成测试记录（无正式分数） |

## 依赖
- Python 3.8+ 标准库；渲染器（rsvg-convert、cairosvg、inkscape、Chrome、ImageMagick、LibreOffice）自动探测，全部缺失时保留 SVG 并如实记录。`pdffonts`、`magick`（TIFF）可选。
- 字体栈：Arial/Helvetica + Noto Sans CJK SC / Source Han Sans SC / WenQuanYi Micro Hei / PingFang SC / Microsoft YaHei。

## 调用方式
```bash
export S=/skills/weekly-skill            # 本地测试时另设 CASE_JSON / WORK_DIR / OUT_DIR
python3 $S/scripts/export_check.py tools
python3 $S/scripts/svgfig.py build /app/output/figure_spec.json /app/output/figure.svg
timeout 300 python3 $S/scripts/export_check.py render /app/output/figure.svg --dpi 600
python3 $S/scripts/svgfig.py edit /app/output/figure.svg /app/output/figure_v2.svg <id> --text "新标签"
python3 $S/scripts/svgfig.py diff /app/output/figure.svg /app/output/figure_v2.svg
python3 $S/scripts/export_check.py check
```

## 输出（/app/output）
`figure_spec.json`、`figure.svg`（分层）、`figure.png`、`figure.pdf`、`figure_elements.tsv`、`figure_source_map.md`、`figure_caption.md`、`export_log.jsonl`、修改后的 `figure_v2.*` 与 diff、`result.json`（含 entities、relations、data_mapping、export_checks、change_log）。

## 方法要点
1. 先抽实体—关系清单（类型、属性、分组、来源、关系类型及依据），图是清单的渲染。
2. 关系语法固定：包含 = 嵌套 panel，并列 = 网格对齐同级，上下游/时序 = 单向 step 箭头 + 序号，因果 = activate/inhibit，推测 = indirect。
3. 分类着色由 python 从数据表生成 nodes 与 legend，数据改了重跑即可，图例不会和数据脱节。
4. 期刊尺寸：`width_mm` 写入物理宽度；有效字号 = 字号px × (D×3.78/W) × 0.75，单栏建议画布宽 340–420 px。
5. 修改在源上做，diff 证明其余元素不变（tspan 换行变化也能检出）。

## 限制
- 坐标由智能体给出，脚本只告警，不自动排版。
- CMYK、EPS 依赖环境里的 inkscape/ghostscript，缺失时只能记为缺口。
- 文字宽度为估算，以渲染结果为准。

## 维护
版本 lite-1.0（2026-11）。改动脚本后用 examples/README.md 的示例重跑 build → render → check。
