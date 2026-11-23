# 交付前自检清单（机制图 / 通路图）

脚本能查的先让脚本查：`svgfig.py build` 的 WARN 改过（最多两轮，剩下的记 exceptions）→ `pixcheck.py` 的提示看过 → `export_check.py assemble` 末尾 check 无 FAIL。下面是脚本查不到、要对着原文人工过一遍的项（结论写进 compliance_checks 或 exceptions）。

## 实体（对照原文和 figure_content_map.json 的 entities）
- [ ] 图上每个节点都能在原文/数据表找到；原文图注和结果段里点名的分子没有漏画（漏了就写 exceptions）。
- [ ] `kind` 判对：基因 vs mRNA vs 蛋白 vs 复合物 vs 家族；同一个符号在材料里既指基因又指蛋白时，按句子语境分别建节点。
- [ ] 物种写法一致（人 *TP53*/p53；小鼠 *Trp53*/p53）；同义名、旧名只进 `aliases`。
- [ ] 同一分子在两个区室各有一个节点，`comp` 正确；跨膜蛋白在膜带上。

## 关系（对照 relations）
- [ ] 方向是因果方向；“A 被 B 抑制”画成 B ⊣ A。
- [ ] 措辞到 type 的映射符合 SKILL.md 表格；修饰位点只写原文给出的。
- [ ] “仅过表达”“未检验是否直接”“可能”都带了 `evidence: indirect/hypothesis`，没有画成实线。
- [ ] transport 只连同一实体的两个副本；转录诱导用 activate 指向基因。
- [ ] 反馈环、并行分支都在，并且画在侧边、不横穿主链。

## 图例与数据
- [ ] 颜色来自 `canvas.colorscale`（CSV 实读），没有手挑的数据色；分档和单位写在图例标题。
- [ ] 正文与数据表矛盾时按数据表上色，矛盾写进 exceptions: contradiction。
- [ ] 灰度打印下靠线型/端点仍能区分关系类型。

## 导出与修改
- [ ] 格式、宽度 mm、dpi 与工单一致；最小字号换算成 pt 后 ≥ 工单要求。
- [ ] 修改在源上完成（spec_v2 重建或 edit），`edit_diff.json` 只含预期改动，旧 id 基本全部保留；新版本已渲染，pixcheck 提示看过。
- [ ] 修改请求引入了材料没有的内容时，exceptions 有 `user_request_not_in_source`。
- [ ] result.json（assemble 生成）：每个 contract 字段都有内容、无“生成中”，status 一个词，status_reasons 与 exceptions 一致，notes.json 里没有 `<…>` 模板残留。
