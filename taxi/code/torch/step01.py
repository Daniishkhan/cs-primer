# Step 1, the library way: the five rides as one tensor, the guess as
# arithmetic on a whole column, the total error as one call.
import torch
from common import RIDES5

rides = torch.tensor(RIDES5)          # shape (5, 4): one row per ride
distance, fare = rides[:, 0], rides[:, 3]
print("distance:", distance)
print("fare:    ", fare)

for per_mile in (2.0, 3.0):
    guess = 2.5 + per_mile * distance   # five guesses at once
    total_error = (guess - fare).abs().sum()
    print(f"$2.50 + ${per_mile:.2f} a mile: total error ${total_error:.2f}")
