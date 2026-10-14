"""Self-check for Lab 3: Hybrid Retrieval & Reranking.

    python3 check.py                  # checks your starter.py
    python3 check.py solution         # checks the reference solution
    python3 check.py solution 4       # only milestone 4
    python3 check.py solution 4 3     # milestone 4, replaying ONLY the random scenario of seed 3

Everything is deterministic: the collection is three files in this folder (corpus.json,
queries.json, qrels.txt, made by make_data.py), the embedder hashes with CRC32, and every random
scenario comes from a seeded random.Random. No network, no clock. The whole check takes a few
seconds. Prints a tick, a cross, or "not implemented yet" for each milestone.
"""
import importlib
import math
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True

args = sys.argv[1:]
target = args[0] if args and not args[0].isdigit() else "starter"
rest = [a for a in args if a.isdigit()]
ONLY = int(rest[0]) if rest else None
ONLY_SEED = int(rest[1]) if len(rest) > 1 else None
mod = importlib.import_module(target)
from evalkit import Collection, load_collection  # noqa: E402

results = []


def seeds(default):
    return [ONLY_SEED] if ONLY_SEED is not None else list(default)


def check(number, name, fn):
    if ONLY is not None and ONLY != number:
        return
    try:
        note = fn()
        print(f"  ✔ {name}")
        for line in (note or "").splitlines():
            print(f"      {line}")
        results.append(True)
    except NotImplementedError as e:
        print(f"  … {name}: not implemented yet ({e})")
        results.append(False)
    except AssertionError as e:
        print(f"  ✘ {name}: {e}")
        results.append(False)
    except Exception as e:
        import traceback
        tb = traceback.extract_tb(e.__traceback__)
        where = next((f"{f.name}() line {f.lineno}" for f in reversed(tb) if f.filename.endswith(f"{target}.py")), "?")
        print(f"  ✘ {name}: {type(e).__name__}: {e}   [in {where}]")
        results.append(False)


def near(a, b, tol=1e-9):
    return abs(a - b) <= tol


_WORLD = {}


def world():
    """The real collection, the two first-stage retrievers (built with the module under test)."""
    if not _WORLD:
        coll = load_collection()
        from bm25 import Bm25Index
        from embedder import TrigramEmbedder
        bm25 = Bm25Index(coll.docs)
        dense = mod.DenseRetriever(coll.docs, TrigramEmbedder(coll.docs))
        _WORLD.update(coll=coll, bm25=bm25, dense=dense)
    return _WORLD["coll"], _WORLD["bm25"], _WORLD["dense"]


# -----------------------------------------------------------------------------
# An independent oracle: plain loops, own cosine, own metrics (not the module under test)
# -----------------------------------------------------------------------------
def o_cos(a, b):
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(y * y for y in b))
    return sum(x * y for x, y in zip(a, b)) / (na * nb) if na and nb else 0.0


def o_ndcg(ids, qrel, k=10):
    g = [qrel.get(d, 0) for d in ids[:k]]
    dcg = sum(v / math.log2(i + 2) for i, v in enumerate(g))
    ideal = sorted(qrel.values(), reverse=True)[:k]
    idcg = sum(v / math.log2(i + 2) for i, v in enumerate(ideal))
    return dcg / idcg if idcg else 0.0


def o_recall(ids, qrel, k=20):
    n = sum(1 for v in qrel.values() if v >= 1)
    return sum(1 for d in ids[:k] if qrel.get(d, 0) >= 1) / n if n else 0.0


def o_eval(fn, coll):
    nd, rc = [], []
    for q in coll.queries:
        ids = [d for d, _ in fn(q["text"], 20)]
        nd.append(o_ndcg(ids, coll.qrels[q["qid"]]))
        rc.append(o_recall(ids, coll.qrels[q["qid"]]))
    return sum(nd) / len(nd), sum(rc) / len(rc)


def o_best(table):
    best, arg = -1.0, None
    for a in sorted(table):
        m = sum(table[a]) / len(table[a])
        if m > best + 1e-12:
            best, arg = m, a
    return arg


def o_loo(table):
    n = len(next(iter(table.values())))
    got, chosen = [], []
    for i in range(n):
        sub = {a: [x for j, x in enumerate(v) if j != i] for a, v in table.items()}
        a = o_best(sub)
        chosen.append(a)
        got.append(table[a][i])
    return sum(got) / n, chosen


# =============================================================================
# Milestone 1: dense retrieval
# =============================================================================
def m1():
    assert near(mod.cosine([1, 2], [2, 4]), 1.0), "cosine of parallel vectors is 1.0"
    assert near(mod.cosine([1, 0], [0, 1]), 0.0), "cosine of orthogonal vectors is 0.0"
    assert near(mod.cosine([1, 0], [-3, 0]), -1.0), "opposite directions give -1.0"
    assert near(mod.cosine([3, 4], [4, 3]), 24 / 25), f"cosine([3,4],[4,3]) is 24/25 = 0.96; got {mod.cosine([3, 4], [4, 3])}"
    assert mod.cosine([0, 0], [1, 2]) == 0.0 and mod.cosine([1, 2], [0, 0]) == 0.0, "a zero vector has no direction: cosine 0.0, not ZeroDivisionError"

    vecs = {"b": [1.0, 0.0], "a": [0.0, 1.0], "c": [1.0, 1.0], "z": [-1.0, 0.0], "d": [1.0, 0.0]}
    got = mod.cosine_topk([1.0, 0.0], vecs, 3)
    want = [("b", 1.0), ("d", 1.0), ("c", 1 / math.sqrt(2))]
    assert [d for d, _ in got] == [d for d, _ in want], (
        f"cosine_topk: best first, ties (b and d both score 1.0) by doc id.\n      expected {[d for d, _ in want]}\n      got      {[d for d, _ in got]}")
    assert all(near(s, w) for (_, s), (_, w) in zip(got, want)), f"cosine_topk returns the cosines themselves (not negatives); got {got}"
    assert len(mod.cosine_topk([1.0, 0.0], vecs, 50)) == 5, "k larger than the collection returns every document"
    assert mod.cosine_topk([1.0, 0.0], vecs, 0) == [], "k = 0 returns an empty list"
    assert mod.cosine_topk([1.0, 0.0], {}, 5) == [], "an empty collection returns an empty list"

    for s in seeds(range(1, 7)):
        rng = random.Random(s)
        d = rng.randint(2, 8)
        docs = {f"d{i:02d}": [rng.choice([-1, 0, 0, 1, 2]) + rng.random() * (i % 2) for _ in range(d)] for i in range(rng.randint(5, 40))}
        q = [rng.gauss(0, 1) for _ in range(d)]
        k = rng.randint(1, 45)
        want = sorted(((o_cos(q, v), x) for x, v in docs.items()), key=lambda t: (-t[0], t[1]))[:k]
        got = mod.cosine_topk(q, docs, k)
        assert [x for x, _ in got] == [x for _, x in want], f"seed {s}: top-{k} ids differ from a full sort by (-cosine, id)"
        assert all(near(a, b, 1e-9) for (_, a), (b, _) in zip(got, want)), f"seed {s}: scores differ from the oracle's cosines"

    coll, bm25, dense = world()
    assert set(dense.vecs) == set(coll.docs), "the retriever holds one vector per document"
    some = sorted(coll.docs)[7]
    top = dense.search(coll.docs[some], 3)
    assert top[0][0] == some and near(top[0][1], 1.0, 1e-9), f"searching with a document's own text should return that document first with cosine 1.0; got {top[0]}"
    assert len(dense.search("anything at all", 20)) == 20 and dense.search("anything at all", 5) == dense.search("anything at all", 20)[:5], \
        "search(query, k) is the first k of a longer list"
    nd, rc = o_eval(dense.search, coll)
    assert abs(nd - 0.786) < 0.005 and abs(rc - 0.792) < 0.005, (
        f"dense retrieval over the real collection should give nDCG@10 about 0.786 and recall@20 about 0.792 (the oracle's numbers); got {nd:.3f} and {rc:.3f}")
    return f"dense stand-in over {len(coll.docs)} passages, {len(coll.queries)} queries: nDCG@10 {nd:.3f}, recall@20 {rc:.3f}"


# =============================================================================
# Milestone 2: measure, compare, find the headroom
# =============================================================================
def m2():
    docs = {"a": "x", "b": "y", "c": "z", "x": "w"}
    qrels = {"q1": {"a": 3, "b": 1, "c": 0}, "q2": {"c": 2}}
    queries = [{"qid": "q1", "text": "one", "kind": "t"}, {"qid": "q2", "text": "two", "kind": "t"}]
    coll = Collection(docs, queries, qrels)
    calls = []
    answers = {"one": ["b", "x", "a"], "two": ["x", "a"]}

    def fake(text, k):
        calls.append((text, k))
        return [(d, 1.0 / (i + 1)) for i, d in enumerate(answers[text])][:k]

    r = mod.evaluate(fake, coll)
    assert calls == [("one", 20), ("two", 20)], f"evaluate calls search_fn(text, max(k_ndcg, k_recall)) once per query, in order; got {calls}"
    want_q1 = (1 + 0 + 3 / math.log2(4)) / (3 + 1 / math.log2(3))
    assert near(r["ndcg"]["q1"], want_q1, 1e-9), (
        f"q1 ranks grades [1, 0, 3]: DCG = 1 + 0 + 3/2, ideal = 3 + 1/log2(3); nDCG@10 should be {want_q1:.4f}; got {r['ndcg']['q1']}")
    assert near(r["recall"]["q1"], 1.0) and near(r["recall"]["q2"], 0.0) and near(r["ndcg"]["q2"], 0.0), \
        f"q1 finds both relevant documents (recall 1.0); q2's one relevant document is not returned (recall 0, nDCG 0); got {r}"
    assert near(r["ndcg_mean"], want_q1 / 2) and near(r["recall_mean"], 0.5), f"the means are macro means over queries; got {r['ndcg_mean']}, {r['recall_mean']}"
    calls.clear()
    r3 = mod.evaluate(fake, coll, k_ndcg=2, k_recall=3)
    assert calls[0] == ("one", 3), f"with k_ndcg=2 and k_recall=3 the search is asked for 3 results; got {calls[0]}"
    assert near(r3["ndcg"]["q1"], (1 + 0) / (3 + 1 / math.log2(3))), "nDCG@2 only counts the first two ranks (grades 1, 0)"

    w = mod.winners({"a": 0.9, "b": 0.5, "c": 0.5, "d": 0.1}, {"a": 0.5, "b": 0.7, "c": 0.3, "d": 0.8}, margin=0.2)
    assert w == {"a": ["a"], "b": ["d"], "tie": ["b", "c"]}, (
        f"winners: A wins when its score is MORE than margin higher (0.7 and 0.3 are not: 0.2 is not > 0.2); expected a=['a'], b=['d'], tie=['b','c']; got {w}")
    assert mod.winners({}, {}) == {"a": [], "b": [], "tie": []}, "no queries, three empty lists"

    def only(ids):
        return lambda text, k: [(d, 1.0) for d in ids][:k]

    ur = mod.union_recall(only(["a", "x"]), only(["b", "c"]), coll, k=2)
    assert near(ur, (1.0 + 1.0) / 2), f"union of {{a,x}} and {{b,c}}: q1 finds a and b (2 of 2), q2 finds c (1 of 1) so 1.0; got {ur}"
    ur = mod.union_recall(only(["a", "x"]), only(["a", "x"]), coll, k=2)
    assert near(ur, (0.5 + 0.0) / 2), f"the same list twice adds nothing: q1 finds 1 of 2, q2 none, so 0.25; got {ur}"

    coll, bm25, dense = world()
    rb, rd = mod.evaluate(bm25.search, coll), mod.evaluate(dense.search, coll)
    for name, rep, fn in (("bm25", rb, bm25.search), ("dense", rd, dense.search)):
        nd, rc = o_eval(fn, coll)
        assert near(rep["ndcg_mean"], nd, 1e-9) and near(rep["recall_mean"], rc, 1e-9), \
            f"{name}: oracle says nDCG@10 {nd:.4f} and recall@20 {rc:.4f}; you got {rep['ndcg_mean']:.4f} and {rep['recall_mean']:.4f}"
        assert len(rep["ndcg"]) == len(coll.queries), f"{name}: one score per query"
    w = mod.winners(rb["ndcg"], rd["ndcg"])
    kinds = {q["qid"]: q["kind"] for q in coll.queries}
    from collections import Counter
    bm_kinds, de_kinds = Counter(kinds[q] for q in w["a"]), Counter(kinds[q] for q in w["b"])
    assert bm_kinds["code"] >= 8 and de_kinds["variant"] >= 8, (
        f"BM25 should win clearly on identifier queries and dense on spelling-variant queries; got BM25 wins {dict(bm_kinds)}, dense wins {dict(de_kinds)}")
    ur = mod.union_recall(bm25.search, dense.search, coll)
    assert ur > max(rb["recall_mean"], rd["recall_mean"]) + 0.01, "the union of the two top-20 lists must find more than either alone"
    return (f"BM25  nDCG@10 {rb['ndcg_mean']:.3f}  recall@20 {rb['recall_mean']:.3f}   clear wins {len(w['a'])}\n"
            f"dense nDCG@10 {rd['ndcg_mean']:.3f}  recall@20 {rd['recall_mean']:.3f}   clear wins {len(w['b'])}   ties {len(w['tie'])}\n"
            f"union of the two top-20 lists: recall {ur:.3f}")


# =============================================================================
# Milestone 3: reciprocal rank fusion
# =============================================================================
def m3():
    bm = ["r2", "r1", "t1", "t2"]
    dn = ["r2", "t1", "t2", "d5", "r1", "d3", "r3", "d1", "r5", "d2"]
    s = mod.rrf_scores([bm, dn], 60)
    want = {"r2": 2 / 61, "t1": 1 / 63 + 1 / 62, "r1": 1 / 62 + 1 / 65, "t2": 1 / 64 + 1 / 63, "d5": 1 / 64}
    for d, v in want.items():
        assert near(s[d], v, 1e-12), (f"chapter 10's example: RRF({d}) with k = 60 should be {v:.5f} "
                                     f"(r2 0.03279, t1 0.03200, r1 0.03151, t2 0.03150, d5 0.01562); got {s.get(d)}")
    assert set(s) == set(bm) | set(dn), "every document from any list appears once in the result"
    assert mod.rrf_scores([["a", "b"], ["b", "c"]], k=1) == {"a": 1 / 2, "b": 1 / 3 + 1 / 2, "c": 1 / 3}, "k = 1: ranks 1, 2 earn 1/2, 1/3"
    w = mod.rrf_scores([["a", "b"], ["b", "a"]], 60, weights=[1.0, 3.0])
    assert near(w["a"], 1 / 61 + 3 / 62) and near(w["b"], 1 / 62 + 3 / 61), f"weights multiply each list's contribution; got {w}"
    assert mod.rrf_scores([], 60) == {} and mod.rrf_scores([[], []], 60) == {}, "no lists, or empty lists: nothing"

    # chapter 10: B at rank r in both lists beats A (first in one list only) exactly when r < k + 2
    for k in (1, 5, 60):
        for r in sorted({2, k, k + 1, k + 3, k + 5}):
            if r < 2:
                continue
            l1 = ["A"] + [f"x{i}" for i in range(r - 2)] + ["B"]          # B at rank r; A at rank 1
            l2 = [f"y{i}" for i in range(r - 1)] + ["B"]                  # B at rank r
            sc = mod.rrf_scores([l1, l2], k)
            if r < k + 2:
                assert sc["B"] > sc["A"], f"k={k}: B at rank {r} in both lists should beat a lone first place (r < k + 2)"
            elif r > k + 2:
                assert sc["A"] > sc["B"], f"k={k}: B at rank {r} in both lists should lose to a lone first place (r > k + 2)"

    class Fake:
        def __init__(self, ids, scale=1.0):
            self.ids, self.scale, self.asked = ids, scale, []

        def search(self, text, k):
            self.asked.append(k)
            return [(d, self.scale * (len(self.ids) - i)) for i, d in enumerate(self.ids)][:k]

    f1, f2 = Fake(["a", "b", "c"]), Fake(["c", "b", "d"])
    out = mod.make_rrf([f1, f2], depth=3)("q", 10)
    assert f1.asked == [3] and f2.asked == [3], f"each retriever is asked for `depth` results, not for k; got {f1.asked}, {f2.asked}"
    assert [d for d, _ in out] == ["c", "b", "a", "d"], (
        f"fused order: c (ranks 3 and 1: 1/63 + 1/61 = 0.03227) just ahead of b (ranks 2 and 2: 2/62 = 0.03226), then a (1/61), then d (1/63); got {[d for d, _ in out]}")
    assert [d for d, _ in mod.make_rrf([f1, f2], depth=3)("q", 2)] == ["c", "b"], "the search function returns only the top k"
    big = mod.make_rrf([Fake(["a", "b", "c"], 1000.0), Fake(["c", "b", "d"], 0.001)], depth=3)("q", 10)
    assert [d for d, _ in big] == [d for d, _ in out] and all(near(x, y) for (_, x), (_, y) in zip(big, out)), \
        "RRF uses only ranks: multiplying one retriever's scores by a million changes nothing"
    tie = mod.make_rrf([Fake(["m", "z"]), Fake(["z", "m"])], depth=2)("q", 2)
    assert [d for d, _ in tie] == ["m", "z"], "equal fused scores are broken by doc id, ascending"

    coll, bm25, dense = world()
    rrf = mod.make_rrf([bm25, dense])
    nd, rc = o_eval(rrf, coll)
    nb, rb_ = o_eval(bm25.search, coll)
    nde, rde = o_eval(dense.search, coll)
    assert abs(nd - 0.782) < 0.005 and abs(rc - 0.800) < 0.005, f"RRF (k = 60, depth 50) over the real collection: nDCG@10 about 0.782, recall@20 about 0.800; got {nd:.3f}, {rc:.3f}"
    assert nd > nb + 0.05 and rc >= max(rb_, rde) - 1e-9, "fusion should beat BM25 clearly on nDCG and match the better retriever on recall"
    return (f"RRF k=60 depth 50: nDCG@10 {nd:.3f} (BM25 {nb:.3f}, dense {nde:.3f}), recall@20 {rc:.3f} (BM25 {rb_:.3f}, dense {rde:.3f})\n"
            "with k = 60 and short lists it behaves like 'count the lists': it recovers BM25's misses, but cannot beat dense on nDCG here")


# =============================================================================
# Milestone 4: score fusion and held-out alpha
# =============================================================================
def m4():
    mm = mod.min_max({"a": 41.0, "b": 6.1, "c": 5.9, "d": 5.8, "e": 5.5})
    assert near(mm["a"], 1.0) and near(mm["e"], 0.0) and near(mm["b"], 0.6 / 35.5, 1e-12), (
        f"chapter 10: min-max of 41.0, 6.1, 5.9, 5.8, 5.5 squeezes the four lower scores to 0.017, 0.011, 0.008, 0.000; got {mm}")
    assert mod.min_max({"a": 2.0, "b": 2.0}) == {"a": 0.0, "b": 0.0}, "no spread: all zeros, not ZeroDivisionError"
    z = mod.z_score({"a": 1.0, "b": 2.0, "c": 3.0})
    assert near(z["a"], -math.sqrt(1.5)) and near(z["b"], 0.0) and near(z["c"], math.sqrt(1.5)), \
        f"z-score uses the population standard deviation (divide by n): [1,2,3] -> -1.2247, 0, 1.2247; got {z}"
    assert mod.z_score({"a": 4.0, "b": 4.0}) == {"a": 0.0, "b": 0.0}, "no spread: all zeros"

    a, b = {"x": 10.0, "y": 0.0}, {"y": 0.9, "z": 0.1}
    c = mod.convex(a, b, 0.5)
    assert set(c) == {"x", "y", "z"}, "the fused list covers the union of the documents"
    assert near(c["x"], 0.5 * 1.0 + 0.5 * 0.0) and near(c["y"], 0.5 * 0.0 + 0.5 * 1.0) and near(c["z"], 0.0), (
        f"alpha = 0.5, min-max: x is 1.0 in a and missing from b (0), y is 0.0 in a and 1.0 in b, z is missing from a and 0.0 in b; got {c}")
    assert mod.convex(a, b, 1.0) == {"x": 1.0, "y": 0.0, "z": 0.0}, "alpha = 1 uses the first list only"
    assert mod.convex(a, b, 0.0) == {"x": 0.0, "y": 1.0, "z": 0.0}, "alpha = 0 uses the second list only"
    assert mod.convex({}, {"y": 3.0, "z": 1.0}, 0.3) == {"y": 0.7, "z": 0.0}, "an empty list contributes nothing (and must not crash)"
    cz = mod.convex({"p": 1.0, "q": 3.0}, {"p": 5.0, "q": 5.0}, 0.5, mod.z_score)
    assert near(cz["p"], -0.5) and near(cz["q"], 0.5), f"the norm argument is used: z-scores [-1, 1] and [0, 0] at alpha 0.5; got {cz}"

    class Fake:
        def __init__(self, hits):
            self.hits, self.asked = hits, []

        def search(self, text, k):
            self.asked.append(k)
            return self.hits[:k]

    lex, den = Fake([("a", 8.0), ("b", 2.0), ("c", 1.0)]), Fake([("b", 0.9), ("a", 0.5), ("d", 0.4)])
    out = mod.make_convex(lex, den, alpha=0.5, depth=3)("q", 3)
    assert lex.asked == [3] and den.asked == [3], "each retriever is asked for `depth` results"
    # a: 0.5*1 + 0.5*0.2 = 0.6 ; b: 0.5*(1/7) + 0.5*1 ; d: 0 + 0.5*0 ; c: 0
    assert [d for d, _ in out] == ["a", "b", "c"], f"expected a (0.6), b (0.571), then the zeros by id (c, d) cut at k=3; got {out}"
    assert near(out[0][1], 0.6) and near(out[1][1], 0.5 / 7 + 0.5), f"fused scores a = 0.6 and b = 0.5714; got {out}"

    t = {0.0: [0.1, 0.1], 0.5: [0.4, 0.2], 1.0: [0.2, 0.5]}
    assert mod.best_alpha(t) == 1.0, f"means are 0.10, 0.30 and 0.35; the best alpha is 1.0; got {mod.best_alpha(t)}"
    assert mod.best_alpha({0.8: [0.5], 0.2: [0.5], 0.5: [0.4]}) == 0.2, "a tie goes to the smaller alpha"
    held, chosen = mod.leave_one_out({0.0: [1, 1, 0], 1.0: [0, 0, 1]})
    assert near(held, 2 / 3) and chosen == [0.0, 0.0, 0.0], (
        f"hand example: leaving out query 3, alpha 0 wins on the other two (1.0 against 0.0) but scores 0 on the one left out; "
        f"mean held-out 2/3, chosen [0, 0, 0]; got {held}, {chosen}")

    for s in seeds(range(1, 9)):
        rng = random.Random(s)
        alphas = [i / 5 for i in range(6)]
        n = rng.randint(4, 15)
        table = {a: [round(rng.random(), 2) for _ in range(n)] for a in alphas}
        want_m, want_c = o_loo(table)
        got_m, got_c = mod.leave_one_out(table)
        assert got_c == want_c and near(got_m, want_m), f"seed {s}: leave_one_out chose {got_c}, the oracle {want_c}; means {got_m:.4f} against {want_m:.4f}"
        assert mod.best_alpha(table) == o_best(table), f"seed {s}: best_alpha"

    coll, bm25, dense = world()
    alphas = [i / 10 for i in range(11)]
    table = mod.alpha_table(coll, bm25, dense, alphas)
    means = {a: sum(v) / len(v) for a, v in table.items()}
    a_star = mod.best_alpha(table)
    held, chosen = mod.leave_one_out(table)
    assert a_star == 0.7 and abs(means[a_star] - 0.831) < 0.005, f"on the real collection min-max gives its best mean (0.831) at alpha 0.7; got {a_star} and {means[a_star]:.3f}"
    assert held < means[a_star] - 0.005, f"the held-out estimate must come out below the in-sample best (0.831); got {held:.3f}"
    assert all(means[a] > means[1.0] for a in (0.3, 0.5, 0.7)) and means[0.5] > means[0.0], "a plateau of good alphas, with BM25-only (alpha 1) the worst"
    ours = mod.make_convex(bm25, dense, 0.5)
    nd, rc = o_eval(ours, coll)
    assert abs(nd - 0.823) < 0.005, f"make_convex(alpha = 0.5) should reach nDCG@10 0.823 on the real collection; got {nd:.3f}"
    return (f"alpha sweep (min-max, mean nDCG@10): " + "  ".join(f"{a:.1f}:{means[a]:.3f}" for a in (0.0, 0.3, 0.5, 0.7, 0.9, 1.0)) + "\n"
            f"best in-sample alpha {a_star} ({means[a_star]:.3f}); leave-one-query-out estimate {held:.3f}")


# =============================================================================
# Milestone 5: pair features
# =============================================================================
def m5():
    assert near(mod.coverage(["cance", "subsc", "cance"], ["cance", "plan"]), 0.5), "coverage counts DISTINCT query terms: {cance, subsc}, one found -> 0.5"
    assert mod.coverage([], ["a"]) == 0.0, "an empty query covers nothing"
    assert near(mod.coverage(["a", "b"], ["b", "a", "a"]), 1.0) and mod.coverage(["a"], []) == 0.0, "all found -> 1.0, empty document -> 0.0"
    q = ["move", "money", "check", "savin"]
    assert near(mod.bigram_overlap(q, q), 1.0), "the same sequence: every pair is found"
    assert near(mod.bigram_overlap(q, ["move", "money", "savin", "check"]), 1 / 3), (
        "(move, money) survives, (money, check) and (check, savin) do not: 1/3. Pairs must be adjacent AND in order")
    assert near(mod.bigram_overlap(q, ["check", "savin", "money", "move"]), 1 / 3), "only (check, savin) survives when the document runs the other way round"
    assert mod.bigram_overlap(["move"], ["move"]) == 0.0 and mod.bigram_overlap([], ["a", "b"]) == 0.0, "fewer than two query terms: no pairs, 0.0"
    assert near(mod.bigram_overlap(["a", "b", "c"], ["z", "a", "b", "z", "b", "c"]), 1.0), "pairs may be found anywhere in the document, not only at the start"

    assert near(mod.id_match("what does e4021 mean", "E4021 on the gateway: declined"), 1.0), "e4021 appears in the document: 1.0"
    assert near(mod.id_match("what does e4021 mean", "E4012 on the gateway: declined"), 0.0), "a near-identical code is not a match"
    assert near(mod.id_match("clause 14.2", "clause 14.3 applies"), 0.5), "'14.2' gives the tokens 14 and 2; only 14 is in the document: 0.5"
    assert mod.id_match("refund policy", "refund policy 14") == 0.0, "no digit in the query, nothing to match: 0.0"
    assert near(mod.id_match("E4021-B checkout", "E4021 means the same"), 1.0), "digit-bearing query tokens are e4021 only ('b' has no digit)"

    f = mod.pair_features("move money from checking to savings", "To move money from checking to savings, open Transfers.", 0.8, 0.5)
    assert len(f) == 5 and near(f[0], 0.8) and near(f[1], 0.5), f"the first two features are the cosine and the scaled BM25 passed in; got {f}"
    assert near(f[2], 1.0) and near(f[3], 1.0) and f[4] == 0.0, f"all query terms present, all pairs in order, no identifier; got {f}"
    g = mod.pair_features("move money from checking to savings", "To move money from savings to checking, open Transfers.", 0.8, 0.5)
    assert near(g[2], 1.0) and near(g[3], 1 / 3), f"the reversed passage has full coverage but only one of three pairs in order; got coverage {g[2]}, bigram {g[3]}"
    h = mod.pair_features("cancelling subscriptions", "Cancel your subscription in Billing.", 0.0, 0.0)
    assert near(h[2], 1.0), f"the crude 5-letter stems make cancelling/cancel and subscriptions/subscription match; coverage should be 1.0, got {h[2]}"

    coll, bm25, dense = world()
    order = [q for q in coll.queries if q["kind"] == "order"]
    for q in order:
        rel = coll.qrels[q["qid"]]
        right = next(d for d, g in rel.items() if g == 3)
        wrong = next(d for d, g in rel.items() if g == 0)
        fr = mod.pair_features(q["text"], coll.docs[right], 0.0, 0.0)
        fw = mod.pair_features(q["text"], coll.docs[wrong], 0.0, 0.0)
        assert abs(fr[2] - fw[2]) < 1e-9 or fr[2] >= fw[2], f"{q['qid']}: coverage cannot tell the two directions apart"
        assert fr[3] > fw[3], (f"{q['qid']} ({q['text']!r}): the bigram feature must be higher for the passage that runs the same way as the query; "
                               f"got {fr[3]:.2f} for the right one and {fw[3]:.2f} for the wrong one")
    return f"on all {len(order)} direction queries the bigram feature separates the right passage from its mirror image, where coverage and the retrievers cannot"


# =============================================================================
# Milestone 6: the reranker
# =============================================================================
def m6():
    assert near(mod.rerank_score([0.5, 1.0, 1.0, 0.5, 0.0]), 0.5 + 1.0 + 1.0 + 1.0 + 0.0), "default WEIGHTS [1, 1, 1, 2, 1]: 0.5 + 1 + 1 + 2 * 0.5 + 0"
    assert near(mod.rerank_score([1, 2, 3], [0.0, 1.0, 0.5]), 3.5) and mod.rerank_score([], []) == 0.0, "a weighted sum for any weights"

    coll, bm25, dense = world()
    rrf = mod.make_rrf([bm25, dense])
    asked = []

    def spy(text, k):
        asked.append(k)
        return rrf(text, k)

    rr = mod.Reranker(spy, coll.docs, dense, bm25, depth=12)
    q = next(x for x in coll.queries if x["kind"] == "order")
    out = rr.search(q["text"], 5)
    assert asked == [12], f"the first stage is asked for `depth` candidates; got {asked}"
    assert len(out) == 5 and rr.pairs_scored == 12, f"12 candidates are scored (pairs_scored == 12), 5 returned; got {len(out)} returned and pairs_scored {rr.pairs_scored}"
    assert out == sorted(out, key=lambda t: (-t[1], t[0])), "results are ordered by score descending, ties by doc id"
    cands = {d for d, _ in rrf(q["text"], 12)}
    assert all(d in cands for d, _ in out), "the reranker only reorders the first stage's candidates; it never adds documents"
    rr.search(q["text"], 100)
    assert rr.pairs_scored == 24 and len(rr.search(q["text"], 100)) == 12, "pairs_scored accumulates over calls; k beyond the candidate count returns what there is"
    assert mod.Reranker(lambda t, k: [], coll.docs, dense, bm25).search("anything", 5) == [], "no candidates, no results"

    # hand-checkable: the reranker's score of a candidate equals rerank_score of its pair_features
    qtext = q["text"]
    first = dict(rrf(qtext, 12))
    lex = bm25.scores(qtext)
    top = max(lex.get(d, 0.0) for d in first)
    qv = dense.embedder.embed(qtext)
    for d, sc in out:
        want = mod.rerank_score(mod.pair_features(qtext, coll.docs[d], o_cos(qv, dense.vecs[d]), lex.get(d, 0.0) / top if top else 0.0), mod.WEIGHTS)
        assert near(sc, want, 1e-9), f"{d}: score should be rerank_score(pair_features(..., cos, bm25 / largest bm25 among the candidates)) = {want:.4f}; got {sc:.4f}"

    # the 12 'order' queries: the right passage must now beat its mirror image
    right_first = 0
    for qq in coll.queries:
        if qq["kind"] != "order":
            continue
        rel = coll.qrels[qq["qid"]]
        right = next(d for d, g in rel.items() if g == 3)
        wrong = next(d for d, g in rel.items() if g == 0)
        ids = [d for d, _ in mod.Reranker(rrf, coll.docs, dense, bm25).search(qq["text"], 20)]
        if right in ids and (wrong not in ids or ids.index(right) < ids.index(wrong)):
            right_first += 1
    assert right_first == 12, f"after reranking, the right direction should outrank the mirror image on every direction query; it did on {right_first} of 12"

    full = mod.Reranker(rrf, coll.docs, dense, bm25)
    nd, rc = o_eval(full.search, coll)
    n0, r0 = o_eval(rrf, coll)
    nb, _ = o_eval(bm25.search, coll)
    nde, _ = o_eval(dense.search, coll)
    assert abs(nd - 0.867) < 0.005, f"RRF + rerank (depth 30) should reach nDCG@10 about 0.867 on the real collection; got {nd:.3f}"
    assert nd > n0 + 0.06 and nd > max(nb, nde) + 0.06, f"the reranker should lift nDCG@10 by well over 0.06 above RRF ({n0:.3f}) and both single retrievers; got {nd:.3f}"
    assert full.pairs_scored <= 30 * len(coll.queries), "never more than depth pairs per query"
    no_bigram = mod.Reranker(rrf, coll.docs, dense, bm25, weights=[1.0, 1.0, 1.0, 0.0, 1.0])
    nd0, _ = o_eval(no_bigram.search, coll)
    assert nd0 < nd - 0.02, f"switching the bigram weight to 0 should cost at least 0.02 nDCG@10 (the direction queries); got {nd0:.3f} against {nd:.3f}"
    shallow = mod.Reranker(rrf, coll.docs, dense, bm25, depth=10)
    ns, rs = o_eval(shallow.search, coll)
    assert shallow.pairs_scored < full.pairs_scored / 2.5, "depth 10 reads far fewer pairs than depth 30"
    return (f"RRF {n0:.3f} -> RRF + rerank {nd:.3f} nDCG@10 (recall@20 {r0:.3f} -> {rc:.3f}); bigram weight 0 gives {nd0:.3f}\n"
            f"cost: depth 30 scored {full.pairs_scored} pairs for {len(coll.queries)} queries; depth 10 scored {shallow.pairs_scored} and reached {ns:.3f}")


MILESTONES = [
    (1, "Milestone 1: dense retrieval and cosine top-k", m1),
    (2, "Milestone 2: measuring both retrievers, and the headroom", m2),
    (3, "Milestone 3: reciprocal rank fusion", m3),
    (4, "Milestone 4: score fusion and a held-out alpha", m4),
    (5, "Milestone 5: features of a query-passage pair", m5),
    (6, "Milestone 6: the reranker", m6),
]

if __name__ == "__main__":
    t0 = time.time()
    print(f"Lab 3 checks against {target}.py\n")
    for n, name, fn in MILESTONES:
        check(n, name, fn)
    print(f"\n{sum(results)}/{len(results)} milestones passing  ({time.time() - t0:.1f} s)")
    sys.exit(0 if all(results) else 1)
