# 最小调用示例（示例 / synthetic，内容全部虚构，不是任何正式案例的输入或结果）

## 1. 示例输入（/input 下）
`case.json`（示例）：`{"case_id": "demo-09", "output_contract": ["case_id", "status", "editable_source", "export_artifact", "content_map", "compliance_checks", "exceptions"]}`
`artifacts/slide-workorder.json`（示例）：
```json
{"mode": "edit", "total_slides": 6, "template_inheritance": "keep starting-deck masters/layouts",
 "source_preservation": "slides 1, 2 and 4 unchanged", "audience": "group meeting", "duration_min": 6,
 "edits": ["E1: compress slide 3 (methods) to at most 3 bullets",
           "E2: insert a new slide after slide 4 showing the 50 h stability result from Fig. 2 of paper.pdf",
           "E3: rewrite the conclusion slide to also state the main limitation"]}
```
`starting-deck.pptx`（示例，5 页：封面、问题、方法 5 条、Table 1、结论）、`target-template.pptx`、`paper.pdf`（示例论文，Fig. 2 在第 2 页）。

## 2. 调用序列（6 次调用；底层命令见各脚本文件头）
```bash
export SKILL_DIR=/skills/weekly-skill WORK_DIR=/app/work OUT_DIR=/app/output
F=$SKILL_DIR/scripts/deck_flow.py; K=$SKILL_DIR/scripts/pptx_kit.py
python3 $F start                                    # 输入清单、工作单全文、模板版式、初始稿逐页内容、论文文字与题注、预检；写 result.json 骨架
python3 $K figcrop /input/paper.pdf 2 "Fig. 2" $WORK_DIR/fig2.png
# 写 $WORK_DIR/plan.md 与 $WORK_DIR/spec_v1.json
python3 $F build $WORK_DIR/spec_v1.json             # 构建 + diff_v0_v1.txt + 复制到 $OUT_DIR/presentation.pptx
# 写 $WORK_DIR/facts.json（content_map、instructions_done、exceptions、uncertainty）与 change_log.md
python3 $F finish --slides 6 --keep-map 1:1,2:2,4:4 --edit-map 3:3,6:5     # 渲染成稿与初始稿、记录、result.json、checker（最后跑）
```
`spec_v1.json`（示例）：
```json
{"template": "/app/work/v0.pptx", "out": "/app/work/v1.pptx", "footer": "组会汇报", "slide_numbers": true,
 "slides": [{"keep": 1}, {"keep": 2},
  {"layout": "标题和内容", "title": "方法：共沉淀制备 4 个 Ce 负载量",
   "body": ["Ce 负载 0、0.5、1、2 wt%，400 °C 焙烧 4 h", "1% CO / 20% O2 / N2，GHSV 30,000 mL g-1 h-1", "每个条件重复 n = 3"], "notes": "E1 …"},
  {"keep": 4},
  {"layout": "标题和内容", "title": "1Ce 在 250 °C 下 50 h 不失活", "image": "/app/work/fig2.png", "caption": "原文 Fig. 2", "notes": "E2 …"},
  {"keep": 5, "replace": {"保持 50 h": "保持 50 h；局限：未测水蒸气条件"}, "notes": "E3 …"}]}
```

## 3. 示意输出（示例，节选）
`diff_v0_v1.txt`（示例）：
```diff
-   [ph:obj] Ce 负载：0、0.5、1、2 wt%
-   [ph:obj] 400 °C 焙烧 4 h
+   [ph:obj] Ce 负载 0、0.5、1、2 wt%，400 °C 焙烧 4 h
+   [ph:title] 1Ce 在 250 °C 下 50 h 不失活
+   [picture] ppt/media/kit_s5_0.png
-   [ph:obj] 保持 50 h
+   [ph:obj] 保持 50 h；局限：未测水蒸气条件
```
`change_log.md`（示例一行）：`| v1 | E3 | 6 | 保持 50 h | 保持 50 h；局限：未测水蒸气条件 | 原文 Sec.4 | 去掉 replace |`
`result.json`（示例节选）：
```json
{"case_id": "demo-09", "status": "complete",
 "editable_source": {"pptx": "/app/output/presentation.pptx", "mode": "edit", "slides": 6, "template": "starting-deck.pptx"},
 "export_artifact": {"pdf": "/app/output/presentation.pdf", "pages": 6},
 "compliance_checks": [{"check": "E1/E2/E3 执行", "result": "PASS", "basis": "versions/diff_v0_v1.txt"},
                       {"check": "保留页 1/2/4 文字未变", "result": "PASS", "basis": "diff 仅页码与计划内改动"}],
 "exceptions": {"material_gaps": [], "undecidable": [], "run_failures": []}}
```
checker：`template: 14 master/layout/theme parts identical to starting-deck.pptx` / `result.json: 15 check rows written to 'compliance_checks' + checker_record` / `PASS: case_id ok, 7 contract fields filled, status=complete`
