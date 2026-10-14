"""Lab 7: Quantise a Model.

Chapter 19 squeezed weights into 8, 4 and fewer bits and showed that the squeeze is not even:
one large number sets the step size for everything that shares its scale. This lab builds the
whole toolbox on a small synthetic layer and measures the damage at every step.

    floats --> symmetric / asymmetric integers --> per-tensor / per-channel / per-group scales
           --> packed 4-bit bytes --> activation outliers (mixed precision, SmoothQuant)
           --> AWQ-style scale search with calibration data --> a side-by-side report

Shapes follow chapter 19 and A2: X is T x C (T tokens, C input channels), the weight W is stored
output-first as D x C (row d produces output d), and the layer computes Y = X W^T, a T x D matrix.
"Per-channel" means one scale per row of W, that is per output channel. A row of W is a Python
list of floats and a matrix is a list of rows. Standard library only.

What is GIVEN: the synthetic layer (weights with loud rows and spikes, activations with outlier
channels), matmul, rel_error, top1_agreement, flatten, column statistics and the final report.
What YOU write is marked TODO.

    1  qmax, scale_sym, quantise_sym, dequantise_sym
    2  quantise_asym, dequantise_asym
    3  fake_quantise_matrix, n_scales, bits_per_weight
    4  pack_int4, unpack_int4, weight_bytes, sequences_that_fit
    5  fake_quantise_activations, find_outlier_channels, mixed_int8_output, smooth_scales, apply_smoothing
    6  awq_scales, awq_effective_weights, search_awq
"""
import math
import random

# =============================================================================
# GIVEN: numerics and measurement
# =============================================================================
def flatten(M):
    return [v for row in M for v in row]


def rel_error(approx, ref):
    """||approx - ref|| / ||ref|| for two equal-length lists of numbers, or two matrices."""
    if approx and isinstance(approx[0], (list, tuple)):
        approx, ref = flatten(approx), flatten(ref)
    num = sum((a - b) ** 2 for a, b in zip(approx, ref))
    den = sum(b * b for b in ref)
    return math.sqrt(num / den) if den > 0 else math.sqrt(num)


def matmul_nt(X, W):
    """Y = X W^T for X (T x C) and W (D x C): Y[t][d] = sum_c X[t][c] * W[d][c]."""
    return [[sum(x * w for x, w in zip(xr, wr)) for wr in W] for xr in X]


def col_absmax(M):
    """Largest magnitude in each column of a matrix (one number per input channel)."""
    return [max(abs(v) for v in col) for col in zip(*M)]


def col_absmean(M):
    """Mean magnitude in each column of a matrix."""
    n = len(M)
    return [sum(abs(v) for v in col) / n for col in zip(*M)]


def top1_agreement(Yq, Y):
    """Fraction of tokens whose argmax over the D outputs is unchanged: a stand-in for 'same answer'."""
    same = sum(1 for a, b in zip(Yq, Y) if max(range(len(a)), key=a.__getitem__) == max(range(len(b)), key=b.__getitem__))
    return same / len(Y)


# =============================================================================
# GIVEN: Llama 3 shapes from chapter 19 (layers, heads, kv heads, width, ffn width, vocabulary)
# =============================================================================
LLAMA3 = {"8B": (32, 32, 8, 4096, 14336, 128256), "70B": (80, 64, 8, 8192, 28672, 128256)}


def llama_params(name):
    """Parameter count from the shapes (untied embedding and output head), as in chapter 19: 8.03 B and 70.55 B."""
    L, H, KV, D, F, V = LLAMA3[name]
    hd = D // H
    attn = 2 * D * D + 2 * D * KV * hd
    return L * (attn + 3 * D * F + 2 * D) + 2 * V * D + D


# bf16 KV cache of one 8,192-token sequence of the 8B model: 2 (K and V) x 32 layers x 8 kv heads x 128 x 2 bytes x 8192
KV_BYTES_PER_SEQUENCE_8B = 2 * 32 * 8 * 128 * 2 * 8192


# =============================================================================
# GIVEN: the synthetic layer. Sizes are small so that pure Python finishes in seconds.
# =============================================================================
ROWS, COLS, TOKENS = 48, 256, 64          # D, C, T
LOUD_ROWS = {5: 12.0, 30: 20.0}           # output channels whose weights are 12x and 20x larger
SPIKES = [(2, 40, 8.0), (17, 130, 8.0), (41, 200, 8.0), (44, 7, 8.0)]   # single weights 8x larger
OUTLIER_CHANNELS = (11, 201)              # input channels that are huge in the activations
OUTLIER_FACTOR = 40.0


def make_weights(seed=7):
    """D x C weights: N(0, 0.02^2), two loud rows and four spikes (all sizes illustrative)."""
    rng = random.Random(seed)
    W = [[rng.gauss(0.0, 0.02) for _ in range(COLS)] for _ in range(ROWS)]
    for r, f in LOUD_ROWS.items():
        W[r] = [v * f for v in W[r]]
    for r, c, f in SPIKES:
        W[r][c] *= f
    return W


def make_activations(seed, channels=OUTLIER_CHANNELS, factor=OUTLIER_FACTOR, tokens=TOKENS):
    """T x C activations: N(0, 1) with the given input channels multiplied by `factor`."""
    rng = random.Random(seed)
    X = [[rng.gauss(0.0, 1.0) for _ in range(COLS)] for _ in range(tokens)]
    for row in X:
        for c in channels:
            row[c] *= factor
    return X


# =============================================================================
# Milestone 1: symmetric quantisation
# =============================================================================
def qmax(bits):
    """The largest integer of a signed `bits`-bit symmetric grid: 7 for 4 bits, 127 for 8. (The grid is -qmax..qmax.)"""
    return 2 ** (bits - 1) - 1


def scale_sym(values, bits):
    """absmax / qmax(bits). An all-zero list has scale 1.0, so that nothing divides by zero."""
    m = max(abs(v) for v in values)
    return m / qmax(bits) if m > 0 else 1.0


def quantise_sym(values, bits):
    """Return (ints, scale): ints[i] = clamp(round(values[i] / scale), -qmax, +qmax), using Python's round().

    quantise_sym([0.02, -0.11, 0.07, 0.31, -0.05, 0.0, 0.13, -0.28], 4)
        -> ([0, -2, 2, 7, -1, 0, 3, -6], 0.31 / 7)
    """
    s = scale_sym(values, bits)
    q = qmax(bits)
    return [max(-q, min(q, round(v / s))) for v in values], s


def dequantise_sym(ints, scale):
    """ints * scale, as floats."""
    return [q * scale for q in ints]


# =============================================================================
# Milestone 2: asymmetric quantisation (a zero point)
# =============================================================================
def quantise_asym(values, bits):
    """Return (ints, scale, zero_point) on the UNSIGNED grid 0 .. 2**bits - 1.

    lo = min(min(values), 0) and hi = max(max(values), 0), so that real zero is always inside the range;
    scale = (hi - lo) / (2**bits - 1);  zero_point = round(-lo / scale);
    ints[i] = clamp(round(values[i] / scale) + zero_point, 0, 2**bits - 1).
    If hi == lo (all zeros) use scale 1.0 and zero_point 0.

    quantise_asym([-1.0, 0.0, 3.0], 3) -> ([0, 2, 7], 4 / 7, 2)
    """
    top = 2 ** bits - 1
    lo, hi = min(min(values), 0.0), max(max(values), 0.0)
    if hi == lo:
        return [0] * len(values), 1.0, 0
    s = (hi - lo) / top
    z = round(-lo / s)
    return [max(0, min(top, round(v / s) + z)) for v in values], s, z


def dequantise_asym(ints, scale, zero_point):
    """(ints - zero_point) * scale, as floats."""
    return [(q - zero_point) * scale for q in ints]


# =============================================================================
# Milestone 3: granularity, and what the scales cost
# =============================================================================
def fake_quantise_matrix(W, bits, granularity, group=128):
    """Quantise then dequantise a matrix (symmetric), so the result shows what the integers mean.

    granularity "tensor":  one scale for the whole matrix
                "channel": one scale per row
                "group":   one scale per run of `group` consecutive weights within a row
                           (the last run of a row may be shorter)
    Returns a new list of rows of floats. Do not modify W.
    """
    if granularity == "tensor":
        ints, s = quantise_sym(flatten(W), bits)
        flat = dequantise_sym(ints, s)
        c = len(W[0])
        return [flat[i * c:(i + 1) * c] for i in range(len(W))]
    out = []
    for row in W:
        if granularity == "channel":
            ints, s = quantise_sym(row, bits)
            out.append(dequantise_sym(ints, s))
        elif granularity == "group":
            new = []
            for i in range(0, len(row), group):
                ints, s = quantise_sym(row[i:i + group], bits)
                new.extend(dequantise_sym(ints, s))
            out.append(new)
        else:
            raise ValueError(f"unknown granularity {granularity!r}")
    return out


def n_scales(rows, cols, granularity, group=128):
    """How many scale numbers a rows x cols matrix needs: 1, rows, or rows * ceil(cols / group)."""
    if granularity == "tensor":
        return 1
    if granularity == "channel":
        return rows
    if granularity == "group":
        return rows * -(-cols // group)
    raise ValueError(f"unknown granularity {granularity!r}")


def bits_per_weight(bits, rows, cols, granularity, group=128, scale_bits=16):
    """Effective storage per weight: bits + scale_bits * n_scales / (rows * cols).

    bits_per_weight(4, 4096, 4096, "group", 128) -> 4.125   (the '4-bit' model is really 4.125 bits)
    """
    return bits + scale_bits * n_scales(rows, cols, granularity, group) / (rows * cols)


# =============================================================================
# Milestone 4: real bytes
# =============================================================================
def pack_int4(ints):
    """Pack signed 4-bit integers (-8 .. 7) two per byte, as `bytes`.

    The first value goes in the LOW nibble, the second in the HIGH nibble; a negative value is stored
    as its two's complement in 4 bits (v & 0xF). An odd count is padded with a zero nibble.
    Raise ValueError for a value outside -8 .. 7.

    pack_int4([1, -2, 7, -8, 3]) -> bytes([0xE1, 0x87, 0x03])
    """
    nibbles = []
    for v in ints:
        if not -8 <= v <= 7:
            raise ValueError(f"{v} does not fit in a signed 4-bit integer")
        nibbles.append(v & 0xF)
    if len(nibbles) % 2:
        nibbles.append(0)
    return bytes(nibbles[i] | (nibbles[i + 1] << 4) for i in range(0, len(nibbles), 2))


def unpack_int4(data, n):
    """Inverse of pack_int4: the first n signed values (sign-extend each nibble)."""
    out = []
    for b in data:
        for nib in (b & 0xF, b >> 4):
            out.append(nib - 16 if nib >= 8 else nib)
    return out[:n]


def weight_bytes(n_weights, bits, group=None, scale_bits=16):
    """Bytes to store n_weights at `bits` bits each, plus one `scale_bits` scale per `group` weights (none if group is None).

    Packed weights take ceil(n_weights * bits / 8) bytes; scales take ceil(n_weights / group) * scale_bits / 8.
    """
    total = -(-n_weights * bits // 8)
    if group:
        total += -(-n_weights // group) * scale_bits // 8
    return total


def sequences_that_fit(weights_bytes, gpu_bytes=24e9, overhead_bytes=2e9, kv_bytes_per_sequence=KV_BYTES_PER_SEQUENCE_8B):
    """How many whole sequences' KV caches fit beside the weights: floor((gpu - overhead - weights) / kv), at least 0."""
    room = gpu_bytes - overhead_bytes - weights_bytes
    return max(0, int(room // kv_bytes_per_sequence))


# =============================================================================
# Milestone 5: activation outliers
# =============================================================================
def fake_quantise_activations(X, bits, granularity):
    """Quantise then dequantise activations X (T x C), symmetric.

    granularity "tensor": one scale for the whole matrix;  "token": one scale per row of X.
    """
    if granularity == "tensor":
        ints, s = quantise_sym(flatten(X), bits)
        flat = dequantise_sym(ints, s)
        c = len(X[0])
        return [flat[i * c:(i + 1) * c] for i in range(len(X))]
    if granularity == "token":
        out = []
        for row in X:
            ints, s = quantise_sym(row, bits)
            out.append(dequantise_sym(ints, s))
        return out
    raise ValueError(f"unknown granularity {granularity!r}")


def find_outlier_channels(x_absmax, ratio=6.0):
    """Indices of input channels whose absmax exceeds `ratio` times the MEDIAN absmax, in increasing order."""
    s = sorted(x_absmax)
    n = len(s)
    med = s[n // 2] if n % 2 else 0.5 * (s[n // 2 - 1] + s[n // 2])
    return [c for c, v in enumerate(x_absmax) if v > ratio * med]


def mixed_int8_output(X, W, outliers):
    """LLM.int8()-style decomposition. Y = X_normal W_normal^T (int8) + X_outlier W_outlier^T (float).

    Split the input channels into `outliers` (a list of indices) and the rest. For the rest, quantise
    X per tensor (8 bits) and W per channel (8 bits) with fake_quantise_*, then multiply; for the outlier
    channels multiply the exact floats (if there are no normal channels left, that part is all zeros).
    Return the sum, a T x D matrix.
    """
    out_set = set(outliers)
    keep = [c for c in range(len(X[0])) if c not in out_set]
    Xn = [[row[c] for c in keep] for row in X]
    Wn = [[row[c] for c in keep] for row in W]
    if keep:
        Y = matmul_nt(fake_quantise_activations(Xn, 8, "tensor"), fake_quantise_matrix(Wn, 8, "channel"))
    else:                                    # every channel is an outlier: nothing left to quantise
        Y = [[0.0] * len(W) for _ in X]
    if out_set:
        idx = sorted(out_set)
        Xo = [[row[c] for c in idx] for row in X]
        Wo = [[row[c] for c in idx] for row in W]
        Yo = matmul_nt(Xo, Wo)
        Y = [[a + b for a, b in zip(r1, r2)] for r1, r2 in zip(Y, Yo)]
    return Y


def smooth_scales(x_absmax, w_absmax, alpha=0.5):
    """SmoothQuant factors s[c] = x_absmax[c]**alpha / w_absmax[c]**(1 - alpha); s[c] = 1.0 if either is 0."""
    return [(x ** alpha) / (w ** (1 - alpha)) if x > 0 and w > 0 else 1.0 for x, w in zip(x_absmax, w_absmax)]


def apply_smoothing(X, W, s):
    """Return (X', W') with X'[t][c] = X[t][c] / s[c] and W'[d][c] = W[d][c] * s[c]. X' W'^T equals X W^T."""
    return ([[v / s[c] for c, v in enumerate(row)] for row in X],
            [[v * s[c] for c, v in enumerate(row)] for row in W])


# =============================================================================
# Milestone 6: AWQ-style scaling, searched on calibration data
# =============================================================================
def awq_scales(x_absmean, a):
    """s[c] = x_absmean[c]**a, then divided by sqrt(max(s) * min(s)) so the scales are centred around 1.

    a = 0 gives all ones. Channels with x_absmean 0 must not break it: treat a mean below 1e-12 as 1e-12.
    """
    s = [max(v, 1e-12) ** a for v in x_absmean]
    norm = math.sqrt(max(s) * min(s))
    return [v / norm for v in s]


def awq_effective_weights(W, x_absmean, a, bits=4, group=128):
    """The weights the layer effectively uses after AWQ scaling: scale column c of W up by s[c], fake-quantise
    (symmetric, per group), then divide column c by s[c] again. Returns a D x C matrix of floats."""
    s = awq_scales(x_absmean, a)
    Ws = [[v * s[c] for c, v in enumerate(row)] for row in W]
    Wq = fake_quantise_matrix(Ws, bits, "group", group)
    return [[v / s[c] for c, v in enumerate(row)] for row in Wq]


def search_awq(X_cal, W, bits=4, group=128, grid=11):
    """Grid-search the exponent a in linspace(0, 1, grid) on calibration data X_cal.

    For each a: build the effective weights, compute rel_error of matmul_nt(X_cal, Weff) against
    matmul_nt(X_cal, W). Return (best_a, best_error, errors), `errors` listing every grid point's error in
    order. On a tie the smaller a wins. Only the calibration data may be used here.
    """
    Y = matmul_nt(X_cal, W)
    mean = col_absmean(X_cal)
    errors = []
    for i in range(grid):
        a = i / (grid - 1)
        errors.append(rel_error(matmul_nt(X_cal, awq_effective_weights(W, mean, a, bits, group)), Y))
    best = min(range(grid), key=lambda i: (errors[i], i))
    return best / (grid - 1), errors[best], errors


# =============================================================================
# GIVEN: the final report (uses your functions)
# =============================================================================
def report(seed_w=7, seed_cal=100, seed_test=200):
    """Quantise the synthetic layer six ways and measure output error and top-1 agreement on held-out tokens."""
    W = make_weights(seed_w)
    X = make_activations(seed_test)
    Y = matmul_nt(X, W)
    rows = []

    def add(name, Yq, bits_w):
        rows.append((name, rel_error(Yq, Y), top1_agreement(Yq, Y), bits_w))

    n = ROWS * COLS
    add("int8 W per-channel, A per-tensor",
        matmul_nt(fake_quantise_activations(X, 8, "tensor"), fake_quantise_matrix(W, 8, "channel")),
        bits_per_weight(8, ROWS, COLS, "channel"))
    add("int8 W per-channel, A per-token",
        matmul_nt(fake_quantise_activations(X, 8, "token"), fake_quantise_matrix(W, 8, "channel")),
        bits_per_weight(8, ROWS, COLS, "channel"))
    add("int8 mixed (outlier channels in float)",
        mixed_int8_output(X, W, find_outlier_channels(col_absmax(make_activations(seed_cal)))),
        bits_per_weight(8, ROWS, COLS, "channel"))
    s = smooth_scales(col_absmax(make_activations(seed_cal)), col_absmax(W))
    Xs, Ws = apply_smoothing(X, W, s)
    add("int8 SmoothQuant (alpha 0.5)",
        matmul_nt(fake_quantise_activations(Xs, 8, "tensor"), fake_quantise_matrix(Ws, 8, "channel")),
        bits_per_weight(8, ROWS, COLS, "channel"))
    add("int4 weights, per-tensor",
        matmul_nt(X, fake_quantise_matrix(W, 4, "tensor")), bits_per_weight(4, ROWS, COLS, "tensor"))
    add("int4 weights, group 128 (RTN)",
        matmul_nt(X, fake_quantise_matrix(W, 4, "group", 128)), bits_per_weight(4, ROWS, COLS, "group", 128))
    a, _, _ = search_awq(make_activations(seed_cal), W)
    add(f"int4 group 128 + AWQ (a = {a:.1f})",
        matmul_nt(X, awq_effective_weights(W, col_absmean(make_activations(seed_cal)), a)),
        bits_per_weight(4, ROWS, COLS, "group", 128))
    print(f"{'recipe':<42}{'output error':>14}{'top-1 agree':>13}{'bits/weight':>13}")
    for name, e, t, b in rows:
        print(f"{name:<42}{e:>14.4f}{t:>13.3f}{b:>13.3f}")
    return rows


if __name__ == "__main__":
    report()
