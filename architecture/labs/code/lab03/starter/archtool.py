"""Lab 3: an import-graph extractor, a boundary checker and a cycle finder.

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
def extract_imports(root):
    """Return every import inside root/shop as Import(file, line, importer, target).

    root       a folder that contains the package folder  shop/
    file       path relative to root, e.g. 'shop/payments/service.py'
    line       node.lineno of the import statement
    importer   the module the file belongs to ('payments'), or None for shop/__init__.py
    target     the full dotted name imported, e.g. 'shop.catalog.api'

    Steps:
      1. Walk root/shop for *.py files (sort them, so output is stable).
      2. Parse each with ast.parse and look at every ast.Import / ast.ImportFrom node.
         ast.walk(tree) also finds imports inside functions.
      3. Work out the file's own package from its path: shop/payments/service.py lives in
         package ['shop', 'payments'].
      4. ImportFrom has .level (number of leading dots), .module and .names:
           from ..ordering import service   level=2, module='ordering', names=[service]
         Climb level-1 packages up from the file's package, then append .module.
      5. 'from shop.catalog import api' really imports the MODULE shop.catalog.api. If
         base + '.' + name exists as a .py file or a package folder, that is the target.
         Otherwise the target is just the base (a function or class was imported).
      6. Keep only targets that are 'shop' or start with 'shop.'. Skip the rest (os, sys).
      7. Return a sorted list; use a set first, so 'from x import a, b' counts once.
    """
    raise NotImplementedError("TODO milestone 1: extract_imports")


def module_graph(imports):
    """Return {module: set of other modules it imports}.

    Use module_of() on the target. Drop imports of your own module (payments importing
    payments.service) and imports whose importer or target module is None.
    """
    raise NotImplementedError("TODO milestone 1: module_graph")


def format_graph(graph):
    """One line per module that has dependencies, sorted, e.g.  'ordering -> cart, catalog'.

    Modules without dependencies are left out.
    """
    raise NotImplementedError("TODO milestone 1: format_graph")


# ---- Milestone 2: boundary rules ------------------------------------------------------
def check_boundaries(imports, rules=default_rules):
    """Return a sorted list of Violation(file, line, rule, message).

    For every import whose importer is a key of rules.ALLOWED and whose target module is a
    different module:
      rule 'shared'      the target module is not a key of rules.ALLOWED (it is shared state,
                         like shop.db). One violation, then move on to the next import.
      rule 'dependency'  the target is not in rules.ALLOWED[importer].
      rule 'internal'    the target is not exactly  shop.<module>.<rules.PUBLIC_API>.
    One import line can break both 'dependency' and 'internal': report both.
    """
    raise NotImplementedError("TODO milestone 2: check_boundaries")


# ---- Milestone 3: cycles --------------------------------------------------------------
def find_cycles(graph):
    """Return every elementary cycle of the module graph.

    Each cycle is a list of module names that starts with its alphabetically smallest
    module and does not repeat the first name at the end: ['ordering', 'payments'].
    Return the cycles sorted. A graph without cycles returns [].

    Idea: depth-first search from each start module, only walking to modules that sort
    after the start (so a cycle is found once, from its smallest member) and never
    revisiting a module already on the current path.
    """
    raise NotImplementedError("TODO milestone 3: find_cycles")


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
