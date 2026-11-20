# 交付前逐项核对（学术 PPT 生成与编辑）

每项写进 compliance_checks：`{"check": ..., "result": "PASS|FAIL|WARN|未核对", "basis": "实测依据"}`。

## A. 工作单
- [ ] mode、总页数、编辑指令（E1…En 原文）、source preservation、template inheritance 全部抄进 plan.md
- [ ] 每条指令在 compliance_checks 里单独一行，依据是 diff 文件里的对应改动
- [ ] 页数 = 工作单总页数（checker `--slides N`）

## B. 保留与版本
- [ ] 未点名的页用 keep 原样保留；diff 中保留页只有页码数字变化
- [ ] 每轮有 spec_vK.json、diff_vJ_vK.txt，复制到 `$OUT_DIR/versions/`；change_log 每条有回退方式
- [ ] 最终交付文件名与工作单一致（默认 presentation.pptx / presentation.pdf）

## C. 内容
- [ ] 改写/换受众/换语言后术语、符号、单位与论文一致；专有名词首现保留原文
- [ ] 每页正文 ≤ 5 条；build 无溢出 WARN
- [ ] 数字照抄原文（checker 数字回查无小数 FAIL；`--source` 同时给 paper.txt 与 v0.txt）
- [ ] 新增图表：有数值 → 原生表格；只有原图 → figcrop 原图 + "原文 Fig. X"；都没有 → 不做并记 exception
- [ ] content_map 每页有 action、instruction、来源 locator、秒数

## D. 模板与导出
- [ ] checker `--template`（edit 用 starting-deck，generate/adapt 用 target-template）PASS
- [ ] 无模板提示文字残留；页脚页码沿用模板
- [ ] presentation.pdf 页数 = 幻灯片数；preview PNG 存在；pdffonts 实测写入 export_artifact
- [ ] 每页有备注且不复述页面；保留页原备注仍在

## E. 记录与结果
- [ ] time_record.json：开始/结束时间、每页秒数与合计
- [ ] contract 根字段齐全；status 一个词；exceptions 分"材料缺失 / 无法判断 / 运行失败"
- [ ] check_result.py PASS
