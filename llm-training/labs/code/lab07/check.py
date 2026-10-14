"""Self-check for Lab 7: Quantise a Model.

    python3 check.py                  # checks your starter.py
    python3 check.py solution         # checks the reference solution
    python3 check.py solution 5       # only milestone 5
    python3 check.py solution 2 3     # milestone 2, replaying ONLY the random cases of seed 3

Everything is synthetic and seeded: the weights, the activations, every random test list. There is no
network and no clock, so every run gives identical numbers. The whole check takes a few seconds.
Prints a tick, a cross, or "not implemented yet" for each milestone.
"""
import contextlib
import importlib
import io
import math
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True

args = sys.argv[1:]
target = args[0] if args and not args[0].isdigit() else "starter"
rest = [a for a in args if a.isdigit()]
ONLY = int(rest[0]) if rest else None
ONLY_SEED = int(rest[1]) if len(rest) > 1 else None
mod = importlib.import_module(target)
results = []


def seeds(default):
    return [ONLY_SEED] if ONLY_SEED is not None else list(default)


def check(number, name, fn):
    if ONLY is not None and ONLY != number:
        return
    try:
        note = fn()
        print(f"  ✔ {name}")
        for line in (note or "").splitlines():
            print(f"      {line}")
        results.append(True)
    except NotImplementedError as e:
        print(f"  … {name}: not implemented yet ({e})")
        results.append(False)
    except AssertionError as e:
        print(f"  ✘ {name}: {e}")
        results.append(False)
    except Exception as e:
        import traceback
        tb = traceback.extract_tb(e.__traceback__)
        where = next((f"{f.name}() line {f.lineno}" for f in reversed(tb) if f.filename.endswith(f"{target}.py")), "?")
        print(f"  ✘ {name}: {type(e).__name__}: {e}   [in {where}]")
        results.append(False)


def near(a, b, tol=1e-9):
    return abs(a - b) <= tol * max(1.0, abs(a), abs(b))


def all_near(xs, ys, tol=1e-9):
    return len(xs) == len(ys) and all(near(a, b, tol) for a, b in zip(xs, ys))


def rnd_list(rng, n, sigma=1.0):
    return [rng.gauss(0.0, sigma) for _ in range(n)]


def rnd_matrix(rng, rows, cols, sigma=1.0):
    return [rnd_list(rng, cols, sigma) for _ in range(rows)]


# Independent, deliberately plain oracles for the cross-checks ------------------------------------
def o_sym(values, bits):
    q = 2 ** (bits - 1) - 1
    m = max(abs(v) for v in values)
    s = m / q if m > 0 else 1.0
    return [max(-q, min(q, round(v / s))) for v in values], s


def o_deq(values, bits):
    ints, s = o_sym(values, bits)
    return [i * s for i in ints]


def o_matrix(W, bits, gran, group=128):
    if gran == "tensor":
        flat = o_deq([v for r in W for v in r], bits)
        c = len(W[0])
        return [flat[i * c:(i + 1) * c] for i in range(len(W))]
    if gran == "channel":
        return [o_deq(r, bits) for r in W]
    return [sum((o_deq(r[i:i + group], bits) for i in range(0, len(r), group)), []) for r in W]


# =============================================================================
# Milestone 1: symmetric quantisation
# =============================================================================
def m1():
    for bits, q in [(2, 1), (3, 3), (4, 7), (8, 127)]:
        assert mod.qmax(bits) == q, f"qmax({bits}) should be {q} (2**({bits}-1) - 1), got {mod.qmax(bits)}"
    w = [0.02, -0.11, 0.07, 0.31, -0.05, 0.00, 0.13, -0.28]
    ints, s = mod.quantise_sym(w, 4)
    assert list(ints) == [0, -2, 2, 7, -1, 0, 3, -6], (
        f"chapter 19's eight weights at int4 should give [0, -2, 2, 7, -1, 0, 3, -6], got {list(ints)}. "
        "The scale is absmax / 7, and each integer is round(w / scale).")
    assert near(s, 0.31 / 7), f"the scale should be 0.31 / 7 = {0.31 / 7:.5f}, got {s}"
    back = mod.dequantise_sym(ints, s)
    assert near(back[3], 0.31, 1e-12), "the largest weight must come back exactly (it sits on the top level)"
    assert near(back[1], -2 * 0.31 / 7), f"dequantise_sym should multiply by the scale, got {back[1]}"
    assert mod.scale_sym([0.0, 0.0, 0.0], 4) == 1.0, "an all-zero list needs scale 1.0 so nothing divides by zero"
    z_ints, _ = mod.quantise_sym([0.0, 0.0], 8)
    assert list(z_ints) == [0, 0], "an all-zero list quantises to zeros"
    ints, s = mod.quantise_sym([-2.0, 0.5, 1.0], 8)
    assert ints[0] == -127 and near(s, 2.0 / 127), "the absmax can be negative: -2.0 must land on -127 with scale 2/127"
    # properties
    worst = {}
    for seed in seeds(range(1, 41)):
        rng = random.Random(seed)
        bits = rng.choice([2, 3, 4, 5, 6, 8])
        n = rng.randint(1, 200)
        v = rnd_list(rng, n, rng.choice([0.02, 1.0, 30.0]))
        ints, s = mod.quantise_sym(v, bits)
        q = 2 ** (bits - 1) - 1
        where = f"(seed {seed}: {n} values, {bits} bits)"
        assert len(ints) == n and all(isinstance(i, int) for i in ints), f"ints must be Python ints, one per value {where}"
        assert all(-q <= i <= q for i in ints), f"integers must stay within -{q}..{q}; the grid is symmetric and never uses -{q + 1} {where}"
        assert near(s, max(abs(x) for x in v) / q), f"scale must be absmax / qmax {where}"
        back = mod.dequantise_sym(ints, s)
        err = max(abs(a - b) for a, b in zip(back, v))
        assert err <= s / 2 + 1e-12, f"the rounding error of any value is at most scale / 2 = {s / 2:.3g}, got {err:.3g} {where}"
        big = max(range(n), key=lambda i: abs(v[i]))
        assert near(back[big], v[big], 1e-9), f"the largest-magnitude value must round-trip exactly {where}"
        ints2, s2 = mod.quantise_sym(back, bits)
        assert list(ints2) == list(ints) and near(s2, s), f"quantising an already-quantised list must change nothing (idempotent) {where}"
        worst[bits] = max(worst.get(bits, 0), err / s)
    # error falls by about 2x per extra bit
    rng = random.Random(0)
    v = rnd_list(rng, 4000)
    e = {}
    for bits in (4, 8):
        ints, s = mod.quantise_sym(v, bits)
        e[bits] = math.sqrt(sum((a - b) ** 2 for a, b in zip(mod.dequantise_sym(ints, s), v)) / sum(b * b for b in v))
    ratio = e[4] / e[8]
    assert 8 < ratio < 30, (f"relative error at int4 / int8 should be about 127/7 = 18 on Gaussian data, got {ratio:.1f} "
                            f"(int4 {e[4]:.4f}, int8 {e[8]:.5f})")
    return (f"chapter 19's eight weights: ints [0, -2, 2, 7, -1, 0, 3, -6], scale 0.31/7; 40 seeded lists: error never above scale/2, idempotent;\n"
            f"4000 Gaussian values: relative error int4 {e[4]:.4f}, int8 {e[8]:.5f} (ratio {ratio:.1f})")


# =============================================================================
# Milestone 2: asymmetric quantisation
# =============================================================================
def m2():
    ints, s, z = mod.quantise_asym([-1.0, 0.0, 3.0], 3)
    assert list(ints) == [0, 2, 7] and near(s, 4 / 7) and z == 2, (
        f"[-1, 0, 3] at 3 bits should give ints [0, 2, 7], scale 4/7, zero point 2; got {list(ints)}, {s:.4f}, {z}. "
        "scale = (hi - lo) / (2**bits - 1), zero_point = round(-lo / scale), q = round(v / scale) + zero_point.")
    ints, s, z = mod.quantise_asym([float(i) for i in range(8)], 3)
    assert list(ints) == list(range(8)) and near(s, 1.0) and z == 0, f"0..7 at 3 bits is already on the grid, got {list(ints)}, scale {s}, zero point {z}"
    ints, s, z = mod.quantise_asym([1.0, 2.0, 5.0], 4)
    assert z == 0 and near(s, 5 / 15) and list(ints) == [3, 6, 15], (
        f"all-positive data still includes real zero in its range (lo = min(min, 0)): expected zero point 0, scale 1/3, ints [3, 6, 15]; "
        f"got zero point {z}, scale {s:.4f}, ints {list(ints)}")
    assert mod.quantise_asym([0.0, 0.0], 8) == ([0, 0], 1.0, 0), "an all-zero list gives ([0, ...], 1.0, 0)"
    assert all_near(mod.dequantise_asym([0, 2, 7], 4 / 7, 2), [-8 / 7, 0.0, 20 / 7]), "dequantise_asym is (q - zero_point) * scale"
    for seed in seeds(range(1, 41)):
        rng = random.Random(seed)
        bits = rng.choice([2, 3, 4, 6, 8])
        n = rng.randint(2, 200)
        shift = rng.choice([0.0, 0.0, 1.5, -2.0])
        v = [x + shift for x in rnd_list(rng, n, rng.choice([0.1, 1.0, 20.0]))]
        v[rng.randrange(n)] = 0.0
        ints, s, z = mod.quantise_asym(v, bits)
        top = 2 ** bits - 1
        where = f"(seed {seed}: {n} values, {bits} bits, shift {shift})"
        assert all(0 <= i <= top for i in ints), f"integers must lie in 0..{top} {where}"
        assert 0 <= z <= top and isinstance(z, int), f"the zero point is an integer in 0..{top}, got {z} {where}"
        back = mod.dequantise_asym(ints, s, z)
        zero_at = v.index(0.0)
        assert abs(back[zero_at]) < 1e-12, f"real 0.0 must round-trip EXACTLY (that is what the zero point is for), got {back[zero_at]} {where}"
        err = max(abs(a - b) for a, b in zip(back, v))
        assert err <= s / 2 + 1e-9 * s, f"the rounding error is at most scale / 2 = {s / 2:.3g}, got {err:.3g} {where}"
    rng = random.Random(3)
    relu = [max(0.0, rng.gauss(0, 1)) for _ in range(2048)]
    gauss = rnd_list(rng, 2048)

    def rel(fn, v):
        out = fn(v)
        return math.sqrt(sum((a - b) ** 2 for a, b in zip(out, v)) / sum(b * b for b in v))

    sym = lambda v: mod.dequantise_sym(*mod.quantise_sym(v, 4))
    asym = lambda v: mod.dequantise_asym(*mod.quantise_asym(v, 4))
    r_sym, r_asym = rel(sym, relu), rel(asym, relu)
    g_sym, g_asym = rel(sym, gauss), rel(asym, gauss)
    assert r_asym < 0.6 * r_sym, (f"on all-positive (ReLU-like) data at int4, asymmetric should be much better than symmetric, "
                                  f"which wastes the negative half of its grid: got asym {r_asym:.4f} vs sym {r_sym:.4f}")
    assert 0.8 < g_asym / g_sym < 1.25, (f"on zero-centred data the two schemes should be about equal, got asym {g_asym:.4f} vs sym {g_sym:.4f}")
    return (f"hand cases and 40 seeded lists (real 0.0 round-trips exactly); int4 on ReLU-like data: relative error symmetric {r_sym:.4f}, asymmetric {r_asym:.4f};\n"
            f"on zero-centred data: symmetric {g_sym:.4f}, asymmetric {g_asym:.4f}")


# =============================================================================
# Milestone 3: granularity
# =============================================================================
def m3():
    W = [[1.0, -0.4], [0.2, 0.6]]
    t = mod.fake_quantise_matrix(W, 4, "tensor")
    assert all_near(t[0], [1.0, -3 / 7]) and all_near(t[1], [1 / 7, 4 / 7]), (
        f"per-tensor int4 on [[1.0, -0.4], [0.2, 0.6]]: one scale 1/7, so the matrix becomes [[1, -3/7], [1/7, 4/7]]; got {t}")
    c = mod.fake_quantise_matrix(W, 4, "channel")
    assert all_near(c[0], [1.0, -3 / 7]) and all_near(c[1], [2 * 0.6 / 7, 0.6]), (
        f"per-channel: row 1 has its own scale 0.6/7, so 0.2 becomes 2 * 0.6/7 and 0.6 stays 0.6; got {c[1]}")
    g1 = mod.fake_quantise_matrix(W, 4, "group", 1)
    assert all(all_near(a, b, 1e-12) for a, b in zip(g1, W)), "a group of size 1 gives every weight its own scale, so nothing is lost"
    keep = [row[:] for row in W]
    mod.fake_quantise_matrix(W, 4, "group", 2)
    assert W == keep, "fake_quantise_matrix must not modify its input"
    try:
        mod.fake_quantise_matrix(W, 4, "block")
        raise AssertionError("an unknown granularity must raise ValueError")
    except ValueError:
        pass
    assert mod.n_scales(48, 256, "tensor") == 1 and mod.n_scales(48, 256, "channel") == 48 and mod.n_scales(48, 256, "group", 128) == 96, (
        "n_scales: 1, rows, rows * ceil(cols / group)")
    assert mod.n_scales(3, 300, "group", 128) == 9, "a row of 300 weights in groups of 128 has 3 groups (the last is short): 3 rows -> 9 scales"
    assert near(mod.bits_per_weight(4, 4096, 4096, "group", 128), 4.125), "4-bit weights with a 16-bit scale per 128 cost 4.125 bits each"
    assert near(mod.bits_per_weight(8, 4096, 4096, "channel"), 8 + 16 / 4096), "int8 per-channel on 4096 x 4096 costs 8 + 16/4096 bits"
    assert near(mod.bits_per_weight(4, 48, 256, "tensor"), 4 + 16 / (48 * 256)), "a single scale is nearly free"
    # cross-check against an independent implementation on random matrices
    for seed in seeds(range(1, 13)):
        rng = random.Random(seed)
        rows, cols = rng.randint(1, 6), rng.choice([5, 64, 130, 256, 300])
        bits = rng.choice([3, 4, 8])
        M = rnd_matrix(rng, rows, cols, 0.05)
        for gran in ("tensor", "channel", "group"):
            got = mod.fake_quantise_matrix(M, bits, gran, 64)
            want = o_matrix(M, bits, gran, 64)
            for r in range(rows):
                assert all_near(got[r], want[r], 1e-9), (
                    f"{gran} at {bits} bits disagrees with the plain reference in row {r} (seed {seed}, {rows} x {cols}); "
                    "check which numbers share a scale")
    # the synthetic layer: loud rows and spikes
    W = mod.make_weights()
    table = {}
    for bits in (8, 4):
        for gran in ("tensor", "channel", "group"):
            table[bits, gran] = mod.rel_error(mod.fake_quantise_matrix(W, bits, gran, 128), W)
    for bits in (8, 4):
        assert table[bits, "tensor"] > 2 * table[bits, "channel"], (
            f"two loud rows (12x and 20x) should make per-tensor much worse than per-channel at {bits} bits: "
            f"tensor {table[bits, 'tensor']:.4f} vs channel {table[bits, 'channel']:.4f}")
        assert table[bits, "group"] < table[bits, "channel"], (
            f"spikes inside a row should make groups of 128 better than a whole row at {bits} bits: "
            f"group {table[bits, 'group']:.4f} vs channel {table[bits, 'channel']:.4f}")
    for gran in ("tensor", "channel", "group"):
        assert table[4, gran] > 5 * table[8, gran], f"{gran}: int4 should be several times worse than int8, got {table[4, gran]:.4f} vs {table[8, gran]:.4f}"
    lines = ["relative weight error ||W - Wq|| / ||W|| on the 48 x 256 layer (loud rows 5, 30; four spikes):"]
    for bits in (8, 4):
        lines.append(f"    int{bits}: per-tensor {table[bits, 'tensor']:.4f}, per-channel {table[bits, 'channel']:.4f}, group-128 {table[bits, 'group']:.4f}")
    lines.append(f"cost: per-channel {mod.bits_per_weight(4, 48, 256, 'channel'):.4f}, group-128 {mod.bits_per_weight(4, 48, 256, 'group'):.4f} bits per int4 weight")
    return "\n".join(lines)


# =============================================================================
# Milestone 4: real bytes
# =============================================================================
def m4():
    packed = mod.pack_int4([1, -2, 7, -8, 3])
    assert isinstance(packed, (bytes, bytearray)), f"pack_int4 returns bytes, got {type(packed).__name__}"
    assert bytes(packed) == bytes([0xE1, 0x87, 0x03]), (
        f"pack_int4([1, -2, 7, -8, 3]) should be e1 87 03 (first value in the low nibble, -2 is 0xE, an odd count pads a zero nibble); "
        f"got {bytes(packed).hex(' ')}")
    assert list(mod.unpack_int4(bytes([0xE1, 0x87, 0x03]), 5)) == [1, -2, 7, -8, 3], "unpack_int4 must sign-extend: nibble 0xE is -2, 0x8 is -8"
    assert bytes(mod.pack_int4([])) == b"", "no values, no bytes"
    for bad in (8, -9, 100):
        try:
            mod.pack_int4([0, bad])
            raise AssertionError(f"{bad} does not fit in 4 signed bits: pack_int4 must raise ValueError")
        except ValueError:
            pass
    for seed in seeds(range(1, 31)):
        rng = random.Random(seed)
        n = rng.randint(0, 120)
        v = [rng.randint(-8, 7) for _ in range(n)]
        p = bytes(mod.pack_int4(v))
        assert len(p) == (n + 1) // 2, f"{n} 4-bit values take ceil(n / 2) = {(n + 1) // 2} bytes, got {len(p)} (seed {seed})"
        assert list(mod.unpack_int4(p, n)) == v, f"unpack_int4(pack_int4(v), len(v)) must give v back (seed {seed}, n = {n})"
    assert mod.weight_bytes(1_000_000, 4, 128) == 515_626, (
        f"1 M weights at 4 bits with a 16-bit scale per 128: 500,000 bytes of weights + ceil(1e6 / 128) = 7,813 scales x 2 bytes = 515,626; "
        f"got {mod.weight_bytes(1_000_000, 4, 128)}")
    assert mod.weight_bytes(1_000_000, 16) == 2_000_000 and mod.weight_bytes(1_000_000, 8) == 1_000_000, "no group means no scale bytes"
    assert mod.weight_bytes(5, 4) == 3, "five 4-bit weights need 3 bytes (round up)"
    # the formula against real packed bytes of a quantised matrix
    W = mod.make_weights()
    flat = []
    n_groups = 0
    for row in W:
        for i in range(0, len(row), 128):
            ints, _ = o_sym(row[i:i + 128], 4)
            flat += ints
            n_groups += 1
    real = len(bytes(mod.pack_int4(flat))) + 2 * n_groups
    assert real == mod.weight_bytes(len(flat), 4, 128), (
        f"weight_bytes should match what packing really produces: {real} bytes for the 48 x 256 layer, got {mod.weight_bytes(len(flat), 4, 128)}")
    # chapter 19's "what fits on 24 GB" table
    n8 = mod.llama_params("8B")
    want = {"bf16": (16, None, 5), "int8": (8, None, 13), "int4, group 128": (4, 128, 16), "int3, group 128": (3, 128, 17)}
    lines = []
    for name, (bits, group, seqs) in want.items():
        wb = mod.weight_bytes(n8, bits, group)
        got = mod.sequences_that_fit(wb)
        assert got == seqs, (f"Llama 3 8B at {name}: {wb / 1e9:.2f} GB of weights on a 24 GB card with 2 GB overhead should leave room for "
                             f"{seqs} sequences of 8,192 tokens (1 GiB of KV cache each), got {got}")
        lines.append(f"{name:<16}{wb / 1e9:>7.2f} GB  ->  {got:>2} sequences")
    assert mod.sequences_that_fit(mod.weight_bytes(mod.llama_params("70B"), 4, 128)) == 0, "70B at 4 bits (36 GB) does not fit on 24 GB: the answer is 0, never negative"
    assert mod.sequences_that_fit(24e9 - 2e9 - 2 ** 30) == 1 and mod.sequences_that_fit(24e9 - 2e9 - 2 ** 30 + 1) == 0, "exactly one sequence fits at the boundary, and one byte less fits none"
    return "Llama 3 8B on one 24 GB card (2 GB overhead, 8,192-token sequences):\n" + "\n".join("    " + l for l in lines)


# =============================================================================
# Milestone 5: activation outliers
# =============================================================================
def m5():
    X = [[1.0, -0.4], [0.2, 0.6]]
    t = mod.fake_quantise_activations(X, 4, "tensor")
    assert all_near(t[0], [1.0, -3 / 7]) and all_near(t[1], [1 / 7, 4 / 7]), f"per-tensor int4: one scale 1/7; expected [[1, -3/7], [1/7, 4/7]], got {t}"
    k = mod.fake_quantise_activations(X, 4, "token")
    assert all_near(k[1], [2 * 0.6 / 7, 0.6]), f"per-token: row 1 has its own scale 0.6/7; expected [2*0.6/7, 0.6], got {k[1]}"
    try:
        mod.fake_quantise_activations(X, 8, "channel")
        raise AssertionError("an unknown granularity must raise ValueError")
    except ValueError:
        pass
    assert mod.find_outlier_channels([1, 1, 1, 50, 1, 1, 70, 1.0]) == [3, 6], "channels 3 and 6 are far above 6x the median"
    assert mod.find_outlier_channels([1.0, 2.0, 3.0, 4.0], ratio=1.5) == [3], "median of an even count is the mean of the two middle values (2.5): only 4 > 1.5 x 2.5 = 3.75"
    assert mod.find_outlier_channels([1.0, 1.0, 6.0, 1.0]) == [], "the test is strictly greater than ratio x median: 6 is not above 6 x 1"
    s = mod.smooth_scales([4.0, 1.0], [1.0, 4.0], 0.5)
    assert all_near(s, [2.0, 0.5]), f"smooth_scales([4, 1], [1, 4], alpha 0.5) should be [2, 0.5] (= sqrt(x) / sqrt(w)), got {s}"
    assert all_near(mod.smooth_scales([4.0, 3.0], [2.0, 5.0], 1.0), [4.0, 3.0]), "alpha = 1 moves the whole absmax: s = x_absmax"
    assert all_near(mod.smooth_scales([4.0, 3.0], [2.0, 5.0], 0.0), [0.5, 0.2]), "alpha = 0 gives s = 1 / w_absmax"
    assert mod.smooth_scales([0.0, 2.0], [1.0, 0.0], 0.5) == [1.0, 1.0], "a channel with a zero absmax on either side keeps scale 1.0"
    for seed in seeds(range(1, 9)):
        rng = random.Random(seed)
        T, C, D = rng.randint(2, 7), rng.randint(2, 9), rng.randint(2, 6)
        Xr, Wr = rnd_matrix(rng, T, C, 3.0), rnd_matrix(rng, D, C, 0.1)
        alpha = rng.choice([0.25, 0.5, 0.75])
        s = mod.smooth_scales(mod.col_absmax(Xr), mod.col_absmax(Wr), alpha)
        Xs, Ws = mod.apply_smoothing(Xr, Wr, s)
        Y, Ys = mod.matmul_nt(Xr, Wr), mod.matmul_nt(Xs, Ws)
        assert all(all_near(a, b, 1e-9) for a, b in zip(Y, Ys)), f"smoothing must leave X W^T unchanged (seed {seed}); divide X's column by s and multiply W's column by the SAME s"
        if alpha == 0.5:
            xm, wm = mod.col_absmax(Xs), mod.col_absmax(Ws)
            assert all_near(xm, wm, 1e-9), f"at alpha = 0.5 each channel's absmax should be equal on the two sides (seed {seed})"
        assert len(Xs) == T and len(Xs[0]) == C and len(Ws) == D, "shapes must be preserved"
    # scenario on the synthetic layer
    W = mod.make_weights()
    X_cal, X_test = mod.make_activations(100), mod.make_activations(200)
    Y = mod.matmul_nt(X_test, W)
    outs = mod.find_outlier_channels(mod.col_absmax(X_cal))
    assert outs == list(mod.OUTLIER_CHANNELS), f"on the calibration activations the outlier channels are {list(mod.OUTLIER_CHANNELS)}, got {outs}"
    Wc = mod.fake_quantise_matrix(W, 8, "channel")
    e_tensor = mod.rel_error(mod.matmul_nt(mod.fake_quantise_activations(X_test, 8, "tensor"), Wc), Y)
    e_token = mod.rel_error(mod.matmul_nt(mod.fake_quantise_activations(X_test, 8, "token"), Wc), Y)
    plain = mod.mixed_int8_output(X_test, W, [])
    assert all(all_near(a, b, 1e-9) for a, b in zip(plain, mod.matmul_nt(mod.fake_quantise_activations(X_test, 8, "tensor"), Wc))), (
        "with no outlier channels, mixed_int8_output is plain W8A8: X per tensor, W per channel")
    everything = mod.mixed_int8_output(X_test, W, list(range(mod.COLS)))
    assert all(all_near(a, b, 1e-9) for a, b in zip(everything, Y)), "with every channel an outlier, nothing is quantised and the output is exact"
    e_mixed = mod.rel_error(mod.mixed_int8_output(X_test, W, outs), Y)
    s = mod.smooth_scales(mod.col_absmax(X_cal), mod.col_absmax(W), 0.5)
    Xs, Ws = mod.apply_smoothing(X_test, W, s)
    e_smooth = mod.rel_error(mod.matmul_nt(mod.fake_quantise_activations(Xs, 8, "tensor"), mod.fake_quantise_matrix(Ws, 8, "channel")), Y)
    assert e_tensor > 0.05, f"two channels 40x larger should wreck a per-tensor activation scale (expected error above 0.05), got {e_tensor:.4f}"
    assert e_token < e_tensor, f"a scale per token should help a little: {e_token:.4f} vs {e_tensor:.4f}"
    assert e_mixed < 0.02, f"keeping the two outlier channels in float should bring the error under 0.02, got {e_mixed:.4f}"
    assert e_smooth < 0.5 * e_tensor, f"SmoothQuant should at least halve the per-tensor error ({e_tensor:.4f}); got {e_smooth:.4f}"
    return (f"int8 weights per-channel; output error on held-out tokens: activations per-tensor {e_tensor:.4f}, per-token {e_token:.4f}, SmoothQuant (alpha 0.5) {e_smooth:.4f},\n"
            f"mixed precision with channels {outs} in float {e_mixed:.4f}")


# =============================================================================
# Milestone 6: AWQ-style scaling and calibration
# =============================================================================
def m6():
    s = mod.awq_scales([4.0, 1.0], 0.5)
    assert all_near(s, [2 / math.sqrt(2), 1 / math.sqrt(2)]), f"awq_scales([4, 1], 0.5): mean**0.5 = [2, 1], divided by sqrt(2 * 1); got {s}"
    assert all_near(mod.awq_scales([4.0, 1.0], 1.0), [2.0, 0.5]), "awq_scales([4, 1], 1.0) = [4, 1] / sqrt(4) = [2, 0.5]"
    assert all_near(mod.awq_scales([4.0, 1.0, 9.0], 0.0), [1.0, 1.0, 1.0]), "exponent 0 means no scaling: all ones"
    s0 = mod.awq_scales([0.0, 2.0], 0.5)
    assert all(math.isfinite(v) and v > 0 for v in s0), f"a zero activation mean must not break the scales (clamp it to 1e-12), got {s0}"
    W = mod.make_weights()
    X_cal, X_test = mod.make_activations(100), mod.make_activations(200)
    mean = mod.col_absmean(X_cal)
    keep = [row[:] for row in W]
    W0 = mod.awq_effective_weights(W, mean, 0.0)
    assert W == keep, "awq_effective_weights must not modify W"
    rtn = mod.fake_quantise_matrix(W, 4, "group", 128)
    assert all(all_near(a, b, 1e-9) for a, b in zip(W0, rtn)), "with exponent 0 the effective weights are plain round-to-nearest with group scales"
    assert len(W0) == mod.ROWS and len(W0[0]) == mod.COLS, "effective weights have the same shape as W"
    W5 = mod.awq_effective_weights(W, mean, 0.5)
    assert mod.rel_error(W5, W) != mod.rel_error(rtn, W), "a nonzero exponent changes which weights share a grid, so the result must differ from RTN"
    assert mod.rel_error(mod.awq_effective_weights(W, mean, 0.5, bits=16, group=128), W) < 1e-3, (
        "at 16 bits the scaling is divided out again and almost nothing is lost: the effective weights should be within 1e-3 of W")
    Y = mod.matmul_nt(X_cal, W)
    best_a, best_e, errs = mod.search_awq(X_cal, W)
    assert isinstance(errs, list) and len(errs) == 11, f"search_awq returns (best_a, best_error, errors) with one error per grid point (11 by default), got {len(errs) if hasattr(errs, '__len__') else errs}"
    assert len(mod.search_awq(X_cal, W, grid=5)[2]) == 5, "grid=5 means exponents 0, 0.25, 0.5, 0.75, 1.0"
    rtn_cal = mod.rel_error(mod.matmul_nt(X_cal, rtn), Y)
    assert near(errs[0], rtn_cal, 1e-9), f"the first grid point (exponent 0) is plain RTN: expected error {rtn_cal:.4f}, got {errs[0]:.4f}"
    assert near(best_e, min(errs), 1e-12) and near(best_a, errs.index(min(errs)) / 10, 1e-12), "best_a / best_error must be the grid point with the lowest error (the smaller a on a tie)"
    assert 0.1 <= best_a <= 0.9, f"the best exponent should be strictly inside (0, 1): the curve falls and then rises. Got {best_a:.1f}"
    assert errs[10] > errs[0], f"a = 1 over-scales and should be worse than RTN on calibration data: {errs[10]:.4f} vs {errs[0]:.4f}"
    assert best_e < 0.5 * errs[0], f"AWQ should at least halve the RTN error on the calibration data ({errs[0]:.4f}); got {best_e:.4f}"
    # held-out tokens from the same distribution
    Yt = mod.matmul_nt(X_test, W)
    e_rtn = mod.rel_error(mod.matmul_nt(X_test, rtn), Yt)
    e_awq = mod.rel_error(mod.matmul_nt(X_test, mod.awq_effective_weights(W, mean, best_a)), Yt)
    assert e_awq < 0.5 * e_rtn, f"the gain should carry over to held-out tokens with the same outlier channels: RTN {e_rtn:.4f}, AWQ {e_awq:.4f}"
    # calibration that does not match deployment
    X_bad = mod.make_activations(101, channels=(60, 150))
    a_bad, e_bad_cal, _ = mod.search_awq(X_bad, W)
    e_bad = mod.rel_error(mod.matmul_nt(X_test, mod.awq_effective_weights(W, mod.col_absmean(X_bad), a_bad)), Yt)
    assert e_bad_cal < rtn_cal, "on its own calibration data the search still finds an improvement"
    assert e_bad > 1.2 * e_rtn, (f"calibrated on data whose outlier channels are in the wrong place, AWQ should HURT on the real traffic: "
                                 f"RTN {e_rtn:.4f}, mismatched AWQ {e_bad:.4f}. Use only the calibration data's statistics (col_absmean(X_cal))")
    # the whole report
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rows = mod.report()
    by = {name: (e, top) for name, e, top, _ in rows}
    names = list(by)
    e = [by[n][0] for n in names]
    assert e[2] < e[3] < e[1] < e[0], "report: expected error order mixed < SmoothQuant < per-token < per-tensor activations at int8"
    assert e[6] < e[5] < e[4], "report: expected error order AWQ < RTN group 128 < per-tensor at int4"
    return (f"search over 11 exponents on 64 calibration tokens: best a = {best_a:.1f}; RTN error {rtn_cal:.4f} -> {best_e:.4f} on calibration, {e_rtn:.4f} -> {e_awq:.4f} on held-out tokens;\n"
            f"calibrated on the WRONG outlier channels: held-out error {e_rtn:.4f} -> {e_bad:.4f} (worse than doing nothing)\n"
            + "\n".join(buf.getvalue().rstrip().splitlines()))


print(f"Lab 7 checks against {target}.py\n")
t0 = time.time()
check(1, "Milestone 1: symmetric quantisation", m1)
check(2, "Milestone 2: asymmetric quantisation and the zero point", m2)
check(3, "Milestone 3: per-tensor, per-channel and per-group scales", m3)
check(4, "Milestone 4: packing int4 and counting bytes", m4)
check(5, "Milestone 5: activation outliers, mixed precision and SmoothQuant", m5)
check(6, "Milestone 6: AWQ-style scaling, calibration and the report", m6)
done = sum(results)
print(f"\n{done}/{len(results)} milestones passing  ({time.time() - t0:.1f} s)")
