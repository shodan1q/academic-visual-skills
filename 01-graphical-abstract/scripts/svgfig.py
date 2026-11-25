#!/usr/bin/env python3
"""svgfig (stdlib, py3.8+): layered, editable SVG figures from a JSON spec, plus source-level edits.
  build spec.json out.svg        spec -> SVG (layers, ids, data-src on every element) + out_elements.tsv
  edit in.svg out.svg ID [--text "new label"] [--set attr=value ...]   change one element in place, rest untouched
  diff old.svg new.svg           element-level change log (proof that an edit kept the source)
Spec keys: canvas{w,h,width_mm,title,font,grid{x0,y0,dx,dy}}, panels[{id,x,y,w,h,title,fill}], nodes[{id,label,cx,cy|col,row,
w,h,shape(rect|round|band|ellipse|circle|diamond),fill,stroke,fs,italic,bold,src}], edges[{id,from,to(node id or [x,y]),
type,label,via[[x,y]],elbow(hv|vh),color,width,both,src}], texts[{id,text,x,y,fs,anchor,bold,italic,color,w,src}],
bars[{id,x,y,w,h,title,unit,max,items[{label,value,err,text,color,src}]}] (bar heights = value, data-value kept), legend{x,y,title,items[{edge:type|fill:#hex,label}]}.  Edge types: activate inhibit bind modify transport indirect flow signal step line"""
import json, os, re, sys
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape
EDGE = {"activate": ("", "tri", "#1B7837"), "inhibit": ("", "bar", "#B2182B"), "bind": ("", "dot", "#555555"),
        "modify": ("", "open", "#7B3294"), "transport": ("7,4", "tri", "#2166AC"), "indirect": ("2,4", "tri", "#777777"),
        "flow": ("", "tri", "#2166AC"), "signal": ("5,3", "tri", "#E08214"), "step": ("", "tri", "#333333"), "line": ("", "none", "#333333")}
FONT = "Arial, Helvetica, 'Noto Sans CJK SC', 'Source Han Sans SC', 'WenQuanYi Micro Hei', 'PingFang SC', 'Microsoft YaHei', sans-serif"
q = lambda s: escape(str(s), {'"': "&quot;"})  # noqa: E731

def tw(s, fs, bold=False):
    return sum(fs * (1.0 if ord(c) > 0x2E80 else (0.6 if bold else 0.56)) for c in s)

def wrap(text, w, fs, bold=False):
    out = []
    for para in str(text).split("\n"):
        cur = ""
        for tok in re.findall(r"[⺀-￿]|[^\s⺀-￿]+\s*|\s+", para):
            if cur.strip() and tw(cur + tok.rstrip(), fs, bold) > w:
                out, cur = out + [cur.rstrip()], tok.lstrip()
            else:
                cur += tok
        out.append(cur.rstrip())
    return out

def txt(i, x, y, lines, fs, o, src="", anchor="middle", color="#111111"):
    st = (' font-weight="bold"' if o.get("bold") else "") + (' font-style="italic"' if o.get("italic") else "")
    sp = "".join('<tspan x="%.1f" dy="%s">%s</tspan>' % (x, "0" if k == 0 else "1.2em", escape(l)) for k, l in enumerate(lines))
    return '<text id="%s" x="%.1f" y="%.1f" font-size="%.1f" text-anchor="%s" fill="%s"%s data-src="%s">%s</text>' % (
        i, x, y, fs, anchor, o.get("color", color), st, q(src), sp)

def head(i, kind, col, a, b, sw=2, s=""):
    """End glyph at b for the segment a->b as plain polygon/polyline/line/circle (no <marker>: some rasterizers skip markers).
    Returns (svg, point where the line itself should stop)."""
    d = ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5 or 1.0
    ux, uy, k = (b[0] - a[0]) / d, (b[1] - a[1]) / d, max(1.0, float(sw) / 2.0) ** 0.5
    ln, hw, at = min(11.0 * k, max(d - 2, 4.0)), 5.0 * k, 'id="%s" data-src="%s"' % (i, q(s))
    c, P = (b[0] - ux * ln, b[1] - uy * ln), "%.1f,%.1f %.1f,%.1f %.1f,%.1f"
    w = (c[0] - uy * hw, c[1] + ux * hw, b[0], b[1], c[0] + uy * hw, c[1] - ux * hw)
    if kind == "tri":
        return '<polygon %s points="%s" fill="%s"/>' % (at, P % w, col), (c[0] + ux, c[1] + uy)
    if kind == "open":
        return '<polyline %s points="%s" fill="none" stroke="%s" stroke-width="1.6"/>' % (at, P % w, col), b
    if kind == "bar":
        return '<line %s x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="3"/>' % (at, b[0] - uy * hw * 1.2, b[1] + ux * hw * 1.2, b[0] + uy * hw * 1.2, b[1] - ux * hw * 1.2, col), b
    if kind == "dot":
        return '<circle %s cx="%.1f" cy="%.1f" r="%.1f" fill="%s"/>' % (at, b[0] - ux * 4 * k, b[1] - uy * 4 * k, 4 * k, col), b
    return "", b

def clip(n, px, py):
    dx, dy, hw, hh, sh = px - n["cx"], py - n["cy"], n["w"] / 2.0, n["h"] / 2.0, n.get("shape", "rect")
    if not (dx or dy):
        return n["cx"], n["cy"]
    t = 1 / ((dx / hw) ** 2 + (dy / hh) ** 2) ** 0.5 if sh in ("ellipse", "circle") else 1 / (abs(dx) / hw + abs(dy) / hh) \
        if sh == "diamond" else min(hw / abs(dx) if dx else 9e9, hh / abs(dy) if dy else 9e9)
    return n["cx"] + dx * min(t, 1), n["cy"] + dy * min(t, 1)

def build(a):
    sp, out = json.load(open(a[0], encoding="utf-8")), a[1]
    cv, warn, rows, marks, N = sp.get("canvas", {}), [], [], {}, {}
    W, H, g = cv.get("w", 1200), cv.get("h", 800), cv.get("grid", {})
    L = {k: [] for k in ("panels", "edges", "nodes", "data", "text", "legend")}
    def src(o, kind, text):
        rows.append([o.get("id", "?"), kind, text, o.get("src", "")])
        warn.extend([] if o.get("src") else ["no src for %s %s" % (kind, o.get("id"))])
        return o.get("src", "")
    for p in sp.get("panels", []):
        s = src(p, "panel", p.get("title", ""))
        L["panels"].append('<rect id="%s" x="%s" y="%s" width="%s" height="%s" rx="8" fill="%s" stroke="%s" stroke-width="1.2" data-src="%s"/>' % (
            p["id"], p["x"], p["y"], p["w"], p["h"], p.get("fill", "#F7F7F7"), p.get("stroke", "#BBBBBB"), q(s)))
        if p.get("title"):
            L["text"].append(txt(p["id"] + "-title", p["x"] + 12, p["y"] + 24, [p["title"]], p.get("fs", 17), {"bold": 1}, s, "start"))
    for n in sp.get("nodes", []):
        n.setdefault("w", 150), n.setdefault("h", 54)
        if "col" in n:
            n["cx"], n["cy"] = g.get("x0", 120) + n["col"] * g.get("dx", 200), g.get("y0", 120) + n["row"] * g.get("dy", 110)
        N[n["id"]], s, sh = n, src(n, "node", n.get("label", "")), n.get("shape", "rect")
        x, y, w, h = n["cx"] - n["w"] / 2.0, n["cy"] - n["h"] / 2.0, n["w"], n["h"]
        base = 'id="%s" fill="%s" stroke="%s" stroke-width="1.5" data-src="%s"' % (n["id"], n.get("fill", "#FFFFFF"), n.get("stroke", "#333333"), q(s))
        L["nodes"].append('<ellipse %s cx="%s" cy="%s" rx="%s" ry="%s"/>' % (base, n["cx"], n["cy"], w / 2.0, h / 2.0) if sh in ("ellipse", "circle") else
                          '<polygon %s points="%s,%s %s,%s %s,%s %s,%s"/>' % (base, n["cx"], y, x + w, n["cy"], n["cx"], y + h, x, n["cy"]) if sh == "diamond" else
                          '<rect %s x="%s" y="%s" width="%s" height="%s" rx="%s"/>' % (base, x, y, w, h, {"round": 14, "band": 0}.get(sh, 4)))
        fs, pad = float(n.get("fs", 14)), (0.72 if sh in ("ellipse", "circle", "diamond") else 1.0)
        lines = wrap(n.get("label", ""), w * pad - 12, fs, n.get("bold"))
        while fs > 9 and (len(lines) * fs * 1.2 > h * pad - 4 or max(tw(l, fs) for l in lines) > w * pad - 8):
            fs -= 0.5
            lines = wrap(n.get("label", ""), w * pad - 12, fs, n.get("bold"))
        if len(lines) * fs * 1.2 > h * pad + 2 or max(tw(l, fs) for l in lines) > w * pad:
            warn.append("label overflows node %s even at 9px: enlarge w/h or shorten the label" % n["id"])
        L["nodes"].append(txt(n["id"] + "-label", n["cx"], n["cy"] - (len(lines) - 1) * fs * 0.6 + fs * 0.35, lines, fs, n, s))
    for e in sp.get("edges", []):
        dash, head_, col = EDGE.get(e.get("type", "step"), EDGE["step"])
        col, s = e.get("color", col), src(e, "edge:" + e.get("type", "step"), e.get("label", ""))
        ends = [N.get(e[k]) if isinstance(e[k], str) else None for k in ("from", "to")]
        if any(isinstance(e[k], str) and not ends[i] for i, k in enumerate(("from", "to"))):
            warn.append("edge %s refers to an unknown node id" % e.get("id"))
            continue
        pts = [(n["cx"], n["cy"]) if n else tuple(e[k]) for n, k in zip(ends, ("from", "to"))]
        pts[1:1] = [tuple(v) for v in e.get("via", [])] or ([(pts[1][0], pts[0][1]) if e["elbow"] == "hv" else (pts[0][0], pts[1][1])] if e.get("elbow") else [])
        warn += ["edge %s: via point %s lies inside node %s (move it outside)" % (e.get("id"), v, k) for v in e.get("via", []) for k, n in N.items() if abs(v[0] - n["cx"]) < n["w"] / 2.0 and abs(v[1] - n["cy"]) < n["h"] / 2.0]
        pts[0] = clip(ends[0], *pts[1]) if ends[0] else pts[0]
        pts[-1] = clip(ends[1], *pts[-2]) if ends[1] else pts[-1]
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            warn += ["edge %s passes through node %s: add via points or move nodes" % (e.get("id"), k) for k, n in N.items() if all(n is not x for x in ends) and any(
                abs(x1 + (x2 - x1) * f / 20.0 - n["cx"]) < n["w"] / 2.0 - 3 and abs(y1 + (y2 - y1) * f / 20.0 - n["cy"]) < n["h"] / 2.0 - 3 for f in range(1, 20))]
        hd, lp = [], list(pts)  # heads are separate elements <edge id>-head / -head0; lp = line shortened under a filled head
        if head_ != "none":
            g, lp[-1] = head(e["id"] + "-head", head_, col, pts[-2], pts[-1], e.get("width", 2), s)
            hd.append(g)
            if e.get("both"):
                g, lp[0] = head(e["id"] + "-head0", head_, col, pts[1], pts[0], e.get("width", 2), s)
                hd.append(g)
        L["edges"].append('<polyline id="%s" points="%s" fill="none" stroke="%s" stroke-width="%s"%s data-src="%s"/>' % (
            e["id"], " ".join("%.1f,%.1f" % p for p in lp), col, e.get("width", 2), ' stroke-dasharray="%s"' % dash if dash else "", q(s)))
        L["edges"].extend(hd)
        if e.get("label"):
            k = len(pts) // 2
            mx, my, lw = (pts[k - 1][0] + pts[k][0]) / 2.0, (pts[k - 1][1] + pts[k][1]) / 2.0, tw(e["label"], 12)
            vert = abs(pts[k][1] - pts[k - 1][1]) > abs(pts[k][0] - pts[k - 1][0])
            lx, ly, anc = (mx + 7, my + 4, "start") if vert else (mx, my - 7, "middle")
            L["edges"].append('<rect id="%s-labelbg" x="%.1f" y="%.1f" width="%.1f" height="16" fill="#FFFFFF" opacity="0.85"/>' % (e["id"], lx - 2 - (0 if vert else lw / 2), ly - 13, lw + 4))
            L["edges"].append(txt(e["id"] + "-label", lx, ly, [e["label"]], 12, e, s, anc, col))
    for t in sp.get("texts", []):
        lines = wrap(t["text"], t["w"], t.get("fs", 14), t.get("bold")) if t.get("w") else str(t["text"]).split("\n")
        L["text"].append(txt(t["id"], t["x"], t["y"], lines, t.get("fs", 14), t, src(t, "text", t["text"]), t.get("anchor", "start")))
    for c in sp.get("bars", []):
        its, s0, u = c["items"], src(c, "chart", c.get("title", "")), c.get("unit", "")
        vmax, bw, base = float(c.get("max") or max(float(i["value"]) + float(i.get("err", 0)) for i in its) * 1.15 or 1), c["w"] / (len(its) * 1.5 + 0.5), c["y"] + c["h"] - 22
        L["data"].append('<line id="%s-axis" x1="%s" y1="%s" x2="%s" y2="%s" stroke="#333333"/>' % (c["id"], c["x"], base, c["x"] + c["w"], base))
        for k, i in enumerate(its):
            v, er, s = float(i["value"]), float(i.get("err", 0)), src(dict(i, id="%s-bar%d" % (c["id"], k)), "bar", "%s=%s" % (i["label"], i["value"]))
            sc, bx = (base - c["y"] - 40) / vmax, c["x"] + bw * (0.5 + 1.5 * k)
            warn.extend(["negative value %s in %s: bars start at 0, use a different chart" % (v, c["id"])] if v < 0 else [])
            L["data"].append('<rect id="%s-bar%d" x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s" data-value="%s" data-src="%s"/>' % (c["id"], k, bx, base - v * sc, bw, v * sc, i.get("color", "#4C72B0"), v, q(s)))
            if er:
                L["data"].append('<path id="%s-err%d" d="M%.1f,%.1f V%.1f M%.1f,%.1f h8 M%.1f,%.1f h8" stroke="#222222" fill="none" data-value="%s"/>' % (c["id"], k, bx + bw / 2, base - (v - er) * sc, base - (v + er) * sc, bx + bw / 2 - 4, base - (v + er) * sc, bx + bw / 2 - 4, base - (v - er) * sc, er))
            L["data"].append(txt("%s-val%d" % (c["id"], k), bx + bw / 2, base - (v + er) * sc - 5, [i.get("text", ("%g%s" if u[:1] in ("%", "", "-", "×", "°") else "%g %s") % (v, u))], 12, {}, s))
            L["data"].append(txt("%s-lab%d" % (c["id"], k), bx + bw / 2, base + 15, [i["label"]], 12, {}, s))
        if c.get("title"):
            L["data"].append(txt(c["id"] + "-title", c["x"] + c["w"] / 2, c["y"] + 14, [c["title"]], 13, {"bold": 1}, s0))
    lg = sp.get("legend")
    if lg:
        y = lg["y"] + (22 if lg.get("title") else 4)
        if lg.get("title"):
            L["legend"].append(txt("legend-title", lg["x"], lg["y"] + 12, [lg["title"]], 13, {"bold": 1}, lg.get("src", ""), "start"))
        for k, it in enumerate(lg["items"]):
            i = "legend-%d" % k
            if it.get("edge"):
                dash, head_, col = EDGE[it["edge"]]
                col = it.get("color", col)
                g, end = head(i + "-head", head_, col, (lg["x"], y + 6), (lg["x"] + 34, y + 6), 2, "legend")
                L["legend"].append('<line id="%s-glyph" x1="%s" y1="%s" x2="%.1f" y2="%s" stroke="%s" stroke-width="2"%s/>%s' % (i, lg["x"], y + 6, end[0], y + 6, col,
                                   ' stroke-dasharray="%s"' % dash if dash else "", g))
            else:
                L["legend"].append('<rect id="%s-glyph" x="%s" y="%s" width="30" height="13" fill="%s" stroke="#555555"/>' % (i, lg["x"], y, it["fill"]))
            L["legend"].append(txt(i, lg["x"] + 44, y + 11, [it["label"]], 12, {}, it.get("src", "legend"), "start"))
            y += 20
    elif sp.get("edges") or sp.get("bars"):
        warn.append("no legend: add one item per edge type / fill colour used")
    if cv.get("title"):
        L["text"].append(txt("figure-title", W / 2.0, 34, [cv["title"]], cv.get("title_fs", 22), {"bold": 1}, cv.get("src", ""), "middle"))
    wa, ha = ("%smm" % cv["width_mm"], "%.2fmm" % (cv["width_mm"] * H / float(W))) if cv.get("width_mm") else (W, H)  # physical size for journals
    body = "\n".join('<g id="layer-%s">\n%s\n</g>' % (k, "\n".join(v)) for k, v in L.items())
    open(out, "w", encoding="utf-8").write('<?xml version="1.0" encoding="UTF-8"?>\n<svg xmlns="http://www.w3.org/2000/svg" width="%s" height="%s" viewBox="0 0 %s %s" font-family="%s">\n<title>%s</title>\n<defs>%s</defs>\n<rect id="background" width="100%%" height="100%%" fill="#FFFFFF"/>\n%s\n</svg>\n' % (
        wa, ha, W, H, q(cv.get("font", FONT)), escape(cv.get("title", "figure")), "".join(marks.values()), body))
    with open(os.path.splitext(out)[0] + "_elements.tsv", "w", encoding="utf-8") as f:
        f.write("id\tkind\ttext\tsrc\n" + "".join("\t".join(re.sub(r"\s+", " ", str(c)) for c in r) + "\n" for r in rows))
    print("\n".join(["WARN: " + w for w in warn] or ["no warnings"]) + "\nwrote %s (%d elements; source table %s_elements.tsv)" % (out, len(rows), os.path.splitext(out)[0]))

def edit(a):
    src, out, i, opt = open(a[0], encoding="utf-8").read(), a[1], a[2], a[3:]
    m = re.search(r'<(\w+)\b[^>]*\bid="%s"[^>]*?(/?)>' % re.escape(i), src)
    if not m:
        print("FAIL: id %r not found in %s" % (i, a[0]))
        return 1
    tagtxt, end = m.group(0), m.end()
    for k, v in zip(opt[::2], opt[1::2]):
        if k == "--set":
            at, val = v.split("=", 1)
            new = re.sub(r'\s%s="[^"]*"' % re.escape(at), ' %s="%s"' % (at, q(val)), tagtxt)
            tagtxt = new if new != tagtxt else tagtxt.replace("<%s " % m.group(1), '<%s %s="%s" ' % (m.group(1), at, q(val)), 1)
        elif k == "--text":
            close = src.index("</%s>" % m.group(1), end)
            xs = re.search(r'<tspan x="([^"]*)"', src[end:close])
            lines = v.split("\\n")
            body = "".join('<tspan x="%s" dy="%s">%s</tspan>' % (xs.group(1), "0" if n == 0 else "1.2em", escape(l)) for n, l in enumerate(lines)) if xs else escape(v)
            src = src[:end] + body + src[close:]
    src = src[:m.start()] + tagtxt + src[m.end():]
    ET.fromstring(src.encode("utf-8"))
    open(out, "w", encoding="utf-8").write(src)
    print("edited %s -> %s (id %s); run diff to log it" % (a[0], out, i))

def index(path):
    return {el.get("id"): (el.tag.split("}")[-1], " / ".join(" ".join("".join(s.itertext()).split()) for s in el) or " ".join("".join(el.itertext()).split()) if el.tag.endswith("text") else "",
                           {k: v for k, v in el.attrib.items() if k != "id"}) for el in ET.parse(path).getroot().iter() if el.get("id")}

def diff(a):
    o, n = index(a[0]), index(a[1])
    ch = [{"id": k, "change": "removed", "before": o[k][1] or o[k][0]} for k in o if k not in n]
    ch += [{"id": k, "change": "added", "after": n[k][1] or n[k][0]} for k in n if k not in o]
    for k in (k for k in o if k in n and o[k] != n[k]):
        ch += [{"id": k, "change": "text", "before": o[k][1], "after": n[k][1]}] if o[k][1] != n[k][1] else []
        ch += [{"id": k, "change": at, "before": o[k][2].get(at), "after": n[k][2].get(at)} for at in sorted(set(o[k][2]) | set(n[k][2])) if o[k][2].get(at) != n[k][2].get(at)]
    print(json.dumps({"old": a[0], "new": a[1], "kept_ids": len(set(o) & set(n)), "changes": ch}, ensure_ascii=False, indent=1))

CMDS = {"build": build, "edit": edit, "diff": diff}
if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] not in CMDS:
        print(__doc__)
        sys.exit(2)
    sys.exit(CMDS[sys.argv[1]](sys.argv[2:]) or 0)
