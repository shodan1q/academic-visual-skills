#!/usr/bin/env python3
"""svgfig (stdlib, py3.8+): layered, editable relationship schematics (structure / lineage / workflow / mechanism) from JSON.
  build spec.json out.svg   -> SVG (layers, ids, data-src) + out_content_map.json (entities, relations incl. containment, legend, data)
  edit in.svg out.svg ID [--text "new label"] [--set attr=value ...]   change one element, rest byte-identical
  diff old.svg new.svg      -> element-level change log (proof the edit kept the source)
Spec: canvas{w,h,width_mm,title,src, categories{csv,key,column,colors{category:#hex},title,show,fmt,src} | colorscale{csv,key,value,
breaks[],colors[],title,src}}, panels[{id,x,y,w,h,title,parent,fill,src}] (parent = enclosing panel id; h<44 = band),
nodes[{id,label,kind,comp,data,cx,cy|col,row,w,h,shape,fill,fs,italic,bold,aliases,src}], edges[{id,from,to (node or panel id),
type,evidence,label,via[[x,y]],elbow,width,both,src}], texts[{id,text,x,y,fs,w,src}], legend{x,y,title,items[]} (auto-filled).
comp = id of the innermost panel the node belongs to (containment).  gene/mrna -> italic.
type: step flow phospho produce signal activate inhibit bind modify transport indirect line; edge "legend" = own legend text for its type.
Auto layout: omit panel x/y/w/h and node cx/cy -> placed by the container's layout (row|col|grid; node col,row are panel-relative),
legend without x/y goes below the content in columns, texts without x/y become footnotes; the canvas grows so nothing is clipped.  evidence: direct|indirect|hypothesis."""
import csv, hashlib, json, os, re, sys
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape
EDGE = {"activate": ("", "tri", "#1B7837"), "inhibit": ("", "bar", "#B2182B"), "bind": ("", "dot", "#555555"),
        "modify": ("", "open", "#A6611A"), "transport": ("7,4", "tri", "#2166AC"), "indirect": ("2,4", "tri", "#777777"),
        "flow": ("", "tri", "#2166AC"), "phospho": ("", "tri", "#7B3294"), "produce": ("", "open", "#2166AC"), "signal": ("5,3", "tri", "#E08214"), "step": ("", "tri", "#333333"), "line": ("", "none", "#333333")}
ELAB = {"step": "next step (order)", "flow": "material / sample flow", "phospho": "phosphotransfer (~P)", "produce": "synthesis / expression", "signal": "signal / secreted factor",
        "activate": "activation / promotes", "inhibit": "inhibition", "bind": "binding / complex", "modify": "modification (+P, +Ub)",
        "transport": "translocation / secretion", "indirect": "indirect effect", "line": "association (no direction)"}
EVID = {"indirect": "2,4", "hypothesis": "9,4,2,4"}
OI = ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#56B4E9", "#D55E00", "#F0E442", "#999999"]  # Okabe-Ito
KINDS = {"gene", "mrna", "protein", "complex", "family", "small_molecule", "ion", "cell", "cell_type", "tissue", "organ", "organism",
         "sample", "material", "reagent", "condition", "instrument", "process", "step", "data", "concept", "group"}
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

def arrow_head(i, kind, col, p0, p1):
    """Arrow head as plain geometry at tip p1 (line comes from p0). No <marker>: several converters drop or mis-scale
    markers, and a relationship figure without heads has no direction. Returns (svg element, where the line should stop)."""
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    d = (dx * dx + dy * dy) ** 0.5 or 1.0
    ux, uy = dx / d, dy / d
    k = max(1.0, TF) ** 0.7  # heads and lines grow with the text so they stay visible at print size
    HL, HW = 11.0 * k, 5.0 * k
    bx, by, a = p1[0] - ux * HL, p1[1] - uy * HL, 'id="%s" data-head="%s"' % (i, kind)
    c1, c2 = (bx - uy * HW, by + ux * HW), (bx + uy * HW, by - ux * HW)
    if kind == "tri":
        return '<polygon %s points="%.1f,%.1f %.1f,%.1f %.1f,%.1f" fill="%s"/>' % (a, p1[0], p1[1], c1[0], c1[1], c2[0], c2[1], col), (p1[0] - ux * (HL - 2), p1[1] - uy * (HL - 2))
    if kind == "open":
        return '<polyline %s points="%.1f,%.1f %.1f,%.1f %.1f,%.1f" fill="none" stroke="%s" stroke-width="%.1f"/>' % (a, c1[0], c1[1], p1[0], p1[1], c2[0], c2[1], col, 2 * k ** 0.7), p1
    if kind == "bar":
        return '<line %s x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="%.1f"/>' % (a, p1[0] - uy * 8 * k, p1[1] + ux * 8 * k, p1[0] + uy * 8 * k, p1[1] - ux * 8 * k, col, 3.5 * k), p1
    return '<circle %s cx="%.1f" cy="%.1f" r="%.1f" fill="%s"/>' % (a, p1[0] - ux * 4 * k, p1[1] - uy * 4 * k, 4.5 * k, col), p1

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
    sha = hashlib.sha256(open(p, "rb").read()).hexdigest()[:16]
    if "column" in cs:  # categorical: one colour per category found in the table (legend = table)
        cats = [c for i, c in enumerate(r.get(cs["column"], "") for r in rows) if c and c not in [r.get(cs["column"]) for r in rows[:i]]]
        given = cs.get("colors") or {}
        cols = [given.get(c) or [x for x in OI if x not in given.values()][k % 8] for k, c in enumerate(cats)]
        warn += ["categories: colour given for %r, which is not a value of column %s" % (c, cs["column"]) for c in given if c not in cats]
        warn += ["categories: %r and %r share colour %s" % (a, b, x) for i, (a, x) in enumerate(zip(cats, cols)) for b, y in zip(cats[i + 1:], cols[i + 1:]) if x.upper() == y.upper()]
        return rows, None, cols, cats, {"file": cs["csv"], "sha256_16": sha, "category_column": cs["column"], "key_column": cs.get("key"),
                                        "categories": [{"label": c, "color": x, "n_rows": sum(r.get(cs["column"]) == c for r in rows)} for c, x in zip(cats, cols)]}
    br, cols = [float(b) for b in cs["breaks"]], cs.get("colors") or []
    if len(cols) != len(br) + 1:
        cols = CS[(len(CS) - len(br) - 1) // 2:][:len(br) + 1]
        warn.append("colorscale: need len(colors) == len(breaks)+1; using default diverging colours")
    g = lambda v: "%g" % v  # noqa: E731
    labs = ["< " + g(br[0])] + ["%s to < %s" % (g(a), g(b)) for a, b in zip(br, br[1:])] + ["≥ " + g(br[-1])]
    return rows, br, cols, labs, {"file": cs["csv"], "sha256_16": sha, "value_column": cs["value"], "key_column": cs.get("key"),
                                  "breaks": br, "bins": [{"label": l, "color": c} for l, c in zip(labs, cols)]}

M_ = 20  # canvas margin
TF = 1.0  # text scale, raised by build until the smallest text meets canvas.min_font_pt at canvas.width_mm

def autolayout(sp, warn):
    """Fill in missing geometry. Panels without x/y and nodes without cx/cy are placed by their container's layout:
    row | col | grid (child col,row, or row-major with cols). Containers size to their content, then stretch to fill."""
    cv, PT, nodes = sp.setdefault("canvas", {}), {p["id"]: p for p in sp.get("panels", [])}, sp.get("nodes", [])
    has = lambda o, ks: all(k in o for k in ks)  # noqa: E731
    free = lambda n: "cx" not in n and not ("col" in n and "grid" in cv)  # noqa: E731
    kids = {}
    for k, p in enumerate(sp.get("panels", [])):
        if not has(p, ("x", "y")):
            kids.setdefault(p.get("parent") if p.get("parent") in PT else "", []).append((p.get("order", k), "p", p))
    for k, n in enumerate(nodes):
        if free(n):
            fs = float(n.get("fs", 14)) * TF
            if "w" not in n:
                n["w"] = int(min(140 * TF ** 0.5, max(84, max([tw(l, fs, n.get("bold")) for l in str(n.get("label", "")).split("\n")] or [0]) + 28)))
            n.setdefault("h", int(max(42, len(wrap(n.get("label", ""), n["w"] - 12, fs)) * fs * 1.2 + 18)))
            kids.setdefault(n.get("comp") if n.get("comp") in PT else "", []).append((n.get("order", 1000 + k), "n", n))
    lg = sp.get("legend")
    if lg is not None and not has(lg, ("x", "y")):
        lg["_auto"] = True
    if not kids:
        return
    def depth(i, d=0):
        return d if PT[i].get("parent") not in PT or d > 9 else depth(PT[i]["parent"], d + 1)
    for i, p in PT.items():
        if not has(p, ("x", "y")) and depth(i):
            p.setdefault("fs", 13.5)
            p.setdefault("fill", ["#F7F7F7", "#FFFFFF", "#EFEFEF"][depth(i) % 3])
    th = lambda c: (float(c.get("fs", 17)) * (1 + 1.2 * (len(c.get("_tl") or [1]) - 1)) + 14) * TF if c and c.get("title") else 0  # noqa: E731
    nat = {}
    def size(i):
        c = PT.get(i)
        ks = [(t, x) for _, t, x in sorted(kids.get(i, []), key=lambda z: z[0])]
        lay = (c or {}).get("layout") or (cv.get("layout", "row") if c is None else "grid" if any("row" in x for _, x in ks)
                                          else "col" if all(t == "p" for t, _ in ks) and len(ks) > 1 else "row" if len(ks) <= cv.get("_maxrow", 4) else "grid")
        lay = "grid" if lay == "row" and any("row" in x and "col" in x for _, x in ks) else lay  # explicit col,row always win
        nc = int((c or {}).get("cols") or (-(-len(ks) // -(-len(ks) // cv["_maxrow"])) if cv.get("_maxrow") else max(1, int(len(ks) ** 0.5 + 0.999))))
        cell = [(0, k) if lay == "col" else (x.get("col", k % nc), x.get("row", k // nc)) if lay == "grid" else (k, 0) for k, (_, x) in enumerate(ks)]
        sz = [size(x["id"]) if t == "p" else (x["w"], x["h"]) for t, x in ks]
        gx = (c or cv).get("gap", cv.get("gap", 40))
        mine = {x.get("id") for t, x in ks if t == "n"}  # room for the labels of edges that run between neighbours in this container
        lab = [tw(str(e["label"]), 12 * TF) for e in sp.get("edges", []) if e.get("label") and e.get("from") in mine and e.get("to") in mine]
        gx = max(gx, min(max(lab), 90 * TF) + 14) if lab and "gap" not in (c or {}) else gx
        gy = (c or cv).get("vgap", cv.get("vgap", gx - 2))
        cw, rh = {}, {}
        for (a_, b_), (w, h) in zip(cell, sz):
            cw[a_], rh[b_] = max(cw.get(a_, 0), w), max(rh.get(b_, 0), h)
        pad = 14 if c else 0
        iw = sum(cw.values()) + gx * max(0, len(cw) - 1)
        ih = sum(rh.values()) + gy * max(0, len(rh) - 1)
        w = max(iw + 2 * pad, min(tw(str(c.get("title", "")), float(c.get("fs", 17)) * TF, True) + 2 * pad + 10, 230 * TF) if c else 0, 100 if c else 0)
        if c and c.get("title"):  # a long title wraps inside its panel instead of widening the whole figure
            c["_tl"] = wrap(str(c["title"]), w - 2 * pad - 6, float(c.get("fs", 17)) * TF, True)
        h = (th(c) + ih + 2 * pad) if ks else max(th(c) + 30, 60)
        nat[i] = (ks, cell, cw, rh, gx, gy, pad)
        if c is not None:
            if c.get("w", w) < w or c.get("h", h) < h:
                warn.append("NOTE panel %s: given w/h is smaller than its content; enlarged to %dx%d" % (i, w, h))
            w, h = max(w, c.get("w", 0)), max(h, c.get("h", 0))
        return w, h
    def place(i, x, y, w, h):
        ks, cell, cw, rh, gx, gy, pad = nat[i]
        c = PT.get(i)
        ix, iy, iw, ih = x + pad, y + th(c) + pad, w - 2 * pad, h - th(c) - 2 * pad
        sw, sh = sum(cw.values()) or 1.0, sum(rh.values()) or 1.0
        fh = max(1.0, (ih - gy * max(0, len(rh) - 1)) / float(sh))
        free_w, wide = iw - gx * max(0, len(cw) - 1), {}
        while True:  # equal column widths where content allows: grids line up and a relabel does not move other columns
            share = (free_w - sum(cw[k] for k in wide)) / float(max(1, len(cw) - len(wide)))
            more = {k for k in cw if k not in wide and cw[k] > share}
            if not more:
                break
            wide.update({k: 1 for k in more})
        cw = {k: (v if k in wide else max(v, share)) for k, v in cw.items()}
        rh = {k: v * fh for k, v in rh.items()}
        cx0 = {k: ix + sum(cw[j] + gx for j in cw if j < k) for k in cw}
        cy0 = {k: iy + sum(rh[j] + gy for j in rh if j < k) for k in rh}
        for (t, o), (a_, b_) in zip(ks, cell):
            if t == "p":
                o["x"], o["y"], o["w"], o["h"] = round(cx0[a_], 1), round(cy0[b_], 1), round(cw[a_], 1), round(rh[b_], 1)
                place(o["id"], o["x"], o["y"], o["w"], o["h"])
            else:
                o["cx"], o["cy"] = round(cx0[a_] + cw[a_] / 2.0, 1), round(cy0[b_] + rh[b_] / 2.0, 1)
    for i in [k for k in kids if k in PT and has(PT[k], ("x", "y"))]:  # explicit containers: lay out their children inside
        w, h = size(i)
        PT[i].setdefault("w", w), PT[i].setdefault("h", h)
        place(i, PT[i]["x"], PT[i]["y"], PT[i]["w"], PT[i]["h"])
    if "" in kids:
        w, h = size("")
        top = M_ + (44 * TF if cv.get("title") else 0)
        cv["w"] = int(max(cv.get("w", 0), w + 2 * M_, tw(str(cv.get("title", "")), cv.get("title_fs", 22) * TF, True) + 2 * M_) + 0.999)
        place("", M_, top, cv["w"] - 2 * M_, h)

def build(a):
    """Build. With canvas.width_mm set, fit the figure to the page: try the sub-figure arrangement (side by side / stacked) and
    spacing, and scale text moderately, until the smallest text is >= canvas.min_font_pt (default 6.5 pt) and the height fits a page."""
    global TF
    raw = open(a[0], encoding="utf-8").read()
    sp0 = json.loads(raw)
    cv0 = sp0.get("canvas", {})
    base, goal, mm = float(cv0.get("font_scale", 1.0)), float(cv0.get("min_font_pt", 6.5)), cv0.get("width_mm")
    auto = bool(mm) and "font_scale" not in cv0
    def spec(over):
        sp = json.loads(raw)
        sp.setdefault("canvas", {}).update(over)
        return sp
    def fit(over):
        global TF
        TF, best = base, None
        for _ in range(6):
            W, mf, H = _build(spec(over), a, False)
            pt = mf * mm / float(W) / 0.3528 if mm else goal
            if best is None or pt > best[0]:
                best = (pt, TF, H * mm / float(W) if mm else 0)
            if pt >= goal - 0.05 or TF >= 2.0 or not auto:
                break
            TF = min(2.0, TF * (goal / pt) ** 1.6 * 1.01)
        return best
    ids = {p.get("id") for p in sp0.get("panels", [])}
    tops = [p for p in sp0.get("panels", []) if p.get("parent") not in ids and "x" not in p]
    cands = [{}]
    if auto and not any(k in cv0 for k in ("gap", "vgap", "w")):
        cands = [{}, {"gap": 26}] + ([{"layout": "col", "gap": 34, "vgap": 24, "_maxrow": 5}, {"layout": "col", "gap": 26, "vgap": 20, "_maxrow": 6}, {"layout": "col", "gap": 40, "vgap": 24}] if len(tops) > 1 and "layout" not in cv0 else [])
    res = []
    for o in cands:
        res.append((fit(o), o))
        if res[-1][0][0] >= goal - 0.05 and res[-1][0][2] <= 235:
            break
    (pt, tf, hmm), over = next((r for r in res if r[0][0] >= goal - 0.05 and r[0][2] <= 235), None) or min([r for r in res if r[0][0] >= goal - 0.05] or [None], key=lambda r: r[0][2] if r else 0) or max(res, key=lambda r: r[0][0])
    TF = tf
    if over:
        print("NOTE: auto-fit to %s mm / %s pt chose %s (set canvas.layout / gap yourself to override)" % (mm, goal, ", ".join("%s=%s" % kv for kv in sorted(over.items()) if kv[0][0] != "_")))
    if auto and pt < goal - 0.05:
        print("WARN: smallest text is %.1f pt, below the required %s pt, even after re-arranging: shorten long labels, use fewer nodes per row (cols), or split the figure; otherwise record it as an exception" % (pt, goal))
    return _build(spec(over), a, True)[2]

def _build(sp, a, emit):
    out = a[1]
    cv, warn, N, P, FS = sp.get("canvas", {}), [], {}, {}, [12.0 * TF]
    autolayout(sp, warn)
    cv = sp["canvas"]
    W, H, g = cv.get("w") or 0, cv.get("h", 0), cv.get("grid", {})
    L = {k: [] for k in ("panels", "edges", "nodes", "data", "text", "legend")}
    cm = {"entities": [], "relations": [], "compartments": [], "legend": [], "data_encoding": None, "warnings": warn}
    def src(o, kind):
        warn.extend([] if o.get("src") else ["no src for %s %s" % (kind, o.get("id"))])
        return o.get("src", "")
    for p in sp.get("panels", []):
        s, thin = src(p, "panel"), p["h"] < 44
        P[p["id"]] = (p["x"], p["y"], p["x"] + p["w"], p["y"] + p["h"])
        cm["compartments"].append({"id": p["id"], "title": p.get("title", ""), "parent": p.get("parent", ""), "src": s})
        L["panels"].append('<rect id="%s" x="%s" y="%s" width="%s" height="%s" rx="%s" fill="%s" stroke="%s" stroke-width="1.2" data-src="%s"/>' % (
            p["id"], p["x"], p["y"], p["w"], p["h"], 3 if thin else 8, p.get("fill", "#F2D7B6" if thin else "#F7F7F7"), p.get("stroke", "#BBBBBB"), q(s)))
        if p.get("title"):
            pf = float(p.get("fs", 12.5 if thin else 17)) * TF
            tl = p.get("_tl") or [p["title"]]
            ty = p["y"] + (p["h"] / 2.0 + pf * 0.36 if thin else pf + 7 * TF)  # plain text on a small backing box: readable in every renderer, lines never run through it
            L["text"].append('<rect id="%s-titlebg" x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s"/>' % (p["id"], p["x"] + 6, ty - pf, max(tw(l, pf, True) for l in tl) + 10, pf * (1.3 + 1.2 * (len(tl) - 1)), p.get("fill", "#F2D7B6" if thin else "#F7F7F7")))
            L["text"].append(txt(p["id"] + "-title", p["x"] + 10, ty, tl, pf, {"bold": 1}, s, "start"))
        else:
            warn.append("panel %s has no title: every group / compartment / sub-figure must be named on the figure" % p["id"])
    PT = {p["id"]: p for p in sp.get("panels", [])}
    box_in = lambda b, o, pad=0: b[0] >= o[0] + pad and b[1] >= o[1] + pad and b[2] <= o[2] - pad and b[3] <= o[3] - pad  # noqa: E731
    for i, p in PT.items():
        par = p.get("parent")
        if par and par not in P:
            warn.append("panel %s: parent %s is not a panel id" % (i, par))
        elif par and not box_in(P[i], P[par], 2):
            warn.append("panel %s sticks out of its parent %s: containment must be drawn as full nesting" % (i, par))
        elif par:
            cm["relations"].append({"id": "contains-" + i, "from": PT[par].get("title", par), "to": p.get("title", i), "type": "contains", "evidence": "", "label": "", "src": p.get("src", "")})
    anc = lambda i: [i] + anc(PT[i]["parent"]) if i in PT and PT[i].get("parent") in PT and PT[i]["parent"] != i else [i]  # noqa: E731
    for i in PT:
        for j in PT:
            a_, b_ = P[i], P[j]
            ov = min(a_[2], b_[2]) - max(a_[0], b_[0]) > 2 and min(a_[3], b_[3]) - max(a_[1], b_[1]) > 2
            if i < j and ov and j not in anc(i) and i not in anc(j):
                warn.append("panels %s and %s overlap but neither is the other's parent: nest them (parent) or separate them" % (i, j))
    sc = cv.get("categories") or cv.get("colorscale")
    rows, br, cols, labs, enc = colorscale(sc, os.path.dirname(os.path.abspath(a[0])), warn) if sc else ([], [], [], [], None)
    cm["data_encoding"], nodata = enc and dict(enc, nodes=[]), False
    for n in sp.get("nodes", []):
        n.setdefault("w", 150), n.setdefault("h", 54)
        if "col" in n and "cx" not in n:
            n["cx"], n["cy"] = g.get("x0", 120) + n["col"] * g.get("dx", 200), g.get("y0", 120) + n["row"] * g.get("dy", 110)
        N[n["id"]], s, sh, kd = n, src(n, "node"), n.get("shape", "rect"), n.get("kind", "")
        n.setdefault("italic", kd in ("gene", "mrna"))
        if kd in ("protein", "complex", "family") and n["italic"] or kd in ("gene", "mrna") and not n["italic"]:
            warn.append("node %s: kind %s but italic=%s (genes/mRNA italic, proteins upright)" % (n["id"], kd, n["italic"]))
        if kd not in KINDS:
            warn.append("NOTE node %s: kind %r not in the known list (optional): %s" % (n["id"], kd, " ".join(sorted(KINDS))))
        nb = (n["cx"] - n["w"] / 2.0, n["cy"] - n["h"] / 2.0, n["cx"] + n["w"] / 2.0, n["cy"] + n["h"] / 2.0)
        deep = [k for k in P if box_in(nb, P[k]) and not any(k2 != k and box_in(nb, P[k2]) and k in anc(k2) for k2 in P)]
        if n.get("comp") and n["comp"] not in P:
            warn.append("node %s: comp %s is not a panel id" % (n["id"], n["comp"]))
        elif n.get("comp") and not box_in(nb, P[n["comp"]]):
            warn.append("node %s is not fully inside its group %s (containment unreadable)" % (n["id"], n["comp"]))
        elif n.get("comp") and deep and n["comp"] not in deep:
            warn.append("node %s is drawn inside %s but comp says %s: move it or fix comp" % (n["id"], deep[0], n["comp"]))
        elif not n.get("comp") and deep:
            warn.append("NOTE node %s sits inside panel %s without comp (optional; add comp=%s if it belongs to that group)" % (n["id"], deep[0], deep[0]))
        if n.get("comp") in PT:
            cm["relations"].append({"id": "contains-" + n["id"], "from": PT[n["comp"]].get("title", n["comp"]), "to": n.get("label", n["id"]), "type": "contains", "evidence": "", "label": "", "src": s})
        dv = None
        if sc and br is None and n.get("data") is not None:  # categorical
            r = next((r for r in rows if r.get(sc.get("key", "")) == n["data"]), None)
            if r is None or r.get(sc["column"]) not in labs:
                warn.append("node %s: data key %r not found in column %s of %s" % (n["id"], n["data"], sc.get("key"), sc["csv"]))
            else:
                dv, n["fill"] = r[sc["column"]], cols[labs.index(r[sc["column"]])]
                if sc.get("show") and sc["show"] in r:
                    n["label"] = n.get("label", "") + "\n" + sc.get("fmt", "n = {}").format(r[sc["show"]])
                cm["data_encoding"]["nodes"].append({"node": n["id"], "key": n["data"], "category": dv, "color": n["fill"],
                                                     "shown": {sc["show"]: r.get(sc["show"])} if sc.get("show") else {}})
        elif sc and n.get("data") is not None:
            r = next((r for r in rows if r.get(sc.get("key", "")) == n["data"]), None) or next((r for r in rows if n["data"] in r.values()), None)
            try:
                dv = float(r[sc["value"]])
                k = sum(dv >= b for b in br)
                n["fill"] = cols[k]
                cm["data_encoding"]["nodes"].append({"node": n["id"], "key": n["data"], "value": dv, "bin": labs[k], "color": cols[k]})
            except (TypeError, KeyError, ValueError):
                warn.append("node %s: data key %r has no numeric %s in %s" % (n["id"], n["data"], sc["value"], sc["csv"]))
        elif sc and br is not None and kd not in ("small_molecule", "ion", "process", "step", "condition", "") and "fill" not in n:
            nodata = True
        x, y, w, h = n["cx"] - n["w"] / 2.0, n["cy"] - n["h"] / 2.0, n["w"], n["h"]
        fill = n.get("fill", "#FFFFFF")
        base = 'id="%s" fill="%s" stroke="%s" stroke-width="1.5" data-src="%s"' % (n["id"], fill, n.get("stroke", "#333333"), q(s))
        L["nodes"].append('<ellipse %s cx="%s" cy="%s" rx="%s" ry="%s"/>' % (base, n["cx"], n["cy"], w / 2.0, h / 2.0) if sh in ("ellipse", "circle") else
                          '<polygon %s points="%s,%s %s,%s %s,%s %s,%s"/>' % (base, n["cx"], y, x + w, n["cy"], n["cx"], y + h, x, n["cy"]) if sh == "diamond" else
                          '<rect %s x="%s" y="%s" width="%s" height="%s" rx="%s"/>' % (base, x, y, w, h, {"round": 14, "band": 0}.get(sh, 4)))
        fs, pad = float(n.get("fs", 14)) * TF, (0.72 if sh in ("ellipse", "circle", "diamond") else 1.0)
        lines = wrap(n.get("label", ""), w * pad - 12, fs, n.get("bold"))
        while fs > 9 * TF and (len(lines) * fs * 1.2 > h * pad - 4 or max(tw(l, fs) for l in lines) > w * pad - 8):
            fs -= 0.5
            lines = wrap(n.get("label", ""), w * pad - 12, fs, n.get("bold"))
        if len(lines) * fs * 1.2 > h * pad + 2 or max(tw(l, fs) for l in lines) > w * pad:
            warn.append("label overflows node %s even at 9px: enlarge w/h or shorten the label" % n["id"])
        o = dict(n, color=n.get("color", "#FFFFFF" if lum(fill) < 0.18 else "#111111"))
        FS.append(fs)
        L["nodes"].append(txt(n["id"] + "-label", n["cx"], n["cy"] - (len(lines) - 1) * fs * 0.6 + fs * 0.35, lines, fs, o, s))
        cm["entities"].append({"id": n["id"], "label": n.get("label", ""), "kind": kd, "compartment": n.get("comp", ""), "italic": n["italic"],
                               "fill": fill, "data_value": dv, "aliases": n.get("aliases", []), "xref": n.get("xref", ""), "src": s})
    lg, used, segs, seen, LB, ELAB_, LBOX, HD, head_ = sp.get("legend"), [], [], {}, [], dict(ELAB), [], [], arrow_head
    PN = {i: {"cx": (b[0] + b[2]) / 2.0, "cy": (b[1] + b[3]) / 2.0, "w": b[2] - b[0], "h": b[3] - b[1], "label": PT[i].get("title", i)} for i, b in P.items()}
    num = lambda n: re.match(r"\s*(\d+)[\s.)]", str((n or {}).get("label", "")) + " ")  # noqa: E731
    for e in sp.get("edges", []):
        t, ev = e.get("type", "step"), e.get("evidence", "direct")
        dash, head, col = EDGE.get(t, EDGE["step"])
        dash, col, s = EVID.get(ev, dash), e.get("color", col), src(e, "edge")
        used += [("edge", t)] + ([("evidence", ev)] if ev in EVID else [])
        if e.get("legend"):
            ELAB_[t] = e["legend"]
        ends = [N.get(e[k]) or PN.get(e[k]) if isinstance(e[k], str) else None for k in ("from", "to")]
        if any(isinstance(e[k], str) and not ends[i] for i, k in enumerate(("from", "to"))):
            warn.append("edge %s refers to an unknown node/panel id" % e.get("id"))
            continue
        if t == "step" and num(ends[0]) and num(ends[1]) and int(num(ends[0]).group(1)) >= int(num(ends[1]).group(1)):
            warn.append("edge %s: step goes from %s to %s, against the step numbering (check direction/order)" % (e["id"], num(ends[0]).group(1), num(ends[1]).group(1)))
        if t == "transport" and all(ends) and not (nm(ends[0].get("label")) in nm(ends[1].get("label")) or nm(ends[1].get("label")) in nm(ends[0].get("label"))):
            warn.append("edge %s: transport joins different entities (%s -> %s); transport = the SAME entity moving between compartments. "
                        "Draw a copy in the target compartment, then activate (e.g. transcription) to the gene" % (e["id"], ends[0].get("label"), ends[1].get("label")))
        pair = frozenset((e["from"], e["to"])) if isinstance(e["from"], str) and isinstance(e["to"], str) else None
        if pair and pair in seen and not (e.get("via") or e.get("elbow")):
            warn.append("edges %s and %s draw over each other (same node pair): give one a via route or merge them" % (seen[pair], e["id"]))
        seen[pair] = e["id"]
        pts = [(n["cx"], n["cy"]) if n else tuple(e[k]) for n, k in zip(ends, ("from", "to"))]
        hit = lambda ps: [k for k, n in N.items() if all(n is not x for x in ends) and any(abs(x1 + (x2 - x1) * f / 20.0 - n["cx"]) < n["w"] / 2.0 - 3 and  # noqa: E731
                                                                                     abs(y1 + (y2 - y1) * f / 20.0 - n["cy"]) < n["h"] / 2.0 - 3 for (x1, y1), (x2, y2) in zip(ps, ps[1:]) for f in range(1, 20))]
        el = e.get("elbow")
        if not (e.get("via") or el) and hit(pts) and all(ends):  # auto-route: try an L-shaped connector that misses the other nodes
            el = next((k for k in ("vh", "hv") if not hit([pts[0], (pts[1][0], pts[0][1]) if k == "hv" else (pts[0][0], pts[1][1]), pts[1]])), None)
        dt = []
        if not (e.get("via") or el) and hit(pts) and all(ends):  # still blocked: step out sideways (or above/below) and come back in
            (x0, y0), (x1, y1) = pts
            ox, oy = max(ends[0]["w"], ends[1]["w"]) / 2.0 + 18, max(ends[0]["h"], ends[1]["h"]) / 2.0 + 14
            cand = [[(x0 + k * ox, y0), (x0 + k * ox, y1)] for k in (1, -1)] + [[(x0, y0 + k * oy), (x1, y0 + k * oy)] for k in (1, -1)] + [[((x0 + x1) / 2.0, y0), ((x0 + x1) / 2.0, y1)], [(x0, (y0 + y1) / 2.0), (x1, (y0 + y1) / 2.0)]]
            dt = next((c for c in cand if not hit([pts[0]] + c + [pts[1]])), [])
        pts[1:1] = [tuple(v) for v in e.get("via", [])] or dt or ([(pts[1][0], pts[0][1]) if el == "hv" else (pts[0][0], pts[1][1])] if el else [])
        warn += ["edge %s: via point %s lies inside node %s (move it outside)" % (e.get("id"), v, k) for v in e.get("via", []) for k, n in N.items() if abs(v[0] - n["cx"]) < n["w"] / 2.0 and abs(v[1] - n["cy"]) < n["h"] / 2.0]
        pts[0] = clip(ends[0], *pts[1]) if ends[0] else pts[0]
        pts[-1] = clip(ends[1], *pts[-2]) if ends[1] else pts[-1]
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            segs.append((e["id"], x1, y1, x2, y2, {e["from"], e["to"]} if isinstance(e["from"], str) and isinstance(e["to"], str) else set()))
            warn += ["edge %s passes through node %s: add via points or move nodes" % (e.get("id"), k) for k, n in N.items() if all(n is not x for x in ends) and any(
                abs(x1 + (x2 - x1) * f / 20.0 - n["cx"]) < n["w"] / 2.0 - 3 and abs(y1 + (y2 - y1) * f / 20.0 - n["cy"]) < n["h"] / 2.0 - 3 for f in range(1, 20))]
        lp, hd = list(pts), []
        if head != "none" and len(pts) > 1:
            h1, lp[-1] = head_(e["id"] + "-head", head, col, pts[-2], pts[-1])
            hd.append(h1)
            if e.get("both"):
                h0, lp[0] = head_(e["id"] + "-head0", head, col, pts[1], pts[0])
                hd.append(h0)
        L["edges"].append('<polyline id="%s" points="%s" fill="none" stroke="%s" stroke-width="%s"%s data-type="%s" data-src="%s"/>' % (
            e["id"], " ".join("%.1f,%.1f" % p for p in lp), col, round(e.get("width", 2) * max(1.0, TF) ** 0.5, 1), ' stroke-dasharray="%s"' % dash if dash else "", t, q(s)))
        HD.extend(hd)
        lab = lambda i: (ends[i] or {}).get("label", str(e[("from", "to")[i]]))  # noqa: E731
        cm["relations"].append({"id": e["id"], "from": lab(0), "to": lab(1), "type": t, "evidence": ev, "label": e.get("label", ""), "src": s})
        if e.get("label"):
            fl = 12 * TF
            lw, k0 = tw(e["label"], fl), len(pts) // 2
            def lpos(k, f, side):
                mx, my = pts[k - 1][0] + (pts[k][0] - pts[k - 1][0]) * f, pts[k - 1][1] + (pts[k][1] - pts[k - 1][1]) * f
                vert = abs(pts[k][1] - pts[k - 1][1]) > abs(pts[k][0] - pts[k - 1][0])
                lx, ly, anc = ((mx + 7, my + 4, "start") if side else (mx - 7, my + 4, "end")) if vert else (mx, my - 7 if side else my + fl + 6, "middle")
                bx = lx - 2 - (0 if anc == "start" else lw if anc == "end" else lw / 2)
                bad = [j for j, n in N.items() if bx < n["cx"] + n["w"] / 2.0 and bx + lw + 4 > n["cx"] - n["w"] / 2.0 and ly - fl - 1 < n["cy"] + n["h"] / 2.0 and ly + 3 > n["cy"] - n["h"] / 2.0]
                bad += ["label of " + o for o, b in LBOX if bx < b[2] and bx + lw + 4 > b[0] and ly - fl - 1 < b[3] and ly + 3 > b[1]]
                return lx, ly, anc, bx, bad
            cands = [lpos(k, f, sd) for k in sorted(range(1, len(pts)), key=lambda j: abs(j - k0)) for f in (0.5, 0.35, 0.65) for sd in (1, 0)]
            lx, ly, anc, bx, bad = next((c for c in cands if not c[4]), cands[0])
            warn += ["label of edge %s (%r) is hidden under %s: shorten it or move nodes" % (e["id"], e["label"], b) for b in bad]
            LBOX.append((e["id"], (bx, ly - fl - 1, bx + lw + 4, ly + 3)))
            LB.append('<rect id="%s-labelbg" x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="#FFFFFF" opacity="0.85"/>' % (e["id"], bx, ly - fl - 1, lw + 4, fl + 4))
            LB.append(txt(e["id"] + "-label", lx, ly, [e["label"]], fl, e, s, anc, col))
    cr = lambda a, b: all(((b[1] - a[1]) * (b[4] - a[2]) - (b[2] - a[2]) * (b[3] - a[1])) * ((b[1] - a[3]) * (b[4] - a[4]) - (b[2] - a[4]) * (b[3] - a[3])) < 0 for a, b in ((a, b), (b, a)))  # noqa: E731
    warn += ["edges %s and %s cross each other: move nodes or add via so connector lines do not cross" % pr for pr in sorted({(a[0], b[0]) for i, a in enumerate(segs) for b in segs[i + 1:] if a[0] != b[0] and not (a[5] & b[5]) and cr(a, b)})]
    L["edges"] += LB + HD  # labels after all lines, heads last: direction is never hidden under a line or a label box
    fills = sorted({n.get("fill") for n in N.values() if n.get("fill") and n.get("fill") not in cols and n.get("fill").upper() != "#FFFFFF"})
    bot = max([b[3] for b in P.values()] + [n["cy"] + n["h"] / 2.0 for n in N.values()] + [40])
    rgt = max([b[2] for b in P.values()] + [n["cx"] + n["w"] / 2.0 for n in N.values()] + [W - M_, tw(str(cv.get("title", "")), cv.get("title_fs", 22) * TF, True) + M_])
    if lg:
        given = {(("edge", it["edge"]) if it.get("edge") else ("evidence", it["evidence"]) if it.get("evidence") else ("fill", it.get("fill", "").upper())): it for it in lg.get("items", [])}
        have, uk = set(given), [u for u in EDGE if ("edge", u) in used] + [u for u in EVID if ("evidence", u) in used]
        items = [given.get((k, v)) or {k: v, "label": ELAB_.get(v, v) if k == "edge" else v + " evidence"} for k in ("edge", "evidence") for v in uk if (k, v) in used]
        warn += ["legend lists %s %s that is not used in the figure" % h for h in have if h[0] != "fill" and h not in set(used)]
        warn += ["fill %s used on nodes but has no legend item (say what it encodes)" % f for f in fills if ("fill", f.upper()) not in have]
        nblk = len(items)
        if enc:
            items += [{"head": sc.get("title", sc.get("value") or sc.get("column"))}] + [dict({"fill": c, "label": l}, **({"cat": l} if br is None else {})) for l, c in zip(labs, cols)] + ([{"fill": "#FFFFFF", "label": "no value in " + os.path.basename(sc["csv"])}] if nodata else [])
        items += [it for h, it in given.items() if h[0] == "fill"]  # own fill items last: adding one later keeps earlier ids stable
        if lg.get("_auto"):
            lg["x"], lg["y"] = M_, bot + 16
        fl, rh_ = 12 * TF, 21 * TF
        colw = 44 + max([tw(str(it.get("label", it.get("head", ""))), fl, bool(it.get("head"))) for it in items] or [0]) + 30
        ncol = int(lg.get("cols") or (max(1, min(len(items), int((max(W, rgt + M_) - lg["x"] - M_ + 30) // colw))) if lg.get("_auto") else 1))
        blocks = [items[:nblk], items[nblk:]] if enc and nblk else [items]
        per = max(-(-len(items) // ncol), max(len(b) for b in blocks) if ncol >= len(blocks) else 0)
        slots, k = [], 0
        for b in blocks:
            if k % per and k % per + len(b) > per and len(b) <= per:
                k += per - k % per
            slots += list(range(k, k + len(b)))
            k += len(b)
        y0 = lg["y"] + (22 * TF if lg.get("title") else 4)
        if lg.get("title"):
            L["legend"].append(txt("legend-title", lg["x"], lg["y"] + 12 * TF, [lg["title"]], 13 * TF, {"bold": 1}, lg.get("src", ""), "start"))
        for k, (it, sl) in enumerate(zip(items, slots)):
            x, y = lg["x"] + (sl // per) * colw, y0 + (sl % per) * rh_
            i = "legend-" + next(p + re.sub(r"[^a-z0-9]+", "", str(it[k]).lower()) for k, p in (("cat", "cat-"), ("edge", "edge-"), ("evidence", "ev-"), ("fill", "fill-"), ("head", "head")) if it.get(k))
            if it.get("head"):
                L["legend"].append(txt(i, x, y + 11 * TF, [it["head"]], fl, {"bold": 1}, sc.get("src", sc["csv"]), "start"))
                continue
            if it.get("edge") or it.get("evidence"):
                dash, head, col = EDGE[it["edge"]] if it.get("edge") else (EVID[it["evidence"]], "none", "#555555")
                col = it.get("color", col)
                gh, ge = head_(i + "-glyph-head", head, col, (x, y + 6 * TF), (x + 36, y + 6 * TF)) if head != "none" else ("", (x + 36, y + 6 * TF))
                L["legend"].append('<line id="%s-glyph" x1="%s" y1="%s" x2="%.1f" y2="%s" stroke="%s" stroke-width="2"%s/>%s' % (i, x, y + 6 * TF, ge[0], y + 6 * TF, col,
                                   ' stroke-dasharray="%s"' % dash if dash else "", gh))
            else:
                L["legend"].append('<rect id="%s-glyph" x="%s" y="%s" width="30" height="%.1f" fill="%s" stroke="#555555"/>' % (i, x, y, 13 * TF, it["fill"]))
            L["legend"].append(txt(i, x + 44, y + 11 * TF, [it["label"]], fl, {}, it.get("src", "legend"), "start"))
            cm["legend"].append(it)
        nc_ = (max(slots) // per + 1) if slots else 1
        lb = (lg["x"] - 4, lg["y"] - 4, lg["x"] + (nc_ - 1) * colw + colw - 26, y0 + min(per, max(slots or [0]) + 1) * rh_ + 2)
        warn += ["edge %s crosses the legend box: re-route it (via) or move the legend" % e for e in sorted({s[0] for s in segs if any(inside(s[1] + (s[3] - s[1]) * f / 30.0, s[2] + (s[4] - s[2]) * f / 30.0, lb) for f in range(31))})]
        warn += ["node %s overlaps the legend box" % k for k, n in N.items() if n["cx"] + n["w"] / 2.0 > lb[0] and n["cx"] - n["w"] / 2.0 < lb[2] and n["cy"] + n["h"] / 2.0 > lb[1] and n["cy"] - n["h"] / 2.0 < lb[3]]
        bot, rgt = max(bot, lb[3]), max(rgt, lb[2])
    elif sp.get("edges"):
        warn.append("no legend: add legend{} (placed below the figure; items are auto-filled from the edge types, evidence styles and colour scale used)")
    for t in sp.get("texts", []):
        fs = float(t.get("fs", 14)) * TF
        FS.append(fs)
        if "x" not in t or "y" not in t:  # footnote: below figure and legend, wrapped to the canvas width
            t.setdefault("w", max(W, rgt + M_) - 2 * M_)
            t["x"], t["y"] = M_, bot + 12 + fs
        lines = wrap(t["text"], t["w"], fs, t.get("bold")) if t.get("w") else str(t["text"]).split("\n")
        L["text"].append(txt(t["id"], t["x"], t["y"], lines, fs, t, src(t, "text"), t.get("anchor", "start")))
        bot = max(bot, t["y"] + (len(lines) - 1) * fs * 1.2 + 5)
        rgt = max(rgt, t["x"] + (max(tw(l, fs) for l in lines) if t.get("anchor", "start") == "start" else 0))
    W0, H0 = W, H
    W, H = int(max(W, rgt + M_)), int(max(H if "h" in cv else 0, bot + M_))
    if W > W0 + 1 and "w" in cv or H > H0 + 1 and "h" in cv:
        warn.append("NOTE canvas grown from %sx%s to %sx%s so nothing is clipped (no action needed)" % (W0, H0, W, H))
    if cv.get("title"):
        L["text"].append(txt("figure-title", W / 2.0, 34 * TF, [cv["title"]], cv.get("title_fs", 22) * TF, {"bold": 1}, cv.get("src", ""), "middle"))
    wa, ha = ("%smm" % cv["width_mm"], "%.2fmm" % (cv["width_mm"] * H / float(W))) if cv.get("width_mm") else (W, H)  # physical size for journals
    body = "\n".join('<g id="layer-%s">\n%s\n</g>' % (k, "\n".join(v)) for k, v in L.items())
    open(out, "w", encoding="utf-8").write('<?xml version="1.0" encoding="UTF-8"?>\n<svg xmlns="http://www.w3.org/2000/svg" width="%s" height="%s" viewBox="0 0 %s %s" font-family="%s">\n<title>%s</title>\n<rect id="background" width="100%%" height="100%%" fill="#FFFFFF"/>\n%s\n</svg>\n' % (
        wa, ha, W, H, q(cv.get("font", FONT)), escape(cv.get("title", "figure")), body))
    cm["spec"], cm["spec_sha256_16"] = a[0], hashlib.sha256(open(a[0], "rb").read()).hexdigest()[:16]
    cmp_ = os.path.splitext(out)[0] + "_content_map.json"
    pt = ("; canvas %dx%d px = %s mm wide, smallest text %.1f px = %.1f pt" % (W, H, cv["width_mm"], min(FS), min(FS) * cv["width_mm"] / float(W) / 0.3528)
          if cv.get("width_mm") else "; canvas %dx%d px, smallest text %.1f px (set canvas.width_mm to get pt)" % (W, H, min(FS)))
    if TF > 1.01:
        pt += "; all text scaled x%.2f to meet min_font_pt %s" % (TF, cv.get("min_font_pt", 6.5))
        warn += ["figure is dense for %s mm: text scaled x%.2f; consider fewer nodes per row or splitting a sub-figure" % (cv.get("width_mm"), TF)] if TF > 1.45 else []
    if cv.get("width_mm") and cv["width_mm"] * H / float(W) > 235:
        warn.append("figure is %d mm tall at %s mm width (a journal page holds about 230 mm): use fewer rows per compartment (more nodes per row), shorten labels, or split into two figures; otherwise record it as an exception" % (cv["width_mm"] * H / float(W), cv["width_mm"]))
    cm["export_geometry"] = {"canvas_px": [W, H], "width_mm": cv.get("width_mm"), "height_mm": round(cv["width_mm"] * H / float(W), 1) if cv.get("width_mm") else None, "min_font_px": round(min(FS), 2), "text_scale": round(TF, 3),
                             "min_font_pt": round(min(FS) * cv["width_mm"] / float(W) / 0.3528, 2) if cv.get("width_mm") else None}
    json.dump(cm, open(cmp_, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if not emit:
        return W, min(FS), H
    print("\n".join([("NOTE: " + w[5:]) if w.startswith("NOTE ") else "WARN: " + w for w in warn] or ["no warnings"]) + "\nwrote %s and %s (%d entities, %d relations, %d legend items%s)" % (
        out, cmp_, len(cm["entities"]), len(cm["relations"]), len(cm["legend"]), pt))
    return W, min(FS), None

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
    return {el.get("id"): (el.tag.split("}")[-1], " ".join(" ".join(el.itertext()).split()) if el.tag.endswith("text") else "",  # line wrapping is layout, not content
                           {k: v for k, v in el.attrib.items() if k != "id"}) for el in ET.parse(path).getroot().iter() if el.get("id")}

def diff(a):
    o, n = index(a[0]), index(a[1])
    ch = [{"id": k, "change": "removed", "before": o[k][1] or o[k][0]} for k in o if k not in n]
    ch += [{"id": k, "change": "added", "after": n[k][1] or n[k][0]} for k in n if k not in o]
    for k in (k for k in o if k in n and o[k] != n[k]):
        ch += [{"id": k, "change": "text", "before": o[k][1], "after": n[k][1]}] if o[k][1] != n[k][1] else []
        ch += [{"id": k, "change": at, "before": o[k][2].get(at), "after": n[k][2].get(at)} for at in sorted(set(o[k][2]) | set(n[k][2])) if o[k][2].get(at) != n[k][2].get(at)]
    geo = {"x", "y", "cx", "cy", "width", "height", "rx", "ry", "points", "x1", "x2", "y1", "y2", "font-size", "text-anchor", "stroke-width"}
    content = [c for c in ch if c["change"] not in geo]
    print(json.dumps({"old": a[0], "new": a[1], "kept_ids": len(set(o) & set(n)), "unchanged_ids": len(set(o) & set(n)) - len({c["id"] for c in ch}),
                      "content_changes": len(content), "layout_only_changes": len(ch) - len(content),
                      "changed_ids": sorted({c["id"] for c in content}), "changes": content + [c for c in ch if c["change"] in geo]}, ensure_ascii=False, indent=1))

CMDS = {"build": build, "edit": edit, "diff": diff}
if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] not in CMDS:
        print(__doc__)
        sys.exit(2)
    sys.exit(CMDS[sys.argv[1]](sys.argv[2:]) or 0)
