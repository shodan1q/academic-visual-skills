#!/usr/bin/env python3
"""export_check (stdlib, py3.8+). tools: renderers/modules/CJK fonts here | render in.svg [--png o.png]
[--pdf o.pdf] [--dpi 300]: real PNG+PDF via fallback chain (120 s each), logged to export_log.jsonl | check:
result.json vs output contract + all artifacts/previews/SVGs (env CASE_JSON, OUT_DIR; else /input/case.json, /app/output)"""
import importlib.util, json, os, re, shutil, subprocess, sys
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
         ("soffice", so, [so, "--headless", "--convert-to", "png", "--outdir", d, svg])] if kind == "png" else \
        [("rsvg-convert", W_("rsvg-convert"), ["rsvg-convert", "-f", "pdf", "-o", out, svg]),
         ("cairosvg", has_mod("cairosvg"), [PY, "-c", "import cairosvg,sys;cairosvg.svg2pdf(url=sys.argv[1],write_to=sys.argv[2])", svg, out]),
         ("inkscape", W_("inkscape"), ["inkscape", svg, "--export-type=pdf", "--export-filename=" + out]),
         ("soffice", so, [so, "--headless", "--convert-to", "pdf", "--outdir", d, svg]),
         ("chrome", ch, [ch, "--headless", "--no-sandbox", "--disable-gpu", "--no-pdf-header-footer", "--print-to-pdf=" + os.path.abspath(out), url]),
         ("raster-PIL", has_mod("PIL") and os.path.exists(png), [PY, "-c", "from PIL import Image;import sys;Image.open(sys.argv[1]).convert('RGB').save(sys.argv[2])", png, out]),
         ("raster-magick", mg and os.path.exists(png), [mg or "convert", png, out])]
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
    Wn += ["standard block %r missing or empty" % k[0] for k in (("artifacts",), ("source_map", "content_map"), ("change_log",), ("export_checks", "export_artifact")) if all(empty(res.get(x)) for x in k)]
    F += ["contract field %r still holds skeleton text (生成中/pending): fill it with the real result" % k for k, _ in fl if re.search(r"生成中|^pending|in progress", json.dumps(res.get(k), ensure_ascii=False).strip('"'), re.I)]
    F += ["field %r still contains template slots (<…>, …, a|b|c choices): fill them" % k for k, v in res.items() if TPL.search(json.dumps(v, ensure_ascii=False))]
    skip = re.compile(r"gap|uncertain|confirm|reason|note|limit|exception|缺|待确认|不确定", re.I)
    leaves = lambda v: [v] if isinstance(v, str) else sum((leaves(x) for x in (v.values() if isinstance(v, dict) else v)), []) if isinstance(v, (dict, list)) else []  # noqa: E731
    F += ["placeholder text (TODO/TBC/lorem/待补充) left in result.json field %r" % k for k, v in res.items() if not skip.search(k) and BAD.search("\n".join(leaves(v)))]
    arts = [x.get("path") if isinstance(x, dict) else x for x in (res.get("artifacts") or []) if isinstance(x, (str, dict))]
    F += ["artifact listed but missing: %s" % p for p in arts if isinstance(p, str) and not (out / p).exists() and not Path(p).exists()]
    mapped = json.dumps(res, ensure_ascii=False) + "".join(q.read_text(encoding="utf-8", errors="ignore") for q in out.rglob("*") if q.suffix in (".md", ".csv", ".tsv", ".json") and q.is_file())
    for src in [q for q in out.rglob("*") if q.suffix.lower() in (".svg", ".pptx", ".drawio", ".py", ".docx")]:
        if not any(valid(str(q), q.suffix.lower()[1:]) for q in src.parent.glob((src.stem if src.suffix.lower() != ".py" else "") + "*") if q.suffix.lower() in (".png", ".pdf")):
            (F if src.suffix.lower() != ".py" else Wn).append("%s has no real PNG/PDF preview with the same stem (render it)" % src.name)
        if src.suffix.lower() == ".svg":
            f, w = svg_issues(src, mapped)
            F, Wn = F + f, Wn + w
    ids = set().union(*[{e.get("id") for e in ET.parse(str(q)).getroot().iter()} for q in out.rglob("*.svg")] or [set()])
    reqs = [r for v in res.values() if isinstance(v, list) for r in v if isinstance(r, dict) and "element_ids" in r]
    F += ["requirement %r cites element id %r that is not in any output SVG" % (str(r.get("requirement", "?"))[:40], i) for r in reqs for i in r["element_ids"] if i not in ids]
    Wn += [] if reqs else ["no requirement trace: list each workorder requirement with element_ids (compliance_checks)"]
    Wn += [] if list(out.rglob("*pixel_check.json")) else ["no *_pixel_check.json: run pixcheck.py on the final SVG"]
    if not list(out.rglob("export_log*")):
        Wn.append("no export_log.jsonl: run `export_check.py render` (or log your matplotlib savefig settings)")
    print("\n".join(["WARN: " + x for x in Wn[:40]] + ["FAIL: " + x for x in F]) or "no warnings")
    print("%s: %d contract field(s), status=%s, %d fail / %d warn" % ("FAIL" if F else "PASS", len(fl), st or "?", len(F), len(Wn)))
    return 1 if F else 0

CMDS = {"tools": tools, "render": render, "check": check}
if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in CMDS:
        print(__doc__)
        sys.exit(2)
    sys.exit(CMDS[sys.argv[1]](sys.argv[2:]) or 0)
