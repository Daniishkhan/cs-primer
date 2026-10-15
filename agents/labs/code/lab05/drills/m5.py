# Drill: A4 Lab 5, milestone 5 of 5: poison steps and a crash storm
# Everything else in this file is already written. Fill in:
#     attempts_for
# Check it with: python3 check.py 5

"""Lab 5 solution: A Durable Agent. A complete reference answer.

An agent that sends refunds and emails must survive being killed at any moment without doing
anything twice. The only thing it may rely on after a restart is a JSONL file, the journal.
The exceptions, the Step record and `digest` are given in the starter; fixtures.py holds the world (a
bank, a mailer, a stand-in model) and the crash machinery. Check this file with

    python3 check.py solution   # checks this file
    python3 check.py solution 3 # only milestone 3
    python3 check.py solution 5 12   # milestone 5, replaying ONLY the storm of seed 12

  1. append, load, rebuild                       the journal: durable lines, a torn tail, messages
  2. next_step, idempotency_key                  what to do next, and the name of an attempt
  3. run                                         the durable loop: resume, never repeat
  4. gate, review                                a human approval that survives a restart
  5. attempts_for (and run's max_attempts)       poison steps, then a crash storm

THE JOURNAL.  One JSON object per line, appended and never edited. Event types:

  {"type": "model",  "content": [blocks]}                      a model reply, exactly as received
  {"type": "result", "id": tool_use_id, "output": str}         what a tool returned; plus "is_error": true on errors
  {"type": "approval_request", "key", "args", "hash"}          a proposal waiting for a human   (Milestone 4)
  {"type": "approval", "key", "decision", "reason", "hash"}    the human's decision             (Milestone 4)
  {"type": "attempt", "seq", "id", "n"}                        "about to run this call, try n"   (Milestone 5)
  {"type": "attempt_end", "seq", "id"}                         "that attempt ended cleanly, by pausing" (Milestone 5)
  {"type": "failed", "seq", "id", "reason"}                    the run was given up on          (Milestone 5)

`seq` is the 1-based number of the model event that asked for a tool call: the first model reply is
seq 1. A tool is a function tool(args, key) -> str, where key is the idempotency key of this attempt.

Standard library only. llm.py is the shared stand-in model module; do not edit it.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from llm import text_of, tool_result


# =============================================================================
# Given: exceptions, the Step record and the argument digest
# =============================================================================
class CorruptJournal(Exception):
    """A line in the MIDDLE of the journal is not valid JSON. (A torn last line is normal, not this.)"""


class Paused(Exception):
    """The run is waiting for a human. The process may exit; nothing is lost."""

    def __init__(self, key: str):
        super().__init__(f"waiting for approval of {key}")
        self.key = key


class RunFailed(Exception):
    """The run was given up on (a step kept killing the process). A human must look at it."""


class BudgetExceeded(Exception):
    """The journal already holds the maximum number of model replies."""


class ToolError(Exception):
    """A tool refused in a way the model can read and react to (a business error, not a crash)."""


@dataclass
class Step:
    """What the next_step function decides. kind is one of:

    "ask_model"   the model must be asked what to do next
    "run_tools"   the tool calls in `calls` (tool_use blocks, in order) have no result yet; `seq` is the
                  1-based number of the model event that asked for them
    "finish"      the last model reply asked for nothing; `text` is the final answer
    """
    kind: str
    seq: int = 0
    calls: List[Dict[str, Any]] = field(default_factory=list)
    text: str = ""


def digest(args: Dict[str, Any]) -> str:
    """Eight hex characters that identify the exact arguments of a call (used by approvals)."""
    return hashlib.sha256(json.dumps(args, sort_keys=True).encode()).hexdigest()[:8]


# =============================================================================
# Milestone 1: the journal
# =============================================================================
def append(path: str, event: Dict[str, Any]) -> None:
    """Add one event to the end of the journal file, durably.

    One line per event: json.dumps(event) + "\\n". The line must be on disk (flush, then os.fsync)
    before append returns: an event counts only once it is durable. If the file's last line is torn
    (a crash left half a line with no newline), cut it off before writing, so the new event does
    not glue itself onto the wreckage. Never rewrite earlier events.
    """
    if os.path.exists(path):
        with open(path, "rb+") as f:                      # cut off a torn last line, if there is one
            data = f.read()
            if data and not data.endswith(b"\n"):
                f.truncate(data.rfind(b"\n") + 1)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")                # json.dumps escapes newlines inside strings
        f.flush()
        os.fsync(f.fileno())                              # on disk before we go on


def load(path: str) -> List[Dict[str, Any]]:
    """All events in the journal, in order. A missing file is an empty journal.

    A last line with no newline is a torn write: it does not count, so leave it out. A line before
    the last that is not valid JSON means the journal is damaged: raise CorruptJournal.
    """
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        lines = f.read().split("\n")
    lines.pop()                                           # "" after the final newline, or a torn last line
    events = []
    for number, line in enumerate(lines, 1):
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            raise CorruptJournal(f"line {number} of {path} is not valid JSON") from None
    return events


def rebuild(task: str, log: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Fold the journal into the message list the model sees.

    [{"role": "user", "content": task}], then each "model" event as an assistant message with that
    content, and the "result" events that follow it gathered into ONE user message of tool_result
    blocks (use llm.tool_result(id, output, is_error)), in order. Other event types are not part of
    the conversation. Do not modify the events in `log`.
    """
    messages: List[Dict[str, Any]] = [{"role": "user", "content": task}]
    for ev in log:
        if ev["type"] == "model":
            messages.append({"role": "assistant", "content": ev["content"]})
        elif ev["type"] == "result":
            if messages[-1]["role"] == "assistant":       # the first result after a reply opens a new user message
                messages.append({"role": "user", "content": []})
            messages[-1]["content"].append(tool_result(ev["id"], ev["output"], ev.get("is_error", False)))
    return messages


# =============================================================================
# Milestone 2: what to do next
# =============================================================================
def next_step(log: List[Dict[str, Any]]) -> Step:
    """Decide the next move from the journal alone. Only "model" and "result" events matter here.

    - no model event yet: ask the model.
    - the last model reply has tool_use blocks: those whose id has no "result" event AFTER that model
      event are pending. Any pending: run_tools (seq = number of model events so far, calls in the
      order of the blocks). None pending: ask the model.
    - the last model reply has no tool_use block: finish, with the text blocks joined (llm.text_of).

    Careful: a model may legitimately make the identical call (same id) in two different turns. A
    result from an earlier turn must not make the later call look done.
    """
    last = max((i for i, e in enumerate(log) if e["type"] == "model"), default=None)
    if last is None:
        return Step("ask_model")
    seq = sum(1 for e in log if e["type"] == "model")
    uses = [b for b in log[last]["content"] if b.get("type") == "tool_use"]
    if not uses:
        return Step("finish", text=text_of({"content": log[last]["content"]}))
    done = {e["id"] for e in log[last + 1:] if e["type"] == "result"}   # only results AFTER the last reply
    pending = [u for u in uses if u["id"] not in done]
    return Step("run_tools", seq=seq, calls=pending) if pending else Step("ask_model")


def idempotency_key(run_id: str, seq: int, tool_use_id: str) -> str:
    """The key sent with every attempt at one tool call: "run1:2:toolu_ab12cd34ef".

    It must be computable from things already in the journal, so that every attempt, in every
    process, derives the same string; and it must differ between two identical-looking calls made in
    different turns.
    """
    return f"{run_id}:{seq}:{tool_use_id}"


# =============================================================================
# Milestone 3 (and 5): the durable loop
# =============================================================================
def run(task: str, path: str, model, tools: Dict[str, Callable], run_id: str = "run1",
        max_calls: int = 8, max_attempts: Optional[int] = None, tool_defs: Optional[list] = None) -> str:
    """Run the task to the end, resuming from the journal at `path`. Returns the final answer.

    Repeat: load the journal, ask next_step, and
      finish     -> return the text.
      run_tools  -> for each pending call, in order: compute its key, call tools[name](input, key),
                    and append a "result" event (output; plus "is_error": True for errors).
                    An unknown tool name or a ToolError becomes an error result ("error: unknown tool
                    'x'" / "error: <message>") that the model sees, not an exception. Any other
                    exception (a Crash, say) must NOT be caught.
      ask_model  -> if the journal already holds max_calls model events, raise BudgetExceeded without
                    calling the model. Otherwise model.complete(rebuild(task, log), tools=tool_defs or [])
                    and append the reply as a "model" event with resp.content.

    Write events only through `append(path, event)` and read only through `load(path)` (the module-level
    names), because check.py swaps in versions that crash on purpose. Keep NO state in variables across
    loop iterations: everything comes from the journal. Do not catch Paused.

    Milestone 5 adds max_attempts (None = off, and then no attempt events are written at all):
      before running a pending call, n = attempts_for(log, seq, id). If n >= max_attempts append
      {"type": "failed", "seq", "id", "reason"} and raise RunFailed. Otherwise append
      {"type": "attempt", "seq", "id", "n": n + 1} and then run the tool. If the tool raises Paused,
      append {"type": "attempt_end", "seq", "id"} and re-raise (a pause is not a failure).
      A journal that already contains a "failed" event raises RunFailed at once.
    """
    while True:
        log = load(path)
        if any(e["type"] == "failed" for e in log):
            raise RunFailed("this run was given up on earlier")
        step = next_step(log)
        if step.kind == "finish":
            return step.text
        if step.kind == "run_tools":
            for call in step.calls:
                key = idempotency_key(run_id, step.seq, call["id"])
                if max_attempts is not None:
                    n = attempts_for(log, step.seq, call["id"])
                    if n >= max_attempts:
                        append(path, {"type": "failed", "seq": step.seq, "id": call["id"],
                                      "reason": f"{call['name']} did not finish in {n} attempts"})
                        raise RunFailed(f"{call['name']} did not finish in {n} attempts")
                    append(path, {"type": "attempt", "seq": step.seq, "id": call["id"], "n": n + 1})
                event = {"type": "result", "id": call["id"]}
                tool = tools.get(call["name"])
                try:
                    if tool is None:
                        raise ToolError(f"unknown tool {call['name']!r}")
                    event["output"] = tool(call["input"], key)    # the side effect happens here
                except ToolError as e:
                    event["output"], event["is_error"] = f"error: {e}", True
                except Paused:
                    if max_attempts is not None:
                        append(path, {"type": "attempt_end", "seq": step.seq, "id": call["id"]})
                    raise
                append(path, event)                               # ...and only now does the journal know
        else:
            if sum(1 for e in log if e["type"] == "model") >= max_calls:
                raise BudgetExceeded(f"{max_calls} model replies are already in the journal")
            resp = model.complete(rebuild(task, log), tools=tool_defs or [])
            append(path, {"type": "model", "content": resp.content})


# =============================================================================
# Milestone 4: a human approval that survives a restart
# =============================================================================
def gate(fn: Callable, path: str, limit: float) -> Callable:
    """Wrap a tool so that amounts above `limit` wait for a human.

    wrapped(args, key):
      amount = args["amount"]; if amount <= limit, just return fn(args, key).
      Otherwise look in the journal for an "approval" event with this key.
        none yet -> unless an "approval_request" with this key already exists, append one
                    {"type": "approval_request", "key": key, "args": args, "hash": digest(args)};
                    then raise Paused(key).
        found, but its hash differs from digest(args) -> return "error: approval was granted for different arguments".
        found, decision is not "approve" -> return "refused by reviewer: " + its reason.
        found and approved -> return fn(args, key).
    """
    def wrapped(args, key):
        if args["amount"] <= limit:
            return fn(args, key)
        events = load(path)
        verdict = next((e for e in events if e["type"] == "approval" and e["key"] == key), None)
        if verdict is None:
            if not any(e["type"] == "approval_request" and e["key"] == key for e in events):
                append(path, {"type": "approval_request", "key": key, "args": args, "hash": digest(args)})
            raise Paused(key)                                     # the process may now exit
        if verdict["hash"] != digest(args):
            return "error: approval was granted for different arguments"
        if verdict["decision"] != "approve":
            return "refused by reviewer: " + verdict["reason"]
        return fn(args, key)
    return wrapped


def review(path: str, decision: str, reason: str = "", shown: Optional[str] = None) -> Dict[str, Any]:
    """The reviewer's side: answer the oldest approval_request that has no approval yet.

    decision must be "approve" or "deny" (ValueError otherwise). Append and return
    {"type": "approval", "key": <the request's key>, "decision", "reason", "hash": shown or <the request's hash>}.
    `shown` is the hash of what the reviewer was actually shown; leave it out to approve exactly what was
    requested. Raise LookupError when nothing is waiting.
    """
    if decision not in ("approve", "deny"):
        raise ValueError(f"decision must be 'approve' or 'deny', not {decision!r}")
    events = load(path)
    answered = {e["key"] for e in events if e["type"] == "approval"}
    waiting = [e for e in events if e["type"] == "approval_request" and e["key"] not in answered]
    if not waiting:
        raise LookupError("no approval request is waiting")
    req = waiting[0]
    event = {"type": "approval", "key": req["key"], "decision": decision, "reason": reason, "hash": shown or req["hash"]}
    append(path, event)
    return event


# =============================================================================
# Milestone 5: poison steps
# =============================================================================
def attempts_for(log: List[Dict[str, Any]], seq: int, tool_use_id: str) -> int:
    """How many attempts at this call (seq, id) started and did not end cleanly.

    The number of "attempt" events for the call, minus the number of "attempt_end" events for it.
    """
    raise NotImplementedError("TODO milestone 5: attempts_for")


if __name__ == "__main__":
    # A tiny demo you can run once Milestone 3 works: python3 starter.py
    import tempfile
    from fixtures import TASKS, World, make_model
    world = World()
    journal = os.path.join(tempfile.mkdtemp(), "run.jsonl")
    print(run(TASKS["plain"], journal, make_model(), world.tools()))
    print("refunds:", world.refunds)
    print(open(journal).read(), end="")
