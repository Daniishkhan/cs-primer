"""Self-check for Lab 3: Feed Fan-out Simulator.

    python3 check.py                  # checks your starter.py
    python3 check.py solution         # checks the reference solution
    python3 check.py solution 4       # only milestone 4
    python3 check.py solution 4 7     # milestone 4, replaying ONLY seed 7

Everything is seeded: the graph, the workload and every sweep. Nothing sleeps, nothing is
timed, so every run gives identical numbers and the whole check takes about ten seconds.
Correctness checks compare feed pages with an uncapped brute-force reference, post by post;
the performance checks assert qualitative facts (monotone curves, which end of the SLO range
wins, hybrid beating both pure models), not exact numbers. Failures print the seed to replay.
Prints a tick, a cross, or "not implemented yet" for each milestone.
"""
import importlib
import math
import os
import sys
import time

T0 = time.time()
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
        print(f"  ✘ {name}: " + str(e).replace("\n", "\n      "))
        results.append(False)
    except Exception as e:
        import traceback
        tb = traceback.extract_tb(e.__traceback__)
        where = next((f"{f.name}() line {f.lineno}" for f in reversed(tb) if f.filename.endswith(f"{target}.py")), "?")
        print(f"  ✘ {name}: {type(e).__name__}: {e}   [in {where}]")
        results.append(False)


def replay(n, seed):
    return f"(replay: python3 check.py {target} {n} {seed})"


def tiny():
    """Users 0..4. Followers: 0 <- {1,2,3}; 1 <- {2}; 2 <- {}; 3 <- {0, 4}; 4 <- {}."""
    followers = [[1, 2, 3], [2], [], [0, 4], []]
    followees = [[3], [0], [0, 1], [0], [3]]
    return mod.Graph(followers, followees)


# ====================================================================================
# Milestone 1: the follower graph
# ====================================================================================
def m1():
    z = mod.zipf_counts(1000, 10, 1.0, 0.1)
    assert len(z) == 1000 and sum(z) == 10_000, f"zipf_counts(1000, mean 10) should have 1000 entries summing to 10,000, got {len(z)} summing to {sum(z)}"
    assert z == sorted(z, reverse=True), "zipf_counts returns the largest count first"
    assert z[0] == 100 and max(z) <= 100, f"counts are capped at cap_frac x n = 100; the largest is {z[0]}"
    assert z[0] == z[5] and z[-1] < z[len(z) // 2] <= z[10], "the head is capped and the tail is small: a power law"
    assert all(c >= 0 for c in z), "counts are non-negative integers"
    shares = {}
    for s in (0.8, 1.0, 1.2):
        zz = mod.zipf_counts(1000, 6, s, 0.2)
        shares[s] = sum(zz[:10]) / sum(zz)
    assert shares[0.8] < shares[1.0] < shares[1.2], f"a larger exponent s concentrates more followers in the top 1% of accounts: {shares}"
    g1 = mod.make_graph(500, 8, 3)
    g2 = mod.make_graph(500, 8, 3)
    g3 = mod.make_graph(500, 8, 4)
    assert g1.followers == g2.followers and g1.followees == g2.followees, "same seed must give the same graph"
    assert g1.followers != g3.followers, "a different seed must give a different graph"
    rows = []
    for seed in seeds(range(1, 21)):
        g = mod.make_graph(800, 12, seed, 1.0, 0.2)
        n = g.n
        assert n == 800 and len(g.followers) == 800 and len(g.followees) == 800, f"seed {seed}: the graph must have 800 users {replay(1, seed)}"
        edges = 0
        for a in range(n):
            fs = g.followers[a]
            assert a not in fs, f"seed {seed}: user {a} follows themselves {replay(1, seed)}"
            assert len(set(fs)) == len(fs), f"seed {seed}: duplicate followers of {a} {replay(1, seed)}"
            assert all(0 <= u < n for u in fs), f"seed {seed}: follower id out of range for author {a} {replay(1, seed)}"
            assert len(fs) <= 160, f"seed {seed}: author {a} has {len(fs)} followers, above the cap of 160 (cap_frac 0.2 x 800) {replay(1, seed)}"
            for u in fs:
                assert a in g.followees[u], f"seed {seed}: {u} is a follower of {a} but {a} is not in followees[{u}] {replay(1, seed)}"
            edges += len(fs)
        assert sum(len(f) for f in g.followees) == edges, f"seed {seed}: followers and followees must hold the same edges {replay(1, seed)}"
        assert abs(edges - 800 * 12) <= 0.01 * 800 * 12, f"seed {seed}: mean followers should be 12 (9,600 edges), got {edges} {replay(1, seed)}"
        fc = sorted((len(f) for f in g.followers), reverse=True)
        top1 = sum(fc[:8]) / edges
        top10 = sum(fc[:80]) / edges
        assert top1 >= 0.12, f"seed {seed}: the top 1% of authors hold {top1:.0%} of follow edges; a power law should give them at least 12% {replay(1, seed)}"
        assert top10 >= 0.45, f"seed {seed}: the top 10% hold {top10:.0%} of edges, expected at least 45% {replay(1, seed)}"
        assert fc[len(fc) // 2] < 12, f"seed {seed}: the median author ({fc[len(fc) // 2]} followers) should be below the mean (12) in a skewed graph {replay(1, seed)}"
        rows.append((top1, top10, fc[0], fc[len(fc) // 2]))
    t1 = sum(r[0] for r in rows) / len(rows)
    t10 = sum(r[1] for r in rows) / len(rows)
    return (f"{len(rows)} graphs of 800 users: no self-follows or duplicates, followers/followees consistent, mean 12 followers, "
            f"cap 160; the top 1% of authors hold {t1:.0%} of edges and the top 10% hold {t10:.0%} (median {rows[0][3]})")


# ====================================================================================
# Milestone 2: push
# ====================================================================================
def m2():
    g = tiny()
    c = mod.Counters()
    m = mod.PushModel(g, 2, c)
    m.post(0, 1)
    assert c.writes == 3 and c.max_fanout == 3 and c.posts == 1, f"a post by user 0 (3 followers) is 3 timeline inserts; got writes={c.writes}, max_fanout={c.max_fanout}"
    m.post(0, 2)
    m.post(0, 3)
    assert c.writes == 9, f"three posts by user 0 are 9 inserts, got {c.writes}"
    assert m.read(1, 10) == [3, 2], f"user 1's timeline is capped at 2: the newest two of 1, 2, 3 are [3, 2]; got {m.read(1, 10)}"
    m.post(1, 4)
    assert m.read(2, 10) == [4, 3], f"user 2 follows 0 and 1; newest two ids are [4, 3]; got {m.read(2, 10)}"
    assert m.read(2, 1) == [4], "read(user, k) returns at most k ids"
    assert m.read(4, 10) == [] and m.read(0, 5) == [], "users with nothing in their timeline get an empty page"
    assert c.list_reads == c.loads == 5 and c.merge_ops == 0, f"push reads ONE list per feed load and merges nothing: list_reads={c.list_reads}, loads={c.loads}, merge_ops={c.merge_ops}"
    assert c.lists_per_load == [1] * 5, "every feed load fetched 1 list"
    # the whole standard graph
    for seed in seeds(range(1, 6)):
        g = mod.standard_graph(seed)
        wl = mod.make_workload(g, seed, reads_per_post=3)
        pages, c = mod.run(g, wl, "push")
        want = sum(g.follower_count(who) for kind, who, _ in wl if kind == "post")
        posts = sum(1 for e in wl if e[0] == "post")
        assert c.writes == want, f"seed {seed}: writes should equal the sum of the authors' follower counts ({want}), got {c.writes} {replay(2, seed)}"
        assert c.max_fanout == max(g.follower_count(who) for kind, who, _ in wl if kind == "post"), f"seed {seed}: max_fanout is the biggest single fan-out {replay(2, seed)}"
        assert c.list_reads == len(pages) == c.loads and c.merge_ops == 0, f"seed {seed}: one list read per load, no merge {replay(2, seed)}"
        ref = mod.reference_pages(g, wl)
        bad = [i for i in range(len(ref)) if pages[i] != ref[i]]
        assert not bad, f"seed {seed}: read #{bad[0]} returned {pages[bad[0]]}, the brute-force answer is {ref[bad[0]]} {replay(2, seed)}"
    return (f"hand-checked fan-out counts and the cap; on 5 graphs push writes = sum of followers per post "
            f"({want:,} inserts for {posts:,} posts on the last), one list read per load, pages equal the brute-force reference")


# ====================================================================================
# Milestone 3: pull
# ====================================================================================
def m3():
    g = tiny()
    c = mod.Counters()
    m = mod.PullModel(g, 3, c, hot_cut=3)
    m.post(0, 5)
    m.post(1, 8)
    m.post(0, 9)
    assert c.writes == 3 and c.max_fanout == 1, f"a pull-model post is ONE write (to the author's own list); got writes={c.writes}"
    page = m.read(2, 3)          # user 2 follows 0 and 1
    assert page == [9, 8, 5], f"user 2 follows 0 ([9, 5]) and 1 ([8]): merged newest-first is [9, 8, 5]; got {page}"
    assert c.list_reads == 2 and c.lists_per_load == [2], f"user 2 follows two authors, so two lists are fetched; got list_reads={c.list_reads}"
    assert c.hot_list_reads == 1, f"author 0 has 3 followers (>= hot_cut 3), author 1 has 1: exactly one hot list; got {c.hot_list_reads}"
    assert c.merge_ops == 6, f"merging [9, 5] and [8] for 3 results is 3 heap pushes + 3 pops = 6 ops; got {c.merge_ops}"
    m.post(0, 10)
    m.post(0, 11)
    assert m.read(1, 10) == [11, 10, 9], "an author's recent list is capped (3 here): user 1's feed is the newest three of user 0's posts"
    assert m.read(4, 10) == [] , "user 4 follows 3, who has no posts"
    for seed in seeds(range(1, 6)):
        g = mod.standard_graph(seed)
        wl = mod.make_workload(g, seed, reads_per_post=3)
        pages, c = mod.run(g, wl, "pull")
        posts = sum(1 for e in wl if e[0] == "post")
        want_lists = sum(len(g.followees[who]) for kind, who, _ in wl if kind == "read")
        assert c.writes == posts, f"seed {seed}: pull writes once per post ({posts}), got {c.writes} {replay(3, seed)}"
        assert c.list_reads == want_lists, f"seed {seed}: list reads should be the sum of followees over all loads ({want_lists}), got {c.list_reads} {replay(3, seed)}"
        assert c.merge_ops > 0 and c.max_fanout == 1, f"seed {seed}: merging costs heap operations; no post fans out {replay(3, seed)}"
        assert c.p99_lists() == sorted(len(g.followees[u]) for k, u, _ in wl if k == "read")[max(0, math.ceil(0.99 * len(pages)) - 1)], f"seed {seed}: p99_lists mismatch {replay(3, seed)}"
        ref = mod.reference_pages(g, wl)
        bad = [i for i in range(len(ref)) if pages[i] != ref[i]]
        assert not bad, f"seed {seed}: read #{bad[0]} returned {pages[bad[0]]}, the brute-force answer is {ref[bad[0]]} {replay(3, seed)}"
        _, cp = mod.run(g, wl, "push")
        assert c.writes < cp.writes / 5 and c.list_reads > 5 * cp.list_reads, f"seed {seed}: pull should write far less and read far more than push {replay(3, seed)}"
    return (f"hand-checked merge ({'6 heap ops for [9,5]+[8]'}); on 5 graphs pull writes once per post, reads sum(followees) lists, "
            f"pages equal the reference, and it trades {cp.writes / c.writes:.0f}x fewer writes for {c.list_reads / cp.list_reads:.0f}x more list reads than push")


# ====================================================================================
# Milestone 4: hybrid
# ====================================================================================
def m4():
    g = tiny()
    c = mod.Counters()
    m = mod.HybridModel(g, 5, c, threshold=2, hot_cut=99)
    assert m.is_celebrity(0) and not m.is_celebrity(1) and not m.is_celebrity(3), "with threshold 2, only user 0 (3 followers) is a celebrity: more than the threshold"
    assert not mod.HybridModel(g, 5, mod.Counters(), threshold=3, hot_cut=99).is_celebrity(0), "exactly `threshold` followers is NOT a celebrity (strictly more)"
    assert not mod.HybridModel(g, 5, mod.Counters(), threshold=None, hot_cut=99).is_celebrity(0), "threshold=None means pure push: nobody is a celebrity"
    m.post(0, 1)
    assert c.writes == 1 and c.max_fanout == 1, f"a celebrity post is ONE write (their own list), got writes={c.writes}"
    m.post(3, 2)
    assert c.writes == 3, f"user 3 is ordinary (2 followers): 2 more inserts; got {c.writes}"
    m.post(1, 3)
    assert m.read(2, 10) == [3, 1], f"user 2 follows celebrity 0 (post 1) and ordinary 1 (post 3, pushed): the merge is [3, 1]; got {m.read(2, 10)}"
    assert c.lists_per_load == [2], f"user 2 fetched its own timeline plus one celebrity list = 2 lists; got {c.lists_per_load}"
    assert m.read(0, 10) == [2], "user 0 follows 3: gets post 2 from their timeline (no celebrities followed, 1 list)"
    assert c.lists_per_load == [2, 1]
    # correctness on the standard graph: equal to pure push, pure pull and the uncapped reference
    ths_all = None
    for seed in seeds(range(1, 9)):
        g = mod.standard_graph(seed)
        ths = mod.candidate_thresholds(g)
        ths_all = ths
        wl = mod.make_workload(g, seed, reads_per_post=2)
        ref = mod.reference_pages(g, wl)
        for cap in (50, 25):
            pu, _ = mod.run(g, wl, "push", cap)
            pl, _ = mod.run(g, wl, "pull", cap)
            for t in ths:
                hy, _ = mod.run(g, wl, "hybrid", cap, threshold=t)
                for i in range(len(ref)):
                    if not (hy[i] == pu[i] == pl[i] == ref[i]):
                        raise AssertionError(f"seed {seed}: hybrid(threshold={t}, cap={cap}) read #{i} returned {hy[i]}; push {pu[i]}, pull {pl[i]}, reference {ref[i]} {replay(4, seed)}")
        # your own verification helper
        for t in (0, ths[len(ths) // 2], None):
            bad = mod.mismatches(g, wl, t)
            assert list(bad) == [], f"seed {seed}: mismatches(threshold={t}) should be empty for a correct hybrid, got {list(bad)[:5]} {replay(4, seed)}"
    g = mod.standard_graph(1)
    wl = mod.make_workload(g, 1, reads_per_post=2)
    broken = mod.mismatches(g, wl, 28, cap=5, k=20)
    assert len(broken) > 0, "mismatches(cap=5, k=20) must report problems: a page of 20 cannot come out of timelines capped at 5 (so the models disagree with the uncapped reference)"
    # shape of the work as the threshold rises
    prev = None
    for seed in seeds(range(1, 4)):
        g = mod.standard_graph(seed)
        wl = mod.make_workload(g, seed, reads_per_post=2)
        prev = None
        for t in mod.candidate_thresholds(g):
            _, c = mod.run(g, wl, "hybrid", threshold=t)
            if t is not None and t >= 1:
                assert c.max_fanout <= t, f"seed {seed}: threshold {t} but a single post caused {c.max_fanout} inserts {replay(4, seed)}"
            if prev:
                assert c.writes >= prev.writes, f"seed {seed}: raising the threshold pushes more authors, so writes must not fall (T={t}: {c.writes} < {prev.writes}) {replay(4, seed)}"
                assert c.list_reads <= prev.list_reads, f"seed {seed}: raising the threshold pulls fewer celebrities, so list reads must not rise (T={t}) {replay(4, seed)}"
                assert c.max_fanout >= prev.max_fanout, f"seed {seed}: worst fan-out must not fall as the threshold rises (T={t}) {replay(4, seed)}"
            prev = c
    n_th = len(ths_all)
    return (f"hybrid pages equal push, pull and the uncapped reference at all {n_th} thresholds, on 8 graphs, for caps 50 and 25 "
            f"({n_th * 8 * 2} runs); writes rise and list reads fall with the threshold; no pushed post exceeds it")


# ====================================================================================
# Milestone 5: sweeps and the best threshold
# ====================================================================================
def m5():
    ths = [None, 0]
    g = mod.standard_graph(1)
    cand = mod.candidate_thresholds(g)
    assert cand[0] == 0 and cand[-1] is None, f"candidate_thresholds starts with 0 (pure pull) and ends with None (pure push); got {cand[:2]}...{cand[-1:]}"
    mids = cand[1:-1]
    assert mids == sorted(set(mids)) and len(mids) >= 8, f"the rungs in between should be distinct, increasing, and at least 8 of them; got {mids}"
    top = max(g.follower_count(a) for a in range(g.n))
    assert mids[0] <= 8 and mids[-1] < top and mids[-1] >= top / 2.5, f"the ladder should run from about a quarter of the mean to just below the largest account ({top}); got {mids[0]}..{mids[-1]}"
    pts = [
        {"threshold": 0, "cost": 10.0, "writes": 1, "list_reads": 9, "merge_ops": 1, "max_fanout": 1, "p99_lists": 30},
        {"threshold": 5, "cost": 12.0, "writes": 4, "list_reads": 7, "merge_ops": 1, "max_fanout": 5, "p99_lists": 12},
        {"threshold": 9, "cost": 8.0, "writes": 6, "list_reads": 5, "merge_ops": 1, "max_fanout": 9, "p99_lists": 8},
        {"threshold": None, "cost": 5.0, "writes": 9, "list_reads": 1, "merge_ops": 1, "max_fanout": 50, "p99_lists": 1},
    ]
    b = mod.best_threshold(pts, fanout_budget=20, lists_budget=20)
    assert b is not None and b["threshold"] == 9, f"cheapest point inside both budgets (fan-out <= 20, lists <= 20) is T=9 (cost 8); got {b}"
    assert mod.best_threshold(pts, fanout_budget=100, lists_budget=100)["threshold"] is None, "with generous budgets the cheapest point (pure push) wins"
    assert mod.best_threshold(pts, fanout_budget=0, lists_budget=0) is None, "if no point fits the budgets, return None"
    # the sweep itself agrees with run()
    wl = mod.make_workload(g, 1, reads_per_post=4)
    sw = mod.sweep(g, [0, 28, None], 4, 1)
    for p in sw:
        _, c = mod.run(g, wl, "hybrid", threshold=p["threshold"])
        assert abs(p["cost"] - c.cost()) < 1e-6 and p["writes"] == c.writes and p["max_fanout"] == c.max_fanout and p["p99_lists"] == c.p99_lists(), \
            f"sweep point for T={p['threshold']} does not match a direct run: {p}"
    # the qualitative results
    ratios = (0.5, 1, 2, 5, 10, 20)
    table = {}
    for seed in seeds(range(1, 4)):
        g = mod.standard_graph(seed)
        cand = mod.candidate_thresholds(g)
        best = []
        for rpp in ratios:
            pts = mod.sweep(g, cand, rpp, seed)
            b = mod.best_threshold(pts)
            assert b is not None, f"seed {seed}, {rpp} reads/post: no threshold meets both SLOs (fan-out <= {mod.FANOUT_BUDGET}, p99 lists <= {mod.LISTS_BUDGET}) {replay(5, seed)}"
            pure_push = next(p for p in pts if p["threshold"] is None)
            pure_pull = next(p for p in pts if p["threshold"] == 0)
            assert pure_push["max_fanout"] > mod.FANOUT_BUDGET, f"seed {seed}: pure push should break the fan-out SLO ({pure_push['max_fanout']} inserts for one post) {replay(5, seed)}"
            assert pure_pull["p99_lists"] > mod.LISTS_BUDGET, f"seed {seed}: pure pull should break the read-latency SLO ({pure_pull['p99_lists']} lists at p99) {replay(5, seed)}"
            feas = [p for p in pts if p["max_fanout"] <= mod.FANOUT_BUDGET and p["p99_lists"] <= mod.LISTS_BUDGET]
            assert all(b["cost"] <= p["cost"] + 1e-9 for p in feas), f"seed {seed}, {rpp} reads/post: best_threshold did not return the cheapest feasible point {replay(5, seed)}"
            best.append((rpp, b["threshold"], b["cost"] / min(pure_push["cost"], pure_pull["cost"]), pts))
        ts = [-1 if t is None else t for _, t, _, _ in best]
        assert ts == sorted(ts), f"seed {seed}: the best threshold should rise (more push) as the workload gets more read-heavy; got {[(r, t) for r, t, _, _ in best]} {replay(5, seed)}"
        # write-heavy: lean on pull, bounded by the read SLO; read-heavy: lean on push, bounded by the fan-out SLO
        assert best[0][1] is not None and best[0][1] <= 30, f"seed {seed}: at 0.5 reads/post the best threshold should be small (<= 30), got {best[0][1]} {replay(5, seed)}"
        feas20 = [p for p in best[-1][3] if p["max_fanout"] <= mod.FANOUT_BUDGET]
        assert best[-1][1] == max(p["threshold"] for p in feas20 if p["threshold"] is not None), \
            f"seed {seed}: at 20 reads/post push is cheapest, so the best threshold is the largest one that keeps fan-out within budget {replay(5, seed)}"
        mid = [r for r in best if r[0] in (1, 2)]
        assert any(r[2] < 0.95 for r in mid), f"seed {seed}: at a balanced ratio (1-2 reads/post) the best hybrid should cost at least 5% less than BOTH pure strategies; ratios {[round(r[2], 2) for r in mid]} {replay(5, seed)}"
        table[seed] = best
    first = table[min(table)]
    lines = ["reads/post  best threshold  cost vs cheaper pure model (pure models break an SLO)"]
    for rpp, t, rel, _ in first:
        lines.append(f"  {rpp:>6}     {('pure push' if t is None else str(t)):>10}      {rel:>5.2f}x")
    return "\n".join(lines)


check(1, "Milestone 1: a seeded power-law follower graph", m1)
check(2, "Milestone 2: push (fan-out on write)", m2)
check(3, "Milestone 3: pull (fan-out on read)", m3)
check(4, "Milestone 4: hybrid, and its correctness", m4)
check(5, "Milestone 5: sweep the threshold and the read/write ratio", m5)

print(f"\n{sum(results)}/{len(results)} milestones passing  ({time.time() - T0:.1f} s)")
sys.exit(0 if results and all(results) else 1)
