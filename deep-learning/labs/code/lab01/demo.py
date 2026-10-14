"""Train the network on two moons and draw what it learned.

    python3 demo.py             # uses your starter.py
    python3 demo.py solution    # uses the reference solution
"""
import importlib
import sys

sys.dont_write_bytecode = True
nn = importlib.import_module(sys.argv[1] if len(sys.argv) > 1 else "starter")

X, y = nn.make_moons(200, seed=1)
Xt, yt = nn.make_moons(200, seed=2)

print("hidden units -> accuracy after 300 epochs of full-batch gradient descent (lr 0.5)")
for H in (1, 2, 4, 8, 16):
    p = nn.init_params((2, H, 2), seed=0)
    nn.train(p, X, y, lr=0.5, epochs=300)
    print(f"  H = {H:2d}   train {nn.accuracy(p, X, y):.3f}   test {nn.accuracy(p, Xt, yt):.3f}")

params = nn.init_params((2, 16, 2), seed=0)
losses = nn.train(params, X, y, lr=0.5, epochs=300)
print("\nloss every 50 epochs:", "  ".join(f"{losses[i]:.3f}" for i in range(0, 300, 50)), f"  final {losses[-1]:.3f}")

# Decision map: '.' where the network says class 0, '#' where it says class 1; the data on top as 'o' and 'x'.
W, Hh = 60, 22
x0, x1, y0, y1 = -1.6, 2.6, -1.1, 1.6
grid = [[(x0 + (x1 - x0) * (c + 0.5) / W, y1 - (y1 - y0) * (r + 0.5) / Hh) for c in range(W)] for r in range(Hh)]
rows = [["#" if k else "." for k in nn.predict(params, line)] for line in grid]
for (a, b), label in zip(Xt, yt):
    c, r = int((a - x0) / (x1 - x0) * W), int((y1 - b) / (y1 - y0) * Hh)
    if 0 <= c < W and 0 <= r < Hh:
        rows[r][c] = "x" if label else "o"
print("\nnetwork's decision map (o = class 0 test point, x = class 1 test point)")
print("\n".join("".join(r) for r in rows))
