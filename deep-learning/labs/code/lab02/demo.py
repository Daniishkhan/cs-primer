"""Train skip-gram with negative sampling on the toy corpus, then explore the vectors.

    python3 demo.py             # uses your starter.py
    python3 demo.py solution    # uses the reference solution
"""
import importlib
import itertools
import sys

sys.dont_write_bytecode = True
w2v = importlib.import_module(sys.argv[1] if len(sys.argv) > 1 else "starter")

sentences = w2v.make_corpus()
vocab, counts = w2v.build_vocab(sentences)
index = {w: i for i, w in enumerate(vocab)}
plural = w2v.relation_questions([(a, a + "s") for a in w2v.ANIMALS])
gender = w2v.relation_questions([("man", "woman"), ("king", "queen"), ("boy", "girl"), ("prince", "princess")])


def fit(window, negatives, epochs=6):
    pairs = w2v.make_pairs(sentences, index, window)
    W_in, _, losses = w2v.train(pairs, len(vocab), counts, negatives=negatives, epochs=epochs)
    return w2v.normalise_rows(W_in), losses, len(pairs)


E, losses, n_pairs = fit(window=2, negatives=5)
print(f"{len(sentences)} sentences, vocabulary {len(vocab)}, {n_pairs} pairs; mean loss per pair by epoch:")
print("  " + " ".join(f"{x:.3f}" for x in losses) + f"   (chance level {6 * 0.6931:.3f})")

print("\nnearest neighbours")
for w in ("cat", "bread", "king", "she"):
    print(f"  {w:6s}", ", ".join(f"{x} {s:.2f}" for x, s in w2v.nearest(E, vocab, w, 4)))

print("\nanalogies: a is to b as c is to ?   (top three answers)")
for q in [("cat", "cats", "dog"), ("bird", "birds", "cow"), ("man", "king", "woman"), ("king", "queen", "boy")]:
    if all(w in vocab for w in q):
        print(f"  {q[0]}:{q[1]} :: {q[2]}:?  ->", ", ".join(w2v.analogy(E, vocab, *q, k=3)))
for name, qs in (("plural", plural), ("gender", gender)):
    print(f"  {name:6s} top-1 accuracy {w2v.analogy_accuracy(E, vocab, qs):4.0%} over {len(qs)} questions;"
          f" with the query words allowed as answers {w2v.analogy_accuracy(E, vocab, qs, exclude=False):4.0%}")

print("\nwindow and number of negatives (4 epochs each)")
print("  window  negatives  animal-animal  animal-food  plural top-1")
for window, k in itertools.product((1, 2, 4), (1, 5)):
    E2, _, _ = fit(window, k, epochs=4)
    cos = lambda a, b: w2v.cosine(E2[vocab.index(a)], E2[vocab.index(b)])
    within = sum(cos(a, b) for a, b in itertools.combinations(w2v.ANIMALS, 2)) / 15
    between = sum(cos(a, f) for a in w2v.ANIMALS for f in w2v.FOODS) / 36
    print(f"  {window:6d}  {k:9d}  {within:13.2f}  {between:11.2f}  {w2v.analogy_accuracy(E2, vocab, plural):11.0%}")
