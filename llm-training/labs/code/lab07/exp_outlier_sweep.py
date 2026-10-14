"""Output error of W8A8 as the activation outlier grows: per-tensor, per-token, mixed precision and SmoothQuant."""
from solution import *

W = make_weights()
Wc = fake_quantise_matrix(W, 8, "channel")
cal_w = col_absmax(W)
print(f"{'outlier x':>9}{'per-tensor':>12}{'per-token':>11}{'mixed':>9}{'smooth':>9}")
for f in (1, 5, 20, 40, 100):
    Xc = make_activations(100, factor=f)
    X = make_activations(200, factor=f)
    Y = matmul_nt(X, W)
    e_t = rel_error(matmul_nt(fake_quantise_activations(X, 8, "tensor"), Wc), Y)
    e_k = rel_error(matmul_nt(fake_quantise_activations(X, 8, "token"), Wc), Y)
    outs = find_outlier_channels(col_absmax(Xc))
    e_m = rel_error(mixed_int8_output(X, W, outs), Y)
    Xs, Ws = apply_smoothing(X, W, smooth_scales(col_absmax(Xc), cal_w))
    e_s = rel_error(matmul_nt(fake_quantise_activations(Xs, 8, "tensor"), fake_quantise_matrix(Ws, 8, "channel")), Y)
    print(f"{f:>9}{e_t:>12.4f}{e_k:>11.4f}{e_m:>9.4f}{e_s:>9.4f}   outlier channels found: {outs}")
