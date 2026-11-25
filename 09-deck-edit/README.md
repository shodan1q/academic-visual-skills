# academic-pptx-generate-edit-lite（学术 PPT 生成与编辑，轻量版）

按工作单生成或编辑学术演示稿：generate 从论文与模板新建，edit 在初始稿上逐条执行指令（压缩、扩写、换受众/语言、插图表、
调序、删改页）并原样保留未点名的页，只改文字的指令在原页**原位编辑**（同页的图、表、手工文本框不动），adapt 把每页迁到目标模板。
每轮存版本并输出文字差异；修改记录由脚本对比初始稿与成稿逐页、逐形状生成（指令原文、理由、改前/改后、动了哪个形状、如何回退）；
交付原生可编辑 PPTX、真实 PDF 导出、主张-来源映射、时长与修改记录。

## 适用 / 不适用
- 适用：组会/开题/答辩/评审稿的生成与多轮修改；按导师或评审意见改稿；按受众改写；补图表。
- 不适用：论文精读与综述、数据可视化算法、文字润色、PPT 软件开发。

## 文件
| 文件 | 作用 |
|---|---|
| `SKILL.md` | 6 步快速路径：start → （figcrop）→ 写 plan + spec → build → 写 facts → finish；spec 写法、事实更正边界、编辑规则、异常处理 |
| `scripts/deck_flow.py` | 纯标准库，三条命令走完全流程。`start`：找齐输入、写 result.json 骨架、列模板版式与初始稿逐页内容（`v0.txt`/`v0.pptx`）、论文转文字并列题注、**初始稿对论文预检**（`precheck.md`：论文里没有的数字、图表号与题注不符）；`build SPEC`：构建一个版本、存文字快照、输出与 v0 和上一版的 diff、打印 **edit scope**（每个改动页几个形状没动/改了哪个/哪些没带过来，重建弄丢图表或手工文本框时 `SCOPE WARN`）、立刻把 deck/spec/diff 复制进输出目录（构建失败不覆盖上一版）；`finish`：限时渲染成稿与初始稿（`versions/v0_before.pdf`）、复制各项记录、写 `time_record.json`、对比 v0 与成稿写 `change_log.md`（逐页：指令原文、理由、改前/改后文字、形状级范围、回退写法、被删/移动的页；作者自己写的 change_log.md 作为 "Author's log" 放在前面）与 `versions/change_summary.json`、从 spec 推出保留页/改动页对应关系、组装 result.json、最后跑 checker；checker 报 FAIL 时把 status 从 complete 改成 partial 并写明原因。每一步出错都只打印和记录，不中断后续步骤 |
| `scripts/pptx_kit.py` | 纯标准库。`inspect [--full]` 列模板版式/占位符/主题字体颜色/母版字号与已有 deck 每页内容；`build` 在模板上建页：占位符继承、正文进**面积最大**的 body/obj、`source_note` 进来源/注释占位符（没有则页脚上方小字）、图片版式的图注占位符、等比图片、三线表、页脚页码、备注、`keep`/`replace`、**原位编辑** `keep` + `set`（只换一个形状的段落，沿用它自己的段落/字符格式，其余形状逐字节不变）/ `remove` / 在保留页上加图 / 补 `source_note`、表格 + 一两行结论时表格占满宽度、可直接引用 deck 里已有的图片（`ppt/media/...`）、溢出与 `min_pt` 字号 WARN、每页打印 `placed` 行；`figcrop` 按题注裁图（图：题注不进图片、白边自动去掉，打印论文题注原文；PDF 里没有图时明确 WARN）；正文/表格/图注支持 `Al_{2}O_{3}`、`cm^{-1}` 真下标/上标；`render` 调 LibreOffice（两次尝试、各限 120 s）出 PDF + 100 dpi PNG + pdffonts，并写 `render.json`，找不到渲染器也不报错 |
| `scripts/check_result.py` | 纯标准库。`--init` 写骨架 result.json；查 contract 字段/status/文件、页数、提示文字、备注、PDF 页数、渲染丢字；`--template` 逐字节比对母版版式主题；`--paper` 查只在旧 deck 出现的数字、图号与论文题注内容不符（`--preserved` 页只报 WARN）；图片拉伸、`--min-pt` 字号、缺页码、散装文本框、build.log 未处理 WARN；写 `slide_audit.md` 逐页偏差记录；`--assemble` 读 facts.json 与磁盘文件，按含义填满 contract 的每个键（任意键名/中文/嵌套），缺文件跳过；`--baseline v0.pptx --keep-map 新:旧 [--edit-map 新:旧]` 比对保留页，并在 `version_diff.md` 里给每个改动页列改前/改后行（-/+）、列出被删页；最后把自己的判定写回 result.json（compliance 行 `by: check_result.py` + `checker_record`；每条指令一行，附文件对比看到的改动；另有一行 "edit scope"：有没有改动页对不上指令、有没有弄丢初始稿的图/表/文本框）；`--paper-advisory` 把论文不一致降为建议；没有渲染器且 status=partial 时渲染类问题降为 WARN |
| `resources/checklist.md` | 工作单/保留与版本/内容/模板导出/记录逐项核对 |
| `resources/pptx_xml.md` | 无 python-pptx 时的 zipfile/XML 字符串编辑配方（命名空间安全）与导出核对命令 |
| `examples/README.md` | 合成最小示例（标注"示例"） |
| `benchmark/EVALUATION.md` | 设计理由与内部自测记录（内部合成案例，含 1.2 → 1.3、1.3 → 1.4、1.4 → 1.5 前后对比） |
| `benchmark/sim09_case.json` | 可复用的合成编辑题：工作单、初始稿逐页文字、论文事实、埋入的错误和页级金标准（期望每页的动作与必须出现的数字） |

## 依赖
Python 3.8+ 标准库（必需）；LibreOffice（导出 PDF）、poppler（pdftotext/pdftoppm/pdffonts/pdfinfo）、`diff` 可选并自动探测。不需要 python-pptx。
路径可用 `CASE_JSON / WORK_DIR / OUT_DIR / SKILL_DIR` 覆盖；运行时安装在 `/skills/weekly-skill`。

## 输出
`presentation.pptx`、`presentation.pdf`、`preview/*.png`、`content_map.json`、`plan.md`、`change_log.md`、`time_record.json`、
`versions/`（spec_v*.json、diff_v*.txt、v0.pptx 原稿、v0.txt、v0_before.pdf 改前导出、change_summary.json、instructions.json、precheck.md）、`version_diff.md`（逐页改前/改后）、`slide_audit.md`、`result.json`（case_id、status、editable_source、export_artifact、content_map、compliance_checks、exceptions 等 contract 根字段）。

## 限制
- 保留页的 XML 原样复制，唯一改动是页码字段缓存值；备注部件会重建（文字不变）。
- 图表对象/SmartArt 只能原样保留，不能在其内部编辑（同页文字可原位改）。
- 原位编辑沿用被改形状第一段的格式；原段落里的局部加粗、超链接等行内格式不保留。组合形状（group）里的文字要用 `replace`。
- 版面检查靠溢出估算与渲染后文字比对，重叠问题需人眼看 PNG。

## 维护
版本 1.5（2026-11）。1.5：原位编辑（`set`/`remove`/保留页加图/`source_note`）、形状级 edit scope、自动生成的逐页修改记录、finish 不再需要手传新旧页对应。
1.4：新增 `scripts/deck_flow.py`。pptx_kit.py / check_result.py 与 06/07/08 同源，接口向后兼容。
改脚本后按 examples/README.md 回归：build 无 WARN、diff 只含计划内改动、finish 产出 PDF/PNG（或照实记录失败）、checker PASS；
另跑三种退化情况：`SOFFICE=none`（无渲染器 → partial）、没有 facts.json、没有初始稿（generate）。
