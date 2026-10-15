# Drill: A2 Lab 5, milestone 5 of 5: drawing a token and generating text (step 1 of 4)
# Everything else in this file is already written. Fill in:
#     sample_from
# Check it with: python3 check.py 5

"""Lab 5 reference solution: a byte-level BPE tokeniser and the decoders that sit after a language model.

Notation follows chapters 13 and 15: a *merge table* maps a pair of token ids to the id of the new
token, in the order the merges were learned; ids 0..255 are the raw bytes of UTF-8; V is the
vocabulary size; probabilities are lists that sum to 1.
"""
import math
import os
import re
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))

# Pre-tokenisation (chapter 13): cut the text into words *before* merging, so a merge never crosses a
# word boundary. A word keeps its leading space; digits, punctuation and white space form their own pieces.
SPLIT = re.compile(r" ?[^\W\d_]+| ?\d+| ?[^\s\w]+|\s+(?!\S)|\s+")


def pretokenise(text):
    """Split text into the pieces BPE works on. Concatenating the pieces gives the text back."""
    return SPLIT.findall(text)


def load_corpus():
    with open(os.path.join(HERE, "corpus.txt"), encoding="utf-8") as f:
        return f.read()


# =============================================================================
# Milestone 1: bytes, pair counts and one merge
# =============================================================================
def utf8_ids(text):
    """The UTF-8 bytes of `text` as a list of ints in 0..255."""
    return list(text.encode("utf-8"))


def count_pairs(seqs, freqs):
    """Count adjacent pairs over distinct words, weighting each word by how often it occurs.

    seqs:  {word: [ids]}      freqs: {word: count}      returns Counter {(a, b): count}
    """
    pairs = Counter()
    for word, ids in seqs.items():
        for a, b in zip(ids, ids[1:]):
            pairs[(a, b)] += freqs[word]
    return pairs


def merge_pair(ids, pair, new_id):
    """Replace every non-overlapping occurrence of `pair` in `ids` by `new_id`, scanning left to right."""
    out, i = [], 0
    while i < len(ids):
        if i < len(ids) - 1 and (ids[i], ids[i + 1]) == pair:
            out.append(new_id)
            i += 2
        else:
            out.append(ids[i])
            i += 1
    return out


def best_pair(pairs):
    """The most frequent pair; ties go to the smaller first id, then the smaller second id."""
    return max(pairs, key=lambda pr: (pairs[pr], -pr[0], -pr[1]))


# =============================================================================
# Milestone 2: training
# =============================================================================
def train_bpe(text, n_merges):
    """Learn up to `n_merges` merges. Returns {(a, b): new_id} in the order learned (ids start at 256)."""
    freqs = Counter(pretokenise(text))
    seqs = {w: utf8_ids(w) for w in freqs}
    merges = {}
    for k in range(n_merges):
        pairs = count_pairs(seqs, freqs)
        if not pairs:                       # every word is a single token: nothing left to merge
            break
        pair = best_pair(pairs)
        merges[pair] = 256 + k
        for w in seqs:
            seqs[w] = merge_pair(seqs[w], pair, 256 + k)
    return merges


# =============================================================================
# Milestone 3: encode and decode
# =============================================================================
def vocab_bytes(merges):
    """{token id: the bytes it stands for}, for all 256 byte tokens and every merged token."""
    vb = {i: bytes([i]) for i in range(256)}
    for (a, b), new in merges.items():      # insertion order = order learned, so parts exist already
        vb[new] = vb[a] + vb[b]
    return vb


def encode(text, merges):
    """Text -> token ids: bytes of each piece, then the earliest-learned merge present, until none is."""
    out = []
    for piece in pretokenise(text):
        ids = utf8_ids(piece)
        while len(ids) > 1:
            pairs = set(zip(ids, ids[1:]))
            pair = min(pairs, key=lambda pr: merges.get(pr, math.inf))
            if pair not in merges:
                break
            ids = merge_pair(ids, pair, merges[pair])
        out.extend(ids)
    return out


def decode(ids, merges):
    """Token ids -> text. Invalid UTF-8 (for instance a cut-off emoji) becomes U+FFFD instead of an error."""
    vb = vocab_bytes(merges)
    return b"".join(vb[i] for i in ids).decode("utf-8", errors="replace")


# =============================================================================
# Milestone 4: reshaping a distribution
# =============================================================================
def softmax(logits, temperature=1.0):
    """softmax(logits / temperature), numerically safe. Temperature must be positive."""
    if temperature <= 0:
        raise ValueError("temperature must be positive (use greedy for 0)")
    z = [x / temperature for x in logits]
    m = max(z)
    e = [math.exp(x - m) for x in z]
    s = sum(e)
    return [x / s for x in e]


def _renormalise(probs, keep):
    total = sum(p for p, k in zip(probs, keep) if k)
    return [p / total if k else 0.0 for p, k in zip(probs, keep)]


def _ranking(probs):
    """Token ids from most to least probable; ties go to the smaller id."""
    return sorted(range(len(probs)), key=lambda i: (-probs[i], i))


def top_k_filter(probs, k):
    """Keep the k most probable tokens, zero the rest, renormalise. k >= len(probs) keeps everything."""
    keep = [False] * len(probs)
    for i in _ranking(probs)[:max(k, 1)]:       # k < 1 is treated as 1
        keep[i] = True
    return _renormalise(probs, keep)


def top_p_filter(probs, p):
    """Nucleus: the smallest set of top tokens whose mass reaches p (the token that crosses p is kept)."""
    keep = [False] * len(probs)
    before = 0.0                            # mass of everything ranked above the current token
    for rank, i in enumerate(_ranking(probs)):
        if rank > 0 and before >= p:        # the best token is always kept, even for tiny p
            break
        keep[i] = True
        before += probs[i]
    return _renormalise(probs, keep)


def min_p_filter(probs, frac):
    """Keep tokens at least `frac` times as probable as the best one."""
    cut = frac * max(probs)
    return _renormalise(probs, [x >= cut for x in probs])


# =============================================================================
# Milestone 5: drawing a token and generating text
# =============================================================================
def sample_from(probs, u):
    """Inverse-CDF draw: return the first token whose running total of probability exceeds u.

    u is a number in [0, 1), from random.Random.random(). Tokens with probability 0 must never be
    returned (so skip them), even when u lands in the floating-point gap just under 1.
    sample_from([0.2, 0.5, 0.3], 0.19) -> 0;  (…, 0.2) -> 1;  (…, 0.69) -> 1;  (…, 0.7) -> 2
    """
    raise NotImplementedError("TODO milestone 5: sample_from")


def greedy(probs):
    """The most probable token; ties go to the smaller id."""
    return _ranking(probs)[0]


def next_token(logits, rng, temperature=1.0, top_k=None, top_p=None, min_p=None):
    """One decoding step: logits -> (temperature) -> top-k -> top-p -> min-p -> draw.

    temperature == 0 means greedy and uses no randomness.
    """
    if temperature == 0:
        return greedy(logits)
    probs = softmax(logits, temperature)
    if top_k is not None:
        probs = top_k_filter(probs, top_k)
    if top_p is not None:
        probs = top_p_filter(probs, top_p)
    if min_p is not None:
        probs = min_p_filter(probs, min_p)
    return sample_from(probs, rng.random())


def generate(model, prompt_ids, n_new, rng, stop_id=None, **settings):
    """Extend `prompt_ids` by up to n_new tokens. `model(ids)` returns the logits for the next token.

    Generation ends early after emitting `stop_id`. Returns the prompt plus the new tokens.
    """
    ids = list(prompt_ids)
    for _ in range(n_new):
        t = next_token(model(ids), rng, **settings)
        ids.append(t)
        if stop_id is not None and t == stop_id:
            break
    return ids


# =============================================================================
# A tiny language model to decode from (given: not part of the milestones)
# =============================================================================
class NGramModel:
    """Counts of which token follows the last two (backing off to the last one, then to nothing).

    model(ids) returns *logits* (log-probabilities) for the next token, like a Transformer's last
    row of output. `alpha` is a small add-alpha smoothing: every token keeps a sliver of probability,
    which is exactly the junk tail that top-k and top-p exist to cut off.
    """

    def __init__(self, ids, vocab_size, alpha=0.0001):
        self.V, self.alpha = vocab_size, alpha
        self.uni = Counter(ids)
        self.bi, self.tri = {}, {}
        for a, b in zip(ids, ids[1:]):
            self.bi.setdefault(a, Counter())[b] += 1
        for a, b, c in zip(ids, ids[1:], ids[2:]):
            self.tri.setdefault((a, b), Counter())[c] += 1

    def __call__(self, ids):
        table = None
        if len(ids) >= 2 and (ids[-2], ids[-1]) in self.tri:
            table = self.tri[(ids[-2], ids[-1])]
        elif ids and ids[-1] in self.bi:
            table = self.bi[ids[-1]]
        else:
            table = self.uni
        total = sum(table.values()) + self.alpha * self.V
        return [math.log((table.get(t, 0) + self.alpha) / total) for t in range(self.V)]
