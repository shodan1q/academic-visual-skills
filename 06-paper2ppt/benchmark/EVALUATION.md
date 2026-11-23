# 设计说明与内部自测记录（内部材料）

> 本文件只记录维护者在本机真实做过的事情。所用案例是自己编写的**合成案例**，不是平台正式案例；
> 没有做"不加载 Skill 的基础 Agent"对照运行，因此这里不给任何增益数字，也不推测正式案例上的结果。

## 1. 为什么是"轻量指令 + 两个标准库脚本"
- 上一期经验：依赖重型脚本流水线的 Skill 在官方环境里整题失败；以指令为主、脚本只做确定性工作的版本稳定得多。
- 运行环境是否有 python-pptx 不确定。没有它时，让 Agent 在 64 次调用里从零手写 OOXML 很容易出错（命名空间、rels、notesMaster）。
  所以把**确定性的文件操作**收进一个纯标准库脚本 `pptx_kit.py`，内容取舍、主线、证据映射全部留给 Agent 按 SKILL.md 判断。
- 运行模型可能看不到图片，所以"版面对不对"改由文本信号判断：build 的溢出估算、渲染后 PDF 文字与页面文字比对、
  figcrop 打印裁剪区内文字、checker 的数字回查。

## 2. 规则 → 针对的失败模式
| 题面列出的失败 | 对应做法 |
|---|---|
| 摘要/正文按顺序贴进页面，主线丢失 | 步骤 4 主线卡（贡献以作者原句为准）+ 内容规则 1、2；checklist A |
| 图表编号与正文引用错位、引用不存在的图 | 步骤 3 题注+页码列表；规则 5；content_map 每页 locator |
| 示意图当实验数据、他人结果当本文结果 | 规则 6、步骤 7；content_map 的 visual 字段要写来源类型 |
| 数值与单位在搬运中被改写 | 规则 4；表格逐格抄录成原生表格；checker 数字回查（小数缺失=FAIL） |
| 长句塞进窄框溢出 / 被压成小字 | build 的溢出估算 WARN（必须处理）；规则 3；checker 比对渲染后文字丢失 |
| 模板标题、页脚、配色被覆盖 | 只用版式占位符（位置字号继承）、页脚页码取模板占位符；checker `--template` 逐字节比对母版/版式/主题 |
| 备注缺失或复述页面 | 规则 7；build 打印 NO NOTES；checker 检查缺失与复述 |
| 换机/导出后字体替换、版面崩坏 | 步骤 9 导出 + pdffonts 实测写进记录；PDF 页数=幻灯片数检查 |
| 复跑不出同一版式 | spec.json + build 命令一起交付；build 结果确定（同输入同输出） |

## 3. 本机自测（2026-11-20，macOS，LibreOffice 26.x，poppler 26.07，无 python-pptx）
| 测试 | 结果 |
|---|---|
| inspect 三类模板：PowerPoint 制作的 11 版式中文模板；LibreOffice 导出的设计模板（无 notesMaster）；pptxgenjs 生成的无占位符 deck | 均能列出版式/占位符/主题字体颜色；无 notesMaster 的模板由 build 自动补齐 |
| build：标题页、要点（二级）、加粗、图片+题注（等比、置顶）、三线表+表题、页脚页码 | soffice 导出正常；页码字段渲染为 1..N；包内所有 XML 良构、rels 目标齐全 |
| build keep 模式：保留/重排/删除原页、跨 run 替换、改备注、插入新页 | 页序与页码正确；未命中的替换会报 WARN |
| 溢出估算 | 小占位符模板上对长标题/长段落给出 WARN；正常页无误报 |
| figcrop：按 "Fig. 2" / "Table 1" 裁剪 | 图裁剪正确；表裁剪偏宽、带入一行正文（已知局限，SKILL 让表格优先做原生表格） |
| 合成案例 demo-06（2 页论文，6 页、6 分钟）：维护者只按 SKILL.md 操作 | 约 15 次调用完成；check_result PASS（数字全部回查到原文，模板 14 个部件未改动） |
| checker 反例：多 1 页、遗留 "Click to add text"、把 92.4 改成 92.5、删一页备注 | 4 处问题全部报出（3 FAIL + 备注 WARN），status=complete 时额外 FAIL |
| `resources/pptx_xml.md` 第 2 节 edit_part 配方 | 改文字后 soffice 正常导出，PDF 中可读到改后文字 |

## 4. 已知局限
- 溢出估算按字符宽度近似，不考虑字距与自动换行细节；渲染比对只能发现被裁掉的文字，发现不了重叠。
- figcrop 对双栏论文按栏宽裁剪；跨栏大图、图注在图上方的期刊格式可能需要换写法或手工给页码。
- `pptx_kit.py` 约 370 行（含 inspect/build/figcrop 三个命令），超过"每个脚本 ≤ 200 行"的内部目标；为保持单文件、零依赖没有再拆。

## 版本 1.1：从 08（模板适配）移植的通用修正（内部记录，未做基础 Agent 对照）
在 08 的合成难例里发现、并在这里同样适用的问题：
- 模板里正文占位符前面还有小占位符（来源/注释）时，旧 kit 把正文塞进第一个 body 占位符 → 正文缩成页脚上方一行小字。现在选面积最大的占位符，每页打印 `placed` 行。
- 有旧 deck 时只拿旧 deck 文字做数字回查，旧 deck 的错数、错图号会被当成"对得上"。现在 `--paper` 单独对论文核对，并能识别"图号与题注内容不符"。
- 字号下限"母版正文 80%"在 32 pt 母版下要求 25.6 pt，与 14 pt 表格、12 pt 图注冲突且无人检查。改为字号阶梯（正文 ≥ 工作单下限或 18 pt，表格 ≥ 14，图注 14，出处 11–12）+ `min_pt` / `--min-pt`。
- 新增逐页审计表 `slide_audit.md`、骨架 `--init`、图片拉伸检查、标题溢出估算按 LibreOffice 渲染校准（两行标题不再误报）；修正 `placeholders` 键被当成占位文字的误报。

复测（2026-11-20，本机 LibreOffice 26.2，只按本包 SKILL.md 操作）：rt06：只有论文 + 4:3 自定义模板（PKU-* 版式，正文占位符前面先有一个 12 pt "Source note"），8 页 generate；figcrop 裁 Fig. 3 时带进了正文段落，按 SKILL 改用 pdfimages 取原图。结果：result.json 字段齐全，PDF/PNG 页数与幻灯片数一致，checker PASS（剩余 WARN：封面标题按模板 44 pt 折成 3 行，已写进 uncertainty）。

## 版本 1.2：运行稳健性（内部记录，未做基础 Agent 对照）
针对四类会让运行时 Agent 交出残缺结果的情况：
- result.json 按固定键名组装，而 contract 用了别的键名 → 骨架文字残留、checker FAIL。现在 `check_result.py --assemble` 按键名与描述的含义映射（中英文、嵌套子字段、JSON schema / 列表 / 字典三种 contract 写法都在合成用例上试过）。
- 可选文件缺失导致组装脚本崩溃 → assemble 对每个文件做存在判断，缺了就跳过。
- 为清掉无法满足的 WARN 反复重建 → SKILL 规定 WARN 只是提示，最多重建 2 轮，剩下的写进 uncertainty。
- 没有渲染器 → `pptx_kit.py render` 自动探测、两次尝试、限时，失败写 render.json；status=partial 时 checker 把渲染类问题降为 WARN。
- 主线覆盖：checker 对"Results / Method"这类话题标题和缺失的页型（问题/方法/结果/结论）给 WARN；figcrop 裁进正文时改用 `pdfimages` 取原始位图（rt06 里 Fig. 3 就是这样取的）。
- 复测 rt06：8 页，render 出 PDF/PNG，assemble 后 checker PASS（content_map 没写 role 时报 "method 页型未找到" 的 WARN）。

## 版本 1.3：交付物的可读性（内部记录，未做基础 Agent 对照）
合成案例 r2-06（本机 2026-11-23，LibreOffice 26.2，poppler 26.07）：3 页双栏论文（tectonic 排版），图全是**矢量图**（pdfimages 取不到），
Fig. 1 是示意图，Table 1 的题注在右栏，Table 2 和引言里有文献 [5][7][9] 的数值，补充材料 Fig. S1–S5 被引用但不提供；4:3 PKU 模板、
工作单要求正好 10 页、12 分钟、中文、正文 ≥ 18 pt。按 v1.2 与 v1.3 的 SKILL.md 各做一遍，打开 PDF 逐页看。

| 问题（v1.2 的实际产物） | 原因 | v1.3 做法 | v1.3 实测 |
|---|---|---|---|
| 结果页的图缩成小图：Fig. 2 两面板图在页上的绘图区只有约 4.9×1.8 in，坐标轴字约 6 pt | figcrop 把页眉空白和整段英文图注一起裁进图片；"图片版式"的占位符 6.0×4.5 in，宽图只能缩小 | figcrop 先 72 dpi 探测去白边，图注不进图片（打印出来写到 `caption`）；宽图（宽高比 ≥ 1.45）配要点时 build 排成上图满宽、下方要点；图在页上 < 55% 页宽时 WARN | Fig. 2 / Fig. 3 在页上 8.8–8.9×3.2 in，坐标轴字约 11 pt |
| checker 对正确引用的 Table 1 报 FAIL（"论文里没有这个题注"），status=complete 被拦下 | 题注索引只认行首，双栏 `-layout` 文本里右栏题注在行中间 | 题注索引改为行首或 ≥ 3 个空格之后；论文正文提到但没解析到题注只报 WARN，论文完全没提的编号才 FAIL | 同一 deck：v1.2 checker 4 FAIL，v1.3 checker PASS（Fig. S4/S5 报 WARN：补充材料未提供） |
| 表格 14 pt、等宽列，只占上半页 | 表格字号固定 14，列宽平均分 | 按单元格内容分配列宽，自动取 24→14 pt 中放得下的最大字号；放不下时 WARN 并建议删列/行 | Table 1、Table 2 在页上 24 pt，首列不再挤成两行 |
| 文字页显得空，或 Agent 自行写 font_size 后字很小 | 只有"溢出就 WARN"，没有"放得下就用模板字号"的规则 | 不写 font_size 时正文继承模板字号；估算放不下时自动降到能放下的最大字号（≥ min_pt），在 placed 行注明 auto-fit | 两栏页 28 pt、方法页 32 pt，无溢出 WARN |
| 题注列表漏掉右栏的 Table 1；节标题和页码要自己 grep | 一行 python 只匹配行首 | 新命令 `pptx_kit.py paper`：写 paper.txt，列页数、节标题、全部题注+页码（按 bbox 块，双栏安全）、每页位图数 | 5 个题注全部列出，raster=0 提示用 figcrop |
| 文献值混进本文页没人提醒 | 数字回查只看"论文里有没有这个数" | checker：论文里只在 [n] 旁出现的小数，页上同一行没有 [n]/"报道" 时 WARN | 反例：把 "HCE：CE 99.2% [5]" 删掉 [5] → 报 `s2:99.2` |

v1.3 checker 在同一反例 deck 上还报出：88.8 改成 88.9（FAIL，论文没有这个小数）、引用不存在的 "Fig. 4"（FAIL）。仍查不出的：
中文页把 Table 2 的内容标成 "Table 1"（题注是英文，词重叠对不上），已写进 README 的限制。

调用次数（按 SKILL.md 操作）：v1.2 约 20 次（含为假 FAIL 回头核对 2–3 次）；v1.3 约 13 次（读输入 1、骨架 1、工具+paper 1、读相关段 1、
主线+大纲 1、inspect 1、figcrop 1（三张图一条命令）、build 2、render 1、看 PNG 1、记录+assemble+checker 2）。
回归：rt06 / rt08 / rt09 旧 spec 用 v1.3 kit 重建，keep/replace 与占位符落位不变（差别只在表格字号、auto-fit 与新的小图 WARN），
v1.2 与 v1.3 checker 在三份 deck 上给出相同的 FAIL 集合。
