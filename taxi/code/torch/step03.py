# Step 3, the library way: every ride as a row of one matrix, and all the
# predictions in one matrix-vector product.
import torch
from common import design_matrix, load_rides, targets

rides = load_rides()
X, y = design_matrix(rides), targets(rides)
print("X.shape =", tuple(X.shape), " y.shape =", tuple(y.shape))
print("first three rows of X:\n", X[:3])

w = torch.tensor([2.5, 2.0, 0.0], dtype=torch.float64)
pred = X @ w                                    # (6367, 3) @ (3,) -> (6367,)
print("pred.shape =", tuple(pred.shape))
print(f"first prediction ${pred[0]:.2f}; mean predicted ${pred.mean():.2f}; real mean ${y.mean():.2f}")
try:
    X @ torch.tensor([2.5, 2.0])
except RuntimeError as e:
    print("shape error:", str(e).splitlines()[0])
