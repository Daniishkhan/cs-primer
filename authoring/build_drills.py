"""Build the Practice mode's drills from the labs.

    python3 authoring/build_drills.py            # write drills and data
    python3 authoring/build_drills.py --verify   # also run each drill's check

A drill is one lab milestone turned into "write this one function":
  <course>/labs/code/labNN/drills/mN.py   solution.py with only milestone N's
                                          functions replaced by their starter
                                          stubs (everything else is given)
  <course>/labs/code/labNN/drills/lab.json  the lab's milestones with their
                                          task, checkpoint, hints, solution and
                                          explanation lifted from the lab page,
                                          plus the need-to-know card
                                          drills/mN.html when an author has
                                          written one (a plain HTML fragment)
  assets/js/drills-data.js                every drill, in artifact-track order

Generated files are committed. Re-run after editing a lab page, a lab's
starter.py or solution.py, or a card. --verify runs `check.py N` on each
drill file and insists that the stubbed milestone reports "not implemented
yet" and nothing else fails, which proves the stub sits on the right
milestone and the rest of the file is sound.
"""
import ast
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG_JS = ("global.window={};require(process.argv[1]);"
              "console.log(JSON.stringify({courses:window.CS_COURSES.map(c=>({id:c.id,num:c.num,title:c.title,dir:c.dir,"
              "labs:(c.labs||[]).map(l=>({id:l.id,file:l.file,title:l.title,related:l.related||[]}))})),"
              "artifacts:(window.CS_ARTIFACTS||[]).map(a=>({id:a.id,num:a.num,title:a.title,build:a.build||[]}))}))")
SKIP_FILES = {"starter.py", ".DS_Store"}
STUB = re.compile(r"milestone\s+(\d+)", re.I)


def slug(s):
    return re.sub(r"^-|-$", "", re.sub(r"[^a-z0-9]+", "-", s.lower()))


def catalog():
    out = subprocess.run(["node", "-e", CATALOG_JS, os.path.join(ROOT, "assets/js/catalog.js")],
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out)


# ── 1. Functions and the milestone each stub belongs to ─────────────────

def functions(src):
    """{qualified name: (milestone or None, node)} for every def in src."""
    tree = ast.parse(src)
    out = {}

    def walk(node, stack):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                walk(child, stack + [child.name])
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                qual = ".".join(stack + [child.name])
                ms = None
                for n in ast.walk(child):
                    if isinstance(n, ast.Raise) and n.exc is not None:
                        text = ast.get_source_segment(src, n.exc) or ""
                        m = STUB.search(text) if "NotImplementedError" in text else None
                        if m:
                            ms = int(m.group(1))
                            break
                out[qual] = (ms, child)
                walk(child, stack + [child.name])
    walk(tree, [])
    return out


def span(node):
    """(first line, last line) of a def, 1-based, decorators included."""
    first = min([d.lineno for d in node.decorator_list] + [node.lineno])
    return first, node.end_lineno


def drill_source(starter, solution, n, lab_label, title, write, total):
    """solution.py with milestone n's functions swapped for their stubs."""
    sfuncs, tfuncs = functions(starter), functions(solution)
    lines = solution.split("\n")
    slines = starter.split("\n")
    swaps = []
    for qual, (ms, snode) in sfuncs.items():
        if ms != n:
            continue
        if qual not in tfuncs:
            print(f"  warning: {qual} is stubbed in starter.py but missing from solution.py")
            continue
        a, b = span(tfuncs[qual][1])
        sa, sb = span(snode)
        swaps.append((a, b, slines[sa - 1:sb]))
    for a, b, body in sorted(swaps, reverse=True):
        lines[a - 1:b] = body
    head = [f"# Drill: {lab_label}, milestone {n} of {total}: {title}",
            "# Everything else in this file is already written. Fill in:",
            "#     " + ", ".join(write),
            f"# Check it with: python3 check.py {n}", ""]
    out = "\n".join(head + lines)
    ast.parse(out)                                   # must still be valid Python
    return out


# ── 2. The lab page: each milestone's task, hints, solution, explanation ──

TAG = re.compile(r"<(/?)div\b[^>]*>")


def balanced_div(html, start):
    """End index of the div that opens at start."""
    depth = 0
    for m in TAG.finditer(html, start):
        depth += -1 if m.group(1) else 1
        if depth == 0:
            return m.end()
    return len(html)


def page_milestones(html):
    """[{n, title, anchor, explain, task, checkpoint, hints, solution}] from a lab page."""
    out = []
    heads = list(re.finditer(r"<h2>(Milestone (\d+):?\s*(.*?))</h2>", html))
    for i, h in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else html.find("<h2>", h.end())
        section = html[h.end():end if end != -1 else len(html)]
        block_at = section.find('<div class="milestone">')
        if block_at == -1:
            print(f"  warning: no milestone block after '{h.group(1)}'")
            continue
        explain = section[:block_at].strip()
        block = section[block_at:balanced_div(section, block_at)]
        task_m = re.search(r'<p class="milestone-title">[^<]*</p>(.*?)<p class="checkpoint">', block, re.S)
        cp_m = re.search(r'<p class="checkpoint">(.*?)</p>', block, re.S)
        hints = []
        hm = re.search(r'<details class="deeper"><summary>Hints.*?</summary>\s*<ul>(.*?)</ul>\s*</details>', block, re.S)
        if hm:
            hints = [x.strip() for x in re.findall(r"<li>(.*?)</li>", hm.group(1), re.S)]
        sm = re.search(r'<details class="deeper"><summary>Solution.*?</summary>\s*(<pre>.*?</pre>)\s*</details>', block, re.S)
        out.append({
            "n": int(h.group(2)), "title": h.group(3).strip(), "anchor": slug(h.group(1)),
            "explain": explain, "task": (task_m.group(1).strip() if task_m else ""),
            "checkpoint": (cp_m.group(1).strip() if cp_m else ""), "hints": hints,
            "solution": (sm.group(1) if sm else ""),
        })
    return out


# ── 3. Build every lab ───────────────────────────────────────────────────

def lab_files(code_dir):
    names = []
    for d, dirs, files in os.walk(code_dir):
        dirs[:] = [x for x in dirs if x not in ("__pycache__", "drills")]
        for f in sorted(files):
            if f in SKIP_FILES or f.endswith((".pyc", ".ipynb")):
                continue
            names.append(os.path.relpath(os.path.join(d, f), code_dir).replace(os.sep, "/"))
    return sorted(names)


def build(verify):
    cat = catalog()
    data = {"labs": {}, "queue": []}
    seen = set()
    for a in cat["artifacts"]:
        for ref in a["build"]:
            if ":L" in ref and ref not in seen:
                seen.add(ref)
                data["queue"].append({"key": ref, "artifact": a["id"], "artifactNum": a["num"], "artifactTitle": a["title"]})
    for c in cat["courses"]:
        for lab in c["labs"]:
            ref = f"{c['id']}:{lab['id']}"
            if ref not in seen:
                seen.add(ref)
                data["queue"].append({"key": ref, "artifact": None})

    total_drills, failures = 0, []
    for c in cat["courses"]:
        for lab in c["labs"]:
            m = re.match(r"lab-(\d\d)-", lab["file"])
            if not m:
                continue
            page_path = os.path.join(ROOT, c["dir"], "labs", lab["file"])
            code_dir = os.path.join(ROOT, c["dir"], "labs", "code", "lab" + m.group(1))
            if not (os.path.exists(page_path) and os.path.exists(os.path.join(code_dir, "starter.py"))
                    and os.path.exists(os.path.join(code_dir, "solution.py"))):
                print(f"skip {c['id']} {lab['id']}: page or code missing")
                continue
            html = open(page_path, encoding="utf-8").read()
            starter = open(os.path.join(code_dir, "starter.py"), encoding="utf-8").read()
            solution = open(os.path.join(code_dir, "solution.py"), encoding="utf-8").read()
            stubs = functions(starter)
            by_ms = {}
            for qual, (ms, _) in stubs.items():
                if ms is not None:
                    by_ms.setdefault(ms, []).append(qual)
            page_ms = {p["n"]: p for p in page_milestones(html)}
            numbers = sorted(set(by_ms) | set(page_ms))
            if set(by_ms) != set(page_ms):
                print(f"  warning: {c['id']} {lab['id']}: stubs for milestones {sorted(by_ms)} but page sections {sorted(page_ms)}")
            ddir = os.path.join(code_dir, "drills")
            os.makedirs(ddir, exist_ok=True)
            lab_label = f"{c['num']} Lab {lab['id'][1:]}"
            provided_all = [q for q, (ms, _) in functions(solution).items()]
            milestones = []
            for n in numbers:
                p = page_ms.get(n, {"title": f"Milestone {n}", "anchor": "", "explain": "", "task": "", "checkpoint": "", "hints": [], "solution": ""})
                write = by_ms.get(n, [])
                if not write:
                    print(f"  warning: {c['id']} {lab['id']} milestone {n}: no stubbed function; no drill file")
                    continue
                src = drill_source(starter, solution, n, lab_label, p["title"], write, len(numbers))
                open(os.path.join(ddir, f"m{n}.py"), "w", encoding="utf-8").write(src)
                card_path = os.path.join(ddir, f"m{n}.html")
                card = open(card_path, encoding="utf-8").read().strip() if os.path.exists(card_path) else None
                milestones.append({
                    "n": n, "title": p["title"], "anchor": p["anchor"], "write": write,
                    "provided": [q for q in provided_all if q not in write and not q.startswith("_")],
                    "task": p["task"], "checkpoint": p["checkpoint"], "hints": p["hints"],
                    "solution": p["solution"], "explain": p["explain"], "card": card,
                })
                total_drills += 1
                if verify:
                    failures += verify_drill(code_dir, src, n, f"{c['id']}:{lab['id']}")
            files = lab_files(code_dir)
            rel_dir = os.path.relpath(code_dir, ROOT).replace(os.sep, "/") + "/"
            lab_json = {
                "course": c["id"], "courseTitle": c["title"], "num": c["num"], "lab": lab["id"], "title": lab["title"],
                "page": os.path.relpath(page_path, ROOT).replace(os.sep, "/"), "dir": rel_dir, "files": " ".join(files),
                "related": lab["related"], "milestones": milestones,
            }
            json.dump(lab_json, open(os.path.join(ddir, "lab.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
            data["labs"][f"{c['id']}:{lab['id']}"] = {
                "course": c["id"], "courseTitle": c["title"], "num": c["num"], "lab": lab["id"], "title": lab["title"],
                "page": lab_json["page"], "dir": rel_dir, "related": lab["related"], "cards": sum(1 for x in milestones if x["card"]),
                "milestones": [{"n": x["n"], "title": x["title"], "write": x["write"]} for x in milestones],
            }
    data["queue"] = [q for q in data["queue"] if q["key"] in data["labs"]]
    js = ("/* Generated by authoring/build_drills.py from the labs: do not edit. */\n"
          "window.CS_DRILLS = " + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n")
    open(os.path.join(ROOT, "assets/js/drills-data.js"), "w", encoding="utf-8").write(js)
    cards = sum(v["cards"] for v in data["labs"].values())
    print(f"{total_drills} drills in {len(data['labs'])} labs ({cards} with a need-to-know card); "
          f"{sum(1 for q in data['queue'] if q['artifact'])} labs on the artifact track")
    if verify:
        print(f"verify: {len(failures)} problem(s)")
        for f in failures:
            print("  " + f)
        if failures:
            sys.exit(1)


def verify_drill(code_dir, src, n, label):
    """A drill is sound when its checker runs, judges the stub as not done
    (ideally "not implemented yet"; some labs catch every exception by
    design and show ✘ instead) and nothing crashes. A stub that passes
    means the stub sits on the wrong milestone."""
    with tempfile.TemporaryDirectory() as tmp:
        for name in lab_files(code_dir):
            dst = os.path.join(tmp, name)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy(os.path.join(code_dir, name), dst)
        open(os.path.join(tmp, "starter.py"), "w", encoding="utf-8").write(src)
        try:
            r = subprocess.run([sys.executable, "-I", "check.py", str(n)], cwd=tmp, capture_output=True, text=True, timeout=180)
        except subprocess.TimeoutExpired:
            return [f"{label} m{n}: check.py {n} timed out"]
        out = r.stdout + r.stderr
        tail = "\n    " + out.strip().replace("\n", "\n    ")[-600:]
        if "Traceback" in out:
            return [f"{label} m{n}: the checker crashed:" + tail]
        m = re.search(r"(\d+)/(\d+) milestones passing", out)
        if not m:
            return [f"{label} m{n}: no summary line from check.py:" + tail]
        if int(m.group(1)) > 0:
            return [f"{label} m{n}: the stub already passes, so the stub is on the wrong milestone:" + tail]
        if "not implemented yet" not in out:
            print(f"  note: {label} m{n}: the checker reports ✘ rather than 'not implemented yet' (the lab catches exceptions)")
    return []


if __name__ == "__main__":
    build("--verify" in sys.argv)
