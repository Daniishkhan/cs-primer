"""Little data against plenty: when does the adapter stop being enough?"""
from solution import *

for n in (36, 72, 240):
    w = World(n_train=n)
    rows = sweep(w, [2, 8])
    print(f"n_train = {n}: base layer test B {evaluate(w.W0, w.test_b):.3f}")
    for r in rows:
        print(f"   {r.name:9s} {r.params:4d} params   test B {r.test_b:.4f}   task A {r.task_a:.4f}")
