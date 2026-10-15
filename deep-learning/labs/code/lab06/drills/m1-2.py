# Drill: A2 Lab 6, milestone 1 of 6: counting parameters (step 2 of 7)
# Everything else in this file is already written. Fill in:
#     attn_params
# Check it with: python3 check.py 1

"""Lab 6 reference solution: the model resource calculator.

Notation follows chapters 16 and 18: C is the model width (d_model), L the number of layers, H the
number of query heads, KV the number of key/value heads, d_k = C/H the head width, F the MLP hidden
width, V the vocabulary, N the parameter count, D the number of training tokens, T the sequence
length, b the microbatch. FLOPs (small s) counts work; FLOP/s is speed. 1 GB = 10^9 bytes.
"""
import math
from dataclasses import dataclass

GB = 1e9


# =============================================================================
# Given: the shape of a model, a small zoo of published shapes, and some GPU numbers
# =============================================================================
@dataclass(frozen=True)
class Config:
    """The shape of a decoder-only Transformer. Everything in this lab is a function of it."""
    name: str
    C: int                      # model width, d_model
    L: int                      # layers
    H: int                      # query heads
    KV: int                     # key/value heads (KV == H is ordinary multi-head attention)
    F: int                      # MLP hidden width (per expert)
    V: int                      # vocabulary size
    mlp: str = "swiglu"         # "swiglu": gate, up, down matrices; "gelu": up and down matrices
    norm: str = "rms"           # "rms": one gain vector (C); "layer": gain and bias (2C)
    bias: bool = False          # biases on the projections and the MLP (GPT-2 style)
    tied: bool = False          # True: the output head reuses the input embedding table
    positions: int = 0          # rows of a learned position table (0 for rotary or no table)
    experts: int = 1            # experts per MLP (1 = dense)
    top_k: int = 1              # experts used per token


MODELS = {c.name: c for c in [
    # GPT-2 small: Radford et al. 2019 / the released config (n_embd 768, 12 layers, 12 heads, 1024 positions)
    Config("GPT-2 small", C=768, L=12, H=12, KV=12, F=3072, V=50257, mlp="gelu", norm="layer", bias=True, tied=True, positions=1024),
    # GPT-3 175B: Brown et al. 2020, Table 2.1 (96 layers, d_model 12288, 96 heads, d_ff = 4 d_model, context 2048)
    Config("GPT-3 175B", C=12288, L=96, H=96, KV=96, F=49152, V=50257, mlp="gelu", norm="layer", bias=True, tied=True, positions=2048),
    # Llama 2 7B: released config
    Config("Llama 2 7B", C=4096, L=32, H=32, KV=32, F=11008, V=32000),
    # Llama 3: Table 3 of the Llama 3 paper; V = 128,256 in the released config
    Config("Llama 3 8B", C=4096, L=32, H=32, KV=8, F=14336, V=128256),
    Config("Llama 3 70B", C=8192, L=80, H=64, KV=8, F=28672, V=128256),
    Config("Llama 3 405B", C=16384, L=126, H=128, KV=8, F=53248, V=128256),
    # Mixtral 8x7B: released config (8 experts, 2 used per token)
    Config("Mixtral 8x7B", C=4096, L=32, H=32, KV=8, F=14336, V=32000, experts=8, top_k=2),
    # Chinchilla 70B: Table 4 of Hoffmann et al. 2022 (80 layers, 64 heads, d_model 8192, d_ff = 4 d_model)
    Config("Chinchilla 70B", C=8192, L=80, H=64, KV=64, F=32768, V=32000, mlp="gelu", norm="layer"),
]}

# The sizes the model cards and papers quote (rounded, as published). Not all are exact; see the lab page.
PUBLISHED = {"GPT-2 small": 124e6, "GPT-3 175B": 175e9, "Llama 2 7B": 6.7e9, "Llama 3 8B": 8e9,
             "Llama 3 70B": 70e9, "Llama 3 405B": 405e9, "Mixtral 8x7B": 46.7e9, "Chinchilla 70B": 70e9}

# Dense bf16 peak FLOP/s, memory bytes and memory bandwidth (bytes/s) from vendor datasheets (dated: chapter 16).
GPUS = {
    "A100 40GB": dict(peak=312e12, mem=40 * GB, bw=1.555e12),
    "A100 80GB": dict(peak=312e12, mem=80 * GB, bw=2.039e12),
    "H100 SXM": dict(peak=989e12, mem=80 * GB, bw=3.35e12),
    "24 GB card": dict(peak=None, mem=24 * GB, bw=None),
}

# Fitted loss laws L(N, D) = E + A / N^alpha + B / D^beta (chapter 18). Tuples are (E, A, B, alpha, beta).
FITS = {"Hoffmann et al. 2022 (as printed)": (1.69, 406.4, 410.7, 0.34, 0.28),
        "Besiroglu et al. 2024 (replication)": (1.8172, 482.01, 2085.43, 0.3478, 0.3658)}
BESIROGLU = FITS["Besiroglu et al. 2024 (replication)"]


# =============================================================================
# Milestone 1: counting parameters
# =============================================================================
def head_dim(cfg):
    """d_k = C / H."""
    return cfg.C // cfg.H


def attn_params(cfg):
    """Attention weights of ONE layer: W_q (C x C), W_k and W_v (C x KV*d_k each), W_o (C x C).

    With grouped-query attention KV < H, so K and V are narrower than Q. If cfg.bias, add the bias
    vectors: C for W_q, KV*d_k for each of W_k and W_v, C for W_o.
    Llama 3 8B: 2*4096^2 + 2*4096*(8*128) = 41,943,040
    """
    raise NotImplementedError("TODO milestone 1: attn_params")


def mlp_params(cfg):
    """ONE expert's MLP: 3 matrices for SwiGLU, 2 for GELU, plus biases if cfg.bias."""
    mats = 3 if cfg.mlp == "swiglu" else 2
    n = mats * cfg.C * cfg.F
    if cfg.bias:
        n += (mats - 1) * cfg.F + cfg.C            # hidden-layer biases, then the output bias
    return n


def norm_params(cfg):
    """The two normalisations in one block."""
    per = cfg.C if cfg.norm == "rms" else 2 * cfg.C
    return 2 * per


def block_params(cfg, active=False):
    """One layer: attention + MLP(s) + router + norms. active=True counts only top_k experts."""
    n_exp = cfg.top_k if active else cfg.experts
    router = cfg.C * cfg.experts if cfg.experts > 1 else 0
    return attn_params(cfg) + n_exp * mlp_params(cfg) + router + norm_params(cfg)


def embedding_params(cfg):
    """Input table V*C, a separate output head V*C unless tied, and a learned position table."""
    return cfg.V * cfg.C * (1 if cfg.tied else 2) + cfg.positions * cfg.C


def count_params(cfg, active=False):
    """All parameters: L blocks + embeddings + the final norm. active=True: per-token (MoE) count."""
    final_norm = cfg.C if cfg.norm == "rms" else 2 * cfg.C
    return cfg.L * block_params(cfg, active) + embedding_params(cfg) + final_norm


# =============================================================================
# Milestone 2: FLOPs, time and cost
# =============================================================================
def matmul_flops(m, k, n):
    """Multiplying an (m, k) matrix by a (k, n) matrix: m*n outputs, k multiplies and k adds each."""
    return 2 * m * k * n


def matmul_weights(cfg):
    """Weights that take part in a matrix product for one token: attention matrices, the MLP matrices of
    the top_k active experts, the router, and the output head. Norms, biases and the input lookup excluded."""
    kv_width = cfg.KV * head_dim(cfg)
    attn = 2 * cfg.C * cfg.C + 2 * cfg.C * kv_width
    mats = 3 if cfg.mlp == "swiglu" else 2
    mlp = cfg.top_k * mats * cfg.C * cfg.F
    router = cfg.C * cfg.experts if cfg.experts > 1 else 0
    return cfg.L * (attn + mlp + router) + cfg.C * cfg.V


def train_flops_per_token(cfg, T):
    """6 FLOPs per matmul weight, plus 12*L*C*T for the QK^T and (weights)V products (chapter 16)."""
    return 6 * matmul_weights(cfg) + 12 * cfg.L * cfg.C * T


def rule_6nd(N, D):
    """The rule of thumb: 6 * N * D."""
    return 6 * N * D


def train_flops(cfg, tokens, T):
    """Exact-count training FLOPs for `tokens` tokens at sequence length T."""
    return train_flops_per_token(cfg, T) * tokens


def train_seconds(flops, peak, mfu, n_gpus=1):
    """Wall-clock seconds: FLOPs / (peak FLOP/s per GPU * MFU * number of GPUs)."""
    return flops / (peak * mfu * n_gpus)


def gpu_hours(flops, peak, mfu):
    """GPU-hours (independent of how many GPUs share the work)."""
    return flops / (peak * mfu) / 3600


def mfu_from_throughput(model_flops_per_s_per_gpu, peak):
    """Model FLOPs utilisation: achieved model FLOP/s over the datasheet peak."""
    return model_flops_per_s_per_gpu / peak


# =============================================================================
# Milestone 3: memory for training
# =============================================================================
def state_bytes(n, weights=2, grads=2, master=4, m=4, v=4):
    """Bytes of model state: bf16 weights and gradients, fp32 master copy and Adam's two moments."""
    return n * (weights + grads + master + m + v)


def act_bytes_per_layer(s, b, h, a, mode="full"):
    """Korthikanti et al. activations for one layer, 16-bit: 'full' s*b*h*(34 + 5*a*s/h),
    'flash' s*b*h*34 (no stored score matrices), 'recompute' 2*s*b*h (only the layer input)."""
    if mode == "full":
        return s * b * h * (34 + 5 * a * s / h)
    if mode == "flash":
        return s * b * h * 34
    if mode == "recompute":
        return 2 * s * b * h
    raise ValueError(f"unknown activation mode {mode!r}")


def activation_bytes(cfg, s, b, mode="full"):
    """Activations of the whole stack: L layers (width cfg.C, cfg.H heads)."""
    return cfg.L * act_bytes_per_layer(s, b, cfg.C, cfg.H, mode)


def training_memory(cfg, s, b, mode="full"):
    """{'states': ..., 'activations': ..., 'total': ...} in bytes, using 16 bytes per parameter."""
    states = state_bytes(count_params(cfg))
    acts = activation_bytes(cfg, s, b, mode)
    return {"states": states, "activations": acts, "total": states + acts}


def fits(total_bytes, gpu_mem, overhead=3 * GB):
    """True if the total plus a fixed allowance for the CUDA context and fragmentation fits the card."""
    return total_bytes + overhead <= gpu_mem


def max_microbatch(cfg, s, mode, gpu_mem, overhead=3 * GB):
    """The largest microbatch b that fits on one card (0 if even b = 1 does not)."""
    b = 0
    while fits(training_memory(cfg, s, b + 1, mode)["total"], gpu_mem, overhead):
        b += 1
        if b >= 4096:
            break
    return b


def max_trainable_params(gpu_mem, overhead=3 * GB):
    """The most parameters whose 16-bytes-each states fit the card, with nothing left for activations."""
    return (gpu_mem - overhead) / 16


# =============================================================================
# Milestone 4: inference, the KV cache and the bandwidth limit
# =============================================================================
def kv_bytes_per_token(cfg, bytes_per=2):
    """Keys and values of one token in every layer: 2 * L * KV * d_k * bytes."""
    return 2 * cfg.L * cfg.KV * head_dim(cfg) * bytes_per


def kv_cache_bytes(cfg, ctx, batch=1, bytes_per=2):
    """The cache of `batch` sequences, each `ctx` tokens long."""
    return kv_bytes_per_token(cfg, bytes_per) * ctx * batch


def weight_bytes(cfg, bytes_per=2):
    """All parameters at `bytes_per` each (a mixture of experts keeps every expert in memory)."""
    return count_params(cfg) * bytes_per


def max_batch(cfg, ctx, gpu_mem, w_bytes=2, kv_bytes=2, overhead=3 * GB):
    """How many sequences of length ctx fit next to the weights (0 if the weights alone do not fit)."""
    free = gpu_mem - overhead - weight_bytes(cfg, w_bytes)
    per_seq = kv_cache_bytes(cfg, ctx, 1, kv_bytes)
    return max(0, int(free // per_seq))


def decode_step_seconds(cfg, ctx, batch, bw, peak, w_bytes=2, kv_bytes=2):
    """One decode step for `batch` sequences at context ctx: the slower of reading the bytes
    (weights once, plus every sequence's cache) and doing the FLOPs (2 per weight, 4*L*C*ctx for attention)."""
    mem_time = (weight_bytes(cfg, w_bytes) + kv_cache_bytes(cfg, ctx, batch, kv_bytes)) / bw
    flop_time = batch * (2 * matmul_weights(cfg) + 4 * cfg.L * cfg.C * ctx) / peak
    return max(mem_time, flop_time)


def decode_tokens_per_second(cfg, ctx, batch, bw, peak, w_bytes=2, kv_bytes=2):
    """Tokens per second summed over the batch."""
    return batch / decode_step_seconds(cfg, ctx, batch, bw, peak, w_bytes, kv_bytes)


def ridge_batch(cfg, bw, peak, w_bytes=2):
    """The batch size at which weights-only decoding stops being memory-bound:
    batch * 2 * W / peak == bytes / bw  ->  batch = peak * bytes / (2 * W * bw)."""
    return peak * weight_bytes(cfg, w_bytes) / (2 * matmul_weights(cfg) * bw)


# =============================================================================
# Milestone 5: compute-optimal sizes
# =============================================================================
def loss(N, D, fit):
    """L(N, D) = E + A / N^alpha + B / D^beta."""
    E, A, B, a, b = fit
    return E + A / N ** a + B / D ** b


def optimum(C, fit):
    """The (N, D, loss) minimising L(N, D) subject to 6*N*D = C (closed form, chapter 18)."""
    E, A, B, a, b = fit
    G = (a * A / (b * B)) ** (1 / (a + b))
    N = G * (C / 6) ** (b / (a + b))
    D = C / (6 * N)
    return N, D, loss(N, D, fit)


def chinchilla_rule(C, ratio=20):
    """The rule of thumb D = ratio * N with C = 6*N*D: returns (N, D)."""
    N = math.sqrt(C / (6 * ratio))
    return N, ratio * N


def isoflop_loss(C, N, fit):
    """Loss of a model with N parameters trained to use exactly C FLOPs (D = C / 6N)."""
    return loss(N, C / (6 * N), fit)


def excess_loss(C, factor, fit):
    """How much worse than the optimum a model `factor` times the optimal size is, at the same budget."""
    N_opt = optimum(C, fit)[0]
    return isoflop_loss(C, factor * N_opt, fit) - optimum(C, fit)[2]


# =============================================================================
# Milestone 6: lifetime cost and over-training
# =============================================================================
def lifetime_flops(N, D, inference_tokens):
    """Training 6*N*D plus serving 2*N FLOPs for each token generated."""
    return 6 * N * D + 2 * N * inference_tokens


def tokens_for_loss(N, target, fit):
    """The D that makes L(N, D) == target, or None if N is too small to reach it at any D."""
    E, A, B, a, b = fit
    room = target - E - A / N ** a
    if room <= 0:
        return None
    return (B / room) ** (1 / b)


def best_size_for_loss(target, inference_tokens, fit):
    """The (N, D, lifetime FLOPs) reaching `target` loss at the least total cost of training plus serving.

    For each N the data D is fixed by the target (tokens_for_loss); lifetime_flops is then a function of
    N alone that falls and rises, so a ternary search over log N finds its minimum.
    """
    E, A, B, a, b = fit
    n_min = (A / (target - E)) ** (1 / a)           # below this no amount of data reaches the target
    lo, hi = math.log(n_min * (1 + 1e-9)), math.log(n_min * 1e4)

    def cost(logn):
        N = math.exp(logn)
        return lifetime_flops(N, tokens_for_loss(N, target, fit), inference_tokens)

    for _ in range(200):
        m1, m2 = lo + (hi - lo) / 3, hi - (hi - lo) / 3
        if cost(m1) < cost(m2):
            hi = m2
        else:
            lo = m1
    N = math.exp((lo + hi) / 2)
    D = tokens_for_loss(N, target, fit)
    return N, D, lifetime_flops(N, D, inference_tokens)
