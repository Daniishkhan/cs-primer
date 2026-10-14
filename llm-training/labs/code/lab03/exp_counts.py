"""Trainable parameters: this lab's layer and two real shapes (Llama 2 7B, as in chapter 11)."""
from solution import count_full, count_lora

print(f"{'matrix':>16s} {'full':>12s}  " + "  ".join(f"r={r:<3d}" + " " * 14 for r in (1, 2, 8, 16)))
for name, (dout, din) in [("this lab 24x24", (24, 24)), ("attention 4096", (4096, 4096)), ("MLP 11008x4096", (11008, 4096))]:
    cells = []
    for r in (1, 2, 8, 16):
        n = count_lora(dout, din, r)
        cells.append(f"{n:>9,d} {100 * n / count_full(dout, din):5.2f}%")
    print(f"{name:>16s} {count_full(dout, din):>12,d}  " + "  ".join(cells))
