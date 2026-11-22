# sci-schematic-editable-lite：科研关系示意图（精简版）

## 用途
把原始论文、figure 工单（如 `editable_relationship_schematic`）和数据表，变成一张**结构可逐条核对**的科研示意图——包含/层级图、谱系/上下游图、实验流程图、因果机制链条——并能在源文件上按要求修改：

- **包含是嵌套，不是箭头**：分组框写 `parent`，节点写 `comp`；脚本检查子组不出界、兄弟组不交叠、节点完全落在所属组内且没画进别的组，并把每条包含关系写进 content_map（`type: contains`）。
- **方向与顺序可查**：流程 step 以序号开头，箭头与序号相反会报警；连线相互交叉、穿过节点、穿过图例、标签被遮都会报警。
- **关系语义固定**：step / flow（物料、谱系）/ signal（分泌因子）/ activate / inhibit / bind / line 各有固定线型与端点；证据强度（direct / indirect / hypothesis）是独立的线型维度，“未检验”的关系不会画成实线。边可以指向整个分组（“TA 细胞 → 分泌谱系”）。
- **图例 = 数据表**：`canvas.categories` 直接读 CSV，每个类别一色、图例按表逐类列出（类别数=色块数），表中数值（如 n cells）原样追加到标签；改一个类别颜色，全图与图例同步。pixcheck 再在渲染像素上核对每个节点颜色都有同色图例色块。
- 交付分层 SVG + JSON 规格 + 真实 PNG/PDF + 像素自检 + 内容映射 + 工单逐条对照（element_ids 由 check 核实存在）+ 源文件级修改 diff。

不负责：统计分析与统计图数值计算、海报封面美化、艺术插画、正文写作。

## 文件
| 路径 | 作用 |
|---|---|
| `SKILL.md` | 运行时说明：8 步流程（目标 20–30 次调用）、关系语法、图例与数据映射、spec 示例、result.json 组装模板、异常处理 |
| `scripts/svgfig.py` | `build` spec → 分层 SVG + `*_content_map.json`，并告警：缺来源/类型、组未命名、子组出界、兄弟组交叠、节点不在/不完全在所属组、step 与序号反向、边重叠/交叉/穿节点/穿图例、边标签被遮、标签溢出、图例缺项/多项、颜色无图例、类别颜色重复；`edit` 按 id 改源；`diff` 元素级改动 |
| `scripts/export_check.py` | `tools` 探测渲染器与中文字体；`render` SVG → PNG/PDF（rsvg-convert → cairosvg → inkscape → chrome → magick → soffice）并写 export_log.jsonl；`check` 核对 result.json（contract 字段、status 一个词、骨架“生成中”/模板槽残留、对照表里的 element_ids 是否真实存在、预览是否真实） |
| `scripts/pixcheck.py` | 纯标准库解码渲染后的 PNG：图不空、不裁切；节点填色按声明渲染、标签有可见墨迹与足够对比度（WCAG 亮度）；节点颜色在图例里有同色色块；图例色块灰度可分；每种边样式有图例线 |
| `resources/checklist.md` | 脚本查不到、需要对照原文人工确认的项 |
| `examples/README.md` | 最小调用示例（示例，合成数据） |
| `benchmark/EVALUATION.md` | 设计理由、内部合成案例上旧版与本版的对照记录（仅内部合成案例，不含正式评测结果） |

## 依赖
- Python 3.8+ 标准库即可。渲染器自动探测并按序回退；PDF 字体检查用 `pdffonts`（可选）；PDF 文本用 `pdftotext`（无则 fitz/pypdf）。
- 字体栈：Arial/Helvetica + Noto Sans CJK SC / Source Han Sans SC / WenQuanYi Micro Hei / PingFang SC / Microsoft YaHei。
- 都没有渲染器时保留 SVG、如实记录失败，不伪造预览。

## 调用方式
```bash
export S=/skills/weekly-skill            # 本地测试时另设 CASE_JSON / WORK_DIR / OUT_DIR
python3 $S/scripts/export_check.py tools
python3 $S/scripts/svgfig.py build /app/output/figure_spec.json /app/output/figure.svg
timeout 300 python3 $S/scripts/export_check.py render /app/output/figure.svg --dpi 600
python3 $S/scripts/pixcheck.py /app/output/figure.svg
python3 $S/scripts/svgfig.py build /app/output/figure_spec_v2.json /app/output/figure_v2.svg   # 修改后的版本
python3 $S/scripts/svgfig.py diff /app/output/figure.svg /app/output/figure_v2.svg > /app/output/edit_diff.json
python3 $S/scripts/export_check.py check
```

## 输出（/app/output）
`figure_spec.json`、`figure.svg`（layer-panels/edges/nodes/data/text/legend，每个元素有 id 与 data-src）、`figure.png`、`figure.pdf`、`figure_content_map.json`（实体、关系含 contains、分组、图例、数据编码含 CSV sha256）、`figure_pixel_check.json`、`export_log.jsonl`、`figure_spec_v2.json` + `figure_v2.*`、`edit_diff.json`、`result.json`（case_id、status、editable_source、export_artifact、content_map、compliance_checks、exceptions、change_log 及其他 contract 字段）。

## 方法要点
1. 图是“实体—关系表”的渲染：spec 里每个节点有 kind/comp/src，每条边有 type/evidence/src；content_map 由 spec 直接生成，不靠模型手抄。
2. 包含、并列、顺序、因果四种结构各有唯一画法，并且都有对应的机器检查（嵌套几何、同组、序号方向、端点类型）。
3. 结构归属用嵌套，类别归属用颜色：同一细胞既“位于隐窝”又“属于分泌谱系”时两种信息不打架。
4. 颜色与图例从同一张 CSV 生成，修改时改类别颜色而不是逐个节点改，diff 证明其余元素不变。

## 限制
- 布局坐标由智能体给出，脚本只做检查，不自动排版。
- 文字宽度按字符估算；pixcheck 对大图通过约 1200 px 的同源重渲染来检查。
- 不判断科学结论是否成立，只保证与材料一致、证据强度可见；纯文本模型读不到 PDF 原图像素，只依据图注、正文与数据表并如实说明。
- CMYK、EPS、TIFF 依赖环境里的 inkscape/ImageMagick，缺失时记为缺口。

## 维护
版本 lite-1.1（2026-11）。改脚本后用 examples/README.md 的示例重跑 build → render → pixcheck → check。
