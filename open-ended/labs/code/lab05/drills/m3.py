# Drill: A7 Lab 5, milestone 3 of 6: the stand-in meta agent
# Everything else in this file is already written. Fill in:
#     propose
# Check it with: python3 check.py 3

"""Lab 5: a mini Meta Agent Search with strict search / selection / test splits.

The task is multi-step arithmetic read strictly left to right ("3 + 4 * 2" is 14), with one to
five operations per question. An AGENT DESIGN is four knobs:

    solver   "direct" (one call for the whole expression) or "steps" (one call per operation)
    prompt   "plain", "careful" or "terse" (a small, free change in accuracy per call)
    samples  how many independent answers to take and vote over: 1, 3, 5 or 7
    retries  verify-and-retry rounds after the vote: 0, 1, 2 or 3

The foundation model is a SEEDED SIMULATION, not a language model: it answers each call right
with a stated probability (lower for harder questions) and draws that probability from a hash,
so the same call always gets the same reply. The "meta agent" that proposes designs is a
deterministic stand-in too: it changes one knob of a good parent. No network, no clock.

What is GIVEN: the world, the Design record, the sealed test set, and a typo-injecting wrapper.
What YOU write is marked TODO:

    1  majority, build_agent, evaluate           (a design becomes an agent that can be scored)
    2  validate, Archive                         (a store of every design tried, and a gate in front of it)
    3  propose                                   (the stand-in meta agent)
    4  meta_search                               (the loop: propose, repair, evaluate, archive)
    5  three_way_split, choose_winner, final_report   (search / selection / test discipline)
    6  inflation                                 (measure how much the best of many overstates itself)

`python3 check.py` runs the milestones; the lab page explains each one.
"""
import hashlib
import random
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

# =============================================================================
# GIVEN: the task, the simulated model, designs
# =============================================================================
SPACE = {
    "solver": ["direct", "steps"],
    "prompt": ["plain", "careful", "terse"],
    "samples": [1, 3, 5, 7],
    "retries": [0, 1, 2, 3],
}
KNOBS = list(SPACE)                      # the order in which a design is written down
MAX_REPAIRS = 5                          # proposals the loop will reject before giving up on an iteration


def uniform(*parts) -> float:
    """A deterministic 'random number' in [0, 1) from a hash of the arguments."""
    h = hashlib.sha256("|".join(map(str, parts)).encode()).digest()
    return int.from_bytes(h[:6], "big") / 2 ** 48


def evaluate_expr(expr: str) -> int:
    """Evaluate strictly left to right: '3 + 4 * 2' is 14."""
    t = expr.split()
    v = int(t[0])
    for op, n in zip(t[1::2], t[2::2]):
        v = v + int(n) if op == "+" else v - int(n) if op == "-" else v * int(n)
    return v


def make_questions(n: int, seed: int) -> List[Tuple[str, int]]:
    """n distinct (expression, answer) pairs; difficulty cycles through 1 to 5 operations."""
    rng, out, seen = random.Random(seed), [], set()
    while len(out) < n:
        k = 1 + len(out) % 5
        e = str(rng.randint(1, 9))
        for _ in range(k):
            e += f" {rng.choice('+-*')} {rng.randint(1, 9)}"
        if e not in seen:
            seen.add(e)
            out.append((e, evaluate_expr(e)))
    return out


# Assumptions of the simulation (illustrative, not measurements of any real model):
P_DIRECT = {1: .85, 2: .66, 3: .50, 4: .38, 5: .28}     # one direct answer is right, by number of operations
P_STEP = .84                                             # one single-operation step is right
PROMPT_BONUS = {"plain": 0.0, "careful": .03, "terse": -.04}
TRAP = .55                                               # share of wrong answers that are the question's habitual slip
CATCH, FALSE_ALARM = .60, .12                            # the verifier flags 60% of wrong answers and 12% of right ones
_memo: Dict[tuple, int] = {}


@dataclass(frozen=True)
class Design:
    solver: str
    prompt: str
    samples: int
    retries: int

    @property
    def name(self) -> str:
        return f"{self.solver}-{self.prompt}-x{self.samples}-v{self.retries}"

    def as_dict(self) -> dict:
        return {k: getattr(self, k) for k in KNOBS}


ALL_DESIGNS = [Design(a, b, c, d) for a in SPACE["solver"] for b in SPACE["prompt"]
               for c in SPACE["samples"] for d in SPACE["retries"]]
SEEDS = [Design("direct", "plain", 1, 0), Design("direct", "plain", 3, 0)]    # the hand-written baselines


class Model:
    """The simulated foundation model. Every call is counted in `calls`."""

    def __init__(self):
        self.calls = 0

    def solve(self, kind: str, expr: str, attempt: int, prompt: str) -> int:
        """kind is 'direct' (whole expression) or 'step' (one operation). Same arguments, same reply."""
        self.calls += 1
        key = (kind, expr, attempt, prompt)
        if key not in _memo:
            if kind == "direct":
                p = P_DIRECT[len(expr.split()) // 2]
            else:
                p = P_STEP
            p = min(.99, max(.01, p + PROMPT_BONUS[prompt]))
            truth = evaluate_expr(expr)
            if uniform("ans", *key) < p:
                _memo[key] = truth
            elif uniform("trap", *key) < TRAP:        # a systematic slip: the same wrong answer on every attempt
                _memo[key] = truth + (1 + int(uniform("pull", expr) * 2)) * (1 if uniform("pside", expr) < .5 else -1)
            else:                                    # a random slip
                d = 1 + int(uniform("off", *key) * 4)
                _memo[key] = truth + (d if uniform("sgn", *key) < .5 else -d)
        return _memo[key]

    def verify(self, expr: str, value: int, attempt: int) -> bool:
        """A critic: True means 'looks right'."""
        self.calls += 1
        u = uniform("chk", expr, value, attempt)
        if value != evaluate_expr(expr):
            return u >= CATCH
        return u >= FALSE_ALARM


def solve_once(model: Model, design: Design, expr: str, attempt: int) -> int:
    """One attempt at a question under the design's solver and prompt (given)."""
    if design.solver == "direct":
        return model.solve("direct", expr, attempt, design.prompt)
    t = expr.split()
    acc = int(t[0])
    for op, n in zip(t[1::2], t[2::2]):
        acc = model.solve("step", f"{acc} {op} {n}", attempt, design.prompt)
    return acc


@dataclass
class Score:
    accuracy: float          # fraction of questions answered exactly right
    calls: float             # model calls per question (the cost)


@dataclass
class Entry:
    """One row of the archive."""
    design: Design
    score: float             # accuracy on the SEARCH questions
    calls: float
    parent: Optional[str] = None
    iteration: int = 0


@dataclass
class SearchResult:
    archive: "Archive"
    repairs: int             # proposals rejected for being invalid
    duplicates: int          # proposals rejected for already being in the archive
    skipped: int             # iterations that ended with no accepted proposal


class SealedSet:
    """A test set that can be opened exactly once. A second open() is a protocol violation."""

    def __init__(self, questions):
        self._q, self._opened = list(questions), False

    def open(self):
        if self._opened:
            raise RuntimeError("the test set was already opened: it may be scored once, at the very end")
        self._opened = True
        return list(self._q)

    def __len__(self):
        return len(self._q)


def with_typos(proposer: Callable, rate: float) -> Callable:
    """Wrap a proposer so that, with probability `rate`, its proposal is corrupted the way a model's
    code sometimes is: an unknown value for one knob. The loop must catch these (given)."""
    def noisy(archive, rng):
        raw, parent = proposer(archive, rng)
        raw = dict(raw)
        if rng.random() < rate:
            k = rng.choice(KNOBS)
            raw[k] = {"solver": "step", "prompt": "carefull", "samples": 4, "retries": -1}[k]
        return raw, parent
    return noisy


# =============================================================================
# Milestone 1: a design becomes an agent that can be scored
# =============================================================================
def majority(answers: List[int]) -> int:
    """The most common answer. A tie goes to the answer that appeared FIRST in the list."""
    counts: Dict[int, int] = {}
    for a in answers:
        counts[a] = counts.get(a, 0) + 1
    best = max(counts.values())
    return next(a for a in answers if counts[a] == best)


def build_agent(design: Design) -> Callable[[str, Model], int]:
    """Return forward(expr, model) -> int, the agent the design describes:

        1. take design.samples answers with solve_once, attempts 0, 1, 2, ...
        2. v = their majority
        3. for r in range(design.retries): if model.verify(expr, v, r) is True stop;
           otherwise v = solve_once(model, design, expr, 100 + r)   (a fresh attempt)
        4. return v
    """
    def forward(expr: str, model: Model) -> int:
        v = majority([solve_once(model, design, expr, i) for i in range(design.samples)])
        for r in range(design.retries):
            if model.verify(expr, v, r):
                break
            v = solve_once(model, design, expr, 100 + r)
        return v
    return forward


def evaluate(design: Design, questions, model: Optional[Model] = None) -> Score:
    """Build the agent and run it on every question with ONE model (the one passed in, or a fresh Model()).
    A question is right when the agent's answer equals the true answer. Return Score(accuracy, calls), where
    calls is the number of model calls per question, verifications included."""
    model = model or Model()
    forward = build_agent(design)
    right = sum(forward(q, model) == a for q, a in questions)
    return Score(right / len(questions), model.calls / len(questions))


# =============================================================================
# Milestone 2: a gate and an archive
# =============================================================================
def validate(raw: dict) -> Design:
    """Turn a proposal (a dict of knob values) into a Design, or raise ValueError saying what is wrong.
    Exactly the four knobs, each with a value from SPACE (True is not a number of samples, although
    True == 1). The message should name the offending knob: the meta agent reads it to repair its proposal."""
    if not isinstance(raw, dict):
        raise ValueError(f"a proposal is a dict of knobs, got {type(raw).__name__}")
    missing = [k for k in KNOBS if k not in raw]
    extra = [k for k in raw if k not in KNOBS]
    if missing or extra:
        raise ValueError(f"knobs must be exactly {KNOBS}; missing {missing}, unexpected {extra}")
    for k in KNOBS:
        v = raw[k]
        if isinstance(v, bool) or v not in SPACE[k]:
            raise ValueError(f"{k}={v!r} is not one of {SPACE[k]}")
    return Design(**{k: raw[k] for k in KNOBS})


class Archive:
    """Every design ever scored, kept even when it was worse than its parent."""

    def __init__(self):
        self.entries: List[Entry] = []
        self._names = set()

    def __len__(self):
        return len(self.entries)

    def __contains__(self, design: Design) -> bool:
        return design.name in self._names

    def add(self, entry: Entry) -> None:
        """Append the entry to self.entries and record its design's name in self._names (that is what `in`
        reads). Adding a design that is already stored is a bug in the caller: raise ValueError."""
        if entry.design in self:
            raise ValueError(f"{entry.design.name} is already in the archive")
        self.entries.append(entry)
        self._names.add(entry.design.name)

    def top(self, k: int) -> List[Entry]:
        """The k best entries by search score; ties go to fewer calls, then to the name. Does not modify the archive."""
        return sorted(self.entries, key=lambda e: (-e.score, e.calls, e.design.name))[:k]


# =============================================================================
# Milestone 3: the stand-in meta agent
# =============================================================================
def propose(archive: Archive, rng: random.Random) -> Tuple[dict, str]:
    """Pick a parent and change exactly one knob of it to a DIFFERENT value from SPACE.

    Draw up to 400 times. On draws 0 to 99 the parent is rng.choice(archive.top(3)).design; on later draws
    (the best designs' neighbours are used up) it is rng.choice(archive.entries).design. Then the knob is
    rng.choice(KNOBS) and the new value rng.choice of the other values in SPACE[knob], in the order of SPACE.
    The first child that is not in the archive wins: return (its knobs as a dict, the parent's name).
    If all 400 draws fail, raise RuntimeError.
    """
    raise NotImplementedError("TODO milestone 3: propose")


# =============================================================================
# Milestone 4: the search loop
# =============================================================================
def meta_search(proposer, search_questions, iterations: int, seed: int, seeds=SEEDS) -> SearchResult:
    """Meta Agent Search in miniature.

    1. archive = the seed designs, each evaluated on the SEARCH questions (iteration 0, parent None).
    2. For iteration 1..iterations: ask `proposer(archive, rng)` for (raw, parent_name), up to MAX_REPAIRS + 1
       times. A raw that validate() rejects counts as a repair and is asked again; a valid design already in the
       archive counts as a duplicate and is asked again. The first valid new design is evaluated on the search
       questions and added with its parent and the iteration number. If every ask fails, the iteration is skipped.
    Use rng = random.Random(seed). Nothing but the search questions is touched.
    """
    rng = random.Random(seed)
    archive, repairs, duplicates, skipped = Archive(), 0, 0, 0
    for d in seeds:
        s = evaluate(d, search_questions)
        archive.add(Entry(d, s.accuracy, s.calls, None, 0))
    for it in range(1, iterations + 1):
        for _ in range(MAX_REPAIRS + 1):
            raw, parent = proposer(archive, rng)
            try:
                design = validate(raw)
            except ValueError:
                repairs += 1
                continue
            if design in archive:
                duplicates += 1
                continue
            s = evaluate(design, search_questions)
            archive.add(Entry(design, s.accuracy, s.calls, parent, it))
            break
        else:
            skipped += 1
    return SearchResult(archive, repairs, duplicates, skipped)


# =============================================================================
# Milestone 5: three sets, used for three jobs
# =============================================================================
def three_way_split(pool, sizes: Tuple[int, int, int], seed: int):
    """Shuffle a copy of the pool with random.Random(seed) and cut the first sizes[0] items as the SEARCH set,
    the next sizes[1] as the SELECTION set and the next sizes[2] as the TEST set, wrapped in a SealedSet.
    Return (search, selection, sealed_test). The three sets share no question. The pool is not modified."""
    a, b, c = sizes
    if a + b + c > len(pool):
        raise ValueError(f"the sets need {a + b + c} questions but the pool has {len(pool)}")
    items = list(pool)
    random.Random(seed).shuffle(items)
    return items[:a], items[a:a + b], SealedSet(items[a + b:a + b + c])


def choose_winner(archive: Archive, selection_questions, shortlist: int = 5) -> Tuple[Entry, float]:
    """Take the `shortlist` best entries by SEARCH score, re-score each on the selection questions, and return
    (the entry with the highest selection accuracy, that accuracy). Ties go to fewer calls, then to the name."""
    scored = [(e, evaluate(e.design, selection_questions).accuracy) for e in archive.top(shortlist)]
    best = min(scored, key=lambda p: (-p[1], p[0].calls, p[0].design.name))
    return best


def final_report(winner: Entry, selection_score: float, sealed_test: SealedSet) -> dict:
    """Open the sealed test set ONCE, score the winner on it, and return a dict with the keys
    'design' (its name), 'search', 'selection', 'test' (accuracies), 'calls' (per question on the test set)
    and 'inflation' (search minus test)."""
    s = evaluate(winner.design, sealed_test.open())
    return {"design": winner.design.name, "search": winner.score, "selection": selection_score,
            "test": s.accuracy, "calls": s.calls, "inflation": winner.score - s.accuracy}


# =============================================================================
# Milestone 6: how much does the best of many overstate itself?
# =============================================================================
TRUTH = make_questions(600, seed=777)           # a large fixed set that stands in for "the real accuracy"
_truth_cache: Dict[str, float] = {}


def true_accuracy(design: Design) -> float:
    """Accuracy on the 600 TRUTH questions (given; cached)."""
    if design.name not in _truth_cache:
        _truth_cache[design.name] = evaluate(design, TRUTH).accuracy
    return _truth_cache[design.name]


def inflation(n_designs: int, n_questions: int, trials: int, seed: int) -> dict:
    """In each of `trials` repetitions (rng = random.Random(seed) throughout): draw n_questions fresh questions
    with make_questions(n_questions, rng.randrange(10**6)), draw n_designs distinct designs with rng.sample
    from ALL_DESIGNS, score all on those questions, keep the one with the highest score (ties: the first drawn),
    and look up its true_accuracy. Return the means over trials:
        {'looks': mean search score of the pick, 'is': mean true accuracy of the pick,
         'inflation': looks - is, 'best_available': mean of the best true accuracy among the drawn designs}
    """
    rng = random.Random(seed)
    looks, real, best = [], [], []
    for _ in range(trials):
        qs = make_questions(n_questions, rng.randrange(10 ** 6))
        ds = rng.sample(ALL_DESIGNS, n_designs)
        scores = [evaluate(d, qs).accuracy for d in ds]
        i = max(range(n_designs), key=lambda j: scores[j])
        looks.append(scores[i])
        real.append(true_accuracy(ds[i]))
        best.append(max(true_accuracy(d) for d in ds))
    m = lambda xs: sum(xs) / len(xs)
    return {"looks": m(looks), "is": m(real), "inflation": m(looks) - m(real), "best_available": m(best)}
