#!/usr/bin/env python3
"""export_check (stdlib, py3.8+), pathway edition. Env CASE_JSON / OUT_DIR / WORK_DIR first; else /input/case.json, /app/output, /app/work.
  skeleton                      result.json with case_id + EVERY output-contract field ("生成中") + status partial
  tools                         renderers / modules / CJK fonts available here
  render in.svg [--png o.png] [--pdf o.pdf] [--dpi 300]   real PNG+PDF via a fallback chain (120 s each) -> export_log.jsonl;
                                last resorts: built-in renderer via matplotlib, then a stdlib vector PDF (base-14 fonts)
  assemble [notes.json]         fill result.json from the files in OUT_DIR + your notes (every contract key, by meaning), then check
  check                         result.json vs output contract + previews/SVGs (FAIL = must fix; WARN = record or ignore)"""
import hashlib, importlib.util, json, math, os, re, shutil, subprocess, sys, zlib
import xml.etree.ElementTree as ET
from pathlib import Path
PY, W_ = sys.executable, shutil.which
UNIT = {"px": 1, "mm": 3.7795, "cm": 37.795, "in": 96, "pt": 1.3333, "": 1}
CKEYS = {"outputcontract", "outputschema", "requiredoutputs", "deliverables", "expectedoutputs", "outputfields", "输出契约", "输出要求", "交付要求", "输出字段"}
WORDS = {"complete", "completed", "success", "partial", "failed", "incomplete", "done", "blocked"}
BAD = re.compile(r"\bTODO\b|\bTBC\b|\bTBD\b|lorem|ipsum|待补充|占位|placeholder|XXX|\{\{|\}\}", re.I)
TPL = re.compile(r"<[^<>\n\"]{0,60}[⺀-鿿…|][^<>\n\"]{0,60}>|\"…\"|pass\|partial\|fail|material_missing\|")  # unfilled template slots

def run(args, t=120):
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=t)
        return p.returncode == 0, p.stdout, (p.stderr or "")[-200:]
    except Exception as e:
        return False, "", str(e)[:200]

def has_mod(m):
    return importlib.util.find_spec(m) is not None

def svg_size(path):
    r = ET.parse(path).getroot()
    def num(s):
        m = re.match(r"\s*([\d.]+)\s*([a-z]*)\s*$", s or "")
        return float(m.group(1)) * UNIT.get(m.group(2), 1) if m else None
    w, h = num(r.get("width")), num(r.get("height"))
    if r.get("viewBox") and not (w and h):
        w, h = [float(x) for x in re.split(r"[ ,]+", r.get("viewBox").strip())][2:4]
    return w or 800.0, h or 600.0

def valid(p, kind):
    b = open(p, "rb").read() if os.path.exists(p) else b""  # header + intact ending (truncated files are not previews)
    return len(b) > 500 and (b.startswith(b"\x89PNG") and b"IEND" in b[-16:] if kind == "png" else b.startswith(b"%PDF") and b"%%EOF" in b[-1024:])

def tools(a):
    r = {b: bool(W_(b)) for b in ["rsvg-convert", "inkscape", "soffice", "chromium", "google-chrome", "magick", "pdftotext", "pdffonts", "fc-list"]}
    r.update({m: has_mod(m) for m in ["cairosvg", "matplotlib", "PIL", "openpyxl", "pptx", "fitz", "pypdf"]})
    if W_("fc-list"):
        r["cjk_fonts"] = sorted({l.split(",")[0].strip() for l in run(["fc-list", ":lang=zh", "family"], 30)[1].splitlines() if l.strip()})[:8]
    print(json.dumps(r, ensure_ascii=False, indent=1))

def chain(kind, svg, out, dpi):
    w, h = svg_size(svg)
    z, d, so, url = dpi / 96.0, os.path.dirname(os.path.abspath(out)), W_("soffice") or W_("libreoffice"), "file://" + os.path.abspath(svg)
    ch, mg = next((b for b in ("chromium", "chromium-browser", "google-chrome", "headless_shell") if W_(b)), None), W_("magick") or W_("convert")
    png = os.path.splitext(out)[0] + ".png"
    T = [("rsvg-convert", W_("rsvg-convert"), ["rsvg-convert", "-f", "png", "-z", str(z), "-b", "white", "-o", out, svg]),
         ("cairosvg", has_mod("cairosvg"), [PY, "-c", "import cairosvg,sys;cairosvg.svg2png(url=sys.argv[1],write_to=sys.argv[2],scale=float(sys.argv[3]),background_color='white')", svg, out, str(z)]),
         ("inkscape", W_("inkscape"), ["inkscape", svg, "--export-type=png", "--export-filename=" + out, "--export-dpi=%d" % dpi, "--export-background=white"]),
         ("chrome", ch, [ch, "--headless", "--no-sandbox", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=%.3f" % z,
                         "--screenshot=" + os.path.abspath(out), "--window-size=%d,%d" % (w, h), url]),
         ("magick", mg, [mg, "-density", str(dpi), "-background", "white", svg, out]),
         ("soffice", so, [so, "--headless", "--convert-to", "png", "--outdir", d, svg]),
         ("builtin-matplotlib", has_mod("matplotlib"), [PY, os.path.abspath(__file__), "_mini", "png", svg, out, str(dpi)])] if kind == "png" else \
        [("rsvg-convert", W_("rsvg-convert"), ["rsvg-convert", "-f", "pdf", "-o", out, svg]),
         ("cairosvg", has_mod("cairosvg"), [PY, "-c", "import cairosvg,sys;cairosvg.svg2pdf(url=sys.argv[1],write_to=sys.argv[2])", svg, out]),
         ("inkscape", W_("inkscape"), ["inkscape", svg, "--export-type=pdf", "--export-filename=" + out]),
         ("soffice", so, [so, "--headless", "--convert-to", "pdf", "--outdir", d, svg]),
         ("chrome", ch, [ch, "--headless", "--no-sandbox", "--disable-gpu", "--no-pdf-header-footer", "--print-to-pdf=" + os.path.abspath(out), url]),
         ("builtin-matplotlib", has_mod("matplotlib"), [PY, os.path.abspath(__file__), "_mini", "pdf", svg, out]),
         ("raster-PIL", has_mod("PIL") and os.path.exists(png), [PY, "-c", "from PIL import Image;import sys;Image.open(sys.argv[1]).convert('RGB').save(sys.argv[2])", png, out]),
         ("raster-magick", mg and os.path.exists(png), [mg or "convert", png, out]),
         ("builtin-stdlib-pdf", True, [PY, os.path.abspath(__file__), "_mini", "pdfstd", svg, out])]
    log = []
    for name, avail, args in (t for t in T if t[1]):
        if os.path.exists(out):
            os.remove(out)
        err = run(args)[2]
        made = os.path.join(d, os.path.splitext(os.path.basename(svg))[0] + "." + kind)
        if name == "soffice" and os.path.exists(made) and made != os.path.abspath(out):
            shutil.move(made, out)
        log.append(name + (": ok" if valid(out, kind) else ": fail " + err.strip()[-60:]))
        if valid(out, kind):
            return name, log
    return None, log or ["no renderer available"]

def render(a):
    svg, opt = a[0], dict(zip(a[1::2], a[2::2]))
    stem = os.path.splitext(svg)[0]
    png, pdf, dpi = opt.get("--png", stem + ".png"), opt.get("--pdf", stem + ".pdf"), int(opt.get("--dpi", 300))
    try:
        ET.parse(svg)
    except Exception as e:
        print("FAIL: SVG is not well-formed XML (fix it, then re-render): %s" % e)
        return 1
    (m, log), (m2, log2), fonts = chain("png", svg, png, dpi), chain("pdf", svg, pdf, dpi), "n/a"
    if m2 and W_("pdffonts"):
        rows = [l for l in run(["pdffonts", pdf], 60)[1].splitlines()[2:] if l.strip()]
        fonts = "%d font(s), all embedded=%s" % (len(rows), all(" yes " in l for l in rows)) if rows else "no fonts (text outlined/raster)"
    rep = {"svg": svg, "canvas_px": svg_size(svg), "dpi": dpi, "png": png if m else None, "png_method": m, "png_log": log,
           "pdf": pdf if m2 else None, "pdf_method": m2, "pdf_is_vector": bool(m2 and not m2.startswith("raster")), "pdf_fonts": fonts, "pdf_log": log2}
    if "builtin" in "%s %s" % (m, m2):
        rep["note"] = "built-in fallback renderer (this Skill's SVG subset, approximate text metrics)" + ("; PDF uses non-embedded base-14 fonts, non-Latin glyphs shown as ?" if m2 == "builtin-stdlib-pdf" else "")
    if not m:
        print("NOTE: no PNG renderer here; keep the SVG + PDF, record it (run_failure) and continue - do not retry")
    with open(os.path.join(os.path.dirname(os.path.abspath(png)), "export_log.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(rep, ensure_ascii=False) + "\n")
    print(json.dumps(rep, ensure_ascii=False, indent=1))
    return 0 if m else 1

norm = lambda k: re.sub(r"[_\-\s]", "", str(k).lower())  # noqa: E731
def fields(c):
    if isinstance(c, list):
        return [(x, "") if isinstance(x, str) else (str(x.get("field") or x.get("name") or x.get("key")), json.dumps(x, ensure_ascii=False)) for x in c if isinstance(x, (str, dict))]
    if not isinstance(c, dict):
        return []
    if isinstance(c.get("properties"), dict) or isinstance(c.get("required"), list):
        p = c.get("properties") or {}
        return [(k, json.dumps(v, ensure_ascii=False)) for k, v in p.items()] + [(k, "") for k in c.get("required") or [] if k not in p]
    return [(k, v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)) for k, v in c.items() if k not in ("type", "description", "title", "$schema")]

def contracts(o):
    if isinstance(o, dict):
        return sum(([v] if norm(k) in CKEYS else contracts(v) for k, v in o.items()), [])
    return sum((contracts(v) for v in o), []) if isinstance(o, list) else []

empty = lambda v: v is None or (isinstance(v, str) and v.strip().upper() in ("", "TODO")) or (isinstance(v, (list, dict)) and not v)
def svg_issues(p, mapped):
    f, w, nums, boxes = [], [], set(), []
    try:
        root = ET.parse(p).getroot()
    except Exception as e:
        return ["%s: not well-formed XML: %s" % (p.name, e)], w
    W, H = [float(x) for x in re.split(r"[ ,]+", root.get("viewBox").strip())][2:4] if root.get("viewBox") else svg_size(str(p))
    ids = {el.get("id") for el in root.iter() if len(el.get("id") or "") > 2}
    texts = [el for el in root.iter() if el.tag.split("}")[-1] == "text"]
    fams = " ".join(el.get("font-family") or el.get("style") or "" for el in root.iter())
    mpl = "atplotlib" in open(p, encoding="utf-8", errors="ignore").read(1500)
    if not texts:
        f.append("%s: no <text> elements, labels are not editable (outlined or raster)" % p.name)
    for el in texts:
        s = " ".join("".join(el.itertext()).split())
        if BAD.search(s) or s in ids or re.search(r"\.(md|csv|xlsx|json|txt):L?\d", s):
            f.append("%s: placeholder / internal id / source path in visible text: %r" % (p.name, s[:50]))
        nums |= set() if re.match(r"[xy]?tick", el.get("id") or "") else set(re.findall(r"\d+\.\d+|\d{2,}", s))  # axis ticks are not data
        m = re.findall(r"font-size\s*[:=]\s*\"?([\d.]+)", (el.get("style") or "") + ' font-size="%s"' % el.get("font-size", ""))
        fs = float(m[0]) if m else 12.0
        if fs < 8:
            w.append("%s: font-size %.1f too small for %r" % (p.name, fs, s[:30]))
        lines = ["".join(t.itertext()) for t in el if t.tag.endswith("tspan")] or [s]
        if s and not mpl and "transform" not in el.attrib:
            x, y = [float(re.split(r"[ ,]+", (el.get(k) or (el[0].get(k) if len(el) else "") or "0").strip())[0]) for k in "xy"]
            lw = max(sum(fs * (1.0 if ord(c) > 0x2E80 else 0.56) for c in ln) for ln in lines)
            x0 = x - {"middle": lw / 2, "end": lw}.get(el.get("text-anchor"), 0)
            boxes.append((x0, y - fs * 0.8, x0 + lw, y - fs * 0.8 + fs * 1.2 * len(lines), s[:30]))
    for i, b in enumerate(boxes):
        if b[0] < -2 or b[1] < -2 or b[2] > W + 2 or b[3] > H + 2:
            w.append("%s: text may overflow the %dx%d canvas: %r" % (p.name, W, H, b[4]))
        w += ["%s: texts overlap: %r / %r" % (p.name, b[4], c[4]) for c in boxes[i + 1:] if min(b[2], c[2]) - max(b[0], c[0]) > 3 and min(b[3], c[3]) - max(b[1], c[1]) > 3]
    if re.search(r"[⺀-鿿]", "".join("".join(t.itertext()) for t in texts)) and not re.search(r"CJK|Han|Hei|Song|YaHei|PingFang|WenQuanYi|SC|Unicode|Fallback|AR PL|Ming|Gothic", fams):
        f.append("%s: Chinese text but no CJK font in font-family (tofu risk)" % p.name)
    if any(el.tag.endswith("image") for el in root.iter()):
        w.append("%s: contains raster <image>; the figure itself must be vector" % p.name)
    miss = sorted(n for n in nums if n not in mapped)
    if miss and not mpl:
        w.append("%s: numbers on the figure not found in source map / result.json: %s" % (p.name, miss[:8]))
    return f, w

def check(a):
    out, F, Wn = Path(os.environ.get("OUT_DIR") or "/app/output"), [], []
    try:
        case = json.loads(Path(os.environ.get("CASE_JSON") or "/input/case.json").read_text(encoding="utf-8"))
        res = json.loads((out / "result.json").read_text(encoding="utf-8"))
    except Exception as e:
        print("FAIL: cannot read case.json or result.json: %s" % e)
        return 1
    cid = (case.get("case_id") or case.get("caseId") or case.get("id")) if isinstance(case, dict) else None
    if cid is not None and str(res.get("case_id")) != str(cid):
        F.append("case_id is %r, case.json says %r" % (res.get("case_id"), cid))
    allowed, fl = set(WORDS), sum((fields(c) for c in contracts(case)), [])
    for k, desc in fl:
        if k not in ("case_id", "caseId") and (k not in res or empty(res.get(k))):
            F.append("contract field missing or empty: %s" % k)
        if norm(k) in ("status", "状态"):
            allowed = {x.lower() for x in re.findall(r"[A-Za-z]+", desc) if x.lower() in WORDS} or allowed
    st = str(res.get("status", ""))
    if st.lower() not in allowed:
        F.append("status %r must be exactly one word of %s; reasons go to status_reasons" % (st, sorted(allowed)))
    if st.lower() not in ("complete", "completed", "success", "done") and empty(res.get("status_reasons")):
        F.append("status is not complete but status_reasons is empty")
    roles = {role(k) for k, v in res.items() if not empty(v)}
    Wn += ["standard block %r missing or empty" % k[0] for k in (("artifacts",), ("source_map", "content_map"), ("change_log",), ("export_checks", "export_artifact")) if all(empty(res.get(x)) for x in k) and k[-1] not in roles]
    F += ["contract field %r still holds skeleton text (生成中/pending): fill it with the real result" % k for k, _ in fl if re.search(r"生成中|^pending|in progress", json.dumps(res.get(k), ensure_ascii=False).strip('"'), re.I)]
    Wn += ["field %r may still contain template slots (<…>, …, a|b|c choices): fill them" % k for k, v in res.items() if TPL.search(json.dumps(v, ensure_ascii=False))]
    skip = re.compile(r"gap|uncertain|confirm|reason|note|limit|exception|缺|待确认|不确定", re.I)
    leaves = lambda v: [v] if isinstance(v, str) else sum((leaves(x) for x in (v.values() if isinstance(v, dict) else v)), []) if isinstance(v, (dict, list)) else []  # noqa: E731
    F += ["placeholder text (TODO/TBC/lorem/待补充) left in result.json field %r" % k for k, v in res.items() if not skip.search(k) and BAD.search("\n".join(leaves(v)))]
    arts = [x.get("path") if isinstance(x, dict) else x for x in (res.get("artifacts") or []) if isinstance(x, (str, dict))]
    F += ["artifact listed but missing: %s" % p for p in arts if isinstance(p, str) and not (out / p).exists() and not Path(p).exists()]
    mapped = json.dumps(res, ensure_ascii=False) + "".join(q.read_text(encoding="utf-8", errors="ignore") for q in out.rglob("*") if q.suffix in (".md", ".csv", ".tsv", ".json") and q.is_file())
    tried = " ".join(json.dumps(e) for e in jl(out / "export_log.jsonl") if not (e.get("png") or e.get("pdf") or e.get("formats")))
    for src in [q for q in out.rglob("*") if q.suffix.lower() in (".svg", ".pptx", ".drawio", ".py", ".docx")]:
        if not any(valid(str(q), q.suffix.lower()[1:]) for q in src.parent.glob((src.stem if src.suffix.lower() != ".py" else "") + "*") if q.suffix.lower() in (".png", ".pdf")):
            (F if src.suffix.lower() != ".py" and src.name not in tried else Wn).append("%s has no real PNG/PDF preview with the same stem (%s)" % (
                src.name, "render failed here: record it as run_failure" if src.name in tried else "run export_check.py render"))
        if src.suffix.lower() == ".svg":
            f, w = svg_issues(src, mapped)
            F, Wn = F + f, Wn + w
    ids = set().union(*[{e.get("id") for e in ET.parse(str(q)).getroot().iter()} for q in out.rglob("*.svg")] or [set()])
    reqs = [r for v in res.values() if isinstance(v, list) for r in v if isinstance(r, dict) and "element_ids" in r]
    Wn += ["requirement %r cites element id %r that is not in any output SVG" % (str(r.get("requirement", "?"))[:40], i) for r in reqs for i in r["element_ids"] if i not in ids]
    Wn += [] if reqs else ["no requirement trace: list each workorder requirement with element_ids (compliance_checks)"]
    Wn += [] if list(out.rglob("*pixel_check.json")) else ["no *_pixel_check.json (advisory pixel inspection not run)"]
    if not list(out.rglob("export_log*")):
        Wn.append("no export_log.jsonl: run `export_check.py render` (or log your matplotlib savefig settings)")
    print("\n".join(["WARN: " + x for x in Wn[:40]] + ["FAIL: " + x for x in F]) or "no warnings")
    print("%s: %d contract field(s), status=%s, %d fail / %d warn" % ("FAIL" if F else "PASS", len(fl), st or "?", len(F), len(Wn)))
    return 1 if F else 0

# ---- fallback renderer for this Skill's own SVGs (rect/circle/ellipse/line/polyline/polygon/path/text/tspan/use/marker,
# transforms): PNG+PDF through matplotlib if importable, else a vector PDF with the PDF base-14 fonts (stdlib only).
NUM = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")
HELV = [278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584, 278, 333, 278, 278] + [556] * 10 + [278, 278, 584, 584, 584, 556, 1015,
        667, 667, 722, 722, 667, 611, 778, 722, 278, 500, 667, 556, 833, 722, 778, 667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611,
        278, 278, 278, 469, 556, 333, 556, 556, 500, 556, 556, 278, 556, 556, 222, 222, 500, 222, 833, 556, 556, 556, 556, 333, 500, 278,
        556, 500, 722, 500, 500, 500, 334, 260, 334, 584]
GREEK = dict(zip("αβγδεζηθικλμνξοπρστυφχψωΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩ", "abgdezhqiklmnxoprstufcywABGDEZHQIKLMNXOPRSTUFCYW"))
SUBST = {"−": "-", "‐": "-", "‑": "-", "–": "\x96", "—": "\x97", "•": "\x95", "’": "\x92", "‘": "\x91", "“": "\x93", "”": "\x94", "…": "\x85",
         "⁻": "-", "⁺": "+", "→": "->", "←": "<-", "≥": ">=", "≤": "<=", "√": "sqrt"}

def _mat(t):
    m = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    for name, args in re.findall(r"(\w+)\s*\(([^)]*)\)", t or ""):
        v = [float(x) for x in NUM.findall(args)] or [0.0]
        if name == "translate":
            n = (1, 0, 0, 1, v[0], v[1] if len(v) > 1 else 0)
        elif name == "scale":
            n = (v[0], 0, 0, v[1] if len(v) > 1 else v[0], 0, 0)
        elif name == "rotate":
            a, cx, cy = math.radians(v[0]), (v[1] if len(v) > 2 else 0), (v[2] if len(v) > 2 else 0)
            c, s = math.cos(a), math.sin(a)
            n = (c, s, -s, c, cx - c * cx + s * cy, cy - s * cx - c * cy)
        elif name == "matrix" and len(v) == 6:
            n = tuple(v)
        else:
            continue
        m = _mul(m, n)
    return m

def _mul(m, n):
    a, b, c, d, e, f = m
    return (a * n[0] + c * n[1], b * n[0] + d * n[1], a * n[2] + c * n[3], b * n[2] + d * n[3], a * n[4] + c * n[5] + e, b * n[4] + d * n[5] + f)

def _ap(m, x, y):
    return (m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5])

def _col(v, cur="#000000"):
    v = (v or "").strip().lower()
    if v in ("", "none", "transparent") or v.startswith("url("):
        return None
    if v == "currentcolor":
        v = cur
    names = {"black": "#000000", "white": "#ffffff", "red": "#ff0000", "green": "#008000", "blue": "#0000ff", "gray": "#808080", "grey": "#808080"}
    v = names.get(v, v)
    if re.match(r"#[0-9a-f]{3}$", v):
        v = "#" + "".join(ch * 2 for ch in v[1:])
    if re.match(r"#[0-9a-f]{6}$", v):
        return tuple(int(v[i:i + 2], 16) / 255.0 for i in (1, 3, 5))
    m = re.match(r"rgb\(([^)]*)\)", v)
    return tuple(min(1.0, float(x) / 255.0) for x in NUM.findall(m.group(1))[:3]) if m else (0.0, 0.0, 0.0)

def _sty(el, inh):
    s = dict(inh)
    for k in ("fill", "stroke", "stroke-width", "stroke-dasharray", "font-size", "font-weight", "font-style", "text-anchor", "display", "visibility", "color"):
        if el.get(k) is not None:
            s[k] = el.get(k)
    for part in (el.get("style") or "").split(";"):
        if ":" in part:
            k, v = [x.strip() for x in part.split(":", 1)]
            if k == "font":
                s["font-size"] = (re.findall(r"([\d.]+)(?:px|pt)?\s+['\"\w]", v) or [s.get("font-size", "12")])[0]
                s["font-style"] = "italic" if re.search(r"italic|oblique", v) else s.get("font-style", "normal")
                s["font-weight"] = "bold" if re.search(r"\bbold\b|\b[6-9]00\b", v) else s.get("font-weight", "normal")
            else:
                s[k] = v
    return s

def _path(d):
    subs, cur, x, y, sx, sy, cmd, lc = [], None, 0.0, 0.0, 0.0, 0.0, "M", None
    toks = re.findall(r"[MmLlHhVvCcSsQqTtAaZz]|[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?", d or "")
    i, need = 0, {"M": 2, "L": 2, "H": 1, "V": 1, "C": 6, "S": 4, "Q": 4, "T": 2, "A": 7, "Z": 0}
    while i < len(toks):
        if re.match(r"[A-Za-z]", toks[i]):
            cmd, i = toks[i], i + 1
        U, rel, n = cmd.upper(), cmd.islower(), need[cmd.upper()]
        if U == "Z":
            if cur:
                cur[1] = True
                x, y = sx, sy
            cur = None
            if i < len(toks) and not re.match(r"[A-Za-z]", toks[i]):
                i += 1
            continue
        v = [float(t) for t in toks[i:i + n]]
        i += n
        if len(v) < n:
            break
        ox, oy = (x, y) if rel else (0.0, 0.0)
        if U == "M" or cur is None:
            if U == "M":
                x, y = v[0] + ox, v[1] + oy
            cur = [[(x, y)], False]
            subs.append(cur)
            sx, sy = x, y
            cmd = ("l" if rel else "L") if U == "M" else cmd
            if U == "M":
                continue
        pts = cur[0]
        if U == "L" or U == "T":
            x, y = v[0] + ox, v[1] + oy
            pts.append((x, y))
        elif U == "H":
            x = v[0] + (x if rel else 0.0)
            pts.append((x, y))
        elif U == "V":
            y = v[0] + (y if rel else 0.0)
            pts.append((x, y))
        elif U in ("C", "S", "Q"):
            if U == "C":
                c1, c2, e = (v[0] + ox, v[1] + oy), (v[2] + ox, v[3] + oy), (v[4] + ox, v[5] + oy)
            elif U == "S":
                c1 = (2 * x - lc[0], 2 * y - lc[1]) if lc else (x, y)
                c2, e = (v[0] + ox, v[1] + oy), (v[2] + ox, v[3] + oy)
            else:
                q, e = (v[0] + ox, v[1] + oy), (v[2] + ox, v[3] + oy)
                c1, c2 = (x + 2 / 3.0 * (q[0] - x), y + 2 / 3.0 * (q[1] - y)), (e[0] + 2 / 3.0 * (q[0] - e[0]), e[1] + 2 / 3.0 * (q[1] - e[1]))
            p0 = (x, y)
            for k in range(1, 9):
                t = k / 8.0
                pts.append(tuple((1 - t) ** 3 * p0[j] + 3 * (1 - t) ** 2 * t * c1[j] + 3 * (1 - t) * t * t * c2[j] + t ** 3 * e[j] for j in (0, 1)))
            x, y, lc = e[0], e[1], c2
            continue
        elif U == "A":
            x, y = v[5] + ox, v[6] + oy
            pts.append((x, y))
        lc = None
    return [(p, c) for p, c in subs if len(p) > 1 or c]

def _shape(tag, el):
    g = lambda k, dv=0.0: float((NUM.findall(el.get(k) or "") or [dv])[0])  # noqa: E731
    if tag == "rect":
        x, y, w, h, rx = g("x"), g("y"), g("width"), g("height"), g("rx", g("ry"))
        if (el.get("width") or "").endswith("%"):
            return None
        rx = min(rx, w / 2.0, h / 2.0)
        if rx <= 0:
            return [([(x, y), (x + w, y), (x + w, y + h), (x, y + h)], True)]
        pts = []
        for cx, cy, a0 in ((x + w - rx, y + rx, -90), (x + w - rx, y + h - rx, 0), (x + rx, y + h - rx, 90), (x + rx, y + rx, 180)):
            pts += [(cx + rx * math.cos(math.radians(a0 + 15 * k)), cy + rx * math.sin(math.radians(a0 + 15 * k))) for k in range(7)]
        return [(pts, True)]
    if tag in ("circle", "ellipse"):
        cx, cy = g("cx"), g("cy")
        rx, ry = (g("r"), g("r")) if tag == "circle" else (g("rx"), g("ry"))
        return [([(cx + rx * math.cos(k * math.pi / 18), cy + ry * math.sin(k * math.pi / 18)) for k in range(36)], True)]
    if tag == "line":
        return [([(g("x1"), g("y1")), (g("x2"), g("y2"))], False)]
    if tag in ("polyline", "polygon"):
        v = [float(t) for t in NUM.findall(el.get("points") or "")]
        return [(list(zip(v[::2], v[1::2])), tag == "polygon")]
    if tag == "path":
        return _path(el.get("d"))
    return None

def scene(svg):
    root = ET.parse(svg).getroot()
    vb = [float(v) for v in NUM.findall(root.get("viewBox") or "")]
    W, H = (vb[2], vb[3]) if len(vb) == 4 else svg_size(svg)
    m0 = (1.0, 0.0, 0.0, 1.0, -vb[0], -vb[1]) if len(vb) == 4 else (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    byid = {e.get("id"): e for e in root.iter() if e.get("id")}
    ops = []
    def mark(url, pt, ang, m, st):
        mk = byid.get(re.sub(r"url\(#?([^)]*)\)", r"\1", url or "").strip('"'))
        if mk is None:
            return
        mvb = [float(v) for v in NUM.findall(mk.get("viewBox") or "")]
        mw, mh = float(mk.get("markerWidth", 3)), float(mk.get("markerHeight", 3))
        sc = (mw / mvb[2] if len(mvb) == 4 and mvb[2] else 1.0) * (1.0 if mk.get("markerUnits") == "userSpaceOnUse" else float(NUM.findall(st.get("stroke-width", "1"))[0]))
        t = _mul(_mul(_mul(m, (1, 0, 0, 1, pt[0], pt[1])), _mat("rotate(%f)" % ang)), (sc, 0, 0, sc, 0, 0))
        t = _mul(t, (1, 0, 0, 1, -float(mk.get("refX", 0)), -float(mk.get("refY", 0))))
        for ch in mk:
            walk(ch, t, dict(st, fill="#000000", stroke="none"))
    def walk(el, m, inh):
        tag = el.tag.split("}")[-1]
        if tag in ("defs", "marker", "clipPath", "symbol", "title", "desc", "metadata", "style", "mask", "pattern", "linearGradient", "radialGradient"):
            return
        st = _sty(el, inh)
        if st.get("display") == "none" or st.get("visibility") == "hidden":
            return
        m = _mul(m, _mat(el.get("transform")))
        if tag == "use":
            ref = byid.get((el.get("{http://www.w3.org/1999/xlink}href") or el.get("href") or "").lstrip("#"))
            if ref is not None:
                walk(ref, _mul(m, (1, 0, 0, 1, float(el.get("x", 0)), float(el.get("y", 0)))), st)
            return
        if tag == "text":
            fz = lambda q: float((NUM.findall(q.get("font-size", "12")) or [12])[0])  # noqa: E731
            fs = fz(st)
            x0, y0 = [float((NUM.findall(el.get(k) or "0") or [0])[0]) for k in ("x", "y")]
            runs, cx, cy = [], x0, y0
            if (el.text or "").strip():
                runs.append((cx, cy, el.text.strip(), st, fs))
            for sp in el:
                if sp.tag.split("}")[-1] != "tspan":
                    continue
                s2 = _sty(sp, st)
                if sp.get("x") is not None:
                    cx = float(NUM.findall(sp.get("x"))[0])
                if sp.get("y") is not None:
                    cy = float(NUM.findall(sp.get("y"))[0])
                dy = sp.get("dy") or "0"
                cy += float((NUM.findall(dy) or [0])[0]) * (fs if "em" in dy else 1.0)
                tx = "".join(sp.itertext()).strip()
                if tx:
                    runs.append((cx, cy, tx, s2, fz(s2)))
            lines = {}
            for r in runs:
                lines.setdefault(round(r[1], 2), []).append(r)
            for ln in lines.values():
                ops.append(("text", m, ln, st.get("text-anchor", "start")))
            return
        geo = _shape(tag, el)
        if geo:
            ops.append(("shape", [([_ap(m, *p) for p in pts], c) for pts, c in geo], _col(st.get("fill", "#000000"), st.get("color", "#000")),
                        _col(st.get("stroke", "none"), st.get("color", "#000")), float((NUM.findall(st.get("stroke-width", "1")) or [1])[0]) * math.sqrt(abs(m[0] * m[3] - m[1] * m[2])),
                        [float(v) for v in NUM.findall(st.get("stroke-dasharray", "")) if st.get("stroke-dasharray") != "none"]))
            pts = geo[-1][0] if geo else []
            if len(pts) > 1:
                for key, (a, b), rev in (("marker-end", (pts[-2], pts[-1]), False), ("marker-start", (pts[1], pts[0]), True)):
                    url = el.get(key) or st.get(key)
                    if url:
                        ang = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))
                        mk = byid.get(re.sub(r"url\(#?([^)]*)\)", r"\1", url).strip('"'))
                        if rev and mk is not None and mk.get("orient") == "auto":
                            ang += 180
                        mark(url, b, ang, m, st)
        for ch in el:
            if tag in ("svg", "g", "a", "switch"):
                walk(ch, m, st)
    walk(root, m0, {"fill": "#000000", "stroke": "none", "font-size": "12", "text-anchor": "start"})
    return W, H, ops

def twidth(s, fs, bold=False):
    return sum((HELV[ord(c) - 32] if 32 <= ord(c) < 127 else (560 if c in GREEK else 556)) for c in s) * fs / 1000.0 * (1.06 if bold else 1.0)

def _runs_x(ln, anchor):
    total = sum(twidth(t, fs, "bold" in str(s.get("font-weight"))) for _, _, t, s, fs in ln)
    x = ln[0][0] - {"middle": total / 2.0, "end": total}.get(anchor, 0.0)
    out = []
    for i, (rx, ry, t, s, fs) in enumerate(ln):
        if i and rx != ln[i - 1][0]:
            x = rx
        out.append((x, ry, t, s, fs))
        x += twidth(t, fs, "bold" in str(s.get("font-weight")))
    return out

def mini(kind, svg, out, dpi=300):
    W, H, ops = scene(svg)
    r = ET.parse(svg).getroot()
    wmm = re.match(r"\s*([\d.]+)\s*(mm|cm|in|pt|px)?", r.get("width") or "")
    win = (float(wmm.group(1)) * {"mm": 1 / 25.4, "cm": 1 / 2.54, "in": 1.0, "pt": 1 / 72.0}.get(wmm.group(2), 1 / 96.0)) if wmm and not (r.get("width") or "").endswith("%") else W / 96.0
    k = win * 72.0 / W  # pt per user unit
    if kind in ("png", "pdf"):
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.path import Path as MP
        from matplotlib.patches import PathPatch
        plt.rcParams.update({"pdf.fonttype": 42, "font.family": "sans-serif",
                             "font.sans-serif": ["Arial", "Liberation Sans", "Helvetica", "Noto Sans CJK SC", "Source Han Sans SC", "WenQuanYi Micro Hei", "PingFang SC", "DejaVu Sans"]})
        fig = plt.figure(figsize=(win, win * H / W))
        ax = fig.add_axes([0, 0, 1, 1])
        ax.set_xlim(0, W)
        ax.set_ylim(H, 0)
        ax.axis("off")
        z = 0
        for op in ops:
            z += 1
            if op[0] == "shape":
                _, subs, fill, stroke, sw, dash = op
                vs, cs = [], []
                for pts, closed in subs:
                    vs += pts + ([pts[0]] if closed else [])
                    cs += [MP.MOVETO] + [MP.LINETO] * (len(pts) - 1) + ([MP.CLOSEPOLY] if closed else [])
                pp = PathPatch(MP(vs, cs), facecolor=fill if fill and any(c for _, c in subs) else "none", edgecolor=stroke or "none",
                               linewidth=sw * k if stroke else 0, zorder=z)
                if dash and stroke:
                    pp.set_linestyle((0, [max(0.1, v * k / max(sw * k, 0.1)) for v in dash]))
                ax.add_patch(pp)
            else:
                _, m, ln, anchor = op
                ang = math.degrees(math.atan2(m[1], m[0]))
                sc = math.sqrt(abs(m[0] * m[3] - m[1] * m[2]))
                for x, y, t, s, fs in _runs_x(ln, anchor):
                    X, Y = _ap(m, x, y)
                    ax.text(X, Y, t, fontsize=fs * sc * k, rotation=-ang, rotation_mode="anchor", ha="left", va="baseline", zorder=z,
                            color=_col(s.get("fill", "#000000")) or (0, 0, 0), fontweight="bold" if "bold" in str(s.get("font-weight")) else "normal",
                            fontstyle="italic" if "italic" in str(s.get("font-style")) else "normal")
        fig.savefig(out, dpi=dpi if kind == "png" else 72, facecolor="white")
        plt.close(fig)
        return
    # stdlib vector PDF, base-14 fonts (Helvetica family + Symbol for Greek); CJK has no glyphs here -> '?'
    Hp, c = H * k, []
    P = lambda x, y: "%.2f %.2f" % (x * k, Hp - y * k)  # noqa: E731
    for op in ops:
        if op[0] == "shape":
            _, subs, fill, stroke, sw, dash = op
            closed = any(cl for _, cl in subs)
            path = " ".join(P(*pts[0]) + " m " + " ".join(P(*p) + " l" for p in pts[1:]) + (" h" if cl else "") for pts, cl in subs)
            fill = fill if closed else None
            if not (fill or stroke):
                continue
            c.append("%s%s%.2f w [%s] 0 d %s %s" % ("%.3f %.3f %.3f rg " % fill if fill else "", "%.3f %.3f %.3f RG " % stroke if stroke else "", sw * k,
                                                     " ".join("%.2f" % (v * k) for v in dash), path, "B" if fill and stroke else "f" if fill else "S"))
        else:
            _, m, ln, anchor = op
            a = -math.atan2(m[1], m[0])
            sc = math.sqrt(abs(m[0] * m[3] - m[1] * m[2]))
            for x, y, t, s, fs in _runs_x(ln, anchor):
                X, Y = _ap(m, x, y)
                f = 1 + ("bold" in str(s.get("font-weight"))) + 2 * ("italic" in str(s.get("font-style")))
                col = _col(s.get("fill", "#000000")) or (0, 0, 0)
                segs, cur = [], None
                for ch in t:
                    sym = ch in GREEK
                    ch = GREEK.get(ch, SUBST.get(ch, ch))
                    ch = "".join(q if ord(q) < 256 else "?" for q in ch)
                    if cur is None or cur[0] != sym:
                        cur = [sym, ""]
                        segs.append(cur)
                    cur[1] += ch
                for sym, s_ in segs:
                    e = s_.encode("latin-1").replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)").decode("latin-1")
                    c.append("BT %.3f %.3f %.3f rg /F%d %.2f Tf %.4f %.4f %.4f %.4f %s Tm (%s) Tj ET" % (col + (5 if sym else f, fs * sc * k, math.cos(a), math.sin(a), -math.sin(a), math.cos(a), P(X, Y), e)))
                    adv = twidth(s_, fs * sc)
                    X, Y = X + adv * m[0] / sc, Y + adv * m[1] / sc
    body = zlib.compress("\n".join(c).encode("latin-1"))
    fonts = "".join("/F%d %d 0 R " % (i, 4 + i) for i in range(1, 6))
    objs = ["<< /Type /Catalog /Pages 2 0 R >>", "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %.2f %.2f] /Resources << /Font << %s>> >> /Contents 4 0 R >>" % (W * k, Hp, fonts), None]
    objs += ["<< /Type /Font /Subtype /Type1 /BaseFont /%s%s >>" % (n, "" if n == "Symbol" else " /Encoding /WinAnsiEncoding")
             for n in ("Helvetica", "Helvetica-Bold", "Helvetica-Oblique", "Helvetica-BoldOblique", "Symbol")]
    buf, offs = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"), []
    for i, o in enumerate(objs, 1):
        offs.append(len(buf))
        buf += (b"%d 0 obj\n" % i) + (b"<< /Length %d /Filter /FlateDecode >>\nstream\n" % len(body) + body + b"\nendstream" if o is None else o.encode("latin-1")) + b"\nendobj\n"
    x = len(buf)
    buf += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1) + b"".join(b"%010d 00000 n \n" % o for o in offs)
    buf += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, x)
    open(out, "wb").write(bytes(buf))

# ---- skeleton / assemble: result.json for ANY contract key names (snake, camel, Chinese, properties/required, list of dicts)
def _case():
    try:
        return json.loads(Path(os.environ.get("CASE_JSON") or "/input/case.json").read_text(encoding="utf-8"))
    except Exception:
        return {}

def _cid(c):
    return (c.get("case_id") or c.get("caseId") or c.get("id")) if isinstance(c, dict) else None

def skeleton(a):
    out = Path(os.environ.get("OUT_DIR") or "/app/output")
    out.mkdir(parents=True, exist_ok=True)
    c, p = _case(), out / "result.json"
    r = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    for k, _ in sum((fields(x) for x in contracts(c)), []):
        r.setdefault(k, "生成中")
    r.update({k: _cid(c) for k in r if norm(k) in ("caseid", "id", "案例id", "案例编号")})
    r.update(case_id=_cid(c), status="partial", status_reasons=r.get("status_reasons") or ["生成中"])
    p.write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
    print("skeleton result.json: case_id=%r, fields=%s" % (r["case_id"], sorted(r)))

ROLE = [("status_reasons", r"reason|原因|理由"), ("status", r"^(run|task|case|final|completion)?(status|state|outcome)$|状态"),
        ("exceptions", r"exception|uncertain|issue|problem|gap|risk|limit|warning|error|caveat|unresolved|异常|不确定|缺口|问题|风险|局限|限制"),
        ("export_artifact", r"export|preview|render|output.?file|image|png|pdf|导出|预览|渲染|出图"),
        ("summary", r"note|summary|remark|comment|说明|摘要|备注"),
        ("compliance_checks", r"check|complian|validat|verif|qc|qa|audit|review|requirement|校验|检查|核对|合规|审查|验证"),
        ("change_log", r"change|edit(?!able)|revision|history|modif|log|修改|变更|编辑记录|历史"),
        ("caption", r"caption|legend|图注|图例说明"),
        ("content_map", r"map|trace|proven|source.?data|data|mapping|lineage|element|entit|relation|mark|来源|映射|溯源|数据|实体|关系|元素"),
        ("editable_source", r"source|editable|script|code|spec|project|svg|源|可编辑|脚本"),
        ("versions", r"version|版本|env|runtime"), ("artifacts", r"artifact|file|deliverable|产物|文件|交付"),
        ("summary", r"description|result|answer|main|结果|结论")]

def role(k):
    n = norm(k)
    if n in ("caseid", "id", "案例id", "案例编号"):
        return "case_id"
    return next((r for r, pat in ROLE if re.search(pat, n, re.I)), None)

def word(st, allowed):
    st = str(st or "partial").strip().lower()
    syn = {"complete": ["complete", "completed", "success", "done"], "partial": ["partial", "incomplete", "blocked"], "failed": ["failed", "blocked", "incomplete"]}
    base = next((b for b, v in syn.items() if st in v), "partial")
    return next((w for w in syn[base] if w in allowed), next(iter(sorted(allowed)), base)) if allowed else base

def jl(p):
    try:
        return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]
    except Exception:
        return []

def jf(p, dv=None):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return dv

def sha(p):
    try:
        return hashlib.sha256(open(p, "rb").read()).hexdigest()
    except Exception:
        return None

def assemble(a):
    out = Path(os.environ.get("OUT_DIR") or "/app/output")
    np_ = Path(a[0] if a else os.path.join(os.environ.get("WORK_DIR") or "/app/work", "notes.json"))
    notes, c, bad = {}, _case(), None
    if np_.exists():
        try:
            notes = json.loads(np_.read_text(encoding="utf-8"))
            bad = None if isinstance(notes, dict) else "not a JSON object"
        except Exception as e:
            bad = str(e)[:120]
    if bad:
        notes = {}
        print("FAIL: %s could not be used (%s): fix the JSON and run assemble again; automatic content only for now" % (np_, bad))
    res = jf(out / "result.json", {}) or {}
    fl = sum((fields(x) for x in contracts(c)), [])
    allowed = set()
    for k, desc in fl:
        if role(k) == "status":
            allowed |= {x.lower() for x in re.findall(r"[A-Za-z]+", desc) if x.lower() in WORDS}
    ck = {k for k, _ in fl}
    for k in [k for k in res if k not in ck and (k in CONSUMED or k in ("editable_source", "export_artifact", "content_map", "versions", "artifacts", "run_notes"))]:
        del res[k]  # rebuilt below, so a re-run never keeps stale blocks
    B, run_notes = blocks(out, notes), list(notes.get("run_notes") or [])
    st = word("failed" if not list(out.glob("*.svg")) else notes.get("status") or "partial", allowed)  # no figure = failed, whatever the notes say
    reasons = notes.get("status_reasons") or B.pop("_auto_reasons", None) or ["see exceptions"]
    B.pop("_auto_reasons", None)
    skel = lambda v: empty(v) or bool(re.search(r"生成中|^pending|in progress", json.dumps(v, ensure_ascii=False).strip('"'), re.I))  # noqa: E731
    given = notes.get("fields") or {}
    res.update(case_id=_cid(c) if _cid(c) is not None else res.get("case_id"), status=st, status_reasons=reasons)
    for k, _ in fl:
        if k in given:
            res[k] = given[k]
            continue
        r = role(k)
        if r == "case_id":
            res[k] = res["case_id"]
        elif r == "status":
            res[k] = st
        elif r == "status_reasons":
            res[k] = reasons
        elif not r and not skel(res.get(k)) and "field name not recognised" not in json.dumps(res.get(k), ensure_ascii=False):
            continue  # unrecognised name the agent already filled itself
        elif r and not empty(B.get(r)):
            res[k] = B[r]
            if k != r:
                run_notes.append("contract field %r filled with the %s block (matched by name)" % (k, r))
        else:
            res[k] = {"summary": B["summary"], "files": [x["path"] for x in B["artifacts"] if x["role"] in ("source", "export")][:12],
                      "note": "nothing of this kind was produced in this run" if r else "field name not recognised; filled with the run summary"}
            run_notes.append("contract field %r %s: filled with the run summary + file list" % (k, "had no content (%s)" % r if r else "not recognised"))
    for r in ("editable_source", "export_artifact", "content_map", "compliance_checks", "exceptions", "change_log", "versions", "artifacts", "caption"):
        if r not in [role(k) for k, _ in fl] and not empty(B.get(r)):
            res[r] = B[r]
    for k, v in notes.items():
        if k not in CONSUMED and k not in res:
            res[k] = v
    if run_notes:
        res["run_notes"] = run_notes
    (out / "result.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print("assembled result.json: status=%s, %d contract field(s): %s" % (st, len(fl), ", ".join("%s<-%s" % (k, role(k) or "summary") for k, _ in fl)))
    rc = check([])
    return 1 if bad else rc

SKILL_VER = "bio-pathway-figure-lite 1.2"
CONSUMED = {"fields", "status", "status_reasons", "run_notes", "edit_request", "summary", "compliance_checks", "exceptions", "change_log", "caption"}

def blocks(out, notes):
    """Canonical result blocks from whatever files exist in OUT_DIR (every input optional) + the agent's notes.json."""
    ls = sorted(p.name for p in out.iterdir() if p.is_file() and p.name != "result.json")
    has = lambda n: n in ls  # noqa: E731
    svgs = [n for n in ls if n.endswith(".svg")]
    main = "figure.svg" if has("figure.svg") else (svgs[0] if svgs else None)
    stem = main[:-4] if main else "figure"
    cm = jf(out / (stem + "_content_map.json"), {}) or {}
    pxs = {n: jf(out / n, {}) or {} for n in ls if n.endswith("_pixel_check.json")}
    logs, diff = jl(out / "export_log.jsonl"), jf(out / "edit_diff.json", {}) or {}
    specs = [n for n in ls if n.endswith(".json") and "spec" in n]
    B = {"artifacts": [{"path": n, "role": "source" if n.endswith(".svg") or n in specs else "export" if n.endswith((".pdf", ".png")) else "record"} for n in ls]}
    B["editable_source"] = {k: v for k, v in (("svg", svgs or None), ("spec", specs or None),
        ("layers", ["panels", "edges", "nodes", "data", "text", "legend"] if main else None),
        ("how_to_edit", "edit the spec and run svgfig.py build, or svgfig.py edit <in.svg> <out.svg> <id> --text/--set" if main else None)) if v is not None}
    ex = []
    for e in logs:
        ex += [{"file": os.path.basename(str(e.get(f))), "format": f, "dpi": e.get("dpi"), "canvas_px": e.get("canvas_px"), "renderer": e.get(f + "_method"),
                "pdf_is_vector": e.get("pdf_is_vector") if f == "pdf" else None, "pdf_fonts": e.get("pdf_fonts") if f == "pdf" else None, "note": e.get("note")}
               for f in ("png", "pdf") if e.get(f)]
        ex += [{"file": None, "source_svg": os.path.basename(str(e.get("svg"))), "format": f, "renderer": None, "log": e.get(f + "_log")} for f in ("png", "pdf") if not e.get(f)]
    seen = {x.get("file") for x in ex}
    ex += [{"file": n, "format": n.rsplit(".", 1)[1]} for n in ls if n.endswith((".png", ".pdf")) and n not in seen]
    ex += [{"pixel_check": n, "advisory": True, "inspected": p.get("inspected"), "export_png_px": p.get("export_png_px"), "export_dpi": p.get("export_dpi"),
            "warnings": (p.get("warnings") or []) + (p.get("fails") or []), "skipped": p.get("skipped")} for n, p in pxs.items()]
    B["export_artifact"] = ex
    B["content_map"] = dict(cm, file=stem + "_content_map.json") if cm else {"file": None, "note": "no content map (svgfig build not run)"}
    if has("figure_source_map.md"):
        B["content_map"]["source_map_file"] = "figure_source_map.md"
    cc = [x for x in (notes.get("compliance_checks") or []) if isinstance(x, dict)]
    cc += [{"requirement": "rendered pixel inspection (%s, advisory)" % n, "result": "pass" if not ((p.get("warnings") or []) + (p.get("fails") or []) or p.get("skipped")) else "partial",
            "element_ids": [], "evidence": "; ".join(((p.get("warnings") or []) + (p.get("fails") or []))[:4]) or p.get("skipped") or n} for n, p in pxs.items()]
    B["compliance_checks"] = cc
    exc = [x for x in (notes.get("exceptions") or []) if isinstance(x, dict)]
    told = json.dumps(exc, ensure_ascii=False).lower()
    skipped = [p.get("skipped") for p in pxs.values() if p.get("skipped")]
    if (not pxs or skipped) and "pixel" not in told:
        exc.append({"category": "run_failure", "detail": "rendered pixel inspection not available: %s" % (skipped[0] if skipped else "not run"), "handling": "advisory check skipped; SVG/PDF kept"})
    miss = [f for f in ("png", "pdf") if not any(n.endswith("." + f) for n in ls)]
    if miss and "run_failure" not in told:
        exc.append({"category": "run_failure", "detail": "missing export format(s): %s" % miss, "handling": "see export_log.jsonl; no preview was faked"})
    left = [w for w in (cm.get("warnings") or []) if w.split(":")[0].lower()[:30] not in told]
    if left:
        exc.append({"category": "run_failure", "detail": "layout warnings left after the allowed rebuilds: %s" % "; ".join(left[:5]), "handling": "kept; see %s_content_map.json" % stem})
    B["exceptions"] = exc or [{"category": "none", "detail": "no open issues recorded", "handling": "-"}]
    v2 = [n for n in ls if "_v2" in n]
    B["change_log"] = [x for x in (notes.get("change_log") or []) if isinstance(x, dict)] or (
        [{"version": "v2", "request": notes.get("edit_request") or "(not stated)", "outputs": v2, "svg_changes": (diff.get("changes") or [])[:40],
          "kept_ids": diff.get("kept_ids"), "unchanged_ids": diff.get("unchanged_ids")}] if v2 or diff else
        [{"version": "v1", "change": "initial figure from the materials", "note": "no edit applied"}])
    mats = sorted(str(p) for p in Path("/input").rglob("*") if p.is_file())[:30] if Path("/input").exists() else []
    B["versions"] = {"skill": SKILL_VER, "python": sys.version.split()[0], "spec_sha256_16": cm.get("spec_sha256_16"),
                     "data_encoding": {k: (cm.get("data_encoding") or {}).get(k) for k in ("file", "sha256_16")} if cm.get("data_encoding") else None,
                     "renderer": next((e.get("png_method") or e.get("pdf_method") for e in reversed(logs) if e.get("png_method") or e.get("pdf_method")), None),
                     "materials_sha256": {p: sha(p) for p in mats}}
    auto = "%s. Legend: %s." % (((jf(out / specs[0], {}) or {}).get("canvas") or {}).get("title", "Figure") if specs else "Figure",
                               "; ".join("%s = %s" % (x.get("edge") or x.get("fill") or x.get("evidence"), x.get("label")) for x in (cm.get("legend") or []))) if cm else None
    B["caption"] = notes.get("caption") or ((out / "figure_caption.md").read_text(encoding="utf-8") if has("figure_caption.md") else auto)
    B["summary"] = notes.get("summary") or "%s: %d entities, %d relations, %d legend items; editable spec %s; exports %s; status reasons: %s" % (
        main or "no figure", len(cm.get("entities") or []), len(cm.get("relations") or []), len(cm.get("legend") or []), specs,
        [n for n in ls if n.endswith((".png", ".pdf"))], "; ".join(map(str, notes.get("status_reasons") or [])) or "see exceptions")
    B["_auto_reasons"] = [x.get("detail") for x in exc if x.get("category") not in ("none",)][:6] or None
    return B

CMDS = {"skeleton": skeleton, "tools": tools, "render": render, "assemble": assemble, "check": check}
if __name__ == "__main__":
    if len(sys.argv) > 4 and sys.argv[1] == "_mini":
        sys.exit(mini(sys.argv[2], sys.argv[3], sys.argv[4], float(sys.argv[5]) if len(sys.argv) > 5 else 300) or 0)
    if len(sys.argv) < 2 or sys.argv[1] not in CMDS:
        print(__doc__)
        sys.exit(2)
    sys.exit(CMDS[sys.argv[1]](sys.argv[2:]) or 0)
