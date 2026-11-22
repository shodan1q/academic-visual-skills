#!/usr/bin/env python3
"""Editable chart source (template from source-data-chart-lite). Copy to /app/output/make_chart.py and put this chart's
choices in chart_config.json next to it (same keys as CONFIG; dict keys merge) - no Python editing needed.
  python3 make_chart.py [stem] [override.json]   -> <stem>.svg/.pdf/.png, <stem>_marks_expected.csv,
  <stem>_content_map.json, <stem>_caption.md, appends export_log.jsonl. An override JSON (dict keys merge) is the
  source-preserving edit: the same script + data + a small recorded change. Values come only from CONFIG["data"]."""
import csv, hashlib, json, math, os, statistics as st, sys, warnings
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager as fm  # noqa: E402
HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = {
    "data": "chart_data.csv",            # verbatim copy of the source table (same columns, same row order)
    "data_origin": "/input/data/SOURCE.csv",  # where the copy came from (sha256 of both is recorded)
    "kind": "bar",                       # bar (grouped, optional points) | line (numeric x) | scatter (raw points)
    "x": "X_COLUMN", "x_order": [], "x_labels": {},      # x_order empty = order of first appearance
    "series": "", "series_order": [], "series_labels": {},  # "" = single series (no legend)
    "y": "VALUE_COLUMN", "id_col": "",   # id_col: sample id column, copied into the content map
    "error": "sem",                      # sem | sd | ci95 | none : must be what the source legend says
    "points": True,                      # draw every replicate
    "ylabel": "Quantity (unit)", "xlabel": "", "ylog": False, "ylim": None, "legend_loc": "upper left",
    "colors": {},                        # {series value: "#hex"}; default Okabe-Ito (colour-blind safe)
    "width_mm": 89, "height_mm": 65, "dpi": 600, "font_pt": 7, "line_pt": 0.75,
    "font": ["Arial", "Liberation Sans", "Helvetica", "DejaVu Sans"],
    "sig": [],                           # [{"a": [x, series], "b": [x, series], "label": "***", "src": "paper.pdf p.N legend"}]
    "n_declared": None,                  # n per group stated in the source (int) -> mismatches are reported
    "caption": "",                       # legend text taken from the source; n per group is appended automatically
    "src": {},                           # provenance of every annotation: {"ylabel": "paper.pdf p.3 Fig.3b legend", ...}
}
OKABE = ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#56B4E9", "#D55E00", "#F0E442", "#000000"]
stem = os.path.join(HERE, sys.argv[1] if len(sys.argv) > 1 else "chart")
for layer in [os.path.join(HERE, "chart_config.json")] + sys.argv[2:3]:   # base config, then the edit override
    if os.path.exists(layer):
        for k, v in json.load(open(layer, encoding="utf-8")).items():
            if k not in CONFIG:
                print("WARN: unknown config key %r ignored" % k)
            CONFIG[k] = dict(CONFIG[k], **v) if isinstance(CONFIG.get(k), dict) and isinstance(v, dict) else v
C = CONFIG
sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest() if os.path.exists(p) else None  # noqa: E731
have = {f.name for f in fm.fontManager.ttflist}
cjk = [f for f in ("Noto Sans CJK SC", "Source Han Sans SC", "WenQuanYi Micro Hei", "SimHei", "Microsoft YaHei", "PingFang SC", "Arial Unicode MS") if f in have]
fonts = [f for f in C["font"] if f in have] + cjk[:1] + ["DejaVu Sans"]
plt.rcParams.update({"svg.fonttype": "none", "pdf.fonttype": 42, "svg.hashsalt": "chart", "font.family": "sans-serif",
                     "font.sans-serif": fonts, "font.size": C["font_pt"], "axes.linewidth": C["line_pt"], "axes.unicode_minus": False,
                     "mathtext.fontset": "custom", "mathtext.it": fonts[0] + ":italic", "mathtext.rm": fonts[0],
                     "mathtext.bf": fonts[0] + ":bold", "mathtext.sf": fonts[0], "mathtext.cal": fonts[0], "mathtext.tt": fonts[0]})
rows = list(csv.DictReader(open(os.path.join(HERE, C["data"]), encoding="utf-8-sig")))
for need in [C["x"], C["y"]] + ([C["series"]] if C["series"] else []):
    if rows and need not in rows[0]:
        sys.exit("column %r not in %s (columns: %s)" % (need, C["data"], list(rows[0])))
def num(v):
    try:
        f = float(v)
        return f if math.isfinite(f) else None
    except (TypeError, ValueError):
        return None
xs = C["x_order"] or list(dict.fromkeys(r[C["x"]] for r in rows))
ss = (C["series_order"] or list(dict.fromkeys(r[C["series"]] for r in rows))) if C["series"] else [""]
cells, excluded = {}, []
for i, r in enumerate(rows, 2):  # row 1 = header, so row numbers match the CSV file lines
    key = (r[C["x"]], r[C["series"]] if C["series"] else "")
    if key[0] not in xs or key[1] not in ss:
        continue
    v = num(r[C["y"]])
    if v is None:
        excluded.append({"row": i, "id": r.get(C["id_col"], ""), "cell": [key[0], key[1]], "raw": r[C["y"]], "reason": "empty or non-numeric value"})
        continue
    cells.setdefault(key, []).append((i, r.get(C["id_col"], ""), v))
def stats(vals):
    n, m = len(vals), st.mean(vals)
    sd = st.stdev(vals) if n > 1 else 0.0
    e = {"sd": sd, "sem": sd / math.sqrt(n), "ci95": 1.96 * sd / math.sqrt(n), "none": 0.0}[C["error"]]  # ci95: normal approx
    return n, m, sd, e
col = {s: C["colors"].get(s, OKABE[k % 8]) for k, s in enumerate(ss)}
lab = lambda d, v: d.get(v, v)  # noqa: E731
fig, ax = plt.subplots(figsize=(C["width_mm"] / 25.4, C["height_mm"] / 25.4))
marks, expected, warn, top = [], [], [], {}
w = 0.8 / len(ss)
with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always")
    for j, s in enumerate(ss):
        line = []
        for g, xv in enumerate(xs):
            if (xv, s) not in cells:
                warn.append("no numeric rows for x=%r series=%r" % (xv, s))
                continue
            pts = cells[(xv, s)]
            n, m, sd, e = stats([p[2] for p in pts])
            if C["n_declared"] and n != int(C["n_declared"]):
                warn.append("n mismatch: x=%r series=%r has n=%d usable rows, source states n=%s" % (xv, s, n, C["n_declared"]))
            pos = (g + (j - (len(ss) - 1) / 2.0) * w) if C["kind"] == "bar" else num(xv)
            mid = "%d-%d" % (g, j)
            if C["kind"] == "bar":
                ax.bar([pos], [m], width=w * 0.9, color=col[s], edgecolor="black", linewidth=C["line_pt"], gid="bar-" + mid, zorder=2,
                       label=lab(C["series_labels"], s) if g == 0 and s else None)
                expected.append(("bar-" + mid, m))
            else:
                line.append((pos, m))
            if C["kind"] != "scatter" and e > 0:
                ec, cw = ("black", w * 0.15) if C["kind"] == "bar" else (col[s], 0.012 * ((max(num(v) for v in xs) - min(num(v) for v in xs)) or 1))
                ax.vlines([pos], [m - e], [m + e], colors=ec, linewidth=C["line_pt"], gid="err-" + mid, zorder=4)
                ax.hlines([m - e, m + e], [pos - cw] * 2, [pos + cw] * 2, colors=ec, linewidth=C["line_pt"], gid="cap-" + mid, zorder=4)
                expected.append(("err-" + mid, 2 * e)) if not C["ylog"] else None
            if C["points"] or C["kind"] == "scatter":
                jit = [pos + (k - (n - 1) / 2.0) * min(w * 0.5 / max(n, 1), 0.04) for k in range(n)] if C["kind"] == "bar" else [pos] * n
                ax.scatter(jit, [p[2] for p in pts], s=6, color="black" if C["kind"] == "bar" else col[s], linewidths=0, zorder=5, gid="pts-" + mid,
                           label=lab(C["series_labels"], s) if C["kind"] == "scatter" and g == 0 and s else None)
                expected.append(("pts-" + mid, ";".join(repr(p[2]) for p in pts)))
            top[(xv, s)] = (pos, max([m + e] + [p[2] for p in pts]))
            mk_id = "bar-" + mid if C["kind"] == "bar" else "pts-" + mid if (C["points"] or C["kind"] == "scatter") else "line-%d" % j
            marks.append({"id": mk_id, "x": xv, "series": s, "colour": col[s], "mean": m, "sd": sd,
                          "error_type": C["error"], "error_halfwidth": e, "n": n, "csv_rows": [p[0] for p in pts], "sample_ids": [p[1] for p in pts],
                          "values": [p[2] for p in pts], "point_id": "pts-" + mid if (C["points"] or C["kind"] == "scatter") else None, "error_id": "err-" + mid if e > 0 and C["kind"] != "scatter" else None})
        if C["kind"] == "line" and line:
            ax.plot([p[0] for p in line], [p[1] for p in line], color=col[s], linewidth=1.0, marker="o", markersize=3, gid="line-%d" % j, label=lab(C["series_labels"], s) or None, zorder=3)
            expected.append(("line-%d" % j, ";".join(repr(p[1]) for p in line)))
    ymax = max(v for _, v in top.values()) if top else 1
    for k, sg in enumerate(C["sig"]):
        a, b = top.get(tuple(sg["a"])), top.get(tuple(sg["b"]))
        if not (a and b):
            warn.append("significance %r refers to a missing cell %r / %r" % (sg.get("label"), sg["a"], sg["b"]))
            continue
        y, h = max(a[1], b[1]) + ymax * (0.06 + 0.09 * k), ymax * 0.025
        ax.plot([a[0], a[0], b[0], b[0]], [y - h, y, y, y - h], color="black", linewidth=C["line_pt"], gid="sig-%d" % k)
        ax.text((a[0] + b[0]) / 2.0, y + h * 0.3, sg["label"], ha="center", va="bottom", gid="sigtext-%d" % k)
    if C["kind"] == "bar":
        ax.set_xticks(range(len(xs)))
        ax.set_xticklabels([lab(C["x_labels"], x) for x in xs])
        ax.set_ylim(0, ymax * (1.15 + 0.09 * len(C["sig"])))
    if C["ylog"]:
        ax.set_yscale("log")
    if C["ylim"]:
        ax.set_ylim(*C["ylim"])
    ax.set_ylabel(C["ylabel"], gid="ylabel")
    ax.set_xlabel(C["xlabel"], gid="xlabel")
    ax.set_gid("axes")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(width=C["line_pt"])
    if C["series"]:
        ax.legend(frameon=False, loc=C["legend_loc"], handlelength=1.0).set_gid("legend")
    fig.tight_layout(pad=0.4)
    for ext in ("svg", "pdf", "png"):
        fig.savefig(stem + "." + ext, dpi=C["dpi"], metadata={"Date": None} if ext == "svg" else ({"CreationDate": None} if ext == "pdf" else None))
warn += ["render: %s" % c.message for c in caught if "Glyph" in str(c.message) or "findfont" in str(c.message)]
with open(stem + "_marks_expected.csv", "w", encoding="utf-8") as f:  # expected values come from the data, never from the drawing
    f.write("id,value\n" + "".join("%s,%s\n" % (i, v) for i, v in expected))
nline = "; ".join("%s / %s: n = %d" % (m["x"], m["series"] or "-", m["n"]) for m in marks)  # raw source values (no mathtext) in the caption
cap = (C["caption"].strip() + " " if C["caption"] else "") + "Error bars: %s. n per group (usable rows in %s): %s." % (
    {"sem": "mean ± s.e.m", "sd": "mean ± s.d", "ci95": "mean ± 95% CI (normal approx.)", "none": "none"}[C["error"]], os.path.basename(C["data"]), nline)
cap += (" Excluded rows: " + "; ".join("row %d %s (%s)" % (e["row"], e["id"], e["reason"]) for e in excluded) + ".") if excluded else ""
open(stem + "_caption.md", "w", encoding="utf-8").write(cap + "\n")
cm = {"chart": os.path.basename(stem), "kind": C["kind"], "data": {"file": C["data"], "sha256": sha(os.path.join(HERE, C["data"])),
      "origin": C["data_origin"], "origin_sha256": sha(C["data_origin"]), "columns": {"x": C["x"], "series": C["series"], "y": C["y"], "id": C["id_col"]}},
      "marks": marks, "excluded_rows": excluded, "legend": [{"series": s, "label": lab(C["series_labels"], s), "colour": col[s]} for s in ss if s],
      "annotations": [{"what": k, "text": C.get(k) if k in C else k, "src": v} for k, v in C["src"].items()] +
                     [{"what": "significance", "text": sg["label"], "between": [sg["a"], sg["b"]], "src": sg.get("src", "")} for sg in C["sig"]],
      "caption": cap, "style": {k: C[k] for k in ("width_mm", "height_mm", "dpi", "font_pt", "line_pt")}, "fonts_used": fonts[:2],
      "warnings": warn, "outputs": {e: os.path.basename(stem) + "." + e for e in ("svg", "pdf", "png")}}
json.dump(cm, open(stem + "_content_map.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
with open(os.path.join(HERE, "export_log.jsonl"), "a", encoding="utf-8") as f:
    f.write(json.dumps({"stem": os.path.basename(stem), "formats": ["svg", "pdf", "png"], "dpi": C["dpi"], "size_mm": [C["width_mm"], C["height_mm"]],
                        "svg_fonttype": "none (editable text)", "pdf_fonttype": "42 (embedded TrueType)", "fonts": fonts[:2], "matplotlib": matplotlib.__version__,
                        "svg_sha256": sha(stem + ".svg"), "png_method": "matplotlib Agg", "pdf_method": "matplotlib pdf"}, ensure_ascii=False) + "\n")
print("fonts:", fonts[:2], "| CJK:", cjk[:1] or "NONE (use English labels)")
print("\n".join("%s %s/%s mean=%.4g %s=%.4g n=%d rows=%s" % (m["id"], m["x"], m["series"], m["mean"], C["error"], m["error_halfwidth"], m["n"], m["csv_rows"]) for m in marks))
print("\n".join("EXCLUDED: row %d %s %s (%s)" % (e["row"], e["id"], e["cell"], e["reason"]) for e in excluded))
print("\n".join("WARN: " + x for x in warn) or "no warnings")
