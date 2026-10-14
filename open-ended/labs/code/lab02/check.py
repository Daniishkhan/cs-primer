"""Self-check for Lab 2: Novelty Search & MAP-Elites on a deceptive maze.

    python3 check.py                  # checks your starter.py
    python3 check.py solution         # checks the reference solution
    python3 check.py solution 4       # only milestone 4
    python3 check.py solution 4 7     # milestone 4, replaying ONLY the random cases of seed 7

Everything is seeded: genomes, mutations, tournaments. There is no network and no clock, so the
same code gives the same result on every run. The whole check finishes in well under a minute
(about fifteen seconds for the reference solution); the three big experiments of milestones 2 to 5
are run once and shared.
Prints a tick, a cross, or "not implemented yet" for each milestone.
"""
import importlib
import math
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True

args = sys.argv[1:]
target = args[0] if args and not args[0].isdigit() else "starter"
rest = [a for a in args if a.isdigit()]
ONLY = int(rest[0]) if rest else None
ONLY_SEED = int(rest[1]) if len(rest) > 1 else None
mod = importlib.import_module(target)
results = []

RUNS = 30                    # seeds for the experiments (a single seed when replaying)
BUDGET = 12_000              # evaluations per run: 60 walkers for 200 generations


def seeds(default):
    return [ONLY_SEED] if ONLY_SEED is not None else list(default)


def check(number, name, fn):
    if ONLY is not None and ONLY != number:
        return
    try:
        note = fn()
        print(f"  ✔ {name}")
        for line in (note or "").splitlines():
            print(f"      {line}")
        results.append(True)
    except NotImplementedError as e:
        print(f"  … {name}: not implemented yet ({e})")
        results.append(False)
    except AssertionError as e:
        print(f"  ✘ {name}: {e}")
        results.append(False)
    except Exception as e:
        import traceback
        tb = traceback.extract_tb(e.__traceback__)
        where = next((f"{f.name}() line {f.lineno}" for f in reversed(tb) if f.filename.endswith(f"{target}.py")), "?")
        print(f"  ✘ {name}: {type(e).__name__}: {e}   [in {where}]")
        results.append(False)


def near(a, b, tol=1e-9):
    return abs(a - b) <= tol


# The route a sensible human would draw: 9 left, 7 up through the gap, 8 right. 24 moves, padded with bumps.
ROUTE = [2] * 9 + [0] * 7 + [3] * 8
ROUTE_GENOME = ROUTE + [0] * (mod.STEPS - len(ROUTE))        # the padding bumps into the top wall


def oracle_path(rows, genome):
    """An independent, deliberately plain walker for the cross-check."""
    start = next((r, row.index("S")) for r, row in enumerate(rows) if "S" in row)
    r, c = start
    out = [(r, c)]
    for m in genome:
        dr, dc = [(-1, 0), (1, 0), (0, -1), (0, 1)][m]
        nr, nc = r + dr, c + dc
        if 0 <= nr < len(rows) and 0 <= nc < len(rows[0]) and rows[nr][nc] != "#":
            r, c = nr, nc
        out.append((r, c))
    return out


# --- the shared experiments (run lazily, once) -------------------------------------------------
_CACHE = {}


def objective_runs():
    if "obj" not in _CACHE:
        sc = mod.objective_scorer(mod.MAZE)
        _CACHE["obj"] = [mod.evolve(mod.MAZE, sc, s) for s in seeds(range(RUNS))]
    return _CACHE["obj"]


def novelty_runs():
    if "nov" not in _CACHE:
        sc = mod.novelty_scorer()
        _CACHE["nov"] = [mod.evolve(mod.MAZE, mod.novelty_scorer(), s) for s in seeds(range(RUNS))]
    return _CACHE["nov"]


def elite_archives():
    if "me" not in _CACHE:
        _CACHE["me"] = [mod.map_elites(mod.MAZE, BUDGET, s) for s in seeds(range(RUNS))]
    return _CACHE["me"]


# =============================================================================
# Milestone 1: the walker
# =============================================================================
def m1():
    tiny = mod.Maze(["#####", "#S.G#", "#####"])
    assert mod.path(tiny, [3, 3, 3]) == [(1, 1), (1, 2), (1, 3), (1, 3)], (
        f"on '#S.G#' the moves right, right, right should give [(1,1), (1,2), (1,3), (1,3)] (the third move bumps the wall); "
        f"got {mod.path(tiny, [3, 3, 3])}")
    assert mod.path(tiny, []) == [(1, 1)], "an empty genome stays at the start; the path still contains the start cell"
    assert mod.path(tiny, [0, 1, 2]) == [(1, 1)] * 4, "up and down are walls; left is a wall too: the walker never moves"
    assert mod.walk(tiny, [3, 3]) == (1, 3) and mod.walk(tiny, [3, 2, 2]) == (1, 1), "walk returns the last cell of the path"
    edge = mod.Maze(["S.", "G."])        # no wall around it: stepping off the grid must not crash or wrap round
    assert mod.path(edge, [0, 2, 1, 3]) == [(0, 0), (0, 0), (0, 0), (1, 0), (1, 1)], (
        f"moves off the edge of the grid do nothing; expected [(0,0), (0,0), (0,0), (1,0), (1,1)], got {mod.path(edge, [0, 2, 1, 3])}")
    # the chapter's maze, by hand
    M = mod.MAZE
    assert M.start == (8, 12) and M.goal == (1, 11)
    assert mod.walk(M, [0] * 10) == (5, 12), f"ten steps up from the start stop at the wall: (5, 12); got {mod.walk(M, [0] * 10)}"
    assert mod.walk(M, [2] * 40) == (8, 1), "forty steps left run along the bottom row to the left-hand wall: (8, 1)"
    assert near(mod.goal_distance(M, M.start), math.sqrt(50)), f"start (8,12) to goal (1,11) is sqrt(7^2 + 1^2) = 7.0711, got {mod.goal_distance(M, M.start)}"
    assert mod.goal_distance(M, M.goal) == 0.0
    assert near(mod.goal_distance(M, (5, 11)), 4.0), "the cell just below the wall under the goal is at distance 4.0, the 'closest' a stuck walker gets"
    assert mod.arrival_step([(0, 0)]) == 0 and mod.arrival_step([(0, 0)] * 5) == 0, "never moved: 0"
    a, b, c = (0, 0), (0, 1), (0, 2)
    assert mod.arrival_step([a, b, b, c, c, c]) == 3, "the last change of position is the move with index 3"
    assert mod.arrival_step([a, b, a]) == 2, "wandering back counts: the last move that changed the position is move 2"
    assert mod.arrival_step([a, a, b]) == 2 and mod.arrival_step([a, b, c]) == 2

    # the hand-drawn route
    p = mod.path(M, ROUTE_GENOME)
    assert len(p) == mod.STEPS + 1 and p[-1] == M.goal, f"the 9-left, 7-up, 8-right route should end on the goal; ended at {p[-1]}"
    assert mod.arrival_step(p) == 24, f"that route reaches the goal after exactly 24 moves; arrival_step gave {mod.arrival_step(p)}"
    assert (4, 3) in p, "the route goes through the gap in the wall at (4, 3)"

    # randomised cross-check against a plain re-implementation
    for s in seeds(range(1, 7)):
        rng = random.Random(s)
        for _ in range(30):
            g = mod.random_genome(rng, rng.choice([0, 1, 5, 45, 80]))
            got, want = mod.path(M, g), oracle_path(M.rows, g)
            assert got == want, f"seed {s}: path differs from the reference walker for genome {g[:12]}...: first difference at move {next(i for i, (x, y) in enumerate(zip(got, want)) if x != y)}"
            assert mod.walk(M, g) == want[-1]
            assert all(M.is_open(*cell) for cell in got), "a walker must never stand inside a wall"
            assert all(abs(x[0] - y[0]) + abs(x[1] - y[1]) <= 1 for x, y in zip(got, got[1:])), "a move changes the position by at most one cell"
            ar = mod.arrival_step(got)
            assert all(got[i] == got[-1] for i in range(ar, len(got))), "after the arrival step the walker never moves again"
            assert ar == 0 or got[ar - 1] != got[ar], "the arrival step is itself a move that changed the position"
    return "paths agree with an independent walker on random genomes; the hand-drawn route needs 24 moves"


# =============================================================================
# Milestone 2: the objective-driven genetic algorithm
# =============================================================================
class CountingScorer:
    def __init__(self, inner=None):
        self.calls, self.sizes, self.states = 0, [], []
        self.inner = inner

    def __call__(self, ends, state):
        self.calls += 1
        self.sizes.append(len(ends))
        self.states.append(id(state))
        state["touched"] = state.get("touched", 0) + 1
        return self.inner(ends, state) if self.inner else [0.0] * len(ends)


def m2():
    # --- tournament
    rng = random.Random(0)
    n = 10
    scores = [float(i) for i in range(n)]
    picks = []
    for s in seeds(range(1, 4)):
        rng = random.Random(s)
        picks += [mod.tournament(scores, rng) for _ in range(4000)]
    assert min(picks) >= 2, (f"sampling 3 DIFFERENT individuals out of 10, the winner has at least two lower-scored rivals at most, "
                             f"so index 0 and 1 can never win; the tournament returned index {min(picks)}. Use rng.sample (without replacement).")
    top = picks.count(n - 1) / len(picks)
    assert abs(top - 0.3) < 0.03, f"the best of 10 wins whenever it is in the sample of 3, which is 3/10 of the time; got {top:.3f}"
    assert all(0 <= p < n for p in picks)
    rng = random.Random(5)
    k5 = [mod.tournament(scores, random.Random(i), k=5) for i in range(3000)]
    assert abs(k5.count(n - 1) / 3000 - 0.5) < 0.04, "with k=5 of 10 the best is in the sample half the time"

    # --- objective scorer
    M = mod.MAZE
    sc = mod.objective_scorer(M)
    got = sc([M.goal, M.start, (5, 11)], {})
    assert near(got[0], 0.0) and near(got[1], -math.sqrt(50)) and near(got[2], -4.0), (
        f"the objective score is minus the distance to the goal: expected [0, -7.071, -4.0], got {[round(x, 3) for x in got]}")

    # --- evolve: contract on tiny mazes
    unsolvable = mod.Maze(["#####", "#S#G#", "#####"])
    cs = CountingScorer()
    r = mod.evolve(unsolvable, cs, 3, pop_size=10, gens=7)
    assert isinstance(r, mod.Result) and r.solved is False, "a goal behind a wall cannot be solved"
    assert r.evals == 70, f"an unsolved run evaluates pop_size x gens = 70 genomes; Result.evals was {r.evals}"
    assert near(r.closest, 2.0) and r.visited == {(1, 1)}, f"closest should be 2.0 (S to G) and visited {{(1, 1)}}; got {r.closest}, {r.visited}"
    assert cs.calls == 7 and set(cs.sizes) == {10}, (f"the scorer is called once per generation (7) with one end cell per genome (10); "
                                                       f"got {cs.calls} calls with sizes {sorted(set(cs.sizes))}")
    assert len(set(cs.states)) == 1, "the same `state` dict must be passed in every generation (the novelty scorer keeps its archive there)"
    easy = mod.Maze(["#####", "#SG.#", "#####"])
    r = mod.evolve(easy, CountingScorer(), 1, pop_size=20, gens=50)
    assert r.solved and r.closest == 0.0 and (1, 2) in r.visited, "two cells from the goal on an open corridor: solved immediately"
    assert r.evals % 20 == 0 and 20 <= r.evals <= 200, f"evals counts whole generations of 20 up to and including the solving one; got {r.evals}"
    a = mod.evolve(M, mod.objective_scorer(M), 4, pop_size=30, gens=20)
    b = mod.evolve(M, mod.objective_scorer(M), 4, pop_size=30, gens=20)
    assert (a.solved, a.evals, a.closest, a.visited) == (b.solved, b.evals, b.closest, b.visited), "same seed, same run"
    # selection must use the scores: a scorer that likes the left-hand cells drives the population left
    left = lambda ends, st: [-c for _, c in ends]
    r = mod.evolve(M, left, 2, pop_size=40, gens=60)
    leftmost = min(c for _, c in r.visited)
    assert leftmost == 1, f"a scorer that rewards small column numbers should pull the population to the left wall (column 1); the leftmost cell visited was column {leftmost}"

    # --- the experiment: the objective is a trap
    runs = objective_runs()
    solved = sum(r.solved for r in runs)
    stuck = sorted(r.closest for r in runs if not r.solved)
    visited = sum(len(r.visited) for r in runs) / len(runs)
    if ONLY_SEED is None:
        assert solved <= 12, (f"distance-driven search should be trapped by the wall: it solved {solved} of {len(runs)} runs "
                              f"(expected at most 12, typically about 7). Is the score minus the distance, and is selection by tournament?")
        assert stuck[len(stuck) // 2] <= 4.2, (f"runs that fail should end pressed against the wall, at distance 4.0; the median closest approach was "
                                               f"{stuck[len(stuck) // 2]:.2f}")
        assert visited < 45, f"the population should huddle at the wall, ending on few distinct cells (under 45 of 85); on average {visited:.0f}"
    return (f"distance-driven GA, {len(runs)} runs of {BUDGET:,} evaluations: solved {solved}; failed runs ended a median "
            f"{stuck[len(stuck) // 2]:.1f} from the goal; ended on {visited:.0f} of 85 cells on average")


# =============================================================================
# Milestone 3: novelty search
# =============================================================================
def m3():
    assert near(mod.novelty((0, 0), [(0, 3), (4, 0)], k=1), 3.0), "k=1: the distance to the single nearest neighbour, (0, 3) at 3.0"
    assert near(mod.novelty((0, 0), [(0, 3), (4, 0)], k=2), 3.5), "k=2: mean of 3.0 and 4.0"
    assert near(mod.novelty((0, 0), [(4, 0), (0, 3), (0, 9)], k=2), 3.5), "the neighbours are the NEAREST ones, however the list is ordered"
    assert near(mod.novelty((0, 0), [(3, 4)], k=10), 5.0), "fewer than k others: use all of them"
    assert mod.novelty((0, 0), [], k=10) == 0.0, "no others at all: novelty 0, not a crash"
    assert near(mod.novelty((2, 2), [(2, 2), (2, 2), (5, 6)], k=3), 5.0 / 3), "identical behaviours are at distance 0 and count as neighbours"

    sc = mod.novelty_scorer(k=10, threshold=7.0)
    state = {}
    ends = [(0, 0), (0, 0), (0, 10)]
    got = sc(ends, state)
    assert [round(x, 6) for x in got] == [5.0, 5.0, 10.0], (f"the lonely cell (0, 10) is 10 from each of the two cells at the origin; each origin cell is "
                                                              f"0 from its twin and 10 from the loner (mean 5). Expected [5, 5, 10], got {got}")
    assert state.get("archive") == [(0, 10)], f"only cells whose novelty EXCEEDS the threshold (7) enter the archive: expected [(0, 10)], got {state.get('archive')}"
    got = sc([(0, 10), (0, 5)], state)
    assert near(got[0], 2.5) and near(got[1], 5.0), (f"(0, 10) is now in the archive, so against the other cell (distance 5) and its archived twin (distance 0) "
                                                      f"its novelty is (0 + 5) / 2 = 2.5, and the other cell is 5 from both: expected [2.5, 5.0], got {got}")
    sc2 = mod.novelty_scorer(k=10, threshold=1.5)
    st2 = {}
    sc2([(0, 0), (0, 4)], st2)
    sc2([(0, 0), (0, 4)], st2)
    assert len(st2["archive"]) > 2, "the archive keeps growing across generations (state persists between calls)"
    st3 = {}
    mod.novelty_scorer(threshold=100.0)([(0, 0), (9, 9)], st3)
    assert st3.get("archive") == [], "nothing is novel enough: the archive stays an empty list (but exists)"

    # --- the experiment
    obj, nov = objective_runs(), novelty_runs()
    s_obj, s_nov = sum(r.solved for r in obj), sum(r.solved for r in nov)
    v_obj = sum(len(r.visited) for r in obj) / len(obj)
    v_nov = sum(len(r.visited) for r in nov) / len(nov)
    if ONLY_SEED is None:
        assert s_nov >= 15, f"novelty search should solve at least 15 of {len(nov)} runs (typically about 21); yours solved {s_nov}"
        assert s_nov >= s_obj + 6, f"novelty search ({s_nov}) should beat the distance-driven search ({s_obj}) by a wide margin"
        assert v_nov > 65, f"novelty search should spread over most of the 85 cells; on average it ended walkers on {v_nov:.0f}"
        assert v_nov > 1.6 * v_obj, f"novelty ({v_nov:.0f} cells) should cover far more of the maze than the distance-driven search ({v_obj:.0f})"
    ev = sorted(r.evals for r in nov if r.solved)
    med = ev[len(ev) // 2] if ev else None
    return (f"{len(nov)} runs of {BUDGET:,} evaluations each: distance-driven GA solved {s_obj}, novelty-search GA solved {s_nov}"
            f" (median {med:,} evaluations)\n"
            f"distinct cells ever occupied, mean per run: distance-driven {v_obj:.0f} of 85, novelty {v_nov:.0f} of 85")


# =============================================================================
# Milestone 4: MAP-Elites
# =============================================================================
def m4():
    assert mod.descriptor((8, 12)) == (8, 12) and mod.descriptor((8, 12), bins=1) == (8, 12), "bins=1: the cell is its own archive cell"
    assert mod.descriptor((8, 12), bins=2) == (4, 6) and mod.descriptor((1, 11), bins=3) == (0, 3) and mod.descriptor((5, 5), 5) == (1, 1), \
        "descriptor(cell, bins) = (row // bins, col // bins)"
    M = mod.MAZE
    assert near(mod.quality(M, [3] * 45), 1.0), "a genome that bumps into the wall from the first move never leaves the start: quality 1.0"
    assert near(mod.quality(M, [0] + [3] * 44), 1 - 1 / 45), "one move then still: arrival step 1, quality 1 - 1/45"
    assert near(mod.quality(M, ROUTE_GENOME), 1 - 24 / 45), "the 24-move route to the goal has quality 1 - 24/45 = 0.467"
    wander = [2, 3] + [3] * 43
    assert near(mod.quality(M, wander), 1 - 2 / 45), "[left, right, then bumps]: the last move that changes the position is move 2"
    assert near(mod.quality(M, [2] * 45), 1 - 11 / 45), "eleven steps left reach (8, 1); the remaining thirty-four moves bump into the wall"
    assert mod.quality(M, [2] * 5 + [1] * 40) > mod.quality(M, [2] * 45), "arriving earlier scores higher"

    # --- try_insert
    arch = {}
    assert mod.try_insert(arch, (1, 1), 0.5, "A") is True and arch == {(1, 1): (0.5, "A")}, "an empty cell accepts any elite"
    assert mod.try_insert(arch, (1, 1), 0.4, "B") is False and arch[(1, 1)] == (0.5, "A"), "a worse child is discarded"
    assert mod.try_insert(arch, (1, 1), 0.5, "C") is False and arch[(1, 1)] == (0.5, "A"), "a tie does NOT replace the elite (strictly better only)"
    assert mod.try_insert(arch, (1, 1), 0.9, "D") is True and arch[(1, 1)] == (0.9, "D"), "a better child replaces the elite"
    assert mod.try_insert(arch, (2, 2), 0.1, "E") is True and len(arch) == 2, "a bad solution in a new cell is kept: it has the cell to itself"

    # --- map_elites: structural properties
    for s in seeds((1, 2, 3)):
        a = mod.map_elites(M, 2000, s)
        assert 0 < len(a) <= 2000
        for key, (q, g) in a.items():
            assert len(g) == mod.STEPS, f"seed {s}: elites are genomes of {mod.STEPS} moves"
            assert key == mod.descriptor(mod.walk(M, g)), f"seed {s}: the elite stored under {key} actually ends at {mod.walk(M, g)}"
            assert near(q, mod.quality(M, g)), f"seed {s}: the stored quality {q:.3f} does not match the genome's quality {mod.quality(M, g):.3f}"
            assert M.is_open(*key)
        # prefix property: more evaluations never make any cell worse and never lose a cell
        b = mod.map_elites(M, 4000, s)
        assert set(a) <= set(b), f"seed {s}: doubling the budget lost cells {sorted(set(a) - set(b))[:3]}: an elite was removed, or the run is not a prefix of the longer run"
        assert all(b[k][0] >= a[k][0] - 1e-12 for k in a), f"seed {s}: a cell got WORSE with more evaluations; replacement must only accept strictly better quality"
        assert mod.map_elites(M, 2000, s).keys() == a.keys(), f"seed {s}: same seed, same archive"
    only_random = mod.map_elites(M, 100, 1, init=300)
    assert len(only_random) <= 100, "with fewer evaluations than `init`, every genome is random"
    coarse = mod.map_elites(M, 3000, 1, bins=4)
    assert all(k[0] <= 2 and k[1] <= 3 for k in coarse) and 1 < len(coarse) <= 3 * 4, (
        f"with bins=4 the 10x14 maze has at most 3 x 4 archive cells; got keys {sorted(coarse)}")
    return "descriptors, quality, local competition and the loop satisfy the structural invariants of chapter 4"


# =============================================================================
# Milestone 5: reading the map
# =============================================================================
def m5():
    M = mod.MAZE
    assert near(mod.qd_score({(1, 1): (0.5, "a"), (2, 2): (0.25, "b")}), 0.75) and mod.qd_score({}) == 0.0, "the QD-score is the sum of the elites' qualities"
    arch = {M.start: (1.0, "g")}
    assert near(mod.coverage(arch, M), 1 / 85), f"one filled cell of the 85 reachable cells: 1/85 = {1 / 85:.4f}, got {mod.coverage(arch, M)}"
    assert mod.coverage({}, M) == 0.0
    full = {c: (0.5, "g") for c in M.reachable()}
    assert near(mod.coverage(full, M), 1.0)
    full[(0, 0)] = (0.5, "wall cell that should be ignored")
    assert near(mod.coverage(full, M), 1.0), "keys that are not reachable cells do not count towards coverage (and cannot push it above 1)"
    blocks = {mod.descriptor(c, 5) for c in M.reachable()}
    assert near(mod.coverage({k: (1.0, "g") for k in list(blocks)[:2]}, M, bins=5), 2 / len(blocks)), "with bins=5 coverage is measured over the 5x5 blocks that contain reachable cells"

    # --- solution_path and stepping_stones on a hand-made archive
    assert mod.solution_path({M.start: (1.0, "g")}, M) is None and mod.stepping_stones({M.start: (1.0, "g")}, M) is None, "no elite in the goal's cell: None"
    arch = {M.goal: (1 - 24 / 45, ROUTE_GENOME)}
    p = mod.solution_path(arch, M)
    assert p == oracle_path(M.rows, ROUTE_GENOME) and p[-1] == M.goal, "solution_path is the full path (start included) of the elite stored under the goal's cell"
    d0 = math.dist(M.start, M.goal)
    want = sorted({c for c in p if math.dist(c, M.goal) > d0})
    got = mod.stepping_stones(arch, M)
    assert got == want, (f"stepping stones are the distinct cells of the route that are farther from the goal than the start is. "
                         f"Expected {len(want)} cells {want[:4]}..., got {got if got is None else (len(got), got[:4])}")
    assert (4, 3) in got and (8, 3) in got and M.start not in got and M.goal not in got
    # the objective scores those cells below the start: this is the deception, in numbers
    assert all(mod.goal_distance(M, c) > mod.goal_distance(M, M.start) for c in got)

    # --- the experiment: three methods on one problem
    obj, nov, archives = objective_runs(), novelty_runs(), elite_archives()
    s_obj, s_nov = sum(r.solved for r in obj), sum(r.solved for r in nov)
    solved_me = [a for a in archives if mod.solution_path(a, M) is not None]
    cov = [mod.coverage(a, M) for a in archives]
    qd = [mod.qd_score(a) for a in archives]
    v_obj = sum(len(r.visited) for r in obj) / len(obj)
    if ONLY_SEED is None:
        assert len(solved_me) >= 18, (f"MAP-Elites with {BUDGET:,} evaluations should reach the goal in at least 18 of {len(archives)} runs "
                                      f"(typically 26); yours did in {len(solved_me)}. Parents must be chosen uniformly from ALL filled cells.")
        assert len(solved_me) > s_obj + 8, f"MAP-Elites ({len(solved_me)}) should far outdo the distance-driven search ({s_obj})"
        assert sum(cov) / len(cov) > 0.93, f"MAP-Elites should fill more than 93% of the reachable cells on average; it filled {100 * sum(cov) / len(cov):.1f}%"
        assert min(cov) > 0.8, f"even the worst run should fill 80% of the cells; the worst filled {100 * min(cov):.0f}%"
        assert sum(cov) / len(cov) * 85 > 1.9 * v_obj, "the archive should cover about twice as many cells as the distance-driven population ever visits"
    for a in solved_me[:5]:
        stones = mod.stepping_stones(a, M)
        assert stones and (4, 3) in stones, ("every solved archive's route passes through the gap at (4, 3), a cell the objective scores WORSE than the start: "
                                               f"stepping_stones returned {stones}")
    # the QD-score grows with the budget
    s0 = seeds([0])[0]
    qds = [mod.qd_score(mod.map_elites(M, n, s0)) for n in (1000, 3000, 12000)]
    assert qds[0] < qds[1] < qds[2], f"QD-score must grow with the evaluation budget; got {[round(x, 2) for x in qds]}"
    shown = solved_me[0] if solved_me else archives[0]
    note = [f"{len(archives)} runs of {BUDGET:,} evaluations each:",
            f"  distance-driven GA   solved {s_obj:>2}  cells ever occupied {v_obj:5.1f} of 85",
            f"  novelty-search GA    solved {s_nov:>2}  cells ever occupied {sum(len(r.visited) for r in nov) / len(nov):5.1f} of 85",
            f"  MAP-Elites           solved {len(solved_me):>2}  cells filled        {85 * sum(cov) / len(cov):5.1f} of 85   mean QD-score {sum(qd) / len(qd):.2f}",
            f"  QD-score of one MAP-Elites run after 1,000 / 3,000 / 12,000 evaluations: " + " / ".join(f"{x:.2f}" for x in qds),
            "arrival time of each cell's elite, in bands of 5 moves (0 = within 4 moves), for one run:"]
    note += ["  " + line for line in mod.render_archive(M, shown).splitlines()]
    return "\n".join(note)


MILESTONES = [
    (1, "Milestone 1: the walker", m1),
    (2, "Milestone 2: a genetic algorithm that follows the objective", m2),
    (3, "Milestone 3: novelty search", m3),
    (4, "Milestone 4: MAP-Elites", m4),
    (5, "Milestone 5: reading the map", m5),
]

if __name__ == "__main__":
    t0 = time.time()
    print(f"Lab 2 checks against {target}.py\n")
    for n, name, fn in MILESTONES:
        check(n, name, fn)
    print(f"\n{sum(results)}/{len(results)} milestones passing  ({time.time() - t0:.1f} s)")
    sys.exit(0 if all(results) else 1)
