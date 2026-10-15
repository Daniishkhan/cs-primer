# Drill: A0 Lab 2, milestone 5 of 5: softmax and cross-entropy (step 1 of 3)
# Everything else in this file is already written. Fill in:
#     logsumexp
# Check it with: python3 check.py 5

"""Lab 2: build an autograd engine, then check it against numerical gradients.

A `Value` is one number that remembers how it was made. Every arithmetic operation
creates a new Value that records its parents and a small function (`_backward`) that
pushes its gradient back into them. Calling `backward()` on the final Value (the loss)
runs those functions in reverse order and fills in `grad` everywhere: reverse-mode
automatic differentiation, chapter 9 of this course.

Notation: `v.data` is the number, `v.grad` is d(loss)/d(v) once backward() has run.

What is GIVEN: Value.__init__, the small neural-network classes (Neuron, Layer, MLP),
`graph_size` and the constants. What YOU write:

    1  Value: +, -, *, negation, repr and the reflected forms (forward values and bookkeeping)
    2  topo_order, Value.backward, and the backward rules of +, -, *
    3  /, **, exp, log, tanh, relu, sigmoid; numerical_grad, autograd_grad, max_error
    4  zero_grad, sgd_step, mse_loss, train
    5  logsumexp, softmax, cross_entropy

`python3 check.py` runs the milestones; the lab page explains each one.
"""
import math
import random

EPS = 1e-6          # step for central differences


# =============================================================================
# Milestones 1 to 3: the Value class
# =============================================================================
class Value:
    """A scalar that records the computation that produced it."""

    def __init__(self, data, _parents=(), _op=""):
        # GIVEN (the five fields every Value carries)
        self.data = float(data)          # the number
        self.grad = 0.0                  # d(loss)/d(this), filled in by backward()
        self._parents = tuple(_parents)  # the Values this one was computed from
        self._op = _op                   # a label such as "+" or "tanh", for debugging
        self._backward = lambda: None    # pushes self.grad into the parents' grads

    # ---- Milestones 1 and 2: + - * -----------------------------------------
    def __add__(self, other):
        """self + other. A plain number is wrapped in a Value first.

        The result records (self, other) as its parents and the label "+".
        Milestone 1: the forward value and the bookkeeping.
        Milestone 2: also give the result a `_backward` that adds out.grad into self.grad and
        other.grad (both local derivatives are 1). Use += because a Value may be used many times.
        """
        other = other if isinstance(other, Value) else Value(other)
        out = Value(self.data + other.data, (self, other), "+")

        def _backward():                 # milestone 2: d(a+b)/da = 1 and d(a+b)/db = 1
            self.grad += out.grad
            other.grad += out.grad
        out._backward = _backward
        return out

    def __mul__(self, other):
        """self * other. A plain number is wrapped in a Value first.

        The result records (self, other) as its parents and the label "*".
        Milestone 1: the forward value and the bookkeeping.
        Milestone 2: also give the result a `_backward`: d(ab)/da = b and d(ab)/db = a, each
        multiplied by out.grad (the chain rule), and added with +=.
        """
        other = other if isinstance(other, Value) else Value(other)
        out = Value(self.data * other.data, (self, other), "*")

        def _backward():                 # milestone 2: d(ab)/da = b and d(ab)/db = a
            self.grad += other.data * out.grad
            other.grad += self.data * out.grad
        out._backward = _backward
        return out

    def __neg__(self):
        """-self, built from the multiplication you already have."""
        return self * -1.0

    def __sub__(self, other):
        """self - other, built from + and negation (so it needs no backward rule of its own)."""
        other = other if isinstance(other, Value) else Value(other)
        return self + (-other)

    def __radd__(self, other):
        """number + Value."""
        return self + other

    def __rmul__(self, other):
        """number * Value."""
        return self * other

    def __rsub__(self, other):
        """number - Value."""
        return (-self) + other

    def __repr__(self):
        """Format as Value(data=7.0000, grad=0.0000): four decimal places for both."""
        return f"Value(data={self.data:.4f}, grad={self.grad:.4f})"

    # ---- Milestone 3: more operations ---------------------------------------
    def __truediv__(self, other):
        """self / other, built from multiplication and a power of -1."""
        other = other if isinstance(other, Value) else Value(other)
        return self * other ** -1

    def __rtruediv__(self, other):
        """number / Value."""
        return (self ** -1) * other

    def __pow__(self, n):
        """self ** n for a constant number n (a Value exponent raises TypeError).

        Record the label f"**{n}". Local derivative: n * self.data ** (n - 1).
        """
        if isinstance(n, Value):
            raise TypeError("only constant exponents are supported: v ** 2, not v ** w")
        out = Value(self.data ** n, (self,), f"**{n}")

        def _backward():                 # d(v^n)/dv = n v^(n-1)
            self.grad += n * self.data ** (n - 1) * out.grad
        out._backward = _backward
        return out

    def exp(self):
        """e ** self. Local derivative: e ** self.data, which is the result itself."""
        e = math.exp(self.data)
        out = Value(e, (self,), "exp")

        def _backward():                 # d(e^v)/dv = e^v
            self.grad += e * out.grad
        out._backward = _backward
        return out

    def log(self):
        """Natural log. A non-positive self.data raises ValueError. Local derivative: 1 / self.data."""
        if self.data <= 0:
            raise ValueError(f"log of a non-positive number: {self.data}")
        out = Value(math.log(self.data), (self,), "log")

        def _backward():                 # d(ln v)/dv = 1/v
            self.grad += out.grad / self.data
        out._backward = _backward
        return out

    def tanh(self):
        """Hyperbolic tangent. Local derivative: 1 - tanh(x) ** 2."""
        t = math.tanh(self.data)
        out = Value(t, (self,), "tanh")

        def _backward():                 # d(tanh v)/dv = 1 - tanh^2 v
            self.grad += (1.0 - t * t) * out.grad
        out._backward = _backward
        return out

    def relu(self):
        """max(0, self). Local derivative: 1 if self.data > 0, else 0 (including exactly 0)."""
        out = Value(self.data if self.data > 0 else 0.0, (self,), "relu")

        def _backward():                 # 1 where the input was positive, else 0 (including at 0)
            self.grad += (1.0 if self.data > 0 else 0.0) * out.grad
        out._backward = _backward
        return out

    def sigmoid(self):
        """1 / (1 + e^-x), without overflow for x = -1000. Local derivative: s * (1 - s).

        Hint: for x >= 0 use 1 / (1 + exp(-x)); for x < 0 use exp(x) / (1 + exp(x)).
        """
        x = self.data
        s = 1.0 / (1.0 + math.exp(-x)) if x >= 0 else math.exp(x) / (1.0 + math.exp(x))   # no overflow for x = -1000
        out = Value(s, (self,), "sigmoid")

        def _backward():                 # d(sigma)/dv = sigma (1 - sigma)
            self.grad += s * (1.0 - s) * out.grad
        out._backward = _backward
        return out

    # ---- Milestone 2: backward ----------------------------------------------
    def backward(self):
        """Fill in .grad for every Value that contributed to self.

        Sets self.grad = 1 (the derivative of a thing with respect to itself), then calls each
        node's _backward in reverse topological order, so a node's gradient is complete
        before it is pushed to its parents. Gradients ADD UP across calls (see zero_grad).
        """
        order = topo_order(self)
        self.grad = 1.0
        for node in reversed(order):
            node._backward()


def topo_order(root):
    """All Values reachable from root, parents before children, each exactly once, root last.

    Must handle a graph 10,000 nodes deep, so recurse with an explicit stack, not Python's call stack.
    """
    order, seen = [], set()
    stack = [(root, False)]
    while stack:
        node, expanded = stack.pop()
        if expanded:
            order.append(node)
            continue
        if id(node) in seen:
            continue
        seen.add(id(node))
        stack.append((node, True))              # emit this node after all its parents
        for p in node._parents:
            if id(p) not in seen:
                stack.append((p, False))
    return order


# =============================================================================
# Milestone 3: checking gradients numerically
# =============================================================================
def numerical_grad(f, xs, eps=EPS):
    """d f / d xs[i] for every i by central differences: (f(x + eps) - f(x - eps)) / (2 eps).

    f takes a list of Values and returns a Value. Call it on fresh Values built from plain
    floats (never reuse a Value whose grad you care about) and read .data off the result.
    """
    grads = []
    for i in range(len(xs)):
        hi = [Value(x + (eps if j == i else 0.0)) for j, x in enumerate(xs)]
        lo = [Value(x - (eps if j == i else 0.0)) for j, x in enumerate(xs)]
        grads.append((f(hi).data - f(lo).data) / (2.0 * eps))
    return grads


def autograd_grad(f, xs):
    """d f / d xs[i] for every i, using your engine: build Values, call f, call backward."""
    vals = [Value(x) for x in xs]
    f(vals).backward()
    return [v.grad for v in vals]


def max_error(a, b):
    """The largest relative difference between two lists of numbers.

    Relative to the bigger magnitude, but never dividing by less than 1:
    max over i of |a[i] - b[i]| / max(1, |a[i]|, |b[i]|).
    """
    return max(abs(x - y) / max(1.0, abs(x), abs(y)) for x, y in zip(a, b))


# =============================================================================
# GIVEN: a small neural network built from Values
# =============================================================================
class Neuron:
    """w . x + b, passed through an activation: "tanh", "relu" or "linear"."""

    def __init__(self, n_in, rng, act="tanh"):
        self.w = [Value(rng.uniform(-1.0, 1.0)) for _ in range(n_in)]
        self.b = Value(0.0)
        self.act = act

    def __call__(self, x):
        z = self.b
        for wi, xi in zip(self.w, x):
            z = z + wi * xi
        return {"tanh": z.tanh, "relu": z.relu, "linear": lambda: z}[self.act]()

    def params(self):
        return self.w + [self.b]


class Layer:
    def __init__(self, n_in, n_out, rng, act="tanh"):
        self.neurons = [Neuron(n_in, rng, act) for _ in range(n_out)]

    def __call__(self, x):
        return [n(x) for n in self.neurons]

    def params(self):
        return [p for n in self.neurons for p in n.params()]


class MLP:
    """A multi-layer perceptron: sizes=[2, 4, 1] is 2 inputs, 4 hidden neurons, 1 output.

    Hidden layers use `act`; the last layer is linear unless `out_act` says otherwise.
    Initial weights come from random.Random(seed), so the same seed gives the same network.
    """

    def __init__(self, sizes, seed=0, act="tanh", out_act="linear"):
        rng = random.Random(seed)
        self.layers = []
        for i in range(len(sizes) - 1):
            last = i == len(sizes) - 2
            self.layers.append(Layer(sizes[i], sizes[i + 1], rng, out_act if last else act))

    def __call__(self, x):
        for layer in self.layers:
            x = layer(x)
        return x

    def params(self):
        return [p for layer in self.layers for p in layer.params()]


def graph_size(root):
    """How many Values the computation behind `root` created."""
    return len(topo_order(root))


# =============================================================================
# Milestone 4: training with gradient descent
# =============================================================================
def zero_grad(params):
    """Reset .grad to 0.0 on every parameter. backward() adds, so without this gradients pile up."""
    for p in params:
        p.grad = 0.0


def sgd_step(params, lr):
    """One gradient-descent update: data <- data - lr * grad, for every parameter."""
    for p in params:
        p.data -= lr * p.grad


def mse_loss(preds, targets):
    """Mean squared error: the average of (pred - target)^2. preds are Values, targets are numbers."""
    if len(preds) != len(targets) or not preds:
        raise ValueError("preds and targets must be non-empty and the same length")
    total = Value(0.0)
    for p, t in zip(preds, targets):
        total = total + (p - t) ** 2
    return total * (1.0 / len(preds))


def train(params, loss_fn, steps, lr):
    """Run `steps` rounds of: zero the gradients, compute loss = loss_fn(), backward, sgd_step.

    loss_fn takes no arguments and returns a Value (it closes over the model and the data).
    Returns the list of loss values, one per step (the loss BEFORE that step's update).
    """
    losses = []
    for _ in range(steps):
        zero_grad(params)
        loss = loss_fn()
        loss.backward()
        sgd_step(params, lr)
        losses.append(loss.data)
    return losses


# =============================================================================
# Milestone 5: classification losses
# =============================================================================
def logsumexp(zs):
    """log(sum(exp(z))) for a list of Values, stable: subtract the largest z first.

    The maximum is a CONSTANT shift (use its plain number, not a Value), so it adds no
    gradient path; the result is  m + log(sum(exp(z - m))).
    """
    raise NotImplementedError("TODO milestone 5: logsumexp")


def softmax(zs):
    """The probabilities exp(z_i) / sum_j exp(z_j), as a list of Values, stable for any size of z."""
    lse = logsumexp(zs)
    return [(z - lse).exp() for z in zs]


def cross_entropy(logits, target):
    """-log softmax(logits)[target] for a list of logit Values and an integer class index.

    Computed as logsumexp(logits) - logits[target]: no separate softmax, no log(0).
    """
    if not 0 <= target < len(logits):
        raise IndexError(f"target {target} out of range for {len(logits)} classes")
    return logsumexp(logits) - logits[target]
