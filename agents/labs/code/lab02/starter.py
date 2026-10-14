"""Lab 2 starter: Tool Design, Measured.  THIS IS YOUR FILE.

Given: the two toolsets (THIN = design A, BETTER = design B, with the definitions exactly as
chapter 5 prints them), the design-A tool functions, build_registry, run_one, Record and
Grade. fixtures.py is the Northwind backend and the twenty tasks; standin.py is the loop and
the stand-in agents. Read them, do not edit them. Every function you write raises
NotImplementedError until you replace the body. Work in order; run

    python3 check.py            # checks this file
    python3 check.py 3          # only milestone 3

  1. lint, definition_tokens            read a toolset the way a reviewer would, count its cost
  2. find_customer, account_summary, issue_refund
                                        build the task-shaped tools (design B)
  3. grade                              end-state grading of one run
  4. run_metrics, evaluate, aggregate   run all twenty tasks several times and summarise
  5. paired_bootstrap_ci, sign_test_p, decide
                                        turn two reports into a decision you can defend

Standard library only. llm.py is the shared stand-in model module; do not edit it.
"""
from __future__ import annotations

import itertools
import json
import math
import random
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from fixtures import REFUND_CAP_CENTS, Northwind, RefundTimeout, TASKS, money
from llm import count_tokens
from standin import Budget, Registry, RunResult, Tool, ToolError, make_agent, run_loop

# =============================================================================
# Given: the two toolsets (definitions exactly as chapter 5 prints them)
# =============================================================================

GENERIC = {"id", "name", "query", "data", "input", "value", "user", "text", "x"}
STOP = {"the", "and", "for", "with", "this", "that", "from", "are", "you"}


def words(s: str) -> set:
    """Lower-case words of three or more letters, minus a few stop words."""
    return set(re.findall(r"[a-z]{3,}", s.lower())) - STOP


def schema(props, req):
    return {"type": "object", "properties": props, "required": req}


# Design A: one tool per REST endpoint.
THIN = [
    {"name": "get_customer", "description": "Gets a customer.", "input_schema": schema({"id": {"type": "string"}}, ["id"])},
    {"name": "list_invoices", "description": "Lists invoices.", "input_schema": schema({"customer": {"type": "string"}}, ["customer"])},
    {"name": "get_invoice", "description": "Gets an invoice.", "input_schema": schema({"id": {"type": "string"}}, ["id"])},
    {"name": "list_payments", "description": "Lists payments.", "input_schema": schema({"invoice": {"type": "string"}}, ["invoice"])},
    {"name": "create_refund", "description": "Creates a refund.", "input_schema": schema({"payment": {"type": "string"}, "amount": {"type": "number"}}, ["payment", "amount"])},
]

# Design B: three tools built around what a support agent has to get done.
BETTER = [
    {"name": "billing_find_customer",
     "description": "Find a customer by email address or by full name. Use this first when the user mentions a person but you do not have a customer_id. Returns up to 5 matches with customer_id, name and email. It does not return invoices; use billing_get_account_summary for those.",
     "input_schema": schema({"email_or_name": {"type": "string", "description": "An email such as ana@example.com, or a full name such as 'Ana Silva'."}}, ["email_or_name"])},
    {"name": "billing_get_account_summary",
     "description": "Summarise one customer's billing: plan, open invoices with amounts and due dates, and the most recent payment with its payment_id. Use for any question about what a customer owes or paid. Read-only. Does not list closed invoices older than 90 days.",
     "input_schema": schema({"customer_id": {"type": "string", "description": "Id from billing_find_customer, like cus_1042."},
                             "response_format": {"type": "string", "enum": ["concise", "detailed"], "description": "concise: amounts and dates only. detailed: adds line items."}}, ["customer_id"])},
    {"name": "billing_issue_refund",
     "description": "Refund all or part of one payment back to the original card. This moves real money and cannot be undone. Only call after the customer has asked for a refund and billing_get_account_summary has shown the payment_id. Refunds above 10000 cents are rejected and must go to a human.",
     "input_schema": schema({"payment_id": {"type": "string", "description": "Payment id like pay_88123, from billing_get_account_summary."},
                             "amount_cents": {"type": "integer", "description": "Amount in cents, 1 to the payment total. 2500 means 25.00."},
                             "reason": {"type": "string", "enum": ["duplicate", "service_issue", "goodwill"], "description": "Why the refund is being made."}}, ["payment_id", "amount_cents", "reason"])},
]


def thin_functions(db: Northwind) -> Dict[str, Any]:
    """The five endpoint wrappers over the backend: raw rows out, status codes for errors."""

    def get_customer(id):
        c = db.customers.get(id)
        if c is None:
            raise ToolError("404 Not Found")
        return c

    def list_invoices(customer):
        return [i for c in db.match_customers(customer) for i in db.invoices_of(c["customer_id"])]

    def get_invoice(id):
        for i in db.invoices:
            if i["id"] == id:
                return i
        raise ToolError("404 Not Found")

    def list_payments(invoice):
        return [p for p in db.payments.values() if p["invoice_id"] == invoice]

    def create_refund(payment, amount):
        try:
            res = db.apply_refund(payment, int(amount))        # the unit (cents) is not stated anywhere
        except RefundTimeout:
            raise ToolError("504 Gateway Timeout")
        except KeyError:
            raise ToolError("404 Not Found")
        except ValueError:
            raise ToolError("400 Bad Request")
        return {"refund": "ok", "remaining_cents": res["remaining_cents"]}

    return {"get_customer": get_customer, "list_invoices": list_invoices, "get_invoice": get_invoice,
            "list_payments": list_payments, "create_refund": create_refund}


def build_registry(design: str, db: Northwind) -> Registry:
    """Design "A" = THIN with the endpoint wrappers; design "B" = BETTER with YOUR functions."""
    if design == "A":
        fns = thin_functions(db)
        return Registry([Tool(d["name"], d["description"], d["input_schema"], fns[d["name"]]) for d in THIN])
    fns = {"billing_find_customer": lambda email_or_name: find_customer(db, email_or_name),
           "billing_get_account_summary": lambda customer_id, response_format="concise": account_summary(db, customer_id, response_format),
           "billing_issue_refund": lambda payment_id, amount_cents, reason: issue_refund(db, payment_id, amount_cents, reason)}
    return Registry([Tool(d["name"], d["description"], d["input_schema"], fns[d["name"]]) for d in BETTER])


def run_one(design: str, task: dict, trial: int) -> Tuple[RunResult, Northwind]:
    """One evaluation run: a fresh backend, a fresh stand-in agent, one loop. Returns the
    loop's result AND the backend, so the grader can look at what really happened to it."""
    db = Northwind(flaky=task["flaky"])
    result = run_loop(make_agent(design, task, trial), task["text"], build_registry(design, db), Budget())
    return result, db


@dataclass
class Record:
    """What one run left behind."""
    design: str
    task_id: str
    trial: int
    success: bool
    harmful: bool
    status: str
    model_calls: int
    tool_calls: int
    tool_errors: int
    input_tokens: int
    result_tokens: int


@dataclass
class Grade:
    success: bool
    harmful: bool
    reasons: List[str] = field(default_factory=list)


# =============================================================================
# Milestone 1: lint a toolset, count what it costs
# =============================================================================

def lint(tools: List[dict]) -> List[Tuple[str, str, str]]:
    """Review tool definitions; return findings as (tool name, code, message).

    Codes, in the order they are reported for each tool:
      "thin"            the description has fewer than 15 words
      "restates"        words(description) is a subset of words(name with "_" as spaces)
      then for each property in schema order:
      "generic_arg"     the property name is in GENERIC
      "undescribed_arg" the property has neither a "description" nor an "enum"
    After every tool has been reviewed, one more kind of finding:
      "overlap"         for each PAIR of tools (a, b) in list order, the Jaccard similarity of
                        words(a description) and words(b description), |A & B| / |A | B|, is at
                        least 0.35. Report it against tool a; the message names both tools.
    Messages are sentences for a human; tests look at the tool name and the code.
    """
    raise NotImplementedError("TODO milestone 1: lint")


def definition_tokens(tools: List[dict]) -> int:
    """Tokens the definitions cost on EVERY request: the sum of count_tokens(json.dumps(tool))."""
    raise NotImplementedError("TODO milestone 1: definition_tokens")


# =============================================================================
# Milestone 2: the task-shaped tools (design B)
# =============================================================================

def find_customer(db: Northwind, email_or_name: str):
    """billing_find_customer: up to 5 matches as [{"customer_id", "name", "email"}, ...].

    Use db.match_customers. When nothing matches, RETURN (do not raise) a sentence that
    starts "No customer found for" followed by the repr of the text, and tells the model
    what to try next (the email address on the account). A name shared by two customers
    returns both: it is the model's job to ask which one.
    """
    raise NotImplementedError("TODO milestone 2: find_customer")


def account_summary(db: Northwind, customer_id: str, response_format: str = "concise"):
    """billing_get_account_summary: one dict that answers "what do they owe / what did they pay".

    Raises ToolError(f"No customer with id {customer_id!r}. Ids look like cus_1042; get one from
    billing_find_customer.") for an unknown id. Otherwise the dict has exactly these keys:
      customer_id, name, plan
      owed_cents          the sum of amount_cents over ALL invoices with status open or overdue
      open_invoices       the newest 5 of those invoices, newest first, each
                          {"invoice_id", "status", "amount_cents", "due"} (due = the invoice's due_at);
                          with response_format "detailed" each also has "line_items"
      latest_payment      the newest payment as {"payment_id", "invoice_id", "amount_cents", "paid_at"}, or None
      recent_payments     the newest 5 payments, same shape, newest first (latest_payment is the first)
    "Newest" payments sort by (paid_at, id) descending, which is what db.payments_of returns.
    Invoices come from db.invoices_of (newest first). Nothing else (no addresses, no audit trail).
    """
    raise NotImplementedError("TODO milestone 2: account_summary")


def issue_refund(db: Northwind, payment_id: str, amount_cents: int, reason: str):
    """billing_issue_refund: refund part or all of a payment, safely.

    1. If amount_cents is above REFUND_CAP_CENTS, raise ToolError whose text contains "human",
       says not to retry, and states the cap. (Enforce it in code, whatever the prompt said.)
    2. Otherwise call db.apply_refund(payment_id, amount_cents, idempotency_key=key) with
       key = f"{payment_id}:{amount_cents}:{reason}", so an identical request is never applied twice.
         KeyError          -> ToolError(f"Error: no payment {payment_id!r}. Payment ids look like
                              pay_88123; get one from billing_get_account_summary.")
         ValueError        -> ToolError naming the legal range "between 1 and N" (N = what is still
                              refundable on that payment) and reminding the model amounts are in cents
         RefundTimeout     -> ToolError saying the service timed out and the outcome is unknown, that
                              retrying the SAME call is safe because repeats are ignored
    3. On success return f"Refunded {amount_cents} cents of {payment_id} ({reason}); {left} cents still
       refundable." and, when the backend says replayed, append " (repeat of an earlier call: no money moved again)".

    Let the backend decide whether the amount is possible (do not pre-check it): after a lost response
    the retry must reach the backend with the same key, even if nothing is left to refund.
    """
    raise NotImplementedError("TODO milestone 2: issue_refund")


# =============================================================================
# Milestone 3: grade a run by what happened, not by what was said
# =============================================================================

def grade(task: dict, db: Northwind, answer: str) -> Grade:
    """Grade one finished run.

    * The refunds that really moved money (db.refunds, a list of (payment_id, amount_cents))
      must equal task["expected_refunds"] as multisets (order does not matter, repeats do).
    * Every phrase in task["must_include"] must appear in the answer, ignoring case.
    * No phrase in task["must_not_include"] may appear, ignoring case.
    success = none of those rules was broken. harmful = at least one refund moved money that
    the task did not expect (an extra, a double, a wrong amount); a MISSING refund is a failure
    but not harmful. reasons has one sentence per rule broken (empty on success).
    """
    raise NotImplementedError("TODO milestone 3: grade")


# =============================================================================
# Milestone 4: run everything, summarise
# =============================================================================

def run_metrics(messages: List[dict]) -> Dict[str, int]:
    """Count what a finished conversation cost, from its messages alone.

    model_calls     assistant messages
    tool_calls      tool_use blocks
    tool_errors     tool_result blocks with is_error true
    result_tokens   sum of count_tokens(content) over all tool_result blocks
    repeated_calls  tool_use blocks whose (name, input) already appeared earlier in the run
    """
    raise NotImplementedError("TODO milestone 4: run_metrics")


def evaluate(design: str, tasks: List[dict], trials: int = 3) -> List[Record]:
    """Run every task `trials` times against one design and return one Record per run.

    Order: task by task in the order given, trials 0 .. trials-1 within each task. For each run
    call run_one(design, task, trial), grade the end state (grade), take the metrics from the
    messages (run_metrics), and take status and input_tokens from the RunResult.
    """
    raise NotImplementedError("TODO milestone 4: evaluate")


def aggregate(records: List[Record]) -> Dict[str, Any]:
    """Summarise one design's records. Raises ValueError if there are none.

    Returns a dict with:
      design, n_runs, n_tasks
      success_rate, harm_rate        over all runs
      mean_model_calls, mean_tool_calls, mean_tool_errors, mean_input_tokens   over all runs
      statuses                       {status: number of runs}
      per_task                       {task_id: {"success": mean over its trials, "harm": mean,
                                                "input_tokens": mean}}   (in first-seen task order)
    """
    raise NotImplementedError("TODO milestone 4: aggregate")


# =============================================================================
# Milestone 5: from two reports to a decision
# =============================================================================

def paired_bootstrap_ci(diffs: List[float], n_boot: int = 2000, seed: int = 0, alpha: float = 0.05) -> Tuple[float, float, float]:
    """(mean, low, high): the mean of `diffs` and a percentile bootstrap interval for it.

    Exactly this procedure, so that results are reproducible:
      rng = random.Random(seed); n = len(diffs)
      repeat n_boot times: draw n items WITH replacement as diffs[rng.randrange(n)] (n draws,
      in order) and record their mean;
      sort the n_boot means; low = means[int(n_boot * alpha / 2)];
      high = means[int(n_boot * (1 - alpha / 2)) - 1].
    Raises ValueError for an empty list.
    """
    raise NotImplementedError("TODO milestone 5: paired_bootstrap_ci")


def sign_test_p(wins: int, losses: int) -> float:
    """Two-sided exact sign test: how surprising is this split if each non-tied task were a coin flip?

    n = wins + losses (ties are dropped). With k = min(wins, losses), the p-value is
    min(1, 2 * P(X <= k)) where X ~ Binomial(n, 0.5). With n = 0 return 1.0.
    """
    raise NotImplementedError("TODO milestone 5: sign_test_p")


def decide(a: Dict[str, Any], b: Dict[str, Any], n_boot: int = 2000, seed: int = 0) -> Dict[str, Any]:
    """Compare two reports (from aggregate) on the tasks they share and say which design to ship.

    d_success[t] = b.per_task[t]["success"] - a.per_task[t]["success"], and likewise d_tokens for
    "input_tokens", over the shared task ids in sorted order. Return a dict with
      success_diff, success_ci        paired_bootstrap_ci(d_success, n_boot, seed): mean and (low, high)
      tokens_diff, tokens_ci          the same for d_tokens
      wins, losses, ties              tasks where d_success is > 0, < 0, == 0 (B's view)
      p_sign                          sign_test_p(wins, losses)
      regressions                     task ids where d_success < 0 (B does worse), sorted
      harm_a, harm_b                  the harm_rate of each report
      verdict, reason                 "B", "A" or "none", and one sentence saying why:
        success_ci low > 0   -> "B" (better on success)
        success_ci high < 0  -> "A"
        otherwise success is a tie, so cost decides: tokens_ci high < 0 -> "B" (cheaper),
        tokens_ci low > 0 -> "A" (cheaper), else "none".
    """
    raise NotImplementedError("TODO milestone 5: decide")
