# academic-pptx-generate-edit-lite（学术 PPT 生成与编辑，轻量版）

按工作单生成或编辑学术演示稿：generate 从论文与模板新建，edit 在初始稿上逐条执行指令（压缩、扩写、换受众/语言、插图表、
调序、删改页）并原样保留未点名的页，adapt 把每页迁到目标模板。每轮存版本并输出文字差异，记录改了什么、为什么、如何回退；
交付原生可编辑 PPTX、真实 PDF 导出、主张-来源映射、时长与修改记录。

## 适用 / 不适用
- 适用：组会/开题/答辩/评审稿的生成与多轮修改；按导师或评审意见改稿；按受众改写；补图表。
- 不适用：论文精读与综述、数据可视化算法、文字润色、PPT 软件开发。

## 文件
| 文件 | 作用 |
|---|---|
| `SKILL.md` | 读工作单 → 页级计划 → 按指令写 spec（keep/replace/新建）→ 每轮构建与 diff → 导出 → 记录与自检 |
| `scripts/pptx_kit.py` | 纯标准库。`inspect [--full]` 列模板版式/占位符/主题字体颜色/母版字号与已有 deck 每页内容；`build` 在模板上建页：占位符继承、正文进**面积最大**的 body/obj、`source_note` 进来源/注释占位符（没有则页脚上方小字）、图片版式的图注占位符、等比图片、三线表、页脚页码、备注、`keep`/`replace`、溢出与 `min_pt` 字号 WARN、每页打印 `placed` 行；`figcrop` 按题注裁图 |
| `scripts/check_result.py` | 纯标准库。`--init` 写骨架 result.json；查 contract 字段/status/文件、页数、提示文字、备注、PDF 页数、渲染丢字；`--template` 逐字节比对母版版式主题；`--paper` 查只在旧 deck 出现的数字、图号与论文题注内容不符（`--preserved` 页只报 WARN）；图片拉伸、`--min-pt` 字号、缺页码、散装文本框、build.log 未处理 WARN；写 `slide_audit.md` 逐页偏差记录 |
| `resources/checklist.md` | 工作单/保留与版本/内容/模板导出/记录逐项核对 |
| `resources/pptx_xml.md` | 无 python-pptx 时的 zipfile/XML 字符串编辑配方（命名空间安全）与导出核对命令 |
| `examples/README.md` | 合成最小示例（标注"示例"） |
| `benchmark/EVALUATION.md` | 设计理由与内部自测记录（内部合成案例） |

## 依赖
Python 3.8+ 标准库（必需）；LibreOffice（导出 PDF）、poppler（pdftotext/pdftoppm/pdffonts/pdfinfo）、`diff` 可选并自动探测。不需要 python-pptx。
路径可用 `CASE_JSON / WORK_DIR / OUT_DIR / SKILL_DIR` 覆盖；运行时安装在 `/skills/weekly-skill`。

## 输出
`presentation.pptx`、`presentation.pdf`、`preview/*.png`、`content_map.json`、`plan.md`、`change_log.md`、`time_record.json`、
`versions/`（spec_v*.json、diff_*.txt）、`result.json`（case_id、status、editable_source、export_artifact、content_map、compliance_checks、exceptions 等 contract 根字段）。

## 限制
- 保留页的 XML 原样复制，唯一改动是页码字段缓存值；备注部件会重建（文字不变）。
- 图表对象/SmartArt 只能原样保留，不能在其内部编辑。
- 版面检查靠溢出估算与渲染后文字比对，重叠问题需人眼看 PNG。

## 维护
版本 1.1（2026-11）。改脚本后按 examples/README.md 回归：build 无 WARN、diff 只含计划内改动、soffice 导出、checker PASS。
