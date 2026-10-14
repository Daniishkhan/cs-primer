"""Lab 1 (reference solution): bandits, then Monte Carlo tree search.

Everything is pure Python and seeded. Part A (milestones 1 to 3) is the bandit problem of
chapter 1: how to split a budget of pulls between trying arms and repeating what works.
Part B (milestones 4 to 6) grows the same idea into a tree: UCB1 chooses which move to
look at next, random playouts score it, and the most-visited move is played.

Conventions used throughout (they match chapter 1):

    arm i has a hidden win rate mu_i; counts[i] = pulls so far, totals[i] = total reward so far
    t          the 1-based number of the pull being chosen (the first pull is t = 1)
    state      a hashable game position; the player to move is implied by the state
    wins       in a tree node: reward for the player who moved INTO that node (1 win, 0.5 draw, 0 loss)
"""
import math
import random
from functools import partial


# =============================================================================
# GIVEN, part A: the bandit and the experiment loop
# =============================================================================
def run_bandit(select, probs, steps, seed):
    """Play `steps` pulls on a Bernoulli bandit with win rates `probs`.

    `select(counts, totals, t, rng)` returns the arm to pull. Rewards come from one seeded
    generator and the policy's own randomness from another, so a policy cannot change the
    rewards an arm would have paid. Returns (counts, totals).
    """
    reward_rng = random.Random(seed)
    policy_rng = random.Random(seed + 1_000_003)
    k = len(probs)
    counts, totals = [0] * k, [0.0] * k
    for t in range(1, steps + 1):
        arm = select(counts, totals, t, policy_rng)
        reward = 1.0 if reward_rng.random() < probs[arm] else 0.0
        counts[arm] += 1
        totals[arm] += reward
    return counts, totals


# =============================================================================
# Milestone 1: regret, greedy and epsilon-greedy
# =============================================================================
def pseudo_regret(probs, counts):
    """R = sum_i counts[i] * (mu_star - mu_i): what the pulls cost against always playing the best arm."""
    best = max(probs)
    return sum(n * (best - p) for n, p in zip(counts, probs))


def greedy(counts, totals, t, rng):
    """Try every arm once (lowest index first), then always pull the arm with the best average.
    Ties go to the lowest index."""
    for i, n in enumerate(counts):
        if n == 0:
            return i
    avg = [s / n for n, s in zip(counts, totals)]
    return max(range(len(avg)), key=lambda i: (avg[i], -i))


def epsilon_greedy(counts, totals, t, rng, eps=0.1):
    """With probability eps pull a uniformly random arm; otherwise act greedily (untried arms first)."""
    if rng.random() < eps:
        return rng.randrange(len(counts))
    return greedy(counts, totals, t, rng)


def mean_regret(select, probs, steps, seeds):
    """Average pseudo-regret of a policy over the given seeds."""
    total = 0.0
    for seed in seeds:
        counts, _ = run_bandit(select, probs, steps, seed)
        total += pseudo_regret(probs, counts)
    return total / len(seeds)


# =============================================================================
# Milestone 2: UCB1
# =============================================================================
def ucb_scores(counts, totals, t, c):
    """UCB_i = mean_i + c * sqrt(ln t / n_i) for every arm. An untried arm has an infinite bound."""
    out = []
    for n, s in zip(counts, totals):
        if n == 0:
            out.append(math.inf)
        else:
            out.append(s / n + c * math.sqrt(math.log(t) / n))
    return out


def ucb1(counts, totals, t, rng, c=1.0):
    """Pull the arm with the highest upper confidence bound (ties to the lowest index)."""
    scores = ucb_scores(counts, totals, t, c)
    return max(range(len(scores)), key=lambda i: (scores[i], -i))


# =============================================================================
# Milestone 3: Thompson sampling
# =============================================================================
def thompson(counts, totals, t, rng):
    """Draw one sample from Beta(1 + wins, 1 + losses) for each arm and pull the arm with the largest draw.
    Draw the arms in index order, one rng.betavariate call each."""
    best, best_draw = 0, -1.0
    for i, (n, s) in enumerate(zip(counts, totals)):
        draw = rng.betavariate(1.0 + s, 1.0 + (n - s))
        if draw > best_draw:
            best, best_draw = i, draw
    return best


# =============================================================================
# GIVEN, part B: games and the node of the search tree
# =============================================================================
class Nim:
    """A pile of stones; players alternate taking 1, 2 or 3; taking the last stone wins.
    A state is just the pile size (an int)."""
    name = "nim"

    def __init__(self, takes=(1, 2, 3)):
        self.takes = takes

    def initial(self, pile=10):
        return pile

    def legal(self, state):
        return [m for m in self.takes if m <= state]

    def next(self, state, move):
        return state - move

    def is_terminal(self, state):
        return state == 0

    def terminal_value(self, state):
        """Reward for the player who moved INTO this terminal state: they took the last stone, so 1."""
        return 1.0


class TicTacToe:
    """3 by 3 noughts and crosses. A state is a 9-character string of 'X', 'O' and '.'; X moves first.
    A move is a cell index 0 to 8."""
    name = "tictactoe"
    LINES = [(0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6), (1, 4, 7), (2, 5, 8), (0, 4, 8), (2, 4, 6)]

    def initial(self):
        return "." * 9

    def to_move(self, state):
        return "X" if state.count("X") == state.count("O") else "O"

    def legal(self, state):
        return [] if self._winner(state) else [i for i, ch in enumerate(state) if ch == "."]

    def next(self, state, move):
        mark = self.to_move(state)
        return state[:move] + mark + state[move + 1:]

    def _winner(self, state):
        for a, b, c in self.LINES:
            if state[a] != "." and state[a] == state[b] == state[c]:
                return state[a]
        return None

    def is_terminal(self, state):
        return self._winner(state) is not None or "." not in state

    def terminal_value(self, state):
        """Reward for the player who moved INTO this terminal state: 1 if their move completed a line, else 0.5 (draw)."""
        return 1.0 if self._winner(state) else 0.5

    def render(self, state):
        return "\n".join(" ".join(state[r * 3:r * 3 + 3]) for r in range(3))


class Node:
    """One position in the search tree.

    wins    summed reward for the player who moved INTO this node (so a node is judged from the
            point of view of its parent, which is the player choosing among siblings)
    visits  how many iterations have passed through this node
    untried moves not yet expanded into children
    """

    def __init__(self, game, state, parent=None, move=None):
        self.state, self.parent, self.move = state, parent, move
        self.children = []
        self.untried = list(game.legal(state))
        self.visits = 0
        self.wins = 0.0


def rollout(game, state, rng):
    """Play uniformly random moves to the end. Returns the reward for the player who moved INTO `state`."""
    flipped = False                       # have the roles swapped relative to the player who moved into `state`?
    while not game.is_terminal(state):
        state = game.next(state, rng.choice(game.legal(state)))
        flipped = not flipped
    value = game.terminal_value(state)    # for whoever moved into the final state
    return 1.0 - value if flipped else value


# =============================================================================
# Milestone 4: the four phases of MCTS
# =============================================================================
def uct_value(wins, visits, parent_visits, c):
    """wins/visits + c * sqrt(ln(parent_visits) / visits)."""
    return wins / visits + c * math.sqrt(math.log(parent_visits) / visits)


def select_child(node, c):
    """The child with the highest UCT value (ties to the first in the list). All children must have visits >= 1."""
    best, best_value = None, -math.inf
    for child in node.children:
        v = uct_value(child.wins, child.visits, node.visits, c)
        if v > best_value:
            best, best_value = child, v
    return best


def expand(node, game, rng):
    """Remove one random untried move from the node, add the child for it, and return the child."""
    move = node.untried.pop(rng.randrange(len(node.untried)))
    child = Node(game, game.next(node.state, move), parent=node, move=move)
    node.children.append(child)
    return child


def backpropagate(node, result):
    """`result` is the reward for the player who moved into `node`. Add a visit and the reward to the node and
    every ancestor, flipping the result (1 - result) at every level."""
    while node is not None:
        node.visits += 1
        node.wins += result
        result = 1.0 - result
        node = node.parent


# =============================================================================
# Milestone 5: the search loop and the move choice
# =============================================================================
def mcts(game, state, iters, rng, c=1.0, rollout_fn=rollout):
    """Run `iters` iterations of selection, expansion, simulation and backpropagation from `state`.
    Returns the root node."""
    root = Node(game, state)
    for _ in range(iters):
        node = root
        # 1. selection: descend while the node is fully expanded and has children
        while not node.untried and node.children:
            node = select_child(node, c)
        # 2. expansion: add one new child (a terminal node has nothing to expand)
        if node.untried:
            node = expand(node, game, rng)
        # 3. simulation: score the new position by playing it out
        result = rollout_fn(game, node.state, rng)
        # 4. backpropagation
        backpropagate(node, result)
    return root


def best_move(root):
    """The move of the most-visited child (not the highest win rate). Ties go to the first child."""
    best = max(root.children, key=lambda ch: ch.visits)
    return best.move


# =============================================================================
# GIVEN: a perfect opponent and a way to play games
# =============================================================================
_MINIMAX_CACHE = {}


def minimax_value(game, state):
    """Game value for the player TO MOVE at `state`: 1 win, 0.5 draw, 0 loss, with perfect play."""
    key = (game.name, state)
    if key not in _MINIMAX_CACHE:
        if game.is_terminal(state):
            _MINIMAX_CACHE[key] = 1.0 - game.terminal_value(state)      # the player to move did not make the last move
        else:
            _MINIMAX_CACHE[key] = max(1.0 - minimax_value(game, game.next(state, m)) for m in game.legal(state))
    return _MINIMAX_CACHE[key]


def minimax_player(game):
    """A perfect player: picks uniformly among the moves that keep the best achievable value."""
    def player(state, rng):
        scored = [(1.0 - minimax_value(game, game.next(state, m)), m) for m in game.legal(state)]
        top = max(v for v, _ in scored)
        return rng.choice([m for v, m in scored if v == top])
    return player


def random_player(game):
    def player(state, rng):
        return rng.choice(game.legal(state))
    return player


def play_game(game, first, second, rng, start=None):
    """Play one game; `first` moves first. Returns 'first', 'second' or 'draw'."""
    state = game.initial() if start is None else start
    players = [first, second]
    turn = 0
    while not game.is_terminal(state):
        state = game.next(state, players[turn](state, rng))
        turn = 1 - turn
    if game.terminal_value(state) < 1.0:
        return "draw"
    return "second" if turn == 0 else "first"      # the player who just moved is the winner (turn already flipped)


# =============================================================================
# Milestone 6: playing tic-tac-toe
# =============================================================================
def smart_rollout(game, state, rng):
    """A rollout that is random except for two cheap rules, applied at every ply:
    1. if some legal move wins the game on the spot, play it;
    2. otherwise avoid any move that lets the opponent win on the spot, if such a safe move exists.
    Returns the reward for the player who moved INTO `state`, exactly like `rollout`."""
    flipped = False
    while not game.is_terminal(state):
        moves = game.legal(state)
        choice = None
        safe = []
        for m in moves:
            nxt = game.next(state, m)
            if game.is_terminal(nxt) and game.terminal_value(nxt) == 1.0:
                choice = m
                break
            if not any(game.is_terminal(game.next(nxt, r)) and game.terminal_value(game.next(nxt, r)) == 1.0
                       for r in game.legal(nxt)):
                safe.append(m)
        if choice is None:
            choice = rng.choice(safe or moves)
        state = game.next(state, choice)
        flipped = not flipped
    value = game.terminal_value(state)
    return 1.0 - value if flipped else value


def mcts_player(game, iters, c=1.0, rollout_fn=rollout):
    """A player function `player(state, rng) -> move` that runs MCTS for `iters` iterations and plays the most-visited move."""
    def player(state, rng):
        return best_move(mcts(game, state, iters, rng, c, rollout_fn))
    return player
