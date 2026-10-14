"""Lab 1: from a customer brief to an evaluation kit.

The brief: a regional insurer wants an assistant that reads a first notice of loss
(an email, a scanned form, a phone note or an adjuster's report) and proposes one of
three decisions: `covered`, `not_covered` or `refer` (send to a specialist). The
people who decide are the insurer's senior claims panel. You have a pool of 304
real-looking (synthetic) documents that two handlers each labelled on their own, with
a senior adjudicator settling the disagreements, and the predictions of three systems
on every document: the proposed `model`, the `current_process` (first-line handlers
under normal conditions) and a trivial `keyword_rule`.

What you build is the kit the chapter on evaluation plans describes: a clean,
stratified, sealed gold set, labels whose agreement you have measured, the metrics
the customer agreed to, a three-outcome acceptance rule on intervals, a paired
comparison with the current process, and an audit that catches a flawed kit.

What is GIVEN: constants, data loaders, `shingles`, `stratum_of`, `build_kit` and the
agreed `SPEC`. What YOU write is marked TODO:

    1  wilson, cases_needed
    2  jaccard, dedupe, stratified_sample
    3  split_dev_test, cohens_kappa, adjudicate
    4  confusion, score, slice_report
    5  verdict, paired_compare, non_inferior
    6  audit_kit, decide

`python3 check.py` runs the milestones; the lab page explains each one.
"""
import json
import math
import os
import random
import re

HERE = os.path.dirname(os.path.abspath(__file__))

LABELS = ["covered", "not_covered", "refer"]

# Cost in euros of each (gold decision, system decision) pair. ILLUSTRATIVE
# assumptions, in the way a real plan would carry the customer's own estimates.
COST = {
    "covered":     {"covered": 0,    "not_covered": 350,  "refer": 40},    # wrongly denied: complaint + rework
    "not_covered": {"covered": 1800, "not_covered": 0,    "refer": 40},    # wrongly paid: money out the door
    "refer":       {"covered": 1800, "not_covered": 600,  "refer": 0},     # skipped a case needing a specialist
}

# The acceptance spec both sides signed BEFORE anyone ran the model.
SPEC = {
    "accuracy_bar": 0.80,        # lower end of the 95% interval must reach this to accept
    "critical_limit": 0.06,      # wrongly approved claims (gold not_covered/refer, system covered), upper end must stay under
    "baseline": "current_process",
    "margin": 0.05,              # non-inferiority margin against the baseline, in accuracy points
    "rule": "interval",          # "interval" (accept on the interval) or "point" (accept on the point estimate)
    "half_width": 0.08,          # the precision the plan promised: +/- 8 points at 90% accuracy
    "min_slice_n": 15,           # a slice with fewer test cases is not reported on its own
    "min_kappa": 0.60,           # labellers must agree at least this well (chance-corrected)
    "dedupe_threshold": 0.70,    # shingle Jaccard at or above this means "the same document"
    "slice_key": "doc_type",
}

# How many of each stratum the gold set should hold (stratum = "<doc_type>/<ordinary|worry>").
QUOTAS = {
    "email/ordinary": 40, "email/worry": 20,
    "scanned_form/ordinary": 24, "scanned_form/worry": 10,
    "phone_note/ordinary": 28, "phone_note/worry": 12,
    "adjuster_report/ordinary": 24, "adjuster_report/worry": 10,
}
SEED = 2026
TEST_FRACTION = 0.5


# =============================================================================
# GIVEN: data loaders, text helpers and the pipeline that chains your functions
# =============================================================================
def load_pool():
    """The labelled pool: id, doc_type, month, worry (an expert flagged it as worrying), text,
    label_a, label_b, and label_adj (set only where label_a != label_b)."""
    with open(os.path.join(HERE, "pool.jsonl")) as f:
        return [json.loads(line) for line in f]


def load_predictions():
    """{system name: {doc id: decision}} for 'model', 'current_process', 'keyword_rule'."""
    with open(os.path.join(HERE, "predictions.json")) as f:
        return json.load(f)


def shingles(text, k=3):
    """The set of word k-grams of a text (lower-case, letters and digits only)."""
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {tuple(words[i:i + k]) for i in range(max(1, len(words) - k + 1))}


def stratum_of(doc):
    """The stratum a document belongs to: its type, and whether an expert flagged it as worrying."""
    return f"{doc['doc_type']}/{'worry' if doc['worry'] else 'ordinary'}"


# =============================================================================
# Milestone 1: how much can a number from n cases be trusted?
# =============================================================================
def wilson(k, n, z=1.96):
    """Wilson score interval (lo, hi) for k successes in n trials.

    wilson(14, 16) -> (0.640..., 0.965...);  n == 0 -> (0.0, 1.0).
    """
    if n == 0:
        return 0.0, 1.0
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, centre - half), min(1.0, centre + half)


def cases_needed(half_width, p=0.9, z=1.96):
    """Cases needed for a 95% interval of +/- half_width around an accuracy near p.

    ceil(z^2 p (1-p) / half_width^2):  cases_needed(0.03) -> 385.
    """
    return math.ceil(z * z * p * (1 - p) / (half_width * half_width))


# =============================================================================
# Milestone 2: clean the pool, then sample it by stratum
# =============================================================================
def jaccard(a, b):
    """|a & b| / |a | b| for two sets; two empty sets count as identical (1.0)."""
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


def dedupe(docs, threshold=0.70):
    """Drop near-duplicates. Walk the documents in id order and keep one only if its
    shingle Jaccard with EVERY document already kept is below `threshold`.
    Returns the kept documents sorted by id; the input list is not modified."""
    kept, kept_sh = [], []
    for d in sorted(docs, key=lambda d: d["id"]):
        s = shingles(d["text"])
        if all(jaccard(s, t) < threshold for t in kept_sh):
            kept.append(d)
            kept_sh.append(s)
    return kept


def stratified_sample(docs, quotas, seed):
    """Sample `quotas[stratum]` documents from each stratum (see stratum_of).

    Determinism contract (so two people get the same set): work through strata in sorted
    name order; inside a stratum sort the members by id, then draw
    random.Random(seed).sample(members, k) with ONE generator shared across strata.
    A quota larger than the stratum takes the whole stratum. Documents in strata with
    no quota are left out. Returns the sample sorted by id."""
    by = {}
    for d in docs:
        by.setdefault(stratum_of(d), []).append(d)
    rng = random.Random(seed)
    out = []
    for name in sorted(quotas):
        members = sorted(by.get(name, []), key=lambda d: d["id"])
        out += rng.sample(members, min(quotas[name], len(members)))
    return sorted(out, key=lambda d: d["id"])


# =============================================================================
# Milestone 3: seal a test half, measure label agreement, settle disagreements
# =============================================================================
def split_dev_test(items, test_fraction, seed):
    """Split into (dev, test), stratified, so that both halves keep the mix.

    For each stratum (sorted by name): sort members by id, shuffle a copy with the shared
    random.Random(seed), and give the first n_test to the test half, where
    n_test = int(len(members) * test_fraction + 0.5), forced into 1 .. len-1 when the
    stratum has 2 or more members (a stratum of 1 goes to dev). Both lists sorted by id."""
    by = {}
    for d in items:
        by.setdefault(stratum_of(d), []).append(d)
    rng = random.Random(seed)
    dev, test = [], []
    for name in sorted(by):
        members = sorted(by[name], key=lambda d: d["id"])
        rng.shuffle(members)
        n_test = int(len(members) * test_fraction + 0.5)
        if len(members) >= 2:
            n_test = min(max(n_test, 1), len(members) - 1)
        else:
            n_test = 0
        test += members[:n_test]
        dev += members[n_test:]
    return sorted(dev, key=lambda d: d["id"]), sorted(test, key=lambda d: d["id"])


def cohens_kappa(a, b):
    """Cohen's kappa for two equal-length label lists: (po - pe) / (1 - pe), where po is the
    observed agreement and pe the agreement expected if each labeller kept their own label
    frequencies but chose independently. If pe == 1 (both always say the same single label)
    return 1.0. Raise ValueError for empty or unequal lists."""
    if not a or len(a) != len(b):
        raise ValueError("kappa needs two equal-length, non-empty label lists")
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    pe = sum((a.count(l) / n) * (b.count(l) / n) for l in set(a) | set(b))
    if pe == 1:
        return 1.0
    return (po - pe) / (1 - pe)


def adjudicate(rows):
    """Final labels from two independent labellers plus an adjudicator.

    Each row has label_a, label_b and label_adj. If a == b the final label is that label.
    If they differ, the final label is label_adj; a disagreement with label_adj None raises
    ValueError('<id> needs adjudication'). Returns (final, log): final maps id -> label, and
    log lists one dict {id, a, b, final} per disagreement, in input order."""
    final, log = {}, []
    for r in rows:
        if r["label_a"] == r["label_b"]:
            final[r["id"]] = r["label_a"]
        else:
            if r.get("label_adj") is None:
                raise ValueError(f"{r['id']} needs adjudication")
            final[r["id"]] = r["label_adj"]
            log.append({"id": r["id"], "a": r["label_a"], "b": r["label_b"], "final": r["label_adj"]})
    return final, log


# =============================================================================
# GIVEN: the pipeline from pool to kit (it chains milestones 2 and 3)
# =============================================================================
def build_kit(seed=SEED):
    """Pool -> dedupe -> stratified sample -> adjudicated labels -> sealed split -> kit."""
    pool = load_pool()
    clean = dedupe(pool, SPEC["dedupe_threshold"])
    gold_docs = stratified_sample(clean, QUOTAS, seed)
    final, log = adjudicate(gold_docs)
    dev, test = split_dev_test(gold_docs, TEST_FRACTION, seed)
    kappa = cohens_kappa([d["label_a"] for d in gold_docs], [d["label_b"] for d in gold_docs])
    return {"pool_size": len(pool), "clean_size": len(clean), "dev": dev, "test": test,
            "gold": final, "disagreements": log, "kappa": kappa, "spec": SPEC}


# =============================================================================
# Milestone 4: the metrics the customer agreed to
# =============================================================================
def confusion(gold, pred):
    """Nested counts m[gold_label][pred_label] over parallel lists, every cell present (0 if unseen),
    for the three LABELS."""
    m = {g: {p: 0 for p in LABELS} for g in LABELS}
    for g, p in zip(gold, pred):
        m[g][p] += 1
    return m


def score(gold, pred, costs=COST):
    """Score parallel lists of decisions against gold labels.

    Returns {n, correct, accuracy, critical, critical_rate, cost_per_case}.
    A critical error is a wrongly approved claim: gold 'not_covered' or 'refer' but the
    system said 'covered'. critical_rate is critical / n. cost_per_case is the mean of
    costs[gold][pred]. An empty list raises ValueError."""
    if not gold or len(gold) != len(pred):
        raise ValueError("score needs two equal-length, non-empty lists")
    n = len(gold)
    correct = sum(g == p for g, p in zip(gold, pred))
    critical = sum(g != "covered" and p == "covered" for g, p in zip(gold, pred))
    cost = sum(costs[g][p] for g, p in zip(gold, pred))
    return {"n": n, "correct": correct, "accuracy": correct / n, "critical": critical,
            "critical_rate": critical / n, "cost_per_case": cost / n}


def slice_report(docs, gold, pred, key, min_n):
    """Accuracy per slice. `docs` are documents, `gold` and `pred` map id -> decision.

    Returns {slice value: {n, correct, accuracy, lo, hi, reportable}} where lo, hi is the 95%
    Wilson interval and reportable is n >= min_n. The slice value is doc[key]."""
    groups = {}
    for d in docs:
        groups.setdefault(d[key], []).append(d["id"])
    out = {}
    for name, ids in groups.items():
        n = len(ids)
        k = sum(gold[i] == pred[i] for i in ids)
        lo, hi = wilson(k, n)
        out[name] = {"n": n, "correct": k, "accuracy": k / n, "lo": lo, "hi": hi, "reportable": n >= min_n}
    return out


# =============================================================================
# Milestone 5: from numbers to a verdict
# =============================================================================
def verdict(k, n, threshold, direction="min", z=1.96):
    """Three-outcome rule on the Wilson interval of k/n.

    direction 'min' (a bar to reach, such as accuracy): 'accept' if lo >= threshold,
    'reject' if hi < threshold, otherwise 'inconclusive'.
    direction 'max' (a limit not to exceed, such as the critical-error rate): 'accept' if
    hi <= threshold, 'reject' if lo > threshold, otherwise 'inconclusive'."""
    lo, hi = wilson(k, n, z)
    if direction == "min":
        return "accept" if lo >= threshold else "reject" if hi < threshold else "inconclusive"
    if direction == "max":
        return "accept" if hi <= threshold else "reject" if lo > threshold else "inconclusive"
    raise ValueError("direction must be 'min' or 'max'")


def paired_compare(a_ok, b_ok, z=1.96):
    """Compare system A with system B on the SAME items. a_ok and b_ok are parallel lists of
    booleans (was each system right on that item).

    Returns {n, both, a_only, b_only, neither, diff, lo, hi, p_sign}:
      diff = (a_only - b_only) / n, the accuracy gap A - B;
      (lo, hi) = diff -/+ z * se, with se = sqrt(a_only + b_only - (a_only - b_only)^2 / n) / n;
      p_sign = exact two-sided sign test on the disagreements (1.0 if there are none):
               min(1, 2 * P(X >= max(a_only, b_only))) for X ~ Binomial(a_only + b_only, 1/2)."""
    n = len(a_ok)
    both = sum(a and b for a, b in zip(a_ok, b_ok))
    a_only = sum(a and not b for a, b in zip(a_ok, b_ok))
    b_only = sum(b and not a for a, b in zip(a_ok, b_ok))
    neither = n - both - a_only - b_only
    diff = (a_only - b_only) / n
    se = math.sqrt(max(0.0, a_only + b_only - (a_only - b_only) ** 2 / n)) / n
    d = a_only + b_only
    if d == 0:
        p = 1.0
    else:
        k = max(a_only, b_only)
        p = min(1.0, 2 * sum(math.comb(d, i) for i in range(k, d + 1)) / 2 ** d)
    return {"n": n, "both": both, "a_only": a_only, "b_only": b_only, "neither": neither,
            "diff": diff, "lo": diff - z * se, "hi": diff + z * se, "p_sign": p}


def non_inferior(cmp, margin):
    """'accept' if the paired interval's low end is above -margin (no worse than the baseline by
    more than the margin), 'reject' if its high end is below -margin (clearly worse by more than the
    margin), otherwise 'inconclusive'. `cmp` is the dict from paired_compare."""
    if cmp["lo"] > -margin:
        return "accept"
    if cmp["hi"] < -margin:
        return "reject"
    return "inconclusive"


# =============================================================================
# Milestone 6: audit the kit, then decide
# =============================================================================
def audit_kit(kit):
    """Return a sorted list of problem codes found in a kit (an empty list means it passes).

    kit has dev and test (lists of documents), kappa and spec (like SPEC). Codes:
      'overlap'        a document id appears in both dev and test
      'leak'           a dev and a test document have shingle Jaccard >= spec['dedupe_threshold']
      'low_kappa'      kappa < spec['min_kappa']
      'underpowered'   len(test) < cases_needed(spec['half_width'])
      'small_slice:X'  the test half has fewer than spec['min_slice_n'] documents with
                       doc[spec['slice_key']] == X   (one code per such slice X)
      'point_rule'     spec['rule'] is not 'interval'
      'no_baseline'    spec has no 'baseline'
      'no_critical'    spec has no 'critical_limit'"""
    spec, dev, test = kit["spec"], kit["dev"], kit["test"]
    problems = []
    dev_ids = {d["id"] for d in dev}
    if any(d["id"] in dev_ids for d in test):
        problems.append("overlap")
    dev_sh = [shingles(d["text"]) for d in dev]
    thr = spec.get("dedupe_threshold", 0.70)
    if any(jaccard(shingles(t["text"]), s) >= thr for t in test for s in dev_sh):
        problems.append("leak")
    if kit["kappa"] < spec["min_kappa"]:
        problems.append("low_kappa")
    if len(test) < cases_needed(spec["half_width"]):
        problems.append("underpowered")
    counts = {}
    for d in test:
        counts[d[spec["slice_key"]]] = counts.get(d[spec["slice_key"]], 0) + 1
    problems += [f"small_slice:{name}" for name, c in counts.items() if c < spec["min_slice_n"]]
    if spec.get("rule") != "interval":
        problems.append("point_rule")
    if not spec.get("baseline"):
        problems.append("no_baseline")
    if "critical_limit" not in spec:
        problems.append("no_critical")
    return sorted(problems)


def decide(ids, gold, model, baseline, spec):
    """Run the signed plan on the sealed test items `ids`.

    gold, model and baseline map id -> decision. Returns {gates, overall, model, baseline, compare}:
      gates['accuracy']  verdict(correct, n, spec['accuracy_bar'], 'min')
      gates['critical']  verdict(critical, n, spec['critical_limit'], 'max')
      gates['baseline']  non_inferior(paired_compare(model right, baseline right), spec['margin'])
      overall            'reject' if any gate rejects, else 'accept' if all accept, else 'inconclusive'
      model, baseline    the score() dicts;   compare   the paired_compare dict."""
    g = [gold[i] for i in ids]
    m = score(g, [model[i] for i in ids])
    b = score(g, [baseline[i] for i in ids])
    cmp = paired_compare([model[i] == gold[i] for i in ids], [baseline[i] == gold[i] for i in ids])
    gates = {
        "accuracy": verdict(m["correct"], m["n"], spec["accuracy_bar"], "min"),
        "critical": verdict(m["critical"], m["n"], spec["critical_limit"], "max"),
        "baseline": non_inferior(cmp, spec["margin"]),
    }
    if "reject" in gates.values():
        overall = "reject"
    elif all(v == "accept" for v in gates.values()):
        overall = "accept"
    else:
        overall = "inconclusive"
    return {"gates": gates, "overall": overall, "model": m, "baseline": b, "compare": cmp}
