from solution import *
import corpus

pages = corpus.pages()
sh = {p.id: shingles(c4_line_filter(extract(p.html), require_punct=False)) for p in pages}
pairs = sorted(corpus.gold_pairs())
print(f"{len(pairs)} duplicate pairs")
print(f"{'num_perm':>8s} {'mean error':>11s} {'worst':>7s}")
for k in (8, 16, 32, 64, 112):
    sig = {i: minhash_signature(s, k) for i, s in sh.items()}
    err = [abs(estimate_jaccard(sig[a], sig[b]) - jaccard(sh[a], sh[b])) for a, b in pairs]
    print(f"{k:>8d} {sum(err) / len(err):11.3f} {max(err):7.3f}")
