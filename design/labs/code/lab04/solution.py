"""Lab 4: Sketches, Count-Min, HyperLogLog and Top-K.

Approximate counting with error bounds you can test. Everything is deterministic: hashes
come from hashlib (never Python's built-in hash(), which is salted per process), every
random draw in the checks comes from a seeded random.Random, nothing reads a clock.

Layout:
  * h64                       given: a seeded 64-bit hash built on hashlib.blake2b
  * milestone 1  cms_dims, CountMin.add / estimate
  * milestone 2  CountMin.merge
  * milestone 3  SpaceSaving (heavy hitters / top-k with per-item error)
  * milestone 4  HyperLogLog (registers, small-range correction, merge)
  * milestone 5  trend_score, TrendingDetector (tumbling windows of sketches vs a baseline)
"""
import hashlib
import heapq
import math
from collections import deque

MASK64 = (1 << 64) - 1


def h64(key, seed=0):
    """A seeded 64-bit hash of `key` (given). Same (key, seed) gives the same number in every
    process on every machine; different seeds behave like independent hash functions."""
    k = (seed & MASK64).to_bytes(8, "big")
    return int.from_bytes(hashlib.blake2b(str(key).encode(), digest_size=8, key=k).digest(), "big")


# ------------------------------------------------------------------------------------
# Milestones 1 and 2: Count-Min sketch
# ------------------------------------------------------------------------------------
def cms_dims(eps, delta):
    """Width and depth of a Count-Min sketch whose estimate is within eps * N of the truth
    with probability at least 1 - delta:  w = ceil(e / eps),  d = ceil(ln(1 / delta)).
    Returns (w, d)."""
    return math.ceil(math.e / eps), math.ceil(math.log(1.0 / delta))


class CountMin:
    """A d x w table of counters. add() bumps one cell per row; estimate() takes the minimum.

    Row r uses the hash function h64(key, seed * 1_000_003 + r) % w, so two sketches with the same
    (w, d, seed) hash identically and can be merged. `n` is the total weight added so far.
    """

    def __init__(self, eps, delta, seed=0, width=None, depth=None):
        """Size the table from (eps, delta) with cms_dims unless width/depth are forced (the checks
        force them to build deliberately undersized sketches). Keep self.eps, self.delta, self.seed,
        self.w, self.d, self.table (list of d lists of w zeros) and self.n = 0."""
        w, d = cms_dims(eps, delta)
        self.eps, self.delta, self.seed = eps, delta, seed
        self.w = width if width else w
        self.d = depth if depth else d
        self.table = [[0] * self.w for _ in range(self.d)]
        self.n = 0

    def _col(self, row, key):
        return h64(key, self.seed * 1_000_003 + row) % self.w

    def add(self, key, count=1):
        """Add `count` (>= 0) occurrences of key: bump the key's cell in every row, and self.n."""
        self.n += count
        for r in range(self.d):
            self.table[r][self._col(r, key)] += count

    def estimate(self, key):
        """Never below the true count. Minimum over the d cells the key hashes to."""
        return min(self.table[r][self._col(r, key)] for r in range(self.d))

    def error_bound(self):
        """The additive error the sketch promises right now: eps * n (given)."""
        return self.eps * self.n

    def compatible(self, other):
        """True if the two sketches use the same shape and the same hash functions (given)."""
        return (self.w, self.d, self.seed) == (other.w, other.d, other.seed)

    def merge(self, other):
        """Return a NEW sketch equal to the sketch of the union of both streams: add the tables
        cell by cell and add the totals. Raise ValueError if the sketches are not compatible
        (different width, depth or seed: adding their cells would be meaningless)."""
        if not self.compatible(other):
            raise ValueError("cannot merge count-min sketches with different (width, depth, seed)")
        out = CountMin(self.eps, self.delta, self.seed, width=self.w, depth=self.d)
        out.table = [[a + b for a, b in zip(r1, r2)] for r1, r2 in zip(self.table, other.table)]
        out.n = self.n + other.n
        return out


# ------------------------------------------------------------------------------------
# Milestone 3: Space-Saving heavy hitters
# ------------------------------------------------------------------------------------
class SpaceSaving:
    """Metwally et al.: keep at most m counters (key -> count, err).

    * key is tracked:        count += c
    * new key, a free slot:  count = c, err = 0
    * new key, table full:   evict the tracked key with the smallest count (ties: smallest key),
                             the newcomer inherits it:  count = old_min + c, err = old_min

    Guarantees for a stream of total weight N:  count - err <= true <= count for tracked keys;
    an untracked key has true <= min counter <= N / m; every key with true > N / m is tracked;
    and the counts always sum to N.
    """

    def __init__(self, m):
        self.m = m
        self.count = {}
        self.err = {}
        self.n = 0
        self._heap = []          # (count, key) entries, lazily invalidated: stale if count[key] != entry count

    def _min_entry(self):
        """Smallest (count, key) among tracked keys; pops stale heap entries on the way."""
        while self._heap:
            c, k = self._heap[0]
            if self.count.get(k) == c:
                return c, k
            heapq.heappop(self._heap)
        return None

    def update(self, key, c=1):
        """Observe `c` more occurrences of key."""
        self.n += c
        if key in self.count:
            self.count[key] += c
        elif len(self.count) < self.m:
            self.count[key] = c
            self.err[key] = 0
        else:
            old, victim = self._min_entry()
            del self.count[victim]
            del self.err[victim]
            self.count[key] = old + c
            self.err[key] = old
        heapq.heappush(self._heap, (self.count[key], key))
        if len(self._heap) > 8 * self.m + 64:            # keep the lazy heap from growing without bound
            self._heap = [(v, k) for k, v in self.count.items()]
            heapq.heapify(self._heap)

    def min_count(self):
        """Upper bound on the true count of any key that is NOT tracked: the smallest counter if
        the table is full, else 0 (every key seen so far is tracked)."""
        if len(self.count) < self.m:
            return 0
        return self._min_entry()[0]

    def bounds(self, key):
        """(lower, upper) bounds on the true count of key."""
        if key in self.count:
            return self.count[key] - self.err[key], self.count[key]
        return 0, self.min_count()

    def top(self, k):
        """The k tracked keys with the largest counters, as (key, count, err), largest first,
        ties broken by key."""
        items = sorted(self.count.items(), key=lambda kv: (-kv[1], kv[0]))[:k]
        return [(key, c, self.err[key]) for key, c in items]

    def guaranteed(self, k):
        """True if the k keys returned by top(k) are PROVABLY the true top-k set: the smallest lower
        bound among them (count - err) is strictly greater than the largest upper bound of everything
        else (the (k+1)-th counter, or min_count() if there is no (k+1)-th)."""
        items = sorted(self.count.items(), key=lambda kv: (-kv[1], kv[0]))
        if len(items) <= k:
            return all(self.err[key] == 0 for key, _ in items) and len(self.count) < self.m
        lower = min(c - self.err[key] for key, c in items[:k])
        upper = items[k][1]
        return lower > upper


# ------------------------------------------------------------------------------------
# Milestone 4: HyperLogLog
# ------------------------------------------------------------------------------------
class HyperLogLog:
    """m = 2**p registers. The top p bits of a 64-bit hash choose a register; the register keeps
    the largest rho seen, where rho = position of the leftmost 1 bit among the remaining 64 - p
    bits (1-based; an all-zero remainder gives 64 - p + 1). Standard error is about 1.04 / sqrt(m)."""

    def __init__(self, p=12, seed=0):
        self.p, self.m, self.seed = p, 1 << p, seed
        self.reg = [0] * self.m

    def add_hash(self, x):
        """Fold one 64-bit hash value into the registers."""
        idx = x >> (64 - self.p)
        rest = x & ((1 << (64 - self.p)) - 1)
        rho = (64 - self.p) - rest.bit_length() + 1
        if rho > self.reg[idx]:
            self.reg[idx] = rho

    def add(self, item):
        """Count an item: hash it with h64 and a seed, then add_hash (given)."""
        self.add_hash(h64(item, self.seed))

    def count(self):
        """Estimated number of distinct items.

        raw = alpha * m^2 / sum(2 ** -reg[i])  with alpha = 0.7213 / (1 + 1.079 / m).
        Small-range correction: if raw <= 2.5 * m and some register is still zero (V of them),
        use linear counting instead:  m * ln(m / V).  Otherwise return raw."""
        m = self.m
        alpha = 0.7213 / (1 + 1.079 / m)
        raw = alpha * m * m / sum(2.0 ** -r for r in self.reg)
        if raw <= 2.5 * m:
            zeros = self.reg.count(0)
            if zeros:
                return m * math.log(m / zeros)
        return raw

    def merge(self, other):
        """Return a NEW HyperLogLog for the union of both sets: the register-wise maximum.
        Raise ValueError if p or seed differ."""
        if (self.p, self.seed) != (other.p, other.seed):
            raise ValueError("cannot merge HyperLogLogs with different p or seed")
        out = HyperLogLog(self.p, self.seed)
        out.reg = [max(a, b) for a, b in zip(self.reg, other.reg)]
        return out


# ------------------------------------------------------------------------------------
# Milestone 5: windowed trending detector
# ------------------------------------------------------------------------------------
def trend_score(cur, base, alpha):
    """How much hotter than normal is a key?  (cur + alpha) / (base + alpha).
    `alpha` is a smoothing constant (in events): a key that goes from 0 to 5 events must not
    score 6x just because its baseline was zero."""
    return (cur + alpha) / (base + alpha)


class TrendingDetector:
    """Tumbling windows of `window_s` seconds over EVENT time. For each window keep a CountMin
    (frequencies), a SpaceSaving (candidate keys) and the total event count. When a window closes:

      * if at least `baseline_windows` earlier windows exist, merge the last `baseline_windows`
        CountMin sketches into a baseline, and for every candidate key (the SpaceSaving keys of the
        window that just closed) compute
            cur   = this window's CountMin estimate
            base  = baseline estimate / baseline_windows, scaled by (this window's n / mean n of the
                    baseline windows) so that a day-wide traffic surge is not a trend
            score = trend_score(cur, base, alpha)
        and record an alert (window, key, score, cur) when cur >= min_count and score >= ratio;
      * then push the window onto the history (keep only the last `baseline_windows`).
    """

    def __init__(self, window_s=60, baseline_windows=4, eps=0.005, delta=0.01, candidates=40,
                 alpha=10.0, ratio=4.0, min_count=100, seed=7):
        self.window_s, self.B = window_s, baseline_windows
        self.eps, self.delta, self.cands, self.seed = eps, delta, candidates, seed
        self.alpha, self.ratio, self.min_count = alpha, ratio, min_count
        self.history = deque(maxlen=baseline_windows)    # (CountMin, SpaceSaving, n) of closed windows
        self.cur_w = None
        self.cms = self.ss = None
        self.n = 0
        self.late = 0
        self.alerts = []                                  # (window, key, score, cur)

    def _open(self, w):
        self.cur_w = w
        self.cms = CountMin(self.eps, self.delta, self.seed)
        self.ss = SpaceSaving(self.cands)
        self.n = 0

    def observe(self, ts, key):
        """One event at event time `ts` (seconds). Window index = int(ts // window_s). Events arrive
        in nondecreasing window order: moving to a later window closes the current one (and any empty
        windows in between must be closed as empty ones, so the baseline is not stretched over a gap).
        An event for a window that is already closed is late: count it in self.late and drop it."""
        w = int(ts // self.window_s)
        if self.cur_w is None:
            self._open(w)
        if w < self.cur_w:
            self.late += 1
            return
        while self.cur_w < w:
            self._close()
            self._open(self.cur_w + 1)
        self.cms.add(key)
        self.ss.update(key)
        self.n += 1

    def flush(self):
        """Close the current window (end of stream)."""
        if self.cur_w is not None:
            self._close()
            self.cur_w = None

    def _close(self):
        if len(self.history) == self.B:
            base_cms = self.history[0][0]
            for cms, _, _ in list(self.history)[1:]:
                base_cms = base_cms.merge(cms)
            mean_n = sum(n for _, _, n in self.history) / self.B
            scale = (self.n / mean_n) if mean_n else 1.0
            for key in sorted(self.ss.count):
                cur = self.cms.estimate(key)
                base = base_cms.estimate(key) / self.B * scale
                score = trend_score(cur, base, self.alpha)
                if cur >= self.min_count and score >= self.ratio:
                    self.alerts.append((self.cur_w, key, score, cur))
        self.history.append((self.cms, self.ss, self.n))
