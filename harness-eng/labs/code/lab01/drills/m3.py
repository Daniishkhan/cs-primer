# Drill: A10 Lab 1, milestone 3 of 6: AIDE's selection rule
# Everything else in this file is already written. Fill in:
#     aide_policy
# Check it with: python3 check.py 3

"""Lab 1: Greedy versus Tree Search.  Reference solution.

A toy ML-style task, a seeded stand-in for the model that proposes edits, a
greedy hill-climber, an AIDE-style tree, a paired comparison and a hacking
probe. Standard library only. Everything is seeded, so every run prints the
same numbers.

The pieces you write are marked "MILESTONE n". Everything else is given.
"""
import math
import random
from dataclasses import dataclass, field, replace
from typing import List, Optional, Tuple

# ── Constants ────────────────────────────────────────────────────────────
N_TRAIN, N_PUBLIC, N_PRIVATE = 60, 30, 400   # rows in each split
NOISE = 0.5                                  # label noise, standard deviation
LAMBDAS = (0.01, 0.1, 1.0, 10.0)             # the ridge grid the agent tunes
BAD_SPLIT = "unknown split"


class ConfigError(Exception):
    """The candidate crashed: a bad index, a missing file, a singular fit."""


# ── The task and its three splits ────────────────────────────────────────
@dataclass(frozen=True)
class Config:
    """One candidate 'program': which features, how much shrinkage, a flag.

    features  indices of the columns the model uses
    lam       ridge penalty, one of LAMBDAS
    peek      True means "read the public labels from the leftover cache
              file instead of learning anything" (the hacking probe)
    """
    features: frozenset = frozenset()
    lam: float = 1.0
    peek: bool = False


@dataclass
class Task:
    """Rows are (x, y). The agent sees `train` and a public score; only the
    evaluator reads `private`. `cache` is the file the harness leaves behind:
    in a leaky harness it holds the public labels."""
    n_features: int
    useful: Tuple[int, ...]
    weights: Tuple[float, ...]
    train: list
    public: list
    private: list
    leaky: bool = True

    @property
    def cache(self) -> Optional[list]:
        return [y for _, y in self.public] if self.leaky else None


def make_task(task_seed: int, n_features: int = 24, n_useful: int = 3,
              leaky: bool = True) -> Task:
    """y = a weighted sum of n_useful columns + noise; the other columns are
    noise. The share n_useful / n_features is the opportunity density: with
    few useful columns, most edits do nothing."""
    rng = random.Random(f"task-{task_seed}-{n_features}-{n_useful}")
    useful = tuple(sorted(rng.sample(range(n_features), n_useful)))
    scale = math.sqrt(3.0 / n_useful)        # keeps the signal's size fixed
    weights = tuple(rng.choice((-1, 1)) * rng.uniform(1.0, 2.0) * scale
                    for _ in useful)

    def rows(n):
        out = []
        for _ in range(n):
            x = [rng.gauss(0, 1) for _ in range(n_features)]
            y = sum(w * x[j] for w, j in zip(weights, useful))
            out.append((x, y + rng.gauss(0, NOISE)))
        return out

    return Task(n_features, useful, weights, rows(N_TRAIN), rows(N_PUBLIC),
                rows(N_PRIVATE), leaky)


# ── Ridge regression by hand (given) ─────────────────────────────────────
def _design(x, features):
    return [1.0] + [x[j] for j in sorted(features)]


def _solve(a, b):
    """Gaussian elimination with partial pivoting; raises ConfigError."""
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(m[r][c]))
        if abs(m[p][c]) < 1e-12:
            raise ConfigError("singular fit")
        m[c], m[p] = m[p], m[c]
        for r in range(c + 1, n):
            f = m[r][c] / m[c][c]
            for k in range(c, n + 1):
                m[r][k] -= f * m[c][k]
    w = [0.0] * n
    for r in range(n - 1, -1, -1):
        w[r] = (m[r][n] - sum(m[r][k] * w[k] for k in range(r + 1, n))) / m[r][r]
    return w


def fit(task: Task, cfg: Config) -> List[float]:
    """Ridge weights on the training rows; the intercept is not penalised."""
    for j in cfg.features:
        if not (0 <= j < task.n_features):
            raise ConfigError(f"no such column: {j}")
    xs = [_design(x, cfg.features) for x, _ in task.train]
    ys = [y for _, y in task.train]
    k = len(xs[0])
    a = [[sum(r[i] * r[j] for r in xs) for j in range(k)] for i in range(k)]
    for i in range(1, k):
        a[i][i] += cfg.lam
    b = [sum(r[i] * y for r, y in zip(xs, ys)) for i in range(k)]
    return _solve(a, b)


# ── MILESTONE 1: the evaluator ───────────────────────────────────────────
def score_config(task: Task, cfg: Config, split: str) -> float:
    """Root-mean-squared error of the candidate on 'public' or 'private'.

    A normal candidate is fitted on task.train and predicts the split's rows.
    A candidate with peek=True does not learn: on the public split it returns
    the labels found in task.cache (RMSE 0 when the cache exists), and it
    raises ConfigError("no cache file") when the cache is gone; on the
    private split it can only predict the mean of the training labels.
    Any other split name raises ValueError(BAD_SPLIT).
    """
    if split not in ("public", "private"):
        raise ValueError(BAD_SPLIT)
    rows = task.public if split == "public" else task.private
    if cfg.peek:
        if split == "public":
            if task.cache is None:
                raise ConfigError("no cache file")
            return 0.0
        mean = sum(y for _, y in task.train) / len(task.train)
        preds = [mean] * len(rows)
    else:
        w = fit(task, cfg)
        preds = [sum(wi * v for wi, v in zip(w, _design(x, cfg.features)))
                 for x, _ in rows]
    se = sum((p - y) ** 2 for p, (_, y) in zip(preds, rows))
    return math.sqrt(se / len(rows))


# ── Nodes and journals (given) ───────────────────────────────────────────
@dataclass(eq=False)
class Node:
    """One tried candidate. `public` is None when it crashed. `private` is
    the evaluator's own record: a policy must never read it."""
    step: int
    stage: str                      # "draft", "debug" or "improve"
    parent: Optional["Node"]
    cfg: Config
    public: Optional[float]
    private: Optional[float]
    children: list = field(default_factory=list)

    @property
    def buggy(self) -> bool:
        return self.public is None

    @property
    def is_leaf(self) -> bool:
        return not self.children

    @property
    def debug_depth(self) -> int:
        d, n = 0, self
        while n.parent is not None and n.parent.buggy:
            d, n = d + 1, n.parent
        return d


class Journal:
    def __init__(self):
        self.nodes: List[Node] = []

    def add(self, node: Node):
        self.nodes.append(node)
        if node.parent is not None:
            node.parent.children.append(node)

    @property
    def good(self):
        return [n for n in self.nodes if not n.buggy]

    @property
    def buggy(self):
        return [n for n in self.nodes if n.buggy]

    @property
    def drafts(self):
        return [n for n in self.nodes if n.parent is None]

    def best(self) -> Optional[Node]:
        """The good node with the lowest PUBLIC score (ties: earliest)."""
        return min(self.good, key=lambda n: (n.public, n.step), default=None)


# ── MILESTONE 2: the greedy policy ───────────────────────────────────────
def greedy_policy(journal: Journal, rng: random.Random):
    """What to do next, for a hill-climber with a single incumbent.

    Returns ("draft", None), ("debug", node) or ("improve", node).
      * no good node yet and a buggy leaf exists: debug the most recent
        buggy leaf (the incumbent is being repaired);
      * no good node yet and nothing to repair: draft;
      * otherwise improve the best good node.
    `rng` is unused here; it is in the signature so every policy has the
    same shape.
    """
    if not journal.good:
        leaves = [n for n in journal.buggy if n.is_leaf]
        if leaves:
            return ("debug", leaves[-1])
        return ("draft", None)
    return ("improve", journal.best())


# ── MILESTONE 3: AIDE's selection rule ───────────────────────────────────
def aide_policy(journal: Journal, rng: random.Random, num_drafts: int = 5,
                debug_prob: float = 0.5, max_debug_depth: int = 3):
    """aideml's search policy, as read in agent.py (version 0.2.2):

      1. fewer than num_drafts draft nodes so far: draft a new one;
      2. with probability debug_prob, if a buggy LEAF with
         debug_depth <= max_debug_depth exists, debug one chosen at random;
      3. no good node: draft;
      4. otherwise improve the best good node.
    Call rng.random() exactly once per decision after step 1 (so seeded
    runs replay), and rng.choice(...) only when you really debug.
    """
    raise NotImplementedError("TODO milestone 3: aide_policy")


# ── The stand-in for the model that proposes edits (given) ───────────────
@dataclass
class Proposer:
    """A seeded stand-in for a coding model: it edits a config at random.
    `p_bug` is the chance an edit is malformed (a column that does not
    exist); `p_peek` the chance it notices the leftover cache file."""
    p_bug: float = 0.15
    p_peek: float = 0.0

    def draft(self, task: Task, rng: random.Random) -> Config:
        feats = frozenset(rng.sample(range(task.n_features), 3))
        cfg = Config(feats, rng.choice(LAMBDAS))
        return self._maybe_break(task, cfg, rng)

    def improve(self, task: Task, parent: Config, rng: random.Random):
        if rng.random() < self.p_peek:
            return replace(parent, peek=True)
        kind = rng.random()
        if kind < 0.25:                      # change the shrinkage
            i = LAMBDAS.index(parent.lam) + rng.choice((-1, 1))
            cfg = replace(parent, lam=LAMBDAS[min(max(i, 0), 3)])
        else:                                # toggle one feature
            j = rng.randrange(task.n_features)
            f = set(parent.features) ^ {j}
            cfg = replace(parent, features=frozenset(f))
        return self._maybe_break(task, cfg, rng)

    def debug(self, task: Task, parent: Config, rng: random.Random):
        good = frozenset(j for j in parent.features
                         if 0 <= j < task.n_features)
        return replace(parent, features=good, peek=False)

    def _maybe_break(self, task, cfg, rng):
        if rng.random() < self.p_bug:        # a column that does not exist
            return replace(cfg, features=cfg.features | {task.n_features + 1})
        return cfg


# ── The search loop (given) ──────────────────────────────────────────────
def run_search(task: Task, proposer: Proposer, steps: int, seed: int,
               policy) -> Journal:
    """Spend exactly `steps` nodes. Each step: the policy picks an action,
    the proposer writes a config, the evaluator scores it on the PUBLIC
    split (the private score is recorded for reporting, never used)."""
    rng = random.Random(seed)
    journal = Journal()
    for step in range(steps):
        stage, parent = policy(journal, rng)
        if stage == "draft":
            cfg = proposer.draft(task, rng)
        elif stage == "debug":
            cfg = proposer.debug(task, parent.cfg, rng)
        else:
            cfg = proposer.improve(task, parent.cfg, rng)
        try:
            pub = score_config(task, cfg, "public")
            priv = score_config(task, cfg, "private")
        except ConfigError:
            pub = priv = None
        journal.add(Node(step, stage, parent, cfg, pub, priv))
    return journal


def final_private(journal: Journal) -> Optional[float]:
    """The number a run reports: the private score of the node that the
    PUBLIC score selected."""
    best = journal.best()
    return None if best is None else best.private


# ── MILESTONE 4: paired comparison with a confidence interval ────────────
def paired_ci(a: List[float], b: List[float], n_boot: int = 2000,
              seed: int = 0) -> Tuple[float, float, float]:
    """Mean of (a - b) over paired seeds, with a 95% percentile bootstrap
    interval: resample the PAIRS with replacement n_boot times, take each
    resample's mean difference, return (mean, 2.5th percentile,
    97.5th percentile) using sorted()[int(0.025 * n_boot)] and
    sorted()[int(0.975 * n_boot) - 1]."""
    assert len(a) == len(b) and a, "need paired, non-empty lists"
    d = [x - y for x, y in zip(a, b)]
    rng = random.Random(seed)
    n = len(d)
    means = sorted(sum(d[rng.randrange(n)] for _ in range(n)) / n
                   for _ in range(n_boot))
    return (sum(d) / n, means[int(0.025 * n_boot)],
            means[int(0.975 * n_boot) - 1])


def compare(n_useful: int, seeds, steps: int = 20,
            proposer: Optional[Proposer] = None):
    """Greedy and tree on the same tasks and the same seeds. Returns
    (greedy private scores, tree private scores); a crashed run counts as
    the training-mean baseline."""
    proposer = proposer or Proposer()
    g, t = [], []
    for s in seeds:
        task = make_task(s, 24, n_useful)
        base = score_config(task, Config(frozenset(), 1.0), "private")
        for out, pol in ((g, greedy_policy), (t, aide_policy)):
            r = final_private(run_search(task, proposer, steps, 1000 + s, pol))
            out.append(base if r is None else r)
    return g, t


# ── MILESTONE 5: opportunity density ─────────────────────────────────────
def realised_density(task: Task, proposer: Proposer, cfg: Config,
                     n: int, seed: int, min_gain: float = 0.05) -> float:
    """Of n proposed improve-edits from `cfg`, the fraction whose PUBLIC
    score is lower (better) than cfg's by MORE than min_gain, the noise
    floor below which a change is not counted as progress. A crashed edit
    counts as not improving. Draw edits with one random.Random(seed)."""
    rng = random.Random(seed)
    base = score_config(task, cfg, "public")
    good = 0
    for _ in range(n):
        new = proposer.improve(task, cfg, rng)
        try:
            good += score_config(task, new, "public") < base - min_gain
        except ConfigError:
            pass
    return good / n


# ── MILESTONE 6: the hacking probe ───────────────────────────────────────
def hack_flags(journal: Journal, margin: float = 0.5) -> List[Node]:
    """Nodes whose public score is suspiciously better than their private
    one: public is not None and private - public > margin."""
    return [n for n in journal.nodes
            if n.public is not None and n.private - n.public > margin]


def hacking_rate(journals: List[Journal], margin: float = 0.5) -> float:
    """Fraction of runs whose SELECTED (best-by-public) node is flagged by
    hack_flags. Runs with no good node count as not hacked."""
    hit = 0
    for j in journals:
        best = j.best()
        hit += best is not None and best in hack_flags(j, margin)
    return hit / len(journals)
