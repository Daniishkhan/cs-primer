# Drill: A0 Lab 6, milestone 4 of 5: remember everything once (step 3 of 3)
# Everything else in this file is already written. Fill in:
#     Archive.best
# Check it with: python3 check.py 4

"""Lab 6: A Tiny Evolution Engine (reference solution).

Standard library only, no clock, no network, no language model.
The task is online bin packing: bins of capacity 100, items of size 20 to 60
arriving one at a time. One function is evolved:

    def priority(item, rem):    # rem = space left in a bin that can hold item
        ...                     # the item goes to the feasible bin that
                                # scores highest, or to a new bin

Candidates are source strings. The loop mutates their syntax trees, scores
them safely and keeps an archive. Milestones:

    1  validate, make_heuristic      only run code you have checked
    2  pack, score                   every outcome becomes a number
    3  mutate                        edit the syntax tree, seeded
    4  canonical_hash, Archive       never score the same program twice
    5  evolve                        the whole loop, reported on held-out data
"""
import ast
import copy
import hashlib
import json
import math
import random
from dataclasses import dataclass, field

CAP = 100
FIRST_FIT = "def priority(item, rem):\n    return 0\n"
BEST_FIT = "def priority(item, rem):\n    return -(rem - item)\n"
SEED_SRC = (
    "def priority(item, rem):\n"
    "    gap = rem - item\n"
    "    return gap * 1\n"
)

TRAIN_SEEDS = tuple(range(8))            # instances the search may look at
TEST_SEEDS = tuple(range(100, 120))      # held-out: only for the final report

PENALTY = 10_000.0     # bins charged to a program that crashes or cheats
FUEL = 200_000         # steps one score() call may spend, over all instances
MAX_CHARS = 1000
MAX_NODES = 80
SAFE_CALLS = ("abs", "min", "max")
ALLOWED_NODES = (
    ast.Module, ast.FunctionDef, ast.arguments, ast.arg,
    ast.Return, ast.Assign, ast.If, ast.While, ast.Pass,
    ast.Name, ast.Load, ast.Store, ast.Constant,
    ast.BinOp, ast.UnaryOp, ast.Compare, ast.IfExp, ast.Call,
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod,
    ast.UAdd, ast.USub,
    ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
)


# ── GIVEN: instances, exceptions and the fuel counter ───────────────────
def instance(seed, n=200):
    """n item sizes in 20..60. The same seed always gives the same items."""
    rng = random.Random(seed)
    return [rng.randint(20, 60) for _ in range(n)]


def make_instances(seeds, n=200):
    return [instance(s, n) for s in seeds]


def lower_bound(items):
    """No packing can use fewer bins than ceil(total size / capacity)."""
    return math.ceil(sum(items) / CAP)


class Rejected(Exception):
    """The source may not run at all (found before anything executes)."""


class OutOfFuel(Exception):
    """The program spent more steps than its budget."""


class Fuel:
    """A step counter. Instrumented code calls tick() on every function
    entry and every loop pass, so a loop that never ends runs out of fuel."""

    def __init__(self, budget):
        self.budget = budget
        self.used = 0

    def tick(self):
        self.used += 1
        if self.used > self.budget:
            raise OutOfFuel(f"more than {self.budget} steps")


class _Instrument(ast.NodeTransformer):
    @staticmethod
    def _tick():
        return ast.Expr(ast.Call(ast.Name("_tick", ast.Load()), [], []))

    def visit_FunctionDef(self, node):
        self.generic_visit(node)
        node.body.insert(0, self._tick())
        return node

    def visit_While(self, node):
        self.generic_visit(node)
        node.body.insert(0, self._tick())
        return node


def instrument(tree):
    """A NEW tree with a _tick() call at the top of the function and of
    every while body. The tree you pass in is left alone."""
    new = _Instrument().visit(copy.deepcopy(tree))
    return ast.fix_missing_locations(new)


# ── Milestone 1: only run code you have checked ─────────────────────────
def validate(src):
    """Return the parsed ast.Module, or raise Rejected(reason).

    Accept exactly one top-level `def priority(item, rem):` (plain
    arguments, no defaults) and nothing else. Every node must be in
    ALLOWED_NODES. Calls must be abs, min or max by bare name. No name
    may start with an underscore.
    """
    if len(src) > MAX_CHARS:
        raise Rejected("source too long")
    try:
        tree = ast.parse(src)
    except (SyntaxError, ValueError, RecursionError):
        raise Rejected("syntax error")
    body = tree.body
    if len(body) != 1 or not isinstance(body[0], ast.FunctionDef):
        raise Rejected("expected exactly one function")
    fn = body[0]
    params = [a.arg for a in fn.args.args]
    a = fn.args
    plain = not (a.defaults or a.vararg or a.kwarg or a.kwonlyargs)
    if fn.name != "priority" or params != ["item", "rem"] or not plain:
        raise Rejected("must be exactly def priority(item, rem)")
    nodes = list(ast.walk(tree))
    if len(nodes) > MAX_NODES:
        raise Rejected("too many nodes")
    for node in nodes:
        if not isinstance(node, ALLOWED_NODES):
            raise Rejected(f"{type(node).__name__} is not allowed")
        if isinstance(node, ast.Name) and node.id.startswith("_"):
            raise Rejected(f"name {node.id!r} is not allowed")
        if isinstance(node, ast.Call):
            ok = isinstance(node.func, ast.Name)
            if not ok or node.func.id not in SAFE_CALLS:
                raise Rejected("only abs, min and max may be called")
    return tree


def make_heuristic(src, fuel):
    """validate, instrument, compile and exec `src`; return `priority`.

    The namespace holds only abs, min, max (as builtins) and the fuel's
    tick under the name _tick. Raises Rejected for a bad source.
    """
    tree = instrument(validate(src))
    code = compile(tree, "<candidate>", "exec")
    builtins = {"abs": abs, "min": min, "max": max}
    namespace = {"__builtins__": builtins, "_tick": fuel.tick}
    exec(code, namespace)
    return namespace["priority"]


# ── Milestone 2: every outcome becomes a number ─────────────────────────
def pack(priority, items):
    """Online bin packing; return the number of bins used.

    Each item goes to the feasible bin (rem >= item) with the highest
    priority(item, rem). Ties go to the earliest bin. If no bin fits,
    open a new one. A priority that returns anything but a finite
    int or float raises ValueError.
    """
    bins = []
    for item in items:
        best = None
        best_p = None
        for i, rem in enumerate(bins):
            if rem < item:
                continue
            p = priority(item, rem)
            if type(p) not in (int, float) or not math.isfinite(p):
                raise ValueError(f"priority returned {p!r}")
            if best_p is None or p > best_p:
                best = i
                best_p = p
        if best is None:
            bins.append(CAP - item)
        else:
            bins[best] -= item
    return len(bins)


def score(src, instances, fuel_budget=FUEL):
    """Mean bins over the instances (lower is better). Never raises.

    A source that is rejected, crashes, runs out of fuel or returns a bad
    value scores PENALTY instead.
    """
    fuel = Fuel(fuel_budget)
    try:
        fn = make_heuristic(src, fuel)
        counts = [pack(fn, items) for items in instances]
    except Exception:
        return PENALTY
    return sum(counts) / len(counts)


# ── Milestone 3: edit the syntax tree ───────────────────────────────────
ARITH = (ast.Add, ast.Sub, ast.Mult)
NUDGES = (-4, -2, -1, 1, 2, 4)
SQUARE_LIMIT = 8     # squaring copies the expression: keep that cheap


def perturb_constant(tree, rng):
    """Add a nudge to one numeric constant. True if one was changed."""
    consts = [n for n in ast.walk(tree)
              if isinstance(n, ast.Constant) and type(n.value) in (int, float)]
    if not consts:
        return False
    node = rng.choice(consts)
    node.value = node.value + rng.choice(NUDGES)
    return True


def swap_operator(tree, rng):
    """Replace one + - * by a different one of the three."""
    sites = [n for n in ast.walk(tree)
             if isinstance(n, ast.BinOp) and isinstance(n.op, ARITH)]
    if not sites:
        return False
    node = rng.choice(sites)
    others = [op for op in ARITH if not isinstance(node.op, op)]
    node.op = rng.choice(others)()
    return True


def wrap_expression(tree, rng):
    """Wrap the value of one return or assignment: abs(e) or e * e.

    Squaring copies the expression, and repeated squaring would double
    the tree each time. Square only when the value has at most
    SQUARE_LIMIT nodes (count them with ast.walk); otherwise use abs.
    """
    sites = [n for n in ast.walk(tree)
             if isinstance(n, (ast.Return, ast.Assign))]
    if not sites:
        return False
    node = rng.choice(sites)
    small = len(list(ast.walk(node.value))) <= SQUARE_LIMIT
    if rng.random() < 0.5 or not small:
        node.value = ast.Call(ast.Name("abs", ast.Load()), [node.value], [])
    else:
        twin = copy.deepcopy(node.value)
        node.value = ast.BinOp(node.value, ast.Mult(), twin)
    return True


OPERATORS = (perturb_constant, swap_operator, wrap_expression)


def mutate(src, rng, attempts=10):
    """One valid edit of `src`, as source text. Same src and rng state
    give the same answer.

    Up to `attempts` times: parse the canonical text, pick an operator
    with rng.choice, apply it, unparse. Return the first result that
    differs from the canonical text and passes validate. If every attempt
    fails, return the canonical text.
    """
    base = ast.unparse(ast.parse(src))
    for _ in range(attempts):
        tree = ast.parse(base)
        operator = rng.choice(OPERATORS)
        if not operator(tree, rng):
            continue
        ast.fix_missing_locations(tree)
        new = ast.unparse(tree)
        if new == base:
            continue
        try:
            validate(new)
        except Rejected:
            continue
        return new
    return base


# ── Milestone 4: never score the same program twice ─────────────────────
def canonical_hash(src):
    """A 12-hex-digit name for the program's syntax tree, so spacing,
    comments and quote style do not matter."""
    text = ast.unparse(ast.parse(src))
    return hashlib.sha256(text.encode()).hexdigest()[:12]


@dataclass
class Entry:
    hash: str
    parent: str        # hash of the parent, or "" for a seed
    score: float
    src: str


@dataclass
class Archive:
    """Every program tried, keyed by hash, plus a JSON-lines log."""
    path: str = ""                       # "" keeps the log in memory only
    entries: dict = field(default_factory=dict)
    lines: list = field(default_factory=list)

    def __contains__(self, src):
        return canonical_hash(src) in self.entries

    def add(self, src, parent, score):
        """Store the program. Return False (storing nothing) if its hash
        is already there; otherwise True.

        The entry keeps the canonical source (ast.unparse of the parse).
        Also append one JSON line {"hash", "parent", "score", "src"} to
        self.lines, and to the file at self.path when it is not "".
        """
        h = canonical_hash(src)
        if h in self.entries:
            return False
        canon = ast.unparse(ast.parse(src))
        entry = Entry(h, parent, score, canon)
        self.entries[h] = entry
        line = json.dumps({"hash": h, "parent": parent,
                           "score": score, "src": canon})
        self.lines.append(line)
        if self.path:
            with open(self.path, "a") as f:
                f.write(line + "\n")
        return True

    def best(self):
        """The entry with the lowest score. Ties: shorter source, then
        smaller hash. None if empty."""
        raise NotImplementedError("TODO milestone 4: best")


# ── Milestone 5: the whole loop ─────────────────────────────────────────
ELITES = 2
TOURNAMENT = 3


def tournament(population, rng, size=TOURNAMENT):
    """Pick up to `size` entries with rng.sample and return the best one
    (lowest score; ties: shorter source, then hash)."""
    contenders = rng.sample(population, min(size, len(population)))
    return min(contenders, key=lambda e: (e.score, len(e.src), e.hash))


def evolve(seed, generations, pop_size, train_seeds=TRAIN_SEEDS,
           path=""):
    """Run the loop and return the Archive.

    Start from SEED_SRC (scored, added with parent ""). The population
    is the list of the best `pop_size` entries so far. Each generation:
    keep the ELITES best unchanged; fill the rest with children. A child
    is mutate(parent.src, rng) for a parent chosen by tournament. If the
    child is already in the archive it is skipped (no score, no add).
    The new population is the elites plus the new children, best first,
    then cut to pop_size. All randomness comes from random.Random(seed).
    """
    rng = random.Random(seed)
    train = make_instances(train_seeds)
    archive = Archive(path)
    first = ast.unparse(ast.parse(SEED_SRC))
    archive.add(first, "", score(first, train))
    population = [archive.best()]
    for _ in range(generations):
        children = []
        for _ in range(pop_size - ELITES):
            parent = tournament(population, rng)
            child = mutate(parent.src, rng)
            if child in archive:
                continue
            archive.add(child, parent.hash, score(child, train))
            children.append(archive.entries[canonical_hash(child)])
        pool = population[:ELITES] + children
        pool.sort(key=lambda e: (e.score, len(e.src), e.hash))
        population = pool[:pop_size]
    return archive


def report(src, test_seeds=TEST_SEEDS):
    """Mean bins of `src`, of first fit and of best fit on the
    held-out instances, plus the mean lower bound."""
    test = make_instances(test_seeds)
    return {
        "program": score(src, test),
        "first_fit": score(FIRST_FIT, test),
        "best_fit": score(BEST_FIT, test),
        "lower": sum(lower_bound(i) for i in test) / len(test),
    }
