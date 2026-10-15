# Drill: A7 Lab 4, milestone 3 of 5: which answer to refine (step 2 of 2)
# Everything else in this file is already written. Fill in:
#     pick_parent
# Check it with: python3 check.py 3

"""Lab 4: Adaptive Branching over Many Models (reference solution).

Pure Python, no clock, no network, no real model. Every random number comes from a seeded
random.Random. The models are numeric stand-ins: each call returns the score a verifier would give
the answer (0 to 1), drawn from a distribution that depends on the model. Chapter 8's question is
asked of them: with a fixed number of calls, should the next call sample a new answer (go wider),
refine an old one (go deeper), and with which model?

What YOU write is marked TODO (this file is the finished version):

    1  coverage, expected_best_of_n, WiderOnly, DeeperOnly, run_search     the loop and two fixed strategies
    2  shrunk_mean, thompson_draw, TwoArmPolicy                            wider or deeper, learned from gains
    3  parent_weights, pick_parent                                         which answer to refine
    4  MultiModelPolicy, model_shares                                      adding "which model" as a third choice
    5  solve_rate, calls_to_solve, mean_ci, evaluate_policy                an honest scoreboard

Conventions (they match chapter 8): an answer is a node with a verifier score in [0, 1]; going
deeper creates a child of an existing node; the GAIN of a call is how far its answer lands above the
best score so far (0 if it does not beat it); an action is ("wider", model) or ("deeper", node_id, model).
"""
import math
import random
import statistics
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


# =============================================================================
# GIVEN: the world. Stand-in models, tasks and the environment that counts calls
# =============================================================================
@dataclass(frozen=True)
class ModelSpec:
    """How one stand-in model behaves on one kind of task.

    A FRESH answer scores s = U ** fresh_a with U uniform on [0, 1]: fresh_a = 1 is a fair coin, 3 mostly
    mediocre. It also gets a hidden CEILING, the best score any refinement of it can ever reach:
    s + (1 - s) * f, where f = ceiling + spread * (2V - 1) with V uniform, clipped to [0, 1]. (A model whose
    fresh answers start down a dead-end approach has a low `ceiling`: repairs inherit the mistake.)
    A REFINED answer moves a fraction `gain` of the way from its parent's score to the parent's ceiling,
    plus Gaussian noise of standard deviation `noise`, clipped to [0, ceiling]. cost is what one call costs
    (reported, never used to stop a search)."""
    name: str
    cost: float
    fresh_a: float
    gain: float
    noise: float = 0.05
    ceiling: float = 1.0
    spread: float = 0.0


@dataclass(frozen=True)
class Task:
    """A kind of task: the models available on it."""
    name: str
    models: Tuple[ModelSpec, ...]


FAMILIES = {
    # feedback helps every model; the larger the model, the better and the dearer
    "refinable": Task("refinable", (ModelSpec("small", 1, 2.5, 0.30), ModelSpec("medium", 2, 2.0, 0.35),
                                    ModelSpec("large", 5, 1.6, 0.40))),
    # feedback is useless: refining is just another noisy draw
    "lottery": Task("lottery", (ModelSpec("small", 1, 2.5, 0.0), ModelSpec("medium", 2, 2.0, 0.0),
                                ModelSpec("large", 5, 1.6, 0.0))),
    # refinement stalls at a hidden ceiling that differs from answer to answer
    "plateau": Task("plateau", (ModelSpec("only", 1, 8.0, 0.80, 0.02, ceiling=0.70, spread=0.30),)),
    # division of labour: one model starts good approaches, another repairs them well
    "split": Task("split", (ModelSpec("drafter", 2, 5.0, 0.00, 0.02, ceiling=0.97),
                            ModelSpec("editor", 2, 6.0, 0.60, 0.05, ceiling=0.25),
                            ModelSpec("small", 1, 5.0, 0.15, 0.05, ceiling=0.60))),
}
TARGET = 0.9            # a verifier score at or above this counts as solved


@dataclass
class Node:
    id: int
    parent: Optional[int]
    score: float
    ceiling: float
    model: int
    depth: int
    kids: int = 0


class BudgetExhausted(Exception):
    pass


class Env:
    """One search problem: a task, a call budget and a seeded stream of answers.

    env.nodes is the list of answers so far (node i has id i). env.calls_left counts down; env.spent adds up
    the cost of the models used. apply() makes exactly one model call."""

    def __init__(self, task, budget, seed):
        self.task, self.budget = task, budget
        self.rng = random.Random(seed)
        self.nodes: List[Node] = []
        self.calls = 0
        self.spent = 0.0

    @property
    def calls_left(self):
        return self.budget - self.calls

    @property
    def n_models(self):
        return len(self.task.models)

    @property
    def best(self):
        """The best node so far (the lowest id on a tie), or None before the first call."""
        return max(self.nodes, key=lambda n: (n.score, -n.id)) if self.nodes else None

    @property
    def best_score(self):
        return self.best.score if self.nodes else 0.0

    def apply(self, action):
        """Make one call. action is ("wider", model) or ("deeper", node_id, model). Returns the new Node."""
        if self.calls_left <= 0:
            raise BudgetExhausted(f"all {self.budget} calls are used")
        kind = action[0]
        if kind == "wider" and len(action) == 2:
            m = action[1]
            spec = self._spec(m)
            s = self.rng.random() ** spec.fresh_a
            f = min(1.0, max(0.0, spec.ceiling + spec.spread * (2 * self.rng.random() - 1)))
            ceiling = s + (1 - s) * f
            node = Node(len(self.nodes), None, s, ceiling, m, 0)
        elif kind == "deeper" and len(action) == 3:
            pid, m = action[1], action[2]
            if not (isinstance(pid, int) and 0 <= pid < len(self.nodes)):
                raise ValueError(f"cannot refine node {pid!r}: there are {len(self.nodes)} nodes")
            spec, parent = self._spec(m), self.nodes[pid]
            s = parent.score + spec.gain * (parent.ceiling - parent.score) + self.rng.gauss(0, spec.noise)
            s = min(parent.ceiling, max(0.0, s))
            node = Node(len(self.nodes), pid, s, parent.ceiling, m, parent.depth + 1)
            parent.kids += 1
        else:
            raise ValueError(f"bad action {action!r}")
        self.nodes.append(node)
        self.calls += 1
        self.spent += spec.cost
        return node

    def _spec(self, m):
        if not (isinstance(m, int) and 0 <= m < len(self.task.models)):
            raise ValueError(f"no model {m!r}: this task has {len(self.task.models)}")
        return self.task.models[m]


@dataclass
class Step:
    call: int            # 1-based number of the call
    action: tuple
    node: int            # id of the answer it produced
    model: int
    score: float         # that answer's verifier score
    gain: float          # max(0, score - best score before this call)
    best: float          # best score after this call


@dataclass
class SearchResult:
    best: float          # best verifier score found
    calls: int           # calls actually made
    spend: float         # total cost of those calls
    solved: bool         # True if a target was given and best >= target
    log: List[Step] = field(default_factory=list)


# =============================================================================
# Milestone 1: the loop and two fixed strategies
# =============================================================================
def coverage(p, n):
    """Chance that at least one of n independent answers is correct when each is correct with probability p."""
    return 1 - (1 - p) ** n


def expected_best_of_n(n, a=2.0):
    """Mean of the best of n fresh answers when one answer scores U ** a with U uniform on [0, 1].
    The maximum of n such scores has CDF x ** (n / a) on [0, 1], so its mean is 1 - 1 / (n / a + 1) = n / (n + a)."""
    return n / (n + a)


class WiderOnly:
    """Always sample a new answer from one model. choose(env, rng) returns an action."""

    def __init__(self, model=0):
        self.model = model

    def choose(self, env, rng):
        return ("wider", self.model)

    def observe(self, action, node, gain):
        pass


class DeeperOnly:
    """Sample one answer, then refine the best answer so far, again and again, with one model.
    (The best answer = env.best; the first call has nothing to refine.)"""

    def __init__(self, model=0):
        self.model = model

    def choose(self, env, rng):
        if not env.nodes:
            return ("wider", self.model)
        return ("deeper", env.best.id, self.model)

    def observe(self, action, node, gain):
        pass


def run_search(policy, env, rng, target=None):
    """Spend the budget: repeatedly ask policy.choose(env, rng) for an action, env.apply() it, compute the
    gain and tell the policy with policy.observe(action, node, gain).

    gain = max(0, node.score - the best score BEFORE this call), where the best score before the first call is 0.
    Stop when env.calls_left is 0, or, if `target` is given, as soon as the best score reaches it (early stopping).
    Return a SearchResult whose log has one Step per call."""
    log = []
    while env.calls_left > 0:
        before = env.best_score
        action = policy.choose(env, rng)
        node = env.apply(action)
        gain = max(0.0, node.score - before)
        policy.observe(action, node, gain)
        log.append(Step(env.calls, action, node.id, node.model, node.score, gain, env.best_score))
        if target is not None and env.best_score >= target:
            break
    solved = target is not None and env.best_score >= target
    return SearchResult(env.best_score, env.calls, env.spent, solved, log)


# =============================================================================
# Milestone 2: wider or deeper, learned from gains
# =============================================================================
def shrunk_mean(history, prior_mean=0.1, prior_weight=2):
    """Mean of the observed gains, pulled toward an optimistic prior as if the prior had been seen
    `prior_weight` times: (prior_mean * prior_weight + sum(history)) / (len(history) + prior_weight)."""
    return (prior_mean * prior_weight + sum(history)) / (len(history) + prior_weight)


def thompson_draw(history, rng, prior_mean=0.1, prior_weight=2, scale=0.2):
    """One Thompson-style draw for an arm: a Gaussian around shrunk_mean(history) whose spread shrinks
    as data arrives, scale / sqrt(len(history) + 1). Exactly one call to rng.gauss(mu, sd)."""
    n = len(history)
    mu = shrunk_mean(history, prior_mean, prior_weight)
    return rng.gauss(mu, scale / math.sqrt(n + 1))


class TwoArmPolicy:
    """Wider or deeper, with one model, decided by Thompson draws over the gains each action has delivered.

    self.hist = {"wider": [gains], "deeper": [gains]}. choose: before any answer exists the action is wider;
    afterwards draw thompson_draw for "wider" and then for "deeper" (in that order, from rng) and take the larger
    (a tie goes to "wider"). A deeper action refines the best answer so far when lam is None, and (from milestone 3)
    pick_parent(env.nodes, rng, lam) otherwise. observe appends the gain to the history of the action taken."""

    def __init__(self, model=0, lam=None):
        self.model, self.lam = model, lam
        self.hist = {"wider": [], "deeper": []}

    def choose(self, env, rng):
        if not env.nodes:
            return ("wider", self.model)
        w, d = thompson_draw(self.hist["wider"], rng), thompson_draw(self.hist["deeper"], rng)
        if w >= d:
            return ("wider", self.model)
        return ("deeper", env.best.id if self.lam is None else pick_parent(env.nodes, rng, self.lam), self.model)

    def observe(self, action, node, gain):
        self.hist[action[0]].append(gain)


# =============================================================================
# Milestone 3: which answer to refine
# =============================================================================
def sigmoid(x):
    return 1 / (1 + math.exp(-x))


def parent_weights(scores, kids, lam=10.0):
    """Chapter 10's weighted parent rule, normalised to sum to 1:
    weight_i = sigmoid(lam * (score_i - median(scores))) / (1 + kids_i).
    A high score raises a node's chance; every child it already has lowers it."""
    w = [sigmoid(lam * (s - statistics.median(scores))) / (1 + k) for s, k in zip(scores, kids)]
    total = sum(w)
    return [x / total for x in w]


def pick_parent(nodes, rng, lam=10.0):
    """The id of the node to refine: one draw, rng.choices(range(len(nodes)), weights)[0],
    with weights from parent_weights over the nodes' scores and kids."""
    raise NotImplementedError("TODO milestone 3: pick_parent")


# =============================================================================
# Milestone 4: many models
# =============================================================================
class MultiModelPolicy:
    """Wider or deeper, AND which model, as one Thompson choice over arms (kind, model).

    self.arms lists ("wider", 0), ("deeper", 0), ("wider", 1), ("deeper", 1), ... in that order, and
    self.hist maps each arm to its gains. choose: before any answer exists, ask for a wider call, with the arm
    ("wider", m) of the largest draw (one thompson_draw per wider arm, in arm order). Afterwards draw once for EVERY arm,
    in arm order, and take the largest (ties: the earlier arm). A deeper arm refines the best answer when lam is None
    and pick_parent(env.nodes, rng, lam) otherwise.
    observe appends the gain to the history of the arm (action[0], action[-1])."""

    def __init__(self, n_models, lam=None):
        self.lam = lam
        self.arms = [(kind, m) for m in range(n_models) for kind in ("wider", "deeper")]
        self.hist = {arm: [] for arm in self.arms}

    def choose(self, env, rng):
        if not env.nodes:
            draws = [(thompson_draw(self.hist[a], rng), -i, a) for i, a in enumerate(self.arms) if a[0] == "wider"]
            return ("wider", max(draws)[2][1])
        draws = [(thompson_draw(self.hist[a], rng), -i, a) for i, a in enumerate(self.arms)]
        kind, m = max(draws)[2]
        if kind == "wider":
            return ("wider", m)
        return ("deeper", env.best.id if self.lam is None else pick_parent(env.nodes, rng, self.lam), m)

    def observe(self, action, node, gain):
        self.hist[(action[0], action[-1])].append(gain)


def model_shares(log, kind, n_models):
    """For the steps of `kind` ("wider" or "deeper") in a search log, the fraction made by each model:
    a list of n_models numbers adding to 1, or all zeros if there were no such steps."""
    steps = [s for s in log if s.action[0] == kind]
    if not steps:
        return [0.0] * n_models
    return [sum(1 for s in steps if s.model == m) / len(steps) for m in range(n_models)]


# =============================================================================
# Milestone 5: an honest scoreboard
# =============================================================================
def solve_rate(results):
    """Fraction of results with solved == True."""
    return sum(r.solved for r in results) / len(results)


def calls_to_solve(results, penalty=None):
    """Median number of calls over the results; unsolved ones count as `penalty` calls (default: the largest
    number of calls any result used, plus 1, so an unsolved run is always worse than any solved one)."""
    if penalty is None:
        penalty = max(r.calls for r in results) + 1
    return statistics.median(r.calls if r.solved else penalty for r in results)


def mean_ci(values, z=1.96):
    """(mean, half_width) of a normal-approximation confidence interval for the mean:
    half_width = z * sample standard deviation / sqrt(n). Zero half-width for a single value."""
    n = len(values)
    mean = sum(values) / n
    if n < 2:
        return mean, 0.0
    sd = math.sqrt(sum((v - mean) ** 2 for v in values) / (n - 1))
    return mean, z * sd / math.sqrt(n)


def evaluate_policy(make_policy, task, budget, seeds, target=0.95):
    """Run make_policy() afresh on Env(task, budget, seed) for every seed, with policy randomness
    random.Random(seed + 7919) and early stopping at `target`. Return a dict with
    best (mean_ci of the best scores), solve_rate, calls (calls_to_solve), spend (mean spend) and runs (the results)."""
    runs = []
    for seed in seeds:
        env = Env(task, budget, seed)
        runs.append(run_search(make_policy(), env, random.Random(seed + 7919), target))
    return {"best": mean_ci([r.best for r in runs]), "solve_rate": solve_rate(runs),
            "calls": calls_to_solve(runs), "spend": sum(r.spend for r in runs) / len(runs), "runs": runs}
