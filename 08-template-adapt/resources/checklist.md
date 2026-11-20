# 交付前逐项核对（学术 PPT 模板与格式适配）

每项写进 compliance_checks：`{"check": ..., "result": "PASS|FAIL|WARN|未核对", "basis": "实测依据"}`。

## A. 模板真实套用
- [ ] checker `--template` PASS：母版/版式/主题部件与目标模板逐字节一致
- [ ] 所有页的版式都来自目标模板（checker 无 "layouts that are not in the template"）
- [ ] inspect 输出里每页标题是 `ph:title`/`ph:ctrTitle`，正文是 `ph:obj`/`ph:body`；散装 `text` 只用于图注
- [ ] run 上没有写字体名/颜色（字体颜色靠主题继承）；工作单规定的例外已记录
- [ ] 模板样例页已删除；无 "单击此处添加" 等提示文字

## B. 版式约束与字号
- [ ] template_spec.md 记录了母版标题/正文字号；没有任何正文低于母版正文 80%（或工作单下限）
- [ ] build 无溢出 WARN；有的话写了处理方式（删冗余 / 拆页 / 换版式）
- [ ] 长标题不超过 2 行；多图并列用 Two Content/Comparison 或显式 box，图不重叠

## C. 图表适配
- [ ] 图片等比缩放（kit 默认），没有拉伸；分辨率不足的图列为 exception
- [ ] 表格是原生表格，数值与原 deck/论文逐格一致（checker 数字回查）
- [ ] 图表编号与引用编号与来源一致，整册写法统一

## D. 批量一致性
- [ ] 页数 = 原 deck / 工作单页数（checker `--slides N`）；layout_map 覆盖每一页
- [ ] 每页有页脚和页码，页码连续（inspect 里 `ph:sldNum` 数 = 页数）
- [ ] 备注全部迁移（inspect 里每页 `[notes]` 非空，或原页本无备注已注明）

## E. 导出
- [ ] presentation.pdf 页数 = 幻灯片数；preview PNG 存在
- [ ] pdffonts 实测字体与替代情况写入 export_artifact
- [ ] 渲染后文字无丢失（checker 无 "missing from the rendered PDF page"）

## F. 结果文件
- [ ] contract 字段齐全；status 一个词；exceptions 分"材料缺失 / 无法判断 / 运行失败"
- [ ] check_result.py PASS
