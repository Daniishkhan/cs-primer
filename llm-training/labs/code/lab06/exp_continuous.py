"""Milestone 4 experiment: the three policies as the arrival rate grows."""
from solution import DEFAULT, POLICIES, print_rows, run_sweep

for name in POLICIES:
    print_rows(name, run_sweep(name, [2, 4, 6, 8, 10, 12], 300, 1, DEFAULT))
    print()
