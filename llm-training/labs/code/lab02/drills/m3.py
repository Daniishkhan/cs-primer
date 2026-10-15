# Drill: A3 Lab 2, milestone 3 of 5: REINFORCE on a gridworld
# Everything else in this file is already written. Fill in:
#     returns_to_go, run_episode, reinforce_grid_gradient, update_values, train_reinforce_grid
# Check it with: python3 check.py 3

"""Lab 2: Policy gradients and PPO, from a softmax bandit to a gridworld.

Chapters 6 to 8 derived REINFORCE, baselines, the PPO clip and the KL leash. This lab
implements each on problems small enough to run in seconds and to check by hand:

    softmax policy --> REINFORCE with a baseline (bandit) --> REINFORCE on a gridworld
        --> PPO's clipped objective (reusing one batch) --> PPO with a KL penalty to a reference

Standard-library Python only; every random draw comes from a seeded random.Random.

Notation follows chapters 6 to 8: a policy pi_theta(a | s) is a softmax over logits z[s][a];
a trajectory tau has states s_t, actions a_t and rewards r_t; G_t is the return-to-go;
A is the advantage; r(theta) = pi_theta(a|s) / pi_old(a|s) is the probability ratio; eps is
the clip range and beta the KL coefficient.

What is GIVEN: the bandit, the gridworld, the reference policy and the KL / evaluation helpers.
What YOU write is marked TODO:

    1  softmax, log_softmax, sample_action, grad_log_prob
    2  advantages, policy_gradient, train_bandit
    3  returns_to_go, run_episode, reinforce_grid_gradient, update_values, train_reinforce_grid
    4  ratio, clipped_surrogate, is_clipped, ppo_gradient, train_bandit_ppo
    5  kl_k3, shaped_rewards, train_ppo_grid

`python3 check.py` runs the milestones; the lab page explains each one.
"""
import math
import random

# =============================================================================
# GIVEN: a bandit, a gridworld and some helpers
# =============================================================================
ACTIONS = ("up", "down", "left", "right")
N_ACTIONS = 4


class Bandit:
    """K arms; pulling arm a pays means[a] plus Gaussian noise of standard deviation sigma."""

    def __init__(self, means, sigma):
        self.means, self.sigma = list(means), sigma

    @property
    def k(self):
        return len(self.means)

    def pull(self, a, rng):
        return self.means[a] + self.sigma * rng.gauss(0.0, 1.0)


CH7_BANDIT = Bandit([0.2, 0.4, 0.6, 0.8], 0.3)                          # chapter 7's variance experiment
CH8_BANDIT = Bandit([0.0, 0.2, 0.4, 0.6, 1.0, 0.1], 0.5)                # chapter 8's six-armed clip experiment (arm 4 is best)


class GridWorld:
    """A 4 x 4 gridworld. State s = 4 * row + col. Deterministic moves; bumping into the
    wall or the edge leaves you where you are.

        S . . .         S start (0,0)    G goal (3,3): reward +1, episode ends
        . # . P         # wall (1,1)     P pit: reward -1, episode ends
        . . . .         every other step costs -0.01
        P . . G         an episode is cut off after max_steps steps (reward 0 for the cut)
    """
    ROWS = COLS = 4
    WALL = 5                         # (1, 1)
    PITS = (7, 12)                   # (1, 3) and (3, 0)
    GOAL = 15
    START = 0
    STEP_COST = -0.01
    n_actions = N_ACTIONS

    def __init__(self, max_steps=30):
        self.max_steps = max_steps
        self.n_states = self.ROWS * self.COLS

    def is_terminal(self, s):
        return s == self.GOAL or s in self.PITS

    def free_states(self):
        """States where the agent can stand and must still choose: not wall, not terminal."""
        return [s for s in range(self.n_states) if s != self.WALL and not self.is_terminal(s)]

    def reset(self):
        return self.START

    def step(self, s, a):
        """(next_state, reward, done) for taking action a (0 up, 1 down, 2 left, 3 right) in state s."""
        row, col = divmod(s, self.COLS)
        dr, dc = ((-1, 0), (1, 0), (0, -1), (0, 1))[a]
        nr, nc = row + dr, col + dc
        if not (0 <= nr < self.ROWS and 0 <= nc < self.COLS) or nr * self.COLS + nc == self.WALL:
            nr, nc = row, col
        s2 = nr * self.COLS + nc
        if s2 == self.GOAL:
            return s2, 1.0, True
        if s2 in self.PITS:
            return s2, -1.0, True
        return s2, self.STEP_COST, False


def zeros_table(env):
    """A tabular policy with all logits 0: uniform over the four actions in every state."""
    return [[0.0] * N_ACTIONS for _ in range(env.n_states)]


def reference_table(env):
    """The 'SFT model' of the KL experiments: mildly prefers moving right and down (logit +0.5)."""
    table = zeros_table(env)
    for s in range(env.n_states):
        table[s][1] = table[s][3] = 0.5
    return table


def true_gradient(logits, means):
    """Exact gradient of the expected reward sum_a pi(a) mu(a) with respect to the logits."""
    p = [math.exp(z - max(logits)) for z in logits]
    total = sum(p)
    p = [x / total for x in p]
    ev = sum(pa * m for pa, m in zip(p, means))
    return [pa * (m - ev) for pa, m in zip(p, means)]


def kl_divergence(p, q):
    """Exact KL(p || q) = sum_a p(a) log(p(a) / q(a)) for two probability vectors."""
    return sum(pa * math.log(pa / qa) for pa, qa in zip(p, q) if pa > 0)


def mean_kl(env, table, ref):
    """Average over the free states of KL(pi(.|s) || ref(.|s)), the drift of a whole policy."""
    states = env.free_states()
    return sum(kl_divergence(softmax(table[s]), softmax(ref[s])) for s in states) / len(states)


def evaluate(env, table, episodes=200, seed=12345):
    """(mean undiscounted return, success rate) of the SAMPLING policy over `episodes` episodes."""
    rng = random.Random(seed)
    total, wins = 0.0, 0
    for _ in range(episodes):
        _, _, rewards = run_episode(env, table, rng)
        total += sum(rewards)
        wins += rewards[-1] == 1.0
    return total / episodes, wins / episodes


# =============================================================================
# Milestone 1: the softmax policy
# =============================================================================
def softmax(logits):
    """Probabilities proportional to exp(logit). Subtract the maximum first so that
    logits like 1000 do not overflow."""
    m = max(logits)
    e = [math.exp(z - m) for z in logits]
    total = sum(e)
    return [x / total for x in e]


def log_softmax(logits):
    """log of softmax(logits), computed stably as z - max - log(sum(exp(z - max)))."""
    m = max(logits)
    lse = m + math.log(sum(math.exp(z - m) for z in logits))
    return [z - lse for z in logits]


def sample_action(probs, rng):
    """Draw an index with the given probabilities using EXACTLY ONE call to rng.random():
    walk along the cumulative sum and return the first index whose running total is
    greater than u. If rounding leaves u above the last total, return the last index."""
    u = rng.random()
    total = 0.0
    for a, p in enumerate(probs):
        total += p
        if u < total:
            return a
    return len(probs) - 1


def grad_log_prob(logits, a):
    """Gradient of log pi(a) with respect to the logits: onehot(a) - softmax(logits)."""
    p = softmax(logits)
    return [(1.0 if k == a else 0.0) - pk for k, pk in enumerate(p)]


# =============================================================================
# Milestone 2: REINFORCE with a baseline on a bandit
# =============================================================================
def advantages(rewards, baseline="loo"):
    """Turn rewards into advantages A_i = R_i - b_i.

        "none"  b_i = 0
        "mean"  b_i = the mean of ALL the rewards in the batch (includes sample i)
        "loo"   b_i = the mean of the OTHER rewards (leave-one-out); needs at least 2 rewards,
                else ValueError
    Any other name raises ValueError.
    """
    n = len(rewards)
    if baseline == "none":
        return list(rewards)
    if baseline == "mean":
        m = sum(rewards) / n
        return [r - m for r in rewards]
    if baseline == "loo":
        if n < 2:
            raise ValueError("leave-one-out needs at least two samples")
        total = sum(rewards)
        return [r - (total - r) / (n - 1) for r in rewards]
    raise ValueError(f"unknown baseline {baseline!r}")


def policy_gradient(logits, actions, advs):
    """The REINFORCE estimate: the mean over samples of A_i * grad log pi(a_i).
    Returns a list the length of `logits`."""
    g = [0.0] * len(logits)
    for a, adv in zip(actions, advs):
        for k, d in enumerate(grad_log_prob(logits, a)):
            g[k] += adv * d
    return [x / len(actions) for x in g]


def train_bandit(bandit, steps=300, batch=8, lr=0.5, baseline="loo", seed=0):
    """Train a softmax policy on a bandit and return its logits.

    Start from zero logits. Each step: sample `batch` actions from the current policy, pull
    each (action first, then its reward, for every sample in turn), compute advantages with
    `baseline`, and ascend: logits += lr * policy_gradient(...).
    """
    rng = random.Random(seed)
    logits = [0.0] * bandit.k
    for _ in range(steps):
        probs = softmax(logits)
        actions, rewards = [], []
        for _ in range(batch):
            a = sample_action(probs, rng)
            actions.append(a)
            rewards.append(bandit.pull(a, rng))
        g = policy_gradient(logits, actions, advantages(rewards, baseline))
        logits = [z + lr * gi for z, gi in zip(logits, g)]
    return logits


# =============================================================================
# Milestone 3: REINFORCE on a gridworld
# =============================================================================
def returns_to_go(rewards, gamma):
    """G_t = r_t + gamma * G_{t+1}, for every t (the last return is the last reward)."""
    raise NotImplementedError("TODO milestone 3: returns_to_go")


def run_episode(env, table, rng):
    """Play one episode with the sampling policy softmax(table[s]).

    Returns (states, actions, rewards), three lists of equal length: states[t] is the state
    BEFORE action t. Start at env.reset(); at each step sample an action with sample_action;
    stop when env.step says done or after env.max_steps steps.
    """
    raise NotImplementedError("TODO milestone 3: run_episode")


def reinforce_grid_gradient(table, episodes, V, gamma):
    """The REINFORCE gradient for a tabular softmax policy, as a table shaped like `table`.

    For every step t of every episode add (G_t - V[s_t]) * grad log pi(a_t | s_t) to row s_t;
    finally divide everything by the NUMBER OF EPISODES. G_t is the discounted return-to-go
    and V[s] is the state-value baseline. (The gamma^t factor of the exact derivation is
    left out, as nearly every implementation does.)
    """
    raise NotImplementedError("TODO milestone 3: reinforce_grid_gradient")


def update_values(V, episodes, gamma, alpha):
    """Move each visited state's value towards the returns observed from it:
    V[s] += alpha * (G_t - V[s]), step by step in the order they happened. Changes V in place."""
    raise NotImplementedError("TODO milestone 3: update_values")


def train_reinforce_grid(env, iterations=150, episodes=16, lr=0.5, gamma=0.99, v_lr=0.2, baseline=True, seed=0):
    """Train a tabular softmax policy with REINFORCE and return (table, V, history).

    Each iteration: play `episodes` episodes with the current table, take one gradient step
    table[s][k] += lr * grad[s][k] (the baseline V is all zeros when `baseline` is False),
    THEN update V from the same episodes. history[i] is the mean undiscounted return of
    iteration i's episodes.
    """
    raise NotImplementedError("TODO milestone 3: train_reinforce_grid")


# =============================================================================
# Milestone 4: PPO's clipped objective
# =============================================================================
def ratio(logp_new, logp_old):
    """The probability ratio pi_new(a|s) / pi_old(a|s), from log-probabilities."""
    return math.exp(logp_new - logp_old)


def clipped_surrogate(r, adv, eps=0.2):
    """min(r * A, clip(r, 1 - eps, 1 + eps) * A): the PPO objective for one sample."""
    return min(r * adv, min(max(r, 1.0 - eps), 1.0 + eps) * adv)


def is_clipped(r, adv, eps=0.2):
    """True if the sample passes NO gradient: the clipped term is the smaller one.
    A sample at exactly the boundary (r == 1 + eps with A > 0) still passes gradient."""
    return r * adv > min(max(r, 1.0 - eps), 1.0 + eps) * adv


def ppo_gradient(logits, old_logits, actions, advs, eps=0.2):
    """Gradient, with respect to `logits`, of the MEAN clipped surrogate over the samples.

    For sample i the ratio is r_i = pi_logits(a_i) / pi_old_logits(a_i). A clipped sample
    contributes nothing; any other contributes A_i * r_i * grad log pi(a_i), because
    grad r = r * grad log pi. Divide by the number of samples.
    """
    p, p_old = softmax(logits), softmax(old_logits)
    g = [0.0] * len(logits)
    for a, adv in zip(actions, advs):
        r = p[a] / p_old[a]
        if is_clipped(r, adv, eps):
            continue
        for k, d in enumerate(grad_log_prob(logits, a)):
            g[k] += adv * r * d
    return [x / len(actions) for x in g]


def train_bandit_ppo(bandit, iters=30, batch=8, epochs=10, lr=1.0, eps=0.2, clip=True, seed=0):
    """Train a softmax policy on a bandit with PPO-style batch reuse; return the logits.

    Each iteration: freeze old = a copy of the logits; sample `batch` actions and rewards from
    it; normalise the rewards to advantages (R - mean) / (std + 1e-8) with the population
    standard deviation; then take `epochs` gradient steps on that SAME batch:
    logits += lr * ppo_gradient(...). With clip=False the ratio is used but never clipped
    (every sample passes gradient).
    """
    rng = random.Random(seed)
    logits = [0.0] * bandit.k
    for _ in range(iters):
        old = list(logits)
        probs = softmax(old)
        actions, rewards = [], []
        for _ in range(batch):
            a = sample_action(probs, rng)
            actions.append(a)
            rewards.append(bandit.pull(a, rng))
        mean = sum(rewards) / batch
        std = math.sqrt(sum((r - mean) ** 2 for r in rewards) / batch)
        advs = [(r - mean) / (std + 1e-8) for r in rewards]
        for _ in range(epochs):
            g = ppo_gradient(logits, old, actions, advs, eps if clip else float("inf"))
            logits = [z + lr * gi for z, gi in zip(logits, g)]
    return logits


# =============================================================================
# Milestone 5: the KL leash
# =============================================================================
def kl_k3(logp, logp_ref):
    """Schulman's k3 estimator of KL(pi || ref) from ONE sample drawn from pi:
    (rho - 1) - log(rho) with rho = pi_ref(a) / pi(a). Always >= 0."""
    log_rho = logp_ref - logp
    return math.exp(log_rho) - 1.0 - log_rho


def shaped_rewards(rewards, logps, logps_ref, beta):
    """Per-step rewards with the KL penalty of chapter 8: r_t - beta * (log pi(a_t|s_t) - log ref(a_t|s_t))."""
    return [r - beta * (lp - lr_) for r, lp, lr_ in zip(rewards, logps, logps_ref)]


def train_ppo_grid(env, ref, beta=0.0, iterations=100, episodes=16, epochs=4, lr=1.0, eps=0.2,
                   gamma=0.99, v_lr=0.2, seed=0):
    """PPO with a KL penalty to the reference table `ref` on the gridworld. Returns (table, V).

    Start from a COPY of `ref` (the tuned model starts as the reference). Each iteration:
      1. old = a copy of the table; play `episodes` episodes with `old`.
      2. For every step, log pi_old(a|s) and log ref(a|s); shape the rewards with beta
         (shaped_rewards), take returns-to-go with gamma, and advantage = G_t - V[s_t].
      3. Group the steps by state. For each of `epochs` passes, for every state that appears:
         table[s][k] += lr * (n_s / N) * ppo_gradient(table[s], old[s], actions_s, advs_s, eps)[k],
         where n_s is the number of steps in that state and N the total number of steps.
      4. Update V towards the SHAPED returns (update_values-style, with v_lr).
    """
    rng = random.Random(seed)
    table = [row[:] for row in ref]
    V = [0.0] * env.n_states
    for _ in range(iterations):
        old = [row[:] for row in table]
        eps_data, groups, total = [], {}, 0
        for _ in range(episodes):
            states, actions, rewards = run_episode(env, old, rng)
            logps = [log_softmax(old[s])[a] for s, a in zip(states, actions)]
            refs = [log_softmax(ref[s])[a] for s, a in zip(states, actions)]
            shaped = shaped_rewards(rewards, logps, refs, beta)
            eps_data.append((states, actions, shaped))
            for s, a, g in zip(states, actions, returns_to_go(shaped, gamma)):
                groups.setdefault(s, ([], []))
                groups[s][0].append(a)
                groups[s][1].append(g - V[s])
                total += 1
        for _ in range(epochs):
            for s, (acts, advs) in groups.items():
                g = ppo_gradient(table[s], old[s], acts, advs, eps)
                w = lr * len(acts) / total
                for k in range(N_ACTIONS):
                    table[s][k] += w * g[k]
        update_values(V, eps_data, gamma, v_lr)
    return table, V
