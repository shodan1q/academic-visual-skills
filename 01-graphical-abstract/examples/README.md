# 最小调用示例（示例 / synthetic，不是正式案例结果）

材料、数值和输出全部为说明接口而虚构。

## 1. 示例输入
case 文件（示例）：
```json
{"id": "example-01",
 "task": "示例：为 materials/summary.md 的研究做单页英文横版 Graphical Abstract，核心结果用 materials/cd_uptake.csv 的数值。",
 "output_contract": [{"field": "editable_source", "desc": "分层可编辑源文件路径"},
                     {"field": "export_files", "desc": "PNG/PDF 导出件路径、尺寸、分辨率、字体检查"},
                     {"field": "provenance_and_changes", "desc": "元素来源、数据映射与修改记录（表）"},
                     {"field": "status", "desc": "complete / partial / failed"}]}
```
`materials/summary.md`（示例，节选）：
```
2 Problem: cadmium (Cd) in paddy soil accumulates in rice grain.
3 Method: a pot experiment compared unamended soil with soil amended with 2% (w/w) rice-husk biochar (n = 5 pots per treatment).
4 Biochar raised soil pH and immobilised Cd (sequential extraction; data not provided here).
6 Conclusion: biochar amendment is associated with lower grain Cd in this pot trial; field validation is needed.
```
`materials/cd_uptake.csv`（示例）：`treatment,grain_Cd_mg_kg_mean,sd,n` / `Control,0.42,0.05,5` / `Biochar 2%,0.19,0.03,5`

## 2. 面板—要点映射（示例）
| 面板 | 上图要点 | 形式 | 来源 |
|---|---|---|---|
| 1 Problem | 土壤 Cd → 籽粒积累 | 两个节点 + transport 边 | summary.md:L2 |
| 2 Method | 对照 vs 2% 生物炭，n = 5 | 节点 + step 边 | summary.md:L3 |
| 2 Method | pH 升高、Cd 形态（无数据） | 点线 indirect | summary.md:L4 |
| 3 Key result | 籽粒 Cd 均值 ± SD | bars | cd_uptake.csv:row2–3 |
| 4 Conclusion | “associated with”，需田间验证 | 圆角框 | summary.md:L6 |
| 只进图注 | 连续提取法、误差含义 | figure_caption.md | summary.md:L4 |

## 3. 由数据生成 bars（示例）
```python
rows = list(csv.DictReader(open("/input/materials/cd_uptake.csv")))
items = [{"label": r["treatment"], "value": float(r["grain_Cd_mg_kg_mean"]), "err": float(r["sd"]),
          "src": "cd_uptake.csv:row%d" % (i + 2)} for i, r in enumerate(rows)]
spec["bars"] = [{"id": "c-cd", "x": 630, "y": 110, "w": 290, "h": 330, "title": "Grain Cd (mg/kg), mean ± SD",
                 "items": items, "src": "cd_uptake.csv:rows2-3"}]
```

## 4. 命令与示意输出
```
$ python3 $S/scripts/svgfig.py build figure_spec.json figure.svg
WARN: edge e-pot1: via point [345, 430] lies inside node n-pot (move it outside)   # 第一次的布局错误被抓到
$ ...修正 via 后重建 -> no warnings
$ (回读) c-cd-bar0 0.42 208.3 / c-cd-bar1 0.19 94.2      # 208.3/0.42 ≈ 94.2/0.19 ≈ 496 px/单位
$ timeout 300 python3 $S/scripts/export_check.py render figure.svg --dpi 300   # rsvg-convert；PDF 14 个字体全部嵌入
$ python3 $S/scripts/export_check.py check
PASS: 4 contract field(s), status=partial, 0 fail / 0 warn
```
`result.json`（示例，节选）：
```json
{"case_id": "example-01", "status": "partial",
 "status_reasons": ["机制（pH、Cd 形态）材料无数据，只以点线示意"],
 "provenance_and_changes": {"data_mapping": [{"bar": "c-cd-bar0", "group": "Control", "value": 0.42, "sd": 0.05,
   "unit": "mg/kg", "source": "cd_uptake.csv row2", "readback_height": 208.3}]}}
```
