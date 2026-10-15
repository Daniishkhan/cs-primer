# Drill: A0 Lab 3, milestone 4 of 6: L2 penalty versus AdamW (step 1 of 2)
# Everything else in this file is already written. Fill in:
#     AdamL2.step
# Check it with: python3 check.py 4

"""Lab 3: The Optimiser Race (reference solution).

Five optimisers written over plain Python lists, the same update rules as chapter 10,
then the extras that real training runs depend on: schedules and gradient clipping.

Notation: w is the weight vector (a list of floats), g = grad L(w) the gradient, eta (`lr`)
the learning rate. Every optimiser is an object with `step(w, g) -> new_w`: it returns a
NEW list, never modifies its arguments, and keeps its own state (velocity, running averages).

What is GIVEN: vector helpers, the double-well surface, `steps_to_origin`, `GRID`, `noisy_problem`
and the record type `Trace`. What YOU write:

    1  bowl, rosenbrock, SGD, minimise
    2  Momentum
    3  RMSProp, Adam
    4  AdamL2, AdamW
    5  warmup_cosine, wsd, global_norm, clip_by_global_norm
    6  best_lr, train

`python3 check.py solution` runs the milestones; the lab page explains each one.
"""
import math
import random
from collections import namedtuple

DIVERGED = 1e12          # a loss above this (or not finite) counts as a blow-up


# =============================================================================
# Given: vector helpers (lists of floats) and the run record
# =============================================================================
def vadd(a, b):
    return [x + y for x, y in zip(a, b)]


def vsub(a, b):
    return [x - y for x, y in zip(a, b)]


def vscale(a, c):
    return [c * x for x in a]


def vdot(a, b):
    return sum(x * y for x, y in zip(a, b))


def vnorm(a):
    return math.sqrt(vdot(a, a))


Trace = namedtuple("Trace", "w losses diverged")
# w:        the final weights
# losses:   the loss at the start and after every step (length steps + 1); if the run blew
#           up, the list stops early and its last entry is math.inf
# diverged: True if the loss became non-finite or exceeded DIVERGED


# =============================================================================
# Milestone 1: test surfaces, plain gradient descent, the loop
# =============================================================================
def bowl(w, kappa=100.0):
    """The narrow valley f(x, y) = 0.5 * (x^2 + kappa * y^2): returns (f, [df/dx, df/dy])."""
    x, y = w
    return 0.5 * (x * x + kappa * y * y), [x, kappa * y]


def rosenbrock(w):
    """Rosenbrock's banana f(x, y) = (1 - x)^2 + 100 (y - x^2)^2, minimum 0 at (1, 1).

    Returns (f, [df/dx, df/dy]).
    """
    x, y = w
    r = y - x * x
    return (1 - x) ** 2 + 100 * r * r, [-2 * (1 - x) - 400 * x * r, 200 * r]


def double_well(w):
    """GIVEN. f(x, y) = (x^2 - 1)^2 + 0.5 y^2: two minima at (-1, 0) and (1, 0), a hump at x = 0."""
    x, y = w
    return (x * x - 1) ** 2 + 0.5 * y * y, [4 * x * (x * x - 1), y]


class SGD:
    """Plain gradient descent: w <- w - lr * g."""

    def __init__(self, lr):
        self.lr = lr

    def step(self, w, g):
        """Return the new weights: SGD(0.1).step([1.0, 2.0], [1.0, -1.0]) == [0.9, 2.1].

        Return a NEW list; do not modify w or g.
        """
        return [wi - self.lr * gi for wi, gi in zip(w, g)]


def minimise(opt, fn, w0, steps):
    """Run `steps` optimiser steps on fn from w0 and return a Trace.

    fn(w) returns (loss, gradient). Record the loss before the first step and after each
    step. If the loss is not finite or exceeds DIVERGED, stop: set diverged=True and make
    the last entry of `losses` math.inf.

    Example: on f(w) = w^2 with SGD(0.25) from [1.0], each step halves w, so the losses are
    [1.0, 0.25, 0.0625, ...] and `Trace.w` is the weights after the last step.
    Do not modify w0.
    """
    w = list(w0)
    losses = []
    for _ in range(steps + 1):
        f, g = fn(w)
        if not math.isfinite(f) or f > DIVERGED:
            losses.append(math.inf)
            return Trace(w, losses, True)
        losses.append(f)
        if len(losses) == steps + 1:
            break
        w = opt.step(w, g)
    return Trace(w, losses, False)


# =============================================================================
# Milestone 2: momentum
# =============================================================================
class Momentum:
    """Heavy-ball momentum, as in chapter 10: v <- beta * v + g, then w <- w - lr * v."""

    def __init__(self, lr, beta=0.9):
        self.lr, self.beta, self.v = lr, beta, None

    def step(self, w, g):
        """The velocity starts at zero. With lr 0.1, beta 0.9 and g = [1, 2] twice from [0, 0]:
        v = [1, 2] then [1.9, 3.8], so w goes [-0.1, -0.2] then [-0.29, -0.58]."""
        if self.v is None:
            self.v = [0.0] * len(w)
        self.v = [self.beta * vi + gi for vi, gi in zip(self.v, g)]
        return [wi - self.lr * vi for wi, vi in zip(w, self.v)]


# =============================================================================
# Milestone 3: adaptive step sizes
# =============================================================================
class RMSProp:
    """s <- beta * s + (1 - beta) * g^2 (per coordinate); w <- w - lr * g / (sqrt(s) + eps)."""

    def __init__(self, lr, beta=0.9, eps=1e-8):
        self.lr, self.beta, self.eps, self.s = lr, beta, eps, None

    def step(self, w, g):
        """Per coordinate. The first step is lr * g / (sqrt(0.1) |g| + eps): about 3.16 * lr in the
        downhill direction, whatever the size of g. Keep eps OUTSIDE the square root."""
        if self.s is None:
            self.s = [0.0] * len(w)
        self.s = [self.beta * si + (1 - self.beta) * gi * gi for si, gi in zip(self.s, g)]
        return [wi - self.lr * gi / (math.sqrt(si) + self.eps) for wi, gi, si in zip(w, g, self.s)]


class Adam:
    """Adam (Kingma and Ba, 2014): a momentum average m, a scale average v, bias-corrected.

    t <- t + 1;  m <- b1 m + (1 - b1) g;  v <- b2 v + (1 - b2) g^2
    m_hat = m / (1 - b1^t);  v_hat = v / (1 - b2^t);  w <- w - lr * m_hat / (sqrt(v_hat) + eps)
    """

    def __init__(self, lr, b1=0.9, b2=0.999, eps=1e-8):
        self.lr, self.b1, self.b2, self.eps = lr, b1, b2, eps
        self.m = self.v = None
        self.t = 0

    def step(self, w, g):
        """Per coordinate, with t counting steps from 1. After bias correction the first step is
        lr * g / (|g| + eps), about lr * sign(g); with a constant gradient EVERY step is."""
        if self.m is None:
            self.m, self.v = [0.0] * len(w), [0.0] * len(w)
        self.t += 1
        self.m = [self.b1 * m + (1 - self.b1) * gi for m, gi in zip(self.m, g)]
        self.v = [self.b2 * v + (1 - self.b2) * gi * gi for v, gi in zip(self.v, g)]
        c1, c2 = 1 - self.b1 ** self.t, 1 - self.b2 ** self.t          # bias corrections
        return [wi - self.lr * (m / c1) / (math.sqrt(v / c2) + self.eps)
                for wi, m, v in zip(w, self.m, self.v)]


# =============================================================================
# Milestone 4: two ways to add weight decay to Adam
# =============================================================================
class AdamL2(Adam):
    """Adam with an L2 penalty: the penalty's gradient l2 * w is ADDED TO g before Adam sees it."""

    def __init__(self, lr, l2, b1=0.9, b2=0.999, eps=1e-8):
        super().__init__(lr, b1, b2, eps)
        self.l2 = l2

    def step(self, w, g):
        """Adam's step on the gradient g + l2 * w. First step of AdamL2(0.1, 0.5) from [1, -2]
        with g = [0.5, 0.5]: Adam sees [1.0, -0.5], so w becomes [0.9, -1.9]."""
        # The decay now travels through m and v, so it is divided by sqrt(v_hat) like any gradient.
        raise NotImplementedError("TODO milestone 4: AdamL2.step")


class AdamW(Adam):
    """AdamW (Loshchilov and Hutter): decay the weights directly, outside the Adam machinery.

    w <- w * (1 - lr * weight_decay), using the weights you were GIVEN, then the ordinary Adam
    step with the unmodified gradient g.
    """

    def __init__(self, lr, weight_decay, b1=0.9, b2=0.999, eps=1e-8):
        super().__init__(lr, b1, b2, eps)
        self.weight_decay = weight_decay

    def step(self, w, g):
        """First step of AdamW(0.1, 0.5) from [1, -2] with g = [0.5, 0.5]: decay to [0.95, -1.9],
        then Adam moves each coordinate 0.1 downhill: [0.85, -2.0]."""
        decayed = [wi * (1 - self.lr * self.weight_decay) for wi in w]
        adam = super().step(w, g)                         # w - lr * m_hat / (sqrt(v_hat) + eps)
        return [a - (wi - d) for a, wi, d in zip(adam, w, decayed)]   # apply the decay on top


# =============================================================================
# Milestone 5: schedules and gradient clipping
# =============================================================================
def warmup_cosine(t, total, warmup, floor=0.1):
    """Learning-rate multiplier at step t: linear warmup 0 -> 1 over `warmup` steps, then a
    half cosine from 1 down to `floor` at step `total`."""
    if t < warmup:
        return t / warmup
    progress = (t - warmup) / (total - warmup)
    return floor + (1 - floor) * 0.5 * (1 + math.cos(math.pi * progress))


def wsd(t, total, warmup, decay_start, floor=0.1):
    """Warmup-stable-decay: warm up to 1, hold 1 until `decay_start`, then decay linearly to
    `floor` at step `total`."""
    if t < warmup:
        return t / warmup
    if t < decay_start:
        return 1.0
    return 1.0 - (1 - floor) * (t - decay_start) / (total - decay_start)


def global_norm(grads):
    """The L2 norm of ALL the gradients together: grads is a list of lists of floats."""
    return math.sqrt(sum(x * x for g in grads for x in g))


def clip_by_global_norm(grads, max_norm):
    """Scale every gradient by ONE common factor so the global norm is at most max_norm.

    Returns (clipped_grads, norm_before, scale), with scale = min(1, max_norm / (norm + 1e-6)).
    A gradient already within the limit passes through with scale exactly 1.0.
    Example: clip_by_global_norm([[3.0], [4.0]], 1.0) -> ([[0.6], [0.8]], 5.0, 0.2) up to the epsilon.
    Return new lists; do not modify grads.
    """
    norm = global_norm(grads)
    scale = min(1.0, max_norm / (norm + 1e-6))
    return [[x * scale for x in g] for g in grads], norm, scale


# =============================================================================
# Milestone 6: the race
# =============================================================================
def noisy_problem(seed=0, dim=5, noise=0.5, spike_every=40, spike_size=60.0):
    """GIVEN. A stochastic test problem for `train`: the loss is 0.5 |w|^2, the minimum is the origin.

    Returns grad_fn(w, t) -> (loss, gradient). The gradient is w plus Gaussian noise of standard
    deviation `noise` per coordinate, like a minibatch gradient; on every `spike_every`-th step
    the noise is multiplied by `spike_size`, like a rare bad batch. The noise comes from one
    random.Random(seed), so grad_fn must be called exactly once per step, in order.
    """
    rng = random.Random(seed)

    def grad_fn(w, t):
        scale = spike_size if t % spike_every == spike_every - 1 else 1.0
        return 0.5 * vdot(w, w), [wi + scale * noise * rng.gauss(0.0, 1.0) for wi in w]
    return grad_fn


_LO, _HI = math.log10(1e-4), math.log10(0.5)
GRID = [10 ** (_LO + (_HI - _LO) * i / 13) for i in range(14)]     # 14 rates, 1e-4 to 0.5, evenly spaced in log
GRID[0], GRID[-1] = 1e-4, 0.5


def steps_to_origin(make, fn, w0, tol=1e-6, cap=20000):
    """GIVEN. Steps until |w| < tol (for surfaces whose minimum is the origin); None if the
    optimiser diverges or has not arrived after `cap` steps."""
    w, opt = list(w0), make()
    for t in range(1, cap + 1):
        w = opt.step(w, fn(w)[1])
        if not all(math.isfinite(x) for x in w) or max(abs(x) for x in w) > 1e6:
            return None
        if vnorm(w) < tol:
            return t
    return None


def best_lr(make, fn, w0, grid, steps):
    """Try every learning rate in `grid` (make(lr) builds a fresh optimiser) and return
    (lr, final_loss) for the one with the lowest final loss. Rates that diverge are skipped;
    if all diverge return (None, math.inf). Ties go to the smaller rate."""
    best = (None, math.inf)
    for lr in grid:
        trace = minimise(make(lr), fn, w0, steps)
        if not trace.diverged and trace.losses[-1] < best[1]:
            best = (lr, trace.losses[-1])
    return best


def train(opt, w0, grad_fn, steps, schedule=None, max_norm=None):
    """Train with an optional learning-rate schedule and gradient clipping.

    grad_fn(w, t) returns (loss, gradient) at step t (t = 0, 1, ...). Remember base = opt.lr.
    At each step t: evaluate grad_fn at the current w, set opt.lr = base * schedule(t) (if a
    schedule is given), clip the gradient to max_norm by global norm (if given; count the
    steps where it was actually shortened), then take the optimiser step.

    Returns a dict: {"w": final weights, "losses": the loss seen at each step (length steps),
    "lrs": the learning rate used at each step, "clipped": number of clipped steps}.
    """
    w = list(w0)
    base = opt.lr
    losses, lrs, clipped = [], [], 0
    for t in range(steps):
        loss, g = grad_fn(w, t)
        if schedule is not None:
            opt.lr = base * schedule(t)
        if max_norm is not None:
            (g,), _, scale = clip_by_global_norm([g], max_norm)
            clipped += scale < 1.0
        losses.append(loss)
        lrs.append(opt.lr)
        w = opt.step(w, g)
    opt.lr = base
    return {"w": w, "losses": losses, "lrs": lrs, "clipped": clipped}
