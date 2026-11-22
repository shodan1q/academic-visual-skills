# 交付前自检清单（科研关系示意图）

脚本能查的先让脚本查：`svgfig.py build` 无 WARN → `pixcheck.py` PASS → `export_check.py check` PASS。下面是脚本查不到、要对着原文人工过一遍的项（结论写进 compliance_checks 或 exceptions）。

## 实体（对照原文和 figure_content_map.json 的 entities）
- [ ] 图上每个节点都能在原文/数据表找到；图注和结果段点名的实体没有漏画（漏了就写 exceptions）。
- [ ] 没有材料以外的实体、浓度、时间点、数值、单位；表中数值由 `categories.show` 自动上图，不手抄。
- [ ] 同一实体在两个子图出现时，显示名与 `data` 键一致。

## 结构（对照 relations，含 `contains`）
- [ ] 每条 `contains` 都有原文依据（“含有/由…组成/位于”）；同级元素在同一组、同尺寸，没有被画成包含。
- [ ] 一个元素同时有“位置归属”和“类别归属”时：位置用嵌套，类别用颜色，没有混用。
- [ ] step 序号与材料顺序一致；分支、并行处理画成并排。
- [ ] 方向是因果方向；“A 被 B 抑制”画成 B ⊣ A；指向整个类群的关系连到 panel。
- [ ] “未检验”“可能”“间接”都带了 `evidence: hypothesis/indirect`，没有画成实线。

## 图例与数据
- [ ] 分类颜色来自 `canvas.categories`（CSV 实读），类别名与表一致、色块数 = 类别数；没有手挑的数据色。
- [ ] 正文与数据表矛盾时按数据表上色，矛盾写进 exceptions: contradiction。
- [ ] 灰度打印下靠线型/端点仍能区分关系类型（pixcheck 的灰度警告已处理或记录）。

## 导出与修改
- [ ] 格式、宽度 mm、dpi 与工单一致；最小字号换算成 pt 后 ≥ 工单要求。
- [ ] 修改在源上完成（spec_v2 重建；类别颜色改 categories.colors），`edit_diff.json` 只含预期改动；新版本已渲染并通过 pixcheck。
- [ ] 修改请求引入了材料没有的内容时，exceptions 有 `user_request_not_in_source`。
- [ ] result.json：全部 contract 字段齐全，status 一个词，status_reasons 与 exceptions 一致，没有“生成中”或 `<…>` 模板残留。
