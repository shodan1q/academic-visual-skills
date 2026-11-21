# 最小调用示例（示例 / synthetic，内容全部虚构，不是任何正式案例的输入或结果）

## 1. 示例输入
case 文件（示例）：
```json
{"case_id": "demo-08", "task": "Adapt the 9-slide starting deck to the department template as a 10-slide, 12-minute group-meeting talk.",
 "inputs": {"paper": "paper.pdf", "starting_deck": "starting-deck.pptx", "template": "target-template.pptx", "workorder": "artifacts/slide-workorder.json"},
 "output_contract": {"editable_presentation": "...", "slide_evidence_map": "...", "render_and_version_record": "...",
                     "status": "complete | partial | failed", "uncertainty": "..."}}
```
工作单（示例）：`{"total_slides": 10, "footer": "PKU Catalysis Group 2026", "slide_numbers": true, "min_body_pt": 18, "rules": ["facts must match paper.pdf", "fill the 'Source note' placeholder (idx 13)"]}`

材料（示例）：
- `target-template.pptx`：4:3，版式 PKU-Cover / PKU-Content / PKU-TwoCol / PKU-Figure…；PKU-Content 里**先**放了一个 12 pt 的 "Source note"（body idx 13），
  后面才是正文占位符（obj idx 1）；母版标题 44 pt、正文 32 pt；带两张样例页。
- `starting-deck.pptx`：旧 16:9 模板，9 页，全部是手工文本框（Arial、红色标题）；第 5 页图注写 "Fig. 3 Light-off curves"（论文里光照曲线是 Fig. 2），
  第 6 页写 "96% retained"（论文是 94%），第 7 页 9 条长要点，第 9 页没有备注；第 5 页图片被拉伸 22%。
- `paper.pdf`：3 页，有 Table 1、Fig. 2、Fig. 3 题注。

## 2. 调用序列（约 14 次调用）
```bash
export SKILL_DIR=/skills/weekly-skill WORK_DIR=/app/work OUT_DIR=/app/output; K=$SKILL_DIR/scripts/pptx_kit.py; C=$SKILL_DIR/scripts/check_result.py
cat /input/case.json; find /input -maxdepth 3 -type f; cat /input/artifacts/slide-workorder.json
python3 $C --init
python3 $K inspect /input/target-template.pptx                                   # -> template_spec.md（角色→版式→占位符、字号阶梯）
pdftotext -layout /input/paper.pdf $WORK_DIR/paper.txt                          # + 题注列表
python3 $K inspect /input/starting-deck.pptx --full > $WORK_DIR/start_text.txt; unzip -o -q /input/starting-deck.pptx 'ppt/media/*' -d $WORK_DIR/start
for w in 96 94 "Fig. 3" "Fig. 2"; do printf "%s " "$w"; grep -c -- "$w" $WORK_DIR/paper.txt; done   # 对账 -> corrections.md
python3 $K build $WORK_DIR/spec.json | tee $WORK_DIR/build.log
cd $OUT_DIR && timeout 120 soffice --headless -env:UserInstallation=file:///tmp/lo_p1 --convert-to pdf presentation.pptx
mkdir -p preview && timeout 60 pdftoppm -png -r 50 presentation.pdf preview/slide; pdffonts presentation.pdf
python3 $C --template /input/target-template.pptx --paper $WORK_DIR/paper.txt --source $WORK_DIR/start_text.txt --slides 10 --min-pt 18
```

## 3. 示意输出（示例，节选）
build 的 placed 行（示例）：
```text
placed slide 2 [PKU-Content]: title->ph title idx0 'Title 1' 9.0x1.2in 44pt; source_note->ph body idx13 'Source note' 9.0x0.4in 12pt; body->ph obj idx1 'Content Placeholder 2' 9.0x4.7in 32pt
placed slide 5 [PKU-Figure]: title->ph title idx0 'Title 1' 6.0x0.6in 20pt; source_note->ph body idx13 'Source note' 9.0x0.4in 12pt; caption->ph body idx2 'Text Placeholder 3' 6.0x0.9in 14pt
```
corrections.md（示例）：
```text
| 旧页 | deck 写法 | 论文写法 + 位置 | 处理 |
| 5 | Fig. 3 Light-off curves | 光照曲线是 Fig. 2（p.2 题注）；Fig. 3 是 100 h 稳定性 | 改为 Fig. 2 |
| 6 | 96% after 100 h | 94%（Abstract p.1；Fig. 3 题注 p.2） | 改为 94% |
| 7 | 9 条要点一页 | Sec. 3.3 + Sec. 4 | 拆成 2 页（总页数 10，正文 ≥ 18 pt） |
```
slide_audit.md（示例，checker 写出）：
```text
| slide | layout | placeholders (type:idx) | loose text boxes | picture aspect error | smallest explicit pt (body) | notes chars | words lost in PDF |
| 5 | PKU-Figure | title:0 body:13 body:2 ftr:11 sldNum:12 | - | 0% | inherit | 121 | 0 |
```
checker（示例）：
```text
template: 13 master/layout/theme parts identical to target-template.pptx
paper: 4 figure/table captions indexed; slide labels checked against them
PASS: case_id ok, 5 contract fields filled, status=complete
```
反例（示例）：照搬旧 deck 文字 →
```text
FAIL: numbers on slides that come from the old deck but NOT from the paper (...): s6:96
FAIL: slide 5: 'Fig. 3  Light-off curves of the four catalysts' reads like paper Fig. 2 ('Fig. 2. CO conversion versus temperature (light-of'), not Fig. 3
FAIL: slide 5: picture stretched (aspect off by 22%) -> scale proportionally          # 直接交旧 deck 时
FAIL: template parts changed or missing in deck: ['ppt/slideLayouts/slideLayout2.xml', ...]
```
