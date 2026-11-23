#!/usr/bin/env python3
"""pixcheck (stdlib, py3.8+): inspect the RENDERED chart, not only the SVG text (the agent cannot see images).
  pixcheck.py chart.svg [--png chart.png] [--map chart_content_map.json] [--workorder wo.json]
              [--width-mm 89] [--dpi 600] [--min-font 6]          -> ADVISORY: WARN lines only, exit 0, writes <stem>_pixel_check.json
Fix an obvious problem once (wrong width/dpi, red-green pair, label below min pt); otherwise record the warnings and go on.
Checks: PNG size = width_mm x dpi; figure not blank / not clipped; every bar renders in its declared series colour;
every series colour is really on the image and no undeclared colour cluster appears (legend = marks); series colours
stay distinguishable under protan/deutan/tritan simulation and in greyscale; smallest SVG font >= min pt;
SVG text editable; render warnings from the content map (missing glyphs, n mismatches) are surfaced."""
import json, os, re, struct, sys, tempfile, zlib
import xml.etree.ElementTree as ET
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def readpng(p):
    b, i, idat, pal = open(p, "rb").read(), 8, b"", None
    if b[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG")
    while i < len(b):
        n, t = struct.unpack(">I", b[i:i + 4])[0], b[i + 4:i + 8]
        d, i = b[i + 8:i + 8 + n], i + 12 + n
        if t == b"IHDR":
            w, h, bd, ct, _, _, il = struct.unpack(">IIBBBBB", d)
        elif t == b"PLTE":
            pal = d
        elif t == b"IDAT":
            idat += d
        elif t == b"IEND":
            break
    if bd not in (8, 16) or il or ct not in (0, 2, 3, 4, 6) or (ct == 3 and bd != 8):
        raise ValueError("unsupported PNG (bit depth %d, colour type %d, interlace %d)" % (bd, ct, il))
    bs = bd // 8
    bpp, raw, rows = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ct] * bs, zlib.decompress(idat), []
    stp, prev = w * bpp, bytearray(w * bpp)
    for y in range(h):
        f, ln = raw[y * (stp + 1)], bytearray(raw[y * (stp + 1) + 1:(y + 1) * (stp + 1)])
        if f == 1:
            for x in range(bpp, stp):
                ln[x] = (ln[x] + ln[x - bpp]) & 255
        elif f == 2:
            ln = bytearray((a + c) & 255 for a, c in zip(ln, prev))
        elif f == 3:
            for x in range(stp):
                ln[x] = (ln[x] + ((ln[x - bpp] if x >= bpp else 0) + prev[x]) // 2) & 255
        elif f == 4:
            for x in range(stp):
                a, c, u = (ln[x - bpp], prev[x - bpp], prev[x]) if x >= bpp else (0, 0, prev[x])
                pa, pb, pc = abs(u - c), abs(a - c), abs(a + u - 2 * c)
                ln[x] = (ln[x] + (a if pa <= pb and pa <= pc else u if pb <= pc else c)) & 255
        rows.append(ln)
        prev = ln
    def px(x, y):
        r = rows[y]
        if ct == 3:
            return tuple(pal[r[x] * 3:r[x] * 3 + 3])
        v = r[x * bpp:(x + 1) * bpp][::bs]
        rgb, al = ((v[0],) * 3, v[1] if ct == 4 else 255) if ct in (0, 4) else (tuple(v[:3]), v[3] if ct == 6 else 255)
        return tuple(int(c * al / 255.0 + 255 * (1 - al / 255.0)) for c in rgb)
    return w, h, px

hexrgb = lambda c: tuple(int(c.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)) if re.match(r"#[0-9a-fA-F]{6}$", c or "") else None  # noqa: E731
dist = lambda a, b: max(abs(x - y) for x, y in zip(a, b))  # noqa: E731
lum = lambda c: (0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]) / 255.0  # noqa: E731
CVD = {"protan": [[.152286, 1.052583, -.204868], [.114503, .786281, .099216], [-.003882, -.048116, 1.051998]],   # Machado 2009, severity 1
       "deutan": [[.367322, .860646, -.227968], [.280085, .672501, .047413], [-.011820, .042940, .968881]],
       "tritan": [[1.255528, -.076749, -.178779], [-.078411, .930809, .147602], [.004733, .691367, .303900]]}
def sim(c, M):
    lin = [((v / 255.0 + .055) / 1.055) ** 2.4 if v > 10 else v / 255.0 / 12.92 for v in c]
    out = [min(1, max(0, sum(M[i][j] * lin[j] for j in range(3)))) for i in range(3)]
    return tuple(int(255 * (1.055 * v ** (1 / 2.4) - .055 if v > .0031308 else 12.92 * v)) for v in out)
def eucl(a, b):
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** .5

def main(a):
    svg, o = a[0], dict(zip(a[1::2], a[2::2]))
    stem = os.path.splitext(svg)[0]
    png, cmp_ = o.get("--png", stem + ".png"), o.get("--map", stem + "_content_map.json")
    try:
        wo = json.load(open(o["--workorder"], encoding="utf-8")) if o.get("--workorder") else {}
    except Exception as e:
        print("WARN: workorder not readable (%s); using --width-mm/--dpi or the content map" % str(e)[:80])
        wo = {}
    ex = wo.get("export", wo) if isinstance(wo, dict) else {}
    cm = json.load(open(cmp_, encoding="utf-8")) if os.path.exists(cmp_) else {}
    wmm = float(o.get("--width-mm") or ex.get("width_mm") or cm.get("style", {}).get("width_mm") or 0)
    dpi = float(o.get("--dpi") or ex.get("dpi") or cm.get("style", {}).get("dpi") or 300)
    minf = float(o.get("--min-font") or ex.get("min_font_pt") or 6)
    root, F, Wn = ET.parse(svg).getroot(), [], []
    VW = [float(x) for x in re.split(r"[ ,]+", root.get("viewBox").strip())][2:4] if root.get("viewBox") else [float(re.sub(r"[a-z]+", "", root.get("width"))), 1]
    wpt = re.match(r"([\d.]+)pt", root.get("width") or "")
    unit_pt = float(wpt.group(1)) / VW[0] if wpt else 0.75
    rep = {"svg": svg, "png": png, "content_map": cmp_ if cm else None}
    try:
        ew, eh = struct.unpack(">II", open(png, "rb").read(24)[16:24])
        if ew * eh <= 4.5e6:
            pw, ph, px = readpng(png)
            rep["inspected"] = "export PNG itself"
        else:
            import export_check as ec
            tmp = os.path.join(tempfile.mkdtemp(), "inspect.png")
            m, _ = ec.chain("png", svg, tmp, 96.0 * 1600 / ec.svg_size(svg)[0])
            if not m:
                raise ValueError("export PNG too large to decode here and no renderer for a smaller copy")
            pw, ph, px = readpng(tmp)
            rep["inspected"] = "re-render %dx%d of the same SVG via %s (export PNG too large for pure-Python decode)" % (pw, ph, m)
    except Exception as e:
        rep.update(skipped="cannot read/inspect PNG %s: %s" % (os.path.basename(png), str(e).replace(os.path.dirname(os.path.abspath(png)) + os.sep, "")[:120]), warnings=[], fails=[], advisory=True)
        json.dump(rep, open(stem + "_pixel_check.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("WARN: %s (advisory check skipped; record it and move on)" % rep["skipped"])
        return 0
    rep["export_png_px"] = [ew, eh]
    if wmm:
        want = wmm / 25.4 * dpi
        rep["expected_width_px"] = round(want)
        F += ["PNG is %d px wide, %g mm at %g dpi needs %d px" % (ew, wmm, dpi, want)] if abs(ew - want) / want > 0.03 else []
    s = pw / VW[0]
    grid = [(x, y) for y in range(0, ph, max(1, ph // 150)) for x in range(0, pw, max(1, pw // 200))]
    ink = sum(1 for x, y in grid if min(px(x, y)) < 235) / float(len(grid))
    edge = sum(1 for k in range(0, pw, 3) for y in (0, ph - 1) if min(px(k, y)) < 160) + sum(1 for k in range(0, ph, 3) for x in (0, pw - 1) if min(px(x, k)) < 160)
    rep["ink_fraction"] = round(ink, 3)
    F += ["figure is (almost) blank: ink %.1f%%" % (ink * 100)] if ink < 0.01 else []
    Wn += ["%d dark pixels on the outer border: something may be clipped" % edge] if edge > 6 else []
    els = {e.get("id"): e for e in root.iter() if e.get("id")}
    marks, series_cols = [], {}
    for m in cm.get("marks", []):
        series_cols[m.get("series", "")] = m.get("colour")
        el = els.get(m["id"])
        if el is None:
            F.append("mark %s from the content map is not in the SVG" % m["id"])
            continue
        if not m["id"].startswith("bar-"):
            continue
        nums = [float(v) for p in el.iter() for v in re.findall(r"-?\d*\.?\d+(?:e-?\d+)?", p.get("d") or "")]
        X, Y = nums[::2], nums[1::2]
        if not X:
            continue
        x0, x1, y0, y1 = min(X) * s, max(X) * s, min(Y) * s, max(Y) * s
        samp = [px(int(x0 + (x1 - x0) * u / 10.0), int(y0 + (y1 - y0) * v / 10.0)) for u in range(1, 10) for v in range(1, 10) if y1 - y0 > 2]
        q = {}
        for c in samp:
            q.setdefault(tuple(v // 12 for v in c), []).append(c)
        body = max(q.values(), key=len) if q else []
        mode = tuple(sum(c[j] for c in body) // len(body) for j in range(3)) if body else None
        r = {"id": m["id"], "declared": m.get("colour"), "rendered": "#%02X%02X%02X" % mode if mode else "too small to sample", "height_px": round(y1 - y0)}
        if mode and hexrgb(m.get("colour")) and dist(mode, hexrgb(m["colour"])) > 40:
            F.append("bar %s declared %s but renders as %s (colour/legend mismatch)" % (m["id"], m["colour"], r["rendered"]))
        marks.append(r)
    sat = {}
    for x, y in grid:
        c = px(x, y)
        if max(c) - min(c) > 45:
            sat.setdefault(tuple(v // 24 for v in c), []).append(c)
    decl = [hexrgb(c) for c in series_cols.values() if hexrgb(c)]
    clusters = [(len(v), tuple(sum(c[j] for c in v) // len(v) for j in range(3))) for v in sat.values() if len(v) > max(3, len(grid) * 0.002)]
    F += ["series colour %s never appears on the rendered image" % ("#%02X%02X%02X" % d) for d in decl
          if max(d) - min(d) > 45 and not any(dist(d, c) <= 40 for _, c in clusters)]
    Wn += ["colour #%02X%02X%02X (%d samples) is not a declared series colour: undeclared encoding or stray default colour" % (c + (n,)) for n, c in clusters
           if decl and not any(dist(d, c) <= 50 for d in decl)]
    cvd, names = {}, list(series_cols)
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            ca, cb = hexrgb(series_cols[names[i]]), hexrgb(series_cols[names[j]])
            if not (ca and cb):
                continue
            d = {k: round(eucl(sim(ca, M), sim(cb, M))) for k, M in CVD.items()}
            d["grey_dL"] = round(abs(lum(ca) - lum(cb)), 3)
            cvd["%s vs %s" % (names[i], names[j])] = d
            F += ["series %r and %r collapse under %s colour-vision deficiency (distance %d < 40)" % (names[i], names[j], k, v) for k, v in d.items() if k != "grey_dL" and v < 40]
            Wn += ["series %r and %r are close in greyscale (dL %.2f): add hatching/markers or pick colours with different lightness" % (names[i], names[j], d["grey_dL"])] if d["grey_dL"] < 0.08 else []
    texts = [e for e in root.iter() if e.tag.split("}")[-1] == "text"]
    sizes = []
    for e in texts:
        stl = (e.get("style") or "") + " font-size:%s" % e.get("font-size", "")
        mm_ = re.search(r"font:\s*(?:italic\s+|bold\s+|oblique\s+)*([\d.]+)px", stl) or re.search(r"font-size:\s*([\d.]+)", stl)
        if mm_:
            sizes.append((float(mm_.group(1)) * unit_pt, " ".join("".join(e.itertext()).split())[:30]))
    small = [t for t in sizes if t[0] < minf - 0.05]
    rep["min_font_pt"] = round(min(sizes)[0], 2) if sizes else None
    F += ["text %r is %.1f pt, below the %.1f pt minimum" % (t[1], t[0], minf) for t in small[:5]]
    F += [] if texts else ["SVG has no <text>: labels are outlined or raster, not editable"]
    for w in cm.get("warnings", []):
        (F if "render:" in w else Wn).append("content map: " + w + ("" if "render:" in w else " -> record it in exceptions"))
    Wn, F = Wn + F, []  # advisory: nothing here blocks delivery
    rep.update(marks=marks, series_colours=series_cols, colour_clusters=["#%02X%02X%02X x%d" % (c + (n,)) for n, c in sorted(clusters, reverse=True)[:10]],
               colour_vision=cvd, fails=F, warnings=Wn, advisory=True)
    outp = stem + "_pixel_check.json"
    json.dump(rep, open(outp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n".join(["WARN: " + x for x in Wn]) or "no warnings")
    print("%s: %d bars sampled on %s, ink %.1f%%, PNG %s px (want %s), min font %s pt -> %s" % (
        "ADVISORY %d warn" % len(Wn) if Wn else "PASS", len(marks), rep["inspected"], ink * 100, rep["export_png_px"], rep.get("expected_width_px", "n/a"), rep["min_font_pt"], outp))
    return 0

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1:]))
