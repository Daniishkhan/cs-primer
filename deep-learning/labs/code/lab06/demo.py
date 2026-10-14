"""Demo for Lab 6: a one-page report for each published model, then a serving plan and a size choice.

    python3 demo.py             # uses your starter.py
    python3 demo.py solution    # uses the reference solution
"""
import importlib
import sys

sys.dont_write_bytecode = True
m = importlib.import_module(sys.argv[1] if len(sys.argv) > 1 else "starter")
GB = 1e9
H100 = m.GPUS["H100 SXM"]

print(f"{'model':<15}{'params':>9}{'active':>9}{'train states':>14}{'KV/token':>10}{'bf16 weights':>14}{'tok/s on H100':>15}")
for name, c in m.MODELS.items():
    n, act = m.count_params(c), m.count_params(c, active=True)
    states = m.state_bytes(n) / GB
    kv = m.kv_bytes_per_token(c) / 1024
    tps = m.decode_tokens_per_second(c, 0, 1, H100["bw"], H100["peak"])
    print(f"{name:<15}{n / 1e9:>8.1f}B{act / 1e9:>8.1f}B{states:>11,.0f} GB{kv:>7,.0f} KiB{m.weight_bytes(c) / GB:>11,.1f} GB{tps:>13,.0f}")

c = m.MODELS["Llama 3 8B"]
print("\nLlama 3 8B, training on a single 80 GB card, sequence length 4,096, microbatch 1")
for mode in ("full", "flash", "recompute"):
    t = m.training_memory(c, 4096, 1, mode)
    print(f"  {mode:<10} states {t['states'] / GB:6.1f} GB + activations {t['activations'] / GB:7.1f} GB = {t['total'] / GB:7.1f} GB  fits: {m.fits(t['total'], 80 * GB)}")

print("\nLlama 3 8B decoding on one 80 GB H100 (bf16), 2,048-token contexts")
print("  batch  tokens/s  tokens/s per user")
for b in (1, 8, 64, m.max_batch(c, 2048, 80 * GB)):
    t = m.decode_tokens_per_second(c, 2048, b, H100["bw"], H100["peak"])
    print(f"  {b:5d} {t:9,.0f} {t / b:15.1f}")

print("\nHow big should the model be? Target: the loss the Besiroglu fit gives for Chinchilla (70B, 1.4T tokens)")
fit = m.BESIROGLU
target = m.loss(70e9, 1.4e12, fit)
print(f"  target loss {target:.3f}")
print(f"  {'tokens served':>14}{'params':>10}{'train tokens':>14}{'tokens/param':>14}{'lifetime FLOPs':>16}")
for served in (0, 1e12, 1e13, 1e14, 1e15):
    n, d, f = m.best_size_for_loss(target, served, fit)
    print(f"  {served:>14.0e}{n / 1e9:>9.1f}B{d / 1e12:>12.2f} T{d / n:>14.0f}{f:>16.2e}")
