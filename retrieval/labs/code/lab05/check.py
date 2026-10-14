"""Self-check for Lab 5: RAG with Verified Citations.

    python3 check.py                  # checks your starter.py
    python3 check.py solution         # checks the reference solution
    python3 check.py solution 3       # only milestone 3
    python3 check.py solution 3 2     # milestone 3, replaying ONLY the random scenario of seed 2

Everything is deterministic: the documents and questions are data.py, the "language model" is the
script in fixtures.py, retrieval is BM25, and every random scenario comes from a seeded
random.Random. No network, no clock. The whole check takes a couple of seconds. Prints a tick, a
cross, or "not implemented yet" for each milestone.
"""
import importlib
import os
import random
import sys
import time
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True

args = sys.argv[1:]
target = args[0] if args and not args[0].isdigit() else "starter"
rest = [a for a in args if a.isdigit()]
ONLY = int(rest[0]) if rest else None
ONLY_SEED = int(rest[1]) if len(rest) > 1 else None
mod = importlib.import_module(target)
from data import DOCS, QUESTIONS  # noqa: E402
from fixtures import SCRIPT  # noqa: E402
from llm import Model, Response, text as text_block  # noqa: E402

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


def ofold(s):
    """The oracle's own fold: NFKC, straight quotes, case-folded, one space."""
    s = unicodedata.normalize("NFKC", s).replace("’", "'").replace("‘", "'")
    return " ".join(s.casefold().split())


def chunk(doc, start, text, n=0):
    return {"id": f"{doc}#{n}", "doc": doc, "start": start, "end": start + len(text), "text": text}


class Echo(Model):
    """A model that returns a fixed reply and remembers what it was asked."""
    name = "echo"

    def __init__(self, reply):
        self.reply, self.calls = reply, []

    def complete(self, messages, *, system=None, tools=None, max_tokens=1024, temperature=0.0):
        self.calls.append({"messages": messages, "system": system})
        return Response(content=[text_block(self.reply)])


SENT = ["The annual charge is 65 pounds for the first car.", "Permits are issued within 2 working days.",
        "A lost permit costs 15 pounds to replace.", "Visitor vouchers last for one day.", "Ask at any library for details."]


# =============================================================================
# Milestone 1: chunks that remember where they came from
# =============================================================================
def m1():
    sp = mod.sentence_spans
    assert sp("One. Two.") == [(0, 4), (5, 9)], f"sentence_spans('One. Two.') should be [(0, 4), (5, 9)]; got {sp('One. Two.')}"
    assert sp("") == [] and sp("  \n ") == [], "empty or blank text has no sentences"
    t = "Express delivery costs 9.50 pounds. It takes 2 days."
    assert [t[s:e] for s, e in sp(t)] == ["Express delivery costs 9.50 pounds.", "It takes 2 days."], \
        f"'9.50' has no whitespace after its dot, so it must not split; got {[t[s:e] for s, e in sp(t)]}"
    t = "Parking Permits\n\nA resident may apply. Fees apply."
    assert [t[s:e] for s, e in sp(t)] == ["Parking Permits", "A resident may apply.", "Fees apply."], \
        f"a blank line ends a sentence (so a title stands alone); got {[t[s:e] for s, e in sp(t)]}"
    t = "It is valid for a complete\napplication  only. Next."
    assert [t[s:e] for s, e in sp(t)] == ["It is valid for a complete\napplication  only.", "Next."], \
        "a newline or a double space INSIDE a sentence stays inside it: spans are offsets, not a rewritten text"
    t = "  Leading space. Trailing space.  "
    assert [t[s:e] for s, e in sp(t)] == ["Leading space.", "Trailing space."], "spans never begin or end in whitespace"
    for seed in seeds(range(1, 7)):
        rng = random.Random(70 + seed)
        sents = [" ".join(rng.choice(["Fee", "of", "9.50", "pounds", "and", "the", "late", "item"]) for _ in range(rng.randint(3, 9))) + rng.choice([".", "!", "?"])
                 for _ in range(rng.randint(2, 8))]
        sents = [s[0].upper() + s[1:] for s in sents]
        text = rng.choice(["", "\n", "  "]) + "".join(s + rng.choice([" ", "  ", "\n", "\n\n", " \n"]) for s in sents)
        got = [text[s:e] for s, e in sp(text)]
        assert got == sents, f"seed {seed}: expected {len(sents)} sentences {sents[:2]}..., got {len(got)}: {got[:2]}...; replay with `python3 check.py solution 1 {seed}`"
    # chunk_document
    text = " ".join(SENT)
    ch = mod.chunk_document("d", text, max_chars=100, overlap=0)
    assert [c["id"] for c in ch] == [f"d#{i}" for i in range(len(ch))], f"ids are doc#0, doc#1, ...; got {[c['id'] for c in ch]}"
    assert all(c["text"] == text[c["start"]:c["end"]] and c["doc"] == "d" for c in ch), "chunk text must equal the document's text[start:end]"
    assert " ".join(c["text"] for c in ch) == text, "with overlap 0, the chunks tile the document: nothing lost, nothing repeated"
    assert all(len(c["text"]) <= 100 for c in ch) and len(ch) == 3, f"100 characters fit two of these sentences: expected 3 chunks, got {len(ch)}: {[len(c['text']) for c in ch]}"
    ov = mod.chunk_document("d", text, max_chars=100, overlap=1)
    assert [c["text"].count(".") for c in ov] and ov[1]["text"].startswith(SENT[1]) , f"overlap=1: the second chunk starts with the last sentence of the first; got {ov[1]['text']!r}"
    assert len(ov) >= len(ch), "overlap can only add chunks"
    long_ = "Tiny. " + "This single sentence is far longer than the limit we set for a chunk of this document. " + "End."
    lc = mod.chunk_document("l", long_, max_chars=40, overlap=0)
    assert any(c["text"].startswith("This single sentence") and c["text"].endswith("document.") for c in lc), \
        f"a sentence longer than max_chars is a chunk by itself, never cut; got {[c['text'] for c in lc]}"
    assert len(mod.chunk_document("e", "", 100, 1)) == 0, "no text, no chunks"
    one = mod.chunk_document("o", SENT[0], 200, 3)
    assert len(one) == 1, f"a single sentence is a single chunk, however large the overlap; got {len(one)}"
    inf = mod.chunk_document("f", text, max_chars=60, overlap=5)
    assert len(inf) < 50 and all(inf[i]["start"] < inf[i + 1]["start"] for i in range(len(inf) - 1)), \
        "overlap larger than the chunk must still advance by at least one sentence (starts strictly increase)"
    for seed in seeds(range(1, 7)):
        rng = random.Random(170 + seed)
        sents = [(" ".join(rng.choice(["alpha", "beta", "9.50", "gamma", "delta", "pounds", "per", "week"]) for _ in range(rng.randint(3, 12))) + ".").capitalize()
                 for _ in range(rng.randint(3, 14))]
        doc = "".join(s + rng.choice([" ", "  ", "\n"]) for s in sents).rstrip()
        mx, ovl = rng.choice([60, 90, 140, 220]), rng.randint(0, 2)
        chs = mod.chunk_document("r", doc, mx, ovl)
        assert all(c["text"] == doc[c["start"]:c["end"]] for c in chs), f"seed {seed}: chunk text differs from doc[start:end]"
        assert all(chs[i]["start"] < chs[i + 1]["start"] for i in range(len(chs) - 1)), f"seed {seed}: chunk starts must strictly increase"
        for s in sents:
            assert any(s in c["text"] for c in chs), f"seed {seed}: the sentence {s!r} was cut or lost (max_chars {mx}, overlap {ovl})"
        for c in chs:
            n_sent = sum(1 for s in sents if s in c["text"])
            assert len(c["text"]) <= mx or n_sent == 1, f"seed {seed}: chunk of {len(c['text'])} characters exceeds max_chars {mx} with {n_sent} sentences; replay `python3 check.py solution 1 {seed}`"
    allc = [c for d, t in DOCS.items() for c in mod.chunk_document(d, t, 260, 1)]
    assert all(c["text"] == DOCS[c["doc"]][c["start"]:c["end"]] for c in allc), "real documents: chunk text must equal text[start:end]"
    for qid, entry in SCRIPT.items():
        for item in entry or []:
            claim, doc, quote = item[:3]
            if qid in ("q05", "q10"):
                continue                                  # these quotes are altered or from a document that is not the answer's
            assert any(ofold(quote) in ofold(c["text"]) for c in allc if c["doc"] == doc), \
                f"{qid}: the quote {quote!r} is not inside any single chunk of '{doc}': the chunker cut the evidence"
    return f"{len(allc)} chunks from {len(DOCS)} documents (mean {sum(len(c['text']) for c in allc) / len(allc):.0f} characters); every quote the model will use lies inside one chunk"


# =============================================================================
# Milestone 2: the context the model sees
# =============================================================================
def m2():
    from llm import count_tokens
    a, b, c = chunk("parking", 0, "Permits cost 65 pounds."), chunk("library", 10, "Books are lent\nfor 21 days.", 1), chunk("waste", 20, "Bins go out by 7am.", 2)
    ctx, labels, dropped = mod.assemble([a, b, c], 1000)
    lines = ctx.split("\n")
    assert lines == ["[S1] (parking) Permits cost 65 pounds.", "[S2] (library) Books are lent for 21 days.", "[S3] (waste) Bins go out by 7am."], \
        f"context lines are  [S<n>] (<doc>) <text with whitespace collapsed>; got {lines}"
    assert list(labels) == ["S1", "S2", "S3"] and labels["S2"]["id"] == "library#1" and labels["S2"]["text"] == b["text"], \
        "labels map S1.. to the ORIGINAL chunk dicts (their text keeps its newline: gate 2 needs the real text)"
    assert dropped == 0
    assert mod.assemble([], 100) == ("", {}, 0), "no chunks: ('', {}, 0)"
    dup = chunk("parking", 500, "PERMITS  cost 65 pounds.", 9)
    ctx, labels, dropped = mod.assemble([a, dup, b], 1000)
    assert list(labels) == ["S1", "S2"] and dropped == 1 and labels["S2"]["doc"] == "library", \
        f"a chunk whose folded text equals an earlier one is dropped and the labels stay contiguous; got {list(labels)}, dropped {dropped}"
    line1 = "[S1] (parking) Permits cost 65 pounds."
    need = count_tokens(line1)
    ctx, labels, dropped = mod.assemble([a, b, c], need + 1)
    assert list(labels) == ["S1"] and dropped == 2, f"a budget of {need + 1} tokens fits only the first line ({need} tokens); got {list(labels)}, dropped {dropped}"
    big = chunk("big", 0, "word " * 100, 3)
    ctx, labels, dropped = mod.assemble([a, big, c], 40)
    assert list(labels) == ["S1"] and dropped == 2, "stop at the first chunk that does not fit: the small chunk after the big one is NOT skipped into"
    assert mod.assemble([a, b], 0) == ("", {}, 2), "a budget of 0 keeps nothing"
    for seed in seeds(range(1, 7)):
        rng = random.Random(270 + seed)
        chs = [chunk(rng.choice(["x", "y", "z"]), i * 1000, " ".join(rng.choice(["fee", "bin", "pass", "bus", "rate"]) for _ in range(rng.randint(2, 40))) + ".", i) for i in range(rng.randint(3, 12))]
        budget = rng.choice([30, 60, 120, 400])
        ctx, labels, dropped = mod.assemble(chs, budget)
        ls = ctx.split("\n") if ctx else []
        assert sum(count_tokens(l) for l in ls) <= budget, f"seed {seed}: context is {sum(count_tokens(l) for l in ls)} tokens, over the budget {budget}"
        assert len(ls) == len(labels) and len(labels) + dropped == len(chs), f"seed {seed}: {len(ls)} lines, {len(labels)} labels, {dropped} dropped of {len(chs)}"
        seen, expect = set(), []
        for ch_ in chs:
            if ofold(ch_["text"]) not in seen:
                seen.add(ofold(ch_["text"]))
                expect.append(ch_["id"])
        got = [labels[f"S{n}"]["id"] for n in range(1, len(labels) + 1)]
        assert got == expect[:len(got)], f"seed {seed}: kept chunks must be a PREFIX of the de-duplicated ranking; got {got}, expected a prefix of {expect}; replay with `python3 check.py solution 2 {seed}`"
    pipe = mod.build()
    toks = []
    for q in QUESTIONS:
        ctx, labels, dropped = mod.assemble(pipe.retrieve(q[1]), pipe.budget)
        toks.append(count_tokens(ctx))
        assert toks[-1] <= pipe.budget, f"{q[0]}: context {toks[-1]} tokens, over the pipeline budget {pipe.budget}"
    ctx, labels, _ = mod.assemble(pipe.retrieve(QUESTIONS[0][1]), pipe.budget)
    assert ctx.startswith("[S1] (parking) "), f"for q01 the best chunk is from 'parking'; context starts {ctx[:30]!r}"
    return f"14 real contexts, {min(toks)} to {max(toks)} tokens (budget {pipe.budget}); q01's context has {len(labels)} sources"


# =============================================================================
# Milestone 3: gates 1 and 2
# =============================================================================
def m3():
    nm = mod.norm_with_map
    assert nm("A  B") == ("a b", [0, 1, 3]), f"norm_with_map('A<NBSP> B') should be ('a b', [0, 1, 3]); got {nm('A  B')}"
    assert nm("ﬁne") == ("fine", [0, 0, 1, 2]), f"the ligature expands to two characters with the same origin; got {nm('ﬁne')}"
    assert nm("  x \n") == ("x", [2]), f"no leading or trailing space; got {nm('  x \n')}"
    assert nm("") == ("", []), "empty text"
    assert nm("the council’s") == ("the council's", list(range(13))), "a curly apostrophe is straightened"
    assert nm("co­op") == ("coop", [0, 1, 3, 4]), "a soft hyphen is dropped"
    for seed in seeds(range(1, 7)):
        rng = random.Random(370 + seed)
        text = "".join(rng.choice(["ab", "Cd", " ", "  ", "\n", " ", "9", "."]) for _ in range(rng.randint(0, 40)))
        n, org = nm(text)
        assert n == " ".join(text.replace(" ", " ").casefold().split()), f"seed {seed}: norm_with_map({text!r}) text is {n!r}"
        assert len(org) == len(n) and all(0 <= o < len(text) for o in org) and org == sorted(org), f"seed {seed}: origin must have one increasing index per character"
        assert all(text[o].casefold() == ch or ch == " " for o, ch in zip(org, n)), f"seed {seed}: each normalised character must come from the original character at its origin"
    text = "Express delivery\ntakes 1 to 2 business days and costs 9.50."
    assert mod.locate(text, "express  delivery takes 1 to 2 BUSINESS days") == (0, 43), \
        f"formatting differences are tolerated; the span is in the ORIGINAL text; got {mod.locate(text, 'express  delivery takes 1 to 2 BUSINESS days')}"
    s, e = mod.locate(text, "takes 1 to 2 business days")
    assert text[s:e] == "takes 1 to 2 business days", f"span {s, e} should slice out the quote; got {text[s:e]!r}"
    assert mod.locate(text, "takes 1 to 3 business days") is None, "ONE changed digit must not be found: tolerant about formatting, never about content"
    assert mod.locate(text, "") is None and mod.locate(text, "   ") is None, "an empty quote is never found"
    t2 = "the ﬁnal reply and the oﬃce"
    s, e = mod.locate(t2, "final reply and the office")
    assert t2[s:e] == t2[4:] and (s, e) == (4, len(t2)), f"a ligature in the source: the span covers the ligature character; got {(s, e)}"
    for seed in seeds(range(1, 9)):
        rng = random.Random(470 + seed)
        words = [rng.choice(["fee", "bin", "pass", "9.50", "late", "term", "week", "stolen", "permit", "year"]) + str(rng.randint(0, 99)) for _ in range(rng.randint(12, 30))]
        doc = "".join(w + rng.choice([" ", "  ", "\n", " "]) for w in words)
        i = rng.randint(0, len(words) - 6)
        j = i + rng.randint(4, 6)
        quote = rng.choice([str.lower, str.upper, str])(rng.choice([" ", "  ", "\n"]).join(words[i:j]))
        span = mod.locate(doc, quote)
        assert span is not None, f"seed {seed}: a re-spaced, re-cased copy of words {i}:{j} was not found"
        assert ofold(doc[span[0]:span[1]]) == ofold(quote), f"seed {seed}: the span {span} slices {doc[span[0]:span[1]]!r}, not the quote"
        w = list(words[i:j])
        k = rng.randrange(len(w))
        w[k] = w[k][:-1] + ("7" if w[k][-1] != "7" else "8")
        bad = " ".join(w)
        if ofold(bad) not in ofold(doc):
            assert mod.locate(doc, bad) is None, f"seed {seed}: a quote with one changed digit ({bad!r}) was found; replay with `python3 check.py solution 3 {seed}`"
    ch = chunk("parking", 1000, "Permits are issued online within 2 working days. A third vehicle is not eligible.", 2)
    labels = {"S1": ch}
    v = mod.verify_quote("S1", "permits are issued online within 2 working days", labels)
    assert v == {"verdict": "OK", "doc": "parking", "span": (1000, 1000 + 47)}, f"OK returns the doc id and the span in the DOCUMENT (chunk start + offset); got {v}"
    v = mod.verify_quote("S1", "A third vehicle is not eligible.", labels)
    assert v["verdict"] == "OK" and v["span"] == (1000 + 49, 1000 + 81), f"offset inside the chunk must be added to the chunk's start; got {v}"
    for q, want in [(("S9", "Permits are issued online"), "BAD_POINTER"), (("S1", "within 3 working days of apply"), "FABRICATED_QUOTE"),
                    (("S1", "within"), "TOO_SHORT"), (("S9", "x"), "BAD_POINTER"), (("S1", "xyz"), "TOO_SHORT")]:
        v = mod.verify_quote(q[0], q[1], labels)
        assert v["verdict"] == want and v["doc"] is None and v["span"] is None, f"verify_quote{q} should be {want} with doc and span None; got {v}"
    pipe = mod.build()
    ok = bad = 0
    for qid, entry in SCRIPT.items():
        for item in entry or []:
            claim, doc, quote = item[:3]
            lab = {f"S{n + 1}": c for n, c in enumerate(c for c in pipe.chunks if c["doc"] == doc and ofold(quote) in ofold(c["text"]))} or {"S1": next(c for c in pipe.chunks if c["doc"] == doc)}
            v = mod.verify_quote("S1", quote, lab)
            if qid == "q05":
                assert v["verdict"] == "FABRICATED_QUOTE", f"q05's quote has 25 changed to 30: expected FABRICATED_QUOTE, got {v['verdict']}"
                bad += 1
            elif qid != "q06":
                assert v["verdict"] == "OK", f"{qid}: a faithful quote should pass gates 1 and 2; got {v['verdict']} for {quote!r}"
                s, e = v["span"]
                assert ofold(DOCS[doc][s:e]) == ofold(quote), f"{qid}: span {s, e} of the document slices {DOCS[doc][s:e]!r}, not the quote"
                ok += 1
    return f"real quotes: {ok} located exactly in their documents (spans checked against the source text), {bad} altered quote rejected"


# =============================================================================
# Milestone 4: gate 3
# =============================================================================
def m4():
    sp = mod.supports
    ok, score = sp("Tents have a 3 year warranty.", "Tents carry a 2 year warranty")
    assert ok is False and isinstance(score, float), f"a different number must fail whatever the word overlap; got {(ok, score)}"
    assert score > 0.5, f"the score is still the coverage (0.5 or more here), reported even when a rule fails; got {score}"
    ok, score = sp("Gift cards do not expire.", "Gift cards expire after a year")
    assert ok is False, "negation differs: the claim says 'not', the quote does not"
    ok, score = sp("The office isn't open.", "The office is open.")
    assert ok is False, "n't forms count as negation"
    ok, score = sp("Gift cards do not expire.", "Gift cards do not expire")
    assert ok is True and near(score, 1.0), f"identical wording is supported with score 1.0; got {(ok, score)}"
    ok, score = sp("The fee is 15 pounds for a replacement permit.", "A replacement permit costs a fee of 15 pounds")
    assert ok and near(score, 1.0), f"stop words and plurals ('pounds') must not count against the claim; got {(ok, score)}"
    ok, score = sp("alpha beta gamma delta", "alpha beta gamma epsilon")
    assert ok and near(score, 0.75), f"3 of 4 content words is exactly 0.75: supported (>= threshold); got {(ok, score)}"
    ok, score = sp("alpha beta gamma delta", "alpha beta epsilon zeta")
    assert (not ok) and near(score, 0.5), f"2 of 4 is 0.5: not supported at the default threshold; got {(ok, score)}"
    assert sp("alpha beta gamma delta", "alpha beta epsilon zeta", threshold=0.5)[0] is True, "threshold is a parameter"
    assert sp("It is.", "Anything at all here") == (False, 0.0), "a claim with no content words is not supported, score 0.0"
    for seed in seeds(range(1, 9)):
        rng = random.Random(570 + seed)
        vocab = ["permit", "vehicle", "charge", "library", "member", "borrow", "renewal", "collection", "garden", "bulky", "notice", "ombudsman", "reminder", "student", "discount"]
        words = rng.sample(vocab, rng.randint(6, 10))
        nums = [str(rng.randint(2, 90)) for _ in range(2)]
        quote = " ".join(words[:3] + [nums[0]] + words[3:] + [nums[1]]) + "."
        assert sp(quote, quote)[0] is True, f"seed {seed}: a quote supports itself"
        assert sp("The " + quote, quote)[0] is True, f"seed {seed}: adding a stop word to the claim changes nothing"
        changed = quote.replace(nums[0], str(int(nums[0]) + 1), 1)
        assert sp(changed, quote)[0] is False, f"seed {seed}: one number changed must fail ({changed!r} against {quote!r}); replay with `python3 check.py solution 4 {seed}`"
        assert sp("It is not true that " + quote, quote)[0] is False, f"seed {seed}: adding a negation to the claim must fail"
        k = len(words) // 2
        garbled = " ".join(["zxq%d" % i for i in range(k)] + words[k:] + nums) + "."
        assert sp(garbled, quote)[0] is False, f"seed {seed}: replacing half the content words must fail the 0.75 coverage"
    ch = chunk("returns", 0, "The refund window is 30 days from delivery. Refunds go to the original payment method. Gift cards do not expire.", 0)
    labels = {"S1": ch}
    q = {"q1": {"src": "S1", "text": "The refund window is 30 days from delivery"}, "q2": {"src": "S1", "text": "Refunds go to the original payment method"},
         "q3": {"src": "S1", "text": "Refunds go to the original payment cheque"}, "q4": {"src": "S9", "text": "Gift cards do not expire"},
         "q5": {"src": "S1", "text": "Gift"}}
    vc = mod.verify_claim
    r = vc("The refund window is 30 days from delivery.", ["q1"], q, labels)
    assert r["verdict"] == "OK" and near(r["score"], 1.0) and len(r["spans"]) == 1 and r["spans"][0][0] == "returns" and r["claim"], f"a plain supported claim; got {r}"
    r = vc("Anything.", [], q, labels)
    assert r["verdict"] == "UNCITED" and r["spans"] == [], f"no cites: UNCITED; got {r}"
    assert vc("Anything at all here.", ["q7"], q, labels)["verdict"] == "BAD_POINTER", "a cited id that is not among the quotes is a BAD_POINTER"
    assert vc("Gift cards do not expire.", ["q4"], q, labels)["verdict"] == "BAD_POINTER", "a quote under a label that does not exist is a BAD_POINTER"
    assert vc("Refunds go to the original payment cheque.", ["q3"], q, labels)["verdict"] == "FABRICATED_QUOTE", "a quote not in the source is FABRICATED_QUOTE"
    assert vc("Gift.", ["q5"], q, labels)["verdict"] == "TOO_SHORT", "a 4-character quote is TOO_SHORT"
    r = vc("Refunds are free.", ["q2"], q, labels)
    assert r["verdict"] == "UNSUPPORTED" and r["spans"] == [] and 0 < r["score"] < 0.75, f"a real quote, an unsupported claim: UNSUPPORTED with its score; got {r}"
    r = vc("Refunds within 30 days from delivery go to the original payment method.", ["q1", "q2"], q, labels)
    assert r["verdict"] == "OK" and len(r["spans"]) == 2, f"gate 3 runs on the quotes JOINED: two quotes may jointly support a claim neither does alone; got {r}"
    assert near(r["score"], 8 / 9), f"expected the joint coverage 8/9; got {r['score']:.3f}"
    assert vc("x.", ["q3", "q4"], q, labels)["verdict"] == "FABRICATED_QUOTE", "the first failing cite, in the order given, decides the verdict"
    pipe = mod.build()
    verdicts = {}
    for qid, entry in SCRIPT.items():
        for item in entry or []:
            claim, doc, quote = item[:3]
            lab = {"S1": next((c for c in pipe.chunks if c["doc"] == doc and ofold(quote) in ofold(c["text"])), next(c for c in pipe.chunks if c["doc"] == doc))}
            verdicts[qid] = mod.verify_claim(claim, ["q1"], {"q1": {"src": "S1", "text": quote}}, lab)["verdict"]
    want = {"q01": "OK", "q02": "OK", "q03": "OK", "q04": "OK", "q05": "FABRICATED_QUOTE", "q06": "OK", "q07": "UNSUPPORTED", "q08": "OK",
            "q10": "UNSUPPORTED", "q11": "OK", "q12": "OK", "q13": "OK", "q14": "OK"}
    for k, w in want.items():
        assert verdicts[k] == w, f"scripted claim {k}: expected {w}, got {verdicts[k]}"
    return ("the scripted claims against their own chunks: " + ", ".join(f"{k} {v.lower()}" for k, v in verdicts.items() if v != "OK")
            + f"; the rest pass. Note q08: a plausible slip ('school year' for 'term') PASSES this gate")


# =============================================================================
# Milestone 5: parse the reply, run the pipeline
# =============================================================================
def m5():
    pr = mod.parse_response
    reply = ('<quotes>\n<quote id="q1" src="S2">Permits are issued\nwithin 2 days</quote>\n<quote id="q2" src="S1">  A lost permit costs 15 pounds  </quote>\n</quotes>\n'
             '<answer>\nPermits take 2 days. [q1] A lost permit costs 15 pounds. [q2][q1] It is cheap.\n</answer>')
    p = pr(reply)
    assert p["none"] is False and p["quotes"]["q1"] == {"src": "S2", "text": "Permits are issued\nwithin 2 days"}, f"quotes keep their inner newline; got {p['quotes'].get('q1')}"
    assert p["quotes"]["q2"]["text"] == "A lost permit costs 15 pounds", "a quote's surrounding whitespace is stripped"
    assert [(c["text"], c["cites"]) for c in p["claims"]] == [("Permits take 2 days.", ["q1"]), ("A lost permit costs 15 pounds.", ["q2", "q1"]), ("It is cheap.", [])], \
        f"claims with their cites, in order, an uncited one with []; got {[(c['text'], c['cites']) for c in p['claims']]}"
    for none in ("<quotes>NONE</quotes><answer>The sources do not say.</answer>", "<QUOTES>\n  none \n</QUOTES>\n<answer>x</answer>"):
        p = pr(none)
        assert p == {"none": True, "quotes": {}, "claims": []}, f"NONE (any case) is an abstention with no claims; got {p}"
    p = pr("<answer>Costs 5 pounds. [q1]</answer>")
    assert p["none"] is False and p["quotes"] == {} and p["claims"][0]["cites"] == ["q1"], f"no <quotes> tag is not an abstention: the claim cites a quote that does not exist; got {p}"
    p = pr('<quotes><quote id="q1" src="S1">some quote text here</quote></quotes>')
    assert p["claims"] == [] and "q1" in p["quotes"], "a reply with no <answer> has no claims"
    # the pipeline, on one tiny document and a model that says what we tell it
    doc = {"d": "Permits are issued within 2 working days. A third vehicle is not eligible for a permit. Visitor vouchers last for one day."}
    q = "How long do permits take?"
    good = '<quotes><quote id="q1" src="S1">Permits are issued within 2 working days.</quote><quote id="q2" src="S1">A third vehicle is not eligible for a permit.</quote></quotes>'

    def run(reply, **kw):
        m = Echo(reply)
        pipe = mod.Pipeline(doc, m, k=3, budget=300)
        return pipe, m, pipe.answer(q, **kw)
    pipe, m, r = run(good + "<answer>Permits are issued within 2 working days. [q1] A third vehicle is not eligible. [q2]</answer>")
    assert r["status"] == "answered" and r["text"].count("[d:") == 2, f"two verified claims: answered, each followed by [doc:start-end]; got {r['status']} {r['text']!r}"
    assert "[d:0-41]" in r["text"] and "[d:42-87]" in r["text"], f"spans are offsets into the document (the two quotes sit at 0-41 and 42-87); got {r['text']!r}"
    assert len(r["claims"]) == 2 and all(v["verdict"] == "OK" for v in r["claims"]) and r["support"] == min(v["score"] for v in r["claims"]), "claims carry the verify_claim dicts; support is their minimum"
    assert m.calls[0]["system"] == mod.SYSTEM and m.calls[0]["messages"][0]["content"] == mod.build_prompt(q, r["context"]), "the model gets SYSTEM and build_prompt(question, context)"
    assert r["context"].startswith("[S1] (d)") and "S1" in r["labels"]
    bad = good + "<answer>Permits are issued within 2 working days. [q1] Vouchers are free for a year. [q2]</answer>"
    _, _, r = run(bad)
    assert r["status"] == "rejected" and r["text"] == mod.REJECT, f"reject mode: one failed claim withholds the whole answer; got {r['status']} {r['text']!r}"
    assert [v["verdict"] for v in r["claims"]] == ["OK", "UNSUPPORTED"], f"claims still report their verdicts when rejected; got {[v['verdict'] for v in r['claims']]}"
    _, _, r = run(bad, mode="drop")
    assert r["status"] == "answered" and "Vouchers" not in r["text"] and "Permits are issued" in r["text"], f"drop mode keeps only the verified claim; got {r['text']!r}"
    _, _, r = run(good + "<answer>Nothing is true here. [q2]</answer>", mode="drop")
    assert r["status"] == "rejected" and r["text"] == mod.REJECT, "drop mode with no verified claim is a rejection"
    _, _, r = run("<quotes>NONE</quotes><answer>The sources do not say.</answer>")
    assert r["status"] == "abstained" and r["text"] == mod.ABSTAIN and r["claims"] == [], f"the model says NONE: abstained; got {r['status']}"
    m = Echo("should not be called")
    pipe = mod.Pipeline(doc, m)
    r = pipe.answer("zebra quantum xylophone")
    assert r["status"] == "abstained" and r["text"] == mod.ABSTAIN and m.calls == [], "nothing retrieved: abstain BEFORE generation, and do not call the model"
    weak = good + "<answer>Permits are issued within 2 working days now. [q1]</answer>"
    _, _, r = run(weak)
    assert r["status"] == "answered" and 0 < r["support"] < 1, f"a slightly paraphrased claim answers with support < 1; got {r['status']} {r['support']}"
    _, _, r2 = run(weak, min_support=r["support"] + 0.01)
    assert r2["status"] == "abstained" and r2["text"] == mod.ABSTAIN, "support below min_support: abstain"
    assert run(weak, min_support=r["support"])[2]["status"] == "answered", "support equal to min_support is accepted"
    # the real thing
    pipe = mod.build()
    want = {"q01": "answered", "q02": "answered", "q03": "answered", "q04": "answered", "q05": "rejected", "q06": "rejected", "q07": "rejected", "q08": "answered",
            "q09": "abstained", "q10": "rejected", "q11": "answered", "q12": "answered", "q13": "rejected", "q14": "rejected"}
    first_fail = {}
    for qd in QUESTIONS:
        r = pipe.answer(qd[1])
        assert r["status"] == want[qd[0]], (f"{qd[0]} ({qd[1]!r}): expected {want[qd[0]]}, got {r['status']} "
                                           f"with verdicts {[v['verdict'] for v in r['claims']]}")
        if r["status"] == "answered":
            for doc_id, s, e in [x for v in r["claims"] for x in v["spans"]]:
                assert ofold(DOCS[doc_id][s:e]) in ofold(DOCS[doc_id]), "every shown span lies in its document"
        first_fail[qd[0]] = [v["verdict"] for v in r["claims"] if v["verdict"] != "OK"]
    r = pipe.answer(QUESTIONS[1][1])
    assert "[parking:" in r["text"], f"q02's answer should carry its source span; got {r['text']!r}"
    r13 = pipe.answer(QUESTIONS[12][1], mode="drop")
    assert r13["status"] == "answered" and "education plan" not in r13["text"], "q13 in drop mode: the cited claim is shown, the uncited one is not"
    return ("real run, reject mode: 7 answered, 6 rejected (" + ", ".join(f"{k} {v[0].lower()}" for k, v in first_fail.items() if v) + "), 1 abstained")


# =============================================================================
# Milestone 6: measure it
# =============================================================================
def m6():
    qa = ("x", "q", True, "120 pounds", "d")
    qn = ("y", "q", False, None, None)
    sa = mod.score_answer
    assert sa(qa, {"status": "answered", "text": "The fee is 120 Pounds. [d:1-2]"}) == "correct", "the phrase is compared after folding (case, spaces)"
    assert sa(qa, {"status": "answered", "text": "The fee is 100 pounds."}) == "wrong"
    assert sa(qa, {"status": "rejected", "text": ""}) == "missed" and sa(qa, {"status": "abstained", "text": ""}) == "missed", "an answerable question that got no answer is 'missed'"
    assert sa(qn, {"status": "answered", "text": "Anything"}) == "wrong", "answering an unanswerable question is 'wrong'"
    assert sa(qn, {"status": "abstained", "text": ""}) == "safe" and sa(qn, {"status": "rejected", "text": ""}) == "safe", "refusing an unanswerable question is 'safe'"

    class Stub:
        def __init__(self, table):
            self.table = table

        def answer(self, question, mode="reject", min_support=0.0):
            return dict(self.table[question])
    qs = [("a", "A", True, "yes", "d"), ("b", "B", True, "yes", "d"), ("c", "C", True, "yes", "d"), ("d", "D", False, None, None), ("e", "E", False, None, None)]
    tbl = {"A": {"status": "answered", "text": "yes", "support": 0.9, "claims": [{"verdict": "OK"}]},
           "B": {"status": "answered", "text": "no", "support": 0.6, "claims": [{"verdict": "OK"}, {"verdict": "UNSUPPORTED"}]},
           "C": {"status": "rejected", "text": "", "support": 0.0, "claims": [{"verdict": "FABRICATED_QUOTE"}]},
           "D": {"status": "abstained", "text": "", "support": 0.0, "claims": []},
           "E": {"status": "answered", "text": "made up", "support": 0.3, "claims": [{"verdict": "OK"}]}}
    ev = mod.evaluate(Stub(tbl), qs)
    assert ev["outcomes"] == {"a": "correct", "b": "wrong", "c": "missed", "d": "safe", "e": "wrong"}, f"outcomes by qid; got {ev['outcomes']}"
    assert ev["answered"] == 3 and near(ev["coverage"], 3 / 5) and near(ev["risk"], 2 / 3), f"answered 3 of 5, risk = wrong / answered = 2/3; got {ev['answered']}, {ev['coverage']}, {ev['risk']}"
    assert dict(ev["verdicts"]) == {"OK": 3, "UNSUPPORTED": 1, "FABRICATED_QUOTE": 1}, f"verdicts count every claim the model made; got {dict(ev['verdicts'])}"
    assert sorted(ev["rows"]) == [(0.3, False), (0.6, False), (0.9, True)], f"rows are (support, is_correct) for answered questions; got {ev['rows']}"
    assert ev["counts"]["wrong"] == 2 and ev["counts"]["safe"] == 1
    none = mod.evaluate(Stub({"A": {"status": "rejected", "text": "", "support": 0.0, "claims": []}}), qs[:1])
    assert none["risk"] == 0.0 and none["coverage"] == 0.0, "nothing answered: risk 0.0, not a division by zero"
    rows = [(0.95, True), (0.91, True), (0.88, True), (0.74, False), (0.70, True), (0.52, False), (0.40, False), (0.31, False)]
    got = mod.risk_coverage(rows, [0.0, 0.35, 0.6, 0.8, 0.9, 0.99])
    want = [(0.0, 1.0, 0.5), (0.35, 7 / 8, 3 / 7), (0.6, 5 / 8, 1 / 5), (0.8, 3 / 8, 0.0), (0.9, 2 / 8, 0.0), (0.99, 0.0, 0.0)]
    for g, w in zip(got, want):
        assert near(g[0], w[0]) and near(g[1], w[1]) and near(g[2], w[2]), f"risk_coverage at {w[0]}: expected coverage {w[1]:.3f}, risk {w[2]:.3f} (chapter 16's table); got {g}"
    assert mod.risk_coverage([], [0.0, 0.5]) == [(0.0, 0.0, 0.0), (0.5, 0.0, 0.0)], "no rows: coverage 0.0 and risk 0.0"
    rng = random.Random(7)
    rws = [(rng.random(), rng.random() < 0.7) for _ in range(50)]
    cov = [c for _, c, _ in mod.risk_coverage(rws, [i / 10 for i in range(11)])]
    assert all(cov[i] >= cov[i + 1] for i in range(len(cov) - 1)), "coverage can only fall as the threshold rises"
    pipe = mod.build()
    rej = mod.evaluate(pipe, QUESTIONS, mode="reject")
    drp = mod.evaluate(pipe, QUESTIONS, mode="drop")
    assert dict(rej["counts"]) == {"correct": 6, "wrong": 1, "missed": 5, "safe": 2}, f"reject mode on the real run; got {dict(rej['counts'])}"
    assert dict(drp["counts"]) == {"correct": 7, "wrong": 1, "missed": 4, "safe": 2}, f"drop mode on the real run; got {dict(drp['counts'])}"
    assert rej["outcomes"]["q08"] == "wrong", "the one wrong answer that got through is q08, the slip no crude gate sees"
    rc = mod.risk_coverage(drp["rows"], [0.0, 0.8, 0.9, 1.0])
    assert near(rc[0][2], 1 / 8) and near(rc[2][2], 0.0), "a support threshold of 0.9 removes the only wrong answer from the answered set"
    v = dict(rej["verdicts"])
    return (f"reject mode: coverage {rej['coverage']:.0%}, risk {rej['risk']:.0%} ({dict(rej['counts'])})\n"
            f"drop mode:   coverage {drp['coverage']:.0%}, risk {drp['risk']:.0%}\n"
            f"what the model's 13 claims did at the gates: {v}\n"
            f"support >= 0.9 on the answered set: coverage {rc[2][1]:.0%}, risk {rc[2][2]:.0%}")


MILESTONES = [
    (1, "Milestone 1: sentence spans and chunks with offsets", m1),
    (2, "Milestone 2: the labelled, budgeted context", m2),
    (3, "Milestone 3: gates 1 and 2, the pointer and the quote", m3),
    (4, "Milestone 4: gate 3, does the span support the claim?", m4),
    (5, "Milestone 5: parsing the reply and the verified pipeline", m5),
    (6, "Milestone 6: measuring answers, risk and coverage", m6),
]

if __name__ == "__main__":
    t0 = time.time()
    print(f"Lab 5 checks against {target}.py\n")
    for n, name, fn in MILESTONES:
        check(n, name, fn)
    print(f"\n{sum(results)}/{len(results)} milestones passing  ({time.time() - t0:.1f} s)")
    sys.exit(0 if all(results) else 1)
