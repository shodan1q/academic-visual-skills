# PPTX 标准库速查（zipfile + 字符串编辑，已在本机实测）

`pptx_kit.py` 已覆盖：看模板（inspect）、按版式建页、保留/重排/删除原页（keep）、跨 run 文字替换（replace）、备注、
图片等比放置、三线表、页脚页码、图表裁剪（figcrop）。只有它做不到的细节才用下面的手工配方。

## 1. 包结构（只需记这些）
| 部件 | 作用 | 注意 |
|---|---|---|
| `[Content_Types].xml` | 每个部件的类型 | 新增 slide/notesSlide/图片扩展名都要登记；`.potx` 主部件类型是 `template.main+xml`，存成 .pptx 要改成 `presentation.main+xml` |
| `ppt/presentation.xml` | `p:sldIdLst` 决定页序 | `p:sldId id` ≥ 256 且唯一；顺序：sldMasterIdLst → notesMasterIdLst → sldIdLst → sldSz |
| `ppt/_rels/presentation.xml.rels` | rId → slides/… | Id 唯一；删页要同时删这里的 Relationship |
| `ppt/slides/slideN.xml` + `_rels/slideN.xml.rels` | 页面；rels 指向版式、图片、备注 | 占位符 `<p:ph type=".." idx=".."/>` 必须与版式里的 type/idx 一致才会继承位置和字号 |
| `ppt/slideLayouts/`、`ppt/slideMasters/`、`ppt/theme/` | 模板本体 | **不要改**：改了就不是"套用模板"了；checker 会逐字节比对 |
| `ppt/notesSlides/` + `ppt/notesMasters/` | 讲稿备注 | notesSlide 必须指向 notesMaster；模板没有 notesMaster 时 kit 会补一个最小的 |

## 2. 安全编辑一个部件（通用函数）
```python
import zipfile, shutil, re
def edit_part(src, dst, part, fn):
    """Copy src->dst with one part transformed by fn(str)->str. Order and other bytes untouched."""
    with zipfile.ZipFile(src) as zi, zipfile.ZipFile(dst + ".tmp", "w", zipfile.ZIP_DEFLATED) as zo:
        for it in zi.infolist():
            data = zi.read(it.filename)
            if it.filename == part:
                data = fn(data.decode("utf-8")).encode("utf-8")
            zo.writestr(it, data)
    shutil.move(dst + ".tmp", dst)

# 例：把第 3 页里的 "92.4%" 改成 "92.4 %"（同一个 run 内的文字）
edit_part("v1.pptx", "v2.pptx", "ppt/slides/slide3.xml", lambda x: x.replace(">92.4%<", ">92.4 %<"))
```
跨 run 的文字（"图" + "3"）用 kit 的 `{"keep": 3, "replace": {...}}`，它会合并段内 run 再替换。

## 3. 命名空间安全（最常见的"文件打不开"原因）
- **不要**用 `ElementTree.tostring()` 重写 `[Content_Types].xml`、`*.rels`、slide XML：它会把前缀改成 `ns0:`、丢掉 `mc:Ignorable`
  声明的命名空间，PowerPoint 报修复、LibreOffice 可能丢内容。
- 非用不可时先注册全部前缀：`ET.register_namespace("a", A); ET.register_namespace("p", P); ET.register_namespace("r", R)`……
  并检查原文件根元素上的每个 `xmlns:*` 都还在。更省事的做法是**只做字符串插入/替换**（kit 就是这么做的）。
- `ET.fromstring(data)` 只用来**检查**是否良构，可以放心用。

## 4. 常用片段（字符串级）
```python
# 文字 run（中文 + 加粗 + 字号 20pt）
'<a:r><a:rPr lang="zh-CN" altLang="en-US" sz="2000" b="1"/><a:t>%s</a:t></a:r>' % xml.sax.saxutils.escape(text)
# 二级要点段落
'<a:p><a:pPr lvl="1"/>' + run + '</a:p>'
# 占位符形状（位置与字号从版式继承：spPr 留空）
'<p:sp><p:nvSpPr><p:cNvPr id="3" name="Content"/><p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr><p:nvPr><p:ph idx="1"/></p:nvPr></p:nvSpPr><p:spPr/><p:txBody><a:bodyPr/><a:lstStyle/>' + paras + '</p:txBody></p:sp>'
# 页码字段（渲染器会重算，缓存值写当前页号）
'<a:fld id="{B6F15528-21DE-4FAA-801E-634DDDAF4B2B}" type="slidenum"><a:rPr lang="en-US"/><a:t>3</a:t></a:fld>'
```
EMU：1 英寸 = 914400，1 pt = 12700。同一页内 `cNvPr id` 不能重复。

## 5. 换图（保持引用关系）
图片部件按 rels 找：`ppt/slides/_rels/slide5.xml.rels` 里 `Target="../media/image3.png"`。直接覆盖 `ppt/media/image3.png`
会改动**所有**引用它的页（先 `grep -l image3 ppt/slides/_rels/*`）。新图宽高比不同 → 同时改该 `p:pic` 的 `a:ext cx/cy`，否则被拉伸。
更稳：在 spec 里用 `image` 重建这一页。

## 6. 导出与核对
```bash
timeout 120 soffice --headless -env:UserInstallation=file:///tmp/lo_profile --convert-to pdf --outdir $OUT_DIR $OUT_DIR/presentation.pptx
timeout 60 pdftoppm -png -r 50 $OUT_DIR/presentation.pdf $OUT_DIR/preview/slide    # 每页一张
pdffonts $OUT_DIR/presentation.pdf      # 实际嵌入/替代的字体，照实写进渲染记录
pdftotext -f 3 -l 3 $OUT_DIR/presentation.pdf -   # 第 3 页渲染后的文字；与页面文字比对可发现被裁掉的字
```
- soffice 卡住：profile 目录换一个新的（`/tmp/lo_profile2`）再试一次；还是失败就照实记录。
- "Task policy set failed" 是 macOS 无害提示。
- PDF 页数必须等于幻灯片数；不等说明导出的是旧文件或转换失败。
