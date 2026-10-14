"""Lab 1: A pretraining data pipeline, from raw HTML to a deduplicated corpus.

Chapter 1 followed trillions of tokens through seven stages. This lab builds a miniature of
five of them and measures each one against labels:

    HTML --extract--> text --C4 + Gopher rules--> good text --line dedupe--> --exact hash-->
         --MinHash + LSH near-duplicate removal--> corpus

Everything is standard-library Python, deterministic and tiny: `corpus.pages()` is a
synthetic crawl of 114 pages (articles, copies, spam, stubs, non-English) with labels.

What is GIVEN: the tag sets, the thresholds, the hash family, the Report container and the
synthetic crawl. What YOU write is marked TODO:

    1  extract
    2  c4_line_filter, quality_flags, keep
    3  normalise, exact_dedupe, line_dedupe
    4  shingles, jaccard, minhash_signature, estimate_jaccard
    5  band_keys, candidate_pairs, candidate_probability, threshold, best_bands
    6  precision_recall, clusters, near_dedupe, run_pipeline

`python3 check.py` runs the milestones; the lab page explains each one.
"""
import hashlib
import math
import random
import re
import struct
from collections import Counter
from dataclasses import dataclass, field
from html.parser import HTMLParser

import corpus

# =============================================================================
# GIVEN: constants
# =============================================================================
SKIP_TAGS = {"head", "script", "style", "nav", "footer", "header", "aside", "noscript"}   # drop everything inside
BLOCK_TAGS = {"p", "div", "li", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6", "br", "tr", "table",
              "section", "article", "main", "blockquote"}                                  # start a new line

# Gopher-style thresholds (Rae et al., 2021), as in chapter 1
MIN_WORDS, MAX_WORDS = 50, 100_000
MIN_MEAN_WORD, MAX_MEAN_WORD = 3.0, 10.0
MAX_SYMBOL_RATIO = 0.10          # '#' and '...' per word
MAX_BULLET_LINES = 0.90
MAX_ELLIPSIS_LINES = 0.30
MIN_ALPHA_WORDS = 0.80
MAX_DUPLICATE_LINES = 0.30
STOPWORDS = {"the", "be", "to", "of", "and", "that", "have", "with"}
MIN_STOPWORDS = 2                # distinct stop words a real English document contains
BULLETS = ("-", "*", "•")

# C4-style line rules (Raffel et al., 2020)
TERMINAL = (".", "!", "?", '"')
BAD_LINE_SUBSTRINGS = ("javascript", "cookie", "terms of use", "privacy policy")
MIN_LINE_WORDS = 3

# MinHash and LSH settings (FineWeb used 112 hashes as 14 bands of 8 rows)
SHINGLE_WORDS = 5
NUM_PERM = 112
BANDS, ROWS = 14, 8
PRIME = (1 << 61) - 1
_rng = random.Random(42)
HASH_COEFS = [(_rng.randrange(1, PRIME), _rng.randrange(PRIME)) for _ in range(NUM_PERM)]   # h_i(x) = (a x + b) mod PRIME
EMPTY = PRIME                    # signature value for an empty shingle set


def base_hash(s):
    """A 64-bit hash of a string (the same on every machine, unlike Python's built-in hash)."""
    return struct.unpack("<Q", hashlib.blake2b(s.encode(), digest_size=8).digest())[0]


@dataclass
class Report:
    """What `run_pipeline` returns. Counts are documents; `dropped` maps id -> (stage, detail)."""
    n_pages: int = 0
    after_quality: int = 0
    after_lines: int = 0
    after_exact: int = 0
    after_near: int = 0
    kept: list = field(default_factory=list)
    dropped: dict = field(default_factory=dict)
    candidates: int = 0           # pairs LSH proposed
    precision: float = 0.0        # of the pairs it reported, how many are true duplicates
    recall: float = 0.0           # of the true duplicate pairs, how many it reported


# =============================================================================
# Milestone 1: HTML to text
# =============================================================================


def extract(html):
    """Return the main text of an HTML page, one paragraph per line.

    Text inside SKIP_TAGS (and everything nested in them) is dropped. A BLOCK_TAGS tag
    starts a new line; inline tags (a, b, span) do not break the text. A newline inside the
    HTML source is just whitespace, not a line break. Whitespace inside a line is collapsed
    to single spaces, lines are stripped, empty lines are removed, and the lines are joined
    with "\\n". Hint: subclass html.parser.HTMLParser and keep a depth counter for SKIP_TAGS.
    """
    raise NotImplementedError("TODO milestone 1: extract")


# =============================================================================
# Milestone 2: quality filters
# =============================================================================
def c4_line_filter(text, require_punct=True):
    """Keep only lines that pass the C4 line rules (Raffel et al., 2020), joined with "\\n".

    A line is kept if it has at least MIN_LINE_WORDS words, contains none of
    BAD_LINE_SUBSTRINGS (compare in lower case), and, when `require_punct` is true, ends
    with one of TERMINAL. Chapter 1: FineWeb found the punctuation rule removed about 30%
    of all tokens, so the pipeline below switches it off.
    """
    raise NotImplementedError("TODO milestone 2: c4_line_filter")


def quality_flags(text):
    """Names of the Gopher-style rules the text breaks (empty list = passes), in this order:

        length, mean_word_length, symbols, bullets, ellipsis, alpha, stopwords,
        repeated_lines, boilerplate
    """
    raise NotImplementedError("TODO milestone 2: quality_flags")


def keep(text):
    """True if the text breaks none of the quality rules."""
    raise NotImplementedError("TODO milestone 2: keep")


# =============================================================================
# Milestone 3: exact and line-level deduplication
# =============================================================================
def normalise(text):
    """Lower-case, replace every run of non-alphanumeric characters by one space, strip."""
    raise NotImplementedError("TODO milestone 3: normalise")


def exact_dedupe(docs):
    """Keep the first document of each distinct normalised text.

    docs: list of (id, text). Returns (kept, dropped): `kept` is the list of (id, text)
    in the original order; `dropped` maps each removed id to the id of the copy it
    duplicates. Compare documents by the SHA-256 of normalise(text), not by the text.
    """
    raise NotImplementedError("TODO milestone 3: exact_dedupe")


def line_dedupe(docs, max_docs=6):
    """Remove every line that occurs in MORE than `max_docs` different documents.

    docs: list of (id, text). Count each line once per document (a line repeated inside
    one document still counts once). Returns a new list of (id, text) in the same order;
    a document whose lines are all removed keeps its id with the empty text "".
    """
    raise NotImplementedError("TODO milestone 3: line_dedupe")


# =============================================================================
# Milestone 4: shingles and MinHash
# =============================================================================
def shingles(text, n=SHINGLE_WORDS):
    """The set of overlapping n-word windows of the lower-cased text (words split on whitespace).

    A text with fewer than n words but at least one word gives a single shingle (all its
    words); an empty text gives the empty set.
    """
    raise NotImplementedError("TODO milestone 4: shingles")


def jaccard(a, b):
    """|A & B| / |A | B|, and 0.0 if both sets are empty."""
    raise NotImplementedError("TODO milestone 4: jaccard")


def minhash_signature(shingle_set, num_perm=NUM_PERM):
    """The MinHash signature: for each of the first `num_perm` hash functions
    h_i(x) = (a_i * x + b_i) mod PRIME in HASH_COEFS, the minimum over the set of
    h_i(base_hash(shingle)). An empty set gives [EMPTY] * num_perm."""
    raise NotImplementedError("TODO milestone 4: minhash_signature")


def estimate_jaccard(sig_a, sig_b):
    """The fraction of positions where two signatures agree."""
    raise NotImplementedError("TODO milestone 4: estimate_jaccard")


# =============================================================================
# Milestone 5: locality-sensitive hashing
# =============================================================================
def band_keys(sig, b=BANDS, r=ROWS):
    """Split a signature into b bands of r rows. Return b hashable keys, one per band,
    each of the form (band_index, tuple_of_the_r_values). The band index is part of the
    key so a match in band 3 never collides with a match in band 4."""
    raise NotImplementedError("TODO milestone 5: band_keys")


def candidate_pairs(sigs, b=BANDS, r=ROWS):
    """All pairs of documents that share at least one band.

    sigs: dict id -> signature (length at least b * r). Returns a set of tuples
    (id1, id2) with id1 < id2. Use one hash table from band key to the list of ids that
    have it; never compare two documents unless they landed in the same bucket.
    """
    raise NotImplementedError("TODO milestone 5: candidate_pairs")


def candidate_probability(s, b=BANDS, r=ROWS):
    """P(two documents of Jaccard similarity s become a candidate pair) = 1 - (1 - s^r)^b."""
    raise NotImplementedError("TODO milestone 5: candidate_probability")


def threshold(b=BANDS, r=ROWS):
    """The similarity at which the S-curve is steepest, approximately (1/b)^(1/r)."""
    raise NotImplementedError("TODO milestone 5: threshold")


def best_bands(num_perm, target):
    """Among all (b, r) with b * r == num_perm, the one whose threshold(b, r) is closest to `target`.
    Returns (b, r). If two are equally close, prefer the one with more bands."""
    raise NotImplementedError("TODO milestone 5: best_bands")


# =============================================================================
# Milestone 6: evaluation and the whole pipeline
# =============================================================================
def precision_recall(predicted, gold):
    """(precision, recall) of a set of predicted pairs against the gold set.

    precision = |predicted & gold| / |predicted|, recall = |predicted & gold| / |gold|.
    An empty prediction has precision 1.0 (it claimed nothing wrong); an empty gold set
    has recall 1.0.
    """
    raise NotImplementedError("TODO milestone 6: precision_recall")


def clusters(ids, pairs):
    """Connected components of the graph whose nodes are `ids` and edges are `pairs`.

    Returns a list of sorted id lists, sorted by their first id. An id in no pair is a
    cluster of one. (Union-find, or a simple graph search.)
    """
    raise NotImplementedError("TODO milestone 6: clusters")


def near_dedupe(docs, b=BANDS, r=ROWS, min_jaccard=0.0):
    """Remove near-duplicates with MinHash and LSH.

    docs: dict id -> text. Steps: shingle every text, sign it, find candidate pairs with
    `candidate_pairs`, then keep only the candidates whose TRUE Jaccard similarity is at
    least `min_jaccard` (0.0 keeps them all). Group the surviving pairs into clusters and
    keep the smallest id of each cluster.

    Returns (kept_ids, removed, pairs): kept_ids a sorted list, removed a dict mapping each
    removed id to the cluster representative that was kept, pairs the set of pairs used.
    """
    raise NotImplementedError("TODO milestone 6: near_dedupe")


def run_pipeline(pages, b=BANDS, r=ROWS):
    """Run every stage on a list of corpus.Page and return a Report.

    Order: extract -> c4_line_filter(require_punct=False) -> quality_flags (drop pages with
    any flag; dropped[id] = ("quality", ",".join(flags))) -> line_dedupe -> exact_dedupe
    (dropped[id] = ("exact", kept_id)) -> near_dedupe (dropped[id] = ("near", kept_id)).
    `after_lines` is the number of documents still non-empty after line_dedupe (empty ones
    are dropped as ("lines", "empty")). `precision` and `recall` score near_dedupe's pairs
    against corpus.gold_pairs of the documents that entered it.
    """
    raise NotImplementedError("TODO milestone 6: run_pipeline")
