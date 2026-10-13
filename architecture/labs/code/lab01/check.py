"""Self-check for Lab 1: Refactor to Hexagonal.

    python3 check.py              # checks the files in starter/
    python3 check.py solution     # checks the reference answer in solution/

Everything runs in-process on in-memory sqlite and fakes: no network, no threads, no
timing. Same result every run, about a second. Prints a tick, a cross, or "not
implemented yet" for each milestone. Milestone 6 is optional.
"""
import ast
import importlib
import io
import json
import os
import sqlite3
import sys
import types
import unittest

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
target = sys.argv[1] if len(sys.argv) > 1 else "starter"
if target not in ("starter", "solution"):
    sys.exit("usage: python3 check.py [starter|solution]")
TARGET = os.path.join(HERE, target)
sys.path.insert(0, HERE)
sys.path.insert(0, TARGET)          # so the refactored modules can say: import domain

import harness                      # noqa: E402  (given)
import legacy                       # noqa: E402  (given)
from contract import make_contract  # noqa: E402
from domain_tests import make_tests  # noqa: E402

with open(harness.GOLDEN) as f:
    GOLDEN = json.load(f)
REQS = harness.requests()
results = {}


# ---- helpers -------------------------------------------------------------------------
def load(name):
    return importlib.import_module(name)


def imports_of(path):
    """Top-level module names imported by a Python file, found with ast (no execution)."""
    with open(path) as f:
        tree = ast.parse(f.read(), path)
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            found.add(("." * node.level) + (node.module or "").split(".")[0])
    return found


def forbid(path, banned, why):
    bad = sorted(i for i in imports_of(path) if i.lstrip(".") in banned)
    if bad:
        raise AssertionError("%s imports %s. %s" % (os.path.relpath(path, HERE), ", ".join(bad), why))


def allow_only(path, allowed, why):
    bad = sorted(i for i in imports_of(path) if i.lstrip(".") not in allowed)
    if bad:
        raise AssertionError("%s imports %s. %s Allowed: %s." % (
            os.path.relpath(path, HERE), ", ".join(bad), why, ", ".join(sorted(allowed))))


def run_suite(suite):
    """Run a unittest suite quietly; turn the outcome into the exceptions check() understands."""
    res = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
    problems = res.failures + res.errors
    if not problems:
        return res.testsRun
    real = [p for p in problems if "NotImplementedError" not in p[1]]
    if not real:
        line = [l for l in problems[0][1].splitlines() if "NotImplementedError" in l][-1]
        raise NotImplementedError(line.split("NotImplementedError:", 1)[-1].strip())
    test, tb = real[0]
    raise AssertionError("%d of %d tests failed. First: %s\n        %s" % (
        len(problems), res.testsRun, test.id().split(".")[-1], tb.strip().splitlines()[-1]))


class Stack:
    """The refactored app wired up with a given repository and fresh fakes."""

    def __init__(self, repo):
        app, http = load("app"), load("adapters.http_handler")
        fake_pay, fake_mail = load("adapters.fake_payment"), load("adapters.fake_email")
        self.repo, self.pay, self.mail = repo, fake_pay.FakePayment(), fake_mail.FakeEmail()
        self.handle = http.build_handler(app.PlaceOrder(repo, self.pay, self.mail), app.GetOrder(repo))

    def stock(self):
        return {sku: self.repo.get_product(sku).stock for sku, _, _ in harness.PRODUCTS}


def memory_repo(products):
    repo = load("adapters.memory_repo").InMemoryRepo()
    for p in products:
        repo.add_product(p)
    return repo


def sqlite_repo(products):
    repo = load("adapters.sqlite_repo").SqliteRepo(sqlite3.connect(":memory:"))
    for p in products:
        repo.add_product(p)
    return repo


def seeded(factory):
    domain = load("domain")
    return Stack(factory([domain.Product(*p) for p in harness.PRODUCTS]))


def replay(stack, reqs):
    return harness.record(stack.handle, reqs, lambda: stack.pay.charges, lambda: stack.mail.sent, stack.stock)


# ---- milestones ----------------------------------------------------------------------
def m1():
    got = harness.run_legacy()
    diff = harness.first_difference(GOLDEN, got)
    assert diff is None, "legacy.py no longer matches golden.json (did you edit legacy.py?)\n    " + str(diff)
    codes = {s for s, _ in got["responses"]}
    assert {200, 201, 400, 402, 404, 405, 409, 422} <= codes, "scenario lost a status code: %s" % sorted(codes)
    assert {"PAID", "ON_HOLD"} <= {b.get("status") for s, b in got["responses"] if s == 201}
    # Does the safety net actually catch a changed rule? Mutate the bulk discount and replay.
    with open(os.path.join(HERE, "legacy.py")) as f:
        src = f.read()
    assert "(q * p) * 10 // 100" in src
    mutant = types.ModuleType("legacy_mutant")
    exec(compile(src.replace("(q * p) * 10 // 100", "(q * p) * 15 // 100"), "legacy_mutant", "exec"), mutant.__dict__)
    assert harness.first_difference(GOLDEN, harness.run_legacy(legacy=mutant)) is not None, \
        "the harness failed to notice a changed discount rule"
    cases = load("my_cases").CASES
    if not cases:
        raise NotImplementedError("TODO milestone 1: add at least 3 requests to my_cases.py")
    assert len(cases) >= 3, "my_cases.CASES has %d requests, need at least 3" % len(cases)
    for c in cases:
        assert isinstance(c, dict) and {"method", "path"} <= set(c), "each case needs 'method' and 'path': %r" % (c,)
    out = harness.run_legacy(cases)
    assert all(isinstance(s, int) for s, _ in out["responses"])
    assert len({json.dumps(r, sort_keys=True) for r in out["responses"]}) >= 3, \
        "your cases should produce at least 3 different responses (vary them!)"


def m2():
    domain = load("domain")
    forbid(os.path.join(TARGET, "domain.py"),
           {"sqlite3", "json", "http", "urllib", "socket", "os", "sys", "subprocess", "smtplib", "re",
            "adapters", "app", "ports", "legacy", "harness"},
           "The domain must be pure: no I/O libraries, no outer layers.")
    run_suite(make_tests(domain))


def m3():
    domain, ports, app = load("domain"), load("ports"), load("app")
    for name, methods in (("OrderRepository", ["get_product", "save_order", "get_order"]),
                          ("PaymentGateway", ["charge"]), ("EmailSender", ["send"])):
        assert hasattr(ports, name), "ports.py needs a Protocol called %s" % name
        for m in methods:
            assert hasattr(getattr(ports, name), m), "%s needs a method %s" % (name, m)
    allow_only(os.path.join(TARGET, "app.py"), {"__future__", "dataclasses", "typing", "domain", "ports"},
               "The use case may depend on the domain and the ports, never on an adapter or a library.")
    allow_only(os.path.join(TARGET, "ports.py"), {"__future__", "typing", "domain", "dataclasses"},
               "Ports describe what the core needs; they import only domain types.")

    class Repo:                      # tiny stand-ins defined HERE, to prove app.py needs nothing else
        def __init__(self):
            self.p = {"mug": domain.Product("mug", 1500, 10), "desk": domain.Product("desk", 45000, 5)}
            self.saved, self.log = [], None

        def get_product(self, sku):
            return self.p.get(sku)

        def save_order(self, order):
            self.saved.append(order)
            return len(self.saved)

        def get_order(self, oid):
            return self.saved[oid - 1] if 1 <= oid <= len(self.saved) else None

    class Pay:
        def __init__(self, ok=True):
            self.calls, self.ok = [], ok

        def charge(self, customer, cents, card):
            self.calls.append((customer, cents, card))
            return self.ok

    class Mail:
        def __init__(self):
            self.sent = []

        def send(self, to, subject, body):
            self.sent.append((to, subject, body))

    def request(sku="mug", qty=2, **kw):
        return domain.OrderRequest("ana@example.com", ((sku, qty),), **kw)

    repo, pay, mail = Repo(), Pay(), Mail()
    order = app.PlaceOrder(repo, pay, mail).execute(request())
    assert (order.id, order.status, order.total_cents) == (1, "PAID", 3499), "got %r" % (order,)
    assert pay.calls == [("ana@example.com", 3499, "tok_ok")], "the gateway should be charged once: %r" % pay.calls
    assert mail.sent == [("ana@example.com", "Order #1 confirmed", "Thanks ana@example.com! We charged 34.99.")]
    assert app.GetOrder(repo).execute(1) == repo.saved[0]
    try:
        app.GetOrder(repo).execute(9)
        raise AssertionError("GetOrder must raise domain.OrderNotFound for a missing order")
    except domain.OrderNotFound:
        pass
    repo, pay, mail = Repo(), Pay(ok=False), Mail()
    try:
        app.PlaceOrder(repo, pay, mail).execute(request())
        raise AssertionError("a declined card must raise domain.PaymentDeclined")
    except domain.PaymentDeclined:
        pass
    assert repo.saved == [] and mail.sent == [], "a declined payment must save nothing and send nothing"
    repo, pay, mail = Repo(), Pay(), Mail()
    held = app.PlaceOrder(repo, pay, mail).execute(request("desk", 2))
    assert held.status == "ON_HOLD" and pay.calls == [], "held orders are saved but not charged"
    assert mail.sent[0][1] == "Order #1 is on hold"
    for bad, exc in ((request("ghost", 1), domain.UnknownSku), (request("desk", 6), domain.OutOfStock)):
        try:
            app.PlaceOrder(Repo(), Pay(), Mail()).execute(bad)
            raise AssertionError("expected %s" % exc.__name__)
        except exc:
            pass


def m4():
    domain = load("domain")
    sqlite_file = os.path.join(TARGET, "adapters", "sqlite_repo.py")
    suite = unittest.TestSuite()
    for label, factory in (("memory", memory_repo), ("sqlite", sqlite_repo)):
        cls = make_contract(domain, factory, label)
        suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(cls))
    run_suite(suite)
    for name in sorted(os.listdir(TARGET)):
        path = os.path.join(TARGET, name)
        if name.endswith(".py"):
            forbid(path, {"sqlite3"}, "All SQL belongs in adapters/sqlite_repo.py.")
    for name in sorted(os.listdir(os.path.join(TARGET, "adapters"))):
        if name.endswith(".py") and name != "sqlite_repo.py":
            forbid(os.path.join(TARGET, "adapters", name), {"sqlite3"}, "All SQL belongs in adapters/sqlite_repo.py.")
    assert "sqlite3" not in imports_of(os.path.join(TARGET, "adapters", "memory_repo.py"))
    assert os.path.exists(sqlite_file)


def m5():
    cases = load("my_cases").CASES
    allow_http = {"__future__", "json", "re", "domain", "typing"}
    allow_only(os.path.join(TARGET, "adapters", "http_handler.py"), allow_http,
               "The HTTP adapter talks to the use cases and the domain only; it never touches another adapter or SQL.")
    for label, factory in (("in-memory", memory_repo), ("sqlite", sqlite_repo)):
        got = replay(seeded(factory), REQS)
        diff = harness.first_difference(GOLDEN, got)
        assert diff is None, "with the %s repository the behaviour differs from legacy.py:\n    %s" % (label, diff)
        want = harness.run_legacy(cases)
        mine = replay(seeded(factory), cases)
        diff = harness.first_difference(want, mine, cases)
        assert diff is None, "your own my_cases.py differ (%s repo):\n    %s" % (label, diff)


def m6():
    if not results.get(5):
        raise NotImplementedError("finish milestone 5 first")
    domain = load("domain")
    if not hasattr(domain, "GIFT_CARDS"):
        raise NotImplementedError("TODO milestone 6: domain.GIFT_CARDS and the pricing rule")
    body = json.dumps({"customer": "ana@example.com", "items": [{"sku": "mug", "qty": 2}]})
    plain = {"method": "POST", "path": "/orders", "body": body}
    gifted = dict(plain, headers={"X-Gift-Card": "GIFT20"})
    big = dict(plain, headers={"X-Gift-Card": "GIFT100"})
    bad = dict(plain, headers={"X-Gift-Card": "NOPE"})
    for label, factory in (("in-memory", memory_repo), ("sqlite", sqlite_repo)):
        st = seeded(factory)
        assert st.handle(plain) == (201, {"id": 1, "status": "PAID", "total_cents": 3499}), "plain orders must not change"
        s, b = st.handle(gifted)
        if (s, b.get("total_cents")) == (201, 3499):
            raise NotImplementedError("the X-Gift-Card header is ignored so far")
        assert (s, b) == (201, {"id": 2, "status": "PAID", "total_cents": 3499 - 2000}), "GIFT20 should reduce 34.99 to 14.99, got %s %s" % (s, b)
        s, b = st.handle(big)
        assert (s, b["total_cents"]) == (201, 0), "a gift card bigger than the total brings it to 0, never below, got %s %s" % (s, b)
        assert st.pay.charges[-2:] == [("ana@example.com", 1499), ("ana@example.com", 0)], st.pay.charges
        assert st.handle(bad) == (422, {"error": "unknown gift card 'NOPE'"})
        assert st.stock()["mug"] == 40 - 6, "rejected requests must not touch stock"
        assert st.mail.sent[-1][1] == "Order #3 confirmed"


MILESTONES = [
    (1, "Milestone 1: characterisation tests (legacy.py recorded)", m1),
    (2, "Milestone 2: pure domain.py", m2),
    (3, "Milestone 3: ports.py and the app.py use case", m3),
    (4, "Milestone 4: repositories pass one contract", m4),
    (5, "Milestone 5: HTTP wiring matches legacy, both repos", m5),
    (6, "Milestone 6 (optional): gift cards", m6),
]

print("Lab 1 checks against %s/\n" % target)
for n, name, fn in MILESTONES:
    # a later milestone is meaningless until the earlier ones' files exist; each check
    # imports only what it needs, so failures stay local.
    try:
        fn()
        print("  ✔ " + name)
        results[n] = True
    except NotImplementedError as e:
        print("  … %s: not implemented yet (%s)" % (name, e))
        results[n] = False
    except AssertionError as e:
        print("  ✘ %s: %s" % (name, e))
        results[n] = False
    except Exception as e:                      # a crash in your code is a failed check, not a crash of the checker
        print("  ✘ %s: %s: %s" % (name, type(e).__name__, e))
        results[n] = False

passed = sum(results.values())
required = all(results[n] for n in range(1, 6))
print("\n%d/6 milestones passing%s" % (passed, "" if results[6] else " (milestone 6 is optional)"))
sys.exit(0 if required else 1)
