"""Lab 3 (reference solution): k-means++ with restarts, PCA by power iteration and an isolation-forest score.

Conventions (the same as chapters 10, 11 and 12 of this course):

    X          list of rows, shape (n_samples, n_features); each row is a list of floats
    centres    list of k rows (the k-means centroids)
    labels     list of n ints: labels[i] is the index of the centre nearest to row i (ties go to the lower index)
    inertia    sum over rows of the squared distance to the row's centre (the k-means objective)
    C          the sample covariance matrix, C = Xc^T Xc / (n - 1), where Xc is X with column means subtracted
    component  a unit-length principal axis; variance[j] is the eigenvalue of C for component j
    path length h(x)  the number of cuts that isolate x in a random binary tree (plus c(leaf size) for a leaf
               that still holds several rows); score s(x) = 2 ** (-E[h(x)] / c(psi))

Everything is deterministic: every random number comes from a seeded random.Random.

What is GIVEN: the data generators, dot, norm, mat_vec, average_ranks, auc, explained_ratio and the result
containers (KMeansResult, PCAModel, IForest). What YOU write is marked TODO:

    1  sq_dist, assign, update_centres, inertia, lloyd
    2  kmeans_pp_init, kmeans, silhouette, sweep_k
    3  column_means, covariance, power_iteration, deflate, pca, project, reconstruct
    4  c_factor, build_tree, path_length, fit_iforest, anomaly_score
    5  centre_distance_scores, pca_residual_scores, rank_normalise, combine_max, precision_at_k,
       expected_alerts, run_detectors

`python3 check.py` runs the milestones; the lab page explains each one.
"""
import math
import random
from dataclasses import dataclass, field


# =============================================================================
# GIVEN: synthetic data, small linear-algebra helpers and result containers
# =============================================================================
def make_blobs(seed, centres, n_per=60, sd=1.0):
    """Round Gaussian blobs: n_per points around each centre with standard deviation sd in every direction.

    Returns (X, truth) where truth[i] is the index of the centre that generated row i.
    """
    rng = random.Random(seed)
    X, truth = [], []
    for j, c in enumerate(centres):
        for _ in range(n_per):
            X.append([ci + rng.gauss(0, sd) for ci in c])
            truth.append(j)
    return X, truth


def make_six_groups(seed):
    """Chapter 10's experiment: six well-separated groups of 60 points on a 3 x 2 grid (spacing 5, sd 0.8)."""
    grid = [[5.0 * a, 5.0 * b] for a in range(3) for b in range(2)]
    return make_blobs(seed, grid, n_per=60, sd=0.8)


def make_factors(seed, n=400, p=8, sds=(3.0, 2.0, 1.0), noise=0.5):
    """Chapter 11's data: n rows and p columns generated from len(sds) hidden factors plus column noise.

    Row i is  z_i W + eps_i  where z_ij ~ N(0, sds[j]^2), W is a fixed random mixing matrix (len(sds) x p) and
    eps ~ N(0, noise^2) on every column. So the covariance has len(sds) large eigenvalues and p - len(sds)
    eigenvalues close to noise^2.
    """
    rng = random.Random(seed)
    W = [[rng.gauss(0, 1) for _ in range(p)] for _ in sds]
    X = []
    for _ in range(n):
        z = [rng.gauss(0, s) for s in sds]
        X.append([sum(z[j] * W[j][c] for j in range(len(sds))) + rng.gauss(0, noise) for c in range(p)])
    return X


# The sensor fleet's flat "operating plane" inside 4-D space, and the two directions perpendicular to it.
_PLANE = ([0.5, 0.5, 0.5, 0.5], [0.5, -0.5, 0.5, -0.5])
_OFF = ([0.5, 0.5, -0.5, -0.5], [0.5, -0.5, -0.5, 0.5])
_MODES = [(-6.0, 0.0), (6.0, 0.0), (0.0, 6.0)]


def _lift(a, b, c, d):
    """Plane coordinates (a, b) and off-plane coordinates (c, d) -> a point in 4-D."""
    return [a * _PLANE[0][i] + b * _PLANE[1][i] + c * _OFF[0][i] + d * _OFF[1][i] for i in range(4)]


def make_sensors(seed, n_normal=600, n_each=12):
    """A fleet of sensors reading 4 numbers. Normal readings sit on a flat 2-D plane inside 4-D space, in three
    operating modes (wide in the plane, sd 1.2; almost flat off it, sd 0.15). Three kinds of anomaly:

        kind 1  global: far away along the plane (a failing unit running at a crazy setting)
        kind 2  between: in the plane but in the empty gap between the three modes (a unit stuck mid-transition)
        kind 3  off-plane: inside a mode's footprint on the plane, but 0.9 off the plane (a broken sensor channel)

    Returns (X, kind) with kind[i] = 0 for a normal row and 1, 2 or 3 for an anomaly. Rows are shuffled.
    """
    rng = random.Random(seed)
    rows = []
    for _ in range(n_normal):
        a0, b0 = rng.choice(_MODES)
        rows.append((_lift(a0 + rng.gauss(0, 1.2), b0 + rng.gauss(0, 1.2), rng.gauss(0, 0.15), rng.gauss(0, 0.15)), 0))
    for _ in range(n_each):
        ang = rng.uniform(0, 2 * math.pi)
        r = rng.uniform(13, 16)
        rows.append((_lift(r * math.cos(ang), r * math.sin(ang), rng.gauss(0, 0.15), rng.gauss(0, 0.15)), 1))
    for _ in range(n_each):
        rows.append((_lift(rng.gauss(0, 0.6), rng.gauss(0, 0.6), rng.gauss(0, 0.15), rng.gauss(0, 0.15)), 2))
    for _ in range(n_each):
        a0, b0 = rng.choice(_MODES)
        ang = rng.uniform(0, 2 * math.pi)
        rows.append((_lift(a0 + rng.gauss(0, 1.2), b0 + rng.gauss(0, 1.2), 0.9 * math.cos(ang), 0.9 * math.sin(ang)), 3))
    rng.shuffle(rows)
    return [r for r, _ in rows], [k for _, k in rows]


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def norm(a):
    return math.sqrt(dot(a, a))


def mat_vec(M, v):
    """Matrix (list of rows) times vector."""
    return [dot(row, v) for row in M]


def average_ranks(values):
    """1-based ranks of the values, with tied values sharing the average of their ranks."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for t in range(i, j + 1):
            ranks[order[t]] = (i + j) / 2 + 1
        i = j + 1
    return ranks


def auc(scores, positive):
    """Probability that a random positive row outscores a random negative one (0.5 = chance).

    `positive` is a list of booleans (or 0/1) of the same length as scores.
    """
    r = average_ranks(scores)
    n1 = sum(1 for p in positive if p)
    n0 = len(positive) - n1
    return (sum(rk for rk, p in zip(r, positive) if p) - n1 * (n1 + 1) / 2) / (n1 * n0)


@dataclass
class KMeansResult:
    """What a k-means run returns: its centres, the label of every row, the final inertia, the number of
    update rounds it took, and the inertia after every round (history[0] is the inertia of the first
    assignment, before any update)."""
    centres: list
    labels: list
    inertia: float
    n_iter: int
    history: list = field(default_factory=list)


@dataclass
class PCAModel:
    """A fitted PCA: the column means, the k unit-length components (k rows of length p), the variance along
    each component, and the total variance of the data (the trace of the covariance matrix)."""
    mean: list
    components: list
    variances: list
    total_variance: float


def explained_ratio(model):
    """Share of the total variance carried by each component."""
    return [v / model.total_variance for v in model.variances]


@dataclass
class IForest:
    """An isolation forest: its trees (nested dicts) and the subsample size psi each tree was grown on."""
    trees: list
    psi: int


# =============================================================================
# Milestone 1: Lloyd's algorithm
# =============================================================================
def sq_dist(a, b):
    """Squared Euclidean distance between two rows: sum_j (a_j - b_j)^2."""
    return sum((x - y) ** 2 for x, y in zip(a, b))


def assign(X, centres):
    """labels[i] = index of the centre nearest to X[i] (squared distance). Ties go to the lower index."""
    labels = []
    for x in X:
        best, best_d = 0, sq_dist(x, centres[0])
        for j in range(1, len(centres)):
            d = sq_dist(x, centres[j])
            if d < best_d:                  # strict: an exact tie keeps the lower index
                best, best_d = j, d
        labels.append(best)
    return labels


def update_centres(X, labels, centres):
    """New centres: the mean of the rows assigned to each centre. A centre that got no rows keeps its old position.

    Returns a new list of k rows; `centres` is not modified.
    """
    k, p = len(centres), len(centres[0])
    sums = [[0.0] * p for _ in range(k)]
    counts = [0] * k
    for x, j in zip(X, labels):
        counts[j] += 1
        for c in range(p):
            sums[j][c] += x[c]
    return [[s / counts[j] for s in sums[j]] if counts[j] else list(centres[j]) for j in range(k)]


def inertia(X, labels, centres):
    """Sum over rows of the squared distance to the row's own centre."""
    return sum(sq_dist(x, centres[j]) for x, j in zip(X, labels))


def lloyd(X, centres, max_iter=100):
    """Lloyd's algorithm from the given starting centres: assign, update, repeat until the labels stop changing.

    Returns a KMeansResult. history[0] is the inertia of the first assignment; every round then appends the
    inertia after updating the centres and re-assigning. The history never increases. n_iter counts the
    update rounds (the round that confirms nothing moved is included). `centres` is not modified.
    """
    centres = [list(c) for c in centres]
    labels = assign(X, centres)
    history = [inertia(X, labels, centres)]
    n_iter = 0
    for n_iter in range(1, max_iter + 1):
        centres = update_centres(X, labels, centres)
        new_labels = assign(X, centres)
        history.append(inertia(X, new_labels, centres))
        changed = new_labels != labels
        labels = new_labels
        if not changed:
            break
    return KMeansResult(centres, labels, history[-1], n_iter, history)


# =============================================================================
# Milestone 2: k-means++ seeding, restarts and the silhouette
# =============================================================================
def kmeans_pp_init(X, k, rng):
    """k-means++ seeding (Arthur and Vassilvitskii, 2007). Returns k starting centres (copies of rows of X).

    The first centre is X[rng.randrange(n)]. Each later centre is drawn with probability proportional to D(x)^2,
    the squared distance from x to its nearest centre chosen so far. Draw it exactly like this, so a scripted
    rng reproduces your choice: r = rng.random() * total, then take the first row whose running total of
    D^2 exceeds r. If the total is 0 (every row already is a centre), take rng.randrange(n) instead.
    """
    n = len(X)
    centres = [list(X[rng.randrange(n)])]
    d2 = [sq_dist(x, centres[0]) for x in X]
    while len(centres) < k:
        total = sum(d2)
        if total == 0:
            pick = rng.randrange(n)
        else:
            r = rng.random() * total
            acc, pick = 0.0, n - 1
            for i, w in enumerate(d2):
                acc += w
                if acc > r:
                    pick = i
                    break
        centres.append(list(X[pick]))
        d2 = [min(w, sq_dist(x, centres[-1])) for w, x in zip(d2, X)]
    return centres


def kmeans(X, k, seed, n_init=10, max_iter=100):
    """The best of n_init runs of Lloyd's algorithm, each from its own k-means++ start.

    One random.Random(seed) feeds all the restarts, in order. 'Best' is the lowest final inertia; on an
    exact tie keep the earlier run. Returns a KMeansResult.
    """
    rng = random.Random(seed)
    best = None
    for _ in range(n_init):
        res = lloyd(X, kmeans_pp_init(X, k, rng), max_iter)
        if best is None or res.inertia < best.inertia:
            best = res
    return best


def silhouette(X, labels):
    """Mean silhouette coefficient (Euclidean distance, not squared).

    For row i: a = mean distance to the other rows of its own cluster, b = the smallest, over the other
    clusters, of the mean distance to that cluster's rows, and s = (b - a) / max(a, b). A row alone in its
    cluster has s = 0. With fewer than two clusters return 0.0.
    """
    clusters = sorted(set(labels))
    if len(clusters) < 2:
        return 0.0
    members = {c: [i for i, l in enumerate(labels) if l == c] for c in clusters}
    total = 0.0
    for i, x in enumerate(X):
        own = members[labels[i]]
        if len(own) == 1:
            continue
        a = sum(math.sqrt(sq_dist(x, X[j])) for j in own if j != i) / (len(own) - 1)
        b = min(sum(math.sqrt(sq_dist(x, X[j])) for j in members[c]) / len(members[c])
                for c in clusters if c != labels[i])
        total += (b - a) / max(a, b)
    return total / len(X)


def sweep_k(X, ks, seed=0, n_init=5):
    """For each k in ks run kmeans(X, k, seed, n_init) and return a list of (k, inertia, silhouette)."""
    out = []
    for k in ks:
        res = kmeans(X, k, seed, n_init)
        out.append((k, res.inertia, silhouette(X, res.labels)))
    return out


# =============================================================================
# Milestone 3: PCA by power iteration
# =============================================================================
def column_means(X):
    """Mean of each column."""
    n = len(X)
    return [sum(row[c] for row in X) / n for c in range(len(X[0]))]


def covariance(X):
    """Sample covariance matrix (p x p, list of rows) with the n - 1 denominator. Centres X itself."""
    n, p = len(X), len(X[0])
    mu = column_means(X)
    Xc = [[row[c] - mu[c] for c in range(p)] for row in X]
    return [[sum(r[a] * r[b] for r in Xc) / (n - 1) for b in range(p)] for a in range(p)]


def power_iteration(C, rng, max_iter=10000, tol=1e-12):
    """Dominant eigenpair of a symmetric positive semi-definite matrix C by power iteration.

    Start from a random vector [rng.gauss(0, 1) for each column], then repeat: v <- C v / |C v|, until the
    vector moves by less than tol (Euclidean distance) in one step, or max_iter steps. Return (lam, v) where v
    has unit length and lam = v^T C v. Fix the sign so the entry of v with the largest magnitude is positive.
    If C v is the zero vector (C is zero) return (0.0, v) with v the unit start vector.
    """
    p = len(C)
    v = [rng.gauss(0, 1) for _ in range(p)]
    nv = norm(v)
    v = [x / nv for x in v]
    for _ in range(max_iter):
        w = mat_vec(C, v)
        nw = norm(w)
        if nw == 0:
            return 0.0, v
        w = [x / nw for x in w]
        moved = norm([a - b for a, b in zip(w, v)])
        v = w
        if moved < tol:
            break
    lam = dot(v, mat_vec(C, v))
    big = max(range(p), key=lambda i: abs(v[i]))
    if v[big] < 0:
        v = [-x for x in v]
    return lam, v


def deflate(C, lam, v):
    """Remove the eigenpair (lam, v) from C: return C - lam * v v^T as a new matrix."""
    p = len(C)
    return [[C[a][b] - lam * v[a] * v[b] for b in range(p)] for a in range(p)]


def pca(X, k, seed=0):
    """The first k principal components of X by repeated power iteration with deflation.

    One random.Random(seed) feeds all k power iterations, in order. Returns a PCAModel: the column means, the
    k components (unit length, sign as in power_iteration), their variances (eigenvalues of the covariance
    matrix) and the total variance (the trace of the covariance matrix, computed before any deflation).
    """
    rng = random.Random(seed)
    C = covariance(X)
    total = sum(C[i][i] for i in range(len(C)))
    comps, variances = [], []
    for _ in range(k):
        lam, v = power_iteration(C, rng)
        comps.append(v)
        variances.append(lam)
        C = deflate(C, lam, v)
    return PCAModel(column_means(X), comps, variances, total)


def project(X, model):
    """Scores: row i -> [ (x_i - mean) . component_j  for each component j ]."""
    return [[dot([a - m for a, m in zip(x, model.mean)], comp) for comp in model.components] for x in X]


def reconstruct(Z, model):
    """Map scores back to the original columns: mean + sum_j z_j * component_j."""
    p = len(model.mean)
    return [[model.mean[c] + sum(z[j] * model.components[j][c] for j in range(len(z))) for c in range(p)] for z in Z]


# =============================================================================
# Milestone 4: an isolation-forest anomaly score
# =============================================================================
def c_factor(n):
    """c(n): the average path length of an unsuccessful search in a binary search tree of n rows.

    c(n) = 2 (ln(n - 1) + 0.5772156649) - 2 (n - 1) / n for n > 1, and 0 for n <= 1. Chapter 12 uses this form.
    """
    if n <= 1:
        return 0.0
    return 2 * (math.log(n - 1) + 0.5772156649) - 2 * (n - 1) / n


def build_tree(S, depth, limit, rng):
    """One isolation tree grown on the rows S (a list of rows). Nodes are dicts.

    A leaf is {"size": len(S)}; make a leaf when depth >= limit, when len(S) <= 1, or when the chosen
    column is constant over S. Otherwise draw, in this order, j = rng.randrange(p), then (after finding the
    minimum and maximum of column j in S) t = rng.uniform(lo, hi), and return
    {"feat": j, "thr": t, "left": <rows with x[j] < t>, "right": <rows with x[j] >= t>}, each child grown with
    depth + 1.
    """
    n = len(S)
    if depth >= limit or n <= 1:
        return {"size": n}
    j = rng.randrange(len(S[0]))
    lo = min(r[j] for r in S)
    hi = max(r[j] for r in S)
    if lo == hi:
        return {"size": n}
    t = rng.uniform(lo, hi)
    left = [r for r in S if r[j] < t]
    right = [r for r in S if r[j] >= t]
    return {"feat": j, "thr": t,
            "left": build_tree(left, depth + 1, limit, rng),
            "right": build_tree(right, depth + 1, limit, rng)}


def path_length(x, node, depth=0):
    """h(x): the depth at which x reaches a leaf, plus c(leaf size) for the cuts the depth limit stopped."""
    while "feat" in node:
        node = node["left"] if x[node["feat"]] < node["thr"] else node["right"]
        depth += 1
    return depth + c_factor(node["size"])


def fit_iforest(X, n_trees=100, psi=128, seed=0):
    """An isolation forest: n_trees trees, each grown on psi rows drawn without replacement.

    psi is capped at len(X). The depth limit is ceil(log2(psi)). One random.Random(seed) does everything: for
    each tree, S = rng.sample(X, psi), then build_tree(S, 0, limit, rng).
    """
    rng = random.Random(seed)
    psi = min(psi, len(X))
    limit = math.ceil(math.log2(psi)) if psi > 1 else 0
    trees = [build_tree(rng.sample(X, psi), 0, limit, rng) for _ in range(n_trees)]
    return IForest(trees, psi)


def anomaly_score(forest, x):
    """s(x) = 2 ** (-E[h(x)] / c(psi)), where E[h(x)] is the mean path length over the forest's trees.

    Near 1: isolated much faster than average. About 0.5: average. Below 0.5: harder to isolate than most.
    """
    mean_h = sum(path_length(x, t) for t in forest.trees) / len(forest.trees)
    return 2 ** (-mean_h / c_factor(forest.psi))


# =============================================================================
# Milestone 5: three detectors, one combined, and the arithmetic of alerts
# =============================================================================
def centre_distance_scores(X, result):
    """k-means as a detector: each row's Euclidean distance (not squared) to its nearest centre."""
    return [math.sqrt(sq_dist(x, result.centres[j])) for x, j in zip(X, assign(X, result.centres))]


def pca_residual_scores(X, model):
    """PCA as a detector: each row's squared reconstruction error, sum over columns of (x - x_hat)^2."""
    Xhat = reconstruct(project(X, model), model)
    return [sq_dist(x, xh) for x, xh in zip(X, Xhat)]


def rank_normalise(scores):
    """Replace each score by its average rank divided by n, so the largest score becomes 1.0.

    rank_normalise([10, 30, 20]) is [1/3, 1, 2/3]; tied scores share an average rank.
    """
    n = len(scores)
    return [r / n for r in average_ranks(scores)]


def combine_max(score_lists):
    """Rank-normalise each list of scores, then take the largest value per row across the lists."""
    normed = [rank_normalise(s) for s in score_lists]
    return [max(col) for col in zip(*normed)]


def precision_at_k(scores, positive, k):
    """Fraction of the k highest-scoring rows that are positive. Ties are broken by the lower row index."""
    order = sorted(range(len(scores)), key=lambda i: (-scores[i], i))[:k]
    return sum(1 for i in order if positive[i]) / k


def expected_alerts(n, base_rate, tpr, fpr):
    """The base-rate arithmetic of chapter 12. n rows, a fraction base_rate of them anomalous; the detector
    flags a fraction tpr of the anomalies and a fraction fpr of the normal rows.

    Returns (true_alerts, false_alerts, precision) where precision = true / (true + false).
    """
    true_alerts = n * base_rate * tpr
    false_alerts = n * (1 - base_rate) * fpr
    return true_alerts, false_alerts, true_alerts / (true_alerts + false_alerts)


def run_detectors(X, seed=0):
    """Fit the three unsupervised detectors on X and return {name: scores} for "kmeans", "pca", "iforest"
    and "combined". Use kmeans(X, 3, seed, n_init=5), pca(X, 2, seed), fit_iforest(X, 100, 128, seed); score
    with centre_distance_scores, pca_residual_scores and anomaly_score; "combined" is combine_max of the three.
    """
    km = kmeans(X, 3, seed, n_init=5)
    model = pca(X, 2, seed)
    forest = fit_iforest(X, 100, 128, seed)
    s_km = centre_distance_scores(X, km)
    s_pca = pca_residual_scores(X, model)
    s_if = [anomaly_score(forest, x) for x in X]
    return {"kmeans": s_km, "pca": s_pca, "iforest": s_if, "combined": combine_max([s_km, s_pca, s_if])}
