"""demo.py: watch a crash and a recovery, then see what the idempotency key was worth.

    python3 demo.py solution      # or: python3 demo.py   (uses your starter.py)

Needs Milestones 1 to 3. Part 1 kills the plain task at the instant after the bank refunded and
before the journal heard about it. Part 2 repeats the whole crash sweep with the key thrown away
before it reaches the bank and the mailer, and lists the crash points that then duplicate an action.
"""
import importlib
import json
import sys

sys.dont_write_bytecode = True
mod = importlib.import_module(sys.argv[1] if len(sys.argv) > 1 else "starter")
from fixtures import TASKS, Injector, World, drive, new_journal  # noqa: E402


def brief(e):
    if e["type"] == "model":
        b = e["content"][0]
        return f"{b['name']}({json.dumps(b['input'])})" if b["type"] == "tool_use" else b["text"]
    return e["output"] if e["type"] == "result" else json.dumps(e)


probe = World()
drive(mod, TASKS["plain"], new_journal(), probe)                       # a dry run, to count the crash points
n_points = probe.inj.count
k = probe.inj.labels.index("refund:after") + 1
world, path, inj = World(), new_journal(), Injector(at=k)
out = drive(mod, TASKS["plain"], path, world, inj=inj)
print(f"crash point {k} of {n_points}: {inj.labels[k - 1]}")
print(f"status={out.status}  restarts={out.restarts}  model calls over both processes={out.model_calls}")
print(f"journal when process 1 died ({len(out.snapshots[0][1])} events):")
for i, e in enumerate(out.snapshots[0][1]):
    print(f"  {i}  {e['type']:<7} {brief(e)}")
print(f"journal at the end ({len(mod.load(path))} events):")
for i, e in enumerate(mod.load(path)):
    print(f"  {i}  {e['type']:<7} {brief(e)}")
print("bank:", [(r["order"], r["amount"], r["key"]) for r in world.refunds])
print("executions:", [(t, key.split(":")[1] if key else None) for t, key in world.executions])


def keyless(world, path):
    return {name: (lambda f: lambda a, key: f(a, None))(f) for name, f in world.tools().items()}


bad = []
for k in range(1, n_points + 1):
    w, p, inj = World(), new_journal(), Injector(at=k)
    drive(mod, TASKS["plain"], p, w, inj=inj, tools_for=keyless)
    if (len(w.refunds), len(w.emails)) != (1, 1):
        bad.append((k, inj.labels[k - 1], len(w.refunds), len(w.emails)))
print(f"\nwithout keys: {len(bad)} of {n_points} crash points duplicate something")
for k, label, r, m in bad:
    print(f"  point {k:>2}  {label:<20} refunds={r} emails={m}")
