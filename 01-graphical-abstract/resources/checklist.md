# 交付前自检清单（Graphical Abstract）

`python3 $S/scripts/export_check.py check` 得到 PASS 后，再逐条人工核对，并把结论写进 result.json 的 export_checks / run_notes：

## 四要素与主线
- [ ] 四个面板齐全：研究问题、方法/路线、核心结果、结论；序号与阅读方向一致，面板间有主线箭头。
- [ ] panel_map.md 中每个“上图”要点都在图上，每个“只进图注”要点都在 figure_caption.md 里，没有挤上图。
- [ ] 结论措辞强度与证据一致（相关 ≠ 因果，盆栽/细胞 ≠ 田间/人体），限定条件写出。

## 科学实体与关系
- [ ] 实体名称照抄材料（缩写、基因斜体、物种、材料型号），没有凭空加入的实体或图标。
- [ ] 箭头方向 = 因果/流程方向；边类型与材料措辞一致；推测或无数据的环节用点线（indirect）并在图注说明。
- [ ] 层级/空间位置合理（分子在细胞内、样本先处理后测量）；示意未按比例时图注已说明；有比例尺时标了数值和单位。

## 数据编码
- [ ] 每根柱的数值、误差、组名都来自数据文件（文件 + 行列），不是摘要里的近似值；冲突已记录。
- [ ] 回读 SVG 的 data-value 与高度：高度/数值比例在各柱之间一致；结果写进 data_mapping。
- [ ] 柱从 0 开始；单位在标题或标签中；误差含义（SD/SEM/CI）和 n 在图注或图上写明。
- [ ] 颜色色盲友好；灰度下靠标签仍能区分组别。

## 图例与版式
- [ ] 每种边类型、每种填充色、每个数据系列都在图例中，且没有多余项。
- [ ] build 无 WARN；check 无文字越界/重叠；最小字号 ≥ 12 px，标题 20–24 px。
- [ ] 画布尺寸满足任务（默认 1200×700；Elsevier ≥ 1328×531）。

## 导出与可编辑性
- [ ] figure_spec.json + figure.svg（分层、文字为 `<text>`）+ figure.png（300 dpi）+ figure.pdf（矢量、字体嵌入）+ export_log.jsonl。
- [ ] 修改（或演示编辑）在源上完成：新 spec/SVG、diff 只含预期改动、新版本已渲染、change_log 已记录。
- [ ] result.json：case_id、全部 contract 字段、status 一个词、status_reasons、uncertainties、material_gaps、needs_human_confirmation。
