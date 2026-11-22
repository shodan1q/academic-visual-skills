# 最小调用示例（示例 / synthetic，不是正式案例结果）

材料、数值和输出全部为说明接口而虚构。

## 1. 示例输入
case 文件（示例）：
```json
{"case_id": "example-05",
 "task": "示例：依据 materials/setup.md 画连续流电解装置图（英文标签），标出液体、气体、电与回流；材料没写的连接不要补。",
 "output_contract": {"editable_source": "分层源文件", "exports": "导出件与检查", "records": "来源、版本与修改记录",
                     "status": "complete / partial / failed"}}
```
`materials/setup.md`（示例）：
```
2 Electrolyte (1 M KOH) is held in a 500 mL reservoir.
3 Peristaltic pump P1 delivers electrolyte from the reservoir to the flow cell at 20 mL/min.
4 The flow cell contains the working electrode and counter electrode; a potentiostat supplies -1.2 V vs RHE.
5 Gas products leave the flow cell through the gas outlet to a gas chromatograph (GC).
6 Liquid outlet of the flow cell returns to the reservoir (recirculation).
7 A cold trap is mentioned in the parts list; its position in the line is not described.
```

## 2. 结构化清单（示例，节选）
| 连接 | from | to | 介质 | 画法 | 来源 |
|---|---|---|---|---|---|
| e-feed2 | P1 | 流动池 | 液体 20 mL/min | flow 蓝 | setup.md:L3 |
| e-power | 恒电位仪 | 流动池 | 电 -1.2 V vs RHE | signal 虚线 | setup.md:L4 |
| e-gas | 流动池 | GC | 气体 | flow 绿 | setup.md:L5 |
| e-recirc | 流动池 | 储液罐 | 回流液 | flow 灰，via 从下方绕回 | setup.md:L6 |
| — | 冷阱 | ? | ? | **不画**，列 material_gaps | setup.md:L7 |

## 3. 规格片段（示例）
```json
{"edges": [{"id": "e-recirc", "from": "n-cell", "to": "n-res", "type": "flow", "color": "#777777", "width": 3,
            "via": [[640, 460], [140, 460]], "label": "liquid outlet, recirculation", "src": "setup.md:L6"}],
 "texts": [{"id": "t-gap", "text": "Cold trap listed in parts list; position not described, not drawn.", "x": 30, "y": 540, "fs": 12, "src": "setup.md:L7"}]}
```

## 4. 命令与示意输出
```
$ python3 $S/scripts/svgfig.py build figure_spec.json figure.svg              -> no warnings (11 elements)
$ timeout 300 python3 $S/scripts/export_check.py render figure.svg           -> rsvg-convert PNG + vector PDF
$ python3 $S/scripts/svgfig.py edit figure.svg figure_v2.svg n-p1-label --text "P1\nperistaltic pump\n20 mL/min"
$ python3 $S/scripts/svgfig.py diff figure.svg figure_v2.svg
  {"id": "n-p1-label", "change": "text", "before": "P1 / peristaltic / pump", "after": "P1 / peristaltic pump / 20 mL/min"}
$ python3 $S/scripts/export_check.py check                                   -> PASS, status=partial
```
`result.json`（示例，节选）：
```json
{"case_id": "example-05", "status": "partial",
 "status_reasons": ["冷阱位置材料未描述，未画（setup.md L7）"],
 "material_gaps": ["cold trap position"], "needs_human_confirmation": ["冷阱接在哪条管路"]}
```
