"""Self-check for Lab 1: A Neural Network from Scratch.

    python3 check.py                  # checks your starter.py
    python3 check.py solution         # checks the reference solution
    python3 check.py solution 4       # only milestone 4
    python3 check.py solution 4 17    # milestone 4, replaying ONLY the random case with seed 17

Everything is seeded: the toy data, the weights, the random test matrices. There is no
clock and no network, so every run gives identical numbers. The whole check takes a few seconds.
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
        where = next((f"{f.name}() line {f.lineno}" for f in reversed(tb) if f.filename.endswith(f"{target}.py")), "?")
        print(f"  ✘ {name}: {type(e).__name__}: {e}   [in {where}]")
        results.append(False)


def close(A, B, tol=1e-9):
    """True if two matrices (or vectors, or numbers) agree elementwise."""
    if isinstance(A, (int, float)):
        return abs(A - B) <= tol
    if len(A) != len(B):
        return False
    return all(close(a, b, tol) for a, b in zip(A, B))


def rand_matrix(rng, m, n):
    return [[round(rng.uniform(-2, 2), 3) for _ in range(n)] for _ in range(m)]


def deep_copy(A):
    return [row[:] for row in A] if A and isinstance(A[0], list) else A[:]


# =============================================================================
# Independent reference pieces used only by the checker (plain loops, no clever tricks)
# =============================================================================
def ref_matmul(A, B):
    m, n, p = len(A), len(B), len(B[0])
    out = [[0.0] * p for _ in range(m)]
    for i in range(m):
        for j in range(p):
            for k in range(n):
                out[i][j] += A[i][k] * B[k][j]
    return out


def ref_loss(params, X, y):
    """Mean softmax cross-entropy of the two-layer ReLU network, written independently."""
    total = 0.0
    for x, label in zip(X, y):
        h = []
        for j in range(len(params["b1"])):
            z = params["b1"][j] + sum(x[i] * params["W1"][i][j] for i in range(len(x)))
            h.append(max(0.0, z))
        logits = []
        for k in range(len(params["b2"])):
            logits.append(params["b2"][k] + sum(h[j] * params["W2"][j][k] for j in range(len(h))))
        m = max(logits)
        lse = m + math.log(sum(math.exp(v - m) for v in logits))
        total += lse - logits[label]
    return total / len(y)


def copy_params(p):
    return {k: deep_copy(v) for k, v in p.items()}


# =============================================================================
# Milestone 1: matrix operations
# =============================================================================
def m1():
    A = [[1, 2], [3, 4]]
    B = [[5, 6], [7, 8]]
    assert close(mod.matmul(A, B), [[19, 22], [43, 50]]), f"matmul([[1,2],[3,4]], [[5,6],[7,8]]) should be [[19, 22], [43, 50]]; got {mod.matmul(A, B)}"
    got = mod.matmul([[1, 2, 3]], [[1], [0], [-1]])
    assert close(got, [[-2]]), f"a (1, 3) times (3, 1) is (1, 1): expected [[-2]], got {got}"
    got = mod.matmul([[1], [2]], [[3, 4, 5]])
    assert close(got, [[3, 4, 5], [6, 8, 10]]), f"(2, 1) times (1, 3) is (2, 3): expected [[3, 4, 5], [6, 8, 10]], got {got}"
    try:
        mod.matmul([[1, 2, 3]], [[1, 2, 3]])
    except ValueError:
        pass
    else:
        raise AssertionError("matmul of (1, 3) by (1, 3) must raise ValueError (inner sizes 3 and 1 differ)")

    assert mod.transpose([[1, 2, 3], [4, 5, 6]]) == [[1, 4], [2, 5], [3, 6]], "transpose of a (2, 3) matrix must be (3, 2): [[1, 4], [2, 5], [3, 6]]"
    assert mod.shape(mod.transpose([[1, 2, 3]])) == (3, 1), "transpose of a (1, 3) row must be a (3, 1) column"

    got = mod.add_bias([[1, 2, 3], [4, 5, 6]], [10, 20, 30])
    assert close(got, [[11, 22, 33], [14, 25, 36]]), f"add_bias adds b to EVERY row: expected [[11, 22, 33], [14, 25, 36]], got {got}"
    try:
        mod.add_bias([[1, 2]], [1, 2, 3])
    except ValueError:
        pass
    else:
        raise AssertionError("add_bias with a bias of the wrong length must raise ValueError")

    got = mod.col_sums([[1, 2, 3], [4, 5, 6]])
    assert close(list(got), [5, 7, 9]), f"col_sums sums DOWN the rows: expected [5, 7, 9], got {got}"
    got = mod.hadamard([[1, 2], [3, 4]], [[5, 6], [7, 8]])
    assert close(got, [[5, 12], [21, 32]]), f"hadamard is the elementwise product: expected [[5, 12], [21, 32]], got {got}"
    assert close(mod.scale([[1, -2]], 0.5), [[0.5, -1.0]]), "scale([[1, -2]], 0.5) should be [[0.5, -1.0]]"

    # Property checks on random sizes against plain triple loops, and algebraic identities.
    for seed in seeds(range(1, 31)):
        rng = random.Random(seed)
        m, n, p = rng.randint(1, 6), rng.randint(1, 6), rng.randint(1, 6)
        X, Y, Z = rand_matrix(rng, m, n), rand_matrix(rng, n, p), rand_matrix(rng, m, n)
        keep = (deep_copy(X), deep_copy(Y))
        got = mod.matmul(X, Y)
        assert close(got, ref_matmul(X, Y), 1e-9), f"[seed {seed}] matmul of {m}x{n} by {n}x{p} disagrees with the triple loop"
        assert (X, Y) == keep, f"[seed {seed}] matmul changed one of its arguments; build and return a new matrix"
        lhs, rhs = mod.transpose(got), mod.matmul(mod.transpose(Y), mod.transpose(X))
        assert close(lhs, rhs, 1e-9), f"[seed {seed}] (XY)^T must equal Y^T X^T; transpose or matmul is wrong"
        assert mod.transpose(mod.transpose(X)) == X, f"[seed {seed}] transposing twice must give the original"
        b = [round(rng.uniform(-1, 1), 3) for _ in range(n)]
        with_b = mod.add_bias(X, b)
        assert close(mod.col_sums(with_b), [s + m * bj for s, bj in zip(mod.col_sums(X), b)], 1e-9), \
            f"[seed {seed}] col_sums(add_bias(X, b)) should be col_sums(X) + {m} * b"
        assert close(mod.hadamard(X, Z), mod.hadamard(Z, X)), f"[seed {seed}] hadamard must be commutative"
    return "matmul, transpose, add_bias, col_sums, hadamard and scale agree with hand values and 30 random cases"


# =============================================================================
# Milestone 2: activations, softmax and the loss
# =============================================================================
def m2():
    assert mod.relu([[-1.5, 0.0, 2.0]]) == [[0.0, 0.0, 2.0]], "relu([[-1.5, 0, 2]]) should be [[0, 0, 2]]"
    assert mod.relu_grad([[-1.5, 0.0, 2.0]]) == [[0.0, 0.0, 1.0]], \
        "relu_grad is 1 where z > 0 and 0 elsewhere (including exactly 0): expected [[0, 0, 1]]"

    P = mod.softmax_rows([[2.0, 1.0, 0.1]])
    want = [0.65900114, 0.24243297, 0.09856589]
    assert close(P[0], want, 1e-6), f"softmax([2, 1, 0.1]) should be {want}; got {[round(p, 6) for p in P[0]]}"
    big = mod.softmax_rows([[1000.0, 1001.0]])
    assert close(big[0], [0.26894142, 0.73105858], 1e-6), \
        f"softmax([1000, 1001]) should be [0.2689, 0.7311]; got {big[0]}. Subtract the row max before exp so it cannot overflow."
    shifted = mod.softmax_rows([[3.0, 2.0, 1.1]])
    assert close(shifted[0], P[0], 1e-9), "softmax must not change when a constant is added to every logit in the row"
    two = mod.softmax_rows([[0.0, 0.0], [5.0, 5.0]])
    assert close(two, [[0.5, 0.5], [0.5, 0.5]]), "equal logits give equal probabilities, one row at a time"

    ce = mod.cross_entropy([want], [0])
    assert close(ce, 0.41703002, 1e-6), f"cross_entropy with p = (0.659, 0.242, 0.099) and true class 0 is -ln 0.659 = 0.4170; got {ce}"
    ce2 = mod.cross_entropy([[0.5, 0.5], [0.9, 0.1]], [0, 1])
    assert close(ce2, (math.log(2) + math.log(10)) / 2, 1e-9), "cross_entropy is the MEAN of -ln p[true class] over the batch rows"

    g = mod.softmax_ce_grad([want], [0])
    assert close(g[0], [want[0] - 1, want[1], want[2]], 1e-6), \
        f"gradient on the logits is p minus one-hot: expected {[-0.341, 0.2424, 0.0986]}; got {[round(v, 4) for v in g[0]]}"
    Pb = [[0.7, 0.3], [0.2, 0.8]]
    keep = deep_copy(Pb)
    g = mod.softmax_ce_grad(Pb, [0, 1])
    assert close(g, [[-0.15, 0.15], [0.1, -0.1]], 1e-9), \
        f"for a batch of 2 the gradient is (p - one_hot) / 2: expected [[-0.15, 0.15], [0.1, -0.1]]; got {g}. Did you divide by the batch size?"
    assert Pb == keep, "softmax_ce_grad changed the probabilities it was given; copy them first"

    for seed in seeds(range(1, 21)):
        rng = random.Random(seed)
        B, K = rng.randint(1, 5), rng.randint(2, 5)
        Z = rand_matrix(rng, B, K)
        y = [rng.randrange(K) for _ in range(B)]
        P = mod.softmax_rows(Z)
        assert all(abs(sum(r) - 1) < 1e-9 for r in P) and all(p > 0 for r in P for p in r), f"[seed {seed}] each softmax row must be positive and sum to 1"
        G = mod.softmax_ce_grad(P, y)
        assert all(abs(sum(r)) < 1e-9 for r in G), f"[seed {seed}] each row of the logit gradient must sum to 0 (probabilities sum to 1, the one-hot sums to 1)"
        eps = 1e-6
        for i in range(B):
            for k in range(K):
                Zp = deep_copy(Z); Zp[i][k] += eps
                Zm = deep_copy(Z); Zm[i][k] -= eps
                num = (mod.cross_entropy(mod.softmax_rows(Zp), y) - mod.cross_entropy(mod.softmax_rows(Zm), y)) / (2 * eps)
                assert abs(num - G[i][k]) < 1e-6, \
                    f"[seed {seed}] d loss / d logit[{i}][{k}]: finite difference says {num:.6f}, softmax_ce_grad says {G[i][k]:.6f}"
    return "relu, softmax_rows, cross_entropy and softmax_ce_grad agree with hand values and a finite-difference check"


# =============================================================================
# Milestone 3: parameters and the forward pass
# =============================================================================
def m3():
    p = mod.init_params((3, 5, 2), seed=0)
    assert set(p) >= {"W1", "b1", "W2", "b2"}, f"init_params must return a dict with W1, b1, W2, b2; got keys {sorted(p)}"
    assert mod.shape(p["W1"]) == (3, 5), f"W1 should have shape (C_in, H) = (3, 5); got {mod.shape(p['W1'])}"
    assert len(p["b1"]) == 5 and all(v == 0 for v in p["b1"]), "b1 should be five zeros"
    assert mod.shape(p["W2"]) == (5, 2), f"W2 should have shape (H, K) = (5, 2); got {mod.shape(p['W2'])}"
    assert len(p["b2"]) == 2 and all(v == 0 for v in p["b2"]), "b2 should be two zeros"
    assert mod.init_params((3, 5, 2), seed=0) == p, "the same seed must give identical parameters"
    assert mod.init_params((3, 5, 2), seed=1)["W1"] != p["W1"], "a different seed must give different weights"

    big = mod.init_params((40, 60, 3), seed=5)

    def std(M):
        flat = [x for r in M for x in r]
        mean = sum(flat) / len(flat)
        return math.sqrt(sum((x - mean) ** 2 for x in flat) / len(flat))

    s1, s2 = std(big["W1"]), std(big["W2"])
    w1, w2 = math.sqrt(2 / 40), math.sqrt(1 / 60)
    assert abs(s1 / w1 - 1) < 0.12, f"W1 should have standard deviation sqrt(2 / C_in) = {w1:.3f} (He initialisation); measured {s1:.3f}"
    assert abs(s2 / w2 - 1) < 0.2, f"W2 should have standard deviation sqrt(1 / H) = {w2:.3f}; measured {s2:.3f}"

    # The worked example of chapter 02: x = (1, 2), W1 = [[0.5, -1], [0.25, 0.25]], W2 = (0.6, -0.4)^T.
    q = {"W1": [[0.5, -1.0], [0.25, 0.25]], "b1": [0.0, 0.0], "W2": [[0.6], [-0.4]], "b2": [0.0]}
    keep = copy_params(q)
    logits, cache = mod.forward(q, [[1.0, 2.0]])
    assert close(logits, [[0.6]]), f"chapter 02's example: x = (1, 2) should give output 0.6; got {logits}"
    assert close(cache["z1"], [[1.0, -0.5]]), f"cache['z1'] should be the pre-activations [[1.0, -0.5]]; got {cache.get('z1')}"
    assert close(cache["a1"], [[1.0, 0.0]]), f"cache['a1'] should be ReLU of z1, [[1.0, 0.0]]; got {cache.get('a1')}"
    assert "X" in cache, "cache must also hold the input X (the backward pass needs it for dW1)"
    assert q == keep, "forward changed the parameters; it must only read them"
    q["b1"] = [1.0, 1.0]
    q["b2"] = [0.5]
    logits, _ = mod.forward(q, [[1.0, 2.0], [0.0, 0.0]])
    assert close(logits, [[2.0 * 0.6 + 0.5 * -0.4 + 0.5], [1.0 * 0.6 + 1.0 * -0.4 + 0.5]]), \
        f"with b1 = (1, 1) and b2 = (0.5): row 1 has z1 = (2, 0.5) and gives 2*0.6 + 0.5*(-0.4) + 0.5 = 1.5, and the zero input gives 0.6-0.4+0.5 = 0.7; got {logits}"

    for seed in seeds(range(1, 16)):
        rng = random.Random(seed)
        B, C, H, K = rng.randint(1, 5), rng.randint(1, 4), rng.randint(1, 6), rng.randint(2, 4)
        params = mod.init_params((C, H, K), seed=seed)
        params["b1"] = [round(rng.uniform(-1, 1), 2) for _ in range(H)]
        params["b2"] = [round(rng.uniform(-1, 1), 2) for _ in range(K)]
        X = rand_matrix(rng, B, C)
        logits, cache = mod.forward(params, X)
        assert mod.shape(logits) == (B, K), f"[seed {seed}] logits should have shape (B, K) = ({B}, {K}); got {mod.shape(logits)}"
        a1 = [[max(0.0, params['b1'][j] + sum(X[b][i] * params['W1'][i][j] for i in range(C))) for j in range(H)] for b in range(B)]
        want = [[params['b2'][k] + sum(a1[b][j] * params['W2'][j][k] for j in range(H)) for k in range(K)] for b in range(B)]
        assert close(logits, want, 1e-9), f"[seed {seed}] forward disagrees with a plain-loop network for shapes B={B}, C_in={C}, H={H}, K={K}"
    return "init_params has the right shapes and scale; forward reproduces chapter 02's example and 15 random networks"


# =============================================================================
# Milestone 4: backpropagation by hand
# =============================================================================
def diagnose(name, got, want, B):
    """Guess the usual mistake from the relation between the wrong gradient and the right one."""
    gf = [x for r in got for x in r] if got and isinstance(got[0], list) else list(got)
    wf = [x for r in want for x in r] if want and isinstance(want[0], list) else list(want)
    if len(gf) != len(wf):
        return f"{name} has {len(gf)} numbers but the parameter has {len(wf)}: a gradient always has the shape of the thing it differentiates"
    pairs = [(g, w) for g, w in zip(gf, wf) if abs(w) > 1e-6]
    if pairs:
        ratios = [g / w for g, w in pairs]
        r = sum(ratios) / len(ratios)
        if max(abs(x - r) for x in ratios) < 1e-6 * max(1, abs(r)):
            if abs(r - B) < 1e-6:
                return f"{name} is exactly B = {B} times too big: the loss is a MEAN, so the first gradient must be divided by the batch size"
            if abs(r + 1) < 1e-6:
                return f"{name} has the wrong sign everywhere"
    return f"{name} does not match the finite-difference gradient; recheck its formula and which cached value it uses"


def m4():
    # A hand-checked case built from chapter 02's network, with two output classes.
    params = {"W1": [[0.5, -1.0], [0.25, 0.25]], "b1": [0.0, 0.0], "W2": [[0.6, 0.2], [-0.4, 0.1]], "b2": [0.0, 0.0]}
    X, y = [[1.0, 2.0]], [0]
    logits, cache = mod.forward(params, X)
    g = mod.backward(params, cache, y)
    for key in ("dW1", "db1", "dW2", "db2"):
        assert key in g, f"backward must return a dict with dW1, db1, dW2, db2; missing {key}"
    p0 = 0.59868766
    want = {
        "dW2": [[-(1 - p0), 1 - p0], [0.0, 0.0]],            # a1 = (1, 0): only unit 1 was active
        "db2": [-(1 - p0), 1 - p0],                          # p - one_hot = (-0.4013, 0.4013)
        "dW1": [[-0.16052494, 0.0], [-0.32104987, 0.0]],     # the blocked ReLU unit gets nothing; x2 = 2 doubles row 2
        "db1": [-0.16052494, 0.0],
    }
    for key, w in want.items():
        assert close(g[key], w, 1e-6), (f"hand case (x = (1, 2), y = 0): {key} should be {w}; got {g[key]}. "
                                        "Work it through: p - one_hot = (-0.4013, 0.4013), da1 = dz2 W2^T = (-0.1605, 0.2007), ReLU blocks unit 2.")

    for seed in seeds([3, 11, 29]):
        rng = random.Random(seed)
        B, C, H, K = 5, 3, 6, 3
        params = mod.init_params((C, H, K), seed=seed)
        params["b1"] = [round(rng.uniform(-0.5, 0.5), 2) for _ in range(H)]
        params["b2"] = [round(rng.uniform(-0.5, 0.5), 2) for _ in range(K)]
        X = rand_matrix(rng, B, C)
        y = [rng.randrange(K) for _ in range(B)]
        logits, cache = mod.forward(params, X)
        keep = copy_params(params)
        g = mod.backward(params, cache, y)
        assert params == keep, f"[seed {seed}] backward must not change the parameters (training does that in sgd_step)"
        for name in ("W1", "b1", "W2", "b2"):
            P = params[name]
            G = g["d" + name]
            if isinstance(P[0], list):
                assert mod.shape(G) == mod.shape(P), f"[seed {seed}] d{name} has shape {mod.shape(G)} but {name} has shape {mod.shape(P)}"
            else:
                assert len(G) == len(P), f"[seed {seed}] d{name} has length {len(G)} but {name} has length {len(P)}"
            num = deep_copy(P)
            eps = 1e-6
            idxs = [(i, j) for i in range(len(P)) for j in range(len(P[0]))] if isinstance(P[0], list) else [(j,) for j in range(len(P))]
            for ix in idxs:
                def at(delta):
                    q = copy_params(params)
                    if len(ix) == 2:
                        q[name][ix[0]][ix[1]] += delta
                    else:
                        q[name][ix[0]] += delta
                    return ref_loss(q, X, y)
                val = (at(eps) - at(-eps)) / (2 * eps)
                if len(ix) == 2:
                    num[ix[0]][ix[1]] = val
                else:
                    num[ix[0]] = val
            flat_n = [x for r in num for x in r] if isinstance(P[0], list) else num
            flat_g = [x for r in G for x in r] if isinstance(P[0], list) else list(G)
            err = max(abs(a - b) for a, b in zip(flat_n, flat_g)) / (max(abs(a) for a in flat_n) + max(abs(b) for b in flat_g) + 1e-12)
            assert err < 1e-6, (f"[seed {seed}] gradient check failed for {name}: max relative error {err:.2e} (want below 1e-6). "
                                + diagnose("d" + name, G, num, B))
    return "dW1, db1, dW2, db2 match the hand case and a finite-difference gradient check (relative error below 1e-6)"


# =============================================================================
# Milestone 5: training
# =============================================================================
def m5():
    p = {"W1": [[1.0, 2.0]], "b1": [0.5, 0.5], "W2": [[1.0], [2.0]], "b2": [0.0]}
    grads = {"dW1": [[0.5, -1.0]], "db1": [1.0, 0.0], "dW2": [[2.0], [4.0]], "db2": [-1.0]}
    out = mod.sgd_step(p, grads, 0.1)
    assert out is None, "sgd_step updates the parameters in place and returns nothing"
    want = {"W1": [[0.95, 2.1]], "b1": [0.4, 0.5], "W2": [[0.8], [1.6]], "b2": [0.1]}
    for k, w in want.items():
        assert close(p[k], w, 1e-9), f"after one step with lr 0.1, {k} should be {w}; got {p[k]}. The rule is p <- p - lr * dp"

    q = {"W1": [[1.0, -1.0], [0.0, 0.0]], "b1": [0.0, 0.0], "W2": [[1.0, 0.0], [0.0, 1.0]], "b2": [0.0, 0.0]}
    X = [[2.0, 0.0], [-2.0, 0.0], [3.0, 1.0]]       # logits: (2,0)->(2,0) class 0, (-2,0)->(0,2) class 1, (3,1)->(3,0) class 0
    assert mod.predict(q, X) == [0, 1, 0], f"predict should take the argmax of the logits: expected [0, 1, 0]; got {mod.predict(q, X)}"
    assert close(mod.accuracy(q, X, [0, 1, 1]), 2 / 3), "accuracy is the fraction of rows predicted correctly: 2 of 3 here"

    X, y = mod.make_moons(200, seed=1)
    Xt, yt = mod.make_moons(200, seed=2)
    params = mod.init_params((2, 16, 2), seed=0)
    first = mod.loss_of(params, X, y)
    t = time.time()
    losses = mod.train(params, X, y, lr=0.5, epochs=300)
    secs = time.time() - t
    assert len(losses) == 300, f"train must return one loss per epoch (300 of them); got {len(losses)}"
    assert abs(losses[0] - first) < 1e-9, "losses[0] must be the loss BEFORE the first update (the loss of the freshly initialised network)"
    assert losses[-1] < 0.5 * losses[0], f"the loss should at least halve over 300 epochs: {losses[0]:.3f} -> {losses[-1]:.3f}. Check the sign in sgd_step and that train calls backward every epoch."
    final = mod.loss_of(params, X, y)
    assert abs(final - losses[-1]) < 0.05, "the parameters must be updated in place, so the loss after training matches the last recorded loss"
    tr, te = mod.accuracy(params, X, y), mod.accuracy(params, Xt, yt)
    assert tr >= 0.95, f"training accuracy on the two moons should reach 95%; got {tr:.1%} (final loss {losses[-1]:.3f})"
    assert te >= 0.92, f"accuracy on 200 NEW moon points should be at least 92%; got {te:.1%}"

    slow = mod.init_params((2, 16, 2), seed=0)
    small = mod.train(slow, X, y, lr=0.05, epochs=60)
    bumps = [i for i in range(1, len(small)) if small[i] > small[i - 1] + 1e-9]
    assert not bumps, f"with a small learning rate (0.05) full-batch gradient descent should never raise the loss, but it rose at epoch {bumps[0]}"

    again = mod.init_params((2, 16, 2), seed=0)
    assert mod.train(again, X, y, lr=0.5, epochs=300) == losses, "the same seed and data must reproduce the same loss curve exactly"

    Xx, yx = mod.make_xor(200, seed=1)
    Xxt, yxt = mod.make_xor(200, seed=4)
    xp = mod.init_params((2, 8, 2), seed=0)
    mod.train(xp, Xx, yx, lr=0.5, epochs=200)
    xa, xt = mod.accuracy(xp, Xx, yx), mod.accuracy(xp, Xxt, yxt)
    assert xa >= 0.95 and xt >= 0.93, f"XOR needs the hidden layer: expected at least 95% train and 93% test accuracy; got {xa:.1%} and {xt:.1%}"
    return (f"moons: loss {losses[0]:.3f} -> {losses[-1]:.3f}, train accuracy {tr:.1%}, test accuracy {te:.1%} ({secs:.1f} s)\n"
            f"XOR (8 hidden units): train {xa:.1%}, test {xt:.1%}")


check(1, "Milestone 1: matrix operations", m1)
check(2, "Milestone 2: activations, softmax and the loss", m2)
check(3, "Milestone 3: parameters and the forward pass", m3)
check(4, "Milestone 4: backpropagation by hand", m4)
check(5, "Milestone 5: training on moons and XOR", m5)

if ONLY is None or results:
    passed = sum(results)
    print(f"\n{passed}/{len(results)} milestones passing  ({time.time() - T0:.1f} s)")
