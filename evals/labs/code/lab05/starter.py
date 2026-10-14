"""Lab 5: citation checking and abstention (starter: your file).

A stand-in assistant answers questions about a council's leisure-services handbook (data.py) and cites its
sources. You build the verification stage of chapter 12 and the abstention policy of chapter 11:

    1  normalise_with_map, verify_quote, check_citation        do the quoted words exist, in a real source?
    2  judge_claim, evaluate_judge                              does the cited text support the claim?
    3  entails, check_statement, verify_answer, citation_report ALCE-style recall and precision, and one support score
    4  risk_coverage, aurc, max_coverage_at_risk                the risk-coverage curve of two confidence signals
    5  expected_score, best_threshold, fit_binning, calibrate   choose a threshold from the cost of a wrong answer

Everything that is not a milestone function is given. Every function you write raises NotImplementedError until you do.
Standard library only.
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
    raise NotImplementedError("TODO milestone 1: normalise_with_map")


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
    raise NotImplementedError("TODO milestone 1: check_citation")


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
    raise NotImplementedError("TODO milestone 2: judge_claim")


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
    raise NotImplementedError("TODO milestone 2: evaluate_judge")


# ----------------------------------------------------------------------------- milestone 3

def entails(statement, doc_ids, corpus, judge=None):
    """Do the cited documents, taken together, support the statement? Documents that do not exist are ignored; if
    none exist the answer is False. True exactly when judge_claim(statement, [texts]).label == "SUPPORTED"."""
    raise NotImplementedError("TODO milestone 3: entails")


def check_statement(stmt, corpus, judge=None):
    """Check one statement {"text", "cites": [{"doc", "quote"}, ...]} against the corpus. Return a dict:
      cites      one dict per citation, in order: {"doc", "status" (check_citation), "alone" (entails with only this
                 document), "irrelevant" (not alone, but the OTHER citations of the statement do entail it)}
      recall     1 if the statement has at least one citation and all its cited documents together entail it, else 0
      precision  one 0/1 per citation: 1 if recall == 1 and the citation is not irrelevant
      support    0.0 unless the statement has citations, EVERY citation has status "ok" and the judge's label on all
                 cited documents together is SUPPORTED; then the judge's score
    """
    raise NotImplementedError("TODO milestone 3: check_statement")


def verify_answer(answer, corpus, judge=None):
    """Check every statement of an answer. Return {"statements": [check_statement(...)...], "support": s} where the
    answer's support is the MINIMUM statement support (an answer is only as good as its weakest claim; 0.0 for an
    answer with no statements)."""
    raise NotImplementedError("TODO milestone 3: verify_answer")


def citation_report(answers, corpus, judge=None):
    """Aggregate the checks over many answers. Return a dict of rates (each 1.0 when its denominator is 0):
      existence   share of citations whose status is not "no_such_source"
      quotes      share of citations whose status is "ok"
      recall      share of statements with recall 1
      precision   share of citations with precision 1
      uncited     share of statements with no citation (a COUNT-based share of statements, 0.0 if none)
      statements, citations   the two counts
    """
    raise NotImplementedError("TODO milestone 3: citation_report")


# ----------------------------------------------------------------------------- milestone 4

def risk_coverage(rows):
    """The risk-coverage curve of a confidence signal. rows is a list of (confidence, correct). For each DISTINCT
    confidence value t, highest first, the system that answers every row with confidence >= t has
         coverage = answered / total      risk = wrong answers / answered
    Return [(t, coverage, risk), ...], highest threshold first. Rows with equal confidence enter together (a tie
    cannot be split by a threshold). Empty input gives []."""
    raise NotImplementedError("TODO milestone 4: risk_coverage")


def aurc(points):
    """Area under the risk-coverage curve as a step function: the sum over points of (coverage - previous coverage)
    * risk, with previous coverage 0.0 before the first point. Lower is better. [] gives 0.0."""
    raise NotImplementedError("TODO milestone 4: aurc")


def max_coverage_at_risk(points, max_risk):
    """The largest coverage among points whose risk is at most max_risk; 0.0 if no point qualifies."""
    raise NotImplementedError("TODO milestone 4: max_coverage_at_risk")


def oracle_aurc(n_correct, n):
    """Given: the AURC of a perfect ranking of n answers with n_correct correct (all correct answers first, no
    ties): the mean of the risk after each answer."""
    return sum((k - n_correct) / k for k in range(n_correct + 1, n + 1)) / n


# ----------------------------------------------------------------------------- milestone 5

def expected_score(rows, t, penalty):
    """Mean score per row of the policy "answer when confidence >= t": +1 for a right answer, -penalty for a wrong
    one, 0 for an abstention. The mean is over ALL rows, answered or not. [] gives 0.0."""
    raise NotImplementedError("TODO milestone 5: expected_score")


def best_threshold(rows, penalty):
    """The threshold with the highest expected_score on these rows. Candidates are the distinct confidence values
    plus math.inf (answer nothing, score 0.0). On a tie take the HIGHER threshold. Return (t, score)."""
    raise NotImplementedError("TODO milestone 5: best_threshold")


def theory_threshold(penalty):
    """If confidences were calibrated, answering beats abstaining exactly when c > penalty / (1 + penalty)."""
    return penalty / (1.0 + penalty)


def fit_binning(rows, n_bins=10):
    """Histogram-binning recalibration. Bin i covers confidences in [i/n_bins, (i+1)/n_bins), the last bin also
    includes 1.0 and anything above. Return a list of n_bins numbers: the share of correct answers in each bin, or
    the bin's midpoint (i + 0.5) / n_bins if the bin is empty."""
    raise NotImplementedError("TODO milestone 5: fit_binning")


def calibrate(conf, table):
    """Map a confidence to the accuracy of its bin in a table from fit_binning (same binning rule)."""
    raise NotImplementedError("TODO milestone 5: calibrate")
