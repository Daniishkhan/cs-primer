"""embedder.py: a STAND-IN for a trained embedding model, GIVEN.

!! This is not a neural network and it knows nothing about meaning. !!
It turns text into a fixed-length vector from sub-word statistics, so the lab runs offline
and gives the same numbers every time. What it shares with a real bi-encoder (chapter 7):

  * texts become dense, fixed-length, length-1 vectors that you compare with cosine;
  * the document vector is computed once, offline, and cannot depend on the query;
  * similar-looking words land near each other ("cancel", "cancelling", "cancellation"),
    so spelling variants and inflections match even though they are different terms.

What it lacks: any grasp of synonyms ("refund" against "money back"), and, like the stand-in
of chapter 8, it forgets word order completely. A trained embedder does better on both.

Recipe: pad each word as ^word$, cut it into character trigrams, hash each trigram to one of
`dim` buckets with CRC32 (stable across runs and machines), weight each bucket by
(1 + log tf) * idf, and divide by the vector's length.
"""
import math
import re
import zlib

_WORD = re.compile(r"[a-z0-9]+")


def trigrams(text):
    """'Cancel it' -> ['^ca', 'can', 'anc', 'nce', 'cel', 'el$', '^it', 'it$'] (order within a word only)."""
    out = []
    for w in _WORD.findall(text.lower()):
        padded = f"^{w}$"
        out.extend(padded[i:i + 3] for i in range(len(padded) - 2))
    return out


class TrigramEmbedder:
    def __init__(self, docs, dim=512):
        self.dim = dim
        df = [0] * dim
        for text in docs.values():
            for b in set(self._bucket(g) for g in trigrams(text)):
                df[b] += 1
        n = len(docs)
        self.idf = [math.log((1 + n) / (1 + c)) + 1.0 for c in df]

    def _bucket(self, gram):
        return zlib.crc32(gram.encode("utf-8")) % self.dim

    def embed(self, text):
        """A list of `dim` floats with length 1 (all zeros for a text with no letters or digits)."""
        counts = {}
        for g in trigrams(text):
            b = self._bucket(g)
            counts[b] = counts.get(b, 0) + 1
        vec = [0.0] * self.dim
        for b, c in counts.items():
            vec[b] = (1 + math.log(c)) * self.idf[b]
        norm = math.sqrt(sum(x * x for x in vec))
        return [x / norm for x in vec] if norm else vec
