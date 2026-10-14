"""Self-check for Lab 3: Attention & a Transformer Block.

    python3 check.py                  # checks your starter.py
    python3 check.py solution         # checks the reference solution
    python3 check.py solution 3       # only milestone 3
    python3 check.py solution 3 17    # milestone 3, replaying ONLY the random case with seed 17

Everything is seeded: the random inputs, the random weights. There is no clock and no network,
so every run gives identical numbers. The whole check takes a few seconds.
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


def mat_near(A, B, tol=1e-9):
    return (len(A) == len(B) and all(len(ra) == len(rb) for ra, rb in zip(A, B))
            and all(near(a, b, tol) for ra, rb in zip(A, B) for a, b in zip(ra, rb)))


def rand_matrix(rng, rows, cols, scale=1.0):
    return [[rng.gauss(0.0, scale) for _ in range(cols)] for _ in range(rows)]


def max_diff(A, B):
    return max(abs(a - b) for ra, rb in zip(A, B) for a, b in zip(ra, rb))


# ---- independent oracles: deliberately written with scalar loops, not with the lab's helpers ----------
def o_matmul(A, B):
    return [[sum(A[i][k] * B[k][j] for k in range(len(B))) for j in range(len(B[0]))] for i in range(len(A))]


def o_softmax(row):
    m = max(row)
    e = [math.exp(v - m) for v in row]
    return [v / sum(e) for v in e]


def o_attention(Q, K, V, causal):
    T, d_k = len(Q), len(Q[0])
    out, W = [], []
    for i in range(T):
        scores = [sum(Q[i][c] * K[j][c] for c in range(d_k)) / math.sqrt(d_k) for j in range(T)
                  if (j <= i or not causal)]                 # only the keys that may be read
        w = o_softmax(scores)
        W.append(w + [0.0] * (T - len(w)))
        out.append([sum(w[j] * V[j][c] for j in range(len(w))) for c in range(len(V[0]))])
    return out, W


def o_mha(x, Wq, Wk, Wv, Wo, h, causal):
    T, C = len(x), len(x[0])
    d_k = C // h
    Q, K, V = o_matmul(x, Wq), o_matmul(x, Wk), o_matmul(x, Wv)
    cat = [[0.0] * C for _ in range(T)]
    for head in range(h):
        sl = slice(head * d_k, (head + 1) * d_k)
        o, _ = o_attention([r[sl] for r in Q], [r[sl] for r in K], [r[sl] for r in V], causal)
        for t in range(T):
            cat[t][sl] = o[t]
    return o_matmul(cat, Wo)


def o_ln(x, g, b, eps=1e-5):
    out = []
    for row in x:
        mu = sum(row) / len(row)
        var = sum((v - mu) ** 2 for v in row) / len(row)
        out.append([(v - mu) / math.sqrt(var + eps) * g[i] + b[i] for i, v in enumerate(row)])
    return out


def o_gelu(z):
    return 0.5 * z * (1 + math.tanh(math.sqrt(2 / math.pi) * (z + 0.044715 * z ** 3)))


def o_block(x, p, h, causal=True):
    a = o_mha(o_ln(x, p["ln1_g"], p["ln1_b"]), p["Wq"], p["Wk"], p["Wv"], p["Wo"], h, causal)
    x = [[u + v for u, v in zip(r1, r2)] for r1, r2 in zip(x, a)]
    n = o_ln(x, p["ln2_g"], p["ln2_b"])
    hid = [[o_gelu(v + p["b1"][j]) for j, v in enumerate(r)] for r in o_matmul(n, p["W1"])]
    m = [[v + p["b2"][j] for j, v in enumerate(r)] for r in o_matmul(hid, p["W2"])]
    return [[u + v for u, v in zip(r1, r2)] for r1, r2 in zip(x, m)]


# =============================================================================
# Milestone 1: softmax, layer normalisation, GELU
# =============================================================================
def m1():
    P = mod.softmax_rows([[2.0, 1.0, 0.1]])
    assert mat_near(P, [[0.6590011388859679, 0.2424329707047139, 0.09856589040931818]], 1e-9), \
        f"softmax([2, 1, 0.1]) should be [0.659, 0.2424, 0.0986] (chapter 02), got {P[0]}"
    big = mod.softmax_rows([[1000.0, 1001.0]])
    assert mat_near(big, [[0.2689414213699951, 0.7310585786300049]], 1e-12), \
        f"logits of 1000 must not overflow: expected [0.2689, 0.7311], got {big[0]}"
    masked = mod.softmax_rows([[0.5, -math.inf, 0.5, -math.inf]])
    assert masked == [[0.5, 0.0, 0.5, 0.0]], f"-inf entries must get weight exactly 0.0; got {masked[0]}"
    try:
        mod.softmax_rows([[-math.inf, -math.inf]])
    except ValueError:
        pass
    else:
        raise AssertionError("a row that is entirely -inf has no softmax: raise ValueError (the usual silent bug is a row of NaN)")
    assert mod.softmax_rows([[3.0, 3.0, 3.0]])[0] == [1 / 3] * 3 or mat_near(mod.softmax_rows([[3.0, 3.0, 3.0]]), [[1 / 3] * 3])

    # layer norm: hand values. Row (1, 2, 3): mean 2, variance 2/3, so (-1, 0, 1) / sqrt(2/3 + eps)
    y = mod.layernorm_rows([[1.0, 2.0, 3.0]], [1.0, 1.0, 1.0], [0.0, 0.0, 0.0], eps=0.0)
    s = 1 / math.sqrt(2 / 3)
    assert mat_near(y, [[-s, 0.0, s]], 1e-12), f"layernorm of (1, 2, 3) with eps=0 should be (-1.2247, 0, 1.2247); got {y[0]}"
    y = mod.layernorm_rows([[1.0, 2.0, 3.0]], [2.0, 2.0, 2.0], [10.0, 10.0, 10.0], eps=0.0)
    assert mat_near(y, [[10 - 2 * s, 10.0, 10 + 2 * s]], 1e-12), "gain multiplies and bias adds AFTER normalising"
    for sd in seeds(range(1, 11)):
        rng = random.Random(sd)
        rows, cols = rng.randint(1, 6), rng.randint(2, 12)
        S = [[rng.gauss(0, 3) for _ in range(cols)] for _ in range(rows)]
        got = mod.softmax_rows(S)
        for r, g in zip(S, got):
            assert near(sum(g), 1.0, 1e-12) and mat_near([g], [o_softmax(r)], 1e-12), f"seed {sd}: softmax row {r} gave {g}"
        shift = rng.uniform(-50, 50)
        assert mat_near(mod.softmax_rows([[v + shift for v in r] for r in S]), got, 1e-9), \
            f"seed {sd}: adding a constant to every score must not change the weights"
        X = [[rng.gauss(rng.uniform(-5, 5), rng.uniform(0.2, 4)) for _ in range(cols)] for _ in range(rows)]
        g, b = [rng.uniform(0.5, 2) for _ in range(cols)], [rng.uniform(-1, 1) for _ in range(cols)]
        Y = mod.layernorm_rows(X, g, b)
        assert mat_near(Y, o_ln(X, g, b), 1e-9), f"seed {sd}: layernorm differs from the reference"
        Z = mod.layernorm_rows(X, [1.0] * cols, [0.0] * cols)
        for z in Z:
            mu = sum(z) / cols
            var = sum((v - mu) ** 2 for v in z) / cols
            assert abs(mu) < 1e-9 and abs(var - 1) < 1e-3, f"seed {sd}: each normalised row should have mean 0 and variance 1; got {mu:.2g} and {var:.4f}"
        assert mat_near(mod.layernorm_rows([[v * 7 + 3 for v in r] for r in X], [1.0] * cols, [0.0] * cols), \
                        mod.layernorm_rows(X, [1.0] * cols, [0.0] * cols), 1e-3), "scaling and shifting a row must not change its normalised value"
    for z in (-3, -1, -0.5, 0, 0.5, 1, 3):
        assert near(mod.gelu(float(z)), o_gelu(z), 1e-12), f"gelu({z}) should be {o_gelu(z):.6f}"
    assert near(mod.gelu(1.0), 0.8411919906, 1e-6) and near(mod.gelu(-1.0), -0.1588080094, 1e-6) and mod.gelu(0.0) == 0.0
    return "softmax (stable, -inf aware), layer norm (mean 0, variance 1 per row) and GELU agree with hand values and 10 random cases"


# =============================================================================
# Milestone 2: scaled dot-product attention
# =============================================================================
def m2():
    m = mod.causal_mask(3)
    assert [[bool(v) for v in r] for r in m] == [[False, True, True], [False, False, True], [False, False, False]], \
        f"causal_mask(3) should hide exactly the entries above the diagonal; got {m}"
    assert mod.causal_mask(1) == [[False]] or [[bool(v) for v in r] for r in mod.causal_mask(1)] == [[False]]

    # the worked example of chapter 09: three tokens, C = 4, d_k = 2
    x = [[1., 0., 1., 0.], [0., 1., 0., 1.], [1., 1., 0., 0.]]
    Wq = [[1, 0], [0, 1], [0, 0], [0, 0]]
    Wk = [[1, 0], [0, 1], [1, 0], [0, 1]]
    Wv = [[1, 0], [0, 1], [1, 0], [0, 0]]
    Q, K, V = (o_matmul(x, W) for W in (Wq, Wk, Wv))
    out, w = mod.attention(Q, K, V)
    want_w = [[0.58, 0.14, 0.28], [0.14, 0.58, 0.28], [1 / 3, 1 / 3, 1 / 3]]
    assert all(abs(a - b) < 0.005 for ra, rb in zip(w, want_w) for a, b in zip(ra, rb)), \
        f"unmasked weights on the chapter 09 example should be {want_w}; got {[[round(v, 2) for v in r] for r in w]}. Did you divide by sqrt(d_k)?"
    want_o = [[1.44, 0.42], [0.56, 0.86], [1.0, 0.67]]
    assert all(abs(a - b) < 0.005 for ra, rb in zip(out, want_o) for a, b in zip(ra, rb)), \
        f"unmasked output should be {want_o}; got {[[round(v, 2) for v in r] for r in out]}"
    outc, wc = mod.attention(Q, K, V, mod.causal_mask(3))
    want_wc = [[1.0, 0.0, 0.0], [0.2, 0.8, 0.0], [1 / 3, 1 / 3, 1 / 3]]
    assert all(abs(a - b) < 0.005 for ra, rb in zip(wc, want_wc) for a, b in zip(ra, rb)), \
        f"causal weights should be {[[round(v, 2) for v in r] for r in want_wc]}; got {[[round(v, 2) for v in r] for r in wc]}. " \
        "Mask the SCORES with -inf before the softmax; zeroing weights afterwards leaves rows that do not sum to 1"
    want_oc = [[2.0, 0.0], [0.39, 0.8], [1.0, 0.67]]
    assert all(abs(a - b) < 0.005 for ra, rb in zip(outc, want_oc) for a, b in zip(ra, rb)), \
        f"causal output should be {want_oc}; got {[[round(v, 2) for v in r] for r in outc]}"
    assert len(out) == 3 and len(out[0]) == 2 and len(w) == 3 and len(w[0]) == 3, "output is (T, d_v) and weights are (T, T)"

    for sd in seeds(range(1, 13)):
        rng = random.Random(sd)
        T, d_k, d_v = rng.randint(1, 7), rng.choice([1, 2, 4, 8, 16]), rng.randint(1, 5)
        Q, K, V = rand_matrix(rng, T, d_k), rand_matrix(rng, T, d_k), rand_matrix(rng, T, d_v)
        before = copy.deepcopy((Q, K, V))
        for causal in (False, True):
            out, w = mod.attention(Q, K, V, mod.causal_mask(T) if causal else None)
            wo, ww = o_attention(Q, K, V, causal)
            assert mat_near(w, ww, 1e-9), f"seed {sd} causal={causal}: attention weights differ from the reference (T={T}, d_k={d_k})"
            assert mat_near(out, wo, 1e-9), f"seed {sd} causal={causal}: attention output differs from the reference"
            assert all(near(sum(r), 1.0, 1e-9) for r in w), f"seed {sd}: every row of weights must sum to 1"
        assert (Q, K, V) == before, "attention must not modify its inputs"
        # a mask the learner did not build: forbid column 0 entirely except for query 0 (and keep one key per row)
        if T >= 2:
            mask = [[(j == 0 and i > 0) for j in range(T)] for i in range(T)]
            _, wm = mod.attention(Q, K, V, mask)
            assert all(wm[i][0] == 0.0 for i in range(1, T)), f"seed {sd}: a custom mask must be respected"
    # why divide by sqrt(d_k): scores of random unit vectors have standard deviation sqrt(d_k) before scaling
    rng = random.Random(0)
    d_k, T, trials = 64, 40, 20
    raw, scaled = [], []
    for _ in range(trials):
        Q, K = rand_matrix(rng, T, d_k), rand_matrix(rng, T, d_k)
        _, w = mod.attention(Q, K, Q)
        scaled.append(sum(max(r) for r in w) / T)
        raw_w = [o_softmax([sum(a * b for a, b in zip(q, k)) for k in K]) for q in Q]
        raw.append(sum(max(r) for r in raw_w) / T)
    a, b = sum(scaled) / trials, sum(raw) / trials
    assert a < 0.5 and b > 0.8, (f"with d_k = 64 and random vectors, the average largest weight should be small when scaled "
                                 f"(about 0.3) and near 1 when not; yours is {a:.2f}. Are you dividing by sqrt(d_k)?")
    return (f"matches chapter 09's worked example and the reference on 12 random cases (both masked and unmasked)\n"
            f"d_k = 64, 40 random keys: largest weight averages {a:.2f} with the scaling, {b:.2f} without it")


# =============================================================================
# Milestone 3: multi-head attention
# =============================================================================
def m3():
    x = [[1, 2, 3, 4, 5, 6], [7, 8, 9, 10, 11, 12]]
    heads = mod.split_heads(x, 3)
    assert heads == [[[1, 2], [7, 8]], [[3, 4], [9, 10]], [[5, 6], [11, 12]]], \
        f"split_heads((2, 6), 3) should give 3 matrices of shape (2, 2): head i takes columns 2i and 2i+1; got {heads}"
    assert mod.merge_heads(heads) == x, "merge_heads must undo split_heads"
    try:
        mod.split_heads([[1, 2, 3, 4, 5]], 2)
    except ValueError:
        pass
    else:
        raise AssertionError("split_heads must raise ValueError when the width is not divisible by the number of heads")

    for sd in seeds(range(1, 9)):
        rng = random.Random(sd)
        h = rng.choice([1, 2, 4])
        d_k = rng.choice([1, 2, 4])
        C, T = h * d_k, rng.randint(1, 6)
        x = rand_matrix(rng, T, C)
        Ws = [rand_matrix(rng, C, C, 1 / math.sqrt(C)) for _ in range(4)]
        before = copy.deepcopy((x, Ws))
        for causal in (True, False):
            out, w = mod.multi_head_attention(x, *Ws, h, causal)
            assert (len(out), len(out[0])) == (T, C), f"seed {sd}: output must be (T, C) = ({T}, {C}); got {(len(out), len(out[0]) if out else 0)}"
            assert len(w) == h and all((len(m), len(m[0])) == (T, T) for m in w), f"seed {sd}: weights must be h = {h} matrices of shape (T, T)"
            assert mat_near(out, o_mha(x, *Ws, h, causal), 1e-9), f"seed {sd} causal={causal}: output differs from the reference (h={h}, T={T}, C={C})"
            if causal:
                assert all(w[k][i][j] == 0.0 for k in range(h) for i in range(T) for j in range(i + 1, T)), f"seed {sd}: a head reads the future"
        assert (x, Ws) == before, "multi_head_attention must not modify its inputs"
        # one head is plain attention with projections around it
        if h == 1:
            Q, K, V = (o_matmul(x, W) for W in Ws[:3])
            o1, _ = mod.attention(Q, K, V, mod.causal_mask(T))
            assert mat_near(mod.multi_head_attention(x, *Ws, 1)[0], o_matmul(o1, Ws[3]), 1e-9), "with h = 1 this is attention followed by Wo"
        # causality: change the last token, earlier outputs must not move
        if T >= 2:
            x2 = copy.deepcopy(x)
            x2[-1] = [v + 1.0 for v in x2[-1]]
            d = max_diff(mod.multi_head_attention(x, *Ws, h)[0][:-1], mod.multi_head_attention(x2, *Ws, h)[0][:-1])
            assert d == 0.0, f"seed {sd}: editing the last token changed an earlier output by {d:.3g}: information leaks backwards"
        # without a mask and without positions, shuffling the tokens just shuffles the outputs
        perm = list(range(T)); rng.shuffle(perm)
        a = mod.multi_head_attention(x, *Ws, h, False)[0]
        b = mod.multi_head_attention([x[i] for i in perm], *Ws, h, False)[0]
        assert mat_near([a[i] for i in perm], b, 1e-9), f"seed {sd}: unmasked attention should be permutation-equivariant"
    # heads really are independent subspaces: zeroing one head's columns in Wq,Wk,Wv,Wo changes only that head's contribution
    rng = random.Random(5)
    C, h, T = 8, 4, 5
    x = rand_matrix(rng, T, C)
    Ws = [rand_matrix(rng, C, C, 0.5) for _ in range(4)]
    full = mod.multi_head_attention(x, *Ws, h)[0]
    cut = copy.deepcopy(Ws)
    for W in cut[:3]:
        for r in W:
            r[2] = r[3] = 0.0                              # head 1 owns columns 2 and 3
    for c in (2, 3):
        cut[3][c] = [0.0] * C                              # and rows 2, 3 of Wo
    ref = o_mha(x, *cut, h, True)
    assert mat_near(mod.multi_head_attention(x, *cut, h)[0], ref, 1e-9), "removing a head should match the reference with that head removed"
    return ("split/merge round-trip; output shape (T, C) and h weight maps (T, T); matches an independent per-head reference\n"
            "on 8 random configurations; causal (editing the last token moves no earlier output); permutation-equivariant without a mask")


# =============================================================================
# Milestone 4: the MLP and the Transformer block
# =============================================================================
def m4():
    # MLP by hand: C = 1, hidden width 2. x = 1; hidden = gelu(1*[1, -1] + [0, 0]) = [gelu(1), gelu(-1)]
    out = mod.mlp([[1.0]], [[1.0, -1.0]], [0.0, 0.0], [[2.0], [3.0]], [0.5])
    want = 2 * o_gelu(1.0) + 3 * o_gelu(-1.0) + 0.5
    assert mat_near(out, [[want]], 1e-12), f"mlp([[1]], ...) should be {want:.6f}; got {out}"
    rng = random.Random(4)
    C, T = 4, 3
    x = rand_matrix(rng, T, C)
    p = mod.init_block(C, rng)
    p["b1"] = [rng.uniform(-1, 1) for _ in range(4 * C)]
    p["b2"] = [rng.uniform(-1, 1) for _ in range(C)]
    o = mod.mlp(x, p["W1"], p["b1"], p["W2"], p["b2"])
    assert (len(o), len(o[0])) == (T, C), "mlp maps (T, C) to (T, C)"
    hid = [[o_gelu(v + p["b1"][j]) for j, v in enumerate(r)] for r in o_matmul(x, p["W1"])]
    assert mat_near(o, [[v + p["b2"][j] for j, v in enumerate(r)] for r in o_matmul(hid, p["W2"])], 1e-9), "mlp differs from gelu(x W1 + b1) W2 + b2"
    # position-wise: each row is processed on its own
    for t in range(T):
        assert mat_near(mod.mlp([x[t]], p["W1"], p["b1"], p["W2"], p["b2"]), [o[t]], 1e-12), "the MLP must treat every position independently"

    # residual wiring: zero the output matrices and the block is the identity
    z = copy.deepcopy(p)
    z["Wo"] = [[0.0] * C for _ in range(C)]
    z["W2"] = [[0.0] * C for _ in range(4 * C)]
    z["b2"] = [0.0] * C
    assert mat_near(mod.block(x, z, 2), x, 1e-12), "with Wo = 0 and W2 = b2 = 0 both sublayers add nothing: the block must return x unchanged (residual connections)"
    # only the attention branch dead: x + MLP(LN2(x)), which shows LN2 sits BEFORE the MLP and reads the stream
    only_mlp = copy.deepcopy(p)
    only_mlp["Wo"] = [[0.0] * C for _ in range(C)]
    want = o_block(x, only_mlp, 2)
    assert mat_near(mod.block(x, only_mlp, 2), want, 1e-9), "with attention switched off the block should be x + MLP(LN2(x))"
    # pre-norm: the stream itself is never normalised, so large inputs stay large
    big = [[100.0 * v for v in r] for r in x]
    out_big = mod.block(big, z, 2)
    assert mat_near(out_big, big, 1e-9), "pre-norm: normalise only the copy that enters a sublayer, never the stream"

    for sd in seeds(range(1, 7)):
        rng = random.Random(sd)
        h, d_k = rng.choice([1, 2, 4]), rng.choice([2, 4])
        C, T = h * d_k, rng.randint(2, 6)
        p = mod.init_block(C, rng)
        for k in ("ln1_g", "ln2_g"):
            p[k] = [rng.uniform(0.5, 1.5) for _ in range(C)]
        for k in ("ln1_b", "ln2_b", "b1", "b2"):
            p[k] = [rng.uniform(-0.5, 0.5) for _ in range(len(p[k]))]
        x = rand_matrix(rng, T, C)
        before = copy.deepcopy((x, p))
        got = mod.block(x, p, h)
        assert (len(got), len(got[0])) == (T, C), f"seed {sd}: a block keeps the shape (T, C) = ({T}, {C})"
        assert mat_near(got, o_block(x, p, h), 1e-9), f"seed {sd}: block output differs from the reference (h={h}, C={C}, T={T}); max difference {max_diff(got, o_block(x, p, h)):.3g}"
        assert mat_near(mod.block(x, p, h, causal=False), o_block(x, p, h, False), 1e-9), f"seed {sd}: block(..., causal=False) differs from the reference"
        assert (x, p) == before, "block must not modify its inputs"
        x2 = copy.deepcopy(x)
        x2[-1] = [v + rng.gauss(0.0, 1.0) for v in x2[-1]]
        d = max_diff(mod.block(x2, p, h)[:-1], got[:-1])
        assert d == 0.0, f"seed {sd}: stacking sublayers leaked the last token into an earlier position (difference {d:.3g})"
        # a stack of 4 blocks still keeps the shape and the causality
        y = x
        for _ in range(4):
            y = mod.block(y, p, h)
        assert (len(y), len(y[0])) == (T, C)
    return "MLP and block agree with hand values and the reference on 6 random configurations; identity when both output matrices are 0; causal through a stack"


# =============================================================================
# Milestone 5: a whole tiny GPT, shape by shape
# =============================================================================
def m5():
    for C in (4, 8, 16, 64):
        p = mod.init_block(C, random.Random(0))
        assert mod.count_params(p) == 12 * C * C + 9 * C, "count_params on a block must give 12 C^2 + 9 C"
        assert mod.block_param_count(C) == 12 * C * C + 9 * C, f"block_param_count({C}) should be 12 C^2 + 9 C = {12 * C * C + 9 * C}; got {mod.block_param_count(C)}"
    assert mod.count_params([[1.0, 2.0], [3.0]]) == 3 and mod.count_params({"a": [1, 2], "b": {"c": [[3]]}}) == 3
    for (V, C, Tm, L, h) in [(10, 8, 6, 1, 2), (27, 16, 8, 2, 4), (5, 4, 3, 3, 1)]:
        P = mod.init_model(V, C, Tm, L, seed=1)
        n = mod.count_params(P)
        assert n == mod.model_param_count(V, C, Tm, L), (f"V={V} C={C} T_max={Tm} L={L}: the model holds {n} numbers, "
                                                         f"model_param_count says {mod.model_param_count(V, C, Tm, L)}")
    # the forward pass, with a trace of shapes
    V, C, Tm, L, h = 27, 16, 8, 2, 4
    P = mod.init_model(V, C, Tm, L, seed=3)
    ids = [3, 1, 4, 1, 5, 9, 2, 6]
    trace = []
    logits = mod.model_forward(ids, P, h, trace)
    T = len(ids)
    want = [("tok_emb", (T, C)), ("x0", (T, C)), ("block0", (T, C)), ("block1", (T, C)), ("ln_f", (T, C)), ("logits", (T, V))]
    assert [tuple(t) for t in trace] == want, f"the shape trace should be {want}; got {trace}"
    assert (len(logits), len(logits[0])) == (T, V)
    # causality of the whole model
    ids2 = ids[:-1] + [(ids[-1] + 5) % V]
    other = mod.model_forward(ids2, P, h)
    assert max_diff(other[:-1], logits[:-1]) == 0.0, "changing the last token changed logits at earlier positions: the model leaks the future"
    assert max_diff(other[-1:], logits[-1:]) > 0.0, "changing the last token must change the last row of logits"
    # a shorter sequence is the prefix of a longer one
    assert mat_near(mod.model_forward(ids[:5], P, h), logits[:5], 1e-12), "the first 5 rows of the logits must not depend on the 3 tokens after them"
    # positions matter: the same token at two positions must not give identical logits unless the position tables are equal
    same = mod.model_forward([7, 7, 7, 7], P, h)
    assert max_diff([same[0]], [same[3]]) > 0.0, "the same token at different positions should get different logits (position embeddings)"
    try:
        mod.model_forward(list(range(Tm + 1)), P, h)
    except ValueError:
        pass
    else:
        raise AssertionError("a sequence longer than T_max has no position embedding: raise ValueError")
    # cross entropy by hand: uniform logits over V give ln V
    assert near(mod.mean_cross_entropy([[0.0] * 4, [1.0] * 4], [2, 0]), math.log(4), 1e-12), "equal logits give a loss of ln V"
    assert near(mod.mean_cross_entropy([[2.0, 1.0, 0.1]], [0]), 0.4170300162, 1e-8), "logits (2, 1, 0.1), class 0: loss 0.417 (chapter 02)"
    # an untrained model should be about as surprised as chance: ln V
    rng = random.Random(11)
    losses = []
    for _ in range(30):
        seq = [rng.randrange(V) for _ in range(Tm + 1)]
        losses.append(mod.mean_cross_entropy(mod.model_forward(seq[:-1], P, h), seq[1:]))
    mean = sum(losses) / len(losses)
    assert abs(mean - math.log(V)) < 0.05, (f"an untrained model (weights N(0, 0.02)) should score about ln V = {math.log(V):.3f} nats; "
                                             f"yours averages {mean:.3f}")
    return (f"shape trace (T=8): tok_emb {want[0][1]} -> block1 {want[3][1]} -> logits {want[5][1]}; parameter counts match 12C^2+9C per block\n"
            f"untrained loss averages {mean:.3f} nats against ln V = {math.log(V):.3f}; the model is causal")


MILESTONES = [
    (1, "Milestone 1: softmax, layer norm and GELU", m1),
    (2, "Milestone 2: scaled dot-product attention", m2),
    (3, "Milestone 3: multi-head attention", m3),
    (4, "Milestone 4: the MLP and the Transformer block", m4),
    (5, "Milestone 5: a whole tiny GPT, shape by shape", m5),
]

if __name__ == "__main__":
    t0 = time.time()
    print(f"Lab 3 checks against {target}.py\n")
    for n, name, fn in MILESTONES:
        check(n, name, fn)
    print(f"\n{sum(results)}/{len(results)} milestones passing  ({time.time() - t0:.1f} s)")
    sys.exit(0 if all(results) else 1)
