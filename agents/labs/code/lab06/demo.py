"""demo.py: look inside one run of the pipeline.

    python3 demo.py solution roads      # or: potholes, fares.  Without arguments: your starter.py, roads.

Needs all six milestones. Prints each stage's output for one of the three research questions,
including the claims that were rejected and the draft sentences that were dropped.
"""
import importlib
import sys

sys.dont_write_bytecode = True
mod = importlib.import_module(sys.argv[1] if len(sys.argv) > 1 else "starter")
from fixtures import QUESTIONS, Index, load_docs, make_models  # noqa: E402

docs = load_docs()
index = Index(docs)
t = mod.research(QUESTIONS[sys.argv[2] if len(sys.argv) > 2 else "roads"], make_models(), index, docs)
print("queries   ", t.queries)
print("read      ", t.to_read)
print("skipped   ", t.skipped)
print("malformed ", t.read.malformed)
print("unreadable", t.read.unreadable)
print(f"claims read {len(t.read.claims)}, verified {len(t.verified)}")
for r in t.rejected:
    c = r["claim"]
    print(f"  rejected {c['id']:<4}{c['doc']:<4}{r['reason']:<22}{c['quote']!r}")
for f in t.findings:
    print(f"  {f.metric} {f.year}: {f.status} {f.values}")
old = {c["id"] for c in t.outdated}
print("draft:")
for a in mod.audit_draft(t.draft, [c for c in t.verified if c["id"] not in old]):
    print(("  ok   " if a.ok else "  DROP ") + a.sentence + ("" if a.ok else "   <- " + "; ".join(a.problems)))
