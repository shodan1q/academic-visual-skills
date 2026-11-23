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

## 7. 1.2 调整：运行预算内的稳健性（2026-11）
同一套 1.1 设计用到字段名不同、工具更少的环境时，会在“收尾”上耗掉预算。按四个假设逐条用合成案例复现（SYN03-TEST-B：contract 写成 `required: [run_status, figure_source_files, rendered_outputs, provenance_table, qa_report, open_issues, revision_history, reviewer_note]`，修改请求把 xylose 设成与 glucose 相同的 #0072B2）：

| 假设 | 1.1 上的复现 | 1.2 的处理 |
|---|---|---|
| H1 组装只填固定字段名 | 1.1 骨架一行命令不认 `properties/required`，只写出 `run_status`；组装模板照常写 editable_source 等 → check：7 个 contract 字段缺失 + `run_status` 残留“生成中” | `export_check.py skeleton` 认所有 contract 写法；`assemble` 按含义映射每个字段（run_status→状态词、figure_source_files→editable_source、rendered_outputs→export_artifact、provenance_table→content_map、qa_report→compliance_checks、open_issues→exceptions、revision_history→change_log），认不出的填运行摘要 + 文件清单并记 run_notes；check 按含义找 exceptions |
| H2 可选文件缺失时组装崩溃 | 删掉 `chart_pixel_check.json` → `FileNotFoundError`；无 matplotlib 时 export_log 是 render 的格式，模板取 `e["stem"]` 会 KeyError | assemble 每个输入都可缺；两种 export_log 格式都认；notes.json 坏了会明确报 FAIL 而不是静默丢弃 |
| H3 不可满足的外观检查导致循环 | 修改请求造成两系列同色 → v2 的 pixcheck 3 条 FAIL，check 把它们算作 FAIL，按 SKILL“照做”后永远过不了 | pixcheck 只给提示、退出码 0；data-to-mark 失败仍是 FAIL，但改 2 轮后在 exceptions 点名即降为 WARN；模板槽、element_id 不存在降为 WARN |
| H4 渲染器缺失 | 无 matplotlib、无 rsvg 等：render 不出任何文件，pixcheck FAIL 且不写 json，check 报“无预览”FAIL（不可满足） | render 末端加内置渲染：有 matplotlib 出 PNG+PDF，否则出标准库矢量 PDF（base-14 字体）；pixcheck 读不了 PNG 写 `skipped`；渲染确实失败过的 SVG 不再判 FAIL |

保留不变：模板从数据行复算、刻度标定对账（含误差线）、content map、源级修改 + diff、工单逐条对照、分类异常。

自测（作者按 SKILL.md 执行，合成案例，非正式案例）：
- gpu 服务器（matplotlib 3.11，无 rsvg/cairosvg/magick）：marks PASS 19 个样本；pixcheck 提示 1 条（n 不符）；v2 同色请求提示 4 条但退出码 0；assemble → `PASS: 9 contract field(s), status=partial, 0 fail / 0 warn`，exceptions 自动补录 n 不符与排除行。180 mm × 600 dpi 时 pixcheck 用内置 matplotlib 重渲染 1600 px 检查。
- 本机无 matplotlib、PATH 中无任何渲染器：svgchart → render 出标准库矢量 PDF（无 PNG）→ pixcheck 跳过 → assemble PASS，exceptions 记录缺 PNG 与跳过的像素检查。有 rsvg 时同一路径出 PNG+PDF。
- 公开示例的 7 字段 contract：映射为同名字段，输出与 1.1 结构一致。
- 内置渲染与 rsvg 渲染逐图目视对照：柱、误差线、个体点、旋转的 y 轴标签、mathtext 下标、图例、箭头 marker 都在原位。

