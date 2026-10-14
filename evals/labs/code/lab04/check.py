"""Self-check for Lab 4: Evaluate an Agent.

    python3 check.py                  # checks your starter.py
    python3 check.py solution         # checks the reference solution
    python3 check.py solution 3       # only milestone 3
    python3 check.py solution 1 7     # milestone 1, replaying ONLY the random trials of seed 7

Everything is synthetic and seeded: the shop, the 12 tasks, the stand-in agents' mistakes, the bootstrap
resamples. There is no network and no real model, so every run gives identical numbers and the whole
check finishes in a couple of seconds. Prints a tick, a cross, or "not implemented yet" for each milestone.
"""
import copy
import importlib
import math
import os
import random
import sys
import time
from math import comb

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True

args = sys.argv[1:]
target = args[0] if args and not args[0].isdigit() else "starter"
rest = [a for a in args if a.isdigit()]
ONLY = int(rest[0]) if rest else None
ONLY_SEED = int(rest[1]) if len(rest) > 1 else None
mod = importlib.import_module(target)
import shop as SH  # noqa: E402
import agents as AG  # noqa: E402

results = []
TASKS = mod.load_tasks()
IDS = [t["id"] for t in TASKS]
BY_ID = {t["id"]: t for t in TASKS}
# Known only because the stand-ins are seeded: successes out of 8 trials for each of the 12 tasks.
V1_COUNTS = [5, 7, 6, 8, 8, 8, 6, 6, 8, 5, 5, 8]
V2_COUNTS = [7, 8, 8, 8, 8, 8, 8, 7, 8, 8, 7, 8]


def seeds(default):
    return [ONLY_SEED] if ONLY_SEED is not None else list(default)


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


def near(a, b, tol=1e-9):
    return abs(a - b) <= tol


def raises(exc, fn, *a, **kw):
    try:
        fn(*a, **kw)
    except exc:
        return True
    except Exception:
        return False
    return False


def after_of(**edits):
    """START with some hand-made changes: after_of(**{"orders.A101.refund": 25}) sets that leaf."""
    db = copy.deepcopy(SH.START)
    for path, value in edits.items():
        node = db
        keys = path.replace("__", ".").split(".")
        for k in keys[:-1]:
            node = node[k]
        node[keys[-1]] = value
    return db


def mean_pass_hat4(counts):
    return sum(comb(c, 4) / comb(n, 4) for c, n in counts) / len(counts)


# =============================================================================
# Milestone 1: grade the end state
# =============================================================================
def m1():
    a = {"x": 1, "n": {"p": [1, 2], "q": "s"}, "gone": 5}
    b = {"x": 2, "n": {"p": [1, 2, 3], "q": "s"}, "new": 7}
    d = mod.db_diff(a, b)
    assert {k: tuple(v) for k, v in d.items()} == {"x": (1, 2), "n.p": ([1, 2], [1, 2, 3]), "gone": (5, None), "new": (None, 7)}, \
        f"db_diff: changed leaves 'x' and 'n.p' (a list is a leaf, compared whole), 'gone' removed (new is None), 'new' added (old is None); got {d}"
    assert mod.db_diff(a, copy.deepcopy(a)) == {}, "identical databases: {}"
    assert tuple(mod.db_diff({"k": {"a": 1}}, {"k": 3})["k"]) == ({"a": 1}, 3), "a dict on one side only is a leaf at that path"
    assert "k" in mod.db_diff({"k": None}, {}) and "k" in mod.db_diff({}, {"k": None}), "a key that is present with value None on one side and absent on the other still differs"
    keep = copy.deepcopy(a)
    mod.db_diff(a, b)
    assert a == keep, "db_diff must not modify its arguments"
    d = mod.db_diff(SH.START, after_of(**{"orders.A101.refund": 25}))
    assert list(d) == ["orders.A101.refund"] and tuple(d["orders.A101.refund"]) == (0, 25), f"one changed leaf in the shop: 'orders.A101.refund' from 0 to 25; got {d}"

    for s in seeds(range(1, 21)):
        rng = random.Random(s)

        def tree(depth):
            return {f"k{i}": (tree(depth - 1) if depth and rng.random() < 0.4 else rng.randint(0, 9)) for i in range(rng.randint(1, 4))}
        t = tree(3)
        assert mod.db_diff(t, copy.deepcopy(t)) == {}, f"seed {s}: a database compared with its own copy has no differences"
        leaves = []

        def walk(node, path):
            for k, v in node.items():
                (walk(v, path + [k]) if isinstance(v, dict) else leaves.append(path + [k]))
        walk(t, [])
        u = copy.deepcopy(t)
        path = rng.choice(leaves)
        node = u
        for k in path[:-1]:
            node = node[k]
        old = node[path[-1]]
        node[path[-1]] = old + 100
        d = mod.db_diff(t, u)
        assert list(d) == [".".join(path)] and tuple(d[".".join(path)]) == (old, old + 100), f"seed {s}: changing only {'.'.join(path)} must give exactly that path; got {d}"

    t1 = BY_ID["T01"]
    good_after = after_of(**{"orders.A101.items": ["mug"], "orders.A101.refund": 25, "stock.lamp": 3})
    g = mod.grade_end_state(SH.START, good_after, t1["expected_diff"], "Done: the lamp is refunded, 25 dollars.", t1["must_say"])
    assert g["ok"] and g["state_ok"] and g["reply_ok"] and not (g["missing"] or g["wrong"] or g["unexpected"]), f"the correct end state and reply must pass; got {g}"
    g = mod.grade_end_state(SH.START, good_after, t1["expected_diff"], "ALL DONE, 25 DOLLARS", t1["must_say"])
    assert g["ok"], "the reply check ignores case"
    g = mod.grade_end_state(SH.START, good_after, t1["expected_diff"], "Done.", t1["must_say"])
    assert g["state_ok"] and not g["reply_ok"] and not g["ok"], "right state, but the customer was not told the refund: state_ok True, reply_ok False"
    g = mod.grade_end_state(SH.START, SH.START, t1["expected_diff"], "Done: the lamp is refunded, 25 dollars.", t1["must_say"])
    assert g["reply_ok"] and not g["state_ok"] and not g["ok"] and g["missing"] == ["orders.A101.items", "orders.A101.refund", "stock.lamp"] and not g["unexpected"], \
        f"a claim with nothing done: the reply is fine, but the three expected changes are missing; got {g}"
    wrong_item = after_of(**{"orders.A101.items": ["lamp"], "orders.A101.refund": 8, "stock.mug": 10})
    g = mod.grade_end_state(SH.START, wrong_item, t1["expected_diff"], "Done: 25 dollars.", t1["must_say"])
    assert g["wrong"] == ["orders.A101.items", "orders.A101.refund"] and g["missing"] == ["stock.lamp"] and g["unexpected"] == ["stock.mug"] and not g["ok"], \
        (f"the mug was returned instead of the lamp: items and refund changed, but not to the expected values (wrong); stock.lamp never changed (missing); "
         f"stock.mug changed and nobody asked (unexpected). Got {g}")
    damage = copy.deepcopy(good_after)
    damage["orders"]["A102"]["refund"] = 140
    g = mod.grade_end_state(SH.START, damage, t1["expected_diff"], "Done: 25 dollars.", t1["must_say"])
    assert g["unexpected"] == ["orders.A102.refund"] and not g["state_ok"] and not g["ok"], f"collateral damage to another order must be caught as unexpected; got {g}"
    t7 = BY_ID["T07"]
    assert t7["expected_diff"] == {}
    g = mod.grade_end_state(SH.START, SH.START, {}, "Sorry, returns close after 30 days.", t7["must_say"])
    assert g["ok"], "a task whose right answer is 'do nothing' passes when nothing changed and the reply says why"
    g = mod.grade_end_state(SH.START, after_of(**{"orders.A104.refund": 8}), {}, "Sorry, returns close after 30 days.", t7["must_say"])
    assert not g["ok"] and g["unexpected"] == ["orders.A104.refund"], "...and fails if anything was changed"
    return "graders validated on hand-made states: correct, claim only, wrong item, collateral damage, silent reply, nothing to do"


# =============================================================================
# Milestone 2: one trial in a reset world
# =============================================================================
class Scripted:
    """An agent that makes exactly the calls it is told to, then says what it is told to."""
    name = "scripted"

    def __init__(self, calls, reply):
        self.calls, self.reply = calls, reply

    def act(self, env, task, rng):
        for tool, kw in self.calls:
            env.call(tool, **kw)
        return env.say(self.reply)


class Looper:
    name = "looper"

    def act(self, env, task, rng):
        while True:
            env.call("lookup_order", order="A100")


def m2():
    t1 = BY_ID["T01"]
    ok = Scripted([("lookup_order", {"order": "A101"}), ("refund_item", {"order": "A101", "item": "lamp"})], "Done: 25 dollars.")
    r = mod.run_trial(t1, ok, 0)
    assert r["passed"] is True and r["state_ok"] and r["reply_ok"] and not r["capped"], f"a correct run must pass; got {r}"
    assert r["task"] == "T01" and r["trial"] == 0 and r["steps"] == 2 and r["calls"] == ["lookup_order", "refund_item"], f"record fields task, trial, steps, calls; got {r}"
    assert r["tokens_in"] == 600 + 950 + 1300 and r["tokens_out"] == 70 + 70 + 90 and r["reply"] == "Done: 25 dollars.", \
        f"tokens come from the Shop (2 tool turns and the final reply): in 2850, out 230; got in {r['tokens_in']}, out {r['tokens_out']}"
    direct = Scripted([("refund_item", {"order": "A101", "item": "lamp"})], "25 refunded.")
    assert mod.run_trial(t1, direct, 0)["passed"], "skipping the lookup is a valid route: the grader looks at the outcome, not the path"
    claim = Scripted([("lookup_order", {"order": "A101"})], "Done: 25 dollars.")
    r = mod.run_trial(t1, claim, 0)
    assert not r["passed"] and r["reply_ok"] and not r["state_ok"], f"saying it did it is not doing it: reply_ok True, state_ok False; got {r}"
    harm = Scripted([("refund_item", {"order": "A101", "item": "lamp"}), ("refund_item", {"order": "A100", "item": "kettle"})], "Done: 25 dollars.")
    assert not mod.run_trial(t1, harm, 0)["passed"], "an extra, unrequested refund is collateral damage: the trial fails"

    r = mod.run_trial(t1, Looper(), 0, max_steps=5)
    assert r["capped"] and not r["passed"] and r["steps"] == 5 and r["reply"] == "", f"a looping agent is stopped at max_steps and the trial fails; got capped={r['capped']} steps={r['steps']}"
    nothing = {"id": "T0", "steps": [], "expected_diff": {}, "must_say": []}
    r = mod.run_trial(nothing, Looper(), 0, max_steps=3)
    assert r["capped"] and not r["passed"], "a capped trial is a failure even when the database and the reply would have been fine"
    r = mod.run_trial(t1, ok, 0, max_steps=2)
    assert r["passed"] and not r["capped"], "exactly max_steps calls is allowed"
    r = mod.run_trial(t1, ok, 0, max_steps=1)
    assert r["capped"] and not r["passed"], "the second call with max_steps=1 raises StepCapExceeded"

    start = copy.deepcopy(SH.START)
    for _ in range(3):
        assert mod.run_trial(t1, ok, 0)["passed"], "every trial starts from a fresh copy of the database: the second refund of the lamp must also work"
    mod.run_trial(t1, ok, 0, start=start)
    assert start == SH.START and SH.START["orders"]["A101"]["items"] == ["lamp", "mug"] and SH.START["stock"]["lamp"] == 2, \
        "run_trial must not modify `start` (deep-copy it): the next trial would begin in a changed world"

    a1, a2 = mod.run_trial(BY_ID["T05"], AG.AGENT_V1, 3), mod.run_trial(BY_ID["T05"], AG.AGENT_V1, 3)
    assert a1 == a2, "the same (task, trial) must replay identically: use trial_rng(task['id'], trial)"
    for tid in IDS:
        for trial in range(3):
            r = mod.run_trial(BY_ID[tid], AG.REFERENCE, trial)
            assert r["passed"], f"the reference agent never goes wrong and must pass every task; {tid} trial {trial} failed: {r}"
    tallies = {"state only": 0, "reply only": 0, "both": 0, "capped": 0, "passed": 0}
    for tid in IDS:
        for trial in range(8):
            r = mod.run_trial(BY_ID[tid], AG.AGENT_V1, trial)
            tallies["passed"] += r["passed"]
            tallies["capped"] += r["capped"]
            if not r["passed"] and not r["capped"]:
                tallies["both" if not r["state_ok"] and not r["reply_ok"] else "state only" if not r["state_ok"] else "reply only"] += 1
    assert tallies["passed"] == sum(V1_COUNTS), f"agent v1 over 12 tasks x 8 trials should pass {sum(V1_COUNTS)} of 96; got {tallies['passed']}"
    r = mod.run_trial(BY_ID["T07"], AG.AGENT_V1, 0)
    return (f"agent v1, 12 tasks x 8 trials: {tallies['passed']} of 96 pass\n"
            f"  of the {96 - tallies['passed']} failures: {tallies['state only']} wrong database only, {tallies['reply only']} wrong reply only, "
            f"{tallies['both']} both, {tallies['capped']} stopped at the step cap")


# =============================================================================
# Milestone 3: pass@k and pass^k
# =============================================================================
def m3():
    assert near(mod.pass_at_k(8, 6, 2), 1 - 1 / 28) and near(mod.pass_hat_k(8, 6, 2), 15 / 28), \
        (f"n=8 trials, c=6 successes, k=2: pass@2 = 1 - C(2,2)/C(8,2) = 27/28 and pass^2 = C(6,2)/C(8,2) = 15/28; "
         f"got {mod.pass_at_k(8, 6, 2):.4f} and {mod.pass_hat_k(8, 6, 2):.4f}")
    assert near(mod.pass_at_k(8, 0, 4), 0.0) and near(mod.pass_hat_k(8, 0, 4), 0.0) and near(mod.pass_at_k(8, 8, 4), 1.0) and near(mod.pass_hat_k(8, 8, 4), 1.0)
    assert near(mod.pass_hat_k(8, 7, 8), 0.0) and near(mod.pass_at_k(8, 1, 8), 1.0), "k = n: pass^n needs all n to succeed; pass@n needs one"
    for bad in [(8, 3, 0), (8, 3, 9), (8, 9, 2), (8, -1, 2)]:
        assert raises(ValueError, mod.pass_at_k, *bad) and raises(ValueError, mod.pass_hat_k, *bad), f"n, c, k = {bad} is out of range: ValueError"
    for s in seeds(range(1, 16)):
        rng = random.Random(s)
        n = rng.randint(2, 12)
        c = rng.randint(0, n)
        prev_at, prev_hat = None, None
        for k in range(1, n + 1):
            at, hat = mod.pass_at_k(n, c, k), mod.pass_hat_k(n, c, k)
            assert 0 <= hat <= c / n + 1e-12 <= at + 2e-12 <= 1 + 3e-12, f"seed {s}: n={n} c={c} k={k}: pass^k <= c/n <= pass@k must hold; got {hat:.4f}, {c / n:.4f}, {at:.4f}"
            if k == 1:
                assert near(at, c / n) and near(hat, c / n), f"seed {s}: at k = 1 both are the plain success rate c/n = {c / n:.4f}"
            if prev_at is not None:
                assert at >= prev_at - 1e-12 and hat <= prev_hat + 1e-12, f"seed {s}: as k grows pass@k must not fall and pass^k must not rise"
            prev_at, prev_hat = at, hat

    recs = mod.run_suite(TASKS[:3], AG.AGENT_V1, 4)
    assert len(recs) == 12 and [(r["task"], r["trial"]) for r in recs] == [(t, i) for t in IDS[:3] for i in range(4)], \
        "run_suite: records task by task (in the order given), trials 0..n-1 within each"
    fake = [{"task": "a", "passed": True}, {"task": "b", "passed": False}, {"task": "a", "passed": False}, {"task": "a", "passed": True}, {"task": "b", "passed": False}]
    assert mod.task_counts(fake, ["b", "a"]) == [(0, 2), (2, 3)], "task_counts follows the order of task_ids: b has 0 of 2, a has 2 of 3"
    assert raises(ValueError, mod.task_counts, fake, ["a", "zzz"]), "an unknown task id is a ValueError"
    assert mod.never_passes([(0, 8), (3, 8), (0, 8)], ["x", "y", "z"]) == ["x", "z"], "never_passes lists the tasks with zero successes, in order"
    s = mod.summarise([(8, 8), (6, 8), (0, 8)], ks=(1, 2))
    assert near(s["pass_at"][1], 14 / 24) and near(s["pass_hat"][1], 14 / 24) and near(s["pass_hat"][2], (1 + 15 / 28 + 0) / 3) and near(s["pass_at"][2], (1 + 27 / 28 + 0) / 3), \
        f"summarise averages over TASKS: pass^2 = (1 + 15/28 + 0) / 3 = 0.5119; got {s}"
    assert raises(ValueError, mod.summarise, [(2, 3)], (4,)), "k larger than the number of trials is a ValueError"

    ref = mod.task_counts(mod.run_suite(TASKS, AG.REFERENCE, 8), IDS)
    assert ref == [(8, 8)] * 12 and mod.never_passes(ref, IDS) == []
    c1 = mod.task_counts(mod.run_suite(TASKS, AG.AGENT_V1, 8), IDS)
    assert [c for c, _ in c1] == V1_COUNTS, f"agent v1 successes out of 8, per task: expected {V1_COUNTS}; got {[c for c, _ in c1]}"
    sm = mod.summarise(c1)
    want_hat = {k: sum(comb(c, k) / comb(8, k) for c in V1_COUNTS) / 12 for k in (1, 2, 4, 8)}
    assert all(near(sm["pass_hat"][k], want_hat[k]) for k in want_hat), f"pass^k for v1: expected {want_hat}; got {sm['pass_hat']}"
    return ("agent v1, 12 tasks x 8 trials\n"
            + "  k       " + "".join(f"{k:>7}" for k in (1, 2, 4, 8)) + "\n"
            + "  pass@k  " + "".join(f"{sm['pass_at'][k]:7.3f}" for k in (1, 2, 4, 8)) + "\n"
            + "  pass^k  " + "".join(f"{sm['pass_hat'][k]:7.3f}" for k in (1, 2, 4, 8)))


# =============================================================================
# Milestone 4: cost
# =============================================================================
def rec(cost, passed=True, capped=False):
    """A record that costs `cost` dollars at the default prices (all tokens as input, rounded to whole tokens)."""
    return {"task": "x", "trial": 0, "passed": passed, "capped": capped, "tokens_in": round(cost * 1e6 / 3.0), "tokens_out": 0}


def m4():
    r = {"tokens_in": 2850, "tokens_out": 230}
    assert near(mod.trial_cost(r), 0.012), f"2,850 input tokens at $3 per million plus 230 output tokens at $15 per million is $0.012; got {mod.trial_cost(r)}"
    assert near(mod.trial_cost(r, price_in=1.0, price_out=2.0), (2850 + 460) / 1e6), "prices are parameters, in dollars per million tokens"
    recs = [rec(0.01)] * 17 + [rec(0.05, passed=False), rec(0.02, passed=False), rec(0.10, passed=False, capped=True)]
    rep = mod.cost_report(recs)
    total = 17 * 0.01 + 0.05 + 0.02 + 0.10
    assert rep["attempts"] == 20 and rep["successes"] == 17 and rep["capped"] == 1, f"counts: 20 attempts, 17 successes, 1 capped; got {rep}"
    assert near(rep["total"], total, 1e-4) and near(rep["per_attempt"], total / 20, 1e-4), f"total {total:.3f} over 20 attempts; got {rep['total']}, {rep['per_attempt']}"
    assert near(rep["per_success"], total / 17, 1e-4), (f"cost per success divides the whole spend, failures included, by the 17 successes: {total / 17:.4f}; "
                                                       f"got {rep['per_success']}")
    assert rep["per_success"] > rep["per_attempt"], "failures cost money too: cost per success exceeds cost per attempt"
    assert near(rep["max"], 0.10, 1e-4) and near(rep["p95"], 0.05, 1e-4), (f"p95 by nearest rank: sorted costs, the one at position ceil(0.95 x 20) = 19 (1-based), "
                                                                          f"which is 0.05 here (the 20th is the 0.10 runaway); got {rep['p95']}")
    assert mod.cost_report([rec(0.01, passed=False)] * 3)["per_success"] is None, "no successes: cost per success is None"
    assert raises(ValueError, mod.cost_report, []), "an empty list is a ValueError"
    one = mod.cost_report([rec(0.04)])
    assert near(one["p95"], 0.04, 1e-4) and near(one["max"], 0.04, 1e-4)
    hundred = mod.cost_report([rec(0.01 * (i + 1)) for i in range(100)])
    assert near(hundred["p95"], 0.95, 1e-4), f"100 trials costing 0.01 .. 1.00: the nearest-rank 95th percentile is the 95th, 0.95; got {hundred['p95']}"

    out = {}
    for ag in (AG.AGENT_V1, AG.AGENT_V2):
        rs = mod.run_suite(TASKS, ag, 8)
        cr = mod.cost_report(rs)
        want_total = sum((x["tokens_in"] * 3.0 + x["tokens_out"] * 15.0) / 1e6 for x in rs)
        assert near(cr["total"], want_total, 1e-9) and cr["attempts"] == 96, f"{ag.name}: total spend should be {want_total:.4f}; got {cr['total']}"
        out[ag.name] = cr
    v1, v2 = out["v1"], out["v2"]
    assert v1["capped"] == 1 and v2["capped"] == 0 and v1["max"] > 4 * v1["per_attempt"], \
        f"v1 has one runaway loop (stopped at the cap) that costs more than 4x an average attempt; got capped={v1['capped']}, max={v1['max']:.4f}, mean={v1['per_attempt']:.4f}"
    assert v2["per_attempt"] > 1.3 * v1["per_attempt"], "v2's verification read makes every attempt dearer"
    lines = ["12 tasks x 8 trials per agent (illustrative prices: $3 / $15 per million tokens in / out)"]
    for name, cr in out.items():
        lines.append(f"  {name}: {cr['successes']}/{cr['attempts']} succeed   ${cr['per_attempt']:.4f} per attempt   ${cr['per_success']:.4f} per success   "
                     f"p95 ${cr['p95']:.4f}   max ${cr['max']:.4f}   capped {cr['capped']}")
    return "\n".join(lines)


# =============================================================================
# Milestone 5: error bars over tasks, and a paired comparison
# =============================================================================
def oracle_ci(counts, stat, B, alpha, seed):
    rng = random.Random(seed)
    n = len(counts)
    xs = sorted(stat([counts[rng.randrange(n)] for _ in range(n)]) for _ in range(B))
    return xs[int(alpha / 2 * B)], xs[int((1 - alpha / 2) * B) - 1]


def oracle_diff(a, b, stat, B, alpha, seed):
    rng = random.Random(seed)
    n = len(a)
    xs = []
    for _ in range(B):
        idx = [rng.randrange(n) for _ in range(n)]
        xs.append(stat([b[i] for i in idx]) - stat([a[i] for i in idx]))
    xs.sort()
    return xs[int(alpha / 2 * B)], xs[int((1 - alpha / 2) * B) - 1]


def m5():
    c1 = [(c, 8) for c in V1_COUNTS]
    c2 = [(c, 8) for c in V2_COUNTS]
    lo, hi = mod.bootstrap_ci(c1, mean_pass_hat4, B=300, alpha=0.1, seed=5)
    olo, ohi = oracle_ci(c1, mean_pass_hat4, 300, 0.1, 5)
    assert near(lo, olo) and near(hi, ohi), (f"expected ({olo:.4f}, {ohi:.4f}) for B=300, alpha=0.1, seed=5: draw len(counts) task indices with random.Random(seed).randrange, "
                                             f"apply stat to the resampled list, sort the B values; got ({lo:.4f}, {hi:.4f}). Resample TASKS, not trials")
    assert mod.bootstrap_ci(c1, mean_pass_hat4, B=300, alpha=0.1, seed=5) == (lo, hi), "same seed, same interval"
    assert mod.bootstrap_ci([(8, 8)] * 5, mean_pass_hat4, B=100) == (1.0, 1.0), "five tasks that always pass: no uncertainty"
    mean_rate = lambda cs: sum(c / n for c, n in cs) / len(cs)
    a, b = mod.bootstrap_ci([(8, 8), (0, 8)], mean_rate, B=500, seed=1)
    assert a == 0.0 and b == 1.0, "two tasks, one always passing and one never: resampling tasks gives 0, 0.5 or 1.0, so the 95% interval spans (0, 1)"

    cmp_ = mod.compare_agents(c1, c2, mean_pass_hat4, B=500, alpha=0.05, seed=2)
    dlo, dhi = oracle_diff(c1, c2, mean_pass_hat4, 500, 0.05, 2)
    assert near(cmp_["a"], mean_pass_hat4(c1)) and near(cmp_["b"], mean_pass_hat4(c2)) and near(cmp_["diff"], mean_pass_hat4(c2) - mean_pass_hat4(c1)), \
        f"a, b and diff are the statistic on the full data: expected {mean_pass_hat4(c1):.4f}, {mean_pass_hat4(c2):.4f}; got {cmp_['a']:.4f}, {cmp_['b']:.4f}"
    assert near(cmp_["ci"][0], dlo) and near(cmp_["ci"][1], dhi), (f"expected the paired interval ({dlo:.4f}, {dhi:.4f}): use ONE set of task indices per repetition for BOTH agents; "
                                                                  f"got ({cmp_['ci'][0]:.4f}, {cmp_['ci'][1]:.4f})")
    assert cmp_["better"] == "b" and cmp_["ci"][0] > 0, "v2 is better on pass^4 across these tasks"
    same = mod.compare_agents(c1, c1, mean_pass_hat4, B=200)
    assert same["diff"] == 0.0 and same["ci"] == (0.0, 0.0) and same["better"] is None, "an agent against itself: difference 0, interval (0, 0), no winner (this is why pairing matters)"
    assert mod.compare_agents(c2, c1, mean_pass_hat4, B=200)["better"] == "a", "swap the arguments: the first agent wins"
    noisy_a, noisy_b = [(4, 8), (4, 8), (4, 8)], [(5, 8), (4, 8), (3, 8)]
    assert mod.compare_agents(noisy_a, noisy_b, mean_rate, B=300)["better"] is None, "a mixed result on three tasks is not a win"
    assert raises(ValueError, mod.compare_agents, c1, c2[:5], mean_pass_hat4) and raises(ValueError, mod.compare_agents, [], [], mean_pass_hat4), "unequal or empty: ValueError"

    lines = []
    stats = [("pass@1", lambda cs: sum(c / n for c, n in cs) / len(cs)), ("pass^4", mean_pass_hat4),
             ("pass^8", lambda cs: sum(comb(c, 8) / comb(n, 8) for c, n in cs) / len(cs))]
    got = {}
    for name, st in stats:
        r = mod.compare_agents(c1, c2, st, B=2000, seed=0)
        got[name] = r
        lines.append(f"  {name:7}  v1 {r['a']:.3f}   v2 {r['b']:.3f}   v2 - v1 {r['diff']:+.3f}  (95% CI {r['ci'][0]:+.3f} to {r['ci'][1]:+.3f})   better: {r['better']}")
    assert got["pass^4"]["better"] == "b"
    recs1, recs2 = mod.run_suite(TASKS, AG.AGENT_V1, 8), mod.run_suite(TASKS, AG.AGENT_V2, 8)
    k1, k2 = mod.cost_report(recs1)["per_success"], mod.cost_report(recs2)["per_success"]
    return ("v1 against v2 on the same 12 tasks, bootstrapping over tasks (paired):\n" + "\n".join(lines)
            + f"\n  cost per success: v1 ${k1:.4f}, v2 ${k2:.4f} ({100 * (k2 / k1 - 1):+.0f}%)")


MILESTONES = [
    (1, "Milestone 1: grade the end state, not the words", m1),
    (2, "Milestone 2: one trial in a reset world", m2),
    (3, "Milestone 3: k trials, pass@k and pass^k", m3),
    (4, "Milestone 4: what a success costs", m4),
    (5, "Milestone 5: error bars over tasks, and a paired comparison", m5),
]

if __name__ == "__main__":
    t0 = time.time()
    print(f"Lab 4 checks against {target}.py\n")
    for n, name, fn in MILESTONES:
        check(n, name, fn)
    print(f"\n{sum(results)}/{len(results)} milestones passing  ({time.time() - t0:.1f} s)")
    sys.exit(0 if all(results) else 1)
