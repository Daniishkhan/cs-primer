"""Lab 1: The Level-1 Checker.

Pure Python, standard library only. Reads the run logs of a self-improvement
loop (one JSON object per line) and decides, condition by condition, whether
the loop meets Weco's four Level-1 conditions:

    1  a fair baseline: same budget, same attempts, and the improver beats it
    2  a sustained trend: several real accepts, not one lucky jump
    3  generalisation: a paired gain on tasks the search never touched
    4  a fixed budget: stated before the first step and never exceeded

    python3 starter.py logs/improver_good.jsonl logs/baseline_fair.jsonl

Milestones: 1 parse_log, 2 fair_baseline, 3 sustained_trend,
4 generalisation, 5 budget_ok and report_card, 6 automation_level.
"""
import json
import math
import statistics
import sys
from dataclasses import dataclass, field


# =============================================================================
# GIVEN: the data model and the rules of this lab
# =============================================================================
class LogError(ValueError):
    """A log line that cannot be used. The message starts with 'line N:'."""


@dataclass
class Step:
    step: int                 # 1, 2, 3 ... within the run
    cost_usd: float           # money spent on this attempt
    search_score: float       # the candidate's score on the search split
    accepted: bool            # did the loop keep it?
    incumbent: float          # best kept search score after this step


@dataclass
class Eval:
    stage: str                # "initial" (before search) or "final"
    task: str                 # a task id
    seed: int
    score: float


@dataclass
class Run:
    run_id: str
    arm: str                  # "improver" or "baseline"
    budget_usd: float         # the budget stated in the header
    max_attempts: int         # the attempts the run was allowed
    noise_floor: float        # the smallest gain that counts as real
    search_tasks: list        # task ids the loop searched on
    steps: list = field(default_factory=list)
    evals: list = field(default_factory=list)


@dataclass
class Verdict:
    passed: bool
    reason: str               # one sentence, with the numbers


MIN_ACCEPTS = 3               # real accepts a "sustained" trend needs
MAX_SHARE = 0.5               # no single accept may carry more than this
MIN_PAIRS = 3                 # held-out tasks needed for a paired test
MIN_GAIN = 0.02               # smallest held-out gain worth reporting
T95 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447,
       7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228}   # two-sided 95%, df 1..10
HEADER_KEYS = ("run_id", "arm", "budget_usd", "max_attempts",
               "noise_floor", "search_tasks")


# =============================================================================
# Milestone 1: parse the run log
# =============================================================================
def parse_log(text):
    """Parse JSONL text into a list of Run objects, in header order.

    Each line is a JSON object with a "type": "run" (the header, which
    must come first for its run_id), "step" or "eval". Blank lines are
    skipped. Raise LogError whose message starts "line N:" (N from 1) for
    invalid JSON, a line with no type, an unknown type, a header missing
    any of HEADER_KEYS, a step or eval whose run_id has no header yet, or
    a step or eval missing a field.
    """
    raise NotImplementedError("TODO milestone 1: parse_log")


# =============================================================================
# helpers shared by milestones 2 to 4
# =============================================================================
def task_means(run, stage):
    """{task: mean score over seeds} for one stage of a run's evals."""
    by_task = {}
    for e in run.evals:
        if e.stage == stage:
            by_task.setdefault(e.task, []).append(e.score)
    return {t: statistics.fmean(v) for t, v in by_task.items()}


def heldout_tasks(run):
    """Tasks evaluated that are not in the run's search tasks."""
    return sorted(set(e.task for e in run.evals) - set(run.search_tasks))


def paired_gain(run):
    """(mean gain, 95% half-width, n) over held-out tasks, final - initial.

    Average the seeds within each held-out task first (task_means), take
    the final minus initial difference per task, and treat the n tasks as
    the sample: half-width = t * standard error, with t from T95 at
    n - 1 degrees of freedom (2.0 beyond the table). With n < 2 the half
    width is math.inf.
    """
    raise NotImplementedError("TODO milestone 4: paired_gain")


# =============================================================================
# Milestone 2: a fair baseline
# =============================================================================
def fair_baseline(improver, baseline):
    """Condition 1. Return a Verdict; check these in order.

    1. declared budget_usd equal (else "budgets differ ...")
    2. declared max_attempts equal (else "attempts differ ...")
    3. the baseline used at least 80% of its attempts (len(steps))
    4. the improver's mean final score over tasks beats the baseline's
       (task_means(run, "final"), then the mean of those means); the
       reason of a loss contains "does not beat"
    """
    raise NotImplementedError("TODO milestone 2: fair_baseline")


# =============================================================================
# Milestone 3: a sustained trend
# =============================================================================
def real_gains(run):
    """Gains of the accepted steps that beat the run's noise floor.

    A step's gain is its incumbent minus the previous step's incumbent.
    Step 1 has no previous incumbent, so it never counts. Only accepted
    steps whose gain is strictly above run.noise_floor are returned.
    """
    raise NotImplementedError("TODO milestone 3: real_gains")


def sustained_trend(run):
    """Condition 2. Need MIN_ACCEPTS real gains, and the largest must be
    at most MAX_SHARE of their sum. The reason for too few contains
    "real accept"; the reason for a lucky jump contains "lucky".
    """
    raise NotImplementedError("TODO milestone 3: sustained_trend")


# =============================================================================
# Milestone 4: generalisation
# =============================================================================
def generalisation(run):
    """Condition 3. Check in order: a task both in run.search_tasks and
    among the evals is leaked (reason contains "used in search"; if no
    held-out task remains, the reason contains "no held-out tasks");
    fewer than MIN_PAIRS tasks fails ("need"); then the gain must be at
    least MIN_GAIN and its interval (gain - half) must stay above zero.
    """
    raise NotImplementedError("TODO milestone 4: generalisation")


# =============================================================================
# Milestone 5: the budget, and the report card
# =============================================================================
def budget_ok(run):
    """Condition 4. Add up cost_usd step by step; the first step whose
    running total passes budget_usd fails, naming that step ("exceeded at
    step N"). Then len(steps) must not pass max_attempts.
    """
    raise NotImplementedError("TODO milestone 5: budget_ok")


CONDITIONS = ("fair baseline", "sustained trend", "generalisation",
              "fixed budget")


def report_card(improver, baseline):
    """{condition: Verdict} for the four conditions, in CONDITIONS order.

    Condition 1 compares improver with baseline; 2 to 4 judge the improver.
    """
    raise NotImplementedError("TODO milestone 5: report_card")


def render(card):
    """The card as text: one line per condition, "  PASS  name ... reason"
    or "  FAIL ...", then "  Level 1: met" if all four pass, else
    "  Level 1: NOT met".
    """
    raise NotImplementedError("TODO milestone 5: render")


# =============================================================================
# Milestone 6: an automation level from a task rubric
# =============================================================================
LEVEL_NAMES = ["not used", "marginal", "assists", "collaborates", "leads",
               "autonomous"]


def task_level(ai_used, ai_share, human_role):
    """Epoch-style 0 to 5 level of one task.

    human_role is "none", "approves", "directs" or "drives".
    not ai_used -> 0;  "none" -> 5;
    "approves": 4 if ai_share >= 0.5 else 3;
    "directs":  3 if ai_share >= 0.5 else 2;
    "drives":   2 if ai_share >= 0.2 else 1.
    """
    raise NotImplementedError("TODO milestone 6: task_level")


def automation_level(tasks):
    """tasks: list of dicts with name, ai_used, ai_share, human_role.

    Returns (levels, mean, weakest): per-task levels, their mean, and the
    name of the lowest-level task, the human bottleneck of the loop.
    """
    raise NotImplementedError("TODO milestone 6: automation_level")


# =============================================================================
# GIVEN: command line
# =============================================================================
def main(argv):
    if len(argv) != 2:
        print("usage: python3 starter.py IMPROVER.jsonl BASELINE.jsonl")
        return 2
    runs = [parse_log(open(p).read()) for p in argv]
    print(render(report_card(runs[0][0], runs[1][0])))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
