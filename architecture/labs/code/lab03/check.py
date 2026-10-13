"""Self-check for Lab 3: Enforce Module Boundaries.

    python3 check.py              # checks starter/ (your archtool.py and your shop/ refactor)
    python3 check.py solution     # checks the reference answer in solution/

Everything is in-process or in a short subprocess on local files: no network, no threads,
no timing, the same result every run, about a second. Prints a tick, a cross, or
"not implemented yet" for each milestone. Milestone 5 is optional.
"""
import importlib
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace

sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
HERE = os.path.dirname(os.path.abspath(__file__))
target = sys.argv[1] if len(sys.argv) > 1 else "starter"
if target not in ("starter", "solution"):
    sys.exit("usage: python3 check.py [starter|solution]")
TARGET = os.path.join(HERE, target)
MONOLITH = os.path.join(HERE, "monolith")
sys.path.insert(0, HERE)
sys.path.insert(0, TARGET)

import rules  # noqa: E402  (given)
import archtool as mine  # noqa: E402  (YOUR tool: starter/archtool.py or solution/archtool.py)

# The reference tool judges milestone 4, so that milestone does not depend on milestones 1-3.
_spec = importlib.util.spec_from_file_location("ref_archtool", os.path.join(HERE, "solution", "archtool.py"))
ref = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ref)

results = []
notes = []


def note(text):
    notes.append(text)


def check(name, fn):
    del notes[:]
    try:
        fn()
        print(f"  ✔ {name}")
        results.append(True)
    except NotImplementedError as e:
        print(f"  … {name}: not implemented yet ({e})")
        results.append(False)
    except AssertionError as e:
        print(f"  ✘ {name}: {e}")
        results.append(False)
    except Exception as e:
        print(f"  ✘ {name}: {type(e).__name__}: {e}")
        results.append(False)
    for line in notes:
        print(line)


def run(cmd, cwd, env_extra=None):
    env = dict(os.environ, **(env_extra or {}))
    p = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=30)
    return p.returncode, p.stdout + p.stderr


def norm(path):
    return path.replace(os.sep, "/")


def show(items, limit=6):
    items = list(items)
    text = "; ".join(str(i) for i in items[:limit])
    return text + (f"; ... and {len(items) - limit} more" if len(items) > limit else "")


# --- the facts about the given monolith (what a correct tool must find) ----------------
MONOLITH_EDGES = {
    "app": {"cart", "catalog", "db", "ordering", "payments"},
    "cart": {"catalog", "db"},
    "catalog": {"cart", "db"},
    "ordering": {"cart", "catalog", "db", "payments", "shipping"},
    "payments": {"db", "ordering"},
    "shipping": {"catalog", "db", "ordering"},
}
MONOLITH_GRAPH_TEXT = "\n".join([
    "app -> cart, catalog, db, ordering, payments",
    "cart -> catalog, db",
    "catalog -> cart, db",
    "ordering -> cart, catalog, db, payments, shipping",
    "payments -> db, ordering",
    "shipping -> catalog, db, ordering",
])
KNOWN_VIOLATIONS = {
    ("shop/app.py", 2, "internal"), ("shop/app.py", 3, "internal"), ("shop/app.py", 4, "internal"),
    ("shop/app.py", 5, "internal"), ("shop/app.py", 6, "shared"),
    ("shop/cart/service.py", 2, "internal"), ("shop/cart/service.py", 3, "shared"),
    ("shop/catalog/service.py", 2, "shared"), ("shop/catalog/service.py", 3, "dependency"),
    ("shop/catalog/service.py", 3, "internal"),
    ("shop/ordering/service.py", 2, "shared"), ("shop/ordering/service.py", 3, "internal"),
    ("shop/ordering/service.py", 4, "internal"), ("shop/ordering/service.py", 5, "internal"),
    ("shop/ordering/service.py", 6, "internal"), ("shop/ordering/service.py", 7, "internal"),
    ("shop/payments/service.py", 2, "shared"), ("shop/payments/service.py", 3, "dependency"),
    ("shop/payments/service.py", 3, "internal"),
    ("shop/shipping/service.py", 3, "shared"), ("shop/shipping/service.py", 4, "dependency"),
    ("shop/shipping/service.py", 4, "internal"), ("shop/shipping/service.py", 18, "dependency"),
    ("shop/shipping/service.py", 18, "internal"),
}
MONOLITH_CYCLES = [("cart", "catalog"), ("ordering", "payments"), ("ordering", "shipping")]


# --- Milestone 1 ---------------------------------------------------------------------
def make_toy_tree(root):
    files = {
        "shop/__init__.py": "",
        "shop/a/__init__.py": "from .x import f\n",
        "shop/a/helper.py": "",
        "shop/a/x.py": ("import os\n"                                   # 1  not ours: ignored
                        "import shop.b.api\n"                           # 2
                        "from shop.b import api as bapi\n"              # 3  api is a module
                        "from shop.b.internals import thing\n"          # 4  thing is not a module
                        "from . import helper\n"                        # 5  relative, a sibling module
                        "from .helper import f\n"                       # 6
                        "from .. import c\n"                            # 7  two dots: c is a package of shop
                        "from ..b import api\n"                         # 8
                        "\n"
                        "def f():\n"
                        "    from shop.c import api as capi\n"          # 11 inside a function
                        "    return capi\n"),
        "shop/b/__init__.py": "", "shop/b/api.py": "", "shop/b/internals.py": "",
        "shop/c/__init__.py": "", "shop/c/api.py": "",
    }
    for rel, text in files.items():
        path = os.path.join(root, *rel.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(text)


def m1():
    tmp = tempfile.mkdtemp()
    try:
        make_toy_tree(tmp)
        got = {(norm(i[0]), i[1], i[2], i[3]) for i in mine.extract_imports(tmp)}
        want = {
            ("shop/a/__init__.py", 1, "a", "shop.a.x"),
            ("shop/a/x.py", 2, "a", "shop.b.api"),
            ("shop/a/x.py", 3, "a", "shop.b.api"),
            ("shop/a/x.py", 4, "a", "shop.b.internals"),
            ("shop/a/x.py", 5, "a", "shop.a.helper"),
            ("shop/a/x.py", 6, "a", "shop.a.helper"),
            ("shop/a/x.py", 7, "a", "shop.c"),
            ("shop/a/x.py", 8, "a", "shop.b.api"),
            ("shop/a/x.py", 11, "a", "shop.c.api"),
        }
        assert got == want, (f"on a small test tree the extractor is wrong. Missing: {show(sorted(want - got))}. "
                             f"Unexpected: {show(sorted(got - want))}  (file, line, importer, target)")
        graph = mine.module_graph(mine.extract_imports(tmp))
        assert {k: set(v) for k, v in graph.items() if v} == {"a": {"b", "c"}}, \
            f"module_graph on the test tree should be {{'a': {{'b', 'c'}}}}, got {graph}"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    imports = mine.extract_imports(MONOLITH)
    graph = mine.module_graph(imports)
    got_edges = {k: set(v) for k, v in graph.items() if v}
    assert got_edges == MONOLITH_EDGES, (
        f"the monolith's module graph is wrong. Expected {MONOLITH_EDGES}, got {got_edges}")
    text = mine.format_graph(graph)
    assert text.strip().splitlines() == MONOLITH_GRAPH_TEXT.splitlines(), \
        f"format_graph should print one sorted line per module, like 'cart -> catalog, db'. Got:\n{text}"
    note(f"      {len(imports)} imports found in the monolith; graph:\n"
         + "\n".join("        " + line for line in text.splitlines()))


# --- Milestone 2 ---------------------------------------------------------------------
def m2():
    toy = SimpleNamespace(MODULES=["a", "b", "c"], ALLOWED={"a": ["b"], "b": [], "c": []}, PUBLIC_API="api")
    I = mine.Import
    imports = [
        I("f.py", 1, "a", "shop.b.api"),          # allowed, public
        I("f.py", 2, "a", "shop.b.service"),      # allowed, but internal
        I("f.py", 3, "a", "shop.c.api"),          # public, but a not allowed to depend on c
        I("f.py", 4, "a", "shop.c.service"),      # both
        I("f.py", 5, "b", "shop.b.service"),      # its own module: always fine
        I("f.py", 6, "a", "shop.db"),             # shared state
        I("f.py", 7, "a", "shop"),                # the bare package: not a module
        I("f.py", 8, "a", "shop.b"),              # the package, not its api
        I("f.py", 9, "zzz", "shop.c.api"),        # importer is not declared: not judged
    ]
    got = mine.check_boundaries(imports, toy)
    got_set = {(v.file, v.line, v.rule) for v in got}
    want = {("f.py", 2, "internal"), ("f.py", 3, "dependency"), ("f.py", 4, "dependency"),
            ("f.py", 4, "internal"), ("f.py", 6, "shared"), ("f.py", 8, "internal")}
    assert got_set == want and len(got) == len(want), (
        f"on the toy rules: missing {show(sorted(want - got_set))}; unexpected {show(sorted(got_set - want))}; "
        f"{len(got)} violations reported, expected {len(want)}")
    imports = mine.extract_imports(MONOLITH)
    found = mine.check_boundaries(imports, rules)
    got_set = {(norm(v.file), v.line, v.rule) for v in found}
    assert got_set == KNOWN_VIOLATIONS and len(found) == len(KNOWN_VIOLATIONS), (
        f"the monolith has exactly {len(KNOWN_VIOLATIONS)} known violations; you reported {len(found)}. "
        f"Missing: {show(sorted(KNOWN_VIOLATIONS - got_set))}. Unexpected: {show(sorted(got_set - KNOWN_VIOLATIONS))}")
    counts = {}
    for _, _, rule in got_set:
        counts[rule] = counts.get(rule, 0) + 1
    note(f"      {len(found)} violations, as expected: {dict(sorted(counts.items()))}")


# --- Milestone 3 ---------------------------------------------------------------------
def m3():
    def cycles(graph):
        return sorted(tuple(c) for c in mine.find_cycles(graph))

    assert cycles({}) == [], "an empty graph has no cycles"
    assert cycles({"a": {"b", "c"}, "b": {"c"}}) == [], "a graph with no cycle must give []"
    assert cycles({"a": {"b"}, "b": {"c"}, "c": {"a"}}) == [("a", "b", "c")], \
        "a -> b -> c -> a is one cycle, reported as ['a', 'b', 'c'] (not repeated three times, first name not repeated at the end)"
    assert cycles({"z": {"m"}, "m": {"z"}}) == [("m", "z")], "a cycle starts at its alphabetically smallest member"
    assert cycles({"a": {"b"}, "b": {"a", "c"}, "c": {"b"}}) == [("a", "b"), ("b", "c")], \
        "two cycles share the module b: report both"
    full = {"a": {"b", "c"}, "b": {"a", "c"}, "c": {"a", "b"}}
    want = [("a", "b"), ("a", "b", "c"), ("a", "c"), ("a", "c", "b"), ("b", "c")]
    assert cycles(full) == want, f"three modules that all import each other have 5 elementary cycles; got {cycles(full)}"
    graph = mine.module_graph(mine.extract_imports(MONOLITH))
    got = cycles(graph)
    assert got == MONOLITH_CYCLES, f"the monolith has the cycles {MONOLITH_CYCLES}; you found {got}"
    for c in got:
        note("      cycle: " + " -> ".join(c + (c[0],)))


# --- Milestone 4 ---------------------------------------------------------------------
def m4():
    shop = os.path.join(TARGET, "shop")
    missing = [m for m in rules.MODULES if not os.path.isfile(os.path.join(shop, m, "api.py"))]
    if len(missing) == len(rules.MODULES):
        raise NotImplementedError("TODO milestone 4: add shop/<module>/api.py for every module and route calls through it")
    assert not missing, f"these modules have no api.py yet: {', '.join(missing)}"
    code, out = run([sys.executable, os.path.join(HERE, "behaviour.py"), TARGET], HERE)
    assert code == 0, "the behaviour tests fail after your refactor:\n" + "\n".join(
        "        " + line for line in out.strip().splitlines()[-14:])
    assert not os.path.exists(os.path.join(shop, "db.py")), \
        "shop/db.py still exists: each module must own its data, so delete the shared dict"
    imports = ref.extract_imports(TARGET)
    violations = ref.check_boundaries(imports, rules)
    assert not violations, f"{len(violations)} boundary violation(s) left: " + show(
        f"{norm(v.file)}:{v.line} [{v.rule}]" for v in violations)
    cycles = ref.find_cycles(ref.module_graph(imports))
    assert not cycles, "dependency cycle(s) left: " + show(" -> ".join(c + [c[0]]) for c in cycles)
    note("      behaviour tests pass, 0 violations, 0 cycles")


# --- Milestone 5 (optional) ----------------------------------------------------------
def m5():
    test_file = os.path.join(TARGET, "test_boundaries.py")
    with open(test_file) as f:
        text = f.read()
    if "raise NotImplementedError" in text:
        raise NotImplementedError("TODO milestone 5: write the two tests in test_boundaries.py")
    if not os.path.isfile(os.path.join(TARGET, "shop", "ordering", "api.py")):
        raise AssertionError("finish milestone 4 first: the fitness function must pass on a clean shop")
    cmd = [sys.executable, "test_boundaries.py"]
    code, out = run(cmd, TARGET)
    assert code == 0, "your fitness function fails on the refactored shop:\n" + "\n".join(
        "        " + line for line in out.strip().splitlines()[-10:])
    mutations = [
        ("ordering/service.py", "\nfrom shop.payments import service as _sneaky\n", "test_no_boundary_violations",
         "an internal import (shop.payments.service) slipped into ordering and the test still passed"),
        ("catalog/api.py", "\nfrom shop.cart import api as _cart\n", "test_no_dependency_cycles",
         "catalog importing cart creates a cycle with cart -> catalog, but test_no_dependency_cycles did not fail"),
    ]
    for rel, line, must_fail, why in mutations:
        tmp = tempfile.mkdtemp()
        try:
            shutil.copytree(os.path.join(TARGET, "shop"), os.path.join(tmp, "shop"),
                            ignore=shutil.ignore_patterns("__pycache__"))
            with open(os.path.join(tmp, "shop", *rel.split("/")), "a") as f:
                f.write(line)
            code, out = run(cmd, TARGET, {"SHOP_ROOT": tmp})
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        assert code != 0 and f"FAIL: {must_fail}" in out, why
    note("      the fitness function passes on clean code and fails when a forbidden import or a cycle is added")


print(f"Lab 3 checks against {target}/\n")
check("Milestone 1: the import graph", m1)
check("Milestone 2: boundary rules and the known violations", m2)
check("Milestone 3: dependency cycles", m3)
check("Milestone 4: refactor to public APIs", m4)
check("Milestone 5 (optional): a fitness function for CI", m5)
passed = sum(results)
print(f"\n{passed}/{len(results)} milestones passing" + ("  🎉 Lab complete!" if passed == len(results) else ""))
sys.exit(0 if passed == len(results) else 1)
