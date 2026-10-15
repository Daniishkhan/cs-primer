# Drill: A2 Lab 3, milestone 5 of 5: a whole tiny GPT, shape by shape (step 1 of 5)
# Everything else in this file is already written. Fill in:
#     block_param_count
# Check it with: python3 check.py 5

"""Lab 3 reference solution: attention and a Transformer block in plain Python (standard library only).

Notation follows Deep Learning chapters 09 and 10: T tokens, width C (d_model), h heads, d_k = C / h,
V vocabulary. A matrix is a list of rows. One sequence x has shape (T, C); a batch is a list of sequences,
(B, T, C). Heads are a list of h matrices, shape (h, T, d_k).
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
    out = []
    for row in S:
        m = max(row)
        if m == -math.inf:
            raise ValueError("a row of all -inf has no softmax (every key was masked)")
        e = [math.exp(s - m) for s in row]        # exp(-inf - m) is 0.0, so masked entries vanish
        z = sum(e)
        out.append([x / z for x in e])
    return out


def layernorm_rows(X, gain, bias, eps=1e-5):
    """Normalise each row over its C numbers: (x - mean) / sqrt(var + eps) * gain + bias.
    The variance is the population variance (divide by C), as in chapter 03."""
    out = []
    for row in X:
        mu = sum(row) / len(row)
        var = sum((x - mu) ** 2 for x in row) / len(row)
        inv = 1.0 / math.sqrt(var + eps)
        out.append([(x - mu) * inv * g + b for x, g, b in zip(row, gain, bias)])
    return out


def gelu(z):
    """GELU, tanh approximation used by GPT-2, for one number."""
    return 0.5 * z * (1.0 + math.tanh(math.sqrt(2.0 / math.pi) * (z + 0.044715 * z ** 3)))


# ----------------------------------------------------------------------------------------
# Milestone 2: scaled dot-product attention and the causal mask
# ----------------------------------------------------------------------------------------
def causal_mask(T):
    """(T, T) matrix of booleans; True where query i must NOT read key j, i.e. where j > i."""
    return [[j > i for j in range(T)] for i in range(T)]


def attention(Q, K, V, mask=None):
    """softmax(Q K^T / sqrt(d_k)) V for one head. Q, K: (T, d_k), V: (T, d_v).
    mask: optional (T, T) booleans, True = forbidden. Apply it to the scores, BEFORE the softmax.
    Returns (output (T, d_v), weights (T, T))."""
    d_k = len(Q[0])
    scores = [[s / math.sqrt(d_k) for s in row] for row in matmul(Q, transpose(K))]
    if mask is not None:
        scores = [[-math.inf if hidden else s for s, hidden in zip(srow, mrow)]
                  for srow, mrow in zip(scores, mask)]
    weights = softmax_rows(scores)
    return matmul(weights, V), weights


# ----------------------------------------------------------------------------------------
# Milestone 3: multi-head attention
# ----------------------------------------------------------------------------------------
def split_heads(x, h):
    """(T, C) -> h matrices of shape (T, d_k): head i takes columns i*d_k .. (i+1)*d_k - 1."""
    C = len(x[0])
    if C % h:
        raise ValueError(f"width {C} is not divisible by {h} heads")
    d_k = C // h
    return [[row[i * d_k:(i + 1) * d_k] for row in x] for i in range(h)]


def merge_heads(heads):
    """h matrices of shape (T, d_k) -> (T, h * d_k): the undo of split_heads (concatenate columns)."""
    return [sum((head[t] for head in heads), []) for t in range(len(heads[0]))]


def multi_head_attention(x, Wq, Wk, Wv, Wo, h, causal=True):
    """Multi-head self-attention for one sequence x (T, C). Wq, Wk, Wv, Wo are (C, C).
    Returns (output (T, C), weights): weights is a list of h matrices (T, T)."""
    T = len(x)
    Qh, Kh, Vh = (split_heads(matmul(x, W), h) for W in (Wq, Wk, Wv))
    mask = causal_mask(T) if causal else None
    outs, weights = [], []
    for q, k, v in zip(Qh, Kh, Vh):
        o, w = attention(q, k, v, mask)
        outs.append(o)
        weights.append(w)
    return matmul(merge_heads(outs), Wo), weights


# ----------------------------------------------------------------------------------------
# Milestone 4: the MLP and the pre-norm Transformer block
# ----------------------------------------------------------------------------------------
def mlp(x, W1, b1, W2, b2):
    """Position-wise MLP: gelu(x W1 + b1) W2 + b2, with shapes (T, C) -> (T, 4C) -> (T, C)."""
    hidden = [[gelu(z) for z in row] for row in add_bias(matmul(x, W1), b1)]
    return add_bias(matmul(hidden, W2), b2)


def block(x, p, h, causal=True):
    """One pre-norm block: x = x + MHA(LN1(x)); x = x + MLP(LN2(x)). (T, C) -> (T, C)."""
    a, _ = multi_head_attention(layernorm_rows(x, p["ln1_g"], p["ln1_b"]),
                                p["Wq"], p["Wk"], p["Wv"], p["Wo"], h, causal)
    x = add(x, a)                                   # write attention's result into the stream
    m = mlp(layernorm_rows(x, p["ln2_g"], p["ln2_b"]), p["W1"], p["b1"], p["W2"], p["b2"])
    return add(x, m)                                # write the MLP's result into the stream


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
    return V * C + T_max * C + n_layers * block_param_count(C) + 2 * C + C * V


def count_params(obj):
    """Count the numbers inside nested lists and dicts (what 'parameters' means)."""
    if isinstance(obj, dict):
        return sum(count_params(v) for v in obj.values())
    if isinstance(obj, list):
        return sum(count_params(v) for v in obj)
    return 1


def model_forward(ids, params, h, trace=None):
    """Logits for one sequence of token ids: shape (T, V).

    Steps, in order, each recorded as trace.append((name, shape(value))) when trace is a list:
      'tok_emb' (T, C), 'x0' (T, C) = token + position embeddings, 'block0', 'block1', ... (T, C),
      'ln_f' (T, C), 'logits' (T, V)."""
    T = len(ids)
    if T > len(params["wpe"]):
        raise ValueError(f"sequence of {T} tokens is longer than the {len(params['wpe'])} positions")
    note = (lambda name, val: trace.append((name, shape(val)))) if trace is not None else (lambda *a: None)
    tok = [params["wte"][i] for i in ids]
    note("tok_emb", tok)
    x = [[a + b for a, b in zip(tok[t], params["wpe"][t])] for t in range(T)]
    note("x0", x)
    for i, p in enumerate(params["blocks"]):
        x = block(x, p, h)
        note(f"block{i}", x)
    x = layernorm_rows(x, params["lnf_g"], params["lnf_b"])
    note("ln_f", x)
    logits = matmul(x, params["head"])
    note("logits", logits)
    return logits


def mean_cross_entropy(logits, targets):
    """Mean over positions of -log softmax(logits[t])[targets[t]], in nats."""
    P = softmax_rows(logits)
    return -sum(math.log(P[t][y]) for t, y in enumerate(targets)) / len(targets)
