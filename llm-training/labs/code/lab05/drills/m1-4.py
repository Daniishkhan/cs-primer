# Drill: A3 Lab 5, milestone 1 of 6: vectors of weights (step 4 of 6)
# Everything else in this file is already written. Fill in:
#     interpolate
# Check it with: python3 check.py 1

"""Lab 5: Evolutionary Model Merging.

Chapter 16 showed that fine-tunes of one base model can be combined by arithmetic on their weights,
and that a search over the recipe can overfit its own evaluation set. This lab builds the whole
loop on a network small enough to train in a fraction of a second:

    base model --fine-tune on task A, B, C--> three specialists
    task vectors (specialist - base) --> average, task arithmetic, TIES
    per-layer merge coefficients --> an evolution strategy that scores each recipe on a SEARCH split
    --> report the winner on a HELD-OUT split it never saw

Standard-library Python only; every random draw comes from a seeded random.Random.

Notation follows chapter 16: theta_base is the base, theta_t the specialist for task t, the task
vector is tau_t = theta_t - theta_base, and a merge is theta = theta_base + sum_t lambda_t tau_t
(here the coefficient may differ per layer). "keep" is TIES' kept fraction of each task vector.

A MODEL is a list of four flat lists [W1, b1, W2, b2]: W1 is H x D row-major, W2 is K x H
row-major. A TASK VECTOR has exactly the same shape. Tensors 0 and 1 form layer 0, tensors 2 and 3
form layer 1 (LAYER_OF). The classifier has K = 6 classes; task t owns two of them (TASKS), so a
specialist trained only on its own task's examples forgets the other four classes: that is the
interference a merge has to repair.

What is GIVEN: the network, training, the data, the world (base model, specialists, splits) and the
scoring helpers. What YOU write is marked TODO:

    1  task_vector, add_scaled, average_models, interpolate, vec_norm, cosine
    2  coeffs_from_vector, merge_coeffs, best_global_lambda
    3  trim_topk, elect_sign, disjoint_mean, ties_merge, merge_ties
    4  evolve
    5  search_recipe
    6  compare_methods, optimism, mean_table
"""
import math
import random
from collections import namedtuple

# =============================================================================
# GIVEN: the network and the task family
# =============================================================================
D, H, K = 8, 10, 6                      # input size, hidden units, classes
TASKS = [(0, 1), (2, 3), (4, 5)]        # task t owns the classes TASKS[t]
N_TASKS = len(TASKS)
LAYER_OF = [0, 0, 1, 1]                 # tensor index -> layer index
N_LAYERS = 2
RECIPE_DIM = {"global": 1, "task": N_TASKS, "layer": N_TASKS * N_LAYERS}
LAMBDA_GRID = [0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]


def init_model(rng):
    """Random initial weights: [W1, b1, W2, b2] as flat lists."""
    return [[rng.gauss(0, D ** -0.5) for _ in range(H * D)], [0.0] * H,
            [rng.gauss(0, H ** -0.5) for _ in range(K * H)], [0.0] * K]


def copy_model(m):
    return [list(t) for t in m]


def n_params(m):
    return sum(len(t) for t in m)


def forward(m, x):
    """Hidden activations (ReLU) and the K logits for one input vector x."""
    W1, b1, W2, b2 = m
    h = []
    for j in range(H):
        s = b1[j]
        o = j * D
        for i in range(D):
            s += W1[o + i] * x[i]
        h.append(s if s > 0.0 else 0.0)
    logits = []
    for k in range(K):
        s = b2[k]
        o = k * H
        for j in range(H):
            s += W2[o + j] * h[j]
        logits.append(s)
    return h, logits


def predict(m, x):
    logits = forward(m, x)[1]
    return max(range(K), key=lambda k: logits[k])


def accuracy(m, xs, ys):
    return sum(1 for x, y in zip(xs, ys) if predict(m, x) == y) / len(xs)


def softmax(z):
    top = max(z)
    e = [math.exp(v - top) for v in z]
    s = sum(e)
    return [v / s for v in e]


def train(m, xs, ys, steps, lr, rng, batch=16):
    """Minibatch SGD on the softmax cross-entropy. Returns a trained COPY of m."""
    m = copy_model(m)
    W1, b1, W2, b2 = m
    for _ in range(steps):
        gW1, gb1, gW2, gb2 = [0.0] * (H * D), [0.0] * H, [0.0] * (K * H), [0.0] * K
        for _ in range(batch):
            i = rng.randrange(len(xs))
            x = xs[i]
            h, logits = forward(m, x)
            g = softmax(logits)
            g[ys[i]] -= 1.0
            dh = [0.0] * H
            for k in range(K):
                gk = g[k] / batch
                gb2[k] += gk
                o = k * H
                for j in range(H):
                    gW2[o + j] += gk * h[j]
                    dh[j] += gk * W2[o + j]
            for j in range(H):
                if h[j] > 0.0:
                    gb1[j] += dh[j]
                    o = j * D
                    for q in range(D):
                        gW1[o + q] += dh[j] * x[q]
        for t, g in zip(m, (gW1, gb1, gW2, gb2)):
            for i in range(len(t)):
                t[i] -= lr * g[i]
    return m


def make_means(seed):
    """Six class centres in D dimensions, resampled until no two are closer than 2.4."""
    rng = random.Random(seed)
    while True:
        means = [[rng.gauss(0, 1.0) for _ in range(D)] for _ in range(K)]
        gaps = [math.dist(means[a], means[b]) for a in range(K) for b in range(a)]
        if min(gaps) >= 2.4:
            return means


def sample(means, classes, n, rng, noise=1.2):
    """n labelled points drawn uniformly from the given classes."""
    xs, ys = [], []
    for _ in range(n):
        y = rng.choice(classes)
        xs.append([c + rng.gauss(0, noise) for c in means[y]])
        ys.append(y)
    return xs, ys


# =============================================================================
# GIVEN: the world. A base model, three specialists, and two splits per task.
# =============================================================================
World = namedtuple("World", "seed base finetunes search hold")
# base:      the shared starting point (trained briefly on a little data from all three tasks)
# finetunes: [theta_0, theta_1, theta_2], each trained from base on ITS task's data only
# search:    [(xs, ys) per task], small: the only data a merge search may look at
# hold:      [(xs, ys) per task], larger: never used for any decision, only for the report


def make_world(seed, n_search=20, n_hold=300):
    means = make_means(seed)
    rng = random.Random(1000 * seed + 1)
    mx, my = [], []
    for cls in TASKS:
        x, y = sample(means, list(cls), 40, rng)
        mx += x
        my += y
    base = train(init_model(rng), mx, my, 60, 0.05, rng)
    finetunes = []
    for cls in TASKS:
        x, y = sample(means, list(cls), 200, rng)
        finetunes.append(train(base, x, y, 150, 0.05, rng))
    rs, rh = random.Random(1000 * seed + 2), random.Random(1000 * seed + 3)
    search = [sample(means, list(cls), n_search, rs) for cls in TASKS]
    hold = [sample(means, list(cls), n_hold, rh) for cls in TASKS]
    return World(seed, base, finetunes, search, hold)


def task_scores(model, split):
    """Accuracy (6-way) of `model` on each task's examples in `split`: a list of N_TASKS numbers."""
    return [accuracy(model, xs, ys) for xs, ys in split]


def mean_score(model, split):
    """Mean of the per-task accuracies. This is the number every merge is judged by."""
    s = task_scores(model, split)
    return sum(s) / len(s)


# =============================================================================
# MILESTONE 1: vectors of weights
# =============================================================================
def task_vector(finetuned, base):
    """tau = finetuned - base, tensor by tensor, as a new list of four lists (inputs untouched).

    task_vector([[3.0, 1.0], [2.0]], [[1.0, 1.0], [5.0]]) == [[2.0, 0.0], [-3.0]]
    """
    return [[f - b for f, b in zip(ft, bt)] for ft, bt in zip(finetuned, base)]


def add_scaled(base, vec, scale):
    """base + scale * vec as a new model (a merge with one task vector).

    add_scaled([[1.0, 2.0]], [[4.0, -2.0]], 0.5) == [[3.0, 1.0]]
    """
    return [[b + scale * v for b, v in zip(bt, vt)] for bt, vt in zip(base, vec)]


def average_models(models):
    """The elementwise mean of several models (same shapes), as a new model.

    Weight averaging, "model soup" style: average_models([a, b]) is the point halfway along the
    straight line between a and b in weight space.
    """
    n = len(models)
    return [[sum(vals) / n for vals in zip(*tensors)] for tensors in zip(*models)]


def interpolate(a, b, t):
    """(1 - t) * a + t * b, elementwise: t = 0 gives a, t = 1 gives b, t = 0.5 the average."""
    raise NotImplementedError("TODO milestone 1: interpolate")


def vec_norm(vec):
    """Euclidean (L2) norm over every entry of every tensor."""
    return math.sqrt(sum(v * v for t in vec for v in t))


def cosine(u, v):
    """Cosine similarity of two task vectors over all entries; 0.0 if either has zero norm.

    Near 0: the two tasks moved the weights in unrelated directions. Near 1: the same direction.
    """
    nu, nv = vec_norm(u), vec_norm(v)
    if nu == 0.0 or nv == 0.0:
        return 0.0
    dot = sum(a * b for tu, tv in zip(u, v) for a, b in zip(tu, tv))
    return dot / (nu * nv)


# =============================================================================
# MILESTONE 2: task arithmetic with per-layer coefficients
# =============================================================================
def coeffs_from_vector(w, mode):
    """Expand a recipe vector w into coeffs[t][l], the coefficient for task t in layer l.

        mode "global": len(w) == 1,            coeffs[t][l] = w[0]
        mode "task":   len(w) == N_TASKS,      coeffs[t][l] = w[t]
        mode "layer":  len(w) == N_TASKS * N_LAYERS,  coeffs[t][l] = w[t * N_LAYERS + l]

    Raise ValueError if the mode is unknown or len(w) is not RECIPE_DIM[mode]. Returns a list of
    N_TASKS lists of N_LAYERS floats.
    """
    if mode not in RECIPE_DIM or len(w) != RECIPE_DIM[mode]:
        raise ValueError(f"mode {mode!r} needs {RECIPE_DIM.get(mode)} numbers, got {len(w)}")
    if mode == "global":
        return [[w[0]] * N_LAYERS for _ in range(N_TASKS)]
    if mode == "task":
        return [[w[t]] * N_LAYERS for t in range(N_TASKS)]
    return [[w[t * N_LAYERS + l] for l in range(N_LAYERS)] for t in range(N_TASKS)]


def merge_coeffs(base, tvs, coeffs):
    """theta = base + sum_t coeffs[t][layer(k)] * tvs[t][k], tensor k by tensor k. A new model.

    `tvs` is a list of N_TASKS task vectors and coeffs[t][l] the coefficient of task t in layer l
    (tensor k belongs to layer LAYER_OF[k]). All-zero coefficients give the base back; a 1 for one
    task in both layers and 0 for the others gives that task's specialist back.
    """
    merged = []
    for k, tensor in enumerate(base):
        layer = LAYER_OF[k]
        merged.append([
            tensor[i] + sum(coeffs[t][layer] * tvs[t][k][i] for t in range(len(tvs)))
            for i in range(len(tensor))
        ])
    return merged


def best_global_lambda(base, tvs, split, grid=LAMBDA_GRID):
    """Plain task arithmetic with ONE coefficient: theta = base + lam * sum_t tau_t.

    Score each lam in `grid` with mean_score(.., split) and return (best_lam, best_score). On a tie
    keep the earlier (smaller) lam in the grid.
    """
    best = None
    for lam in grid:
        score = mean_score(merge_coeffs(base, tvs, coeffs_from_vector([lam], "global")), split)
        if best is None or score > best[1]:
            best = (lam, score)
    return best


# =============================================================================
# MILESTONE 3: TIES, trim / elect / disjoint mean
# =============================================================================
def trim_topk(vec, keep):
    """Keep the k = max(1, floor(keep * n + 0.5)) entries of largest |value| (n = len(vec)), zero
    the rest. If two entries have the same magnitude the LOWER index wins. Returns a new list.

    trim_topk([0.1, -0.9, 0.4, 0.4], 0.5) == [0.0, -0.9, 0.4, 0.0]
    """
    n = len(vec)
    k = max(1, math.floor(keep * n + 0.5))
    order = sorted(range(n), key=lambda i: (-abs(vec[i]), i))
    kept = set(order[:k])
    return [v if i in kept else 0.0 for i, v in enumerate(vec)]


def elect_sign(vecs):
    """For each position, the sign (+1.0, -1.0 or 0.0) of the SUM of the vectors' entries there.

    The sign with more total mass wins, so a large +0.5 outvotes a small -0.2. `vecs` is a list of
    equal-length flat lists.
    """
    out = []
    for col in zip(*vecs):
        s = sum(col)
        out.append(1.0 if s > 0 else -1.0 if s < 0 else 0.0)
    return out


def disjoint_mean(vecs, signs):
    """For each position, the mean of the NONZERO entries whose sign equals signs[i]; 0.0 if there
    are none. Entries that disagree with the elected sign (and zeros) are left out of the mean."""
    out = []
    for col, sg in zip(zip(*vecs), signs):
        agree = [v for v in col if v != 0.0 and sg != 0.0 and (v > 0) == (sg > 0)]
        out.append(sum(agree) / len(agree) if agree else 0.0)
    return out


def ties_merge(tvs, keep):
    """TIES on a list of task vectors: trim each tensor of each task vector to its top `keep`
    fraction, elect a sign per position, take the disjoint mean. Trimming is PER TENSOR (so the
    small bias vectors keep entries too). Returns one merged task vector (four lists)."""
    merged = []
    for k in range(len(tvs[0])):
        trimmed = [trim_topk(tv[k], keep) for tv in tvs]
        merged.append(disjoint_mean(trimmed, elect_sign(trimmed)))
    return merged


def merge_ties(base, tvs, keep, lam):
    """base + lam * ties_merge(tvs, keep), as a new model."""
    return add_scaled(base, ties_merge(tvs, keep), lam)


# =============================================================================
# MILESTONE 4: an evolution strategy
# =============================================================================
EvoResult = namedtuple("EvoResult", "x fitness history evals")
# x: best vector found; fitness: its score; history: best fitness after the initial pool and
# after each generation (length generations + 1); evals: number of calls made to fitness


def evolve(fitness, x0, rng, mu=4, lam=16, generations=15, sigma=0.4, decay=0.85):
    """A (mu + lam) evolution strategy that MAXIMISES fitness(x) over lists of floats.

    1. Initial pool: x0 itself and mu - 1 mutants of it (each coordinate plus rng.gauss(0, sigma)).
       Evaluate each exactly once. The mu best (highest fitness) become the parents.
    2. Each generation: make lam children, child j from parents[j % mu] by adding rng.gauss(0,
       sigma) to every coordinate; evaluate each child once. Pool = parents + children; the mu best
       of the pool are the next parents. Then sigma *= decay.
    Sorting must be stable, so on equal fitness an earlier individual (a parent before a child, an
    earlier child before a later one, x0 before its mutants) wins. Never mutate x0 or hand the
    same list object to fitness twice.

    Returns EvoResult(x, fitness, history, evals): the best individual, its fitness, the best
    fitness after the initial pool and after each generation, and mu + lam * generations.
    """
    pool = [(fitness(list(x0)), list(x0))]
    for _ in range(mu - 1):
        x = [v + rng.gauss(0.0, sigma) for v in x0]
        pool.append((fitness(x), x))
    pool.sort(key=lambda p: -p[0])                  # stable: earlier wins ties
    parents = pool[:mu]
    history = [parents[0][0]]
    for _ in range(generations):
        children = []
        for j in range(lam):
            x = [v + rng.gauss(0.0, sigma) for v in parents[j % mu][1]]
            children.append((fitness(x), x))
        pool = parents + children                   # elitist: parents compete with children
        pool.sort(key=lambda p: -p[0])
        parents = pool[:mu]
        history.append(parents[0][0])
        sigma *= decay
    return EvoResult(parents[0][1], parents[0][0], history, mu + lam * generations)


# =============================================================================
# MILESTONE 5: search for a merge recipe
# =============================================================================
def search_recipe(world, mode="layer", seed=0, mu=4, lam=16, generations=15, sigma=0.4, decay=0.85):
    """Evolve the coefficients of a task-arithmetic merge against world.search ONLY.

    The recipe vector w has RECIPE_DIM[mode] entries (see coeffs_from_vector). Start from the
    plain average: x0 = [1 / N_TASKS] * RECIPE_DIM[mode]. The fitness of w is
    mean_score(merge_coeffs(world.base, tvs, coeffs_from_vector(w, mode)), world.search), where
    tvs are the task vectors of world.finetunes. Run evolve with rng = random.Random(seed).

    Returns (w, result): the best recipe vector and the full EvoResult.
    """
    tvs = [task_vector(ft, world.base) for ft in world.finetunes]

    def fitness(w):
        merged = merge_coeffs(world.base, tvs, coeffs_from_vector(w, mode))
        return mean_score(merged, world.search)

    result = evolve(fitness, [1.0 / N_TASKS] * RECIPE_DIM[mode], random.Random(seed),
                    mu, lam, generations, sigma, decay)
    return result.x, result


# =============================================================================
# MILESTONE 6: the honest comparison
# =============================================================================
METHODS = ["base", "oracle", "average", "task arithmetic", "TIES", "evolved"]


def compare_methods(world, seed=0, keep=0.3, mode="layer"):
    """Score six candidates on the search split AND the held-out split.

    Returns a dict {name: (search_score, hold_score)} with the keys of METHODS, in that order:
      "base"             the base model itself
      "oracle"           specialist t scored on task t only, averaged over tasks (not a single
                         model: it is what a perfect router between the specialists would get)
      "average"          average_models of the three specialists
      "task arithmetic"  best_global_lambda chosen on world.search
      "TIES"             merge_ties with the given `keep`; lam chosen from LAMBDA_GRID by the
                         mean_score on world.search (first best on ties)
      "evolved"          search_recipe(world, mode, seed), then scored on both splits
    Every DECISION (lambda, recipe) may use world.search only. world.hold is read to report.
    """
    base, fts = world.base, world.finetunes
    tvs = [task_vector(ft, base) for ft in fts]

    def both(model):
        return (mean_score(model, world.search), mean_score(model, world.hold))

    table = {"base": both(base)}
    table["oracle"] = (
        sum(task_scores(fts[t], world.search)[t] for t in range(N_TASKS)) / N_TASKS,
        sum(task_scores(fts[t], world.hold)[t] for t in range(N_TASKS)) / N_TASKS,
    )
    table["average"] = both(average_models(fts))
    lam, _ = best_global_lambda(base, tvs, world.search)
    table["task arithmetic"] = both(merge_coeffs(base, tvs, coeffs_from_vector([lam], "global")))
    best = max(LAMBDA_GRID, key=lambda l: mean_score(merge_ties(base, tvs, keep, l), world.search))
    table["TIES"] = both(merge_ties(base, tvs, keep, best))
    w, _ = search_recipe(world, mode, seed)
    table["evolved"] = both(merge_coeffs(base, tvs, coeffs_from_vector(w, mode)))
    return table


def optimism(table, name):
    """How much better a method looked on the search split than it really is: search - hold."""
    search, hold = table[name]
    return search - hold


def mean_table(tables):
    """Average a list of compare_methods results over worlds: {name: (mean search, mean hold)}."""
    n = len(tables)
    return {name: (sum(t[name][0] for t in tables) / n, sum(t[name][1] for t in tables) / n)
            for name in tables[0]}


def print_table(table):
    print(f"{'method':<17}{'search':>8}{'held-out':>10}{'optimism':>10}")
    for name in table:
        s, h = table[name]
        print(f"{name:<17}{s:8.3f}{h:10.3f}{s - h:+10.3f}")


if __name__ == "__main__":
    tables = [compare_methods(make_world(s)) for s in range(4)]
    print_table(mean_table(tables))
