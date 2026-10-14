"""Self-check for Lab 4: Adaptive Branching over Many Models.

    python3 check.py                  # checks your starter.py
    python3 check.py solution         # checks the reference solution
    python3 check.py solution 3       # only milestone 3
    python3 check.py solution 3 7     # milestone 3, replaying ONLY the random cases of seed 7

Everything is seeded: the stand-in models, the answers' scores, the policies' draws. There is no network, no
clock and no real model, so the same code gives the same result on every run. The whole check finishes in
well under a minute (a few seconds for the reference solution).
Prints a tick, a cross, or "not implemented yet" for each milestone.
"""
import importlib
import math
import os
import random
import statistics
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


def mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs)


FAM = mod.FAMILIES
SEEDS = range(300)


def run_many(make_policy, family, budget, seeds_=SEEDS, stop=None):
    """Plain loop over seeds using only the GIVEN pieces and the policy (and your run_search)."""
    out = []
    for s in seeds_:
        out.append(mod.run_search(make_policy(), mod.Env(FAM[family], budget, s), random.Random(s + 7919), stop))
    return out


class Scripted:
    """A policy that plays a fixed list of actions and records what it is told."""

    def __init__(self, actions):
        self.actions, self.i, self.told, self.rngs = list(actions), 0, [], []

    def choose(self, env, rng):
        self.rngs.append(rng)
        a = self.actions[self.i]
        self.i += 1
        return a

    def observe(self, action, node, gain):
        self.told.append((action, node.id, node.score, gain))


# =============================================================================
# Milestone 1: the loop and two fixed strategies
# =============================================================================
def m1():
    # ---- closed forms
    assert near(mod.coverage(0.05, 20), 1 - 0.95 ** 20) and round(mod.coverage(0.05, 20), 2) == 0.64, "chapter 8: p = 0.05, n = 20 gives 0.64"
    assert round(mod.coverage(0.05, 45), 2) == 0.90 and near(mod.coverage(0.2, 1), 0.2) and near(mod.coverage(0.0, 10), 0.0) and near(mod.coverage(1.0, 3), 1.0), "coverage(p, n) = 1 - (1 - p) ** n"
    assert near(mod.expected_best_of_n(1), 1 / 3), "one fresh answer scores U**2, whose mean is 1/3"
    assert near(mod.expected_best_of_n(30), 30 / 32) and near(mod.expected_best_of_n(4, a=1.0), 0.8), "mean of the best of n draws of U**a is n / (n + a)"
    for n, a in [(5, 2.0), (12, 2.0), (10, 3.0)]:
        sim = mean(max(random.Random(1000 * s + i).random() ** a for i in range(n)) for s in range(3000))
        assert abs(sim - mod.expected_best_of_n(n, a)) < 0.012, \
            f"expected_best_of_n({n}, {a}) = {mod.expected_best_of_n(n, a):.4f} but simulating 3000 trials gives {sim:.4f}"

    # ---- the fixed strategies
    env = mod.Env(FAM["refinable"], 10, 1)
    rng = random.Random(0)
    assert mod.WiderOnly(2).choose(env, rng) == ("wider", 2) and mod.WiderOnly().choose(env, rng) == ("wider", 0), "WiderOnly(model) always asks for (\"wider\", model)"
    d = mod.DeeperOnly(1)
    assert d.choose(env, rng) == ("wider", 1), "DeeperOnly has nothing to refine on the first call: it asks for one fresh answer"
    for _ in range(4):
        env.apply(("wider", 0))
    best = max(env.nodes, key=lambda n: n.score)
    assert d.choose(env, rng) == ("deeper", best.id, 1), f"DeeperOnly must refine the best answer so far (node {best.id}); got {d.choose(env, rng)}"

    # ---- run_search by hand
    plan = [("wider", 0), ("wider", 1), ("deeper", 0, 2), ("wider", 2), ("deeper", 3, 1)]
    ref = mod.Env(FAM["refinable"], 5, 9)
    expect = []
    for a in plan:
        before = ref.best_score
        node = ref.apply(a)
        expect.append((a, node.id, node.score, max(0.0, node.score - before), ref.best_score, node.model))
    pol = Scripted(plan)
    rng = random.Random(5)
    res = mod.run_search(pol, mod.Env(FAM["refinable"], 5, 9), rng)
    assert res.calls == 5 and len(res.log) == 5 and pol.i == 5, f"a budget of 5 means exactly 5 calls; made {res.calls} (log of {len(res.log)})"
    assert all(r is rng for r in pol.rngs), "pass the SAME rng object you were given to policy.choose on every call"
    for k, (a, nid, sc, gain, best_after, model) in enumerate(expect):
        st = res.log[k]
        assert (st.call, st.action, st.node, st.model) == (k + 1, a, nid, model), f"step {k + 1}: log entry is {st}, expected call {k + 1}, action {a}, node {nid}, model {model}"
        assert near(st.score, sc) and near(st.gain, gain) and near(st.best, best_after), \
            f"step {k + 1}: score {st.score:.4f} gain {st.gain:.4f} best {st.best:.4f}; expected {sc:.4f} {gain:.4f} {best_after:.4f}. gain = max(0, score - best BEFORE this call), and the best before the first call is 0"
        told = pol.told[k]
        assert told[0] == a and told[1] == nid and near(told[3], gain), f"step {k + 1}: observe must be called with (action, node, gain); got {told}"
    assert near(res.best, ref.best_score) and near(res.spend, ref.spent) and res.solved is False, "SearchResult: best, calls, spend; solved is False without a target"
    assert near(res.spend, sum(mod.FAMILIES["refinable"].models[s.model].cost for s in res.log)), 'res.spend must add up the cost of the model used at every call'
    # early stopping at a target
    tgt = expect[2][4]
    first = next(k for k, e in enumerate(expect) if e[4] >= tgt)
    res2 = mod.run_search(Scripted(plan), mod.Env(FAM["refinable"], 5, 9), random.Random(5), target=tgt)
    assert res2.calls == first + 1 and res2.solved is True and len(res2.log) == first + 1, \
        f"with target {tgt:.3f} the search should stop right after call {first + 1}; it made {res2.calls} calls (solved={res2.solved})"
    res3 = mod.run_search(Scripted(plan), mod.Env(FAM["refinable"], 5, 9), random.Random(5), target=2.0)
    assert res3.calls == 5 and res3.solved is False, "an unreachable target uses the whole budget and is not solved"
    # budget exhausted: the environment refuses a sixth call
    e5 = mod.Env(FAM["refinable"], 2, 0)
    mod.run_search(Scripted(plan), e5, random.Random(0))
    try:
        e5.apply(("wider", 0))
    except mod.BudgetExhausted:
        pass
    else:
        raise AssertionError("the environment should refuse a call beyond the budget")

    # ---- the two worlds
    note = []
    for fam, model, budget in [("refinable", 1, 20), ("lottery", 1, 20)]:
        wide = mean(r.best for r in run_many(lambda: mod.WiderOnly(model), fam, budget))
        deep = mean(r.best for r in run_many(lambda: mod.DeeperOnly(model), fam, budget))
        note.append(f"{fam:10s} 20 calls, mean best score:  always wider {wide:.3f}   always deeper {deep:.3f}")
        if fam == "refinable":
            assert deep > wide + 0.03, f"refinable: refining the best answer should clearly beat fresh samples (wider {wide:.3f}, deeper {deep:.3f})"
        else:
            assert wide > deep + 0.15, f"lottery: refining is a waste when feedback is useless (wider {wide:.3f}, deeper {deep:.3f})"
            f = mod.expected_best_of_n(20, FAM[fam].models[model].fresh_a)
            assert abs(wide - f) < 0.015, f"the wider-only mean {wide:.3f} should match the closed form {f:.3f}"
            note.append(f"           closed form for always wider: {f:.3f}")
    return "\n".join(note)


# =============================================================================
# Milestone 2: wider or deeper, learned from gains
# =============================================================================
def seeded_env(n_nodes=6, family="refinable", seed=3, budget=40):
    env = mod.Env(FAM[family], budget, seed)
    for i in range(n_nodes):
        env.apply(("wider", 0) if i < 4 else ("deeper", env.best.id, 0))
    return env


def m2():
    # ---- shrunk_mean, by hand
    assert near(mod.shrunk_mean([]), 0.1), "no data: the prior mean"
    assert near(mod.shrunk_mean([0.3]), (0.2 + 0.3) / 3) and near(mod.shrunk_mean([0, 0, 0, 0]), 0.2 / 6), 'shrunk_mean = (prior_mean * prior_weight + sum(history)) / (len(history) + prior_weight): [0.3] gives 0.5/3, four zeros give 0.2/6'
    assert near(mod.shrunk_mean([1, 1], prior_mean=0.5, prior_weight=4), (2 + 2) / 6), "prior_mean and prior_weight are parameters"
    # ---- thompson_draw: exactly one gauss call with the right mean and spread
    for hist, kw in [([], {}), ([0.2, 0.0, 0.1], {}), ([0.05] * 8, {}), ([0.4], {"scale": 0.1, "prior_mean": 0.3, "prior_weight": 5})]:
        for s in seeds((1, 2, 3)):
            r1, r2 = random.Random(s), random.Random(s)
            got = mod.thompson_draw(hist, r1, **kw)
            pm, pw, sc = kw.get("prior_mean", 0.1), kw.get("prior_weight", 2), kw.get("scale", 0.2)
            want = r2.gauss((pm * pw + sum(hist)) / (len(hist) + pw), sc / math.sqrt(len(hist) + 1))
            assert near(got, want), (f"history {hist}, seed {s}: expected rng.gauss(shrunk mean, scale / sqrt(n + 1)) = {want:.6f}, got {got:.6f}")
            assert r1.getstate() == r2.getstate(), "make exactly ONE call to rng.gauss per draw (and no other random calls)"
    draws = [mod.thompson_draw([0.1] * 3, random.Random(s)) for s in range(4000)]
    assert abs(mean(draws) - (0.2 + 0.3) / 5) < 0.01 and abs(statistics.pstdev(draws) - 0.1) < 0.01, "3 observations of 0.1: mean 0.1, spread 0.2 / 2 = 0.1"

    # ---- TwoArmPolicy.choose / observe against a replica
    env = seeded_env()
    pol = mod.TwoArmPolicy(2)
    assert pol.choose(mod.Env(FAM["refinable"], 5, 0), random.Random(0)) == ("wider", 2), "with no answers yet, ask for a fresh one from the policy's model"
    assert set(pol.hist) == {"wider", "deeper"}, "the policy keeps self.hist = {'wider': [...], 'deeper': [...]}"
    pol.hist = {"wider": [0.0, 0.1, 0.0], "deeper": [0.3, 0.2]}
    best_id = env.best.id
    seen = set()
    for s in seeds(range(60)):
        r1, r2 = random.Random(s), random.Random(s)
        act = pol.choose(env, r1)
        w, d = mod.thompson_draw(pol.hist["wider"], r2), mod.thompson_draw(pol.hist["deeper"], r2)
        want = ("wider", 2) if w >= d else ("deeper", best_id, 2)
        assert act == want, f"seed {s}: draws were wider {w:.4f}, deeper {d:.4f}, so the action should be {want}; got {act}. Draw wider first, then deeper, and refine the best answer (node {best_id})"
        seen.add(act[0])
    assert seen == {"wider", "deeper"}, "with these histories both actions should be chosen sometimes"
    p2 = mod.TwoArmPolicy(0)
    p2.observe(("wider", 0), env.nodes[0], 0.25)
    p2.observe(("deeper", 3, 0), env.nodes[1], 0.0)
    p2.observe(("wider", 0), env.nodes[2], 0.5)
    assert p2.hist == {"wider": [0.25, 0.5], "deeper": [0.0]}, f"observe appends the gain to the history of the action's kind; got {p2.hist}"
    # ---- it reacts to evidence
    pol = mod.TwoArmPolicy(0)
    pol.hist = {"wider": [0.0] * 30, "deeper": [0.3] * 30}
    deeper = sum(pol.choose(env, random.Random(s))[0] == "deeper" for s in seeds(range(300)))
    assert ONLY_SEED is not None or deeper >= 280, f"30 observations of deeper paying 0.3 and wider paying 0 should send nearly every call deeper; {deeper}/300 did"
    pol.hist = {"wider": [0.3] * 30, "deeper": [0.0] * 30}
    wider = sum(pol.choose(env, random.Random(s))[0] == "wider" for s in seeds(range(300)))
    assert ONLY_SEED is not None or wider >= 280, f"and the reverse: {wider}/300 went wider"

    # ---- the scenario: no fixed strategy wins in both worlds; the adaptive one nearly does
    note, rows = [], {}
    for fam in ("refinable", "lottery"):
        w = mean(r.best for r in run_many(lambda: mod.WiderOnly(1), fam, 20))
        dp = mean(r.best for r in run_many(lambda: mod.DeeperOnly(1), fam, 20))
        ad = mean(r.best for r in run_many(lambda: mod.TwoArmPolicy(1), fam, 20))
        rows[fam] = (w, dp, ad)
        note.append(f"{fam:10s} 20 calls, mean best score:  always wider {w:.3f}   always deeper {dp:.3f}   adaptive {ad:.3f}")
    w, dp, ad = rows["refinable"]
    assert ad >= dp - 0.02 and ad > w + 0.03, f"refinable: the adaptive policy should be close to always-deeper ({dp:.3f}) and far above always-wider ({w:.3f}); got {ad:.3f}"
    w, dp, ad = rows["lottery"]
    assert ad >= w - 0.03 and ad > dp + 0.15, f"lottery: the adaptive policy should be close to always-wider ({w:.3f}) and far above always-deeper ({dp:.3f}); got {ad:.3f}"
    return "\n".join(note)


# =============================================================================
# Milestone 3: which answer to refine
# =============================================================================
def m3():
    # ---- the weights of chapter 10's table
    scores, kids = [0.92, 0.90, 0.85, 0.80, 0.70, 0.40], [9, 7, 1, 0, 0, 0]
    for lam, want in [(10, [0.065, 0.076, 0.253, 0.393, 0.200, 0.013]), (30, [0.106, 0.127, 0.381, 0.360, 0.026, 0.000])]:
        got = mod.parent_weights(scores, kids, lam)
        assert near(sum(got), 1.0) and all(abs(g - w) < 0.0006 for g, w in zip(got, want)), \
            f"chapter 10's table for lambda = {lam} is {want}; parent_weights gives {[round(g, 3) for g in got]}. weight = sigmoid(lam * (score - MEDIAN)) / (1 + kids), then normalise"
    assert near(mod.parent_weights([0.5, 0.5], [0, 3])[0], 0.8) and near(mod.parent_weights([0.5, 0.5], [0, 3])[1], 0.2), "equal scores, 0 and 3 children: weights 1 and 1/4, so 0.8 and 0.2"
    assert mod.parent_weights([0.7], [5]) == [1.0] or near(mod.parent_weights([0.7], [5])[0], 1.0), 'a single node gets all the weight'
    u = mod.parent_weights([0.3, 0.3, 0.3, 0.3], [0, 0, 0, 0])
    assert all(near(x, 0.25) for x in u), 'equal scores and no children: equal weights'
    hi = mod.parent_weights([0.9, 0.1], [0, 0], lam=50)
    assert hi[0] > 0.99 - 0.0, f"a large lambda should concentrate on the higher score; got {hi}"
    # ---- pick_parent returns an id, not an index, with the right frequencies
    nodes = [mod.Node(10 + i, None, sc, 1.0, 0, 0, k) for i, (sc, k) in enumerate(zip(scores, kids))]
    want = mod.parent_weights(scores, kids, 10)
    for s in seeds((4,)):
        rng = random.Random(s)
        count = {n.id: 0 for n in nodes}
        N = 4000
        for _ in range(N):
            count[mod.pick_parent(nodes, rng, 10.0)] += 1
        assert set(count) == {n.id for n in nodes}, "pick_parent must return a node's .id (these ids are 10 to 15), not its position in the list"
        for n, w in zip(nodes, want):
            assert abs(count[n.id] / N - w) < 0.03, (f"seed {s}: node {n.id} (score {n.score}, {n.kids} children) should be chosen with probability {w:.3f}; "
                                                     f"observed {count[n.id] / N:.3f}")
    assert mod.pick_parent(nodes, random.Random(1)) == mod.pick_parent(nodes, random.Random(1)), "deterministic given the rng"
    # ---- wired into the policy
    env = seeded_env(8)
    greedy, weighted = mod.TwoArmPolicy(0), mod.TwoArmPolicy(0, lam=10.0)
    for p in (greedy, weighted):
        p.hist = {"wider": [0.0] * 30, "deeper": [0.3] * 30}
    ids_g = {greedy.choose(env, random.Random(s)) for s in seeds(range(100))}
    assert ids_g == {("deeper", env.best.id, 0)}, f"with lam=None the policy refines the best answer (node {env.best.id}) every time; got {ids_g}"
    w = mod.parent_weights([n.score for n in env.nodes], [n.kids for n in env.nodes], 10.0)
    cnt = {}
    N = 3000
    for s in range(N):
        act = weighted.choose(env, random.Random(s))
        assert act[0] == "deeper" and act[2] == 0, "a deeper action is ('deeper', node_id, model)"
        cnt[act[1]] = cnt.get(act[1], 0) + 1
    for n, wi in zip(env.nodes, w):
        assert abs(cnt.get(n.id, 0) / N - wi) < 0.04, f"with lam=10 node {n.id} should be refined with probability about {wi:.3f}; observed {cnt.get(n.id, 0) / N:.3f}"
    # ---- the scenario: ceilings that differ, so greedy refinement gets stuck on a dead end
    P = FAM["plateau"]
    diffs, gs, ws = [], [], []
    for s in seeds(range(500)):
        a = mod.run_search(mod.TwoArmPolicy(0), mod.Env(P, 30, s), random.Random(s + 7919)).best
        b = mod.run_search(mod.TwoArmPolicy(0, lam=10.0), mod.Env(P, 30, s), random.Random(s + 7919)).best
        gs.append(a), ws.append(b), diffs.append(b - a)
    m = mean(diffs)
    if ONLY_SEED is None:
        assert m > 0.01, (f"plateau world, 30 calls: refining a sampled parent with the weighted rule should beat always refining the best answer "
                          f"by at least 0.01 on average; difference {m:.4f}")
    return (f"plateau world (hidden ceilings), 30 calls, 500 seeds, mean best score:\n"
            f"always refine the best answer {mean(gs):.3f}   weighted parent (lam 10) {mean(ws):.3f}   paired difference {m:+.3f}")


# =============================================================================
# Milestone 4: many models
# =============================================================================
def m4():
    pol = mod.MultiModelPolicy(3)
    assert pol.arms == [("wider", 0), ("deeper", 0), ("wider", 1), ("deeper", 1), ("wider", 2), ("deeper", 2)] and set(pol.hist) == set(pol.arms), "the arms are given: (kind, model) pairs in a fixed order"
    # ---- the first call: only wider arms, by draw, in arm order
    empty = mod.Env(FAM["split"], 10, 0)
    chosen = set()
    for s in seeds(range(40)):
        pol = mod.MultiModelPolicy(3)
        pol.hist[("wider", 1)] = [0.2, 0.2]
        r1, r2 = random.Random(s), random.Random(s)
        act = pol.choose(empty, r1)
        draws = [mod.thompson_draw(pol.hist[a], r2) for a in pol.arms if a[0] == "wider"]
        want = ("wider", max(range(3), key=lambda m: (draws[m], -m)))
        assert act == want, f"seed {s}: first call, wider-arm draws {[round(d, 3) for d in draws]}: expected {want}, got {act}"
        assert r1.getstate() == r2.getstate(), "on the first call draw once per WIDER arm only (3 draws for 3 models), nothing else"
        chosen.add(act[1])
    assert len(chosen) >= 2, "different seeds should sometimes pick different models on the first call"
    # ---- later calls: one draw per arm, in arm order
    env = seeded_env(6, "split")
    best_id = env.best.id
    kinds = set()
    for s in seeds(range(60)):
        rr = random.Random(1000 + s)
        pol = mod.MultiModelPolicy(3)
        for a in pol.arms:
            pol.hist[a] = [round(rr.random() * 0.3, 3) for _ in range(rr.randint(0, 4))]
        r1, r2 = random.Random(s), random.Random(s)
        act = pol.choose(env, r1)
        draws = [mod.thompson_draw(pol.hist[a], r2) for a in pol.arms]
        k = max(range(6), key=lambda i: (draws[i], -i))
        kind, m = pol.arms[k]
        want = ("wider", m) if kind == "wider" else ("deeper", best_id, m)
        assert act == want, f"seed {s}: arm draws {[round(d, 3) for d in draws]} pick arm {pol.arms[k]}, so the action is {want}; got {act}"
        assert r1.getstate() == r2.getstate(), "one draw per arm (6 here), in arm order, and no other random numbers when lam is None"
        kinds.add(act[0])
    assert kinds == {"wider", "deeper"}, 'over 60 seeds both kinds of action should be chosen sometimes'
    # a learned preference
    pol = mod.MultiModelPolicy(3)
    pol.hist = {a: [0.0] * 20 for a in pol.arms}
    pol.hist[("deeper", 1)] = [0.3] * 20
    top = sum(pol.choose(env, random.Random(s)) == ("deeper", best_id, 1) for s in seeds(range(300)))
    assert ONLY_SEED is not None or top >= 270, f"an arm that has paid 0.3 twenty times among arms that paid nothing should win nearly every draw; won {top}/300"
    # lam wires in the weighted parent rule
    polw = mod.MultiModelPolicy(3, lam=10.0)
    polw.hist = {a: [0.0] * 20 for a in polw.arms}
    polw.hist[("deeper", 2)] = [0.3] * 20
    parents = {polw.choose(env, random.Random(s))[1] for s in seeds(range(200))}
    assert len(parents) > 1 or ONLY_SEED is not None, "with lam=10 the parent is sampled, so several different nodes should be refined"
    # ---- observe
    p = mod.MultiModelPolicy(3)
    p.observe(("wider", 2), env.nodes[0], 0.4)
    p.observe(("deeper", 5, 1), env.nodes[0], 0.1)
    p.observe(("deeper", 0, 1), env.nodes[0], 0.0)
    assert p.hist[("wider", 2)] == [0.4] and p.hist[("deeper", 1)] == [0.1, 0.0] and sum(len(v) for v in p.hist.values()) == 3, \
        "observe files the gain under the arm (kind, model): ('wider', 2) -> hist[('wider', 2)]; ('deeper', 5, 1) -> hist[('deeper', 1)] (the model is the LAST element of an action)"
    # ---- model_shares
    S = lambda kind, model: mod.Step(1, (kind, 0, model) if kind == "deeper" else (kind, model), 0, model, 0.5, 0.1, 0.5)
    log = [S("wider", 0), S("wider", 2), S("wider", 2), S("deeper", 1), S("wider", 2), S("deeper", 1), S("deeper", 0)]
    assert mod.model_shares(log, "wider", 3) == [0.25, 0.0, 0.75], f"wider calls by model: 1 of 4 used model 0 and 3 of 4 model 2; got {mod.model_shares(log, 'wider', 3)}"
    sh = mod.model_shares(log, "deeper", 3)
    assert [round(x, 4) for x in sh] == [0.3333, 0.6667, 0.0] and mod.model_shares([], "deeper", 3) == [0.0, 0.0, 0.0] and mod.model_shares(log[:3], "deeper", 2) == [0.0, 0.0], 'model_shares: fractions of the steps of that kind, per model, zeros when there are none or the kind is absent'

    # ---- the scenario: a world where no single model can do both jobs
    B = 40
    note = []
    multi = run_many(lambda: mod.MultiModelPolicy(3), "split", B, stop=mod.TARGET)
    singles = {}
    for m in range(3):
        singles[m] = run_many(lambda: mod.TwoArmPolicy(m), "split", B, stop=mod.TARGET)
    sr = lambda rs: mean(r.solved for r in rs)
    best_m = max(singles, key=lambda m: sr(singles[m]))
    for m in range(3):
        note.append(f"one model only ({FAM['split'].models[m].name:10s}) solves {sr(singles[m]):.2f}  mean best {mean(r.best for r in singles[m]):.3f}  median calls used {statistics.median(r.calls for r in singles[m]):.0f}")
    note.append(f"all three models, as arms       solves {sr(multi):.2f}  mean best {mean(r.best for r in multi):.3f}  median calls used {statistics.median(r.calls for r in multi):.0f}")
    if ONLY_SEED is None:
        assert sr(multi) >= sr(singles[best_m]) + 0.1, (f"split world, {B} calls: choosing among models should solve at least 0.10 more tasks than the best single model "
                                                         f"({FAM['split'].models[best_m].name}: {sr(singles[best_m]):.2f}); got {sr(multi):.2f}")
    log = [s for r in multi for s in r.log]
    dsh = mod.model_shares(log, "deeper", 3)
    note.append("share of deeper calls by model: " + ", ".join(f"{FAM['split'].models[m].name} {dsh[m]:.2f}" for m in range(3)))
    if ONLY_SEED is None:
        assert dsh[1] > dsh[0] and dsh[1] > dsh[2], f"the editor (model 1) repairs best, so it should get the largest share of deeper calls; shares {dsh}"
    return "\n".join(note)


# =============================================================================
# Milestone 5: an honest scoreboard
# =============================================================================
def R(best, calls, solved, spend=0.0):
    return mod.SearchResult(best, calls, spend, solved, [])


def m5():
    rs = [R(0.9, 5, True), R(0.5, 12, False), R(0.95, 9, True), R(0.4, 12, False)]
    assert mod.solve_rate(rs) == 0.5 and mod.solve_rate(rs[:1]) == 1.0 and mod.solve_rate(rs[1:2]) == 0.0, 'solve_rate is the fraction of results with solved == True'
    assert mod.calls_to_solve([R(1, 5, True), R(0, 7, False), R(0, 9, False), R(1, 12, True)]) == 12.5, \
        "unsolved runs count as (largest calls used + 1) = 13: the values 5, 13, 13, 12 have median 12.5"
    assert mod.calls_to_solve([R(1, 5, True), R(0, 7, False), R(0, 9, False), R(1, 12, True)], penalty=100) == 56, 'unsolved runs count as `penalty` calls when it is given: the values 5, 100, 100, 12 have median 56'
    assert mod.calls_to_solve([R(1, 5, True), R(1, 7, True), R(1, 9, True)]) == 7, 'the median of calls when all runs are solved'
    m, hw = mod.mean_ci([1, 2, 3, 4])
    assert near(m, 2.5) and near(hw, 1.96 * math.sqrt(5 / 3) / 2), f"mean_ci([1, 2, 3, 4]) = (2.5, {1.96 * math.sqrt(5 / 3) / 2:.4f}) with the SAMPLE standard deviation (divide by n - 1); got ({m}, {hw})"
    assert mod.mean_ci([7.0]) == (7.0, 0.0) and near(mod.mean_ci([1, 2, 3, 4], z=1.0)[1], math.sqrt(5 / 3) / 2), 'mean_ci of one value is (value, 0.0); z scales the half-width'
    m, hw = mod.mean_ci([0.5] * 10)
    assert near(m, 0.5) and hw == 0.0, 'identical values have a zero-width interval'

    # ---- evaluate_policy against a manual replica
    task, B, sd = FAM["lottery"], 15, range(7, 19)
    ev = mod.evaluate_policy(lambda: mod.TwoArmPolicy(1), task, B, sd, target=0.9)
    assert set(ev) >= {"best", "solve_rate", "calls", "spend", "runs"} and len(ev["runs"]) == 12, 'evaluate_policy returns a dict with best, solve_rate, calls, spend and runs (one result per seed)'
    manual = [mod.run_search(mod.TwoArmPolicy(1), mod.Env(task, B, s), random.Random(s + 7919), 0.9) for s in sd]
    for a, b in zip(ev["runs"], manual):
        assert (a.best, a.calls, a.solved) == (b.best, b.calls, b.solved) and near(a.spend, b.spend), \
            "run i uses Env(task, budget, seed) and random.Random(seed + 7919), a FRESH policy from make_policy(), and the target for early stopping"
    assert ev["solve_rate"] == mod.solve_rate(manual) and ev["calls"] == mod.calls_to_solve(manual), 'solve_rate and calls must be computed with your solve_rate and calls_to_solve'
    assert ev["best"] == mod.mean_ci([r.best for r in manual]) and near(ev["spend"], mean(r.spend for r in manual)), 'best is mean_ci of the best scores; spend is the mean spend'
    assert all(r.calls <= B for r in ev["runs"]), "the budget is never exceeded"
    assert ev["runs"][0] is not ev["runs"][1], 'each run needs its own fresh policy: call make_policy() once per seed'

    # ---- the scoreboard
    rows = []
    sol = {}
    specs = [("refinable", 20, 2), ("lottery", 20, 2), ("plateau", 30, 0), ("split", 40, 0)]
    for fam, B, best_single in specs:
        t = FAM[fam]
        n = len(t.models)
        w = mod.evaluate_policy(lambda: mod.WiderOnly(best_single), t, B, SEEDS, mod.TARGET)
        a = mod.evaluate_policy(lambda: mod.TwoArmPolicy(best_single), t, B, SEEDS, mod.TARGET)
        mm = mod.evaluate_policy(lambda: mod.MultiModelPolicy(n), t, B, SEEDS, mod.TARGET)
        sol[fam] = (w, a, mm)
        for r in (w, a, mm):
            assert all(x.calls <= B for x in r["runs"]), 'the budget is never exceeded'
            assert all(near(x.spend, sum(t.models[s.model].cost for s in x.log)) for x in r["runs"][:20]), "spend is the sum of the costs of the models called"
        rows.append(f"{fam:10s} {B} calls   solved at {mod.TARGET}: wider {w['solve_rate']:.2f}  adaptive {a['solve_rate']:.2f}  all models {mm['solve_rate']:.2f}"
                    f"   median calls: {w['calls']:.0f} / {a['calls']:.0f} / {mm['calls']:.0f}")
    w, a, mm = sol["split"]
    ind = lambda r: mod.mean_ci([1.0 if x.solved else 0.0 for x in r["runs"]])
    (m_multi, h_multi), (m_one, h_one) = ind(mm), ind(a)
    if ONLY_SEED is None:
        assert m_multi - h_multi > m_one + h_one, (f"split world: the intervals for 'all models' ({m_multi:.2f} +- {h_multi:.2f}) and the best single model "
                                                    f"({m_one:.2f} +- {h_one:.2f}) should not overlap")
        assert sol["refinable"][0]["solve_rate"] < sol["refinable"][1]["solve_rate"], "refinable: adaptive beats always-wider"
        assert sol["lottery"][1]["solve_rate"] > 0.5 * sol["lottery"][0]["solve_rate"], "lottery: adaptive stays near always-wider"
    rows.append(f"split world, solve rate with 95% intervals: all models {m_multi:.2f} +- {h_multi:.2f}, best single model {m_one:.2f} +- {h_one:.2f}")
    lot = sol["lottery"]
    rows.append(f"the price of choice: in the lottery world six arms cost exploration: all models {lot[2]['solve_rate']:.2f} vs one model's wider sampler {lot[0]['solve_rate']:.2f}")
    return "\n".join(rows)


MILESTONES = [
    (1, "Milestone 1: the loop, and the two fixed strategies", m1),
    (2, "Milestone 2: wider or deeper, learned from gains", m2),
    (3, "Milestone 3: which answer to refine", m3),
    (4, "Milestone 4: many models as arms", m4),
    (5, "Milestone 5: an honest scoreboard", m5),
]

if __name__ == "__main__":
    t0 = time.time()
    print(f"Lab 4 checks against {target}.py\n")
    for n, name, fn in MILESTONES:
        check(n, name, fn)
    print(f"\n{sum(results)}/{len(results)} milestones passing  ({time.time() - t0:.1f} s)")
    sys.exit(0 if all(results) else 1)
