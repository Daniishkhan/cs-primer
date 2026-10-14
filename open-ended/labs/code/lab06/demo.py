"""python3 demo.py [solution]: watch the search climb the leaky harness, then the hardened one."""
import sys
sys.dont_write_bytecode = True
import importlib
mod = importlib.import_module(sys.argv[1] if len(sys.argv) > 1 else "starter")
from collections import Counter

LEVELS = [
    ("leaky first draft",       dict()),
    ("+ strict output check",   dict(strict=True)),
    ("+ isolated runs",         dict(strict=True, isolated=True)),
    ("+ cold timing",           dict(strict=True, isolated=True, cold=True)),
    ("+ hidden tests",          dict(strict=True, isolated=True, cold=True, hidden=True)),
    ("+ tripwire",              dict(strict=True, isolated=True, cold=True, hidden=True, guard=True)),
]
SEEDS = range(8)
print(f"{'harness':24s} {'harness says':>12s} {'audit says':>11s}   what the winners were")
for name, flags in LEVELS:
    rs, au, kinds = [], [], Counter()
    for s in SEEDS:
        (algo, trick), r = mod.search(mod.Harness(seed=s, **flags), s)
        rs.append(r)
        au.append(mod.audit(mod.render(algo, trick)))
        kinds[trick or ("honest " + algo)] += 1
    print(f"{name:24s} {sum(rs)/len(rs):12.1f} {sum(au)/len(au):11.1f}   " + ", ".join(f"{k} x{v}" for k, v in kinds.most_common()))

print()
print("How much each trick gains over the honest `sorted` program (reward points), by harness:")
SHORT = ["leaky", "+strict", "+isolated", "+cold", "+hidden"]
print(f"{'trick':14s}" + "".join(f"{n:>11s}" for n in SHORT) + f"{'tripwire only':>15s}")
cols = [mod.red_team(mod.Harness(**f)) for _, f in LEVELS[:5]] + [mod.red_team(mod.Harness(guard=True))]
for t in mod.EXPLOITS:
    print(f"{t:14s}" + "".join(f"{c[t]:11.1f}" for c in cols[:5]) + f"{cols[5][t]:15.1f}")
