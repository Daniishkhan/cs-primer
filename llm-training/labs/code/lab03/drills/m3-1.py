# Drill: A3 Lab 3, milestone 3 of 6: training loops (step 1 of 3)
# Everything else in this file is already written. Fill in:
#     full_grads
# Check it with: python3 check.py 3

"""Lab 3: LoRA from scratch, on a layer small enough to check by hand.

Chapter 11 said: freeze W0, learn a low-rank correction, and fold it back in afterwards.

    h = W0 x + (alpha / r) * B (A x)         B is d_out x r and starts at ZERO, A is r x d_in
    merged weight  W = W0 + (alpha / r) * B A

This lab does that on one linear layer standing in for a pretrained model. The "pretrained"
weights W0 were fit on task A. Task B asks for a different mapping: W_B = W_A + a rank-2
change + a faint dense change. You adapt W0 to task B two ways, with a LoRA adapter and by
full fine-tuning, and compare trainable parameters, task B loss and how much task A is forgotten.

    count + init + forward --> gradients of A and B --> training loops --> merge
        --> run one experiment --> sweep ranks against full fine-tuning

Standard-library Python only; every random draw comes from a seeded random.Random.

Notation follows chapter 11: W0 frozen (d_out x d_in), A (r x d_in), B (d_out x r),
s = alpha / r the scale, g = dL/dh the gradient at the layer's output.

What is GIVEN: the matrix helpers, Adam, the synthetic tasks and the loss.
What YOU write is marked TODO.

    1  count_full, count_lora, init_adapter, lora_forward
    2  lora_grads, batch_loss_and_grads
    3  full_grads, train_lora, train_full
    4  adapter_delta, merge, unmerge
    5  evaluate, run_lora, run_full
    6  sweep, verdict
"""
import math
import random
from operator import mul

# =============================================================================
# GIVEN: matrix helpers (matrices are lists of rows)
# =============================================================================
D = 24                  # the layer is D x D: 576 weights
TRUE_RANK = 2           # the task-B change is (mostly) rank 2


def matvec(M, x):
    return [sum(map(mul, row, x)) for row in M]


def transpose(M):
    return [list(col) for col in zip(*M)]


def matmul(P, Q):
    Qt = transpose(Q)
    return [[sum(map(mul, row, col)) for col in Qt] for row in P]


def mat_add(P, Q, c=1.0):
    """P + c * Q, as a new matrix."""
    return [[p + c * q for p, q in zip(rp, rq)] for rp, rq in zip(P, Q)]


def zeros(rows, cols):
    return [[0.0] * cols for _ in range(rows)]


def outer(u, v):
    return [[a * b for b in v] for a in u]


def frobenius_sq(M):
    return sum(v * v for row in M for v in row)


def numeric_rank(M, tol=1e-8):
    """Rank by Gaussian elimination with partial pivoting (enough for the lab's checks)."""
    M = [row[:] for row in M]
    rank, rows, cols = 0, len(M), len(M[0])
    scale = max(abs(v) for row in M for v in row) or 1.0
    for c in range(cols):
        piv = max(range(rank, rows), key=lambda i: abs(M[i][c]), default=None)
        if piv is None or abs(M[piv][c]) <= tol * scale:
            continue
        M[rank], M[piv] = M[piv], M[rank]
        for i in range(rank + 1, rows):
            f = M[i][c] / M[rank][c]
            M[i] = [a - f * b for a, b in zip(M[i], M[rank])]
        rank += 1
        if rank == rows:
            break
    return rank


class Adam:
    """Adam over a list of matrices, updated in place. step(grads) takes one gradient matrix per parameter."""

    def __init__(self, params, lr, b1=0.9, b2=0.999, eps=1e-8):
        self.params, self.lr, self.b1, self.b2, self.eps, self.t = params, lr, b1, b2, eps, 0
        self.m = [zeros(len(p), len(p[0])) for p in params]
        self.v = [zeros(len(p), len(p[0])) for p in params]

    def step(self, grads):
        self.t += 1
        c1, c2 = 1 - self.b1 ** self.t, 1 - self.b2 ** self.t
        for P, G, M, V in zip(self.params, grads, self.m, self.v):
            for i, (prow, grow) in enumerate(zip(P, G)):
                mrow, vrow = M[i], V[i]
                for j, g in enumerate(grow):
                    mrow[j] = self.b1 * mrow[j] + (1 - self.b1) * g
                    vrow[j] = self.b2 * vrow[j] + (1 - self.b2) * g * g
                    prow[j] -= self.lr * (mrow[j] / c1) / (math.sqrt(vrow[j] / c2) + self.eps)


# =============================================================================
# GIVEN: the loss, the two tasks and the "pretrained" layer
# =============================================================================
def mse_loss(preds, targets):
    """Mean squared error over samples AND outputs: (1 / (N d_out)) sum_n ||h_n - y_n||^2."""
    n, d = len(preds), len(preds[0])
    return sum((h - y) ** 2 for hs, ys in zip(preds, targets) for h, y in zip(hs, ys)) / (n * d)


def mse_grad_out(h, y, n_samples):
    """g = dL/dh for one sample of the batch loss above: 2 (h - y) / (N d_out)."""
    return [2.0 * (a - b) / (n_samples * len(h)) for a, b in zip(h, y)]


class World:
    """Everything the experiments need, generated from one seed.

    W0        the frozen pretrained layer (fit on task A: it equals W_A up to a tiny fit error)
    task_a    held-out task-A samples (x, y): the loss on these measures FORGETTING
    train_b   task-B training samples (noisy labels), test_b: clean held-out task-B samples
    Task B: W_B = W_A + a rank-2 change (the part worth learning) + a faint dense change.
    """

    def __init__(self, seed=0, n_train=72, n_test=200, n_a=200, noise=0.4, dense=0.04):
        rng = random.Random(seed)
        g = lambda: rng.gauss(0.0, 1.0)
        self.W_A = [[g() / math.sqrt(D) for _ in range(D)] for _ in range(D)]
        self.W0 = [[w + 0.003 * g() for w in row] for row in self.W_A]
        U = [[g() for _ in range(TRUE_RANK)] for _ in range(D)]
        V = [[g() for _ in range(D)] for _ in range(TRUE_RANK)]
        low = matmul(U, V)
        norm = math.sqrt(frobenius_sq(low))
        self.low = [[2.0 * v / norm for v in row] for row in low]                     # rescaled so ||low||_F = 2
        self.faint = [[dense * g() for _ in range(D)] for _ in range(D)]
        self.W_B = mat_add(mat_add(self.W_A, self.low), self.faint)
        self.d_in = self.d_out = D

        def draw(W, n, sigma):
            xs = [[g() for _ in range(D)] for _ in range(n)]
            return [(x, [v + sigma * g() for v in matvec(W, x)]) for x in xs]

        self.task_a = draw(self.W_A, n_a, 0.0)
        self.train_b = draw(self.W_B, n_train, noise)
        self.test_b = draw(self.W_B, n_test, 0.0)


# =============================================================================
# Milestone 1: count, initialise, forward
# =============================================================================
def count_full(d_out, d_in):
    """Trainable parameters when you fine-tune the whole matrix."""
    return d_out * d_in


def count_lora(d_out, d_in, r):
    """Trainable parameters of a rank-r adapter: A is r x d_in, B is d_out x r."""
    return r * (d_in + d_out)


def init_adapter(d_out, d_in, r, rng):
    """(A, B): A is r x d_in with entries N(0, 1/d_in); B is d_out x r and exactly zero."""
    A = [[rng.gauss(0.0, 1.0 / math.sqrt(d_in)) for _ in range(d_in)] for _ in range(r)]
    return A, zeros(d_out, r)


def lora_forward(W0, A, B, x, alpha):
    """h = W0 x + (alpha / r) * B (A x), with r = len(A). Never form B A: go through the r-dimensional bottleneck."""
    s = alpha / len(A)
    base = matvec(W0, x)
    low = matvec(B, matvec(A, x))
    return [b + s * l for b, l in zip(base, low)]


# =============================================================================
# Milestone 2: gradients of A and B
# =============================================================================
def lora_grads(A, B, x, g, alpha):
    """(dA, dB) for ONE sample, given g = dL/dh (length d_out).

        dL/dB = s * g (A x)^T          (d_out x r)
        dL/dA = s * (B^T g) x^T        (r x d_in)
    """
    s = alpha / len(A)
    Ax = matvec(A, x)
    Btg = matvec(transpose(B), g)
    dB = [[s * gi * a for a in Ax] for gi in g]
    dA = [[s * c * xj for xj in x] for c in Btg]
    return dA, dB


def batch_loss_and_grads(W0, A, B, data, alpha):
    """(loss, dA, dB) of the mean squared error over a batch of (x, y) pairs."""
    n = len(data)
    preds = [lora_forward(W0, A, B, x, alpha) for x, _ in data]
    loss = mse_loss(preds, [y for _, y in data])
    dA, dB = zeros(len(A), len(A[0])), zeros(len(B), len(B[0]))
    for (x, y), h in zip(data, preds):
        da, db = lora_grads(A, B, x, mse_grad_out(h, y, n), alpha)
        dA = mat_add(dA, da)
        dB = mat_add(dB, db)
    return loss, dA, dB


# =============================================================================
# Milestone 3: training loops
# =============================================================================
def full_grads(W, data):
    """(loss, dW) for full fine-tuning: dW = sum over samples of g x^T."""
    raise NotImplementedError("TODO milestone 3: full_grads")


def train_lora(W0, data, r, alpha, lr, steps, seed=0):
    """Train a rank-r adapter by full-batch Adam. W0 is never touched. Returns (A, B, losses).

    Make rng = random.Random(seed), then init_adapter(d_out, d_in, r, rng). The trainable
    parameters are the two matrices A and B; hand [A, B] to Adam(...), which updates them in place.
    Each of the `steps` steps: compute the loss and gradients on ALL of `data`, append the loss
    to `losses` (so losses[0] is the loss of the untouched base model, because B = 0), then
    opt.step([dA, dB]).
    """
    rng = random.Random(seed)
    A, B = init_adapter(len(W0), len(W0[0]), r, rng)
    opt = Adam([A, B], lr)
    losses = []
    for _ in range(steps):
        loss, dA, dB = batch_loss_and_grads(W0, A, B, data, alpha)
        losses.append(loss)
        opt.step([dA, dB])
    return A, B, losses


def train_full(W0, data, lr, steps):
    """Fine-tune a COPY of W0 by full-batch Adam. W0 itself must not change. Returns (W, losses).

    Same loop as train_lora, but the parameter is the whole matrix W: losses[k] is the loss
    BEFORE step k, and the gradient comes from full_grads.
    """
    W = [row[:] for row in W0]
    opt = Adam([W], lr)
    losses = []
    for _ in range(steps):
        loss, dW = full_grads(W, data)
        losses.append(loss)
        opt.step([dW])
    return W, losses


# =============================================================================
# Milestone 4: merge
# =============================================================================
def adapter_delta(A, B, alpha):
    """The update the adapter represents: (alpha / r) * B A, a d_out x d_in matrix of rank at most r."""
    return [[(alpha / len(A)) * v for v in row] for row in matmul(B, A)]


def merge(W0, A, B, alpha):
    """A new matrix W0 + (alpha / r) B A. W0 is left alone (return a new list of rows, do not edit W0 in place)."""
    return mat_add(W0, adapter_delta(A, B, alpha))


def unmerge(W, A, B, alpha):
    """Undo merge: W - (alpha / r) B A, as a new matrix."""
    return mat_add(W, adapter_delta(A, B, alpha), -1.0)


# =============================================================================
# Milestone 5: run one experiment
# =============================================================================
def evaluate(W, data):
    """Mean squared error of the plain linear layer W on (x, y) pairs."""
    return mse_loss([matvec(W, x) for x, _ in data], [y for _, y in data])


class Result:
    """One row of the comparison table."""

    def __init__(self, name, params, fraction, train_b, test_b, task_a):
        self.name, self.params, self.fraction = name, params, fraction
        self.train_b, self.test_b, self.task_a = train_b, test_b, task_a


def run_lora(world, r, alpha=16.0, lr=0.02, steps=200, seed=0):
    """Train a rank-r adapter on task B (on world.train_b, starting from world.W0), merge it, and measure the merged layer.

    Returns Result("LoRA r=<r>", params, params / count_full(...), train_b, test_b, task_a) where
    the three losses are evaluate(merged, world.train_b), evaluate(merged, world.test_b) and
    evaluate(merged, world.task_a). The last one is the FORGETTING measure: the base model scores
    about 0.0002 on it, so everything above that is damage to task A.
    """
    A, B, losses = train_lora(world.W0, world.train_b, r, alpha, lr, steps, seed)
    W = merge(world.W0, A, B, alpha)
    params = count_lora(world.d_out, world.d_in, r)
    return Result(f"LoRA r={r}", params, params / count_full(world.d_out, world.d_in),
                  evaluate(W, world.train_b), evaluate(W, world.test_b), evaluate(W, world.task_a))


def run_full(world, lr=0.005, steps=200):
    """Full fine-tuning on task B, measured the same way. Returns Result("full", params, 1.0, ...)."""
    W, losses = train_full(world.W0, world.train_b, lr, steps)
    return Result("full", count_full(world.d_out, world.d_in), 1.0,
                  evaluate(W, world.train_b), evaluate(W, world.test_b), evaluate(W, world.task_a))


# =============================================================================
# Milestone 6: the comparison
# =============================================================================
def sweep(world, ranks, alpha=16.0, lr=0.02, steps=200, full_lr=0.005):
    """[full fine-tuning, LoRA at each rank in `ranks`], as a list of Result. The full row comes first.

    alpha, lr and steps go to run_lora; full_lr and steps go to run_full.
    """
    return [run_full(world, full_lr, steps)] + [run_lora(world, r, alpha, lr, steps) for r in ranks]


def verdict(rows, tolerance=0.10):
    """Summarise a sweep (rows[0] is the full fine-tune, the rest are LoRA ranks in increasing order).

    The target is the best held-out task-B loss of ANY row (full fine-tuning included).
    Returns a dict:
      "smallest_rank"    the integer rank (parse it from the name, "LoRA r=4" -> 4) of the first LoRA row
                         whose test_b is at most best * (1 + tolerance); None if no LoRA row gets there
      "param_fraction"   that row's fraction of trainable parameters (None if no row qualifies)
      "forgetting_saved" 1 - (that row's task_a) / (the full row's task_a)  (None if no row qualifies)
    """
    best = min(row.test_b for row in rows)
    for row in rows[1:]:
        if row.test_b <= best * (1 + tolerance):
            return {"smallest_rank": int(row.name.split("=")[1]), "param_fraction": row.fraction,
                    "forgetting_saved": 1 - row.task_a / rows[0].task_a}
    return {"smallest_rank": None, "param_fraction": None, "forgetting_saved": None}


if __name__ == "__main__":
    w = World()
    for row in sweep(w, [1, 2, 4, 8]):
        print(f"{row.name:10s} params {row.params:5d} ({100 * row.fraction:5.1f}%)  "
              f"train B {row.train_b:.4f}  test B {row.test_b:.4f}  task A {row.task_a:.4f}")
