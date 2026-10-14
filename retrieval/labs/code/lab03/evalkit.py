"""evalkit.py: collection loading and the metrics from chapter 4 and Lab 2, GIVEN.

The functions are Lab 2's, in the same notation: a ranked list becomes a list of GRADES (one per
rank, 0 for unjudged), and `ndcg_at_k` / `recall_at_k` take that list. If you finished Lab 2 you
can replace this file's metrics with your own; the results will be identical.
"""
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))


class Collection:
    """docs {id: text}, queries [{qid, text, kind}], qrels {qid: {doc_id: grade}}."""

    def __init__(self, docs, queries, qrels):
        self.docs, self.queries, self.qrels = docs, queries, qrels

    def n_relevant(self, qid):
        return sum(1 for g in self.qrels[qid].values() if g >= 1)


def load_collection(folder=HERE):
    with open(os.path.join(folder, "corpus.json"), encoding="utf-8") as fh:
        docs = json.load(fh)
    with open(os.path.join(folder, "queries.json"), encoding="utf-8") as fh:
        queries = json.load(fh)
    qrels = {}
    with open(os.path.join(folder, "qrels.txt"), encoding="utf-8") as fh:
        for line in fh:
            if line.strip() and not line.startswith("#"):
                q, _, d, g = line.split()
                qrels.setdefault(q, {})[d] = int(g)
    return Collection(docs, queries, qrels)


def rank(scores):
    """{doc_id: score} -> doc ids, best first; ties broken by doc id so results never flicker."""
    return [d for d, _ in sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))]


def grades_for(ranking, qrel):
    return [qrel.get(d, 0) for d in ranking]


def dcg(grades, k):
    return sum(g / math.log2(i + 1) for i, g in enumerate(grades[:k], 1))


def ndcg_at_k(grades, k, all_grades):
    best = dcg(sorted(all_grades, reverse=True), k)
    return dcg(grades, k) / best if best > 0 else 0.0


def recall_at_k(grades, k, n_relevant):
    return sum(1 for g in grades[:k] if g >= 1) / n_relevant if n_relevant else 0.0
