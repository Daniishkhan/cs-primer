"""Remove pages or whole courses from the site, and repair what points at them.

    python3 authoring/remove_pages.py --dir ai-delivery --page ml/chapters/03-x.html ...
    python3 authoring/remove_pages.py --move retrieval/chapters/07-a.html=agents/chapters/23-a.html ...
    python3 authoring/remove_pages.py ... --apply      # dry run without it

What it does:
  1. Builds the deleted set: every file under each --dir, each --page, the code
     folder a lab page links to (code/labNN/), the code folder of a workbench
     (code/wNN/), and glossary-src/<course>-<chapter>.json for chapters.
  2. --move OLD=NEW moves a page (and, for a workbench, OLD's code folder to
     NEW's). Links to OLD are rewritten to NEW, and the moved page's own
     relative links are re-pointed from its new folder.
  3. In every remaining page, an <a href> that resolves into the deleted set is
     unwrapped to its inner text.
  4. Reports, without editing, lines that still name a deleted course or a
     deleted chapter's title, so they can be reworded by hand.
  5. Lists widgets (assets/js/widgets, assets/css/widgets) that no remaining
     page loads, and unit briefs (authoring/units) whose pages are all gone;
     with --apply they are deleted too.
With --apply, files are removed with `git rm` and moved with `git mv`.
The catalog (assets/js/catalog.js) is edited by hand afterwards.
"""
import argparse
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {".git", "graft", "node_modules", "__pycache__"}
ANCHOR = re.compile(r'<a\b([^>]*?)\bhref="([^"]*)"([^>]*)>(.*?)</a>', re.S)
PAGE_PATH = re.compile(r'[a-z][\w-]*/(?:chapters|labs|cases|studios|workbench)/[\w.-]+\.html')


def rel(p):
    return os.path.relpath(p, ROOT).replace(os.sep, "/")


def catalog():
    js = ("global.window={};require(process.argv[1]);"
          "console.log(JSON.stringify(window.CS_COURSES.map(c=>({id:c.id,dir:c.dir,title:c.title,"
          "chapters:(c.chapters||[]).map(x=>({id:x.id,file:x.file,title:x.title}))}))))")
    out = subprocess.run(["node", "-e", js, os.path.join(ROOT, "assets/js/catalog.js")],
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def all_files(base):
    for d, dirs, files in os.walk(base):
        dirs[:] = [x for x in dirs if x not in SKIP_DIRS]
        for f in files:
            yield os.path.join(d, f)


def html_pages():
    return [p for p in all_files(ROOT) if p.endswith(".html")]


def code_folder(page):
    """The code folder a lab or workbench page belongs to, or None."""
    d, f = os.path.split(page)
    m = re.match(r"lab-(\d\d)-", f)
    if m and os.path.basename(d) == "labs":
        return os.path.join(d, "code", "lab" + m.group(1))
    m = re.match(r"w(\d\d)-", f)
    if m and os.path.basename(d) == "workbench":
        return os.path.join(d, "code", "w" + m.group(1))
    return None


def resolve(page, href):
    """Absolute path an href points at, or None for external/anchor links."""
    if not href or re.match(r"^(?:[a-z]+:|#|//)", href):
        return None
    path = href.split("#")[0].split("?")[0]
    if not path:
        return None
    return os.path.normpath(os.path.join(os.path.dirname(page), path))


def relhref(from_page, target, fragment):
    r = os.path.relpath(target, os.path.dirname(from_page)).replace(os.sep, "/")
    if os.path.isdir(target) and not r.endswith("/"):
        r += "/"
    return r + fragment


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", action="append", default=[])
    ap.add_argument("--page", action="append", default=[])
    ap.add_argument("--move", action="append", default=[])
    ap.add_argument("--mention", action="append", default=[], help="extra regex to report")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    cat = catalog()
    by_dir = {c["dir"]: c for c in cat}

    deleted_dirs = [os.path.join(ROOT, d.strip("/")) for d in a.dir]
    deleted = set()
    for d in deleted_dirs:
        if not os.path.isdir(d):
            sys.exit("no such folder: " + rel(d))
        deleted.update(all_files(d))
    titles = []
    for p in a.page:
        ap_ = os.path.join(ROOT, p)
        if not os.path.exists(ap_):
            sys.exit("no such page: " + p)
        deleted.add(ap_)
        cf = code_folder(ap_)
        if cf and os.path.isdir(cf):
            deleted.update(all_files(cf))
    # glossary files and titles for deleted chapters
    gloss = []
    for c in cat:
        for ch in c["chapters"]:
            page = os.path.join(ROOT, c["dir"], "chapters", ch["file"])
            if page in deleted or any(page.startswith(d + os.sep) for d in deleted_dirs):
                titles.append(ch["title"])
                g = os.path.join(ROOT, "glossary-src", "%s-%s.json" % (c["id"], ch["id"]))
                if os.path.exists(g):
                    gloss.append(g)
    deleted.update(gloss)
    for d in deleted_dirs:
        c = by_dir.get(rel(d))
        if c:
            titles.append(c["title"])

    moves = {}
    for m in a.move:
        old, new = m.split("=")
        old, new = os.path.join(ROOT, old), os.path.join(ROOT, new)
        if not os.path.exists(old):
            sys.exit("no such page to move: " + rel(old))
        moves[old] = new
        oc, nc = code_folder(old), code_folder(new)
        if oc and nc and os.path.isdir(oc):
            moves[oc] = nc
        deleted.discard(old)

    def moved_to(target):
        for old, new in moves.items():
            if target == old:
                return new
            if os.path.isdir(old) and target.startswith(old + os.sep):
                return new + target[len(old):]
        return None

    def is_deleted(target):
        if moved_to(target):
            return False
        if target in deleted:
            return True
        return any(target == d or target.startswith(d + os.sep) for d in deleted_dirs)

    remaining = [p for p in html_pages() if not is_deleted(p)]
    edits, unwrapped, rewritten = {}, 0, 0
    for page in remaining:
        src = open(page, encoding="utf-8").read()
        new_page = moves.get(page)
        here = new_page or page

        def fix(m):
            nonlocal unwrapped, rewritten
            pre, href, post, inner = m.groups()
            target = resolve(page, href)
            if target is None:
                return m.group(0)
            frag = "#" + href.split("#", 1)[1] if "#" in href else ""
            mt = moved_to(target)
            if mt:
                rewritten += 1
                return '<a%shref="%s"%s>%s</a>' % (pre, relhref(here, mt, frag), post, inner)
            if is_deleted(target):
                unwrapped += 1
                line = src.count("\n", 0, m.start()) + 1
                print("  unwrap %s:%d  %s" % (rel(page), line, rel(target)))
                return inner
            if new_page:                       # moved page: re-point its own links
                r = relhref(here, target, frag)
                if r != href:
                    rewritten += 1
                    return '<a%shref="%s"%s>%s</a>' % (pre, r, post, inner)
            return m.group(0)

        out = ANCHOR.sub(fix, src)
        if out != src:
            edits[page] = out

    print("\n%d files deleted, %d moved, %d links unwrapped, %d rewritten, in %d pages"
          % (len(deleted), len(moves), unwrapped, rewritten, len(edits)))

    # mentions to reword by hand
    pats = [re.escape(t) for t in titles if len(t) > 12] + a.mention
    if pats:
        rx = re.compile("|".join(pats))
        print("\nLines that still name deleted material (reword by hand):")
        for page in remaining:
            text = edits.get(page) or open(page, encoding="utf-8").read()
            for i, line in enumerate(text.split("\n"), 1):
                if rx.search(re.sub(r"<[^>]+>", "", line)):
                    print("  %s:%d" % (rel(page), i))

    # orphans
    refs = "\n".join(edits.get(p) or open(p, encoding="utf-8").read() for p in remaining)
    orphans = []
    for sub in ("assets/js/widgets", "assets/css/widgets"):
        base = os.path.join(ROOT, sub)
        for f in sorted(os.listdir(base)) if os.path.isdir(base) else []:
            if f not in refs:
                orphans.append(os.path.join(base, f))
    units_dir = os.path.join(ROOT, "authoring", "units")
    dead_units = []
    if os.path.isdir(units_dir):
        for f in sorted(os.listdir(units_dir)):
            if not f.endswith(".md"):
                continue
            paths = set(PAGE_PATH.findall(open(os.path.join(units_dir, f), encoding="utf-8").read()))
            if paths and all(is_deleted(os.path.join(ROOT, p)) for p in paths):
                dead_units.append(os.path.join(units_dir, f))
    print("\n%d orphaned widget files, %d unit briefs with no surviving page" % (len(orphans), len(dead_units)))
    for o in orphans + dead_units:
        print("  " + rel(o))

    if not a.apply:
        print("\nDry run. Re-run with --apply to change files.")
        return
    tracked = set(subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True).stdout.split("\n"))
    deleted = {p for p in deleted if not moved_to(p)}
    gone = sorted(set(map(rel, deleted)) | set(map(rel, orphans)) | set(map(rel, dead_units)))
    for chunk in range(0, len(gone), 200):
        part = gone[chunk:chunk + 200]
        tr = [p for p in part if p in tracked]
        if tr:
            subprocess.run(["git", "rm", "-q", "-r", "--"] + tr, cwd=ROOT, check=True)
        for p in part:
            if p not in tracked and os.path.exists(os.path.join(ROOT, p)):
                os.remove(os.path.join(ROOT, p))
    for page, text in edits.items():
        if page in moves:
            continue
        open(page, "w", encoding="utf-8").write(text)
    for old, new in moves.items():
        os.makedirs(os.path.dirname(new), exist_ok=True)
        subprocess.run(["git", "mv", rel(old), rel(new)], cwd=ROOT, check=True)
        if old in edits:
            open(new, "w", encoding="utf-8").write(edits[old])
    # empty folders left behind
    for d in deleted_dirs:
        if os.path.isdir(d):
            subprocess.run(["find", d, "-depth", "-type", "d", "-empty", "-delete"])
    idx = os.path.join(units_dir, "index.json")
    if os.path.exists(idx) and dead_units:
        names = {os.path.basename(u)[:-3] for u in dead_units}
        data = [u for u in json.load(open(idx)) if u[0] not in names]
        json.dump(data, open(idx, "w"), indent=1)
    print("Applied.")


if __name__ == "__main__":
    main()
