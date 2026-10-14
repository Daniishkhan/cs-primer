from solution import *
import corpus

pages = {p.id: p for p in corpus.pages()}
text = {i: c4_line_filter(extract(p.html), require_punct=False) for i, p in pages.items()}
by = {}
for p in pages.values():
    if p.family:
        by.setdefault(p.family, {})[p.kind] = p.id
light = next(v for v in by.values() if "article" in v and "light" in v)
medium = next(v for v in by.values() if "article" in v and "medium" in v)
pairs = {"light edit": (light["article"], light["light"]),
         "one sentence": (medium["article"], medium["medium"]),
         "unrelated": (light["article"], medium["article"])}

print(f"{'shingle':>9s} {'light edit':>11s} {'one sentence':>13s} {'unrelated':>10s}   P(candidate) at 14 x 8, light edit")
for n in (2, 3, 5, 8, 12):
    j = {k: jaccard(shingles(text[a], n), shingles(text[b], n)) for k, (a, b) in pairs.items()}
    print(f"{n:>5d}-word {j['light edit']:11.3f} {j['one sentence']:13.3f} {j['unrelated']:10.3f}   {candidate_probability(j['light edit']):.2f}")
