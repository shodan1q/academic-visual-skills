#!/usr/bin/env python3
"""run.py (stdlib, py3.8+): the two-call front end of this Skill. Env CASE_JSON / WORK_DIR / OUT_DIR first; else /input/case.json, /app/work, /app/output.
  start          print the inputs, PDF/text -> WORK_DIR/src.txt (numbered lines, passages naming the work order's terms), partial result.json
  build fig.txt  line spec (or JSON spec) -> figure.svg + PNG + PDF + content map + pixel check + edited version + result.json
Every stage is optional and time-boxed: a stage that fails is recorded in result.json and the next one still runs.
Line spec: one item per line (title / color / comp / node / edge / note / req / exc / edit / summary), fields separated by '|',
'@12' or '@12-15' at the end = the lines of src.txt the item comes from. Full format: SKILL.md."""
import csv, hashlib, json, os, re, shutil, subprocess, sys, time
from pathlib import Path
HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
CJ = Path(os.environ.get("CASE_JSON") or "/input/case.json")
IN, WORK, OUT = CJ.parent, Path(os.environ.get("WORK_DIR") or "/app/work"), Path(os.environ.get("OUT_DIR") or "/app/output")
T0 = time.time()
KINDS = ("gene", "mrna", "protein", "complex", "family", "small_molecule", "ion", "cell", "process")
TYPES = ("activate", "inhibit", "bind", "modify", "transport", "line")
EVS = ("direct", "indirect", "hypothesis")
BLUE = {0: [], 1: ["#2166AC"], 2: ["#2166AC", "#67A9CF"], 3: ["#2166AC", "#4393C3", "#92C5DE"]}
RED = {0: [], 1: ["#B2182B"], 2: ["#EF8A62", "#B2182B"], 3: ["#F4A582", "#D6604D", "#B2182B"]}

def r1(x):
    return float("%.1g" % x) if x else 0.0

def scale(cs, nodes, notes):
    """data-driven breaks when none are given (or when the given ones put every coloured node in one bin); colours follow the sign of each bin"""
    try:
        rows = {r.get(cs.get("key"), "").strip(): float(r[cs["value"]]) for r in csv.DictReader(open(cs["csv"], encoding="utf-8-sig")) if r.get(cs.get("value"), "").strip()}
    except Exception:
        return
    vals = [rows[n["data"]] for n in nodes if isinstance(n, dict) and n.get("data") in rows] or list(rows.values())
    br = sorted(cs.get("breaks") or [])
    binof = lambda v: sum(1 for b in br if v >= b)  # noqa: E731
    if vals and (not br or (len(set(vals)) >= 3 and len({binof(v) for v in vals}) == 1)):
        lo, hi, old = min(vals), max(vals), br
        m = max(abs(lo), abs(hi)) or 1.0
        br = [-r1(m * 0.5), -r1(max(m * 0.12, 0.3)), r1(max(m * 0.12, 0.3)), r1(m * 0.5)] if lo < -0.3 * m and hi > 0.3 * m else \
            [r1(m * 0.15), r1(m * 0.4), r1(m * 0.75)] if hi > 0 and lo > -0.3 * m else [-r1(m * 0.75), -r1(m * 0.4), -r1(m * 0.15)]
        br = sorted(set(br))
        cs.pop("colors", None)
        msg = "colour breaks %s chosen from the data range %g..%g of the coloured nodes%s" % (br, lo, hi, " (the given breaks %s put every coloured node in one bin)" % old if old else "")
        notes.setdefault("_defaults", []).append(msg)
        print("   NOTE: " + msg)
    cs["breaks"] = br
    if br and not cs.get("colors"):
        z = next((i for i in range(len(br) + 1) if (i == 0 or br[i - 1] <= 0) and (i == len(br) or br[i] >= 0)), None)
        nb, nr = (z, len(br) - z) if z is not None else ((len(br) + 1, 0) if br[-1] < 0 else (0, len(br) + 1))
        if nb <= 3 and nr <= 3:
            cs["colors"] = BLUE[nb] + (["#CCCCCC"] if z is not None else []) + RED[nr]

STOP = set("""figure legend arrow arrows label labels export format colour color compartment compartments nodes edges source paper table italic upright style distinguish include shown required mechanism pathway relations request element changed""".split())

try:
    sys.path.insert(0, HERE)
    from svgfig import TSYN, KSYN, ESYN
except Exception:  # the builder still normalises what it is given
    TSYN = KSYN = ESYN = ()

def syn(v, table):
    t = str(v or "").strip().lower().replace("-", "_").replace(" ", "_")
    return next((k for k, rx in table if re.search(rx, t)), None)

def sh(args, t=120):
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=t, errors="replace")
        return p.returncode, (p.stdout or "") + (("\n" + p.stderr[-400:]) if p.returncode and p.stderr else "")
    except subprocess.TimeoutExpired:
        return 124, "timed out after %ds" % t
    except Exception as e:
        return 1, "%s: %s" % (type(e).__name__, str(e)[:200])

def el():
    return "%.0fs" % (time.time() - T0)

def jload(p, dv=None):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8-sig"))
    except Exception:
        return dv

def walk(o, pat):
    """first scalar value in nested JSON whose key matches pat"""
    if isinstance(o, dict):
        for k, v in o.items():
            if re.search(pat, str(k), re.I) and isinstance(v, (int, float, str)) and str(v).strip():
                return v
        o = list(o.values())
    for v in o if isinstance(o, list) else []:
        r = walk(v, pat)
        if r is not None:
            return r
    return None

def strings(o):
    if isinstance(o, str):
        return [o]
    if isinstance(o, dict):
        return sum((strings(v) for v in o.values()), [])
    return sum((strings(v) for v in o), []) if isinstance(o, list) else []

def inputs():
    fs = sorted(p for p in IN.rglob("*") if p.is_file()) if IN.is_dir() else []
    return [p for p in fs if "/." not in str(p)][:200]

def workorder(fs):
    js = [p for p in fs if p.suffix.lower() == ".json" and p.resolve() != CJ.resolve()]
    js.sort(key=lambda p: (0 if re.search(r"work.?order|order|工单", p.name, re.I) else 1, len(str(p))))
    return js[0] if js else None

def pdf_text(p):
    if shutil.which("pdftotext"):
        rc, o = sh(["pdftotext", "-layout", str(p), "-"], 90)
        if rc == 0 and len(o.strip()) > 200:
            return o, "pdftotext -layout"
    for mod, code in (("fitz", "import fitz,sys;d=fitz.open(sys.argv[1]);sys.stdout.write('\\f'.join(pg.get_text() for pg in d))"),
                      ("pypdf", "import pypdf,sys;r=pypdf.PdfReader(sys.argv[1]);sys.stdout.write('\\f'.join((pg.extract_text() or '') for pg in r.pages))")):
        rc, o = sh([PY, "-c", code, str(p)], 120)
        if rc == 0 and len(o.strip()) > 200:
            return o, mod
    return "", None

def keywords(texts):
    sym, words = [], []
    for t in texts:
        for w in re.findall(r"[A-Za-zα-ωΑ-Ω][A-Za-z0-9α-ωΑ-Ω\-]{1,24}", t):
            if re.search(r"[A-Z0-9α-ω]", w[1:]) and not re.match(r"^(PNG|PDF|SVG|DPI|JSON|CSV|RGB|CMYK|ID|WO|SIM\d*|[A-Z]?\d+)$", w, re.I):
                sym += [w.strip("-")] + [x for x in w.split("-") if len(x) >= 3 and re.search(r"[A-Z0-9]", x[1:])]
            elif len(w) >= 5 and w.lower() not in STOP:
                words.append(w.lower())
    uniq = lambda xs: list(dict.fromkeys(xs))  # noqa: E731
    return uniq(sym)[:40], uniq(words)[:40]

def start(a):
    WORK.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    fs = inputs()
    print("== inputs under %s (work %s, output %s)" % (IN, WORK, OUT))
    for p in fs:
        try:
            print("  %-48s %8d B  sha256 %s" % (p.relative_to(IN), p.stat().st_size, hashlib.sha256(p.read_bytes()).hexdigest()[:12]))
        except Exception:
            pass
    case = jload(CJ)
    print("== case.json\n%s" % (json.dumps(case, ensure_ascii=False)[:2500] if case is not None else "(missing or not JSON: %s)" % CJ))
    wo = workorder(fs)
    wtxt = ""
    if wo:
        wtxt = wo.read_text(encoding="utf-8", errors="replace")
        w = jload(wo)
        print("== work order %s\n%s" % (wo.relative_to(IN), (json.dumps(w, ensure_ascii=False, indent=1) if w is not None else wtxt)[:6000]))
    for p in fs:
        if p.name.lower() == "task.md":
            t = p.read_text(encoding="utf-8", errors="replace")
            k = max(t.rfind("组织方具体输入修订"), t.rfind("Concrete source-bound"))
            print("== task.md (%d chars; revision note)\n%s" % (len(t), (t[k:] if k >= 0 else t[-700:])[:900].strip()))
    parts, how = [], []
    for p in [p for p in fs if p.suffix.lower() == ".pdf"][:4]:
        t, m = pdf_text(p)
        how.append("%s: %s" % (p.name, m or "NO TEXT EXTRACTED (record material_missing)"))
        if t:
            parts.append((p.name, t))
    for p in [p for p in fs if p.suffix.lower() in (".txt", ".md", ".tex", ".html", ".xml") and p.name.lower() != "task.md"][:6]:
        if p.stat().st_size < 2000000:
            parts.append((p.name, p.read_text(encoding="utf-8", errors="replace")))
            how.append("%s: read as text" % p.name)
    src = "".join(("" if len(parts) == 1 else "##### %s #####\n" % n) + t.rstrip("\n") + "\n" for n, t in parts)
    lines = src.replace("\f", "").split("\n")
    if src:
        (WORK / "src.txt").write_text(src, encoding="utf-8")
    sym, words = keywords(strings(jload(wo, wtxt) if wo else []) + strings(case if isinstance(case, (dict, list)) else []))
    print("== source text -> %s (%d lines, %d chars; %s)" % (WORK / "src.txt", len(lines), len(src), "; ".join(how) or "no PDF/text source found"))
    num = lambda i: "%4d| %s" % (i + 1, lines[i].rstrip()[:230])  # noqa: E731
    if src and len(src) <= 16000:
        print("\n".join(num(i) for i in range(len(lines)) if lines[i].strip()))
    elif src:
        end = len(lines)
        for i in range(len(lines) - 1, int(len(lines) * 0.5), -1):  # the reference list is not evidence for a relation
            if re.match(r"^\s*(references|bibliography|参考文献|literature cited)\s*$", lines[i], re.I):
                end = i
        low_src = src.lower()
        sym = [s for s in sym if s.lower() in low_src]  # ids and file names from the work order are not search terms
        rx_s = [re.compile(r"(?<![A-Za-z0-9])%s(?![A-Za-z])" % re.escape(s), re.I) for s in sym]
        rx_w = [re.compile(re.escape(w[:max(5, len(w) - 2)]), re.I) for w in words]
        wt = [0.0] * len(lines)
        for i in range(end):
            ln = lines[i]
            if len(ln.strip()) > 25:
                wt[i] = 2.0 * sum(1 for r in rx_s if r.search(ln)) + 0.5 * sum(1 for r in rx_w if r.search(ln))
        symhit = [any(r.search(lines[i]) for r in rx_s) if i < end else False for i in range(len(lines))]
        para = [sum(wt[max(0, i - 2):i + 3]) if (not sym or any(symhit[max(0, i - 2):i + 3])) else 0 for i in range(len(lines))]
        keep, used = set(), 0
        for i in sorted(range(len(lines)), key=lambda i: -para[i]):
            if para[i] < 2 or used > 11000:
                break
            for j in range(max(0, i - 2), min(len(lines), i + 3)):
                if j not in keep and lines[j].strip():
                    keep.add(j)
                    used += min(len(lines[j]), 230) + 6
        ks = sorted(keep)
        for x, y in zip(ks, ks[1:]):  # short gaps inside a passage are cheaper to print than to fetch
            if 1 < y - x <= 7:
                keep.update(j for j in range(x + 1, y) if lines[j].strip())
        print("-- passages that mention the work-order terms (line numbers of src.txt; read more with: sed -n '120,160p' %s)" % (WORK / "src.txt"))
        prev = None
        for i in sorted(keep):
            if prev is not None and i > prev + 1:
                print("   ...")
            print(num(i))
            prev = i
        idx = []
        for s, r in zip(sym, rx_s):
            hit = [i + 1 for i in range(end) if r.search(lines[i])]
            idx.append("%s: %s" % (s, ",".join(map(str, hit[:6])) + ("…(%d)" % len(hit) if len(hit) > 6 else "") if hit else "NOT FOUND"))
        print("-- term index (first lines): " + "; ".join(idx))
    for p in [p for p in fs if p.suffix.lower() in (".csv", ".tsv")][:4]:
        try:
            rows = list(csv.reader(open(str(p), encoding="utf-8-sig", errors="replace"), delimiter="\t" if p.suffix.lower() == ".tsv" else ","))
            low = {s.lower() for s in sym}
            hit = [r for r in rows[1:] if any(c.strip().lower() in low for c in r[:3])]
            show = rows[1:] if len(rows) <= 41 else (hit[:30] if hit else rows[1:9])
            hit = hit if len(rows) > 41 else []
            print("== data %s: %d rows; columns %s\n%s" % (p.relative_to(IN), len(rows) - 1, rows[0] if rows else [], "\n".join("  " + ",".join(r) for r in show)))
            if hit:
                print("  (rows above = work-order terms found in the table; other rows not shown)")
        except Exception as e:
            print("== data %s: unreadable (%s)" % (p.name, e))
    sh([PY, os.path.join(HERE, "export_check.py"), "skeleton"], 30)
    have = [b for b in ("rsvg-convert", "inkscape", "magick", "convert", "soffice", "chromium", "pdftotext") if shutil.which(b)]
    print("== result.json skeleton written (status partial). renderers here: %s (built-in fallback always available)" % (", ".join(have) or "none"))
    print("NEXT: write %s (line spec, see SKILL.md) and run: python3 %s build %s   [%s]" % (WORK / "figure.txt", os.path.abspath(__file__), WORK / "figure.txt", el()))
    return 0

# ---------------------------------------------------------------- line spec -> JSON spec + notes
def src_of(tail):
    t = tail.strip()
    m = re.match(r"^L?(\d+)\s*(?:[-–~]\s*L?(\d+))?$", t)
    if m:
        return "src.txt:L%s" % m.group(1) + ("-L%s" % m.group(2) if m.group(2) else "")
    return t

AT = re.compile(r"(?:^|\s)@\s*(L?\d+(?:\s*[-\u2013~,]\s*L?\d+)*|[\w./\-]+\.(?:csv|tsv|txt|md|json|pdf)\S*|work.?order|edit.?request|工单)", re.I)

def cut(line, keep=False):
    """'body @12-15 more' -> ('body more', 'src.txt:L12-L15'); keep=True leaves the pointer readable inside the text"""
    m = AT.search(line)
    if not m:
        return line, None
    first = re.split(r"\s*,\s*", m.group(1))[0]
    body = re.sub(r"\s+\|", " |", (line[:m.start()] + " " + AT.sub(" ", line[m.end():])).strip())
    return body + (" (L%s)" % m.group(1).lstrip("L") if keep and first.lstrip("L")[:1].isdigit() else ""), src_of(first)

def find_csv(name):
    name = str(name).strip().strip("'\"")
    for c in (Path(name), IN / name, IN / "data" / name, WORK / name):
        if c.is_file():
            return str(c)
    hit = [p for p in inputs() if p.name == os.path.basename(name)] or [p for p in inputs() if p.suffix.lower() in (".csv", ".tsv")]
    return str(hit[0]) if hit else name

def parse(text, warn):
    sp = {"canvas": {}, "panels": [], "nodes": [], "edges": [], "texts": []}
    notes = {"compliance_checks": [], "exceptions": []}
    edits, pid = [], set()
    for no, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith(("#", "//", "```")):
            continue
        line, src = cut(line, bool(re.match(r"(req|exc)\b", line, re.I)))
        if re.match(r"(req|exc)\b", line, re.I):
            src = None  # the pointer stays in the sentence
        m = re.match(r"^(comp|compartment|panel|node|edge|edit|req|exc|note|color|colour|colorscale)\b\s*:?\s*(.*)$", line, re.I)
        try:
            if not m:
                k, _, v = line.partition(":")
                k, v = k.strip().lower().replace(" ", "_"), v.strip()
                if k in ("title",):
                    sp["canvas"]["title"] = v
                    if src:
                        sp["canvas"]["src"] = src
                elif k in ("width_mm", "min_font_pt", "dpi"):
                    sp["canvas"][k] = float(re.sub(r"[^\d.]", "", v) or 0) or None
                elif k in ("legend", "legend_at"):
                    sp["canvas"]["legend_at"] = v.lower()
                elif k in ("edit_request", "summary", "caption", "status", "species"):
                    notes[k] = v
                elif k in ("status_reason", "status_reasons"):
                    notes.setdefault("status_reasons", []).append(v)
                else:
                    warn.append("line %d not understood (skipped): %s" % (no, raw.strip()[:70]))
                continue
            kw, rest = m.group(1).lower(), m.group(2).strip()
            if kw == "edge":  # the inhibition arrow contains the field separator
                rest = re.sub(r"^(\S+)\s*(?:-\|\||-\|)\s*", lambda g: g.group(1) + " \u22a3 " + ("| " if g.group(0).rstrip().endswith("||") else ""), rest, 1)
            if kw in ("node", "comp", "edit"):  # 'cy alias=X' written without the separator
                rest = re.sub(r"(?<=[^|\s])\s+(?=(?:alias|aliases|mods?|data|col|rank|fill|stroke|label|in)=)", " | ", rest)
            f = [x.strip() for x in rest.split("|")]
            if kw in ("comp", "compartment", "panel"):
                head, _, title = f[0].partition(":")
                hm = re.match(r"^(\S+)(?:\s+in\s+(\S+))?$", head.strip())
                p = {"id": hm.group(1) if hm else re.sub(r"\W+", "-", head.strip()), "title": title.strip() or head.strip()}
                if hm and hm.group(2):
                    p["in"] = hm.group(2)
                for x in f[1:]:
                    k, eq, v = x.partition("=")
                    if eq:
                        p["in" if k.strip().lower() in ("in", "parent", "inside") else k.strip().lower()] = v.strip()
                    elif x.lower() == "membrane":
                        p["membrane"] = True
                if src:
                    p["src"] = src
                pid.add(p["id"])
                sp["panels"].append(p)
            elif kw == "node":
                head, c0, lab = f[0].partition(":")
                if not c0 and len(f) > 2 and f[1] not in pid and f[1].lower() not in KINDS and "=" not in f[1]:
                    lab = f.pop(1)  # 'node ins | Insulin | protein | ex'
                n = {"id": re.sub(r"[^\w.\-]+", "-", head.strip()), "label": lab.strip() or head.strip()}
                for x in f[1:]:
                    k, eq, v = x.partition("=")
                    k, v = k.strip().lower(), v.strip()
                    if eq and k in ("mods", "mod", "alias", "aliases"):
                        n["mods" if k.startswith("mod") else "aliases"] = [y.strip() for y in v.split(",") if y.strip()]
                    elif eq and k in ("col", "rank"):
                        n[k] = int(float(v))
                    elif eq:
                        n[{"compartment": "comp", "in": "comp", "type": "kind"}.get(k, k)] = v
                    elif x in pid:
                        n["comp"] = x
                    elif x.lower().replace(" ", "_") in KINDS:
                        n["kind"] = x.lower().replace(" ", "_")
                    elif x.lower() in ("dash", "bold"):
                        n[x.lower()] = True
                    elif x and "kind" not in n and syn(x, KSYN):
                        n["kind"] = syn(x, KSYN)
                    elif x and "comp" not in n:
                        n["comp"] = x  # a compartment title; matched to a compartment by the builder
                    elif x:
                        n.setdefault("kind", x)
                if src:
                    n["src"] = src
                sp["nodes"].append(n)
            elif kw == "edge":
                h0 = re.sub(r"^[\w.\-]+\s*:\s*(?=\S+\s*(?:-o|--|->|=>|→|⊣|>))", "", f[0])  # 'edge e1: A -> B'
                h0, c0, t0 = h0.partition(":")  # 'edge A -> B: inhibit'
                if c0 and t0.strip():
                    f.insert(1, t0.strip())
                hm = re.match(r"^(\S+?)\s*(-o|--|->|=>|→|⊣|>)\s*(\S+)$", h0.strip())
                if not hm:
                    warn.append("line %d: edge needs 'A -> B | type | label' (skipped): %s" % (no, raw.strip()[:70]))
                    continue
                e = {"from": hm.group(1), "to": hm.group(3), "type": {"-|": "inhibit", "⊣": "inhibit", "-o": "bind", "--": "line"}.get(hm.group(2), "activate")}
                typed, soft = False, None
                for x in f[1:]:
                    lx = x.lower().strip()
                    k, eq, v = x.partition("=")
                    if lx in EVS or lx in ("indirect evidence", "hypothetical", "untested", "putative"):
                        e["evidence"] = lx if lx in EVS else syn(lx, ESYN) or "hypothesis"
                    elif not typed and (lx in TYPES or (len(lx.split()) <= 2 and syn(lx, TSYN))):
                        t2 = lx if lx in TYPES else syn(lx, TSYN)
                        if not (hm.group(2) in ("-|", "\u22a3") and t2 == "activate"):
                            e["type"] = t2
                        typed = True
                        if lx not in TYPES:
                            soft = x  # the author's own word stays as the label unless a label follows
                    elif lx == "feedback":
                        e["feedback"] = True
                    elif eq and k.strip().lower() in ("label", "type", "evidence", "id"):
                        e[k.strip().lower()] = v.strip()
                    elif x and "label" not in e:
                        e["label"] = x
                if soft and "label" not in e:
                    e["label"] = soft
                e["id"] = e.get("id") or "e-%s-%s" % (e["from"], e["to"])
                if src:
                    e["src"] = src
                sp["edges"].append(e)
            elif kw == "note":
                sp["texts"].append(dict({"id": "t-note%d" % (len(sp["texts"]) + 1), "text": rest}, **({"src": src} if src else {})))
            elif kw in ("color", "colour", "colorscale"):
                f = f + [""] * 5
                br = [float(x) for x in re.findall(r"-?\d+\.?\d*", f[3])]
                cols = next((re.findall(r"#[0-9A-Fa-f]{6}", x) for x in f[4:] if "#" in x), None)
                title = next((x for x in f[4:] if x and "#" not in x), "%s (%s)" % (f[2], os.path.basename(f[0])))
                sp["canvas"]["colorscale"] = {"csv": find_csv(f[0]), "key": f[1], "value": f[2], "breaks": br, "title": title}
                if cols and len(cols) == len(br) + 1:
                    sp["canvas"]["colorscale"]["colors"] = cols
            elif kw == "req":
                f = f + [""] * 4
                res = f[1].lower() if f[1].lower() in ("pass", "partial", "fail") else "partial"
                pm = re.search(r"\s*\(L[^)]*\)\s*$", f[2])
                if pm:
                    f[2], f[3] = f[2][:pm.start()], (f[3] + " " + pm.group(0).strip()).strip()
                ids = [x for x in re.split(r"[,\s]+", f[2]) if re.match(r"^[\w.\-]+$", x)] if f[1].lower() in ("pass", "partial", "fail") else []
                notes["compliance_checks"].append({"requirement": f[0], "result": res, "element_ids": ids,
                                                   "evidence": " | ".join(x for x in f[3:] if x)})
            elif kw == "exc":
                f = f + [""] * 3
                notes["exceptions"].append({"category": f[0], "detail": f[1], "handling": f[2]} if f[1] else
                                           {"category": "undecidable", "detail": f[0], "handling": "recorded"})
            elif kw == "edit":
                ops = {}
                for x in f[1:]:
                    k, eq, v = x.partition("=")
                    if x:
                        ops[k.strip().lower()] = v.strip() if eq else True
                edits.append((f[0].split(":")[0].strip(), ops))
        except Exception as ex:
            warn.append("line %d skipped (%s): %s" % (no, type(ex).__name__, raw.strip()[:70]))
    return sp, notes, edits

def prepare(path, warn):
    text = Path(path).read_text(encoding="utf-8-sig", errors="replace")
    edits = []
    if text.lstrip().startswith("{"):
        sp = jload(path)
        if not isinstance(sp, dict):
            warn.append("%s starts with '{' but is not valid JSON: fix it or use the line format" % path)
            sp = {}
        notes = {k: sp.pop(k) for k in ("compliance_checks", "exceptions", "edit_request", "summary", "caption", "status", "status_reasons", "species") if k in sp}
        notes.setdefault("compliance_checks", sp.pop("checks", []))
        notes.setdefault("exceptions", [])
        for e in sp.pop("edits", []) or []:
            if isinstance(e, dict) and e.get("id"):
                edits.append((e["id"], {k: v for k, v in e.items() if k != "id"}))
        sp.setdefault("canvas", {})
        cs = sp["canvas"].get("colorscale") if isinstance(sp["canvas"], dict) else None
        if isinstance(cs, dict) and cs.get("csv"):
            cs["csv"] = find_csv(cs["csv"])
    else:
        sp, notes, edits = parse(text, warn)
    cv = sp["canvas"] if isinstance(sp.get("canvas"), dict) else {}
    sp["canvas"] = cv
    wo = workorder(inputs())
    w = [jload(wo, {}) if wo else {}, jload(CJ, {})]
    for k, pat, dv in (("width_mm", r"width.?mm|宽度", 180), ("min_font_pt", r"min.?font|最小字号", 6), ("dpi", r"^dpi$|resolution|分辨率", 300)):
        if not cv.get(k):
            v = walk(w, pat)
            try:
                cv[k] = float(re.sub(r"[^\d.]", "", str(v))) if v is not None else dv
                if v is None:
                    notes.setdefault("_defaults", []).append("%s=%s (not in the work order; default)" % (k, dv))
            except ValueError:
                cv[k] = dv
    if not cv.get("title"):
        cv["title"] = str(walk(w, r"^title$|figure.?title") or "")[:120] or "Mechanism figure"
    cs = cv.get("colorscale")
    if isinstance(cs, dict):  # gene / mRNA nodes named like a table key take their colour from the table without being told
        try:
            keys = {r.get(cs.get("key"), "").strip() for r in csv.DictReader(open(cs["csv"], encoding="utf-8-sig"))}
            for n in sp.get("nodes", []):
                if isinstance(n, dict) and "data" not in n and str(n.get("kind", "")).lower() in ("gene", "mrna") and str(n.get("label", "")).strip() in keys:
                    n["data"] = str(n["label"]).strip()
        except Exception:
            pass
    if isinstance(cs, dict):
        scale(cs, sp.get("nodes", []), notes)
    if not notes.get("edit_request"):
        er = walk(w, r"edit.?request|revision.?request|modif|修改请求|编辑请求")
        if er:
            notes["edit_request"] = str(er)
    reqs = next((v for d in w if isinstance(d, dict) for k, v in d.items() if re.search(r"requirement|must|constraint|要求", k, re.I) and isinstance(v, list)), [])
    if not notes["compliance_checks"] and reqs:
        notes["compliance_checks"] = [{"requirement": str(r)[:300], "result": "partial", "element_ids": [],
                                       "evidence": "not assessed item by item in this run (no req line in the spec); see content_map"} for r in reqs]
    return sp, notes, edits

def stage(name, args, t):
    t1 = time.time()
    rc, o = sh(args, t)
    print("[%s] %s: %s (%.0fs)" % (el(), name, "ok" if rc == 0 else "rc=%d" % rc, time.time() - t1))
    return rc, o

def show(o, n=14, pat=r"^(WARN|FAIL|NOTE)"):
    ls = [l for l in o.splitlines() if re.search(pat, l)]
    for l in ls[:n]:
        print("   " + l[:260])
    if len(ls) > n:
        print("   ... %d more (see figure_content_map.json warnings)" % (len(ls) - n))

def export(svg, dpi, budget):
    env_t = str(int(max(20, min(90, budget / 3))))
    os.environ["EC_TOOL_T"] = env_t
    rc, o = stage("render %s" % os.path.basename(svg), [PY, os.path.join(HERE, "export_check.py"), "render", svg, "--dpi", str(int(dpi))], int(budget))
    m = re.findall(r'"(png_method|pdf_method)": "?([\w\-]+)', o)
    print("   " + (", ".join("%s=%s" % x for x in m) or o.strip()[-200:]))
    rc2, o2 = stage("pixel check", [PY, os.path.join(HERE, "pixcheck.py"), svg], 90)
    show(o2, 5)
    print("   " + (o2.strip().splitlines() or ["(no output)"])[-1][:240])

def apply_edits(res, edits, warn):
    nm = lambda s: re.sub(r"[^a-z0-9]", "", str(s).lower())  # noqa: E731
    done = []
    objs = [o for k in ("nodes", "edges", "panels", "texts") for o in res.get(k, []) if isinstance(o, dict)]
    for tid, ops in edits:
        hit = [o for o in objs if o.get("id") == tid] or [o for o in objs if nm(o.get("id")) == nm(tid)] or \
              [o for o in objs if nm(o.get("label") or o.get("title") or o.get("text")) == nm(tid)] or \
              [o for o in objs if nm(o.get("id")).endswith(nm(tid)) and nm(tid)]
        if tid.lower() in ("title", "figure-title"):
            hit = [res["canvas"]]
            ops = {("title" if k in ("label", "text") else k): v for k, v in ops.items()}
        if not hit:
            warn.append("edit: no element with id or label %r (ids: %s ...)" % (tid, ", ".join(str(o.get("id")) for o in objs[:12])))
            continue
        for o in hit:
            for k, v in ops.items():
                k = {"text": "label", "name": "label", "dashed": "dash", "color": "fill", "colour": "fill", "border": "stroke"}.get(k, k)
                if k == "label" and "label" not in o and ("title" in o or "text" in o):
                    k = "title" if "title" in o else "text"
                if k in ("remove", "delete"):
                    for key in ("nodes", "edges", "texts"):
                        res[key] = [x for x in res.get(key, []) if x is not o and x.get("from") != o.get("id") and x.get("to") != o.get("id")]
                    continue
                if k == "fill" and "data" in o:
                    o.pop("data")
                    warn.append("edit: %s no longer shows its data value (fill set by hand)" % o.get("id"))
                if k == "label" and "w" in o and len(str(v)) > len(str(o.get("label", ""))):
                    o["w"] = round(float(o["w"]) * min(1.9, max(1.0, (len(str(v)) + 2.0) / max(4, len(str(o.get("label", ""))) + 2.0))), 1)
                o[k] = v
            done.append({"id": o.get("id"), "set": ops})
    return done

def build(a):
    WORK.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    warn = []
    if not a or not os.path.exists(a[0]):
        print("FAIL: spec file not found: %s (write it first; format in SKILL.md)" % (a[0] if a else "<none>"))
        return 2
    try:
        sp, notes, edits = prepare(a[0], warn)
    except Exception as ex:
        print("FAIL: could not read the spec (%s: %s)" % (type(ex).__name__, ex))
        return 2
    cv = sp["canvas"]
    dpi = cv.pop("dpi", None) or 300
    if a[0].endswith(".txt") and Path(a[0]).parent != OUT:
        shutil.copyfile(a[0], str(OUT / "figure_spec_lines.txt"))  # the hand-written source stays with the deliverables
    spec, svg = str(OUT / "figure_spec.json"), str(OUT / "figure.svg")
    for old in ("figure_v2.svg", "figure_v2.png", "figure_v2.pdf", "figure_spec_v2.json", "edit_diff.json", "figure_v2_pixel_check.json", "figure_v2_content_map.json", "export_log.jsonl"):
        if (OUT / old).exists():
            (OUT / old).unlink()
    json.dump(sp, open(spec, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("spec: %d compartments, %d nodes, %d edges, %d checks, %d exceptions, %d edit(s); width %s mm, min font %s pt, %s dpi" % (
        len(sp.get("panels", [])), len(sp.get("nodes", [])), len(sp.get("edges", [])), len(notes["compliance_checks"]), len(notes["exceptions"]), len(edits),
        cv.get("width_mm"), cv.get("min_font_pt"), dpi))
    for w in warn:
        print("   WARN: " + w)
    sf = os.path.join(HERE, "svgfig.py")
    rc, o = stage("build figure.svg", [PY, sf, "build", spec, svg], 150)
    if rc != 0 and not os.path.exists(svg) and isinstance(cv.get("colorscale"), dict):
        cv.pop("colorscale")
        json.dump(sp, open(spec, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        notes["exceptions"].append({"category": "run_failure", "detail": "build failed with the data colour scale; rebuilt without data colours", "handling": "fix the color line (file/columns/breaks) and rerun"})
        rc, o = stage("build without colour scale", [PY, sf, "build", spec, svg], 150)
    show(o)
    print("   " + next((l for l in o.splitlines() if l.startswith("wrote ")), o.strip()[-300:])[:300])
    lg = (jload(OUT / "figure_content_map.json", {}) or {}).get("legend") or []
    if lg:
        print("   legend drawn automatically (%d items): %s" % (len(lg), "; ".join(str(x.get("label")) for x in lg if x.get("label"))[:330]))
    npath = str(WORK / "notes.json")
    def assemble(tag):
        n2 = {k: v for k, v in notes.items() if not k.startswith("_") and v not in (None, "", [])}
        if notes.get("species"):
            n2.pop("species")
            n2["nomenclature"] = {"species": notes["species"]}
        if notes.get("_defaults"):
            n2["run_notes"] = notes["_defaults"]
        json.dump(n2, open(npath, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        rc_, o_ = stage("result.json (%s)" % tag, [PY, os.path.join(HERE, "export_check.py"), "assemble", npath], 120)
        return o_
    if not os.path.exists(svg):
        notes["exceptions"].append({"category": "run_failure", "detail": "figure build failed: %s" % o.strip()[-200:], "handling": "no figure in this run"})
        show(assemble("no figure"), 8)
        print("FAIL: no figure.svg. Fix the spec lines named above and rerun build.")
        return 1
    export(svg, dpi, 150)
    o1 = assemble("first complete version")
    rsv = jload(OUT / "figure_resolved_spec.json") or jload(spec)
    demo = not edits
    if demo and notes.get("edit_request"):
        demo = False
        print("   WARN: the work order has an edit request but the spec has no 'edit' line: add e.g. `edit <id or label> | label=New name` and rerun build")
        notes["exceptions"].append({"category": "run_failure", "detail": "edit request not applied in this run (no edit line in the spec): %s" % str(notes["edit_request"])[:200], "handling": "figure.svg is the unedited version"})
        o1 = assemble("edit request still open")
    elif demo and rsv.get("nodes"):
        n0 = rsv["nodes"][0]
        edits = [(n0.get("id"), {"stroke": "#D55E00", "dash": True})]
        notes["edit_request"] = "demonstration edit (not part of the official figure; figure.svg stays the deliverable): dashed orange border on node %s to show an id-stable source-level edit" % n0.get("id")
    if edits and time.time() - T0 < 420:
        w2 = []
        done = apply_edits(rsv, edits, w2)
        for w in w2:
            print("   WARN: " + w)
        if done:
            spec2, svg2 = str(OUT / "figure_spec_v2.json"), str(OUT / "figure_v2.svg")
            json.dump(rsv, open(spec2, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            rc, o = stage("build figure_v2.svg (%d edit(s)%s)" % (len(done), ", demonstration" if demo else ""), [PY, sf, "build", spec2, svg2], 120)
            if os.path.exists(svg2):
                rc, d = sh([PY, sf, "diff", svg, svg2], 60)
                if rc == 0:
                    (OUT / "edit_diff.json").write_text(d, encoding="utf-8")
                    dj = jload(OUT / "edit_diff.json", {}) or {}
                    ch = sorted({c.get("id") for c in dj.get("changes", [])})
                    print("   diff: %s ids kept, %s unchanged, changed: %s" % (dj.get("kept_ids"), dj.get("unchanged_ids"), ", ".join(map(str, ch[:12]))))
                cm2 = OUT / "figure_v2_content_map.json"
                if cm2.exists():
                    cm2.unlink()  # the v1 content map + edit_diff.json describe v2; one map keeps the record unambiguous
                rs2 = OUT / "figure_v2_resolved_spec.json"
                if rs2.exists():
                    rs2.unlink()
                export(svg2, dpi, max(40, min(150, 600 - (time.time() - T0))))
                notes["exceptions"] += [{"category": "layout_note", "detail": w, "handling": "edit applied as far as possible"} for w in w2]
                o1 = assemble("with the edited version")
        elif not demo:
            notes["exceptions"].append({"category": "run_failure", "detail": "edit lines matched no element: %s" % "; ".join(w2)[:300], "handling": "edit not applied"})
            o1 = assemble("edit not applied")
    show(o1, 10, r"^(WARN|FAIL|source trace)")
    print("   " + (o1.strip().splitlines() or ["?"])[-1])
    res = jload(OUT / "result.json", {}) or {}
    print("DONE in %s -> %s: %s" % (el(), OUT, ", ".join(sorted(p.name for p in OUT.iterdir() if p.is_file()))))
    print("status=%s; reasons=%s" % (res.get("status"), json.dumps(res.get("status_reasons"), ensure_ascii=False)[:300]))
    print("All deliverables are written; result.json is final for this version. Optional: fix a WARN that names a wrong fact (unknown node, skipped line, missing src, cited line) in the spec file and rerun build (at most twice).")
    return 0

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd not in ("start", "build"):
        print(__doc__)
        sys.exit(2)
    try:
        sys.exit((start if cmd == "start" else build)(sys.argv[2:]) or 0)
    except Exception as ex:  # never leave without saying what is on disk
        print("run.py %s stopped: %s: %s. Files so far in %s: %s" % (cmd, type(ex).__name__, ex, OUT, sorted(p.name for p in OUT.iterdir()) if OUT.is_dir() else []))
        sys.exit(1)
