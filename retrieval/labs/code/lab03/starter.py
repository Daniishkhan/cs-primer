"""Lab 3: hybrid retrieval and reranking.

Two first-stage retrievers (BM25 and a dense stand-in), measured, fused two ways, then a reranker
that reads the query and each candidate together. Notation is chapters 8 and 10's:

    docs        {doc_id: text}
    retriever   any object with .search(text, k) -> [(doc_id, score), ...], best first
    search fn   a function (text, k) -> [(doc_id, score), ...]; what `evaluate` runs
    ranking     a list of doc ids, best first
    scores      {doc_id: float}

What is GIVEN: bm25.py (the lexical retriever), embedder.py (the dense STAND-IN, not a neural
network), evalkit.py (loading and Lab 2's metrics), `dot`, `alpha_table`, the crude stemmer and
the printing at the bottom. What YOU write is marked TODO:

    1  cosine, cosine_topk, DenseRetriever.search
    2  evaluate, winners, union_recall
    3  rrf_scores, make_rrf
    4  min_max, z_score, convex, make_convex, best_alpha, leave_one_out
    5  coverage, bigram_overlap, id_match, pair_features
    6  rerank_score, Reranker.search

`python3 check.py` runs the milestones; the lab page explains each one.
"""
import heapq          # noqa: F401  (milestone 1: heapq.nsmallest keeps only the k best)
import math           # noqa: F401

from bm25 import Bm25Index, analyse
from embedder import TrigramEmbedder
from evalkit import load_collection, rank, grades_for, ndcg_at_k, recall_at_k


# =============================================================================
# Milestone 1: dense retrieval
# =============================================================================
def dot(a, b):
    """GIVEN."""
    return sum(x * y for x, y in zip(a, b))


def cosine(a, b):
    """Cosine similarity of two vectors: dot(a, b) / (|a| |b|). 0.0 if either has length zero.

        cosine([1, 2], [2, 4]) -> 1.0        cosine([1, 0], [0, 1]) -> 0.0
    """
    raise NotImplementedError("TODO milestone 1: cosine")


def cosine_topk(qvec, doc_vecs, k):
    """The k documents most similar to `qvec`: [(doc_id, cosine), ...], best first.

    `doc_vecs` is {doc_id: vector}. Ties in cosine are broken by doc id, ascending, so results
    never flicker. k larger than the number of documents returns them all; k <= 0 returns [].
    Returns the cosine itself (not its negative). Hint: heapq.nsmallest on (-cosine, doc_id).
    """
    raise NotImplementedError("TODO milestone 1: cosine_topk")


class DenseRetriever:
    """Offline: embed every document once. Online: embed the query, compare, return the top k."""

    def __init__(self, docs, embedder):
        self.embedder = embedder
        self.vecs = {d: embedder.embed(t) for d, t in docs.items()}      # GIVEN: the offline half

    def search(self, query, k=20):
        """[(doc_id, cosine), ...] for the k nearest documents to the embedded query."""
        raise NotImplementedError("TODO milestone 1: DenseRetriever.search")


# =============================================================================
# Milestone 2: measure, compare, find the headroom
# =============================================================================
def _mean(values):
    """GIVEN: mean of an iterable, 0.0 if empty."""
    values = list(values)
    return sum(values) / len(values) if values else 0.0


def evaluate(search_fn, coll, k_ndcg=10, k_recall=20):
    """Run every query in `coll.queries` through `search_fn` and score it.

    Call search_fn(query_text, max(k_ndcg, k_recall)) once per query. For each query get the
    grades of the ranked ids from coll.qrels[qid] (unjudged = 0), then nDCG@k_ndcg (the ideal
    comes from ALL the query's judged grades) and recall@k_recall (relevant means grade >= 1;
    coll.n_relevant(qid) counts them). Return

        {"ndcg": {qid: float}, "recall": {qid: float}, "ndcg_mean": float, "recall_mean": float}

    The means are macro means: one number per query, then the average of those.
    """
    raise NotImplementedError("TODO milestone 2: evaluate")


def winners(per_a, per_b, margin=0.2):
    """Split query ids by which system did clearly better, given {qid: score} for each.

    Returns {"a": [...], "b": [...], "tie": [...]}, each list sorted. A wins when
    per_a[qid] - per_b[qid] > margin (strictly), B wins when it is < -margin, otherwise tie.
    """
    raise NotImplementedError("TODO milestone 2: winners")


def union_recall(search_a, search_b, coll, k=20):
    """Mean recall of the SET of documents in either system's top k: the most a perfect merge could reach.

    For each query take the top k of both systems, union the doc ids, count the relevant ones
    (grade >= 1) and divide by coll.n_relevant(qid). Average over queries.
    """
    raise NotImplementedError("TODO milestone 2: union_recall")


# =============================================================================
# Milestone 3: reciprocal rank fusion
# =============================================================================
def rrf_scores(rankings, k=60, weights=None):
    """Reciprocal rank fusion. `rankings` is a list of rankings (lists of doc ids, best first).

    Each document earns weight / (k + rank) from every list it appears in (ranks start at 1);
    a document missing from a list earns nothing from it. `weights` defaults to 1.0 per list.
    Returns {doc_id: fused score}.

        rrf_scores([["a", "b"], ["b", "c"]], k=60)
        -> {"a": 1/61, "b": 1/62 + 1/61, "c": 1/62}
    """
    raise NotImplementedError("TODO milestone 3: rrf_scores")


def make_rrf(retrievers, depth=50, rrf_k=60, weights=None):
    """Return a search function (text, k=20) that fuses the retrievers' rankings with RRF.

    Ask each retriever for `depth` results, keep only the ORDER of each list (throw the scores
    away), fuse with rrf_scores, and return the top k as [(doc_id, fused_score), ...] ordered by
    fused score descending, ties by doc id (the `rank` helper does this).
    """
    raise NotImplementedError("TODO milestone 3: make_rrf")


# =============================================================================
# Milestone 4: normalised score fusion, and tuning alpha without fooling yourself
# =============================================================================
def min_max(scores):
    """Rescale {doc_id: score} to [0, 1]: lowest -> 0, highest -> 1. No spread -> all zeros."""
    raise NotImplementedError("TODO milestone 4: min_max")


def z_score(scores):
    """(score - mean) / standard deviation, using the POPULATION standard deviation (divide by n).

    No spread -> all zeros.
    """
    raise NotImplementedError("TODO milestone 4: z_score")


def convex(a, b, alpha, norm=min_max):
    """alpha * norm(a) + (1 - alpha) * norm(b) for two score dicts; alpha weights `a` (the lexical side).

    A document missing from one list counts as 0 for that list. Either dict may be empty.
    Returns {doc_id: fused score} over the union of the documents.
    """
    raise NotImplementedError("TODO milestone 4: convex")


def make_convex(lexical, dense, alpha=0.5, depth=50, norm=min_max):
    """Return a search function (text, k=20) fusing the two retrievers' score lists with `convex`.

    Ask each retriever for `depth` results, turn each list into a {doc_id: score} dict, fuse,
    and return the top k as [(doc_id, fused_score), ...] (best first, ties by doc id).
    """
    raise NotImplementedError("TODO milestone 4: make_convex")


def best_alpha(table):
    """`table` is {alpha: [nDCG of each query]}. Return the alpha with the highest mean.

    Ties go to the smaller alpha. (Iterate the alphas in sorted order.)
    """
    raise NotImplementedError("TODO milestone 4: best_alpha")


def leave_one_out(table):
    """The honest estimate of "tune alpha on judged queries".

    For each query i: choose alpha with best_alpha on the table WITHOUT query i, then record that
    alpha's score on query i. Return (mean held-out score, [alpha chosen for each query]).
    """
    raise NotImplementedError("TODO milestone 4: leave_one_out")


def alpha_table(coll, lexical, dense, alphas, depth=50, norm=min_max):
    """GIVEN: {alpha: [nDCG@10 per query]}, with each query's candidate lists fetched once."""
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
    """GIVEN: content terms of a text, in order, crudely stemmed ('cancelling it' -> ['cance'])."""
    return [crude_stem(t) for t in analyse(text)]


def coverage(q_terms, d_terms):
    """Fraction of the DISTINCT query terms that occur somewhere in the document.

    Both arguments are lists of stemmed terms. 0.0 if the query list is empty.
        coverage(["cance", "subsc", "cance"], ["cance", "plan"]) -> 0.5
    """
    raise NotImplementedError("TODO milestone 5: coverage")


def bigram_overlap(q_terms, d_terms):
    """Fraction of the query's adjacent term pairs that also occur adjacent, IN THE SAME ORDER, in the document.

    Pairs come from zip(terms, terms[1:]). 0.0 if the query has fewer than two terms.
        q = ["move", "money", "check", "savin"]   (move money checking savings)
        bigram_overlap(q, q)                                      -> 1.0
        bigram_overlap(q, ["move", "money", "savin", "check"])    -> 1/3  (only (move, money) survives)
    """
    raise NotImplementedError("TODO milestone 5: bigram_overlap")


def id_match(query, doc_text):
    """Among the query's tokens that contain a digit (identifiers), the fraction found verbatim in the document.

    Tokens come from `analyse` (so "E4021-B" gives "e4021" and "b"). 0.0 if the query has no
    token with a digit.
        id_match("what does e4021 mean", "E4021 on the gateway") -> 1.0
        id_match("clause 14.2", "clause 14.3 applies")           -> 0.5   (tokens 14 and 2; only 14 is there)
    """
    raise NotImplementedError("TODO milestone 5: id_match")


FEATURES = ["cosine", "bm25", "coverage", "bigram", "id_match"]


def pair_features(query, doc_text, cos, bm25_norm):
    """The feature vector of one (query, passage) pair, in the order of FEATURES:

        [cos, bm25_norm, coverage, bigram_overlap, id_match]

    `cos` and `bm25_norm` (BM25 already scaled to 0..1 within the candidate list) are passed in.
    The other three come from `stems(query)`, `stems(doc_text)` and the raw strings.
    """
    raise NotImplementedError("TODO milestone 5: pair_features")


# =============================================================================
# Milestone 6: the reranker and its pipeline
# =============================================================================
WEIGHTS = [1.0, 1.0, 1.0, 2.0, 1.0]        # GIVEN: hand-set once, round numbers, same order as FEATURES


def rerank_score(features, weights=WEIGHTS):
    """The weighted sum of the features: sum(w * f)."""
    raise NotImplementedError("TODO milestone 6: rerank_score")


class Reranker:
    """Take a first stage's top `depth` candidates, score each (query, passage) pair, reorder.

    `first_stage(text, depth)` returns [(doc_id, score)]; `dense` supplies cosines (its .vecs and
    .embedder); `bm25` supplies BM25 scores (bm25.scores(text) -> {doc_id: score}).
    `pairs_scored` counts how many pairs were read: the cost of reranking.
    """

    def __init__(self, first_stage, docs, dense, bm25, depth=30, weights=WEIGHTS):
        self.first_stage, self.docs, self.dense, self.bm25 = first_stage, docs, dense, bm25
        self.depth, self.weights = depth, weights
        self.pairs_scored = 0

    def search(self, text, k=20):
        """Rerank the first stage's top `self.depth` and return the best k: [(doc_id, score), ...].

        1. candidates = ids from self.first_stage(text, self.depth); none -> return [].
        2. qvec = self.dense.embedder.embed(text); lex = self.bm25.scores(text).
        3. Scale BM25 WITHIN the candidates: bm25_norm = lex.get(d, 0) / the largest of those
           over the candidates (0.0 if that largest is 0).
        4. For each candidate: cos = cosine(qvec, self.dense.vecs[d]); features = pair_features(text,
           self.docs[d], cos, bm25_norm); score = rerank_score(features, self.weights). Add 1 to
           self.pairs_scored per candidate.
        5. Return the top k by score, ties by doc id (the `rank` helper).
        """
        raise NotImplementedError("TODO milestone 6: Reranker.search")


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
