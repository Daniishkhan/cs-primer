"""Self-check for Lab 5: A Geospatial Index.

    python3 check.py                  # checks your starter.py
    python3 check.py solution         # checks the reference solution
    python3 check.py solution 3       # only milestone 3
    python3 check.py solution 3 7     # milestone 3, replaying ONLY seed 7

Seeded and deterministic: every random draw comes from a seeded random.Random and nothing reads a clock. The check
brings its OWN reference code (a bit-string geohash, integer-grid neighbours, a brute-force oracle with its own
haversine), so a bug in your helpers cannot hide a bug in your index. The benchmark counts distance computations,
not seconds. When a property fails it prints the failing seed and the command that replays it.
Prints a tick, a cross, or "not implemented yet" for each milestone.
"""
import importlib
import math
import os
import random
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

B32 = "0123456789bcdefghjkmnpqrstuvwxyz"


def seeds(default):
    return [ONLY_SEED] if ONLY_SEED is not None else list(default)


def replay(n, seed):
    return f"(replay: python3 check.py {target} {n} {seed})"


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
        print(f"  ✘ {name}: crashed with {type(e).__name__}: {e}  [in {where}]")
        results.append(False)


# ---------------------------------------------------------------------------------------------
# Trusted reference code (independent of your module)
# ---------------------------------------------------------------------------------------------
RE = 6371008.8


def ref_hav(a, b, c, d):
    p1, p2 = math.radians(a), math.radians(c)
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(d - b) / 2) ** 2
    return 2 * RE * math.asin(min(1.0, math.sqrt(h)))


def ref_bits(lat, lng, precision):
    """The geohash as a string of 0/1: bisect longitude, latitude, longitude, ..."""
    lo_a, hi_a, lo_g, hi_g, out = -90.0, 90.0, -180.0, 180.0, []
    for i in range(5 * precision):
        if i % 2 == 0:
            mid = (lo_g + hi_g) / 2
            out.append("1" if lng >= mid else "0")
            lo_g, hi_g = (mid, hi_g) if lng >= mid else (lo_g, mid)
        else:
            mid = (lo_a + hi_a) / 2
            out.append("1" if lat >= mid else "0")
            lo_a, hi_a = (mid, hi_a) if lat >= mid else (lo_a, mid)
    return "".join(out)


def ref_encode(lat, lng, precision):
    bits = ref_bits(min(90.0, max(-90.0, lat)), min(180.0, max(-180.0, lng)), precision)
    return "".join(B32[int(bits[i:i + 5], 2)] for i in range(0, len(bits), 5))


def ref_ij(h):
    """(row, col) by de-interleaving the bits of the hash: even bits are longitude, odd bits latitude."""
    bits = "".join(format(B32.index(c), "05b") for c in h)
    col = int("".join(bits[0::2]) or "0", 2)
    row = int("".join(bits[1::2]) or "0", 2)
    return row, col


def ref_cell(row, col, p):
    nl, ng = (5 * p) // 2, (5 * p + 1) // 2
    lb, gb = format(row, f"0{nl}b") if nl else "", format(col, f"0{ng}b")
    bits = []
    for i in range(5 * p):
        bits.append(gb[i // 2] if i % 2 == 0 else lb[i // 2])
    s = "".join(bits)
    return "".join(B32[int(s[i:i + 5], 2)] for i in range(0, len(s), 5))


def ref_shift(h, di, dj):
    p = len(h)
    nr, nc = 1 << (5 * p // 2), 1 << ((5 * p + 1) // 2)
    r, c = ref_ij(h)
    r += di
    if not 0 <= r < nr:
        return None
    return ref_cell(r, (c + dj) % nc, p)


def ref_knn(pos, lat, lng, k):
    return sorted((ref_hav(lat, lng, la, ln), d) for d, (la, ln) in pos.items())[:k]


class RefBrute(mod.SpatialIndex):
    """The oracle for the simulation: brute force with this file's own haversine."""

    def update(self, did, lat, lng):
        self.pos[did] = (lat, lng)

    def remove(self, did):
        del self.pos[did]

    def knn(self, lat, lng, k):
        self.visits += 1
        self.dist_calls += len(self.pos)
        return ref_knn(self.pos, lat, lng, k)

    def footprint(self):
        return 0


def same(got, want, tol=1e-6):
    return len(got) == len(want) and all(g[1] == w[1] and abs(g[0] - w[0]) <= tol for g, w in zip(got, want))


def fmt(res):
    return "[" + ", ".join(f"({d:.1f}, {i})" for d, i in res[:6]) + (" ..." if len(res) > 6 else "") + "]"


def km(m):
    return f"{m / 1000:.2f} km" if m >= 1000 else f"{m:.0f} m"


# ---------------------------------------------------------------------------------------------
def m1():
    assert mod.encode(57.64911, 10.40744, 11) == "u4pruydqqvj", f"the textbook vector (57.64911, 10.40744) at precision 11 is u4pruydqqvj, got {mod.encode(57.64911, 10.40744, 11)}"
    assert mod.encode(42.6, -5.6, 5) == "ezs42", f"(42.6, -5.6) at precision 5 is ezs42 (the Wikipedia example), got {mod.encode(42.6, -5.6, 5)}"
    assert mod.encode(0.0, 0.0, 5) == "s0000", f"(0, 0) is s0000...: the equator and the prime meridian meet at the lower-left of the 's' cell, got {mod.encode(0.0, 0.0, 5)}"
    a, b, c, d = mod.decode_bbox("ezs42")
    assert abs(a - 42.5830078125) < 1e-9 and abs(b - 42.626953125) < 1e-9 and abs(c + 5.625) < 1e-9 and abs(d + 5.5810546875) < 1e-9, f"bbox of ezs42 should be lat 42.5830078125..42.626953125, lng -5.625..-5.5810546875, got {(a, b, c, d)}"
    la, ln = mod.decode("ezs42")
    assert abs(la - 42.60498046875) < 1e-9 and abs(ln + 5.60302734375) < 1e-9, f"centre of ezs42 should be (42.60498046875, -5.60302734375), got {(la, ln)}"
    for p in range(1, 13):
        dlat, dlng = mod.cell_dims(p)
        nl, ng = (5 * p) // 2, (5 * p + 1) // 2
        assert abs(dlat - 180 / 2 ** nl) < 1e-12 and abs(dlng - 360 / 2 ** ng) < 1e-12, f"cell_dims({p}) should be (180/2^{nl}, 360/2^{ng}), got {(dlat, dlng)}"
    S = seeds(range(1, 41))
    n_pts = 0
    for s in S:
        rng = random.Random(s)
        for _ in range(25):
            lat, lng = rng.uniform(-90, 90), rng.uniform(-180, 180)
            if rng.random() < 0.2:
                lat = rng.choice((-90.0, 90.0, 0.0, 89.999999, -89.999999))
            if rng.random() < 0.2:
                lng = rng.choice((-180.0, 180.0, 0.0, 179.999999, -179.999999))
            p = rng.randrange(1, 13)
            h = mod.encode(lat, lng, p)
            n_pts += 1
            assert h == ref_encode(lat, lng, p), f"seed {s}: encode({lat}, {lng}, {p}) = {h!r}, the reference bisection gives {ref_encode(lat, lng, p)!r} {replay(1, s)}"
            a, b, c, d = mod.decode_bbox(h)
            la = min(90.0, lat)
            ln = min(180.0, lng)
            assert a <= la <= b and c <= ln <= d, f"seed {s}: the box {(a, b, c, d)} of {h!r} does not contain the point ({lat}, {lng}) {replay(1, s)}"
            dlat, dlng = mod.cell_dims(p)
            assert abs((b - a) - dlat) < 1e-12 and abs((d - c) - dlng) < 1e-12, f"seed {s}: the box of {h!r} should be {dlat} x {dlng} degrees {replay(1, s)}"
            ctr = mod.decode(h)
            assert abs(ctr[0] - (a + b) / 2) < 1e-12 and abs(ctr[1] - (c + d) / 2) < 1e-12, f"seed {s}: decode({h!r}) should be the centre of its box {replay(1, s)}"
            assert mod.encode(ctr[0], ctr[1], p) == h, f"seed {s}: encoding the centre of {h!r} must give {h!r} back {replay(1, s)}"
            assert mod.encode(lat, lng, 12).startswith(h), f"seed {s}: a shorter geohash must be a prefix of a longer one for the same point {replay(1, s)}"
    lines = ["precision   cell height x width at the equator   cells in the world"]
    for p in (1, 2, 3, 4, 5, 6, 7, 8, 9):
        dlat, dlng = mod.cell_dims(p)
        lines.append(f"   {p}        {km(dlat * math.pi * RE / 180):>9} x {km(dlng * math.pi * RE / 180):<9}            2^{5 * p}")
    return (f"known vectors (u4pruydqqvj, ezs42, s0000) and bounding boxes match; {n_pts} random points (poles, equator, +-180 included) agree with a reference bisection:\n"
            "encode == reference, point in its box, box size == cell_dims, centre re-encodes to the same cell, prefixes nest\n" + "\n".join(lines))


# ---------------------------------------------------------------------------------------------
def m2():
    S = seeds(range(1, 31))
    n_cells = n_pole = n_anti = n_prime = 0
    for s in S:
        rng = random.Random(s)
        pts = []
        for _ in range(12):
            pts.append((rng.uniform(-90, 90), rng.uniform(-180, 180)))
        pts += [(rng.uniform(88, 90), rng.uniform(-180, 180)), (rng.uniform(-90, -88), rng.uniform(-180, 180)),
                (rng.uniform(-60, 60), rng.uniform(179.5, 180)), (rng.uniform(-60, 60), rng.uniform(-180, -179.5)),
                (rng.uniform(-60, 60), rng.uniform(-0.5, 0.5)), (rng.uniform(-0.5, 0.5), rng.uniform(-170, 170))]
        for lat, lng in pts:
            p = rng.randrange(1, 9)
            h = ref_encode(lat, lng, p)
            got = mod.neighbors(h)
            n_cells += 1
            n_pole += abs(lat) > 88
            n_anti += abs(lng) > 179.4
            n_prime += abs(lng) < 0.6
            assert set(got) == set(mod.DIRS), f"seed {s}: neighbors({h!r}) must have the 8 keys n ne e se s sw w nw, got {sorted(got)} {replay(2, s)}"
            for name, (di, dj) in mod.DIRS.items():
                want = ref_shift(h, di, dj)
                assert got[name] == want, f"seed {s}: neighbors({h!r})[{name!r}] = {got[name]!r}, expected {want!r}" + \
                    (" (past a pole there is no neighbour: None)" if want is None else (" (wrap round the antimeridian?)" if abs(lng) > 179 else "")) + f" {replay(2, s)}"
            for di, dj in ((0, 0), (2, -3), (-5, 7), (0, 1 << ((5 * p + 1) // 2)), (1 << (5 * p // 2), 0)):
                assert mod.shift(h, di, dj) == ref_shift(h, di, dj), f"seed {s}: shift({h!r}, {di}, {dj}) = {mod.shift(h, di, dj)!r}, expected {ref_shift(h, di, dj)!r} {replay(2, s)}"
            if got["e"] is not None:
                assert mod.neighbors(got["e"])["w"] == h, f"seed {s}: the west neighbour of the east neighbour of {h!r} must be {h!r} {replay(2, s)}"
    nb = mod.neighbors("ezs42")
    assert nb["n"] == "ezs48" and nb["e"] == "ezs43" and nb["ne"] == "ezs49" and nb["s"] == "ezs40" and nb["sw"] == "ezefp" and nb["w"] == "ezefr", f"worked example: neighbours of ezs42: n ezs48, ne ezs49, e ezs43, s ezs40, sw ezefp, w ezefr; got {nb}"
    # the point of the exercise: neighbours across a boundary may share almost no prefix
    a = mod.encode(0.0001, -0.0001, 6)
    b = mod.encode(0.0001, 0.0001, 6)
    assert mod.neighbors(a)["e"] == b and a[0] != b[0], f"two cells either side of the prime meridian are neighbours although {a!r} and {b!r} share no prefix"
    top = mod.encode(89.99, 10.0, 5)
    assert all(mod.neighbors(top)[x] is None for x in ("n", "ne", "nw")) and mod.neighbors(top)["s"] is not None, "cells on the northern edge of the map have no northern neighbours"
    return (f"{n_cells} cells ({n_pole} near a pole, {n_anti} at the antimeridian, {n_prime} at the prime meridian) x 8 directions agree with an independent bit-interleaving reference\n"
            f"shift() agrees too, including full wrap-arounds; east then west returns home; ezs42 -> n ezs48, ne ezs49, e ezs43, s ezs40, sw ezefp, w ezefr\n"
            f"cells either side of longitude 0 are neighbours with no common prefix ({a} and {b}); past a pole the neighbour is None")


# ---------------------------------------------------------------------------------------------
def build(index, pos):
    for did, (la, ln) in pos.items():
        index.update(did, la, ln)
    return index


def city_points(rng, n, spread=(0.2, 0.25)):
    return {i: (37.77 + rng.uniform(-spread[0], spread[0]) * (rng.random() ** 2 if rng.random() < 0.5 else 1),
                -122.42 + rng.uniform(-spread[1], spread[1]) * (rng.random() ** 2 if rng.random() < 0.5 else 1)) for i in range(n)}


def world_points(rng, n):
    pts = {}
    for i in range(n):
        c = rng.random()
        if c < 0.18:
            pts[i] = (rng.uniform(-90, 90), rng.choice((1, -1)) * rng.uniform(179.0, 180.0))
        elif c < 0.36:
            pts[i] = (rng.choice((1, -1)) * rng.uniform(88.5, 90.0), rng.uniform(-180, 180))
        else:
            pts[i] = (rng.uniform(-90, 90), rng.uniform(-180, 180))
    return pts


def compare(idx_factory, pos, queries, ks, tag, n, seed, maxr=None):
    idx = build(idx_factory(), pos)
    tot = 0
    for (la, ln) in queries:
        for k in ks:
            idx.reset_counters()
            got = idx.knn(la, ln, k)
            tot += idx.dist_calls
            want = ref_knn(pos, la, ln, k)
            assert same(got, want), f"{tag}, seed {seed}: knn({la:.5f}, {ln:.5f}, k={k}) over {len(pos)} drivers differs from brute force.\n  got  {fmt(got)}\n  want {fmt(want)} {replay(n, seed)}"
    return idx, tot


def m3():
    # ring cells
    for p in (1, 2, 4, 6):
        for h in (ref_encode(37.77, -122.42, p), ref_encode(0.0, 179.99, p), ref_encode(89.9, 3.0, p), ref_encode(-89.9, -3.0, p)):
            nr, nc = 1 << (5 * p // 2), 1 << ((5 * p + 1) // 2)
            r0, c0 = ref_ij(h)
            for r in (0, 1, 2, 3, 7):
                want = set()
                for dr in range(-r, r + 1):
                    for dc in range(-r, r + 1):
                        if max(abs(dr), abs(dc)) == r and 0 <= r0 + dr < nr:
                            want.add(ref_cell(r0 + dr, (c0 + dc) % nc, p))
                got = mod.ring(h, r)
                assert len(got) == len(set(got)), f"ring({h!r}, {r}) contains duplicates (a ring that wraps the world must not repeat cells): {got[:6]}..."
                assert set(got) == want, f"ring({h!r}, {r}) should be the {len(want)} cells at Chebyshev distance exactly {r}; got {len(got)} cells, missing {sorted(want - set(got))[:3]}, extra {sorted(set(got) - want)[:3]}"
    # unsearched_bound: valid and not lazy
    rng = random.Random(3)
    checked = 0
    for _ in range(400):
        p = rng.choice((2, 3, 4, 5))
        lat = rng.choice((rng.uniform(-90, 90), rng.uniform(80, 90), rng.uniform(-90, -80)))
        lng = rng.choice((rng.uniform(-180, 180), rng.uniform(178, 180), rng.uniform(-180, -178)))
        h = ref_encode(lat, lng, p)
        r = rng.randrange(0, 4)
        b = mod.unsearched_bound(lat, h, r)
        nr, nc = 1 << (5 * p // 2), 1 << ((5 * p + 1) // 2)
        r0, c0 = ref_ij(h)
        for _ in range(60):
            qr, qc = rng.randrange(nr), rng.randrange(nc)
            dcirc = min((qc - c0) % nc, (c0 - qc) % nc)
            if abs(qr - r0) <= r and dcirc <= r:
                continue                                              # inside the block
            dlat, dlng = mod.cell_dims(p)
            for _ in range(2):
                pla = -90 + (qr + rng.random()) * dlat
                pln = -180 + (qc + rng.random()) * dlng
                d = ref_hav(lat, lng, pla, pln)
                checked += 1
                assert d >= b - 1e-6, f"unsearched_bound({lat:.4f}, {h!r}, {r}) = {b:.1f} m, but the point ({pla:.4f}, {pln:.4f}) outside the block is only {d:.1f} m away: the bound is not a lower bound"
    h6 = ref_encode(37.77, -122.42, 6)
    dlat6 = mod.cell_dims(6)[0] * math.pi * RE / 180
    b2 = mod.unsearched_bound(37.77, h6, 2)
    assert 0.95 * 2 * dlat6 <= b2 <= 2.6 * dlat6, f"at precision 6 in San Francisco two rings should guarantee about 2 cells ({2 * dlat6:.0f} m) of clearance, got {b2:.0f} m"
    assert mod.unsearched_bound(37.77, h6, 0) == 0 or mod.unsearched_bound(37.77, h6, 0) < 1e-9, "with only ring 0 searched nothing is guaranteed: the bound is 0"
    assert mod.unsearched_bound(0.0, ref_encode(0.0, 0.0, 1), 40) == float("inf"), "when the block covers the whole world there is nothing left to search: the bound is infinity"
    # nearest-k against brute force
    S = seeds(range(1, 31))
    calls_dense = []
    for s in S:
        rng = random.Random(s)
        p = (5, 6, 7)[s % 3]
        n = (300, 1500, 800)[s % 3]
        pos = city_points(rng, n)
        qs = [(37.77 + rng.uniform(-0.2, 0.2), -122.42 + rng.uniform(-0.25, 0.25)) for _ in range(15)]
        _, tot = compare(lambda: mod.GeoHashIndex(p), pos, qs, (1, 8, 20), f"city p={p}", 3, s)
        calls_dense.append(tot / (len(qs) * 3) / n)
    for s in seeds(range(1, 13)):
        rng = random.Random(500 + s)
        pos = city_points(rng, 40)                                        # sparse: a long way to the k-th driver
        qs = [(37.77 + rng.uniform(-0.2, 0.2), -122.42 + rng.uniform(-0.25, 0.25)) for _ in range(6)]
        compare(lambda: mod.GeoHashIndex(6), pos, qs, (1, 8, 40), "sparse", 3, s)
    worldq = 0
    for s in seeds(range(1, 31)):
        rng = random.Random(900 + s)
        pos = world_points(rng, 60)
        qs = [(rng.uniform(-90, 90), rng.uniform(-180, 180)) for _ in range(5)] + [(90.0, 0.0), (-90.0, 120.0), (10.0, 179.999), (-10.0, -179.999), (89.9, 179.9)]
        compare(lambda: mod.GeoHashIndex(2), pos, qs, (1, 5, 12), "world p=2", 3, s)
        worldq += len(qs) * 3
        if s % 5 == 0:
            compare(lambda: mod.GeoHashIndex(3), pos, qs[:2] + qs[-3:], (3, 9), "world p=3", 3, s)
            worldq += 10
    # ties: ten drivers on the very same spot; the lowest ids must win
    pos = {i: (37.77, -122.42) for i in range(10)}
    pos.update({10 + i: (37.7701 + i * 0.001, -122.42) for i in range(5)})
    idx = build(mod.GeoHashIndex(6), pos)
    got = idx.knn(37.77, -122.42, 4)
    assert [g[1] for g in got] == [0, 1, 2, 3], f"ten drivers at the same point: ties break by id, expected ids [0, 1, 2, 3], got {[g[1] for g in got]}"
    # churn: moves across cells, removals, re-insertions
    for s in seeds(range(1, 9)):
        rng = random.Random(1300 + s)
        pos = city_points(rng, 400)
        idx = build(mod.GeoHashIndex(6), pos)
        for step in range(600):
            did = rng.randrange(400)
            if did in pos and rng.random() < 0.15:
                idx.remove(did)
                del pos[did]
            else:
                la, ln = 37.77 + rng.uniform(-0.2, 0.2), -122.42 + rng.uniform(-0.25, 0.25)
                idx.update(did, la, ln)
                pos[did] = (la, ln)
            if step % 40 == 0:
                q = (37.77 + rng.uniform(-0.2, 0.2), -122.42 + rng.uniform(-0.25, 0.25))
                assert same(idx.knn(q[0], q[1], 8), ref_knn(pos, q[0], q[1], 8)), f"churn seed {s}, step {step}: knn differs from brute force after updates/removals {replay(3, s)}"
        assert len(idx) == len(pos) and idx.footprint() == len({ref_encode(la, ln, 6) for la, ln in pos.values()}), \
            f"churn seed {s}: after updates the index should hold {len(pos)} drivers in {len({ref_encode(la, ln, 6) for la, ln in pos.values()})} non-empty cells; it has {len(idx)} in {idx.footprint()} {replay(3, s)}"
    mean_frac = sum(calls_dense) / len(calls_dense)
    assert mean_frac < 0.35, f"the ring search computed distances to {mean_frac:.0%} of all drivers on average; it should prune to a small neighbourhood"
    return (f"ring(), 4 precisions x 4 places (incl. both poles and the antimeridian) x 5 radii == reference; unsearched_bound valid on {checked:,} outside points and about 2 cells wide at r=2\n"
            f"k-nearest == brute force EXACTLY on 30 city seeds (precisions 5, 6, 7; k = 1, 8, 20), 12 sparse seeds (rings out to ~40 cells), {len(seeds(range(1, 31)))} world seeds ({worldq} queries at the poles and the antimeridian)\n"
            f"ties break by id, results stay exact through 600 moves/removals/re-inserts; on average only {mean_frac:.1%} of drivers got a distance computation")


# ---------------------------------------------------------------------------------------------
def count_nodes(n):
    return 1 if n.kids is None else 1 + sum(count_nodes(k) for k in n.kids)


def leaves(n):
    if n.kids is None:
        yield n
    else:
        for k in n.kids:
            yield from leaves(k)


def check_tree(idx, tag, seed, mnum=4):
    assert count_nodes(idx.root) == idx.footprint(), f"{tag}, seed {seed}: footprint() says {idx.footprint()} nodes but the tree has {count_nodes(idx.root)} (splits/merges not counted?) {replay(mnum, seed)}"
    seen = 0
    for lf in leaves(idx.root):
        seen += len(lf.ids)
        assert len(lf.ids) <= idx.capacity or lf.depth >= idx.max_depth, f"{tag}, seed {seed}: a leaf at depth {lf.depth} holds {len(lf.ids)} > capacity {idx.capacity} drivers: it should have split {replay(mnum, seed)}"
        for did in lf.ids:
            la, ln = idx.pos[did]
            assert idx.leaf[did] is lf and lf.lat0 <= la <= lf.lat1 and lf.lng0 <= ln <= lf.lng1, f"{tag}, seed {seed}: driver {did} is in a leaf whose box does not contain its position {replay(mnum, seed)}"
    assert seen == len(idx) == len(idx.pos) == len(idx.leaf), f"{tag}, seed {seed}: leaves hold {seen} drivers, index says {len(idx)} {replay(mnum, seed)}"


def m4():
    S = seeds(range(1, 31))
    fracs = []
    for s in S:
        rng = random.Random(s)
        cap = (4, 8, 16)[s % 3]
        n = (200, 1500, 600)[s % 3]
        pos = city_points(rng, n)
        qs = [(37.77 + rng.uniform(-0.2, 0.2), -122.42 + rng.uniform(-0.25, 0.25)) for _ in range(15)]
        idx, tot = compare(lambda: mod.QuadTree(cap), pos, qs, (1, 8, 20), f"city cap={cap}", 4, s)
        check_tree(idx, f"cap={cap}", s)
        fracs.append(tot / (len(qs) * 3) / n)
    for s in seeds(range(1, 31)):
        rng = random.Random(900 + s)
        pos = world_points(rng, 60)
        qs = [(rng.uniform(-90, 90), rng.uniform(-180, 180)) for _ in range(5)] + [(90.0, 0.0), (-90.0, 120.0), (10.0, 179.999), (-10.0, -179.999), (89.9, 179.9)]
        idx, _ = compare(lambda: mod.QuadTree(4), pos, qs, (1, 5, 12), "world", 4, s)
        check_tree(idx, "world", s)
    # many drivers on one point: the tree must stop splitting at max_depth
    pos = {i: (12.3456, 65.4321) for i in range(60)}
    pos.update({100 + i: (12.3456 + 0.0001 * i, 65.4321) for i in range(1, 6)})
    idx = build(mod.QuadTree(4, max_depth=12), pos)
    check_tree(idx, "duplicates", 0)
    got = idx.knn(12.3456, 65.4321, 5)
    assert [g[1] for g in got] == [0, 1, 2, 3, 4] and got[0][0] == 0.0, f"sixty drivers on one point: ties break by id; expected [0..4], got {[g[1] for g in got]}"
    # churn: insert / move / delete, tree stays valid and collapses back
    for s in seeds(range(1, 13)):
        rng = random.Random(1700 + s)
        pos = city_points(rng, 300)
        idx = build(mod.QuadTree(6), pos)
        for step in range(900):
            did = rng.randrange(330)
            r = rng.random()
            if did in pos and r < 0.2:
                idx.remove(did)
                del pos[did]
            else:
                if did in pos and r < 0.7:
                    la, ln = pos[did][0] + rng.uniform(-0.0004, 0.0004), pos[did][1] + rng.uniform(-0.0005, 0.0005)       # a short hop
                else:
                    la, ln = 37.77 + rng.uniform(-0.2, 0.2), -122.42 + rng.uniform(-0.25, 0.25)
                idx.update(did, la, ln)
                pos[did] = (la, ln)
            if step % 60 == 0:
                q = (37.77 + rng.uniform(-0.2, 0.2), -122.42 + rng.uniform(-0.25, 0.25))
                assert same(idx.knn(q[0], q[1], 8), ref_knn(pos, q[0], q[1], 8)), f"churn seed {s}, step {step}: knn differs from brute force after updates/removals {replay(4, s)}"
                check_tree(idx, "churn", s)
        for did in list(pos):
            idx.remove(did)
        assert idx.footprint() == 1 and idx.root.kids is None and len(idx) == 0, f"churn seed {s}: after removing every driver the tree should collapse back to a single root leaf; it has {idx.footprint()} nodes {replay(4, s)}"
        assert idx.knn(37.77, -122.42, 3) == [], "knn on an empty tree must return []"
    # a hop inside the same leaf costs no structure change
    idx = mod.QuadTree(8)
    for i in range(7):
        idx.update(i, 37.77 + i * 0.0001, -122.42)
    before = idx.ops
    idx.update(3, 37.77031, -122.42)
    assert idx.ops == before and idx.pos[3] == (37.77031, -122.42), "moving a driver within its leaf is just a position write: ops must not change"
    mean_frac = sum(fracs) / len(fracs)
    assert mean_frac < 0.2, f"the quadtree computed distances to {mean_frac:.0%} of all drivers on average; best-first search should prune far more"
    return (f"k-nearest == brute force EXACTLY on {len(S)} city seeds (capacities 4, 8, 16; k = 1, 8, 20) and 30 world seeds (poles, antimeridian)\n"
            f"tree invariants hold (leaf <= capacity, box contains position, node count); 60 drivers on one point stop at max_depth; ties break by id\n"
            f"900 insert/move/delete steps x 12 seeds stay exact and valid; deleting everything collapses the tree to one root; on average {mean_frac:.1%} of drivers got a distance computation")


# ---------------------------------------------------------------------------------------------
def m5():
    N, TICKS, QPT = 10000, 10, 20
    seed = ONLY_SEED if ONLY_SEED is not None else 1
    idxs = {"brute": RefBrute(), "geohash-6": mod.GeoHashIndex(6), "geohash-7": mod.GeoHashIndex(7), "quadtree-8": mod.QuadTree(8), "quadtree-32": mod.QuadTree(32)}
    out = mod.simulate(seed, idxs, n=N, ticks=TICKS, queries_per_tick=QPT, k=8)
    assert not out["mismatch"], f"seed {seed}: these (tick, query, index) answers differ from brute force: {out['mismatch'][:5]} {replay(5, seed)}"
    rows = out["rows"]
    for nm, idx in idxs.items():
        assert len(idx) == N, f"{nm}: after {TICKS} ticks of updates the index holds {len(idx)} drivers, expected {N} {replay(5, seed)}"
    brute = rows["brute"]
    nq = sum(brute["queries"].values())
    nd = brute["queries"]["downtown"]
    ns = brute["queries"]["suburb"]
    assert nq == TICKS * QPT and nd > 0 and ns > 0, "the workload should contain both downtown and suburb queries"
    assert brute["dist"]["downtown"] + brute["dist"]["suburb"] == nq * N, "brute force should compute exactly one distance per driver per query"
    lines = [f"{N:,} drivers, {TICKS} ticks (~{rows['geohash-6']['updates']:,} position updates per index), {nq} nearest-8 queries ({nd} downtown, {ns} suburb), seed {seed}; every index returned exactly the brute-force answer",
             "index          distance computations per query        cells/nodes looked at       structure ops   footprint",
             "                downtown   suburb    vs brute            downtown   suburb         per update      (cells / nodes)"]
    per = {}
    for nm in ("brute", "geohash-6", "geohash-7", "quadtree-8", "quadtree-32"):
        r = rows[nm]
        dd, ds = r["dist"]["downtown"] / max(nd, 1), r["dist"]["suburb"] / max(ns, 1)
        vd, vs = r["visits"]["downtown"] / max(nd, 1), r["visits"]["suburb"] / max(ns, 1)
        allq = (r["dist"]["downtown"] + r["dist"]["suburb"]) / nq
        per[nm] = allq
        lines.append(f"{nm:<13} {dd:>9.0f} {ds:>9.0f}   {allq / N:>8.2%}         {vd:>11.0f} {vs:>9.0f}          {r['ops'] / max(r['updates'], 1):>8.3f}      {r['footprint']:>9,}")
    for nm in ("geohash-6", "geohash-7"):
        assert per[nm] < 0.20 * N, f"{nm}: {per[nm]:.0f} distance computations per query is {per[nm] / N:.0%} of brute force; a ring search should look at a small neighbourhood {replay(5, seed)}"
    for nm in ("quadtree-8", "quadtree-32"):
        assert per[nm] < 0.03 * N, f"{nm}: {per[nm]:.0f} distance computations per query is {per[nm] / N:.1%} of brute force; best-first search should prune to a few leaves {replay(5, seed)}"
    hs = mod.hotspot(seed, {"brute": RefBrute(), "geohash-6": mod.GeoHashIndex(6), "geohash-7": mod.GeoHashIndex(7), "quadtree-8": mod.QuadTree(8)}, n=3000, k=8, queries=30)
    assert all(v["ok"] for v in hs.values()), f"hotspot: some index disagrees with brute force: {[k for k, v in hs.items() if not v['ok']]}"
    assert hs["geohash-6"]["dist"] > 0.8 * 3000, f"hotspot: a precision-6 cell holds the whole crowd, so the ring search must scan almost all 3000 drivers; yours computed only {hs['geohash-6']['dist']:.0f} per query"
    assert hs["quadtree-8"]["dist"] < 0.05 * 3000, f"hotspot: the quadtree splits where the crowd is and should compute few distances; yours computed {hs['quadtree-8']['dist']:.0f} per query"
    lines.append("")
    lines.append(f"hotspot: 3,000 drivers inside a 300 m square, nearest-8 from inside it (distance computations per query):")
    lines.append("   " + "   ".join(f"{nm} {v['dist']:.0f}" for nm, v in hs.items()))
    return "\n".join(lines)


check(1, "Milestone 1: geohash encode / decode and the cell bounding box", m1)
check(2, "Milestone 2: neighbour cells, across boundaries", m2)
check(3, "Milestone 3: k-nearest drivers by expanding geohash rings", m3)
check(4, "Milestone 4: a quadtree with insert, delete, move and k-nearest", m4)
check(5, "Milestone 5: 10k moving drivers, ring vs quadtree vs brute force", m5)

print(f"\n{sum(results)}/{len(results)} milestones passing  ({time.time() - T0:.1f} s)")
sys.exit(0 if results and all(results) else 1)
