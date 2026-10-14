"""Lab 1: a search engine with BM25.

Pipeline: text -> analyser -> terms -> inverted index -> BM25 scores -> top-k.

The vocabulary is chapters 1 and 2 of this course:

    term         what the index stores after analysis (not the raw word)
    tf           times a term occurs in one document
    df           number of documents containing a term
    N, avgdl     number of documents, mean document length (in terms)
    idf          ln(1 + (N - df + 0.5) / (df + 0.5))
    tf_norm      tf * (k1 + 1) / (tf + k1 * (1 - b + b * dl / avgdl))
    score(q, d)  sum over the distinct query terms t of idf(t) * tf_norm(t, d)

What is GIVEN: the constants, the stop list, a crude stemmer and `query_terms`.
What YOU write is marked TODO:

    1  fold_accents, tokenise, analyse
    2  Index.add, Index.df, Index.posting_list, Index.avg_doc_len
    3  idf, tf_norm, score_doc
    4  search
    5  explain

`python3 check.py` runs the milestones; the lab page explains each one.
"""
import heapq          # noqa: F401  (milestone 4: heapq.nsmallest is a good fit)
import math           # noqa: F401
import re             # noqa: F401
import unicodedata    # noqa: F401

K1 = 1.2          # term-frequency saturation (Lucene default)
B = 0.75          # length normalisation (Lucene default)

STOP = {"the", "a", "an", "of", "to", "and", "in", "is", "for", "on", "are", "be", "by",
        "or", "it", "at", "as", "with", "you", "your", "this", "that", "from"}


# =============================================================================
# GIVEN: a crude stemmer (a stand-in for Porter or Snowball, as in chapter 1)
# =============================================================================
def light_stem(w):
    for suf, rep in [("ational", "ate"), ("ization", "ize"), ("ies", "y"), ("sses", "ss"),
                     ("ing", ""), ("ed", ""), ("es", ""), ("s", ""), ("ly", "")]:
        if w.endswith(suf) and len(w) - len(suf) >= 3 and not w.endswith("ss"):
            return w[: len(w) - len(suf)] + rep
    return w


# =============================================================================
# Milestone 1: the analyser
# =============================================================================
def fold_accents(text):
    """Strip combining marks: 'café' -> 'cafe', 'Zoë' -> 'Zoe'.

    Decompose with unicodedata.normalize("NFD", ...) and drop the characters whose
    unicodedata.category is "Mn". Case is left alone ('Café' -> 'Cafe') and so are
    letters that are not accented ('Straße' stays 'Straße').
    """
    raise NotImplementedError("TODO milestone 1: fold_accents")


def tokenise(text):
    """Normalise to NFC, casefold, then cut into tokens.

    A token is a run of letters and digits (underscore is a separator) that may contain
    '.', "'" or '-' BETWEEN letters or digits. A trailing 's is dropped.

        tokenise("Dr. O'Neil's co-op paid $1,250.50")
        -> ['dr', "o'neil", 'co-op', 'paid', '1', '250.50']

    Use one compiled regex with findall: [^\\W_]+ is "letters and digits".
    """
    raise NotImplementedError("TODO milestone 1: tokenise")


def analyse(text, fold=True, stop=True, stem=True):
    """text -> list of index terms.

    In this order: fold accents (if `fold`), tokenise, drop words in STOP (if `stop`),
    apply light_stem to each term (if `stem`).

        analyse("The refunds are issued to the original payment method.")
        -> ['refund', 'issu', 'original', 'payment', 'method']
    """
    raise NotImplementedError("TODO milestone 1: analyse")


# =============================================================================
# Milestone 2: the inverted index
# =============================================================================
class Index:
    """An in-memory inverted index. `analyser` maps text to a list of terms."""

    def __init__(self, analyser=analyse):
        self.analyser = analyser
        self.postings = {}        # term -> {doc_id: tf}
        self.doc_len = {}         # doc_id -> number of terms after analysis

    @property
    def n_docs(self):
        return len(self.doc_len)

    def add(self, doc_id, text):
        """Analyse `text` and record its terms.

        Fill `self.postings` and `self.doc_len`. A document whose text analyses to no
        terms is still a document (length 0). Adding a doc id that is already indexed
        raises ValueError, and must leave the index exactly as it was.
        """
        raise NotImplementedError("TODO milestone 2: Index.add")

    def df(self, term):
        """Number of documents containing `term` (0 if unseen)."""
        raise NotImplementedError("TODO milestone 2: Index.df")

    def posting_list(self, term):
        """[(doc_id, tf), ...] sorted by doc_id; [] for an unseen term."""
        raise NotImplementedError("TODO milestone 2: Index.posting_list")

    def avg_doc_len(self):
        """Mean document length over ALL indexed documents (0.0 for an empty index)."""
        raise NotImplementedError("TODO milestone 2: Index.avg_doc_len")

    def tf(self, term, doc_id):
        """Term frequency of `term` in `doc_id` (0 if absent). Given."""
        return self.postings.get(term, {}).get(doc_id, 0)


# =============================================================================
# GIVEN: the query goes through the same analyser, once per distinct term
# =============================================================================
def query_terms(index, query):
    seen, out = set(), []
    for t in index.analyser(query):
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


# =============================================================================
# Milestone 3: BM25 pieces
# =============================================================================
def idf(n_docs, df):
    """ln(1 + (N - df + 0.5) / (df + 0.5)).  idf(8, 2) = ln 3.6 = 1.2809."""
    raise NotImplementedError("TODO milestone 3: idf")


def tf_norm(tf, dl, avgdl, k1=K1, b=B):
    """tf * (k1 + 1) / (tf + k1 * (1 - b + b * dl / avgdl)), and 0.0 when tf is 0.

    tf_norm(2, 22, 23.875) = 1.406.  With tf = 1 and dl = avgdl the result is exactly 1.
    """
    raise NotImplementedError("TODO milestone 3: tf_norm")


def score_doc(index, terms, doc_id, k1=K1, b=B):
    """BM25 score of one document for a list of DISTINCT query terms.

    Sum idf(N, df) * tf_norm(tf, dl, avgdl, k1, b) over the terms the document contains.
    Use index.n_docs, index.avg_doc_len(), index.doc_len[doc_id], index.df(t), index.tf(t, doc_id).
    """
    raise NotImplementedError("TODO milestone 3: score_doc")


# =============================================================================
# Milestone 4: top-k search, term at a time
# =============================================================================
def search(index, query, k=10, k1=K1, b=B):
    """[(doc_id, score), ...], best first, at most k, only documents matching a query term.

    Walk the posting list of each query term (query_terms gives the distinct terms) and
    add that term's contribution to a dict of per-document scores. Compute each term's
    idf once, not once per document. Order by score descending, then doc_id ascending.
    """
    raise NotImplementedError("TODO milestone 4: search")


# =============================================================================
# Milestone 5: explain
# =============================================================================
def explain(index, query, doc_id, k1=K1, b=B):
    """Per-term breakdown of a document's score, biggest contribution first.

    One dict per query term the document contains:
        {"term", "tf", "df", "idf", "tf_norm", "score"}   with score = idf * tf_norm.
    Terms the document lacks are left out, so the scores sum to the document's score.
    Sort by score descending, then term ascending.
    """
    raise NotImplementedError("TODO milestone 5: explain")
