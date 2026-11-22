# 设计说明与内部测试记录

> 内部记录：只用作者自己编写的合成案例，由作者按 SKILL.md 扮演运行时智能体执行；不是平台正式案例，不含任何正式评测结果。

## 1. 为什么是“说明为主 + 三个标准库脚本”
- 运行环境：快速模型、64 次请求 / 900 秒、只保证 Python 标准库。不安装任何东西；SKILL.md + `svgfig.py`（spec → 分层 SVG + content map）+ `export_check.py`（渲染、自检）+ `pixcheck.py`（看渲染像素）。
- 图形摘要的风险不在“画不出来”，而在：一句没有出处的结论、一个抄自摘要的近似数、一个看不见的重叠或白底白字。科学判断留给模型，但每个元素必须带 `src`；能机械检查的交给脚本。

## 2. 合成案例（SIM01-GA-01，示例）
- 材料：合成论文 PDF（摘要、方法、结果、Figure 3 图注）、`data/fig3b_source.csv`（16 行，S07 空值）、工单 `figure-workorder.json`（graphical_abstract：4 个面板、核心结果用源数据柱图带单位、结论不强于原文、180 mm / 300 dpi / ≥ 6 pt、修改请求“改结论措辞”）。contract：`case_id, status, editable_source, export_artifact, content_map, compliance_checks, exceptions`。
- 陷阱：图注 n = 4 vs 可用 3 行；摘要“约 40 倍” vs 数据 37.6；基因名需斜体、基因型上标；1200 px 画布印到 180 mm 时 12 px 文字只有 5.1 pt。

## 3. 旧版（lite-1.0）在同一输入上的问题
| # | 问题 | 后果 |
|---|---|---|
| 1 | `check` 对全是“生成中”的骨架给 PASS；嵌套 JSON（`}}`）被误判为占位符 | 空结果自认为通过；content_map 写成对象就 FAIL |
| 2 | 不读工单，不提 contract 的 5 个字段，用自造字段（panel_map、material_gaps…） | 工单要求没有逐条对照；异常没有按“缺失/无法判断/运行失败”分类 |
| 3 | 没有像素检查：柱子 x 轴标签“WT\nvehicle”被压成一行并相互重叠，图例最后一项与说明文字重叠 | 运行时模型看不见图片，这些都会原样交付 |
| 4 | 字号只按 px 检查（≥ 12 px），不按打印宽度换算 | 180 mm 宽时 12 px = 5.1 pt，低于工单 6 pt |
| 5 | 标签不能局部斜体/上下标 | *Ifnb1*、*Sting1*<sup>−/−</sup> 只能正体，实体命名不规范 |
| 6 | pixcheck 对比度用未线性化亮度（WCAG 要线性） | 白字压 #0072B2 被误报 2.5:1（实际约 5:1） |

## 4. 改后同一输入的执行（按新版 SKILL.md）
调用：读任务+工单（1）→ 骨架+tools（1）→ pdftotext + grep + 读 CSV（1）→ panel_map（1）→ python 从 CSV 生成 bars 写 spec + build（1）→ 改重叠后重 build（1）→ render + pixcheck（1）→ spec_v2 + build + diff + render + pixcheck（1）→ 组装 result.json + check（1）。共约 9 次。
- build 告警 `texts t-err and legend-3 overlap` → 把误差说明并入柱图标题后 0 告警；柱标签按 `\n` 分两行。
- pixcheck：PNG 2126 px = 180 mm × 300 dpi；最小打印字号 6.12 pt（画布宽 1000 px，按 SKILL 的公式算出）；6 个节点颜色、标签墨迹、对比度通过。
- content_map：18 个元素各带 src，4 个柱值 1.00 / 37.57 / 1.01 / 1.21 与 CSV 复算一致（S07 排除）。
- diff：59 个 id 保留，只改了 `n-concl-label` 的文字与出处。
- check：`PASS: 7 contract field(s), status=partial, 0 fail / 0 warn`；exceptions 2 条 contradiction（n、40 倍）。

## 5. 机制与拦截（同一输入实测）
| 问题 | 机制 | 实测输出 |
|---|---|---|
| 骨架假通过 | check：contract 字段为“生成中”/无 SVG/模板槽 → FAIL | `contract field 'compliance_checks' still holds skeleton text` |
| 文字重叠、出画布 | build 按文字框求交 | `texts t-err and legend-3 overlap` |
| 字号太小 | pixcheck 按 width_mm 换算 pt | `text … prints at 5.1 pt, below 6.0 pt` |
| 修改后标签消失 | pixcheck 密集采样标签墨迹 | 旧的 15×9 采样把两行结论误判为“无墨迹”，改为 30×40 后正确 |
| 工单要求漏项 | compliance_checks 一行一项，element_ids 必须在 SVG 中 | `requirement … cites element id … not in any output SVG` |

## 6. 仍做不到的
- 不自动排版：坐标由模型给出，脚本只检查重叠、穿越、越界、字号。
- 上下标按 75% 字号渲染，pixcheck 的最小字号只按 `font-size` 属性计算。
- PDF 中原图的像素读不到，只依据正文、图注与数据。
