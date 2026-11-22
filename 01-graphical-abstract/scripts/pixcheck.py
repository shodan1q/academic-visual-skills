#!/usr/bin/env python3
"""pixcheck (stdlib, py3.8+): look at the RENDERED pixels of an SVG figure, not just the SVG text.
  pixcheck.py figure.svg [figure.png] [--workorder wo.json] [--dpi 300] [--min-font 6]
                                           -> prints PASS/FAIL lines, writes <stem>_pixel_check.json next to the SVG
Checks: export PNG size = width_mm x requested dpi; smallest text >= min pt at the printed width; figure not blank or clipped; every node's fill is rendered as declared and its label leaves
ink (not lost / not white-on-white); label-vs-fill contrast; every node colour has a legend swatch with the same rendered
colour (legend = figure); legend swatches distinguishable in greyscale; every edge colour/dash has a legend line.
Large PNGs are inspected through a ~1200 px re-render of the same SVG with the same renderer chain (export_check.chain)."""
import json, os, re, struct, sys, tempfile, zlib
import xml.etree.ElementTree as ET
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import export_check as ec  # noqa: E402

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
    st, prev = w * bpp, bytearray(w * bpp)
    for y in range(h):
        f, ln = raw[y * (st + 1)], bytearray(raw[y * (st + 1) + 1:(y + 1) * (st + 1)])
        if f == 1:
            for x in range(bpp, st):
                ln[x] = (ln[x] + ln[x - bpp]) & 255
        elif f == 2:
            ln = bytearray((a + c) & 255 for a, c in zip(ln, prev))
        elif f == 3:
            for x in range(st):
                ln[x] = (ln[x] + ((ln[x - bpp] if x >= bpp else 0) + prev[x]) // 2) & 255
        elif f == 4:
            for x in range(st):
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
rl = lambda c: sum(w * ((v / 255.0 + .055) / 1.055) ** 2.4 if v > 10 else w * v / 255.0 / 12.92 for w, v in zip((.2126, .7152, .0722), c))  # noqa: E731
lum = lambda c: (0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]) / 255.0  # noqa: E731

def boxes(root):
    out = []
    for el in root.iter():
        t, i = el.tag.split("}")[-1], el.get("id") or ""
        g = {k: float(el.get(k)) for k in ("x", "y", "width", "height", "cx", "cy", "rx", "ry") if el.get(k) and re.match(r"^[\d.]+$", el.get(k))}
        if t == "rect" and "width" in g:
            b = (g.get("x", 0), g.get("y", 0), g.get("x", 0) + g["width"], g.get("y", 0) + g["height"])
        elif t == "ellipse" and "rx" in g:
            b = (g["cx"] - g["rx"] * .7, g["cy"] - g["ry"] * .7, g["cx"] + g["rx"] * .7, g["cy"] + g["ry"] * .7)
        elif t == "polygon" and el.get("points"):
            v = [float(x) for x in re.split(r"[ ,]+", el.get("points").strip())]
            b = (min(v[::2]) + (max(v[::2]) - min(v[::2])) / 4, min(v[1::2]) + (max(v[1::2]) - min(v[1::2])) / 4, max(v[::2]) - (max(v[::2]) - min(v[::2])) / 4, max(v[1::2]) - (max(v[1::2]) - min(v[1::2])) / 4)
        else:
            continue
        out.append((i, t, b, el.get("fill")))
    return out

def main(a):
    svg, o = a[0], dict(zip([x for x in a[1:] if x.startswith("--")], [a[a.index(x) + 1] for x in a[1:] if x.startswith("--")]))
    pos = [x for i, x in enumerate(a[1:], 1) if not x.startswith("--") and not a[i - 1].startswith("--")]
    png = pos[0] if pos else os.path.splitext(svg)[0] + ".png"
    wo = json.load(open(o["--workorder"], encoding="utf-8")) if o.get("--workorder") else {}
    ex = {}
    for k, v in (wo.items() if isinstance(wo, dict) else []):  # export block may be nested anywhere one level down
        ex.update(v if isinstance(v, dict) and any(x in v for x in ("dpi", "width_mm", "min_font_pt")) else {})
    ex.update({k: v for k, v in (wo.items() if isinstance(wo, dict) else []) if k in ("dpi", "width_mm", "min_font_pt")})
    want_dpi, minf = float(o.get("--dpi") or ex.get("dpi") or 0), float(o.get("--min-font") or ex.get("min_font_pt") or 6)
    root, F, Wn, rep = ET.parse(svg).getroot(), [], [], {"svg": svg, "png": png}
    W, H = [float(x) for x in re.split(r"[ ,]+", root.get("viewBox").strip())][2:4] if root.get("viewBox") else ec.svg_size(svg)
    mm = re.match(r"([\d.]+)mm", root.get("width") or "")
    try:
        ew, eh = struct.unpack(">II", open(png, "rb").read(24)[16:24])
        pw, ph, px = readpng(png) if ew * eh <= 2.6e6 else (None, None, None)
        rep["export_png_px"], rep["export_dpi"] = [ew, eh], round(ew / (float(mm.group(1)) / 25.4)) if mm else "n/a (no width_mm)"
        if px is None:
            tmp = os.path.join(tempfile.mkdtemp(), "inspect.png")
            m, _ = ec.chain("png", svg, tmp, 96.0 * 1200 / ec.svg_size(svg)[0])
            pw, ph, px = readpng(tmp)
            rep["inspected"] = "re-render %dx%d via %s (export PNG too large to decode in pure Python)" % (pw, ph, m)
        else:
            rep["inspected"] = "export PNG itself"
    except Exception as e:
        print("FAIL: cannot read/inspect PNG %s: %s (run export_check.py render first)" % (png, e))
        return 1
    if mm and want_dpi:
        F += ["PNG is %d px wide; %s mm at %g dpi needs %d px (render with --dpi %g)" % (ew, mm.group(1), want_dpi, float(mm.group(1)) / 25.4 * want_dpi, want_dpi)] if ew < float(mm.group(1)) / 25.4 * want_dpi * 0.97 else []
    if ex.get("width_mm") and mm and abs(float(mm.group(1)) - float(ex["width_mm"])) > 1:
        F.append("SVG width is %s mm, the work order asks for %s mm (set canvas.width_mm)" % (mm.group(1), ex["width_mm"]))
    ptpu = (float(mm.group(1)) / W) / 25.4 * 72 if mm else 0.75  # points per SVG user unit at the printed width
    fsz = [(float(e.get("font-size")) * ptpu, " ".join("".join(e.itertext()).split())[:30]) for e in root.iter() if e.tag.endswith("text") and re.match(r"^[\d.]+$", e.get("font-size") or "")]
    rep["min_font_pt"] = round(min(fsz)[0], 2) if fsz else None
    F += ["text %r prints at %.1f pt, below %.1f pt (raise fs or reduce canvas.w)" % (t, f, minf) for f, t in sorted(fsz)[:5] if f < minf - 0.05]
    s = pw / W
    P = lambda x, y: px(min(pw - 1, max(0, int(x * s))), min(ph - 1, max(0, int(y * s))))  # noqa: E731
    grid = [(x, y) for y in range(0, ph, max(1, ph // 120)) for x in range(0, pw, max(1, pw // 160))]
    ink = sum(1 for x, y in grid if min(px(x, y)) < 235) / float(len(grid))
    edge = sum(1 for k in range(0, pw, 3) for y in (0, ph - 1) if min(px(k, y)) < 200) + sum(1 for k in range(0, ph, 3) for x in (0, pw - 1) if min(px(x, k)) < 200)
    rep["ink_fraction"] = round(ink, 3)
    F += ["figure is (almost) blank: ink %.1f%%" % (ink * 100)] if ink < 0.01 else []
    Wn += ["%d dark pixels on the outer border: something is clipped at the canvas edge" % edge] if edge > 6 else []
    nodes, legend = [], {}
    lay = {g.get("id"): g for g in root.iter() if (g.get("id") or "").startswith("layer-")}
    for i, t, b, fill in boxes(lay.get("layer-legend", root)):
        if i.endswith("-glyph") and hexrgb(fill):
            legend[i] = P((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)
    labels = {el.get("id"): " ".join("".join(el.itertext()).split()) for el in root.iter() if el.tag.endswith("text")}
    for i, t, b, fill in boxes(lay.get("layer-nodes", root)):
        dx, dy = (b[2] - b[0]) * .12, (b[3] - b[1]) * .12
        pts = [P(b[0] + dx + (b[2] - b[0] - 2 * dx) * u / 29.0, b[1] + dy + (b[3] - b[1] - 2 * dy) * v / 39.0) for u in range(30) for v in range(40)]  # dense: thin text lines
        q = {}
        for c in pts:
            k = tuple(x // 8 for x in c)
            q[k] = q.get(k, []) + [c]
        body = max(q.values(), key=len)
        mode = tuple(sum(c[j] for c in body) // len(body) for j in range(3))
        inkp = [c for c in pts if dist(c, mode) > 90]
        decl = hexrgb(fill)
        r = {"id": i, "label": labels.get(i + "-label", ""), "declared_fill": fill, "rendered_fill": "#%02X%02X%02X" % mode, "label_ink_px": len(inkp)}
        if decl and dist(decl, mode) > 40:
            F.append("node %s: declared fill %s but renders as %s" % (i, fill, r["rendered_fill"]))
        if r["label"] and not inkp:
            F.append("node %s: label %r leaves no visible ink (lost, clipped or same colour as fill)" % (i, r["label"]))
        elif inkp:
            ic = max(inkp, key=lambda c: abs(rl(c) - rl(mode)))
            cr = (max(rl(ic), rl(mode)) + .05) / (min(rl(ic), rl(mode)) + .05)  # WCAG contrast on linear luminance
            r["label_contrast"] = round(cr, 1)
            Wn += ["node %s: label contrast %.1f:1 is low (< 3)" % (i, cr)] if cr < 3 else []
        if legend and not any(dist(mode, c) <= 30 for c in legend.values()) and not (dist(mode, (255, 255, 255)) <= 12):
            Wn.append("node %s colour %s has no legend swatch of the same rendered colour (fine if the colour is decorative; else add a legend item)" % (i, r["rendered_fill"]))
        nodes.append(r)
    sw = sorted(legend.items(), key=lambda kv: lum(kv[1]))
    Wn += ["legend swatches %s and %s are hard to tell apart in greyscale" % (a[0], b[0]) for a, b in zip(sw, sw[1:]) if abs(lum(a[1]) - lum(b[1])) < 0.03 and dist(a[1], b[1]) > 30]
    sty = lambda el: (el.get("stroke"), el.get("stroke-dasharray") or "")  # noqa: E731
    lines = {sty(el) for el in lay.get("layer-legend", root).iter() if el.tag.endswith("line")}
    edges = {sty(el): el.get("id") for el in lay.get("layer-edges", root).iter() if el.tag.endswith("polyline")}
    F += ["edge style %s (e.g. %s) has no matching legend line" % (k, v) for k, v in edges.items() if lines and k not in lines and not any(k[1] and l[1] == k[1] for l in lines)]
    rep.update(nodes=nodes, legend_swatches={k: "#%02X%02X%02X" % v for k, v in legend.items()}, fails=F, warnings=Wn)
    outp = os.path.splitext(svg)[0] + "_pixel_check.json"
    json.dump(rep, open(outp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n".join(["WARN: " + x for x in Wn] + ["FAIL: " + x for x in F]))
    print("%s: %d nodes inspected on %s, ink %.1f%%, export %s px, dpi %s, min font %s pt -> %s" % ("FAIL" if F else "PASS", len(nodes), rep["inspected"], ink * 100, rep["export_png_px"], rep["export_dpi"], rep["min_font_pt"], outp))
    return 1 if F else 0

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1:]))
