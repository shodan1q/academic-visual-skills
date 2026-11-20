# 交付前逐项核对（论文转学术 PPT）

每项写进 result.json 的 compliance_checks：`{"check": ..., "result": "PASS|FAIL|WARN|未核对", "basis": "实测依据"}`。

## A. 主线（与论文自身贡献一致）
- [ ] storyline.md 的贡献句能在 Abstract / Introduction / Conclusion 找到原句（写页码）
- [ ] 页序是 问题 → 方法 → 证据 → 结论/局限，不是章节顺序逐段搬运
- [ ] 每组关键证据都有自己的页；支撑性细节放备注或合并
- [ ] 局限页存在，内容来自原文的 Limitations / Discussion，不是自己推测
- [ ] 他人工作（引用 [n] 的数）没有出现在本文结果页，或明确标"[n] 报道"

## B. 页结构
- [ ] 页数符合工作单（"exactly N" = 正好 N 页；checker `--slides N`）
- [ ] 结果页标题是结论句，不是 "Results"/"实验结果"
- [ ] 每页正文 ≤ 5 条要点、≤ 2 级；build 无溢出 WARN（或已写明原因）
- [ ] 每页时长写在 plan.md，合计 ≈ 规定时长

## C. 图表与数字
- [ ] 页面上的每个图/表编号都在 paper.txt 的题注列表里，子图字母正确
- [ ] 原图用 figcrop/pdfimages 取得，裁剪区文字是坐标轴/图例/题注，不是正文段落
- [ ] 表格是原生表格，数值逐格与原文一致，表头有单位
- [ ] 示意图没被当作实验数据讲；没有重画/编造的曲线
- [ ] checker 的数字回查：小数全部在原文出现；整数警告逐个确认

## D. 备注
- [ ] 每页都有备注（2–4 句：过渡、强调、追问时的补充证据位置、时长）
- [ ] 备注不复述页面（checker 无 "notes mostly repeat" 警告）

## E. 模板与导出
- [ ] checker `--template`：母版/版式/主题逐字节未改，所有页都用模板版式
- [ ] 模板样例页已删除（或按工作单保留），没有 "单击此处添加" 等提示文字
- [ ] 页脚/页码沿用模板占位符
- [ ] presentation.pdf 页数 = 幻灯片数；preview PNG 存在
- [ ] pdffonts 实测字体写进渲染记录；中文字体被替代时照实写
- [ ] spec.json 在交付目录，复跑命令写在 editable_source

## F. 结果文件
- [ ] contract 每个字段都有实质内容；status 是一个词
- [ ] exceptions 把"材料缺失 / 无法判断 / 运行失败"分开列
- [ ] check_result.py PASS
