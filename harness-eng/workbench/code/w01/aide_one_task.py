"""AIDE on one small task: nodes per hour, cost per node, tree versus greedy.

    python aide_one_task.py --arm tree   --seed 0 --steps 20
    python aide_one_task.py --arm greedy --seed 0 --steps 20
    python aide_one_task.py --report runs/tree-s0 runs/greedy-s0 ...

Needs: pip install aideml, OPENAI_API_KEY in the environment, and the
task/ and private/ folders from make_task.py in the current directory.

Both arms run aideml's own Agent with the same prompts, model and steps.
The only difference is agent.search.num_drafts: 5 for the tree arm (aideml's
default), 1 for the greedy arm, so it drafts once and then keeps improving
the best node it has. Each node's submission.csv is scored on the private
rows after the agent has finished with it; the agent never sees that score.
"""
import argparse
import csv
import glob
import json
import math
import os
import random
import shutil
import signal
import subprocess
import time

ap = argparse.ArgumentParser()
ap.add_argument("--arm", choices=["tree", "greedy"], default="tree")
ap.add_argument("--seed", type=int, default=0)       # python's random only
ap.add_argument("--steps", type=int, default=20)     # nodes per run (budget)
ap.add_argument("--model", default="gpt-5.4-mini")
ap.add_argument("--feedback-model", default="gpt-5.4-mini")
ap.add_argument("--out", default="runs")
ap.add_argument("--report", nargs="*", default=None)
ap.add_argument("--exec-timeout", type=int, default=300)  # s per script
args, _ = ap.parse_known_args()

# USD per million tokens, from OpenAI's pricing page (see the workbench page)
PRICE = {"gpt-5.4-mini": (0.75, 4.50), "gpt-5.4-nano": (0.20, 1.25)}


# ── 1. The private scorer: RMSE between log prices ───────────────────────
def private_rmse(path, labels="private/test_labels.csv"):
    """Return the RMSE of log prices for a submission, or None if unusable."""
    try:
        with open(labels, newline="") as f:
            want = {r["Id"]: float(r["SalePrice"]) for r in csv.DictReader(f)}
        with open(path, newline="") as f:
            got = {r["Id"]: float(r["SalePrice"]) for r in csv.DictReader(f)}
        if set(got) != set(want) or any(v <= 0 for v in got.values()):
            return None
        se = [(math.log(got[i]) - math.log(want[i])) ** 2 for i in want]
        return math.sqrt(sum(se) / len(se))
    except (OSError, KeyError, ValueError):
        return None


# ── 2. One run: AIDE's own agent, with counters bolted on ────────────────
def sweep_strays(keep):
    """Kill every process in our session except those in `keep`.

    The agent's generated scripts often start joblib worker pools. When a
    script times out, aideml kills the script but its workers can survive
    and keep every core busy, so we clear them out between nodes."""
    sid = os.getsid(0)
    ps = subprocess.run(["ps", "-eo", "pid=,sid="], capture_output=True,
                        text=True).stdout
    for line in ps.splitlines():
        pid, s = (int(x) for x in line.split())
        if s == sid and pid not in keep:
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass


def watchdog(signum, frame):
    raise RuntimeError("step watchdog: the step took far too long")


def run_once():
    import aide.backend as backend
    from aide import Experiment, Interpreter
    from aide.utils.config import save_run
    from omegaconf import OmegaConf

    try:
        os.setsid()                    # our own session, to sweep later
    except OSError:
        pass
    signal.signal(signal.SIGALRM, watchdog)
    random.seed(args.seed)
    name = f"{args.arm}-s{args.seed}"
    run_dir = os.path.abspath(os.path.join(args.out, name))
    shutil.rmtree(run_dir, ignore_errors=True)
    os.makedirs(run_dir)
    os.chdir(run_dir)                  # aideml writes logs/ and workspaces/
    task = os.path.abspath("../../task")
    labels = os.path.abspath("../../private/test_labels.csv")

    calls = []                         # (seconds, tokens in, tokens out)
    inner = backend.provider_to_query_func["openai"]

    def counted(**kw):
        out = inner(**kw)
        calls.append((out[1], out[2], out[3]))
        return out
    backend.provider_to_query_func["openai"] = counted

    exp = Experiment(
        data_dir=task,
        goal="Predict the sales price for each house",
        eval="RMSE between log-prices")
    cfg = exp.cfg
    cfg.agent.code.model = args.model
    cfg.agent.feedback.model = args.feedback_model
    cfg.agent.search.num_drafts = 5 if args.arm == "tree" else 1
    cfg.exec.timeout = args.exec_timeout
    sub = os.path.join(cfg.workspace_dir, "working", "submission.csv")
    pin, pout = PRICE[args.model]
    log = open("steps.jsonl", "w")
    t_start = time.time()
    died = 0                           # times the script's child died
    while len(exp.journal.nodes) < args.steps and died < 5:
        step = len(exp.journal.nodes)
        child = getattr(exp.interpreter, "process", None)
        sweep_strays({os.getpid(), child.pid if child else 0})
        if os.path.exists(sub):
            os.remove(sub)             # no stale file from the last node
        n0, t0 = len(calls), time.time()
        signal.alarm(2 * args.exec_timeout + 120)   # per-node ceiling
        try:
            exp.agent.step(exec_callback=exp.interpreter.run)
            signal.alarm(0)
        except RuntimeError as err:    # child died, or the watchdog fired
            signal.alarm(0)
            died += 1
            mine = calls[n0:]
            tin = sum(c[1] for c in mine)
            tout = sum(c[2] for c in mine)
            log.write(json.dumps({
                "step": step, "died": str(err), "tok_in": tin,
                "tok_out": tout,
                "usd": round((tin * pin + tout * pout) / 1e6, 5)}) + "\n")
            log.flush()
            exp.interpreter = Interpreter(
                cfg.workspace_dir,
                **OmegaConf.to_container(cfg.exec))   # a fresh child
            continue
        node = exp.journal.nodes[-1]
        mine = calls[n0:]
        tin = sum(c[1] for c in mine)
        tout = sum(c[2] for c in mine)
        row = {
            "step": step, "stage": node.stage_name,
            "parent": node.parent.step if node.parent else None,
            "buggy": bool(node.is_buggy),
            "val": None if node.is_buggy else node.metric.value,
            "maximize": None if node.is_buggy else node.metric.maximize,
            "crashed": node.exc_type is not None,
            "private": private_rmse(sub, labels),   # even if flagged buggy
            "seconds": round(time.time() - t0, 1),
            "calls": len(mine), "tok_in": tin, "tok_out": tout,
            "usd": round((tin * pin + tout * pout) / 1e6, 5)}
        log.write(json.dumps(row) + "\n")
        log.flush()
        save_run(cfg, exp.journal)
        print(f"{name} step {step:2d} {row['stage']:7s} "
              f"val {row['val']} private {row['private']} "
              f"{row['seconds']} s ${row['usd']}", flush=True)
    exp.interpreter.cleanup_session()
    log.write(json.dumps({"total_seconds": round(time.time() - t_start, 1),
                          "model": args.model, "arm": args.arm,
                          "seed": args.seed}) + "\n")
    log.close()


# ── 3. Report: speed and cost, then quality, then the paired gap ─────────
def load(d):
    rows = [json.loads(x) for x in open(os.path.join(d, "steps.jsonl"))]
    steps = [r for r in rows if "stage" in r]
    lost = [r for r in rows if "died" in r]
    total = [r for r in rows if "total_seconds" in r]
    secs = total[0]["total_seconds"] if total else \
        sum(r["seconds"] for r in steps)
    good = [r for r in steps if r["val"] is not None
            and r["private"] is not None]
    sign = -1 if good and good[0]["maximize"] else 1
    best = min(good, key=lambda r: sign * r["val"]) if good else None
    return steps, lost, secs, good, best


def report(dirs):
    runs = {d: load(d) for d in dirs}
    print(f"{'run':10s} {'nodes':>5s} {'min':>6s} {'nodes/h':>8s} "
          f"{'median s':>8s} {'max s':>6s} {'$/node':>7s} {'$ total':>8s} "
          f"{'died':>5s}")
    for d, (steps, lost, secs, good, best) in runs.items():
        usd = sum(r["usd"] for r in steps + lost)
        per = sorted(r["seconds"] for r in steps)
        print(f"{os.path.basename(d):10s} {len(steps):5d} {secs / 60:6.1f} "
              f"{len(steps) / secs * 3600:8.1f} {per[len(per) // 2]:8.1f} "
              f"{per[-1]:6.0f} {usd / len(steps):7.4f} "
              f"{usd:8.3f} {len(lost):5d}")
    print()
    print(f"{'run':10s} {'ok':>3s} {'false bug':>9s} {'best val':>9s} "
          f"{'its private':>11s} {'best private':>12s} {'1st draft':>9s}")
    for d, (steps, lost, secs, good, best) in runs.items():
        flagged = [r for r in steps if r["buggy"] and not r["crashed"]
                   and r["private"] is not None]
        draft = next((r for r in good if r["stage"] == "draft"), None)
        print(f"{os.path.basename(d):10s} {len(good):3d} {len(flagged):9d} "
              f"{best['val']:9.4f} {best['private']:11.4f} "
              f"{min(r['private'] for r in good):12.4f} "
              f"{draft['private'] if draft else float('nan'):9.4f}")
    by = {os.path.basename(d): v[4]["private"] for d, v in runs.items()}
    diffs = [(k.split("-s")[1], by[k] - by["tree-s" + k.split("-s")[1]])
             for k in by if k.startswith("greedy-s")
             and "tree-s" + k.split("-s")[1] in by]
    if diffs:
        print("\nprivate RMSE of the selected node, greedy minus tree "
              "(positive: tree better)")
        for seed, d in sorted(diffs):
            print(f"  seed {seed}: {d:+.4f}")
        m = sum(d for _, d in diffs) / len(diffs)
        print(f"  mean over {len(diffs)} seeds: {m:+.4f}")


if args.report is not None:
    report(args.report or sorted(glob.glob(os.path.join(args.out, "*"))))
else:
    run_once()
