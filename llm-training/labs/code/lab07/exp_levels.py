"""Why one large number costs so much: the same eight weights, with and without one outlier (int4, symmetric)."""
from solution import *

w = [0.02, -0.11, 0.07, 0.31, -0.05, 0.00, 0.13, -0.28]
for name, vals in [("as given", w), ("one weight is 3.1", w[:3] + [3.1] + w[4:])]:
    ints, s = quantise_sym(vals, 4)
    back = dequantise_sym(ints, s)
    print(f"{name:<18} scale {s:.4f}  ints {ints}")
    print(f"{'':<18} error per weight {[round(abs(a - b), 3) for a, b in zip(back, vals)]}")
