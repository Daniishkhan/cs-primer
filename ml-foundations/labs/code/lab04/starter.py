"""Lab 4: Sampling, Likelihood & Entropy.

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

`python3 check.py` runs the milestones; the lab page explains each one.
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
    raise NotImplementedError("TODO milestone 1: sample_exponential")


def sample_categorical(rng, probs):
    """One index drawn with the given probabilities: walk along the cumulative sums.

    Use exactly one rng.random() call, u. Return the first index i whose running total
    p_0 + ... + p_i is STRICTLY greater than u (so an entry with probability 0 is never returned).
    If rounding leaves u above every running total, return the last index with positive probability.
    """
    raise NotImplementedError("TODO milestone 1: sample_categorical")


def box_muller(rng):
    """Two independent standard Gaussians (z1, z2) from two uniforms.

    u1 = 1 - rng.random() (the first call; this keeps u1 in (0, 1] so the log is finite),
    u2 = rng.random() (the second call); r = sqrt(-2 ln u1); return (r cos(2 pi u2), r sin(2 pi u2)).
    """
    raise NotImplementedError("TODO milestone 1: box_muller")


def rejection_sample(rng, density, bound, n):
    """n draws from a density on [0, 1] that never exceeds `bound`, by rejection.

    Repeat: x = rng.random() (first call), u = rng.random() (second call); keep x if
    u < density(x) / bound. Stop at n kept samples. Return (samples, tries), where tries counts
    the proposals made (kept or not).
    """
    raise NotImplementedError("TODO milestone 1: rejection_sample")


# =============================================================================
# Milestone 2: likelihoods and maximum-likelihood estimates
# =============================================================================
def bernoulli_loglik(heads, n, theta):
    """ln L(theta) for `heads` successes in n independent trials: h ln(theta) + (n - h) ln(1 - theta).

    A term whose count is 0 contributes 0 even if its probability is 0 (0 ln 0 = 0); a positive
    count with probability 0 makes the data impossible, so return -math.inf.
    Example: bernoulli_loglik(7, 10, 0.7) == 7 ln 0.7 + 3 ln 0.3 = -6.1086.
    """
    raise NotImplementedError("TODO milestone 2: bernoulli_loglik")


def gaussian_loglik(xs, mu, sigma):
    """ln L(mu, sigma) of independent draws xs from N(mu, sigma^2):
    sum over i of  -0.5 ln(2 pi sigma^2) - (x_i - mu)^2 / (2 sigma^2).

    Example: gaussian_loglik([0.0], 0.0, 1.0) == -0.5 ln(2 pi) = -0.9189.
    """
    raise NotImplementedError("TODO milestone 2: gaussian_loglik")


def poisson_loglik(counts, lam):
    """ln L(lambda) of independent Poisson counts: sum over i of  k_i ln(lambda) - lambda - ln(k_i!).

    Use math.lgamma(k + 1) for ln(k!). Example: poisson_loglik([0, 1, 2], 1.0) == -3 - ln 2 = -3.6931.
    """
    raise NotImplementedError("TODO milestone 2: poisson_loglik")


def gaussian_mle(xs, ddof=0):
    """(mean, variance) of xs. The maximum-likelihood variance divides by n (ddof=0); the unbiased
    estimate divides by n - ddof with ddof=1. Raise ValueError if xs has too few points."""
    raise NotImplementedError("TODO milestone 2: gaussian_mle")


def poisson_mle(counts):
    """The maximum-likelihood rate of Poisson counts: their mean. Raise ValueError if empty."""
    raise NotImplementedError("TODO milestone 2: poisson_mle")


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
    raise NotImplementedError("TODO milestone 3: line_nll")


def least_squares(xs, ys):
    """The closed-form least-squares line (w, b): w = cov(x, y) / var(x), b = mean(y) - w mean(x)."""
    raise NotImplementedError("TODO milestone 3: least_squares")


def fit_line(xs, ys, lr=0.1, steps=1500):
    """Gradient descent on the MEAN negative log-likelihood from (w, b, s) = (0, 0, 0).

    Each step moves params by -lr * grad / n, using line_nll. Returns the final (w, b, s) as a list.
    """
    raise NotImplementedError("TODO milestone 3: fit_line")


# =============================================================================
# Milestone 4: a numerically stable log-softmax
# =============================================================================
def logsumexp(zs):
    """ln(sum_j exp(z_j)) without overflow: m + ln(sum_j exp(z_j - m)) with m = max(zs).

    Raise ValueError for an empty list. If every entry is -math.inf the answer is -math.inf
    (do not compute -inf minus -inf). Example: logsumexp([1000, 1000]) == 1000 + ln 2.
    """
    raise NotImplementedError("TODO milestone 4: logsumexp")


def log_softmax(zs):
    """ln softmax(z)_i = z_i - logsumexp(z), computed in log space (never form the probabilities)."""
    raise NotImplementedError("TODO milestone 4: log_softmax")


def softmax(zs):
    """The probabilities exp(log_softmax(z)); they sum to 1 and survive logits of 1000."""
    raise NotImplementedError("TODO milestone 4: softmax")


def cross_entropy(logits, target):
    """The loss -ln softmax(logits)[target], computed from the logits without forming a probability."""
    raise NotImplementedError("TODO milestone 4: cross_entropy")


def cross_entropy_grad(logits, target):
    """The gradient of cross_entropy with respect to the logits: softmax(logits) minus the one-hot target."""
    raise NotImplementedError("TODO milestone 4: cross_entropy_grad")


# =============================================================================
# Milestone 5: temperature, entropy and truncation
# =============================================================================
def softmax_t(logits, temperature=1.0):
    """softmax(logits / T). Raise ValueError unless temperature > 0. Must be stable for T = 0.001."""
    raise NotImplementedError("TODO milestone 5: softmax_t")


def entropy(p, base=2.0):
    """H(p) = - sum_i p_i log(p_i) in the given base (2 = bits). Terms with p_i = 0 contribute 0."""
    raise NotImplementedError("TODO milestone 5: entropy")


def perplexity(p, base=2.0):
    """The effective number of choices: base ** entropy(p, base). Equal to e ** (entropy in nats)."""
    raise NotImplementedError("TODO milestone 5: perplexity")


def top_k(p, k):
    """Keep the k most probable entries (ties go to the lower index), zero the rest, renormalise.
    Raise ValueError unless k >= 1. If k >= len(p) nothing changes."""
    raise NotImplementedError("TODO milestone 5: top_k")


def top_p(p, nucleus):
    """Nucleus sampling: keep the smallest set of most probable entries (ties to the lower index)
    whose total probability is at least `nucleus`, zero the rest, renormalise.
    Raise ValueError unless 0 < nucleus <= 1."""
    raise NotImplementedError("TODO milestone 5: top_p")


def sample_token(rng, logits, temperature=1.0, k=None, p=None):
    """One next-token draw: softmax with temperature, then top-k (if k), then top-p (if p), then a
    categorical draw with sample_categorical. Returns the index."""
    raise NotImplementedError("TODO milestone 5: sample_token")


# =============================================================================
# Milestone 6: cross-entropy, KL, its estimators and the leash
# =============================================================================
def xent(p, q, base=2.0):
    """The cross-entropy H(p, q) = - sum_i p_i log(q_i): the average surprise of model q on data from p.
    Terms with p_i = 0 are skipped. If p_i > 0 and q_i = 0 the answer is math.inf."""
    raise NotImplementedError("TODO milestone 6: xent")


def kl(p, q, base=2.0):
    """KL(p || q) = sum_i p_i log(p_i / q_i), the extra cost of coding data from p with a model q.
    Terms with p_i = 0 are skipped. If p_i > 0 and q_i = 0 the answer is math.inf."""
    raise NotImplementedError("TODO milestone 6: kl")


def kl_estimators(logp, logp_ref):
    """The three single-sample estimators of KL(pi || ref) (Schulman, 2020) for a token x drawn from pi.

    logp = ln pi(x), logp_ref = ln ref(x). With the ratio r = ref(x) / pi(x):
        k1 = -ln r,   k2 = (ln r)^2 / 2,   k3 = (r - 1) - ln r.
    Returns (k1, k2, k3). Example: logp = ln 0.5, logp_ref = ln 0.25 gives r = 0.5 and
    (0.6931, 0.2402, 0.1931).
    """
    raise NotImplementedError("TODO milestone 6: kl_estimators")


def estimate_kl(rng, pi, ref, n):
    """Estimate KL(pi || ref) in nats from n tokens sampled from pi (use sample_categorical).

    Returns {"k1": (mean, sd), "k2": (mean, sd), "k3": (mean, sd)}: the mean and the sample standard
    deviation (dividing by n - 1) of each estimator over the n draws.
    """
    raise NotImplementedError("TODO milestone 6: estimate_kl")


def leash_policy(ref, reward, beta):
    """The policy that maximises  E_pi[reward] - beta * KL(pi || ref):  pi*(y) = ref(y) exp(reward(y) / beta) / Z.

    Must not overflow for beta = 0.001 (subtract the largest exponent before exponentiating).
    Returns a list of probabilities summing to 1. Entries with ref = 0 stay at 0.
    """
    raise NotImplementedError("TODO milestone 6: leash_policy")
