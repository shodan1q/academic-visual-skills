# bio-pathway-figure-lite：生物机制图与通路图（精简版）

## 用途
把原始论文、figure 工单和数据表变成一张**可逐条质疑**的机制图/通路图，并能在源文件上按要求修改：

- 每个实体带类型（基因/mRNA/蛋白/复合物/家族/小分子…）、所在区室和来源行；基因自动斜体，蛋白正体。
- 每条关系带作用类型（激活、抑制、结合、修饰、转运、无向关联）和**独立的证据强度**（直接/间接/假设），所以“间接抑制”“未检验是否直接的激活”都能如实画出。
- **自动布局**：spec 里不写坐标。区室按给定顺序自上而下（细胞器是胞质里的子框），区室内按边的因果顺序分行；反馈边自动识别并从外侧通道返回；被挡住的边走行间/列间空白通道；从下方区室产生的分子（核内基因表达出的反馈蛋白）放在本区室底部；字号按 `width_mm` 自动放大到 `min_font_pt` 以上，图例放右侧或底部取能满足字号的一种。
- 生物学图元：膜画成脂双层带（受体跨在带上），核画双层核膜；基因=直角框+启动子箭头+斜体，蛋白=圆角框，复合物=八角框，家族=叠框，小分子=椭圆；磷酸化/泛素化状态是节点角标（P、Ub）；图例自动列出用到的图元。
- 节点颜色由脚本直接读 CSV 计算，图例（边类型、证据线型、颜色分档、“无数据”）自动生成，和图面同源。
- 交付分层 SVG + JSON 规格 + 真实 PNG/PDF + 像素级自检报告 + 内容映射 + 工单逐条对照 + 源文件级修改 diff。

不负责：统计分析、实验设计、论文写作、艺术插画。

## 文件
| 路径 | 作用 |
|---|---|
| `SKILL.md` | 运行时说明：8 步流程（目标 20–30 次调用）、机制规则、spec 示例、notes.json 格式、异常处理 |
| `scripts/svgfig.py` | `build` spec → 自动布局（或手写坐标）→ 分层 SVG + `*_content_map.json` + `*_resolved_spec.json`（排好的坐标，修改时复制它），报告边交叉数与最小字号 pt，并告警：数据分档色接近“无数据”白色、字号低于工单、边标签压线、缺来源/类型、区室未命名、节点不在所属区室、基因/蛋白字体、transport 连了不同实体、两条边重叠、穿节点、穿图例、边标签被遮、标签溢出、图例缺项/多项、颜色无图例；`edit` 按 id 改源；`diff` 元素级改动 |
| `scripts/export_check.py` | `skeleton` 按任意 contract 写法写骨架；`tools` 探测渲染器与中文字体；`render` SVG → PNG/PDF（rsvg-convert → cairosvg → inkscape → chrome → magick → soffice → 内置 matplotlib 渲染 → 标准库矢量 PDF）并写 export_log.jsonl；`assemble` 从已有文件 + notes.json 按含义填满每个 contract 字段（任何输入缺失都不报错）后自动 check；`check` 核对 result.json（contract 字段、status 一个词、骨架/模板残留、工单对照里的 element_ids 是否真实存在、预览是否真实） |
| `scripts/pixcheck.py` | 只给提示（退出码 0）。解码渲染后的 PNG（纯标准库）：图不空、不裁切；每个节点填色按声明渲染、标签有可见墨迹与足够对比度；每种节点颜色在图例里有同色色块；图例色块灰度可分；每种边样式有图例线 |
| `resources/checklist.md` | 脚本查不到、需要对照原文人工确认的项 |
| `examples/README.md` | 最小调用示例（示例，合成数据） |
| `benchmark/EVALUATION.md` | 设计理由、内部合成案例上不加载与加载 Skill 的对照记录（仅内部合成案例） |

## 依赖
- Python 3.8+ 标准库即可。渲染器自动探测并按序回退；PDF 字体检查用 `pdffonts`（可选）；PDF 文本用 `pdftotext`（无则 fitz/pypdf）。
- 渲染器都是可选的：全无时 `render` 用内置渲染（有 matplotlib 出 PNG+PDF，否则出 base-14 字体的矢量 PDF，中文无字形），export_log 写明；没有 PNG 时如实记录，不伪造预览。

## 调用方式
```bash
export S=/skills/weekly-skill            # 本地测试时另设 CASE_JSON / WORK_DIR / OUT_DIR
python3 $S/scripts/export_check.py skeleton; python3 $S/scripts/export_check.py tools
python3 $S/scripts/svgfig.py build /app/output/figure_spec.json /app/output/figure.svg
timeout 300 python3 $S/scripts/export_check.py render /app/output/figure.svg --dpi 600
python3 $S/scripts/pixcheck.py /app/output/figure.svg
python3 $S/scripts/svgfig.py build /app/output/figure_spec_v2.json /app/output/figure_v2.svg   # 修改后的版本
python3 $S/scripts/svgfig.py diff /app/output/figure.svg /app/output/figure_v2.svg > /app/output/edit_diff.json
python3 $S/scripts/export_check.py assemble /app/work/notes.json     # 填满 result.json 并自动 check
```

## 输出（/app/output）
`figure_spec.json`、`figure.svg`（layer-panels/edges/nodes/data/text/legend，每个元素有 id 与 data-src）、`figure.png`、`figure.pdf`、`figure_content_map.json`（实体/关系/区室/图例/数据编码，含 CSV sha256）、`figure_pixel_check.json`、`export_log.jsonl`、`figure_spec_v2.json` + `figure_v2.*`、`edit_diff.json`、`result.json`（case_id、每个 contract 字段、status、status_reasons、versions、artifacts；contract 用其他字段名时按含义映射，认不出的填运行摘要并记 run_notes）。

## 方法要点
0. 布局由脚本算：分层（区室约束 + 局部因果序）→ 列序（重心迭代 + 保序回归 PAV 取最近的整数列）→ 让开直通链上的节点 → 正交通道布线（行间/列间空白带，反馈走外侧）→ 标签逐段试放（不压节点、不压别的边、不出画布）。模型只做科学判断（实体、类型、区室、关系、证据），不算坐标。
1. 图是“实体—关系表”的渲染：spec 里每个节点有 kind/comp/src，每条边有 type/evidence/src；content_map 直接由 spec 生成，不靠模型手抄。
2. 作用类型与证据强度是两个独立维度（端点/颜色 vs 线型），避免“间接”吞掉“抑制”。
3. transport 只表示同一实体换区室；转录、表达用 activate。这条规则由 build 自动检查。
4. 数据颜色从 CSV 读、自动分档、自动进图例；图例与图面再由 pixcheck 在像素层面比对。
5. 修改在源上做，图例项 id 按内容命名，新增项排在最后，所以 diff 只显示真实改动。

## 限制
- 自动布局是启发式的：复杂图（> 25 个节点、多条反馈）仍会有边交叉和长绕线；可用 `col`/`rank`/`feedback` 提示调整，或改用手写坐标。修改版从 resolved spec 出发时节点宽度固定，长标签会换行。
- 文字宽度按字符估算；pixcheck 对大图通过约 1200 px 的同源重渲染来检查（无渲染器时跳过并记录）。
- 内置回退渲染只覆盖本 Skill 产生的 SVG 子集（矩形、圆、折线、路径、文字、marker、变换）。
- 不判断机制在生物学上是否成立，只保证与材料一致、证据强度可见。
- 纯文本模型读不到 PDF 里的原图像素，只能依据图注、正文与数据表，并如实说明。

## 维护
版本 lite-1.3（2026-11）：自动布局、生物学图元（脂双层、核膜、基因启动子、复合物、修饰角标）、最小字号自动满足、标签压线检查、resolved spec 修改流程。lite-1.2：skeleton/assemble（任意 contract 字段名、可选输入容错）、build WARN 最多改两轮、pixcheck 改为提示、渲染器可选（内置回退）。改脚本后用 examples/README.md 的示例重跑 build → render → pixcheck → assemble。
