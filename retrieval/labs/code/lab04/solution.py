"""Lab 4: HNSW from scratch (reference solution).

A hierarchical navigable small-world graph (Malkov and Yashunin) over unit vectors, built and
searched in pure Python, with every similarity computation counted.

    1  exact_topk, recall_at_k
    2  HNSW.search_layer
    3  random_level, HNSW.select_simple, HNSW.select_heuristic
    4  HNSW.add
    5  HNSW.search
    6  recall_curve, ef_for_recall
"""
import heapq
import math
import operator
import random

from data import make_dataset  # noqa: F401


def dot(a, b):
    return sum(map(operator.mul, a, b))


# =============================================================================
# Milestone 1: the exact baseline and the metric
# =============================================================================
def exact_topk(vectors, q, k):
    """Ids of the k vectors with the largest dot product with `q`, best first, ties by smaller id."""
    scored = [(-dot(v, q), i) for i, v in enumerate(vectors)]
    return [i for _, i in heapq.nsmallest(k, scored)]


def recall_at_k(found, truth):
    """Mean over queries of |found ∩ truth| / |truth|. `found` and `truth` are lists of id lists."""
    if not truth:
        return 0.0
    return sum(len(set(f) & set(t)) / len(t) for f, t in zip(found, truth)) / len(truth)


# =============================================================================
# Milestone 3 (first part): the random layer of a new node
# =============================================================================
def random_level(rng, mL):
    """floor(-ln(U) * mL) with U uniform in (0, 1]: P(level >= l) = M**-l when mL = 1 / ln(M)."""
    return int(-math.log(1.0 - rng.random()) * mL)


class HNSW:
    def __init__(self, M=12, ef_construction=64, seed=1):
        self.M, self.ef_construction = M, ef_construction
        self.mL = 1.0 / math.log(M)
        self.rng = random.Random(seed)
        self.vectors = []        # vectors[i] is node i's vector
        self.level = []          # level[i] is the highest layer node i lives on
        self.links = []          # links[layer][node] -> list of neighbour ids (dict per layer)
        self.entry = None        # id of the entry point: a node on the top layer
        self.dist_calls = 0      # similarity computations made by search_layer

    @property
    def top_layer(self):
        return self.level[self.entry] if self.entry is not None else -1

    def sims(self, q, ids):
        """GIVEN: similarity of `q` to each node in `ids`. Every call is counted in dist_calls."""
        self.dist_calls += len(ids)
        return [dot(self.vectors[i], q) for i in ids]

    # =========================================================================
    # Milestone 2: best-first search inside one layer (Algorithm 2 of the paper)
    # =========================================================================
    def search_layer(self, q, entry_points, ef, layer):
        """The `ef` nodes of `layer` most similar to `q` found by a beam search from `entry_points`.

        Returns [(similarity, node_id), ...], best first (ties by smaller id)."""
        visited = set(entry_points)
        s0 = self.sims(q, list(entry_points))
        cand = [(-s, e) for s, e in zip(s0, entry_points)]        # max-heap on similarity
        heapq.heapify(cand)
        best = [(s, e) for s, e in zip(s0, entry_points)]         # min-heap: the ef best so far
        heapq.heapify(best)
        while len(best) > ef:
            heapq.heappop(best)
        while cand:
            neg, node = heapq.heappop(cand)
            if len(best) >= ef and -neg < best[0][0]:             # the best open candidate is worse than
                break                                             # the worst kept result: nothing left to gain
            fresh = [n for n in self.links[layer][node] if n not in visited]
            if not fresh:
                continue
            visited.update(fresh)
            for s, n in zip(self.sims(q, fresh), fresh):
                if len(best) < ef or s > best[0][0]:
                    heapq.heappush(cand, (-s, n))
                    heapq.heappush(best, (s, n))
                    if len(best) > ef:
                        heapq.heappop(best)
        return sorted(best, key=lambda t: (-t[0], t[1]))

    # =========================================================================
    # Milestone 3: choosing which neighbours to keep
    # =========================================================================
    def select_simple(self, candidates, m):
        """The m most similar candidates. `candidates` is [(similarity to the base node, id)], best first."""
        return list(candidates[:m])

    def select_heuristic(self, candidates, m):
        """Algorithm 4: walk the candidates best first; keep one only if it is MORE similar to the base
        node than to every neighbour already kept; stop at m. Same input and output shape as select_simple."""
        kept = []
        for s, c in candidates:
            if all(s > dot(self.vectors[c], self.vectors[r]) for _, r in kept):
                kept.append((s, c))
                if len(kept) == m:
                    break
        return kept

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
        """Insert one vector; return its id (0, 1, 2, ... in order of insertion)."""
        i = len(self.vectors)
        self.vectors.append(vec)
        L = random_level(self.rng, self.mL)
        self.level.append(L)
        while len(self.links) <= L:
            self.links.append({})
        for layer in range(L + 1):
            self.links[layer][i] = []
        if self.entry is None:
            self.entry = i
            return i
        top = self.level[self.entry]
        ep = [self.entry]
        for layer in range(top, L, -1):                            # above the new node's layers: just descend
            ep = [self.search_layer(vec, ep, 1, layer)[0][1]]
        for layer in range(min(L, top), -1, -1):                   # from there down: find, link, prune
            found = self.search_layer(vec, ep, self.ef_construction, layer)
            chosen = self.select_heuristic(found, self.M)
            self.links[layer][i] = [c for _, c in chosen]
            for _, c in chosen:
                self.links[layer][c].append(i)
                if len(self.links[layer][c]) > (2 * self.M if layer == 0 else self.M):
                    self.shrink(layer, c)
            ep = [n for _, n in found]                             # the whole beam seeds the next layer down
        if L > top:
            self.entry = i
        return i

    def build(self, vectors):
        """GIVEN: insert every vector in order."""
        for v in vectors:
            self.add(v)
        return self

    # =========================================================================
    # Milestone 5: query
    # =========================================================================
    def search(self, q, k=10, ef=50):
        """The ids of the k nodes most similar to `q`, best first. `ef` is the beam width on layer 0."""
        if self.entry is None or k <= 0:
            return []
        ep = [self.entry]
        for layer in range(self.top_layer, 0, -1):
            ep = [self.search_layer(q, ep, 1, layer)[0][1]]
        found = self.search_layer(q, ep, max(ef, k), 0)
        return [n for _, n in found[:k]]

    # GIVEN: a few views used by the checks and the page
    def layer_sizes(self):
        return [len(layer) for layer in self.links]

    def degrees(self, layer):
        return [len(v) for v in self.links[layer].values()]


# =============================================================================
# Milestone 6: recall against search effort
# =============================================================================
def recall_curve(index, queries, truth, k=10, efs=(10, 20, 40, 80, 160)):
    """For each ef: the mean recall@k and the mean number of similarity computations per query.

    Returns [{"ef": ef, "recall": float, "dist_calls": float}, ...] in the order of `efs`."""
    rows = []
    for ef in efs:
        before = index.dist_calls
        found = [index.search(q, k, ef) for q in queries]
        rows.append({"ef": ef, "recall": recall_at_k(found, truth), "dist_calls": (index.dist_calls - before) / len(queries)})
    return rows


def ef_for_recall(curve, target):
    """The smallest ef in `curve` whose recall is at least `target`; None if no row reaches it."""
    for row in sorted(curve, key=lambda r: r["ef"]):
        if row["recall"] >= target:
            return row["ef"]
    return None


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
