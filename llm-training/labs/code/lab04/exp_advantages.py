"""Advantages in a group of eight, for every number of correct answers, under the three rules of chapter 14."""
from solution import *

print(f"{'correct':>7s} | {'std: right':>10s} {'wrong':>7s} {'sum|A|':>7s} | {'mean: right':>11s} {'wrong':>7s} | {'rloo: right':>11s} {'wrong':>7s}")
for k in range(0, 9):
    rs = [1.0] * k + [0.0] * (8 - k)
    cells = []
    for mode in ("std", "mean", "rloo"):
        a = group_advantages(rs, mode)
        cells.append((a[0] if k else float("nan"), a[-1] if k < 8 else float("nan"), sum(abs(v) for v in a)))
    f = lambda v: f"{v:7.3f}" if v == v else "      -"
    print(f"{k:7d} | {f(cells[0][0]):>10s} {f(cells[0][1])} {cells[0][2]:7.2f} | {f(cells[1][0]):>11s} {f(cells[1][1])} | {f(cells[2][0]):>11s} {f(cells[2][1])}")
