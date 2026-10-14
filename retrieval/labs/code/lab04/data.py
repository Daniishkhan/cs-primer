"""data.py: synthetic 'embeddings' for Lab 4, GIVEN.

Clustered unit vectors in `dim` dimensions: a stand-in for real text embeddings (chapter 7), which
also lie in clumps (topics) rather than uniformly. Everything comes from a seeded
random.Random, so the data are identical on every machine.

    vectors, queries = make_dataset()            # 3,000 vectors and 100 queries, 32 dimensions

Every vector has length 1, so the dot product IS the cosine similarity, and "nearest" means
"largest dot product" (the convention of chapter 11).
"""
import math
import random


def _unit(v):
    n = math.sqrt(sum(x * x for x in v))
    return [x / n for x in v]


def make_dataset(n=3000, dim=32, clusters=40, noise=2.0, n_queries=100, seed=7):
    rng = random.Random(seed)
    centres = [_unit([rng.gauss(0, 1) for _ in range(dim)]) for _ in range(clusters)]

    def sample(m):
        out = []
        for _ in range(m):
            c = centres[rng.randrange(clusters)]
            out.append(_unit([x + noise / math.sqrt(dim) * rng.gauss(0, 1) for x in c]))
        return out

    return sample(n), sample(n_queries)
