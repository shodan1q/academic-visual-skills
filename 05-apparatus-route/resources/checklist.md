# 交付前自检清单（实验装置图 / 流程图 / 技术路线图）

`python3 $S/scripts/export_check.py fill` 回填、`check` 得到 PASS（最多两轮；改不掉的 FAIL 写进 status_reasons、status partial）后，再逐条人工核对，结论写进 result.json 的 export_checks / run_notes：

## 部件与连接
- [ ] ir.md 部件表中每个部件都在图上（名称、数量与材料一致，同类部件分别编号）；图上没有多出的部件。
- [ ] 每条连接都能在材料里找到（文件:行）；材料没写的连接没有画，已列入 material_gaps。
- [ ] 流向箭头与介质流动方向一致；分流/合流/回流/废料出口都有，没有断头箭头。
- [ ] 介质 → 颜色/线型固定：液体蓝实线、气体绿、热/能量橙红、电/信号橙虚线、回流/废料灰；参数带单位、照抄。

## 步骤与路线
- [ ] 步骤编号与正文逐条对应；并行支路并排（3a/3b）；循环有回到起点的边和次数/条件；判断用菱形并标出“是/否”。
- [ ] 技术路线：阶段从左到右，目标 → 方法 → 输出/里程碑；依赖箭头从前序输出指向后续方法；并列研究内容不加箭头。
- [ ] 没有写材料中不存在的时间、样本量、指标。

## 图例与版式
- [ ] 每种边类型/颜色、部件类别色都在图例中，且没有多余项。
- [ ] build 无 WARN（缺 src、溢出、穿部件、via 点在节点内、无图例）；check 无越界、重叠、小字号告警。
- [ ] 字号 ≥ 12 px；中文有 CJK 字体；图上无内部 id、文件名、行号、TODO。

## 导出与可编辑性
- [ ] figure_spec.json + 分层 figure.svg + figure.png（300 dpi）+ figure.pdf（矢量、字体嵌入）+ export_log.jsonl；两张图各自齐全。
- [ ] 修改（或演示编辑）在源上完成，diff 只含预期改动，新版本已渲染，change_log 已写。
- [ ] result.json：case_id、全部 contract 字段、status 一个词、status_reasons、uncertainties、material_gaps、needs_human_confirmation。
