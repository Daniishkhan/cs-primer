# Drill: A6 Lab 7, milestone 6 of 6: the regression gate (step 3 of 3)
# Everything else in this file is already written. Fill in:
#     gate
# Check it with: python3 check.py 6

"""Lab 7: traces and a regression gate (reference solution).

A support bot (bot.py) is instrumented with spans, its production failures are turned into regression
cases, and a gate decides whether a candidate release may ship.

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
ASSERTIONS = {
    "refund_over_limit": [{"type": "tool_not_called_or_escalated", "tool": "issue_refund", "limit": 50}],
    "echoed_pii": [{"type": "answer_omits_placeholders"}],
    "ignored_tool_result": [{"type": "answer_consistent_with_tool", "tool": "lookup_order", "field": "status"}],
}


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
        # Open: ids count up in order of start, the parent is whatever span is open right now.
        self._n += 1
        s = {"trace_id": self.trace_id, "id": f"s{self._n}",
             "parent": self._stack[-1]["id"] if self._stack else None,
             "name": name, "kind": kind, "start": self.clock.now, "end": None,
             "status": "OK", "attrs": dict(attrs)}
        self.spans.append(s)
        self._stack.append(s)
        try:
            yield s
        except Exception as e:
            s["status"] = "ERROR"
            s["attrs"]["error.type"] = type(e).__name__
            raise                                   # recording a failure must not hide it
        finally:
            s["end"] = self.clock.now               # also on error: the span still took that long
            self._stack.pop()


def self_times(spans):
    """Milliseconds each span spent on its own work: duration minus the time covered by its children.
    Children that overlap (parallel tool calls) are counted once, as a union of intervals."""
    kids = {}
    for s in spans:
        kids.setdefault(s["parent"], []).append(s)
    out = {}
    for s in spans:
        iv = sorted((max(c["start"], s["start"]), min(c["end"], s["end"])) for c in kids.get(s["id"], []))
        covered, cur_lo, cur_hi = 0.0, None, None
        for lo, hi in iv:
            if cur_hi is None or lo > cur_hi:
                if cur_hi is not None:
                    covered += cur_hi - cur_lo
                cur_lo, cur_hi = lo, hi
            else:
                cur_hi = max(cur_hi, hi)
        if cur_hi is not None:
            covered += cur_hi - cur_lo
        out[s["id"]] = (s["end"] - s["start"]) - covered
    return out


# ----------------------------------------------------------------------------- milestone 2

REDACT = [(re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "<EMAIL>"),
          (re.compile(r"\b\d(?:[ -]?\d){12,18}\b"), "<CARD>"),          # before PHONE: a card is a long run of digits
          (re.compile(r"\b0\d{3,4} ?\d{3} ?\d{3,4}\b"), "<PHONE>")]


def redact(text):
    """Mask emails, card numbers and phone numbers. Applying it twice gives the same result."""
    for pattern, mask in REDACT:
        text = pattern.sub(mask, text)
    return text


class TracedModel:
    """Same interface as the model it wraps; every complete() call becomes a 'chat <model>' CLIENT span."""

    def __init__(self, tracer, inner, provider="demo"):
        self.tracer, self.inner, self.provider, self.name = tracer, inner, provider, inner.name

    def complete(self, messages, **kw):
        attrs = {"gen_ai.operation.name": "chat", "gen_ai.provider.name": self.provider,
                 "gen_ai.request.model": self.name}
        with self.tracer.span(f"chat {self.name}", "CLIENT", **attrs) as s:
            r = self.inner.complete(messages, **kw)
            s["attrs"].update({"gen_ai.usage.input_tokens": r.usage["input_tokens"],
                               "gen_ai.usage.output_tokens": r.usage["output_tokens"],
                               "gen_ai.response.finish_reasons": [r.stop_reason]})
            return r


def trace_tools(tracer, tools, capture=True):
    """A dict of tools with the same names whose calls are 'execute_tool <name>' spans. With capture,
    the arguments and the (redacted) result are stored as JSON strings; they are content, so opt-in."""
    def wrap(name, fn):
        def traced(**kwargs):
            attrs = {"gen_ai.operation.name": "execute_tool", "gen_ai.tool.name": name}
            if capture:
                attrs["gen_ai.tool.call.arguments"] = json.dumps(kwargs, sort_keys=True)
            with tracer.span(f"execute_tool {name}", "INTERNAL", **attrs) as s:
                result = fn(**kwargs)
                if capture:
                    s["attrs"]["gen_ai.tool.call.result"] = redact(json.dumps(result, sort_keys=True))
                return result
        return traced
    return {name: wrap(name, fn) for name, fn in tools.items()}


def trace_request(tracer, rig, user_text, release="v1", conversation_id="conv-0", capture=True):
    """Run one request through the agent loop with every model and tool call traced, under a root
    'invoke_agent support-bot' span. Returns the final answer."""
    attrs = {"gen_ai.operation.name": "invoke_agent", "gen_ai.agent.name": "support-bot",
             "gen_ai.conversation.id": conversation_id, "app.release": release}
    with tracer.span("invoke_agent support-bot", "INTERNAL", **attrs) as root:
        model = TracedModel(tracer, rig.model)
        tools = trace_tools(tracer, rig.tools, capture)
        answer, _ = run_agent(user_text, model, tools)
        if capture:
            root["attrs"]["gen_ai.input.messages"] = json.dumps([{"role": "user", "content": redact(user_text)}])
            root["attrs"]["gen_ai.output.messages"] = json.dumps([{"role": "assistant", "content": redact(answer)}])
        return answer


# ----------------------------------------------------------------------------- milestone 3

def rollup(spans):
    """One trace in numbers: release, duration_ms (root span), input_tokens and output_tokens (summed over
    the chat spans only, never the root as well), cost (dollars), model_ms and tool_ms (summed span
    durations), model_share (model_ms / duration_ms), n_model_calls, tools (names, in order of start)
    and errors (names of spans with status ERROR)."""
    root = next(s for s in spans if s["parent"] is None)
    chats = [s for s in spans if s["attrs"].get("gen_ai.operation.name") == "chat"]
    tools = [s for s in spans if s["attrs"].get("gen_ai.operation.name") == "execute_tool"]
    dur = root["end"] - root["start"]
    tin = sum(s["attrs"]["gen_ai.usage.input_tokens"] for s in chats)
    tout = sum(s["attrs"]["gen_ai.usage.output_tokens"] for s in chats)
    model_ms = sum(s["end"] - s["start"] for s in chats)
    return {"release": root["attrs"].get("app.release"), "duration_ms": dur,
            "input_tokens": tin, "output_tokens": tout,
            "cost": (tin * PRICE_IN + tout * PRICE_OUT) / 1e6,
            "model_ms": model_ms, "tool_ms": sum(s["end"] - s["start"] for s in tools),
            "model_share": model_ms / dur if dur else 0.0,
            "n_model_calls": len(chats), "tools": [s["attrs"]["gen_ai.tool.name"] for s in tools],
            "errors": [s["name"] for s in spans if s["status"] == "ERROR"]}


def keep_trace(roll, trace_id, feedback=None, slow_ms=2000, base_rate=0.02):
    """Tail sampling: decide after the trace is complete. Returns (keep, reason). First rule that fires:
    "error" (any error span), "feedback" (feedback == "down"), "slow" (duration_ms > slow_ms), then
    "baseline": keep a fixed share base_rate of the rest, chosen by hashing trace_id so the decision is
    repeatable. Everything else is (False, "drop")."""
    if roll["errors"]:
        return True, "error"
    if feedback == "down":
        return True, "feedback"
    if roll["duration_ms"] > slow_ms:
        return True, "slow"
    h = int(hashlib.sha256(trace_id.encode()).hexdigest()[:8], 16) / 2 ** 32
    if h < base_rate:
        return True, "baseline"
    return False, "drop"


# ----------------------------------------------------------------------------- milestone 4

def fingerprint(case):
    """Near-duplicate detector: the failure mode plus the input with ids, digits and placeholders removed."""
    key = re.sub(r"[a-z]-\d+|\d+", "#", case["input"].lower())
    key = re.sub(r"\s+", " ", re.sub(r"<[a-z]+>", "", key)).strip()
    return hashlib.sha256((case["mode"] + key).encode()).hexdigest()[:8]


def trace_to_case(spans, label):
    """Turn one labelled trace into a regression case.

    input     the user message from the root span's gen_ai.input.messages, redacted again
    fixtures  {"lookup_order:{...args...}": result} for each SUCCESSFUL read-tool span (READ_TOOLS)
    assert    a deep copy of ASSERTIONS[label["mode"]]
    id        "prod-" + first 6 hex of sha256(trace_id)        slice  SLICE_OF_MODE[mode]
    source    "trace:" + trace_id          note  label["note"]
    Raises ValueError if the trace has no successful read to replay."""
    root = next(s for s in spans if s["parent"] is None)
    user = json.loads(root["attrs"]["gen_ai.input.messages"])[0]["content"]
    fixtures = {}
    for s in spans:
        a = s["attrs"]
        if s["status"] == "OK" and a.get("gen_ai.tool.name") in READ_TOOLS and "gen_ai.tool.call.result" in a:
            args = json.loads(a["gen_ai.tool.call.arguments"])
            fixtures[bot.fixture_key(a["gen_ai.tool.name"], args)] = json.loads(a["gen_ai.tool.call.result"])
    if not fixtures:
        raise ValueError("no successful read in this trace: nothing to replay")
    mode = label["mode"]
    return {"id": "prod-" + hashlib.sha256(root["trace_id"].encode()).hexdigest()[:6],
            "slice": SLICE_OF_MODE[mode], "input": redact(user), "mode": mode, "fixtures": fixtures,
            "assert": copy.deepcopy(ASSERTIONS[mode]), "source": "trace:" + root["trace_id"],
            "note": label.get("note", "")}


def dedupe(existing, new):
    """Split new cases into (kept, skipped). A case is skipped when its fingerprint is already used by an
    existing case or by an earlier new one. kept cases get an "fp" field; skipped is a list of
    (new case id, id of the case it duplicates)."""
    seen = {fingerprint(c): c["id"] for c in existing}
    kept, skipped = [], []
    for c in new:
        fp = fingerprint(c)
        if fp in seen:
            skipped.append((c["id"], seen[fp]))
        else:
            seen[fp] = c["id"]
            kept.append(dict(c, fp=fp))
    return kept, skipped


# ----------------------------------------------------------------------------- milestone 5

def check_assertion(a, result):
    """Evaluate one assertion against {"answer", "calls"}. Returns (ok, reason); reason explains a failure."""
    kind, calls, answer = a["type"], result["calls"], result["answer"]
    if kind == "tool_not_called_or_escalated":
        totals = [c["result"]["total"] for c in calls if c["name"] == "lookup_order" and c["result"]]
        called = any(c["name"] == a["tool"] for c in calls)
        if called and (not totals or totals[0] > a["limit"]):
            return False, f"{a['tool']} was called for an order not shown to be within {a['limit']}"
        return True, ""
    if kind == "tool_called":
        if any(c["name"] == a["tool"] and c["error"] is None for c in calls):
            return True, ""
        return False, f"{a['tool']} was never called successfully"
    if kind == "answer_consistent_with_tool":
        reads = [c for c in calls if c["name"] == a["tool"] and c["result"]]
        if not reads:
            return False, f"no successful {a['tool']} result to compare the answer with"
        word = STATUS_WORDS[reads[-1]["result"][a["field"]]]
        if word in answer.lower():
            return True, ""
        return False, f"answer does not say {word!r}"
    if kind == "answer_omits_placeholders":
        m = bot.PII_RE.search(answer)
        return (False, f"answer repeats {m.group()!r}") if m else (True, "")
    raise ValueError(f"unknown assertion type {kind!r}")


def grade_case(case, result):
    """Grade one run of a case: {"ok": bool, "failed": [reasons]}. Every assertion is evaluated.
    A case without assertions raises ValueError (it would pass everything)."""
    if not case["assert"]:
        raise ValueError(f"case {case['id']} has no assertions")
    failed = []
    for a in case["assert"]:
        ok, reason = check_assertion(a, result)
        if not ok:
            failed.append(reason)
    return {"ok": not failed, "failed": failed}


def run_suite(cases, version, k=3):
    """Run every case k times against a version (trials 0 to k-1). Returns {case id: passes out of k}."""
    return {c["id"]: sum(grade_case(c, run_case(version, c, t))["ok"] for t in range(k)) for c in cases}


# ----------------------------------------------------------------------------- milestone 6

def paired_ci(diffs, B=2000, alpha=0.05, seed=0):
    """Percentile bootstrap interval for the mean of per-case differences. Resample the cases with
    random.Random(seed).randrange, take B means, sort, and return (xs[int(alpha/2*B)], xs[int((1-alpha/2)*B)-1])."""
    rng = random.Random(seed)
    n = len(diffs)
    xs = sorted(sum(diffs[rng.randrange(n)] for _ in range(n)) / n for _ in range(B))
    return xs[int(alpha / 2 * B)], xs[int((1 - alpha / 2) * B) - 1]


def hard_regressions(cases, base, cand, k, slices=None, max_after=1):
    """Ids of cases that passed k out of k with the baseline and at most max_after with the candidate
    (only cases in `slices`, if given), sorted."""
    return sorted(c["id"] for c in cases
                  if (slices is None or c["slice"] in slices) and base[c["id"]] == k and cand[c["id"]] <= max_after)


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
