# 设计说明与内部自测记录（内部材料）

> 只记录维护者在本机真实做过的事。案例是自己编写的**合成案例**，不是平台正式案例；没有做"不加载 Skill 的基础 Agent"
> 对照运行，因此不给任何相对基础 Agent 的增益数字，也不推测正式案例结果。

## 1. 依据与设计取舍
- 题包公开的接口说明（dataset 里的 output-contract.md 与 example-input.json）写明：运行时读 case.json、material.json、
  artifacts/slide-workorder.json，正式案例提供真实的 target-template.pptx 与 starting-deck.pptx；交付 `/app/output/presentation.pptx`、
  真实 PDF、计划/主张-来源/时间/修改记录和带全部根字段的 result.json；要读准 mode、总页数、source preservation 与 template inheritance。
  示例 contract 根字段：case_id、status、editable_source、export_artifact、content_map、compliance_checks、exceptions。SKILL.md 按这些名字给了映射。
- "改一页时顺手改坏母版和后面所有页"是本题点名的失败。所以编辑走 **keep 模式**：未点名的页 XML 原样复制，母版/版式/主题不动；
  每轮用 `inspect --full` 生成可读文字快照并 `diff`，改动是否只落在指令点名的页一目了然，也是 compliance_checks 的依据。
- 版本 = spec 文件。回退就是用上一版 spec 重建，结果确定，不依赖撤销历史。
- 文件生成用纯标准库 `pptx_kit.py`（环境不一定有 python-pptx），与 06/07/08 共用同一份代码。

## 2. 规则 → 针对的失败模式
| 题面列出的失败 | 对应做法 |
|---|---|
| 摘要或段落整段塞进文本框 | 编辑规则 1；溢出 WARN 必须清零 |
| 数字抄错或按印象取整，图注与图上标注不符 | 数字回查（论文 + 初始稿文字，小数缺失 = FAIL）；caption 写原文编号 |
| 占位图或凭空曲线 | 有数值才做原生表格，否则用 figcrop 原图，都没有就记 exception |
| 模板字体、配色、页脚被覆盖 | 只用占位符；`--template` 逐字节比对；页脚页码取版式占位符 |
| 改一页改坏母版和后面所有页 | keep 原样复制 + diff 核对；新图片换名，不覆盖保留页的媒体 |
| 导出后字体替换、文字溢出、图片被裁 | PDF 页数检查、渲染后文字比对、pdffonts 实测 |
| 多轮迭代回不到上一版、说不清交付版 | spec_vK + diff + change_log（含回退方式）；交付名固定为工作单要求 |

## 3. 本机自测（2026-11-20，macOS，LibreOffice 26.x，poppler 26.07，无 python-pptx）
| 测试 | 结果 |
|---|---|
| 合成案例 demo-09（edit 模式，5 页初始稿 → 6 页，三条指令 E1–E3，第 1/2/4 页须原样保留），维护者只按 SKILL.md 操作 | 约 16 次调用；diff 只出现 E1–E3 的改动和页码变化；PDF 6 页；checker PASS（模板 14 个部件与初始稿逐字节一致，数字全部回查到论文或初始稿） |
| 第二轮在 v1 上再插入一张图 | 发现新图与保留页图片同名会互相覆盖，已修复为自动换名（kit_s5_0 / kit_s5_1），回归通过 |
| 共用组件反例测试 | 多页、遗留提示文字、改错小数、缺备注、旧模板冒充新模板均被 checker 报出（见 06、08 的记录） |

## 4. 已知局限
- 保留页的备注部件会按原文字重建（文字不变，备注里的格式不保留）。
- 图表对象、SmartArt 只能整页保留，不能在其内部编辑。
- `pptx_kit.py` 约 370 行（inspect/build/figcrop），超过"每个脚本 ≤ 200 行"的内部目标；为单文件零依赖没有再拆。

## 版本 1.1：从 08（模板适配）移植的通用修正（内部记录，未做基础 Agent 对照）
在 08 的合成难例里发现、并在这里同样适用的问题：
- 模板里正文占位符前面还有小占位符（来源/注释）时，旧 kit 把正文塞进第一个 body 占位符 → 正文缩成页脚上方一行小字。现在选面积最大的占位符，每页打印 `placed` 行。
- 有旧 deck 时只拿旧 deck 文字做数字回查，旧 deck 的错数、错图号会被当成"对得上"。现在 `--paper` 单独对论文核对，并能识别"图号与题注内容不符"。
- 字号下限"母版正文 80%"在 32 pt 母版下要求 25.6 pt，与 14 pt 表格、12 pt 图注冲突且无人检查。改为字号阶梯（正文 ≥ 工作单下限或 18 pt，表格 ≥ 14，图注 14，出处 11–12）+ `min_pt` / `--min-pt`。
- 新增逐页审计表 `slide_audit.md`、骨架 `--init`、图片拉伸检查、标题溢出估算按 LibreOffice 渲染校准（两行标题不再误报）；修正 `placeholders` 键被当成占位文字的误报。

复测（2026-11-20，本机 LibreOffice 26.2，只按本包 SKILL.md 操作）：rt09：edit 模式，模板 = 初始稿；保留 1–5、8–9 页，E1 把 9 条要点页拆成两页，E2 重写稳定性页（初始稿 96% → 论文 94%）；保留页 5 的 "Fig. 3" 图号错误、22% 拉伸图与 14 pt 图注按保留要求不改，checker 以 `--preserved` 报 WARN 并写进 exceptions.undecidable。结果：result.json 字段齐全，PDF/PNG 页数与幻灯片数一致，checker PASS（剩余 WARN：封面标题按模板 44 pt 折成 3 行，已写进 uncertainty；保留页的问题如上）。

## 版本 1.2：运行稳健性（内部记录，未做基础 Agent 对照）
针对四类会让运行时 Agent 交出残缺结果的情况：
- result.json 按固定键名组装，而 contract 用了别的键名 → 骨架文字残留、checker FAIL。现在 `check_result.py --assemble` 按键名与描述的含义映射（中英文、嵌套子字段、JSON schema / 列表 / 字典三种 contract 写法都在合成用例上试过）。
- 可选文件缺失导致组装脚本崩溃 → assemble 对每个文件做存在判断，缺了就跳过。
- 为清掉无法满足的 WARN 反复重建 → SKILL 规定 WARN 只是提示，最多重建 2 轮，剩下的写进 uncertainty。
- 没有渲染器 → `pptx_kit.py render` 自动探测、两次尝试、限时，失败写 render.json；status=partial 时 checker 把渲染类问题降为 WARN。
- 编辑任务专项：旧版对账规则让编辑页"以论文为准"，会产生指令之外的改动。现在只有指令要求核对事实、或该页按指令从论文重写时才更正，其余写成"建议更正（未执行）"；checker `--paper-advisory` 把论文不一致降为 WARN 清单。保留页由 `--baseline/--keep-map` 逐页比对文字，结果写 `version_diff.md`。
- 复测 rt09：E2 页按指令从论文重写（94%）；保留页 5 的 "Fig. 3" 图号问题只出现在建议清单与 exceptions.undecidable；version_diff.md 7 个保留页全部 identical；checker PASS。

## 版本 1.3：把"可复核"做到交付物里（内部记录，未做基础 Agent 对照）
合成案例 SIM09（`benchmark/sim09_case.json`：16:9 母版带主题色条，10 页组会稿 → 10 页评审稿，7 条指令 E1–E7：压缩、换图、段落改要点、
插 Table 2、核对 5–7 页数字图号、调序删页、结论页改中文；初始稿埋了 96%（论文 94.0%）、"Fig. 3" 错标、94% 取整三处问题）。
维护者只按 SKILL.md 操作，1.2 与 1.3 两次运行步骤相同（约 20 次调用）。两次都 checker PASS、页数 10、母版 14 个部件逐字节一致、保留页 1/2/4/9 文字一致。
差别全在复核者打开的东西上：

| 交付物 | 1.2 | 1.3 |
|---|---|---|
| result.json 的 compliance_checks | 2 行（"能打开""有 PDF"）；checker 的判定只打印在终端 | 18 行：11 行 checker 实测（页数、模板逐字节、保留页、数字回查、图表号对题注、备注、导出、字号…）+ 7 行逐条指令；另有 `checker_record`（命令原文、全部 WARN/FAIL 原文、时间） |
| version_diff.md | 每页一行"identical / new or edited" | 每个改动页列改前/改后行（- / +），点名被删页（"10: Acknowledgements"）；`--edit-map` 给定新旧页对应，没给时按词重叠 + 位置一对一匹配 |
| 换图页（论文 Fig. 3） | 裁图含整页宽白边和论文题注，幻灯片上题注出现两遍；曲线约占页面高度 44% | 只裁图本身（白边去掉、题注不进图片），曲线约占页面高度 56%（面积约 1.6 倍），题注一次 |
| 预览 PNG | 667×375（50 dpi），坐标轴数字难辨 | 1334×750（100 dpi） |
| 改前版本 | 只有 v0 文字快照 | 另交 `versions/v0_before.pdf`，可与 presentation.pdf 逐页对照 |

埋入错误的检出（把未改的初始稿当成交付物跑 checker `--paper`）：s6 的 96、s5 的 "Fig. 3" 错标、s8 的 94（论文 94.0）三处全部报 FAIL；
改后版本三处都消失（E5 范围内的按指令更正，s8 在 E7 重写时用论文值）。另报出 s3/s8 主题式标题与 s7/s10 缺备注。
未解决：LibreOffice 在中英混排处加的字间距偏大（替代字体所致，PowerPoint 打开正常与否未验证）；封面 "2026" 不在论文里，按保留页只报 WARN。
共用脚本改动（与 06/07/08 同源，接口向后兼容）：figcrop 去白边/题注、`_{}`/`^{}` 下标上标、render 100 dpi、checker 写回判定行、`--edit-map`。

## 版本 1.4：把流程压成三条命令（内部记录，未做基础 Agent 对照）
动机：运行条件是 64 次请求、900 s。1.3 的流程在维护者手里约 20 次调用，其中读输入 5–6 次、构建后出 diff 2 次、渲染/复制/组装/自检 5–6 次，
都是固定动作；任何一步漏掉（没复制成稿、没跑 assemble、checker 没最后跑），交付目录里就只剩骨架 result.json。SKILL.md 第 9 步是一整段长文。

改动：新增 `scripts/deck_flow.py`（start / build / finish，只调用原有两个脚本）；SKILL.md 改写为 6 步快速路径 + spec 模板 + facts 模板。

同一合成案例 SIM09（`benchmark/sim09_case.json`），同一份 plan/spec/facts，Linux x86_64 + LibreOffice 24.2.7 + poppler 24.02 上运行：

| 项目 | 1.3 | 1.4 |
|---|---|---|
| 工具调用次数（维护者按 SKILL.md 操作） | 约 20 | 6（start、figcrop、写 plan+spec、build、写 facts、finish） |
| 第一份可交付 pptx 出现在输出目录 | 第 8 步（定稿）之后 | 第一次 build 结束时；之后每次 build 覆盖，构建失败不覆盖 |
| 初始稿里埋的三处错误（96%、"Fig. 3" 错标、94% 取整） | 需要按第 4 步手工逐个 grep 对账 | start 的预检直接列出三处（另有封面 "2026" 一条非论文数字） |
| 脚本单步耗时 | — | start 0.3 s，build < 1 s，finish 约 6 s（两次 LibreOffice 导出） |
| 成稿与各项记录 | checker PASS，10 页，保留页 1/2/4/9 一致 | 相同（pptx 由同一 spec 生成）；另自动交付 time_record.json、versions/v0.txt、v0_before_preview/*.png、precheck.md |
| 没写 change_log.md | 交付物里缺这一份 | finish 按 instructions_done 起草（含每条的回退方式和版本列表） |
| checker 报 FAIL 而没有后续调用 | result.json 仍写 complete | finish 把 status 改为 partial，status_reasons 写 FAIL 原文 |

退化情况（均实测）：`SOFFICE=none` → 交付 pptx 与全部文字记录，status=partial，run_failures 写明无渲染器；没有 facts.json → 仍组装出全部 contract 字段并提示；
未 build 就 finish → 返回提示，骨架保留；spec 写错（keep 超出页数）→ 构建失败不覆盖已交付版本；没有初始稿也没有工作单（generate）→ 以 target-template 为模板，
编造的小数（77.7%）在数字回查中 FAIL，status 自动降为 partial。
未验证：平台实际运行环境中的 LibreOffice 版本与耗时；finish 给渲染留的时间按 900 s 总预算估算（`RUN_BUDGET_S` 可调）。

## 版本 1.5：原位编辑与由文件算出来的修改记录（内部记录，未做基础 Agent 对照）
动机：1.4 里"压缩/改写/换语言"一律按版式重建该页。合成案例 SIM09-B（8 页会议稿；第 3、5 页是"左文右图 + 手工放的高亮文本框"，
工作单写明图、图注和高亮框不许动；5 条指令：第 3 页 6 条压成 3 条并核对数字、第 4 页只换标题、第 5 页只改备注、第 6 页换成 Table 2 + 一行"暂定"、
第 8 页重写结论；初始稿埋了 234 °C（论文 243）和"重复性约 5 °C"（论文 ≤ 3 °C））上，按 1.4 的 SKILL.md 操作会出现：

| 观察点（Linux + LibreOffice 24.2 渲染后逐页看图） | 1.4 | 1.5 |
|---|---|---|
| 第 3 页的高亮框 "ΔT50 = −42 °C" | 重建时丢失；checker 仍 PASS，记录里看不出来 | 原位编辑，保留；记录写明"6 个形状 4 个逐字节相同，改了正文和出处行" |
| 第 3 页的图 | 从论文重新裁了一张放回去（不是原对象） | 原图片对象未动 |
| 第 6 页（表格 + 一行结论） | 表格被挤到右半页，四列全部折行；左半页只有一行字 | 表格占满宽度不折行，结论行排在表格正下方 |
| change_log.md | 7 行，每行的回退方式都是同一句话；没有改前/改后 | 逐页：指令原文、理由、改前/改后文字与备注、形状级范围、针对该页的回退写法；被删页、移动页、没有指令依据的改动单列 |
| result.json 每条指令的 compliance 行 | 只是把作者的话抄一遍，却标 `by: check_result.py` | 作者说法 + 文件对比看到的改动（`file_diff`）；另有 "edit scope" 一行 |
| finish 的参数 | 要手传 `--keep-map/--edit-map`（传错会 FAIL） | 从 spec 的 `keep`/`from` 推出；手传仍然有效 |
| 换图页（SIM09 第 6 页） | 图顶到标题下的红线 | 留 0.08 in 空隙 |

SIM09（10 页，7 条指令）在 1.5 上回归：checker PASS；保留页 1/2/4/9 逐形状相同；中文结论页（原第 8 页）被识别为"原位编辑 + 移动"，第 10 页"致谢"列为被删页并给出回退写法。
退化情况复测：`SOFFICE=none`、没有 facts.json（指令编号从 spec 的 notes 里取，取不到的列为"没有指令依据的改动"）、未 build 就 finish、keep 超出页数、
`set` 的键找不到形状（WARN 并列出该页形状名，其余照常）、generate 模式（没有初始稿 → 写 Build record）。
已知局限：原位编辑沿用被改形状第一段的格式，行内局部格式不保留；组合形状里的文字 `set` 找不到（用 `replace`）；
形状范围只比对内容与位置，不判断"这次改动是否符合指令的意图"——那一栏仍然是作者的说法。
