# Step 2, the library way: a ride is a 1-D tensor, the knobs are another,
# and the prediction is their dot product.
import torch
from common import RIDES5

distance, minutes, _, fare = RIDES5[3]           # ride 4
x = torch.tensor([1.0, distance, minutes])        # features: a vector
w = torch.tensor([2.5, 2.0, 0.5])                 # base, per mile, per minute
print("x:", x, "shape", tuple(x.shape))
print("w:", w)
print(f"x @ w     = {(x @ w).item():.4f}")
print(f"torch.dot = {torch.dot(x, w).item():.4f}")
print(f"by hand   = {(x * w).sum().item():.4f}   (multiply pairwise, add up)")
print(f"the meter said ${fare:.2f}")
try:
    torch.tensor([1.0, 2.0]) @ torch.tensor([1.0])
except RuntimeError as e:
    print("wrong lengths:", str(e).splitlines()[0])
