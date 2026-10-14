"""Your agent loop on a real, small model: run lab 1's loop over twelve
support-desk tasks and count what breaks that the scripted model never showed.

With Ollama (ollama pull qwen2.5:0.5b), from this folder:
    python local_agent.py --model qwen2.5:0.5b
With serve_local.py (no Ollama needed), in another terminal first:
    python serve_local.py --model Qwen/Qwen2.5-0.5B-Instruct --port 8765
    python local_agent.py --base-url http://127.0.0.1:8765/v1 \
        --model Qwen/Qwen2.5-0.5B-Instruct
Add --show T6 to print one task's whole conversation.

Needs: lab 1's solution.py and llm.py (agents/labs/code/lab01). Standard
library only, so no virtual environment is needed for this one."""
import argparse
import json
import os
import sys
import time
import traceback
from collections import Counter
from pathlib import Path

sys.dont_write_bytecode = True      # keep the lab folder clean

# ── 1. Settings and the lab's code ───────────────────────────────────────
try:
    LAB = Path(__file__).resolve().parents[3] / "labs/code/lab01"
except NameError:                              # running as a notebook
    LAB = Path("../../../labs/code/lab01").resolve()
ap = argparse.ArgumentParser()
ap.add_argument("--base-url", default="http://localhost:11434/v1")
ap.add_argument("--model", default="qwen2.5:0.5b")
ap.add_argument("--lab", default=str(LAB))     # your solution.py lives here
ap.add_argument("--temperature", type=float, default=0.0)
ap.add_argument("--repeats", type=int, default=1)
ap.add_argument("--no-system", action="store_true")  # drop the system prompt
ap.add_argument("--show", default="")          # print one task in full
ap.add_argument("--crash-test", action="store_true")   # prove the harness
args, _ = ap.parse_known_args()    # notebooks pass their own flags

os.environ["OPENAI_BASE_URL"] = args.base_url
os.environ["LAB_MODEL"] = "openai:" + args.model
sys.path.insert(0, args.lab)
import llm                                  # noqa: E402  (lab-support)
from llm import Model, count_tokens, get_model   # noqa: E402
from solution import (Budget, Shop, Trace, agent_loop,   # noqa: E402
                      make_registry, summarise)

SYSTEM = ("You are a support agent for an online shop. Use the tools to look "
          "facts up. Never guess an order's details. Answer briefly.")


# ── 2. Twelve tasks, each with a check on the shop's real state ──────────
class Task:
    def __init__(self, tid, prompt, need, ok, refunds=()):
        self.tid, self.prompt, self.need = tid, prompt, set(need)
        self.ok, self.refunds = ok, list(refunds)  # expected refund ledger


def has(*words):
    return lambda a: all(w in a.lower() for w in words)


TASKS = [
    Task("T1", "What is the status of order A-1001?",
         ["get_order"], has("shipped")),
    Task("T2", "Which carrier has order A-1001 and where is the parcel now?",
         ["get_order", "track_shipment"], has("leeds")),
    Task("T3", "What is the total of order A-1003 in pounds?",
         ["get_order"], lambda a: "129" in a),
    Task("T4", "Has order A-1002 been shipped yet?",
         ["get_order"],
         lambda a: any(w in a.lower() for w in
                       ("processing", "not yet", "not been", "not shipped"))),
    Task("T5", "Where is order A-1003 right now?",
         ["get_order", "track_shipment"], has("hull")),
    Task("T6", "Refund 25.00 of order A-1001, it arrived damaged.",
         ["issue_refund"], lambda a: True, [("A-1001", 2500, "damaged")]),
    Task("T7", "Refund the whole of order A-1002: charged twice (duplicate).",
         ["get_order", "issue_refund"], lambda a: True,
         [("A-1002", 1999, "duplicate")]),
    Task("T8", "What is the status of order A-9999?",
         ["get_order"], lambda a: not any(
             w in a.lower() for w in ("shipped", "delivered", "processing"))),
    Task("T9", "How long do I have to return an item?",
         ["get_returns_policy"], has("30")),
    Task("T10", "Which costs more, order A-1001 or order A-1003?",
         ["get_order"], has("a-1003")),
    Task("T11", "Refund 500.00 of order A-1001 as goodwill.",
         [], lambda a: True),          # over the 100.00 cap: no refund
    Task("T12", "Hello! What can you help me with?",
         [], lambda a: len(a) > 0),    # needs no tool at all
]


# ── 3. A spy around the model: record every reply, even a crash ──────────
class Spy(Model):
    """Wraps the real model; remembers each reply and any exception."""
    def __init__(self, inner):
        self.inner, self.replies, self.name = inner, [], inner.name

    def complete(self, messages, **kw):
        kw["temperature"] = args.temperature
        reply = self.inner.complete(messages, **kw)
        self.replies.append(reply)
        return reply


def text_calls(reply):
    """A tool call written as plain text instead of a real tool_use."""
    said = "".join(b.get("text", "") for b in reply.content
                   if b.get("type") == "text")
    has_use = any(b.get("type") == "tool_use" for b in reply.content)
    return (not has_use) and ("tool_call" in said or '"arguments"' in said)


# ── 4. The harness: one task, never allowed to crash the run ─────────────
def run_one(task):
    shop, trace = Shop(), Trace()
    spy = Spy(get_model())
    start = time.monotonic()
    flags, res, err = Counter(), None, ""
    try:
        res = agent_loop(spy, task.prompt, make_registry(shop),
                         system="" if args.no_system else SYSTEM,
                         budget=Budget(max_iterations=8, max_seconds=60),
                         trace=trace)
    except Exception as e:                     # the harness survives anything
        flags["crash"] += 1
        err = f"{type(e).__name__}: {e}"[:70]
        if args.show == task.tid:
            traceback.print_exc()
    flags["tool_as_text"] = sum(text_calls(r) for r in spy.replies)
    if res:
        for m in res.messages:
            for b in m["content"] if isinstance(m["content"], list) else []:
                if b.get("type") == "tool_result" and b["is_error"]:
                    kind = ("unknown_tool" if b["content"].startswith("Unknown")
                            else "bad_args" if "Invalid" in b["content"]
                            else "tool_error")
                    flags[kind] += 1
        s = summarise(trace.events)
        flags["repeat"] = max(s["wasted_calls"] - s["errors"], 0)
    ran = set(shop.executed)
    if res is None:
        why = "crash"
    elif res.status != "done":
        why = res.status                       # a guard stopped the loop
    elif set(shop.refunds) - set(task.refunds):
        why = "wrong_refund"                   # money moved that should not
    elif shop.refunds != task.refunds:
        why = "no_refund"                      # the refund never happened
    elif not task.need <= ran:                 # a needed tool never ran
        why = "lucky" if task.ok(res.answer) else "skipped_step"
    elif not task.ok(res.answer):
        why = "wrong_answer"
    else:
        why = "ok"
    return dict(task=task, why=why, res=res, flags=flags, shop=shop,
                err=err, secs=time.monotonic() - start,
                calls=[c["name"] for m in (res.messages if res else [])
                       if isinstance(m["content"], list)
                       for c in m["content"] if c.get("type") == "tool_use"],
                tokens=res.input_tokens if res else 0,
                per_call=[e["input_tokens"] for e in trace.events
                          if e["kind"] == "model_call"],
                iters=res.iterations if res else len(spy.replies))


# ── 5. Prove the harness: two crashes, caused on purpose ─────────────────
if args.crash_test:
    real_post, real_url = llm.RealModel._post, os.environ["OPENAI_BASE_URL"]
    os.environ["OPENAI_BASE_URL"] = "http://127.0.0.1:9/v1"    # nobody home
    r = run_one(TASKS[0])
    print(f"dead server    -> {r['why']}: {r['err']}")
    os.environ["OPENAI_BASE_URL"] = real_url
    cut = {"choices": [{"finish_reason": "tool_calls", "message": {
        "content": None, "tool_calls": [{"id": "c1", "function": {
            "name": "get_order", "arguments": '{"order_id": "A-1001"'}}]}}]}
    llm.RealModel._post = lambda self, *a: cut     # a cut-off tool call
    r = run_one(TASKS[0])
    print(f"cut-off JSON   -> {r['why']}: {r['err']}")
    llm.RealModel._post = real_post
    sys.exit()

# ── 6. Run everything and print what happened ─────────────────────────────
print(f"model {args.model} at {args.base_url}, temperature "
      f"{args.temperature}, system prompt {'off' if args.no_system else 'on'}")
runs = []
for rep in range(args.repeats):
    for task in TASKS:
        r = run_one(task)
        runs.append(r)
        if args.show == task.tid and rep == 0 and r["res"]:
            for m in r["res"].messages:
                print(f"  [{m['role']}]", json.dumps(m["content"])[:300])
        seq = ">".join(c.replace("get_", "").replace("_", "") for c in
                       r["calls"]) or "-"
        odd = {k: v for k, v in r["flags"].items() if v}
        print(f"{task.tid:>3} {r['why']:<12} {r['iters']} it {seq:<22} "
              f"{r['secs']:4.1f}s {odd or ''} {r['err']}")

n = len(runs)
good = sum(r["why"] == "ok" for r in runs)
print(f"\nsuccess {good}/{n} = {good / n:.0%}")
print("outcomes:", dict(Counter(r["why"] for r in runs)))
tot = Counter()
for r in runs:
    for k, v in r["flags"].items():
        tot[k] += bool(v)
print("runs showing each symptom:", dict(tot))
bad_money = sum(bool(set(r["shop"].refunds) - set(r["task"].refunds))
                for r in runs)
print(f"runs that moved the wrong money: {bad_money}")
print(f"mean input tokens per run {sum(r['tokens'] for r in runs) / n:,.0f}, "
      f"mean iterations {sum(r['iters'] for r in runs) / n:.1f}")

# ── 7. Chapter 2's cost model against the real token counts ──────────────
# Iteration k sends B + D(k-1) tokens: B for system prompt, tool schemas
# and question; D for what each earlier iteration added to the history.
defs = make_registry(Shop()).definitions()
hello = [r for r in runs if r["per_call"]][-1]   # a run that got a reply
pred_b = (count_tokens(SYSTEM) + count_tokens(hello["task"].prompt) +
          sum(count_tokens(json.dumps(t, sort_keys=True)) for t in defs))
print(f"\nB, predicted at 4 characters a token: {pred_b}; "
      f"measured on {hello['task'].tid}: {hello['per_call'][0]}")
for k in (0, 1, 2):
    xs = [r["per_call"][k] for r in runs if len(r["per_call"]) > k]
    if xs:
        print(f"iteration {k + 1}: {sum(xs) / len(xs):6.0f} input tokens "
              f"on average, over {len(xs)} runs")
