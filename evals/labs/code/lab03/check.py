"""Self-check for Lab 3: Build a Domain Benchmark.

    python3 check.py                  # checks your starter.py
    python3 check.py solution         # checks the reference solution
    python3 check.py solution 4       # only milestone 4
    python3 check.py solution 2 7     # milestone 2, replaying ONLY the random trials of seed 7

Everything is synthetic and seeded: the 50 draft items (with eight planted defects), the 14-document
crawl snapshot, the stand-in models. There is no network and no real model, so every run gives
identical numbers, and the whole check finishes in a couple of seconds. Prints a tick, a cross, or
"not implemented yet" for each milestone.
"""
import hashlib
import importlib
import json
import os
import random
import re
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
import fixtures as FX  # noqa: E402

results = []

# Ground truth known only because the fixtures were generated.
PLANTED = {("p043", "missing_gold", None), ("p044", "bad_category", None), ("p045", "bad_difficulty", None),
           ("p046", "near_duplicate", "p001"), ("p047", "near_duplicate", "p013"),
           ("p048", "conflicting_gold", "p009"), ("p020", "duplicate_id", "p020"), ("p050", "missing_gold", None)}
LEAKED_VERBATIM = {"p001", "p002", "p004", "p007", "p010", "p016", "p022", "p033", "p046"}      # the question text is in the crawl
LEAKED_REWRITTEN = {"p003", "p005", "p009", "p028", "p029", "p030", "p031", "p032", "p034"}     # same content, other words or language
LEAKED_ALL = LEAKED_VERBATIM | LEAKED_REWRITTEN


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


def raises(exc, fn, *a, **kw):
    try:
        fn(*a, **kw)
    except exc:
        return True
    except Exception:
        return False
    return False


def item(id, q, gold="x", cat="fees", lv="easy", src="s"):
    return {"id": id, "category": cat, "difficulty": lv, "question": q, "gold": gold, "source": src}


ITEMS = mod.load_items()
CORPUS = mod.load_corpus()


# =============================================================================
# Milestone 1: validate the items
# =============================================================================
def m1():
    assert mod.shingles("a b c d") == {"a b c", "b c d"}, f'shingles("a b c d") should be {{"a b c", "b c d"}}; got {mod.shingles("a b c d")}'
    assert mod.shingles("Hello, World! hello", 2) == {"hello world", "world hello"}, \
        "case and punctuation are ignored: shingles('Hello, World! hello', 2) is {'hello world', 'world hello'}"
    assert mod.shingles("only two", 3) == set() and mod.shingles("", 3) == set(), "fewer than k words: the empty set"
    assert near(mod.jaccard({"a", "b"}, {"b", "c"}), 1 / 3), "jaccard({a,b}, {b,c}) = 1/3"
    assert mod.jaccard({"a"}, {"a"}) == 1.0 and mod.jaccard(set(), set()) == 0.0, "identical sets 1.0; two empty sets 0.0 (not a ZeroDivisionError)"
    assert mod.jaccard({"a"}, {"b"}) == 0.0

    base = item("a1", "What is the fee for a deck permit under thirty square metres?", "120")
    good = [base, item("a2", "How many hours of notice must a contractor give for an inspection?", "24")]
    assert mod.validate(good) == [], f"two distinct, well-formed items have no problems; got {mod.validate(good)}"

    def kinds(items, **kw):
        return {(p["id"], p["kind"], p["other"]) for p in mod.validate(items, **kw)}

    assert kinds([item("a1", "q one two three", "")]) == {("a1", "missing_gold", None)}, "an empty gold is missing_gold"
    assert kinds([item("a1", "q one two three", "  ")]) == {("a1", "missing_gold", None)}, "a whitespace-only gold is missing_gold"
    no_key = item("a1", "q one two three")
    del no_key["gold"]
    assert kinds([no_key]) == {("a1", "missing_gold", None)}, "an item with no gold key at all is missing_gold (use .get, not [])"
    assert kinds([item("a1", "q one two three", cat="setback")]) == {("a1", "bad_category", None)}
    assert kinds([item("a1", "q one two three", lv="Medium")]) == {("a1", "bad_difficulty", None)}, "difficulty must match exactly: 'Medium' is not 'medium'"
    assert kinds([item("a1", "alpha beta gamma delta"), item("a1", "epsilon zeta eta theta")]) == {("a1", "duplicate_id", "a1")}, \
        "the SECOND item with an id is the duplicate; other is that id"
    two = [base, item("b1", "What is the fee for a deck permit under thirty square metres?", "120")]
    assert kinds(two) == {("b1", "near_duplicate", "a1")}, f"an exact copy of an earlier question: near_duplicate of a1; got {kinds(two)}"
    three = [base, item("b1", "What is the fee for a deck permit under thirty square metres?", " 120 ")]
    assert kinds(three) == {("b1", "near_duplicate", "a1")}, "golds that agree after norm() (strip, lower-case) are still a plain near_duplicate"
    conflict = [base, item("b1", "What is the fee for a deck permit under thirty square metres?", "150")]
    assert kinds(conflict) == {("b1", "conflicting_gold", "a1")}, "same question, different gold: conflicting_gold (a broken key, not just a copy)"
    nogold = [base, item("b1", "What is the fee for a deck permit under thirty square metres?", "")]
    assert kinds(nogold) == {("b1", "missing_gold", None), ("b1", "near_duplicate", "a1")}, \
        "with a missing gold you cannot call the golds conflicting: report missing_gold AND near_duplicate"
    # threshold and ties
    a = item("a1", "one two three four five six")                     # 4 shingles
    b = item("b1", "one two three four five seven")                   # shares 3 of 5 -> 0.6
    assert kinds([a, b], threshold=0.6) == {("b1", "near_duplicate", "a1")} and kinds([a, b], threshold=0.7) == set(), \
        "similarity >= threshold is flagged (0.6 is flagged at threshold 0.6, not at 0.7)"
    c = item("c1", "one two three four five six")
    assert kinds([a, c, item("d1", "one two three four five six")]) == {("c1", "near_duplicate", "a1"), ("d1", "near_duplicate", "a1")}, \
        "when several earlier items are equally similar, other is the EARLIEST"
    d_ = [dict(x) for x in (a, c)]
    before = json.dumps(d_)
    mod.validate(d_)
    assert json.dumps(d_) == before, "validate must not modify its input"

    # property: distinct random questions have no problems; adding a copy is found
    vocab = [f"w{i}" for i in range(400)]
    for s in seeds(range(1, 16)):
        rng = random.Random(s)
        items = [item(f"r{i}", " ".join(rng.sample(vocab, 9)), str(rng.randint(1, 99))) for i in range(30)]
        assert mod.validate(items) == [], f"seed {s}: 30 random, distinct questions should have no problems; got {mod.validate(items)[:3]}"
        k = rng.randrange(30)
        items.append(dict(items[k], id="copy"))
        got = {(p["id"], p["kind"], p["other"]) for p in mod.validate(items)}
        assert got == {("copy", "near_duplicate", f"r{k}")}, f"seed {s}: an exact copy of r{k} should be the only problem; got {got}"

    # the real draft
    got = {(p["id"], p["kind"], p["other"]) for p in mod.validate(ITEMS)}
    assert got == PLANTED, (f"on the 50-item draft expected exactly the 8 planted defects.\n    missing: {sorted(PLANTED - got, key=str)}\n"
                            f"    unexpected: {sorted(got - PLANTED, key=str)}")
    return ("the draft has 50 items and 8 problems:\n  " + ", ".join(f"{p['id']} {p['kind']}" for p in mod.validate(ITEMS)))


# =============================================================================
# Milestone 2: coverage and splits
# =============================================================================
def oracle_split(group, share):
    return "dev" if int(hashlib.sha256(group.encode()).hexdigest(), 16) % 1000 < share * 1000 else "test"


def m2():
    toy = [item("a", "q1", cat="fees", lv="easy"), item("b", "q2", cat="fees", lv="easy"), item("c", "q3", cat="fees", lv="hard"),
           item("d", "q4", cat="setbacks", lv="medium"), item("e", "q5", cat="nonsense", lv="easy"), item("f", "q6", cat="fees", lv="Hard")]
    cov = mod.coverage(toy)
    assert dict(cov) == {("fees", "easy"): 2, ("fees", "hard"): 1, ("setbacks", "medium"): 1}, \
        f"coverage counts only valid (category, level) cells and leaves out empty ones; got {dict(cov)}"
    thin = mod.thin_cells(toy, 2)
    assert len(thin) == 18 - 1 and thin[0] == ("fees", "medium", 0) and ("fees", "hard", 1) in thin and ("fees", "easy", 2) not in thin, \
        f"thin_cells(min_n=2) lists every cell with fewer than 2 items, empty ones included (17 of the 18 here); got {thin[:3]} ..."
    assert thin == sorted(thin, key=lambda t: (mod.CATEGORIES.index(t[0]), mod.LEVELS.index(t[1]))), "order: by category, then by level"
    assert mod.thin_cells(toy, 0) == [], "min_n=0: no cell has fewer than zero items"

    for g in ("code:4.6", "fee-schedule:B2", "zoning:Z1", ""):
        for share in (0.3, 0.5):
            assert mod.split_of(g, share) == oracle_split(g, share), \
                f"split_of({g!r}, {share}): int(sha256(group).hexdigest(), 16) % 1000 < share * 1000 means dev; expected {oracle_split(g, share)}"
    assert all(mod.split_of(f"g{i}", 0.0) == "test" for i in range(50)) and all(mod.split_of(f"g{i}", 1.0) == "dev" for i in range(50)), \
        "dev_share 0 puts everything in test; 1 puts everything in dev"
    share = sum(mod.split_of(f"group-{i}", 0.3) == "dev" for i in range(3000)) / 3000
    assert abs(share - 0.3) < 0.04, f"over 3,000 groups about 30% should be dev; got {share:.1%}"

    for s in seeds(range(1, 11)):
        rng = random.Random(s)
        srcs = [f"code:{rng.randint(1, 12)}.{rng.randint(1, 9)}" for _ in range(60)]
        items = [item(f"i{n}", f"question {n}", src=src) for n, src in enumerate(srcs)]
        sp = mod.assign_splits(items, 0.3)
        assert set(sp) == {it["id"] for it in items} and set(sp.values()) <= {"dev", "test"}, f"seed {s}: one 'dev' or 'test' per item id"
        by_src = {}
        for it in items:
            by_src.setdefault(it["source"], set()).add(sp[it["id"]])
        assert all(len(v) == 1 for v in by_src.values()), f"seed {s}: items from the same source must land in the same split"
        extra = items + [item(f"new{n}", "another one", src=rng.choice(srcs)) for n in range(10)] + [item("z", "q", src="zoning:Z9")]
        sp2 = mod.assign_splits(extra, 0.3)
        assert all(sp2[k] == v for k, v in sp.items()), f"seed {s}: adding items must never move an existing item between splits (hash the source, not the position)"
        assert mod.assign_splits(list(reversed(items)), 0.3) == sp, f"seed {s}: the order of the items must not matter"

    pair = [item("a", "what is the fee for a deck permit under thirty square metres", src="s1"),
            item("b", "what is the fee for a deck permit under thirty square metres", src="s2"),
            item("c", "completely different words here to avoid any overlap at all today", src="s3"),
            item("d", "what is the fee for a deck permit under thirty square metres", src="s1")]
    got = mod.cross_split_duplicates(pair, {"a": "dev", "b": "test", "c": "dev", "d": "dev"})
    assert got == [("a", "b"), ("b", "d")], (f"a, b and d share a question; b (test) straddles with a and d (both dev) but a and d are twins inside dev. "
                                              f"Expected [('a', 'b'), ('b', 'd')] (pairs ordered by their later item); got {got}")
    got = mod.cross_split_duplicates(pair, {"a": "dev", "b": "test", "c": "dev", "d": "test"})
    assert got == [("a", "b"), ("a", "d")], f"now a (dev) straddles with b and d (both test): expected [('a', 'b'), ('a', 'd')]; got {got}"
    assert mod.cross_split_duplicates(pair, {k: "dev" for k in "abcd"}) == [], "everything in one split: nothing straddles"

    sp = mod.assign_splits(ITEMS, 0.3)
    counts = {s: sum(v == s for v in sp.values()) for s in ("dev", "test")}
    assert counts == {"dev": 15, "test": 34}, (f"on the draft (30% dev, grouped by source) expected 15 dev and 34 test, one entry per distinct id "
                                              f"(49 ids: p020 appears twice); got {counts}")
    cross = mod.cross_split_duplicates(ITEMS, sp)
    assert cross == [("p001", "p046")], (f"the exact copy p046 has a different source (faq:12) from p001 (fee-schedule:B2) and the hash puts them "
                                         f"in different splits: expected [('p001', 'p046')]; got {cross}")
    cells = mod.thin_cells(ITEMS, 2)
    return (f"{len(sp)} distinct ids -> {counts['dev']} dev, {counts['test']} test (grouped by source); "
            f"{len(cells)} of 18 category x difficulty cells hold fewer than 2 items\n"
            f"  the duplicate p046 straddles the split: {cross}")


# =============================================================================
# Milestone 3: versions and fingerprints
# =============================================================================
def oracle_hash(items):
    return hashlib.sha256("\n".join(sorted(json.dumps(i, sort_keys=True) for i in items)).encode()).hexdigest()[:16]


def m3():
    a = [item("x1", "q one", "1"), item("x2", "q two", "2")]
    h = mod.content_hash(a)
    assert h == oracle_hash(a), f"content_hash: sha256 of the sorted json.dumps(item, sort_keys=True) lines joined with newlines, first 16 hex characters; expected {oracle_hash(a)}, got {h}"
    assert mod.content_hash(list(reversed(a))) == h, "the order of the items must not change the hash"
    for field, value in [("gold", "3"), ("question", "q uno"), ("source", "elsewhere"), ("difficulty", "hard"), ("category", "timelines")]:
        b = [dict(a[0], **{field: value}), a[1]]
        assert mod.content_hash(b) != h, f"changing {field} must change the hash (the hash identifies the whole file)"
    assert mod.content_hash(a[:1]) != h and len(h) == 16 and all(c in "0123456789abcdef" for c in h)

    old = [item("x1", "q one", "1"), item("x2", "q two", "2"), item("x3", "q three", "3"), item("x4", "q four", "4")]
    new = [item("x1", "q one", "1", lv="hard"), item("x2", "q two", "22"), item("x4", "q four", "4"), item("x5", "q five", "5")]
    d = mod.diff_items(old, new)
    assert d == {"added": ["x5"], "removed": ["x3"], "edited": ["x2"], "meta": ["x1"]}, f"diff_items: x5 added, x3 removed, x2's gold edited, x1 only metadata; got {d}"
    assert mod.diff_items(old, old) == {"added": [], "removed": [], "edited": [], "meta": []}
    assert raises(ValueError, mod.diff_items, old + [item("x1", "again")], new), "duplicate ids make a diff meaningless: ValueError"

    assert mod.classify(old, old)[0] == "patch", "no change at all: patch"
    meta = [dict(x, source="moved") for x in old]
    assert mod.classify(old, meta)[0] == "patch", "metadata only: patch (every earlier score is still valid)"
    lvl, why = mod.classify(old, new)
    assert lvl == "minor" and "1 added" in why and "1 removed" in why and "1 edited" in why, f"minor, and the reason names the counts ('1 added, 1 removed, 1 edited'); got {lvl!r}, {why!r}"
    assert mod.classify(old, old + [item("x9", "new")])[0] == "minor", "an added item: minor"
    assert mod.classify(old, old[:-1])[0] == "minor", "a removed item: minor"
    assert mod.classify(old, old, scoring_changed=True)[0] == "major", "a changed scoring rule is major even if no item changed"
    assert mod.classify(old, new, scoring_changed=True)[0] == "major"

    for v, lv, want in [("1.0.0", "minor", "1.1.0"), ("1.4.7", "minor", "1.5.0"), ("1.4.7", "major", "2.0.0"), ("1.4.7", "patch", "1.4.8"), ("0.9.9", "patch", "0.9.10")]:
        assert mod.bump_version(v, lv) == want, f"bump_version({v!r}, {lv!r}) should be {want!r}; got {mod.bump_version(v, lv)!r} (minor resets patch; major resets both)"
    for v, lv in [("1.0", "minor"), ("a.b.c", "patch"), ("1.0.0", "huge")]:
        assert raises(ValueError, mod.bump_version, v, lv), f"bump_version({v!r}, {lv!r}) must raise ValueError"

    # scenario: release v1.0.0, then fix the draft and ship v1.1.0
    seen, v1 = set(), []
    for it in ITEMS:
        if it["id"] not in seen:                     # v1.0.0 as first released: the duplicate id dropped, everything else as drafted
            seen.add(it["id"])
            v1.append(it)
    v11 = []
    for it in v1:
        if it["id"] in ("p046", "p047", "p048"):
            continue                                 # the three duplicates are removed
        it = dict(it)
        if it["id"] == "p043":
            it["gold"] = "100"                       # a missing key supplied
        if it["id"] == "p050":
            it["gold"] = "12"
        if it["id"] == "p044":
            it["category"] = "setbacks"              # metadata fixes
        if it["id"] == "p045":
            it["difficulty"] = "medium"
        v11.append(it)
    assert mod.validate(v11) == [], f"after the fixes the validator should be silent; got {mod.validate(v11)}"
    lvl, why = mod.classify(v1, v11)
    assert lvl == "minor" and "0 added" in why and "3 removed" in why and "2 edited" in why, f"v1 -> v1.1: 0 added, 3 removed, 2 edited -> minor; got {lvl!r}, {why!r}"
    assert mod.bump_version("1.0.0", lvl) == "1.1.0"
    h1, h2 = mod.content_hash(v1), mod.content_hash(v11)
    assert h1 == oracle_hash(v1) and h2 == oracle_hash(v11) and h1 != h2
    return (f"v1.0.0 ({len(v1)} items) hash {h1}\n"
            f"  v1.1.0 ({len(v11)} items) hash {h2}   -> bump {lvl}: {why}")


# =============================================================================
# Milestone 4: contamination probe
# =============================================================================
def m4():
    assert mod.ngrams("a b c d", 2) == {"a b", "b c", "c d"} and mod.ngrams("A, b!", 3) == set(), "ngrams: word n-grams, lower-cased; fewer than n words gives the empty set"
    assert near(mod.overlap("a b c d e", "x a b c d y", 3), 2 / 3), "item 3-grams {abc, bcd, cde}; the document has abc and bcd: 2/3"
    assert mod.overlap("a b", "a b c", 3) == 0.0, "an item shorter than n words has no n-grams: overlap 0.0, not a ZeroDivisionError"
    assert mod.overlap("a b c d", "", 2) == 0.0 and mod.overlap("a b c d", "a b c d", 2) == 1.0
    assert near(mod.overlap("a b c d", "d c b a", 2), 0.0), "order matters: an n-gram is a consecutive run"

    toy_items = [item("t1", "one two three four five six seven eight nine"), item("t2", "alpha beta gamma delta epsilon zeta eta theta iota"),
                 item("t3", "completely unrelated words that appear nowhere else at all today")]
    toy_corpus = {"zeta-doc": "intro one two three four five six seven eight nine outro",
                  "alpha-doc": "one two three four five six seven eight nine and more",
                  "partial": "alpha beta gamma delta epsilon zeta eta then different tail words",
                  "noise": "nothing to see here"}
    f = mod.scan_corpus(toy_items, toy_corpus, n=3, threshold=0.5)
    assert [(x["id"], x["doc"]) for x in f] == [("t1", "alpha-doc"), ("t2", "partial")], \
        f"documents are tried in sorted name order and the first best one wins (a tie goes to alpha-doc, not zeta-doc); got {[(x['id'], x['doc']) for x in f]}"
    assert near(f[0]["overlap"], 1.0) and near(f[1]["overlap"], 5 / 7), f"t2: 7 3-grams, 5 shared with 'partial'; got {f[1]['overlap']}"
    assert [x["id"] for x in mod.scan_corpus(toy_items, toy_corpus, n=3, threshold=5 / 7)] == ["t1", "t2"], "overlap >= threshold is flagged (inclusive)"
    assert [x["id"] for x in mod.scan_corpus(toy_items, toy_corpus, n=3, threshold=0.8)] == ["t1"]
    assert mod.scan_corpus(toy_items, {}, n=3) == [], "an empty corpus finds nothing"

    assert mod.canary_docs({"b": "x CANARY y", "a": "has CANARY", "c": "canary lower"}, "CANARY") == ["a", "b"], "sorted names of the documents containing the canary, case-sensitive"
    m = mod.leak_metrics({1, 2, 3}, {2, 3, 4, 5})
    assert (m["tp"], m["fp"], m["fn"]) == (2, 1, 2) and near(m["precision"], 2 / 3) and near(m["recall"], 0.5), f"found {{1,2,3}} vs truth {{2,3,4,5}}: tp 2, fp 1, fn 2, precision 2/3, recall 1/2; got {m}"
    assert mod.leak_metrics([], {1})["precision"] is None and mod.leak_metrics({1}, [])["recall"] is None, "nothing found: precision None; nothing to find: recall None"
    assert mod.leak_metrics(["a", "a", "b"], ["a"])["tp"] == 1, "ids are sets: a repeated id counts once"

    for s in seeds(range(1, 11)):
        rng = random.Random(s)
        vocab = [f"v{i}" for i in range(300)]
        qs = {f"i{n}": rng.sample(vocab, 12) for n in range(12)}
        its = [item(i, " ".join(w)) for i, w in qs.items()]
        leaked = set(rng.sample(sorted(qs), 5))
        corpus = {f"d{n}": " ".join(rng.sample(vocab, 40)) for n in range(6)}
        for i in leaked:
            corpus[f"copy-{i}"] = "prefix words " + " ".join(qs[i]) + " suffix words"
        got = {x["id"] for x in mod.scan_corpus(its, corpus, n=8, threshold=0.5)}
        assert got == leaked, f"seed {s}: the verbatim copies {sorted(leaked)} should be found and nothing else; got {sorted(got)}"

    f8 = mod.scan_corpus(ITEMS, CORPUS, n=8)
    ids8 = {x["id"] for x in f8}
    assert ids8 == LEAKED_VERBATIM, f"8-grams should find exactly the nine verbatim leaks; missing {sorted(LEAKED_VERBATIM - ids8)}, extra {sorted(ids8 - LEAKED_VERBATIM)}"
    f3 = mod.scan_corpus(ITEMS, CORPUS, n=3)
    ids3 = {x["id"] for x in f3}
    assert ids3 == LEAKED_VERBATIM | {"p043"}, f"3-grams find the same nine plus one false alarm (p043); got extra {sorted(ids3 - LEAKED_VERBATIM)}, missing {sorted(LEAKED_VERBATIM - ids3)}"
    canary = mod.canary_docs(CORPUS, mod.CANARY)
    assert canary == ["benchmark-repo-copy"], f"the canary string is in exactly one document; got {canary}"
    m8, m3_ = mod.leak_metrics(ids8, LEAKED_ALL), mod.leak_metrics(ids3, LEAKED_ALL)
    assert near(m8["precision"], 1.0) and near(m8["recall"], 0.5) and near(m3_["precision"], 0.9) and near(m3_["recall"], 0.5)
    return (f"{len(ITEMS)} questions against {len(CORPUS)} crawl documents ({len(LEAKED_ALL)} questions leaked in some form, 9 of them verbatim)\n"
            f"  8-gram overlap >= 50%: found {len(ids8)}, precision {m8['precision']:.0%}, recall {m8['recall']:.0%}\n"
            f"  3-gram overlap >= 50%: found {len(ids3)}, precision {m3_['precision']:.0%}, recall {m3_['recall']:.0%}  (shorter n-grams buy false alarms, not rewrites)\n"
            f"  canary string found in: {', '.join(canary)}")


# =============================================================================
# Milestone 5: the fresh-variant gap test
# =============================================================================
def oracle_gap(o, v, B, alpha, seed):
    d = [x - y for x, y in zip(o, v)]
    n = len(d)
    rng = random.Random(seed)
    xs = sorted(sum(d[rng.randrange(n)] for _ in range(n)) / n for _ in range(B))
    return xs[int(alpha / 2 * B)], xs[int((1 - alpha / 2) * B) - 1]


def m5():
    from llm import RuleModel
    orig = [("Q1", "1"), ("Q2", "2"), ("Q3", "3"), ("Q4", "4")]
    var = [("R1", "1"), ("R2", "2"), ("R3", "3"), ("R4", "4")]
    model = RuleModel([("^Q1$", "1"), ("^Q2$", "2"), ("^Q3$", "9"), ("^Q4$", "4"), ("^R1$", "1")], default="9")
    r = mod.gap_test(model, orig, var, B=200, alpha=0.1, seed=3)
    assert near(r["acc_original"], 0.75) and near(r["acc_fresh"], 0.25) and near(r["gap"], 0.5), \
        f"toy model: right on Q1, Q2, Q4 (3 of 4) and only R1 (1 of 4): accuracies 0.75 and 0.25, gap 0.5; got {r}"
    lo, hi = oracle_gap([1, 1, 0, 1], [1, 0, 0, 0], 200, 0.1, 3)
    assert near(r["ci"][0], lo) and near(r["ci"][1], hi), (f"expected the percentile bootstrap interval ({lo:.3f}, {hi:.3f}) with random.Random(3), 200 resamples of the "
                                                         f"4 template indices and alpha 0.1; got {tuple(round(x, 3) for x in r['ci'])}. Resample the paired differences, "
                                                         "and sort the B gaps")
    assert r["leak_detected"] == (lo > 0)
    same = FX.make_model([])
    assert raises(ValueError, mod.gap_test, same, orig, var[:3]) and raises(ValueError, mod.gap_test, same, [], []), "unequal or empty lists: ValueError"
    assert mod.gap_test(model, orig, var, B=200, alpha=0.1, seed=3) == r, "same seed, same answer"

    originals, variants = FX.make_problems(150)
    rows = []
    for memorised, detected in [(0, False), (30, False), (60, True), (105, True)]:
        mdl = FX.make_model(originals[:memorised])
        g = mod.gap_test(mdl, originals, variants, B=2000, seed=0)
        o, v = FX.correct_flags(mdl, originals), FX.correct_flags(mdl, variants)
        lo, hi = oracle_gap(o, v, 2000, 0.05, 0)
        assert near(g["gap"], (sum(o) - sum(v)) / 150) and near(g["ci"][0], lo) and near(g["ci"][1], hi), f"{memorised} memorised: expected CI ({lo:.3f}, {hi:.3f}); got {g['ci']}"
        assert g["leak_detected"] is detected, (f"with {memorised} of 150 items memorised the gap is {g['gap']:+.1%} (CI {g['ci'][0]:+.1%} to {g['ci'][1]:+.1%}): "
                                                f"leak_detected should be {detected}")
        rows.append((memorised, g))
    lines = ["a 70%-ability model that has memorised k of 150 original questions, 150 fresh variants (paired by template):"]
    for k, g in rows:
        lines.append(f"  k={k:3d}  original {g['acc_original']:.0%}  fresh {g['acc_fresh']:.0%}  gap {g['gap']:+.1%}  95% CI {g['ci'][0]:+.1%} to {g['ci'][1]:+.1%}  leak detected: {g['leak_detected']}")
    return "\n".join(lines)


MILESTONES = [
    (1, "Milestone 1: validate the items", m1),
    (2, "Milestone 2: coverage and stable, grouped splits", m2),
    (3, "Milestone 3: a version and a fingerprint", m3),
    (4, "Milestone 4: a contamination probe", m4),
    (5, "Milestone 5: the fresh-variant gap test", m5),
]

if __name__ == "__main__":
    t0 = time.time()
    print(f"Lab 3 checks against {target}.py\n")
    for n, name, fn in MILESTONES:
        check(n, name, fn)
    print(f"\n{sum(results)}/{len(results)} milestones passing  ({time.time() - t0:.1f} s)")
    sys.exit(0 if all(results) else 1)
