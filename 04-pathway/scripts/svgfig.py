#!/usr/bin/env python3
"""svgfig (stdlib, py3.8+): layered, editable pathway/mechanism SVG from a JSON spec, plus source-level edits.
  build spec.json out.svg   -> SVG (layers, ids, data-src) + out_content_map.json (entities/relations/legend/data, src)
                               auto layout (no cx/cy, or canvas.layout "auto") also writes out_resolved_spec.json
  edit in.svg out.svg ID [--text "new label"] [--set attr=value ...]   change one element, rest byte-identical
  diff old.svg new.svg      -> element-level change log (proof the edit kept the source)
Spec: canvas{w,h,width_mm,min_font_pt,fs_scale,layout,title,src,colorscale{csv,key,value,breaks[],colors[],title,src}},
panels[{id,title,in,membrane,fill,src (+x,y,w,h when not auto)}] listed top -> bottom, nodes[{id,label,kind,comp,data,mods,
shape,fill,fs,bold,aliases,xref,rank,col,src (+cx,cy,w,h when not auto)}], edges[{id,from,to,type,evidence,label,feedback,
via[[x,y]],elbow,width,both,src}], texts[{id,text,x,y,fs,w,src}], legend{x,y,title,items[{edge|fill|evidence,label}]}.
Auto layout: panels stacked in the order given (panel "in": parent -> organelle box inside it; membranes/envelopes are thin
bilayer bands, nodes on them span the band); rows inside a panel follow the causal order of the edges (feedback edges found
automatically or marked "feedback": true); columns ordered to straighten chains; blocked/upward edges routed orthogonally
through empty lanes between rows and columns; fonts scaled so the smallest text >= canvas.min_font_pt at width_mm.
kind: gene mrna protein complex family small_molecule ion cell process (sets the glyph; gene/mrna italic).
type: activate inhibit bind modify transport indirect line (+ flow signal step).  evidence: direct|indirect|hypothesis.
mods: ["P","Ub","Ac","Me"] -> state badges on the node."""
import copy, csv, hashlib, json, os, re, sys
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
KSHAPE = {"protein": "round", "complex": "octagon", "family": "stack", "gene": "gene", "mrna": "mrna", "small_molecule": "ellipse",
          "ion": "circle", "cell": "ellipse"}
KLAB = {"gene": "gene (italic; bent arrow = promoter)", "mrna": "mRNA (italic)", "protein": "protein", "complex": "protein complex",
        "family": "protein family", "small_molecule": "small molecule", "ion": "ion", "cell": "cell", "process": "process"}
MODS = {"P": "phosphorylated", "UB": "ubiquitinated", "AC": "acetylated", "ME": "methylated"}
FONT = "Arial, Helvetica, 'Noto Sans CJK SC', 'Source Han Sans SC', 'WenQuanYi Micro Hei', 'PingFang SC', 'Microsoft YaHei', sans-serif"
FSUSED = []
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
    FSUSED.append(fs)
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

def shape(sh, x, y, w, h, base, cx, cy):
    """Node glyph; the main element keeps the node id (rect / ellipse / polygon) so edits and pixel checks find it."""
    if sh in ("ellipse", "circle"):
        return ['<ellipse %s cx="%s" cy="%s" rx="%s" ry="%s"/>' % (base, cx, cy, w / 2.0, h / 2.0)]
    if sh == "diamond":
        return ['<polygon %s points="%s,%s %s,%s %s,%s %s,%s"/>' % (base, cx, y, x + w, cy, cx, y + h, x, cy)]
    if sh == "octagon":
        c = min(9.0, h / 4.0)
        return ['<polygon %s points="%s"/>' % (base, " ".join("%.1f,%.1f" % p for p in (
            (x + c, y), (x + w - c, y), (x + w, y + c), (x + w, y + h - c), (x + w - c, y + h), (x + c, y + h), (x, y + h - c), (x, y + c))))]
    out = []
    if sh == "stack":
        out.append('<rect x="%.1f" y="%.1f" width="%s" height="%s" rx="4" fill="#FFFFFF" stroke="#333333" stroke-width="1.2"/>' % (x + 5, y - 5, w, h))
    out.append('<rect %s x="%s" y="%s" width="%s" height="%s" rx="%s"/>' % (base, x, y, w, h, {"round": 12, "band": 0, "gene": 0, "mrna": 0}.get(sh, 4)))
    if sh == "gene":  # promoter: bent arrow above the left end, pointing along the gene
        out.append('<path d="M%.1f,%.1f v-9 h12" fill="none" stroke="#333333" stroke-width="1.5"/><path d="M%.1f,%.1f l6,3.5 l-6,3.5 z" fill="#333333"/>' % (
            x + 10, y, x + 21, y - 12.5))
    return out

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

def thin(p):
    t = str(p.get("title", "")).lower()
    return bool(p.get("membrane")) or ("h" in p and p["h"] < 44 and not p.get("auto")) or "membrane" in t or "envelope" in t or "膜" in t

def legend_est(sp, F):
    """Rough legend size before build: (number of rows, widest label px)."""
    ed = sp.get("edges", [])
    labs = [ELAB.get(t, t) for t in {e.get("type", "step") for e in ed}] + [v + " evidence" for v in {e.get("evidence") for e in ed} if v in EVID]
    labs += ["Entities"] + [KLAB.get(k, k) for k in {n.get("kind") for n in sp.get("nodes", []) if n.get("kind")}]
    labs += [MODS.get(str(m).upper(), m) for m in {m for n in sp.get("nodes", []) for m in (n.get("mods") or [])}]
    sc = sp["canvas"].get("colorscale")
    if sc:
        labs += [sc.get("title", sc.get("value", ""))] + ["x to < y"] * (len(sc.get("breaks", [])) + 1) + ["no value in " + os.path.basename(str(sc.get("csv", "")))]
    labs += [it.get("label", "") for it in (sp.get("legend") or {}).get("items", [])]
    return len(labs) + 2, max([tw(str(l), 12 * F) for l in labs] + [60])

def layout(sp, F, where="right"):
    """Compartment-constrained layered layout. Fills panel x/y/w/h, node cx/cy/w/h/fs, edge via, legend x/y, canvas w/h."""
    cv, nodes, edges = sp["canvas"], sp.get("nodes", []), sp.get("edges", [])
    cv["fs_scale"] = round(F, 3)
    panels = sp.setdefault("panels", [])
    PI = {p["id"]: p for p in panels}
    N = {n["id"]: n for n in nodes}
    ids = [n["id"] for n in nodes]
    E = [e for e in edges if isinstance(e.get("from"), str) and isinstance(e.get("to"), str) and e["from"] in N and e["to"] in N and e["from"] != e["to"]]
    out, pred = {i: [] for i in ids}, {i: set() for i in ids}
    for e in E:
        if not e.get("feedback"):
            out[e["from"]].append(e["to"])
            pred[e["to"]].add(e["from"])
    state, back = {}, set()
    def dfs(u):
        state[u] = 1
        for v in out[u]:
            if state.get(v) == 1:
                back.add((u, v))
            elif not state.get(v):
                dfs(v)
        state[u] = 2
    sys.setrecursionlimit(5000)
    for i in sorted(ids, key=lambda i: (len(pred[i]) > 0, ids.index(i))):
        if not state.get(i):
            dfs(i)
    dag = {i: [v for v in out[i] if (i, v) not in back] for i in ids}
    indeg = {i: 0 for i in ids}
    for i in ids:
        for v in dag[i]:
            indeg[v] += 1
    order, st, rank, deg = [], [i for i in ids if not indeg[i]], {i: 0 for i in ids}, dict(indeg)
    top_of = lambda i: (PI.get(N[i].get("comp")) or {}).get("in") or N[i].get("comp")  # noqa: E731
    while st:  # rows count causal steps inside each compartment; input from another compartment starts at its top
        u = st.pop(0)
        order.append(u)
        for v in dag[u]:
            if top_of(u) == top_of(v):
                rank[v] = max(rank[v], rank[u] + 1)
            deg[v] -= 1
            if not deg[v]:
                st.append(v)
    tix = {p["id"]: k for k, p in enumerate(panels) if not p.get("in")}
    below = [u for u in ids if pred[u] and all(tix.get(top_of(w), -1) > tix.get(top_of(u), 99) for w in pred[u])]
    if below:  # made in a compartment further down (e.g. feedback protein from a nuclear gene): bottom of its own compartment
        der, stk = set(below), list(below)
        while stk:
            u = stk.pop()
            for v in dag[u]:
                if top_of(v) == top_of(u) and v not in der:
                    der.add(v)
                    stk.append(v)
        base = {u: 0 for u in ids}
        for u in below:
            base[u] = 1 + max([rank[w] for w in ids if top_of(w) == top_of(u) and w not in der] + [-1])
        rank = dict(base)
        for u in order:
            for v in dag[u]:
                if top_of(u) == top_of(v):
                    rank[v] = max(rank[v], rank[u] + 1)
    for u in reversed(order):  # pure sources sit next to (binding partner) or just above their first target
        if not indeg[u] and [v for v in dag[u] if top_of(v) == top_of(u)]:
            v = min([v for v in dag[u] if top_of(v) == top_of(u)], key=lambda v: rank[v])
            side = all(e["type"] == "bind" for e in E if e["from"] == u) and top_of(u) == top_of(v) and len(pred[v]) > 1
            rank[u] = rank[v] if side else max(0, rank[v] - 1)
    for n in nodes:
        rank[n["id"]] = n.get("rank", rank[n["id"]])
    tops = [p for p in panels if not p.get("in") or p["in"] not in PI]
    def home(n):
        p = PI.get(n.get("comp"))
        if not p:
            return "_free", None
        return (p["in"], p["id"]) if p.get("in") in PI else (p["id"], None)
    if any(home(n)[0] == "_free" for n in nodes):
        tops.append({"id": "_free", "title": ""})
    for n in nodes:  # sizes
        fs = n["fs"] = n.get("fs0", n.get("fs", round(14 * F, 1)))
        sh = n.setdefault("shape", KSHAPE.get(n.get("kind", ""), "rect"))
        if "w0" in n or "w" not in n:
            w = max(tw(l, fs, n.get("bold")) for l in str(n.get("label", "")).split("\n")) + 26 * F
            n["w"] = round(min(max(w * (1.3 if sh in ("ellipse", "circle") else 1), 84 * F), 210 * F), 1)
        if "h0" in n or "h" not in n:
            n["h"] = round(max(len(wrap(n.get("label", ""), n["w"] - 12, fs)) * fs * 1.25 + 16 * F, 40 * F), 1)
            if PI.get(n.get("comp")) and thin(PI[n["comp"]]):
                n["h"] = round(max(n["h"], 52 * F), 1)
    rows = []  # each: {"ids", "top", "sub", "thin"}
    for p in tops:
        mem = [n for n in nodes if home(n)[0] == p["id"]]
        if p["id"] != "_free" and thin(p):
            rows.append({"ids": [n["id"] for n in mem], "top": p["id"], "sub": None, "thin": True})
            continue
        plain = [n for n in mem if home(n)[1] is None]
        blocks = [(r, 0, [[n["id"] for n in plain if rank[n["id"]] == r]], None, False) for r in sorted({rank[n["id"]] for n in plain})]
        for s in [s for s in panels if s.get("in") == p["id"]]:
            m = [n for n in mem if n.get("comp") == s["id"]]
            if m:
                rs = sorted({rank[n["id"]] for n in m})
                blocks.append((rs[0], 1, [[n["id"] for n in m]] if thin(s) else [[n["id"] for n in m if rank[n["id"]] == r] for r in rs], s["id"], thin(s)))
        blocks.sort(key=lambda b: (b[0], b[1]))
        if not blocks:
            rows.append({"ids": [], "top": p["id"], "sub": None, "thin": False})
        for b in blocks:
            for k, r in enumerate(b[2]):
                rows.append({"ids": r, "top": p["id"], "sub": b[3], "thin": b[4], "first": k == 0, "last": k == len(b[2]) - 1})
    slot, nb = {}, {i: [] for i in ids}
    for e in E:
        nb[e["from"]].append(e["to"])
        nb[e["to"]].append(e["from"])
    for r in rows:
        for k, i in enumerate(r["ids"]):
            slot[i] = N[i].get("col", k)
    rowof = {i: k for k, r in enumerate(rows) for i in r["ids"]}
    for it in range(12):
        for r in (rows if it % 2 == 0 else rows[::-1]):
            if not r["ids"]:
                continue
            rs, des = set(r["ids"]), {}
            for i in r["ids"]:
                xs = [slot[j] for j in nb[i] if j not in rs and abs(rowof[j] - rowof[i]) <= (1 if it < 6 else 99)] or [slot[j] for j in nb[i] if j not in rs]
                des[i] = N[i]["col"] if "col" in N[i] else (sum(xs) / float(len(xs)) if xs else slot[i])
            seq = sorted(r["ids"], key=lambda i: (des[i], slot[i]))
            for i, v in zip(seq, pav([des[i] - k for k, i in enumerate(seq)])):  # closest strictly increasing slots
                slot[i] = v
            slot[seq[0]] = int(round(slot[seq[0]]))
            for k in range(1, len(seq)):
                slot[seq[k]] = max(int(round(slot[seq[k]] + k)), slot[seq[k - 1]] + 1)
    lo, hi = min(slot.values() or [0]), max(slot.values() or [0])
    for e in E:  # keep straight vertical chains free: nudge a node that sits between the two ends into a free slot
        r1, r2, c = rowof[e["from"]], rowof[e["to"]], slot[e["from"]]
        if slot[e["to"]] == c and r2 > r1 + 1:
            for k in range(r1 + 1, r2):
                taken = {slot[j] for j in rows[k]["ids"]}
                for i in [j for j in rows[k]["ids"] if slot[j] == c and "col" not in N[j]]:
                    free = [c + d for d in (1, -1, 2, -2) if c + d not in taken and lo <= c + d <= hi]
                    if free:
                        slot[i] = free[0]
                        taken = {slot[j] for j in rows[k]["ids"]}
    m0 = min(slot.values()) if slot else 0
    for i in slot:
        slot[i] -= m0
    ncol = max(slot.values()) + 1 if slot else 1
    dx = max([n["w"] for n in nodes] + [84 * F]) + 44
    titled = [p for p in panels if p.get("title")]
    reserve = max([tw(p["title"], 12.5 * F, True) + 26 for p in titled if thin(p) and not p.get("in")] + [24])
    X0, PX = 20 + reserve, 20
    y = (40 + 22 * F if cv.get("title") else 16)
    gut, info = {}, {}
    for k, r in enumerate(rows):
        p = PI.get(r["top"], {"id": "_free"})
        mh = max([N[i]["h"] for i in r["ids"]] + [40 * F])
        if k == 0 or rows[k - 1]["top"] != r["top"]:  # new top-level panel
            if k:
                y += 14
            p["_y"] = y
            if not r["thin"] and p.get("title"):
                y += 20 + 16 * F
        if r["thin"] and not r["sub"]:
            bh = 38 * F
            cy = y + bh / 2.0
            p["_band"] = bh
            y += bh
            gut[k] = (cy - mh / 2.0 - 8, cy + mh / 2.0 + 8)
        else:
            if r["sub"] and r.get("first"):
                y += 10 if r["thin"] else 14 + 16 * F
                PI[r["sub"]]["_y"] = y - (0 if r["thin"] else 6 + 16 * F)
            pad = 28
            cy = y + pad + mh / 2.0
            gut[k] = (cy - mh / 2.0 - 12, cy + mh / 2.0 + 12)
            y = cy + mh / 2.0 + pad
            if r["sub"] and r.get("last"):
                PI[r["sub"]]["_y2"] = y - pad + (10 if r["thin"] else 14)
                y += 6
        for i in r["ids"]:
            N[i]["cx"], N[i]["cy"] = round(X0 + slot[i] * dx + dx / 2.0, 1), round(cy, 1)
            info[i] = (k, slot[i])
        if k == len(rows) - 1 or rows[k + 1]["top"] != r["top"]:
            p["_y2"] = y + (0 if r["thin"] and not r["sub"] else 4)
    gx = lambda g: X0 + g * dx  # noqa: E731  lane g = left boundary of column g
    used = {}
    def off(key, step):
        n = used.get(key, 0)
        used[key] = n + 1
        return step * ((n + 1) // 2) * (1 if n % 2 else -1)
    def blocked(a, b):
        x1, y1, x2, y2 = a["cx"], a["cy"], b["cx"], b["cy"]
        return any(n is not a and n is not b and any(abs(x1 + (x2 - x1) * f / 24.0 - n["cx"]) < n["w"] / 2.0 + 4 and
                                                     abs(y1 + (y2 - y1) * f / 24.0 - n["cy"]) < n["h"] / 2.0 + 4 for f in range(1, 24)) for n in nodes)
    seen, side = set(), {}
    for e in E:
        a, b = N[e["from"]], N[e["to"]]
        (r1, c1), (r2, c2) = info[a["id"]], info[b["id"]]
        pair = frozenset((a["id"], b["id"]))
        dup = pair in seen
        seen.add(pair)
        e.pop("via", None), e.pop("elbow", None)
        near = r2 == r1 + 1 or (r2 > r1 and c1 == c2) or (r1 == r2 and abs(c1 - c2) == 1) or (r2 == r1 - 1 and c1 == c2)
        if not dup and near and not blocked(a, b):
            continue
        if dup and near and (r1 == r2 or c1 == c2):  # second relation between the same pair: a parallel offset line
            o = 10
            if r1 == r2:
                sx = 1 if b["cx"] > a["cx"] else -1
                e["via"] = [[a["cx"] + sx * (a["w"] / 2.0 + 3), a["cy"] + o], [b["cx"] - sx * (b["w"] / 2.0 + 3), b["cy"] + o]]
            else:
                sy = 1 if b["cy"] > a["cy"] else -1
                e["via"] = [[a["cx"] + o, a["cy"] + sy * (a["h"] / 2.0 + 3)], [b["cx"] + o, b["cy"] - sy * (b["h"] / 2.0 + 3)]]
        elif r1 == r2:
            gy = gut[r1][1 if dup else 0] + off(("g", r1, dup), 5)
            e["via"] = [[a["cx"], gy], [b["cx"], gy]]
        elif r2 > r1:
            g = c1 + 1 if c1 == c2 else (c2 if c2 > c1 else c2 + 1)
            lx = gx(g) + off(("l", g), 7)
            y1, y2 = gut[r1][1] + off(("g", r1, 1), 5), gut[r2][0] + off(("g", r2, 0), 5)
            e["via"] = [[a["cx"], y1], [lx, y1], [lx, y2], [b["cx"], y2]]
        else:  # upward / feedback: leave from the top, climb in the outer lane on the nearer side, enter from below
            g = 0 if (c1 + c2) / 2.0 < (ncol - 1) / 2.0 else ncol
            side[g] = side.get(g, 0) + 1
            lx = gx(g) + (1 if g else -1) * (8 + 9 * (side[g] - 1))
            y1, y2 = gut[r1][0] + off(("g", r1, 0), 5), gut[r2][1] + off(("g", r2, 1), 5)
            e["via"] = [[a["cx"], y1], [lx, y1], [lx, y2], [b["cx"], y2]]
        e["via"] = [[round(u, 1), round(v, 1)] for u, v in e["via"]]
    right = gx(ncol) + 18 + 9 * side.get(ncol, 0)
    if where != "right":  # legend below: panels span the full width under the title
        right = max(right, tw(cv.get("title", ""), 20 * F, True) + 34)
    for p in panels:
        if p.get("in") in PI and p.get("_y") is not None:
            m = [N[i] for i in N if N[i].get("comp") == p["id"]]
            x1, x2 = min(n["cx"] - n["w"] / 2.0 for n in m) - 16, max(n["cx"] + n["w"] / 2.0 for n in m) + 16
            if thin(p):
                p.update(x=round(x1, 1), y=round(m[0]["cy"] - 17 * F, 1), w=round(x2 - x1 + tw(p.get("title", ""), 12.5 * F, True) + 20, 1), h=round(34 * F, 1), title_right=True)
            else:
                p.update(x=round(x1, 1), y=round(p["_y"], 1), w=round(x2 - x1, 1), h=round(p["_y2"] - p["_y"], 1))
        elif p.get("_y") is not None:
            p.update(x=PX, y=round(p["_y"], 1), w=round(right - PX, 1), h=round((p["_band"] if p.get("_band") else p["_y2"] - p["_y"]), 1))
        elif "x" not in p:
            p.update(x=PX, y=round(y, 1), w=round(right - PX, 1), h=40)
        for k in ("_y", "_y2", "_band"):
            p.pop(k, None)
        p["auto"] = True
    panels[:] = [p for p in panels if p["id"] != "_free" and not (p.get("in") in PI and not any(n.get("comp") == p["id"] for n in nodes))]  # empty organelle box: dropped
    bottom = y + 6
    for t in sp.get("texts", []):
        if "x" not in t or "y" not in t:
            t.update(x=PX, y=round(bottom + 14 * F, 1), w=t.get("w", right - PX), fs=t.get("fs", round(12 * F, 1)))
            bottom += 14 * F + (len(wrap(t["text"], t["w"], t["fs"])) - 1) * t["fs"] * 1.2 + 6
    lg = sp.setdefault("legend", {"title": "Legend"})
    lg["glyphs"] = True
    nrow, lw = legend_est(sp, F)
    colw = 44 * F + lw + 26
    if where == "right":
        lg.update(x=round(right + 22, 1), y=round(y0_top(cv, F), 1))
        cv["w"], cv["h"] = round(right + 22 + colw), round(max(bottom + 10, lg["y"] + nrow * 20 * F + 20))
    else:
        ncl = max(1, int((max(right - PX, tw(cv.get("title", ""), 20 * F, True) + 20)) // colw))
        per = -(-nrow // ncl)
        lg.update(x=PX + 4, y=round(bottom + 12, 1), cols=ncl, colw=round(colw, 1), maxh=round(per * 20 * F + 30, 1))
        cv["w"], cv["h"] = round(max(right + 6, PX + ncl * colw)), round(bottom + 12 + 22 * F + per * 20 * F + 30)
    cv["w"] = max(cv["w"], int(tw(cv.get("title", ""), 20 * F, True) + 40))
    cv["autosize"] = True
    return cv["w"]

def pav(v):
    """Isotonic (non-decreasing) least-squares fit, pool-adjacent-violators."""
    bl = []
    for x in v:
        bl.append([x, 1])
        while len(bl) > 1 and bl[-2][0] > bl[-1][0]:
            a, b = bl.pop(), bl.pop()
            bl.append([(a[0] * a[1] + b[0] * b[1]) / float(a[1] + b[1]), a[1] + b[1]])
    return [m for m, c in bl for _ in range(c)]

def y0_top(cv, F):
    return 40 + 22 * F if cv.get("title") else 16

def build(a):
    sp, out = json.load(open(a[0], encoding="utf-8")), a[1]
    cv, warn, marks, N, P = sp.setdefault("canvas", {}), [], {}, {}, {}
    del FSUSED[:]
    auto = cv.get("layout") == "auto" or (not cv.get("grid") and bool(sp.get("nodes")) and any("cx" not in n and "col" not in n for n in sp["nodes"]))
    if auto:
        F0, mm, mp = float(cv.get("fs_scale", 1)), cv.get("width_mm"), cv.get("min_font_pt")
        tries = [(F0 + 0.1 * k, wh) for k in range(13) for wh in ((cv.get("legend_at"),) if cv.get("legend_at") else ("right", "bottom"))]
        for F, wh in tries:  # smallest font scale (legend right first, then below) that keeps every text >= min_font_pt at width_mm
            s2 = copy.deepcopy(sp)
            Wl = layout(s2, F, wh)
            if not (mm and mp) or 12.0 * F * float(mm) * 3.78 / Wl * 0.75 >= float(mp) * 1.04:
                break
        sp, cv = s2, s2["canvas"]
        res = copy.deepcopy(sp)
        res["canvas"]["layout"] = "fixed"
        rpath = os.path.splitext(out)[0] + "_resolved_spec.json"
        json.dump(res, open(rpath, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    S = float(cv.get("fs_scale", 1))
    W, H, g = cv.get("w", 1200), cv.get("h", 800), cv.get("grid", {})
    L = {k: [] for k in ("panels", "edges", "nodes", "data", "text", "legend")}
    cm = {"entities": [], "relations": [], "compartments": [], "legend": [], "data_encoding": None, "warnings": warn}
    def src(o, kind):
        warn.extend([] if o.get("src") else ["no src for %s %s" % (kind, o.get("id"))])
        return o.get("src", "")
    def mk(head, col):
        k = "m-%s-%s" % (head, col.strip("#"))
        marks[k] = '<marker id="%s" viewBox="-1 -1 13 13" refX="%d" refY="5" markerWidth="%.1f" markerHeight="%.1f" markerUnits="userSpaceOnUse" orient="auto-start-reverse">%s</marker>' % (
            k, REF[head], 12 * S, 12 * S, HEAD[head] % col)
        return k
    for p in sp.get("panels", []):
        s, th = src(p, "panel"), thin(p) if p.get("auto") else p["h"] < 44
        P[p["id"]] = (p["x"], p["y"], p["x"] + p["w"], p["y"] + p["h"])
        cm["compartments"].append({"id": p["id"], "title": p.get("title", ""), "inside": p.get("in", ""), "membrane": th, "src": s})
        L["panels"].append('<rect id="%s" x="%s" y="%s" width="%s" height="%s" rx="%s" fill="%s" stroke="%s" stroke-width="1.2" data-src="%s"/>' % (
            p["id"], p["x"], p["y"], p["w"], p["h"], 3 if th else 8, p.get("fill", "#F2D7B6" if th else "#EEF3F8" if p.get("in") else "#F7F7F7"), p.get("stroke", "#BBBBBB"), q(s)))
        if th:  # lipid bilayer: two rows of head groups
            k = int(p["w"] // 9)
            L["panels"].append('<g id="%s-bilayer">%s</g>' % (p["id"], "".join('<circle cx="%.1f" cy="%.1f" r="2.8" fill="#C8996A"/>' % (p["x"] + 5 + 9 * j, yy)
                                                                                for j in range(k) for yy in (p["y"] + 4, p["y"] + p["h"] - 4))))
        elif re.search(r"nucle(us|ar)|核", str(p.get("title", "")).lower()) or p.get("envelope"):  # double nuclear envelope
            L["panels"].append('<rect id="%s-envelope" x="%s" y="%s" width="%s" height="%s" rx="6" fill="none" stroke="%s" stroke-width="1"/>' % (
                p["id"], p["x"] + 5, p["y"] + 5, p["w"] - 10, p["h"] - 10, p.get("stroke", "#BBBBBB")))
        if p.get("title"):
            tfs = p.get("fs", (12.5 if th else 15 if p.get("in") else 17) * S)
            if th and p.get("title_right"):
                L["text"].append(txt(p["id"] + "-title", p["x"] + p["w"] - 10, p["y"] + p["h"] / 2.0 + tfs * 0.36, [p["title"]], tfs, {"bold": 1}, s, "end"))
            else:
                L["text"].append(txt(p["id"] + "-title", p["x"] + 10, p["y"] + (p["h"] / 2.0 + tfs * 0.36 if th else 24 * S), [p["title"]], tfs, {"bold": 1}, s, "start"))
        else:
            warn.append("panel %s has no title: every compartment/membrane must be named on the figure" % p["id"])
    sc = cv.get("colorscale")
    rows, br, cols, labs, enc = colorscale(sc, os.path.dirname(os.path.abspath(a[0])), warn) if sc else ([], [], [], [], None)
    cm["data_encoding"], nodata, kinds, mods = enc and dict(enc, nodes=[]), False, [], []
    warn += ["colour bin %r (%s) looks like the white used for 'no value': use a visible grey such as #CCCCCC" % (l, c) for l, c in zip(labs, cols)
             if len(c) == 7 and min(int(c[k:k + 2], 16) for k in (1, 3, 5)) > 238]
    for n in sp.get("nodes", []):
        n.setdefault("w", 150), n.setdefault("h", 54)
        if "col" in n and "cx" not in n:
            n["cx"], n["cy"] = g.get("x0", 120) + n["col"] * g.get("dx", 200), g.get("y0", 120) + n["row"] * g.get("dy", 110)
        N[n["id"]], s, kd = n, src(n, "node"), n.get("kind", "")
        sh = n.setdefault("shape", KSHAPE.get(kd, "rect"))
        n.setdefault("italic", kd in ("gene", "mrna"))
        kinds += [kd] if kd and kd not in kinds else []
        if kd in ("protein", "complex", "family") and n["italic"] or kd in ("gene", "mrna") and not n["italic"]:
            warn.append("node %s: kind %s but italic=%s (genes/mRNA italic, proteins upright)" % (n["id"], kd, n["italic"]))
        if not kd:
            warn.append("node %s has no kind (gene/mrna/protein/complex/family/small_molecule/cell/process)" % n["id"])
        if n.get("comp") and n["comp"] not in P:
            warn.append("node %s: comp %s is not a panel id" % (n["id"], n["comp"]))
        elif n.get("comp") and not inside(n["cx"], n["cy"], P[n["comp"]], -1):
            warn.append("node %s centre (%s,%s) is outside its compartment %s" % (n["id"], n["cx"], n["cy"], n["comp"]))
        dv, nod = None, False
        if sc and n.get("data") is not None:
            r = next((r for r in rows if r.get(sc.get("key", "")) == n["data"]), None) or next((r for r in rows if n["data"] in r.values()), None)
            try:
                dv = float(r[sc["value"]])
                k = sum(dv >= b for b in br)
                n["fill"] = cols[k]
                cm["data_encoding"]["nodes"].append({"node": n["id"], "key": n["data"], "value": dv, "bin": labs[k], "color": cols[k]})
            except (TypeError, KeyError, ValueError):
                warn.append("node %s: data key %r has no numeric %s in %s" % (n["id"], n["data"], sc["value"], sc["csv"]))
                nod = True
        elif sc and kd not in ("small_molecule", "ion", "process", "cell", "") and "fill" not in n:
            nod = True
        nodata = nodata or nod
        x, y, w, h = n["cx"] - n["w"] / 2.0, n["cy"] - n["h"] / 2.0, n["w"], n["h"]
        fill = n.get("fill", "#FFFFFF")
        base = 'id="%s" fill="%s" stroke="%s" stroke-width="1.5" data-src="%s"' % (n["id"], fill, n.get("stroke", "#333333"), q(s))
        L["nodes"] += shape(sh, x, y, w, h, base, n["cx"], n["cy"])
        fs, pad = float(n.get("fs", 14 * S)), (0.72 if sh in ("ellipse", "circle", "diamond") else 1.0)
        lines = wrap(n.get("label", ""), w * pad - 12, fs, n.get("bold"))
        while fs > 9 * S and (len(lines) * fs * 1.2 > h * pad - 4 or max(tw(l, fs) for l in lines) > w * pad - 8):
            fs -= 0.5
            lines = wrap(n.get("label", ""), w * pad - 12, fs, n.get("bold"))
        if len(lines) * fs * 1.2 > h * pad + 2 or max(tw(l, fs) for l in lines) > w * pad:
            warn.append("label overflows node %s even at %.0fpx: enlarge w/h or shorten the label" % (n["id"], 9 * S))
        o = dict(n, color=n.get("color", "#FFFFFF" if lum(fill) < 0.18 else "#111111"))
        L["nodes"].append(txt(n["id"] + "-label", n["cx"], n["cy"] - (len(lines) - 1) * fs * 0.6 + fs * 0.35, lines, fs, o, s))
        for j, md in enumerate(n.get("mods") or []):
            bx, by = x + w - 4 * S - j * 24 * S, y + 1
            L["nodes"].append('<circle id="%s-mod-%s" cx="%.1f" cy="%.1f" r="%.1f" fill="#FFFFFF" stroke="#7B3294" stroke-width="1.4"/>' % (n["id"], re.sub(r"\W", "", md), bx, by, 11 * S))
            L["nodes"].append(txt("%s-mod-%s-label" % (n["id"], re.sub(r"\W", "", md)), bx, by + 4.3 * S, [md], 12 * S, {"bold": 1}, s, "middle", "#7B3294"))
            mods += [md] if md not in mods else []
        cm["entities"].append({"id": n["id"], "label": n.get("label", ""), "kind": kd, "compartment": n.get("comp", ""), "italic": n["italic"], "glyph": sh,
                               "mods": n.get("mods", []), "fill": fill, "data_value": dv, "aliases": n.get("aliases", []), "xref": n.get("xref", ""), "src": s})
    lg, used, segs, seen, LQ = sp.get("legend"), [], [], {}, []
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
            e["id"], " ".join("%.1f,%.1f" % p for p in pts), col, e.get("width", round(2 * min(S, 1.5), 1)), ' stroke-dasharray="%s"' % dash if dash else "", m, q(s)))
        lab = lambda i: (ends[i] or {}).get("label", str(e[("from", "to")[i]]))  # noqa: E731
        cm["relations"].append({"id": e["id"], "from": lab(0), "to": lab(1), "type": t, "evidence": ev, "label": e.get("label", ""), "src": s})
        if e.get("label"):
            LQ.append((e, pts, col, s))
    hits = lambda b: [k for k, n in N.items() if b[0] < n["cx"] + n["w"] / 2.0 and b[2] > n["cx"] - n["w"] / 2.0 and b[1] < n["cy"] + n["h"] / 2.0 and b[3] > n["cy"] - n["h"] / 2.0]  # noqa: E731
    def crossed(b, eid):
        return sorted({sg[0] for sg in segs if sg[0] != eid and any(inside(sg[1] + (sg[3] - sg[1]) * f / 30.0, sg[2] + (sg[4] - sg[2]) * f / 30.0, b) for f in range(31))})
    placed = []
    for e, pts, col, s in LQ:  # labels after all lines: choose the segment where the label hides nothing
        lfs, lw = 12 * S, tw(e["label"], 12 * S)
        best = None
        for k in sorted(range(1, len(pts)), key=lambda k: (abs(k - len(pts) // 2), -abs(pts[k][0] - pts[k - 1][0]) - abs(pts[k][1] - pts[k - 1][1]))):
            mx, my = (pts[k - 1][0] + pts[k][0]) / 2.0, (pts[k - 1][1] + pts[k][1]) / 2.0
            vert = abs(pts[k][1] - pts[k - 1][1]) > abs(pts[k][0] - pts[k - 1][0])
            for sd in (1, -1):
                lx, ly, anc = (mx + sd * 6 * S, my + 4 * S, "start" if sd > 0 else "end") if vert else (mx, my - 6 * S if sd > 0 else my + 16 * S, "middle")
                bx = lx - 2 - (0 if vert and sd > 0 else lw if vert else lw / 2)
                box = (bx, ly - 13 * S, bx + lw + 4, ly + 3 * S)
                bad = (len(hits(box)) * 3 + len(crossed(box, e["id"])) + 9 * (box[0] < 2 or box[2] > W - 2) + 3 * sum(1 for pb in placed if box[0] < pb[2] and box[2] > pb[0] and box[1] < pb[3] and box[3] > pb[1]),
                       abs(k - len(pts) // 2), sd < 0)
                if best is None or bad < best[0]:
                    best = (bad, lx, ly, anc, box)
        bad, lx, ly, anc, box = best
        placed.append(box)
        warn += ["label of edge %s (%r) is hidden under node %s: shorten it or move nodes" % (e["id"], e["label"], k) for k in hits(box)]
        warn += ["label of edge %s (%r) sits on edge %s: shorten the label or re-route" % (e["id"], e["label"], k) for k in crossed(box, e["id"])[:2]]
        L["edges"].append('<rect id="%s-labelbg" x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="#FFFFFF" opacity="0.85"/>' % (e["id"], box[0], box[1], box[2] - box[0], box[3] - box[1]))
        L["edges"].append(txt(e["id"] + "-label", lx, ly, [e["label"]], lfs, e, s, anc, col))
    xs = 0
    for i, s1 in enumerate(segs):
        for s2 in segs[i + 1:]:
            if s1[0] != s2[0]:
                d = (s1[3] - s1[1]) * (s2[4] - s2[2]) - (s1[4] - s1[2]) * (s2[3] - s2[1])
                if abs(d) > 1e-9:
                    u = ((s2[1] - s1[1]) * (s2[4] - s2[2]) - (s2[2] - s1[2]) * (s2[3] - s2[1])) / d
                    v = ((s2[1] - s1[1]) * (s1[4] - s1[2]) - (s2[2] - s1[2]) * (s1[3] - s1[1])) / d
                    xs += 0.02 < u < 0.98 and 0.02 < v < 0.98
    for t in sp.get("texts", []):
        tfs = t.get("fs", 14 * S)
        lines = wrap(t["text"], t["w"], tfs, t.get("bold")) if t.get("w") else str(t["text"]).split("\n")
        L["text"].append(txt(t["id"], t["x"], t["y"], lines, tfs, t, src(t, "text"), t.get("anchor", "start")))
    fills = sorted({n.get("fill") for n in N.values() if n.get("fill") and n.get("fill") not in cols and n.get("fill").upper() != "#FFFFFF"})
    if lg:
        given = {(("edge", it["edge"]) if it.get("edge") else ("evidence", it["evidence"]) if it.get("evidence") else ("fill", it.get("fill", "").upper())): it for it in lg.get("items", [])}
        have, uk = set(given), [u for u in EDGE if ("edge", u) in used] + [u for u in EVID if ("evidence", u) in used]
        items = [given.get((k, v)) or {k: v, "label": ELAB.get(v, v) if k == "edge" else v + " evidence"} for k in ("edge", "evidence") for v in uk if (k, v) in used]
        warn += ["legend lists %s %s that is not used in the figure" % h for h in have if h[0] != "fill" and h not in set(used)]
        warn += ["fill %s used on nodes but has no legend item (say what it encodes)" % f for f in fills if ("fill", f.upper()) not in have]
        if auto or lg.get("glyphs"):
            items += [{"head": "Entities"}] + [{"kind": k, "label": KLAB.get(k, k)} for k in KLAB if k in kinds] + [{"mod": md, "label": MODS.get(md.upper(), md)} for md in mods]
        if enc:
            items += [{"head": enc and sc.get("title", sc["value"])}] + [{"fill": c, "label": l} for l, c in zip(labs, cols)] + (
                [{"fill": "#FFFFFF", "nodata": 1, "label": "no value in " + os.path.basename(sc["csv"])}] if nodata else [])
        items += [it for h, it in given.items() if h[0] == "fill"]  # own fill items last: adding one later keeps earlier ids stable
        fs1, step = 12 * S, 20 * S
        y = lg["y"] + (22 * S if lg.get("title") else 4)
        if lg.get("title"):
            L["legend"].append(txt("legend-title", lg["x"], lg["y"] + 12 * S, [lg["title"]], 13 * S, {"bold": 1}, lg.get("src", ""), "start"))
        lx0, ytop, ymax = lg["x"], y, y
        for k, it in enumerate(items):
            if lg.get("maxh") and y - ytop > lg["maxh"] - (44 if it.get("head") else 20) * S and y > ytop and lg["x"] < lx0 + (lg.get("cols", 9) - 1.5) * lg.get("colw", 260):
                lg["x"], ymax, y = lg["x"] + lg.get("colw", 260), max(ymax, y), ytop
            i = "legend-" + next(p + re.sub(r"[^a-z0-9]+", "", str(it[k]).lower()) for k, p in (("edge", "edge-"), ("evidence", "ev-"), ("kind", "kind-"), ("mod", "mod-"), ("fill", "fill-"), ("head", "head")) if it.get(k))
            i += "-nodata" if it.get("nodata") else ""
            if it.get("head"):
                L["legend"].append(txt(i, lg["x"], y + 15 * S, [it["head"]], fs1, {"bold": 1}, sc.get("src", sc["csv"]) if sc and it["head"] != "Entities" else "legend", "start"))
                y += 24 * S
                continue
            gh = 14 * S
            if it.get("edge") or it.get("evidence"):
                dash, head, col = EDGE[it["edge"]] if it.get("edge") else (EVID[it["evidence"]], "none", "#555555")
                col = it.get("color", col)
                L["legend"].append('<line id="%s-glyph" x1="%s" y1="%s" x2="%s" y2="%s" stroke="%s" stroke-width="2"%s%s/>' % (i, lg["x"], y + 6 * S, lg["x"] + 34 * S, y + 6 * S, col,
                                   ' stroke-dasharray="%s"' % dash if dash else "", ' marker-end="url(#%s)"' % mk(head, col) if head != "none" else ""))
            elif it.get("kind"):
                gh = 18 * S if it["kind"] == "gene" else 14 * S
                yy = y + (6 * S if it["kind"] == "gene" else 0)
                L["legend"] += [re.sub(r'id="[^"]*" ', "", s0, count=1) if k0 else s0 for k0, s0 in enumerate(shape(KSHAPE.get(it["kind"], "rect"), lg["x"], yy, 34 * S, 14 * S,
                                'id="%s-glyph" fill="#FFFFFF" stroke="#333333" stroke-width="1.2"' % i, lg["x"] + 17 * S, yy + 7 * S))]
                y += gh - 14 * S + (6 * S if it["kind"] == "gene" else 0)
            elif it.get("mod"):
                L["legend"].append('<circle id="%s-glyph" cx="%.1f" cy="%.1f" r="%.1f" fill="#FFFFFF" stroke="#7B3294" stroke-width="1.4"/>' % (i, lg["x"] + 17 * S, y + 6 * S, 10 * S))
                L["legend"].append(txt(i + "-glyphtext", lg["x"] + 17 * S, y + 10 * S, [it["mod"]], fs1, {"bold": 1}, "legend", "middle", "#7B3294"))
                y += 4 * S
            else:
                L["legend"].append('<rect id="%s-glyph" x="%s" y="%s" width="%.1f" height="%.1f" fill="%s" stroke="%s"%s/>' % (
                    i, lg["x"], y, 30 * S, 13 * S, it["fill"], "#555555", ""))
            L["legend"].append(txt(i, lg["x"] + 44 * S, y + 11 * S, [it["label"]], fs1, {}, it.get("src", "legend"), "start"))
            cm["legend"].append({k: v for k, v in it.items() if k != "src"})
            y += step
        y = max(y, ymax)
        lb = (lx0 - 4, lg["y"] - 4, lg["x"] + 44 * S + max([tw(str(it.get("label", it.get("head", ""))), fs1) for it in items] or [0]) + 4, y + 2)
        lg["x"] = lx0
        if cv.get("autosize"):
            W, H = max(W, int(lb[2] + 16)), max(H, int(lb[3] + 16))
        warn += ["edge %s crosses the legend box: re-route it (via) or move the legend" % e for e in sorted({s[0] for s in segs if any(inside(s[1] + (s[3] - s[1]) * f / 30.0, s[2] + (s[4] - s[2]) * f / 30.0, lb) for f in range(31))})]
        warn += ["legend runs past the canvas (right edge %.0f > w %s): widen canvas.w or move the legend" % (lb[2], W)] if lb[2] > W or y > H else []
        warn += ["node %s overlaps the legend box" % k for k, n in N.items() if n["cx"] + n["w"] / 2.0 > lb[0] and n["cx"] - n["w"] / 2.0 < lb[2] and n["cy"] + n["h"] / 2.0 > lb[1] and n["cy"] - n["h"] / 2.0 < lb[3]]
    elif sp.get("edges"):
        warn.append("no legend: add legend{x,y} (items are auto-filled from the edge types, evidence styles and colour scale used)")
    if cv.get("title"):
        L["text"].append(txt("figure-title", W / 2.0, 34 * S, [cv["title"]], cv.get("title_fs", 20 * S), {"bold": 1}, cv.get("src", ""), "middle"))
    wa, ha = ("%smm" % cv["width_mm"], "%.2fmm" % (cv["width_mm"] * H / float(W))) if cv.get("width_mm") else (W, H)  # physical size for journals
    fonts = {"min_px": round(min(FSUSED or [0]), 2)}
    if cv.get("width_mm"):
        fonts["min_pt"] = round(min(FSUSED or [0]) * cv["width_mm"] * 3.78 / float(W) * 0.75, 2)
        if cv.get("min_font_pt") and fonts["min_pt"] < float(cv["min_font_pt"]) - 0.05:
            warn.append("smallest text is %.1f pt at %s mm < min_font_pt %s: set canvas.fs_scale to %.2f (or use auto layout)" % (
                fonts["min_pt"], cv["width_mm"], cv["min_font_pt"], S * float(cv["min_font_pt"]) / fonts["min_pt"]))
    body = "\n".join('<g id="layer-%s">\n%s\n</g>' % (k, "\n".join(v)) for k, v in L.items())
    open(out, "w", encoding="utf-8").write('<?xml version="1.0" encoding="UTF-8"?>\n<svg xmlns="http://www.w3.org/2000/svg" width="%s" height="%s" viewBox="0 0 %s %s" font-family="%s">\n<title>%s</title>\n<defs>%s</defs>\n<rect id="background" width="100%%" height="100%%" fill="#FFFFFF"/>\n%s\n</svg>\n' % (
        wa, ha, W, H, q(cv.get("font", FONT)), escape(cv.get("title", "figure")), "".join(marks.values()), body))
    cm["spec"], cm["spec_sha256_16"] = a[0], hashlib.sha256(open(a[0], "rb").read()).hexdigest()[:16]
    cm["layout"] = {"mode": "auto" if auto else "fixed", "canvas": [W, H], "fs_scale": S, "edge_crossings": xs, "fonts": fonts}
    if auto:
        cm["layout"]["resolved_spec"] = os.path.basename(rpath)
    cmp_ = os.path.splitext(out)[0] + "_content_map.json"
    json.dump(cm, open(cmp_, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n".join(["WARN: " + w for w in warn] or ["no warnings"]) + "\nwrote %s and %s (%d entities, %d relations, %d legend items; %s layout, %d edge crossings, smallest text %s)%s" % (
        out, cmp_, len(cm["entities"]), len(cm["relations"]), len(cm["legend"]), cm["layout"]["mode"], xs,
        "%.1f pt" % fonts["min_pt"] if "min_pt" in fonts else "%.1f px" % fonts["min_px"],
        "\nresolved coordinates -> %s (copy it to make an edited version: ids and positions stay stable)" % rpath if auto else ""))

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
