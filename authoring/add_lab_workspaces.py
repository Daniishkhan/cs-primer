"""Add an in-page lab workspace to lab pages (assets/js/runner.js runs it).

    python3 authoring/add_lab_workspaces.py [--skip LIST] [page.html ...]

With no pages, every <course>/labs/lab-*.html. The workspace goes at the end
of the "Before you start" section and lists every file in the lab's folder
(apart from starter.py, which is the editable one), so check.py, solution.py
and any data files are fetched next to it. Pages that already have one, and
labs without a top-level starter.py and check.py, are left alone. --skip
names a file of page paths (one per line, or "N path" lines) not to touch.
"""
import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_PARTS = {"__pycache__", ".claude", ".DS_Store"}

BLOCK = '''<h3>Or work in the page</h3>
<p>Below is <code>starter.py</code>, live. <strong>✎ Edit</strong> it and press <strong>▶ Check</strong> to run <code>check.py</code> against your code in the browser; your edits are saved in this browser until you press Reset. Type <code>solution</code> in <em>args</em> to check the reference answer, or a milestone number to check one milestone. Browser Python is two to three times slower than <code>python3</code>, and your real <code>starter.py</code> is not changed: copy your work across when you are done.</p>
<div class="lab-workspace" data-dir="{dir}" data-files="{files}"></div>

'''


def lab_files(code_dir):
    out = []
    for dirpath, dirs, files in os.walk(code_dir):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_PARTS)
        for f in sorted(files):
            if f in SKIP_PARTS or f.endswith(".pyc"):
                continue
            rel = os.path.relpath(os.path.join(dirpath, f), code_dir)
            if rel != "starter.py":
                out.append(rel)
    return out


def add(page, out):
    src = open(page, encoding="utf-8").read()
    rel = os.path.relpath(page, ROOT)
    if 'class="lab-workspace"' in src:
        out.append(f"has   {rel}")
        return
    m = re.search(r'href="(code/lab\d+/)', src)
    if not m:
        out.append(f"skip  {rel}  (no code/labNN/ link)")
        return
    code_dir = os.path.join(os.path.dirname(page), m.group(1))
    if not (os.path.isfile(os.path.join(code_dir, "starter.py")) and os.path.isfile(os.path.join(code_dir, "check.py"))):
        out.append(f"skip  {rel}  (no top-level starter.py + check.py)")
        return
    start = src.find("<h2>Before you start</h2>")
    nxt = src.find("<h2", start + 10) if start != -1 else -1
    if nxt == -1:
        out.append(f"skip  {rel}  (no 'Before you start' section)")
        return
    block = BLOCK.format(dir=m.group(1), files=" ".join(lab_files(code_dir)))
    src = src[:nxt] + block + src[nxt:]
    open(page, "w", encoding="utf-8").write(src)
    out.append(f"added {rel}")


def main(argv):
    skip = set()
    if argv[:1] == ["--skip"]:
        for line in open(argv[1], encoding="utf-8"):
            if line.strip():
                skip.add(os.path.normpath(line.split()[-1]))
        argv = argv[2:]
    pages = argv or sorted(glob.glob(os.path.join(ROOT, "*/labs/lab-*.html")))
    out = []
    for p in pages:
        if os.path.normpath(os.path.relpath(p, ROOT)) in skip:
            out.append(f"later {os.path.relpath(p, ROOT)}")
            continue
        add(p, out)
    print("\n".join(out))


if __name__ == "__main__":
    main(sys.argv[1:])
