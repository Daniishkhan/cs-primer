"""Lab 6 solution: a resilience toolkit, tested in simulated time.

There are no real sleeps and no network. A FakeClock is the only source of time: calling
clock.sleep(d) just moves the clock forward by d, instantly. A FlakyDependency "takes"
simulated time and fails on a script. So an outage of a minute runs in a few milliseconds
and every run is identical.

The layers, outermost first:   retry -> bulkhead -> circuit breaker -> timeout -> the call
"""
import random
import threading
from collections import deque
from contextlib import contextmanager


# ======================================================================================
# Errors
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
    """Timeouts and retryable dependency errors may succeed next time. Rejections and permanent errors never will."""
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
        if d < 0:
            raise ValueError("cannot sleep a negative time")
        self.sleeps.append(d)
        limit = self._deadlines[-1] if self._deadlines else None
        if limit is not None and self._now + d > limit + 1e-9:
            self._now = max(self._now, limit)       # the time up to the deadline really passed
            raise TimeoutError("deadline exceeded at t=%.3f" % self._now)
        self._now += d

    @contextmanager
    def deadline(self, timeout):
        """Everything inside the `with` block must finish within `timeout` simulated seconds.
        Nested deadlines can only tighten: the inner limit is the smaller of the two."""
        limit = self._now + timeout
        if self._deadlines:
            limit = min(limit, self._deadlines[-1])
        self._deadlines.append(limit)
        try:
            yield
        finally:
            self._deadlines.pop()


def with_timeout(clock, fn, timeout):
    """Call fn(); if it would take more than `timeout` simulated seconds, raise TimeoutError
    at start + timeout (not later: the caller stops waiting, even though the work goes on)."""
    with clock.deadline(timeout):
        return fn()


# ======================================================================================
# The fake dependency (given in the starter too)
# ======================================================================================
class Phase:
    """From simulated time `start` on, each call takes `latency` seconds and ends in `error`
    (None = success, "transient" = 503, "permanent" = 400)."""

    def __init__(self, start, latency=0.05, error=None):
        self.start, self.latency, self.error = start, latency, error


class FlakyDependency:
    """A scripted dependency. phases: list of Phase sorted by start. If `capacity` is set the
    dependency also sheds load: more than `capacity` calls arriving within `capacity_window`
    seconds make it answer 503 even when its script says it is healthy. That is how
    retry storms keep a recovering service down."""

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
    """Full jitter: a random time between 0 and min(cap, base * 2**retry_number).
    retry_number is 0 for the first retry."""
    return rng.uniform(0, min(policy.cap, policy.base * 2 ** retry_number))


class RetryBudget:
    """Retries may be at most `ratio` of the calls made in the last `window` seconds
    (but always at least `min_retries`, so a quiet service can still retry a little)."""

    def __init__(self, clock, window=10.0, ratio=0.1, min_retries=0):
        self.clock, self.window, self.ratio, self.min_retries = clock, window, ratio, min_retries
        self._calls = deque()                   # timestamps of first attempts
        self._retries = deque()                 # timestamps of retries

    def _prune(self):
        cutoff = self.clock.now() - self.window
        for q in (self._calls, self._retries):
            while q and q[0] <= cutoff:
                q.popleft()

    def record_call(self):
        self._prune()
        self._calls.append(self.clock.now())

    def record_retry(self):
        self._retries.append(self.clock.now())

    def can_retry(self):
        self._prune()
        allowed = max(self.min_retries, self.ratio * len(self._calls))
        return len(self._retries) + 1 <= allowed + 1e-9


def retry(clock, rng, fn, policy, budget=None, retryable=is_retryable):
    """Call fn() up to policy.max_attempts times. Between attempts sleep a jittered backoff on the
    fake clock. Give up (re-raise the last error) when the error is not retryable, attempts are used
    up, or the budget says no."""
    if budget is not None:
        budget.record_call()
    attempt = 0
    while True:
        try:
            return fn()
        except Exception as exc:
            attempt += 1
            if not retryable(exc) or attempt >= policy.max_attempts:
                raise
            if budget is not None:
                if not budget.can_retry():
                    raise
                budget.record_retry()
            clock.sleep(backoff_delay(attempt - 1, policy, rng))


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
        if self._state == "open" and self.clock.now() >= self.opened_at + self.open_duration - 1e-9:
            self._transition("half-open", at=self.opened_at + self.open_duration)
        return self._state

    def window_counts(self):
        """(calls, failures) recorded in the rolling window. (Given.)"""
        cutoff = self.clock.now() - self.window
        while self.events and self.events[0][0] <= cutoff:
            self.events.popleft()
        return len(self.events), sum(1 for _, ok in self.events if not ok)

    def before_call(self):
        """Ask permission. Raises CircuitOpenError when the call must not be made."""
        s = self.state
        if s == "open" or (s == "half-open" and self.probes_admitted >= self.half_open_max):
            self.short_circuited += 1
            raise CircuitOpenError("circuit %s" % s)
        if s == "half-open":
            self.probes_admitted += 1

    def on_success(self):
        if self._state == "half-open":
            self.probe_successes += 1
            if self.probe_successes >= self.half_open_max:
                self._transition("closed")
        elif self._state == "closed":
            self.events.append((self.clock.now(), True))

    def on_failure(self):
        if self._state == "half-open":
            self._transition("open")
        elif self._state == "closed":
            self.events.append((self.clock.now(), False))
            calls, failures = self.window_counts()
            if calls >= self.min_calls and failures / calls >= self.failure_rate:
                self._transition("open")

    def call(self, fn):
        self.before_call()
        try:
            result = fn()
        except Exception as exc:
            # A 400 means the dependency is alive and answering; only retryable errors and timeouts count as failures.
            if is_retryable(exc):
                self.on_failure()
            else:
                self.on_success()
            raise
        self.on_success()
        return result


# ======================================================================================
# Milestone 4: the bulkhead
# ======================================================================================
class Bulkhead:
    """At most `max_concurrent` calls in flight to one dependency. A full bulkhead rejects at once;
    it never queues, because a queue is just another place for a slow dependency to hold your threads."""

    def __init__(self, max_concurrent, name="dependency"):
        self.max_concurrent, self.name = max_concurrent, name
        self._lock = threading.Lock()
        self.in_flight = 0
        self.max_seen = 0
        self.rejected = 0

    def acquire(self):
        with self._lock:
            if self.in_flight >= self.max_concurrent:
                self.rejected += 1
                raise BulkheadFullError("%s: %d calls already in flight" % (self.name, self.in_flight))
            self.in_flight += 1
            self.max_seen = max(self.max_seen, self.in_flight)

    def release(self):
        with self._lock:
            if self.in_flight <= 0:
                raise RuntimeError("release() without a matching acquire()")
            self.in_flight -= 1

    def call(self, fn):
        self.acquire()
        try:
            return fn()
        finally:
            self.release()


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
        """retry( bulkhead( breaker( timeout( fn ) ) ) )"""
        def one_attempt():
            return self.bulkhead.call(
                lambda: self.breaker.call(
                    lambda: with_timeout(self.clock, fn, self.timeout)))
        return retry(self.clock, self.rng, one_attempt, self.policy, self.budget)


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
