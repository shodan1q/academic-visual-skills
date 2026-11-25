# paper-to-academic-pptx-lite（论文转学术 PPT，轻量版）

把一篇论文（PDF/文本）在**给定模板**里变成可讲、可核验、可编辑的学术 PPT：主线按论文自身贡献重建，一页一个主张，
每页挂到原文的图/表/章节/页码，讲稿备注与页面分离，导出 PDF/PNG 并逐项自检。

**单一来源**：Agent 只写一个 `spec.json`（主线、每页内容、证据定位与原文短引、时长、异常）；PPTX、页级证据映射 `content_map.json`、
页级大纲 `plan.md`、修改记录 `change_log.md` 都由 `build` 从它生成，所以页面和记录不会对不上。

## 适用 / 不适用
- 适用：组会、开题、答辩、会议报告；输入是论文 PDF + 模板 .pptx/.potx（可选工作单 slide-workorder.json、页数/时长/听众）。
- 不适用：论文精读结论生成、科研绘图美化、语言润色、没有原文只凭标题做 PPT。

## 文件
| 文件 | 作用 |
|---|---|
| `SKILL.md` | Agent 执行流程、内容规则、result.json 映射、异常处理 |
| `scripts/pptx_kit.py` | 纯标准库。`paper` 写 paper.txt（保留版面）和 paper_flow.txt（阅读顺序，双栏不串行）并列出页数、节标题、**全部图表题注+页码**（双栏右栏也能找到）、每页位图数（0 = 矢量图）；`inspect [--full]` 列模板版式/占位符/主题字体颜色/母版字号与已有 deck 每页内容；`build` 在模板上建页：占位符继承、正文进**面积最大**的 body/obj、`source_note` 进来源/注释占位符（没有则页脚上方小字）、图片版式的图注占位符、等比图片、三线表、页脚页码、备注、`keep`/`replace`、溢出与 `min_pt` 字号 WARN、每页打印 `placed` 行；`figcrop` 按题注裁图、自动去白边、图注不进图片（打印题注原文，放到页上做可编辑文字）；宽图/宽表配要点时自动排成上图满宽、下方要点；表格按内容分配列宽并自动选字号（≥ 14）；正文在模板字号放不下时自动降到能放下的最大字号（不低于 `min_pt`）；图在页上太小时 WARN；`build` 另外写出 content_map.json（证据短引在论文文本中的核对结果、每个数字出现的论文页码）、plan.md、change_log.md、合并后的 spec.json；单位指数自动上标（cm-2）、`formulas` 列出的化学式自动下标；两/三行标题在短语边界断行；图下要点字号按剩余空间取；spec 语法错时指出行号；版式名不存在时按页面角色选最接近的版式；`render` 调 LibreOffice（两次尝试、各限 120 s）出 PDF + PNG + pdffonts，并写 `render.json`，找不到渲染器也不报错 |
| `scripts/check_result.py` | 纯标准库。`--init` 写骨架 result.json；查 contract 字段/status/文件、页数、提示文字、备注、PDF 页数、渲染丢字；`--template` 逐字节比对母版版式主题；`--paper` 查只在旧 deck 出现的数字、图号与论文题注内容不符（双栏右栏题注也索引；正文提到但没解析到题注只报 WARN）、只在 [n] 引用旁出现的文献数值未标出处（WARN）（`--preserved` 页只报 WARN）；图片拉伸、`--min-pt` 字号、缺页码、散装文本框、build.log 未处理 WARN；写 `slide_audit.md` 逐页偏差记录；`--assemble` 读 facts.json 与磁盘文件，按含义填满 contract 的每个键（任意键名/中文/嵌套），缺文件跳过；`--baseline v0.pptx --keep-map 新:旧` 比对保留页并写 `version_diff.md`；`--paper-advisory` 把论文不一致降为建议；没有渲染器且 status=partial 时渲染类问题降为 WARN |
| `resources/checklist.md` | 交付前逐项核对表 |
| `resources/pptx_xml.md` | 不用 python-pptx 的 zipfile/XML 字符串编辑配方（命名空间安全）、导出与核对命令 |
| `examples/README.md` | 一个合成的最小调用示例（标注"示例"） |
| `benchmark/EVALUATION.md` | 设计理由与内部自测记录（内部合成案例） |

## 依赖
- 必需：Python 3.8+ 标准库。
- 可选（自动探测，缺了就降级并在结果中说明）：poppler（pdftotext / pdftoppm / pdfimages / pdffonts / pdfinfo）、LibreOffice `soffice`（导出 PDF）、
  tesseract（扫描件 OCR）、qpdf（加密 PDF）。不需要 python-pptx、PIL、matplotlib。
- 安装位置：运行时 `/skills/weekly-skill`；路径都可用 `CASE_JSON / WORK_DIR / OUT_DIR / SKILL_DIR` 环境变量覆盖。

## 调用
```bash
K=/skills/weekly-skill/scripts/pptx_kit.py
python3 $K inspect /input/target-template.pptx
python3 $K paper /input/paper.pdf /app/work           # paper.txt + 节标题 + 全部题注与页码
python3 $K figcrop /input/paper.pdf 5 "Figure 3" /app/work/fig3.png   # 去白边，图注不进图片
python3 $K build /app/work/spec.json            # spec 格式：python3 $K 不带参数即打印；同时写 content_map.json / plan.md / change_log.md
python3 $K render $OUT_DIR/presentation.pptx      # PDF + preview PNG + pdffonts + render.json；无 LibreOffice 时照实记录
python3 $SKILL_DIR/scripts/check_result.py --assemble      # 读 $WORK_DIR/facts.json + 磁盘文件，按含义填满 contract 每个键
python3 /skills/weekly-skill/scripts/check_result.py --paper /app/work/paper.txt --min-pt 18 --template /input/target-template.pptx --slides 8
```

## 输出
`presentation.pptx`、`presentation.pdf`、`preview/*.png`、`content_map.json`（页级证据映射）、`plan.md`（页级大纲+时长）、
`change_log.md`、`spec.json`（复跑源）、`result.json`（含 case_id 与 contract 全部字段）。

## 限制
- 证据短引核对是文本匹配：`verbatim` = 规范化后逐字出现；`words found` = 同一页上词都在但换行/分栏不同；扫描件或公式里的内容查不到。
- 单位上标只认常见单位（cm、m、s、h、g、mol、L、V、K 等）后的 -1…-9 和面积/体积的 2、3；其他上下标要写 `^{}`/`_{}`，`"auto_units": false` 可关闭。
- 溢出检测是字符宽度估算，加上渲染后文字比对兜底；不能代替人眼看版面。
- figcrop 依赖题注定位，复杂多栏/跨页图可能裁不准，打印裁剪区文字供核对；失败时改用原生表格或文字并列入 exceptions。
- 图号与内容的对照靠题注词重叠，中文页面引用英文题注时查不出"Table 1 写成了 Table 2 的内容"，需要人看。
- 只处理 .pptx/.potx；Keynote、Google Slides 需先导出为 pptx。
- 不改母版/版式/主题；模板本身有问题（缺版式、字体缺失）只报告不修。

## 维护
版本 1.4（2026-11）。问题与改进：在提交仓库提 issue。改 `pptx_kit.py` 后用 examples/README.md 的流程回归一次，确保 build 输出
"package integrity OK"、render 产出 PDF/PNG（或照实记录失败）、checker PASS。
