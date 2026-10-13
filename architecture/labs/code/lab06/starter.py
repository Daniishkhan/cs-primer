"""Lab 6 starter: a resilience toolkit, tested in simulated time.

There are no real sleeps and no network. A FakeClock is the only source of time: calling
clock.sleep(d) just moves the clock forward by d, instantly. A FlakyDependency "takes"
simulated time and fails on a script. So an outage of a minute runs in a few milliseconds
and every run is identical.

Fill in every TODO, one milestone at a time, and run `python3 check.py` after each one.
The lab page walks you through it.

The layers, outermost first:   retry -> bulkhead -> circuit breaker -> timeout -> the call
"""
import random
import threading
from collections import deque
from contextlib import contextmanager


# ======================================================================================
# Errors (given)
# ======================================================================================
class DependencyError(Exception):
    """The dependency answered with an error. `retryable` says whether trying again can help."""
    retryable = True


class TransientError(DependencyError):
    """Like an HTTP 503: may clear on its own."""
    retryable = True


class PermanentError(DependencyError):
    """Like an HTTP 400: asking again gives the same answer."""
    retryable = False


class RejectedError(Exception):
    """We refused to make the call at all (nothing reached the dependency). Never retried."""


class CircuitOpenError(RejectedError):
    pass


class BulkheadFullError(RejectedError):
    pass


def is_retryable(exc):
    """Timeouts and retryable dependency errors may succeed next time. Rejections and permanent errors never will. (Given.)"""
    if isinstance(exc, RejectedError):
        return False
    return isinstance(exc, TimeoutError) or (isinstance(exc, DependencyError) and exc.retryable)


# ======================================================================================
# Milestone 1: the fake clock with deadlines, and the timeout wrapper
# ======================================================================================
class FakeClock:
    """Simulated time. now() reads it, sleep(d) advances it, and deadline(t) makes any sleep
    that would cross the deadline stop AT the deadline and raise TimeoutError."""

    def __init__(self, start=0.0):
        self._now = start
        self._deadlines = []                    # stack of absolute deadlines; the last one is the tightest
        self.sleeps = []                        # every duration passed to sleep(), for the checks

    def now(self):
        return self._now

    def sleep(self, d):
        """Advance the clock by d seconds, instantly.
        TODO milestone 1: if a deadline is active (self._deadlines[-1]) and now + d would pass it,
        advance the clock only TO the deadline and raise TimeoutError. The time up to the deadline
        really did pass: the caller waited that long before giving up."""
        if d < 0:
            raise ValueError("cannot sleep a negative time")
        self.sleeps.append(d)
        self._now += d                          # <- no deadline handling yet

    @contextmanager
    def deadline(self, timeout):
        """Everything inside the `with` block must finish within `timeout` simulated seconds.
        TODO milestone 1: limit = now + timeout, but never later than an enclosing deadline
        (nested deadlines can only tighten). Push it on self._deadlines, yield, and pop it in a
        `finally` so an exception cannot leave a stale deadline behind."""
        raise NotImplementedError("TODO milestone 1: FakeClock.deadline")
        yield


def with_timeout(clock, fn, timeout):
    """Call fn(); if it would take more than `timeout` simulated seconds, raise TimeoutError
    at start + timeout (the caller stops waiting, even though the work goes on elsewhere)."""
    raise NotImplementedError("TODO milestone 1: with_timeout")


# ======================================================================================
# The fake dependency (given)
# ======================================================================================
class Phase:
    """From simulated time `start` on, each call takes `latency` seconds and ends in `error`
    (None = success, "transient" = 503, "permanent" = 400)."""

    def __init__(self, start, latency=0.05, error=None):
        self.start, self.latency, self.error = start, latency, error


class FlakyDependency:
    """A scripted dependency. phases: list of Phase. If `capacity` is set the dependency also
    sheds load: more than `capacity` calls arriving within `capacity_window` seconds make it
    answer 503 even when its script says it is healthy. That is how retry storms keep a
    recovering service down."""

    def __init__(self, clock, phases, capacity=None, capacity_window=5.0):
        self.clock = clock
        self.phases = sorted(phases, key=lambda p: p.start)
        self.capacity, self.capacity_window = capacity, capacity_window
        self.arrivals = []                      # time of every call that reached us, even ones the caller gave up on

    @property
    def calls(self):
        return len(self.arrivals)

    def phase_at(self, t):
        current = self.phases[0]
        for p in self.phases:
            if p.start <= t:
                current = p
        return current

    def call(self):
        now = self.clock.now()
        self.arrivals.append(now)
        phase = self.phase_at(now)
        error = phase.error
        if self.capacity is not None:
            recent = sum(1 for t in self.arrivals if t > now - self.capacity_window)
            if recent > self.capacity:
                error = "transient"
        self.clock.sleep(phase.latency)         # may raise TimeoutError if the caller's deadline hits first
        if error == "transient":
            raise TransientError("503 from dependency")
        if error == "permanent":
            raise PermanentError("400 from dependency")
        return "ok"


# ======================================================================================
# Milestone 2: retries with exponential backoff, full jitter and a budget
# ======================================================================================
class RetryPolicy:
    def __init__(self, max_attempts=4, base=0.1, cap=2.0):
        self.max_attempts, self.base, self.cap = max_attempts, base, cap


def backoff_delay(retry_number, policy, rng):
    """Full jitter: a random time between 0 and min(cap, base * 2**retry_number), drawn with
    rng.uniform. retry_number is 0 for the first retry."""
    raise NotImplementedError("TODO milestone 2: backoff_delay")


class RetryBudget:
    """Retries may be at most `ratio` of the calls made in the last `window` seconds
    (but always at least `min_retries`, so a quiet service can still retry a little)."""

    def __init__(self, clock, window=10.0, ratio=0.1, min_retries=0):
        self.clock, self.window, self.ratio, self.min_retries = clock, window, ratio, min_retries
        self._calls = deque()                   # timestamps of first attempts
        self._retries = deque()                 # timestamps of retries

    def _prune(self):
        """Forget anything older than the window. (Given.)"""
        cutoff = self.clock.now() - self.window
        for q in (self._calls, self._retries):
            while q and q[0] <= cutoff:
                q.popleft()

    def record_call(self):
        """A new logical call (first attempt) is starting: prune, then remember its timestamp."""
        raise NotImplementedError("TODO milestone 2: RetryBudget.record_call")

    def record_retry(self):
        """A retry is being made: remember its timestamp."""
        raise NotImplementedError("TODO milestone 2: RetryBudget.record_retry")

    def can_retry(self):
        """Prune, then: is (retries so far + 1) <= max(min_retries, ratio * calls)?
        Add a tiny epsilon (1e-9) to the right side to be safe with floating point."""
        raise NotImplementedError("TODO milestone 2: RetryBudget.can_retry")


def retry(clock, rng, fn, policy, budget=None, retryable=is_retryable):
    """Call fn() up to policy.max_attempts times, sleeping a jittered backoff on the fake clock between
    attempts. Re-raise the last error when: the error is not retryable(exc), attempts are used up, or
    the budget says no. Steps:
    1. if there is a budget: budget.record_call();
    2. loop: try fn(); on Exception count the attempt, decide whether to give up (see above), else
       budget.record_retry(), clock.sleep(backoff_delay(attempt - 1, policy, rng)) and go round again."""
    raise NotImplementedError("TODO milestone 2: retry")


# ======================================================================================
# Milestone 3: the circuit breaker
# ======================================================================================
class CircuitBreaker:
    """closed -> open when, within the last `window` seconds, at least `min_calls` calls were
    recorded and at least `failure_rate` of them failed.
    open -> half-open once `open_duration` seconds have passed.
    half-open lets `half_open_max` probe calls through: all succeed -> closed, any fails -> open again."""

    def __init__(self, clock, window=5.0, min_calls=5, failure_rate=0.5, open_duration=5.0, half_open_max=2):
        self.clock = clock
        self.window, self.min_calls, self.failure_rate = window, min_calls, failure_rate
        self.open_duration, self.half_open_max = open_duration, half_open_max
        self._state = "closed"
        self.opened_at = None
        self.events = deque()                   # (time, ok) of recent calls while closed
        self.probes_admitted = 0
        self.probe_successes = 0
        self.short_circuited = 0                # calls refused without touching the dependency
        self.transitions = []                   # (time, old_state, new_state), for the checks

    def _transition(self, new, at=None):
        """Change state and log (time, old, new). Sets opened_at when opening, resets the probe counters
        when going half-open, clears the window when closing. (Given.)"""
        at = self.clock.now() if at is None else at
        self.transitions.append((at, self._state, new))
        self._state = new
        if new == "open":
            self.opened_at = at
        elif new == "half-open":
            self.probes_admitted = 0
            self.probe_successes = 0
        elif new == "closed":
            self.events.clear()

    @property
    def state(self):
        """"closed", "open" or "half-open". Time passing is what moves open -> half-open, and nobody
        calls us at that moment, so work it out lazily here: if we are open and
        now >= opened_at + open_duration, call self._transition("half-open", at=opened_at + open_duration)
        (log the moment it LOGICALLY happened, not the moment somebody noticed). Then return self._state."""
        raise NotImplementedError("TODO milestone 3: CircuitBreaker.state")

    def window_counts(self):
        """(calls, failures) recorded in the rolling window. (Given.)"""
        cutoff = self.clock.now() - self.window
        while self.events and self.events[0][0] <= cutoff:
            self.events.popleft()
        return len(self.events), sum(1 for _, ok in self.events if not ok)

    def before_call(self):
        """Ask permission. Raise CircuitOpenError (and count self.short_circuited += 1) when the circuit
        is open, or half-open with probes_admitted already == half_open_max. In half-open, an admitted call
        is a probe: probes_admitted += 1."""
        raise NotImplementedError("TODO milestone 3: CircuitBreaker.before_call")

    def on_success(self):
        """half-open: count the probe success; when half_open_max have succeeded, close.
        closed: append (now, True) to self.events."""
        raise NotImplementedError("TODO milestone 3: CircuitBreaker.on_success")

    def on_failure(self):
        """half-open: open again at once. closed: append (now, False), then use window_counts():
        if calls >= min_calls and failures / calls >= failure_rate, open."""
        raise NotImplementedError("TODO milestone 3: CircuitBreaker.on_failure")

    def call(self, fn):
        """before_call(); run fn(); report on_success / on_failure; return the result or re-raise.
        Only is_retryable(exc) errors count as failures: a 400 means the dependency is alive, so it counts as a success."""
        raise NotImplementedError("TODO milestone 3: CircuitBreaker.call")


# ======================================================================================
# Milestone 4: the bulkhead
# ======================================================================================
class Bulkhead:
    """At most `max_concurrent` calls in flight to one dependency. A full bulkhead rejects at once;
    it never queues, because a queue is just another place for a slow dependency to hold your threads."""

    def __init__(self, max_concurrent, name="dependency"):
        self.max_concurrent, self.name = max_concurrent, name
        self._lock = threading.Lock()           # real threads use this class too: guard the counters
        self.in_flight = 0
        self.max_seen = 0                       # the highest in_flight ever observed
        self.rejected = 0                       # how many acquires were refused

    def acquire(self):
        """Take a slot, or raise BulkheadFullError (and count it in self.rejected) if all are taken.
        Update max_seen. Do the check and the increment under self._lock."""
        raise NotImplementedError("TODO milestone 4: Bulkhead.acquire")

    def release(self):
        """Give a slot back. Raise RuntimeError if none is held."""
        raise NotImplementedError("TODO milestone 4: Bulkhead.release")

    def call(self, fn):
        """acquire(); run fn(); release() in a `finally`. If acquire() raises, fn must not run and
        release() must NOT be called."""
        raise NotImplementedError("TODO milestone 4: Bulkhead.call")


# ======================================================================================
# Milestone 5: put it together
# ======================================================================================
class Toolkit:
    def __init__(self, clock, rng, timeout=0.5, policy=None, budget=None, breaker=None, bulkhead=None):
        self.clock, self.rng, self.timeout = clock, rng, timeout
        self.policy = policy or RetryPolicy(max_attempts=3, base=0.1, cap=2.0)
        self.budget = budget or RetryBudget(clock, window=10.0, ratio=0.1, min_retries=2)
        self.breaker = breaker or CircuitBreaker(clock)
        self.bulkhead = bulkhead or Bulkhead(10)

    def call(self, fn):
        """Wrap fn in all four protections, outermost first: retry( bulkhead( breaker( timeout( fn )))).
        One attempt = bulkhead.call(lambda: breaker.call(lambda: with_timeout(clock, fn, timeout))).
        retry() runs attempts, with self.policy and self.budget. The page explains why this order."""
        raise NotImplementedError("TODO milestone 5: Toolkit.call")


def naive_call(clock, fn, attempts=5, timeout=0.5):
    """The baseline most code starts with: a timeout, and up to 5 immediate retries. (Given.)"""
    for i in range(attempts):
        try:
            return with_timeout(clock, fn, timeout)
        except Exception as exc:
            if i == attempts - 1 or not is_retryable(exc):
                raise


OUTAGE_START, OUTAGE_END, SCENARIO_LENGTH = 10.0, 40.0, 60.0


def run_scenario(kind, seed=1):
    """One request every 0.5 s for 60 simulated seconds. The dependency fails with 503 from t=10 to
    t=40 and can only serve 25 calls per 5 seconds. kind is "naive" or "toolkit". (Given.)
    Returns a dict of numbers."""
    clock = FakeClock()
    dep = FlakyDependency(clock, [Phase(0, 0.05), Phase(OUTAGE_START, 0.05, "transient"), Phase(OUTAGE_END, 0.05)],
                          capacity=25, capacity_window=5.0)
    rng = random.Random(seed)
    toolkit = Toolkit(clock, rng) if kind == "toolkit" else None
    ok = failed = rejected = 0
    first_ok_after_outage = None
    for i in range(int(SCENARIO_LENGTH / 0.5)):
        clock.sleep(max(0.0, i * 0.5 - clock.now()))        # wait for this request's arrival time
        try:
            toolkit.call(dep.call) if toolkit else naive_call(clock, dep.call)
            ok += 1
            if clock.now() >= OUTAGE_END and first_ok_after_outage is None:
                first_ok_after_outage = clock.now()
        except RejectedError:
            rejected += 1
        except NotImplementedError:
            raise
        except Exception:
            failed += 1
    return {"calls_to_dependency": dep.calls, "ok": ok, "failed": failed, "rejected": rejected,
            "recovery_seconds": None if first_ok_after_outage is None else first_ok_after_outage - OUTAGE_END,
            "toolkit": toolkit}
