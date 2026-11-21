# 交付前逐项核对（学术 PPT 模板与格式适配）

每项写进 compliance_checks：`{"check": ..., "result": "PASS|FAIL|WARN|未核对", "basis": "实测依据"}`。

## A. 模板真实套用
- [ ] checker `--template` PASS：母版/版式/主题部件与目标模板逐字节一致；所有页的版式都来自目标模板
- [ ] build 的 `placed` 行：标题在 title/ctrTitle，正文在面积最大的 body/obj，出处在 Source/Note 占位符，图注在图片版式的图注占位符
- [ ] slide_audit.md 的 loose text boxes 列基本为空（图注/出处文本框除外）
- [ ] run 上没有写字体名/颜色；模板样例页已删除；无 "Click to add / 单击此处" 等提示文字

## B. 事实与编号（论文优先）
- [ ] corrections.md 列出旧 deck 与论文不一致处及处理；change_log 有对应记录
- [ ] checker `--paper` 无 "come from the old deck but NOT from the paper"、无 "reads like paper Fig. N"
- [ ] 图表编号沿用论文编号与写法，整册统一；他人工作的数写 "[n] 报道"

## C. 版式约束与字号
- [ ] template_spec.md 写了字号阶梯；正文 ≥ 工作单下限（默认 18 pt），checker `--min-pt` 无 FAIL
- [ ] build.log 的 WARN 已处理（删字 / 拆页 / 换版式）或逐条写进 uncertainty/exceptions
- [ ] 长标题 ≤ 2 行；多图并列用双栏版式或显式 box

## D. 图表
- [ ] slide_audit.md 图片比例误差 ≤ 3%；分辨率不足的图列为 exception
- [ ] 表格是原生表格，数值逐格照论文

## E. 批量一致性与讲述
- [ ] 页数 = 工作单页数（`--slides N`）；plan.md 覆盖旧 deck 每一页的去向
- [ ] 每页有页脚和页码（审计表 placeholders 列含 ftr、sldNum）
- [ ] 每页有备注（审计表 notes chars > 0），备注不复读页面
- [ ] 页序 问题→方法→证据→结论→局限；结果页标题是结论句

## F. 导出与结果文件
- [ ] presentation.pdf 页数 = 幻灯片数；preview PNG 存在；pdffonts 实测与替代写进 substitutions
- [ ] contract 字段齐全；status 一个词；exceptions 分"材料缺失 / 无法判断 / 运行失败"
- [ ] check_result.py PASS
