"""Predict samples per minute for the evolver on one GPU, from first
principles: decoding is limited by memory bandwidth until the batch is big,
then by arithmetic; prefilling the prompt is limited by arithmetic.

    python predict_rate.py --model Qwen/Qwen2.5-Coder-7B-Instruct

Reads config.json and the weight size from Hugging Face (no GPU, no
download of weights). The card defaults are an RTX 4090's published peaks.

Needs: Python 3.9+. No other packages."""
import argparse
import json
import urllib.request

# ── 1. Settings ──────────────────────────────────────────────────────────
ap = argparse.ArgumentParser()
ap.add_argument("--model", default="Qwen/Qwen2.5-Coder-7B-Instruct")
ap.add_argument("--bandwidth", type=float, default=1008)   # GB/s, peak
ap.add_argument("--tflops", type=float, default=165)       # dense bf16, peak
ap.add_argument("--vram", type=float, default=24)          # GiB
ap.add_argument("--bw-eff", type=float, default=0.7)       # assumed
ap.add_argument("--mfu", type=float, default=0.4)          # assumed
ap.add_argument("--tokens-in", type=int, default=224)      # measured, W2
ap.add_argument("--tokens-out", type=int, default=152)     # measured, W2
ap.add_argument("--shared", type=int, default=160)         # cacheable prefix
args, _ = ap.parse_known_args()


def fetch(name):
    url = f"https://huggingface.co/{args.model}/resolve/main/{name}"
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.loads(r.read())


# ── 2. Inputs from the model's own files ─────────────────────────────────
cfg = fetch("config.json")
weights = fetch("model.safetensors.index.json")["metadata"]["total_size"]
L, n_kv = cfg["num_hidden_layers"], cfg["num_key_value_heads"]
d_head = cfg["hidden_size"] // cfg["num_attention_heads"]
params = weights / 2                       # bf16: two bytes per number
kv_token = 2 * L * n_kv * d_head * 2       # chapter 18 of the LLM course
ctx = args.tokens_in + args.tokens_out / 2     # average context while decoding
bw = args.bandwidth * 1e9 * args.bw_eff    # bytes per second we can use
flops = args.tflops * 1e12 * args.mfu      # FLOP per second we can use
print(f"{args.model}: {weights:,} bytes of weights, {params / 1e9:.2f} B "
      f"parameters, KV cache {kv_token:,} bytes per token")
print(f"usable: {bw / 1e9:.0f} GB/s and {flops / 1e12:.0f} TFLOP/s "
      f"({args.bw_eff:.0%} and {args.mfu:.0%} of the peaks)")

# ── 3. Memory: how many requests can be in flight at once? ───────────────
free = args.vram * 2**30 * 0.9 - weights   # keep a 10% margin
fit = int(free // (ctx * kv_token))
print(f"room for the KV cache: {free / 2**30:.1f} GiB = about {fit} "
      f"requests of {ctx:.0f} tokens")

# ── 4. Time per sample = its prefill + its share of the decode steps ─────
print(f"\n{'in flight':>9s} {'step ms':>8s} {'bound by':>9s} "
      f"{'prefill ms':>11s} {'decode ms':>10s} {'samples/min':>12s} "
      f"{'with prefix cache':>18s}")
for b in (1, 4, 16, 64, 256):
    mem_s = (weights + b * ctx * kv_token) / bw     # read weights + caches
    cmp_s = 2 * params * b / flops                  # one token for each
    step, bound = max((mem_s, "memory"), (cmp_s, "compute"))
    decode = args.tokens_out * step / b             # this sample's share
    rates = []
    for new in (args.tokens_in, args.tokens_in - args.shared):
        prefill = 2 * params * new / flops
        rates.append((prefill, 60 / (prefill + decode)))
    print(f"{b:9d} {1000 * step:8.1f} {bound:>9s} "
          f"{1000 * rates[0][0]:11.1f} {1000 * decode:10.1f} "
          f"{rates[0][1]:12.0f} {rates[1][1]:18.0f}")
