#!/usr/bin/env python3
"""export_check (stdlib, py3.8+). Never raises; every command ends with an [elapsed] line.
  init                      skeleton /app/output/result.json (case_id + contract fields, status partial) + tools probe
  tools                     renderers / python modules / CJK fonts available here
  pdf in.pdf [--grep RE]    PDF -> $WORK_DIR/<stem>.txt (timeouts + fallbacks); prints a bounded map, never the whole text
  render a.svg [b.svg ...] [--dpi 300] [--budget 180]   real PNG+PDF via fallback chain; each tool <= 60 s, all SVGs together
                            <= --budget s (default 180); tools that hung are skipped for the rest of the run; always logs export_log.jsonl
  fill                      fill EMPTY standard blocks of result.json from disk (artifacts, export_checks, source_map,
                            change_log, versions); never overwrites what is already written
  check                     result.json vs output contract + all artifacts/previews/SVGs
Env: CASE_JSON, OUT_DIR, WORK_DIR (defaults /input/case.json, /app/output, /app/work)."""
import importlib.util, json, os, re, shutil, signal, struct, subprocess, sys, time
import xml.etree.ElementTree as ET
from pathlib import Path
PY, W_ = sys.executable, shutil.which
OUT = os.environ.get("OUT_DIR") or "/app/output"
WORK = os.environ.get("WORK_DIR") or "/app/work"
CASE = os.environ.get("CASE_JSON") or "/input/case.json"
UNIT = {"px": 1, "mm": 3.7795, "cm": 37.795, "in": 96, "pt": 1.3333, "": 1}
CKEYS = {"outputcontract", "outputschema", "requiredoutputs", "deliverables", "expectedoutputs", "outputfields", "输出契约", "输出要求", "交付要求", "输出字段"}
WORDS = {"complete", "completed", "success", "partial", "failed", "incomplete", "done", "blocked"}
BAD = re.compile(r"\bTODO\b|\bTBC\b|\bTBD\b|lorem|ipsum|待补充|占位|placeholder|XXX|\{\{|\}\}", re.I)
SKEL = "生成中"

def run(args, t=60):
    """subprocess with a hard timeout that kills the whole process group (soffice/chrome leave children otherwise)"""
    try:
        p = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             encoding="utf-8", errors="replace", start_new_session=True)
    except Exception as e:
        return False, "", str(e)[:200]
    try:
        o, e = p.communicate(timeout=max(1, t))
        return p.returncode == 0, o or "", (e or "")[-200:]
    except subprocess.TimeoutExpired:
        try:
            os.killpg(p.pid, signal.SIGKILL)
        except Exception:
            p.kill()
        try:
            p.communicate(timeout=5)
        except Exception:
            pass
        return False, "", "TIMEOUT after %ds (killed)" % t
    except Exception as e:
        return False, "", str(e)[:200]

def has_mod(m):
    try:
        return importlib.util.find_spec(m) is not None
    except Exception:
        return False

def elapsed():
    try:
        s = time.time() - float(open(os.path.join(WORK, ".t0")).read().strip())
        tip = "  time is short: skip optional steps, run `fill` + write result.json + `check` now" if s > 600 else ""
        print("[elapsed %d s since init; run budget 900 s]%s" % (s, tip))
    except Exception:
        pass

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
    try:
        with open(p, "rb") as f:
            head = f.read(8)
            f.seek(0, 2)
            n = f.tell()
            f.seek(max(0, n - 1024))
            tail = f.read()
    except Exception:
        return False  # header + intact ending (truncated files are not previews)
    return n > 500 and (head.startswith(b"\x89PNG") and b"IEND" in tail[-16:] if kind == "png" else head.startswith(b"%PDF") and b"%%EOF" in tail)

def png_px(p):
    try:
        b = open(p, "rb").read(24)
        return list(struct.unpack(">II", b[16:24])) if b.startswith(b"\x89PNG") else None
    except Exception:
        return None

def load_json(p, default=None):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return default

def tools(a, quiet=False):
    r = {b: bool(W_(b)) for b in ["rsvg-convert", "inkscape", "soffice", "chromium", "google-chrome", "magick", "pdftotext", "pdffonts", "fc-list"]}
    r.update({m: has_mod(m) for m in ["cairosvg", "matplotlib", "PIL", "openpyxl", "pptx", "fitz", "pypdf"]})
    if W_("fc-list"):
        r["cjk_fonts"] = sorted({l.split(",")[0].strip() for l in run(["fc-list", ":lang=zh", "family"], 30)[1].splitlines() if l.strip()})[:8]
    print(json.dumps(r, ensure_ascii=False))
    return r

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

def case_id(case):
    return (case.get("case_id") or case.get("caseId") or case.get("id")) if isinstance(case, dict) else None

def init(a):
    """skeleton result.json within the first calls: valid JSON even if the run is cut off later"""
    for d in (OUT, WORK):
        try:
            os.makedirs(d, exist_ok=True)
        except Exception as e:
            print("WARN: cannot create %s: %s" % (d, e))
    t0 = os.path.join(WORK, ".t0")
    if not os.path.exists(t0):
        try:
            open(t0, "w").write(str(time.time()))
        except Exception:
            pass
    case = load_json(CASE, {})
    rp = os.path.join(OUT, "result.json")
    if isinstance(load_json(rp), dict):
        print("result.json already exists and is valid JSON: left unchanged (%s)" % rp)
    else:
        fl = [k for k, _ in sum((fields(c) for c in contracts(case)), [])]
        r = {k: SKEL for k in fl if k not in ("case_id", "caseId")}
        r.update(case_id=case_id(case), status="partial", status_reasons=[SKEL + "：运行未完成时保留本句，表示后续字段未填写"])
        try:
            Path(rp).write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
            print("wrote skeleton %s: case_id=%r, %d contract field(s): %s" % (rp, r["case_id"], len(fl), ", ".join(fl) or "(no output contract found in case.json: use the task text)"))
        except Exception as e:
            print("WARN: cannot write %s: %s" % (rp, e))
    tools(a)

def pdf(a):
    if not a:
        print("usage: pdf in.pdf [--grep REGEX] [--out file.txt]")
        return 0
    src, opt = a[0], dict(zip(a[1::2], a[2::2]))
    os.makedirs(WORK, exist_ok=True)
    out = opt.get("--out") or os.path.join(WORK, re.sub(r"[^\w.-]", "_", os.path.splitext(os.path.basename(src))[0]) + ".txt")
    how, txt = None, ""
    attempts = []
    if W_("pdftotext"):
        attempts.append(("pdftotext", ["pdftotext", "-layout", src, out], 60))
    if has_mod("fitz"):
        attempts.append(("fitz", [PY, "-c", "import fitz,sys;d=fitz.open(sys.argv[1]);open(sys.argv[2],'w',encoding='utf-8').write('\\f'.join(p.get_text() for p in d))", src, out], 60))
    if has_mod("pypdf"):
        attempts.append(("pypdf", [PY, "-c", "import pypdf,sys;r=pypdf.PdfReader(sys.argv[1]);open(sys.argv[2],'w',encoding='utf-8').write('\\f'.join((p.extract_text() or '') for p in r.pages))", src, out], 80))
    for name, args, t in attempts:
        ok, _, err = run(args, t)
        try:
            txt = open(out, encoding="utf-8", errors="replace").read()
        except Exception:
            txt = ""
        if ok and len(txt.strip()) > 50:
            how = name
            break
        print("WARN: %s failed: %s" % (name, err.strip()[-120:] or "empty text"))
    if not how:
        print("FAIL: no text extracted from %s (tried: %s). Record it in material_gaps; if it is a scan, say so; do not guess its content." % (src, ", ".join(n for n, _, _ in attempts) or "no pdftotext/fitz/pypdf"))
        elapsed()
        return 0
    lines = txt.split("\n")  # not splitlines(): it would swallow the \f page breaks
    print("text: %s  (method %s, %d pages, %d lines, %d chars)  read parts with: sed -n 'A,Bp' %s  (<= 120 lines per call)" % (out, how, txt.count("\f") + 1, len(lines), len(txt), out))
    head = re.compile(r"^\s{0,12}((\d{1,2}(\.\d{1,2}){0,2}\.?\s+[A-Z一-鿿])|(abstract|introduction|results?|discussion|methods?|materials and methods|experimental|star\s*methods|method details|references|supplementa\w*|acknowledg\w*)\b|(fig(ure)?\.?\s*\d+[.:|]))", re.I)
    page, shown = 1, 0
    print("--- map (page:line  text) ---")
    for i, l in enumerate(lines, 1):
        page += l.count("\f")
        c = l.replace("\f", "").strip()
        if re.match(r"^(references|bibliography|参考文献)\b", c, re.I) and i > len(lines) * 0.3:
            print("p%d:L%d  %s  (map stops here)" % (page, i, c[:60]))
            break
        if head.match(l.replace("\f", "")) and shown < 70 and (len(c) < 90 or re.match(r"fig", c, re.I)):
            print("p%d:L%d  %s" % (page, i, " ".join(l.split())[:110]))
            shown += 1
    if opt.get("--grep"):
        try:
            rg = re.compile(opt["--grep"], re.I)
        except re.error as e:
            print("WARN: bad --grep regex: %s" % e)
            rg = None
        hits = [(i, l) for i, l in enumerate(lines, 1) if rg and rg.search(l)]
        print("--- grep %r: %d hit(s), first 40 ---" % (opt["--grep"], len(hits)))
        for i, l in hits[:40]:
            print("L%d  %s" % (i, " ".join(l.split())[:160]))
    elapsed()
    return 0

def chain(kind, svg, out, dpi, deadline, per, skip):
    w, h = svg_size(svg)
    z, d, so, url = dpi / 96.0, os.path.dirname(os.path.abspath(out)), W_("soffice") or W_("libreoffice"), "file://" + os.path.abspath(svg)
    ch, mg = next((W_(b) for b in ("chromium", "chromium-browser", "google-chrome", "headless_shell") if W_(b)), None), W_("magick") or W_("convert")
    lo = ["-env:UserInstallation=file://" + os.path.abspath(os.path.join(WORK, "lo_profile"))]
    cf = ["--headless", "--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage", "--no-first-run", "--hide-scrollbars"]
    png = os.path.splitext(out)[0] + ".png"
    T = [("rsvg-convert", W_("rsvg-convert"), ["rsvg-convert", "-f", "png", "-z", str(z), "-b", "white", "-o", out, svg]),
         ("cairosvg", has_mod("cairosvg"), [PY, "-c", "import cairosvg,sys;cairosvg.svg2png(url=sys.argv[1],write_to=sys.argv[2],scale=float(sys.argv[3]),background_color='white')", svg, out, str(z)]),
         ("inkscape", W_("inkscape"), ["inkscape", svg, "--export-type=png", "--export-filename=" + out, "--export-dpi=%d" % dpi, "--export-background=white"]),
         ("chrome", ch, [ch] + cf + ["--force-device-scale-factor=%.3f" % z, "--screenshot=" + os.path.abspath(out), "--window-size=%d,%d" % (w, h), url]),
         ("magick", mg, [mg, "-density", str(dpi), "-background", "white", svg, out]),
         ("soffice", so, [so] + lo + ["--headless", "--convert-to", "png", "--outdir", d, svg])] if kind == "png" else \
        [("rsvg-convert", W_("rsvg-convert"), ["rsvg-convert", "-f", "pdf", "-o", out, svg]),
         ("cairosvg", has_mod("cairosvg"), [PY, "-c", "import cairosvg,sys;cairosvg.svg2pdf(url=sys.argv[1],write_to=sys.argv[2])", svg, out]),
         ("inkscape", W_("inkscape"), ["inkscape", svg, "--export-type=pdf", "--export-filename=" + out]),
         ("soffice", so, [so] + lo + ["--headless", "--convert-to", "pdf", "--outdir", d, svg]),
         ("chrome", ch, [ch] + cf + ["--no-pdf-header-footer", "--print-to-pdf=" + os.path.abspath(out), url]),
         ("raster-PIL", has_mod("PIL") and os.path.exists(png), [PY, "-c", "from PIL import Image;import sys;Image.open(sys.argv[1]).convert('RGB').save(sys.argv[2])", png, out]),
         ("raster-magick", mg and os.path.exists(png), [mg or "convert", png, out])]
    log = []
    if os.path.exists(out):
        os.remove(out)  # a stale preview of an older SVG must not pass as this one
    for name, avail, args in (t for t in T if t[1]):
        left = deadline - time.time()
        if name in skip:
            log.append(name + ": skipped (timed out earlier in this run)")
            continue
        if left < 8:
            log.append(name + ": skipped (render budget used up)")
            continue
        if os.path.exists(out):
            os.remove(out)
        ok, _, err = run(args, int(min(per, left)))
        if err.startswith("TIMEOUT"):
            skip.add(name)
        made = os.path.join(d, os.path.splitext(os.path.basename(svg))[0] + "." + kind)
        if name == "soffice" and os.path.exists(made) and made != os.path.abspath(out):
            shutil.move(made, out)
        log.append(name + (": ok" if valid(out, kind) else ": fail " + err.strip()[-60:]))
        if valid(out, kind):
            return name, log
    return None, log or ["no renderer available"]

def render(a):
    svgs, opt, k = [], {}, 0
    while k < len(a):
        if a[k].startswith("--") and k + 1 < len(a):
            opt[a[k]], k = a[k + 1], k + 2
        else:
            svgs, k = svgs + [a[k]], k + 1
    if not svgs:
        print("usage: render a.svg [b.svg ...] [--dpi 300] [--budget 180]")
        return 0
    dpi, per = int(float(opt.get("--dpi", 300))), int(float(opt.get("--per-tool", 60)))
    deadline = time.time() + float(opt.get("--budget", 180))
    os.makedirs(WORK, exist_ok=True)
    sk = os.path.join(WORK, ".render_skip")
    skip = set(load_json(sk, []) or [])
    summary = []
    for svg in svgs:
        stem = os.path.splitext(svg)[0]
        png, pdfp = (opt.get("--png"), opt.get("--pdf")) if len(svgs) == 1 else (None, None)
        png, pdfp = png or stem + ".png", pdfp or stem + ".pdf"
        try:
            ET.parse(svg)
        except Exception as e:
            print("FAIL: %s is not well-formed XML (fix it, then re-render): %s" % (svg, e))
            summary.append("%s: not rendered (bad XML)" % os.path.basename(svg))
            continue
        (m, log), (m2, log2), fonts = chain("png", svg, png, dpi, deadline, per, skip), chain("pdf", svg, pdfp, dpi, deadline, per, skip), "n/a"
        if m2 and W_("pdffonts"):
            rows = [l for l in run(["pdffonts", pdfp], 20)[1].splitlines()[2:] if l.strip()]
            fonts = "%d font(s), all embedded=%s" % (len(rows), all(" yes " in l for l in rows)) if rows else "no fonts (text outlined/raster)"
        rep = {"svg": svg, "canvas_px": svg_size(svg), "dpi": dpi, "png": png if m else None, "png_px": png_px(png) if m else None, "png_method": m, "png_log": log,
               "pdf": pdfp if m2 else None, "pdf_method": m2, "pdf_is_vector": bool(m2 and not m2.startswith("raster")), "pdf_fonts": fonts, "pdf_log": log2,
               "time": time.strftime("%Y-%m-%d %H:%M:%S")}
        try:
            with open(os.path.join(os.path.dirname(os.path.abspath(png)), "export_log.jsonl"), "a", encoding="utf-8") as f:
                f.write(json.dumps(rep, ensure_ascii=False) + "\n")
        except Exception as e:
            print("WARN: cannot write export_log.jsonl: %s" % e)
        print(json.dumps(rep, ensure_ascii=False))
        summary.append("%s: png=%s pdf=%s" % (os.path.basename(svg), m or "FAILED", m2 or "FAILED"))
    try:
        open(sk, "w").write(json.dumps(sorted(skip)))
    except Exception:
        pass
    bad = [s for s in summary if "FAILED" in s or "not rendered" in s]
    print("RENDER %s: %s" % ("INCOMPLETE" if bad else "OK", "; ".join(summary)))
    if bad:
        print("Do not loop on this: retry at most once (e.g. after fixing XML); otherwise keep the SVG, record the failure from export_log.jsonl in export_checks + status_reasons, status partial.")
    elapsed()
    return 0

def leaves(v):
    return [v] if isinstance(v, str) else sum((leaves(x) for x in (v.values() if isinstance(v, dict) else v)), []) if isinstance(v, (dict, list)) else []

empty = lambda v: v is None or (isinstance(v, str) and v.strip().upper() in ("", "TODO")) or (isinstance(v, (list, dict)) and not v)  # noqa: E731
skel = lambda v: any(SKEL in s for s in leaves(v))  # noqa: E731

def role(p):
    s = p.suffix.lower()
    return "source" if s in (".svg", ".drawio", ".py") or (s == ".json" and "spec" in p.name) else "preview" if s == ".png" else "export" if s in (".pdf", ".tif", ".tiff", ".eps") else "record"

def fill(a):
    out, rp = Path(OUT), Path(OUT) / "result.json"
    res = load_json(rp)
    if not isinstance(res, dict):
        print("FAIL: result.json missing or not a JSON object: run `init` first, or rewrite it with python json.dump")
        return 0
    done = []
    files = sorted(q for q in out.rglob("*") if q.is_file() and q.name != "result.json" and not q.name.startswith("."))
    if empty(res.get("artifacts")) or skel(res.get("artifacts")):
        res["artifacts"] = [{"path": str(q.relative_to(out)), "role": role(q), "bytes": q.stat().st_size} for q in files][:120]
        done.append("artifacts")
    log = []
    for q in out.rglob("export_log*.jsonl"):
        for l in q.read_text(encoding="utf-8", errors="ignore").splitlines():
            try:
                log.append(json.loads(l))
            except Exception:
                pass
    last = {}
    for e in log:
        last[os.path.basename(str(e.get("svg")))] = e
    if (empty(res.get("export_checks")) or skel(res.get("export_checks"))) and last:
        ec = []
        for name, e in sorted(last.items()):
            sv = out / name
            fs, fam = [], ""
            try:
                root = ET.parse(str(sv)).getroot()
                fam = root.get("font-family") or ""
                fs = [float(x.get("font-size")) for x in root.iter() if x.get("font-size") and re.match(r"^[\d.]+$", x.get("font-size"))]
            except Exception:
                pass
            ec.append({"svg": name, "canvas_px": e.get("canvas_px"), "dpi": e.get("dpi"), "png": e.get("png") and os.path.basename(e["png"]),
                       "png_px": e.get("png_px"), "png_method": e.get("png_method"), "pdf": e.get("pdf") and os.path.basename(e["pdf"]),
                       "pdf_is_vector": e.get("pdf_is_vector"), "pdf_fonts": e.get("pdf_fonts"), "min_font_px": min(fs) if fs else None,
                       "font_stack_has_cjk": bool(re.search(r"CJK|Han|Hei|PingFang|YaHei|WenQuanYi", fam)), "render_log": (e.get("png_log") or []) + (e.get("pdf_log") or []),
                       "result": "ok" if e.get("png") and e.get("pdf") else "render failed: see render_log"})
        res["export_checks"] = ec
        done.append("export_checks")
    if empty(res.get("source_map")) or skel(res.get("source_map")):
        rows, srcf = [], []
        for q in sorted(out.rglob("*_elements.tsv")):
            srcf.append(str(q.relative_to(out)))
            for l in q.read_text(encoding="utf-8", errors="ignore").splitlines()[1:]:
                c = (l.split("\t") + ["", "", "", ""])[:4]
                rows.append({"figure": q.name.replace("_elements.tsv", ""), "id": c[0], "kind": c[1], "text": c[2], "src": c[3]})
        srcf += [str(q.relative_to(out)) for q in out.rglob("*source_map*.md")]
        if rows:
            res["source_map"] = {"files": srcf, "rows": rows[:200], "rows_total": len(rows)}
            done.append("source_map")
    if empty(res.get("change_log")) or skel(res.get("change_log")):
        cl = []
        for q in sorted(out.rglob("*diff*.json")):
            d = load_json(q, {})
            if isinstance(d, dict) and "changes" in d:
                cl.append({"file": str(q.relative_to(out)), "old": d.get("old"), "new": d.get("new"), "kept_ids": d.get("kept_ids"), "changes": d.get("changes", [])[:40]})
        if cl:
            res["change_log"] = cl
            done.append("change_log")
    if empty(res.get("versions")) or skel(res.get("versions")):
        case_dir = os.path.dirname(os.path.abspath(CASE))
        mats = []
        for r_, _, fs in os.walk(case_dir):
            mats += [os.path.relpath(os.path.join(r_, f), case_dir) for f in fs]
        res["versions"] = {"skill": "apparatus-route-figure-lite 1.1", "python": sys.version.split()[0],
                           "renderers": sorted({str(e.get(k)) for e in last.values() for k in ("png_method", "pdf_method") if e.get(k)}),
                           "materials": sorted(mats)[:40], "generated": time.strftime("%Y-%m-%d %H:%M:%S")}
        done.append("versions")
    try:
        rp.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception as e:
        print("FAIL: cannot write result.json: %s" % e)
        return 0
    left = [k for k in ("artifacts", "export_checks", "source_map", "change_log", "versions") if empty(res.get(k)) or skel(res.get(k))]
    print("filled: %s; still to write yourself: %s" % (", ".join(done) or "nothing (already present)", ", ".join(left) or "-"))
    print("change_log entries from diff files carry no purpose yet: add one (requested edit / 演示编辑，不属于正式图).")
    print("Now write the remaining fields (contract fields, components, connections, steps/stages, data_mapping, uncertainties, material_gaps, needs_human_confirmation, status, status_reasons) with a short python json load/update/dump, then run check.")
    elapsed()
    return 0

def svg_issues(p, mapped):
    f, w, nums, boxes = [], [], set(), []
    try:
        root = ET.parse(str(p)).getroot()
    except Exception as e:
        return ["%s: not well-formed XML: %s" % (p.name, e)], w
    try:
        W, H = [float(x) for x in re.split(r"[ ,]+", root.get("viewBox").strip())][2:4] if root.get("viewBox") else svg_size(str(p))
    except Exception:
        W, H = 1e9, 1e9
    ids = {el.get("id") for el in root.iter() if len(el.get("id") or "") > 2}
    texts = [el for el in root.iter() if el.tag.split("}")[-1] == "text"]
    fams = " ".join(el.get("font-family") or el.get("style") or "" for el in root.iter())
    mpl = "atplotlib" in open(str(p), encoding="utf-8", errors="ignore").read(1500)
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
            try:
                x, y = [float(re.split(r"[ ,]+", (el.get(k) or (el[0].get(k) if len(el) else "") or "0").strip())[0]) for k in "xy"]
            except Exception:
                continue  # % / em coordinates: skip geometry checks for this text
            lw = max(sum(fs * (1.0 if ord(c) > 0x2E80 else 0.56) for c in ln) for ln in lines)
            x0 = x - {"middle": lw / 2, "end": lw}.get(el.get("text-anchor"), 0)
            boxes.append((x0, y - fs * 0.8, x0 + lw, y - fs * 0.8 + fs * 1.2 * len(lines), s[:30]))
    for i, b in enumerate(boxes[:400]):
        if b[0] < -2 or b[1] < -2 or b[2] > W + 2 or b[3] > H + 2:
            w.append("%s: text may overflow the %dx%d canvas: %r" % (p.name, W, H, b[4]))
        w += ["%s: texts overlap: %r / %r" % (p.name, b[4], c[4]) for c in boxes[i + 1:400] if min(b[2], c[2]) - max(b[0], c[0]) > 3 and min(b[3], c[3]) - max(b[1], c[1]) > 3]
    if re.search(r"[⺀-鿿]", "".join("".join(t.itertext()) for t in texts)) and not re.search(r"CJK|Han|Hei|Song|YaHei|PingFang|WenQuanYi|SC|Unicode|Fallback|AR PL|Ming|Gothic", fams):
        f.append("%s: Chinese text but no CJK font in font-family (tofu risk)" % p.name)
    if any(el.tag.endswith("image") for el in root.iter()):
        w.append("%s: contains raster <image>; the figure itself must be vector" % p.name)
    miss = sorted(n for n in nums if n not in mapped)
    if miss and not mpl:
        w.append("%s: numbers on the figure not found in source map / result.json: %s" % (p.name, miss[:8]))
    return f, w

def check(a):
    out, F, Wn = Path(OUT), [], []
    case = load_json(CASE)
    try:
        raw = (out / "result.json").read_text(encoding="utf-8")
        res = json.loads(raw)
    except Exception as e:
        print("FAIL: cannot read result.json as JSON: %s  (rewrite it with python json.dump)" % e)
        elapsed()
        return 1
    if not isinstance(res, dict):
        print("FAIL: result.json must be a JSON object")
        return 1
    if case is None:
        Wn.append("cannot read case.json (%s): contract fields not checked" % CASE)
    if len(raw) > 400000 or "data:image" in raw or "base64," in raw:
        F.append("result.json is %d KB or embeds base64 data: keep it < 400 KB and reference files by path" % (len(raw) // 1024))
    cid = case_id(case)
    if cid is not None and str(res.get("case_id")) != str(cid):
        F.append("case_id is %r, case.json says %r" % (res.get("case_id"), cid))
    allowed, fl = set(WORDS), sum((fields(c) for c in contracts(case)), [])
    for k, desc in fl:
        if k not in ("case_id", "caseId") and (k not in res or empty(res.get(k))):
            F.append("contract field missing or empty: %s" % k)
        elif k not in ("case_id", "caseId") and skel(res.get(k)):
            F.append("contract field %r still holds the skeleton text %r: fill it with the real result" % (k, SKEL))
        if norm(k) in ("status", "状态"):
            allowed = {x.lower() for x in re.findall(r"[A-Za-z]+", desc) if x.lower() in WORDS} or allowed
    st = str(res.get("status", ""))
    if st.lower() not in allowed:
        F.append("status %r must be exactly one word of %s; reasons go to status_reasons" % (st, sorted(allowed)))
    if st.lower() not in ("complete", "completed", "success", "done") and (empty(res.get("status_reasons")) or skel(res.get("status_reasons"))):
        F.append("status is not complete but status_reasons is empty or still the skeleton text")
    Wn += ["standard block %r missing or empty (run `fill`)" % k for k in ("artifacts", "source_map", "change_log", "export_checks") if empty(res.get(k)) or skel(res.get(k))]
    skip = re.compile(r"gap|uncertain|confirm|reason|note|limit|缺|待确认|不确定", re.I)
    F += ["placeholder text (TODO/TBC/lorem/待补充/{{ }}) left in result.json field %r" % k for k, v in res.items() if not skip.search(k) and BAD.search("\n".join(leaves(v)))]
    arts = [x.get("path") if isinstance(x, dict) else x for x in (res.get("artifacts") or []) if isinstance(x, (str, dict))] if isinstance(res.get("artifacts"), list) else []
    F += ["artifact listed but missing: %s" % p for p in arts if isinstance(p, str) and not (out / p).exists() and not Path(p).exists()]
    mapped = raw
    for q in out.rglob("*"):
        if q.suffix in (".md", ".csv", ".tsv", ".json") and q.is_file():
            try:
                with open(str(q), encoding="utf-8", errors="ignore") as fh:
                    mapped += fh.read(2000000)
            except Exception:
                pass
    failed_render = set()
    for q in out.rglob("export_log*.jsonl"):
        for l in q.read_text(encoding="utf-8", errors="ignore").splitlines():
            try:
                e = json.loads(l)
                (failed_render.add if not (e.get("png") or e.get("pdf")) else failed_render.discard)(os.path.basename(str(e.get("svg"))))
            except Exception:
                pass
    for src in [q for q in out.rglob("*") if q.suffix.lower() in (".svg", ".pptx", ".drawio", ".py", ".docx")]:
        try:
            if not any(valid(str(q), q.suffix.lower()[1:]) for q in src.parent.glob((src.stem if src.suffix.lower() != ".py" else "") + "*") if q.suffix.lower() in (".png", ".pdf")):
                msg = "%s has no real PNG/PDF preview with the same stem" % src.name
                if src.suffix.lower() == ".py":
                    Wn.append(msg)
                elif src.name in failed_render and st.lower() not in ("complete", "completed", "success", "done"):
                    Wn.append(msg + " (render failure is logged in export_log.jsonl; keep it in export_checks/status_reasons)")
                else:
                    F.append(msg + " (run render; if every renderer fails it is logged and this becomes a warning with status partial)")
            if src.suffix.lower() == ".svg":
                f, w = svg_issues(src, mapped)
                F, Wn = F + f, Wn + w
        except Exception as e:
            Wn.append("%s: could not be checked (%s)" % (src.name, str(e)[:80]))
    if not list(out.rglob("export_log*")):
        Wn.append("no export_log.jsonl: run `export_check.py render`")
    print("\n".join(["WARN: " + x for x in Wn[:30]] + ["FAIL: " + x for x in F[:30]]) or "no warnings")
    print("%s: %d contract field(s), status=%s, %d fail / %d warn" % ("FAIL" if F else "PASS", len(fl), st or "?", len(F), len(Wn)))
    if F:
        print("Fix the FAIL lines (at most 2 check rounds). Anything you cannot fix: describe it in status_reasons, status partial, and stop.")
    elapsed()
    return 1 if F else 0

CMDS = {"init": init, "tools": tools, "pdf": pdf, "render": render, "fill": fill, "check": check}
if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in CMDS:
        print(__doc__)
        sys.exit(0)
    try:
        rc = CMDS[sys.argv[1]](sys.argv[2:]) or 0
    except Exception as e:  # never leave the agent with a traceback loop
        import traceback
        tb = traceback.extract_tb(sys.exc_info()[2])[-1]
        print("ERROR in export_check %s: %s: %s (line %s). Continue with the next step and record this in run_notes." % (sys.argv[1], type(e).__name__, str(e)[:200], tb.lineno))
        rc = 0 if sys.argv[1] != "check" else 1
    sys.exit(rc)
