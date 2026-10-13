"""Self-check for Lab 4: A Relationship-Based Authorization Engine.

    python3 check.py                  # checks your starter.py
    python3 check.py solution         # checks the reference solution
    python3 check.py solution 3       # only milestone 3

Everything is deterministic (random graphs come from a fixed seed) and runs in
one process: no network, no files. The attacks in milestone 5 are aimed only at
the deliberately vulnerable App in this lab. Prints a tick, a cross, or
"not implemented yet" for each milestone. Finishes in a couple of seconds.
"""
import importlib
import os
import random
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True

args = sys.argv[1:]
target = args[0] if args and not args[0].isdigit() else "starter"
rest = [a for a in args if a.isdigit()]
ONLY = int(rest[0]) if rest else None
mod = importlib.import_module(target)
results = []


def check(number, name, fn):
    if ONLY is not None and ONLY != number:
        return
    try:
        note = fn()
        print(f"  ✔ {name}")
        for line in (note or "").splitlines():
            print(f"      {line}")
        results.append(True)
    except NotImplementedError as e:
        print(f"  … {name}: not implemented yet ({e})")
        results.append(False)
    except AssertionError as e:
        print(f"  ✘ {name}: {e}")
        results.append(False)
    except Exception as e:
        import traceback
        tb = traceback.extract_tb(e.__traceback__)
        where = next((f"{f.name}() line {f.lineno}" for f in reversed(tb) if f.filename.endswith(f"{target}.py")), "?")
        print(f"  ✘ {name}: {type(e).__name__}: {e}   [in {where}]")
        results.append(False)


def raises(exc, fn, *a):
    try:
        fn(*a)
    except exc:
        return True
    except Exception as e:
        raise AssertionError(f"expected {exc.__name__}, got {type(e).__name__}: {e}")
    return False


# ------------------------------------------------------------------ milestone 1
def m1():
    r = mod.RBAC()
    r.grant("editor", "doc:write")
    r.grant("editor", "doc:read")
    r.grant("viewer", "doc:read")
    r.assign("alice", "editor")
    r.assign("bob", "viewer")
    r.assign("bob", "billing")           # a role that carries nothing yet
    assert r.allowed("alice", "doc:write") and r.allowed("alice", "doc:read"), "alice (editor) should read and write"
    assert r.allowed("bob", "doc:read") and not r.allowed("bob", "doc:write"), "bob (viewer) reads but must not write"
    assert not r.allowed("mallory", "doc:read"), "an unknown user must be denied"
    assert not r.allowed("alice", "doc:delete"), "an unknown permission must be denied"
    r.grant("billing", "doc:write")
    assert r.allowed("bob", "doc:write"), "permissions from ALL of a user's roles count (bob gained billing's grant)"

    def sharing(n_docs):
        shares = []
        for i in range(n_docs):
            shares.append(("alice", f"d{i}", "editor"))
            shares.append((f"user{i}", f"d{i}", "viewer"))        # each doc has its own reader
            shares.append(("bob", f"d{i}", "viewer"))
        return shares, mod.rbac_for_sharing(shares)

    shares, rb = sharing(10)
    for user, doc, level in shares:
        assert rb.allowed(user, f"read:{doc}"), f"{user} should read {doc}"
        assert rb.allowed(user, f"write:{doc}") == (level == "editor"), f"{user} write on {doc} should be {level == 'editor'}"
    assert not rb.allowed("alice", "read:d99") and not rb.allowed("user3", "read:d4"), "a share on one document must not leak to another"
    sizes = []
    for n in (10, 20, 40):
        _, rb_n = sharing(n)
        sizes.append((n,) + mod.policy_size(rb_n))
    (n1, roles1, pairs1), (n2, roles2, pairs2), (n3, roles3, pairs3) = sizes
    assert roles1 == 2 * n1 and roles3 == 4 * roles1, \
        f"expected one viewer role and one editor role per document (2n roles); got {roles1} roles for {n1} docs and {roles3} for {n3}"
    return (f"role explosion: {n1} docs -> {roles1} roles / {pairs1} role-permission pairs; {n2} docs -> {roles2}/{pairs2}; "
            f"{n3} docs -> {roles3}/{pairs3}\n"
            "the policy a reviewer must read grows with the DATA; a ReBAC schema stays the same size (milestone 3)")


# ------------------------------------------------------------------ milestone 2
def m2():
    t = mod.parse_tuple("doc:plan#editor@user:alice")
    assert (t.obj, t.rel, t.subject) == ("doc:plan", "editor", "user:alice"), f"parsed to {t!r}"
    assert str(t) == "doc:plan#editor@user:alice", "str(Tup) should round-trip"
    t2 = mod.parse_tuple("folder:q3#viewer@group:eng#member")
    assert (t2.obj, t2.rel, t2.subject) == ("folder:q3", "viewer", "group:eng#member"), f"userset subject parsed to {t2!r}"
    t3 = mod.parse_tuple("doc:d-12#owner@user:u_7")
    assert t3.obj == "doc:d-12" and t3.subject == "user:u_7"
    bad = ["", "doc:plan#editor", "doc:plan@user:alice", "doc#editor@user:alice", "doc:plan#editor@alice",
           "doc:plan#Editor@user:alice", "doc:plan#editor@user:alice#", "doc:plan #editor@user:alice",
           "doc:plan#editor@user:alice@user:bob", "doc:#editor@user:alice", "doc:plan#editor@user:alice garbage",
           "doc:plan#editor@user:alice\n", "x doc:plan#editor@user:alice"]
    for b in bad:
        assert raises(ValueError, mod.parse_tuple, b), f"parse_tuple({b!r}) should raise ValueError"

    s = mod.TupleStore()
    assert s.subjects("doc:a", "viewer") == [], "an empty store has no subjects"
    s.add("doc:a#viewer@user:bob")
    s.add(mod.parse_tuple("doc:a#viewer@user:bob"))          # same tuple again, as a Tup
    s.add("doc:a#viewer@user:amy")
    s.add("doc:a#viewer@group:g#member")
    s.add("doc:b#viewer@user:bob")
    assert len(s) == 4, f"adding the same tuple twice must change nothing; len is {len(s)}, expected 4"
    assert s.subjects("doc:a", "viewer") == ["group:g#member", "user:amy", "user:bob"], \
        f"subjects must be a sorted list, got {s.subjects('doc:a', 'viewer')!r}"
    assert mod.check_direct(s, "doc:a", "viewer", "user:bob") is True, "stored tuple: direct check should be True"
    assert mod.check_direct(s, "doc:a", "editor", "user:bob") is False, "a different relation is not granted"
    assert mod.check_direct(s, "doc:c", "viewer", "user:bob") is False, "a different object is not granted"
    s.add("group:g#member@user:carl")
    assert mod.check_direct(s, "doc:a", "viewer", "user:carl") is False, \
        "check_direct must NOT follow usersets (carl is in group g, but there is no direct tuple); that is milestone 3"
    s.remove("doc:a#viewer@user:bob")
    s.remove("doc:a#viewer@user:bob")                         # removing twice is fine
    s.remove("doc:zzz#viewer@user:nobody")                    # removing a tuple that never existed is fine
    assert mod.check_direct(s, "doc:a", "viewer", "user:bob") is False, "after remove, the direct check must be False"
    assert mod.check_direct(s, "doc:b", "viewer", "user:bob") is True, "removing doc:a's tuple must not touch doc:b's"
    return "parse (with the trailing-newline trap), idempotent add, sorted subjects, remove, direct check only"


# ------------------------------------------------------------------ milestone 3
def build(*tuples, **kw):
    store = mod.TupleStore()
    for t in tuples:
        store.add(t)
    return mod.Engine(store, **kw)


class CountingStore(mod.TupleStore):
    """Counts lookups so an exponential search cannot hide behind a fast machine."""
    def __init__(self, limit):
        super().__init__()
        self.calls, self.limit = 0, limit

    def subjects(self, obj, rel):
        self.calls += 1
        if self.calls > self.limit:
            raise AssertionError(f"more than {self.limit} store lookups for one query: the search revisits nodes "
                                 "(keep a 'seen' set of (object, relation) for the whole query)")
        return super().subjects(obj, rel)


def oracle(store, schema, users):
    """An independent fixpoint computation of who has what. Slow, simple, obviously right."""
    ids = set()
    for (o, r), subs in store._by_key.items():
        ids.add(o)
        for s in subs:
            ids.add(s.split("#")[0])
    has = defaultdict(set)
    changed = True
    while changed:
        changed = False
        for (typ, rel), rules in schema.items():
            for obj in sorted(i for i in ids if i.split(":")[0] == typ):
                new = set()
                for rule in rules:
                    if rule[0] == "this":
                        for s in store.subjects(obj, rel):
                            if "#" in s:
                                so, sr = s.split("#")
                                new |= has[(so, sr)]
                            elif s.startswith("user:"):
                                new.add(s)
                    elif rule[0] == "computed":
                        new |= has[(obj, rule[1])]
                    else:
                        for p in store.subjects(obj, rule[1]):
                            if "#" not in p:
                                new |= has[(p, rule[2])]
                if not new <= has[(obj, rel)]:
                    has[(obj, rel)] |= new
                    changed = True
    return has


def random_world(seed):
    rnd = random.Random(seed)
    users = [f"user:u{i}" for i in range(4)]
    groups = [f"group:g{i}" for i in range(3)]
    folders = [f"folder:f{i}" for i in range(3)]
    docs = [f"doc:d{i}" for i in range(3)]
    tuples = set()
    for _ in range(rnd.randint(6, 16)):
        kind = rnd.choice(["gm_user", "gm_group", "f_rel", "f_parent", "d_rel", "d_parent", "f_set", "d_set"])
        if kind == "gm_user":
            tuples.add(f"{rnd.choice(groups)}#member@{rnd.choice(users)}")
        elif kind == "gm_group":
            tuples.add(f"{rnd.choice(groups)}#member@{rnd.choice(groups)}#member")
        elif kind == "f_rel":
            tuples.add(f"{rnd.choice(folders)}#{rnd.choice(['owner', 'editor', 'viewer'])}@{rnd.choice(users)}")
        elif kind == "f_set":
            tuples.add(f"{rnd.choice(folders)}#{rnd.choice(['editor', 'viewer'])}@{rnd.choice(groups)}#member")
        elif kind == "f_parent":
            tuples.add(f"{rnd.choice(folders)}#parent@{rnd.choice(folders)}")
        elif kind == "d_rel":
            tuples.add(f"{rnd.choice(docs)}#{rnd.choice(['owner', 'editor', 'viewer'])}@{rnd.choice(users)}")
        elif kind == "d_set":
            tuples.add(f"{rnd.choice(docs)}#{rnd.choice(['editor', 'viewer'])}@{rnd.choice(groups)}#member")
        else:
            tuples.add(f"{rnd.choice(docs)}#parent@{rnd.choice(folders)}")
    store = mod.TupleStore()
    for t in sorted(tuples):
        store.add(t)
    return store, users, groups + folders + docs


def m3():
    # --- the schema's rules, one at a time
    e = build("doc:plan#owner@user:alice", "doc:plan#editor@user:bob", "doc:plan#viewer@user:carol")
    assert e.check("doc:plan", "owner", "user:alice") is True, "direct tuple"
    assert e.check("doc:plan", "viewer", "user:carol") is True, "direct viewer tuple"
    assert e.check("doc:plan", "editor", "user:alice") is True, "computed userset: owner implies editor"
    assert e.check("doc:plan", "viewer", "user:alice") is True, "computed userset: owner implies editor implies viewer (two steps)"
    assert e.check("doc:plan", "viewer", "user:bob") is True, "computed userset: editor implies viewer"
    assert e.check("doc:plan", "editor", "user:carol") is False, "the implication is one-way: viewer does NOT imply editor"
    assert e.check("doc:plan", "owner", "user:bob") is False, "editor does not imply owner"
    assert e.check("doc:plan", "viewer", "user:mallory") is False, "a stranger has nothing"
    assert e.check("doc:plan", "frobnicate", "user:alice") is False, "unknown relation: deny"
    assert e.check("widget:7", "viewer", "user:alice") is False, "unknown object type: deny"
    # --- usersets and nested groups
    e = build("folder:q3#viewer@group:eng#member", "group:eng#member@user:bob", "group:eng#member@group:interns#member",
              "group:interns#member@user:dave", "group:interns#member@group:temps#member", "group:temps#member@user:erin")
    for u, want in (("bob", True), ("dave", True), ("erin", True), ("carol", False)):
        assert e.check("folder:q3", "viewer", f"user:{u}") is want, f"folder:q3#viewer for {u} should be {want} (nested groups)"
    assert e.check("folder:q3", "editor", "user:dave") is False, "viewer-through-a-group must not become editor"
    # --- tuple-to-userset: inherit from the parent, several levels up, only the 'viewer' relation
    e = build("doc:plan#parent@folder:f1", "folder:f1#parent@folder:f2", "folder:f2#parent@folder:f3", "folder:f3#parent@folder:f4",
              "folder:f4#viewer@user:alice", "folder:f3#editor@user:bob")
    assert e.check("doc:plan", "viewer", "user:alice") is True, "viewer on a grand-grand-parent folder is viewer on the doc"
    assert e.check("doc:plan", "viewer", "user:bob") is True, "editor on a parent folder implies viewer there, which the doc inherits"
    assert e.check("doc:plan", "editor", "user:bob") is False, "only viewer is inherited, not editor"
    assert e.check("folder:f1", "viewer", "user:alice") is True, "folders inherit from their parent too"
    # --- revocation takes effect on the very next check
    e.store.remove("folder:f4#viewer@user:alice")
    assert e.check("doc:plan", "viewer", "user:alice") is False, "after removing the one tuple that granted it, access must be gone"
    # --- cycles
    e = build("group:a#member@group:b#member", "group:b#member@group:a#member", "group:b#member@user:ann",
              "folder:x#parent@folder:y", "folder:y#parent@folder:x", "folder:x#parent@folder:x",
              "folder:y#viewer@user:ann", "doc:d#parent@folder:x")
    try:
        e.check("group:a", "member", "user:ann")
    except mod.DepthExceeded:
        raise AssertionError("a cycle ran into DepthExceeded: remember every (object, relation) already visited in this query and return False when you meet one again")
    assert e.check("group:a", "member", "user:ann") is True, "ann is reachable through the a<->b cycle"
    assert e.check("group:a", "member", "user:zed") is False, "a stranger must terminate with False in a group cycle"
    assert e.check("doc:d", "viewer", "user:ann") is True, "ann reaches the doc through the folder cycle"
    assert e.check("doc:d", "viewer", "user:zed") is False, "a stranger must terminate with False in a folder cycle (including a self-parent)"
    # --- a diamond: 2^22 paths if you do not remember where you have been
    store = CountingStore(20000)
    layers = 22
    for i in range(layers):
        for a in ("a", "b"):
            for b in ("a", "b"):
                store.add(f"group:l{i}{a}#member@group:l{i + 1}{b}#member")
    store.add(f"group:l{layers}a#member@user:deep")
    eng = mod.Engine(store, max_depth=layers + 5)
    assert eng.check("group:l0a", "member", "user:deep") is True, "deep user should be found through the diamond ladder"
    store.calls = 0
    assert eng.check("group:l0a", "member", "user:nobody") is False
    # --- the depth bound, exactly: a call at depth d fails when d > max_depth; the top call is depth 0
    L = 12
    chain = [f"group:c{i}#member@group:c{i + 1}#member" for i in range(L)] + [f"group:c{L}#member@user:end"]
    assert build(*chain, max_depth=L).check("group:c0", "member", "user:end") is True, f"a chain of {L} userset hops must pass with max_depth={L}"
    assert raises(mod.DepthExceeded, build(*chain, max_depth=L - 1).check, "group:c0", "member", "user:end"), \
        f"max_depth={L - 1} must raise DepthExceeded for a chain of {L} hops (a deny, never a Python RecursionError, never True)"
    long_chain = [f"group:z{i}#member@group:z{i + 1}#member" for i in range(3000)]
    assert raises(mod.DepthExceeded, build(*long_chain).check, "group:z0", "member", "user:x"), \
        "a 3000-hop chain with the default max_depth must raise DepthExceeded, not blow the Python stack"
    # --- against the oracle on 150 random worlds
    n_true = n_total = 0
    for seed in range(150):
        store, users, objs = random_world(seed)
        eng = mod.Engine(store, max_depth=64)
        truth = oracle(store, eng.schema, users)
        for o in objs:
            for rel in ("owner", "editor", "viewer", "member", "parent"):
                for u in users:
                    want = u in truth[(o, rel)]
                    got = eng.check(o, rel, u)
                    n_total += 1
                    n_true += want
                    assert got is want, (f"seed {seed}: check({o}, {rel}, {u}) returned {got}, the oracle says {want}.\n"
                                         f"        tuples: {sorted(str(t) for t in tuples_of(store))}")
    return f"every rule, cycles, the 22-layer diamond, depth bound, and {n_total} random queries ({n_true} granted) agree with an independent oracle"


def tuples_of(store):
    return [mod.Tup(o, r, s) for (o, r), subs in sorted(store._by_key.items()) for s in sorted(subs)]


# ------------------------------------------------------------------ milestone 4
def parse_step(step):
    kind, _, rest = step.partition(" ")
    if kind == "tuple":
        t = mod.parse_tuple(rest)
        return kind, f"{t.obj}#{t.rel}", None, rest
    left, sep, right = rest.partition(" => ")
    assert sep, f"step {step!r} is not 'kind SOURCE => TARGET [via TUPLE]'"
    tgt, _, via = right.partition(" via ")
    return kind, left, tgt, via or None


def validate_path(eng, obj, rel, user, path):
    assert isinstance(path, list) and path, f"explain must return a non-empty list, got {path!r}"
    expect_src = f"{obj}#{rel}"
    for i, step in enumerate(path):
        kind, src, tgt, via = parse_step(step)
        assert src == expect_src, f"step {i} ({step!r}) starts at {src}, but the previous step ended at {expect_src}"
        if kind == "tuple":
            assert i == len(path) - 1, "a 'tuple' step must be the last step"
            assert via.endswith("@" + user), f"the last step must name {user}: {step!r}"
            t = mod.parse_tuple(via)
            assert t.subject in eng.store.subjects(t.obj, t.rel), f"{via} is not a stored tuple"
        else:
            assert i < len(path) - 1, "the last step must be a 'tuple' step"
            if kind in ("ttu", "userset"):
                t = mod.parse_tuple(via)
                assert t.subject in eng.store.subjects(t.obj, t.rel), f"step {step!r} cites {via}, which is not a stored tuple"
            else:
                assert via is None, "computed steps cite no tuple"
            expect_src = tgt
    return len(path)


def m4():
    e = build("doc:plan#parent@folder:q3", "folder:q3#viewer@group:eng#member", "group:eng#member@user:bob",
              "group:eng#member@group:interns#member", "group:interns#member@user:dave", "doc:plan#editor@user:alice")
    path = e.explain("doc:plan", "viewer", "user:dave")
    expected = ["ttu doc:plan#viewer => folder:q3#viewer via doc:plan#parent@folder:q3",
                "userset folder:q3#viewer => group:eng#member via folder:q3#viewer@group:eng#member",
                "userset group:eng#member => group:interns#member via group:eng#member@group:interns#member",
                "tuple group:interns#member@user:dave"]
    assert path == expected, "path for dave should be (it is the only path):\n        " + "\n        ".join(expected) + f"\n      got: {path!r}"
    p2 = e.explain("doc:plan", "viewer", "user:alice")
    assert p2 == ["computed doc:plan#viewer => doc:plan#editor", "tuple doc:plan#editor@user:alice"], f"alice's path: {p2!r}"
    assert e.explain("doc:plan", "editor", "user:bob") is None, "bob is only a viewer: no path to editor"
    assert e.explain("doc:plan", "viewer", "user:mallory") is None, "no path means None"
    assert e.who_can("doc:plan", "viewer") == ["user:alice", "user:bob", "user:dave"], f"who_can viewer: {e.who_can('doc:plan', 'viewer')!r}"
    assert e.who_can("doc:plan", "editor") == ["user:alice"], f"who_can editor: {e.who_can('doc:plan', 'editor')!r}"
    e.store.remove("group:eng#member@group:interns#member")
    assert e.explain("doc:plan", "viewer", "user:dave") is None, "after removing the nesting tuple, dave has no path"
    assert e.who_can("doc:plan", "viewer") == ["user:alice", "user:bob"], "and who_can no longer lists dave"
    # the guards still hold
    store = CountingStore(20000)
    for i in range(22):
        for a in ("a", "b"):
            for b in ("a", "b"):
                store.add(f"group:l{i}{a}#member@group:l{i + 1}{b}#member")
    store.add("group:l22a#member@user:deep")
    eng = mod.Engine(store, max_depth=30)
    assert eng.explain("group:l0a", "member", "user:deep") is not None, "explain through the diamond ladder"
    assert eng.explain("group:l0a", "member", "user:nobody") is None
    assert eng.who_can("group:l0a", "member") == ["user:deep"], "who_can through the diamond ladder"
    long_chain = [f"group:z{i}#member@group:z{i + 1}#member" for i in range(3000)]
    assert raises(mod.DepthExceeded, build(*long_chain).explain, "group:z0", "member", "user:x"), "explain must honour max_depth"
    assert raises(mod.DepthExceeded, build(*long_chain).who_can, "group:z0", "member"), "who_can must honour max_depth"
    cyc = build("group:a#member@group:b#member", "group:b#member@group:a#member", "group:a#member@user:ann")
    assert cyc.who_can("group:b", "member") == ["user:ann"] and cyc.explain("group:b", "member", "user:ann") is not None, "cycles: terminate and still find ann"
    # random worlds: explain agrees with check and the oracle, every path is valid, who_can equals the oracle
    steps = granted = 0
    for seed in range(150):
        store, users, objs = random_world(seed)
        eng = mod.Engine(store, max_depth=64)
        truth = oracle(store, eng.schema, users)
        for o in objs:
            for rel in ("owner", "editor", "viewer", "member"):
                want_users = sorted(truth[(o, rel)])
                got_users = eng.who_can(o, rel)
                assert got_users == want_users, f"seed {seed}: who_can({o}, {rel}) = {got_users}, the oracle says {want_users}"
                for u in users:
                    p = eng.explain(o, rel, u)
                    assert (p is not None) == (u in truth[(o, rel)]), f"seed {seed}: explain({o}, {rel}, {u}) = {p!r} but the oracle says {u in truth[(o, rel)]}"
                    if p is not None:
                        steps += validate_path(eng, o, rel, u, p)
                        granted += 1
    return (f"exact path for dave:\n" + "\n".join("  " + s for s in expected) +
            f"\n{granted} random grants explained ({steps} steps, each citing a stored tuple); who_can matches the oracle everywhere")


# ------------------------------------------------------------------ milestone 5
ACCESS = ()


def world(app_cls):
    global ACCESS
    ACCESS = (mod.Forbidden, mod.NotFound)
    app = app_cls()
    for u, t in (("alice", "acme"), ("bob", "acme"), ("carol", "acme"), ("mallory", "globex"), ("gina", "globex")):
        app.register(u, t)
    P = {u: mod.Principal(u, t) for u, t in app.user_tenant.items()}
    ids = {}
    ids["f1"] = app.create_folder(P["alice"], "board")
    ids["d1"] = app.create_doc(P["alice"], "salaries", "alice's private salary table")        # private to alice
    ids["d2"] = app.create_doc(P["alice"], "roadmap", "the roadmap")                          # alice owns, bob views
    app.share(P["alice"], ids["d2"], "bob", "viewer")
    ids["d3"] = app.create_doc(P["gina"], "globex plan", "globex secret")                     # another tenant
    ids["d4"] = app.create_doc(P["alice"], "minutes", "board minutes", folder=ids["f1"])      # in alice's folder
    app.store.add(f"folder:{ids['f1']}#viewer@user:bob")                                      # bob may view the folder
    return app, P, ids


def attacks():
    """(name, function(app, P, ids) -> True if the attack SUCCEEDED)."""
    def lands(fn):
        def run(app, P, ids):
            try:
                fn(app, P, ids)
            except ACCESS:
                return False
            return True
        return run

    def inject_then_read(app, P, ids):
        app.store.add(f"doc:{ids['d1']}#viewer@user:mallory")        # a bad tuple appears (bug, import, admin slip)
        return app.read_doc(P["mallory"], ids["d1"])

    def list_leaks(who, forbidden):
        def run(app, P, ids):
            return bool(set(app.list_docs(P[who])) & {ids[x] for x in forbidden})
        return run

    def existence_oracle(app, P, ids):
        def probe(i):
            try:
                app.read_doc(P["mallory"], i)
                return ("OK",)
            except Exception as e:
                return (type(e).__name__, str(e).replace(i, "<id>"))
        return probe(ids["d1"]) != probe("d999")

    return [
        ("cross-tenant read of another tenant's document", lands(lambda a, P, i: a.read_doc(P["mallory"], i["d1"]))),
        ("cross-tenant read of a document shared inside the other tenant", lands(lambda a, P, i: a.read_doc(P["mallory"], i["d2"]))),
        ("cross-tenant update", lands(lambda a, P, i: a.update_doc(P["mallory"], i["d1"], "pwned"))),
        ("cross-tenant delete", lands(lambda a, P, i: a.delete_doc(P["mallory"], i["d1"]))),
        ("cross-tenant self-grant (share d1 with myself)", lands(lambda a, P, i: a.share(P["mallory"], i["d1"], "mallory", "editor"))),
        ("a stray tuple names a user of another tenant", lands(inject_then_read)),
        ("owner shares with a user of another tenant", lands(lambda a, P, i: a.share(P["alice"], i["d1"], "mallory", "viewer"))),
        ("same-tenant stranger reads a private document", lands(lambda a, P, i: a.read_doc(P["carol"], i["d1"]))),
        ("same-tenant stranger reads a document shared with someone else", lands(lambda a, P, i: a.read_doc(P["carol"], i["d2"]))),
        ("viewer updates", lands(lambda a, P, i: a.update_doc(P["bob"], i["d2"], "defaced"))),
        ("viewer deletes", lands(lambda a, P, i: a.delete_doc(P["bob"], i["d2"]))),
        ("viewer shares (not the owner)", lands(lambda a, P, i: a.share(P["bob"], i["d2"], "carol", "viewer"))),
        ("folder viewer edits an inherited document", lands(lambda a, P, i: a.update_doc(P["bob"], i["d4"], "defaced"))),
        ("list leaks other users' documents", list_leaks("carol", ["d1", "d2", "d4"])),
        ("list leaks another tenant's documents", list_leaks("mallory", ["d1", "d2", "d4"])),
        ("existence oracle: 'forbidden' vs 'no such id'", existence_oracle),
    ]


def m5():
    app, P, ids = world(mod.App)
    # The choke point must exist before anything else can be judged.
    path = app.require(P["alice"], ids["d1"], "read")
    assert isinstance(path, list) and path, "require() should return the path that allowed the access"
    # 1. The attack suite is real: with require() and can() switched off, every attack lands.
    Vuln = type("Vuln", (mod.App,), {"require": lambda self, *a, **k: None, "can": lambda self, *a, **k: True})
    landed = []
    for name, fn in attacks():
        v_app, vP, vids = world(Vuln)
        if fn(v_app, vP, vids):
            landed.append(name)
    all_names = [name for name, _ in attacks()]
    assert len(landed) == len(all_names), "internal: with the checks off, every attack should land; missing: " + "; ".join(sorted(set(all_names) - set(landed)))
    # 2. Against the real handlers, none may land (each attack gets a fresh world).
    still = []
    for name, fn in attacks():
        app, P, ids = world(mod.App)
        try:
            ok = fn(app, P, ids)
        except Exception as e:
            raise AssertionError(f"attack {name!r} raised {type(e).__name__}: {e} (a denial must be NotFound or Forbidden)")
        if ok:
            still.append(name)
    assert not still, (f"{len(still)} of {len(all_names)} attacks still succeed. Is every handler routed through require()/can()?\n"
                       + "".join(f"        - {n}\n" for n in still).rstrip())
    # 3. Legitimate use still works.
    app, P, ids = world(mod.App)
    d1, d2, d3, d4 = ids["d1"], ids["d2"], ids["d3"], ids["d4"]
    assert app.read_doc(P["alice"], d1)["body"] == "alice's private salary table", "owner must read own document"
    app.update_doc(P["alice"], d1, "revised")
    assert app.read_doc(P["alice"], d1)["body"] == "revised", "owner must update own document"
    assert app.read_doc(P["bob"], d2)["title"] == "roadmap", "a shared viewer reads"
    assert app.read_doc(P["bob"], d4)["title"] == "minutes", "folder viewer reads a document inherited from the folder"
    assert app.list_docs(P["bob"]) == [d2, d4], f"bob should list exactly his documents, got {app.list_docs(P['bob'])}"
    assert app.list_docs(P["alice"]) == [d1, d2, d4] and app.list_docs(P["gina"]) == [d3], "each owner lists their own"
    app.share(P["alice"], d2, "carol", "editor")
    app.update_doc(P["carol"], d2, "carol was here")
    assert app.read_doc(P["alice"], d2)["body"] == "carol was here", "an editor can update"
    assert app.read_doc(P["gina"], d3)["body"] == "globex secret", "another tenant's owner reads their own"
    app.store.remove(f"folder:{ids['f1']}#viewer@user:bob")
    assert raises(mod.NotFound, app.read_doc, P["bob"], d4), "revoking the folder tuple must remove bob's access at once"
    app.delete_doc(P["alice"], d2)
    assert raises(mod.NotFound, app.read_doc, P["alice"], d2), "a deleted document is gone"
    # 4. Audit.
    allowed = [a for a in app.audit if a["allowed"]]
    denied = [a for a in app.audit if not a["allowed"]]
    assert allowed and all(a["via"] and a["via"][-1].startswith("tuple ") for a in allowed), "each allowed decision records the path that granted it"
    assert denied and all(a["via"] is None for a in denied), "each denied decision is logged too, with no path"
    assert {"user", "tenant", "action", "doc", "allowed", "via"} <= set(app.audit[0]), f"audit entry fields: {sorted(app.audit[0])}"
    return (f"{len(all_names)} attacks (cross-tenant, cross-user, enumeration): all {len(landed)} land with the checks off, 0 with them on\n"
            f"legitimate use unchanged; {len(app.audit)} audit entries ({len(allowed)} allowed with a path, {len(denied)} denied)")


print(f"Lab 4 checks against {target}.py\n")
check(1, "Milestone 1: RBAC, and role explosion shown with a test", m1)
check(2, "Milestone 2: relation tuples and a direct check", m2)
check(3, "Milestone 3: userset rewrites, bounded depth, cycle safety", m3)
check(4, "Milestone 4: explain and expand for audit", m4)
check(5, "Milestone 5: fix the IDOR; every access goes through check", m5)
print(f"\n{sum(results)}/{len(results)} milestones passing")
sys.exit(0 if all(results) else 1)
