"""binpack.py: online bin packing, a safe evaluator and an island database.

This is Lab 3's solution (open-ended/labs/code/lab03/solution.py) with the
scripted mutation operator taken out and the lines reflowed to 80 columns,
so that this folder stands on its own. Standard library only.

The task is chapter 9's: bins of capacity 100, items of size 20 to 60 that
arrive one at a time, and one function to evolve,

    def priority(item, rem): ...   # rem = space left in a bin

The item goes to the feasible bin with the highest priority. A program is a
source string. Its score is the mean number of bins over some instances
(lower is better), its fitness is minus that, and its signature is the tuple
of bin counts it gets on each instance.

Three sets of instances, as in chapter 16:
    TRAIN_SEEDS   the search set: the loop sees these scores all the time
    SELECT_SEEDS  the selection set: picks among finalists at the end
    TEST_SEEDS    the test set: used once, to report
"""
import ast
import copy
import math
import random
from dataclasses import dataclass

CAP = 100
SEED_SRC = "def priority(item, rem):\n    gap = rem - item\n    return -gap\n"
FIRST_FIT_SRC = "def priority(item, rem):\n    return 0\n"

TRAIN_SEEDS = tuple(range(10))
SELECT_SEEDS = tuple(range(50, 60))
TEST_SEEDS = tuple(range(100, 130))


# ── 1. The problem ───────────────────────────────────────────────────────
def instance(seed, n=300):
    """n item sizes in 20..60; the same seed always gives the same items."""
    rng = random.Random(seed)
    return [rng.randint(20, 60) for _ in range(n)]


def make_instances(seeds, n=300):
    return [instance(s, n) for s in seeds]


def lower_bound(items):
    """No packing, online or not, can use fewer bins than total / capacity."""
    return sum(items) / CAP


def pack(items, priority):
    """Each item goes to the feasible bin (rem >= item) with the highest
    priority(item, rem); ties go to the earliest bin. If none fits, open a
    new bin. Returns the number of bins used."""
    bins = []
    for it in items:
        best, best_p = None, None
        for i, rem in enumerate(bins):
            if rem >= it:
                p = priority(it, rem)
                if best_p is None or p > best_p:
                    best, best_p = i, p
        if best is None:
            bins.append(CAP - it)
        else:
            bins[best] -= it
    return len(bins)


# ── 2. A whitelist and a fuel budget (chapter 21 and 22 of A0) ───────────
class Rejected(Exception):
    """The source may not run at all (decided before any execution)."""


class OutOfFuel(Exception):
    """The program used more steps than its budget."""


class Fuel:
    """A step counter. instrument() makes candidate code call tick() on
    entering the function and on every loop pass, so a loop that never ends
    runs the fuel out."""

    def __init__(self, budget):
        self.budget, self.used = budget, 0

    def tick(self):
        self.used += 1
        if self.used > self.budget:
            raise OutOfFuel(f"more than {self.budget} steps")


MAX_CHARS, MAX_NODES = 2000, 150
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


def validate(src):
    """Parse `src` and return its tree, or raise Rejected(reason). Exactly
    one `def priority(item, rem):` made only of whitelisted node types;
    calls only to abs, min, max; no name starting with an underscore; every
    name read is a parameter, an assigned name or a safe call."""
    if len(src) > MAX_CHARS:
        raise Rejected(f"source longer than {MAX_CHARS} characters")
    try:
        tree = ast.parse(src)
    except (SyntaxError, ValueError, RecursionError, MemoryError) as e:
        raise Rejected(f"syntax error: {type(e).__name__}")
    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.FunctionDef):
        raise Rejected("expected exactly one function definition")
    fn, a = tree.body[0], tree.body[0].args
    if (fn.name != "priority" or [x.arg for x in a.args] != ["item", "rem"]
            or a.vararg or a.kwarg or a.kwonlyargs or a.posonlyargs
            or a.defaults or fn.decorator_list or fn.returns):
        raise Rejected("the function must be `def priority(item, rem):`")
    nodes = list(ast.walk(tree))
    if sum(isinstance(n, ast.FunctionDef) for n in nodes) != 1:
        raise Rejected("nested function definitions are not allowed")
    if len(nodes) > MAX_NODES:
        raise Rejected(f"more than {MAX_NODES} syntax nodes")
    assigned = {n.id for n in nodes
                if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
    known = {"item", "rem"} | assigned | set(SAFE_CALLS)
    for n in nodes:
        if not isinstance(n, ALLOWED_NODES):
            raise Rejected(f"{type(n).__name__} is not allowed")
        if isinstance(n, ast.Constant):
            if type(n.value) not in (int, float, bool) or abs(n.value) > 1e9:
                raise Rejected(f"constant {n.value!r} is not allowed")
        if isinstance(n, ast.Name):
            if n.id.startswith("_"):
                raise Rejected(f"name {n.id!r} is not allowed")
            if isinstance(n.ctx, ast.Load) and n.id not in known:
                raise Rejected(f"unknown name {n.id!r}")
        if isinstance(n, ast.Call):
            if (not (isinstance(n.func, ast.Name) and n.func.id in SAFE_CALLS)
                    or n.keywords):
                raise Rejected("only abs, min and max may be called")
    return tree


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

    def visit_Constant(self, node):
        if type(node.value) is int:      # all arithmetic becomes float:
            return ast.copy_location(ast.Constant(float(node.value)), node)
        return node                      # no huge integers


def instrument(tree):
    """A NEW tree with a _tick() call at the top of the function and of
    every loop body, and every int constant turned into a float."""
    return ast.fix_missing_locations(_Instrument().visit(copy.deepcopy(tree)))


def compile_restricted(src, fuel):
    """validate, instrument, compile and exec `src`; return `priority`. The
    namespace holds only abs, min, max and the fuel's tick: no __import__,
    no open, no getattr."""
    code = compile(instrument(validate(src)), "<candidate>", "exec")
    ns = {"__builtins__": {"abs": abs, "min": min, "max": max},
          "_tick": fuel.tick}
    exec(code, ns)
    return ns["priority"]


# ── 3. A total evaluator: every outcome becomes a result ─────────────────
@dataclass
class Outcome:
    """status is 'ok', 'rejected', 'error', 'timeout' or 'bad_value'. Only
    'ok' has a score."""
    status: str
    score: float = math.inf          # mean bins over the instances
    bins: tuple = ()                 # bins on each instance: the signature
    detail: str = ""
    steps: int = 0

    @property
    def ok(self):
        return self.status == "ok"

    @property
    def fitness(self):
        return -self.score           # higher is better; -inf if not ok


FUEL_PER_INSTANCE = 40_000


def evaluate(src, instances, fuel_budget=None):
    """Score `src` on a list of instances. NEVER raises."""
    fuel = Fuel(fuel_budget or FUEL_PER_INSTANCE * len(instances))
    try:
        fn = compile_restricted(src, fuel)
    except Rejected as e:
        return Outcome("rejected", detail=str(e))
    except Exception as e:           # an accepted tree that will not compile
        return Outcome("rejected", detail=f"{type(e).__name__}: {e}")

    def checked(item, rem):
        v = fn(float(item), float(rem))
        if type(v) not in (int, float) or not math.isfinite(v):
            raise ValueError(f"priority returned {v!r}")
        return v

    try:
        counts = tuple(pack(items, checked) for items in instances)
    except OutOfFuel as e:
        return Outcome("timeout", detail=str(e), steps=fuel.used)
    except ValueError as e:
        return Outcome("bad_value", detail=str(e), steps=fuel.used)
    except Exception as e:
        return Outcome("error", detail=f"{type(e).__name__}: {e}",
                       steps=fuel.used)
    return Outcome("ok", sum(counts) / len(counts), counts, steps=fuel.used)


def evaluate_seeds(src, seeds):
    """evaluate() on the instances of some seeds. A plain function of two
    plain arguments, so a process pool can run it."""
    return evaluate(src, make_instances(seeds))


def canonical(src):
    """The one text for a syntax tree, so equal programs are equal strings."""
    return ast.unparse(ast.parse(src))


# ── 4. Islands of clusters (chapter 9) ───────────────────────────────────
def softmax_weights(values, temperature):
    m = max(values)
    w = [math.exp((v - m) / temperature) for v in values]
    return [x / sum(w) for x in w]


MAX_PER_CLUSTER = 4


class Island:
    """Programs grouped into clusters by signature. Programs in a cluster
    behave identically on the search set, so a cluster is one idea."""

    def __init__(self, max_clusters=24):
        self.max_clusters = max_clusters
        self.clusters = {}      # signature -> {"fitness", "programs"}

    def add(self, src, outcome):
        if not outcome.ok:
            return
        c = self.clusters.setdefault(
            outcome.bins, {"fitness": outcome.fitness, "programs": []})
        if src not in c["programs"]:
            c["programs"].append(src)
            c["programs"].sort(key=lambda p: (len(p), p))   # short first
            del c["programs"][MAX_PER_CLUSTER:]
        if len(self.clusters) > self.max_clusters:
            worst = min(self.clusters,
                        key=lambda s: self.clusters[s]["fitness"])
            del self.clusters[worst]

    def best(self):
        """(shortest program of the best cluster, its fitness) or None."""
        if not self.clusters:
            return None
        sig = max(self.clusters, key=lambda s: self.clusters[s]["fitness"])
        c = self.clusters[sig]
        return c["programs"][0], c["fitness"]

    def fresh_from_best(self):
        sig = max(self.clusters, key=lambda s: self.clusters[s]["fitness"])
        c = self.clusters[sig]
        fresh = Island(self.max_clusters)
        fresh.clusters[sig] = {"fitness": c["fitness"],
                               "programs": [c["programs"][0]]}
        return fresh

    def sample(self, rng, k=2, cluster_temp=0.5, length_temp=50.0):
        """Best-shot prompt material: k distinct programs, worst to best.
        Pick a cluster by softmax over fitness, then a short program."""
        sigs = list(self.clusters)
        fits = [self.clusters[s]["fitness"] for s in sigs]
        chosen = {}
        for _ in range(k):
            w = softmax_weights(fits, cluster_temp)
            sig = sigs[rng.choices(range(len(sigs)), w)[0]]
            progs = self.clusters[sig]["programs"]
            w = softmax_weights([-len(x) for x in progs], length_temp)
            chosen[progs[rng.choices(range(len(progs)), w)[0]]] = \
                self.clusters[sig]["fitness"]
        return sorted(chosen, key=lambda p: (chosen[p], len(p)))


class Database:
    def __init__(self, n_islands, seed_src, seed_outcome):
        self.islands = [Island() for _ in range(n_islands)]
        for isl in self.islands:
            isl.add(seed_src, seed_outcome)

    def best(self):
        """(program, fitness) of the best program on any island."""
        tops = [b for b in (i.best() for i in self.islands) if b]
        return max(tops, key=lambda b: b[1]) if tops else None

    def reseed(self, rng):
        """Replace the weakest half of the islands by fresh ones that hold
        only the best program of a surviving island."""
        order = sorted(range(len(self.islands)),
                       key=lambda i: (-(self.islands[i].best()[1]), i))
        n = len(order) // 2
        survivors, weakest = order[:len(order) - n], order[len(order) - n:]
        for i in weakest:
            j = rng.choice(survivors)
            self.islands[i] = self.islands[j].fresh_from_best()
        return [(i, j) for i in weakest]
