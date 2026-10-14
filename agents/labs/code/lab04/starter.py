"""Lab 4 starter: Workflow Patterns & Budgets.  THIS IS YOUR FILE.

Given: the prompts, the (assumed) price and latency tables, the result dataclasses, Budget and
BudgetExceeded, and BudgetedMeter.ask. fixtures.py holds the world: tickets, orders and the
deterministic stand-in model. Every function you write raises NotImplementedError until you
replace it. Work in order; run

    python3 check.py            # checks this file
    python3 check.py 3          # only milestone 3

  1. call_cost, call_seconds, Meter (ask, fan_out, totals, by_step)   the meter: tokens, dollars, time
  2. chain, chain_outcomes                                            a chain with gates
  3. classify, route, evaluate_router, pick_threshold                 a router and its threshold
  4. section, majority, vote, majority_accuracy, evaluate_voting      parallel fan-out and voting
  5. BudgetedMeter.check_budget, plan, orchestrate                    orchestrator-workers, with limits
  6. process_ticket, percentile, run_desk                             the whole desk, per-ticket budgets

Standard library only. llm.py is the shared stand-in model module; do not edit it.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from fixtures import ORDERS, make_model
from llm import text_of

# =============================================================================
# Given: prompts, prices and the shape of the results
# =============================================================================
# The stand-in model reads the first word of the system prompt to know which step is calling.
SYSTEM_EXTRACT = 'EXTRACT the order id and the issue from the customer message. Reply as JSON: {"order_id": ..., "issue": ...}.'
SYSTEM_DRAFT = "DRAFT a short, polite reply to the customer using only the FACTS given. Mention the order id."
SYSTEM_CLASSIFY = "CLASSIFY the message as refund, account, tracking or other. Reply as label|confidence."
HANDLER_SYSTEMS = {
    "refund": "HANDLE-refund: you are the refunds specialist. Be careful with money.",
    "account": "HANDLE-account: you are the account-access specialist.",
    "tracking": "HANDLE-tracking: you are the delivery-tracking specialist.",
}
ROUTES = {"refund": "large", "account": "small", "tracking": "small"}     # label -> model tier
CHECK_SYSTEMS = {
    "pii": "CHECK-pii: does the text contain personal data that should not be repeated? Reply ok or flag: reason.",
    "tone": "CHECK-tone: is the text rude or aggressive? Reply ok or flag: reason.",
    "policy": "CHECK-policy: does the text raise a legal or policy matter? Reply ok or flag: reason.",
}
SYSTEM_PLAN = "PLAN split the request into independent subtasks. Reply as a JSON list of {\"task\": ..., \"city\": ...}."
SYSTEM_WORK = "WORK answer one subtask in one line."
SYSTEM_SYNTH = "SYNTH combine the findings into one short answer."


def judge_system(k: int) -> str:
    return f"JUDGE-{k}: decide whether this ticket needs a human. Answer yes or no."


# ASSUMED, illustrative prices in US dollars per million tokens (input, output). Real prices
# differ by vendor and change often; the lab only needs two tiers with a large gap between them.
PRICES = {"small": (0.25, 1.25), "large": (3.00, 15.00)}
# ASSUMED simulated latency per call in seconds: (fixed overhead, per input token, per output token).
LATENCY = {"small": (0.3, 0.0002, 0.01), "large": (0.8, 0.0005, 0.03)}


@dataclass
class Call:
    step: str
    tier: str
    tokens_in: int
    tokens_out: int
    seconds: float
    cost_usd: float


@dataclass
class Outcome:
    status: str                      # "ok", "gate1" or "gate2"
    reply: Optional[str]
    reason: str


@dataclass
class Routed:
    label: str
    confidence: float
    destination: str                 # the label, or "human"
    reply: Optional[str]


@dataclass
class Orchestration:
    answer: str
    planned: int                     # subtasks the plan contained
    ran: int                         # subtasks whose worker finished
    dropped: List[Dict[str, str]]    # [{"task": ..., "reason": "limit" | "budget"}], in plan order


@dataclass
class Budget:
    max_calls: Optional[int] = None
    max_tokens: Optional[int] = None       # input + output
    max_usd: Optional[float] = None


class BudgetExceeded(Exception):
    def __init__(self, reason: str):
        super().__init__(f"budget exhausted: {reason}")
        self.reason = reason                # "calls", "tokens" or "usd"


@dataclass
class TicketResult:
    ticket_id: str
    status: str                      # "answered" or "human"
    reason: str
    calls: int
    tokens: int
    cost_usd: float
    seconds: float


# =============================================================================
# Milestone 1: the meter
# =============================================================================
def call_cost(tier: str, tokens_in: int, tokens_out: int) -> float:
    """Dollars for one call: (tokens_in x input price + tokens_out x output price) / 1,000,000."""
    raise NotImplementedError("TODO milestone 1: call_cost")


def call_seconds(tier: str, tokens_in: int, tokens_out: int) -> float:
    """Simulated seconds for one call: overhead + tokens_in x per-input + tokens_out x per-output."""
    raise NotImplementedError("TODO milestone 1: call_seconds")


class Meter:
    """Wraps a model so that every call is recorded, and keeps a simulated clock."""

    def __init__(self, model):
        self.model = model
        self.calls: List[Call] = []
        self.clock = 0.0                     # simulated seconds elapsed on the critical path

    def ask(self, step: str, system: str, user: str, tier: str = "small") -> str:
        """One model call with `user` as the only message. Record a Call from the response's usage,
        advance the clock by the call's seconds, and return the reply text."""
        raise NotImplementedError("TODO milestone 1: Meter.ask")

    def fan_out(self, thunks: List[Callable[[], Any]]) -> List[Any]:
        """Run the thunks as if in parallel and return their results in order.

        They run one after another in this simulation, but each starts at the same clock reading,
        and afterwards the clock stands at the latest finish time among them: the slowest branch
        sets the wait. An empty list leaves the clock alone.
        """
        raise NotImplementedError("TODO milestone 1: Meter.fan_out")

    def totals(self) -> Dict[str, Any]:
        """calls, tokens_in, tokens_out, cost_usd, seconds (the clock: wall time on the critical path)
        and work_seconds (the sum of every call's seconds: what you would wait with no parallelism)."""
        raise NotImplementedError("TODO milestone 1: Meter.totals")

    def by_step(self) -> Dict[str, Dict[str, Any]]:
        """Per step name, in first-seen order: calls, tokens_in, tokens_out, cost_usd."""
        raise NotImplementedError("TODO milestone 1: Meter.by_step")


# =============================================================================
# Milestone 2: a chain with gates
# =============================================================================
def chain(meter: Meter, ticket_text: str) -> Outcome:
    """extract (model) -> gate 1 -> lookup (plain code) -> draft (model) -> gate 2.

    1. ask("extract", SYSTEM_EXTRACT, ticket_text); the reply is JSON with "order_id" and "issue".
       Not valid JSON: Outcome("gate1", None, "extract was not valid JSON").
    2. Gate 1: the order_id must be a key of ORDERS, else Outcome("gate1", None, "no valid order id").
       No further model call is made.
    3. facts = dict(ORDERS[order_id], order_id=order_id); then
       ask("draft", SYSTEM_DRAFT, "FACTS:" + json.dumps(facts, sort_keys=True)).
    4. Gate 2: the reply must contain the order id and have at most 40 words,
       else Outcome("gate2", None, "draft rejected").
    5. Outcome("ok", reply, "ok").
    """
    raise NotImplementedError("TODO milestone 2: chain")


def chain_outcomes(p_step: float, n_steps: int, catch: float) -> Dict[str, float]:
    """What happens to a chain of n independent steps, each right with probability p_step,
    when a gate after each step stops the chain on a fraction `catch` of the wrong outputs.

    Returns probabilities that sum to 1:
      "correct"  every step was right,
      "detected" some wrong output was caught by a gate (the chain stopped, loudly),
      "silent"   the chain finished but at least one wrong output slipped through.
    """
    raise NotImplementedError("TODO milestone 2: chain_outcomes")


# =============================================================================
# Milestone 3: a router with a threshold
# =============================================================================
def classify(meter: Meter, text: str) -> Tuple[str, float]:
    """One small call: ask("classify", SYSTEM_CLASSIFY, text) replies 'label|confidence'.
    Return (label, confidence as a float); a malformed reply is ("other", 0.0)."""
    raise NotImplementedError("TODO milestone 3: classify")


def route(meter: Meter, text: str, threshold: float = 0.7, tier_override: Optional[str] = None) -> Routed:
    """Classify, then either hand the ticket to a specialist or to a human.

    A label that is not in ROUTES, or a confidence below `threshold`, goes to "human" with no reply
    and no further call. Otherwise ask("handle", HANDLER_SYSTEMS[label], text, tier=...) with the
    tier ROUTES gives for that label (or `tier_override` when it is not None).
    """
    raise NotImplementedError("TODO milestone 3: route")


def evaluate_router(tickets: List[Dict[str, Any]], threshold: float = 0.7, tier_override: Optional[str] = None) -> Dict[str, Any]:
    """Route every ticket through one Meter(make_model()) and score the result against the labels.

    Returns: threshold, n, auto (tickets not sent to a human), auto_rate = auto / n,
    misrouted (auto tickets whose destination differs from the true intent),
    misroute_rate = misrouted / n, plus the meter's calls, tokens (in + out) and cost_usd.
    """
    raise NotImplementedError("TODO milestone 3: evaluate_router")


def pick_threshold(rows: List[Dict[str, Any]], max_misroute_rate: float) -> float:
    """From evaluate_router rows, the threshold with the highest auto_rate among those whose
    misroute_rate is at most the cap; ties go to the HIGHER threshold. No row qualifies: ValueError."""
    raise NotImplementedError("TODO milestone 3: pick_threshold")


# =============================================================================
# Milestone 4: parallel fan-out, sectioning and voting
# =============================================================================
def section(meter: Meter, text: str, parallel: bool = True) -> Dict[str, str]:
    """Run the three independent checks of CHECK_SYSTEMS (pii, tone, policy, in that order) on `text`.

    Each is ask("check-<name>", CHECK_SYSTEMS[name], text). With parallel=True they run inside
    meter.fan_out; with parallel=False one after another. Return {name: reply}.
    """
    raise NotImplementedError("TODO milestone 4: section")


def majority(votes: List[str]) -> str:
    """The most common vote. A tie goes to the vote that appeared first. Empty: ValueError."""
    raise NotImplementedError("TODO milestone 4: majority")


def vote(meter: Meter, text: str, n: int, tier: str = "small") -> Tuple[str, List[str]]:
    """Ask n judges (k = 0 .. n-1) at once: inside fan_out, ask("judge", judge_system(k), text, tier).
    Return (majority label, the list of votes in judge order)."""
    raise NotImplementedError("TODO milestone 4: vote")


def majority_accuracy(p: float, n: int) -> float:
    """Chance that a majority of n independent judges, each right with probability p, is right.
    n must be odd (ValueError otherwise)."""
    raise NotImplementedError("TODO milestone 4: majority_accuracy")


def evaluate_voting(items: List[Dict[str, Any]], n: int) -> Dict[str, Any]:
    """Run vote(...) with n judges on every item (one Meter(make_model()) for all) and score the
    majorities against item["truth"]. Returns n, accuracy, calls, tokens (in + out), cost_usd, seconds."""
    raise NotImplementedError("TODO milestone 4: evaluate_voting")


# =============================================================================
# Milestone 5: budgets, and an orchestrator that cannot be talked past its limits
# =============================================================================
class BudgetedMeter(Meter):
    """A Meter that refuses to make a call once a limit has been reached."""

    def __init__(self, model, budget: Budget):
        super().__init__(model)
        self.budget = budget

    def check_budget(self) -> None:
        """Raise BudgetExceeded("calls"), ("tokens") or ("usd") (checked in that order) if the calls
        made so far have already REACHED a limit that is not None: calls >= max_calls,
        tokens_in + tokens_out >= max_tokens, cost >= max_usd. Otherwise return."""
        raise NotImplementedError("TODO milestone 5: BudgetedMeter.check_budget")

    def ask(self, step: str, system: str, user: str, tier: str = "small") -> str:
        self.check_budget()                      # given: the check happens before every call
        return super().ask(step, system, user, tier)


def plan(meter: Meter, request: str) -> List[Dict[str, str]]:
    """ask("plan", SYSTEM_PLAN, request, tier="large"); the reply is a JSON list of subtasks
    ({"task": ..., "city": ...}). Not valid JSON, or not a list: return []."""
    raise NotImplementedError("TODO milestone 5: plan")


def orchestrate(meter: Meter, request: str, max_subtasks: int = 6) -> Orchestration:
    """Plan, fan out one worker per subtask, synthesise, and say what was left out.

    1. tasks = plan(...). None: Orchestration("No subtasks found for this request.", 0, 0, []).
    2. Only the first `max_subtasks` run; the rest are dropped with reason "limit".
    3. Workers run inside meter.fan_out: ask("worker", SYSTEM_WORK, task["task"]) at tier "small".
       A worker that raises BudgetExceeded is dropped with reason "budget" (the others carry on).
       (A BudgetExceeded from the plan call itself is not caught here.)
    4. No worker finished: answer "No subtask finished: budget exhausted.". Otherwise
       ask("synth", SYSTEM_SYNTH, "\\n".join(results), tier="large"); if that raises BudgetExceeded the
       answer is "Budget reached before synthesis: " + "; ".join(results) + ".".
    5. If anything was dropped, append " Not covered: " + ", ".join(dropped task texts) + "."
    `dropped` lists the dropped subtasks in plan order; `ran` counts finished workers.
    """
    raise NotImplementedError("TODO milestone 5: orchestrate")


# =============================================================================
# Milestone 6: the whole desk, with per-ticket budgets
# =============================================================================
def process_ticket(ticket: Dict[str, Any], model, threshold: float = 0.7, budget: Optional[Budget] = None) -> TicketResult:
    """Handle one ticket with a BudgetedMeter(model, budget or Budget()).

    classify first. A label not in ROUTES or a confidence below `threshold`: status "human",
    reason "router". Label "tracking": run chain(...): "answered" if it returned "ok", else "human"
    with reason "gate: " + the Outcome's reason. Other labels: one ask("handle", ...) at the ROUTES
    tier, status "answered", reason "ok". BudgetExceeded anywhere: status "human", reason "budget: <which>".
    The result carries the meter's calls, tokens (in + out), cost_usd and seconds.
    """
    raise NotImplementedError("TODO milestone 6: process_ticket")


def percentile(values: List[float], q: float) -> float:
    """Nearest-rank percentile, 0 < q <= 100: sort, take the value at 1-based rank ceil(q/100 x n).
    percentile([1..10], 50) is 5 and (.., 95) is 10. Empty list or q out of range: ValueError."""
    raise NotImplementedError("TODO milestone 6: percentile")


def run_desk(tickets: List[Dict[str, Any]], threshold: float = 0.7, budget: Optional[Budget] = None) -> Dict[str, Any]:
    """Process every ticket (one shared make_model(), a fresh budget per ticket) and summarise:
    results (list of TicketResult), answered, human, reasons ({reason: count}), tokens_total,
    cost_usd (sum), p50_tokens and p95_tokens (percentile of per-ticket tokens)."""
    raise NotImplementedError("TODO milestone 6: run_desk")
