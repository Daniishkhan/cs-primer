"""Train a character GPT in PyTorch, predicting parameters and FLOPs first.

Chapter 12's model on Tiny Shakespeare, with chapter 16's rule C = 6ND. The
script predicts the parameter count and the training FLOPs, trains, then
turns the measured tokens per second into an achieved FLOP/s.

Laptop (the chapter's 108,352-weight model, 3,000 steps):
    python char_gpt.py
GPU box (nanoGPT's 10.8M-weight Shakespeare model; give your card's
datasheet peak to get the utilisation):
    python char_gpt.py --size nano --steps 5000 --batch 64 --peak-tflops 312

Needs: torch (workbench/requirements.txt). Downloads 1.1 MB of text once."""
import argparse
import math
import os
import time
import urllib.request

import torch
import torch.nn as nn
import torch.nn.functional as F

# ── 1. Settings ──────────────────────────────────────────────────────────
ap = argparse.ArgumentParser()
ap.add_argument("--size", default="toy", choices=["toy", "nano"])
ap.add_argument("--steps", type=int, default=3000)
ap.add_argument("--batch", type=int, default=32)
ap.add_argument("--peak-tflops", type=float, default=0.0)  # optional
ap.add_argument("--seed", type=int, default=1337)
ap.add_argument("--device", default="auto")      # auto: CUDA, MPS, CPU
args, _ = ap.parse_known_args()        # notebooks pass their own flags

SIZES = {                              # vocab V is read from the data
    "toy": dict(T=64, C=64, h=4, L=2),         # chapter 12
    "nano": dict(T=256, C=384, h=6, L=6),      # nanoGPT shakespeare-char
}
cfg = SIZES[args.size]
T, C, H, L = cfg["T"], cfg["C"], cfg["h"], cfg["L"]

if args.device != "auto":
    DEVICE = args.device
elif torch.cuda.is_available():
    DEVICE = "cuda"
elif torch.backends.mps.is_available():
    DEVICE = "mps"
else:
    DEVICE = "cpu"
torch.manual_seed(args.seed)


def sync():
    if DEVICE == "cuda":
        torch.cuda.synchronize()
    elif DEVICE == "mps":
        torch.mps.synchronize()


# ── 2. Data: characters to ids, 90% train and 10% validation ─────────────
URL = ("https://raw.githubusercontent.com/karpathy/char-rnn/master/"
       "data/tinyshakespeare/input.txt")
path = os.path.expanduser("~/.cache/zts/tinyshakespeare.txt")
if not os.path.exists(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    urllib.request.urlretrieve(URL, path)
text = open(path, encoding="utf-8").read()
chars = sorted(set(text))
V = len(chars)
stoi = {c: i for i, c in enumerate(chars)}
data = torch.tensor([stoi[c] for c in text])
n_train = int(0.9 * len(data))
train, val = data[:n_train], data[n_train:]
gen = torch.Generator().manual_seed(args.seed)     # batch offsets, on CPU


def get_batch(d, g):
    ix = torch.randint(0, len(d) - T - 1, (args.batch,), generator=g)
    x = torch.stack([d[i:i + T] for i in ix])
    y = torch.stack([d[i + 1:i + T + 1] for i in ix])
    return x.to(DEVICE), y.to(DEVICE)


# ── 3. The model: chapter 12's GPT, with PyTorch doing the backward ──────


class Block(nn.Module):
    def __init__(self):
        super().__init__()
        self.ln1, self.ln2 = nn.LayerNorm(C), nn.LayerNorm(C)
        self.qkv, self.proj = nn.Linear(C, 3 * C), nn.Linear(C, C)
        self.fc1, self.fc2 = nn.Linear(C, 4 * C), nn.Linear(4 * C, C)

    def forward(self, x):
        B, t, _ = x.shape
        q, k, v = self.qkv(self.ln1(x)).split(C, dim=-1)
        q, k, v = [a.view(B, t, H, C // H).transpose(1, 2) for a in (q, k, v)]
        a = F.scaled_dot_product_attention(q, k, v, is_causal=True)
        x = x + self.proj(a.transpose(1, 2).reshape(B, t, C))
        return x + self.fc2(F.gelu(self.fc1(self.ln2(x)), approximate="tanh"))


class GPT(nn.Module):
    def __init__(self):
        super().__init__()
        self.wte, self.wpe = nn.Embedding(V, C), nn.Embedding(T, C)
        self.blocks = nn.ModuleList([Block() for _ in range(L)])
        self.lnf = nn.LayerNorm(C)
        for name, p in self.named_parameters():          # GPT-2 style init
            if p.ndim >= 2:
                std = 0.02 / math.sqrt(2 * L) if name.endswith(
                    ("proj.weight", "fc2.weight")) else 0.02
                nn.init.normal_(p, 0.0, std)

    def forward(self, idx):
        x = self.wte(idx) + self.wpe(torch.arange(idx.shape[1],
                                                  device=idx.device))
        for b in self.blocks:
            x = b(x)
        return self.lnf(x) @ self.wte.weight.T           # tied head


model = GPT().to(DEVICE)

# ── 4. Predict: parameters (chapter 12) and FLOPs (chapter 16) ───────────
N_formula = V * C + T * C + L * (12 * C * C + 13 * C) + 2 * C
N = sum(p.numel() for p in model.parameters())
tokens = args.steps * args.batch * T                     # D
flops_tok = 6 * N                                        # 6N per token
flops_tok_attn = 6 * N + 12 * L * C * T                  # + score products
print(f"device {DEVICE}; size {args.size}: V={V} T={T} C={C} h={H} L={L}")
print(f"parameters: formula {N_formula:,}, counted {N:,}")
print(f"D = {args.steps} steps x {args.batch} x {T} = {tokens:,} tokens")
print(f"C = 6ND = {6 * N * tokens:.3e} FLOPs "
      f"({flops_tok:,} per token; {flops_tok_attn:,} with the 12LCT "
      f"attention term, +{flops_tok_attn / flops_tok - 1:.1%})")

# ── 5. Train: AdamW, warmup, cosine decay, clipping ──────────────────────
decay = [p for p in model.parameters() if p.ndim >= 2]
no_decay = [p for p in model.parameters() if p.ndim < 2]
opt = torch.optim.AdamW(
    [dict(params=decay, weight_decay=0.1),
     dict(params=no_decay, weight_decay=0.0)],
    lr=3e-3, betas=(0.9, 0.99))
warmup, lr_max, lr_min = 100, 3e-3, 3e-4


def lr_at(t):
    if t < warmup:
        return lr_max * (t + 1) / warmup
    r = (t - warmup) / max(1, args.steps - warmup)
    return lr_min + 0.5 * (1 + math.cos(math.pi * r)) * (lr_max - lr_min)


@torch.no_grad()
def estimate(d, k=20):
    g = torch.Generator().manual_seed(0)         # same batches every time
    model.eval()
    out = sum(F.cross_entropy(
        model(x).view(-1, V), y.view(-1)).item()
        for x, y in (get_batch(d, g) for _ in range(k))) / k
    model.train()
    return out


every = max(1, args.steps // 6)
busy = 0.0                                       # seconds spent training
for step in range(args.steps + 1):
    if step % every == 0 or step == args.steps:
        print(f"step {step:5d}  train {estimate(train):.3f}  "
              f"val {estimate(val):.3f}")
    if step == args.steps:
        break
    x, y = get_batch(train, gen)
    for grp in opt.param_groups:
        grp["lr"] = lr_at(step)
    sync()
    t0 = time.perf_counter()
    loss = F.cross_entropy(model(x).view(-1, V), y.view(-1))
    opt.zero_grad(set_to_none=True)
    loss.backward()
    torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
    opt.step()
    sync()
    busy += time.perf_counter() - t0

# ── 6. Measure: tokens per second, achieved FLOP/s ───────────────────────
tok_s = tokens / busy
achieved = tok_s * flops_tok_attn
print(f"\ntrained {tokens:,} tokens in {busy:.1f} s of step time "
      f"(evaluation not counted)")
print(f"measured: {tok_s:,.0f} tokens/s; {busy / args.steps * 1000:.1f} "
      f"ms/step")
print(f"achieved: {tok_s:,.0f} x {flops_tok_attn:,} = "
      f"{achieved / 1e12:.3f} TFLOP/s")
if args.peak_tflops:
    print(f"utilisation: {achieved / (args.peak_tflops * 1e12):.1%} of "
          f"{args.peak_tflops} TFLOP/s")

# ── 7. Sample ────────────────────────────────────────────────────────────
model.eval()
ids = torch.tensor([[stoi[c] for c in "ROMEO:\n"]], device=DEVICE)
g = torch.Generator(device="cpu").manual_seed(0)
with torch.no_grad():
    for _ in range(280):
        probs = F.softmax(model(ids[:, -T:])[0, -1].float().cpu(), -1)
        nxt = torch.multinomial(probs, 1, generator=g).to(DEVICE)
        ids = torch.cat([ids, nxt[None]], dim=1)
print("\n" + "".join(chars[i] for i in ids[0].tolist()))
