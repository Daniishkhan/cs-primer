"""Plan a vLLM deployment on paper: how many conversations fit, and where
the latency knee should be (chapter 18's cache formula, chapter 20's
settings). Reads the model's real config.json and weight size; no GPU.

    python plan.py
    python plan.py --model Qwen/Qwen2.5-7B-Instruct --prompt 440 --out 256

Needs: network access to huggingface.co (two small JSON files)."""
import argparse
import json
import math
import urllib.request

# ── 1. Settings ──────────────────────────────────────────────────────────
ap = argparse.ArgumentParser()
ap.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
ap.add_argument("--gpu-gib", type=float, default=24)    # card memory
ap.add_argument("--util", type=float, default=0.90)     # vLLM's share
ap.add_argument("--overhead-gib", type=float, default=1.5)  # ASSUMED
ap.add_argument("--bw", type=float, default=1008)       # GB/s (RTX 4090)
ap.add_argument("--tflops", type=float, default=165)    # bf16 dense
ap.add_argument("--prompt", type=int, default=440)      # tokens in
ap.add_argument("--out", type=int, default=256)         # tokens out
ap.add_argument("--max-seqs", type=int, default=256)    # --max-num-seqs
ap.add_argument("--block", type=int, default=16)        # tokens per block
ap.add_argument("--kv-bytes", type=int, default=2)      # 1 = fp8 cache
args, _ = ap.parse_known_args()        # notebooks pass their own flags
GIB = 2 ** 30


def fetch(name):
    url = f"https://huggingface.co/{args.model}/raw/main/{name}"
    return json.load(urllib.request.urlopen(url))


# ── 2. The real numbers: config.json and the weight size ─────────────────
cfg = fetch("config.json")
L, n_kv = cfg["num_hidden_layers"], cfg["num_key_value_heads"]
d_head = cfg["hidden_size"] // cfg["num_attention_heads"]
weights = fetch("model.safetensors.index.json")["metadata"]["total_size"]
b = args.kv_bytes                       # bytes per cached number
per_token = 2 * L * n_kv * d_head * b   # chapter 18, eq-kv-bytes
print(f"{args.model}: L={L}, n_kv={n_kv}, d_head={d_head}, b={b}")
print(f"cache per token: 2 x {L} x {n_kv} x {d_head} x {b} = "
      f"{per_token:,} bytes ({per_token / 1024:.0f} KiB)")
print(f"weights: {weights:,} bytes = {weights / GIB:.2f} GiB")

# ── 3. How many sequences fit in the cache pool? ─────────────────────────
budget = args.util * args.gpu_gib * GIB
pool = budget - weights - args.overhead_gib * GIB
block_bytes = args.block * per_token
blocks = int(pool // block_bytes)
seq_tokens = args.prompt + args.out
seq_blocks = math.ceil(seq_tokens / args.block)
fit = blocks // seq_blocks
print(f"\nbudget {args.util:.2f} x {args.gpu_gib:g} GiB = "
      f"{budget / GIB:.2f} GiB; minus weights, minus "
      f"{args.overhead_gib:g} GiB assumed overhead")
print(f"cache pool: {pool / GIB:.2f} GiB = {blocks:,} blocks of "
      f"{args.block} tokens ({blocks * args.block:,} tokens)")
print(f"one conversation ({args.prompt} in + {args.out} out = "
      f"{seq_tokens} tokens): {seq_blocks} blocks")
print(f"sequences that fit: {blocks:,} / {seq_blocks} = {fit}  "
      f"(--max-num-seqs is {args.max_seqs})")
cap = min(fit, args.max_seqs)

# ── 4. Step time and throughput: read the weights, read the caches ───────
params = weights / 2                    # bf16 weights: 2 bytes each
ctx = args.prompt + args.out / 2        # average context during decode


def step_ms(n):
    memory = (weights + n * ctx * per_token) / (args.bw * 1e9)
    compute = 2 * params * n / (args.tflops * 1e12)
    return 1000 * max(memory, compute)


prefill = 1000 * 2 * params * args.prompt / (args.tflops * 1e12)
print(f"\nprefill floor for {args.prompt} tokens at peak compute: "
      f"{prefill:.0f} ms  (a real engine is slower)")
print("concurrent  step (ms)   tokens/s ceiling   note")
for n in (1, 2, 4, 8, 16, 32, 64, 128, 192, 256):
    run = min(n, cap)
    ms = step_ms(run)
    note = "" if n <= cap else "queueing: only %d run at once" % cap
    print(f"{n:>10} {ms:>10.1f} {run / ms * 1000:>18,.0f}   {note}")
