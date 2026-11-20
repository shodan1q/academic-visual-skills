# 最小调用示例（示例 / synthetic，不是正式案例结果）

材料、数值和输出全部为说明接口而虚构。

## 1. 示例输入
case 文件（示例）：
```json
{"case_id": "example-03",
 "task": "示例：用 materials/il6.xlsx（Sheet1）画分组柱状图：IL-6 浓度（pg/mL），Control / LPS / LPS+Drug，均值±SD，标注 n；按 materials/stats.txt 标显著性。随后把 y 轴标签改为中文“IL-6 浓度 (pg/mL)”。",
 "output_contract": {"properties": {"chart_source": {"description": "可编辑源文件路径"}, "chart_exports": {"description": "导出件路径与导出参数"},
                     "data_trace": {"description": "图元→源数据行列映射表"}, "status": {"enum": ["complete", "partial", "failed"]}},
                     "required": ["chart_source", "chart_exports", "data_trace", "status"]}}
```
`materials/il6.xlsx`（示例）：12 行 `mouse, group, IL6_pg_mL`，每组 4 只（实际 sheet 名为 `il6`，不是任务写的 Sheet1）。
`materials/stats.txt`（示例）：
```
1 One-way ANOVA on IL-6 (pg/mL), n = 4 mice per group: F(2,9) = 48.2, p < 0.001
2 Tukey post hoc: LPS vs Control p < 0.001; LPS+Drug vs LPS p = 0.004; LPS+Drug vs Control p = 0.012
3 Error bars in the draft figure legend are described as SEM (to be checked).
```

## 2. 命令与示意输出
```
$ python3 $S/scripts/chartkit.py table il6.xlsx --out /app/work
== sheet 'il6': 13 rows x 3 cols, 0 formula cell(s) -> /app/work/il6__il6.csv
il6!row 2: ['M1', 'Control', '21.5'] ...
$ timeout 120 python3 /app/output/make_chart.py
{'Control': (22.5, 2.33, 4), 'LPS': (309.3, 24.53, 4), 'LPS+Drug': (155.9, 14.03, 4)}
$ python3 $S/scripts/chartkit.py marks chart.svg chart_marks_expected.csv
bar-Control: length: value 22.5 -> 18.19 px, residual 0.00% OK
pts-LPS[2]: position: value 342.9 -> ... residual 0.00% OK
PASS: 15 mark sample(s), 0 problem(s)
$ (把期望值 18.9 故意写成 20.9 再跑) -> MISMATCH ... FAIL
$ (改 STYLE["ylabel"] 后) python3 make_chart.py chart_v2 ; python3 $S/scripts/chartkit.py diff chart.svg chart_v2.svg
{"kept_ids": 48, "changes": [{"id": "text_9", "change": "text", "before": "IL-6 (pg/mL)", "after": "IL-6 浓度 (pg/mL)"}]}
$ python3 $S/scripts/export_check.py check   -> PASS
```

## 3. 示意结果（示例，节选）
```json
{"case_id": "example-03", "status": "partial",
 "status_reasons": ["误差线：材料称 SEM，数据核算为 SD，需作者确认", "任务写 Sheet1，实际 sheet 名为 il6"],
 "data_trace": [{"mark": "bar-LPS", "value": "309.3 pg/mL", "source": "il6.xlsx!il6 C6:C9", "method": "复算 mean; SD 24.53"},
                {"mark": "*** / ** / *", "value": "p<0.001 / p=0.004 / p=0.012", "source": "stats.txt L2", "method": "照抄 Tukey"}]}
```
