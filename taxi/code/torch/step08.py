# Step 8, the library way: torch.optim.SGD is the loop's update. These few
# lines are the training loop of almost every PyTorch script.
import torch
import torch.nn.functional as F
from common import design_matrix, load_rides, targets

rides = load_rides()[:500]                 # the same 500 rides as the check
X, y = design_matrix(rides), targets(rides)

def train(lr, steps):
    w = torch.zeros(3, dtype=torch.float64, requires_grad=True)
    opt = torch.optim.SGD([w], lr=lr)
    losses = []
    for _ in range(steps):
        loss = F.mse_loss(X @ w, y)        # the loss at the current w
        losses.append(loss.item())         # written down before the step
        opt.zero_grad()                    # forget the last step's slope
        loss.backward()                    # the exact gradient, in w.grad
        opt.step()                         # w <- w - lr * w.grad
    return losses

def show(x):                               # 239.2, 9.0 or 3.68e+28
    return f"{x:.1f}" if x < 1000 else f"{x:.3g}"

for lr, steps in ((1e-4, 200), (1e-2, 20)):
    losses = train(lr, steps)
    print(f"lr {lr}: loss {show(losses[0])} -> {show(losses[-1])}"
          f" by step {steps}")
