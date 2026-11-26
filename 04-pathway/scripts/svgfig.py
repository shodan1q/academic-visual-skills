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
KLAB = {"gene": "gene (italic)", "mrna": "mRNA (italic)", "protein": "protein", "complex": "protein complex",
        "family": "protein family", "small_molecule": "small molecule", "ion": "ion", "cell": "cell", "process": "process"}
MODS = {"P": "phosphorylated", "UB": "ubiquitinated", "AC": "acetylated", "ME": "methylated"}
FONT = "Arial, Helvetica, 'Noto Sans CJK SC', 'Source Han Sans SC', 'WenQuanYi Micro Hei', 'PingFang SC', 'Microsoft YaHei', sans-serif"
FSUSED = []
GS = [1.0, 1.0]  # glyph scale (text scale S) and line-weight scale K of the figure being built
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

def head(i, kind, col, a, b, S, sw=2.0):
    """Explicit end glyph at b for the last segment a->b (plain geometry, no <marker>, so every renderer draws it).
    Returns (svg, new line end)."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    d = (dx * dx + dy * dy) ** 0.5 or 1.0
    ux, uy = dx / d, dy / d
    nx, ny, ln, hw = -uy, ux, min(11.0 * S, max(d - 2, 4.0)), 5.0 * S
    b = (b[0] - ux * 1.5, b[1] - uy * 1.5)
    c = (b[0] - ux * ln, b[1] - uy * ln)
    if kind in ("tri", "open"):
        g = '<polygon id="%s" points="%.1f,%.1f %.1f,%.1f %.1f,%.1f" fill="%s" stroke="%s" stroke-width="%.1f" stroke-linejoin="round"/>' % (
            i, b[0], b[1], c[0] + nx * hw, c[1] + ny * hw, c[0] - nx * hw, c[1] - ny * hw, col if kind == "tri" else "#FFFFFF", col, 1.0 if kind == "tri" else sw * 0.8)
        return g, c
    if kind == "bar":
        return '<line id="%s" x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="%.1f" stroke-linecap="butt"/>' % (
            i, b[0] + nx * hw * 1.3, b[1] + ny * hw * 1.3, b[0] - nx * hw * 1.3, b[1] - ny * hw * 1.3, col, max(3.0, 2.8 * S)), b
    if kind == "dot":
        r = 4.2 * S
        return '<circle id="%s" cx="%.1f" cy="%.1f" r="%.1f" fill="%s"/>' % (i, b[0] - ux * r, b[1] - uy * r, r, col), (b[0] - ux * r, b[1] - uy * r)
    return "", b

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
        c = min(9.0 * GS[0], h / 3.2)
        return ['<polygon %s points="%s"/>' % (base, " ".join("%.1f,%.1f" % p for p in (
            (x + c, y), (x + w - c, y), (x + w, y + c), (x + w, y + h - c), (x + w - c, y + h), (x + c, y + h), (x, y + h - c), (x, y + c))))]
    out, g = [], GS[0]
    if sh == "stack":
        out.append('<rect x="%.1f" y="%.1f" width="%s" height="%s" rx="%g" fill="#FFFFFF" stroke="#333333" stroke-width="%g"/>' % (x + 5 * g, y - 5 * g, w, h, round(4 * g, 1), round(1.2 * GS[1], 1)))
    out.append('<rect %s x="%s" y="%s" width="%s" height="%s" rx="%s"/>' % (base, x, y, w, h, {"round": round(min(12 * g, h * 0.32), 1), "band": 0, "gene": 0, "mrna": 0}.get(sh, 2)))
    if sh == "gene":  # promoter: bent arrow above the left end, pointing along the gene
        out.append('<path d="M%.1f,%.1f v%g h%g" fill="none" stroke="#333333" stroke-width="%g"/><path d="M%.1f,%.1f l%g,%g l%g,%g z" fill="#333333"/>' % (
            x + 10 * g, y, -9 * g, 12 * g, round(1.5 * GS[1], 1), x + 21 * g, y - 12.5 * g, 6 * g, 3.5 * g, -6 * g, 3.5 * g))
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

TSYN = (("inhibit", r"inhib|repress|block|suppress|antagon|degrad|downreg|silenc|negative|抑制|阻断|降解|拮抗|下调"),
        ("transport", r"transport|transloc|import|export|secret|traffick|shuttl|releas|uptake|internal|转运|转位|入核|出核|分泌|释放"),
        ("modify", r"modif|phosph|ubiquit|acetyl|methyl|sumo|glycos|cleav|磷酸化|泛素化|乙酰化|甲基化|修饰|切割"),
        ("bind", r"bind|recruit|complex|interact|dimer|assembl|dock|结合|募集|复合|互作"),
        ("activate", r"activ|induc|promot|stimul|upreg|transcri|express|translat|produc|convert|catal|trigger|enhanc|positive|激活|促进|诱导|上调|转录|表达|催化"),
        ("line", r"assoc|correl|link|unknown|relat|相关|关联"))
KSYN = (("gene", r"^gene|promoter|locus|基因"), ("mrna", r"mrna|transcript|rna"), ("complex", r"complex|复合"), ("family", r"family|家族"),
        ("small_molecule", r"small|metabol|lipid|drug|compound|chemical|ligand_small|nucleotide|second.?mess|小分子|代谢|药物|脂"), ("ion", r"^ion|离子"),
        ("cell", r"cell|细胞"), ("process", r"process|phenotype|outcome|event|stimul|stress|pathway|表型|过程|结局"),
        ("protein", r"protein|receptor|kinase|enzyme|tf|factor|ligand|cytokine|channel|phosphatase|ligase|adaptor|蛋白|受体|激酶|酶|因子"))
ESYN = (("hypothesis", r"hypoth|putat|propos|specul|untest|unknown|unclear|possib|predict|假设|推测|未检验|可能"), ("indirect", r"indirect|infer|overexp|weak|间接"))

def normalize(sp, warn):
    """Accept the spec variants a hurried author writes (other key names, type words, missing ids) instead of crashing."""
    def first(o, keys, pop=True):
        for k in keys:
            if o.get(k) not in (None, ""):
                return o.pop(k) if pop else o[k]
        return None
    def syn(v, table, valid):
        t = str(v or "").strip().lower().replace("-", "_").replace(" ", "_")
        if t in valid:
            return t
        return next((k for k, rx in table if re.search(rx, t)), None)
    cv = sp["canvas"] = sp["canvas"] if isinstance(sp.get("canvas"), dict) else {}
    for k in ("width_mm", "min_font_pt", "w", "h", "fs_scale"):
        if k in cv:
            try:
                cv[k] = float(re.sub(r"[^\d.]", "", str(cv[k])))
            except ValueError:
                warn.append("canvas.%s %r is not a number: ignored" % (k, cv.pop(k)))
    for key in ("panels", "nodes", "edges", "texts"):
        v = sp.get(key)
        sp[key] = [o for o in (list(v.values()) if isinstance(v, dict) else v if isinstance(v, list) else []) if isinstance(o, dict)]
    seen = set()
    def uid(o, base):
        i = re.sub(r"[^\w.\-]+", "-", str(o.get("id") or base)).strip("-") or base
        while i in seen:
            i += "x"
        seen.add(i)
        o["id"] = i
    for k, p in enumerate(sp["panels"]):
        p["title"] = str(first(p, ("title", "label", "name")) or p.get("id") or "")
        uid(p, "p%d" % (k + 1))
        par = first(p, ("in", "parent", "inside"))
        if par:
            p["in"] = par
    ptitle = {}
    for p in sp["panels"]:
        ptitle[nm(p["id"])] = ptitle[nm(p["title"])] = p["id"]
        if p.get("in") and p["in"] not in [x["id"] for x in sp["panels"]]:
            p["in"] = ptitle.get(nm(p["in"])) or p.pop("in") and None
            if not p.get("in"):
                p.pop("in", None)
    for k, n in enumerate(sp["nodes"]):
        lab = first(n, ("label", "name", "text", "symbol", "title"))
        n["label"] = str(lab if lab is not None else n.get("id", ""))
        uid(n, "n%d" % (k + 1))
        kd = first(n, ("kind", "type", "class", "category"))
        if kd is not None:
            k2 = syn(kd, KSYN, KLAB)
            if k2:
                n["kind"] = k2
            else:
                warn.append("node %s: unknown kind %r (use gene/mrna/protein/complex/family/small_molecule/ion/cell/process)" % (n["id"], kd))
        cp = first(n, ("comp", "compartment", "panel", "location", "in"))
        if cp is not None:
            c2 = cp if cp in [x["id"] for x in sp["panels"]] else ptitle.get(nm(cp)) or next((v for t, v in ptitle.items() if t and (t in nm(cp) or nm(cp) in t)), None)
            if c2:
                n["comp"] = c2
            else:
                warn.append("node %s: comp %r matches no panel id/title (placed outside the compartments)" % (n["id"], cp))
        if isinstance(n.get("mods"), str):
            n["mods"] = [n["mods"]]
        if isinstance(n.get("aliases"), str):
            n["aliases"] = [n["aliases"]]
    nid = {n["id"] for n in sp["nodes"]}
    nlab = {}
    for n in sp["nodes"]:
        nlab.setdefault(nm(n["label"]), n["id"])
    keep = []
    for k, e in enumerate(sp["edges"]):
        e["from"], e["to"] = first(e, ("from", "source", "src_node", "start", "a")), first(e, ("to", "target", "dst", "end", "b"))
        uid(e, "e%d" % (k + 1))
        for kk in ("from", "to"):
            if isinstance(e[kk], str) and e[kk] not in nid:
                e[kk] = nlab.get(nm(e[kk]), e[kk])
        if not all(isinstance(e[kk], (list, tuple)) or e[kk] in nid for kk in ("from", "to")):
            warn.append("edge %s: %r -> %r refers to an unknown node id (edge not drawn)" % (e["id"], e["from"], e["to"]))
            continue
        t0 = first(e, ("type", "relation", "interaction", "kind"))
        t = syn(t0, TSYN, EDGE)
        if not t:
            t = "line"
            warn.append("edge %s: type %r not recognised, drawn as plain line (use activate/inhibit/bind/modify/transport/line)" % (e["id"], t0))
        e["type"] = t
        ev0 = e.get("evidence")
        if ev0 is not None:
            e["evidence"] = "direct" if str(ev0).strip().lower() in ("direct", "strong", "confirmed", "true", "直接") else syn(ev0, ESYN, EVID) or "direct"
        if "label" in e and e["label"] is not None:
            e["label"] = str(e["label"])
        keep.append(e)
    sp["edges"] = keep
    for k, t in enumerate(sp["texts"]):
        t["text"] = str(first(t, ("text", "label")) or "")
        uid(t, "t%d" % (k + 1))
    sp["texts"] = [t for t in sp["texts"] if t["text"]]
    for o in sp["panels"] + sp["nodes"] + sp["edges"] + sp["texts"]:
        if not o.get("src"):
            v = first(o, ("source", "ref", "citation", "provenance", "evidence_src"))
            if v:
                o["src"] = str(v)
    sc = cv.get("colorscale")
    if sc is not None:
        try:
            base = sc["csv"] if os.path.isabs(str(sc["csv"])) else os.path.join(cv.get("_base", "."), str(sc["csv"]))
            hdr = next(csv.reader(open(base, encoding="utf-8-sig")))
            [float(b) for b in sc["breaks"]]
            if sc["value"] not in hdr:
                raise KeyError("column %r not in %s" % (sc["value"], hdr))
        except Exception as ex:  # unreadable data must not stop the figure
            warn.append("colorscale ignored (%s: %s): nodes are not coloured by data; fix canvas.colorscale csv/key/value/breaks" % (type(ex).__name__, ex))
            cv.pop("colorscale")
    if sp.get("legend") is not None and not isinstance(sp["legend"], dict):
        sp["legend"] = {"title": "Legend"}
    cv.pop("_base", None)

def thin(p):
    t = str(p.get("title", "")).lower()
    return bool(p.get("membrane")) or ("h" in p and p["h"] < 44 and not p.get("auto")) or "membrane" in t or "envelope" in t or "膜" in t

def legend_est(sp, F):
    """Rough legend size before build: (number of rows, widest label px)."""
    ed = sp.get("edges", [])
    labs = ["Interactions"] + [ELAB.get(t, t) for t in {e.get("type", "step") for e in ed}] + [v + " evidence" for v in {e.get("evidence") for e in ed} if v in EVID]
    labs += ["Entities"] + [KLAB.get(k, k) for k in {n.get("kind") for n in sp.get("nodes", []) if n.get("kind")}]
    labs += [MODS.get(str(m).upper(), m) for m in {m for n in sp.get("nodes", []) for m in (n.get("mods") or [])}]
    sc = sp["canvas"].get("colorscale")
    if sc:
        labs += [sc.get("title", sc.get("value", ""))] + ["x to < y"] * (len(sc.get("breaks", [])) + 1) + ["no data"]
    labs += [it.get("label", "") for it in (sp.get("legend") or {}).get("items", [])]
    return len(labs) + 2, max([tw(str(l), 12 * F) for l in labs] + [60])

def legend_plan(groups, avail):
    """Place legend groups (w, h) left to right, wrapping to a new band when the row is full -> ([(dx, dy)], total height)."""
    pos, x, y, band = [], 0.0, 0.0, 0.0
    for w, h in groups:
        if x > 0 and x + w > avail:
            x, y, band = 0.0, y + band + 8, 0.0
        pos.append((x, y))
        x, band = x + w, max(band, h)
    return pos, y + band

def legend_groups(sp, F):
    ed = sp.get("edges", [])
    g = [["Interactions"] + [ELAB.get(t, t) for t in {e.get("type", "step") for e in ed}] + [v + " evidence" for v in {e.get("evidence") for e in ed} if v in EVID]]
    g.append(["Entities"] + [KLAB.get(k, k) for k in {n.get("kind") for n in sp.get("nodes", []) if n.get("kind")}] +
             [MODS.get(str(m).upper(), m) for m in {m for n in sp.get("nodes", []) for m in (n.get("mods") or [])}])
    sc = sp["canvas"].get("colorscale")
    if sc:
        g.append([sc.get("title", sc.get("value", ""))] + ["x to < y"] * (len(sc.get("breaks", [])) + 1) + ["no data"])
    g[-1] += [it.get("label", "") for it in (sp.get("legend") or {}).get("items", []) if it.get("fill")]
    return [(44 * F + max([tw(str(l), 12 * F) for l in labs] + [40]) + 26, len(labs) * 20 * F + 8 * F) for labs in g if labs]

def layout(sp, F, where="right", stretch=0, fold=False):
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
    FL, run = {}, {}  # fold: an unbranched step u -> v inside one compartment continues to the right on the same row (max 3 per row)
    if fold:
        for e in E:
            u, v = e["from"], e["to"]
            if (N[u].get("comp") == N[v].get("comp") and v in dag[u] and "rank" not in N[u] and "rank" not in N[v] and len(str(e.get("label") or "")) <= 10
                    and sum(1 for x in E if x["from"] == u) == 1 and sum(1 for x in E if x["to"] == v) == 1
                    and all(len(dag[w]) <= 1 for w in pred[u]) and not (PI.get(N[u].get("comp")) and thin(PI[N[u]["comp"]]))):
                FL[u] = v
        heads = [u for u in FL if u not in FL.values()]
        for h in heads:
            u, k = h, 0
            while u in FL and k < 2:
                run[FL[u]] = (h, k + 1)
                u, k = FL[u], k + 1
            if u in FL:  # longer chain: the rest starts a new row
                heads.append(FL[u])
        FL = {u: v for u, v in FL.items() if v in run}
    step = lambda u, v: 0 if FL.get(u) == v else 1  # noqa: E731
    while st:  # rows count causal steps inside each compartment; input from another compartment starts at its top
        u = st.pop(0)
        order.append(u)
        for v in dag[u]:
            if top_of(u) == top_of(v):
                rank[v] = max(rank[v], rank[u] + step(u, v))
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
                    rank[v] = max(rank[v], rank[u] + step(u, v))
    for u in reversed(order):  # pure sources sit next to (binding partner) or just above their first target
        if not indeg[u] and [v for v in dag[u] if top_of(v) == top_of(u)]:
            v = min([v for v in dag[u] if top_of(v) == top_of(u)], key=lambda v: rank[v])
            side = all(e["type"] == "bind" for e in E if e["from"] == u) and top_of(u) == top_of(v) and len(pred[v]) > 1
            rank[u] = rank[v] if side or FL.get(u) == v else max(0, rank[v] - 1)
    for u in reversed(order):  # organelle member fed only from outside its compartment: as late as its targets in the organelle allow
        if (PI.get(N[u].get("comp")) or {}).get("in") in PI and not [w for w in pred[u] if top_of(w) == top_of(u) and (w, u) not in back]:
            nx = [rank[v] for v in dag[u] if N[v].get("comp") == N[u].get("comp")]
            if nx:
                rank[u] = max(rank[u], min(nx) - 1)
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
            n["w"] = round(min(max(w * (1.3 if sh in ("ellipse", "circle") else 1), 78 * F), 128 * F), 1)
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
            slot[i] = int(N[i].get("col", k))
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
    for r in rows if run else []:  # folded chains read left to right in adjacent columns
        seq = sorted(r["ids"], key=lambda i: slot[i])
        hp = {i: k for k, i in enumerate(seq)}
        seq.sort(key=lambda i: (hp.get(run[i][0], hp[i]), run[i][1]) if i in run and run[i][0] in hp else (hp[i], 0))
        sv, prev = sorted(slot[i] for i in seq), None
        for k, i in enumerate(seq):
            slot[i] = prev + 1 if prev is not None and (i in run or sv[k] <= prev) else sv[k]
            prev = slot[i]
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
    gap = 30 + 14 * F + stretch
    colw = [max([N[i]["w"] for i in slot if slot[i] == c] + [40 * F]) for c in range(ncol)]
    titled = [p for p in panels if p.get("title")]
    reserve = max([tw(p["title"], 12.5 * F, True) + 26 for p in titled if thin(p) and not p.get("in")] + [24])
    X0, PX = 20 + reserve, 20
    xl, need = [X0], {}
    for c in range(ncol):
        xl.append(xl[-1] + colw[c] + gap)
    for e in E:  # a labelled link between neighbours on one row: the space between the two nodes must hold the label
        u, v = sorted((e["from"], e["to"]), key=lambda i: slot[i])
        if rowof[u] == rowof[v] and slot[v] - slot[u] == 1 and e.get("label"):
            clear = (xl[slot[v]] + xl[slot[v] + 1] - N[v]["w"]) / 2.0 - (xl[slot[u]] + xl[slot[u] + 1] + N[u]["w"]) / 2.0
            need[slot[u]] = max(need.get(slot[u], 0), min(2 * (tw(str(e["label"]), 12 * F) + 30 * F - clear), 150 * F))  # nodes sit mid-span: half of the extra reaches this gap
    if any(v > 0 for v in need.values()):
        xl = [X0]
        for c in range(ncol):
            xl.append(xl[-1] + colw[c] + gap + max(0, need.get(c, 0)))
    cv["title_w"] = round(max(xl[-1] + 18 - PX, 300 * F), 1)
    y = y0_top(cv, F)
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
            gut[k] = (cy - mh / 2.0 - 4 - 8 * F, cy + mh / 2.0 + 4 + 8 * F)
        else:
            if r["sub"] and r.get("first"):
                y += 10 if r["thin"] else 14 + 16 * F
                PI[r["sub"]]["_y"] = y - (0 if r["thin"] else 6 + 16 * F)
            pad = 9 + 10 * F
            cy = y + pad + mh / 2.0
            gut[k] = (cy - mh / 2.0 - 5 - 9 * F, cy + mh / 2.0 + 5 + 9 * F)
            y = cy + mh / 2.0 + pad
            if r["sub"] and r.get("last"):
                PI[r["sub"]]["_y2"] = y - pad + (10 if r["thin"] else 14)
                y += 6
        for i in r["ids"]:
            N[i]["cx"], N[i]["cy"] = round((xl[slot[i]] + xl[slot[i] + 1]) / 2.0, 1), round(cy, 1)
            info[i] = (k, slot[i])
        if k == len(rows) - 1 or rows[k + 1]["top"] != r["top"]:
            p["_y2"] = y + (0 if r["thin"] and not r["sub"] else 4)
    gx = lambda g: xl[max(0, min(ncol, g))]  # noqa: E731  lane g = left boundary of column g
    used = {}
    def off(key, step):
        n = used.get(key, 0)
        used[key] = n + 1
        return step * ((n + 1) // 2) * (1 if n % 2 else -1)
    def blocked(a, b):
        x1, y1, x2, y2 = a["cx"], a["cy"], b["cx"], b["cy"]
        return any(n is not a and n is not b and any(abs(x1 + (x2 - x1) * f / 24.0 - n["cx"]) < n["w"] / 2.0 + 4 and
                                                     abs(y1 + (y2 - y1) * f / 24.0 - n["cy"]) < n["h"] / 2.0 + 4 for f in range(1, 24)) for n in nodes)
    seen, side, bus = set(), {}, {}
    for e in E:
        a, b = N[e["from"]], N[e["to"]]
        (r1, c1), (r2, c2) = info[a["id"]], info[b["id"]]
        pair = frozenset((a["id"], b["id"]))
        dup = pair in seen
        seen.add(pair)
        e.pop("via", None), e.pop("elbow", None), e.pop("ports", None)
        near = r2 == r1 + 1 or (r2 > r1 and c1 == c2) or (r1 == r2 and abs(c1 - c2) == 1) or (r2 == r1 - 1 and c1 == c2)
        if not dup and near and not blocked(a, b):
            if r2 == r1 + 1 and c1 != c2 and not cv.get("diagonal"):  # next row, other column: right-angle connector (down, across, down)
                if (r1, a["id"]) not in bus:
                    bus[(r1, a["id"])] = gut[r1][1] + off(("g", r1, 1), 6)
                e["via"] = [[round(a["cx"], 1), round(bus[(r1, a["id"])], 1)], [round(b["cx"], 1), round(bus[(r1, a["id"])], 1)]]
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
    pk = {}  # ports: edges that meet the top/bottom of a node are spread along that side instead of sharing its centre
    for e in E:
        a, b, v = N[e["from"]], N[e["to"]], e.get("via") or []
        for n, o, k in ((a, b, 0), (b, a, 1)):
            qq = (v[0] if k == 0 else v[-1]) if v else (o["cx"], o["cy"])
            sd = "b" if qq[1] > n["cy"] + n["h"] / 4.0 else "t" if qq[1] < n["cy"] - n["h"] / 4.0 else None
            if sd and (not v or abs(qq[0] - n["cx"]) < 0.5):
                key = qq[0] if not v else (v[1] if k == 0 else v[-2])[0] if len(v) > 1 else qq[0]
                pk.setdefault((n["id"], sd), []).append((key, e["id"], e, k))
    for (nid, sd), lst in pk.items():
        n, m = N[nid], len(lst)
        lst.sort(key=lambda t: (t[0], t[1]))
        step = min(18 * F, n["w"] * 0.66 / m)
        for j, (_, _, e, k) in enumerate(lst):
            o, hh = (j - (m - 1) / 2.0) * step, n["h"] / 2.0
            if n.get("shape") in ("ellipse", "circle"):
                hh *= max(0.2, 1 - (o / (n["w"] / 2.0)) ** 2) ** 0.5
            pt = [round(n["cx"] + o, 1), round(n["cy"] + (hh if sd == "b" else -hh), 1)]
            e.setdefault("ports", [None, None])[k] = pt
            if e.get("via"):  # first / last leg stays vertical
                (e["via"][0] if k == 0 else e["via"][-1])[0] = pt[0]
    for e in E:  # straight link inside one column stays vertical: both ends take the port of the busier node
        pr, a, b = e.get("ports"), N[e["from"]], N[e["to"]]
        if pr and pr[0] and pr[1] and not e.get("via") and abs(a["cx"] - b["cx"]) < 1:
            k = 0 if len(pk.get((a["id"], "b" if b["cy"] > a["cy"] else "t"), [])) >= len(pk.get((b["id"], "t" if b["cy"] > a["cy"] else "b"), [])) else 1
            pr[1 - k][0] = pr[k][0]
    for e in E:  # parallel second relation: its two offset points are the ends themselves
        v = e.get("via")
        if v and len(v) == 2 and not e.get("ports") and (abs(v[0][0] - v[1][0]) < 0.5 and abs(v[0][0] - N[e["from"]]["cx"]) > 0.5 or abs(v[0][1] - v[1][1]) < 0.5 and abs(v[0][1] - N[e["from"]]["cy"]) < N[e["from"]]["h"] / 2.0):
            e["ports"] = [v[0], v[1]]
            del e["via"]
    right = gx(ncol) + 18 + 9 * side.get(ncol, 0)
    if where != "right":  # legend below: panels span the full width under the title
        right = max(right, PX + 300 * F)
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
        gs = legend_groups(sp, F)
        avail = max(right - PX, max(g[0] for g in gs))
        lg.update(x=PX + 4, y=round(bottom + 12 + 8 * F, 1), groups=True, avail=round(avail, 1))
        cv["w"], cv["h"] = round(max(right + 6, PX + avail + 6)), round(bottom + 12 + 30 * F + legend_plan(gs, avail)[1] + 16)
    cv["w"] = max(cv["w"], int(cv["title_w"] + 2 * PX))
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
    if not cv.get("title"):
        return 16
    return 14 + 24 * F * len(wrap(cv["title"], cv["title_w"] * 0.88, 20 * F, True)) + 10 if cv.get("title_w") else 40 + 22 * F

def build(a):
    try:
        sp, out = json.load(open(a[0], encoding="utf-8-sig")), a[1]
    except ValueError as ex:
        print("FAIL: %s is not valid JSON (%s). Fix that spot and build again." % (a[0], ex))
        return 2
    warn, marks, N, P = [], {}, {}, {}
    if not isinstance(sp, dict):
        sp = {"nodes": sp if isinstance(sp, list) else []}
    if isinstance(sp.get("canvas"), dict):
        sp["canvas"]["_base"] = os.path.dirname(os.path.abspath(a[0]))
    normalize(sp, warn)
    cv = sp["canvas"]
    del FSUSED[:]
    auto = cv.get("layout") == "auto" or (not cv.get("grid") and bool(sp.get("nodes")) and any("cx" not in n and "col" not in n for n in sp["nodes"]))
    if auto:
        F0, mm, mp = float(cv.get("fs_scale", 1)), cv.get("width_mm"), cv.get("min_font_pt")
        tries = [(F0 + 0.15 * k, wh, st, fo) for k in range(18) for wh in ((cv.get("legend_at"),) if cv.get("legend_at") in ("right", "bottom") else ("right", "bottom"))
                 for st in (0, 16, 32, 48) for fo in (False, True)]  # st: wider column gaps, so a tall diagram uses the page width instead of oversized text
        best = fok = None
        for F, wh, st, fo in tries:  # smallest font scale that keeps every text >= min_font_pt at width_mm without a page-breaking height
            s2 = copy.deepcopy(sp)
            Wl = layout(s2, F, wh, st, fo)
            pt = 12.0 * F * float(mm or 180) * 3.78 / Wl * 0.75
            ok = not (mm and mp) or pt >= float(mp) * 1.04
            if fok is not None and F > fok + 0.61:
                break
            asp = s2["canvas"]["h"] / float(Wl)  # a page-like shape first (not much taller than wide), then the smallest scale
            key = (not ok, round(max(0.0, asp - 1.3), 1) if ok else 0, F if ok else -pt, fo, st, asp)
            fok = F if ok and fok is None else fok
            if best is None or key < best[0]:
                best = (key, s2)
        s2 = best[1]
        sp, cv = s2, s2["canvas"]
        res = copy.deepcopy(sp)
        res["canvas"]["layout"] = "fixed"
        rpath = os.path.splitext(out)[0] + "_resolved_spec.json"
        json.dump(res, open(rpath, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    S, PXL = float(cv.get("fs_scale", 1)), 20
    K = max(1.0, S * 0.7)  # line weights and dash lengths follow the text scale, so a figure laid out large does not end up with hairlines in print
    GS[:] = [max(1.0, S), K]
    dsc = lambda d: ",".join("%g" % round(float(x) * K, 1) for x in str(d).split(",")) if d and re.match(r"^[\d.,]+$", str(d)) else d  # noqa: E731
    W, H, g = cv.get("w", 1200), cv.get("h", 800), cv.get("grid", {})
    L = {k: [] for k in ("panels", "edges", "nodes", "data", "text", "legend")}
    cm = {"entities": [], "relations": [], "compartments": [], "legend": [], "data_encoding": None, "warnings": warn}
    nosrc = []
    def src(o, kind):
        if not o.get("src"):
            nosrc.append(str(o.get("id")))
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
        L["panels"].append('<rect id="%s" x="%s" y="%s" width="%s" height="%s" rx="%s" fill="%s" stroke="%s" stroke-width="%g" data-src="%s"/>' % (
            p["id"], p["x"], p["y"], p["w"], p["h"], 3 if th else round(8 * GS[0], 1), p.get("fill", "#F2D7B6" if th else "#EEF3F8" if p.get("in") else "#F7F7F7"), p.get("stroke", "#BBBBBB"), round(1.2 * K, 1), q(s)))
        if th:  # lipid bilayer: two rows of head groups
            g = GS[0]
            k = int(p["w"] // (9 * g))
            L["panels"].append('<g id="%s-bilayer">%s</g>' % (p["id"], "".join('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="#C8996A"/>' % (p["x"] + 5 * g + 9 * g * j, yy, 2.8 * g)
                                                                                for j in range(k) for yy in (p["y"] + 4 * g, p["y"] + p["h"] - 4 * g))))
        elif re.search(r"nucle(us|ar)|核", str(p.get("title", "")).lower()) or p.get("envelope"):  # double nuclear envelope
            L["panels"].append('<rect id="%s-envelope" x="%s" y="%s" width="%s" height="%s" rx="%g" fill="none" stroke="%s" stroke-width="%g"/>' % (
                p["id"], p["x"] + 5 * GS[0], p["y"] + 5 * GS[0], p["w"] - 10 * GS[0], p["h"] - 10 * GS[0], round(6 * GS[0], 1), p.get("stroke", "#BBBBBB"), round(K, 1)))
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
        base = 'id="%s" fill="%s" stroke="%s" stroke-width="%s"%s data-src="%s"' % (n["id"], fill, n.get("stroke", "#333333"), n.get("stroke_width", round(1.5 * K, 1)),
                                                                                  ' stroke-dasharray="%s"' % q(dsc("6,4") if n["dash"] is True else n["dash"]) if n.get("dash") else "", q(s))
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
            L["nodes"].append('<circle id="%s-mod-%s" cx="%.1f" cy="%.1f" r="%.1f" fill="#FFFFFF" stroke="#7B3294" stroke-width="%g"/>' % (n["id"], re.sub(r"\W", "", md), bx, by, 11 * S, round(1.4 * K, 1)))
            L["nodes"].append(txt("%s-mod-%s-label" % (n["id"], re.sub(r"\W", "", md)), bx, by + 4.3 * S, [md], 12 * S, {"bold": 1}, s, "middle", "#7B3294"))
            mods += [md] if md not in mods else []
        cm["entities"].append({"id": n["id"], "label": n.get("label", ""), "kind": kd, "compartment": n.get("comp", ""), "italic": n["italic"], "glyph": sh,
                               "mods": n.get("mods", []), "fill": fill, "data_value": dv, "aliases": n.get("aliases", []), "xref": n.get("xref", ""), "src": s})
    lg, used, segs, seen, LQ = sp.get("legend"), [], [], {}, []
    for e in sp.get("edges", []):
        t, ev = e.get("type", "step"), e.get("evidence", "direct")
        dash, hk, col = EDGE.get(t, EDGE["step"])
        dash, col, s = dsc(EVID.get(ev, dash)), e.get("color", col), src(e, "edge")
        used += [("edge", t)] + ([("evidence", ev)] if ev in EVID else [])
        ends = [N.get(e[k]) if isinstance(e[k], str) else None for k in ("from", "to")]
        if any(isinstance(e[k], str) and not ends[i] for i, k in enumerate(("from", "to"))):
            warn.append("edge %s refers to an unknown node id" % e.get("id"))
            continue
        if t == "transport" and all(ends) and not (nm(ends[0].get("label")) in nm(ends[1].get("label")) or nm(ends[1].get("label")) in nm(ends[0].get("label"))):
            warn.append("edge %s: transport joins different entities (%s -> %s); transport = the SAME entity moving between compartments. "
                        "Draw a copy in the target compartment, then activate (e.g. transcription) to the gene" % (e["id"], ends[0].get("label"), ends[1].get("label")))
        pair = frozenset((e["from"], e["to"])) if isinstance(e["from"], str) and isinstance(e["to"], str) else None
        if pair and pair in seen and not (e.get("via") or e.get("elbow") or e.get("ports")):
            warn.append("edges %s and %s draw over each other (same node pair): give one a via route or merge them" % (seen[pair], e["id"]))
        seen[pair] = e["id"]
        pts = [(n["cx"], n["cy"]) if n else tuple(e[k]) for n, k in zip(ends, ("from", "to"))]
        pts[1:1] = [tuple(v) for v in e.get("via", [])] or ([(pts[1][0], pts[0][1]) if e["elbow"] == "hv" else (pts[0][0], pts[1][1])] if e.get("elbow") else [])
        warn += ["edge %s: via point %s lies inside node %s (move it outside)" % (e.get("id"), v, k) for v in e.get("via", []) for k, n in N.items() if abs(v[0] - n["cx"]) < n["w"] / 2.0 and abs(v[1] - n["cy"]) < n["h"] / 2.0]
        pr = e.get("ports") or [None, None]
        pts[0] = tuple(pr[0]) if pr[0] else clip(ends[0], *pts[1]) if ends[0] else pts[0]
        pts[-1] = tuple(pr[1]) if pr[1] else clip(ends[1], *pts[-2]) if ends[1] else pts[-1]
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            segs.append((e["id"], x1, y1, x2, y2))
            warn += ["edge %s passes through node %s: add via points or move nodes" % (e.get("id"), k) for k, n in N.items() if all(n is not x for x in ends) and any(
                abs(x1 + (x2 - x1) * f / 20.0 - n["cx"]) < n["w"] / 2.0 - 3 and abs(y1 + (y2 - y1) * f / 20.0 - n["cy"]) < n["h"] / 2.0 - 3 for f in range(1, 20))]
        sw = e.get("width", round(2 * max(min(S, 1.5), S * 0.85), 1))
        hd = []
        if hk != "none" and len(pts) > 1:
            g1, pts[-1] = head(e["id"] + "-head", hk, col, pts[-2], pts[-1], S, sw)
            hd.append(g1)
            if e.get("both"):
                g2, pts[0] = head(e["id"] + "-head2", hk, col, pts[1], pts[0], S, sw)
                hd.append(g2)
        m = ""
        L["edges"].append('<polyline id="%s" points="%s" fill="none" stroke="%s" stroke-width="%s"%s%s data-src="%s"/>' % (
            e["id"], " ".join("%.1f,%.1f" % p for p in pts), col, sw, ' stroke-dasharray="%s"' % dash if dash else "", m, q(s)))
        L["edges"] += hd
        lab = lambda i: (ends[i] or {}).get("label", str(e[("from", "to")[i]]))  # noqa: E731
        cm["relations"].append({"id": e["id"], "from": lab(0), "to": lab(1), "type": t, "evidence": ev, "label": e.get("label", ""), "src": s})
        if e.get("label"):
            fan = (str(e["from"]), t, ev, e["label"])  # one source, same relation to several targets: the shared label is written once
            if fan not in seen or len(e["label"]) < 6:
                LQ.append((e, pts, col, s))
            seen[fan] = e["id"]
    hits = lambda b: [k for k, n in N.items() if b[0] < n["cx"] + n["w"] / 2.0 and b[2] > n["cx"] - n["w"] / 2.0 and b[1] < n["cy"] + n["h"] / 2.0 and b[3] > n["cy"] - n["h"] / 2.0]  # noqa: E731
    def crossed(b, eid):
        return sorted({sg[0] for sg in segs if sg[0] != eid and any(inside(sg[1] + (sg[3] - sg[1]) * f / 30.0, sg[2] + (sg[4] - sg[2]) * f / 30.0, b) for f in range(31))})
    placed = [(p["x"] + 6, p["y"] + 4, p["x"] + 14 + tw(p.get("title", ""), 15 * S, True), p["y"] + 30 * S) for p in sp.get("panels", []) if p.get("title") and not thin(p)]
    for e, pts, col, s in LQ:  # labels after all lines: choose the segment where the label hides nothing
        lfs, lw = 12 * S, tw(e["label"], 12 * S)
        best = None
        for k in sorted(range(1, len(pts)), key=lambda k: (abs(k - len(pts) // 2), -abs(pts[k][0] - pts[k - 1][0]) - abs(pts[k][1] - pts[k - 1][1]))):
          vert = abs(pts[k][1] - pts[k - 1][1]) > 0.6 * abs(pts[k][0] - pts[k - 1][0])
          for tq, sd in ((0.5, 1), (0.5, -1), (0.32, 1), (0.32, -1), (0.68, 1), (0.68, -1), (0.2, 1), (0.2, -1), (0.8, 1), (0.8, -1)):
                mx, my = pts[k - 1][0] + (pts[k][0] - pts[k - 1][0]) * tq, pts[k - 1][1] + (pts[k][1] - pts[k - 1][1]) * tq
                lx, ly, anc = (mx + sd * 6 * S, my + 4 * S, "start" if sd > 0 else "end") if vert else (mx, my - 6 * S if sd > 0 else my + 16 * S, "middle")
                bx = lx - 2 - (0 if vert and sd > 0 else lw if vert else lw / 2)
                box = (bx, ly - 13 * S, bx + lw + 4, ly + 3 * S)
                bad = (len(hits(box)) * 8 + len(crossed(box, e["id"])) + 9 * (box[0] < 2 or box[2] > W - 2) + 5 * sum(1 for pb in placed if box[0] < pb[2] and box[2] > pb[0] and box[1] < pb[3] and box[3] > pb[1]),
                       abs(k - len(pts) // 2), tq != 0.5, sd < 0)
                if best is None or bad < best[0]:
                    best = (bad, lx, ly, anc, box)
        bad, lx, ly, anc, box = best
        placed.append(box)
        warn += ["label of edge %s (%r) is hidden under node %s: shorten it or move nodes" % (e["id"], e["label"], k) for k in hits(box)]
        warn += ["label of edge %s (%r) sits on edge %s: shorten the label or re-route" % (e["id"], e["label"], k) for k in crossed(box, e["id"])[:2]]
        cxb, cyb, bgc = (box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0, "#FFFFFF"
        for p in sorted(sp.get("panels", []), key=lambda p: -p["w"] * p["h"]):  # innermost compartment under the label
            if p["x"] <= cxb <= p["x"] + p["w"] and p["y"] <= cyb <= p["y"] + p["h"]:
                bgc = p.get("fill", "#F2D7B6" if (thin(p) if p.get("auto") else p["h"] < 44) else "#EEF3F8" if p.get("in") else "#F7F7F7")
        trim = (box[2] - box[0]) * 0.05
        L["edges"].append('<rect id="%s-labelbg" x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="2" fill="%s" opacity="0.92"/>' % (
            e["id"], box[0] + (0 if anc == "start" else trim * (2 if anc == "end" else 1)), box[1], box[2] - box[0] - 2 * trim, box[3] - box[1], bgc))
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
            items[0:0] = [{"head": "Interactions"}]
            items += [{"head": "Entities"}] + [{"kind": k, "label": KLAB.get(k, k)} for k in KLAB if k in kinds] + [{"mod": md, "label": MODS.get(md.upper(), md)} for md in mods]
        if enc:
            items += [{"head": enc and sc.get("title", sc["value"])}] + [{"fill": c, "label": l} for l, c in zip(labs, cols)] + (
                [{"fill": "#FFFFFF", "nodata": 1, "label": "no data"}] if nodata else [])
        items += [it for h, it in given.items() if h[0] == "fill"]  # own fill items last: adding one later keeps earlier ids stable
        fs1, step = 12 * S, 20 * S
        y = lg["y"] + (22 * S if lg.get("title") else 4)
        if lg.get("title"):
            L["legend"].append(txt("legend-title", lg["x"], lg["y"] + 12 * S, [lg["title"]], 13 * S, {"bold": 1}, lg.get("src", ""), "start"))
        lx0, ytop, ymax, xr = lg["x"], y, y, lg["x"]
        gpos = None
        if lg.get("groups"):
            gi, cur = [], []
            for it in items:
                if it.get("head") and cur:
                    gi.append(cur)
                    cur = []
                cur.append(it)
            gi.append(cur)
            gpos, _ = legend_plan([(44 * S + max([tw(str(it.get("label", it.get("head", ""))), fs1) for it in g_] + [40]) + 26, sum((24 if it.get("head") else 30 if it.get("kind") == "gene" else 24 if it.get("mod") else 20) * S for it in g_) + 8 * S) for g_ in gi], lg.get("avail", 600))
            gstart = {id(g_[0]): gpos[j] for j, g_ in enumerate(gi)}
        for k, it in enumerate(items):
            if gpos and id(it) in gstart:
                ymax = max(ymax, y)
                lg["x"], y = lx0 + gstart[id(it)][0], ytop + gstart[id(it)][1]
            elif lg.get("maxh") and y - ytop > lg["maxh"] - (44 if it.get("head") else 20) * S and y > ytop and lg["x"] < lx0 + (lg.get("cols", 9) - 1.5) * lg.get("colw", 260):
                lg["x"], ymax, y = lg["x"] + lg.get("colw", 260), max(ymax, y), ytop
            i = "legend-" + next(p + re.sub(r"[^a-z0-9]+", "", str(it[k]).lower()) for k, p in (("edge", "edge-"), ("evidence", "ev-"), ("kind", "kind-"), ("mod", "mod-"), ("fill", "fill-"), ("head", "head")) if it.get(k))
            i += "-nodata" if it.get("nodata") else ""
            if it.get("head"):
                L["legend"].append(txt(i, lg["x"], y + 15 * S, [it["head"]], fs1, {"bold": 1}, sc.get("src", sc["csv"]) if sc and it["head"] not in ("Entities", "Interactions") else "legend", "start"))
                y += 24 * S
                continue
            gh = 14 * S
            if it.get("edge") or it.get("evidence"):
                dash, hk, col = EDGE[it["edge"]] if it.get("edge") else (EVID[it["evidence"]], "none", "#555555")
                dash = dsc(dash)
                col = it.get("color", col)
                g1, en = head(i + "-glyphhead", hk, col, (lg["x"], y + 6 * S), (lg["x"] + 36 * S, y + 6 * S), S * 0.8)
                L["legend"].append('<line id="%s-glyph" x1="%s" y1="%s" x2="%.1f" y2="%s" stroke="%s" stroke-width="%.1f"%s/>' % (i, lg["x"], y + 6 * S, en[0], y + 6 * S, col, round(2 * max(min(S, 1.5), S * 0.85), 1),
                                   ' stroke-dasharray="%s"' % dash if dash else ""))
                L["legend"] += [g1] if g1 else []
            elif it.get("kind"):
                gh = 18 * S if it["kind"] == "gene" else 14 * S
                yy = y + (6 * S if it["kind"] == "gene" else 0)
                L["legend"] += [re.sub(r'id="[^"]*" ', "", s0, count=1) if k0 else s0 for k0, s0 in enumerate(shape(KSHAPE.get(it["kind"], "rect"), lg["x"], yy, 34 * S, 14 * S,
                                'id="%s-glyph" fill="#FFFFFF" stroke="#333333" stroke-width="%g"' % (i, round(1.2 * K, 1)), lg["x"] + 17 * S, yy + 7 * S))]
                y += gh - 14 * S + (6 * S if it["kind"] == "gene" else 0)
            elif it.get("mod"):
                L["legend"].append('<circle id="%s-glyph" cx="%.1f" cy="%.1f" r="%.1f" fill="#FFFFFF" stroke="#7B3294" stroke-width="%g"/>' % (i, lg["x"] + 17 * S, y + 6 * S, 10 * S, round(1.4 * K, 1)))
                L["legend"].append(txt(i + "-glyphtext", lg["x"] + 17 * S, y + 10 * S, [it["mod"]], fs1, {"bold": 1}, "legend", "middle", "#7B3294"))
                y += 4 * S
            else:
                L["legend"].append('<rect id="%s-glyph" x="%s" y="%s" width="%.1f" height="%.1f" fill="%s" stroke="%s"%s/>' % (
                    i, lg["x"], y, 30 * S, 13 * S, it["fill"], "#555555", ""))
            L["legend"].append(txt(i, lg["x"] + 44 * S, y + 11 * S, [it["label"]], fs1, {}, it.get("src", "legend"), "start"))
            cm["legend"].append({k: v for k, v in it.items() if k != "src"})
            xr = max(xr, lg["x"] + 44 * S + tw(str(it["label"]), fs1) + 4)
            y += step
        y = max(y, ymax)
        lb = (lx0 - 4, lg["y"] - 4, xr, y + 2)
        lg["x"] = lx0
        if cv.get("autosize"):
            W, H = max(W, int(lb[2] + 16)), int(lb[3] + 14) if gpos else max(H, int(lb[3] + 16))
        warn += ["edge %s crosses the legend box: re-route it (via) or move the legend" % e for e in sorted({s[0] for s in segs if any(inside(s[1] + (s[3] - s[1]) * f / 30.0, s[2] + (s[4] - s[2]) * f / 30.0, lb) for f in range(31))})]
        warn += ["legend runs past the canvas (right edge %.0f > w %s): widen canvas.w or move the legend" % (lb[2], W)] if lb[2] > W or y > H else []
        warn += ["node %s overlaps the legend box" % k for k, n in N.items() if n["cx"] + n["w"] / 2.0 > lb[0] and n["cx"] - n["w"] / 2.0 < lb[2] and n["cy"] + n["h"] / 2.0 > lb[1] and n["cy"] - n["h"] / 2.0 < lb[3]]
    elif sp.get("edges"):
        warn.append("no legend: add legend{x,y} (items are auto-filled from the edge types, evidence styles and colour scale used)")
    if cv.get("title"):
        tfs = cv.get("title_fs", 20 * S)
        tl = wrap(cv["title"], cv["title_w"] * 0.88, tfs, True) if cv.get("title_w") else [cv["title"]]
        L["text"].append(txt("figure-title", (PXL + cv["title_w"] / 2.0) if cv.get("title_w") else W / 2.0, (10 + 22 * S) if cv.get("title_w") else 34 * S, tl, tfs, {"bold": 1}, cv.get("src", ""), "middle"))
    wa, ha = ("%smm" % cv["width_mm"], "%.2fmm" % (cv["width_mm"] * H / float(W))) if cv.get("width_mm") else (W, H)  # physical size for journals
    fonts = {"min_px": round(min(FSUSED or [0]), 2)}
    if cv.get("width_mm"):
        fonts["min_pt"] = round(min(FSUSED or [0]) * cv["width_mm"] * 3.78 / float(W) * 0.75, 2)
        if cv.get("min_font_pt") and fonts["min_pt"] < float(cv["min_font_pt"]) - 0.05:
            warn.append("smallest text is %.1f pt at %s mm < min_font_pt %s: set canvas.fs_scale to %.2f (or use auto layout)" % (
                fonts["min_pt"], cv["width_mm"], cv["min_font_pt"], S * float(cv["min_font_pt"]) / fonts["min_pt"]))
    if nosrc:
        warn.append("no src for %d element(s): %s%s (add \"src\": where in the material each one comes from)" % (len(nosrc), ", ".join(nosrc[:8]), " ..." if len(nosrc) > 8 else ""))
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
