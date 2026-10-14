"""Demo for Lab 5: train a tokeniser on corpus.txt, look at it, then decode from a tiny language model.

    python3 demo.py             # uses your starter.py
    python3 demo.py solution    # uses the reference solution
"""
import importlib
import random
import sys

sys.dont_write_bytecode = True
m = importlib.import_module(sys.argv[1] if len(sys.argv) > 1 else "starter")

text = m.load_corpus()
merges = m.train_bpe(text, 200)
vb = m.vocab_bytes(merges)
show = lambda i: vb[i].decode("utf-8", errors="replace")
print(f"corpus: {len(text.encode()):,} bytes; {len(merges)} merges; vocabulary {256 + len(merges)}")
print("first merges:", [(show(a), show(b)) for a, b in list(merges)[:8]])
print("later merges:", [show(n) for n in list(merges.values())[150:158]])

s = "The baker's café opens at 7:30 👍"
ids = m.encode(s, merges)
print(f"\n{len(s.encode())} bytes -> {len(ids)} tokens: {[show(i) for i in ids]}")
print("round trip ok:", m.decode(ids, merges) == s)
print("cut an emoji in half:", repr(m.decode(m.utf8_ids("👍")[:2], {})))

held = "Tomorrow the bakery on the corner will compare 3 prices and taste 12 loaves."
print("\nbytes per token on a sentence the tokeniser has not seen")
for k in (0, 25, 50, 100, 200):
    sub = dict(list(merges.items())[:k])
    print(f"  {k:3d} merges: {len(held.encode()) / len(m.encode(held, sub)):.2f}")

ids = m.encode(text, merges)
lm = m.NGramModel(ids, 256 + len(merges))
prompt = m.encode("The ", merges)
settings = [("greedy", dict(temperature=0)), ("temperature 1.0", dict()), ("temperature 0.7", dict(temperature=0.7)),
            ("top-p 0.9", dict(top_p=0.9)), ("top-k 40, temperature 0.8", dict(top_k=40, temperature=0.8)),
            ("min-p 0.05", dict(min_p=0.05))]
for name, kw in settings:
    out = m.generate(lm, prompt, 40, random.Random(7), **kw)
    print(f"\n--- {name}\n" + m.decode(out, merges).replace("\n", " "))

# how often does each decoder draw a token the model itself considers very unlikely (under 0.1%)?
import math
print("\ntokens drawn that the model gave under 0.1%, out of 600 steps")
for name, kw in settings[1:]:
    rng, n_tail = random.Random(11), 0
    for _ in range(6):
        ctx = list(prompt)
        for _ in range(100):
            logits = lm(ctx)
            t = m.next_token(logits, rng, **kw)
            n_tail += math.exp(logits[t]) < 0.001
            ctx.append(t)
    print(f"  {name:28s} {n_tail:3d}")
