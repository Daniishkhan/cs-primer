"""Lab 2 starter: skip-gram with negative sampling (SGNS) in plain Python.

Notation follows Deep Learning chapter 06: each word has an input vector v (used when it is the
centre word, and the one we keep) and an output vector u (used when it is a context word).
A pair is scored by the dot product v . u and turned into a probability by the sigmoid.

Replace every `raise NotImplementedError(...)` with working code, one milestone at a time,
and run `python3 check.py` after each.
"""
import bisect
import math
import random
import re
from itertools import accumulate


# ----------------------------------------------------------------------------------------
# Given scaffolding: do not change
# ----------------------------------------------------------------------------------------
ANIMALS = {"cat": "purring", "dog": "barking", "horse": "galloping", "cow": "grazing", "bird": "singing", "rabbit": "hopping"}
FOODS = ["bread", "cheese", "apple", "rice", "soup", "cake"]
# word: (pronoun, item 1, item 2). A pair such as king / queen shares its items and differs in the pronoun.
PEOPLE = {
    "king": ("he", "crown", "throne"), "queen": ("she", "crown", "throne"),
    "man": ("he", "farm", "market"), "woman": ("she", "farm", "market"),
    "boy": ("he", "school", "toys"), "girl": ("she", "school", "toys"),
    "prince": ("he", "palace", "tutor"), "princess": ("she", "palace", "tutor"),
}


def make_corpus(seed=7, n=3000):
    """A toy language of n sentences (lists of words): animals, foods, people.

    Animals appear in singular and plural ("the purring cat eats bread", "the purring cats eat bread"),
    so cat -> cats is a relation the corpus makes consistent. People come in gendered pairs
    (king/queen) that share their items and differ in the pronoun (he/she).
    """
    rng = random.Random(seed)
    out = []
    for _ in range(n):
        kind = rng.randrange(4)
        if kind == 0:
            a, a2, f = rng.choice(list(ANIMALS)), rng.choice(list(ANIMALS)), rng.choice(FOODS)
            adj = ANIMALS[a]
            if rng.random() < 0.5:
                s = rng.choice([f"the {adj} {a} eats {f}", f"the {a} chases the {a2}", f"the {adj} {a} sleeps", f"the {a} runs"])
            else:
                s = rng.choice([f"the {adj} {a}s eat {f}", f"the {a}s chase the {a2}s", f"the {adj} {a}s sleep", f"the {a}s run"])
        elif kind == 1:
            f, f2 = rng.choice(FOODS), rng.choice(FOODS)
            s = rng.choice([f"we cook {f} with {f2}", f"we buy {f} and {f2}"])
        else:
            w = rng.choice(list(PEOPLE))
            pr, i1, i2 = PEOPLE[w]
            it = rng.choice([i1, i2])
            s = rng.choice([f"the {w} said {pr} has the {it}", f"{pr} is the {w} with the {it}", f"the {w} lost {pr} {it}"])
        out.append(s.split())
    return out


def dot(a, b):
    """Dot product of two equal-length vectors."""
    return sum(x * y for x, y in zip(a, b))


def cumulative(probs):
    """Running totals of a list of probabilities: [0.5, 0.3, 0.2] -> [0.5, 0.8, 1.0]."""
    return list(accumulate(probs))


def relation_questions(pairs):
    """Every ordered choice of two different pairs gives a question: (a, b, c, d) for a:b :: c:d."""
    return [(a, b, c, d) for a, b in pairs for c, d in pairs if (a, b) != (c, d)]


def normalise_rows(M):
    """Scale every row of M to length 1, so that a dot product is a cosine similarity."""
    out = []
    for row in M:
        n = math.sqrt(sum(x * x for x in row)) or 1.0
        out.append([x / n for x in row])
    return out


# ----------------------------------------------------------------------------------------
# Milestone 1: from text to (centre, context) pairs
# ----------------------------------------------------------------------------------------
def tokenise(text):
    """Split text into sentences (on . ! ?) and each sentence into lowercase words.

    tokenise("The cat sat. The dog sat!") == [["the", "cat", "sat"], ["the", "dog", "sat"]]
    A word is a run of letters and apostrophes (so "don't" is one word); other characters
    separate words. Sentences with no words are skipped. Hint: re.split and re.findall.
    """
    raise NotImplementedError("TODO milestone 1: tokenise")


def build_vocab(sentences, min_count=1):
    """Return (vocab, counts): words seen at least min_count times, most frequent first.

    Ties are broken alphabetically, so the order is deterministic. counts[i] is the count of vocab[i].
    build_vocab([["a", "b", "a"], ["b", "a", "c"]]) == (["a", "b", "c"], [3, 2, 1])
    """
    raise NotImplementedError("TODO milestone 1: build_vocab")


def make_pairs(sentences, index, window):
    """All (centre_id, context_id) pairs with the context within `window` words of the centre.

    `index` maps a word to its id. Words not in `index` are dropped first, so the window closes
    over the gap (as word2vec does). Windows do not cross sentence boundaries.
    With window=1, ["a", "b", "c"] gives (a,b), (b,a), (b,c), (c,b) as ids. Pairs may come in any order.
    """
    raise NotImplementedError("TODO milestone 1: make_pairs")


# ----------------------------------------------------------------------------------------
# Milestone 2: negative sampling
# ----------------------------------------------------------------------------------------
def noise_distribution(counts, power=0.75):
    """Probabilities proportional to count ** power (Mikolov et al. use 3/4), summing to 1.

    noise_distribution([8, 1]) is about [0.826, 0.174]: the rare word is boosted relative to [0.889, 0.111].
    """
    raise NotImplementedError("TODO milestone 2: noise_distribution")


def sample_negatives(cum, k, avoid, rng):
    """Draw k word ids from the distribution whose running totals are `cum`, never returning `avoid`.

    `cum` comes from cumulative(noise_distribution(counts)). Draw u = rng.random() * cum[-1],
    find the first id whose running total exceeds u (bisect_right does this in O(log V)),
    and if that id equals `avoid` (the true context word) draw again. Use only the rng you are given.
    """
    raise NotImplementedError("TODO milestone 2: sample_negatives")


# ----------------------------------------------------------------------------------------
# Milestone 3: the loss and its gradient for one pair
# ----------------------------------------------------------------------------------------
def sigmoid(x):
    """1 / (1 + e^-x), safe for any x: sigmoid(-800) must not raise OverflowError.

    Hint: for x >= 0 use 1 / (1 + exp(-x)); for x < 0 use exp(x) / (1 + exp(x)).
    """
    raise NotImplementedError("TODO milestone 3: sigmoid")


def sgns_loss(v, u_pos, u_negs):
    """The loss for one centre word: -ln sigmoid(v . u_pos) - sum over negatives of ln sigmoid(-v . u_n).

    v is the centre word's input vector, u_pos the true context's output vector, u_negs a list of
    noise words' output vectors. With all-zero vectors and two negatives the loss is 3 ln 2.
    """
    raise NotImplementedError("TODO milestone 3: sgns_loss")


def sgns_grads(v, u_pos, u_negs):
    """Gradients of sgns_loss: returns (grad_v, grad_u_pos, grad_u_negs).

    With s = v . u, d loss / d s is sigmoid(s) - 1 for the true pair and sigmoid(s) for each noise pair.
    Then grad_u = (d loss / d s) * v, and grad_v is the sum of (d loss / d s) * u over all pairs.
    grad_u_negs is a list of vectors, one per negative. Do not modify the inputs.
    """
    raise NotImplementedError("TODO milestone 3: sgns_grads")


# ----------------------------------------------------------------------------------------
# Milestone 4: the training loop
# ----------------------------------------------------------------------------------------
def train(pairs, vocab_size, counts, dim=16, negatives=5, lr=0.05, epochs=6, seed=0):
    """Train SGNS by stochastic gradient descent, one (centre, context) pair at a time.

    rng = random.Random(seed). Initialise W_in uniform in [-0.5/dim, 0.5/dim] and W_out to zeros,
    both (vocab_size, dim). Each epoch: shuffle a COPY of pairs with rng, then for each (w, c):
    sample `negatives` ids with sample_negatives (avoiding c), compute the loss and gradients for
    v = W_in[w], u_pos = W_out[c], u_negs = [W_out[n] ...], and subtract lr * gradient from each row.
    Compute all gradients before changing any vector.

    Returns (W_in, W_out, losses) where losses[e] is the mean loss per pair in epoch e.
    """
    raise NotImplementedError("TODO milestone 4: train")


# ----------------------------------------------------------------------------------------
# Milestone 5: neighbours and analogies
# ----------------------------------------------------------------------------------------
def cosine(a, b):
    """Cosine similarity of two vectors: dot(a, b) / (|a| |b|)."""
    raise NotImplementedError("TODO milestone 5: cosine")


def nearest(E, vocab, word, k=5):
    """The k words most similar to `word` by cosine, as [(word, similarity), ...], best first.

    E holds one row per vocabulary word; the word itself is not returned. Ties go to the
    earlier vocabulary entry.
    """
    raise NotImplementedError("TODO milestone 5: nearest")


def analogy(E, vocab, a, b, c, k=1, exclude=True):
    """'a is to b as c is to ?': the k words closest (by cosine) to vec(b) - vec(a) + vec(c).

    Returns a list of k words, best first. With exclude=True the three query words a, b and c
    may not be returned; with exclude=False they may (and often are: try it).
    """
    raise NotImplementedError("TODO milestone 5: analogy")


def analogy_accuracy(E, vocab, questions, exclude=True):
    """Fraction of (a, b, c, d) questions whose top-1 answer to 'a:b :: c:?' is d."""
    raise NotImplementedError("TODO milestone 5: analogy_accuracy")


if __name__ == "__main__":
    sentences = make_corpus()
    vocab, counts = build_vocab(sentences)
    index = {w: i for i, w in enumerate(vocab)}
    pairs = make_pairs(sentences, index, window=2)
    print(f"{len(sentences)} sentences, vocabulary {len(vocab)}, {len(pairs)} (centre, context) pairs")
    W_in, _, losses = train(pairs, len(vocab), counts)
    print("mean loss per pair:", " ".join(f"{x:.3f}" for x in losses))
    E = normalise_rows(W_in)
    for w in ("cat", "bread", "king"):
        print(f"{w:6s}", ", ".join(f"{x} {s:.2f}" for x, s in nearest(E, vocab, w, 4)))
    plural = relation_questions([(a, a + "s") for a in ANIMALS])
    print(f"plural analogies, top-1: {analogy_accuracy(E, vocab, plural):.0%}  (query words allowed as answers: {analogy_accuracy(E, vocab, plural, False):.0%})")
