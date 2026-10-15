# Step 7, the library way: loss.backward() gives the exact gradient, and it
# agrees with your formula (and with nudging) to the printed digits.
import torch
import torch.nn.functional as F
from common import design_matrix, load_rides, targets

rides = load_rides()[:500]                 # the same 500 rides as the check
X, y = design_matrix(rides), targets(rides)

w = torch.tensor([2.5, 2.0, 0.0], dtype=torch.float64)
w.requires_grad_()                         # ask the library to track w
loss = F.mse_loss(X @ w, y)                # recorded as it is computed
loss.backward()                            # walk the record backwards
print(f"loss {loss.item():.2f} at w = {w.tolist()}")
print("w.grad from backward():", [round(g, 3) for g in w.grad.tolist()])

n = len(y)
by_formula = 2 / n * X.T @ (X @ w.detach() - y)    # (2/n) sum (pred - fare) x_j
print("your formula, in one line:", [round(g, 3) for g in by_formula.tolist()])
