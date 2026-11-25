# 最小调用示例（示例 / synthetic，不是正式案例结果）

以下材料、数值与输出全部为说明接口而编写：一篇合成的 4 页“论文” PDF，内容按哈维弧菌群体感应的教科书知识改写，Figure 3 为矢量图（图中文字在 PDF 文本层）。

## 1. 示例输入
case（示例）：
```json
{"case_id": "SIM02-QS-FIG3", "task": "Redraw Figure 3 of the source paper as an editable relationship schematic following the work order.",
 "workorder": "artifacts/figure-workorder.json",
 "materials": ["source/paper.pdf", "data/table1_autoinducers.csv", "artifacts/figure-workorder.json"],
 "output_contract": ["case_id", "status", "editable_source", "export_artifact", "content_map", "compliance_checks", "exceptions"]}
```
工单（示例，节选）：
```json
{"figure_id": "figure03", "workorder_type": "editable_relationship_schematic",
 "panels": ["3a low cell density (LCD): kinase mode", "3b high cell density (HCD): phosphatase mode"],
 "must_show": ["three autoinducer-receptor pairs with their synthases; autoinducers coloured by signal class from Table 1",
               "compartments: receptors in the inner membrane, LuxP periplasmic, LuxU/LuxO/Hfq/LuxR cytoplasmic",
               "phosphorelay direction receptor -> LuxU -> LuxO at LCD, reversed at HCD",
               "untested feedback must not look like established regulation"],
 "export": {"formats": ["svg", "pdf", "png"], "width_mm": 180, "png_dpi": 600, "min_font_pt": 6},
 "edit_request": "rename the node 'Qrr1-5' to 'Qrr sRNAs (qrr1-5)' and recolour the inter-species signal class to #CC79A7; re-export and record the source-level diff."}
```
table1_autoinducers.csv（示例）：`autoinducer,synthase,receptor,signal_class,...` / `HAI-1,LuxM,LuxN,intra-species,...` / `AI-2,LuxS,LuxPQ,inter-species,...` / `CAI-1,CqsA,CqsS,intra-genus,...`

## 2. 找图注和原图标签（示例输出，节选）
```bash
pdftotext -layout /input/source/paper.pdf /app/work/src.txt
# 本例 case.json 明说 “Figure 3 of the source paper”，且图注主题与工单 title 一致，才用图号；否则按工单关键词 grep 正文
python3 $S/scripts/export_check.py figtext /app/work/src.txt 3
# caption of figure 3: src.txt:L84-88 (page 3)
#   L84 Figure 3. Quorum-sensing circuit of V. harveyi. (a) At LCD the receptors LuxN, LuxPQ and CqsS act as kinases; ...
# short text on the same page, outside the caption (usually the labels drawn in the original figure; lines L46-79):
#   HAI-1 | AI-2 | CAI-1 | a Low cell density (kinase) | b High cell density (phosphatase) | Inner membrane | LuxN | LuxPQ | CqsS |
#   Cytoplasm | LuxU | P | sigma-54 | LuxO-P | LuxO | Qrr1-5 | Hfq | LuxR | qrr4 promoter | luxR mRNA | aphA mRNA | ...
# lines citing figure 3: L27 L29 L34 L36
```

## 3. 结构 spec 片段（示例；不写任何坐标）
```json
{"canvas": {"width_mm": 180, "min_font_pt": 6, "title": "Quorum-sensing circuit of V. harveyi",
  "categories": {"csv": "/input/data/table1_autoinducers.csv", "key": "autoinducer", "column": "signal_class", "title": "Signal class (Table 1)"}},
 "panels": [{"id": "p-a", "title": "a  Low cell density: kinase mode", "src": "src.txt:L84"},
            {"id": "a-out", "parent": "p-a", "title": "Outside (autoinducers low)", "src": "src.txt:L29"},
            {"id": "a-mem", "parent": "p-a", "title": "Inner membrane", "fill": "#F2D7B6", "src": "src.txt:L27"},
            {"id": "a-cyt", "parent": "p-a", "title": "Cytoplasm", "layout": "grid", "src": "src.txt:L27"},
            {"id": "p-b", "title": "b  High cell density: phosphatase mode", "src": "src.txt:L86"}],
 "nodes": [{"id": "a-ai2", "label": "AI-2", "kind": "small_molecule", "comp": "a-out", "data": "AI-2", "src": "table1_autoinducers.csv:row3"},
           {"id": "a-luxpq", "label": "LuxP·LuxQ", "kind": "protein", "comp": "a-mem", "src": "src.txt:L27"},
           {"id": "a-luxu", "label": "LuxU", "kind": "protein", "comp": "a-cyt", "col": 1, "row": 0, "src": "src.txt:L29"},
           {"id": "a-luxo", "label": "LuxO~P", "kind": "protein", "comp": "a-cyt", "col": 1, "row": 1, "src": "src.txt:L29"},
           {"id": "a-qrr", "label": "Qrr1–5 sRNAs", "kind": "concept", "comp": "a-cyt", "col": 1, "row": 2, "src": "src.txt:L31; L93"}],
 "edges": [{"id": "a-e2", "from": "a-luxpq", "to": "a-luxu", "type": "phospho", "src": "src.txt:L29"},
           {"id": "a-e4", "from": "a-luxu", "to": "a-luxo", "type": "phospho", "src": "src.txt:L29"},
           {"id": "b-e7", "from": "b-luxR", "to": "b-qrr4", "type": "inhibit", "evidence": "hypothesis", "label": "ChIP only", "src": "src.txt:L38-39"}],
 "texts": [{"id": "t-note", "text": "* Qrr count: five in Abstract and Methods M3; Results R3 says four (unresolved).", "src": "src.txt:L9; L31; L93"}],
 "legend": {"title": "Legend"}}
```

## 4. 命令与输出（示例，本机 rsvg-convert）
```bash
python3 $S/scripts/svgfig.py build $OUT_DIR/figure_spec.json $OUT_DIR/figure.svg
#  no warnings
#  wrote ... (25 entities, 50 relations, 8 legend items; canvas 985x939 px = 180 mm wide, smallest text 12.5 px = 6.5 pt; all text scaled x1.04 ...)
timeout 300 python3 $S/scripts/export_check.py render $OUT_DIR/figure.svg --dpi 600
#  -> PNG 4252 x 4054 px (180 mm @ 600 dpi); PDF vector, 16 fonts, all embedded
python3 $S/scripts/svgfig.py build $OUT_DIR/figure_spec_v2.json $OUT_DIR/figure_v2.svg   # 只改 a-qrr 的 label + categories.colors
python3 $S/scripts/svgfig.py diff $OUT_DIR/figure.svg $OUT_DIR/figure_v2.svg > $OUT_DIR/edit_diff.json
#  -> content_changes 4: a-qrr-label text; a-ai2 / b-ai2 / legend-cat-interspecies-glyph fill #E69F00 -> #CC79A7
#     (另有 layout_only_changes：标签变长后自动重排的坐标)
python3 $S/scripts/export_check.py check
#  -> PASS: 7 contract field(s), status=partial, 0 fail / 0 warn
```
渲染结果（示例）：两个子图各含 “Outside / Inner membrane / Cytoplasm” 三个嵌套分区；受体在膜带内，磷酸转移为紫色箭头（图例 “phosphotransfer (~P)”），LuxR ⊣ qrr4 为点划线（hypothesis）；图例在图下方分两栏：关系类型 + “Signal class (Table 1)” 3 个色块；脚注在最下。

## 5. result.json 节选（示例）
```json
{"case_id": "SIM02-QS-FIG3", "status": "partial",
 "status_reasons": ["Qrr count contradicts (five in Abstract/M3 vs four in R3); drawn as Qrr1-5 with footnote"],
 "editable_source": {"svg": "figure.svg", "spec": "figure_spec.json", "edited": ["figure_v2.svg", "figure_spec_v2.json"]},
 "content_map": {"file": "figure_content_map.json",
   "relations": [{"id": "contains-a-luxpq", "from": "Inner membrane", "to": "LuxP·LuxQ", "type": "contains", "src": "src.txt:L27"},
                 {"id": "b-e7", "from": "LuxR", "to": "qrr4", "type": "inhibit", "evidence": "hypothesis", "src": "src.txt:L38-39"}],
   "export_geometry": {"canvas_px": [985, 939], "width_mm": 180, "min_font_pt": 6.5, "text_scale": 1.04}},
 "compliance_checks": [{"requirement": "compartments: receptors in the inner membrane, LuxP periplasmic, ...", "result": "pass",
                        "element_ids": ["a-mem", "a-cyt", "a-luxpq"], "evidence": "nested panels; LuxP·LuxQ inside the membrane band"},
                       {"requirement": "labels match the original Figure 3", "result": "partial",
                        "element_ids": ["a-qrr"], "evidence": "all figtext labels drawn except 'AphA (LCD genes)' (not requested by the work order)"}],
 "exceptions": [{"category": "contradiction", "detail": "Abstract L9 / Methods L93: five Qrr; Results L31: four", "handling": "five + footnote quoting both"},
                {"category": "undecidable", "detail": "LuxR feedback on qrr4 supported by ChIP only", "handling": "hypothesis line style + caption"}]}
```
