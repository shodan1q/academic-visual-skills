#!/usr/bin/env python3
"""deck_flow.py - three one-call wrappers around pptx_kit.py and check_result.py (stdlib only, Python 3.8+).

  python3 deck_flow.py start                  # find the inputs, write the result.json skeleton, inspect template + starting deck
                                              # (-> v0.txt, v0.pptx), pdftotext the paper (-> paper.txt), list captions,
                                              # pre-check the starting deck against the paper (-> precheck.md)
  python3 deck_flow.py build SPEC.json        # build one version, snapshot its text, diff against v0 and the previous version,
                                              # copy deck + spec + diff into $OUT_DIR at once (a deliverable exists after every build)
  python3 deck_flow.py finish --slides N --keep-map 1:1,2:2 --edit-map 3:3 [--fact-check] [--min-pt 18] [--template T.pptx]
                                              # render final (+ starting deck for comparison), copy the records, write
                                              # time_record.json, assemble result.json from facts.json, run the checker last

Paths: CASE_JSON (/input/case.json), WORK_DIR (/app/work), OUT_DIR (/app/output). No step raises: a missing tool or file is
printed and recorded, the remaining steps still run. Everything here can also be done by hand with the two underlying scripts.
"""
import datetime, difflib, glob, json, os, re, shutil, subprocess, sys, time

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
            print("\n== %s: %s (read every field; copy the edit instructions verbatim as E1, E2, ...) ==" % (k, inp[k]))
            print(open(inp[k], encoding="utf-8", errors="ignore").read())
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
    for f in ("plan.md", "corrections.md", "precheck.md", "change_log.md", "content_map.json"):
        src = os.path.join(WORK, f)
        if os.path.exists(src):
            cp(src, os.path.join(OUT if f in ("plan.md", "corrections.md", "change_log.md", "content_map.json") else vd, f))
    for f in glob.glob(os.path.join(WORK, "spec_v*.json")) + glob.glob(os.path.join(WORK, "diff_v*.txt")) + glob.glob(os.path.join(WORK, "v[0-9]*.txt")):
        cp(f, os.path.join(vd, os.path.basename(f)))
    fx = rj(os.path.join(WORK, "facts.json"), {}) or {}
    if not os.path.exists(os.path.join(WORK, "facts.json")):
        print("WARN: %s/facts.json not found - result.json will only hold what the files on disk show" % WORK)
    cm = fx.get("content_map") if isinstance(fx.get("content_map"), list) else rj(os.path.join(OUT, "content_map.json"))
    if isinstance(fx.get("content_map"), list) and not os.path.exists(os.path.join(OUT, "content_map.json")):
        json.dump(fx["content_map"], open(os.path.join(OUT, "content_map.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    cl = fx.get("change_log")
    if cl and not os.path.exists(os.path.join(OUT, "change_log.md")):
        open(os.path.join(OUT, "change_log.md"), "w", encoding="utf-8").write("# Change log\n\n" + (cl if isinstance(cl, str) else "\n".join(x if isinstance(x, str) else json.dumps(x, ensure_ascii=False) for x in cl)) + "\n")
    if not os.path.exists(os.path.join(OUT, "change_log.md")):  # never deliver without a change record: draft one from what is known
        ks = sorted(int(m) for m in re.findall(r"spec_v(\d+)\.json", " ".join(os.listdir(vd))))
        back = lambda k: "rebuild versions/spec_v%d.json" % (k - 1) if k > 1 else "deliver the starting deck (v0) again, or rebuild with {\"keep\": n} for that slide"
        done = fx.get("instructions_done") if isinstance(fx.get("instructions_done"), dict) else {}
        rows = ["| v%d | %s | %s | %s |" % (ks[-1] if ks else 1, k, str(v).replace("|", "/")[:200], back(ks[-1] if ks else 1)) for k, v in done.items()]
        open(os.path.join(OUT, "change_log.md"), "w", encoding="utf-8").write(
            "# Change log (drafted by deck_flow.py from facts.json; line-level before/after: version_diff.md, versions/diff_v*.txt)\n\n"
            "| version | instruction | what changed (slide, evidence) | rollback |\n|---|---|---|---|\n" + ("\n".join(rows) or "| - | - | no instructions_done in facts.json | - |") +
            "\n\n## Versions\n- v0 = starting deck as received (versions/v0.txt, v0_before.pdf)\n" + "".join("- v%d = versions/spec_v%d.json%s\n" % (k, k, " (delivered)" if k == ks[-1] else "") for k in ks))
        print("change_log.md drafted from facts.json (write your own $WORK_DIR/change_log.md for before/after wording and reasons)")
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
    if os.path.exists(v0) and a.keep_map:
        cmd += ["--baseline", v0, "--keep-map", a.keep_map] + (["--edit-map", a.edit_map] if a.edit_map else [])
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
