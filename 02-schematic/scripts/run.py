#!/usr/bin/env python3
"""run.py (stdlib, py3.8+): the two-call front end of this Skill. Env CASE_JSON / WORK_DIR / OUT_DIR first; else /input/case.json, /app/work, /app/output.
  start          print the inputs, PDF/text -> WORK_DIR/src.txt (numbered lines, passages naming the work order's terms), partial result.json
  build fig.txt  line spec (or JSON spec) -> figure.svg + PNG + PDF + content map + source map + pixel check + edited version + result.json
Every stage is optional and time-boxed: a stage that fails is recorded in result.json and the next one still runs.
Line spec: one item per line (title / color / key / group / node / edge / note / req / exc / edit / caption / summary), fields separated
by '|', '@12' or '@12-15' at the end = the lines of src.txt the item comes from. Full format: SKILL.md."""
import copy, csv, hashlib, json, os, re, shutil, subprocess, sys, time
from pathlib import Path
HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
CJ = Path(os.environ.get("CASE_JSON") or "/input/case.json")
IN, WORK, OUT = CJ.parent, Path(os.environ.get("WORK_DIR") or "/app/work"), Path(os.environ.get("OUT_DIR") or "/app/output")
T0 = time.time()
KINDS = ("gene", "mrna", "protein", "complex", "family", "small_molecule", "ion", "cell", "cell_type", "tissue", "organ", "organism",
		 "sample", "material", "reagent", "condition", "instrument", "process", "step", "data", "concept", "group")
SHAPES = ("rect", "round", "ellipse", "circle", "diamond")
TYPES = ("step", "flow", "phospho", "produce", "signal", "activate", "inhibit", "bind", "modify", "transport", "indirect", "line")
EVS = ("direct", "indirect", "hypothesis")
PALETTE = ("#0072B2", "#E69F00", "#009E73", "#CC79A7", "#56B4E9", "#D55E00", "#F0E442", "#999999")  # Okabe-Ito
TSYN = (("inhibit", r"inhib|repress|block|suppress|antagon|degrad|oppos|remov|抑制|阻断|降解|拮抗"), ("phospho", r"phospho|kinase|磷酸"),
		("bind", r"bind|recruit|complex|interact|dock|结合|募集|复合"), ("produce", r"produc|synth|express|transcri|translat|generat|yield|合成|表达|转录|翻译|产生"),
		("transport", r"transport|transloc|import|export|secret|traffic|shuttl|转运|转位|分泌|入核|出核"),
		("modify", r"modif|ubiquit|acetyl|methyl|cleav|process|修饰|泛素|乙酰|甲基|切割"), ("signal", r"signal|信号"),
		("flow", r"flow|material|sample|convert|differenti|transfer|物料|样本|分化|流"), ("step", r"step|next|then|order|sequen|follow|步骤|时序|顺序|下一步"),
		("activate", r"activ|promot|induc|stimul|upregul|enhanc|cause|激活|促进|诱导|上调|导致"), ("line", r"assoc|correl|^line$|relat|link|相关|关联|对应"))
ESYN = (("hypothesis", r"hypoth|untest|putativ|propos|specul|unknown|推测|假设|未验证|未检验"), ("indirect", r"indirect|overexpress|may|possib|间接|可能"))
KSYN = (("small_molecule", r"small|molecule|metabol|drug|compound|ligand|chemical|小分子|药物|化合物"), ("protein", r"protein|enzyme|kinase|receptor|ligase|蛋白|酶|受体"),
		("complex", r"complex|复合"), ("gene", r"gene|locus|基因"), ("mrna", r"mrna|transcript|rna"), ("cell_type", r"cell.?type|细胞类型"), ("cell", r"cell|细胞"),
		("organ", r"organ|器官"), ("tissue", r"tissue|组织"), ("sample", r"sample|specimen|样本|样品"), ("instrument", r"instrument|device|machine|equipment|仪器|设备"),
		("reagent", r"reagent|buffer|antibod|试剂|抗体"), ("material", r"material|材料"), ("condition", r"condition|treatment|param|条件|处理"),
		("data", r"data|output|result|readout|score|数据|结果"), ("step", r"step|stage|phase|步骤|阶段"), ("process", r"process|event|过程|事件"), ("concept", r"concept|idea|概念"))

STOP = set("""figure legend arrow arrows label labels export format colour color compartment compartments nodes edges source paper table italic upright style distinguish include shown required mechanism pathway relations request element changed""".split())
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
	print("NEXT: write %s (line spec: title/group/node/edge/req/exc/edit lines, see SKILL.md) and run: python3 %s build %s   [%s]" % (WORK / "figure.txt", os.path.abspath(__file__), WORK / "figure.txt", el()))
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
	sp = {"canvas": {}, "panels": [], "nodes": [], "edges": [], "texts": [], "legend": {"title": "Legend", "items": []}}
	notes = {"compliance_checks": [], "exceptions": []}
	edits, pid = [], {}
	for no, raw in enumerate(text.splitlines(), 1):
		line = raw.strip()
		if not line or line.startswith(("#", "//", "```")):
			continue
		isnote = bool(re.match(r"(req|exc)\b", line, re.I))
		line, src = cut(line, isnote)
		if isnote:
			src = None  # the pointer stays in the sentence
		m = re.match(r"^(group|panel|comp|compartment|box|subfigure|node|edge|edit|req|exc|note|color|colour|categories|key)\b\s*:?\s*(.*)$", line, re.I)
		try:
			if not m:
				k, _, v = line.partition(":")
				k, v = k.strip().lower().replace(" ", "_"), v.strip()
				if k == "title":
					sp["canvas"]["title"] = v
					if src:
						sp["canvas"]["src"] = src
				elif k in ("width_mm", "min_font_pt", "dpi"):
					sp["canvas"][k] = float(re.sub(r"[^\d.]", "", v) or 0) or None
				elif k == "layout" and v.lower() in ("row", "col"):
					sp["canvas"]["layout"] = v.lower()
				elif k in ("edit_request", "summary", "caption", "status"):
					notes[k] = v
				elif k in ("status_reason", "status_reasons"):
					notes.setdefault("status_reasons", []).append(v)
				else:
					warn.append("line %d not understood (skipped): %s" % (no, raw.strip()[:70]))
				continue
			kw, rest = m.group(1).lower(), m.group(2).strip()
			if kw == "edge":  # the inhibition arrow contains the field separator
				rest = re.sub(r"^(\S+)\s*(?:-\|\||-\|)\s*", lambda g: g.group(1) + " ⊣ " + ("| " if g.group(0).rstrip().endswith("||") else ""), rest, 1)
			if kw in ("node", "group", "panel", "comp", "compartment", "box", "subfigure", "edit"):  # 'cy fill=#fff' written without the separator
				rest = re.sub(r"(?<=[^|\s])\s+(?=(?:alias|aliases|data|col|row|cols|fill|stroke|label|shape|layout|in|parent)=)", " | ", rest)
			f = [x.strip() for x in rest.split("|")]
			if kw in ("group", "panel", "comp", "compartment", "box", "subfigure"):
				head, _, title = f[0].partition(":")
				hm = re.match(r"^(\S+)(?:\s+in\s+(\S+))?$", head.strip())
				p = {"id": hm.group(1) if hm else re.sub(r"\W+", "-", head.strip()), "title": title.strip() or head.strip()}
				if hm and hm.group(2):
					p["parent"] = hm.group(2)
				for x in f[1:]:
					k, eq, v = x.partition("=")
					k, v = k.strip().lower(), v.strip()
					if eq and k in ("in", "parent", "inside"):
						p["parent"] = v
					elif eq and k == "cols":
						p["cols"] = int(float(v))
					elif eq and k in ("layout", "fill", "stroke"):
						p[k] = v.lower() if k == "layout" else v
					elif x.lower() in ("row", "col", "grid"):
						p["layout"] = x.lower()
					elif x.lower() in ("membrane", "band", "boundary"):
						p["fill"] = "#F2D7B6"
					elif k in ("dashed", "dash", "planned"):
						p["dash"] = v or (k if k == "planned" else True)
				if src:
					p["src"] = src
				pid[p["id"]] = p
				sp["panels"].append(p)
			elif kw == "node":
				head, c0, lab = f[0].partition(":")
				if not c0 and len(f) > 2 and f[1] not in pid and f[1].lower() not in KINDS and "=" not in f[1]:
					lab = f.pop(1)  # 'node ins | Insulin | protein | ex'
				n = {"id": re.sub(r"[^\w.\-]+", "-", head.strip()), "label": (lab.strip() or head.strip()).replace("\\n", "\n")}
				for x in f[1:]:
					k, eq, v = x.partition("=")
					k, v, lx = k.strip().lower(), v.strip(), x.lower().replace(" ", "_")
					if eq and k in ("alias", "aliases"):
						n["aliases"] = [y.strip() for y in v.split(",") if y.strip()]
					elif k in ("dashed", "dash", "planned"):
						n["dash"] = v or (k if k == "planned" else True)
					elif eq and k in ("col", "row", "w", "h"):
						n[k] = int(float(v))
					elif eq:
						n[{"group": "comp", "in": "comp", "panel": "comp", "type": "kind", "color": "fill", "colour": "fill"}.get(k, k)] = v
					elif x in pid:
						n["comp"] = x
					elif lx in KINDS:
						n["kind"] = lx
					elif lx in SHAPES:
						n["shape"] = lx
					elif lx == "bold":
						n["bold"] = True
					elif x and "comp" not in n and gid(x, pid):
						n["comp"] = gid(x, pid)
					elif x and "kind" not in n and syn(x, KSYN):
						n["kind"] = syn(x, KSYN)
					elif x and "comp" not in n:
						n["comp"] = x  # unknown group: reported by the builder
				if src:
					n["src"] = src
				sp["nodes"].append(n)
			elif kw == "edge":
				h0 = re.sub(r"^[\w.\-]+\s*:\s*(?=\S+\s*(?:-o|--|<->|->|=>|→|⊣|>))", "", f[0])  # 'edge e1: A -> B'
				h0, c0, t0 = h0.partition(":")  # 'edge A -> B: inhibit'
				if c0 and t0.strip():
					f.insert(1, t0.strip())
				hm = re.match(r"^(\S+?)\s*(-o|--|<->|->|=>|→|⊣|>)\s*(\S+)$", h0.strip())
				if not hm:
					warn.append("line %d: edge needs 'A -> B | type | label' (skipped): %s" % (no, raw.strip()[:70]))
					continue
				e = {"from": hm.group(1), "to": hm.group(3)}
				given = {"-|": "inhibit", "⊣": "inhibit", "-o": "bind", "--": "line"}.get(hm.group(2))
				if hm.group(2) == "<->":
					e["both"] = True
				typed, soft = False, None
				for x in f[1:]:
					lx = x.lower().strip()
					k, eq, v = x.partition("=")
					if lx in EVS or (len(lx.split()) <= 2 and syn(lx, ESYN) and lx not in TYPES):
						e["evidence"] = lx if lx in EVS else syn(lx, ESYN)
					elif not typed and (lx in TYPES or (len(lx.split()) <= 2 and syn(lx, TSYN))):
						t2 = lx if lx in TYPES else syn(lx, TSYN)
						if not (given == "inhibit" and t2 != "inhibit"):
							e["type"] = t2
						typed = True
						if lx not in TYPES:
							soft = x  # the author's own word stays as the label unless a label follows
					elif eq and k.strip().lower() in ("label", "type", "evidence", "id", "legend", "elbow"):
						e[k.strip().lower()] = v.strip()
					elif lx in ("thick", "bold"):
						e["width"] = 3
					elif x and "label" not in e:
						e["label"] = x
				if soft and "label" not in e:
					e["label"] = soft
				if "type" not in e:
					e["type"] = given or "?"
				if e["type"] == "indirect" and "evidence" not in e:
					e["type"], e["evidence"] = given or "activate", "indirect"
				e["id"] = e.get("id") or "e-%s-%s" % (e["from"], e["to"])
				if src:
					e["src"] = src
				sp["edges"].append(e)
			elif kw == "note":
				sp["texts"].append(dict({"id": "t-note%d" % (len(sp["texts"]) + 1), "text": rest}, **({"src": src} if src else {})))
			elif kw == "key":
				hx = re.search(r"#[0-9A-Fa-f]{6}", rest)
				lab = " ".join(x for x in (re.sub(r"#[0-9A-Fa-f]{6}", "", y).strip(" =:") for y in f) if x)
				if hx and lab:
					sp["legend"]["items"].append({"fill": hx.group(0), "label": lab})
				else:
					warn.append("line %d: key needs '#hex | meaning' (skipped): %s" % (no, raw.strip()[:70]))
			elif kw in ("color", "colour", "categories"):
				f = f + [""] * 4
				cat = {"csv": find_csv(f[0]), "key": f[1], "column": f[2]}
				cols = dict((a.strip(), b) for x in f[3:] for a, b in re.findall(r"([^,;=]+?)\s*=\s*(#[0-9A-Fa-f]{6})", x))
				title = next((x for x in f[3:] if x and "#" not in x and "=" not in x), "")
				show = next((x.split("=", 1)[1].strip() for x in f[3:] if x.lower().startswith("show=")), "")
				cat["title"] = title or "%s (%s)" % (f[2], os.path.basename(f[0]))
				if cols:
					cat["colors"] = cols
				if show:
					cat["show"], cat["fmt"] = show, "{}"
				cat["src"] = src or os.path.basename(f[0])
				sp["canvas"]["categories"] = cat
			elif kw == "req":
				f = f + [""] * 4
				res = f[1].lower() if f[1].lower() in ("pass", "partial", "fail") else "partial"
				pm = re.search(r"\s*\(L[^)]*\)\s*$", f[2])
				if pm:
					f[2], f[3] = f[2][:pm.start()], (f[3] + " " + pm.group(0).strip()).strip()
				ids = [x for x in re.split(r"[,\s]+", f[2]) if re.match(r"^[\w.\-]+$", x)] if f[1].lower() in ("pass", "partial", "fail") else []
				notes["compliance_checks"].append({"requirement": f[0], "result": res, "element_ids": ids,
												   "evidence": " | ".join(x for x in (f[3:] if ids or f[1].lower() in ("pass", "partial", "fail") else f[1:]) if x)})
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

def gid(x, pid):
	"""a group named by its title (or a unique part of it) instead of its id"""
	k = re.sub(r"[^a-z0-9⺀-￿]", "", str(x).lower())
	if not k:
		return None
	t = {i: re.sub(r"[^a-z0-9⺀-￿]", "", str(p.get("title", "")).lower()) for i, p in pid.items()}
	hit = [i for i in pid if i.lower() == str(x).lower()] or [i for i, v in t.items() if v == k] or [i for i, v in t.items() if len(k) >= 3 and k in v]
	return hit[0] if len(hit) == 1 else None

def normalise(sp, warn, notes):
	"""make any spec safe for the builder: ids unique, groups/kinds/types known, data colours only when the table really has the columns"""
	for k in ("panels", "nodes", "edges", "texts"):
		sp[k] = [o for o in (sp.get(k) or []) if isinstance(o, dict)]
	cv = sp["canvas"]
	pid = {p.get("id"): p for p in sp["panels"]}
	for p in sp["panels"]:
		par = p.pop("in", None) or p.get("parent")
		if par and par not in pid:
			g = gid(par, pid)
			warn.append("group %s: parent %r is not a group id%s" % (p.get("id"), par, " (taken as %s)" % g if g else " (drawn at top level)"))
			par = g
		if par and par != p.get("id"):
			p["parent"] = par
		else:
			p.pop("parent", None)
	seen = set(pid)
	for n in sp["nodes"]:
		if n.get("id") in seen:
			old, k = n["id"], 2
			while "%s-%d" % (old, k) in seen:
				k += 1
			n["id"] = "%s-%d" % (old, k)
			warn.append("node id %r is used twice: the second one was renamed %s (edges keep pointing to the first)" % (old, n["id"]))
		seen.add(n.get("id"))
		c = n.get("comp")
		if c and c not in pid:
			g = gid(c, pid)
			if g:
				n["comp"] = g
			else:
				warn.append("node %s: group %r is not defined (add a `group %s: <title>` line); drawn outside the groups" % (n.get("id"), c, c))
				n.pop("comp")
		kd = str(n.get("kind", "")).lower().replace(" ", "_")
		if kd and kd not in KINDS:
			kd = syn(kd, KSYN) or "concept"
		n["kind"] = kd or "concept"
		if n.get("shape") and n["shape"] not in SHAPES:
			n.pop("shape")
	nid = {n["id"]: n for n in sp["nodes"] if n.get("id")}
	lab = {}
	for n in sp["nodes"]:
		lab.setdefault(re.sub(r"\s+", "", str(n.get("label", "")).lower()), []).append(n["id"])
	keep, dflt = [], []
	for e in sp["edges"]:
		for k in ("from", "to"):
			v = e.get(k)
			if isinstance(v, str) and v not in nid and v not in pid:
				h = lab.get(re.sub(r"\s+", "", v.lower()), []) or [i for i in list(nid) + list(pid) if i and i.lower() == v.lower()]
				if len(h) == 1:
					e[k] = h[0]
		if not (isinstance(e.get("from"), str) and isinstance(e.get("to"), str) and (e["from"] in nid or e["from"] in pid) and (e["to"] in nid or e["to"] in pid)):
			warn.append("edge %s -> %s: unknown node (define both ends with node lines, ids are case-sensitive); edge left out" % (e.get("from"), e.get("to")))
			continue
		t = str(e.get("type", "?")).lower()
		if t not in TYPES:
			t2 = syn(t, TSYN)
			if not t2:
				ends = [nid.get(e["from"], {}), nid.get(e["to"], {})]
				t2 = "step" if all(x.get("kind") in ("step", "process", "sample", "material", "instrument", "data", "reagent", "condition") or re.match(r"\s*\d+[\s.)]", str(x.get("label", ""))) for x in ends) else "activate"
				dflt.append("%s (%s)" % (e.get("id"), t2))
			t = t2
		e["type"] = t
		ev = str(e.get("evidence", "direct")).lower()
		e["evidence"] = ev if ev in EVS else (syn(ev, ESYN) or "direct")
		if e["evidence"] == "direct":
			e.pop("evidence")
		elif e.get("label") and re.match(r"^[\s,;()]*((proposed|untested|not tested|hypothe\w+|putative|possibl[ey]|indirect|speculative|推测|未验证|未检验|间接|可能)[\s,;()]*)+$", str(e["label"]), re.I):
			e.pop("label")  # the line style and its legend entry already say this; a second copy only crowds the figure
		keep.append(e)
	sp["edges"] = keep
	if dflt:
		warn.append("edge type not given, guessed for: %s. Write the type (step/flow/activate/inhibit/bind/...) if the guess is wrong" % ", ".join(dflt[:8]))
	ids, k = set(), 0
	for e in sp["edges"]:
		if e.get("id") in ids or not e.get("id"):
			k += 1
			e["id"] = "%s-%d" % (e.get("id") or "e", k + 1)
		ids.add(e["id"])
	cat = cv.get("categories")
	if isinstance(cat, dict):
		try:
			cat["csv"] = find_csv(cat.get("csv", ""))
			rows = list(csv.DictReader(open(cat["csv"], encoding="utf-8-sig")))
			hdr = list(rows[0].keys()) if rows else []
			low = lambda s: re.sub(r"[^a-z0-9⺀-￿]", "", str(s).lower())  # noqa: E731
			for k in ("key", "column", "show"):
				if cat.get(k) and cat[k] not in hdr:
					h = [c for c in hdr if low(c) == low(cat[k])] or [c for c in hdr if low(cat[k]) and low(cat[k]) in low(c)]
					if h:
						cat[k] = h[0]
					elif k == "show":
						cat.pop("show"), cat.pop("fmt", None)
					else:
						raise KeyError("column %r not in %s (columns: %s)" % (cat[k], os.path.basename(cat["csv"]), ", ".join(hdr)))
			cats = {r.get(cat["column"]) for r in rows}
			if isinstance(cat.get("colors"), dict):
				fix = {}
				for c, v in cat["colors"].items():
					h = [x for x in cats if x and low(x) == low(c)] or [x for x in cats if x and low(c) and low(c) in low(x)]
					if h:
						fix[h[0]] = v
					else:
						warn.append("color line: %r is not a value of column %s (values: %s)" % (c, cat["column"], ", ".join(sorted(x for x in cats if x))[:160]))
				cat["colors"] = fix
			keys = {str(r.get(cat["key"], "")).strip(): 1 for r in rows}
			lk = {low(k): k for k in keys}
			for n in sp["nodes"]:
				if "data" not in n and "fill" not in n:
					for c in [str(n.get("label", "")).split("\n")[0]] + list(n.get("aliases") or []) + [str(n.get("id"))]:
						if low(c) in lk and low(c):
							n["data"] = lk[low(c)]
							break
				elif "data" in n and n["data"] not in keys and low(n["data"]) in lk:
					n["data"] = lk[low(n["data"])]
			un = [n["id"] for n in sp["nodes"] if n.get("data") and n["data"] not in keys]
			for n in sp["nodes"]:
				if n.get("data") and n["data"] not in keys:
					n.pop("data")
			if un:
				warn.append("data key not in %s column %s for: %s (left uncoloured)" % (os.path.basename(cat["csv"]), cat["key"], ", ".join(un[:8])))
			if any(not n.get("data") and not n.get("fill") for n in sp["nodes"]) and isinstance(sp.get("legend"), dict):
				sp["legend"].setdefault("items", []).append({"fill": "#FFFFFF", "label": "not listed in %s" % os.path.basename(cat["csv"])})
			print("   data colours: %d node(s) coloured by %s from %s; %d node(s) without a row stay white" % (
				sum(1 for n in sp["nodes"] if n.get("data")), cat["column"], os.path.basename(cat["csv"]), sum(1 for n in sp["nodes"] if not n.get("data") and not n.get("fill"))))
		except Exception as ex:
			cv.pop("categories", None)
			for n in sp["nodes"]:
				n.pop("data", None)
			warn.append("color line not usable (%s): figure built without data colours; fix `color: file.csv | key column | category column` and rerun" % str(ex)[:200])
			notes["exceptions"].append({"category": "run_failure", "detail": "data colour mapping not applied: %s" % str(ex)[:200], "handling": "figure drawn without data colours"})
	elif cat is not None:
		cv.pop("categories", None)
	dz = [o.get("dash") for o in sp["panels"] + sp["nodes"] if o.get("dash")]
	if dz and not any("dashed outline" in str(t.get("text", "")).lower() for t in sp["texts"]):
		why = next((d for d in dz if isinstance(d, str) and d.lower() not in ("true", "planned")), None) or "planned / not established in the source (not an implemented or tested part)"
		sp["texts"].append({"id": "t-dashed", "text": "Dashed outline: %s." % why.rstrip("."), "src": next((o.get("src") for o in sp["panels"] + sp["nodes"] if o.get("dash") and o.get("src")), "spec")})
	lg = sp.get("legend") if isinstance(sp.get("legend"), dict) else {"title": "Legend"}
	lg["items"] = [it for it in (lg.get("items") or []) if isinstance(it, dict) and it.get("fill") and it.get("label")]
	if not lg["items"]:
		lg.pop("items")
	sp["legend"] = lg
	return sp

def prepare(path, warn):
	text = Path(path).read_text(encoding="utf-8-sig", errors="replace")
	edits = []
	if text.lstrip().startswith("{"):
		sp = jload(path)
		if not isinstance(sp, dict):
			warn.append("%s starts with '{' but is not valid JSON: fix it or use the line format" % path)
			sp = {}
		notes = {k: sp.pop(k) for k in ("compliance_checks", "exceptions", "edit_request", "summary", "caption", "status", "status_reasons") if k in sp}
		notes.setdefault("compliance_checks", sp.pop("checks", []))
		notes.setdefault("exceptions", [])
		for e in sp.pop("edits", []) or []:
			if isinstance(e, dict) and e.get("id"):
				edits.append((e["id"], {k: v for k, v in e.items() if k != "id"}))
	else:
		sp, notes, edits = parse(text, warn)
	cv = sp["canvas"] if isinstance(sp.get("canvas"), dict) else {}
	sp["canvas"] = cv
	for k in ("w", "h", "grid"):  # geometry is always computed
		cv.pop(k, None)
	wo = workorder(inputs())
	w = [jload(wo, {}) if wo else {}, jload(CJ, {})]
	for k, pat, dv in (("width_mm", r"width.?mm|宽度", 180), ("min_font_pt", r"min.?font|最小字号", 6), ("dpi", r"dpi|resolution|分辨率", 300)):
		if not cv.get(k):
			v = walk(w, pat)
			try:
				cv[k] = float(re.sub(r"[^\d.]", "", str(v))) if v is not None else dv
				if v is None:
					notes.setdefault("_defaults", []).append("%s=%s (not in the work order; default)" % (k, dv))
			except ValueError:
				cv[k] = dv
	cv["dpi"] = min(600.0, max(72.0, float(cv.get("dpi") or 300)))
	if not cv.get("title"):
		cv["title"] = str(walk(w, r"^title$|figure.?title") or "")[:120] or "Schematic"
	sp = normalise(sp, warn, notes)
	if not notes.get("edit_request"):
		er = walk(w, r"edit.?request|revision.?request|modif|修改请求|编辑请求")
		if er:
			notes["edit_request"] = str(er)
	reqs = next((v for d in w if isinstance(d, dict) for k, v in d.items() if re.search(r"requirement|must|constraint|criteria|checklist|acceptance|should|要求|必须|验收", k, re.I) and isinstance(v, list) and v), [])
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
	ns = [l.split("no src for ", 1)[1].strip() for l in ls if "no src for " in l]
	if len(ns) > 2:  # one line instead of one per element
		ls = [l for l in ls if "no src for " not in l] + ["WARN: no src for %d element(s): %s%s. Add the source line at the end of each spec line (@12 or @12-15)" % (len(ns), ", ".join(ns[:10]), " ..." if len(ns) > 10 else "")]
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

def extra_formats(stems, dpi, notes):
	"""TIFF / JPEG / EPS asked for by the work order: converted from the real PNG / PDF when a tool is here, else recorded as missing"""
	wo = workorder(inputs())
	want = {str(x).lower().strip(". ") for x in strings([jload(wo, {}) if wo else {}, jload(CJ, {})]) if re.match(r"^\.?(tiff?|eps|jpe?g)$", str(x).strip(), re.I)}
	txt = json.dumps([jload(wo, {}) if wo else {}], ensure_ascii=False).lower()
	want |= {f for f in ("tiff", "eps") if re.search(r"\b%s\b" % f, txt)}
	want = {"tiff" if w in ("tif", "tiff") else "jpg" if w in ("jpg", "jpeg") else w for w in want}
	im = shutil.which("magick") or shutil.which("convert")
	for f in sorted(want):
		made = []
		for st in stems:
			png, pdf, dst = OUT / (st + ".png"), OUT / (st + ".pdf"), OUT / ("%s.%s" % (st, f))
			tries = []
			if f in ("tiff", "jpg") and png.exists():
				tries.append([PY, "-c", "from PIL import Image;import sys;im=Image.open(sys.argv[1]).convert('RGB');d=float(sys.argv[3]);im.save(sys.argv[2],dpi=(d,d),**({'compression':'tiff_lzw'} if sys.argv[2].endswith('tiff') else {}))", str(png), str(dst), str(dpi)])
				if im:
					tries.append([im, str(png), "-density", str(int(dpi)), "-units", "PixelsPerInch"] + (["-compress", "lzw"] if f == "tiff" else ["-background", "white", "-flatten"]) + [str(dst)])
			if f == "eps" and pdf.exists():
				if shutil.which("pdftops"):
					tries.append(["pdftops", "-eps", str(pdf), str(dst)])
				if shutil.which("gs"):
					tries.append(["gs", "-q", "-dNOPAUSE", "-dBATCH", "-sDEVICE=eps2write", "-sOutputFile=" + str(dst), str(pdf)])
			for t in tries:
				rc, o = sh(t, 60)
				if rc == 0 and dst.exists() and dst.stat().st_size > 200:
					made.append(dst.name)
					break
				if dst.exists():
					dst.unlink()
		if made:
			print("   extra format %s (asked by the work order): %s" % (f, ", ".join(made)))
			notes.setdefault("_defaults", []).append("%s written from the rendered %s: %s" % (f.upper(), "PDF" if f == "eps" else "PNG (%s dpi)" % int(dpi), ", ".join(made)))
		if len(made) < 1:
			print("   WARN: the work order asks for %s but no converter is available here: recorded as a missing export format (status partial)" % f.upper())
			notes["exceptions"].append({"category": "run_failure", "detail": "missing export format: %s (asked by the work order; no converter available in this environment)" % f.upper(),
										"handling": "SVG, PDF and PNG delivered; convert figure.png / figure.pdf to %s with ImageMagick or Inkscape" % f.upper()})

def apply_edits(sp, edits, warn, cm):
	nm = lambda s: re.sub(r"[^a-z0-9⺀-￿]", "", str(s).lower())  # noqa: E731
	done = []
	cat = sp["canvas"].get("categories") if isinstance(sp["canvas"].get("categories"), dict) else None
	cats = {c.get("label"): c.get("color") for c in ((cm.get("data_encoding") or {}).get("categories") or [])}
	if cat and cats:
		cat["colors"] = dict(cats, **(cat.get("colors") or {}))  # every category keeps its colour unless an edit names it
	for tid, ops in edits:
		ops = {{"text": "label", "name": "label", "rename": "label", "color": "fill", "colour": "fill", "border": "stroke", "delete": "remove", "dashed": "dash"}.get(k, k): v for k, v in ops.items()}
		objs = [o for k in ("nodes", "edges", "panels", "texts") for o in sp.get(k, [])]
		t = re.sub(r"^(class|category|group|node|edge)\s*[:=]\s*", "", tid, flags=re.I)
		chit = [c for c in cats if nm(c) == nm(t)] or [c for c in cats if nm(t) and (nm(t) in nm(c) or nm(c) in nm(t))]
		if cat and len(chit) == 1 and "fill" in ops and not [o for o in objs if o.get("id") == tid]:
			old = cat["colors"].get(chit[0])
			cat["colors"][chit[0]] = ops["fill"]
			done.append({"id": "legend-cat-" + re.sub(r"[^a-z0-9]+", "", chit[0].lower()), "category": chit[0], "set": {"fill": ops["fill"]}})
			for c2, v2 in list(cat["colors"].items()):  # one colour per category must survive the edit
				if c2 != chit[0] and str(v2).upper() == str(ops["fill"]).upper():
					used = {str(v).upper() for v in cat["colors"].values()}
					free = ([old] if old and str(old).upper() not in used else []) + [x for x in PALETTE if x not in used]
					if free:
						cat["colors"][c2] = free[0]
						done.append({"id": "legend-cat-" + re.sub(r"[^a-z0-9]+", "", c2.lower()), "category": c2, "set": {"fill": free[0]}, "why": "it had the colour now given to %s" % chit[0]})
						warn.append("edit: category %r already used %s, so it was moved to %s (one colour per category; legend and nodes follow)" % (c2, ops["fill"], free[0]))
			continue
		if t.lower() in ("title", "figure-title"):
			sp["canvas"]["title"] = ops.get("label", sp["canvas"].get("title"))
			done.append({"id": "figure-title", "set": ops})
			continue
		hit = [o for o in objs if o.get("id") == t] or [o for o in objs if nm(o.get("id")) == nm(t)] or \
			  [o for o in objs if nm(str(o.get("label") or o.get("title") or o.get("text")).split("\n")[0]) == nm(t)]
		if not hit:
			warn.append("edit: no element with id or label %r (ids: %s ...)" % (tid, ", ".join(str(o.get("id")) for o in objs[:14])))
			continue
		for o in hit:
			for k, v in ops.items():
				if k == "label" and "label" not in o and ("title" in o or "text" in o):
					k = "title" if "title" in o else "text"
				if k == "remove":
					for key in ("nodes", "edges", "texts"):
						sp[key] = [x for x in sp.get(key, []) if x is not o and x.get("from") != o.get("id") and x.get("to") != o.get("id")]
					continue
				if k == "fill" and "data" in o:
					o.pop("data")
					warn.append("edit: %s no longer takes its colour from the data table (fill set by hand)" % o.get("id"))
				if k == "label" and o.get("label") and "aliases" not in o and "from" not in o:
					o["aliases"] = [str(o["label"]).split("\n")[0]]  # the old name stays searchable in the content map
				o[k] = str(v).replace("\\n", "\n") if isinstance(v, str) else v
			done.append({"id": o.get("id"), "set": ops})
	return done

def source_map(cm):
	"""figure_source_map.md: one row per drawn element with its source pointer and the verbatim source line(s)"""
	try:
		lines = (WORK / "src.txt").read_text(encoding="utf-8", errors="replace").replace("\f", "").split("\n")
	except Exception:
		lines = []
	def quote(s):
		m = re.search(r"src\.txt\s*[:#]\s*L?(\d+)(?:\s*[-–~]\s*L?(\d+))?", str(s))
		if not m or not lines:
			return ""
		a = int(m.group(1))
		b = min(int(m.group(2) or a), a + 5)
		return " ".join(" ".join(lines[a - 1:b]).split())[:220] if 1 <= a <= len(lines) else "(line outside the source text)"
	esc = lambda s: str(s if s is not None else "").replace("|", "/").replace("\n", " ")  # noqa: E731
	out = ["# Source map: every element on the figure -> where it comes from", "", "| element id | on the figure | kind / relation | source | source text (verbatim) |", "|---|---|---|---|---|"]
	for c in cm.get("compartments") or []:
		out.append("| %s | %s | group%s | %s | %s |" % (esc(c.get("id")), esc(c.get("title")), " in " + esc(c.get("parent")) if c.get("parent") else "", esc(c.get("src")), esc(quote(c.get("src")))))
	for e in cm.get("entities") or []:
		dv = " = %s" % e["data_value"] if e.get("data_value") is not None else ""
		out.append("| %s | %s | %s%s%s | %s | %s |" % (esc(e.get("id")), esc(e.get("label")), esc(e.get("kind")), " in " + esc(e.get("compartment")) if e.get("compartment") else "", esc(dv), esc(e.get("src")), esc(quote(e.get("src")))))
	for r in cm.get("relations") or []:
		if r.get("type") != "contains":
			out.append("| %s | %s -> %s%s | %s%s | %s | %s |" % (esc(r.get("id")), esc(r.get("from")), esc(r.get("to")), " (%s)" % esc(r["label"]) if r.get("label") else "", esc(r.get("type")),
															", %s evidence" % r["evidence"] if r.get("evidence") not in (None, "", "direct") else "", esc(r.get("src")), esc(quote(r.get("src")))))
	enc = cm.get("data_encoding") or {}
	if enc.get("categories"):
		out += ["", "## Data mapping (%s, column %s)" % (os.path.basename(str(enc.get("file"))), enc.get("category_column")), "", "| category | colour | rows in table | nodes |", "|---|---|---|---|"]
		out += ["| %s | %s | %s | %s |" % (esc(c.get("label")), c.get("color"), c.get("n_rows"), ", ".join(n.get("node") for n in enc.get("nodes") or [] if n.get("category") == c.get("label"))) for c in enc["categories"]]
	(OUT / "figure_source_map.md").write_text("\n".join(out) + "\n", encoding="utf-8")

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
	for old in ("figure.svg", "figure.png", "figure.pdf", "figure_pixel_check.json", "figure_content_map.json", "figure_v2.svg", "figure_v2.png", "figure_v2.pdf", "figure_spec_v2.json",
				"edit_diff.json", "figure_v2_pixel_check.json", "figure_v2_content_map.json", "export_log.jsonl", "figure_source_map.md",
				"figure.tiff", "figure.eps", "figure.jpg", "figure_v2.tiff", "figure_v2.eps", "figure_v2.jpg"):
		if (OUT / old).exists():
			(OUT / old).unlink()
	json.dump(sp, open(spec, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
	print("spec: %d groups, %d nodes, %d edges, %d requirement checks, %d exceptions, %d edit(s); width %s mm, min font %s pt, %s dpi" % (
		len(sp["panels"]), len(sp["nodes"]), len(sp["edges"]), len(notes["compliance_checks"]), len(notes["exceptions"]), len(edits),
		cv.get("width_mm"), cv.get("min_font_pt"), dpi))
	for w in warn:
		print("   WARN: " + w)
	spec_warn = list(warn)
	sf = os.path.join(HERE, "svgfig.py")
	rc, o = stage("build figure.svg", [PY, sf, "build", spec, svg], 150)
	if not os.path.exists(svg) and cv.get("categories"):
		cv.pop("categories")
		json.dump(sp, open(spec, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
		notes["exceptions"].append({"category": "run_failure", "detail": "build failed with the data colours; rebuilt without them", "handling": "fix the color line (file / columns) and rerun"})
		rc, o = stage("build without data colours", [PY, sf, "build", spec, svg], 150)
	show(o, 14, r"^(WARN|FAIL)")
	print("   " + next((l for l in o.splitlines() if l.startswith("wrote ")), o.strip()[-300:])[:300])
	cm = jload(OUT / "figure_content_map.json", {}) or {}
	lg = cm.get("legend") or []
	if lg:
		print("   legend drawn automatically (%d items): %s" % (len(lg), "; ".join(str(x.get("label") or x.get("head")) for x in lg)[:330]))
	npath = str(WORK / "notes.json")
	def assemble(tag):
		n2 = {k: v for k, v in notes.items() if not k.startswith("_") and v not in (None, "", [])}
		rn = list(notes.get("_defaults") or []) + ["spec: " + w for w in spec_warn[:8]]
		if rn:
			n2["run_notes"] = rn
		json.dump(n2, open(npath, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
		rc_, o_ = stage("result.json (%s)" % tag, [PY, os.path.join(HERE, "export_check.py"), "assemble", npath], 120)
		return o_
	if not os.path.exists(svg):
		notes["exceptions"].append({"category": "run_failure", "detail": "figure build failed: %s" % o.strip()[-200:], "handling": "no figure in this run"})
		show(assemble("no figure"), 8)
		print("FAIL: no figure.svg. Fix the spec lines named above and rerun build.")
		return 1
	if not notes["compliance_checks"]:
		notes["compliance_checks"].append({"requirement": "task: %s" % str(walk([jload(CJ, {})], r"^task$|instruction|description|任务") or cv.get("title"))[:240], "result": "pass", "element_ids": [],
										   "evidence": "figure built with %d entities and %d relations; the work order has no itemised requirement list and the spec has no req lines, so no item-by-item check applies" % (len(sp["nodes"]), len(sp["edges"]))})
	try:
		source_map(cm)
	except Exception as ex:
		print("   NOTE: figure_source_map.md not written (%s)" % ex)
	export(svg, dpi, 150)
	try:
		extra_formats(["figure"], dpi, notes)
	except Exception as ex:
		print("   NOTE: extra export formats skipped (%s)" % ex)
	o1 = assemble("first complete version")
	demo = not edits
	if demo and notes.get("edit_request"):
		demo = False
		print("   WARN: the work order has an edit request but the spec has no 'edit' line: add e.g. `edit <id or label> | label=New name` and rerun build")
		notes["exceptions"].append({"category": "run_failure", "detail": "edit request not applied in this run (no edit line in the spec): %s" % str(notes["edit_request"])[:200], "handling": "figure.svg is the unedited version"})
		o1 = assemble("edit request still open")
	elif demo and sp["nodes"]:
		n0 = sp["nodes"][0]
		edits = [(n0.get("id"), {"stroke": "#D55E00"})]
		notes["edit_request"] = "demonstration edit (not part of the official figure; figure.svg stays the deliverable): orange border on node %s to show an id-stable source-level edit" % n0.get("id")
	if edits and time.time() - T0 < 420:
		w2 = []
		sp2 = copy.deepcopy(sp)
		done = apply_edits(sp2, edits, w2, cm)
		for w in w2:
			print("   WARN: " + w)
		if done:
			spec2, svg2 = str(OUT / "figure_spec_v2.json"), str(OUT / "figure_v2.svg")
			json.dump(sp2, open(spec2, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
			rc, o = stage("build figure_v2.svg (%d edit(s)%s)" % (len(done), ", demonstration" if demo else ""), [PY, sf, "build", spec2, svg2], 120)
			if os.path.exists(svg2):
				rc, d = sh([PY, sf, "diff", svg, svg2], 60)
				ch = []
				if rc == 0:
					(OUT / "edit_diff.json").write_text(d, encoding="utf-8")
					dj = jload(OUT / "edit_diff.json", {}) or {}
					ch = dj.get("changed_ids") or sorted({c.get("id") for c in dj.get("changes", [])})
					print("   diff: %s ids kept, %s unchanged; content changes on: %s; %s layout-only change(s) from the automatic re-flow" % (
						dj.get("kept_ids"), dj.get("unchanged_ids"), ", ".join(map(str, ch[:12])) or "-", dj.get("layout_only_changes")))
				cm2 = OUT / "figure_v2_content_map.json"
				if cm2.exists():
					cm2.unlink()  # the v1 content map + edit_diff.json describe v2; one map keeps the record unambiguous
				export(svg2, dpi, max(40, min(150, 600 - (time.time() - T0))))
				try:
					if any(p.suffix.lower() in (".tiff", ".eps", ".jpg") for p in OUT.glob("figure.*")):
						extra_formats(["figure_v2"], dpi, {"exceptions": [], "_defaults": []})
				except Exception:
					pass
				notes["exceptions"] += [{"category": "edit_side_effect" if "moved to" in w or "no longer" in w else "edit_not_applied", "detail": w, "handling": "recorded in the change log; see edit_diff.json"} for w in w2]
				if not demo:
					notes["compliance_checks"].append({"requirement": "edit request: %s" % str(notes.get("edit_request") or "; ".join(t for t, _ in edits))[:300],
													   "result": "pass" if len(done) >= len(edits) and not [x for x in w2 if "no element" in x] else "partial", "element_ids": [str(c) for c in ch[:12]],
													   "evidence": "%d of %d edit line(s) applied to the spec and rebuilt as figure_v2.svg/.png/.pdf; element-level diff in edit_diff.json%s" % (
														   min(len(done), len(edits)), len(edits), "; side effects: " + "; ".join(w2)[:300] if w2 else "")})
				o1 = assemble("with the edited version")
		elif not demo:
			notes["exceptions"].append({"category": "run_failure", "detail": "edit lines matched no element: %s" % "; ".join(w2)[:300], "handling": "edit not applied"})
			o1 = assemble("edit not applied")
	show(o1, 10, r"^(WARN|FAIL|source trace)")
	print("   " + (o1.strip().splitlines() or ["?"])[-1])
	res = jload(OUT / "result.json", {}) or {}
	print("DONE in %s -> %s: %s" % (el(), OUT, ", ".join(sorted(p.name for p in OUT.iterdir() if p.is_file()))))
	print("status=%s; reasons=%s" % (res.get("status"), json.dumps(res.get("status_reasons"), ensure_ascii=False)[:300]))
	print("All deliverables are written; result.json is final for this version. Optional: fix a WARN that names a wrong fact (unknown node, skipped line, missing src, cited line, guessed edge type) in the spec file and rerun build (at most twice).")
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
