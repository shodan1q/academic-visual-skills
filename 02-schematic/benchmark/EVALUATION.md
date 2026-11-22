# 设计说明与内部测试记录

> 内部记录：只用作者自己编写的合成案例，由作者按 SKILL.md 扮演运行时智能体执行；不是平台正式案例，不含任何正式评测结果。

## 1. 为什么是“说明为主 + 三个标准库脚本”
- 运行环境是快速模型、64 次请求 / 900 秒、只保证 Python 标准库。重型流水线容易因依赖与超时整体失败，所以本包只有 SKILL.md 和 3 个标准库脚本，不安装任何东西。
- 科学判断（这句话是“包含”还是“产生”、是抑制还是相关、证据是否已检验）留给模型，但必须写成 spec 里的结构化字段（`parent`、`comp`、`kind`、`type`、`evidence`、`src`）；**一切能机械检查的都交给脚本**：嵌套几何、组归属、步骤方向、连线交叉、图例生成、数据上色、像素渲染、result.json 完整性。
- 流程按 20–30 次调用设计；内部合成案例实际约 11 次命令调用（第 3 节）。

## 2. 合成案例（SIM02-SCHEMATIC-01，示例）
- 材料：合成“论文” PDF（摘要 + 6 段结果 + Figure 3 图注 + 2 段方法，小鼠肠类器官：类器官 ⊃ 隐窝样/绒毛样两个区域 ⊃ 6 种细胞；Lgr5+ 干细胞 → TA 细胞 → 吸收/分泌两支；Paneth 细胞分泌 Wnt3、EGF 支持干细胞；Notch–Hes1 抑制分泌分化；5 步实验流程与 ENR 培养基浓度）；Table S2（6 行：细胞类型、谱系、细胞数、区域）；工单 `figure-workorder.json`（`editable_relationship_schematic`，3 个子图、5 条 must_show、180 mm / 600 dpi / ≥ 6 pt、修改请求“TA cells 改名、分泌谱系改色 #CC79A7”）。
- 陷阱：培养天数摘要/方法写 7 天、结果写 4 天；Paneth 细胞“位置在隐窝”但“谱系属分泌”（结构与类别交叉）；Tuft 细胞只在成像里出现、表中没有；“Hes1 是否直接作用于 Atoh1 未检验”；EGF 同时是培养基成分和 Paneth 分泌因子。

## 3. 同一输入的两次执行对照
**A. 按旧版 lite-1.0 SKILL.md 执行**（相当于“有画图脚本但没有结构检查”的基础做法）。以下问题都在实际产出或实际运行的脚本输出上确认：
| # | 问题 | 读者/审稿人会怎么判 |
|---|---|---|
| 1 | 只写了“生成中”的 result.json 骨架，旧 check 给 `PASS: 7 contract field(s), 0 fail` | 预算耗尽时交出空结果却自认通过 |
| 2 | 旧 SKILL 没提工单文件，也没有 compliance_checks / content_map / exceptions 的写法；contract 字段只要求“非空” | 工单 5 条 must_show 无逐条对照，无法复核 |
| 3 | Paneth 细胞被画进绒毛样区域（spec 里本应属隐窝）、绒毛框伸出类器官框，旧 build：`no warnings` | “包含关系画错”正是题面列的典型失败 |
| 4 | 颜色手挑：TA 细胞用了第 4 种颜色但图例只列 3 类；按旧说明逐个节点 `edit --set fill` 改分泌谱系颜色后，图例色块仍是旧色。旧工具无任何提示 | 图例与数据表/图面对不上 |
| 5 | 旧 build 不支持边指向分组，“Hes1 抑制分泌分化”只能连到 Goblet 一个细胞；旧版没有证据强度维度 | 关系对象画错；“未检验”只能画成灰箭头或实线 |
| 6 | 流程第 3、4 步箭头画反、两条连线交叉，旧 build 不查 | 时序颠倒、引导线交叉 |

**B. 按本版 SKILL.md 执行**：读工单与 case（1）→ 骨架 + tools（1）→ pdftotext + 读 CSV + sha256（1）→ 写 spec + build（1，3 条 WARN：标签被遮、无图例的灰底、图例越界）→ 修正 + render 600 dpi + pixcheck（1，灰度相近警告）→ 改色、重排两组位置消除新加的“连线交叉”警告（1）→ spec_v2 + build + diff + render + pixcheck（1）→ 模板组装 result.json（1）→ check（1–2）。结果：
- build 无告警；PNG 4252 × 3700 px（180 mm @ 600 dpi），PDF 矢量、19 个字体嵌入；pixcheck 21 个节点填色、标签、图例同色全部通过。
- content_map：21 个实体、38 条关系（其中 26 条 `contains` 由嵌套自动导出）、10 个图例项（自动）；data_encoding 记 CSV sha256 与每个节点的类别、颜色、显示的细胞数。
- 修改：只改 2 个标签与 `categories.colors.secretory`；diff 99 个 id 不变，6 个分泌谱系节点和图例色块一起变色。
- exceptions 三条：contradiction（7 天 vs 4 天，图上星号脚注）、material_missing（Tuft 细胞）、undecidable（Hes1→Atoh1）；status = partial 并逐条给原因。check PASS，0 fail / 0 warn。

## 4. 每条规则拦住的是哪个问题（A 表的错误注入同一 spec 后实测）
| A 表中的问题 | 拦截机制 | 实测输出（节选） |
|---|---|---|
| 1 骨架假通过 | check：contract 字段残留“生成中”、`<…>` 模板槽、对照表里不存在的 element_id 都判 FAIL | `contract field 'content_map' still holds skeleton text` |
| 2 工单无对照 | SKILL 第 1 步读工单、第 8 步模板要求 compliance_checks 覆盖每条 must_show 且带 element_ids；无对照时 check 警告 | `no requirement trace: list each workorder requirement` |
| 3 包含画错 | build：节点框必须完全在 `comp` 组内、不能落进别的组；子组不得出界；兄弟组不得交叠 | `panel p-villus sticks out of its parent p-org`；`node a-pan is not fully inside its group p-crypt` |
| 4 图例脱节 | `canvas.categories` 读 CSV 一类一色、自动图例；build 报无图例的颜色；pixcheck 在像素上比对节点与图例 | `fill #56B4E9 used on nodes but has no legend item`；`node b-pan colour #CB78A6 has no legend swatch` |
| 5 关系对象/证据 | 边可连 panel（指向整个谱系）；`evidence` 与 `type` 正交，图例自动加证据线型 | content_map：`Hes1 → Secretory lineage, inhibit` |
| 6 顺序/交叉 | build：step 箭头与标签序号反向、两条连线相交都告警 | `edge e-s34: step goes from 4 to 3`；`edges e-tabs and e-hes cross each other` |

另：本轮自测发现旧 check 会把内容映射里嵌套 JSON 的 `}}` 误判为占位符，已改为只扫描字符串值。

## 5. 仍做不到的
- 不自动排版：坐标由模型给出，脚本只检查（嵌套、重叠、交叉、越界）。
- “这句话是包含还是产生”“证据算不算已检验”仍是模型判断；脚本只保证判断被显式记录、被一致地画出。
- 纯文本模型看不到 PDF 中原图的像素，只能依据图注与正文；这一点会写进 exceptions。
- pixcheck 对超过约 260 万像素的导出图通过同源 1200 px 重渲染来检查，不逐像素解码原图。
