"""Self-check for Lab 2: Build an Autograd Engine.

    python3 check.py                  # checks your starter.py
    python3 check.py solution         # checks the reference solution
    python3 check.py solution 3       # only milestone 3
    python3 check.py solution 3 12    # milestone 3, replaying ONLY seed 12

Everything is deterministic: hand-derived gradients first, then seeded random
expressions whose gradients are compared with central differences computed by an
independent float-only evaluator below (it never touches your Value class), then
small training runs. The whole check finishes in a few seconds.
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
Value = mod.Value
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


def raises(exc, fn, *a, **k):
    try:
        fn(*a, **k)
    except exc:
        return True
    except NotImplementedError:
        raise
    except Exception as e:
        raise AssertionError(f"expected {exc.__name__} but got {type(e).__name__}: {e}")
    return False


def rel_err(a, b):
    return max(abs(x - y) / max(1.0, abs(x), abs(y)) for x, y in zip(a, b))


# =============================================================================
# An independent oracle: random expression trees, evaluated on floats and on Values
# =============================================================================
ALL_OPS = ["add", "sub", "mul", "div", "pow2", "pow3", "exp", "log", "tanh", "sigmoid", "neg", "scale"]
BASIC_OPS = ["add", "sub", "mul", "neg", "scale"]


def make_tree(rng, depth, nvars, allowed=ALL_OPS):
    """A random expression as nested tuples, safe on its whole domain (no log of a negative,
    no division by zero, no overflow)."""
    if depth == 0 or rng.random() < 0.15:
        return ("var", rng.randrange(nvars)) if rng.random() < 0.8 else ("const", round(rng.uniform(-2, 2), 2))
    op = rng.choice(allowed)
    a = make_tree(rng, depth - 1, nvars, allowed)
    if op in ("add", "sub", "mul", "div"):
        return (op, a, make_tree(rng, depth - 1, nvars, allowed))
    if op == "scale":
        return (op, a, round(rng.uniform(-3, 3), 2))
    return (op, a)


def ev(t, xs, ops):
    """Evaluate a tree with the operations table `ops` (float version or Value version)."""
    k = t[0]
    if k == "var":
        return xs[t[1]]
    if k == "const":
        return ops["const"](t[1])
    if k in ("add", "sub", "mul", "div"):
        a, b = ev(t[1], xs, ops), ev(t[2], xs, ops)
        if k == "div":                       # denominator b*b + 1 is never zero
            return ops["div"](a, ops["add"](ops["mul"](b, b), ops["const"](1.0)))
        return ops[k](a, b)
    a = ev(t[1], xs, ops)
    if k == "scale":
        return ops["mul"](a, ops["const"](t[2]))
    if k == "log":                           # log(a*a + 1) is always defined
        return ops["log"](ops["add"](ops["mul"](a, a), ops["const"](1.0)))
    if k == "exp":                           # exp(tanh(a)) stays bounded
        return ops["exp"](ops["tanh"](a))
    if k == "pow2":
        return ops["pow"](a, 2)
    if k == "pow3":
        return ops["pow"](a, 3)
    return ops[k](a)


FLOAT_OPS = {
    "const": lambda c: c, "add": lambda a, b: a + b, "sub": lambda a, b: a - b, "mul": lambda a, b: a * b,
    "div": lambda a, b: a / b, "pow": lambda a, n: a ** n, "exp": math.exp, "log": math.log, "tanh": math.tanh,
    "sigmoid": lambda x: 1.0 / (1.0 + math.exp(-x)), "neg": lambda a: -a,
}
VALUE_OPS = {
    "const": lambda c: Value(c), "add": lambda a, b: a + b, "sub": lambda a, b: a - b, "mul": lambda a, b: a * b,
    "div": lambda a, b: a / b, "pow": lambda a, n: a ** n, "exp": lambda a: a.exp(), "log": lambda a: a.log(),
    "tanh": lambda a: a.tanh(), "sigmoid": lambda a: a.sigmoid(), "neg": lambda a: -a,
}


def float_grad(t, xs, eps=1e-6):
    """Central differences using plain floats and math only."""
    g = []
    for i in range(len(xs)):
        hi = list(xs)
        lo = list(xs)
        hi[i] += eps
        lo[i] -= eps
        g.append((ev(t, hi, FLOAT_OPS) - ev(t, lo, FLOAT_OPS)) / (2 * eps))
    return g


def show(t):
    k = t[0]
    if k == "var":
        return f"x{t[1]}"
    if k == "const":
        return f"{t[1]}"
    if k in ("add", "sub", "mul", "div"):
        sym = {"add": "+", "sub": "-", "mul": "*", "div": "/"}[k]
        return f"({show(t[1])} {sym} {show(t[2])})"
    if k == "scale":
        return f"({show(t[1])} * {t[2]})"
    if k in ("pow2", "pow3"):
        return f"({show(t[1])} ** {k[-1]})"
    return f"{k}({show(t[1])})"


# =============================================================================
# Milestone 1: Value, forward only
# =============================================================================
def m1():
    a, b = Value(2.0), Value(3.0)
    assert a.data == 2.0 and a.grad == 0.0, f"a new Value has .data = the number and .grad = 0.0; got data={a.data}, grad={a.grad}"
    assert isinstance(Value(3).data, float), "integers must be stored as floats: Value(3).data should be 3.0"
    assert a._parents == () and Value(1.0)._op == "", "a leaf Value has no parents and an empty op label"
    c = a + b
    assert c.data == 5.0, f"2 + 3 should be 5, got {c.data}"
    assert len(c._parents) == 2 and c._parents[0] is a and c._parents[1] is b, \
        "(a + b)._parents must be the tuple (a, b): the very same objects, not copies"
    assert c._op == "+", f"the result of + records the label '+', got {c._op!r}"
    d = a * b
    assert d.data == 6.0 and d._op == "*" and d._parents == (a, b), "a * b is 6.0, op '*', parents (a, b)"
    assert (a + 1).data == 3.0 and (1 + a).data == 3.0, "adding a plain number must work on either side (__radd__)"
    assert (a * 4).data == 8.0 and (4 * a).data == 8.0, "multiplying by a plain number must work on either side (__rmul__)"
    assert (a - b).data == -1.0 and (b - a).data == 1.0, "subtraction: 2 - 3 = -1"
    assert (a - 5).data == -3.0 and (5 - a).data == 3.0, "number - Value (__rsub__): 5 - 2 = 3"
    assert (-a).data == -2.0, "negation: -(2) = -2"
    k = a + 1
    assert len(k._parents) == 2 and isinstance(k._parents[1], Value) and k._parents[1].data == 1.0, \
        "a plain number added to a Value must be wrapped in a Value (so it can be a node in the graph)"
    expr = a * b + a
    assert expr.data == 8.0, f"2*3 + 2 should be 8, got {expr.data}"
    assert a.data == 2.0 and b.data == 3.0 and a.grad == 0.0, "operations must not change their operands"
    assert repr(Value(7.0)) == "Value(data=7.0000, grad=0.0000)", f"repr should look like 'Value(data=7.0000, grad=0.0000)', got {Value(7.0)!r}"
    x = Value(1.0)
    y = x * x
    assert y._parents[0] is x and y._parents[1] is x, "x * x has the same Value as both parents (the graph records it twice)"
    # a long chain still evaluates forward
    t = Value(0.0)
    for _ in range(2000):
        t = t + 1
    assert t.data == 2000.0, f"adding 1 two thousand times should give 2000, got {t.data}"
    for s in seeds(range(1, 31)):
        rng = random.Random(s)
        tree = make_tree(rng, 4, 3, BASIC_OPS)
        xs = [rng.uniform(-1.5, 1.5) for _ in range(3)]
        want = ev(tree, xs, FLOAT_OPS)
        got = ev(tree, [Value(x) for x in xs], VALUE_OPS)
        assert near(got.data, want, 1e-9), f"seed {s}: {show(tree)} at {[round(x, 4) for x in xs]} should be {want}, got {got.data}"
    # random sums and products of Values and numbers against plain floats
    for s in seeds(range(1, 31)):
        rng = random.Random(1000 + s)
        p, q, r = (rng.uniform(-4, 4) for _ in range(3))
        vp, vq, vr = Value(p), Value(q), Value(r)
        got = (vp * vq - vr) * 2 + 3 * vp - (vq + 1) * vr
        want = (p * q - r) * 2 + 3 * p - (q + 1) * r
        assert near(got.data, want, 1e-9), f"seed {s}: (p*q - r)*2 + 3*p - (q+1)*r with p={p:.4f}, q={q:.4f}, r={r:.4f} should be {want:.6f}, got {got.data:.6f}"
    return ""


# =============================================================================
# Milestone 2: topological order and backward for + - *
# =============================================================================
def m2():
    x, y = Value(2.0), Value(3.0)
    f = x * y + x                          # df/dx = y + 1 = 4, df/dy = x = 2
    order = mod.topo_order(f)
    ids = [id(v) for v in order]
    assert len(ids) == len(set(ids)), "topo_order must list each Value exactly once (x is used twice in x*y + x)"
    assert order[-1] is f, "the root must come last"
    assert len(order) == 4, f"x*y + x has 4 Values (x, y, x*y, the sum); topo_order returned {len(order)}"
    pos = {id(v): i for i, v in enumerate(order)}
    for v in order:
        for p in v._parents:
            assert pos[id(p)] < pos[id(v)], "every Value must come AFTER all of its parents"
    f.backward()
    assert f.grad == 1.0, f"backward() sets the root's own gradient to 1.0, got {f.grad}"
    assert x.grad == 4.0 and y.grad == 2.0, f"for f = x*y + x at (2, 3): df/dx = y + 1 = 4 and df/dy = x = 2; got dx={x.grad}, dy={y.grad}"
    assert f.data == 8.0, "backward() must not change any .data"

    a = Value(3.0)
    g = a * a + a                          # a used three times: dg/da = 2a + 1 = 7
    g.backward()
    assert a.grad == 7.0, (f"a*a + a at a = 3 has derivative 2a + 1 = 7, got {a.grad}. A Value used more than once must "
                           "ADD the contributions from each use: write `self.grad += ...`, not `=`")

    a = Value(2.0)
    b, c = a * 2, a * 3
    d = b * c                               # 6 a^2, derivative 12 a = 24
    d.backward()
    assert a.grad == 24.0, f"the diamond d = (2a)(3a) at a = 2 has derivative 12a = 24, got {a.grad}. The gradients of both paths must be summed"
    assert b.grad == c.data and c.grad == b.data, "intermediate nodes get gradients too: d(bc)/db = c and d(bc)/dc = b"

    p, q = Value(5.0), Value(2.0)
    h = p - q
    h.backward()
    assert (p.grad, q.grad) == (1.0, -1.0), f"p - q has gradients (1, -1), got ({p.grad}, {q.grad})"
    n = Value(4.0)
    (-n).backward()
    assert n.grad == -1.0, f"d(-n)/dn = -1, got {n.grad}"
    s = Value(5.0)
    (7 - s * 2).backward()
    assert s.grad == -2.0, f"7 - 2s has derivative -2, got {s.grad}"
    s = Value(-3.0)
    (s * s).backward()
    assert s.grad == -6.0, f"s*s at -3 has derivative 2s = -6, got {s.grad}"

    other = Value(10.0)
    u, w = Value(1.0), Value(2.0)
    (u * w).backward()
    assert other.grad == 0.0, "a Value that is not part of the computation must keep grad 0"
    # gradients accumulate in the leaves across separate graphs
    t = Value(2.0)
    (t * t).backward()
    (t * 3).backward()
    assert t.grad == 4.0 + 3.0, (f"two backward passes through different graphs must ADD into the shared leaf: 4 + 3 = 7, got {t.grad}. "
                                 "This is why training loops zero the gradients before every step")

    # a long chain: Python's recursion limit is about 1000 frames
    x = Value(1.0)
    z = x
    for _ in range(5000):
        z = z * 1.0001
    assert len(mod.topo_order(z)) == 10001, "a chain of 5000 multiplications has 10,001 Values (5000 products, 5000 constants, the start)"
    z.backward()
    assert near(x.grad, 1.0001 ** 5000, 1e-9), (f"d/dx of x * 1.0001^5000 is 1.0001^5000 = {1.0001 ** 5000:.6f}, got {x.grad}. "
                                                "A recursive topological sort fails on deep graphs: use an explicit stack")

    for s in seeds(range(1, 31)):
        rng = random.Random(s)
        P, Q, R = (rng.uniform(-3, 3) for _ in range(3))
        vp, vq, vr = Value(P), Value(Q), Value(R)
        loss = (vp * vq - vr) * 2 + 3 * vp - (vq + 1) * vr + vp * vp * vq
        loss.backward()
        # d/dp = 2q + 3 + 2pq ; d/dq = 2p - r + p^2 ; d/dr = -2 - (q+1)
        want = [2 * Q + 3 + 2 * P * Q, 2 * P - R + P * P, -2 - (Q + 1)]
        got = [vp.grad, vq.grad, vr.grad]
        assert rel_err(got, want) < 1e-9, f"seed {s}: gradients at p={P:.4f}, q={Q:.4f}, r={R:.4f} should be {[round(w, 6) for w in want]}, got {[round(g, 6) for g in got]}"
    for s in seeds(range(1, 31)):                # random + - * trees against the float-only oracle
        rng = random.Random(500 + s)
        tree = make_tree(rng, 5, 3, BASIC_OPS)
        xs = [rng.uniform(-1.5, 1.5) for _ in range(3)]
        vs = [Value(x) for x in xs]
        ev(tree, vs, VALUE_OPS).backward()
        ref = float_grad(tree, xs)
        assert rel_err([v.grad for v in vs], ref) < 1e-5, f"seed {s}: f = {show(tree)} at {[round(x, 4) for x in xs]}: central differences give {[round(r, 6) for r in ref]}, your backward gives {[round(v.grad, 6) for v in vs]}"
    return ""


# =============================================================================
# Milestone 3: more operations and gradient checking
# =============================================================================
def grad_of(f, *xs):
    vals = [Value(x) for x in xs]
    out = f(*vals)
    out.backward()
    return out.data, [v.grad for v in vals]


def m3():
    e = math.e
    val, g = grad_of(lambda x, y: x / y, 6.0, 3.0)
    assert near(val, 2.0) and near(g[0], 1 / 3) and near(g[1], -6 / 9), f"x / y at (6, 3): value 2, dx = 1/y = 0.3333, dy = -x/y^2 = -0.6667; got {val}, {g}"
    val, g = grad_of(lambda x: 3 / x, 2.0)
    assert near(val, 1.5) and near(g[0], -0.75), f"3 / x at x = 2: value 1.5, derivative -3/x^2 = -0.75; got {val}, {g}"
    val, g = grad_of(lambda x: x / 4, 2.0)
    assert near(val, 0.5) and near(g[0], 0.25), f"x / 4 at 2: value 0.5, derivative 0.25; got {val}, {g}"
    val, g = grad_of(lambda x: x ** 3, 2.0)
    assert near(val, 8.0) and near(g[0], 12.0), f"x**3 at 2: value 8, derivative 3x^2 = 12; got {val}, {g}"
    val, g = grad_of(lambda x: x ** 0.5, 4.0)
    assert near(val, 2.0) and near(g[0], 0.25), f"x**0.5 at 4: value 2, derivative 1/(2 sqrt x) = 0.25; got {val}, {g}"
    val, g = grad_of(lambda x: x ** -1, 2.0)
    assert near(val, 0.5) and near(g[0], -0.25), f"x**-1 at 2: value 0.5, derivative -1/x^2 = -0.25; got {val}, {g}"
    val, g = grad_of(lambda x: x ** 2, -3.0)
    assert near(val, 9.0) and near(g[0], -6.0), f"x**2 at -3: value 9, derivative 2x = -6; got {val}, {g}"
    assert raises(TypeError, lambda: Value(2.0) ** Value(2.0)), "an exponent that is itself a Value is not supported: raise TypeError"
    val, g = grad_of(lambda x: x.exp(), 1.0)
    assert near(val, e) and near(g[0], e), f"exp(1) is e and so is its derivative; got {val}, {g}"
    val, g = grad_of(lambda x: x.log(), e)
    assert near(val, 1.0) and near(g[0], 1 / e), f"log(e) = 1 with derivative 1/e = 0.3679; got {val}, {g}"
    assert raises(ValueError, lambda: Value(0.0).log()), "log(0) must raise ValueError"
    assert raises(ValueError, lambda: Value(-1.0).log()), "log of a negative number must raise ValueError"
    t = math.tanh(0.5)
    val, g = grad_of(lambda x: x.tanh(), 0.5)
    assert near(val, t) and near(g[0], 1 - t * t), f"tanh(0.5) = {t:.6f}, derivative 1 - tanh^2 = {1 - t * t:.6f}; got {val}, {g}"
    val, g = grad_of(lambda x: x.relu(), 2.5)
    assert val == 2.5 and g[0] == 1.0, f"relu(2.5) = 2.5 with gradient 1; got {val}, {g}"
    val, g = grad_of(lambda x: x.relu(), -2.5)
    assert val == 0.0 and g[0] == 0.0, f"relu(-2.5) = 0 with gradient 0; got {val}, {g}"
    val, g = grad_of(lambda x: x.relu(), 0.0)
    assert val == 0.0 and g[0] == 0.0, f"relu(0) = 0; by convention its gradient there is 0, got {g[0]}"
    val, g = grad_of(lambda x: x.sigmoid(), 0.0)
    assert near(val, 0.5) and near(g[0], 0.25), f"sigmoid(0) = 0.5 with derivative 0.25; got {val}, {g}"
    val, g = grad_of(lambda x: x.sigmoid(), -1000.0)
    assert val == 0.0 and g[0] == 0.0, f"sigmoid(-1000) is 0 (not an OverflowError from exp(1000)); got {val}, {g}"
    val, g = grad_of(lambda x: x.sigmoid(), 1000.0)
    assert val == 1.0, f"sigmoid(1000) is 1; got {val}"

    # the gradient-checking tools
    f = lambda v: v[0] * v[1] + v[0].exp()
    want = [3.0 + math.exp(2.0), 2.0]
    num = mod.numerical_grad(f, [2.0, 3.0])
    assert len(num) == 2 and rel_err(num, want) < 1e-6, f"numerical_grad of x*y + exp(x) at (2, 3) should be {[round(w, 6) for w in want]}, got {num}"
    auto = mod.autograd_grad(f, [2.0, 3.0])
    assert rel_err(auto, want) < 1e-12, f"autograd_grad of x*y + exp(x) at (2, 3) should be {[round(w, 6) for w in want]}, got {auto}"
    sq = lambda v: v[0] * v[0]
    num = mod.numerical_grad(sq, [3.0], 1e-3)
    assert near(num[0], 6.0, 1e-9), "central differences are exact for a quadratic whatever the step: x^2 at 3 with eps = 1e-3 gives 6"
    assert near(mod.max_error([1.0, 2.0], [1.0, 2.0]), 0.0), "identical lists have error 0"
    assert near(mod.max_error([1000.0, 0.001], [1001.0, 0.002]), 0.001, 1e-9), \
        "max_error([1000, 0.001], [1001, 0.002]) is 0.001: the first pair differs by 1 in 1001 (0.000999), the second by 0.001 of max(1, ...) = 1"
    assert near(mod.max_error([0.0], [1e-8]), 1e-8, 1e-6), "tiny numbers are compared absolutely: never divide by less than 1"
    assert mod.max_error([1.0, 5.0], [1.0, 4.0]) > 0.15, "max_error picks the worst pair: 5 vs 4 differ by 1 in 5, error 0.2"
    before = Value(2.0)
    mod.autograd_grad(sq, [2.0])
    assert before.grad == 0.0, "autograd_grad builds its own Values; it must not touch others"

    worst = 0.0
    count = 0
    for s in seeds(range(1, 61)):
        rng = random.Random(s)
        tree = make_tree(rng, rng.randint(2, 5), 3)
        xs = [rng.uniform(-1.5, 1.5) for _ in range(3)]
        ref = float_grad(tree, xs)
        got = mod.autograd_grad(lambda vs: ev(tree, vs, VALUE_OPS), xs)
        err = rel_err(got, ref)
        worst = max(worst, err)
        count += 1
        assert err < 1e-5, (f"seed {s}: f = {show(tree)} at {[round(x, 4) for x in xs]}\n"
                            f"      central differences give {[round(r, 6) for r in ref]}\n"
                            f"      your engine gives        {[round(g, 6) for g in got]}\n"
                            "      a wrong or missing local derivative in one of the operations above is the usual cause")
        num = mod.numerical_grad(lambda vs: ev(tree, vs, VALUE_OPS), xs)
        assert rel_err(num, ref) < 1e-6, f"seed {s}: your numerical_grad disagrees with the float-only oracle: {num} vs {ref}"
    return f"{count} random expressions: worst relative error between your autograd and central differences is {worst:.1e}"


# =============================================================================
# Milestone 4: gradient descent and training
# =============================================================================
def m4():
    ps = [Value(1.0), Value(-2.0)]
    ps[0].grad, ps[1].grad = 0.5, -4.0
    mod.sgd_step(ps, 0.1)
    assert near(ps[0].data, 0.95) and near(ps[1].data, -1.6), f"sgd_step: 1 - 0.1*0.5 = 0.95 and -2 - 0.1*(-4) = -1.6; got {ps[0].data}, {ps[1].data}"
    assert ps[0].grad == 0.5, "sgd_step changes .data only; the gradients stay until zero_grad"
    mod.zero_grad(ps)
    assert ps[0].grad == 0.0 and ps[1].grad == 0.0 and ps[0].data == 0.95, "zero_grad sets every .grad to 0.0 and leaves .data alone"

    preds = [Value(2.0), Value(0.0), Value(5.0)]
    loss = mod.mse_loss(preds, [1.0, 1.0, 5.0])
    assert near(loss.data, 2 / 3), f"mse of [2, 0, 5] against [1, 1, 5] is (1 + 1 + 0)/3 = 0.6667, got {loss.data}"
    loss.backward()
    assert rel_err([p.grad for p in preds], [2 / 3, -2 / 3, 0.0]) < 1e-12, \
        f"d mse / d pred_i = 2 (pred_i - target_i) / n = [0.6667, -0.6667, 0]; got {[p.grad for p in preds]}"
    assert raises(ValueError, mod.mse_loss, [Value(1.0)], [1.0, 2.0]), "mismatched lengths must raise ValueError"

    # exact trajectory on a quadratic: w <- w - lr * 2 (w - 3), so w_k = 3 (1 - 0.8^k) and loss_k = 9 * 0.64^k
    w = Value(0.0)
    losses = mod.train([w], lambda: (w - 3.0) ** 2, 30, 0.1)
    assert len(losses) == 30, f"train returns one loss per step: expected 30, got {len(losses)}"
    for k in (0, 1, 2, 10, 29):
        assert near(losses[k], 9 * 0.64 ** k, 1e-9), (f"loss at step {k} should be 9 * 0.64^{k} = {9 * 0.64 ** k:.6f}, got {losses[k]:.6f}. "
                                                       "Gradients must be zeroed before every backward() (otherwise they pile up) and the recorded loss is the one BEFORE the update")
    assert near(w.data, 3 * (1 - 0.8 ** 30), 1e-9), f"after 30 steps w should be {3 * (1 - 0.8 ** 30):.6f}, got {w.data}"

    # the whole network's gradients, against central differences, parameter by parameter
    model = mod.MLP([2, 3, 1], seed=4)
    data = [([0.5, -1.0], 0.3), ([1.5, 0.2], -0.4), ([-0.7, 0.9], 0.8)]
    params = model.params()
    assert len(params) == 13, f"MLP([2, 3, 1]) has 3*(2+1) + 1*(3+1) = 13 parameters, got {len(params)}"
    loss_fn = lambda: mod.mse_loss([model(x)[0] for x, _ in data], [t for _, t in data])
    mod.zero_grad(params)
    loss_fn().backward()
    auto = [p.grad for p in params]
    num = []
    for p in params:
        old = p.data
        p.data = old + 1e-6
        hi = loss_fn().data
        p.data = old - 1e-6
        lo = loss_fn().data
        p.data = old
        num.append((hi - lo) / 2e-6)
    err = rel_err(auto, num)
    assert err < 1e-6, (f"gradients of the loss through a 13-parameter network disagree with central differences (worst relative error {err:.2g}). "
                        "Every operation passed its own test, so look at how gradients combine: a Value used by several neurons must sum")

    # XOR, as in chapter 9
    model = mod.MLP([2, 4, 1], seed=1, out_act="tanh")
    xor = [([0, 0], -1.0), ([0, 1], 1.0), ([1, 0], 1.0), ([1, 1], -1.0)]
    losses = mod.train(model.params(), lambda: mod.mse_loss([model(x)[0] for x, _ in xor], [t for _, t in xor]), 200, 0.3)
    assert losses[0] > 0.5 and losses[-1] < 0.05, f"XOR should train from a loss above 0.5 to below 0.05 in 200 steps at lr 0.3; went {losses[0]:.4f} to {losses[-1]:.4f}"
    assert losses[20] < losses[0] and losses[100] < losses[20], f"the loss should be lower at step 20 than at step 0, and lower at step 100 than at step 20; got {losses[0]:.3f}, {losses[20]:.3f}, {losses[100]:.3f}"
    for x, t in xor:
        out = model(x)[0].data
        assert out * t > 0.5, f"XOR input {x} should give an output near {t:+.0f}, got {out:+.3f}"
    again = mod.MLP([2, 4, 1], seed=1, out_act="tanh")
    assert [p.data for p in again.params()] != [p.data for p in model.params()], "(sanity) training must have changed the parameters"

    # a line: y = 2x + 1 with one linear neuron should recover w = 2 and b = 1
    lin = mod.MLP([1, 1], seed=0, act="linear")
    xs = [-2.0, -1.0, 0.0, 1.0, 2.0]
    mod.train(lin.params(), lambda: mod.mse_loss([lin([x])[0] for x in xs], [2 * x + 1 for x in xs]), 300, 0.05)
    w_, b_ = lin.params()
    assert abs(w_.data - 2.0) < 1e-6 and abs(b_.data - 1.0) < 1e-6, f"fitting y = 2x + 1 should recover w = 2, b = 1; got w = {w_.data:.6f}, b = {b_.data:.6f}"
    return f"XOR: loss {losses[0]:.3f} -> {losses[-1]:.4f} in 200 steps; line fit: w = {w_.data:.4f}, b = {b_.data:.4f}"


# =============================================================================
# Milestone 5: softmax and cross-entropy
# =============================================================================
def m5():
    zs = [Value(1.0), Value(2.0), Value(3.0)]
    lse = mod.logsumexp(zs)
    want = math.log(math.exp(1) + math.exp(2) + math.exp(3))
    assert near(lse.data, want), f"logsumexp([1, 2, 3]) = {want:.6f}, got {lse.data}"
    lse.backward()
    sm = [math.exp(z) / (math.exp(1) + math.exp(2) + math.exp(3)) for z in (1, 2, 3)]
    assert rel_err([z.grad for z in zs], sm) < 1e-9, f"the gradient of logsumexp is the softmax: {[round(p, 6) for p in sm]}, got {[round(z.grad, 6) for z in zs]}"
    big = mod.logsumexp([Value(1000.0), Value(1000.0)])
    assert near(big.data, 1000.0 + math.log(2), 1e-12), f"logsumexp([1000, 1000]) = 1000 + ln 2 = {1000 + math.log(2):.4f}, got {big.data} (exp(1000) overflows: subtract the maximum first)"
    small = mod.logsumexp([Value(-1000.0), Value(-1001.0)])
    assert near(small.data, -1000.0 + math.log(1 + math.exp(-1)), 1e-12), f"logsumexp([-1000, -1001]) = {-1000 + math.log(1 + math.exp(-1)):.6f}, got {small.data}"

    p = mod.softmax([Value(0.0), Value(0.0), Value(0.0)])
    assert all(near(q.data, 1 / 3) for q in p), "softmax of equal logits is uniform"
    p = mod.softmax([Value(1.0), Value(2.0), Value(3.0)])
    assert rel_err([q.data for q in p], sm) < 1e-9 and near(sum(q.data for q in p), 1.0), f"softmax([1,2,3]) = {[round(x, 4) for x in sm]}, got {[round(q.data, 4) for q in p]}"
    p = mod.softmax([Value(1000.0), Value(1001.0)])
    want = [1 / (1 + math.e), math.e / (1 + math.e)]
    assert rel_err([q.data for q in p], want) < 1e-9, f"softmax([1000, 1001]) = {[round(w, 4) for w in want]} (the naive formula overflows to nan); got {[q.data for q in p]}"
    p = mod.softmax([Value(5.0), Value(-5.0)])
    assert 0 < p[1].data < 1e-4 and near(p[0].data + p[1].data, 1.0), "softmax([5, -5]) has a tiny but positive second entry"

    ce = mod.cross_entropy([Value(0.0), Value(0.0), Value(0.0)], 1)
    assert near(ce.data, math.log(3)), f"three equal logits give probability 1/3, so loss ln 3 = {math.log(3):.4f}; got {ce.data}"
    zs = [Value(1.0), Value(2.0), Value(3.0)]
    ce = mod.cross_entropy(zs, 2)
    assert near(ce.data, -math.log(sm[2])), f"cross_entropy([1,2,3], 2) = -ln(0.6652) = {-math.log(sm[2]):.4f}; got {ce.data}"
    ce.backward()
    want = [sm[0], sm[1], sm[2] - 1.0]
    assert rel_err([z.grad for z in zs], want) < 1e-9, (f"the gradient of softmax cross-entropy is p - one_hot = {[round(w, 4) for w in want]}; "
                                                         f"got {[round(z.grad, 4) for z in zs]}")
    assert near(sum(z.grad for z in zs), 0.0, 1e-9), "the gradients of the logits sum to 0 (probabilities add to 1, one-hot adds to 1)"
    sure = mod.cross_entropy([Value(1000.0), Value(0.0)], 0)
    assert near(sure.data, 0.0, 1e-9), f"a confident correct prediction has loss near 0, got {sure.data}"
    wrong = mod.cross_entropy([Value(1000.0), Value(0.0)], 1)
    assert near(wrong.data, 1000.0, 1e-9), f"a confident wrong prediction at logit gap 1000 has loss 1000 (finite, not inf or nan); got {wrong.data}"
    assert raises(IndexError, mod.cross_entropy, [Value(0.0), Value(1.0)], 2), "a target outside the classes must raise IndexError"

    worst = 0.0
    for s in seeds(range(1, 31)):
        rng = random.Random(s)
        n = rng.randint(2, 6)
        scale = rng.choice([1.0, 5.0, 20.0])
        logits = [rng.uniform(-scale, scale) for _ in range(n)]
        tgt = rng.randrange(n)
        f = lambda vs: mod.cross_entropy(vs, tgt)
        auto = mod.autograd_grad(f, logits)
        # float-only reference: central differences on -log softmax
        def ref_loss(z):
            m = max(z)
            return math.log(sum(math.exp(a - m) for a in z)) + m - z[tgt]
        num = []
        for i in range(n):
            hi, lo = list(logits), list(logits)
            hi[i] += 1e-6
            lo[i] -= 1e-6
            num.append((ref_loss(hi) - ref_loss(lo)) / 2e-6)
        err = rel_err(auto, num)
        worst = max(worst, err)
        assert err < 1e-5, f"seed {s}: logits {[round(l, 3) for l in logits]}, target {tgt}: central differences give {[round(a, 5) for a in num]}, your engine gives {[round(a, 5) for a in auto]}"
        pr = mod.autograd_grad(lambda vs: mod.softmax(vs)[tgt], logits)
        pv = [q.data for q in mod.softmax([Value(l) for l in logits])]
        want = [pv[tgt] * ((1.0 if i == tgt else 0.0) - pv[i]) for i in range(n)]
        assert rel_err(pr, want) < 1e-8, f"seed {s}: d softmax_t / d z_i should be p_t ([t == i] - p_i); got {pr}, expected {want}"

    # scenario: three blobs in the plane, a small network, cross-entropy
    rng = random.Random(5)
    X, Y = [], []
    for c, (cx, cy) in enumerate([(-2.0, 0.0), (2.0, 0.0), (0.0, 3.0)]):
        for _ in range(15):
            X.append([rng.gauss(cx, 0.8), rng.gauss(cy, 0.8)])
            Y.append(c)
    model = mod.MLP([2, 8, 3], seed=3)
    batch = lambda: sum((mod.cross_entropy(model(x), y) for x, y in zip(X, Y)), Value(0.0)) * (1.0 / len(X))
    losses = mod.train(model.params(), batch, 100, 0.3)
    acc = sum(max(range(3), key=lambda k: model(x)[k].data) == y for x, y in zip(X, Y)) / len(X)
    assert 0.3 < losses[0] < 2.0, f"the first loss of an untrained 3-class network should be near ln 3 = 1.10 (between 0.3 and 2); got {losses[0]:.3f}"
    assert losses[-1] < 0.15, f"after 100 steps the mean cross-entropy should be below 0.15; got {losses[-1]:.3f}"
    assert acc >= 0.95, f"accuracy on the 45 training points should be at least 95%; got {acc:.0%}"
    return f"three blobs: loss {losses[0]:.3f} -> {losses[-1]:.3f}, accuracy {acc:.0%}; worst gradient error on random logits {worst:.1e}"


MILESTONES = [
    (1, "Milestone 1: the Value class, forward only", m1),
    (2, "Milestone 2: the graph, topological order and backward()", m2),
    (3, "Milestone 3: more operations, checked against numerical gradients", m3),
    (4, "Milestone 4: gradient descent trains a network", m4),
    (5, "Milestone 5: softmax and cross-entropy", m5),
]

if __name__ == "__main__":
    t0 = time.time()
    print(f"Lab 2 checks against {target}.py\n")
    for n, name, fn in MILESTONES:
        check(n, name, fn)
    print(f"\n{sum(results)}/{len(results)} milestones passing  ({time.time() - t0:.1f} s)")
    sys.exit(0 if all(results) else 1)
