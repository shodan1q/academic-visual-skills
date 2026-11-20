#!/usr/bin/env python3
"""check_result.py - validate result.json + the delivered deck (stdlib only, Python 3.8+).

Usage: python3 check_result.py [--case X] [--out OUT_DIR/result.json] [--deck D.pptx] [--source paper.txt ...]
                              [--slides N | --max-slides N] [--template target-template.pptx]
Defaults: $CASE_JSON|/input/case.json, $OUT_DIR|/app/output, deck = newest *.pptx in OUT_DIR, source = $WORK_DIR/*.txt.
Checks result.json: case_id; every output_contract field (any key style, nested sub-fields) non-empty; no placeholders;
status is ONE word (contract's own words, else complete|partial|failed); listed files exist.
Checks the deck: opens; slide count vs --max-slides; template prompt text left ("Click to add", "单击此处"); slides
without notes; notes that just repeat the slide; PDF preview exists with one page per slide; PNG previews exist;
every number on a slide appears in the source text (catches typos/rounding/invented values); per-slide evidence map
covers every slide; with --template: masters/layouts/theme unchanged and every slide on a template layout. Exit 1 on FAIL.
"""
import argparse, glob, json, os, re, subprocess, sys, zipfile
from pathlib import Path
from xml.sax.saxutils import unescape

CONTRACT_KEYS = ("output_contract", "outputcontract", "outputs_contract", "output_schema", "required_outputs", "deliverables",
                 "expected_outputs", "output_fields", "输出契约", "输出要求", "交付要求")
SCHEMA_WORDS = ("type", "description", "$schema", "title", "required", "properties")
PLACEHOLDER = re.compile(r"\bTODO\b|\bTBD\b|\bTBC\b|待补充|待填|PLACEHOLDER|lorem ipsum|\{\{[^{}]{0,40}\}\}|xxx+", re.I)
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
    a = ap.parse_args()
    case, res = load(a.case), load(a.out)
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
    warns += ["no '%s' block (recommended)" % k for k in ("source_map", "change_log", "uncertainty", "material_gaps") if k not in res]
    for p in sorted(set(re.findall(r'"(/[^"\s]+\.(?:pptx|potx|pdf|png|jpg|md|json|csv|txt|py))"', json.dumps(res, ensure_ascii=False)))):
        if not Path(p).exists():
            fails.append("listed file does not exist: %s" % p)
    decks = [a.deck] if a.deck else sorted(glob.glob(os.path.join(os.path.dirname(a.out), "*.pptx")), key=os.path.getmtime)[-1:]
    if not decks:
        fails.append("no .pptx in %s (pass --deck)" % os.path.dirname(a.out))
    srcs = a.source if a.source is not None else glob.glob(os.path.join(os.environ.get("WORK_DIR", "/app/work"), "*.txt"))
    for d in decks:
        check_deck(d, res, srcs, a.max_slides, fails, warns, a.slides)
        if a.template:
            check_template(d, a.template, fails, warns)
    if st == "complete" and fails:
        fails.append("status 'complete' while the problems above remain -> fix them or use 'partial'")
    print("\n".join(["WARN: " + w for w in warns] + ["FAIL: " + f for f in fails]))
    if fails:
        return 1
    print("PASS: case_id ok, %d contract fields filled, status=%s" % (len(spec), raw))
    return 0


if __name__ == "__main__":
    sys.exit(main())
