#!/usr/bin/env python3
"""pixcheck (stdlib, py3.8+): look at the RENDERED pixels of a schematic figure, not just the SVG text.
  pixcheck.py figure.svg [figure.png]      -> advisory only: prints WARN lines (exit 0), writes <stem>_pixel_check.json next to the SVG
Checks: export PNG size/dpi; figure not blank or clipped; every node's fill is rendered as declared and its label leaves
ink (not lost / not white-on-white); label-vs-fill contrast; every node colour has a legend swatch with the same rendered
colour (legend = figure); legend swatches distinguishable in greyscale; every edge colour/dash has a legend line;
every arrow head / T-bar and every panel title is really in the image (direction and compartment names survive export).
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
lin = lambda v: v / 3294.6 if v <= 10 else ((v / 255.0 + 0.055) / 1.055) ** 2.4  # noqa: E731  (sRGB -> linear, WCAG)
lum = lambda c: 0.2126 * lin(c[0]) + 0.7152 * lin(c[1]) + 0.0722 * lin(c[2])  # noqa: E731

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
    svg = a[0]
    png = a[1] if len(a) > 1 else os.path.splitext(svg)[0] + ".png"
    root, F, Wn, rep = ET.parse(svg).getroot(), [], [], {"svg": svg, "png": png}
    W, H = [float(x) for x in re.split(r"[ ,]+", root.get("viewBox").strip())][2:4] if root.get("viewBox") else ec.svg_size(svg)
    mm = re.match(r"([\d.]+)mm", root.get("width") or "")
    try:
        ew, eh = struct.unpack(">II", open(png, "rb").read(24)[16:24])
        pw, ph, px = readpng(png) if ew * eh <= 1.5e6 else (None, None, None)
        rep["export_png_px"], rep["export_dpi"] = [ew, eh], round(ew / (float(mm.group(1)) / 25.4)) if mm else "n/a (no width_mm)"
        if px is None:
            tmp = os.path.join(tempfile.mkdtemp(), "inspect.png")
            m, _ = ec.chain("png", svg, tmp, 96.0 * 1200 / ec.svg_size(svg)[0])
            pw, ph, px = readpng(tmp)
            rep["inspected"] = "re-render %dx%d via %s (export PNG too large to decode in pure Python)" % (pw, ph, m)
        else:
            rep["inspected"] = "export PNG itself"
    except Exception as e:
        print("WARN: cannot read/inspect PNG %s: %s (advisory check skipped; record it and move on)" % (png, e))
        return 0
    s = pw / W
    P = lambda x, y: px(min(pw - 1, max(0, int(x * s))), min(ph - 1, max(0, int(y * s))))  # noqa: E731
    grid = [(x, y) for y in range(0, ph, max(1, ph // 120)) for x in range(0, pw, max(1, pw // 160))]
    ink = sum(1 for x, y in grid if min(px(x, y)) < 235) / float(len(grid))
    edge = sum(1 for k in range(0, pw, 3) for y in (0, ph - 1) if min(px(k, y)) < 200) + sum(1 for k in range(0, ph, 3) for x in (0, pw - 1) if min(px(x, k)) < 200)
    rep["ink_fraction"] = round(ink, 3)
    Wn += ["figure is (almost) blank: ink %.1f%%" % (ink * 100)] if ink < 0.01 else []
    Wn += ["%d dark pixels on the outer border: something is clipped at the canvas edge" % edge] if edge > 6 else []
    nodes, legend = [], {}
    lay = {g.get("id"): g for g in root.iter() if (g.get("id") or "").startswith("layer-")}
    for i, t, b, fill in boxes(lay.get("layer-legend", root)):
        if i.endswith("-glyph") and hexrgb(fill):
            legend[i] = P((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)
    labels = {el.get("id"): " ".join("".join(el.itertext()).split()) for el in root.iter() if el.tag.endswith("text")}
    for i, t, b, fill in boxes(lay.get("layer-nodes", root)):
        dx, dy = (b[2] - b[0]) * .12, (b[3] - b[1]) * .12
        pts = [P(b[0] + dx + (b[2] - b[0] - 2 * dx) * u / 14.0, b[1] + dy + (b[3] - b[1] - 2 * dy) * v / 8.0) for u in range(15) for v in range(9)]
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
            Wn.append("node %s: declared fill %s but renders as %s" % (i, fill, r["rendered_fill"]))
        if r["label"] and not inkp:
            Wn.append("node %s: label %r leaves no visible ink (lost, clipped or same colour as fill)" % (i, r["label"]))
        elif inkp:
            ic = max(inkp, key=lambda c: abs(lum(c) - lum(mode)))
            cr = (max(lum(ic), lum(mode)) + .05) / (min(lum(ic), lum(mode)) + .05)
            r["label_contrast"] = round(cr, 1)
            Wn += ["node %s: label contrast %.1f:1 is low (< 3)" % (i, cr)] if cr < 3 else []
        if legend and not any(dist(mode, c) <= 30 for c in legend.values()) and not (dist(mode, (255, 255, 255)) <= 12):
            Wn.append("node %s colour %s has no legend swatch of the same rendered colour" % (i, r["rendered_fill"]))
        nodes.append(r)
    sw = sorted(legend.items(), key=lambda kv: lum(kv[1]))
    Wn += ["legend swatches %s and %s are hard to tell apart in greyscale" % (a[0], b[0]) for a, b in zip(sw, sw[1:]) if abs(lum(a[1]) - lum(b[1])) < 0.03 and dist(a[1], b[1]) > 30]
    sty = lambda el: (el.get("stroke"), el.get("stroke-dasharray") or "")  # noqa: E731
    lines = {sty(el) for el in lay.get("layer-legend", root).iter() if el.tag.endswith("line")}
    edges = {sty(el): el.get("id") for el in lay.get("layer-edges", root).iter() if el.tag.endswith("polyline")}
    Wn += ["edge style %s (e.g. %s) has no matching legend line" % (k, v) for k, v in edges.items() if lines and k not in lines and not any(k[1] and l[1] == k[1] for l in lines)]
    # direction and naming must survive rendering: every arrow head / T-bar and every panel title has to leave ink
    heads, lost_h, lost_t = [el for el in root.iter() if el.get("data-head")], [], []
    for el in heads:
        v = [float(x) for x in re.findall(r"-?[\d.]+", el.get("points") or "")] or [float(el.get(k, 0)) for k in ("x1", "y1", "x2", "y2")] if not el.get("cx") else [float(el.get("cx")), float(el.get("cy"))]
        cx, cy, col = sum(v[::2]) / len(v[::2]), sum(v[1::2]) / len(v[1::2]), hexrgb(el.get("fill") if hexrgb(el.get("fill")) else el.get("stroke"))
        near = [P(cx + dx, cy + dy) for dx in (-3, -1.5, 0, 1.5, 3) for dy in (-3, -1.5, 0, 1.5, 3)]
        if col and not any(dist(c, col) <= 70 for c in near):
            lost_h.append(el.get("id"))
    Wn += ["arrow head / T-bar of %s is not in the rendered image (%d of %d lost): direction unreadable - this renderer dropped it; re-render with another one or report it" % (", ".join(lost_h[:6]), len(lost_h), len(heads))] if lost_h else []
    for el in root.iter():
        i, s_ = el.get("id") or "", " ".join("".join(el.itertext()).split())
        if el.tag.endswith("text") and (i.endswith("-title") or i == "figure-title") and s_ and el.get("x"):
            fs, x0, y0 = float(el.get("font-size", 14)), float(el.get("x")), float(el.get("y"))
            wd = len(s_) * fs * 0.58
            x0 -= wd / 2 if el.get("text-anchor") == "middle" else 0
            smp = [P(x0 + wd * u / 40.0, y0 - fs * v / 6.0) for u in range(41) for v in range(1, 5)]
            bg = max(set(smp), key=smp.count)
            if not any(dist(c, bg) > 90 for c in smp):
                lost_t.append("%s (%r)" % (i, s_[:30]))
    Wn += ["title text not visible in the rendered image: %s" % "; ".join(lost_t[:6])] if lost_t else []
    rep.update(arrow_heads={"declared": len(heads), "rendered": len(heads) - len(lost_h)}, titles_lost=lost_t)
    rep.update(nodes=nodes, legend_swatches={k: "#%02X%02X%02X" % v for k, v in legend.items()}, fails=F, warnings=Wn)
    outp = os.path.splitext(svg)[0] + "_pixel_check.json"
    json.dump(rep, open(outp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n".join(["WARN: " + x for x in Wn]) or "no warnings")
    print("%s: %d nodes inspected on %s, ink %.1f%%, export %s px, dpi %s -> %s" % ("ADVISORY %d warn" % len(Wn), len(nodes), rep["inspected"], ink * 100, rep["export_png_px"], rep["export_dpi"], outp))
    return 0

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1:]))
