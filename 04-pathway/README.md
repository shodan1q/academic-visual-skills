# bio-pathway-figure-lite：生物机制图与通路图（精简版，lite-1.7）

## 用途
把原始论文、figure 工单和数据表变成一张**可逐条质疑**的机制图/通路图，并能在源文件上按要求修改。

- 每个实体带类型（基因/mRNA/蛋白/复合物/家族/小分子…）、所在区室和来源行；每条关系带作用类型（激活、抑制、结合、修饰、转运、无向关联）和**独立的证据强度**（直接/间接/假设）。
- 布局由脚本算：区室自上而下（细胞器是胞质里的子框），区室内按因果顺序分行，连线横平竖直，反馈边走外侧通道；字号、线宽按期刊宽度保证最小 pt。
- 图元：膜=脂双层带（受体跨在带上），核=双层核膜；基因=直角框+启动子箭头+斜体，蛋白=圆角框，复合物=八角框，小分子=椭圆；修饰状态是角标。箭头端点是普通多边形，任何渲染器都画得出。
- 节点颜色由脚本读 CSV 计算，图例（关系、证据线型、图元、颜色分档、“no data”）自动生成，和图面同源。
- 两条命令出全部交付物：分层 SVG + JSON 规格 + 真实 PNG/PDF + 像素自检 + 内容映射（每个来源指针回填原文引句与页码）+ 工单逐条对照 + 修改 diff + result.json。

不负责：统计分析、实验设计、论文写作、艺术插画。

## 文件
| 路径 | 作用 |
|---|---|
| `SKILL.md` | 运行时说明：必做三步、规格写法、机制规则、状态与异常处理 |
| `scripts/run.py` | `start`：一次读完输入（清单+sha256、case.json、工单、PDF→带行号文本、术语相关段落、数据表）并写如实的 partial 骨架；`build`：行式规格（或 JSON 规格）→ 出图 → 导出 → 像素自检 → 修改版 + diff → result.json，每步限时、失败不中断 |
| `scripts/svgfig.py` | `build` JSON 规格 → 自动布局 → 分层 SVG + `*_content_map.json` + `*_resolved_spec.json`；`edit` 改单个元素；`diff` 元素级改动记录 |
| `scripts/export_check.py` | `render` SVG → PNG/PDF（rsvg-convert → cairosvg → inkscape → chrome → magick → soffice → 内置渲染），写 `export_log.jsonl`；`assemble` 按任意 contract 字段名填满 result.json；`check` 自检；`skeleton`、`tools` |
| `scripts/pixcheck.py` | 解码渲染后的 PNG（纯标准库）：图不空、节点填色按声明渲染、标签可见、每种节点颜色在图例里有色块。只给提示 |
| `resources/checklist.md`、`examples/README.md`、`benchmark/EVALUATION.md` | 人工核对清单；最小调用示例（合成数据）；设计理由与内部执行记录 |

## 依赖与安装
Python 3.8+ 标准库，无需安装。可选工具自动探测：`pdftotext`（无则 fitz / pypdf）、任一 SVG 渲染器（都没有时用内置渲染：有 matplotlib 出 PNG+PDF，否则只出标准库矢量 PDF 并如实记录缺 PNG）。

## 调用
```bash
export S=/skills/weekly-skill        # 本地测试另设 CASE_JSON / WORK_DIR / OUT_DIR
python3 $S/scripts/run.py start                      # 读材料
python3 $S/scripts/run.py build /app/work/figure.txt # 规格 → 全部交付物（改规格后重跑同一条）
```
单步命令（调试或接入别的流程时用）：`svgfig.py build spec.json figure.svg`、`export_check.py render figure.svg --dpi 300`、`pixcheck.py figure.svg`、`svgfig.py edit in.svg out.svg <id>-label --text "新标签"`、`svgfig.py diff a.svg b.svg`、`export_check.py assemble notes.json`（notes：status_reasons / compliance_checks / exceptions / edit_request）。

## 规格
行式规格见 SKILL.md。JSON 规格（`build` 也接受；`run.py build x.json` 时可带 `checks`、`exceptions`、`edits:[{"id":…,"label":…}]`）：
键名见 `svgfig.py` 文件头：`canvas{width_mm,min_font_pt,title,colorscale}`、`panels[{id,title,in}]`、`nodes[{id,label,kind,comp,mods,data,aliases,src}]`、`edges[{id,from,to,type,evidence,label,src}]`、`texts`。
其他键：节点 `shape`/`fill`/`stroke`/`dash`/`col`/`rank`，边 `feedback`/`both`/`width`；手写坐标（cx/cy、via）仍支持。写法有出入会被归一，认不出的逐条 WARN。

## 方法要点
1. 图是“实体—关系表”的渲染：content_map 直接由规格生成；`src` 指针由脚本解析成原文引句 + PDF 页码，并核对节点名是否出现在所引行。
2. 作用类型与证据强度是两个独立维度（端点/颜色 vs 线型）；transport 只表示同一实体换区室。
3. 数据颜色从 CSV 读并自动进图例，再由 pixcheck 在像素层面比对；修改从排好坐标的规格出发，diff 只显示真实改动。
4. 状态由文件实际情况判定：缺导出格式、有未满足的工单项即 partial。

## 限制
- 自动布局是启发式的：> 25 个节点或多条反馈时仍有边交叉和长绕线，可用 `col`/`rank`/`feedback` 提示。
- 文字宽度按字符估算；内置回退渲染只覆盖本 Skill 产生的 SVG 子集；没有任何渲染器且没有 matplotlib 时没有 PNG。
- 不判断机制在生物学上是否成立，只保证与材料一致、证据强度可见；读不到 PDF 里原图的像素。
- start 的段落挑选按工单术语打分，可能漏掉用别名叙述的句子：用术语行号索引和 `sed -n` 补读。

## 维护
lite-1.7（2026-11）：新增 `run.py`（两条命令、行式规格、限时分步、先交付后改进）；来源核对对希腊字母与撇号写法不敏感；渲染器时限可用 `EC_TOOL_T` 调整。历史见 `benchmark/EVALUATION.md`。
