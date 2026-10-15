# Step 4, the library way: the mean squared error is one library call.
import torch
import torch.nn.functional as F
from common import design_matrix, load_rides, targets

rides = load_rides()
X, y = design_matrix(rides), targets(rides)

for per_mile in (2.0, 2.5):
    w = torch.tensor([2.5, per_mile, 0.0], dtype=torch.float64)
    pred = X @ w
    by_hand = ((pred - y) ** 2).mean()
    library = F.mse_loss(pred, y)
    print(f"${per_mile:.2f} a mile: mse by hand {by_hand:.2f}, F.mse_loss {library:.2f}, "
          f"root {library.sqrt():.2f}")
