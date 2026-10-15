# Step 13, the library way: tensors record how they were made, so
# .backward() fills in the gradient. No formula from step 7 appears below.
import torch
from common import design_matrix, load_rides, targets

rides = load_rides()[:200]                  # the same 200 rides as the check
X, y = design_matrix(rides), targets(rides)

w = torch.tensor([2.5, 2.0, 0.0], dtype=torch.float64, requires_grad=True)
loss = ((X @ w - y) ** 2).mean()            # built from tensors that remember
loss.backward()                             # walk the graph in reverse
print(f"loss {loss.item():.2f}; the last operation recorded: "
      f"{type(loss.grad_fn).__name__}")
print("autograd gradient:", [round(g, 4) for g in w.grad.tolist()])

with torch.no_grad():
    hand = 2 * X.T @ (X @ w - y) / len(y)   # step 7's formula, one product
print("hand gradient:    ", [round(g, 4) for g in hand.tolist()])
