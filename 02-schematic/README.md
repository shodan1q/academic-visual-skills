# sci-schematic-editable-lite：科研关系示意图（精简版）

## 用途
把原始论文、figure 工单（如 `editable_relationship_schematic`）和数据表，变成一张**结构可逐条核对、排版不靠手填坐标**的科研示意图——包含/层级图、信号通路与分区、谱系/上下游图、实验流程图、因果机制链条——并能在源文件上按要求修改：

- **原图标签当金标准**：`export_check.py figtext src.txt 3` 打印 Figure 3 的图注、原图里画着的文字标签（矢量 PDF 的文本层）和所有引用行号；实体名照原图写，漏画的要说明。
- **只写结构，脚本排版**：spec 里写“子图 → 分区（parent）→ 节点（comp）”和分区内的 col/row，`svgfig.py build` 自动定尺寸、嵌套、网格对齐、等宽分栏，图例放在图下方分栏，脚注排在最下，画布自动扩展，不会裁切。边穿过别的节点时先自动改 L 形折线，边标签自动避让节点和其他标签。
- **包含是嵌套，不是箭头**：膜、胞质、周质这类分区画成框中框；脚本检查子组不出界、兄弟组不交叠、节点完全落在所属组内，并把每条包含关系写进 content_map（`type: contains`）。
- **关系语义固定**：step / flow / produce（合成、表达）/ phospho（磷酸转移）/ signal / activate / inhibit / bind / line 各有固定线型与端点；证据强度（direct / indirect / hypothesis）是独立的线型维度，“未检验”的关系不会画成实线；图例文字可按边改写成材料里的说法。
- **图例 = 数据表**：`canvas.categories` 直接读 CSV，每个类别一色、图例按表逐类列出（类别数 = 色块数）；改一个类别颜色，全图与图例同步。pixcheck 在渲染像素上核对每个节点颜色都有同色图例色块。
- **期刊字号自动达标**：写 `canvas.width_mm` 与 `min_font_pt`，build 反复放大全部文字直到最小字号 ≥ 要求，并报告画布 px、mm、最小字号 pt 与放大倍数（写入 content_map 的 `export_geometry`）。
- **修改留痕**：改 spec 另存 v2 重建，`svgfig.py diff` 把“内容改动”（文字、颜色，按 id 列出）和“自动重排的坐标变化”分开统计；换行不算内容改动。
- 交付分层 SVG + JSON 规格 + 真实 PNG/PDF + 像素自检 + 内容映射 + 工单逐条对照（element_ids 由 check 核实存在）+ 源文件级修改 diff。

不负责：统计分析与统计图数值计算、海报封面美化、艺术插画、正文写作。

## 文件
| 路径 | 作用 |
|---|---|
| `SKILL.md` | 运行时说明：9 步流程（目标 ≤ 25 次调用）、关系语法、图例与数据映射、自动排版 spec 示例、result.json 规则、异常处理 |
| `scripts/svgfig.py` | `build` spec → 自动排版的分层 SVG + `*_content_map.json`（实体、关系含 contains、分区、图例、数据编码、导出几何），并告警：缺来源、子组出界、兄弟组交叠、节点不在所属组、step 与序号反向、边重叠/交叉/穿节点/穿图例、边标签被遮、标签溢出、图例缺项/多项、颜色无图例、类别颜色重复；`edit` 按 id 改源；`diff` 元素级改动（内容/布局分开） |
| `scripts/export_check.py` | `tools` 探测渲染器与中文字体；`figtext` 找图注、原图标签与引用行；`render` SVG → PNG/PDF（rsvg-convert → cairosvg → inkscape → chrome → magick → soffice）并写 export_log.jsonl；`check` 核对 result.json（contract 字段、status 一个词、骨架“生成中”/模板槽残留、对照表里的 element_ids 是否真实存在、预览是否真实） |
| `scripts/pixcheck.py` | 纯标准库解码渲染后的 PNG：图不空、不裁切；节点填色按声明渲染、标签有可见墨迹与足够对比度；节点颜色在图例里有同色色块；图例色块灰度可分；每种边样式有图例线。只给提示 |
| `resources/checklist.md` | 脚本查不到、需要对照原文人工确认的项 |
| `examples/README.md` | 最小调用示例（示例，合成数据） |
| `benchmark/EVALUATION.md` | 设计理由与内部合成案例上的前后对照记录（仅内部合成案例，不含正式评测结果） |

## 依赖
- Python 3.8+ 标准库即可。渲染器自动探测并按序回退；PDF 字体检查用 `pdffonts`（可选）；PDF 文本用 `pdftotext`（无则 fitz/pypdf）。
- 字体栈：Arial/Helvetica + Noto Sans CJK SC / Source Han Sans SC / WenQuanYi Micro Hei / PingFang SC / Microsoft YaHei。
- 都没有渲染器时保留 SVG、如实记录失败，不伪造预览。

## 调用方式
```bash
export S=/skills/weekly-skill            # 本地测试时另设 CASE_JSON / WORK_DIR / OUT_DIR
python3 $S/scripts/export_check.py tools
pdftotext -layout /input/source/paper.pdf /app/work/src.txt
python3 $S/scripts/export_check.py figtext /app/work/src.txt 3
python3 $S/scripts/svgfig.py build /app/output/figure_spec.json /app/output/figure.svg
timeout 300 python3 $S/scripts/export_check.py render /app/output/figure.svg --dpi 600
python3 $S/scripts/pixcheck.py /app/output/figure.svg
python3 $S/scripts/svgfig.py build /app/output/figure_spec_v2.json /app/output/figure_v2.svg   # 修改后的版本
python3 $S/scripts/svgfig.py diff /app/output/figure.svg /app/output/figure_v2.svg > /app/output/edit_diff.json
python3 $S/scripts/export_check.py check
```

## 输出（/app/output）
`figure_spec.json`、`figure.svg`（layer-panels/edges/nodes/data/text/legend，每个元素有 id 与 data-src）、`figure.png`、`figure.pdf`、`figure_content_map.json`（实体、关系含 contains、分区、图例、数据编码含 CSV sha256、export_geometry）、`figure_pixel_check.json`、`export_log.jsonl`、`figure_spec_v2.json` + `figure_v2.*`、`edit_diff.json`、`figure_source_map.md`、`figure_caption.md`、`result.json`（case_id、status、editable_source、export_artifact、content_map、compliance_checks、exceptions、change_log 及其他 contract 字段）。

## 方法要点
1. 图是“实体—关系表”的渲染：spec 里每个节点有 kind/comp/src，每条边有 type/evidence/src；content_map 由 spec 直接生成，不靠模型手抄。
2. 模型只做科学判断（谁在哪个分区、什么关系、证据多强），几何由脚本算：自底向上按内容定尺寸，自顶向下分配位置，列等宽以便 a/b 子图逐格对齐。快速模型手填坐标时最常见的失败（为了避开重叠而删掉分区、图例被裁到画布外）因此不再出现。
3. 包含、并列、顺序、因果四种结构各有唯一画法，并且都有对应的机器检查（嵌套几何、同组、序号方向、端点类型）。
4. 颜色与图例从同一张 CSV 生成，修改时改类别颜色而不是逐个节点改，diff 证明内容改动只落在预期 id 上。

## 限制
- 自动排版是网格式的：节点放在分区的行列格里，连线是直线或单折线，不做正交布线；复杂交叉网络需要模型调整 col/row 或加 `via`。
- 文字宽度按字符估算；pixcheck 对大图通过约 1200 px 的同源重渲染来检查。
- `figtext` 只读得到矢量图里的文字；原图是位图时只能依据图注与正文，并如实说明。
- 不判断科学结论是否成立，只保证与材料一致、证据强度可见。
- CMYK、EPS、TIFF 依赖环境里的 inkscape/ImageMagick，缺失时记为缺口。

## 维护
版本 lite-1.3（2026-11）：新增自动排版（结构 spec，无需坐标）、图例分栏与画布自动扩展、最小字号自动达标、`figtext` 原图标签提取、`phospho`/`produce` 边类型与按边图例文字、边自动折线与标签避让、diff 区分内容与布局。保留 1.2 的九步流程、骨架残留检测、只提示不阻断的 pixcheck。旧 spec（显式坐标）照常可用。改脚本后用 examples/README.md 的示例重跑 build → render → pixcheck → check。
