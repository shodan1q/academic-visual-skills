# 最小调用示例（示例 / synthetic，内容全部虚构，不是任何正式案例的输入或结果）

## 1. 示例输入
`case.json`（示例）：
```json
{"case_id": "demo-08", "mode": "adapt",
 "task": "Adapt starting-deck.pptx (old template) to target-template.pptx. Keep all 6 slides, their content, figure numbers and speaker notes; every slide must inherit a target layout; footer and slide numbers on every slide; export PDF.",
 "output_contract": ["case_id", "status", "editable_source", "export_artifact", "content_map", "compliance_checks", "exceptions"]}
```
`artifacts/slide-workorder.json`（示例）：`{"total_slides": 6, "mode": "adapt", "footer": "组会汇报 · 新模板", "slide_numbers": true, "min_body_pt": 18}`
`starting-deck.pptx`（示例）：旧设计模板（版式 "Focus"/"Focus2"），6 页：封面、问题、方法、Table 1（表格）、Fig. 2（图片+图注）、结论；每页有备注。
`target-template.pptx`（示例）：11 个标准版式（标题幻灯片、标题和内容、图片与标题……），母版标题 40 pt、正文 24 pt。

## 2. 调用序列（约 14 次调用）
```bash
export SKILL_DIR=/skills/weekly-skill WORK_DIR=/app/work OUT_DIR=/app/output; K=$SKILL_DIR/scripts/pptx_kit.py
cat /input/case.json; find /input -maxdepth 3 -type f; cat /input/artifacts/slide-workorder.json
# 第 5 次调用内写 result.json 骨架
python3 $K inspect /input/target-template.pptx                          # → template_spec.md
python3 $K inspect /input/starting-deck.pptx --full > $WORK_DIR/start_text.txt
unzip -o /input/starting-deck.pptx 'ppt/media/*' -d $WORK_DIR/start     # 原图
# 写 layout_map.md（6 行，每页一行）和 spec.json
python3 $K build $WORK_DIR/spec.json
cd $OUT_DIR && timeout 120 soffice --headless -env:UserInstallation=file:///tmp/lo_profile --convert-to pdf presentation.pptx
mkdir -p preview && timeout 60 pdftoppm -png -r 50 presentation.pdf preview/slide; pdffonts presentation.pdf
python3 $K inspect $OUT_DIR/presentation.pptx | grep -c "ph:sldNum"     # 批量一致性：应为 6
python3 $SKILL_DIR/scripts/check_result.py --template /input/target-template.pptx --slides 6 --source $WORK_DIR/start_text.txt
```

## 3. 示意输出（示例，节选）
`layout_map.md`（示例）：
```text
| 原页 | 内容 | 目标版式 | 标题→ | 正文/图/表→ | 说明 |
| 1 | 封面 | 标题幻灯片 | ctrTitle | — | |
| 4 | Table 1 | 标题和内容 | title | 原生三线表，obj 区域 | 数值逐格照抄 |
| 5 | Fig. 2 + 图注 | 图片与标题 | title | pic 占位符容器，等比 | 图注保留 "Fig. 2" |
```
build：`package integrity OK (all XML well-formed, all relationship targets exist)`
checker：
```text
template: 14 master/layout/theme parts identical to target-template.pptx
PASS: case_id ok, 7 contract fields filled, status=complete
```
反例（示例）：把旧 deck 直接改名交付 → `FAIL: template parts changed or missing in deck: ['ppt/slideLayouts/slideLayout4.xml', ...]`
