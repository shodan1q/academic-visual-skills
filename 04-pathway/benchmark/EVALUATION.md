# 设计说明与内部测试记录

> 内部记录：只用作者自己编写的合成案例，由作者按 SKILL.md 扮演运行时智能体执行；不是平台正式案例，不含任何正式评测结果。

## 1. 为什么是“说明为主 + 三个标准库脚本”
- 运行环境是快速模型、64 次请求 / 900 秒、只保证 Python 标准库。重型流水线容易因依赖与超时整体失败，所以本包只有 SKILL.md 和 3 个标准库脚本，不安装任何东西。
- 科学判断（这是基因还是蛋白、这句话是激活还是抑制、证据是否直接）留给模型，但必须写成 spec 里的结构化字段（`kind`、`comp`、`type`、`evidence`、`src`）；**一切能机械检查的都交给脚本**：图例生成、数据上色、区室归属、transport 语义、边重叠、像素渲染。
- 流程按 20–30 次调用设计；内部合成案例实际用了约 10 次命令调用（下文第 3 节）。

## 2. 合成案例（SIM04-PATHWAY-01，示例）
- 材料：一份合成“论文” PDF（8 段结果 + Figure 3 图注，小鼠 cGAS–STING–TBK1–IRF3 通路、STAT1→TRIM30a 负反馈、TBK1→NF-κB 并行支、PPM1A 间接抑制、STING 同义名 MITA/TMEM173、摘要与数据表对 Irf3 的矛盾）；9 行 log2FC 表；工单 `figure-workorder.json`（6 个必需区室、4 项必须表现、180 mm / 600 dpi / ≥ 6 pt、修改请求“TBK1 改为 TBK1 (p-S172)、IFNAR 改灰色”）。
- 陷阱：修改请求里的 S172 位点原文没有；IFNAR、JAK1 在数据表里没有值；Irf3 文字说上调、数据是 −0.3。

## 3. 同一输入的两次执行对照
**A. 不带本版规则（相当于基础智能体或旧版 lite-1.0 的做法：手写布局、手挑颜色、只查版式）**，第一稿的问题，全部来自实际产出的 SVG/PNG：
| # | 问题 | 读者会怎么判 |
|---|---|---|
| 1 | 质膜、ER 膜画成无标题的色带 | 工单要求的 6 个区室有 2 个没出现在图上 |
| 2 | IRF3 → *Ifnb1*、IRF3 → *Cxcl10*、*Ifnb1* → IFN-β 都画成 transport 虚线 | “转运”被用来表示转录和分泌，语义错 |
| 3 | PPM1A ⊣ TBK1 画成实线 | 原文明说“仅过表达、应视为间接”，而 indirect 类型只有箭头，没法表示“间接抑制” |
| 4 | STING–TBK1 的“结合”和“+P S365 磷酸化”两条边重合 | 两个关系看起来只有一条 |
| 5 | 分泌边横穿 *Cxcl10* 节点和图例 | 图例被线切开 |
| 6 | 颜色按 log2FC 手工分档；无数据的 IFNAR/JAK1/NF-κB 为白色但图例没有“无数据”项；图例无标题和单位 | 图例与图面不自洽 |
| 7 | 深红节点上黑字 | 对比度低 |
| 8 | 只把 result.json 骨架写成“生成中”时，旧检查脚本也给 PASS | 预算耗尽时会交出空结果却自认为通过 |
| 9 | 修改后 TBK1 标签变长、IFNAR 变灰，但灰色在图例里没有含义 | 修改破坏了图例一致性，无人发现 |

**B. 按本版 SKILL.md 执行**：读工单与源（2 次）→ spec + build（1 次，0 告警）→ render 600 dpi + pixcheck（1 次）→ spec_v2 + build + diff + render + pixcheck（2 次，第一次被 pixcheck 拦下第 9 条）→ 画布加宽修图例越界（1 次）→ 模板组装 result.json + check（1–2 次）。结果：
- build 无告警；PNG 4252 × 3254 px（180 mm @ 600 dpi），PDF 矢量、16 个字体嵌入；pixcheck 18 个节点填色、标签、图例同色全部通过；check PASS，0 fail / 0 warn。
- content_map 18 个实体（含 kind、区室、aliases、数据值）、19 条关系（含 evidence）；data_encoding 记录 CSV sha256 与每个节点的值/分档/颜色。
- diff：132 个 id 保留，改动只有 TBK1 标签、IFNAR 填色、新增的灰色图例项。
- exceptions 三条分类记录：contradiction（Irf3）、user_request_not_in_source（S172）、undecidable（IFN-β 蛋白借用转录本数值）；status = partial 并逐条给原因。

## 4. 每条规则拦住的是哪个问题（同一输入上实测）
| A 表中的问题 | 拦截机制 | 实测输出（节选） |
|---|---|---|
| 1 区室无名 | build：无标题 panel 告警；窄带标题自动画在带内 | `panel p-pm has no title` |
| 2 transport 误用 | build：transport 两端必须是同一实体 | `transport joins different entities (IRF3 -> Ifnb1)` |
| 3 间接抑制 | spec：`evidence` 与 `type` 正交（红色点线 T 端），图例自动加“indirect evidence” | 图例新增 `legend-ev-indirect` |
| 4 边重合 | build：同一节点对两条直线边告警 | `edges e5 and e17 draw over each other` |
| 5 穿节点/穿图例 | build：线段与节点、图例框求交 | `edge e8 crosses the legend box` |
| 6 数据色与图例 | `canvas.colorscale` 读 CSV 自动分档上色、自动图例（含“no value in …”）；pixcheck 比对节点与图例的渲染颜色 | `node n-ifnar colour #BABABA has no legend swatch` |
| 7 对比度 | 深色填充自动白字；pixcheck 计算标签/填充对比度 | `label contrast` 字段写入 pixel_check.json |
| 8 假通过 | check：contract 字段残留“生成中”、`<…>` 模板槽、工单对照里不存在的 element_id 都判 FAIL | `requirement … cites element id … not in any output SVG` |
| 9 修改破坏图例 | 改 spec 重建 + pixcheck；自加图例项排在最后、id 按内容命名，diff 不被重排污染 | diff 只含 3 处真实改动 |

## 5. 仍做不到的
- 不自动排版：坐标由模型给出，脚本只检查（区室、重叠、穿越、越界）。
- “这句话到底是激活还是抑制”“证据算不算直接”仍是模型判断；脚本只保证判断被显式记录、被一致地画出。
- 纯文本模型看不到 PDF 中原图的像素，只能依据图注与正文；这一点会写进 exceptions。
- pixcheck 对超过约 260 万像素的导出图通过同源 1200 px 重渲染来检查，不逐像素解码原图。

## 6. 1.2 调整：运行预算内的稳健性（2026-11）
同一套 1.1 设计用到字段名不同、工具更少的环境时，会在“收尾”上耗掉预算。按四个假设用合成案例复现（SYN04-TEST-C：TLR4–NF-κB 通路，contract 写成 `deliverables: [{field: caseId}, {field: outcome, allowed: [done, partial, failed]}, diagramSource, previewFiles, elementProvenance, qcResults, knownProblems, editHistory, 图注]`）：

| 假设 | 1.1 上的复现 | 1.2 的处理 |
|---|---|---|
| H1 组装只填固定字段名 | 组装模板只写 editable_source / export_artifact / content_map / compliance_checks / exceptions，这 9 个 contract 字段都会残留“生成中”或缺失，check 判 FAIL；骨架要模型自己解析字段对象列表 | `export_check.py skeleton` 认所有 contract 写法；`assemble` 按含义映射（caseId→case_id、outcome→状态词、diagramSource→editable_source、previewFiles→export_artifact、elementProvenance→content_map、qcResults→compliance_checks、knownProblems→exceptions、editHistory→change_log、图注→caption），认不出的填运行摘要并记 run_notes |
| H2 可选文件缺失时组装崩溃 | 无渲染器时 v2 pixcheck 退出 1 且不写 `figure_pixel_check.json` → 模板 `FileNotFoundError`；`edit_diff.json` 也是无条件读取 | assemble 每个输入都可缺；notes.json 坏了明确报 FAIL |
| H3 不可满足的外观检查导致循环 | SKILL 要求“build WARN 全部改到消失”、“pixcheck FAIL → 重建”；版面类 WARN（如图例略超出画布）不一定能在几轮内消掉；check 把模板槽、不存在的 element_id 判 FAIL | build WARN 最多再改两轮，剩下的由 assemble 自动记入 exceptions；pixcheck 只给提示、退出码 0；模板槽与 element_id 降为 WARN（与 02 的 1.2 一致） |
| H4 渲染器缺失 | PATH 中无渲染器：render 不出 PNG/PDF，pixcheck FAIL，check 报“无预览”FAIL（不可满足） | render 末端加内置渲染：有 matplotlib 出 PNG+PDF，否则出标准库矢量 PDF（Helvetica/Symbol，希腊字母可显示）；pixcheck 读不了 PNG 写 `skipped`；渲染确实失败过的 SVG 不再判 FAIL |

保留不变：实体/关系/区室规则、CSV 分档上色与自动图例、content map、源级修改 + diff、工单逐条对照、分类异常。

自测（作者按 SKILL.md 执行，合成案例，非正式案例）：
- 本机有 rsvg-convert：PNG 2126 px（180 mm @ 300 dpi）+ 矢量 PDF（15 个字体嵌入）；pixcheck 9 个节点无提示；assemble → `PASS: 9 contract field(s), status=partial, 0 fail / 0 warn`，build 剩下的“图例超出画布”自动进 knownProblems。
- 本机 PATH 中无任何渲染器、无 matplotlib：render 出标准库矢量 PDF，pixcheck 跳过，assemble PASS，exceptions 记缺 PNG 与跳过的像素检查。
- gpu 服务器（matplotlib，无 rsvg/cairosvg/magick）：render 用内置 matplotlib 出 PNG+PDF，pixcheck 在 1200 px 重渲染上检查 9 个节点无提示，assemble PASS。
- 内置渲染与 rsvg 渲染目视对照：区室、膜带、节点、斜体基因名、箭头/T 端/圆点端 marker、虚线 transport、图例都在原位。

