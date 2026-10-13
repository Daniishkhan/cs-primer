"""Lab 4: Queues, load tests and coordinated omission.

One process, simulated time, seeded randomness: no sleeping, no sockets, no threads.
You build a discrete-event simulator for a queue with c servers, check it against the
formulas of chapter 8 (M/M/1, Erlang C, Little's law, Kingman), and then use the same
ideas to build two load generators that disagree about how slow a stalling server is.
The second one is right.

    1  simulate: Poisson (or regular) arrivals, c servers, one FIFO queue
    2  mm1_sojourn, erlang_c, mmc_wait, littles_law
    3  kingman_wq, kingman_table
    4  percentile, run_closed, run_open, co_correct
    5  sweep, find_knee, max_rate_under_slo, saturation_throughput

What is GIVEN: the service-time distributions, the Job and Result types, and the
stalling server used by the load generators. What YOU write is marked TODO.
`python3 check.py` runs the milestones; the lab page explains each one.
"""
import heapq
import math
import random
from collections import deque
from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple


# =============================================================================
# GIVEN: service-time distributions, jobs, results
# =============================================================================
def make_service(kind: str, mean: float) -> Callable[[random.Random], float]:
    """A sampler for service times with the given mean.

    kind      squared coefficient of variation cs^2
    "det"     0      every job takes exactly `mean`
    "erlang2" 0.5    the sum of two exponentials
    "exp"     1      exponential (the "M" in M/M/1)
    "hyper4"  4      mostly short jobs, a few very long ones (two-phase
                     hyperexponential with balanced means)
    """
    if kind == "det":
        return lambda rng: mean
    if kind == "exp":
        return lambda rng: rng.expovariate(1.0 / mean)
    if kind == "erlang2":
        return lambda rng: rng.expovariate(2.0 / mean) + rng.expovariate(2.0 / mean)
    if kind == "hyper4":
        cv2 = 4.0
        p = 0.5 * (1.0 + math.sqrt((cv2 - 1.0) / (cv2 + 1.0)))

        def hyper(rng):
            if rng.random() < p:
                return rng.expovariate(2.0 * p / mean)
            return rng.expovariate(2.0 * (1.0 - p) / mean)
        return hyper
    raise ValueError("unknown service kind: " + kind)


CS2 = {"det": 0.0, "erlang2": 0.5, "exp": 1.0, "hyper4": 4.0}


@dataclass
class Job:
    arrival: float
    service: float
    start: float = 0.0
    finish: float = 0.0

    @property
    def wait(self) -> float:
        return self.start - self.arrival

    @property
    def sojourn(self) -> float:
        return self.finish - self.arrival


@dataclass
class Result:
    jobs: List[Job]          # in order of arrival
    area: float              # integral of (jobs in the system) dt over the run
    horizon: float           # time of the last departure

    def stats(self, warmup: float = 0.1):
        """(mean wait, mean time in system) over the jobs after the first `warmup`
        fraction. The start of a run is an empty system, which is not typical."""
        js = self.jobs[int(len(self.jobs) * warmup):]
        return (sum(j.wait for j in js) / len(js), sum(j.sojourn for j in js) / len(js))

    def sojourns(self, warmup: float = 0.1) -> List[float]:
        return [j.sojourn for j in self.jobs[int(len(self.jobs) * warmup):]]


# =============================================================================
# 1. A discrete-event simulator
# =============================================================================
ARRIVAL, DEPARTURE = 0, 1


def simulate(lam: float, service: Callable[[random.Random], float], c: int, n_jobs: int, seed: int,
             arrivals: str = "poisson") -> Result:
    """Simulate n_jobs jobs through a FIFO queue with c servers.

    lam       arrival rate (jobs per second)
    service   a sampler: service(rng) -> seconds; call it ONCE per job, at its arrival
    arrivals  "poisson": exponential gaps with mean 1/lam
              "regular": a gap of exactly 1/lam
    Use two random.Random streams (arrivals and service times) derived from `seed`,
    so changing the service distribution does not change the arrival times.
    Keep a heap of future events (time, tie-breaker, kind, job), a deque of waiting
    jobs and a count of busy servers. Before handling an event at time t, add
    (jobs in system) * (t - previous event time) to `area`. Run until every job has
    left. Fill in job.start and job.finish.
    """
    raise NotImplementedError("TODO milestone 1: simulate")


# =============================================================================
# 2. Formulas, and Little's law
# =============================================================================
def mm1_sojourn(lam: float, mu: float) -> float:
    """Mean time in system for M/M/1: 1 / (mu - lam)."""
    raise NotImplementedError("TODO milestone 2: mm1_sojourn")


def erlang_c(c: int, a: float) -> float:
    """Probability that an arriving job must wait in M/M/c, with offered load
    a = lam / mu (in 'servers'), a < c:
        C(c, a) = [a^c / c! * c/(c-a)] / [ sum_{k<c} a^k / k!  +  a^c / c! * c/(c-a) ]
    Compute the terms iteratively (term_k = term_{k-1} * a / k) so big c does not overflow."""
    raise NotImplementedError("TODO milestone 2: erlang_c")


def mmc_wait(lam: float, mu: float, c: int) -> float:
    """Mean wait in the queue for M/M/c: Wq = C(c, a) / (c*mu - lam)."""
    raise NotImplementedError("TODO milestone 2: mmc_wait")


def littles_law(res: Result) -> Tuple[float, float]:
    """Return (L, lambda * W): the time-average number of jobs in the system
    (area / horizon), and the arrival rate (jobs / horizon) times the mean time in
    system. For a run that is allowed to drain the two are equal."""
    raise NotImplementedError("TODO milestone 2: littles_law")


# =============================================================================
# 3. Kingman: variability multiplies the wait
# =============================================================================
def kingman_wq(rho: float, ca2: float, cs2: float, tau: float) -> float:
    """Kingman's approximation for the mean wait in a G/G/1 queue:
        Wq ~ (rho / (1 - rho)) * ((ca2 + cs2) / 2) * tau
    ca2, cs2: squared coefficients of variation of inter-arrival and service times;
    tau: mean service time."""
    raise NotImplementedError("TODO milestone 3: kingman_wq")


def kingman_table(rho: float, kinds: List[str], tau: float = 1.0, n_jobs: int = 60000,
                  seeds: Tuple[int, ...] = (1, 2, 3), arrivals: str = "poisson"):
    """For each service kind, run a single-server queue at utilisation rho (Poisson
    or regular arrivals) and return a list of (kind, cs2, simulated mean wait,
    Kingman's prediction). Average the simulated wait over the seeds
    (use Result.stats()). With regular arrivals ca2 is 0, with Poisson it is 1."""
    raise NotImplementedError("TODO milestone 3: kingman_table")


# =============================================================================
# GIVEN: a server that stalls (a garbage-collection pause, a failover, a lock)
# =============================================================================
def make_stalls(seed: int, duration: float, every: float = 10.0, length: float = 1.0) -> List[Tuple[float, float]]:
    """One stall of `length` seconds in every `every`-second block, at a random spot."""
    rng = random.Random(seed * 7 + 5)
    out = []
    t = 0.0
    while t + every <= duration:
        s = t + rng.uniform(0.1 * every, 0.9 * every - length)
        out.append((s, s + length))
        t += every
    return out


def stalled_finish(start: float, work: float, stalls: List[Tuple[float, float]]) -> float:
    """When does `work` seconds of service that begins at `start` complete, if the
    server does nothing during the stall intervals (sorted, disjoint)?"""
    t, remaining = start, work
    for s, e in stalls:
        if e <= t:
            continue
        if s > t:
            if remaining <= s - t:
                return t + remaining
            remaining -= s - t
        t = e
    return t + remaining


class StallingServer:
    """One FIFO server whose clock stops during stalls. Requests must be offered in
    the order they are sent: `serve(sent_at, work)` returns the completion time."""

    def __init__(self, stalls, mean_service: float = 0.005, seed: int = 1):
        self.stalls, self.mean = stalls, mean_service
        self.free_at = 0.0
        self.rng = random.Random(seed * 13 + 1)

    def serve(self, sent_at: float) -> float:
        work = self.rng.expovariate(1.0 / self.mean)
        start = max(sent_at, self.free_at)
        self.free_at = stalled_finish(start, work, self.stalls)
        return self.free_at


# =============================================================================
# 4. Two load generators, and coordinated omission
# =============================================================================
def percentile(xs: List[float], p: float) -> float:
    """The p-th percentile (0 < p <= 100), nearest-rank method: sort, then take the
    element at 1-based rank ceil(p/100 * n)."""
    raise NotImplementedError("TODO milestone 4: percentile")


def run_closed(server: StallingServer, users: int, think: float, duration: float, seed: int = 1) -> List[float]:
    """CLOSED LOOP: `users` virtual users. Each one sends a request, waits for the
    response, thinks for an exponential time with mean `think`, and sends the next.
    A user never has two requests in flight, so a stalled server slows the users down.
    Users start at random times in [0, think). Keep a heap of (next send time, user).
    Pop the earliest, call server.serve(send_time), record latency = completion -
    send time, and schedule that user's next send at completion + think time.
    Stop sending after `duration`. Return the list of latencies."""
    raise NotImplementedError("TODO milestone 4: run_closed")


def run_open(server: StallingServer, rate: float, duration: float) -> List[float]:
    """OPEN LOOP: requests are sent at a fixed rate, at intended times 0, 1/rate,
    2/rate, ..., whether or not earlier responses have come back. Measure each
    latency from the INTENDED send time (the moment the user would have arrived),
    not from when something got around to sending it. Return the latencies."""
    raise NotImplementedError("TODO milestone 4: run_open")


def co_correct(latencies: List[float], expected_interval: float) -> List[float]:
    """Gil Tene's correction for coordinated omission (what HdrHistogram's
    recordValueWithExpectedInterval does). A generator that meant to send a request
    every `expected_interval` seconds but sat waiting for a slow response of latency L
    skipped the requests it would have sent meanwhile. Those would have been waiting
    too, each a little less than the one before: L - interval, L - 2*interval, ...,
    stopping when the value reaches zero. Return the original latencies plus those
    synthetic ones, as a new list."""
    raise NotImplementedError("TODO milestone 4: co_correct")


# =============================================================================
# 5. Saturation, the knee and the SLO
# =============================================================================
def sweep(rates: List[float], service: Callable[[random.Random], float], c: int, n_jobs: int, seed: int):
    """Open-loop load test of a c-server queue at each arrival rate. Return a list
    of (rate, p50, p99) of the time in system (use simulate and percentile on
    Result.sojourns())."""
    raise NotImplementedError("TODO milestone 5: sweep")


def find_knee(points: List[Tuple[float, float]]) -> float:
    """The knee of a hockey-stick curve. `points` is a list of (rate, latency)
    sorted by rate. Scale both axes to [0, 1], draw the straight line from the first
    to the last point, and return the rate of the point farthest from that line."""
    raise NotImplementedError("TODO milestone 5: find_knee")


def max_rate_under_slo(slo: float, service: Callable[[random.Random], float], c: int, lo: float, hi: float,
                       n_jobs: int = 40000, seed: int = 1, steps: int = 12) -> float:
    """The highest arrival rate whose p99 time in system is at most `slo` seconds.
    p99 grows with the rate, so bisect between lo (meets the SLO) and hi (does not):
    simulate at the middle, keep the half that still straddles the SLO. Use the same
    seed for every probe. Return the final lo."""
    raise NotImplementedError("TODO milestone 5: max_rate_under_slo")


def saturation_throughput(users: int, mean_service: float, duration: float = 60.0, seed: int = 1) -> float:
    """Throughput (completed requests per second) of a closed loop with no think
    time against a single stall-free server. With enough users the server is never
    idle, so this is its saturation point. Use run_closed with think=0."""
    raise NotImplementedError("TODO milestone 5: saturation_throughput")
