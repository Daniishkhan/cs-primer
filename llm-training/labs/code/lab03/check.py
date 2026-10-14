"""Self-check for Lab 3: LoRA from Scratch.

    python3 check.py                  # checks your starter.py
    python3 check.py solution         # checks the reference solution
    python3 check.py solution 4       # only milestone 4
    python3 check.py solution 2 3     # milestone 2, replaying ONLY the random cases of seed 3

Everything is seeded: the synthetic tasks, the adapters' starting values and every random test
input. There is no network and no clock, so every run gives identical numbers. The whole check
takes a few seconds. Prints a tick, a cross, or "not implemented yet" for each milestone.
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


def close_mat(P, Q, tol=1e-9):
    return len(P) == len(Q) and all(len(p) == len(q) and all(near(a, b, tol) for a, b in zip(p, q)) for p, q in zip(P, Q))


def shape(M):
    return (len(M), len(M[0]) if M else 0)


def rand_mat(rng, r, c, s=1.0):
    return [[s * rng.gauss(0, 1) for _ in range(c)] for _ in range(r)]


_world_cache = {}


def world(**kw):
    key = tuple(sorted(kw.items()))
    if key not in _world_cache:
        _world_cache[key] = mod.World(**kw)
    return _world_cache[key]


# =============================================================================
# Milestone 1: count, initialise, forward
# =============================================================================
def m1():
    assert mod.count_full(4096, 4096) == 16_777_216, "a 4096 x 4096 matrix has 16,777,216 weights"
    assert mod.count_full(3, 5) == 15
    assert mod.count_lora(4096, 4096, 16) == 131_072, \
        f"rank 16 on a 4096 x 4096 matrix: 16 * (4096 + 4096) = 131,072, got {mod.count_lora(4096, 4096, 16)}"
    assert mod.count_lora(11008, 4096, 16) == 241_664, "A is r x d_in and B is d_out x r: r (d_in + d_out)"
    assert mod.count_lora(24, 24, 2) == 96 and mod.count_lora(24, 24, 12) == 576, "at r = d/2 the adapter is as big as the matrix"

    rng = random.Random(1)
    A, B = mod.init_adapter(7, 11, 3, rng)
    assert shape(A) == (3, 11), f"A must be r x d_in = (3, 11), got {shape(A)}"
    assert shape(B) == (7, 3), f"B must be d_out x r = (7, 3), got {shape(B)}"
    assert all(v == 0.0 for row in B for v in row), "B must start at exactly zero (that is what makes step 0 equal the base model)"
    assert any(v != 0.0 for row in A for v in row), "A must be random, not zero: with B = A = 0 neither would ever get a gradient"
    A2, _ = mod.init_adapter(7, 11, 3, random.Random(1))
    assert A == A2, "same rng seed must give the same A"
    big, _ = mod.init_adapter(5, 400, 20, random.Random(2))
    vals = [v for row in big for v in row]
    sd = math.sqrt(sum(v * v for v in vals) / len(vals))
    assert abs(sd - 1 / math.sqrt(400)) < 0.15 / math.sqrt(400) * 2, \
        f"A's entries should have standard deviation about 1/sqrt(d_in) = {1 / math.sqrt(400):.4f}, got {sd:.4f}"

    # hand-computed forward passes
    W0 = [[1.0, 0.0], [0.0, 1.0]]
    got = mod.lora_forward(W0, [[1.0, 1.0]], [[2.0], [3.0]], [1.0, 2.0], 4.0)
    assert all(near(a, b) for a, b in zip(got, [25.0, 38.0])), \
        f"W0 = I, A = [[1, 1]], B = [[2], [3]], alpha = 4 (r = 1, so scale 4), x = (1, 2): h = x + 4 * B (A x) = (25, 38); got {got}"
    got = mod.lora_forward([[0.0, 0.0]], [[1.0, 0.0], [0.0, 1.0]], [[1.0, 1.0]], [3.0, 5.0], 4.0)
    assert near(got[0], 16.0), f"r = 2 and alpha = 4 give scale 2: h = 2 * (3 + 5) = 16, got {got[0]} (is the scale alpha / r, with r = len(A)?)"

    for s in seeds((1, 2, 3)):
        r = random.Random(s)
        W0 = rand_mat(r, 6, 9)
        x = [r.gauss(0, 1) for _ in range(9)]
        A, B = mod.init_adapter(6, 9, 4, r)
        base = [sum(a * b for a, b in zip(row, x)) for row in W0]
        got = mod.lora_forward(W0, A, B, x, 16.0)
        assert all(near(a, b) for a, b in zip(got, base)), f"seed {s}: at initialisation (B = 0) the adapted layer must equal the base layer"
        B = rand_mat(r, 6, 4)
        got = mod.lora_forward(W0, A, B, x, 8.0)
        BA = [[sum(B[i][k] * A[k][j] for k in range(4)) for j in range(9)] for i in range(6)]
        want = [sum((W0[i][j] + 2.0 * BA[i][j]) * x[j] for j in range(9)) for i in range(6)]
        assert all(near(a, b, 1e-9) for a, b in zip(got, want)), f"seed {s}: lora_forward differs from (W0 + (alpha / r) B A) x"
        assert len(got) == 6
    return "counts for 4096 x 4096 at r = 16: 131,072 trainable (0.78% of 16.8M); B starts at 0, so the adapted layer equals the base layer"


# =============================================================================
# Milestone 2: gradients of A and B
# =============================================================================
def num_grad(f, M, i, j, eps=1e-6):
    old = M[i][j]
    M[i][j] = old + eps
    hi = f()
    M[i][j] = old - eps
    lo = f()
    M[i][j] = old
    return (hi - lo) / (2 * eps)


def m2():
    dA, dB = mod.lora_grads([[1.0, 2.0]], [[3.0], [4.0]], [1.0, 1.0], [1.0, -1.0], 2.0)
    assert close_mat(dB, [[6.0], [-6.0]]), \
        f"A = [[1, 2]], B = [[3], [4]], x = (1, 1), g = (1, -1), alpha = 2: dB = s g (A x)^T = [[6], [-6]], got {dB}"
    assert close_mat(dA, [[-2.0, -2.0]]), f"dA = s (B^T g) x^T = 2 * (-1) * (1, 1) = [[-2, -2]], got {dA}"

    A, B = mod.init_adapter(5, 8, 3, random.Random(0))
    dA, dB = mod.lora_grads(A, B, [0.5] * 8, [1.0, -2.0, 0.5, 0.0, 3.0], 12.0)
    assert shape(dA) == (3, 8) and shape(dB) == (5, 3), f"dA is r x d_in and dB is d_out x r; got {shape(dA)} and {shape(dB)}"
    assert all(v == 0.0 for row in dA for v in row), \
        "at B = 0 the gradient of A is exactly zero (it is multiplied by B^T g): only B moves on the first step"
    assert any(abs(v) > 1e-6 for row in dB for v in row), "but the gradient of B is not zero, because A is random"

    note = ""
    for s in seeds((1, 2, 3)):
        rng = random.Random(s)
        d_out, d_in, r, alpha = 5, 7, 3, 6.0
        W0 = rand_mat(rng, d_out, d_in)
        A = rand_mat(rng, r, d_in, 0.5)
        B = rand_mat(rng, d_out, r, 0.5)
        data = [([rng.gauss(0, 1) for _ in range(d_in)], [rng.gauss(0, 1) for _ in range(d_out)]) for _ in range(6)]
        W0_copy = [row[:] for row in W0]
        loss, dA, dB = mod.batch_loss_and_grads(W0, A, B, data, alpha)
        assert W0 == W0_copy, "batch_loss_and_grads must not modify W0"
        want = sum((h - y) ** 2 for x, y in data for h, y in zip(mod.lora_forward(W0, A, B, x, alpha), y)) / (len(data) * d_out)
        assert near(loss, want), f"seed {s}: loss should be the mean squared error over samples and outputs: expected {want:.6f}, got {loss:.6f}"
        f = lambda: mod.mse_loss([mod.lora_forward(W0, A, B, x, alpha) for x, _ in data], [y for _, y in data])
        worst = 0.0
        for M, G, name in ((A, dA, "dA"), (B, dB, "dB")):
            assert shape(G) == shape(M), f"seed {s}: {name} has shape {shape(G)}, expected {shape(M)}"
            for i in range(len(M)):
                for j in range(len(M[0])):
                    num = num_grad(f, M, i, j)
                    err = abs(num - G[i][j]) / max(1e-6, abs(num), abs(G[i][j]))
                    worst = max(worst, err)
                    assert err < 1e-5, (f"seed {s}: {name}[{i}][{j}] = {G[i][j]:.6g} but a finite difference of the loss gives {num:.6g}. "
                                        "Check the scale alpha / r, and that you SUM the per-sample gradients over the batch "
                                        "(mse_grad_out already includes the 1 / N)")
        note = f"finite-difference check of every entry of dA and dB (worst relative error {worst:.1e})"
    return note + "; at B = 0 the gradient of A is exactly 0"


# =============================================================================
# Milestone 3: training loops
# =============================================================================
def m3():
    rng = random.Random(5)
    W = rand_mat(rng, 4, 6)
    data = [([rng.gauss(0, 1) for _ in range(6)], [rng.gauss(0, 1) for _ in range(4)]) for _ in range(5)]
    loss, dW = mod.full_grads(W, data)
    want = mod.mse_loss([mod.matvec(W, x) for x, _ in data], [y for _, y in data])
    assert near(loss, want), f"full_grads loss: expected {want:.6f}, got {loss:.6f}"
    f = lambda: mod.mse_loss([mod.matvec(W, x) for x, _ in data], [y for _, y in data])
    for i in range(4):
        for j in range(6):
            num = num_grad(f, W, i, j)
            assert abs(num - dW[i][j]) < 1e-6 * max(1.0, abs(num)), \
                f"dW[{i}][{j}] = {dW[i][j]:.6g} but a finite difference gives {num:.6g} (dW = sum over samples of g x^T)"

    # a noiseless rank-1 target from a zero base: r = 1 can fit it, and W0 must stay untouched
    rng = random.Random(7)
    u, v = [rng.gauss(0, 1) for _ in range(4)], [rng.gauss(0, 1) for _ in range(4)]
    target = [[a * b for b in v] for a in u]
    xs = [[rng.gauss(0, 1) for _ in range(4)] for _ in range(24)]
    data = [(x, mod.matvec(target, x)) for x in xs]
    W0 = mod.zeros(4, 4)
    A, B, losses = mod.train_lora(W0, data, 1, 1.0, 0.05, 400, seed=0)
    assert W0 == mod.zeros(4, 4), "train_lora must not change W0"
    assert len(losses) == 400, f"losses should hold one value per step (400), got {len(losses)}"
    base_loss = mod.mse_loss([mod.matvec(W0, x) for x, _ in data], [y for _, y in data])
    assert near(losses[0], base_loss), f"losses[0] must be the loss of the untouched base model ({base_loss:.5f}); got {losses[0]:.5f}. Is B initialised to zero?"
    assert losses[-1] < 1e-3 * losses[0], f"a rank-1 adapter should fit a rank-1 target almost exactly: loss {losses[0]:.4f} -> {losses[-1]:.5f}"
    assert any(v != 0.0 for row in B for v in row), "B is still all zeros after training: nothing was learned"
    A_again, B_again, losses_again = mod.train_lora(W0, data, 1, 1.0, 0.05, 400, seed=0)
    assert A == A_again and losses == losses_again, "same seed must give identical training"

    # rank-2 target: r = 1 is capacity-limited, r = 2 is not
    u2, v2 = [rng.gauss(0, 1) for _ in range(4)], [rng.gauss(0, 1) for _ in range(4)]
    target2 = [[target[i][j] + u2[i] * v2[j] for j in range(4)] for i in range(4)]
    data2 = [(x, mod.matvec(target2, x)) for x in xs]
    _, _, l1 = mod.train_lora(W0, data2, 1, 2.0, 0.05, 500)
    _, _, l2 = mod.train_lora(W0, data2, 2, 2.0, 0.05, 500)
    assert l2[-1] < 1e-3 * l2[0], f"a rank-2 adapter should fit a rank-2 target: loss {l2[0]:.4f} -> {l2[-1]:.5f}"
    assert l1[-1] > 20 * l2[-1] and l1[-1] > 0.01 * l1[0], f"a rank-1 adapter cannot fit a rank-2 target: expected its loss to plateau well above rank 2's ({l2[-1]:.5f}), got {l1[-1]:.5f}"

    W0 = rand_mat(random.Random(8), 4, 4)
    W0_copy = [row[:] for row in W0]
    Wf, lf = mod.train_full(W0, data, 0.05, 300)
    assert W0 == W0_copy, "train_full must work on a COPY: W0 was modified"
    assert len(lf) == 300 and lf[-1] < 1e-3 * lf[0], f"full fine-tuning should drive a noiseless problem to ~0: {lf[0]:.4f} -> {lf[-1]:.5f}"
    assert close_mat(Wf, target, 1e-2), "with 24 noiseless samples of a 4-input problem, full fine-tuning should recover the target matrix"
    return f"rank-1 target: LoRA r=1 loss {losses[0]:.3f} -> {losses[-1]:.1e}; rank-2 target: r=1 stalls at {l1[-1]:.3f}, r=2 reaches {l2[-1]:.1e}"


# =============================================================================
# Milestone 4: merge
# =============================================================================
def m4():
    A, B = [[1.0, 0.0, 2.0]], [[1.0], [2.0]]
    d = mod.adapter_delta(A, B, 3.0)
    assert close_mat(d, [[3.0, 0.0, 6.0], [6.0, 0.0, 12.0]]), f"alpha = 3, r = 1: delta = 3 * B A = [[3, 0, 6], [6, 0, 12]], got {d}"
    d2 = mod.adapter_delta([[1.0, 0.0, 2.0], [0.0, 1.0, 0.0]], [[1.0, 1.0], [2.0, 0.0]], 4.0)
    assert close_mat(d2, [[2.0, 2.0, 4.0], [4.0, 0.0, 8.0]]), f"r = 2, alpha = 4: scale 2; got {d2}"
    assert close_mat(mod.merge([[1.0, 1.0, 1.0], [1.0, 1.0, 1.0]], A, B, 3.0), [[4.0, 1.0, 7.0], [7.0, 1.0, 13.0]])

    for s in seeds((1, 2, 3)):
        rng = random.Random(s)
        d_out, d_in, r, alpha = 9, 12, 3, 6.0
        W0 = rand_mat(rng, d_out, d_in)
        W0_copy = [row[:] for row in W0]
        A = rand_mat(rng, r, d_in)
        B = rand_mat(rng, d_out, r)
        W = mod.merge(W0, A, B, alpha)
        assert W0 == W0_copy, f"seed {s}: merge changed W0 in place; build a new matrix"
        assert W is not W0 and W[0] is not W0[0]
        for _ in range(5):
            x = [rng.gauss(0, 1) for _ in range(d_in)]
            a, b = mod.lora_forward(W0, A, B, x, alpha), mod.matvec(W, x)
            assert all(near(p, q, 1e-9) for p, q in zip(a, b)), f"seed {s}: the merged layer must give the same output as W0 x + (alpha / r) B (A x)"
        delta = mod.adapter_delta(A, B, alpha)
        rk = mod.numeric_rank(delta)
        assert rk == r, f"seed {s}: B A is a {d_out} x {d_in} matrix but its rank is at most r = {r}; numeric_rank says {rk}"
        assert mod.numeric_rank(W0) == min(d_out, d_in) and mod.numeric_rank(W) == min(d_out, d_in)
        assert close_mat(mod.unmerge(W, A, B, alpha), W0, 1e-9), f"seed {s}: unmerge(merge(W0)) should give W0 back"
        assert close_mat(mod.adapter_delta(A, B, 2 * alpha), [[2 * v for v in row] for row in delta]), "the delta is linear in alpha"
    A, B = mod.init_adapter(5, 7, 2, random.Random(0))
    W0 = rand_mat(random.Random(3), 5, 7)
    assert close_mat(mod.merge(W0, A, B, 16.0), W0, 0), "an untrained adapter (B = 0) merges to the base weights exactly"

    w = world()
    A, B, _ = mod.train_lora(w.W0, w.train_b, 2, 16.0, 0.02, 60)
    W = mod.merge(w.W0, A, B, 16.0)
    fwd = mod.mse_loss([mod.lora_forward(w.W0, A, B, x, 16.0) for x, _ in w.test_b], [y for _, y in w.test_b])
    merged = mod.mse_loss([mod.matvec(W, x) for x, _ in w.test_b], [y for _, y in w.test_b])
    assert near(fwd, merged, 1e-9), "a trained adapter, merged, must score exactly what the unmerged layer scores"
    rank = mod.numeric_rank(mod.mat_add(W, w.W0, -1.0), 1e-9)
    assert rank == 2, f"after merging a rank-2 adapter, W - W0 must still have rank 2, numeric_rank says {rank}"
    return f"trained r=2 adapter on a {w.d_out} x {w.d_in} layer: merged and unmerged outputs agree to 1e-9; W - W0 has rank {rank}, not {w.d_out}"


# =============================================================================
# Milestone 5: run one experiment
# =============================================================================
def m5():
    got = mod.evaluate([[1.0, 0.0], [0.0, 1.0]], [([1.0, 2.0], [1.0, 0.0])])
    assert near(got, 2.0), f"W = I on one sample: prediction (1, 2), target (1, 0), squared errors 0 and 4, mean over 2 outputs = 2.0; got {got}"
    w = world()
    untouched_b, untouched_a = mod.evaluate(w.W0, w.test_b), mod.evaluate(w.W0, w.task_a)
    assert untouched_a < 1e-3, f"the pretrained layer should be near-perfect on task A, but evaluate gives {untouched_a:.5f}"
    assert untouched_b > 0.15, f"the pretrained layer should be poor at task B, but evaluate gives {untouched_b:.4f}"

    r2 = mod.run_lora(w, 2)
    assert r2.name == "LoRA r=2", f"Result.name must read 'LoRA r=2', got {r2.name!r}"
    assert r2.params == 96 and near(r2.fraction, 96 / 576), f"r = 2 on 24 x 24: 96 params, fraction {96 / 576:.4f}; got {r2.params}, {r2.fraction}"
    assert r2.test_b < 0.5 * untouched_b, f"LoRA r=2 should more than halve the held-out task-B loss ({untouched_b:.3f}); got {r2.test_b:.3f}"
    assert r2.train_b > r2.test_b * 0.9 and r2.train_b < untouched_b, "train_b is measured on the NOISY training labels, so it sits above the clean test loss"
    assert r2.task_a > 10 * untouched_a, f"learning task B must cost something on task A (base {untouched_a:.5f}); got {r2.task_a:.5f}"
    full = mod.run_full(w)
    assert full.name == "full" and full.params == 576 and full.fraction == 1.0, f"full row: name 'full', 576 params, fraction 1.0; got {full.name}, {full.params}, {full.fraction}"
    assert full.test_b < 0.6 * untouched_b and full.train_b < r2.train_b, \
        f"full fine-tuning should fit the training data better than rank 2 (train {full.train_b:.3f} vs {r2.train_b:.3f}) and beat the base model on test"
    again = mod.run_lora(w, 2)
    assert (again.train_b, again.test_b, again.task_a) == (r2.train_b, r2.test_b, r2.task_a), "same world and seed must reproduce the same numbers"
    r2b = mod.run_lora(w, 2, seed=5)
    assert r2b.test_b != r2.test_b and abs(r2b.test_b - r2.test_b) < 0.01, "a different adapter seed should change the result a little, not a lot"
    return (f"base layer: task B test {untouched_b:.3f}, task A {untouched_a:.5f}\n"
            f"LoRA r=2  ({r2.params} params): test B {r2.test_b:.4f}, task A {r2.task_a:.4f}\n"
            f"full      ({full.params} params): test B {full.test_b:.4f}, task A {full.task_a:.4f}")


# =============================================================================
# Milestone 6: the comparison
# =============================================================================
def m6():
    R = mod.Result
    rows = [R("full", 576, 1.0, 0.1, 0.10, 0.30), R("LoRA r=1", 48, 48 / 576, 0.3, 0.30, 0.10),
            R("LoRA r=2", 96, 96 / 576, 0.2, 0.108, 0.18), R("LoRA r=4", 192, 192 / 576, 0.15, 0.10, 0.22)]
    v = mod.verdict(rows)
    assert v["smallest_rank"] == 2 and near(v["param_fraction"], 96 / 576) and near(v["forgetting_saved"], 0.4), \
        f"best test_b is 0.10, 10% tolerance allows 0.11: rank 2 (0.108) is the first to qualify; expected rank 2, fraction 0.1667, 40% forgetting saved; got {v}"
    assert mod.verdict(rows, tolerance=0.0)["smallest_rank"] == 4, "with zero tolerance only the row with test_b == best qualifies (here rank 4 ties the full row)"
    rows[3].test_b = rows[2].test_b = 0.3
    assert mod.verdict(rows[:3], 0.1) == {"smallest_rank": None, "param_fraction": None, "forgetting_saved": None}, \
        "when no LoRA row gets within tolerance of the best, every value is None"

    out = []
    for s in seeds((0, 1)):
        w = world(seed=s)
        rows = mod.sweep(w, [1, 2, 4, 8])
        assert [r.name for r in rows] == ["full", "LoRA r=1", "LoRA r=2", "LoRA r=4", "LoRA r=8"], f"seed {s}: sweep must return the full row first, then one row per rank; got {[r.name for r in rows]}"
        full, r1, r2, r4, r8 = rows
        assert r1.test_b > 1.2 * r2.test_b, f"seed {s}: rank 1 cannot express a rank-2 change, so its test loss ({r1.test_b:.4f}) must be clearly above rank 2's ({r2.test_b:.4f})"
        assert r2.test_b < full.test_b, f"seed {s}: with 72 noisy samples full fine-tuning fits the noise; rank 2 should generalise better ({r2.test_b:.4f} vs {full.test_b:.4f})"
        assert r2.train_b > full.train_b, f"seed {s}: full fine-tuning must fit the training set best"
        assert r8.test_b > r2.test_b, f"seed {s}: rank 8 starts fitting noise: its test loss should be above rank 2's"
        assert r2.task_a < full.task_a, f"seed {s}: the adapter should forget less than full fine-tuning (task A {r2.task_a:.4f} vs {full.task_a:.4f})"
        assert r1.task_a < r2.task_a < r4.task_a < r8.task_a, f"seed {s}: forgetting should grow with rank: {[round(r.task_a, 4) for r in rows[1:]]}"
        v = mod.verdict(rows)
        assert v["smallest_rank"] == 2, f"seed {s}: the smallest rank within 10% of the best test loss should be the true rank, 2; got {v['smallest_rank']}"
        assert 0.15 < v["param_fraction"] < 0.18 and 0.2 < v["forgetting_saved"] < 0.5, f"seed {s}: verdict numbers look wrong: {v}"
        if s == 0:
            out.append("n = 72 noisy samples (seed 0):")
            for r in rows:
                out.append(f"  {r.name:9s} {r.params:4d} params ({100 * r.fraction:5.1f}%)  train B {r.train_b:.3f}  test B {r.test_b:.4f}  task A {r.task_a:.4f}")
            out.append(f"  verdict: rank {v['smallest_rank']} gets there with {100 * v['param_fraction']:.1f}% of the parameters and forgets {100 * v['forgetting_saved']:.0f}% less")

    if ONLY_SEED is None:
        w = mod.World(seed=0, n_train=240)
        rows = mod.sweep(w, [2, 8])
        full, r2, r8 = rows
        assert full.test_b < r2.test_b and full.test_b < r8.test_b, "with 240 samples full fine-tuning has enough data to learn the dense part too: it should win on task B"
        assert r8.test_b < r2.test_b, "more rank closes part of the gap"
        v = mod.verdict(rows)
        assert v["smallest_rank"] is None, f"with plenty of data no LoRA rank in [2, 8] gets within 10% of full fine-tuning; verdict says {v}"
        out.append("n = 240 samples: full fine-tuning wins on task B "
                   f"({full.test_b:.4f} vs {r2.test_b:.4f} at r=2, {r8.test_b:.4f} at r=8) but forgets more (task A {full.task_a:.3f} vs {r2.task_a:.3f})")
    return "\n".join(out)


MILESTONES = [
    (1, "Milestone 1: count, initialise, forward", m1),
    (2, "Milestone 2: the gradients of A and B", m2),
    (3, "Milestone 3: training loops", m3),
    (4, "Milestone 4: merge and unmerge", m4),
    (5, "Milestone 5: run one experiment", m5),
    (6, "Milestone 6: LoRA against full fine-tuning", m6),
]

if __name__ == "__main__":
    t0 = time.time()
    print(f"Lab 3 checks against {target}.py\n")
    for n, name, fn in MILESTONES:
        check(n, name, fn)
    print(f"\n{sum(results)}/{len(results)} milestones passing  ({time.time() - t0:.1f} s)")
    sys.exit(0 if all(results) else 1)
