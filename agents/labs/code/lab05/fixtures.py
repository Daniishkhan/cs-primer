"""fixtures.py: the world Lab 5 runs in. GIVEN: do not edit.

Three things live here.

  1. The OUTSIDE WORLD: a bank and a mailer that outlive any agent process. Each keeps a record of
     what really happened (`refunds`, `emails`) and honours an idempotency key the way a real service
     does: the same key again returns the first answer without acting twice.
  2. The STAND-IN MODEL `desk_model`: a stateless function of the messages it is shown, so a
     restarted process can ask it again and get the right continuation.
  3. The CRASH MACHINERY: an `Injector` that kills the "process" at a chosen or seeded-random
     moment, and `drive`, a supervisor that restarts the agent after every crash, with no memory but
     the journal file and the world. Crash points sit before and after every model call, before and
     after every tool's effect (after the effect means "the money moved, the reply was lost"), and
     before, during (a torn write) and after every journal append.

check.py does all of its work through `drive`, so you can use it too, from a Python prompt:

    python3 -i starter.py
    >>> from fixtures import *; w = World(); path = new_journal()
    >>> drive(sys.modules["__main__"], TASKS["plain"], path, w)
"""
from __future__ import annotations

import json
import os
import random
import re
import shutil
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from llm import ScriptedModel, text_of, tool_use

LIMIT = 25.00      # refunds above this amount need a human (Milestone 4)

TASKS = {
    "plain": "Refund order 42 (20.00) and email the customer.",
    "batch": "[batch] Refund order 43 (15.00) and email the customer.",
    "twice": "[twice] Refund order 7 (10.00) twice, once for each damaged item.",
    "big": "Refund order 44 (80.00) and email the customer.",
    "bigtwice": "[twice] Refund order 8 (40.00) twice, once for each damaged item.",
    "loop": "[loop] Refund order 45 (5.00) and email the customer.",
    "poison": "[poison] Refund order 9 (10.00) after reading the attachment.",
}


class Crash(Exception):
    """Stands in for a power cut, an out-of-memory kill or a deploy. Not a bug in the agent."""


# =============================================================================
# The crash injector
# =============================================================================
class Injector:
    """Counts "crash points" and fires at one of them.

    Injector(at=k)             crash exactly once, at the k-th point (1-based), then never again.
    Injector(seed=s, p=0.05)   crash at each point with probability p, from a seeded generator.
    Injector()                 never crash, but still count points (a dry run tells you how many).
    """

    def __init__(self, at: Optional[int] = None, seed: Optional[int] = None, p: float = 0.0):
        self.at, self.p = at, p
        self.rng = random.Random(seed) if seed is not None else None
        self.count = 0
        self.crashes = 0
        self.labels: List[str] = []

    def hit(self, label: str) -> bool:
        self.count += 1
        self.labels.append(label)
        if self.at is not None:
            fire = self.count == self.at
        elif self.rng is not None:
            fire = self.rng.random() < self.p
        else:
            fire = False
        if fire:
            self.crashes += 1
        return fire

    def point(self, label: str) -> None:
        if self.hit(label):
            raise Crash(label)


# =============================================================================
# The outside world: services that outlive the agent
# =============================================================================
class World:
    """A bank, a mailer and an attachment parser. The agent process comes and goes; this stays."""

    def __init__(self, inj: Optional[Injector] = None):
        self.inj = inj or Injector()
        self.refunds: List[Dict[str, Any]] = []     # money that really moved
        self.emails: List[Dict[str, Any]] = []      # messages that really left
        self.stores: Dict[str, Dict[str, str]] = {"refund": {}, "send_email": {}}   # the services' idempotency stores
        self.executions: List[tuple] = []           # (tool, key) each time a tool body starts
        self.poison_runs = 0

    def tools(self) -> Dict[str, Callable]:
        return {"lookup_order": self.lookup_order, "refund": self.refund,
                "send_email": self.send_email, "parse_attachment": self.parse_attachment}

    def lookup_order(self, args, key):
        """Read-only. Safe to repeat; the journal lets the agent skip it anyway."""
        self.executions.append(("lookup_order", key))
        self.inj.point("lookup_order:before")
        out = f"order {args['order']}: delivered, paid 30.00"
        self.inj.point("lookup_order:after")
        return out

    def refund(self, args, key):
        """A keyed write: the same key replays the first answer and moves no money."""
        self.executions.append(("refund", key))
        self.inj.point("refund:before")
        store = self.stores["refund"]
        if key is not None and key in store:
            out = store[key]
        else:
            self.refunds.append({"order": args["order"], "amount": args["amount"], "key": key})
            out = f"refund #{len(self.refunds)} issued: {args['amount']:.2f} for order {args['order']}"
            if key is not None:
                store[key] = out
        self.inj.point("refund:after")              # the effect has happened; the reply may be lost
        return out

    def send_email(self, args, key):
        """Also keyed, like most transactional-email APIs."""
        self.executions.append(("send_email", key))
        self.inj.point("send_email:before")
        store = self.stores["send_email"]
        if key is not None and key in store:
            out = store[key]
        else:
            self.emails.append({"to": args["to"], "subject": args["subject"], "key": key})
            out = f"email #{len(self.emails)} sent to {args['to']}"
            if key is not None:
                store[key] = out
        self.inj.point("send_email:after")
        return out

    def parse_attachment(self, args, key):
        """A poison step: this file blows the parser's memory, every single time."""
        self.executions.append(("parse_attachment", key))
        self.poison_runs += 1
        raise Crash("parse_attachment: out of memory")


# =============================================================================
# The stand-in model
# =============================================================================
def desk_model(messages, tools, system):
    """A stateless function of the messages. The task text picks the script:

      plain     lookup_order, refund, send_email, final answer (one tool call per turn)
      [batch]   lookup_order, then refund AND send_email in the SAME reply, final answer
      [twice]   lookup_order, the identical refund twice in two turns, final answer
      [loop]    asks for another lookup forever (to exercise the call budget)
      [poison]  lookup_order, then parse_attachment (which kills the process), final answer

    If the latest tool results contain an error or a refusal, it stops and says so.
    """
    task = messages[0]["content"]
    m = re.search(r"order (\d+) \(([\d.]+)\)", task)
    order, amount = int(m.group(1)), float(m.group(2))
    turn = sum(1 for msg in messages if msg["role"] == "assistant")
    last = messages[-1]["content"]
    if turn and isinstance(last, list):
        bad = [b["content"] for b in last if b.get("type") == "tool_result" and b["content"].startswith(("error", "refused"))]
        if bad:
            return f"Stopped: {bad[0]}"
    lookup = tool_use("lookup_order", {"order": order})
    refund = tool_use("refund", {"order": order, "amount": amount})
    email = tool_use("send_email", {"to": f"customer-{order}@example.com", "subject": f"Refund for order {order}"})
    if "[loop]" in task:
        return [tool_use("lookup_order", {"order": order, "n": turn})]
    if "[poison]" in task:
        script = [[lookup], [tool_use("parse_attachment", {"file": "scan-17.pdf"})], [refund]]
    elif "[batch]" in task:
        script = [[lookup], [refund, email]]
    elif "[twice]" in task:
        script = [[lookup], [refund], [refund]]
    else:
        script = [[lookup], [refund], [email]]
    if turn < len(script):
        return script[turn]
    if "[twice]" in task:
        return f"Order {order} refunded twice."
    return f"Order {order} refunded and customer emailed."


def make_model() -> ScriptedModel:
    return ScriptedModel(desk_model)


class ChaosModel:
    """Wraps a model: a crash can strike before the call (nothing paid) or after it (paid, reply lost)."""

    def __init__(self, inner, inj: Injector):
        self.inner, self.inj = inner, inj

    def complete(self, messages, **kw):
        self.inj.point("model:before")
        resp = self.inner.complete(messages, **kw)
        self.inj.point("model:after")
        return resp


@contextmanager
def chaos_journal(mod, inj: Injector):
    """Replace mod.append by a version that can crash before the write, tear it in half, or crash after.
    (This is why your run() must write events through the module-level name `append`.)"""
    real = mod.append

    def append(path, event):
        inj.point("append:before")
        if inj.hit("append:torn"):
            line = json.dumps(event)
            with open(path, "a", encoding="utf-8") as f:     # half a line, no newline: a torn write
                f.write(line[: max(1, len(line) // 2)])
            raise Crash("append:torn")
        real(path, event)
        inj.point("append:after")

    mod.append = append
    try:
        yield
    finally:
        mod.append = real


# =============================================================================
# The supervisor
# =============================================================================
@dataclass
class Outcome:
    status: str                     # "done", "paused", "failed" or "budget"
    answer: Optional[str]
    restarts: int                   # crashes survived
    model_calls: int                # model calls that reached the model, over all processes
    snapshots: List[tuple]          # at each crash: (executions so far, the journal as it stood)


def new_journal() -> str:
    d = tempfile.mkdtemp(prefix="lab5-")
    return os.path.join(d, "run.jsonl")


def drop_journal(path: str) -> None:
    shutil.rmtree(os.path.dirname(path), ignore_errors=True)


def drive(mod, task: str, path: str, world: World, *, inj: Optional[Injector] = None, run_id: str = "run1",
          tools_for: Optional[Callable] = None, on_pause: Optional[Callable] = None,
          max_restarts: int = 300, **run_kw) -> Outcome:
    """Run mod.run the way a supervisor would. A Crash kills the "process"; a new one starts with no memory
    except the journal file and the world. A Paused run calls on_pause(path) (the reviewer) and restarts,
    or stops with status "paused" when there is no reviewer. RunFailed and BudgetExceeded end the run."""
    inj = inj if inj is not None else world.inj
    world.inj = inj
    restarts, model_calls, snaps = 0, 0, []
    while True:
        sm = make_model()
        model = ChaosModel(sm, inj)
        tools = tools_for(world, path) if tools_for else world.tools()
        status, answer, review = None, None, False
        try:
            with chaos_journal(mod, inj):
                answer = mod.run(task, path, model, tools, run_id=run_id, **run_kw)
            status = "done"
        except Crash:
            restarts += 1
            snaps.append((len(world.executions), mod.load(path)))
            if restarts > max_restarts:
                raise AssertionError(f"still crashing after {max_restarts} restarts; is the run making progress?")
        except mod.Paused:
            if on_pause is None:
                status = "paused"
            else:
                review = True
        except mod.RunFailed:
            status = "failed"
        except mod.BudgetExceeded:
            status = "budget"
        finally:
            model_calls += len(sm.calls)
        if review:
            on_pause(path)
        if status is not None:
            return Outcome(status, answer, restarts, model_calls, snaps)
