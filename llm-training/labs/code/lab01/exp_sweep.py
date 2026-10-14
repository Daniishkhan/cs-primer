from solution import *
import corpus

pages = corpus.pages()
fam = {p.id: p.family for p in pages}
print(f"{'b x r':>8s} {'thresh':>6s} {'pairs':>5s} {'precision':>9s} {'recall':>6s} {'left':>5s} {'wrongly removed':>16s}")
for b, r in [(4, 28), (7, 16), (8, 14), (14, 8), (16, 7), (28, 4), (56, 2)]:
    rep = run_pipeline(pages, b, r)
    wrong = sum(1 for i, (st, rid) in rep.dropped.items()
                if st == "near" and not (fam[i] and fam[i] == fam[rid]))
    print(f"{b:>3d} x {r:<3d} {threshold(b, r):6.2f} {rep.candidates:5d} {rep.precision:9.2f} {rep.recall:6.2f} {rep.after_near:5d} {wrong:16d}")
