# Drill: A4 Lab 1, milestone 4 of 6: the loop (step 2 of 2)
# Everything else in this file is already written. Fill in:
#     agent_loop
# Check it with: python3 check.py 4

"""Lab 1 reference solution: the agent loop from scratch.

Six milestones, in the order the page builds them:

  1. validate_args, Registry.definitions   tool schemas and argument checking
  2. run_tool                              one tool call, failures returned as data
  3. LoopGuard                             budgets, deadline, repeated-call detection
  4. check_pairing, agent_loop             the loop itself
  5. summarise (and Trace events)          structured logging of a run
  6. parse_react, ReActModel               the same loop driven by a text-only model

Standard library only. llm.py is the shared stand-in model module, unchanged.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from llm import Model, Response, count_tokens, text, text_of, tool_calls, tool_result, tool_use

# =============================================================================
# Given: the world the agent works in (an order-support desk)
# =============================================================================


class ToolError(Exception):
    """Raise this inside a tool for a failure the MODEL should read: the message is
    sent back verbatim as the tool result, so write it as an instruction."""


class Shop:
    """The state the tools act on. One fresh Shop per run, so a test can look at the
    side effects (refunds) and at which tool functions really executed."""

    def __init__(self):
        self.orders = {
            "A-1001": {"status": "shipped", "total_cents": 4250, "carrier": "UPS"},
            "A-1002": {"status": "processing", "total_cents": 1999, "carrier": None},
            "A-1003": {"status": "delivered", "total_cents": 12900, "carrier": "DHL"},
        }
        self.tracking = {"UPS": "Out for delivery in Leeds", "DHL": "Delivered to front door in Hull on 3 March"}
        self.refunds: List[tuple] = []      # (order_id, amount_cents, reason)
        self.executed: List[str] = []       # names of tool functions that actually ran


@dataclass
class Tool:
    name: str
    description: str
    input_schema: Dict[str, Any]
    fn: Callable[..., Any]


class Registry:
    """The tools the harness offers. The model only ever sees definitions(); the
    functions stay on this side of the wire."""

    def __init__(self, tools=()):
        self._tools: Dict[str, Tool] = {}
        for t in tools:
            self.add(t)

    def add(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"duplicate tool name {tool.name!r}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def names(self) -> List[str]:
        return list(self._tools)

    def definitions(self) -> List[dict]:
        """The list sent as `tools=` on every model request.

        Each entry has exactly the keys name, description and input_schema (no
        function), in registration order. The result is a fresh list each call.
        """
        return [{"name": t.name, "description": t.description, "input_schema": t.input_schema}
                for t in self._tools.values()]


def make_registry(shop: Shop) -> Registry:
    """The four tools of the support desk, bound to one Shop."""

    def get_order(order_id):
        shop.executed.append("get_order")
        order = shop.orders.get(order_id)
        if order is None:
            raise ToolError(f"No order with id {order_id!r}. Order ids look like A-1001.")
        return json.dumps(order)

    def track_shipment(carrier):
        shop.executed.append("track_shipment")
        return shop.tracking[carrier]

    def issue_refund(order_id, amount_cents, reason):
        shop.executed.append("issue_refund")
        order = shop.orders.get(order_id)
        if order is None:
            raise ToolError(f"No order with id {order_id!r}. Nothing was refunded.")
        if amount_cents > order["total_cents"]:
            raise ToolError(f"Refund of {amount_cents} cents is more than the order total of "
                            f"{order['total_cents']} cents. Nothing was refunded.")
        shop.refunds.append((order_id, amount_cents, reason))
        return f"Refunded {amount_cents} cents of order {order_id} ({reason})."

    def get_returns_policy():
        shop.executed.append("get_returns_policy")
        clause = "Items may be returned within 30 days in their original packaging; refunds go to the original payment method."
        return "\n".join(f"{i}. {clause}" for i in range(1, 25))

    return Registry([
        Tool("get_order", "Look up one order by id. Returns its status, total in cents and carrier as JSON. "
             "Use this before answering any question about an order.",
             {"type": "object", "properties": {"order_id": {"type": "string", "pattern": r"A-\d{4}", "examples": ["A-1001"],
                                                            "description": "Order id such as A-1001."}},
              "required": ["order_id"]}, get_order),
        Tool("track_shipment", "Get the latest tracking status for a carrier's parcel. Use after get_order shows a carrier.",
             {"type": "object", "properties": {"carrier": {"type": "string", "enum": ["UPS", "DHL"],
                                                           "description": "Carrier name from get_order."}},
              "required": ["carrier"]}, track_shipment),
        Tool("issue_refund", "Refund part or all of an order to the original payment method. Moves real money and "
             "cannot be undone; only call after the customer has asked for a refund.",
             {"type": "object", "properties": {
                 "order_id": {"type": "string", "pattern": r"A-\d{4}", "examples": ["A-1001"]},
                 "amount_cents": {"type": "integer", "minimum": 1, "maximum": 10000,
                                  "description": "Amount in cents; 2500 means 25.00."},
                 "reason": {"type": "string", "enum": ["duplicate", "damaged", "goodwill"]}},
              "required": ["order_id", "amount_cents", "reason"]}, issue_refund),
        Tool("get_returns_policy", "Return the full text of the returns policy (long). Takes no arguments.",
             {"type": "object", "properties": {}, "required": []}, get_returns_policy),
    ])


@dataclass
class Budget:
    """Hard limits the harness enforces. The model is never trusted to respect them."""
    max_iterations: int = 8          # model calls
    max_input_tokens: int = 20_000   # cumulative input tokens over all calls
    max_repeats: int = 2             # how often an identical (tool, input) call is allowed
    max_seconds: float = 30.0        # wall clock for the whole task


STOP_MESSAGES = {
    "max_iterations": "I stopped because I reached the limit on model calls for this task.",
    "token_budget": "I stopped because the task used up its token budget.",
    "timeout": "I stopped because the task ran out of time.",
    "repeated_call": "I stopped because I kept repeating the same tool call without making progress.",
}


class FakeClock:
    """A clock you wind by hand, so time limits are tested without sleeping.
    Use it wherever the code takes a `clock` argument."""

    def __init__(self, start: float = 0.0):
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@dataclass
class RunResult:
    messages: List[dict]
    status: str            # "done", "truncated", or one of the keys of STOP_MESSAGES
    answer: str
    iterations: int
    input_tokens: int


class Trace:
    """An append-only list of structured events (milestone 5). Given: the loop adds
    events, summarise() reads them. Every event is a plain, JSON-serialisable dict."""

    def __init__(self):
        self.events: List[dict] = []

    def add(self, kind: str, **fields) -> None:
        self.events.append({"kind": kind, **fields})


# =============================================================================
# Milestone 1: schemas and argument validation
# =============================================================================

def _json_type(value) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    return "object"


def _type_ok(value, wanted: str) -> bool:
    actual = _json_type(value)
    if wanted == "number":
        return actual in ("integer", "number")      # an int is a valid number
    return actual == wanted                          # True is NOT an integer, 3.0 is NOT an integer here


def validate_args(schema: dict, args: Any) -> List[str]:
    """Check `args` against a (small subset of) JSON Schema; return a list of problems.

    An empty list means the arguments are acceptable. Each problem is one sentence the
    MODEL will read, so name the argument and say what would be valid.

    Supported: a top-level {"type": "object", "properties": {...}, "required": [...]}
    where each property may have type (string, integer, number, boolean, array, object),
    enum, minimum, maximum and pattern (a regex that must match the whole string).

    Order of the returned list: missing required arguments first (in the order of
    `required`), then one pass over `properties` in schema order for the arguments that
    were given, then unexpected arguments, sorted by name. A bool is not an integer and a
    float is not an integer. An argument with the wrong type gets ONE problem (no range or
    enum complaint on top of it). If `args` is not a dict, return a single problem.
    """
    if not isinstance(args, dict):
        return [f"arguments must be a JSON object, got {_json_type(args)}"]
    props = schema.get("properties", {})
    errors: List[str] = []
    for name in schema.get("required", []):
        if name not in args:
            errors.append(f"missing required argument '{name}'")
    for name, spec in props.items():
        if name not in args:
            continue
        value = args[name]
        wanted = spec.get("type")
        if wanted and not _type_ok(value, wanted):
            errors.append(f"argument '{name}' must be {wanted}, got {_json_type(value)} ({value!r})")
            continue
        if "enum" in spec and value not in spec["enum"]:
            errors.append(f"argument '{name}' must be one of {spec['enum']}, got {value!r}")
        if "pattern" in spec and isinstance(value, str) and not re.fullmatch(spec["pattern"], value):
            hint = f", for example {spec['examples'][0]!r}" if spec.get("examples") else ""
            errors.append(f"argument '{name}' = {value!r} does not match the pattern {spec['pattern']}{hint}")
        if "minimum" in spec and _json_type(value) in ("integer", "number") and value < spec["minimum"]:
            errors.append(f"argument '{name}' must be at least {spec['minimum']}, got {value!r}")
        if "maximum" in spec and _json_type(value) in ("integer", "number") and value > spec["maximum"]:
            errors.append(f"argument '{name}' must be at most {spec['maximum']}, got {value!r}")
    for name in sorted(set(args) - set(props)):
        errors.append(f"unexpected argument '{name}' (valid arguments: {', '.join(props) or 'none'})")
    return errors


# =============================================================================
# Milestone 2: running one tool call
# =============================================================================

def run_tool(registry: Registry, call: dict, max_result_chars: int = 2000) -> dict:
    """Run one tool_use block and return the matching tool_result block. NEVER raises.

    `call` is {"type": "tool_use", "id": ..., "name": ..., "input": {...}}.
    Use llm.tool_result(id, content, is_error) to build the block.

      * unknown tool name   -> error result naming the tool and listing the available ones
      * invalid arguments   -> error result starting "Invalid arguments for <name>:" with
                               every problem from validate_args; the function is NOT run
      * ToolError raised    -> error result whose content is str(error), verbatim
      * any other exception -> error result that names the tool and the exception TYPE
                               but not its message (internals stay out of the context)
      * a str result        -> used as is; anything else -> json.dumps(result, sort_keys=True)
      * a result longer than max_result_chars is cut to that length and a note is
        appended that contains the word "truncated" and both the shown and the total
        number of characters. Error messages are never truncated.
    """
    call_id = call.get("id", "")
    name = call.get("name", "")
    tool = registry.get(name)
    if tool is None:
        return tool_result(call_id, f"Unknown tool '{name}'. Available tools: {', '.join(registry.names())}. "
                                    "Nothing was run.", is_error=True)
    problems = validate_args(tool.input_schema, call.get("input", {}))
    if problems:
        return tool_result(call_id, f"Invalid arguments for {name}: " + "; ".join(problems) +
                           ". Nothing was run. Fix the arguments and call again.", is_error=True)
    try:
        value = tool.fn(**call.get("input", {}))
        content = value if isinstance(value, str) else json.dumps(value, sort_keys=True)
    except ToolError as e:
        return tool_result(call_id, str(e), is_error=True)
    except Exception as e:                                   # noqa: BLE001 (the loop must survive anything)
        return tool_result(call_id, f"{name} failed with an internal error ({type(e).__name__}). "
                                    "Try a different approach or tell the user.", is_error=True)
    if len(content) > max_result_chars:
        total = len(content)
        content = (content[:max_result_chars] +
                   f"\n[truncated: showing the first {max_result_chars} of {total} characters. "
                   "Ask for something narrower.]")
    return tool_result(call_id, content)


# =============================================================================
# Milestone 3: stopping rules
# =============================================================================

class LoopGuard:
    """Decides, from the numbers, when a run must stop. Pure bookkeeping: it never
    calls a model or a tool. `clock` is any zero-argument function returning seconds."""

    def __init__(self, budget: Budget, clock: Callable[[], float] = time.monotonic):
        self.budget = budget
        self.clock = clock
        self.started = clock()
        self.iterations = 0          # model calls made so far
        self.input_tokens = 0        # sum of input_tokens over those calls
        self.seen: Dict[tuple, int] = {}   # (tool name, canonical input json) -> times called

    def before_model_call(self) -> Optional[str]:
        """Return None if another model call is allowed, else the reason to stop.

        Checked in this order: "token_budget" when input_tokens so far is MORE than
        max_input_tokens; "timeout" when MORE than max_seconds have passed since the
        guard was created; "max_iterations" when iterations has reached max_iterations.
        """
        b = self.budget
        if self.input_tokens > b.max_input_tokens:
            return "token_budget"
        if self.clock() - self.started > b.max_seconds:
            return "timeout"
        if self.iterations >= b.max_iterations:
            return "max_iterations"
        return None

    def after_model_call(self, usage: Dict[str, int]) -> None:
        """Record one finished model call: one more iteration, plus its input tokens."""
        self.iterations += 1
        self.input_tokens += usage.get("input_tokens", 0)

    def check_calls(self, calls: List[dict]) -> Optional[str]:
        """Count every requested call and return "repeated_call" if any identical call
        (same tool name and same input, key order ignored) has now been requested MORE
        than max_repeats times in total; otherwise None. Every call is counted, in order,
        even after a repeat has been found."""
        verdict = None
        for c in calls:
            key = (c["name"], json.dumps(c["input"], sort_keys=True))
            self.seen[key] = self.seen.get(key, 0) + 1
            if self.seen[key] > self.budget.max_repeats:
                verdict = "repeated_call"
        return verdict


# =============================================================================
# Milestone 4: the loop
# =============================================================================

def check_pairing(messages: List[dict]) -> List[str]:
    """Return the problems in a conversation history (an empty list when it is valid).

    Rules: roles alternate user, assistant, user, ... starting with user; every tool_use
    id in an assistant message is answered by exactly one tool_result with that id in the
    very next message (which must be a user message); every tool_result answers a
    tool_use from the message just before it. Each problem is a string that starts with
    "message <index>:" (0-based) and names the offending id.
    """
    problems: List[str] = []
    for i, m in enumerate(messages):
        want = "user" if i % 2 == 0 else "assistant"
        if m["role"] != want:
            problems.append(f"message {i}: expected role '{want}' but got '{m['role']}'")
        blocks = m["content"] if isinstance(m["content"], list) else []
        asked = [b["id"] for b in blocks if b.get("type") == "tool_use"]
        answered = [b["tool_use_id"] for b in blocks if b.get("type") == "tool_result"]
        previous = messages[i - 1]["content"] if i > 0 and isinstance(messages[i - 1]["content"], list) else []
        prev_ids = [b["id"] for b in previous if b.get("type") == "tool_use"] if i > 0 and messages[i - 1]["role"] == "assistant" else []
        for rid in sorted(set(answered)):
            if rid not in prev_ids:
                problems.append(f"message {i}: tool_result for '{rid}' does not answer a tool_use in the message before it")
            elif answered.count(rid) > 1:
                problems.append(f"message {i}: more than one tool_result for '{rid}'")
        if asked:
            nxt = messages[i + 1]["content"] if i + 1 < len(messages) and isinstance(messages[i + 1]["content"], list) else []
            got = {b["tool_use_id"] for b in nxt if b.get("type") == "tool_result"}
            for tid in asked:
                if tid not in got:
                    problems.append(f"message {i}: tool_use '{tid}' has no tool_result in the next message")
    return problems


def agent_loop(model: Model, question: str, registry: Registry, *, system: str = "",
               budget: Optional[Budget] = None, clock: Callable[[], float] = time.monotonic,
               max_result_chars: int = 2000, trace: Optional[Trace] = None) -> RunResult:
    """Run the tool-calling loop until the model answers or a limit stops it.

    History: starts as [{"role": "user", "content": question}]. Each iteration, in order:
      1. ask a LoopGuard (built from `budget`, default Budget(), and `clock`) whether
         another model call is allowed; if it names a reason, stop with that status;
      2. call model.complete(messages, system=system, tools=registry.definitions());
         tell the guard about its usage; append reply.as_message();
      3. no tool_use blocks in the reply -> stop: status "done" (or "truncated" when the
         stop_reason is "max_tokens");
      4. tool_use blocks but stop_reason "max_tokens" (the call was cut off): answer each
         with an error result "Not run: ...", append them, stop with "truncated";
      5. guard.check_calls(calls) names a reason ("repeated_call"): answer each call with
         an error result "Not run: ..." and stop with that reason (the history must stay valid);
      6. otherwise run every call IN ORDER with run_tool and append ONE user message whose
         content is the list of tool_result blocks.
    Whatever the exit, check_pairing(messages) must come back empty.

    The answer is the reply's text for "done" and "truncated", otherwise STOP_MESSAGES[status].
    RunResult.iterations is the number of model calls; input_tokens their summed input tokens.

    Milestone 5 adds logging: when `trace` is not None, call trace.add(...) for
      "model_call"  i, stop_reason, input_tokens, output_tokens, tools (list of requested names)
      "tool_call"   i, id, tool, input, is_error, result_chars, seconds (clock time the run took)
      "stop"        status, iterations
    in that order for each iteration, and exactly one "stop" event at the end.
    """
    raise NotImplementedError("TODO milestone 4: agent_loop")


# =============================================================================
# Milestone 5: reading a trace
# =============================================================================

def summarise(events: List[dict]) -> dict:
    """Condense a Trace's events into the numbers you read first when a run goes wrong.

    Returns a dict with exactly these keys:
      status         the status of the "stop" event ("" if there is none)
      iterations     number of "model_call" events
      input_tokens   sum of input_tokens over "model_call" events
      output_tokens  sum of output_tokens over "model_call" events
      tool_calls     number of "tool_call" events
      errors         tool_call events with is_error true
      calls_by_tool  {tool name: number of calls}
      wasted_calls   tool_call events that errored OR repeat an earlier call (same tool
                     and same input) of this run; each event counts once
      seconds        sum of "seconds" over tool_call events (rounded to 6 places)
    """
    out = {"status": "", "iterations": 0, "input_tokens": 0, "output_tokens": 0, "tool_calls": 0,
           "errors": 0, "calls_by_tool": {}, "wasted_calls": 0, "seconds": 0.0}
    seen = set()
    for e in events:
        if e["kind"] == "model_call":
            out["iterations"] += 1
            out["input_tokens"] += e["input_tokens"]
            out["output_tokens"] += e["output_tokens"]
        elif e["kind"] == "tool_call":
            out["tool_calls"] += 1
            out["calls_by_tool"][e["tool"]] = out["calls_by_tool"].get(e["tool"], 0) + 1
            key = (e["tool"], json.dumps(e["input"], sort_keys=True))
            if e["is_error"]:
                out["errors"] += 1
            if e["is_error"] or key in seen:
                out["wasted_calls"] += 1
            seen.add(key)
            out["seconds"] += e["seconds"]
        elif e["kind"] == "stop":
            out["status"] = e["status"]
    out["seconds"] = round(out["seconds"], 6)
    return out


# =============================================================================
# Milestone 6: the same loop with a text-only model (ReAct)
# =============================================================================

def parse_react(reply: str) -> dict:
    """Parse one reply in the ReAct text format. NEVER raises, whatever the text.

    The format is:
        Thought: <free text>
        Action: <tool name> <JSON object>        (the JSON is optional: no JSON means {})
    or
        Thought: <free text>
        Final Answer: <free text>

    First cut the reply at the first line that starts with "Observation:" (a model that
    writes its own observation is inventing one; the harness supplies the real one).
    Then, whichever of "Action:" / "Final Answer:" starts a line first wins. Return one of
        {"kind": "final",  "thought": str, "answer": str}
        {"kind": "action", "thought": str, "tool": str, "input": dict}
        {"kind": "error",  "message": str}     neither found, JSON that does not parse, or
                                                JSON that is not an object
    `thought` is the text after "Thought:" up to the Action/Final Answer line, stripped
    ("" when absent). `answer` is everything after "Final Answer:", stripped.
    """
    cut = re.search(r"^Observation:", reply, re.M)
    body = reply[:cut.start()] if cut else reply
    act = re.search(r"^Action:[ \t]*([A-Za-z_][\w.-]*)[ \t]*(.*)$", body, re.M)
    fin = re.search(r"^Final Answer:[ \t]*", body, re.M)
    if not act and not fin:
        return {"kind": "error", "message": "Reply with 'Action: <tool> <JSON arguments>' or 'Final Answer: <text>'."}
    use_final = fin is not None and (act is None or fin.start() < act.start())
    first = fin if use_final else act
    th = re.search(r"Thought:[ \t]*", body[:first.start()])
    thought = body[th.end():first.start()].strip() if th else ""
    if use_final:
        return {"kind": "final", "thought": thought, "answer": body[fin.end():].strip()}
    raw_args = act.group(2).strip()
    if not raw_args:
        return {"kind": "action", "thought": thought, "tool": act.group(1), "input": {}}
    try:
        parsed = json.loads(raw_args)
    except ValueError as e:
        return {"kind": "error", "message": f"The arguments of Action {act.group(1)} are not valid JSON ({e.__class__.__name__}). "
                                            "Write one JSON object on the Action line."}
    if not isinstance(parsed, dict):
        return {"kind": "error", "message": "The arguments must be a JSON object, like {\"order_id\": \"A-1001\"}."}
    return {"kind": "action", "thought": thought, "tool": act.group(1), "input": parsed}


def to_transcript(messages: List[dict]) -> str:
    """Render a native content-block history as the text a ReAct model reads.

        Question: <first user message>
        Thought: <assistant text>            (only when an assistant message has text and a tool_use)
        Action: <tool name> <input as JSON>
        Observation: <tool_result content>   (one line per result, in order)

    An assistant message without a tool_use renders as "Final Answer: <text>". One line
    per item, each ending in a newline. Use json.dumps(input) for the arguments.
    """
    lines: List[str] = []
    for m in messages:
        c = m["content"]
        if isinstance(c, str):
            lines.append(f"Question: {c}")
            continue
        if m["role"] == "user":
            for b in c:
                if b.get("type") == "tool_result":
                    lines.append(f"Observation: {b['content']}")
            continue
        uses = [b for b in c if b.get("type") == "tool_use"]
        words = "".join(b.get("text", "") for b in c if b.get("type") == "text").strip()
        if not uses:
            lines.append(f"Final Answer: {words}")
            continue
        if words:
            lines.append(f"Thought: {words}")
        for b in uses:
            lines.append(f"Action: {b['name']} {json.dumps(b['input'])}")
    return "\n".join(lines) + "\n"


def react_system(tools: List[dict], system: str = "") -> str:
    """Given: the instructions a ReAct model gets, listing the tools in plain text."""
    listing = "\n".join(f"- {t['name']}: {t['description']} Arguments (JSON Schema): {json.dumps(t['input_schema'])}" for t in tools)
    return (system + "\n" if system else "") + (
        "Answer by alternating lines. Thought: your reasoning. Action: <tool name> <JSON arguments>. "
        "Stop after the Action line; the system replies with an Observation. "
        "When you know the answer, write 'Final Answer: <answer>'.\nTools:\n" + listing)


class ReActModel(Model):
    """Wraps a TEXT-ONLY model so agent_loop can drive it like a tool-calling model.

    complete(messages, system=..., tools=...) must:
      1. build prompt = to_transcript(messages) and call
         inner.complete([{"role": "user", "content": prompt}], system=react_system(tools, system))
      2. parse_react(text_of(raw)). On kind "error" append the raw reply and
         "Observation: Format error: <message>" to the prompt and ask the inner model
         again, at most `max_format_retries` extra times.
      3. return a Response: for "final" content [text(answer)], stop_reason "end_turn"; for
         "action" content [text(thought)] (omit when empty) + [tool_use(tool, input, id=...)],
         stop_reason "tool_use". The id is f"react-{n}" where n is 1 plus the number of
         assistant messages already in `messages`. After the retries run out on an error,
         return the last raw reply as plain text with stop_reason "end_turn".
      The usage of the returned Response is the SUM of the usage of every inner call.
    """
    name = "react"

    def __init__(self, inner: Model, max_format_retries: int = 2):
        self.inner = inner
        self.max_format_retries = max_format_retries

    def complete(self, messages, *, system=None, tools=None, max_tokens=1024, temperature=0.0):
        prompt = to_transcript(messages)
        n = 1 + sum(1 for m in messages if m["role"] == "assistant")
        usage = {"input_tokens": 0, "output_tokens": 0}
        raw_text = ""
        for attempt in range(self.max_format_retries + 1):
            raw = self.inner.complete([{"role": "user", "content": prompt}],
                                      system=react_system(tools or [], system or ""), max_tokens=max_tokens)
            for k in usage:
                usage[k] += raw.usage.get(k, 0)
            raw_text = text_of(raw)
            parsed = parse_react(raw_text)
            if parsed["kind"] == "final":
                return Response([text(parsed["answer"])], "end_turn", usage, self.name)
            if parsed["kind"] == "action":
                blocks = ([text(parsed["thought"])] if parsed["thought"] else []) + \
                         [tool_use(parsed["tool"], parsed["input"], id=f"react-{n}")]
                return Response(blocks, "tool_use", usage, self.name)
            prompt += raw_text.rstrip("\n") + f"\nObservation: Format error: {parsed['message']}\n"
        return Response([text(raw_text)], "end_turn", usage, self.name)
