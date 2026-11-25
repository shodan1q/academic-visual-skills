#!/usr/bin/env python3
"""deck_flow.py - three one-call wrappers around pptx_kit.py and check_result.py (stdlib only, Python 3.8+).

  python3 deck_flow.py start                  # find the inputs, write the result.json skeleton, inspect template + starting deck
                                              # (-> v0.txt, v0.pptx), pdftotext the paper (-> paper.txt), list captions,
                                              # pre-check the starting deck against the paper (-> precheck.md)
  python3 deck_flow.py build SPEC.json        # build one version, snapshot its text, diff against v0 and the previous version,
                                              # copy deck + spec + diff into $OUT_DIR at once (a deliverable exists after every build)
                                              # and print an edit-scope check: which shapes of each edited slide changed / were lost
  python3 deck_flow.py finish --slides N [--fact-check] [--min-pt 18] [--keep-map 1:1,2:2 --edit-map 3:3] [--template T.pptx]
                                              # render final (+ starting deck for comparison), copy the records, write the
                                              # per-slide change log (before/after, shapes touched, reason, rollback) from the
                                              # files themselves, time_record.json, assemble result.json, run the checker last
                                              # (keep/edit maps are derived from the delivered spec when not given)

Paths: CASE_JSON (/input/case.json), WORK_DIR (/app/work), OUT_DIR (/app/output). No step raises: a missing tool or file is
printed and recorded, the remaining steps still run. Everything here can also be done by hand with the two underlying scripts.
"""
import datetime, difflib, glob, hashlib, json, os, re, shutil, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
KIT, CHK = os.path.join(HERE, "pptx_kit.py"), os.path.join(HERE, "check_result.py")
CASE = os.environ.get("CASE_JSON", "/input/case.json")
WORK, OUT = os.environ.get("WORK_DIR", "/app/work"), os.environ.get("OUT_DIR", "/app/output")
BUDGET = float(os.environ.get("RUN_BUDGET_S", "900"))
now = lambda: datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sh(cmd, t=120, show=True, save=None):
    """Run a command with a time limit; return (rc, output). Never raises."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=max(5, t))
        rc, out = r.returncode, (r.stdout or "") + (r.stderr or "")
    except Exception as e:  # missing binary, timeout
        rc, out = -1, "%s: %s" % (type(e).__name__, e)
    if save:
        open(save, "w", encoding="utf-8").write(out)
    if show:
        print(out.rstrip())
    return rc, out


def rj(p, d=None):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return d


def elapsed():
    try:
        t0 = datetime.datetime.strptime(open(os.path.join(WORK, "t_start")).read().strip(), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
        return (datetime.datetime.now(datetime.timezone.utc) - t0).total_seconds()
    except Exception:
        return 0.0


def cp(src, dst):
    try:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(src, dst)
        return True
    except Exception as e:
        print("(copy skipped %s: %s)" % (src, e))
        return False


def find_inputs():
    roots = [os.path.dirname(os.path.abspath(CASE))] + (["/input"] if os.path.isdir("/input") else [])
    files = []
    for r in roots:
        for d, _, fs in os.walk(r):
            if d[len(r):].count(os.sep) <= 3:
                files += [os.path.join(d, f) for f in fs]
    files = sorted(set(files))
    first = lambda rx: next((f for f in files if re.search(rx, os.path.basename(f), re.I)), None)
    pp = [f for f in files if f.lower().endswith((".pptx", ".potx"))]
    return {"case": CASE, "files": files, "workorder": first(r"work-?order.*\.json$"), "material": first(r"^material.*\.json$"),
            "template": first(r"template.*\.(pptx|potx)$") or first(r"\.potx$"),
            "starting_deck": first(r"(start|initial|draft|current|v0|old|orig).*\.pptx$") or next((f for f in pp if not re.search(r"template", os.path.basename(f), re.I)), None),
            "pdfs": [f for f in files if f.lower().endswith(".pdf")],
            "data": [f for f in files if f.lower().endswith((".csv", ".tsv", ".xlsx", ".txt", ".md", ".tex")) and not f.lower().endswith("task.md")]}


def instructions(wo):
    """Edit instructions of the work order as an ordered {E1: verbatim text} dict (labels already present are kept)."""
    best = []
    def walk(o, key=""):
        nonlocal best
        if isinstance(o, dict):
            for k, v in o.items():
                walk(v, str(k))
        elif isinstance(o, list):
            if o and all(isinstance(x, (str, dict)) for x in o) and re.search(r"edit|instruct|change|request|revision|task|step|修改|指令|编辑|改动|要求", key, re.I) and len(o) > len(best):
                best = o
            for x in o:
                walk(x, key)
    walk(wo)
    out = {}
    for n, x in enumerate(best, 1):
        t = x if isinstance(x, str) else json.dumps(x, ensure_ascii=False)
        m = re.match(r"\s*(E\d+)\s*[:：.)-]\s*(.*)", t, re.S)
        out[m.group(1) if m else "E%d" % n] = (m.group(2) if m else t).strip()
    return out


def inventory(path):
    """Per slide: every shape (footer placeholders left out) with kind, name, text, position and a content hash."""
    sys.dont_write_bytecode = True
    sys.path.insert(0, HERE) if HERE not in sys.path else None
    import pptx_kit as K
    z, slides, _, _ = K.load(path)
    out = []
    for sl in slides:
        x, sr, items = K.rd(z, sl), K.rels(z, sl), []
        for m in re.finditer(K.SHAPE, x, re.S):
            b = m.group(0)
            ph = K._pht(b)
            if ph in K.FOOT:
                continue
            kind = "picture" if b.startswith("<p:pic") else "table" if "<a:tbl>" in b else "graphic object" if b.startswith("<p:graphicFrame") else ("placeholder " + ph) if ph else "text box"
            off, emb = re.search(r'<a:off x="(-?\d+)" y="(-?\d+)"/>\s*<a:ext cx="(\d+)" cy="(\d+)"', b), re.search(r'r:embed="([^"]+)"', b)
            media = hashlib.md5(z.get(sr.get(emb.group(1), ("", ""))[1], b"")).hexdigest()[:8] if emb else ""
            items.append({"kind": kind, "name": K._name(b), "text": " / ".join(t for t in K.text_of(b) if t.strip()), "box": off.groups() if off else None, "media": media,
                          "raw": hashlib.md5(re.sub(r'<p:cNvPr id="\d+"', "", b).encode("utf-8")).hexdigest()})
        out.append(items)
    return out


def scope(old, new):
    """Shape-level comparison of one baseline slide with its new version: (untouched, changed, removed, added) lists of readable labels."""
    lab = lambda s: "%s '%s'%s" % (s["kind"], s["name"], (' "%s"' % s["text"][:40]) if s["text"] and s["kind"] in ("text box", "table") else "")
    left, same, changed, removed = list(new), [], [], []
    for o in old:
        hit = next((n for n in left if n["raw"] == o["raw"]), None)
        if hit:
            same.append(lab(o))
            left.remove(hit)
    for o in old:
        if any(o["raw"] == n["raw"] for n in new):
            continue
        hit = (next((n for n in left if o["media"] and n["media"] == o["media"]), None) or next((n for n in left if n["kind"] == o["kind"] and n["name"] == o["name"]), None)
               or next((n for n in left if n["kind"] == o["kind"] and o["text"] and n["text"] == o["text"]), None))
        if hit:
            left.remove(hit)
            what = [w for w, c in (("text", hit["text"] != o["text"]), ("position/size", hit["box"] != o["box"] and o["box"] and hit["box"]), ("picture file", hit["media"] != o["media"])) if c]
            changed.append("%s (%s)" % (lab(o), ", ".join(what) or "formatting / re-created with the same content"))
        else:
            removed.append(lab(o))
    return same, changed, removed, [lab(n) for n in left]


def slide_map(S, a, b, kmap=None, emap=None):
    """For every slide of the delivered spec: (mode, baseline slide or None). mode = kept | notes only | edited in place | rebuilt | new."""
    wd = lambda t: set(re.findall(r"\w[\w.%/+-]*", t.lower()))
    out, used = [], set()
    for i, e in enumerate(S.get("slides") or [], 1):
        if isinstance(e, dict) and "keep" in e:
            j = int(e["keep"])
            mode = "edited in place" if any(e.get(k) for k in ("replace", "set", "remove", "image", "source_note")) else "notes only" if e.get("notes") is not None else "kept"
            out.append((mode, j))
            used.add(j)
        else:
            out.append(("rebuilt", int(e["from"]) if isinstance(e, dict) and str(e.get("from", "")).isdigit() else (emap or {}).get(i)))
    used |= {j for m, j in out if j}
    for i, (m, j) in enumerate(out, 1):  # rebuilt slides without "from": the most similar unused baseline slide, else new
        if m == "rebuilt" and j is None and i <= len(a):
            nums = lambda t: set(re.findall(r"\d+(?:\.\d+)?", t))  # a translated slide shares its numbers, not its words
            sim = lambda x, y: max(len(wd(x) & wd(y)) / float(len(wd(x) | wd(y)) or 1), (len(nums(x) & nums(y)) / float(len(nums(x) | nums(y)) or 1)) if len(nums(x) & nums(y)) >= 2 else 0)
            c = sorted(((sim(a[i - 1][0], b[k - 1][0]) + 0.1 / (1 + abs(i - k)), k) for k in range(1, len(b) + 1) if k not in used), reverse=True)
            if c and c[0][0] >= 0.3:
                out[i - 1] = ("rebuilt", c[0][1])
                used.add(c[0][1])
            else:
                out[i - 1] = ("new", None)
    return out


def change_record(deck, v0, spec_path, k, fx, vd, emap_given=None):
    """Compare the delivered deck with the starting deck slide by slide and shape by shape. Returns (markdown, summary rows, warnings, kmap, emap)."""
    sys.dont_write_bytecode = True
    sys.path.insert(0, HERE) if HERE not in sys.path else None
    import check_result as C
    S = rj(spec_path, {}) or {}
    a, b, ia, ib = C.slides_of(deck), C.slides_of(v0), inventory(deck), inventory(v0)
    sm = slide_map(S, a, b, emap=emap_given)
    ins = rj(os.path.join(WORK, "instructions.json"), {}) or {}
    cm = {int(r["slide"]): r for r in (fx.get("content_map") or []) if isinstance(r, dict) and str(r.get("slide", "")).isdigit()}
    done = fx.get("instructions_done") if isinstance(fx.get("instructions_done"), dict) else {}
    ln = lambda t: [x.strip() for x in t.split("\n") if x.strip()]
    rows, detail, summary, warns, kmap, emap = [], [], [], [], {}, {}
    seq = [j for _, j in sm[:len(a)] if j]  # baseline numbers in their new order; slides outside the longest increasing run were moved
    best = []
    for x in seq:
        cand = max([c for c in best if c[-1] < x], key=len, default=[]) + [x]
        best.append(cand)
    moved = set(seq) - set(max(best, key=len, default=[]))
    for i, (mode, j) in enumerate(sm, 1):
        if i > len(a):
            break
        t, n = a[i - 1]
        ok_j = j is not None and 1 <= j <= len(b)
        if mode == "kept" and ok_j and b[j - 1] == (t, n) and [s["raw"] for s in ia[i - 1]] == [s["raw"] for s in ib[j - 1]]:
            kmap[i] = j
            rows.append("| %d | %d | kept: every shape and the notes identical%s | - | - |" % (i, j, ", moved (was slide %d)" % j if j in moved else ""))
            continue
        e = (S.get("slides") or [])[i - 1] if i <= len(S.get("slides") or []) else {}
        tag = str((cm.get(i) or {}).get("instruction") or "").strip(" -") or ",".join(dict.fromkeys(re.findall(r"\bE\d+\b", str(e.get("notes") or "") if isinstance(e, dict) else ""))) or "none recorded"
        if not ok_j:
            rows.append("| %d | - | new slide | %s | %d shapes added |" % (i, tag, len(ia[i - 1])))
            detail.append("### Slide %d - new slide - instruction %s\n%s\n\nAfter:\n%s\n\nRollback: delete entry %d from versions/spec_v%d.json and rebuild.\n" % (
                i, tag, "".join("Instruction %s (verbatim): %s\n" % (e, ins[e]) for e in re.findall(r"E\d+", tag) if e in ins), "\n".join("+ " + x[:160] for x in ln(t)[:14]), i, k))
            summary.append({"slide": i, "baseline_slide": None, "change": "new slide", "instruction": tag, "rollback": "delete spec entry %d, rebuild" % i})
            if tag == "none recorded":
                warns.append("slide %d is new but no instruction is recorded for it in facts.json content_map" % i)
            continue
        emap[i] = j
        bt, bn = b[j - 1]
        same, chg, rem, add = scope(ib[j - 1], ia[i - 1])
        minus, plus = [x for x in ln(bt) if x not in ln(t)], [x for x in ln(t) if x not in ln(bt)]
        sc = "%d baseline shapes: %d byte-identical" % (len(ib[j - 1]), len(same)) + ("; changed: " + "; ".join(chg) if chg else "") + ("; not carried over: " + "; ".join(rem) if rem else "") + ("; added: " + "; ".join(add) if add else "")
        if not mode.startswith("rebuilt") and not rem:
            sc += "; every shape kept its place and formatting" if not any("position" in c for c in chg) else ""
        if j in moved:
            mode += ", moved (was slide %d)" % j
        if mode == "kept":
            mode = "edited in place"
        rows.append("| %d | %d | %s%s | %s | %s |" % (i, j, mode, ", notes changed" if bn != n else "", tag, sc.replace("|", "/")[:260]))
        d = ["### Slide %d (baseline slide %d) - %s - instruction %s" % (i, j, mode, tag)]
        d += ["Instruction %s (verbatim): %s" % (e, ins[e]) for e in re.findall(r"E\d+", tag) if e in ins]
        d += ["Reason / what was done (author): %s" % done[e] for e in re.findall(r"E\d+", tag) if e in done]
        d += ["Scope (computed from the two files): " + sc + "."]
        if minus or plus:
            d += ["", "Text before -> after:"] + ["- " + x[:200] for x in minus[:12]] + ["+ " + x[:200] for x in plus[:12]]
        if bn != n:
            d += ["", "Notes before: " + (bn[:300] or "(none)"), "Notes after:  " + (n[:400] or "(none)")]
        d += ["", "Rollback: in versions/spec_v%d.json replace entry %d by {\"keep\": %d} and rebuild (python3 pptx_kit.py build versions/spec_v%d.json); the untouched starting deck is versions/v0.pptx." % (k, i, j, k), ""]
        detail.append("\n".join(d))
        summary.append({"slide": i, "baseline_slide": j, "change": mode + (", notes changed" if bn != n else ""), "instruction": tag, "shapes_identical": "%d/%d" % (len(same), len(ib[j - 1])),
                        "shapes_changed": chg, "shapes_not_carried_over": rem, "shapes_added": add, "text_out": minus[:6], "text_in": plus[:6], "rollback": "spec entry %d -> {\"keep\": %d}, rebuild" % (i, j)})
        if tag == "none recorded":
            warns.append("slide %d differs from baseline slide %d but no instruction is recorded for it (facts.json content_map[].instruction) -> name the instruction or restore it with {\"keep\": %d}" % (i, j, j))
        hand = [r for r in rem if not r.startswith("placeholder")]  # pictures, tables, text boxes, drawings: content somebody placed by hand
        summary[-1]["hand_placed_shapes_lost"] = hand
        if hand and mode.startswith("rebuilt"):
            warns.append("slide %d was rebuilt and lost baseline shapes: %s -> if the instruction only changes text, edit in place instead: {\"keep\": %d, \"set\": {\"title\": ..., \"body\": [...]}}" % (i, "; ".join(hand)[:200], j))
    gone = [g for g in range(1, len(b) + 1) if g not in set(kmap.values()) | set(emap.values())]
    for g in gone:
        summary.append({"slide": None, "baseline_slide": g, "change": "deleted: %s" % (ln(b[g - 1][0]) or [""])[0][:60], "rollback": "add {\"keep\": %d} to the spec, rebuild" % g})
    ks = sorted(int(m) for m in re.findall(r"spec_v(\d+)\.json", " ".join(os.listdir(vd)))) if os.path.isdir(vd) else [k]
    md = ("## Verified change record (computed by deck_flow.py from starting-deck v0 and the delivered deck; not hand-written)\n\n"
          "%d -> %d slides. Identical to the starting deck: %s. Changed or new: %s. Deleted baseline slides: %s.\n\n"
          "| slide | baseline slide | change | instruction | shapes touched |\n|---|---|---|---|---|\n%s\n\n%s\n"
          % (len(b), len(a), sorted(kmap) or "none", sorted(set(range(1, len(a) + 1)) - set(kmap)) or "none",
             "; ".join("%d '%s' (rollback: add {\"keep\": %d} to the spec)" % (g, (ln(b[g - 1][0]) or [""])[0][:50], g) for g in gone) or "none", "\n".join(rows), "\n".join(detail)))
    md += "## Changes without a recorded instruction\n" + ("\n".join("- " + w for w in warns if "no instruction" in w) or "- none: every changed slide is tied to an instruction") + "\n\n"
    md += "## Versions\n- v0 = starting deck as received (versions/v0.pptx, v0.txt, v0_before.pdf)\n" + "".join("- v%d = versions/spec_v%d.json%s\n" % (x, x, " (delivered)" if x == ks[-1] else "; diff to the next version: versions/diff_v%d_v%d.txt" % (x, x + 1)) for x in ks)
    return md, summary, warns, kmap, emap


def start():
    os.makedirs(WORK, exist_ok=True)
    os.makedirs(OUT, exist_ok=True)
    ts = os.path.join(WORK, "t_start")
    if not os.path.exists(ts):
        open(ts, "w").write(now())
    inp = find_inputs()
    print("== input files ==\n" + "\n".join("%9d  %s" % (os.path.getsize(f), f) for f in inp["files"][:60]))
    sh([sys.executable, CHK, "--init"])
    for k in ("workorder", "material"):
        if inp[k] and os.path.getsize(inp[k]) < 60000:
            print("\n== %s: %s (read every field) ==" % (k, inp[k]))
            print(open(inp[k], encoding="utf-8", errors="ignore").read())
    try:
        ins = instructions(rj(inp["workorder"], {})) if inp["workorder"] else {}
        if ins:
            json.dump(ins, open(os.path.join(WORK, "instructions.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            print("\n== edit instructions, numbered (use exactly these labels in plan.md / facts.json; saved to %s/instructions.json) ==\n%s" % (WORK, "\n".join("%s: %s" % kv for kv in ins.items())))
    except Exception as e:
        print("(instructions not numbered: %s)" % e)
    tpl_out = ""
    if inp["template"]:
        print("\n== template: %s ==" % inp["template"])
        tpl_out = sh([sys.executable, KIT, "inspect", inp["template"]], 60)[1]
    if inp["starting_deck"]:
        v0 = os.path.join(WORK, "v0.txt")
        cp(inp["starting_deck"], os.path.join(WORK, "v0.pptx"))
        rc, out = sh([sys.executable, KIT, "inspect", inp["starting_deck"], "--full"], 60, show=False, save=v0)
        i = out.find("\nslide 1 ")
        print("\n== starting deck: %s (layouts + every slide; full copy in %s, baseline copy %s/v0.pptx) ==" % (inp["starting_deck"], v0, WORK))
        lay = lambda t: re.findall(r"\nlayout \d+: (.*?) \(", t)
        same = inp["template"] and lay(out) == lay(tpl_out)
        print(("(layouts: same names as the template above)\n" + out[max(i, 0):]) if same else out)
    paper = os.path.join(WORK, "paper.txt")
    for n, pdf in enumerate(inp["pdfs"][:4]):
        dst = paper if n == 0 else os.path.join(WORK, "paper%d.txt" % (n + 1))
        rc, out = sh(["pdftotext", "-layout", pdf, dst], 90, show=False)
        if rc != 0 or not os.path.exists(dst) or os.path.getsize(dst) < 200:
            print("\n== %s: no text layer extracted (%s) -> read it another way or record a material gap ==" % (pdf, out.strip()[:120] or "empty"))
            continue
        pages = open(dst, encoding="utf-8", errors="ignore").read().split("\f")
        print("\n== %s -> %s: %d pages, %d chars. Captions (page | caption): ==" % (pdf, dst, len(pages), sum(map(len, pages))))
        for i, p in enumerate(pages, 1):
            for l in p.splitlines():
                if re.match(r"\s*(Fig(ure)?\.?|Table|Tab\.|图|表)\s*S?\d+\s*[.:|：]", l):
                    print("  p.%d | %s" % (i, l.strip()[:110]))
        body = "\n".join("[p.%d] %s" % (i, p.strip()) for i, p in enumerate(pages, 1))
        if n == 0 and len(body) <= 14000:
            print("-- full text (short paper; [p.N] = PDF page) --\n" + re.sub(r"\n{3,}", "\n\n", re.sub(r"[ \t]{3,}", "  ", body)))
        else:
            print("-- long text: read %s in parts (sed -n '1,200p'), grep -n for the numbers you need --" % dst)
    inp["paper_txt"] = paper if os.path.exists(paper) else None
    json.dump(inp, open(os.path.join(WORK, "inputs.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if inp["starting_deck"] and inp["paper_txt"]:
        try:  # the starting deck's own numbers / figure labels against the paper: candidates only, nothing is changed
            sys.dont_write_bytecode = True
            sys.path.insert(0, HERE)
            import check_result as C
            f, w = [], []
            C.paper_check(C.slides_of(inp["starting_deck"]), paper, [], f, w)
            rows = [m.replace("found in neither paper nor deck", "NOT found in the paper text") for m in f + w]
            md = "# Starting deck vs paper (automatic pre-check; candidates, verify each in paper.txt)\n\n" + ("\n".join("- " + r for r in rows) or "- no mismatch found") + \
                 "\n\nRule: correct a candidate only on a slide an instruction tells you to fact-check or rewrite; list every other one as 'proposed, not applied'.\n"
            open(os.path.join(WORK, "precheck.md"), "w", encoding="utf-8").write(md)
            print("\n== starting deck vs paper: mismatch candidates (saved to %s/precheck.md) ==\n%s" % (WORK, "\n".join("- " + r for r in rows) or "- none"))
        except Exception as e:
            print("(pre-check skipped: %s)" % e)
    print("\nNEXT: verify in %s every number / label you will put on a new or edited slide (grep -n), then write plan.md + spec_v1.json and run: deck_flow.py build spec_v1.json" % paper)


def snapshot(deck, txt):
    rc, out = sh([sys.executable, KIT, "inspect", deck, "--full"], 60, show=False)
    i = out.find("\nslide 1 ")
    open(txt, "w", encoding="utf-8").write(out)
    return out[max(i, 0):].splitlines()


def build(spec):
    S = rj(spec)
    if not isinstance(S, dict) or "slides" not in S:
        sys.exit("ERROR: %s is not a readable spec (JSON with template, out, slides)" % spec)
    m = re.search(r"v(\d+)", os.path.basename(spec))
    k = int(m.group(1)) if m else len(glob.glob(os.path.join(WORK, "v[1-9]*.txt"))) + 1
    deck = S.get("out") or os.path.join(WORK, "v%d.pptx" % k)
    rc, out = sh([sys.executable, KIT, "build", spec], 120, save=os.path.join(WORK, "build.log"))
    if rc != 0 or not os.path.exists(deck):
        sys.exit("BUILD FAILED (nothing copied; the previous version stays the deliverable). Fix the spec and rerun.")
    new = snapshot(deck, os.path.join(WORK, "v%d.txt" % k))
    vd = os.path.join(OUT, "versions")
    os.makedirs(vd, exist_ok=True)
    for base in ([0] if os.path.exists(os.path.join(WORK, "v0.txt")) else []) + ([k - 1] if k > 1 and os.path.exists(os.path.join(WORK, "v%d.txt" % (k - 1))) else []):
        old = open(os.path.join(WORK, "v%d.txt" % base), encoding="utf-8").read()
        old = old[max(old.find("\nslide 1 "), 0):].splitlines()
        d = list(difflib.unified_diff(old, new, "v%d" % base, "v%d" % k, n=1, lineterm=""))
        name = "diff_v%d_v%d.txt" % (base, k)
        open(os.path.join(WORK, name), "w", encoding="utf-8").write("\n".join(d) + "\n")
        cp(os.path.join(WORK, name), os.path.join(vd, name))
        print("\n== %s (%d changed lines; only instructed edits may appear, slide-number shifts are normal) ==" % (name, sum(1 for x in d if x[:1] in "+-" and x[:3] not in ("+++", "---"))))
        print("\n".join(d[:160]) + ("\n... (%d more lines in the file)" % (len(d) - 160) if len(d) > 160 else ""))
    cp(spec, os.path.join(vd, "spec_v%d.json" % k))
    name = os.environ.get("DELIVER_NAME", "presentation.pptx")
    if cp(deck, os.path.join(OUT, name)):
        print("\ndelivered v%d -> %s (spec + diff in %s). Roll back = rebuild the previous spec_v*.json." % (k, os.path.join(OUT, name), vd))
    v0p = os.path.join(WORK, "v0.pptx")
    if os.path.exists(v0p):
        try:  # edit-scope check: what each changed slide kept, changed and lost, shape by shape
            md, summary, cw, km, em = change_record(deck, v0p, spec, k, rj(os.path.join(WORK, "facts.json"), {}) or {}, vd)
            print("\n== edit scope vs starting deck (shape level) ==\nidentical slides: %s" % (sorted(km) or "none"))
            for r in summary:
                if r.get("slide") and r.get("baseline_slide"):
                    print("slide %d (was %d) %s: %s shapes identical%s%s%s" % (r["slide"], r["baseline_slide"], r["change"], r["shapes_identical"],
                          "; changed: " + "; ".join(r["shapes_changed"]) if r["shapes_changed"] else "", "; not carried over: " + "; ".join(r["shapes_not_carried_over"]) if r["shapes_not_carried_over"] else "",
                          "; added: " + "; ".join(r["shapes_added"]) if r["shapes_added"] else ""))
                else:
                    print("slide %s: %s" % (r.get("slide") or "-", r["change"] if r.get("slide") else "baseline slide %d %s" % (r["baseline_slide"], r["change"])))
            for w in cw:
                if "no instruction" not in w:
                    print("SCOPE WARN: " + w)
        except Exception as e:
            print("(edit-scope check skipped: %s)" % e)
    nw = sum(1 for l in out.splitlines() if l.startswith("WARN"))
    print("build WARN lines: %d%s" % (nw, " -> fix overflow by cutting words / splitting, at most 2 rebuilds; then record the rest" if nw else ""))


def finish(argv):
    import argparse
    ap = argparse.ArgumentParser(prog="deck_flow.py finish")
    ap.add_argument("--slides", type=int)
    ap.add_argument("--keep-map", default="")
    ap.add_argument("--edit-map", default="")
    ap.add_argument("--min-pt", type=float)
    ap.add_argument("--template")
    ap.add_argument("--fact-check", action="store_true", help="the work order asks to check facts against the paper: paper mismatches are FAIL, not proposals")
    ap.add_argument("--no-before", action="store_true", help="skip rendering the starting deck")
    a = ap.parse_args(argv)
    inp = rj(os.path.join(WORK, "inputs.json"), {}) or find_inputs()
    deck = os.path.join(OUT, os.environ.get("DELIVER_NAME", "presentation.pptx"))
    if not os.path.exists(deck):
        last = sorted(glob.glob(os.path.join(WORK, "v[1-9]*.pptx")), key=os.path.getmtime)
        if not last or not cp(last[-1], deck):
            print("no deck to finish: run deck_flow.py build first; result.json stays at the skeleton (status partial)")
            return 1
    vd = os.path.join(OUT, "versions")
    os.makedirs(vd, exist_ok=True)
    left = BUDGET - elapsed()
    print("== render (%.0f s used, %.0f s left of the run budget) ==" % (elapsed(), left))
    rc, out = sh([sys.executable, KIT, "render", deck], min(280, max(40, left - 90)))
    if rc != 0 and not os.path.exists(os.path.join(OUT, "render.json")):
        json.dump({"pptx": deck, "pdf": None, "png": [], "status": "failed", "errors": ["render step did not finish: %s" % out.strip()[-200:]]},
                  open(os.path.join(OUT, "render.json"), "w"), indent=1)
    v0 = os.path.join(WORK, "v0.pptx")
    left = BUDGET - elapsed()
    rendered = (rj(os.path.join(OUT, "render.json"), {}) or {}).get("pdf")
    if os.path.exists(v0) and not a.no_before and left > 240 and rendered:
        rc, out = sh([sys.executable, KIT, "render", v0], min(150, left - 150), show=False)
        if os.path.exists(os.path.join(WORK, "v0.pdf")) and cp(os.path.join(WORK, "v0.pdf"), os.path.join(vd, "v0_before.pdf")):
            for p in glob.glob(os.path.join(WORK, "preview", "slide*.png")):
                cp(p, os.path.join(vd, "v0_before_preview", os.path.basename(p)))
            print("before-version export: %s (+ v0_before_preview/*.png) for page-by-page comparison" % os.path.join(vd, "v0_before.pdf"))
        else:
            print("(starting deck not rendered: %s)" % out.strip()[-120:])
    elif os.path.exists(v0):
        print("(starting-deck render skipped: %s)" % ("--no-before" if a.no_before else "no renderer" if not rendered else "time budget"))
    for f in ("plan.md", "corrections.md", "precheck.md", "content_map.json", "instructions.json"):
        src = os.path.join(WORK, f)
        if os.path.exists(src):
            cp(src, os.path.join(OUT if f in ("plan.md", "corrections.md", "content_map.json") else vd, f))
    for f in glob.glob(os.path.join(WORK, "spec_v*.json")) + glob.glob(os.path.join(WORK, "diff_v*.txt")) + glob.glob(os.path.join(WORK, "v[0-9]*.txt")):
        cp(f, os.path.join(vd, os.path.basename(f)))
    fx = rj(os.path.join(WORK, "facts.json"), {}) or {}
    if not os.path.exists(os.path.join(WORK, "facts.json")):
        print("WARN: %s/facts.json not found - result.json will only hold what the files on disk show" % WORK)
    cm = fx.get("content_map") if isinstance(fx.get("content_map"), list) else rj(os.path.join(OUT, "content_map.json"))
    if isinstance(fx.get("content_map"), list) and not os.path.exists(os.path.join(OUT, "content_map.json")):
        json.dump(fx["content_map"], open(os.path.join(OUT, "content_map.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    cl = fx.get("change_log")
    author = ""
    if os.path.exists(os.path.join(WORK, "change_log.md")):
        author = open(os.path.join(WORK, "change_log.md"), encoding="utf-8", errors="ignore").read().strip()
    elif cl:
        author = cl if isinstance(cl, str) else "\n".join(x if isinstance(x, str) else json.dumps(x, ensure_ascii=False) for x in cl)
    ks = sorted(int(m) for m in re.findall(r"spec_v(\d+)\.json", " ".join(os.listdir(vd))))
    kmap_auto, emap_auto, verified = {}, {}, ""
    if os.path.exists(v0) and ks:
        cp(v0, os.path.join(vd, "v0.pptx"))
        try:
            verified, summary, cw, kmap_auto, emap_auto = change_record(deck, v0, os.path.join(vd, "spec_v%d.json" % ks[-1]), ks[-1], fx, vd,
                                                                       {int(x): int(y) for x, y in re.findall(r"(\d+)\s*:\s*(\d+)", a.edit_map or "")})
            json.dump(summary, open(os.path.join(WORK, "change_summary.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            cp(os.path.join(WORK, "change_summary.json"), os.path.join(vd, "change_summary.json"))
            print("change_log.md: verified per-slide record written (%d changed/new slides, %d identical)" % (len([r for r in summary if r.get("slide")]), len(kmap_auto)))
            for w in cw:
                print("SCOPE WARN: " + w)
        except Exception as e:
            print("(verified change record skipped: %s)" % e)
    if not verified:  # no starting deck (generate) or comparison failed: still deliver a change record from what is known
        done = fx.get("instructions_done") if isinstance(fx.get("instructions_done"), dict) else {}
        verified = ("## Build record\n\n| version | item | what was done | rollback |\n|---|---|---|---|\n" + ("\n".join("| v%d | %s | %s | rebuild versions/spec_v%d.json |" % (ks[-1] if ks else 1, a_, str(b_).replace("|", "/")[:200], max((ks[-1] if ks else 1) - 1, 1)) for a_, b_ in done.items())
                    or "| v%d | deck | built from the template (no starting deck to compare with) | rebuild the spec |" % (ks[-1] if ks else 1)) +
                    "\n\n## Versions\n" + "".join("- v%d = versions/spec_v%d.json%s\n" % (x, x, " (delivered)" if x == ks[-1] else "") for x in ks))
    open(os.path.join(OUT, "change_log.md"), "w", encoding="utf-8").write("# Change log\n\n" + ("## Author's log\n\n" + re.sub(r"^# .*\n", "", author).strip() + "\n\n" if author else "") + verified)
    secs = [(r.get("slide"), r.get("seconds")) for r in (cm or []) if isinstance(r, dict) and isinstance(r.get("seconds"), (int, float))]
    tr = {"run_started_utc": (open(os.path.join(WORK, "t_start")).read().strip() if os.path.exists(os.path.join(WORK, "t_start")) else None), "run_finished_utc": now(),
          "run_seconds": round(elapsed()), "talk_seconds_per_slide": dict(secs), "talk_seconds_total": sum(s for _, s in secs) or None}
    json.dump(tr, open(os.path.join(OUT, "time_record.json"), "w"), indent=1)
    print("\n== assemble + check ==")
    sh([sys.executable, CHK, "--assemble"])
    mode = ""
    try:
        mode = json.dumps(rj(inp.get("workorder"), {}), ensure_ascii=False).lower()
        mode = (re.search(r'"mode"\s*:\s*"([a-z]+)', mode) or [None, ""])[1]
    except Exception:
        pass
    tpl = a.template or (inp.get("starting_deck") if mode.startswith("edit") and inp.get("starting_deck") else inp.get("template") or inp.get("starting_deck"))
    cmd = [sys.executable, CHK, "--deck", deck]
    cmd += ["--slides", str(a.slides)] if a.slides else []
    cmd += ["--template", tpl] if tpl and os.path.exists(tpl) else []
    paper = inp.get("paper_txt") or os.path.join(WORK, "paper.txt")
    if os.path.exists(paper):
        cmd += ["--paper", paper] + ([] if a.fact_check or not os.path.exists(v0) else ["--paper-advisory"])  # advisory only when editing a given deck
    cmd += ["--min-pt", str(a.min_pt)] if a.min_pt else []
    if os.path.exists(os.path.join(WORK, "v0.txt")):
        cmd += ["--source", os.path.join(WORK, "v0.txt")]
    else:  # no starting deck: numbers must come from the papers / data files, never from the deck's own snapshot
        cmd += ["--source"] + sorted(glob.glob(os.path.join(WORK, "paper*.txt"))) + [f for f in inp.get("data") or [] if f.lower().endswith((".csv", ".tsv", ".txt", ".md", ".tex")) and os.path.exists(f)]
    fmt = lambda d: ",".join("%d:%d" % kv for kv in sorted(d.items()))
    km, em = a.keep_map or fmt(kmap_auto), a.edit_map or fmt(emap_auto)
    if os.path.exists(v0) and (km or em):
        cmd += ["--baseline", v0] + (["--keep-map", km] if km else []) + (["--edit-map", em] if em else [])
        print("slide maps %s: keep %s | edited %s" % ("as given" if a.keep_map else "derived from the delivered spec and files", km or "-", em or "-"))
    rc, out = sh(cmd, 120)
    if rc != 0:  # never leave "complete" standing next to FAIL rows: the record must be true even if no further call follows
        res = rj(os.path.join(OUT, "result.json"))
        if isinstance(res, dict) and str(res.get("status", "")).lower() == "complete":
            res["status"] = "partial"
            res["status_reasons"] = ["checker FAIL: " + x[:200] for x in ((res.get("checker_record") or {}).get("fails") or [])[:6] if "status 'complete'" not in x] or ["checker reported FAIL"]
            json.dump(res, open(os.path.join(OUT, "result.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            print("status set to partial in result.json (checker FAIL); it returns to complete when a later finish passes")
    for f in ("version_diff.md", "slide_audit.md"):
        if os.path.exists(os.path.join(OUT, f)):
            cp(os.path.join(OUT, f), os.path.join(vd, f))
    print("\n== delivered in %s ==\n%s" % (OUT, "\n".join("  " + os.path.relpath(p, OUT) for p in sorted(glob.glob(os.path.join(OUT, "*")) + glob.glob(os.path.join(vd, "*")))[:60])))
    print("run time used: %.0f s. %s" % (elapsed(), "Checker PASS." if rc == 0 else "Checker reported FAIL lines above: fix what you can (at most 2 rounds: edit spec -> build -> finish); "
                                         "what cannot be fixed -> set \"status\": \"partial\" + status_reasons in facts.json and run finish once more."))
    return 0


if __name__ == "__main__":
    c = sys.argv[1] if len(sys.argv) > 1 else ""
    if c == "start":
        start()
    elif c == "build" and len(sys.argv) > 2:
        build(sys.argv[2])
    elif c == "finish":
        sys.exit(finish(sys.argv[2:]))
    else:
        sys.exit(__doc__)
