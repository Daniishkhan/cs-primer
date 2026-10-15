"""Self-check for Lab 1: A Keep-or-Revert Research Loop.

    python3 check.py                  # checks your starter.py
    python3 check.py solution         # checks the reference solution
    python3 check.py solution 3       # only milestone 3
    python3 check.py solution 6 1     # milestone 6, only the random cases of seed 1

Everything is seeded and there is no network and no clock, so the same
code gives the same result on every run. The whole check takes about ten
seconds for the reference solution. Prints a tick, a cross, or "not
implemented yet" for each milestone, and a final count.
"""
import importlib
import json
import math
import os
import random
import shutil
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True

args = sys.argv[1:]
target = args[0] if args and not args[0].isdigit() else "starter"
rest = [a for a in args if a.isdigit()]
ONLY = int(rest[0]) if rest else None
ONLY_SEED = int(rest[1]) if len(rest) > 1 else None
mod = importlib.import_module(target)
results = []
TMP = tempfile.mkdtemp(prefix="lab01-")


def seeds(default):
    return [ONLY_SEED] if ONLY_SEED is not None else list(default)


def check(number, name, fn):
    if ONLY is not None and ONLY != number:
        return
    try:
        note = fn()
        print(f"  ✔ {name}")
        for line in (note or "").splitlines():
            print(f"      {line}")
        results.append(True)
    except NotImplementedError as e:
        print(f"  … {name}: not implemented yet ({e})")
        results.append(False)
    except AssertionError as e:
        print(f"  ✘ {name}: {e}")
        results.append(False)
    except Exception as e:
        import traceback
        tb = traceback.extract_tb(e.__traceback__)
        where = next((f"{f.name}() line {f.lineno}" for f in reversed(tb)
                      if f.filename.endswith(f"{target}.py")), "?")
        print(f"  ✘ {name}: {type(e).__name__}: {e}   [in {where}]")
        results.append(False)


def near(a, b, tol=1e-9):
    return abs(a - b) <= tol


_n = [0]


def fresh(name="s"):
    """A path for a store that does not exist yet."""
    _n[0] += 1
    return os.path.join(TMP, f"{name}{_n[0]}.jsonl")


class Patched:
    """Temporarily replace mod.train_and_score with a fake."""

    def __init__(self, fake):
        self.fake = fake

    def __enter__(self):
        self.orig = mod.train_and_score
        mod.train_and_score = self.fake

    def __exit__(self, *exc):
        mod.train_and_score = self.orig


# ─────────────────────────────────────────────────────────────────────
def m1():
    cfg = {"lr": 0.02, "degree": 3}
    h = mod.config_hash(cfg)
    assert isinstance(h, str) and len(h) == 12 and \
        all(c in "0123456789abcdef" for c in h), \
        f"config_hash must be 12 hex characters; got {h!r}"
    assert mod.config_hash({"a": 1}) == "015abd7f5cc5", \
        ("hash of {'a': 1}: SHA-256 of the text {\"a\":1} (sorted keys, "
         f"separators ',' and ':'), first 12 hex = 015abd7f5cc5; got "
         f"{mod.config_hash({'a': 1})}")
    assert mod.config_hash({"lr": 0.02, "degree": 3}) == \
        mod.config_hash({"degree": 3, "lr": 0.02}), \
        "key order must not change the hash (sort the keys)"
    assert mod.config_hash({"lr": 0.02, "degree": 3}) != \
        mod.config_hash({"lr": 0.021, "degree": 3}), \
        "a different value must give a different hash"
    assert mod.run_key(cfg, 4) == f"{h}:4"

    path = fresh()
    st = mod.RunStore(path)
    a = {"key": "k1", "v": 1.5}
    b = {"key": "k2", "v": 2}
    st.append(a)
    st.append(b)
    assert len(st) == 2 and st.get("k1") == a and st.get("zz") is None, \
        "get(key) returns the record, or None; len counts records"
    want = mod.dump_line(a) + mod.dump_line(b)
    got = open(path, encoding="utf-8").read()
    assert got == want, f"file must hold one dump_line per record.\n" \
        f"expected {want!r}\n     got {got!r}"
    try:
        st.append({"key": "k1", "v": 99})
    except mod.DuplicateKey:
        pass
    else:
        raise AssertionError("appending an existing key must raise "
                             "DuplicateKey (append-only means no overwrite)")
    assert open(path, encoding="utf-8").read() == want, \
        "a refused append must not touch the file"
    again = mod.RunStore(path)
    assert len(again) == 2 and again.get("k2") == b, \
        "opening an existing file must load its records"

    # a crash mid-write leaves half a line; it must be dropped, not fatal
    with open(path, "a", encoding="utf-8") as fh:
        fh.write('{"key":"k3","v":')
    torn = mod.RunStore(path)
    assert len(torn) == 2, "a torn last line (no newline) must be ignored"
    torn.append({"key": "k3", "v": 3})
    final = mod.RunStore(path)
    assert len(final) == 3 and final.get("k3")["v"] == 3, \
        ("after a torn line the next append must still give a valid file; "
         "drop the torn text when you load")

    # evaluate: train once, then serve from the store
    st = mod.RunStore(fresh())
    before = mod.TRAIN_CALLS
    r1 = mod.evaluate(mod.BASELINE, 5, st)
    r2 = mod.evaluate(mod.BASELINE, 5, st)
    assert mod.TRAIN_CALLS - before == 1, \
        f"the second call must come from the store; trained " \
        f"{mod.TRAIN_CALLS - before} times"
    assert r1 == r2 and len(st) == 1
    for field in ("kind", "key", "hash", "seed", "config", "proxy",
                  "heldout"):
        assert field in r1, f"run record is missing {field!r}"
    assert r1["kind"] == "run" and r1["seed"] == 5 and \
        r1["key"] == mod.run_key(mod.BASELINE, 5)
    st2 = mod.RunStore(st.path)
    before = mod.TRAIN_CALLS
    assert mod.evaluate(mod.BASELINE, 5, st2) == r1
    assert mod.TRAIN_CALLS == before, "a reopened store must act as a cache"
    return "hash, append-only JSONL, torn-line recovery, run cache"


def m2():
    assert near(mod.mean([1, 2, 6]), 3.0)
    assert near(mod.sample_sd([2, 4, 4, 4, 5, 5, 7, 9]),
                math.sqrt(32 / 7)), \
        "sample_sd divides by n - 1; [2,4,4,4,5,5,7,9] gives 2.1381"

    def fake(cfg, seed):
        return float(seed), 2.0 * seed

    with Patched(fake):
        st = mod.RunStore(fresh())
        nf = mod.noise_floor(mod.BASELINE, [1, 2, 3, 4], st)
    sd = math.sqrt(5 / 3)
    assert nf["n"] == 4
    assert near(nf["proxy"]["mean"], 2.5) and near(nf["proxy"]["sd"], sd), \
        f"seeds 1..4 with proxy = seed: mean 2.5, sd 1.2910; got {nf['proxy']}"
    assert near(nf["proxy"]["floor"], 1.96 * math.sqrt(2) * sd, 1e-6), \
        ("floor = 1.96 * sqrt(2) * sd: the size of a difference between "
         f"two single runs that reseeding alone produces 95% of the time; "
         f"expected {1.96 * math.sqrt(2) * sd:.4f}, got "
         f"{nf['proxy']['floor']:.4f}")
    assert near(nf["heldout"]["mean"], 5.0) and \
        near(nf["heldout"]["sd"], 2 * sd)
    assert len(st) == 4, "every baseline run must be kept in the store"

    st = mod.RunStore(fresh())
    nf = mod.noise_floor(mod.BASELINE, mod.BASELINE_SEEDS, st)
    before = mod.TRAIN_CALLS
    nf2 = mod.noise_floor(mod.BASELINE, mod.BASELINE_SEEDS, st)
    assert mod.TRAIN_CALLS == before and nf2 == nf, \
        "a second noise_floor must be served from the store"
    assert nf["proxy"]["sd"] > 0 and nf["heldout"]["sd"] > 0
    assert nf["proxy"]["floor"] > 0.03, \
        "the proxy (40 steps, 16 points) is noisy: floor should be > 0.03; " \
        f"got {nf['proxy']['floor']:.4f}"
    return (f"baseline over {nf['n']} seeds: proxy {nf['proxy']['mean']:.4f}"
            f" (sd {nf['proxy']['sd']:.4f}, floor {nf['proxy']['floor']:.4f})"
            f", held-out {nf['heldout']['mean']:.4f}"
            f" (sd {nf['heldout']['sd']:.4f},"
            f" floor {nf['heldout']['floor']:.4f})")


def m3():
    m, sd, t, df, sig = mod.paired_test([1, 2, 3, 4, 5])
    assert near(m, 3) and near(sd, math.sqrt(2.5)) and df == 4, \
        f"[1..5]: mean 3, sd 1.5811, df 4; got {(m, sd, df)}"
    assert near(t, 3 / (math.sqrt(2.5) / math.sqrt(5)), 1e-9) and sig, \
        f"t = mean / (sd / sqrt(n)) = 4.243 > 2.776, significant; got t={t}"
    m, sd, t, df, sig = mod.paired_test([1, -1, 2, -2, 0.5])
    assert near(m, 0.1) and not sig, \
        f"[1,-1,2,-2,0.5] has mean 0.1 and is noise; got sig={sig}, t={t:.2f}"
    _, _, t, _, sig = mod.paired_test([0.25, 0.25, 0.25])
    assert t == math.inf and sig, "sd 0 with a nonzero mean: t = +inf"
    _, _, t, _, sig = mod.paired_test([0.0, 0.0, 0.0])
    assert t == 0.0 and not sig, "all differences zero: t = 0, not significant"

    # property: the paired rule rarely keeps a change that does nothing
    rng = random.Random(7)
    keeps = singles = 0
    trials = 4000
    for _ in range(trials):
        d = [rng.gauss(0, 1) for _ in range(5)]
        mm, _, _, _, sg = mod.paired_test(d)
        keeps += (mm > 0 and sg)
        singles += d[0] > 0
    rate, srate = keeps / trials, singles / trials
    assert 0.005 < rate < 0.045, \
        ("with no true effect and 5 seeds, mean > 0 and |t| > crit should "
         f"happen about 2.5% of the time; got {rate:.3f}")
    assert srate > 0.45

    # keep_or_revert: shared seed noise cancels because runs are paired
    def fake(cfg, seed):
        shared = 5.0 * math.sin(seed)                    # big, per seed
        return shared - cfg["lr"] + 0.001 * (seed % 3), 0.0

    best = {"lr": 0.10}
    better = {"lr": 0.20}
    worse = {"lr": 0.05}
    with Patched(fake):
        st = mod.RunStore(fresh())
        sd_ = [1, 2, 3, 4, 5]
        d = mod.keep_or_revert(best, better, sd_, st)
        assert d["keep"] and near(d["mean_gain"], 0.10, 1e-9), \
            ("candidate is 0.10 better on every seed (seed noise cancels "
             f"when paired): must keep; got {d}")
        assert not mod.keep_or_revert(best, worse, sd_, st)["keep"], \
            "a worse candidate must be reverted"
        assert not mod.keep_or_revert(best, dict(best), sd_, st)["keep"], \
            "an identical config has zero gain: revert"
    for field in ("keep", "mean_gain", "t", "df"):
        assert field in d, f"decision is missing {field!r}"

    # a gain inside the noise is reverted even if the mean is positive
    def noisy(cfg, seed):
        eff = 0.05 if cfg["lr"] > 0.15 else 0.0
        rng = random.Random(seed * 1000 + int(cfg["lr"] * 1000))
        return 1.0 - eff + rng.gauss(0, 0.4), 0.0

    with Patched(noisy):
        st = mod.RunStore(fresh())
        kept = [mod.keep_or_revert(best, better, [i, i + 1, i + 2, i + 3],
                                   st)["keep"] for i in range(0, 40, 4)]
    assert sum(kept) <= 3, \
        f"a 0.05 gain under 0.4 of noise should rarely pass; kept {sum(kept)}/10"
    return (f"no-effect change kept {rate:.1%} of the time on a paired test"
            f" vs {srate:.0%} on one comparison")


def m4():
    # the decision uses the proxy only; held-out is logged, never decided on
    def fake(cfg, seed):
        return 1.0 - cfg["lr"] + 0.001 * (seed % 3), 1.0 + cfg["lr"]

    best, cand = {"lr": 0.1}, {"lr": 0.3}
    with Patched(fake):
        st = mod.RunStore(fresh())
        rec = mod.run_experiment(3, best, cand, st, k=4)
    assert rec["kind"] == "experiment" and rec["key"] == "exp:0003" and \
        rec["index"] == 3
    assert st.get("exp:0003") == rec, "the experiment record must be stored"
    assert rec["keep"] is True, \
        "proxy improves by 0.2, so keep; held-out must not veto it"
    assert near(rec["proxy_gain"], 0.2, 1e-9), rec["proxy_gain"]
    assert near(rec["heldout_gain"], -0.2, 1e-9), \
        "held-out gain = mean(best.heldout - cand.heldout); here -0.2"
    assert near(rec["gap"], 0.4, 1e-9), "gap = proxy_gain - heldout_gain"
    assert rec["seeds"] == mod.experiment_seeds(3, 4)
    assert rec["cand_config"] == cand
    assert rec["best_hash"] == mod.config_hash(best)

    # the loop: proposer sees the current best, and a kept candidate becomes it
    seen = []

    class Spy:
        def propose(self, b, i):
            seen.append((i, dict(b)))
            return {"lr": [0.3, 0.2, 0.5][i]}

    with Patched(fake):
        st = mod.RunStore(fresh())
        b, hist = mod.research_loop(Spy(), 3, st, k=3, start={"lr": 0.1})
    assert [s[1]["lr"] for s in seen] == [0.1, 0.3, 0.3], \
        ("experiment 1 must be proposed against the kept 0.3, and "
         f"experiment 2 against it again (0.2 was reverted); saw {seen}")
    assert [r["keep"] for r in hist] == [True, False, True]
    assert b == {"lr": 0.5} and len(hist) == 3
    ex = [r for r in st.records.values() if r["kind"] == "experiment"]
    assert len(ex) == 3, "every experiment must be in the store"
    all_seeds = [s for r in hist for s in r["seeds"]]
    assert len(set(all_seeds)) == len(all_seeds), \
        "each experiment must use fresh seeds (experiment_seeds)"

    # the real task
    out = []
    for s in seeds((0, 1)):
        st = mod.RunStore(fresh())
        before = mod.TRAIN_CALLS
        b, hist = mod.research_loop(mod.RandomProposer(s), 12, st)
        runs = [r for r in st.records.values() if r["kind"] == "run"]
        assert len(hist) == 12 and len(runs) == mod.TRAIN_CALLS - before, \
            "every (config, seed) pair must be trained exactly once"
        for r in hist:
            assert near(r["gap"], r["proxy_gain"] - r["heldout_gain"])
        out.append(f"seed {s}: kept {sum(r['keep'] for r in hist)}/12,"
                   f" {len(runs)} runs")
    return "\n".join(out)


def m5():
    assert near(mod.ols_slope([1, 3, 5, 7]), 2.0)
    assert near(mod.ols_slope([5, 5, 5]), 0.0)
    assert near(mod.ols_slope([2, 1, 0]), -1.0)

    hist = [{"keep": True, "proxy_gain": 1.0, "heldout_gain": 0.5},
            {"keep": False, "proxy_gain": 9.0, "heldout_gain": 9.0},
            {"keep": True, "proxy_gain": 2.0, "heldout_gain": -0.5}]
    cp, ch, cg = mod.cumulative(hist)
    assert cp == [1.0, 1.0, 3.0] and ch == [0.5, 0.5, 0.0] and \
        cg == [0.5, 0.5, 3.0], \
        ("cumulative sums only the kept experiments, and has one entry per "
         f"experiment; got {(cp, ch, cg)}")

    cp = [0, 1, 2, 3, 4, 5, 6, 7]
    flat = [0] * 8
    assert mod.detect_overfit(cp, flat, window=4, min_slope=0.5) == 3, \
        ("proxy climbs 1 per experiment, held-out is flat: the first full "
         "window ends at index 3")
    assert mod.detect_overfit(cp, cp, window=4, min_slope=0.5) is None, \
        "both climbing together is progress, not overfitting"
    slow = [0.1 * i for i in range(8)]
    assert mod.detect_overfit(cp, slow, window=4, min_slope=0.5) is None, \
        "held-out still climbing: the proxy gain is transferring"
    assert mod.detect_overfit(cp, flat, window=9, min_slope=0.5) is None, \
        "fewer experiments than one window: nothing to flag yet"
    assert mod.detect_overfit(flat, flat, window=4, min_slope=0.5) is None

    got = mod.text_chart([0, 2, 2, 4], [0, 1, 1, 2], every=2, width=8)
    want = ("   2 P ####     +2.0000\n"
            "   2 H ##       +1.0000\n"
            "   4 P ######## +4.0000\n"
            "   4 H ####     +2.0000")
    assert got == want, f"text_chart mismatch.\nexpected:\n{want}\n got:\n{got}"
    neg = mod.text_chart([4, 4], [-1, -1], every=2, width=4)
    assert neg == "   2 P #### +4.0000\n   2 H      -1.0000", \
        f"a negative gain draws no bar but keeps its sign; got {neg!r}"

    note = []
    for s in seeds((0, 1, 2)):
        st = mod.RunStore(fresh())
        _, hist = mod.research_loop(mod.RandomProposer(s), 60, st)
        cp, ch, _ = mod.cumulative(hist)
        at = mod.detect_overfit(cp, ch)
        assert at is not None, \
            (f"seed {s}: 60 experiments of a proposer that only sees the "
             f"proxy should trip the detector (proxy +{cp[-1]:.3f}, "
             f"held-out +{ch[-1]:.3f})")
        assert cp[-1] >= 3 * max(ch[-1], 0.005), \
            f"seed {s}: proxy gain should dwarf held-out gain; {cp[-1]:.3f}" \
            f" vs {ch[-1]:.3f}"
        note.append(f"seed {s}: proxy +{cp[-1]:.3f}, held-out "
                    f"+{ch[-1]:.3f}, flagged at experiment {at + 1}")
    return "\n".join(note)


def m6():
    a, b = fresh("a"), fresh("b")
    open(a, "w").write("x\ny\nz\n")
    open(b, "w").write("x\ny\nz\n")
    assert mod.first_difference(a, b) is None
    open(b, "w").write("x\nQ\nz\n")
    assert mod.first_difference(a, b) == 2
    open(b, "w").write("x\ny\n")
    assert mod.first_difference(a, b) == 3, \
        "a shorter file differs at the first missing line"
    open(b, "w").write("x\ny\nz\nw\n")
    assert mod.first_difference(a, b) == 4

    note = []
    for s in seeds((0, 1)):
        path = fresh("log")
        st = mod.RunStore(path)
        mod.noise_floor(mod.BASELINE, mod.BASELINE_SEEDS, st)
        mod.research_loop(mod.RandomProposer(s), 15, st)
        out = fresh("replayed")
        diff = mod.replay(path, out)
        assert diff is None, \
            (f"seed {s}: replaying {len(st)} records gave a different file;"
             f" first difference at line {diff}. Is anything in a record "
             f"not a function of (config, seed)?")
        assert open(path, "rb").read() == open(out, "rb").read()

        # tamper with one logged score and replay: the lie is located
        lines = open(path, encoding="utf-8").read().splitlines()
        j = next(i for i, ln in enumerate(lines)
                 if json.loads(ln)["kind"] == "run" and i > 3)
        rec = json.loads(lines[j])
        rec["proxy"] -= 0.01
        lines[j] = mod.dump_line(rec).rstrip("\n")
        bad = fresh("tampered")
        open(bad, "w", encoding="utf-8").write("\n".join(lines) + "\n")
        found = mod.replay(bad, fresh("rb"))
        assert found == j + 1, \
            f"a score edited on line {j + 1} must be reported at line " \
            f"{j + 1}; replay reported {found}"
        note.append(f"seed {s}: {len(st)} records replay byte-identical;"
                    f" a forged score on line {j + 1} is caught")
    return "\n".join(note)


MILESTONES = [
    (1, "Milestone 1: an append-only run store keyed by config hash", m1),
    (2, "Milestone 2: a noise floor from baseline seeds", m2),
    (3, "Milestone 3: keep or revert on a paired test", m3),
    (4, "Milestone 4: proxy and held-out, logged per experiment", m4),
    (5, "Milestone 5: the gap, its trend, and a text chart", m5),
    (6, "Milestone 6: byte-identical replay from the log", m6),
]

if __name__ == "__main__":
    t0 = time.time()
    print(f"Lab 1 checks against {target}.py\n")
    try:
        for n, name, fn in MILESTONES:
            check(n, name, fn)
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
    print(f"\n{sum(results)}/{len(results)} milestones passing"
          f"  ({time.time() - t0:.1f} s)")
    sys.exit(0 if all(results) else 1)
