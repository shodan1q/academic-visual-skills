# bio-pathway-figure-lite：生物机制图与通路图（精简版）

## 用途
把机制描述、实验记录、实体表和数据表画成一张**可逐条质疑**的机制图/通路图：每个实体、每条边都能回到材料的文件与行；激活、抑制、结合、修饰、转运、间接/推测用不同的线型和端点区分；区室（胞外、膜、胞质、核）决定布局；图例与颜色编码和数据表一致。交付可编辑的分层 SVG（及生成它的 JSON 规格）、真实渲染的 PNG/PDF、来源映射和源文件级修改记录。

不负责：统计分析、实验设计、论文写作、艺术插画。

## 文件
| 路径 | 作用 |
|---|---|
| `SKILL.md` | 智能体执行说明（≤ 30 次调用的 9 步流程、机制图规则、spec 示例、result.json 规则、异常处理） |
| `scripts/svgfig.py` | 标准库：`build` JSON 规格 → 分层 SVG（id、data-src、语义箭头、自动换行、图例、`width_mm` 物理尺寸、溢出/穿节点/via 点告警、元素来源表）；`edit` 按 id 改文字/属性，其余字节不动；`diff` 输出元素级改动 |
| `scripts/export_check.py` | 标准库：`tools` 探测渲染器与中文字体；`render` SVG → PNG/PDF（rsvg-convert → cairosvg → inkscape → chrome → magick → soffice，PDF 最后才退到栅格并标明），写 export_log.jsonl；`check` 核对 result.json 与全部交付物 |
| `resources/checklist.md` | 交付前人工核对清单 |
| `examples/README.md` | 最小调用示例（示例，合成数据） |
| `benchmark/EVALUATION.md` | 设计理由与内部合成测试记录（无正式分数） |

## 依赖
- 只需要 Python 3.8+ 标准库。渲染器按顺序自动探测：`rsvg-convert`、Python `cairosvg`、`inkscape`、Chromium/Chrome、ImageMagick、LibreOffice。PDF 字体检查用 `pdffonts`（可选）。都没有时保留 SVG、如实记录失败。
- 字体：SVG 字体栈为 Arial/Helvetica + Noto Sans CJK SC / Source Han Sans SC / WenQuanYi Micro Hei / PingFang SC / Microsoft YaHei；`tools` 会列出本机可用的中文字体。

## 调用方式
```bash
export S=/skills/weekly-skill            # 本地测试时另设 CASE_JSON / WORK_DIR / OUT_DIR
python3 $S/scripts/export_check.py tools
python3 $S/scripts/svgfig.py build /app/output/figure_spec.json /app/output/figure.svg
timeout 300 python3 $S/scripts/export_check.py render /app/output/figure.svg --dpi 300
python3 $S/scripts/svgfig.py edit /app/output/figure.svg /app/output/figure_v2.svg n-bcat-label --text "β-catenin (CTNNB1)"
python3 $S/scripts/svgfig.py diff /app/output/figure.svg /app/output/figure_v2.svg
python3 $S/scripts/export_check.py check
```

## 输出（/app/output）
`figure_spec.json`（可编辑规格）、`figure.svg`（分层源）、`figure.png`、`figure.pdf`、`figure_elements.tsv`（元素→来源底稿）、`figure_source_map.md`、`figure_caption.md`、`export_log.jsonl`、修改后的 `figure_v2.*` 与 diff、`result.json`。

## 方法要点
1. 先建实体—关系表（实体类型、区室、关系语义、方向依据、证据强度、来源），再画图；图只是这张表的渲染。
2. 关系语义映射为固定图形语法（见 SKILL.md 表格），颜色和端点由脚本统一生成，模型不手画箭头。
3. 区室用 panel 分层，跨膜蛋白放在膜条上；边由节点边界裁剪，穿过第三个节点时告警。
4. 图例项与实际使用的边类型、填充色一一对应；缺图例告警。
5. 修改在源上做（改 spec 重建或按 id 编辑 SVG），用 diff 证明其余元素未变，新旧版本都渲染。

## 限制
- 布局坐标由智能体给出，脚本只检查溢出、穿越与重叠，不自动排版。
- 文字宽度按字符估算，极端字体下可能有少量偏差；以渲染出的 PNG 为准。
- 不判断机制本身是否成立，只保证图与材料一致并标注证据强度。

## 维护
版本 lite-1.0（2026-11）。修改脚本后用 examples/README.md 的示例重跑 build → render → check。
