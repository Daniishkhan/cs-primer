# Step 5, the library way: the whole sweep is one broadcast expression,
# the matrix of rides times a matrix with one row of knobs per price.
import torch
from common import design_matrix, load_rides, targets

rides = load_rides()
X, y = design_matrix(rides), targets(rides)

def sweep_losses(prices):
    """The loss at each price per mile: $2.50 base, nothing per minute."""
    W = torch.zeros(len(prices), 3, dtype=torch.float64)  # a row per price
    W[:, 0] = 2.5
    W[:, 1] = prices
    pred = X @ W.T                      # (6367, 3) @ (3, k) -> (6367, k)
    miss = pred - y[:, None]            # y becomes a column, then stretches
    return (miss ** 2).mean(dim=0)      # mean over the rides -> (k,)

grid = torch.tensor([1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0], dtype=torch.float64)
losses = sweep_losses(grid)
for price, loss in zip(grid, losses):
    print(f"${price:.2f} a mile: loss {loss:.2f}")
best = losses.argmin()
print(f"best on the grid: ${grid[best]:.2f} (loss {losses[best]:.2f})")

fine = torch.linspace(1.0, 4.0, 301, dtype=torch.float64)    # 301 prices
fine_losses = sweep_losses(fine)
best = fine_losses.argmin()
print(f"a cent apart: best ${fine[best]:.2f} (loss {fine_losses[best]:.2f})")
