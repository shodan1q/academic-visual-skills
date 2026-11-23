# 最小调用示例（示例 / synthetic，不是正式案例结果）

材料、数值和输出全部为说明接口而虚构。

## 1. 示例输入
case 文件（示例）：
```json
{"case_id": "example-03",
 "task": "示例：按工单用源数据重画论文 Figure 3b，交付可编辑源、SVG/PNG/PDF 和源级修改。",
 "materials": {"source": "source/paper.pdf", "workorder": "artifacts/figure-workorder.json", "data": ["data/fig3b_source.csv"]},
 "output_contract": ["case_id", "status", "editable_source", "export_artifact", "content_map", "compliance_checks", "exceptions"]}
```
工单（示例）：`{"workorder": "source_value_chart", "chart": {"type": "grouped bar with individual points", "x": "genotype", "series": "treatment", "y_quantity": "Ifnb1 mRNA", "y_unit": "fold change vs WT vehicle"}, "export": {"width_mm": 89, "dpi": 600, "min_font_pt": 6}, "edit_request": "DMXAA 改为朱红；y 轴改为 Ifnb1 / Actb (fold vs WT vehicle)"}`
数据（示例）：16 行 `sample_id, genotype, treatment, mouse, Ifnb1_rel, note`，S07 为空（qPCR well failed）。
图注（示例，PDF 第 1 页）：`Bars show mean ± s.e.m.; dots are individual mice; n = 4 mice per group. … ***P < 0.001, WT DMXAA vs WT vehicle; NS …`

## 2. 配置与命令（示意输出）
`chart_config.json`（示例，节选）：
```json
{"kind": "bar", "x": "genotype", "series": "treatment", "y": "Ifnb1_rel", "id_col": "sample_id", "error": "sem", "n_declared": 4,
 "ylabel": "$\\mathit{Ifnb1}$ mRNA (fold vs WT vehicle)", "width_mm": 89, "dpi": 600,
 "sig": [{"a": ["WT", "vehicle"], "b": ["WT", "DMXAA"], "label": "***", "src": "src.txt L14 (Fig. 3 legend)"}],
 "src": {"error": "src.txt L14 'mean ± s.e.m.'", "n_declared": "src.txt L14"}}
```
```
$ timeout 120 python3 make_chart.py
bar-0-1 WT/DMXAA mean=37.57 sem=3.277 n=3 rows=[6, 7, 9]
EXCLUDED: row 8 S07 ['WT', 'DMXAA'] (empty or non-numeric value)
WARN: n mismatch: x='WT' series='DMXAA' has n=3 usable rows, source states n=4
$ python3 $S/scripts/chartkit.py marks chart.svg chart_marks_expected.csv
err-0-1: length: value 6.55473 -> 18.73 px, residual 0.00% of axis OK
scale(length): 2.8570 px per unit from y-axis ticks [0.0, 10.0, 20.0, 30.0, 40.0, 50.0] (OK)
PASS: 23 mark sample(s), 0 problem(s)
$ python3 $S/scripts/export_check.py skeleton     # 第 2 步，任意 contract 写法
skeleton result.json: case_id='example-03', fields=['case_id', 'compliance_checks', 'content_map', ...]
$ python3 $S/scripts/pixcheck.py chart.svg --workorder /input/artifacts/figure-workorder.json   # 只给提示，退出码 0
PASS: 4 bars sampled on export PNG itself, ink 13.0%, PNG [2102, 1535] px (want 2102), min font 7.0 pt
$ (若把空值当 0 计算期望值) -> bar-0-1: length: value 28.175 -> 107.33 px, residual 18.78% of axis MISMATCH ... FAIL
$ echo '{"colors": {"DMXAA": "#D55E00"}, "ylabel": "..."}' > edit_v2.json
$ timeout 120 python3 make_chart.py chart_v2 edit_v2.json && python3 $S/scripts/chartkit.py diff chart.svg chart_v2.svg
{"kept_ids": 58, "changed_ids": ["bar-0-1", "bar-1-1", "patch_6", "ylabel"], ...}
$ cat > /app/work/notes.json   # 只写判断：status、status_reasons、compliance_checks、exceptions、edit_request
$ python3 $S/scripts/export_check.py assemble /app/work/notes.json
assembled result.json: status=partial, 7 contract field(s): case_id<-case_id, status<-status, editable_source<-editable_source, ...
PASS: 7 contract field(s), status=partial, 0 fail / 0 warn
```
contract 换成别的名字（示例：`{"required": ["case_id", "run_status", "figure_source_files", "rendered_outputs", "provenance_table", "qa_report", "open_issues", "revision_history"]}`）时，assemble 输出
`run_status<-status, figure_source_files<-editable_source, rendered_outputs<-export_artifact, provenance_table<-content_map, qa_report<-compliance_checks, open_issues<-exceptions, revision_history<-change_log`。
```
```

## 3. 示意结果（示例，节选）
```json
{"case_id": "example-03", "status": "partial",
 "status_reasons": ["图注写 n = 4，WT/DMXAA 只有 3 个可用值，需作者确认"],
 "content_map": {"marks": [{"id": "bar-0-1", "x": "WT", "series": "DMXAA", "mean": 37.57, "error_type": "sem", "n": 3, "csv_rows": [6, 7, 9], "sample_ids": ["S05", "S06", "S08"]}],
                 "excluded_rows": [{"row": 8, "id": "S07", "reason": "empty or non-numeric value"}], "mark_check": {"verdict": "PASS", "samples": 23}},
 "compliance_checks": [{"requirement": "error bars with the legend meaning", "result": "pass", "element_ids": ["err-0-0", "err-0-1"], "evidence": "error=sem; src.txt L14"}],
 "exceptions": [{"category": "contradiction", "detail": "图注 n = 4 vs 数据 3 个可用值", "handling": "按数据画，图注写明"},
                {"category": "data_excluded", "detail": "row 8 S07 空值", "handling": "排除并记入图注"}]}
```
