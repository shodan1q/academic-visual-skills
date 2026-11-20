# 设计说明与内部自测记录（内部材料，不含任何正式评分）

> 只记录维护者在本机真实做过的事。案例是自己编写的**合成案例**，不是平台正式案例；没有做"不加载 Skill 的基础 Agent"
> 对照运行，因此不给任何增益数字，也不推测正式分数。

## 1. 依据与设计取舍
- 题包公开的接口说明（dataset 里的 output-contract.md 与 example-input.json）写明：运行时读 case.json、material.json、
  artifacts/slide-workorder.json，正式案例提供真实的 target-template.pptx 与 starting-deck.pptx；交付 `/app/output/presentation.pptx`、
  真实 PDF、计划/主张-来源/时间/修改记录和带全部根字段的 result.json；要读准 mode、总页数、source preservation 与 template inheritance。
  示例 contract 根字段：case_id、status、editable_source、export_artifact、content_map、compliance_checks、exceptions。SKILL.md 按这些名字给了映射。
- "改一页时顺手改坏母版和后面所有页"是本题点名的失败。所以编辑走 **keep 模式**：未点名的页 XML 原样复制，母版/版式/主题不动；
  每轮用 `inspect --full` 生成可读文字快照并 `diff`，改动是否只落在指令点名的页一目了然，也是 compliance_checks 的依据。
- 版本 = spec 文件。回退就是用上一版 spec 重建，结果确定，不依赖撤销历史。
- 文件生成用纯标准库 `pptx_kit.py`（环境不一定有 python-pptx），与 06/07/08 共用同一份代码。

## 2. 规则 → 针对的失败模式
| 题面列出的失败 | 对应做法 |
|---|---|
| 摘要或段落整段塞进文本框 | 编辑规则 1；溢出 WARN 必须清零 |
| 数字抄错或按印象取整，图注与图上标注不符 | 数字回查（论文 + 初始稿文字，小数缺失 = FAIL）；caption 写原文编号 |
| 占位图或凭空曲线 | 有数值才做原生表格，否则用 figcrop 原图，都没有就记 exception |
| 模板字体、配色、页脚被覆盖 | 只用占位符；`--template` 逐字节比对；页脚页码取版式占位符 |
| 改一页改坏母版和后面所有页 | keep 原样复制 + diff 核对；新图片换名，不覆盖保留页的媒体 |
| 导出后字体替换、文字溢出、图片被裁 | PDF 页数检查、渲染后文字比对、pdffonts 实测 |
| 多轮迭代回不到上一版、说不清交付版 | spec_vK + diff + change_log（含回退方式）；交付名固定为工作单要求 |

## 3. 本机自测（2026-11-20，macOS，LibreOffice 26.x，poppler 26.07，无 python-pptx）
| 测试 | 结果 |
|---|---|
| 合成案例 demo-09（edit 模式，5 页初始稿 → 6 页，三条指令 E1–E3，第 1/2/4 页须原样保留），维护者只按 SKILL.md 操作 | 约 16 次调用；diff 只出现 E1–E3 的改动和页码变化；PDF 6 页；checker PASS（模板 14 个部件与初始稿逐字节一致，数字全部回查到论文或初始稿） |
| 第二轮在 v1 上再插入一张图 | 发现新图与保留页图片同名会互相覆盖，已修复为自动换名（kit_s5_0 / kit_s5_1），回归通过 |
| 共用组件反例测试 | 多页、遗留提示文字、改错小数、缺备注、旧模板冒充新模板均被 checker 报出（见 06、08 的记录） |

## 4. 已知局限
- 保留页的备注部件会按原文字重建（文字不变，备注里的格式不保留）。
- 图表对象、SmartArt 只能整页保留，不能在其内部编辑。
- `pptx_kit.py` 约 370 行（inspect/build/figcrop），超过"每个脚本 ≤ 200 行"的内部目标；为单文件零依赖没有再拆。
