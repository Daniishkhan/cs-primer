"""Self-check for the leg "From five rides to a learning loop".

    python3 check.py              # checks every step in project.py
    python3 check.py 7            # only step 7
    python3 check.py project 7    # the same (the file to check comes first)

Each step prints ✔ with the numbers your code gives on the real rides,
✘ with what was expected and what was got, or "not implemented yet".
Deterministic: the same code gives the same numbers every time.
"""
import importlib
import json
import math
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True

args = sys.argv[1:]
target = args[0] if args and not args[0].isdigit() else "project"
rest = [a for a in args if a.isdigit()]
ONLY = int(rest[0]) if rest else None
mod = importlib.import_module(target)
results = []
_rides = None


def rides():
    global _rides
    if _rides is None:
        _rides = mod.load_rides(os.path.join(HERE, "rides.csv"))
    return _rides


def close(a, b, tol=1e-6):
    return abs(a - b) <= tol * max(1.0, abs(a), abs(b))


def expect(got, want, what, tol=1e-6):
    if isinstance(want, float) or isinstance(got, float):
        ok = close(got, want, tol)
    else:
        ok = got == want
    assert ok, f"{what}: expected {want!r}, got {got!r}"


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
        tb = e.__traceback__
        while tb.tb_next:
            tb = tb.tb_next
        print(f"  ✘ {name}: {type(e).__name__}: {e}   [in {tb.tb_frame.f_code.co_name}() line {tb.tb_lineno}]")
        results.append(False)


# ── the steps ──────────────────────────────────────────────────────────
def step1():
    expect(mod.guess(1.6, 2.5, 2.0), 5.7, "guess(1.6, 2.5, 2.0)")
    expect(mod.guess(0.0, 3.0, 2.5), 3.0, "guess(0, 3, 2.5): no miles, just the base")
    expect(mod.total_error(mod.RIDES5, 2.5, 2.0), 15.76, "total_error(RIDES5, 2.5, 2.0)", 1e-9)
    expect(mod.total_error(mod.RIDES5[:1], 2.5, 2.0), 1.3, "one ride: |5.7 - 7.0|", 1e-9)
    e1, e2 = mod.total_error(mod.RIDES5, 2.5, 2.0), mod.total_error(mod.RIDES5, 2.5, 3.0)
    return (f"$2.50 + $2.00 a mile misses the five fares by ${e1:.2f} in total; "
            f"$3.00 a mile misses by ${e2:.2f}")


def step2():
    expect(mod.dot([1, 2, 3], [4, 5, 6]), 32.0, "dot([1,2,3],[4,5,6])")
    expect(mod.dot([], []), 0.0, "dot of nothing")
    try:
        mod.dot([1, 2], [1])
        raise AssertionError("dot([1,2],[1]) should raise ValueError")
    except ValueError:
        pass
    expect(mod.features(mod.RIDES5[0]), [1.0, 1.6, 6.2], "features of the first ride")
    expect(mod.predict(mod.RIDES5[0], [2.5, 2.0, 0.0]), 5.7, "predict with step 1's guess as weights")
    p = mod.predict(mod.RIDES5[3], [2.5, 2.0, 0.5])
    expect(p, 2.5 + 2.0 * 7.7 + 0.5 * 25.9, "predict with a per-minute weight")
    return (f"ride 4 (7.7 miles, 25.9 minutes): $2.50 + $2 a mile + $0.50 a minute "
            f"predicts ${p:.2f}; the fare was $27.00")


def step3():
    expect(mod.matvec([[1, 2], [3, 4]], [1, 1]), [3.0, 7.0], "matvec on a 2x2")
    expect(mod.matvec([], [1, 1]), [], "matvec on no rows")
    R = rides()
    assert len(R) == 6367, f"load_rides should give 6367 rides, got {len(R)}"
    X = mod.design_matrix(R)
    assert len(X) == 6367 and len(X[0]) == 3, "design matrix should be 6367 x 3"
    pred = mod.matvec(X, [2.5, 2.0, 0.0])
    expect(pred[0], 5.7, "first prediction")
    mean_pred = sum(pred) / len(pred)
    mean_fare = sum(mod.targets(R)) / len(R)
    return (f"{len(R):,} rides, shape ({len(X)}, {len(X[0])}): the guess predicts a mean fare "
            f"of ${mean_pred:.2f}; the real mean is ${mean_fare:.2f}")


def step4():
    expect(mod.mse([1, 2], [1, 4]), 2.0, "mse([1,2],[1,4])")
    expect(mod.mse([3.0], [3.0]), 0.0, "a perfect prediction")
    try:
        mod.mse([1], [1, 2])
        raise AssertionError("mse with different lengths should raise ValueError")
    except ValueError:
        pass
    R = rides()
    X, y = mod.design_matrix(R), mod.targets(R)
    a, b = mod.loss(X, y, [2.5, 2.0, 0.0]), mod.loss(X, y, [2.5, 2.5, 0.0])
    return (f"loss of $2 a mile: {a:.2f}; of $2.50 a mile: {b:.2f} "
            f"(root of that: about ${math.sqrt(b):.2f} off a typical fare)")


def step5():
    X, y = [[1.0, 1.0], [1.0, 2.0], [1.0, 3.0]], [2.0, 4.0, 6.0]
    out = mod.sweep(X, y, [0.0, 0.0], 1, [1.0, 2.0, 3.0])
    expect([v for v, _ in out], [1.0, 2.0, 3.0], "the values, in order")
    expect(out[1][1], 0.0, "loss at the perfect slope 2")
    expect(out[0][1], mod.loss(X, y, [0.0, 1.0]), "loss at slope 1")
    w = [0.0, 0.0]
    mod.sweep(X, y, w, 1, [5.0])
    expect(w, [0.0, 0.0], "sweep must not change w")
    R = rides()
    Xr, yr = mod.design_matrix(R), mod.targets(R)
    grid = [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]
    best = min(mod.sweep(Xr, yr, [2.5, 0.0, 0.0], 1, grid), key=lambda p: p[1])
    return f"with $2.50 base and nothing per minute, the best price per mile on the grid is ${best[0]:.2f} (loss {best[1]:.2f})"


def step6():
    f = lambda w: (w[0] - 3) ** 2 + 2 * (w[1] + 1) ** 2
    g = mod.numeric_grad(f, [0.0, 0.0])
    expect(g[0], -6.0, "d/dw0 at (0,0)", 1e-5)
    expect(g[1], 4.0, "d/dw1 at (0,0)", 1e-5)
    expect(mod.gd_step([1.0, 2.0], [0.5, -1.0], 0.1), [0.95, 2.1], "gd_step")
    w = [0.0, 0.0]
    for _ in range(200):
        w = mod.gd_step(w, mod.numeric_grad(f, w), 0.1)
    expect(w[0], 3.0, "200 steps reach the minimum (w0)", 1e-5)
    expect(w[1], -1.0, "200 steps reach the minimum (w1)", 1e-5)
    return f"200 nudged steps from (0, 0) land at ({w[0]:.4f}, {w[1]:.4f}); the minimum is (3, -1)"


def step7():
    R = rides()[:500]
    X, y = mod.design_matrix(R), mod.targets(R)
    w = [2.5, 2.0, 0.0]
    exact = mod.grad_mse_linear(X, y, w)
    numeric = mod.numeric_grad(lambda v: mod.loss(X, y, v), w, 1e-4)
    for j in range(3):
        expect(exact[j], numeric[j], f"gradient component {j} vs numeric", 1e-4)
    expect(mod.grad_mse_linear([[1.0, 2.0]], [5.0], [1.0, 1.0]), [-4.0, -8.0], "one ride by hand")
    return (f"on 500 rides at w = {w}: gradient {[round(g, 3) for g in exact]}; "
            f"nudging gives {[round(g, 3) for g in numeric]}")


def step8():
    X, y = [[1.0, 1.0], [1.0, 2.0], [1.0, 3.0]], [2.0, 4.0, 6.0]
    w, losses = mod.train_linear(X, y, [0.0, 0.0], 0.1, 300)
    expect(len(losses), 300, "one loss per step")
    assert losses[0] > losses[-1], "the loss should fall"
    expect(w[1], 2.0, "the slope after 300 steps", 1e-2)
    R = rides()[:500]
    Xr, yr = mod.design_matrix(R), mod.targets(R)
    w_ok, l_ok = mod.train_linear(Xr, yr, [0.0, 0.0, 0.0], 1e-4, 200)
    w_bad, l_bad = mod.train_linear(Xr, yr, [0.0, 0.0, 0.0], 1e-2, 20)
    assert l_ok[-1] < l_ok[0], "a small learning rate should lower the loss on real rides"
    return (f"on 500 real rides, lr 0.0001: loss {l_ok[0]:.1f} -> {l_ok[-1]:.1f} in 200 steps; "
            f"lr 0.01: loss {l_bad[0]:.1f} -> {l_bad[-1]:.3g} by step 20 (it blows up)")


def step9():
    Xs, means, stds = mod.standardise([[1.0, 2.0, 10.0], [1.0, 4.0, 30.0]])
    expect(means, [0.0, 3.0, 20.0], "means (constant column untouched)")
    expect(stds, [1.0, 1.0, 10.0], "population standard deviations")
    expect(Xs, [[1.0, -1.0, -1.0], [1.0, 1.0, 1.0]], "standardised rows")
    R = rides()[:500]
    Xr, yr = mod.design_matrix(R), mod.targets(R)
    Xz, m, s = mod.standardise(Xr)
    w, losses = mod.train_linear(Xz, yr, [0.0, 0.0, 0.0], 0.1, 200)
    assert losses[-1] < 40, f"after standardising, lr 0.1 should converge (loss {losses[-1]:.1f})"
    return (f"after standardising, lr 0.1 takes the loss {losses[0]:.1f} -> {losses[-1]:.1f}; "
            f"weights: ${w[0]:.2f} base, ${w[1]:.2f} per standard deviation of distance "
            f"({s[1]:.2f} miles), ${w[2]:.2f} per standard deviation of time ({s[2]:.1f} minutes)")


def step10():
    V = mod.Value
    a, b = V(2.0), V(3.0)
    c = a + b
    expect(c.data, 5.0, "(2 + 3).data")
    assert c.parents == (a, b) and c.op == "+", "a + b should record parents (a, b) and op '+'"
    d = a * b
    expect(d.data, 6.0, "(2 * 3).data")
    assert d.parents == (a, b) and d.op == "*", "a * b should record parents (a, b) and op '*'"
    e = a + 1
    expect(e.data, 3.0, "Value + plain number")
    assert isinstance(e.parents[1], V), "a plain number becomes a Value parent"
    expect((V(-2.0).relu()).data, 0.0, "relu of a negative")
    expect((V(1.5).relu()).data, 1.5, "relu of a positive")
    assert V(1.5).relu().op == "relu", "relu's op is 'relu'"
    expect((2 * a - b / V(2.0)).data, 2.5, "the derived operators: 2a - b/2")
    return "2 + 3 = 5 and 2 * 3 = 6, each remembering its parents; relu(-2) = 0, relu(1.5) = 1.5"


def step11():
    V = mod.Value
    a, b = V(2.0), V(3.0)
    expect(mod.local_grads(a + b), [1.0, 1.0], "local grads of +")
    expect(mod.local_grads(a * b), [3.0, 2.0], "local grads of *: each parent's partner")
    expect(mod.local_grads(V(1.5).relu()), [1.0], "relu, positive side")
    expect(mod.local_grads(V(-1.5).relu()), [0.0], "relu, negative side")
    expect(mod.local_grads(a), [], "a leaf has no parents")
    return "d(a+b)/da = 1, d(a*b)/da = b = 3, d relu(1.5)/dx = 1, d relu(-1.5)/dx = 0"


def step12():
    V = mod.Value
    a, b = V(2.0), V(3.0)
    out = a * b + a           # d/da = b + 1 = 4, d/db = a = 2
    mod.backward(out)
    expect(a.grad, 4.0, "d(ab + a)/da")
    expect(b.grad, 2.0, "d(ab + a)/db")
    x = V(1.5)
    y = (x * x + x).relu() * 3   # d/dx = 3 * (2x + 1) = 12
    mod.backward(y)
    expect(x.grad, 12.0, "through relu and reuse of x")
    x2 = V(-0.4)
    y2 = (x2 * 2).relu() + x2
    mod.backward(y2)
    expect(x2.grad, 1.0, "relu off: only the direct path counts")
    f = lambda v: (v[0] * v[1] + v[0]) * (v[0] - 1)
    w = [0.7, -1.3]
    num = mod.numeric_grad(f, w, 1e-6)
    vs = [V(w[0]), V(w[1])]
    mod.backward(f(vs))
    expect(vs[0].grad, num[0], "autograd vs numeric, w0", 1e-5)
    expect(vs[1].grad, num[1], "autograd vs numeric, w1", 1e-5)
    return f"d(ab + a)/da = 4, d/db = 2; on (w0 w1 + w0)(w0 - 1) autograd gives {vs[0].grad:.6f}, nudging gives {num[0]:.6f}"


def step13():
    R = rides()[:200]
    X, y = mod.design_matrix(R), mod.targets(R)
    w = [2.5, 2.0, 0.0]
    val = mod.mse_value(X, y, [mod.Value(v) for v in w])
    expect(val.data, mod.loss(X, y, w), "mse_value agrees with mse", 1e-9)
    g_auto = mod.grad_by_autograd(X, y, w)
    g_exact = mod.grad_mse_linear(X, y, w)
    for j in range(3):
        expect(g_auto[j], g_exact[j], f"autograd vs the hand gradient, component {j}", 1e-8)
    return (f"on 200 rides the hand gradient is {[round(g, 4) for g in g_exact]} "
            f"and autograd gives {[round(g, 4) for g in g_auto]}")


def step14():
    tr, he = mod.split(list(range(10)), 0.8, 0)
    expect(len(tr), 8, "80% of 10 rows")
    expect(len(he), 2, "the rest is held out")
    expect(sorted(tr + he), list(range(10)), "nothing lost, nothing duplicated")
    tr2, _ = mod.split(list(range(10)), 0.8, 0)
    expect(tr, tr2, "the same seed gives the same split")
    tr3, _ = mod.split(list(range(10)), 0.8, 1)
    assert tr != tr3, "a different seed should give a different split"
    assert tr != list(range(8)), "the rows must be shuffled, not sliced in order"
    R = rides()
    train_r, held_r = mod.split(R, 0.8, 0)
    held_mse, model = mod.fit_linear(train_r, held_r)
    long = mod.residual_by(held_r, model, lambda r: r[1] > 30)
    short = mod.residual_by(held_r, model, lambda r: r[1] < 5)
    return (f"{len(train_r):,} rides to learn from, {len(held_r):,} held out; held-out loss {held_mse:.2f}. "
            f"On the held-out rides the average of fare minus prediction is {long:+.2f} for rides over "
            f"30 minutes and {short:+.2f} for rides under 5 minutes (positive means the line under-charges)")


def step15():
    p = mod.init_mlp(3, 4, 0)
    out = mod.mlp_forward([1.0, 0.5, -0.5], p)
    assert isinstance(out, mod.Value), "mlp_forward returns a Value"
    h = [max(0.0, sum(wj.data * xj for wj, xj in zip(row, [1.0, 0.5, -0.5])) + b.data)
         for row, b in zip(p["W1"], p["b1"])]
    want = sum(hv * wo.data for hv, wo in zip(h, p["W2"])) + p["b2"].data
    expect(out.data, want, "the forward value, by hand", 1e-9)
    mod.backward(out)
    assert any(abs(v.grad) > 0 for v in mod.parameters(p)), "gradients should reach the parameters"
    return f"a 3-4-1 network on one ride gives {out.data:.4f}, and backward fills {len(mod.parameters(p))} gradients"


def step16():
    R = rides()
    train_r, held_r = mod.split(R, 0.8, 0)
    Xtr, means, stds = mod.standardise(mod.design_matrix(train_r[:200]))
    ytr = mod.targets(train_r[:200])
    p = mod.init_mlp(3, 4, 0)
    losses = mod.train(mod.mlp_forward, p, Xtr, ytr, 0.01, 5, 20, 0)
    expect(len(losses), 5, "one loss per epoch")
    assert losses[-1] < losses[0], f"the loss should fall over 5 epochs ({losses[0]:.1f} -> {losses[-1]:.1f})"
    losses2 = mod.train(mod.mlp_forward, mod.init_mlp(3, 4, 0), Xtr, ytr, 0.01, 5, 20, 0)
    expect(losses2, losses, "the same seed gives the same run")
    Xh = [[(f - m) / s for f, m, s in zip(mod.features(r), means, stds)] for r in held_r[:200]]
    yh = mod.targets(held_r[:200])
    held = sum((mod.mlp_forward(x, p).data - t) ** 2 for x, t in zip(Xh, yh)) / 200
    w_line, _ = mod.train_linear(Xtr, ytr, [0.0, 0.0, 0.0], 0.1, 200)
    line = mod.loss(Xh, yh, w_line)
    return (f"a 3-4-1 network on 200 rides, 5 epochs of batches of 20: loss {losses[0]:.1f} -> {losses[-1]:.1f}; "
            f"on 200 held-out rides {held:.1f}. The straight line of step 9, trained on the same 200 rides, scores {line:.1f} there")


def step17():
    mean, sd = mod.noise_floor(lambda s: float(s), [1, 2, 3, 4])
    expect(mean, 2.5, "mean of 1..4")
    expect(sd, math.sqrt(1.25), "population sd of 1..4")
    R = rides()[:1500]
    def run(seed):
        tr, he = mod.split(R, 0.8, seed)
        return mod.fit_linear(tr, he, steps=100)[0]
    m, s = mod.noise_floor(run, [0, 1, 2, 3, 4])
    assert s > 0, "different splits should give different scores"
    return (f"the linear model's held-out loss over 5 splits of 1,500 rides: {m:.2f} ± {s:.2f}. "
            f"A change smaller than {s:.2f} is noise, not progress")


def step18():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "runs.jsonl")
        cfg = {"features": "both", "lr": 0.1, "steps": 100}
        e = mod.log_run(path, cfg, 0, 30.5, 31.25)
        expect(sorted(e.keys()), ["config", "hash", "held", "seed", "train"], "the keys")
        expect(e["hash"], mod.config_hash(cfg), "the hash")
        mod.log_run(path, {"lr": 0.1, "features": "both", "steps": 100}, 1, 30.0, 31.0)
        runs = mod.load_runs(path)
        expect(len(runs), 2, "two lines")
        expect(runs[0]["hash"], runs[1]["hash"], "the same config in another key order has the same hash")
        expect(runs[1]["seed"], 1, "fields round-trip")
        with open(path) as fh:
            lines = fh.read().splitlines()
        assert all(json.loads(l) for l in lines), "every line is JSON"
    return f"two runs logged under hash {e['hash']}; reading them back gives {len(runs)} runs"


def step19():
    best = {"hash": "a", "held": 30.0}
    cand = {"hash": "b", "held": 29.0}
    expect(mod.keep_or_revert(best, cand, 0.5), (cand, True), "a clear win is kept")
    expect(mod.keep_or_revert(best, cand, 1.5), (best, False), "a win inside the noise is reverted")
    expect(mod.keep_or_revert(best, {"hash": "c", "held": 31.0}, 0.0), (best, False), "worse is reverted")
    expect(mod.keep_or_revert(best, {"hash": "d", "held": 30.0}, 0.0), (best, False), "a tie is reverted")
    return "29.0 beats 30.0 with a floor of 0.5 and is kept; with a floor of 1.5 it is reverted"


def step20():
    R = rides()[:1500]
    rest, test_r = mod.split(R, 0.8, 7)
    train_r, val_r = mod.split(rest, 0.8, 7)
    _, floor = mod.noise_floor(lambda s: mod.fit_linear(*mod.split(rest, 0.8, s), steps=100)[0], [0, 1, 2])
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "runs.jsonl")
        best, kept = mod.search(mod.SPACE, 5, 0, train_r, val_r, floor, path)
        runs = mod.load_runs(path)
        expect(len(runs), 6, "the start plus 5 candidates are logged")
        expect(runs[0]["config"], mod.SPACE[0], "the first run is space[0]")
        assert len({r["hash"] for r in runs}) == 6, "every configuration is tried once"
        with tempfile.TemporaryDirectory() as d2:
            _, kept_small = mod.search(mod.SPACE, 2, 0, train_r, val_r, floor, os.path.join(d2, "small.jsonl"))
            expect(len(mod.load_runs(os.path.join(d2, "small.jsonl"))), 3, "a budget of 2 logs the start plus 2")
        assert best["held"] <= runs[0]["held"], "the best is never worse than the start"
        assert all(r["seed"] == 0 for r in runs), "every run uses the seed"
        path2 = os.path.join(d, "again.jsonl")
        best2, kept2 = mod.search(mod.SPACE, 5, 0, train_r, val_r, floor, path2)
        expect(mod.load_runs(path2), runs, "the same seed replays the same log")
        start_test = mod.evaluate(mod.SPACE[0], train_r, test_r, 0)[1]
        best_test = mod.evaluate(best["config"], train_r, test_r, 0)[1]
    val_gain = runs[0]["held"] - best["held"]
    test_gain = start_test - best_test
    return (f"5 candidates, {kept} kept, noise floor {floor:.2f}: validation loss {runs[0]['held']:.2f} -> {best['held']:.2f} "
            f"with {best['config']}. On rides never used in the search: {start_test:.2f} -> {best_test:.2f}. "
            f"Gain claimed {val_gain:.2f}, gain real {test_gain:.2f}")


STEPS = [
    (1, "Step 1: a guess and how wrong it is", step1),
    (2, "Step 2: a ride is a vector", step2),
    (3, "Step 3: many rides are a matrix", step3),
    (4, "Step 4: a loss", step4),
    (5, "Step 5: the loss surface", step5),
    (6, "Step 6: downhill by nudging", step6),
    (7, "Step 7: the exact gradient", step7),
    (8, "Step 8: a training loop", step8),
    (9, "Step 9: features on the same scale", step9),
    (10, "Step 10: a number that remembers how it was made", step10),
    (11, "Step 11: how much each input mattered", step11),
    (12, "Step 12: backward", step12),
    (13, "Step 13: the linear model, rebuilt on Value", step13),
    (14, "Step 14: rides the model never saw", step14),
    (15, "Step 15: a small network", step15),
    (16, "Step 16: training in batches", step16),
    (17, "Step 17: the noise floor", step17),
    (18, "Step 18: a run store", step18),
    (19, "Step 19: keep or revert", step19),
    (20, "Step 20: the loop", step20),
]

t0 = time.time()
print(f"Leg 1 checks against {target}.py\n")
for n, name, fn in STEPS:
    check(n, name, fn)
passed = sum(results)
print(f"\n{passed}/{len(results)} steps passing  ({time.time() - t0:.1f} s)")
sys.exit(0 if passed == len(results) else 1)
