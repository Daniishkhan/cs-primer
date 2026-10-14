import numpy as np
from ts01 import make_series

def naive(hist, h):            return np.full(h, hist[-1])
def snaive(hist, h, m=7):      return np.array([hist[-m + (k % m)] for k in range(h)])
def mean_all(hist, h):         return np.full(h, hist.mean())
def drift(hist, h):            return hist[-1] + (hist[-1] - hist[0]) / (len(hist) - 1) * np.arange(1, h + 1)
def ma_season(hist, h, m=7, k=4):   # average of the same weekday over the last k weeks
    return np.array([np.mean([hist[-m * j + (i % m)] for j in range(1, k + 1)]) for i in range(h)])

def ses(hist, h, alpha=0.3):
    l = hist[0]
    for v in hist[1:]: l = alpha * v + (1 - alpha) * l
    return np.full(h, l)

def holt_winters(hist, h, m=7, alpha=0.2, beta=0.01, gamma=0.2):
    """Additive Holt-Winters (level, trend, seasonal) with fixed smoothing weights."""
    n = len(hist); l = hist[:m].mean(); b = (hist[m:2*m].mean() - hist[:m].mean()) / m
    s = list(hist[:m] - l)
    for i in range(m, n):
        v = hist[i]; sl = s[i - m]
        l_new = alpha * (v - sl) + (1 - alpha) * (l + b)
        b = beta * (l_new - l) + (1 - beta) * b
        s.append(gamma * (v - l_new) + (1 - gamma) * sl); l = l_new
    return np.array([l + (k + 1) * b + s[n - m + (k % m)] for k in range(h)])

def mase(actual, fc, hist, m=7):
    """Mean absolute scaled error: MAE divided by the in-sample MAE of the seasonal-naive forecast."""
    scale = np.mean(np.abs(hist[m:] - hist[:-m]))
    return np.mean(np.abs(actual - fc)) / scale

def origins(n, first, h, step):
    return list(range(first, n - h + 1, step))
