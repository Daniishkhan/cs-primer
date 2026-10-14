"""Self-check for Lab 5: Evolutionary Model Merging.

    python3 check.py                  # checks your starter.py
    python3 check.py solution         # checks the reference solution
    python3 check.py solution 5       # only milestone 5
    python3 check.py solution 3 7     # milestone 3, replaying ONLY the random cases of seed 7

Everything is seeded: the worlds (base model, specialists, search and held-out splits), the
evolution runs and every random test input. There is no network and no clock, so every run gives
identical numbers. The whole check takes about ten seconds.
Prints a tick, a cross, or "not implemented yet" for each milestone.
"""
import copy
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


def models_near(a, b, tol=1e-9):
    return len(a) == len(b) and all(len(x) == len(y) and all(near(u, v, tol) for u, v in zip(x, y)) for x, y in zip(a, b))


_WORLDS = {}


def world(seed, n_search=20):
    key = (seed, n_search)
    if key not in _WORLDS:
        _WORLDS[key] = mod.make_world(seed, n_search=n_search)
    return _WORLDS[key]


def rand_model(rng, sizes=(5, 2, 4, 3)):
    return [[rng.uniform(-1, 1) for _ in range(n)] for n in sizes]


# =============================================================================
# Milestone 1: vectors of weights
# =============================================================================
def m1():
    assert mod.task_vector([[3.0, 1.0], [2.0]], [[1.0, 1.0], [5.0]]) == [[2.0, 0.0], [-3.0]], "task_vector: finetuned minus base, tensor by tensor"
    assert mod.add_scaled([[1.0, 2.0]], [[4.0, -2.0]], 0.5) == [[3.0, 1.0]], "add_scaled([[1,2]], [[4,-2]], 0.5) should be [[3, 1]]"
    assert mod.average_models([[[1.0, 2.0], [3.0]], [[3.0, 6.0], [5.0]]]) == [[2.0, 4.0], [4.0]], "average of two tiny models"
    avg3 = mod.average_models([[[0.0]], [[3.0]], [[6.0]]])
    assert near(avg3[0][0], 3.0), f"average of three models: expected 3.0, got {avg3[0][0]}"
    a, b = [[0.0, 10.0], [2.0]], [[4.0, 20.0], [6.0]]
    assert mod.interpolate(a, b, 0.0) == a and mod.interpolate(a, b, 1.0) == b, "interpolate: t = 0 gives a, t = 1 gives b"
    assert mod.interpolate(a, b, 0.25) == [[1.0, 12.5], [3.0]], "interpolate at t = 0.25"
    assert mod.interpolate(a, b, 2.0) == [[8.0, 30.0], [10.0]], "t outside [0, 1] extrapolates: (1 - t) a + t b"
    assert near(mod.vec_norm([[3.0], [4.0]]), 5.0), "vec_norm([[3], [4]]) is 5: the norm runs over ALL tensors"
    assert near(mod.cosine([[1.0, 0.0]], [[0.0, 1.0]]), 0.0) and near(mod.cosine([[1.0, 2.0]], [[2.0, 4.0]]), 1.0)
    assert near(mod.cosine([[1.0], [1.0]], [[-1.0], [-1.0]]), -1.0), "opposite vectors have cosine -1"
    assert mod.cosine([[0.0, 0.0]], [[1.0, 1.0]]) == 0.0, "cosine with a zero vector is 0.0, not a division error"

    for s in seeds(range(1, 31)):
        rng = random.Random(s)
        base, ft = rand_model(rng), rand_model(rng)
        keep_base, keep_ft = copy.deepcopy(base), copy.deepcopy(ft)
        tv = mod.task_vector(ft, base)
        assert base == keep_base and ft == keep_ft, f"seed {s}: task_vector must not modify its inputs"
        back = mod.add_scaled(base, tv, 1.0)
        assert models_near(back, ft, 1e-12), f"seed {s}: base + (ft - base) should give ft back"
        assert models_near(mod.add_scaled(base, tv, 0.0), base), f"seed {s}: scale 0 gives the base"
        assert back is not base and all(x is not y for x, y in zip(back, base)), f"seed {s}: return NEW lists, not the input tensors"
        half = mod.interpolate(base, ft, 0.5)
        assert models_near(half, mod.average_models([base, ft]), 1e-12), f"seed {s}: interpolate(a, b, 0.5) is the average of a and b"
        assert models_near(half, mod.add_scaled(base, tv, 0.5), 1e-12), f"seed {s}: the midpoint is base + 0.5 * task vector"
        assert near(mod.vec_norm(mod.add_scaled(base, tv, 3.0)), mod.vec_norm([[b + 3 * v for b, v in zip(x, y)] for x, y in zip(base, tv)]), 1e-9)
        n = mod.vec_norm(tv)
        assert near(mod.cosine(tv, tv), 1.0, 1e-9) and near(mod.vec_norm(mod.add_scaled([[0.0] * len(t) for t in tv], tv, -2.0)), 2 * n, 1e-9), \
            f"seed {s}: cosine(tv, tv) is 1 and scaling by -2 doubles the norm"

    # Scenario 1: why merging needs a common ancestor.
    rows, drop_same, drop_indep = [], [], []
    for s in seeds(range(4)):
        means = mod.make_means(s)
        r = random.Random(s + 50)
        xs, ys = mod.sample(means, list(range(mod.K)), 240, r)
        xt, yt = mod.sample(means, list(range(mod.K)), 600, r)
        start = mod.train(mod.init_model(r), xs, ys, 40, 0.05, r)
        f1, f2 = (mod.train(start, xs, ys, 200, 0.05, random.Random(k)) for k in (1, 2))
        i1, i2 = (mod.train(mod.init_model(random.Random(k)), xs, ys, 240, 0.05, random.Random(k + 2)) for k in (11, 12))
        for (u, v), bucket in (((f1, f2), drop_same), ((i1, i2), drop_indep)):
            ends = (mod.accuracy(u, xt, yt) + mod.accuracy(v, xt, yt)) / 2
            mid = mod.accuracy(mod.interpolate(u, v, 0.5), xt, yt)
            bucket.append(ends - mid)
    ds, di = sum(drop_same) / len(drop_same), sum(drop_indep) / len(drop_indep)
    assert ds < di, (f"the midpoint of two fine-tunes of ONE base lost {ds:.3f} accuracy on average, the midpoint of two independent "
                     f"runs lost {di:.3f}: the shared ancestor should make the first loss smaller. Check interpolate.")

    # Scenario 2: the specialists' task vectors, measured.
    cos = []
    for s in seeds(range(3)):
        w = world(s)
        tvs = [mod.task_vector(ft, w.base) for ft in w.finetunes]
        cos.append(max(abs(mod.cosine(tvs[a], tvs[b])) for a in range(3) for b in range(a)))
        assert all(mod.vec_norm(t) > 0 for t in tvs), "fine-tuning moved the weights, so the norm cannot be 0"
    w = world(0)
    tvs = [mod.task_vector(ft, w.base) for ft in w.finetunes]
    return (f"midpoint accuracy drop, 4 worlds: {100 * ds:.1f} points for two fine-tunes of one base, {100 * di:.1f} points for two independent runs\n"
            f"world 0: {mod.n_params(w.base)} weights; task-vector norms {', '.join(f'{mod.vec_norm(t):.2f}' for t in tvs)}; "
            f"largest |cosine| between two task vectors {cos[0]:.2f}")


# =============================================================================
# Milestone 2: task arithmetic with per-layer coefficients
# =============================================================================
def flat_merge(base, tvs, coeffs):
    """An independent merge written over flat position lists, for cross-checking."""
    layer = [0, 0, 1, 1]
    out = []
    for k in range(4):
        row = list(base[k])
        for t in range(len(tvs)):
            for i in range(len(row)):
                row[i] += coeffs[t][layer[k]] * tvs[t][k][i]
        out.append(row)
    return out


def m2():
    cv = mod.coeffs_from_vector
    assert cv([0.7], "global") == [[0.7, 0.7]] * 3, "mode 'global': every task and layer gets w[0]"
    assert cv([1.0, 2.0, 3.0], "task") == [[1.0, 1.0], [2.0, 2.0], [3.0, 3.0]], "mode 'task': coeffs[t][l] = w[t]"
    assert cv([1, 2, 3, 4, 5, 6], "layer") == [[1, 2], [3, 4], [5, 6]], "mode 'layer': coeffs[t][l] = w[t * N_LAYERS + l]"
    for bad, mode in [([0.1, 0.2], "global"), ([0.1] * 5, "layer"), ([0.1] * 3, "layer"), ([0.5], "nope")]:
        try:
            cv(bad, mode)
        except ValueError:
            continue
        raise AssertionError(f"coeffs_from_vector({bad!r}, {mode!r}) must raise ValueError (wrong length or unknown mode)")

    base = [[1.0, 2.0], [3.0], [4.0, 5.0], [6.0]]
    tvs = [[[1.0, 1.0], [1.0], [1.0, 1.0], [1.0]], [[0.0, 2.0], [0.0], [2.0, 0.0], [2.0]], [[-1.0, 0.0], [4.0], [0.0, 0.0], [0.0]]]
    got = mod.merge_coeffs(base, tvs, [[1.0, 0.0], [0.5, 1.0], [2.0, 0.0]])
    # layer 0 (tensors 0, 1) uses the first number of each pair, layer 1 (tensors 2, 3) the second
    want = [[1.0 + 1.0 + 0.0 - 2.0, 2.0 + 1.0 + 1.0 + 0.0], [3.0 + 1.0 + 0.0 + 8.0], [4.0 + 0.0 + 2.0 + 0.0, 5.0 + 0.0 + 0.0 + 0.0], [6.0 + 0.0 + 2.0 + 0.0]]
    assert models_near(got, want), f"merge_coeffs hand example: expected {want}, got {got}. Layer 0 is tensors 0 and 1, layer 1 is tensors 2 and 3."
    assert models_near(mod.merge_coeffs(base, tvs, [[0.0, 0.0]] * 3), base), "all-zero coefficients give the base"

    note = ""
    for s in seeds(range(3)):
        w = world(s)
        tv = [mod.task_vector(ft, w.base) for ft in w.finetunes]
        for t in range(3):
            c = [[0.0, 0.0] for _ in range(3)]
            c[t] = [1.0, 1.0]
            assert models_near(mod.merge_coeffs(w.base, tv, c), w.finetunes[t], 1e-12), f"world {s}: coefficient 1 for task {t} only must reproduce specialist {t}"
        assert models_near(mod.merge_coeffs(w.base, tv, mod.coeffs_from_vector([1 / 3], "global")), mod.average_models(w.finetunes), 1e-12), \
            f"world {s}: coefficients of 1/3 for every task are exactly the average of the three specialists"
        rng = random.Random(s)
        c1 = [[rng.uniform(-1, 1) for _ in range(2)] for _ in range(3)]
        c2 = [[rng.uniform(-1, 1) for _ in range(2)] for _ in range(3)]
        csum = [[a + b for a, b in zip(r1, r2)] for r1, r2 in zip(c1, c2)]
        assert models_near(mod.merge_coeffs(w.base, tv, c1), flat_merge(w.base, tv, c1), 1e-12), f"world {s}: merge_coeffs differs from an independent merge"
        lin = mod.merge_coeffs(w.base, tv, csum)
        parts = [[b1 + b2 - 2 * b0 for b1, b2, b0 in zip(t1, t2, t0)] for t1, t2, t0 in
                 zip(mod.merge_coeffs(w.base, tv, c1), mod.merge_coeffs(w.base, tv, c2), w.base)]
        assert models_near(lin, [[p + b for p, b in zip(tp, tb)] for tp, tb in zip(parts, w.base)], 1e-12), f"world {s}: a merge is linear in its coefficients"

        lam, score = mod.best_global_lambda(w.base, tv, w.search)
        assert lam in mod.LAMBDA_GRID, f"world {s}: best_global_lambda must return a value from the grid, got {lam}"
        scores = [mod.mean_score(flat_merge(w.base, tv, [[g, g]] * 3), w.search) for g in mod.LAMBDA_GRID]
        want_lam = mod.LAMBDA_GRID[scores.index(max(scores))]
        assert lam == want_lam and near(score, max(scores)), (f"world {s}: the best lambda on the search split is {want_lam} "
                                                              f"(score {max(scores):.3f}), you returned {lam} ({score:.3f}). Ties go to the earlier grid entry.")
        if s == 0:
            hold = mod.mean_score(mod.merge_coeffs(w.base, tv, mod.coeffs_from_vector([lam], "global")), w.hold)
            avg = mod.mean_score(mod.average_models(w.finetunes), w.hold)
            note = (f"world 0: base {mod.mean_score(w.base, w.hold):.3f}, average of specialists {avg:.3f}, "
                    f"task arithmetic with lambda {lam} (picked on the search split) {hold:.3f} on held-out data")
    w = world(0)
    tv = [mod.task_vector(ft, w.base) for ft in w.finetunes]
    lam, sc = mod.best_global_lambda(w.base, tv, w.search, [0.4, 0.9])
    want = {g: mod.mean_score(flat_merge(w.base, tv, [[g, g]] * 3), w.search) for g in (0.4, 0.9)}
    assert lam == max(want, key=want.get) and near(sc, want[lam]), "best_global_lambda must honour a custom grid"
    assert mod.best_global_lambda(w.base, tv, w.search, [0.5, 0.5])[0] == 0.5, "a grid with repeated values is fine"
    return note


# =============================================================================
# Milestone 3: TIES
# =============================================================================
def m3():
    assert mod.trim_topk([0.1, -0.9, 0.4, 0.4], 0.5) == [0.0, -0.9, 0.4, 0.0], "trim_topk: keep 2 of 4; the tie between the two 0.4 entries goes to the lower index"
    assert mod.trim_topk([1.0, -2.0, 3.0], 1.0) == [1.0, -2.0, 3.0], "keep = 1.0 keeps everything"
    assert mod.trim_topk([1.0, -2.0, 3.0], 0.0) == [0.0, 0.0, 3.0], "keep = 0.0 still keeps one entry (k = max(1, ...))"
    assert mod.trim_topk([5.0, 1.0, 2.0, 3.0, 4.0], 0.5) == [5.0, 0.0, 0.0, 3.0, 4.0], "n = 5, keep = 0.5: k = floor(3.0) = 3 entries"
    assert sum(1 for v in mod.trim_topk([float(i + 1) for i in range(10)], 0.25) if v) == 3, "n = 10, keep = 0.25: k = floor(2.5 + 0.5) = 3"
    assert mod.elect_sign([[0.5, 0.8, 0.0, 1.0], [-0.7, 0.6, 0.0, -1.0]]) == [-1.0, 1.0, 0.0, 0.0], "elect_sign: sign of the SUM, 0.0 when the sum is 0"
    assert mod.disjoint_mean([[0.5, 0.8, 0.0], [-0.7, 0.6, 0.0]], [-1.0, 1.0, 0.0]) == [-0.7, 0.7, 0.0], "disjoint_mean: average only the entries that agree with the elected sign"
    assert mod.disjoint_mean([[0.0, 0.0], [0.0, 0.3]], [1.0, 1.0]) == [0.0, 0.3], "zeros are not counted in the mean: one agreeing entry gives that entry"

    A = [[0.8, 0.05, 0.5, -0.6, 0.02, -0.1]]
    B = [[0.6, -0.1, -0.7, -0.5, 0.05, 0.02]]
    got = mod.ties_merge([A, B], 0.5)
    assert models_near(got, [[0.7, 0.0, -0.7, -0.55, 0.0, 0.0]]), (f"the six-weight example of chapter 16: expected [0.7, 0, -0.7, -0.55, 0, 0], got "
                                                                   f"{[round(v, 3) for v in got[0]]}")
    plain = [(a + b) / 2 for a, b in zip(A[0], B[0])]
    assert near(plain[2], -0.1), "(for comparison: the plain average blurs column 3 to -0.1)"
    tiny = mod.ties_merge([[[9.0, 8.0, 7.0, 6.0], [0.01, 0.02]], [[9.0, -8.0, 7.0, 6.0], [-0.01, 0.03]]], 0.3)
    assert tiny[1] != [0.0, 0.0], "trimming is PER TENSOR: a small bias vector keeps its own top entries instead of being zeroed by the big weights"

    for s in seeds(range(1, 26)):
        rng = random.Random(s)
        n_tasks, sizes = rng.randint(2, 4), (7, 3, 5, 2)
        tvs = [[[rng.uniform(-1, 1) for _ in range(n)] for n in sizes] for _ in range(n_tasks)]
        keep = rng.choice([0.2, 0.5, 1.0])
        out = mod.ties_merge(tvs, keep)
        assert [len(t) for t in out] == list(sizes), f"seed {s}: the merged task vector must have the same shape"
        order = list(range(n_tasks))
        rng.shuffle(order)
        assert models_near(out, mod.ties_merge([tvs[i] for i in order], keep), 1e-12), f"seed {s}: the order of the task vectors must not matter"
        for k in range(4):
            tr = [mod.trim_topk(tv[k], keep) for tv in tvs]
            for i in range(sizes[k]):
                col = [t[i] for t in tr]
                total = sum(col)
                agree = [v for v in col if v != 0 and (v > 0) == (total > 0)] if total != 0 else []
                want = sum(agree) / len(agree) if agree else 0.0
                assert near(out[k][i], want, 1e-12), (f"seed {s}: tensor {k} position {i}: kept entries {col} elect sign {'+' if total > 0 else '-' if total < 0 else '0'}; "
                                                    f"the mean of the agreeing ones is {want:.4f}, you returned {out[k][i]:.4f}")
        one = mod.ties_merge([tvs[0]], 1.0)
        assert models_near(one, tvs[0], 1e-12), f"seed {s}: TIES of a single untrimmed task vector is that vector"
        pos = [[[abs(v) + 0.1 for v in t] for t in tv] for tv in tvs]
        full = mod.ties_merge(pos, 1.0)
        assert models_near(full, [[sum(col) / n_tasks for col in zip(*[tv[k] for tv in pos])] for k in range(4)], 1e-12), f"seed {s}: with keep = 1 and all signs equal, TIES is the plain mean"

    base = [[1.0, 2.0], [3.0]]
    assert models_near(mod.merge_ties(base, [[[1.0, 0.0], [2.0]], [[3.0, 0.0], [2.0]]], 1.0, 0.5), [[2.0, 2.0], [4.0]]), "merge_ties: base + lam * mean of agreeing entries"

    # Scenario: what do trimming and sign election throw away, and how do the merges score?
    dropped_trim = dropped_elect = survivors = total = 0
    ta, ti = [], []
    for s in seeds(range(4)):
        w = world(s)
        tvs = [mod.task_vector(ft, w.base) for ft in w.finetunes]
        for k in range(4):
            tr = [mod.trim_topk(tv[k], 0.3) for tv in tvs]
            sg = mod.elect_sign(tr)
            for i in range(len(tr[0])):
                col = [t[i] for t in tr if t[i] != 0]
                total += len(tvs)
                survivors += len(col)
                dropped_elect += sum(1 for c in col if (c > 0) != (sg[i] > 0))
        lam_ta, _ = mod.best_global_lambda(w.base, tvs, w.search)
        ta.append(mod.mean_score(mod.merge_coeffs(w.base, tvs, mod.coeffs_from_vector([lam_ta], "global")), w.hold))
        best = max(mod.LAMBDA_GRID, key=lambda l: mod.mean_score(mod.merge_ties(w.base, tvs, 0.3, l), w.search))
        ti.append(mod.mean_score(mod.merge_ties(w.base, tvs, 0.3, best), w.hold))
        assert models_near(mod.merge_ties(w.base, tvs, 0.3, 0.0), w.base), "lam = 0 gives the base"
    return (f"keep 30%: {survivors} of {total} task-vector entries survive trimming, and sign election then overrules {dropped_elect} of those survivors\n"
            f"held-out score, 4 worlds: task arithmetic {sum(ta) / 4:.3f}, TIES (keep 0.3) {sum(ti) / 4:.3f}")


# =============================================================================
# Milestone 4: an evolution strategy
# =============================================================================
def m4():
    target = [1.0, -1.0, 0.5, 2.0]
    sphere = lambda x: -sum((a - b) ** 2 for a, b in zip(x, target))
    calls = []

    def fit(x):
        calls.append(list(x))
        return sphere(x)

    x0 = [0.0, 0.0, 0.0, 0.0]
    keep_x0 = list(x0)
    res = mod.evolve(fit, x0, random.Random(3), mu=4, lam=16, generations=40, sigma=0.5, decay=0.92)
    assert x0 == keep_x0, "evolve must not modify x0"
    assert len(calls) == 4 + 16 * 40 == res.evals, f"fitness must be called exactly mu + lam * generations = 644 times (once per individual); it was called {len(calls)} times, evals says {res.evals}"
    assert calls[0] == x0, "the first individual evaluated is x0 itself"
    assert len(res.history) == 41, f"history has one entry for the initial pool and one per generation (41); got {len(res.history)}"
    assert all(b >= a for a, b in zip(res.history, res.history[1:])), "the best fitness can never go down: parents compete with their children (elitism)"
    assert near(res.fitness, sphere(res.x)) and near(res.fitness, res.history[-1]) and near(res.fitness, max(sphere(c) for c in calls)), \
        "result.fitness must be the fitness of result.x, the last history entry and the best value ever evaluated"
    dist = math.dist(res.x, target)
    assert dist < 0.35, f"on a sphere centred at {target}, 40 generations should land within 0.35 of the centre; you ended {dist:.2f} away"
    assert res.history[0] < res.history[-1], "the search must improve on the initial pool"

    again = mod.evolve(sphere, [0.0] * 4, random.Random(3), mu=4, lam=16, generations=40, sigma=0.5, decay=0.92)
    assert again.x == res.x and again.history == res.history, "same seed, same run"
    other = mod.evolve(sphere, [0.0] * 4, random.Random(4), mu=4, lam=16, generations=40, sigma=0.5, decay=0.92)
    assert other.x != res.x, "a different seed must give a different run"

    flat = mod.evolve(lambda x: 1.0, [0.3, 0.7], random.Random(0), generations=5)
    assert flat.x == [0.3, 0.7] and flat.history == [1.0] * 6, "with constant fitness the stable sort keeps x0 (the earliest individual) on every tie"

    calls.clear()
    mod.evolve(fit, x0, random.Random(5), mu=3, lam=6, generations=4, sigma=0.5, decay=0.0)
    assert len(calls) == 3 + 6 * 4, f"mu = 3, lam = 6, 4 generations: expected 27 evaluations, got {len(calls)}"
    seen = calls[:3 + 6]
    for later in calls[9:]:
        assert later in seen, ("decay = 0 means sigma is 0 from the second generation on, so every later child is an exact copy of a parent; "
                               "sigma must be multiplied by decay AFTER each generation, not before the first")
    one = mod.evolve(sphere, [0.0] * 4, random.Random(1), mu=1, lam=1, generations=300, sigma=0.3, decay=0.99)
    assert one.evals == 301 and one.fitness > sphere([0.0] * 4), "a (1+1) strategy is the special case mu = 1, lam = 1"

    # a landscape with plateaus, like an accuracy on a small set
    steps = lambda x: float(sum(1 for v in x if v > 0.5))
    res2 = mod.evolve(steps, [0.0] * 6, random.Random(2), mu=4, lam=16, generations=20, sigma=0.4)
    assert res2.fitness >= 4, f"on a staircase fitness (count of coordinates above 0.5) 20 generations should reach at least 4 of 6; got {res2.fitness}"
    return (f"sphere in 4 dimensions: fitness {res.history[0]:.2f} -> {res.history[10]:.2f} -> {res.fitness:.4f} (generations 0, 10, 40), "
            f"{res.evals} evaluations, {dist:.3f} from the optimum\nstaircase fitness: {res2.history[0]:.0f} -> {res2.fitness:.0f} of 6 coordinates above 0.5")


# =============================================================================
# Milestone 5: search for a merge recipe
# =============================================================================
class Spy:
    """Wraps mod.task_scores so a test can see which splits the search looks at."""
    def __init__(self, forbidden=()):
        self.forbidden, self.calls, self.orig = list(forbidden), 0, mod.task_scores

    def __enter__(self):
        def spy(model, split):
            assert not any(split is f for f in self.forbidden), \
                "the search evaluated a model on world.hold: a recipe search may only look at world.search"
            self.calls += 1
            return self.orig(model, split)
        mod.task_scores = spy
        return self

    def __exit__(self, *exc):
        mod.task_scores = self.orig


def m5():
    gains = []
    for s in seeds(range(3)):
        w = world(s)
        for mode in ("global", "task", "layer"):
            with Spy(forbidden=[w.hold]) as spy:
                vec, res = mod.search_recipe(w, mode, seed=s)
            tvs = [mod.task_vector(ft, w.base) for ft in w.finetunes]
            avg_search = mod.mean_score(mod.average_models(w.finetunes), w.search)
            assert len(vec) == mod.RECIPE_DIM[mode], f"world {s}, mode {mode}: the recipe has {mod.RECIPE_DIM[mode]} numbers, got {len(vec)}"
            assert res.evals == 4 + 16 * 15 and spy.calls == res.evals, (f"world {s}, mode {mode}: one fitness evaluation (one scoring on world.search) per individual: "
                                                                          f"expected 244, scored {spy.calls} times, evals says {res.evals}")
            merged = mod.merge_coeffs(w.base, tvs, mod.coeffs_from_vector(vec, mode))
            assert near(mod.mean_score(merged, w.search), res.fitness), f"world {s}, mode {mode}: result.fitness must be the search score of the returned recipe"
            assert res.fitness >= avg_search - 1e-12, (f"world {s}, mode {mode}: the search starts from the plain average (search score {avg_search:.3f}) and is elitist, "
                                                       f"so it cannot end below it, but it ended at {res.fitness:.3f}. Is x0 = [1/3] * dim?")
            assert all(b >= a for a, b in zip(res.history, res.history[1:])) and len(res.history) == 16
            if mode == "layer":
                gains.append((avg_search, res.fitness))
        v2, _ = mod.search_recipe(w, "layer", seed=s)
        v3, _ = mod.search_recipe(w, "layer", seed=s)
        v4, _ = mod.search_recipe(w, "layer", seed=s + 100)
        assert v2 == v3, f"world {s}: the same seed must give the same recipe"
        assert v2 != v4, f"world {s}: a different seed should explore differently"
        short = mod.search_recipe(w, "layer", seed=s, generations=3, mu=2, lam=4)[1]
        assert short.evals == 2 + 4 * 3 and len(short.history) == 4, "the evolution parameters are passed through to evolve"
    a = sum(g[0] for g in gains) / len(gains)
    b = sum(g[1] for g in gains) / len(gains)
    return (f"per-layer recipes, 3 worlds, score on the SEARCH split: plain average {a:.3f} -> evolved {b:.3f}; "
            f"244 evaluations each, none touching the held-out split")


# =============================================================================
# Milestone 6: the honest comparison
# =============================================================================
def m6():
    names = ["base", "oracle", "average", "task arithmetic", "TIES", "evolved"]
    w = world(0)
    table = mod.compare_methods(w, seed=0)
    assert list(table) == names, f"compare_methods must return the keys {names} in that order; got {list(table)}"
    assert all(isinstance(v, tuple) and len(v) == 2 for v in table.values()), "every value is a (search_score, hold_score) pair"
    assert near(table["base"][0], mod.mean_score(w.base, w.search)) and near(table["base"][1], mod.mean_score(w.base, w.hold)), "base row"
    orc = [(mod.task_scores(w.finetunes[t], w.search)[t], mod.task_scores(w.finetunes[t], w.hold)[t]) for t in range(3)]
    assert near(table["oracle"][0], sum(o[0] for o in orc) / 3) and near(table["oracle"][1], sum(o[1] for o in orc) / 3), \
        "oracle row: specialist t scored on task t only (index [t] of task_scores), averaged over the three tasks"
    avg = mod.average_models(w.finetunes)
    assert near(table["average"][0], mod.mean_score(avg, w.search)) and near(table["average"][1], mod.mean_score(avg, w.hold)), "average row"
    tvs = [mod.task_vector(ft, w.base) for ft in w.finetunes]
    lam, _ = mod.best_global_lambda(w.base, tvs, w.search)
    m_ta = mod.merge_coeffs(w.base, tvs, mod.coeffs_from_vector([lam], "global"))
    assert near(table["task arithmetic"][0], mod.mean_score(m_ta, w.search)) and near(table["task arithmetic"][1], mod.mean_score(m_ta, w.hold)), \
        "task arithmetic row: the lambda comes from best_global_lambda on world.search"
    sc = {l: mod.mean_score(mod.merge_ties(w.base, tvs, 0.3, l), w.search) for l in mod.LAMBDA_GRID}
    lt = max(mod.LAMBDA_GRID, key=lambda l: sc[l])
    assert near(table["TIES"][0], sc[lt]), f"TIES row: lam should be the grid value with the best search score ({lt}, search {sc[lt]:.3f}); your search score is {table['TIES'][0]:.3f}"
    m_ti = mod.merge_ties(w.base, tvs, 0.3, lt)
    assert near(table["TIES"][1], mod.mean_score(m_ti, w.hold)), "TIES row: the held-out score of that merge"
    vec, res = mod.search_recipe(w, "layer", 0)
    assert near(table["evolved"][0], res.fitness) and near(table["evolved"][1], mod.mean_score(
        mod.merge_coeffs(w.base, tvs, mod.coeffs_from_vector(vec, "layer")), w.hold)), "evolved row: search_recipe(world, mode, seed), scored on both splits"
    assert table["evolved"][0] >= table["average"][0], "evolved cannot score below the plain average on the search split"

    # The protocol: nothing about the held-out split may influence a decision.
    scrambled = w._replace(hold=[(xs, [(y + 1) % mod.K for y in ys]) for xs, ys in w.hold])
    t2 = mod.compare_methods(scrambled, seed=0)
    for name in names:
        assert near(table[name][0], t2[name][0]), (f"'{name}': the search-split score changed when only the held-out LABELS were scrambled, so a decision "
                                                   f"({name}) used world.hold. Choose lambda and the recipe on world.search alone.")
    assert t2["base"][1] != table["base"][1], "(sanity) scrambling the held-out labels changes held-out scores"

    assert near(mod.optimism({"x": (0.8, 0.65)}, "x"), 0.15), "optimism = search - hold"
    mt = mod.mean_table([{"a": (0.5, 0.4), "b": (1.0, 0.0)}, {"a": (0.7, 0.6), "b": (0.0, 1.0)}])
    assert list(mt) == ["a", "b"] and near(mt["a"][0], 0.6) and near(mt["a"][1], 0.5) and near(mt["b"][0], 0.5) and near(mt["b"][1], 0.5), "mean_table averages each column over worlds"

    # Scenario 1: six worlds, a small search split. The winner's curse.
    tables = [mod.compare_methods(world(s), seed=s) for s in seeds(range(6))]
    mt = mod.mean_table(tables)
    g_evo = sum(mod.optimism(t, "evolved") for t in tables) / len(tables)
    g_avg = sum(mod.optimism(t, "average") for t in tables) / len(tables)
    assert g_evo > g_avg + 0.03, (f"over 6 worlds the evolved recipe should look clearly better on the search split than it is on held-out data "
                                  f"(optimism {g_evo:+.3f}), more than the untuned average ({g_avg:+.3f}); selecting on a small split inflates the winner's score")
    # Scenario 2: a bigger search split shrinks the inflation.
    big = [mod.compare_methods(world(s, 100), seed=s) for s in seeds(range(3))]
    g_big = sum(mod.optimism(t, "evolved") for t in big) / len(big)
    g_small = sum(mod.optimism(t, "evolved") for t in tables[:3]) / 3
    assert g_big < g_small, f"with 100 search examples per task instead of 20 the optimism should fall, but it went from {g_small:+.3f} to {g_big:+.3f}"
    lines = [f"{n:<16} search {s:.3f}   held-out {h:.3f}   optimism {s - h:+.3f}" for n, (s, h) in mt.items()]
    return ("6 worlds, 20 search examples per task, 300 held-out:\n" + "\n".join(lines) +
            f"\nevolved optimism with 20 search examples per task {g_small:+.3f}, with 100: {g_big:+.3f} (3 worlds each)")


MILESTONES = [
    (1, "Milestone 1: vectors of weights", m1),
    (2, "Milestone 2: task arithmetic with per-layer coefficients", m2),
    (3, "Milestone 3: TIES, trim, elect, merge", m3),
    (4, "Milestone 4: an evolution strategy", m4),
    (5, "Milestone 5: search for a merge recipe", m5),
    (6, "Milestone 6: the honest comparison", m6),
]

if __name__ == "__main__":
    t0 = time.time()
    print(f"Lab 5 checks against {target}.py\n")
    for n, name, fn in MILESTONES:
        check(n, name, fn)
    print(f"\n{sum(results)}/{len(results)} milestones passing  ({time.time() - t0:.1f} s)")
    sys.exit(0 if all(results) else 1)
