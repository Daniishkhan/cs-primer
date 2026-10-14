"""bm25.py: the lexical retriever, GIVEN (the same engine as Labs 1 and 3, in a smaller package).

    index = Bm25Index(docs)                  # docs: {doc_id: text}
    index.search("refund policy", k=20)      # [(doc_id, score), ...] best first, ties by doc id

Analysis is deliberately plain: lower-case, split on letters and digits, drop a short list of
stop words. No stemming, no accent folding. "cancelling" and "cancel" are different terms here,
which is exactly the weakness the dense stand-in compensates for. Scores use the Lucene form of
idf and the usual k1 = 1.2, b = 0.75 (chapter 2).
"""
import math
import re

K1, B = 1.2, 0.75
STOP = {"a", "an", "and", "are", "as", "at", "be", "by", "can", "do", "does", "for", "from", "how", "i", "if", "in",
        "is", "it", "my", "of", "on", "or", "the", "to", "what", "when", "with", "you", "your"}
_TOKEN = re.compile(r"[a-z0-9]+")


def analyse(text):
    """'Error E4021-B!' -> ['error', 'e4021', 'b']"""
    return [t for t in _TOKEN.findall(text.lower()) if t not in STOP]


class Bm25Index:
    def __init__(self, docs):
        self.postings = {}                      # term -> {doc_id: tf}
        self.doc_len = {}
        for doc_id, text in docs.items():
            terms = analyse(text)
            self.doc_len[doc_id] = len(terms)
            for t in terms:
                by_doc = self.postings.setdefault(t, {})
                by_doc[doc_id] = by_doc.get(doc_id, 0) + 1
        self.n = len(self.doc_len)
        self.avgdl = sum(self.doc_len.values()) / self.n

    def scores(self, query):
        """{doc_id: BM25 score} for every document that shares a term with the query."""
        acc = {}
        for t in set(analyse(query)):
            plist = self.postings.get(t)
            if not plist:
                continue
            idf = math.log(1 + (self.n - len(plist) + 0.5) / (len(plist) + 0.5))
            for d, tf in plist.items():
                norm = tf * (K1 + 1) / (tf + K1 * (1 - B + B * self.doc_len[d] / self.avgdl))
                acc[d] = acc.get(d, 0.0) + idf * norm
        return acc

    def search(self, query, k=20):
        acc = self.scores(query)
        return sorted(acc.items(), key=lambda kv: (-kv[1], kv[0]))[:k]
