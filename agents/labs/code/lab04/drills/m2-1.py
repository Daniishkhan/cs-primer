# Drill: A4 Lab 4, milestone 2 of 6: a chain with gates (step 1 of 2)
# Everything else in this file is already written. Fill in:
#     chain
# Check it with: python3 check.py 2

"""Lab 4 solution: workflow patterns and budgets.

A support desk built from four workflow patterns (chain with gates, router, parallel fan-out,
orchestrator-workers) over a deterministic stand-in model, with every call metered: tokens,
dollars (at ASSUMED prices) and simulated seconds. Standard library only.
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
    pin, pout = PRICES[tier]
    return (tokens_in * pin + tokens_out * pout) / 1_000_000


def call_seconds(tier: str, tokens_in: int, tokens_out: int) -> float:
    """Simulated seconds for one call: overhead + tokens_in x per-input + tokens_out x per-output."""
    base, per_in, per_out = LATENCY[tier]
    return base + tokens_in * per_in + tokens_out * per_out


class Meter:
    """Wraps a model so that every call is recorded, and keeps a simulated clock."""

    def __init__(self, model):
        self.model = model
        self.calls: List[Call] = []
        self.clock = 0.0                     # simulated seconds elapsed on the critical path

    def ask(self, step: str, system: str, user: str, tier: str = "small") -> str:
        """One model call with `user` as the only message. Record a Call from the response's usage,
        advance the clock by the call's seconds, and return the reply text."""
        r = self.model.complete([{"role": "user", "content": user}], system=system)
        tin, tout = r.usage["input_tokens"], r.usage["output_tokens"]
        secs = call_seconds(tier, tin, tout)
        self.calls.append(Call(step, tier, tin, tout, secs, call_cost(tier, tin, tout)))
        self.clock += secs
        return text_of(r)

    def fan_out(self, thunks: List[Callable[[], Any]]) -> List[Any]:
        """Run the thunks as if in parallel and return their results in order.

        They run one after another in this simulation, but each starts at the same clock reading,
        and afterwards the clock stands at the latest finish time among them: the slowest branch
        sets the wait. An empty list leaves the clock alone.
        """
        start, ends, results = self.clock, [], []
        for thunk in thunks:
            self.clock = start
            results.append(thunk())
            ends.append(self.clock)
        self.clock = max(ends, default=start)
        return results

    def totals(self) -> Dict[str, Any]:
        """calls, tokens_in, tokens_out, cost_usd, seconds (the clock: wall time on the critical path)
        and work_seconds (the sum of every call's seconds: what you would wait with no parallelism)."""
        return {"calls": len(self.calls), "tokens_in": sum(c.tokens_in for c in self.calls),
                "tokens_out": sum(c.tokens_out for c in self.calls),
                "cost_usd": sum(c.cost_usd for c in self.calls), "seconds": self.clock,
                "work_seconds": sum(c.seconds for c in self.calls)}

    def by_step(self) -> Dict[str, Dict[str, Any]]:
        """Per step name, in first-seen order: calls, tokens_in, tokens_out, cost_usd."""
        out: Dict[str, Dict[str, Any]] = {}
        for c in self.calls:
            row = out.setdefault(c.step, {"calls": 0, "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0})
            row["calls"] += 1
            row["tokens_in"] += c.tokens_in
            row["tokens_out"] += c.tokens_out
            row["cost_usd"] += c.cost_usd
        return out


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
    correct = p_step ** n_steps
    survives = (p_step + (1 - p_step) * (1 - catch)) ** n_steps      # nothing was caught
    return {"correct": correct, "detected": 1 - survives, "silent": survives - correct}


# =============================================================================
# Milestone 3: a router with a threshold
# =============================================================================
def classify(meter: Meter, text: str) -> Tuple[str, float]:
    """One small call: ask("classify", SYSTEM_CLASSIFY, text) replies 'label|confidence'.
    Return (label, confidence as a float); a malformed reply is ("other", 0.0)."""
    raw = meter.ask("classify", SYSTEM_CLASSIFY, text)
    try:
        label, conf = raw.split("|")
        return label.strip(), float(conf)
    except ValueError:
        return "other", 0.0


def route(meter: Meter, text: str, threshold: float = 0.7, tier_override: Optional[str] = None) -> Routed:
    """Classify, then either hand the ticket to a specialist or to a human.

    A label that is not in ROUTES, or a confidence below `threshold`, goes to "human" with no reply
    and no further call. Otherwise ask("handle", HANDLER_SYSTEMS[label], text, tier=...) with the
    tier ROUTES gives for that label (or `tier_override` when it is not None).
    """
    label, conf = classify(meter, text)
    if label not in ROUTES or conf < threshold:
        return Routed(label, conf, "human", None)
    tier = tier_override or ROUTES[label]
    return Routed(label, conf, label, meter.ask("handle", HANDLER_SYSTEMS[label], text, tier=tier))


def evaluate_router(tickets: List[Dict[str, Any]], threshold: float = 0.7, tier_override: Optional[str] = None) -> Dict[str, Any]:
    """Route every ticket through one Meter(make_model()) and score the result against the labels.

    Returns: threshold, n, auto (tickets not sent to a human), auto_rate = auto / n,
    misrouted (auto tickets whose destination differs from the true intent),
    misroute_rate = misrouted / n, plus the meter's calls, tokens (in + out) and cost_usd.
    """
    meter = Meter(make_model())
    auto = misrouted = 0
    for t in tickets:
        r = route(meter, t["text"], threshold, tier_override)
        if r.destination != "human":
            auto += 1
            misrouted += r.destination != t["intent"]
    tot, n = meter.totals(), len(tickets)
    return {"threshold": threshold, "n": n, "auto": auto, "auto_rate": auto / n, "misrouted": misrouted,
            "misroute_rate": misrouted / n, "calls": tot["calls"], "tokens": tot["tokens_in"] + tot["tokens_out"],
            "cost_usd": tot["cost_usd"]}


def pick_threshold(rows: List[Dict[str, Any]], max_misroute_rate: float) -> float:
    """From evaluate_router rows, the threshold with the highest auto_rate among those whose
    misroute_rate is at most the cap; ties go to the HIGHER threshold. No row qualifies: ValueError."""
    ok = [r for r in rows if r["misroute_rate"] <= max_misroute_rate]
    if not ok:
        raise ValueError(f"no threshold keeps misrouting at or below {max_misroute_rate}")
    return max(ok, key=lambda r: (r["auto_rate"], r["threshold"]))["threshold"]


# =============================================================================
# Milestone 4: parallel fan-out, sectioning and voting
# =============================================================================
def section(meter: Meter, text: str, parallel: bool = True) -> Dict[str, str]:
    """Run the three independent checks of CHECK_SYSTEMS (pii, tone, policy, in that order) on `text`.

    Each is ask("check-<name>", CHECK_SYSTEMS[name], text). With parallel=True they run inside
    meter.fan_out; with parallel=False one after another. Return {name: reply}.
    """
    names = list(CHECK_SYSTEMS)
    thunks = [lambda n=n: meter.ask("check-" + n, CHECK_SYSTEMS[n], text) for n in names]
    replies = meter.fan_out(thunks) if parallel else [t() for t in thunks]
    return dict(zip(names, replies))


def majority(votes: List[str]) -> str:
    """The most common vote. A tie goes to the vote that appeared first. Empty: ValueError."""
    if not votes:
        raise ValueError("no votes")
    counts: Dict[str, int] = {}
    for v in votes:
        counts[v] = counts.get(v, 0) + 1
    best = max(counts.values())
    return next(v for v in votes if counts[v] == best)


def vote(meter: Meter, text: str, n: int, tier: str = "small") -> Tuple[str, List[str]]:
    """Ask n judges (k = 0 .. n-1) at once: inside fan_out, ask("judge", judge_system(k), text, tier).
    Return (majority label, the list of votes in judge order)."""
    votes = meter.fan_out([lambda k=k: meter.ask("judge", judge_system(k), text, tier=tier).strip() for k in range(n)])
    return majority(votes), votes


def majority_accuracy(p: float, n: int) -> float:
    """Chance that a majority of n independent judges, each right with probability p, is right.
    n must be odd (ValueError otherwise)."""
    if n % 2 == 0:
        raise ValueError("n must be odd so there are no ties")
    return sum(math.comb(n, k) * p ** k * (1 - p) ** (n - k) for k in range(n // 2 + 1, n + 1))


def evaluate_voting(items: List[Dict[str, Any]], n: int) -> Dict[str, Any]:
    """Run vote(...) with n judges on every item (one Meter(make_model()) for all) and score the
    majorities against item["truth"]. Returns n, accuracy, calls, tokens (in + out), cost_usd, seconds."""
    meter = Meter(make_model())
    right = sum(vote(meter, it["text"], n)[0] == it["truth"] for it in items)
    tot = meter.totals()
    return {"n": n, "accuracy": right / len(items), "calls": tot["calls"],
            "tokens": tot["tokens_in"] + tot["tokens_out"], "cost_usd": tot["cost_usd"], "seconds": tot["seconds"]}


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
        b, t = self.budget, self.totals()
        if b.max_calls is not None and t["calls"] >= b.max_calls:
            raise BudgetExceeded("calls")
        if b.max_tokens is not None and t["tokens_in"] + t["tokens_out"] >= b.max_tokens:
            raise BudgetExceeded("tokens")
        if b.max_usd is not None and t["cost_usd"] >= b.max_usd:
            raise BudgetExceeded("usd")

    def ask(self, step: str, system: str, user: str, tier: str = "small") -> str:
        self.check_budget()                      # given: the check happens before every call
        return super().ask(step, system, user, tier)


def plan(meter: Meter, request: str) -> List[Dict[str, str]]:
    """ask("plan", SYSTEM_PLAN, request, tier="large"); the reply is a JSON list of subtasks
    ({"task": ..., "city": ...}). Not valid JSON, or not a list: return []."""
    try:
        tasks = json.loads(meter.ask("plan", SYSTEM_PLAN, request, tier="large"))
    except ValueError:
        return []
    return tasks if isinstance(tasks, list) else []


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
    tasks = plan(meter, request)
    if not tasks:
        return Orchestration("No subtasks found for this request.", 0, 0, [])
    runnable = tasks[:max_subtasks]

    def worker(t):
        try:
            return meter.ask("worker", SYSTEM_WORK, t["task"], tier="small")
        except BudgetExceeded:
            return None

    outputs = meter.fan_out([lambda t=t: worker(t) for t in runnable]) + [None] * (len(tasks) - len(runnable))
    results = [o for o in outputs if o is not None]
    dropped = []
    for i, (t, o) in enumerate(zip(tasks, outputs)):
        if i >= max_subtasks:
            dropped.append({"task": t["task"], "reason": "limit"})
        elif o is None:
            dropped.append({"task": t["task"], "reason": "budget"})
    if not results:
        answer = "No subtask finished: budget exhausted."
    else:
        try:
            answer = meter.ask("synth", SYSTEM_SYNTH, "\n".join(results), tier="large")
        except BudgetExceeded:
            answer = "Budget reached before synthesis: " + "; ".join(results) + "."
    if dropped:
        answer += " Not covered: " + ", ".join(d["task"] for d in dropped) + "."
    return Orchestration(answer, len(tasks), len(results), dropped)


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
    meter = BudgetedMeter(model, budget or Budget())
    status, reason = "answered", "ok"
    try:
        label, conf = classify(meter, ticket["text"])
        if label not in ROUTES or conf < threshold:
            status, reason = "human", "router"
        elif label == "tracking":
            out = chain(meter, ticket["text"])
            if out.status != "ok":
                status, reason = "human", "gate: " + out.reason
        else:
            meter.ask("handle", HANDLER_SYSTEMS[label], ticket["text"], tier=ROUTES[label])
    except BudgetExceeded as e:
        status, reason = "human", f"budget: {e.reason}"
    t = meter.totals()
    return TicketResult(ticket["id"], status, reason, t["calls"], t["tokens_in"] + t["tokens_out"], t["cost_usd"], t["seconds"])


def percentile(values: List[float], q: float) -> float:
    """Nearest-rank percentile, 0 < q <= 100: sort, take the value at 1-based rank ceil(q/100 x n).
    percentile([1..10], 50) is 5 and (.., 95) is 10. Empty list or q out of range: ValueError."""
    if not values or not 0 < q <= 100:
        raise ValueError("need values and 0 < q <= 100")
    s = sorted(values)
    return s[math.ceil(q / 100 * len(s)) - 1]


def run_desk(tickets: List[Dict[str, Any]], threshold: float = 0.7, budget: Optional[Budget] = None) -> Dict[str, Any]:
    """Process every ticket (one shared make_model(), a fresh budget per ticket) and summarise:
    results (list of TicketResult), answered, human, reasons ({reason: count}), tokens_total,
    cost_usd (sum), p50_tokens and p95_tokens (percentile of per-ticket tokens)."""
    model = make_model()
    results = [process_ticket(t, model, threshold, budget) for t in tickets]
    reasons: Dict[str, int] = {}
    for r in results:
        if r.status == "human":
            reasons[r.reason] = reasons.get(r.reason, 0) + 1
    toks = [r.tokens for r in results]
    return {"results": results, "answered": sum(r.status == "answered" for r in results),
            "human": sum(r.status == "human" for r in results), "reasons": reasons,
            "tokens_total": sum(toks), "cost_usd": sum(r.cost_usd for r in results),
            "p50_tokens": percentile(toks, 50), "p95_tokens": percentile(toks, 95)}
