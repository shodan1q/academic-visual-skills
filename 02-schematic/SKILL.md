---
name: sci-schematic-editable-lite
description: 把来源材料（原始论文 PDF、figure 工单 figure-workorder.json、数据表、研究/流程/结构描述）画成或改成科研示意图——实验流程图、结构/层级关系图、概念或机制链条图。两条命令完成：start 读材料并给出带行号的原文段落，build 把一份“每行一个分组/实体/关系”的文本规格变成全部交付物。关系按语法画（包含=嵌套分区、并列=同行、上下游/时序=箭头方向、因果=激活/抑制、推测=点划线），排版全自动，分类颜色从数据表读取并自动生成图例；交付分层可编辑 SVG（每个元素 id + 来源）+ JSON 规格 + 真实 PNG/PDF + 像素自检 + 内容映射（来源指针回填原文引句与页码）+ 工单逐条对照 + 源文件级修改记录 + result.json。标准库脚本，无安装。不用于：统计图表数值计算、海报/封面美化、艺术插画、正文写作。
---

# 科研示意图生成与编辑（精简版）

版本 lite-1.6。`$S` = 本 Skill 目录（`/skills/weekly-skill`）。输入 `/input`，工作目录 `/app/work`，交付 `/app/output`（环境变量 `CASE_JSON`/`WORK_DIR`/`OUT_DIR` 存在时优先）。

## 必做的三步（3–5 次调用就有完整交付物；先交付，再改进）

**① 读材料（1 次调用）**
```
python3 $S/scripts/run.py start
```
一次输出：输入文件清单与 sha256、case.json、工单全文、任务修订说明、论文文本（PDF 已转成 `/app/work/src.txt`，每行带行号；长论文只印提到工单术语的段落 + 术语行号索引）、数据表列名与行，并写好一份如实标 partial 的 result.json。不要再单独 `cat` 这些文件。只有某条关系的原句没印出来时，才 `sed -n '120,160p' /app/work/src.txt` 补读（最多 2 次）。

**② 写规格并出图（1 次调用，写文件和 build 放在同一条命令里）**
```
mkdir -p /app/work && cat > /app/work/figure.txt <<'EOF_SPEC'
title: <图题，来自工单/材料> @1
color: table1.csv | <名称列> | <类别列> | <图例标题，如 Functional class (Table 1)>
group a: a  <子图 a 标题> @40
group a-out in a: <外层分区，如 Cytosol> @23
group a-mem in a: <膜/边界分区，如 OMM> | membrane @23
group b: b  <子图 b 标题：流程> @52
node k1: <实体名，与原文写法一致> | protein | a-out @26
node s1: <底物> | protein | a-mem @27
node x1: <推测因子> | protein | a-out @41
node w1: 1 <步骤一，含原文条件 10 uM, 2 h> | step | b @53
node w2: 2 <步骤二> | step | b @54
node w3: 3 <读出/数据> | data | b @55
edge k1 -> s1 | phospho | Ser65 @31
edge x1 -| s1 | inhibit | hypothesis @41-42
edge w1 -> w2 | step @53-54
edge w2 -> w3 | flow | <物料名> @55
note: * <矛盾或只进脚注的信息，两处原文都引> @30
req: <工单 must_show 原文一项> | pass | a-out,a-mem,k1 | <怎么满足 + 行号>
exc: contradiction | <正文 L30 写 10 uM，方法 L85 写 20 uM> | <图上怎么处理>
edit <节点显示名或 id> | label=<新名>
edit <类别名> | fill=#D55E00
summary: <一句话：画了什么，多少实体/关系>
EOF_SPEC
python3 $S/scripts/run.py build /app/work/figure.txt
```
build 一条命令做完：自动排版出 `figure.svg`（分区嵌套、子图并排或叠放、字号按工单宽度与最小 pt 自动调，图例自动生成：用到的关系类型、证据线型、数据类别）→ 真实 PNG + PDF → 像素自检 → `figure_source_map.md`（每个元素 → 行号 + 原文引句）→ 按 `edit` 行生成 `figure_v2.*` 和 `edit_diff.json` → 组装 `result.json`（填满 output_contract 每个字段，状态如实）并自检。每一步有时限，哪一步失败都记录在 result.json 里并继续下一步。宽度 mm / dpi / 最小字号自动取工单的值，不用写；工单要 TIFF/EPS/JPEG 时自动从真实 PNG/PDF 转出，转不了就如实记为缺失。

**③ 看 build 的输出，只改点名的事实性问题（0–2 次调用）**：`unknown node`、`line N not understood`、`no src for …`、`edge type not given, guessed`、`transport joins different entities`、`source trace: … cited lines do not name …`（行号不准）、`NOT in the source text`（名字拼错或材料里没有）、`color line not usable`——改 `figure.txt` 对应行后重跑同一条 build。版面类 WARN（标签压线、图偏高等）不用管，已自动记入 exceptions。**重跑最多 2 次；时间不够就停在当前版本，它已经是完整交付。**

## 规格写法（每行一项，`|` 分隔；行尾 `@12` 或 `@12-15` = 该项出自 src.txt 的哪几行，数据表写 `@table1.csv`）
- `group ID: 标题`：分组/分区/子图。嵌套写 `group 子ID in 父ID: 标题`（包含关系就靠嵌套表达）。子图标题以 `a `、`b ` 开头。膜、边界层加 `| membrane`；计划中/未实现/未验证的分组或节点加 `| dashed=<原因，如 planned, not implemented>`（虚线框 + 自动脚注）。可选 `| row`、`| col`、`| cols=3` 指定组内排法；不写时自动（流程链自动蛇形排）。按阅读顺序写：上游/外层在前。
- `node ID: 显示名 | kind | 分组ID`：kind 任选 protein gene mrna complex small_molecule cell cell_type tissue organ organism sample material reagent condition instrument step process data concept（gene/mrna 自动斜体）。可加 `shape=diamond|ellipse|round`、`fill=#hex`、`alias=旧名,同义名`、`data=数据表键`。同一实体在两个子图/分区里各写一个 node（ID 不同、显示名相同）。流程步骤的显示名前加序号 `1 …`。
- `edge A -> B | type | 标签 | indirect 或 hypothesis`：type 见下表；`->` 有向、`-|` 抑制、`-o` 结合、`--` 无向、`<->` 双向。两端也可以是分组 ID（指向整组）。标签 ≤ 3 个词（位点、条件、物料名），细节进 note。
- `color: 文件 | 键列 | 类别列 | 图例标题 | 类别=#hex,…`：节点颜色由脚本读表决定，一类一色（色盲友好），图例与表逐类一致；显示名等于键值的节点自动上色，其余写 `data=键`。没有数据着色就不写。手工底色要配一行 `key: #hex | 含义`。
- `req: 要求原文 | pass/partial/fail | 元素id,… | 证据`：工单 must_show / 要求**每项一行**；pass 只写图上真能看到的。不写的话各项被列为“未逐项评估”，状态为 partial。
- `exc: 类别 | 细节 | 处置`，类别：contradiction / undecidable / material_missing / run_failure / user_request_not_in_source。
- `edit 目标 | label=新名 | fill=#hex | stroke=#hex | remove`：工单的修改请求逐条写成 edit 行；目标可以是节点 ID、显示名或数据类别名（改类别色，图例同步；撞色时脚本自动换开并记录）。没有修改请求时不写，脚本自动做一次标明“演示、不属于正式图”的编辑来证明源文件可改。
- `note:` 图下脚注；`caption:` 图注；也接受 JSON 规格（`canvas/panels/nodes/edges` + `checks/exceptions/edits`，见 README）。

## 关系语法（结构画错比画丑更致命，写规格时过一遍）
| 材料里的关系 | 写法 |
|---|---|
| 包含 / 位于 / 组成（细胞⊃膜；平台⊃模块） | `group 子 in 父` 嵌套，节点写所属分组；**不用箭头表示包含** |
| 并列 / 同级 / 分组比较 | 放同一分组，不连箭头；两个状态（处理/对照、野生型/突变）画成结构相同的子图 a/b |
| 上下游 / 流程 / 时序 | `step`，方向 = 先后顺序，步骤带序号 |
| 物料、样本、分子沿路径移动（经过别的部件） | `flow`，标签写物料名或原文动词 |
| 同一实体换位置（入核、转位、分泌） | `transport`，只连**同一实体的两个副本** |
| 激活、促进、诱导、招募 | `activate`；抑制、阻断、降解、去除 → `inhibit`（“A 被 B 抑制”写 `B -| A`） |
| 磷酸化 | `phospho`（标签写位点）；其他修饰（泛素化、切割）`modify`；合成/转录/表达 `produce` |
| 结合、形成复合物 | `bind`；只说相关、无方向 → `line`；分泌因子/信号 → `signal` |
| 推测、未检验、仅间接证据 | 在同一条边后加 `| hypothesis` 或 `| indirect`（点划线/点线，图例自动说明）；**不画成实线**，原文明确排除的分支不画、写进 exc |
- 只画材料里有的实体、位点、数值、单位，写法与原文一致；数值单位原样照抄。工单要求而原文没有的，照工单画并写 `exc: user_request_not_in_source`。
- 同一参数在摘要/结果/方法里说法不一致（剂量、时间、数量）：按结果或数据表画，加 `note: *…` 脚注并写 `exc: contradiction`，两处行号都给。
- 范围由工单定：must_show 的每一项都有对应元素；工单没要求的不硬塞。节点多于 25 个时合并非核心分支。

## 输出与状态
`/app/output`：`figure.svg`（分层、每个元素有 id 和 data-src）、`figure.png`、`figure.pdf`、`figure_spec.json` + `figure_spec_lines.txt`（可编辑规格）、`figure_content_map.json`、`figure_source_map.md`、`figure_pixel_check.json`、`figure_v2.*` + `figure_spec_v2.json` + `edit_diff.json`、`export_log.jsonl`、`source_text.txt`、`result.json`。
status 只有一个词：SVG+PNG+PDF 齐全且每条 req 为 pass → complete（已如实写进 exc 的矛盾与未决点不影响）；有 req 为 partial/fail、缺导出格式或材料读不了 → partial；没出图 → failed。脚本按文件实际情况判定，不能靠手写改成 complete。

## 异常处理
| 情况 | 处置 |
|---|---|
| start 提示 PDF 无法提取文字 | 只画工单/数据表里写明的内容，`exc: material_missing`，不凭记忆补 |
| 方向或类型原文没写清 | `--`（line）或加 `hypothesis`，`exc: undecidable` |
| 数据表类别与正文对不上 | 颜色和图例按数据表，`exc: contradiction` |
| 修改请求引入材料没有的内容 | 照做，`exc: user_request_not_in_source` |
| 渲染器缺失 / 某种要求的格式转不出 | 自动退到内置渲染；仍缺的格式由脚本记 run_failure、状态 partial，不重试、不伪造；CMYK 等做不到的要求写一条 `exc: run_failure` |
| build 报 FAIL 或某行被跳过 | 按提示改那一行重跑；无法解析的行只会被跳过并点名，不会中断 |

不做的事：不编造实体、关系、数值或来源；不把推测画成确定；不用箭头表示包含；不只交位图；不伪造渲染、检查或人工确认。
