"""The SmoothQuant migration strength alpha, and the AWQ exponent curve with its calibration-set size."""
from solution import *

W = make_weights()
X, Xc = make_activations(200), make_activations(100)
Y = matmul_nt(X, W)
print("SmoothQuant alpha, int8 weights and activations (activations per tensor):")
for alpha in (0.0, 0.25, 0.5, 0.75, 1.0):
    Xs, Ws = apply_smoothing(X, W, smooth_scales(col_absmax(Xc), col_absmax(W), alpha))
    e = rel_error(matmul_nt(fake_quantise_activations(Xs, 8, "tensor"), fake_quantise_matrix(Ws, 8, "channel")), Y)
    print(f"  alpha {alpha:.2f}: output error {e:.4f}")
print("\nAWQ-style exponent search, int4 group 128; error on 64 held-out tokens:")
for tokens in (2, 8, 64):
    cal = make_activations(300 + tokens, tokens=tokens)
    a, e_cal, errs = search_awq(cal, W)
    e_test = rel_error(matmul_nt(X, awq_effective_weights(W, col_absmean(cal), a)), Y)
    print(f"  {tokens:>2} calibration tokens: best exponent {a:.1f}, calibration error {e_cal:.4f}, held-out error {e_test:.4f}")
