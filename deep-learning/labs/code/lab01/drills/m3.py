# Drill: A2 Lab 1, milestone 3 of 5: parameters and the forward pass
# Everything else in this file is already written. Fill in:
#     init_params, forward
# Check it with: python3 check.py 3

"""Lab 1 reference solution: a two-layer neural network from scratch, standard library only.

Conventions follow Deep Learning chapters 01 and 02: a matrix is a list of rows, a batch X has
shape (B, C_in), a layer computes z = a W + b with W of shape (C_in, C_out), and the gradient of
something always has the shape of that thing.
"""
import math
import random


# ----------------------------------------------------------------------------------------
# Given scaffolding (identical in starter.py)
# ----------------------------------------------------------------------------------------
def shape(A):
    """(rows, cols) of a matrix stored as a list of rows."""
    return (len(A), len(A[0]) if A else 0)


def zeros(rows, cols):
    return [[0.0] * cols for _ in range(rows)]


def apply(f, A):
    """Apply a scalar function to every element, returning a new matrix."""
    return [[f(x) for x in row] for row in A]


def make_moons(n, noise=0.15, seed=0):
    """Two interleaved half-circles. Returns X of shape (n, 2) and labels y (list of 0/1).

    Class 0 is the upper arc, class 1 the lower arc shifted right and down. Not linearly separable.
    """
    rng = random.Random(seed)
    X, y = [], []
    for i in range(n):
        label = i % 2
        t = rng.uniform(0.0, math.pi)
        if label == 0:
            x1, x2 = math.cos(t), math.sin(t)
        else:
            x1, x2 = 1.0 - math.cos(t), 0.5 - math.sin(t)
        X.append([x1 + rng.gauss(0, noise), x2 + rng.gauss(0, noise)])
        y.append(label)
    return X, y


def make_xor(n, noise=0.2, seed=0):
    """Points near (+-1, +-1); the label is 1 when the two signs differ. Not linearly separable."""
    rng = random.Random(seed)
    X, y = [], []
    for _ in range(n):
        a, b = rng.choice([-1.0, 1.0]), rng.choice([-1.0, 1.0])
        X.append([a + rng.gauss(0, noise), b + rng.gauss(0, noise)])
        y.append(1 if a != b else 0)
    return X, y


# ----------------------------------------------------------------------------------------
# Milestone 1: matrix operations
# ----------------------------------------------------------------------------------------
def matmul(A, B):
    """(m, n) @ (n, p) -> (m, p). Raise ValueError if the inner sizes differ."""
    if shape(A)[1] != shape(B)[0]:
        raise ValueError(f"cannot multiply {shape(A)} by {shape(B)}")
    cols = list(zip(*B))                       # columns of B, so each entry is a row . column dot
    return [[sum(a * b for a, b in zip(row, col)) for col in cols] for row in A]


def transpose(A):
    """(m, n) -> (n, m)."""
    return [list(col) for col in zip(*A)]


def add_bias(A, b):
    """Add the vector b (length n) to every row of A (m, n): the broadcast of z = aW + b."""
    if len(b) != shape(A)[1]:
        raise ValueError(f"bias of length {len(b)} does not fit {shape(A)}")
    return [[x + bj for x, bj in zip(row, b)] for row in A]


def col_sums(A):
    """Sum down the rows: (m, n) -> a list of n numbers. The backward pass of add_bias."""
    return [sum(col) for col in zip(*A)]


def hadamard(A, B):
    """Elementwise product of two matrices of the same shape."""
    if shape(A) != shape(B):
        raise ValueError(f"shapes {shape(A)} and {shape(B)} differ")
    return [[a * b for a, b in zip(ra, rb)] for ra, rb in zip(A, B)]


def scale(A, s):
    """Multiply every element by the number s."""
    return [[x * s for x in row] for row in A]


# ----------------------------------------------------------------------------------------
# Milestone 2: activations, softmax and the loss
# ----------------------------------------------------------------------------------------
def relu(Z):
    """max(0, z) elementwise."""
    return apply(lambda z: z if z > 0 else 0.0, Z)


def relu_grad(Z):
    """The slope f'(z) as a matrix of 1.0 and 0.0: 1 where z > 0, else 0."""
    return apply(lambda z: 1.0 if z > 0 else 0.0, Z)


def softmax_rows(Z):
    """Softmax of each row. Subtract the row maximum first so exp never overflows."""
    out = []
    for row in Z:
        m = max(row)
        e = [math.exp(z - m) for z in row]
        s = sum(e)
        out.append([x / s for x in e])
    return out


def cross_entropy(P, y):
    """Mean of -ln P[i][y[i]] over the batch."""
    return -sum(math.log(P[i][label]) for i, label in enumerate(y)) / len(y)


def softmax_ce_grad(P, y):
    """Gradient of the mean cross-entropy with respect to the logits: (P - one_hot(y)) / B."""
    B = len(y)
    G = [row[:] for row in P]
    for i, label in enumerate(y):
        G[i][label] -= 1.0
    return scale(G, 1.0 / B)


# ----------------------------------------------------------------------------------------
# Milestone 3: parameters and the forward pass
# ----------------------------------------------------------------------------------------
def init_params(sizes, seed=0):
    """Initial parameters for a (C_in, H, K) network, as a dict {"W1", "b1", "W2", "b2"}.

    W1 has shape (C_in, H), b1 length H, W2 shape (H, K), b2 length K. Biases start at zero.
    Weights are random with a scale that keeps signals sensible (chapter 03):
        W1 ~ Normal(0, sqrt(2 / C_in))      (He initialisation, for the ReLU layer)
        W2 ~ Normal(0, sqrt(1 / H))
    Use random.Random(seed) and its .gauss(mu, sigma) so the same seed gives the same weights.
    """
    raise NotImplementedError("TODO milestone 3: init_params")


def forward(params, X):
    """Run the network on a batch X (B, C_in). Return (logits, cache).

        z1 = X W1 + b1      (B, H)
        a1 = relu(z1)       (B, H)
        logits = a1 W2 + b2 (B, K)

    cache is a dict holding what the backward pass will need: "X", "z1", "a1" and "logits".
    Do not modify params.
    """
    raise NotImplementedError("TODO milestone 3: forward")


# ----------------------------------------------------------------------------------------
# Milestone 4: backpropagation by hand
# ----------------------------------------------------------------------------------------
def backward(params, cache, y):
    """Gradients of the mean cross-entropy loss: a dict with dW1, db1, dW2, db2."""
    P = softmax_rows(cache["logits"])                           # (B, K) probabilities
    dz2 = softmax_ce_grad(P, y)                                 # (B, K): the first delta
    dW2 = matmul(transpose(cache["a1"]), dz2)                   # (H, K)
    db2 = col_sums(dz2)                                         # (K,)
    da1 = matmul(dz2, transpose(params["W2"]))                  # (B, H)
    dz1 = hadamard(da1, relu_grad(cache["z1"]))                 # (B, H)
    dW1 = matmul(transpose(cache["X"]), dz1)                    # (C_in, H)
    db1 = col_sums(dz1)                                         # (H,)
    return {"dW1": dW1, "db1": db1, "dW2": dW2, "db2": db2}


# ----------------------------------------------------------------------------------------
# Milestone 5: training
# ----------------------------------------------------------------------------------------
def loss_of(params, X, y):
    """Mean cross-entropy of the network on (X, y). Given: built from your own pieces."""
    logits, _ = forward(params, X)
    return cross_entropy(softmax_rows(logits), y)


def sgd_step(params, grads, lr):
    """In place: every parameter moves against its gradient, p <- p - lr * dp."""
    for name in ("W1", "W2"):
        W, dW = params[name], grads["d" + name]
        for i, row in enumerate(W):
            for j in range(len(row)):
                row[j] -= lr * dW[i][j]
    for name in ("b1", "b2"):
        b, db = params[name], grads["d" + name]
        for j in range(len(b)):
            b[j] -= lr * db[j]


def predict(params, X):
    """Predicted class (argmax of the logits) for each row of X."""
    logits, _ = forward(params, X)
    return [max(range(len(row)), key=lambda k: row[k]) for row in logits]


def accuracy(params, X, y):
    """Fraction of rows classified correctly."""
    return sum(p == t for p, t in zip(predict(params, X), y)) / len(y)


def train(params, X, y, lr=0.5, epochs=300):
    """Full-batch gradient descent. Returns the loss before each step (length epochs)."""
    losses = []
    for _ in range(epochs):
        logits, cache = forward(params, X)
        losses.append(cross_entropy(softmax_rows(logits), y))
        grads = backward(params, cache, y)
        sgd_step(params, grads, lr)
    return losses


if __name__ == "__main__":
    X, y = make_moons(200, seed=1)
    Xt, yt = make_moons(200, seed=2)
    params = init_params((2, 16, 2), seed=0)
    losses = train(params, X, y)
    print(f"loss {losses[0]:.3f} -> {losses[-1]:.3f}  train acc {accuracy(params, X, y):.3f}  test acc {accuracy(params, Xt, yt):.3f}")
