"""Self-check for Lab 5: A Durable Agent.

    python3 check.py                  # checks your starter.py
    python3 check.py solution         # checks the reference solution
    python3 check.py solution 3       # only milestone 3
    python3 check.py solution 5 12    # milestone 5, replaying ONLY the crash storm of seed 12

Everything is deterministic. The "outside world" (a bank and a mailer) is in fixtures.py, the model is a
stand-in, and every crash is injected on purpose: at a chosen moment (Milestones 3 and 4 try EVERY
moment, one run per moment) or from a seeded random generator (Milestone 5). A failure prints the crash
point or the seed so you can replay it. No network, no real clock; the whole check takes a few seconds.
Prints a tick, a cross, or "not implemented yet" for each milestone.
"""
import importlib
import json
import os
import random
import signal
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True

args = sys.argv[1:]
target = args[0] if args and not args[0].isdigit() else "starter"
rest = [a for a in args if a.isdigit()]
ONLY = int(rest[0]) if rest else None
ONLY_SEED = int(rest[1]) if len(rest) > 1 else None
mod = importlib.import_module(target)
from fixtures import LIMIT, TASKS, Crash, Injector, World, drive, drop_journal, make_model, new_journal  # noqa: E402
from llm import ScriptedModel, text, tool_result, tool_use  # noqa: E402

results = []
CORE = ("model", "result", "approval_request", "approval")


def seeds(default):
    return [ONLY_SEED] if ONLY_SEED is not None else list(default)


def check(number, name, fn):
    if ONLY is not None and ONLY != number:
        return
    if hasattr(signal, "SIGALRM"):                 # a loop that never ends is a failure, not a hang
        def _timeout(signum, frame):
            raise AssertionError("no answer after 25 seconds: is some loop not making progress (a call budget, a pending call that never gets its result)?")
        signal.signal(signal.SIGALRM, _timeout)
        signal.alarm(25)
    try:
        note = fn()
        print(f"  ✔ {name}")
        for line in (note or "").splitlines():
            print(f"      {line}")
        results.append(True)
    except NotImplementedError as e:
        print(f"  … {name}: not implemented yet ({e})")
        results.append(False)
    except AssertionError as e:
        print(f"  ✘ {name}: {e}")
        results.append(False)
    except Exception as e:
        import traceback
        tb = traceback.extract_tb(e.__traceback__)
        where = next((f"{f.name}() line {f.lineno}" for f in reversed(tb) if f.filename.endswith(f"{target}.py")), "?")
        print(f"  ✘ {name}: {type(e).__name__}: {e}   [in {where}]")
        results.append(False)
    finally:
        if hasattr(signal, "SIGALRM"):
            signal.alarm(0)


# ---------------------------------------------------------------- helpers
PATHS = []


def journal():
    p = new_journal()
    PATHS.append(p)
    return p


def write_raw(path, events, tail=""):
    with open(path, "w", encoding="utf-8") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")
        f.write(tail)


def core(events):
    return [e for e in events if e["type"] in CORE]


def gated_tools(world, path):
    return {**world.tools(), "refund": mod.gate(world.refund, path, LIMIT)}


def approver(decision="approve", reason="", shown=None):
    return lambda path: mod.review(path, decision, reason, shown)


class Capped:
    """A model that fails the check, instead of looping for ever, if it is asked too many times."""

    def __init__(self, inner, limit=40):
        self.inner, self.limit = inner, limit
        self.calls = inner.calls

    def complete(self, messages, **kw):
        assert len(self.inner.calls) < self.limit, f"the model was called {self.limit} times: the loop is not stopping (is the call budget checked?)"
        return self.inner.complete(messages, **kw)


def call(name, **inp):
    return tool_use(name, inp)


L42, R42 = call("lookup_order", order=42), call("refund", order=42, amount=20.0)
E42 = call("send_email", to="customer-42@example.com", subject="Refund for order 42")
PLAIN = [
    {"type": "model", "content": [L42]},
    {"type": "result", "id": L42["id"], "output": "order 42: delivered, paid 30.00"},
    {"type": "model", "content": [R42]},
    {"type": "result", "id": R42["id"], "output": "refund #1 issued: 20.00 for order 42"},
    {"type": "model", "content": [E42]},
    {"type": "result", "id": E42["id"], "output": "email #1 sent to customer-42@example.com"},
    {"type": "model", "content": [text("Order 42 refunded and customer emailed.")]},
]

# what the world must look like at the end of each task, however many crashes happened on the way
EXPECT = {"plain": (1, 1), "batch": (1, 1), "twice": (2, 0), "big": (1, 1), "bigtwice": (2, 0)}


def reference(kind):
    """The uninterrupted run of a task: its journal (core events), its point count and the world."""
    w, p = World(), journal()
    out = drive(mod, TASKS[kind], p, w, tools_for=gated_tools, on_pause=approver())
    assert out.status == "done" and out.restarts == 0, f"the uninterrupted '{kind}' run should simply finish; got {out.status}"
    return core(mod.load(p)), w.inj.count, out.answer


def result_keys(events, run_id="run1"):
    """The key each journaled result was produced under (derived independently of your code)."""
    keys, seq = set(), 0
    for e in events:
        if e["type"] == "model":
            seq += 1
        elif e["type"] == "result":
            keys.add(f"{run_id}:{seq}:{e['id']}")
    return keys


# =============================================================================
# Milestone 1: the journal
# =============================================================================
def m1():
    p = journal()
    assert mod.load(p) == [], "a journal that does not exist yet is an empty list"
    evs = [{"type": "model", "content": [text("héllo £4.20\nsecond line")]},
           {"type": "result", "id": "t1", "output": "line one\nline two"},
           {"type": "result", "id": "t2", "output": "ok", "is_error": True}]
    syncs = []
    real_fsync = os.fsync
    os.fsync = lambda fd: (syncs.append(fd), real_fsync(fd))[1]
    try:
        for e in evs:
            mod.append(p, e)
    finally:
        os.fsync = real_fsync
    assert len(syncs) >= 3, f"append must os.fsync the file every time (an event counts only once it is on disk); fsync was called {len(syncs)} times for 3 appends"
    assert mod.load(p) == evs, f"load should give back exactly what was appended, in order; got {mod.load(p)}"
    raw = open(p, encoding="utf-8").read()
    assert raw.endswith("\n") and len(raw.splitlines()) == 3, f"one event per line, each ending in a newline (newlines inside strings must be escaped); the file holds {len(raw.splitlines())} lines"
    before = open(p, "rb").read()
    mod.append(p, {"type": "model", "content": [text("more")]})
    assert open(p, "rb").read().startswith(before), "append must only add to the end; earlier bytes were changed"
    # a torn tail: half a line, no newline
    q = journal()
    write_raw(q, evs[:2], tail='{"type": "result", "id": "t3", "outp')
    assert mod.load(q) == evs[:2], f"a last line without a newline is a torn write and must be ignored; load gave {mod.load(q)}"
    mod.append(q, evs[2])
    assert mod.load(q) == evs, "after a torn tail, append must cut the wreckage off first, otherwise the new event glues onto it and is lost"
    assert all(json.loads(line) for line in open(q, encoding="utf-8").read().splitlines()), "every line left in the file must be valid JSON"
    # a torn tail on its own, and nothing but garbage
    write_raw(q, [], tail='{"type"')
    assert mod.load(q) == [], "a journal whose only line is torn is empty"
    # damage in the middle is not a torn write
    write_raw(q, evs[:1], tail="")
    with open(q, "a", encoding="utf-8") as f:
        f.write("this is not json\n" + json.dumps(evs[1]) + "\n")
    try:
        mod.load(q)
    except mod.CorruptJournal:
        pass
    else:
        raise AssertionError("a bad line in the MIDDLE of the journal means damage, not a crash: raise CorruptJournal")
    # rebuild
    log = [{"type": "model", "content": [text("Checking."), L42, R42]},
           {"type": "result", "id": L42["id"], "output": "order 42: delivered, paid 30.00"},
           {"type": "approval_request", "key": "k", "args": {}, "hash": "h"},
           {"type": "result", "id": R42["id"], "output": "error: nope", "is_error": True},
           {"type": "model", "content": [text("Done.")]}]
    snapshot = json.dumps(log, sort_keys=True)
    got = mod.rebuild("Refund order 42", log)
    want = [{"role": "user", "content": "Refund order 42"},
            {"role": "assistant", "content": [text("Checking."), L42, R42]},
            {"role": "user", "content": [tool_result(L42["id"], "order 42: delivered, paid 30.00"), tool_result(R42["id"], "error: nope", True)]},
            {"role": "assistant", "content": [text("Done.")]}]
    assert got == want, f"rebuild gave\n        {got}\n      expected\n        {want}"
    assert json.dumps(log, sort_keys=True) == snapshot, "rebuild must not modify the events it is given"
    assert mod.rebuild("t", []) == [{"role": "user", "content": "t"}], "an empty journal rebuilds to just the task"
    # property: random conversations rebuild into a well-formed alternating transcript
    for seed in seeds(range(1, 26)):
        rnd = random.Random(seed)
        events, expect_ids = [], []
        turns = rnd.randint(1, 5)
        for turn in range(turns):
            n = rnd.randint(0 if turn == turns - 1 else 1, 3)         # only the last reply may ask for nothing
            uses = [call("lookup_order", order=rnd.randint(1, 3), n=i) for i in range(n)]
            events.append({"type": "model", "content": [text(f"turn {turn}")] + uses})
            expect_ids.append([u["id"] for u in uses])
            for u in uses:
                if rnd.random() < 0.3:
                    events.append({"type": "approval", "key": "k", "decision": "approve", "reason": "", "hash": "h"})
                events.append({"type": "result", "id": u["id"], "output": f"r{rnd.randint(0, 99)}"})
        msgs = mod.rebuild("task", events)
        roles = [m["role"] for m in msgs]
        assert roles[0] == "user" and all(a != b for a, b in zip(roles, roles[1:])), f"seed {seed}: roles must alternate user/assistant; got {roles}"
        answered = [[b["tool_use_id"] for b in m["content"]] for m in msgs[2:] if m["role"] == "user"]
        assert answered == [ids for ids in expect_ids if ids], f"seed {seed}: each user message must hold the results of the previous reply, in order; got {answered}, expected {[i for i in expect_ids if i]}"
    return "durable one-line appends, torn-tail repair, damage detection, and rebuild (25 random conversations)"


# =============================================================================
# Milestone 2: what to do next
# =============================================================================
def m2():
    S = mod.Step
    assert mod.idempotency_key("run1", 2, "toolu_abc") == "run1:2:toolu_abc", f"expected 'run1:2:toolu_abc'; got {mod.idempotency_key('run1', 2, 'toolu_abc')!r}"
    assert mod.idempotency_key("run1", 2, "t") != mod.idempotency_key("run1", 3, "t"), "the same tool_use id in two different turns must give two different keys"
    assert mod.idempotency_key("run1", 2, "t") != mod.idempotency_key("run2", 2, "t"), "two runs must not share keys"
    a, b = call("lookup_order", order=1), call("lookup_order", order=2)
    ra, rb = {"type": "result", "id": a["id"], "output": "x"}, {"type": "result", "id": b["id"], "output": "y"}
    noise = {"type": "approval_request", "key": "k", "args": {}, "hash": "h"}

    def step(log):
        s = mod.next_step(log)
        return s.kind, s.seq, [c["id"] for c in s.calls], s.text

    cases = [
        ("empty journal", [], ("ask_model", 0, [], "")),
        ("a reply that asked for two tools", [{"type": "model", "content": [a, b]}], ("run_tools", 1, [a["id"], b["id"]], "")),
        ("one of the two done", [{"type": "model", "content": [a, b]}, ra], ("run_tools", 1, [b["id"]], "")),
        ("only the second done (e.g. interleaved)", [{"type": "model", "content": [a, b]}, rb], ("run_tools", 1, [a["id"]], "")),
        ("both done", [{"type": "model", "content": [a, b]}, ra, rb], ("ask_model", 0, [], "")),
        ("final text", [{"type": "model", "content": [text("All "), text("done.")]}], ("finish", 0, [], "All done.")),
        ("text and a tool call together", [{"type": "model", "content": [text("Let me check."), a]}], ("run_tools", 1, [a["id"]], "")),
        ("approval events are ignored", [{"type": "model", "content": [a]}, noise, ra, noise], ("ask_model", 0, [], "")),
        ("seq counts model events", [{"type": "model", "content": [a]}, ra, {"type": "model", "content": [b]}], ("run_tools", 2, [b["id"]], "")),
        ("finish after tools", [{"type": "model", "content": [a]}, ra, {"type": "model", "content": [text("ok")]}], ("finish", 0, [], "ok")),
        ("the SAME call in a later turn is not already done",
         [{"type": "model", "content": [a]}, ra, {"type": "model", "content": [a]}], ("run_tools", 2, [a["id"]], "")),
        ("an old result for an id the last reply did not ask for",
         [{"type": "model", "content": [a]}, ra, {"type": "model", "content": [b]}, ra], ("run_tools", 2, [b["id"]], "")),
    ]
    for name, log, want in cases:
        got = step(log)
        if got[0] == "run_tools":
            assert got == want, f"{name}: expected {want}; got {got}"
        else:
            assert got[0] == want[0] and (got[3] == want[3]), f"{name}: expected kind {want[0]!r} text {want[3]!r}; got kind {got[0]!r} text {got[3]!r}"
    # property: every prefix of a random valid journal gets the move an independent oracle expects
    for seed in seeds(range(1, 31)):
        rnd = random.Random(seed)
        pool = [call("lookup_order", order=i) for i in (1, 2, 3)]            # few calls, so ids repeat across turns
        events, marks = [], []
        turns = rnd.randint(1, 5)
        for t in range(turns):
            uses = rnd.sample(pool, rnd.randint(0, 3))
            events.append({"type": "model", "content": [text(f"t{t}")] + uses})
            marks.append(("model", t + 1, uses, 0))
            for i, u in enumerate(uses):
                if rnd.random() < 0.3:
                    events.append(noise)
                    marks.append(("noise", t + 1, uses, i))
                events.append({"type": "result", "id": u["id"], "output": "r"})
                marks.append(("result", t + 1, uses, i))
        for n in range(len(events) + 1):
            if n == 0:
                want = ("ask_model", 0, [])
            else:
                kind, seq, uses, i = marks[n - 1]
                if kind == "model":
                    want = ("run_tools", seq, [u["id"] for u in uses]) if uses else ("finish", 0, [])
                else:
                    done = i + 1 if kind == "result" else i
                    left = [u["id"] for u in uses[done:]]
                    want = ("run_tools", seq, left) if left else ("ask_model", 0, [])
            got = step(events[:n])[:3]
            assert got == want, f"seed {seed}, after {n} events: expected {want}; got {got}"
    return "twelve hand-made journals, and every prefix of 30 random journals with repeated calls"


# =============================================================================
# Milestone 3: the durable loop
# =============================================================================
def m3():
    # 1. an uninterrupted run
    w, p = World(), journal()
    model = make_model()
    answer = mod.run(TASKS["plain"], p, model, w.tools())
    assert answer == "Order 42 refunded and customer emailed.", f"final answer wrong: {answer!r}"
    assert mod.load(p) == PLAIN, "the journal of the plain task should hold exactly these 7 events:\n      " + "\n      ".join(map(str, PLAIN)) + "\n    got:\n      " + "\n      ".join(map(str, mod.load(p)))
    assert len(model.calls) == 4, f"four model replies were needed; the model was called {len(model.calls)} times"
    assert [m["role"] for m in model.calls[2]["messages"]] == ["user", "assistant", "user", "assistant", "user"], "the third model call must see the rebuilt conversation so far"
    keys = [(t, k) for t, k in w.executions]
    want = [("lookup_order", f"run1:1:{L42['id']}"), ("refund", f"run1:2:{R42['id']}"), ("send_email", f"run1:3:{E42['id']}")]
    assert keys == want, f"every tool call must receive its idempotency key (run_id:seq:tool_use_id); expected {want}; got {keys}"
    # 2. a finished journal replays: nothing runs, nobody is asked
    w2, model2 = World(), make_model()
    assert mod.run(TASKS["plain"], p, model2, w2.tools()) == answer and not model2.calls and not w2.executions, \
        "running a task whose journal is already complete must return the answer without calling the model or any tool"
    # 3. resume from a prefix: the lookup is in the journal, so it is not run again
    w3, q = World(), journal()
    write_raw(q, PLAIN[:2])
    model3 = make_model()
    assert mod.run(TASKS["plain"], q, model3, w3.tools()) == answer
    assert [t for t, _ in w3.executions] == ["refund", "send_email"], f"completed results must be replayed from the journal, not re-run; tools executed after resuming: {[t for t, _ in w3.executions]}"
    assert len(model3.calls) == 3, f"resuming after the first result needs 3 more model replies; got {len(model3.calls)}"
    # 4. the identical call in two turns is two calls with two keys
    w4, r = World(), journal()
    mod.run(TASKS["twice"], r, make_model(), w4.tools())
    assert len(w4.refunds) == 2 and w4.refunds[0]["key"] != w4.refunds[1]["key"], f"the model asked for the same refund in two turns: two refunds, two different keys; got {w4.refunds}"
    # 5. two calls in one reply run in order
    w5, s = World(), journal()
    mod.run(TASKS["batch"], s, make_model(), w5.tools())
    assert [t for t, _ in w5.executions] == ["lookup_order", "refund", "send_email"] and len(w5.refunds) == 1 and len(w5.emails) == 1, f"batch task: expected lookup, refund, email once each; got {[t for t, _ in w5.executions]}"
    # 6. errors become results the model can read
    def script(messages, tools, system):
        n = sum(1 for m in messages if m["role"] == "assistant")
        return [[tool_use("nope", {})], [tool_use("locked", {"order": 1})], "fine"][n]
    def locked(a, k):
        raise mod.ToolError("order is locked")
    t, u = journal(), ScriptedModel(script)
    assert mod.run("go", t, u, {"locked": locked}) == "fine"
    errs = [e for e in mod.load(t) if e["type"] == "result"]
    assert [(e["output"], e.get("is_error")) for e in errs] == [("error: unknown tool 'nope'", True), ("error: order is locked", True)], f"an unknown tool and a ToolError both become error results; got {errs}"
    assert u.calls[2]["messages"][-1]["content"][0]["is_error"] is True, "the model must see is_error on the tool_result block"
    # 7. a Crash inside a tool is not caught
    def boom(a, k):
        raise Crash("power cut")
    try:
        mod.run("go", journal(), ScriptedModel(lambda m, t_, s: [tool_use("boom", {})]), {"boom": boom})
    except Crash:
        pass
    else:
        raise AssertionError("run must not catch arbitrary exceptions: a Crash has to kill the process")
    # 8. the call budget lives in the journal
    w8, v = World(), journal()
    try:
        mod.run(TASKS["loop"], v, Capped(make_model()), w8.tools(), max_calls=4)
    except mod.BudgetExceeded:
        pass
    else:
        raise AssertionError("a model that never stops asking for tools must hit BudgetExceeded")
    assert sum(e["type"] == "model" for e in mod.load(v)) == 4, "BudgetExceeded after exactly max_calls model replies"
    fresh = make_model()
    try:
        mod.run(TASKS["loop"], v, Capped(fresh), w8.tools(), max_calls=4)
    except mod.BudgetExceeded:
        pass
    assert not fresh.calls, "a restart must not refill the budget: the count comes from the journal, so the model is not called again"
    # 9. kill it at EVERY crash point, once per run
    total, lines = 0, []
    for kind in ("plain", "batch", "twice"):
        ref, points, _ = reference(kind)
        refunds, emails = EXPECT[kind]
        model_events = sum(e["type"] == "model" for e in ref)
        for k in range(1, points + 1):
            world, path = World(), journal()
            inj = Injector(at=k)
            where = f"task '{kind}', crash point {k} of {points} ({{label}})"
            out = drive(mod, TASKS[kind], path, world, inj=inj)
            where = where.format(label=inj.labels[k - 1])
            assert out.status == "done" and out.restarts == 1, f"{where}: the run should survive its one crash and finish; status {out.status}, restarts {out.restarts}"
            assert (len(world.refunds), len(world.emails)) == (refunds, emails), f"{where}: expected {refunds} refund(s) and {emails} email(s) in the world; got {len(world.refunds)} and {len(world.emails)}. Is the key identical on every attempt?"
            assert core(mod.load(path)) == ref, f"{where}: the journal after the crash and restart should be identical to the uninterrupted run's"
            assert out.model_calls <= model_events + 1, f"{where}: {out.model_calls} model calls for {model_events} replies; only the interrupted call may be repeated"
            n_exec, snap = out.snapshots[0]
            again = [k_ for _, k_ in world.executions[n_exec:] if k_ in result_keys(snap)]
            assert not again, f"{where}: re-ran a call whose result was already in the journal: {again}"
            total += 1
        lines.append(f"{kind}: {points} crash points")
    return f"{total} runs, one per crash point, each killed once and restarted:\n" + "; ".join(lines) + "\nevery refund and email exactly once, journals identical to the uninterrupted run"


# =============================================================================
# Milestone 4: a human approval that survives a restart
# =============================================================================
def m4():
    big = call("refund", order=44, amount=80.0)
    key = f"run1:2:{big['id']}"
    shown = {"order": 44, "amount": 80.0}
    # unit: the limit is inclusive
    calls = []
    p0 = journal()
    g = mod.gate(lambda a, k: calls.append((a, k)) or "done", p0, 25.0)
    assert g({"amount": 25.0}, "k1") == "done" and g({"amount": 5.0}, "k2") == "done" and mod.load(p0) == [], "amounts up to and including the limit pass straight through and write nothing"
    try:
        g({"amount": 25.01}, "k3")
    except mod.Paused as e:
        assert e.key == "k3", f"Paused should carry the key; got {e.key!r}"
    else:
        raise AssertionError("25.01 is above the limit of 25.00: the gate must raise Paused")
    # process 1: proposes and exits
    world, path = World(), journal()
    o1 = drive(mod, TASKS["big"], path, world, tools_for=gated_tools)
    assert o1.status == "paused", f"with no reviewer the run must stop paused; got {o1.status}"
    ev = mod.load(path)
    assert [e["type"] for e in ev] == ["model", "result", "model", "approval_request"], f"journal while waiting should be model, result, model, approval_request; got {[e['type'] for e in ev]}"
    assert ev[-1] == {"type": "approval_request", "key": key, "args": shown, "hash": mod.digest(shown)}, f"the request must carry the key, the exact arguments and their digest; got {ev[-1]}"
    assert world.refunds == [] and o1.model_calls == 2, f"nothing may happen before approval; refunds {world.refunds}, model calls {o1.model_calls} (expected 2)"
    # process 2: still waiting, and does not file a second request
    o2 = drive(mod, TASKS["big"], path, world, tools_for=gated_tools)
    assert o2.status == "paused" and o2.model_calls == 0, f"a restart with no decision pauses again without asking the model anything; got {o2.status}, {o2.model_calls} model calls"
    assert sum(e["type"] == "approval_request" for e in mod.load(path)) == 1, "asking again must not file a duplicate request"
    # the reviewer approves; process 3 finishes without re-asking about the lookup or the refund
    decision = mod.review(path, "approve")
    assert decision == {"type": "approval", "key": key, "decision": "approve", "reason": "", "hash": mod.digest(shown)} and mod.load(path)[-1] == decision, f"review should append and return the approval event; got {decision}"
    o3 = drive(mod, TASKS["big"], path, world, tools_for=gated_tools)
    assert o3.status == "done" and o3.answer == "Order 44 refunded and customer emailed.", f"after approval the run should finish; got {o3.status}, {o3.answer!r}"
    assert [r["amount"] for r in world.refunds] == [80.0] and len(world.emails) == 1, f"one refund of 80.00 and one email; got {world.refunds}, {world.emails}"
    assert o3.model_calls == 2, f"the resumed process needs only the email turn and the final answer (2 model calls); got {o3.model_calls}"
    assert [e["type"] for e in mod.load(path)] == ["model", "result", "model", "approval_request", "approval", "result", "model", "result", "model"]
    # a denial is information for the model
    w, p = World(), journal()
    o = drive(mod, TASKS["big"], p, w, tools_for=gated_tools, on_pause=approver("deny", "needs a receipt"))
    assert o.answer == "Stopped: refused by reviewer: needs a receipt" and w.refunds == [] and w.emails == [], f"a denial goes back to the model as a result: expected the answer 'Stopped: refused by reviewer: needs a receipt' and no effects; got {o.answer!r}, {w.refunds}, {w.emails}"
    # an approval bound to other arguments is refused
    w, p = World(), journal()
    o = drive(mod, TASKS["big"], p, w, tools_for=gated_tools, on_pause=approver("approve", shown="deadbeef"))
    assert o.answer == "Stopped: error: approval was granted for different arguments" and w.refunds == [], f"a hash that does not match the arguments must not release the refund; got {o.answer!r}, {w.refunds}"
    # approvals belong to ONE call: two identical large refunds need two decisions
    w, p = World(), journal()
    o = drive(mod, TASKS["bigtwice"], p, w, tools_for=gated_tools)
    assert o.status == "paused"
    mod.review(p, "approve")
    o = drive(mod, TASKS["bigtwice"], p, w, tools_for=gated_tools)
    assert o.status == "paused" and len(w.refunds) == 1, f"approving the first of two identical refunds must not approve the second; status {o.status}, refunds {len(w.refunds)}"
    reqs = [e for e in mod.load(p) if e["type"] == "approval_request"]
    assert len(reqs) == 2 and reqs[0]["key"] != reqs[1]["key"], "the second refund is a separate request with its own key"
    mod.review(p, "approve")
    o = drive(mod, TASKS["bigtwice"], p, w, tools_for=gated_tools)
    assert o.status == "done" and len(w.refunds) == 2, f"after the second approval both refunds are made; got {o.status}, {len(w.refunds)}"
    # review's contract
    try:
        mod.review(p, "approve")
    except LookupError:
        pass
    else:
        raise AssertionError("review with nothing waiting should raise LookupError")
    try:
        mod.review(journal(), "maybe")
    except ValueError:
        pass
    else:
        raise AssertionError("review should reject a decision that is not 'approve' or 'deny'")
    # a small refund is never gated
    w, p = World(), journal()
    o = drive(mod, TASKS["plain"], p, w, tools_for=gated_tools)
    assert o.status == "done" and not any(e["type"].startswith("approval") for e in mod.load(p)), "a 20.00 refund is under the limit: no approval events"
    # crash at EVERY point of the run, with the reviewer answering as soon as asked
    ref, points, _ = reference("big")
    total = 0
    for k in range(1, points + 1):
        w, p, inj = World(), journal(), Injector(at=k)
        o = drive(mod, TASKS["big"], p, w, inj=inj, tools_for=gated_tools, on_pause=approver())
        where = f"crash point {k} of {points} ({inj.labels[k - 1]})"
        assert o.status == "done" and (len(w.refunds), len(w.emails)) == (1, 1), f"{where}: expected one refund and one email; got status {o.status}, {len(w.refunds)} refunds, {len(w.emails)} emails"
        assert core(mod.load(p)) == ref, f"{where}: the journal should equal the uninterrupted run's (one request, one approval)"
        total += 1
    return f"pause, duplicate-free resume, deny, hash mismatch, per-call approvals, and {total} crash points of the whole approval flow"


# =============================================================================
# Milestone 5: poison steps and a crash storm
# =============================================================================
def m5():
    log = [{"type": "attempt", "seq": 2, "id": "A", "n": 1}, {"type": "attempt_end", "seq": 2, "id": "A"},
           {"type": "attempt", "seq": 2, "id": "A", "n": 1}, {"type": "attempt", "seq": 2, "id": "A", "n": 2},
           {"type": "attempt", "seq": 3, "id": "A", "n": 1}, {"type": "attempt", "seq": 2, "id": "B", "n": 1},
           {"type": "model", "content": []}]
    got = [mod.attempts_for(log, 2, "A"), mod.attempts_for(log, 3, "A"), mod.attempts_for(log, 2, "B"), mod.attempts_for(log, 9, "A"), mod.attempts_for([], 1, "A")]
    assert got == [2, 1, 1, 0, 0], f"attempts_for counts attempts minus clean ends for ONE (seq, id); expected [2, 1, 1, 0, 0]; got {got}"
    # the poison step: three attempts, then a human queue; never an endless loop
    w, p = World(), journal()
    o = drive(mod, TASKS["poison"], p, w, max_attempts=3, max_restarts=20)
    ev = mod.load(p)
    assert o.status == "failed", f"a step that kills the process every time must end in RunFailed; got {o.status} after {o.restarts} restarts"
    assert w.poison_runs == 3, f"max_attempts=3 allows exactly 3 attempts at the poison step; it ran {w.poison_runs} times"
    poison_id = next(b["id"] for e in ev if e["type"] == "model" for b in e["content"] if b.get("name") == "parse_attachment")
    assert [e["n"] for e in ev if e["type"] == "attempt" and e["id"] == poison_id] == [1, 2, 3], f"attempt events at the poison step should count 1, 2, 3; got {[e for e in ev if e['type'] == 'attempt']}"
    assert sum(e["type"] == "failed" for e in ev) == 1 and ev[-1]["type"] == "failed", "exactly one 'failed' event, at the end"
    assert w.refunds == [], "the run stopped before the refund"
    again = drive(mod, TASKS["poison"], p, w, max_attempts=3)
    assert again.status == "failed" and again.restarts == 0 and w.poison_runs == 3 and again.model_calls == 0, "a run already marked failed stays failed: no process may touch the poison step again"
    # without max_attempts there are no attempt events at all (Milestone 3's journals stay clean)
    w, p = World(), journal()
    drive(mod, TASKS["plain"], p, w)
    assert not any(e["type"] in ("attempt", "attempt_end", "failed") for e in mod.load(p)), "with max_attempts left at None, run must write no attempt events"
    # waiting for a human is not a failure
    w, p = World(), journal()
    for _ in range(5):
        o = drive(mod, TASKS["big"], p, w, tools_for=gated_tools, max_attempts=2)
        assert o.status == "paused", f"a paused run restarted five times must stay paused, not become 'failed'; got {o.status}"
    mod.review(p, "approve")
    o = drive(mod, TASKS["big"], p, w, tools_for=gated_tools, max_attempts=2)
    assert o.status == "done" and len(w.refunds) == 1, f"after the long wait the approval still works; got {o.status}, {len(w.refunds)} refunds"
    assert not any(e["type"] == "failed" for e in mod.load(p))
    # the storm
    kinds = ["plain", "batch", "twice", "big", "bigtwice"]
    refs = {k: reference(k)[0] for k in kinds}
    crashes = restarts_max = runs = 0
    for seed in seeds(range(1, 41)):
        kind = kinds[seed % 5]
        p_crash = 0.04 + 0.02 * (seed % 4)
        w, path, inj = World(), journal(), Injector(seed=seed, p=p_crash)
        o = drive(mod, TASKS[kind], path, w, inj=inj, tools_for=gated_tools, on_pause=approver(), max_attempts=40, max_restarts=400)
        refunds, emails = EXPECT[kind]
        tag = f"storm seed {seed} ('{kind}', crash probability {p_crash:.2f} per point, {inj.crashes} crashes)"
        assert o.status == "done", f"{tag}: the run should finish; status {o.status}"
        assert (len(w.refunds), len(w.emails)) == (refunds, emails), f"{tag}: expected {refunds} refund(s) and {emails} email(s); the world holds {len(w.refunds)} and {len(w.emails)}: {w.refunds}"
        assert len({r['key'] for r in w.refunds}) == len(w.refunds), f"{tag}: two refunds share a key"
        assert core(mod.load(path)) == refs[kind], f"{tag}: the journal differs from the uninterrupted run's"
        model_events = sum(e["type"] == "model" for e in refs[kind])
        assert o.model_calls <= model_events + inj.crashes, f"{tag}: {o.model_calls} model calls for {model_events} replies and {inj.crashes} crashes; a crash may cost one repeated call, not more"
        crashes += inj.crashes
        restarts_max = max(restarts_max, o.restarts)
        runs += 1
    return f"{runs} random crash storms: {crashes} crashes survived (at most {restarts_max} restarts in one run), no duplicate refund or email, journals identical to the uninterrupted runs"


print(f"Lab 5 checks against {target}.py\n")
t0 = time.time()
check(1, "Milestone 1: the journal, a torn tail and the message list", m1)
check(2, "Milestone 2: what to do next, and the name of an attempt", m2)
check(3, "Milestone 3: the durable loop, killed at every crash point", m3)
check(4, "Milestone 4: a human approval that survives a restart", m4)
check(5, "Milestone 5: poison steps and a crash storm", m5)
for p in PATHS:
    drop_journal(p)
print(f"\n{sum(results)}/{len(results)} milestones passing  ({time.time() - t0:.1f} s)")
