from collections import Counter, defaultdict
from solution import *
import corpus

by_kind = defaultdict(Counter)
for p in corpus.pages():
    text = c4_line_filter(extract(p.html), require_punct=False)
    flags = quality_flags(text)
    by_kind[p.kind]["pages"] += 1
    if not flags:
        by_kind[p.kind]["kept"] += 1
    for f in flags:
        by_kind[p.kind][f] += 1
print(f"{'kind':11s} {'pages':>5s} {'kept':>5s}  rules that fired (pages)")
for kind in ["article", "exact", "light", "medium", "related", "borderline", "seo", "spam", "short", "nonenglish"]:
    c = by_kind[kind]
    fired = ", ".join(f"{k} {v}" for k, v in c.items() if k not in ("pages", "kept"))
    print(f"{kind:11s} {c['pages']:5d} {c['kept']:5d}  {fired}")
