"""Self-check for Lab 4: Train a Tiny GPT.

    python3 check.py                  # checks your starter.py
    python3 check.py solution         # checks the reference solution
    python3 check.py solution 3       # only milestone 3
    python3 check.py solution 1 7     # milestone 1, replaying ONLY the random case with seed 7

Everything is seeded: the weights, the order of the training names, the sampling. There is no clock
and no network, so every run gives identical numbers. Milestones 4 and 5 train one model for 600
steps (about 20 seconds in pure Python; the trained model is shared by both milestones).
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
V = mod.V
LN_V = math.log(V)


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


def rel_err(a, b):
    return abs(a - b) / max(1e-8, abs(a) + abs(b))


def grad_check(build, leaves, tol=1e-5, eps=1e-6, what="gradient"):
    """build() makes a fresh scalar Value from the CURRENT .data of the leaves. Compare backward() with central differences."""
    for v in leaves:
        v.grad = 0.0
    out = build()
    out.backward()
    analytic = [v.grad for v in leaves]
    for v, a in zip(leaves, analytic):
        old = v.data
        v.data = old + eps
        hi = build().data
        v.data = old - eps
        lo = build().data
        v.data = old
        numeric = (hi - lo) / (2 * eps)
        assert rel_err(a, numeric) < tol or abs(a - numeric) < 1e-9, (
            f"{what}: backward() says {a:.8g} but a finite difference says {numeric:.8g} (leaf value {old:.4f}); "
            "a local derivative is wrong, or a gradient is assigned (=) where it must be accumulated (+=)")
    return out.data


# =============================================================================
# Milestone 1: the autograd engine
# =============================================================================
def m1():
    Value = mod.Value
    a, b = Value(2.0), Value(-3.0)
    c = a * b + a ** 2                       # -6 + 4 = -2
    c.backward()
    assert near(c.data, -2.0) and near(a.grad, -3.0 + 4.0) and near(b.grad, 2.0), \
        f"c = a*b + a**2 at a=2, b=-3: expected c=-2, dc/da=b+2a=1, dc/db=a=2; got c={c.data}, da={a.grad}, db={b.grad}"
    x = Value(3.0)
    y = x * x + x                            # the same node used three times
    y.backward()
    assert near(y.data, 12.0) and near(x.grad, 7.0), (f"y = x*x + x at x=3: dy/dx = 2x + 1 = 7; got {x.grad}. "
                                                     "A Value used several times must ADD up the gradients from every use (+=)")
    p, q = Value(5.0), Value(2.0)
    z = (p + q) * (p - q)                    # p^2 - q^2: a diamond in the graph
    z.backward()
    assert near(z.data, 21.0) and near(p.grad, 10.0) and near(q.grad, -4.0), \
        f"(p+q)*(p-q) at 5, 2: expected 21 with gradients 10 and -4; got {z.data}, {p.grad}, {q.grad}. Process each node once, after everything that uses it"
    for f, val, g, name in [(lambda v: v.exp(), math.e, math.e, "exp"), (lambda v: v.log(), 0.0, 1.0, "log"),
                            (lambda v: v ** -1, 1.0, -1.0, "v ** -1"), (lambda v: v ** 0.5, 1.0, 0.5, "v ** 0.5")]:
        v = Value(1.0)
        o = f(v)
        o.backward()
        assert near(o.data, val, 1e-9) and near(v.grad, g, 1e-9), f"{name} at 1.0: expected value {val} and slope {g}; got {o.data} and {v.grad}"
    for xv, slope in [(2.5, 1.0), (-2.5, 0.0), (0.0, 0.0)]:
        v = Value(xv)
        o = v.relu()
        o.backward()
        assert near(o.data, max(0.0, xv)) and v.grad == slope, f"relu({xv}): expected value {max(0.0, xv)} and slope {slope}; got {o.data} and {v.grad}"
    # operators with plain numbers and the ones derived from yours
    v = Value(4.0)
    r = 1 + 2 * v - v / 8 + 3 / v - (-v)
    r.backward()
    assert near(r.data, 1 + 8 - 0.5 + 0.75 + 4) and near(v.grad, 2 - 1 / 8 - 3 / 16 + 1), "numbers on either side of an operator must work"
    # a graph 20,000 nodes deep must not hit Python's recursion limit
    deep = Value(1.0)
    root = deep
    for _ in range(20000):
        root = root * 1.0001 + 0.0
    root.backward()
    assert near(deep.grad, 1.0001 ** 20000, 1e-6 * 1.0001 ** 20000), "gradient through a 20,000-node chain is wrong"

    note_n = 0
    for sd in seeds(range(1, 31)):
        rng = random.Random(sd)
        leaves = [Value(rng.uniform(-2, 2)) for _ in range(3)]

        def build():
            pool = list(leaves)
            r = random.Random(sd * 1000 + 1)             # same expression every time build() is called
            for _ in range(r.randint(5, 12)):
                u, w = r.choice(pool), r.choice(pool)
                op = r.randrange(8)
                if op == 0: n = u + w
                elif op == 1: n = u * w
                elif op == 2: n = u - w
                elif op == 3: n = u / (w * w + 1.0)
                elif op == 4: n = (u * 0.3).exp()
                elif op == 5: n = (u * u + 1.0).log()
                elif op == 6: n = u.relu() + 0.1 * w
                else: n = (u * u + 0.5) ** -0.5
                pool.append(n)
            out = pool[-1]
            for extra in pool[3:-1]:                     # use every intermediate result so that nothing is dead
                out = out + 0.01 * extra
            return out
        grad_check(build, leaves, what=f"seed {sd}, a random expression")
        note_n += 1
    return f"hand-derived gradients, reuse of a node, a diamond, 20,000-deep chains, and {note_n} random expressions agree with finite differences"


# =============================================================================
# Milestone 2: layers on Values
# =============================================================================
def vec(rng, n, scale=1.0):
    return [mod.Value(rng.gauss(0, scale)) for _ in range(n)]


def m2():
    Value = mod.Value
    W = [[Value(1.0), Value(0.0), Value(1.0)], [Value(0.0), Value(1.0), Value(-1.0)]]
    out = mod.linear([Value(1.0), Value(2.0), Value(3.0)], W)
    assert [o.data for o in out] == [4.0, -1.0], f"linear: W (2, 3) times x (3) should give [4, -1]; got {[o.data for o in out]}"
    p = mod.softmax([Value(2.0), Value(1.0), Value(0.1)])
    assert all(near(a.data, b, 1e-9) for a, b in zip(p, [0.6590011388859679, 0.2424329707047139, 0.09856589040931818])), \
        f"softmax([2, 1, 0.1]) should be [0.659, 0.2424, 0.0986]; got {[round(v.data, 4) for v in p]}"
    big = mod.softmax([Value(1000.0), Value(1001.0)])
    assert near(big[1].data, 0.7310585786300049, 1e-12), "softmax of logits (1000, 1001) overflows unless you subtract the maximum first"
    n = mod.rmsnorm([Value(3.0), Value(4.0)], eps=0.0)
    s = math.sqrt((9 + 16) / 2)
    assert near(n[0].data, 3 / s, 1e-9) and near(n[1].data, 4 / s, 1e-9), f"rmsnorm([3, 4], eps=0) should be [0.8485, 1.1314]; got {[round(v.data, 4) for v in n]}"
    ce = mod.cross_entropy([Value(2.0), Value(1.0), Value(0.1)], 0)
    assert near(ce.data, 0.4170300162, 1e-8), f"cross_entropy([2, 1, 0.1], 0) should be 0.417 (chapter 02); got {ce.data}"
    lg = [Value(2.0), Value(1.0), Value(0.1)]
    mod.cross_entropy(lg, 0).backward()
    assert all(near(g.grad, e, 1e-8) for g, e in zip(lg, [0.6590011388859679 - 1, 0.2424329707047139, 0.09856589040931818])), \
        f"the gradient of the loss on the logits is p - onehot = [-0.341, 0.2424, 0.0986]; got {[round(v.grad, 4) for v in lg]}"
    for sd in seeds(range(1, 13)):
        rng = random.Random(sd)
        n_in, n_out = rng.randint(1, 6), rng.randint(1, 6)
        x = vec(rng, n_in)
        Wm = [vec(rng, n_in) for _ in range(n_out)]
        leaves = x + [w for row in Wm for w in row]
        weights = [rng.uniform(-1, 1) for _ in range(n_out)]
        def f_lin():
            return sum((o * wt for o, wt in zip(mod.linear(x, Wm), weights)), mod.Value(0.0))
        grad_check(f_lin, leaves, what=f"seed {sd}: linear")
        logits = vec(rng, rng.randint(2, 8), 3.0)
        probs = mod.softmax(logits)
        assert near(sum(q.data for q in probs), 1.0, 1e-12) and all(q.data > 0 for q in probs), f"seed {sd}: softmax must give positive probabilities that sum to 1"
        mx = max(l.data for l in logits)
        e = [math.exp(l.data - mx) for l in logits]
        assert all(near(q.data, ei / sum(e), 1e-12) for q, ei in zip(probs, e)), f"seed {sd}: softmax values differ from the reference"
        wts = [rng.uniform(-1, 1) for _ in logits]
        grad_check(lambda: sum((q * wt for q, wt in zip(mod.softmax(logits), wts)), mod.Value(0.0)), logits, what=f"seed {sd}: softmax")
        tgt = rng.randrange(len(logits))
        grad_check(lambda: mod.cross_entropy(logits, tgt), logits, what=f"seed {sd}: cross_entropy")
        xs = vec(rng, rng.randint(2, 8), 2.0)
        r = mod.rmsnorm(xs)
        assert near(sum(v.data ** 2 for v in r) / len(r), 1.0, 1e-3), f"seed {sd}: after rmsnorm the mean square of the vector should be 1"
        wts = [rng.uniform(-1, 1) for _ in xs]
        grad_check(lambda: sum((o * wt for o, wt in zip(mod.rmsnorm(xs), wts)), mod.Value(0.0)), xs, what=f"seed {sd}: rmsnorm")
    return "linear, softmax (stable), rmsnorm and cross_entropy match hand values; gradients match finite differences on 12 random cases"


# =============================================================================
# Milestone 3: the model
# =============================================================================
def floats(params):
    return {k: [[v.data for v in row] for row in m] for k, m in params.items()}


def o_rms(x, eps=1e-5):
    s = (sum(v * v for v in x) / len(x) + eps) ** -0.5
    return [v * s for v in x]


def o_lin(x, W):
    return [sum(w * v for w, v in zip(row, x)) for row in W]


def o_logits(cfg, P, ids):
    """Independent reference: the whole sequence at once with a causal mask (the style of Lab 3), plain floats."""
    C, h, L = cfg["C"], cfg["h"], cfg["L"]
    d_k, n = C // h, len(ids)
    x = [[a + b for a, b in zip(P["wte"][i], P["wpe"][t])] for t, i in enumerate(ids)]
    for l in range(L):
        xn = [o_rms(r) for r in x]
        Q = [o_lin(r, P[f"l{l}.wq"]) for r in xn]
        K = [o_lin(r, P[f"l{l}.wk"]) for r in xn]
        Vv = [o_lin(r, P[f"l{l}.wv"]) for r in xn]
        cat = [[0.0] * C for _ in range(n)]
        for i in range(h):
            sl = slice(i * d_k, (i + 1) * d_k)
            for t in range(n):
                sc = [sum(a * b for a, b in zip(Q[t][sl], K[j][sl])) / math.sqrt(d_k) for j in range(t + 1)]
                m = max(sc)
                e = [math.exp(s - m) for s in sc]
                w = [v / sum(e) for v in e]
                for c in range(sl.start, sl.stop):
                    cat[t][c] = sum(w[j] * Vv[j][c] for j in range(t + 1))
        x = [[a + b for a, b in zip(r, o_lin(c, P[f"l{l}.wo"]))] for r, c in zip(x, cat)]
        x = [[a + b for a, b in zip(r, o_lin([max(0.0, v) for v in o_lin(o_rms(r), P[f"l{l}.w1"])], P[f"l{l}.w2"]))] for r in x]
    return [o_lin(o_rms(r), P["head"]) for r in x]


def o_loss(cfg, P, ids):
    ids = ids[:cfg["T"] + 1]
    lg = o_logits(cfg, P, ids[:-1])
    total = 0.0
    for t, row in enumerate(lg):
        m = max(row)
        total += -(row[ids[t + 1]] - m - math.log(sum(math.exp(v - m) for v in row)))
    return total / len(lg)


def m3():
    cfg = {"V": V, "C": 4, "h": 2, "T": 5, "L": 2}
    params = mod.init_params(cfg, seed=3, std=0.4)
    P = floats(params)
    ids = mod.encode("ana")                       # [0, 1, 14, 1, 0]
    assert ids == [0, 1, 14, 1, 0], f"encode('ana') should be [0, 1, 14, 1, 0]; got {ids}"
    keys = [[] for _ in range(cfg["L"])]
    values = [[] for _ in range(cfg["L"])]
    ref = o_logits(cfg, P, ids[:-1])
    for pos, tok in enumerate(ids[:-1]):
        lg = mod.gpt_step(cfg, params, tok, pos, keys, values)
        assert len(lg) == V, f"gpt_step must return V = {V} logits; got {len(lg)}"
        assert all(isinstance(v, mod.Value) for v in lg), "the logits must be Values, or no gradient can flow back to the weights"
        assert all(len(keys[l]) == pos + 1 and len(values[l]) == pos + 1 for l in range(cfg["L"])), \
            f"after processing position {pos} each layer's key and value cache should hold {pos + 1} entries (the token reads itself too)"
        assert all(len(k) == cfg["C"] for k in keys[0]), "a cached key is one vector of C numbers"
        d = max(abs(a.data - b) for a, b in zip(lg, ref[pos]))
        assert d < 1e-9, (f"position {pos}: logits differ from the full-sequence reference by {d:.3g} (C=4, h=2, L=2). "
                          "Check: the 1/sqrt(d_k) factor, the head slices, the residuals, and that K and V are cached before attending")
    # causality: a different FUTURE leaves earlier logits identical
    k1, v1 = [[] for _ in range(2)], [[] for _ in range(2)]
    k2, v2 = [[] for _ in range(2)], [[] for _ in range(2)]
    a = [mod.gpt_step(cfg, params, t, p, k1, v1) for p, t in enumerate([0, 5, 7, 9])]
    b = [mod.gpt_step(cfg, params, t, p, k2, v2) for p, t in enumerate([0, 5, 7, 20])]
    assert all(x.data == y.data for r1, r2 in zip(a[:3], b[:3]) for x, y in zip(r1, r2)) and any(x.data != y.data for x, y in zip(a[3], b[3])), \
        "changing token 3 must change the logits at position 3 and leave positions 0 to 2 identical"
    # sequence loss
    for name in ("ana", "zoe", "willow", "bo"):
        got = mod.sequence_loss(cfg, params, mod.encode(name)).data
        want = o_loss(cfg, P, mod.encode(name))
        assert near(got, want, 1e-9), f"sequence_loss for {name!r} should be {want:.6f}; got {got:.6f} (mean over the {len(name) + 1} predictions)"
    long_ids = mod.encode("willow")
    assert len(long_ids) > cfg["T"] + 1 and near(mod.sequence_loss(cfg, params, long_ids).data, o_loss(cfg, P, long_ids[:cfg["T"] + 1]), 1e-9), \
        "a name longer than the context must be cut to T + 1 ids (T inputs and their targets)"

    # the whole thing against finite differences, on a tiny model: every kind of weight gets checked
    cfg2 = {"V": V, "C": 4, "h": 2, "T": 4, "L": 1}
    p2 = mod.init_params(cfg2, seed=9, std=0.3)
    rng = random.Random(ONLY_SEED if ONLY_SEED is not None else 5)
    picks = []
    for key, mat in p2.items():
        for _ in range(3 if key in ("wte", "head") else 4):
            picks.append(rng.choice(rng.choice(mat)))
    for nm in ("ana", "mia"):
        ids2 = mod.encode(nm)
        picks += [p2["wte"][ids2[1]][0], p2["wpe"][0][1]]
        grad_check(lambda: mod.sequence_loss(cfg2, p2, ids2), picks, tol=1e-5, eps=1e-5, what=f"model gradient on {nm!r}")
    # an untrained model is as surprised as chance
    cfg3 = dict(mod.CFG)
    p3 = mod.init_params(cfg3, seed=0)
    ls = [mod.sequence_loss(cfg3, p3, mod.encode(n)).data for n in mod.TRAIN[:12]]
    mean = sum(ls) / len(ls)
    assert abs(mean - LN_V) < 0.25, f"an untrained model should have a loss near ln {V} = {LN_V:.3f}; yours averages {mean:.3f}"
    n_params = len(mod.flat_params(p3))
    return (f"logits match an independent full-sequence reference to 1e-9 (L=2, h=2); the model is causal; gradients of {len(picks)} sampled\n"
            f"weights match finite differences; untrained loss {mean:.3f} vs ln {V} = {LN_V:.3f}; the training model has {n_params:,} weights")


# =============================================================================
# Milestone 4: Adam and training
# =============================================================================
_TRAINED = {}


def trained():
    if "m" not in _TRAINED:
        t0 = time.time()
        params, losses = mod.train(mod.CFG, mod.TRAIN, 600, seed=0)
        _TRAINED["m"] = (params, losses, time.time() - t0)
    return _TRAINED["m"]


def m4():
    Value = mod.Value
    pv = Value(1.0)
    opt = mod.Adam([pv], lr=0.1)
    pv.grad = 0.5
    opt.step()
    assert near(pv.data, 0.9, 1e-6), f"first Adam step with gradient 0.5 and lr 0.1: bias correction makes the step lr * sign(g) = 0.1, so 0.9; got {pv.data}"
    assert pv.grad == 0.0, "step() must reset every gradient to 0 for the next backward pass"
    # reference Adam on a short gradient sequence
    gs = [0.5, -0.2, 0.7, 0.1]
    p_ref, m_, v_ = 1.0, 0.0, 0.0
    pv2 = Value(1.0)
    opt2 = mod.Adam([pv2], lr=0.05, beta1=0.9, beta2=0.99, eps=1e-8)
    for t, g in enumerate(gs, 1):
        m_ = 0.9 * m_ + 0.1 * g
        v_ = 0.99 * v_ + 0.01 * g * g
        p_ref -= 0.05 * (m_ / (1 - 0.9 ** t)) / (math.sqrt(v_ / (1 - 0.99 ** t)) + 1e-8)
        pv2.grad = g
        opt2.step()
        assert near(pv2.data, p_ref, 1e-9), f"Adam step {t}: expected {p_ref:.9f}; got {pv2.data:.9f}"
    pv3 = Value(5.0)
    opt3 = mod.Adam([pv3], lr=0.1)
    pv3.grad = 1.0
    opt3.step(lr=0.0)
    assert pv3.data == 5.0, "step(lr=...) overrides the learning rate for that step"
    # it really optimises: minimise (w - 3)^2 + (u + 1)^2
    w, u = Value(0.0), Value(0.0)
    opt4 = mod.Adam([w, u], lr=0.1)
    for _ in range(300):
        loss = (w - 3.0) ** 2 + (u + 1.0) ** 2
        loss.backward()
        opt4.step()
    assert abs(w.data - 3.0) < 0.05 and abs(u.data + 1.0) < 0.05, f"Adam should find the minimum (3, -1); got ({w.data:.3f}, {u.data:.3f})"

    # train(): determinism and seeds
    tiny = {"V": V, "C": 4, "h": 2, "T": 4, "L": 1}
    p1, l1 = mod.train(tiny, mod.TRAIN, 4, seed=2)
    p2, l2 = mod.train(tiny, mod.TRAIN, 4, seed=2)
    p3, l3 = mod.train(tiny, mod.TRAIN, 4, seed=3)
    assert len(l1) == 4 and l1 == l2 and [v.data for v in mod.flat_params(p1)] == [v.data for v in mod.flat_params(p2)], \
        "the same seed must give the same losses and the same weights, bit for bit"
    assert l1 != l3, "a different seed should change the initial weights and the order of the names"
    assert all(v.grad == 0.0 for v in mod.flat_params(p1)), "gradients must be reset after every step"
    # the real run
    params, losses, secs = trained()
    first, last = sum(losses[:10]) / 10, sum(losses[-50:]) / 50
    assert abs(first - LN_V) < 0.4, f"the first ten steps should score near chance, ln {V} = {LN_V:.2f}; got {first:.2f}"
    assert last < 2.45, (f"after 600 steps the average loss of the last 50 should be below 2.45 nats; yours is {last:.3f} "
                         "(first ten steps: %.3f). Check that you call backward() on the loss, step the optimiser, and decay the rate" % first)
    return (f"Adam matches a reference to 1e-9; train() is deterministic\n"
            f"600 steps in {secs:.0f} s: loss {first:.2f} (first 10) -> {last:.2f} (last 50), chance is {LN_V:.2f}")


# =============================================================================
# Milestone 5: evaluating and sampling
# =============================================================================
def m5():
    params, losses, _ = trained()
    cfg = mod.CFG
    # average_loss against the independent reference, on a tiny untrained model
    tiny = {"V": V, "C": 4, "h": 2, "T": 4, "L": 1}
    pt = mod.init_params(tiny, seed=4, std=0.3)
    P = floats(pt)
    names = ["ana", "bo", "willow", "zoe"]
    tot = cnt = 0
    for nm in names:
        ids = mod.encode(nm)[:tiny["T"] + 1]
        tot += o_loss(tiny, P, ids) * (len(ids) - 1)
        cnt += len(ids) - 1
    got = mod.average_loss(tiny, pt, names)
    assert near(got, tot / cnt, 1e-9), (f"average_loss should weight every prediction equally: expected {tot / cnt:.6f}; got {got:.6f}. "
                                        "Longer names count for more; do not average the per-name means")
    assert isinstance(got, float), "average_loss returns a plain float, not a Value"
    # generalisation
    held = mod.average_loss(cfg, params, mod.HELD_OUT)
    train_l = mod.average_loss(cfg, params, mod.TRAIN)
    assert held < 2.6, f"the trained model should score under 2.6 nats on the {len(mod.HELD_OUT)} held-out names (chance is {LN_V:.2f}); got {held:.3f}"
    # sampling: determinism and structure
    s1 = [mod.sample_name(cfg, params, random.Random(7 + i)) for i in range(5)]
    s2 = [mod.sample_name(cfg, params, random.Random(7 + i)) for i in range(5)]
    assert s1 == s2, "the same rng seed must give the same name"
    rng = random.Random(1)
    samples = [mod.sample_name(cfg, params, rng) for _ in range(60)]
    assert all(isinstance(s, str) and 0 <= len(s) <= cfg["T"] and set(s) <= set(mod.CHARS) for s in samples), \
        f"names are strings of at most T = {cfg['T']} letters a to z (BOS is not part of the name)"
    assert len(set(samples)) >= 12, f"60 samples at temperature 1 should include at least 12 different names; got {len(set(samples))}"
    pairs = {(a, b) for n in mod.TRAIN for a, b in zip("^" + n, n + "$")}
    ok = tot2 = 0
    for s in samples:
        for a, b in zip("^" + s, s + "$"):
            tot2 += 1
            ok += (a, b) in pairs
    frac = ok / tot2
    assert frac > 0.8, (f"at least 80% of the letter pairs in sampled names (including start and end) should occur in the training names; "
                        f"yours: {frac:.0%}. Random letters would give about 30%")
    novel = sum(s not in mod.NAMES for s in samples if s)
    assert novel >= 25, f"the model should invent names, not recite: {novel} of {len(samples)} samples are new"
    # temperature: a tiny temperature is greedy decoding
    greedy_ref = []
    ids = [mod.BOS]
    P2 = floats(params)
    for _ in range(cfg["T"]):
        lg = o_logits(cfg, P2, ids)[-1]
        nxt = max(range(V), key=lambda i: lg[i])
        if nxt == mod.BOS:
            break
        greedy_ref.append(nxt)
        ids.append(nxt)
    g = mod.sample_name(cfg, params, random.Random(0), temperature=0.01)
    assert g == mod.decode(greedy_ref), f"temperature 0.01 should pick the most likely letter every time: expected {mod.decode(greedy_ref)!r}; got {g!r}"
    hot = {mod.sample_name(cfg, params, random.Random(i), temperature=3.0) for i in range(30)}
    cold = {mod.sample_name(cfg, params, random.Random(i), temperature=0.3) for i in range(30)}
    assert len(hot) > len(cold), f"a high temperature should give more variety than a low one: {len(hot)} distinct vs {len(cold)}"
    show = ", ".join(sorted({s for s in samples if s})[:14])
    return (f"held-out loss {held:.2f} nats (train {train_l:.2f}, chance {LN_V:.2f}); {frac:.0%} of sampled letter pairs occur in the data; {novel}/60 samples are new\n"
            f"samples: {show}")


MILESTONES = [
    (1, "Milestone 1: a scalar autograd engine", m1),
    (2, "Milestone 2: linear, softmax, rmsnorm and the loss", m2),
    (3, "Milestone 3: the GPT, one token at a time", m3),
    (4, "Milestone 4: Adam and the training loop", m4),
    (5, "Milestone 5: held-out loss and sampling names", m5),
]

if __name__ == "__main__":
    t0 = time.time()
    print(f"Lab 4 checks against {target}.py\n")
    for n, name, fn in MILESTONES:
        check(n, name, fn)
    print(f"\n{sum(results)}/{len(results)} milestones passing  ({time.time() - t0:.1f} s)")
    sys.exit(0 if all(results) else 1)
