# 最小调用示例（合成数据，仅示意接口；不是任何正式案例的结果）

输入（合成）：`/input/case.json`（`case_id` + `output_contract`）、`/input/artifacts/figure-workorder.json`（title、must_show、export{width_mm, png_dpi, min_font_pt, formats}、edit_request）、`/input/source/paper.pdf`、`/input/data/table1_steps.csv`（列 `step,name,stage`）。

```bash
python3 /skills/weekly-skill/scripts/run.py start        # 打印材料（带行号），写 partial result.json
cat > /app/work/figure.txt <<'EOF_SPEC'
title: Assay workflow and analysis package structure @1
color: table1_steps.csv | name | stage | Stage (Table 1)
group a: a  Workflow from tissue to clusters @19
group b: b  Structure of the analysis package @33
group pkg in b: Analysis package @33
group qc in pkg: Quality control module @34
group bc in pkg: Batch-correction module | dashed=planned, not implemented in this study @41
node w1: 1 Nuclei isolation (5 mg tissue) | step | a | data=Nuclei isolation @20
node w2: 2 Fixation (1% formaldehyde, 10 min) | step | a | data=Fixation @21
node w3: 3 Sequencing (2 x 50 bp) | step | a | data=Sequencing @27
node d1: Discarded nuclei | data | a @30
node f1: TSS-enrichment filter (score >= 6) | process | qc @34
node f2: Doublet filter (score < 0.3) | process | qc @35
edge w1 -> w2 | step @21
edge w2 -> w3 | step @27
edge w3 -> d1 | flow | fail QC @30
edge f1 -> f2 | step @34-35
note: * Fixation: 10 min in Results (L21), 5 min in Methods (L52); the Results value is drawn. @21
req: steps in order, numbered, with conditions | pass | w1,w2,w3 | L20-27
req: steps coloured by stage from Table 1 | pass | legend-cat-wetlabpreparation | colours read from the table by the script
req: planned module must not look implemented | pass | bc | dashed outline + footnote (L41)
exc: contradiction | fixation 10 min (L21) vs 5 min (L52) | Results value drawn, footnote added
edit w2 | label=2 Fixation (PFA)
edit library construction | fill=#CC79A7
summary: Two-panel schematic: 3-step workflow with discard branch; package with QC module (2 filters) and a planned module.
EOF_SPEC
python3 /skills/weekly-skill/scripts/run.py build /app/work/figure.txt
```

示意输出（节选，示例）：
```
   data colours: 3 node(s) coloured by stage from table1_steps.csv; 3 node(s) without a row stay white
spec: 5 groups, 6 nodes, 4 edges, 3 requirement checks, 1 exceptions, 2 edit(s); width 180.0 mm, min font 7.0 pt, 300.0 dpi
[0s] build figure.svg: ok (0s)
   legend drawn automatically (5 items): material / sample flow; next step (order); wet-lab preparation; library construction; not listed in table1_steps.csv
[3s] render figure.svg: ok (3s)
   png_method=magick, pdf_method=soffice
[6s] build figure_v2.svg (2 edit(s)): ok (0s)
   diff: 61 ids kept, 57 unchanged; content changes on: legend-cat-libraryconstruction-glyph, w2-label, w3; 2 layout-only change(s) from the automatic re-flow
   source trace: 24/24 src pointers resolved to verbatim quotes; 6/6 entity names occur in their cited lines
   PASS: 7 contract field(s), status=complete, 0 fail / 0 warn
DONE in 12s -> /app/output: edit_diff.json, export_log.jsonl, figure.pdf, figure.png, figure.svg, figure_content_map.json, figure_pixel_check.json, figure_source_map.md, figure_spec.json, figure_spec_lines.txt, figure_spec_v2.json, figure_v2.pdf, figure_v2.png, figure_v2.svg, figure_v2_pixel_check.json, result.json, source_text.txt
```

result.json（示例结构）：`case_id`、`status`（一个词）、`status_reasons`、`editable_source{svg, spec, layers, how_to_edit}`、`export_artifact[{file, format, dpi, pixels, renderer, pdf_is_vector, pdf_fonts}]`、`content_map{entities[{id,label,kind,compartment,fill,data_value,src,quote,page,named_in_source}], relations[…], compartments[…], legend[…], data_encoding{file, sha256_16, categories[{label,color,n_rows}], nodes[…]}, export_geometry, source_trace}`、`compliance_checks[{requirement,result,element_ids,evidence}]`、`exceptions[{category,detail,handling}]`、`change_log[{version,request,outputs,svg_changes,kept_ids,unchanged_ids}]`、`versions`、`artifacts`、`caption`。contract 字段名不同（camelCase、中文、properties/required）时按含义对应填写，并在 `run_notes` 说明。

常见情况：
- 没有工单修改请求：不写 `edit` 行，脚本做一次标明“演示”的描边编辑并写入 change_log。
- 没有数据表：不写 `color:` 行；手工底色配 `key: #56B4E9 | 含义`。
- 只改现成 SVG 的一个标签：`svgfig.py edit in.svg out.svg <id>-label --text "新标签"`，再 `svgfig.py diff in.svg out.svg`。
