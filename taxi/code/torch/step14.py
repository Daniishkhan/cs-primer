# Step 14, the library way: random_split cuts the rides, a seeded Generator
# makes the cut repeatable, and a least-squares fit scores on the rest.
import torch
from torch.utils.data import TensorDataset, random_split
from common import design_matrix, load_rides, targets

rides = load_rides()
X, y = design_matrix(rides), targets(rides)
n_train = int(0.8 * len(y))                       # rounded down, as in split()
train, held = random_split(TensorDataset(X, y), [n_train, len(y) - n_train],
                           generator=torch.Generator().manual_seed(0))
print(f"{len(train):,} rides to learn from, {len(held):,} held out")

Xt, yt = X[train.indices], y[train.indices]
Xh, yh = X[held.indices], y[held.indices]
w = torch.linalg.lstsq(Xt, yt.unsqueeze(1)).solution.squeeze(1)  # best line
print(f"line: ${w[0]:.2f} + ${w[1]:.2f} a mile + ${w[2]:.2f} a minute")
print(f"loss on the rides it learnt from: {((Xt @ w - yt) ** 2).mean():.2f}")
print(f"loss on the held-out rides:       {((Xh @ w - yh) ** 2).mean():.2f}")

miss = yh - Xh @ w                                # fare minus prediction
print(f"average of fare minus prediction: {miss[Xh[:, 2] > 30].mean():+.2f} "
      f"over 30 minutes, {miss[Xh[:, 2] < 5].mean():+.2f} under 5 minutes")
