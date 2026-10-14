"""Self-check for Lab 2: Word Embeddings (skip-gram with negative sampling).

    python3 check.py                  # checks your starter.py
    python3 check.py solution         # checks the reference solution
    python3 check.py solution 3       # only milestone 3
    python3 check.py solution 3 17    # milestone 3, replaying ONLY the random case with seed 17

Everything is seeded: the toy corpus, the sampling, the initial vectors. There is no clock and
no network, so every run gives identical numbers. Milestone 4 trains a small model (about two
seconds); milestone 5 uses the saved vectors in vectors.json so it does not depend on milestone 4.
Prints a tick, a cross, or "not implemented yet" for each milestone.
"""
import importlib
import json
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
results = []
T0 = time.time()


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


def close(a, b, tol=1e-9):
    if isinstance(a, (int, float)):
        return abs(a - b) <= tol
    return len(a) == len(b) and all(close(x, y, tol) for x, y in zip(a, b))


# =============================================================================
# Milestone 1: from text to (centre, context) pairs
# =============================================================================
def m1():
    got = mod.tokenise("The cat sat. The dog sat!  Is it?")
    assert got == [["the", "cat", "sat"], ["the", "dog", "sat"], ["is", "it"]], \
        f"tokenise should split on . ! ? and lowercase the words; got {got}"
    assert mod.tokenise("Hello,   WORLD... ") == [["hello", "world"]], "punctuation inside a sentence is dropped and empty sentences are skipped"
    assert mod.tokenise("Don't stop.") == [["don't", "stop"]], "an apostrophe stays inside a word: [\"don't\", 'stop']"
    assert mod.tokenise("") == [], "empty text has no sentences"

    sents = [["a", "b", "a"], ["b", "a", "c"]]
    vocab, counts = mod.build_vocab(sents)
    assert (vocab, counts) == (["a", "b", "c"], [3, 2, 1]), f"vocab sorts by count, most frequent first: expected (['a', 'b', 'c'], [3, 2, 1]); got {(vocab, counts)}"
    vocab, counts = mod.build_vocab([["y", "x", "z", "x", "y"]])
    assert vocab == ["x", "y", "z"] and counts == [2, 2, 1], f"ties break alphabetically: expected ['x', 'y', 'z'] with counts [2, 2, 1]; got {(vocab, counts)}"
    vocab, counts = mod.build_vocab(sents, min_count=2)
    assert (vocab, counts) == (["a", "b"], [3, 2]), "min_count=2 should drop 'c', which appears once"

    idx = {"a": 0, "b": 1, "c": 2, "d": 3}
    got = sorted(mod.make_pairs([["a", "b", "c"]], idx, 1))
    assert got == [(0, 1), (1, 0), (1, 2), (2, 1)], f"window 1 on 'a b c' gives (a,b), (b,a), (b,c), (c,b); got {got}"
    got = mod.make_pairs([["a", "b", "c", "d"]], idx, 2)
    assert len(got) == 10 and (0, 2) in got and (0, 3) not in got and (3, 1) in got, \
        f"window 2 on 'a b c d' gives 10 pairs (a pairs with b, c but not d); got {len(got)} pairs"
    assert mod.make_pairs([["a"]], idx, 2) == [], "a one-word sentence has no pairs"
    got = sorted(mod.make_pairs([["a", "zzz", "b"]], {"a": 0, "b": 1}, 1))
    assert got == [(0, 1), (1, 0)], f"words outside the vocabulary are dropped BEFORE windowing, so a and b become neighbours; got {got}"
    got = sorted(mod.make_pairs([["a", "b"], ["c", "d"]], idx, 3))
    assert got == [(0, 1), (1, 0), (2, 3), (3, 2)], f"windows must not cross sentence boundaries; got {got}"

    for seed in seeds(range(1, 21)):
        rng = random.Random(seed)
        words = ["w%d" % i for i in range(5)]
        sentences = [[rng.choice(words) for _ in range(rng.randint(1, 7))] for _ in range(rng.randint(1, 5))]
        window = rng.randint(1, 4)
        vocab, counts = mod.build_vocab(sentences)
        index = {w: i for i, w in enumerate(vocab)}
        pairs = mod.make_pairs(sentences, index, window)
        want = sum(min(len(s) - 1, i + window) - max(0, i - window) for s in sentences for i in range(len(s)))
        assert len(pairs) == want, f"[seed {seed}] expected {want} pairs for window {window}; got {len(pairs)}"
        assert sum(counts) == sum(len(s) for s in sentences), f"[seed {seed}] counts must add up to the number of words"
        assert counts == sorted(counts, reverse=True), f"[seed {seed}] counts must be in decreasing order"
    return "tokenise, build_vocab and make_pairs agree with hand values and 20 random corpora"


# =============================================================================
# Milestone 2: negative sampling
# =============================================================================
def m2():
    p = mod.noise_distribution([8, 1])
    assert close(p, [0.82625, 0.17375], 1e-4), f"counts [8, 1] raised to 0.75 give weights 4.757 and 1, so probabilities [0.8263, 0.1737]; got {p}"
    assert close(mod.noise_distribution([8, 1], power=1.0), [8 / 9, 1 / 9]), "power 1 is the plain unigram distribution [8/9, 1/9]"
    assert close(mod.noise_distribution([8, 1], power=0.0), [0.5, 0.5]), "power 0 makes every word equally likely"
    assert abs(sum(mod.noise_distribution([5, 3, 2, 1])) - 1) < 1e-12, "probabilities must sum to 1"

    cum = mod.cumulative([0.5, 0.3, 0.2])
    rng = random.Random(0)
    out = mod.sample_negatives(cum, 7, 1, rng)
    assert len(out) == 7 and all(isinstance(n, int) for n in out), f"sample_negatives(cum, 7, ...) must return 7 integer ids; got {out}"
    assert all(0 <= n < 3 for n in out), f"ids must lie in 0..2; got {out}"

    for seed in seeds([1, 2, 3]):
        rng = random.Random(seed)
        counts = [0, 0, 0]
        for _ in range(4000):
            for n in mod.sample_negatives(cum, 5, -1, rng):
                counts[n] += 1
        total = sum(counts)
        freq = [c / total for c in counts]
        assert close(freq, [0.5, 0.3, 0.2], 0.015), f"[seed {seed}] 20,000 draws from probabilities [0.5, 0.3, 0.2] gave frequencies {[round(f, 3) for f in freq]}"
        rng = random.Random(seed)
        counts = [0, 0, 0]
        for _ in range(4000):
            ns = mod.sample_negatives(cum, 5, 0, rng)
            assert 0 not in ns, f"[seed {seed}] sample_negatives returned the avoided id 0 in {ns}; the true context must never be its own negative"
            for n in ns:
                counts[n] += 1
        freq = [c / sum(counts) for c in counts]
        assert close(freq, [0.0, 0.6, 0.4], 0.015), (f"[seed {seed}] with id 0 avoided the remaining mass is re-normalised to [0, 0.6, 0.4]; "
                                                       f"got {[round(f, 3) for f in freq]}. Redraw when you hit `avoid`; do not just skip or clip.")
        zero = mod.cumulative([0.5, 0.0, 0.5])
        seen = {n for _ in range(3000) for n in mod.sample_negatives(zero, 1, -1, rng)}
        assert seen == {0, 2}, f"[seed {seed}] a word with probability 0 must never be sampled; got ids {sorted(seen)}"

    a = mod.sample_negatives(cum, 6, 2, random.Random(5))
    random.seed(999)
    b = mod.sample_negatives(cum, 6, 2, random.Random(5))
    assert a == b, "sample_negatives must draw only from the rng it is given (so the same seed gives the same negatives)"
    return "noise_distribution and sample_negatives match hand values and the sampling frequencies over 20,000 draws"


# =============================================================================
# Milestone 3: the loss and its gradient for one pair
# =============================================================================
def m3():
    assert close(mod.sigmoid(0.0), 0.5) and close(mod.sigmoid(2.0), 0.8807970779778823, 1e-9), "sigmoid(0) is 0.5 and sigmoid(2) is 0.8808"
    assert mod.sigmoid(800.0) == 1.0 and 0.0 <= mod.sigmoid(-800.0) < 1e-300, \
        "sigmoid must survive large inputs: sigmoid(800) = 1.0 and sigmoid(-800) is a tiny positive number (no OverflowError)"

    loss = mod.sgns_loss([0.0, 0.0], [0.0, 0.0], [[0.0, 0.0], [0.0, 0.0]])
    assert close(loss, 3 * math.log(2), 1e-9), f"with all-zero vectors every score is 0 and every term costs ln 2, so two negatives give 3 ln 2 = 2.0794; got {loss}"

    # The worked example of chapter 06: "cat" predicts "eats", with the noise words "rice" and "the".
    v, u_pos, u_negs = [0.5, -0.2], [0.3, 0.4], [[-0.4, 0.1], [0.2, -0.6]]
    loss = mod.sgns_loss(v, u_pos, u_negs)
    assert close(loss, 2.0571, 5e-5), f"chapter 06's example has loss 2.0571; got {loss:.4f}. The true pair costs -ln sigmoid(v.u); each noise word costs -ln sigmoid(-v.u)."
    gv, gp, gn = mod.sgns_grads(v, u_pos, u_negs)
    assert close(gv, [-0.2119, -0.4813], 5e-5), f"gradient on v should be [-0.2119, -0.4813]; got {[round(x, 4) for x in gv]}"
    assert close(gp, [-0.2413, 0.0965], 5e-4), f"gradient on u_pos is (sigmoid(s) - 1) v = [-0.2413, 0.0965]; got {[round(x, 4) for x in gp]}"
    assert len(gn) == 2 and close(gn[0], [0.2226, -0.0891], 5e-4) and close(gn[1], [0.2774, -0.1110], 5e-4), \
        f"gradients on the noise vectors are sigmoid(s) v: expected [[0.2226, -0.0891], [0.2774, -0.1110]]; got {gn}"
    assert v == [0.5, -0.2] and u_pos == [0.3, 0.4], "sgns_loss and sgns_grads must not modify their inputs"

    for seed in seeds(range(1, 16)):
        rng = random.Random(seed)
        d, k = rng.randint(2, 5), rng.randint(1, 4)
        v = [rng.uniform(-1, 1) for _ in range(d)]
        up = [rng.uniform(-1, 1) for _ in range(d)]
        un = [[rng.uniform(-1, 1) for _ in range(d)] for _ in range(k)]
        gv, gp, gn = mod.sgns_grads(v, up, un)
        assert len(gv) == d and len(gp) == d and len(gn) == k and all(len(g) == d for g in gn), f"[seed {seed}] gradient shapes must mirror the inputs (d={d}, k={k})"
        eps = 1e-6

        def f(v_, p_, n_):
            return mod.sgns_loss(v_, p_, n_)

        for i in range(d):
            vp, vm = v[:], v[:]
            vp[i] += eps
            vm[i] -= eps
            num = (f(vp, up, un) - f(vm, up, un)) / (2 * eps)
            assert abs(num - gv[i]) < 1e-6, f"[seed {seed}] d loss / d v[{i}]: finite difference {num:.6f}, sgns_grads {gv[i]:.6f}"
            pp, pm = up[:], up[:]
            pp[i] += eps
            pm[i] -= eps
            num = (f(v, pp, un) - f(v, pm, un)) / (2 * eps)
            assert abs(num - gp[i]) < 1e-6, f"[seed {seed}] d loss / d u_pos[{i}]: finite difference {num:.6f}, sgns_grads {gp[i]:.6f}"
            for j in range(k):
                np_, nm = [r[:] for r in un], [r[:] for r in un]
                np_[j][i] += eps
                nm[j][i] -= eps
                num = (f(v, up, np_) - f(v, up, nm)) / (2 * eps)
                assert abs(num - gn[j][i]) < 1e-6, f"[seed {seed}] d loss / d u_neg[{j}][{i}]: finite difference {num:.6f}, sgns_grads {gn[j][i]:.6f}"
    return "sigmoid, sgns_loss and sgns_grads reproduce chapter 06's worked example and pass a finite-difference check"


# =============================================================================
# Milestone 4: the training loop
# =============================================================================
def m4():
    # Three words; the only real pair is (0, 1). Word 2 appears only as noise.
    W_in, W_out, losses = mod.train([(0, 1)] * 300, 3, [1, 1, 1], dim=4, negatives=2, lr=0.1, epochs=1, seed=0)
    assert len(W_in) == 3 and all(len(r) == 4 for r in W_in), f"W_in should have shape (vocab_size, dim) = (3, 4); got {len(W_in)} rows"
    assert len(W_out) == 3 and all(len(r) == 4 for r in W_out), "W_out should have shape (vocab_size, dim) = (3, 4)"
    assert len(losses) == 1, "train returns one mean loss per epoch"
    s_true = sum(a * b for a, b in zip(W_in[0], W_out[1]))
    s_noise = [sum(a * b for a, b in zip(W_in[0], W_out[j])) for j in (0, 2)]
    assert s_true > 0.5 and all(s < s_true - 0.5 for s in s_noise), (f"after 300 updates of the pair (0, 1) the score v0.u1 should be clearly positive and above the noise "
                                                                    f"scores; got true {s_true:.2f}, noise {[round(s, 2) for s in s_noise]}")

    sentences = mod.make_corpus(seed=3, n=1200)
    vocab, counts = mod.build_vocab(sentences)
    index = {w: i for i, w in enumerate(vocab)}
    pairs = mod.make_pairs(sentences, index, 2)
    t = time.time()
    W_in, W_out, losses = mod.train(pairs, len(vocab), counts, dim=16, negatives=5, lr=0.05, epochs=5, seed=1)
    secs = time.time() - t
    chance = 6 * math.log(2)
    assert len(losses) == 5, f"train must return one loss per epoch (5); got {len(losses)}"
    assert losses[0] < chance, f"even the first epoch should beat the chance level (1 + 5) ln 2 = {chance:.3f}; got {losses[0]:.3f}"
    assert losses[-1] < losses[0] and losses[-1] < 2.0, f"the loss should fall over the epochs and end below 2.0; got {[round(x, 3) for x in losses]}"
    assert any(x != 0 for r in W_out for x in r), "W_out is still all zeros: the output vectors must be updated too"
    E = mod.normalise_rows(W_in)

    def avg(pairs_):
        return sum(sum(a * b for a, b in zip(E[vocab.index(x)], E[vocab.index(y)])) for x, y in pairs_) / len(pairs_)

    animals, foods = list(mod.ANIMALS), mod.FOODS
    within = avg([(a, b) for i, a in enumerate(animals) for b in animals[i + 1:]])
    between = avg([(a, f) for a in animals for f in foods])
    assert within > between + 0.4, (f"animals share contexts, so animal-animal cosine should beat animal-food by a wide margin; "
                                    f"got {within:.2f} against {between:.2f}. Check that the gradients are applied with a minus sign and that negatives are sampled.")
    again = mod.train(pairs, len(vocab), counts, dim=16, negatives=5, lr=0.05, epochs=5, seed=1)
    assert again[0] == W_in and again[2] == losses, "the same seed must reproduce the same vectors and losses exactly"
    return f"loss {losses[0]:.3f} -> {losses[-1]:.3f} (chance {chance:.3f}); animal-animal cosine {within:.2f}, animal-food {between:.2f}  ({secs:.1f} s)"


# =============================================================================
# Milestone 5: neighbours and analogies
# =============================================================================
def m5():
    a, b = [1.0, 2.0, 2.0], [2.0, 4.0, 4.0]
    assert close(mod.cosine(a, b), 1.0, 1e-12), "parallel vectors have cosine 1 whatever their lengths"
    assert close(mod.cosine([1.0, 0.0], [0.0, 3.0]), 0.0, 1e-12) and close(mod.cosine([1.0, 0.0], [-2.0, 0.0]), -1.0, 1e-12), "perpendicular vectors give 0, opposite vectors -1"

    vocab = ["a", "b", "c", "d"]
    E = [[1.0, 0.0], [0.9, 0.1], [0.0, 1.0], [-1.0, 0.0]]
    got = mod.nearest(E, vocab, "a", 2)
    assert [w for w, _ in got] == ["b", "c"], f"nearest('a', 2) should be b (cosine 0.994) then c (0); got {got}"
    assert close(got[0][1], 0.9 / math.sqrt(0.82), 1e-9), f"the similarity returned alongside 'b' should be its cosine 0.9939; got {got[0][1]}"
    assert "a" not in [w for w, _ in mod.nearest(E, vocab, "a", 3)], "a word is not its own neighbour"
    assert len(mod.nearest(E, vocab, "d", 3)) == 3, "nearest(..., k=3) returns three neighbours"

    # a:b :: c:? where c is close to a, so b - a + c stays close to b. The right answer is d.
    vocab = ["a", "b", "c", "d", "e"]
    E = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [1.0, 0.1, 0.0], [0.0, 0.9, 0.4], [-1.0, 0.0, 0.0]]
    assert mod.analogy(E, vocab, "a", "b", "c") == ["d"], f"with the query words excluded the answer is d; got {mod.analogy(E, vocab, 'a', 'b', 'c')}"
    assert mod.analogy(E, vocab, "a", "b", "c", exclude=False) == ["b"], \
        "with exclude=False the nearest word to b - a + c is b itself (the offset is small): the classic trap of early analogy papers"
    top2 = mod.analogy(E, vocab, "a", "b", "c", k=2)
    assert len(top2) == 2 and top2[0] == "d", f"k=2 returns the two best answers, best first; got {top2}"
    quads = [("a", "b", "c", "d"), ("a", "b", "e", "d")]
    acc = mod.analogy_accuracy(E, vocab, quads)
    assert close(acc, mod.analogy_accuracy(E, vocab, quads[:1]) / 2 + mod.analogy_accuracy(E, vocab, quads[1:]) / 2) and 0 <= acc <= 1, "analogy_accuracy is the fraction of questions answered correctly"
    assert close(mod.analogy_accuracy(E, vocab, quads[:1]), 1.0) and close(mod.analogy_accuracy(E, vocab, quads[:1], exclude=False), 0.0), \
        "the first question is answered correctly with exclusion and wrongly without it"

    # Scenario: vectors trained by the reference solution (saved in vectors.json).
    with open(os.path.join(HERE, "vectors.json")) as fh:
        data = json.load(fh)
    vocab, E = data["vocab"], data["vectors"]
    for w in ("cat", "dog", "horse"):
        near = [x for x, _ in mod.nearest(E, vocab, w, 4)]
        assert sum(x in mod.ANIMALS for x in near) >= 3, f"at least three of the four neighbours of '{w}' should be animals; got {near}"
    near = [x for x, _ in mod.nearest(E, vocab, "bread", 4)]
    assert all(x in mod.FOODS for x in near), f"the neighbours of 'bread' should all be foods; got {near}"
    plural = mod.relation_questions([(x, x + "s") for x in mod.ANIMALS])
    acc_plural = mod.analogy_accuracy(E, vocab, plural)
    assert acc_plural >= 0.9, f"the singular-to-plural relation is clean in this corpus; top-1 accuracy should be at least 90%; got {acc_plural:.0%} on {len(plural)} questions"
    gender = mod.relation_questions([("man", "woman"), ("king", "queen"), ("boy", "girl"), ("prince", "princess")])
    female = {"woman", "queen", "girl", "princess"}
    in_class = sum(mod.analogy(E, vocab, *q[:3])[0] in female for q in gender) / len(gender)
    acc_g, acc_g_open = mod.analogy_accuracy(E, vocab, gender), mod.analogy_accuracy(E, vocab, gender, exclude=False)
    echo = sum(mod.analogy(E, vocab, *q[:3], exclude=False)[0] in q[:3] for q in gender) / len(gender)
    assert in_class >= 0.75, f"the man-to-woman direction should land on a female word for most questions; got {in_class:.0%}"
    assert acc_g_open <= acc_g and echo >= 0.5, (f"without exclusion most 'answers' are just one of the query words (got {echo:.0%}); "
                                                 f"check the exclude flag in analogy()")
    return (f"nearest neighbours: animals near animals, foods near foods\n"
            f"plural analogies: {acc_plural:.0%} top-1 on {len(plural)} questions\n"
            f"gender analogies: {acc_g:.0%} top-1 ({in_class:.0%} land on a female word); with the query words allowed, {echo:.0%} of answers just repeat one of them")


check(1, "Milestone 1: tokens, vocabulary and (centre, context) pairs", m1)
check(2, "Milestone 2: negative sampling", m2)
check(3, "Milestone 3: the SGNS loss and its gradient", m3)
check(4, "Milestone 4: the training loop", m4)
check(5, "Milestone 5: neighbours and analogies", m5)

if ONLY is None or results:
    passed = sum(results)
    print(f"\n{passed}/{len(results)} milestones passing  ({time.time() - T0:.1f} s)")
