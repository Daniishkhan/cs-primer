"""Demo for Lab 3: run a small GPT forward pass and look at the shapes and the attention maps.

    python3 demo.py             # uses your starter.py
    python3 demo.py solution    # uses the reference solution
"""
import importlib
import math
import random
import sys

sys.dont_write_bytecode = True
m = importlib.import_module(sys.argv[1] if len(sys.argv) > 1 else "starter")

V, C, T_MAX, L, H = 27, 16, 8, 2, 4
P = m.init_model(V, C, T_MAX, L, seed=0)
ids = [0, 8, 5, 12, 12, 15, 0, 0]                         # a short sequence of token ids
trace = []
logits = m.model_forward(ids, P, H, trace)
print(f"B=1, T={len(ids)}, C={C}, h={H}, d_k={C // H}, V={V}, L={L}")
for name, shp in trace:
    print(f"  {name:8s} {shp}")
print(f"parameters: {m.count_params(P):,} counted, {m.model_param_count(V, C, T_MAX, L):,} by formula "
      f"({m.block_param_count(C)} per block)")
loss = m.mean_cross_entropy(logits[:-1], ids[1:])
print(f"loss of the untrained model: {loss:.3f} nats  (ln V = {math.log(V):.3f})")

# attention maps of the first block's first head, with random but non-trivial weights
rng = random.Random(1)
x = [[rng.gauss(0, 1) for _ in range(C)] for _ in range(6)]
W = [[[rng.gauss(0, 1 / math.sqrt(C)) for _ in range(C)] for _ in range(C)] for _ in range(4)]
for causal in (False, True):
    _, weights = m.multi_head_attention(x, *W, H, causal)
    print(f"\nattention weights of head 0, causal={causal} (row = query, column = key)")
    for row in weights[0]:
        print("  " + " ".join(f"{w:5.2f}" for w in row))
