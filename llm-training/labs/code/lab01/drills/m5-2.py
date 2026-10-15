# Drill: A3 Lab 1, milestone 5 of 6: locality-sensitive hashing (step 2 of 5)
# Everything else in this file is already written. Fill in:
#     candidate_pairs
# Check it with: python3 check.py 5

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
class _Extractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)       # &amp; arrives as "&"
        self.skip = 0                                  # how many SKIP_TAGS we are currently inside
        self.out = []

    def handle_starttag(self, tag, attrs):
        if tag in SKIP_TAGS:
            self.skip += 1
        if tag in BLOCK_TAGS:
            self.out.append("\n")

    def handle_endtag(self, tag):
        if tag in SKIP_TAGS:
            self.skip = max(0, self.skip - 1)
        if tag in BLOCK_TAGS:
            self.out.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.out.append(re.sub(r"\s+", " ", data))      # a newline in the HTML source is only a space


def extract(html):
    """Return the main text of an HTML page, one paragraph per line.

    Text inside SKIP_TAGS (and everything nested in them) is dropped. A BLOCK_TAGS tag
    starts a new line; inline tags (a, b, span) do not break the text. A newline inside the
    HTML source is just whitespace, not a line break. Whitespace inside a line is collapsed
    to single spaces, lines are stripped, empty lines are removed, and the lines are joined
    with "\\n". Hint: subclass html.parser.HTMLParser and keep a depth counter for SKIP_TAGS.
    """
    parser = _Extractor()
    parser.feed(html)
    parser.close()
    lines = [re.sub(r"\s+", " ", ln).strip() for ln in "".join(parser.out).split("\n")]
    return "\n".join(ln for ln in lines if ln)


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
    kept = []
    for line in text.split("\n"):
        line = line.strip()
        if len(line.split()) < MIN_LINE_WORDS:
            continue
        if any(bad in line.lower() for bad in BAD_LINE_SUBSTRINGS):
            continue
        if require_punct and not line.endswith(TERMINAL):
            continue
        kept.append(line)
    return "\n".join(kept)


def quality_flags(text):
    """Names of the Gopher-style rules the text breaks (empty list = passes), in this order:

        length, mean_word_length, symbols, bullets, ellipsis, alpha, stopwords,
        repeated_lines, boilerplate
    """
    words = text.split()
    lines = [ln for ln in text.split("\n") if ln.strip()]
    n_words, n_lines = max(1, len(words)), max(1, len(lines))
    flags = []
    if not MIN_WORDS <= len(words) <= MAX_WORDS:
        flags.append("length")
    mean_len = sum(len(w) for w in words) / n_words
    if not MIN_MEAN_WORD <= mean_len <= MAX_MEAN_WORD:
        flags.append("mean_word_length")
    if sum(w.count("#") + w.count("...") for w in words) / n_words > MAX_SYMBOL_RATIO:
        flags.append("symbols")
    if sum(ln.lstrip().startswith(BULLETS) for ln in lines) / n_lines > MAX_BULLET_LINES:
        flags.append("bullets")
    if sum(ln.rstrip().endswith("...") for ln in lines) / n_lines > MAX_ELLIPSIS_LINES:
        flags.append("ellipsis")
    if sum(any(c.isalpha() for c in w) for w in words) / n_words < MIN_ALPHA_WORDS:
        flags.append("alpha")
    present = {w.strip(".,;:!?\"'()").lower() for w in words} & STOPWORDS
    if len(present) < MIN_STOPWORDS:
        flags.append("stopwords")
    if (len(lines) - len(set(lines))) / n_lines > MAX_DUPLICATE_LINES:
        flags.append("repeated_lines")
    low = text.lower()
    if "lorem ipsum" in low or "{" in text:
        flags.append("boilerplate")
    return flags


def keep(text):
    """True if the text breaks none of the quality rules."""
    return not quality_flags(text)


# =============================================================================
# Milestone 3: exact and line-level deduplication
# =============================================================================
def normalise(text):
    """Lower-case, replace every run of non-alphanumeric characters by one space, strip."""
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def exact_dedupe(docs):
    """Keep the first document of each distinct normalised text.

    docs: list of (id, text). Returns (kept, dropped): `kept` is the list of (id, text)
    in the original order; `dropped` maps each removed id to the id of the copy it
    duplicates. Compare documents by the SHA-256 of normalise(text), not by the text.
    """
    seen, kept, dropped = {}, [], {}
    for doc_id, text in docs:
        digest = hashlib.sha256(normalise(text).encode()).hexdigest()
        if digest in seen:
            dropped[doc_id] = seen[digest]
        else:
            seen[digest] = doc_id
            kept.append((doc_id, text))
    return kept, dropped


def line_dedupe(docs, max_docs=6):
    """Remove every line that occurs in MORE than `max_docs` different documents.

    docs: list of (id, text). Count each line once per document (a line repeated inside
    one document still counts once). Returns a new list of (id, text) in the same order;
    a document whose lines are all removed keeps its id with the empty text "".
    """
    in_docs = Counter()
    for _, text in docs:
        in_docs.update(set(text.split("\n")))
    return [(i, "\n".join(ln for ln in text.split("\n") if in_docs[ln] <= max_docs)) for i, text in docs]


# =============================================================================
# Milestone 4: shingles and MinHash
# =============================================================================
def shingles(text, n=SHINGLE_WORDS):
    """The set of overlapping n-word windows of the lower-cased text (words split on whitespace).

    A text with fewer than n words but at least one word gives a single shingle (all its
    words); an empty text gives the empty set.
    """
    w = text.lower().split()
    if not w:
        return set()
    if len(w) < n:
        return {" ".join(w)}
    return {" ".join(w[i:i + n]) for i in range(len(w) - n + 1)}


def jaccard(a, b):
    """|A & B| / |A | B|, and 0.0 if both sets are empty."""
    union = len(a | b)
    return len(a & b) / union if union else 0.0


def minhash_signature(shingle_set, num_perm=NUM_PERM):
    """The MinHash signature: for each of the first `num_perm` hash functions
    h_i(x) = (a_i * x + b_i) mod PRIME in HASH_COEFS, the minimum over the set of
    h_i(base_hash(shingle)). An empty set gives [EMPTY] * num_perm."""
    if not shingle_set:
        return [EMPTY] * num_perm
    xs = [base_hash(s) for s in shingle_set]
    return [min((a * x + b) % PRIME for x in xs) for a, b in HASH_COEFS[:num_perm]]


def estimate_jaccard(sig_a, sig_b):
    """The fraction of positions where two signatures agree."""
    return sum(x == y for x, y in zip(sig_a, sig_b)) / len(sig_a)


# =============================================================================
# Milestone 5: locality-sensitive hashing
# =============================================================================
def band_keys(sig, b=BANDS, r=ROWS):
    """Split a signature into b bands of r rows. Return b hashable keys, one per band,
    each of the form (band_index, tuple_of_the_r_values). The band index is part of the
    key so a match in band 3 never collides with a match in band 4."""
    return [(i, tuple(sig[i * r:(i + 1) * r])) for i in range(b)]


def candidate_pairs(sigs, b=BANDS, r=ROWS):
    """All pairs of documents that share at least one band.

    sigs: dict id -> signature (length at least b * r). Returns a set of tuples
    (id1, id2) with id1 < id2. Use one hash table from band key to the list of ids that
    have it; never compare two documents unless they landed in the same bucket.
    """
    raise NotImplementedError("TODO milestone 5: candidate_pairs")


def candidate_probability(s, b=BANDS, r=ROWS):
    """P(two documents of Jaccard similarity s become a candidate pair) = 1 - (1 - s^r)^b."""
    return 1.0 - (1.0 - s ** r) ** b


def threshold(b=BANDS, r=ROWS):
    """The similarity at which the S-curve is steepest, approximately (1/b)^(1/r)."""
    return (1.0 / b) ** (1.0 / r)


def best_bands(num_perm, target):
    """Among all (b, r) with b * r == num_perm, the one whose threshold(b, r) is closest to `target`.
    Returns (b, r). If two are equally close, prefer the one with more bands."""
    options = [(b, num_perm // b) for b in range(1, num_perm + 1) if num_perm % b == 0]
    return min(options, key=lambda br: (abs(threshold(*br) - target), -br[0]))


# =============================================================================
# Milestone 6: evaluation and the whole pipeline
# =============================================================================
def precision_recall(predicted, gold):
    """(precision, recall) of a set of predicted pairs against the gold set.

    precision = |predicted & gold| / |predicted|, recall = |predicted & gold| / |gold|.
    An empty prediction has precision 1.0 (it claimed nothing wrong); an empty gold set
    has recall 1.0.
    """
    hit = len(predicted & gold)
    return (hit / len(predicted) if predicted else 1.0), (hit / len(gold) if gold else 1.0)


def clusters(ids, pairs):
    """Connected components of the graph whose nodes are `ids` and edges are `pairs`.

    Returns a list of sorted id lists, sorted by their first id. An id in no pair is a
    cluster of one. (Union-find, or a simple graph search.)
    """
    parent = {i: i for i in ids}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]          # path halving
            x = parent[x]
        return x

    for a, b in pairs:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)
    groups = {}
    for i in ids:
        groups.setdefault(find(i), []).append(i)
    return sorted((sorted(g) for g in groups.values()), key=lambda g: g[0])


def near_dedupe(docs, b=BANDS, r=ROWS, min_jaccard=0.0):
    """Remove near-duplicates with MinHash and LSH.

    docs: dict id -> text. Steps: shingle every text, sign it, find candidate pairs with
    `candidate_pairs`, then keep only the candidates whose TRUE Jaccard similarity is at
    least `min_jaccard` (0.0 keeps them all). Group the surviving pairs into clusters and
    keep the smallest id of each cluster.

    Returns (kept_ids, removed, pairs): kept_ids a sorted list, removed a dict mapping each
    removed id to the cluster representative that was kept, pairs the set of pairs used.
    """
    sh = {i: shingles(t) for i, t in docs.items()}
    sigs = {i: minhash_signature(s) for i, s in sh.items()}
    pairs = {p for p in candidate_pairs(sigs, b, r) if jaccard(sh[p[0]], sh[p[1]]) >= min_jaccard}
    kept, removed = [], {}
    for group in clusters(sorted(docs), pairs):
        kept.append(group[0])
        for other in group[1:]:
            removed[other] = group[0]
    return sorted(kept), removed, pairs


def run_pipeline(pages, b=BANDS, r=ROWS):
    """Run every stage on a list of corpus.Page and return a Report.

    Order: extract -> c4_line_filter(require_punct=False) -> quality_flags (drop pages with
    any flag; dropped[id] = ("quality", ",".join(flags))) -> line_dedupe -> exact_dedupe
    (dropped[id] = ("exact", kept_id)) -> near_dedupe (dropped[id] = ("near", kept_id)).
    `after_lines` is the number of documents still non-empty after line_dedupe (empty ones
    are dropped as ("lines", "empty")). `precision` and `recall` score near_dedupe's pairs
    against corpus.gold_pairs of the documents that entered it.
    """
    rep = Report(n_pages=len(pages))
    docs = []
    for p in pages:
        text = c4_line_filter(extract(p.html), require_punct=False)
        flags = quality_flags(text)
        if flags:
            rep.dropped[p.id] = ("quality", ",".join(flags))
        else:
            docs.append((p.id, text))
    rep.after_quality = len(docs)
    docs = line_dedupe(docs)
    for i, t in docs:
        if not t:
            rep.dropped[i] = ("lines", "empty")
    docs = [(i, t) for i, t in docs if t]
    rep.after_lines = len(docs)
    docs, exact_dropped = exact_dedupe(docs)
    for i, rep_id in exact_dropped.items():
        rep.dropped[i] = ("exact", rep_id)
    rep.after_exact = len(docs)
    kept, removed, pairs = near_dedupe(dict(docs), b, r)
    for i, rep_id in removed.items():
        rep.dropped[i] = ("near", rep_id)
    rep.kept, rep.after_near, rep.candidates = kept, len(kept), len(pairs)
    rep.precision, rep.recall = precision_recall(pairs, corpus.gold_pairs({i for i, _ in docs}))
    return rep
