"""Lab 4: HNSW from scratch.

A hierarchical navigable small-world graph (Malkov and Yashunin) over unit vectors, built and
searched in pure Python, with every similarity computation counted. Notation is chapter 11's:

    M                 links kept per node (layer 0 allows 2M)
    ef_construction   beam width while inserting
    ef                beam width while searching (efSearch)
    mL                1 / ln(M), the level-assignment constant
    similarity        the dot product of unit vectors (the cosine); LARGER means nearer

The graph lives in these attributes of `HNSW` (the checks read them, so keep the names):

    vectors[i]        node i's vector
    level[i]          the highest layer node i lives on (0 = only the bottom layer)
    links[layer][i]   node i's neighbour ids on that layer; `links` is a list with one dict per layer,
                      and a node appears in the dicts of layers 0..level[i] only
    entry             id of the entry point, a node on the top layer (None while empty)
    dist_calls        similarity computations counted so far (the cost measure)

What is GIVEN: `dot`, `sims` (the counted similarity), `shrink`, `build`, `top_layer`,
`layer_sizes`, `degrees` and the printing at the bottom. What YOU write is marked TODO:

    1  exact_topk, recall_at_k
    2  HNSW.search_layer
    3  random_level, HNSW.select_simple, HNSW.select_heuristic
    4  HNSW.add
    5  HNSW.search
    6  recall_curve, ef_for_recall

`python3 check.py` runs the milestones; the lab page explains each one.
"""
import heapq          # noqa: F401  (milestones 1 and 2: nsmallest, and the two heaps of the beam search)
import math
import operator
import random

from data import make_dataset


def dot(a, b):
    """GIVEN."""
    return sum(map(operator.mul, a, b))


# =============================================================================
# Milestone 1: the exact baseline and the metric
# =============================================================================
def exact_topk(vectors, q, k):
    """Ids of the k vectors with the largest dot product with `q`, best first; ties go to the smaller id.

    This is brute force: len(vectors) similarity computations. Everything else in the lab is
    judged against it.
        exact_topk([[1, 0], [0, 1], [0.6, 0.8]], [0.0, 1.0], 2) -> [1, 2]
    """
    raise NotImplementedError("TODO milestone 1: exact_topk")


def recall_at_k(found, truth):
    """ANN recall: the mean over queries of |found ∩ truth| / |truth|.

    `found` and `truth` are lists with one id list per query. Order inside a list does not
    matter. Return 0.0 for no queries. (Chapter 11: this compares the index with exact search over
    the same vectors; it is not relevance recall.)
        recall_at_k([[1, 2], [5, 6]], [[1, 2], [5, 9]]) -> 0.75
    """
    raise NotImplementedError("TODO milestone 1: recall_at_k")


# =============================================================================
# Milestone 3 (first part): the random layer of a new node
# =============================================================================
def random_level(rng, mL):
    """A node's top layer: floor(-ln(U) * mL) with U uniform in (0, 1].

    Draw U as `1.0 - rng.random()` so that U is never 0. With mL = 1 / ln(M), the chance of
    reaching layer l or higher is M**-l: layer 0 holds everything, layer 1 about 1/M of it, and so on.
    """
    raise NotImplementedError("TODO milestone 3: random_level")


class HNSW:
    def __init__(self, M=12, ef_construction=64, seed=1):
        self.M, self.ef_construction = M, ef_construction
        self.mL = 1.0 / math.log(M)
        self.rng = random.Random(seed)
        self.vectors = []        # vectors[i] is node i's vector
        self.level = []          # level[i] is the highest layer node i lives on
        self.links = []          # links[layer][node] -> list of neighbour ids (one dict per layer)
        self.entry = None        # id of the entry point: a node on the top layer
        self.dist_calls = 0      # similarity computations made by search_layer

    @property
    def top_layer(self):
        """GIVEN: the highest layer of the entry point (-1 for an empty index)."""
        return self.level[self.entry] if self.entry is not None else -1

    def sims(self, q, ids):
        """GIVEN: the similarity of `q` to each node in `ids`. Every call is counted in dist_calls."""
        self.dist_calls += len(ids)
        return [dot(self.vectors[i], q) for i in ids]

    # =========================================================================
    # Milestone 2: best-first search inside one layer (Algorithm 2 of the paper)
    # =========================================================================
    def search_layer(self, q, entry_points, ef, layer):
        """The `ef` nodes of `layer` most similar to `q` found by a beam search from `entry_points`.

        Returns [(similarity, node_id), ...], best first, ties by smaller id; at most `ef` entries.

        Keep a visited set, a max-heap of candidates still to expand and a min-heap of the best `ef`
        results so far. Pop the most promising candidate; if the results are full and it is worse than
        the worst result, stop; otherwise look at its unvisited neighbours on this layer (self.links[layer]),
        score them with self.sims (each node is scored at most once per call), and keep those that
        improve the results. ef = 1 is the greedy walk used on the upper layers.
        """
        raise NotImplementedError("TODO milestone 2: HNSW.search_layer")

    # =========================================================================
    # Milestone 3: choosing which neighbours to keep
    # =========================================================================
    def select_simple(self, candidates, m):
        """The m most similar candidates. `candidates` is [(similarity to the base node, id)], best first.

        Returns a list of the same (similarity, id) pairs."""
        raise NotImplementedError("TODO milestone 3: HNSW.select_simple")

    def select_heuristic(self, candidates, m):
        """Algorithm 4 of the paper: spread the links out.

        Walk the candidates best first. Keep a candidate c (similarity s to the base node) only if s is
        strictly larger than dot(vectors[c], vectors[r]) for EVERY neighbour r already kept: c must be
        closer to the base node than to anything already chosen. Stop when m are kept. Same input and
        output shape as select_simple. Candidates that fail the test are dropped, even if that leaves
        fewer than m.
        """
        raise NotImplementedError("TODO milestone 3: HNSW.select_heuristic")

    def shrink(self, layer, node):
        """GIVEN: cut an over-full neighbour list back to its cap (2M on layer 0, M above) with the heuristic."""
        cap = 2 * self.M if layer == 0 else self.M
        ids = self.links[layer][node]
        scored = sorted(((dot(self.vectors[node], self.vectors[n]), n) for n in ids), key=lambda t: (-t[0], t[1]))
        self.links[layer][node] = [n for _, n in self.select_heuristic(scored, cap)]

    # =========================================================================
    # Milestone 4: insertion (Algorithm 1)
    # =========================================================================
    def add(self, vec):
        """Insert one vector and return its id (0, 1, 2, ... in order of insertion).

        1. Append the vector, draw its level L with random_level(self.rng, self.mL), append to self.level,
           grow self.links until it has a dict for layer L, and give the node an empty list on layers 0..L.
        2. The first node becomes the entry point; return.
        3. Otherwise start at the entry point. For layers above L (from top_layer down to L + 1), descend
           greedily: ep = [best node of search_layer(vec, ep, 1, layer)].
        4. For each layer from min(L, top_layer) down to 0: found = search_layer(vec, ep, ef_construction,
           layer); chosen = select_heuristic(found, M); set the new node's links to the chosen ids; add the
           new node to each chosen node's list, calling self.shrink(layer, c) when a list passes its cap
           (2M on layer 0, M above); then ep = all ids in `found` (the beam seeds the next layer down).
        5. If L is above the old top layer, the new node becomes the entry point.
        """
        raise NotImplementedError("TODO milestone 4: HNSW.add")

    def build(self, vectors):
        """GIVEN: insert every vector in order."""
        for v in vectors:
            self.add(v)
        return self

    # =========================================================================
    # Milestone 5: query
    # =========================================================================
    def search(self, q, k=10, ef=50):
        """The ids of the k nodes most similar to `q`, best first.

        Greedy descent (ef = 1) from the entry point through layers top_layer .. 1, then a beam search
        of width max(ef, k) on layer 0, then the first k ids. An empty index or k <= 0 returns [].
        """
        raise NotImplementedError("TODO milestone 5: HNSW.search")

    # GIVEN: views used by the checks and the page
    def layer_sizes(self):
        return [len(layer) for layer in self.links]

    def degrees(self, layer):
        return [len(v) for v in self.links[layer].values()]


# =============================================================================
# Milestone 6: recall against search effort
# =============================================================================
def recall_curve(index, queries, truth, k=10, efs=(10, 20, 40, 80, 160)):
    """For each ef: the mean recall@k and the mean number of similarity computations per query.

    `truth` holds each query's exact top-k ids. Measure the cost as the growth of index.dist_calls
    while the queries for that ef run, divided by the number of queries.
    Returns [{"ef": ef, "recall": float, "dist_calls": float}, ...] in the order of `efs`.
    """
    raise NotImplementedError("TODO milestone 6: recall_curve")


def ef_for_recall(curve, target):
    """The smallest ef in `curve` whose recall is at least `target`; None if no row reaches it.

    `curve` is a list of the dicts that recall_curve returns, in any order.
    """
    raise NotImplementedError("TODO milestone 6: ef_for_recall")


if __name__ == "__main__":
    import time
    vectors, queries = make_dataset()
    truth = [exact_topk(vectors, q, 10) for q in queries]
    t0 = time.time()
    idx = HNSW(M=12, ef_construction=64).build(vectors)
    print(f"built {len(vectors)} nodes in {time.time() - t0:.1f} s; layers {idx.layer_sizes()}")
    print(f"brute force: {len(vectors)} similarity computations per query\n")
    print("   ef  recall@10  similarities/query  vs brute force")
    for r in recall_curve(idx, queries, truth):
        print(f"{r['ef']:>5}  {r['recall']:>9.3f}  {r['dist_calls']:>18,.0f}  {len(vectors) / r['dist_calls']:>9.1f}x fewer")
