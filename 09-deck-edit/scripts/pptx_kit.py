#!/usr/bin/env python3
"""pptx_kit.py - stdlib-only PPTX inspect/build on a real template or starting deck (Python 3.8+, no python-pptx).

  python3 pptx_kit.py inspect FILE.pptx [--full]  # theme fonts/colours, layouts+placeholders (inches), every slide's
                                                  # shapes by role (ph:title/ph:obj/text), table rows, pictures, notes
  python3 pptx_kit.py build SPEC.json     # write the deck, print per-slide summary + overflow/placeholder/integrity warnings
  python3 pptx_kit.py figcrop paper.pdf PAGE "Fig. 2" /app/work/fig2.png [DPI]   # crop a figure (caption left out, margins trimmed) or table by its caption
  python3 pptx_kit.py render /app/output/presentation.pptx   # soffice (2 tries, 120 s each) -> PDF, 100 dpi PNGs, pdffonts, render.json

SPEC = {"template": "template.pptx|.potx|starting_deck.pptx", "out": "/app/output/deck.pptx",
        "footer": "optional footer text", "date": "optional", "slide_numbers": true,
        "slides": [
          {"keep": 3, "replace": {"old text": "new text"}, "notes": "..."},     # reuse slide 3 of the input file
          {"layout": "Title and Content" or 2, "title": "claim sentence", "subtitle": "...",
           "body": ["point", "  sub-point (2 leading spaces = level 2)", "**bold** words", "Al_{2}O_{3}, cm^{-1}"], "body2": ["right column"],
           "font_size": 20, "image": "/app/work/fig2.png", "image_box": [x, y, w, h], "caption": "Fig. 2 ...",
           "table": [["head", "head"], ["1.0", "2.0"]], "table_box": [x, y, w, h], "table_size": 14,
           "source_note": "Paper Sec. 3, Table 1, p.2",   # -> layout placeholder named Source/Note/Ref, else small textbox above footer
           "ph": {"13": ["text for placeholder idx 13"]}, "notes": "speaker notes", "source": "ignored by build"}],
        "min_pt": 18}                           # optional: WARN when body text would render below this size
Main body goes to the LARGEST body/obj placeholder (not the first one); every build prints "placed slide N: what->ph ..." - check it.
Boxes are inches. Input slides that are not kept are dropped; masters, layouts, theme and media are never rewritten.
Package files are edited as strings (no ElementTree re-serialisation), so namespaces/prefixes stay intact.
"""
import json, os, re, struct, sys, zipfile
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape, unescape

EMU, CT = 914400, "application/vnd.openxmlformats-officedocument."
NS = ('xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/'
      'officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"')
RT = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/"
GRP = '<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/>'
NOTE = re.compile(r"source|note|ref|cit|来源|出处|注释|脚注", re.I)
HEAD, FOOT = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n', ("ftr", "sldNum", "dt")
q = lambda s: escape(str(s), {'"': "&quot;"})

def rd(z, n):
    return z[n].decode("utf-8") if n in z else ""

def relpath(part):
    return os.path.dirname(part) + "/_rels/" + os.path.basename(part) + ".rels"

def rels(z, part):
    out = {}
    for m in re.finditer(r"<Relationship ([^>]*?)/?>", rd(z, relpath(part))):
        a = dict(re.findall(r'(\w+)="([^"]*)"', m.group(1)))
        t = a.get("Target", "")
        out[a.get("Id")] = (a.get("Type", "").split("/")[-1], t if a.get("TargetMode") else os.path.normpath(os.path.join(os.path.dirname(part), t)))
    return out

def phs(xml):
    out = []
    for b in re.findall(r"<p:sp>.*?</p:sp>", xml, re.S):
        ph = re.search(r"<p:ph\b([^>]*?)/?>", b)
        if ph:
            a = dict(re.findall(r'(\w+)="([^"]*)"', ph.group(1)))
            off, ext = re.search(r'<a:off x="(-?\d+)" y="(-?\d+)"', b), re.search(r'<a:ext cx="(\d+)" cy="(\d+)"', b)
            sz, nm = re.search(r'<a:lvl1pPr[^>]*>(?:(?!</a:lvl1pPr>).)*?sz="(\d+)"', b, re.S), re.search(r'<p:cNvPr [^>]*name="([^"]*)"', b)
            out.append({"type": a.get("type", "obj"), "idx": a.get("idx", "0"), "attrs": ph.group(1).strip(), "block": b,
                        "name": nm.group(1) if nm else "", "sz": int(sz.group(1)) // 100 if sz else None,
                        "box": [int(v) for v in off.groups() + ext.groups()] if off and ext else None})
    return out

def load(path):
    with zipfile.ZipFile(path) as zf:
        z = {n: zf.read(n) for n in zf.namelist()}
    pres, pr, layouts = rd(z, "ppt/presentation.xml"), rels(z, "ppt/presentation.xml"), []
    for mid in re.findall(r'<p:sldMasterId [^>]*r:id="([^"]+)"', pres):
        mp = pr[mid][1]
        for lid in re.findall(r'<p:sldLayoutId [^>]*r:id="([^"]+)"', rd(z, mp)):
            lp = rels(z, mp)[lid][1]
            nm = re.search(r'<p:cSld name="([^"]*)"', rd(z, lp))
            layouts.append({"path": lp, "master": mp, "name": unescape(nm.group(1)) if nm else os.path.basename(lp)})
    sz = re.search(r'<p:sldSz cx="(\d+)" cy="(\d+)"', pres)
    return z, [pr[r][1] for r in re.findall(r'<p:sldId [^>]*r:id="([^"]+)"', pres)], layouts, (int(sz.group(1)), int(sz.group(2))) if sz else (12192000, 6858000)

def geom(z, lay, ph):
    want = {"ctrTitle": "title", "subTitle": "body", "obj": "body", "pic": "body"}.get(ph["type"], ph["type"])
    return ph["box"] or next((m["box"] for m in phs(rd(z, lay["master"])) if m["type"] == want and m["box"]), None)

def text_of(xml):
    return ["".join(unescape(t) for t in re.findall(r"<a:t>([^<]*)</a:t>", p)) for p in re.findall(r"<a:p(?=[ >]).*?</a:p>", xml, re.S)]

def notes_of(z, slide):
    nt = [p for t, p in rels(z, slide).values() if t == "notesSlide"]
    return "\n".join(t for p in phs(rd(z, nt[0])) if p["type"] == "body" for t in text_of(p["block"])).strip() if nt else ""

def inspect(path, full=False):
    z, slides, layouts, (cx, cy) = load(path)
    print("file: %s\nslide size: %.2f x %.2f in (%d x %d EMU)" % (path, cx / EMU, cy / EMU, cx, cy))
    t = rd(z, next((n for n in sorted(z) if n.startswith("ppt/theme/theme")), ""))
    for k in ("majorFont", "minorFont"):
        f = re.search(r'<a:%s><a:latin typeface="([^"]*)"[^>]*/>(?:<a:ea typeface="([^"]*)")?' % k, t)
        print("theme %s: latin=%s ea=%s" % (k, f and f.group(1), f and f.group(2)))
    print("theme colours: " + " ".join("%s=%s" % c for c in re.findall(r'<a:(dk1|lt1|dk2|lt2|accent\d)>.*?(?:val|lastClr)="([0-9A-Fa-f]{6})"', t, re.S)))
    for mp in sorted({l["master"] for l in layouts}):
        for st in ("titleStyle", "bodyStyle"):
            s = re.search(r"<p:%s>.*?<a:lvl1pPr[^>]*>.*?sz=\"(\d+)\"" % st, rd(z, mp), re.S)
            print("%s %s lvl1 size: %s pt" % (mp, st, int(s.group(1)) // 100 if s else "?"))
    print("notes master: %s" % ("yes" if "/notesMaster\"" in rd(z, "ppt/_rels/presentation.xml.rels") else "no (build adds one)"))
    for i, l in enumerate(layouts, 1):
        print("\nlayout %d: %r (%s)" % (i, l["name"], l["path"]))
        for p in phs(rd(z, l["path"])):
            g = geom(z, l, p)
            print("   ph type=%-8s idx=%-3s box=%s sz=%s  %s" % (p["type"], p["idx"], "[%.2f, %.2f, %.2f, %.2f]" % tuple(v / EMU for v in g) if g else "inherit", p["sz"], p["name"]))
    for i, s in enumerate(slides, 1):
        sx, sr = rd(z, s), rels(z, s)
        print("\nslide %d (%s) layout=%r" % (i, s, next((l["name"] for t, p in sr.values() for l in layouts if t == "slideLayout" and l["path"] == p), "?")))
        for m in re.finditer(r"<p:sp>.*?</p:sp>|<p:pic>.*?</p:pic>|<p:graphicFrame>.*?</p:graphicFrame>", sx, re.S):
            b, ph = m.group(0), re.search(r"<p:ph\b([^>]*)", m.group(0))
            kind = "ph:" + (re.findall(r'type="(\w+)"', ph.group(1)) or ["obj"])[0] if ph else "text"
            if b.startswith("<p:pic>"):
                r = re.search(r'r:embed="([^"]+)"', b)
                print("   [picture] %s" % (sr.get(r.group(1), ("", "?"))[1] if r else "?"))
            elif "<a:tbl>" in b:
                for tr in re.findall(r"<a:tr .*?</a:tr>", b, re.S):
                    print("   [table] " + " | ".join(" ".join(text_of(tc)) for tc in re.findall(r"<a:tc>.*?</a:tc>", tr, re.S)))
            else:
                for pp in re.findall(r"<a:p(?=[ >]).*?</a:p>", b, re.S):
                    t, lv = "".join(text_of(pp)), re.search(r'lvl="(\d)"', pp)
                    if t.strip():
                        print("   [%s] %s%s" % (kind, "  " * int(lv.group(1) if lv else 0), t if full else t[:110]))
        n = notes_of(z, s)
        print("   [notes] " + ((n if full else n[:160]).replace("\n", " / ") if n else "(none)"))

def runs(text, sz=None):
    """**bold**, H_{2}O subscript, cm^{-1} / Ce^{3+} superscript (the markup never reaches the slide text)."""
    out, bold = [], False
    for g in re.split(r"(\*\*|_\{[^{}]*\}|\^\{[^{}]*\})", str(text)):
        if g == "**":
            bold = not bold
            continue
        base = ' baseline="-25000"' if g.startswith("_{") else ' baseline="30000"' if g.startswith("^{") else ""
        g = g[2:-1] if base else g
        if g:
            out.append('<a:r><a:rPr lang="zh-CN" altLang="en-US"%s%s%s dirty="0"/><a:t>%s</a:t></a:r>' % (' sz="%d"' % (sz * 100) if sz else "", ' b="1"' if bold else "", base, escape(g)))
    return "".join(out) or '<a:endParaRPr lang="zh-CN"/>'

def items_of(items):
    items = items.split("\n") if isinstance(items, str) else items
    return [(i[0], i[1]) if isinstance(i, (list, tuple)) else ((len(i) - len(i.lstrip(" "))) // 2, i.strip()) for i in items]

def paras(items, sz=None):
    return "".join('<a:p>%s%s</a:p>' % ('<a:pPr lvl="%d"/>' % l if l else "", runs(t, sz)) for l, t in items_of(items))

def xfrm(b):
    return '<a:xfrm><a:off x="%d" y="%d"/><a:ext cx="%d" cy="%d"/></a:xfrm>' % tuple(int(v) for v in b)

def fit_warn(n, what, items, box, sz):
    """Rough, deliberately conservative overflow estimate: CJK 1.05 em, latin 0.62 em, titles x0.9 (calibrated on LibreOffice renders), line 1.2 em, 0.25 in indent per level."""
    if box and items:
        wpt, hpt = box[2] / 12700.0 - 14, box[3] / 12700.0 - 7
        lines = sum(max(1, -(-sum(1.05 if ord(c) > 0x2e80 else 0.62 for c in t.replace("**", "")) * sz * (0.9 if what == "title" else 1) // max(wpt - 18 * l, 40))) for l, t in items_of(items))
        if lines * sz * 1.2 > hpt * (1.35 if what == "title" else 1) or (what == "title" and lines > 2):  # renderers let 2-line titles spill into the margin
            print("WARN slide %d %s: ~%d lines at %dpt need %.0fpt but box is %.0fpt high -> shorten, split slide or pick a bigger layout" % (n, what, lines, sz, lines * sz * 1.2, hpt))

def imgsize(data):
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return struct.unpack(">II", data[16:24])
    i = 2
    while data[:2] == b"\xff\xd8" and i < len(data) - 9:
        if data[i + 1] in (0xC0, 0xC1, 0xC2):
            h, w = struct.unpack(">HH", data[i + 5:i + 9])
            return w, h
        i += 2 + struct.unpack(">H", data[i + 2:i + 4])[0]
    print("WARN unknown image size (use PNG/JPEG); assuming 4:3")
    return 4, 3

def rep(xml, old, new):
    """Replace text inside paragraphs even when it is split across runs (merged into the paragraph's first run)."""
    hit = [0]
    def fp(m):
        p, ts = m.group(0), re.findall(r"<a:t>([^<]*)</a:t>", m.group(0))
        full = "".join(unescape(t) for t in ts)
        if old not in full:
            return p
        hit[0] += 1
        if any(escape(old) in t for t in ts):
            return re.sub(r"<a:t>([^<]*)</a:t>", lambda t: "<a:t>%s</a:t>" % t.group(1).replace(escape(old), escape(new)), p)
        k = iter(range(10 ** 6))
        return re.sub(r"<a:t>[^<]*</a:t>", lambda t: "<a:t>%s</a:t>" % (escape(full.replace(old, new)) if next(k) == 0 else ""), p)
    return re.sub(r"<a:p(?=[ >]).*?</a:p>", fp, xml, flags=re.S), hit[0]

def relxml(items):
    return "".join('<Relationship Id="%s" Type="%s%s" Target="%s"/>' % (i, RT, t, g) for i, t, g in items)

def wrap_rels(items):
    return HEAD + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' + relxml(items) + "</Relationships>"

def add_notes_master(z, layouts, prels, pres, ctx):
    th = next(p for t, p in rels(z, layouts[0]["master"]).values() if t == "theme")
    tn = "ppt/theme/theme%d.xml" % (1 + sum(1 for n in z if n.startswith("ppt/theme/theme")))
    z[tn] = z[th]
    sp = ('<p:sp><p:nvSpPr><p:cNvPr id="%d" name="%s"/><p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr><p:nvPr><p:ph type="%s" idx="%d"/></p:nvPr></p:nvSpPr>'
          '<p:spPr>%s<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr>%s</p:sp>')
    clr = " ".join('%s="%s"' % (a, b) for a, b in zip("bg1 tx1 bg2 tx2".split(), "lt1 dk1 lt2 dk2".split())) + " " + " ".join('%s="%s"' % (a, a) for a in "accent1 accent2 accent3 accent4 accent5 accent6 hlink folHlink".split())
    z["ppt/notesMasters/notesMaster1.xml"] = (HEAD + '<p:notesMaster %s><p:cSld><p:spTree>%s%s%s</p:spTree></p:cSld><p:clrMap %s/></p:notesMaster>' % (NS, GRP,
        sp % (2, "Slide Image", "sldImg", 2, xfrm([381000, 685800, 6096000, 3429000]), ""),
        sp % (3, "Notes", "body", 3, xfrm([685800, 4400550, 5486400, 3600450]), '<p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:endParaRPr lang="zh-CN"/></a:p></p:txBody>'), clr)).encode("utf-8")
    z["ppt/notesMasters/_rels/notesMaster1.xml.rels"] = wrap_rels([("rId1", "theme", "../theme/" + os.path.basename(tn))]).encode("utf-8")
    prels = prels.replace("</Relationships>", relxml([("rIdKitNM", "notesMaster", "notesMasters/notesMaster1.xml")]) + "</Relationships>")
    pres = pres.replace("</p:sldMasterIdLst>", '</p:sldMasterIdLst><p:notesMasterIdLst><p:notesMasterId r:id="rIdKitNM"/></p:notesMasterIdLst>', 1)
    ctx = ctx.replace("</Types>", '<Override PartName="/ppt/notesMasters/notesMaster1.xml" ContentType="%spresentationml.notesMaster+xml"/><Override PartName="/%s" ContentType="%stheme+xml"/></Types>' % (CT, tn, CT))
    return prels, pres, ctx

def new_slide(z, S, s, n, layouts, cx, cy, R, ctx):
    lay = s.get("layout", 2)
    lay = layouts[int(lay) - 1] if str(lay).isdigit() and int(lay) <= len(layouts) else next((l for l in layouts if l["name"].lower() == str(lay).lower()), None) or next((l for l in layouts if str(lay).lower() in l["name"].lower()), None)
    if lay is None:
        print("WARN slide %d: layout %r not found -> using layout 2; run inspect and pick a listed name" % (n, s.get("layout")))
        lay = layouts[min(1, len(layouts) - 1)]
    L, sh, nid, used = phs(rd(z, lay["path"])), [], [2], []
    free = [p for p in L if p["type"] not in FOOT]
    R.append(("rId1", "slideLayout", "../slideLayouts/" + os.path.basename(lay["path"])))
    take = lambda pred: next((free.pop(free.index(p)) for p in list(free) if pred(p)), None)
    body_ph = lambda p: p["type"] in ("body", "obj")
    area = lambda p: (lambda g: g[2] * g[3] if g else 0)(geom(z, lay, p))
    def big(frac):  # LARGEST free body/obj placeholder (not a source/note box) covering >= frac of the slide
        c = [p for p in free if body_ph(p) and area(p) >= frac * cx * cy and not NOTE.search(p["name"])]
        return free.pop(free.index(max(c, key=area))) if c else None
    mpt = lambda title: (lambda m: int(m.group(1)) // 100 if m else (32 if title else 18))(re.search(
        r"<p:%s>.*?<a:lvl1pPr[^>]*>.*?sz=\"(\d+)\"" % ("titleStyle" if title else "bodyStyle"), rd(z, lay["master"]), re.S))
    def add(xml):
        nid[0] += 1
        sh.append(xml.replace("@ID@", str(nid[0])))
    def sp(p, what, body, box=None, sz=None):
        if p is None:
            return print("WARN slide %d: layout %r has no free placeholder for %s -> pick another layout" % (n, lay["name"], what))
        add('<p:sp><p:nvSpPr><p:cNvPr id="@ID@" name="%s"/><p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr><p:nvPr><p:ph %s/></p:nvPr></p:nvSpPr><p:spPr>%s</p:spPr>'
            '<p:txBody><a:bodyPr/><a:lstStyle/>%s</p:txBody></p:sp>' % (q(p["name"]), p["attrs"], xfrm(box) if box else "", paras(body, sz)))
        g, eff = box or geom(z, lay, p), sz or p["sz"] or mpt(p["type"] in ("title", "ctrTitle"))
        used.append("%s->ph %s idx%s %r %s %dpt" % (what, p["type"], p["idx"], p["name"], "%.1fx%.1fin" % (g[2] / EMU, g[3] / EMU) if g else "", eff))
        fit_warn(n, what, body, g, eff)
        if S.get("min_pt") and what in ("body", "body2") and eff < S["min_pt"]:
            print("WARN slide %d %s: %dpt is below min_pt %s -> shorten/split instead of shrinking" % (n, what, eff, S["min_pt"]))
    for k, v in (s.get("ph") or {}).items():
        sp(take(lambda p: p["idx"] == str(k)), "ph idx %s" % k, v)
    if s.get("title"):
        sp(take(lambda p: p["type"] in ("title", "ctrTitle")), "title", [s["title"]])
    if s.get("subtitle"):
        sp(take(lambda p: p["type"] == "subTitle") or big(0.03), "subtitle", s["subtitle"])
    if s.get("source_note"):
        snp = take(lambda p: body_ph(p) and NOTE.search(p["name"]))
        if snp:
            sp(snp, "source_note", [s["source_note"]])
        else:
            fy = min([geom(z, lay, p)[1] for p in L if p["type"] in FOOT and geom(z, lay, p)] or [cy - 0.5 * EMU])
            add('<p:sp><p:nvSpPr><p:cNvPr id="@ID@" name="Source note"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr><p:spPr>%s<a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/></p:spPr>'
                '<p:txBody><a:bodyPr wrap="square"/><a:lstStyle/><a:p>%s</a:p></p:txBody></p:sp>' % (xfrm([0.5 * EMU, fy - 0.36 * EMU, cx - EMU, 0.34 * EMU]), runs(s["source_note"], 11)))
            used.append("source_note->textbox above footer (layout has no source placeholder)")
    pic, b1 = take(lambda p: p["type"] == "pic"), big(0.08) if s.get("body") else None
    b2, vis = big(0.08) if s.get("body2") else None, s.get("image") or s.get("table")
    vbox = [v * EMU for v in s.get("image_box") or s.get("table_box") or []] or (pic and geom(z, lay, pic))
    if vis and not vbox and not s.get("body2"):
        b2 = big(0.15)
        vbox = b2 and geom(z, lay, b2)
    if vis and not vbox and not s.get("body") and not b1:
        b1 = big(0.15)
    g1, tbox = b1 and geom(z, lay, b1) or [0.5 * EMU, 1.5 * EMU, cx - EMU, cy - 2.3 * EMU], None
    if vis and not vbox:
        vbox, tbox = ([g1[0] + g1[2] * 0.53, g1[1], g1[2] * 0.47, g1[3]], [g1[0], g1[1], g1[2] * 0.5, g1[3]]) if s.get("body") else (g1, None)
    if s.get("body"):
        sp(b1, "body", s["body"], tbox, s.get("font_size"))
    if s.get("body2"):
        sp(b2, "body2", s["body2"], None, s.get("font_size"))
    if vis:
        x, y, w, h = vbox
        cap = 0.4 * EMU if s.get("caption") else 0
        h = (h * 0.58 if s.get("table") and s.get("image") else h) - cap
        if s.get("image"):
            data = open(s["image"], "rb").read()
            iw, ih = imgsize(data)
            k, ext = min(w / iw, h / ih), os.path.splitext(s["image"])[1].lower().lstrip(".").replace("jpg", "jpeg")
            mn, rid = next("ppt/media/kit_s%d_%d.%s" % (n, j, ext) for j in range(999) if "ppt/media/kit_s%d_%d.%s" % (n, j, ext) not in z), "rIdKitImg"  # never overwrite media of kept slides
            z[mn] = data
            R.append((rid, "image", "../media/" + os.path.basename(mn)))
            if 'Extension="%s"' % ext not in ctx[0]:
                ctx[0] = ctx[0].replace("</Types>", '<Default Extension="%s" ContentType="image/%s"/></Types>' % (ext, ext))
            add('<p:pic><p:nvPicPr><p:cNvPr id="@ID@" name="Picture @ID@" descr="%s"/><p:cNvPicPr><a:picLocks noChangeAspect="1"/></p:cNvPicPr><p:nvPr/></p:nvPicPr><p:blipFill>'
                '<a:blip r:embed="%s"/><a:stretch><a:fillRect/></a:stretch></p:blipFill><p:spPr>%s<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr></p:pic>'
                % (q(os.path.basename(s["image"])), rid, xfrm([x + (w - iw * k) / 2, y, iw * k, ih * k])))
            h = ih * k
        capsp = lambda yy: add('<p:sp><p:nvSpPr><p:cNvPr id="@ID@" name="Caption"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr><p:spPr>%s<a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/></p:spPr>'
            '<p:txBody><a:bodyPr wrap="square"/><a:lstStyle/><a:p><a:pPr algn="ctr"/>%s</a:p></p:txBody></p:sp>' % (xfrm([x, yy, w, cap]), runs(s["caption"], s.get("caption_size", 14))))
        cph = pic and s.get("caption") and s.get("image") and big(0.0)
        if cph:  # picture layout with its own caption placeholder: inherit it
            sp(cph, "caption", [s["caption"]])
        elif s.get("caption") and s.get("image"):
            capsp(y + h)  # figure caption below the figure
        if s.get("table"):
            rows, tsz = s["table"], s.get("table_size", 14)
            if s.get("image"):
                y, h = y + h + cap + 0.1 * EMU, vbox[1] + vbox[3] - (y + h + cap + 0.1 * EMU)
            if s.get("caption") and not s.get("image"):
                capsp(y)  # table caption above the table
                y += cap
            rh, nc = min(h / len(rows), 0.45 * EMU), max(len(r) for r in rows)
            ln = lambda e, wd: '<a:%s w="%d">%s</a:%s>' % (e, wd, '<a:solidFill><a:schemeClr val="tx1"/></a:solidFill>' if wd else "<a:noFill/>", e)
            trs = "".join('<a:tr h="%d">%s</a:tr>' % (rh, "".join('<a:tc><a:txBody><a:bodyPr/><a:lstStyle/><a:p>%s</a:p></a:txBody><a:tcPr>%s</a:tcPr></a:tc>' % (
                runs("**%s**" % c if i == 0 and str(c) else c, tsz), ln("lnL", 0) + ln("lnR", 0) + ln("lnT", 19050 if i == 0 else 0) + ln("lnB", 12700 if i == 0 else 19050 if i == len(rows) - 1 else 0))
                for c in list(r) + [""] * (nc - len(r)))) for i, r in enumerate(rows))
            add('<p:graphicFrame><p:nvGraphicFramePr><p:cNvPr id="@ID@" name="Table @ID@"/><p:cNvGraphicFramePr><a:graphicFrameLocks noGrp="1"/></p:cNvGraphicFramePr><p:nvPr/></p:nvGraphicFramePr>'
                '<p:xfrm><a:off x="%d" y="%d"/><a:ext cx="%d" cy="%d"/></p:xfrm><a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/table"><a:tbl><a:tblPr firstRow="1"/>'
                '<a:tblGrid>%s</a:tblGrid>%s</a:tbl></a:graphicData></a:graphic></p:graphicFrame>' % (x, y, w, rh * len(rows), '<a:gridCol w="%d"/>' % (w / nc) * nc, trs))
    print("   placed slide %d [%s]: %s" % (n, lay["name"], "; ".join(used) or "-"))
    for p in L:
        val = {"ftr": S.get("footer"), "dt": S.get("date"), "sldNum": str(n) if S.get("slide_numbers", True) else None}[p["type"]] if p["type"] in FOOT else None
        if val or (p["type"] == "ftr" and "".join(text_of(p["block"])).strip()):
            g, b = geom(z, lay, p), re.sub(r'<p:cNvPr id="\d+"', '<p:cNvPr id="@ID@"', p["block"])
            b = b.replace("<p:spPr/>", "<p:spPr>%s</p:spPr>" % xfrm(g), 1) if g else b
            add(b if p["type"] == "sldNum" or not val else re.sub(r"<a:p(?=[ >]).*</a:p>", lambda m: paras([val]), b, flags=re.S))
    return HEAD + '<p:sld %s><p:cSld><p:spTree>%s%s</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>' % (NS, GRP, "".join(sh)), lay["name"]

def build(spec_path):
    S = json.load(open(spec_path, encoding="utf-8"))
    z, old, layouts, (cx, cy) = load(S["template"])
    keep = {i: (rd(z, s), rd(z, relpath(s)), notes_of(z, s)) for i, s in enumerate(old, 1)}
    ctx = [rd(z, "[Content_Types].xml").replace("presentationml.template.main+xml", "presentationml.presentation.main+xml")]
    pres, prels = rd(z, "ppt/presentation.xml"), rd(z, "ppt/_rels/presentation.xml.rels")
    for n in [n for n in z if re.match(r"ppt/(slides|notesSlides)/", n)]:
        del z[n]
    ctx[0] = re.sub(r'<Override PartName="/ppt/(slides|notesSlides)/[^>]*/>', "", ctx[0])
    prels = re.sub(r'<Relationship [^>]*?Type="[^"]*/slide"[^>]*/>', "", prels)
    pres = re.sub(r"<p:sldIdLst>.*?</p:sldIdLst>|<p:sldIdLst/>", "", pres, flags=re.S)
    if "/notesMaster\"" not in prels:
        prels, pres, ctx[0] = add_notes_master(z, layouts, prels, pres, ctx[0])
    nmp = next(os.path.normpath("ppt/" + m) for m in re.findall(r'Type="[^"]*/notesMaster"[^>]*Target="([^"]+)"|Target="([^"]+)"[^>]*Type="[^"]*/notesMaster"', prels)[0] if m)
    nidx, ids = next((p["idx"] for p in phs(rd(z, nmp)) if p["type"] == "body"), "1"), []
    for n, s in enumerate(S["slides"], 1):
        notes, R = s.get("notes"), []
        if "keep" in s:
            if int(s["keep"]) not in keep:
                sys.exit("ERROR slide %d: keep=%s but input has %d slides" % (n, s["keep"], len(keep)))
            x, rx, oldn = keep[int(s["keep"])]
            for o, nw in (s.get("replace") or {}).items():
                x, h = rep(x, o, nw)
                print("WARN slide %d: replace text not found: %r" % (n, o[:60])) if not h else None
            rx = re.sub(r'<Relationship [^>]*?/notesSlide"[^>]*/>', "", rx)
            lname, notes = "kept input slide %s" % s["keep"], oldn if notes is None else notes
        else:
            x, lname = new_slide(z, S, s, n, layouts, cx, cy, R, ctx)
            rx = wrap_rels(R)
        x = re.sub(r'(<a:fld [^>]*type="slidenum"[^>]*>).*?</a:fld>', lambda m: m.group(1) + '<a:rPr lang="en-US"/><a:t>%d</a:t></a:fld>' % n, x, flags=re.S)
        z["ppt/slides/slide%d.xml" % n] = x.encode("utf-8")
        z["ppt/slides/_rels/slide%d.xml.rels" % n] = rx.replace("</Relationships>", relxml([("rIdKitNotes", "notesSlide", "../notesSlides/notesSlide%d.xml" % n)]) + "</Relationships>").encode("utf-8")
        nb = ('<p:sp><p:nvSpPr><p:cNvPr id="2" name="Slide Image"/><p:cNvSpPr><a:spLocks noGrp="1" noRot="1" noChangeAspect="1"/></p:cNvSpPr><p:nvPr><p:ph type="sldImg"/></p:nvPr></p:nvSpPr><p:spPr/></p:sp>'
              '<p:sp><p:nvSpPr><p:cNvPr id="3" name="Notes"/><p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr><p:nvPr><p:ph type="body" idx="%s"/></p:nvPr></p:nvSpPr><p:spPr/>'
              '<p:txBody><a:bodyPr/><a:lstStyle/>%s</p:txBody></p:sp>' % (nidx, paras(notes or "")))
        z["ppt/notesSlides/notesSlide%d.xml" % n] = (HEAD + '<p:notes %s><p:cSld><p:spTree>%s%s</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:notes>' % (NS, GRP, nb)).encode("utf-8")
        z["ppt/notesSlides/_rels/notesSlide%d.xml.rels" % n] = wrap_rels([("rId1", "notesMaster", "../notesMasters/" + os.path.basename(nmp)), ("rId2", "slide", "../slides/slide%d.xml" % n)]).encode("utf-8")
        ctx[0] = ctx[0].replace("</Types>", "".join('<Override PartName="/ppt/%ss/%s%d.xml" ContentType="%spresentationml.%s+xml"/>' % (d, d, n, CT, d) for d in ("slide", "notesSlide")) + "</Types>")
        prels = prels.replace("</Relationships>", relxml([("rIdKitS%d" % n, "slide", "slides/slide%d.xml" % n)]) + "</Relationships>")
        ids.append('<p:sldId id="%d" r:id="rIdKitS%d"/>' % (255 + n, n))
        first = next((t for t in text_of(x) if t.strip()), "")
        print("slide %d/%d [%s] %s | notes %d chars%s" % (n, len(S["slides"]), lname, first[:50], len(notes or ""), "" if notes else " | NO NOTES"))
    z["[Content_Types].xml"], z["ppt/_rels/presentation.xml.rels"] = ctx[0].encode("utf-8"), prels.encode("utf-8")
    z["ppt/presentation.xml"] = pres.replace("<p:sldSz", "<p:sldIdLst>%s</p:sldIdLst><p:sldSz" % "".join(ids), 1).encode("utf-8")
    bad = [(r, p) for r in z if r.endswith(".rels") and r != "_rels/.rels" for t, p in rels(z, r.replace("_rels/", "")[:-5]).values() if "://" not in p and p not in z and t != "hyperlink"]
    for n in [n for n in z if n.endswith((".xml", ".rels"))]:
        try:
            ET.fromstring(z[n])  # parse-only well-formedness check; never re-serialise with ElementTree
        except ET.ParseError as e:
            bad.append((n, str(e)))
    print("WARN package problems: %s" % bad[:5] if bad else "package integrity OK (all XML well-formed, all relationship targets exist)")
    os.makedirs(os.path.dirname(os.path.abspath(S["out"])), exist_ok=True)
    with zipfile.ZipFile(S["out"], "w", zipfile.ZIP_DEFLATED) as zf:
        for name in ["[Content_Types].xml"] + sorted(n for n in z if n != "[Content_Types].xml"):
            zf.writestr(name, z[name])
    print("wrote %s (%d slides)" % (S["out"], len(S["slides"])))

def figcrop(pdf, page, label, out, dpi=200):
    """Crop a figure/table from a PDF page via pdftotext -bbox-layout + pdftoppm (poppler). Figures: the caption is left OUT of
    the picture (put "Paper Fig. N ..." as the slide caption) and white margins are trimmed, so the figure fills its box."""
    import subprocess, tempfile
    x = subprocess.run(["pdftotext", "-bbox-layout", "-f", str(page), "-l", str(page), pdf, "-"], capture_output=True, text=True, timeout=60).stdout
    pw, ph = [float(v) for v in re.search(r'<page width="([\d.]+)" height="([\d.]+)"', x).groups()]
    blocks = [([float(v) for v in m.group(1, 2, 3, 4)], " ".join(re.findall(r">([^<]+)</word>", m.group(5))), m.group(5).count("<line"))
              for m in re.finditer(r'<block xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">(.*?)</block>', x, re.S)]
    key = re.sub(r"\s+", "", label).lower()
    cap = min([b for b in blocks if re.sub(r"\s+", "", b[1]).lower().startswith(key)], key=lambda b: b[2], default=None)  # caption = shortest match
    if not cap:
        sys.exit("caption %r not found on page %s; blocks start with: %s" % (label, page, [b[1][:25] for b in blocks][:15]))
    (x0, y0, x1, y1), table = cap[0], label.strip().lower().startswith(("tab", "表"))
    widths = sorted(b[0][2] - b[0][0] for b in blocks if b[2] >= 2) or [pw]
    twocol = widths[len(widths) // 2] < pw * 0.5  # median paragraph width -> two-column page
    lo, hi = (0, pw / 2) if twocol and x1 < pw * 0.55 else (pw / 2, pw) if twocol and x0 > pw * 0.45 else (0, pw)
    para = [b for b in blocks if b is not cap and b[0][2] > lo and b[0][0] < hi and b[0][2] - b[0][0] > (hi - lo) * 0.6]
    lo, hi, k = max(lo, 18), min(hi, pw - 18), dpi / 72.0
    def ink(l, t, r, bt):  # bounding box (pt) of non-white pixels in a region, from a 50 dpi greyscale render; None if blank
        if bt - t < 6 or r - l < 6:
            return None
        try:
            tmp, g = tempfile.mkdtemp(prefix="figcrop_"), 50 / 72.0
            subprocess.run(["pdftoppm", "-gray", "-r", "50", "-f", str(page), "-l", str(page), "-x", str(int(l * g)), "-y", str(int(t * g)), "-W", str(max(1, int((r - l) * g))),
                            "-H", str(max(1, int((bt - t) * g))), "-singlefile", pdf, os.path.join(tmp, "p")], check=True, timeout=60, capture_output=True)
            d = open(os.path.join(tmp, "p.pgm"), "rb").read()
            hd = re.match(rb"P5\s+(\d+)\s+(\d+)\s+(\d+)\s", d)
            w, h, px = int(hd.group(1)), int(hd.group(2)), d[hd.end():]
            rows = [i for i in range(h) if min(px[i * w:(i + 1) * w] or b"\xff") < 235]
            cols = [j for j in range(w) if min(px[j::w][:h] or b"\xff") < 235]
            return (l + cols[0] / g - 3, t + rows[0] / g - 3, l + (cols[-1] + 1) / g + 3, t + (rows[-1] + 1) / g + 3) if rows and cols else None
        except Exception as e:
            print("(margin trim skipped: %s)" % e)
            return (l, t, r, bt)
    if table:  # tables: caption above + rows below, kept together
        bot = min([b[0][1] for b in para if b[0][1] > y1 + 5] or [ph - 36]) - 2
        top, bot = y0 - 2, min(bot, max([b[0][3] for b in blocks if y1 <= b[0][1] < bot] or [bot]) + 4)
        box, where = ink(lo, top, hi, bot) or (lo, top, hi, bot), "table incl. its caption"
    else:  # figure above its caption; if that region is blank, the caption sits above the figure
        txt = [b for b in blocks if b is not cap and b[0][2] > lo and b[0][0] < hi and b[0][2] - b[0][0] > (hi - lo) * 0.4]  # body text, also short last lines
        above = (lo, max([b[0][3] for b in txt if b[0][3] <= y0 + 1] or [36]) + 2, hi, y0 - 1)
        below = (lo, y1 + 1, hi, min([b[0][1] for b in para if b[0][1] > y1 + 1] or [ph - 36]) - 2)
        box, where = (ink(*above), "figure above caption (caption excluded)")
        if not box:
            box, where = ink(*below), "figure below caption (caption excluded)"
        if not box:
            box, where = (lo, above[1], hi, y1 + 2), "WARN no figure pixels next to the caption: the PDF may not contain this figure -> do not insert it, record a material gap"
    l, t, r, bt = max(box[0], 0), max(box[1], 0), min(box[2], pw), min(box[3], ph)
    subprocess.run(["pdftoppm", "-r", str(dpi), "-f", str(page), "-l", str(page), "-x", str(int(l * k)), "-y", str(int(t * k)), "-W", str(int((r - l) * k)),
                    "-H", str(int((bt - t) * k)), "-png", "-singlefile", pdf, out[:-4] if out.endswith(".png") else out], check=True, timeout=120)
    inside = [b[1][:40] for b in blocks if b[0][1] >= t - 1 and b[0][3] <= bt + 1 and b[0][0] >= l - 1 and b[0][2] <= r + 1]
    print("cropped page %s [%.0f,%.0f,%.0f,%.0f]pt (%s) -> %s\ncaption: %s\ntext inside crop (axis labels/legend expected, not body paragraphs): %s"
          % (page, l, t, r, bt, where, out, cap[1][:160], inside[:12]))

def render(deck, dpi=100):
    """deck.pptx -> deck.pdf + preview/slide-N.png + render.json. Never raises: every failure is recorded honestly."""
    import glob, shutil, subprocess, tempfile
    out, stem = os.path.dirname(os.path.abspath(deck)), os.path.splitext(os.path.abspath(deck))[0]
    rec = {"pptx": os.path.abspath(deck), "pdf": None, "png": [], "pages": None, "renderer": None, "fonts": [], "substitutions": [], "errors": [], "commands": []}
    def run(cmd, t):
        rec["commands"].append(" ".join(cmd))
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=t)
            return r.returncode, (r.stdout or "") + (r.stderr or "")
        except Exception as e:  # missing binary, timeout
            return -1, "%s: %s" % (type(e).__name__, e)
    for old in glob.glob(os.path.join(out, "preview", "slide*.png")) + glob.glob(stem + ".pdf"):
        os.remove(old)  # stale previews from an earlier build must not pass as this build's render
    env = os.environ.get("SOFFICE", "")
    cands = ([env] if env and env != "none" and os.path.exists(env) else []) + [shutil.which(c) for c in ("soffice", "libreoffice")] + glob.glob("/usr/lib/libreoffice/program/soffice") + glob.glob("/opt/libreoffice*/program/soffice") + \
        glob.glob("/Applications/LibreOffice.app/Contents/MacOS/soffice")
    so = None if env == "none" else next((c for c in cands if c), None)
    if not so:
        rec["errors"].append("no LibreOffice (soffice/libreoffice) found: PDF/PNG previews could not be produced")
    for k in range(2 if so else 0):
        prof = tempfile.mkdtemp(prefix="lo_kit%d_" % k)
        rc, msg = run([so, "--headless", "-env:UserInstallation=file://" + prof, "--convert-to", "pdf", "--outdir", out, deck], 120)
        if os.path.exists(stem + ".pdf") and os.path.getmtime(stem + ".pdf") >= os.path.getmtime(deck) - 1:
            rec["pdf"], rec["renderer"] = stem + ".pdf", (run([so, "--version"], 30)[1].strip().splitlines() or ["LibreOffice"])[0][:80]
            break
        rec["errors"].append("soffice attempt %d failed (rc %s): %s" % (k + 1, rc, msg.strip()[-200:]))
    if rec["pdf"]:
        rc, info = run(["pdfinfo", rec["pdf"]], 30)
        m = re.search(r"Pages:\s+(\d+)", info)
        rec["pages"] = int(m.group(1)) if m else len(re.findall(rb"/Type\s*/Page(?!s)", open(rec["pdf"], "rb").read()))
        os.makedirs(os.path.join(out, "preview"), exist_ok=True)
        for tool in (["pdftoppm", "-png", "-r", str(dpi)], ["pdftocairo", "-png", "-r", str(dpi)]):
            rc, msg = run(tool + [rec["pdf"], os.path.join(out, "preview", "slide")], 120)
            rec["png"] = sorted(glob.glob(os.path.join(out, "preview", "slide*.png")))
            if rec["png"]:
                break
            rec["errors"].append("%s failed: %s" % (tool[0], msg.strip()[-160:]))
        rc, f = run(["pdffonts", rec["pdf"]], 30)
        rec["fonts"] = sorted({ln.split()[0].split("+")[-1] for ln in f.splitlines()[2:] if ln.strip()}) if rc == 0 else []
        try:
            z, _, layouts, _ = load(deck)
            th = rd(z, next((n for n in sorted(z) if n.startswith("ppt/theme/theme")), ""))
            want = set(re.findall(r'<a:(?:latin|ea) typeface="([^"+][^"]*)"', th)[:4])
            got = " ".join(rec["fonts"]).replace("-", "").lower()
            rec["substitutions"] = ["%s not embedded (renderer substituted another font)" % w for w in sorted(want) if w.replace(" ", "").lower() not in got.replace(" ", "")]
        except Exception as e:
            rec["errors"].append("font comparison skipped: %s" % e)
    rec["status"] = "rendered" if rec["png"] else "pdf_only" if rec["pdf"] else "failed"
    json.dump(rec, open(os.path.join(out, "render.json"), "w"), indent=1, ensure_ascii=False)
    print("render: %s | pdf=%s pages=%s png=%d | fonts=%s | substitutions=%s%s" % (rec["status"], rec["pdf"], rec["pages"], len(rec["png"]), rec["fonts"][:6],
          rec["substitutions"], "\nrender errors: %s" % rec["errors"] if rec["errors"] else ""))
    print("record written to %s (status partial + exceptions.run_failures if not 'rendered')" % os.path.join(out, "render.json"))

if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] not in ("inspect", "build", "figcrop", "render"):
        sys.exit(__doc__)
    if sys.argv[1] == "render":
        render(sys.argv[2])
    elif sys.argv[1] == "figcrop":
        figcrop(*sys.argv[2:6], **({"dpi": int(sys.argv[6])} if len(sys.argv) > 6 else {}))
    else:
        inspect(sys.argv[2], "--full" in sys.argv) if sys.argv[1] == "inspect" else build(sys.argv[2])
