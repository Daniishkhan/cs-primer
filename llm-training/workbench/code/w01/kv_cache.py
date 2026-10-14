"""The KV cache, measured: predict its size from chapter 18's formula, then
read the real tensors out of a real model and compare.

Laptop (SmolLM2-135M, on CPU or Apple's MPS):
    python kv_cache.py
GPU box (a 7B model, then batch up to the memory limit):
    python kv_cache.py --model Qwen/Qwen2.5-7B-Instruct --sweep

Needs: torch, transformers (workbench/requirements.txt)."""
import argparse
import time

import torch
from transformers import AutoConfig, AutoModelForCausalLM

# ── 1. Settings ──────────────────────────────────────────────────────────
ap = argparse.ArgumentParser()
ap.add_argument("--model", default="HuggingFaceTB/SmolLM2-135M")
ap.add_argument("--tokens", type=int, default=512)    # prompt length
ap.add_argument("--new", type=int, default=32)        # tokens to decode
ap.add_argument("--sweep", action="store_true")       # GPU: batch until OOM
args, _ = ap.parse_known_args()        # notebooks pass their own flags

if torch.cuda.is_available():
    DEVICE, DTYPE = "cuda", torch.bfloat16
elif torch.backends.mps.is_available():
    DEVICE, DTYPE = "mps", torch.float16
else:
    DEVICE, DTYPE = "cpu", torch.float32
BYTES = torch.tensor([], dtype=DTYPE).element_size()   # bytes per number


def mib(n):
    return f"{n / 2**20:,.2f} MiB"


# ── 2. Predict from the config alone (chapter 18) ────────────────────────
cfg = AutoConfig.from_pretrained(args.model)
L = cfg.num_hidden_layers
n_kv = getattr(cfg, "num_key_value_heads", None) or cfg.num_attention_heads
d_head = (getattr(cfg, "head_dim", None)
          or cfg.hidden_size // cfg.num_attention_heads)
per_token = 2 * L * n_kv * d_head * BYTES          # K and V, every layer
print(f"model {args.model} on {DEVICE} in {DTYPE}")
print(f"L={L} layers, n_kv={n_kv} of {cfg.num_attention_heads} heads, "
      f"d_head={d_head}, b={BYTES} bytes")
print(f"predicted: {per_token:,} bytes per token; "
      f"{mib(per_token * args.tokens)} for {args.tokens} tokens")

# ── 3. Measure: run the prompt once and read the cache tensors ───────────
model = AutoModelForCausalLM.from_pretrained(args.model, dtype=DTYPE)
model = model.to(DEVICE).eval()
torch.manual_seed(0)
ids = torch.randint(0, cfg.vocab_size, (1, args.tokens), device=DEVICE)
with torch.no_grad():
    out = model(ids, use_cache=True)


def cache_bytes(cache):
    """Sum the bytes of every key and value tensor the model kept."""
    total = 0
    for layer in cache.layers:              # transformers' DynamicCache
        total += layer.keys.numel() * layer.keys.element_size()
        total += layer.values.numel() * layer.values.element_size()
    return total


measured = cache_bytes(out.past_key_values)
ratio = measured / (per_token * args.tokens)
print(f"measured:  {mib(measured)} in {len(out.past_key_values.layers)} "
      f"layers  (measured / predicted = {ratio:.3f})")

# ── 4. Why it exists: decode with the cache vs recomputing everything ────


def sync():
    if DEVICE == "cuda":
        torch.cuda.synchronize()
    elif DEVICE == "mps":
        torch.mps.synchronize()


def decode(use_cache):
    seq = ids
    past = None
    sync()
    start = time.perf_counter()
    with torch.no_grad():
        for _ in range(args.new):
            step_in = seq[:, -1:] if past is not None else seq
            o = model(step_in, past_key_values=past, use_cache=use_cache)
            past = o.past_key_values if use_cache else None
            nxt = o.logits[:, -1].argmax(-1, keepdim=True)
            seq = torch.cat([seq, nxt], dim=1)
    sync()
    return (time.perf_counter() - start) / args.new * 1000


with_cache = decode(True)
without = decode(False)
print(f"decode {args.new} tokens after a {args.tokens}-token prompt: "
      f"{with_cache:.1f} ms/token with the cache, {without:.1f} without "
      f"({without / with_cache:.1f}x)")

# ── 5. GPU only: how many conversations fit? Predict, then find out ──────
if args.sweep and DEVICE == "cuda":
    free, total = torch.cuda.mem_get_info()
    print(f"\nGPU: {torch.cuda.get_device_name(0)}, {mib(free)} free "
          f"of {mib(total)} with the weights loaded")
    predicted_batch = int(free * 0.9 // (per_token * args.tokens))
    print(f"predicted max batch at {args.tokens} tokens: about "
          f"{predicted_batch} (90% of free memory / cache per sequence)")
    batch = 1
    while True:
        try:
            torch.cuda.reset_peak_memory_stats()
            x = torch.randint(0, cfg.vocab_size, (batch, args.tokens),
                              device=DEVICE)
            with torch.no_grad():                # keep only the last
                model(x, use_cache=True, logits_to_keep=1)   # logits row
            peak = torch.cuda.max_memory_allocated()
            print(f"  batch {batch:4d}: peak {mib(peak)}")
            batch *= 2
        except torch.OutOfMemoryError:
            print(f"  batch {batch:4d}: out of memory")
            break
        finally:
            torch.cuda.empty_cache()
