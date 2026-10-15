# Drill: A2 Lab 2, milestone 3 of 5: the loss and its gradient for one pair (step 3 of 3)
# Everything else in this file is already written. Fill in:
#     sgns_grads
# Check it with: python3 check.py 3

"""Lab 2 reference solution: skip-gram with negative sampling (SGNS) in plain Python.

Notation follows Deep Learning chapter 06: each word has an input vector v (used when it is the
centre word, and the one we keep) and an output vector u (used when it is a context word).
A pair is scored by the dot product v . u and turned into a probability by the sigmoid.
"""
import bisect
import math
import random
import re
from itertools import accumulate


# ----------------------------------------------------------------------------------------
# Given scaffolding (identical in starter.py)
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
    """Split text into sentences (on . ! ?) and each sentence into lowercase words."""
    sentences = []
    for chunk in re.split(r"[.!?]+", text):
        words = re.findall(r"[a-z']+", chunk.lower())
        if words:
            sentences.append(words)
    return sentences


def build_vocab(sentences, min_count=1):
    """Return (vocab, counts): words seen at least min_count times, most frequent first.

    Ties are broken alphabetically, so the order is deterministic. counts[i] is the count of vocab[i].
    """
    freq = {}
    for s in sentences:
        for w in s:
            freq[w] = freq.get(w, 0) + 1
    vocab = sorted((w for w in freq if freq[w] >= min_count), key=lambda w: (-freq[w], w))
    return vocab, [freq[w] for w in vocab]


def make_pairs(sentences, index, window):
    """All (centre_id, context_id) pairs with the context within `window` words of the centre.

    Words not in `index` are dropped first, so the window closes over the gap (as word2vec does).
    A word is never paired with itself at the same position; windows do not cross sentences.
    """
    pairs = []
    for s in sentences:
        ids = [index[w] for w in s if w in index]
        for i, centre in enumerate(ids):
            for j in range(max(0, i - window), min(len(ids), i + window + 1)):
                if j != i:
                    pairs.append((centre, ids[j]))
    return pairs


# ----------------------------------------------------------------------------------------
# Milestone 2: negative sampling
# ----------------------------------------------------------------------------------------
def noise_distribution(counts, power=0.75):
    """Probabilities proportional to count ** power (Mikolov et al. use 3/4)."""
    w = [c ** power for c in counts]
    total = sum(w)
    return [x / total for x in w]


def sample_negatives(cum, k, avoid, rng):
    """Draw k word ids from the distribution whose running totals are `cum`, never returning `avoid`.

    Draw u = rng.random() * cum[-1] and take the first id whose running total exceeds u (bisect);
    if it equals `avoid`, draw again.
    """
    out = []
    while len(out) < k:
        n = bisect.bisect_right(cum, rng.random() * cum[-1])
        if n != avoid:
            out.append(n)
    return out


# ----------------------------------------------------------------------------------------
# Milestone 3: the loss and its gradient for one pair
# ----------------------------------------------------------------------------------------
def sigmoid(x):
    """1 / (1 + e^-x), safe for any x (no OverflowError for large negative x)."""
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    e = math.exp(x)
    return e / (1.0 + e)


def sgns_loss(v, u_pos, u_negs):
    """-ln sigmoid(v . u_pos) - sum over negatives of ln sigmoid(-v . u_n)."""
    loss = -math.log(sigmoid(dot(v, u_pos)))
    for u in u_negs:
        loss -= math.log(sigmoid(-dot(v, u)))
    return loss


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
    """Train SGNS by stochastic gradient descent, one pair at a time.

    Returns (W_in, W_out, losses): W_in and W_out are (vocab_size, dim); losses[e] is the mean
    loss per pair in epoch e. Initialisation: W_in uniform in [-0.5/dim, 0.5/dim], W_out zeros.
    """
    rng = random.Random(seed)
    W_in = [[rng.uniform(-0.5 / dim, 0.5 / dim) for _ in range(dim)] for _ in range(vocab_size)]
    W_out = [[0.0] * dim for _ in range(vocab_size)]
    cum = cumulative(noise_distribution(counts))
    order = list(pairs)
    losses = []
    for _ in range(epochs):
        rng.shuffle(order)
        total = 0.0
        for w, c in order:
            negs = sample_negatives(cum, negatives, c, rng)
            v, u_pos, u_negs = W_in[w], W_out[c], [W_out[n] for n in negs]
            total += sgns_loss(v, u_pos, u_negs)
            gv, gu_pos, gu_negs = sgns_grads(v, u_pos, u_negs)
            for i in range(dim):                      # update after ALL gradients are computed
                v[i] -= lr * gv[i]
                u_pos[i] -= lr * gu_pos[i]
            for n, gu in zip(negs, gu_negs):
                un = W_out[n]
                for i in range(dim):
                    un[i] -= lr * gu[i]
        losses.append(total / len(order))
    return W_in, W_out, losses


# ----------------------------------------------------------------------------------------
# Milestone 5: neighbours and analogies
# ----------------------------------------------------------------------------------------
def cosine(a, b):
    """Cosine similarity of two vectors: dot(a, b) / (|a| |b|)."""
    return dot(a, b) / (math.sqrt(dot(a, a)) * math.sqrt(dot(b, b)))


def nearest(E, vocab, word, k=5):
    """The k words most similar to `word` by cosine, as [(word, similarity), ...], best first.

    The word itself is excluded. Ties break towards the earlier vocabulary entry.
    """
    i = vocab.index(word)
    sims = [(cosine(E[i], E[j]), j) for j in range(len(vocab)) if j != i]
    sims.sort(key=lambda t: (-t[0], t[1]))
    return [(vocab[j], s) for s, j in sims[:k]]


def analogy(E, vocab, a, b, c, k=1, exclude=True):
    """'a is to b as c is to ?': the k words closest (cosine) to vec(b) - vec(a) + vec(c).

    With exclude=True the three query words are not allowed as answers.
    """
    ia, ib, ic = vocab.index(a), vocab.index(b), vocab.index(c)
    target = [y - x + z for x, y, z in zip(E[ia], E[ib], E[ic])]
    banned = {ia, ib, ic} if exclude else set()
    sims = [(cosine(target, E[j]), j) for j in range(len(vocab)) if j not in banned]
    sims.sort(key=lambda t: (-t[0], t[1]))
    return [vocab[j] for _, j in sims[:k]]


def analogy_accuracy(E, vocab, questions, exclude=True):
    """Fraction of (a, b, c, d) questions whose top-1 answer to 'a:b :: c:?' is d."""
    hits = sum(analogy(E, vocab, a, b, c, 1, exclude)[0] == d for a, b, c, d in questions)
    return hits / len(questions)


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
