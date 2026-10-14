"""Self-check for Lab 1: A Small Linear Algebra Library.

    python3 check.py                  # checks your starter.py
    python3 check.py solution         # checks the reference solution
    python3 check.py solution 4       # only milestone 4
    python3 check.py solution 4 7     # milestone 4, replaying ONLY seed 7

Everything is deterministic: hand-computed values first, then seeded random inputs
(a failure prints its seed so you can replay it), then a scenario. There is no NumPy
here; the oracles below are written independently of your code, in plain loops.
The whole check finishes in a few seconds.
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


def vec_near(x, y, tol=1e-9):
    return len(x) == len(y) and all(near(a, b, tol) for a, b in zip(x, y))


def mat_near(A, B, tol=1e-9):
    return len(A) == len(B) and all(vec_near(r, s, tol) for r, s in zip(A, B))


def fmt(v):
    """Compact printing of a vector or matrix for failure messages."""
    if isinstance(v, (list, tuple)) and v and isinstance(v[0], (list, tuple)):
        return "[" + ", ".join(fmt(r) for r in v) + "]"
    if isinstance(v, (list, tuple)):
        return "[" + ", ".join(f"{x:.6g}" for x in v) + "]"
    return f"{v:.6g}"


def rand_vec(rng, n, lo=-3.0, hi=3.0):
    return [rng.uniform(lo, hi) for _ in range(n)]


def rand_mat(rng, m, n, lo=-3.0, hi=3.0):
    return [[rng.uniform(lo, hi) for _ in range(n)] for _ in range(m)]


# Independent oracles, deliberately plain loops with different structure from the solution.
def o_matmul(A, B):
    out = [[0.0] * len(B[0]) for _ in A]
    for i in range(len(A)):
        for k in range(len(B)):
            for j in range(len(B[0])):
                out[i][j] += A[i][k] * B[k][j]
    return out


def o_dot(x, y):
    t = 0.0
    for i in range(len(x)):
        t += x[i] * y[i]
    return t


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


# =============================================================================
# Milestone 1: vectors
# =============================================================================
def m1():
    assert mod.add([1, 2, 3], [10, 20, 30]) == [11, 22, 33], f"add: expected [11, 22, 33], got {mod.add([1, 2, 3], [10, 20, 30])}"
    assert mod.sub([5, 5], [2, 7]) == [3, -2], "sub([5, 5], [2, 7]) should be [3, -2]"
    assert mod.scale(-2, [1, -1, 0.5]) == [-2, 2, -1.0], "scale(-2, [1, -1, 0.5]) should be [-2, 2, -1.0]"
    assert mod.dot([1, 2, 3], [4, -5, 6]) == 12, f"dot([1,2,3],[4,-5,6]) = 4 - 10 + 18 = 12, got {mod.dot([1, 2, 3], [4, -5, 6])}"
    assert near(mod.norm([3, 4]), 5.0), f"norm([3, 4]) should be 5, got {mod.norm([3, 4])}"
    assert mod.norm([0, 0, 0]) == 0.0, "norm of the zero vector is 0.0 (and must not divide by zero)"
    assert near(mod.norm([1] * 100), 10.0), "norm of 100 ones is 10"
    for fn, args in [(mod.add, ([1, 2], [1, 2, 3])), (mod.sub, ([1], [1, 2])), (mod.dot, ([1, 2], [1]))]:
        assert raises(ValueError, fn, *args), f"{fn.__name__} on vectors of length {len(args[0])} and {len(args[1])} must raise ValueError (the shapes disagree)"

    n = mod.normalise([3, 0, 4])
    assert vec_near(n, [0.6, 0.0, 0.8]), f"normalise([3, 0, 4]) should be [0.6, 0, 0.8], got {fmt(n)}"
    assert raises(ValueError, mod.normalise, [0, 0]), "normalise of the zero vector has no direction: raise ValueError"

    assert near(mod.cosine([1, 0], [0, 5]), 0.0), "perpendicular vectors have cosine 0"
    assert near(mod.cosine([1, 2], [2, 4]), 1.0), "parallel vectors have cosine 1, whatever their lengths"
    assert near(mod.cosine([1, 2], [-3, -6]), -1.0), "opposite vectors have cosine -1"
    assert near(mod.cosine([1, 1], [1, 0]), math.sqrt(0.5)), "the angle between (1,1) and (1,0) is 45 degrees: cosine 0.7071"
    assert -1.0 <= mod.cosine([0.1, 0.2, 0.3], [0.1, 0.2, 0.3]) <= 1.0, \
        "cosine of a vector with itself must be exactly within [-1, 1]; rounding can give 1.0000000000000002, so clamp it"
    assert raises(ValueError, mod.cosine, [0, 0], [1, 2]), "cosine with a zero vector is undefined: raise ValueError"

    p = mod.project([3, 4], [1, 0])
    assert vec_near(p, [3.0, 0.0]), f"project([3, 4], [1, 0]) should be [3, 0], got {fmt(p)}"
    p = mod.project([2, 2], [3, 0])
    assert vec_near(p, [2.0, 0.0]), f"projection must not depend on the length of w: project([2,2],[3,0]) should be [2, 0], got {fmt(p)}"
    assert vec_near(mod.project([1, 2, 3], [1, 2, 3]), [1, 2, 3]), "projecting x onto itself gives x"
    assert raises(ValueError, mod.project, [1, 2], [0, 0]), "projecting onto the zero vector: raise ValueError"

    # numerical safety: squaring 3e200 overflows to inf, so a naive norm returns inf
    big = mod.norm([3e200, 4e200])
    assert math.isfinite(big) and near(big, 5e200, 1e-12), (f"norm([3e200, 4e200]) should be 5e200, got {big}. "
                                                            "Squaring 3e200 overflows: divide by the largest |entry| first, then multiply back")
    tiny = mod.norm([3e-200, 4e-200])
    assert near(tiny / 1e-200, 5.0, 1e-12), f"norm([3e-200, 4e-200]) should be 5e-200 (naive squaring underflows to 0), got {tiny}"

    for s in seeds(range(1, 41)):
        rng = random.Random(s)
        n = rng.randint(1, 12)
        x, y, z = rand_vec(rng, n), rand_vec(rng, n), rand_vec(rng, n)
        c = rng.uniform(-4, 4)
        assert near(mod.dot(x, y), o_dot(x, y), 1e-12), f"seed {s}: dot disagrees with a plain loop"
        assert near(mod.dot(x, y), mod.dot(y, x), 1e-12), f"seed {s}: the dot product must be symmetric"
        assert near(mod.dot(x, mod.add(y, z)), mod.dot(x, y) + mod.dot(x, z), 1e-9), f"seed {s}: dot must distribute over addition"
        assert near(mod.dot(mod.scale(c, x), y), c * mod.dot(x, y), 1e-9), f"seed {s}: dot must pull out a scalar"
        assert near(mod.norm(x) ** 2, mod.dot(x, x), 1e-9), f"seed {s}: |x|^2 must equal x . x"
        assert near(mod.norm(mod.scale(c, x)), abs(c) * mod.norm(x), 1e-9), f"seed {s}: |c x| must equal |c| |x|"
        assert mod.norm(mod.add(x, y)) <= mod.norm(x) + mod.norm(y) + 1e-9, f"seed {s}: the triangle inequality failed"
        assert abs(mod.dot(x, y)) <= mod.norm(x) * mod.norm(y) + 1e-9, f"seed {s}: Cauchy-Schwarz failed, so dot or norm is wrong"
        assert near(mod.norm(mod.normalise(x)), 1.0), f"seed {s}: a normalised vector has length 1"
        assert near(mod.cosine(mod.scale(abs(c) + 0.1, x), y), mod.cosine(x, y), 1e-9), f"seed {s}: cosine must ignore the length of its inputs"
        if mod.norm(y) > 1e-3:
            p = mod.project(x, y)
            r = mod.sub(x, p)
            assert abs(mod.dot(r, y)) <= 1e-9 * (1 + mod.norm(x) * mod.norm(y)), \
                f"seed {s}: x minus its projection must be perpendicular to w; got r . w = {mod.dot(r, y):.3g}"
            assert mod.norm(p) <= mod.norm(x) + 1e-9, f"seed {s}: a projection is never longer than the original"
    return ""


# =============================================================================
# Milestone 2: matrices
# =============================================================================
def m2():
    I3 = mod.identity(3)
    assert I3 == [[1, 0, 0], [0, 1, 0], [0, 0, 1]], f"identity(3) should have ones on the diagonal, got {fmt(I3)}"
    assert mod.shape(mod.identity(1)) == (1, 1), "identity(1) is [[1.0]]"

    A = [[1, 2, 3], [4, 5, 6]]
    At = mod.transpose(A)
    assert At == [[1, 4], [2, 5], [3, 6]], f"transpose of a (2, 3) matrix must be (3, 2): expected [[1,4],[2,5],[3,6]], got {fmt(At)}"
    assert mod.transpose([[7, 8, 9]]) == [[7], [8], [9]], "a row vector (1, 3) transposes to a column (3, 1)"
    assert mod.transpose(mod.transpose(A)) == A, "transposing twice gives back the original"
    A_before = [r[:] for r in A]
    mod.transpose(A)
    assert A == A_before, "transpose must not modify its input"

    assert mod.matvec([[1, 2], [3, 4]], [1, 1]) == [3, 7], "matvec([[1,2],[3,4]], [1,1]) = [3, 7]"
    assert mod.matvec([[0, -1], [1, 0]], [1, 0]) == [0, 1], "the matrix [[0,-1],[1,0]] rotates (1, 0) by 90 degrees to (0, 1)"
    assert raises(ValueError, mod.matvec, [[1, 2], [3, 4]], [1, 2, 3]), "matvec with a mismatched vector must raise ValueError"

    B = [[1, 2], [3, 4]]
    C = [[0, 1], [1, 0]]
    assert mod.matmul(B, C) == [[2, 1], [4, 3]], f"B C swaps the columns of B: expected [[2,1],[4,3]], got {fmt(mod.matmul(B, C))}"
    assert mod.matmul(C, B) == [[3, 4], [1, 2]], f"C B swaps the rows of B: expected [[3,4],[1,2]], got {fmt(mod.matmul(C, B))}"
    assert mod.matmul(B, C) != mod.matmul(C, B), "matrix multiplication is not commutative: B C and C B differ here"
    got = mod.matmul([[1, 2, 3], [4, 5, 6]], [[7, 8], [9, 10], [11, 12]])
    assert got == [[58, 64], [139, 154]], f"(2,3) times (3,2) should be [[58,64],[139,154]], got {fmt(got)}"
    assert mod.shape(mod.matmul([[1, 2, 3]], [[1], [2], [3]])) == (1, 1) and mod.matmul([[1, 2, 3]], [[1], [2], [3]]) == [[14]], \
        "(1,3) times (3,1) is (1,1): [[14]]"
    assert mod.matmul([[1], [2], [3]], [[1, 2, 3]]) == [[1, 2, 3], [2, 4, 6], [3, 6, 9]], "(3,1) times (1,3) is the outer product, shape (3,3)"
    try:
        mod.matmul([[1, 2, 3], [4, 5, 6]], [[1, 2], [3, 4]])
    except ValueError as e:
        msg = str(e)
        assert "(2, 3)" in msg and "(2, 2)" in msg, (f"the error for a shape mismatch must show both shapes, e.g. "
                                                      f"'cannot multiply (2, 3) by (2, 2): ...'; got {msg!r}")
    else:
        raise AssertionError("matmul of (2, 3) by (2, 2) must raise ValueError: the inner dimensions 3 and 2 differ")
    assert raises(ValueError, mod.matmul, [[1, 2], [3]], [[1], [2]]), "a ragged matrix is not a matrix: raise ValueError"

    for s in seeds(range(1, 31)):
        rng = random.Random(s)
        m, n, p, q = (rng.randint(1, 6) for _ in range(4))
        A, B, C = rand_mat(rng, m, n), rand_mat(rng, n, p), rand_mat(rng, p, q)
        x = rand_vec(rng, n)
        AB = mod.matmul(A, B)
        assert mod.shape(AB) == (m, p), f"seed {s}: ({m},{n}) times ({n},{p}) must be ({m},{p}), got {mod.shape(AB)}"
        assert mat_near(AB, o_matmul(A, B), 1e-12), f"seed {s}: matmul disagrees with the triple loop"
        assert mat_near(mod.matmul(AB, C), mod.matmul(A, mod.matmul(B, C)), 1e-9), f"seed {s}: matrix multiplication must be associative"
        assert mat_near(mod.matmul(mod.identity(m), A), A) and mat_near(mod.matmul(A, mod.identity(n)), A), \
            f"seed {s}: multiplying by the identity must change nothing"
        assert mat_near(mod.transpose(AB), mod.matmul(mod.transpose(B), mod.transpose(A)), 1e-9), \
            f"seed {s}: (A B)^T must equal B^T A^T (note the reversed order)"
        col = [[v] for v in x]
        assert vec_near(mod.matvec(A, x), [r[0] for r in mod.matmul(A, col)], 1e-12), f"seed {s}: matvec must agree with matmul on a column"
        # linearity: A (c x + y) = c A x + A y, the defining property of a linear map
        y, c = rand_vec(rng, n), rng.uniform(-2, 2)
        lhs = mod.matvec(A, mod.add(mod.scale(c, x), y))
        rhs = mod.add(mod.scale(c, mod.matvec(A, x)), mod.matvec(A, y))
        assert vec_near(lhs, rhs, 1e-9), f"seed {s}: a matrix must act linearly: A(cx + y) = cAx + Ay"
        # composing transformations: (A B) v = A (B v)
        v = rand_vec(rng, p)
        assert vec_near(mod.matvec(AB, v), mod.matvec(A, mod.matvec(B, v)), 1e-9), f"seed {s}: (A B) v must equal A (B v)"
    # chapter 6's point: the order of multiplication sets the cost, the answer is the same
    rng = random.Random(0)
    A, B, v = rand_mat(rng, 20, 20), rand_mat(rng, 20, 20), rand_vec(rng, 20)
    left = mod.matvec(mod.matmul(A, B), v)
    right = mod.matvec(A, mod.matvec(B, v))
    assert vec_near(left, right, 1e-9), "(A B) v and A (B v) must agree; the second needs 2 * 20 * 20 multiplies instead of 20^3 + 20^2"
    return ""


# =============================================================================
# Milestone 3: Gram-Schmidt and QR
# =============================================================================
def orthonormal(vs, tol=1e-9):
    for i, a in enumerate(vs):
        for j, b in enumerate(vs):
            want = 1.0 if i == j else 0.0
            if abs(o_dot(a, b) - want) > tol:
                return False, (i, j, o_dot(a, b))
    return True, None


def span_residual(basis, v):
    """How far v is from the span of an orthonormal basis (0 if inside)."""
    r = list(v)
    for q in basis:
        c = o_dot(r, q)
        r = [a - c * b for a, b in zip(r, q)]
    return math.sqrt(o_dot(r, r))


def m3():
    basis = mod.gram_schmidt([[3, 0], [1, 2]])
    assert len(basis) == 2, f"two independent vectors in 2-D give two basis vectors, got {len(basis)}"
    assert vec_near(basis[0], [1.0, 0.0]) and vec_near(basis[1], [0.0, 1.0]), \
        f"gram_schmidt([[3,0],[1,2]]) should give [[1,0],[0,1]], got {fmt(basis)}. The first vector is only normalised; the second loses its component along it"
    b = mod.gram_schmidt([[1, 1, 0], [1, 0, 1], [0, 1, 1]])
    ok, bad = orthonormal(b)
    assert len(b) == 3 and ok, f"the basis from [[1,1,0],[1,0,1],[0,1,1]] must be 3 orthonormal vectors; got {len(b)} vectors, first problem {bad}"
    assert vec_near(b[0], [1 / math.sqrt(2), 1 / math.sqrt(2), 0.0]), f"the first basis vector is the first input, normalised; got {fmt(b[0])}"
    assert vec_near(b[1], [1 / math.sqrt(6), -1 / math.sqrt(6), 2 / math.sqrt(6)]), \
        f"second vector: (1,0,1) minus its projection onto (1,1,0)/sqrt 2, normalised, is (1,-1,2)/sqrt 6; got {fmt(b[1])}"
    # dependent vectors are skipped, in any position
    d = mod.gram_schmidt([[1, 0, 0], [2, 0, 0], [0, 1, 0], [3, 4, 0], [0, 0, 1]])
    assert len(d) == 3, f"five vectors spanning only 3 dimensions should give 3 basis vectors (dependent ones skipped), got {len(d)}"
    assert mod.gram_schmidt([[0, 0], [1, 1]]) == [[1 / math.sqrt(2)] * 2] or vec_near(mod.gram_schmidt([[0, 0], [1, 1]])[0], [1 / math.sqrt(2)] * 2), \
        "a zero vector contributes nothing and is skipped"
    assert mod.gram_schmidt([]) == [], "no vectors, no basis"
    original = [[1.0, 2.0], [3.0, 1.0]]
    keep = [v[:] for v in original]
    mod.gram_schmidt(original)
    assert original == keep, "gram_schmidt must not modify its input vectors"

    for s in seeds(range(1, 31)):
        rng = random.Random(s)
        dim = rng.randint(2, 8)
        k = rng.randint(1, dim)
        vs = [rand_vec(rng, dim) for _ in range(k)]
        # add dependent vectors: random combinations of the independent ones
        extra = []
        for _ in range(rng.randint(0, 3)):
            cs = rand_vec(rng, k)
            extra.append([sum(c * v[i] for c, v in zip(cs, vs)) for i in range(dim)])
        allv = vs + extra
        rng.shuffle(allv)
        basis = mod.gram_schmidt(allv)
        ok, bad = orthonormal(basis, 1e-8)
        assert ok, f"seed {s}: basis vectors {bad[0]} and {bad[1]} have dot product {bad[2]:.3g}; an orthonormal basis has 1 on the diagonal and 0 elsewhere"
        assert len(basis) == k, f"seed {s}: {k} independent directions plus {len(extra)} combinations of them should give {k} basis vectors, got {len(basis)}"
        for v in allv:
            assert span_residual(basis, v) < 1e-8 * (1 + math.sqrt(o_dot(v, v))), f"seed {s}: the basis must span every input vector"

    # QR: Q has orthonormal columns, R is upper triangular, and Q R = A
    A = [[1, 1, 0], [1, 0, 1], [0, 1, 1], [1, 1, 1]]
    Q, R = mod.qr(A)
    assert mod.shape(Q) == (4, 3) and mod.shape(R) == (3, 3), f"for a (4, 3) matrix Q is (4, 3) and R is (3, 3); got {mod.shape(Q)} and {mod.shape(R)}"
    assert mat_near(o_matmul(Q, R), A, 1e-9), f"Q R must reproduce A; got {fmt(o_matmul(Q, R))}"
    assert all(abs(R[i][j]) < 1e-12 for i in range(3) for j in range(i)), f"R must be upper triangular (zeros below the diagonal); got {fmt(R)}"
    assert all(R[i][i] > 0 for i in range(3)), "the diagonal of R holds the leftover lengths, so it is positive"
    ok, bad = orthonormal([list(c) for c in zip(*Q)], 1e-9)
    assert ok, f"the columns of Q must be orthonormal; columns {bad[0]} and {bad[1]} have dot product {bad[2]:.3g}"
    assert raises(ValueError, mod.qr, [[1, 2], [2, 4], [3, 6]]), "dependent columns have no QR with a square R: raise ValueError"
    for s in seeds(range(1, 16)):
        rng = random.Random(100 + s)
        n = rng.randint(1, 5)
        m = n + rng.randint(0, 3)
        A = rand_mat(rng, m, n)
        Q, R = mod.qr(A)
        assert mat_near(o_matmul(Q, R), A, 1e-8), f"seed {s}: Q R != A for a ({m}, {n}) matrix"
        QtQ = o_matmul([list(c) for c in zip(*Q)], Q)
        assert mat_near(QtQ, mod.identity(n), 1e-8), f"seed {s}: Q^T Q must be the identity"

    # the classic trap: classical Gram-Schmidt loses orthogonality on nearly dependent vectors
    e = 1e-8
    lauchli = [[1, e, 0, 0], [1, 0, e, 0], [1, 0, 0, e]]
    B = mod.gram_schmidt(lauchli)
    assert len(B) == 3, f"three nearly parallel but independent vectors should give 3 basis vectors, got {len(B)}"
    worst = max(abs(o_dot(B[i], B[j])) for i in range(3) for j in range(i))
    assert worst < 1e-6, (f"on [1,e,0,0], [1,0,e,0], [1,0,0,e] with e = 1e-8 your basis has a dot product of {worst:.3g} between two "
                          "vectors that should be perpendicular. That is classical Gram-Schmidt (projecting the ORIGINAL vector onto each basis vector); "
                          "the modified version subtracts one projection at a time from the running remainder")
    return f"nearly dependent test: worst |q_i . q_j| = {worst:.1e} (classical Gram-Schmidt gives 0.5 here)"


# =============================================================================
# Milestone 4: power iteration and PageRank
# =============================================================================
def m4():
    A = [[4.0, 1.0], [2.0, 3.0]]
    assert near(mod.rayleigh(A, [1, 1]), 5.0), "(1, 1) is an eigenvector of [[4,1],[2,3]] with eigenvalue 5, so the Rayleigh quotient is 5"
    assert near(mod.rayleigh([[2, 0], [0, 3]], [1, 0]), 2.0), "the Rayleigh quotient of (1, 0) under diag(2, 3) is 2"
    assert near(mod.rayleigh([[2, 0], [0, 3]], [2, 0]), 2.0), "the Rayleigh quotient must not depend on the length of v (divide by v . v)"

    lam, v, iters = mod.power_iteration(A)
    r = 1 / math.sqrt(2)
    assert near(lam, 5.0, 1e-8), f"the dominant eigenvalue of [[4,1],[2,3]] is 5 (the other is 2), got {lam}"
    assert vec_near(v, [r, r], 1e-7), f"its eigenvector is (1, 1)/sqrt 2 = (0.7071, 0.7071) with the largest entry positive; got {fmt(v)}"
    assert 5 <= iters <= 60, f"error shrinks by 2/5 = 0.4 per step, so 1e-10 needs about 25 steps; you took {iters}"

    L = [[2.0, -1.0, 0.0], [-1.0, 2.0, -1.0], [0.0, -1.0, 2.0]]
    lam, v, _ = mod.power_iteration(L)
    assert near(lam, 2 + math.sqrt(2), 1e-8), f"eigenvalues of the 3x3 second-difference matrix are 2 +- sqrt 2 and 2; the biggest is 3.4142, got {lam}"
    assert vec_near(v, [-0.5, r, -0.5], 1e-6), f"expected (-1/2, 1/sqrt 2, -1/2): unit length, largest entry positive; got {fmt(v)}"

    lam, v, _ = mod.power_iteration([[-3.0, 0.0], [0.0, 1.0]])
    assert near(lam, -3.0, 1e-8) and vec_near(v, [1.0, 0.0], 1e-6), \
        f"the dominant eigenvalue is the one largest in size, even when negative: expected (-3, [1, 0]), got ({lam:.6g}, {fmt(v)}). A stopping rule based on the vector alone can see it flip sign each step"
    lam, v, it = mod.power_iteration([[0.0, 0.0], [0.0, 0.0]])
    assert lam == 0.0, f"the zero matrix has eigenvalue 0; got {lam}"
    lam, v, it = mod.power_iteration([[1.0, 0.0], [0.0, 0.0]], v0=[0.0, 1.0])
    assert near(lam, 0.0, 1e-12), (f"started in the null space (A v = 0) the answer is eigenvalue 0 with v unchanged; got {lam}. "
                                   "Do not divide by a zero length")
    lam, v, _ = mod.power_iteration(A, v0=[1.0, 0.0])
    assert near(lam, 5.0, 1e-8), "a different starting vector must reach the same eigenvalue"
    assert raises(ValueError, mod.power_iteration, [[1, 2, 3], [4, 5, 6]]), "power iteration needs a square matrix: raise ValueError"
    assert raises(RuntimeError, mod.power_iteration, [[0.0, 1.0], [1.0, 0.0]], [1.0, 0.3]), \
        "eigenvalues +1 and -1 have equal size, so the vector just swaps back and forth and never settles: raise RuntimeError after max_iter"
    assert raises(RuntimeError, mod.power_iteration, A, None, 1e-10, 3), "max_iter must be respected: 3 iterations cannot reach 1e-10"

    # convergence rate depends on the gap between the two biggest eigenvalues
    _, _, fast = mod.power_iteration([[2.0, 0.0], [0.0, 1.0]], v0=[1.0, 1.0])
    _, _, slow = mod.power_iteration([[2.0, 0.0], [0.0, 1.98]], v0=[1.0, 1.0])
    assert slow > 20 * fast, (f"the error shrinks by lambda_2/lambda_1 each step: 0.5 for diag(2, 1) but 0.99 for diag(2, 1.98), so the second "
                              f"should take many times longer. Took {fast} and {slow}")

    for s in seeds(range(1, 21)):
        rng = random.Random(s)
        n = rng.randint(2, 7)
        # a symmetric positive matrix with a known, well-separated dominant eigenvalue
        M = rand_mat(rng, n, n)
        S = [[(M[i][j] + M[j][i]) / 2 + (6.0 if i == j else 0.0) for j in range(n)] for i in range(n)]
        lam, v, _ = mod.power_iteration(S)
        Sv = [o_dot(row, v) for row in S]
        resid = max(abs(a - lam * b) for a, b in zip(Sv, v))
        assert resid < 1e-6, f"seed {s}: A v must equal lam v; the largest entry of A v - lam v is {resid:.3g}"
        assert near(math.sqrt(o_dot(v, v)), 1.0, 1e-9), f"seed {s}: the returned eigenvector must have length 1"
        # no estimate can exceed the Gershgorin bound: the largest absolute row sum
        bound = max(sum(abs(x) for x in row) for row in S)
        assert abs(lam) <= bound + 1e-9, f"seed {s}: |lambda| = {abs(lam):.4g} exceeds the largest absolute row sum {bound:.4g}, which no eigenvalue can"
        # the dominant eigenvalue bounds the Rayleigh quotient of every vector for a symmetric matrix
        for _ in range(5):
            w = rand_vec(rng, n)
            assert mod.rayleigh(S, w) <= lam + 1e-8, f"seed {s}: the Rayleigh quotient of any vector is at most the top eigenvalue for a symmetric matrix"

    # scenario: PageRank on a five-page web, dead end included
    links = [[1, 2], [2], [0], [2], []]           # page 3 links to 2; page 4 has no links (a dead end)
    pr = mod.pagerank(links)
    assert len(pr) == 5 and near(sum(pr), 1.0, 1e-9), f"PageRank scores form a probability distribution (sum 1); got sum {sum(pr):.6g}"
    assert all(x > 0 for x in pr), "damping gives every page a positive score"
    # independent check: iterate the random surfer directly and compare
    d, n = 0.85, 5
    p = [1.0 / n] * n
    for _ in range(500):
        q = [(1 - d) / n] * n
        for i, outs in enumerate(links):
            tg = outs if outs else list(range(n))
            for j in tg:
                q[j] += d * p[i] / len(tg)
        p = q
    assert vec_near(pr, p, 1e-6), f"PageRank should match the random-surfer iteration {fmt(p)}; got {fmt(pr)}"
    assert pr[2] == max(pr), "page 2 is linked to by pages 0, 1 and 3 and passes its rank to page 0: it should rank first"
    assert pr[3] < pr[0] < pr[2], "page 3 has no in-links, so it receives only the teleport and dead-end shares and ranks lowest; page 0 is fed by page 2"
    pr2 = mod.pagerank([[1], [0]])
    assert vec_near(pr2, [0.5, 0.5], 1e-8), "two pages linking to each other share rank equally"
    pr3 = mod.pagerank([[1], [2], [0]], damping=0.5)
    assert vec_near(pr3, [1 / 3] * 3, 1e-8), "a symmetric ring of three pages gives each 1/3, whatever the damping"
    return f"PageRank on the five-page web: {fmt(pr)}"


# =============================================================================
# Milestone 5: deflation and PCA
# =============================================================================
def gauss(rng):
    return rng.gauss(0.0, 1.0)


def make_data(seed, n=200, scales=(4.0, 1.5, 0.4)):
    """Data with known principal axes: independent coordinates with the given standard
    deviations, rotated by a fixed seeded orthogonal matrix, then shifted."""
    rng = random.Random(seed)
    d = len(scales)
    axes = []                   # a random orthonormal set, by plain Gram-Schmidt (independent of your code)
    while len(axes) < d:
        v = [rng.gauss(0, 1) for _ in range(d)]
        for q in axes:
            c = o_dot(v, q)
            v = [a - c * b for a, b in zip(v, q)]
        nv = math.sqrt(o_dot(v, v))
        if nv > 0.3:
            axes.append([a / nv for a in v])
    shift = [rng.uniform(-5, 5) for _ in range(d)]
    X = []
    for _ in range(n):
        z = [rng.gauss(0, 1) * sc for sc in scales]
        X.append([sum(z[j] * axes[j][i] for j in range(d)) + shift[i] for i in range(d)])
    return X, axes


def o_cov(X):
    n, d = len(X), len(X[0])
    mu = [sum(r[j] for r in X) / n for j in range(d)]
    return [[sum((r[i] - mu[i]) * (r[j] - mu[j]) for r in X) / (n - 1) for j in range(d)] for i in range(d)]


def m5():
    X = [[1, 2], [2, 4], [3, 6]]
    C = mod.covariance(X)
    assert mat_near(C, [[1.0, 2.0], [2.0, 4.0]]), (f"points on the line y = 2x: variance of x is 1, of y is 4, covariance 2 "
                                                    f"(dividing by n - 1 = 2); expected [[1,2],[2,4]], got {fmt(C)}")
    C = mod.covariance([[0, 0], [2, 0], [0, 2], [2, 2]])
    assert mat_near(C, [[4 / 3, 0.0], [0.0, 4 / 3]]), f"four corners of a square of side 2: variance 4/3 each, covariance 0; got {fmt(C)}"
    assert raises(ValueError, mod.covariance, [[1.0, 2.0]]), "one sample has no spread to estimate: raise ValueError"
    keep = [r[:] for r in X]
    mod.covariance(X)
    assert X == keep, "covariance must not modify the data (centre a copy)"

    # deflation on a matrix with known eigenvalues: [[2,1],[1,2]] has 3 (along (1,1)) and 1 (along (1,-1))
    pairs = mod.top_k_eigen([[2.0, 1.0], [1.0, 2.0]], 2)
    assert len(pairs) == 2, "top_k_eigen(A, 2) returns two eigenpairs"
    (l1, v1), (l2, v2) = pairs
    r = 1 / math.sqrt(2)
    assert near(l1, 3.0, 1e-7) and near(l2, 1.0, 1e-7), f"eigenvalues of [[2,1],[1,2]] are 3 and 1; got {l1:.6g} and {l2:.6g}"
    assert vec_near(v1, [r, r], 1e-6), f"top eigenvector is (1,1)/sqrt 2; got {fmt(v1)}"
    assert abs(abs(o_dot(v2, [r, -r])) - 1) < 1e-6, f"second eigenvector is +-(1,-1)/sqrt 2 (deflation removed the first); got {fmt(v2)}"
    A = [[2.0, 1.0], [1.0, 2.0]]
    mod.top_k_eigen(A, 2)
    assert A == [[2.0, 1.0], [1.0, 2.0]], "top_k_eigen must not modify its input matrix (deflate a copy)"
    assert raises(ValueError, mod.top_k_eigen, A, 3), "k larger than the matrix size: raise ValueError"
    D = [[5.0, 0, 0], [0, 3.0, 0], [0, 0, 1.0]]
    got = [lam for lam, _ in mod.top_k_eigen(D, 3)]
    assert vec_near(got, [5.0, 3.0, 1.0], 1e-7), f"a diagonal matrix has its diagonal as eigenvalues, biggest first: expected [5, 3, 1], got {fmt(got)}"

    # PCA on points along a line: all the variance is in one direction
    mean, comps, var = mod.pca(X, 1)
    assert vec_near(mean, [2.0, 4.0]), f"the mean of the three points is (2, 4); got {fmt(mean)}"
    assert vec_near(comps[0], [1 / math.sqrt(5), 2 / math.sqrt(5)], 1e-7), f"the first component is (1, 2)/sqrt 5; got {fmt(comps[0])}"
    assert near(var[0], 5.0, 1e-8), f"the variance along it is 1 + 4 = 5; got {var[0]:.6g}"
    mean, comps, var = mod.pca(X, 2)
    assert abs(var[1]) < 1e-8, f"the second direction carries no variance for exactly collinear points; got {var[1]:.3g}"

    for s in seeds(range(1, 9)):
        X, axes = make_data(s)
        mean, comps, var = mod.pca(X, 3)
        C = o_cov(X)
        trace = sum(C[i][i] for i in range(3))
        assert var[0] >= var[1] >= var[2] > 0, f"seed {s}: variances must come biggest first and be positive; got {fmt(var)}"
        assert near(sum(var), trace, 1e-6), f"seed {s}: the eigenvalues of a matrix add up to its trace: {trace:.6g}, but they sum to {sum(var):.6g}"
        ok, bad = orthonormal(comps, 1e-6)
        assert ok, f"seed {s}: components {bad[0]} and {bad[1]} have dot product {bad[2]:.3g}; they must be orthonormal"
        for lam, q in zip(var, comps):
            Cq = [o_dot(row, q) for row in C]
            assert max(abs(a - lam * b) for a, b in zip(Cq, q)) < 1e-5 * (1 + lam), f"seed {s}: each component must satisfy C q = lambda q"
        # the data was built with standard deviations 4, 1.5, 0.4: variances near 16, 2.25, 0.16 and the axes recovered
        assert abs(var[0] - 16) < 5 and abs(var[1] - 2.25) < 1.5, f"seed {s}: variances {fmt(var)} are far from the (16, 2.25, 0.16) the data was built with"
        assert abs(abs(o_dot(comps[0], axes[0])) - 1.0) < 0.02, f"seed {s}: the first component should point along the long axis of the cloud"
        # variance of the projected scores equals the eigenvalue
        for lam, q in zip(var, comps):
            scores = [o_dot(sub_row, q) for sub_row in [[a - m for a, m in zip(row, mean)] for row in X]]
            sv = sum(t * t for t in scores) / (len(X) - 1)
            assert near(sv, lam, 1e-5), f"seed {s}: the variance of the data projected on a component must equal its eigenvalue ({lam:.6g}), got {sv:.6g}"
        # reconstruction: error falls as components are added, and is zero with all of them
        errs = []
        for k in (1, 2, 3):
            m2_, c2, _ = mod.pca(X, k)
            Xh = mod.reconstruct(X, m2_, c2)
            assert len(Xh) == len(X) and len(Xh[0]) == 3, f"seed {s}: reconstruct must return a matrix shaped like X"
            errs.append(sum((a - b) ** 2 for r1, r2 in zip(X, Xh) for a, b in zip(r1, r2)) / (len(X) - 1))
        assert errs[0] > errs[1] > errs[2], f"seed {s}: reconstruction error must fall as k grows; got {fmt(errs)}"
        assert errs[2] < 1e-8, f"seed {s}: with k = d the reconstruction is exact; error {errs[2]:.3g}"
        # Eckart-Young for PCA: the error left at rank k is the sum of the discarded eigenvalues
        assert near(errs[0], var[1] + var[2], 1e-5) and near(errs[1], var[2], 1e-5), \
            f"seed {s}: the mean squared error after keeping k components equals the sum of the eigenvalues you dropped; expected {var[1] + var[2]:.6g} and {var[2]:.6g}, got {errs[0]:.6g} and {errs[1]:.6g}"
    X, _ = make_data(1)
    _, comps, var = mod.pca(X, 3)
    return f"seed 1: variances {', '.join(f'{v:.3f}' for v in var)} (built from 16, 2.25, 0.16 plus sampling noise)"


MILESTONES = [
    (1, "Milestone 1: vectors, dot product, norm, cosine, projection", m1),
    (2, "Milestone 2: matrices, transpose and matrix multiplication", m2),
    (3, "Milestone 3: Gram-Schmidt and QR", m3),
    (4, "Milestone 4: power iteration and PageRank", m4),
    (5, "Milestone 5: deflation and PCA", m5),
]

if __name__ == "__main__":
    t0 = time.time()
    print(f"Lab 1 checks against {target}.py\n")
    for n, name, fn in MILESTONES:
        check(n, name, fn)
    print(f"\n{sum(results)}/{len(results)} milestones passing  ({time.time() - t0:.1f} s)")
    sys.exit(0 if all(results) else 1)
