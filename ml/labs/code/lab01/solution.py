"""Lab 1 (reference solution): linear and logistic regression from scratch, in plain Python lists.

Conventions (the same as chapters 5 and 6 of this course):

    X          list of rows, shape (n_samples, n_features); y is a list of length n_samples
    theta      weights WITH the intercept first: theta = [b, w1, ..., wd]
    A          the design matrix: X with a leading column of ones, so predictions are A @ theta
    ridge      loss = sum (y - yhat)^2 + alpha * sum w_j^2          (features standardised, intercept free)
    lasso      loss = (1 / 2n) sum (y - yhat)^2 + alpha * sum |w_j|  (features standardised, intercept free)
    logistic   loss = mean log-loss + (l2 / 2) * sum w_j^2           (features standardised, intercept free)

Everything is deterministic: every random number comes from a seeded random.Random.
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
    return sum(x * y for x, y in zip(a, b))


def transpose(M):
    """Transpose of a matrix given as a list of rows."""
    return [list(col) for col in zip(*M)]


def matmul(A, B):
    """Matrix product A @ B for lists of rows: (m, k) @ (k, n) -> (m, n)."""
    Bt = transpose(B)
    return [[dot(row, col) for col in Bt] for row in A]


def solve(A, b):
    """Solve A x = b for square A by Gaussian elimination with partial pivoting.

    Raises ValueError("singular matrix") if a pivot is negligible next to the
    largest entry of A (a duplicated or constant-multiple column does this).
    Neither A nor b is modified.
    """
    n = len(A)
    M = [list(map(float, A[i])) + [float(b[i])] for i in range(n)]   # augmented matrix
    scale = max(abs(v) for row in A for v in row) or 1.0
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(M[r][c]))              # the row with the biggest pivot
        if abs(M[p][c]) < 1e-12 * scale:
            raise ValueError("singular matrix")
        M[c], M[p] = M[p], M[c]
        for r in range(c + 1, n):
            f = M[r][c] / M[c][c]
            if f:
                M[r] = [a - f * k for a, k in zip(M[r], M[c])]
    x = [0.0] * n
    for r in range(n - 1, -1, -1):                                    # back-substitution
        x[r] = (M[r][n] - sum(M[r][j] * x[j] for j in range(r + 1, n))) / M[r][r]
    return x


def add_intercept(X):
    """Prepend a column of ones to every row: the design matrix A."""
    return [[1.0] + list(row) for row in X]


def fit_ols(X, y):
    """Ordinary least squares by the normal equations (A^T A) theta = A^T y.

    Returns theta = [b, w1, ..., wd]. Raises ValueError if A^T A is singular.
    """
    A = add_intercept(X)
    At = transpose(A)
    return solve(matmul(At, A), [dot(col, y) for col in At])


def predict_linear(X, theta):
    """Predictions theta[0] + sum_j theta[j+1] * x[j] for every row."""
    return [theta[0] + dot(theta[1:], row) for row in X]


def mse(y, p):
    """Mean squared error."""
    return sum((a - b) ** 2 for a, b in zip(y, p)) / len(y)


def r2(y, p):
    """Coefficient of determination: 1 - SS_res / SS_tot (1.0 is perfect, 0.0 is 'predict the mean')."""
    ybar = sum(y) / len(y)
    ss_res = sum((a - b) ** 2 for a, b in zip(y, p))
    ss_tot = sum((a - ybar) ** 2 for a in y)
    return 1.0 - ss_res / ss_tot


# =============================================================================
# Milestone 2: gradient descent, and why feature scale matters
# =============================================================================
def column_stats(X):
    """Per-column (means, standard deviations), the standard deviation being the population one
    (divide by n). A constant column gets sd = 1.0 so that dividing by it is harmless."""
    n = len(X)
    mu = [sum(col) / n for col in zip(*X)]
    sd = [math.sqrt(sum((v - m) ** 2 for v in col) / n) or 1.0 for col, m in zip(zip(*X), mu)]
    return mu, sd


def standardise(X, mu, sd):
    """(x - mu) / sd, column by column. mu and sd come from the TRAINING rows only."""
    return [[(v - m) / s for v, m, s in zip(row, mu, sd)] for row in X]


def mse_gradient(X, y, theta):
    """Gradient of the mean squared error with respect to theta = [b, w...]:  (2/n) A^T (A theta - y)."""
    n = len(y)
    resid = [p - t for p, t in zip(predict_linear(X, theta), y)]
    g = [2.0 * sum(resid) / n]
    for col in zip(*X):
        g.append(2.0 * dot(col, resid) / n)
    return g


def gradient_descent(loss_fn, grad_fn, theta0, lr, steps):
    """Plain batch gradient descent. Returns (theta, history).

    history[t] is loss_fn(theta) at the START of step t (so history[0] is the loss of theta0)
    and has exactly `steps` entries. Each step is theta <- theta - lr * grad_fn(theta).
    """
    theta, history = list(theta0), []
    for _ in range(steps):
        history.append(loss_fn(theta))
        g = grad_fn(theta)
        theta = [t - lr * gj for t, gj in zip(theta, g)]
    return theta, history


def gd_linear(X, y, lr, steps):
    """Fit a linear model by gradient descent on the MSE, starting from all zeros.

    Returns (theta, history) with theta = [b, w...] in the units of the X you pass in.
    """
    def loss(th):
        return mse(y, predict_linear(X, th))

    def grad(th):
        return mse_gradient(X, y, th)

    return gradient_descent(loss, grad, [0.0] * (len(X[0]) + 1), lr, steps)


# =============================================================================
# Milestone 3: ridge regression and choosing alpha by cross-validation
# =============================================================================
def ridge_fit(X, y, alpha):
    """Ridge regression: minimise sum (y - yhat)^2 + alpha * sum w_j^2 on standardised features.

    Standardise X with column_stats, centre y, and solve (Z^T Z + alpha I) w = Z^T (y - mean(y)).
    The intercept is never penalised: it is the mean of y once the columns are centred.
    Returns a StdLinear. alpha = 0 is ordinary least squares.
    """
    mu, sd = column_stats(X)
    Z = standardise(X, mu, sd)
    ybar = sum(y) / len(y)
    yc = [v - ybar for v in y]
    G = matmul(transpose(Z), Z)
    for j in range(len(G)):
        G[j][j] += alpha
    w = solve(G, [dot(col, yc) for col in zip(*Z)])
    return StdLinear(mu, sd, ybar, w)


def kfold_rmse(fit, X, y, k=5):
    """Mean validation RMSE over k folds. Row i belongs to fold i % k.

    fit(X_train, y_train) must return an object with .predict(X). Each fold is scored on
    the rows it did not train on; the result is the average of the k fold RMSEs.
    """
    scores = []
    for f in range(k):
        tr = [i for i in range(len(y)) if i % k != f]
        va = [i for i in range(len(y)) if i % k == f]
        model = fit([X[i] for i in tr], [y[i] for i in tr])
        scores.append(rmse([y[i] for i in va], model.predict([X[i] for i in va])))
    return sum(scores) / k


def select_alpha(X, y, alphas, k=5):
    """The alpha with the lowest k-fold CV RMSE for ridge_fit, as (alpha, cv_rmse).
    Ties go to the first alpha in the list."""
    best = None
    for a in alphas:
        score = kfold_rmse(lambda Xt, yt, a=a: ridge_fit(Xt, yt, a), X, y, k)
        if best is None or score < best[1]:
            best = (a, score)
    return best


# =============================================================================
# Milestone 4: the lasso, by coordinate descent
# =============================================================================
def soft_threshold(r, t):
    """S(r, t) = sign(r) * max(|r| - t, 0): shrink r towards zero by t, and stop at zero."""
    if r > t:
        return r - t
    if r < -t:
        return r + t
    return 0.0


def alpha_max(X, y):
    """The smallest alpha at which the lasso solution is all zeros: max_j |(1/n) z_j . (y - mean y)|
    for standardised columns z_j."""
    mu, sd = column_stats(X)
    Z = standardise(X, mu, sd)
    n = len(y)
    ybar = sum(y) / n
    yc = [v - ybar for v in y]
    return max(abs(dot(col, yc)) / n for col in zip(*Z))


def lasso_fit(X, y, alpha, max_sweeps=1000, tol=1e-9):
    """Lasso: minimise (1/2n) sum (y - yhat)^2 + alpha * sum |w_j| on standardised features.

    Coordinate descent: cycle through the features; for feature j compute
    rho_j = (1/n) z_j . r + w_j, where r is the current residual (so rho_j is the best weight for j
    on its own, given the others), and set w_j = soft_threshold(rho_j, alpha). Stop when no weight
    moved by more than tol in a whole sweep, or after max_sweeps. Returns a StdLinear.
    """
    mu, sd = column_stats(X)
    Z = standardise(X, mu, sd)
    n, d = len(y), len(X[0])
    ybar = sum(y) / n
    r = [v - ybar for v in y]                       # residual with all weights at zero
    cols = [list(c) for c in zip(*Z)]
    w = [0.0] * d
    for _ in range(max_sweeps):
        biggest = 0.0
        for j in range(d):
            zj = cols[j]
            rho = dot(zj, r) / n + w[j]             # mean(z_j^2) = 1, so this is the one-feature optimum
            new = soft_threshold(rho, alpha)
            delta = new - w[j]
            if delta:
                r = [ri - delta * zi for ri, zi in zip(r, zj)]
                w[j] = new
                biggest = max(biggest, abs(delta))
        if biggest < tol:
            break
    return StdLinear(mu, sd, ybar, w)


# =============================================================================
# Milestone 5: the sigmoid, log-loss and the logistic gradient
# =============================================================================
def sigmoid(z):
    """1 / (1 + e^-z), without ever overflowing: sigmoid(-1000) is 0.0 and sigmoid(1000) is 1.0."""
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    e = math.exp(z)
    return e / (1.0 + e)


def log_loss(y, p, eps=1e-12):
    """Mean binary cross-entropy -[y ln p + (1 - y) ln(1 - p)], with p clipped into [eps, 1 - eps]."""
    total = 0.0
    for t, q in zip(y, p):
        q = min(max(q, eps), 1.0 - eps)
        total -= t * math.log(q) + (1.0 - t) * math.log(1.0 - q)
    return total / len(y)


def predict_proba(X, theta):
    """P(y = 1 | x) = sigmoid(theta[0] + theta[1:] . x) for every row."""
    return [sigmoid(theta[0] + dot(theta[1:], row)) for row in X]


def logistic_gradient(X, y, theta, l2=0.0):
    """Gradient of  mean log-loss + (l2 / 2) * sum_{j >= 1} theta_j^2  with respect to theta.

    The log-loss part is (1/n) A^T (p - y); the penalty adds l2 * theta_j to every entry except the
    intercept (entry 0), which is never penalised.
    """
    n = len(y)
    err = [p - t for p, t in zip(predict_proba(X, theta), y)]
    g = [sum(err) / n]
    for col, wj in zip(zip(*X), theta[1:]):
        g.append(dot(col, err) / n + l2 * wj)
    return g


def odds_ratio(w):
    """The factor by which the odds multiply when a feature rises by one unit: e^w."""
    return math.exp(w)


# =============================================================================
# Milestone 6: fitting logistic regression, with and without a penalty
# =============================================================================
def fit_logistic(X, y, l2=0.0, lr=0.5, steps=400):
    """Logistic regression by gradient descent on standardised features, from all-zero weights.

    Minimises mean log-loss + (l2 / 2) * sum w_j^2 (intercept free). Standardise with column_stats
    (training rows only), then use gradient_descent with logistic_gradient. Returns a StdLogistic.
    Plain gradient descent is stable while lr * (l2 + 0.25) stays below about 2, so a heavy penalty needs a smaller lr.
    """
    mu, sd = column_stats(X)
    Z = standardise(X, mu, sd)

    def loss(th):
        return log_loss(y, predict_proba(Z, th)) + 0.5 * l2 * sum(w * w for w in th[1:])

    def grad(th):
        return logistic_gradient(Z, y, th, l2)

    theta, _ = gradient_descent(loss, grad, [0.0] * (len(X[0]) + 1), lr, steps)
    return StdLogistic(mu, sd, theta)
