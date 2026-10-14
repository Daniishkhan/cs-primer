"""Lab 4: evaluate an agent (starter: your file).

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
    raise NotImplementedError("TODO milestone 1: db_diff")


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
    raise NotImplementedError("TODO milestone 1: grade_end_state")


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
    raise NotImplementedError("TODO milestone 2: run_trial")


# ----------------------------------------------------------------------------- milestone 3

def pass_at_k(n, c, k):
    """P(at least one of k trials succeeds), estimated from n recorded trials with c successes:
    1 - C(n - c, k) / C(n, k). Raise ValueError unless 1 <= k <= n and 0 <= c <= n."""
    raise NotImplementedError("TODO milestone 3: pass_at_k")


def pass_hat_k(n, c, k):
    """P(all k trials succeed), estimated from n recorded trials with c successes: C(c, k) / C(n, k).
    Same ValueError rule as pass_at_k."""
    raise NotImplementedError("TODO milestone 3: pass_hat_k")


def run_suite(tasks, agent, n_trials):
    """Run trials 0 .. n_trials-1 of every task. Return the records, task by task in the order of `tasks`,
    trials in increasing order."""
    raise NotImplementedError("TODO milestone 3: run_suite")


def task_counts(records, task_ids):
    """[(c, n)] for each task id in the order given: c = trials passed, n = trials run.
    Raise ValueError if a task id has no records."""
    raise NotImplementedError("TODO milestone 3: task_counts")


def never_passes(counts, task_ids):
    """Ids of the tasks with c == 0: nobody passed in any trial. These are the tasks to read FIRST,
    because a task that never passes is more often a broken task or a broken grader than a hard one."""
    raise NotImplementedError("TODO milestone 3: never_passes")


def summarise(counts, ks=(1, 2, 4, 8)):
    """Average pass@k and pass^k over tasks, for each k in ks.
    Return {"pass_at": {k: mean}, "pass_hat": {k: mean}} (the means are over tasks, not over trials).
    Raise ValueError (via pass_at_k) if some task has fewer than k trials."""
    raise NotImplementedError("TODO milestone 3: summarise")


# ----------------------------------------------------------------------------- milestone 4

def trial_cost(rec, price_in=PRICE_IN, price_out=PRICE_OUT):
    """Dollars for one trial: tokens_in and tokens_out at the given prices per million tokens."""
    raise NotImplementedError("TODO milestone 4: trial_cost")


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
    raise NotImplementedError("TODO milestone 4: cost_report")


# ----------------------------------------------------------------------------- milestone 5

def bootstrap_ci(counts, stat, B=1000, alpha=0.05, seed=0):
    """Percentile bootstrap interval for stat(counts), resampling TASKS (each with all its trials).

    counts is a list of (c, n), one per task; stat maps such a list to a number. Each of the B
    repetitions draws len(counts) task indices with random.Random(seed).randrange and applies stat to
    the resampled list. Sort the B values xs; return (xs[int(alpha / 2 * B)], xs[int((1 - alpha / 2) * B) - 1]).
    """
    raise NotImplementedError("TODO milestone 5: bootstrap_ci")


def compare_agents(counts_a, counts_b, stat, B=1000, alpha=0.05, seed=0):
    """Paired comparison of two agents on the SAME tasks (counts_a[i] and counts_b[i] are task i).

    Each repetition draws one set of task indices and applies it to BOTH lists, then records
    stat(resampled b) - stat(resampled a). Return {"a": stat(counts_a), "b": stat(counts_b),
    "diff": b - a, "ci": (lo, hi) as in bootstrap_ci, "better": "b" if lo > 0, "a" if hi < 0, else None}.
    Raise ValueError if the lists differ in length or are empty.
    """
    raise NotImplementedError("TODO milestone 5: compare_agents")
