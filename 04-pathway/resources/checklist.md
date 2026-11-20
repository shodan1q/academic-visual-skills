# 交付前自检清单（机制图 / 通路图）

运行 `python3 $S/scripts/export_check.py check` 得到 PASS 后，再逐条人工核对（在 result.json 的 export_checks 或 run_notes 里写结论）：

## 科学内容
- [ ] er.md 每个实体都在图上，图上每个节点都在 er.md 里（不多不少）；节点 `src` 指向文件:行。
- [ ] 基因斜体、蛋白正体；物种大小写规则一致；复合物与成员、家族与成员没有混画。
- [ ] 每条边的 type 与材料措辞一致（激活/抑制/结合/修饰/转运/间接）；方向是“上游 → 下游”；“被 X 抑制”画成 X ⊣ 目标。
- [ ] 推测、未检验、间接的关系用 indirect（点线），没有被画成实线。
- [ ] 区室顺序与材料一致；跨膜蛋白在膜条上；入核/分泌等跨区室过程用 transport。
- [ ] 图上所有数值（log2FC、倍数、p 值、浓度、时间）都能在数据文件找到行列，单位正确。

## 图例与编码
- [ ] 用到的每种边类型、每种填充色都在图例中；图例没有图上不存在的项。
- [ ] 颜色编码数据时，图例写清分档/数值和单位；色盲友好；灰度下靠线型/端点仍可区分。

## 版式与导出
- [ ] build 无 WARN（无缺 src、溢出、穿节点、无图例）。
- [ ] figure.png（300 dpi）与 figure.pdf（矢量、字体嵌入）存在且来自 render；export_log.jsonl 有记录。
- [ ] 最小字号 ≥ 9 px（画布宽 1000–1400 px 时）；中文标签有 CJK 字体。
- [ ] 图上无内部 id、文件名、行号、TODO、占位文字。

## 可编辑性与记录
- [ ] figure_spec.json 与 figure.svg 都在 /app/output；SVG 分层（layer-panels / edges / nodes / data / text / legend），文字是 `<text>`。
- [ ] 修改请求（或演示编辑）是在源文件上完成的：diff 只显示预期改动，kept_ids 接近全部；新版本也已渲染。
- [ ] result.json：case_id、所有 contract 字段、status 一个词、status_reasons、uncertainties、material_gaps、needs_human_confirmation 都已填写。
