# sci-schematic-editable-lite：科研示意图生成与编辑（精简版，lite-1.6）

## 用途
把原始论文、figure 工单和数据表变成一张**每个元素都能回查原文**的示意图（实验流程图、结构/层级图、概念或机制链条图），并能在源文件上按要求修改。

- 图是“分组—实体—关系表”的渲染：包含关系用嵌套分区表达，并列用同行，流程/因果用带类型的箭头，推测用点划线或虚线框；作用类型（颜色+端点）与证据强度（线型）是两个独立维度。
- 排版由脚本算：分区嵌套、子图并排或叠放、流程链（含带一个旁支的链）蛇形排、同组节点自动换位以减少连线交叉（编号步骤保持书写顺序）、边标签避让、图例和脚注放在图下，画布自动扩展；字号按工单宽度（mm）和最小 pt 自动调。
- 分类颜色由脚本读 CSV 决定（一类一色，色盲友好），图例与数据表逐类一致；改类别色时图例和节点同步，撞色自动换开并记录。
- 箭头、T 形端、圆点端都是普通多边形/线段，不用 SVG marker，任何渲染器（含只有 ImageMagick 的环境）都画得出方向。
- 两条命令出全部交付物：分层 SVG + 规格 + 真实 PNG/PDF（工单要 TIFF/EPS/JPEG 时一并转出）+ 像素自检 + 内容映射与来源表（来源指针回填原文引句与页码）+ 工单逐条对照 + 修改 diff + result.json。

不负责：统计图表的数值计算、海报/封面美化、艺术插画、正文写作。

## 文件
| 路径 | 作用 |
|---|---|
| `SKILL.md` | 运行时说明：必做三步、规格写法、关系语法、状态与异常处理 |
| `scripts/run.py` | `start`：一次读完输入（清单+sha256、case.json、工单、PDF→带行号文本、术语相关段落、数据表）并写如实的 partial 骨架；`build`：行式规格（或 JSON 规格）→ 出图 → 导出 → 像素自检 → 来源表 → 修改版 + diff → result.json，每步限时、失败不中断 |
| `scripts/svgfig.py` | `build` JSON 规格 → 自动排版 → 分层 SVG + `*_content_map.json`；`edit` 改单个元素；`diff` 元素级改动记录（内容改动与重排坐标分开统计） |
| `scripts/export_check.py` | `render` SVG → PNG/PDF（rsvg-convert → cairosvg → inkscape → chrome → magick → soffice → 内置渲染），写 `export_log.jsonl`；`assemble` 按任意 contract 字段名填满 result.json；`check` 自检；`skeleton`、`tools` |
| `scripts/pixcheck.py` | 解码渲染后的 PNG（纯标准库）：图不空、节点填色按声明渲染、标签可见、箭头端点和分区标题真的在图里、每种节点颜色在图例里有色块。只给提示 |
| `resources/checklist.md`、`examples/README.md`、`benchmark/EVALUATION.md` | 人工核对清单；最小调用示例（合成数据）；设计理由与内部执行记录 |

## 依赖与安装
Python 3.8+ 标准库，无需安装。可选工具自动探测：`pdftotext`（无则 fitz / pypdf）、任一 SVG 渲染器（都没有时用内置渲染：有 matplotlib 出 PNG+PDF，否则只出标准库矢量 PDF 并如实记录缺 PNG）。字体：SVG 的 font-family 依次为 Arial / Helvetica / Noto Sans CJK SC / 思源黑体 / 文泉驿 / 系统无衬线，文字保持可选可改；环境缺中文字体时像素自检会提示标签不可见，改用英文标签或记为异常。

## 调用
```bash
export S=/skills/weekly-skill        # 本地测试另设 CASE_JSON / WORK_DIR / OUT_DIR
python3 $S/scripts/run.py start                      # 读材料
python3 $S/scripts/run.py build /app/work/figure.txt # 规格 → 全部交付物（改规格后重跑同一条）
```
单步命令（调试或接入别的流程时用）：`svgfig.py build spec.json figure.svg`、`export_check.py render figure.svg --dpi 300`、`pixcheck.py figure.svg`、`svgfig.py edit in.svg out.svg <id>-label --text "新标签"`、`svgfig.py diff a.svg b.svg`、`export_check.py assemble notes.json`（notes：status_reasons / compliance_checks / exceptions / edit_request）。

## 规格
行式规格见 SKILL.md 和 `examples/README.md`。JSON 规格（`run.py build x.json` 也接受，可带 `checks`、`exceptions`、`edits:[{"id":…,"label":…}]`）：`canvas{width_mm,min_font_pt,title,categories{csv,key,column,colors,title}}`、`panels[{id,title,parent,layout,cols,fill,dash,src}]`、`nodes[{id,label,kind,comp,shape,fill,data,aliases,dash,src}]`、`edges[{id,from,to,type,evidence,label,both,width,src}]`、`texts[{id,text,src}]`、`legend{title,items[{fill,label}]}`。坐标一律不写（写了的显式坐标 `cx,cy / x,y,w,h` 仍被 svgfig 接受，用于局部微调）。写法有出入会被归一：未知分组、重复 id、未定义节点的边、读不了的颜色表都只产生点名的 WARN，不会中断。

导出参数：宽度 mm、PNG dpi（上限 600）、最小字号 pt 取自工单（缺省 180 mm / 300 dpi / 6 pt）；SVG/PDF 为真实物理宽度；PDF 是否矢量、字体是否嵌入、PNG 像素尺寸记在 result.json 的导出块里。

## 方法要点
1. 先交付再改进：`start` 就写出如实的 partial result.json；一次 `build` 后即为完整交付，之后只修被点名的事实性问题。
2. content_map 直接由规格生成；`@行号` 指针由脚本解析成原文引句 + PDF 页码，并核对节点名是否出现在所引行（`source_trace`）。
3. 修改从规格出发重建 `figure_v2`，`edit_diff.json` 把内容改动（文字、颜色）与自动重排引起的坐标变化分开，元素 id 保持不变。
4. 状态由文件实际情况判定：缺导出格式、有未满足的工单项即 partial；已写明的矛盾与未决点作为 exceptions 如实交付。

## 限制
- 自动排版是启发式的：> 25 个节点或跨分区长连线多时仍会有交叉和标签拥挤；可用 `cols=`、分组顺序或拆子图调整。
- 文字宽度按字符估算；内置回退渲染只覆盖本 Skill 产生的 SVG 子集；没有任何渲染器且没有 matplotlib 时没有 PNG。
- 不判断科学结论是否成立，只保证与材料一致、证据强度可见；读不到 PDF 里位图原图的内容。
- start 的段落挑选按工单术语的匹配程度排序，可能漏掉用别名叙述的句子：用术语行号索引和 `sed -n` 补读。
- CMYK 分色不支持（输出 sRGB），需要时在导出后用专业软件转换并记录。

## 维护
lite-1.6（2026-11）：新增 `run.py`（两条命令、行式规格、限时分步、先交付后改进）；箭头端点为普通图形；虚线框表示计划中/未验证的部件；同组节点换位减少连线交叉；改类别色自动避免撞色；按工单转出 TIFF/EPS/JPEG。历史见 `benchmark/EVALUATION.md`。
