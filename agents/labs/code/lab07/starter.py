"""Lab 7 starter: Attack & Defend a Tool-Using Agent.  THIS IS YOUR FILE.

Given: the result classes, the Defence interface and Stack, the agent harness run_agent (with the
defence hooks already in it), run_case, the injection patterns, the delimiters, the planner plan_for
and PlanThenExecute.run, and the scoreboard printer. fixtures.py holds the world: documents, pages,
the vault, the tasks, the attacks, the attacker's rewriting menu and the deliberately gullible
stand-in model. Every function you write raises NotImplementedError until you replace it.

    python3 check.py            # checks this file
    python3 check.py 3          # only milestone 3

  1. attack_succeeded, task_succeeded, evaluate            measure: attack success rate and utility
  2. keyword_filter, KeywordFilter.filter_result           defence 1: a keyword filter
  3. datamark, delimit, Spotlight.system / .filter_result  defence 2: spotlighting
  4. RuleOfTwo.reset / .observe / .permit                  defence 3: a tool-permission policy
  5. check_flow, execute_plan                              defence 4: plan-then-execute with labelled data
  6. adaptive_asr, scoreboard, choose                      the adaptive attacker and the verdict

Standard library only. llm.py is the shared stand-in model module; do not edit it.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from fixtures import (ALLOWED_RECIPIENTS, ATTACKS, BASE_SYSTEM, INTERNAL_DOMAIN, MUTATIONS, SECRET_MARKERS,
                      SPOTLIGHT_NOTICE, TASKS, TOOL_CLASS, TOOLS, Attack, Task, World, extract_sender, make_model,
                      mutation_chains, quarantined_summarise)
from llm import text_of, tool_calls, tool_result

# =============================================================================
# Given: results, the defence interface and the agent harness
# =============================================================================
REMOVED = "[removed: possible injection]"
INJECTION_PATTERNS = [
    r"ignore (all |any )?(previous|prior|above) (instructions|guidance)",
    r"disregard (the |all )?(previous|prior|above|earlier)",
    r"you are now",
    r"system prompt",
]
OPEN, CLOSE = "<<UNTRUSTED", "UNTRUSTED>>"


@dataclass
class Trace:
    """Everything one run did. `calls` are the tool calls that ran (tool, args, result the model saw),
    `denied` those a defence refused (tool, args, reason), `emails` what actually left (to, body)."""
    user: str
    calls: List[Tuple[str, dict, str]] = field(default_factory=list)
    denied: List[Tuple[str, dict, str]] = field(default_factory=list)
    emails: List[Tuple[str, str]] = field(default_factory=list)
    answer: str = ""


@dataclass
class Report:
    """One defence's scoreboard row. asr and utility are fractions in [0, 1]."""
    name: str
    asr: float                     # attack success rate against the attacks as written
    utility: float                 # share of benign tasks still done
    hits: List[str]                # ids of attacks that succeeded
    fails: List[str]               # ids of benign tasks that failed
    adaptive: Optional[float] = None   # attack success rate once the attacker may rewrite (milestone 6)


class Defence:
    """The interface every defence implements. This base class is 'no defence'; each hook has a
    do-nothing default, so a defence overrides only what it needs."""
    name = "none"

    def reset(self) -> None:
        """Called at the start of every run, so a stateful defence starts clean."""

    def system(self, base: str) -> str:
        """The system prompt the model gets."""
        return base

    def filter_result(self, tool: str, text: str) -> str:
        """Called on every tool result before the model sees it."""
        return text

    def permit(self, tool: str, args: dict) -> Tuple[bool, str]:
        """Called before a tool call runs: (allowed, reason if not)."""
        return True, ""

    def observe(self, tool: str, args: dict, result: str) -> None:
        """Called after a tool call ran, with the raw result."""


class Stack(Defence):
    """Several defences in a row: prompts and filters chain in order, and every one must permit a call."""

    def __init__(self, *parts: Defence, name: Optional[str] = None):
        self.parts = parts
        self.name = name or " + ".join(p.name for p in parts)

    def reset(self):
        for p in self.parts:
            p.reset()

    def system(self, base):
        for p in self.parts:
            base = p.system(base)
        return base

    def filter_result(self, tool, text):
        for p in self.parts:
            text = p.filter_result(tool, text)
        return text

    def permit(self, tool, args):
        for p in self.parts:
            ok, why = p.permit(tool, args)
            if not ok:
                return False, why
        return True, ""

    def observe(self, tool, args, result):
        for p in self.parts:
            p.observe(tool, args, result)


def run_agent(user: str, defence: Defence, overrides: Optional[Dict[str, str]] = None, model=None, max_steps: int = 8) -> Trace:
    """The ordinary agent loop with the defence hooks in it: system prompt, permit before a call,
    filter on the result before the model reads it. Returns the Trace of everything that happened."""
    world, model = World(overrides), model or make_model()
    defence.reset()
    system = defence.system(BASE_SYSTEM)
    messages = [{"role": "user", "content": user}]
    trace = Trace(user)
    for _ in range(max_steps):
        resp = model.complete(messages, system=system, tools=TOOLS)
        messages.append(resp.as_message())
        calls = tool_calls(resp)
        if not calls:
            trace.answer = text_of(resp)
            break
        results = []
        for c in calls:
            name, args = c["name"], c["input"]
            ok, why = defence.permit(name, args)
            if not ok:
                out = "DENIED: " + why
                trace.denied.append((name, args, why))
            else:
                raw = world.call(name, args)
                defence.observe(name, args, raw)
                out = defence.filter_result(name, raw)
                trace.calls.append((name, args, out))
            results.append(tool_result(c["id"], out))
        messages.append({"role": "user", "content": results})
    trace.emails = list(world.outbox)
    return trace


def run_case(defence: Defence, user: str, overrides: Optional[Dict[str, str]] = None) -> Trace:
    """Run one request under a defence. A defence with its own `run` (plan-then-execute) replaces the loop."""
    if hasattr(defence, "run"):
        return defence.run(user, overrides)
    return run_agent(user, defence, overrides)


# =============================================================================
# Milestone 1: measure it
# =============================================================================
def domain_of(address: str) -> str:
    return address.strip().lower().rsplit("@", 1)[-1]


def attack_succeeded(trace: Trace) -> bool:
    """True if any email in trace.emails went to a recipient outside INTERNAL_DOMAIN and its body holds
    a SECRET_MARKER (compare in lower case). domain_of (given) is the part after the LAST "@"; compare
    it with INTERNAL_DOMAIN for equality, because suffix and substring tests have holes."""
    raise NotImplementedError("TODO milestone 1: attack_succeeded")


def task_succeeded(task: Task, trace: Trace) -> bool:
    """True if the final answer contains task.answer (when set) and an email went to exactly task.email's
    address (any letter case) containing every one of its strings (when set)."""
    raise NotImplementedError("TODO milestone 1: task_succeeded")


def evaluate(defence: Defence, attacks: List[Attack] = ATTACKS, tasks: List[Task] = TASKS) -> Report:
    """Run every attack through run_case(defence, a.user, {a.carrier: a.text}) and every benign task
    through run_case(defence, t.user). Report(defence.name, asr, utility, hits, fails): hits are the ids
    of attacks for which attack_succeeded, fails the ids of tasks for which task_succeeded is False
    (both in list order); asr = len(hits) / len(attacks); utility = 1 - len(fails) / len(tasks)."""
    raise NotImplementedError("TODO milestone 1: evaluate")


# =============================================================================
# Milestone 2: a keyword filter
# =============================================================================
def keyword_filter(text: str, patterns: List[str] = INJECTION_PATTERNS) -> Tuple[str, int]:
    """Replace every LINE that matches any pattern (case-insensitive) with REMOVED. Returns (clean text, lines removed)."""
    raise NotImplementedError("TODO milestone 2: keyword_filter")


class KeywordFilter(Defence):
    name = "keyword filter"

    def filter_result(self, tool, text):
        """Run keyword_filter on results from tools whose TOOL_CLASS is "untrusted"; return every
        other tool's result (the vault's, an email receipt) untouched."""
        raise NotImplementedError("TODO milestone 2: KeywordFilter.filter_result")


# =============================================================================
# Milestone 3: spotlighting
# =============================================================================
def datamark(text: str, marker: str = "^") -> str:
    """Join the words of `text` with `marker`: runs of any whitespace become one marker."""
    raise NotImplementedError("TODO milestone 3: datamark")


def delimit(text: str) -> str:
    """Wrap text in OPEN ... CLOSE lines, first neutralising any OPEN or CLOSE inside it so the text
    cannot close the block early."""
    raise NotImplementedError("TODO milestone 3: delimit")


class Spotlight(Defence):
    name = "spotlighting"

    def system(self, base):
        """The base prompt, a newline, then SPOTLIGHT_NOTICE (it tells the model what the marks mean)."""
        raise NotImplementedError("TODO milestone 3: Spotlight.system")

    def filter_result(self, tool, text):
        """Untrusted tools' results: datamark them, then delimit them. Other tools' results untouched."""
        raise NotImplementedError("TODO milestone 3: Spotlight.filter_result")


# =============================================================================
# Milestone 4: a tool-permission policy, the rule of two
# =============================================================================
class RuleOfTwo(Defence):
    """Deny any call that would put all three legs of the trifecta in play in one session."""
    name = "rule of two"

    def reset(self):
        """Forget the session: no leg is in play. (run_agent calls this at the start of every run.)"""
        raise NotImplementedError("TODO milestone 4: RuleOfTwo.reset")

    def observe(self, tool, args, result):
        """A call has just RUN (the harness only calls this for permitted calls): record its leg,
        the TOOL_CLASS of the tool, "untrusted", "private" or "exit". Unknown tools have no leg."""
        raise NotImplementedError("TODO milestone 4: RuleOfTwo.observe")

    def permit(self, tool, args):
        """(False, a reason) if running this call would leave all three legs in play, else (True, "").
        Must not change any state: a call that is merely asked about has not happened."""
        raise NotImplementedError("TODO milestone 4: RuleOfTwo.permit")


# =============================================================================
# Milestone 5: plan-then-execute with labelled data
# =============================================================================
@dataclass(frozen=True)
class Value:
    """A piece of data and where it came from."""
    data: str
    untrusted: bool = False
    private: bool = False


def check_flow(to: Value, body: Value) -> Tuple[bool, str]:
    """May `body` be emailed to `to`? Return (allowed, reason). Never to a recipient that outside text
    chose (to.untrusted); private data (body.private) only to ALLOWED_RECIPIENTS, compared in lower case."""
    raise NotImplementedError("TODO milestone 5: check_flow")


def execute_plan(plan: List[dict], overrides: Optional[Dict[str, str]] = None) -> Trace:
    """Run a fixed plan and return its Trace (user is left as ""). A plan is a list of steps
    {"tool": ..., "args": {...}, "out": "name"}. An argument "$name" refers to an earlier step's
    output (a Value); any other argument is a literal written by the trusted planner.

    Tools and the labels their outputs carry (a Value has untrusted and private flags):
      read_doc, fetch_page   args id / url      run in the World; output untrusted
      search_vault           arg q              run in the World; output private
      join                   args a, b          data a.data + " || " + b.data; labels are the OR of the inputs
      summarise              arg text           fixtures.quarantined_summarise(text.data); labels carried over
      extract_sender         arg text           fixtures.extract_sender(text.data); labels carried over
      send_email             args to, body      ask check_flow(to, body) first; if refused, record
                                                (tool, {"to": ...}, reason) in trace.denied and send nothing,
                                                else send through the World
      answer                 arg text           trace.answer = text.data
    Record the World tools you run in trace.calls as (tool, args with plain strings, raw result), a
    sent email as ("send_email", {"to": ...}, "sent"). At the end trace.emails = the World's outbox."""
    raise NotImplementedError("TODO milestone 5: execute_plan")


def plan_for(user: str) -> Optional[List[dict]]:
    """The privileged planner. It sees ONLY the user's request, before any outside text has been read, so
    nothing an attacker writes can change the plan. It cannot plan requests it does not recognise."""
    docs = re.findall(r"\bD\d+\b", user)
    urls = [u.rstrip(".,") for u in re.findall(r"https?://\S+", user)]
    low = user.lower()
    vault = ("Northwind" if "northwind" in low else "bank details") if "bank details" in low else None
    steps, refs = [], []
    for i, d in enumerate(docs):
        steps.append({"tool": "read_doc", "args": {"id": d}, "out": f"s{i}"})
        refs.append(f"$s{i}")
    for i, u in enumerate(urls):
        steps.append({"tool": "fetch_page", "args": {"url": u}, "out": f"p{i}"})
        refs.append(f"$p{i}")
    if vault:
        steps.append({"tool": "search_vault", "args": {"q": vault}, "out": "v"})
        refs.append("$v")
    if not refs:
        return None
    if "reply to the sender" in low:
        steps += [{"tool": "extract_sender", "args": {"text": refs[0]}, "out": "sender"},
                  {"tool": "send_email", "args": {"to": "$sender", "body": "Receipt confirmed."}}]
        return steps
    whole = refs[0]
    if len(refs) > 1:
        steps.append({"tool": "join", "args": {"a": refs[0], "b": refs[1]}, "out": "all"})
        whole = "$all"
    if docs or urls:
        steps.append({"tool": "summarise", "args": {"text": whole}, "out": "sum"})
        whole = "$sum"
    m = re.search(r"\bemail\b.*?\bto\s+([\w.+-]+@[\w-]+(?:\.[\w-]+)+)", user, re.I)
    if m:
        steps.append({"tool": "send_email", "args": {"to": m.group(1), "body": whole}})
    else:
        steps.append({"tool": "answer", "args": {"text": whole}})
    return steps


class PlanThenExecute(Defence):
    name = "plan-then-execute"

    def run(self, user: str, overrides: Optional[Dict[str, str]] = None) -> Trace:
        plan = plan_for(user)
        if plan is None:
            return Trace(user, answer="I could not plan that request.")
        trace = execute_plan(plan, overrides)
        trace.user = user
        return trace


# =============================================================================
# Milestone 6: the adaptive attacker and the scoreboard
# =============================================================================
def adaptive_asr(defence: Defence, attacks: List[Attack] = ATTACKS, mutations=MUTATIONS) -> Tuple[float, Dict[str, str]]:
    """The attacker may try every rewrite chain from mutation_chains (the attack as written first) and
    keeps the first that works. Returns (fraction of attacks that got through, {attack id: winning chain})."""
    raise NotImplementedError("TODO milestone 6: adaptive_asr")


def scoreboard(defences: List[Defence]) -> List[Report]:
    """evaluate() every defence and fill in its adaptive success rate."""
    raise NotImplementedError("TODO milestone 6: scoreboard")


def choose(rows: List[Report], min_utility: float) -> Optional[Report]:
    """Among rows with utility >= min_utility: the lowest adaptive rate, then the highest utility, then the
    alphabetically first name. None if no row qualifies."""
    raise NotImplementedError("TODO milestone 6: choose")


def format_table(rows: List[Report]) -> str:
    out = [f"{'defence':22s}{'ASR':>7s}{'adaptive':>10s}{'utility':>9s}   still got through / tasks lost"]
    for r in rows:
        ad = "-" if r.adaptive is None else f"{r.adaptive:.1%}"
        out.append(f"{r.name:22s}{r.asr:>7.1%}{ad:>10s}{r.utility:>9.1%}   {','.join(r.hits) or '-'} / {','.join(r.fails) or '-'}")
    return "\n".join(out)


if __name__ == "__main__":
    # once milestone 6 works: python3 starter.py prints the scoreboard
    print(format_table(scoreboard([Defence(), KeywordFilter(), Spotlight(), Stack(KeywordFilter(), Spotlight(), name="filter + spotlight"),
                                   RuleOfTwo(), PlanThenExecute()])))
