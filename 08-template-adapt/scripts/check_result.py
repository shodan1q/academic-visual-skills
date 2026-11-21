#!/usr/bin/env python3
"""check_result.py - validate result.json + the delivered deck (stdlib only, Python 3.8+).

Usage: python3 check_result.py --init                       # skeleton result.json (every contract field, status partial)
       python3 check_result.py [--case X] [--out OUT_DIR/result.json] [--deck D.pptx] [--source start_text.txt ...]
                              [--paper paper.txt] [--slides N | --max-slides N] [--template target-template.pptx] [--min-pt 18]
Defaults: $CASE_JSON|/input/case.json, $OUT_DIR|/app/output, deck = newest *.pptx in OUT_DIR, source = $WORK_DIR/*.txt.
Checks result.json: case_id; every output_contract field (any key style, nested sub-fields) non-empty; no placeholders;
status is ONE word (contract's own words, else complete|partial|failed); listed files exist.
Checks the deck: opens; slide count vs --max-slides; template prompt text left ("Click to add", "单击此处"); slides
without notes; notes that just repeat the slide; PDF preview exists with one page per slide; PNG previews exist;
every number on a slide appears in the source text (catches typos/rounding/invented values); per-slide evidence map
covers every slide; with --template: masters/layouts/theme unchanged and every slide on a template layout; with --paper:
numbers that only the old deck has, figure/table labels whose wording matches another caption; picture stretch; explicit
fonts below --min-pt; missing slide numbers; loose text boxes; unresolved WARN lines in $WORK_DIR/build.log.
Always writes OUT_DIR/slide_audit.md (per-slide deviation record). Exit 1 on FAIL.
"""
import argparse, glob, json, os, re, subprocess, sys, zipfile
from pathlib import Path
from xml.sax.saxutils import unescape

CONTRACT_KEYS = ("output_contract", "outputcontract", "outputs_contract", "output_schema", "required_outputs", "deliverables",
                 "expected_outputs", "output_fields", "输出契约", "输出要求", "交付要求")
SCHEMA_WORDS = ("type", "description", "$schema", "title", "required", "properties")
PLACEHOLDER = re.compile(r"not yet produced|\bTODO\b|\bTBD\b|\bTBC\b|待补充|待填|<placeholder>|lorem ipsum|\{\{[^{}]{0,40}\}\}|xxx+", re.I)
PROMPT = re.compile(r"Click to (add|edit)|单击此处|点击此处|点击添加|单击以|Lorem|\bTODO\b|待补充|标题文字|在此输入", re.I)
STATUS, ALIASES = ("complete", "partial", "failed"), {"completed": "complete", "success": "complete", "done": "complete", "fail": "failed"}
NUM = re.compile(r"(?<![\w.])[-−]?\d+(?:[.,]\d+)*(?:\.\d+)?")


def load(p):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception as e:
        sys.exit("FAIL: cannot read %s: %s" % (p, e))


def find_contract(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if re.sub(r"[_\s]", "", str(k)).lower() in [re.sub(r"[_\s]", "", c) for c in CONTRACT_KEYS]:
                return v
        for v in obj.values():
            c = find_contract(v)
            if c is not None:
                return c
    return None


def fields(contract):
    out = {}
    if isinstance(contract, list):
        for x in contract:
            name = x if isinstance(x, str) else (x.get("name") or x.get("field")) if isinstance(x, dict) else None
            if name:
                out[name] = None
        return out
    if not isinstance(contract, dict):
        return out
    props = contract.get("properties") if isinstance(contract.get("properties"), dict) else None
    for k, v in (props if props is not None else {k: v for k, v in contract.items() if k not in SCHEMA_WORDS}).items():
        inner = (v.get("properties") if isinstance(v.get("properties"), dict) else v) if isinstance(v, dict) else {}
        out[k] = {kk: vv for kk, vv in inner.items() if kk not in SCHEMA_WORDS} or None
    for k in contract.get("required") or []:
        out.setdefault(k, None)
    return out


def empty(v):
    return v is None or (isinstance(v, str) and not v.strip()) or (isinstance(v, (list, dict)) and not v)


def slides_of(deck):
    """[(slide_text_without_footer_placeholders, notes_text)] in presentation order."""
    with zipfile.ZipFile(deck) as zf:
        rd = lambda n: zf.read(n).decode("utf-8") if n in zf.namelist() else ""
        rel = lambda part: {i: os.path.normpath(os.path.join(os.path.dirname(part), t)) for i, t in re.findall(r'Id="([^"]+)"[^>]*Target="([^"]+)"', rd(os.path.dirname(part) + "/_rels/" + os.path.basename(part) + ".rels"))}
        txt = lambda x: "\n".join("".join(unescape(t) for t in re.findall(r"<a:t>([^<]*)</a:t>", p)) for p in re.findall(r"<a:p(?=[ >]).*?</a:p>", x, re.S))
        pr, out = rel("ppt/presentation.xml"), []
        for rid in re.findall(r'<p:sldId [^>]*r:id="([^"]+)"', rd("ppt/presentation.xml")):
            part = pr[rid]
            x = re.sub(r'<p:sp>(?:(?!</p:sp>).)*?<p:ph type="(?:sldNum|ftr|dt)".*?</p:sp>', "", rd(part), flags=re.S)
            notes = [t for t in rel(part).values() if "notesSlide" in t]
            nx = rd(notes[0]) if notes else ""
            nb = "".join(b for b in re.findall(r"<p:sp>.*?</p:sp>", nx, re.S) if 'type="body"' in b)
            out.append((txt(x), txt(nb).strip()))
        return out


def pdf_pages(pdf):
    try:
        o = subprocess.run(["pdfinfo", pdf], capture_output=True, text=True, timeout=30).stdout
        return int(re.search(r"Pages:\s+(\d+)", o).group(1))
    except Exception:
        return len(re.findall(rb"/Type\s*/Page(?!s)", Path(pdf).read_bytes())) or None


def norm(n):
    return n.replace("−", "-").replace(",", "").lstrip("-")


def check_template(deck, tpl, fails, warns):
    """Template inheritance: masters/layouts/theme byte-identical to the template; every slide uses one of its layouts."""
    with zipfile.ZipFile(deck) as d, zipfile.ZipFile(tpl) as t:
        dn, tn = set(d.namelist()), set(t.namelist())
        parts = [n for n in tn if re.match(r"ppt/(slideMasters|slideLayouts|theme)/[^/]+\.xml$", n)]
        changed = [n for n in parts if n not in dn or d.read(n) != t.read(n)]
        (fails.append("template parts changed or missing in deck: %s" % changed[:6]) if changed else
         print("template: %d master/layout/theme parts identical to %s" % (len(parts), os.path.basename(tpl))))
        used = set(re.findall(r"slideLayouts/(slideLayout\d+\.xml)", " ".join(d.read(n).decode("utf-8", "ignore") for n in dn if re.match(r"ppt/slides/_rels/", n))))
        foreign = [u for u in used if "ppt/slideLayouts/" + u not in tn]
        if foreign:
            fails.append("slides use layouts that are not in the template: %s" % foreign)
        free = sum(d.read(n).decode("utf-8", "ignore").count('txBox="1"') for n in dn if re.match(r"ppt/slides/slide\d+\.xml$", n))
        if free > 2 * max(1, len([n for n in dn if re.match(r"ppt/slides/slide\d+\.xml$", n)])):
            warns.append("%d free text boxes: content should sit in layout placeholders, not loose boxes" % free)


def check_deck(deck, res, sources, max_slides, fails, warns, exact=None):
    try:
        sl = slides_of(deck)
    except Exception as e:
        return fails.append("deck %s cannot be read as PPTX: %s" % (deck, e))
    n = len(sl)
    print("deck: %s, %d slides" % (deck, n))
    if exact and n != exact:
        fails.append("deck has %d slides, work order requires exactly %d" % (n, exact))
    if max_slides and n > max_slides:
        fails.append("deck has %d slides, limit is %d" % (n, max_slides))
    for i, (t, nt) in enumerate(sl, 1):
        m = PROMPT.search(t)
        if m:
            fails.append("slide %d: template prompt / placeholder text left: %r" % (i, m.group(0)))
        if not t.strip():
            warns.append("slide %d has no text at all (title missing?)" % i)
        if not nt:
            warns.append("slide %d has no speaker notes" % i)
        elif len(nt) > 20 and sum(1 for c in nt if c in t) / float(len(nt)) > 0.8 and nt.replace(" ", "")[:40] in t.replace(" ", ""):
            warns.append("slide %d notes mostly repeat the slide text; notes should add transitions/emphasis/backup evidence" % i)
    lost_by = {}
    stem = os.path.splitext(deck)[0]
    pdfs = [p for p in glob.glob(os.path.join(os.path.dirname(deck), "*.pdf"))]
    pdf = stem + ".pdf" if os.path.exists(stem + ".pdf") else (pdfs[0] if pdfs else None)
    if not pdf:
        fails.append("no PDF preview next to the deck (render with soffice, or state the failure in result.json)")
    else:
        pg = pdf_pages(pdf)
        if pg is not None and pg != n:
            fails.append("PDF %s has %s pages but deck has %d slides (stale or wrong preview?)" % (os.path.basename(pdf), pg, n))
        for i, (t, _) in enumerate(sl[:pg or 0], 1):  # text clipped or dropped in the render shows up as tokens missing from the PDF page
            try:
                pt = re.sub(r"\s+", "", subprocess.run(["pdftotext", "-f", str(i), "-l", str(i), pdf, "-"], capture_output=True, text=True, timeout=30).stdout)
            except Exception:
                break
            toks = [w for w in re.findall(r"[A-Za-z]{3,}|[\u4e00-\u9fff]", t)]
            lost = [w for w in toks if w not in pt]
            lost_by[i] = len(lost)
            if toks and pt and len(lost) > max(2, 0.1 * len(toks)):
                warns.append("slide %d: %d/%d words missing from the rendered PDF page (clipped/overflow?): %s" % (i, len(lost), len(toks), "".join(lost[:15])[:60]))
    if not glob.glob(os.path.join(os.path.dirname(deck), "**", "*.png"), recursive=True):
        warns.append("no PNG page previews found under %s" % os.path.dirname(deck))
    src = ""
    for s in sources:
        try:
            src += Path(s).read_text(encoding="utf-8", errors="ignore") + "\n"
        except Exception:
            pass
    if src:
        pool = {norm(x) for x in NUM.findall(src)}
        miss = []
        for i, (t, _) in enumerate(sl, 1):
            miss += ["s%d:%s" % (i, x) for x in NUM.findall(t) if norm(x) not in pool and not (norm(x).isdigit() and int(norm(x)) < 10)]
        dec = [m for m in miss if re.search(r"\d[.,]\d", m.split(":")[1])]
        if dec:
            fails.append("decimal numbers on slides not found in source text (typo/rounding/invented?): %s" % ", ".join(dec[:20]))
        if len(miss) > len(dec):
            warns.append("integers on slides not found in source text (check each; dates/ids are fine): %s" % ", ".join([m for m in miss if m not in dec][:20]))
        if not miss:
            print("numbers: every number on the slides occurs in the source text")
    else:
        warns.append("no source text given (--source paper.txt) -> number provenance not checked")
    return sl, lost_by


def paper_check(sl, paper, deck_srcs, fails, warns):
    """Slides vs the PAPER (not the old deck): numbers that only the old deck has, and figure/table labels whose text
    matches a different caption in the paper (the classic 'Fig. 3' that is really Fig. 2)."""
    txt = Path(paper).read_text(encoding="utf-8", errors="ignore")
    pool = {norm(x) for x in NUM.findall(txt)}
    deck_pool = set()
    for s in deck_srcs:
        try:
            deck_pool |= {norm(x) for x in NUM.findall(Path(s).read_text(encoding="utf-8", errors="ignore"))}
        except Exception:
            pass
    only_deck, unknown = [], []
    for i, (t, _) in enumerate(sl, 1):
        for x in NUM.findall(t):
            v = norm(x)
            if v in pool or (v.isdigit() and int(v) < 10):
                continue
            (only_deck if v in deck_pool else unknown).append("s%d:%s" % (i, x))
    if only_deck:
        fails.append("numbers on slides that come from the old deck but NOT from the paper (deck error carried over? check and correct to the paper, log it): %s" % ", ".join(only_deck[:15]))
    if unknown:
        warns.append("numbers on slides found in neither paper nor deck (computed? label 'calculated from ...' or remove): %s" % ", ".join(unknown[:15]))
    LBL = r"(Fig(?:ure)?\.?|Table|Tab\.|图|表)\s*(S?\d+)"
    kind = lambda k: "T" if k.lower().startswith(("tab", "表")) else "F"
    caps = {}
    for line in txt.splitlines():
        m = re.match(r"\s*" + LBL + r"\s*[.:|：]", line)
        if m:
            caps.setdefault((kind(m.group(1)), m.group(2)), line.strip())
    words = lambda u: {w.lower() for w in re.findall(r"[A-Za-z]{4,}|[\u4e00-\u9fff]", u)} - {"figure", "table", "with", "from", "that", "this"}
    for i, (t, _) in enumerate(sl, 1):
        for line in t.splitlines():
            for m in re.finditer(LBL, line):
                key = (kind(m.group(1)), m.group(2))
                if caps and key not in caps:
                    fails.append("slide %d cites %s but the paper has no caption with that number" % (i, m.group(0)))
                    continue
                rest = words(line[m.end():])
                if len(rest) < 2 or key not in caps:
                    continue
                ov = lambda c: len(rest & words(c)) / float(len(rest))
                best = max(caps, key=lambda k: ov(caps[k]) if k[0] == key[0] else -1)
                if best != key and ov(caps[best]) >= 0.5 and ov(caps[key]) < 0.25:
                    fails.append("slide %d: %r reads like paper %s%s (%r), not %s -> fix the label or the content" % (i, line[:50], "Fig. " if best[0] == "F" else "Table ", best[1], caps[best][:50], m.group(0)))
    if caps:
        print("paper: %d figure/table captions indexed; slide labels checked against them" % len(caps))


def deck_audit(deck, n, lost_by, min_pt, out_md, fails, warns):
    """Per-slide deviation record: layout, placeholders used, loose text boxes, picture aspect, smallest explicit font, notes, render loss."""
    with zipfile.ZipFile(deck) as zf:
        names = set(zf.namelist())
        rd = lambda p: zf.read(p).decode("utf-8", "ignore") if p in names else ""
        rel = lambda part: {i: os.path.normpath(os.path.join(os.path.dirname(part), t)) for i, t in re.findall(r'Id="([^"]+)"[^>]*Target="([^"]+)"', rd(os.path.dirname(part) + "/_rels/" + os.path.basename(part) + ".rels"))}
        pr = rel("ppt/presentation.xml")
        rows, has_num = [], any('type="sldNum"' in rd(p) for p in names if p.startswith("ppt/slideLayouts/slideLayout"))
        for i, rid in enumerate(re.findall(r'<p:sldId [^>]*r:id="([^"]+)"', rd("ppt/presentation.xml")), 1):
            part = pr[rid]
            x, rl = rd(part), rel(part)
            lay = next((p for p in rl.values() if "slideLayout" in p), "")
            lname = (re.findall(r'<p:cSld name="([^"]*)"', rd(lay)) or [os.path.basename(lay)])[0]
            phs = ["%s:%s" % ((re.findall(r'type="(\w+)"', a) or ["obj"])[0], (re.findall(r'idx="(\d+)"', a) or ["0"])[0]) for a in re.findall(r"<p:ph\b([^>]*)", x)]
            loose = [nm for b in re.findall(r"<p:sp>.*?</p:sp>", x, re.S) if "<p:ph" not in b and "<a:t>" in b
                     for nm in re.findall(r'<p:cNvPr [^>]*name="([^"]*)"', b)[:1] if not re.search(r"caption|source|note|图注|来源", nm, re.I)]
            small, pics = [], []
            for b in re.findall(r"<p:sp>.*?</p:sp>", x, re.S):
                nm = (re.findall(r'<p:cNvPr [^>]*name="([^"]*)"', b) or [""])[0]
                if re.search(r"caption|source|note|图注|来源", nm, re.I) or re.search(r'type="(sldNum|ftr|dt)"', b):
                    continue
                small += [int(v) / 100.0 for v in re.findall(r'<a:rPr[^>]*\bsz="(\d+)"', b)]
            tsz = [int(v) / 100.0 for g in re.findall(r"<a:tbl>.*?</a:tbl>", x, re.S) for v in re.findall(r'<a:rPr[^>]*\bsz="(\d+)"', g)]
            for b in re.findall(r"<p:pic>.*?</p:pic>", x, re.S):
                e, ext = re.search(r'r:embed="([^"]+)"', b), re.search(r'<a:ext cx="(\d+)" cy="(\d+)"', b)
                data = zf.read(rl[e.group(1)]) if e and rl.get(e.group(1)) in names else b""
                if not (ext and data[:8] == b"\x89PNG\r\n\x1a\n"):
                    pics.append("?")
                    continue
                iw, ih = int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
                c = dict((k, int(v)) for k, v in re.findall(r'\b([ltrb])="(\d+)"', (re.findall(r"<a:srcRect[^>]*/>", b) or [""])[0]))
                iw, ih = iw * (1 - (c.get("l", 0) + c.get("r", 0)) / 1e5), ih * (1 - (c.get("t", 0) + c.get("b", 0)) / 1e5)
                dev = abs((int(ext.group(1)) / float(ext.group(2))) / (iw / ih) - 1)
                pics.append("%.0f%%" % (dev * 100))
                if dev > 0.03:
                    fails.append("slide %d: picture stretched (aspect off by %.0f%%) -> scale proportionally" % (i, dev * 100))
            mn = min(small) if small else None
            if min_pt and mn is not None and mn < min_pt:
                fails.append("slide %d: body text at %.0fpt below the %.0fpt floor -> shorten/split, do not shrink" % (i, mn, min_pt))
            if tsz and min(tsz) < 12:
                warns.append("slide %d: table text %.0fpt (< 12pt is unreadable when projected)" % (i, min(tsz)))
            if has_num and "sldNum:" not in " ".join(phs):
                warns.append("slide %d has no slide-number placeholder although the template layouts have one" % i)
            if len(loose) > 1:
                warns.append("slide %d: %d loose text boxes %s -> put content in layout placeholders" % (i, len(loose), loose[:3]))
            nt = rl and next((p for p in rl.values() if "notesSlide" in p), None)
            nchars = len("".join(re.findall(r"<a:t>([^<]*)</a:t>", rd(nt)))) if nt else 0
            rows.append("| %d | %s | %s | %s | %s | %s | %d | %s |" % (i, lname, " ".join(phs) or "-", ", ".join(loose) or "-", " ".join(pics) or "-",
                        ("%.0f" % mn) if mn is not None else "inherit", nchars, lost_by.get(i, "n/a")))
    if out_md:
        Path(out_md).write_text("# Slide audit (written by check_result.py)\n\n| slide | layout | placeholders (type:idx) | loose text boxes | picture aspect error | smallest explicit pt (body) | notes chars | words lost in PDF |\n|---|---|---|---|---|---|---|---|\n" + "\n".join(rows) + "\n", encoding="utf-8")
        print("audit: per-slide record written to %s" % out_md)


def evidence_rows(res, n, warns):
    blob = json.dumps(res, ensure_ascii=False)
    pages = {int(x) for x in re.findall(r'"(?:slide|slide_no|slide_number|slide_index|page|页码?|幻灯片)"\s*:\s*"?(\d+)', blob)}
    if not pages:
        warns.append("result.json has no per-slide evidence rows with a slide/page number key")
    elif set(range(1, n + 1)) - pages:
        warns.append("evidence map has no row for slides %s" % sorted(set(range(1, n + 1)) - pages)[:20])


def main():
    ap = argparse.ArgumentParser()
    out_dir = os.environ.get("OUT_DIR", "/app/output")
    ap.add_argument("--case", default=os.environ.get("CASE_JSON", "/input/case.json"))
    ap.add_argument("--out", default=os.path.join(out_dir, "result.json"))
    ap.add_argument("--deck")
    ap.add_argument("--source", nargs="*")
    ap.add_argument("--max-slides", type=int)
    ap.add_argument("--slides", type=int, help="exact required slide count")
    ap.add_argument("--template", help="template .pptx/.potx the deck must inherit from")
    ap.add_argument("--paper", help="paper text (pdftotext); slide numbers/figure labels are checked against it")
    ap.add_argument("--min-pt", type=float, help="smallest allowed explicit body font size")
    ap.add_argument("--init", action="store_true", help="write a skeleton result.json (status partial) and exit")
    a = ap.parse_args()
    case = load(a.case)
    if a.init:
        cid = (case.get("case_id") or case.get("caseId") or case.get("id")) if isinstance(case, dict) else None
        sk = {"case_id": cid}
        for f in fields(find_contract(case)):
            sk.setdefault(f, "not yet produced")
        sk.update({"status": "partial", "status_reasons": ["skeleton written at start; deliverables in progress"]})
        os.makedirs(os.path.dirname(a.out), exist_ok=True)
        Path(a.out).write_text(json.dumps(sk, ensure_ascii=False, indent=1), encoding="utf-8")
        return print("skeleton written: %s (%d fields)" % (a.out, len(sk))) or 0
    res = load(a.out)
    fails, warns = [], []
    cid = (case.get("case_id") or case.get("caseId") or case.get("id")) if isinstance(case, dict) else None
    if cid is not None and str(res.get("case_id")) != str(cid):
        fails.append("case_id is %r, case says %r" % (res.get("case_id"), cid))
    contract = find_contract(case)
    spec = fields(contract)
    if not spec:
        warns.append("no output_contract found in case.json - check fields by hand")
    for f, sub in spec.items():
        if f in ("status", "case_id"):
            continue
        if f not in res or empty(res[f]):
            fails.append("contract field missing or empty: %s" % f)
            continue
        if sub and isinstance(res[f], dict):
            fails += ["sub-field missing or empty: %s.%s" % (f, k) for k in sub if k not in res[f] or empty(res[f][k])]
        m = PLACEHOLDER.search(json.dumps(res[f], ensure_ascii=False))
        if m:
            fails.append("placeholder text in %s: %r" % (f, m.group(0)))
    sd = (contract.get("properties") or {}).get("status") if isinstance(contract, dict) and isinstance(contract.get("properties"), dict) else contract.get("status") if isinstance(contract, dict) else None
    allowed = [w for w in re.findall(r"[A-Za-z_]{4,}", json.dumps(sd) if sd is not None else "") if w.lower() not in ("type", "string", "description", "enum", "status")]
    raw = str(res.get("status", "")).strip()
    st = ALIASES.get(raw.lower(), raw.lower())
    if not re.fullmatch(r"[A-Za-z_]+", raw):
        fails.append("status %r must be exactly one word; put limits/reasons in status_reasons" % raw)
    elif allowed and raw.lower() not in [w.lower() for w in allowed]:
        fails.append("status %r is not one of the contract's words %s" % (raw, allowed))
    elif not allowed and st not in STATUS:
        fails.append("status is %r; use complete / partial / failed" % raw)
    warns += ["no '%s' block (recommended)" % k for k in ("source_map", "change_log", "uncertainty", "material_gaps") if '"%s"' % k not in json.dumps(res)]
    decks = [a.deck] if a.deck else sorted(glob.glob(os.path.join(os.path.dirname(a.out), "*.pptx")), key=os.path.getmtime)[-1:]
    if not decks:
        fails.append("no .pptx in %s (pass --deck)" % os.path.dirname(a.out))
    srcs = a.source if a.source is not None else glob.glob(os.path.join(os.environ.get("WORK_DIR", "/app/work"), "*.txt"))
    for d in decks:
        r = check_deck(d, res, srcs + ([a.paper] if a.paper else []), a.max_slides, fails, warns, a.slides)
        if not r:
            continue
        sl, lost_by = r
        evidence_rows(res, len(sl), warns)
        if a.paper:
            paper_check(sl, a.paper, [s for s in srcs if os.path.abspath(s) != os.path.abspath(a.paper)], fails, warns)
        if a.template:
            check_template(d, a.template, fails, warns)
        deck_audit(d, len(sl), lost_by, a.min_pt, os.path.join(os.path.dirname(a.out), "slide_audit.md"), fails, warns)
    for p in sorted(set(re.findall(r'"(/[^"\s]+\.(?:pptx|potx|pdf|png|jpg|md|json|csv|txt|py))"', json.dumps(res, ensure_ascii=False)))):
        if not Path(p).exists():
            fails.append("listed file does not exist: %s" % p)
    blog = os.path.join(os.environ.get("WORK_DIR", "/app/work"), "build.log")
    if os.path.exists(blog):
        bw = [l.strip() for l in open(blog, encoding="utf-8", errors="ignore") if l.startswith("WARN")]
        if bw:
            warns.append("build.log still has %d WARN lines (fix, or list each in exceptions): %s" % (len(bw), bw[0][:90]))
    if st == "complete" and fails:
        fails.append("status 'complete' while the problems above remain -> fix them or use 'partial'")
    print("\n".join(["WARN: " + w for w in warns] + ["FAIL: " + f for f in fails]))
    if fails:
        return 1
    print("PASS: case_id ok, %d contract fields filled, status=%s" % (len(spec), raw))
    return 0


if __name__ == "__main__":
    sys.exit(main())
