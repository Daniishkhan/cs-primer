"""Lab 1: a search engine with BM25 (reference solution).

Pipeline: text -> analyser -> terms -> inverted index -> BM25 -> top-k.

    1  fold_accents, tokenise, analyse
    2  Index.add, Index.df, Index.posting_list, Index.avg_doc_len
    3  idf, tf_norm, score_doc
    4  search
    5  explain
"""
import heapq
import math
import re
import unicodedata

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
    """Strip combining marks: 'café' -> 'cafe', 'Zoë' -> 'Zoe'."""
    decomposed = unicodedata.normalize("NFD", text)          # e-acute -> e + combining acute
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn")


_TOKEN = re.compile(r"[^\W_]+(?:[.'-][^\W_]+)*")


def tokenise(text):
    """NFC, casefold, cut into tokens that keep internal . ' - and drop a trailing 's."""
    text = unicodedata.normalize("NFC", text).casefold()
    tokens = _TOKEN.findall(text)
    return [t[:-2] if t.endswith("'s") else t for t in tokens]


def analyse(text, fold=True, stop=True, stem=True):
    """text -> list of index terms: fold accents, tokenise, drop stop words, stem."""
    if fold:
        text = fold_accents(text)
    terms = tokenise(text)
    if stop:
        terms = [t for t in terms if t not in STOP]
    if stem:
        terms = [light_stem(t) for t in terms]
    return terms


# =============================================================================
# Milestone 2: the inverted index
# =============================================================================
class Index:
    def __init__(self, analyser=analyse):
        self.analyser = analyser
        self.postings = {}        # term -> {doc_id: tf}
        self.doc_len = {}         # doc_id -> number of terms after analysis

    @property
    def n_docs(self):
        return len(self.doc_len)

    def add(self, doc_id, text):
        """Analyse `text` and record its terms. Duplicate doc ids are an error."""
        if doc_id in self.doc_len:
            raise ValueError(f"document {doc_id!r} is already indexed")
        terms = self.analyser(text)
        self.doc_len[doc_id] = len(terms)          # a document of only stop words still counts
        for t in terms:
            by_doc = self.postings.setdefault(t, {})
            by_doc[doc_id] = by_doc.get(doc_id, 0) + 1

    def df(self, term):
        """Number of documents containing `term` (0 if unseen)."""
        return len(self.postings.get(term, ()))

    def posting_list(self, term):
        """[(doc_id, tf), ...] sorted by doc_id; [] for an unseen term."""
        return sorted(self.postings.get(term, {}).items())

    def avg_doc_len(self):
        """Mean document length over all indexed documents (0.0 for an empty index)."""
        if not self.doc_len:
            return 0.0
        return sum(self.doc_len.values()) / len(self.doc_len)

    def tf(self, term, doc_id):
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
    """ln(1 + (N - df + 0.5) / (df + 0.5)): the Lucene form, never negative."""
    return math.log(1 + (n_docs - df + 0.5) / (df + 0.5))


def tf_norm(tf, dl, avgdl, k1=K1, b=B):
    """tf * (k1 + 1) / (tf + k1 * (1 - b + b * dl / avgdl)); 0 when tf is 0."""
    if tf == 0:
        return 0.0
    return tf * (k1 + 1) / (tf + k1 * (1 - b + b * dl / avgdl))


def score_doc(index, terms, doc_id, k1=K1, b=B):
    """BM25 score of one document for a list of distinct query terms."""
    n, avgdl, dl = index.n_docs, index.avg_doc_len(), index.doc_len[doc_id]
    total = 0.0
    for t in terms:
        tf = index.tf(t, doc_id)
        if tf:
            total += idf(n, index.df(t)) * tf_norm(tf, dl, avgdl, k1, b)
    return total


# =============================================================================
# Milestone 4: top-k search, term at a time
# =============================================================================
def search(index, query, k=10, k1=K1, b=B):
    """[(doc_id, score), ...], best first; ties broken by doc_id; only matching documents."""
    n, avgdl = index.n_docs, index.avg_doc_len()
    acc = {}                                           # doc_id -> partial score
    for t in query_terms(index, query):
        postings = index.posting_list(t)
        if not postings:
            continue
        w = idf(n, len(postings))                      # one idf per term, not per document
        for doc_id, tf in postings:
            acc[doc_id] = acc.get(doc_id, 0.0) + w * tf_norm(tf, index.doc_len[doc_id], avgdl, k1, b)
    return heapq.nsmallest(k, acc.items(), key=lambda kv: (-kv[1], kv[0]))


# =============================================================================
# Milestone 5: explain
# =============================================================================
def explain(index, query, doc_id, k1=K1, b=B):
    """Per-term breakdown of a document's score, biggest contribution first.

    Each entry: {"term", "tf", "df", "idf", "tf_norm", "score"}. Terms the document
    does not contain are left out, so the entries sum to the document's score.
    """
    n, avgdl, dl = index.n_docs, index.avg_doc_len(), index.doc_len[doc_id]
    rows = []
    for t in query_terms(index, query):
        tf = index.tf(t, doc_id)
        if not tf:
            continue
        w, comp = idf(n, index.df(t)), tf_norm(tf, dl, avgdl, k1, b)
        rows.append({"term": t, "tf": tf, "df": index.df(t), "idf": w, "tf_norm": comp, "score": w * comp})
    rows.sort(key=lambda r: (-r["score"], r["term"]))
    return rows
