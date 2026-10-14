"""Lab 1 starter: a two-layer neural network from scratch, standard library only.

Conventions follow Deep Learning chapters 01 and 02: a matrix is a list of rows, a batch X has
shape (B, C_in), a layer computes z = a W + b with W of shape (C_in, C_out), and the gradient of
something always has the shape of that thing.

Replace every `raise NotImplementedError(...)` with working code, one milestone at a time,
and run `python3 check.py` after each. Nothing else in this file needs to change.
"""
import math
import random


# ----------------------------------------------------------------------------------------
# Given scaffolding: do not change
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
    """(m, n) @ (n, p) -> (m, p). Raise ValueError if the inner sizes differ.

    matmul([[1, 2], [3, 4]], [[5, 6], [7, 8]]) == [[19, 22], [43, 50]]
    Return a new matrix; never modify A or B.
    """
    raise NotImplementedError("TODO milestone 1: matmul")


def transpose(A):
    """(m, n) -> (n, m).  transpose([[1, 2, 3], [4, 5, 6]]) == [[1, 4], [2, 5], [3, 6]]"""
    raise NotImplementedError("TODO milestone 1: transpose")


def add_bias(A, b):
    """Add the vector b (length n) to every row of A (m, n): the broadcast of z = aW + b.

    add_bias([[1, 2], [3, 4]], [10, 20]) == [[11, 22], [13, 24]]
    Raise ValueError if len(b) is not the number of columns.
    """
    raise NotImplementedError("TODO milestone 1: add_bias")


def col_sums(A):
    """Sum down the rows: (m, n) -> a list of n numbers. The backward pass of add_bias.

    col_sums([[1, 2, 3], [4, 5, 6]]) == [5, 7, 9]
    """
    raise NotImplementedError("TODO milestone 1: col_sums")


def hadamard(A, B):
    """Elementwise product of two matrices of the same shape (raise ValueError otherwise).

    hadamard([[1, 2], [3, 4]], [[5, 6], [7, 8]]) == [[5, 12], [21, 32]]
    """
    raise NotImplementedError("TODO milestone 1: hadamard")


def scale(A, s):
    """Multiply every element of A by the number s, returning a new matrix."""
    raise NotImplementedError("TODO milestone 1: scale")


# ----------------------------------------------------------------------------------------
# Milestone 2: activations, softmax and the loss
# ----------------------------------------------------------------------------------------
def relu(Z):
    """max(0, z) elementwise.  relu([[-1.5, 0.0, 2.0]]) == [[0.0, 0.0, 2.0]]"""
    raise NotImplementedError("TODO milestone 2: relu")


def relu_grad(Z):
    """The slope f'(z) as a matrix of 1.0 and 0.0: 1.0 where z > 0, else 0.0 (including z == 0).

    relu_grad([[-1.5, 0.0, 2.0]]) == [[0.0, 0.0, 1.0]]
    """
    raise NotImplementedError("TODO milestone 2: relu_grad")


def softmax_rows(Z):
    """Softmax of each row of the logits Z (B, K): exp(z) / sum(exp(z)).

    softmax_rows([[2.0, 1.0, 0.1]]) is about [[0.659, 0.242, 0.099]].
    Subtract each row's maximum before exponentiating, so large logits cannot overflow:
    softmax_rows([[1000.0, 1001.0]]) must work and give [[0.2689, 0.7311]].
    """
    raise NotImplementedError("TODO milestone 2: softmax_rows")


def cross_entropy(P, y):
    """Mean over the batch of -ln P[i][y[i]], where P holds probabilities (B, K), y the true classes.

    cross_entropy([[0.659, 0.242, 0.099]], [0]) is about 0.417.
    """
    raise NotImplementedError("TODO milestone 2: cross_entropy")


def softmax_ce_grad(P, y):
    """Gradient of the MEAN cross-entropy with respect to the logits: (P - one_hot(y)) / B.

    Shape (B, K), the same as P. For one example with P = [0.659, 0.242, 0.099] and y = 0
    it is [-0.341, 0.242, 0.099]. Do not modify P: copy it first.
    """
    raise NotImplementedError("TODO milestone 2: softmax_ce_grad")


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
    """Gradients of the mean cross-entropy loss with respect to every parameter.

    Return a dict {"dW1", "db1", "dW2", "db2"}, each with the SHAPE of the parameter it names.
    Follow chapter 02, from the loss backwards:
        dz2 = softmax_ce_grad(softmax_rows(logits), y)        (B, K)
        dW2 = a1^T dz2,   db2 = column sums of dz2
        da1 = dz2 W2^T
        dz1 = da1 (elementwise) relu_grad(z1)                 (B, H)
        dW1 = X^T dz1,    db1 = column sums of dz1
    Do not modify params.
    """
    raise NotImplementedError("TODO milestone 4: backward")


# ----------------------------------------------------------------------------------------
# Milestone 5: training
# ----------------------------------------------------------------------------------------
def loss_of(params, X, y):
    """Mean cross-entropy of the network on (X, y). Given: built from your own pieces."""
    logits, _ = forward(params, X)
    return cross_entropy(softmax_rows(logits), y)


def sgd_step(params, grads, lr):
    """In place: move every parameter against its gradient, p <- p - lr * dp.

    W1, W2 are lists of rows; b1, b2 are flat lists. grads has the keys of backward().
    Return nothing.
    """
    raise NotImplementedError("TODO milestone 5: sgd_step")


def predict(params, X):
    """Predicted class (the index of the largest logit) for each row of X, as a list of ints."""
    raise NotImplementedError("TODO milestone 5: predict")


def accuracy(params, X, y):
    """Fraction of rows of X whose predicted class equals the label in y."""
    raise NotImplementedError("TODO milestone 5: accuracy")


def train(params, X, y, lr=0.5, epochs=300):
    """Full-batch gradient descent: every epoch is forward, backward, sgd_step on ALL of X.

    Return a list of `epochs` losses, where entry i is the loss BEFORE the i-th update.
    The parameters in `params` are updated in place.
    """
    raise NotImplementedError("TODO milestone 5: train")


if __name__ == "__main__":
    X, y = make_moons(200, seed=1)
    Xt, yt = make_moons(200, seed=2)
    params = init_params((2, 16, 2), seed=0)
    losses = train(params, X, y)
    print(f"loss {losses[0]:.3f} -> {losses[-1]:.3f}  train acc {accuracy(params, X, y):.3f}  test acc {accuracy(params, Xt, yt):.3f}")
