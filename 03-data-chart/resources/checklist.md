# 交付前自检清单（数据图表）

`chartkit.py marks`、`pixcheck.py`、`export_check.py check` 都 PASS 后，再逐条核对，结论写进 result.json 的 compliance_checks / exceptions：

## 数据 → 图元
- [ ] `chart_data.csv` 是源数据的原样副本；`data_origin` 指向 /input 原文件，content map 里有两者 sha256。
- [ ] 每个图元在 `chart_content_map.json` 有 x、系列、均值、误差、n、CSV 行号、样本 id；被排除的行有行号与原因。
- [ ] `chart_mark_check.json` 为 PASS，比例尺来自 y 轴刻度（不是拟合）；误差线全长也在对账里。
- [ ] 原文近似数、汇总表与数据复算不一致 → 按数据画，exceptions `contradiction` 写两处出处。

## 标注（出处写进配置 `src`）
- [ ] 轴标签 = 量 + 单位/归一化；柱状图从 0 开始；对数轴在图注说明。
- [ ] 图例项 = 系列，名称与数据取值或原文一致；单系列无图例。
- [ ] `error` 与图注一致（sem / sd / ci95）；图注 n 与可用行数不符已记 exceptions。
- [ ] 显著性只用原文报告的比较与符号，图注写检验方法；未重算 p 值。
- [ ] n 写明统计单位；基因斜体、基因型上标、化合物缩写与全名照原文。

## 样式与导出
- [ ] `chart_pixel_check.json` 无 fails：PNG 宽 = width_mm × dpi，最小字号 ≥ 工单要求，柱色 = 图例色，色盲模拟可分。
- [ ] SVG 文字可编辑（svg.fonttype none），PDF 字体 Type 42；实际字体（可能是替代字体）写进 export_artifact 与 status_reasons。
- [ ] 无遮挡、无裁切（pixcheck 边缘告警已处理）。

## 可编辑性与记录
- [ ] 修改通过 `edit_v2.json` + 重跑完成，`edit_diff.json` 只含预期改动；v2 也跑过 marks 与 pixcheck。
- [ ] result.json：case_id、全部 contract 字段、status 一个词、status_reasons、compliance_checks 覆盖工单每一项（element_ids 真实存在）、exceptions 分类（material_missing / undecidable / contradiction / run_failure / user_request_not_in_source / data_excluded）。
