"""Word vectors from real text: skip-gram with negative sampling in PyTorch.

Chapter 6 factorised a count matrix on text8 and described word2vec's
negative-sampling loss. Here that loss trains the vectors directly, on a
slice of text8 (the first 20 million characters, about 3.4 million words;
the full file is 100 million and would take hours on a laptop). The script
predicts the loss at step 0, trains, then asks the same questions chapter
6 asked: nearest neighbours and analogies.

    python word_vectors.py                   # a few minutes on a laptop
    python word_vectors.py --chars 100000000 --epochs 1   # the full text

Needs: torch, numpy (workbench/requirements.txt). Downloads about 0.3 MB
of text8.zip per million characters, once."""
import argparse
import math
import os
import time
import urllib.request
import zlib

import numpy as np
import torch
import torch.nn.functional as F

# ── 1. Settings ──────────────────────────────────────────────────────────
ap = argparse.ArgumentParser()
ap.add_argument("--chars", type=int, default=20_000_000)  # slice of text8
ap.add_argument("--vocab", type=int, default=8000)       # as chapter 6
ap.add_argument("--dim", type=int, default=100)
ap.add_argument("--window", type=int, default=5)
ap.add_argument("--neg", type=int, default=5)            # noise words, k
ap.add_argument("--epochs", type=int, default=8)
ap.add_argument("--batch", type=int, default=4096)
ap.add_argument("--lr", type=float, default=0.001)
ap.add_argument("--sub", type=float, default=1e-4)       # subsampling t
ap.add_argument("--seed", type=int, default=0)
args, _ = ap.parse_known_args()        # notebooks pass their own flags

if torch.cuda.is_available():
    DEVICE = "cuda"
elif torch.backends.mps.is_available():
    DEVICE = "mps"
else:
    DEVICE = "cpu"
torch.manual_seed(args.seed)
rng = np.random.default_rng(args.seed)

# ── 2. Data: stream the first N characters of text8.zip ──────────────────
URL = "https://mattmahoney.net/dc/text8.zip"
path = os.path.expanduser(f"~/.cache/zts/text8-{args.chars}.txt")
if not os.path.exists(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    got = b""
    with urllib.request.urlopen(URL) as resp:
        head = resp.read(30)                    # zip local file header
        n_name = int.from_bytes(head[26:28], "little")
        n_extra = int.from_bytes(head[28:30], "little")
        resp.read(n_name + n_extra)
        raw = zlib.decompressobj(-15)           # the entry is raw deflate
        while len(got) < args.chars:
            chunk = resp.read(1 << 16)
            if not chunk:
                break
            got += raw.decompress(chunk)
    open(path, "w").write(got[:args.chars].decode())
words = open(path).read().split()
vocab, counts = np.unique(words, return_counts=True)
top = np.argsort(-counts, kind="stable")[:args.vocab]
itos = [vocab[i] for i in top]
stoi = {w: i for i, w in enumerate(itos)}
V = len(itos)
ids = np.array([stoi.get(w, -1) for w in words], dtype=np.int64)
ids = ids[ids >= 0]                                     # drop rare words
freq = np.bincount(ids, minlength=V) / len(ids)
print(f"device {DEVICE}; text8 slice: {args.chars:,} characters, "
      f"{len(words):,} words, {len(ids):,} in the {V:,}-word vocabulary")

# ── 3. Predict ───────────────────────────────────────────────────────────
n_params = 2 * V * args.dim                  # input table v and output u
chance = (1 + args.neg) * math.log(2)        # every score 0: sigma = 1/2
keep = np.minimum(1.0, np.sqrt(args.sub / freq) + args.sub / freq)
n_kept = float((freq * len(ids) * keep).sum())      # expected after thinning
pairs_pred = 2 * args.window * n_kept        # 2W pairs per kept word
print(f"predicted: {n_params:,} parameters; loss at step 0 = "
      f"(1+k) ln 2 = {chance:.4f}")
print(f"predicted: {n_kept:,.0f} words kept by subsampling, about "
      f"{pairs_pred:,.0f} pairs per epoch")

# ── 4. Pairs and the noise distribution ──────────────────────────────────


def make_pairs():
    """Subsample frequent words, then pair each with its W neighbours."""
    kept = ids[rng.random(len(ids)) < keep[ids]]
    cen, ctx = [], []
    for d in range(1, args.window + 1):
        cen += [kept[:-d], kept[d:]]
        ctx += [kept[d:], kept[:-d]]
    c = torch.from_numpy(np.concatenate(cen))
    x = torch.from_numpy(np.concatenate(ctx))
    return c, x, len(kept)


noise = torch.tensor(freq ** 0.75, dtype=torch.float32)
noise = (noise / noise.sum()).to(DEVICE)         # unigram^(3/4)

# ── 5. The model and the loss of chapter 6 ───────────────────────────────
v = torch.nn.Embedding(V, args.dim).to(DEVICE)   # input vectors (kept)
u = torch.nn.Embedding(V, args.dim).to(DEVICE)   # output vectors
torch.nn.init.uniform_(v.weight, -0.5 / args.dim, 0.5 / args.dim)
torch.nn.init.zeros_(u.weight)
opt = torch.optim.Adam(list(v.parameters()) + list(u.parameters()),
                       lr=args.lr)


def sgns_loss(w, c):
    """-log s(v.u_c) - sum_i log s(-v.u_ni), averaged over the batch."""
    vw = v(w)
    pos = F.logsigmoid((vw * u(c)).sum(-1))
    n = torch.multinomial(noise, w.numel() * args.neg, replacement=True)
    neg = F.logsigmoid(-torch.einsum(
        "bd,bkd->bk", vw, u(n.view(-1, args.neg))))
    return -(pos + neg.sum(-1)).mean()


# ── 6. Train ─────────────────────────────────────────────────────────────
t0 = time.time()
first = True
for epoch in range(1, args.epochs + 1):
    cen, ctx, n_kept_real = make_pairs()
    if epoch == 1:
        print(f"measured:  {n_kept_real:,} words kept, {len(cen):,} "
              f"pairs per epoch, {len(cen) // args.batch:,} steps")
    perm = torch.randperm(len(cen))
    total, steps = 0.0, 0
    marks = []
    for b in range(0, len(cen) - args.batch + 1, args.batch):
        i = perm[b:b + args.batch]
        w, c = cen[i].to(DEVICE), ctx[i].to(DEVICE)
        loss = sgns_loss(w, c)
        if first:
            print(f"step 0 loss: {loss.item():.4f}   (predicted "
                  f"{chance:.4f})")
            first = False
        opt.zero_grad(set_to_none=True)
        loss.backward()
        opt.step()
        total += loss.item() if steps % 20 == 0 else 0.0
        steps += 1
        if steps % max(1, (len(cen) // args.batch) // 4) == 0:
            marks.append(loss.item())
    n_sampled = len(range(0, steps, 20))
    print(f"epoch {epoch}: mean loss {total / n_sampled:.3f}  "
          f"(quarter-epoch losses "
          + " ".join(f"{m:.2f}" for m in marks[:4])
          + f")  {time.time() - t0:.0f} s")

# ── 7. Evaluate: neighbours, analogies, arrows (as chapter 6) ────────────
E = F.normalize(v.weight.detach().cpu(), dim=1).numpy()


def neighbours(w, k=5):
    if w not in stoi:
        return "(not among this slice's most frequent words)"
    sims = E @ E[stoi[w]]
    return ", ".join(f"{itos[i]} {sims[i]:.2f}"
                     for i in np.argsort(-sims)[1:k + 1])


print("\nnearest neighbours (cosine):")
for w in ["france", "monday", "tiger", "bank", "python", "doctor"]:
    print(f"  {w:8s} {neighbours(w)}")


def ranking(a, b, c):
    q = E[stoi[b]] - E[stoi[a]] + E[stoi[c]]
    return [itos[i] for i in np.argsort(-(E @ q))
            if itos[i] not in (a, b, c)]


RELATIONS = {
    "capital of": [("france", "paris"), ("germany", "berlin"),
                   ("italy", "rome"), ("spain", "madrid"),
                   ("england", "london"), ("japan", "tokyo"),
                   ("russia", "moscow"), ("china", "beijing"),
                   ("greece", "athens"), ("austria", "vienna"),
                   ("poland", "warsaw"), ("portugal", "lisbon"),
                   ("ireland", "dublin"), ("egypt", "cairo")],
    "female form": [("man", "woman"), ("king", "queen"),
                    ("prince", "princess"), ("brother", "sister"),
                    ("son", "daughter"), ("father", "mother"),
                    ("boy", "girl"), ("husband", "wife"),
                    ("uncle", "aunt")],
    "comparative": [("big", "bigger"), ("small", "smaller"),
                    ("large", "larger"), ("high", "higher"),
                    ("low", "lower"), ("long", "longer"),
                    ("short", "shorter"), ("old", "older"),
                    ("young", "younger"), ("fast", "faster")],
}
print("\nanalogies, top-1 over the whole vocabulary, inputs excluded:")
print("  (chapter 6, SVD on 17M words: capital 49%, female 54%, "
      "comparative 43%)")
for name, pairs in RELATIONS.items():
    pairs = [p for p in pairs if p[0] in stoi and p[1] in stoi]
    qs = [(a, b, c, d) for a, b in pairs for c, d in pairs
          if (c, d) != (a, b)]
    hit = np.mean([ranking(a, b, c)[0] == d for a, b, c, d in qs])
    print(f"  {name:12s} {len(pairs):2d} pairs {len(qs):4d} questions "
          f"{hit:5.0%}")
a, b, c, d = "man", "king", "woman", "queen"
r = ranking(a, b, c)
print(f"\n{a}:{b} :: {c}:?  expected {d!r} at rank {r.index(d) + 1}; "
      f"top three {[str(x) for x in r[:3]]}")
caps = [(p, q) for p, q in RELATIONS["capital of"]
        if p in stoi and q in stoi]
off = np.array([E[stoi[q]] - E[stoi[p]] for p, q in caps])
off /= np.linalg.norm(off, axis=1, keepdims=True)
m = off @ off.T
print(f"mean cosine between the {len(caps)} capital-minus-country "
      f"arrows: {(m.sum() - len(caps)) / (len(caps) * (len(caps) - 1)):.2f}"
      f"  (chapter 6: 0.58; random pairs: -0.01)")
