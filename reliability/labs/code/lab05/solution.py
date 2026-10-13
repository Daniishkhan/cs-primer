"""Lab 5: Adaptive concurrency and load shedding.

One process, simulated time, seeded randomness: no sleeping, no sockets, no threads.
The simulated world is one service and its clients:

    clients --(attempt)--> [ queue ] --> [ worker pool: `workers` x exponential service ] --> response
        ^   timeout after `timeout` s: the client gives up and may retry, but the
        |   server does not know that and still does the work (this is the trap)
        +-- retries (up to `max_retries`, after a short backoff)

Vocabulary is chapters 8 and 11 of this course:

    goodput      responses that reached a client in time (not the same as throughput)
    metastable   a failure that persists after the trigger is gone, sustained by
                 retries and by work done for requests nobody is waiting for
    shedding     refusing or dropping work on purpose so the rest can succeed
    AIMD         additive increase, multiplicative decrease (a concurrency limit)

What is GIVEN: the event loop (`simulate`), the config, the request type, the metrics.
What YOU write is marked TODO:

    1  FifoQueue, Server.submit/dispatch/finish, Client.should_retry
    2  goodput, wasted_share, is_metastable
    3  ShedQueue: drop requests whose deadline has passed, and LIFO under overload
    4  AIMDLimiter: an adaptive concurrency limit
    5  RetryBudget and ClientThrottle

`python3 check.py` runs the milestones; the lab page explains each one.
"""
import heapq
import math
import random
from collections import deque
from dataclasses import dataclass, field
from typing import List, Optional

ARRIVE, DONE, TIMEOUT, CAPACITY = 0, 1, 2, 3     # event kinds


# =============================================================================
# GIVEN: configuration, requests, results
# =============================================================================
@dataclass
class Config:
    base_rate: float = 70.0        # new requests per second (the "normal" load)
    workers: int = 10              # concurrent requests the service can work on
    service_mean: float = 0.1      # seconds per request, exponential => capacity 100/s
    service_fixed: bool = False    # True: every request takes exactly service_mean
    timeout: float = 1.0           # client gives up this long after sending
    max_retries: int = 3           # retries after the first attempt
    retry_backoff: float = 0.05    # seconds before a retry is sent
    queue_limit: int = 2000        # waiting room size (requests beyond it are rejected)
    duration: float = 140.0
    trigger: str = "dip"           # "none" | "dip" (fewer workers) | "spike" (more load)
    trigger_start: float = 20.0
    trigger_end: float = 30.0
    dip_workers: int = 4           # workers left during a dip  => 40/s
    spike_factor: float = 3.0      # load multiplier during a spike

    @property
    def capacity(self) -> float:
        return self.workers / self.service_mean


class Orig:
    """One logical request from a user: it may be sent several times (attempts)."""
    __slots__ = ("oid", "t0", "tries", "done")

    def __init__(self, oid, t0):
        self.oid, self.t0, self.tries, self.done = oid, t0, 0, False


class Req:
    """One attempt sent to the server."""
    __slots__ = ("orig", "sent", "deadline", "enq", "started", "state", "abandoned")

    def __init__(self, orig):
        self.orig = orig
        self.sent = self.deadline = self.enq = self.started = 0.0
        self.state = "new"          # new | queued | running | ok | rejected | dropped
        self.abandoned = False      # the client has given up (the server does not know)


class Result:
    def __init__(self, cfg):
        n = int(cfg.duration) + 2
        self.cfg = cfg
        self.succ = [0] * n          # successful responses per second (goodput)
        self.attempts = [0] * n      # attempts that reached the server per second
        self.wasted = [0] * n        # completed jobs whose client had already given up
        self.rejected = [0] * n      # attempts refused or dropped by the server
        self.qlen = [0] * n          # queue length sampled once per second
        self.limit = [0.0] * n       # concurrency limit sampled once per second (0 = none)
        self.n_orig = 0
        self.ok = 0                  # original requests that eventually succeeded
        self.failed = 0              # original requests that gave up
        self.latencies: List[float] = []
        self.sojourn_sum = 0.0       # time in the server (queue + service) of finished attempts
        self.sojourn_n = 0
        self.area = 0.0              # integral of (queued + running) dt
        self.max_busy = 0
        self.max_queue = 0
        self.workers_seen = []


# =============================================================================
# 1. The server and the client
# =============================================================================
class FifoQueue:
    """The waiting room, first in first out. `pop` returns (request, dropped_list)."""

    def __init__(self):
        self.q = deque()

    def __len__(self):
        return len(self.q)

    def push(self, req, now):
        self.q.append(req)

    def pop(self, now):
        """Return (the oldest request, []) or (None, []) when empty."""
        if not self.q:
            return None, []
        return self.q.popleft(), []


class Server:
    """A pool of `workers` that take requests from `queue`.

    The simulator calls submit() when an attempt arrives, dispatch() whenever a
    worker might be free, and finish() when a job completes. Use `self.schedule(t,
    DONE, req)` to say when a job will finish.
    """

    def __init__(self, cfg, queue, limiter, schedule, rng):
        self.cfg, self.queue, self.limiter = cfg, queue, limiter
        self.schedule, self.rng = schedule, rng
        self.workers = cfg.workers      # current number of workers (the simulator changes it)
        self.busy = 0                   # jobs being worked on right now

    @property
    def inflight(self):
        """Requests in the server: queued plus running."""
        return len(self.queue) + self.busy

    def service_time(self):
        if self.cfg.service_fixed:
            return self.cfg.service_mean
        return self.rng.expovariate(1.0 / self.cfg.service_mean)

    def submit(self, req, now):
        """Accept the attempt into the queue and return True, or refuse it (False).
        Refuse when the waiting room is full (`len(queue) >= cfg.queue_limit`) or,
        if there is a limiter, when `limiter.try_acquire(self.inflight)` says no
        (milestone 4: tell the limiter about the refusal with `limiter.on_drop(now)`).
        Set req.enq and req.state = "queued" when accepted."""
        if len(self.queue) >= self.cfg.queue_limit:
            return False
        if self.limiter is not None and not self.limiter.try_acquire(self.inflight):
            self.limiter.on_drop(now)
            return False
        req.enq = now
        req.state = "queued"
        self.queue.push(req, now)
        return True

    def dispatch(self, now):
        """Start jobs while a worker is free and the queue has something to serve.
        `queue.pop(now)` returns (request or None, dropped): every request in
        `dropped` was thrown away by the queue (milestone 3): set its state to
        "dropped", tell the limiter if there is one, and append it to the returned
        list so the simulator can tell its client. Returns the list of dropped
        requests. For a started job: busy += 1, req.started = now, state "running",
        and schedule its DONE event."""
        dropped_all = []
        while self.busy < self.workers and len(self.queue) > 0:
            req, dropped = self.queue.pop(now)
            for d in dropped:
                d.state = "dropped"
                if self.limiter is not None:
                    self.limiter.on_drop(now)
            dropped_all.extend(dropped)
            if req is None:
                break
            self.busy += 1
            req.started = now
            req.state = "running"
            self.schedule(now + self.service_time(), DONE, req)
        return dropped_all

    def finish(self, req, now):
        """A job completed: free its worker. Return True if the client was still
        waiting (`not req.abandoned`: the response is useful), False if the client
        had already given up (the work was wasted). Feed the limiter (milestone 4):
        `limiter.on_sample(queue_wait, now)`, where queue_wait is how long the job
        waited before it started: `req.started - req.enq`."""
        self.busy -= 1
        useful = not req.abandoned
        if self.limiter is not None:
            self.limiter.on_sample(req.started - req.enq, now)
        return useful


class Client:
    """The retry policy of the users' side. `should_retry` is asked after every
    failed attempt (timeout, rejection or drop)."""

    def __init__(self, cfg, budget=None, throttle=None):
        self.cfg, self.budget, self.throttle = cfg, budget, throttle

    def should_retry(self, orig, now):
        """True if this request may be sent again: it has used fewer than
        `max_retries` retries so far (`orig.tries` counts attempts sent, including
        the first), and, if there is a retry budget (milestone 5), the budget agrees
        (`budget.try_retry()`; ask it last, it spends a token)."""
        if orig.tries > self.cfg.max_retries:
            return False
        if self.budget is not None and not self.budget.try_retry():
            return False
        return True

    def may_send(self, now, rng):
        """Client-side throttle (milestone 5): False means 'do not even send'."""
        return self.throttle is None or self.throttle.allow(now, rng)


# =============================================================================
# 2. Measuring metastability
# =============================================================================
def goodput(res, t0, t1):
    """Mean successful responses per second over the seconds [t0, t1)."""
    lo, hi = int(t0), int(t1)
    return sum(res.succ[lo:hi]) / max(1, hi - lo)


def wasted_share(res, t0, t1):
    """Of the jobs the workers completed in [t0, t1), the fraction whose client had
    already given up (res.wasted counts those; res.succ counts the useful ones)."""
    lo, hi = int(t0), int(t1)
    w, s = sum(res.wasted[lo:hi]), sum(res.succ[lo:hi])
    return w / (w + s) if (w + s) else 0.0


def is_metastable(res, margin=30.0):
    """True if the system was healthy before the trigger but is still failing
    `margin` seconds after the trigger ended, with the offered load back to normal.
    Healthy: goodput >= 90% of cfg.base_rate. Failing: goodput < 50% of it."""
    c = res.cfg
    before = goodput(res, 5, c.trigger_start)
    after = goodput(res, c.trigger_end + margin, c.duration)
    return before >= 0.9 * c.base_rate and after < 0.5 * c.base_rate


# =============================================================================
# 3. Deadline-aware shedding and LIFO under overload
# =============================================================================
class ShedQueue:
    """A queue that refuses to do useless work.

    expire:     drop requests that cannot finish in time: at pop time,
                `now + min_useful > req.deadline` (the client will have left)
    lifo_over:  if the queue is longer than this, serve the NEWEST request first
                (it has the most time left); None means always FIFO
    codel_target: (stretch) CoDel-ish: if the time in queue has stayed above
                this many seconds for `codel_interval` seconds, drop from the head
    `pop` returns (request or None, dropped_list). Expired requests at the head
    of the queue (the oldest) should also be purged when a new request is pushed,
    so dead requests never fill the waiting room.
    """

    def __init__(self, expire=True, lifo_over=None, min_useful=0.0, codel_target=None, codel_interval=0.5):
        self.q = deque()
        self.expire, self.lifo_over, self.min_useful = expire, lifo_over, min_useful
        self.codel_target, self.codel_interval = codel_target, codel_interval
        self.above_since = None
        self.purged = []            # dead requests removed by push(); the server reports them

    def __len__(self):
        return len(self.q)

    def push(self, req, now):
        if self.expire:
            while self.q and now + self.min_useful > self.q[0].deadline:
                dead = self.q.popleft()
                self.purged.append(dead)
        self.q.append(req)

    def pop(self, now):
        dropped = self.purged
        self.purged = []
        while self.q:
            if self.lifo_over is not None and len(self.q) > self.lifo_over:
                req = self.q.pop()
            else:
                req = self.q.popleft()
            if self.expire and now + self.min_useful > req.deadline:
                dropped.append(req)
                continue
            if self.codel_target is not None:
                sojourn = now - req.enq
                if sojourn <= self.codel_target:
                    self.above_since = None
                else:
                    if self.above_since is None:
                        self.above_since = now
                    if now - self.above_since >= self.codel_interval:
                        dropped.append(req)
                        continue
            return req, dropped
        return None, dropped


# =============================================================================
# 4. An adaptive concurrency limit (AIMD)
# =============================================================================
class AIMDLimiter:
    """Limit how many requests are in the server (queued + running).

    Additive increase, multiplicative decrease, driven by queueing delay:
      - a request that waited <= `target` seconds before starting: limit += 1/limit
        (about +1 per `limit` good responses, i.e. roughly +1 per round trip)
      - a request that waited longer, or a drop: limit *= backoff, but at most once
        per `cooldown` seconds, because one burst makes many slow responses at once
    The limit stays within [min_limit, max_limit].
    """

    def __init__(self, initial=20.0, min_limit=2.0, max_limit=1000.0, target=0.05, backoff=0.9, cooldown=0.2):
        self.limit = float(initial)
        self.min_limit, self.max_limit = min_limit, max_limit
        self.target, self.backoff, self.cooldown = target, backoff, cooldown
        self.last_decrease = -1e9

    def try_acquire(self, inflight):
        """May one more request enter, given `inflight` requests already inside?"""
        return inflight < int(self.limit)

    def on_sample(self, queue_wait, now):
        """A request finished; it waited `queue_wait` seconds in the queue."""
        if queue_wait > self.target:
            self._decrease(now)
        else:
            self.limit = min(self.max_limit, self.limit + 1.0 / self.limit)

    def on_drop(self, now):
        """A request was refused or dropped: a congestion signal."""
        self._decrease(now)

    def _decrease(self, now):
        if now - self.last_decrease >= self.cooldown:
            self.limit = max(self.min_limit, self.limit * self.backoff)
            self.last_decrease = now


# =============================================================================
# 5. Retry budget and client-side throttle
# =============================================================================
class RetryBudget:
    """Retries may not exceed `ratio` of the original requests.

    A token bucket: every original request adds `ratio` tokens (at most
    `max_tokens`), every retry costs one. `try_retry` spends a token if there is one."""

    def __init__(self, ratio=0.1, max_tokens=10.0, initial=0.0):
        self.ratio, self.max_tokens = ratio, max_tokens
        self.tokens = initial
        self.requests = 0
        self.retries = 0

    def on_request(self):
        """An original (first-attempt) request was made."""
        self.requests += 1
        self.tokens = min(self.max_tokens, self.tokens + self.ratio)

    def try_retry(self):
        """True (and spend one token) if a retry is allowed right now."""
        if self.tokens >= 1.0 - 1e-9:        # 10 additions of 0.1 sum to 0.9999999999999999
            self.tokens -= 1.0
            self.retries += 1
            return True
        return False


class ClientThrottle:
    """Adaptive client-side throttling (the Google SRE book's formula).

    Over the last `window` seconds the client counts `requests` (every attempt it
    wanted to send, including ones it throttled itself) and `accepts` (attempts
    that got a useful response). It then rejects locally, without sending, with
    probability   max(0, (requests - k * accepts) / (requests + 1)).
    With k = 2 a client whose backend answers at least half its requests never throttles.
    (The SRE book keeps two minutes of history; this lab's incidents last seconds, so
    the default window is 5 s. A long window remembers the failure long after it ends.)
    """

    def __init__(self, k=2.0, window=5.0):
        self.k, self.window = k, window
        self.events = deque()        # (time, requested 1, accepted 0 or 1)
        self.requests = 0
        self.accepts = 0

    def _expire(self, now):
        while self.events and self.events[0][0] < now - self.window:
            _, r, a = self.events.popleft()
            self.requests -= r
            self.accepts -= a

    def record(self, now, accepted):
        """One attempt's outcome: accepted True if it got a useful response."""
        self._expire(now)
        self.events.append((now, 1, 1 if accepted else 0))
        self.requests += 1
        self.accepts += 1 if accepted else 0

    def reject_probability(self, now):
        self._expire(now)
        return max(0.0, (self.requests - self.k * self.accepts) / (self.requests + 1.0))

    def allow(self, now, rng):
        """Should this attempt be sent? Throttled attempts count as requests that
        were not accepted (call record(now, False) for them)."""
        if rng.random() < self.reject_probability(now):
            self.record(now, False)
            return False
        return True


def recovery_time(res, frac=0.8, hold=5):
    """GIVEN. Seconds after the trigger ended until goodput (averaged over `hold`
    seconds) is back to `frac` of the normal load; None if it never is."""
    c = res.cfg
    start = int(c.trigger_end)
    for t in range(start, int(c.duration) - hold + 1):
        if goodput(res, t, t + hold) >= frac * c.base_rate:
            return t - start
    return None


# =============================================================================
# GIVEN: protections bundle and the event loop
# =============================================================================
@dataclass
class Protections:
    shed_expired: bool = False
    lifo_over: Optional[int] = None
    codel_target: Optional[float] = None
    limiter: bool = False
    retry_budget: Optional[float] = None      # e.g. 0.1 = 10%
    throttle: bool = False

    @staticmethod
    def none():
        return Protections()

    @staticmethod
    def shedding():
        return Protections(shed_expired=True, lifo_over=20)

    @staticmethod
    def server_side():
        return Protections(shed_expired=True, lifo_over=20, limiter=True)

    @staticmethod
    def client_side():
        return Protections(retry_budget=0.1, throttle=True)

    @staticmethod
    def full():
        return Protections(shed_expired=True, lifo_over=20, limiter=True, retry_budget=0.1, throttle=True)


def poisson_arrivals(cfg, rng, rate_fn_pieces):
    """Arrival times of new requests: a Poisson process whose rate changes at the
    given breakpoints. rate_fn_pieces: list of (start, end, rate)."""
    out = []
    for lo, hi, rate in rate_fn_pieces:
        if rate <= 0:
            continue
        t = lo
        while True:
            t += rng.expovariate(rate)
            if t >= hi:
                break
            out.append(t)
    return out


def simulate(cfg: Config, prot: Protections, seed: int, arrivals: Optional[List[float]] = None) -> Result:
    """Run one scenario and return a Result. Three independent random streams
    (arrivals, service times, client coins) so that turning a protection on does not
    change the arrivals: the comparison is fair, request for request."""
    rng_a = random.Random(seed * 1000003 + 1)
    rng_s = random.Random(seed * 1000003 + 2)
    rng_c = random.Random(seed * 1000003 + 3)
    res = Result(cfg)
    events = []
    counter = [0]

    def schedule(t, kind, obj):
        counter[0] += 1
        heapq.heappush(events, (t, counter[0], kind, obj))

    if arrivals is None:
        r, ts, te = cfg.base_rate, cfg.trigger_start, cfg.trigger_end
        if cfg.trigger == "spike":
            pieces = [(0, ts, r), (ts, te, r * cfg.spike_factor), (te, cfg.duration, r)]
        else:
            pieces = [(0, cfg.duration, r)]
        arrivals = poisson_arrivals(cfg, rng_a, pieces)

    if prot.shed_expired or prot.lifo_over is not None or prot.codel_target is not None:
        queue = ShedQueue(expire=prot.shed_expired, lifo_over=prot.lifo_over,
                          min_useful=cfg.service_mean, codel_target=prot.codel_target)
    else:
        queue = FifoQueue()
    limiter = AIMDLimiter() if prot.limiter else None
    budget = RetryBudget(prot.retry_budget) if prot.retry_budget else None
    throttle = ClientThrottle() if prot.throttle else None
    server = Server(cfg, queue, limiter, schedule, rng_s)
    client = Client(cfg, budget, throttle)

    for i, t in enumerate(arrivals):
        schedule(t, ARRIVE, Orig(i, t))
    res.n_orig = len(arrivals)
    if cfg.trigger == "dip":
        schedule(cfg.trigger_start, CAPACITY, cfg.dip_workers)
        schedule(cfg.trigger_end, CAPACITY, cfg.workers)
    # one sample per second of the queue length and the limit
    for s in range(int(cfg.duration) + 1):
        schedule(float(s) + 0.5, CAPACITY, -1)

    def sec(t):
        return min(int(t), len(res.succ) - 1)

    last_t = [0.0]

    def account(now):
        res.area += server.inflight * (now - last_t[0])
        last_t[0] = now

    def failed_attempt(req, now):
        """The attempt failed (timeout, rejection or drop): retry or give up."""
        orig = req.orig
        if orig.done or (req.abandoned and req.state in ("rejected", "dropped")):
            return
        if client.should_retry(orig, now):
            schedule(now + cfg.retry_backoff * (0.5 + rng_c.random()), ARRIVE, orig)
        else:
            orig.done = True
            res.failed += 1

    while events:
        now, _, kind, obj = heapq.heappop(events)
        if now > cfg.duration:
            break
        account(now)
        if kind == ARRIVE:
            orig = obj
            if orig.done:
                continue
            if orig.tries == 0 and budget is not None:
                budget.on_request()
            req = Req(orig)
            req.sent, req.deadline = now, now + cfg.timeout
            if not client.may_send(now, rng_c):
                req.state = "rejected"
                orig.tries += 1
                failed_attempt(req, now)
                continue
            orig.tries += 1
            res.attempts[sec(now)] += 1
            schedule(req.deadline, TIMEOUT, req)
            if server.submit(req, now):
                for d in server.dispatch(now):
                    res.rejected[sec(now)] += 1
                    if throttle is not None:
                        throttle.record(now, False)
                    failed_attempt(d, now + 0.001)
            else:
                req.state = "rejected"
                res.rejected[sec(now)] += 1
                if throttle is not None:
                    throttle.record(now, False)
                failed_attempt(req, now + 0.001)
        elif kind == DONE:
            req = obj
            useful = server.finish(req, now)
            res.sojourn_sum += now - req.enq
            res.sojourn_n += 1
            if useful:
                req.state = "ok"
                res.succ[sec(now)] += 1
                res.latencies.append(now - req.sent)
                if throttle is not None:
                    throttle.record(now, True)
                if not req.orig.done:
                    req.orig.done = True
                    res.ok += 1
            else:
                res.wasted[sec(now)] += 1
            for d in server.dispatch(now):
                res.rejected[sec(now)] += 1
                if throttle is not None:
                    throttle.record(now, False)
                failed_attempt(d, now + 0.001)
        elif kind == TIMEOUT:
            req = obj
            if req.state in ("queued", "running") and not req.abandoned:
                req.abandoned = True            # the server is not told: it keeps the request
                if throttle is not None:
                    throttle.record(now, False)
                failed_attempt(req, now)
        elif kind == CAPACITY:
            if obj >= 0:
                server.workers = obj
                for d in server.dispatch(now):
                    res.rejected[sec(now)] += 1
                    failed_attempt(d, now + 0.001)
            else:
                s = sec(now)
                res.qlen[s] = len(queue)
                res.limit[s] = limiter.limit if limiter else 0.0
        res.max_busy = max(res.max_busy, server.busy)
        res.max_queue = max(res.max_queue, len(queue))
    return res
