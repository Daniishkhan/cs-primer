"""Lab 3: k-means++ with restarts, PCA by power iteration and an isolation-forest score.

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
    raise NotImplementedError("TODO milestone 1: sq_dist")


def assign(X, centres):
    """labels[i] = index of the centre nearest to X[i] (squared distance). Ties go to the lower index."""
    raise NotImplementedError("TODO milestone 1: assign")


def update_centres(X, labels, centres):
    """New centres: the mean of the rows assigned to each centre. A centre that got no rows keeps its old position.

    Returns a new list of k rows; `centres` is not modified.
    """
    raise NotImplementedError("TODO milestone 1: update_centres")


def inertia(X, labels, centres):
    """Sum over rows of the squared distance to the row's own centre."""
    raise NotImplementedError("TODO milestone 1: inertia")


def lloyd(X, centres, max_iter=100):
    """Lloyd's algorithm from the given starting centres: assign, update, repeat until the labels stop changing.

    Returns a KMeansResult. history[0] is the inertia of the first assignment; every round then appends the
    inertia after updating the centres and re-assigning. The history never increases. n_iter counts the
    update rounds (the round that confirms nothing moved is included). `centres` is not modified.
    """
    raise NotImplementedError("TODO milestone 1: lloyd")


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
    raise NotImplementedError("TODO milestone 2: kmeans_pp_init")


def kmeans(X, k, seed, n_init=10, max_iter=100):
    """The best of n_init runs of Lloyd's algorithm, each from its own k-means++ start.

    One random.Random(seed) feeds all the restarts, in order. 'Best' is the lowest final inertia; on an
    exact tie keep the earlier run. Returns a KMeansResult.
    """
    raise NotImplementedError("TODO milestone 2: kmeans")


def silhouette(X, labels):
    """Mean silhouette coefficient (Euclidean distance, not squared).

    For row i: a = mean distance to the other rows of its own cluster, b = the smallest, over the other
    clusters, of the mean distance to that cluster's rows, and s = (b - a) / max(a, b). A row alone in its
    cluster has s = 0. With fewer than two clusters return 0.0.
    """
    raise NotImplementedError("TODO milestone 2: silhouette")


def sweep_k(X, ks, seed=0, n_init=5):
    """For each k in ks run kmeans(X, k, seed, n_init) and return a list of (k, inertia, silhouette)."""
    raise NotImplementedError("TODO milestone 2: sweep_k")


# =============================================================================
# Milestone 3: PCA by power iteration
# =============================================================================
def column_means(X):
    """Mean of each column."""
    raise NotImplementedError("TODO milestone 3: column_means")


def covariance(X):
    """Sample covariance matrix (p x p, list of rows) with the n - 1 denominator. Centres X itself."""
    raise NotImplementedError("TODO milestone 3: covariance")


def power_iteration(C, rng, max_iter=10000, tol=1e-12):
    """Dominant eigenpair of a symmetric positive semi-definite matrix C by power iteration.

    Start from a random vector [rng.gauss(0, 1) for each column], then repeat: v <- C v / |C v|, until the
    vector moves by less than tol (Euclidean distance) in one step, or max_iter steps. Return (lam, v) where v
    has unit length and lam = v^T C v. Fix the sign so the entry of v with the largest magnitude is positive.
    If C v is the zero vector (C is zero) return (0.0, v) with v the unit start vector.
    """
    raise NotImplementedError("TODO milestone 3: power_iteration")


def deflate(C, lam, v):
    """Remove the eigenpair (lam, v) from C: return C - lam * v v^T as a new matrix."""
    raise NotImplementedError("TODO milestone 3: deflate")


def pca(X, k, seed=0):
    """The first k principal components of X by repeated power iteration with deflation.

    One random.Random(seed) feeds all k power iterations, in order. Returns a PCAModel: the column means, the
    k components (unit length, sign as in power_iteration), their variances (eigenvalues of the covariance
    matrix) and the total variance (the trace of the covariance matrix, computed before any deflation).
    """
    raise NotImplementedError("TODO milestone 3: pca")


def project(X, model):
    """Scores: row i -> [ (x_i - mean) . component_j  for each component j ]."""
    raise NotImplementedError("TODO milestone 3: project")


def reconstruct(Z, model):
    """Map scores back to the original columns: mean + sum_j z_j * component_j."""
    raise NotImplementedError("TODO milestone 3: reconstruct")


# =============================================================================
# Milestone 4: an isolation-forest anomaly score
# =============================================================================
def c_factor(n):
    """c(n): the average path length of an unsuccessful search in a binary search tree of n rows.

    c(n) = 2 (ln(n - 1) + 0.5772156649) - 2 (n - 1) / n for n > 1, and 0 for n <= 1. Chapter 12 uses this form.
    """
    raise NotImplementedError("TODO milestone 4: c_factor")


def build_tree(S, depth, limit, rng):
    """One isolation tree grown on the rows S (a list of rows). Nodes are dicts.

    A leaf is {"size": len(S)}; make a leaf when depth >= limit, when len(S) <= 1, or when the chosen
    column is constant over S. Otherwise draw, in this order, j = rng.randrange(p), then (after finding the
    minimum and maximum of column j in S) t = rng.uniform(lo, hi), and return
    {"feat": j, "thr": t, "left": <rows with x[j] < t>, "right": <rows with x[j] >= t>}, each child grown with
    depth + 1.
    """
    raise NotImplementedError("TODO milestone 4: build_tree")


def path_length(x, node, depth=0):
    """h(x): the depth at which x reaches a leaf, plus c(leaf size) for the cuts the depth limit stopped."""
    raise NotImplementedError("TODO milestone 4: path_length")


def fit_iforest(X, n_trees=100, psi=128, seed=0):
    """An isolation forest: n_trees trees, each grown on psi rows drawn without replacement.

    psi is capped at len(X). The depth limit is ceil(log2(psi)). One random.Random(seed) does everything: for
    each tree, S = rng.sample(X, psi), then build_tree(S, 0, limit, rng).
    """
    raise NotImplementedError("TODO milestone 4: fit_iforest")


def anomaly_score(forest, x):
    """s(x) = 2 ** (-E[h(x)] / c(psi)), where E[h(x)] is the mean path length over the forest's trees.

    Near 1: isolated much faster than average. About 0.5: average. Below 0.5: harder to isolate than most.
    """
    raise NotImplementedError("TODO milestone 4: anomaly_score")


# =============================================================================
# Milestone 5: three detectors, one combined, and the arithmetic of alerts
# =============================================================================
def centre_distance_scores(X, result):
    """k-means as a detector: each row's Euclidean distance (not squared) to its nearest centre."""
    raise NotImplementedError("TODO milestone 5: centre_distance_scores")


def pca_residual_scores(X, model):
    """PCA as a detector: each row's squared reconstruction error, sum over columns of (x - x_hat)^2."""
    raise NotImplementedError("TODO milestone 5: pca_residual_scores")


def rank_normalise(scores):
    """Replace each score by its average rank divided by n, so the largest score becomes 1.0.

    rank_normalise([10, 30, 20]) is [1/3, 1, 2/3]; tied scores share an average rank.
    """
    raise NotImplementedError("TODO milestone 5: rank_normalise")


def combine_max(score_lists):
    """Rank-normalise each list of scores, then take the largest value per row across the lists."""
    raise NotImplementedError("TODO milestone 5: combine_max")


def precision_at_k(scores, positive, k):
    """Fraction of the k highest-scoring rows that are positive. Ties are broken by the lower row index."""
    raise NotImplementedError("TODO milestone 5: precision_at_k")


def expected_alerts(n, base_rate, tpr, fpr):
    """The base-rate arithmetic of chapter 12. n rows, a fraction base_rate of them anomalous; the detector
    flags a fraction tpr of the anomalies and a fraction fpr of the normal rows.

    Returns (true_alerts, false_alerts, precision) where precision = true / (true + false).
    """
    raise NotImplementedError("TODO milestone 5: expected_alerts")


def run_detectors(X, seed=0):
    """Fit the three unsupervised detectors on X and return {name: scores} for "kmeans", "pca", "iforest"
    and "combined". Use kmeans(X, 3, seed, n_init=5), pca(X, 2, seed), fit_iforest(X, 100, 128, seed); score
    with centre_distance_scores, pca_residual_scores and anomaly_score; "combined" is combine_max of the three.
    """
    raise NotImplementedError("TODO milestone 5: run_detectors")
