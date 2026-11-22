# 设计说明与内部测试记录

> 内部记录：只用作者自己编写的合成案例，由作者按 SKILL.md 扮演运行时智能体执行；不是平台正式案例，不含任何正式评测结果。

## 1. 为什么是“说明为主 + 三个标准库脚本”
- 运行环境：快速模型、64 次请求 / 900 秒、只保证 Python 标准库。不安装任何东西；SKILL.md + `svgfig.py`（spec → 分层 SVG + content map）+ `export_check.py`（渲染、自检）+ `pixcheck.py`（看渲染像素）。
- 装置图与路线图的错误多是“顺序、条件、单位、连接”与原文不一致，或标签压住部件看不清。先抽结构化清单（ir.md，每行带出处），再画；能机械检查的交给脚本。

## 2. 合成案例（SIM05-ROUTE-01，示例）
- 材料：合成论文 PDF（三步合成：甲基化 → Suzuki 偶联 → 水解；Methods、Table 1、Scheme 1 图注）、工单 `figure-workorder.json`（apparatus_and_technical_route：化合物 1–4 编号与名称、箭头上试剂/下条件、每步产率、步骤顺序同 Methods；180 mm / 300 dpi / ≥ 6 pt；修改请求“产物 4 高亮并加图例”）。contract 同 7 字段。
- 陷阱：第 2 步温度 Methods 与 Scheme 写 90 °C、Table 1 写 80 °C；化学式需下标；第 2 步试剂很长。

## 3. 旧版（lite-1.0）在同一输入上的问题
| # | 问题 | 后果 |
|---|---|---|
| 1 | `check` 对骨架 result.json 给 PASS；嵌套 JSON 被误判为占位符 | 空结果自认为通过 |
| 2 | 不读工单、不提 contract 字段；没有“工单逐条对照” | 必须表现的四项与导出参数没有逐项证据 |
| 3 | 边标签只能一行 | “试剂 + 溶剂 + 温度 + 时间 + 产率”挤成一长行 |
| 4 | 第 2 步长标签压住化合物 2 和 3 的方框，build 0 告警、渲染照样出图 | 读者看不清试剂和化合物名；模型看不见图片 |
| 5 | 字号不按打印宽度换算 | 1200 px 画布印到 180 mm，12 px 边标签只有 5.1 pt |
| 6 | K2CO3、H2O 不能写下标 | 化学式不规范 |

## 4. 改后同一输入的执行（按新版 SKILL.md）
调用：读任务+工单（1）→ 骨架+tools（1）→ pdftotext + grep（1）→ ir.md（1）→ spec + build（1，得到 `label of edge e-b overlaps node n-c2 / n-c3`）→ 标签拆成三行 + 下标后重 build（1，0 告警）→ render + pixcheck（1）→ spec_v2 + build + diff + render + pixcheck（1）→ 组装 result.json + check（1）。共约 9 次。
- pixcheck：PNG 2126 px = 180 mm × 300 dpi；最小打印字号 6.12 pt（画布宽 1000 px）；4 个化合物节点颜色与标签通过；PDF 8 个字体全部嵌入。
- diff：v2 只新增 `legend-1`（target compound）与 `n-c4` 填色，29 个 id 保留；v2 的 pixcheck 通过。
- exceptions：1 条 contradiction（90 °C vs 80 °C，按 Methods + Scheme 画）；status partial。
- check：`PASS: 7 contract field(s), status=partial, 0 fail / 0 warn`。

## 5. 机制与拦截（同一输入实测）
| 问题 | 机制 | 实测输出 |
|---|---|---|
| 骨架假通过 | check：contract 字段为“生成中”/无 SVG → FAIL | `no SVG figure in the output dir` |
| 标签压部件 | build 对边标签框与节点求交 | `label of edge e-b overlaps node n-c3` |
| 字号太小 | pixcheck 按 width_mm 换算 pt；SKILL 给出画布宽度公式 | `text … prints at 5.1 pt, below 6.0 pt` |
| 图例缺项 | build 比对已用边类型/颜色与图例 | `legend has no item for edge type …` |
| 工单漏项 | compliance_checks 一行一项，element_ids 必须在 SVG 中 | `requirement … cites element id … not in any output SVG` |

## 6. 仍做不到的
- 不画化学结构式（只画编号 + 名称节点）；需要结构式时在 exceptions 说明。
- 不自动排版：坐标由模型给出，脚本只检查重叠、穿越、越界、字号。
- 不判断工艺或路线是否合理，只保证与原文一致。
