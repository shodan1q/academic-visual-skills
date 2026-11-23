# academic-talk-content-organizer-lite（学术汇报内容组织，轻量版）

把已有的论文/研究材料，按**汇报目标、听众、时长、页数、模板**组织成可讲的学术 PPT：目标写成可检查的一句话，
取舍表说明每个图表/结论的去向，每页唯一主张并标证据强度，备注写过渡与强调，另附问答准备与备用页指引；
所有论断回到原文位置，交付可编辑 PPTX + PDF/PNG 导出 + 自检结果。

## 适用 / 不适用
- 适用：组会、开题/中期、答辩、基金/项目评审、会议 talk，同一份研究按不同听众重组。
- 不适用：论文精读、学术写作润色、科研绘图素材生产（相邻课题负责）。

## 文件
| 文件 | 作用 |
|---|---|
| `SKILL.md` | 执行流程：目标卡 → 听众画像 → 取舍表 → 叙事大纲 → 问答准备 → 建页导出 → 映射与自检 |
| `scripts/pptx_kit.py` | 纯标准库。`inspect [--full]` 列模板版式/占位符/主题字体颜色/母版字号与已有 deck 每页内容；`build` 在模板上建页：占位符继承、正文进**面积最大**的 body/obj、`source_note` 进来源/注释占位符（没有则页脚上方小字）、图片版式的图注占位符、等比图片、三线表、页脚页码、备注、`keep`/`replace`、溢出与 `min_pt` 字号 WARN、每页打印 `placed` 行；正文不写字号时用模板字号、放不下才自动降到能放下的最大字号；宽图/宽表自动排成上图满宽、下方要点，表格按内容选字号与列宽；`**粗体**`、`X_{2}` 下标、`cm^{-1}` 上标；小图 WARN；`paper` 输出论文地图（各节标题、双栏安全的全部图表题注+页码、每页位图数）；`figcrop` 按题注裁图、去白边、题注不进图片（题注在页上可编辑），题注在图上方也能裁，PDF 里没有该图时报 WARN；`render` 调 LibreOffice（两次尝试、各限 120 s）出 PDF + 100 dpi PNG + pdffonts，并写 `render.json`，找不到渲染器也不报错 |
| `scripts/check_result.py` | 纯标准库。`--init` 写骨架 result.json；查 contract 字段/status/文件、页数、提示文字、备注、PDF 页数、渲染丢字；`--template` 逐字节比对母版版式主题；`--paper` 查只在旧 deck 出现的数字、图号与论文题注内容不符（`--preserved` 页只报 WARN）；图片拉伸、`--min-pt` 字号、缺页码、散装文本框、build.log 未处理 WARN；写 `slide_audit.md` 逐页偏差记录；`--assemble` 读 facts.json 与磁盘文件，按含义填满 contract 的每个键（任意键名/中文/嵌套），缺文件跳过；`--baseline v0.pptx --keep-map 新:旧 --edit-map 新:旧` 比对保留页、逐页写改前/改后到 `version_diff.md`；最后把逐项判定（`by: check_result.py`）和 `checker_record` 写回 result.json 的合规列表；双栏论文右栏题注不再误报；`--paper-advisory` 把论文不一致降为建议；没有渲染器且 status=partial 时渲染类问题降为 WARN |
| `resources/checklist.md` | 目标/听众/取舍/证据强度/问答/模板导出的逐项核对 |
| `resources/pptx_xml.md` | 无 python-pptx 时的 zipfile/XML 字符串编辑配方与导出核对命令 |
| `examples/README.md` | 合成最小示例（标注"示例"） |
| `benchmark/EVALUATION.md` | 设计理由与内部自测记录（内部合成案例） |

## 依赖
Python 3.8+ 标准库（必需）；poppler、LibreOffice、tesseract、qpdf 可选并自动探测，缺失时降级并在结果中说明。不需要 python-pptx。
路径可用 `CASE_JSON / WORK_DIR / OUT_DIR / SKILL_DIR` 覆盖；运行时安装在 `/skills/weekly-skill`。

## 输出
`presentation.pptx`、`presentation.pdf`、`preview/*.png`、`talk_plan.md`（目标、听众、时长分配、证据强度、取舍表）、`plan.md`、
`qa_prep.md`、`content_map.json`、`change_log.md`、`spec.json`、`result.json`。

## 限制
- 听众画像和追问是基于材料与场合的推断，写成"假设"，需要汇报人确认。
- 证据强度三级（强/中/弱）是粗分，判据写在 SKILL.md；不做统计再分析。
- 版面检查依赖文本信号（溢出估算、渲染后文字比对），不能代替人眼。

## 维护
版本 1.3（2026-11；脚本与 06/08/09 共用同一份合并版）。改脚本后按 examples/README.md 的流程回归：build 无 WARN、render 产出 PDF/PNG（或照实记录失败）、checker PASS。
