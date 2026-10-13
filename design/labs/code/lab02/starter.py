"""Lab 2: Rate Limiters, your starter.

Everything here runs on simulated time. Nothing sleeps, nothing touches a socket, every
random draw comes from a seeded random.Random, so a run with the same seed is identical.

Layout:
  * ManualClock / SimClock       the injected clocks (the limiters never call time.time())
  * milestone 1  TokenBucket
  * milestone 2  SlidingWindowLog, SlidingWindowCounter (FixedWindow is given, as a baseline)
  * milestone 3  max_in_window, replay, make_trace
  * simulation   Sim, Network, Store (a Redis-like shared store), rpc(), run_global, run_local
  * milestone 4  Store.get / Store.incr (atomic, with a TTL), GlobalLimiter.request
  * milestone 5  LocalSyncNode, GlobalLimiter.failed (fail-open / closed / local), clock skew

Times in the traces are multiples of 1/1024 s so that all the arithmetic is exact in floating
point; that lets the property tests demand exact answers at window edges.
"""
import heapq
import math
import random
from collections import deque, namedtuple

EPS = 1e-9
QUANTUM = 1.0 / 1024.0


# ------------------------------------------------------------------------------------
# Clocks (given). A limiter takes a clock object with .now(); tests drive time by hand.
# ------------------------------------------------------------------------------------
class ManualClock:
    """A clock that only moves when you move it."""

    def __init__(self, t=0.0):
        self.t = float(t)

    def now(self):
        return self.t

    def advance(self, dt):
        self.t += dt

    def set(self, t):
        self.t = float(t)


class SimClock:
    """The simulator's time as seen by one node: true time plus that node's skew."""

    def __init__(self, sim, skew=0.0):
        self.sim, self.skew = sim, skew

    def now(self):
        return self.sim.now + self.skew


# ------------------------------------------------------------------------------------
# Milestone 1: the token bucket
# ------------------------------------------------------------------------------------
class TokenBucket:
    """Tokens drip in at `rate` per second up to `capacity`; each request spends `cost`.

    The bucket is lazy: no timer fills it. Every call first adds rate x (time since the
    last call), capped at capacity. It starts full.
    """

    def __init__(self, rate, capacity, clock):
        self.rate = float(rate)
        self.capacity = float(capacity)
        self.clock = clock
        self._tokens = float(capacity)
        self._last = clock.now()

    def _refill(self):
        raise NotImplementedError("TODO milestone 1: TokenBucket._refill")

    def tokens(self):
        """Tokens available right now (after refilling)."""
        raise NotImplementedError("TODO milestone 1: TokenBucket.tokens")

    def allow(self, cost=1.0):
        """Spend `cost` tokens and return True, or return False and spend nothing."""
        raise NotImplementedError("TODO milestone 1: TokenBucket.allow")

    def retry_after(self, cost=1.0):
        """Seconds until `cost` tokens will be available (0.0 if they are now)."""
        raise NotImplementedError("TODO milestone 1: TokenBucket.retry_after")


# ------------------------------------------------------------------------------------
# Milestone 2: sliding windows
# ------------------------------------------------------------------------------------
class FixedWindow:
    """Given, as a baseline: one counter per aligned window. Cheap, and wrong at the edges."""

    def __init__(self, limit, window, clock):
        self.limit, self.window, self.clock = limit, window, clock
        self._idx, self._count = None, 0

    def allow(self):
        idx = math.floor(self.clock.now() / self.window)
        if idx != self._idx:
            self._idx, self._count = idx, 0
        if self._count < self.limit:
            self._count += 1
            return True
        return False


class SlidingWindowLog:
    """Exact: remember the timestamp of every admitted request in the last `window` seconds.

    A request at time t is admitted if fewer than `limit` admitted requests lie in the
    half-open interval (t - window, t]. Rejected requests are not logged.
    """

    def __init__(self, limit, window, clock):
        self.limit, self.window, self.clock = limit, window, clock
        self._log = deque()

    def allow(self):
        raise NotImplementedError("TODO milestone 2: SlidingWindowLog.allow")


class SlidingWindowCounter:
    """Approximate: two counters (this window, the previous one) and a weighted sum.

    estimate = previous x (1 - fraction of the current window elapsed) + current.
    A request is admitted if estimate + 1 <= limit. The estimate assumes the previous
    window's requests were spread evenly, which is where the error comes from.
    """

    def __init__(self, limit, window, clock):
        self.limit, self.window, self.clock = limit, window, clock
        self._idx = math.floor(clock.now() / window)
        self._cur, self._prev = 0, 0

    def _roll(self, now):
        raise NotImplementedError("TODO milestone 2: SlidingWindowCounter._roll")

    def estimate(self):
        """The weighted estimate of requests in the last `window` seconds."""
        raise NotImplementedError("TODO milestone 2: SlidingWindowCounter.estimate")

    def allow(self):
        raise NotImplementedError("TODO milestone 2: SlidingWindowCounter.allow")


# ------------------------------------------------------------------------------------
# Milestone 3: property-test helpers
# ------------------------------------------------------------------------------------
def max_in_window(times, window):
    """The largest number of `times` (sorted) inside any half-open interval of length `window`.

    Two pointers: for each right end j, move i forward while times[j] - times[i] >= window.
    """
    raise NotImplementedError("TODO milestone 3: max_in_window")


def replay(limiter, clock, times):
    """Feed the request times to the limiter (setting the manual clock first); return admitted times."""
    raise NotImplementedError("TODO milestone 3: replay")


def _q(t):
    """Snap a time down to the 1/1024 s grid."""
    return math.floor(t / QUANTUM) * QUANTUM


def make_trace(kind, seed, duration, rate):
    """A sorted list of request times in [0, duration), on the 1/1024 s grid.

    kinds:
      "steady"  evenly spaced, `rate` per second
      "poisson" random gaps with mean 1/rate
      "bursty"  bursts of about rate/4 requests packed into 50 ms, 4 bursts a second on average
      "edges"   at every whole second, half a second's traffic just before and half just after
    """
    raise NotImplementedError("TODO milestone 3: make_trace")


# ------------------------------------------------------------------------------------
# The simulation kit (given): an event loop, a network, a shared store, an RPC helper
# ------------------------------------------------------------------------------------
class Sim:
    """A discrete-event loop: a heap of (time, tie-breaker, function, args)."""

    def __init__(self):
        self.now = 0.0
        self._q = []
        self._n = 0

    def schedule(self, delay, fn, *args):
        heapq.heappush(self._q, (self.now + max(0.0, delay), self._n, fn, args))
        self._n += 1

    def run(self, until=None):
        while self._q:
            t, _, fn, args = self._q[0]
            if until is not None and t > until:
                break
            heapq.heappop(self._q)
            self.now = t
            fn(*args)
        if until is not None:
            self.now = max(self.now, until)


class Network:
    """One-way delays drawn uniformly from [lo, hi] seconds with a seeded generator."""

    def __init__(self, rng, lo=0.001, hi=0.005):
        self.rng, self.lo, self.hi = rng, lo, hi

    def delay(self):
        return self.rng.uniform(self.lo, self.hi)


class Store:
    """A Redis-like shared store: keys with integer values and a time to live.

    Everything a method does happens at a single instant of simulated time, so each
    method is atomic with respect to every other (like a Redis command or a Lua script).
    Expiry is judged by the STORE's clock, which is simply sim.now.
    """

    def __init__(self, sim, down=()):
        self.sim = sim
        self.data = {}          # key -> [value, expires_at]
        self.down = list(down)  # outage intervals (t0, t1)

    def now(self):
        return self.sim.now

    def is_down(self):
        return any(a <= self.sim.now < b for a, b in self.down)

    def _live(self, key):
        item = self.data.get(key)
        if item is None:
            return None
        if item[1] <= self.sim.now:
            del self.data[key]
            return None
        return item

    def get(self, key):
        """The value of `key`, or 0 if it is missing or expired."""
        raise NotImplementedError("TODO milestone 4: Store.get")

    def set(self, key, value, ttl):
        self.data[key] = [value, self.sim.now + ttl]

    def incr(self, key, ttl, by=1):
        """Atomically add `by` and return the new value.

        If the key is missing or has expired it is created with value `by` and expires
        `ttl` seconds from now; an existing key keeps its original expiry (INCR then
        EXPIRE only when new).
        """
        raise NotImplementedError("TODO milestone 4: Store.incr")


def rpc(sim, net, store, op, callback, timeout):
    """Run op(store) at the store after one network delay; callback(result) after a second delay.

    If the store is down when the request arrives, nothing comes back and callback(None) is
    called after `timeout`. A reply that comes after the timeout is ignored (but the op has
    still run, exactly as in real life).
    """
    state = {"done": False}

    def finish(result):
        if not state["done"]:
            state["done"] = True
            callback(result)

    def arrive():
        if store.is_down():
            return
        result = op(store)
        sim.schedule(net.delay(), finish, result)

    sim.schedule(net.delay(), arrive)
    sim.schedule(timeout, finish, None)


# ------------------------------------------------------------------------------------
# Milestone 4 and 5: the global limiter
# ------------------------------------------------------------------------------------
class GlobalLimiter:
    """One per app node. Every request does one INCR on a shared counter for its window.

    on_error says what to do when the store does not answer: "open" (admit), "closed"
    (reject) or "local" (admit from a small local token bucket sized limit/nodes).
    time_source says which clock names the window: "local" (this node's, which may be
    skewed) or "store" (the store computes the window index, so every node agrees).
    """

    def __init__(self, sim, net, store, limit, window, nodes=1, skew=0.0, on_error="open",
                 timeout=0.05, time_source="local"):
        self.sim, self.net, self.store = sim, net, store
        self.limit, self.window, self.nodes = limit, window, nodes
        self.clock = SimClock(sim, skew)
        self.on_error, self.timeout, self.time_source = on_error, timeout, time_source
        rate = limit / window / nodes
        self.fallback = TokenBucket(rate, max(1.0, 0.25 * rate * window), SimClock(sim)) if on_error == "local" else None

    def make_op(self):
        """The operation to run at the store: INCR the counter of the current window.

        The TTL is two windows, not one. It starts when the key is first touched (a few ms into the
        window), so a one-window TTL would let the key expire while late requests for the same window
        are still in flight, or while a node with a slow clock still uses it, and the counter would
        silently restart from zero.
        """
        raise NotImplementedError("TODO milestone 4: GlobalLimiter.make_op")

    def request(self, done):
        """Decide one request; call done(allowed) when the decision is made."""
        raise NotImplementedError("TODO milestone 4: GlobalLimiter.request")

    def failed(self, done):
        """The store did not answer in time: apply the failure policy."""
        raise NotImplementedError("TODO milestone 5: GlobalLimiter.failed")


class RacyGlobalLimiter:
    """Given, for comparison: read the counter, then write back count + 1. NOT atomic."""

    def __init__(self, sim, net, store, limit, window, nodes=1, skew=0.0, timeout=0.05, **_):
        self.sim, self.net, self.store = sim, net, store
        self.limit, self.window, self.timeout = limit, window, timeout
        self.clock = SimClock(sim, skew)

    def request(self, done):
        key = f"rl:{math.floor(self.clock.now() / self.window)}"

        def after_get(count):
            if count is None:
                return done(True)
            if count >= self.limit:
                return done(False)
            rpc(self.sim, self.net, self.store, lambda st: st.set(key, count + 1, self.window),
                lambda _r: None, self.timeout)
            done(True)
        rpc(self.sim, self.net, self.store, lambda st: st.get(key), after_get, self.timeout)


class LocalSyncNode:
    """A node that decides locally and syncs with the store every `sync_interval` seconds.

    It knows `known` (the global count for this window as of its last sync, including its own
    requests up to then) and `unsynced` (what it admitted since). Modes:
      "optimistic"   admit while known + unsynced < limit
      "conservative" admit while unsynced < (limit - known) / nodes, a fair share of what is left
    """

    def __init__(self, sim, net, store, limit, window, nodes, sync_interval, node_id=0,
                 mode="optimistic", skew=0.0, timeout=0.05, phase=0.0):
        self.sim, self.net, self.store = sim, net, store
        self.limit, self.window, self.nodes = limit, window, nodes
        self.sync_interval, self.node_id, self.mode, self.timeout = sync_interval, node_id, mode, timeout
        self.clock = SimClock(sim, skew)
        self.phase = phase
        self.widx = None
        self.known = 0
        self.unsynced = 0

    def _roll(self):
        idx = math.floor(self.clock.now() / self.window)
        if idx != self.widx:
            self.widx, self.known, self.unsynced = idx, 0, 0

    def allow(self):
        """Decide one request from local state only (no network)."""
        raise NotImplementedError("TODO milestone 5: LocalSyncNode.allow")

    def sync(self):
        """Send our unsynced count to the store and learn the global count."""
        raise NotImplementedError("TODO milestone 5: LocalSyncNode.sync")

    def start(self):
        """Begin periodic syncing (given)."""
        def tick():
            self.sync()
            self.sim.schedule(self.sync_interval, tick)
        self.sim.schedule(self.phase, tick)


# ------------------------------------------------------------------------------------
# Experiment harnesses (given)
# ------------------------------------------------------------------------------------
Decision = namedtuple("Decision", "t_arrive t_decide node allowed")


def _arrivals(rng, rate, duration, nodes, weights):
    out, t = [], rng.expovariate(rate)
    ids = list(range(nodes))
    while t < duration:
        out.append((t, rng.choices(ids, weights)[0] if weights else rng.randrange(nodes)))
        t += rng.expovariate(rate)
    return out


def run_global(seed, nodes=4, limit=100, window=1.0, rate=400.0, duration=20.0, delay=(0.001, 0.005),
               limiter="atomic", on_error="open", time_source="local", skews=None, outage=None,
               weights=None, timeout=0.05):
    """Several app nodes, each calling a shared store (atomic INCR) for every request."""
    sim = Sim()
    net = Network(random.Random(seed * 3 + 1), *delay)
    store = Store(sim, down=[outage] if outage else [])
    skews = skews or [0.0] * nodes
    if limiter == "racy":
        lims = [RacyGlobalLimiter(sim, net, store, limit, window, nodes, skews[i], timeout) for i in range(nodes)]
    else:
        lims = [GlobalLimiter(sim, net, store, limit, window, nodes, skews[i], on_error, timeout, time_source)
                for i in range(nodes)]
    log = []

    def arrive(i):
        t0 = sim.now
        lims[i].request(lambda ok: log.append(Decision(t0, sim.now, i, ok)))

    for t, i in _arrivals(random.Random(seed * 3 + 2), rate, duration, nodes, weights):
        sim.schedule(t, arrive, i)
    sim.run(until=duration + 1.0)
    return sorted(log)


def run_local(seed, nodes=8, limit=100, window=1.0, rate=400.0, duration=20.0, sync_interval=0.1,
              mode="optimistic", weights=None, delay=(0.001, 0.005), skews=None, outage=None, timeout=0.05):
    """Several nodes that decide locally and sync with the store periodically."""
    sim = Sim()
    rng = random.Random(seed * 3 + 1)
    net = Network(rng, *delay)
    store = Store(sim, down=[outage] if outage else [])
    skews = skews or [0.0] * nodes
    ns = [LocalSyncNode(sim, net, store, limit, window, nodes, sync_interval, i, mode, skews[i], timeout,
                        phase=rng.uniform(0, sync_interval)) for i in range(nodes)]
    for n in ns:
        n.start()
    log = []

    def arrive(i):
        log.append(Decision(sim.now, sim.now, i, ns[i].allow()))

    for t, i in _arrivals(random.Random(seed * 3 + 2), rate, duration, nodes, weights):
        sim.schedule(t, arrive, i)
    sim.run(until=duration + 1.0)
    return sorted(log)


def admitted_times(log, by="decide"):
    """Times of the admitted requests: when the decision was made (default) or when the request arrived."""
    return sorted((d.t_decide if by == "decide" else d.t_arrive) for d in log if d.allowed)


def window_counts(times, window, duration):
    """Admitted requests per aligned window of true time, for windows 0 .. duration/window - 1."""
    n = int(round(duration / window))
    counts = [0] * n
    for t in times:
        k = int(t // window)
        if 0 <= k < n:
            counts[k] += 1
    return counts


def over_admission(times, limit, window, duration, skip=1):
    """Mean of (admitted / limit - 1) over the full windows, skipping `skip` at each end.

    0.0 means exactly at the limit; 1.0 means twice the limit; negative means under-admitting.
    """
    c = window_counts(times, window, duration)[skip:-skip or None]
    return sum(c) / len(c) / limit - 1.0


def peak_over_limit(times, limit, window):
    """The most admitted in ANY sliding window of length `window`, as a multiple of the limit."""
    return max_in_window(times, window) / limit
