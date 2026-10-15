"""An improver's elasticity: how much held-out gain does each dollar buy?

A small API-driven improver edits one function (the priority rule of online
bin packing, starting from the poor "worst fit" rule), keeps a change only if
it packs the TRAIN instances into fewer bins, and is stopped after 2, 8 and
32 proposals. For each stopping point
we measure the dollars spent and the bins saved on HELD-OUT instances the
loop never saw, then fit gain = a * cost^e and report the elasticity e with
a bootstrap interval over seeds, for the whole range and for each step of it.

Lab VM (needs OPENAI_API_KEY; about 400 calls, well under 1 dollar):
    source ~/.config/lab.env && python3 improver_elasticity.py
No key, no cost (a random-constant stand-in instead of the model; it is
charged a fixed 600 + 250 pretend tokens a call so costs line up):
    python3 improver_elasticity.py --stub
Other sizes, or a looser cap on the length of a proposed function:
    python3 improver_elasticity.py --seeds 4 --budgets 4 16 64
    python3 improver_elasticity.py --max-chars 6000 --cache calls_long.jsonl

Standard library only. Replies are cached in calls.jsonl, so a re-run
replays the same trajectories at no cost."""
import argparse
import ast
import hashlib
import json
import math
import os
import random
import re
import multiprocessing
import resource
import statistics
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ProcessPoolExecutor

# ── 1. Settings ──────────────────────────────────────────────────────────
ap = argparse.ArgumentParser()
ap.add_argument("--model", default="gpt-5.4-nano")
ap.add_argument("--seeds", type=int, default=12)
ap.add_argument("--budgets", type=int, nargs="+", default=[2, 8, 32])
ap.add_argument("--max-chars", type=int, default=2000)  # source cap
ap.add_argument("--stub", action="store_true")      # no API, no cost
ap.add_argument("--cache", default="calls.jsonl")
ap.add_argument("--boot", type=int, default=2000)   # bootstrap resamples
args, _ = ap.parse_known_args()   # notebooks pass their own flags

PRICE_IN = 0.20e-6        # dollars per input token (gpt-5.4-nano list price)
PRICE_OUT = 1.25e-6       # dollars per output token
CAP, ITEMS = 100, 200     # bin capacity; items per instance
N_TRAIN, N_HELD = 10, 30  # instances the loop sees / never sees
SEED_SRC = "def priority(item, rem):\n    return rem - item\n"  # worst fit
ALLOWED = (ast.Module, ast.FunctionDef, ast.arguments, ast.arg, ast.Return,
           ast.Assign, ast.AugAssign, ast.If, ast.IfExp, ast.While,
           ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.Compare, ast.Call,
           ast.Name, ast.Constant, ast.Load, ast.Store, ast.Add, ast.Sub,
           ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.USub, ast.Not,
           ast.And, ast.Or, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.Eq,
           ast.NotEq, ast.Break, ast.Pass)
BUILTINS = {"abs": abs, "min": min, "max": max}


# ── 2. The object level: pack items, score a candidate safely ────────────
def instances(seed, kind, n):
    """n instances of ITEMS item sizes in 20..60, fixed by (seed, kind)."""
    rng = random.Random(f"{kind}-{seed}")
    return [[rng.randint(20, 60) for _ in range(ITEMS)] for _ in range(n)]


def pack(items, priority):
    """Bins used when each item goes to the feasible bin of top priority."""
    rems = []
    for it in items:
        best, where = None, None
        for i, r in enumerate(rems):
            if r >= it:
                p = priority(it, r)
                if best is None or p > best:
                    best, where = p, i
        if where is None:
            rems.append(CAP - it)
        else:
            rems[where] -= it
    return len(rems)


def validate(src):
    """Parse src; allow one function, no imports, no attributes."""
    tree = ast.parse(src)
    if len(src) > args.max_chars:
        raise ValueError("too long")
    for node in ast.walk(tree):
        if not isinstance(node, ALLOWED):
            raise ValueError(type(node).__name__ + " is not allowed")
        if isinstance(node, ast.Call) and not (
                isinstance(node.func, ast.Name) and node.func.id in BUILTINS):
            raise ValueError("only abs, min and max may be called")
    fns = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
    if len(fns) != 1 or fns[0].name != "priority" or len(tree.body) != 1:
        raise ValueError("exactly one function, named priority")
    return tree


def _score(src, insts, conn):
    """Child process: hard CPU and memory limits, then score src."""
    resource.setrlimit(resource.RLIMIT_CPU, (3, 3))            # seconds
    resource.setrlimit(resource.RLIMIT_AS, (1 << 30, 1 << 30))  # 1 GiB
    try:
        space = {"__builtins__": BUILTINS}
        exec(compile(validate(src), "<candidate>", "exec"), space)
        fn = space["priority"]
        conn.send(sum(pack(items, fn) for items in insts) / len(insts))
    except Exception:                    # rejected or crashed
        conn.send(None)


def mean_bins(src, insts, seconds=2.0):
    """Mean bins over insts, or None if src is rejected, crashes or hangs.

    The candidate runs in its own process with CPU and memory limits and
    is killed after `seconds`, so even a single C-level operation that
    never returns (9 ** 9 ** 9) cannot stall or exhaust the loop."""
    ctx = multiprocessing.get_context("fork")
    recv, send = ctx.Pipe(duplex=False)
    proc = ctx.Process(target=_score, args=(src, insts, send))
    proc.start()
    send.close()
    try:
        value = recv.recv() if recv.poll(seconds) else None
    except EOFError:                     # the child died without answering
        value = None
    if proc.is_alive():
        proc.kill()
    proc.join()
    return value


# ── 3. The proposer: a model call, cached, with its cost ─────────────────
def prompt_for(src, bins, history):
    tried = "\n".join(f"- {h}" for h in history[-3:]) or "- (none yet)"
    return (
        "You improve a heuristic for online bin packing. Bins hold 100; "
        "items of size 20 to 60 arrive one at a time. Each item goes to "
        "the feasible bin (rem >= item) with the highest priority(item, "
        "rem), where rem is the space left in that bin. Fewer bins is "
        "better.\n\nCurrent function, using "
        f"{bins:.2f} bins per instance on average:\n```python\n{src}```\n"
        f"Recent attempts that did not help:\n{tried}\n\n"
        "Write ONE improved version. Use only arithmetic, comparisons, "
        "if/else, abs, min and max (no ** operator: write 1000000, not "
        "10**6). Reply with the full function in one "
        "```python block and a one-line comment saying what you changed.")


def key_of(seed, step, prompt):
    h = hashlib.sha256(prompt.encode()).hexdigest()[:16]
    return f"{seed}:{step}:{h}"


def load_cache(path):
    cache = {}
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                row = json.loads(line)
                cache[row["key"]] = row
    return cache


def call_api(prompt):
    """One chat completion; returns (text, tokens in, tokens out)."""
    body = json.dumps({"model": args.model, "messages": [
        {"role": "user", "content": prompt}],
        "max_completion_tokens": 1200}).encode()
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions", body, {
            "Content-Type": "application/json",
            "Authorization": "Bearer " + os.environ["OPENAI_API_KEY"]})
    for attempt in range(6):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                data = json.load(r)
            u = data["usage"]
            return (data["choices"][0]["message"]["content"] or "",
                    u["prompt_tokens"], u["completion_tokens"])
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503) or attempt == 5:
                raise
        except (urllib.error.URLError, TimeoutError):
            if attempt == 5:
                raise
        time.sleep(2 ** attempt)


def stub_reply(seed, step, src):
    """No model: nudge a few constants into a fixed template."""
    rng = random.Random(f"stub-{seed}-{step}")
    a, b, c = (round(rng.uniform(-3, 3), 2) for _ in range(3))
    return (f"```python\ndef priority(item, rem):\n    gap = rem - item\n"
            f"    return {a} * gap + {b} * abs(gap - 20) + {c} * rem\n```",
            600, 250)    # fixed pretend tokens: comparable cost axis, $0 spent


def extract(reply):
    m = re.search(r"```(?:python)?\n(.*?)```", reply, re.S)
    return m.group(1) if m else reply


# ── 4. One improver run: keep a change only if the TRAIN score improves ──
def run_seed(seed):
    """One trajectory of max(budgets) proposals. Returns checkpoints."""
    train = instances(seed, "train", N_TRAIN)
    held = instances(seed, "held", N_HELD)
    cache = load_cache(args.cache)
    inc, inc_bins = SEED_SRC, mean_bins(SEED_SRC, train)
    start_held = mean_bins(SEED_SRC, held)
    history, spent = [], 0.0
    out = {"seed": seed, "start_train": inc_bins, "start_held": start_held,
           "points": {}, "errors": 0, "accepts": 0}
    for step in range(1, max(args.budgets) + 1):
        prompt = prompt_for(inc, inc_bins, history)
        key = key_of(seed, step, prompt)
        if key in cache:
            row = cache[key]
        else:
            text, tin, tout = (stub_reply(seed, step, inc) if args.stub
                               else call_api(prompt))
            row = {"key": key, "reply": text, "tin": tin, "tout": tout}
            with open(args.cache, "a") as f:    # append at once: a crash
                f.write(json.dumps(row) + "\n")  # loses no paid reply
        spent += row["tin"] * PRICE_IN + row["tout"] * PRICE_OUT
        cand = extract(row["reply"])
        bins = mean_bins(cand, train)
        if bins is None:
            out["errors"] += 1
            history.append("a version that was rejected or crashed")
        elif bins < inc_bins:
            inc, inc_bins = cand, bins
            out["accepts"] += 1
            history = []
        else:
            history.append(f"a version using {bins:.2f} bins")
        if step in args.budgets:
            out["points"][step] = {
                "cost": spent, "train": inc_bins,
                "held": mean_bins(inc, held)}
    out["final_src"] = inc
    return out


# ── 5. Elasticity: fit gain = a * cost^e, interval by bootstrap ──────────
def slope(xs, ys):
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    return (sum((x - mx) * (y - my) for x, y in zip(xs, ys))
            / sum((x - mx) ** 2 for x in xs))


def elasticity(runs, budgets):
    """Slope of ln(mean gain) on ln(mean cost) over the budgets, or None."""
    gains = [statistics.fmean(r["start_held"] - r["points"][b]["held"]
                              for r in runs) for b in budgets]
    costs = [statistics.fmean(r["points"][b]["cost"] for r in runs)
             for b in budgets]
    if min(gains) <= 0 or min(costs) <= 0:
        return None
    return slope([math.log(c) for c in costs], [math.log(g) for g in gains])


def report(results):
    B = sorted(args.budgets)
    print(f"{'calls':>5} {'cost $':>8} {'train saved':>12} "
          f"{'held-out saved':>16} {'se':>6}")
    for b in B:
        g = [r["start_held"] - r["points"][b]["held"] for r in results]
        t = [r["start_train"] - r["points"][b]["train"] for r in results]
        c = [r["points"][b]["cost"] for r in results]
        se = statistics.stdev(g) / math.sqrt(len(g))
        print(f"{b:>5} {statistics.fmean(c):>8.4f} "
              f"{statistics.fmean(t):>12.2f} "
              f"{statistics.fmean(g):>16.2f} {se:>6.2f}")
    rng = random.Random(0)
    for label, bs in [("whole range", B)] + [
            (f"{a} to {b} calls", [a, b]) for a, b in zip(B, B[1:])]:
        e = elasticity(results, bs)
        boots, skipped = [], 0
        for _ in range(args.boot):
            v = elasticity([rng.choice(results) for _ in results], bs)
            if v is None:
                skipped += 1
            else:
                boots.append(v)
        boots.sort()
        if e is None or len(boots) < 100:
            print(f"e ({label}): undefined, a mean gain was not above zero")
            continue
        lo, hi = boots[int(0.025 * len(boots))], boots[int(0.975 * len(boots))]
        print(f"e ({label}) = {e:.2f}   95% bootstrap interval "
              f"{lo:.2f} to {hi:.2f}   ({skipped} of {args.boot} skipped)")
    tot = sum(r["points"][max(B)]["cost"] for r in results)
    errs = sum(r["errors"] for r in results)
    acc = sum(r["accepts"] for r in results)
    held = instances(1, "held", N_HELD)
    ref = results[0]["start_held"] - mean_bins(
        "def priority(item, rem):\n    return item - rem\n", held)
    print(f"reference: plain best fit saves {ref:.2f} bins on seed 1's "
          f"held-out set")
    what = "pretend spend (stub)" if args.stub else "total spend"
    print(f"accepts {acc}, rejected or crashed {errs} of "
          f"{len(results) * max(B)} proposals; {what} ${tot:.2f}")


# ── 6. Run all seeds in parallel, then report ────────────────────────────
if __name__ == "__main__":
    if not args.stub and "OPENAI_API_KEY" not in os.environ:
        sys.exit("set OPENAI_API_KEY (source ~/.config/lab.env) or --stub")
    with ProcessPoolExecutor(max_workers=min(args.seeds, 16)) as pool:
        results = list(pool.map(run_seed, range(1, args.seeds + 1)))
    report(results)
    best = max(results, key=lambda r: r["start_held"]
               - r["points"][max(args.budgets)]["held"])
    print(f"\nbest final function (seed {best['seed']}):")
    print(best["final_src"])
