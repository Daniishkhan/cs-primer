"""Milestone 1 experiment: what fits in the KV cache of a 24 GB card running an 8B model.
Change the import to `starter` to run it on your own code."""
from solution import kv_bytes_per_token, cache_pages, LLAMA3_8B

per_tok = kv_bytes_per_token(**LLAMA3_8B)
pages = cache_pages(24e9, 8.03e9 * 2, 1.5e9, per_tok, 16)
print(f"KV cache per token: {per_tok:,} bytes ({per_tok // 1024} KiB);  pages of 16 tokens in the budget: {pages:,}")
print(f"{'context':>8} {'pages each':>11} {'sequences that fit':>19}")
for ctx in (512, 1024, 2048, 4096, 8192):
    need = -(-ctx // 16)
    print(f"{ctx:8d} {need:11d} {pages // need:19d}")
print("\nbytes per token for other shapes (bf16):")
for name, shape in (("8 KV heads, 32 layers", (32, 8, 128)), ("full multi-head, 32 layers", (32, 32, 128)),
                    ("8 KV heads, 80 layers", (80, 8, 128))):
    print(f"  {name:<28} {kv_bytes_per_token(*shape):>9,}")
