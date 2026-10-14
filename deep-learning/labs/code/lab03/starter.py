"""Lab 3 starter: attention and a Transformer block in plain Python (standard library only).

Notation follows Deep Learning chapters 09 and 10: T tokens, width C (d_model), h heads, d_k = C / h,
V vocabulary. A matrix is a list of rows. One sequence x has shape (T, C); a batch is a list of sequences,
(B, T, C). Heads are a list of h matrices, shape (h, T, d_k).

Replace every `raise NotImplementedError(...)` with working code, one milestone at a time, and run
`python3 check.py` after each. The helpers marked "Given" need no changes.
"""
import math
import random


# ----------------------------------------------------------------------------------------
# Given scaffolding (from Lab 1 and a few helpers)
# ----------------------------------------------------------------------------------------
def shape(x):
    """Shape of a nested list as a tuple, e.g. shape([[1, 2, 3], [4, 5, 6]]) == (2, 3)."""
    dims = []
    while isinstance(x, list):
        dims.append(len(x))
        x = x[0] if x else None
    return tuple(dims)


def matmul(A, B):
    """(m, n) @ (n, p) -> (m, p)."""
    if len(A[0]) != len(B):
        raise ValueError(f"cannot multiply {shape(A)} by {shape(B)}")
    cols = list(zip(*B))
    return [[sum(a * b for a, b in zip(row, col)) for col in cols] for row in A]


def transpose(A):
    """(m, n) -> (n, m)."""
    return [list(col) for col in zip(*A)]


def add_bias(A, b):
    """Add the vector b (length n) to every row of A (m, n)."""
    return [[x + bj for x, bj in zip(row, b)] for row in A]


def add(A, B):
    """Elementwise sum of two matrices of the same shape (the residual connection)."""
    if shape(A) != shape(B):
        raise ValueError(f"cannot add {shape(A)} and {shape(B)}")
    return [[a + b for a, b in zip(ra, rb)] for ra, rb in zip(A, B)]


def init_block(C, rng, std=None):
    """Random weights for one Transformer block. std=None means 1/sqrt(fan_in) per matrix."""
    def mat(rows, cols):
        s = std if std is not None else 1.0 / math.sqrt(rows)
        return [[rng.gauss(0.0, s) for _ in range(cols)] for _ in range(rows)]
    return {
        "ln1_g": [1.0] * C, "ln1_b": [0.0] * C,
        "Wq": mat(C, C), "Wk": mat(C, C), "Wv": mat(C, C), "Wo": mat(C, C),
        "ln2_g": [1.0] * C, "ln2_b": [0.0] * C,
        "W1": mat(C, 4 * C), "b1": [0.0] * (4 * C),
        "W2": mat(4 * C, C), "b2": [0.0] * C,
    }


def init_model(V, C, T_max, n_layers, seed=0, std=0.02):
    """Random parameters of a tiny GPT: embeddings, n_layers blocks, final norm, output head."""
    rng = random.Random(seed)
    def mat(rows, cols):
        return [[rng.gauss(0.0, std) for _ in range(cols)] for _ in range(rows)]
    return {
        "wte": mat(V, C), "wpe": mat(T_max, C),
        "blocks": [init_block(C, rng, std) for _ in range(n_layers)],
        "lnf_g": [1.0] * C, "lnf_b": [0.0] * C,
        "head": mat(C, V),
    }


# ----------------------------------------------------------------------------------------
# Milestone 1: softmax, layer normalisation and GELU
# ----------------------------------------------------------------------------------------
def softmax_rows(S):
    """Softmax of each row. Subtract the row maximum first; -inf entries must get weight exactly 0.
    A row in which every entry is -inf has no valid answer: raise ValueError."""
    raise NotImplementedError("TODO milestone 1: softmax_rows")


def layernorm_rows(X, gain, bias, eps=1e-5):
    """Normalise each row over its C numbers: (x - mean) / sqrt(var + eps) * gain + bias.
    The variance is the population variance (divide by C), as in chapter 03."""
    raise NotImplementedError("TODO milestone 1: layernorm_rows")


def gelu(z):
    """GELU, tanh approximation used by GPT-2, for one number."""
    raise NotImplementedError("TODO milestone 1: gelu")


# ----------------------------------------------------------------------------------------
# Milestone 2: scaled dot-product attention and the causal mask
# ----------------------------------------------------------------------------------------
def causal_mask(T):
    """(T, T) matrix of booleans; True where query i must NOT read key j, i.e. where j > i."""
    raise NotImplementedError("TODO milestone 2: causal_mask")


def attention(Q, K, V, mask=None):
    """softmax(Q K^T / sqrt(d_k)) V for one head. Q, K: (T, d_k), V: (T, d_v).
    mask: optional (T, T) booleans, True = forbidden. Apply it to the scores, BEFORE the softmax.
    Returns (output (T, d_v), weights (T, T))."""
    raise NotImplementedError("TODO milestone 2: attention")


# ----------------------------------------------------------------------------------------
# Milestone 3: multi-head attention
# ----------------------------------------------------------------------------------------
def split_heads(x, h):
    """(T, C) -> h matrices of shape (T, d_k): head i takes columns i*d_k .. (i+1)*d_k - 1."""
    raise NotImplementedError("TODO milestone 3: split_heads")


def merge_heads(heads):
    """h matrices of shape (T, d_k) -> (T, h * d_k): the undo of split_heads (concatenate columns)."""
    raise NotImplementedError("TODO milestone 3: merge_heads")


def multi_head_attention(x, Wq, Wk, Wv, Wo, h, causal=True):
    """Multi-head self-attention for one sequence x (T, C). Wq, Wk, Wv, Wo are (C, C).
    Returns (output (T, C), weights): weights is a list of h matrices (T, T)."""
    raise NotImplementedError("TODO milestone 3: multi_head_attention")


# ----------------------------------------------------------------------------------------
# Milestone 4: the MLP and the pre-norm Transformer block
# ----------------------------------------------------------------------------------------
def mlp(x, W1, b1, W2, b2):
    """Position-wise MLP: gelu(x W1 + b1) W2 + b2, with shapes (T, C) -> (T, 4C) -> (T, C)."""
    raise NotImplementedError("TODO milestone 4: mlp")


def block(x, p, h, causal=True):
    """One pre-norm block: x = x + MHA(LN1(x)); x = x + MLP(LN2(x)). (T, C) -> (T, C)."""
    raise NotImplementedError("TODO milestone 4: block")


def apply_batch(fn, X):
    """Apply a per-sequence function to every sequence of a batch (B, T, C)."""
    return [fn(x) for x in X]


# ----------------------------------------------------------------------------------------
# Milestone 5: counting parameters and a whole tiny GPT
# ----------------------------------------------------------------------------------------
def block_param_count(C):
    """Closed form for one block: attention 4C^2, MLP 8C^2 + 5C, two LayerNorms 4C."""
    raise NotImplementedError("TODO milestone 5: block_param_count")


def model_param_count(V, C, T_max, n_layers):
    """Closed form for the whole model of init_model."""
    raise NotImplementedError("TODO milestone 5: model_param_count")


def count_params(obj):
    """Count the numbers inside nested lists and dicts (what 'parameters' means)."""
    raise NotImplementedError("TODO milestone 5: count_params")


def model_forward(ids, params, h, trace=None):
    """Logits for one sequence of token ids: shape (T, V).

    Steps, in order, each recorded as trace.append((name, shape(value))) when trace is a list:
      'tok_emb' (T, C), 'x0' (T, C) = token + position embeddings, 'block0', 'block1', ... (T, C),
      'ln_f' (T, C), 'logits' (T, V)."""
    raise NotImplementedError("TODO milestone 5: model_forward")


def mean_cross_entropy(logits, targets):
    """Mean over positions of -log softmax(logits[t])[targets[t]], in nats."""
    raise NotImplementedError("TODO milestone 5: mean_cross_entropy")
