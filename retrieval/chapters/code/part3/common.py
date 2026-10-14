"""Shared helpers: tokeniser, BM25, a stand-in dense embedder (LSA), nDCG."""
import math
import re
from collections import Counter

import numpy as np

from corpus import DOCS, QUERIES

STOP = set("a an the of to and or is are in on for by it be as at from with your you we our can i my do how that this".split())


def tok(text, stop=False):
    ws = re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)?", text.lower())
    return [w for w in ws if not (stop and w in STOP)]


def stem(w):
    for suf in ("ing", "ed", "es", "s"):
        if w.endswith(suf) and len(w) - len(suf) >= 4:
            return w[: -len(suf)]
    return w


def terms(text):
    return [stem(w) for w in tok(text, stop=True)]


IDS = list(DOCS)
DT = {d: terms(t) for d, t in DOCS.items()}
N = len(IDS)
AVGDL = sum(len(v) for v in DT.values()) / N
DF = Counter(t for v in DT.values() for t in set(v))
TF = {d: Counter(v) for d, v in DT.items()}


def idf(t):
    return math.log(1 + (N - DF[t] + 0.5) / (DF[t] + 0.5))


def bm25(query, k1=1.2, b=0.75):
    q = terms(query)
    out = {}
    for d in IDS:
        s = 0.0
        for t in q:
            tf = TF[d][t]
            if tf:
                s += idf(t) * tf * (k1 + 1) / (tf + k1 * (1 - b + b * len(DT[d]) / AVGDL))
        out[d] = s
    return out


# ---- stand-in "embedder": latent semantic analysis (SVD of the tf-idf matrix).
VOCAB = sorted(DF)
VI = {t: i for i, t in enumerate(VOCAB)}


def _tfidf(counter):
    v = np.zeros(len(VOCAB))
    for t, c in counter.items():
        if t in VI:
            v[VI[t]] = (1 + math.log(c)) * idf(t)
    return v


M = np.stack([_tfidf(TF[d]) for d in IDS])  # docs x terms
K = 7
U, S, Vt = np.linalg.svd(M, full_matrices=False)
PROJ = Vt[:K].T  # terms x K


def _unit(v):
    n = np.linalg.norm(v)
    return v / n if n else v


DOC_VEC = {d: _unit(M[i] @ PROJ) for i, d in enumerate(IDS)}


def embed(text):
    return _unit(_tfidf(Counter(terms(text))) @ PROJ)


def dense(query):
    q = embed(query)
    return {d: float(q @ DOC_VEC[d]) for d in IDS}


def rank(scores, floor=0.0):
    return [d for d, s in sorted(scores.items(), key=lambda kv: (-kv[1], kv[0])) if s > floor]


def ndcg(ranking, qrels, k=10):
    dcg = sum((2 ** qrels.get(d, 0) - 1) / math.log2(i + 2) for i, d in enumerate(ranking[:k]))
    ideal = sorted(qrels.values(), reverse=True)[:k]
    idcg = sum((2 ** g - 1) / math.log2(i + 2) for i, g in enumerate(ideal))
    return dcg / idcg if idcg else 0.0


def recall(ranking, qrels, k):
    rel = {d for d, g in qrels.items() if g > 0}
    return len(rel & set(ranking[:k])) / len(rel)
