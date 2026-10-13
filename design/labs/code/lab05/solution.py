"""Lab 5: A Geospatial Index.

Geohash cells, neighbours, nearest-driver search by expanding rings, a quadtree, and a
benchmark that counts distance computations instead of timing them. Pure standard library,
seeded and deterministic: nothing reads a clock.

Layout:
  * haversine_m, SpatialIndex, BruteForce      given: the distance, a counting base class, the baseline
  * milestone 1  cell_dims, encode, decode_bbox, decode
  * milestone 2  cell_ij, ij_cell, shift, neighbors
  * milestone 3  ring, unsearched_bound, GeoHashIndex (k-nearest by rings)
  * milestone 4  QuadTree (insert / delete / move / k-nearest)
  * milestone 5  make_city, simulate (given) -> you read the numbers and write down the trade-offs

Every index exposes the same interface:
    update(id, lat, lng)      insert a driver or move it
    remove(id)
    knn(lat, lng, k)          -> [(distance_m, id), ...] sorted by (distance, id), at most k of them
and counts its own work in dist_calls (haversine evaluations), visits (cells or nodes looked at) and
ops (structure changes caused by updates).
"""
import heapq
import math
import random

B32 = "0123456789bcdefghjkmnpqrstuvwxyz"
R_EARTH = 6371008.8          # mean Earth radius in metres
INF = float("inf")
SLACK = 1e-9                 # relative slack when comparing a float distance with a float bound


def haversine_m(lat1, lng1, lat2, lng2):
    """Great-circle distance in metres between two (lat, lng) points in degrees (given)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R_EARTH * math.asin(min(1.0, math.sqrt(a)))


class SpatialIndex:
    """Base class (given): positions plus the counters every index reports."""

    def __init__(self):
        self.pos = {}            # id -> (lat, lng)
        self.dist_calls = 0      # haversine evaluations done on behalf of queries
        self.visits = 0          # cells / nodes looked at by queries
        self.ops = 0             # structure changes caused by updates (cell moves, splits, merges, ...)

    def dist(self, lat, lng, did):
        """Distance from a query point to driver `did`. Always use this, so it is counted."""
        self.dist_calls += 1
        p = self.pos[did]
        return haversine_m(lat, lng, p[0], p[1])

    def __len__(self):
        return len(self.pos)

    def reset_counters(self):
        self.dist_calls = self.visits = self.ops = 0


class BruteForce(SpatialIndex):
    """Scan everything (given): the oracle and the baseline."""

    def update(self, did, lat, lng):
        self.pos[did] = (lat, lng)

    def remove(self, did):
        del self.pos[did]

    def knn(self, lat, lng, k):
        self.visits += 1
        best = sorted((self.dist(lat, lng, d), d) for d in self.pos)
        return best[:k]

    def footprint(self):
        return 0


# ------------------------------------------------------------------------------------
# Milestone 1: geohash encode / decode
# ------------------------------------------------------------------------------------
def cell_dims(precision):
    """(height, width) of a geohash cell in degrees. A geohash interleaves bits, longitude first:
    precision p has 5p bits, of which ceil(5p/2) refine longitude and floor(5p/2) refine latitude.
    The world is 180 degrees tall and 360 wide."""
    lat_bits = 5 * precision // 2
    lng_bits = (5 * precision + 1) // 2
    return 180.0 / (1 << lat_bits), 360.0 / (1 << lng_bits)


def encode(lat, lng, precision=9):
    """Geohash string of `precision` characters for a point. Bisect longitude, then latitude,
    alternately (longitude first): a bit is 1 when the value is >= the midpoint of its range, and the
    range becomes that half. Every 5 bits is one character of B32. Clamp lat to [-90, 90] and lng to
    [-180, 180] first."""
    lat = min(90.0, max(-90.0, lat))
    lng = min(180.0, max(-180.0, lng))
    lat_r, lng_r = [-90.0, 90.0], [-180.0, 180.0]
    out, bits, ch, even = [], 0, 0, True
    while len(out) < precision:
        rng, v = (lng_r, lng) if even else (lat_r, lat)
        mid = (rng[0] + rng[1]) / 2
        ch <<= 1
        if v >= mid:
            ch |= 1
            rng[0] = mid
        else:
            rng[1] = mid
        even = not even
        bits += 1
        if bits == 5:
            out.append(B32[ch])
            bits = ch = 0
    return "".join(out)


def decode_bbox(h):
    """The cell's bounding box (lat_min, lat_max, lng_min, lng_max): replay the bisection the other way."""
    lat_r, lng_r, even = [-90.0, 90.0], [-180.0, 180.0], True
    for c in h:
        v = B32.index(c)
        for shift_ in (4, 3, 2, 1, 0):
            rng = lng_r if even else lat_r
            mid = (rng[0] + rng[1]) / 2
            if (v >> shift_) & 1:
                rng[0] = mid
            else:
                rng[1] = mid
            even = not even
    return lat_r[0], lat_r[1], lng_r[0], lng_r[1]


def decode(h):
    """The centre of the cell: (lat, lng)."""
    a, b, c, d = decode_bbox(h)
    return (a + b) / 2, (c + d) / 2


# ------------------------------------------------------------------------------------
# Milestone 2: neighbours
# ------------------------------------------------------------------------------------
def grid_size(precision):
    """(rows, columns) of the geohash grid at this precision (given)."""
    return (1 << (5 * precision // 2)), (1 << ((5 * precision + 1) // 2))


def cell_ij(h):
    """(row, col) of a cell in the grid: row 0 is the southernmost band, col 0 starts at longitude -180."""
    dlat, dlng = cell_dims(len(h))
    a, _, c, _ = decode_bbox(h)
    return int(round((a + 90.0) / dlat)), int(round((c + 180.0) / dlng))


def ij_cell(row, col, precision):
    """The geohash of the cell at (row, col)."""
    dlat, dlng = cell_dims(precision)
    return encode(-90.0 + (row + 0.5) * dlat, -180.0 + (col + 0.5) * dlng, precision)


def shift(h, di, dj):
    """The cell di rows north and dj columns east of h (negative = south / west), or None if that
    would go past a pole. Columns wrap around the antimeridian (longitude +180 meets -180)."""
    nrows, ncols = grid_size(len(h))
    row, col = cell_ij(h)
    row += di
    if row < 0 or row >= nrows:
        return None
    return ij_cell(row, (col + dj) % ncols, len(h))


DIRS = {"n": (1, 0), "ne": (1, 1), "e": (0, 1), "se": (-1, 1), "s": (-1, 0), "sw": (-1, -1), "w": (0, -1), "nw": (1, -1)}


def neighbors(h):
    """{'n': hash-or-None, 'ne': ..., 'e': ..., 'se': ..., 's': ..., 'sw': ..., 'w': ..., 'nw': ...}.
    A neighbour that would lie beyond a pole is None."""
    return {name: shift(h, di, dj) for name, (di, dj) in DIRS.items()}


# ------------------------------------------------------------------------------------
# Milestone 3: k-nearest by expanding rings
# ------------------------------------------------------------------------------------
def ring(h, r):
    """The cells at Chebyshev distance exactly r from h (r = 0 is [h]), as a sorted list of unique
    hashes. Columns wrap; rows beyond a pole are skipped. When the ring wraps all the way round the
    world, the same cell must not appear twice."""
    if r == 0:
        return [h]
    p = len(h)
    nrows, ncols = grid_size(p)
    row, col = cell_ij(h)
    cells = set()
    for dj in range(-r, r + 1):                       # the top and bottom rows of the square ring
        for di in (-r, r):
            if 0 <= row + di < nrows:
                cells.add((row + di, (col + dj) % ncols))
    for di in range(-r + 1, r):                       # the left and right columns, without the corners
        if 0 <= row + di < nrows:
            for dj in (-r, r):
                cells.add((row + di, (col + dj) % ncols))
    return sorted(ij_cell(i, j, p) for i, j in cells)


def unsearched_bound(lat, h, r):
    """A lower bound, in metres, on the distance from a point at latitude `lat` inside cell h to ANY
    point outside the (2r+1) x (2r+1) block of cells centred on h (rings 0..r). INF if the block already
    covers the whole world.

    Anything outside the block is either more than r rows away, so at least r * cell_height of latitude
    away, which is at least R * radians(r * dlat) metres; or more than r columns away, so at least
    r * cell_width of longitude away. A point at longitude offset delta from you is at least
    R * asin(cos(lat) * sin(delta)) metres away (delta capped at 90 degrees). Return the smaller of the
    two. A direction that is closed (the block touches both poles; the block wraps all columns) does not
    count."""
    p = len(h)
    nrows, ncols = grid_size(p)
    dlat, dlng = cell_dims(p)
    row, _ = cell_ij(h)
    bounds = []
    if row + r < nrows - 1 or row - r > 0:
        bounds.append(R_EARTH * math.radians(r * dlat))
    if 2 * r + 1 < ncols:
        delta = min(90.0, r * dlng)
        s = abs(math.cos(math.radians(lat))) * math.sin(math.radians(delta))
        bounds.append(R_EARTH * math.asin(min(1.0, s)))
    return min(bounds) if bounds else INF


class GeoHashIndex(SpatialIndex):
    """Drivers bucketed by geohash cell at one fixed precision."""

    def __init__(self, precision):
        super().__init__()
        self.precision = precision
        self.cells = {}          # hash -> set of ids
        self.where = {}          # id -> hash

    def update(self, did, lat, lng):
        """Insert or move. Only touch the cell sets when the cell actually changes (count that in self.ops)."""
        h = encode(lat, lng, self.precision)
        old = self.where.get(did)
        if old != h:
            if old is not None:
                self.cells[old].discard(did)
                if not self.cells[old]:
                    del self.cells[old]
            self.cells.setdefault(h, set()).add(did)
            self.where[did] = h
            self.ops += 1
        self.pos[did] = (lat, lng)

    def remove(self, did):
        h = self.where.pop(did)
        self.cells[h].discard(did)
        if not self.cells[h]:
            del self.cells[h]
        del self.pos[did]
        self.ops += 1

    def footprint(self):
        """Non-empty cells (memory proxy)."""
        return len(self.cells)

    def knn(self, lat, lng, k, max_rings=None):
        """The k nearest drivers, [(distance_m, id), ...] sorted by (distance, id).

        Search ring 0, ring 1, ... Stop when you hold k candidates and the k-th is strictly closer than
        unsearched_bound(...) for the rings searched so far (use the SLACK constant: compare
        kth < bound * (1 - SLACK)), or when unsearched_bound is INF (the whole world is covered), or when
        max_rings is given and exceeded. Count every cell looked at in self.visits and every distance via
        self.dist."""
        h0 = encode(lat, lng, self.precision)
        best = []
        r = 0
        while True:
            for c in ring(h0, r):
                self.visits += 1
                for did in self.cells.get(c, ()):
                    best.append((self.dist(lat, lng, did), did))
            best.sort()
            del best[k:]
            bound = unsearched_bound(lat, h0, r)
            if bound == INF or (len(best) == k and best[-1][0] < bound * (1 - SLACK)):
                break
            r += 1
            if max_rings is not None and r > max_rings:
                break
        return best


# ------------------------------------------------------------------------------------
# Milestone 4: bucket quadtree
# ------------------------------------------------------------------------------------
def rect_lower_bound(lat, lng, lat0, lat1, lng0, lng1):
    """A lower bound in metres on the distance from (lat, lng) to any point of the lat/lng rectangle
    (given). Latitude gap: R * radians(gap). Longitude gap (circular, capped at 90 degrees):
    R * asin(cos(lat) * sin(gap)). The larger of the two is still a lower bound."""
    gap_lat = lat0 - lat if lat < lat0 else (lat - lat1 if lat > lat1 else 0.0)
    if lng0 <= lng <= lng1:
        gap_lng = 0.0
    else:
        gap_lng = min((lng0 - lng) % 360.0, (lng - lng1) % 360.0)
    gap_lng = min(gap_lng, 90.0)
    b1 = R_EARTH * math.radians(gap_lat)
    b2 = R_EARTH * math.asin(min(1.0, abs(math.cos(math.radians(lat))) * math.sin(math.radians(gap_lng))))
    return max(b1, b2)


class _Node:
    __slots__ = ("lat0", "lat1", "lng0", "lng1", "depth", "parent", "kids", "ids")

    def __init__(self, lat0, lat1, lng0, lng1, depth, parent):
        self.lat0, self.lat1, self.lng0, self.lng1 = lat0, lat1, lng0, lng1
        self.depth, self.parent = depth, parent
        self.kids = None         # None for a leaf, else [sw, se, nw, ne]
        self.ids = set()         # leaf only


class QuadTree(SpatialIndex):
    """A bucket (PR) quadtree over lat/lng: a leaf holds up to `capacity` drivers; one that overflows splits
    into four equal quadrants (sw, se, nw, ne) unless it is already at max_depth. A point belongs to the
    quadrant with lat >= mid and/or lng >= mid on the upper side, so every point lies in exactly one leaf."""

    def __init__(self, capacity=8, max_depth=24):
        super().__init__()
        self.capacity, self.max_depth = capacity, max_depth
        self.root = _Node(-90.0, 90.0, -180.0, 180.0, 0, None)
        self.leaf = {}           # id -> leaf node holding it
        self.nodes = 1

    @staticmethod
    def _kid_index(n, lat, lng):
        return (2 if lat >= (n.lat0 + n.lat1) / 2 else 0) + (1 if lng >= (n.lng0 + n.lng1) / 2 else 0)

    @staticmethod
    def _inside(n, lat, lng):
        return (n.lat0 <= lat < n.lat1 or (n.lat1 == 90.0 and lat == 90.0)) and \
               (n.lng0 <= lng < n.lng1 or (n.lng1 == 180.0 and lng == 180.0))

    def _descend(self, lat, lng):
        n = self.root
        while n.kids is not None:
            n = n.kids[self._kid_index(n, lat, lng)]
        return n

    def _split(self, n):
        """Turn leaf n into an inner node with four leaf children and push its drivers down; recurse if
        they all landed in one child and it is now over capacity."""
        la, lb, ga, gb = n.lat0, n.lat1, n.lng0, n.lng1
        lm, gm = (la + lb) / 2, (ga + gb) / 2
        d = n.depth + 1
        n.kids = [_Node(la, lm, ga, gm, d, n), _Node(la, lm, gm, gb, d, n),
                  _Node(lm, lb, ga, gm, d, n), _Node(lm, lb, gm, gb, d, n)]
        self.nodes += 4
        self.ops += 1
        for did in n.ids:
            lat, lng = self.pos[did]
            kid = n.kids[self._kid_index(n, lat, lng)]
            kid.ids.add(did)
            self.leaf[did] = kid
        n.ids = set()
        for kid in n.kids:
            if len(kid.ids) > self.capacity and kid.depth < self.max_depth:
                self._split(kid)

    def _collapse(self, n):
        """Walk up from inner node n: while all four children are leaves holding at most `capacity`
        drivers in total, merge them back into n (n becomes a leaf)."""
        while n is not None and n.kids is not None:
            if any(k.kids is not None for k in n.kids):
                return
            total = sum(len(k.ids) for k in n.kids)
            if total > self.capacity:
                return
            ids = set()
            for k in n.kids:
                ids |= k.ids
            n.kids, n.ids = None, ids
            for did in ids:
                self.leaf[did] = n
            self.nodes -= 4
            self.ops += 1
            n = n.parent

    def update(self, did, lat, lng):
        """Insert, or move. A move that stays inside the driver's current leaf only changes its stored
        position (no structure change); otherwise remove it and insert it again."""
        old = self.leaf.get(did)
        if old is not None:
            if self._inside(old, lat, lng):
                self.pos[did] = (lat, lng)
                return
            self.remove(did)
        self.pos[did] = (lat, lng)
        n = self._descend(lat, lng)
        n.ids.add(did)
        self.leaf[did] = n
        if len(n.ids) > self.capacity and n.depth < self.max_depth:
            self._split(n)

    def remove(self, did):
        n = self.leaf.pop(did)
        n.ids.discard(did)
        del self.pos[did]
        self._collapse(n.parent)

    def footprint(self):
        """Nodes in the tree (memory proxy)."""
        return self.nodes

    def knn(self, lat, lng, k):
        """Best-first search: a heap of (lower_bound, tiebreak, node) starting at the root. Pop the node with the
        smallest bound; stop when you hold k candidates and that bound exceeds the k-th distance (with the
        SLACK constant: stop when bound > kth * (1 + SLACK) + 1e-6). A leaf: compute distances with self.dist and
        keep the best k as (distance, id). An inner node: push its four children with their rect_lower_bound.
        Count each node popped in self.visits."""
        best = []
        heap = [(0.0, 0, self.root)]
        tie = 1
        while heap:
            lb, _, n = heapq.heappop(heap)
            if len(best) == k and lb > best[-1][0] * (1 + SLACK) + 1e-6:
                break
            self.visits += 1
            if n.kids is None:
                for did in n.ids:
                    best.append((self.dist(lat, lng, did), did))
                best.sort()
                del best[k:]
            else:
                for kid in n.kids:
                    heapq.heappush(heap, (rect_lower_bound(lat, lng, kid.lat0, kid.lat1, kid.lng0, kid.lng1), tie, kid))
                    tie += 1
        return best


# ------------------------------------------------------------------------------------
# Milestone 5: the simulation (given). You build nothing here: you run it and read the numbers.
# ------------------------------------------------------------------------------------
CITY = (37.77, -122.42)                       # centre; the box is about 40 km x 40 km
HALF_LAT, HALF_LNG = 0.18, 0.228
HOTSPOTS = [(0.00, 0.00, 1.2), (0.06, 0.05, 1.0), (-0.07, 0.08, 1.5), (0.09, -0.07, 1.0), (-0.05, -0.09, 0.8)]  # (dlat, dlng, sigma in km)


def _clamp_city(lat, lng):
    return (min(CITY[0] + HALF_LAT, max(CITY[0] - HALF_LAT, lat)), min(CITY[1] + HALF_LNG, max(CITY[1] - HALF_LNG, lng)))


def make_city(rng, n):
    """n driver positions: 60% in gaussian clusters around five hotspots, 40% spread uniformly (the suburbs)."""
    pts = []
    for _ in range(n):
        if rng.random() < 0.6:
            dlat, dlng, sig = HOTSPOTS[rng.randrange(len(HOTSPOTS))]
            pts.append(_clamp_city(CITY[0] + dlat + rng.gauss(0, sig / 111.0), CITY[1] + dlng + rng.gauss(0, sig / 88.0)))
        else:
            pts.append((CITY[0] + rng.uniform(-HALF_LAT, HALF_LAT), CITY[1] + rng.uniform(-HALF_LNG, HALF_LNG)))
    return pts


def is_downtown(lat, lng):
    return any(haversine_m(lat, lng, CITY[0] + a, CITY[1] + b) < 2500 for a, b, _ in HOTSPOTS)


def simulate(seed, indexes, n=10000, ticks=10, queries_per_tick=20, k=8):
    """Run the same workload against every index in `indexes` (dict name -> index). Each tick, every driver
    reports a new position (a short random step; a third stay put), then `queries_per_tick` riders ask for their
    k nearest drivers. Returns {'results': [per-query answers of the first index], 'mismatch': [(tick, q, name)],
    'rows': {name: dict of counters}} ; counters are totals over the run, split into downtown / suburb queries."""
    rng = random.Random(seed)
    pts = make_city(rng, n)
    for idx in indexes.values():
        for i, (la, ln) in enumerate(pts):
            idx.update(i, la, ln)
        idx.reset_counters()
    names = list(indexes)
    stats = {nm: {"updates": 0, "queries": {"downtown": 0, "suburb": 0}, "dist": {"downtown": 0, "suburb": 0},
                  "visits": {"downtown": 0, "suburb": 0}} for nm in names}
    mismatch, answers = [], []
    for t in range(ticks):
        for i in range(n):
            if rng.random() < 0.34:
                continue                                    # a third of the drivers did not move
            la, ln = pts[i]
            ang = rng.random() * 2 * math.pi
            step = rng.uniform(10, 60)                      # metres in 4 seconds
            la, ln = _clamp_city(la + step * math.cos(ang) / 111000.0, ln + step * math.sin(ang) / 88000.0)
            pts[i] = (la, ln)
            for nm in names:
                indexes[nm].update(i, la, ln)
                stats[nm]["updates"] += 1
        qs = make_city(rng, queries_per_tick)
        for qi, (la, ln) in enumerate(qs):
            cls = "downtown" if is_downtown(la, ln) else "suburb"
            ref = None
            for nm in names:
                idx = indexes[nm]
                d0, v0 = idx.dist_calls, idx.visits
                got = idx.knn(la, ln, k)
                stats[nm]["queries"][cls] += 1
                stats[nm]["dist"][cls] += idx.dist_calls - d0
                stats[nm]["visits"][cls] += idx.visits - v0
                if ref is None:
                    ref = got
                    answers.append(got)
                elif [x[1] for x in got] != [x[1] for x in ref] or any(abs(a[0] - b[0]) > 1e-6 for a, b in zip(got, ref)):
                    mismatch.append((t, qi, nm))
    for nm in names:
        stats[nm]["ops"] = indexes[nm].ops
        stats[nm]["footprint"] = indexes[nm].footprint()
    return {"answers": answers, "mismatch": mismatch, "rows": stats}


def hotspot(seed, indexes, n=3000, k=8, queries=30):
    """Stress case (given): n drivers packed inside a ~300 m square (a stadium letting out), then `queries`
    nearest-k queries from inside it. Returns {name: distance computations per query}."""
    rng = random.Random(seed)
    crowd = [(CITY[0] + rng.uniform(0, 0.0027), CITY[1] + rng.uniform(0, 0.0034)) for _ in range(n)]
    for idx in indexes.values():
        for i, (la, ln) in enumerate(crowd):
            idx.update(i, la, ln)
        idx.reset_counters()
    out = {}
    qrng = random.Random(seed + 1)
    qs = [(CITY[0] + qrng.uniform(0, 0.0027), CITY[1] + qrng.uniform(0, 0.0034)) for _ in range(queries)]
    ref = None
    for nm, idx in indexes.items():
        ans = [idx.knn(la, ln, k) for la, ln in qs]
        if ref is None:
            ref = ans
        out[nm] = {"dist": idx.dist_calls / queries, "visits": idx.visits / queries, "ok": [[x[1] for x in a] for a in ans] == [[x[1] for x in a] for a in ref]}
    return out
