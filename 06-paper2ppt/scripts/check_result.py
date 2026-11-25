#!/usr/bin/env python3
"""check_result.py - validate result.json + the delivered deck (stdlib only, Python 3.8+).

Usage: python3 check_result.py --init                       # skeleton result.json (every contract field, status partial)
       python3 check_result.py --assemble [facts.json]       # result.json with EVERY contract key filled by meaning from facts + files
       ... [--baseline v0.pptx --keep-map 1:1,2:2 --edit-map 3:3] [--paper-advisory]   # preserved-slide check + per-slide before/after version_diff.md
       python3 check_result.py [--case X] [--out OUT_DIR/result.json] [--deck D.pptx] [--source start_text.txt ...]
                              [--paper paper.txt] [--preserved 2,5] [--slides N | --max-slides N] [--template target-template.pptx] [--min-pt 18]
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
        row = lambda m: "<a:p><a:t>%s</a:t></a:p>" % " | ".join("".join(re.findall(r"<a:t>([^<]*)</a:t>", c)) for c in re.findall(r"<a:tc\b.*?</a:tc>", m.group(0), re.S))
        txt = lambda x: "\n".join("".join(unescape(t) for t in re.findall(r"<a:t>([^<]*)</a:t>", p)) for p in re.findall(r"<a:p(?=[ >]).*?</a:p>", re.sub(r"<a:tr\b.*?</a:tr>", row, x, flags=re.S), re.S))  # table row = one line
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
        fails.append("[render] no PDF preview next to the deck (run pptx_kit.py render; if no renderer exists set status partial and record it)")
    else:
        pg = pdf_pages(pdf)
        if pg is not None and pg != n:
            fails.append("[render] PDF %s has %s pages but deck has %d slides (stale or wrong preview? re-run pptx_kit.py render)" % (os.path.basename(pdf), pg, n))
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


def paper_check(sl, paper, deck_srcs, fails, warns, preserved=()):
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
    keep = lambda items: [m for m in items if int(re.match(r"s?(\d+)", m).group(1)) in preserved]
    if preserved and only_deck:
        kd = keep(only_deck)
        if kd:
            warns.append("preserved slides carry numbers the paper does not have (do not edit them; report in exceptions): %s" % ", ".join(kd[:10]))
        only_deck = [m for m in only_deck if m not in kd]
    if only_deck:
        fails.append("numbers on slides that come from the old deck but NOT from the paper (deck error carried over? check and correct to the paper, log it): %s" % ", ".join(only_deck[:15]))
    if unknown:
        warns.append("numbers on slides found in neither paper nor deck (computed? label 'calculated from ...' or remove): %s" % ", ".join(unknown[:15]))
    # literature values: decimals that the paper only states next to a citation [n] must carry an attribution on the slide
    CIT = re.compile(r"\[\d+(?:[,\u2013-]\s*\d+)*\]")
    occ = {}
    for line in txt.splitlines():
        for m in NUM.finditer(line):  # cited = a [n] follows within 40 characters (same sentence or same table row)
            if "." in m.group(0):
                occ.setdefault(norm(m.group(0)), []).append(bool(CIT.search(line[m.end():m.end() + 40])))
    lit = []
    for i, (t, _) in enumerate(sl, 1):
        for line in t.splitlines():
            if CIT.search(line) or re.search(r"\bref|文献|报道|reported|et al", line, re.I):
                continue
            lit += ["s%d:%s" % (i, x) for x in NUM.findall(line) if "." in x and occ.get(norm(x)) and all(occ[norm(x)])]
    if lit:
        warns.append("numbers the paper only gives with a citation [n] (other groups' results?) appear on slides without attribution - add '[n] 报道' or move off this-work pages: %s" % ", ".join(lit[:10]))
    LBL = r"(Fig(?:ure)?\.?|Table|Tab\.|图|表)\s*(S?\d+)"
    kind = lambda k: "T" if k.lower().startswith(("tab", "表")) else "F"
    caps = {}
    tl = txt.splitlines()
    for li, line in enumerate(tl):
        for m in re.finditer(r"(?:^|\s{3,})" + LBL + r"\s*[.:|：]", line):  # also right-column captions of 2-column layout text
            caps.setdefault((kind(m.group(1)), m.group(2)), (line[m.start(1):].strip() + " " + " ".join(x.strip() for x in tl[li + 1:li + 3])) if m.start(1) < 8 else line[m.start(1):].strip())
    mentioned = {(kind(m.group(1)), m.group(2)) for m in re.finditer(LBL, txt)}
    words = lambda u: {w.lower()[:6] for w in re.findall(r"[A-Za-z]{4,}|[\u4e00-\u9fff]", u)} - {"figure", "table", "with", "from", "that", "this", "paper", "compar", "result", "overvi", "visual", "numeri"}
    for i, (t, _) in enumerate(sl, 1):
        for line in t.splitlines():
            for m in re.finditer(LBL, line):
                key = (kind(m.group(1)), m.group(2))
                bucket = warns if i in preserved else fails
                if caps and key not in caps:
                    if key in mentioned:  # cited in the paper text but caption not parsed (layout) -> advisory only
                        warns.append("slide %d cites %s: referenced in the paper text but no caption found in paper.txt (supplementary not supplied, or caption not parsed) - confirm by eye and say 'not supplied' where true" % (i, m.group(0)))
                    else:
                        bucket.append("slide %d cites %s but the paper never mentions that number (no caption, no in-text reference)" % (i, m.group(0)))
                    continue
                rest = words(line[m.end():])
                if len(rest) < 2 or key not in caps:
                    continue
                ov = lambda c: len(rest & words(c)) / float(len(rest))
                best = max(caps, key=lambda k: ov(caps[k]) if k[0] == key[0] else -1)
                if best != key and len(rest) >= 3 and ov(caps[best]) >= 0.6 and ov(caps[key]) < 0.25:  # word overlap is weak evidence: FAIL only when unambiguous
                    (bucket if len(rest) >= 4 and ov(caps[best]) >= 0.75 and ov(caps[key]) == 0 else warns).append("slide %d: %r reads like paper %s%s (%r), not %s -> fix the label or the content" % (i, line[:50], "Fig. " if best[0] == "F" else "Table ", best[1], caps[best][:50], m.group(0)))
    if caps:
        print("paper: %d figure/table captions indexed; slide labels checked against them" % len(caps))


def deck_audit(deck, n, lost_by, min_pt, out_md, fails, warns, preserved=()):
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
                    bad("slide %d: picture stretched (aspect off by %.0f%%) -> scale proportionally" % (i, dev * 100))
            bad = (lambda m: warns.append(m + " [preserved slide: not edited, report in exceptions]")) if i in preserved else fails.append
            mn = min(small) if small else None
            if min_pt and mn is not None and mn < min_pt:
                bad("slide %d: body text at %.0fpt below the %.0fpt floor -> shorten/split, do not shrink" % (i, mn, min_pt))
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


ROLES = [("status", r"^status$|状态"), ("case_id", r"case_?id|caseid|用例|案例编号"),
         ("evidence", r"evidence|content_?map|source_?map|sources|mapping|provenance|citation|证据|映射|来源|出处"),
         ("change_log", r"change|history|diff|revision|修改|变更|版本差异"),
         ("render", r"render|export|preview|pdf|png|version|record|导出|渲染|版本|预览|记录"),
         ("editable", r"editable|pptx|presentation|deck|slides?|source|artifact|可编辑|演示|文稿|源文件|幻灯片"),
         ("compliance", r"compliance|check|verif|validation|合规|检查|核对|校验"),
         ("exceptions", r"exception|gap|missing|failure|error|异常|缺失|失败"),
         ("uncertainty", r"uncertain|limit|risk|caveat|issue|不确定|局限|限制|风险|问题"),
         ("plan", r"plan|outline|structure|storyline|order|大纲|结构|主线|页序"),
         ("notes", r"note|script|speaker|讲稿|备注|讲解")]


def assemble(case, out_path, facts_path):
    """Write result.json from the agent's facts + the files on disk, filling EVERY contract key by meaning (any key name/style)."""
    od, fx = os.path.dirname(out_path), {}
    if facts_path and os.path.exists(facts_path):
        try:
            fx = json.loads(Path(facts_path).read_text(encoding="utf-8"))
        except Exception as e:
            print("WARN: facts file unreadable (%s); assembling from files only" % e)
    try:  # the build spec may carry the run-level facts too (one file to write): exceptions, uncertainty, storyline ...
        sp = json.loads(Path(os.path.join(od, "spec.json")).read_text(encoding="utf-8"))
        for k in ("exceptions", "uncertainty", "material_gaps", "status_reasons", "storyline", "compliance_checks", "template"):
            if sp.get(k) and k not in fx:
                fx[k] = sp[k]
    except Exception:
        pass
    nk = lambda k: re.sub(r"[\W_]+", "", str(k)).lower()
    fxn = {nk(k): v for k, v in fx.items()}
    rdj = lambda p: (lambda t: json.loads(t))(Path(p).read_text(encoding="utf-8")) if p and os.path.exists(p) else None
    def safe(fn, d=None):
        try:
            return fn()
        except Exception:
            return d
    deck = fx.get("pptx") or (sorted(glob.glob(os.path.join(od, "*.pptx")), key=os.path.getmtime) or [None])[-1]
    rj = safe(lambda: rdj(os.path.join(od, "render.json"))) or {}
    pdf = rj.get("pdf") or next(iter(glob.glob(os.path.join(od, "*.pdf"))), None)
    png = rj.get("png") or sorted(glob.glob(os.path.join(od, "preview", "*.png")))
    sl = safe(lambda: slides_of(deck), []) if deck else []
    files = {k: os.path.join(od, f) for k, f in (("content_map", "content_map.json"), ("change_log", "change_log.md"), ("slide_audit", "slide_audit.md"),
             ("plan", "plan.md"), ("spec", "spec.json"), ("corrections", "corrections.md"), ("version_diff", "version_diff.md"), ("render_record", "render.json"))
             if os.path.exists(os.path.join(od, f))}
    files.update({k: v for k, v in (fx.get("files") or {}).items() if isinstance(v, str) and os.path.exists(v)})
    vers = sorted(glob.glob(os.path.join(od, "versions", "*")))
    specs = [v for v in vers if re.search(r"spec[^/]*\.json$", v)] or sorted(glob.glob(os.path.join(os.environ.get("WORK_DIR", "/app/work"), "spec*.json")), key=os.path.getmtime)
    if specs and "spec" not in files:
        files["spec"] = specs[-1]
    cm = fx.get("content_map") or safe(lambda: rdj(files.get("content_map"))) or [{"slide": i, "title": t.split("\n")[0][:90]} for i, (t, _) in enumerate(sl, 1)]
    lines = lambda k: [l.strip("-* ").strip() for l in safe(lambda: Path(files[k]).read_text(encoding="utf-8").splitlines(), []) if l.strip("-*# ").strip()]
    errs = list(rj.get("errors") or [])
    exc = fx.get("exceptions") or {"material_missing": fx.get("material_gaps") or [], "undecidable": [], "run_failures": errs}
    if isinstance(exc, dict) and errs and not exc.get("run_failures"):
        exc["run_failures"] = errs
    st = fx.get("status") or ("failed" if not deck else "complete" if pdf and png else "partial")
    val = {"case_id": (case.get("case_id") or case.get("caseId") or case.get("id")) if isinstance(case, dict) else None,
           "editable": {"pptx": deck, "slides": len(sl), "spec": files.get("spec") or fx.get("spec"), "rebuild": fx.get("rebuild") or "python3 pptx_kit.py build %s" % (files.get("spec") or "spec.json"),
                        "template": fx.get("template"), "versions": fx.get("versions") or vers, "slide_titles": [t.split("\n")[0][:90] for t, _ in sl]},
           "render": {"pptx": deck, "pdf": pdf, "png": png, "pages": rj.get("pages"), "renderer": rj.get("renderer") or "none (see run_failures)",
                      "fonts": rj.get("fonts"), "substitutions": rj.get("substitutions"), "render_record": files.get("render_record"), "slide_audit": files.get("slide_audit"),
                      "change_log": fx.get("change_log") or lines("change_log") or ["single build, no revisions"]},
           "evidence": {"rows": cm, "file": files.get("content_map")}, "compliance": fx.get("compliance_checks") or fx.get("compliance") or
           [{"check": "deck opens and has %d slides" % len(sl), "result": "PASS" if sl else "FAIL", "basis": "zip/XML read"},
            {"check": "PDF + PNG previews", "result": "PASS" if pdf and png else "FAIL", "basis": rj.get("status") or "files on disk"}],
           "exceptions": exc, "uncertainty": fx.get("uncertainty") or ["no open issues recorded beyond exceptions"],
           "change_log": fx.get("change_log") or lines("change_log") or ["single build, no revisions"],
           "plan": fx.get("plan") or lines("plan") or [t.split("\n")[0][:90] for t, _ in sl], "notes": [{"slide": i, "notes": n[:200]} for i, (_, n) in enumerate(sl, 1)]}
    val["summary"] = {"files": dict(files, pptx=deck, pdf=pdf), "slides": len(sl), "status": st}
    clean = lambda v: {k: x for k, x in v.items() if not empty(x)} if isinstance(v, dict) else v
    def pick(key, desc=""):
        if nk(key) in fxn:
            return fxn[nk(key)]
        for text in (str(key), str(desc)):
            for role, rx in ROLES:
                if re.search(rx, text, re.I):
                    return (val[role] if role == "exceptions" else clean(val[role])) if role in val else st
        return clean(val["summary"])
    contract = find_contract(case)
    res = {}
    for f, sub in fields(contract).items():
        desc = json.dumps((contract.get("properties") or contract).get(f, "") if isinstance(contract, dict) else "", ensure_ascii=False)
        if sub:
            par = pick(f, desc)
            def leaf(k, v):
                if isinstance(par, dict):
                    hit = [x for kk, x in par.items() if nk(kk) and (nk(kk) in nk(k) or nk(k) in nk(kk) or nk(kk).rstrip("s") in nk(k)) and not empty(x)]
                    if hit:
                        return hit[0]
                return pick(k, json.dumps(v, ensure_ascii=False))
            res[f] = {k: leaf(k, v) for k, v in sub.items()}
            res[f] = {k: (v if not empty(v) else par) for k, v in res[f].items()}
        else:
            res[f] = pick(f, desc)
    sd = ((contract.get("properties") or {}).get("status") if isinstance(contract.get("properties"), dict) else contract.get("status")) if isinstance(contract, dict) else None
    words = [w for w in re.findall(r"[A-Za-z_]{4,}", json.dumps(sd) if sd else "") if w.lower() not in ("type", "string", "description", "enum", "status")]
    if words:
        st = next((w for w in words if w.lower().startswith(st[:4].lower())), words[0] if st == "complete" else words[-1])
    for k in ("source_map", "change_log", "uncertainty", "material_gaps", "exceptions"):
        res.setdefault(k, fx.get(k) or {"source_map": files.get("content_map") or val["evidence"], "change_log": val["change_log"], "uncertainty": val["uncertainty"],
                                       "material_gaps": (exc.get("material_missing") if isinstance(exc, dict) else None) or ["none recorded"], "exceptions": exc}[k])
    for k, v in fx.items():
        res.setdefault(k, v)
    res["case_id"], res["status"] = val["case_id"], st
    res["status_reasons"] = fx.get("status_reasons") or (errs or ["deliverables present; see compliance checks"])
    Path(out_path).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print("assembled %s: %d contract fields, status=%s; run the checker next" % (out_path, len(fields(contract)), st))


def baseline_check(deck, base, kmap, out_md, fails, warns, emap=None):
    """Preserved slides must be text-identical to the baseline deck; every other slide gets a before/after line diff
    against its baseline slide: --edit-map new:old if given, else the most similar unused baseline slide (word overlap +
    position, one-to-one) or "new". Writes a per-slide version diff (version_diff.md)."""
    a, b = slides_of(deck), slides_of(base)
    rows, detail, emap = [], [], dict(emap or {})
    ln = lambda t: [x.strip() for x in t.split("\n") if x.strip()]
    wd = lambda t: set(re.findall(r"\w[\w.%/+-]*", t.lower()))
    free_new = [i for i in range(1, len(a) + 1) if i not in kmap and i not in emap]
    free_old = [j for j in range(1, len(b) + 1) if j not in set(kmap.values()) | set(emap.values())]
    pairs = sorted(((len(wd(a[i - 1][0]) & wd(b[j - 1][0])) / float(len(wd(a[i - 1][0]) | wd(b[j - 1][0])) or 1) + 0.1 / (1 + abs(i - j)), i, j)
                    for i in free_new for j in free_old), reverse=True)
    for r, i, j in pairs:
        if r >= 0.3 and i not in emap and j not in emap.values():
            emap[i] = j
    for i, (t, n) in enumerate(a, 1):
        o = kmap.get(i)
        if o is None:  # edited (diff against its baseline slide) or new
            j = emap.get(i) if emap.get(i, 0) <= len(b) else None
            ttl = (ln(t) or [""])[0][:60]
            if j is None:
                rows.append("| %d | - | new slide | %s |" % (i, ttl))
                detail.append("### slide %d (new)\n" % i + "\n".join("+ " + x[:110] for x in ln(t)[:12]) + "\n")
                continue
            bt, bn = b[j - 1]
            minus, plus = [x for x in ln(bt) if x not in ln(t)], [x for x in ln(t) if x not in ln(bt)]
            rows.append("| %d | %d | edited (%d lines out, %d in%s) | %s |" % (i, j, len(minus), len(plus), ", notes changed" if bn != n else "", ttl))
            detail.append("### slide %d (from baseline slide %d)\n" % (i, j) + "\n".join(["- " + x[:110] for x in minus[:10]] + ["+ " + x[:110] for x in plus[:10]]) + "\n")
            continue
        if o > len(b):
            fails.append("keep-map: baseline has no slide %d" % o)
            continue
        bt, bn = b[o - 1]
        if bt != t:
            dl = [x for x in t.split("\n") if x not in bt.split("\n")][:2]
            fails.append("preserved slide %d (baseline %d) text changed: %s" % (i, o, dl))
            rows.append("| %d | %d | TEXT CHANGED | %s |" % (i, o, "; ".join(dl)[:80]))
        else:
            rows.append("| %d | %d | kept, identical text%s | |" % (i, o, "" if bn == n else ", notes changed"))
            if bn != n:
                warns.append("preserved slide %d: speaker notes differ from baseline slide %d (allowed only if the instruction asks)" % (i, o))
    mapped = set(kmap.values()) | {int(m) for m in re.findall(r"\| \d+ \| (\d+) \| edited", "\n".join(rows))}
    gone = sorted(set(range(1, len(b) + 1)) - mapped)
    Path(out_md).write_text("# Version diff vs %s (written by check_result.py)\n\n%d -> %d slides. Kept unchanged: %s. Baseline slides deleted: %s.\n\n"
                            "| new slide | baseline slide | status | title / first changed line |\n|---|---|---|---|\n%s\n\n## Line diff per edited/new slide (- before, + after)\n\n%s"
                            % (os.path.basename(base), len(b), len(a), sorted(kmap) or "none", ["%d: %s" % (g, (ln(b[g - 1][0]) or [""])[0][:40]) for g in gone] or "none",
                               "\n".join(rows), "\n".join(detail) or "(none)\n"), encoding="utf-8")
    print("baseline: %d preserved slides compared, %d edited/new slides diffed; written to %s" % (len(kmap), len(a) - len(kmap), out_md))


GENERIC = re.compile(r"^\s*(results?|methods?|methodology|introduction|background|conclusions?|discussion|summary|outline|experiments?|结果|方法|背景|引言|结论|讨论|总结|实验)\s*$", re.I)


def storyline_check(sl, res, warns):
    """Claim titles and page-type coverage (cover, motivation, method, result, conclusion)."""
    for i, (t, _) in enumerate(sl, 1):
        ttl = t.split("\n")[0]
        if i > 1 and GENERIC.match(ttl):
            warns.append("slide %d title %r is a topic, not a claim -> write the finding as the title" % (i, ttl))
    blob = (json.dumps(res, ensure_ascii=False) + " ".join(t for t, _ in sl)).lower()
    need = {"motivation/problem": r"motivat|problem|background|gap|question|动机|问题|背景", "method": r"method|approach|design|方法|做法|实验设计",
            "result/evidence": r"result|evidence|finding|结果|证据|发现", "conclusion/limitations": r"conclu|limit|take-home|summary|结论|局限|总结"}
    miss = [k for k, rx in need.items() if not re.search(rx, blob)]
    if miss and len(sl) >= 5:
        warns.append("page types not found in the deck/content map: %s (cover -> problem -> method -> results -> conclusion/limitations)" % miss)


CHECKS = [  # (check name, regex over FAIL/WARN messages, applies-if, basis when nothing matched)
    ("slide count", r"slides, work order requires|slides, limit is", lambda a: a.slides or a.max_slides, "deck slide count = required"),
    ("template inheritance (masters/layouts/theme byte-identical)", r"template parts|layouts that are not in the template|free text boxes", lambda a: a.template, "parts compared with the template file"),
    ("preserved slides unchanged", r"preserved slide \d|keep-map", lambda a: a.baseline and a.keep_map, "version_diff.md"),
    ("per-slide before/after record vs starting deck", r"keep-map|baseline has no", lambda a: a.baseline and not a.keep_map and a.edit_map, "version_diff.md lists every slide's removed/added lines"),
    ("numbers traced to source text", r"numbers on slides|decimal numbers|integers on slides|neither paper nor deck|carry numbers", lambda a: True, "every number on the slides found in the source/paper text"),
    ("figure/table labels match paper captions", r"caption|label", lambda a: a.paper, "slide Fig./Table labels compared with the paper caption index"),
    ("speaker notes", r"speaker notes|notes mostly repeat", lambda a: True, "every slide has notes"),
    ("PDF/PNG export matches deck", r"\[render\]|PDF|PNG|rendered PDF", lambda a: True, "PDF page count = slide count; PNG previews present"),
    ("font size floor", r"pt is below|below --min-pt|table text|explicit", lambda a: a.min_pt, "no explicit body size below the floor"),
    ("contract fields and status", r"contract field|sub-field|placeholder text|^status|case_id is|listed file", lambda a: True, "all contract fields filled, one-word status")]


def record_checks(out, res, a, fails, warns):
    """Write the checker's own verdicts into result.json: compliance rows (by=check_result.py, replaced on every run) + checker_record."""
    import datetime
    rows = []
    for name, rx, applies, basis in CHECKS:
        if not applies(a):
            continue
        f = [m for m in fails if re.search(rx, m, re.I)]
        w = [m for m in warns if re.search(rx, m, re.I)]
        rows.append({"check": name, "result": "FAIL" if f else "WARN" if w else "PASS", "basis": ("; ".join((f + w)[:2])[:300] if f or w else basis), "by": "check_result.py"})
    try:  # evidence quotes: verdicts written by pptx_kit.py build into content_map.json
        qc = re.findall(r'"quote_check"\s*:\s*"([^"]*)"', Path(os.path.join(os.path.dirname(out), "content_map.json")).read_text(encoding="utf-8"))
        if qc:
            bad = [x for x in qc if x.startswith("NOT")]
            rows.append({"check": "evidence quotes located in the paper text", "result": "WARN" if bad else "PASS", "by": "check_result.py",
                         "basis": "%d quotes: %d verbatim, %d words-found, %d not found" % (len(qc), sum(x.startswith("verbatim") for x in qc), sum(x.startswith("words") for x in qc), len(bad))})
    except Exception:
        pass
    done = res.get("instructions_done")
    if isinstance(done, dict):
        rows += [{"check": "instruction %s executed" % k, "result": "PASS" if v and not re.search(r"not done|未执行|skipped|FAIL", json.dumps(v, ensure_ascii=False), re.I) else "WARN",
                  "basis": (v if isinstance(v, str) else json.dumps(v, ensure_ascii=False))[:200], "by": "check_result.py"} for k, v in done.items()]
    key = next((k for k in res if re.search(r"compliance|check|verif|validation|合规|检查|核对|校验", k, re.I) and k != "checker_record"), "compliance_checks")
    cur = res.get(key)
    if isinstance(cur, list):
        res[key] = [r for r in cur if not (isinstance(r, dict) and r.get("by") == "check_result.py")] + rows
    elif isinstance(cur, dict):
        cur["automated_checks"] = rows
    else:
        res[key] = ([{"check": "agent note", "result": "INFO", "basis": str(cur)}] if cur and not empty(cur) else []) + rows
    res["checker_record"] = {"command": "python3 check_result.py " + " ".join(sys.argv[1:]), "verdict": "FAIL" if fails else "PASS",
                             "fails": fails, "warns": warns, "at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    Path(out).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print("result.json: %d check rows written to '%s' + checker_record" % (len(rows), key))


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
    ap.add_argument("--preserved", help="comma list of slides that must stay unchanged (paper mismatches there become WARN)")
    ap.add_argument("--min-pt", type=float, help="smallest allowed explicit body font size")
    ap.add_argument("--init", action="store_true", help="write a skeleton result.json (status partial) and exit")
    ap.add_argument("--assemble", nargs="?", const="", help="FACTS.json: write result.json filling every contract key by meaning, then exit")
    ap.add_argument("--paper-advisory", action="store_true", help="paper mismatches are proposals (WARN), e.g. deck-edit tasks that did not ask for fact-checking")
    ap.add_argument("--baseline", help="baseline deck (v0 / starting deck) for preserved-slide checks and the per-slide before/after diff")
    ap.add_argument("--keep-map", help="new:old pairs of preserved slides, e.g. 1:1,2:2,9:8")
    ap.add_argument("--edit-map", help="new:old pairs of edited slides for the before/after diff, e.g. 3:3,6:6,10:8 (unlisted: matched by similarity); 'auto' = all by similarity")
    a = ap.parse_args()
    case = load(a.case)
    if a.assemble is not None:
        return assemble(case, a.out, a.assemble or os.path.join(os.environ.get("WORK_DIR", "/app/work"), "facts.json")) or 0
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
        kmap = {int(x): int(y) for x, y in re.findall(r"(\d+)\s*:\s*(\d+)", a.keep_map or "")}
        pres = {int(v) for v in re.findall(r"\d+", a.preserved or "")} | set(kmap)
        if a.baseline and (kmap or a.edit_map):  # --edit-map alone (adapt: every slide migrated) -> diff only, nothing preserved
            baseline_check(d, a.baseline, kmap, os.path.join(os.path.dirname(a.out), "version_diff.md"), fails, warns,
                           {int(x): int(y) for x, y in re.findall(r"(\d+)\s*:\s*(\d+)", a.edit_map or "")})
        storyline_check(sl, res, warns)
        if a.paper_advisory:
            pres |= set(range(1, len(sl) + 1))
        if a.paper:
            paper_check(sl, a.paper, [s for s in srcs if os.path.abspath(s) != os.path.abspath(a.paper)], fails, warns, pres)
        if a.template:
            check_template(d, a.template, fails, warns)
        deck_audit(d, len(sl), lost_by, a.min_pt, os.path.join(os.path.dirname(a.out), "slide_audit.md"), fails, warns, pres)
    for p in sorted(set(re.findall(r'"(/[^"\s]+\.(?:pptx|potx|pdf|png|jpg|md|json|csv|txt|py))"', json.dumps(res, ensure_ascii=False)))):
        if not Path(p).exists():
            fails.append("listed file does not exist: %s" % p)
    blog = os.path.join(os.environ.get("WORK_DIR", "/app/work"), "build.log")
    if os.path.exists(blog):
        bw = [l.strip() for l in open(blog, encoding="utf-8", errors="ignore") if l.startswith("WARN")]
        if bw:
            warns.append("build.log still has %d WARN lines (fix, or list each in exceptions): %s" % (len(bw), bw[0][:90]))
    if st != "complete":
        warns += [f + " [allowed: status is %s; keep it in exceptions.run_failures]" % raw for f in fails if f.startswith("[render]")]
        fails = [f for f in fails if not f.startswith("[render]")]
    if st == "complete" and fails:
        fails.append("status 'complete' while the problems above remain -> fix them or use 'partial'")
    print("\n".join(["WARN: " + w for w in warns] + ["FAIL: " + f for f in fails]))
    try:
        record_checks(a.out, res, a, fails, warns)
    except Exception as e:  # recording must never break the check itself
        print("WARN: could not write check rows into result.json: %s" % e)
    if fails:
        return 1
    print("PASS: case_id ok, %d contract fields filled, status=%s" % (len(spec), raw))
    return 0


if __name__ == "__main__":
    sys.exit(main())
