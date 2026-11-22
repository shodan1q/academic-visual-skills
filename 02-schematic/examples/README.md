# 最小调用示例（示例 / synthetic，不是正式案例结果）

以下材料、数值与输出全部为说明接口而虚构（一段合成的小鼠肠类器官谱系描述）。

## 1. 示例输入
case（示例）：
```json
{"case_id": "SIM02-SCHEMATIC-01", "workorder_type": "editable_relationship_schematic",
 "materials": ["source/paper.pdf", "data/tableS2_cells.csv", "artifacts/figure-workorder.json"],
 "output_contract": ["case_id", "status", "editable_source", "export_artifact", "content_map", "compliance_checks", "exceptions"]}
```
工单（示例，节选）：
```json
{"figure_id": "figure03", "panels": ["3a containment hierarchy", "3b lineage tree", "3c workflow"],
 "must_show": ["containment (organoid > domain > cell type) distinct from lineage arrows", "secretory vs absorptive branch",
               "Paneth-to-stem niche signal (activation)", "Notch repression of secretory fate",
               "workflow steps in order with culture conditions and units"],
 "export": {"formats": ["svg", "pdf", "png"], "width_mm": 180, "png_dpi": 600, "min_font_pt": 6},
 "edit_request": "rename 'TA cells' to 'Transit-amplifying cells' and recolour the secretory lineage to #CC79A7; re-export and record the diff"}
```
paper.pdf 文本（示例，节选，行号来自 `pdftotext -layout`）：
```
 4 Abstract Mouse small-intestinal organoids were grown for 7 days and profiled
10 R1. Each organoid contains two epithelial domains. The crypt-like domain
11 contains Lgr5+ stem cells, Paneth cells and transit-amplifying (TA) cells.
18 R3. Paneth cells support the stem cells by secreting Wnt3 and EGF, which
20 R4. Notch signalling in TA cells represses secretory differentiation via
21 Hes1; ... Whether Hes1 acts directly on Atoh1 in organoids was not tested here.
26 and cultured in ENR medium (EGF 50 ng/mL, Noggin 100 ng/mL, R-spondin 1 500
27 ng/mL) for 4 days before dissociation, ...
36 M1. Organoids were cultured for 7 days in ENR medium before single-cell
```
tableS2_cells.csv（示例，节选）：`cell_type,lineage,n_cells,domain` / `Lgr5+ stem cells,stem,1105,crypt-like` / `TA cells,progenitor,1460,crypt-like` / `Paneth cells,secretory,312,crypt-like`

## 2. spec 片段（示例）
```json
{"canvas": {"w": 1000, "h": 870, "width_mm": 180,
  "categories": {"csv": "/input/data/tableS2_cells.csv", "key": "cell_type", "column": "lineage",
                 "colors": {"stem": "#009E73", "progenitor": "#F0E442", "secretory": "#E69F00", "absorptive": "#0072B2"},
                 "title": "Lineage (Table S2)", "show": "n_cells", "fmt": "n = {}"}},
 "panels": [{"id": "p-org", "parent": "p-a", "x": 35, "y": 85, "w": 440, "h": 420, "title": "Organoid", "src": "src.txt:L10"},
            {"id": "p-crypt", "parent": "p-org", "x": 50, "y": 120, "w": 200, "h": 370, "title": "Crypt-like domain", "src": "src.txt:L10-11"},
            {"id": "p-sec", "parent": "p-b", "x": 525, "y": 285, "w": 330, "h": 135, "title": "Secretory lineage", "src": "src.txt:L16-17"}],
 "nodes": [{"id": "a-pan", "label": "Paneth cells", "kind": "cell_type", "comp": "p-crypt", "data": "Paneth cells", "cx": 150, "cy": 300, "w": 160, "h": 64, "src": "src.txt:L11"},
           {"id": "s3", "label": "3 Culture in ENR medium, 7 d *", "kind": "step", "comp": "p-c", "cx": 385, "cy": 640, "w": 130, "h": 70, "src": "src.txt:L26-27; L4; L36"}],
 "edges": [{"id": "e-niche", "from": "a-pan", "to": "a-stem", "type": "signal", "label": "Wnt3, EGF", "src": "src.txt:L18"},
           {"id": "e-hes", "from": "b-hes1", "to": "p-sec", "type": "inhibit", "src": "src.txt:L20-21"}],
 "texts": [{"id": "t-note", "text": "* Culture time: 7 d in Abstract and Methods M1; Results R6 says 4 d (unresolved).", "x": 35, "y": 835, "fs": 12, "src": "src.txt:L4; L27; L36"}],
 "legend": {"x": 772, "y": 545, "title": "Legend"}}
```
标签 “Paneth cells” 由脚本自动变成 “Paneth cells / n = 312”（数字取自 CSV，不手抄）。

## 3. 命令与输出（示例，本机 rsvg-convert）
```bash
python3 $S/scripts/svgfig.py build $OUT_DIR/figure_spec.json $OUT_DIR/figure.svg
#  第一次 -> WARN: edges e-tabs and e-hes cross each other ...（调整两组位置后）-> no warnings
#  21 entities, 38 relations (含 26 条 contains), 10 legend items (auto)
timeout 300 python3 $S/scripts/export_check.py render $OUT_DIR/figure.svg --dpi 600
#  -> PNG 4252 x 3700 px (180 mm @ 600 dpi); PDF vector, 19 fonts embedded
python3 $S/scripts/pixcheck.py $OUT_DIR/figure.svg
#  -> PASS: 21 nodes inspected, fills as declared, labels visible, every colour in legend
python3 $S/scripts/svgfig.py build $OUT_DIR/figure_spec_v2.json $OUT_DIR/figure_v2.svg   # 只改 2 个 label + categories.colors.secretory
python3 $S/scripts/svgfig.py diff $OUT_DIR/figure.svg $OUT_DIR/figure_v2.svg > $OUT_DIR/edit_diff.json
#  -> 99 ids unchanged; 6 secretory nodes + legend-cat-secretory-glyph fill #E69F00 -> #CC79A7; a-ta/b-ta label text
python3 $S/scripts/export_check.py check
#  -> PASS: 7 contract field(s), status=partial, 0 fail / 0 warn
```
对照：若按旧做法逐个节点 `svgfig.py edit … --set fill=#CC79A7`，图例色块仍是旧色，pixcheck 报 `node b-pan colour #CB78A6 has no legend swatch of the same rendered colour`。

## 4. result.json 节选（示例）
```json
{"case_id": "SIM02-SCHEMATIC-01", "status": "partial",
 "status_reasons": ["culture duration contradicts (7 d in Abstract/M1 vs 4 d in R6); drawn as 7 d with footnote"],
 "editable_source": {"svg": "figure.svg", "spec": "figure_spec.json", "edited": ["figure_v2.svg", "figure_spec_v2.json"]},
 "content_map": {"file": "figure_content_map.json",
   "relations": [{"id": "contains-a-pan", "from": "Crypt-like domain", "to": "Paneth cells", "type": "contains", "src": "src.txt:L11"},
                 {"id": "e-hes", "from": "Hes1", "to": "Secretory lineage", "type": "inhibit", "evidence": "direct", "src": "src.txt:L20-21"}],
   "data_encoding": {"file": "/input/data/tableS2_cells.csv", "category_column": "lineage",
                     "nodes": [{"node": "a-pan", "key": "Paneth cells", "category": "secretory", "color": "#E69F00", "shown": {"n_cells": "312"}}]}},
 "compliance_checks": [{"requirement": "Notch repression of secretory fate", "result": "pass",
                        "element_ids": ["e-n-h", "e-hes"], "evidence": "Notch -> Hes1 -| secretory lineage (R4)"}],
 "exceptions": [{"category": "contradiction", "detail": "Abstract L4 / Methods L36: 7 days; Results L27: 4 days", "handling": "7 d + footnote quoting both"},
                {"category": "material_missing", "detail": "Tuft cells seen by imaging only, absent from Table S2", "handling": "not drawn"},
                {"category": "undecidable", "detail": "Hes1 acting directly on Atoh1 not tested", "handling": "Atoh1 not drawn"}]}
```
