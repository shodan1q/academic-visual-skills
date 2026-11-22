# 设计说明与内部测试记录

> 内部记录：只用作者自己编写的合成案例，由作者按 SKILL.md 扮演运行时智能体执行；不是平台正式案例，不含任何正式评测结果。

## 1. 为什么是“说明为主 + 一个绘图模板 + 三个标准库脚本”
- 运行环境：快速模型、64 次请求 / 900 秒、只保证 Python 标准库。重型流水线容易整体失败，所以不安装任何东西；matplotlib 有则用模板，无则走 `svgchart` 回退。
- 科学判断（误差线是什么、哪些比较有显著性、单位怎么写）留给模型，但必须写进 `chart_config.json` 并带 `src`；**能机械检查的都交给脚本**：均值/SD/SEM/n 从数据行复算、空值排除与行号、图元回读对账、渲染像素、色盲可分、导出尺寸与字号、源文件级修改的差异。
- 模型只写 JSON 配置、不写绘图代码：DeepSeek 一类快速模型手写分组柱图 + 误差线 + 个体点 + 图例时最容易出错，也最费调用。

## 2. 合成案例（SIM03-CHART-01，示例）
- 材料：合成论文 PDF（摘要、方法、结果、Figure 3 图注），`data/fig3b_source.csv`（16 行：基因型 × 处理 × 小鼠，S07 为空值“qPCR well failed”），工单 `artifacts/figure-workorder.json`（source_value_chart：分组柱 + 个体点、误差照图注、n 进图注、显著性只照原文、色盲友好、89 mm / 600 dpi / ≥ 6 pt / svg+pdf+png，修改请求“DMXAA 改朱红、y 轴标签改为 *Ifnb1* / *Actb*”）。contract：`case_id, status, editable_source, export_artifact, content_map, compliance_checks, exceptions`。
- 陷阱：图注写 n = 4 只/组，WT+DMXAA 只有 3 个可用值；摘要写“约 40 倍”，数据均值 37.57；图注误差为 s.e.m.；基因名需斜体、基因型带上标；运行机没有 pdftotext 和 Arial。

## 3. 同一输入下旧版（lite-1.0）的模拟：发现的问题
| # | 问题 | 后果 |
|---|---|---|
| 1 | `check` 对全是“生成中”的骨架 result.json、且输出目录里没有任何图，给出 **PASS（0 fail）** | 预算耗尽时交出空结果却自认为通过 |
| 2 | `check` 把任何嵌套 JSON 判为“占位符”（`}}` 命中占位正则）：`content_map` 写成对象就 FAIL | 智能体被迫压平结构或反复改，浪费调用 |
| 3 | SKILL 不提工单，也不提 contract 的 `editable_source / export_artifact / content_map / compliance_checks / exceptions`，改用自己的 data_trace、material_gaps 等字段 | 字段靠猜；工单要求没有逐条对照；“材料缺失 / 无法判断 / 运行失败”没分开 |
| 4 | 读 PDF 只为抽表格，图注（误差含义、n、检验、单位）没有提取步骤；模板默认 SD、单系列 | 误差线类型可能画错；n = 4 与 3 的矛盾无人发现；分组柱图每次手写 |
| 5 | `marks` 不查误差线；用自由最小二乘拟合比例尺 | 把空值当 0 算出的 WT+DMXAA 柱（28.2 而非 37.6）在拟合下 **PASS**（大值柱杠杆高，拟合把错误吸收） |
| 6 | 没有像素检查 | 图宽是否等于 89 mm × 600 dpi、柱色与图例是否一致、红/绿配色都没人看（模型看不见图） |
| 7 | `diff` 只比较带 id 元素自身的属性，matplotlib 把填色写在子 path 上 | 修改请求“DMXAA 改朱红”在 edit 记录里是**空的** |

## 4. 改后同一输入的执行（按新版 SKILL.md）
调用：读任务+工单（1）→ 骨架+tools（1）→ PDF 文本（fitz 回退）+ grep 图注 + table（1）→ 复制模板与数据、写 chart_config.json（1）→ 出图（1）→ marks + pixcheck（1）→ edit_v2 + diff + marks + pixcheck（1）→ 组装 result.json（1）→ check（1）。共 9 次命令调用。
- 模板输出：4 根柱的均值、SEM、n 与 CSV 行号；`EXCLUDED: row 8 S07`；`WARN: n mismatch: WT/DMXAA has n=3 usable rows, source states n=4`。图注自动附 n 与排除行。
- marks：`PASS: 23 mark sample(s)`，比例尺取自 y 轴刻度 `[0, 10, …, 50]`（2.857 px/单位），柱长、4 条误差线全长、15 个个体点逐一核对。
- pixcheck：PNG 2102 px 宽 = 89 mm × 600 dpi；4 根柱渲染色 = 声明色；系列色在 protan/deutan/tritan 模拟下距离 212/228/251；最小字号 7 pt。
- edit：`edit_v2.json` 只有两个键；diff 的 changed_ids = `bar-0-1, bar-1-1, patch_6（图例色块）, ylabel`，58 个 id 保留；v2 的 marks、pixcheck 均 PASS，pixcheck 提示新配色灰度差 0.07 → 写入 exceptions。
- 同一配置重跑，chart.svg 的 sha256 完全相同（固定 hashsalt、去掉日期元数据）。
- check：`PASS: 7 contract field(s), status=partial, 0 fail / 0 warn`；status_reasons 3 条，exceptions 4 条（contradiction ×2、data_excluded、undecidable）。

## 5. 每条机制拦住什么（同一输入上实测）
| 旧版问题 | 新机制 | 实测输出（节选） |
|---|---|---|
| 1 骨架假通过 | check：contract 字段仍是“生成中”、无图、模板槽未填 → FAIL | `FAIL: no chart SVG in the output dir` |
| 2 嵌套 JSON 误报 | 只扫描字符串叶子 | 嵌套 content_map 通过 |
| 3 字段与工单 | 组装模板直接产出 5 个 contract 字段；compliance_checks 的 element_ids 必须存在于 SVG；exceptions 分类 | `requirement … cites element id … not in any output SVG` |
| 4 图注信息 | 第 3 步 grep 图注；配置 `error`/`n_declared`/`sig`/`src`；模板对 n 不符告警，check 要求写进 exceptions | `content map warns 'n mismatch…' but exceptions is empty` |
| 5 对账太弱 | y 刻度标定 + 误差线全长入账 | 空值当 0：`bar-0-1 … residual 18.78% of axis MISMATCH`；按图注 n=4 算 SEM：`err-0-1 … MISMATCH` |
| 6 看不见图 | pixcheck 解码 PNG | 红/绿配色：`FAIL: series 'vehicle' and 'DMXAA' collapse under deutan (distance 29 < 40)`；折线图 content map 写错 id：`FAIL: mark pts-4-1 … not in the SVG` |
| 7 修改记录为空 | diff 比较整个子树的样式与文字，只报最内层改动 | `bar-0-1 style: fill #e69f00 → #d55e00`、`ylabel text …` |

另做了一个折线图（两细胞系 × 5 时间点、1 个 NA）：模板、marks（20 个样本，刻度标定）、pixcheck 均通过，NA 行自动排除并告警 n 不符。

## 6. 仍做不到的
- 箱线图、热图、多面板没有模板，需要照模板写法自己画；marks 只覆盖柱、误差线、点、折线顶点。
- 不重算显著性，只保证图上的符号都有原文出处；图注没写误差类型时只能记 undecidable。
- PDF 中原图的像素读不到，只依据图注、正文与源数据。
- pixcheck 不识别缺字方框；缺字靠 matplotlib 的 Glyph 告警（模板记录，check 判 FAIL）。
