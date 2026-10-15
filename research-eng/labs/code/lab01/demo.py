"""A whole research loop, end to end, with your finished starter.py.

    python3 demo.py              # uses starter.py
    python3 demo.py solution     # uses the reference solution
    python3 demo.py solution runs.jsonl   # also keeps the run store

It measures the noise floor, runs 60 experiments with the seeded random
proposer, charts proxy gain against held-out gain, asks the detector
where it would have stopped, and replays the log byte for byte.
"""
import importlib
import os
import shutil
import sys
import tempfile

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
lab = importlib.import_module(sys.argv[1] if len(sys.argv) > 1 else "starter")

# ── 1. A fresh run store, and the noise floor of the baseline ────────
tmp = tempfile.mkdtemp(prefix="lab01-demo-")
path = os.path.join(tmp, "runs.jsonl")
store = lab.RunStore(path)
nf = lab.noise_floor(lab.BASELINE, lab.BASELINE_SEEDS, store)
print(f"baseline config {lab.config_hash(lab.BASELINE)}, "
      f"{nf['n']} seeds")
for name in ("proxy", "heldout"):
    s = nf[name]
    print(f"  {name:8s} mean {s['mean']:.4f}  sd {s['sd']:.4f}"
          f"  floor {s['floor']:.4f}")

# ── 2. The loop: 60 experiments, decided on the proxy only ───────────
best, history = lab.research_loop(lab.RandomProposer(0), 60, store)
kept = [r for r in history if r["keep"]]
print(f"\n{len(kept)} of {len(history)} experiments kept; "
      f"{len(store)} records in the store")
for r in kept:
    print(f"  exp {r['index'] + 1:2d}: proxy gain {r['proxy_gain']:+.4f}"
          f"  held-out gain {r['heldout_gain']:+.4f}"
          f"  t {r['t']:5.2f}  {r['cand_config']}")

# ── 3. The gap, and where the detector would have stopped ────────────
cp, ch, cg = lab.cumulative(history)
print("\ncumulative gain over the baseline (higher is better)")
print(lab.text_chart(cp, ch, every=10))
at = lab.detect_overfit(cp, ch)
print(f"\ndetector: " + ("never fired" if at is None else
      f"fired at experiment {at + 1} (proxy +{cp[at]:.4f}, "
      f"held-out +{ch[at]:.4f})"))
print(f"final: proxy +{cp[-1]:.4f}, held-out +{ch[-1]:.4f}, "
      f"gap {cg[-1]:.4f}")

# ── 4. Replay the log into a new file and compare the bytes ──────────
again = os.path.join(tmp, "replayed.jsonl")
diff = lab.replay(path, again)
print("\nreplay:", "byte-identical" if diff is None
      else f"differs at line {diff}")
print(f"log: {os.path.getsize(path):,} bytes, "
      f"{sum(1 for _ in open(path)):,} lines")

# ── 5. Optionally keep the run store, e.g. for the Rust exercise ─────
if len(sys.argv) > 2:
    shutil.copy(path, sys.argv[2])
    print("run store copied to", sys.argv[2])
