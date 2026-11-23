# 最小调用示例（示例 / synthetic，内容全部虚构，不是任何正式案例的输入或结果）

## 1. 示例输入（/input 下）
`case.json`（示例）：
```json
{"case_id": "demo-06", "mode": "generate",
 "task": "Turn paper.pdf into a 6-slide group-meeting talk (6 min) in target-template.pptx with speaker notes.",
 "output_contract": ["case_id", "status", "editable_source", "export_artifact", "content_map", "compliance_checks", "exceptions"]}
```
`artifacts/slide-workorder.json`（示例）：
```json
{"total_slides": 6, "audience": "group meeting", "duration_min": 6, "language": "zh-CN", "notes_required": true,
 "template": "target-template.pptx", "source_preservation": "numbers and figure numbers exactly as in paper.pdf"}
```
`paper.pdf`（示例论文，2 页）：Ce 掺杂 Co3O4 的 CO 氧化；Table 1 给 4 个样品的 T50 与 250 °C 转化率；Fig. 2 为 50 h 稳定性；
第 4 节写了局限（未测水蒸气）。`target-template.pptx`：11 个标准版式（标题幻灯片、标题和内容、两栏内容……）。

## 2. Agent 的调用序列（约 15 次调用）
```bash
export SKILL_DIR=/skills/weekly-skill WORK_DIR=/app/work OUT_DIR=/app/output; K=$SKILL_DIR/scripts/pptx_kit.py
cat /input/case.json; find /input -maxdepth 3 -type f; cat /input/artifacts/slide-workorder.json   # 1 读输入
python3 - <<'PY'                                                  # 2 第 5 次调用内写骨架
import json; c = json.load(open("/input/case.json"))
r = {"case_id": c["case_id"], "status": "partial"}; r.update({k: "pending" for k in c["output_contract"] if k not in r})
json.dump(r, open("/app/output/result.json", "w"), ensure_ascii=False, indent=1)
PY
python3 $K paper /input/paper.pdf $WORK_DIR                       # 3 paper.txt + 节标题 + 全部题注与页码
python3 $K inspect /input/target-template.pptx                    # 4 版式与占位符
# 5 写 storyline.md / plan.md（问题→方法→Table 1→Fig. 2→结论与局限）
python3 $K figcrop /input/paper.pdf 2 "Fig. 2" $WORK_DIR/fig2.png  # 6 原图（去白边；题注打印出来写进 caption）
python3 $K build $WORK_DIR/spec.json                              # 7 建页（无 WARN）
python3 $K render $OUT_DIR/presentation.pptx      # PDF + preview PNG + pdffonts + render.json；无 LibreOffice 时照实记录
python3 $SKILL_DIR/scripts/check_result.py --assemble      # 读 $WORK_DIR/facts.json + 磁盘文件，按含义填满 contract 每个键
python3 $SKILL_DIR/scripts/check_result.py --paper $WORK_DIR/paper.txt --template /input/target-template.pptx --min-pt 18 --slides 6   # 9 自检
```

`spec.json`（示例节选）：
```json
{"template": "/input/target-template.pptx", "out": "/app/output/presentation.pptx", "footer": "组会汇报", "slide_numbers": true,
 "slides": [
  {"layout": "标题幻灯片", "title": "Ce 掺杂 Co3O4 的低温 CO 氧化", "subtitle": "论文汇报", "notes": "开场 30 秒：……"},
  {"layout": "标题和内容", "title": "1 wt% Ce 使 T50 从 285 °C 降到 243 °C",
   "table": [["样品", "T50 (°C)", "X250 (%)"], ["Co3O4", "285", "61.0"], ["1Ce", "243", "92.4"]],
   "caption": "原文 Table 1（n = 3 均值）", "notes": "先看 1Ce 一行，再指出 2Ce 反而变差；被问误差：原文只给均值。"},
  {"layout": "标题和内容", "title": "1Ce 在 250 °C 下 50 h 不失活", "body": ["XPS：O_ads/O_latt **0.42 → 0.71**"],
   "image": "/app/work/fig2.png", "caption": "原文 Fig. 2：250 °C 稳定性，50 h", "source_note": "Paper Fig. 2, Sec. 3, p.2",
   "notes": "氧空位是作者解释，证据强度中等。"}]}
```
宽图（宽高比 ≥ 1.45）配 body 时 build 打印 `stacked: visual on top (9.0x3.6in), body below`：图满宽在上，要点在下。

## 3. 示意输出（示例，节选）
build 打印：
```text
slide 4/6 [标题和内容] 1 wt% Ce 使 T50 从 285 °C 降到 243 °C | notes 51 chars
package integrity OK (all XML well-formed, all relationship targets exist)
```
`result.json`（示例节选）：
```json
{"case_id": "demo-06", "status": "complete",
 "editable_source": {"pptx": "/app/output/presentation.pptx", "spec": "/app/output/spec.json", "rebuild": "python3 pptx_kit.py build spec.json", "slides": 6},
 "export_artifact": {"pdf": "/app/output/presentation.pdf", "pages": 6, "fonts": "Arial; 中文为渲染机替代字体 PingFang SC"},
 "content_map": [{"slide": 4, "role": "结果1", "claim": "1 wt% Ce 使 T50 从 285 °C 降到 243 °C",
   "evidence": [{"source": "paper.pdf", "locator": "Table 1, p.1"}], "numbers": ["285", "243", "61.0", "92.4"],
   "visual": "原生表格（Table 1 数值逐格抄录）", "confidence": "high"}],
 "compliance_checks": [{"check": "页数 = 6", "result": "PASS"},
   {"check": "模板继承", "result": "PASS", "basis": "14 个母版/版式/主题部件与模板逐字节一致"},
   {"check": "数字回查", "result": "PASS", "basis": "slide 上所有数字均出现在 paper.txt"}],
 "exceptions": {"material_gaps": [], "undecidable": ["氧空位机理仅 XPS 支持"], "run_failures": []}}
```
checker 输出：`PASS: case_id ok, 7 contract fields filled, status=complete`
