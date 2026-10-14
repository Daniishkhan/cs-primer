"""Lint pages against the site's page contract.

    python3 authoring/check_page.py path/to/page.html [more.html ...]
    python3 authoring/check_page.py --course agt      # every page of one course
    python3 authoring/check_page.py --all-ai          # every AI-track page that exists
    python3 authoring/check_page.py --global-ids      # marker/gradient id collisions across the site

Exit status 1 if any ERROR. WARN lines are advice. Needs node (to read catalog.js).
"""
import html
import json
import os
import re
import subprocess
import sys
from html.parser import HTMLParser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AMERICAN = ["behavior", "color", "optimiz", "analyz", "modeling", "modeled", "labeled", "labeling", "center ",
            "centered", "favorite", "organiz", "recogniz", "summariz", "normaliz", "tokeniz", "visualiz",
            "generaliz", "regulariz", "minimiz", "maximiz", "prioritiz", "utiliz", "initializ", "parameteriz",
            "quantiz", "randomiz", "categoriz", "characteriz", "standardiz", "memoriz", "serializ", "license ",
            "catalog ", "defense", "artifact", "gray"]


def catalog():
    js = ("global.window={};require(%r);console.log(JSON.stringify(window.CS_COURSES.map(c=>({id:c.id,dir:c.dir,track:c.track||null,title:c.title,"
          "chapters:c.chapters.map(x=>({id:x.id,file:x.file,title:x.title,depth:x.depth})),labs:c.labs.map(x=>({id:x.id,file:x.file,title:x.title})),"
          "cases:c.cases.map(x=>({id:x.id,file:x.file,title:x.title})),studios:(c.studios||[]).map(x=>({id:x.id,file:x.file,title:x.title})),"
          "tools:(c.tools||[]).map(t=>t.id)}))))") % os.path.join(ROOT, "assets/js/catalog.js")
    return json.loads(subprocess.check_output(["node", "-e", js]))


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tags, self.ids, self.links, self.body_attrs = [], [], [], {}
        self.title, self.in_title = "", False
        self.text_parts, self.code_depth, self.script_depth = [], 0, 0
        self.quiz_q, self.qs = None, []
        self.in_option = False
        self.classes = []
        self.h1 = ""
        self.in_h1 = False
        self.in_svg = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        self.tags.append(tag)
        cls = a.get("class", "") or ""
        self.classes.extend(cls.split())
        if "id" in a:
            self.ids.append(a["id"])
        for k in ("href", "src"):
            if k in a and a[k]:
                self.links.append(a[k])
        if tag == "body":
            self.body_attrs = a
        if tag == "title":
            self.in_title = True
        if tag == "h1":
            self.in_h1 = True
        if tag in ("code", "pre"):
            self.code_depth += 1
        if tag in ("script", "style"):
            self.script_depth += 1
        if tag == "svg":
            self.in_svg += 1
        if tag == "div" and "q" in cls.split():
            self.quiz_q = {"answer": a.get("data-answer"), "options": 0}
            self.qs.append(self.quiz_q)
        if tag == "li" and self.quiz_q is not None and self._in_options:
            self.quiz_q["options"] += 1
        if tag == "ol" and "q-options" in cls.split():
            self._in_options = True

    _in_options = False

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
        if tag == "h1":
            self.in_h1 = False
        if tag in ("code", "pre"):
            self.code_depth -= 1
        if tag in ("script", "style"):
            self.script_depth -= 1
        if tag == "svg":
            self.in_svg -= 1
        if tag == "ol" and self._in_options:
            self._in_options = False

    def handle_data(self, d):
        if self.in_title:
            self.title += d
        if self.in_h1:
            self.h1 += d
        if self.code_depth == 0 and self.script_depth == 0 and self.in_svg == 0:
            self.text_parts.append(d)


def kind_of(path):
    parts = path.split(os.sep)
    for k, folder in (("chapter", "chapters"), ("lab", "labs"), ("case", "cases"), ("studio", "studios")):
        if folder in parts[-2:-1]:
            return k
    base = os.path.basename(path)
    return {"index.html": "course", "toolbox.html": "toolbox"}.get(base, "other")


def lint(path, cat, out):
    rel = os.path.relpath(os.path.abspath(path), ROOT)
    errs, warns = [], []
    src = open(path, encoding="utf-8").read()
    p = Page()
    p.feed(src)
    kind = kind_of(rel) if os.sep in rel else "other"
    dirname = rel.split(os.sep)[0]
    course = next((c for c in cat if c["dir"] == dirname), None)
    if not src.startswith("<!doctype html>"):
        errs.append("must start with <!doctype html>")
    depth = rel.count(os.sep)
    prefix = "/".join([".."] * depth) if depth else "."
    for need in ("assets/css/theme.css", "assets/css/main.css", "assets/js/catalog.js", "assets/js/main.js"):
        want = f'{prefix}/{need}' if depth else need
        if f'"{want}"' not in src:
            errs.append(f"missing {want}")
    if 'localStorage.getItem("nz-theme")' not in src:
        errs.append("missing the theme bootstrap <script> in <head>")
    for need in ('<aside id="sidebar" class="sidebar"></aside>', '<main class="content">'):
        if need not in src:
            errs.append(f"missing {need}")
    b = p.body_attrs
    if b.get("data-root") != prefix:
        errs.append(f'body data-root should be "{prefix}", is {b.get("data-root")!r}')
    if course is None and depth:
        errs.append(f"folder {dirname}/ is not a course in catalog.js")
    if course is not None:
        if kind in ("chapter", "lab", "case", "studio", "course", "toolbox") and b.get("data-course") != course["id"]:
            errs.append(f'body data-course should be "{course["id"]}"')
        coll = {"chapter": "chapters", "lab": "labs", "case": "cases", "studio": "studios"}.get(kind)
        if coll:
            attr = "data-" + kind
            entry = next((e for e in course[coll] if e["file"] == os.path.basename(rel)), None)
            if entry is None:
                errs.append(f"{os.path.basename(rel)} is not listed in catalog.js {coll} for {course['id']}")
            else:
                if b.get(attr) != entry["id"]:
                    errs.append(f'body {attr} should be "{entry["id"]}", is {b.get(attr)!r}')
                want = entry["title"] if kind != "lab" else f'Lab {int(entry["id"][1:])}: {entry["title"]}'
                if html.unescape(p.h1.strip()) != want:
                    warns.append(f"h1 {p.h1.strip()!r} differs from catalog title {want!r}")
                if not p.title.strip().startswith(html.unescape(want)) and not html.unescape(p.title.strip()).startswith(want):
                    warns.append(f"<title> should start with {want!r}")
        if kind == "toolbox":
            for t in course["tools"]:
                if t not in p.ids:
                    errs.append(f'toolbox has no section id="{t}"')
    if "chapter-head" not in p.classes and kind in ("chapter", "lab", "case", "studio", "toolbox"):
        errs.append('missing <header class="chapter-head">')
    if kind in ("chapter", "lab", "case", "studio") and "article" not in p.tags:
        errs.append('missing <article class="prose">')
    # scripts
    if "quiz" in p.classes and "assets/js/quiz.js" not in src:
        errs.append("page has a quiz but does not load quiz.js")
    if "stepper" in p.classes and "assets/js/stepper.js" not in src:
        errs.append("page has a stepper but does not load stepper.js")
    if kind == "studio" and "assets/js/studio.js" not in src:
        errs.append("studio page must load studio.js")
    if kind == "studio":
        for c in ("studio-brief", "studio-notes", "stage", "reveal", "rubric"):
            if c not in p.classes:
                errs.append(f'studio missing class "{c}"')
    # ids
    seen = set()
    for i in p.ids:
        if i in seen:
            errs.append(f'duplicate id "{i}" on the page')
        seen.add(i)
    # links
    for href in p.links:
        if re.match(r"^(https?:|mailto:|data:|#|javascript:)", href):
            continue
        target = href.split("#")[0].split("?")[0]
        if not target:
            continue
        full = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(path)), target))
        if not os.path.exists(full):
            errs.append(f"broken link: {href}")
    # quiz
    for n, q in enumerate(p.qs, 1):
        try:
            ans = int(q["answer"])
        except (TypeError, ValueError):
            errs.append(f"quiz question {n}: data-answer missing or not a number")
            continue
        if not (0 <= ans < q["options"]):
            errs.append(f"quiz question {n}: data-answer={ans} but {q['options']} options")
    if kind == "chapter" and len(p.qs) < 4:
        warns.append(f"only {len(p.qs)} quiz questions")
    if p.qs:
        answers = [q["answer"] for q in p.qs]
        if len(set(answers)) == 1 and len(answers) > 2:
            warns.append("every quiz answer is in the same position")
    # prose checks
    prose = " ".join(p.text_parts)
    prose_clean = re.sub(r"https?://\S+", "", prose)
    if "—" in src:
        errs.append(f"{src.count(chr(0x2014))} em-dash(es) found; rewrite without them")
    low = prose_clean.lower()
    hits = sorted({w.strip() for w in AMERICAN if w in low})
    if hits:
        warns.append("possible American spellings in prose: " + ", ".join(hits))
    words = len(re.findall(r"[A-Za-z][A-Za-z'-]*", prose_clean))
    if kind == "chapter":
        if "term" not in p.classes:
            warns.append('no <span class="term"> definitions')
        if "callout key" not in src:
            warns.append("no Key takeaways callout")
        if course:
            entry = next((e for e in course["chapters"] if e["file"] == os.path.basename(rel)), None)
            if entry:
                g = os.path.join(ROOT, "glossary-src", f'{course["id"]}-{entry["id"]}.json')
                if course["track"] == "ai":
                    if not os.path.exists(g):
                        warns.append(f"no glossary file {os.path.relpath(g, ROOT)}")
                    else:
                        try:
                            data = json.load(open(g, encoding="utf-8"))
                            assert isinstance(data, list) and all({"term", "def", "file"} <= set(d) for d in data)
                        except Exception as e:
                            errs.append(f"glossary file {os.path.relpath(g, ROOT)} invalid: {e}")
                lo, hi = {"deep": (4000, 9000), "core": (2500, 6500), "intro": (1100, 3500)}[entry["depth"]]
                if words < lo * 0.8:
                    warns.append(f"about {words} words of prose; target for {entry['depth']} is {lo} to {hi}")
    if "<pre" in src and 'data-title="output"' not in src and kind == "chapter":
        warns.append("no output blocks: chapters should show real output of code they run")
    status = "ERROR" if errs else ("WARN " if warns else "ok   ")
    out.append(f"{status} {rel}  (~{words} words)")
    for e in errs:
        out.append(f"    ERROR {e}")
    for w in warns:
        out.append(f"    WARN  {w}")
    return not errs


def global_ids(cat):
    pat = re.compile(r'<(?:marker|linearGradient|radialGradient|clipPath|pattern|filter)[^>]*\bid="([^"]+)"')
    owner = {}
    bad = 0
    for dirpath, _, files in os.walk(ROOT):
        if "/graft" in dirpath or "/.git" in dirpath:
            continue
        for f in files:
            if f.endswith(".html"):
                path = os.path.join(dirpath, f)
                for i in set(pat.findall(open(path, encoding="utf-8").read())):
                    if i in owner:
                        print(f"collision: id {i!r} in {os.path.relpath(path, ROOT)} and {owner[i]}")
                        bad += 1
                    else:
                        owner[i] = os.path.relpath(path, ROOT)
    print(f"{len(owner)} SVG defs ids, {bad} collisions")
    return bad == 0


def main(argv):
    cat = catalog()
    if "--global-ids" in argv:
        sys.exit(0 if global_ids(cat) else 1)
    paths = [a for a in argv if not a.startswith("--")]
    if "--course" in argv:
        cid = argv[argv.index("--course") + 1]
        paths = [a for a in paths if a != cid]
        co = next(c for c in cat if c["id"] == cid)
        d = os.path.join(ROOT, co["dir"])
        for sub in ("chapters", "labs", "cases", "studios"):
            sd = os.path.join(d, sub)
            if os.path.isdir(sd):
                paths += [os.path.join(sd, f) for f in sorted(os.listdir(sd)) if f.endswith(".html")]
        for f in ("index.html", "toolbox.html"):
            if os.path.exists(os.path.join(d, f)):
                paths.append(os.path.join(d, f))
    if "--all-ai" in argv:
        for co in cat:
            if co["track"] != "ai":
                continue
            d = os.path.join(ROOT, co["dir"])
            for sub in ("chapters", "labs", "cases", "studios"):
                sd = os.path.join(d, sub)
                if os.path.isdir(sd):
                    paths += [os.path.join(sd, f) for f in sorted(os.listdir(sd)) if f.endswith(".html")]
            for f in ("index.html", "toolbox.html"):
                if os.path.exists(os.path.join(d, f)):
                    paths.append(os.path.join(d, f))
    out, ok = [], True
    for p in paths:
        ok &= lint(p, cat, out)
    print("\n".join(out))
    print(f"\n{len(paths)} page(s), {sum(1 for l in out if l.startswith('ERROR'))} with errors, {sum(1 for l in out if l.startswith('WARN'))} with warnings only")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main(sys.argv[1:])
