"""Self-check for Lab 1: The Level-1 Checker.

    python3 check.py                  # checks your starter.py
    python3 check.py solution         # checks the reference solution
    python3 check.py solution 4       # only milestone 4
    python3 check.py solution 4 7     # milestone 4, only the random cases of seed 7

Everything is seeded and there is no network and no clock, so the same code
gives the same result every time. The fixture logs in logs/ are made by
make_fixtures.py. The whole check finishes in about a second.
"""
import importlib
import json
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
print(f"Lab 1 checks against {target}.py\n")


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


def load(name):
    with open(os.path.join(HERE, "logs", name)) as f:
        return mod.parse_log(f.read())[0]


def near(a, b, tol=1e-9):
    return abs(a - b) <= tol


def make_run(arm="improver", budget=60.0, attempts=10, noise=0.01,
             search=("s1",), incumbents=(), costs=None, finals=None,
             initials=None, run_id="r"):
    """A Run built directly. incumbents: one best-score per step (a step is
    accepted when the incumbent rises). finals/initials: {task: score}."""
    run = mod.Run(run_id, arm, budget, attempts, noise, list(search))
    prev = None
    for i, inc in enumerate(incumbents, start=1):
        cost = costs[i - 1] if costs else budget / attempts
        run.steps.append(mod.Step(i, cost, inc, prev is not None and
                                  inc > prev, inc))
        prev = inc
    for stage, d in (("initial", initials or {}), ("final", finals or {})):
        for task, score in d.items():
            run.evals.append(mod.Eval(stage, task, 1, score))
    return run


def line(**kw):
    return json.dumps(kw)


HEADER = line(type="run", run_id="a", arm="improver", budget_usd=10,
              max_attempts=5, noise_floor=0.01, search_tasks=["s1"])


# ── Milestone 1 ──────────────────────────────────────────────────────────
def m1():
    text = "\n".join([
        HEADER, "",
        line(type="step", run_id="a", step=1, cost_usd=2.0, search_score=0.5,
             accepted=False, incumbent=0.5),
        line(type="step", run_id="a", step=2, cost_usd=1.5, search_score=0.6,
             accepted=True, incumbent=0.6),
        line(type="eval", run_id="a", stage="final", task="h1", seed=3,
             score=0.7)])
    runs = mod.parse_log(text)
    assert len(runs) == 1, f"expected 1 run, got {len(runs)}"
    r = runs[0]
    assert (r.run_id, r.arm, r.budget_usd, r.max_attempts) == \
        ("a", "improver", 10.0, 5), f"header fields wrong: {r}"
    assert r.noise_floor == 0.01 and r.search_tasks == ["s1"], "noise/tasks"
    assert [s.step for s in r.steps] == [1, 2] and r.steps[1].accepted is True
    assert r.steps[0].cost_usd == 2.0 and r.steps[1].incumbent == 0.6
    assert len(r.evals) == 1 and r.evals[0].task == "h1" and \
        r.evals[0].seed == 3, "the eval line was not kept"

    def bad(text, needle, label):
        try:
            mod.parse_log(text)
        except mod.LogError as e:
            assert str(e).startswith(needle), \
                f"{label}: message should start {needle!r}, got {str(e)!r}"
            return
        raise AssertionError(f"{label}: expected a LogError, got none")

    bad(HEADER + "\n{not json", "line 2:", "invalid JSON on line 2")
    bad(HEADER + "\n\n" + line(x=1), "line 3:",
        "no type on line 3 (blank lines still count in line numbers)")
    bad(line(type="step", run_id="a", step=1, cost_usd=1, search_score=0,
             accepted=False, incumbent=0), "line 1:",
        "step before its header")
    bad(HEADER + "\n" + line(type="step", run_id="a", step=1, cost_usd=1),
        "line 2:", "step missing fields")
    bad(line(type="run", run_id="a", arm="improver"), "line 1:",
        "header missing budget_usd")
    bad(HEADER + "\n" + line(type="note"), "line 2:", "unknown type")
    two = HEADER + "\n" + HEADER.replace('"a"', '"b"')
    assert [x.run_id for x in mod.parse_log(two)] == ["a", "b"], \
        "two headers should give two runs in file order"
    good = load("improver_good.jsonl")
    assert len(good.steps) == 30 and len(good.evals) == 36, \
        f"improver_good.jsonl: expected 30 steps and 36 evals, got " \
        f"{len(good.steps)} and {len(good.evals)}"
    return (f"improver_good.jsonl: {len(good.steps)} steps, "
            f"{len(good.evals)} evals, budget ${good.budget_usd:g}")


# ── Milestone 2 ──────────────────────────────────────────────────────────
def m2():
    inc = [0.5] * 10
    fin_hi = {"h1": 0.6, "h2": 0.62}
    fin_lo = {"h1": 0.55, "h2": 0.57}
    imp = make_run(incumbents=inc, finals=fin_hi)
    base = make_run("baseline", incumbents=inc, finals=fin_lo)
    v = mod.fair_baseline(imp, base)
    assert v.passed, f"same budget and attempts, improver ahead: {v.reason}"
    v = mod.fair_baseline(imp, make_run("baseline", budget=30.0,
                                        incumbents=inc, finals=fin_lo))
    assert not v.passed and "budgets differ" in v.reason, \
        f"budget 60 against 30 should fail with 'budgets differ': {v}"
    v = mod.fair_baseline(imp, make_run("baseline", attempts=20,
                                        incumbents=inc, finals=fin_lo))
    assert not v.passed and "attempts differ" in v.reason, \
        f"attempts 10 against 20 should fail with 'attempts differ': {v}"
    v = mod.fair_baseline(imp, make_run("baseline", incumbents=inc[:7],
                                        finals=fin_lo))
    assert not v.passed, "a baseline that used 7 of 10 attempts (under " \
        "80%) is not a fair comparison"
    v = mod.fair_baseline(imp, make_run("baseline", incumbents=inc[:8],
                                        finals=fin_lo))
    assert v.passed, f"8 of 10 attempts is exactly 80% and should pass: {v}"
    v = mod.fair_baseline(base, imp)
    assert not v.passed and "does not beat" in v.reason, \
        f"the weaker arm as improver should fail with 'does not beat': {v}"
    ties = make_run(incumbents=inc, finals=fin_lo)
    assert not mod.fair_baseline(ties, base).passed, "a tie is not a win"
    fair = mod.fair_baseline(load("improver_good.jsonl"),
                             load("baseline_fair.jsonl"))
    short = mod.fair_baseline(load("improver_good.jsonl"),
                              load("baseline_short.jsonl"))
    assert fair.passed, f"improver_good vs baseline_fair: {fair.reason}"
    assert not short.passed, "baseline_short has half the budget"
    return f"fair pair: {fair.reason}\nshort pair: {short.reason}"


# ── Milestone 3 ──────────────────────────────────────────────────────────
def m3():
    g = mod.real_gains(make_run(incumbents=[0.5, 0.5, 0.53, 0.53, 0.535,
                                            0.56, 0.5605], noise=0.01))
    assert len(g) == 2 and near(g[0], 0.03) and near(g[1], 0.025), \
        f"expected the gains [0.03, 0.025] (0.005 and 0.0005 are under the " \
        f"noise floor 0.01), got {g}"
    assert mod.real_gains(make_run(incumbents=[0.9, 0.9])) == [], \
        "step 1 has no previous incumbent"
    v = mod.sustained_trend(make_run(incumbents=[0.5, 0.53, 0.56, 0.59]))
    assert v.passed, f"three equal real accepts should pass: {v.reason}"
    v = mod.sustained_trend(make_run(
        incumbents=[0.5, 0.5, 0.6, 0.6, 0.601, 0.603]))
    assert not v.passed and "real accept" in v.reason, \
        f"one big accept and two within noise: {v}"
    v = mod.sustained_trend(make_run(incumbents=[0.5, 0.52, 0.54, 0.54]))
    assert not v.passed, "two accepts are not enough"
    v = mod.sustained_trend(make_run(incumbents=[0.5, 0.52, 0.53, 0.62,
                                                 0.62]))
    assert not v.passed and "lucky" in v.reason, \
        f"three real accepts but one carries 0.09 of 0.12 (75%): {v}"
    for seed in seeds(range(1, 6)):
        rng = random.Random(seed)
        gains = [rng.uniform(0.02, 0.05) for _ in range(rng.randint(3, 6))]
        steps, level = [0.5], 0.5
        for gn in gains:
            steps += [level] * rng.randint(0, 3)    # rejected steps between
            level += gn
            steps.append(level)
        v = mod.sustained_trend(make_run(incumbents=steps,
                                         attempts=len(steps)))
        share = max(gains) / sum(gains)
        want = share <= 0.5
        assert v.passed == want, (
            f"seed {seed}: accepts {[round(x, 3) for x in gains]} (largest "
            f"share {share:.0%}) should give passed={want}, got {v.passed}. "
            f"Rejected steps between accepts must not matter.")
    good = mod.sustained_trend(load("improver_good.jsonl"))
    lucky = mod.sustained_trend(load("improver_lucky.jsonl"))
    assert good.passed and not lucky.passed, "fixtures disagree"
    return f"good: {good.reason}\nlucky: {lucky.reason}"


# ── Milestone 4 ──────────────────────────────────────────────────────────
def m4():
    d = [0.06, 0.07, 0.08, 0.05, 0.07, 0.07]
    init = {f"h{i}": 0.5 for i in range(1, 7)}
    fin = {f"h{i}": 0.5 + x for i, x in enumerate(d, start=1)}
    run = make_run(initials=init, finals=fin)
    gain, half, n = mod.paired_gain(run)
    mean = sum(d) / 6
    sd = (sum((x - mean) ** 2 for x in d) / 5) ** 0.5
    want_half = 2.571 * sd / 6 ** 0.5
    assert n == 6 and near(gain, mean, 1e-9), \
        f"mean gain should be {mean:.4f} over 6 tasks, got {gain:.4f} (n={n})"
    assert near(half, want_half, 1e-4), \
        f"half-width should be t(5) = 2.571 x sd / sqrt(6) = " \
        f"{want_half:.4f}, got {half:.4f}"
    v = mod.generalisation(run)
    assert v.passed, f"a clear paired gain on 6 unseen tasks: {v.reason}"
    v = mod.generalisation(make_run(initials={"h1": .5, "h2": .5},
                                    finals={"h1": .6, "h2": .6}))
    assert not v.passed and "need" in v.reason, \
        f"two held-out tasks are fewer than MIN_PAIRS: {v}"
    v = mod.generalisation(make_run(initials=dict(init, s1=0.5),
                                    finals=dict(fin, s1=0.7)))
    assert not v.passed and "used in search" in v.reason, \
        f"s1 is a search task and appears in the evals: {v}"
    v = mod.generalisation(make_run(initials={"s1": .5}, finals={"s1": .7}))
    assert not v.passed and "no held-out tasks" in v.reason, \
        f"every evaluated task was searched on: {v}"
    swing = {f"h{i}": 0.5 + x for i, x in enumerate(
        [0.2, -0.1, 0.15, -0.05, 0.12, -0.08], start=1)}
    v = mod.generalisation(make_run(initials=init, finals=swing))
    assert not v.passed, "mean +0.04 but swinging by 0.15: the interval " \
        "reaches below zero, so it should fail"
    steady = {f"h{i}": 0.51 for i in range(1, 7)}
    v = mod.generalisation(make_run(initials=init, finals=steady))
    assert not v.passed, "a perfectly steady +0.01 is under MIN_GAIN (0.02)"
    for seed in seeds(range(1, 6)):
        rng = random.Random(seed)
        diffs = [rng.gauss(0.0, 0.03) for _ in range(8)]
        r = make_run(initials={f"h{i}": .5 for i in range(8)},
                     finals={f"h{i}": .5 + x for i, x in enumerate(diffs)})
        g, h, k = mod.paired_gain(r)
        assert k == 8 and near(g, sum(diffs) / 8, 1e-9), (
            f"seed {seed}: mean of {k} differences should be "
            f"{sum(diffs) / 8:.4f}, got {g:.4f}")
    fx = {n: mod.generalisation(load(n)) for n in
          ("improver_good.jsonl", "improver_leaky.jsonl",
           "improver_overfit.jsonl")}
    assert fx["improver_good.jsonl"].passed, fx["improver_good.jsonl"]
    assert not fx["improver_leaky.jsonl"].passed
    assert not fx["improver_overfit.jsonl"].passed
    return "\n".join(f"{k}: {v.reason}" for k, v in fx.items())


# ── Milestone 5 ──────────────────────────────────────────────────────────
def m5():
    ok = make_run(budget=10.0, attempts=5, incumbents=[.5] * 5,
                  costs=[2.0] * 5)
    v = mod.budget_ok(ok)
    assert v.passed, f"exactly $10.00 of $10 should pass: {v.reason}"
    over = make_run(budget=10.0, attempts=5, incumbents=[.5] * 5,
                    costs=[2.0, 2.0, 2.0, 2.5, 2.0])
    v = mod.budget_ok(over)
    assert not v.passed and "exceeded at step 5" in v.reason, \
        f"running total passes $10 at step 5 ($10.50): {v}"
    many = make_run(budget=100.0, attempts=3, incumbents=[.5] * 4,
                    costs=[1.0] * 4)
    v = mod.budget_ok(many)
    assert not v.passed and "attempts" in v.reason, \
        f"4 steps against 3 allowed attempts: {v}"
    base = load("baseline_fair.jsonl")
    card = mod.report_card(load("improver_good.jsonl"), base)
    assert list(card) == list(mod.CONDITIONS), \
        f"the card's keys should be CONDITIONS in order, got {list(card)}"
    assert all(v.passed for v in card.values()), "improver_good should pass"
    text = mod.render(card)
    assert text.splitlines()[-1] == "  Level 1: met", \
        f"last line should be '  Level 1: met', got {text.splitlines()[-1]!r}"
    assert text.count("PASS") == 4 and "FAIL" not in text
    expect = {"improver_lucky.jsonl": "sustained trend",
              "improver_overspend.jsonl": "fixed budget",
              "improver_leaky.jsonl": "generalisation"}
    for name, bad in expect.items():
        c = mod.report_card(load(name), base)
        failed = [k for k, v in c.items() if not v.passed]
        assert failed == [bad], \
            f"{name}: expected only {bad!r} to fail, got {failed}"
        out = mod.render(c)
        assert out.splitlines()[-1] == "  Level 1: NOT met" and \
            out.count("FAIL") == 1, f"{name}: render shows\n{out}"
    c = mod.report_card(load("improver_good.jsonl"),
                        load("baseline_short.jsonl"))
    assert [k for k, v in c.items() if not v.passed] == ["fair baseline"]
    return mod.render(mod.report_card(load("improver_overspend.jsonl"),
                                      base))


# ── Milestone 6 ──────────────────────────────────────────────────────────
def m6():
    table = [(False, 0.0, "none", 0), (True, 0.9, "none", 5),
             (True, 0.6, "approves", 4), (True, 0.4, "approves", 3),
             (True, 0.5, "directs", 3), (True, 0.49, "directs", 2),
             (True, 0.2, "drives", 2), (True, 0.1, "drives", 1)]
    for used, share, role, want in table:
        got = mod.task_level(used, share, role)
        assert got == want, (f"ai_used={used}, ai_share={share}, human_role="
                             f"{role!r}: expected level {want}, got {got}")
    loop = [dict(name="propose", ai_used=True, ai_share=0.9,
                 human_role="approves"),
            dict(name="run", ai_used=True, ai_share=1.0, human_role="none"),
            dict(name="decide", ai_used=True, ai_share=0.5,
                 human_role="directs"),
            dict(name="write-up", ai_used=True, ai_share=0.1,
                 human_role="drives")]
    levels, mean, weakest = mod.automation_level(loop)
    assert levels == {"propose": 4, "run": 5, "decide": 3, "write-up": 1}, \
        f"levels wrong: {levels}"
    assert near(mean, 3.25), f"mean of 4, 5, 3, 1 is 3.25, got {mean}"
    assert weakest == "write-up", \
        f"the weakest link is write-up, got {weakest!r}"
    tie = [dict(name="b", ai_used=False, ai_share=0, human_role="drives"),
           dict(name="a", ai_used=False, ai_share=0, human_role="drives")]
    assert mod.automation_level(tie)[2] == "a", \
        "ties go to the name that sorts first"
    return f"example loop: levels {levels}, mean {mean:.2f}, weakest {weakest}"


check(1, "Milestone 1: parse the run log", m1)
check(2, "Milestone 2: a fair baseline", m2)
check(3, "Milestone 3: a sustained trend, not a lucky accept", m3)
check(4, "Milestone 4: generalisation to tasks never searched", m4)
check(5, "Milestone 5: the budget and the report card", m5)
check(6, "Milestone 6: an automation level from a rubric", m6)

t = sum(1 for r in results if r)
print(f"\n{t}/{len(results)} milestones passing  "
      f"({time.process_time():.1f} s)")
sys.exit(0 if t == len(results) else 1)
