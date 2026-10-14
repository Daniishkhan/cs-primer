"""Lab 6 starter: the model resource calculator.

Write the functions marked TODO, one milestone at a time, and run `python3 check.py` after each.

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
    """d_k = C / H, the width of one attention head.   head_dim(Llama 3 8B) -> 128"""
    raise NotImplementedError("TODO milestone 1: head_dim")


def attn_params(cfg):
    """Attention weights of ONE layer: W_q (C x C), W_k and W_v (C x KV*d_k each), W_o (C x C).

    With grouped-query attention KV < H, so K and V are narrower than Q. If cfg.bias, add the bias
    vectors: C for W_q, KV*d_k for each of W_k and W_v, C for W_o.
    Llama 3 8B: 2*4096^2 + 2*4096*(8*128) = 41,943,040
    """
    raise NotImplementedError("TODO milestone 1: attn_params")


def mlp_params(cfg):
    """MLP weights of ONE expert in one layer.

    cfg.mlp == "swiglu": three C x F matrices (gate, up, down).  "gelu": two (up, down).
    If cfg.bias: add a bias of F for every matrix that feeds the hidden layer (1 for gelu, 2 for
    swiglu) and one of C for the output matrix.   Llama 3 8B: 3*4096*14336 = 176,160,768
    """
    raise NotImplementedError("TODO milestone 1: mlp_params")


def norm_params(cfg):
    """The two normalisations in one block: each has C weights ("rms") or 2C ("layer": gain and bias)."""
    raise NotImplementedError("TODO milestone 1: norm_params")


def block_params(cfg, active=False):
    """One layer: attention + MLP + norms (+ the router C x experts if cfg.experts > 1).

    The MLP part is experts * mlp_params(cfg), or top_k * mlp_params(cfg) when active=True: a
    mixture of experts stores every expert but each token only uses top_k of them.
    """
    raise NotImplementedError("TODO milestone 1: block_params")


def embedding_params(cfg):
    """Input table V*C, plus a separate output head V*C unless cfg.tied, plus positions*C for a learned position table."""
    raise NotImplementedError("TODO milestone 1: embedding_params")


def count_params(cfg, active=False):
    """Every parameter: L blocks + embeddings + the final norm (C for "rms", 2C for "layer").

    Must reproduce the published sizes: GPT-2 small 124,439,808; Llama 3 8B 8,030,261,248.
    active=True gives the per-token count of a mixture of experts (Mixtral: about 12.9 billion).
    """
    raise NotImplementedError("TODO milestone 1: count_params")


# =============================================================================
# Milestone 2: FLOPs, time and cost
# =============================================================================
def matmul_flops(m, k, n):
    """FLOPs of an (m, k) by (k, n) matrix product: 2*m*k*n.   matmul_flops(2, 3, 4) -> 48"""
    raise NotImplementedError("TODO milestone 2: matmul_flops")


def matmul_weights(cfg):
    """The weights one token multiplies by (chapter 16's `weights`): per layer the four attention
    matrices, top_k experts' MLP matrices and the router; then the output head C*V once.

    Norms and biases are not matrix products and the input embedding is a lookup, so none counts.
    """
    raise NotImplementedError("TODO milestone 2: matmul_weights")


def train_flops_per_token(cfg, T):
    """6 * matmul_weights(cfg) + 12 * L * C * T: the weights term plus the attention-score term.

    Llama 3 8B at T = 8192 is 1.202 times 6N (chapter 16).
    """
    raise NotImplementedError("TODO milestone 2: train_flops_per_token")


def rule_6nd(N, D):
    """The rule of thumb: 6 * N * D."""
    raise NotImplementedError("TODO milestone 2: rule_6nd")


def train_flops(cfg, tokens, T):
    """train_flops_per_token(cfg, T) * tokens."""
    raise NotImplementedError("TODO milestone 2: train_flops")


def train_seconds(flops, peak, mfu, n_gpus=1):
    """Seconds = flops / (peak * mfu * n_gpus), where peak is FLOP/s per GPU and mfu is a fraction (0.4)."""
    raise NotImplementedError("TODO milestone 2: train_seconds")


def gpu_hours(flops, peak, mfu):
    """GPU-hours = flops / (peak * mfu) / 3600. It does not depend on the number of GPUs."""
    raise NotImplementedError("TODO milestone 2: gpu_hours")


def mfu_from_throughput(model_flops_per_s_per_gpu, peak):
    """MFU: model FLOP/s each GPU actually delivers divided by its peak. 400 TFLOP/s on a 989 TFLOP/s GPU -> 0.404"""
    raise NotImplementedError("TODO milestone 2: mfu_from_throughput")


# =============================================================================
# Milestone 3: memory for training
# =============================================================================
def state_bytes(n, weights=2, grads=2, master=4, m=4, v=4):
    """Model-state bytes for n parameters: n * (weights + grads + master + m + v). The defaults are
    the mixed-precision AdamW recipe: 2 + 2 + 4 + 4 + 4 = 16 bytes per parameter."""
    raise NotImplementedError("TODO milestone 3: state_bytes")


def act_bytes_per_layer(s, b, h, a, mode="full"):
    """Activation bytes one layer saves for the backward pass (16-bit numbers), Korthikanti et al. 2022.

    s: sequence length, b: microbatch, h: model width C, a: heads.
    mode "full":      s*b*h*(34 + 5*a*s/h)   everything, including the (s, s) score tables
    mode "flash":     s*b*h*34               a fused attention kernel never stores the tables
    mode "recompute": 2*s*b*h                only the layer's input; the rest is recomputed
    Anything else: raise ValueError.
    """
    raise NotImplementedError("TODO milestone 3: act_bytes_per_layer")


def activation_bytes(cfg, s, b, mode="full"):
    """Activations of all cfg.L layers (width cfg.C, cfg.H heads) for a microbatch of b sequences of s tokens."""
    raise NotImplementedError("TODO milestone 3: activation_bytes")


def training_memory(cfg, s, b, mode="full"):
    """{"states": ..., "activations": ..., "total": ...} in bytes: 16 bytes per parameter plus the activations.

    Llama 3 8B, s = 4096, b = 1, mode "full": states 128.5 GB, activations 104.2 GB.
    """
    raise NotImplementedError("TODO milestone 3: training_memory")


def fits(total_bytes, gpu_mem, overhead=3 * GB):
    """True if total_bytes + overhead <= gpu_mem. `overhead` is the CUDA context, buffers and fragmentation."""
    raise NotImplementedError("TODO milestone 3: fits")


def max_microbatch(cfg, s, mode, gpu_mem, overhead=3 * GB):
    """The largest microbatch b (sequences of s tokens) whose training_memory total still fits the card;
    0 if even b = 1 does not. Search upwards from 1; stop at 4096 if everything fits."""
    raise NotImplementedError("TODO milestone 3: max_microbatch")


def max_trainable_params(gpu_mem, overhead=3 * GB):
    """The largest N whose 16-bytes-per-parameter states fit: (gpu_mem - overhead) / 16."""
    raise NotImplementedError("TODO milestone 3: max_trainable_params")


# =============================================================================
# Milestone 4: inference, the KV cache and the bandwidth limit
# =============================================================================
def kv_bytes_per_token(cfg, bytes_per=2):
    """Bytes of keys and values one token adds to the cache: 2 (K and V) * L * KV * d_k * bytes_per.
    Llama 3 8B in bf16: 131,072 bytes = 128 KiB."""
    raise NotImplementedError("TODO milestone 4: kv_bytes_per_token")


def kv_cache_bytes(cfg, ctx, batch=1, bytes_per=2):
    """The cache of `batch` sequences of `ctx` tokens each."""
    raise NotImplementedError("TODO milestone 4: kv_cache_bytes")


def weight_bytes(cfg, bytes_per=2):
    """All parameters at bytes_per each. A mixture of experts must keep every expert in memory."""
    raise NotImplementedError("TODO milestone 4: weight_bytes")


def max_batch(cfg, ctx, gpu_mem, w_bytes=2, kv_bytes=2, overhead=3 * GB):
    """How many sequences of ctx tokens fit beside the weights: (gpu_mem - overhead - weights) // cache per sequence,
    and 0 if the weights alone do not fit."""
    raise NotImplementedError("TODO milestone 4: max_batch")


def decode_step_seconds(cfg, ctx, batch, bw, peak, w_bytes=2, kv_bytes=2):
    """Seconds for one decode step that produces one token for each of `batch` sequences at context ctx.

    A step is limited by the slower of two things. Memory: read every weight once plus every
    sequence's cache, at `bw` bytes/s. Compute: batch * (2 * matmul_weights + 4*L*C*ctx) FLOPs at
    `peak` FLOP/s (2 FLOPs per weight per token, and 4*C*ctx per layer for the attention products).
    """
    raise NotImplementedError("TODO milestone 4: decode_step_seconds")


def decode_tokens_per_second(cfg, ctx, batch, bw, peak, w_bytes=2, kv_bytes=2):
    """Throughput of the whole batch: batch / decode_step_seconds(...).
    Llama 3 8B, bf16, batch 1, no context, H100 (3.35 TB/s): 208.6 tokens/s (chapter 16)."""
    raise NotImplementedError("TODO milestone 4: decode_tokens_per_second")


def ridge_batch(cfg, bw, peak, w_bytes=2):
    """The batch at which the weights-only memory time equals the compute time:
    batch = peak * weight_bytes / (2 * matmul_weights * bw). Below it, decoding is memory-bound."""
    raise NotImplementedError("TODO milestone 4: ridge_batch")


# =============================================================================
# Milestone 5: compute-optimal sizes
# =============================================================================
def loss(N, D, fit):
    """L(N, D) = E + A / N^alpha + B / D^beta, with fit = (E, A, B, alpha, beta)."""
    raise NotImplementedError("TODO milestone 5: loss")


def optimum(C, fit):
    """(N, D, loss) minimising L(N, D) subject to 6*N*D = C. Set dL/dN = 0 along D = C / 6N:

        G = (alpha*A / (beta*B)) ** (1 / (alpha + beta));   N = G * (C/6) ** (beta / (alpha + beta));   D = C / (6N)
    Besiroglu fit at C = 5.76e23: N = 7.2e10, D = 1.33e12.
    """
    raise NotImplementedError("TODO milestone 5: optimum")


def chinchilla_rule(C, ratio=20):
    """The rule of thumb D = ratio * N with C = 6*N*D, so N = sqrt(C / (6 * ratio)). Returns (N, D).
    chinchilla_rule(6e23) -> (7.07e10, 1.41e12)"""
    raise NotImplementedError("TODO milestone 5: chinchilla_rule")


def isoflop_loss(C, N, fit):
    """Loss of an N-parameter model trained on exactly the budget C: loss(N, C / (6N))."""
    raise NotImplementedError("TODO milestone 5: isoflop_loss")


def excess_loss(C, factor, fit):
    """isoflop_loss at factor * N_opt minus the loss at N_opt: the price of straying from the optimum.
    Besiroglu fit, C = 1e22: factor 0.5 costs 0.0099 nats, factor 4 costs 0.0408."""
    raise NotImplementedError("TODO milestone 5: excess_loss")


# =============================================================================
# Milestone 6: lifetime cost and over-training
# =============================================================================
def lifetime_flops(N, D, inference_tokens):
    """6*N*D to train, plus 2*N for every token generated while serving. lifetime_flops(70e9, 1.4e12, 0) -> 5.88e23"""
    raise NotImplementedError("TODO milestone 6: lifetime_flops")


def tokens_for_loss(N, target, fit):
    """The D with loss(N, D, fit) == target: solve B / D^beta = target - E - A / N^alpha for D.
    Return None when target - E - A/N^alpha <= 0 (this N cannot reach the target with any amount of data)."""
    raise NotImplementedError("TODO milestone 6: tokens_for_loss")


def best_size_for_loss(target, inference_tokens, fit):
    """(N, D, lifetime FLOPs) that reach `target` loss at the least cost of training plus serving `inference_tokens`.

    For each N, tokens_for_loss fixes D, so lifetime_flops is a function of N alone. It is huge for N just
    above the smallest feasible size (D explodes) and huge for large N (6ND explodes), with one minimum
    between. Find it by ternary search on log N between n_min = (A / (target - E))^(1/alpha) and 10^4 * n_min.
    With inference_tokens = 0 the answer is the compute-optimal pair for that loss.
    """
    raise NotImplementedError("TODO milestone 6: best_size_for_loss")
