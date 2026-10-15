# Drill: A2 Lab 4, milestone 2 of 5: layers on Values (step 4 of 4)
# Everything else in this file is already written. Fill in:
#     cross_entropy
# Check it with: python3 check.py 2

"""Lab 4 reference solution: a character-level GPT in pure Python, with its own scalar autograd.

Notation follows Deep Learning chapters 09, 10 and 12: C is the width (d_model), h the number of heads,
d_k = C / h, T the context length, V the vocabulary. Weight matrices are stored as lists of rows with
shape (n_out, n_in), so linear(x, W) is a list of dot products: out[i] = sum_j W[i][j] * x[j].

The design follows the spirit of Karpathy's micrograd and microgpt (a scalar autograd and a GPT in a few
hundred lines of Python) but all code here is written for this lab.
"""
import math
import random

from names import NAMES

# ----------------------------------------------------------------------------------------
# Given: data, vocabulary and configuration
# ----------------------------------------------------------------------------------------
BOS = 0                                    # one special token that marks both the start and the end of a name
CHARS = "abcdefghijklmnopqrstuvwxyz"
V = len(CHARS) + 1                         # 27 tokens: BOS plus 26 letters
CFG = {"V": V, "C": 8, "h": 2, "T": 8, "L": 1}     # the model of the training run: about 1,300 weights
TRAIN = [n for i, n in enumerate(NAMES) if i % 7 != 0]
HELD_OUT = [n for i, n in enumerate(NAMES) if i % 7 == 0]


def encode(name):
    """'ana' -> [0, 1, 14, 1, 0]: BOS, one id per letter, BOS again. Letter ids are 1 to 26."""
    return [BOS] + [CHARS.index(c) + 1 for c in name] + [BOS]


def decode(ids):
    """Inverse of encode for the letters; BOS is dropped."""
    return "".join(CHARS[i - 1] for i in ids if i != BOS)


def sample_index(probs, rng):
    """Draw an index with the given probabilities using one number from rng."""
    r, acc = rng.random(), 0.0
    for i, p in enumerate(probs):
        acc += p
        if r < acc:
            return i
    return len(probs) - 1


# ----------------------------------------------------------------------------------------
# Milestone 1: a scalar autograd engine
# ----------------------------------------------------------------------------------------
class Value:
    """A number that remembers how it was made, so that backward() can fill in .grad everywhere.

    .data is the number, .grad is d(output)/d(this value) after backward(), _prev are the Values this one
    was computed from, and _back is a function that pushes self.grad into the grads of _prev."""
    __slots__ = ("data", "grad", "_prev", "_back")

    def __init__(self, data, prev=()):
        self.data = float(data)
        self.grad = 0.0
        self._prev = prev
        self._back = None

    def __add__(self, other):
        """self + other, where other is a Value or a plain number."""
        other = other if isinstance(other, Value) else Value(other)
        out = Value(self.data + other.data, (self, other))

        def back():
            self.grad += out.grad                  # d(a + b)/da = 1
            other.grad += out.grad
        out._back = back
        return out

    def __mul__(self, other):
        """self * other."""
        other = other if isinstance(other, Value) else Value(other)
        out = Value(self.data * other.data, (self, other))

        def back():
            self.grad += other.data * out.grad     # d(a b)/da = b
            other.grad += self.data * out.grad
        out._back = back
        return out

    def __pow__(self, k):
        """self ** k for a plain number k (an int or a float, not a Value)."""
        out = Value(self.data ** k, (self,))

        def back():
            self.grad += k * self.data ** (k - 1) * out.grad
        out._back = back
        return out

    def exp(self):
        """e ** self, as a new Value."""
        out = Value(math.exp(self.data), (self,))

        def back():
            self.grad += out.data * out.grad       # d exp(a)/da = exp(a)
        out._back = back
        return out

    def log(self):
        """Natural logarithm, as a new Value (self.data must be positive)."""
        out = Value(math.log(self.data), (self,))

        def back():
            self.grad += out.grad / self.data      # d log(a)/da = 1/a
        out._back = back
        return out

    def relu(self):
        """max(0, self); the slope is 1 where self.data > 0 and 0 elsewhere (including exactly 0)."""
        out = Value(self.data if self.data > 0 else 0.0, (self,))

        def back():
            self.grad += (1.0 if self.data > 0 else 0.0) * out.grad
        out._back = back
        return out

    def backward(self):
        """Set self.grad = 1 and propagate to every Value this one depends on.
        Visit each node once, in reverse topological order, so a node's grad is complete before it is pushed on."""
        order, seen = [], set()
        stack = [(self, False)]                    # iterative depth-first search: deep graphs must not overflow the stack
        while stack:
            v, expanded = stack.pop()
            if expanded:
                order.append(v)                    # appended only after all its inputs
            elif id(v) not in seen:
                seen.add(id(v))
                stack.append((v, True))
                for p in v._prev:
                    stack.append((p, False))
        self.grad = 1.0
        for v in reversed(order):
            if v._back:
                v._back()

    # given: everything else is built from the six operations above
    def __neg__(self):
        return self * -1.0

    def __sub__(self, other):
        return self + (-other)

    def __truediv__(self, other):
        return self * (other ** -1 if isinstance(other, Value) else 1.0 / other)

    def __radd__(self, other):
        return self + other

    def __rmul__(self, other):
        return self * other

    def __rsub__(self, other):
        return (-self) + other

    def __rtruediv__(self, other):
        return (self ** -1) * other

    def __repr__(self):
        return f"Value(data={self.data:.6g}, grad={self.grad:.6g})"


# ----------------------------------------------------------------------------------------
# Milestone 2: the layers, on lists of Values
# ----------------------------------------------------------------------------------------
def linear(x, W):
    """x: list of n_in Values, W: n_out rows of n_in Values. Returns n_out Values, out[i] = sum_j W[i][j] x[j]."""
    return [sum((w * xi for w, xi in zip(row, x)), Value(0.0)) for row in W]


def softmax(logits):
    """Probabilities as Values. Subtract the largest logit (a plain float, a constant) before exp."""
    m = max(v.data for v in logits)
    exps = [(v - m).exp() for v in logits]
    total = sum(exps, Value(0.0))
    return [e / total for e in exps]


def rmsnorm(x, eps=1e-5):
    """Scale the vector to unit root-mean-square: x_i * (mean(x^2) + eps) ** -0.5 (chapter 03, RMSNorm)."""
    ms = sum((xi * xi for xi in x), Value(0.0)) * (1.0 / len(x))
    scale = (ms + eps) ** -0.5
    return [xi * scale for xi in x]


def cross_entropy(logits, target):
    """-log softmax(logits)[target] as one Value, in nats."""
    raise NotImplementedError("TODO milestone 2: cross_entropy")


# ----------------------------------------------------------------------------------------
# Given: parameters
# ----------------------------------------------------------------------------------------
def init_params(cfg, seed=0, std=0.08):
    """Random weights as Values. Matrices are (n_out, n_in). Returns a dict of matrices; one per layer for blocks."""
    rng = random.Random(seed)
    C, V_, T, L = cfg["C"], cfg["V"], cfg["T"], cfg["L"]

    def mat(n_out, n_in):
        return [[Value(rng.gauss(0.0, std)) for _ in range(n_in)] for _ in range(n_out)]
    p = {"wte": mat(V_, C), "wpe": mat(T, C), "head": mat(V_, C)}
    for l in range(L):
        p[f"l{l}.wq"], p[f"l{l}.wk"], p[f"l{l}.wv"], p[f"l{l}.wo"] = mat(C, C), mat(C, C), mat(C, C), mat(C, C)
        p[f"l{l}.w1"], p[f"l{l}.w2"] = mat(4 * C, C), mat(C, 4 * C)
    return p


def flat_params(params):
    """Every parameter Value in a fixed order (dict insertion order, row by row)."""
    return [v for mat in params.values() for row in mat for v in row]


# ----------------------------------------------------------------------------------------
# Milestone 3: the GPT, one token at a time
# ----------------------------------------------------------------------------------------
def gpt_step(cfg, params, token, pos, keys, values):
    """Process ONE token at position pos and return its V logits (a list of Values).

    keys[l] and values[l] are the caches of layer l: lists with one C-vector (list of Values) per earlier
    position. Append this token's key and value to them BEFORE attending, so the token can read itself.
    Because only past entries are ever in the cache, the model is causal by construction."""
    C, h, L = cfg["C"], cfg["h"], cfg["L"]
    d_k = C // h
    x = [t + p for t, p in zip(params["wte"][token], params["wpe"][pos])]          # token + position embedding
    for l in range(L):
        xn = rmsnorm(x)
        q, k, v = linear(xn, params[f"l{l}.wq"]), linear(xn, params[f"l{l}.wk"]), linear(xn, params[f"l{l}.wv"])
        keys[l].append(k)
        values[l].append(v)
        heads = []
        for i in range(h):
            s = slice(i * d_k, (i + 1) * d_k)
            scores = [sum((a * b for a, b in zip(q[s], kt[s])), Value(0.0)) * (1.0 / math.sqrt(d_k)) for kt in keys[l]]
            w = softmax(scores)
            heads += [sum((w[t] * values[l][t][j] for t in range(len(w))), Value(0.0)) for j in range(s.start, s.stop)]
        x = [a + b for a, b in zip(x, linear(heads, params[f"l{l}.wo"]))]           # residual around attention
        hid = [z.relu() for z in linear(rmsnorm(x), params[f"l{l}.w1"])]
        x = [a + b for a, b in zip(x, linear(hid, params[f"l{l}.w2"]))]             # residual around the MLP
    return linear(rmsnorm(x), params["head"])


def sequence_loss(cfg, params, ids):
    """Mean cross-entropy of predicting ids[t+1] from ids[:t+1], over t = 0 .. len(ids) - 2 (one Value)."""
    ids = ids[:cfg["T"] + 1]                         # the context holds at most T input tokens
    keys = [[] for _ in range(cfg["L"])]
    values = [[] for _ in range(cfg["L"])]
    total = Value(0.0)
    for t in range(len(ids) - 1):
        total = total + cross_entropy(gpt_step(cfg, params, ids[t], t, keys, values), ids[t + 1])
    return total * (1.0 / (len(ids) - 1))


# ----------------------------------------------------------------------------------------
# Milestone 4: Adam and the training loop
# ----------------------------------------------------------------------------------------
class Adam:
    """Adam (A0 chapter 10) over a flat list of Values."""

    def __init__(self, params, lr=0.01, beta1=0.9, beta2=0.99, eps=1e-8):
        self.params, self.lr, self.beta1, self.beta2, self.eps = params, lr, beta1, beta2, eps
        self.m = [0.0] * len(params)
        self.v = [0.0] * len(params)
        self.t = 0

    def step(self, lr=None):
        """One update using each p.grad, with bias correction; then set every p.grad back to 0."""
        lr = self.lr if lr is None else lr
        self.t += 1
        c1, c2 = 1 - self.beta1 ** self.t, 1 - self.beta2 ** self.t
        for i, p in enumerate(self.params):
            g = p.grad
            self.m[i] = self.beta1 * self.m[i] + (1 - self.beta1) * g
            self.v[i] = self.beta2 * self.v[i] + (1 - self.beta2) * g * g
            p.data -= lr * (self.m[i] / c1) / (math.sqrt(self.v[i] / c2) + self.eps)
            p.grad = 0.0


def train(cfg, names, steps=600, seed=0, lr=0.02):
    """Train a fresh model for `steps` steps, one name per step, cycling through a seeded shuffle of names.
    The learning rate decays linearly from lr to 0 over the run. Returns (params, losses): the per-step losses."""
    params = init_params(cfg, seed)
    opt = Adam(flat_params(params), lr)
    rng = random.Random(seed)
    order, losses = [], []
    for step in range(steps):
        if not order:
            order = list(names)
            rng.shuffle(order)
        loss = sequence_loss(cfg, params, encode(order.pop()))
        loss.backward()
        opt.step(lr * (1.0 - step / steps))
        losses.append(loss.data)
    return params, losses


# ----------------------------------------------------------------------------------------
# Milestone 5: evaluating and sampling
# ----------------------------------------------------------------------------------------
def average_loss(cfg, params, names):
    """Mean per-character cross-entropy, in nats, over all names (every position of every name counts once)."""
    total, count = 0.0, 0
    for name in names:
        ids = encode(name)[:cfg["T"] + 1]
        total += sequence_loss(cfg, params, ids).data * (len(ids) - 1)
        count += len(ids) - 1
    return total / count


def sample_name(cfg, params, rng, temperature=1.0):
    """Generate one name: start from BOS, repeatedly sample the next token, stop at BOS or after T letters."""
    keys = [[] for _ in range(cfg["L"])]
    values = [[] for _ in range(cfg["L"])]
    token, out = BOS, []
    for pos in range(cfg["T"]):
        logits = gpt_step(cfg, params, token, pos, keys, values)
        scaled = [z.data / temperature for z in logits]
        m = max(scaled)
        e = [math.exp(z - m) for z in scaled]
        token = sample_index([x / sum(e) for x in e], rng)
        if token == BOS:
            break
        out.append(token)
    return decode(out)
