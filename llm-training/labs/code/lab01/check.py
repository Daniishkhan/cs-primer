"""Self-check for Lab 1: A Pretraining Data Pipeline.

    python3 check.py                  # checks your starter.py
    python3 check.py solution         # checks the reference solution
    python3 check.py solution 4       # only milestone 4
    python3 check.py solution 4 7     # milestone 4, replaying ONLY the random cases of seed 7

Everything is synthetic and seeded: the crawl (corpus.py), the hash functions and every random
test input. There is no network and no clock, so every run gives identical numbers. The whole
check finishes in a few seconds.
Prints a tick, a cross, or "not implemented yet" for each milestone.
"""
import hashlib
import importlib
import random
import re
import sys
import time

import os

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True

import corpus  # noqa: E402

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


PAGES = corpus.pages()
KIND = {p.id: p.kind for p in PAGES}
FAMILY = {p.id: p.family for p in PAGES}


def prose(n_words, salt=0):
    """Distinct English-looking lines of 10 words, with stop words, about n_words words long."""
    verbs = "carries shapes drains reaches shifts crosses fills guards".split()
    nouns = "harbour estuary shoreline current basin channel sandbar lagoon beach swell".split()
    lines = []
    for i in range(0, n_words, 10):
        lines.append(f"The {nouns[(i + salt) % 10]} {verbs[(i // 10 + salt) % 8]} the {nouns[(i * 3 + salt + 1) % 10]} "
                     f"and the {nouns[(i + 5 + salt) % 10]} that I have seen.")
    return "\n".join(lines)


# =============================================================================
# Milestone 1: HTML to text
# =============================================================================
def m1():
    ex = mod.extract
    cases = [
        ("<p>Hello  <b>big</b>\n world</p><p>Bye</p>", "Hello big world\nBye", "inline tags do not break a line; runs of whitespace collapse to one space; each <p> is a line"),
        ("foo<span>bar</span>", "foobar", "an inline tag must not insert a space or a newline"),
        ("<ul><li>One</li><li>Two</li></ul>", "One\nTwo", "each <li> is its own line"),
        ("one<br>two<br/>three", "one\ntwo\nthree", "<br> starts a new line"),
        ("<nav><a href='/'>Home</a></nav><script>var x = 1;</script><style>p{color:red}</style><p>Keep</p>", "Keep",
         "nav, script and style content must be dropped"),
        ("<html><head><title>The title</title></head><body><h1>Heading</h1></body></html>", "Heading",
         "everything in <head> (including the title) is dropped; <header> is a different tag"),
        ("<aside>a<nav>b</nav>still hidden</aside><p>shown</p>", "shown",
         "skipped tags nest: after </nav> you are still inside <aside>. Count depth instead of using a True/False flag"),
        ("<p>Tom &amp; Jerry &lt;3</p>", "Tom & Jerry <3", "character references are decoded (HTMLParser does this for you)"),
        ("   <div>  </div>\n<div> x </div>", "x", "blank lines are removed and lines are stripped"),
        ("", "", "empty input gives the empty string"),
        ("<footer>Only boilerplate</footer>", "", "a page that is all boilerplate extracts to nothing"),
    ]
    for html, want, why in cases:
        got = ex(html)
        assert got == want, f"extract({html!r}) should be {want!r} ({why}); got {got!r}"

    bad_markers = ("<", "var tracker", "Copyright", "Related stories", "Daily Gazette", "&amp;", "Home")
    n_words = 0
    for p in PAGES:
        t = ex(p.html)
        for m in bad_markers:
            assert m not in t, f"page {p.id} ({p.kind}): the extracted text still contains {m!r}; first 120 chars: {t[:120]!r}"
        assert all(ln == ln.strip() and "  " not in ln and ln for ln in t.split("\n")) or t == "", \
            f"page {p.id}: every line must be stripped, single-spaced and non-empty"
        if p.kind in ("article", "exact"):
            assert re.search(r"report \d+ & outlook", t, re.I), f"page {p.id}: the <h1> (with &amp; decoded) is missing from {t[:80]!r}"
            assert len(t.split()) >= 50, f"page {p.id}: an article should extract to at least 50 words; got {len(t.split())}"
        n_words += len(t.split())
    return f"{len(cases)} hand cases, then {len(PAGES)} synthetic pages: no tags, scripts, navigation or footers survive ({n_words} words in all)"


# =============================================================================
# Milestone 2: quality filters
# =============================================================================
def m2():
    f = mod.c4_line_filter
    text = ("Home\nThe tide rises twice a day.\nBuy now\nEnable JavaScript to view this page properly.\n"
            "We use cookies on this site today.\nA line with no end punctuation here\nShare this page!\n"
            "Our Terms of Use apply to everything here.")
    got = f(text)
    assert got == "The tide rises twice a day.\nShare this page!", (
        f"c4_line_filter(text) with require_punct=True should keep only the two sentences with three or more words and "
        f"terminal punctuation; got {got!r}")
    got = f(text, require_punct=False)
    assert got == "The tide rises twice a day.\nA line with no end punctuation here\nShare this page!", (
        f"with require_punct=False the unpunctuated line must survive but 'Home' (1 word), 'Buy now' (2 words) and the "
        f"javascript, cookie and terms-of-use lines must not; got {got!r}")
    assert f("") == "" and f("Two words") == "", "empty or too-short input gives the empty string"
    assert f('He said "yes please"', True) == 'He said "yes please"', "a closing double quote counts as terminal punctuation"

    good = prose(60)
    assert len(good.split()) >= 50 and mod.quality_flags(good) == [], \
        f"a clean 60-word text must pass every rule; got flags {mod.quality_flags(good)}"
    assert mod.keep(good) is True and mod.keep("Short.") is False, "keep() returns True for a clean text and False for a flagged one"
    assert mod.quality_flags(prose(50)) == [], "exactly 50 words is allowed (the lower bound is inclusive)"
    assert mod.quality_flags(prose(40)) == ["length"], f"40 words must break only 'length'; got {mod.quality_flags(prose(40))}"
    assert "length" in mod.quality_flags(""), "the empty text must be flagged 'length' (and must not divide by zero)"

    rules = {
        "mean_word_length": good + "\n" + " ".join(["internationalisation"] * 120),
        "symbols": good + "\n" + " ".join(["#deal"] * 20),
        "bullets": "\n".join("- " + ln for ln in good.split("\n")),
        "ellipsis": "\n".join(ln[:-1] + "..." for ln in good.split("\n")),
        "alpha": good + "\n" + " ".join(["1234", "5678"] * 40),
        "stopwords": "\n".join(ln.replace("The ", "Our ").replace(" the ", " our ").replace(" and ", " plus ").replace(" that ", " which ")
                              .replace(" have ", " had ") for ln in good.split("\n")),
        "repeated_lines": "\n".join([good.split("\n")[0]] * 8),
        "boilerplate": good + "\nLorem ipsum dolor sit amet.",
    }
    for rule, text in rules.items():
        got = mod.quality_flags(text)
        assert rule in got, f"a text built to break '{rule}' was not flagged for it; flags were {got}"
    assert mod.quality_flags(good + "\nif (x) { y = 1; }") == ["boilerplate"], "a curly bracket marks code or template debris: flag 'boilerplate'"
    multi = mod.quality_flags("\n".join("- #a #b #c #d #e #f" for _ in range(12)))
    assert multi == sorted(multi, key=["length", "mean_word_length", "symbols", "bullets", "ellipsis", "alpha",
                                       "stopwords", "repeated_lines", "boilerplate"].index) and len(multi) >= 4, \
        f"flags must be listed in the documented order (length, mean_word_length, symbols, ...); got {multi}"

    verdict = {}
    for p in PAGES:
        text = f(mod.extract(p.html), require_punct=False)
        verdict.setdefault(p.kind, []).append(mod.keep(text))
    for kind in ("article", "exact", "light", "medium", "related"):
        assert all(verdict[kind]), f"{sum(not v for v in verdict[kind])} of {len(verdict[kind])} '{kind}' pages (good prose) were dropped by your filters; print quality_flags() for one of them"
    for kind in ("spam", "short", "nonenglish"):
        assert not any(verdict[kind]), f"{sum(verdict[kind])} of {len(verdict[kind])} '{kind}' pages passed your filters; print their quality_flags()"
    assert not any(verdict["borderline"]), "the 40-word 'borderline' pages are genuinely good but fall under the 50-word rule: they should be dropped"
    fam = [k for k in ("spam", "short", "nonenglish")]
    return (f"hand cases for every rule, then the crawl: {sum(map(len, (verdict[k] for k in fam)))} spam, stub and non-English pages dropped, "
            f"{sum(map(len, (verdict[k] for k in ('article', 'exact', 'light', 'medium', 'related'))))} article pages kept;\n"
            f"the {sum(verdict['seo'])} keyword-stuffed 'seo' pages also pass (rules cannot see them), and the 3 short good notes are lost")


# =============================================================================
# Milestone 3: exact and line-level deduplication
# =============================================================================
def m3():
    n = mod.normalise("  Hello, WORLD!!  It's 5 o'clock. ")
    assert n == "hello world it s 5 o clock", f"normalise should lower-case and turn each run of punctuation or space into one space; got {n!r}"
    assert mod.normalise("") == "" and mod.normalise("!!!") == "", "text with no letters or digits normalises to the empty string"

    docs = [("a", "The cat."), ("b", "the  cat"), ("c", "A dog."), ("d", "THE CAT!"), ("e", "A dog!")]
    kept, dropped = mod.exact_dedupe(docs)
    assert [i for i, _ in kept] == ["a", "c"], f"exact_dedupe should keep the first of each distinct normalised text (a, c); kept {[i for i, _ in kept]}"
    assert dict(kept)["a"] == "The cat.", "kept documents keep their original text, not the normalised one"
    assert dropped == {"b": "a", "d": "a", "e": "c"}, f"dropped should map each removed id to the id it copies; got {dropped}"
    assert mod.exact_dedupe([]) == ([], {}), "no documents: nothing kept, nothing dropped"

    promo = "Subscribe to our newsletter for weekly updates."
    docs = [(f"d{i}", f"Unique line number {i} here.\n{promo}\nShared twice.") for i in range(4)]
    docs.append(("d4", f"Only this one.\n{promo}\n{promo}"))
    out = dict(mod.line_dedupe(docs, max_docs=4))
    assert promo not in out["d0"].split("\n"), f"a line found in 5 documents (more than max_docs=4) must be removed; d0 became {out['d0']!r}"
    assert out["d0"] == "Unique line number 0 here.\nShared twice.", f"only the over-frequent line goes; got {out['d0']!r}"
    assert out["d4"] == "Only this one.", f"a line repeated inside one document counts once per document but is removed everywhere; d4 became {out['d4']!r}"
    out = dict(mod.line_dedupe(docs, max_docs=5))
    assert promo in out["d0"].split("\n"), "a line found in exactly max_docs documents is kept (the test is 'more than')"
    res = mod.line_dedupe([("x", promo), ("y", promo)], max_docs=1)
    assert res == [("x", ""), ("y", "")], f"documents that lose every line stay in the list with the empty text; got {res}"

    # The crawl: cleaning promo lines first lets exact deduplication see the copies.
    pre = [(p.id, mod.c4_line_filter(mod.extract(p.html), require_punct=False)) for p in PAGES]
    pre = [(i, t) for i, t in pre if mod.keep(t)]
    _, plain = mod.exact_dedupe(pre)
    lined = mod.line_dedupe(pre)
    _, after = mod.exact_dedupe([(i, t) for i, t in lined if t])
    n_exact = sum(KIND[i] == "exact" for i, _ in pre)
    for d, rep in after.items():
        assert FAMILY[d] is not None and FAMILY[d] == FAMILY[rep], f"exact_dedupe wrongly merged {d} ({KIND[d]}) into {rep} ({KIND[rep]}); only copies of one article may merge"
    assert len(after) > len(plain), (f"line_dedupe followed by exact_dedupe should find more copies than exact_dedupe alone "
                                     f"(promo lines hide them), but it found {len(after)} and {len(plain)}")
    assert len(after) >= n_exact - 1, f"after line_dedupe, {n_exact} pages are exact copies of an article and at least {n_exact - 1} should be removed; yours removed {len(after)}"
    return (f"hand cases, then the crawl: exact_dedupe alone finds {len(plain)} copies, but after line_dedupe removes the shared promo lines\n"
            f"it finds {len(after)} of the {n_exact} generated exact copies")


# =============================================================================
# Milestone 4: shingles and MinHash
# =============================================================================
def oracle_signature(shingle_set, num_perm):
    xs = [mod.base_hash(s) for s in shingle_set]
    return [min((a * x + b) % mod.PRIME for x in xs) for a, b in mod.HASH_COEFS[:num_perm]]


def m4():
    s = mod.shingles("a b c d e f g", 5)
    assert s == {"a b c d e", "b c d e f", "c d e f g"}, f"shingles('a b c d e f g', 5) are the three 5-word windows; got {sorted(s)}"
    assert mod.shingles("A  B\nC", 2) == {"a b", "b c"}, "shingles lower-case the text and split on any whitespace, including newlines"
    assert mod.shingles("only three words", 5) == {"only three words"}, "fewer than n words: one shingle holding all of them"
    assert mod.shingles("", 5) == set() and mod.shingles("   ", 5) == set(), "no words: the empty set"
    assert len(mod.shingles(" ".join(f"w{i}" for i in range(100)))) == 96, "100 distinct words give 96 five-word shingles by default"

    assert near(mod.jaccard({1, 2, 3}, {2, 3, 4}), 0.5) and mod.jaccard({1}, {1}) == 1.0 and mod.jaccard({1}, {2}) == 0.0
    assert mod.jaccard(set(), set()) == 0.0, "two empty sets: return 0.0 (do not divide by zero)"

    assert mod.minhash_signature(set(), 8) == [mod.EMPTY] * 8, "an empty set gives [EMPTY] * num_perm"
    one = mod.minhash_signature({"a b c d e"}, 112)
    assert len(one) == 112 and one == oracle_signature({"a b c d e"}, 112), "a one-element set's signature is just that element's 112 hash values"
    assert mod.minhash_signature({"x y", "z w"}, 16) == oracle_signature({"x y", "z w"}, 16), "num_perm selects the FIRST num_perm hash functions of HASH_COEFS"

    note = ""
    for seed in seeds(range(1, 4)):
        rng = random.Random(seed)
        A = {f"t{rng.randrange(10**6)}" for _ in range(rng.randint(5, 40))}
        B = {f"t{rng.randrange(10**6)}" for _ in range(rng.randint(5, 40))}
        sa, sb, su = mod.minhash_signature(A), mod.minhash_signature(B), mod.minhash_signature(A | B)
        assert sa == oracle_signature(A, 112), f"seed {seed}: the signature of a {len(A)}-element set differs from the definition min over (a*x+b) mod PRIME"
        assert su == [min(x, y) for x, y in zip(sa, sb)], (
            f"seed {seed}: the signature of a union must be the position-wise minimum of the two signatures "
            f"(that identity is why MinHash works); you built it some other way")
    # Estimates track the truth.
    errs, rng = [], random.Random(11)
    for i in range(40):
        m, shared = rng.randint(20, 60), rng.random()
        k = int(m * shared)
        base = [f"p{i}-{j}" for j in range(m + (m - k))]
        A, B = set(base[:m]), set(base[:k] + base[m:])
        errs.append(abs(mod.estimate_jaccard(mod.minhash_signature(A), mod.minhash_signature(B)) - mod.jaccard(A, B)))
    mean_err = sum(errs) / len(errs)
    assert mean_err < 0.05 and max(errs) < 0.15, (f"over 40 random set pairs the estimate should be within about 1/sqrt(112) = 0.09 of the true Jaccard; "
                                                  f"mean error {mean_err:.3f}, worst {max(errs):.3f}")
    X = {f"x{i}" for i in range(30)}
    assert mod.estimate_jaccard(mod.minhash_signature(X), mod.minhash_signature(set(X))) == 1.0, "identical sets estimate to exactly 1.0"
    assert mod.estimate_jaccard(mod.minhash_signature(X), mod.minhash_signature({f"y{i}" for i in range(30)})) <= 0.03, "disjoint sets estimate to about 0"

    sh = {p.id: mod.shingles(mod.c4_line_filter(mod.extract(p.html), False)) for p in PAGES}
    sig = {i: mod.minhash_signature(s) for i, s in sh.items() if s}
    pairs = sorted(corpus.gold_pairs(set(sig)))
    gaps = [abs(mod.estimate_jaccard(sig[a], sig[b]) - mod.jaccard(sh[a], sh[b])) for a, b in pairs]
    assert sum(gaps) / len(gaps) < 0.05, f"on the {len(pairs)} true duplicate pairs of the crawl the mean estimate error should be under 0.05; got {sum(gaps) / len(gaps):.3f}"
    note = (f"hand values, exact signatures, the union identity, then the crawl: on {len(pairs)} duplicate pairs the 112-number signatures\n"
            f"estimate Jaccard to within {sum(gaps) / len(gaps):.3f} on average (worst {max(gaps):.3f})")
    return note


# =============================================================================
# Milestone 5: locality-sensitive hashing
# =============================================================================
def m5():
    sig = list(range(112))
    keys = mod.band_keys(sig, 14, 8)
    assert len(keys) == 14 and keys[0] == (0, tuple(range(8))) and keys[13] == (13, tuple(range(104, 112))), \
        f"band_keys(range(112), 14, 8) should be 14 keys of the form (index, tuple of 8 values), first (0, (0, ..., 7)); got {keys[:1]} ... {keys[-1:]}"
    assert len(set(mod.band_keys([7] * 112, 14, 8))) == 14, "identical band contents in different bands must give different keys (include the band index)"

    a, b_, c = [1] * 16, [1] * 8 + [2] * 8, [3] * 16
    got = mod.candidate_pairs({"a": a, "b": b_, "c": c}, b=2, r=8)
    assert got == {("a", "b")}, f"a and b share band 0 and c shares nothing: expected {{('a', 'b')}}; got {got}"
    got = mod.candidate_pairs({"b": b_, "a": a}, b=2, r=8)
    assert got == {("a", "b")}, f"each pair is reported once as (smaller id, larger id), whatever the dict order; got {got}"
    x, y = [1, 2, 3, 4], [3, 4, 1, 2]
    got = mod.candidate_pairs({"x": x, "y": y}, b=2, r=2)
    assert got == set(), f"x and y hold the same band values in different bands, which must not match; got {got}"
    got = mod.candidate_pairs({"p": [5] * 8, "q": [5] * 8, "r": [5] * 8}, b=2, r=4)
    assert got == {("p", "q"), ("p", "r"), ("q", "r")}, f"three identical documents form three pairs, each once; got {got}"
    assert mod.candidate_pairs({}, 2, 4) == set() and mod.candidate_pairs({"a": [1] * 8}, 2, 4) == set(), "fewer than two documents: no pairs"

    rng = random.Random(5)
    big = {f"u{i}": [rng.randrange(2 ** 61) for _ in range(112)] for i in range(8000)}
    planted = {(f"u{i}", f"u{i + 1}") for i in range(0, 40, 2)}
    for p, q in planted:
        big[q] = list(big[p][:100]) + [rng.randrange(2 ** 61) for _ in range(12)]
    t0 = time.time()
    got = mod.candidate_pairs(big, 14, 8)
    took = time.time() - t0
    assert got == planted, f"8,000 random signatures with 20 planted near-copies: expected exactly the 20 planted pairs; got {len(got)} pairs"
    assert took < 8.0, f"candidate_pairs took {took:.1f} s on 8,000 documents: you are probably comparing all pairs (32 million) instead of using a bucket table"

    assert near(mod.candidate_probability(0.0), 0.0) and near(mod.candidate_probability(1.0), 1.0)
    for s, want in [(0.5, 0.0532), (0.7, 0.5645), (0.75, 0.7716), (0.8, 0.9236)]:
        got = mod.candidate_probability(s, 14, 8)
        assert near(got, want, 5e-4), f"1 - (1 - {s}^8)^14 should be about {want}; got {got:.4f}"
    assert near(mod.candidate_probability(0.5, 28, 4), 1 - (1 - 0.5 ** 4) ** 28), "b and r are parameters"
    assert near(mod.threshold(14, 8), 0.7190, 5e-4) and near(mod.threshold(28, 4), 0.4347, 5e-4), \
        f"threshold is (1/b)^(1/r): 0.7190 for 14 x 8 and 0.4347 for 28 x 4; got {mod.threshold(14, 8):.4f} and {mod.threshold(28, 4):.4f}"
    assert mod.best_bands(112, 0.75) == (14, 8), f"of the splits of 112 into b x r, 14 x 8 (threshold 0.719) is closest to 0.75; got {mod.best_bands(112, 0.75)}"
    assert mod.best_bands(112, 0.4) == (28, 4) and mod.best_bands(128, 0.5) == (32, 4), "best_bands(112, 0.4) is (28, 4) and best_bands(128, 0.5) is (32, 4)"

    # The S-curve is a fact about signatures, so measure it.
    lines = []
    for seed in seeds([21]):
        for (m, k, J) in [(18, 12, 0.5), (18, 16, 0.8)]:
            r_ = random.Random(seed * 100 + k)
            hits, n = 0, 150
            for t in range(n):
                A = {f"s{seed}-{t}-{j}" for j in range(m)}
                B = set(list(A)[:k]) | {f"s{seed}-{t}-n{j}" for j in range(m - k)}
                sa, sb = mod.minhash_signature(A), mod.minhash_signature(B)
                hits += bool(mod.candidate_pairs({"A": sa, "B": sb}, 14, 8))
            want = mod.candidate_probability(J, 14, 8)
            assert abs(hits / n - want) < 0.12, (f"seed {seed}: {n} pairs of true similarity {J} were flagged {hits / n:.2f} of the time; "
                                                  f"the formula says {want:.2f}. Check band_keys and candidate_pairs")
            lines.append(f"similarity {J}: flagged {hits / n:.2f} of {n} pairs, formula {want:.2f}")
    return "hand cases, an 8,000-document scale test, then the S-curve measured on signatures:\n" + "\n".join(lines)


# =============================================================================
# Milestone 6: evaluation and the whole pipeline
# =============================================================================
def m6():
    P = {("a", "b"), ("a", "c")}
    G = {("a", "b"), ("b", "c"), ("c", "d")}
    p, r = mod.precision_recall(P, G)
    assert near(p, 0.5) and near(r, 1 / 3), f"precision_recall({sorted(P)}, {sorted(G)}) should be (0.5, 0.333); got ({p}, {r})"
    assert mod.precision_recall(set(), G) == (1.0, 0.0), "no predictions: precision 1.0 (nothing claimed wrong), recall 0.0"
    assert mod.precision_recall(P, set()) == (0.0, 1.0), "no gold pairs: recall 1.0, and every prediction is wrong"
    assert mod.precision_recall(G, G) == (1.0, 1.0)

    got = mod.clusters(list("abcdef"), {("a", "b"), ("b", "c"), ("e", "f")})
    assert got == [["a", "b", "c"], ["d"], ["e", "f"]], f"clusters are connected components, sorted: expected [['a','b','c'],['d'],['e','f']]; got {got}"
    got = mod.clusters(list("abcd"), {("d", "c"), ("c", "b")})
    assert got == [["a"], ["b", "c", "d"]], f"pairs chain into one cluster whatever their order; got {got}"

    base = ("the harbour tide rises twice a day and floods the shallow estuary near the old town where "
            "small boats wait for the water to return and the fishermen mend their nets in the evening light")
    near_copy = base.replace("old town", "new town").replace("evening", "morning")
    other = ("bees gather nectar from the orchard blossoms and carry it back to the hive where the workers "
             "turn it into honey while the queen lays eggs and the drones wait for the warm days of summer")
    kept, removed, pairs = mod.near_dedupe({"d1": base, "d2": near_copy, "d3": other})
    assert kept == ["d1", "d3"] and removed == {"d2": "d1"}, (
        f"near_dedupe should merge d2 into d1 (a copy with two words changed) and keep the unrelated d3; kept {kept}, removed {removed}")
    assert pairs == {("d1", "d2")}, f"the pairs used should be {{('d1', 'd2')}}; got {pairs}"
    docs = {"d1": base, "d2": base.replace("tide rises", "wave falls").replace("small boats", "tall ships")}
    assert mod.jaccard(mod.shingles(base), mod.shingles(docs["d2"])) < 0.6
    loose = mod.near_dedupe(docs, b=56, r=2)
    assert loose[1] == {"d2": "d1"} and loose[2], "with 56 bands of 2 rows even a rather different pair becomes a candidate (and is merged)"
    verified = mod.near_dedupe(docs, b=56, r=2, min_jaccard=0.6)
    assert verified[0] == ["d1", "d2"] and verified[2] == set(), "min_jaccard=0.6 verifies each candidate with the true Jaccard and drops this one"
    chain = mod.near_dedupe({"c": base, "a": near_copy, "b": other})[0]
    assert chain == ["a", "b"], f"within a cluster the SMALLEST id is kept (here a, not c); kept {chain}"

    rep = mod.run_pipeline(PAGES)
    assert rep.n_pages == len(PAGES)
    assert rep.n_pages >= rep.after_quality >= rep.after_lines >= rep.after_exact >= rep.after_near > 0, f"stage counts must not increase: {rep}"
    assert rep.after_near == len(rep.kept) and set(rep.kept).isdisjoint(rep.dropped) and len(rep.kept) + len(rep.dropped) == rep.n_pages, (
        f"every page is either kept or dropped exactly once: kept {len(rep.kept)} + dropped {len(rep.dropped)} should be {rep.n_pages}")
    stage = {}
    for i, (st, detail) in rep.dropped.items():
        stage.setdefault(st, []).append(i)
    for i in (p_.id for p_ in PAGES if p_.kind in ("spam", "short", "nonenglish")):
        assert rep.dropped.get(i, ("",))[0] == "quality", f"page {i} ({KIND[i]}) should be dropped at the 'quality' stage; got {rep.dropped.get(i)}"
    for st in ("exact", "near"):
        for i in stage.get(st, []):
            rid = rep.dropped[i][1]
            assert FAMILY[i] and FAMILY[i] == FAMILY[rid], f"page {i} ({KIND[i]}) was dropped as a '{st}' copy of {rid} ({KIND[rid]}), but they are different articles"
    for i in (p_.id for p_ in PAGES if p_.kind == "related"):
        assert i in rep.kept, f"the 'related' page {i} only quotes another article and must survive deduplication; it was dropped as {rep.dropped[i]}"
    left = {}
    for i in rep.kept:
        if FAMILY[i]:
            left.setdefault(FAMILY[i], []).append(i)
    survivors = sum(len(v) > 1 for v in left.values())
    assert rep.precision >= 0.95, f"at 14 bands of 8 rows precision should be at least 0.95 (nearly every flagged pair is a real duplicate); got {rep.precision:.2f}"
    assert rep.recall >= 0.85, f"at 14 bands of 8 rows recall should be at least 0.85; got {rep.recall:.2f}. Duplicates at Jaccard 0.75 are caught 77% of the time, not 100%"
    assert len(set(FAMILY[i] for i in rep.kept if FAMILY[i])) == len(left) and len(left) >= 38, "every generated article should still be represented once"

    rows = []
    sweep = {}
    for b, r in [(7, 16), (14, 8), (28, 4), (56, 2)]:
        rp = mod.run_pipeline(PAGES, b, r)
        sweep[(b, r)] = rp
        rows.append(f"  {b:>2} bands x {r:>2} rows  threshold {mod.threshold(b, r):.2f}  candidates {rp.candidates:>3}  precision {rp.precision:.2f}  recall {rp.recall:.2f}  docs left {rp.after_near}")
    assert sweep[(7, 16)].recall < sweep[(14, 8)].recall <= sweep[(28, 4)].recall, "recall should rise as the threshold falls (more bands of fewer rows)"
    assert sweep[(56, 2)].precision < 0.8 < sweep[(14, 8)].precision, "a threshold of 0.13 (56 bands of 2 rows) should flag many pairs that are not duplicates"
    funnel = (f"funnel: {rep.n_pages} pages -> {rep.after_quality} after quality -> {rep.after_lines} after line dedupe -> "
              f"{rep.after_exact} after exact -> {rep.after_near} after near-duplicates")
    return (funnel + f"\nat 14 x 8: precision {rep.precision:.2f}, recall {rep.recall:.2f}; {survivors} families still have two surviving copies\n"
            + "\n".join(rows))


MILESTONES = [
    (1, "Milestone 1: HTML to text", m1),
    (2, "Milestone 2: C4 and Gopher quality filters", m2),
    (3, "Milestone 3: exact and line-level deduplication", m3),
    (4, "Milestone 4: shingles and MinHash signatures", m4),
    (5, "Milestone 5: locality-sensitive hashing", m5),
    (6, "Milestone 6: precision, recall and the full pipeline", m6),
]

if __name__ == "__main__":
    t0 = time.time()
    print(f"Lab 1 checks against {target}.py\n")
    for n, name, fn in MILESTONES:
        check(n, name, fn)
    print(f"\n{sum(results)}/{len(results)} milestones passing  ({time.time() - t0:.1f} s)")
    sys.exit(0 if all(results) else 1)
