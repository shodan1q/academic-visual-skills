# 最小调用示例（示例 / synthetic，内容全部虚构，不是任何正式案例的输入或结果）

## 1. 示例输入
`case.json`（示例）：
```json
{"case_id": "demo-07", "mode": "generate",
 "task": "Organise paper.pdf into a 5-minute talk for a funding review panel (non-specialist reviewers), exactly 5 slides in target-template.pptx, with notes and Q&A preparation.",
 "output_contract": {"case_id": "string", "status": "complete | partial | failed", "editable_source": "pptx path",
   "export_artifact": "pdf", "content_map": "per slide claim-source", "compliance_checks": "checks", "exceptions": "gaps"}}
```
`artifacts/slide-workorder.json`（示例）：`{"total_slides": 5, "audience": "funding review panel, mixed backgrounds", "duration_min": 5, "backup_slides_allowed": false}`
`paper.pdf`（示例）：Ce 掺杂 Co3O4 的 CO 氧化；Table 1（4 个样品 T50/转化率）、Fig. 2（50 h 稳定性）、XPS 比值、局限（未测水蒸气）。

## 2. 调用序列（约 16 次调用）
```bash
export SKILL_DIR=/skills/weekly-skill WORK_DIR=/app/work OUT_DIR=/app/output; K=$SKILL_DIR/scripts/pptx_kit.py
cat /input/case.json; find /input -maxdepth 3 -type f; cat /input/artifacts/slide-workorder.json   # 读输入
# 第 5 次调用内写 result.json 骨架（status: partial）
python3 $K paper /input/paper.pdf $WORK_DIR      # paper.txt + 各节标题 + 全部 Fig./Table 题注与页码
# 写 talk_plan.md：目标句、听众画像、时长分配、证据强度、取舍表
python3 $K inspect /input/target-template.pptx
python3 $K figcrop /input/paper.pdf 2 "Fig. 2" $WORK_DIR/fig2.png   # 题注不进图片，打印题注原文写到 caption
python3 $K build $WORK_DIR/spec.json      # 第 1 次：封面标题 3 行溢出 WARN → 缩短标题 → 第 2 次无 WARN
python3 $K render $OUT_DIR/presentation.pptx      # PDF + preview PNG + pdffonts + render.json；无 LibreOffice 时照实记录
python3 $SKILL_DIR/scripts/check_result.py --assemble      # 读 $WORK_DIR/facts.json + 磁盘文件，按含义填满 contract 每个键
# 写 qa_prep.md、content_map.json、change_log.md，填 result.json
python3 $SKILL_DIR/scripts/check_result.py --paper $WORK_DIR/paper.txt --template /input/target-template.pptx --slides 5   # 最后跑：判定行写回 result.json
```

## 3. 示意输出（示例，节选）
`talk_plan.md`（示例）：
```text
目标：让非本领域评审在 5 分钟后认可"1 wt% Ce 掺杂是降低 Co3O4 低温 CO 氧化温度的可行路线"，依据 Table 1 与 Fig. 2。
听众：跨学科评审；关心结论强度与应用价值；可能质疑：只测了干气、只有一种前驱体、无误差。
时长：封面 20 s｜结论先行 60 s｜证据 1 80 s｜证据 2 80 s｜局限 60 s = 300 s
| 内容 | 去向 | 理由 |
| Table 1 | 上页 | 核心证据 |
| XPS 比值 0.42→0.71 | 备注 + Q1 | 机理只有中等证据，非评审关注点 |
| 制备与测试条件 | 只进问答 Q5 | 非同行听众，时长不够 |
```
叙事：评审场合"结论先行"——第 2 页直接给结论，第 3、4 页给两组证据，第 5 页主动交代边界。
`qa_prep.md`（示例）：`Q3 统计：差异显著吗？ → Table 1 为 n = 3 均值，原文未给误差与检验（p.1）。翻第 3 页。`
证据页（示例）：标题"1 wt% Ce 使 T50 降低 42 °C"，上方满宽原图 Fig. 2，下方 2 条要点，出处行"Paper Fig. 2, p.2 · 证据：强（n = 3）"。
`content_map.json`（示例一行）：`{"slide": 3, "claim": "1 wt% 最优", "evidence_strength": "强", "evidence": [{"source": "paper.pdf", "locator": "Table 1 p.1"}], "seconds": 80}`
checker：`PASS: case_id ok, 7 contract fields filled, status=complete`
