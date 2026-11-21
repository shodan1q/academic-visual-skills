#!/usr/bin/env python3
"""svgfig (stdlib, py3.8+): layered, editable pathway/mechanism SVG from a JSON spec, plus source-level edits.
  build spec.json out.svg   -> SVG (layers, ids, data-src) + out_content_map.json (entities/relations/legend/data, src)
  edit in.svg out.svg ID [--text "new label"] [--set attr=value ...]   change one element, rest byte-identical
  diff old.svg new.svg      -> element-level change log (proof the edit kept the source)
Spec: canvas{w,h,width_mm,title,src,colorscale{csv,key,value,breaks[],colors[],title,src}},
panels[{id,x,y,w,h,title,fill,src}] (h<44 = membrane band, title drawn inside), nodes[{id,label,kind,comp,data,cx,cy,w,h,
shape,fill,fs,italic,bold,aliases,xref,src}], edges[{id,from,to,type,evidence,label,via[[x,y]],elbow,width,both,src}],
texts[{id,text,x,y,fs,w,src}], legend{x,y,title,items[{edge|fill|evidence,label}]} (missing items are auto-added).
kind: gene mrna protein complex family small_molecule ion cell process; gene/mrna -> italic.  comp: id of the panel it sits in.
type: activate inhibit bind modify transport indirect line (+ flow signal step).  evidence: direct|indirect|hypothesis."""
import csv, hashlib, json, os, re, sys
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape
EDGE = {"activate": ("", "tri", "#1B7837"), "inhibit": ("", "bar", "#B2182B"), "bind": ("", "dot", "#555555"),
        "modify": ("", "open", "#7B3294"), "transport": ("7,4", "tri", "#2166AC"), "indirect": ("2,4", "tri", "#777777"),
        "flow": ("", "tri", "#2166AC"), "signal": ("5,3", "tri", "#E08214"), "step": ("", "tri", "#333333"), "line": ("", "none", "#333333")}
ELAB = {"activate": "activation / induction", "inhibit": "inhibition", "bind": "binding / complex", "modify": "modification (+P, +Ub)",
        "transport": "translocation / secretion", "indirect": "indirect effect", "line": "association (no direction)"}
EVID = {"indirect": "2,4", "hypothesis": "9,4,2,4"}
HEAD = {"tri": '<path d="M0,0 L10,5 L0,10 z" fill="%s"/>', "open": '<path d="M0,0 L10,5 L0,10" fill="none" stroke="%s" stroke-width="1.6"/>',
        "bar": '<path d="M5,-1 L5,11" stroke="%s" stroke-width="3"/>', "dot": '<circle cx="6" cy="5" r="4" fill="%s"/>'}
REF = {"tri": 9, "open": 9, "bar": 6, "dot": 10}
CS = ["#2166AC", "#92C5DE", "#F7F7F7", "#F4A582", "#D6604D", "#B2182B", "#67001F"]
FONT = "Arial, Helvetica, 'Noto Sans CJK SC', 'Source Han Sans SC', 'WenQuanYi Micro Hei', 'PingFang SC', 'Microsoft YaHei', sans-serif"
q = lambda s: escape(str(s), {'"': "&quot;"})  # noqa: E731
nm = lambda s: re.sub(r"[^a-z0-9α-ω]", "", str(s).lower().replace("p-", ""))  # noqa: E731

def tw(s, fs, bold=False):
    return sum(fs * (1.0 if ord(c) > 0x2E80 else (0.6 if bold else 0.56)) for c in s)

def lum(c):
    c = c.lstrip("#")
    if len(c) != 6:
        return 1.0
    v = [int(c[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    return sum(k * (x / 12.92 if x <= 0.04 else ((x + 0.055) / 1.055) ** 2.4) for k, x in zip((0.2126, 0.7152, 0.0722), v))

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

def clip(n, px, py):
    dx, dy, hw, hh, sh = px - n["cx"], py - n["cy"], n["w"] / 2.0, n["h"] / 2.0, n.get("shape", "rect")
    if not (dx or dy):
        return n["cx"], n["cy"]
    t = 1 / ((dx / hw) ** 2 + (dy / hh) ** 2) ** 0.5 if sh in ("ellipse", "circle") else 1 / (abs(dx) / hw + abs(dy) / hh) \
        if sh == "diamond" else min(hw / abs(dx) if dx else 9e9, hh / abs(dy) if dy else 9e9)
    return n["cx"] + dx * min(t, 1), n["cy"] + dy * min(t, 1)

def inside(x, y, b, pad=0):
    return b[0] + pad < x < b[2] - pad and b[1] + pad < y < b[3] - pad

def colorscale(cs, base, warn):
    p = cs["csv"] if os.path.isabs(cs["csv"]) else os.path.join(base, cs["csv"])
    rows = list(csv.DictReader(open(p, encoding="utf-8-sig")))
    br, cols = [float(b) for b in cs["breaks"]], cs.get("colors") or []
    if len(cols) != len(br) + 1:
        cols = CS[(len(CS) - len(br) - 1) // 2:][:len(br) + 1]
        warn.append("colorscale: need len(colors) == len(breaks)+1; using default diverging colours")
    g = lambda v: "%g" % v  # noqa: E731
    labs = ["< " + g(br[0])] + ["%s to < %s" % (g(a), g(b)) for a, b in zip(br, br[1:])] + ["≥ " + g(br[-1])]
    sha = hashlib.sha256(open(p, "rb").read()).hexdigest()[:16]
    return rows, br, cols, labs, {"file": cs["csv"], "sha256_16": sha, "value_column": cs["value"], "key_column": cs.get("key"),
                                  "breaks": br, "bins": [{"label": l, "color": c} for l, c in zip(labs, cols)]}

def build(a):
    sp, out = json.load(open(a[0], encoding="utf-8")), a[1]
    cv, warn, marks, N, P = sp.get("canvas", {}), [], {}, {}, {}
    W, H, g = cv.get("w", 1200), cv.get("h", 800), cv.get("grid", {})
    L = {k: [] for k in ("panels", "edges", "nodes", "data", "text", "legend")}
    cm = {"entities": [], "relations": [], "compartments": [], "legend": [], "data_encoding": None, "warnings": warn}
    def src(o, kind):
        warn.extend([] if o.get("src") else ["no src for %s %s" % (kind, o.get("id"))])
        return o.get("src", "")
    def mk(head, col):
        k = "m-%s-%s" % (head, col.strip("#"))
        marks[k] = '<marker id="%s" viewBox="-1 -1 13 13" refX="%d" refY="5" markerWidth="12" markerHeight="12" markerUnits="userSpaceOnUse" orient="auto-start-reverse">%s</marker>' % (k, REF[head], HEAD[head] % col)
        return k
    for p in sp.get("panels", []):
        s, thin = src(p, "panel"), p["h"] < 44
        P[p["id"]] = (p["x"], p["y"], p["x"] + p["w"], p["y"] + p["h"])
        cm["compartments"].append({"id": p["id"], "title": p.get("title", ""), "src": s})
        L["panels"].append('<rect id="%s" x="%s" y="%s" width="%s" height="%s" rx="%s" fill="%s" stroke="%s" stroke-width="1.2" data-src="%s"/>' % (
            p["id"], p["x"], p["y"], p["w"], p["h"], 3 if thin else 8, p.get("fill", "#F2D7B6" if thin else "#F7F7F7"), p.get("stroke", "#BBBBBB"), q(s)))
        if p.get("title"):
            L["text"].append(txt(p["id"] + "-title", p["x"] + 10, p["y"] + (p["h"] / 2.0 + 4.5 if thin else 24), [p["title"]], p.get("fs", 12.5 if thin else 17), {"bold": 1}, s, "start"))
        else:
            warn.append("panel %s has no title: every compartment/membrane must be named on the figure" % p["id"])
    sc = cv.get("colorscale")
    rows, br, cols, labs, enc = colorscale(sc, os.path.dirname(os.path.abspath(a[0])), warn) if sc else ([], [], [], [], None)
    cm["data_encoding"], nodata = enc and dict(enc, nodes=[]), False
    for n in sp.get("nodes", []):
        n.setdefault("w", 150), n.setdefault("h", 54)
        if "col" in n:
            n["cx"], n["cy"] = g.get("x0", 120) + n["col"] * g.get("dx", 200), g.get("y0", 120) + n["row"] * g.get("dy", 110)
        N[n["id"]], s, sh, kd = n, src(n, "node"), n.get("shape", "rect"), n.get("kind", "")
        n.setdefault("italic", kd in ("gene", "mrna"))
        if kd in ("protein", "complex", "family") and n["italic"] or kd in ("gene", "mrna") and not n["italic"]:
            warn.append("node %s: kind %s but italic=%s (genes/mRNA italic, proteins upright)" % (n["id"], kd, n["italic"]))
        if not kd:
            warn.append("node %s has no kind (gene/mrna/protein/complex/family/small_molecule/cell/process)" % n["id"])
        if n.get("comp") and n["comp"] not in P:
            warn.append("node %s: comp %s is not a panel id" % (n["id"], n["comp"]))
        elif n.get("comp") and not inside(n["cx"], n["cy"], P[n["comp"]], -1):
            warn.append("node %s centre (%s,%s) is outside its compartment %s" % (n["id"], n["cx"], n["cy"], n["comp"]))
        dv = None
        if sc and n.get("data") is not None:
            r = next((r for r in rows if r.get(sc.get("key", "")) == n["data"]), None) or next((r for r in rows if n["data"] in r.values()), None)
            try:
                dv = float(r[sc["value"]])
                k = sum(dv >= b for b in br)
                n["fill"] = cols[k]
                cm["data_encoding"]["nodes"].append({"node": n["id"], "key": n["data"], "value": dv, "bin": labs[k], "color": cols[k]})
            except (TypeError, KeyError, ValueError):
                warn.append("node %s: data key %r has no numeric %s in %s" % (n["id"], n["data"], sc["value"], sc["csv"]))
        elif sc and kd not in ("small_molecule", "ion", "process", "cell", "") and "fill" not in n:
            nodata = True
        x, y, w, h = n["cx"] - n["w"] / 2.0, n["cy"] - n["h"] / 2.0, n["w"], n["h"]
        fill = n.get("fill", "#FFFFFF")
        base = 'id="%s" fill="%s" stroke="%s" stroke-width="1.5" data-src="%s"' % (n["id"], fill, n.get("stroke", "#333333"), q(s))
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
        o = dict(n, color=n.get("color", "#FFFFFF" if lum(fill) < 0.18 else "#111111"))
        L["nodes"].append(txt(n["id"] + "-label", n["cx"], n["cy"] - (len(lines) - 1) * fs * 0.6 + fs * 0.35, lines, fs, o, s))
        cm["entities"].append({"id": n["id"], "label": n.get("label", ""), "kind": kd, "compartment": n.get("comp", ""), "italic": n["italic"],
                               "fill": fill, "data_value": dv, "aliases": n.get("aliases", []), "xref": n.get("xref", ""), "src": s})
    lg, used, segs, seen, LB = sp.get("legend"), [], [], {}, []
    for e in sp.get("edges", []):
        t, ev = e.get("type", "step"), e.get("evidence", "direct")
        dash, head, col = EDGE.get(t, EDGE["step"])
        dash, col, s = EVID.get(ev, dash), e.get("color", col), src(e, "edge")
        used += [("edge", t)] + ([("evidence", ev)] if ev in EVID else [])
        ends = [N.get(e[k]) if isinstance(e[k], str) else None for k in ("from", "to")]
        if any(isinstance(e[k], str) and not ends[i] for i, k in enumerate(("from", "to"))):
            warn.append("edge %s refers to an unknown node id" % e.get("id"))
            continue
        if t == "transport" and all(ends) and not (nm(ends[0].get("label")) in nm(ends[1].get("label")) or nm(ends[1].get("label")) in nm(ends[0].get("label"))):
            warn.append("edge %s: transport joins different entities (%s -> %s); transport = the SAME entity moving between compartments. "
                        "Draw a copy in the target compartment, then activate (e.g. transcription) to the gene" % (e["id"], ends[0].get("label"), ends[1].get("label")))
        pair = frozenset((e["from"], e["to"])) if isinstance(e["from"], str) and isinstance(e["to"], str) else None
        if pair and pair in seen and not (e.get("via") or e.get("elbow")):
            warn.append("edges %s and %s draw over each other (same node pair): give one a via route or merge them" % (seen[pair], e["id"]))
        seen[pair] = e["id"]
        pts = [(n["cx"], n["cy"]) if n else tuple(e[k]) for n, k in zip(ends, ("from", "to"))]
        pts[1:1] = [tuple(v) for v in e.get("via", [])] or ([(pts[1][0], pts[0][1]) if e["elbow"] == "hv" else (pts[0][0], pts[1][1])] if e.get("elbow") else [])
        warn += ["edge %s: via point %s lies inside node %s (move it outside)" % (e.get("id"), v, k) for v in e.get("via", []) for k, n in N.items() if abs(v[0] - n["cx"]) < n["w"] / 2.0 and abs(v[1] - n["cy"]) < n["h"] / 2.0]
        pts[0] = clip(ends[0], *pts[1]) if ends[0] else pts[0]
        pts[-1] = clip(ends[1], *pts[-2]) if ends[1] else pts[-1]
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            segs.append((e["id"], x1, y1, x2, y2))
            warn += ["edge %s passes through node %s: add via points or move nodes" % (e.get("id"), k) for k, n in N.items() if all(n is not x for x in ends) and any(
                abs(x1 + (x2 - x1) * f / 20.0 - n["cx"]) < n["w"] / 2.0 - 3 and abs(y1 + (y2 - y1) * f / 20.0 - n["cy"]) < n["h"] / 2.0 - 3 for f in range(1, 20))]
        m = (' marker-end="url(#%s)"' % mk(head, col) if head != "none" else "") + (' marker-start="url(#%s)"' % mk(head, col) if e.get("both") and head != "none" else "")
        L["edges"].append('<polyline id="%s" points="%s" fill="none" stroke="%s" stroke-width="%s"%s%s data-src="%s"/>' % (
            e["id"], " ".join("%.1f,%.1f" % p for p in pts), col, e.get("width", 2), ' stroke-dasharray="%s"' % dash if dash else "", m, q(s)))
        lab = lambda i: (ends[i] or {}).get("label", str(e[("from", "to")[i]]))  # noqa: E731
        cm["relations"].append({"id": e["id"], "from": lab(0), "to": lab(1), "type": t, "evidence": ev, "label": e.get("label", ""), "src": s})
        if e.get("label"):
            k = len(pts) // 2
            mx, my, lw = (pts[k - 1][0] + pts[k][0]) / 2.0, (pts[k - 1][1] + pts[k][1]) / 2.0, tw(e["label"], 12)
            vert = abs(pts[k][1] - pts[k - 1][1]) > abs(pts[k][0] - pts[k - 1][0])
            lx, ly, anc = (mx + 7, my + 4, "start") if vert else (mx, my - 7, "middle")
            bx = lx - 2 - (0 if vert else lw / 2)
            warn += ["label of edge %s (%r) is hidden under node %s: shorten it or move nodes" % (e["id"], e["label"], k) for k, n in N.items()
                     if bx < n["cx"] + n["w"] / 2.0 and bx + lw + 4 > n["cx"] - n["w"] / 2.0 and ly - 13 < n["cy"] + n["h"] / 2.0 and ly + 3 > n["cy"] - n["h"] / 2.0]
            LB.append('<rect id="%s-labelbg" x="%.1f" y="%.1f" width="%.1f" height="16" fill="#FFFFFF" opacity="0.85"/>' % (e["id"], bx, ly - 13, lw + 4))
            LB.append(txt(e["id"] + "-label", lx, ly, [e["label"]], 12, e, s, anc, col))
    L["edges"] += LB  # labels after all lines, so no later edge is drawn over a label
    for t in sp.get("texts", []):
        lines = wrap(t["text"], t["w"], t.get("fs", 14), t.get("bold")) if t.get("w") else str(t["text"]).split("\n")
        L["text"].append(txt(t["id"], t["x"], t["y"], lines, t.get("fs", 14), t, src(t, "text"), t.get("anchor", "start")))
    fills = sorted({n.get("fill") for n in N.values() if n.get("fill") and n.get("fill") not in cols and n.get("fill").upper() != "#FFFFFF"})
    if lg:
        given = {(("edge", it["edge"]) if it.get("edge") else ("evidence", it["evidence"]) if it.get("evidence") else ("fill", it.get("fill", "").upper())): it for it in lg.get("items", [])}
        have, uk = set(given), [u for u in EDGE if ("edge", u) in used] + [u for u in EVID if ("evidence", u) in used]
        items = [given.get((k, v)) or {k: v, "label": ELAB.get(v, v) if k == "edge" else v + " evidence"} for k in ("edge", "evidence") for v in uk if (k, v) in used]
        warn += ["legend lists %s %s that is not used in the figure" % h for h in have if h[0] != "fill" and h not in set(used)]
        warn += ["fill %s used on nodes but has no legend item (say what it encodes)" % f for f in fills if ("fill", f.upper()) not in have]
        if enc:
            items += [{"head": enc and sc.get("title", sc["value"])}] + [{"fill": c, "label": l} for l, c in zip(labs, cols)] + ([{"fill": "#FFFFFF", "label": "no value in " + os.path.basename(sc["csv"])}] if nodata else [])
        items += [it for h, it in given.items() if h[0] == "fill"]  # own fill items last: adding one later keeps earlier ids stable
        y = lg["y"] + (22 if lg.get("title") else 4)
        if lg.get("title"):
            L["legend"].append(txt("legend-title", lg["x"], lg["y"] + 12, [lg["title"]], 13, {"bold": 1}, lg.get("src", ""), "start"))
        for k, it in enumerate(items):
            i = "legend-" + next(p + re.sub(r"[^a-z0-9]+", "", str(it[k]).lower()) for k, p in (("edge", "edge-"), ("evidence", "ev-"), ("fill", "fill-"), ("head", "head")) if it.get(k))
            if it.get("head"):
                L["legend"].append(txt(i, lg["x"], y + 15, [it["head"]], 12, {"bold": 1}, sc.get("src", sc["csv"]), "start"))
                y += 24
                continue
            if it.get("edge") or it.get("evidence"):
                dash, head, col = EDGE[it["edge"]] if it.get("edge") else (EVID[it["evidence"]], "none", "#555555")
                col = it.get("color", col)
                L["legend"].append('<line id="%s-glyph" x1="%s" y1="%s" x2="%s" y2="%s" stroke="%s" stroke-width="2"%s%s/>' % (i, lg["x"], y + 6, lg["x"] + 34, y + 6, col,
                                   ' stroke-dasharray="%s"' % dash if dash else "", ' marker-end="url(#%s)"' % mk(head, col) if head != "none" else ""))
            else:
                L["legend"].append('<rect id="%s-glyph" x="%s" y="%s" width="30" height="13" fill="%s" stroke="#555555"/>' % (i, lg["x"], y, it["fill"]))
            L["legend"].append(txt(i, lg["x"] + 44, y + 11, [it["label"]], 12, {}, it.get("src", "legend"), "start"))
            cm["legend"].append(it)
            y += 20
        lb = (lg["x"] - 4, lg["y"] - 4, lg["x"] + 44 + max([tw(str(it.get("label", it.get("head", ""))), 12) for it in items] or [0]) + 4, y + 2)
        warn += ["edge %s crosses the legend box: re-route it (via) or move the legend" % e for e in sorted({s[0] for s in segs if any(inside(s[1] + (s[3] - s[1]) * f / 30.0, s[2] + (s[4] - s[2]) * f / 30.0, lb) for f in range(31))})]
        warn += ["legend runs past the canvas (right edge %.0f > w %s): widen canvas.w or move the legend" % (lb[2], W)] if lb[2] > W or y > H else []
        warn += ["node %s overlaps the legend box" % k for k, n in N.items() if n["cx"] + n["w"] / 2.0 > lb[0] and n["cx"] - n["w"] / 2.0 < lb[2] and n["cy"] + n["h"] / 2.0 > lb[1] and n["cy"] - n["h"] / 2.0 < lb[3]]
    elif sp.get("edges"):
        warn.append("no legend: add legend{x,y} (items are auto-filled from the edge types, evidence styles and colour scale used)")
    if cv.get("title"):
        L["text"].append(txt("figure-title", W / 2.0, 34, [cv["title"]], cv.get("title_fs", 22), {"bold": 1}, cv.get("src", ""), "middle"))
    wa, ha = ("%smm" % cv["width_mm"], "%.2fmm" % (cv["width_mm"] * H / float(W))) if cv.get("width_mm") else (W, H)  # physical size for journals
    body = "\n".join('<g id="layer-%s">\n%s\n</g>' % (k, "\n".join(v)) for k, v in L.items())
    open(out, "w", encoding="utf-8").write('<?xml version="1.0" encoding="UTF-8"?>\n<svg xmlns="http://www.w3.org/2000/svg" width="%s" height="%s" viewBox="0 0 %s %s" font-family="%s">\n<title>%s</title>\n<defs>%s</defs>\n<rect id="background" width="100%%" height="100%%" fill="#FFFFFF"/>\n%s\n</svg>\n' % (
        wa, ha, W, H, q(cv.get("font", FONT)), escape(cv.get("title", "figure")), "".join(marks.values()), body))
    cm["spec"], cm["spec_sha256_16"] = a[0], hashlib.sha256(open(a[0], "rb").read()).hexdigest()[:16]
    cmp_ = os.path.splitext(out)[0] + "_content_map.json"
    json.dump(cm, open(cmp_, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n".join(["WARN: " + w for w in warn] or ["no warnings"]) + "\nwrote %s and %s (%d entities, %d relations, %d legend items)" % (
        out, cmp_, len(cm["entities"]), len(cm["relations"]), len(cm["legend"])))

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
            box = re.search(r'id="%s"[^>]*?(?:\swidth="([\d.]+)"|\srx="([\d.]+)")' % re.escape(i[:-6]), src) if i.endswith("-label") else None
            fm = re.search(r'font-size="([\d.]+)"', tagtxt)
            fs = float(fm.group(1)) if fm else 14.0
            bw = box and (float(box.group(1)) if box.group(1) else 2 * float(box.group(2)) * 0.72)
            if bw and max(tw(l, fs) for l in lines) > bw - 6:
                print("WARN: new label is wider than its node (%.0f > %.0f px): edit the spec (w or label) and rebuild instead" % (max(tw(l, fs) for l in lines), bw - 6))
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
    print(json.dumps({"old": a[0], "new": a[1], "kept_ids": len(set(o) & set(n)), "unchanged_ids": len(set(o) & set(n)) - len({c["id"] for c in ch}), "changes": ch}, ensure_ascii=False, indent=1))

CMDS = {"build": build, "edit": edit, "diff": diff}
if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] not in CMDS:
        print(__doc__)
        sys.exit(2)
    sys.exit(CMDS[sys.argv[1]](sys.argv[2:]) or 0)
