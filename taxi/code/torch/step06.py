# Step 6, the library way: torch.optim.SGD's step is gd_step. It reads the
# slope from w.grad; here the slope comes from nudging, as in numeric_grad.
import torch

def bowl(w):                           # the toy bowl, lowest at (3, -1)
    return (w[0] - 3) ** 2 + 2 * (w[1] + 1) ** 2

def nudged_slope(f, w, eps=1e-6):      # numeric_grad, on tensors
    slope = torch.zeros_like(w)
    for i in range(len(w)):
        nudge = torch.zeros_like(w)
        nudge[i] = eps
        slope[i] = (f(w + nudge) - f(w - nudge)) / (2 * eps)
    return slope

w = torch.zeros(2, dtype=torch.float64, requires_grad=True)
opt = torch.optim.SGD([w], lr=0.1)
s = nudged_slope(bowl, w.detach())
print(f"slope at (0, 0): ({s[0]:.4f}, {s[1]:.4f})")
for step in range(200):
    w.grad = nudged_slope(bowl, w.detach())    # where opt.step() looks
    opt.step()                                 # w <- w - lr * w.grad
    if step == 0:
        print(f"after 1 step: ({w[0]:.4f}, {w[1]:.4f})")
print(f"after 200 steps: ({w[0]:.4f}, {w[1]:.4f})")

start = torch.zeros(2, dtype=torch.float64, requires_grad=True)
print("gradcheck, nudging against autograd:",
      torch.autograd.gradcheck(bowl, (start,)))
