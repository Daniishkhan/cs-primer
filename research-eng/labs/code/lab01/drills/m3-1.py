# Drill: A9 Lab 1, milestone 3 of 6: keep or revert on a paired test (step 1 of 2)
# Everything else in this file is already written. Fill in:
#     paired_test
# Check it with: python3 check.py 3

"""Lab 1 reference solution: a keep-or-revert research loop.

Pure standard library, no clock, no network. Every random number comes
from a seeded random.Random, so every number below repeats exactly.

The inner task is a toy "training run": fit a polynomial to noisy data
with minibatch SGD. A config says how (lr, degree, l2, batch). A run
gives two scores for the same weights (lower is better):

    proxy    40 SGD steps, scored on a 16-point validation slice
    heldout  300 SGD steps, scored on 400 fresh points

The loop only ever decides on the proxy. The held-out score is logged,
never used to decide, and the gap between the two is the extension.
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
    """12 hex characters of SHA-256 over the canonical JSON of config."""
    text = json.dumps(config, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def run_key(config, seed):
    return f"{config_hash(config)}:{seed}"


class RunStore:
    """Append-only JSONL file. Opening an existing file loads it."""

    def __init__(self, path):
        self.path = path
        self.records = {}
        self.load()

    def load(self):
        """Read the file (if it exists) into self.records."""
        if os.path.exists(self.path):
            with open(self.path, encoding="utf-8") as fh:
                text = fh.read()
            keep = text[:text.rfind("\n") + 1]    # drop a torn last line
            if keep != text:
                with open(self.path, "w", encoding="utf-8") as fh:
                    fh.write(keep)
            for line in keep.splitlines():
                rec = json.loads(line)
                self.records[rec["key"]] = rec

    def append(self, record):
        key = record["key"]
        if key in self.records:
            raise DuplicateKey(key)
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(dump_line(record))
        self.records[key] = record

    def get(self, key):
        return self.records.get(key)

    def __len__(self):
        return len(self.records)


def evaluate(config, seed, store):
    """The run record for (config, seed); train only if it is new."""
    key = run_key(config, seed)
    rec = store.get(key)
    if rec is None:
        proxy, held = train_and_score(config, seed)
        rec = {"kind": "run", "key": key, "hash": config_hash(config),
               "seed": seed, "config": config,
               "proxy": proxy, "heldout": held}
        store.append(rec)
    return rec


# ── 2. The noise floor ──────────────────────────────────────────────
def mean(xs):
    return sum(xs) / len(xs)


def sample_sd(xs):
    """Standard deviation with n - 1 in the denominator."""
    m = mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def noise_floor(config, seeds, store):
    """How far two single runs of one config differ by reseeding alone."""
    recs = [evaluate(config, s, store) for s in seeds]
    out = {"n": len(recs)}
    for name in ("proxy", "heldout"):
        vals = [r[name] for r in recs]
        sd = sample_sd(vals)
        out[name] = {"mean": mean(vals), "sd": sd,
                     "floor": 1.96 * math.sqrt(2) * sd}
    return out


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
    """Keep `cand` only if it beats `best` on the proxy, paired by seed."""
    diffs = []
    for s in seeds:
        b = evaluate(best, s, store)["proxy"]
        c = evaluate(cand, s, store)["proxy"]
        diffs.append(b - c)           # positive: the candidate is better
    m, sd, t, df, sig = paired_test(diffs)
    return {"keep": m > 0 and sig, "mean_gain": m, "t": t, "df": df}


# ── 4. One experiment, logged with both scores ──────────────────────
def run_experiment(index, best, cand, store, k=5):
    seeds = experiment_seeds(index, k)
    dec = keep_or_revert(best, cand, seeds, store)
    held = [evaluate(best, s, store)["heldout"]
            - evaluate(cand, s, store)["heldout"] for s in seeds]
    proxy_gain = dec["mean_gain"]
    held_gain = mean(held)
    rec = {"kind": "experiment", "key": f"exp:{index:04d}",
           "index": index, "best_hash": config_hash(best),
           "cand_config": cand, "seeds": seeds, "keep": dec["keep"],
           "t": dec["t"], "proxy_gain": proxy_gain,
           "heldout_gain": held_gain, "gap": proxy_gain - held_gain}
    store.append(rec)
    return rec


def research_loop(proposer, n, store, k=5, start=None):
    """n experiments; returns (best_config, list of experiment records)."""
    best = dict(start or BASELINE)
    history = []
    for i in range(n):
        cand = proposer.propose(best, i)
        rec = run_experiment(i, best, cand, store, k)
        history.append(rec)
        if rec["keep"]:
            best = cand
    return best, history


# ── 5. The gap, its trend, and a text chart ─────────────────────────
def cumulative(history):
    """Running totals over kept experiments: proxy, heldout and gap."""
    p = h = 0.0
    cp, ch, cg = [], [], []
    for rec in history:
        if rec["keep"]:
            p += rec["proxy_gain"]
            h += rec["heldout_gain"]
        cp.append(p)
        ch.append(h)
        cg.append(p - h)
    return cp, ch, cg


def ols_slope(ys):
    """Least-squares slope of ys against 0, 1, 2, ..."""
    n = len(ys)
    xbar = (n - 1) / 2
    ybar = mean(ys)
    num = sum((i - xbar) * (y - ybar) for i, y in enumerate(ys))
    den = sum((i - xbar) ** 2 for i in range(n))
    return num / den


def detect_overfit(cum_proxy, cum_heldout, window=10, min_slope=0.002):
    """First index where, over the last `window` experiments, the proxy
    gain climbs at >= min_slope per experiment while the held-out gain
    does not climb at all (its slope is <= 0)."""
    for i in range(window - 1, len(cum_proxy)):
        lo = i - window + 1
        gap = [p - h for p, h in zip(cum_proxy[lo:i + 1],
                                     cum_heldout[lo:i + 1])]
        if (ols_slope(gap) >= min_slope
                and ols_slope(cum_heldout[lo:i + 1]) <= 0):
            return i
    return None


def text_chart(cum_proxy, cum_heldout, every=10, width=30):
    scale = max(max(cum_proxy), max(cum_heldout), 1e-12)
    lines = []
    for i in range(every - 1, len(cum_proxy), every):
        for tag, v in (("P", cum_proxy[i]), ("H", cum_heldout[i])):
            n = max(0, round(width * v / scale))
            lines.append(f"{i + 1:>4} {tag} {'#' * n:<{width}} {v:+.4f}")
    return "\n".join(lines)


# ── 6. Byte-identical replay ────────────────────────────────────────
def first_difference(path_a, path_b):
    """1-based number of the first differing line, or None if the two
    files are byte-identical."""
    with open(path_a, "rb") as fa, open(path_b, "rb") as fb:
        a = fa.read().split(b"\n")
        b = fb.read().split(b"\n")
    for i in range(max(len(a), len(b))):
        la = a[i] if i < len(a) else None
        lb = b[i] if i < len(b) else None
        if la != lb:
            return i + 1
    return None


def replay(path, out_path):
    """Re-execute every record of the log at `path` into a fresh store
    at out_path, in file order; then compare the two files."""
    if os.path.exists(out_path):
        os.remove(out_path)
    store = RunStore(out_path)
    best = dict(BASELINE)
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            rec = json.loads(line)
            if rec["kind"] == "run":
                evaluate(rec["config"], rec["seed"], store)
            else:
                again = run_experiment(rec["index"], best,
                                       rec["cand_config"], store,
                                       len(rec["seeds"]))
                if again["keep"]:
                    best = rec["cand_config"]
    return first_difference(path, out_path)
