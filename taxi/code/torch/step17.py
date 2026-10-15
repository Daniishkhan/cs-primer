# Step 17, the library way: the same five seeds, the same recipe, and the
# mean and spread of the five held-out losses.
import torch
from torch.utils.data import random_split
from common import design_matrix, load_rides, targets

rides = load_rides()[:1500]                  # the check's 1,500 rides
X, y = design_matrix(rides), targets(rides)


def run(seed):
    torch.manual_seed(seed)                  # the seed picks the split
    train, held = (s.indices for s in random_split(range(len(y)), [0.8, 0.2]))
    mean = X[train, 1:].mean(dim=0)          # standardise on the training rides
    std = X[train, 1:].std(dim=0, correction=0)
    Z = torch.cat([X[:, :1], (X[:, 1:] - mean) / std], dim=1)
    w = torch.zeros(3, dtype=torch.float64, requires_grad=True)
    opt = torch.optim.SGD([w], lr=0.1)
    for _ in range(100):                     # 100 steps at lr 0.1, as in step 17
        opt.zero_grad()
        ((Z[train] @ w - y[train]) ** 2).mean().backward()
        opt.step()
    return ((Z[held] @ w - y[held]) ** 2).mean().item()


scores = torch.tensor([run(seed) for seed in range(5)])
for seed, score in enumerate(scores):
    print(f"seed {seed}: held-out loss {score:.2f}")
print(f"mean {scores.mean():.2f}, spread {scores.std(correction=0):.2f}; "
      f"torch's default std divides by n - 1: {scores.std():.2f}")
