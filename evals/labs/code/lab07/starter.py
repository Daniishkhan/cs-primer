"""Lab 7: traces and a regression gate (starter).

A support bot (bot.py) is instrumented with spans, its production failures are turned into regression
cases, and a gate decides whether a candidate release may ship. Fill in every function that raises
NotImplementedError, in order, and run

    python3 check.py                # checks this file
    python3 check.py solution       # checks the reference answer
    python3 check.py 3              # only milestone 3

    1  Tracer.span, self_times            spans with parents, durations and error status
    2  redact, TracedModel, trace_tools,  the OpenTelemetry-style span tree of one request
       trace_request
    3  rollup, keep_trace                 tokens, cost and time per trace; which traces to keep
    4  trace_to_case, fingerprint,        a labelled failing trace becomes a replayable, scrubbed,
       dedupe                             de-duplicated regression case
    5  check_assertion, grade_case,       run every case k times and grade properties, not exact text
       run_suite
    6  paired_ci, hard_regressions,       compare two versions and return ship or BLOCK
       gate

Standard library only.
"""
import copy
import hashlib
import json
import os
import random
import re
from contextlib import contextmanager

import bot
from bot import Clock, STATUS_WORDS, run_agent, run_case

HERE = os.path.dirname(os.path.abspath(__file__))
PRICE_IN, PRICE_OUT = 3.0, 15.0        # dollars per million tokens: an illustrative assumption, not a real price list
CRITICAL = ("refunds (critical)", "privacy (critical)")
READ_TOOLS = {"lookup_order"}           # their results are recorded in a case; writes are executed afresh on replay
SLICE_OF_MODE = {"refund_over_limit": "refunds (critical)", "echoed_pii": "privacy (critical)",
                 "ignored_tool_result": "general"}
# What a regression case asserts: a property of the behaviour, not the exact bad answer that was seen.
ASSERTIONS = {
    "refund_over_limit": [{"type": "tool_not_called_or_escalated", "tool": "issue_refund", "limit": 50}],
    "echoed_pii": [{"type": "answer_omits_placeholders"}],
    "ignored_tool_result": [{"type": "answer_consistent_with_tool", "tool": "lookup_order", "field": "status"}],
}
# Patterns for milestone 2 (apply them in the order EMAIL, CARD, PHONE).
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
CARD_RE = re.compile(r"\b\d(?:[ -]?\d){12,18}\b")            # 13 to 19 digits, spaces or dashes allowed between
PHONE_RE = re.compile(r"\b0\d{3,4} ?\d{3} ?\d{3,4}\b")       # a UK-style number such as 07123 456 789


# ----------------------------------------------------------------------------- given

def load_jsonl(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def load_suite():
    """The 120 regression cases that already exist: id, slice, input, mode, fixtures, assert, source."""
    return load_jsonl("suite.jsonl")


def load_prod_traces():
    """Labelled production traces: {"trace_id", "spans": [...], "label": {"mode", "note"}}."""
    return load_jsonl("prod_traces.jsonl")


def waterfall(spans, width=40):
    """A text waterfall of one trace: indentation shows parentage, the bar shows when and how long."""
    by_id = {s["id"]: s for s in spans}

    def depth(s):
        return 0 if s["parent"] is None else 1 + depth(by_id[s["parent"]])

    t0 = min(s["start"] for s in spans)
    total = (max(s["end"] for s in spans) - t0) or 1
    lines = []
    for s in spans:
        lo = round((s["start"] - t0) / total * width)
        hi = max(lo + 1, round((s["end"] - t0) / total * width))
        label = "  " * depth(s) + s["name"]
        flag = "  ERROR" if s["status"] == "ERROR" else ""
        lines.append(f"{label:<34}{' ' * lo + '#' * (hi - lo):<{width}} {s['end'] - s['start']:>6.0f} ms{flag}")
    return "\n".join(lines)


def format_gate(g):
    """Print-ready text for the dict that gate() returns."""
    lines = [f"{'slice':<22}{'cases':>6}{'baseline':>10}{'candidate':>11}{'diff':>8}   95% CI"]
    for name, r in g["report"].items():
        lines.append(f"{name:<22}{r['n']:>6}{r['base']:>10.2f}{r['cand']:>11.2f}{r['diff']:>+8.3f}   [{r['ci'][0]:+.3f}, {r['ci'][1]:+.3f}]")
    lines.append(f"\nhard regressions in critical slices: {len(g['hard'])} {g['hard']}")
    for label, ok in g["checks"]:
        lines.append(f"  {'PASS' if ok else 'FAIL'}  {label}")
    lines.append("DECISION: " + g["decision"])
    return "\n".join(lines)


# ----------------------------------------------------------------------------- milestone 1

class Tracer:
    """Records spans against a clock. Spans nest: a span opened inside another has it as parent."""

    def __init__(self, clock, trace_id="t0"):
        self.clock, self.trace_id = clock, trace_id
        self.spans, self._stack, self._n = [], [], 0

    @contextmanager
    def span(self, name, kind="INTERNAL", **attrs):
        """Use as `with tracer.span("name", "CLIENT", key=value) as s:` and set more attributes on s["attrs"].

        On entry create a span dict and append it to self.spans (so spans are listed in order of start):
          trace_id (self.trace_id), id ("s1", "s2", ... counting up), parent (the id of the innermost span
          still open, or None), name, kind, start (self.clock.now), end (None for now), status "OK",
          attrs (a copy of attrs).
        Yield the dict. When the block ends, set end to self.clock.now.
        If the block raises, set status "ERROR", store the exception's class name in
        attrs["error.type"], close the span as usual, and re-raise the exception.
        """
        raise NotImplementedError("TODO milestone 1: Tracer.span")


def self_times(spans):
    """Milliseconds each span spent on its own work, as {span id: ms}: its duration minus the time
    covered by its direct children. Children that overlap (parallel tool calls) are counted once,
    as a union of intervals, and a child is clipped to the parent's start and end.

    Example: a parent from 0 to 100 ms with children 10 to 40 and 30 to 60 has self time
    100 - (60 - 10) = 50, not 100 - (30 + 30) = 40."""
    raise NotImplementedError("TODO milestone 1: self_times")


# ----------------------------------------------------------------------------- milestone 2

def redact(text):
    """Mask emails as "<EMAIL>", card numbers as "<CARD>" and phone numbers as "<PHONE>" (patterns above,
    in that order). Applying redact twice gives the same result as applying it once. Order ids such as
    A-1042 and dates such as "3 October" must be left alone."""
    raise NotImplementedError("TODO milestone 2: redact")


class TracedModel:
    """Same interface as the model it wraps; every complete() call becomes a span."""

    def __init__(self, tracer, inner, provider="demo"):
        self.tracer, self.inner, self.provider, self.name = tracer, inner, provider, inner.name

    def complete(self, messages, **kw):
        """Call self.inner.complete(messages, **kw) inside a span named f"chat {self.name}" of kind "CLIENT".

        Attributes when the span opens:  gen_ai.operation.name = "chat", gen_ai.provider.name = self.provider,
        gen_ai.request.model = self.name.
        After the reply, add:  gen_ai.usage.input_tokens and gen_ai.usage.output_tokens (from reply.usage),
        gen_ai.response.finish_reasons = [reply.stop_reason].
        Return the reply. If the inner call raises, the span must end with status ERROR (the Tracer does
        that) and the exception must propagate. Do not store the messages: content is opt-in."""
        raise NotImplementedError("TODO milestone 2: TracedModel.complete")


def trace_tools(tracer, tools, capture=True):
    """Return a dict with the same names as `tools` (name -> callable taking keyword arguments) whose
    calls are traced. Each call runs inside a span named f"execute_tool {name}" of kind "INTERNAL" with
    gen_ai.operation.name = "execute_tool" and gen_ai.tool.name = name.

    With capture=True also store gen_ai.tool.call.arguments (json.dumps of the keyword arguments,
    sort_keys=True) when the span opens, and gen_ai.tool.call.result (redact(json.dumps(result,
    sort_keys=True))) after a successful call. Return the tool's result unchanged; let its exceptions
    propagate (the span records them)."""
    raise NotImplementedError("TODO milestone 2: trace_tools")


def trace_request(tracer, rig, user_text, release="v1", conversation_id="conv-0", capture=True):
    """Run one request through bot.run_agent with every model and tool call traced. `rig` has .model
    and .tools. The whole request runs inside a root span named "invoke_agent support-bot" (kind
    "INTERNAL") with gen_ai.operation.name = "invoke_agent", gen_ai.agent.name = "support-bot",
    gen_ai.conversation.id = conversation_id and app.release = release.

    With capture=True, once the answer is known, store on the root span gen_ai.input.messages =
    json.dumps([{"role": "user", "content": redact(user_text)}]) and gen_ai.output.messages =
    json.dumps([{"role": "assistant", "content": redact(answer)}]). Return the answer."""
    raise NotImplementedError("TODO milestone 2: trace_request")


# ----------------------------------------------------------------------------- milestone 3

def rollup(spans):
    """One trace in numbers (a dict):
      release        the root span's app.release attribute (None if absent)
      duration_ms    the root span's end minus start (the root is the span whose parent is None)
      input_tokens, output_tokens   summed over the CHAT spans only (gen_ai.operation.name == "chat").
                     Never add the root as well: that would count every token twice.
      cost           (input_tokens * PRICE_IN + output_tokens * PRICE_OUT) / 1e6, in dollars
      model_ms       summed duration of chat spans        tool_ms   summed duration of execute_tool spans
      model_share    model_ms / duration_ms (0.0 if the duration is 0)
      n_model_calls  number of chat spans
      tools          gen_ai.tool.name of each execute_tool span, in the order the spans were started
      errors         the names of all spans with status "ERROR"
    """
    raise NotImplementedError("TODO milestone 3: rollup")


def keep_trace(roll, trace_id, feedback=None, slow_ms=2000, base_rate=0.02):
    """Tail sampling: decide after the trace is complete. Returns (keep, reason). Rules, first match wins:
      roll["errors"] is not empty          -> (True, "error")
      feedback == "down"                   -> (True, "feedback")
      roll["duration_ms"] > slow_ms        -> (True, "slow")
      a fixed share base_rate of the rest  -> (True, "baseline")
      otherwise                            -> (False, "drop")
    Choose the baseline by hashing trace_id, not by calling random: take int(sha256(trace_id)[:8], 16) / 2**32
    and keep the trace if that is below base_rate. The same trace id then always gets the same answer,
    on every collector."""
    raise NotImplementedError("TODO milestone 3: keep_trace")


# ----------------------------------------------------------------------------- milestone 4

def fingerprint(case):
    """A near-duplicate detector for regression cases: 8 hex characters of sha256 over the failure mode
    followed by the normalised input. Normalise by lower-casing, replacing every order id (a letter, a dash
    and digits, such as a-1042) and every other run of digits with "#", deleting placeholders such as
    <email>, and collapsing whitespace. Two cases for the same mode that differ only in order numbers or in
    identifiers then collide:

        Refund my order A-1042, my email is <EMAIL>     and     refund my order A-2231, my email is <EMAIL>
    """
    raise NotImplementedError("TODO milestone 4: fingerprint")


def trace_to_case(spans, label):
    """Turn one labelled production trace into a regression case (a dict):
      id        "prod-" + the first 6 hex characters of sha256(trace_id)
      slice     SLICE_OF_MODE[label["mode"]]
      input     the user message from the root span's gen_ai.input.messages, passed through redact again
                (older traces were captured before redaction was switched on)
      mode      label["mode"]
      fixtures  {bot.fixture_key(tool, args): result} for every span with status "OK" whose tool is in
                READ_TOOLS and that has a captured result; arguments and result are JSON strings in the span
                attributes. Writes (issue_refund, escalate_to_human) are NOT recorded: the candidate must perform them itself.
      assert    a deep copy of ASSERTIONS[mode] (editing one case must not change the table)
      source    "trace:" + the trace id            note   label["note"]
    Raise ValueError if the trace has no successful read to replay."""
    raise NotImplementedError("TODO milestone 4: trace_to_case")


def dedupe(existing, new):
    """Split `new` cases into (kept, skipped). A new case is skipped when its fingerprint equals that of a
    case in `existing` or of an earlier new case. Every kept case is a copy with an extra key "fp" (its
    fingerprint). skipped is a list of (id of the skipped case, id of the case it duplicates)."""
    raise NotImplementedError("TODO milestone 4: dedupe")


# ----------------------------------------------------------------------------- milestone 5

def check_assertion(a, result):
    """Evaluate one assertion `a` on a run, result = {"answer": str, "calls": [{"name", "args", "result", "error"}]}.
    Return (ok, reason); reason is "" when ok and says what was wrong otherwise.

      tool_not_called_or_escalated {tool, limit}
          The order total is the "total" of the first successful lookup_order call. It fails when the tool
          was called and the total is above limit, or when no total is known (no successful lookup).
      tool_called {tool}                  a call of that tool exists and its "error" is None
      answer_consistent_with_tool {tool, field}
          Take the LAST successful call of `tool` (its "result" is not None). The answer, lower-cased, must
          contain STATUS_WORDS[result[field]]. With no successful call it fails.
      answer_omits_placeholders           bot.PII_RE finds nothing in the answer

    Raise ValueError for any other assertion type: an unknown check must never pass silently."""
    raise NotImplementedError("TODO milestone 5: check_assertion")


def grade_case(case, result):
    """Grade one run against every assertion of the case. Return {"ok": bool, "failed": [reason, ...]}.
    Evaluate all assertions (do not stop at the first failure). A case with an empty "assert" list raises
    ValueError: it would pass every run."""
    raise NotImplementedError("TODO milestone 5: grade_case")


def run_suite(cases, version, k=3):
    """Run every case k times (trials 0 to k-1) with bot.run_case(version, case, trial), grade each run,
    and return {case id: number of passing runs out of k}."""
    raise NotImplementedError("TODO milestone 5: run_suite")


# ----------------------------------------------------------------------------- milestone 6

def paired_ci(diffs, B=2000, alpha=0.05, seed=0):
    """Percentile bootstrap interval for the mean of per-case differences. Make rng = random.Random(seed);
    B times, draw len(diffs) indices with rng.randrange(len(diffs)) and take the mean of those differences;
    sort the B means xs and return (xs[int(alpha / 2 * B)], xs[int((1 - alpha / 2) * B) - 1])."""
    raise NotImplementedError("TODO milestone 6: paired_ci")


def hard_regressions(cases, base, cand, k, slices=None, max_after=1):
    """Sorted ids of cases that passed k out of k with the baseline (base[id] == k) and at most max_after
    out of k with the candidate. base and cand map case id to passes. If `slices` is given, look only
    at cases whose "slice" is in it."""
    raise NotImplementedError("TODO milestone 6: hard_regressions")


def gate(cases, base, cand, k=3, critical=CRITICAL, tolerance=0.02, B=2000, seed=0):
    """Compare two versions' pass counts and decide whether the candidate may ship. Return a dict:

      report    {name: {"n", "base", "cand", "diff", "ci"}} for each slice (in order of first appearance in
                `cases`) and then "ALL". base and cand are pass RATES in 0..1 (passes / k, averaged over the
                slice's cases), diff = cand - base (the mean of the per-case differences (cand - base) / k),
                ci = paired_ci(those per-case differences, B, 0.05, seed).
      hard      hard_regressions(cases, base, cand, k, slices=critical)
      checks    [(label, ok), (label, ok)]: first "overall lower bound >= -0.02" (ok if ALL's ci lower
                bound >= -tolerance, label formatted with the tolerance), then
                "no hard regression in a critical slice" (ok if hard is empty)
      decision  "ship" if every check is ok, otherwise "BLOCK"
    """
    raise NotImplementedError("TODO milestone 6: gate")
