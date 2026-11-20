# graphical-abstract-lite：Graphical Abstract 图形摘要（精简版）

## 用途
把研究描述、方法记录和源数据压缩成一张**单页、可核对**的图形摘要：研究问题 → 方法 → 核心结果 → 结论四个面板按阅读顺序排列；科学实体与因果/空间关系按材料摆放；核心结果用数据文件里的真实数值画成柱（含误差与单位）；图例、单位、比例尺、限定条件齐全。交付可编辑的 JSON 规格与分层 SVG、真实渲染的 PNG/PDF、面板—要点映射、来源映射、数据回读核对和源文件级修改记录。

不负责：论文正文写作、统计分析、实验设计、纯装饰插画。

## 文件
| 路径 | 作用 |
|---|---|
| `SKILL.md` | 智能体执行说明：≤ 30 次调用的 9 步流程、面板—要点映射、版式与编码规则、spec 示例、result.json 规则、异常处理 |
| `scripts/svgfig.py` | 标准库：`build` 规格 → 分层 SVG（id、data-src、语义箭头、自动换行、`bars` 数据小图带 data-value、图例、`width_mm` 物理尺寸、溢出/穿节点/via 点告警、元素来源表）；`edit` 按 id 改文字/属性；`diff` 元素级改动 |
| `scripts/export_check.py` | 标准库：`tools` 探测渲染器与中文字体；`render` SVG → PNG/PDF（rsvg-convert → cairosvg → inkscape → Chrome → ImageMagick → LibreOffice，PDF 最后才退到栅格并标明），写 export_log.jsonl；`check` 核对 result.json 与全部交付物 |
| `resources/checklist.md` | 交付前人工核对清单（四要素、实体关系、数据编码、图例版式、导出与可编辑性） |
| `examples/README.md` | 最小调用示例（示例，合成数据） |
| `benchmark/EVALUATION.md` | 设计理由、规则与失败形态对照、内部合成测试记录（无正式分数） |

## 依赖
- Python 3.8+ 标准库即可；渲染器自动探测，全部缺失时保留 SVG 并如实记录。`pdffonts` 可选（检查字体嵌入）。
- 字体栈：Arial/Helvetica + Noto Sans CJK SC / Source Han Sans SC / WenQuanYi Micro Hei / PingFang SC / Microsoft YaHei。

## 调用方式
```bash
export S=/skills/weekly-skill            # 本地测试时另设 CASE_JSON / WORK_DIR / OUT_DIR
python3 $S/scripts/export_check.py tools
python3 $S/scripts/svgfig.py build /app/output/figure_spec.json /app/output/figure.svg
python3 -c "import xml.etree.ElementTree as E;[print(e.get('id'),e.get('data-value'),e.get('height')) for e in E.parse('/app/output/figure.svg').iter() if e.get('data-value')]"
timeout 300 python3 $S/scripts/export_check.py render /app/output/figure.svg --dpi 300
python3 $S/scripts/svgfig.py build /app/output/figure_spec_v2.json /app/output/figure_v2.svg
python3 $S/scripts/svgfig.py diff /app/output/figure.svg /app/output/figure_v2.svg
python3 $S/scripts/export_check.py check
```

## 输出（/app/output）
`figure_spec.json`、`figure.svg`（layer-panels / edges / nodes / data / text / legend）、`figure.png`、`figure.pdf`、`figure_elements.tsv`、`figure_source_map.md`、`figure_caption.md`、`export_log.jsonl`、修改后的 `figure_v2.*` 与 diff、`result.json`（含 panel_map、data_mapping、export_checks、change_log）。

## 方法要点
1. **面板—要点映射**先于画图：每个要点注明上图形式与来源，次要信息明确“只进图注”。
2. **数据驱动**：用 python 从数据文件生成 `bars` 项，柱高由脚本按数值计算，SVG 保留 `data-value`，渲染前回读比对。
3. **语义固定**：流程、促进、抑制、转移、推测等边类型的线型和端点由脚本统一生成，图例随之生成。
4. **版式约束**：四面板阅读顺序、字号下限、色盲友好配色；溢出、穿越、via 点落在节点内都会告警。
5. **源级修改**：改 spec 重建或按 id 编辑 SVG，diff 证明只改了预期元素，新旧版本都渲染。

## 限制
- 坐标由智能体给出，脚本不自动排版，只告警。
- `bars` 只适合非负数值；负值/对数数据改用文字数值或交给数据图表工具。
- 不判断研究结论本身是否成立，只保证图与材料一致、强度不过度。

## 维护
版本 lite-1.0（2026-11）。改动脚本后用 examples/README.md 的示例重跑 build → render → check。
