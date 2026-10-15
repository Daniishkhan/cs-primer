# Drill: A6 Lab 5, milestone 1 of 5: do the quoted words exist? (step 2 of 3)
# Everything else in this file is already written. Fill in:
#     verify_quote
# Check it with: python3 check.py 1

"""Lab 5: citation checking and abstention (reference solution).

A stand-in assistant answers questions about a council's leisure-services handbook (data.py) and cites its
sources. You build the verification stage of chapter 12 and the abstention policy of chapter 11:

    1  normalise_with_map, verify_quote, check_citation        do the quoted words exist, in a real source?
    2  judge_claim, evaluate_judge                              does the cited text support the claim?
    3  check_statement, verify_answer, citation_report          ALCE-style recall and precision, and one support score
    4  risk_coverage, aurc, max_coverage_at_risk                the risk-coverage curve of two confidence signals
    5  expected_score, best_threshold, fit_binning, calibrate   choose a threshold from the cost of a wrong answer

Standard library only. This file is the reference answer: every function below is complete.
"""
import math
import re
from collections import namedtuple

from data import CORPUS, calibration_set, dev_set, make_dataset, test_set  # noqa: F401

MIN_QUOTE_CHARS = 12            # a quotation shorter than this (all fragments together) proves nothing
MIN_OVERLAP = 0.6               # share of the claim's content words that the best sentence must contain
LABELS = ("SUPPORTED", "CONTRADICTED", "NOT_ENOUGH_INFO")


# ----------------------------------------------------------------------------- given helpers

_QUOTE_MAP = {"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
              "\u2013": "-", "\u2014": "-", "\u2212": "-", "\u00a0": " "}


def split_fragments(quote):
    """A quotation may leave words out with '...' or the single character '…'. Returns the pieces between them."""
    return [p for p in re.split(r"\.\.\.|…", quote)]


STOP = set("""a an the of to in on at is are was were be been has have had do does for and or it its this that
    by with as from can may must will should would there their than then so such""".split())
SYNONYMS = {"hold": "capacity", "holds": "capacity", "room": "capacity", "charges": "costs", "charge": "costs",
            "cost": "costs", "pay": "costs", "ticket": "entry", "enter": "entry", "opening": "opened",
            "open": "opened", "doors": "", "first": "", "year": "", "time": "", "spaces": "spaces", "space": "spaces",
            "offers": "has", "need": "must", "needs": "must", "book": "bookings", "booking": "bookings",
            "weekday": "weekdays", "weekend": "weekends", "visitor": "visitors", "adult": "adults",
            "closing": "closes", "close": "closes", "ahead": "advance", "notice": "advance", "pounds": "pounds",
            "pound": "pounds", "group": "group", "groups": "group", "day": "days", "made": "", "official": "",
            "handbook": "", "confirms": ""}
NEGATIONS = {"not", "no", "never", "cannot", "without", "n't"}


def canon(word):
    """Lower-case a word and fold the stand-in's synonyms together ('hold' and 'room' both mean 'capacity')."""
    word = word.lower()
    return SYNONYMS.get(word, word)


def split_sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def words_of(text):
    """The content words of a text as a list of canonical words: letters only (numbers are separate), no stop
    words, no empty synonyms."""
    out = []
    for w in re.findall(r"[a-z]+", text.lower().replace("\u2019", "").replace("'", "")):
        if w in STOP:
            continue
        w = canon(w)
        if w:
            out.append(w)
    return out


def numbers_of(text):
    """The numbers in a text as a set of strings, commas removed ('3,200' -> '3200')."""
    return set(re.findall(r"\d+", text.replace(",", "")))


def has_negation(text):
    return any(w in NEGATIONS for w in re.findall(r"[a-z']+", text.lower()))


Verdict = namedtuple("Verdict", "label score sentence")


# ----------------------------------------------------------------------------- milestone 1

def normalise_with_map(text):
    """Normalise a text for comparison and remember where every kept character came from.

    Returns (norm, idx). norm is the text with: every character lower-cased (if lower() gives one character),
    curly quotes, dashes and non-breaking spaces replaced as in _QUOTE_MAP, and each run of whitespace collapsed
    to a single space. idx has one entry per character of norm: idx[i] is the offset in the ORIGINAL text of the
    character that norm[i] came from (for a collapsed run, the offset of its first whitespace character).
    Nothing is stripped. len(norm) == len(idx).
    """
    norm, idx, in_space = [], [], False
    for i, ch in enumerate(text):
        ch = _QUOTE_MAP.get(ch, ch)
        low = ch.lower()
        if len(low) == 1:
            ch = low
        if ch.isspace():
            if not in_space:                      # the first whitespace character of a run stands for the run
                norm.append(" ")
                idx.append(i)
            in_space = True
        else:
            norm.append(ch)
            idx.append(i)
            in_space = False
    return "".join(norm), idx


def verify_quote(quote, passage):
    """Where, in the passage, does the quotation appear? Return (start, end) with passage[start:end] the span
    (offsets into the ORIGINAL passage), or None.

    Split the quote into fragments at '...' or '…'; normalise and strip each fragment (drop empty ones); the
    quote is rejected (None) if there are no fragments or all fragments together have fewer than MIN_QUOTE_CHARS
    characters. Normalise the passage with normalise_with_map. Find the fragments in order with str.find in the
    normalised passage, each search starting where the previous fragment ended (so they cannot overlap or go
    backwards). If any fragment is missing, return None. start is the original offset of the first fragment's first
    character; end is one past the original offset of the last fragment's last character.
    """
    raise NotImplementedError("TODO milestone 1: verify_quote")


def check_citation(cite, corpus):
    """Check one citation {"doc": id, "quote": text} against the corpus {id: text}. Return one of:
         "no_such_source"   the document id is not in the corpus (exact match)
         "quote_not_found"  the document exists but verify_quote finds no such span
         "ok"               the quotation is there
    """
    text = corpus.get(cite["doc"])
    if text is None:
        return "no_such_source"
    return "ok" if verify_quote(cite["quote"], text) is not None else "quote_not_found"


# ----------------------------------------------------------------------------- milestone 2

def judge_claim(claim, passages):
    """Decide whether the passages support a claim. A rule-based stand-in for an entailment model.

    Take every sentence of every passage (split_sentences, passages in the given order). For each sentence compute
    overlap = |W(claim) & W(sentence)| / |W(claim)|, where W is the SET of words_of(...) (0.0 if the claim has no
    content words). The best sentence is the one with the highest overlap, the first one on ties. Then, in order:
      no sentences at all, or overlap < MIN_OVERLAP           -> NOT_ENOUGH_INFO
      has_negation(best) != has_negation(claim)               -> CONTRADICTED
      claim has numbers and they are not all in the best sentence's numbers   -> CONTRADICTED
      otherwise                                               -> SUPPORTED
    Return Verdict(label, score=overlap of the best sentence (0.0 if no sentences), sentence=the best sentence or "").
    """
    claim_words = set(words_of(claim))
    best, best_score = "", 0.0
    for passage in passages:
        for sent in split_sentences(passage):
            sw = set(words_of(sent))
            score = len(claim_words & sw) / len(claim_words) if claim_words else 0.0
            if best == "" or score > best_score:
                best, best_score = sent, score
    if best == "" or best_score < MIN_OVERLAP:
        return Verdict("NOT_ENOUGH_INFO", best_score, best)
    if has_negation(best) != has_negation(claim):
        return Verdict("CONTRADICTED", best_score, best)
    nums = numbers_of(claim)
    if nums and not nums <= numbers_of(best):
        return Verdict("CONTRADICTED", best_score, best)
    return Verdict("SUPPORTED", best_score, best)


def evaluate_judge(items, judge=None):
    """Score a judge against gold labels. items is a list of (claim, passages, gold_label). Return a dict:
         confusion   {(gold, predicted): count} with an entry for every pair of LABELS (zeros included)
         accuracy    correct / total
         precision   precision of SUPPORTED: of the claims predicted SUPPORTED, the share whose gold is SUPPORTED
                     (1.0 if nothing was predicted SUPPORTED)
         recall      recall of SUPPORTED: of the claims whose gold is SUPPORTED, the share predicted SUPPORTED
                     (1.0 if there are none)
         false_support  the (claim, gold) pairs predicted SUPPORTED whose gold is not, in input order
    """
    judge = judge or judge_claim
    conf = {(g, p): 0 for g in LABELS for p in LABELS}
    false_support, right = [], 0
    for claim, passages, gold in items:
        pred = judge(claim, passages).label
        conf[(gold, pred)] += 1
        right += pred == gold
        if pred == "SUPPORTED" and gold != "SUPPORTED":
            false_support.append((claim, gold))
    pred_sup = sum(conf[(g, "SUPPORTED")] for g in LABELS)
    gold_sup = sum(conf[("SUPPORTED", p)] for p in LABELS)
    return {"confusion": conf, "accuracy": right / len(items) if items else 1.0,
            "precision": conf[("SUPPORTED", "SUPPORTED")] / pred_sup if pred_sup else 1.0,
            "recall": conf[("SUPPORTED", "SUPPORTED")] / gold_sup if gold_sup else 1.0,
            "false_support": false_support}


# ----------------------------------------------------------------------------- milestone 3

def entails(statement, doc_ids, corpus, judge=None):
    """Do the cited documents, taken together, support the statement? Documents that do not exist are ignored; if
    none exist the answer is False. True exactly when judge_claim(statement, [texts]).label == "SUPPORTED"."""
    judge = judge or judge_claim
    texts = [corpus[d] for d in doc_ids if d in corpus]
    return bool(texts) and judge(statement, texts).label == "SUPPORTED"


def check_statement(stmt, corpus, judge=None):
    """Check one statement {"text", "cites": [{"doc", "quote"}, ...]} against the corpus. Return a dict:
      cites      one dict per citation, in order: {"doc", "status" (check_citation), "alone" (entails with only this
                 document), "irrelevant" (not alone, but the OTHER citations of the statement do entail it)}
      recall     1 if the statement has at least one citation and all its cited documents together entail it, else 0
      precision  one 0/1 per citation: 1 if recall == 1 and the citation is not irrelevant
      support    0.0 unless the statement has citations, EVERY citation has status "ok" and the judge's label on all
                 cited documents together is SUPPORTED; then the judge's score
    """
    judge = judge or judge_claim
    text, cites = stmt["text"], stmt["cites"]
    ids = [c["doc"] for c in cites]
    rows = []
    for k, c in enumerate(cites):
        others = ids[:k] + ids[k + 1:]
        alone = entails(text, [c["doc"]], corpus, judge)
        rows.append({"doc": c["doc"], "status": check_citation(c, corpus), "alone": alone,
                     "irrelevant": (not alone) and entails(text, others, corpus, judge)})
    recall = 1 if cites and entails(text, ids, corpus, judge) else 0
    support = 0.0
    if cites and all(r["status"] == "ok" for r in rows):
        v = judge(text, [corpus[d] for d in ids])
        if v.label == "SUPPORTED":
            support = v.score
    return {"cites": rows, "recall": recall, "precision": [1 if recall and not r["irrelevant"] else 0 for r in rows],
            "support": support}


def verify_answer(answer, corpus, judge=None):
    """Check every statement of an answer. Return {"statements": [check_statement(...)...], "support": s} where the
    answer's support is the MINIMUM statement support (an answer is only as good as its weakest claim; 0.0 for an
    answer with no statements)."""
    res = [check_statement(s, corpus, judge) for s in answer["statements"]]
    return {"statements": res, "support": min((r["support"] for r in res), default=0.0)}


def citation_report(answers, corpus, judge=None):
    """Aggregate the checks over many answers. Return a dict of rates (each 1.0 when its denominator is 0):
      existence   share of citations whose status is not "no_such_source"
      quotes      share of citations whose status is "ok"
      recall      share of statements with recall 1
      precision   share of citations with precision 1
      uncited     share of statements with no citation (a COUNT-based share of statements, 0.0 if none)
      statements, citations   the two counts
    """
    n_s = n_c = ex = ok = rec = prec = unc = 0
    for a in answers:
        for st in verify_answer(a, corpus, judge)["statements"]:
            n_s += 1
            rec += st["recall"]
            unc += not st["cites"]
            for row, p in zip(st["cites"], st["precision"]):
                n_c += 1
                ex += row["status"] != "no_such_source"
                ok += row["status"] == "ok"
                prec += p
    one = lambda a, b: a / b if b else 1.0
    return {"existence": one(ex, n_c), "quotes": one(ok, n_c), "recall": one(rec, n_s), "precision": one(prec, n_c),
            "uncited": unc / n_s if n_s else 0.0, "statements": n_s, "citations": n_c}


# ----------------------------------------------------------------------------- milestone 4

def risk_coverage(rows):
    """The risk-coverage curve of a confidence signal. rows is a list of (confidence, correct). For each DISTINCT
    confidence value t, highest first, the system that answers every row with confidence >= t has
         coverage = answered / total      risk = wrong answers / answered
    Return [(t, coverage, risk), ...], highest threshold first. Rows with equal confidence enter together (a tie
    cannot be split by a threshold). Empty input gives []."""
    n = len(rows)
    groups = {}
    for conf, ok in rows:
        c, w = groups.get(conf, (0, 0))
        groups[conf] = (c + 1, w + (not ok))
    points, answered, wrong = [], 0, 0
    for t in sorted(groups, reverse=True):
        c, w = groups[t]
        answered += c
        wrong += w
        points.append((t, answered / n, wrong / answered))
    return points


def aurc(points):
    """Area under the risk-coverage curve as a step function: the sum over points of (coverage - previous coverage)
    * risk, with previous coverage 0.0 before the first point. Lower is better. [] gives 0.0."""
    area, prev = 0.0, 0.0
    for _, cov, risk in points:
        area += (cov - prev) * risk
        prev = cov
    return area


def max_coverage_at_risk(points, max_risk):
    """The largest coverage among points whose risk is at most max_risk; 0.0 if no point qualifies."""
    ok = [cov for _, cov, risk in points if risk <= max_risk]
    return max(ok) if ok else 0.0


def oracle_aurc(n_correct, n):
    """Given: the AURC of a perfect ranking of n answers with n_correct correct (all correct answers first, no
    ties): the mean of the risk after each answer."""
    return sum((k - n_correct) / k for k in range(n_correct + 1, n + 1)) / n


# ----------------------------------------------------------------------------- milestone 5

def expected_score(rows, t, penalty):
    """Mean score per row of the policy "answer when confidence >= t": +1 for a right answer, -penalty for a wrong
    one, 0 for an abstention. The mean is over ALL rows, answered or not. [] gives 0.0."""
    if not rows:
        return 0.0
    return sum((1.0 if ok else -penalty) for conf, ok in rows if conf >= t) / len(rows)


def best_threshold(rows, penalty):
    """The threshold with the highest expected_score on these rows. Candidates are the distinct confidence values
    plus math.inf (answer nothing, score 0.0). On a tie take the HIGHER threshold. Return (t, score)."""
    best_t, best_s = math.inf, 0.0
    for t in sorted({c for c, _ in rows}, reverse=True):
        s = expected_score(rows, t, penalty)
        if s > best_s:                       # strict: scanning from the top, an equal score keeps the higher t
            best_t, best_s = t, s
    return best_t, best_s


def theory_threshold(penalty):
    """If confidences were calibrated, answering beats abstaining exactly when c > penalty / (1 + penalty)."""
    return penalty / (1.0 + penalty)


def fit_binning(rows, n_bins=10):
    """Histogram-binning recalibration. Bin i covers confidences in [i/n_bins, (i+1)/n_bins), the last bin also
    includes 1.0 and anything above. Return a list of n_bins numbers: the share of correct answers in each bin, or
    the bin's midpoint (i + 0.5) / n_bins if the bin is empty."""
    right, total = [0] * n_bins, [0] * n_bins
    for conf, ok in rows:
        b = min(max(int(conf * n_bins), 0), n_bins - 1)
        total[b] += 1
        right[b] += bool(ok)
    return [right[i] / total[i] if total[i] else (i + 0.5) / n_bins for i in range(n_bins)]


def calibrate(conf, table):
    """Map a confidence to the accuracy of its bin in a table from fit_binning (same binning rule)."""
    n = len(table)
    return table[min(max(int(conf * n), 0), n - 1)]
