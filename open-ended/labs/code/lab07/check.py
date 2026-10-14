"""Self-check for Lab 7: Improve the Improver.

    python3 check.py                  # checks your starter.py
    python3 check.py solution         # checks the reference solution
    python3 check.py solution 4       # only milestone 4

Everything is seeded: the instances, the evolver, the improvers. There is no network and no clock
(fuel and a budget counter, not seconds, limit the work), so the same code gives the same result on
every run. The whole check finishes in about ten seconds for the reference solution.
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
mod = importlib.import_module(target)
results = []
T0 = time.time()


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


def near(a, b, tol=1e-9):
    return abs(a - b) <= tol


def prog(*body):
    return "def priority(item, rem):\n" + "".join(f"    {line}\n" for line in body)


def oracle_improve(config, score, rng, rounds, settings):
    """A plain reference for improve(): returns (best, best_score, the configs scored in order)."""
    best, best_score, seen = config, score(config), [config]
    for _ in range(rounds):
        cands = [mod.perturb(best, mod.CHOICES, rng, settings.n_change, settings.step)
                 for _ in range(settings.proposals)]
        for c in cands:
            s = score(c)
            seen.append(c)
            if s > best_score:
                best, best_score = c, s
    return best, best_score, seen


def toy_score(cfg):
    """A made-up meta-utility with a known best config, for testing the improvers."""
    return -abs(cfg.w_shape - 6) - abs(cfg.w_rule - 4) - 0.5 * abs(cfg.n_islands - 3)


# =============================================================================
# Milestone 1: utility
# =============================================================================
def m1():
    first_fit = prog("return 0")
    # [60,60,40,40]: first fit puts 40 in bin 1 and 40 in bin 2 -> 2 bins
    u = mod.utility(first_fit, [[60, 60, 40, 40]])
    assert near(u, -2), f"first fit on [60,60,40,40] uses 2 bins, so utility -2; got {u!r}"
    # two instances: [50,50,50] -> 2 bins, [30,30,30,30] -> 2 bins ... mean of 2 and 2
    u = mod.utility(first_fit, [[50, 50, 50], [30, 30, 30, 30]])
    assert near(u, -2), f"mean of 2 and 2 bins is 2; got {u!r}"
    u = mod.utility(first_fit, [[50, 50, 50], [60, 60, 60, 60]])
    assert near(u, -3), f"mean of 2 and 4 bins is 3; got {u!r}"
    best_fit = prog("return item - rem")
    assert near(mod.utility(best_fit, [[60, 50, 40, 50]]), -2), "best fit on [60,50,40,50] uses 2 bins"
    bad = {
        "a syntax error": "def priority(item, rem) return 0",
        "an import": "import os\n" + prog("return 0"),
        "an endless loop": prog("x = 0", "while True:", "    x += 1", "return x"),
        "division by zero": prog("return 1 / (rem - item)"),
        "a bool": prog("return item > 3"),
        "an infinity": prog("x = 1000000000", *["x = x * x"] * 7, "return x"),
        "a wrong signature": "def priority(item):\n    return 0\n",
    }
    inst = [[50, 50, 30, 30]]          # the second 50 fits exactly: rem - item == 0 there
    for what, src in bad.items():
        u = mod.utility(src, inst)
        assert u == mod.PENALTY, f"{what} must give PENALTY ({mod.PENALTY}); got {u!r}"
    loop = prog("k = 0", "while k < 10:", "    k += 1", "return 0")
    assert mod.utility(loop, inst, fuel_budget=10_000) == -2, "a short loop with enough fuel is fine"
    assert mod.utility(loop, inst, fuel_budget=20) == mod.PENALTY, "the same loop with 20 fuel must time out"
    assert type(mod.utility(first_fit, inst)) is float, "utility returns a float"
    return f"first fit on [60,60,40,40]: {mod.utility(first_fit, [[60, 60, 40, 40]])}; seven kinds of failure: {mod.PENALTY}"


# =============================================================================
# Milestone 2: meta_utility
# =============================================================================
def m2():
    cfg = mod.DEFAULT
    a = mod.meta_utility(cfg, mod.TRAIN_TASKS, mod.BUDGET)
    b = mod.meta_utility(cfg, mod.TRAIN_TASKS, mod.BUDGET)
    assert a == b, f"meta_utility must be deterministic; got {a!r} then {b!r}"
    singles = [mod.meta_utility(cfg, (t,), mod.BUDGET) for t in mod.TRAIN_TASKS]
    assert near(a, sum(singles) / len(singles)), f"it must be the mean over tasks: {a!r} vs {singles!r}"
    # With a budget of 1 the evolver can only score the seed program, so the answer is known.
    for t in (1, 2):
        scoring = mod.make_instances([1000 * t + 500 + j for j in range(mod.N_EVAL)], mod.ITEMS, 20, 60)
        want = mod.utility(mod.SEED_SRC, scoring)
        got = mod.meta_utility(cfg, (t,), 1)
        assert near(got, want), (f"budget 1: the evolver keeps SEED_SRC, scored on the scoring instances "
                                 f"of task {t}; expected {want!r}, got {got!r}")
    # Count the evaluations the evolver makes: its Budget counters, and its calls of utility.
    real, real_budget, log, counters = mod.utility, mod.Budget, [], []

    class SpyBudget(real_budget):
        def __init__(self, limit):
            super().__init__(limit)
            counters.append(self)

    def spy(src, instances, *rest):
        log.append(len(instances))
        return real(src, instances, *rest)

    mod.utility, mod.Budget = spy, SpyBudget
    try:
        mod.meta_utility(mod.TUNED, (1, 2, 3), 20)
    finally:
        mod.utility, mod.Budget = real, real_budget
    assert len(counters) == 3, f"each task needs its own fresh Budget; saw {len(counters)} counters for 3 tasks"
    assert all(c.used == 21 for c in counters), ("the evolver should run until its budget of 20 is "
                                                 f"exhausted; counters read {[c.used for c in counters]}")
    assert 0 < log.count(mod.N_SEARCH) <= 60, f"search evaluations: {log.count(mod.N_SEARCH)} (at most 60)"
    assert log.count(mod.N_EVAL) == 3, f"three tasks: three scoring calls; saw {log.count(mod.N_EVAL)}"
    lo = mod.meta_utility(cfg, (1, 2), mod.BUDGET, 10, 70)
    assert lo != mod.meta_utility(cfg, (1, 2), mod.BUDGET), "lo and hi must reach the instances"
    return (f"meta_utility(naive, train tasks, budget {mod.BUDGET}) = {a:.3f}   "
            f"(budget 1, the seed program alone: {mod.meta_utility(cfg, mod.TRAIN_TASKS, 1):.3f})")


# =============================================================================
# Milestone 3: improve
# =============================================================================
def m3():
    st = mod.Settings(proposals=3, n_change=2, step=1)
    cfg = mod.Config(w_shape=0, w_rule=0, n_islands=1)
    calls = []

    def counted(c):
        calls.append(c)
        return toy_score(c)

    best, best_s = mod.improve(cfg, counted, random.Random(5), 4, st)
    want, want_s, seen = oracle_improve(cfg, toy_score, random.Random(5), 4, st)
    assert len(calls) == 1 + 4 * 3, f"expected {1 + 4 * 3} score calls (1 + rounds * proposals); got {len(calls)}"
    assert calls == seen, ("the configs scored differ from the reference. Draw all `proposals` candidates "
                           "from the best-so-far BEFORE scoring any of them, and score them in order")
    assert best == want and near(best_s, want_s), f"expected {want} ({want_s}); got {best} ({best_s})"
    assert near(best_s, toy_score(best)), "the second value is the score of the config returned"
    assert best_s > toy_score(cfg), "twelve proposals on the toy score must find something better"
    # a constant score: nothing is STRICTLY better, so the start comes back
    flat, flat_s = mod.improve(cfg, lambda c: 1.0, random.Random(1), 3, st)
    assert flat == cfg, "a candidate that only ties must not replace the best"
    # the real thing
    score = mod.make_scorer()
    start = score(mod.DEFAULT)
    final, final_s = mod.improve(mod.DEFAULT, score, random.Random(0), 4, mod.SEED_SETTINGS)
    assert final_s > start, f"the seed improver should improve the naive config; {start:.3f} -> {final_s:.3f}"
    assert near(final_s, score(final)), "returned score must match score(returned config)"
    return (f"toy score: {toy_score(cfg):.1f} -> {best_s:.1f}\n"
            f"naive evolver on the training tasks: {start:.3f} -> {final_s:.3f}  ({final})")


# =============================================================================
# Milestone 4: self-application
# =============================================================================
def m4():
    st = mod.Settings(proposals=2, n_change=2, step=1)
    seeds = (0, 1, 2)
    cfg = mod.Config(w_shape=0, w_rule=0, n_islands=1)
    calls = []

    def counted(c):
        calls.append(c)
        return toy_score(c)

    u = mod.improver_utility(st, counted, cfg, seeds, 8)
    gains = []
    for s in seeds:
        _, bs, _ = oracle_improve(cfg, toy_score, random.Random(s), 8 // st.proposals, st)
        gains.append(bs - toy_score(cfg))
    assert near(u, sum(gains) / 3), f"expected the mean gain {sum(gains) / 3:.4f}; got {u!r}"
    assert len(calls) == 1 + 3 * (1 + 4 * 2), f"score calls: expected {1 + 3 * 9}; got {len(calls)}"
    u6 = mod.improver_utility(mod.Settings(6, 1, 1), toy_score, cfg, seeds, 8)
    u1 = mod.improver_utility(mod.Settings(1, 1, 1), toy_score, cfg, seeds, 8)
    assert u1 >= 0 and u6 >= 0, "an improver never makes things worse"
    # self_improve: the same hill-climb, one level up
    real, tried = mod.improver_utility, []

    def spy(settings, score, start=mod.DEFAULT, *a, **k):
        tried.append(settings)
        return real(settings, score, start, *a, **k)

    mod.improver_utility = spy
    try:
        best, best_u = mod.self_improve(toy_score, random.Random(3), 3, mod.SEED_SETTINGS, cfg)
    finally:
        mod.improver_utility = real
    assert len(tried) == 1 + 3, f"improver_utility should be called 1 + rounds = 4 times; got {len(tried)}"
    rng, b = random.Random(3), mod.SEED_SETTINGS
    bu = real(b, toy_score, cfg)
    for _ in range(3):
        c = mod.perturb(b, mod.SETTING_CHOICES, rng, 1, 1)
        cu = real(c, toy_score, cfg)
        if cu > bu:
            b, bu = c, cu
    assert best == b and near(best_u, bu), f"expected {b} ({bu:.4f}); got {best} ({best_u:.4f})"
    # the real self-application, on the training tasks
    score = mod.make_scorer()
    seed_u = mod.improver_utility(mod.SEED_SETTINGS, score)
    new, new_u = mod.self_improve(score, random.Random(0), 10)
    assert new_u > seed_u, f"the improved improver must beat the seed improver on the training tasks: {seed_u:.3f} vs {new_u:.3f}"
    fresh_seed = mod.improver_utility(mod.SEED_SETTINGS, score, seeds=mod.FRESH_SEEDS)
    fresh_new = mod.improver_utility(new, score, seeds=mod.FRESH_SEEDS)
    assert fresh_new > fresh_seed, ("on fresh random streams the improved improver should still win: "
                                    f"{fresh_seed:.3f} vs {fresh_new:.3f}")
    return (f"seed improver {mod.SEED_SETTINGS}\n  mean gain {seed_u:.3f} bins (train)   {fresh_seed:.3f} (fresh streams)\n"
            f"improved improver {new}\n  mean gain {new_u:.3f} bins (train)   {fresh_new:.3f} (fresh streams)")


# =============================================================================
# Milestone 5: held-out meta-evaluation
# =============================================================================
def m5():
    st = mod.Settings(2, 2, 1)
    cfg = mod.Config(w_shape=0, w_rule=0, n_islands=1)
    train = lambda c: toy_score(c)
    held = lambda c: -toy_score(c) / 2
    shifted = lambda c: float(c.w_constant)
    out = mod.generalisation(st, train, held, shifted, cfg, (0, 1), 8)
    tr, he, sh = [], [], []
    for s in (0, 1):
        final, _, _ = oracle_improve(cfg, train, random.Random(s), 4, st)
        tr.append(train(final) - train(cfg))
        he.append(held(final) - held(cfg))
        sh.append(shifted(final) - shifted(cfg))
    want = {"train": sum(tr) / 2, "held": sum(he) / 2, "shifted": sum(sh) / 2}
    want["gap"] = want["train"] - want["held"]
    assert set(out) == set(want), f"expected the keys {sorted(want)}; got {sorted(out)}"
    for k in want:
        assert near(out[k], want[k]), f"{k}: expected {want[k]:.4f}; got {out[k]!r}"
    assert out["train"] > 0 and out["held"] < 0, "this toy case has train gain > 0 and held gain < 0"
    # the real thing. The improver only ever sees the training scorer.
    tr_s = mod.make_scorer()
    he_s = mod.make_scorer(mod.HELD_TASKS)
    sh_s = mod.make_scorer(mod.HELD_TASKS, 10, 70)
    easy = mod.generalisation(mod.SEED_SETTINGS, tr_s, he_s, sh_s, mod.DEFAULT, mod.FRESH_SEEDS)
    hard = mod.generalisation(mod.SEED_SETTINGS, tr_s, he_s, sh_s, mod.TUNED, mod.FRESH_SEEDS, 40)
    assert easy["train"] > 0.4 and easy["held"] > 0 and easy["shifted"] > 0, (
        f"from the naive config the gain is large and should transfer; got {easy}")
    assert hard["train"] > 0 and hard["gap"] > 0.05 and hard["shifted"] < 0, (
        f"from the tuned config the training gain is small, noise-sized, and does not transfer; got {hard}")
    f = lambda d: "  ".join(f"{k} {v:+.3f}" for k, v in d.items())
    return f"from the naive config (4 calls):  {f(easy)}\nfrom the tuned config (40 calls): {f(hard)}"


# =============================================================================
# Milestone 6: the audit
# =============================================================================
def m6():
    real = mod.meta_utility
    consts = (mod.BUDGET, mod.TRAIN_TASKS, mod.HELD_TASKS)
    ok, why = mod.audit(mod.honest())
    assert ok and why == [], f"the honest improver must pass; got {ok}, {why}"
    expect = {"cheat_budget": ["budget"], "cheat_peek": ["peeked"]}
    for name, want in expect.items():
        ok, why = mod.audit(getattr(mod, name))
        assert not ok and why == want, f"{name}: expected rejection with {want}; got {ok}, {why}"
    ok, why = mod.audit(mod.cheat_tamper)
    assert not ok and "tampered" in why, f"cheat_tamper changes BUDGET; expected 'tampered' in the reasons; got {why}"
    assert (mod.BUDGET, mod.TRAIN_TASKS, mod.HELD_TASKS) == consts, (
        "audit must put BUDGET and the task tuples back, even after a cheater changed them (use try/finally)")
    assert mod.meta_utility is real, "audit must put the real meta_utility back"

    def sneaky(config, score, rng, rounds):
        """Asks for a scorer on the held-out tasks: still goes through meta_utility."""
        peek = mod.make_scorer(mod.HELD_TASKS)
        return max([config, mod.perturb(config, mod.CHOICES, rng, 1, 1)], key=peek)

    def both(config, score, rng, rounds):
        mod.meta_utility(config, mod.HELD_TASKS, mod.BUDGET * 5)
        return config

    def boom(config, score, rng, rounds):
        raise RuntimeError("improver crashed")

    ok, why = mod.audit(sneaky)
    assert not ok and why == ["peeked"], f"a scorer on the held-out tasks is still a peek; got {ok}, {why}"
    ok, why = mod.audit(both)
    assert not ok and why == ["peeked", "budget"], f"reasons must come in the order peeked, budget; got {why}"
    try:
        mod.audit(boom)
    except RuntimeError:
        pass
    assert mod.meta_utility is real, "a crashing improver must not leave the spy installed"
    # the honest result still holds, after all that
    score = mod.make_scorer()
    final = mod.honest()(mod.DEFAULT, score, random.Random(0), 4)
    gain = score(final) - score(mod.DEFAULT)
    assert gain > 0.3, f"the honest improver should still improve the naive config; gain {gain:.3f}"
    lines = []
    for name in ("honest", "cheat_budget", "cheat_peek", "cheat_tamper"):
        fn = mod.honest() if name == "honest" else getattr(mod, name)
        ok, why = mod.audit(fn)
        lines.append(f"{name:13s} -> {'accepted' if ok else 'REJECTED ' + str(why)}")
    return "\n".join(lines) + f"\nhonest improver after the audits: +{gain:.3f} bins on the training tasks"


print(f"Lab 7: Improve the Improver  ({target}.py)")
check(1, "Milestone 1: utility", m1)
check(2, "Milestone 2: meta_utility", m2)
check(3, "Milestone 3: improve", m3)
check(4, "Milestone 4: improving the improver", m4)
check(5, "Milestone 5: held-out meta-evaluation", m5)
check(6, "Milestone 6: audit", m6)
print(f"\n{sum(results)}/{len(results)} milestones passing  ({time.time() - T0:.1f} s)")
