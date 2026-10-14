"""Self-check for Lab 3: k-means, PCA & Anomalies.

    python3 check.py                  # checks your starter.py
    python3 check.py solution         # checks the reference solution
    python3 check.py solution 3       # only milestone 3
    python3 check.py solution 3 2     # milestone 3, replaying ONLY the dataset of seed 2

Every dataset is synthetic and generated from a seeded random.Random, so every run gives identical
numbers and the whole check finishes in a few seconds. The oracles in this file are deliberately
independent of the functions you write: hand-worked values from chapters 10 to 12, a Jacobi
eigenvalue solver for PCA, the inertia of the true grouping for k-means, and properties the answer
must have (inertia never rises, components are orthonormal, scores come out between 0 and 1).
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
START = time.time()


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


def near_list(a, b, tol=1e-9):
    return len(a) == len(b) and all(near(x, y, tol) for x, y in zip(a, b))


def clone(M):
    return [list(r) for r in M]


def pair_auc(scores, kind, g):
    """AUC of the scores at separating anomaly kind g from the normal rows (kind 0)."""
    idx = [i for i in range(len(kind)) if kind[i] in (0, g)]
    return mod.auc([scores[i] for i in idx], [kind[i] == g for i in idx])


class Script:
    """A scripted stand-in for random.Random: hands back prepared numbers, and complains if you ask for more."""

    def __init__(self, ranges=(), randoms=(), midpoint=False):
        self.ranges, self.randoms, self.midpoint = list(ranges), list(randoms), midpoint
        self.calls = []

    def randrange(self, n):
        self.calls.append(("randrange", n))
        assert self.ranges, f"you called rng.randrange({n}) more times than the contract allows"
        return self.ranges.pop(0)

    def random(self):
        self.calls.append(("random",))
        assert self.randoms, "you called rng.random() more times than the contract allows"
        return self.randoms.pop(0)

    def uniform(self, lo, hi):
        self.calls.append(("uniform", lo, hi))
        assert self.midpoint, "unexpected rng.uniform call"
        return (lo + hi) / 2

    def gauss(self, mu, sd):
        raise AssertionError("unexpected rng.gauss call")


# =============================================================================
# Independent oracles
# =============================================================================
def jacobi_eigen(A, sweeps=60):
    """Eigenvalues (descending) and eigenvectors (rows) of a symmetric matrix by the Jacobi rotation method."""
    n = len(A)
    A = clone(A)
    V = [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
    for _ in range(sweeps):
        off = sum(A[i][j] ** 2 for i in range(n) for j in range(n) if i != j)
        if off < 1e-22:
            break
        for p in range(n - 1):
            for q in range(p + 1, n):
                if abs(A[p][q]) < 1e-300:
                    continue
                theta = (A[q][q] - A[p][p]) / (2 * A[p][q])
                t = (1 if theta >= 0 else -1) / (abs(theta) + math.sqrt(theta * theta + 1))
                c = 1 / math.sqrt(t * t + 1)
                s = t * c
                for k in range(n):
                    akp, akq = A[k][p], A[k][q]
                    A[k][p], A[k][q] = c * akp - s * akq, s * akp + c * akq
                for k in range(n):
                    apk, aqk = A[p][k], A[q][k]
                    A[p][k], A[q][k] = c * apk - s * aqk, s * apk + c * aqk
                for k in range(n):
                    vkp, vkq = V[k][p], V[k][q]
                    V[k][p], V[k][q] = c * vkp - s * vkq, s * vkp + c * vkq
    order = sorted(range(n), key=lambda i: -A[i][i])
    return [A[i][i] for i in order], [[V[k][i] for k in range(n)] for i in order]


def oracle_cov(X):
    n, p = len(X), len(X[0])
    mu = [sum(r[c] for r in X) / n for c in range(p)]
    return [[sum((r[a] - mu[a]) * (r[b] - mu[b]) for r in X) / (n - 1) for b in range(p)] for a in range(p)]


def oracle_silhouette(X, lab):
    n = len(X)
    D = [[math.dist(X[i], X[j]) for j in range(n)] for i in range(n)]
    total = 0.0
    for i in range(n):
        own = [j for j in range(n) if lab[j] == lab[i] and j != i]
        if not own:
            continue
        a = sum(D[i][j] for j in own) / len(own)
        b = min(sum(D[i][j] for j in range(n) if lab[j] == c) / sum(1 for j in range(n) if lab[j] == c)
                for c in set(lab) if c != lab[i])
        total += (b - a) / max(a, b)
    return total / n


def true_inertia(X, truth):
    k = max(truth) + 1
    cs = [[sum(x[c] for x, l in zip(X, truth) if l == j) / truth.count(j) for c in range(len(X[0]))] for j in range(k)]
    return sum(math.dist(x, cs[l]) ** 2 for x, l in zip(X, truth))


# =============================================================================
# Milestone 1: Lloyd's algorithm
# =============================================================================
def m1():
    assert near(mod.sq_dist([0, 0], [3, 4]), 25), f"sq_dist([0, 0], [3, 4]) should be 25 (squared, no square root); got {mod.sq_dist([0, 0], [3, 4])}"
    assert near(mod.sq_dist([1.5], [1.5]), 0), "sq_dist of a row with itself is 0"
    X = [[0.0], [1.0], [4.0], [5.0]]
    got = mod.assign(X, [[0.0], [5.0]])
    assert got == [0, 0, 1, 1], f"assign(X, [[0], [5]]) on rows 0, 1, 4, 5 should be [0, 0, 1, 1]; got {got}"
    got = mod.assign([[2.5]], [[5.0], [0.0]])
    assert got == [0], f"a row exactly halfway between two centres goes to the lower index (0); got {got}"
    got = mod.assign([[2.0], [4.0]], [[0.0], [5.0], [2.0]])
    assert got == [2, 1], f"rows 2 and 4 with centres 0, 5, 2 should go to centres 2 and 1; got {got} (the third centre is last in the list but the nearest to row 2)"
    cs = [[0.0], [5.0], [100.0]]
    keep = clone(cs)
    got = mod.update_centres(X, [0, 0, 1, 1], cs)
    assert cs == keep, "update_centres must not modify the centres it is given; build a new list"
    assert near_list([got[0][0], got[1][0]], [0.5, 4.5]), f"means of {{0, 1}} and {{4, 5}} are 0.5 and 4.5; got {got}"
    assert got[2] == [100.0], f"a centre that attracted no rows must stay where it was; got {got[2]}"
    xs = [[0.0, 0.0], [2.0, 4.0]]
    got = mod.update_centres(xs, [0, 0], [[9.0, 9.0]])
    assert near_list(got[0], [1.0, 2.0]), f"the mean of (0, 0) and (2, 4) is (1, 2); got {got[0]} (does it handle two columns?)"
    val = mod.inertia(X, [0, 0, 1, 1], [[0.5], [4.5]])
    assert near(val, 1.0), f"inertia of {{0, 1}} and {{4, 5}} around 0.5 and 4.5 is 4 x 0.25 = 1.0; got {val}"
    # a hand-worked run (the same one the lab page walks through)
    res = mod.lloyd(X, [[0.0], [1.0]])
    assert res.labels == [0, 0, 1, 1], f"lloyd from centres 0 and 1 should end with labels [0, 0, 1, 1]; got {res.labels}"
    assert near_list([res.centres[0][0], res.centres[1][0]], [0.5, 4.5]), f"final centres should be 0.5 and 4.5; got {res.centres}"
    assert near_list(res.history, [25.0, 4.2222222222222222, 1.0]), (
        f"history should be [25, 4.222, 1.0] (assign with the start centres, then after each update and re-assign); got {res.history}")
    assert res.n_iter == 2, f"two update rounds (the second confirms nothing moved); got n_iter = {res.n_iter}"
    assert near(res.inertia, 1.0), f"final inertia should be 1.0; got {res.inertia}"
    # max_iter is respected
    one = mod.lloyd(X, [[0.0], [1.0]], max_iter=1)
    assert one.n_iter == 1 and len(one.history) == 2, f"max_iter=1 means one update round; got n_iter {one.n_iter}, history {one.history}"
    # properties on real data
    worst = 0.0
    for seed in seeds((1, 2, 3)):
        X6, _ = mod.make_six_groups(seed)
        rng = random.Random(seed)
        start = clone(rng.sample(X6, 6))
        keep = clone(start)
        r = mod.lloyd(X6, start)
        assert start == keep, "lloyd must not modify the starting centres it is given (seed %d)" % seed
        for a, b in zip(r.history, r.history[1:]):
            assert b <= a + 1e-9, f"inertia went UP from {a:.4f} to {b:.4f} (seed {seed}): each assign and each update can only lower or keep it"
        assert mod.assign(X6, r.centres) == r.labels, f"at the end every row must be at its nearest centre (seed {seed})"
        again = mod.update_centres(X6, r.labels, r.centres)
        assert all(near_list(a, b, 1e-9) for a, b in zip(again, r.centres)), f"at the end every centre must be the mean of its rows (seed {seed})"
        assert near(r.inertia, mod.inertia(X6, r.labels, r.centres), 1e-9), f"result.inertia must equal inertia(X, labels, centres) (seed {seed})"
        assert near(r.inertia, r.history[-1], 1e-9) and r.n_iter < 100
        worst = max(worst, r.history[0] / r.inertia)
    return f"hand values, the 4-point walk-through, and 3 seeded runs: inertia never rose (a random start fell by up to {worst:.1f}x)"


# =============================================================================
# Milestone 2: k-means++ seeding, restarts, silhouette
# =============================================================================
def m2():
    X = [[0.0, 0.0], [1.0, 0.0], [10.0, 0.0], [11.0, 0.0]]
    # scripted draws: first centre = row 0; D^2 = [0, 1, 100, 121], total 222
    for r, want in [(0.5, 3), (0.4, 2), (0.0001, 1)]:
        s = Script(ranges=[0], randoms=[r])
        got = mod.kmeans_pp_init(X, 2, s)
        assert got == [X[0], X[want]], (f"with D^2 = [0, 1, 100, 121] (total 222) and random() = {r}, the draw is {r} x 222 = {r * 222:.2f}; "
                                       f"the first row whose running total exceeds it is row {want}. You returned {got}")
        assert s.calls == [("randrange", 4), ("random",)], f"expected exactly randrange(4) then one random(); got {s.calls}"
    s = Script(ranges=[0], randoms=[0.5, 0.75])
    got = mod.kmeans_pp_init(X, 3, s)
    assert got == [X[0], X[3], X[2]], (f"third centre: after centres at 0 and 11, D^2 = [0, 1, 1, 0] (total 2), draw 0.75 x 2 = 1.5, so row 2. "
                                       f"Remember D is the distance to the NEAREST centre so far. You returned {got}")
    got[0][0] = 99.0
    assert X[0] == [0.0, 0.0], "return copies of the rows, not the rows themselves"
    # a row that is already a centre can never be drawn again
    Z = [[0.0], [0.0], [0.0], [100.0]]
    for seed in seeds(range(25)):
        cs = mod.kmeans_pp_init(Z, 2, random.Random(seed))
        assert sorted(c[0] for c in cs) == [0.0, 100.0], f"rows at distance 0 from a centre must have probability 0; got centres {cs} (seed {seed})"
    # k-means++ spreads the starts out better than random rows
    X6, _ = mod.make_six_groups(1)
    cen = [[5.0 * (j // 2), 5.0 * (j % 2)] for j in range(6)]

    def hit(cs):
        return len({min(range(6), key=lambda j: math.dist(c, cen[j])) for c in cs})

    pp = [hit(mod.kmeans_pp_init(X6, 6, random.Random(s))) for s in range(40)]
    rnd = [hit(random.Random(s).sample(X6, 6)) for s in range(40)]
    mpp, mrnd = sum(pp) / 40, sum(rnd) / 40
    assert mpp > 4.8, (f"on six well-separated groups k-means++ starts should land in about 5.3 different groups on average "
                       f"(random rows manage {mrnd:.1f}); yours land in {mpp:.2f}. Is the probability proportional to D^2, not D or uniform?")
    # restarts
    for seed in seeds((1, 2, 3)):
        X6, truth = mod.make_six_groups(seed)
        oracle = true_inertia(X6, truth)
        best = mod.kmeans(X6, 6, 0, n_init=10)
        assert best.inertia <= 1.02 * oracle, (f"best of 10 restarts should reach the true grouping's inertia ({oracle:.1f}); got {best.inertia:.1f} "
                                               f"(seed {seed}). Keep the run with the LOWEST inertia")
        singles = [mod.kmeans(X6, 6, s, n_init=1).inertia for s in range(20)]
        assert max(singles) >= 1.5 * oracle, f"a single k-means++ run should sometimes land in a poor optimum (seed {seed}); is n_init being honoured?"
        for s in range(3):
            more, fewer = mod.kmeans(X6, 6, s, n_init=8).inertia, mod.kmeans(X6, 6, s, n_init=1).inertia
            assert more <= fewer + 1e-9, (f"with the same seed, 8 restarts must not be worse than 1: {more:.1f} vs {fewer:.1f}. "
                                          "One rng feeds all the restarts, in order, so the first restart is the same run")
        again = mod.kmeans(X6, 6, 0, n_init=10)
        assert again.labels == best.labels and again.inertia == best.inertia, "the same seed must give the same result"
    # silhouette: hand values
    S = [[0.0], [1.0], [10.0], [11.0]]
    a0, a1 = 1.0, 1.0
    want = ((10.5 - a0) / 10.5 + (9.5 - a1) / 9.5) / 2
    got = mod.silhouette(S, [0, 0, 1, 1])
    assert near(got, want, 1e-9), f"silhouette of two tight pairs far apart should be {want:.5f} (a = 1; b = 10.5, 9.5, 9.5, 10.5); got {got}"
    want = (0 + (5 - 1) / 5 + (6 - 1) / 6) / 3
    got = mod.silhouette([[0.0], [5.0], [6.0]], [0, 1, 1])
    assert near(got, want, 1e-9), f"a row alone in its cluster has s = 0; expected {want:.5f}, got {got}"
    assert mod.silhouette(S, [0, 0, 0, 0]) == 0.0, "with a single cluster the silhouette is 0.0"
    for seed in seeds((4, 5)):
        Xb, _ = mod.make_blobs(seed, [[0, 0], [5, 0], [2.5, 4]], n_per=30, sd=1.0)
        lab = mod.kmeans(Xb, 3, seed, 3).labels
        assert near(mod.silhouette(Xb, lab), oracle_silhouette(Xb, lab), 1e-9), f"silhouette disagrees with an independent computation (seed {seed})"
    # choose k
    Xb, _ = mod.make_blobs(7, [[0, 0], [6, 0], [3, 5]], n_per=50, sd=1.0)
    table = mod.sweep_k(Xb, [2, 3, 4, 5, 6], seed=0, n_init=5)
    assert [t[0] for t in table] == [2, 3, 4, 5, 6], "sweep_k returns one (k, inertia, silhouette) tuple per k, in order"
    inert = [t[1] for t in table]
    assert all(b <= a + 1e-9 for a, b in zip(inert, inert[1:])), f"inertia can only fall as k grows; got {[round(i, 1) for i in inert]}"
    best_k = max(table, key=lambda t: t[2])[0]
    assert best_k == 3, f"three planted blobs: the silhouette should peak at k = 3, got k = {best_k} ({[(k, round(s, 3)) for k, _, s in table]})"
    return ("scripted k-means++ draws, a 3rd-centre case, restarts that reach the true inertia on 3 seeds, silhouette vs an independent version\n"
            f"k-means++ starts hit {mpp:.1f} of 6 groups on average (random rows: {mrnd:.1f}); silhouette peaks at k = 3 on three blobs")


# =============================================================================
# Milestone 3: PCA by power iteration
# =============================================================================
def random_psd(rng, eigs):
    """A symmetric matrix with the given eigenvalues and random orthonormal eigenvectors (Gram-Schmidt)."""
    p = len(eigs)
    Q = []
    while len(Q) < p:
        v = [rng.gauss(0, 1) for _ in range(p)]
        for q in Q:
            d = sum(a * b for a, b in zip(v, q))
            v = [a - d * b for a, b in zip(v, q)]
        n = math.sqrt(sum(a * a for a in v))
        if n > 1e-3:
            Q.append([a / n for a in v])
    C = [[sum(eigs[k] * Q[k][i] * Q[k][j] for k in range(p)) for j in range(p)] for i in range(p)]
    return C, Q


def m3():
    X = [[1.0, 2.0], [3.0, 6.0], [5.0, 10.0]]
    got = mod.column_means(X)
    assert near_list(got, [3.0, 6.0]), f"column_means should be [3, 6]; got {got}"
    got = mod.covariance(X)
    assert all(near_list(a, b) for a, b in zip(got, [[4.0, 8.0], [8.0, 16.0]])), (
        f"covariance of x = 1, 3, 5 and y = 2, 6, 10 is [[4, 8], [8, 16]] (divide by n - 1 = 2); got {got}")
    X2 = clone(X)
    mod.covariance(X2)
    assert X2 == X, "covariance must not modify X"
    # power iteration, closed-form 2x2
    for C in ([[2.0, 1.0], [1.0, 2.0]], [[1.0, 0.0], [0.0, 4.0]], [[3.0, -1.0], [-1.0, 1.0]], [[5.0, 2.0], [2.0, 2.0]]):
        a, b, d = C[0][0], C[0][1], C[1][1]
        lam = (a + d) / 2 + math.sqrt(((a - d) / 2) ** 2 + b * b)
        v = [b, lam - a] if abs(b) > 1e-12 else ([1.0, 0.0] if a >= d else [0.0, 1.0])
        nv = math.hypot(*v)
        v = [x / nv for x in v]
        if v[max(range(2), key=lambda i: abs(v[i]))] < 0:
            v = [-x for x in v]
        gl, gv = mod.power_iteration(C, random.Random(0))
        assert near(gl, lam, 1e-9), f"dominant eigenvalue of {C} is {lam:.6f}; got {gl}"
        assert near_list(gv, v, 1e-6), (f"dominant eigenvector of {C} is {[round(x, 5) for x in v]} "
                                        f"(unit length, largest-magnitude entry positive); got {[round(x, 5) for x in gv]}")
    gl, gv = mod.power_iteration([[0.0, 0.0], [0.0, 0.0]], random.Random(1))
    assert gl == 0.0 and near(math.hypot(*gv), 1.0), f"for the zero matrix return (0.0, a unit vector); got {(gl, gv)}"
    # random PSD matrices with known eigen-structure
    for seed in seeds((1, 2, 3)):
        rng = random.Random(seed)
        eigs = [10.0, 5.0, 2.0, 1.0, 0.5]
        C, Q = random_psd(rng, eigs)
        lam, v = mod.power_iteration(C, random.Random(seed + 100))
        assert near(lam, 10.0, 1e-8), f"dominant eigenvalue should be 10; got {lam} (seed {seed})"
        assert abs(sum(a * b for a, b in zip(v, Q[0]))) > 1 - 1e-8, f"eigenvector does not match the true one (seed {seed}); did you normalise every step?"
        lam2, v2 = mod.power_iteration(C, random.Random(seed + 200))
        assert near_list(v, v2, 1e-6), f"the answer must not depend on the random start (seed {seed}): the sign rule makes it unique"
        D = mod.deflate(C, lam, v)
        assert near(mod.dot(v, mod.mat_vec(D, v)), 0.0, 1e-8), f"after deflation the old eigenvector has eigenvalue 0 (seed {seed})"
        l2, _ = mod.power_iteration(D, random.Random(seed))
        assert near(l2, 5.0, 1e-8), f"after deflating the top pair the dominant eigenvalue is 5; got {l2} (seed {seed})"
    D = mod.deflate([[2.0, 1.0], [1.0, 2.0]], 3.0, [math.sqrt(0.5), math.sqrt(0.5)])
    assert all(near_list(a, b, 1e-9) for a, b in zip(D, [[0.5, -0.5], [-0.5, 0.5]])), f"deflating [[2, 1], [1, 2]] by (3, (1, 1)/sqrt 2) leaves [[0.5, -0.5], [-0.5, 0.5]]; got {D}"
    # a rank-one hand case: every row on the line y = x
    L = [[0.0, 0.0], [2.0, 2.0], [4.0, 4.0]]
    m = mod.pca(L, 1)
    s = math.sqrt(0.5)
    assert near(m.total_variance, 8.0) and near(m.variances[0], 8.0), f"points on y = x: variances along x and y are 4 + 4 = 8, all on PC1; got total {m.total_variance}, PC1 {m.variances}"
    assert near_list(m.components[0], [s, s], 1e-8), f"PC1 of points on y = x is (1, 1)/sqrt 2; got {m.components[0]}"
    Z = mod.project(L, m)
    assert near_list([z[0] for z in Z], [-2 * math.sqrt(2), 0.0, 2 * math.sqrt(2)], 1e-8), f"scores along PC1 should be -2.828, 0, 2.828; got {Z}"
    back = mod.reconstruct(Z, m)
    assert all(near_list(a, b, 1e-8) for a, b in zip(back, L)), f"one component rebuilds a line exactly; got {back}"
    # the factor data of chapter 11
    for seed in seeds((1, 2, 3)):
        X = mod.make_factors(seed)
        n, p = len(X), len(X[0])
        evals, evecs = jacobi_eigen(oracle_cov(X))
        m = mod.pca(X, 3, seed)
        assert near(m.total_variance, sum(evals), 1e-9), f"total_variance is the trace of the covariance matrix ({sum(evals):.4f}); got {m.total_variance} (seed {seed})"
        assert near_list(m.variances, evals[:3], 1e-6), f"variances should be the top eigenvalues {[round(e, 4) for e in evals[:3]]}; got {[round(v, 4) for v in m.variances]} (seed {seed})"
        for j in range(3):
            assert abs(mod.dot(m.components[j], evecs[j])) > 1 - 1e-6, f"component {j} does not match the true eigenvector (seed {seed}); deflate after each component"
            assert near(mod.norm(m.components[j]), 1.0, 1e-9), f"components must have unit length (seed {seed})"
            big = max(range(p), key=lambda i: abs(m.components[j][i]))
            assert m.components[j][big] > 0, f"sign rule: the largest-magnitude entry of component {j} must be positive (seed {seed})"
        for a in range(3):
            for b in range(a + 1, 3):
                assert abs(mod.dot(m.components[a], m.components[b])) < 1e-6, f"components {a} and {b} must be orthogonal (seed {seed})"
        ratio = mod.explained_ratio(m)
        assert sum(ratio) > 0.9, f"three hidden factors should carry over 90% of the variance; got {sum(ratio):.3f} (seed {seed})"
        Z = mod.project(X, m)
        assert len(Z) == n and len(Z[0]) == 3, f"project should return n rows of k scores; got {len(Z)} x {len(Z[0])}"
        for j in range(3):
            col = [z[j] for z in Z]
            assert near(sum(col) / n, 0.0, 1e-8), f"scores are centred, so each score column has mean 0 (seed {seed})"
            var = sum(c * c for c in col) / (n - 1)
            assert near(var, m.variances[j], 1e-6), f"the variance of score column {j} should equal variances[{j}] = {m.variances[j]:.4f}; got {var:.4f} (seed {seed})"
        Xh = mod.reconstruct(Z, m)
        err = sum(sum((a - b) ** 2 for a, b in zip(r, rh)) for r, rh in zip(X, Xh)) / (n - 1)
        want = sum(evals) - sum(evals[:3])
        assert near(err, want, 1e-6), (f"the squared reconstruction error summed over rows, divided by n - 1, equals the variance left behind "
                                       f"({want:.4f}); got {err:.4f} (seed {seed}). Reconstruction adds the mean back")
    return (f"closed-form 2x2 eigenpairs, a rank-one hand case, and 3 seeded 400 x 8 datasets against a Jacobi solver\n"
            f"top three components explain {sum(ratio) * 100:.1f}% of the variance (last seed); sign, orthogonality and reconstruction identity hold")


# =============================================================================
# Milestone 4: isolation-forest score
# =============================================================================
def tree_depth(node):
    return 0 if "feat" not in node else 1 + max(tree_depth(node["left"]), tree_depth(node["right"]))


def m4():
    assert mod.c_factor(0) == 0 and mod.c_factor(1) == 0, "c(n) is 0 for n <= 1"
    assert near(mod.c_factor(2), 0.1544313298, 1e-8), f"c(2) = 2 x 0.5772 - 1 = 0.15443 with chapter 12's formula; got {mod.c_factor(2)}"
    assert near(mod.c_factor(256), 10.24477092, 1e-8), f"c(256) = 2 (ln 255 + 0.5772) - 2 x 255 / 256 = 10.2448; got {mod.c_factor(256)}"
    # a hand-grown tree: midpoint cuts on column 0, rows 0, 1, 2, 3, 100
    S = [[0.0], [1.0], [2.0], [3.0], [100.0]]
    s = Script(ranges=[0] * 20, midpoint=True)
    tree = mod.build_tree(S, 0, 3, s)
    assert tree.get("feat") == 0 and near(tree.get("thr", -1), 50.0), f"the root cut is at the midpoint of [0, 100] = 50; got {tree}"
    assert tree["right"] == {"size": 1}, f"the row at 100 is alone on the right of the root cut; got {tree['right']}"
    assert s.calls[0] == ("randrange", 1) and s.calls[1] == ("uniform", 0.0, 100.0), (
        f"draw the column with randrange(p) first, then uniform(lo, hi) over that column's range; saw {s.calls[:2]}")
    got = {x: mod.path_length([x], tree) for x in (0.0, 1.0, 2.0, 3.0, 100.0)}
    assert near(got[100.0], 1.0), f"the outlier at 100 is isolated by one cut: path length 1 + c(1) = 1; got {got[100.0]}"
    assert all(near(got[x], 3.0) for x in (0.0, 1.0, 2.0, 3.0)), f"the four crowded rows each need 3 cuts; got {got}"
    tree2 = mod.build_tree(S, 0, 2, Script(ranges=[0] * 20, midpoint=True))
    assert near(mod.path_length([1.0], tree2), 2 + mod.c_factor(2)), (
        f"with depth limit 2 the node {{0, 1}} stays a leaf of size 2, so h = 2 + c(2) = {2 + mod.c_factor(2):.4f}; got {mod.path_length([1.0], tree2)}")
    flat = mod.build_tree([[1.0, 5.0], [2.0, 5.0]], 0, 5, Script(ranges=[1] * 5, midpoint=True))
    assert flat == {"size": 2}, f"a constant column cannot be cut: make a leaf of size 2; got {flat}"
    assert mod.build_tree([[1.0]], 0, 5, Script()) == {"size": 1}, "a single row is a leaf (and must not consume random numbers)"
    # hand score
    fake = mod.IForest([{"size": 1}] * 4, 256)
    leaf3 = {"feat": 0, "thr": 0.0, "left": {"size": 1}, "right": {"size": 1}}
    assert near(mod.anomaly_score(mod.IForest([{"size": 1}], 256), [0.0]), 1.0), "a point isolated at depth 0 has E[h] = 0 and score 2^0 = 1"
    deep = {"feat": 0, "thr": 0.5, "left": {"feat": 0, "thr": 0.25, "left": {"feat": 0, "thr": 0.1, "left": {"size": 1}, "right": {"size": 1}}, "right": {"size": 1}}, "right": {"size": 1}}
    sc = mod.anomaly_score(mod.IForest([deep], 256), [0.0])
    assert near(sc, 2 ** (-3 / 10.24477092), 1e-7), f"path length 3 with psi = 256: score = 2^(-3 / 10.2448) = 0.8163; got {sc}"
    # forest structure
    rng = random.Random(0)
    Xn = [[rng.gauss(0, 1), rng.gauss(0, 1)] for _ in range(300)]
    f1 = mod.fit_iforest(Xn, n_trees=25, psi=64, seed=3)
    assert len(f1.trees) == 25 and f1.psi == 64, f"expected 25 trees with psi 64; got {len(f1.trees)} trees, psi {f1.psi}"
    assert max(tree_depth(t) for t in f1.trees) <= 6, "the depth limit is ceil(log2(64)) = 6 cuts"
    small = mod.fit_iforest(Xn[:40], n_trees=5, psi=128, seed=0)
    assert small.psi == 40, f"psi is capped at the number of rows (40); got {small.psi}"
    f2 = mod.fit_iforest(Xn, n_trees=25, psi=64, seed=3)
    f3 = mod.fit_iforest(Xn, n_trees=25, psi=64, seed=4)
    assert f1.trees == f2.trees, "the same seed must grow the same forest"
    assert f1.trees != f3.trees, "a different seed must grow a different forest"
    # scores on data
    worst_gap = 1.0
    for seed in seeds((1, 2, 3)):
        rng = random.Random(seed)
        pts = [[rng.gauss(0, 1), rng.gauss(0, 1)] for _ in range(400)] + [[8.0, 8.0], [0.0, 0.0]]
        forest = mod.fit_iforest(pts, n_trees=100, psi=128, seed=seed)
        sc = [mod.anomaly_score(forest, x) for x in pts]
        assert all(0.0 < s <= 1.0 for s in sc), f"scores must lie in (0, 1]; got range {min(sc):.3f} to {max(sc):.3f} (seed {seed})"
        assert sc[-2] > 0.65, f"a point at (8, 8), 8 sd from the cloud, should score above 0.65; got {sc[-2]:.3f} (seed {seed})"
        assert sc[-1] < 0.45, f"the point at the very centre should score below 0.45 (it takes many cuts); got {sc[-1]:.3f} (seed {seed})"
        worst_gap = min(worst_gap, sc[-2] - sc[-1])
    Xs, kind = mod.make_sensors(1)
    forest = mod.fit_iforest(Xs, 100, 128, seed=0)
    sc = [mod.anomaly_score(forest, x) for x in Xs]
    a1, a2 = pair_auc(sc, kind, 1), pair_auc(sc, kind, 2)
    assert a1 > 0.95 and a2 > 0.9, f"on the sensor fleet the forest should isolate far-away and in-between readings (AUC > 0.95 and > 0.9); got {a1:.3f} and {a2:.3f}"
    return (f"c(n) hand values, a hand-grown tree (path lengths 1 and 3), forest structure, and scores on a Gaussian cloud\n"
            f"sensor fleet: isolation-forest AUC {a1:.3f} on far-away readings, {a2:.3f} on in-between readings")


# =============================================================================
# Milestone 5: detectors compared, combined, and the arithmetic of alerts
# =============================================================================
def m5():
    res = mod.KMeansResult([[0.0, 0.0], [10.0, 0.0]], [], 0.0, 0)
    got = mod.centre_distance_scores([[3.0, 4.0], [10.0, 2.0]], res)
    assert near_list(got, [5.0, 2.0]), f"distance (not squared) to the nearest centre: expected [5, 2]; got {got}"
    s = math.sqrt(0.5)
    model = mod.PCAModel([0.0, 0.0], [[s, s]], [1.0], 1.0)
    got = mod.pca_residual_scores([[1.0, 1.0], [1.0, -1.0]], model)
    assert near_list(got, [0.0, 2.0], 1e-9), f"a row on the PC1 line has residual 0; (1, -1) is perpendicular, so squared residual 2; got {got}"
    model = mod.PCAModel([5.0, 5.0], [[s, s]], [1.0], 1.0)
    got = mod.pca_residual_scores([[6.0, 6.0], [6.0, 4.0]], model)
    assert near_list(got, [0.0, 2.0], 1e-9), f"the residual is measured around the mean (5, 5): expected [0, 2]; got {got}"
    got = mod.rank_normalise([10.0, 30.0, 20.0])
    assert near_list(got, [1 / 3, 1.0, 2 / 3]), f"rank_normalise([10, 30, 20]) = [1/3, 1, 2/3]; got {got}"
    got = mod.rank_normalise([1.0, 1.0, 2.0])
    assert near_list(got, [0.5, 0.5, 1.0]), f"tied scores share an average rank: [1, 1, 2] -> [0.5, 0.5, 1.0]; got {got}"
    got = mod.combine_max([[1.0, 2.0, 3.0], [3.0, 2.0, 1.0]])
    assert near_list(got, [1.0, 2 / 3, 1.0]), f"rank-normalise each list first, then take the larger value per row: [1, 2/3, 1]; got {got}"
    assert near(mod.precision_at_k([0.9, 0.8, 0.7, 0.6], [1, 0, 1, 0], 2), 0.5), "top 2 are rows 0 and 1, one positive: 0.5"
    assert near(mod.precision_at_k([0.9, 0.8, 0.7, 0.6], [1, 0, 1, 0], 3), 2 / 3), "top 3 hold two positives: 2/3"
    assert near(mod.precision_at_k([1.0, 1.0, 1.0], [0, 1, 1], 1), 0.0), "ties break towards the lower row index: row 0 (a negative) is first"
    t, f, p = mod.expected_alerts(1_000_000, 0.001, 0.9, 0.01)
    assert near(t, 900.0) and near(f, 9990.0) and near(p, 900 / 10890), (
        f"1,000,000 rows, 0.1% anomalous, 90% caught, 1% false alarms: 900 true alerts, 9,990 false ones, precision 8.3%; got {(t, f, p)}")
    # the scenario
    lines = []
    for seed in seeds((1, 2)):
        X, kind = mod.make_sensors(seed)
        out = mod.run_detectors(X, seed=0)
        assert set(out) == {"kmeans", "pca", "iforest", "combined"} and all(len(v) == len(X) for v in out.values()), \
            f"run_detectors should return four score lists, one score per row; got {sorted(out)}"
        A = {name: [pair_auc(sc, kind, g) for g in (1, 2, 3)] for name, sc in out.items()}
        assert A["kmeans"][0] > 0.95 and A["kmeans"][1] > 0.95, f"k-means distance should catch far-away and in-between readings; got AUC {A['kmeans'][:2]} (seed {seed})"
        assert A["kmeans"][2] < 0.8, f"k-means distance should be BLIND to off-plane readings (the cluster spread hides them); got {A['kmeans'][2]:.3f} (seed {seed}); is it a Euclidean distance to the nearest centre?"
        assert A["pca"][2] > 0.95, f"PCA residual should catch off-plane readings; got {A['pca'][2]:.3f} (seed {seed}); score each row by its squared reconstruction error with k = 2"
        assert A["pca"][0] < 0.7 and A["pca"][1] < 0.7, f"PCA residual should be blind to readings that sit ON the plane (far or between); got {A['pca'][:2]} (seed {seed})"
        assert A["iforest"][0] > 0.95, f"the isolation forest should catch far-away readings; got {A['iforest'][0]:.3f} (seed {seed})"
        assert min(A["combined"]) > 0.9, f"the combined detector should catch all three kinds (AUC > 0.9 each); got {[round(a, 3) for a in A['combined']]} (seed {seed}); rank-normalise before taking the max"
        pos = [k != 0 for k in kind]
        k_alerts = sum(pos)
        pk = {name: mod.precision_at_k(sc, pos, k_alerts) for name, sc in out.items()}
        assert pk["combined"] > max(pk["kmeans"], pk["pca"], pk["iforest"]) - 1e-9 or pk["combined"] > 0.7, f"the combined list should be at least competitive at k = {k_alerts}: {pk} (seed {seed})"
        lines.append((seed, A, pk, k_alerts))
    seed, A, pk, ka = lines[-1]
    rows = [f"seed {seed}: AUC by anomaly kind (far, between, off-plane)"]
    for name in ("kmeans", "pca", "iforest", "combined"):
        rows.append(f"  {name:9s} " + "  ".join(f"{a:.3f}" for a in A[name]) + f"   precision at {ka}: {pk[name]:.2f}")
    return "\n".join(rows)


check(1, "Milestone 1: Lloyd's algorithm", m1)
check(2, "Milestone 2: k-means++ with restarts, and the silhouette", m2)
check(3, "Milestone 3: PCA by power iteration", m3)
check(4, "Milestone 4: an isolation-forest score", m4)
check(5, "Milestone 5: three detectors, one combined, and the alert arithmetic", m5)

print()
print(f"{sum(results)}/{len(results)} milestones passing  ({time.time() - START:.1f} s)")
