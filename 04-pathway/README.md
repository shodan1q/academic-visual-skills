# bio-pathway-figure-lite：生物机制图与通路图（精简版）

## 用途
把原始论文、figure 工单和数据表变成一张**可逐条质疑**的机制图/通路图，并能在源文件上按要求修改：

- 每个实体带类型（基因/mRNA/蛋白/复合物/家族/小分子…）、所在区室和来源行；基因自动斜体，蛋白正体。
- 每条关系带作用类型（激活、抑制、结合、修饰、转运、无向关联）和**独立的证据强度**（直接/间接/假设），所以“间接抑制”“未检验是否直接的激活”都能如实画出。
- 区室（胞外、质膜、胞质、ER、Golgi、核…）是带标题的分层面板，膜是窄带；脚本检查节点是否落在声明的区室里。
- 节点颜色由脚本直接读 CSV 计算，图例（边类型、证据线型、颜色分档、“无数据”）自动生成，和图面同源。
- 交付分层 SVG + JSON 规格 + 真实 PNG/PDF + 像素级自检报告 + 内容映射 + 工单逐条对照 + 源文件级修改 diff。

不负责：统计分析、实验设计、论文写作、艺术插画。

## 文件
| 路径 | 作用 |
|---|---|
| `SKILL.md` | 运行时说明：8 步流程（目标 20–30 次调用）、机制规则、spec 示例、result.json 组装模板、异常处理 |
| `scripts/svgfig.py` | `build` spec → 分层 SVG + `*_content_map.json`，并告警：缺来源/类型、区室未命名、节点不在所属区室、基因/蛋白字体、transport 连了不同实体、两条边重叠、穿节点、穿图例、边标签被遮、标签溢出、图例缺项/多项、颜色无图例；`edit` 按 id 改源；`diff` 元素级改动 |
| `scripts/export_check.py` | `tools` 探测渲染器与中文字体；`render` SVG → PNG/PDF（rsvg-convert → cairosvg → inkscape → chrome → magick → soffice）并写 export_log.jsonl；`check` 核对 result.json（contract 字段、status 一个词、骨架/模板残留、工单对照里的 element_ids 是否真实存在、预览是否真实） |
| `scripts/pixcheck.py` | 解码渲染后的 PNG（纯标准库）：图不空、不裁切；每个节点填色按声明渲染、标签有可见墨迹与足够对比度；每种节点颜色在图例里有同色色块；图例色块灰度可分；每种边样式有图例线 |
| `resources/checklist.md` | 脚本查不到、需要对照原文人工确认的项 |
| `examples/README.md` | 最小调用示例（示例，合成数据） |
| `benchmark/EVALUATION.md` | 设计理由、内部合成案例上不加载与加载 Skill 的对照记录（仅内部合成案例） |

## 依赖
- Python 3.8+ 标准库即可。渲染器自动探测并按序回退；PDF 字体检查用 `pdffonts`（可选）；PDF 文本用 `pdftotext`（无则 fitz/pypdf）。
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
`figure_spec.json`、`figure.svg`（layer-panels/edges/nodes/data/text/legend，每个元素有 id 与 data-src）、`figure.png`、`figure.pdf`、`figure_content_map.json`（实体/关系/区室/图例/数据编码，含 CSV sha256）、`figure_pixel_check.json`、`export_log.jsonl`、`figure_spec_v2.json` + `figure_v2.*`、`edit_diff.json`、`result.json`（case_id、status、editable_source、export_artifact、content_map、compliance_checks、exceptions 及其他 contract 字段）。

## 方法要点
1. 图是“实体—关系表”的渲染：spec 里每个节点有 kind/comp/src，每条边有 type/evidence/src；content_map 直接由 spec 生成，不靠模型手抄。
2. 作用类型与证据强度是两个独立维度（端点/颜色 vs 线型），避免“间接”吞掉“抑制”。
3. transport 只表示同一实体换区室；转录、表达用 activate。这条规则由 build 自动检查。
4. 数据颜色从 CSV 读、自动分档、自动进图例；图例与图面再由 pixcheck 在像素层面比对。
5. 修改在源上做，图例项 id 按内容命名，新增项排在最后，所以 diff 只显示真实改动。

## 限制
- 布局坐标由智能体给出，脚本只做检查，不自动排版。
- 文字宽度按字符估算；pixcheck 对大图通过约 1200 px 的同源重渲染来检查。
- 不判断机制在生物学上是否成立，只保证与材料一致、证据强度可见。
- 纯文本模型读不到 PDF 里的原图像素，只能依据图注、正文与数据表，并如实说明。

## 维护
版本 lite-1.1（2026-11）。改脚本后用 examples/README.md 的示例重跑 build → render → pixcheck → check。
