"""Self-check for Lab 6: The Model Resource Calculator.

    python3 check.py                  # checks your starter.py
    python3 check.py solution         # checks the reference solution
    python3 check.py solution 3       # only milestone 3
    python3 check.py solution 3 17    # milestone 3, replaying ONLY the random case with seed 17

Everything is closed-form arithmetic on model shapes, plus seeded random shapes for the property tests.
There is no clock, no network and no GPU, so every run gives identical numbers and finishes in a
second or two. Prints a tick, a cross, or "not implemented yet" for each milestone.
"""
import importlib
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
Config, M, GB = mod.Config, mod.MODELS, 1e9
BES = mod.FITS["Besiroglu et al. 2024 (replication)"]
HOF = mod.FITS["Hoffmann et al. 2022 (as printed)"]


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


def rel(a, b):
    return abs(a - b) / abs(b)


def close(a, b, tol, what):
    assert rel(a, b) <= tol, f"{what}: expected about {b:,.6g}, got {a:,.6g} (off by {100 * rel(a, b):.2f}%)"


# ---- independent oracle: list every weight tensor of the model and add up their sizes --------------------
def o_tensors(cfg, active=False):
    d = cfg.C // cfg.H
    kvw = cfg.KV * d
    shapes = [("embed", cfg.V, cfg.C)]
    if not cfg.tied:
        shapes.append(("head", cfg.V, cfg.C))
    if cfg.positions:
        shapes.append(("pos", cfg.positions, cfg.C))
    for _ in range(cfg.L):
        shapes += [("wq", cfg.C, cfg.C), ("wk", cfg.C, kvw), ("wv", cfg.C, kvw), ("wo", cfg.C, cfg.C)]
        if cfg.bias:
            shapes += [("bq", cfg.C, 1), ("bk", kvw, 1), ("bv", kvw, 1), ("bo", cfg.C, 1)]
        if cfg.experts > 1:
            shapes.append(("router", cfg.C, cfg.experts))
        for _e in range(cfg.top_k if active else cfg.experts):
            shapes += [("up", cfg.C, cfg.F), ("down", cfg.F, cfg.C)]
            if cfg.mlp == "swiglu":
                shapes.append(("gate", cfg.C, cfg.F))
            if cfg.bias:
                shapes += [("b_up", cfg.F, 1), ("b_down", cfg.C, 1)] + ([("b_gate", cfg.F, 1)] if cfg.mlp == "swiglu" else [])
        for _n in range(2):
            shapes.append(("norm", cfg.C * (1 if cfg.norm == "rms" else 2), 1))
    shapes.append(("final_norm", cfg.C * (1 if cfg.norm == "rms" else 2), 1))
    return sum(a * b for _, a, b in shapes)


def random_config(rng, **force):
    H = rng.choice([2, 4, 8, 16])
    d = rng.choice([8, 16, 32])
    kw = dict(name="random", C=H * d, L=rng.randint(1, 8), H=H, KV=rng.choice([k for k in (1, 2, 4, 8, 16) if H % k == 0]),
              F=rng.randint(10, 400), V=rng.randint(50, 5000), mlp=rng.choice(["swiglu", "gelu"]), norm=rng.choice(["rms", "layer"]),
              bias=rng.random() < 0.5, tied=rng.random() < 0.5, positions=rng.choice([0, 0, 128, 512]))
    if rng.random() < 0.4:
        kw["experts"] = rng.choice([2, 4, 8])
        kw["top_k"] = rng.randint(1, 2)
    kw.update(force)
    return Config(**kw)


# =============================================================================
# Milestone 1: counting parameters
# =============================================================================
def m1():
    l8, l70, l405, l2, g2, mx = (M[k] for k in ("Llama 3 8B", "Llama 3 70B", "Llama 3 405B", "Llama 2 7B", "GPT-2 small", "Mixtral 8x7B"))
    assert mod.head_dim(l8) == 128 and mod.head_dim(g2) == 64, "d_k = C / H: 4096/32 = 128 and 768/12 = 64"
    assert mod.attn_params(l8) == 41_943_040, (f"Llama 3 8B attention: W_q and W_o are 4096 x 4096, W_k and W_v are 4096 x (8 key/value heads x 128) "
                                              f"= 4096 x 1024, so 2*4096^2 + 2*4096*1024 = 41,943,040; got {mod.attn_params(l8):,}")
    assert mod.mlp_params(l8) == 176_160_768, f"Llama 3 8B MLP: 3 * 4096 * 14336 = 176,160,768, got {mod.mlp_params(l8):,}"
    assert mod.norm_params(l8) == 8192, "two RMSNorm gains of 4096 per block"
    assert mod.block_params(l8) == 218_112_000, f"Llama 3 8B per block should be 218,112,000 (chapter 16), got {mod.block_params(l8):,}"
    assert mod.embedding_params(l8) == 1_050_673_152, f"two tables of 128,256 x 4096 = 1,050,673,152, got {mod.embedding_params(l8):,}"
    assert mod.attn_params(g2) == 2_362_368, f"GPT-2 small attention with biases: 4*768^2 + 4*768 = 2,362,368, got {mod.attn_params(g2):,}"
    assert mod.mlp_params(g2) == 4_722_432, f"GPT-2 small MLP: 2*768*3072 + 3072 + 768 = 4,722,432, got {mod.mlp_params(g2):,}"
    assert mod.norm_params(g2) == 3072, "two LayerNorms with gain and bias: 2 * 2 * 768"
    assert mod.embedding_params(g2) == 50257 * 768 + 1024 * 768, "tied head: one 50,257 x 768 table, plus 1,024 learned positions"

    exact = [("Llama 3 8B", 8_030_261_248), ("Llama 3 70B", 70_553_706_496), ("Llama 3 405B", 405_853_388_800),
             ("Llama 2 7B", 6_738_415_616), ("GPT-2 small", 124_439_808), ("Mixtral 8x7B", 46_702_792_704)]
    for name, want in exact:
        got = mod.count_params(M[name])
        assert got == want, (f"{name}: expected {want:,} parameters, got {got:,} (off by {got - want:+,}). "
                             "Likely culprits: tied/untied embeddings, biases, the final norm, GQA key/value width, SwiGLU's third matrix")
    act = mod.count_params(mx, active=True)
    assert act == 12_879_925_248, f"Mixtral active parameters per token: 2 of 8 experts, expected 12,879,925,248 (12.9 B), got {act:,}"
    assert mod.block_params(mx) - mod.block_params(mx, active=True) == 6 * mod.mlp_params(mx), "six idle experts per block"
    assert mod.count_params(l8, active=True) == mod.count_params(l8), "a dense model has no idle parameters"

    for s in seeds(range(1, 61)):
        cfg = random_config(random.Random(s))
        for active in (False, True):
            got, want = mod.count_params(cfg, active), o_tensors(cfg, active)
            assert got == want, (f"seed {s}: count_params(active={active}) = {got:,} but listing every tensor gives {want:,} for {cfg}")
        tied_less = mod.count_params(cfg) - mod.count_params(Config(**{**cfg.__dict__, "tied": not cfg.tied}))
        assert abs(tied_less) == cfg.V * cfg.C, f"seed {s}: tying or untying the head changes the count by exactly V*C"
        assert mod.count_params(cfg, True) <= mod.count_params(cfg), f"seed {s}: active parameters can never exceed the total"

    lines = []
    for name, c in M.items():
        n = mod.count_params(c)
        q = mod.PUBLISHED[name]
        tol = 0.10 if name == "Chinchilla 70B" else 0.01
        assert rel(n, q) <= tol, f"{name}: counted {n:,}, the published size is about {q:,.0f}; off by {100 * rel(n, q):.1f}%"
        pub = f"{q / 1e6:g}M" if q < 1e9 else f"{q / 1e9:g}B"
        lines.append(f"{name:<15} {n:>16,} counted vs {pub} published ({100 * (n - q) / q:+.1f}%)")
    return "\n".join(lines)


# =============================================================================
# Milestone 2: FLOPs, time and cost
# =============================================================================
def m2():
    assert mod.matmul_flops(2, 3, 4) == 48 and mod.matmul_flops(1, 1, 1) == 2, "2*m*k*n"
    l8, l70, l405 = M["Llama 3 8B"], M["Llama 3 70B"], M["Llama 3 405B"]
    assert mod.matmul_weights(l8) == 7_504_658_432, (f"Llama 3 8B: 32 * (41,943,040 + 176,160,768) + 4096 * 128,256 (the output head, "
                                                    f"counted once) = 7,504,658,432; got {mod.matmul_weights(l8):,}")
    N8 = mod.count_params(l8)
    for T, want in [(2048, 1.001), (8192, 1.202), (131072, 5.213)]:
        got = mod.train_flops_per_token(l8, T) / (6 * N8)
        assert abs(got - want) < 0.002, f"Llama 3 8B at T = {T}: exact FLOPs / 6N should be {want} (chapter 16), got {got:.3f}"
    got = mod.train_flops_per_token(l405, 8192) / (6 * mod.count_params(l405))
    assert abs(got - 1.078) < 0.002, f"Llama 3 405B at T = 8192: exact / 6N should be 1.078, got {got:.3f}"
    got = mod.train_flops_per_token(l8, 4096) - mod.train_flops_per_token(l8, 2048)
    assert got == 12 * 32 * 4096 * 2048, f"each extra context token adds 12*L*C FLOPs per token: expected {12 * 32 * 4096 * 2048:,}, got {got:,}"
    assert mod.train_flops(l8, 1_000_000, 2048) == mod.train_flops_per_token(l8, 2048) * 1_000_000, "FLOPs scale linearly with tokens"
    flops = mod.rule_6nd(mod.count_params(l405), 15.6e12)
    close(flops, 3.80e25, 0.002, "6 N D for Llama 3 405B on 15.6 trillion tokens (the paper reports 3.8e25)")

    H100, A100 = mod.GPUS["H100 SXM"]["peak"], mod.GPUS["A100 80GB"]["peak"]
    days = mod.train_seconds(flops, H100, 0.40, 16384) / 86400
    assert abs(days - 67.8) < 0.2, f"405B on 16,384 H100s at 40% MFU should take about 67.8 days, got {days:.1f}"
    gh = mod.gpu_hours(flops, H100, 0.40)
    close(gh, 26_673_660, 0.002, "GPU-hours for the 405B run at 40% MFU")
    assert near_eq(mod.train_seconds(flops, H100, 0.40, 1000) * 1000 / 3600, gh), "GPU-hours must not depend on how many GPUs share the work"
    gh2 = mod.gpu_hours(mod.rule_6nd(124e6, 10e9), A100, 0.40)
    close(gh2, 16.56, 0.005, "GPT-2 small on 10 billion tokens, one A100 at 40% MFU (about 17 GPU-hours)")
    assert abs(mod.train_seconds(1e18, 1e15, 0.5) - 2000) < 1e-9, "1e18 FLOPs at 0.5 * 1e15 FLOP/s is 2,000 s"
    assert abs(mod.mfu_from_throughput(400e12, 989e12) - 0.4044) < 1e-3, "400 of 989 TFLOP/s is an MFU of 0.404"
    assert abs(mod.train_seconds(1e18, 1e15, 0.5, 4) - 500) < 1e-9, "four GPUs quarter the time"

    for s in seeds(range(1, 41)):
        cfg = random_config(random.Random(s), experts=1, top_k=1, bias=False, tied=False, norm="rms", positions=0)
        want = mod.count_params(cfg, True) - cfg.L * 2 * cfg.C - cfg.C - cfg.V * cfg.C        # drop norms and the input lookup
        assert mod.matmul_weights(cfg) == want, (f"seed {s}: matmul_weights = {mod.matmul_weights(cfg):,} but 'active parameters minus norms "
                                                 f"minus the input lookup' = {want:,}")
    mx = M["Mixtral 8x7B"]
    assert mod.matmul_weights(mx) < 0.3 * mod.count_params(mx), "a mixture of experts multiplies by far fewer weights than it stores"
    r = mod.train_flops_per_token(mx, 2048) / (6 * mod.count_params(mx))
    r_dense = mod.train_flops_per_token(M["Llama 3 8B"], 2048) / (6 * mod.count_params(M["Llama 3 8B"]))
    return (f"405B: 6ND = {flops:.2e} FLOPs, {days:.1f} days on 16,384 H100s at 40% MFU, {gh / 1e6:.1f}M GPU-hours\n"
            f"Mixtral 8x7B trains at {r:.2f} x (6 x total params) per token because only 2 of 8 experts run; a dense 8B model: {r_dense:.2f}")


def near_eq(a, b, tol=1e-9):
    return abs(a - b) <= tol * max(1.0, abs(b))


# =============================================================================
# Milestone 3: memory for training
# =============================================================================
def m3():
    assert mod.state_bytes(1) == 16, "2 + 2 + 4 + 4 + 4 = 16 bytes per parameter"
    assert mod.state_bytes(10, m=1, v=1) == 100, "8-bit Adam moments: 2 + 2 + 4 + 1 + 1 = 10 bytes per parameter"
    assert mod.state_bytes(3e9) == 48e9, "a 3 B model needs 48 GB of state (chapter 16 quiz)"
    assert mod.act_bytes_per_layer(2, 1, 4, 2, "full") == 312, "s=2, b=1, h=4, a=2: 8 * (34 + 5*2*2/4) = 312"
    assert mod.act_bytes_per_layer(2, 1, 4, 2, "flash") == 272, "flash drops the 5*a*s/h term: 8 * 34 = 272"
    assert mod.act_bytes_per_layer(2, 1, 4, 2, "recompute") == 16, "recompute keeps only the layer input: 2*s*b*h = 16"
    try:
        mod.act_bytes_per_layer(2, 1, 4, 2, "mystery")
    except ValueError:
        pass
    else:
        raise AssertionError("an unknown mode must raise ValueError")
    l8 = M["Llama 3 8B"]
    st = mod.state_bytes(mod.count_params(l8))
    close(st / GB, 128.5, 0.001, "Llama 3 8B training states in GB")
    for s, full, flash, rec in [(2048, 30.6, 9.1, 0.54), (4096, 104.2, 18.3, 1.07), (8192, 380.1, 36.5, 2.15), (16384, 1447.4, 73.0, 4.29)]:
        for mode, want in (("full", full), ("flash", flash), ("recompute", rec)):
            got = mod.activation_bytes(l8, s, 1, mode) / GB
            close(got, want, 0.01, f"Llama 3 8B activations, s = {s}, mode {mode}, in GB (chapter 16 table)")
    tm = mod.training_memory(l8, 4096, 1, "full")
    assert set(tm) == {"states", "activations", "total"} and tm["total"] == tm["states"] + tm["activations"], "keys states, activations, total"
    assert near_eq(mod.training_memory(l8, 4096, 4, "full")["activations"], 4 * tm["activations"]), "activations are proportional to the microbatch"
    a1, a2 = (mod.activation_bytes(l8, s, 1, "full") - mod.activation_bytes(l8, s, 1, "flash") for s in (2048, 4096))
    assert near_eq(a2, 4 * a1), "the score-table term is quadratic in sequence length: doubling s quadruples it"
    assert mod.fits(77e9, 80e9) and not mod.fits(78e9, 80e9), "overhead defaults to 3 GB: 77 + 3 fits an 80 GB card, 78 + 3 does not"
    assert mod.fits(78e9, 80e9, overhead=1e9), "overhead is a parameter"
    close(mod.max_trainable_params(80e9), 4.8125e9, 1e-9, "(80 GB - 3 GB) / 16 bytes")

    small = Config("1B-class", C=2048, L=20, H=16, KV=16, F=8192, V=32000, mlp="gelu", tied=True)
    n_small = mod.count_params(small)
    for mode in ("full", "flash", "recompute"):
        want, b = 0, 1
        while mod.state_bytes(n_small) + sum([small.L * mod.act_bytes_per_layer(2048, b, small.C, small.H, mode)]) + 3 * GB <= 24 * GB and b < 4096:
            want, b = b, b + 1
        got = mod.max_microbatch(small, 2048, mode, 24 * GB)
        assert got == want, (f"1B-class model ({n_small / 1e9:.2f} B parameters), 2,048 tokens, mode {mode}, 24 GB card: "
                             f"the largest microbatch that fits is {want}, got {got}")
    assert mod.max_microbatch(l8, 2048, "recompute", 80 * GB) == 0, "the 8B model's 128.5 GB of states do not fit an 80 GB card at all"
    b_full, b_flash, b_rec = (mod.max_microbatch(small, 2048, m, 24 * GB) for m in ("full", "flash", "recompute"))
    assert b_full <= b_flash <= b_rec, "cheaper activation modes can only allow bigger microbatches"
    rows = []
    for name in ("Llama 3 8B", "Llama 3 70B"):
        c = M[name]
        rows.append(f"{name}: states {mod.state_bytes(mod.count_params(c)) / GB:,.0f} GB; largest card here is 80 GB, so it must be sharded")
    return (f"1B-class model on a 24 GB card at 2,048 tokens: largest microbatch {b_full} (keep all), {b_flash} (fused attention), {b_rec} (recompute)\n"
            + "\n".join(rows))


# =============================================================================
# Milestone 4: inference, the KV cache and the bandwidth limit
# =============================================================================
def m4():
    l8, l2, l70 = M["Llama 3 8B"], M["Llama 2 7B"], M["Llama 3 70B"]
    assert mod.kv_bytes_per_token(l8) == 131_072, f"Llama 3 8B: 2 * 32 * 8 * 128 * 2 bytes = 131,072, got {mod.kv_bytes_per_token(l8):,}"
    assert mod.kv_bytes_per_token(l2) == 524_288, f"Llama 2 7B has 32 key/value heads: 524,288 bytes per token, got {mod.kv_bytes_per_token(l2):,}"
    assert mod.kv_bytes_per_token(l8, 1) == 65_536, "an 8-bit cache halves it"
    assert mod.kv_cache_bytes(l8, 8192) == 131_072 * 8192 and mod.kv_cache_bytes(l8, 100, 3) == 131_072 * 300, "tokens x batch x bytes per token"
    close(mod.kv_cache_bytes(l8, 8192) / GB, 1.07, 0.005, "one 8,192-token conversation, Llama 3 8B")
    assert mod.weight_bytes(l8) == 2 * mod.count_params(l8) and mod.weight_bytes(l8, 0.5) == 0.5 * mod.count_params(l8), "bytes per parameter"
    mx = M["Mixtral 8x7B"]
    assert mod.weight_bytes(mx) == 2 * mod.count_params(mx), "all eight experts stay in memory even though two run"
    assert mod.max_batch(l8, 8192, 80 * GB) == 56, f"80 GB card, bf16 8B model, 8,192-token sequences: (80 - 3 - 16.06) GB / 1.07 GB = 56; got {mod.max_batch(l8, 8192, 80 * GB)}"
    assert mod.max_batch(l70, 8192, 80 * GB) == 0, "70B in bf16 is 141 GB: it does not fit one 80 GB card"
    assert mod.max_batch(l8, 8192, 80 * GB, w_bytes=0.5) > mod.max_batch(l8, 8192, 80 * GB), "4-bit weights leave more room for caches"

    bw, pk = mod.GPUS["H100 SXM"]["bw"], mod.GPUS["H100 SXM"]["peak"]
    t = mod.decode_tokens_per_second(l8, 0, 1, bw, pk)
    close(t, 208.6, 0.002, "Llama 3 8B, bf16, batch 1, empty context, H100 (chapter 16: at most 209 tokens/s)")
    t2 = mod.decode_tokens_per_second(l8, 8192, 1, bw, pk)
    close(t2, 195.5, 0.005, "the same at an 8,192-token context: the cache adds 1.07 GB to read per token")
    t4 = mod.decode_tokens_per_second(l8, 0, 1, bw, pk, w_bytes=0.5)
    close(t4, 4 * t, 0.001, "4-bit weights read a quarter of the bytes")
    big = mod.decode_tokens_per_second(l8, 0, 4096, bw, pk)
    close(big, pk / (2 * mod.matmul_weights(l8)), 0.001, "with a huge batch decoding is compute-bound: peak / (2 FLOPs per weight)")
    rb = mod.ridge_batch(l8, bw, pk)
    close(rb, 315.9, 0.005, "ridge batch for Llama 3 8B on an H100")
    prev = 0
    for b in (1, 2, 4, 8, 16, 64, 256, 1024):
        cur = mod.decode_tokens_per_second(l8, 2048, b, bw, pk)
        assert cur >= prev - 1e-9, f"batching can only raise throughput; batch {b} gave {cur:.0f} after {prev:.0f}"
        prev = cur
    s1 = mod.decode_step_seconds(l8, 0, 8, bw, pk)
    s2 = mod.decode_step_seconds(l8, 0, 64, bw, pk)
    assert near_eq(s1, 16.06e9 / bw, 2e-3) and near_eq(s2, s1, 1e-9), "below the ridge the step time does not depend on the batch (weights are read once)"
    assert mod.decode_step_seconds(l8, 8192, 8, bw, pk) > s1, "a longer context means more cache to read"
    top = mod.max_batch(l8, 2048, 80 * GB)
    assert top == 227, f"80 GB card, 2,048-token sequences: (80 - 3 - 16.06) GB / 0.268 GB = 227; got {top}"
    rows = ["batch  tokens/s   per user"]
    for b in (1, 8, 64, top):
        tot = mod.decode_tokens_per_second(l8, 2048, b, bw, pk)
        rows.append(f"{b:5d} {tot:9,.0f} {tot / b:10.1f}")
    assert mod.decode_step_seconds(l8, 2048, top, bw, pk) * bw > mod.weight_bytes(l8), "the cache keeps it memory-bound"
    return ("Llama 3 8B on one 80 GB H100, bf16 weights, 2,048-token contexts\n" + "\n".join(rows)
            + f"\nthe ridge batch is {rb:.0f}, but only {top} sequences fit, so memory capacity caps batching before compute does")


# =============================================================================
# Milestone 5: compute-optimal sizes
# =============================================================================
def m5():
    E, A, B, a, b = BES
    N, D = 7e9, 1.4e11
    assert near_eq(mod.loss(N, D, BES), E + A / N ** a + B / D ** b), "L = E + A/N^alpha + B/D^beta"
    N, D, L = mod.optimum(5.76e23, BES)
    close(N, 7.225e10, 0.001, "compute-optimal N at Gopher's 5.76e23 FLOPs (Besiroglu refit)")
    close(D, 1.329e12, 0.001, "compute-optimal D at 5.76e23 FLOPs")
    assert near_eq(6 * N * D, 5.76e23, 1e-9) and near_eq(L, mod.loss(N, D, BES)), "the optimum must spend exactly the budget and report its own loss"
    N, D, L = mod.optimum(1e19, HOF)
    close(N, 2.280e8, 0.002, "Hoffmann printed constants, 1e19 FLOPs: N")
    close(D / N, 32.1, 0.005, "Hoffmann printed constants, 1e19 FLOPs: tokens per parameter")
    n, d = mod.chinchilla_rule(6e23)
    close(n, 7.071e10, 0.001, "the 20-tokens-per-parameter rule at 6e23 FLOPs: N")
    assert near_eq(d / n, 20) and near_eq(6 * n * d, 6e23), "D = 20 N and 6ND = C"
    n3, d3 = mod.chinchilla_rule(1e22, ratio=40)
    assert near_eq(d3 / n3, 40) and near_eq(6 * n3 * d3, 1e22), "the ratio is a parameter"
    assert near_eq(mod.isoflop_loss(1e22, 9.045e9, BES), mod.optimum(1e22, BES)[2], 2e-4), "near the optimum the IsoFLOP loss equals the optimum"
    for f, want in [(0.25, 0.0400), (0.5, 0.0099), (1.0, 0.0), (2.0, 0.0099), (4.0, 0.0408), (8.0, 0.0949)]:
        got = mod.excess_loss(1e22, f, BES)
        assert abs(got - want) < 0.0006, f"{f} x the optimal size at 1e22 FLOPs should cost about {want:.4f} nats (chapter 18), got {got:.4f}"
    assert abs(mod.excess_loss(1e22, 1.0, BES)) < 1e-9, "the optimum costs nothing extra"

    for s in seeds(range(1, 31)):
        rng = random.Random(s)
        fit = (rng.uniform(1, 2), rng.uniform(100, 600), rng.uniform(100, 3000), rng.uniform(0.25, 0.6), rng.uniform(0.25, 0.6))
        C = 10 ** rng.uniform(18, 25)
        N, D, L = mod.optimum(C, fit)
        assert near_eq(6 * N * D, C, 1e-9), f"seed {s}: 6ND must equal C"
        for f in (0.5, 0.8, 0.95, 1.05, 1.25, 2.0):
            other = mod.isoflop_loss(C, f * N, fit)
            assert other >= L - 1e-12, f"seed {s}: a model {f}x the 'optimal' size has lower loss ({other:.5f} < {L:.5f}); the optimum formula is off"
    return ("Besiroglu refit at Gopher's budget (5.76e23 FLOPs): N = 72 B, D = 1.33 T, tokens per parameter 18.4\n"
            "at 1e22 FLOPs a model half or twice the optimal size costs about 0.01 nats; four times, about 0.04")


# =============================================================================
# Milestone 6: lifetime cost and over-training
# =============================================================================
def m6():
    assert near_eq(mod.lifetime_flops(70e9, 1.4e12, 0), 5.88e23), "with no serving it is 6ND"
    assert near_eq(mod.lifetime_flops(70e9, 1.4e12, 1e13), 5.88e23 + 2 * 70e9 * 1e13), "plus 2N per served token"
    target = mod.loss(70e9, 1.4e12, BES)
    assert mod.tokens_for_loss(1e9, 1.9, BES) is None, "a 1 B model cannot reach loss 1.9 on this fit with any amount of data"
    for N in (3e10, 7e10, 2e11):
        D = mod.tokens_for_loss(N, target, BES)
        assert abs(mod.loss(N, D, BES) - target) < 1e-9, f"N = {N:g}: tokens_for_loss must invert loss(), got D = {D:g}"
    n0, d0, f0 = mod.best_size_for_loss(target, 0, BES)
    No, Do, Lo = mod.optimum(6 * n0 * d0, BES)
    close(n0, No, 0.002, "with no serving, the cheapest way to reach a loss is the compute-optimal model for the budget it costs")
    close(f0, 6 * n0 * d0, 1e-9, "with no serving the lifetime cost is 6ND")
    assert abs(mod.loss(n0, d0, BES) - target) < 1e-6, "the answer must actually reach the target loss"
    prev_n, prev_ratio = n0, d0 / n0
    for I in (1e12, 1e13, 1e14, 1e15):
        n, d, f = mod.best_size_for_loss(target, I, BES)
        assert abs(mod.loss(n, d, BES) - target) < 1e-6, f"I = {I:g}: the answer must reach the target loss"
        assert near_eq(f, mod.lifetime_flops(n, d, I)), "the third value is the lifetime cost"
        assert n < prev_n and d / n > prev_ratio, f"I = {I:g}: more serving should shrink the model ({n:.3g} vs {prev_n:.3g}) and raise tokens per parameter"
        assert f <= mod.lifetime_flops(n0, d0, I) * (1 + 1e-9), f"I = {I:g}: the best plan can never cost more than the compute-optimal model's lifetime cost"
        prev_n, prev_ratio = n, d / n
    for s in seeds(range(1, 11)):
        rng = random.Random(s)
        fit = (rng.uniform(1.5, 2), rng.uniform(200, 600), rng.uniform(500, 3000), rng.uniform(0.3, 0.45), rng.uniform(0.3, 0.45))
        tgt = fit[0] + rng.uniform(0.15, 0.5)
        I = 10 ** rng.uniform(11, 14)
        n, d, f = mod.best_size_for_loss(tgt, I, fit)
        for k in (0.7, 0.9, 1.1, 1.4):
            D2 = mod.tokens_for_loss(n * k, tgt, fit)
            if D2 is not None:
                assert mod.lifetime_flops(n * k, D2, I) >= f * (1 - 1e-6), f"seed {s}: a model {k}x the size you returned is cheaper, so the search did not find the minimum"
    n, d, f = mod.best_size_for_loss(target, 1e13, BES)
    save = 1 - f / mod.lifetime_flops(n0, d0, 1e13)
    return (f"target loss {target:.3f} (the fit's value for Chinchilla); with no serving the cheapest model is {n0 / 1e9:.0f} B parameters on {d0 / 1e12:.2f} T tokens\n"
            f"serving 1e13 tokens: {n / 1e9:.0f} B parameters on {d / 1e12:.2f} T tokens ({d / n:.0f} tokens per parameter) saves {100 * save:.0f}% of lifetime FLOPs")


t0 = time.time()
check(1, "Milestone 1: counting parameters", m1)
check(2, "Milestone 2: FLOPs, time and cost", m2)
check(3, "Milestone 3: memory for training", m3)
check(4, "Milestone 4: the KV cache and the bandwidth limit", m4)
check(5, "Milestone 5: compute-optimal sizes", m5)
check(6, "Milestone 6: lifetime cost and over-training", m6)
print(f"\n{sum(results)}/{len(results)} milestones passing  ({time.time() - t0:.1f} s)")
