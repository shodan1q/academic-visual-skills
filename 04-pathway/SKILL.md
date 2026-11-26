---
name: bio-pathway-figure-lite
description: 把机制材料（原始论文 PDF、figure 工单 figure-workorder.json、数据表）画成或改成可逐条核对的生物机制图/信号通路图。两条命令完成：start 读材料并给出带行号的原文段落，build 把一份“每行一个实体/关系”的文本规格变成全部交付物。实体带类型与区室（基因斜体、复合物八角框、受体跨在膜带上），布局自动（自上而下、连线横平竖直、反馈环走外侧），相互作用语义与证据强度分开编码，节点颜色从 CSV 计算并自动生成图例，交付分层可编辑 SVG + JSON 规格 + 真实 PNG/PDF + 像素自检 + 每个来源指针回填原文引句与页码 + 工单逐条对照 + 源文件级修改记录 + result.json。标准库脚本，无安装。不用于：统计计算、艺术插画、论文写作。
---

# 生物机制图与通路图（精简版）

版本 lite-1.7。`$S` = 本 Skill 目录（`/skills/weekly-skill`）。输入 `/input`，工作目录 `/app/work`，交付 `/app/output`（环境变量 `CASE_JSON`/`WORK_DIR`/`OUT_DIR` 存在时优先）。

## 必做的三步（3–5 次调用就有完整交付物；先交付，再改进）

**① 读材料（1 次调用）**
```
python3 $S/scripts/run.py start
```
一次输出：输入文件清单与 sha256、case.json、工单全文、任务修订说明、论文文本（PDF 已转成 `/app/work/src.txt`，每行带行号；长论文只印提到工单术语的段落 + 术语行号索引）、数据表列名与行、并写好一份如实标 partial 的 result.json。不要再单独 `cat` 这些文件。只有当某条关系的原句没印出来时，才 `sed -n '120,160p' /app/work/src.txt` 补读（最多 2 次）。

**② 写规格并出图（1 次调用，写文件和 build 放在同一条命令里）**
```
mkdir -p /app/work && cat > /app/work/figure.txt <<'EOF'
title: <图题，来自材料> @1
species: mouse
color: tableS2.csv | gene_symbol | log2FC_6h | auto | log2FC, 6 h (Table S2)
comp ex: Extracellular space @27
comp pm: Plasma membrane @27
comp cy: Cytosol @35
comp ly in cy: Lysosome @37
comp nu: Nucleus @57
node ins: Insulin | protein | ex @27
node insr: INSR | protein | pm | mods=P @28
node akt: AKT | protein | cy | alias=AKT2 @31
node tsc: TSC1/TSC2 | complex | ly @36
node foxo1c: FOXO1 | protein | cy | mods=P @58
node foxo1n: FOXO1 | protein | nu @57
node pck1: Pck1 | gene | nu @57
edge ins -o insr | bind @27
edge insr -> akt | activate | via IRS1-PI3K @28-31
edge akt -| tsc | inhibit | +P T1462 @36
edge akt -> foxo1c | modify | +P S256 @58
edge foxo1n -> foxo1c | transport | nuclear export @58-59
edge foxo1n -> pck1 | activate | transcription @57
edge tsc -| foxo1n | inhibit | overexpression only | indirect @60
note: Schematic, not to scale. Gene colour = log2FC (Table S2). @64
req: <工单要求原文一项> | pass | pm,insr,e-akt-tsc | <怎么满足 + 行号>
exc: undecidable | <原文没说清的点 + 行号> | <图上怎么处理>
edit insr | label=INSR (p-Tyr) | dash
summary: <一句话：画了什么，多少实体/关系>
EOF
python3 $S/scripts/run.py build /app/work/figure.txt
```
build 一条命令做完：自动布局出 `figure.svg`（图例自动生成：用到的关系类型、证据线型、实体图元、颜色分档，输出里有一行 `legend drawn automatically` 列出各项）→ 真实 PNG + PDF → 像素自检 → 按 `edit` 行生成 `figure_v2.*` 和 `edit_diff.json` → 组装 `result.json`（填满 output_contract 每个字段，状态如实）并自检。每一步有时限，哪一步失败都记录在 result.json 里并继续下一步。宽度 mm / dpi / 最小字号自动取工单的值，不用写。

**③ 看 build 的输出，只改点名的事实性问题（0–2 次调用）**：`edge … unknown node`、`line N not understood`、`no src for …`、`source trace: … cited lines do not name …`（行号不准）、`NOT in the source text`（名字拼错或材料里没有）——改 `figure.txt` 对应行后重跑同一条 build。版面类 WARN（标签压线等）不用管，已自动记入 exceptions。**重跑最多 2 次；时间不够就停在当前版本，它已经是完整交付。**

## 规格写法（每行一项，`|` 分隔；`@12` 或 `@12-15` 写在行尾 = 该项出自 src.txt 的哪几行）
- `comp ID: 标题`，按自上而下顺序写：胞外 → 质膜 → 胞质 → 核。细胞器写 `comp er in cy: ER`。标题含 membrane/膜 的画成脂双层带，nucleus 画双层核膜。
- `node ID: 显示名 | kind | 区室ID`，可加 `mods=P`（或 Ub/Ac/Me，画成角标）、`alias=旧名,同义名`、`data=数据表键`。kind：gene / mrna / protein / complex / family / small_molecule / ion / cell / process。
- `edge A -> B | type | 标签 | indirect 或 hypothesis`；箭头写法 `->` 激活、`-|` 抑制、`-o` 结合、`--` 仅相关；反馈边可加 `| feedback`。边的 id 自动为 `e-A-B`。
- `color: 文件 | 键列 | 数值列 | auto | 图例标题`：节点颜色由脚本读表计算；分档断点写 `auto`（按上图节点的数据范围取，零附近为灰）或自己给 `-2,-0.5,0.5,2`；kind 为 gene/mrna 且显示名等于键值的节点自动上色，其余节点要上色就写 `data=键`。不手挑数据色。
- `req: 要求 | pass/partial/fail | 元素id,… | 证据`：工单每项要求一行（区室、关系类型、反馈/分支、命名、数据上色、修改请求）。不写的话脚本把工单各项列为“未逐项评估”，状态为 partial。
- `exc: 类别 | 细节 | 处置`，类别：undecidable / contradiction / material_missing / run_failure / user_request_not_in_source。
- `edit ID或显示名 | label=新名 | dash | stroke=#hex | fill=#hex | remove`：工单有修改请求就逐条写成 edit 行（坐标固定、其余 id 不变）；没有修改请求时不写，脚本自动做一次标明“演示、不属于正式图”的编辑来证明源文件可改。
- 也接受 JSON 规格（`canvas/panels/nodes/edges` + 可选 `checks/exceptions/edits`），格式见 README。

## 机制规则（读者会逐条核对，写规格时过一遍）
| 材料措辞 | type | 图形 |
|---|---|---|
| 激活、促进、诱导、上调、转录诱导、表达 | activate | 实线实心箭头 |
| 抑制、阻断、降解、拮抗 | inhibit | 实线 T 端 |
| 结合、募集、形成复合物 | bind | 圆点端 |
| 磷酸化/泛素化等修饰（效应未说明） | modify | 空心箭头 + 标签 “+P S388” |
| 入核、出核、跨膜转位、分泌 | transport | 虚线箭头，只连**同一实体的两个区室副本** |
| 只说“相关”、无方向 | line | 无端点 |
- 方向 = 因果方向：“A 被 B 抑制”写 `B -| A`。修饰且效应已说明（泛素化→降解）按效应用 inhibit/activate，标签写 “+Ub, degradation”。
- 证据强度与 type 分开：原文说“仅过表达观察到 / 可能间接”→ 加 `indirect`（点线）；“未检验 / 推测”→ `hypothesis`（点划线）。不把间接画成实线。原文明确说未检验、未纳入模型的分支不画，写进 exc。
- 同一分子在两个区室（胞质与核的 IRF3、ER 与 Golgi 的 STING）写两个 node，显示名相同、ID 不同，用 transport 相连。
- 基因与蛋白分开建节点：人 基因 *TP53*（gene）/ 蛋白 p53；小鼠 基因 *Pck1* / 蛋白全大写。同义名、旧名只进 `alias`。复合物一个节点，标签写全成员（“IFNAR1/IFNAR2”）。
- 跨膜受体的区室是膜带；配体在胞外；转录因子入核后再 `-> 基因 | activate | transcription`；基因到蛋白用 `activate | expression`。
- 图上不出现材料里没有的分子、位点、数值；位点只写原文给出的。正文与数据表矛盾：颜色按数据表，两处原文写进 `exc: contradiction`。
- 节点超过 25 个时把非核心分支合并为一个节点并在 alias 里列出成员。

## 输出与状态
`/app/output`：`figure.svg`（分层、每个元素有 id 和来源）、`figure.png`、`figure.pdf`、`figure_spec.json` + `figure_spec_lines.txt`（规格）、`figure_resolved_spec.json`（排好的坐标）、`figure_content_map.json`（实体/关系/图例/数据映射 + 原文引句与页码）、`figure_pixel_check.json`、`figure_v2.*` + `edit_diff.json`、`export_log.jsonl`、`source_text.txt`、`result.json`。
status 只有一个词：SVG+PNG+PDF 齐全且每条 req 为 pass → complete（原文没说清的地方已按证据强度画出并写进 exc，属于如实交付）；有 req 为 partial/fail、缺导出格式或材料读不了 → partial；没出图 → failed。脚本按文件实际情况判定，不能靠手写改成 complete。

## 异常处理
| 情况 | 处置 |
|---|---|
| start 提示 PDF 无法提取文字 | 只画工单/数据表里写明的内容，`exc: material_missing`，不凭记忆补 |
| 方向或作用类型原文没写清 | `--`（line）或加 `hypothesis`，`exc: undecidable` |
| 修改请求引入材料没有的内容 | 照做，`exc: user_request_not_in_source` |
| 渲染器缺失 | 自动退到内置渲染（matplotlib → 标准库矢量 PDF）；仍无 PNG 时记 run_failure、状态 partial，不重试、不伪造 |
| build 报 FAIL | 按提示改那一行重跑；规格里无法解析的行会被跳过并点名，不会中断 |

不做的事：不编造实体、关系、位点、数值或来源；不把间接画成实线；不只交位图；不伪造渲染、检查或人工确认。
