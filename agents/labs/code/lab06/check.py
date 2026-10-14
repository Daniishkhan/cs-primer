"""Self-check for Lab 6: A Mini Deep-Research Agent.

    python3 check.py                  # checks your starter.py
    python3 check.py solution         # checks the reference solution
    python3 check.py solution 4       # only milestone 4
    python3 check.py solution 4 7     # milestone 4, replaying ONLY the random case of seed 7

Everything is deterministic: the corpus (corpus.json), the BM25 search and the three stand-in models
live in fixtures.py, there is no network and no real clock, and the random cases are seeded; a failure
prints the seed. The whole check takes about a second. Prints a tick, a cross, or "not implemented
yet" for each milestone.
"""
import importlib
import json
import random
import re
import signal
import sys
import threading
import time

import os

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True

args = sys.argv[1:]
target = args[0] if args and not args[0].isdigit() else "starter"
rest = [a for a in args if a.isdigit()]
ONLY = int(rest[0]) if rest else None
ONLY_SEED = int(rest[1]) if len(rest) > 1 else None
mod = importlib.import_module(target)
from fixtures import (FARES, POTHOLES, QUESTIONS, READER, ROADS, Index, load_docs, make_models,  # noqa: E402
                      make_planner, make_reader, reader_prompt, writer_prompt)
from llm import ScriptedModel  # noqa: E402

results = []
DOCS = load_docs()
IDX = Index(DOCS)


def seeds(default):
    return [ONLY_SEED] if ONLY_SEED is not None else list(default)


def check(number, name, fn):
    if ONLY is not None and ONLY != number:
        return
    if hasattr(signal, "SIGALRM"):                 # a hang is a failure, not a freeze
        def _timeout(signum, frame):
            raise AssertionError("no answer after 25 seconds: is something waiting for ever (a loop, a thread)?")
        signal.signal(signal.SIGALRM, _timeout)
        signal.alarm(25)
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
    finally:
        if hasattr(signal, "SIGALRM"):
            signal.alarm(0)


def near(a, b, tol=1e-9):
    return abs(a - b) <= tol * max(1.0, abs(a), abs(b))


def doc(id, kind="primary", derived=None, supersedes=(), text="", title=None, date="2025-01-01"):
    return {"id": id, "title": title or f"Title of {id}", "kind": kind, "date": date, "derived_from": derived,
            "supersedes": list(supersedes), "text": text}


def claim(doc_id, metric, year, value, quote="some quote here", id=None):
    c = {"doc": doc_id, "metric": metric, "year": year, "value": value, "quote": quote}
    if id:
        c["id"] = id
    return c


def first_difference(want, got):
    wl, gl = want.splitlines(), got.splitlines()
    for i in range(max(len(wl), len(gl))):
        a = wl[i] if i < len(wl) else "<no line>"
        b = gl[i] if i < len(gl) else "<no line>"
        if a != b:
            return f"line {i + 1}:\n          expected {a!r}\n          got      {b!r}"
    return "(identical)"


# =============================================================================
# Milestone 1: plan
# =============================================================================
def m1():
    P = mod.parse_json_list
    cases = [('["a", "b"]', ["a", "b"]), ('  [1, 2]  ', [1, 2]), ("[]", []), ('```json\n["x", "y"]\n```', ["x", "y"]),
             ('```\n["x"]\n```', ["x"]), ('Here you go:\n```json\n["x"]\n```\nHope that helps.', ["x"]),
             ("just some prose", None), ('{"queries": ["a"]}', None), ('["a", "b', None), ("", None), ("```", None), ("null", None), ('"a"', None)]
    for reply, want in cases:
        got = P(reply)
        assert got == want, f"parse_json_list({reply!r}) should be {want!r}; got {got!r}"
    q = QUESTIONS["roads"]
    planner = make_planner()
    got = mod.plan(planner, q)
    assert got == ["road repair spending 2024", "Northvale spent on roads in 2024", "road repair spending 2023", "storm damage road repair increase"], f"a clean list should pass through unchanged; got {got}"
    assert len(planner.calls) == 1 and [m["role"] for m in planner.calls[0]["messages"]] == ["user"] and planner.calls[0]["messages"][0]["content"] == mod.plan_prompt(q), \
        f"send the planner exactly ONE user message, plan_prompt(question); sent {planner.calls[0]['messages']}"
    got = mod.plan(make_planner(), QUESTIONS["potholes"])
    assert got == ["pothole repairs 2024", "potholes repaired by the contractor", "potholes repaired by council crews", "pothole response time"], \
        f"a fenced list with duplicates (differing in case or spaces), a number and blank strings should be cleaned to four queries; got {got}"
    got = mod.plan(make_planner(), "  " + QUESTIONS["fares"] + " ")
    assert got == [QUESTIONS["fares"]], f"when the reply is prose, fall back to the (stripped) question; got {got}"

    def scripted(reply):
        return ScriptedModel([reply])
    assert mod.plan(scripted('["a","b","c","d","e","f"]'), "q") == ["a", "b", "c", "d"], "keep at most max_queries (4 by default), in order"
    assert mod.plan(scripted('["a","b","c","d","e","f"]'), "q", max_queries=2) == ["a", "b"]
    assert mod.plan(scripted('[3, null, "", "   ", {"q": "x"}]'), "the question ") == ["the question"], "junk only: fall back to the question"
    assert mod.plan(scripted("[]"), "Q?") == ["Q?"] and mod.plan(scripted("not json"), "Q?") == ["Q?"]
    assert mod.plan(scripted('["Road repair", "road   repair ", "ROAD REPAIR", "bus fares"]'), "q") == ["Road repair", "bus fares"], "duplicates that differ only in case or spacing: keep the first spelling"
    for seed in seeds(range(1, 31)):
        rnd = random.Random(seed)
        pool = ["alpha", "Alpha", " alpha ", "beta gamma", "beta  gamma", "delta", "", "  ", 3, None, 2.5, ["x"], "epsilon", "Zeta"]
        items = [rnd.choice(pool) for _ in range(rnd.randint(0, 9))]
        mq = rnd.randint(1, 5)
        got = mod.plan(scripted(json.dumps(items)), "FALLBACK", max_queries=mq)
        seen, want = set(), []
        for it in items:
            if isinstance(it, str) and it.strip() and " ".join(it.lower().split()) not in seen:
                seen.add(" ".join(it.lower().split()))
                want.append(it.strip())
        want = want[:mq] or ["FALLBACK"]
        assert got == want, f"seed {seed}: for {items!r} with max_queries={mq} expected {want}; got {got}"
    return "list parsing (fences, prose, truncation), one clean planner call, de-duplication, the cap, the fallback and 30 random replies"


# =============================================================================
# Milestone 2: search in parallel, then triage
# =============================================================================
class SlowIndex:
    """Wraps the real index; every search sleeps, and we watch how many run at the same time."""

    def __init__(self, inner, delays=None, boom=()):
        self.inner, self.delays, self.boom = inner, delays or {}, set(boom)
        self.active = self.peak = 0
        self.lock = threading.Lock()

    def search(self, q, k=6):
        with self.lock:
            self.active += 1
            self.peak = max(self.peak, self.active)
        try:
            time.sleep(self.delays.get(q, 0.1))
            if q in self.boom:
                raise RuntimeError("search backend unavailable")
            return self.inner.search(q, k)
        finally:
            with self.lock:
                self.active -= 1


def m2():
    qs = ["road repair spending 2024", "Northvale spent on roads in 2024", "road repair spending 2023", "storm damage road repair increase"]
    got = mod.search_all(IDX, qs, k=3)
    assert got == [IDX.search(q, 3) for q in qs], "search_all returns one result list per query, in the order of the queries, each cut to k"
    assert mod.search_all(IDX, []) == [], "no queries, no results"
    slow = SlowIndex(IDX)
    t0 = time.time()
    got = mod.search_all(slow, qs, k=4, workers=4)
    took = time.time() - t0
    assert slow.peak >= 3 and took < 0.3, f"four searches that each take 0.1 s must overlap: at most {slow.peak} ran together and the whole thing took {took:.2f} s (sequential would be 0.4 s). Use a thread pool"
    assert got == [IDX.search(q, 4) for q in qs]
    slow = SlowIndex(IDX)
    mod.search_all(slow, qs, workers=2)
    assert slow.peak == 2, f"workers=2 means exactly two searches at a time; saw {slow.peak}"
    slow = SlowIndex(IDX, delays={qs[0]: 0.25, qs[1]: 0.0})
    got = mod.search_all(slow, qs, k=2, workers=4)
    assert got == [IDX.search(q, 2) for q in qs], "the first query finishes LAST, but its results must still come first"
    slow = SlowIndex(IDX, delays={q: 0.01 for q in qs}, boom=[qs[1]])
    got = mod.search_all(slow, qs, k=2)
    assert got[1] == [] and got[0] == IDX.search(qs[0], 2) and got[2] == IDX.search(qs[2], 2), "a query whose search raises contributes [] and the others still count"
    # merge
    per = [[("d1", 8.0), ("d2", 4.0)], [("d2", 3.0), ("d3", 1.0)], [], [("d9", 0.0)]]
    m = mod.merge(per)
    assert set(m) == {"d1", "d2", "d3"} and near(m["d1"], 1.0) and near(m["d2"], 1.0) and near(m["d3"], 1 / 3), \
        f"each query's scores are divided by its best; a document keeps the highest value: expected d1 1.0, d2 1.0, d3 0.333; got {m}"
    assert mod.merge([]) == {} and mod.merge([[], []]) == {}
    # triage: values are relevance x (0.5 + prior / 2): primary x1, news x0.8, blog x0.65, forum x0.55
    docs = {"d1": doc("d1", "primary"), "d2": doc("d2", "news"), "d3": doc("d3", "blog"), "d4": doc("d4", "forum"),
            "d10": doc("d10", "primary"), "d7": doc("d7", "primary")}
    rel = {"d1": 0.9, "d2": 0.6, "d3": 0.5, "d4": 0.9, "d10": 0.3}
    got = mod.triage(rel, docs, threshold=0.4, max_docs=8)
    assert got == (["d1", "d2", "d4"], ["d3", "d10"]), f"values are d1 0.9, d2 0.48, d3 0.325, d4 0.495, d10 0.3; threshold 0.4 keeps d1, d2, d4 (natural order: d3 before d10 in skipped). Got {got}"
    got = mod.triage(rel, docs, threshold=0.4, max_docs=2)
    assert got == (["d1", "d4"], ["d2", "d3", "d10"]), f"max_docs=2 keeps the two highest values (d1 0.9, d4 0.495); got {got}"
    got = mod.triage({"d7": 0.8, "d1": 0.8}, docs, threshold=0.1, max_docs=1)
    assert got == (["d1"], ["d7"]), f"equal values: the lower document number wins; got {got}"
    assert mod.triage({}, docs) == ([], [])
    for seed in seeds(range(1, 31)):
        rnd = random.Random(seed)
        kinds = ["primary", "news", "blog", "forum"]
        dd = {f"d{i}": doc(f"d{i}", rnd.choice(kinds)) for i in range(1, rnd.randint(2, 25))}
        rel = {d: round(rnd.random(), 3) for d in dd if rnd.random() < 0.8}
        th, mx = rnd.choice([0.2, 0.35, 0.5]), rnd.randint(1, 6)
        pri = {"primary": 1.0, "news": 0.6, "blog": 0.3, "forum": 0.1}
        val = {d: r * (0.5 + pri[dd[d]["kind"]] / 2) for d, r in rel.items()}
        cand = sorted((d for d in val if val[d] >= th), key=lambda d: (-val[d], int(d[1:])))[:mx]
        want = (sorted(cand, key=lambda d: int(d[1:])), sorted(set(rel) - set(cand), key=lambda d: int(d[1:])))
        got = mod.triage(rel, dd, th, mx)
        assert got == want, f"seed {seed}: threshold {th}, max_docs {mx}: expected {want}; got {got}"
    # the real thing: the roads question
    hits = mod.search_all(IDX, mod.plan(make_planner(), QUESTIONS["roads"]), k=6)
    to_read, skipped = mod.triage(mod.merge(hits), DOCS)
    assert to_read == ["d1", "d2", "d3", "d5", "d6", "d7", "d8", "d9"] and skipped == ["d4", "d14"], \
        f"for the roads question the default triage should read d1, d2, d3, d5, d6, d7, d8, d9 and skip the blog d4 and the pothole blog d14; got read {to_read}, skipped {skipped}"
    return "parallel (and bounded, ordered, fault-tolerant) search, merge, hand-checked triage, 30 random triage cases, and the roads question"


# =============================================================================
# Milestone 3: read
# =============================================================================
def m3():
    q = QUESTIONS["roads"]
    reader = make_reader()
    rr = mod.read_docs(reader, q, ["d1", "d2"], DOCS)
    want = [{**c, "id": f"c{i}"} for i, c in enumerate(READER["d1"] + READER["d2"], 1)]
    assert rr.claims == want and rr.malformed == [] and rr.unreadable == [], f"d1 and d2 give four valid claims c1 to c4; got {rr.claims}"
    assert len(reader.calls) == 2, f"one reader call per document; got {len(reader.calls)}"
    for call, d in zip(reader.calls, ["d1", "d2"]):
        msgs = call["messages"]
        assert len(msgs) == 1 and msgs[0]["role"] == "user" and msgs[0]["content"] == reader_prompt(q, DOCS[d]), f"each reader sees ONE user message, reader_prompt(question, document), in its own context; for {d} it got {msgs}"
        other = "d2" if d == "d1" else "d1"
        assert DOCS[other]["text"] not in msgs[0]["content"], "a reader must not see another document's text"
    # a bigger read: the roads documents with their mistakes
    ids = ["d1", "d2", "d3", "d4", "d5", "d6", "d7", "d8", "d9"]
    rr = mod.read_docs(make_reader(), q, ids, DOCS)
    assert [c["id"] for c in rr.claims] == [f"c{i}" for i in range(1, 15)], f"ids count across all documents: c1 to c14; got {[c['id'] for c in rr.claims]}"
    assert rr.malformed == [("d9", "claim names another document")] and rr.unreadable == [], f"d9's second claim is credited to d8; got {rr.malformed}"
    assert [c["doc"] for c in rr.claims][-4:] == ["d8", "d8", "d8", "d9"] and rr.claims[5]["quote"] == "the council confirmed a 24 per cent rise", \
        "reading does not check quotes: the invented d3 quote is still a claim here (Milestone 4 rejects it)"
    rr = mod.read_docs(make_reader(), QUESTIONS["potholes"], ["d10", "d11", "d12", "d15"], DOCS)
    assert [c["doc"] for c in rr.claims] == ["d10", "d11", "d12"] and rr.malformed == [("d12", "missing field value")] and rr.unreadable == ["d15"], \
        f"d12 has a claim with no value, d15's reply is prose; got claims {[c['doc'] for c in rr.claims]}, malformed {rr.malformed}, unreadable {rr.unreadable}"
    # every kind of bad claim
    good = {"doc": "d1", "metric": "m", "year": 2024, "value": 4.2, "quote": "a b c d"}
    bad = [("oops", "not an object"), ([1], "not an object"),
           ({k: v for k, v in good.items() if k != "doc"}, "missing field doc"), ({k: v for k, v in good.items() if k != "metric"}, "missing field metric"),
           ({k: v for k, v in good.items() if k != "year"}, "missing field year"), ({k: v for k, v in good.items() if k != "value"}, "missing field value"),
           ({k: v for k, v in good.items() if k != "quote"}, "missing field quote"),
           ({**good, "year": "2024"}, "wrong type for year"), ({**good, "year": True}, "wrong type for year"), ({**good, "year": 2024.0}, "wrong type for year"),
           ({**good, "value": "4.2"}, "wrong type for value"), ({**good, "value": True}, "wrong type for value"), ({**good, "value": None}, "wrong type for value"),
           ({**good, "metric": 5}, "wrong type for metric"), ({**good, "quote": None}, "wrong type for quote"), ({**good, "doc": 1}, "wrong type for doc"),
           ({**good, "doc": "d2"}, "claim names another document")]
    keep = {**good, "value": 7, "note": "extra keys are fine"}
    reply = json.dumps([b for b, _ in bad] + [keep])
    rr = mod.read_docs(ScriptedModel([reply]), "q", ["d1"], DOCS)
    assert rr.malformed == [("d1", r) for _, r in bad], "reasons in order:\n        expected " + "\n                 ".join(r for _, r in bad) + "\n        got      " + "\n                 ".join(r for _, r in rr.malformed)
    assert rr.claims == [{**keep, "id": "c1"}], f"the one good claim (an int value, an extra key) is kept with its id; got {rr.claims}"
    rr = mod.read_docs(ScriptedModel(['```json\n[{"doc":"d1","metric":"m","year":1,"value":2,"quote":"x y z"}]\n```', "[]", "no json here", '{"doc": "d1"}']), "q", ["d1", "d2", "d3", "d4"], DOCS)
    assert [c["id"] for c in rr.claims] == ["c1"] and rr.unreadable == ["d3", "d4"], f"a fenced reply is read, [] is readable with no claims, prose and an object are unreadable; got {rr.claims}, {rr.unreadable}"
    return "isolated reader calls, ids across documents, and every kind of malformed claim and reply"


# =============================================================================
# Milestone 4: the citation checker
# =============================================================================
NUM = re.compile(r"\d+(?:,\d{3})*(?:\.\d+)?")


def m4():
    docs = {"d1": doc("d1", text="Road maintenance and repair expenditure in 2024 was 4.2 million pounds.\nExpenditure in 2023 was 3.4 million pounds."),
            "d2": doc("d2", text="Highways teams repaired 1,350 potholes in 2024.")}
    ok = [claim("d1", "m", 2024, 4.2, "expenditure in 2024 was 4.2 million pounds"),
          claim("d1", "m", 2023, 3.4, "pounds. EXPENDITURE   in 2023 was\n3.4 million"),
          claim("d2", "p", 2024, 1350, "repaired 1,350 potholes in 2024"),
          claim("d2", "p", 2024, 1350.0, "Highways teams repaired 1,350 potholes")]
    v, r = mod.verify_claims(ok, docs)
    assert v == ok and r == [], f"all four are genuine (case, whitespace, a newline and '1,350' do not matter); rejected: {r}"
    bad = [(claim("d9", "m", 1, 4.2, "expenditure in 2024 was 4.2 million pounds"), "unknown document"),
           (claim("d9", "m", 1, 4.2, ""), "unknown document"),
           (claim("d1", "m", 1, 4.2, ""), "empty quote"), (claim("d1", "m", 1, 4.2, "   \n "), "empty quote"),
           (claim("d1", "m", 1, 4.2, "4.2 million"), "quote too short"), (claim("d1", "m", 1, 4.2, "was 4.2"), "quote too short"),
           (claim("d1", "m", 1, 4.2, "of the road"), "quote not in source"),
           (claim("d1", "m", 1, 4.5, "expenditure in 2024 was 4.5 million pounds"), "quote not in source"),
           (claim("d1", "m", 1, 4.2, "expenditure in 2024 was about 4.2 million pounds"), "quote not in source"),
           (claim("d1", "m", 1, 4.3, "expenditure in 2024 was 4.2 million pounds"), "value not in quote"),
           (claim("d1", "m", 1, 24, "expenditure in 2024 was 4.2 million pounds"), "value not in quote"),
           (claim("d1", "m", 1, 4, "expenditure in 2024 was 4.2 million pounds"), "value not in quote"),
           (claim("d2", "m", 1, 135, "repaired 1,350 potholes in 2024"), "value not in quote")]
    for c, reason in bad:
        v, r = mod.verify_claims([c], docs)
        assert v == [] and len(r) == 1 and r[0]["claim"] is c and r[0]["reason"] == reason, \
            f"claim {c['value']!r} with quote {c['quote']!r} from {c['doc']}: expected rejection '{reason}'; got verified={len(v)}, rejected={[x['reason'] for x in r]}"
    mixed = [ok[0], bad[2][0], ok[2], bad[7][0]]
    v, r = mod.verify_claims(mixed, docs)
    assert v == [ok[0], ok[2]] and [x["reason"] for x in r] == ["empty quote", "quote not in source"], "both lists keep the input order"
    for seed in seeds(range(1, 41)):
        rnd = random.Random(seed)
        words = [rnd.choice(["road", "repair", "the", "council", "spent", "on", "in", "pounds", "of", "grant", "paid"]) if rnd.random() < 0.75 else f"{rnd.randint(1, 99)}.{rnd.randint(1, 9)}" for _ in range(30)]
        text = " ".join(words)
        d = {"dx": doc("dx", text=text)}
        i = rnd.randint(0, 22)
        window = words[i:i + rnd.randint(3, 6)]
        nums = [w for w in window if NUM.fullmatch(w)]
        if not nums:
            continue
        quote = " ".join(window)
        quote = "".join(ch.upper() if rnd.random() < 0.3 else ch for ch in quote).replace(" ", rnd.choice([" ", "  ", "\n"]))
        v, r = mod.verify_claims([claim("dx", "m", 1, float(nums[0]), quote)], d)
        assert len(v) == 1, f"seed {seed}: a real window of the text, with changed case and spacing, must verify; quote {quote!r}, rejected for {[x['reason'] for x in r]}"
        j = rnd.choice([k for k, w in enumerate(window) if not NUM.fullmatch(w)] or [None]) if any(not NUM.fullmatch(w) for w in window) else None
        if j is not None:
            altered = list(window)
            altered[j] = "zzzz"
            v, r = mod.verify_claims([claim("dx", "m", 1, float(nums[0]), " ".join(altered))], d)
            assert len(v) == 0 and r[0]["reason"] == "quote not in source", f"seed {seed}: changing one word of the quote ({altered!r}) must make it 'quote not in source'; got {[x['reason'] for x in r]}"
    # the sentence audit
    cl = [claim("d1", "road repair spend", 2024, 4.2, id="c1"), claim("d2", "road repair spend", 2023, 3.4, id="c2"), claim("d3", "potholes", 2024, 1350, id="c3")]
    A = lambda *s: [(a.sentence, a.problems, a.ok) for a in mod.audit_draft(list(s), cl)]
    cases = [
        ("Road repair spending in 2024 was 4.2 million pounds [c1].", []),
        ("It was 4.2 million in 2024, up from 3.4 million in 2023 [c1][c2].", []),
        ("Up from 3.4 million pounds in 2023 [c1].", ["3.4 is not in the cited claims", "2023 is not in the cited claims"]),
        ("Spending was driven by storm damage.", ["no citation"]),
        ("It rose 24 per cent.", ["no citation", "24 is not in the cited claims"]),
        ("The rise is 24 per cent [c2].", ["24 is not in the cited claims"]),
        ("Roads improved [c99][c1][c99].", ["unknown claim c99"]),
        ("Roads improved [c99].", ["unknown claim c99"]),
        ("About 1,350 potholes were repaired [c3].", []),
        ("Potholes: 1350 [c3], and 4.2 [c3].", ["4.2 is not in the cited claims"]),
        ("In 2024 [c1].", []),
        ("Both 4.5 and 4.5 are wrong [c1].", ["4.5 is not in the cited claims"]),
        ("Cited twice [c1][c1].", []),
        ("Also 0.8 and 12 [c1][c2][c77].", ["unknown claim c77", "0.8 is not in the cited claims", "12 is not in the cited claims"]),
    ]
    for sentence, problems in cases:
        (s, p, okk), = A(sentence)
        assert s == sentence and p == problems and okk == (not problems), f"audit of {sentence!r}: expected problems {problems}; got {p}"
    assert [a.sentence for a in mod.audit_draft([c[0] for c in cases], cl)] == [c[0] for c in cases] and mod.audit_draft([], cl) == [], "one Audit per sentence, in order"
    for seed in seeds(range(1, 31)):
        rnd = random.Random(seed)
        cited = rnd.sample(cl, rnd.randint(1, 3))
        parts = [f"In {c['year']} it was {format(c['value'], ',g')}" for c in cited]
        s = "; ".join(parts) + " " + "".join(f"[{c['id']}]" for c in cited) + "."
        assert A(s)[0][1] == [], f"seed {seed}: every number comes from a cited claim, so {s!r} is clean; got {A(s)[0][1]}"
        extra = rnd.choice([777.5, 31, 0.25])
        s2 = s.replace(" [", f" and {format(extra, 'g')} [", 1)
        assert A(s2)[0][1] == [f"{format(extra, 'g')} is not in the cited claims"], f"seed {seed}: {s2!r} adds a number no cited claim contains; got {A(s2)[0][1]}"
        s3 = re.sub(r"\[c\d\]", "", s)
        assert A(s3)[0][1][:1] == ["no citation"], f"seed {seed}: without markers the first problem is 'no citation'; got {A(s3)[0][1]}"
    return "claims against documents (5 reasons, 13 hand-made rejections, 40 random quotes), sentences against claims (14 cases, 30 random sentences)"


# =============================================================================
# Milestone 5: cross-check
# =============================================================================
def m5():
    D = {"d1": doc("d1"), "d2": doc("d2"), "d3": doc("d3", "news", derived="d1"), "d4": doc("d4", "news", derived="d3"),
         "d5": doc("d5"), "d6": doc("d6", supersedes=["d7"]), "d7": doc("d7"), "d8": doc("d8"), "d9": doc("d9"),
         "d10": doc("d10", derived="d9"), "d11": doc("d11", derived="d99"), "d12": doc("d12", derived="d13"), "d13": doc("d13", derived="d12"), "d14": doc("d14", derived="d14")}
    O = lambda x: mod.origin(x, D)
    assert [O("d1"), O("d3"), O("d4"), O("d10"), O("d11"), O("d14")] == ["d1", "d1", "d1", "d9", "d11", "d14"], "origin follows derived_from to the end of the chain (d4 -> d3 -> d1); a parent that is not in the corpus, or a self-loop, ends the chain"
    assert O("d12") == "d13" and O("d13") == "d12", f"a loop d12 -> d13 -> d12 ends at the last document reached before it repeats: origin('d12') is d13, origin('d13') is d12; got {O('d12')}, {O('d13')}"
    assert mod.origin("d3", DOCS) == "d1" and mod.origin("d9", DOCS) == "d8" and mod.origin("d18", DOCS) == "d17" and mod.origin("d16", DOCS) == "d16"
    X = lambda cs: mod.cross_check(cs, D)
    f, o = X([claim("d1", "x", 2024, 10, id="c1"), claim("d3", "x", 2024, 10, id="c2"), claim("d4", "x", 2024, 10, id="c3")])
    assert o == [] and len(f) == 1 and (f[0].metric, f[0].year, f[0].status, f[0].values, f[0].best, f[0].note) == ("x", 2024, "single_source", {10: ["d1"]}, 10, ""), \
        f"three documents, one origin (d3 and d4 copy d1): single_source with values {{10: ['d1']}}; got {f}"
    f, o = X([claim("d1", "x", 2024, 10, id="c1"), claim("d2", "x", 2024, 10, id="c2"), claim("d4", "x", 2024, 10, id="c3")])
    assert (f[0].status, f[0].values) == ("corroborated", {10: ["d1", "d2"]}), f"d1, d2 and a copy of d1: two origins, corroborated; got {f[0].status}, {f[0].values}"
    f, o = X([claim("d2", "x", 2024, 10), claim("d1", "x", 2024, 10), claim("d5", "x", 2024, 12), claim("d5", "y", 2024, 2)])
    assert [(g.metric, g.status) for g in f] == [("x", "conflict"), ("y", "single_source")], f"got {[(g.metric, g.status) for g in f]}"
    assert f[0].values == {10: ["d1", "d2"], 12: ["d5"]} and f[0].best == 10, f"values {f[0].values}, best {f[0].best}"
    assert f[0].note == "12 is 2 away from 10; a verified claim of 2 exists (y, d5).", f"note: {f[0].note!r}"
    f, o = X([claim("d1", "x", 2024, 5), claim("d2", "x", 2024, 3)])
    assert f[0].status == "conflict" and f[0].best == 3 and f[0].values == {3: ["d2"], 5: ["d1"]} and f[0].note == "", f"one origin each: the lower value is best and, with no explaining claim, note is empty; got {f[0]}"
    f, o = X([claim("d1", "x", 2025, 2.5, id="c1"), claim("d7", "x", 2025, 2.0, id="c2"), claim("d7", "z", 2025, 0.5, id="c3")])
    assert [c["id"] for c in o] == ["c2", "c3"] and [(g.metric, g.status, g.best) for g in f] == [("x", "single_source", 2.5)] and f[0].note == "", \
        f"d7 is superseded by d6: its claims are outdated and take no part, not even as explanations; got outdated {[c['id'] for c in o]}, findings {f}"
    f, o = X([claim("d1", "b", 2023, 1), claim("d1", "a", 2024, 1), claim("d1", "a", 2023, 1)])
    assert [(g.metric, g.year) for g in f] == [("a", 2023), ("a", 2024), ("b", 2023)], f"findings are ordered by (metric, year); got {[(g.metric, g.year) for g in f]}"
    f, o = X([claim("d1", "x", 1, 10), claim("d2", "x", 1, 10), claim("d8", "x", 1, 12), claim("d9", "x", 1, 15), claim("d5", "z", 1, 2), claim("d5", "w", 1, 5), claim("d2", "w", 1, 5)])
    f = [g for g in f if g.metric == "x"]
    assert f[0].note == "12 is 2 away from 10; a verified claim of 2 exists (z, d5). 15 is 5 away from 10; a verified claim of 5 exists (w, d2, d5).", f"two explanations, joined by a space, values ascending, all documents listed; got {f[0].note!r}"
    f, o = X([claim("d1", "r", 2024, 4.2), claim("d2", "r", 2024, 4.2), claim("d8", "r", 2024, 4.5), claim("d5", "grant", 2024, 0.3)])
    assert f[1].note == "4.5 is 0.3 away from 4.2; a verified claim of 0.3 exists (grant, d5).", f"float gaps are rounded to two places before comparing; got {f[1].note!r}"
    assert X([]) == ([], [])
    f, o = X([claim("d1", "r", 2024, 1350), claim("d2", "r", 2024, 1200), claim("d8", "in-house", 2024, 150), claim("d9", "in-house", 2024, 150)])
    assert f[1].note == "1,350 is 150 away from 1,200; a verified claim of 150 exists (in-house, d8, d9)." and f[1].best == 1200, f"thousands separators in notes use format(x, ',g'); got {f[1].note!r}, best {f[1].best}"
    # the real roads claims, checked independently of your Milestone 3 and 4
    claims, n = [], 0
    for d in ["d1", "d2", "d3", "d6", "d7", "d8", "d9"]:
        for c in READER[d]:
            text = DOCS[c["doc"]]["text"].lower()
            if c["metric"] in {ROADS, "grant", "storm programme extra"} and c["quote"].lower() in text and any(near(float(t.replace(",", "")), c["value"]) for t in NUM.findall(c["quote"])):
                n += 1
                claims.append({**c, "id": f"c{n}"})
    f, o = mod.cross_check(claims, DOCS)
    got = [(g.metric, g.year, g.status, g.values, g.best) for g in f]
    want = [("grant", 2024, "corroborated", {0.3: ["d7", "d8"]}, 0.3), ("road repair spend", 2023, "corroborated", {3.4: ["d1", "d2"]}, 3.4),
            ("road repair spend", 2024, "conflict", {4.2: ["d1", "d2"], 4.5: ["d8"]}, 4.2), ("storm programme extra", 2024, "single_source", {0.8: ["d6"]}, 0.8)]
    assert got == want and o == [], f"chapter 16's roads corpus: expected\n        {want}\n      got\n        {got}"
    assert f[2].note == "4.5 is 0.3 away from 4.2; a verified claim of 0.3 exists (grant, d7, d8)."
    return "origins (chains, loops, strangers), single / corroborated / conflict, tie-breaks, outdated documents, explanations, and the roads corpus"


# =============================================================================
# Milestone 6: the report, and the whole pipeline
# =============================================================================
def m6():
    D = {"d1": doc("d1", "primary", title="Alpha report", date="2025-01-01"), "d2": doc("d2", "news", title="Beta news", date="2025-02-02"),
         "d3": doc("d3", "primary", title="Gamma letter", date="2025-03-03"), "d4": doc("d4", "primary", title="Old policy", date="2020-01-01"),
         "d5": doc("d5", "primary", title="New policy", date="2025-04-04", supersedes=["d4"])}
    cl = [claim("d1", "alpha", 2024, 10, id="c1"), claim("d2", "alpha", 2024, 10, id="c2"), claim("d3", "beta", 2024, 3, id="c3"),
          claim("d1", "gamma", 2024, 7, id="c4"), claim("d2", "alpha", 2024, 12, id="c5")]
    findings = [mod.Finding("alpha", 2024, "conflict", {10: ["d1", "d2"], 12: ["d2"]}, 10, "12 is 2 away from 10; a verified claim of 2 exists (x, d3)."),
                mod.Finding("beta", 2024, "single_source", {3: ["d3"]}, 3)]
    outdated = [claim("d4", "fare", 2025, 2.0, id="c9")]
    draft = ["Alpha was 10 in 2024 [c2][c1].", "Beta was 3 [c3] and gamma was 7 [c4] [c1].", "Delta rose 99 [c1].", "Epsilon happened.", "Alpha was 12 [c5][c99].",
             "Gamma again [c4]."]
    rep = mod.assemble("What happened?", draft, cl, findings, outdated, D)
    want = """Question: What happened?

Findings
- Alpha was 10 in 2024 [1][2].
- Beta was 3 [3] and gamma was 7 [2].
- Gamma again [2].

Where sources disagree
- Alpha in 2024: 10 (d1, d2) versus 12 (d2). 12 is 2 away from 10; a verified claim of 2 exists (x, d3).

Set aside as outdated
- d4: Old policy (superseded by d5)

Dropped 3 of 6 draft sentences that could not be traced to verified claims.

Sources
[1] d2: Beta news (news, 2025-02-02)
[2] d1: Alpha report (primary, 2025-01-01)
[3] d3: Gamma letter (primary, 2025-03-03)"""
    assert rep.text == want, "assemble produced a different report; first difference at " + first_difference(want, rep.text)
    assert rep.kept == ["Alpha was 10 in 2024 [1][2].", "Beta was 3 [3] and gamma was 7 [2].", "Gamma again [2]."], f"kept sentences, rendered; got {rep.kept}"
    assert rep.dropped == [("Delta rose 99 [c1].", ["99 is not in the cited claims"]), ("Epsilon happened.", ["no citation"]), ("Alpha was 12 [c5][c99].", ["unknown claim c99"])], f"dropped sentences with their problems; got {rep.dropped}"
    assert rep.sources == ["d2", "d1", "d3"], f"sources in order of first use (the first sentence cites c2, a d2 claim, before c1); sources in citation order; got {rep.sources}"
    rep = mod.assemble("Q?", ["Nothing here.", "Or here [c77]."], cl, [], [], D)
    want = "Question: Q?\n\nFindings\n- (nothing could be supported)\n\nDropped 2 of 2 draft sentences that could not be traced to verified claims."
    assert rep.text == want and rep.sources == [] and rep.kept == [], "when nothing survives, say so and omit the empty blocks; first difference at " + first_difference(want, rep.text)
    rep = mod.assemble("Q?", ["Alpha [c1] and beta [c3].", "Spaced [c1] [c2] [c1]."], cl, [], [], D)
    assert rep.kept == ["Alpha [1] and beta [2].", "Spaced [1][3]."], \
        f"each run of markers becomes source numbers: separate runs stay separate, a run lists each document once, ascending; got {rep.kept}"
    assert "Dropped" not in rep.text, "no 'Dropped' line when nothing was dropped"
    # the whole pipeline, three questions
    EXPECT = {
        "roads": open_expected("roads"), "potholes": open_expected("potholes"), "fares": open_expected("fares")}
    for name, question in QUESTIONS.items():
        models = make_models()
        t = mod.research(question, models, IDX, DOCS)
        text = t.report.text
        assert text == EXPECT[name], f"research({name!r}): the report differs from the expected one; first difference at " + first_difference(EXPECT[name], text)
        assert len(models.planner.calls) == 1 and len(models.writer.calls) == 1 and len(models.reader.calls) == len(t.to_read), \
            f"{name}: one planner call, one writer call and one reader call per document read; got {len(models.planner.calls)}, {len(models.writer.calls)}, {len(models.reader.calls)} for {len(t.to_read)} documents"
        old = {c["id"] for c in t.outdated}
        usable = [c for c in t.verified if c["id"] not in old]
        assert models.writer.calls[0]["messages"] == [{"role": "user", "content": writer_prompt(question, usable)}], \
            f"{name}: the writer must be given exactly the verified, not outdated claims; it was sent\n        {models.writer.calls[0]['messages'][0]['content'][:300]}"
        for banned in ("24 per cent", "10 working days", "lowest bus fares", "more potholes than ever", "storm damage.", "improved everywhere"):
            assert banned not in text, f"{name}: the unsupported sentence containing '{banned}' reached the report"
        again = mod.research(question, make_models(), IDX, DOCS)
        assert again.report.text == text, f"{name}: two runs gave different reports"
    t = mod.research(QUESTIONS["roads"], make_models(), IDX, DOCS)
    assert t.to_read == ["d1", "d2", "d3", "d5", "d6", "d7", "d8", "d9"] and t.skipped == ["d4", "d14"]
    assert sorted((r["claim"]["doc"], r["reason"]) for r in t.rejected) == [("d3", "quote not in source"), ("d5", "empty quote"), ("d8", "value not in quote")], f"rejected claims: {[(r['claim']['doc'], r['reason']) for r in t.rejected]}"
    assert t.read.malformed == [("d9", "claim names another document")] and len(t.report.dropped) == 3
    t = mod.research(QUESTIONS["potholes"], make_models(), IDX, DOCS)
    assert t.read.unreadable == ["d15"] and t.read.malformed == [("d12", "missing field value")] and [(r["claim"]["doc"], r["reason"]) for r in t.rejected] == [("d14", "quote not in source")]
    t = mod.research(QUESTIONS["fares"], make_models(), IDX, DOCS)
    assert [c["doc"] for c in t.outdated] == ["d16"] and t.queries == [QUESTIONS["fares"]] and t.findings[0].status == "corroborated" and t.findings[0].values == {2.5: ["d17", "d19", "d20"]}
    return "hand-checked report layout, dropped sentences, source numbering, and three full runs: roads (a conflict, an invention), potholes (a disagreement and a paraphrase), fares (an outdated policy)"


def open_expected(name):
    with open(os.path.join(HERE, "expected", f"{name}.txt"), encoding="utf-8") as f:
        return f.read().rstrip("\n")


print(f"Lab 6 checks against {target}.py\n")
t0 = time.time()
check(1, "Milestone 1: plan, from a question to clean sub-questions", m1)
check(2, "Milestone 2: parallel search and triage", m2)
check(3, "Milestone 3: reading, one document per context", m3)
check(4, "Milestone 4: the citation checker", m4)
check(5, "Milestone 5: cross-check, origins and outdated sources", m5)
check(6, "Milestone 6: the report, and the whole pipeline", m6)
print(f"\n{sum(results)}/{len(results)} milestones passing  ({time.time() - t0:.1f} s)")
