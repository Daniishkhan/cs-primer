"""Real embedders and a reranker, measured on a small retrieval corpus:
378 passages, 60 queries of four kinds, graded judgements. Predict which
system wins each kind of query, then measure nDCG@10 and recall@20.

    python real_embedders.py
    python real_embedders.py --depth 50

Needs: sentence-transformers (workbench/requirements.txt) and the corpus/
folder next to this script (corpus, queries, judgements and the BM25 and
stand-in embedder code it is compared with). Downloads about 87 MB
(all-MiniLM-L6-v2), 136 MB (bge-small-en-v1.5) and 87 MB (the
cross-encoder ms-marco-MiniLM-L-6-v2) the first time."""
import argparse
import sys
import time
from pathlib import Path

import numpy as np
import torch
from sentence_transformers import CrossEncoder, SentenceTransformer

# ── 1. Settings and the lab's own code ───────────────────────────────────
ap = argparse.ArgumentParser()
ap.add_argument("--lab", default=None)     # folder holding corpus.json
ap.add_argument("--depth", type=int, default=30)    # candidates reranked
ap.add_argument("--no-prefix", action="store_true")  # bge: skip the prefix
args, _ = ap.parse_known_args()        # notebooks pass their own flags


def find_lab():
    if args.lab:
        return Path(args.lab)
    try:
        here = Path(__file__).resolve().parent
    except NameError:                  # inside a notebook
        here = Path.cwd().resolve()
    for base in (here, here / "agents/workbench/code/w02"):
        if (base / "corpus" / "corpus.json").is_file():
            return base / "corpus"
    raise SystemExit("cannot find corpus/corpus.json next to this script; pass --lab")


LAB = find_lab()
sys.path.insert(0, str(LAB))
from bm25 import Bm25Index                       # noqa: E402
from embedder import TrigramEmbedder             # noqa: E402
from evalkit import (grades_for, load_collection,  # noqa: E402
                     ndcg_at_k, recall_at_k)

if torch.cuda.is_available():
    DEVICE = "cuda"
else:
    DEVICE = "cpu"
torch.manual_seed(0)
coll = load_collection(str(LAB))
ids = list(coll.docs)
texts = [coll.docs[d] for d in ids]
kinds = sorted({q["kind"] for q in coll.queries})
counts = {k: sum(q["kind"] == k for q in coll.queries) for k in kinds}
print(f"{len(ids)} passages, {len(coll.queries)} queries {counts}; "
      f"device {DEVICE}")

# ── 2. Predict, before measuring (chapters 7 and 8) ──────────────────────
print("""
predicted winners (nDCG@10), from the chapters' reasoning
  code     BM25: an exact token like E4021 matters, and vectors blur it
  variant  a dense model: typos and inflections share word pieces or
           letter groups, which BM25's exact terms miss
  plain    a real embedder: it was trained on paraphrase, the stand-in was not
  order    below plain for every dense first stage (one vector per
           passage holds "from A to B" and "from B to A" almost alike),
           and the cross-encoder lifts it
  overall  real embedders beat the stand-in; reranking helps; recall@20
           after reranking cannot exceed recall at the depth it was given""")

# ── 3. Build the five first stages ───────────────────────────────────────
bm25 = Bm25Index(coll.docs)
stand = TrigramEmbedder(coll.docs)
stand_vecs = np.array([stand.embed(t) for t in texts])
BGE_PREFIX = "Represent this sentence for searching relevant passages: "
MODELS = {
    "MiniLM": ("sentence-transformers/all-MiniLM-L6-v2", ""),
    "bge-small": ("BAAI/bge-small-en-v1.5",
                  "" if args.no_prefix else BGE_PREFIX),
}
dense = {"stand-in": (stand_vecs, stand.embed)}
for name, (hf_id, prefix) in MODELS.items():
    model = SentenceTransformer(hf_id, device=DEVICE)
    t0 = time.perf_counter()
    vecs = model.encode(texts, normalize_embeddings=True, batch_size=64)
    secs = time.perf_counter() - t0
    print(f"{name}: {vecs.shape[1]} numbers per passage, "
          f"{len(texts) / secs:.0f} passages/s (encoding only)")
    dense[name] = (vecs, lambda q, m=model, p=prefix:
                   m.encode(p + q, normalize_embeddings=True))


def top_dense(name, query, k):
    vecs, embed = dense[name]
    scores = vecs @ np.asarray(embed(query))
    order = np.argsort(-scores, kind="stable")[:k]
    return [(ids[i], float(scores[i])) for i in order]


SEARCH = {"BM25": bm25.search}
for name in dense:
    SEARCH[name] = lambda q, k, n=name: top_dense(n, q, k)

# ── 4. The cross-encoder reranks a first stage's top candidates ──────────
ce = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2", device=DEVICE)


def reranked(first):
    def run(query, k):
        cands = [d for d, _ in SEARCH[first](query, args.depth)]
        s = ce.predict([(query, coll.docs[d]) for d in cands],
                       batch_size=64)
        order = np.argsort(-s, kind="stable")[:k]
        return [(cands[i], float(s[i])) for i in order]
    return run


for first in ("BM25", "bge-small"):
    SEARCH[f"{first}+rerank"] = reranked(first)

# ── 5. Measure ───────────────────────────────────────────────────────────


def evaluate(fn):
    nd, rc = {}, {}
    for q in coll.queries:
        qrel = coll.qrels[q["qid"]]
        got = [d for d, _ in fn(q["text"], 20)]
        g = grades_for(got, qrel)
        nd[q["qid"]] = ndcg_at_k(g, 10, list(qrel.values()))
        rc[q["qid"]] = recall_at_k(g, 20, coll.n_relevant(q["qid"]))
    return nd, rc


results = {name: evaluate(fn) for name, fn in SEARCH.items()}


def mean(d, kind=None):
    vals = [v for q in coll.queries if kind in (None, q["kind"])
            for v in [d[q["qid"]]]]
    return sum(vals) / len(vals)


print(f"\nnDCG@10 and recall@20 over all queries (rerank depth "
      f"{args.depth})")
print(f"  {'system':18}{'nDCG@10':>9}{'recall@20':>11}")
for name, (nd, rc) in results.items():
    print(f"  {name:18}{mean(nd):>9.3f}{mean(rc):>11.3f}")

print("\nnDCG@10 by kind of query")
print(f"  {'system':18}" + "".join(f"{k:>9}" for k in kinds))
for name, (nd, _) in results.items():
    print(f"  {name:18}" + "".join(f"{mean(nd, k):>9.3f}" for k in kinds))
print("  best first stage and best system overall, per kind:")
firsts = ["BM25", "stand-in", "MiniLM", "bge-small"]
for k in kinds:
    a = max(firsts, key=lambda n: mean(results[n][0], k))
    b = max(results, key=lambda n: mean(results[n][0], k))
    print(f"    {k:9}{a:>10}   {b}")

# ── 6. The recall ceiling: a reranker cannot add a document ──────────────
print(f"\nrecall ceiling: first stage at depth {args.depth} against "
      f"recall@20 after reranking")
for first in ("BM25", "bge-small"):
    ceil = []
    for q in coll.queries:
        got = [d for d, _ in SEARCH[first](q["text"], args.depth)]
        g = grades_for(got, coll.qrels[q["qid"]])
        ceil.append(recall_at_k(g, args.depth, coll.n_relevant(q["qid"])))
    after = mean(results[f"{first}+rerank"][1])
    print(f"  {first:10} first stage recall@{args.depth} "
          f"{sum(ceil) / len(ceil):.3f}   after rerank recall@20 "
          f"{after:.3f}")

# ── 7. One query where direction matters ─────────────────────────────────
q = next(x for x in coll.queries if x["kind"] == "order")
qrel = coll.qrels[q["qid"]]
print(f"\nquery {q['qid']}: {q['text']!r}")
for name in ("bge-small", "bge-small+rerank"):
    top = SEARCH[name](q["text"], 3)
    print(f"  {name}")
    for d, s in top:
        print(f"    grade {qrel.get(d, 0)}  {s:7.3f}  {coll.docs[d][:70]}")
