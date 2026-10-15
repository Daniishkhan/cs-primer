# Step 16, the library way: a DataLoader shuffles and batches, SGD steps.
import random

import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset
from common import design_matrix, load_rides, targets

rides = load_rides()
X, y = design_matrix(rides), targets(rides)
rows = list(range(len(y)))
random.Random(0).shuffle(rows)               # the cut split(R, 0.8, 0) makes
tr, he = rows[:200], rows[5093:5293]         # 200 rides on each side of it
mean, std = X[tr].mean(0), X[tr].std(0, unbiased=False)
mean[0], std[0] = 0.0, 1.0                   # the constant 1 stays 1
Xtr, Xhe = (X[tr] - mean) / std, (X[he] - mean) / std

torch.manual_seed(0)
net = nn.Sequential(nn.Linear(3, 4), nn.ReLU(), nn.Linear(4, 1)).double()
rng, s = random.Random(0), 3 ** -0.5         # init_mlp(3, 4, 0)'s start
with torch.no_grad():
    for layer in (net[0], net[2]):
        w = layer.weight
        w.copy_(torch.tensor([[rng.uniform(-s, s) for _ in w[0]] for _ in w]))
        layer.bias.zero_()
opt = torch.optim.SGD(net.parameters(), lr=0.01)
loader = DataLoader(TensorDataset(Xtr, y[tr]), batch_size=20, shuffle=True,
                    generator=torch.Generator().manual_seed(0))
for epoch in range(5):
    losses = []
    for xb, yb in loader:
        loss = ((net(xb).squeeze(1) - yb) ** 2).mean()   # the batch's loss
        opt.zero_grad()                                  # clear old gradients
        loss.backward()                                  # fill in new ones
        opt.step()                                       # p -= lr * grad
        losses.append(loss.item())
    print(f"epoch {epoch + 1}: loss {sum(losses) / len(losses):.1f}")
held = ((net(Xhe).squeeze(1) - y[he]) ** 2).mean().item()
print(f"on {len(he)} held-out rides: {held:.1f}")
