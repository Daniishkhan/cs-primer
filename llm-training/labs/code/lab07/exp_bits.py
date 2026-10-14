"""Error against bit width, for per-tensor, per-channel and group-128 scales on the synthetic layer."""
from solution import *

W = make_weights()
print(f"{'bits':>4}{'per-tensor':>12}{'per-channel':>13}{'group 128':>11}   levels")
for bits in (8, 6, 5, 4, 3, 2):
    row = [rel_error(fake_quantise_matrix(W, bits, g, 128), W) for g in ("tensor", "channel", "group")]
    print(f"{bits:>4}" + "".join(f"{e:>{w}.4f}" for e, w in zip(row, (12, 13, 11))) + f"   {2 * qmax(bits) + 1}")
