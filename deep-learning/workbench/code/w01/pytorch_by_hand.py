"""PyTorch by hand: tensors, autograd and a training loop, with PyTorch's
gradients checked against the scalar engine you built in lab 2.

    python pytorch_by_hand.py

Needs: torch (workbench/requirements.txt). No downloads."""
import argparse
import math
import random

import torch
from torch import nn

# ── 1. Settings ──────────────────────────────────────────────────────────
ap = argparse.ArgumentParser()
ap.add_argument("--steps", type=int, default=300)     # training steps
ap.add_argument("--seed", type=int, default=0)
args, _ = ap.parse_known_args()        # notebooks pass their own flags

if torch.cuda.is_available():
    DEVICE = "cuda"
else:
    DEVICE = "cpu"
torch.manual_seed(args.seed)
print(f"training device: {DEVICE}; torch {torch.__version__}")

# ── 2. Tensors: shape, dtype, device, and views that share memory ────────
x = torch.arange(12, dtype=torch.float32).reshape(3, 4)
print("\n[tensors]")
print(f"shape {tuple(x.shape)}, dtype {x.dtype}, device {x.device}, "
      f"{x.numel() * x.element_size()} bytes")
t = x.T                                  # a view: no data copied
print(f"transpose shares memory: {t.data_ptr() == x.data_ptr()}; "
      f"strides {x.stride()} -> {t.stride()}")
r = x.reshape(2, 6)
r[0, 0] = 99.0                           # write through the view
print(f"write through a view changed the original: x[0, 0] = {x[0, 0]:.0f}")
col, row = torch.zeros(3, 1), torch.zeros(4)
print(f"broadcast (3,4) + (3,1) + (4,) -> {tuple((x + col + row).shape)}")

# ── 3. The scalar engine from lab 2, cut down to what we need ────────────


class Value:
    """One number that remembers how it was made (ml-foundations lab 2)."""

    def __init__(self, data, parents=()):
        self.data, self.grad = float(data), 0.0
        self.parents, self._backward = parents, lambda: None

    def __add__(self, o):
        o = o if isinstance(o, Value) else Value(o)
        out = Value(self.data + o.data, (self, o))

        def back():
            self.grad += out.grad
            o.grad += out.grad
        out._backward = back
        return out

    def __mul__(self, o):
        o = o if isinstance(o, Value) else Value(o)
        out = Value(self.data * o.data, (self, o))

        def back():
            self.grad += o.data * out.grad
            o.grad += self.data * out.grad
        out._backward = back
        return out

    __radd__, __rmul__ = __add__, __mul__
    def __neg__(self): return self * -1.0
    def __sub__(self, o): return self + (-o)
    def __rsub__(self, o): return (-self) + o

    def __pow__(self, n):
        out = Value(self.data ** n, (self,))

        def back():
            self.grad += n * self.data ** (n - 1) * out.grad
        out._backward = back
        return out

    def tanh(self):
        th = math.tanh(self.data)
        out = Value(th, (self,))

        def back():
            self.grad += (1 - th * th) * out.grad
        out._backward = back
        return out

    def backward(self):
        order, seen = [], set()

        def visit(v):
            if id(v) not in seen:
                seen.add(id(v))
                for p in v.parents:
                    visit(p)
                order.append(v)
        visit(self)
        self.grad = 1.0
        for v in reversed(order):
            v._backward()


# ── 4. Autograd: the same expression in both engines ─────────────────────
# loss = (tanh(w x + b) - target)^2 + 0.1 w^2
W0, X0, B0, T0 = 0.8, 1.5, -0.3, 0.5
w = torch.tensor(W0, dtype=torch.float64, requires_grad=True)
b = torch.tensor(B0, dtype=torch.float64, requires_grad=True)
loss = (torch.tanh(w * X0 + b) - T0) ** 2 + 0.1 * w ** 2
loss.backward()

vw, vb = Value(W0), Value(B0)
vloss = ((vw * X0 + vb).tanh() - T0) ** 2 + 0.1 * vw ** 2
vloss.backward()

eps = 1e-6                                # central difference on w


def f(wv):
    return (math.tanh(wv * X0 + B0) - T0) ** 2 + 0.1 * wv ** 2


numeric = (f(W0 + eps) - f(W0 - eps)) / (2 * eps)
print("\n[autograd] loss = (tanh(w x + b) - t)^2 + 0.1 w^2, "
      f"w={W0}, x={X0}, b={B0}, t={T0}")
print(f"loss    torch {loss.item():.6f}   engine {vloss.data:.6f}")
print(f"dL/dw   torch {w.grad.item():.6f}   engine {vw.grad:.6f}   "
      f"finite diff {numeric:.6f}")
print(f"dL/db   torch {b.grad.item():.6f}   engine {vb.grad:.6f}")

# ── 5. A whole 2-3-1 network: every gradient, both engines ───────────────
net = nn.Sequential(nn.Linear(2, 3), nn.Tanh(), nn.Linear(3, 1)).double()
X = torch.tensor([[0.5, -1.0], [1.0, 0.3], [-0.7, 0.8], [0.2, 0.2]],
                 dtype=torch.float64)
Y = torch.tensor([[1.0], [0.0], [0.0], [1.0]], dtype=torch.float64)
torch.mean((net(X) - Y) ** 2).backward()
tg = torch.cat([p.grad.flatten() for p in net.parameters()])

W1, B1, W2, B2 = [p.detach().tolist() for p in net.parameters()]
vW1 = [[Value(v) for v in rw] for rw in W1]
vB1 = [Value(v) for v in B1]
vW2 = [Value(v) for v in W2[0]]
vB2 = Value(B2[0])
total = Value(0.0)
for xs, ys in zip(X.tolist(), Y.tolist()):
    hid = [(vW1[j][0] * xs[0] + vW1[j][1] * xs[1] + vB1[j]).tanh()
           for j in range(3)]
    out = vW2[0] * hid[0] + vW2[1] * hid[1] + vW2[2] * hid[2] + vB2
    total = total + (out - ys[0]) ** 2
(total * (1 / len(X))).backward()
eg = []                                  # same order as PyTorch's flatten
for j in range(3):
    eg += [vW1[j][0].grad, vW1[j][1].grad]
eg += [v.grad for v in vB1] + [v.grad for v in vW2] + [vB2.grad]
worst = max(abs(a - c) for a, c in zip(tg.tolist(), eg))
print(f"\n[network] {len(eg)} gradients, 2-3-1 tanh net, 4 points")
print(f"largest |torch - engine| over all {len(eg)}: {worst:.2e}")
print("first three:", " ".join(f"{a:.6f}/{c:.6f}"
                               for a, c in zip(tg.tolist()[:3], eg[:3])))

# ── 6. nn.Module and the five-line training loop ─────────────────────────


def make_moons(n, noise=0.15, seed=0):
    """Two interleaved half-circles (the shape of deep-learning lab 1)."""
    g = random.Random(seed)
    pts, ys = [], []
    for i in range(n):
        k, a = i % 2, g.uniform(0.0, math.pi)
        px = math.cos(a) if k == 0 else 1.0 - math.cos(a)
        py = math.sin(a) if k == 0 else 0.5 - math.sin(a)
        pts.append([px + g.gauss(0, noise), py + g.gauss(0, noise)])
        ys.append(float(k))
    return torch.tensor(pts), torch.tensor(ys).unsqueeze(1)


class MLP(nn.Module):
    def __init__(self, width=32):
        super().__init__()
        self.body = nn.Sequential(
            nn.Linear(2, width), nn.ReLU(),
            nn.Linear(width, width), nn.ReLU(),
            nn.Linear(width, 1))

    def forward(self, x):
        return self.body(x)


Xtr, Ytr = make_moons(400, seed=1)
Xte, Yte = make_moons(400, seed=2)
Xtr, Ytr, Xte, Yte = [a.to(DEVICE) for a in (Xtr, Ytr, Xte, Yte)]
model = MLP().to(DEVICE)
n_params = sum(p.numel() for p in model.parameters())
print(f"\n[training] parameters: {n_params} "
      f"(predicted 2*32+32 + 32*32+32 + 32+1 = {2*32+32 + 32*32+32 + 33})")
opt = torch.optim.Adam(model.parameters(), lr=0.01)
lossfn = nn.BCEWithLogitsLoss()
for step in range(args.steps + 1):
    if step % 100 == 0:
        with torch.no_grad():
            acc = ((model(Xte) > 0).float() == Yte).float().mean().item()
        print(f"step {step:4d}  train loss "
              f"{lossfn(model(Xtr), Ytr).item():.4f}  test accuracy {acc:.3f}")
    opt.zero_grad()                       # 1. clear old gradients
    loss = lossfn(model(Xtr), Ytr)        # 2. forward
    loss.backward()                       # 3. backward
    opt.step()                            # 4. update

# ── 7. The classic bug: forget zero_grad ─────────────────────────────────
p = nn.Parameter(torch.tensor([3.0]))
for call in (1, 2, 3):
    ((p * 2.0 - 10.0) ** 2).sum().backward()
    print(f"backward call {call} with no zero_grad: p.grad = "
          f"{p.grad.item():.0f}")
