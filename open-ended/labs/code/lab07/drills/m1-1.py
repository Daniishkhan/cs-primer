# Drill: A7 Lab 7, milestone 1 of 6: utility (step 1 of 1)
# Everything else in this file is already written. Fill in:
#     utility
# Check it with: python3 check.py 1

"""Lab 7: Improve the Improver (a miniature of STOP).

Pure Python, no clock, no network. Every random number comes from a seeded random.Random.

The object level is the bin packing of the last labs: bins of capacity 100, items arrive one at a
time, and an evolver searches for a priority function

    def priority(item, rem):     # rem = space left in a bin; the item goes to the feasible bin
        ...                      # with the highest priority

The evolver has settings (a Config): how often it uses each kind of edit, how many islands it has,
how big its tournaments are, how often islands swap. The evolver gets a FIXED number of heuristic
evaluations. The meta level searches for good settings. The meta-meta level searches for a good
way of searching for settings: the improver is improved by itself.

    1  utility                 score one heuristic; every failure is a penalty
    2  meta_utility            run the evolver with a Config on several tasks, within a budget
    3  improve                 the seed improver: perturb the config, keep it if it is better
    4  improver_utility,       self-application: the improver's own settings, improved by the same idea
       self_improve
    5  generalisation          train, held-out and shifted scores, and the gap between them
    6  audit                   catch an improver that cheats at the meta level

What YOU write is marked TODO (the solution file is the finished version).
"""
import ast
import copy
import math
import random
from dataclasses import dataclass, fields, replace

# =============================================================================
# GIVEN: the problem, the tasks and the budget
# =============================================================================
CAP = 100
SEED_SRC = "def priority(item, rem):\n    return rem - item\n"   # worst fit: a poor start with room to improve
BEST_FIT_SRC = "def priority(item, rem):\n    return item - rem\n"
PENALTY = -1000.0            # utility of a program that is rejected, crashes, loops or lies
FUEL = 50_000                # steps one utility() call may spend, over all its instances
ITEMS = 80                   # items per instance (short, so the check is fast)
N_SEARCH, N_EVAL = 3, 6      # per task: instances the evolver sees, instances it is scored on
BUDGET = 20                  # heuristic evaluations the evolver gets, per task
POP = 6                      # programs kept per island

TRAIN_TASKS = (1, 2, 3)                # the improver may look at these
HELD_TASKS = (11, 12, 13, 14, 15, 16)  # it must never look at these
IMPROVE_SEEDS = (0, 1, 2)              # random streams used to compare improvers on the training tasks
FRESH_SEEDS = tuple(range(50, 62))     # twelve new streams, used only for the final comparison
CALLS = 4                              # about this many rounds*proposals an improver may use per run


def instance(seed, n=ITEMS, lo=20, hi=60):
    """n item sizes in lo..hi (capacity is 100); the same seed always gives the same items."""
    rng = random.Random(seed)
    return [rng.randint(lo, hi) for _ in range(n)]


def make_instances(seeds, n=ITEMS, lo=20, hi=60):
    return [instance(s, n, lo, hi) for s in seeds]


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
    if len(src) > MAX_CHARS:
        raise Rejected(f"source longer than {MAX_CHARS} characters")
    try:
        tree = ast.parse(src)
    except (SyntaxError, ValueError, RecursionError, MemoryError) as e:
        raise Rejected(f"syntax error: {type(e).__name__}")
    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.FunctionDef):
        raise Rejected("expected exactly one function definition")
    fn = tree.body[0]
    a = fn.args
    if (fn.name != "priority" or [x.arg for x in a.args] != ["item", "rem"] or a.vararg or a.kwarg
            or a.kwonlyargs or a.posonlyargs or a.defaults or fn.decorator_list or fn.returns):
        raise Rejected("the function must be exactly `def priority(item, rem):`")
    nodes = list(ast.walk(tree))
    if sum(isinstance(n, ast.FunctionDef) for n in nodes) != 1:
        raise Rejected("nested function definitions are not allowed")
    if len(nodes) > MAX_NODES:
        raise Rejected(f"more than {MAX_NODES} syntax nodes")
    assigned = {n.id for n in nodes if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
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
            if not (isinstance(n.func, ast.Name) and n.func.id in SAFE_CALLS) or n.keywords:
                raise Rejected("only abs, min and max may be called, with positional arguments")
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
        if type(node.value) is int:                 # all arithmetic becomes float arithmetic: no huge integers
            return ast.copy_location(ast.Constant(float(node.value)), node)
        return node


def instrument(tree):
    """Return a NEW tree (leave `tree` untouched) in which the function body and every while-loop body begin
    with a call `_tick()`, and every int constant has become a float, so nothing can grow without bound.
    Call ast.fix_missing_locations on the result before it is compiled."""
    new = _Instrument().visit(copy.deepcopy(tree))
    return ast.fix_missing_locations(new)


def compile_restricted(src, fuel):
    """validate, instrument, compile and exec `src`; return the `priority` function.

    The namespace holds only abs, min, max and the fuel's tick, which is registered under the name _tick
    (the name instrument() calls): no __import__, no open, no getattr."""
    tree = instrument(validate(src))
    code = compile(tree, "<candidate>", "exec")
    ns = {"__builtins__": {"abs": abs, "min": min, "max": max}, "_tick": fuel.tick}
    exec(code, ns)
    return ns["priority"]

def pack(items, priority):
    """Online bin packing. Each item goes to the feasible bin (rem >= item) with the highest
    priority(item, rem); ties go to the earliest bin. If none fits, open a new bin.
    Return the number of bins used."""
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


def edit_constant(tree, rng):
    """Nudge one numeric constant by -2, -1, +1 or +2 (never below 0). Edit `tree` in place.
    Return True if there was a constant to edit, False if not. Choose the constant, then the nudge,
    with one rng call each, in that order."""
    consts = [n for n in ast.walk(tree) if isinstance(n, ast.Constant) and type(n.value) in (int, float)]
    if not consts:
        return False
    node = rng.choice(consts)
    node.value = max(0, node.value + rng.choice([-2, -1, 1, 2]))
    return True


def edit_operator(tree, rng):
    """Swap one operator for another of its family, in place: + - * among arithmetic operators,
    < <= > >= among comparisons (an == is left alone). Return False if there is no such operator."""
    sites = [n for n in ast.walk(tree)
             if (isinstance(n, ast.BinOp) and isinstance(n.op, ARITH))
             or (isinstance(n, ast.Compare) and len(n.ops) == 1 and isinstance(n.ops[0], CMP))]
    if not sites:
        return False
    node = rng.choice(sites)
    if isinstance(node, ast.BinOp):
        node.op = rng.choice([o for o in ARITH if not isinstance(node.op, o)])()
    else:
        node.ops = [rng.choice([o for o in CMP if not isinstance(node.ops[0], o)])()]
    return True




def canonical_ok(src):
    try:
        validate(src)
        return True
    except Rejected:
        return False


# =============================================================================
# Milestone 1: utility
# =============================================================================
def utility(src, instances, fuel_budget=FUEL):
    """Score the program `src` on a list of instances. NEVER raises. Higher is better.

    A working program's utility is minus the mean number of bins it uses (so best fit
    on a typical instance scores about -17). Every failure gets PENALTY instead:
      * validate() refuses it (Rejected), or it fails to compile;
      * it runs out of fuel (OutOfFuel), which catches endless loops;
      * it raises any other exception while packing;
      * priority returns something that is not a finite int or float (a bool, nan, inf).
    Use compile_restricted(src, Fuel(fuel_budget)) and pack(items, priority).
    """
    raise NotImplementedError("TODO milestone 1: utility")


# =============================================================================
# GIVEN: the object-level evolver, its settings and its budget
# =============================================================================
class BudgetExceeded(Exception):
    """The evolver asked for more heuristic evaluations than it was given."""


class Budget:
    """A counter that lives inside meta_utility. The evolver calls spend() once per
    evaluation and cannot raise the limit: the improver never even sees this object."""

    def __init__(self, limit):
        self._limit = limit
        self.used = 0

    def spend(self):
        self.used += 1
        if self.used > self._limit:
            raise BudgetExceeded(f"more than {self._limit} evaluations")


@dataclass(frozen=True)
class Config:
    """The evolver's settings. These are what the improver searches over."""
    w_constant: int = 3      # relative weight of "nudge a constant" edits
    w_operator: int = 2      # ... "swap an operator"
    w_rule: int = 2          # ... "insert an if-rule"
    w_shape: int = 2         # ... "wrap an expression"
    n_islands: int = 2       # separate sub-populations
    tournament: int = 2      # parents compared when choosing one to mutate
    migrate_every: int = 8   # steps between island swaps (0 = never)


CHOICES = {
    "w_constant": tuple(range(0, 9)),
    "w_operator": tuple(range(0, 9)),
    "w_rule": tuple(range(0, 9)),
    "w_shape": tuple(range(0, 9)),
    "n_islands": (1, 2, 3, 4),
    "tournament": (1, 2, 3, 4),
    "migrate_every": (0, 4, 8, 16),
}
# A naive evolver: it can only nudge constants, with one island and no tournament.
DEFAULT = Config(w_constant=8, w_operator=0, w_rule=0, w_shape=0,
                 n_islands=1, tournament=1, migrate_every=0)
# A config someone already tuned by hand: improving it is much harder.
TUNED = Config(w_constant=3, w_operator=2, w_rule=2, w_shape=4,
               n_islands=4, tournament=3, migrate_every=8)


def fix_config(cfg):
    """A config the evolver can run: at least one edit weight must be positive."""
    if cfg.w_constant + cfg.w_operator + cfg.w_rule + cfg.w_shape == 0:
        return replace(cfg, w_constant=1)
    return cfg


EDITS = (edit_constant, edit_operator, edit_insert_rule, edit_shape)


def mutate(src, rng, weights):
    """One valid edit of `src`; the kind of edit is drawn with the given weights."""
    base = ast.unparse(ast.parse(src))
    for _ in range(8):
        tree = ast.parse(base)
        edit = rng.choices(EDITS, weights)[0]
        if not edit(tree, rng):
            continue
        ast.fix_missing_locations(tree)
        new = ast.unparse(tree)
        if new != base and canonical_ok(new):
            return new
    return base


def evolve(config, instances, budget, rng):
    """Search for a good priority function with `config`; stop when `budget` runs out.

    Each island holds up to POP (program, utility) pairs, all starting from SEED_SRC.
    Step s works on island s % n_islands: pick the best of `tournament` random members,
    mutate it, evaluate the child (one unit of budget), keep the POP best.
    Every migrate_every steps the best of each island replaces the worst of the next.
    Returns the best program found, judged on `instances` only.
    """
    cfg = fix_config(config)
    weights = [cfg.w_constant, cfg.w_operator, cfg.w_rule, cfg.w_shape]
    seen = {SEED_SRC}
    try:
        budget.spend()
        u0 = utility(SEED_SRC, instances)
        islands = [[(u0, SEED_SRC)] for _ in range(cfg.n_islands)]
        step = 0
        while True:
            budget.spend()
            pop = islands[step % cfg.n_islands]
            picks = [rng.choice(pop) for _ in range(cfg.tournament)]
            parent = max(picks, key=lambda p: p[0])[1]
            child = mutate(parent, rng, weights)
            if child not in seen:
                seen.add(child)
                pop.append((utility(child, instances), child))
                pop.sort(key=lambda p: (-p[0], len(p[1]), p[1]))
                del pop[POP:]
            step += 1
            if cfg.migrate_every and step % cfg.migrate_every == 0:
                tops = [isl[0] for isl in islands]
                for i, top in enumerate(tops):
                    nxt = islands[(i + 1) % len(islands)]
                    if top not in nxt:
                        nxt[-1:] = [top] if len(nxt) >= POP else [nxt[-1], top]
                        nxt.sort(key=lambda p: (-p[0], len(p[1]), p[1]))
    except BudgetExceeded:
        pass
    return max((isl[0] for isl in islands), key=lambda p: p[0])[1]


# =============================================================================
# Milestone 2: meta_utility
# =============================================================================
def meta_utility(config, task_seeds, budget, lo=20, hi=60):
    """The mean utility of what the evolver finds, over several tasks.

    For each task seed t (in the order given):
      * the search instances are make_instances([1000*t + j for j in range(N_SEARCH)], ITEMS, lo, hi)
      * the scoring instances are  make_instances([1000*t + 500 + j for j in range(N_EVAL)], ITEMS, lo, hi)
        (the evolver never sees these)
      * make a fresh Budget(budget), run evolve(config, search, counter, random.Random(t)),
        and take utility(found, scoring instances).
    Return the mean over tasks. The same arguments must always give the same number.
    """
    total = 0.0
    for t in task_seeds:
        search = make_instances([1000 * t + j for j in range(N_SEARCH)], ITEMS, lo, hi)
        scoring = make_instances([1000 * t + 500 + j for j in range(N_EVAL)], ITEMS, lo, hi)
        counter = Budget(budget)
        found = evolve(config, search, counter, random.Random(t))
        total += utility(found, scoring)
    return total / len(task_seeds)


def make_scorer(task_seeds=None, lo=20, hi=60):
    """GIVEN. The only handle an improver gets on the meta level: score(config) -> number.

    The tasks, the budget and the distribution are fixed here, so an honest improver
    cannot change them. Results are cached, because the same config always scores the same.
    """
    cache = {}

    def score(config):
        tasks = TRAIN_TASKS if task_seeds is None else task_seeds
        key = (fix_config(config), tuple(tasks), BUDGET, lo, hi)
        if key not in cache:
            cache[key] = meta_utility(key[0], tasks, BUDGET, lo, hi)
        return cache[key]

    return score


# =============================================================================
# Milestone 3: the seed improver
# =============================================================================
@dataclass(frozen=True)
class Settings:
    """How an improver improves. The improver's own settings (milestone 4 searches these)."""
    proposals: int = 2       # candidate configs tried per round
    n_change: int = 1        # how many config fields each candidate changes
    step: int = 1            # how far along a field's list of choices a change moves


SETTING_CHOICES = {
    "proposals": (1, 2, 3, 4, 6),
    "n_change": (1, 2, 3),
    "step": (1, 2, 3),
}
SEED_SETTINGS = Settings()


def perturb(obj, choices, rng, n_change, step):
    """GIVEN. A copy of the dataclass `obj` with `n_change` distinct fields moved by +-step
    positions along their list of choices (clamped to the ends)."""
    names = rng.sample(sorted(choices), n_change)
    changes = {}
    for name in names:
        options = choices[name]
        i = options.index(getattr(obj, name))
        i = min(len(options) - 1, max(0, i + rng.choice([-step, step])))
        changes[name] = options[i]
    return replace(obj, **changes)


def improve(config, score, rng, rounds, settings=SEED_SETTINGS):
    """Hill-climb over configs. Return (best_config, best_score).

    Start with best = config and best_score = score(config). Then, for each of `rounds`
    rounds, make settings.proposals candidates with
    perturb(best, CHOICES, rng, settings.n_change, settings.step) (draw them all before scoring
    any), and score them in order. Whenever a candidate scores STRICTLY higher than the best so
    far, it becomes the best. Return the best. The number of score calls is
    1 + rounds * proposals.
    """
    best = config
    best_score = score(config)
    for _ in range(rounds):
        candidates = [perturb(best, CHOICES, rng, settings.n_change, settings.step)
                      for _ in range(settings.proposals)]
        for cand in candidates:
            s = score(cand)
            if s > best_score:
                best, best_score = cand, s
    return best, best_score


# =============================================================================
# Milestone 4: self-application
# =============================================================================
def improver_utility(settings, score, start=DEFAULT, seeds=IMPROVE_SEEDS, calls=CALLS):
    """How good an improver is: the mean gain in `score` it makes from `start`.

    For each seed s run improve(start, score, random.Random(s), rounds, settings) where
    rounds = calls // settings.proposals (so every improver makes about the same number of
    score calls: a fair fight). The gain of a run is best_score - score(start).
    Return the mean gain over the seeds.
    """
    rounds = calls // settings.proposals
    base = score(start)
    gains = []
    for s in seeds:
        _, best_score = improve(start, score, random.Random(s), rounds, settings)
        gains.append(best_score - base)
    return sum(gains) / len(gains)


def self_improve(score, rng, rounds, settings=SEED_SETTINGS, start=DEFAULT):
    """Improve the improver: hill-climb over Settings with improver_utility as the score.

    Same shape as improve(): best = settings, best_u = improver_utility(settings, score, start);
    for each of `rounds` rounds make ONE candidate with
    perturb(best, SETTING_CHOICES, rng, 1, 1), compute its improver_utility, and keep it if STRICTLY
    higher. Return (best_settings, best_u).
    """
    best = settings
    best_u = improver_utility(settings, score, start)
    for _ in range(rounds):
        cand = perturb(best, SETTING_CHOICES, rng, 1, 1)
        u = improver_utility(cand, score, start)
        if u > best_u:
            best, best_u = cand, u
    return best, best_u


# =============================================================================
# Milestone 5: held-out meta-evaluation
# =============================================================================
def generalisation(settings, train_score, held_score, shifted_score, start=DEFAULT,
                   seeds=FRESH_SEEDS, calls=CALLS):
    """Run the improver `settings` once per seed using ONLY train_score, then re-score the
    config it ends with on the other two scorers. Return a dict of means over the seeds:

        train    mean of (train_score(final) - train_score(start))
        held     mean of (held_score(final)  - held_score(start))
        shifted  mean of (shifted_score(final) - shifted_score(start))
        gap      train - held     (positive = the improver overfitted the training tasks)
    """
    rounds = calls // settings.proposals
    train, held, shifted = [], [], []
    for s in seeds:
        final, _ = improve(start, train_score, random.Random(s), rounds, settings)
        train.append(train_score(final) - train_score(start))
        held.append(held_score(final) - held_score(start))
        shifted.append(shifted_score(final) - shifted_score(start))
    mean = lambda xs: sum(xs) / len(xs)
    out = {"train": mean(train), "held": mean(held), "shifted": mean(shifted)}
    out["gap"] = out["train"] - out["held"]
    return out


# =============================================================================
# GIVEN: improvers, honest and not
# =============================================================================
def honest(settings=SEED_SETTINGS):
    """An improver is a function (config, score, rng, rounds) -> config."""
    def run(config, score, rng, rounds):
        return improve(config, score, rng, rounds, settings)[0]
    return run


def cheat_budget(config, score, rng, rounds):
    """Cheat 1: score candidates with ten times the evaluation budget, so they look better."""
    best, best_s = config, meta_utility(config, TRAIN_TASKS, BUDGET * 10)
    for _ in range(rounds * 2):
        cand = perturb(best, CHOICES, rng, 1, 1)
        s = meta_utility(cand, TRAIN_TASKS, BUDGET * 10)
        if s > best_s:
            best, best_s = cand, s
    return best


def cheat_peek(config, score, rng, rounds):
    """Cheat 2: choose configs by their score on the held-out tasks."""
    best, best_s = config, meta_utility(config, HELD_TASKS, BUDGET)
    for _ in range(rounds * 2):
        cand = perturb(best, CHOICES, rng, 1, 1)
        s = meta_utility(cand, HELD_TASKS, BUDGET)
        if s > best_s:
            best, best_s = cand, s
    return best


def cheat_tamper(config, score, rng, rounds):
    """Cheat 3: raise the module's BUDGET constant, then use the honest scorer."""
    global BUDGET
    BUDGET = BUDGET * 10
    return improve(config, make_scorer(), rng, rounds)[0]


# =============================================================================
# Milestone 6: the audit
# =============================================================================
def audit(improver, start=DEFAULT, rounds=2, seed=0):
    """Run `improver` under surveillance. Return (ok, reasons).

    Snapshot BUDGET, TRAIN_TASKS and HELD_TASKS. Replace the module-level meta_utility by a
    spy (a function with the same signature that records (task_seeds, budget) and then calls
    the real one). Run improver(start, make_scorer(), random.Random(seed), rounds), then ALWAYS
    (use try/finally) put the real meta_utility and the three constants back.
    Reasons (strings, in this order, each at most once):
      "peeked"    some call used task seeds other than TRAIN_TASKS
      "budget"    some call used a budget other than the original BUDGET
      "tampered"  BUDGET, TRAIN_TASKS or HELD_TASKS differed after the run
    ok is True when there are no reasons.
    """
    global meta_utility, BUDGET, TRAIN_TASKS, HELD_TASKS
    real = meta_utility
    before = (BUDGET, TRAIN_TASKS, HELD_TASKS)
    calls = []

    def spy(config, task_seeds, budget, lo=20, hi=60):
        calls.append((tuple(task_seeds), budget))
        return real(config, task_seeds, budget, lo, hi)

    meta_utility = spy
    try:
        improver(start, make_scorer(), random.Random(seed), rounds)
        after = (BUDGET, TRAIN_TASKS, HELD_TASKS)
    finally:
        meta_utility = real
        BUDGET, TRAIN_TASKS, HELD_TASKS = before
    reasons = []
    if any(tasks != tuple(before[1]) for tasks, _ in calls):
        reasons.append("peeked")
    if any(b != before[0] for _, b in calls):
        reasons.append("budget")
    if after != before:
        reasons.append("tampered")
    return not reasons, reasons
