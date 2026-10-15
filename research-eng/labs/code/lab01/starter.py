"""Lab 1: a keep-or-revert research loop (starter).

Pure standard library, no clock, no network. Every random number comes
from a seeded random.Random, so every number repeats exactly.

The inner task is a toy "training run": fit a polynomial to noisy data
with minibatch SGD. A config says how (lr, degree, l2, batch). One run
gives two scores for the same weights (mean squared error, lower is
better):

    proxy    40 SGD steps, scored on a 16-point validation slice
    heldout  300 SGD steps, scored on 400 fresh points

The loop decides on the proxy only. The held-out score is logged, never
used to decide, and the gap between the two is the extension.

GIVEN: the task, the t table, dump_line, experiment_seeds, the two
proposers, DuplicateKey. YOU write what is marked TODO:

    1  config_hash, RunStore.load/append/get, evaluate   the run store
    2  mean, sample_sd, noise_floor                      the noise floor
    3  paired_test, keep_or_revert                       paired decisions
    4  run_experiment, research_loop                     both scores logged
    5  cumulative, ols_slope, detect_overfit, text_chart the gap's trend
    6  first_difference, replay                          byte-identical replay

Conventions: scores are errors, so a GAIN is old minus new (positive is
better). A run is identified by run_key(config, seed).
"""
import hashlib
import json
import math
import os
import random

# ── 0. Given: the task ──────────────────────────────────────────────
PROXY_STEPS = 40        # SGD steps in the cheap run the loop sees
HELD_STEPS = 300        # SGD steps in the long run the loop never sees
BASELINE = {"lr": 0.02, "degree": 3, "l2": 0.001, "batch": 16}
BASELINE_SEEDS = tuple(range(8))   # K seeds for the noise floor

# Two-sided 95% critical values of Student's t, by degrees of freedom.
T_CRIT = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447,
          7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228, 11: 2.201, 12: 2.179,
          13: 2.160, 14: 2.145, 15: 2.131, 16: 2.120, 17: 2.110,
          18: 2.101, 19: 2.093, 20: 2.086, 25: 2.060, 30: 2.042}


def t_critical(df):
    """Smallest tabulated df at or below `df`, else 1.96 (large df)."""
    if df > 30:
        return 1.96
    while df not in T_CRIT:
        df += 1
    return T_CRIT[df]


def _make_data(seed, n, noise=0.3):
    rng = random.Random(seed)
    pts = []
    for _ in range(n):
        x = rng.uniform(-1, 1)
        y = math.sin(2.5 * x) + 0.5 * x * x + rng.gauss(0, noise)
        pts.append((x, y))
    return pts


TRAIN = _make_data(11, 48)
VAL_PROXY = _make_data(12, 16)
VAL_HELD = _make_data(13, 400)
TRAIN_CALLS = 0         # how many real training runs happened


def _features(x, degree):
    return [x ** k for k in range(degree + 1)]


def _sgd(config, seed, steps):
    rng = random.Random(seed)
    d = config["degree"]
    w = [rng.gauss(0, 0.1) for _ in range(d + 1)]
    for _ in range(steps):
        batch = [TRAIN[rng.randrange(len(TRAIN))]
                 for _ in range(config["batch"])]
        grad = [2 * config["l2"] * wk for wk in w]
        for x, y in batch:
            f = _features(x, d)
            err = sum(a * b for a, b in zip(w, f)) - y
            for k in range(d + 1):
                grad[k] += 2 * err * f[k] / len(batch)
        w = [a - config["lr"] * g for a, g in zip(w, grad)]
        if any(abs(a) > 1e6 for a in w):
            return None                      # diverged
    return w


def _mse(w, data, degree):
    if w is None:
        return 1e6
    total = 0.0
    for x, y in data:
        pred = sum(a * b for a, b in zip(w, _features(x, degree)))
        total += (pred - y) ** 2
    return total / len(data)


def train_and_score(config, seed):
    """One run: (proxy, heldout), both mean squared error."""
    global TRAIN_CALLS
    TRAIN_CALLS += 1
    d = config["degree"]
    proxy = _mse(_sgd(config, seed, PROXY_STEPS), VAL_PROXY, d)
    held = _mse(_sgd(config, seed, HELD_STEPS), VAL_HELD, d)
    return proxy, held


def dump_line(record):
    """The one canonical way to write a record: sorted keys, no spaces."""
    return json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"


def experiment_seeds(index, k):
    """Fresh seeds for experiment `index`, so decisions do not reuse luck."""
    return [1000 * (index + 1) + j for j in range(k)]


class RandomProposer:
    """Stand-in for the agent: perturb one or two settings of the best."""

    def __init__(self, seed):
        self.rng = random.Random(seed)

    def propose(self, best, index):
        rng = self.rng
        cfg = dict(best)
        for key in rng.sample(["lr", "degree", "l2", "batch"],
                              rng.choice([1, 1, 2])):
            if key == "lr":
                cfg["lr"] = min(0.5, max(0.001,
                                cfg["lr"] * math.exp(rng.gauss(0, 0.5))))
            elif key == "degree":
                cfg["degree"] = min(9, max(1,
                                cfg["degree"] + rng.choice([-1, 1])))
            elif key == "l2":
                cfg["l2"] = min(1.0, max(1e-6,
                                cfg["l2"] * 10 ** rng.gauss(0, 0.7)))
            else:
                cfg["batch"] = rng.choice([2, 4, 8, 16, 32])
        cfg["lr"] = round(cfg["lr"], 4)
        cfg["l2"] = float("%.3g" % cfg["l2"])
        return cfg


class ScriptedProposer:
    """Replays a fixed list of candidate configs (used by replay)."""

    def __init__(self, configs):
        self.configs = list(configs)

    def propose(self, best, index):
        return self.configs[index]


# ── 1. The run store ────────────────────────────────────────────────
class DuplicateKey(Exception):
    """A record with this key is already in the store."""


def config_hash(config):
    """12 hex characters of the SHA-256 of the canonical JSON of `config`.

    Canonical means sorted keys and separators (",", ":"), so that
    {"a": 1, "b": 2} and {"b": 2, "a": 1} hash alike.
    >>> config_hash({"a": 1})
    '015abd7f5cc5'
    """
    raise NotImplementedError("TODO milestone 1: config_hash")


def run_key(config, seed):
    return f"{config_hash(config)}:{seed}"


class RunStore:
    """Append-only JSONL file. Opening an existing file loads it."""

    def __init__(self, path):
        self.path = path
        self.records = {}
        self.load()

    def load(self):
        """Read self.path (if it exists) into self.records, keyed by "key".
    
        A crash can leave half a line at the end, with no newline. Ignore
        it, and cut it off the file, so that the next append is valid.
        """
        raise NotImplementedError("TODO milestone 1: load")

    def append(self, record):
        """Add one record: write dump_line(record) to the end of the file and
        remember it in self.records. If its key is already there, raise
        DuplicateKey and leave the file alone. Never rewrite old lines.
        """
        raise NotImplementedError("TODO milestone 1: append")

    def get(self, key):
        """The record stored under `key`, or None."""
        raise NotImplementedError("TODO milestone 1: get")

    def __len__(self):
        return len(self.records)


def evaluate(config, seed, store):
    """The run record for (config, seed). Train only if the store has no
    record under run_key(config, seed); otherwise return the stored one.

    A new record is a dict with exactly these fields:
    kind "run", key, hash (config_hash), seed, config, proxy, heldout
    (the two scores from train_and_score). Append it to the store.
    """
    raise NotImplementedError("TODO milestone 1: evaluate")


# ── 2. The noise floor ──────────────────────────────────────────────
def mean(xs):
    """Arithmetic mean of a non-empty list."""
    raise NotImplementedError("TODO milestone 2: mean")


def sample_sd(xs):
    """Sample standard deviation: divide by n - 1, not n.
    >>> round(sample_sd([2, 4, 4, 4, 5, 5, 7, 9]), 4)
    2.1381
    """
    raise NotImplementedError("TODO milestone 2: sample_sd")


def noise_floor(config, seeds, store):
    """Run `config` on every seed (through evaluate, so the store caches
    them) and report how much it moves on its own. Returns

        {"n": len(seeds),
         "proxy":   {"mean": m, "sd": s, "floor": f},
         "heldout": {"mean": m, "sd": s, "floor": f}}

    with floor = 1.96 * sqrt(2) * sd: the difference between two single
    runs that reseeding alone produces 95% of the time.
    """
    raise NotImplementedError("TODO milestone 2: noise_floor")


# ── 3. Keep or revert, on a paired test ─────────────────────────────
def paired_test(diffs):
    """Test whether per-seed differences have a mean different from zero.

    Returns (mean, sd, t, df, significant) where sd is the sample sd,
    t = mean / (sd / sqrt(n)), df = n - 1 and significant means
    abs(t) > t_critical(df). If sd == 0: t is 0.0 when the mean is 0,
    else +inf or -inf by the sign of the mean.
    >>> paired_test([1, 2, 3, 4, 5])      # (3.0, 1.5811, 4.2426, 4, True)
    """
    raise NotImplementedError("TODO milestone 3: paired_test")


def keep_or_revert(best, cand, seeds, store):
    """Decide whether `cand` replaces `best`, on the PROXY score only.

    For each seed, run both configs on that same seed (through
    evaluate) and take diff = best.proxy - cand.proxy (positive means
    the candidate is better: scores are errors). Then paired_test.
    Return {"keep": bool, "mean_gain": mean, "t": t, "df": df} where
    keep is true only if the mean gain is positive AND significant.
    """
    raise NotImplementedError("TODO milestone 3: keep_or_revert")


# ── 4. One experiment, logged with both scores ──────────────────────
def run_experiment(index, best, cand, store, k=5):
    """One experiment: decide on the proxy, log both scores.

    seeds = experiment_seeds(index, k). Decide with keep_or_revert.
    heldout_gain = mean over the same seeds of best.heldout - cand.heldout
    (also through evaluate). The held-out score never affects "keep".
    Append and return this record:

        kind "experiment", key f"exp:{index:04d}", index,
        best_hash (config_hash of best), cand_config, seeds, keep, t,
        proxy_gain (the decision's mean_gain), heldout_gain,
        gap (proxy_gain - heldout_gain)
    """
    raise NotImplementedError("TODO milestone 4: run_experiment")


def research_loop(proposer, n, store, k=5, start=None):
    """Run n experiments. Start from a copy of `start` (default BASELINE).

    For i in range(n): cand = proposer.propose(best, i), then
    run_experiment(i, best, cand, store, k); if it was kept, the
    candidate becomes the best. Return (best_config, list_of_records).
    """
    raise NotImplementedError("TODO milestone 4: research_loop")


# ── 5. The gap, its trend, and a text chart ─────────────────────────
def cumulative(history):
    """Running totals over the history, one entry per experiment:
    (cum_proxy, cum_heldout, cum_gap), where only KEPT experiments add
    their proxy_gain and heldout_gain, and cum_gap = cum_proxy - cum_heldout.
    """
    raise NotImplementedError("TODO milestone 5: cumulative")


def ols_slope(ys):
    """Least-squares slope of ys against x = 0, 1, 2, ...
    >>> ols_slope([1, 3, 5, 7])
    2.0
    """
    raise NotImplementedError("TODO milestone 5: ols_slope")


def detect_overfit(cum_proxy, cum_heldout, window=10, min_slope=0.002):
    """First index i (at least window - 1) at which, over the last
    `window` experiments ending at i, BOTH hold:
      - the gap (cum_proxy - cum_heldout) has ols_slope >= min_slope, and
      - cum_heldout has ols_slope <= 0 (the held-out gain is not growing).
    Return None if that never happens.
    """
    raise NotImplementedError("TODO milestone 5: detect_overfit")


def text_chart(cum_proxy, cum_heldout, every=10, width=30):
    """Two bars per checkpoint, every `every` experiments.

    scale = max(max(cum_proxy), max(cum_heldout), 1e-12)
    For i in every-1, 2*every-1, ... and for ("P", cum_proxy[i]) then
    ("H", cum_heldout[i]): n = max(0, round(width * v / scale)) and the line
        f"{i + 1:>4} {tag} {'#' * n:<{width}} {v:+.4f}"
    Return the lines joined by newlines (no trailing newline).
    """
    raise NotImplementedError("TODO milestone 5: text_chart")


# ── 6. Byte-identical replay ────────────────────────────────────────
def first_difference(path_a, path_b):
    """1-based number of the first line at which the two files differ
    (compare bytes; a shorter file differs at its first missing line),
    or None if they are byte-identical."""
    raise NotImplementedError("TODO milestone 6: first_difference")


def replay(path, out_path):
    """Re-execute the log at `path` into a fresh store at out_path.

    Delete out_path if it exists; make a RunStore there; best = a copy of
    BASELINE. Then, for each record of `path`, in file order:
      "run"        -> evaluate(config, seed, store)
      "experiment" -> run_experiment(index, best, cand_config, store,
                                     len(seeds)); if kept, cand is the best
    Return first_difference(path, out_path): None means byte-identical.
    """
    raise NotImplementedError("TODO milestone 6: replay")
