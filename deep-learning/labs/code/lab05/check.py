"""Self-check for Lab 5: A BPE Tokeniser & Decoders.

    python3 check.py                  # checks your starter.py
    python3 check.py solution         # checks the reference solution
    python3 check.py solution 3       # only milestone 3
    python3 check.py solution 3 17    # milestone 3, replaying ONLY the random case with seed 17

Everything is seeded: the random strings, the random distributions, the random draws. There is no
clock and no network, so every run gives identical numbers. The whole check takes a few seconds.
Prints a tick, a cross, or "not implemented yet" for each milestone.
"""
import importlib
import math
import os
import random
import re
import sys
import time
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


def vec_near(a, b, tol=1e-9):
    return len(a) == len(b) and all(near(x, y, tol) for x, y in zip(a, b))


# ---- independent oracles: plain loops, written differently from the solution ----------------------------
PIECE = re.compile(r" ?[^\W\d_]+| ?\d+| ?[^\s\w]+|\s+(?!\S)|\s+")


def o_merge(ids, pair, new):
    out = list(ids)
    i = 0
    while i < len(out) - 1:
        if (out[i], out[i + 1]) == pair:
            out[i:i + 2] = [new]
        i += 1
    return out


def o_train(text, n):
    """Naive BPE: one flat token list per word *occurrence*, no counting trick."""
    toks = [list(w.encode("utf-8")) for w in PIECE.findall(text)]
    merges = {}
    for k in range(n):
        c = Counter()
        for t in toks:
            for i in range(len(t) - 1):
                c[(t[i], t[i + 1])] += 1
        if not c:
            break
        top = max(c.values())
        pair = min(p for p in c if c[p] == top)
        merges[pair] = 256 + k
        toks = [o_merge(t, pair, 256 + k) for t in toks]
    return merges


def o_encode(text, merges):
    out = []
    for piece in PIECE.findall(text):
        t = list(piece.encode("utf-8"))
        for pair, new in merges.items():            # apply the merges one after another, in learning order
            t = o_merge(t, pair, new)
        out += t
    return out


def o_softmax(logits, tau=1.0):
    z = [x / tau for x in logits]
    m = max(z)
    e = [math.exp(x - m) for x in z]
    return [x / sum(e) for x in e]


def o_norm(p, keep):
    s = sum(p[i] for i in keep)
    return [p[i] / s if i in keep else 0.0 for i in range(len(p))]


def o_topk(p, k):
    order = sorted(range(len(p)), key=lambda i: (-p[i], i))
    return o_norm(p, set(order[:k]))


def o_topp(p, top):
    order = sorted(range(len(p)), key=lambda i: (-p[i], i))
    keep, acc = set(), 0.0
    for i in order:
        if acc >= top and keep:
            break
        keep.add(i)
        acc += p[i]
    return o_norm(p, keep)


def o_minp(p, frac):
    return o_norm(p, {i for i in range(len(p)) if p[i] >= frac * max(p)})


ALPHABETS = [
    "ab ",                                                        # tiny alphabet: lots of repeated pairs
    "abcdefghijklmnopqrstuvwxyz  ",                               # English-like
    "abcdefghij 0123456789.,!?\n\t",                              # digits, punctuation, white space
    "aeiou tnsrlé東京ü👍🙏\n  ",                                    # multi-byte characters
]


def rand_text(rng, max_len=60):
    alpha = rng.choice(ALPHABETS)
    return "".join(rng.choice(alpha) for _ in range(rng.randint(0, max_len)))


CORPUS = mod.load_corpus() if hasattr(mod, "load_corpus") else open(os.path.join(HERE, "corpus.txt"), encoding="utf-8").read()
CRAFTED = " low" * 5 + " lower" * 2 + " newest" * 6 + " widest" * 3
HELD_OUT = ("The bakery on the corner opens at six. Tomorrow we will compare 3 prices, taste 12 loaves, "
            "and write down what the customers said about the café, the crust and the queue.")
_tables = {}


def table(n):
    """A merge table trained by the oracle, so milestones 3 to 5 do not depend on milestone 2."""
    if n not in _tables:
        _tables[n] = o_train(CORPUS, n)
    return _tables[n]


# =============================================================================
# Milestone 1: bytes, pair counts and one merge
# =============================================================================
def m1():
    for text, want in [("hi", [104, 105]), ("", []), ("é", [195, 169]), ("👍", [240, 159, 145, 141]), ("a\nb", [97, 10, 98])]:
        got = mod.utf8_ids(text)
        assert got == want, f"utf8_ids({text!r}) should be {want} (the UTF-8 bytes), got {got}"
    got = mod.utf8_ids("東")
    assert len(got) == 3 and all(0 <= b < 256 for b in got), f"'東' is three UTF-8 bytes, got {got}"

    for ids, pair, new, want in [
        ([1, 2, 3, 1, 2], (1, 2), 9, [9, 3, 9]),
        ([5, 5, 5], (5, 5), 9, [9, 5]),
        ([5, 5, 5, 5], (5, 5), 9, [9, 9]),
        ([1, 2, 1], (2, 1), 7, [1, 7]),
        ([1, 2, 3], (4, 5), 9, [1, 2, 3]),
        ([], (1, 2), 9, []),
        ([7], (7, 7), 9, [7]),
    ]:
        before = list(ids)
        got = mod.merge_pair(ids, pair, new)
        assert got == want, (f"merge_pair({before}, {pair}, {new}) should be {want}, got {got}"
                             + ("  (hint: after merging two items in a run, skip both before looking for the next pair)" if before == [5, 5, 5] else ""))
        assert ids == before, "merge_pair must not modify its input list; build and return a new one"

    c = mod.count_pairs({" low": [32, 108, 111, 119], " lo": [32, 108, 111]}, {" low": 5, " lo": 2})
    assert dict(c) == {(32, 108): 7, (108, 111): 7, (111, 119): 5}, f"count_pairs: each pair is weighted by its word's frequency; got {dict(c)}"
    assert not mod.count_pairs({"a": [1]}, {"a": 3}), "a one-token word has no pairs"
    assert mod.count_pairs({"x": [4, 4, 4]}, {"x": 1})[(4, 4)] == 2, "[4, 4, 4] contains the pair (4, 4) at two positions"
    bp = mod.best_pair(Counter({(1, 2): 4, (0, 9): 4, (0, 3): 4, (7, 7): 3}))
    assert bp == (0, 3), f"best_pair: three pairs tie at 4; the smaller first id wins and then the smaller second id, so (0, 3); got {bp}"
    assert mod.best_pair(Counter({(1, 2): 1, (3, 4): 5})) == (3, 4), "best_pair must prefer the higher count"

    note_seed = None
    for s in seeds(range(1, 41)):
        rng = random.Random(s)
        ids = [rng.randint(0, 4) for _ in range(rng.randint(0, 30))]
        pair = (rng.randint(0, 4), rng.randint(0, 4))
        got = mod.merge_pair(ids, pair, 99)
        assert got == o_merge(ids, pair, 99), f"seed {s}: merge_pair({ids}, {pair}, 99) gave {got}, expected {o_merge(ids, pair, 99)}"
        back = []
        for t in got:
            back += list(pair) if t == 99 else [t]
        assert back == ids, f"seed {s}: expanding the new token back must give the original ids"
        note_seed = s
    return "merge_pair agrees with an independent loop on 40 seeded random sequences and expands back exactly"


# =============================================================================
# Milestone 2: training
# =============================================================================
def m2():
    m = mod.train_bpe(CRAFTED, 3)
    first = list(m.items())
    assert first == [((101, 115), 256), ((256, 116), 257), ((32, 108), 258)], (
        f"on ' low'x5 ' lower'x2 ' newest'x6 ' widest'x3 the first merges are e+s (the tie with s+t goes to the smaller id), "
        f"then es+t, then space+l (a three-way tie at 7, smaller first id wins); got {first}")
    assert mod.train_bpe("", 5) == {}, "no text, no merges"
    assert len(mod.train_bpe("ab", 10)) == 1, "'ab' is one pair; after merging it there is nothing left, so training stops after 1 merge"
    assert list(mod.train_bpe("aaaa aaaa", 1)) == [(97, 97)], "a repeated byte pairs with itself"
    m0 = mod.train_bpe(CRAFTED, 0)
    assert m0 == {}, "n_merges = 0 gives an empty table"

    sp = mod.train_bpe("ab ab ab ab", 20)
    vb = {i: bytes([i]) for i in range(256)}
    for (a, b), n in sp.items():
        vb[n] = vb[a] + vb[b]
        assert b" " not in vb[n][1:], (f"merge {n} = {vb[n]!r} spans two words: pre-tokenise with the regular expression first, so the "
                                       "pairs are counted inside each piece only")

    note = ""
    for s in seeds(range(1, 5)):
        rng = random.Random(s)
        text = " ".join(rng.choice(["the", "then", "there", "cat", "cart", "a", "at", "tea", "teal", "11", "x!"]) for _ in range(rng.randint(5, 80)))
        k = rng.randint(1, 25)
        got, want = mod.train_bpe(text, k), o_train(text, k)
        assert list(got.items()) == list(want.items()), (
            f"seed {s}: train_bpe on a {len(text)}-character text with {k} merges differs from a naive reference.\n"
            f"        yours:     {list(got.items())[:6]} ...\n        reference: {list(want.items())[:6]} ...\n"
            "        (check the tie-break and that each word is weighted by its frequency)")
    for n in (10, 100, 200):
        got, want = mod.train_bpe(CORPUS, n), table(n)
        assert list(got.items()) == list(want.items()), f"{n} merges on corpus.txt differ from the reference table; first difference at merge " \
            f"{next(i for i, (a, b) in enumerate(zip(got.items(), want.items())) if a != b) if len(got) == len(want) else min(len(got), len(want))}"
    note = f"corpus.txt ({len(CORPUS.encode()):,} bytes): 200 merges match the reference table; first three merges are " \
           + ", ".join(repr(bytes(_expand(table(5), p))) for p in list(table(3))[:3])
    return note


def _expand(merges, pair):
    vb = {i: bytes([i]) for i in range(256)}
    for (a, b), n in merges.items():
        vb[n] = vb[a] + vb[b]
    return vb[pair[0]] + vb[pair[1]]


# =============================================================================
# Milestone 3: encode and decode
# =============================================================================
def m3():
    m = table(10)
    vb = mod.vocab_bytes(m)
    assert all(vb[i] == bytes([i]) for i in range(256)), "tokens 0..255 are the single bytes"
    assert vb[256] == _expand(m, next(iter(m))), f"token 256 stands for the concatenation of its two parts, got {vb[256]!r}"
    top = max(m.values())
    assert set(vb) == set(range(top + 1)), "vocab_bytes must have an entry for every id from 0 to the last merge"

    cm = o_train(CRAFTED, 5)
    ids = mod.encode(" lowest", cm)
    pieces = [mod.vocab_bytes(cm)[i] for i in ids]
    assert pieces == [b" low", b"est"], (f"after 5 merges the unseen word ' lowest' should split into ' low' + 'est', "
                                         f"got {pieces} (ids {ids}); apply the earliest-learned merge first, and keep going until none applies")
    assert mod.encode("", cm) == [], "empty text encodes to no tokens"
    assert mod.encode("é", {}) == [195, 169], "with no merges, encode gives the raw UTF-8 bytes"
    assert mod.decode([], cm) == "", "decoding no tokens gives the empty string"
    assert mod.decode([240, 159], {}) == "�", \
        "the first two bytes of a four-byte emoji are not valid UTF-8; decode should give the replacement character U+FFFD, not raise"
    assert mod.decode([240, 159, 145, 141], {}) == "👍", "four bytes make one thumbs-up"
    a, b = "the ca", "t sat"
    assert mod.decode(mod.encode(a, table(60)) + mod.encode(b, table(60)), table(60)) == a + b, "decoding concatenated id lists gives concatenated text"

    n_checked = 0
    for s in seeds(range(1, 61)):
        rng = random.Random(s)
        text = rand_text(rng, 70)
        for n in (0, 25, 200):
            mt = table(n)
            got = mod.encode(text, mt)
            want = o_encode(text, mt)
            assert got == want, (f"seed {s}, {n} merges: encode({text!r}) gave {got} but applying the merges one by one in order gives {want}")
            assert all(0 <= t < 256 + len(mt) for t in got), f"seed {s}: token ids must stay below {256 + len(mt)}"
            back = mod.decode(got, mt)
            assert back == text, f"seed {s}, {n} merges: decode(encode(text)) must return the text exactly; text {text!r}, got {back!r}"
            n_checked += 1
    rng = random.Random(7)
    text = "".join(rng.choice(["x", "y", " ", "ñ", "😀"]) for _ in range(40))
    assert mod.decode(mod.encode(text, table(200)), table(200)) == text, "round trip with an emoji and an accent"

    r0 = len(HELD_OUT.encode()) / len(mod.encode(HELD_OUT, {}))
    r50 = len(HELD_OUT.encode()) / len(mod.encode(HELD_OUT, table(50)))
    r200 = len(HELD_OUT.encode()) / len(mod.encode(HELD_OUT, table(200)))
    assert r0 == 1.0 and r0 < r50 < r200, f"more merges should mean fewer tokens on unseen text: bytes per token {r0:.2f}, {r50:.2f}, {r200:.2f}"
    return (f"{n_checked} random strings round-trip and match a one-merge-at-a-time reference\n"
            f"held-out sentence: {r0:.2f} bytes/token with 0 merges, {r50:.2f} with 50, {r200:.2f} with 200")


# =============================================================================
# Milestone 4: reshaping a distribution
# =============================================================================
def m4():
    assert vec_near(mod.softmax([0.0, 0.0]), [0.5, 0.5]), "equal logits give equal probabilities"
    assert vec_near(mod.softmax([math.log(3), 0.0]), [0.75, 0.25]), "softmax([ln 3, 0]) = [3/4, 1/4]"
    r = math.sqrt(3)
    assert vec_near(mod.softmax([math.log(3), 0.0], 2.0), [r / (r + 1), 1 / (r + 1)]), \
        "temperature 2 divides the logits by 2 before the softmax: [sqrt(3), 1] / (sqrt(3) + 1)"
    got = mod.softmax([1000.0, 999.0])
    assert near(sum(got), 1.0) and got[0] > got[1], "softmax([1000, 999]) overflows unless you subtract the maximum first"
    for tau in (0.0, -1.0):
        try:
            mod.softmax([1.0, 2.0], tau)
        except ValueError:
            pass
        else:
            raise AssertionError(f"softmax with temperature {tau} must raise ValueError")

    P = [0.5, 0.25, 0.125, 0.125]
    third = [2 / 3, 1 / 3, 0.0, 0.0]
    cases = [
        ("top_k_filter", mod.top_k_filter, P, 2, third),
        ("top_k_filter", mod.top_k_filter, P, 1, [1.0, 0.0, 0.0, 0.0]),
        ("top_k_filter", mod.top_k_filter, P, 3, [0.5 / 0.875, 0.25 / 0.875, 0.125 / 0.875, 0.0]),   # tie at rank 3: the smaller id wins
        ("top_k_filter", mod.top_k_filter, P, 10, P),
        ("top_p_filter", mod.top_p_filter, P, 0.4, [1.0, 0.0, 0.0, 0.0]),
        ("top_p_filter", mod.top_p_filter, P, 0.5, [1.0, 0.0, 0.0, 0.0]),       # mass already 0.5 >= p: stop
        ("top_p_filter", mod.top_p_filter, P, 0.7, third),
        ("top_p_filter", mod.top_p_filter, P, 0.75, third),
        ("top_p_filter", mod.top_p_filter, P, 0.8, [0.5 / 0.875, 0.25 / 0.875, 0.125 / 0.875, 0.0]),
        ("top_p_filter", mod.top_p_filter, P, 1.0, P),
        ("top_p_filter", mod.top_p_filter, [0.0, 0.6, 0.4], 1.0, [0.0, 0.6, 0.4]),
        ("min_p_filter", mod.min_p_filter, [0.6, 0.3, 0.07, 0.03], 0.1, [x / 0.97 if i < 3 else 0.0 for i, x in enumerate([0.6, 0.3, 0.07, 0.03])]),
        ("min_p_filter", mod.min_p_filter, [0.6, 0.3, 0.07, 0.03], 0.0, [0.6, 0.3, 0.07, 0.03]),
        ("min_p_filter", mod.min_p_filter, [0.6, 0.3, 0.07, 0.03], 0.6, [1.0, 0.0, 0.0, 0.0]),
    ]
    for name, fn, p, arg, want in cases:
        before = list(p)
        got = fn(p, arg)
        assert vec_near(got, want), f"{name}({before}, {arg}) should be {[round(x, 4) for x in want]}, got {[round(x, 4) for x in got]}"
        assert p == before, f"{name} must not modify its input"
    assert vec_near(mod.top_k_filter([0.1, 0.4, 0.4, 0.1], 2), [0.0, 0.5, 0.5, 0.0]), "two tokens tie for the top: both survive k = 2"
    assert vec_near(mod.top_k_filter([0.25] * 4, 2), [0.5, 0.5, 0.0, 0.0]), "a four-way tie with k = 2 keeps the two smallest ids"

    note = ""
    for s in seeds(range(1, 41)):
        rng = random.Random(s)
        V = rng.randint(2, 30)
        logits = [rng.gauss(0, 2) for _ in range(V)]
        tau = rng.choice([0.3, 0.7, 1.0, 1.5])
        p = mod.softmax(logits, tau)
        assert near(sum(p), 1.0) and vec_near(p, o_softmax(logits, tau)), f"seed {s}: softmax(…, {tau}) differs from the textbook formula"
        order = lambda q: sorted(range(len(q)), key=lambda i: (-q[i], i))
        assert order(p) == order(o_softmax(logits, 1.0)), f"seed {s}: temperature must not change the ranking of tokens"
        k = rng.randint(1, V)
        assert vec_near(mod.top_k_filter(p, k), o_topk(p, k)), f"seed {s}: top_k_filter(p, {k}) differs from the reference"
        f = rng.choice([0.05, 0.2, 0.5, 0.9])
        assert vec_near(mod.min_p_filter(p, f), o_minp(p, f)), f"seed {s}: min_p_filter(p, {f}) differs from the reference"
        top = rng.choice([0.3, 0.6, 0.9, 0.95])
        got = mod.top_p_filter(p, top)
        ranked = order(p)
        run, edge = 0.0, False
        for i in ranked:
            edge = edge or abs(run - top) < 1e-9
            run += p[i]
        if not edge:                                   # skip the knife-edge cases where float rounding decides
            assert vec_near(got, o_topp(p, top)), f"seed {s}: top_p_filter(p, {top}) differs from the reference (kept {sum(x > 0 for x in got)} tokens, expected {sum(x > 0 for x in o_topp(p, top))})"
        kept = [i for i in range(V) if got[i] > 0]
        mass = sum(p[i] for i in kept)
        assert mass >= top - 1e-9, f"seed {s}: the nucleus holds only {mass:.4f} of the mass, below p = {top}"
        assert mass - min(p[i] for i in kept) < top + 1e-9 or len(kept) == 1, f"seed {s}: the nucleus is larger than needed (drop its least likely token and it still reaches p = {top})"
        assert near(sum(got), 1.0), f"seed {s}: filters must renormalise so the result sums to 1"
        note = f"40 random distributions: softmax, top-k, top-p and min-p agree with the references"
    return note


# =============================================================================
# Milestone 5: drawing a token and generating text
# =============================================================================
class Spy:
    """A model that records the contexts it is called with and returns fixed logits."""
    def __init__(self, logits):
        self.logits, self.calls = logits, []

    def __call__(self, ids):
        self.calls.append(list(ids))
        return list(self.logits)


def m5():
    p = [0.2, 0.5, 0.3]
    for u, want in [(0.0, 0), (0.19, 0), (0.2, 1), (0.69, 1), (0.7, 2), (0.999999, 2)]:
        got = mod.sample_from(p, u)
        assert got == want, f"sample_from({p}, {u}) should be {want} (running totals 0.2, 0.7, 1.0; the first one above u), got {got}"
    for u in (0.0, 0.3, 0.999999999999):
        got = mod.sample_from([0.0, 1.0, 0.0], u)
        assert got == 1, f"sample_from([0, 1, 0], {u}) must be 1: a zero-probability token is never drawn, got {got}"
    got = mod.sample_from([0.3, 0.3, 0.0], 0.95)
    assert got in (0, 1), f"u past the total (rounding) must still return a token with non-zero probability, got {got}"

    rng = random.Random(5)
    probs = [0.05, 0.4, 0.0, 0.25, 0.3]
    counts = Counter(mod.sample_from(probs, rng.random()) for _ in range(30000))
    for i, pr in enumerate(probs):
        f = counts[i] / 30000
        assert abs(f - pr) < 0.015, f"over 30,000 draws token {i} should appear {pr:.2f} of the time, got {f:.3f}"
    assert mod.greedy([0.1, 0.7, 0.2]) == 1 and mod.greedy([-3.0, -1.0, -2.0]) == 1, "greedy is the argmax (logits or probabilities)"
    assert mod.greedy([0.4, 0.4, 0.2]) == 0, "greedy breaks ties towards the smaller id"

    # next_token: temperature 0 uses no randomness; otherwise exactly one rng.random() call per step
    r = random.Random(3)
    state = r.getstate()
    assert mod.next_token([0.1, 2.0, 0.3], r, temperature=0) == 1, "temperature 0 is greedy"
    assert r.getstate() == state, "greedy must not consume random numbers"
    r1, r2 = random.Random(9), random.Random(9)
    mod.next_token([0.1, 2.0, 0.3], r1)
    r2.random()
    assert r1.getstate() == r2.getstate(), "next_token must call rng.random() exactly once"
    seen = {mod.next_token([5.0, 4.0, 3.0, 0.0], random.Random(s), top_k=1) for s in range(20)}
    assert seen == {0}, f"top_k=1 is greedy, got tokens {seen}"

    for s in seeds(range(1, 41)):
        rng = random.Random(s)
        V = rng.randint(3, 25)
        logits = [rng.gauss(0, 2) for _ in range(V)]
        kw = {"temperature": rng.choice([0.5, 1.0, 1.4])}
        if rng.random() < 0.6: kw["top_k"] = rng.randint(1, V)
        if rng.random() < 0.6: kw["top_p"] = rng.choice([0.5, 0.8, 0.95])
        if rng.random() < 0.4: kw["min_p"] = rng.choice([0.05, 0.2])
        q = o_softmax(logits, kw["temperature"])
        if "top_k" in kw: q = o_topk(q, kw["top_k"])
        if "top_p" in kw: q = o_topp(q, kw["top_p"])
        if "min_p" in kw: q = o_minp(q, kw["min_p"])
        u_rng = random.Random(1000 + s)
        u = u_rng.random()
        tot, want = 0.0, None
        for i, x in enumerate(q):
            tot += x
            if x > 0 and u < tot:
                want = i
                break
        if want is None:
            want = max(i for i, x in enumerate(q) if x > 0)
        got = mod.next_token(logits, random.Random(1000 + s), **kw)
        assert got == want, (f"seed {s}: next_token(logits, rng, {kw}) with u = {u:.4f} should draw token {want}, got {got}. "
                             "Apply the steps in the documented order (temperature, top-k, top-p, min-p), renormalising after each filter.")

    # generate: contract
    spy = Spy([0.0, 0.0, 5.0, 0.0])
    out = mod.generate(spy, [1, 1], 4, random.Random(0), temperature=0)
    assert out == [1, 1, 2, 2, 2, 2], f"generate with a model that always prefers token 2: expected [1, 1, 2, 2, 2, 2], got {out}"
    assert spy.calls[0] == [1, 1] and spy.calls[3] == [1, 1, 2, 2, 2], f"the model must see the whole context so far at each step, saw {spy.calls}"
    prompt = [1, 1]
    mod.generate(spy, prompt, 3, random.Random(0), temperature=0)
    assert prompt == [1, 1], "generate must not modify the prompt list"
    out = mod.generate(spy, [0], 10, random.Random(0), stop_id=2, temperature=0)
    assert out == [0, 2], f"stop_id: generation ends right after emitting the stop token (included), got {out}"
    assert mod.generate(spy, [0], 0, random.Random(0)) == [0], "n_new = 0 returns the prompt"
    a = mod.generate(spy, [0], 12, random.Random(4), top_p=0.99)
    b = mod.generate(spy, [0], 12, random.Random(4), top_p=0.99)
    assert a == b, "the same seed must give the same text"

    # scenario: a real tokeniser, a real (tiny) language model, four decoders
    mt = table(150)
    V = 256 + len(mt)
    ids = o_encode(CORPUS, mt)
    lm = mod.NGramModel(ids, V)
    prompt = o_encode("The ", mt)
    g = mod.generate(lm, prompt, 100, random.Random(0), temperature=0)
    state_seen, loop_at = {}, None
    for i in range(1, len(g)):
        st = (g[i - 1], g[i])
        if st in state_seen:
            loop_at = (state_seen[st], i)
            break
        state_seen[st] = i
    assert loop_at is not None, "greedy decoding from a model that looks at the last two tokens must enter a loop within 100 tokens"
    text_g = mod.decode(g, mt)
    cut = 0.001                                      # tokens the model gives under 0.1% are the smoothing tail
    junk = {}
    for name, kw in [("plain sampling", {}), ("top-p 0.9", {"top_p": 0.9}), ("top-k 40", {"top_k": 40}), ("min-p 0.05", {"min_p": 0.05})]:
        rng = random.Random(11)
        n_junk = 0
        for _ in range(6):
            ctx = list(prompt)
            for _ in range(100):
                probs = o_softmax(lm(ctx))
                t = mod.next_token(lm(ctx), rng, **kw)
                n_junk += probs[t] < cut
                ctx.append(t)
        junk[name] = n_junk
    assert junk["plain sampling"] >= 5, f"plain sampling should now and then draw a tail token, drew {junk['plain sampling']} in 600 steps"
    assert junk["top-p 0.9"] == 0 and junk["min-p 0.05"] == 0, \
        f"top-p 0.9 and min-p 0.05 cut the tail: junk tokens drawn were {junk['top-p 0.9']} and {junk['min-p 0.05']}, expected 0"
    shown = text_g[:46].replace("\n", " ")
    return (f"greedy from 'The ' enters a loop (\"{shown}...\")\n"
            f"tail tokens drawn in 600 steps: plain {junk['plain sampling']}, top-p 0.9 {junk['top-p 0.9']}, min-p 0.05 {junk['min-p 0.05']}, top-k 40 {junk['top-k 40']}")


t0 = time.time()
check(1, "Milestone 1: bytes, pair counts and one merge", m1)
check(2, "Milestone 2: training byte-pair encoding", m2)
check(3, "Milestone 3: encode, decode and the round trip", m3)
check(4, "Milestone 4: temperature, top-k, top-p and min-p", m4)
check(5, "Milestone 5: sampling and generation", m5)
print(f"\n{sum(results)}/{len(results)} milestones passing  ({time.time() - t0:.1f} s)")
