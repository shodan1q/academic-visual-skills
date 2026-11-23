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
| 1 骨架假通过 | check：contract 字段残留“生成中”判 FAIL；`<…>` 模板槽、对照表里不存在的 element_id 判 WARN（1.2） | `contract field 'content_map' still holds skeleton text` |
| 2 工单无对照 | SKILL 第 1 步读工单、第 8 步模板要求 compliance_checks 覆盖每条 must_show 且带 element_ids；无对照时 check 警告 | `no requirement trace: list each workorder requirement` |
| 3 包含画错 | build：节点框必须完全在 `comp` 组内、不能落进别的组；子组不得出界；兄弟组不得交叠 | `panel p-villus sticks out of its parent p-org`；`node a-pan is not fully inside its group p-crypt` |
| 4 图例脱节 | `canvas.categories` 读 CSV 一类一色、自动图例；build 报无图例的颜色；pixcheck 在像素上比对节点与图例 | `fill #56B4E9 used on nodes but has no legend item`；`node b-pan colour #CB78A6 has no legend swatch` |
| 5 关系对象/证据 | 边可连 panel（指向整个谱系）；`evidence` 与 `type` 正交，图例自动加证据线型 | content_map：`Hes1 → Secretory lineage, inhibit` |
| 6 顺序/交叉 | build：step 箭头与标签序号反向、两条连线相交都告警 | `edge e-s34: step goes from 4 to 3`；`edges e-tabs and e-hes cross each other` |

另：本轮自测发现旧 check 会把内容映射里嵌套 JSON 的 `}}` 误判为占位符，已改为只扫描字符串值。

## 5. 仍做不到的
- （1.0–1.2）不自动排版：坐标由模型给出，脚本只检查（嵌套、重叠、交叉、越界）。1.3 起改为结构 spec + 自动排版，见第 7 节。
- “这句话是包含还是产生”“证据算不算已检验”仍是模型判断；脚本只保证判断被显式记录、被一致地画出。
- 纯文本模型看不到 PDF 中原图的像素，只能依据图注与正文；这一点会写进 exceptions。
- pixcheck 对超过约 260 万像素的导出图通过同源 1200 px 重渲染来检查，不逐像素解码原图。

## 6. 1.2 调整（2026-11）
1.1 步骤更多、门槛更硬，运行预算内容易在可选检查上返工。1.2 回到 1.0 的九步流程（步骤短、WARN 可记录不必清零），只保留风险低的部分：build 自动出 content_map、组内包含与图例核对、CSV 分类着色、check 对残留“生成中”判 FAIL 与逐个字符串叶子扫占位词。pixcheck 只给提示；`kind`/`comp` 缺省降为 NOTE，旧式 spec 不再产生 WARN。

## 7. 1.3：结构 spec + 自动排版（第二个合成案例，前后对照）
**案例 SIM02-QS-FIG3（示例，合成）**：作者编写的 4 页“论文” PDF（矢量 Figure 3，图中标签在 PDF 文本层里），内容按哈维弧菌群体感应的公开教科书知识编写：三对自诱导物—受体（HAI-1/LuxN、AI-2/LuxP·LuxQ、CAI-1/CqsS）、低密度激酶模式与高密度磷酸酶模式两个子图、LuxU→LuxO 磷酸转移、Qrr sRNA 与 Hfq 抑制 luxR、激活 aphA、LuxR 激活 luxCDABE；Table 1（CSV）给出信号类别；工单 `editable_relationship_schematic`，6 条 must_show（含“受体在内膜、LuxP 在周质”“未检验的反馈不能像已确立的调控”），180 mm / 600 dpi / ≥ 6 pt，修改请求“Qrr1-5 改名 + inter-species 类改色 #CC79A7”。陷阱：结果段说 4 个 Qrr、摘要与方法说 5 个；OD600 两处写法不同；LuxT 在引言出现但不属于该图；LuxR→qrr4 反馈仅 ChIP。

**执行方式**：同一个快速小模型分别只按 1.2 与 1.3 的 SKILL.md 扮演运行时智能体（路径映射到本机、不看答案文件），作者事后打开 PNG，按审稿人的眼光检查。

| 项 | 1.2（手填坐标） | 1.3（结构 spec，自动排版） |
|---|---|---|
| 调用次数 | 12 | 14（另一次 12） |
| 分区 / 包含 | 只有 a、b 两个框；“inner membrane”“cytoplasm”是浮在左侧的两行字，受体并不在任何膜区里；“periplasm”标注因与连线重叠被删，工单第 2 条自评 partial | 每个子图 4 个嵌套分区（自诱导物与合成酶 / 周质 LuxP / 内膜 LuxN·LuxPQ·CqsS / 胞质），content_map 43 条 `contains`；工单第 2 条 pass 且图上可见 |
| 图例与数据表 | 画布 900×880，信号类别图例（3 个色块）落在画布下方被裁掉；build 的提示写成 “right edge 216 > w 900”（实际是底边越界），模型判为脚本误报；pixcheck 报“节点颜色无同色图例”也被当成误报；对照表仍写 pass | 图例自动放到图下方两栏：关系类型 7 项 + “Signal class (Table 1)” 3 项，画布自动扩展，无裁切；修改后图例色块随类别同步变色 |
| 关系语义 | 磷酸转移和合成都用 flow，图例读作 “material / sample flow”；翻译用 step，图例读作 “next step (order)” | `phospho` 8 条（图例 “phosphotransfer (~P)”）、`produce` 7 条（“synthesis / expression”）；推断的 aphA mRNA→AphA 标为 indirect 点线 |
| 字号 | 未报告 pt；按 900 px / 180 mm 换算节点 14 px ≈ 7.4 pt、图例 12 px ≈ 6.3 pt | build 自动放大 ×1.27，报告最小 15.2 px = 5.97 pt（工单 6 pt，容差内）；PNG 4252×4798（600 dpi），PDF 矢量、15 个字体全部嵌入 |
| 修改记录 | diff 列出 2 个标签与 3 个色块的改动 | diff：`content_changes` 5（两个子图的 Qrr 标签、两个 AI-2 节点、图例色块），另列 424 处 `layout_only_changes`（标签变长引起的自动重排）；换行不再算内容改动 |
| check | PASS，0 fail / 8 warn（图例文字超出画布） | PASS，0 fail / 0 warn |

表中 1.3 数字是该次试跑当时的输出。试跑后又把自动节点宽度上限从 210 px 降到 140 px（长标签优先换行，竖向增长不影响 pt），diff 的文字比较改为忽略换行；用同一份 spec 重建：画布 1218×1467 px、文字 ×1.22、最小 6.2 pt，v2 的 `changed_ids` 仍只有上述 5 个。

**1.3 首轮试跑暴露、已修的问题**（同一案例第一次 1.3 试跑）：模型看到“最小字号 5.9 pt”后把两个子图改成竖排，得到 527×2520 px 的细长图且标题被裁。据此：build 改为自动放大全部文字直到达到 `canvas.min_font_pt`，画布宽度计入标题宽度，SKILL 写明“不要为了字号改竖排或删内容”。第二次试跑即上表。

**仍存在的**：第一次 1.3 试跑没注意到 OD600 两处写法不同；第二次把 Qrr 4/5 矛盾只写进了实体清单、没列进 exceptions，说明“读矛盾”仍取决于模型；自动排版是网格式，跨子图对齐靠等宽列，长标签会让其余元素整体平移（diff 里归为布局变化）。
