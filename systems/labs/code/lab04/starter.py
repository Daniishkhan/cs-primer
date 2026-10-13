"""Lab 4 starter: a thread pool with backpressure.  Fill in every TODO, then run: python3 check.py

Six milestones:
  1. Future            - a promise of a result that another thread will fill in
  2. ThreadPool        - workers pulling tasks from a queue
  3. shutdown          - finish queued work, then stop every worker (poison pills)
  4. backpressure      - "block", "reject" and "caller_runs" when the queue is full
  5. run_load          - measure latency under load; see the knee and Little's law
  6. deadlines         - skip tasks nobody is waiting for any more (optional)
"""
import queue
import random
import threading
import time


class Rejected(Exception):
    """submit() refused the task because the queue was full (policy "reject")."""


class DeadlineExceeded(Exception):
    """The task's deadline passed before a worker could start it."""


# --- Milestone 1: Future -------------------------------------------------------------

class Future:
    """A box that is empty now and will be filled once, by another thread."""

    def __init__(self):
        # TODO milestone 1: a threading.Condition plus fields for done / result / exception
        pass

    def set_result(self, value):
        """Store the value, mark the future done, and wake EVERY thread waiting in result()
        (notify_all, not notify)."""
        raise NotImplementedError("TODO milestone 1: Future.set_result")

    def set_exception(self, exc):
        """Like set_result, but result() must re-raise `exc` instead of returning."""
        raise NotImplementedError("TODO milestone 1: Future.set_exception")

    def done(self):
        """True once a result or exception has been set. Never blocks."""
        raise NotImplementedError("TODO milestone 1: Future.done")

    def result(self, timeout=None):
        """Block until done, then return the value (or raise the stored exception).
        If `timeout` seconds pass first, raise the built-in TimeoutError.
        Hint: Condition.wait_for(predicate, timeout) returns False on timeout."""
        raise NotImplementedError("TODO milestone 1: Future.result")


# --- Milestones 2-4, 6: ThreadPool ---------------------------------------------------

_STOP = object()          # the poison pill: "no more work, you may exit"
POLICIES = ("block", "reject", "caller_runs")


class ThreadPool:
    def __init__(self, n_workers, max_queue=0, policy="block"):
        """Milestone 2: create queue.Queue(maxsize=max_queue) (0 = unbounded) and start
        n_workers DAEMON threads (daemon=True, so a bug can never keep Python alive), all
        running self._worker. Keep them in a list called self.threads.
        Also keep: self.policy, counters self.rejected / self.caller_ran / self.expired
        (guard them with a Lock), and a self._closed flag.
        Milestone 4: raise ValueError for an unknown policy."""
        raise NotImplementedError("TODO milestone 2: ThreadPool.__init__")

    def submit(self, fn, *args, deadline=None):
        """Milestone 2: wrap fn and args in a task together with a new Future, put it on the
        queue, and return the Future. If the pool is shut down, raise RuntimeError.
        Milestone 4: when the queue is full, obey self.policy:
            "block"       wait for room (queue.put)
            "reject"      count it in self.rejected and raise Rejected at once
            "caller_runs" count it in self.caller_ran and run the task right here, in the
                          calling thread; return its (already finished) Future
        Milestone 6: `deadline` is a time.monotonic() timestamp; see _run."""
        raise NotImplementedError("TODO milestone 2: ThreadPool.submit")

    def _run(self, task):
        """Run one task and fill in its Future. Used by workers and by caller_runs.
        Milestone 2: try fn(*args) -> fut.set_result(...); `except Exception as e` ->
        fut.set_exception(e). A failing task must NOT kill the worker.
        Milestone 6: first check the deadline; if time.monotonic() is past it, count it in
        self.expired, set DeadlineExceeded on the future, and skip the work."""
        raise NotImplementedError("TODO milestone 2: ThreadPool._run")

    def _worker(self):
        """Milestone 2: loop forever: task = queue.get(); run it.
        Milestone 3: if the task is the _STOP pill, return."""
        raise NotImplementedError("TODO milestone 2: ThreadPool._worker")

    def shutdown(self, wait=True):
        """Milestone 3: mark the pool closed (a second call does nothing), then put ONE _STOP
        pill per worker on the queue, and if wait is True join every worker thread."""
        raise NotImplementedError("TODO milestone 3: ThreadPool.shutdown")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.shutdown(wait=True)


# --- Milestone 5: measuring ----------------------------------------------------------

def percentile(values, p):
    """The p-th percentile (0-100) of a list, nearest-rank style. (Already written.)"""
    if not values:
        return 0.0
    s = sorted(values)
    return s[min(len(s) - 1, int(p / 100.0 * len(s)))]


def run_load(arrival_rate, n_tasks, service_time, n_workers, max_queue=0, policy="block", seed=1):
    """Submit n_tasks tasks, each time.sleep(service_time), at about arrival_rate per second
    to a fresh ThreadPool, wait for them, shut the pool down, and return a dict with:

      submitted, completed, rejected   counts (rejected = submits that raised Rejected)
      avg, p95                         seconds in the system (arrival -> finished), completed only
      throughput                       completed / elapsed seconds
      L                                the average number of accepted-but-unfinished tasks,
                                       measured by a sampler thread reading a counter every 5 ms
      lambda_W                         throughput * avg   (Little's law's prediction of L)
      elapsed                          seconds from the first arrival to the last completion

    Steps:
      - rng = random.Random(seed); gaps between arrivals are rng.expovariate(arrival_rate)
        (random gaps, like real traffic). Sleep until each absolute arrival time.
      - record time.monotonic() when a task ARRIVES; the task itself records its finish time.
      - a Lock protects the shared latency list and the in-system counter.
    """
    raise NotImplementedError("TODO milestone 5: run_load")


def sweep(service_time=0.02, n_workers=4, n_tasks=300, utilisations=(0.3, 0.5, 0.7, 0.85, 0.95, 1.1)):
    """Run run_load at several utilisations and print a table. (Already written.)"""
    capacity = n_workers / service_time
    print("%d workers x %.0f ms tasks: capacity = %.0f tasks/s" % (n_workers, service_time * 1000, capacity))
    print("%5s %7s %8s %8s %9s %7s %9s" % ("util", "rate/s", "avg ms", "p95 ms", "L (meas)", "lam*W", "done/sub"))
    rows = []
    for u in utilisations:
        r = run_load(u * capacity, n_tasks, service_time, n_workers, seed=int(u * 100))
        rows.append((u, r))
        print("%5.2f %7.0f %8.1f %8.1f %9.2f %7.2f %6d/%d" % (
            u, u * capacity, r["avg"] * 1000, r["p95"] * 1000, r["L"], r["lambda_W"],
            r["completed"], r["submitted"]))
    return rows


if __name__ == "__main__":
    sweep()
