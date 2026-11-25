#!/usr/bin/env python3
"""pptx_kit.py - stdlib-only PPTX inspect/build on a real template or starting deck (Python 3.8+, no python-pptx).

  python3 pptx_kit.py inspect FILE.pptx [--full]  # theme fonts/colours, layouts+placeholders (inches), every slide's
                                                  # shapes by role (ph:title/ph:obj/text), table rows, pictures, notes
  python3 pptx_kit.py build SPEC.json [MORE_SLIDES.json]   # write the deck, print per-slide summary + overflow/placeholder/integrity warnings
  python3 pptx_kit.py paper paper.pdf /app/work     # paper.txt + pages/sections/every Fig./Table caption with page (2-column safe)
  python3 pptx_kit.py figcrop paper.pdf PAGE "Fig. 2" /app/work/fig2.png [DPI] [--keep-caption]   # crop by caption, trim margins,
                                                  # figure caption left OUT of the image (printed: put it on the slide)
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
           "ph": {"13": ["text for placeholder idx 13"]}, "notes": "speaker notes",
           "role": "result", "seconds": 70, "confidence": "high", "uncertainty": "...",          # record fields (not drawn)
           "evidence": [{"locator": "Fig. 2a, Sec. 3.1, p.5", "quote": "short phrase copied from paper.txt"}]}],
        "min_pt": 18,                           # optional: WARN when body text would render below this size
        "formulas": ["LiPF6", "H2O"],           # these get subscript digits everywhere; unit exponents (cm-2, g-1, m2) are automatic
        "duration_min": 12, "storyline": {"problem": "...", "method": "...", "evidence": ["..."], "conclusion": "...", "limits": "..."},
        "change": "what this rebuild changed"}  # -> change_log.md
build also writes, next to the deck, content_map.json (evidence + quote check vs paper.txt + paper pages of every number),
plan.md, spec.json and appends change_log.md - all derived from this one spec.
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

FORMULAS, UNITS = [], [True]
UNIT = re.compile(r"(?<![A-Za-z])((?:cm|mm|nm|\u03bcm|\u00b5m|km|m|s|h|g|kg|mg|mL|L|mol|min|mAh|Ah|Wh|kWh|K|V|W|Pa|Hz|eV|J)\s?)([-\u2212][1-9])(?![\w.])|(?<![A-Za-z])(cm|mm|nm|\u03bcm|\u00b5m|km|m)([23])(?![\w.])")

def markup(text):
    """Plain text -> kit markup: unit exponents (mA cm-2, m2 g-1 -> superscript) and the formulas listed in spec "formulas"
    (["LiPF6", "H2O"] -> subscript digits). Text that already carries _{..}/^{..} is left alone; "auto_units": false disables."""
    t = str(text)
    if "_{" in t or "^{" in t:
        return t
    for f in FORMULAS:
        t = t.replace(f, re.sub(r"(?<=[A-Za-z)\]])(\d+(?:\.\d+)?)", r"_{\1}", f)) if f else t
    if UNITS[0]:
        t = UNIT.sub(lambda m: "%s^{%s}" % ((m.group(1).rstrip(" "), m.group(2)) if m.group(1) else (m.group(3), m.group(4))), t)
    return t

def runs(text, sz=None):
    """**bold**, H_{2}O subscript, cm^{-1} / Ce^{3+} superscript (the markup never reaches the slide text); \\v = line break."""
    out, bold = [], False
    for g in re.split(r"(\*\*|_\{[^{}]*\}|\^\{[^{}]*\}|\v)", markup(text)):
        if g == "\v":
            out.append("<a:br/>")
            continue
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

def plain(t):
    """Visible characters of a markup string: **bold** markers and _{..}/^{..} wrappers removed (for width estimates)."""
    return re.sub(r"[_^]\{([^{}]*)\}", r"\1", markup(t)).replace("**", "").replace("\v", "")

def balance(title, box, sz):
    """A title that needs two or three lines gets its line breaks at the most even phrase boundaries (after punctuation /
    at a space), so it never wraps inside a unit or leaves a one-character last line. Returns the title with \\v at breaks."""
    t = str(title)
    if "\n" in t or "\v" in t or not box:
        return t.replace("\n", "\v")
    wd = lambda x: sum(1.05 if ord(c) > 0x2e80 else 0.62 for c in plain(x)) * sz * 0.9
    cap = box[2] / 12700.0 - 14
    if not cap * 1.08 < wd(t) <= cap * 2.8:  # clearly more than one line (the width estimate is conservative)
        return t
    cands = []
    for m in re.finditer(r"[\uff0c\uff1a\uff1b\u3001,;:]\s?| (?=\S)|(?<=[\u4e00-\u9fff])(?=[A-Za-z0-9])", t):
        a, b = t[:m.end()], t[m.end():]
        if re.search(r"(\*\*|_\{|\^\{)[^*{}]*$", a) and re.match(r"[^*{}]*(\*\*|\})", b) or not b or re.match(r"(wt|vol|at|mol)?\s?%|[-\u2212\u00b0\u2103]|[a-zA-Z\u03bc\u03a9]{1,3}\b(?![a-z])", b) and re.search(r"\d\s?$", a):
            continue  # never inside markup, never between a number and its unit
        cands.append((m.end(), 0.22 * cap if re.match(r"[\uff0c\uff1a\uff1b\u3001,;:]", m.group(0)) else 0))
    best = None
    def cost_of(parts, bonus):
        w = [wd(x) for x in parts]
        return None if max(w) > cap * 0.95 else max(w) - min(w) - bonus + (0.1 * cap if w[-1] > w[0] * 1.6 else 0)
    if wd(t) <= cap * 1.8:
        for i, bo in cands:
            c = cost_of([t[:i], t[i:]], bo)
            if c is not None and (best is None or c < best[0]):
                best = (c, t[:i] + "\v" + t[i:])
    if best is None and wd(t) > cap * 1.9:  # really a three-line title: avoid a one-word last line
        for x, (i, bi) in enumerate(cands):
            for j, bj in cands[x + 1:]:
                c = cost_of([t[:i], t[i:j], t[j:]], bi + bj)
                if c is not None and (best is None or c < best[0]):
                    best = (c, t[:i] + "\v" + t[i:j] + "\v" + t[j:])
    return best[1] if best else t

def fit_need(what, items, box, sz):
    """Rough, deliberately conservative estimate: CJK 1.05 em, latin 0.62 em, titles x0.9 (calibrated on LibreOffice renders), line 1.2 em, 0.25 in indent per level."""
    wpt, hpt = box[2] / 12700.0 - 14, box[3] / 12700.0 - 7
    lines = sum(max(1, -(-sum(1.05 if ord(c) > 0x2e80 else 0.62 for c in plain(t)) * sz * (0.9 if what == "title" else 1) // max(wpt - 18 * l, 40))) for l, t in items_of(items))
    return lines, lines * sz * 1.2, hpt

def fit_warn(n, what, items, box, sz):
    if box and items:
        lines, need, hpt = fit_need(what, items, box, sz)
        if need > hpt * (1.35 if what == "title" else 1) or (what == "title" and lines > 2):  # renderers let 2-line titles spill into the margin
            print("WARN slide %d %s: ~%d lines at %dpt need %.0fpt but box is %.0fpt high -> shorten, split slide or pick a bigger layout" % (n, what, lines, sz, need, hpt))

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
    if lay is None:  # unknown name: choose by what the slide needs (cover -> centred-title layout, else the largest content placeholder)
        types = lambda l: [p["type"] for p in phs(rd(z, l["path"]))]
        cover = n == 1 or re.search(r"title slide|cover|封面|标题幻灯片", str(s.get("layout", "")), re.I) or s.get("role") in ("title", "cover", "封面")
        two = s.get("body2") and next((l for l in layouts if sum(t in ("body", "obj") for t in types(l)) >= 2 and "title" in types(l)), None)
        lay = (next((l for l in layouts if "ctrTitle" in types(l)), None) if cover else two or next((l for l in layouts if "title" in types(l) and ("obj" in types(l) or "body" in types(l))), None)) or layouts[min(1, len(layouts) - 1)]
        print("WARN slide %d: layout %r not in this template -> using %r; layout names are listed by inspect" % (n, s.get("layout"), lay["name"]))
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
        g, eff = box or geom(z, lay, p), sz or p["sz"] or mpt(p["type"] in ("title", "ctrTitle"))
        if not sz and what in ("body", "body2") and g and body and (lambda f: f[1] > f[2])(fit_need(what, body, g, eff)):
            lo_pt = int(S.get("min_pt") or 18)  # inherited size would overflow: largest even size that fits, never below min_pt
            sz = eff = next((v for v in range(eff - eff % 2 - 2, lo_pt - 1, -2) if (lambda f: f[1] <= f[2])(fit_need(what, body, g, v))), lo_pt)
            what_note = " (auto-fit from template size)"
        else:
            what_note = ""
        if what == "title" and g and S.get("balance_titles", True):
            body = [balance(body[0], g, eff)]
            what_note = " (2 lines, balanced break)" if "\v" in body[0] else ""
        add('<p:sp><p:nvSpPr><p:cNvPr id="@ID@" name="%s"/><p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr><p:nvPr><p:ph %s/></p:nvPr></p:nvSpPr><p:spPr>%s</p:spPr>'
            '<p:txBody>%s<a:lstStyle/>%s</p:txBody></p:sp>' % (q(p["name"]), p["attrs"], xfrm(box) if box else "",
            "<a:bodyPr><a:noAutofit/></a:bodyPr>" if sz and what in ("body", "body2") else "<a:bodyPr/>", paras(body, sz)))
        used.append("%s->ph %s idx%s %r %s %dpt%s" % (what, p["type"], p["idx"], p["name"], "%.1fx%.1fin" % (g[2] / EMU, g[3] / EMU) if g else "", eff, what_note))
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
    bsz = s.get("font_size")
    if vis and not vbox and s.get("body"):
        iw0, ih0 = imgsize(open(s["image"], "rb").read()) if s.get("image") else (len(s["table"][0]) * 2, 2)
        if iw0 / float(ih0) >= 1.45 or (s.get("table") and not s.get("image") and len(s["table"][0]) >= 4):
            # wide figure / wide table: full-width visual on top, short takeaway bullets underneath (readable sizes)
            lo_pt, capx = int(S.get("min_pt") or 18), (0.4 * EMU if s.get("caption") else 0)
            vh = min(g1[2] * ih0 / float(iw0) + capx, g1[3] * 0.75) if s.get("image") else min(len(s["table"]) * 24 * 1.9 * 12700 + capx, g1[3] * 0.72)
            hneed = lambda v: fit_need("body", s["body"], g1, v)[0] * v * 1.5 * 12700 + 0.3 * EMU
            top_pt = min((b1 and b1["sz"]) or mpt(False), 28)  # takeaways under a figure: as large as the free space allows, never above the template size
            bsz = bsz or next((v for v in range(top_pt - top_pt % 2, max(lo_pt, 20) - 1, -2) if hneed(v) <= g1[3] - vh - 0.1 * EMU), max(lo_pt, 20))
            bh = min(max(hneed(bsz), g1[3] * 0.2), g1[3] * 0.45)
            vbox, tbox = [g1[0], g1[1], g1[2], g1[3] - bh - 0.08 * EMU], [g1[0], g1[1] + g1[3] - bh, g1[2], bh]
            if s.get("image") and not s.get("table"):  # very wide figure leaves a gap: move the takeaways up under figure + caption
                shown = min(vbox[2] / iw0, (vbox[3] - (0.4 * EMU if s.get("caption") else 0)) / ih0) * ih0 + (0.4 * EMU if s.get("caption") else 0)
                if vbox[3] - shown > 0.3 * EMU:
                    tbox = [g1[0], g1[1] + shown + 0.12 * EMU, g1[2], g1[1] + g1[3] - (g1[1] + shown + 0.12 * EMU)]
            used.append("stacked: visual on top (%.1fx%.1fin), body below" % (g1[2] / EMU, (g1[3] - bh) / EMU))
        else:
            vbox, tbox = [g1[0] + g1[2] * 0.53, g1[1], g1[2] * 0.47, g1[3]], [g1[0], g1[1], g1[2] * 0.5, g1[3]]
    elif vis and not vbox:
        vbox, tbox = g1, None
    if s.get("body"):
        sp(b1, "body", s["body"], tbox, bsz)
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
            st = any(u.startswith("stacked") for u in used)  # already full-width on top: only a much smaller figure is worth a rebuild
            if iw * k < (0.5 if st else 0.55) * cx and ih * k < 0.6 * cy:
                print("WARN slide %d: figure is only %.1fx%.1fin on a %.1fin-wide slide (axis labels unreadable?) -> %s" % (n, iw * k / EMU, ih * k / EMU, cx / EMU,
                      "keep 1 short body line (rest into notes) or drop the body" if st else
                      "use a Title+Content layout (wide figure + short body stacks automatically), drop the body, or give image_box"))
        capsp = lambda yy: add('<p:sp><p:nvSpPr><p:cNvPr id="@ID@" name="Caption"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr><p:spPr>%s<a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/></p:spPr>'
            '<p:txBody><a:bodyPr wrap="square"/><a:lstStyle/><a:p><a:pPr algn="ctr"/>%s</a:p></p:txBody></p:sp>' % (xfrm([x, yy, w, cap]), runs(s["caption"], s.get("caption_size", 14))))
        cph = pic and s.get("caption") and s.get("image") and big(0.0)
        if cph:  # picture layout with its own caption placeholder: inherit it
            sp(cph, "caption", [s["caption"]])
        elif s.get("caption") and s.get("image"):
            capsp(y + h)  # figure caption below the figure
        if s.get("table"):
            rows = s["table"]
            if s.get("image"):
                y, h = y + h + cap + 0.1 * EMU, vbox[1] + vbox[3] - (y + h + cap + 0.1 * EMU)
            if s.get("caption") and not s.get("image"):
                capsp(y)  # table caption above the table
                y += cap
            nc = max(len(r) for r in rows)
            cw = lambda c, z: sum(1.05 if ord(ch) > 0x2e80 else 0.58 for ch in plain(c)) * z + 16  # pt incl. cell margins
            need = lambda z: [max([cw(r[j], z) for r in rows if j < len(r)] + [36]) for j in range(nc)]
            fits = lambda z: sum(need(z)) <= w / 12700.0 and len(rows) * z * 1.9 <= h / 12700.0
            tsz = s.get("table_size") or next((z for z in (24, 22, 20, 18, 16, 14) if fits(z)), 14)
            if not fits(tsz):
                print("WARN slide %d: table needs ~%.0fpt wide x %.0fpt high at %dpt but box is %.0fx%.0fpt -> drop columns/rows (move to notes) or split" % (
                    n, sum(need(tsz)), len(rows) * tsz * 1.9, tsz, w / 12700.0, h / 12700.0))
            nd = need(tsz)
            colw = [int(w * v / sum(nd)) for v in nd]
            rh = min(h / len(rows), tsz * 2.4 * 12700)
            used.append("table %dx%d at %dpt" % (len(rows), nc, tsz))
            ln = lambda e, wd: '<a:%s w="%d">%s</a:%s>' % (e, wd, '<a:solidFill><a:schemeClr val="tx1"/></a:solidFill>' if wd else "<a:noFill/>", e)
            trs = "".join('<a:tr h="%d">%s</a:tr>' % (rh, "".join('<a:tc><a:txBody><a:bodyPr/><a:lstStyle/><a:p>%s</a:p></a:txBody><a:tcPr>%s</a:tcPr></a:tc>' % (
                runs("**%s**" % c if i == 0 and str(c) else c, tsz), ln("lnL", 0) + ln("lnR", 0) + ln("lnT", 19050 if i == 0 else 0) + ln("lnB", 12700 if i == 0 else 19050 if i == len(rows) - 1 else 0))
                for c in list(r) + [""] * (nc - len(r)))) for i, r in enumerate(rows))
            add('<p:graphicFrame><p:nvGraphicFramePr><p:cNvPr id="@ID@" name="Table @ID@"/><p:cNvGraphicFramePr><a:graphicFrameLocks noGrp="1"/></p:cNvGraphicFramePr><p:nvPr/></p:nvGraphicFramePr>'
                '<p:xfrm><a:off x="%d" y="%d"/><a:ext cx="%d" cy="%d"/></p:xfrm><a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/table"><a:tbl><a:tblPr firstRow="1"/>'
                '<a:tblGrid>%s</a:tblGrid>%s</a:tbl></a:graphicData></a:graphic></p:graphicFrame>' % (x, y, sum(colw), rh * len(rows), "".join('<a:gridCol w="%d"/>' % c for c in colw), trs))
    print("   placed slide %d [%s]: %s" % (n, lay["name"], "; ".join(used) or "-"))
    for p in L:
        val = {"ftr": S.get("footer"), "dt": S.get("date"), "sldNum": str(n) if S.get("slide_numbers", True) else None}[p["type"]] if p["type"] in FOOT else None
        if val or (p["type"] == "ftr" and "".join(text_of(p["block"])).strip()):
            g, b = geom(z, lay, p), re.sub(r'<p:cNvPr id="\d+"', '<p:cNvPr id="@ID@"', p["block"])
            b = b.replace("<p:spPr/>", "<p:spPr>%s</p:spPr>" % xfrm(g), 1) if g else b
            add(b if p["type"] == "sldNum" or not val else re.sub(r"<a:p(?=[ >]).*</a:p>", lambda m: paras([val]), b, flags=re.S))
    return HEAD + '<p:sld %s><p:cSld><p:spTree>%s%s</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>' % (NS, GRP, "".join(sh)), lay["name"]

def load_spec(path):
    try:
        return json.loads(open(path, encoding="utf-8").read())
    except ValueError as e:  # show where the JSON breaks instead of a traceback
        ln = getattr(e, "lineno", 0)
        src = open(path, encoding="utf-8").read().splitlines()
        sys.exit("ERROR %s is not valid JSON: %s\n  line %s: %s\n  (common causes: unescaped \" inside a string, trailing comma, a real line break inside a string - use \\n)" % (path, e, ln, src[ln - 1][:160] if 0 < ln <= len(src) else ""))

def build(spec_path, more=()):
    S = load_spec(spec_path)
    for extra in more:  # a long deck can be written as several files: slides of later files are appended
        x = load_spec(extra)
        S["slides"] = list(S.get("slides") or []) + list(x.get("slides") if isinstance(x, dict) else x)
    FORMULAS[:] = sorted([str(f) for f in S.get("formulas") or [] if re.search(r"[A-Za-z)\]]\d", str(f))], key=len, reverse=True)
    UNITS[0] = S.get("auto_units", True) is not False
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
    try:
        records(S, spec_path)
    except Exception as e:  # records are derived extras: never fail the build because of them
        print("note: records not written (%s) - write content_map.json / plan.md by hand" % e)

def records(S, spec_path):
    """Derive the review records from the SAME spec that built the deck (one source, so they cannot drift apart):
    content_map.json (claim, evidence, quote check against paper.txt, numbers with the paper pages they occur on, visual
    kind, notes, time), plan.md (storyline + page plan + time budget), spec.json copy, change_log.md (one entry per build)."""
    import datetime, shutil
    od = os.path.dirname(os.path.abspath(S["out"]))
    if S.get("records") is False:
        return
    ptxt = S.get("paper_text") or os.path.join(os.environ.get("WORK_DIR", os.path.dirname(os.path.abspath(spec_path))), "paper.txt")
    rdp = lambda f: open(f, encoding="utf-8", errors="ignore").read().split("\f") if os.path.exists(f) else []
    pages, flow = rdp(ptxt), rdp(os.path.join(os.path.dirname(ptxt), "paper_flow.txt"))
    nrm = lambda t: re.sub(r"\s+", " ", re.sub(r"(?<=[a-z])-\s*\n\s*(?=[a-z])", "", str(t).replace("\ufb01", "fi").replace("\ufb02", "fl").replace("\ufb00", "ff").replace("\ufb03", "ffi")).replace("\u2212", "-").replace("\u2013", "-").replace("\u2225", "||")).strip().lower()
    npages = [nrm(pg) + " " + nrm(flow[i] if i < len(flow) else "") for i, pg in enumerate(pages)]
    def where(quote):  # -> (verdict, page)
        qn = nrm(quote).strip(" .\"'\u201c\u201d")
        if not npages or len(qn) < 6:
            return ("not checked (no paper.txt)" if not npages else "too short to check"), None
        for i, pg in enumerate(npages, 1):
            if qn in pg:
                return "verbatim", i
        tok = re.findall(r"[\w.%]+", qn)
        best = max(((sum(1 for w in tok if w in pg) / float(len(tok) or 1), -i) for i, pg in enumerate(npages, 1)), default=(0, 0))
        return ("words found (line breaks/columns differ)" if best[0] >= 0.85 else "NOT FOUND in paper text"), (-best[1] if best[0] >= 0.85 else None)
    num_rx = re.compile(r"(?<![\w.])\d+(?:\.\d+)?(?:\s?%)?")
    rows, miss, tot = [], [], 0
    for n, sl in enumerate(S["slides"], 1):
        ev = sl.get("evidence") or sl.get("source") or sl.get("source_note") or []
        ev = [ev] if isinstance(ev, (str, dict)) else list(ev)
        evo = []
        for e in ev:
            e = {k: v for k, v in e.items() if v not in (None, "")} if isinstance(e, dict) else {"locator": str(e)}
            e.setdefault("source", S.get("paper_name") or "paper.pdf")
            if e.get("quote"):
                v, pg = where(e["quote"])
                e["quote_check"] = v + (" on p.%d" % pg if pg else "")
                said = re.search(r"p{1,2}\.?\s?(\d+)", str(e.get("locator", "")))
                if pg and said and int(said.group(1)) != pg and nrm(e["quote"]) not in (npages[int(said.group(1)) - 1] if int(said.group(1)) <= len(npages) else ""):
                    e["quote_check"] += " (locator says p.%s)" % said.group(1)
                if v.startswith("NOT"):
                    miss.append("slide %d: %r" % (n, str(e["quote"])[:50]))
            evo.append(e)
        vis_txt = " ".join([str(sl.get("title", "")), str(sl.get("subtitle", ""))] + [str(b) for k in ("body", "body2") for b in (sl.get(k) if isinstance(sl.get(k), list) else [sl.get(k) or ""])] +
                           [str(c) for r in sl.get("table") or [] for c in r])
        nums = []
        for v in sorted(set(x.replace(" ", "") for x in num_rx.findall(plain(vis_txt))), key=lambda x: vis_txt.find(x.rstrip("%"))):
            core = v.rstrip("%")
            if len(core) < 2 and "." not in core:
                continue
            pg = [i for i, t in enumerate(pages, 1) if re.search(r"(?<![\d.])%s(?![\d]|\.\d)" % re.escape(core), t)]
            nums.append({"value": v, "paper_pages": pg[:6]} if pages else {"value": v})
        visual = ("native editable table %dx%d" % (len(sl["table"]), max(len(r) for r in sl["table"])) if sl.get("table") else "") + \
                 ((" + " if sl.get("table") else "") + "paper figure crop %s" % os.path.basename(sl["image"]) if sl.get("image") else "") or ("kept input slide %s" % sl["keep"] if "keep" in sl else "text only")
        sec = sl.get("seconds") or sl.get("time_s") or 0
        tot += sec if isinstance(sec, (int, float)) else 0
        row = {"slide": n, "role": sl.get("role") or ("title" if n == 1 else ""), "claim": plain(sl.get("title", "")), "layout": sl.get("layout"), "evidence": evo,
               "numbers": nums, "visual": visual + (" (%s)" % sl["visual_kind"] if sl.get("visual_kind") else ""), "caption": plain(sl.get("caption", "")) or None,
               "on_slide_source": sl.get("source_note"), "notes_summary": str(sl.get("notes") or "")[:160], "seconds": sec or None,
               "confidence": sl.get("confidence") or ("high" if evo and not any("NOT" in str(e.get("quote_check", "")) for e in evo) else "medium" if evo else "low"),
               "uncertainty": sl.get("uncertainty") or None}
        rows.append({k: v for k, v in row.items() if v not in (None, "", [])})
    json.dump(rows, open(os.path.join(od, "content_map.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    st = S.get("storyline") or {}
    md = ["# Talk plan (derived from spec.json by pptx_kit.py build)", ""]
    if st:
        md += ["## Storyline (the paper's own contribution, not its section order)", ""] + ["- **%s**: %s" % (k, v if isinstance(v, str) else "; ".join(str(x) for x in v)) for k, v in (st.items() if isinstance(st, dict) else [("line", st)])] + [""]
    cell = lambda t: str(t).replace("|", "\\|").replace("\n", " ")
    md += ["## Page plan", "", "| slide | role | claim (title) | evidence | visual | time (s) |", "|---|---|---|---|---|---|"]
    md += ["| %d | %s | %s | %s | %s | %s |" % (r["slide"], cell(r.get("role", "")), cell(r.get("claim", "")), cell("; ".join(str(e.get("locator", "")) for e in r.get("evidence", []))), cell(r.get("visual", "")), r.get("seconds", "")) for r in rows]
    dur = S.get("duration_min")
    md += ["", "Slides: %d. Planned speaking time: %s%s." % (len(rows), "%d s (%.1f min)" % (tot, tot / 60.0) if tot else "not given per slide", " of %s min allowed" % dur if dur else "")]
    open(os.path.join(od, "plan.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")
    if os.path.abspath(spec_path) != os.path.join(od, "spec.json"):  # the complete (merged) spec: rebuild with `pptx_kit.py build spec.json`
        json.dump(S, open(os.path.join(od, "spec.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    log = os.path.join(od, "change_log.md")
    k = len(re.findall(r"^## build ", open(log, encoding="utf-8").read(), re.M)) + 1 if os.path.exists(log) else 1
    with open(log, "a", encoding="utf-8") as f:
        f.write("%s## build %d - %s\n- %d slides on template %s -> %s\n- change: %s\n" % ("" if k > 1 else "# Change log (one entry per build; appended by pptx_kit.py)\n\n", k,
                datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), len(rows), os.path.basename(S["template"]), os.path.basename(S["out"]), S.get("change") or ("first build" if k == 1 else "rebuild (see spec.json)")))
    noev = [r["slide"] for r in rows if not r.get("evidence") and r.get("role") not in ("title", "封面", "cover", "Q&A", "致谢")]
    print("records: content_map.json (%d rows), plan.md, spec.json, change_log.md (build %d) -> %s" % (len(rows), k, od))
    if tot and dur and abs(tot - float(dur) * 60) > float(dur) * 60 * 0.15:
        print("WARN time budget: slides add up to %d s, the talk is %s min -> adjust \"seconds\"/content" % (tot, dur))
    if noev[1 if noev[:1] == [1] else 0:]:
        print("WARN no \"evidence\" on slides %s -> add [{\"locator\": \"Fig. 2, Sec. 3.1, p.5\", \"quote\": \"short phrase copied from paper.txt\"}]" % noev[1 if noev[:1] == [1] else 0:])
    if miss:
        print("WARN evidence quotes not found in paper.txt (copy a short phrase exactly, or fix the locator): %s" % "; ".join(miss[:6]))

def figcrop(pdf, page, label, out, dpi=200, keep_caption=False):
    """Crop a figure/table from a PDF page via pdftotext -bbox-layout + pdftoppm (poppler). Figures: the caption is left OUT of
    the picture (put "Paper Fig. N ..." on the slide as editable text; --keep-caption keeps it), white margins are trimmed, a
    caption that sits ABOVE its figure is handled, and a caption with no figure pixels next to it is reported."""
    import subprocess, tempfile
    x = subprocess.run(["pdftotext", "-bbox-layout", "-f", str(page), "-l", str(page), pdf, "-"], capture_output=True, text=True, timeout=60).stdout
    pg = re.search(r'<page width="([\d.]+)" height="([\d.]+)"', x)
    if not pg:
        sys.exit("pdftotext -bbox-layout gave no page %s (page out of range, encrypted or scanned PDF?)" % page)
    pw, ph = [float(v) for v in pg.groups()]
    blocks = [([float(v) for v in m.group(1, 2, 3, 4)], unescape(" ".join(re.findall(r">([^<]+)</word>", m.group(5)))), m.group(5).count("<line"))
              for m in re.finditer(r'<block xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">(.*?)</block>', x, re.S)]
    key = re.sub(r"\s+", "", label).lower()
    cap = min([b for b in blocks if re.sub(r"\s+", "", b[1]).lower().startswith(key)], key=lambda b: b[2], default=None)  # caption = shortest match
    if not cap:
        sys.exit("caption %r not found on page %s; blocks start with: %s" % (label, page, [b[1][:25] for b in blocks][:15]))
    (x0, y0, x1, y1), table = cap[0], label.strip().lower().startswith(("tab", "表"))
    widths = sorted(b[0][2] - b[0][0] for b in blocks if b[2] >= 2) or [pw]
    twocol = widths[len(widths) // 2] < pw * 0.5  # median paragraph width -> two-column page
    lo, hi = (0, pw / 2) if twocol and x1 < pw * 0.55 else (pw / 2, pw) if twocol and x0 > pw * 0.45 else (0, pw)
    prose = lambda b: len(b[1].split()) >= 6 and b[1].rstrip().endswith((".", "。", ":", ";")) or b[0][2] - b[0][0] > (hi - lo) * 0.6
    para = [b for b in blocks if b is not cap and b[0][2] > lo and b[0][0] < hi and prose(b)]  # body text bounds the crop
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
    other = [b for b in blocks if b is not cap and lo - 5 <= b[0][0] < hi and len(b[1].split()) <= 30 and (re.match(r"\d{1,2}(\.\d{1,2})*\.?\s+[A-Z\u4e00-\u9fff][a-z\u4e00-\u9fff]", b[1])
             or re.match(r"(Fig(ure)?\.?|Table|Tab\.|Scheme|图|表)\s*S?\d+[a-z]?\s*[.:|：]", b[1]))]  # section headings + other captions bound a figure
    if table:  # tables: caption above + rows below, kept together; stops at body text or the next section heading
        head = [b for b in blocks if re.match(r"(\d{1,2}(\.\d{1,2})*\.?$|\d{1,2}(\.\d{1,2})*\.?\s+[A-Z\u4e00-\u9fff]|[IVX]+\.)", b[1]) and lo - 5 <= b[0][0] < hi]
        bot = min([b[0][1] for b in para + head if b[0][1] > y1 + 5] or [ph - 36]) - 2
        top, bot = y0 - 2, min(bot, max([b[0][3] for b in blocks if y1 <= b[0][1] < bot] or [bot]) + 12)  # room for the bottom rule; ink() trims
        box, where = ink(lo, top, hi, bot) or (lo, top, hi, bot), "table incl. its caption"
    else:  # figure above its caption; if that region is blank, the caption sits above the figure
        txt = [b for b in blocks if b is not cap and b[0][2] > lo and b[0][0] < hi and (prose(b) or b[0][2] - b[0][0] > (hi - lo) * 0.4 and len(b[1].split()) >= 6)]
        above = (lo, max([b[0][3] for b in txt + other if b[0][3] <= y0 + 1] or [30]) + 2, hi, y0 - 1)
        below = (lo, y1 + 1, hi, min([b[0][1] for b in para + other if b[0][1] > y1 + 1] or [ph - 36]) - 2)
        box, where = ink(*above), "figure above caption (caption NOT in the image)"
        if box and keep_caption:
            box, where = (box[0], box[1], box[2], y1 + 2), "figure above caption (caption kept)"
        if not box:
            box, where = ink(*below), "figure below caption (caption NOT in the image)"
            if box and keep_caption:
                box, where = (box[0], y0 - 2, box[2], box[3]), "figure below caption (caption kept)"
        if not box:
            box, where = (lo, above[1], hi, y1 + 2), "WARN no figure pixels next to the caption: the PDF may not contain this figure -> do not insert it, record a material gap"
    l, t, r, bt = max(box[0], 0), max(box[1], 0), min(box[2], pw), min(box[3], ph)
    subprocess.run(["pdftoppm", "-r", str(dpi), "-f", str(page), "-l", str(page), "-x", str(int(l * k)), "-y", str(int(t * k)), "-W", str(int((r - l) * k)),
                    "-H", str(int((bt - t) * k)), "-png", "-singlefile", pdf, out[:-4] if out.endswith(".png") else out], check=True, timeout=120)
    within = [b for b in blocks if b[0][1] >= t - 1 and b[0][3] <= bt + 1 and b[0][0] >= l - 1 and b[0][2] <= r + 1]
    print("cropped page %s [%.0f,%.0f,%.0f,%.0f]pt (%.1f x %.1f in, aspect %.2f; %s) -> %s" % (page, l, t, r, bt, (r - l) / 72, (bt - t) / 72, (r - l) / max(bt - t, 1), where, out))
    print("caption (put the label + a short version on the slide as editable text):\n  %s" % cap[1][:300])
    print("text inside crop (should be axis labels/legend/panel letters, not body paragraphs): %s" % [b[1][:40] for b in within][:12])
    if any(b[2] >= 3 and len(b[1].split()) >= 5 * b[2] and b is not cap for b in within):
        print("WARN crop contains a multi-line text block - may be a body paragraph; check the PNG or use pdfimages")

def paper(pdf, outdir):
    """paper.pdf -> OUTDIR/paper.txt (pdftotext -layout, form feed = page break) + a map: pages, text per page (scan check),
    section headings, every Figure/Table caption with page (column-aware, from bbox blocks) and raster-image count per page."""
    import subprocess
    os.makedirs(outdir, exist_ok=True)
    txt = os.path.join(outdir, "paper.txt")
    try:
        r = subprocess.run(["pdftotext", "-layout", pdf, txt], capture_output=True, text=True, timeout=120)
    except Exception as e:
        sys.exit("pdftotext unavailable (%s): extract text another way (python zlib on the PDF streams) and record it in exceptions" % e)
    if r.returncode:
        sys.exit("pdftotext failed (%s) - encrypted? try qpdf --decrypt; scanned? pdftoppm + tesseract" % r.stderr.strip()[-200:])
    pages = open(txt, encoding="utf-8", errors="ignore").read().split("\f")
    pages = pages[:-1] if pages and not pages[-1].strip() else pages
    print("paper.txt: %s (%d pages, %d chars; layout kept - use it for tables)" % (txt, len(pages), sum(len(p) for p in pages)))
    try:  # reading-order text: columns are not interleaved, so prose can be read and quoted line by line
        flow = os.path.join(outdir, "paper_flow.txt")
        subprocess.run(["pdftotext", pdf, flow], capture_output=True, text=True, timeout=120)
        fp = open(flow, encoding="utf-8", errors="ignore").read().split("\f")
        print("paper_flow.txt: %s (reading order, one column at a time - READ and QUOTE prose from this file; page N starts at line %s)" % (
            flow, ", ".join("p%d:%d" % (i + 1, 1 + sum(x.count("\n") for x in fp[:i])) for i in range(min(len(fp), 40)) if fp[i].strip())))
    except Exception as e:
        print("(paper_flow.txt not written: %s)" % e)
    thin = [i for i, p in enumerate(pages, 1) if len(p.strip()) < 200]
    if thin:
        print("WARN pages with almost no text layer (scanned/figure-only?): %s" % thin[:20])
    try:
        il = subprocess.run(["pdfimages", "-list", pdf], capture_output=True, text=True, timeout=60).stdout.splitlines()[2:]
    except Exception:
        il = []
    imgs = {}
    for ln in il:
        f = ln.split()
        if len(f) > 4 and f[0].isdigit() and f[2] == "image" and int(f[3]) * int(f[4]) > 40000:
            imgs[int(f[0])] = imgs.get(int(f[0]), 0) + 1
    print("sections (page | heading):")
    num = lambda t: re.match(r"(?:[1-9]|1[0-5])(?:\.\d{1,2})*\.?$", t)
    for i, p in enumerate(pages, 1):
        for ln in p.splitlines():
            seg = [g for g in re.split(r"\s{3,}", ln.strip()) if g]
            for a, g in enumerate(seg):
                m = re.match(r"((?:[1-9]|1[0-5])(?:\.\d{1,2})*\.?)\s{1,2}([A-Z\u4e00-\u9fff][a-z\u4e00-\u9fff][^.]{0,50})$", g)
                if m or (num(g) and a + 1 < len(seg) and re.match(r"[A-Z][a-z]", seg[a + 1])):
                    print("  p.%d | %s" % (i, (m.group(1) + " " + m.group(2)) if m else g + " " + seg[a + 1][:50]))
                elif not (a and num(seg[a - 1])) and re.match(r"(Abstract|Introduction|Methods?|Results?|Discussion|Conclusions?|References|Limitations|Acknowledg\w+|摘要|引言|方法|结果|讨论|结论|参考文献)$", g):
                    print("  p.%d | %s" % (i, g))
    print("captions (page | label | start) - cite exactly these numbers; raster = big bitmap images on that page (0 -> vector figure: use figcrop):")
    LBL = re.compile(r"^(Fig(?:ure)?\.?|Table|Tab\.|Scheme|图|表)\s*(S?\d+[a-z]?)\s*[.:|：]")
    for i in range(1, len(pages) + 1):
        try:
            x = subprocess.run(["pdftotext", "-bbox-layout", "-f", str(i), "-l", str(i), pdf, "-"], capture_output=True, text=True, timeout=60).stdout
        except Exception as e:
            print("  p.%d caption scan skipped: %s" % (i, e))
            continue
        for m in re.finditer(r"<block [^>]*>(.*?)</block>", x, re.S):
            t = unescape(" ".join(re.findall(r">([^<]+)</word>", m.group(1))))
            c = LBL.match(t)
            if c:
                print("  p.%d | %s %s | %s | raster=%d" % (i, c.group(1), c.group(2), t[:110], imgs.get(i, 0)))

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
    if len(sys.argv) < 3 or sys.argv[1] not in ("inspect", "build", "figcrop", "render", "paper"):
        sys.exit(__doc__)
    if sys.argv[1] == "render":
        render(sys.argv[2])
    elif sys.argv[1] == "paper":
        paper(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else os.environ.get("WORK_DIR", "."))
    elif sys.argv[1] == "figcrop":
        a = [v for v in sys.argv[2:] if not v.startswith("--")]
        figcrop(*a[:4], **dict({"dpi": int(a[4])} if len(a) > 4 else {}, keep_caption="--keep-caption" in sys.argv))
    else:
        inspect(sys.argv[2], "--full" in sys.argv) if sys.argv[1] == "inspect" else build(sys.argv[2], sys.argv[3:])
