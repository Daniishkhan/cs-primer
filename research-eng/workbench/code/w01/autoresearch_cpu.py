"""autoresearch on a CPU proxy: run the loop, then measure its noise.

Run on the lab VM, after cpu_patch.py and prepare.py (see the page):

    python3 autoresearch_cpu.py noise --repo ~/work/re-build/ar-cpu
    python3 autoresearch_cpu.py loop  --repo ~/work/re-build/ar-cpu \
        --experiments 30 --proposer api      # or --proposer random

noise  runs the unmodified baseline several times in four conditions
       (time or step budget, same seed or new seeds) and prints how far
       val_bpb moves with nothing changed.
loop   is autoresearch's loop: propose one edit to a hyperparameter
       constant in train.py, run it, keep it if val_bpb is strictly
       lower than the best so far, otherwise put the old file back.
       Then it re-runs the first and the last kept version on fresh
       seeds, to see whether the "improvement" holds. With --fixed-steps
       every run stops after --steps optimiser steps, not after --budget
       seconds.

Needs: Python 3.9+, a patched autoresearch checkout, the standard
library only. --proposer api needs OPENAI_API_KEY in the environment
(source ~/.config/lab.env); it is read, never printed or written.
"""
import argparse
import hashlib
import json
import math
import os
import random
import re
import shutil
import subprocess
import sys
import time
import urllib.request

# ── 1. Settings ──────────────────────────────────────────────────────
ap = argparse.ArgumentParser()
ap.add_argument("cmd", choices=["noise", "loop"])
ap.add_argument("--repo", default=os.path.expanduser("~/work/re-build/ar-cpu"))
ap.add_argument("--budget", type=int, default=30)     # seconds of training
ap.add_argument("--steps", type=int, default=30)      # step-budget runs
ap.add_argument("--seeds", type=int, default=6)       # noise: runs per cell
ap.add_argument("--threads", type=int, default=4)     # OMP_NUM_THREADS
ap.add_argument("--experiments", type=int, default=30)
ap.add_argument("--proposer", choices=["random", "api"], default="random")
ap.add_argument("--model", default="gpt-5.4-nano")
ap.add_argument("--confirm", type=int, default=5)     # loop: fresh seeds
ap.add_argument("--fixed-steps", action="store_true")  # loop: step budget
ap.add_argument("--seed", type=int, default=0)        # proposer's own seed
ap.add_argument("--out", default="w01_out")
args, _ = ap.parse_known_args()        # notebooks pass their own flags
os.makedirs(args.out, exist_ok=True)
TRAIN = os.path.join(args.repo, "train.py")
FIXED = args.cmd == "loop" and args.fixed_steps
STAT = re.compile(r"^(\w+):\s+(-?[\d.]+)\s*$", re.M)


# ── 2. One training run, as a subprocess ─────────────────────────────
def run_train(seed, budget=None, steps=0):
    """Run train.py once. Returns a dict, with val_bpb None on a crash."""
    steps = steps or (args.steps if FIXED else 0)
    env = dict(os.environ, AR_SEED=str(seed), OMP_NUM_THREADS=str(
        args.threads), AR_BUDGET=str(budget or args.budget),
        AR_STEPS=str(steps))
    load1 = os.getloadavg()[0]
    t0 = time.time()
    try:
        done = subprocess.run([sys.executable, "train.py"], cwd=args.repo,
                              env=env, capture_output=True, text=True,
                              timeout=20 * (budget or args.budget))
        text = done.stdout.split("---")[-1] if "---" in done.stdout else ""
    except subprocess.TimeoutExpired:
        text = ""
    stats = {k: float(v) for k, v in STAT.findall(text)}
    return {"seed": seed, "val_bpb": stats.get("val_bpb"),
            "steps": int(stats.get("num_steps", 0)),
            "train_s": stats.get("training_seconds"),
            "wall_s": round(time.time() - t0, 1), "load1": round(load1, 1)}


def mean(xs):
    return sum(xs) / len(xs)


def sd(xs):
    m = mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


# ── 3. noise: nothing changed, how much does val_bpb move? ───────────
def noise():
    cells = [("time budget, same seed", dict(), lambda i: 42),
             ("time budget, new seeds", dict(), lambda i: i + 1),
             ("step budget, same seed", dict(steps=args.steps), lambda i: 42),
             ("step budget, new seeds", dict(steps=args.steps),
              lambda i: i + 1)]
    print(f"{'condition':26s} {'mean':>7s} {'sd':>7s} {'range':>7s} "
          f"{'floor':>7s} {'steps':>6s} {'wall s':>7s} {'load':>5s}")
    log = open(os.path.join(args.out, "noise.jsonl"), "w")
    for name, kw, seed_of in cells:
        runs = [run_train(seed_of(i), **kw) for i in range(args.seeds)]
        for r in runs:
            log.write(json.dumps(dict(r, cell=name)) + "\n")
        log.flush()
        v = [r["val_bpb"] for r in runs if r["val_bpb"] is not None]
        if len(v) < 2:
            print(f"{name:26s} fewer than 2 runs finished")
            continue
        floor = 1.96 * math.sqrt(2) * sd(v)
        print(f"{name:26s} {mean(v):7.4f} {sd(v):7.4f} "
              f"{max(v) - min(v):7.4f} {floor:7.4f} "
              f"{mean([r['steps'] for r in runs]):6.1f} "
              f"{mean([r['wall_s'] for r in runs]):7.1f} "
              f"{mean([r['load1'] for r in runs]):5.1f}")


# ── 4. Editing train.py: one constant at a time ──────────────────────
KNOBS = {   # name: (allowed values, or None for a free multiplier, lo, hi)
    "EMBEDDING_LR": (None, 0.05, 3.0), "UNEMBEDDING_LR": (None, 0.0005, 0.05),
    "MATRIX_LR": (None, 0.005, 0.3), "SCALAR_LR": (None, 0.05, 3.0),
    "WEIGHT_DECAY": (None, 0.0, 1.0), "WARMDOWN_RATIO": (None, 0.1, 0.9),
    "WARMUP_RATIO": ([0.0, 0.05, 0.1, 0.2], 0.0, 0.2),
    "FINAL_LR_FRAC": ([0.0, 0.05, 0.1, 0.2], 0.0, 0.2),
    "DEPTH": ([3, 4, 5, 6], 3, 6),
}


def read_knob(name):
    for line in open(TRAIN):
        m = re.match(rf"^{name}\s*=\s*([^#\n]+?)\s*(#.*)?$", line)
        if m:
            return eval(m.group(1), {})      # our own file, plain numbers
    raise KeyError(name)


def write_knob(name, value):
    src = open(TRAIN).read()
    new, n = re.subn(rf"^({name}\s*=\s*)[^#\n]+?(\s*(#.*)?)$",
                     lambda m: m.group(1) + repr(value) + m.group(2),
                     src, count=1, flags=re.M)
    assert n == 1, name
    open(TRAIN, "w").write(new)


# ── 5. Two proposers: a rule, and a small model ──────────────────────
class RandomProposer:
    """Stand-in for the agent: scale one constant by a random factor."""

    def __init__(self, seed):
        self.rng = random.Random(seed)

    def propose(self, history):
        name = self.rng.choice(sorted(KNOBS))
        allowed, lo, hi = KNOBS[name]
        cur = read_knob(name)
        if allowed:
            value = self.rng.choice([v for v in allowed if v != cur])
        else:
            value = cur * self.rng.choice([0.5, 0.7, 1.4, 2.0])
            value = round(min(hi, max(lo, value)), 6)
        return name, value, "random rescale"


class ApiProposer:
    """A small chat model reads the constants and the results table."""

    def __init__(self, model, fallback):
        self.model, self.fallback = model, fallback
        self.tokens = 0

    def propose(self, history):
        knobs = {k: read_knob(k) for k in KNOBS}
        rows = "\n".join(f"{h['name']}={h['value']} -> {h['val_bpb']} "
                         f"({h['status']})" for h in history[-12:])
        prompt = (
            "You tune a tiny GPT trained for 30 seconds on a CPU. Lower "
            "val_bpb is better. Current constants:\n"
            f"{json.dumps(knobs)}\nRecent experiments:\n{rows or 'none'}\n"
            "Change exactly ONE constant to a new number. Reply with JSON "
            'only: {"name": ..., "value": ..., "why": "one sentence"}. '
            f"Names allowed: {sorted(KNOBS)}.")
        body = {"model": self.model, "max_completion_tokens": 300,
                "messages": [{"role": "user", "content": prompt}]}
        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=json.dumps(body).encode(),
            headers={"content-type": "application/json",
                     "authorization": "Bearer " + os.environ["OPENAI_API_KEY"]})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                reply = json.loads(r.read())
            self.tokens += reply["usage"]["total_tokens"]
            data = json.loads(re.search(r"\{.*\}", reply["choices"][0][
                "message"]["content"], re.S).group(0))
            name, value = data["name"], float(data["value"])
            allowed, lo, hi = KNOBS[name]
            if name == "DEPTH":
                value = int(value)
            assert lo <= value <= hi and value != read_knob(name)
            return name, value, str(data.get("why", ""))[:80]
        except Exception as e:                    # bad reply: use the rule
            name, value, why = self.fallback.propose(history)
            return name, value, f"fallback ({type(e).__name__})"


# ── 6. loop: keep if strictly lower, else put the old file back ──────
def loop():
    rule = RandomProposer(args.seed)
    prop = rule if args.proposer == "random" else ApiProposer(args.model, rule)
    tsv = open(os.path.join(args.out, "results.tsv"), "w")
    tsv.write("exp\tstatus\tval_bpb\tsteps\twall_s\tload1\tchange\twhy\n")
    first_src = open(TRAIN).read()
    base = run_train(42)
    best, history = base["val_bpb"], []
    tsv.write(f"0\tkeep\t{best:.6f}\t{base['steps']}\t{base['wall_s']}\t"
              f"{base['load1']}\tbaseline\t\n")
    print(f"exp  0 keep    {best:.4f}  baseline, {base['steps']} steps")
    for i in range(1, args.experiments + 1):
        name, value, why = prop.propose(history)
        before = open(TRAIN).read()
        write_knob(name, value)
        r = run_train(42)
        v = r["val_bpb"]
        status = "crash" if v is None else "keep" if v < best else "discard"
        if status == "keep":
            best = v
        else:
            open(TRAIN, "w").write(before)             # revert
        history.append(dict(name=name, value=value, val_bpb=v, status=status))
        tsv.write(f"{i}\t{status}\t{v if v is None else f'{v:.6f}'}\t"
                  f"{r['steps']}\t{r['wall_s']}\t{r['load1']}\t"
                  f"{name}={value}\t{why}\n")
        tsv.flush()
        print(f"exp {i:2d} {status:7s} "
              f"{'-' if v is None else f'{v:.4f}'}  {name}={value}")
    if args.proposer == "api":
        print(f"API tokens used by the proposer: {prop.tokens:,}")
    last_src = open(TRAIN).read()
    confirm(first_src, last_src)


def confirm(first_src, last_src):
    """Fresh seeds, paired by seed: does the kept version beat the first?"""
    diffs = []
    for k in range(args.confirm):
        seed = 1000 + k
        open(TRAIN, "w").write(first_src)
        a = run_train(seed)["val_bpb"]
        open(TRAIN, "w").write(last_src)
        b = run_train(seed)["val_bpb"]
        if a is not None and b is not None:
            diffs.append(a - b)
            print(f"confirm seed {seed}: first {a:.4f}  last {b:.4f}  "
                  f"gain {a - b:+.4f}")
    if len(diffs) > 1:
        t = mean(diffs) / (sd(diffs) / math.sqrt(len(diffs)))
        print(f"mean gain {mean(diffs):+.4f}  sd {sd(diffs):.4f}  "
              f"t = {t:.2f} on {len(diffs)} paired seeds")
    open(TRAIN, "w").write(last_src)


if __name__ == "__main__":
    {"noise": noise, "loop": loop}[args.cmd]()
