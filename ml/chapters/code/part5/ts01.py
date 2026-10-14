"""Anatomy of a series: trend + weekly + yearly seasonality + noise, recovered by least squares."""
import numpy as np

def make_series(seed=7, days=1096):
    rng = np.random.default_rng(seed)
    t = np.arange(days)
    weekly = np.array([-14, -10, -6, -2, 8, 22, 2.0])             # effect by day of week (Mon..Sun)
    season = 25 * np.sin(2 * np.pi * (t - 80) / 365.25)           # yearly cycle, peak in late June
    noise = np.zeros(days)
    for i in range(1, days):                                      # AR(1) noise: today's surprise carries over a little
        noise[i] = 0.5 * noise[i - 1] + rng.normal(0, 10)
    return 200 + 0.05 * t + weekly[t % 7] + season + noise, t

if __name__ == "__main__":
    y, t = make_series()
    # Regression on calendar features: intercept, linear trend, six weekday dummies, yearly sine and cosine
    dow = np.eye(7)[t % 7][:, 1:]
    X = np.c_[np.ones_like(t), t, dow, np.sin(2 * np.pi * t / 365.25), np.cos(2 * np.pi * t / 365.25)]
    beta = np.linalg.lstsq(X, y, rcond=None)[0]
    resid = y - X @ beta
    print(f"{len(y)} days; mean {y.mean():.1f}, sd {y.std():.1f}")
    print(f"trend per day: fitted {beta[1]:.3f}   (true 0.050)")
    wk = np.r_[0, beta[2:8]]; wk = wk - wk.mean()
    print("weekday effects Mon..Sun, fitted:", np.round(wk, 1), " true:", np.array([-14, -10, -6, -2, 8, 22, 2.0]) - np.mean([-14, -10, -6, -2, 8, 22, 2.0]))
    print(f"yearly amplitude: fitted {np.hypot(beta[8], beta[9]):.1f}   (true 25.0)")
    print(f"residual sd {resid.std():.1f}; lag-1 autocorrelation of residuals {np.corrcoef(resid[1:], resid[:-1])[0, 1]:.2f}   (true noise: sd 11.5, lag-1 0.50)")
    share = 1 - resid.var() / y.var()
    print(f"share of the variance explained by trend + seasonality: {share:.1%}")
