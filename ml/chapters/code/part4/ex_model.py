import numpy as np
names = ["area_m2", "age_years", "dist_centre_km", "rooms", "noise"]
def make(n, rng):
    area = rng.normal(95, 30, n).clip(30, 250)
    age = rng.uniform(0, 80, n)
    dist = rng.gamma(3, 2.5, n)
    rooms = np.round(area / 28 + rng.normal(0, 0.5, n)).clip(1, 9)          # strongly tied to area
    noise = rng.normal(size=n)
    price = (2.4 * area * (1 + 0.8 * np.exp(-dist / 4)) - 0.9 * np.minimum(age, 40) + 0.2 * (age - 40).clip(0) * (age > 40)
             + 15.0 * (area > 120) * (dist < 5) + rng.normal(0, 18, n))      # price in thousands of pounds
    return np.c_[area, age, dist, rooms, noise], price

class MLP:
    def __init__(self, d, h, rng): 
        self.W1 = rng.normal(0, 0.5, (d, h)); self.b1 = np.zeros(h); self.W2 = rng.normal(0, 0.5, h); self.b2 = 0.0
    def forward(self, X):
        A = np.tanh(X @ self.W1 + self.b1); return A, A @ self.W2 + self.b2
def fit_mlp(X, y, h=24, epochs=3000, lr=0.02, seed=0):
    rng = np.random.default_rng(seed)
    mu, sd = X.mean(0), X.std(0); ym, ys = y.mean(), y.std()
    Z = (X - mu) / sd; t = (y - ym) / ys
    m = MLP(X.shape[1], h, rng)
    ps = [m.W1, m.b1, m.W2]; vel = [np.zeros_like(p) for p in ps]; vb = 0.0
    for e in range(epochs):
        A, out = m.forward(Z); err = (out - t) / len(t)
        gW2 = A.T @ err; gb2 = err.sum(); dA = np.outer(err, m.W2) * (1 - A ** 2)
        grads = [Z.T @ dA, dA.sum(0), gW2]
        for i, (p, g) in enumerate(zip(ps, grads)):
            vel[i] = 0.9 * vel[i] - lr * g * 10; p += vel[i]
        vb = 0.9 * vb - lr * gb2 * 10; m.b2 += vb
    return lambda Xn: m.forward((Xn - mu) / sd)[1] * ys + ym
def r2(y, p): return 1 - np.sum((y - p) ** 2) / np.sum((y - y.mean()) ** 2)
