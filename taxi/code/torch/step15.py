# Step 15, the library way: the same 3-4-1 network as two layers and a bend.
import random

import torch
from torch import nn

torch.manual_seed(0)
net = nn.Sequential(nn.Linear(3, 4), nn.ReLU(), nn.Linear(4, 1)).double()
print("parameters:", sum(p.numel() for p in net.parameters()))
for name, p in net.named_parameters():
    print(f"  {name:9s} shape {tuple(p.shape)}")

# Start where init_mlp(3, 4, 0) starts, so both networks hold the same numbers.
rng, s = random.Random(0), 3 ** -0.5          # s is 1 / sqrt(3)
with torch.no_grad():
    for layer in (net[0], net[2]):
        w = layer.weight
        w.copy_(torch.tensor([[rng.uniform(-s, s) for _ in w[0]] for _ in w]))
        layer.bias.zero_()

x = torch.tensor([1.0, 0.5, -0.5], dtype=torch.float64)    # one ride
out = net(x)
out.backward()
print(f"one ride through the network: {out.item():.4f}")
print("gradients filled in:", sum(p.grad.numel() for p in net.parameters()))
