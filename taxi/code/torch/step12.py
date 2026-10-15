# Step 12, the library way: the expressions of check.py on tensors, with
# .backward() doing what your backward does.
import torch

a = torch.tensor(2.0, requires_grad=True)
b = torch.tensor(3.0, requires_grad=True)
(a * b + a).backward()
print(f"d(ab + a)/da = {a.grad.item():.0f}, d/db = {b.grad.item():.0f}")

x = torch.tensor(1.5, requires_grad=True)
((x * x + x).relu() * 3).backward()          # x is used three times
print(f"through relu and reuse of x: {x.grad.item():.0f}")

x2 = torch.tensor(-0.4, requires_grad=True)
((x2 * 2).relu() + x2).backward()            # the relu is off
print(f"relu off, only the direct path: {x2.grad.item():.0f}")

w = torch.tensor([0.7, -1.3], dtype=torch.float64, requires_grad=True)
f = (w[0] * w[1] + w[0]) * (w[0] - 1)
f.backward()
print(f"(w0 w1 + w0)(w0 - 1) at (0.7, -1.3): {w.grad[0]:.6f}, {w.grad[1]:.6f}")

(a * b).backward()                           # a second backward, on a * b
print(f"a second backward adds b = 3: a.grad is now {a.grad.item():.0f}")
