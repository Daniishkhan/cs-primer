# Drill: A6 Lab 4, milestone 3 of 5: k trials, pass@k and pass^k (step 2 of 6)
# Everything else in this file is already written. Fill in:
#     pass_hat_k
# Check it with: python3 check.py 3

"""Lab 4: evaluate an agent (reference solution).

A simulated shop (shop.py), a stand-in agent with seeded, stochastic mistakes (agents.py) and 12 tasks
(tasks.json). The harness you build: grade the database the agent leaves behind -> run one reset,
capped trial -> run k trials of every task and report pass@k and pass^k -> put a cost on every success
-> bootstrap over tasks to compare two agent versions.

    1  db_diff, grade_end_state
    2  run_trial
    3  pass_at_k, pass_hat_k, run_suite, task_counts, never_passes, summarise
    4  trial_cost, cost_report
    5  bootstrap_ci, compare_agents

Standard library only.
"""
import copy
import json
import math
import os
import random
from math import comb

from shop import START, Shop, StepCapExceeded
from agents import AGENT_V1, AGENT_V2

HERE = os.path.dirname(os.path.abspath(__file__))
MAX_STEPS = 12                          # the harness's cap on tool calls per trial
PRICE_IN, PRICE_OUT = 3.0, 15.0         # dollars per million tokens: an illustrative assumption, not a real price list


# ----------------------------------------------------------------------------- given

def load_tasks():
    """The 12 tasks: dicts with id, instruction (what the customer wants), steps (for the stand-in agent),
    expected_diff ({path: [old, new]}: exactly what a correct run changes in the database) and must_say
    (words the reply must contain)."""
    with open(os.path.join(HERE, "tasks.json"), encoding="utf-8") as f:
        return json.load(f)


def trial_rng(task_id, trial):
    """The random generator for one trial: the same (task, trial) always gives the same luck."""
    return random.Random(f"{task_id}#{trial}")


# ----------------------------------------------------------------------------- milestone 1

def db_diff(before, after):
    """Every leaf that differs between two databases: {"orders.A101.refund": (0, 25), ...}.

    Walk both dicts together. When a key holds a dict on BOTH sides, recurse, joining the keys with ".".
    Otherwise compare the two values with ==; if they differ, record (old, new) at that path, using
    None for a key that is missing on one side. Lists are leaves (compared whole). Identical databases
    give {}. Do not modify the arguments.
    """
    out = {}

    def walk(a, b, prefix):
        for key in sorted(set(a) | set(b)):
            path = f"{prefix}.{key}" if prefix else str(key)
            x, y = a.get(key), b.get(key)
            if isinstance(x, dict) and isinstance(y, dict):
                walk(x, y, path)
            elif x != y or (key in a) != (key in b):
                out[path] = (x, y)

    walk(before, after, "")
    return out


def grade_end_state(before, after, expected_diff, reply, must_say):
    """Grade one trial by what it changed, and what it told the customer.

    actual = db_diff(before, after). Compare it with expected_diff (values may be lists or tuples:
    compare them as (old, new) tuples). Return a dict:
      missing     sorted paths expected but not changed at all
      wrong       sorted paths changed, but not to the expected (old, new)
      unexpected  sorted paths changed that the task never mentioned (collateral damage)
      state_ok    True if all three lists are empty
      reply_ok    True if every string in must_say occurs in reply (ignore case)
      ok          state_ok and reply_ok
    """
    actual = db_diff(before, after)
    want = {p: tuple(v) for p, v in expected_diff.items()}
    missing = sorted(p for p in want if p not in actual)
    wrong = sorted(p for p in want if p in actual and tuple(actual[p]) != want[p])
    unexpected = sorted(p for p in actual if p not in want)
    state_ok = not (missing or wrong or unexpected)
    low = reply.lower()
    reply_ok = all(s.lower() in low for s in must_say)
    return {"missing": missing, "wrong": wrong, "unexpected": unexpected,
            "state_ok": state_ok, "reply_ok": reply_ok, "ok": state_ok and reply_ok}


# ----------------------------------------------------------------------------- milestone 2

def run_trial(task, agent, trial, start=START, max_steps=MAX_STEPS):
    """Run ONE trial of one task and grade it. Return a record dict:
      task, trial        the task id and the trial number
      passed             grade_end_state(...)["ok"] and the trial was not capped
      state_ok, reply_ok from the grade
      capped             True if the agent hit StepCapExceeded (its reply is then "")
      steps, calls       number of tool calls, and the list of tool names in order
      tokens_in, tokens_out, reply

    Steps: build a Shop on a deep copy of `start` (the trial must not touch `start` or any other trial);
    keep a deep copy as `before`; call agent.act(shop, task, trial_rng(task["id"], trial)); catch
    StepCapExceeded; grade the database that is left, whether or not the cap was hit.
    """
    env = Shop(copy.deepcopy(start), max_steps)
    before = copy.deepcopy(env.db)
    capped = False
    try:
        reply = agent.act(env, task, trial_rng(task["id"], trial))
    except StepCapExceeded:
        capped, reply = True, ""
    grade = grade_end_state(before, env.db, task["expected_diff"], reply, task["must_say"])
    return {"task": task["id"], "trial": trial, "passed": grade["ok"] and not capped,
            "state_ok": grade["state_ok"], "reply_ok": grade["reply_ok"], "capped": capped,
            "steps": len(env.transcript), "calls": [t["tool"] for t in env.transcript],
            "tokens_in": env.tokens_in, "tokens_out": env.tokens_out, "reply": reply}


# ----------------------------------------------------------------------------- milestone 3

def pass_at_k(n, c, k):
    """P(at least one of k trials succeeds), estimated from n recorded trials with c successes:
    1 - C(n - c, k) / C(n, k). Raise ValueError unless 1 <= k <= n and 0 <= c <= n."""
    if not (1 <= k <= n and 0 <= c <= n):
        raise ValueError(f"need 1 <= k <= n and 0 <= c <= n; got n={n}, c={c}, k={k}")
    return 1 - comb(n - c, k) / comb(n, k)


def pass_hat_k(n, c, k):
    """P(all k trials succeed), estimated from n recorded trials with c successes: C(c, k) / C(n, k).
    Same ValueError rule as pass_at_k."""
    raise NotImplementedError("TODO milestone 3: pass_hat_k")


def run_suite(tasks, agent, n_trials):
    """Run trials 0 .. n_trials-1 of every task. Return the records, task by task in the order of `tasks`,
    trials in increasing order."""
    return [run_trial(task, agent, t) for task in tasks for t in range(n_trials)]


def task_counts(records, task_ids):
    """[(c, n)] for each task id in the order given: c = trials passed, n = trials run.
    Raise ValueError if a task id has no records."""
    out = []
    for tid in task_ids:
        rs = [r for r in records if r["task"] == tid]
        if not rs:
            raise ValueError(f"no records for task {tid!r}")
        out.append((sum(r["passed"] for r in rs), len(rs)))
    return out


def never_passes(counts, task_ids):
    """Ids of the tasks with c == 0: nobody passed in any trial. These are the tasks to read FIRST,
    because a task that never passes is more often a broken task or a broken grader than a hard one."""
    return [tid for tid, (c, n) in zip(task_ids, counts) if c == 0]


def summarise(counts, ks=(1, 2, 4, 8)):
    """Average pass@k and pass^k over tasks, for each k in ks.
    Return {"pass_at": {k: mean}, "pass_hat": {k: mean}} (the means are over tasks, not over trials).
    Raise ValueError (via pass_at_k) if some task has fewer than k trials."""
    return {"pass_at": {k: sum(pass_at_k(n, c, k) for c, n in counts) / len(counts) for k in ks},
            "pass_hat": {k: sum(pass_hat_k(n, c, k) for c, n in counts) / len(counts) for k in ks}}


# ----------------------------------------------------------------------------- milestone 4

def trial_cost(rec, price_in=PRICE_IN, price_out=PRICE_OUT):
    """Dollars for one trial: tokens_in and tokens_out at the given prices per million tokens."""
    return (rec["tokens_in"] * price_in + rec["tokens_out"] * price_out) / 1_000_000


def cost_report(records):
    """Cost figures for a set of trials. Failures cost money too. Return a dict:
      attempts, successes   number of trials, number with passed True
      total                 sum of trial_cost over all trials
      per_attempt           total / attempts
      per_success           total / successes (None if there are no successes)
      p95                   the 95th-percentile trial cost, nearest-rank: sort the costs and take
                            the one at position ceil(0.95 * attempts) (1-based)
      max                   the largest trial cost
      capped                number of trials that hit the step cap
    Raise ValueError for an empty list."""
    if not records:
        raise ValueError("no records")
    costs = sorted(trial_cost(r) for r in records)
    total = sum(costs)
    successes = sum(r["passed"] for r in records)
    return {"attempts": len(records), "successes": successes, "total": total,
            "per_attempt": total / len(records), "per_success": total / successes if successes else None,
            "p95": costs[math.ceil(0.95 * len(costs)) - 1], "max": costs[-1],
            "capped": sum(r["capped"] for r in records)}


# ----------------------------------------------------------------------------- milestone 5

def bootstrap_ci(counts, stat, B=1000, alpha=0.05, seed=0):
    """Percentile bootstrap interval for stat(counts), resampling TASKS (each with all its trials).

    counts is a list of (c, n), one per task; stat maps such a list to a number. Each of the B
    repetitions draws len(counts) task indices with random.Random(seed).randrange and applies stat to
    the resampled list. Sort the B values xs; return (xs[int(alpha / 2 * B)], xs[int((1 - alpha / 2) * B) - 1]).
    """
    rng = random.Random(seed)
    n = len(counts)
    xs = sorted(stat([counts[rng.randrange(n)] for _ in range(n)]) for _ in range(B))
    return xs[int(alpha / 2 * B)], xs[int((1 - alpha / 2) * B) - 1]


def compare_agents(counts_a, counts_b, stat, B=1000, alpha=0.05, seed=0):
    """Paired comparison of two agents on the SAME tasks (counts_a[i] and counts_b[i] are task i).

    Each repetition draws one set of task indices and applies it to BOTH lists, then records
    stat(resampled b) - stat(resampled a). Return {"a": stat(counts_a), "b": stat(counts_b),
    "diff": b - a, "ci": (lo, hi) as in bootstrap_ci, "better": "b" if lo > 0, "a" if hi < 0, else None}.
    Raise ValueError if the lists differ in length or are empty.
    """
    if len(counts_a) != len(counts_b) or not counts_a:
        raise ValueError("need two non-empty lists with one entry per task")
    rng = random.Random(seed)
    n = len(counts_a)
    xs = []
    for _ in range(B):
        idx = [rng.randrange(n) for _ in range(n)]
        xs.append(stat([counts_b[i] for i in idx]) - stat([counts_a[i] for i in idx]))
    xs.sort()
    lo, hi = xs[int(alpha / 2 * B)], xs[int((1 - alpha / 2) * B) - 1]
    a, b = stat(counts_a), stat(counts_b)
    return {"a": a, "b": b, "diff": b - a, "ci": (lo, hi), "better": "b" if lo > 0 else "a" if hi < 0 else None}
