# 最小调用示例（示例 / synthetic，不是正式案例结果）

材料、数值和输出全部为说明接口而虚构。

## 1. 示例输入
case 文件（示例）：
```json
{"case_id": "example-02",
 "task": "示例：依据 materials/protocol.md 画类器官药筛实验流程示意图（中文标签），按 materials/groups.csv 的处理组着色并给图例；期刊单栏 85 mm，导出 PDF + PNG(600 dpi)。",
 "deliverables": {"source_file": "可编辑分层源文件路径", "export": "导出件路径与期刊参数检查",
                  "trace": "元素来源与修改记录表", "status": "complete / partial / failed"}}
```
`materials/protocol.md`（示例，节选）：
```
2 肿瘤组织经酶解得到单细胞悬液，接种于基质胶中培养 7 天形成类器官。
3 类器官分为三组并行处理 72 h：溶剂对照、药物 A 1 µM、药物 A 10 µM。
4 处理结束后进行 ATP 发光法活力检测与免疫荧光成像，两项检测并行。
```
`materials/groups.csv`（示例）：`group,label` / `vehicle,溶剂对照` / `A1,药物 A 1 µM` / `A10,药物 A 10 µM`

## 2. 关系清单（示例，节选）
| id | from | to | 关系 | 画法 | 来源 |
|---|---|---|---|---|---|
| r1 | 肿瘤组织 | 单细胞悬液 | 时序 | step | protocol.md:L2 |
| r2 | 三个处理组 | — | 并列 | 同行同尺寸、无箭头，外框 panel | protocol.md:L3 |
| r3 | 处理 | ATP / 免疫荧光 | 上下游 + 并行 | 一个分叉两条 step | protocol.md:L4 |

## 3. 从数据表生成着色与图例（示例）
```python
G = list(csv.DictReader(open("/input/materials/groups.csv", encoding="utf-8")))
pal = ["#BBBBBB", "#56B4E9", "#0072B2"]
nodes += [{"id": "n-grp-" + g["group"], "label": g["label"], "cx": 70 + 130 * i, "cy": 210, "w": 116, "h": 40,
           "fs": 13, "fill": pal[i], "src": "protocol.md:L3; groups.csv:row%d" % (i + 2)} for i, g in enumerate(G)]
legend = {"x": 10, "y": 385, "items": [{"fill": pal[i], "label": g["label"]} for i, g in enumerate(G)] + [{"edge": "step", "label": "流程顺序"}]}
spec["canvas"] = {"w": 400, "h": 470, "width_mm": 85, "title": "类器官药物处理流程（示例）", "title_fs": 15}
```

## 4. 命令与示意输出
```
$ python3 $S/scripts/svgfig.py build figure_spec.json figure.svg          -> no warnings (16 elements)
$ timeout 300 python3 $S/scripts/export_check.py render figure.svg --dpi 600  -> canvas 321 x 377 px (= 85 mm), PDF 字体嵌入
$ python3 -c "print(12*(85*3.78/400)*0.75)"                              -> 7.2 pt 最小有效字号
$ python3 $S/scripts/svgfig.py edit figure.svg figure_v2.svg n-org-label --text "3 基质胶培养 7 天\n形成类器官"
$ python3 $S/scripts/svgfig.py diff figure.svg figure_v2.svg
  {"id": "n-org-label", "change": "text", "before": "3 基质胶培养 7 / 天 / 形成类器官", "after": "3 基质胶培养 7 天 / 形成类器官"}
$ python3 $S/scripts/export_check.py check                               -> PASS
```
`result.json`（示例，节选）：
```json
{"case_id": "example-02", "status": "complete",
 "export": {"width": "85 mm", "dpi": 600, "min_font_pt": 7.2, "pdf": "vector, fonts embedded"},
 "change_log": [{"version": "v2", "type": "演示编辑（标签换行修正），不属于正式图"}]}
```
