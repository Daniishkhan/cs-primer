"""Self-check for Lab 1: A Search Engine with BM25.

    python3 check.py                  # checks your starter.py
    python3 check.py solution         # checks the reference solution
    python3 check.py solution 4       # only milestone 4
    python3 check.py solution 4 3     # milestone 4, replaying ONLY the random corpus of seed 3

Everything is deterministic: a small fixed corpus (corpus.json), the eight documents of
chapter 2, and random corpora built from seeded random.Random generators. No network, no
clock. The whole check finishes in a couple of seconds.
Prints a tick, a cross, or "not implemented yet" for each milestone.
"""
import importlib
import json
import math
import os
import random
import sys
import time
import unicodedata
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True

args = sys.argv[1:]
target = args[0] if args and not args[0].isdigit() else "starter"
rest = [a for a in args if a.isdigit()]
ONLY = int(rest[0]) if rest else None
ONLY_SEED = int(rest[1]) if len(rest) > 1 else None
mod = importlib.import_module(target)
results = []


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


# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------
with open(os.path.join(HERE, "corpus.json"), encoding="utf-8") as fh:
    KB = json.load(fh)

# The eight documents of chapter 2 ("Inverted Indexes & BM25").
CH2 = {
    "d1": "Late payment fees apply when an invoice is paid after the due date. The late payment fee is 2 percent per month.",
    "d2": "To dispute an invoice, contact billing within 30 days. Include the invoice number and a short description of the dispute.",
    "d3": "Our refund policy: refunds are issued to the original payment method. Refunds take 5 to 10 working days.",
    "d4": "Payment methods accepted: credit card, bank transfer and direct debit. Card payment is processed immediately.",
    "d5": ("Annual report. The company reported revenue growth, new products, hiring, office moves, a new brand, partnerships, "
           "sustainability goals, board changes and a long list of other matters. Late in the year a payment platform was "
           "launched. Customers can now pay invoices online. Further detail on payment, tax, audit, risk, governance, "
           "remuneration and the outlook can be found in the notes that follow this summary section of the report."),
    "d6": "Invoice template: invoice number, invoice date, customer, line items, tax, total and payment terms.",
    "d7": "Holiday calendar for staff. Offices are closed on public holidays. Request leave through the HR portal.",
    "d8": "Tax invoice requirements: the invoice must show the supplier tax number, the date and the total tax charged.",
}


def plain(text):
    return mod.analyse(text, fold=True, stop=False, stem=False)


def build(docs, analyser=None):
    ix = mod.Index(analyser) if analyser else mod.Index()
    for d, t in docs.items():
        ix.add(d, t)
    return ix


VOCAB = [f"w{i}" for i in range(1, 31)]
WEIGHTS = [1 / (i + 1) for i in range(30)]          # Zipf-like: w1 is common, w30 is rare


def random_corpus(seed, n_docs=25):
    """{doc_id: text} where text is space-separated words (pair it with str.split)."""
    rng = random.Random(seed)
    docs = {}
    for i in range(n_docs):
        n = rng.choice([0, 1, 2, 5, 8, 12, 20, 40, 40])
        docs[f"d{i:02d}"] = " ".join(rng.choices(VOCAB, WEIGHTS, k=n))
    docs["d98"] = docs["d99"] = "w3 w3 w7 w20"           # identical twins: exact ties
    return docs, rng


def random_query(rng):
    words = rng.choices(VOCAB, WEIGHTS, k=rng.randint(1, 4))
    if rng.random() < 0.3:
        words.append("zzz")                              # unseen term
    if rng.random() < 0.3:
        words.append(words[0])                           # repeated term
    return " ".join(words)


def oracle(docs, query, k1=1.2, b=0.75):
    """BM25 written from scratch and scored document by document (slow and obviously right)."""
    toks = {d: t.split() for d, t in docs.items()}
    n = len(toks)
    avgdl = sum(len(t) for t in toks.values()) / n
    out = {}
    for d, t in toks.items():
        c = Counter(t)
        s = 0.0
        for term in dict.fromkeys(query.split()):
            if c[term]:
                df = sum(1 for u in toks.values() if term in u)
                w = math.log(1 + (n - df + 0.5) / (df + 0.5))
                s += w * c[term] * (k1 + 1) / (c[term] + k1 * (1 - b + b * len(t) / avgdl))
        if s > 0:
            out[d] = s
    return sorted(out.items(), key=lambda kv: (-kv[1], kv[0]))


def same_ranking(got, full, k, label):
    """Compare a top-k list with the oracle's full ranking.

    Scores must agree rank by rank (to 1e-9). A document may stand where the oracle has a
    different one only if the two scores are equal to within 1e-9 (a tie, or a float
    rounding difference between mathematically equal scores). Documents that tie EXACTLY
    must be listed in ascending doc id.
    """
    want = full[:k]
    assert len(got) == len(want), f"{label}: expected {len(want)} results, got {len(got)}: {got}"
    score_of = dict(full)
    for i, ((gd, gs), (wd, ws)) in enumerate(zip(got, want)):
        assert near(gs, ws), f"{label}: rank {i + 1} should score {ws:.6f} ({wd}), got {gs:.6f} ({gd})"
        assert gd in score_of and near(score_of[gd], gs), f"{label}: {gd} does not score {gs:.6f} for this query"
    assert len({d for d, _ in got}) == len(got), f"{label}: a document appears twice"
    for (d1, s1), (d2, s2) in zip(got, got[1:]):
        if s1 == s2:
            assert d1 < d2, f"{label}: {d1} and {d2} tie exactly at {s1:.6f}; ties must be listed in ascending doc id"


# =============================================================================
# Milestone 1: the analyser
# =============================================================================
def m1():
    got = mod.tokenise("Dr. O'Neil's co-op paid $1,250.50 for 3 MacBook-Pro units, e-mail: sales@acme.example (50% off!)")
    want = ["dr", "o'neil", "co-op", "paid", "1", "250.50", "for", "3", "macbook-pro", "units",
            "e-mail", "sales", "acme.example", "50", "off"]
    assert got == want, (f"tokenise on the awkward sentence.\n      expected {want}\n      got      {got}\n"
                         "      hint: one regex with findall; keep . ' - only BETWEEN letters or digits, and drop a trailing 's")
    assert mod.tokenise("") == [] and mod.tokenise("  ...  !? ") == [], "no letters or digits, no tokens"
    assert mod.tokenise("Straße STRASSE") == ["strasse", "strasse"], "use casefold(), not lower(): ß folds to ss"
    assert mod.tokenise("café") == mod.tokenise("café"), "normalise to NFC first: composed and decomposed é must match"
    assert mod.tokenise("snake_case") == ["snake", "case"], "an underscore separates tokens"

    assert mod.fold_accents("Café naïve Zoë") == "Cafe naive Zoe", f"fold_accents: got {mod.fold_accents('Café naïve Zoë')!r}"
    assert mod.fold_accents("Straße") == "Straße", "ß is a letter, not an accent: leave it alone"
    assert mod.fold_accents("café") == "cafe", "decomposed input must fold too"

    a = mod.analyse("The refunds are issued to the original payment method.")
    assert a == ["refund", "issu", "original", "payment", "method"], (
        f"analyse with defaults: expected ['refund', 'issu', 'original', 'payment', 'method'], got {a}\n"
        "      order: fold accents, tokenise, drop stop words, then stem")
    assert mod.analyse("The Refunds", stop=False, stem=False) == ["the", "refunds"], "flags off: only fold and tokenise"
    assert mod.analyse("Cafés", fold=False, stop=False, stem=False) == ["cafés"], "fold=False keeps the accent"
    assert mod.analyse("Cafés", stop=False, stem=False) == ["cafes"], "fold=True removes it"
    assert mod.analyse("the of and to") == [], "a text of only stop words has no terms"
    assert mod.analyse("This was seen") == ["was", "seen"], (
        f"drop stop words BEFORE stemming ('this' would stem to 'thi' and escape the list); got {mod.analyse('This was seen')}")

    note = ""
    pool = ["Refund", "Refunds", "Café", "café", "STRASSE", "Straße", "invoice", "Invoices", "the", "co-op",
            "O'Neil's", "résumé", "naïve", "payments", "paid"]
    for s in seeds(range(1, 8)):
        rng = random.Random(s)
        text = " ".join(rng.choices(pool, k=rng.randint(1, 12))) + rng.choice(["", ".", "!", " (ok)"])
        base = mod.analyse(text)
        assert mod.analyse(text.upper()) == base, f"seed {s}: upper-case input changed the terms: {text!r} -> {mod.analyse(text.upper())} vs {base}"
        nfd = unicodedata.normalize("NFD", text)
        assert mod.analyse(nfd) == base, f"seed {s}: decomposed input changed the terms: {text!r}"
        assert mod.analyse(text + " the") == base, f"seed {s}: a trailing stop word changed the terms"
    return note


# =============================================================================
# Milestone 2: the inverted index
# =============================================================================
def m2():
    ix = mod.Index(str.split)                    # split on spaces: no analyser involved
    ix.add("d2", "b c")
    ix.add("d1", "a b a")
    assert ix.n_docs == 2, f"n_docs should be 2, got {ix.n_docs}"
    assert ix.posting_list("b") == [("d1", 1), ("d2", 1)], f"posting_list('b') should be sorted by doc id: got {ix.posting_list('b')}"
    assert ix.posting_list("a") == [("d1", 2)], f"tf of 'a' in d1 is 2; got {ix.posting_list('a')}"
    assert ix.posting_list("zzz") == [] and ix.df("zzz") == 0, "an unseen term has no postings and df 0"
    assert ix.df("b") == 2 and ix.df("a") == 1, f"df counts documents, not occurrences: df(a)={ix.df('a')}, df(b)={ix.df('b')}"
    assert ix.doc_len == {"d2": 2, "d1": 3}, f"doc_len should hold analysed lengths; got {ix.doc_len}"
    assert near(ix.avg_doc_len(), 2.5), f"avg_doc_len should be 2.5, got {ix.avg_doc_len()}"
    before = (dict(ix.doc_len), {t: dict(p) for t, p in ix.postings.items()})
    try:
        ix.add("d1", "x y z")
    except ValueError:
        pass
    else:
        raise AssertionError("adding a doc id twice must raise ValueError")
    assert (dict(ix.doc_len), {t: dict(p) for t, p in ix.postings.items()}) == before, \
        "a rejected duplicate must leave the index unchanged (check BEFORE you record anything)"
    ix.add("d3", "")
    assert ix.n_docs == 3 and ix.doc_len["d3"] == 0, "an empty document is still a document"
    assert near(ix.avg_doc_len(), 5 / 3), f"empty documents count in the average length: expected {5 / 3:.4f}, got {ix.avg_doc_len()}"
    assert near(mod.Index().avg_doc_len(), 0.0), "an empty index has average length 0.0, not a ZeroDivisionError"

    for s in seeds(range(1, 6)):
        docs, _ = random_corpus(s)
        ix = build(docs, str.split)
        counts = {d: Counter(t.split()) for d, t in docs.items()}
        terms = {t for c in counts.values() for t in c}
        for t in terms | {"nope"}:
            want = sorted((d, c[t]) for d, c in counts.items() if c[t])
            assert ix.posting_list(t) == want, f"seed {s}: posting_list({t!r}) should be {want}, got {ix.posting_list(t)}"
            assert ix.df(t) == len(want), f"seed {s}: df({t!r}) should be {len(want)}, got {ix.df(t)}"
        tot = sum(sum(c.values()) for c in counts.values())
        assert near(ix.avg_doc_len(), tot / len(docs)), f"seed {s}: avg_doc_len should be {tot / len(docs):.4f}, got {ix.avg_doc_len()}"

    ix = build(CH2, lambda t: mod.analyse(t, stop=False, stem=False))
    assert ix.n_docs == 8 and near(ix.avg_doc_len(), 191 / 8), f"chapter 2 corpus: N=8, avgdl=23.875; got N={ix.n_docs}, avgdl={ix.avg_doc_len()}"
    got = {t: ix.df(t) for t in ["invoice", "payment", "tax", "late", "the"]}
    assert got == {"invoice": 4, "payment": 5, "tax": 3, "late": 2, "the": 6}, f"chapter 2 document frequencies: got {got}"
    return f"chapter 2 corpus: N={ix.n_docs}, avgdl={ix.avg_doc_len():.3f}, df(late)={ix.df('late')}, df(payment)={ix.df('payment')}"


# =============================================================================
# Milestone 3: BM25 pieces
# =============================================================================
def m3():
    assert near(mod.idf(8, 2), math.log(3.6)), f"idf(8, 2) should be ln(1 + 6.5/2.5) = 1.2809, got {mod.idf(8, 2)}"
    assert near(mod.idf(8, 4), math.log(2)), f"idf(8, 4) should be ln 2 = 0.6931, got {mod.idf(8, 4)}"
    assert mod.idf(8, 8) > 0 and mod.idf(1000, 1000) > 0, "the Lucene form is positive even for a term in every document"
    assert mod.idf(8, 1) > mod.idf(8, 2) > mod.idf(8, 7), "idf must fall as df rises"
    assert near(mod.idf(1_000_000, 1000), math.log(1 + 999_000.5 / 1000.5)), "idf(1e6, 1000)"

    avgdl = 191 / 8
    assert near(mod.tf_norm(2, 22, avgdl), 2 * 2.2 / (2 + 1.2 * (0.25 + 0.75 * 22 / avgdl))), \
        f"tf_norm(2, 22, 23.875) should be about 1.406, got {mod.tf_norm(2, 22, avgdl)}"
    assert mod.tf_norm(0, 22, avgdl) == 0.0, "tf 0 contributes nothing"
    for k1, b in [(1.2, 0.75), (0.5, 0.0), (3.0, 1.0)]:
        assert near(mod.tf_norm(1, 20, 20, k1, b), 1.0), f"tf=1 in an average-length document gives exactly 1 (k1={k1}, b={b})"
    assert near(mod.tf_norm(5, 3, 30, k1=0.0), 1.0), "k1 = 0: presence only, every tf gives 1"
    assert near(mod.tf_norm(3, 5, 30, 1.2, 0.0), mod.tf_norm(3, 500, 30, 1.2, 0.0)), "b = 0: document length is ignored"
    assert mod.tf_norm(3, 5, 30, 1.2, 1.0) > mod.tf_norm(3, 60, 30, 1.2, 1.0), "b = 1: a longer document scores less"
    assert mod.tf_norm(10 ** 9, 10, 10) < 2.2 + 1e-6, "the tf component never exceeds k1 + 1"
    assert near(mod.tf_norm(10 ** 9, 10, 10), 2.2, 1e-6), "and approaches k1 + 1 as tf grows"

    ix = build(CH2, lambda t: mod.analyse(t, stop=False, stem=False))
    q = ["late", "payment", "invoice"]
    want = {"d1": 3.2096, "d5": 1.1752, "d7": 0.0}
    for d, w in want.items():
        got = mod.score_doc(ix, q, d)
        assert abs(got - w) < 5e-4, f"score_doc(d={d}) for 'late payment invoice': chapter 2 gives {w}, got {got:.4f}"
    assert mod.score_doc(ix, [], "d1") == 0.0, "no query terms, no score"
    s0, s1 = mod.score_doc(ix, q, "d5", b=0.0), mod.score_doc(ix, q, "d5", b=1.0)
    assert s0 > s1 > 0, f"the long report d5 must lose score as b rises: b=0 gave {s0:.3f}, b=1 gave {s1:.3f}"

    for s in seeds(range(1, 6)):
        docs, rng = random_corpus(s)
        ix = build(docs, str.split)
        for _ in range(6):
            query = random_query(rng)
            want = dict(oracle(docs, query, 0.9, 0.4))
            for d in docs:
                got = mod.score_doc(ix, list(dict.fromkeys(query.split())), d, 0.9, 0.4)
                assert near(got, want.get(d, 0.0)), f"seed {s}: score_doc({d!r}) for {query!r} (k1=0.9, b=0.4) should be {want.get(d, 0.0):.6f}, got {got:.6f}"
    return ""


# =============================================================================
# Milestone 4: top-k search
# =============================================================================
def m4():
    ix = build(CH2, lambda t: mod.analyse(t, stop=False, stem=False))
    got = mod.search(ix, "late payment invoice", k=10)
    want = [("d1", 3.21), ("d6", 1.788), ("d5", 1.175), ("d8", 1.024), ("d2", 0.999), ("d4", 0.756), ("d3", 0.548)]
    assert [d for d, _ in got] == [d for d, _ in want], (f"chapter 2's ranking is d1 d6 d5 d8 d2 d4 d3 (d7 matches no term and "
                                                       f"must not appear); got {[d for d, _ in got]}")
    for (d, s), (_, w) in zip(got, want):
        assert abs(s - w) < 5e-4, f"score of {d}: chapter 2 gives {w}, got {s:.4f}"
    assert [d for d, _ in mod.search(ix, "late payment invoice", k=3)] == ["d1", "d6", "d5"], "k limits the list"
    assert mod.search(ix, "late payment invoice", k=0) == [], "k = 0 returns nothing"
    assert mod.search(ix, "zebra quokka") == [], "no known term, no results"
    assert mod.search(ix, "") == [], "an empty query returns nothing"
    a, b2 = mod.search(ix, "late payment invoice"), mod.search(ix, "late late payment payment invoice invoice")
    assert a == b2, "a repeated query term must count once"

    twins = mod.Index(str.split)
    for d in ["z3", "z1", "z2"]:
        twins.add(d, "w3 w3 w7")
    twins.add("a1", "w3")
    res = mod.search(twins, "w3 w7")
    assert [d for d, _ in res][:3] == ["z1", "z2", "z3"], f"identical documents tie: list them in ascending doc id; got {[d for d, _ in res]}"

    for s in seeds(range(1, 6)):
        docs, rng = random_corpus(s)
        ix = build(docs, str.split)
        for _ in range(12):
            query = random_query(rng)
            k1, b = rng.choice([(1.2, 0.75), (0.0, 0.75), (2.0, 0.0), (1.5, 1.0), (0.6, 0.3)])
            k = rng.choice([1, 3, 5, 100])
            full = oracle(docs, query, k1, b)
            got = mod.search(ix, query, k, k1, b)
            same_ranking(got, full, k, f"seed {s} q={query!r} k={k} k1={k1} b={b}")
    return f"{len(docs)} random documents per seed, 12 queries each, compared with a brute-force oracle"


# =============================================================================
# Milestone 5: explain, and scenarios on a small knowledge base
# =============================================================================
def m5():
    ix = build(CH2, lambda t: mod.analyse(t, stop=False, stem=False))
    rows = mod.explain(ix, "late payment invoice", "d1")
    assert [r["term"] for r in rows] == ["late", "invoice", "payment"], \
        f"explain lists terms best first (late 1.801, invoice 0.716, payment 0.692); got {[r['term'] for r in rows]}"
    r0 = rows[0]
    assert (r0["tf"], r0["df"]) == (2, 2), f"'late' occurs twice in d1 and in 2 documents; got tf={r0['tf']} df={r0['df']}"
    assert near(r0["idf"], math.log(3.6)) and abs(r0["score"] - 1.801) < 5e-4, f"the 'late' row should have idf 1.281 and score 1.801: {r0}"
    assert near(r0["score"], r0["idf"] * r0["tf_norm"]), "score = idf x tf_norm"
    assert [r["term"] for r in mod.explain(ix, "late payment invoice", "d5")] == ["late", "payment"], "terms the document lacks are omitted"
    assert mod.explain(ix, "zebra", "d1") == [], "nothing to explain"

    for s in seeds(range(1, 4)):
        docs, rng = random_corpus(s)
        kb = build(docs, str.split)
        for _ in range(8):
            query = random_query(rng)
            for d, sc in mod.search(kb, query, 5):
                total = sum(r["score"] for r in mod.explain(kb, query, d))
                assert near(total, sc), f"seed {s}: explain({d!r}) for {query!r} sums to {total:.6f} but search scored it {sc:.6f}"

    ix = build(KB)
    top = lambda q, **kw: mod.search(ix, q, 5, **kw)
    ids = lambda res: [d for d, _ in res]

    res = top("refund policy")
    assert ids(res)[0] == "kb01", f"'refund policy' should put the refund policy page first, got {ids(res)}"
    res = top("refund damaged photo")
    assert ids(res)[0] == "kb02" and "kb03" in ids(res), \
        f"a page about damaged refunds beats the keyword-stuffed page kb03; got {ids(res)}"
    stuffed = mod.explain(ix, "refund", "kb03")[0]
    assert stuffed["tf"] >= 12 and stuffed["tf_norm"] < 2.2, \
        f"kb03 repeats 'refund' 13 times, but its tf component must stay below k1 + 1 = 2.2; got tf={stuffed['tf']}, tf_norm={stuffed['tf_norm']:.3f}"
    flat = top("refund", k1=0.0)
    assert len({round(sc, 9) for _, sc in flat}) == 1 and ids(flat)[0] == "kb01", \
        f"with k1 = 0 every page containing 'refund' scores the same (term presence only) and ties go by doc id; got {flat}"
    long_b0 = dict(mod.search(ix, "refund", 40, b=0.0))["kb32"]
    long_b1 = dict(mod.search(ix, "refund", 40, b=1.0))["kb32"]
    assert long_b1 < long_b0, f"the long terms page kb32 must score less for 'refund' as b rises; b=0: {long_b0:.3f}, b=1: {long_b1:.3f}"

    res = top("payment passport")
    assert ids(res)[0] == "kb13" and mod.explain(ix, "payment passport", "kb13")[0]["term"] == "passport", \
        f"the rare term 'passport' (1 page) should outweigh the common 'payment'; got {ids(res)}"
    assert ids(top("cafe"))[:1] == ["kb21"] == ids(top("café"))[:1], "'cafe' and 'café' must find the café page (accent folding)"
    assert ids(top("resume"))[:1] == ["kb22"] == ids(top("RÉSUMÉ"))[:1], "'resume' and 'RÉSUMÉ' must find the résumé page"
    assert top("the of and to") == [], "a query of only stop words has no terms and no results"
    res = top("personal data")
    assert ids(res)[:2] == ["kb25", "kb26"] and near(res[0][1], res[1][1]), f"kb25 and kb26 tie for 'personal data'; ties go by doc id: {res}"

    stemmed = ids(mod.search(ix, "refunds", 40))
    raw = build(KB, lambda t: mod.analyse(t, stem=False))
    unstemmed = ids(mod.search(raw, "refunds", 40))
    assert len(stemmed) > len(unstemmed) >= 1, f"stemming should widen 'refunds' from {len(unstemmed)} pages to more; got {len(stemmed)} with stemming"
    lines = []
    for q in ["refund policy", "payment passport", "personal data"]:
        res = top(q)[:3]
        lines.append(f"{q!r:<20} -> " + "  ".join(f"{d} {sc:.2f}" for d, sc in res))
    lines.append(f"'refunds': {len(stemmed)} pages with stemming, {len(unstemmed)} without")
    return "\n".join(lines)


MILESTONES = [
    (1, "Milestone 1: the analyser", m1),
    (2, "Milestone 2: the inverted index", m2),
    (3, "Milestone 3: IDF, saturation and length normalisation", m3),
    (4, "Milestone 4: top-k search, term at a time", m4),
    (5, "Milestone 5: explain, and rankings you can defend", m5),
]

if __name__ == "__main__":
    t0 = time.time()
    print(f"Lab 1 checks against {target}.py\n")
    for n, name, fn in MILESTONES:
        check(n, name, fn)
    print(f"\n{sum(results)}/{len(results)} milestones passing  ({time.time() - t0:.1f} s)")
    sys.exit(0 if all(results) else 1)
