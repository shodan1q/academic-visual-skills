# academic-pptx-template-adapter-lite（学术 PPT 模板与格式适配，轻量版）

把旧模板的 deck（或论文/提纲内容）迁到指定模板：母版、版式、主题原样继承，每页内容写进正确版式的占位符，
字号遵守模板阶梯，图片等比放入容器，整册页脚页码一致，导出 PDF/PNG，并用逐字节比对证明"真的套用了模板"。

## 适用 / 不适用
- 适用：换会议/单位模板、旧 deck 统一版式、论文内容按模板成稿、批量修正页脚页码与字号层级。
- 不适用：改写论文内容、科研绘图美化、语言润色、需要修改模板本身的设计工作。

## 文件
| 文件 | 作用 |
|---|---|
| `SKILL.md` | 读模板结构 → 逐页版式映射 → spec 构建 → 导出 → 批量一致性与模板继承核对 |
| `scripts/pptx_kit.py` | 纯标准库：`inspect [--full]` 列模板版式/占位符/主题字体颜色/母版字号，列旧 deck 每页按角色的文字、表格行、图片、备注；`build` 按 spec 在目标模板上建页（占位符继承、不写字体颜色、等比图片、三线表、页脚页码、备注、溢出估算、包完整性）；`figcrop` 从论文 PDF 裁图 |
| `scripts/check_result.py` | 纯标准库：contract 字段/status/文件；页数、提示文字残留、备注、PDF 页数、渲染后文字丢失、数字回查、证据映射覆盖；`--template` 逐字节比对母版/版式/主题并检查每页版式来源与散装文本框 |
| `resources/checklist.md` | 模板套用/字号/图表/批量一致性/导出逐项核对 |
| `resources/pptx_xml.md` | 无 python-pptx 时的 zipfile/XML 字符串编辑配方（命名空间安全）与导出核对命令 |
| `examples/README.md` | 合成最小示例（标注"示例"） |
| `benchmark/EVALUATION.md` | 设计理由与内部自测记录（无正式评分） |

## 依赖
Python 3.8+ 标准库（必需）；LibreOffice（导出）、poppler（pdftoppm/pdffonts/pdftotext）可选并自动探测。不需要 python-pptx。
路径可用 `CASE_JSON / WORK_DIR / OUT_DIR / SKILL_DIR` 覆盖；运行时安装在 `/skills/weekly-skill`。

## 输出
`presentation.pptx`、`presentation.pdf`、`preview/*.png`、`template_spec.md`、`layout_map.md`、`content_map.json`（逐页迁移映射）、
`change_log.md`、`spec.json`（复跑源）、`result.json`。

## 限制
- 图表对象（chart）、SmartArt、动画不迁移：转为图片或原生表格并记录。
- 溢出检测是字符宽度估算 + 渲染后文字比对，重叠类问题需要人眼复核 PNG。
- 不修复模板本身的问题（缺版式、缺字体），只报告。

## 维护
版本 1.0（2026-11）。改脚本后按 examples/README.md 回归：build 无 WARN、soffice 导出、checker（含 `--template`）PASS。
