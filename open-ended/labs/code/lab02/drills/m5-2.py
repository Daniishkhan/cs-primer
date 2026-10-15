# Drill: A7 Lab 2, milestone 5 of 5: reading the map (step 2 of 4)
# Everything else in this file is already written. Fill in:
#     qd_score
# Check it with: python3 check.py 5

"""Lab 2 (reference solution): a deceptive maze, novelty search and MAP-Elites.

The maze is the one from chapter 3. A genome is a list of 45 moves (0 up, 1 down, 2 left,
3 right). A walker follows them from the start cell; a move into a wall does nothing. The
walker's BEHAVIOUR is the cell where it ends up.

    objective   -(straight-line distance from the final cell to the goal)
    novelty     mean distance from the final cell to its k nearest neighbours (population + archive)
    MAP-Elites  one elite per final cell, the genome that gets there in the fewest moves

A wall with a single gap runs between the start and the goal, so the final cells closest to the
goal are the ones pressed against the wall: the score points the wrong way.
"""
import math
import random
from dataclasses import dataclass, field

MAZE_ROWS = [
    "##############",
    "#..........G.#",
    "#............#",
    "#............#",
    "###.##########",      # the only gap is at column 3
    "#............#",
    "#............#",
    "#............#",
    "#...........S#",
    "##############",
]
MOVES = [(-1, 0), (1, 0), (0, -1), (0, 1)]      # 0 up, 1 down, 2 left, 3 right
STEPS = 45                                       # moves in a genome


# =============================================================================
# GIVEN: the maze, genomes, mutation, a result record, a few pictures
# =============================================================================
class Maze:
    def __init__(self, rows):
        self.rows = list(rows)
        self.height, self.width = len(rows), len(rows[0])
        self.start = self.goal = None
        for r, row in enumerate(rows):
            for c, ch in enumerate(row):
                if ch == "S":
                    self.start = (r, c)
                elif ch == "G":
                    self.goal = (r, c)

    def is_open(self, r, c):
        return 0 <= r < self.height and 0 <= c < self.width and self.rows[r][c] != "#"

    def open_cells(self):
        return [(r, c) for r in range(self.height) for c in range(self.width) if self.is_open(r, c)]

    def reachable(self, limit=STEPS):
        """Cells a walker can stand on after at most `limit` moves (breadth-first search)."""
        seen, frontier = {self.start: 0}, [self.start]
        while frontier:
            nxt = []
            for r, c in frontier:
                for dr, dc in MOVES:
                    p = (r + dr, c + dc)
                    if self.is_open(*p) and p not in seen and seen[(r, c)] < limit:
                        seen[p] = seen[(r, c)] + 1
                        nxt.append(p)
            frontier = nxt
        return seen          # cell -> shortest number of moves from the start


MAZE = Maze(MAZE_ROWS)


def random_genome(rng, steps=STEPS):
    return [rng.randrange(4) for _ in range(steps)]


def mutate(genome, rng, rate=0.05):
    """Replace each move by a random one with probability `rate`."""
    return [rng.randrange(4) if rng.random() < rate else m for m in genome]


@dataclass
class Result:
    solved: bool            # did any walker reach the goal?
    evals: int              # genomes evaluated (up to and including the generation that solved it)
    closest: float          # smallest distance to the goal seen
    visited: set = field(default_factory=set)       # every final cell any walker ended on


def render(maze, cells=(), mark="o"):
    """The maze as text with the given cells marked."""
    cells = set(cells)
    return "\n".join("".join(mark if (r, c) in cells and ch in ".SG" else ch for c, ch in enumerate(row))
                     for r, row in enumerate(maze.rows))


def render_archive(maze, archive, bins=1):
    """The maze with each filled archive cell showing its elite's arrival time in bands of five moves
    (0 = reached within 4 moves, 1 = 5 to 9, ..., 9 = 45); '?' marks a reachable cell nobody has filled.
    Only meaningful for bins=1."""
    out = []
    reach = maze.reachable()
    for r, row in enumerate(maze.rows):
        line = ""
        for c, ch in enumerate(row):
            if ch == "#":
                line += "#"
            elif (r, c) in archive:
                q = archive[(r, c)][0]
                line += str(min(9, round((1.0 - q) * STEPS) // 5))
            else:
                line += "?" if (r, c) in reach else " "
        out.append(line)
    return "\n".join(out)


# =============================================================================
# Milestone 1: the walker
# =============================================================================
def path(maze, genome):
    """The cells visited, as a list of length len(genome) + 1: the start cell, then the cell after each move.
    A move into a wall (or off the grid) leaves the walker where it is."""
    r, c = maze.start
    cells = [(r, c)]
    for m in genome:
        dr, dc = MOVES[m]
        if maze.is_open(r + dr, c + dc):
            r, c = r + dr, c + dc
        cells.append((r, c))
    return cells


def walk(maze, genome):
    """The behaviour of a genome: the cell where the walker ends up."""
    return path(maze, genome)[-1]


def goal_distance(maze, cell):
    """Straight-line (Euclidean) distance from `cell` to the goal."""
    return math.dist(cell, maze.goal)


def arrival_step(cells):
    """How many moves it took to reach the final cell for good: the index of the last move that changed
    the position (0 if the walker never moved). `cells` is a path as returned by `path`."""
    last = 0
    for i in range(1, len(cells)):
        if cells[i] != cells[i - 1]:
            last = i
    return last


# =============================================================================
# Milestone 2: the objective-driven genetic algorithm
# =============================================================================
def tournament(scores, rng, k=3):
    """Pick k random individuals (without replacement) and return the index of the one with the highest score."""
    return max(rng.sample(range(len(scores)), k), key=lambda i: scores[i])


def objective_scorer(maze):
    """A scorer for `evolve`: higher is better, so the score is minus the distance to the goal."""
    def scorer(ends, state):
        return [-goal_distance(maze, e) for e in ends]
    return scorer


def evolve(maze, scorer, seed, pop_size=60, gens=200):
    """A generational genetic algorithm with tournament selection and mutation (no crossover).

    Every generation: walk each genome to get its final cell; update `visited` and `closest`; if the goal
    has been reached stop and return Result(True, (gen + 1) * pop_size, 0.0, visited); otherwise ask
    `scorer(ends, state)` for one score per genome (`state` is a dict the scorer may use to remember
    things between generations) and build the next population with `tournament` and `mutate`.
    If the budget runs out return Result(False, gens * pop_size, closest, visited).
    """
    rng = random.Random(seed)
    pop = [random_genome(rng) for _ in range(pop_size)]
    state, visited, closest = {}, set(), math.inf
    for gen in range(gens):
        ends = [walk(maze, g) for g in pop]
        visited.update(ends)
        closest = min(closest, min(goal_distance(maze, e) for e in ends))
        if closest == 0:
            return Result(True, (gen + 1) * pop_size, 0.0, visited)
        scores = scorer(ends, state)
        pop = [mutate(pop[tournament(scores, rng)], rng) for _ in range(pop_size)]
    return Result(False, gens * pop_size, closest, visited)


# =============================================================================
# Milestone 3: novelty search
# =============================================================================
def novelty(cell, others, k=10):
    """Mean distance from `cell` to its k nearest neighbours among `others` (a list of cells).
    With fewer than k others, use all of them; with none at all the novelty is 0."""
    d = sorted(math.dist(cell, o) for o in others)[:k]
    return sum(d) / len(d) if d else 0.0


def novelty_scorer(k=10, threshold=1.5):
    """A scorer for `evolve` that ignores the goal. Each final cell is scored by its novelty against the
    other cells of this generation plus `state["archive"]`; afterwards every cell of the generation whose
    novelty exceeds `threshold` is appended to the archive."""
    def scorer(ends, state):
        archive = state.setdefault("archive", [])
        scores = [novelty(e, ends[:i] + ends[i + 1:] + archive, k) for i, e in enumerate(ends)]
        archive.extend(e for e, s in zip(ends, scores) if s > threshold)
        return scores
    return scorer


# =============================================================================
# Milestone 4: MAP-Elites
# =============================================================================
def descriptor(cell, bins=1):
    """The archive cell a final cell belongs to: (row // bins, col // bins)."""
    return (cell[0] // bins, cell[1] // bins)


def quality(maze, genome):
    """1 - arrival_step / len(genome): the fewer moves a genome needs to get where it ends up, the better.
    A genome that never leaves the start scores 1.0."""
    return 1.0 - arrival_step(path(maze, genome)) / len(genome)


def try_insert(archive, key, q, genome):
    """Local competition. Store (q, genome) under `key` if the cell is empty or q is STRICTLY better than
    the occupant's quality. Return True if the archive changed."""
    if key not in archive or q > archive[key][0]:
        archive[key] = (q, genome)
        return True
    return False


def map_elites(maze, evals, seed, bins=1, init=300):
    """MAP-Elites. The first `init` genomes are random; after that each genome is `mutate` applied to the elite
    of a uniformly random filled cell (rng.choice over the archive's cells, in sorted order so runs
    are repeatable). Every genome is evaluated once: its cell is descriptor(walk(maze, genome), bins) and its
    quality is `quality`. Returns the archive: {cell: (quality, genome)}."""
    rng = random.Random(seed)
    archive = {}
    for e in range(evals):
        if e < init or not archive:
            genome = random_genome(rng)
        else:
            parent = archive[rng.choice(sorted(archive))][1]
            genome = mutate(parent, rng)
        try_insert(archive, descriptor(walk(maze, genome), bins), quality(maze, genome), genome)
    return archive


# =============================================================================
# Milestone 5: reading the map
# =============================================================================
def coverage(archive, maze, bins=1):
    """Fraction of the reachable archive cells that hold an elite. (Reachable: the cells of
    maze.reachable(), mapped through `descriptor`.)"""
    reachable = {descriptor(c, bins) for c in maze.reachable()}
    return len(set(archive) & reachable) / len(reachable)


def qd_score(archive):
    """The sum of the elites' qualities."""
    raise NotImplementedError("TODO milestone 5: qd_score")


def solution_path(archive, maze, bins=1):
    """The elite genome's path (list of cells) for the cell that contains the goal, or None if that cell is empty."""
    key = descriptor(maze.goal, bins)
    if key not in archive:
        return None
    return path(maze, archive[key][1])


def stepping_stones(archive, maze, bins=1):
    """Cells of the solution path that are NOT closer to the goal than the start is: the part of the route where
    the objective gets worse before it gets better. Returns the sorted list of distinct cells on the path whose
    distance to the goal is greater than the start's, or None if the maze is unsolved."""
    p = solution_path(archive, maze, bins)
    if p is None:
        return None
    d0 = goal_distance(maze, maze.start)
    return sorted({c for c in p if goal_distance(maze, c) > d0})
