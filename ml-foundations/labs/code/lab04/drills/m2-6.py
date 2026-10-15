# Drill: A0 Lab 4, milestone 2 of 6: likelihoods and maximum-likelihood fits (step 6 of 6)
# Everything else in this file is already written. Fill in:
#     categorical_mle
# Check it with: python3 check.py 2

"""Lab 4: Sampling, Likelihood & Entropy (reference solution).

The probability toolkit of chapters 12 to 14, written over plain Python lists and checked against
hand-computed values: samplers built from uniform numbers, maximum-likelihood fits, a numerically
stable log-softmax, temperature and truncation for next-token sampling, entropy, and the KL
divergence in the forms that post-training uses.

Notation: p and q are probability lists (non-negative, summing to 1); z or `logits` are real scores;
`rng` is any object with a `.random()` method returning a float in [0, 1) (a `random.Random`).
Logarithms are natural (nats) unless a `base` argument says otherwise.

What is GIVEN: `make_line_data`, `normalise`, the example logits and the constant `NATS`. What YOU write:

    1  sample_exponential, sample_categorical, box_muller, rejection_sample
    2  bernoulli_loglik, gaussian_loglik, poisson_loglik, gaussian_mle, poisson_mle, categorical_mle
    3  line_nll, least_squares, fit_line
    4  logsumexp, log_softmax, softmax, cross_entropy, cross_entropy_grad
    5  softmax_t, entropy, perplexity, top_k, top_p, sample_token
    6  xent, kl, kl_estimators, estimate_kl, leash_policy

`python3 check.py solution` runs the milestones; the lab page explains each one.
"""
import math
import random

NATS = math.e                                   # pass base=NATS to measure in nats
TOKENS = ["the", "a", "cat", "dog", "ran", "sat"]
LOGITS = [3.0, 2.2, 1.5, 1.4, 0.2, -1.0]       # the example logits of chapters 12 and 14


# =============================================================================
# Given helpers
# =============================================================================
def normalise(p):
    """GIVEN. Scale a list of non-negative numbers so that it sums to 1."""
    total = sum(p)
    return [x / total for x in p]


def make_line_data(seed, n=200, slope=2.0, intercept=1.0, sd=0.7):
    """GIVEN. n points (xs, ys) with x uniform on [-2, 2] and y = slope * x + intercept + Gaussian noise."""
    rng = random.Random(seed)
    xs = [rng.uniform(-2.0, 2.0) for _ in range(n)]
    ys = [slope * x + intercept + rng.gauss(0.0, sd) for x in xs]
    return xs, ys


# =============================================================================
# Milestone 1: samplers built from uniform numbers
# =============================================================================
def sample_exponential(rng, rate):
    """One draw from Exponential(rate) by inverting the cdf F(x) = 1 - exp(-rate x).

    Use exactly one rng.random() call, u, and return -ln(1 - u) / rate.
    """
    return -math.log(1.0 - rng.random()) / rate


def sample_categorical(rng, probs):
    """One index drawn with the given probabilities: walk along the cumulative sums.

    Use exactly one rng.random() call, u. Return the first index i whose running total
    p_0 + ... + p_i is STRICTLY greater than u (so an entry with probability 0 is never returned).
    If rounding leaves u above every running total, return the last index with positive probability.
    """
    u, acc, last = rng.random(), 0.0, len(probs) - 1
    for i, p in enumerate(probs):
        if p > 0:
            last = i
        acc += p
        if u < acc:
            return i
    return last


def box_muller(rng):
    """Two independent standard Gaussians (z1, z2) from two uniforms.

    u1 = 1 - rng.random() (the first call; this keeps u1 in (0, 1] so the log is finite),
    u2 = rng.random() (the second call); r = sqrt(-2 ln u1); return (r cos(2 pi u2), r sin(2 pi u2)).
    """
    u1 = 1.0 - rng.random()
    u2 = rng.random()
    r = math.sqrt(-2.0 * math.log(u1))
    return r * math.cos(2.0 * math.pi * u2), r * math.sin(2.0 * math.pi * u2)


def rejection_sample(rng, density, bound, n):
    """n draws from a density on [0, 1] that never exceeds `bound`, by rejection.

    Repeat: x = rng.random() (first call), u = rng.random() (second call); keep x if
    u < density(x) / bound. Stop at n kept samples. Return (samples, tries), where tries counts
    the proposals made (kept or not).
    """
    samples, tries = [], 0
    while len(samples) < n:
        x = rng.random()
        u = rng.random()
        tries += 1
        if u < density(x) / bound:
            samples.append(x)
    return samples, tries


# =============================================================================
# Milestone 2: likelihoods and maximum-likelihood estimates
# =============================================================================
def bernoulli_loglik(heads, n, theta):
    """ln L(theta) for `heads` successes in n independent trials: h ln(theta) + (n - h) ln(1 - theta).

    A term whose count is 0 contributes 0 even if its probability is 0 (0 ln 0 = 0); a positive
    count with probability 0 makes the data impossible, so return -math.inf.
    Example: bernoulli_loglik(7, 10, 0.7) == 7 ln 0.7 + 3 ln 0.3 = -6.1086.
    """
    total = 0.0
    for count, prob in ((heads, theta), (n - heads, 1.0 - theta)):
        if count > 0:
            if prob <= 0.0:
                return -math.inf
            total += count * math.log(prob)
    return total


def gaussian_loglik(xs, mu, sigma):
    """ln L(mu, sigma) of independent draws xs from N(mu, sigma^2):
    sum over i of  -0.5 ln(2 pi sigma^2) - (x_i - mu)^2 / (2 sigma^2).

    Example: gaussian_loglik([0.0], 0.0, 1.0) == -0.5 ln(2 pi) = -0.9189.
    """
    n = len(xs)
    sq = sum((x - mu) ** 2 for x in xs)
    return -0.5 * n * math.log(2.0 * math.pi * sigma * sigma) - sq / (2.0 * sigma * sigma)


def poisson_loglik(counts, lam):
    """ln L(lambda) of independent Poisson counts: sum over i of  k_i ln(lambda) - lambda - ln(k_i!).

    Use math.lgamma(k + 1) for ln(k!). Example: poisson_loglik([0, 1, 2], 1.0) == -3 - ln 2 = -3.6931.
    """
    return sum(k * math.log(lam) - lam - math.lgamma(k + 1) for k in counts)


def gaussian_mle(xs, ddof=0):
    """(mean, variance) of xs. The maximum-likelihood variance divides by n (ddof=0); the unbiased
    estimate divides by n - ddof with ddof=1. Raise ValueError if xs has too few points."""
    n = len(xs)
    if n - ddof < 1:
        raise ValueError("need more data than ddof")
    mu = sum(xs) / n
    return mu, sum((x - mu) ** 2 for x in xs) / (n - ddof)


def poisson_mle(counts):
    """The maximum-likelihood rate of Poisson counts: their mean. Raise ValueError if empty."""
    if not counts:
        raise ValueError("no data")
    return sum(counts) / len(counts)


def categorical_mle(counts):
    """The maximum-likelihood probabilities of a categorical variable: counts / total.
    Raise ValueError if the total is 0."""
    raise NotImplementedError("TODO milestone 2: categorical_mle")


# =============================================================================
# Milestone 3: fitting a line by gradient descent on the negative log-likelihood
# =============================================================================
def line_nll(params, xs, ys):
    """Negative log-likelihood of y = w x + b + noise, noise ~ N(0, sigma^2), with sigma = exp(s).

    params = (w, b, s): the slope, the intercept and the LOG of the noise standard deviation.
    With r_i = y_i - (w x_i + b) and sigma^2 = exp(2 s):
        nll = sum_i  0.5 ln(2 pi sigma^2) + r_i^2 / (2 sigma^2)
    Returns (nll, grad) with grad = [d nll / d w, d nll / d b, d nll / d s]. These are SUMS over the
    data, not means. Example: xs = [0, 1], ys = [1, 3], params (2, 1, 0) has nll = ln(2 pi) = 1.8379,
    and params (0, 0, 0) has gradient [-3, -4, -8].
    """
    w, b, s = params
    var = math.exp(2.0 * s)
    nll, gw, gb, gs = 0.0, 0.0, 0.0, 0.0
    for x, y in zip(xs, ys):
        r = y - (w * x + b)
        nll += 0.5 * math.log(2.0 * math.pi * var) + r * r / (2.0 * var)
        gw -= r * x / var
        gb -= r / var
        gs += 1.0 - r * r / var
    return nll, [gw, gb, gs]


def least_squares(xs, ys):
    """The closed-form least-squares line (w, b): w = cov(x, y) / var(x), b = mean(y) - w mean(x)."""
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    w = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)
    return w, my - w * mx


def fit_line(xs, ys, lr=0.1, steps=1500):
    """Gradient descent on the MEAN negative log-likelihood from (w, b, s) = (0, 0, 0).

    Each step moves params by -lr * grad / n, using line_nll. Returns the final (w, b, s) as a list.
    """
    n = len(xs)
    params = [0.0, 0.0, 0.0]
    for _ in range(steps):
        _, g = line_nll(params, xs, ys)
        params = [p - lr * gi / n for p, gi in zip(params, g)]
    return params


# =============================================================================
# Milestone 4: a numerically stable log-softmax
# =============================================================================
def logsumexp(zs):
    """ln(sum_j exp(z_j)) without overflow: m + ln(sum_j exp(z_j - m)) with m = max(zs).

    Raise ValueError for an empty list. If every entry is -math.inf the answer is -math.inf
    (do not compute -inf minus -inf). Example: logsumexp([1000, 1000]) == 1000 + ln 2.
    """
    if not zs:
        raise ValueError("logsumexp of an empty list")
    m = max(zs)
    if m == -math.inf:
        return -math.inf
    return m + math.log(sum(math.exp(z - m) for z in zs))


def log_softmax(zs):
    """ln softmax(z)_i = z_i - logsumexp(z), computed in log space (never form the probabilities)."""
    lse = logsumexp(zs)
    return [z - lse for z in zs]


def softmax(zs):
    """The probabilities exp(log_softmax(z)); they sum to 1 and survive logits of 1000."""
    return [math.exp(v) for v in log_softmax(zs)]


def cross_entropy(logits, target):
    """The loss -ln softmax(logits)[target], computed from the logits without forming a probability."""
    return -log_softmax(logits)[target]


def cross_entropy_grad(logits, target):
    """The gradient of cross_entropy with respect to the logits: softmax(logits) minus the one-hot target."""
    p = softmax(logits)
    p[target] -= 1.0
    return p


# =============================================================================
# Milestone 5: temperature, entropy and truncation
# =============================================================================
def softmax_t(logits, temperature=1.0):
    """softmax(logits / T). Raise ValueError unless temperature > 0. Must be stable for T = 0.001."""
    if temperature <= 0:
        raise ValueError("temperature must be positive")
    return softmax([z / temperature for z in logits])


def entropy(p, base=2.0):
    """H(p) = - sum_i p_i log(p_i) in the given base (2 = bits). Terms with p_i = 0 contribute 0."""
    h = 0.0
    for x in p:
        if x > 0:
            h -= x * math.log(x)
    return h / math.log(base)


def perplexity(p, base=2.0):
    """The effective number of choices: base ** entropy(p, base). Equal to e ** (entropy in nats)."""
    return base ** entropy(p, base)


def top_k(p, k):
    """Keep the k most probable entries (ties go to the lower index), zero the rest, renormalise.
    Raise ValueError unless k >= 1. If k >= len(p) nothing changes."""
    if k < 1:
        raise ValueError("k must be at least 1")
    order = sorted(range(len(p)), key=lambda i: (-p[i], i))[:k]
    keep = set(order)
    return normalise([x if i in keep else 0.0 for i, x in enumerate(p)])


def top_p(p, nucleus):
    """Nucleus sampling: keep the smallest set of most probable entries (ties to the lower index)
    whose total probability is at least `nucleus`, zero the rest, renormalise.
    Raise ValueError unless 0 < nucleus <= 1."""
    if not 0 < nucleus <= 1:
        raise ValueError("nucleus must be in (0, 1]")
    order = sorted(range(len(p)), key=lambda i: (-p[i], i))
    keep, total = set(), 0.0
    for i in order:
        keep.add(i)
        total += p[i]
        if total >= nucleus:
            break
    return normalise([x if i in keep else 0.0 for i, x in enumerate(p)])


def sample_token(rng, logits, temperature=1.0, k=None, p=None):
    """One next-token draw: softmax with temperature, then top-k (if k), then top-p (if p), then a
    categorical draw with sample_categorical. Returns the index."""
    probs = softmax_t(logits, temperature)
    if k is not None:
        probs = top_k(probs, k)
    if p is not None:
        probs = top_p(probs, p)
    return sample_categorical(rng, probs)


# =============================================================================
# Milestone 6: cross-entropy, KL, its estimators and the leash
# =============================================================================
def xent(p, q, base=2.0):
    """The cross-entropy H(p, q) = - sum_i p_i log(q_i): the average surprise of model q on data from p.
    Terms with p_i = 0 are skipped. If p_i > 0 and q_i = 0 the answer is math.inf."""
    total = 0.0
    for a, b in zip(p, q):
        if a > 0:
            if b <= 0:
                return math.inf
            total -= a * math.log(b)
    return total / math.log(base)


def kl(p, q, base=2.0):
    """KL(p || q) = sum_i p_i log(p_i / q_i), the extra cost of coding data from p with a model q.
    Terms with p_i = 0 are skipped. If p_i > 0 and q_i = 0 the answer is math.inf."""
    total = 0.0
    for a, b in zip(p, q):
        if a > 0:
            if b <= 0:
                return math.inf
            total += a * math.log(a / b)
    return total / math.log(base)


def kl_estimators(logp, logp_ref):
    """The three single-sample estimators of KL(pi || ref) (Schulman, 2020) for a token x drawn from pi.

    logp = ln pi(x), logp_ref = ln ref(x). With the ratio r = ref(x) / pi(x):
        k1 = -ln r,   k2 = (ln r)^2 / 2,   k3 = (r - 1) - ln r.
    Returns (k1, k2, k3). Example: logp = ln 0.5, logp_ref = ln 0.25 gives r = 0.5 and
    (0.6931, 0.2402, 0.1931).
    """
    log_r = logp_ref - logp
    r = math.exp(log_r)
    return -log_r, 0.5 * log_r * log_r, (r - 1.0) - log_r


def estimate_kl(rng, pi, ref, n):
    """Estimate KL(pi || ref) in nats from n tokens sampled from pi (use sample_categorical).

    Returns {"k1": (mean, sd), "k2": (mean, sd), "k3": (mean, sd)}: the mean and the sample standard
    deviation (dividing by n - 1) of each estimator over the n draws.
    """
    log_pi = [math.log(x) if x > 0 else -math.inf for x in pi]
    log_ref = [math.log(x) if x > 0 else -math.inf for x in ref]
    cols = ([], [], [])
    for _ in range(n):
        x = sample_categorical(rng, pi)
        for col, v in zip(cols, kl_estimators(log_pi[x], log_ref[x])):
            col.append(v)
    out = {}
    for name, col in zip(("k1", "k2", "k3"), cols):
        mean = sum(col) / n
        out[name] = (mean, math.sqrt(sum((v - mean) ** 2 for v in col) / (n - 1)))
    return out


def leash_policy(ref, reward, beta):
    """The policy that maximises  E_pi[reward] - beta * KL(pi || ref):  pi*(y) = ref(y) exp(reward(y) / beta) / Z.

    Must not overflow for beta = 0.001 (subtract the largest exponent before exponentiating).
    Returns a list of probabilities summing to 1. Entries with ref = 0 stay at 0.
    """
    expo = [(math.log(r) + w / beta) if r > 0 else -math.inf for r, w in zip(ref, reward)]
    return softmax(expo)
