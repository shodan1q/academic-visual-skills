# 最小调用示例（示例 / synthetic，不是正式案例结果）

以下材料、数值与输出全部为说明接口而虚构（一段合成的人巨噬细胞 cGAS–STING 机制描述）。

## 1. 示例输入
```json
{"caseId": "SIM04-C-CGAS-STING", "output_contract": {"required": ["case_id", "status", "editable_source", "export_artifact", "content_map", "compliance_checks", "exceptions"]}}
```
工单（示例）：`{"task": "cGAS-STING-TBK1-IRF3 axis and the TRIM21 feedback in human macrophages", "must_show": ["compartments incl. ER, Golgi, nucleus, plasma membrane", "arrow semantics with legend", "feedback loop", "gene vs protein naming (human)", "uncertain or overexpression-only relations visibly different"]}`；另有 `source/paper.pdf`（610 行文本）和 `data/tableS1.csv`（`symbol,log2FC_ISD_6h,padj`）。

## 2. 第一条命令
`python3 $S/scripts/run.py start` 输出输入清单与 sha256、工单、`/app/work/src.txt` 中提到工单术语的段落（带行号，如 `  42| At the Golgi, STING co-immunoprecipitated with TBK1 …`）、术语行号索引和数据表各行。

## 3. 规格（示例，节选）与第二条命令
```
title: cGAS-STING-TBK1-IRF3 signalling and TRIM21 feedback in human macrophages @1
color: tableS1.csv | symbol | log2FC_ISD_6h | 1,3,6 | log2FC, ISD 6 h vs mock (Table S1)
comp cy: Cytosol @24
comp go in cy: Golgi @36
comp nu: Nucleus @48
node stinggo: STING | protein | go | mods=P | alias=TMEM173 @36
node tbk1: TBK1 | protein | go @42
node irf3c: IRF3 | protein | cy | mods=P @44
node irf3n: IRF3 | protein | nu @48
node ifnb1: IFNB1 | gene | nu @51
node trim21p: TRIM21 | protein | cy @63
node cgas: cGAS | protein | cy @24
edge tbk1 -> irf3c | modify | +P S396 @44
edge irf3c -> irf3n | transport | nuclear entry @48
edge irf3n -> ifnb1 | activate | transcription @50
edge trim21p -| stinggo | inhibit | +Ub K288, degradation | feedback @64-65
edge trim21p -| cgas | inhibit | overexpression only | hypothesis @67-69
req: feedback loop | pass | e-trim21p-stinggo | L57-67
exc: undecidable | STING→NF-kB branch not tested (L81-82) | not drawn
```
```
$ python3 $S/scripts/run.py build /app/work/figure.txt
spec: 6 compartments, 15 nodes, 17 edges, 6 checks, 3 exceptions, 0 edit(s); width 180 mm, min font 6 pt, 300 dpi
[0s] build figure.svg: ok      wrote figure.svg … (15 entities, 17 relations, 17 legend items; smallest text 7.0 pt)
[3s] render figure.svg: ok     png_method=magick, pdf_method=soffice
[7s] result.json (first complete version): ok
[7s] build figure_v2.svg (1 edit(s), demonstration): ok     diff: 161 ids kept, 160 unchanged
   source trace: 38/38 src pointers resolved to verbatim quotes; 14/15 entity names occur in their cited lines
   PASS: 7 contract field(s), status=partial, 0 fail / 0 warn
DONE in 13s -> /app/output: figure.svg, figure.png, figure.pdf, figure_spec.json, figure_content_map.json, … result.json
```
示例里状态为 partial，是因为有一条 req 写的是 partial（工单没给宽度，用了默认值）。

## 4. result.json 节选（示例）
```json
{"case_id": "SIM04-C-CGAS-STING", "status": "partial",
 "status_reasons": ["workorder item not fully met: deliverables editable SVG + PNG + PDF, single-column width"],
 "content_map": {"relations": [{"id": "e-trim21p-cgas", "type": "inhibit", "evidence": "hypothesis", "src": "src.txt:L67-L69", "quote": "… In overexpression experiments TRIM21 also reduced cGAS protein levels …", "page": 2}]},
 "change_log": [{"version": "v2", "request": "demonstration edit (not part of the official figure …)", "kept_ids": 161, "unchanged_ids": 160}]}
```
