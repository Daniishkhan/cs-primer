"""Lab 3: hybrid retrieval and reranking (reference solution).

Two first-stage retrievers (BM25 and a dense stand-in), measured, fused two ways, then a reranker
that reads the query and each candidate together.

    1  cosine, cosine_topk, DenseRetriever.search
    2  evaluate, winners, union_recall
    3  rrf_scores, make_rrf
    4  min_max, z_score, convex, make_convex, best_alpha, leave_one_out
    5  coverage, bigram_overlap, id_match, pair_features
    6  rerank_score, Reranker.search
"""
import heapq
import math

from bm25 import Bm25Index, analyse
from embedder import TrigramEmbedder
from evalkit import load_collection, rank, grades_for, ndcg_at_k, recall_at_k


# =============================================================================
# Milestone 1: dense retrieval
# =============================================================================
def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def cosine(a, b):
    """Cosine similarity of two vectors; 0.0 if either has length zero."""
    na, nb = math.sqrt(dot(a, a)), math.sqrt(dot(b, b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot(a, b) / (na * nb)


def cosine_topk(qvec, doc_vecs, k):
    """The k documents most similar to `qvec`: [(doc_id, cosine), ...], best first, ties by doc id."""
    if k <= 0:
        return []
    # heapq.nsmallest on (-cosine, id) keeps only k candidates in memory: O(n log k), not a full sort
    best = heapq.nsmallest(k, ((-cosine(qvec, v), d) for d, v in doc_vecs.items()))
    return [(d, -neg) for neg, d in best]


class DenseRetriever:
    """Offline: embed every document once. Online: embed the query, compare, return the top k."""

    def __init__(self, docs, embedder):
        self.embedder = embedder
        self.vecs = {d: embedder.embed(t) for d, t in docs.items()}

    def search(self, query, k=20):
        return cosine_topk(self.embedder.embed(query), self.vecs, k)


# =============================================================================
# Milestone 2: measure, compare, find the headroom
# =============================================================================
def _mean(values):
    values = list(values)
    return sum(values) / len(values) if values else 0.0


def evaluate(search_fn, coll, k_ndcg=10, k_recall=20):
    """Run every query and score it. `search_fn(text, k)` returns [(doc_id, score), ...]."""
    ndcg, recall = {}, {}
    depth = max(k_ndcg, k_recall)
    for q in coll.queries:
        qid, qrel = q["qid"], coll.qrels[q["qid"]]
        ranking = [d for d, _ in search_fn(q["text"], depth)]
        grades = grades_for(ranking, qrel)
        ndcg[qid] = ndcg_at_k(grades, k_ndcg, list(qrel.values()))
        recall[qid] = recall_at_k(grades, k_recall, coll.n_relevant(qid))
    return {"ndcg": ndcg, "recall": recall, "ndcg_mean": _mean(ndcg.values()), "recall_mean": _mean(recall.values())}


def winners(per_a, per_b, margin=0.2):
    """Split query ids by which system did clearly better: {"a": [...], "b": [...], "tie": [...]}."""
    out = {"a": [], "b": [], "tie": []}
    for qid in sorted(per_a):
        diff = per_a[qid] - per_b[qid]
        out["a" if diff > margin else "b" if diff < -margin else "tie"].append(qid)
    return out


def union_recall(search_a, search_b, coll, k=20):
    """Mean recall of the SET of documents in either system's top k: the most a perfect merge could reach."""
    total = 0.0
    for q in coll.queries:
        found = {d for d, _ in search_a(q["text"], k)} | {d for d, _ in search_b(q["text"], k)}
        qrel = coll.qrels[q["qid"]]
        hits = sum(1 for d in found if qrel.get(d, 0) >= 1)
        total += hits / coll.n_relevant(q["qid"])
    return total / len(coll.queries)


# =============================================================================
# Milestone 3: reciprocal rank fusion
# =============================================================================
def rrf_scores(rankings, k=60, weights=None):
    """Sum of weight / (k + rank) over the lists a document appears in (ranks start at 1)."""
    weights = weights or [1.0] * len(rankings)
    out = {}
    for w, ranking in zip(weights, rankings):
        for r, d in enumerate(ranking, start=1):
            out[d] = out.get(d, 0.0) + w / (k + r)
    return out


def make_rrf(retrievers, depth=50, rrf_k=60, weights=None):
    """A search function that asks each retriever for `depth` results and fuses the rankings."""
    def search(text, k=20):
        rankings = [[d for d, _ in r.search(text, depth)] for r in retrievers]
        fused = rrf_scores(rankings, rrf_k, weights)
        return [(d, fused[d]) for d in rank(fused)[:k]]
    return search


# =============================================================================
# Milestone 4: normalised score fusion, and tuning alpha without fooling yourself
# =============================================================================
def min_max(scores):
    """Rescale to [0, 1] (lowest 0, highest 1). A list with no spread becomes all zeros."""
    lo, hi = min(scores.values()), max(scores.values())
    return {d: (s - lo) / (hi - lo) if hi > lo else 0.0 for d, s in scores.items()}


def z_score(scores):
    """(s - mean) / population standard deviation. A list with no spread becomes all zeros."""
    vals = list(scores.values())
    m = sum(vals) / len(vals)
    sd = math.sqrt(sum((v - m) ** 2 for v in vals) / len(vals))
    return {d: (s - m) / sd if sd else 0.0 for d, s in scores.items()}


def convex(a, b, alpha, norm=min_max):
    """alpha * norm(a) + (1 - alpha) * norm(b); a document missing from a list counts as 0 for it."""
    na, nb = norm(a) if a else {}, norm(b) if b else {}
    return {d: alpha * na.get(d, 0.0) + (1 - alpha) * nb.get(d, 0.0) for d in set(na) | set(nb)}


def make_convex(lexical, dense, alpha=0.5, depth=50, norm=min_max):
    """A search function: weighted sum of the two retrievers' normalised score lists."""
    def search(text, k=20):
        fused = convex(dict(lexical.search(text, depth)), dict(dense.search(text, depth)), alpha, norm)
        return [(d, fused[d]) for d in rank(fused)[:k]]
    return search


def best_alpha(table):
    """`table` is {alpha: [nDCG per query]}. The alpha with the highest mean; ties go to the smaller alpha."""
    return max(sorted(table), key=lambda a: _mean(table[a]))


def leave_one_out(table):
    """Choose alpha on all queries but one, score the one left out; repeat for every query.

    Returns (mean held-out score, [alpha chosen for each query])."""
    n = len(next(iter(table.values())))
    held, chosen = [], []
    for i in range(n):
        rest = {a: v[:i] + v[i + 1:] for a, v in table.items()}
        a = best_alpha(rest)
        chosen.append(a)
        held.append(table[a][i])
    return _mean(held), chosen


# =============================================================================
# GIVEN: the table builder for milestone 4 (caches each query's candidate lists once)
# =============================================================================
def alpha_table(coll, lexical, dense, alphas, depth=50, norm=min_max):
    cache = [(q["qid"], dict(lexical.search(q["text"], depth)), dict(dense.search(q["text"], depth))) for q in coll.queries]
    table = {}
    for alpha in alphas:
        row = []
        for qid, lex, den in cache:
            qrel = coll.qrels[qid]
            ranking = rank(convex(lex, den, alpha, norm))
            row.append(ndcg_at_k(grades_for(ranking, qrel), 10, list(qrel.values())))
        table[alpha] = row
    return table


# =============================================================================
# Milestone 5: features of a (query, passage) pair, the inputs of a reranker
# =============================================================================
def crude_stem(term):
    """GIVEN: a rough stand-in for a stemmer. Terms with a digit are identifiers and stay whole."""
    return term if any(c.isdigit() for c in term) else term[:5]


def stems(text):
    """GIVEN: content terms of a text, in order, crudely stemmed."""
    return [crude_stem(t) for t in analyse(text)]


def coverage(q_terms, d_terms):
    """Fraction of the DISTINCT query terms that occur somewhere in the document (0.0 if the query is empty)."""
    wanted = set(q_terms)
    if not wanted:
        return 0.0
    return len(wanted & set(d_terms)) / len(wanted)


def bigram_overlap(q_terms, d_terms):
    """Fraction of the query's adjacent term pairs that occur adjacent, in the same order, in the document.

    0.0 if the query has fewer than two terms."""
    q_pairs = list(zip(q_terms, q_terms[1:]))
    if not q_pairs:
        return 0.0
    d_pairs = set(zip(d_terms, d_terms[1:]))
    return sum(1 for p in q_pairs if p in d_pairs) / len(q_pairs)


def id_match(query, doc_text):
    """Among the query's tokens that contain a digit (identifiers), the fraction found verbatim in the document.

    0.0 if the query has no such token. Tokens come from `analyse`, so 'E4021-B' gives 'e4021' and 'b'."""
    wanted = [t for t in analyse(query) if any(c.isdigit() for c in t)]
    if not wanted:
        return 0.0
    have = set(analyse(doc_text))
    return sum(1 for t in wanted if t in have) / len(wanted)


FEATURES = ["cosine", "bm25", "coverage", "bigram", "id_match"]


def pair_features(query, doc_text, cos, bm25_norm):
    """[cosine, bm25 (already scaled to 0..1), coverage, bigram_overlap, id_match], in FEATURES order."""
    q_terms, d_terms = stems(query), stems(doc_text)
    return [cos, bm25_norm, coverage(q_terms, d_terms), bigram_overlap(q_terms, d_terms), id_match(query, doc_text)]


# =============================================================================
# Milestone 6: the reranker and its pipeline
# =============================================================================
WEIGHTS = [1.0, 1.0, 1.0, 2.0, 1.0]        # GIVEN: hand-set once, round numbers, same order as FEATURES


def rerank_score(features, weights=WEIGHTS):
    """The weighted sum of the features."""
    return sum(w * f for w, f in zip(weights, features))


class Reranker:
    """Take a first stage's top `depth` candidates, score each (query, passage) pair, reorder.

    `first_stage(text, depth)` returns [(doc_id, score)]; `dense` supplies cosines (its .vecs and
    .embedder); `bm25` supplies BM25 scores. `pairs_scored` counts how many pairs were read: the cost."""

    def __init__(self, first_stage, docs, dense, bm25, depth=30, weights=WEIGHTS):
        self.first_stage, self.docs, self.dense, self.bm25 = first_stage, docs, dense, bm25
        self.depth, self.weights = depth, weights
        self.pairs_scored = 0

    def search(self, text, k=20):
        cands = [d for d, _ in self.first_stage(text, self.depth)]
        if not cands:
            return []
        qvec = self.dense.embedder.embed(text)
        lex = self.bm25.scores(text)
        top = max((lex.get(d, 0.0) for d in cands), default=0.0)       # scale BM25 within THIS candidate list
        scored = {}
        for d in cands:
            self.pairs_scored += 1
            f = pair_features(text, self.docs[d], cosine(qvec, self.dense.vecs[d]), lex.get(d, 0.0) / top if top else 0.0)
            scored[d] = rerank_score(f, self.weights)
        return [(d, scored[d]) for d in rank(scored)[:k]]


# =============================================================================
# GIVEN: build everything, and print the table the lab is about
# =============================================================================
def build(coll=None):
    coll = coll or load_collection()
    bm25 = Bm25Index(coll.docs)
    dense = DenseRetriever(coll.docs, TrigramEmbedder(coll.docs))
    return coll, bm25, dense


if __name__ == "__main__":
    coll, bm25, dense = build()
    rrf = make_rrf([bm25, dense])
    reranked = Reranker(rrf, coll.docs, dense, bm25)
    print(f"{'system':<22}{'nDCG@10':>9}{'recall@20':>11}")
    for name, fn in [("BM25", bm25.search), ("dense", dense.search), ("RRF k=60", rrf),
                     ("convex a=0.5", make_convex(bm25, dense)), ("RRF + rerank", reranked.search)]:
        r = evaluate(fn, coll)
        print(f"{name:<22}{r['ndcg_mean']:>9.3f}{r['recall_mean']:>11.3f}")
