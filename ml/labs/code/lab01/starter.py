"""Lab 1: linear and logistic regression from scratch, in plain Python lists.

Conventions (the same as chapters 5 and 6 of this course):

    X          list of rows, shape (n_samples, n_features); y is a list of length n_samples
    theta      weights WITH the intercept first: theta = [b, w1, ..., wd]
    A          the design matrix: X with a leading column of ones, so predictions are A @ theta
    ridge      loss = sum (y - yhat)^2 + alpha * sum w_j^2          (features standardised, intercept free)
    lasso      loss = (1 / 2n) sum (y - yhat)^2 + alpha * sum |w_j|  (features standardised, intercept free)
    logistic   loss = mean log-loss + (l2 / 2) * sum w_j^2           (features standardised, intercept free)

Everything is deterministic: every random number comes from a seeded random.Random.

What is GIVEN: the data generators, rmse, numeric_gradient and the two model containers
(StdLinear, StdLogistic). What YOU write is marked TODO:

    1  dot, transpose, matmul, solve, add_intercept, fit_ols, predict_linear, mse, r2
    2  column_stats, standardise, mse_gradient, gradient_descent, gd_linear
    3  ridge_fit, kfold_rmse, select_alpha
    4  soft_threshold, alpha_max, lasso_fit
    5  sigmoid, log_loss, predict_proba, logistic_gradient, odds_ratio
    6  fit_logistic

`python3 check.py` runs the milestones; the lab page explains each one.
"""
import math
import random
from dataclasses import dataclass


# =============================================================================
# GIVEN: synthetic data, small containers, and helpers that are not the lesson
# =============================================================================
def make_rent(seed, n=200):
    """Chapter 5's lettings data: rent = 300 + 11*area - 25*dist - 2*age + N(0, 60^2).

    Returns (X, y) with columns [area (m^2), dist (km), age (years)].
    """
    rng = random.Random(seed)
    X, y = [], []
    for _ in range(n):
        area, dist, age = rng.uniform(25, 120), rng.uniform(0.5, 15), rng.uniform(0, 80)
        X.append([area, dist, age])
        y.append(300 + 11 * area - 25 * dist - 2 * age + rng.gauss(0, 60))
    return X, y


def make_sine(seed, n=18, sigma=0.3, degree=12):
    """Chapter 6's sine world: y = sin(2 pi x) + N(0, sigma^2), x in [0, 1].

    The features are the polynomial columns u, u^2, ..., u^degree with u = 2x - 1,
    which are strongly correlated (the hard case for plain least squares).
    """
    rng = random.Random(seed)
    xs = [rng.random() for _ in range(n)]
    X = [[(2 * x - 1) ** k for k in range(1, degree + 1)] for x in xs]
    y = [math.sin(2 * math.pi * x) + rng.gauss(0, sigma) for x in xs]
    return X, y


def make_sparse(seed, n=60, d=20, sigma=3.0):
    """d standard-normal features, of which only the first five matter.

    True weights are [4, -3, 2, -2, 1.5, 0, 0, ...]; the intercept is 1.
    Returns (X, y, support) where support = [0, 1, 2, 3, 4].
    """
    rng = random.Random(seed)
    w = [4.0, -3.0, 2.0, -2.0, 1.5] + [0.0] * (d - 5)
    X = [[rng.gauss(0, 1) for _ in range(d)] for _ in range(n)]
    y = [1.0 + sum(a * b for a, b in zip(row, w)) + rng.gauss(0, sigma) for row in X]
    return X, y, [0, 1, 2, 3, 4]


def _poisson(rng, lam):
    """Knuth's method: count uniform draws until their product drops below e^-lam."""
    limit, k, prod = math.exp(-lam), 0, rng.random()
    while prod > limit:
        k += 1
        prod *= rng.random()
    return k


def make_churn(seed, n=700):
    """Chapter 5's churn data: columns [tenure (months), spend, tickets], y = 1 if the customer churned.

    log-odds = -0.3 - 0.06 (tenure - 24) + 0.02 (spend - 50) + 0.5 (tickets - 1.5)
    """
    rng = random.Random(seed)
    X, y = [], []
    for _ in range(n):
        tenure, spend, tickets = rng.uniform(1, 60), rng.gauss(50, 20), _poisson(rng, 1.5)
        z = -0.3 - 0.06 * (tenure - 24) + 0.02 * (spend - 50) + 0.5 * (tickets - 1.5)
        X.append([tenure, spend, float(tickets)])
        y.append(1.0 if rng.random() < 1 / (1 + math.exp(-z)) else 0.0)
    return X, y


def make_separable(seed, n=40):
    """Two features, labels given by the sign of x0 + x1, with a gap: perfectly separable data."""
    rng = random.Random(seed)
    X, y = [], []
    while len(X) < n:
        a, b = rng.uniform(-3, 3), rng.uniform(-3, 3)
        if abs(a + b) > 0.6:
            X.append([a, b])
            y.append(1.0 if a + b > 0 else 0.0)
    return X, y


def rmse(y, p):
    """Root mean squared error (given, so the later milestones can score without your mse)."""
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(y, p)) / len(y))


def numeric_gradient(f, theta, eps=1e-6):
    """Central finite differences: the gradient of f at theta, for checking your analytic one."""
    g = []
    for j in range(len(theta)):
        up, down = list(theta), list(theta)
        up[j] += eps
        down[j] -= eps
        g.append((f(up) - f(down)) / (2 * eps))
    return g


@dataclass
class StdLinear:
    """A linear model fitted on standardised features (used by ridge and lasso).

    prediction = y_mean + sum_j w[j] * (x[j] - mu[j]) / sd[j]
    """
    mu: list
    sd: list
    y_mean: float
    w: list

    def predict(self, X):
        return [self.y_mean + sum(w * (v - m) / s for w, v, m, s in zip(self.w, row, self.mu, self.sd))
                for row in X]

    def to_original(self):
        """The same model in the original units, as theta = [b, w1, ...]."""
        slopes = [w / s for w, s in zip(self.w, self.sd)]
        b = self.y_mean - sum(sl * m for sl, m in zip(slopes, self.mu))
        return [b] + slopes


@dataclass
class StdLogistic:
    """A logistic model fitted on standardised features: theta = [b, w1, ...] is in standardised units."""
    mu: list
    sd: list
    theta: list

    def predict_proba(self, X):
        Z = [[(v - m) / s for v, m, s in zip(row, self.mu, self.sd)] for row in X]
        return [sigmoid(self.theta[0] + sum(w * z for w, z in zip(self.theta[1:], row))) for row in Z]

    def to_original(self):
        slopes = [w / s for w, s in zip(self.theta[1:], self.sd)]
        return [self.theta[0] - sum(sl * m for sl, m in zip(slopes, self.mu))] + slopes


# =============================================================================
# Milestone 1: the closed form, from nothing
# =============================================================================
def dot(a, b):
    """Dot product of two equal-length lists."""
    raise NotImplementedError("TODO milestone 1: dot")


def transpose(M):
    """Transpose of a matrix given as a list of rows."""
    raise NotImplementedError("TODO milestone 1: transpose")


def matmul(A, B):
    """Matrix product A @ B for lists of rows: (m, k) @ (k, n) -> (m, n)."""
    raise NotImplementedError("TODO milestone 1: matmul")


def solve(A, b):
    """Solve A x = b for square A by Gaussian elimination with partial pivoting.

    Raises ValueError("singular matrix") if a pivot is negligible next to the
    largest entry of A (a duplicated or constant-multiple column does this).
    Neither A nor b is modified.
    """
    raise NotImplementedError("TODO milestone 1: solve")


def add_intercept(X):
    """Prepend a column of ones to every row: the design matrix A."""
    raise NotImplementedError("TODO milestone 1: add_intercept")


def fit_ols(X, y):
    """Ordinary least squares by the normal equations (A^T A) theta = A^T y.

    Returns theta = [b, w1, ..., wd]. Raises ValueError if A^T A is singular.
    """
    raise NotImplementedError("TODO milestone 1: fit_ols")


def predict_linear(X, theta):
    """Predictions theta[0] + sum_j theta[j+1] * x[j] for every row."""
    raise NotImplementedError("TODO milestone 1: predict_linear")


def mse(y, p):
    """Mean squared error."""
    raise NotImplementedError("TODO milestone 1: mse")


def r2(y, p):
    """Coefficient of determination: 1 - SS_res / SS_tot (1.0 is perfect, 0.0 is 'predict the mean')."""
    raise NotImplementedError("TODO milestone 1: r2")


# =============================================================================
# Milestone 2: gradient descent, and why feature scale matters
# =============================================================================
def column_stats(X):
    """Per-column (means, standard deviations), the standard deviation being the population one
    (divide by n). A constant column gets sd = 1.0 so that dividing by it is harmless."""
    raise NotImplementedError("TODO milestone 2: column_stats")


def standardise(X, mu, sd):
    """(x - mu) / sd, column by column. mu and sd come from the TRAINING rows only."""
    raise NotImplementedError("TODO milestone 2: standardise")


def mse_gradient(X, y, theta):
    """Gradient of the mean squared error with respect to theta = [b, w...]:  (2/n) A^T (A theta - y)."""
    raise NotImplementedError("TODO milestone 2: mse_gradient")


def gradient_descent(loss_fn, grad_fn, theta0, lr, steps):
    """Plain batch gradient descent. Returns (theta, history).

    history[t] is loss_fn(theta) at the START of step t (so history[0] is the loss of theta0)
    and has exactly `steps` entries. Each step is theta <- theta - lr * grad_fn(theta).
    """
    raise NotImplementedError("TODO milestone 2: gradient_descent")


def gd_linear(X, y, lr, steps):
    """Fit a linear model by gradient descent on the MSE, starting from all zeros.

    Returns (theta, history) with theta = [b, w...] in the units of the X you pass in.
    """
    raise NotImplementedError("TODO milestone 2: gd_linear")


# =============================================================================
# Milestone 3: ridge regression and choosing alpha by cross-validation
# =============================================================================
def ridge_fit(X, y, alpha):
    """Ridge regression: minimise sum (y - yhat)^2 + alpha * sum w_j^2 on standardised features.

    Standardise X with column_stats, centre y, and solve (Z^T Z + alpha I) w = Z^T (y - mean(y)).
    The intercept is never penalised: it is the mean of y once the columns are centred.
    Returns a StdLinear. alpha = 0 is ordinary least squares.
    """
    raise NotImplementedError("TODO milestone 3: ridge_fit")


def kfold_rmse(fit, X, y, k=5):
    """Mean validation RMSE over k folds. Row i belongs to fold i % k.

    fit(X_train, y_train) must return an object with .predict(X). Each fold is scored on
    the rows it did not train on; the result is the average of the k fold RMSEs.
    """
    raise NotImplementedError("TODO milestone 3: kfold_rmse")


def select_alpha(X, y, alphas, k=5):
    """The alpha with the lowest k-fold CV RMSE for ridge_fit, as (alpha, cv_rmse).
    Ties go to the first alpha in the list."""
    raise NotImplementedError("TODO milestone 3: select_alpha")


# =============================================================================
# Milestone 4: the lasso, by coordinate descent
# =============================================================================
def soft_threshold(r, t):
    """S(r, t) = sign(r) * max(|r| - t, 0): shrink r towards zero by t, and stop at zero."""
    raise NotImplementedError("TODO milestone 4: soft_threshold")


def alpha_max(X, y):
    """The smallest alpha at which the lasso solution is all zeros: max_j |(1/n) z_j . (y - mean y)|
    for standardised columns z_j."""
    raise NotImplementedError("TODO milestone 4: alpha_max")


def lasso_fit(X, y, alpha, max_sweeps=1000, tol=1e-9):
    """Lasso: minimise (1/2n) sum (y - yhat)^2 + alpha * sum |w_j| on standardised features.

    Coordinate descent: cycle through the features; for feature j compute
    rho_j = (1/n) z_j . r + w_j, where r is the current residual (so rho_j is the best weight for j
    on its own, given the others), and set w_j = soft_threshold(rho_j, alpha). Stop when no weight
    moved by more than tol in a whole sweep, or after max_sweeps. Returns a StdLinear.
    """
    raise NotImplementedError("TODO milestone 4: lasso_fit")


# =============================================================================
# Milestone 5: the sigmoid, log-loss and the logistic gradient
# =============================================================================
def sigmoid(z):
    """1 / (1 + e^-z), without ever overflowing: sigmoid(-1000) is 0.0 and sigmoid(1000) is 1.0."""
    raise NotImplementedError("TODO milestone 5: sigmoid")


def log_loss(y, p, eps=1e-12):
    """Mean binary cross-entropy -[y ln p + (1 - y) ln(1 - p)], with p clipped into [eps, 1 - eps]."""
    raise NotImplementedError("TODO milestone 5: log_loss")


def predict_proba(X, theta):
    """P(y = 1 | x) = sigmoid(theta[0] + theta[1:] . x) for every row."""
    raise NotImplementedError("TODO milestone 5: predict_proba")


def logistic_gradient(X, y, theta, l2=0.0):
    """Gradient of  mean log-loss + (l2 / 2) * sum_{j >= 1} theta_j^2  with respect to theta.

    The log-loss part is (1/n) A^T (p - y); the penalty adds l2 * theta_j to every entry except the
    intercept (entry 0), which is never penalised.
    """
    raise NotImplementedError("TODO milestone 5: logistic_gradient")


def odds_ratio(w):
    """The factor by which the odds multiply when a feature rises by one unit: e^w."""
    raise NotImplementedError("TODO milestone 5: odds_ratio")


# =============================================================================
# Milestone 6: fitting logistic regression, with and without a penalty
# =============================================================================
def fit_logistic(X, y, l2=0.0, lr=0.5, steps=400):
    """Logistic regression by gradient descent on standardised features, from all-zero weights.

    Minimises mean log-loss + (l2 / 2) * sum w_j^2 (intercept free). Standardise with column_stats
    (training rows only), then use gradient_descent with logistic_gradient. Returns a StdLogistic.
    Plain gradient descent is stable while lr * (l2 + 0.25) stays below about 2, so a heavy penalty needs a smaller lr.
    """
    raise NotImplementedError("TODO milestone 6: fit_logistic")
