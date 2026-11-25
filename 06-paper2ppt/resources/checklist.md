# 交付前逐项核对（论文转学术 PPT）

每项写进 result.json 的 compliance_checks：`{"check": ..., "result": "PASS|FAIL|WARN|未核对", "basis": "实测依据"}`。

## A. 主线（与论文自身贡献一致）
- [ ] spec.json 的 `storyline`（写进 plan.md）的贡献句能在 Abstract / Introduction / Conclusion 找到原句（写页码）
- [ ] 页序是 问题 → 方法 → 证据 → 结论/局限，不是章节顺序逐段搬运
- [ ] 每组关键证据都有自己的页；支撑性细节放备注或合并
- [ ] 局限页存在，内容来自原文的 Limitations / Discussion，不是自己推测
- [ ] 他人工作（引用 [n] 的数）没有出现在本文结果页，或明确标"[n] 报道"

## B. 页结构
- [ ] 页数符合工作单（"exactly N" = 正好 N 页；checker `--slides N`）
- [ ] 结果页标题是结论句，不是 "Results"/"实验结果"
- [ ] 每页正文 ≤ 5 条要点、≤ 2 级；build 无溢出 WARN（或已写明原因）
- [ ] 标题都在标题占位符内（build 的 placed 行写明了自动适配后的字号；change_log.md 有 "size fit" 记录）
- [ ] 每组关键结果页带原图或原生表格；图在页上足够大（build 无 "figure is only" WARN）
- [ ] 每页 `seconds` 写在 spec（→ plan.md），合计 ≈ 规定时长（build 偏差超过 15% 会提示）

## C. 图表与数字
- [ ] 每页 `evidence` 有定位和原文短引；content_map.json 里的 quote_check 没有 NOT FOUND（或已说明）
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

## 1.1 新增
- [ ] build 的 `placed` 行：正文在面积最大的占位符，出处在 source_note；build.log 的 WARN 已处理或写进 uncertainty
- [ ] 正文 ≥ 字号下限（checker `--min-pt`）；图片比例误差 ≤ 3%（slide_audit.md）
- [ ] checker `--paper` 无 FAIL（有旧 deck 时加 `--source`）；slide_audit.md 已交付并在 result.json 里引用

## 1.3 新增（看 PDF 时逐页核对）
- [ ] 结果页的图占满正文区宽度（build 无 `figure is only ...` WARN），坐标轴字在 PDF 里看得清；图注是页上的可编辑文字，含原文编号和条件
- [ ] 表格只留支撑主张的列/行，主张所在行加粗；build 无表格放不下的 WARN
- [ ] 文字页没有半页空白（要点 3–5 条，或配原文图/表）；没为了"好看"自己写小于模板的 font_size
- [ ] checker 无"[n] 引用旁的数值未标出处"WARN，或已在页上标 "[n] 报道"
