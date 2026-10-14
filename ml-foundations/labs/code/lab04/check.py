"""Self-check for Lab 4: Sampling, Likelihood & Entropy.

    python3 check.py                  # checks your starter.py
    python3 check.py solution         # checks the reference solution
    python3 check.py solution 4       # only milestone 4
    python3 check.py solution 1 3     # milestone 1, replaying ONLY the random cases of seed 3

Samplers are tested two ways: with a scripted source of "random" numbers (so a hand-computed
answer is exact), and statistically, on seeded generators, with a tolerance of five standard
errors (a correct sampler fails that by chance about once in two million runs, and with fixed
seeds never). Likelihood code is tested against hand values and against the property that the
maximum-likelihood estimate beats its neighbours. The oracles never call your functions. A failure
prints its seed or the exact inputs. The whole check takes a few seconds.
Prints a tick, a cross, or "not implemented yet" for each milestone.
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


def vnear(a, b, tol=1e-9):
    return len(a) == len(b) and all(near(x, y, tol) for x, y in zip(a, b))


def fmt(v):
    return "[" + ", ".join(f"{x:.6g}" for x in v) + "]"


class FixedRng:
    """A 'random' source that returns scripted numbers and refuses to be asked for more."""

    def __init__(self, values):
        self.values, self.calls = list(values), 0

    def random(self):
        if self.calls >= len(self.values):
            raise AssertionError(f"your function called rng.random() {self.calls + 1} times; the contract allows {len(self.values)}")
        self.calls += 1
        return self.values[self.calls - 1]


def within(est, exact, se, k=5.0):
    return abs(est - exact) <= k * se


def softmax_naive(z):
    e = [math.exp(x) for x in z]
    return [v / sum(e) for v in e]


def H2(p):
    return -sum(x * math.log2(x) for x in p if x > 0)


def KL2(p, q):
    return sum(a * math.log2(a / b) for a, b in zip(p, q) if a > 0)


# =============================================================================
# Milestone 1: samplers
# =============================================================================
def m1():
    # exponential: one uniform, inverse cdf
    r = FixedRng([0.5])
    got = mod.sample_exponential(r, 2.0)
    assert near(got, math.log(2) / 2, 1e-12), f"sample_exponential with u = 0.5 and rate 2 should be -ln(0.5) / 2 = {math.log(2) / 2:.6f}; got {got}"
    assert mod.sample_exponential(FixedRng([0.0]), 3.0) == 0.0, "u = 0 maps to 0: x = -ln(1 - u) / rate"
    assert near(mod.sample_exponential(FixedRng([1 - math.exp(-1)]), 1.0), 1.0, 1e-9), "the cdf F(1) = 1 - e^-1 for rate 1, so that u must give x = 1"

    # categorical: cumulative walk, strict inequality, zero-probability entries are never returned
    p = [0.5, 0.3, 0.2]
    for u, want in [(0.0, 0), (0.49999, 0), (0.5, 1), (0.79, 1), (0.8, 2), (0.999999, 2)]:
        got = mod.sample_categorical(FixedRng([u]), p)
        assert got == want, f"sample_categorical([0.5, 0.3, 0.2]) with u = {u} should return {want} (the first index whose running total exceeds u); got {got}"
    assert mod.sample_categorical(FixedRng([0.5]), [0.5, 0.0, 0.5]) == 2, "an entry with probability 0 must never be returned (use u < running total, strictly)"
    assert mod.sample_categorical(FixedRng([0.0]), [0.0, 1.0]) == 1, "u = 0 must not select a zero-probability first entry"
    assert mod.sample_categorical(FixedRng([0.95]), [0.3, 0.3, 0.3, 0.0]) == 2, (
        "if rounding leaves u above every running total (here the probabilities sum to 0.9), return the LAST entry with positive probability, not the last index")

    # Box-Muller: two uniforms, in order
    z = mod.box_muller(FixedRng([0.5, 0.25]))
    assert len(z) == 2 and near(z[0], 0.0, 1e-9) and near(z[1], math.sqrt(2 * math.log(2)), 1e-9), (
        f"box_muller with the uniforms 0.5 then 0.25: r = sqrt(-2 ln 0.5) = 1.17741 and the angle is pi/2, so (0, 1.17741); got {z}")
    z = mod.box_muller(FixedRng([0.0, 0.3]))
    assert all(math.isfinite(v) for v in z), f"a uniform draw of exactly 0.0 must not crash or give inf (use 1 - u inside the log); got {z}"

    # rejection: scripted proposals
    r = FixedRng([0.5, 0.9, 0.8, 0.5])
    samples, tries = mod.rejection_sample(r, lambda x: 2 * x, 2.0, 1)
    assert samples == [0.8] and tries == 2, (f"density 2x with bound 2: the proposal x = 0.5 has acceptance probability 0.5 and u = 0.9 is above it (rejected); "
                                              f"x = 0.8 has 0.8 and u = 0.5 is below it (kept). Expected ([0.8], 2); got ({samples}, {tries})")

    # statistics
    notes = []
    N = 20000
    for s in seeds(range(1, 4)):
        rng = random.Random(s)
        rate = [0.5, 2.0, 7.0][s % 3]
        xs = [mod.sample_exponential(rng, rate) for _ in range(N)]
        assert min(xs) >= 0.0, f"seed {s}: exponential draws must be non-negative"
        m = exp_mean = sum(xs) / N
        assert within(m, 1 / rate, (1 / rate) / math.sqrt(N)), f"seed {s}: Exponential({rate}) has mean {1 / rate:.4f}; the mean of {N} draws was {m:.4f}"
        tail = sum(x > 1 / rate for x in xs) / N
        assert within(tail, math.exp(-1), math.sqrt(math.exp(-1) * (1 - math.exp(-1)) / N)), f"seed {s}: P(X > mean) should be e^-1 = 0.3679; got {tail:.4f}"

        probs = [0.5, 0.3, 0.15, 0.05, 0.0]
        draws = [mod.sample_categorical(rng, probs) for _ in range(N)]
        for i, pi in enumerate(probs):
            f = draws.count(i) / N
            assert within(f, pi, math.sqrt(pi * (1 - pi) / N) if 0 < pi < 1 else 0.0), f"seed {s}: index {i} should appear with frequency {pi}; got {f:.4f}"

        zs = []
        for _ in range(N // 2):
            zs.extend(mod.box_muller(rng))
        mean = sum(zs) / len(zs)
        var = bm_var = sum((v - mean) ** 2 for v in zs) / len(zs)
        assert within(mean, 0.0, 1 / math.sqrt(len(zs))), f"seed {s}: Box-Muller mean should be 0; got {mean:.4f}"
        assert within(var, 1.0, math.sqrt(2.0 / len(zs))), f"seed {s}: Box-Muller variance should be 1; got {var:.4f}"
        inside = sum(abs(v) < 1.96 for v in zs) / len(zs)
        assert within(inside, 0.95, math.sqrt(0.95 * 0.05 / len(zs))), f"seed {s}: about 95% of standard Gaussians lie within 1.96; got {inside:.4f}"
        pairs = [mod.box_muller(rng) for _ in range(5000)]
        corr = sum(a * b for a, b in pairs) / len(pairs)
        assert abs(corr) < 5 / math.sqrt(len(pairs)), f"seed {s}: the two outputs of one call must be independent; their mean product is {corr:.3f}"

        n = 4000
        xs, tries = mod.rejection_sample(rng, lambda x: 6 * x * (1 - x), 1.5, n)
        assert len(xs) == n and all(0 <= x <= 1 for x in xs), f"seed {s}: rejection_sample must return exactly n samples inside [0, 1]"
        mean = sum(xs) / n
        var = sum((x - mean) ** 2 for x in xs) / n
        assert within(mean, 0.5, math.sqrt(0.05 / n)), f"seed {s}: the density 6x(1-x) has mean 0.5; got {mean:.4f}"
        assert within(var, 0.05, 0.05 * math.sqrt(2.0 / n) * 1.5), f"seed {s}: the density 6x(1-x) has variance 0.05 (a Beta(2,2)); got {var:.4f}"
        assert within(n / tries, 2 / 3, math.sqrt((2 / 3) * (1 / 3) / tries)), f"seed {s}: the acceptance rate should be 1/bound = 0.667; got {n / tries:.3f}"
        if not notes:
            notes.append(f"seed {s}: Exponential({rate}) mean {exp_mean:.3f} (exact {1 / rate:.3f}); Box-Muller variance {bm_var:.3f} (exact 1); "
                         f"rejection acceptance {n / tries:.3f} (exact 0.667)")
    xs, tries = mod.rejection_sample(random.Random(1), lambda x: 10.0 if 0.45 <= x <= 0.55 else 0.0, 10.0, 500)
    assert 7.0 < tries / 500 < 14.0, f"a narrow density (width 0.1) under a uniform proposal is accepted about 10% of the time; tries per sample was {tries / 500:.1f}"
    return "\n".join(notes)


# =============================================================================
# Milestone 2: likelihoods and maximum-likelihood estimates
# =============================================================================
def poisson_draw(rng, lam):
    """Knuth's multiplication method, only for the oracle data."""
    limit, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= limit:
            return k
        k += 1


def m2():
    assert near(mod.bernoulli_loglik(7, 10, 0.7), 7 * math.log(0.7) + 3 * math.log(0.3)), (
        f"bernoulli_loglik(7, 10, 0.7) should be 7 ln 0.7 + 3 ln 0.3 = -6.1086; got {mod.bernoulli_loglik(7, 10, 0.7)}")
    ll = mod.bernoulli_loglik(1050, 1500, 0.7)
    assert abs(ll + 916.30) < 0.01, f"the log-likelihood of 1,050 heads in 1,500 flips at theta = 0.7 should be -916.30 (finite, although the likelihood underflows to 0); got {ll}"
    assert mod.bernoulli_loglik(0, 10, 0.0) == 0.0 and mod.bernoulli_loglik(10, 10, 1.0) == 0.0, "0 ln 0 counts as 0: zero heads with theta = 0 is certain"
    assert mod.bernoulli_loglik(3, 10, 0.0) == -math.inf and mod.bernoulli_loglik(0, 10, 1.0) == -math.inf, "data the parameter rules out has log-likelihood -inf, not an error"
    for h, n, want in [(7, 10, 0.8057), (70, 100, 0.1153), (700, 1000, 4.158e-10)]:
        ratio = math.exp(mod.bernoulli_loglik(h, n, 0.6) - mod.bernoulli_loglik(h, n, h / n))
        assert abs(ratio - want) <= 2e-3 * want, (
            f"L(0.6) / L(best) for {h} heads in {n} should be about {want:.4g} (more data, sharper curve); got {ratio:.4g}")

    assert near(mod.gaussian_loglik([0.0], 0.0, 1.0), -0.5 * math.log(2 * math.pi)), "one point at the mean of a standard Gaussian: -0.5 ln(2 pi) = -0.9189"
    assert near(mod.gaussian_loglik([1.0, 3.0], 2.0, 1.0), -math.log(2 * math.pi) - 1.0), "two points one unit either side of the mean: -ln(2 pi) - 1 = -2.8379"
    assert near(mod.gaussian_loglik([1.0, 3.0], 2.0, 2.0), -math.log(2 * math.pi * 4) - 2 / 8), "sigma is a standard deviation: the variance in the formula is sigma^2"
    assert near(mod.poisson_loglik([0, 1, 2], 1.0), -3 - math.log(2)), f"poisson_loglik([0, 1, 2], 1.0) should be -3 - ln 2 = -3.6931; got {mod.poisson_loglik([0, 1, 2], 1.0)}"

    mu, var = mod.gaussian_mle([1.0, 2.0, 3.0, 4.0])
    assert near(mu, 2.5) and near(var, 1.25), f"gaussian_mle([1, 2, 3, 4]) is (2.5, 1.25): the MLE variance divides by n; got ({mu}, {var})"
    assert near(mod.gaussian_mle([1.0, 2.0, 3.0, 4.0], ddof=1)[1], 5 / 3), "with ddof=1 the variance divides by n - 1: 5/3"
    for bad in (lambda: mod.gaussian_mle([]), lambda: mod.gaussian_mle([1.0], ddof=1), lambda: mod.poisson_mle([]), lambda: mod.categorical_mle([0, 0])):
        try:
            bad()
        except ValueError:
            continue
        raise AssertionError("gaussian_mle([]), gaussian_mle([x], ddof=1), poisson_mle([]) and categorical_mle([0, 0]) must raise ValueError")
    assert near(mod.poisson_mle([2, 4, 6]), 4.0), "the Poisson MLE is the sample mean"
    assert vnear(mod.categorical_mle([2, 3, 5, 0]), [0.2, 0.3, 0.5, 0.0]), "the categorical MLE is counts / total"

    # the MLE is a maximum: neighbours do worse, on random data
    for s in seeds(range(1, 7)):
        rng = random.Random(s)
        h, n = rng.randint(1, 49), 50
        th = mod.categorical_mle([h, n - h])[0]
        assert near(th, h / n), f"seed {s}: the Bernoulli MLE is heads / n"
        best = mod.bernoulli_loglik(h, n, th)
        for d in (-0.05, -0.01, 0.01, 0.05):
            t2 = min(max(th + d, 1e-6), 1 - 1e-6)
            assert mod.bernoulli_loglik(h, n, t2) <= best + 1e-12, f"seed {s}: theta = {t2:.3f} beats the MLE {th:.3f} for {h} heads in {n}"
        xs = [rng.gauss(rng.uniform(-3, 3), rng.uniform(0.5, 3)) for _ in range(60)]
        mu, var = mod.gaussian_mle(xs)
        sd = math.sqrt(var)
        best = mod.gaussian_loglik(xs, mu, sd)
        assert near(best, -0.5 * len(xs) * (math.log(2 * math.pi * var) + 1), 1e-9), (
            f"seed {s}: at the MLE the squared-error term equals n/2, so the maximum log-likelihood is -n/2 (ln(2 pi var) + 1) = "
            f"{-0.5 * len(xs) * (math.log(2 * math.pi * var) + 1):.4f}; yours is {best:.4f}")
        for dm, fs in [(0.1, 1.0), (-0.1, 1.0), (0.0, 0.9), (0.0, 1.1)]:
            assert mod.gaussian_loglik(xs, mu + dm, sd * fs) <= best + 1e-9, f"seed {s}: (mu + {dm}, sigma x {fs}) beats the Gaussian MLE"
        counts = [poisson_draw(rng, 4.0) for _ in range(40)]
        lam = mod.poisson_mle(counts)
        for f in (0.9, 0.95, 1.05, 1.1):
            assert mod.poisson_loglik(counts, lam * f) <= mod.poisson_loglik(counts, lam) + 1e-9, f"seed {s}: lambda x {f} beats the Poisson MLE"

    # bias of the MLE variance: n = 3 samples from N(0, 2^2) have an average MLE variance of (n - 1)/n * 4
    rng = random.Random(11 if ONLY_SEED is None else ONLY_SEED)
    reps = 20000
    m0 = m1 = 0.0
    for _ in range(reps):
        xs = [rng.gauss(0.0, 2.0) for _ in range(3)]
        m0 += mod.gaussian_mle(xs)[1]
        m1 += mod.gaussian_mle(xs, ddof=1)[1]
    m0, m1 = m0 / reps, m1 / reps
    assert abs(m0 - 8 / 3) < 0.15 and abs(m1 - 4.0) < 0.15, (
        f"over {reps} samples of 3 points from N(0, 4): the MLE variance averages (2/3) * 4 = 2.667 and the n - 1 version 4.0; got {m0:.3f} and {m1:.3f}")
    return (f"1,050 heads in 1,500 flips: log-likelihood {ll:.2f} (exp of it underflows to {math.exp(ll)}); "
            f"mean MLE variance with n = 3: {m0:.3f} (n - 1 version {m1:.3f}, true 4)")


# =============================================================================
# Milestone 3: fitting a line by gradient descent on the NLL
# =============================================================================
def m3():
    nll, g = mod.line_nll((2.0, 1.0, 0.0), [0.0, 1.0], [1.0, 3.0])
    assert near(nll, math.log(2 * math.pi)), f"a perfect fit with sigma = 1 on 2 points has nll = 2 * 0.5 ln(2 pi) = 1.8379; got {nll}"
    assert vnear(g, [0.0, 0.0, 2.0]), f"at a perfect fit the slope and intercept gradients are 0 and d nll / d s = sum(1 - 0) = 2; got {fmt(g)}"
    nll, g = mod.line_nll((0.0, 0.0, 0.0), [0.0, 1.0], [1.0, 3.0])
    assert near(nll, math.log(2 * math.pi) + 5.0), f"at (0, 0, 0): residuals 1 and 3, nll = ln(2 pi) + (1 + 9) / 2 = 6.8379; got {nll}"
    assert vnear(g, [-3.0, -4.0, -8.0]), f"at (0, 0, 0) the gradient is [-sum(r x), -sum(r), sum(1 - r^2)] = [-3, -4, -8]; got {fmt(g)}"

    worst = 0.0
    for s in seeds(range(1, 6)):
        rng = random.Random(s)
        xs = [rng.uniform(-2, 2) for _ in range(8)]
        ys = [rng.uniform(-3, 3) for _ in range(8)]
        p = [rng.uniform(-2, 2), rng.uniform(-2, 2), rng.uniform(-1, 1)]
        _, g = mod.line_nll(p, xs, ys)
        for i in range(3):
            hi, lo = list(p), list(p)
            hi[i] += 1e-6
            lo[i] -= 1e-6
            num = (mod.line_nll(hi, xs, ys)[0] - mod.line_nll(lo, xs, ys)[0]) / 2e-6
            err = abs(num - g[i]) / max(1.0, abs(num), abs(g[i]))
            worst = max(worst, err)
            assert err < 1e-6, (f"seed {s}: d nll / d {'wbs'[i]} at {fmt(p)} is {g[i]:.6f} by your formula but {num:.6f} by central differences of your nll. "
                                "Remember sigma^2 = exp(2 s), so d sigma^2 / d s = 2 sigma^2")

    w, b = mod.least_squares([0.0, 1.0, 2.0], [1.0, 3.0, 5.0])
    assert near(w, 2.0) and near(b, 1.0), f"least_squares on the exact line y = 2x + 1 should give (2, 1); got ({w}, {b})"
    for s in seeds((13, 14, 15)):
        xs, ys = mod.make_line_data(s, n=100)
        n = len(xs)
        sx, sy, sxx, sxy = sum(xs), sum(ys), sum(x * x for x in xs), sum(x * y for x, y in zip(xs, ys))
        det = n * sxx - sx * sx
        w0, b0 = (n * sxy - sx * sy) / det, (sxx * sy - sx * sxy) / det          # the normal equations, Cramer's rule
        w, b = mod.least_squares(xs, ys)
        assert near(w, w0, 1e-9) and near(b, b0, 1e-9), f"seed {s}: the normal equations give ({w0:.6f}, {b0:.6f}); least_squares gave ({w:.6f}, {b:.6f})"
        wf, bf, sf = mod.fit_line(xs, ys)
        assert all(math.isfinite(v) for v in (wf, bf, sf)), (f"seed {s}: fit_line produced {wf, bf, sf}. Use the MEAN gradient (divide by n) so that lr = 0.1 is stable; "
                                                            "the sums in line_nll are n times larger")
        assert abs(wf - w0) < 1e-3 and abs(bf - b0) < 1e-3, (f"seed {s}: after 1,500 steps the fit should match least squares ({w0:.4f}, {b0:.4f}); "
                                                            f"got ({wf:.4f}, {bf:.4f}). Maximum likelihood under Gaussian noise IS least squares")
        rms = math.sqrt(sum((y - (w0 * x + b0)) ** 2 for x, y in zip(xs, ys)) / n)
        assert abs(math.exp(sf) - rms) < 1e-3, (f"seed {s}: the fitted sigma = exp(s) should be the root-mean-square residual {rms:.4f} (the MLE divides by n); "
                                                f"got {math.exp(sf):.4f}")
        assert abs(wf - 2.0) < 0.25 and abs(bf - 1.0) < 0.25 and abs(math.exp(sf) - 0.7) < 0.15, f"seed {s}: the data were made with (2, 1, 0.7); the fit ({wf:.3f}, {bf:.3f}, {math.exp(sf):.3f}) is too far"
    return (f"worst gradient error {worst:.1e}; seed {s}: slope {wf:.4f}, intercept {bf:.4f}, sigma {math.exp(sf):.4f} "
            f"= the least-squares fit ({w0:.4f}, {b0:.4f}) and its rms residual {rms:.4f}")


# =============================================================================
# Milestone 4: stable log-softmax
# =============================================================================
def m4():
    assert near(mod.logsumexp([1000.0, 1000.0]), 1000.0 + math.log(2)), "logsumexp([1000, 1000]) = 1000 + ln 2 (the naive exp(1000) overflows)"
    p = mod.softmax([1000.0, 1001.0, 1002.0])
    assert all(math.isfinite(x) for x in p) and vnear(p, [0.0900306, 0.2447285, 0.6652410], 1e-6), (
        f"softmax([1000, 1001, 1002]) should be [0.0900, 0.2447, 0.6652] (the naive formula overflows to nan); got {fmt(p)}. Subtract the maximum first")
    ls = mod.log_softmax([0.0, -200.0])
    assert vnear(ls, [0.0, -200.0], 1e-9), f"log_softmax([0, -200]) should be [0, -200] exactly (no log of an underflowed 0); got {fmt(ls)}"
    assert near(mod.cross_entropy([0.0, -200.0], 1), 200.0, 1e-9), "a target 200 below the maximum logit costs 200 nats, not inf"
    assert near(mod.cross_entropy([0.0, 200.0], 0), 200.0, 1e-9), "cross_entropy([0, 200], 0) is 200 (the loss of a confident mistake), not inf"
    assert near(mod.logsumexp([1000.0, 1000.0]), 1000.0 + math.log(2)), "logsumexp([1000, 1000]) = 1000 + ln 2"
    assert near(mod.logsumexp([-1000.0, -1001.0]), -1000.0 + math.log(1 + math.exp(-1))), "logsumexp must also survive very negative logits (underflow)"
    assert mod.logsumexp([-math.inf, 0.0]) == 0.0 and mod.logsumexp([-math.inf, -math.inf]) == -math.inf, "masked logits (-inf) must work: logsumexp([-inf, 0]) = 0 and logsumexp([-inf, -inf]) = -inf"
    assert vnear(mod.softmax([-math.inf, 0.0]), [0.0, 1.0]), "a -inf logit has probability exactly 0"
    assert vnear(mod.softmax([1e4, -1e4]), [1.0, 0.0]) and vnear(mod.softmax([1e308, 0.0]), [1.0, 0.0]), "huge gaps must give [1, 0], not nan"
    assert vnear(mod.softmax([5.0]), [1.0]) and mod.log_softmax([5.0]) == [0.0], "one class: probability 1, log-probability 0"
    try:
        mod.logsumexp([])
    except ValueError:
        pass
    else:
        raise AssertionError("logsumexp([]) must raise ValueError")

    # the gradient of the loss: softmax minus one-hot (the Lab 2 result), by hand then by finite differences
    g = mod.cross_entropy_grad([2.0, 1.0, 0.0], 0)
    assert vnear(g, [-0.3347590, 0.2447285, 0.0900306], 1e-6), f"cross_entropy_grad([2, 1, 0], 0) should be [-0.3348, 0.2447, 0.0900]; got {fmt(g)}"
    z = [3.0, 1.0, -2.0]
    keep = list(z)
    mod.softmax(z)
    mod.cross_entropy_grad(z, 1)
    assert z == keep, "do not modify the logits you were given"

    worst = 0.0
    for s in seeds(range(1, 9)):
        rng = random.Random(s)
        k = rng.randint(2, 8)
        z = [rng.uniform(-8, 8) for _ in range(k)]
        t = rng.randrange(k)
        pn = softmax_naive(z)
        ps = mod.softmax(z)
        assert vnear(ps, pn, 1e-12), f"seed {s}: on moderate logits {fmt(z)} softmax must agree with the textbook formula {fmt(pn)}; got {fmt(ps)}"
        assert near(sum(ps), 1.0, 1e-12) and min(ps) >= 0.0, f"seed {s}: probabilities must be non-negative and sum to 1"
        assert vnear(mod.log_softmax(z), [math.log(x) for x in pn], 1e-10), f"seed {s}: log_softmax must equal ln of the softmax on moderate logits"
        assert near(mod.cross_entropy(z, t), -math.log(pn[t]), 1e-10), f"seed {s}: cross_entropy must be -ln p[target]"
        shift = rng.choice([-5000.0, 123.0, 7000.0])
        assert vnear(mod.softmax([x + shift for x in z]), pn, 1e-9), f"seed {s}: softmax is shift-invariant: adding {shift} to every logit must not change it"
        grad = mod.cross_entropy_grad(z, t)
        assert near(sum(grad), 0.0, 1e-12), f"seed {s}: the gradient of softmax cross-entropy sums to 0"
        for i in range(k):
            hi, lo = list(z), list(z)
            hi[i] += 1e-6
            lo[i] -= 1e-6
            num = (mod.cross_entropy(hi, t) - mod.cross_entropy(lo, t)) / 2e-6
            worst = max(worst, abs(num - grad[i]))
            assert abs(num - grad[i]) < 1e-6, f"seed {s}: d loss / d z_{i} is {grad[i]:.6f} by your formula but {num:.6f} by finite differences"
    return f"softmax([1000, 1001, 1002]) = {fmt(p)}; log_softmax([0, -200]) = {fmt(ls)}; worst gradient error {worst:.1e}"


# =============================================================================
# Milestone 5: temperature, entropy and truncation
# =============================================================================
def m5():
    L = mod.LOGITS
    for T, first in [(1.0, 0.512), (0.5, 0.771), (2.0, 0.336)]:
        p = mod.softmax_t(L, T)
        assert abs(p[0] - first) < 6e-4 and near(sum(p), 1.0, 1e-12), f"softmax_t(LOGITS, {T})[0] should be about {first} (chapter 12); got {p[0]:.4f}"
    for T, bits in [(0.25, 0.279), (0.5, 1.071), (1.0, 1.897), (2.0, 2.347), (5.0, 2.540), (100.0, 2.585)]:
        h = mod.entropy(mod.softmax_t(L, T))
        assert abs(h - bits) < 6e-4, f"entropy of softmax_t(LOGITS, {T}) should be about {bits} bits (chapter 14); got {h:.4f}"
    cold = mod.softmax_t(L, 0.001)
    assert all(math.isfinite(x) for x in cold) and cold[0] > 0.999999, f"T = 0.001 divides the logits by 0.001 (3,000): the softmax must stay stable and be almost one-hot; got {fmt(cold)}"
    assert vnear(mod.softmax_t(L, 1e6), [1 / 6] * 6, 1e-4), "an enormous temperature gives the uniform distribution"
    for T in (0.0, -1.0):
        try:
            mod.softmax_t(L, T)
        except ValueError:
            continue
        raise AssertionError("softmax_t must raise ValueError for a temperature of 0 or below")
    hs = [mod.entropy(mod.softmax_t(L, T)) for T in (0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 100.0)]
    assert all(a < b for a, b in zip(hs, hs[1:])), f"entropy must rise with temperature; got {fmt(hs)}"

    assert near(mod.entropy([1 / 8] * 8), 3.0) and near(mod.entropy([1 / 8] * 8, base=math.e), math.log(8)), "a uniform distribution over 8 outcomes has 3 bits = ln 8 nats"
    assert mod.entropy([1.0, 0.0, 0.0]) == 0.0 and near(mod.entropy([0.5, 0.5, 0.0, 0.0]), 1.0), "a certain outcome has entropy 0; zero-probability entries add nothing (and must not give nan)"
    assert near(mod.perplexity([1 / 8] * 8), 8.0) and near(mod.perplexity([0.5, 0.5]), 2.0), "perplexity of a uniform distribution over K outcomes is K"
    q = [0.5, 0.25, 0.125, 0.125]
    assert near(mod.perplexity(q, 2.0), mod.perplexity(q, math.e), 1e-12), "perplexity does not depend on the unit: base ** entropy(base) is the same for base 2 and base e"
    for s in seeds(range(1, 6)):
        rng = random.Random(s)
        k = rng.randint(2, 10)
        pr = mod.normalise([rng.random() ** 3 for _ in range(k)])
        h = mod.entropy(pr)
        assert -1e-12 <= h <= math.log2(k) + 1e-12, f"seed {s}: entropy {h} must lie between 0 and log2({k})"
        assert near(mod.entropy(pr, math.e) * math.log2(math.e), h, 1e-12), f"seed {s}: 1 nat = 1.4427 bits"

    p = mod.softmax_t(L, 1.0)
    tk = mod.top_k(p, 3)
    assert vnear(tk, [0.5979219, 0.2686636, 0.1334144, 0, 0, 0], 1e-6), f"top_k(softmax(LOGITS), 3) should be [0.598, 0.269, 0.133, 0, 0, 0]; got {fmt(tk)}"
    assert vnear(mod.top_k([0.25] * 4, 2), [0.5, 0.5, 0.0, 0.0]), "ties go to the lower index, so top_k([0.25] * 4, 2) keeps the first two"
    assert vnear(mod.top_k(p, 6), p) and vnear(mod.top_k(p, 99), p), "k at least len(p) changes nothing"
    tp = mod.top_p(p, 0.9)
    assert vnear(tp, [0.5335167, 0.2397245, 0.1190437, 0.1077152, 0, 0], 1e-6), (
        f"top_p(softmax(LOGITS), 0.9) keeps FOUR tokens (the first three only reach 0.856): [0.534, 0.240, 0.119, 0.108, 0, 0]; got {fmt(tp)}")
    assert vnear(mod.top_p(p, 0.85), tk, 1e-9), "p = 0.85 is reached by three tokens (0.856), so top_p keeps exactly the top-3 set"
    assert vnear(mod.top_p([0.5, 0.25, 0.25], 0.5), [1.0, 0.0, 0.0]) and vnear(mod.top_p([0.5, 0.25, 0.25], 0.75), [2 / 3, 1 / 3, 0.0]), (
        "the nucleus is the smallest set whose mass is AT LEAST p: top_p([0.5, 0.25, 0.25], 0.5) keeps one token (mass exactly 0.5), and 0.75 keeps two")
    assert vnear(mod.top_p(p, 0.01), [1, 0, 0, 0, 0, 0]), "a tiny nucleus keeps the single most probable token"
    assert all(x > 0 for x in mod.top_p(p, 1.0)), "p = 1.0 keeps everything with positive probability"
    for bad in (lambda: mod.top_k(p, 0), lambda: mod.top_p(p, 0.0), lambda: mod.top_p(p, 1.5)):
        try:
            bad()
        except ValueError:
            continue
        raise AssertionError("top_k(p, 0), top_p(p, 0) and top_p(p, 1.5) must raise ValueError")
    for s in seeds(range(1, 7)):
        rng = random.Random(s)
        pr = mod.normalise([rng.random() ** 2 for _ in range(rng.randint(3, 12))])
        nucleus = rng.choice([0.3, 0.5, 0.8, 0.95])
        out = mod.top_p(pr, nucleus)
        kept = [i for i, x in enumerate(out) if x > 0]
        mass = sum(pr[i] for i in kept)
        smallest = min(pr[i] for i in kept)
        assert mass >= nucleus - 1e-12, f"seed {s}: the kept set has mass {mass:.4f}, below the nucleus {nucleus}"
        assert len(kept) == 1 or mass - smallest < nucleus, f"seed {s}: the kept set is not the SMALLEST that reaches {nucleus}: removing its least likely member keeps the mass at {mass - smallest:.4f}"
        assert near(sum(out), 1.0, 1e-12), f"seed {s}: the result must be renormalised"
        assert all(pr[i] >= max(pr[j] for j in range(len(pr)) if j not in kept) - 1e-15 for i in kept), f"seed {s}: kept tokens must be the MOST probable ones"

    # sample_token with scripted uniforms, then statistically
    assert mod.sample_token(FixedRng([0.0]), L) == 0 and mod.sample_token(FixedRng([0.99999]), L) == 5, "sample_token walks the softmax cumulative sums: u = 0 is token 0, u near 1 is the last"
    assert mod.sample_token(FixedRng([0.99]), L, k=2) == 1 and mod.sample_token(FixedRng([0.99]), L, p=0.5) == 0, "k = 2 leaves tokens 0 and 1 only; p = 0.5 leaves token 0 alone (it has mass 0.512)"
    assert mod.sample_token(FixedRng([0.999]), L, temperature=0.001) == 0, "at T = 0.001 the draw is the arg-max"
    rng = random.Random(5 if ONLY_SEED is None else ONLY_SEED)
    N = 20000
    want = mod.normalise([x if i < 4 else 0.0 for i, x in enumerate(softmax_naive([z / 0.8 for z in L]))])
    want = [x if x >= sorted(want)[-3] else 0.0 for x in want]          # top-3 of the T = 0.8 distribution
    want = mod.normalise(want)
    draws = [mod.sample_token(rng, L, 0.8, k=3, p=0.95) for _ in range(N)]
    for i in range(6):
        f = draws.count(i) / N
        assert within(f, want[i], math.sqrt(want[i] * (1 - want[i]) / N) if 0 < want[i] < 1 else 0.0), (
            f"T = 0.8, k = 3, p = 0.95: token {i} should have frequency {want[i]:.4f}; got {f:.4f}")
    return (f"entropy at T = 0.25, 1, 5: " + ", ".join(f"{mod.entropy(mod.softmax_t(L, T)):.3f}" for T in (0.25, 1.0, 5.0))
            + f" bits (perplexity at T = 1: {mod.perplexity(mod.softmax_t(L, 1.0)):.2f}); top_p 0.9 keeps {sum(x > 0 for x in tp)} tokens")


# =============================================================================
# Milestone 6: cross-entropy, KL, estimators, the leash
# =============================================================================
def m6():
    P = [0.7, 0.2, 0.1]
    U = [1 / 3] * 3
    assert abs(mod.xent(P, P) - H2(P)) < 1e-12 and abs(H2(P) - 1.1568) < 1e-4, "cross-entropy of a model with itself is the entropy, 1.1568 bits for p = (0.7, 0.2, 0.1)"
    assert abs(mod.kl(P, U) - 0.428) < 1e-3 and abs(mod.kl(U, P) - 0.468) < 1e-3, (
        f"for p = (0.7, 0.2, 0.1) and the uniform model: KL(p || u) = 0.428 and KL(u || p) = 0.468 bits (it is not symmetric); got {mod.kl(P, U):.4f} and {mod.kl(U, P):.4f}")
    assert abs(mod.kl(P, [0.05, 0.05, 0.9]) - 2.748) < 1e-3, "a model that puts 90% on the wrong outcome pays 2.748 extra bits"
    assert mod.kl(P, [0.8, 0.2, 0.0]) == math.inf and mod.xent(P, [0.8, 0.2, 0.0]) == math.inf, "if the model gives probability 0 to something that can happen, KL and cross-entropy are infinite"
    assert abs(mod.kl([0.8, 0.2, 0.0], P) - 0.1541) < 1e-3, "KL(q || p) with q = (0.8, 0.2, 0) is finite (0.1541 bits): terms where the first argument is 0 are skipped"
    assert mod.kl(P, P) == 0.0 and near(mod.kl(P, U, math.e) * math.log2(math.e), mod.kl(P, U), 1e-12), "KL(p || p) = 0, and nats convert to bits by 1.4427"
    for s in seeds(range(1, 8)):
        rng = random.Random(s)
        k = rng.randint(2, 7)
        p = mod.normalise([rng.random() + 0.01 for _ in range(k)])
        q = mod.normalise([rng.random() + 0.01 for _ in range(k)])
        assert near(mod.xent(p, q), H2(p) + KL2(p, q), 1e-10), f"seed {s}: cross-entropy must equal entropy + KL; got {mod.xent(p, q):.6f} vs {H2(p) + KL2(p, q):.6f}"
        assert mod.kl(p, q) >= -1e-12, f"seed {s}: KL is never negative (Gibbs' inequality); got {mod.kl(p, q)}"

    # the three single-sample estimators
    k1, k2, k3 = mod.kl_estimators(math.log(0.5), math.log(0.25))
    assert near(k1, math.log(2)) and near(k2, 0.5 * math.log(2) ** 2) and near(k3, -0.5 + math.log(2)), (
        f"logp = ln 0.5, logp_ref = ln 0.25: r = 0.5, so k1 = ln 2 = 0.6931, k2 = (ln 0.5)^2 / 2 = 0.2402, k3 = (0.5 - 1) - ln 0.5 = 0.1931; got {k1:.4f}, {k2:.4f}, {k3:.4f}")
    pi = [0.40, 0.30, 0.15, 0.10, 0.05]
    ref = [0.30, 0.30, 0.20, 0.10, 0.10]
    exact = sum(a * math.log(a / b) for a, b in zip(pi, ref))
    e1 = e2 = e3 = 0.0
    for a, b in zip(pi, ref):                                     # exact expectation under pi: no sampling noise at all
        v1, v2, v3 = mod.kl_estimators(math.log(a), math.log(b))
        e1, e2, e3 = e1 + a * v1, e2 + a * v2, e3 + a * v3
    assert near(e1, exact, 1e-12) and near(e3, exact, 1e-12), (
        f"k1 and k3 are UNBIASED: their expectation under pi equals KL = {exact:.5f} nats; the expectations were {e1:.5f} and {e3:.5f}")
    assert abs(e2 - exact) > 1e-4 and abs(e2 - exact) < 0.15 * exact, f"k2 is slightly biased: its expectation {e2:.5f} should be close to, but not equal to, {exact:.5f}"
    rng = random.Random(3)
    for _ in range(500):
        v = mod.kl_estimators(math.log(rng.uniform(0.01, 1)), math.log(rng.uniform(0.01, 1)))
        assert v[1] >= 0 and v[2] >= -1e-12, f"k2 and k3 are never negative; got {v}"

    # sampled estimates
    notes = None
    for s in seeds(range(1, 4)):
        n = 20000
        est = mod.estimate_kl(random.Random(s), pi, ref, n)
        (m1_, s1), (m2_, s2), (m3_, s3) = est["k1"], est["k2"], est["k3"]
        assert within(m1_, exact, s1 / math.sqrt(n)), f"seed {s}: the mean of k1 over {n} samples is {m1_:.5f}, more than 5 standard errors from the exact KL {exact:.5f}"
        assert within(m3_, exact, s3 / math.sqrt(n)), f"seed {s}: the mean of k3 over {n} samples is {m3_:.5f}, more than 5 standard errors from the exact KL {exact:.5f}"
        assert abs(m2_ - e2) < 5 * s2 / math.sqrt(n), f"seed {s}: the mean of k2 should settle on its own (biased) expectation {e2:.5f}; got {m2_:.5f}"
        assert s3 < s1 / 2.5, f"seed {s}: k3 should have far lower variance than k1 (k3 is never negative; k1 is negative for many samples); standard deviations {s3:.3f} and {s1:.3f}"
        notes = (s, exact, m1_, s1, m2_, s2, m3_, s3)

    # the leash
    refp, rew = [0.55, 0.25, 0.15, 0.05], [0.0, 1.0, 2.0, 5.0]
    for beta, want in [(10.0, [0.504, 0.253, 0.168, 0.075]), (3.0, [0.378, 0.240, 0.201, 0.182]), (1.0, [0.056, 0.070, 0.114, 0.760])]:
        got = mod.leash_policy(refp, rew, beta)
        assert all(abs(a - b) < 1e-3 for a, b in zip(got, want)), f"leash_policy(ref, reward, beta = {beta}) should be {want} (chapter 14); got {fmt(got)}"
    assert vnear(mod.leash_policy(refp, rew, 1e7), refp, 1e-4), "a very strong KL penalty (huge beta) leaves the policy at the reference"
    cold = mod.leash_policy(refp, rew, 0.001)
    assert all(math.isfinite(x) for x in cold) and vnear(cold, [0, 0, 0, 1], 1e-9), f"beta = 0.001 makes reward / beta = 5,000: subtract the maximum before exponentiating; got {fmt(cold)}"
    z = mod.leash_policy([0.5, 0.0, 0.5], [1.0, 9.0, 1.0], 1.0)
    assert vnear(z, [0.5, 0.0, 0.5]), "an outcome the reference rules out (probability 0) stays at 0 however high its reward"

    def objective(pol, beta):
        return sum(a * r for a, r in zip(pol, rew)) - beta * sum(a * math.log(a / b) for a, b in zip(pol, refp) if a > 0)
    for s in seeds(range(1, 4)):
        rng = random.Random(s)
        for beta in (3.0, 1.0):
            star = mod.leash_policy(refp, rew, beta)
            best = objective(star, beta)
            for _ in range(300):
                other = mod.normalise([x * math.exp(rng.gauss(0, 0.5)) for x in star] if rng.random() < 0.5 else [rng.random() + 1e-3 for _ in range(4)])
                assert objective(other, beta) <= best + 1e-12, f"seed {s}, beta {beta}: the policy {fmt(other)} scores {objective(other, beta):.5f}, above yours ({best:.5f}); yours is not the maximiser"
    # the DPO observation: the reward is beta times the log ratio, plus a constant that is the same for every outcome
    star = mod.leash_policy(refp, rew, 2.0)
    consts = [2.0 * math.log(a / b) - r for a, b, r in zip(star, refp, rew)]
    assert max(consts) - min(consts) < 1e-9, f"beta * ln(pi*/ref) - reward must be the same constant (-beta ln Z) for every outcome; got {fmt(consts)}"
    star3 = mod.leash_policy(refp, rew, 3.0)
    ex_r, ex_kl = sum(a * r for a, r in zip(star3, rew)), sum(a * math.log(a / b) for a, b in zip(star3, refp))
    assert abs(ex_r - 1.550) < 1e-3 and abs(ex_kl - 0.141) < 1e-3, f"at beta = 3 the chapter reports expected reward 1.550 and KL 0.141 nats; got {ex_r:.3f} and {ex_kl:.3f}"
    s, ex, a1, d1, a2, d2, a3, d3 = notes
    return (f"seed {s}, exact KL {ex:.5f} nats from 20,000 samples: k1 {a1:.5f} (sd {d1:.3f}), k2 {a2:.5f} (sd {d2:.3f}), k3 {a3:.5f} (sd {d3:.3f})\n"
            f"leash at beta = 3: expected reward {ex_r:.3f}, KL {ex_kl:.3f} nats")


MILESTONES = [
    (1, "Milestone 1: samplers from uniform numbers", m1),
    (2, "Milestone 2: likelihoods and maximum-likelihood fits", m2),
    (3, "Milestone 3: a line fitted by gradient descent on the NLL", m3),
    (4, "Milestone 4: a stable log-softmax and its gradient", m4),
    (5, "Milestone 5: temperature, entropy and truncation", m5),
    (6, "Milestone 6: cross-entropy, KL, its estimators and the leash", m6),
]

if __name__ == "__main__":
    t0 = time.time()
    print(f"Lab 4 checks against {target}.py\n")
    for n, name, fn in MILESTONES:
        check(n, name, fn)
    print(f"\n{sum(results)}/{len(results)} milestones passing  ({time.time() - t0:.1f} s)")
    sys.exit(0 if all(results) else 1)
