# Step 9, the library way: standardise with whole-column arithmetic, then the
# same 200 steps at learning rate 0.1, the step taken by torch.optim.SGD.
import torch
import torch.nn.functional as F
from common import design_matrix, load_rides, targets

rides = load_rides()[:500]                 # the check's first 500 rides
X, y = design_matrix(rides), targets(rides)

mean = X.mean(0)                           # one number per column
std = X.std(0, unbiased=False)             # divide by n, as the check does
mean[0], std[0] = 0.0, 1.0                 # leave the constant column alone
Z = (X - mean) / std                       # (500, 3) minus (3,): every row
print("means:", [round(v, 2) for v in mean.tolist()])
print("stds: ", [round(v, 2) for v in std.tolist()])

w = torch.zeros(3, dtype=torch.float64, requires_grad=True)
opt = torch.optim.SGD([w], lr=0.1)
losses = []
for _ in range(200):
    loss = F.mse_loss(Z @ w, y)
    losses.append(loss.item())             # the loss before this step
    opt.zero_grad()                        # backward adds into .grad
    loss.backward()
    opt.step()
print(f"lr 0.1: loss {losses[0]:.1f} -> {losses[-1]:.1f} in 200 steps")
print(f"base      ${w[0]:.2f}  (the mean fare is ${y.mean():.2f})")
print(f"distance  ${w[1]:.2f} per standard deviation ({std[1]:.2f} miles)")
print(f"time      ${w[2]:.2f} per standard deviation ({std[2]:.1f} minutes)")
print(f"in raw units: ${w[1] / std[1]:.2f} a mile, "
      f"${w[2] / std[2]:.2f} a minute")
