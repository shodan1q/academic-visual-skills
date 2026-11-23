# 最小调用示例（示例 / synthetic，不是正式案例结果）

以下材料、数值与输出全部为说明接口而虚构（一段合成的小鼠 cGAS–STING 机制描述）。

## 1. 示例输入
case（示例）：
```json
{"case_id": "SIM04-PATHWAY-01",
 "materials": ["source/paper.pdf", "data/tableS3_log2fc.csv", "artifacts/figure-workorder.json"],
 "output_contract": ["case_id", "status", "editable_source", "export_artifact", "content_map", "compliance_checks", "exceptions"]}
```
工单（示例，节选）：
```json
{"figure_id": "figure03", "panel": "3E",
 "required_compartments": ["extracellular", "plasma membrane", "cytosol", "ER membrane", "Golgi", "nucleus"],
 "must_show": ["binding vs activation vs inhibition vs phosphorylation vs translocation vs ubiquitination distinguishable",
               "negative feedback loop", "parallel NF-kB branch", "evidence strength for indirect links"],
 "export": {"formats": ["svg", "pdf", "png"], "width_mm": 180, "png_dpi": 600, "min_font_pt": 6},
 "edit_request": "change the label of TBK1 to 'TBK1 (p-S172)' and the IFNAR colour to grey #BBBBBB, re-export, record the diff"}
```
paper.pdf 文本（示例，节选，行号来自 `pdftotext -layout`）：
```
14 3.4 TBK1 phosphorylated STING at Ser365 and phosphorylated IRF3 at Ser388.
15 Phosphorylated IRF3 dimerized and translocated to the nucleus.
16 3.5 In the nucleus, IRF3 induced transcription of Ifnb1 and Cxcl10. ...
19 3.6 STAT1 induced expression of the E3 ligase Trim30a. TRIM30a protein promoted
20 ubiquitination and degradation of STING, providing negative feedback (Figure 3E).
23 3.8 The phosphatase PPM1A inhibited TBK1 activity; the effect was observed only
24 with overexpression and should be considered indirect.
30 Note: In the abstract we state that Irf3 mRNA is strongly upregulated; Table S3 shows otherwise.
```
tableS3_log2fc.csv（示例，节选）：`gene,protein,log2FC_6h,padj` / `Ifnb1,IFN-beta,6.9,1e-12` / `Irf3,IRF3,-0.3,0.48` / `Trim30a,TRIM30a,3.1,4e-6`

## 2. spec 片段（示例；自动布局，不写任何坐标）
```json
{"canvas": {"width_mm": 180, "min_font_pt": 6,
  "colorscale": {"csv": "/input/data/tableS3_log2fc.csv", "key": "gene", "value": "log2FC_6h", "breaks": [-1, 1, 3, 5],
                 "colors": ["#2166AC", "#CCCCCC", "#FDDBC7", "#EF8A62", "#B2182B"], "title": "log2FC, 6 h (Table S3)"}},
 "nodes": [
  {"id": "n-irf3-c", "label": "IRF3", "kind": "protein", "comp": "p-cy", "data": "Irf3", "mods": ["P"], "src": "src.txt:L14-15"},
  {"id": "n-irf3-n", "label": "IRF3", "kind": "protein", "comp": "p-nu", "data": "Irf3", "src": "src.txt:L15-16"},
  {"id": "n-ifnb1", "label": "Ifnb1", "kind": "gene", "comp": "p-nu", "data": "Ifnb1", "src": "src.txt:L16"}],
 "edges": [
  {"id": "e-imp", "from": "n-irf3-c", "to": "n-irf3-n", "type": "transport", "label": "dimer → nucleus", "src": "src.txt:L15"},
  {"id": "e-tx1", "from": "n-irf3-n", "to": "n-ifnb1", "type": "activate", "label": "transcription", "src": "src.txt:L16"},
  {"id": "e-ppm", "from": "n-ppm1a", "to": "n-tbk1", "type": "inhibit", "evidence": "indirect", "src": "src.txt:L23-24"}]}
```

## 3. 命令与输出（示例，本机 rsvg-convert）
```bash
python3 $S/scripts/export_check.py skeleton      # 第 2 步，任意 contract 写法
python3 $S/scripts/svgfig.py build $OUT_DIR/figure_spec.json $OUT_DIR/figure.svg
#  -> no warnings; 18 entities, 19 relations, 17 legend items; auto layout, 8 edge crossings, smallest text 6.0 pt
#     (panels p-er / p-golgi written with "in": "p-cy" become organelle boxes inside the cytosol)
timeout 300 python3 $S/scripts/export_check.py render $OUT_DIR/figure.svg --dpi 600
#  -> PNG 4252 x 3254 px (180 mm @ 600 dpi); PDF vector, 16 fonts embedded
python3 $S/scripts/pixcheck.py $OUT_DIR/figure.svg
#  -> PASS: 18 nodes inspected (re-render 1201 px), fills as declared, labels visible, every colour in legend
cp $OUT_DIR/figure_resolved_spec.json $OUT_DIR/figure_spec_v2.json   # then change only the TBK1 label / IFNAR fill
python3 $S/scripts/svgfig.py build $OUT_DIR/figure_spec_v2.json $OUT_DIR/figure_v2.svg
python3 $S/scripts/svgfig.py diff $OUT_DIR/figure.svg $OUT_DIR/figure_v2.svg > $OUT_DIR/edit_diff.json
#  -> 132 ids kept; changes: n-tbk1-label text "TBK1" -> "TBK1 / (p-S172)", n-ifnar fill #FFFFFF -> #BBBBBB, legend-fill-bbbbbb added
python3 $S/scripts/export_check.py assemble $WORK_DIR/notes.json   # notes 只含 status、reasons、compliance_checks、exceptions、edit_request
#  -> assembled result.json: status=partial, 7 contract field(s) ...
#  -> PASS: 7 contract field(s), status=partial, 0 fail / 0 warn
```
第一次 build v2 时只改了颜色、没加图例项，pixcheck 提示 `node n-ifnar colour #BABABA has no legend swatch`；在 spec_v2 的 legend.items 加 `{"fill":"#BBBBBB","label":"recoloured on request (no data)"}` 后消失（提示不阻断交付，改一次即可）。
contract 换成别的名字（示例：`[{"field":"caseId"},{"field":"outcome","allowed":["done","partial","failed"]},{"field":"diagramSource"},{"field":"previewFiles"},{"field":"elementProvenance"},{"field":"qcResults"},{"field":"knownProblems"},{"field":"editHistory"},{"field":"图注"}]`）时，assemble 把它们分别填成 case_id、状态词（partial）、editable_source、export_artifact、content_map、compliance_checks、exceptions、change_log、caption。

## 4. result.json 节选（示例）
```json
{"case_id": "SIM04-PATHWAY-01", "status": "partial",
 "status_reasons": ["Abstract vs Table S3 contradiction on Irf3 left for author confirmation",
                    "edit request adds p-S172, which the source does not mention"],
 "editable_source": {"svg": "figure.svg", "spec": "figure_spec.json", "edited": ["figure_v2.svg", "figure_spec_v2.json"]},
 "content_map": {"file": "figure_content_map.json",
   "relations": [{"id": "e-ppm", "from": "PPM1A", "to": "TBK1", "type": "inhibit", "evidence": "indirect", "src": "src.txt:L23-24"}],
   "data_encoding": {"file": "/input/data/tableS3_log2fc.csv", "sha256_16": "ab7d289f2138333a",
                     "nodes": [{"node": "n-irf3-c", "key": "Irf3", "value": -0.3, "bin": "-1 to < 1", "color": "#E0E0E0"}]}},
 "compliance_checks": [{"requirement": "negative feedback loop", "result": "pass",
                        "element_ids": ["e-trimg", "e-trimp", "e-fb"], "evidence": "STAT1 → Trim30a → TRIM30a ⊣ STING"}],
 "exceptions": [{"category": "contradiction", "detail": "abstract: Irf3 strongly up; Table S3: log2FC -0.3",
                 "handling": "coloured by Table S3"},
                {"category": "user_request_not_in_source", "detail": "label 'TBK1 (p-S172)'", "handling": "applied in v2, src marks the workorder"}]}
```
