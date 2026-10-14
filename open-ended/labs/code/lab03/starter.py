"""Lab 3: A Mini FunSearch.

Pure Python, no clock, no network. Every random number comes from a seeded random.Random.
The task is the online bin packing of chapter 9: bins of capacity 100, items of size 20 to 60
arriving one at a time, and one function to evolve:

    def priority(item, rem):      # rem = space left in a bin; the item goes to the feasible bin
        ...                       # with the highest priority

The "language model" is a deterministic stand-in: a seeded function that edits the program's
syntax tree. It is NOT a language model. The loop around it is the loop of chapter 9.

What is GIVEN: the instances, the exceptions, Fuel and Outcome, the grammar of edits, the stand-in
model and the shapes of Island and Database. What YOU write is marked TODO:

    1  validate, instrument, compile_restricted      run untrusted code with a whitelist and a fuel budget
    2  pack, evaluate                                a total evaluator: every outcome becomes a result
    3  edit_constant, edit_operator, mutate          the mutation operator, on the AST
    4  softmax_weights, Island                       clusters by signature, best-shot sampling
    5  Database.reseed, Database.best                islands, and replacing the weakest
    6  funsearch, report                             the whole loop, reported on held-out instances

Conventions (they match chapter 9): a program is a source string; its score is the mean number
of bins over a set of instances (lower is better); its fitness is minus that score (higher is better);
its signature is the tuple of bin counts it gets on each instance.
"""
import ast
import copy
import math
import random
from dataclasses import dataclass, field

CAP = 100
SEED_SRC = "def priority(item, rem):\n    gap = rem - item\n    return -gap\n"
FIRST_FIT_SRC = "def priority(item, rem):\n    return 0\n"

TRAIN_SEEDS = tuple(range(10))             # instances the search may look at
TEST_SEEDS = tuple(range(100, 130))        # held-out instances: only used for the final report


# =============================================================================
# GIVEN: problem instances and the exceptions of the sandbox
# =============================================================================
def instance(seed, n=300):
    """n item sizes in 20..60 (capacity is 100); the same seed always gives the same items."""
    rng = random.Random(seed)
    return [rng.randint(20, 60) for _ in range(n)]


def make_instances(seeds, n=300):
    return [instance(s, n) for s in seeds]


def lower_bound(items):
    """No packing, online or not, can use fewer bins than total size / capacity."""
    return sum(items) / CAP


class Rejected(Exception):
    """The source is not allowed to run at all (checked before any execution)."""


class OutOfFuel(Exception):
    """The program used more steps than its budget."""


class Fuel:
    """A shared step counter. instrument() makes candidate code call tick() at function entry
    and once per loop iteration, so any loop that does not stop runs the fuel out."""

    def __init__(self, budget):
        self.budget = budget
        self.used = 0

    def tick(self):
        self.used += 1
        if self.used > self.budget:
            raise OutOfFuel(f"more than {self.budget} steps")


MAX_CHARS = 2000
MAX_NODES = 150
SAFE_CALLS = ("abs", "min", "max")
ALLOWED_NODES = (
    ast.Module, ast.FunctionDef, ast.arguments, ast.arg,
    ast.Return, ast.Assign, ast.AugAssign, ast.If, ast.While, ast.Pass,
    ast.Name, ast.Load, ast.Store, ast.Constant,
    ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.Compare, ast.IfExp, ast.Call,
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod,
    ast.UAdd, ast.USub, ast.Not, ast.And, ast.Or,
    ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
)


# =============================================================================
# Milestone 1: run untrusted code with a whitelist and a fuel budget
# =============================================================================
def validate(src):
    """Parse `src` and return its ast.Module, or raise Rejected(reason).

    Accept exactly one top-level `def priority(item, rem):` with plain positional arguments (and no
    other function definition anywhere inside it), whose every node type is in ALLOWED_NODES. Also require:
      * len(src) <= MAX_CHARS and at most MAX_NODES nodes in the tree;
      * constants are int, float or bool (so `while True:` parses), with absolute value at most 1e9;
      * calls are `abs`, `min` or `max` by bare name, with positional arguments only;
      * no name starts with an underscore (this also keeps candidates away from the hidden _tick);
      * every name that is read is a parameter, a name assigned somewhere in the function, or a safe call.
    """
    raise NotImplementedError("TODO milestone 1: validate")



def instrument(tree):
    """Return a NEW tree (leave `tree` untouched) in which the function body and every while-loop body begin
    with a call `_tick()`, and every int constant has become a float, so nothing can grow without bound.
    Call ast.fix_missing_locations on the result before it is compiled."""
    raise NotImplementedError("TODO milestone 1: instrument")


def compile_restricted(src, fuel):
    """validate, instrument, compile and exec `src`; return the `priority` function.

    The namespace holds only abs, min, max and the fuel's tick, which is registered under the name _tick
    (the name instrument() calls): no __import__, no open, no getattr."""
    raise NotImplementedError("TODO milestone 1: compile_restricted")


# =============================================================================
# Milestone 2: a total evaluator
# =============================================================================
@dataclass
class Outcome:
    """What the evaluator says about one program. status is one of
    'ok', 'rejected', 'error', 'timeout', 'bad_value'. Only 'ok' has a score."""
    status: str
    score: float = math.inf         # mean bins over the instances (lower is better)
    bins: tuple = ()                # bins used on each instance: the program's signature
    detail: str = ""
    steps: int = 0

    @property
    def ok(self):
        return self.status == "ok"

    @property
    def fitness(self):
        return -self.score          # higher is better; -inf for programs that did not run


def pack(items, priority):
    """Online bin packing. Each item goes to the feasible bin (rem >= item) with the highest
    priority(item, rem); ties go to the earliest bin. If none fits, open a new bin.
    Return the number of bins used."""
    raise NotImplementedError("TODO milestone 2: pack")


FUEL = 400_000          # steps one evaluation may use, over all instances


def evaluate(src, instances, fuel_budget=FUEL):
    """Score `src` on a list of instances (each a list of item sizes). NEVER raises.

    rejected   validate() refused it (detail = the reason)
    timeout    ran out of fuel
    error      any exception while running (ZeroDivisionError, NameError, ...)
    bad_value  priority returned something that is not a finite int/float (a bool, a string, nan, inf)
    ok         score = mean bins, bins = per-instance bins, steps = fuel used
    """
    raise NotImplementedError("TODO milestone 2: evaluate")


# =============================================================================
# GIVEN: the program-editing toolkit (the grammar of edits)
# =============================================================================
ARITH = (ast.Add, ast.Sub, ast.Mult)
CMP = (ast.Lt, ast.LtE, ast.Gt, ast.GtE)
THRESHOLDS = tuple(range(0, 41))
PAYOFFS = (1, 2, 5, 10, 20, 50, 100, 200, 1000)


def canonical(src):
    """The one text for a syntax tree, so equal programs are equal strings."""
    return ast.unparse(ast.parse(src))


def is_valid(src):
    try:
        validate(src)
        return True
    except Rejected:
        return False


def scope_names(tree):
    fn = tree.body[0]
    names = ["item", "rem"]
    for n in ast.walk(fn):
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store) and n.id not in names:
            names.append(n.id)
    return names


def replace_node(tree, old, new):
    """Replace the node `old` (compared by identity) by `new`, anywhere in the tree."""
    class R(ast.NodeTransformer):
        def generic_visit(self, node):
            for field_name, value in ast.iter_fields(node):
                if isinstance(value, list):
                    node_list = []
                    for item in value:
                        if isinstance(item, ast.AST):
                            item = new if item is old else self.visit(item)
                        node_list.append(item)
                    value[:] = node_list
                elif isinstance(value, ast.AST):
                    setattr(node, field_name, new if value is old else self.visit(value))
            return node
    R().visit(tree)


def rule_position(body):
    """Where a new `if` rule goes: after the leading assignments (so the names it reads exist), before the rest."""
    i = 0
    while i < len(body) and isinstance(body[i], ast.Assign):
        i += 1
    return i


def _name(s):
    return ast.Name(s, ast.Load())


def _num(v):
    return ast.Constant(v)


def _rhs(rng, names):
    return _name(rng.choice(names)) if rng.random() < 0.3 else _num(rng.choice(THRESHOLDS))


def edit_insert_rule(tree, rng):
    """Insert `if <name> <cmp> <name or number>: return <payoff>` after the function's leading assignments."""
    names = scope_names(tree)
    lhs = _name(rng.choice(names[2:] or names))
    op = rng.choice(CMP + (ast.Eq,))()
    test = ast.Compare(lhs, [op], [_rhs(rng, names)])
    kind = rng.random()
    if kind < 0.4:
        value = _num(rng.choice(PAYOFFS))
    else:
        base = ast.UnaryOp(ast.USub(), _name(rng.choice(names[2:] or names)))
        value = ast.BinOp(base, ast.Sub(), _num(rng.choice(PAYOFFS)))
    body = tree.body[0].body
    body.insert(rule_position(body), ast.If(test, [ast.Return(value)], []))
    return True


def edit_shape(tree, rng):
    """Wrap one expression of a return statement: abs(e), -e, e - c, e % c, min(e, c) or max(e, c)."""
    rets = [n for n in ast.walk(tree) if isinstance(n, ast.Return) and n.value is not None]
    if not rets:
        return False
    ret = rng.choice(rets)
    sub = [n for n in ast.walk(ret.value) if isinstance(n, (ast.Name, ast.BinOp, ast.UnaryOp, ast.Call))]
    target = rng.choice(sub) if sub else ret.value
    kind = rng.randrange(6)
    c = _num(rng.choice(THRESHOLDS[2:]))
    new = [lambda: ast.Call(_name("abs"), [target], []),
           lambda: ast.UnaryOp(ast.USub(), target),
           lambda: ast.BinOp(target, ast.Sub(), c),
           lambda: ast.BinOp(target, ast.Mod(), c),
           lambda: ast.Call(_name("min"), [target, c], []),
           lambda: ast.Call(_name("max"), [target, c], [])][kind]()
    if target is ret.value:
        ret.value = new
    else:
        replace_node(ret, target, new)
    return True


def edit_replace_name(tree, rng):
    """Replace one name that is read by another name in scope."""
    names = scope_names(tree)
    sites = [n for n in ast.walk(tree.body[0]) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)
             and n.id in names]
    if not sites:
        return False
    node = rng.choice(sites)
    node.id = rng.choice(names)
    return True


def edit_delete(tree, rng):
    """Delete one statement from the body (never the last one)."""
    body = tree.body[0].body
    if len(body) < 2:
        return False
    del body[rng.randrange(len(body) - 1)]
    return True


def edit_borrow(tree, rng, donor_src):
    """Copy one `if` rule from another program into this one, after its leading assignments."""
    ifs = [s for s in ast.parse(donor_src).body[0].body if isinstance(s, ast.If)]
    if not ifs:
        return False
    body = tree.body[0].body
    body.insert(rule_position(body), copy.deepcopy(rng.choice(ifs)))
    return True


# =============================================================================
# Milestone 3: the mutation operator
# =============================================================================
def edit_constant(tree, rng):
    """Nudge one numeric constant by -2, -1, +1 or +2 (never below 0). Edit `tree` in place.
    Return True if there was a constant to edit, False if not. Choose the constant, then the nudge,
    with one rng call each, in that order."""
    raise NotImplementedError("TODO milestone 3: edit_constant")


def edit_operator(tree, rng):
    """Swap one operator for another of its family, in place: + - * among arithmetic operators,
    < <= > >= among comparisons (an == is left alone). Return False if there is no such operator."""
    raise NotImplementedError("TODO milestone 3: edit_operator")


EDITS = (edit_constant, edit_operator, edit_insert_rule, edit_shape, edit_replace_name, edit_delete)


def mutate(src, rng, attempts=10):
    """One syntactically valid edit of `src`, as canonical source text.

    Up to `attempts` times: parse src, pick one function of EDITS with rng.choice, apply it to the tree,
    unparse. Return the first result that differs from canonical(src) and passes is_valid.
    If every attempt fails, return canonical(src). Same src and same rng state: same answer."""
    raise NotImplementedError("TODO milestone 3: mutate")


def stand_in_llm(parents, rng):
    """The pluggable mutation operator: parents are sorted worst to best, like the numbered versions in a
    FunSearch prompt. Edit the best (last); one time in five, first borrow an `if` rule from an earlier one.
    A deterministic stand-in: a real model would write free-form code from the same prompt."""
    best = parents[-1]
    if len(parents) > 1 and rng.random() < 0.2:
        tree = ast.parse(canonical(best))
        if edit_borrow(tree, rng, rng.choice(parents[:-1])):
            ast.fix_missing_locations(tree)
            new = ast.unparse(tree)
            if new != canonical(best) and is_valid(new):
                return new
    return mutate(best, rng)


# =============================================================================
# Milestone 4: an island of clusters
# =============================================================================
def softmax_weights(values, temperature):
    """Probabilities proportional to exp(value / temperature), computed stably (subtract the maximum first).
    Higher values get more weight; a small temperature concentrates the weight on the maximum."""
    raise NotImplementedError("TODO milestone 4: softmax_weights")


MAX_PER_CLUSTER = 4


class Island:
    """Programs grouped into clusters by signature (the tuple of bins on the training instances).
    Programs in a cluster behave identically on those instances, so a cluster is one idea."""

    def __init__(self, max_clusters=24):
        self.max_clusters = max_clusters
        self.clusters = {}          # signature -> {"fitness": float, "programs": [source, ...]}

    def add(self, src, outcome):
        """Store an 'ok' outcome (ignore anything else). The cluster is outcome.bins. A cluster keeps at most
        MAX_PER_CLUSTER programs, the shortest (ties by text), without duplicates. If the island then has more
        than max_clusters clusters, drop the cluster with the lowest fitness (the earliest-created on a tie)."""
        raise NotImplementedError("TODO milestone 4: add")

    def __len__(self):
        return sum(len(c["programs"]) for c in self.clusters.values())

    def best(self):
        """(shortest program of the highest-fitness cluster, its fitness), or None if empty."""
        if not self.clusters:
            return None
        sig = max(self.clusters, key=lambda s: self.clusters[s]["fitness"])
        c = self.clusters[sig]
        return c["programs"][0], c["fitness"]

    def fresh_from_best(self):
        """A new, empty-but-for-one island that holds only this island's best program in its own cluster."""
        sig = max(self.clusters, key=lambda s: self.clusters[s]["fitness"])
        c = self.clusters[sig]
        fresh = Island(self.max_clusters)
        fresh.clusters[sig] = {"fitness": c["fitness"], "programs": [c["programs"][0]]}
        return fresh

    def sample(self, rng, k=2, cluster_temp=0.5, length_temp=50.0):
        """Best-shot prompt material: draw k programs, each by a two-stage draw, and return the DISTINCT ones
        sorted from worst to best cluster fitness (ties: longer first). Stage one picks a cluster with
        softmax_weights over cluster fitness at cluster_temp; stage two picks a program in it with softmax_weights
        over minus the length, at length_temp. Use rng.choices(range(n), weights)[0] for each stage."""
        raise NotImplementedError("TODO milestone 4: sample")


# =============================================================================
# Milestone 5: islands, and replacing the weakest
# =============================================================================
class Database:
    def __init__(self, n_islands, seed_src, seed_outcome, max_clusters=24):
        self.max_clusters = max_clusters
        self.islands = [Island(max_clusters) for _ in range(n_islands)]
        for isl in self.islands:
            isl.add(seed_src, seed_outcome)

    def add(self, i, src, outcome):
        self.islands[i].add(src, outcome)

    def best(self):
        """(program, fitness) of the best program on any island. Ties: the lowest island index."""
        raise NotImplementedError("TODO milestone 5: best")

    def reseed(self, rng):
        """Replace the weakest half of the islands (len // 2 of them).

        Rank islands by the fitness of their best program, best first, ties by lower index. Every one of the
        weakest len // 2 islands is replaced by a fresh Island that holds only the best program of a surviving
        island, chosen with rng.choice over the survivors in rank order. Returns the list of
        (replaced_index, source_index) pairs, in rank order of the replaced islands."""
        raise NotImplementedError("TODO milestone 5: reseed")


# =============================================================================
# Milestone 6: the whole loop, and an honest report
# =============================================================================
@dataclass
class RunResult:
    best_src: str
    best_outcome: Outcome
    calls: int                                   # mutation-operator calls made (the budget)
    evaluations: int                             # distinct programs actually evaluated
    statuses: dict = field(default_factory=dict) # status -> number of evaluated programs
    trace: list = field(default_factory=list)    # best fitness after each call


def funsearch(budget, seed, train_seeds=TRAIN_SEEDS, n_islands=4, k=2, mutator=stand_in_llm,
              reseed_every=150, cluster_temp=0.5, fuel_budget=FUEL):
    """Run the FunSearch loop for `budget` calls of the mutation operator and return a RunResult.

    Call i (0-based) works on island i % n_islands: draw k parents with Island.sample(rng, k, cluster_temp),
    ask mutator(parents, rng) for a child, skip it if that exact source was seen before (it still counts as a
    call), otherwise evaluate it on the training instances and add 'ok' outcomes to that island. Every
    `reseed_every` calls (after calls reseed_every, 2 * reseed_every, ...) call Database.reseed(rng).
    The seed program SEED_SRC (canonical form) is evaluated first and does not count as a call."""
    raise NotImplementedError("TODO milestone 6: funsearch")


def report(src, train_seeds=TRAIN_SEEDS, test_seeds=TEST_SEEDS):
    """Train and held-out scores (mean bins) of `src` and of best fit, and the saving in each.

    Returns a dict with keys: train, test, base_train, base_test (best fit = SEED_SRC),
    gain_train, gain_test (base minus program, in bins; positive means fewer bins) and lower_test
    (the mean lower bound on the held-out instances)."""
    raise NotImplementedError("TODO milestone 6: report")
