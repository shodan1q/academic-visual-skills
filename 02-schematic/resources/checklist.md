# 交付前自检清单（科研示意图）

`python3 $S/scripts/export_check.py check` 得到 PASS 后，再逐条人工核对，并把结论写进 result.json 的 export_checks / run_notes：

## 实体与关系
- [ ] er.md 的每个实体都在图上，图上每个元素都在 er.md 里；节点、边、文字都带 `src`。
- [ ] 名称、数量、浓度、时间、单位与材料原文一致，没有新增。
- [ ] 包含关系用嵌套 panel（内层完全在外层内），没有用箭头表示包含；并列元素同行/同列、同尺寸、无箭头。
- [ ] 上下游/时序箭头方向正确、阅读方向单一；步骤序号与材料顺序一致；并行分支画成并排。
- [ ] 促进/抑制/结合/推测分别用 activate / inhibit / bind / indirect；“A 被 B 抑制”画成 B ⊣ A。

## 图例与数据映射
- [ ] 类别数 = 图例色块数，类别名与数据表原文一致；每种边类型也在图例中。
- [ ] 着色由脚本从数据表生成（数据变化可重跑），映射写进 data_mapping。
- [ ] 配色色盲友好，灰度下靠形状/线型仍可区分。

## 版式与导出
- [ ] build 无 WARN；check 无越界、重叠、小字号告警。
- [ ] 期刊尺寸：`width_mm` 已设（如有要求），有效最小字号 ≥ 6–7 pt（计算写进 export_checks）。
- [ ] PNG（300/600 dpi）与 PDF（矢量、字体嵌入）来自 render；要求的 TIFF/EPS 已生成或已记为缺口。
- [ ] 图上无内部 id、文件名、行号、TODO、占位文字；中文有 CJK 字体。

## 可编辑性与记录
- [ ] figure_spec.json 与分层 figure.svg 在 /app/output；文字为 `<text>`。
- [ ] 修改（或演示编辑）在源上完成，diff 只含预期改动，新版本已渲染，change_log 已写。
- [ ] result.json：case_id、全部 contract 字段、status 一个词、status_reasons、uncertainties、material_gaps、needs_human_confirmation。
