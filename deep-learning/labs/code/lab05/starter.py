"""Lab 5 starter: a byte-level BPE tokeniser and the decoders that sit after a language model.

Write the functions marked TODO, one milestone at a time, and run `python3 check.py` after each.

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
    """The UTF-8 bytes of `text` as a list of ints in 0..255.

    utf8_ids("hi")  -> [104, 105]
    utf8_ids("é")   -> [195, 169]          (one character, two bytes)
    utf8_ids("👍")  -> [240, 159, 145, 141] (one character, four bytes)
    """
    raise NotImplementedError("TODO milestone 1: utf8_ids")


def count_pairs(seqs, freqs):
    """Count adjacent pairs over distinct words, weighting each word by how often it occurs.

    seqs:  {word: [ids]}   the current token ids of each distinct word
    freqs: {word: count}   how many times each word occurs in the corpus
    returns a Counter {(a, b): count}

    count_pairs({" low": [32, 108, 111, 119]}, {" low": 5})
        -> Counter({(32, 108): 5, (108, 111): 5, (111, 119): 5})
    Pairs never span two words, and a pair is counted once per adjacent position.
    """
    raise NotImplementedError("TODO milestone 1: count_pairs")


def merge_pair(ids, pair, new_id):
    """Replace every non-overlapping occurrence of `pair` in `ids` by `new_id`, scanning left to right.

    merge_pair([1, 2, 3, 1, 2], (1, 2), 9)  -> [9, 3, 9]
    merge_pair([5, 5, 5], (5, 5), 9)        -> [9, 5]      (the scan consumes two, then one is left)
    The input list must not be modified; return a new list.
    """
    raise NotImplementedError("TODO milestone 1: merge_pair")


def best_pair(pairs):
    """The most frequent pair in a Counter; ties go to the smaller first id, then the smaller second id.

    best_pair(Counter({(1, 2): 4, (0, 9): 4, (0, 3): 4})) -> (0, 3)
    """
    raise NotImplementedError("TODO milestone 1: best_pair")


# =============================================================================
# Milestone 2: training
# =============================================================================
def train_bpe(text, n_merges):
    """Learn up to `n_merges` merges from `text`. Returns {(a, b): new_id} in the order learned.

    Steps (chapter 13): split the text into pieces with pretokenise, count each distinct piece once,
    turn each into its UTF-8 byte ids, then repeat n_merges times: count_pairs, take best_pair, give
    it the next id (256, 257, ...), and merge_pair it in every piece. Stop early if no pair is left.
    The dict's insertion order is the order of learning, which encode relies on.
    """
    raise NotImplementedError("TODO milestone 2: train_bpe")


# =============================================================================
# Milestone 3: encode and decode
# =============================================================================
def vocab_bytes(merges):
    """{token id: the bytes it stands for}, for the 256 byte tokens and every merged token.

    A merged token is the concatenation of the bytes of its two parts: if 256 = (101, 115) then
    vocab_bytes(merges)[256] == b"es".
    """
    raise NotImplementedError("TODO milestone 3: vocab_bytes")


def encode(text, merges):
    """Text -> token ids.

    For each piece from pretokenise: start from its UTF-8 bytes, then repeatedly find the pair
    present with the *lowest* merge id (the earliest learned), merge it, and stop when no pair
    in the piece is in `merges`. Concatenate the pieces' ids.
    """
    raise NotImplementedError("TODO milestone 3: encode")


def decode(ids, merges):
    """Token ids -> text. Join the bytes of the tokens, then decode as UTF-8.

    Invalid UTF-8 (for instance the first two bytes of a four-byte emoji) must not raise: use
    errors="replace", which turns the broken part into the character U+FFFD.
    """
    raise NotImplementedError("TODO milestone 3: decode")


# =============================================================================
# Milestone 4: reshaping a distribution
# =============================================================================
def softmax(logits, temperature=1.0):
    """softmax(logits / temperature) as a list of probabilities that sums to 1.

    softmax([0.0, 0.0])            -> [0.5, 0.5]
    softmax([1.0, 0.0], 0.5)       -> sharper than temperature 1
    Subtract the maximum before exponentiating so that logits like [1000, 999] do not overflow.
    Raise ValueError if temperature <= 0.
    """
    raise NotImplementedError("TODO milestone 4: softmax")


def _renormalise(probs, keep):
    total = sum(p for p, k in zip(probs, keep) if k)
    return [p / total if k else 0.0 for p, k in zip(probs, keep)]


def _ranking(probs):
    """Token ids from most to least probable; ties go to the smaller id."""
    return sorted(range(len(probs)), key=lambda i: (-probs[i], i))


def top_k_filter(probs, k):
    """Keep the k most probable tokens, set the rest to 0.0, renormalise so the survivors sum to 1.

    top_k_filter([0.5, 0.25, 0.125, 0.125], 2) -> [2/3, 1/3, 0.0, 0.0]
    Ties are broken towards the smaller token id, so exactly k tokens survive. k >= len(probs)
    keeps everything; treat k < 1 as 1. Return a new list of the same length.
    """
    raise NotImplementedError("TODO milestone 4: top_k_filter")


def top_p_filter(probs, p):
    """Nucleus filter: keep the smallest set of top tokens whose total probability reaches p.

    top_p_filter([0.5, 0.25, 0.125, 0.125], 0.7) -> [2/3, 1/3, 0.0, 0.0]   (0.5 < 0.7, 0.75 >= 0.7)
    Walk the tokens from most to least probable (ties: smaller id first), keeping each one until the
    mass kept so far is already >= p. The token that crosses p is kept; the best token is always kept.
    Renormalise the survivors. p = 1.0 keeps every token with non-zero probability.
    """
    raise NotImplementedError("TODO milestone 4: top_p_filter")


def min_p_filter(probs, frac):
    """Keep tokens whose probability is at least `frac` times the best token's; renormalise.

    min_p_filter([0.6, 0.3, 0.07, 0.03], 0.1) -> keeps 0.6, 0.3 and 0.07 (cut-off 0.06), renormalised
    """
    raise NotImplementedError("TODO milestone 4: min_p_filter")


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
    """The most probable token (works on logits or probabilities); ties go to the smaller id."""
    raise NotImplementedError("TODO milestone 5: greedy")


def next_token(logits, rng, temperature=1.0, top_k=None, top_p=None, min_p=None):
    """One decoding step: logits -> softmax(temperature) -> top-k -> top-p -> min-p -> draw one token.

    Each filter is applied only if its argument is not None, in that order, and each one
    renormalises. temperature == 0 means greedy decoding on the logits and must not use `rng`.
    The draw is sample_from(probs, rng.random()): exactly one rng.random() call per step.
    """
    raise NotImplementedError("TODO milestone 5: next_token")


def generate(model, prompt_ids, n_new, rng, stop_id=None, **settings):
    """Extend `prompt_ids` by up to n_new tokens and return prompt + new tokens (a new list).

    model(ids) returns the logits (length V) for the next token. At each step call next_token with
    **settings. If stop_id is given, stop right after emitting it (the stop token is included).
    """
    raise NotImplementedError("TODO milestone 5: generate")


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
