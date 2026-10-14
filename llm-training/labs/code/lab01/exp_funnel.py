from collections import Counter
from solution import *
import corpus

pages = corpus.pages()
kind = {p.id: p.kind for p in pages}
rep = run_pipeline(pages)
print(f"{rep.n_pages} pages -> {rep.after_quality} after quality -> {rep.after_lines} after line dedupe"
      f" -> {rep.after_exact} after exact -> {rep.after_near} after near-duplicates\n")
by = Counter((stage, kind[i]) for i, (stage, _) in rep.dropped.items())
for stage in ("quality", "exact", "near"):
    row = ", ".join(f"{k} {n}" for (s, k), n in sorted(by.items()) if s == stage)
    print(f"dropped at {stage:8s}: {row}")
print("kept            :", ", ".join(f"{k} {n}" for k, n in sorted(Counter(kind[i] for i in rep.kept).items())))
print(f"\nnear-duplicate pairs: precision {rep.precision:.2f}, recall {rep.recall:.2f}")
