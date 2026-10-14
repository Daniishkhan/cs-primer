from solution import *
import corpus

pages = {p.id: p for p in corpus.pages()}
texts = {i: c4_line_filter(extract(p.html), require_punct=False) for i, p in pages.items()}
fam = {}
for p in pages.values():
    if p.family and p.kind in ("article", "light"):
        fam.setdefault(p.family, {})[p.kind] = p.id
a, b = next((v["article"], v["light"]) for v in fam.values() if len(v) == 2)
sa, sb = shingles(texts[a]), shingles(texts[b])
siga, sigb = minhash_signature(sa), minhash_signature(sb)
print(f"{a} (article) vs {b} (light edit): {len(sa)} and {len(sb)} shingles")
print(f"true Jaccard      {jaccard(sa, sb):.3f}")
print(f"MinHash estimate  {estimate_jaccard(siga, sigb):.3f}  ({sum(x == y for x, y in zip(siga, sigb))} of 112 positions agree)")
ka, kb = band_keys(siga), band_keys(sigb)
same = [i for i in range(14) if ka[i] == kb[i]]
print(f"bands that match  {len(same)} of 14: {same}  -> candidate pair: {bool(same)}")
print(f"formula says P(candidate) = {candidate_probability(jaccard(sa, sb)):.2f} at this similarity")
