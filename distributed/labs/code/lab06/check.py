"""Self-check for Lab 6: CRDTs That Converge.

    python3 check.py                          # checks your starter.py
    python3 check.py solution                 # checks the reference solution
    python3 check.py solution --kind orset --seed 17    # replay one random schedule and shrink it

Everything is in-process and seeded: no network, no threads, no clocks.  Replicas, "messages in
flight" (snapshots of a replica's state), duplicated and reordered deliveries are all simulated.
A property failure prints the seed and a MINIMAL list of operations that still fails (a
delta-debugging shrinker removes operations while the failure persists).  Whole check: a few seconds.
"""
import importlib
import os
import random
import signal
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

args = sys.argv[1:]
opt = lambda name: args[args.index(name) + 1] if name in args else None
replay_seed = int(opt("--seed")) if opt("--seed") else None
replay_kind = opt("--kind")
pos = [a for i, a in enumerate(args) if not a.startswith("--") and not (i and args[i - 1] in ("--seed", "--kind"))]
target = pos[0] if pos else "starter"
if target not in ("starter", "solution"):
    sys.exit("usage: python3 check.py [starter|solution] [--kind K --seed N]")
mod = importlib.import_module(target)

SEEDS = 300
results, notes = [], []


# ---------------------------------------------------------------------------------------------
# One spec per type: how to make a replica, how to generate / apply an operation, and the ORACLE:
# what the converged value must be, computed from the operations alone (no CRDT involved).
# ---------------------------------------------------------------------------------------------
def dominated_writes(ev):
    """ev = [(value, vv)]: the writes not strictly below another write's version vector."""
    keep = []
    for i, (v, vv) in enumerate(ev):
        if not any(j != i and mod.vv_leq(vv, w) and vv != w for j, (_, w) in enumerate(ev)):
            keep.append(v)
    return sorted(set(keep), key=repr)


def lww_winner(ev):
    return max(ev, key=lambda e: e[0])[1] if ev else None


SPECS = {}


def spec(name, make, gen, apply, oracle, view):
    SPECS[name] = dict(name=name, make=make, gen=gen, apply=apply, oracle=oracle, view=view)


# counters
spec("gcounter", lambda rid: mod.GCounter(rid),
     lambda rng: ("inc", rng.randint(1, 3)),
     lambda r, op, ev: (r.increment(op[1]), ev.append(op[1])),
     lambda ev: sum(ev), lambda r: r.value())


def pn_apply(r, op, ev):
    (r.increment if op[0] == "inc" else r.decrement)(op[1])
    ev.append(op[1] if op[0] == "inc" else -op[1])


spec("pncounter", lambda rid: mod.PNCounter(rid),
     lambda rng: (rng.choice(["inc", "dec"]), rng.randint(1, 3)),
     pn_apply, lambda ev: sum(ev), lambda r: r.value())

# registers.  The timestamps come from a tiny range on purpose, so ties are common.
spec("lww", lambda rid: mod.LWWRegister(rid),
     lambda rng: ("set", f"v{rng.randint(0, 9)}", rng.randint(0, 4)),
     lambda r, op, ev: ev.append((r.set(op[1], op[2]), op[1])),
     lambda ev: lww_winner(ev), lambda r: r.value())

spec("mvregister", lambda rid: mod.MVRegister(rid),
     lambda rng: ("set", rng.choice("abcd")),
     lambda r, op, ev: ev.append((op[1], r.set(op[1]))),
     dominated_writes, lambda r: r.value())


# sets
def orset_apply(r, op, ev):
    if op[0] == "add":
        ev.append(("add", op[1], r.add(op[1])))
    else:
        ev.append(("rem", r.remove(op[1])))


def orset_oracle(ev):
    removed = set()
    for e in ev:
        if e[0] == "rem":
            removed |= set(e[1])
    return {el for k, el, *rest in [x for x in ev if x[0] == "add"] for tag in rest if tag not in removed}


spec("orset", lambda rid: mod.ORSet(rid),
     lambda rng: (rng.choice(["add", "add", "remove"]), rng.choice("xyz")),
     orset_apply, orset_oracle, lambda r: r.value())


def twop_apply(r, op, ev):
    if op[0] == "add":
        r.add(op[1])
        ev.append(("add", op[1]))
    elif r.remove(op[1]):
        ev.append(("rem", op[1]))


spec("twopset", lambda rid: mod.TwoPSet(rid),
     lambda rng: (rng.choice(["add", "add", "remove"]), rng.choice("xyz")),
     twop_apply,
     lambda ev: {e[1] for e in ev if e[0] == "add"} - {e[1] for e in ev if e[0] == "rem"},
     lambda r: r.value())


# the application
def cart_apply(r, op, ev):
    k = op[0]
    if k == "add":
        ev.append(("add", op[1], op[2], r.add_item(op[1], op[2])))
    elif k == "remove":
        ev.append(("rem", r.remove_item(op[1])))
    elif k == "addr":
        ev.append(("addr", r.set_address(op[1], op[2]), op[1]))
    else:
        ev.append(("note", r.set_note(op[1])))
        ev[-1] = ("note", op[1], ev[-1][1])


def cart_oracle(ev):
    removed = set()
    for e in ev:
        if e[0] == "rem":
            removed |= set(e[1])
    items = {}
    for e in ev:
        if e[0] == "add" and e[3] not in removed:
            items[e[1]] = items.get(e[1], 0) + e[2]
    return {"items": items,
            "address": lww_winner([(e[1], e[2]) for e in ev if e[0] == "addr"]),
            "note": dominated_writes([(e[1], e[2]) for e in ev if e[0] == "note"])}


spec("cart", lambda rid: mod.Cart(rid),
     lambda rng: rng.choice([("add", rng.choice(["pen", "ink", "pad"]), rng.randint(1, 3))] * 3
                            + [("remove", rng.choice(["pen", "ink", "pad"]))] * 2
                            + [("addr", rng.choice(["home", "work", "gran"]), rng.randint(0, 4)),
                               ("note", rng.choice(["hi", "bye", "ta"]))]),
     cart_apply, cart_oracle, lambda r: r.value())


# ---------------------------------------------------------------------------------------------
# Running one schedule
# ---------------------------------------------------------------------------------------------
def show(x, n=140):
    s = repr(x)
    return s if len(s) <= n else s[:n] + "..."


def laws(pool, rng):
    for _ in range(12):
        a, b, c = (rng.choice(pool) for _ in range(3))
        sa, sb, sc = a.state(), b.state(), c.state()
        ab, ba = a.merge(b), b.merge(a)
        assert a.state() == sa and b.state() == sb, "merge changed one of its inputs: it must return a NEW replica"
        assert ab.state() == ba.state(), f"merge is not commutative:\n        a.merge(b) = {show(ab.state())}\n        b.merge(a) = {show(ba.state())}\n        a = {show(sa)}\n        b = {show(sb)}"
        l, r = ab.merge(c).state(), a.merge(b.merge(c)).state()
        assert l == r, f"merge is not associative:\n        (a.merge(b)).merge(c) = {show(l)}\n        a.merge(b.merge(c)) = {show(r)}"
        assert a.merge(a).state() == sa, f"merge is not idempotent: a.merge(a) = {show(a.merge(a).state())} but a = {show(sa)}"
        assert ab.merge(a).state() == ab.state() and ab.merge(b).state() == ab.state(), \
            "merging an input again changes the result (the merge is not an upper bound of its inputs)"
        assert c.state() == sc


def run_schedule(sp, n, ops, seed):
    """Returns None if every property holds, else a message.  NotImplementedError escapes."""
    try:
        reps = [sp["make"](f"r{i}") for i in range(n)]
        ev, flight = [], []
        for op in ops:
            if op[0] == "local":
                sp["apply"](reps[op[1] % n], op[2], ev)
            elif op[0] == "send":
                flight.append((op[2] % n, reps[op[1] % n].copy()))
            elif flight:                                            # deliver
                j = op[1] % len(flight)
                d, snap = flight[j]
                before = snap.state()
                reps[d] = reps[d].merge(snap)
                assert snap.state() == before, "merge changed the replica it was given: it must return a NEW replica"
                if not op[2]:
                    flight.pop(j)                                   # else it stays in flight: a duplicate delivery later
        rng = random.Random(seed * 1315423911 ^ 0x5BD1E995)
        pool = [r.copy() for r in reps] + [s.copy() for _, s in flight][:6]
        laws(pool, rng)
        snaps = [r.copy() for r in reps] + [s for _, s in flight]
        for i in range(n):                                          # everybody finally merges everything, in a random order, with repeats
            order = snaps[:]
            rng.shuffle(order)
            r = reps[i]
            for s in order + rng.sample(order, min(3, len(order))):
                r = r.merge(s)
            reps[i] = r
        base = reps[0].state()
        for i in range(1, n):
            assert reps[i].state() == base, f"replicas did not converge:\n        r0 = {show(base)}\n        r{i} = {show(reps[i].state())}"
        got, want = sp["view"](reps[0]), sp["oracle"](ev)
        assert got == want, f"converged to the wrong value:\n        got      {show(got)}\n        expected {show(want)}"
        return None
    except NotImplementedError:
        raise
    except AssertionError as e:
        return str(e)
    except Exception as e:                                          # a crash in the student's code is a failure too
        return f"{type(e).__name__}: {e}"


def gen_schedule(sp, seed):
    rng = random.Random(seed)
    n = rng.choice([3, 3, 4])
    ops = []
    for _ in range(rng.randint(20, 45)):
        x = rng.random()
        if x < 0.5:
            ops.append(("local", rng.randrange(n), sp["gen"](rng)))
        elif x < 0.75:
            s = rng.randrange(n)
            ops.append(("send", s, rng.choice([i for i in range(n) if i != s])))
        else:
            ops.append(("deliver", rng.randrange(100), rng.random() < 0.4))
    return n, ops


def shrink(sp, n, ops, seed):
    fails = lambda o: run_schedule(sp, n, o, seed) is not None
    chunk = max(1, len(ops) // 2)
    while True:
        changed, i = False, 0
        while i < len(ops):
            trial = ops[:i] + ops[i + chunk:]
            if trial and fails(trial):
                ops, changed = trial, True
            else:
                i += chunk
        if chunk > 1:
            chunk //= 2
        elif not changed:
            return ops


def fmt_op(op, n):
    if op[0] == "local":
        o = op[2]
        return f"r{op[1] % n}: {o[0]}({', '.join(repr(x) for x in o[1:])})"
    if op[0] == "send":
        return f"send a snapshot of r{op[1] % n} towards r{op[2] % n}"
    return f"deliver in-flight message #{op[1]}" + (" (and leave a copy in flight: a duplicate)" if op[2] else "")


def report_failure(sp, seed, n, ops, label=""):
    small = shrink(sp, n, ops, seed)
    msg = run_schedule(sp, n, small, seed)
    out = [f"    {label}seed {seed}: minimal failing schedule, {len(small)} of {len(ops)} operations, {n} replicas:"]
    out += [f"        {i + 1}. {fmt_op(o, n)}" for i, o in enumerate(small)]
    out.append(f"      -> {msg}")
    return out, len(small)


def fuzz(sp, seeds=SEEDS):
    """Run `seeds` random schedules.  On failure, raise with the failing seeds and a minimal schedule."""
    bad = []
    for seed in range(1, seeds + 1):
        n, ops = gen_schedule(sp, seed)
        msg = run_schedule(sp, n, ops, seed)
        if msg is not None:
            bad.append((seed, n, ops))
    if bad:
        seed, n, ops = bad[0]
        lines, _ = report_failure(sp, seed, n, ops)
        notes.append(f"    {sp['name']}: {len(bad)} of {seeds} seeds fail: {[b[0] for b in bad[:12]]}"
                     f"   replay: python3 check.py {target} --kind {sp['name']} --seed {seed}")
        notes.extend(lines)
        raise AssertionError(f"{sp['name']}: {len(bad)} of {seeds} random schedules break a property (seed {seed} first)")
    return seeds


# ---------------------------------------------------------------------------------------------
# Milestones 1-3: unit tests
# ---------------------------------------------------------------------------------------------
def m1_counters():
    a, b = mod.GCounter("a"), mod.GCounter("b")
    a.increment()
    a.increment(2)
    b.increment(5)
    assert a.value() == 3 and b.value() == 5
    ab, ba = a.merge(b), b.merge(a)
    assert ab.value() == 8 and ab.state() == ba.state(), f"two replicas that counted 3 and 5 must merge to 8, got {ab.value()}"
    assert (a.value(), b.value()) == (3, 5), "merge must not change its inputs"
    assert ab.rid == "a" and ba.rid == "b", "the merged replica keeps the rid of the replica merge() was called on"
    assert ab.merge(ab).state() == ab.state(), "merging a replica with itself must change nothing (idempotent)"
    assert ab.merge(a).value() == 8, "delivering an old state again must not add to the total"
    old = a.copy()
    a.increment()
    assert a.merge(old).value() == 4 and old.merge(a).value() == 4, "a stale copy of yourself must not win"
    try:
        a.increment(-1)
        raise AssertionError("a G-Counter must refuse a negative increment (it only grows)")
    except ValueError:
        pass
    p, q = mod.PNCounter("p"), mod.PNCounter("q")
    p.increment(5)
    q.decrement(3)
    assert p.value() == 5 and q.value() == -3
    m = p.merge(q)
    assert m.value() == 2 and m.state() == q.merge(p).state(), f"+5 on one replica and -3 on another is 2, got {m.value()}"
    q.increment(10)
    q.decrement(1)
    m2 = m.merge(q)
    assert m2.value() == 5 + 10 - 3 - 1 and m2.merge(q).state() == m2.state() and m2.merge(m).state() == m2.state()
    assert (p.value(), q.value()) == (5, 6), "merge must not change its inputs"


def m2_registers():
    a, b = mod.LWWRegister("a"), mod.LWWRegister("b")
    assert a.value() is None and a.merge(b).value() is None, "an empty register has value None"
    a.set("x", 10)
    b.set("y", 20)
    assert a.merge(b).value() == "y" and b.merge(a).value() == "y", "the later timestamp wins"
    c, d = mod.LWWRegister("c"), mod.LWWRegister("d")
    c.set("from-c", 7)
    d.set("from-d", 7)
    assert c.merge(d).value() == "from-d" and d.merge(c).value() == "from-d", \
        "equal timestamps: the higher replica id must win, in BOTH merge orders (commutativity!)"
    a.set("late", 1)                                   # a clock that is behind: the write must still take effect locally
    assert a.value() == "late", "a replica's own write must never be lost to its own older value"
    s = a.set("later", 1)
    assert a.value() == "later" and s[1] == "a", "set() returns the stamp (ts, rid) it actually used"
    assert a.merge(a).state() == a.state()
    # multi-value
    r1, r2 = mod.MVRegister("r1"), mod.MVRegister("r2")
    r1.set("base")
    r2 = r2.merge(r1)
    r2.rid = "r2"
    assert r2.value() == ["base"]
    r1.set("left")
    r2.set("right")                                    # concurrent
    m = r1.merge(r2)
    assert m.value() == ["left", "right"] and m.state() == r2.merge(r1).state(), \
        f"two concurrent writes must BOTH survive a merge, got {m.value()}"
    assert m.merge(m).state() == m.state() and m.merge(r1).state() == m.state()
    m.rid = "r1"
    vv = m.set("resolved")
    assert m.value() == ["resolved"], "a write made after seeing both siblings replaces both"
    assert vv.get("r1", 0) >= 2 and vv.get("r2", 0) >= 1, f"the new version vector must cover everything seen, got {vv}"
    assert m.merge(r1).value() == ["resolved"] and r2.merge(m).value() == ["resolved"], "the resolving write dominates the old siblings"
    assert r1.value() == ["left"], "merge must not change its inputs"
    e = mod.MVRegister("e")
    e.set("v")
    f = e.copy()
    assert e.merge(f).value() == ["v"], "the same write seen twice is one value"


def m3_orset():
    a, b = mod.ORSet("a"), mod.ORSet("b")
    t1 = a.add("x")
    t2 = a.add("x")
    assert t1 != t2, "every add must get its own unique tag, even for the same element"
    t3 = b.add("x")
    assert t3 not in (t1, t2), "tags must be unique across replicas too"
    assert a.value() == {"x"} and a.contains("x") and not a.contains("y")
    assert a.remove("x") == {t1, t2} and a.value() == set(), "remove tombstones every tag it can see"
    assert a.remove("x") == set(), "removing what is not there does nothing"
    a.add("x")
    assert a.value() == {"x"}, "an element removed earlier can be added again (this is what a 2P-Set cannot do)"
    # add wins over a concurrent remove
    p, q = mod.ORSet("p"), mod.ORSet("q")
    p.add("milk")
    q = q.merge(p)
    q.rid = "q"
    q.remove("milk")                                   # q removes the milk it saw ...
    p.add("milk")                                      # ... while p concurrently adds it again
    m1, m2 = p.merge(q), q.merge(p)
    assert m1.value() == {"milk"} and m1.state() == m2.state(), "a concurrent add must survive a remove that never saw it (add wins)"
    # remove only removes what it observed
    u, v = mod.ORSet("u"), mod.ORSet("v")
    u.add("k")
    assert v.remove("k") == set()
    assert u.merge(v).value() == {"k"}, "a replica that never saw an add cannot remove it"
    assert m1.merge(m1).state() == m1.state() and m1.merge(p).state() == m1.state()
    assert p.value() == {"milk"} and q.value() == set(), "merge must not change its inputs"
    ent = m1.entries()
    assert len(ent) == len({t for _, t in ent}) >= 1, "entries() returns the live (element, tag) pairs"


# ---------------------------------------------------------------------------------------------
# Milestone 4: property tests, with a self-test of the test
# ---------------------------------------------------------------------------------------------
def make_mutants():
    class SumGCounter(mod.GCounter):                   # merge adds instead of taking the maximum
        def merge(self, other):
            out = mod.GCounter(self.rid)
            for k in set(self.counts) | set(other.counts):
                out.counts[k] = self.counts.get(k, 0) + other.counts.get(k, 0)
            return out

    class TieLWW(mod.LWWRegister):                     # ignores the replica id on ties
        def merge(self, other):
            out = mod.LWWRegister(self.rid)
            if self.entry is None or (other.entry is not None and other.entry[0] > self.entry[0]):
                out.entry = other.entry
            else:
                out.entry = self.entry
            return out

    class ForgetfulORSet(mod.ORSet):                   # remove forgets the tags instead of tombstoning them
        def remove(self, e):
            tags = {t for el, t in self.adds if el == e}
            self.adds = {(el, t) for el, t in self.adds if el != e}
            return tags

    class InPlaceORSet(mod.ORSet):                     # merge mutates self
        def merge(self, other):
            self.adds |= other.adds
            self.removed |= other.removed
            return self

    def with_make(name, cls):
        sp = dict(SPECS[name])
        sp["make"] = lambda rid: cls(rid)
        return sp

    return [("a G-Counter whose merge ADDS", with_make("gcounter", SumGCounter)),
            ("an LWW-Register that ignores the replica id on ties", with_make("lww", TieLWW)),
            ("an OR-Set whose remove forgets tags instead of tombstoning them", with_make("orset", ForgetfulORSet)),
            ("an OR-Set whose merge mutates its receiver", with_make("orset", InPlaceORSet))]


def m4_properties():
    total = 0
    for kind in ("gcounter", "pncounter", "lww", "mvregister", "orset"):
        total += fuzz(SPECS[kind])
    notes.append(f"    5 types x {SEEDS} seeds = {total} random schedules on 3-4 replicas (duplicated, reordered, repeated deliveries): "
                 "converged, commutative, associative, idempotent, correct value")
    # does the test itself have teeth?  Plant four bugs and require that each is found and shrunk.
    shown = False
    for label, sp in make_mutants():
        found = None
        for seed in range(1, SEEDS + 1):
            n, ops = gen_schedule(sp, seed)
            if run_schedule(sp, n, ops, seed) is not None:
                found = (seed, n, ops)
                break
        assert found, f"self-test: the property tests failed to catch {label}; they are too weak"
        lines, k = report_failure(sp, found[0], found[1], found[2])
        assert k <= 10, f"self-test: the shrinker left {k} operations for {label}; expected at most 10"
        notes.append(f"    self-test: planted {label}: caught on seed {found[0]}, shrunk to {k} operations")
        if not shown and "forgets" in label:
            notes.extend(["      " + l for l in lines])
            shown = True


# ---------------------------------------------------------------------------------------------
# Milestone 5: the application
# ---------------------------------------------------------------------------------------------
def m5_application():
    # 2P-Set versus OR-Set: remove, then add again
    tp, orr = mod.TwoPSet("a"), mod.ORSet("a")
    for s in (tp, orr):
        s.add("apple")
        s.remove("apple")
        s.add("apple")
    assert tp.value() == set(), "the 2P-Set limitation: once removed, an element can never come back (its tombstone is for ever)"
    assert orr.value() == {"apple"}, "the OR-Set lets a removed element be added again (the new add has a fresh tag)"
    t2 = mod.TwoPSet("b")
    t2.add("pear")
    assert tp.merge(t2).value() == {"pear"} and t2.merge(tp).state() == tp.merge(t2).state()
    t3 = mod.TwoPSet("c")
    assert t3.remove("ghost") is False and t3.value() == set(), "removing an element you never saw does nothing"
    notes.append("    2P-Set: add, remove, add again -> element is GONE for ever.  OR-Set: same operations -> element is back.")

    # the cart
    phone, laptop = mod.Cart("phone"), mod.Cart("laptop")
    phone.add_item("pen", 1)
    phone.add_item("pen", 1)
    assert phone.items() == {"pen": 2}, "two taps on 'add pen' are two lines: the total is 2"
    laptop = laptop.merge(phone)
    laptop.rid = "laptop"
    phone.remove_item("pen")                           # phone removes the pen ...
    laptop.add_item("pen", 3)                          # ... while the laptop concurrently adds 3 more
    a, b = phone.merge(laptop), laptop.merge(phone)
    assert a.items() == {"pen": 3} and a.state() == b.state(), \
        f"add wins: the phone's remove covers the two pens it saw, the laptop's concurrent add of 3 survives; got {a.items()}"
    phone2 = a.copy()
    phone2.rid = "phone"
    phone2.remove_item("pen")
    phone2.add_item("pen", 1)
    assert phone2.items() == {"pen": 1}, "remove then add the same item again must work"
    x, y = mod.Cart("x"), mod.Cart("y")
    x.set_address("home", 5)
    y.set_address("work", 5)
    x.set_note("happy birthday")
    y.set_note("get well soon")
    m = x.merge(y)
    assert m.value()["address"] == "work" and y.merge(x).value()["address"] == "work", "address: last writer wins, ties by replica id"
    assert m.value()["note"] == ["get well soon", "happy birthday"], f"two concurrent notes must both be shown, got {m.value()['note']}"
    assert m.merge(m).state() == m.state() and x.value()["address"] == "home"
    # random schedules for the two new types
    n1 = fuzz(SPECS["twopset"])
    n2 = fuzz(SPECS["cart"])
    notes.append(f"    {n1} TwoPSet and {n2} Cart schedules on 3-4 replicas: converged, laws hold, carts equal the oracle")


# ---------------------------------------------------------------------------------------------
MILESTONES = [
    ("Milestone 1: G-Counter and PN-Counter", m1_counters),
    ("Milestone 2: LWW-Register and MV-Register", m2_registers),
    ("Milestone 3: OR-Set (add-wins, unique tags)", m3_orset),
    ("Milestone 4: property tests: random schedules, merge laws, convergence", m4_properties),
    ("Milestone 5: a shopping cart, and the 2P-Set's limitation", m5_application),
]


def _alarm(signum, frame):
    raise AssertionError("this milestone took more than 55 seconds: is a loop in your code never ending?")


def run_milestone(name, fn):
    del notes[:]
    if hasattr(signal, "SIGALRM"):
        signal.signal(signal.SIGALRM, _alarm)
        signal.alarm(55)
    try:
        fn()
        print(f"  ✔ {name}")
        results.append(True)
    except NotImplementedError as e:
        print(f"  … {name}: not implemented yet ({e})")
        results.append(False)
        del notes[:]
    except AssertionError as e:
        print(f"  ✘ {name}: {e}")
        results.append(False)
    except Exception as e:
        print(f"  ✘ {name}: {type(e).__name__}: {e}")
        results.append(False)
    finally:
        if hasattr(signal, "SIGALRM"):
            signal.alarm(0)
    for line in notes:
        print(line)


def replay():
    sp = SPECS[replay_kind]
    n, ops = gen_schedule(sp, replay_seed)
    msg = run_schedule(sp, n, ops, replay_seed)
    print(f"{replay_kind}, seed {replay_seed}: {len(ops)} operations on {n} replicas")
    for i, o in enumerate(ops):
        print(f"  {i + 1:2}. {fmt_op(o, n)}")
    if msg is None:
        print("all properties hold")
    else:
        print("FAILED:", msg)
        lines, _ = report_failure(sp, replay_seed, n, ops)
        print("\n".join(lines))


if __name__ == "__main__":
    if replay_seed is not None:
        if replay_kind not in SPECS:
            sys.exit(f"--kind must be one of {sorted(SPECS)}")
        try:
            replay()
        except NotImplementedError as e:
            print(f"not implemented yet ({e})")
        sys.exit(0)
    print(f"Lab 6 checks against {target}.py\n")
    for name, fn in MILESTONES:
        run_milestone(name, fn)
    ok = sum(results)
    print(f"\n{ok}/{len(MILESTONES)} milestones passing")
    sys.exit(0 if ok == len(MILESTONES) else 1)
