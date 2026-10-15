"""Demo for Lab 1: what the finished pieces show.

    python3 demo.py trace         # one task, both searches, step by step
    python3 demo.py sweep         # tree versus greedy at four densities
    python3 demo.py hack          # the peekable cache file, before and after

Uses solution.py; run `python3 demo.py trace starter` after you have written
your own functions to see them at work.
"""
import importlib
import sys

sys.dont_write_bytecode = True
which = sys.argv[1] if len(sys.argv) > 1 else "trace"
lab = importlib.import_module(sys.argv[2] if len(sys.argv) > 2 else "solution")


def mean(xs):
    return sum(xs) / len(xs)


def trace():
    task = lab.make_task(2, 24, 3)
    print(f"task 2: 24 columns, the useful ones are {list(task.useful)}")
    for name, pol in (("greedy", lab.greedy_policy),
                      ("tree", lab.aide_policy)):
        j = lab.run_search(task, lab.Proposer(), 12, 102, pol)
        print(f"\n{name}: step stage   parent  columns" + " " * 22
              + "lam    public  private")
        for n in j.nodes:
            par = "-" if n.parent is None else str(n.parent.step)
            cols = ",".join(map(str, sorted(n.cfg.features))) or "none"
            pub = "crash" if n.public is None else f"{n.public:.2f}"
            prv = "" if n.private is None else f"{n.private:.2f}"
            mark = "  <- selected" if n is j.best() else ""
            print(f"  {n.step:2d}  {n.stage:7s} {par:>5s}  {cols:30s} "
                  f"{n.cfg.lam:5g}  {pub:>6s}  {prv:>6s}{mark}")
        print(f"  reported private RMSE: {lab.final_private(j):.2f}")


def sweep():
    print("useful  density  greedy  tree  greedy-tree [95% CI]   "
          "(60 seeds, 12 steps)")
    for k in (1, 3, 6, 12):
        d = mean([lab.realised_density(lab.make_task(s, 24, k),
                                       lab.Proposer(),
                                       lab.Config(frozenset(), 1.0), 100, s)
                  for s in range(30)])
        g, t = lab.compare(k, range(60), steps=12)
        m, lo, hi = lab.paired_ci(g, t)
        print(f"{k:5d}  {d:7.2f}  {mean(g):6.2f} {mean(t):5.2f}  "
              f"{m:+7.2f}  [{lo:+.2f}, {hi:+.2f}]")


def hack():
    print("cache file  policy   hacked  selected public  selected private")
    for leaky in (True, False):
        for name, pol in (("greedy", lab.greedy_policy),
                          ("tree", lab.aide_policy)):
            js = [lab.run_search(lab.make_task(s, 24, 3, leaky=leaky),
                                 lab.Proposer(p_peek=0.1), 24, 300 + s, pol)
                  for s in range(40)]
            sel = [j.best() for j in js if j.best()]
            print(f"{'present' if leaky else 'removed':10s}  {name:7s} "
                  f"{lab.hacking_rate(js):6.2f}  "
                  f"{mean([n.public for n in sel]):16.2f} "
                  f"{mean([n.private for n in sel]):17.2f}")


{"trace": trace, "sweep": sweep, "hack": hack}[which]()
