"""standin.py: the harness and the stand-in agents for Lab 2.  Given; not part of the exercise.

harness   Tool, Registry, run_tool and run_loop: the Lab 1 loop, trimmed to what this lab
          needs (schema checks for required/unknown/enum arguments, tool errors as data,
          an iteration cap, a cumulative input-token budget and repeated-call detection).

agents    make_agent(design, task, trial) -> a ScriptedModel whose replies come from a
          small "policy" for each design. A policy is a generator: it yields the tool call
          it wants to make, is sent back what the tool returned, and finally returns its
          answer. It reads real results, so a tool that returns less, or says more, changes
          what happens next.

IMPORTANT: the policies are STAND-INS for a model. They encode the behaviour that
chapter 5 describes (a model holding an email address tries the id-only tool first; a
silent unit gets guessed; an opaque error gets repeated; a long dump hides the one
fact that matters; a refund whose response is lost gets retried). They are not
measurements of any real model, and the numbers they produce illustrate the METHOD of
measuring a tool design. To measure a real model, see "Run it against a real model".
"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from fixtures import REFUND_CAP_CENTS, money
from llm import ScriptedModel, count_tokens, text_of, tool_calls, tool_result, tool_use

# ---------------------------------------------------------------- harness


class ToolError(Exception):
    """A failure written for the model to read; the message is sent back verbatim."""


@dataclass
class Tool:
    name: str
    description: str
    input_schema: Dict[str, Any]
    fn: Callable[..., Any]


class Registry:
    def __init__(self, tools):
        self.tools = {t.name: t for t in tools}

    def definitions(self) -> List[dict]:
        return [{"name": t.name, "description": t.description, "input_schema": t.input_schema} for t in self.tools.values()]


@dataclass
class Budget:
    max_iterations: int = 10
    max_input_tokens: int = 20_000      # cumulative over the run: a long dump is re-sent on every later call
    max_repeats: int = 3


@dataclass
class RunResult:
    messages: List[dict]
    status: str            # "done", "max_iterations", "token_budget" or "repeated_call"
    answer: str
    iterations: int
    input_tokens: int


def _check_args(schema: dict, args: Any) -> Optional[str]:
    if not isinstance(args, dict):
        return "arguments must be an object"
    props = schema.get("properties", {})
    for name in schema.get("required", []):
        if name not in args:
            return f"missing required argument '{name}'"
    for name, value in args.items():
        if name not in props:
            return f"unexpected argument '{name}'"
        spec = props[name]
        if "enum" in spec and value not in spec["enum"]:
            return f"argument '{name}' must be one of {spec['enum']}"
        t = spec.get("type")
        ok = {"string": str, "integer": int, "number": (int, float), "boolean": bool}.get(t)
        if ok and (not isinstance(value, ok) or (t != "boolean" and isinstance(value, bool))):
            return f"argument '{name}' must be {t}"
    return None


def run_tool(registry: Registry, call: dict) -> dict:
    tool = registry.tools.get(call["name"])
    if tool is None:
        return tool_result(call["id"], f"Unknown tool '{call['name']}'.", is_error=True)
    problem = _check_args(tool.input_schema, call["input"])
    if problem:
        return tool_result(call["id"], f"Invalid arguments for {call['name']}: {problem}.", is_error=True)
    try:
        value = tool.fn(**call["input"])
    except ToolError as e:
        return tool_result(call["id"], str(e), is_error=True)
    except Exception as e:                                  # noqa: BLE001
        return tool_result(call["id"], f"{type(e).__name__}: {e}", is_error=True)
    return tool_result(call["id"], value if isinstance(value, str) else json.dumps(value, sort_keys=True))


def run_loop(model, question: str, registry: Registry, budget: Optional[Budget] = None) -> RunResult:
    budget, tools = budget or Budget(), registry.definitions()
    messages = [{"role": "user", "content": question}]
    seen: Dict[tuple, int] = {}
    spent, iterations, status, reply = 0, 0, "done", None
    while True:
        if spent > budget.max_input_tokens:
            status = "token_budget"
            break
        if iterations >= budget.max_iterations:
            status = "max_iterations"
            break
        reply = model.complete(messages, tools=tools)
        iterations += 1
        spent += reply.usage["input_tokens"]
        messages.append(reply.as_message())
        calls = tool_calls(reply)
        if not calls:
            break
        repeat = False
        for c in calls:
            key = (c["name"], json.dumps(c["input"], sort_keys=True))
            seen[key] = seen.get(key, 0) + 1
            repeat = repeat or seen[key] > budget.max_repeats
        if repeat:
            messages.append({"role": "user", "content": [tool_result(c["id"], "Not run: repeated call.", True) for c in calls]})
            status = "repeated_call"
            break
        messages.append({"role": "user", "content": [run_tool(registry, c) for c in calls]})
    answer = text_of(reply) if status == "done" else f"[stopped: {status}]"
    return RunResult(messages, status, answer, iterations, spent)


# ---------------------------------------------------------------- stand-in agents

@dataclass
class Out:
    content: str
    is_error: bool

    def json(self):
        try:
            return json.loads(self.content)
        except ValueError:
            return None


def _call(name, **args):
    return (name, args)


def _replay(policy, messages):
    """Run the generator from the start, feeding it the recorded results. A reply is
    either the next tool call or (when the policy returns) the final answer."""
    results = [Out(b["content"], b["is_error"]) for m in messages if m["role"] == "user" and isinstance(m["content"], list)
               for b in m["content"] if b.get("type") == "tool_result"]
    gen = policy()
    try:
        step = next(gen)
        for out in results:
            step = gen.send(out)
    except StopIteration as stop:
        return stop.value
    return [tool_use(step[0], step[1], id=f"t{len(results) + 1}")]


def _policy_thin(task, trial):
    """Design A: the five endpoint wrappers. What a model does with only an email or a name."""
    rng = random.Random(f"{task['id']}-{trial}-thin")
    who = task["email"] or task["name"]

    def go():
        yield _call("get_customer", id=who)                       # the only identifier it has; an id was wanted
        out = yield _call("list_invoices", customer=who)           # found by trial: this one accepts an email or a name
        rows = out.json() if not out.is_error else None
        if not rows:
            return f"I found no customer or invoices for {who}. Please check the email address."
        intent = task["intent"]
        owners = {r["customer_id"] for r in rows}
        if len(owners) > 1 and not task["email"]:
            if rng.random() < 0.5:                                 # sometimes it notices two customers in one dump
                return "There is more than one customer with that name. Which email address is yours?"
        if intent == "owed" or intent == "ambiguous":
            open_rows = [r for r in rows if r["status"] in ("open", "overdue")]
            return f"{task['name']} owes {money(sum(r['amount_cents'] for r in open_rows))} on {len(open_rows)} unpaid invoices."
        if intent == "history":
            row = next((r for r in rows if r["created_at"].startswith(task["month"])), None)
            return f"Your invoice from {task['month']} was {money(row['amount_cents'])}." if row else "I could not find that invoice."
        paid = sorted((r for r in rows if r["status"] == "paid"), key=lambda r: r["created_at"], reverse=True)
        if intent == "refund_cap":
            paid = [r for r in paid if r["amount_cents"] > REFUND_CAP_CENTS]
        else:
            paid = [r for r in paid if r["amount_cents"] <= REFUND_CAP_CENTS]
        out = yield _call("list_payments", invoice=paid[0]["id"])
        pays = sorted(out.json() or [], key=lambda p: (p["paid_at"], p["id"]))
        if intent == "last_payment":
            p = pays[-1]
            return f"Your last payment was {money(p['amount_cents'])} on {p['paid_at']}."
        if intent in ("refund_duplicate", "ambiguous_refund"):
            if len(pays) < 2:
                return "I could not find a duplicate charge."
            target, amount = pays[-1]["id"], pays[-1]["amount_cents"]
        elif intent == "refund_partial":
            target, amount = pays[-1]["id"], (2500 if rng.random() < 0.5 else 25.0)   # the unit was never stated
        else:                                                      # refund_cap: nothing in the interface says there is a limit
            target, amount = pays[-1]["id"], pays[-1]["amount_cents"]
        out = yield _call("create_refund", payment=target, amount=amount)
        if out.is_error and "504" in out.content:                  # no idea whether it went through; try again
            out = yield _call("create_refund", payment=target, amount=amount)
        if out.is_error:
            return "I tried to issue the refund but the service returned an error, so please check the account."
        return "I have requested the refund as asked."
    return go


def _policy_task_shaped(task, trial):
    """Design B: three tools built around the task."""
    who = task["email"] or task["name"]

    def go():
        out = yield _call("billing_find_customer", email_or_name=who)
        matches = out.json()
        if not isinstance(matches, list) or not matches:
            return f"I found no customer matching {who}. Please check the email address."
        if len(matches) > 1:
            return "There is more than one customer with that name. Which email address is yours?"
        out = yield _call("billing_get_account_summary", customer_id=matches[0]["customer_id"], response_format="concise")
        s = out.json()
        if not isinstance(s, dict):
            return "I could not read the account."
        intent = task["intent"]
        if intent == "owed":
            return f"{s['name']} owes {money(s['owed_cents'])} on {len(s['open_invoices'])} unpaid invoices."
        if intent == "last_payment":
            p = s["latest_payment"]
            return f"Your last payment was {money(p['amount_cents'])} on {p['paid_at']}."
        if intent == "history":
            return "I can only see recent invoices, so I cannot find that one. Please contact billing."
        pays = s["recent_payments"]
        if intent == "refund_duplicate":
            by_invoice: Dict[str, list] = {}
            for p in pays:
                by_invoice.setdefault(p["invoice_id"], []).append(p)
            dup = next((v for v in by_invoice.values() if len(v) > 1), None)
            if not dup:
                return "I could not find a duplicate charge."
            target, amount, reason = dup[0]["payment_id"], dup[0]["amount_cents"], "duplicate"
        elif intent == "refund_partial":
            target, amount, reason = s["latest_payment"]["payment_id"], 2500, "goodwill"
        else:                                                      # refund_cap
            big = max(pays, key=lambda p: p["amount_cents"])
            target, amount, reason = big["payment_id"], big["amount_cents"], "goodwill"
        args = dict(payment_id=target, amount_cents=amount, reason=reason)
        out = yield _call("billing_issue_refund", **args)
        if out.is_error and "timed out" in out.content:            # the error said retrying is safe
            out = yield _call("billing_issue_refund", **args)
        if out.is_error and "human" in out.content:
            return "That refund is above the limit I can approve, so I have passed it to a human colleague."
        if out.is_error:
            return f"The refund could not be issued: {out.content}"
        return f"I have issued the refund of {money(amount)}."
    return go


def make_agent(design: str, task: dict, trial: int) -> ScriptedModel:
    """The stand-in model for one run. `design` is "A" (thin wrappers) or "B" (task-shaped)."""
    policy = (_policy_thin if design == "A" else _policy_task_shaped)(task, trial)
    return ScriptedModel(lambda messages, tools, system: _replay(policy, messages))
