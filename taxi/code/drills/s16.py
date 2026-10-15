# project.py at step 16 of 20: training in batches
# Everything up to here is written. Fill in: train
# Check it with: python3 check.py 16
"""project.py: the program that grows, one step at a time, from five taxi
rides to a loop that improves a model of their fares.

Each step adds one or two functions marked "# drill": those are yours to
write. Everything else is given. Check a step with

    python3 check.py 7        # step 7 only, against this file
    python3 check.py          # every step so far

The data is rides.csv: 6,367 real New York taxi rides from March 2019,
the seaborn sample of the city's public Taxi and Limousine Commission
records, trimmed to pickup, dropoff, passengers, distance, fare and the
pickup borough. Standard library only.
"""
import csv
import hashlib
import json
import math
import random
from datetime import datetime


# ── Step 1: five rides and a guess ─────────────────────────────────────
# Five real rides: distance in miles, minutes on the road, passengers, fare.
RIDES5 = [
    (1.60, 6.2, 1, 7.0),
    (0.79, 7.1, 1, 5.0),
    (1.37, 7.4, 1, 7.5),
    (7.70, 25.9, 1, 27.0),
    (2.16, 9.5, 3, 9.0),
]


def guess(distance, base, per_mile):  # drill
    """A fare guess for one ride: a flag-drop `base` plus `per_mile` for
    every mile. guess(1.6, 2.5, 2.0) is 5.7."""
    return base + per_mile * distance


def total_error(rides, base, per_mile):  # drill
    """How wrong the guess is over many rides: the sum of |guess - fare|,
    in dollars. rides are (distance, minutes, passengers, fare) tuples.
    total_error(RIDES5, 2.5, 2.0) is 15.76."""
    return sum(abs(guess(d, base, per_mile) - fare) for d, _, _, fare in rides)


# ── Step 2: a ride is a vector ─────────────────────────────────────────
def features(ride):
    """A ride as a list of numbers the model reads: a constant 1 (for the
    flag-drop), distance in miles, minutes on the road."""
    distance, minutes, _, _ = ride
    return [1.0, distance, minutes]


def dot(x, w):  # drill
    """The dot product: multiply entries pairwise and add them up.
    dot([1, 2, 3], [4, 5, 6]) is 32. Different lengths raise ValueError."""
    if len(x) != len(w):
        raise ValueError(f"length mismatch: {len(x)} vs {len(w)}")
    return sum(a * b for a, b in zip(x, w))


def predict(ride, w):  # drill
    """The fare a weight vector predicts for one ride: dot(features, w).
    With w = [2.5, 2.0, 0.0] this is step 1's guess again."""
    return dot(features(ride), w)


# ── Step 3: many rides are a matrix ────────────────────────────────────
def load_rides(path="rides.csv"):
    """Every ride in the file as (distance, minutes, passengers, fare)."""
    rides = []
    with open(path, newline="") as fh:
        for row in csv.DictReader(fh):
            a = datetime.strptime(row["pickup"], "%Y-%m-%d %H:%M:%S")
            b = datetime.strptime(row["dropoff"], "%Y-%m-%d %H:%M:%S")
            minutes = (b - a).total_seconds() / 60
            rides.append((float(row["distance"]), minutes,
                          int(row["passengers"]), float(row["fare"])))
    return rides


def design_matrix(rides):
    """One row of features per ride: a list of lists, shape (n, 3)."""
    return [features(r) for r in rides]


def targets(rides):
    """The true fares, one per ride."""
    return [r[3] for r in rides]


def matvec(X, w):  # drill
    """Predict every ride at once: the matrix-vector product, one dot
    product per row. matvec([[1, 2], [3, 4]], [1, 1]) is [3, 7]."""
    return [dot(row, w) for row in X]


# ── Step 4: a loss ─────────────────────────────────────────────────────
def mse(pred, y):  # drill
    """Mean squared error: average over rides of (prediction - fare)^2.
    mse([1, 2], [1, 4]) is 2.0. Squaring punishes big misses most."""
    if len(pred) != len(y):
        raise ValueError(f"length mismatch: {len(pred)} vs {len(y)}")
    return sum((p - t) ** 2 for p, t in zip(pred, y)) / len(y)


def loss(X, y, w):
    """The loss of weights w on data (X, y): mse of the predictions."""
    return mse(matvec(X, w), y)


# ── Step 5: the loss surface ───────────────────────────────────────────
def sweep(X, y, w, index, values):  # drill
    """Vary one weight and watch the loss: for each value, set w[index]
    to it (leaving the others as they are) and record (value, loss).
    Returns the list of pairs, in the order given."""
    out = []
    for v in values:
        trial = list(w)
        trial[index] = v
        out.append((v, loss(X, y, trial)))
    return out


# ── Step 6: downhill by nudging ────────────────────────────────────────
def numeric_grad(f, w, eps=1e-6):  # drill
    """The slope of f at w in every direction, by nudging: for each
    weight, (f(w + eps there) - f(w - eps there)) / (2 * eps).
    Returns a list the length of w."""
    grad = []
    for i in range(len(w)):
        up, down = list(w), list(w)
        up[i] += eps
        down[i] -= eps
        grad.append((f(up) - f(down)) / (2 * eps))
    return grad


def gd_step(w, grad, lr):  # drill
    """One step downhill: each weight moves against its slope, scaled
    by the learning rate lr. Returns the new list, w unchanged."""
    return [wi - lr * gi for wi, gi in zip(w, grad)]


# ── Step 7: the exact gradient ─────────────────────────────────────────
def grad_mse_linear(X, y, w):  # drill
    """The exact gradient of mse(matvec(X, w), y) with respect to w:
    for weight j, (2/n) * sum over rides of (prediction - fare) * X[i][j].
    Agrees with numeric_grad to many decimal places, and is cheaper."""
    n = len(y)
    pred = matvec(X, w)
    grad = [0.0] * len(w)
    for row, p, t in zip(X, pred, y):
        err = p - t
        for j, xj in enumerate(row):
            grad[j] += 2 * err * xj / n
    return grad


# ── Step 8: a training loop ────────────────────────────────────────────
def train_linear(X, y, w, lr, steps):  # drill
    """Gradient descent: `steps` times, compute the exact gradient at w
    and take a gd_step. Returns (final w, list of the loss before each
    step), so the list has `steps` entries."""
    losses = []
    for _ in range(steps):
        losses.append(loss(X, y, w))
        w = gd_step(w, grad_mse_linear(X, y, w), lr)
    return w, losses


# ── Step 9: features on the same scale ─────────────────────────────────
def standardise(X):  # drill
    """Put every feature column except the first (the constant 1) on the
    same scale: subtract the column's mean, divide by its standard
    deviation (the population one: divide by n, not n - 1). Returns
    (new matrix, means, stds); means[0] is 0 and stds[0] is 1 so the
    constant column is untouched."""
    n, d = len(X), len(X[0])
    means = [0.0] + [sum(row[j] for row in X) / n for j in range(1, d)]
    stds = [1.0] + [math.sqrt(sum((row[j] - means[j]) ** 2 for row in X) / n)
                    for j in range(1, d)]
    Xs = [[(row[j] - means[j]) / stds[j] for j in range(d)] for row in X]
    return Xs, means, stds


# ── Step 10: a number that remembers how it was made ───────────────────
class Value:
    """A scalar that records the operation that produced it and its
    inputs, so a gradient can flow back through it later."""

    def __init__(self, data, parents=(), op=""):
        self.data = float(data)
        self.grad = 0.0
        self.parents = tuple(parents)
        self.op = op

    def __repr__(self):
        return f"Value({self.data:.4g}, grad={self.grad:.4g})"

    def __add__(self, other):  # drill
        """self + other, where other may be a Value or a plain number.
        The result's parents are (self, other) and its op is "+"."""
        other = other if isinstance(other, Value) else Value(other)
        return Value(self.data + other.data, (self, other), "+")

    def __mul__(self, other):  # drill
        """self * other, parents (self, other), op "*"."""
        other = other if isinstance(other, Value) else Value(other)
        return Value(self.data * other.data, (self, other), "*")

    def relu(self):  # drill
        """max(0, self): the bend that lets a network draw curves.
        One parent (self), op "relu"."""
        return Value(self.data if self.data > 0 else 0.0, (self,), "relu")

    # The rest follows from the three above.
    def __neg__(self):
        return self * -1

    def __sub__(self, other):
        return self + (-other)

    def __radd__(self, other):
        return self + other

    def __rmul__(self, other):
        return self * other

    def __rsub__(self, other):
        return Value(other) + (-self)

    def __truediv__(self, other):
        other = other if isinstance(other, Value) else Value(other)
        return self * Value(1.0 / other.data, (other,), "inv")


# ── Step 11: how much each input mattered ──────────────────────────────
def local_grads(v):  # drill
    """For a Value made by an operation, the derivative of v with respect
    to each parent, as a list in parent order:
      "+"    -> [1, 1]
      "*"    -> [other.data, self.data]  (each parent's partner)
      "relu" -> [1 if v.data > 0 else 0]
      "inv"  -> [-1 / parent.data ** 2]
    A Value with no parents (a leaf) returns []."""
    a = v.parents
    if v.op == "+":
        return [1.0, 1.0]
    if v.op == "*":
        return [a[1].data, a[0].data]
    if v.op == "relu":
        return [1.0 if v.data > 0 else 0.0]
    if v.op == "inv":
        return [-1.0 / a[0].data ** 2]
    return []


# ── Step 12: backward ──────────────────────────────────────────────────
def backward(out):  # drill
    """Fill in .grad on every Value that out depends on: d out / d value.
    Order the graph so each Value comes after its parents, the Values
    that feed it (a topological order), set out.grad to 1, then walk
    the order in reverse, adding grad * local gradient to each parent."""
    order, seen = [], set()

    def visit(v):
        if id(v) in seen:
            return
        seen.add(id(v))
        for p in v.parents:
            visit(p)
        order.append(v)
    visit(out)
    for v in order:
        v.grad = 0.0
    out.grad = 1.0
    for v in reversed(order):
        for p, g in zip(v.parents, local_grads(v)):
            p.grad += v.grad * g


# ── Step 13: the linear model, rebuilt on Value ────────────────────────
def mse_value(X, y, w):  # drill
    """The same mse as step 4, but w is a list of Values, so the result
    is a Value whose backward() gives the gradient for free."""
    total = Value(0.0)
    for row, t in zip(X, y):
        pred = Value(0.0)
        for xj, wj in zip(row, w):
            pred = pred + wj * xj
        diff = pred - t
        total = total + diff * diff
    return total * (1.0 / len(y))


def grad_by_autograd(X, y, w):
    """The gradient of the loss at w, by building the graph and calling
    backward: should agree with grad_mse_linear."""
    ws = [Value(wi) for wi in w]
    backward(mse_value(X, y, ws))
    return [wi.grad for wi in ws]


# ── Step 14: rides the model never saw ─────────────────────────────────
def split(rows, frac, seed):  # drill
    """Shuffle rows with random.Random(seed) and cut them: the first
    `frac` share (rounded down) is the training set, the rest is held
    out. Returns (train, held). The same seed gives the same split."""
    rows = list(rows)
    random.Random(seed).shuffle(rows)
    cut = int(len(rows) * frac)
    return rows[:cut], rows[cut:]


def residual_by(rides, model, key):
    """Mean (fare - prediction) for the rides where key(ride) is true:
    positive means the model under-charges them. model is what
    fit_linear returns: (weights, means, stds) for standardised features."""
    picked = [r for r in rides if key(r)]
    if not picked:
        return 0.0
    return sum(r[3] - predict_std(r, model) for r in picked) / len(picked)


def predict_std(ride, model):
    """The fare a standardised linear model predicts for one ride."""
    w, means, stds = model
    return dot([(f - m) / s for f, m, s in zip(features(ride), means, stds)], w)


def fit_linear(train_rides, held_rides, lr=0.1, steps=200):
    """Standardise on the training rides, train the linear model there,
    and return (held-out mse, model) where model = (weights, means, stds)."""
    X, means, stds = standardise(design_matrix(train_rides))
    w, _ = train_linear(X, targets(train_rides), [0.0] * len(X[0]), lr, steps)
    Xh = [[(f - m) / s for f, m, s in zip(features(r), means, stds)] for r in held_rides]
    return loss(Xh, targets(held_rides), w), (w, means, stds)


# ── Step 15: a small network ───────────────────────────────────────────
def init_mlp(d_in, hidden, seed):
    """Parameters of a one-hidden-layer network as Values: W1 (hidden x
    d_in), b1 (hidden), W2 (hidden), b2 (1), small random numbers."""
    rng = random.Random(seed)
    s = 1.0 / math.sqrt(d_in)
    return {
        "W1": [[Value(rng.uniform(-s, s)) for _ in range(d_in)] for _ in range(hidden)],
        "b1": [Value(0.0) for _ in range(hidden)],
        "W2": [Value(rng.uniform(-s, s)) for _ in range(hidden)],
        "b2": Value(0.0),
    }


def mlp_forward(x, params):  # drill
    """One ride through the network: for each hidden unit h, take
    dot(W1[h], x) + b1[h] and apply relu; the output is the dot of those
    hidden values with W2, plus b2. Returns a Value."""
    hidden = []
    for row, b in zip(params["W1"], params["b1"]):
        h = b
        for wj, xj in zip(row, x):
            h = h + wj * xj
        hidden.append(h.relu())
    out = params["b2"]
    for hv, wo in zip(hidden, params["W2"]):
        out = out + hv * wo
    return out


def parameters(params):
    """Every Value in the parameter dict, as one flat list."""
    flat = list(params["b1"]) + list(params["W2"]) + [params["b2"]]
    for row in params["W1"]:
        flat.extend(row)
    return flat


# ── Step 16: training in batches ───────────────────────────────────────
def train(forward, params, X, y, lr, epochs, batch, seed):  # drill
    """Minibatch gradient descent. Each epoch, shuffle the row indexes
    with random.Random(seed + epoch), walk them in groups of `batch`, and
    for each group: build the mean squared error of forward(x, params)
    over the group as a Value, zero every parameter's grad, call
    backward, and move each parameter by -lr * grad. Returns the list of
    epoch losses (the mean of the group losses in that epoch)."""
    raise NotImplementedError("TODO step 16: train")
