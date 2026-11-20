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
| `scripts/pptx_kit.py` | 纯标准库：`inspect` 模板版式/占位符；`build` 按 spec 在模板上建页（占位符继承、备注、图片、三线表、页脚页码、保留原页、溢出估算、包完整性检查）；`figcrop` 按题注裁图 |
| `scripts/check_result.py` | 纯标准库：contract 字段/status/文件；页数、提示文字残留、备注缺失或复述、PDF 页数、渲染后文字丢失、数字回查原文、证据映射覆盖、模板未被改动 |
| `resources/checklist.md` | 目标/听众/取舍/证据强度/问答/模板导出的逐项核对 |
| `resources/pptx_xml.md` | 无 python-pptx 时的 zipfile/XML 字符串编辑配方与导出核对命令 |
| `examples/README.md` | 合成最小示例（标注"示例"） |
| `benchmark/EVALUATION.md` | 设计理由与内部自测记录（无正式评分） |

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
版本 1.0（2026-11）。改脚本后按 examples/README.md 的流程回归：build 无 WARN、soffice 能导出、checker PASS。
