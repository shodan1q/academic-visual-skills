# 最小调用示例（示例 / synthetic，不是正式案例结果）

下面的材料、数值和输出全部为说明接口而虚构。

## 1. 示例输入
case 文件（示例）：
```json
{"caseId": "example-04",
 "task": "示例：依据 materials/mechanism.md 画三区室信号通路机制图，用颜色标出 de.csv 的 log2FC；随后把 β-catenin 节点标签改为 β-catenin (CTNNB1)。",
 "materials": ["materials/mechanism.md", "materials/de.csv"],
 "outputContract": {"editableSource": "分层 SVG 源文件路径", "exports": "PNG/PDF 导出件与检查",
                    "provenance": "元素来源与修改记录（表）", "status": "completed / partial / failed"}}
```
`materials/mechanism.md`（示例，节选）：
```
2  Ligand WNT3A binds the receptor FZD7 at the plasma membrane together with co-receptor LRP6.
3  Receptor activation recruits DVL2 to the membrane, and DVL2 inhibits the destruction complex (AXIN1/APC/GSK3B).
7  AXIN2 protein is reported to feed back on the destruction complex; whether this is direct was not tested.
```
`materials/de.csv`（示例）：`gene,log2FC,padj` / `AXIN2,2.4,0.001` / `MYC,1.1,0.03`

## 2. 实体—关系表（示例，节选）
| id | 上游 | 下游 | 语义 | 证据 | 来源 |
|---|---|---|---|---|---|
| e-bind1 | WNT3A | FZD7 | bind | 直接 | mechanism.md:L2 |
| e-inh | DVL2 | 破坏复合体 | inhibit | 直接 | mechanism.md:L3 |
| e-fb | AXIN2 | 破坏复合体 | indirect（材料说未检验） | 推测 | mechanism.md:L7 |

## 3. 规格片段（示例）
```json
{"nodes": [{"id": "n-dvl2", "label": "DVL2", "cx": 330, "cy": 280, "src": "mechanism.md:L3"},
           {"id": "n-axin2", "label": "AXIN2", "cx": 520, "cy": 700, "italic": true, "fill": "#D55E00", "src": "mechanism.md:L6; de.csv:row2"}],
 "edges": [{"id": "e-fb", "from": "n-axin2", "to": "n-dc", "type": "indirect", "label": "feedback (direct? untested)",
            "via": [[120, 700], [120, 390]], "src": "mechanism.md:L7"}]}
```

## 4. 命令
```bash
python3 $S/scripts/svgfig.py build $OUT_DIR/figure_spec.json $OUT_DIR/figure.svg      # -> no warnings, 24 elements
timeout 300 python3 $S/scripts/export_check.py render $OUT_DIR/figure.svg --dpi 300   # -> rsvg-convert, PDF fonts embedded
python3 $S/scripts/svgfig.py edit $OUT_DIR/figure.svg $OUT_DIR/figure_v2.svg n-bcat-label --text "β-catenin (CTNNB1)"
python3 $S/scripts/svgfig.py diff $OUT_DIR/figure.svg $OUT_DIR/figure_v2.svg          # -> 1 change, 78 ids kept
python3 $S/scripts/export_check.py check                                              # -> PASS
```

## 5. 示意输出（示例）
- `figure.svg` 分层：layer-panels（胞外/膜/胞质/核）、layer-edges（10 条语义边）、layer-nodes、layer-text、layer-legend；每个元素带 `data-src`。
- `result.json`（节选）：
```json
{"case_id": "example-04", "status": "completed",
 "provenance": {"source_map_file": "figure_source_map.md",
                "change_log": [{"id": "n-bcat-label", "change": "text", "before": "β-catenin", "after": "β-catenin (CTNNB1)"}]},
 "uncertainties": ["AXIN2 反馈是否直接未检验，画为 indirect"]}
```
