"""Regenerate the fixture logs in logs/ (seeded: the files never change).

    python3 make_fixtures.py

The logs are synthetic: they imitate the shape of a self-improvement run,
not any real system. Each one is built to fail (or pass) exactly one thing.
"""
import json
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))
SEARCH = ["s1", "s2", "s3"]
HELD = ["h1", "h2", "h3", "h4", "h5", "h6"]


def run_log(run_id, arm, budget, attempts, accepts, per_step, held_gain,
            seed, start=0.50, noise=0.01, search_tasks=SEARCH,
            eval_tasks=HELD):
    """Lines of one run. accepts maps step number to the gain it brings."""
    rng = random.Random(seed)
    out = [{"type": "run", "run_id": run_id, "arm": arm,
            "budget_usd": budget, "max_attempts": attempts,
            "noise_floor": noise, "search_tasks": search_tasks}]
    best = start
    for step in range(1, attempts + 1):
        gain = accepts.get(step, 0.0)
        cand = best + gain if gain else best - rng.uniform(0.0, 0.03)
        if gain:
            best = cand
        out.append({"type": "step", "run_id": run_id, "step": step,
                    "cost_usd": per_step(step), "search_score":
                    round(cand, 4), "accepted": bool(gain),
                    "incumbent": round(best, 4)})
    for task in eval_tasks:
        base = start + rng.uniform(-0.05, 0.05)
        for s in (1, 2, 3):
            out.append({"type": "eval", "run_id": run_id, "stage":
                        "initial", "task": task, "seed": s,
                        "score": round(base + rng.gauss(0, 0.01), 4)})
            out.append({"type": "eval", "run_id": run_id, "stage": "final",
                        "task": task, "seed": s, "score": round(
                            base + held_gain + rng.gauss(0, 0.01), 4)})
    return out


def write(name, *runs):
    with open(os.path.join(HERE, "logs", name), "w") as f:
        for lines in runs:
            for row in lines:
                f.write(json.dumps(row) + "\n")


flat = lambda step: 2.0                      # $2 an attempt: 30 x 2 = $60
GOOD = {3: 0.03, 8: 0.025, 14: 0.03, 21: 0.02, 27: 0.025}

write("improver_good.jsonl",
      run_log("improver-good", "improver", 60.0, 30, GOOD, flat, 0.07, 11))
write("baseline_fair.jsonl",
      run_log("baseline-fair", "baseline", 60.0, 30,
              {5: 0.02, 17: 0.015}, flat, 0.03, 12))
write("baseline_short.jsonl",
      run_log("baseline-short", "baseline", 30.0, 15,
              {5: 0.02}, flat, 0.01, 13))
write("improver_lucky.jsonl",
      run_log("improver-lucky", "improver", 60.0, 30,
              {12: 0.09, 20: 0.004, 25: 0.006}, flat, 0.07, 14))
write("improver_overspend.jsonl",
      run_log("improver-overspend", "improver", 60.0, 30, GOOD,
              lambda s: 2.0 if s < 25 else 6.0, 0.07, 15))
write("improver_leaky.jsonl",
      run_log("improver-leaky", "improver", 60.0, 30, GOOD, flat, 0.07, 16,
              eval_tasks=["s2", "h1", "h2", "h3"]))
write("improver_overfit.jsonl",
      run_log("improver-overfit", "improver", 60.0, 30, GOOD, flat, 0.003,
              17))
