"""Self-check for Lab 4: HNSW from Scratch.

    python3 check.py                  # checks your starter.py
    python3 check.py solution         # checks the reference solution
    python3 check.py solution 4       # only milestone 4
    python3 check.py solution 4 3     # milestone 4, replaying ONLY the random scenario of seed 3

Everything is deterministic: the vectors come from a seeded random.Random (data.py), the index
draws its levels from a seeded random.Random, and every random scenario here has its own seed. No
network, no clock. The whole check takes a few seconds. Prints a tick, a cross, or "not
implemented yet" for each milestone.
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
from data import make_dataset  # noqa: E402

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


def o_dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def o_topk(vectors, q, k):
    return [i for _, i in sorted(((-o_dot(v, q), i) for i, v in enumerate(vectors)))[:k]]


def small_data(n=400, seed=3):
    return make_dataset(n=n, dim=16, clusters=10, noise=1.5, n_queries=30, seed=seed)


def bare_index(vectors, links0, M=8):
    """An HNSW whose bottom layer is set by hand (milestone 2 tests search_layer without insertion)."""
    idx = mod.HNSW(M=M, ef_construction=40, seed=0)
    idx.vectors = list(vectors)
    idx.level = [0] * len(vectors)
    idx.links = [{i: list(links0[i]) for i in range(len(vectors))}]
    idx.entry = 0
    return idx


def reachable(links, start):
    seen, stack = {start}, [start]
    while stack:
        for n in links[stack.pop()]:
            if n not in seen:
                seen.add(n)
                stack.append(n)
    return seen


_CACHE = {}


def big_index():
    if "big" not in _CACHE:
        vectors, queries = make_dataset()
        truth = [o_topk(vectors, q, 10) for q in queries]
        t0 = time.time()
        idx = mod.HNSW(M=12, ef_construction=64, seed=1).build(vectors)
        _CACHE["big"] = (idx, vectors, queries, truth, time.time() - t0)
    return _CACHE["big"]


# =============================================================================
# Milestone 1: the exact baseline and the metric
# =============================================================================
def m1():
    got = mod.exact_topk([[1, 0], [0, 1], [0.6, 0.8]], [0.0, 1.0], 2)
    assert got == [1, 2], f"the docstring example: dot products 0, 1, 0.8 against [0, 1], so the top 2 are [1, 2]; got {got}"
    same = [[1.0, 0.0]] * 4
    assert mod.exact_topk(same, [1.0, 0.0], 3) == [0, 1, 2], "equal similarities: the smaller id comes first"
    assert mod.exact_topk(same, [1.0, 0.0], 10) == [0, 1, 2, 3], "k larger than the collection returns everything"
    assert mod.exact_topk(same, [1.0, 0.0], 0) == [] and mod.exact_topk([], [1.0], 3) == [], "k = 0 or no vectors: empty list"

    for s in seeds(range(1, 7)):
        rng = random.Random(s)
        d = rng.randint(2, 6)
        vecs = [[rng.choice([-1, 0, 1]) + rng.random() * (i % 3 == 0) for _ in range(d)] for i in range(rng.randint(1, 60))]
        q = [rng.gauss(0, 1) for _ in range(d)]
        k = rng.randint(1, 20)
        assert mod.exact_topk(vecs, q, k) == o_topk(vecs, q, k), f"seed {s}: top-{k} differs from a full sort by (-dot, id)"

    assert near(mod.recall_at_k([[1, 2], [5, 6]], [[1, 2], [5, 9]]), 0.75), "docstring example: query 1 recall 1.0, query 2 recall 0.5, mean 0.75"
    assert near(mod.recall_at_k([[2, 1]], [[1, 2]]), 1.0), "order inside a list does not matter"
    assert near(mod.recall_at_k([[]], [[1, 2, 3]]), 0.0) and mod.recall_at_k([], []) == 0.0, "nothing found: 0.0; no queries: 0.0"
    assert near(mod.recall_at_k([[1, 2, 3, 4]], [[1, 2]]), 1.0), "extra results do not lower recall: it divides by the size of the truth"
    assert near(mod.recall_at_k([[1, 1, 1]], [[1, 2, 3]]), 1 / 3), "a repeated id counts once"

    vectors, queries = make_dataset()
    for q in queries[:10]:
        ids = mod.exact_topk(vectors, q, 10)
        sims = [o_dot(vectors[i], q) for i in ids]
        assert sims == sorted(sims, reverse=True) and all(o_dot(v, q) <= sims[-1] + 1e-12 for j, v in enumerate(vectors) if j not in ids), \
            "the 10 returned must be the 10 most similar, best first"
    return f"brute force over {len(vectors)} vectors = {len(vectors)} similarity computations per query: the cost every later number is compared with"


# =============================================================================
# Milestone 2: beam search inside one layer
# =============================================================================
def m2():
    # eight points on a circle, 45 degrees apart, linked in a ring
    pts = [[math.cos(math.radians(45 * i)), math.sin(math.radians(45 * i))] for i in range(8)]
    ring = [[(i - 1) % 8, (i + 1) % 8] for i in range(8)]
    q = [math.cos(math.radians(100)), math.sin(math.radians(100))]
    idx = bare_index(pts, ring)
    out = idx.search_layer(q, [0], 1, 0)
    assert [n for _, n in out] == [2], f"ef = 1 is a greedy walk: from node 0 (0 deg) towards the query at 100 deg it goes 0 -> 1 (45) -> 2 (90) and stops, since 135 deg is farther. got {out}"
    assert near(out[0][0], math.cos(math.radians(10))), "the score returned is the similarity itself, cos 10 deg"
    out = idx.search_layer(q, [0], 3, 0)
    assert [n for _, n in out] == [2, 3, 1], f"ef = 3: the three nearest found are nodes 2 (90 deg), 3 (135 deg), 1 (45 deg), best first; got {[n for _, n in out]}"
    out = idx.search_layer(q, [0], 20, 0)
    assert len(out) == 8, "ef larger than the layer returns every reachable node, no more"
    assert [n for _, n in out] == o_topk(pts, q, 8), "and in exact order of similarity"
    assert [n for _, n in idx.search_layer(pts[5], [0], 1, 0)] == [5], "a query equal to a node finds that node"
    two = idx.search_layer(q, [0, 6], 2, 0)
    assert [n for _, n in two] == [2, 3], f"several entry points are all scored and all seed the search; got {two}"
    assert idx.search_layer(q, [2], 1, 0)[0][1] == 2, "starting on the answer, the answer stays"

    # no node is scored twice in one call, and dist_calls counts exactly what was scored
    scored = []
    orig = idx.sims
    idx.sims = lambda qq, ids: (scored.extend(ids), orig(qq, ids))[1]
    before = idx.dist_calls
    idx.search_layer(q, [0], 8, 0)
    assert len(scored) == len(set(scored)), f"a node must be scored at most once per search (keep a visited set); scored {sorted(scored)}"
    assert idx.dist_calls - before == len(scored) == 8, f"all 8 nodes are reachable and each is scored once; counted {idx.dist_calls - before}"

    # a real neighbour graph: 400 clustered vectors, each linked to its 8 nearest
    vectors, queries = small_data()
    knn = [[j for j in o_topk(vectors, vectors[i], 9) if j != i][:8] for i in range(len(vectors))]
    big = bare_index(vectors, knn)
    comp = reachable(knn, 0)
    for qi, q in enumerate(queries[:12]):
        cur = 0                                       # an independent greedy walk
        while True:
            nxt = max(knn[cur] + [cur], key=lambda n: (o_dot(vectors[n], q), -n))
            if nxt == cur:
                break
            cur = nxt
        got = big.search_layer(q, [0], 1, 0)
        assert [n for _, n in got] == [cur], f"query {qi}: ef = 1 should end where a plain greedy walk from node 0 ends (node {cur}); got {got}"
        want = [i for i in o_topk(vectors, q, len(vectors)) if i in comp][:len(comp)]
        full = big.search_layer(q, [0], len(vectors), 0)
        assert [n for _, n in full] == want, f"query {qi}: with ef >= the layer's size the answer is the exact ranking of all reachable nodes"
        sims = [s for s, _ in full]
        assert sims == sorted(sims, reverse=True), "results come back best first"
    truth = [o_topk(vectors, q, 10) for q in queries]
    rec, calls, nearest = [], [], []
    for ef in (1, 4, 16, 64):
        before = big.dist_calls
        found = [[n for _, n in big.search_layer(q, [0], ef, 0)] for q in queries]
        rec.append(sum(len(set(f[:10]) & set(t)) / 10 for f, t in zip(found, truth)) / len(queries))
        nearest.append(sum(1 for f, t in zip(found, truth) if f[0] == t[0]) / len(queries))
        calls.append((big.dist_calls - before) / len(queries))
    assert all(a <= b + 0.01 for a, b in zip(rec, rec[1:])), f"recall of a single-layer search should rise with ef; got {[round(r, 2) for r in rec]}"
    assert calls == sorted(calls) and calls[-1] < len(vectors), f"cost should rise with ef and stay below brute force ({len(vectors)}); got {[round(c) for c in calls]}"
    assert nearest[0] <= 0.5, f"a greedy walk (ef = 1) from a fixed node on this single-layer graph should often stop in a local optimum: it found the true nearest neighbour for {nearest[0]:.0%} of queries, expected at most 50%"
    assert rec[-1] >= 0.9 and nearest[-1] >= 0.95, f"ef = 64 should find at least 90% of the true top 10 and the true nearest for almost every query; got {rec[-1]:.2f} and {nearest[-1]:.2f}"
    return ("single-layer search on a 400-node neighbour graph (from a fixed entry point):\n"
            + "\n".join(f"  ef {ef:>3}: true nearest found for {h:.0%} of queries, recall@10 {r:.2f}, {c:.0f} similarities per query (brute force: {len(vectors)})"
                        for ef, h, r, c in zip((1, 4, 16, 64), nearest, rec, calls)))


# =============================================================================
# Milestone 3: levels and neighbour selection
# =============================================================================
class _Fixed:
    def __init__(self, values):
        self.values = list(values)

    def random(self):
        return self.values.pop(0)


def m3():
    mL = 1 / math.log(4)
    got = [mod.random_level(_Fixed([u]), mL) for u in (0.0, 0.2, 0.9, 0.99)]
    assert got == [0, 0, 1, 3], (f"floor(-ln(1 - u) * mL) with M = 4: u = 0 gives 0, u = 0.2 gives 0.16 -> 0, "
                                 f"u = 0.9 gives 1.66 -> 1, u = 0.99 gives 3.32 -> 3; got {got}")
    for s in seeds(range(1, 4)):
        for M in (4, 8, 16):
            rng = random.Random(s)
            lv = [mod.random_level(rng, 1 / math.log(M)) for _ in range(20000)]
            assert all(isinstance(x, int) and x >= 0 for x in lv), "levels are non-negative integers"
            p1, p2 = sum(1 for x in lv if x >= 1) / len(lv), sum(1 for x in lv if x >= 2) / len(lv)
            assert abs(p1 - 1 / M) < 0.012 and abs(p2 - 1 / M ** 2) < 0.006, (
                f"seed {s}, M = {M}: P(level >= 1) should be about 1/M = {1 / M:.3f} and P(level >= 2) about 1/M^2 = {1 / M ** 2:.4f}; got {p1:.3f} and {p2:.4f}")

    idx = mod.HNSW(M=4)
    # base node at angle 0; candidates at 10, 20 and -80 degrees (ids 0, 1, 2), given best first
    ang = [10, 20, -80]
    idx.vectors = [[math.cos(math.radians(a)), math.sin(math.radians(a))] for a in ang]
    cands = [(math.cos(math.radians(a)), i) for i, a in enumerate(ang)]
    simple = idx.select_simple(cands, 2)
    assert [c for _, c in simple] == [0, 1], f"select_simple keeps the closest m: ids 0 and 1; got {simple}"
    assert [c for _, c in idx.select_simple(cands, 9)] == [0, 1, 2], "fewer candidates than m: keep them all"
    heur = idx.select_heuristic(cands, 3)
    assert [c for _, c in heur] == [0, 2], (
        "select_heuristic: candidate 1 (20 deg) is closer to candidate 0 (10 deg, cos 10 = 0.985) than to the base (cos 20 = 0.940), so it is dropped; "
        f"candidate 2 (-80 deg) is closer to the base (0.174) than to candidate 0 (0.0), so it stays. expected [0, 2]; got {[c for _, c in heur]}")
    assert heur[0] == cands[0] and heur[1] == cands[2], "the pairs keep their similarity to the base node"
    assert [c for _, c in idx.select_heuristic(cands, 1)] == [0], "m = 1 keeps only the best"
    idx.vectors = [[1.0, 0.0], [1.0, 0.0], [0.6, -0.8]]
    assert [c for _, c in idx.select_heuristic([(1.0, 0), (1.0, 1), (0.7, 2)], 3)] == [0, 2], (
        "candidate 1 is an exact copy of candidate 0: its similarity to the base (1.0) only EQUALS its similarity to the kept twin (1.0), "
        "and the test is strict ('>'), so it is dropped; candidate 2 (0.7 against 0.6) stays")
    assert idx.select_heuristic([], 5) == [], "no candidates, nothing kept"

    # on clustered data the heuristic spreads links over more clusters than the simple rule
    vectors, _ = small_data()
    idx.vectors = vectors
    spread_simple = spread_heur = 0.0
    for base in range(0, 400, 20):
        cand = sorted(((o_dot(vectors[base], vectors[j]), j) for j in range(len(vectors)) if j != base), key=lambda t: (-t[0], t[1]))[:30]
        a = [j for _, j in idx.select_simple(cand, 6)]
        b = [j for _, j in idx.select_heuristic(cand, 6)]
        mean_pair = lambda ids: sum(o_dot(vectors[x], vectors[y]) for x in ids for y in ids if x < y) / max(1, len(ids) * (len(ids) - 1) / 2)
        spread_simple += mean_pair(a)
        spread_heur += mean_pair(b)
    assert spread_heur < spread_simple, "the heuristic's neighbours should be less similar to one another, on average, than the 6 closest"
    return f"mean similarity between a node's own neighbours: 6 closest {spread_simple / 20:.3f}, heuristic {spread_heur / 20:.3f} (lower = more spread out)"


# =============================================================================
# Milestone 4: insertion
# =============================================================================
def m4():
    vectors, queries = small_data()
    for s in seeds([5, 6]):
        M = 6
        idx = mod.HNSW(M=M, ef_construction=40, seed=s)
        ids = [idx.add(v) for v in vectors]
        n = len(vectors)
        assert ids == list(range(n)), "add returns 0, 1, 2, ... in order of insertion"
        rng = random.Random(s)
        mL = 1 / math.log(M)
        want = [int(-math.log(1.0 - rng.random()) * mL) for _ in range(n)]
        assert idx.level == want, (f"seed {s}: draw exactly one random number per insertion, in order, with random_level(self.rng, self.mL); "
                                   f"the first levels should be {want[:12]} but are {idx.level[:12]}")
        assert len(idx.links) == max(want) + 1, f"one dict of links per layer: {max(want) + 1} layers expected, got {len(idx.links)}"
        for layer, d in enumerate(idx.links):
            members = {i for i in range(n) if idx.level[i] >= layer}
            assert set(d) == members, f"seed {s}: layer {layer} must hold exactly the nodes whose level is at least {layer}; it holds {len(d)}, expected {len(members)}"
            cap = 2 * M if layer == 0 else M
            for i, nb in d.items():
                assert len(nb) <= cap, f"seed {s}: node {i} on layer {layer} has {len(nb)} links, above the cap {cap} (call self.shrink when a list overflows)"
                assert i not in nb, f"seed {s}: node {i} is linked to itself on layer {layer}"
                assert len(set(nb)) == len(nb), f"seed {s}: node {i} has a repeated neighbour on layer {layer}"
                assert all(x in d for x in nb), f"seed {s}: node {i} on layer {layer} links to a node that is not on that layer"
        assert idx.level[idx.entry] == max(idx.level) and idx.top_layer == max(idx.level), "the entry point must live on the top layer"
        assert min(idx.degrees(0)) >= 1, "every node keeps at least one link on layer 0"
        seen = reachable(idx.links[0], idx.entry)
        assert len(seen) >= 0.98 * n, f"seed {s}: only {len(seen)} of {n} nodes can be reached from the entry point on layer 0"
        sizes = idx.layer_sizes()
        assert sizes[0] == n and 0.4 * n / M < sizes[1] < 2.0 * n / M, f"layer sizes should shrink by about 1/M = 1/{M} each layer; got {sizes}"

    idx = mod.HNSW(M=6, ef_construction=40, seed=5)
    idx.build(vectors)
    found = [[n for _, n in idx.search_layer(q, [idx.entry], 60, 0)][:10] for q in queries]
    truth = [o_topk(vectors, q, 10) for q in queries]
    rec = sum(len(set(f) & set(t)) / 10 for f, t in zip(found, truth)) / len(queries)
    assert rec >= 0.9, f"a layer-0 beam search of width 60 over your graph should find at least 90% of the true top 10; got {rec:.2f}. The graph is poorly connected: check the neighbour selection and the reverse links"

    twin = mod.HNSW(M=6, ef_construction=40, seed=5).build(vectors)
    assert twin.links == idx.links and twin.entry == idx.entry, "same seed and same data must give the same graph"

    dup = mod.HNSW(M=4, ef_construction=20, seed=1)
    for v in [[1.0, 0.0]] * 6 + [[0.0, 1.0], [0.6, 0.8]]:
        dup.add(v)
    assert min(dup.degrees(0)) >= 1, "even identical vectors keep at least one link (the closest candidate is always kept)"

    one = mod.HNSW(M=4)
    assert one.add([1.0, 0.0]) == 0 and one.entry == 0 and one.links[0] == {0: []}, "the first node becomes the entry point and has no links"
    return (f"400 nodes, M = 6: layer sizes {idx.layer_sizes()}; layer-0 degrees {min(idx.degrees(0))} to {max(idx.degrees(0))} (cap 12); "
            f"beam search of width 60 finds {rec:.0%} of the true top 10")


# =============================================================================
# Milestone 5: search
# =============================================================================
def m5():
    empty = mod.HNSW(M=4)
    assert empty.search([1.0, 0.0], 5, 10) == [], "an empty index returns []"
    one = mod.HNSW(M=4).build([[1.0, 0.0]])
    assert one.search([0.0, 1.0], 5, 10) == [0], "k larger than the index returns every node"

    vectors, queries = small_data()
    idx = mod.HNSW(M=6, ef_construction=40, seed=5).build(vectors)
    truth = [o_topk(vectors, q, 10) for q in queries]
    assert len(idx.search(queries[0], 10, 3)) == 10, "ef smaller than k is raised to k: the beam on layer 0 has width max(ef, k)"
    assert idx.search(queries[0], 0, 10) == [], "k = 0 returns []"
    full = [idx.search(q, 10, len(vectors)) for q in queries]
    rec = sum(len(set(f) & set(t)) / 10 for f, t in zip(full, truth)) / len(queries)
    assert rec >= 0.99, f"with ef as large as the index the search is exhaustive over the connected graph: recall should be about 1.0; got {rec:.3f}"
    for q in queries[:5]:
        ids = idx.search(q, 10, 40)
        sims = [o_dot(vectors[i], q) for i in ids]
        assert sims == sorted(sims, reverse=True) and len(set(ids)) == 10, "results are distinct and best first"
    recs = []
    for ef in (10, 40, 160):
        found = [idx.search(q, 10, ef) for q in queries]
        recs.append(sum(len(set(f) & set(t)) / 10 for f, t in zip(found, truth)) / len(queries))
    assert all(a <= b + 0.01 for a, b in zip(recs, recs[1:])), f"recall should not fall as ef grows; got {[round(r, 3) for r in recs]}"

    idx2, vecs, qs, tr, built = big_index()
    n = len(vecs)
    out = {}
    for ef in (10, 80):
        before = idx2.dist_calls
        found = [idx2.search(q, 10, ef) for q in qs]
        calls = (idx2.dist_calls - before) / len(qs)
        out[ef] = (sum(len(set(f) & set(t)) / 10 for f, t in zip(found, tr)) / len(qs), calls)
    assert out[80][0] >= 0.97, f"{n} nodes, M = 12, ef = 80: recall@10 should be at least 0.97; got {out[80][0]:.3f}"
    assert out[80][1] < 0.5 * n, f"ef = 80 should cost well under half of brute force ({n}); you computed {out[80][1]:.0f} similarities per query. Are you scoring nodes twice, or searching with ef = max(ef, k) on the upper layers?"
    assert out[10][0] < out[80][0] - 0.1, f"recall must rise clearly between ef = 10 and ef = 80; got {out[10][0]:.3f} and {out[80][0]:.3f}"
    assert out[10][1] < out[80][1], "and so must the cost"
    return "\n".join(f"{n} nodes, M = 12, ef {ef:>3}: recall@10 {r:.3f} for {c:.0f} similarities per query ({n / c:.1f}x fewer than brute force)" for ef, (r, c) in out.items())


# =============================================================================
# Milestone 6: the recall curve
# =============================================================================
class _FakeIndex:
    def __init__(self):
        self.dist_calls = 100
        self.asked = []

    def search(self, q, k, ef):
        self.asked.append((q, k, ef))
        self.dist_calls += ef                          # ef similarities per query
        return list(range(min(ef, k)))                 # finds ids 0 .. min(ef, k) - 1


def m6():
    fake = _FakeIndex()
    truth = [list(range(10)), list(range(10))]
    rows = mod.recall_curve(fake, ["a", "b"], truth, k=10, efs=(2, 5, 20))
    assert [r["ef"] for r in rows] == [2, 5, 20], "one row per ef, in the order given"
    assert [round(r["recall"], 6) for r in rows] == [0.2, 0.5, 1.0], f"the fake index finds the first min(ef, 10) of the true 10: recall 0.2, 0.5, 1.0; got {[r['recall'] for r in rows]}"
    assert [round(r["dist_calls"], 6) for r in rows] == [2.0, 5.0, 20.0], f"the fake index adds ef to dist_calls per query, so the mean per query is ef itself; got {[r['dist_calls'] for r in rows]}"
    assert fake.asked[0] == ("a", 10, 2) and len(fake.asked) == 6, f"every query is run once for every ef, with k passed on; got {fake.asked}"

    curve = [{"ef": 40, "recall": 0.94, "dist_calls": 500}, {"ef": 10, "recall": 0.66, "dist_calls": 200}, {"ef": 80, "recall": 0.99, "dist_calls": 900}]
    assert mod.ef_for_recall(curve, 0.9) == 40 and mod.ef_for_recall(curve, 0.5) == 10, "the smallest ef that reaches the target, whatever the order of the rows"
    assert mod.ef_for_recall(curve, 0.94) == 40, "reaching the target exactly counts (>=)"
    assert mod.ef_for_recall(curve, 0.995) is None and mod.ef_for_recall([], 0.5) is None, "no row reaches it: None"

    idx, vectors, queries, truth, built = big_index()
    efs = (10, 20, 40, 80, 160)
    curve = mod.recall_curve(idx, queries, truth, 10, efs)
    rec = [r["recall"] for r in curve]
    cost = [r["dist_calls"] for r in curve]
    assert all(a <= b + 0.005 for a, b in zip(rec, rec[1:])), f"recall should rise with ef; got {[round(r, 3) for r in rec]}"
    assert cost == sorted(cost) and cost[-1] < len(vectors), f"cost rises with ef and stays under brute force ({len(vectors)}); got {[round(c) for c in cost]}"
    assert rec[0] < 0.8 and rec[-1] >= 0.995, f"the curve should run from under 0.8 at ef = 10 to about 1.0 at ef = 160; got {[round(r, 3) for r in rec]}"
    ef95 = mod.ef_for_recall(curve, 0.95)
    assert ef95 in (40, 80), f"recall 0.95 should need ef 40 or 80 on this data; got {ef95}"
    c95 = next(r["dist_calls"] for r in curve if r["ef"] == ef95)
    lines = [f"{r['ef']:>5}  {r['recall']:>7.3f}  {r['dist_calls']:>9.0f}  {len(vectors) / r['dist_calls']:>6.1f}x" for r in curve]
    return ("   ef   recall  sims/query  vs brute force (3,000)\n" + "\n".join(lines)
            + f"\nrecall 0.95 first reached at ef {ef95}: {c95:.0f} similarities per query, {len(vectors) / c95:.1f}x fewer than brute force"
            + f"\nbuild: {len(vectors)} nodes in {built:.1f} s")


MILESTONES = [
    (1, "Milestone 1: the exact baseline and recall", m1),
    (2, "Milestone 2: beam search inside one layer", m2),
    (3, "Milestone 3: random levels and neighbour selection", m3),
    (4, "Milestone 4: inserting a node", m4),
    (5, "Milestone 5: searching the whole structure", m5),
    (6, "Milestone 6: recall against search effort", m6),
]

if __name__ == "__main__":
    t0 = time.time()
    print(f"Lab 4 checks against {target}.py\n")
    for n, name, fn in MILESTONES:
        check(n, name, fn)
    print(f"\n{sum(results)}/{len(results)} milestones passing  ({time.time() - t0:.1f} s)")
    sys.exit(0 if all(results) else 1)
