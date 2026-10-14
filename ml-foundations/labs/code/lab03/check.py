"""Self-check for Lab 3: The Optimiser Race.

    python3 check.py                  # checks your starter.py
    python3 check.py solution         # checks the reference solution
    python3 check.py solution 4       # only milestone 4
    python3 check.py solution 3 12    # milestone 3, replaying ONLY the random cases of seed 12

Everything is deterministic: the test surfaces are formulas, the noise comes from seeded
generators, and the independent oracles below re-derive each update rule from its UNROLLED
definition (for example Adam's m as an explicit weighted sum of every past gradient), never
from your classes. A failure prints its seed so it can be replayed. The whole check takes
a few seconds.
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
    return abs(a - b) <= tol * max(1.0, abs(a), abs(b))


def vnear(a, b, tol=1e-9):
    return len(a) == len(b) and all(near(x, y, tol) for x, y in zip(a, b))


def fmt(v):
    return "[" + ", ".join(f"{x:.8g}" for x in v) + "]"


def numeric_grad(f, w, eps=1e-6):
    out = []
    for i in range(len(w)):
        hi, lo = list(w), list(w)
        hi[i] += eps
        lo[i] -= eps
        out.append((f(hi) - f(lo)) / (2 * eps))
    return out


# =============================================================================
# Milestone 1: surfaces, SGD and the loop
# =============================================================================
def m1():
    f, g = mod.bowl([3.0, 2.0])
    assert near(f, 204.5) and vnear(g, [3.0, 200.0]), (
        f"bowl([3, 2]) with kappa=100 should be (204.5, [3, 200]) (f = 0.5 (x^2 + kappa y^2), gradient [x, kappa y]); got ({f}, {fmt(g)})")
    f, g = mod.bowl([1.0, 1.0], 4.0)
    assert near(f, 2.5) and vnear(g, [1.0, 4.0]), f"bowl([1, 1], kappa=4) should be (2.5, [1, 4]); got ({f}, {fmt(g)})"
    f, g = mod.rosenbrock([-1.2, 1.0])
    assert near(f, 24.2) and vnear(g, [-215.6, -88.0]), (
        f"rosenbrock([-1.2, 1]) should be (24.2, [-215.6, -88]); got ({f}, {fmt(g)}). "
        "With r = y - x^2: df/dx = -2 (1 - x) - 400 x r and df/dy = 200 r")
    f, g = mod.rosenbrock([1.0, 1.0])
    assert near(f, 0.0) and vnear(g, [0.0, 0.0]), f"the minimum (1, 1) must have f = 0 and gradient 0; got ({f}, {fmt(g)})"
    f, g = mod.rosenbrock([0.0, 0.0])
    assert near(f, 1.0) and vnear(g, [-2.0, 0.0]), f"rosenbrock([0, 0]) should be (1, [-2, 0]); got ({f}, {fmt(g)})"

    worst = 0.0
    for s in seeds(range(1, 9)):
        rng = random.Random(s)
        w = [rng.uniform(-2, 2), rng.uniform(-2, 2)]
        kappa = rng.choice([2.0, 10.0, 100.0])
        for name, fn in (("bowl", lambda v: mod.bowl(v, kappa)), ("rosenbrock", mod.rosenbrock)):
            num = numeric_grad(lambda v: fn(v)[0], w)
            got = fn(w)[1]
            err = max(abs(a - b) / max(1.0, abs(a), abs(b)) for a, b in zip(got, num))
            worst = max(worst, err)
            assert err < 1e-5, (f"seed {s}: {name} gradient at {fmt(w)} is {fmt(got)} but central differences of YOUR f give {fmt(num)}. "
                                "Either f or the gradient has a slip; differentiate by hand once more")

    # SGD: one step by hand, no mutation
    w, g = [1.0, 2.0], [1.0, -1.0]
    out = mod.SGD(0.1).step(w, g)
    assert vnear(out, [0.9, 2.1]), f"SGD(0.1).step([1, 2], [1, -1]) should be [0.9, 2.1]; got {fmt(out)}"
    assert w == [1.0, 2.0] and g == [1.0, -1.0], "step must not modify its arguments: return a NEW list"
    assert out is not w, "step must return a new list, not the list it was given"

    # the loop: on the bowl each coordinate shrinks by a fixed factor, so the losses are known exactly
    eta, x0, y0 = 0.015, 2.0, 1.0
    trace = mod.minimise(mod.SGD(eta), mod.bowl, [x0, y0], 40)
    assert len(trace.losses) == 41 and not trace.diverged, (
        f"minimise(..., steps=40) must record the loss before the first step and after each step: 41 entries; got {len(trace.losses)}")
    for k in (0, 1, 2, 10, 40):
        want = 0.5 * (x0 ** 2 * (1 - eta) ** (2 * k) + 100 * y0 ** 2 * (1 - 100 * eta) ** (2 * k))
        assert near(trace.losses[k], want, 1e-9), (
            f"on the bowl, x is multiplied by 1 - eta = {1 - eta:.3f} and y by 1 - 100 eta = {1 - 100 * eta:.2f} each step, "
            f"so losses[{k}] should be {want:.8g}; got {trace.losses[k]:.8g}")
    assert vnear(trace.w, [x0 * (1 - eta) ** 40, y0 * (1 - 100 * eta) ** 40]), f"the final weights are wrong: {fmt(trace.w)}"
    start = [2.0, 1.0]
    mod.minimise(mod.SGD(0.01), mod.bowl, start, 5)
    assert start == [2.0, 1.0], "minimise must not modify w0"
    assert mod.minimise(mod.SGD(0.01), mod.bowl, [1.0, 1.0], 0).losses == [mod.bowl([1.0, 1.0])[0]], "steps = 0 gives just the starting loss"

    # the stability limit: eta < 2 / kappa for the steepest direction
    ok = mod.minimise(mod.SGD(0.0199), mod.bowl, [1.0, 1.0], 3000)
    assert not ok.diverged and ok.losses[-1] < 1e-6, (
        f"eta = 0.0199 is just under 2/kappa = 0.02, so SGD should converge (factor -0.99 in y); diverged={ok.diverged}, final loss {ok.losses[-1]:.3g}")
    bad = mod.minimise(mod.SGD(0.0205), mod.bowl, [1.0, 1.0], 3000)
    assert bad.diverged and bad.losses[-1] == math.inf and len(bad.losses) < 3001, (
        "eta = 0.0205 is above 2/kappa = 0.02: the y coordinate grows by 1.05 each step, so the run must be reported as diverged "
        "(diverged=True, last loss math.inf, stopped early)")
    nan_run = mod.minimise(mod.SGD(1e6), lambda v: (v[0] ** 2, [2 * v[0]]), [1.0], 500)
    assert nan_run.diverged, "an astronomically large loss (above DIVERGED) or a non-finite one must count as diverged"
    return f"worst gradient error against central differences {worst:.1e}; eta=0.0199 converges, eta=0.0205 diverges after {len(bad.losses) - 1} steps"


# =============================================================================
# Milestone 2: momentum
# =============================================================================
def m2():
    opt = mod.Momentum(0.1, 0.9)
    w = [0.0, 0.0]
    g = [1.0, 2.0]
    w1 = opt.step(w, g)
    assert vnear(w1, [-0.1, -0.2]), f"first momentum step from [0, 0] with g = [1, 2], lr 0.1: v = g, so w = [-0.1, -0.2]; got {fmt(w1)}"
    w2 = opt.step(w1, g)
    assert vnear(w2, [-0.29, -0.58]), (f"second step with the same gradient: v = 0.9 * [1, 2] + [1, 2] = [1.9, 3.8], so w = [-0.1 - 0.19, -0.2 - 0.38] "
                                       f"= [-0.29, -0.58]; got {fmt(w2)}")
    assert w == [0.0, 0.0] and g == [1.0, 2.0], "step must not modify its arguments"

    # beta = 0 is plain SGD
    for s in seeds(range(1, 5)):
        rng = random.Random(s)
        a, b = mod.Momentum(0.05, 0.0), mod.SGD(0.05)
        wa = wb = [rng.uniform(-1, 1) for _ in range(3)]
        for _ in range(10):
            gr = [rng.gauss(0, 1) for _ in range(3)]
            wa, wb = a.step(wa, gr), b.step(wb, gr)
        assert vnear(wa, wb), f"seed {s}: with beta = 0 momentum must equal plain SGD; got {fmt(wa)} versus {fmt(wb)}"

    # v is an exponentially weighted sum of ALL past gradients: v_t = sum_k beta^k g_{t-k}
    note = ""
    for s in seeds(range(1, 6)):
        rng = random.Random(s)
        lr, beta = 0.01 * rng.randint(1, 9), rng.choice([0.5, 0.9, 0.99])
        opt, w0 = mod.Momentum(lr, beta), [rng.uniform(-1, 1) for _ in range(2)]
        gs = [[rng.gauss(0, 2) for _ in range(2)] for _ in range(15)]
        w, wo = list(w0), list(w0)
        for t, gt in enumerate(gs):
            w = opt.step(w, gt)
            v = [sum(beta ** (t - i) * gs[i][j] for i in range(t + 1)) for j in range(2)]
            wo = [wo[j] - lr * v[j] for j in range(2)]
            assert vnear(w, wo, 1e-9), (f"seed {s}, step {t + 1}: expected the weights {fmt(wo)} from v = sum of beta^k * (past gradients) "
                                        f"(beta={beta}, lr={lr}); got {fmt(w)}")
    # constant gradient: v tends to g / (1 - beta), so the step tends to lr * g / (1 - beta)
    opt, w = mod.Momentum(0.01, 0.9), [0.0]
    for _ in range(200):
        prev, w = w, opt.step(w, [1.0])
    assert near(prev[0] - w[0], 0.01 * 10.0, 1e-6), (f"with a constant gradient of 1 and beta = 0.9 the step should settle at lr / (1 - beta) = 0.1 "
                                                      f"(ten times plain SGD's 0.01); got {prev[0] - w[0]:.6f}")
    # two optimisers must not share state
    a, b = mod.Momentum(0.1), mod.Momentum(0.1)
    a.step([0.0], [5.0])
    assert vnear(b.step([0.0], [1.0]), [-0.1]), "each Momentum object needs its own velocity (do not store it in a shared default or class attribute)"

    # scenario: on the narrow valley, momentum needs far fewer steps (each at its own best rate)
    best = {}
    for name, make in (("SGD", lambda lr: mod.SGD(lr)), ("momentum", lambda lr: mod.Momentum(lr, 0.9))):
        runs = [mod.steps_to_origin(lambda lr=lr: make(lr), lambda v: mod.bowl(v, 100.0), [1.0, 1.0]) for lr in mod.GRID]
        runs = [r for r in runs if r is not None]
        assert runs, f"{name} converged at no learning rate in the grid"
        best[name] = min(runs)
    assert best["momentum"] * 2 < best["SGD"], (f"on the kappa = 100 valley momentum should need less than half of SGD's steps at their best rates; "
                                                 f"got {best['momentum']} and {best['SGD']}")
    return f"kappa=100 valley, steps to reach |w| < 1e-6 at the best rate on the grid: SGD {best['SGD']}, momentum {best['momentum']}"


# =============================================================================
# Milestone 3: RMSProp and Adam
# =============================================================================
def adam_oracle(gs, lr, b1=0.9, b2=0.999, eps=1e-8):
    """The Adam step number len(gs) from the UNROLLED moments: m_t = (1-b1) sum b1^(t-i) g_i, same for v."""
    t, n = len(gs), len(gs[0])
    out = []
    for j in range(n):
        m = (1 - b1) * sum(b1 ** (t - 1 - i) * gs[i][j] for i in range(t))
        v = (1 - b2) * sum(b2 ** (t - 1 - i) * gs[i][j] ** 2 for i in range(t))
        out.append(lr * (m / (1 - b1 ** t)) / (math.sqrt(v / (1 - b2 ** t)) + eps))
    return out


def rms_oracle(gs, lr, beta=0.9, eps=1e-8):
    t, n = len(gs), len(gs[0])
    out = []
    for j in range(n):
        s = (1 - beta) * sum(beta ** (t - 1 - i) * gs[i][j] ** 2 for i in range(t))
        out.append(lr * gs[-1][j] / (math.sqrt(s) + eps))
    return out


def m3():
    # first steps by hand
    w = mod.RMSProp(0.01).step([0.0, 0.0], [2.0, -0.5])
    c = 0.01 / math.sqrt(0.1)           # s = 0.1 g^2, so the step is lr * sign(g) / sqrt(0.1)
    assert vnear(w, [-c, c], 1e-6), (f"RMSProp(0.01) first step with g = [2, -0.5]: s = 0.1 g^2, so each coordinate moves "
                                     f"lr / sqrt(0.1) = {c:.6f} downhill whatever its gradient size; got {fmt(w)}")
    w = mod.Adam(0.01).step([0.0, 0.0, 0.0], [1.0, -2.0, 0.5])
    assert vnear(w, [-0.01, 0.01, -0.01], 1e-6), (f"Adam's first step is lr * sign(g) (m_hat = g and v_hat = g^2 after bias correction); "
                                                  f"expected [-0.01, 0.01, -0.01], got {fmt(w)}")
    for scale in (1e-3, 1.0, 1e3):
        w = mod.Adam(0.01).step([0.0, 0.0], [1.0 * scale, -3.0 * scale])
        assert vnear(w, [-0.01, 0.01], 1e-4), f"gradients scaled by {scale:g} must give the same first Adam step [-0.01, 0.01]; got {fmt(w)}"
    # constant gradient: with bias correction EVERY step is exactly lr * sign(g)
    opt, w = mod.Adam(0.01), [0.0]
    for t in range(1, 30):
        prev, w = w, opt.step(w, [0.7])
        assert near(prev[0] - w[0], 0.01, 1e-6), (f"with a constant gradient, bias-corrected Adam moves exactly lr = 0.01 every step; "
                                                   f"step {t} moved {prev[0] - w[0]:.8f} (did you divide m and v by 1 - b^t, with t counting from 1?)")
    # g = 0: no division by zero
    for make in (lambda: mod.Adam(0.1), lambda: mod.RMSProp(0.1)):
        w = make().step([1.0, 2.0], [0.0, 0.0])
        assert vnear(w, [1.0, 2.0]), f"a zero gradient must leave the weights unchanged (is eps added to the denominator?); got {fmt(w)}"
    w = mod.Adam(1.0).step([0.0], [1e-10])
    assert near(w[0], -1e-10 / (1e-10 + 1e-8), 1e-6), f"eps = 1e-8 must be added OUTSIDE the square root; expected a step of {1e-10 / (1e-10 + 1e-8):.5f}, got {-w[0]:.5f}"

    # against the unrolled oracles on random gradient sequences
    for s in seeds(range(1, 7)):
        rng = random.Random(s)
        scales = [10 ** rng.uniform(-3, 3) for _ in range(3)]
        lr = rng.choice([0.001, 0.01, 0.1])
        b1, b2 = rng.choice([0.8, 0.9]), rng.choice([0.99, 0.999])
        ad, rm = mod.Adam(lr, b1, b2), mod.RMSProp(lr, b2)
        wa, wr = [0.0] * 3, [0.0] * 3
        gs = []
        for t in range(25):
            gs.append([rng.gauss(0, 1) * sc for sc in scales])
            wa2, wr2 = ad.step(wa, gs[-1]), rm.step(wr, gs[-1])
            want_a = [x - d for x, d in zip(wa, adam_oracle(gs, lr, b1, b2))]
            want_r = [x - d for x, d in zip(wr, rms_oracle(gs, lr, b2))]
            assert vnear(wa2, want_a, 1e-8), (f"seed {s}, step {t + 1}: Adam(lr={lr}, b1={b1}, b2={b2}) expected {fmt(want_a)}, got {fmt(wa2)}. "
                                              "Per-coordinate m and v, both bias-corrected, eps outside the sqrt")
            assert vnear(wr2, want_r, 1e-8), (f"seed {s}, step {t + 1}: RMSProp(lr={lr}, beta={b2}) expected {fmt(want_r)}, got {fmt(wr2)}")
            wa, wr = wa2, wr2
    # coordinates are independent
    a1, a2 = mod.Adam(0.01), mod.Adam(0.01)
    for t in range(5):
        p = a1.step([0.0, 0.0], [t + 1.0, -2.0 * t - 1.0])
        q = a2.step([0.0], [t + 1.0])
        assert near(p[0], q[0]), "each coordinate must be updated using only its own history"

    # scenario: tuned rates on the valley (the chapter-10 numbers); RMSProp's constant-size steps cannot settle
    # (best_lr belongs to milestone 6, so this search uses the milestone-1 loop)
    res = {}
    for name, make in (("RMSProp", lambda lr: mod.RMSProp(lr)), ("Adam", lambda lr: mod.Adam(lr))):
        best = min(mod.minimise(make(lr), mod.bowl, [-1.5, 1.0], 300).losses[-1] for lr in mod.GRID)
        res[name] = best
    assert res["Adam"] < 1e-9, f"Adam at its best rate should reach a loss below 1e-9 on the valley in 300 steps; got {res['Adam']:.2e}"
    assert 1e-5 < res["RMSProp"] < 1e-1, (f"RMSProp (no momentum) takes steps of size about lr whatever the gradient, so it hops around the minimum; "
                                          f"its best loss on the valley should be around 1e-3, got {res['RMSProp']:.2e}")
    return f"valley, best loss after 300 steps: Adam {res['Adam']:.2e}, RMSProp {res['RMSProp']:.2e}"


# =============================================================================
# Milestone 4: L2 penalty versus decoupled weight decay
# =============================================================================
def m4():
    # AdamW, first step by hand: w * (1 - lr wd) - lr * sign(g)
    w = mod.AdamW(0.1, 0.5).step([1.0, -2.0], [0.5, 0.5])
    assert vnear(w, [0.85, -2.0], 1e-6), (f"AdamW(lr=0.1, wd=0.5) from [1, -2] with g = [0.5, 0.5]: decay [1, -2] * (1 - 0.05) = [0.95, -1.9], "
                                         f"then the Adam step of 0.1 downhill: [0.85, -2.0]; got {fmt(w)}")
    # AdamL2, first step by hand: the gradient seen by Adam is g + l2 w, and Adam's first step is lr * sign
    w = mod.AdamL2(0.1, 0.5).step([1.0, -2.0], [0.5, 0.5])
    assert vnear(w, [0.9, -1.9], 1e-6), (f"AdamL2(lr=0.1, l2=0.5) from [1, -2] with g = [0.5, 0.5]: Adam sees g + 0.5 w = [1.0, -0.5], whose "
                                         f"signs are + and -, so the first step is [-0.1, +0.1]: [0.9, -1.9]; got {fmt(w)}")
    assert vnear(mod.AdamW(0.1, 0.0).step([1.0], [3.0]), mod.Adam(0.1).step([1.0], [3.0])), "with weight_decay = 0, AdamW must be exactly Adam"
    assert vnear(mod.AdamL2(0.1, 0.0).step([1.0], [3.0]), mod.Adam(0.1).step([1.0], [3.0])), "with l2 = 0, AdamL2 must be exactly Adam"
    w, g = [1.0, 2.0], [0.1, 0.2]
    mod.AdamW(0.1, 0.1).step(w, g)
    mod.AdamL2(0.1, 0.1).step(w, g)
    assert w == [1.0, 2.0] and g == [0.1, 0.2], "step must not modify its arguments"

    # random sequences against the unrolled oracle
    for s in seeds(range(1, 6)):
        rng = random.Random(s)
        lr, wd = rng.choice([0.01, 0.05]), rng.choice([0.1, 0.5, 1.0])
        aw, al = mod.AdamW(lr, wd), mod.AdamL2(lr, wd)
        ww = wl = [rng.uniform(-2, 2) for _ in range(3)]
        raw, eff = [], []
        for t in range(20):
            gt = [rng.gauss(0, 1) * sc for sc in (0.01, 1.0, 100.0)]
            # AdamW: oracle sees the raw gradients, decay is separate
            raw.append(gt)
            want_w = [x * (1 - lr * wd) - d for x, d in zip(ww, adam_oracle(raw, lr))]
            ww2 = aw.step(ww, gt)
            assert vnear(ww2, want_w, 1e-8), f"seed {s}, step {t + 1}: AdamW expected {fmt(want_w)}, got {fmt(ww2)}"
            ww = ww2
            # AdamL2: oracle sees g + wd * w (using the weights it was given at that step)
            eff.append([gi + wd * x for gi, x in zip(gt, wl)])
            want_l = [x - d for x, d in zip(wl, adam_oracle(eff, lr))]
            wl2 = al.step(wl, gt)
            assert vnear(wl2, want_l, 1e-8), f"seed {s}, step {t + 1}: AdamL2 expected {fmt(want_l)}, got {fmt(wl2)}"
            wl = wl2

    # scenario: the loss is flat (gradient 0), so ONLY the decay acts. A weight of 0.1 and a weight of 10
    # should lose the same fraction under a decay that does what its name says.
    def flat(make, w0, steps=100):
        opt, w = make(), [w0]
        for _ in range(steps):
            w = opt.step(w, [0.0])
        return w[0] / w0
    lr, wd = 0.01, 1.0
    small, large = flat(lambda: mod.AdamW(lr, wd), 0.1), flat(lambda: mod.AdamW(lr, wd), 10.0)
    want = (1 - lr * wd) ** 100
    assert near(small, want, 1e-9) and near(large, want, 1e-9), (
        f"with zero loss gradient AdamW shrinks every weight by (1 - lr wd) per step: after 100 steps w / w0 should be {want:.6f} "
        f"for ANY starting weight; got {small:.6f} (w0 = 0.1) and {large:.6f} (w0 = 10)")
    l2_small, l2_large = flat(lambda: mod.AdamL2(lr, wd), 0.1), flat(lambda: mod.AdamL2(lr, wd), 10.0)
    assert abs(l2_small) < 0.1 and l2_large > 0.8, (
        f"with an L2 penalty the decay goes through Adam's normalisation, so every step is about lr in WEIGHT units: the small weight should be "
        f"driven to nearly 0 and the large one barely touched; got remaining fractions {l2_small:.3f} and {l2_large:.3f}")
    return (f"flat loss, 100 steps, fraction of the weight left: AdamW {small:.3f} for both w0 = 0.1 and 10; "
            f"Adam + L2 {l2_small:.3f} and {l2_large:.3f}")


# =============================================================================
# Milestone 5: schedules and clipping
# =============================================================================
def m5():
    # the numbers printed in chapter 10 (total 1000, warmup 50, floor 0.1)
    for t, want in [(0, 0.0), (10, 0.2), (25, 0.5), (50, 1.0), (100, 0.994), (250, 0.905), (500, 0.587), (750, 0.245), (800, 0.195), (900, 0.124), (1000, 0.1)]:
        got = mod.warmup_cosine(t, 1000, 50)
        assert abs(got - want) < 6e-4, f"warmup_cosine({t}, total=1000, warmup=50) should be about {want}; got {got:.4f}"
    for t, want in [(0, 0.0), (10, 0.2), (50, 1.0), (500, 1.0), (799, 1.0), (800, 1.0), (900, 0.55), (1000, 0.1)]:
        got = mod.wsd(t, 1000, 50, 800)
        assert abs(got - want) < 6e-4, f"wsd({t}, total=1000, warmup=50, decay_start=800) should be about {want}; got {got:.4f}"
    assert near(mod.warmup_cosine(5, 100, 10), 0.5), "halfway through a 10-step warmup the multiplier is 0.5"
    assert near(mod.warmup_cosine(100, 100, 10, floor=0.25), 0.25) and near(mod.warmup_cosine(10, 100, 10, floor=0.25), 1.0), "floor sets the end value; the peak is exactly 1.0 at the end of warmup"
    assert near(mod.warmup_cosine(55, 100, 10, floor=0.0), 0.5), "the midpoint of the cosine (step 55 of 10..100) is halfway between 1 and the floor"
    assert near(mod.wsd(950, 1000, 50, 900, floor=0.0), 0.5), "wsd decays linearly: halfway through the decay phase the multiplier is halfway down"
    assert near(mod.warmup_cosine(0, 100, 0), 1.0), "with no warmup the schedule starts at its peak, 1.0 (careful with t / warmup)"
    for s in seeds(range(1, 5)):
        rng = random.Random(s)
        total, warm = rng.randint(100, 1000), rng.randint(1, 50)
        floor = rng.choice([0.0, 0.1, 0.3])
        ds = rng.randint(warm, total - 1)
        prev_c = prev_w = None
        for t in range(total + 1):
            c, w = mod.warmup_cosine(t, total, warm, floor), mod.wsd(t, total, warm, ds, floor)
            assert floor - 1e-12 <= c <= 1 + 1e-12 or t < warm, f"seed {s}: warmup_cosine({t}) = {c} left the range [floor, 1]"
            if t >= warm and prev_c is not None and t > warm:
                assert c <= prev_c + 1e-12, f"seed {s}: warmup_cosine must not increase after warmup (step {t}: {prev_c} -> {c})"
                assert w <= prev_w + 1e-12, f"seed {s}: wsd must not increase after warmup (step {t}: {prev_w} -> {w})"
            prev_c, prev_w = c, w
        assert near(mod.warmup_cosine(total, total, warm, floor), floor) and near(mod.wsd(total, total, warm, ds, floor), floor), f"seed {s}: both schedules end at the floor"
        assert near(mod.wsd(ds, total, warm, ds, floor), 1.0), f"seed {s}: wsd is still 1.0 at decay_start"

    # clipping
    assert near(mod.global_norm([[3.0], [4.0]]), 5.0) and near(mod.global_norm([[1.0, 2.0, 2.0]]), 3.0), "global_norm is the L2 norm over ALL numbers in ALL gradients"
    assert near(mod.global_norm([[], [1.0]]), 1.0) and mod.global_norm([]) == 0.0, "empty lists contribute nothing"
    grads = [[3.0], [4.0]]
    clipped, norm, scale = mod.clip_by_global_norm(grads, 1.0)
    assert near(norm, 5.0) and near(scale, 0.2, 1e-5), f"[[3], [4]] has norm 5; clipping to 1 scales by 0.2; got norm {norm}, scale {scale}"
    assert vnear(clipped[0] + clipped[1], [0.6, 0.8], 1e-5), f"clipped gradients should be [[0.6], [0.8]]; got {clipped}"
    assert grads == [[3.0], [4.0]], "clip_by_global_norm must return new lists, not modify its input"
    small = [[0.1, -0.2], [0.05]]
    clipped, norm, scale = mod.clip_by_global_norm(small, 1.0)
    assert scale == 1.0 and clipped == small, f"a gradient already inside the limit must pass through untouched with scale exactly 1.0; got scale {scale}, {clipped}"
    for s in seeds(range(1, 7)):
        rng = random.Random(s)
        shapes = [rng.randint(1, 6) for _ in range(rng.randint(1, 4))]
        grads = [[rng.gauss(0, 1) * 10 ** rng.uniform(-2, 1) for _ in range(n)] for n in shapes]
        limit = rng.choice([0.1, 1.0, 5.0])
        clipped, norm, scale = mod.clip_by_global_norm(grads, limit)
        true_norm = math.sqrt(sum(x * x for g in grads for x in g))
        assert near(norm, true_norm), f"seed {s}: returned norm {norm} but the global norm is {true_norm}"
        after = math.sqrt(sum(x * x for g in clipped for x in g))
        if true_norm > limit:
            assert limit * (1 - 1e-4) <= after <= limit * (1 + 1e-9), f"seed {s}: a clipped gradient should have norm just under {limit}; got {after}"
        else:
            assert scale == 1.0 and near(after, true_norm), f"seed {s}: norm {true_norm:.3f} is within {limit}, so nothing should change"
        # one common factor: every gradient keeps its direction and the ratios between them
        for g, c in zip(grads, clipped):
            for x, y in zip(g, c):
                assert near(y, x * scale, 1e-9), f"seed {s}: all gradients must be multiplied by the SAME factor ({scale}); got {y} for {x}"
    return "schedules match the chapter-10 table; clipping caps the global norm and keeps the direction"


# =============================================================================
# Milestone 6: the race
# =============================================================================
def m6():
    quad = lambda v: (0.5 * v[0] ** 2, [v[0]])
    lr, loss = mod.best_lr(lambda r: mod.SGD(r), quad, [1.0], [0.5, 1.0, 1.5, 2.5, 3.0], 5)
    assert lr == 1.0 and loss == 0.0, (f"on f = x^2/2 the rate 1.0 lands exactly on the minimum in one step, 2.5 and 3.0 diverge; "
                                       f"best_lr should return (1.0, 0.0); got ({lr}, {loss})")
    lr, loss = mod.best_lr(lambda r: mod.SGD(r), mod.bowl, [1.0, 1.0], [1.0, 5.0, 10.0], 50)
    assert lr is None and loss == math.inf, f"when every rate diverges return (None, math.inf); got ({lr}, {loss})"
    lr, _ = mod.best_lr(lambda r: mod.SGD(r), lambda v: (0.0, [0.0]), [1.0], [0.1, 0.2, 0.3], 3)
    assert lr == 0.1, f"only a STRICTLY better loss replaces the current best, so on a tie the first (smallest) rate wins; got {lr}"
    assert len(mod.GRID) == 14 and mod.GRID[0] == 1e-4 and mod.GRID[-1] == 0.5, "GRID is given: 14 rates from 1e-4 to 0.5"

    # the race: the chapter-10 table, reproduced
    makers = {"SGD": lambda r: mod.SGD(r), "momentum 0.9": lambda r: mod.Momentum(r, 0.9),
              "RMSProp": lambda r: mod.RMSProp(r), "Adam": lambda r: mod.Adam(r)}
    surfaces = {"bowl (kappa=100)": (mod.bowl, [-1.5, 1.0]), "Rosenbrock": (mod.rosenbrock, [-1.2, 1.0])}
    expected = {  # the numbers printed in chapter 10 (NumPy there, plain lists here)
        "bowl (kappa=100)": {"SGD": 1.21e-05, "momentum 0.9": 4.16e-14, "RMSProp": 1.17e-03, "Adam": 1.95e-13},
        "Rosenbrock": {"SGD": 1.88e-01, "momentum 0.9": 1.61e-04, "RMSProp": 2.34e-01, "Adam": 3.50e-03},
    }
    table, lines = {}, []
    for sname, (fn, w0) in surfaces.items():
        table[sname] = {}
        for oname, make in makers.items():
            lr, loss = mod.best_lr(make, fn, w0, mod.GRID, 300)
            assert lr is not None, f"{oname} diverged at every rate on {sname}"
            table[sname][oname] = (lr, loss)
            want = expected[sname][oname]
            assert 0.8 * want < loss < 1.25 * want, (f"{sname}, {oname}: chapter 10 reports a best final loss of {want:.2e}; you got {loss:.2e} at lr {lr:.4f}. "
                                                      "Check best_lr (final loss after exactly 300 steps) and the optimiser from its milestone")
            lines.append(f"{sname:17s} {oname:13s} lr {lr:.4f}  loss {loss:.2e}")

    # train: bookkeeping on a deterministic problem
    constant = lambda w, t: (float(t), [3.0, 4.0])
    out = mod.train(mod.SGD(1.0), [0.0, 0.0], constant, 3, max_norm=1.0)
    assert vnear(out["w"], [-1.8, -2.4], 1e-4), f"three steps of lr 1 along a gradient clipped from norm 5 to 1 move the weights by 3 * [0.6, 0.8]; got {fmt(out['w'])}"
    assert out["clipped"] == 3 and out["losses"] == [0.0, 1.0, 2.0], f"expected 3 clipped steps and losses [0, 1, 2] (the loss seen at each step); got {out['clipped']} and {out['losses']}"
    out = mod.train(mod.SGD(1.0), [0.0, 0.0], constant, 2, max_norm=10.0)
    assert out["clipped"] == 0 and vnear(out["w"], [-6.0, -8.0]), f"a limit of 10 never triggers on a gradient of norm 5; got clipped={out['clipped']}, w={fmt(out['w'])}"
    opt = mod.SGD(0.5)
    out = mod.train(opt, [0.0], lambda w, t: (0.0, [1.0]), 4, schedule=lambda t: t / 4)
    assert vnear(out["lrs"], [0.0, 0.125, 0.25, 0.375]) and vnear(out["w"], [-0.375 - 0.25 - 0.125]), (
        f"the learning rate at step t is base * schedule(t): expected [0, 0.125, 0.25, 0.375]; got {fmt(out['lrs'])}")
    assert opt.lr == 0.5, "train must put the optimiser's base learning rate back when it finishes"
    out = mod.train(mod.SGD(0.1), [1.0], lambda w, t: (w[0], [w[0]]), 0)
    assert out["w"] == [1.0] and out["losses"] == [] and out["clipped"] == 0, "zero steps: nothing happens"

    # scenario 1: rare bad batches. Clipping at 5 catches the spikes (every 40th step) and nothing else.
    note = []
    for s in seeds(range(1, 5)):
        free = mod.train(mod.SGD(0.1), [1.0] * 5, mod.noisy_problem(s), 400)
        clip = mod.train(mod.SGD(0.1), [1.0] * 5, mod.noisy_problem(s), 400, max_norm=5.0)
        assert 9 <= clip["clipped"] <= 12, f"seed {s}: the 10 spike batches should be clipped and the ordinary ones not; clipped {clip['clipped']} steps"
        assert max(free["losses"]) > 10 * max(clip["losses"]), (
            f"seed {s}: without clipping a spike batch should throw the weights far away (peak loss {max(free['losses']):.1f}); "
            f"with clipping the loss should never exceed its starting value 2.5 by much (peak {max(clip['losses']):.2f})")
        tail = lambda r: sum(r["losses"][-100:]) / 100
        assert tail(clip) < tail(free) / 5, f"seed {s}: clipping should also leave a much lower loss at the end ({tail(clip):.3f} vs {tail(free):.3f})"
        note.append((max(free["losses"]), max(clip["losses"]), tail(free), tail(clip)))
    a = note[0]
    # scenario 2: a decaying schedule shrinks the noise floor
    calm = lambda s: mod.noisy_problem(s, spike_every=10 ** 9)
    for s in seeds(range(1, 5)):
        const = mod.train(mod.SGD(0.1), [1.0] * 5, calm(s), 400)
        cosine = mod.train(mod.SGD(0.1), [1.0] * 5, calm(s), 400, schedule=lambda t: mod.warmup_cosine(t, 400, 20, 0.0))
        tail = lambda r: sum(r["losses"][-50:]) / 50
        assert tail(cosine) < tail(const) / 2, (f"seed {s}: with noisy gradients a constant rate jitters around the minimum; cosine decay to 0 should leave a "
                                                f"much lower loss at the end ({tail(cosine):.4f} vs {tail(const):.4f})")
        assert near(cosine["lrs"][20], 0.1) and cosine["lrs"][0] == 0.0, "the recorded rates must follow base * schedule(t)"
    return "\n".join(lines) + f"\nspike run (seed 1): peak loss {a[0]:.1f} unclipped vs {a[1]:.2f} clipped; final loss {a[2]:.3f} vs {a[3]:.3f}"


MILESTONES = [
    (1, "Milestone 1: surfaces, SGD and the loop", m1),
    (2, "Milestone 2: momentum", m2),
    (3, "Milestone 3: RMSProp and Adam", m3),
    (4, "Milestone 4: L2 penalty versus decoupled weight decay", m4),
    (5, "Milestone 5: schedules and gradient clipping", m5),
    (6, "Milestone 6: the race, with clipping and a schedule", m6),
]

if __name__ == "__main__":
    t0 = time.time()
    print(f"Lab 3 checks against {target}.py\n")
    for n, name, fn in MILESTONES:
        check(n, name, fn)
    print(f"\n{sum(results)}/{len(results)} milestones passing  ({time.time() - t0:.1f} s)")
    sys.exit(0 if all(results) else 1)
