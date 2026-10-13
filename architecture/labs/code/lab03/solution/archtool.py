"""Lab 3 reference solution: an import-graph extractor, a boundary checker, a cycle finder.

    python3 archtool.py <dir-that-contains-shop> [graph|check|cycles|all]
"""
import ast
import os
import sys
from collections import namedtuple

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))      # rules.py lives one folder up
import rules as default_rules                  # noqa: E402

PACKAGE = "shop"

Import = namedtuple("Import", "file line importer target")
Violation = namedtuple("Violation", "file line rule message")


def module_of(dotted):
    """'shop.catalog.api' -> 'catalog'; 'shop.db' -> 'db'; 'shop' or 'os.path' -> None."""
    parts = dotted.split(".")
    return parts[1] if parts[0] == PACKAGE and len(parts) > 1 else None


# ---- Milestone 1: the import graph ----------------------------------------------------
def _exists(root, dotted):
    """Is there a module or package called `dotted` under root?"""
    path = os.path.join(root, *dotted.split("."))
    return os.path.isfile(path + ".py") or os.path.isfile(os.path.join(path, "__init__.py"))


def _resolve(root, node, pkg_parts):
    """All the dotted names one import statement refers to (relative imports resolved)."""
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]
    if node.level:                                  # from ..x import y: climb level-1 packages
        base = pkg_parts[:len(pkg_parts) - (node.level - 1)]
        if node.module:
            base = base + node.module.split(".")
    else:
        base = node.module.split(".")
    base = ".".join(base)
    out = []
    for alias in node.names:
        sub = base + "." + alias.name
        out.append(sub if _exists(root, sub) else base)   # 'from shop.catalog import api' names a module
    return out


def extract_imports(root):
    """Every import inside root/shop as Import(file, line, importer, target)."""
    found = set()                                 # a set: 'from x import a, b' is one import line
    pkg_dir = os.path.join(root, PACKAGE)
    for folder, dirs, files in os.walk(pkg_dir):
        dirs.sort()
        for name in sorted(files):
            if not name.endswith(".py"):
                continue
            path = os.path.join(folder, name)
            rel = os.path.relpath(path, root)
            parts = rel[:-3].split(os.sep)            # ['shop', 'payments', 'service']
            pkg_parts = parts[:-1]                    # the package the file lives in
            dotted = ".".join(pkg_parts if name == "__init__.py" else parts)
            importer = module_of(dotted)
            with open(path, encoding="utf-8") as f:
                tree = ast.parse(f.read(), path)
            for node in ast.walk(tree):               # ast.walk also finds imports inside functions
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    for target in _resolve(root, node, pkg_parts):
                        if target == PACKAGE or target.startswith(PACKAGE + "."):
                            found.add(Import(rel, node.lineno, importer, target))
    return sorted(found)


def module_graph(imports):
    """{module: set of other modules it imports}. Imports inside one module are dropped."""
    graph = {}
    for imp in imports:
        target = module_of(imp.target)
        if imp.importer and target and imp.importer != target:
            graph.setdefault(imp.importer, set()).add(target)
    return graph


def format_graph(graph):
    """One line per module that has dependencies: 'ordering -> cart, catalog'."""
    return "\n".join(f"{m} -> {', '.join(sorted(graph[m]))}" for m in sorted(graph) if graph[m])


# ---- Milestone 2: boundary rules ------------------------------------------------------
def check_boundaries(imports, rules=default_rules):
    """Return a sorted list of Violation(file, line, rule, message)."""
    out = []
    for imp in imports:
        target = module_of(imp.target)
        if imp.importer not in rules.ALLOWED or target is None or target == imp.importer:
            continue
        if target not in rules.ALLOWED:
            out.append(Violation(imp.file, imp.line, "shared",
                                 f"{imp.importer} imports {imp.target}: not a declared module (shared state?)"))
            continue
        if target not in rules.ALLOWED[imp.importer]:
            out.append(Violation(imp.file, imp.line, "dependency",
                                 f"{imp.importer} may not depend on {target}"))
        if imp.target != f"{PACKAGE}.{target}.{rules.PUBLIC_API}":
            out.append(Violation(imp.file, imp.line, "internal",
                                 f"{imp.importer} imports {imp.target}: use {PACKAGE}.{target}.{rules.PUBLIC_API}"))
    return sorted(out)


# ---- Milestone 3: cycles --------------------------------------------------------------
def find_cycles(graph):
    """Every elementary cycle, each starting at its smallest module, the list sorted."""
    cycles = []

    def walk(start, node, path):
        for nxt in sorted(graph.get(node, ())):
            if nxt == start:
                cycles.append(list(path))
            elif nxt > start and nxt not in path:     # only visit bigger names: each cycle found once
                walk(start, nxt, path + [nxt])

    for start in sorted(graph):
        walk(start, start, [start])
    return sorted(cycles)


# ---- command line ---------------------------------------------------------------------
def main(argv):
    root = argv[1] if len(argv) > 1 else "."
    what = argv[2] if len(argv) > 2 else "all"
    imports = extract_imports(root)
    graph = module_graph(imports)
    if what in ("graph", "all"):
        print("Dependencies:")
        print(format_graph(graph))
    if what in ("check", "all"):
        violations = check_boundaries(imports)
        print(f"\n{len(violations)} boundary violation(s):")
        for v in violations:
            print(f"  {v.file}:{v.line}: [{v.rule}] {v.message}")
    if what in ("cycles", "all"):
        cycles = find_cycles(graph)
        print(f"\n{len(cycles)} cycle(s):")
        for c in cycles:
            print("  " + " -> ".join(c + [c[0]]))
    return 1 if what in ("check", "all") and violations else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
