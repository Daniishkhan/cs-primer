# Step 10, the library way: a tensor that remembers how it was made. Every
# operation on a tensor that needs a slope stores itself in grad_fn.
import torch

a = torch.tensor(2.0, requires_grad=True)   # a leaf: no operation made it
b = torch.tensor(3.0, requires_grad=True)
c = a + b                                   # each result records its maker
d = a * b
r = torch.relu(torch.tensor(-2.0, requires_grad=True))
for name, t in (("a + b", c), ("a * b", d), ("relu(-2)", r)):
    print(f"{name:9} = {t.item():4.1f}   made by {type(t.grad_fn).__name__}")
print("a leaf's grad_fn:", a.grad_fn)


def show(fn, depth=0):
    """Print the recorded graph: each node's parents indented below it."""
    print("  " * depth + type(fn).__name__)
    for parent, _ in fn.next_functions:
        if parent is not None:              # a plain number is not recorded
            show(parent, depth + 1)


print("\nthe graph of a * b + a:")
show((a * b + a).grad_fn)
print("\nthe graph of a + 1:")
show((a + 1).grad_fn)
