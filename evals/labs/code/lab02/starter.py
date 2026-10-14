"""Lab 2: calibrate an LLM judge (starter: your file).

Pipeline: human labels + judge verdicts -> confusion matrix (TPR, TNR, kappa) -> honest split and
error bars -> probe position bias (swap the order) and length bias (pad the answer)
-> correct the judge's pass rate on unlabelled traffic (Rogan-Gladen) with a bootstrap interval.

    1  confusion, rates, cohen_kappa
    2  split_items, bootstrap_rate_cis
    3  swap_test
    4  pad_answer, padding_probe
    5  rogan_gladen, correct_pass_rate, corrected_ci

Standard library only. The judge itself is in judge.py (a stand-in; you do not edit it).
"""
import json
import math
import os
import random
from collections import defaultdict

from judge import judge_single, judge_pair

HERE = os.path.dirname(os.path.abspath(__file__))
PASS, FAIL = "PASS", "FAIL"
PAD_SENTENCE = "Thank you for getting in touch."          # six harmless words


# ----------------------------------------------------------------------------- given

def load_labelled():
    """The 200 human-labelled answers: dicts with id, question, answer, human ("PASS" or "FAIL")."""
    with open(os.path.join(HERE, "labelled.jsonl"), encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def load_production():
    """1,500 unlabelled production answers: dicts with id, question, answer (no human label)."""
    with open(os.path.join(HERE, "production.jsonl"), encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def run_judge(items, judge=judge_single):
    """The judge's verdict ("PASS" or "FAIL") for each item, in order."""
    return [judge(it["question"], it["answer"]) for it in items]


def make_pairs(items):
    """(question, good_answer, bad_answer) for every question where humans passed exactly one of its two answers."""
    by_q = defaultdict(list)
    for it in items:
        by_q[it["id"][:-1]].append(it)                    # ids end in a/b: same prefix = same question
    pairs = []
    for group in by_q.values():
        labels = {g["human"] for g in group}
        if len(group) == 2 and labels == {PASS, FAIL}:
            good = next(g for g in group if g["human"] == PASS)
            bad = next(g for g in group if g["human"] == FAIL)
            pairs.append((good["question"], good["answer"], bad["answer"]))
    return pairs


# ----------------------------------------------------------------------------- milestone 1

def confusion(human, judged):
    """Count the four cells, with the human label as the reference and PASS as "positive".

    Return {"tp": human PASS & judge PASS, "fn": human PASS & judge FAIL,
            "fp": human FAIL & judge PASS, "tn": human FAIL & judge FAIL}.
    Raise ValueError if the lists differ in length or contain a label other than "PASS"/"FAIL".
    """
    raise NotImplementedError("TODO milestone 1: confusion")


def rates(cm):
    """Return {"accuracy", "tpr", "tnr"} from a confusion dict.

    accuracy  (tp + tn) / total
    tpr       tp / (tp + fn): of the outputs humans PASS, the share the judge passes
    tnr       tn / (tn + fp): of the outputs humans FAIL, the share the judge fails
    A rate whose denominator is zero is None.
    """
    raise NotImplementedError("TODO milestone 1: rates")


def cohen_kappa(cm):
    """Cohen's kappa between the human labels and the judge: (po - pe) / (1 - pe).

    po is the observed agreement; pe is the agreement expected by chance if each rater kept its own
    PASS rate: pe = p_human * p_judge + (1 - p_human) * (1 - p_judge). If pe == 1 (no variation at
    all) return 1.0 when po == 1 and 0.0 otherwise.
    """
    raise NotImplementedError("TODO milestone 1: cohen_kappa")


# ----------------------------------------------------------------------------- milestone 2

def split_items(items, dev_frac=0.5, seed=0):
    """Split labelled items into (dev, test), stratified by the human label.

    Within each label, shuffle with random.Random(seed) and give the first round(dev_frac * count)
    items to dev and the rest to test. Neither list may share an item; every item lands in one of them.
    Return each list in the original order of `items`. Do not modify `items`.
    """
    raise NotImplementedError("TODO milestone 2: split_items")


def bootstrap_rate_cis(human, judged, B=1000, alpha=0.05, seed=0):
    """Percentile bootstrap intervals for TPR and TNR: {"tpr": (lo, hi), "tnr": (lo, hi)}.

    TPR is a rate over the human-PASS items only, so resample those (with replacement, same count)
    for it; resample the human-FAIL items separately for TNR. Use random.Random(seed). Sort the B
    estimates; lo = xs[int(alpha / 2 * B)], hi = xs[int((1 - alpha / 2) * B) - 1].
    """
    raise NotImplementedError("TODO milestone 2: bootstrap_rate_cis")


# ----------------------------------------------------------------------------- milestone 3

def swap_test(pairs, judge_pair=judge_pair):
    """Judge every (question, good, bad) pair in BOTH orders and summarise.

    judge_pair(question, first, second) returns "A" (the first shown wins) or "B". Return a dict:
      first_slot_rate  share of all 2n judgments that picked "A" (0.5 if the judge has no position preference)
      good_first       share of pairs where the good answer won when shown first
      good_second      share of pairs where the good answer won when shown second
      strict_win       share of pairs where the good answer won in both orders
      strict_loss      share of pairs where the bad answer won in both orders
      consistent       strict_win + strict_loss (the same answer won both times)
      swap_score       strict_win + 0.5 * (share of pairs where the verdict flipped with the order)
    """
    raise NotImplementedError("TODO milestone 3: swap_test")


# ----------------------------------------------------------------------------- milestone 4

def pad_answer(answer, extra_words):
    """Append harmless filler: PAD_SENTENCE repeated ceil(extra_words / 6) times, joined by single
    spaces after the original answer. extra_words <= 0 returns the answer unchanged."""
    raise NotImplementedError("TODO milestone 4: pad_answer")


def padding_probe(items, judge=judge_single, extra_words=80):
    """Does padding an answer with fluff change the judge's verdict? (No human labels needed.)

    Judge every item as it is, and again with pad_answer(answer, extra_words). Return:
      n_fail, n_pass          how many items the judge failed / passed before padding
      fail_to_pass            share of the n_fail items that the padded version passes
      pass_to_fail            share of the n_pass items that the padded version fails
    A share over zero items is None.
    """
    raise NotImplementedError("TODO milestone 4: padding_probe")


# ----------------------------------------------------------------------------- milestone 5

def rogan_gladen(observed, tpr, tnr):
    """The true pass rate implied by the judge's observed pass rate, given its TPR and TNR:
        p = (observed + tnr - 1) / (tpr + tnr - 1)
    Clip the result to [0, 1]. If tpr + tnr - 1 <= 0 the judge is no better than a coin and the
    correction is meaningless: raise ValueError."""
    raise NotImplementedError("TODO milestone 5: rogan_gladen")


def _tpr_tnr(pairs):
    """(tpr, tnr) from a list of (human, judged) pairs, or None if a class is missing."""
    cm = confusion([h for h, _ in pairs], [j for _, j in pairs])
    r = rates(cm)
    return None if r["tpr"] is None or r["tnr"] is None else (r["tpr"], r["tnr"])


def correct_pass_rate(human, judged, prod_judged):
    """Correct the judge's pass rate on unlabelled traffic.

    human/judged: labels and verdicts on the calibration set. prod_judged: verdicts on production.
    Return {"observed": judge's pass rate on prod_judged, "tpr", "tnr" (from the calibration set),
            "corrected": rogan_gladen(observed, tpr, tnr)}.
    """
    raise NotImplementedError("TODO milestone 5: correct_pass_rate")


def corrected_ci(human, judged, prod_judged, B=2000, alpha=0.05, seed=0):
    """Bootstrap interval for the corrected pass rate, resampling BOTH data sets.

    Each of the B repetitions: resample the calibration pairs (human, judged) with replacement
    (same count) to get a new TPR and TNR; resample prod_judged with replacement (same count) to get a
    new observed rate; apply rogan_gladen. Skip a repetition (it does not count towards B's
    percentile positions) if a class is missing or tpr + tnr - 1 <= 0. Use random.Random(seed).
    Sort the kept estimates xs; return (xs[int(alpha / 2 * m)], xs[int((1 - alpha / 2) * m) - 1])
    with m = len(xs).
    """
    raise NotImplementedError("TODO milestone 5: corrected_ci")
