# academic-pptx-template-adapter-lite（学术 PPT 模板与格式适配，轻量版）

把旧模板的 deck 或论文内容套进指定模板：母版、版式、主题原样继承；正文进版式里最大的正文占位符，出处进模板的来源/注释占位符；
旧 deck 的数字与图号先和论文对账（以论文为准并记录更正）；字号遵守模板阶梯；图片等比；整册页脚页码一致；
导出 PDF/PNG 后写逐页审计表 `slide_audit.md`，让别人能按记录复跑和逐页核对。

## 适用 / 不适用
- 适用：换会议/单位模板（adapt）、论文按模板成稿（generate）、在原 deck 上小改（edit）、批量修正页脚页码与字号层级。
- 不适用：改写论文结论、科研绘图美化、语言润色、修改模板本身的设计。

## 一次完整流程（论文 + 模板 → pptx + PDF）
```bash
export SKILL_DIR=/skills/weekly-skill WORK_DIR=/app/work OUT_DIR=/app/output CASE_JSON=/input/case.json
K=$SKILL_DIR/scripts/pptx_kit.py; C=$SKILL_DIR/scripts/check_result.py
python3 $C --init                                             # 骨架 result.json（status partial）
python3 $K inspect /input/target-template.pptx                # 版式、占位符(type/idx/英寸/字号)、主题字体颜色、母版字号
pdftotext -layout /input/paper.pdf $WORK_DIR/paper.txt
python3 $K inspect /input/starting-deck.pptx --full > $WORK_DIR/start_text.txt   # 只有 adapt 需要
# 写 corrections.md（deck 对论文）、plan.md（逐页主张与证据）、spec.json
python3 $K build $WORK_DIR/spec.json | tee $WORK_DIR/build.log   # 每页打印 placed 行：内容进了哪个占位符
python3 $K render $OUT_DIR/presentation.pptx      # PDF + preview PNG + pdffonts + render.json；无 LibreOffice 时照实记录
python3 $C --assemble      # 读 $WORK_DIR/facts.json + 磁盘文件，按含义填满 contract 每个键
python3 $C --template /input/target-template.pptx --paper $WORK_DIR/paper.txt --source $WORK_DIR/start_text.txt --slides 10 --min-pt 18
```

## 文件
| 文件 | 作用 |
|---|---|
| `SKILL.md` | 运行时流程：模板结构 → 事实对账 → 页级大纲 → spec 构建 → 导出 → 审计与自检 |
| `scripts/pptx_kit.py` | 纯标准库。`inspect` 列版式/占位符/主题/母版字号与旧 deck 每页内容；`build` 在目标模板上建页（占位符继承、正文选最大占位符、`source_note` 进来源占位符、图注进图片版式的图注占位符、等比图片、三线表、页脚页码、备注、溢出与字号下限 WARN、包完整性）；`figcrop` 按题注从论文 PDF 裁图；`render` 调 LibreOffice（两次尝试、各限 120 s）出 PDF + PNG + pdffonts，并写 `render.json`，找不到渲染器也不报错 |
| `scripts/check_result.py` | 纯标准库。`--init` 写骨架；检查 contract 字段/status/文件/页数/提示文字/备注/PDF 页数/渲染丢字；`--template` 逐字节比对母版版式主题；`--paper` 查"只在旧 deck 出现的数字"和"图号与题注内容不符"；图片拉伸；`--min-pt` 字号下限；缺页码；散装文本框；build.log 未处理的 WARN；写 `slide_audit.md`；`--assemble` 读 facts.json 与磁盘文件，按含义填满 contract 的每个键（任意键名/中文/嵌套），缺文件跳过；`--baseline v0.pptx --keep-map 新:旧` 比对保留页并写 `version_diff.md`；`--paper-advisory` 把论文不一致降为建议；没有渲染器且 status=partial 时渲染类问题降为 WARN |
| `resources/checklist.md` | 交付前逐项核对（对应 compliance_checks） |
| `resources/pptx_xml.md` | kit 做不到时的 zipfile/XML 字符串编辑配方与导出核对命令 |
| `examples/README.md` | 合成最小示例（标注"示例"） |
| `benchmark/EVALUATION.md` | 设计理由、失败模式 → 规则对照、内部合成案例的模拟记录 |

## 参数与约定
- spec 键：`template`、`out`、`footer`、`date`、`slide_numbers`、`min_pt`；每页 `layout`（名字或序号）、`title`、`subtitle`、`body`（两个前导空格=二级）、
  `body2`、`image`、`image_box`、`caption`、`caption_size`、`table`、`table_box`、`table_size`、`source_note`、`ph`（按 idx 指定）、`font_size`、`notes`、`keep`/`replace`。
- 字号阶梯：标题 = 母版标题；正文 ≥ 工作单下限（默认 18 pt）；表格 ≥ 14；图注 14；出处 11–12。
- 导出：LibreOffice `--convert-to pdf`，`-env:UserInstallation` 用独立 profile；`pdffonts` 记录嵌入与替代字体（如 Calibri → Carlito）。

## 依赖
Python 3.8+ 标准库（必需）；LibreOffice（导出）、poppler（pdftotext/pdftoppm/pdffonts）可选并自动探测。不需要 python-pptx。

## 限制
- 图表对象（chart）、SmartArt、动画不迁移：转为图片或原生表格并记录。
- 溢出检测是字符宽度估算（标题宽度按 LibreOffice 渲染校准）+ 渲染后丢字比对；文字压到相邻框上这类问题仍需看 PNG。
- 图号核对依赖论文题注能被 pdftotext 抽出；扫描版论文需要 OCR。
- 不修复模板本身的问题（缺版式、缺字体），只报告。

## 维护
版本 1.2（2026-11）。改脚本后用 examples/README.md 的流程回归：build 的 placed 行正确、无未处理 WARN、render 产出 PDF/PNG（或照实记录失败）、checker（含 `--template --paper`）PASS。
