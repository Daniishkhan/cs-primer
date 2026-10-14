"""Rebuild glossary.html: the track-1 entries (authoring/glossary-track1.html, frozen)
plus every AI-track glossary-src/*.json file. Safe to rerun.

    python3 authoring/build_glossary.py
"""
import glob
import html
import json
import os
import re
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
cat = json.loads(subprocess.check_output(["node", "-e",
    "global.window={};require(%r);console.log(JSON.stringify(window.CS_COURSES.map(c=>({id:c.id,dir:c.dir,title:c.title,track:c.track||null,chapters:c.chapters.map(x=>({id:x.id,file:x.file}))}))))"
    % os.path.join(ROOT, "assets/js/catalog.js")]))
by_dir = {c["dir"]: c for c in cat}

base = open(os.path.join(ROOT, "authoring/glossary-track1.html"), encoding="utf-8").read()
old = re.findall(r'  <div class="gloss" data-course="[^"]+" data-text="[^"]*"><dt>.*?</dd></div>', base)
entries = []  # (sort_key, html)
for line in old:
    term = html.unescape(re.search(r"<dt>(.*?) <span", line).group(1))
    entries.append((term.lower(), line))

seen = {e[0] for e in entries}
added, skipped = 0, []
for path in sorted(glob.glob(os.path.join(ROOT, "glossary-src", "*.json"))):
    try:
        items = json.load(open(path, encoding="utf-8"))
    except Exception as e:
        skipped.append(f"{os.path.basename(path)}: {e}")
        continue
    for it in items:
        term, d, f = it["term"].strip(), it["def"].strip().replace("—", ", "), it["file"].strip().lstrip("/")
        course = by_dir.get(f.split("/")[0])
        if not course or not os.path.exists(os.path.join(ROOT, f)):
            skipped.append(f"{term}: bad file {f}")
            continue
        key = term.lower()
        if key in seen:
            # same term already defined (possibly in track 1): keep both only if from a different course
            if any(k == key and f'data-course="{course["id"]}"' in h for k, h in entries):
                continue
        seen.add(key)
        ch = next((c for c in course["chapters"] if c["file"] == os.path.basename(f)), None)
        label = f"Chapter {int(ch['id'])} →" if ch else "Read →"
        if not d.endswith("."):
            d += "."
        text = (term + " " + d).lower()
        entries.append((key, f'  <div class="gloss" data-course="{course["id"]}" data-text="{html.escape(text, quote=True)}"><dt>{html.escape(term)} '
                             f'<span class="gloss-course">{html.escape(course["title"])}</span></dt><dd>{html.escape(d)} '
                             f'<a href="{html.escape(f)}">{label}</a></dd></div>'))
        added += 1

entries.sort(key=lambda e: (re.sub(r"[^a-z0-9]", "", e[0]) or e[0]))
groups = {}
for k, h in entries:
    letter = k[0].upper() if k[0].isalpha() else "#"
    groups.setdefault(letter, []).append(h)
parts = []
for letter in sorted(groups, key=lambda L: (L == "#", L)):
    parts.append(f'<dl class="gloss-group" data-letter="{letter}">\n  <p class="gloss-letter">{letter}</p>\n' + "\n".join(groups[letter]) + "\n</dl>")
chips = '<div class="gloss-chips" role="group" aria-label="Filter by course"><button type="button" class="pill active" data-course="">All</button>' + \
    "".join(f'<button type="button" class="pill" data-course="{c["id"]}">{html.escape(c["title"])}</button>' for c in cat) + "</div>"

out = base
out = re.sub(r'<div class="gloss-chips".*?</div>', chips, out, count=1, flags=re.S)
start = out.index('<div class="glossary-list">') + len('<div class="glossary-list">')
end = out.index("</div>\n</article>") if "</div>\n</article>" in out else None
if end is None:
    raise SystemExit("could not find the end of the glossary list")
out = out[:start] + "\n" + "\n".join(parts) + "\n" + out[end:]
out = re.sub(r"<p class=\"lede\">\d+ terms from across the path", f'<p class="lede">{len(entries)} terms from across both paths', out)
out = out.replace("<title>Glossary · Zero to Systems</title>", "<title>Glossary · Zero to Systems</title>")
open(os.path.join(ROOT, "glossary.html"), "w", encoding="utf-8").write(out)
print(f"{len(entries)} entries ({added} from glossary-src)")
for s in skipped:
    print("skipped:", s)
