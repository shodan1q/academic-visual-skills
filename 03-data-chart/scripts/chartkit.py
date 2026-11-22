#!/usr/bin/env python3
"""chartkit (stdlib, py3.8+): source tables -> chart marks -> back-check.
  table data.xlsx|data.csv [--out DIR] [--rows 40]   print cells with Excel refs (Sheet!B3 / CSV row numbers);
                                                     xlsx sheets are also saved as DIR/<stem>__<sheet>.csv
  marks fig.svg expected.csv [--log]                 data-to-mark check: re-read mark geometry from the SVG by id
                                                     (matplotlib gid or own id); expected.csv columns id,value
                                                     (value "a;b;c" for a series; err-* = full error-bar span);
                                                     calibrated from the y tick labels in the same SVG
                                                     (else fitted); FAIL if off by > 1 % of the axis; writes <svg stem>_mark_check.json
  svgchart spec.json out.svg                         fallback bar/line/scatter SVG when matplotlib is missing
  diff old.svg new.svg                               element-level change log of an edit
svgchart spec: {w,h,type:bar|line|scatter,title,xlabel,ylabel,ymin,ymax,categories[...],
  series[{name,color,y[...],x[...](line/scatter),err[...],src}]}"""
import csv, json, math, os, re, sys, zipfile
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape
M = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
OKABE = ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#56B4E9", "#D55E00", "#F0E442", "#000000"]
FONT = "Arial, Helvetica, 'Noto Sans CJK SC', 'Source Han Sans SC', 'WenQuanYi Micro Hei', 'PingFang SC', sans-serif"

def col2n(s):
    return sum((ord(c) - 64) * 26 ** i for i, c in enumerate(reversed(s)))

def table(a):
    p, o = a[0], dict(zip(a[1::2], a[2::2]))
    nrows, outd = int(o.get("--rows", 40)), o.get("--out", os.environ.get("WORK_DIR", "."))
    if not p.lower().endswith((".xlsx", ".xlsm")):
        for i, r in enumerate(csv.reader(open(p, encoding="utf-8-sig", errors="replace")), 1):
            print("row %d: %s" % (i, r)) if i <= nrows else None
        return
    z = zipfile.ZipFile(p)
    ss = ["".join(t.text or "" for t in si.iter(M + "t")) for si in ET.fromstring(z.read("xl/sharedStrings.xml")).iter(M + "si")] if "xl/sharedStrings.xml" in z.namelist() else []
    rel = {r.get("Id"): r.get("Target") for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))}
    for sh in ET.fromstring(z.read("xl/workbook.xml")).iter(M + "sheet"):
        t = rel[sh.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")].lstrip("/")
        cells, nf = {}, 0
        for c in ET.fromstring(z.read(t if t.startswith("xl/") else "xl/" + t)).iter(M + "c"):
            v, ty = c.find(M + "v"), c.get("t")
            nf += c.find(M + "f") is not None
            cells[c.get("r")] = ss[int(v.text)] if ty == "s" and v is not None else "".join(x.text or "" for x in c.iter(M + "t")) if ty == "inlineStr" else (v.text if v is not None else "")
        refs = [re.match(r"([A-Z]+)(\d+)", r).groups() for r in cells]
        mr, mc = max([int(r) for _, r in refs] or [0]), max([col2n(c) for c, _ in refs] or [0])
        grid = [[cells.get("%s%d" % (_ref(k), r), "") for k in range(mc)] for r in range(1, mr + 1)]
        out = os.path.join(outd, "%s__%s.csv" % (os.path.splitext(os.path.basename(p))[0], re.sub(r"\W+", "_", sh.get("name"))))
        csv.writer(open(out, "w", newline="", encoding="utf-8")).writerows(grid)
        print("== sheet %r: %d rows x %d cols, %d formula cell(s) (cached values shown) -> %s" % (sh.get("name"), mr, mc, nf, out))
        for i, r in enumerate(grid[:nrows], 1):
            print("%s!row %d: %s" % (sh.get("name"), i, r))

def _ref(k):
    s, k = "", k + 1
    while k:
        k, r = divmod(k - 1, 26)
        s = chr(65 + r) + s
    return s

def prims(el):
    """list of point lists, one per drawn primitive below el."""
    out = []
    for e in el.iter():
        t, g = e.tag.split("}")[-1], lambda k: float(e.get(k) or 0)
        if t == "rect":
            out.append([(g("x"), g("y")), (g("x") + g("width"), g("y") + g("height"))])
        elif t in ("use", "circle", "ellipse"):
            out.append([(g("x") or g("cx"), g("y") or g("cy"))])
        elif t == "line":
            out.append([(g("x1"), g("y1")), (g("x2"), g("y2"))])
        elif t in ("path", "polyline", "polygon"):
            n = [float(x) for x in re.findall(r"-?\d*\.?\d+(?:e-?\d+)?", e.get("d") or e.get("points") or "")]
            out.append(list(zip(n[::2], n[1::2])))
    return [p for p in out if p]

def marks(a):
    root, log = ET.parse(a[0]).getroot(), "--log" in a
    els = {e.get("id"): e for e in root.iter() if e.get("id")}
    S, rep = [], []
    for row in csv.DictReader(open(a[1], encoding="utf-8-sig")):
        i, vals = row["id"], [float(v) for v in str(row["value"]).split(";") if v.strip()]
        if i not in els:
            rep.append([i, "MISSING id in SVG"])
            continue
        P = prims(els[i])
        pts = [p[0] for p in P if len(p) == 1]
        if len(vals) == 1:
            ys = [y for p in P for _, y in p]
            barlike = i.startswith("err") or any(len(p) >= 4 for p in P) or any(e.tag.endswith("rect") for e in els[i].iter())  # error bar: span = upper - lower
            S.append((i, 0, vals[0], max(ys) - min(ys) if barlike else -sum(ys) / len(ys), "length" if barlike else "position"))
        else:
            seq = [-y for _, y in pts] if len(pts) == len(vals) else next(([-y for _, y in p] for p in P if len(p) == len(vals)), None)
            if seq is None:
                rep.append([i, "cannot match %d values to %d primitives" % (len(vals), len(P))])
                continue
            S += [(i, k, v, m, "position") for k, (v, m) in enumerate(zip(vals, seq))]
    cal = []  # axis calibration from the y tick labels drawn in the same SVG (matplotlib ytick_N groups)
    for e in root.iter():
        if re.match(r"ytick_\d+$", e.get("id") or "") and not log:
            t = "".join("".join(x.itertext()) for x in e.iter() if x.tag.endswith("text")).strip().replace("\u2212", "-")
            u = [p[0] for p in prims(e) if len(p) == 1]
            if u and re.match(r"^-?[\d.]+(e-?\d+)?$", t):
                cal.append((float(t), -u[0][1]))
    if len(cal) >= 2:
        mx, my = sum(c[0] for c in cal) / len(cal), sum(c[1] for c in cal) / len(cal)
        b = sum((x - mx) * (y - my) for x, y in cal) / (sum((x - mx) ** 2 for x, _ in cal) or 1)
        a0, span, how = my - b * mx, (max(c[1] for c in cal) - min(c[1] for c in cal)) or 1, "y-axis ticks %s" % [c[0] for c in cal]
    for kind in sorted({s[4] for s in S}):
        G = [s for s in S if s[4] == kind]
        X, Y = [math.log10(v) if log else v for _, _, v, _, _ in G], [m for _, _, _, m, _ in G]
        if len(cal) < 2:  # no readable ticks: fit (positions with intercept, lengths through the origin)
            if len(G) < 2:
                rep.append([G[0][0], "only one %s mark and no readable axis ticks: cannot calibrate" % kind])
                continue
            mx, my = sum(X) / len(X), sum(Y) / len(Y)
            b = sum((x - mx) * (y - my) for x, y in zip(X, Y)) / (sum((x - mx) ** 2 for x in X) or 1) if kind == "position" else sum(x * y for x, y in zip(X, Y)) / (sum(x * x for x in X) or 1)
            a0, span, how = my - b * mx, (max(Y) - min(Y)) or 1, "least-squares fit (weaker: one wrong high-leverage mark can be absorbed)"
        for (i, k, v, m, _), x in zip(G, X):
            err = abs((a0 if kind == "position" else 0) + b * x - m) / span
            rep.append([i if not k else "%s[%d]" % (i, k), "%s: value %g -> %.2f px, residual %.2f%% of axis %s" % (kind, v, m, 100 * err, "OK" if err <= 0.01 else "MISMATCH")])
        rep.append(["scale(%s)" % kind, "%.4f px per unit from %s (%s)" % (b, how, "OK" if b > 0 else "NEGATIVE: axis inverted or wrong marks")])
    print("\n".join("%s: %s" % tuple(r) for r in rep))
    bad = [r for r in rep if "MISMATCH" in r[1] or "MISSING" in r[1] or "NEGATIVE" in r[1] or "cannot" in r[1]]
    verdict = "FAIL" if bad or len(S) < 2 else "PASS"
    print("%s: %d mark sample(s), %d problem(s)" % (verdict, len(S), len(bad)))
    json.dump({"svg": a[0], "expected": a[1], "verdict": verdict, "samples": len(S), "problems": ["%s: %s" % tuple(r) for r in bad],
               "lines": ["%s: %s" % tuple(r) for r in rep]}, open(os.path.splitext(a[0])[0] + "_mark_check.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return 1 if verdict == "FAIL" else 0

def nice(lo, hi):
    st = 10 ** math.floor(math.log10((hi - lo) / 5 or 1))
    st *= next(m for m in (1, 2, 5, 10) if (hi - lo) / (st * m) <= 6)
    return [math.floor(lo / st) * st + k * st for k in range(int((math.ceil(hi / st) - math.floor(lo / st))) + 1)]

def svgchart(a):
    s = json.load(open(a[0], encoding="utf-8"))
    W, H, ty, ser, cats = s.get("w", 640), s.get("h", 420), s.get("type", "bar"), s["series"], s.get("categories", [])
    L, R, T, B = 80, 30 + (130 if len(ser) > 1 else 0), 50, 70
    allv = [y + e for se in ser for y, e in zip(se["y"], se.get("err") or [0] * len(se["y"]))] + [y - e for se in ser for y, e in zip(se["y"], se.get("err") or [0] * len(se["y"]))]
    ticks = nice(min(s.get("ymin", 0 if ty == "bar" else min(allv)), min(allv)), max(s.get("ymax", max(allv)), max(allv)))
    lo, hi = ticks[0], ticks[-1]
    Y = lambda v: T + (H - T - B) * (hi - v) / ((hi - lo) or 1)  # noqa: E731
    xs = [x for se in ser for x in se.get("x", [])]
    X = (lambda v: L + (W - L - R) * (v - min(xs)) / ((max(xs) - min(xs)) or 1)) if ty != "bar" else None  # noqa: E731
    g = ['<line id="axis-y" x1="%d" y1="%d" x2="%d" y2="%d" stroke="#000"/>' % (L, T, L, H - B), '<line id="axis-x" x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="#000"/>' % (L, Y(max(lo, 0)) if ty == "bar" else H - B, W - R, Y(max(lo, 0)) if ty == "bar" else H - B)]
    g += ['<text id="ytick-%d" x="%d" y="%.1f" font-size="12" text-anchor="end">%g</text><line x1="%d" x2="%d" y1="%.1f" y2="%.1f" stroke="#000"/>' % (k, L - 8, Y(v) + 4, round(v, 10), L - 5, L, Y(v), Y(v)) for k, v in enumerate(ticks)]
    n, bw = max(len(se["y"]) for se in ser), (W - L - R) / max(1, max(len(se["y"]) for se in ser)) * 0.8 / len(ser)
    for j, se in enumerate(ser):
        c, sid, err = se.get("color", OKABE[j % 8]), re.sub(r"\W+", "_", str(se["name"])), se.get("err") or [0] * len(se["y"])
        pts = []
        for k, v in enumerate(se["y"]):
            if ty == "bar":
                cx = L + (W - L - R) * (k + 0.5) / n + (j - (len(ser) - 1) / 2.0) * bw
                y0, y1 = sorted((Y(v), Y(max(lo, 0))))
                g.append('<rect id="mark-%s-%d" x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s" data-value="%s" data-src="%s"/>' % (sid, k, cx - bw / 2, y0, bw * 0.95, y1 - y0, c, v, escape(se.get("src", ""))))
            else:
                cx = X(se["x"][k])
                pts.append("%.1f,%.1f" % (cx, Y(v)))
                g.append('<circle id="mark-%s-%d" cx="%.1f" cy="%.1f" r="4" fill="%s" data-value="%s" data-src="%s"/>' % (sid, k, cx, Y(v), c, v, escape(se.get("src", ""))))
            if err[k]:
                g.append('<path id="err-%s-%d" d="M%.1f,%.1f V%.1f M%.1f,%.1f h8 M%.1f,%.1f h8" stroke="#222" fill="none" data-value="%s"/>' % (sid, k, cx, Y(v - err[k]), Y(v + err[k]), cx - 4, Y(v + err[k]), cx - 4, Y(v - err[k]), err[k]))
        if ty == "line":
            g.insert(2, '<polyline id="line-%s" points="%s" fill="none" stroke="%s" stroke-width="2"/>' % (sid, " ".join(pts), c))
        if len(ser) > 1:
            g.append('<rect id="legend-%s-glyph" x="%d" y="%d" width="14" height="14" fill="%s"/><text id="legend-%s" x="%d" y="%d" font-size="12">%s</text>' % (sid, W - R + 15, T + 22 * j, c, sid, W - R + 35, T + 22 * j + 12, escape(str(se["name"]))))
    if ty == "bar":
        g += ['<text id="xcat-%d" x="%.1f" y="%d" font-size="12" text-anchor="middle">%s</text>' % (k, L + (W - L - R) * (k + 0.5) / n, H - B + 18, escape(str(c))) for k, c in enumerate(cats)]
    else:
        g += ['<text id="xtick-%d" x="%.1f" y="%d" font-size="12" text-anchor="middle">%g</text>' % (k, X(v), H - B + 18, round(v, 10)) for k, v in enumerate(nice(min(xs), max(xs))) if min(xs) <= v <= max(xs)]
    g += ['<text id="xlabel" x="%.1f" y="%d" font-size="14" text-anchor="middle">%s</text>' % ((L + W - R) / 2.0, H - 20, escape(s.get("xlabel", ""))),
          '<text id="ylabel" transform="translate(22,%.1f) rotate(-90)" font-size="14" text-anchor="middle">%s</text>' % ((T + H - B) / 2.0, escape(s.get("ylabel", ""))),
          '<text id="title" x="%.1f" y="28" font-size="16" font-weight="bold" text-anchor="middle">%s</text>' % (W / 2.0, escape(s.get("title", "")))]
    open(a[1], "w", encoding="utf-8").write('<?xml version="1.0" encoding="UTF-8"?>\n<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d" font-family="%s">\n<rect id="background" width="100%%" height="100%%" fill="#FFFFFF"/>\n<g id="layer-chart">\n%s\n</g>\n</svg>\n' % (W, H, W, H, FONT.replace('"', ""), "\n".join(g)))
    print("wrote %s; marks have ids mark-<series>-<i> with data-value -> verify with: chartkit.py marks" % a[1])

HASH = re.compile(r"^[mp][0-9a-f]{8,}$")
def index(path):  # each id'd element -> (tag, its visible text, style/geometry attrs of its subtree); hashed mpl ids are noise
    out = {}
    for el in ET.parse(path).getroot().iter():
        i = el.get("id")
        if not i or HASH.match(i):
            continue
        txt = " ".join("".join(el.itertext()).split()) if any(e.tag.endswith("text") for e in el.iter()) else ""
        att = {}
        for k, e in enumerate(el.iter()):
            for at in ("fill", "stroke", "style", "d", "x", "y", "width", "height", "transform", "font-size", "points"):
                if e.get(at) is not None:
                    att["%s%s" % (at, "" if not k else "@%d" % k)] = re.sub(r"url\(#[^)]*\)", "", e.get(at))
        out[i] = (el.tag.split("}")[-1], txt, att, {e.get("id") for e in el.iter() if e is not el and e.get("id")})
    return out

def diff(a):
    o, n = index(a[0]), index(a[1])
    ch = [{"id": k, "change": "removed"} for k in o if k not in n] + [{"id": k, "change": "added"} for k in n if k not in o]
    chg = {k for k in o if k in n and o[k][:3] != n[k][:3]}
    for k in (k for k in chg if not (o[k][3] & chg)):  # report the innermost changed element, not its containers
        ch += [{"id": k, "change": "text", "before": o[k][1], "after": n[k][1]}] if o[k][1] != n[k][1] else []
        if o[k][1] == n[k][1] or not o[k][1]:
            ch += [{"id": k, "change": at, "before": o[k][2].get(at), "after": n[k][2].get(at)} for at in sorted(set(o[k][2]) | set(n[k][2])) if o[k][2].get(at) != n[k][2].get(at)][:3]
    print(json.dumps({"old": a[0], "new": a[1], "kept_ids": len(set(o) & set(n)), "changed_ids": sorted({c["id"] for c in ch}), "changes": ch[:40]}, ensure_ascii=False, indent=1))

CMDS = {"table": table, "marks": marks, "svgchart": svgchart, "diff": diff}
if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] not in CMDS:
        print(__doc__)
        sys.exit(2)
    sys.exit(CMDS[sys.argv[1]](sys.argv[2:]) or 0)
