"""Self-check for Lab 5: Citation Checking & Abstention.

    python3 check.py                  # checks your starter.py
    python3 check.py solution         # checks the reference solution
    python3 check.py solution 3       # only milestone 3
    python3 check.py solution 1 7     # milestone 1, replaying ONLY the random cases of seed 7

Everything is synthetic and seeded: the handbook, the questions, the stand-in assistant's answers and its
confidence. There is no network and no real model, so every run gives identical numbers and the whole check
finishes in a couple of seconds. Prints a tick, a cross, or "not implemented yet" for each milestone.
"""
import importlib
import math
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True

args = sys.argv[1:]
target = args[0] if args and not args[0].isdigit() else "starter"
rest = [a for a in args if a.isdigit()]
ONLY = int(rest[0]) if rest else None
ONLY_SEED = int(rest[1]) if len(rest) > 1 else None
mod = importlib.import_module(target)
import data as D  # noqa: E402

results = []
CORPUS = D.CORPUS
DEV, CAL, TEST = D.dev_set(), D.calibration_set(), D.test_set()


def seeds(default):
    return [ONLY_SEED] if ONLY_SEED is not None else list(default)


def check(number, name, fn):
    if ONLY is not None and ONLY != number:
        return
    try:
        note = fn()
        print(f"  ✔ {name}")
        for line in (note or "").splitlines():
            print(f"      {line}")
        results.append(True)
    except NotImplementedError as e:
        print(f"  … {name}: not implemented yet ({e})")
        results.append(False)
    except AssertionError as e:
        print(f"  ✘ {name}: {e}")
        results.append(False)
    except Exception as e:
        import traceback
        tb = traceback.extract_tb(e.__traceback__)
        where = next((f"{f.name}() line {f.lineno}" for f in reversed(tb) if f.filename.endswith(f"{target}.py")), "?")
        print(f"  ✘ {name}: {type(e).__name__}: {e}   [in {where}]")
        results.append(False)


def near(a, b, tol=1e-9):
    return abs(a - b) <= tol


# =============================================================================
# Milestone 1: do the quoted words exist?
# =============================================================================
PASSAGE = ("Marlow Pool has capacity for 300 visitors. Adult entry to Marlow Pool costs 14 pounds. "
           "Marlow Pool closes at 9 pm on weekdays.")


def m1():
    n, ix = mod.normalise_with_map("Hi  There")
    assert n == "hi there" and list(ix) == [0, 1, 2, 4, 5, 6, 7, 8], (
        f'normalise_with_map("Hi  There") should give ("hi there", [0, 1, 2, 4, 5, 6, 7, 8]): lower-case, and the double space '
        f"collapsed to ONE space whose offset is that of the first space (2). Got ({n!r}, {list(ix)})")
    n, ix = mod.normalise_with_map("  x \n\t y")
    assert n == " x y" and list(ix) == [0, 2, 3, 7], f'whitespace runs (spaces, newlines, tabs) collapse to one space, nothing is stripped: expected (" x y", [0, 2, 3, 7]), got ({n!r}, {list(ix)})'
    n, ix = mod.normalise_with_map("It’s a “flat”–rate fee")
    assert n == "it's a \"flat\"-rate fee", f"curly quotes, en dash and the non-breaking space must be replaced by plain ones: got {n!r}"
    assert len(ix) == len(n) and list(ix) == sorted(ix), "idx has one offset per character of norm, in increasing order"
    assert mod.normalise_with_map("") == ("", []) or (mod.normalise_with_map("")[0] == "" and list(mod.normalise_with_map("")[1]) == []), "empty text"

    # --- verify_quote on hand-worked cases
    def span(q, p=PASSAGE):
        got = mod.verify_quote(q, p)
        return None if got is None else tuple(got)

    q = "capacity for 300 visitors"
    s = PASSAGE.index(q)
    assert span(q) == (s, s + len(q)), f"an exact quotation: expected {(s, s + len(q))}, got {span(q)}"
    assert span(q + ".") == (s, s + len(q) + 1), "the full stop is part of the passage, so a quotation that includes it ends one later"
    assert span("CAPACITY  for 300\nvisitors") == (s, s + len(q)), "case and whitespace differences are ignored, and the span is in ORIGINAL offsets"
    assert span("Adult entry to Marlow Pool costs 14 pounds.") == (PASSAGE.index("Adult"), PASSAGE.index("14 pounds.") + 10), "a whole sentence"
    a, b = PASSAGE.index("Adult entry"), PASSAGE.index("14 pounds") + len("14 pounds")
    assert span("Adult entry ... costs 14 pounds") == (a, b), "'...' means words were left out: the span runs from the first fragment to the last"
    assert span("Adult entry … costs 14 pounds") == (a, b), "the single character '…' means the same as '...'"
    assert span("costs 14 pounds ... Adult entry to Marlow") is None, "fragments must appear in order"
    assert span("Marlow Pool has capacity ... Marlow Pool has capacity") is None, "a later fragment must come AFTER the previous one: the same words cannot be used twice"
    assert span("capacity for 301 visitors") is None and span("capacity for 300 guests") is None, "one changed word or figure and it is not a quotation"
    assert span("") is None and span(" ... ") is None, "an empty quotation proves nothing"
    assert span("14 pounds") is None, f"a quotation of fewer than {mod.MIN_QUOTE_CHARS} characters in total proves nothing (a short phrase occurs by chance); '14 pounds' is {len('14 pounds')}"
    p2 = "St Anne’s Hall opened in 1969 – the same year as the library."
    got = span("anne's hall opened in 1969 - the same year", p2)
    assert got == (p2.index("Anne"), p2.index("year") + 4), f"curly apostrophes and dashes match their plain forms: expected {(p2.index('Anne'), p2.index('year') + 4)}, got {got}"

    # --- check_citation
    corp = {"D01": PASSAGE}
    assert mod.check_citation({"doc": "D01", "quote": "capacity for 300 visitors"}, corp) == "ok"
    assert mod.check_citation({"doc": "D01", "quote": "capacity for 400 visitors"}, corp) == "quote_not_found"
    assert mod.check_citation({"doc": "D99", "quote": "capacity for 300 visitors"}, corp) == "no_such_source", "an unknown document id: no_such_source, whatever the quotation"
    assert mod.check_citation({"doc": "d01", "quote": "capacity for 300 visitors"}, corp) == "no_such_source", "document ids match exactly"

    # --- random property: any mangled substring of a passage is found, and the span normalises to it
    for seed in seeds((1, 2, 3)):
        rng = random.Random(seed)
        for _ in range(60):
            text = rng.choice(list(CORPUS.values()))
            words = text.split(" ")
            i = rng.randrange(0, len(words) - 3)
            j = rng.randrange(i + 3, len(words) + 1)
            quote = " ".join(words[i:j])
            if len(quote) < mod.MIN_QUOTE_CHARS:
                continue
            mangled = "".join(c.upper() if rng.random() < 0.3 else c.lower() for c in quote).replace(" ", rng.choice([" ", "  ", " \n"]))
            got = mod.verify_quote(mangled, text)
            assert got is not None, f"seed {seed}: {mangled!r} is a (messy) substring of the passage {text!r} but verify_quote returned None"
            st, en = got
            assert " ".join(text[st:en].lower().split()) == " ".join(mangled.lower().split()), (
                f"seed {seed}: the span {got} of the passage is {text[st:en]!r}, which is not the quotation {mangled!r}")
            broken = quote.replace(rng.choice(words[i:j]), "zzyx", 1)
            if " ".join(broken.lower().split()) not in " ".join(text.lower().split()):
                assert mod.verify_quote(broken, text) is None, f"seed {seed}: {broken!r} is not in the passage but verify_quote accepted it"

    # --- the generated answers: every citation's status must match what the generator planted
    tally = {"ok": 0, "quote_not_found": 0, "no_such_source": 0}
    for a in DEV:
        for st in a["statements"]:
            for c, want in zip(st["cites"], st["cite_status"]):
                got = mod.check_citation(c, CORPUS)
                assert got == want, (f"answer {a['id']}: citation {c} should be {want!r}, got {got!r}"
                                     + (" (the quotation is real; look at how you map offsets, case, quotes or the ellipsis)" if want == "ok" else ""))
                tally[want] += 1
    return (f"dev set, {sum(tally.values())} citations: {tally['ok']} ok, {tally['quote_not_found']} quotation not in the document, "
            f"{tally['no_such_source']} document does not exist")


# =============================================================================
# Milestone 2: does the cited text support the claim?
# =============================================================================
def oracle_judge(claim, passages):
    """An independent, deliberately plain re-implementation of the judge rules, for cross-checking."""
    cw = set(mod.words_of(claim))
    sents = [s for p in passages for s in mod.split_sentences(p)]
    if not sents:
        return "NOT_ENOUGH_INFO", 0.0, ""
    scored = [((len(cw & set(mod.words_of(s))) / len(cw)) if cw else 0.0, s) for s in sents]
    top = max(sc for sc, _ in scored)
    best = next(s for sc, s in scored if sc == top)
    if top < mod.MIN_OVERLAP:
        return "NOT_ENOUGH_INFO", top, best
    if mod.has_negation(best) != mod.has_negation(claim):
        return "CONTRADICTED", top, best
    cn = mod.numbers_of(claim)
    if cn and not cn.issubset(mod.numbers_of(best)):
        return "CONTRADICTED", top, best
    return "SUPPORTED", top, best


def m2():
    P = [PASSAGE]
    V = mod.judge_claim("Marlow Pool can hold 300 visitors.", P)
    assert (V.label, V.sentence) == ("SUPPORTED", "Marlow Pool has capacity for 300 visitors."), f"'can hold' means 'capacity' (see canon): expected SUPPORTED on the first sentence, got {tuple(V)}"
    assert near(V.score, 1.0), f"all four content words of the claim occur in the sentence: score 1.0, got {V.score}"
    V = mod.judge_claim("Marlow Pool can hold 250 visitors.", P)
    assert V.label == "CONTRADICTED", f"same words, a different number: CONTRADICTED, got {V.label}"
    V = mod.judge_claim("Adult entry to Marlow Pool costs 14 pounds.", P)
    assert V.label == "SUPPORTED" and V.sentence.startswith("Adult entry"), f"got {tuple(V)}"
    V = mod.judge_claim("Marlow Pool has 40 car parking spaces.", P)
    assert V.label == "NOT_ENOUGH_INFO" and near(V.score, 0.4) and V.sentence == "Marlow Pool has capacity for 300 visitors.", (
        f"2 of 5 content words (marlow, pool) match: overlap 0.4 < {mod.MIN_OVERLAP}, NOT_ENOUGH_INFO; on a tie the FIRST best sentence wins. Got {tuple(V)}")
    N = ["The pool is not open on Sundays."]
    assert mod.judge_claim("The pool is open on Sundays.", N).label == "CONTRADICTED", "the evidence has a negation the claim lacks: CONTRADICTED"
    assert mod.judge_claim("The pool is not open on Sundays.", N).label == "SUPPORTED"
    V = mod.judge_claim("Alpha beta gamma delta epsilon.", ["Alpha beta gamma zeta eta."])
    assert V.label == "SUPPORTED" and near(V.score, 0.6), f"3 of 5 words is exactly the threshold 0.6, and the threshold is inclusive: got {tuple(V)}"
    V = mod.judge_claim("Alpha beta gamma delta epsilon.", ["Alpha beta zeta eta theta."])
    assert V.label == "NOT_ENOUGH_INFO" and near(V.score, 0.4), f"got {tuple(V)}"
    V = mod.judge_claim("The site employs 3,200 people.", ["The site employs 3200 people, of whom 1100 work in Leeds."])
    assert V.label == "SUPPORTED", f"3,200 and 3200 are the same number (numbers_of removes commas): got {V.label}"
    V = mod.judge_claim("Marlow Pool opened.", [])
    assert tuple(V) == ("NOT_ENOUGH_INFO", 0.0, ""), f"no passages at all: NOT_ENOUGH_INFO, score 0.0, empty sentence; got {tuple(V)}"
    V = mod.judge_claim("Marlow Pool closes at 9 pm on weekdays.", ["Nothing relevant here.", PASSAGE])
    assert V.label == "SUPPORTED" and V.sentence.startswith("Marlow Pool closes"), "sentences of ALL the passages compete for best"
    V = mod.judge_claim("the of and", P)
    assert V.label == "NOT_ENOUGH_INFO" and V.score == 0.0, "a claim with no content words has overlap 0.0 (do not divide by zero)"

    # --- evaluate_judge on a stub judge
    stub = lambda claim, passages: mod.Verdict(passages[0], 1.0, "")
    items = [("c1", ["SUPPORTED"], "SUPPORTED"), ("c2", ["SUPPORTED"], "NOT_ENOUGH_INFO"), ("c3", ["CONTRADICTED"], "CONTRADICTED"),
             ("c4", ["NOT_ENOUGH_INFO"], "SUPPORTED"), ("c5", ["SUPPORTED"], "CONTRADICTED"), ("c6", ["SUPPORTED"], "SUPPORTED")]
    r = mod.evaluate_judge(items, stub)
    c = r["confusion"]
    assert c[("SUPPORTED", "SUPPORTED")] == 2 and c[("NOT_ENOUGH_INFO", "SUPPORTED")] == 1 and c[("CONTRADICTED", "SUPPORTED")] == 1 \
        and c[("SUPPORTED", "NOT_ENOUGH_INFO")] == 1 and c[("CONTRADICTED", "CONTRADICTED")] == 1 and c[("SUPPORTED", "CONTRADICTED")] == 0, (
        f"confusion[(gold, predicted)] is wrong: {dict((k, v) for k, v in c.items() if v)}")
    assert len(c) == 9, "the confusion dict has an entry for all 9 (gold, predicted) pairs, zeros included"
    assert near(r["accuracy"], 3 / 6) and near(r["precision"], 2 / 4) and near(r["recall"], 2 / 3), (
        f"accuracy 3/6, precision of SUPPORTED 2/4, recall of SUPPORTED 2/3; got {r['accuracy']:.3f}, {r['precision']:.3f}, {r['recall']:.3f}")
    assert [tuple(x) for x in r["false_support"]] == [("c2", "NOT_ENOUGH_INFO"), ("c5", "CONTRADICTED")], f"false_support in input order: got {r['false_support']}"
    r0 = mod.evaluate_judge([("x", ["CONTRADICTED"], "CONTRADICTED")], stub)
    assert r0["precision"] == 1.0 and r0["recall"] == 1.0, "precision and recall are 1.0 when their denominators are 0"

    # --- the generated claims, against the independent oracle
    def claim_items(answers):
        out = []
        for a in answers:
            for st in a["statements"]:
                texts = [CORPUS[c["doc"]] for c in st["cites"] if c["doc"] in CORPUS]
                if texts:
                    out.append((st["text"], texts, st["gold"]))
        return out

    items = claim_items(DEV) + claim_items(TEST[:200])
    for claim, texts, gold in items:
        want = oracle_judge(claim, texts)
        got = mod.judge_claim(claim, texts)
        assert (got.label, round(got.score, 9)) == (want[0], round(want[1], 9)), (
            f"claim {claim!r}: expected {want[0]} (score {want[1]:.3f}, best sentence {want[2]!r}), got {got.label} (score {got.score:.3f}, "
            f"best sentence {got.sentence!r})")
    r = mod.evaluate_judge(claim_items(DEV))
    c = r["confusion"]
    assert r["precision"] >= 0.9 and r["recall"] >= 0.9, f"dev set: precision {r['precision']:.3f}, recall {r['recall']:.3f} of SUPPORTED"
    assert c[("CONTRADICTED", "SUPPORTED")] == 0, "a changed number must never be judged SUPPORTED"
    lines = ["dev set, rows = gold, columns = predicted:", "                  SUP  CON  NEI"]
    short = {"SUPPORTED": "SUP", "CONTRADICTED": "CON", "NOT_ENOUGH_INFO": "NEI"}
    for g in mod.LABELS:
        lines.append(f"  {g:<16}" + "".join(f"{c[(g, p)]:>5}" for p in mod.LABELS))
    lines.append(f"accuracy {r['accuracy']:.3f}   precision of SUPPORTED {r['precision']:.3f}   recall {r['recall']:.3f}   "
                 f"{len(r['false_support'])} false supports")
    return "\n".join(lines)


# =============================================================================
# Milestone 3: citation recall, precision and a support score per answer
# =============================================================================
CH12 = {"1": "Harbourline Ltd reported revenue of 412 million pounds in 2025, up 8 percent from 2024. Operating profit was 61 million pounds. "
             "The company employs 3,200 people, of whom 1,100 work in Leeds. The board did not recommend a dividend for 2025. "
             "The chief executive, Mara Quince, joined in 2021.",
        "2": "Harbourline opened a second distribution centre in Doncaster in March 2025. The site cost 38 million pounds and has capacity for 90,000 parcels a day."}
CH12_ANSWER = [
    ("Harbourline's revenue was 412 million pounds in 2025.", [("1", "revenue of 412 million pounds")]),
    ("Harbourline operating profit was 61 million pounds.", [("1", "Operating profit was 61 million pounds"), ("2", "capacity for 90,000 parcels")]),
    ("Harbourline paid a dividend of 12 pence.", [("1", "dividend of 12 pence")]),
    ("The Doncaster centre cost 38 million pounds.", [("2", "The site cost 38 million pounds")]),
    ("Harbourline was fined 2 million pounds by a regulator.", [("3", "fined 2 million pounds")]),
    ("Harbourline's chief executive joined in 2021.", []),
]


def as_answer(rows):
    return {"id": "x", "statements": [{"text": t, "cites": [{"doc": d, "quote": q} for d, q in cs]} for t, cs in rows]}


def oracle_report(answers):
    s = c = ex = ok = rec = prec = unc = 0
    for a in answers:
        for st in a["statements"]:
            s += 1
            ids = [x["doc"] for x in st["cites"]]
            unc += not ids
            e = lambda dids: bool([d for d in dids if d in CORPUS]) and mod.judge_claim(st["text"], [CORPUS[d] for d in dids if d in CORPUS]).label == "SUPPORTED"
            r = int(bool(ids) and e(ids))
            rec += r
            for k, x in enumerate(st["cites"]):
                c += 1
                status = mod.check_citation(x, CORPUS)
                ex += status != "no_such_source"
                ok += status == "ok"
                irrelevant = (not e([x["doc"]])) and e(ids[:k] + ids[k + 1:])
                prec += int(r and not irrelevant)
    return dict(existence=ex / c, quotes=ok / c, recall=rec / s, precision=prec / c, uncited=unc / s, statements=s, citations=c)


def m3():
    ans = as_answer(CH12_ANSWER)
    assert mod.entails("Harbourline operating profit was 61 million pounds.", ["1"], CH12) is True
    assert mod.entails("Harbourline operating profit was 61 million pounds.", ["2"], CH12) is False
    assert mod.entails("Harbourline operating profit was 61 million pounds.", ["9", "1"], CH12) is True, "documents that do not exist are ignored"
    assert mod.entails("Harbourline operating profit was 61 million pounds.", ["9"], CH12) is False, "only documents that do not exist: False"
    assert mod.entails("Harbourline operating profit was 61 million pounds.", [], CH12) is False
    res = mod.verify_answer(ans, CH12)
    sts = res["statements"]
    assert len(sts) == 6
    assert [s["recall"] for s in sts] == [1, 1, 0, 1, 0, 0], f"recall per statement should be [1, 1, 0, 1, 0, 0] (the worked example of chapter 12), got {[s['recall'] for s in sts]}"
    s2 = sts[1]
    assert [c["status"] for c in s2["cites"]] == ["ok", "ok"] and [c["alone"] for c in s2["cites"]] == [True, False] \
        and [c["irrelevant"] for c in s2["cites"]] == [False, True], (
        f"statement 2 cites a real quotation from document 2 that is about parcels, not profit: its status is ok, it does not support the statement alone, "
        f"and it is irrelevant because document 1 does. Got {s2['cites']}")
    assert s2["precision"] == [1, 0], f"statement 2: the first citation earns precision 1 and the irrelevant one 0, got {s2['precision']}"
    assert [c["status"] for c in sts[2]["cites"]] == ["quote_not_found"] and sts[2]["precision"] == [0], "the invented quotation"
    assert [c["status"] for c in sts[4]["cites"]] == ["no_such_source"] and sts[4]["cites"][0]["irrelevant"] is False, "a missing source is not 'irrelevant' (nothing else supports the statement)"
    assert sts[5]["cites"] == [] and sts[5]["precision"] == [] and sts[5]["recall"] == 0, "no citations: recall 0, no precision entries"
    assert [round(s["support"], 3) for s in sts] == [0.75, 0.8, 0.0, 0.6, 0.0, 0.0], (
        f"support is the judge's score when every citation is ok AND the cited documents support the statement, else 0.0: expected "
        f"[0.75, 0.8, 0.0, 0.6, 0.0, 0.0], got {[round(s['support'], 3) for s in sts]}")
    assert res["support"] == 0.0, "the answer's support is the minimum over its statements"
    good = as_answer(CH12_ANSWER[:2] + CH12_ANSWER[3:4])
    assert near(mod.verify_answer(good, CH12)["support"], 0.6), "min(0.75, 0.8, 0.6)"
    assert mod.verify_answer({"statements": []}, CH12)["support"] == 0.0, "an answer with no statements has support 0.0"
    rep = mod.citation_report([ans], CH12)
    assert (rep["statements"], rep["citations"]) == (6, 6)
    assert near(rep["existence"], 5 / 6) and near(rep["quotes"], 4 / 6) and near(rep["recall"], 3 / 6) and near(rep["precision"], 3 / 6) and near(rep["uncited"], 1 / 6), (
        f"chapter 12 reports existence 5/6, quotes 4/6, recall 3/6, precision 3/6 and one uncited statement; got existence {rep['existence']:.3f}, "
        f"quotes {rep['quotes']:.3f}, recall {rep['recall']:.3f}, precision {rep['precision']:.3f}, uncited {rep['uncited']:.3f}")
    empty = mod.citation_report([], CH12)
    assert empty["existence"] == 1.0 and empty["precision"] == 1.0 and empty["uncited"] == 0.0 and empty["statements"] == 0, "nothing to check: rates are 1.0 (uncited 0.0)"

    # --- dev and test sets against an independent count
    for name, answers in (("dev", DEV), ("test", TEST)):
        want, got = oracle_report(answers), mod.citation_report(answers, CORPUS)
        for k in want:
            assert near(got[k], want[k], 1e-9), f"{name} set: {k} should be {want[k]:.4f}, got {got[k]:.4f}"
    for a in DEV[:40]:
        r = mod.verify_answer(a, CORPUS)
        assert 0.0 <= r["support"] <= 1.0
        if any(c["status"] != "ok" for s in r["statements"] for c in s["cites"]):
            assert r["support"] == 0.0, f"answer {a['id']} has a citation that is not ok, so its support must be 0.0"
    # the support gate separates good answers from bad ones
    sup = [(mod.verify_answer(a, CORPUS)["support"], a["correct"]) for a in TEST]
    with_support = [ok for s, ok in sup if s > 0]
    without = [ok for s, ok in sup if s == 0]
    assert sum(with_support) / len(with_support) >= 0.9 and sum(without) / len(without) <= 0.2, (
        f"answers with support > 0 should be right ~90% of the time and answers with support 0 wrong ~90% of the time; got "
        f"{sum(with_support) / len(with_support):.2f} right among {len(with_support)} with support, {sum(without) / len(without):.2f} among {len(without)} without")
    rep = mod.citation_report(DEV, CORPUS)
    return (f"chapter 12's six-sentence answer: existence 5/6, quotations 4/6, recall 3/6, precision 3/6, one uncited\n"
            f"dev set ({rep['statements']} statements, {rep['citations']} citations): existence {rep['existence']:.0%}, quotations {rep['quotes']:.0%}, "
            f"recall {rep['recall']:.0%}, precision {rep['precision']:.0%}\n"
            f"test set: {len(with_support)} answers with support > 0 are right {sum(with_support) / len(with_support):.0%} of the time, "
            f"{len(without)} with support 0 are right {sum(without) / len(without):.0%}")


# =============================================================================
# Milestone 4: the risk-coverage curve
# =============================================================================
def m4():
    rows = [(0.9, True), (0.8, True), (0.8, False), (0.5, True), (0.4, False)]
    pts = [tuple(p) for p in mod.risk_coverage(rows)]
    want = [(0.9, 0.2, 0.0), (0.8, 0.6, 1 / 3), (0.5, 0.8, 0.25), (0.4, 1.0, 0.4)]
    assert len(pts) == 4 and all(near(a, b) and near(c, d) and near(e, f) for (a, c, e), (b, d, f) in zip(pts, want)), (
        f"risk_coverage on the hand-worked rows (a tie at 0.8 enters as ONE group): expected {[(t, c, round(r, 4)) for t, c, r in want]}, "
        f"got {[(t, round(c, 4), round(r, 4)) for t, c, r in pts]}")
    assert near(mod.aurc(pts), 0.4 * (1 / 3) + 0.2 * 0.25 + 0.2 * 0.4), f"AURC = sum of (coverage step) x risk = 0.2x0 + 0.4x1/3 + 0.2x0.25 + 0.2x0.4 = 0.2633; got {mod.aurc(pts):.4f}"
    assert mod.risk_coverage([]) == [] and mod.aurc([]) == 0.0
    assert near(mod.max_coverage_at_risk(pts, 0.25), 0.8) and near(mod.max_coverage_at_risk(pts, 0.0), 0.2) \
        and near(mod.max_coverage_at_risk(pts, 0.3), 0.8) and near(mod.max_coverage_at_risk(pts, 1.0), 1.0), (
        "max_coverage_at_risk: the largest coverage whose risk is at most the limit (0.25 -> 0.8, 0.0 -> 0.2, 0.3 -> 0.8, 1.0 -> 1.0)")
    assert mod.max_coverage_at_risk([(0.9, 0.5, 0.2)], 0.1) == 0.0, "no point qualifies: 0.0"
    # constant confidence: nothing to rank, so AURC is the overall error rate
    assert near(mod.aurc(mod.risk_coverage([(0.5, True)] * 3 + [(0.5, False)])), 0.25), "a single tie group: AURC = error rate"

    for seed in seeds((4, 5, 6)):
        rng = random.Random(seed)
        n = rng.randint(30, 120)
        confs = rng.sample(range(1000), n)
        rows = [(c / 1000, rng.random() < c / 1000) for c in confs]       # distinct confidences
        pts = mod.risk_coverage(rows)
        order = sorted(rows, key=lambda r: -r[0])
        risks = [sum(not ok for _, ok in order[:k]) / k for k in range(1, n + 1)]
        assert len(pts) == n and all(near(p[2], r) and near(p[1], (k + 1) / n) for k, (p, r) in enumerate(zip(pts, risks))), f"seed {seed}: distinct confidences give one point per row"
        assert near(mod.aurc(pts), sum(risks) / n), f"seed {seed}: with no ties, AURC is the mean of the risks after each answer"
        cubed = mod.risk_coverage([(c ** 3, ok) for c, ok in rows])
        assert near(mod.aurc(cubed), mod.aurc(pts)), f"seed {seed}: only the RANKING of the confidences matters, not their values"
        m = sum(ok for _, ok in rows)
        perfect = mod.risk_coverage([(1.0 + (0.5 + i / (n + 1) if ok else -i / (n + 1)), ok) for i, (_, ok) in enumerate(rows)])
        assert near(mod.aurc(perfect), mod.oracle_aurc(m, n)), f"seed {seed}: a perfect ranking has the oracle AURC"
        assert all(a[1] < b[1] for a, b in zip(pts, pts[1:])) and all(a[0] > b[0] for a, b in zip(pts, pts[1:])), "coverage rises and thresholds fall along the curve"

    # the two confidence signals of the lab, on the TEST set
    n = len(TEST)
    m = sum(a["correct"] for a in TEST)
    sig = {"self-reported": [(a["self_conf"], a["correct"]) for a in TEST],
           "verifier support": [(mod.verify_answer(a, CORPUS)["support"], a["correct"]) for a in TEST]}
    out = {k: mod.risk_coverage(v) for k, v in sig.items()}
    a_self, a_ver = mod.aurc(out["self-reported"]), mod.aurc(out["verifier support"])
    lo, base = mod.oracle_aurc(m, n), 1 - m / n
    assert lo < a_ver < a_self < base, (f"expected oracle {lo:.3f} < verifier {a_ver:.3f} < self-reported {a_self:.3f} < no-skill {base:.3f}: both signals "
                                         "carry information, and the verifier carries more")
    assert mod.max_coverage_at_risk(out["self-reported"], 0.10) == 0.0, "the assistant's own confidence never reaches 10% risk"
    assert mod.max_coverage_at_risk(out["verifier support"], 0.05) > 0.45, "the verifier can answer about half the questions at under 5% wrong"
    lines = [f"test set: {n} answers, {m} right ({m / n:.1%}); AURC: oracle {lo:.3f}  verifier {a_ver:.3f}  self-reported {a_self:.3f}  no skill {base:.3f}",
             f"{'signal':<17}" + "".join(f"  cov @ risk<={r:.0%}" for r in (0.30, 0.10, 0.05))]
    for k, pts in out.items():
        lines.append(f"{k:<17}" + "".join(f"  {mod.max_coverage_at_risk(pts, r):>14.1%}" for r in (0.30, 0.10, 0.05)))
    return "\n".join(lines)


# =============================================================================
# Milestone 5: where to put the threshold
# =============================================================================
def m5():
    rows = [(0.9, True), (0.8, False), (0.6, True), (0.3, False)]
    assert near(mod.expected_score(rows, 0.6, 2), 0.0) and near(mod.expected_score(rows, 0.85, 2), 0.25) and near(mod.expected_score(rows, 0.0, 1), 0.0) \
        and mod.expected_score(rows, math.inf, 5) == 0.0 and mod.expected_score([], 0.5, 1) == 0.0 and near(mod.expected_score(rows, 0.0, 0), 0.5), (
        "expected_score: +1 right, -penalty wrong, 0 abstained, divided by ALL rows. rows [(.9,T),(.8,F),(.6,T),(.3,F)]: t=.6 penalty 2 -> (1-2+1)/4 = 0; "
        "t=.85 -> 1/4; t=0 penalty 1 -> 0; penalty 0 answering everything -> 2/4")
    t, s = mod.best_threshold(rows, 1)
    assert t == 0.9 and near(s, 0.25), f"penalty 1: t=0.9 and t=0.6 both score 0.25; on a tie take the HIGHER threshold. Got ({t}, {s})"
    t, s = mod.best_threshold(rows, 0)
    assert t == 0.6 and near(s, 0.5), f"penalty 0: t=0.6 and t=0.3 both score 0.5; the higher one wins. Got ({t}, {s})"
    t, s = mod.best_threshold([(0.9, False), (0.5, True)], 3)
    assert t == math.inf and s == 0.0, f"the most confident answer is wrong and any threshold that admits it loses: the best policy answers nothing (threshold math.inf, score 0.0). Got ({t}, {s})"
    t, s = mod.best_threshold([(0.7, True), (0.4, True)], 3)
    assert t == 0.4 and near(s, 1.0), f"every answer right: answer them all (t = the lowest confidence). Got ({t}, {s})"
    assert mod.best_threshold([], 2) == (math.inf, 0.0), "no rows: answer nothing"
    for pen, want in [(0, 0.0), (1, 0.5), (3, 0.75), (9, 0.9)]:
        assert near(mod.theory_threshold(pen), want), f"theory_threshold({pen}) = {pen}/(1+{pen}) = {want}"

    tab = mod.fit_binning([(0.05, True), (0.05, False), (0.95, True), (1.0, True), (0.55, False)])
    want = [0.5, 0.15, 0.25, 0.35, 0.45, 0.0, 0.65, 0.75, 0.85, 1.0]
    assert len(tab) == 10 and all(near(a, b) for a, b in zip(tab, want)), (
        f"fit_binning: bin i holds confidences in [i/10, (i+1)/10), the top bin also takes 1.0; its value is the share correct, or the midpoint if empty. "
        f"Expected {want}, got {[round(x, 3) for x in tab]}")
    assert near(mod.calibrate(0.05, tab), 0.5) and near(mod.calibrate(1.0, tab), 1.0) and near(mod.calibrate(0.5, tab), 0.0) and near(mod.calibrate(0.999, tab), 1.0), \
        "calibrate maps a confidence to its bin's value (1.0 belongs to the top bin)"
    assert len(mod.fit_binning(rows, 4)) == 4 and near(mod.calibrate(0.3, mod.fit_binning(rows, 4)), 0.0), "n_bins is a parameter"

    for seed in seeds((7, 8, 9)):
        rng = random.Random(seed)
        rows = [(round(rng.random(), 2), rng.random() < 0.55) for _ in range(rng.randint(40, 120))]
        for pen in (0, 0.5, 1, 3, 9):
            t, s = mod.best_threshold(rows, pen)
            cands = sorted({c for c, _ in rows}) + [math.inf]
            scores = [mod.expected_score(rows, c, pen) for c in cands]
            assert near(s, max(scores)) and near(mod.expected_score(rows, t, pen), s), f"seed {seed} penalty {pen}: best_threshold returned a policy scoring {s:.4f}, but the best candidate scores {max(scores):.4f}"
            better_or_equal = [c for c, sc in zip(cands, scores) if near(sc, max(scores))]
            assert t == max(better_or_equal), f"seed {seed} penalty {pen}: ties must go to the higher threshold; {max(better_or_equal)} ties with {t}"

    # the lab's scenario: choose on the calibration set, report on the test set
    def sigs(answers):
        return {"self-reported": [(a["self_conf"], a["correct"]) for a in answers],
                "verifier support": [(mod.verify_answer(a, CORPUS)["support"], a["correct"]) for a in answers]}

    cal, tst = sigs(CAL), sigs(TEST)
    table = {}
    lines = [f"{'signal':<17}{'penalty':>8}{'threshold':>11}{'calib':>8}{'test':>8}{'theory t':>10}{'theory on test':>16}{'recalibrated':>14}{'answer all':>12}"]
    for name in cal:
        tab = mod.fit_binning(cal[name])
        for pen in (0, 1, 3, 9):
            t, s_cal = mod.best_threshold(cal[name], pen)
            s_test = mod.expected_score(tst[name], t, pen)
            th = mod.theory_threshold(pen)
            raw = mod.expected_score(tst[name], th, pen)
            recal = mod.expected_score([(mod.calibrate(c, tab), ok) for c, ok in tst[name]], th, pen)
            allv = mod.expected_score(tst[name], -1.0, pen)
            table[(name, pen)] = (t, s_cal, s_test, raw, recal, allv)
            lines.append(f"{name:<17}{pen:>8}{('none' if t == math.inf else f'{t:.3f}'):>11}{s_cal:>+8.3f}{s_test:>+8.3f}{th:>10.2f}{raw:>+16.3f}{recal:>+14.3f}{allv:>+12.3f}")
    for name in cal:
        for pen in (1, 3):
            t, s_cal, s_test, raw, recal, allv = table[(name, pen)]
            assert s_test > allv + 0.1, f"{name}, penalty {pen}: the threshold chosen on the calibration set should beat answering everything on the TEST set by a wide margin ({s_test:+.3f} vs {allv:+.3f})"
            assert s_test >= s_cal - 0.08, f"{name}, penalty {pen}: the test score {s_test:+.3f} is far below the calibration score {s_cal:+.3f}; did you choose the threshold on the test set?"
        assert table[(name, 9)][1] >= 0.0, "abstaining is always available, so the best score can never be negative"
    t3 = table[("verifier support", 3)]
    assert t3[2] > table[("self-reported", 3)][2] + 0.25, "at penalty 3 the verifier's support should be worth far more than the assistant's own confidence"
    assert abs(t3[4] - t3[2]) < 0.04, (f"for the verifier, the formula penalty/(1+penalty) applied to RECALIBRATED confidences should land within 0.04 of the threshold chosen "
                                       f"on the calibration set: {t3[4]:+.3f} vs {t3[2]:+.3f}")
    assert table[("self-reported", 3)][3] < table[("self-reported", 3)][4], "recalibration should help the overconfident self-reported signal when the formula is used"
    return "\n".join(lines)


MILESTONES = [
    (1, "Milestone 1: do the quoted words exist?", m1),
    (2, "Milestone 2: does the cited text support the claim?", m2),
    (3, "Milestone 3: citation recall, precision and a support score", m3),
    (4, "Milestone 4: the risk-coverage curve", m4),
    (5, "Milestone 5: where to put the abstention threshold", m5),
]

if __name__ == "__main__":
    t0 = time.time()
    print(f"Lab 5 checks against {target}.py\n")
    for n, name, fn in MILESTONES:
        check(n, name, fn)
    print(f"\n{sum(results)}/{len(results)} milestones passing  ({time.time() - t0:.1f} s)")
    sys.exit(0 if all(results) else 1)
