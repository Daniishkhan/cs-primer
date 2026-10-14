"""Evaluator hacking, planted: a weak scorer, two hacks, a tripwire and a fix.

A scorer that treats a crash as "skip this item" rewards programs that crash.
This script scores hand-written candidates (and, with --replay, a model's
real samples) with that weak scorer, a tripwire and the total evaluator.

    python hack_demo.py
    python hack_demo.py --replay evolve_llm.jsonl     # Workbench 1's log

Needs: Python 3.9+ and binpack.py next to this file. No model needed."""
import argparse
import json

from binpack import (CAP, FIRST_FIT_SRC, SEED_SRC, TRAIN_SEEDS, Fuel,
                     compile_restricted, evaluate, lower_bound,
                     make_instances)

ap = argparse.ArgumentParser()
ap.add_argument("--replay", default="")        # a JSONL log from evolve_llm
ap.add_argument("--jump", type=float, default=3.0)   # tripwire, in bins
args, _ = ap.parse_known_args()

train = make_instances(TRAIN_SEEDS)
bound = sum(map(lower_bound, train)) / len(train)
best_fit = evaluate(SEED_SRC, train).score


# ── 1. The weak scorer: one innocent-looking try/except ──────────────────
def pack_weak(items, priority):
    """Like binpack.pack, but "one bad item should not end the run": an
    item whose handling raises is skipped. Returns (bins, items placed)."""
    bins, placed = [], 0
    for it in items:
        try:
            best, best_p = None, None
            for i, rem in enumerate(bins):
                if rem >= it:
                    p = priority(it, rem)
                    if best_p is None or p > best_p:
                        best, best_p = i, p
            if best is None:
                bins.append(CAP - it)
            else:
                bins[best] -= it
            placed += 1
        except Exception:
            continue                  # <- the flaw: a crash is not a loss
    return len(bins), placed


def weak_score(src):
    """(mean bins, mean items placed out of 300), or None if refused."""
    try:
        fn = compile_restricted(src, Fuel(40_000 * len(train)))
    except Exception:
        return None
    runs = [pack_weak(items, lambda a, b: fn(float(a), float(b)))
            for items in train]
    return (sum(r[0] for r in runs) / len(runs),
            sum(r[1] for r in runs) / len(runs))


# ── 2. The tripwire: results that are too good to be true (chapter 15) ───
def tripwire(score):
    """A reason to hold the candidate for a human, or None."""
    if score < bound:
        return f"below the lower bound ({bound:.1f}): impossible"
    if best_fit - score > args.jump:
        return f"{best_fit - score:.1f} bins better than best fit in one step"
    return None


# ── 3. The candidates: two honest, two planted ───────────────────────────
GAP = "def priority(item, rem):\n    gap = rem - item\n"
CANDIDATES = {
    "first fit": FIRST_FIT_SRC,
    "best fit": SEED_SRC,
    "hack: always crash": "def priority(item, rem):\n"
                          "    return 1 / (item - item)\n",
    "hack: crash at gap 30": GAP + "    return -gap + 0 * (1 / (gap - 30))\n",
}
print(f"search set: lower bound {bound:.1f} bins, best fit {best_fit:.1f}\n")
print(f"{'candidate':22s} {'weak score':>10s} {'placed':>7s}  "
      f"{'total evaluator':16s} tripwire")
rows = {}
for name, src in CANDIDATES.items():
    bins, placed = weak_score(src)
    strong = evaluate(src, train)
    flag = tripwire(bins)
    rows[name] = (bins, strong, flag)
    verdict = f"ok {strong.score:.1f}" if strong.ok else strong.status
    print(f"{name:22s} {bins:10.1f} {placed:7.0f}  {verdict:16s} "
          f"{flag or '-'}")

# ── 4. Three judges pick a champion from the same four candidates ────────
weak = min(rows, key=lambda n: rows[n][0])
wired = min((n for n in rows if not rows[n][2]), key=lambda n: rows[n][0])
total = min((n for n in rows if rows[n][1].ok), key=lambda n: rows[n][1].score)
print(f"\nchampion if the weak scorer alone judges:  {weak}")
print(f"champion if the tripwire holds back hacks: {wired}")
print(f"champion if the total evaluator judges:    {total}")

# ── 5. Optionally, rescore a real model's samples with the weak scorer ───
if args.replay:
    errors = []
    for line in open(args.replay):
        rec = json.loads(line)
        if rec["src"] and rec["status"] == "error":
            errors.append(rec["src"])
    print(f"\n{args.replay}: {len(errors)} samples crashed under the total "
          f"evaluator")
    scored = [(weak_score(s), s) for s in errors]
    scored = [(w[0], w[1], s) for w, s in scored if w]
    for bins, placed, _ in sorted(scored, key=lambda r: r[0])[:3]:
        print(f"  weak scorer says {bins:6.1f} bins, "
              f"{placed:5.0f} of 300 items placed")
    better = sum(b < best_fit for b, _, _ in scored)
    print(f"  {better} of them 'beat' best fit ({best_fit:.1f}) only because "
          f"they crashed")
