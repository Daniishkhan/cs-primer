"""Self-check for Lab 1: Bandits & Monte Carlo Tree Search.

    python3 check.py                  # checks your starter.py
    python3 check.py solution         # checks the reference solution
    python3 check.py solution 4       # only milestone 4
    python3 check.py solution 4 7     # milestone 4, replaying ONLY the random cases of seed 7

Everything is seeded: the bandits, the playouts, the games. There is no network and no
clock, so the same code gives the same result on every run. The whole check finishes in
well under a minute (about ten seconds for the reference solution).
Prints a tick, a cross, or "not implemented yet" for each milestone.
"""
import importlib
import math
import os
import random
import sys
import time
from functools import partial

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

CHAPTER_ARMS = [0.30, 0.45, 0.50]       # the bandit of chapter 1


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


# =============================================================================
# Milestone 1: regret, greedy, epsilon-greedy
# =============================================================================
def m1():
    # --- regret, by hand
    r = mod.pseudo_regret(CHAPTER_ARMS, [10, 20, 70])
    assert near(r, 3.0), (f"pseudo_regret([0.30, 0.45, 0.50], [10, 20, 70]) should be 10*0.20 + 20*0.05 + 70*0 = 3.0, got {r}. "
                          "Regret is the sum over arms of pulls * (best mean - this arm's mean).")
    assert near(mod.pseudo_regret([0.5, 0.5], [3, 9]), 0.0), "when every arm is equally good no pull costs anything"
    assert near(mod.pseudo_regret([0.1, 0.9], [0, 100]), 0.0), "pulling only the best arm has zero regret"

    # --- greedy, by hand
    rng = random.Random(0)
    assert mod.greedy([5, 5, 5], [1, 4, 2], 16, rng) == 1, "greedy must pull the arm with the best average (arm 1: 4/5)"
    assert mod.greedy([3, 0, 2], [1, 0, 1], 6, rng) == 1, "an arm that has never been pulled must be tried before any greedy choice"
    assert mod.greedy([0, 0, 0], [0, 0, 0], 1, rng) == 0, "with nothing tried yet, the lowest index goes first"
    assert mod.greedy([4, 4], [2, 2], 9, rng) == 0, "ties go to the lowest index"
    assert mod.greedy([100, 2], [40, 2], 103, rng) == 1, ("the average decides, not the count: arm 1 has 2/2 = 1.0, arm 0 has 0.4. "
                                                          "(This is exactly how greedy gets locked in by luck.)")

    # --- epsilon-greedy, statistically
    counts, totals = [10, 10, 10], [2, 3, 9]            # arm 2 is clearly the best average
    for eps in (0.0, 0.1, 0.3, 0.9):
        picks = []
        for s in seeds((1, 2, 3)):
            rng = random.Random(s)
            picks += [mod.epsilon_greedy(counts, totals, 31, rng, eps=eps) for _ in range(3000)]
        off = sum(p != 2 for p in picks) / len(picks)
        want = eps * 2 / 3                                # an exploring pull lands off the best arm 2 times in 3
        assert abs(off - want) < 0.025, (f"eps={eps}: expected about {want:.3f} of the pulls to be off the best arm "
                                         f"(exploring with probability eps, then a uniformly random arm of 3), got {off:.3f}. "
                                         "Draw one rng.random() to decide, then rng.randrange(n_arms) only when exploring.")
    assert mod.epsilon_greedy([3, 0, 2], [1, 0, 1], 6, random.Random(0), eps=0.0) == 1, "with eps=0, untried arms are still tried first"

    # --- mean_regret, exactly
    got = mod.mean_regret(lambda c, t, k, rng: 0, [0.3, 0.5], 100, range(5))
    assert near(got, 100 * 0.2, 1e-9), f"always pulling arm 0 of [0.3, 0.5] for 100 steps costs exactly 20.0 regret, got {got}"
    got = mod.mean_regret(lambda c, t, k, rng: 1, [0.3, 0.5], 100, range(5))
    assert got == 0.0, f"always pulling the best arm costs 0 regret, got {got}"

    # --- the experiment of chapter 1
    seeds_ = range(100)
    rg = mod.mean_regret(mod.greedy, CHAPTER_ARMS, 2000, seeds_)
    re = mod.mean_regret(partial(mod.epsilon_greedy, eps=0.1), CHAPTER_ARMS, 2000, seeds_)
    assert rg > 100, f"greedy should lock on to a wrong arm in many runs and lose well over 100 in 2000 pulls; its mean regret was {rg:.1f}"
    assert re < 80, f"epsilon-greedy (eps=0.1) should have a mean regret under 80 here; yours was {re:.1f}"
    assert re < rg / 2, "epsilon-greedy should beat greedy by a wide margin"
    r0 = mod.mean_regret(partial(mod.epsilon_greedy, eps=0.1), [0.2, 0.5, 0.8], 500, seeds_)
    r1 = mod.mean_regret(partial(mod.epsilon_greedy, eps=0.1), [0.2, 0.5, 0.8], 4000, seeds_)
    assert r1 > 4 * r0, (f"epsilon-greedy keeps exploring forever, so its regret should grow roughly linearly: "
                         f"500 pulls gave {r0:.1f} and 4000 pulls {r1:.1f} (expected a ratio above 4)")
    return (f"chapter bandit, 2000 pulls, mean regret over 100 seeds: greedy {rg:.1f}, epsilon-greedy(0.1) {re:.1f}\n"
            f"epsilon-greedy on a 0.2/0.5/0.8 bandit: regret {r0:.1f} after 500 pulls, {r1:.1f} after 4000 (linear growth)")


# =============================================================================
# Milestone 2: UCB1
# =============================================================================
def m2():
    counts, totals, t, c = [4, 2, 1], [2.0, 1.0, 0.0], 8, 1.0
    want = [0.5 + math.sqrt(math.log(8) / 4), 0.5 + math.sqrt(math.log(8) / 2), 0.0 + math.sqrt(math.log(8) / 1)]
    got = mod.ucb_scores(counts, totals, t, c)
    for i in range(3):
        assert near(got[i], want[i], 1e-9), (f"ucb_scores arm {i}: expected mean + c*sqrt(ln t / n) = {want[i]:.4f}, got {got[i]:.4f}. "
                                             f"(mean {[0.5, 0.5, 0.0][i]}, n={counts[i]}, t={t}, c={c})")
    got2 = mod.ucb_scores(counts, totals, t, 0.5)
    assert near(got2[1], 0.5 + 0.5 * math.sqrt(math.log(8) / 2)), "the constant c multiplies only the bonus, not the mean"
    got3 = mod.ucb_scores([3, 0], [1, 0], 4, 1.0)
    assert got3[1] == math.inf and math.isfinite(got3[0]), "an arm with zero pulls has an infinite bound (no division by zero)"
    assert mod.ucb_scores([3, 0], [1, 0], 4, 0.0)[1] == math.inf, "even with c=0 an untried arm must come first"

    rng = random.Random(0)
    # which arm wins in the hand example: arm 1 (1.5196) beats arm 2 (1.4420) and arm 0 (1.2210)
    assert mod.ucb1(counts, totals, t, rng, c=1.0) == 1, f"scores {[round(x, 3) for x in want]}: arm 1 has the highest bound, got arm {mod.ucb1(counts, totals, t, rng, c=1.0)}"
    assert mod.ucb1([0, 0, 0], [0, 0, 0], 1, rng) == 0 and mod.ucb1([2, 0, 0], [1, 0, 0], 3, rng) == 1, "untried arms first, lowest index first"
    assert mod.ucb1([4, 4], [2, 2], 9, rng) == 0, "ties go to the lowest index"
    # the same evidence, different appetite for risk
    assert mod.ucb1([50, 2], [30.0, 1.0], 52, rng, c=1.0) == 1, "with a big bonus the barely-tried arm gets another look"
    assert mod.ucb1([50, 2], [30.0, 1.0], 52, rng, c=0.01) == 0, "with a tiny bonus the arm with the better average wins (c near 0 is greedy)"
    assert mod.ucb1([50, 2], [30.0, 1.0], 52, rng, c=0.0) == 0, "c=0 is exactly greedy"

    # it never abandons an arm for ever: the bonus keeps growing with ln t while the arm sleeps
    counts, totals = [1000, 1], [900.0, 0.0]
    assert mod.ucb1(counts, totals, 1001, rng, c=0.1) == 0, "with a small c a once-failed arm is not retried straight away"
    assert mod.ucb1(counts, totals, 10 ** 300, rng, c=0.1) == 1, \
        "ln t keeps growing while the arm is left alone, so eventually its bound must overtake the leader's"

    # the experiment
    S = range(100)
    ru14 = mod.mean_regret(partial(mod.ucb1, c=1.41), CHAPTER_ARMS, 2000, S)
    ru05 = mod.mean_regret(partial(mod.ucb1, c=0.5), CHAPTER_ARMS, 2000, S)
    ru02 = mod.mean_regret(partial(mod.ucb1, c=0.2), CHAPTER_ARMS, 2000, S)
    rgr = mod.mean_regret(mod.greedy, CHAPTER_ARMS, 2000, S)
    assert ru14 < rgr and ru05 < rgr, f"UCB should beat greedy (regret {rgr:.1f}); got {ru14:.1f} for c=1.41 and {ru05:.1f} for c=0.5"
    assert ru05 < ru14, (f"on this bandit the textbook c = 1.41 over-explores: c=0.5 should have lower regret "
                         f"(got {ru05:.1f} for c=0.5 and {ru14:.1f} for c=1.41)")
    assert ru05 < ru02, f"...but c=0.2 is too greedy: c=0.5 should beat it ({ru05:.1f} against {ru02:.1f})"
    easy = [0.2, 0.5, 0.8]
    a = mod.mean_regret(partial(mod.ucb1, c=1.0), easy, 500, S)
    b = mod.mean_regret(partial(mod.ucb1, c=1.0), easy, 4000, S)
    assert b < 2.5 * a, (f"UCB's regret should grow like log t: {a:.1f} after 500 pulls and {b:.1f} after 4000 "
                         f"(a straight line would be 8 times larger; it must be under 2.5 times)")
    counts, _ = mod.run_bandit(partial(mod.ucb1, c=1.0), easy, 2000, 5)
    assert counts[2] > 0.85 * 2000, f"UCB should put over 85% of 2000 pulls on the best arm of {easy}; got {counts}"
    return (f"chapter bandit, 2000 pulls, mean regret: UCB c=1.41 {ru14:.1f}, c=0.5 {ru05:.1f}, c=0.2 {ru02:.1f} (greedy {rgr:.1f})\n"
            f"0.2/0.5/0.8 bandit: UCB regret {a:.1f} after 500 pulls, {b:.1f} after 4000 (logarithmic growth)")


# =============================================================================
# Milestone 3: Thompson sampling
# =============================================================================
class ScriptedRng:
    """Records the arguments of betavariate and returns scripted draws."""

    def __init__(self, draws):
        self.draws, self.calls = list(draws), []

    def betavariate(self, a, b):
        self.calls.append((a, b))
        return self.draws[len(self.calls) - 1]

    def random(self):
        raise AssertionError("thompson() should only use rng.betavariate")


def m3():
    rng = ScriptedRng([0.2, 0.9, 0.5])
    arm = mod.thompson([10, 4, 6], [7.0, 1.0, 3.0], 21, rng)
    assert [tuple(map(float, x)) for x in rng.calls] == [(8.0, 4.0), (2.0, 4.0), (4.0, 4.0)], (
        f"each arm's belief is Beta(1 + wins, 1 + losses), one rng.betavariate call per arm in index order. "
        f"Expected [(8, 4), (2, 4), (4, 4)] for 7/10, 1/4, 3/6; got {rng.calls}")
    assert arm == 1, f"the arm with the largest draw wins: draws were [0.2, 0.9, 0.5], so arm 1; got arm {arm}"
    arm = mod.thompson([0, 0], [0.0, 0.0], 1, ScriptedRng([0.3, 0.8]))
    assert arm == 1, "with no data every arm is Beta(1, 1); the larger draw wins"

    # clear evidence is followed, ignorance is explored
    for s in seeds((1, 2, 3)):
        rng = random.Random(s)
        picks = [mod.thompson([1000, 1000], [900.0, 100.0], 2001, rng) for _ in range(300)]
        assert set(picks) == {0}, f"seed {s}: with 900/1000 against 100/1000 Thompson sampling should always pick arm 0, got {set(picks)}"
        picks = [mod.thompson([0, 0, 0], [0.0, 0.0, 0.0], 1, rng) for _ in range(3000)]
        shares = [picks.count(i) / len(picks) for i in range(3)]
        assert all(abs(x - 1 / 3) < 0.04 for x in shares), f"seed {s}: with no data the three arms should be picked about equally, got {shares}"
        rng = random.Random(s)
        picks = [mod.thompson([10, 2], [5.0, 1.0], 13, rng) for _ in range(2000)]
        share_b = picks.count(1) / len(picks)
        assert 0.25 < share_b < 0.55, (f"seed {s}: arm 0 is 5/10, arm 1 is 1/2: arm 1's belief is wider so it should win a large minority "
                                       f"of draws (between 25% and 55%), got {share_b:.2f}")

    S = range(100)
    rt = mod.mean_regret(mod.thompson, CHAPTER_ARMS, 2000, S)
    re = mod.mean_regret(partial(mod.epsilon_greedy, eps=0.1), CHAPTER_ARMS, 2000, S)
    ru = mod.mean_regret(partial(mod.ucb1, c=1.41), CHAPTER_ARMS, 2000, S)
    rg = mod.mean_regret(mod.greedy, CHAPTER_ARMS, 2000, S)
    assert rt < re and rt < ru and rt < rg, (f"with no constant to tune, Thompson sampling should beat greedy ({rg:.1f}), epsilon-greedy "
                                             f"({re:.1f}) and textbook UCB ({ru:.1f}) on the chapter bandit; yours: {rt:.1f}")
    assert rt < 45, f"Thompson sampling should have a mean regret well under 45 here; got {rt:.1f}"
    a = mod.mean_regret(mod.thompson, [0.2, 0.5, 0.8], 500, S)
    b = mod.mean_regret(mod.thompson, [0.2, 0.5, 0.8], 4000, S)
    assert b < 2.5 * a, f"Thompson regret should grow slowly: {a:.1f} after 500 pulls, {b:.1f} after 4000 (a straight line would be 8x)"

    # the league table over three different problems
    problems = {"chapter 0.30/0.45/0.50": CHAPTER_ARMS, "easy 0.2/0.5/0.8": [0.2, 0.5, 0.8],
                "ten arms, one good": [0.1] * 9 + [0.3]}
    policies = [("greedy", mod.greedy), ("epsilon-greedy 0.1", partial(mod.epsilon_greedy, eps=0.1)),
                ("UCB1 c=0.5", partial(mod.ucb1, c=0.5)), ("UCB1 c=1.41", partial(mod.ucb1, c=1.41)),
                ("Thompson", mod.thompson)]
    lines = [f"{'mean regret after 2000 pulls (50 seeds)':42s}" + "".join(f"{n:>24s}" for n in problems)]
    table = {}
    for pname, p in policies:
        row = [mod.mean_regret(p, probs, 2000, range(50)) for probs in problems.values()]
        table[pname] = row
        lines.append(f"{pname:42s}" + "".join(f"{x:>24.1f}" for x in row))
    for j, pn in enumerate(problems):
        assert table["Thompson"][j] < table["greedy"][j], f"Thompson should beat greedy on '{pn}'"
    return "\n".join(lines)


# =============================================================================
# Milestone 4: the four phases of MCTS
# =============================================================================
def m4():
    g = mod.Nim()
    # --- uct_value, by hand (this is the number from the chapter's stepper)
    got = mod.uct_value(2.0, 3, 4, 1.0)
    want = 2 / 3 + math.sqrt(math.log(4) / 3)
    assert near(got, want), f"uct_value(wins=2, visits=3, parent_visits=4, c=1) should be 2/3 + sqrt(ln 4 / 3) = {want:.4f}, got {got}"
    assert near(mod.uct_value(0.0, 1, 4, 1.0), math.sqrt(math.log(4))), "an unwon child with one visit: 0 + sqrt(ln 4 / 1) = 1.1774"
    assert near(mod.uct_value(5.0, 10, 100, 0.0), 0.5), "c=0 leaves only the win rate"
    assert near(mod.uct_value(5.0, 10, 100, 2.0), 0.5 + 2 * math.sqrt(math.log(100) / 10)), "c scales the bonus"

    # --- select_child, on a hand-built node
    root = mod.Node(g, 10)
    root.untried = []
    root.visits = 4
    kids = []
    for move, visits, wins in ((1, 1, 0.0), (2, 3, 2.0)):
        k = mod.Node(g, 10 - move, parent=root, move=move)
        k.visits, k.wins = visits, wins
        kids.append(k)
    root.children = kids
    chosen = mod.select_child(root, 1.0)
    assert chosen.move == 2, (f"UCT values are {mod.uct_value(0, 1, 4, 1.0):.2f} for move 1 and {mod.uct_value(2, 3, 4, 1.0):.2f} for move 2; "
                              f"the larger wins, so move 2. Got move {chosen.move}.")
    assert mod.select_child(root, 3.0).move == 1, "with a large exploration constant the barely-visited child wins (move 1)"
    assert mod.select_child(root, 0.0).move == 2, "with c = 0 the win rate decides"
    kids[0].visits, kids[0].wins, kids[1].visits, kids[1].wins = 2, 1.0, 2, 1.0
    assert mod.select_child(root, 1.0).move == 1, "equal values: the first child in the list wins"

    # --- expand
    g_t = mod.TicTacToe()
    node = mod.Node(g_t, g_t.initial())
    assert sorted(node.untried) == list(range(9))
    rng = random.Random(1)
    seen = set()
    for _ in range(9):
        before = len(node.untried)
        child = mod.expand(node, g_t, rng)
        assert len(node.untried) == before - 1 and child.move not in node.untried, "expand must remove the move it used from node.untried"
        assert child in node.children and child.parent is node, "expand must attach the child to the node (children list and parent link)"
        assert child.state == g_t.next(node.state, child.move), "the child's state is the position after the move"
        assert child.visits == 0 and child.wins == 0.0 and not child.children and len(child.untried) == 8
        seen.add(child.move)
    assert seen == set(range(9)) and node.untried == [], "nine expansions must create nine distinct children"
    picks = {mod.expand(mod.Node(g_t, g_t.initial()), g_t, random.Random(s)).move for s in range(40)}
    assert len(picks) >= 5, f"expand should pick the untried move at random; over 40 seeds it only ever chose {sorted(picks)}"

    # --- backpropagate: a chain root -> a -> b -> c, result for the player who moved into c
    nodes = [mod.Node(g, 10)]
    for mv in (2, 1, 3):
        nodes.append(mod.Node(g, nodes[-1].state - mv, parent=nodes[-1], move=mv))
    mod.backpropagate(nodes[3], 1.0)
    assert [n.visits for n in nodes] == [1, 1, 1, 1], "every node on the path gets one visit"
    assert [n.wins for n in nodes] == [0.0, 1.0, 0.0, 1.0], (f"the result alternates up the path: c gets 1 (its mover won), b 0, a 1, root 0. "
                                                              f"Got wins {[n.wins for n in nodes]}")
    mod.backpropagate(nodes[2], 0.5)
    assert [n.wins for n in nodes] == [0.5, 1.5, 0.5, 1.0] and [n.visits for n in nodes] == [2, 2, 2, 1], \
        f"a draw (0.5) is 0.5 for both sides: expected wins [0.5, 1.5, 0.5, 1.0], visits [2, 2, 2, 1]; got {[n.wins for n in nodes]}, {[n.visits for n in nodes]}"
    mod.backpropagate(nodes[0], 1.0)
    assert nodes[0].visits == 3 and nodes[1].visits == 2, "backpropagating from the root only touches the root"

    # --- the rollout is given; check you can use it
    for s in seeds((1, 2, 3)):
        r = random.Random(s)
        assert mod.rollout(g, 0, r) == 1.0, "a rollout from a finished game just reports its value"
        assert all(mod.rollout(g, 3, random.Random(i)) in (0.0, 1.0) for i in range(5))
    return "uct_value, select_child, expand and backpropagate agree with the hand-worked tree of chapter 1"


# =============================================================================
# Milestone 5: the search loop, on Nim
# =============================================================================
def walk(node):
    yield node
    for ch in node.children:
        yield from walk(ch)


def m5():
    g = mod.Nim()
    # --- tiny games with a known answer
    root = mod.mcts(g, 1, 20, random.Random(0))
    assert root.visits == 20 and len(root.children) == 1 and root.children[0].move == 1, "from a pile of 1 the only move is to take 1"
    assert near(root.children[0].wins, root.children[0].visits), "taking the last stone wins every time: wins == visits"
    root = mod.mcts(g, 2, 300, random.Random(0))
    kids = {k.move: k for k in root.children}
    assert mod.best_move(root) == 2, f"from a pile of 2, taking both wins at once; visits were {[(m, k.visits) for m, k in kids.items()]}"
    assert kids[2].visits > 10 * kids[1].visits, "the winning move should get most of the visits"

    # --- bookkeeping invariants on a real search
    for s in seeds((1, 2)):
        rng = random.Random(s)
        calls = []

        def counting_rollout(game, state, r):
            calls.append(state)
            return mod.rollout(game, state, r)

        root = mod.mcts(g, 12, 500, rng, 1.0, counting_rollout)
        assert len(calls) == 500, f"seed {s}: exactly one rollout per iteration expected (and rollout_fn must be the one passed in); got {len(calls)} calls for 500 iterations"
        assert root.visits == 500, f"seed {s}: the root should have been visited once per iteration (500), got {root.visits}"
        assert sum(k.visits for k in root.children) == 500, f"seed {s}: every iteration passes through exactly one child of the root"
        for n in walk(root):
            assert 0 <= n.wins <= n.visits, f"seed {s}: a node's wins ({n.wins}) must lie between 0 and its visits ({n.visits})"
            if n is not root and n.children:
                assert n.visits == 1 + sum(k.visits for k in n.children), (
                    f"seed {s}: a node's visits should be 1 (the iteration that created it) plus its children's visits; "
                    f"pile {n.state}: {n.visits} against {1 + sum(k.visits for k in n.children)}")
        for n in walk(root):
            for ch in n.children:
                assert ch.parent is n and ch.state == n.state - ch.move
    # a constant rollout makes every node worth exactly half
    root = mod.mcts(g, 9, 200, random.Random(3), 1.0, lambda game, st, r: 0.5)
    assert all(near(n.wins, n.visits / 2) for n in walk(root)), "if every rollout returns 0.5 (a draw), every node must end with wins == visits / 2 (check the flip in backpropagate)"
    # determinism
    a = mod.mcts(g, 10, 300, random.Random(9))
    b = mod.mcts(g, 10, 300, random.Random(9))
    assert [(k.move, k.visits) for k in a.children] == [(k.move, k.visits) for k in b.children], "same seed, same tree"
    # a finished game does not crash the search
    done = mod.mcts(g, 0, 5, random.Random(0))
    assert done.visits == 5 and done.children == [], "searching from a finished game should just record the visits"

    # --- pile 10: take 2, leave 8
    root = mod.mcts(g, 10, 2000, random.Random(0))
    kids = {k.move: k for k in root.children}
    assert mod.best_move(root) == 2, f"from a pile of 10 the winning move is to take 2 (leave 8, a multiple of 4); visits {[(m, k.visits) for m, k in sorted(kids.items())]}"
    share = kids[2].visits / 2000
    assert share > 0.9, f"after 2000 iterations at least 90% of the visits should be on the winning move, got {share:.1%}"
    for m in (1, 3):
        assert kids[m].wins / kids[m].visits < kids[2].wins / kids[2].visits, "the winning move should have the best win rate"
    line = "  ".join(f"take {m}: {kids[m].visits:>4d} visits, win rate {kids[m].wins / kids[m].visits:.2f}" for m in sorted(kids))
    note = [f"pile 10, 2000 iterations: {line}"]

    # --- accuracy over many piles: does the most-visited move leave a multiple of 4?
    table = []
    for iters, floor in ((10, 0.0), (200, 0.85), (1000, 0.95)):
        ok = tot = 0
        for pile in range(1, 13):
            if pile % 4 == 0:
                continue
            for rep in range(3):
                r = mod.mcts(g, pile, iters, random.Random(1000 * pile + rep + (ONLY_SEED or 0)))
                ok += (pile - mod.best_move(r)) % 4 == 0
                tot += 1
        acc = ok / tot
        assert acc >= floor, f"piles 1 to 12 with {iters} iterations: expected at least {floor:.0%} of the chosen moves to be winning, got {acc:.0%} ({ok}/{tot})"
        table.append(f"{iters}: {acc:.0%}")
    note.append("share of winning moves on piles 1 to 12 by iteration budget: " + ", ".join(table))
    return "\n".join(note)


# =============================================================================
# Milestone 6: playing tic-tac-toe
# =============================================================================
def m6():
    T = mod.TicTacToe()
    # --- smart_rollout, by hand: X to move and X can win on the spot, so a player who just moved (O) is beaten every time
    state = "XX.OO...."
    assert T.to_move(state) == "X"
    vals = {mod.smart_rollout(T, state, random.Random(s)) for s in range(40)}
    assert vals == {0.0}, (f"X to move can win at cell 2 at once. smart_rollout returns the reward for the player who moved INTO the state (O), "
                           f"so it must be 0.0 every time; got {sorted(vals)}")
    vals = {mod.smart_rollout(T, "XX.OO.O..", random.Random(s)) for s in range(40)}
    assert vals == {0.0}, f"from 'XX.OO.O..' X (to move) wins at cell 2 immediately; expected 0.0 for O every time, got {sorted(vals)}"
    assert mod.smart_rollout(T, "XXXOO....", random.Random(0)) == 1.0, "a finished game: the value of the final state for the player who moved into it (X completed the line: 1.0)"
    full_draw = "XOXXOOOXX"
    assert mod.smart_rollout(T, full_draw, random.Random(0)) == 0.5, "a drawn board is worth 0.5"
    # a perspective sanity check: results are always in {0, 0.5, 1}
    for s in range(30):
        assert mod.smart_rollout(T, T.initial(), random.Random(s)) in (0.0, 0.5, 1.0)
    # smart rollouts make X's opening look better than O's: both players are sensible, so draws dominate
    draws = sum(mod.smart_rollout(T, T.initial(), random.Random(s)) == 0.5 for s in range(300))
    plain = sum(mod.rollout(T, T.initial(), random.Random(s)) == 0.5 for s in range(300))
    assert draws > plain + 30, (f"playing sensibly (take a win, avoid an instant loss) should draw far more often than random play: "
                                f"{draws} draws of 300 against {plain} for random playouts")

    # --- mcts_player: tactics at a small budget
    budget = 30
    cases = [("XX..O....", 2), ("X.X.O....", 1), (".XX.O....", 0), ("OO.X...X.", 2)]   # (position, the only non-losing move)
    rates = []
    for st, mv in cases:
        wins_smart = wins_plain = 0
        for s in seeds(range(60)):
            wins_smart += mod.mcts_player(T, budget, 1.0, mod.smart_rollout)(st, random.Random(s)) == mv
            wins_plain += mod.mcts_player(T, budget, 1.0, mod.rollout)(st, random.Random(s)) == mv
        n = len(seeds(range(60)))
        rates.append((wins_plain / n, wins_smart / n))
        if n < 20:                      # replaying a single seed: the rates below only make sense in aggregate
            continue
        assert wins_smart / n >= 0.8, (f"position\n{T.render(st)}\n{T.to_move(st)} to move must block at cell {mv}; with {budget} iterations "
                                       f"and smart rollouts you found it in {wins_smart}/{n} games (need 80%)")
        assert wins_smart > wins_plain, f"smart rollouts should find the block more often than random ones ({wins_smart} against {wins_plain})"

    # --- full games
    def outcomes(player, opponent, games, seed0):
        res = {"win": 0, "draw": 0, "loss": 0}
        for i in range(games):
            rng = random.Random(seed0 + i)
            r = mod.play_game(T, player, opponent, rng)
            res["win" if r == "first" else "draw" if r == "draw" else "loss"] += 1
            rng = random.Random(seed0 + i)
            r = mod.play_game(T, opponent, player, rng)
            res["win" if r == "second" else "draw" if r == "draw" else "loss"] += 1
        return res

    n = 20
    vs_random = outcomes(mod.mcts_player(T, 600), mod.random_player(T), n, 100 + (ONLY_SEED or 0))
    assert vs_random["loss"] == 0, f"MCTS (600 iterations) should never lose to a random player; results over {2 * n} games: {vs_random}"
    assert vs_random["win"] >= 2 * n * 0.8, f"MCTS (600 iterations) should win at least 80% of {2 * n} games against random play; results: {vs_random}"
    vs_perfect = outcomes(mod.mcts_player(T, 1500), mod.minimax_player(T), n, 500 + (ONLY_SEED or 0))
    assert vs_perfect["win"] == 0, "nobody beats a perfect tic-tac-toe player"
    assert vs_perfect["loss"] <= 1, f"MCTS (1500 iterations) against a perfect player should draw nearly every game; results over {2 * n} games: {vs_perfect}"
    low = outcomes(mod.mcts_player(T, 30), mod.minimax_player(T), n, 900)
    assert low["loss"] > vs_perfect["loss"], "with only 30 iterations MCTS should be easier to beat than with 1500 (more search, fewer mistakes)"
    note = [f"must-block positions at {budget} iterations (random rollouts vs smart): " +
            ", ".join(f"{a:.0%}/{b:.0%}" for a, b in rates),
            f"600 iterations vs random player, {2 * n} games: {vs_random['win']} wins, {vs_random['draw']} draws, {vs_random['loss']} losses",
            f"1500 iterations vs perfect player, {2 * n} games: {vs_perfect['draw']} draws, {vs_perfect['loss']} losses",
            f"30 iterations vs perfect player, {2 * n} games: {low['draw']} draws, {low['loss']} losses"]
    return "\n".join(note)


MILESTONES = [
    (1, "Milestone 1: regret, greedy and epsilon-greedy", m1),
    (2, "Milestone 2: UCB1, optimism under uncertainty", m2),
    (3, "Milestone 3: Thompson sampling", m3),
    (4, "Milestone 4: the four phases of MCTS", m4),
    (5, "Milestone 5: the search loop, tested on Nim", m5),
    (6, "Milestone 6: playing tic-tac-toe", m6),
]

if __name__ == "__main__":
    t0 = time.time()
    print(f"Lab 1 checks against {target}.py\n")
    for n, name, fn in MILESTONES:
        check(n, name, fn)
    print(f"\n{sum(results)}/{len(results)} milestones passing  ({time.time() - t0:.1f} s)")
    sys.exit(0 if all(results) else 1)
