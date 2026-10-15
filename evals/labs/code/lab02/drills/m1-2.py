# Drill: A6 Lab 2, milestone 1 of 5: agreement with the humans (step 2 of 3)
# Everything else in this file is already written. Fill in:
#     rates
# Check it with: python3 check.py 1

"""Lab 2: calibrate an LLM judge (reference solution).

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
    if len(human) != len(judged):
        raise ValueError(f"{len(human)} human labels but {len(judged)} judge verdicts")
    cm = {"tp": 0, "fn": 0, "fp": 0, "tn": 0}
    for h, j in zip(human, judged):
        if h not in (PASS, FAIL) or j not in (PASS, FAIL):
            raise ValueError(f"labels must be 'PASS' or 'FAIL'; got {h!r} and {j!r}")
        key = ("t" if h == j else "f") + ("p" if j == PASS else "n")
        cm[key] += 1
    return cm


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
    n = sum(cm.values())
    po = (cm["tp"] + cm["tn"]) / n
    p_h = (cm["tp"] + cm["fn"]) / n
    p_j = (cm["tp"] + cm["fp"]) / n
    pe = p_h * p_j + (1 - p_h) * (1 - p_j)
    if pe == 1:
        return 1.0 if po == 1 else 0.0
    return (po - pe) / (1 - pe)


# ----------------------------------------------------------------------------- milestone 2

def split_items(items, dev_frac=0.5, seed=0):
    """Split labelled items into (dev, test), stratified by the human label.

    Within each label, shuffle with random.Random(seed) and give the first round(dev_frac * count)
    items to dev and the rest to test. Neither list may share an item; every item lands in one of them.
    Return each list in the original order of `items`. Do not modify `items`.
    """
    rng = random.Random(seed)
    dev_ids = set()
    for label in (PASS, FAIL):
        ids = [it["id"] for it in items if it["human"] == label]
        rng.shuffle(ids)
        dev_ids.update(ids[:round(dev_frac * len(ids))])
    dev = [it for it in items if it["id"] in dev_ids]
    test = [it for it in items if it["id"] not in dev_ids]
    return dev, test


def bootstrap_rate_cis(human, judged, B=1000, alpha=0.05, seed=0):
    """Percentile bootstrap intervals for TPR and TNR: {"tpr": (lo, hi), "tnr": (lo, hi)}.

    TPR is a rate over the human-PASS items only, so resample those (with replacement, same count)
    for it; resample the human-FAIL items separately for TNR. Use random.Random(seed). Sort the B
    estimates; lo = xs[int(alpha / 2 * B)], hi = xs[int((1 - alpha / 2) * B) - 1].
    """
    rng = random.Random(seed)
    pos = [j == PASS for h, j in zip(human, judged) if h == PASS]       # judge caught it?
    neg = [j == FAIL for h, j in zip(human, judged) if h == FAIL]
    out = {}
    for name, hits in (("tpr", pos), ("tnr", neg)):
        n = len(hits)
        xs = sorted(sum(hits[rng.randrange(n)] for _ in range(n)) / n for _ in range(B))
        out[name] = (xs[int(alpha / 2 * B)], xs[int((1 - alpha / 2) * B) - 1])
    return out


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
    n = len(pairs)
    a_picks = good_first = good_second = wins = losses = 0
    for q, good, bad in pairs:
        v1 = judge_pair(q, good, bad)            # good shown first
        v2 = judge_pair(q, bad, good)            # same pair, good shown second
        a_picks += (v1 == "A") + (v2 == "A")
        g1, g2 = v1 == "A", v2 == "B"
        good_first += g1
        good_second += g2
        wins += g1 and g2
        losses += (not g1) and (not g2)
    flips = n - wins - losses
    return {
        "first_slot_rate": a_picks / (2 * n),
        "good_first": good_first / n,
        "good_second": good_second / n,
        "strict_win": wins / n,
        "strict_loss": losses / n,
        "consistent": (wins + losses) / n,
        "swap_score": (wins + 0.5 * flips) / n,
    }


# ----------------------------------------------------------------------------- milestone 4

def pad_answer(answer, extra_words):
    """Append harmless filler: PAD_SENTENCE repeated ceil(extra_words / 6) times, joined by single
    spaces after the original answer. extra_words <= 0 returns the answer unchanged."""
    if extra_words <= 0:
        return answer
    reps = math.ceil(extra_words / len(PAD_SENTENCE.split()))
    return answer + (" " + PAD_SENTENCE) * reps


def padding_probe(items, judge=judge_single, extra_words=80):
    """Does padding an answer with fluff change the judge's verdict? (No human labels needed.)

    Judge every item as it is, and again with pad_answer(answer, extra_words). Return:
      n_fail, n_pass          how many items the judge failed / passed before padding
      fail_to_pass            share of the n_fail items that the padded version passes
      pass_to_fail            share of the n_pass items that the padded version fails
    A share over zero items is None.
    """
    nf = npass = f2p = p2f = 0
    for it in items:
        before = judge(it["question"], it["answer"])
        after = judge(it["question"], pad_answer(it["answer"], extra_words))
        if before == FAIL:
            nf += 1
            f2p += after == PASS
        else:
            npass += 1
            p2f += after == FAIL
    return {"n_fail": nf, "n_pass": npass,
            "fail_to_pass": f2p / nf if nf else None,
            "pass_to_fail": p2f / npass if npass else None}


# ----------------------------------------------------------------------------- milestone 5

def rogan_gladen(observed, tpr, tnr):
    """The true pass rate implied by the judge's observed pass rate, given its TPR and TNR:
        p = (observed + tnr - 1) / (tpr + tnr - 1)
    Clip the result to [0, 1]. If tpr + tnr - 1 <= 0 the judge is no better than a coin and the
    correction is meaningless: raise ValueError."""
    j = tpr + tnr - 1
    if j <= 0:
        raise ValueError(f"TPR + TNR - 1 = {j:.3f}: the judge has no discriminating power")
    return min(1.0, max(0.0, (observed + tnr - 1) / j))


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
    cm = confusion(human, judged)
    r = rates(cm)
    observed = sum(v == PASS for v in prod_judged) / len(prod_judged)
    return {"observed": observed, "tpr": r["tpr"], "tnr": r["tnr"],
            "corrected": rogan_gladen(observed, r["tpr"], r["tnr"])}


def corrected_ci(human, judged, prod_judged, B=2000, alpha=0.05, seed=0):
    """Bootstrap interval for the corrected pass rate, resampling BOTH data sets.

    Each of the B repetitions: resample the calibration pairs (human, judged) with replacement
    (same count) to get a new TPR and TNR; resample prod_judged with replacement (same count) to get a
    new observed rate; apply rogan_gladen. Skip a repetition (it does not count towards B's
    percentile positions) if a class is missing or tpr + tnr - 1 <= 0. Use random.Random(seed).
    Sort the kept estimates xs; return (xs[int(alpha / 2 * m)], xs[int((1 - alpha / 2) * m) - 1])
    with m = len(xs).
    """
    rng = random.Random(seed)
    cal = list(zip(human, judged))
    n_cal, n_prod = len(cal), len(prod_judged)
    prod_pass = [v == PASS for v in prod_judged]
    xs = []
    for _ in range(B):
        r = _tpr_tnr([cal[rng.randrange(n_cal)] for _ in range(n_cal)])
        obs = sum(prod_pass[rng.randrange(n_prod)] for _ in range(n_prod)) / n_prod
        if r is None or r[0] + r[1] - 1 <= 0:
            continue
        xs.append(rogan_gladen(obs, *r))
    xs.sort()
    m = len(xs)
    return xs[int(alpha / 2 * m)], xs[int((1 - alpha / 2) * m) - 1]
