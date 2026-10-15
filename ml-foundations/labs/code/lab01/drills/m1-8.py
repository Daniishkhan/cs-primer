# Drill: A0 Lab 1, milestone 1 of 5: vectors (step 8 of 8)
# Everything else in this file is already written. Fill in:
#     project
# Check it with: python3 check.py 1

"""Lab 1: a small linear algebra library, in pure Python.

Vectors are lists of floats. Matrices are lists of rows, so A[i][j] is the entry in
row i, column j, and shapes are written (rows, cols) exactly as NumPy writes them.
Notation follows chapters 5 to 7 of the course: vectors x, y, w; matrices A, B; the
dot product is x . y; the transpose is A^T.

What is GIVEN: the constants and the helpers `shape`, `outer`, `default_start`, `close`,
`mat_close`, `_same_length` and `_fix_sign`. What YOU write:

    1  add, sub, scale, dot, norm, normalise, cosine, project
    2  identity, transpose, matvec, matmul
    3  gram_schmidt, qr
    4  rayleigh, power_iteration, pagerank
    5  covariance, top_k_eigen, pca, reconstruct

`python3 check.py` runs the milestones; the lab page explains each one.
"""
import math
import random

TOL = 1e-9          # default tolerance for "equal" in floating point
RANK_TOL = 1e-10    # a vector whose leftover length is below this fraction of its original is "dependent"


# =============================================================================
# GIVEN: helpers
# =============================================================================
def shape(A):
    """(rows, cols) of a matrix given as a list of rows. Ragged or empty input raises ValueError."""
    if not A or not A[0]:
        raise ValueError("a matrix needs at least one row and one column")
    cols = len(A[0])
    if any(len(row) != cols for row in A):
        raise ValueError("ragged matrix: rows have different lengths")
    return len(A), cols


def outer(x, y):
    """The outer product x y^T: a (len(x), len(y)) matrix with entry x[i] * y[j]."""
    return [[a * b for b in y] for a in x]


def default_start(n):
    """A fixed, reproducible starting vector. Random enough that it is not orthogonal to
    the answer by accident, deterministic so every run of the lab gives the same numbers."""
    rng = random.Random(12345)
    return [rng.uniform(-1.0, 1.0) for _ in range(n)]


def close(a, b, tol=TOL):
    """Are two floats equal up to tol (absolute, or relative for large values)?"""
    return abs(a - b) <= tol * max(1.0, abs(a), abs(b))


def mat_close(A, B, tol=TOL):
    """Are two matrices the same shape and equal entry by entry?"""
    return shape(A) == shape(B) and all(close(a, b, tol) for ra, rb in zip(A, B) for a, b in zip(ra, rb))


# =============================================================================
# Milestone 1: vectors
# =============================================================================
def _same_length(x, y):
    """GIVEN: raise ValueError if two vectors differ in length. Use it in add, sub, dot."""
    if len(x) != len(y):
        raise ValueError(f"length mismatch: {len(x)} vs {len(y)}")


def add(x, y):
    """x + y, entry by entry. Different lengths raise ValueError."""
    _same_length(x, y)
    return [a + b for a, b in zip(x, y)]


def sub(x, y):
    """x - y, entry by entry. Different lengths raise ValueError."""
    _same_length(x, y)
    return [a - b for a, b in zip(x, y)]


def scale(c, x):
    """c * x: every entry multiplied by the number c."""
    return [c * a for a in x]


def dot(x, y):
    """The dot product: the sum of x[i] * y[i]. Different lengths raise ValueError."""
    _same_length(x, y)
    return sum(a * b for a, b in zip(x, y))


def norm(x):
    """The Euclidean length sqrt(x . x).

    Must not overflow for entries like 3e200 (squaring them gives inf): divide by the
    largest absolute entry first, take the length, and multiply back.
    """
    m = max((abs(a) for a in x), default=0.0)
    if m == 0.0:
        return 0.0
    return m * math.sqrt(sum((a / m) ** 2 for a in x))


def normalise(x):
    """x scaled to length 1. The zero vector has no direction: raise ValueError."""
    n = norm(x)
    if n == 0.0:
        raise ValueError("cannot normalise the zero vector")
    return scale(1.0 / n, x)


def cosine(x, y):
    """cos(angle between x and y) = x . y / (|x| |y|). A zero vector raises ValueError."""
    _same_length(x, y)
    nx, ny = norm(x), norm(y)
    if nx == 0.0 or ny == 0.0:
        raise ValueError("cosine is undefined for the zero vector")
    c = dot(x, y) / (nx * ny)
    return max(-1.0, min(1.0, c))          # rounding can push 1.0 up to 1.0000000000000002


def project(x, w):
    """The projection of x onto the line through w: ((x . w) / (w . w)) w. Zero w raises ValueError."""
    raise NotImplementedError("TODO milestone 1: project")


# =============================================================================
# Milestone 2: matrices
# =============================================================================
def identity(n):
    """The (n, n) identity matrix: 1 on the diagonal, 0 elsewhere."""
    return [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]


def transpose(A):
    """A^T: the (cols, rows) matrix whose entry (j, i) is A[i][j]."""
    rows, cols = shape(A)
    return [[A[i][j] for i in range(rows)] for j in range(cols)]


def matvec(A, x):
    """A x for a (m, n) matrix and a length-n vector: a length-m vector, each entry a row . x."""
    rows, cols = shape(A)
    if cols != len(x):
        raise ValueError(f"cannot multiply {(rows, cols)} by a vector of length {len(x)}: "
                         f"inner dimensions {cols} and {len(x)} differ")
    return [dot(row, x) for row in A]


def matmul(A, B):
    """A B for (m, n) and (n, p): the (m, p) matrix with entry (i, j) = row i of A . column j of B.

    Mismatched inner dimensions raise ValueError whose message shows both shapes.
    """
    m, n = shape(A)
    n2, p = shape(B)
    if n != n2:
        raise ValueError(f"cannot multiply {(m, n)} by {(n2, p)}: inner dimensions {n} and {n2} differ")
    Bt = transpose(B)                      # rows of B^T are columns of B
    return [[dot(row, col) for col in Bt] for row in A]


# =============================================================================
# Milestone 3: Gram-Schmidt and QR
# =============================================================================
def gram_schmidt(vectors, tol=RANK_TOL):
    """An orthonormal list spanning the same space as `vectors` (modified Gram-Schmidt).

    For each vector v in turn: subtract its projection onto every basis vector found so
    far, ONE AT A TIME, updating v after each subtraction. If what is left is shorter than
    tol times the original length, v was (numerically) dependent on the earlier ones: skip
    it. Otherwise normalise it and append it to the basis.
    """
    basis = []
    for v in vectors:
        original = norm(v)
        if original == 0.0:
            continue
        r = list(v)
        for q in basis:
            r = sub(r, scale(dot(r, q), q))      # uses the UPDATED r: this is the 'modified' part
        if norm(r) <= tol * original:
            continue
        basis.append(normalise(r))
    return basis


def qr(A):
    """The QR factorisation of a (m, n) matrix with m >= n and independent columns.

    Returns (Q, R): Q is (m, n) with orthonormal columns, R is (n, n) upper triangular,
    and Q R = A. Dependent columns raise ValueError.
    """
    m, n = shape(A)
    cols = transpose(A)
    Q_cols = gram_schmidt(cols)
    if len(Q_cols) < n:
        raise ValueError(f"columns are dependent: rank {len(Q_cols)} < {n}")
    # R[i][j] = q_i . a_j for i <= j, and 0 below the diagonal
    R = [[dot(Q_cols[i], cols[j]) if i <= j else 0.0 for j in range(n)] for i in range(n)]
    return transpose(Q_cols), R


# =============================================================================
# Milestone 4: power iteration and PageRank
# =============================================================================
def rayleigh(A, v):
    """The Rayleigh quotient v . (A v) / (v . v): the best single-number guess for an eigenvalue."""
    return dot(v, matvec(A, v)) / dot(v, v)


def _fix_sign(v):
    """GIVEN: flip v if needed so that its largest-magnitude entry is positive (eigenvectors have no sign)."""
    big = max(range(len(v)), key=lambda i: abs(v[i]))
    return scale(-1.0, v) if v[big] < 0 else v


def power_iteration(A, v0=None, tol=1e-10, max_iter=10_000):
    """The dominant eigenpair of a square matrix by repeated multiplication.

    Start from v0 (default_start(n) if None), normalised. Repeat: w = A v; v = w / |w|.
    Stop when the residual |A v - lam v| is below tol * max(1, |lam|), with lam the Rayleigh
    quotient of v. Returns (lam, v, iterations), v of length 1 with its largest entry positive.

    - If A v is the zero vector, v lies in the null space: return (0.0, v, iterations).
    - If it has not converged after max_iter steps (two eigenvalues of equal size, say),
      raise RuntimeError.
    - A non-square A raises ValueError.
    """
    n, cols = shape(A)
    if n != cols:
        raise ValueError(f"power iteration needs a square matrix, got {(n, cols)}")
    v = normalise(list(v0) if v0 is not None else default_start(n))
    for it in range(1, max_iter + 1):
        w = matvec(A, v)
        nw = norm(w)
        if nw == 0.0:
            return 0.0, _fix_sign(v), it
        lam = dot(v, w)                                   # v has length 1, so this is the Rayleigh quotient
        residual = norm(sub(w, scale(lam, v)))
        if residual <= tol * max(1.0, abs(lam)):
            return lam, _fix_sign(v), it
        v = scale(1.0 / nw, w)
    raise RuntimeError(f"power iteration did not converge in {max_iter} iterations")


def pagerank(links, damping=0.85):
    """PageRank scores (summing to 1) for a web graph.

    links[i] is the list of pages that page i links to. A page with no links is a dead end
    and is treated as linking to every page. Build the column-stochastic matrix M with
    M[j][i] = 1/len(links[i]) for each link i -> j, form the Google matrix
    G = damping * M + (1 - damping)/n (every entry), and return its dominant eigenvector
    rescaled to sum to 1, using power_iteration.
    """
    n = len(links)
    M = [[0.0] * n for _ in range(n)]
    for i, outs in enumerate(links):
        targets = list(outs) if outs else list(range(n))   # dead end: spread evenly
        for j in targets:
            M[j][i] += 1.0 / len(targets)
    G = [[damping * M[j][i] + (1.0 - damping) / n for i in range(n)] for j in range(n)]
    lam, v, _ = power_iteration(G)
    total = sum(v)
    return [x / total for x in v]


# =============================================================================
# Milestone 5: eigenpairs by deflation, and PCA
# =============================================================================
def covariance(X):
    """The sample covariance of data X, shape (n, d), one row per sample: a (d, d) matrix.

    Centre each column on its mean, then C = (X_c^T X_c) / (n - 1). Fewer than two rows raise ValueError.
    """
    n, d = shape(X)
    if n < 2:
        raise ValueError("covariance needs at least two samples")
    means = [sum(X[i][j] for i in range(n)) / n for j in range(d)]
    Xc = [[X[i][j] - means[j] for j in range(d)] for i in range(n)]
    S = matmul(transpose(Xc), Xc)
    return [[s / (n - 1) for s in row] for row in S]


def top_k_eigen(A, k):
    """The k largest eigenpairs [(lam, v), ...] of a symmetric matrix, biggest first, by deflation.

    Find the dominant pair with power_iteration, then subtract lam v v^T from the matrix so
    that eigenvalue is removed, and repeat on what is left.
    """
    n, _ = shape(A)
    if not 1 <= k <= n:
        raise ValueError(f"k must be between 1 and {n}")
    pairs = []
    B = [row[:] for row in A]
    for _ in range(k):
        lam, v, _ = power_iteration(B)
        pairs.append((lam, v))
        B = [[b - lam * o for b, o in zip(rb, ro)] for rb, ro in zip(B, outer(v, v))]
    return pairs


def pca(X, k):
    """Principal components of data X (n, d): returns (mean, components, variances).

    mean is the length-d column mean; components is a list of k orthonormal length-d vectors;
    variances is the list of the k largest eigenvalues of the covariance, biggest first.
    """
    n, d = shape(X)
    mean = [sum(X[i][j] for i in range(n)) / n for j in range(d)]
    pairs = top_k_eigen(covariance(X), k)
    return mean, [v for _, v in pairs], [lam for lam, _ in pairs]


def reconstruct(X, mean, components):
    """Project every row of X onto the components and map back: the best rank-k picture of X.

    For each row x: centre it, take the coefficient c_j = (x - mean) . components[j] for each
    component, and rebuild  mean + sum_j c_j components[j]. Returns a matrix shaped like X.
    """
    out = []
    for x in X:
        xc = sub(x, mean)
        r = list(mean)
        for q in components:
            r = add(r, scale(dot(xc, q), q))
        out.append(r)
    return out
