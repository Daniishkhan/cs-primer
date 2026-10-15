# Step 11, the library way: the local slope of one operation at a time, from
# torch.autograd.grad. The same numbers as local_grads.
import torch


def local(fn, *inputs):
    """The slope of fn's result toward each input, at these input values."""
    xs = [torch.tensor(v, dtype=torch.float64, requires_grad=True)
          for v in inputs]
    grads = torch.autograd.grad(fn(*xs), xs)
    return [g.item() for g in grads]


print("a + b      at (2, 3):", local(lambda a, b: a + b, 2.0, 3.0))
print("a * b      at (2, 3):", local(lambda a, b: a * b, 2.0, 3.0))
print("relu(x)    at 1.5:   ", local(torch.relu, 1.5))
print("relu(x)    at -1.5:  ", local(torch.relu, -1.5))
print("relu(x)    at 0:     ", local(torch.relu, 0.0))
print("1 / x      at 4:     ", local(lambda x: 1 / x, 4.0))
