"""Turn a workbench script into a paired Jupyter notebook.

    python3 authoring/py2ipynb.py path/to/script.py [...]   # writes script.ipynb

The docstring becomes the first markdown cell; each "# ── N. Title ───"
banner starts a new section (a markdown heading, then the code). The script
stays the source of truth: re-run this after editing it. Notebooks are written
without outputs, so they show what the reader will run, not stale results.
"""
import ast
import json
import re
import sys

BANNER = re.compile(r"^# ── (\d+\.\s*.*?)\s*─*$")


def cells_of(src):
    tree = ast.parse(src)
    doc = ast.get_docstring(tree) or ""
    body = src
    if doc:                          # drop the docstring from the code
        first = tree.body[0]
        lines = src.splitlines(keepends=True)
        body = "".join(lines[first.end_lineno:])
    cells = []
    if doc:
        cells.append(("markdown", doc))
    chunk, title = [], None
    for line in body.splitlines():
        m = BANNER.match(line)
        if m:
            if "".join(chunk).strip():
                cells.append(("code", "\n".join(chunk).strip("\n")))
            chunk = []
            cells.append(("markdown", "## " + m.group(1)))
            continue
        chunk.append(line)
    if "".join(chunk).strip():
        cells.append(("code", "\n".join(chunk).strip("\n")))
    return cells


def notebook(cells):
    def cell(kind, text):
        c = {"cell_type": kind, "metadata": {}, "source": text.splitlines(keepends=True)}
        if kind == "code":
            c.update(execution_count=None, outputs=[])
        return c
    return {"cells": [cell(k, t) for k, t in cells],
            "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                         "language_info": {"name": "python"}},
            "nbformat": 4, "nbformat_minor": 5}


for path in sys.argv[1:]:
    nb = notebook(cells_of(open(path, encoding="utf-8").read()))
    out = re.sub(r"\.py$", ".ipynb", path)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(nb, f, indent=1, ensure_ascii=False)
        f.write("\n")
    print(f"{out}: {len(nb['cells'])} cells")
