# 交付前自检清单（数据图表）

`python3 $S/scripts/export_check.py check` 与 `chartkit.py marks` 都 PASS 后，再逐条人工核对，结论写进 result.json 的 annotation_check / export_checks：

## 数据 → 图元
- [ ] 每个图元在 datamap.md 有一行：文件!行列、数值、单位、复算方式；均值/SD/SEM/n 由原始行复算。
- [ ] 汇总表与原始数据不一致的地方已记为冲突，没有悄悄选一个。
- [ ] `chart_marks_expected.csv` 由数据计算得到（不是从图元读出）；`marks` PASS，输出写进 mark_check。
- [ ] 绘图用的数据已复制为 `chart_data.csv` 并注明来源文件/sheet；脚本直接读它。

## 标注
- [ ] 轴标签 = 量 + 单位，量级换算写进单位；刻度覆盖全部数据与误差线；柱状图从 0 开始；对数轴已说明。
- [ ] 图例项 = 系列，名称、数量与数据一致；单系列不放图例。
- [ ] 误差线含义（SD/SEM/CI）写在图注并与数据核对；材料矛盾已列待确认。
- [ ] 显著性符号只用于统计输出里存在的比较，阈值写在图注。
- [ ] n 写明统计单位；基因斜体、物种、化合物名照抄材料。

## 样式与导出
- [ ] STYLE 字典集中了尺寸、字号、配色、dpi、标签；配色色盲友好、灰度可分。
- [ ] SVG 文字可编辑（svg.fonttype none），PDF 字体嵌入（Type 42），PNG 达到要求 dpi；export_log.jsonl 有记录。
- [ ] 中文标签：脚本打印的 CJK 字体不是 NONE，渲染无方框警告。
- [ ] 无遮挡（标签、图例、括线不压数据点）。

## 可编辑性与记录
- [ ] 修改（或演示编辑）通过改 STYLE/数据重跑脚本完成，输出 `chart_v2.*`；`chartkit.py diff` 记录改动；v2 也跑过 marks。
- [ ] result.json：case_id、全部 contract 字段、status 一个词（contract 有 enum 用 enum）、status_reasons、uncertainties、material_gaps、needs_human_confirmation。
