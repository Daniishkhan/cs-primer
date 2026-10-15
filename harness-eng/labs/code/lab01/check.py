"""Self-check for Lab 1: Greedy versus Tree Search.

    python3 check.py                  # checks your starter.py
    python3 check.py solution         # checks the reference solution
    python3 check.py solution 4       # only milestone 4
    python3 check.py solution 5 3     # milestone 5, replaying ONLY seed 3

Everything is deterministic: tasks, proposals and bootstrap resamples all
come from seeded random.Random generators. There is no network, no clock and
no model. The whole check takes a few seconds.
Prints a tick, a cross, or "not implemented yet" for each milestone.
"""
import importlib
import math
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True

args = sys.argv[1:]
target = args[0] if args and not args[0].isdigit() else "starter"
rest = [a for a in args if a.isdigit()]
ONLY = int(rest[0]) if rest else None
ONLY_SEED = int(rest[1]) if len(rest) > 1 else None
mod = importlib.import_module(target)
results = []
T0 = time.time()


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
        where = next((f"{f.name}() line {f.lineno}" for f in reversed(tb)
                      if f.filename.endswith(f"{target}.py")), "?")
        print(f"  ✘ {name}: {type(e).__name__}: {e}   [in {where}]")
        results.append(False)


Config, Task, Node, Journal = mod.Config, mod.Task, mod.Node, mod.Journal
Proposer = mod.Proposer
F = frozenset


def mean(xs):
    return sum(xs) / len(xs)


def tiny_task(leaky=True):
    """y = 2x. Training x is -1, 1, -1, 1 so the intercept is 0 and the
    ridge slope is sum(xy) / (sum(x^2) + lam) = 8 / (4 + lam)."""
    train = [([-1.0], -2.0), ([1.0], 2.0), ([-1.0], -2.0), ([1.0], 2.0)]
    public = [([3.0], 6.0)]
    private = [([2.0], 4.0), ([0.0], 0.0)]
    return Task(1, (0,), (2.0,), train, public, private, leaky)


def node(step, stage, parent, public, private=None, cfg=None):
    n = Node(step, stage, parent, cfg or Config(F([0]), 1.0), public,
             private if private is not None else public)
    return n


def journal_of(*nodes):
    j = Journal()
    for n in nodes:
        j.add(n)
    return j


class CountingRandom(random.Random):
    """A random.Random that counts how many times random() is called."""
    calls = 0

    def random(self):
        self.calls += 1
        return super().random()


# ── Milestone 1 ──────────────────────────────────────────────────────────
def m1():
    t = tiny_task()
    got = mod.score_config(t, Config(F([0]), 1.0), "public")
    assert abs(got - 1.2) < 1e-9, (
        f"slope 8/(4+1) = 1.6 predicts 4.8 at x=3, true 6, so the public "
        f"RMSE is 1.2; got {got:.6f}. Is the fit on task.train, and the "
        f"error on the split's own rows?")
    got = mod.score_config(t, Config(F([0]), 1.0), "private")
    want = math.sqrt(0.32)
    assert abs(got - want) < 1e-9, (
        f"private rows predict 3.2 and 0.0 for labels 4.0 and 0.0, so the "
        f"RMSE is sqrt(0.32) = {want:.6f}; got {got:.6f}")
    got = mod.score_config(t, Config(F(), 1.0), "public")
    assert abs(got - 6.0) < 1e-9, (
        f"with no features the model predicts the training mean 0, so the "
        f"public RMSE is 6.0; got {got:.6f}")
    # peek: reads the public labels from the cache, learns nothing
    got = mod.score_config(t, Config(F(), 1.0, True), "public")
    assert got == 0.0, f"peek on a leaky task has RMSE 0 on public; got {got}"
    got = mod.score_config(t, Config(F([0]), 1.0, True), "private")
    assert abs(got - math.sqrt(8.0)) < 1e-9, (
        f"peek cannot see private labels, so it predicts the training mean "
        f"0 for labels 4 and 0: RMSE sqrt(8) = {math.sqrt(8):.4f}; "
        f"got {got:.4f}")
    try:
        mod.score_config(tiny_task(leaky=False), Config(F(), 1.0, True),
                         "public")
        raise AssertionError("peek with no cache file must raise ConfigError")
    except mod.ConfigError:
        pass
    try:
        mod.score_config(t, Config(F([0]), 1.0), "secret")
        raise AssertionError("an unknown split must raise ValueError")
    except ValueError:
        pass
    try:
        mod.score_config(t, Config(F([5]), 1.0), "public")
        raise AssertionError("a column that does not exist must raise "
                             "ConfigError")
    except mod.ConfigError:
        pass
    orc, emp = [], []
    for s in seeds(range(6)):
        task = mod.make_task(s, 24, 3)
        o = mod.score_config(task, Config(F(task.useful), 0.1), "private")
        e = mod.score_config(task, Config(F(), 1.0), "private")
        assert o < 0.9 and e > 1.8, (
            f"seed {s}: the true features should give a private RMSE under "
            f"0.9 and no features over 1.8; got {o:.2f} and {e:.2f}")
        orc.append(o)
        emp.append(e)
    return (f"hand-checked RMSEs match; peek scores 0 on public and sqrt(8) "
            f"on private\nmean private RMSE: {mean(orc):.2f} with the true "
            f"columns, {mean(emp):.2f} with none")


# ── Milestone 2 ──────────────────────────────────────────────────────────
def m2():
    rng = random.Random(0)
    assert mod.greedy_policy(Journal(), rng) == ("draft", None), \
        "an empty journal means: draft"
    b = node(0, "draft", None, None)
    got = mod.greedy_policy(journal_of(b), rng)
    assert got == ("debug", b), (
        f"with only a buggy leaf, the incumbent is being repaired: debug "
        f"it; got {got}")
    g1 = node(0, "draft", None, 1.5)
    g2 = node(1, "draft", None, 1.1)
    g3 = node(2, "improve", g2, 1.1)          # ties g2: the earlier wins
    bug = node(3, "improve", g2, None)
    stage, parent = mod.greedy_policy(journal_of(g1, g2, g3, bug), rng)
    assert stage == "improve" and parent is g2, (
        f"improve the best good node (lowest public score, earliest on a "
        f"tie); got {stage} {getattr(parent, 'step', parent)}")
    # on real runs: one chain, drafts only before the first good node
    log = []
    for s in seeds(range(8)):
        task = mod.make_task(s, 24, 3)
        j = mod.run_search(task, Proposer(), 24, 100 + s, mod.greedy_policy)
        best_so_far, seen_good = None, False
        for n in j.nodes:
            if n.stage == "draft":
                assert not seen_good, (
                    f"seed {s}: step {n.step} drafted after a good node "
                    f"existed. A greedy climber drafts once.")
            if n.stage == "improve":
                assert n.parent.public == best_so_far, (
                    f"seed {s}: step {n.step} improved a node that was not "
                    f"the best so far. Replay: python3 check.py {target} "
                    f"2 {s}")
            if n.public is not None:
                seen_good = True
                best_so_far = n.public if best_so_far is None else \
                    min(best_so_far, n.public)
        log.append(mod.final_private(j))
    base = [mod.score_config(mod.make_task(s, 24, 3), Config(F(), 1.0),
                             "private") for s in seeds(range(8))]
    assert mean(log) < mean(base) - 0.3, (
        f"greedy should clearly beat the no-feature baseline: "
        f"{mean(log):.2f} vs {mean(base):.2f}")
    return (f"hand-built journals pick the right action; on 8 seeds greedy "
            f"reaches private RMSE {mean(log):.2f} against {mean(base):.2f} "
            f"for no model")


# ── Milestone 3 ──────────────────────────────────────────────────────────
def m3():
    rng = CountingRandom(0)
    assert mod.aide_policy(Journal(), rng) == ("draft", None)
    assert rng.calls == 0, ("while drafts are still owed, the rule makes no "
                            "random draw")
    j = journal_of(*[node(i, "draft", None, 1.0 + i) for i in range(3)])
    assert mod.aide_policy(j, rng)[0] == "draft", \
        "3 drafts and num_drafts=5: draft again"
    drafts = [node(i, "draft", None, 1.0 + i) for i in range(5)]
    j = journal_of(*drafts)
    rng = CountingRandom(1)
    got = mod.aide_policy(j, rng, debug_prob=0.0)
    assert got == ("improve", drafts[0]), (
        f"5 good drafts and nothing to debug: improve the best (the first, "
        f"1.0); got {got[0]} {getattr(got[1], 'step', got[1])}")
    assert rng.calls == 1, (f"make exactly one rng.random() call per "
                            f"decision after the drafts; made {rng.calls}")
    # debug: only buggy LEAVES within max_debug_depth
    bug = node(5, "draft", None, None)
    j = journal_of(*drafts, bug)
    got = mod.aide_policy(j, random.Random(2), debug_prob=1.0)
    assert got == ("debug", bug), f"debug_prob=1 with a buggy leaf: {got}"
    mid = node(6, "draft", None, None)
    kid = node(7, "debug", mid, 2.0)           # mid is no longer a leaf
    j = journal_of(*drafts, mid, kid)
    got = mod.aide_policy(j, random.Random(2), debug_prob=1.0)
    assert got[0] == "improve", (
        f"a buggy node that already has a child is not a leaf, so there is "
        f"nothing to debug; got {got[0]}")
    chain = [node(5, "draft", None, None)]
    for i in range(1, 5):
        chain.append(node(5 + i, "debug", chain[-1], None))
    assert chain[-1].debug_depth == 4
    j = journal_of(*drafts, *chain)
    got = mod.aide_policy(j, random.Random(2), debug_prob=1.0,
                          max_debug_depth=3)
    assert got[0] == "improve", (
        "the only buggy leaf is 4 repairs deep, past max_debug_depth=3; the "
        f"rule must give up on it and improve; got {got[0]}")
    # no good nodes at all, nothing debuggable: draft again
    allbad = [node(i, "draft", None, None) for i in range(5)]
    for b in allbad:
        b.children.append(object())            # make none of them a leaf
    got = mod.aide_policy(journal_of(*allbad), random.Random(3),
                          debug_prob=0.0)
    assert got[0] == "draft", f"no good node: draft again; got {got[0]}"
    # the share of debug steps follows debug_prob
    j = journal_of(*drafts, bug)
    r = random.Random(4)
    n_debug = sum(mod.aide_policy(j, r)[0] == "debug" for _ in range(2000))
    assert 0.45 < n_debug / 2000 < 0.55, (
        f"with debug_prob 0.5 about half of 2000 decisions should debug; "
        f"got {n_debug / 2000:.3f}")
    # on a real run the first five steps are the five drafts
    for s in seeds(range(5)):
        task = mod.make_task(s, 24, 3)
        run = mod.run_search(task, Proposer(), 20, 7 + s, mod.aide_policy)
        first = [n.stage for n in run.nodes[:5]]
        assert first == ["draft"] * 5, (
            f"seed {s}: the first 5 steps should be drafts, got {first}")
        assert len(run.drafts) == 5 + sum(
            n.stage == "draft" for n in run.nodes[5:]), "bookkeeping"
    return ("hand-built journals: drafts first, then debug with probability "
            "0.5 (about half of 2000 draws), never past depth 3, else "
            "improve the best")


# ── Milestone 4 ──────────────────────────────────────────────────────────
def m4():
    got = mod.paired_ci([3.0, 5.0], [2.0, 4.0])
    assert all(abs(x - 1.0) < 1e-12 for x in got), (
        f"every pair differs by exactly 1, so mean and both ends are 1; "
        f"got {got}")
    got = mod.paired_ci([10.0, 20.0, 30.0], [10.0, 20.0, 30.0])
    assert got == (0.0, 0.0, 0.0), (
        f"identical lists must give (0, 0, 0); got {got}. If it does not, "
        f"you resampled a and b separately instead of resampling PAIRS.")
    m, lo, hi = mod.paired_ci([1.0, 3.0], [1.0, 1.0])
    assert abs(m - 1.0) < 1e-12 and lo == 0.0 and hi == 2.0, (
        f"differences are [0, 2]: mean 1, and with 2000 resamples the "
        f"percentile ends are 0 and 2; got {(m, lo, hi)}")
    assert mod.paired_ci([1.0, 3.0, 2.0], [0.0, 1.0, 2.0]) == \
        mod.paired_ci([1.0, 3.0, 2.0], [0.0, 1.0, 2.0]), \
        "same inputs and seed must give the same interval"
    # coverage: the interval should contain the true mean about 95% of the
    # time (a little less for 30 pairs); we ask for 85% to 100%
    r = random.Random(5)
    hit, trials = 0, 150
    for _ in range(trials):
        d = [r.gauss(0.3, 1.0) for _ in range(30)]
        m, lo, hi = mod.paired_ci(d, [0.0] * 30, n_boot=300, seed=1)
        assert lo <= m <= hi, f"mean {m:.3f} outside [{lo:.3f}, {hi:.3f}]"
        hit += lo <= 0.3 <= hi
    assert 0.85 <= hit / trials, (
        f"the 95% interval covered the true mean in {hit / trials:.0%} of "
        f"{trials} simulated studies; expected about 92% to 96%")
    g, t = mod.compare(1, seeds(range(12)), steps=24)
    m, lo, hi = mod.paired_ci(g, t)
    return (f"intervals are exact on hand cases and cover the true mean in "
            f"{hit / trials:.0%} of {trials} simulated studies\n"
            f"12 seeds, one useful column, 24 steps: greedy minus tree = "
            f"{m:+.2f} RMSE, 95% CI [{lo:+.2f}, {hi:+.2f}]")


# ── Milestone 5 ──────────────────────────────────────────────────────────
def m5():
    empty = Config(F(), 1.0)
    task = mod.make_task(0, 24, 3)
    p = Proposer()
    assert mod.realised_density(task, p, empty, 100, 1) == \
        mod.realised_density(task, p, empty, 100, 1), "must be deterministic"
    got = mod.realised_density(task, Proposer(p_bug=1.0), empty, 50, 1)
    assert got == 0.0, (f"every edit crashes, so none improves: 0.0; "
                        f"got {got}")
    got = mod.realised_density(task, Proposer(p_bug=0.0), empty, 50, 1,
                               min_gain=-100.0)
    assert got == 1.0, (f"with a huge negative min_gain every edit that "
                        f"runs counts: 1.0; got {got}")
    got = mod.realised_density(task, Proposer(p_bug=0.0), empty, 50, 1,
                               min_gain=100.0)
    assert got == 0.0, f"no edit gains 100 RMSE: 0.0; got {got}"
    rows, prev = [], -1.0
    for k in (1, 3, 6, 12):
        ds = [mod.realised_density(mod.make_task(s, 24, k), Proposer(),
                                   empty, 100, s)
              for s in seeds(range(30))]
        rows.append((k, mean(ds)))
        assert mean(ds) > prev, (
            f"density should rise with the number of useful columns; "
            f"{k} useful gave {mean(ds):.3f} after {prev:.3f}")
        prev = mean(ds)
    # the gap, by density: greedy minus tree, paired over 60 seeds, 12 steps
    out = []
    for k, d in rows:
        g, t = mod.compare(k, seeds(range(60)), steps=12)
        m, lo, hi = mod.paired_ci(g, t)
        out.append(f"{k:2d} useful of 24: density {d:.2f}, greedy minus "
                   f"tree {m:+.2f} [{lo:+.2f}, {hi:+.2f}]")
    return "\n".join(out)


# ── Milestone 6 ──────────────────────────────────────────────────────────
def m6():
    hack = node(0, "improve", None, 0.0, 2.5)
    fine = node(1, "improve", None, 1.0, 1.05)
    crash = node(2, "improve", None, None, None)
    edge = node(3, "improve", None, 1.0, 1.5)  # gap exactly 0.5: not flagged
    j = journal_of(hack, fine, crash, edge)
    got = [n.step for n in mod.hack_flags(j)]
    assert got == [0], (f"flag only nodes whose private score is MORE than "
                        f"margin worse than public; got steps {got}")
    got = [n.step for n in mod.hack_flags(j, margin=0.1)]
    assert got == [0, 3], f"margin=0.1 should also flag step 3; got {got}"
    a = journal_of(node(0, "draft", None, 0.0, 2.5))       # selected, flagged
    b = journal_of(node(0, "draft", None, 1.0, 1.1))       # selected, fine
    c = journal_of(node(0, "draft", None, None, None))     # nothing good
    got = mod.hacking_rate([a, b, c, a])
    assert abs(got - 0.5) < 1e-12, (
        f"2 of 4 runs selected a flagged node: 0.5; got {got}")
    # a flagged node that was NOT selected does not count
    d = journal_of(node(0, "draft", None, 0.0, 2.5),
                   node(1, "improve", None, -1.0, -1.0))
    assert mod.hacking_rate([d]) == 0.0, (
        "the selected node is the lowest public score (step 1, which is "
        "fine); the flagged step 0 was not selected")
    # the probe on real runs: leaky harness versus the cache file removed
    res = {}
    for leaky in (True, False):
        js, priv = [], []
        for s in seeds(range(30)):
            task = mod.make_task(s, 24, 3, leaky=leaky)
            j = mod.run_search(task, Proposer(p_peek=0.1), 24, 300 + s,
                               mod.aide_policy)
            js.append(j)
            b = j.best()
            priv.append(b.private if b else 3.0)
        res[leaky] = (mod.hacking_rate(js), mean(priv))
    assert res[True][0] >= 0.5, (
        f"with the cache file in place and peek noticed 10% of the time, "
        f"most runs should end on a peek node; flagged {res[True][0]:.2f}")
    assert res[False][0] <= 0.15, (
        f"with the cache file gone a peek crashes and gets debugged; "
        f"flagged {res[False][0]:.2f}")
    honest = [mod.run_search(mod.make_task(s, 24, 3), Proposer(), 24, 300 + s,
                             mod.aide_policy) for s in seeds(range(30))]
    assert mod.hacking_rate(honest) <= 0.1, (
        f"honest runs should rarely be flagged; got "
        f"{mod.hacking_rate(honest):.2f}")
    return (f"leaky harness: hacking rate {res[True][0]:.2f}, private RMSE "
            f"{res[True][1]:.2f}\n"
            f"cache file removed: hacking rate {res[False][0]:.2f}, "
            f"private RMSE {res[False][1]:.2f}\n"
            f"no peeking proposer: hacking rate "
            f"{mod.hacking_rate(honest):.2f} (the false-alarm rate)")


print(f"Lab 1 checks against {target}.py\n")
check(1, "Milestone 1: the evaluator", m1)
check(2, "Milestone 2: the greedy hill-climber", m2)
check(3, "Milestone 3: AIDE's selection rule", m3)
check(4, "Milestone 4: a paired comparison with an interval", m4)
check(5, "Milestone 5: opportunity density", m5)
check(6, "Milestone 6: the hacking probe", m6)
print(f"\n{sum(results)}/{len(results)} milestones passing  "
      f"({time.time() - T0:.1f} s)")
sys.exit(0 if all(results) else 1)
