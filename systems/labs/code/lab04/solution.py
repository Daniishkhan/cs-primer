"""Lab 4 reference solution: a thread pool with backpressure.

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
        self._cond = threading.Condition()
        self._done = False
        self._result = None
        self._exception = None

    def set_result(self, value):
        with self._cond:
            self._result = value
            self._done = True
            self._cond.notify_all()        # wake EVERY thread waiting in result()

    def set_exception(self, exc):
        with self._cond:
            self._exception = exc
            self._done = True
            self._cond.notify_all()

    def done(self):
        with self._cond:
            return self._done

    def result(self, timeout=None):
        """Block until done. Raise TimeoutError if `timeout` seconds pass first; re-raise the
        task's exception if it failed."""
        with self._cond:
            if not self._done:
                # wait_for re-checks the predicate in a loop for us (like our `while`)
                if not self._cond.wait_for(lambda: self._done, timeout):
                    raise TimeoutError("future not done after %s s" % timeout)
            if self._exception is not None:
                raise self._exception
            return self._result


# --- Milestones 2-4, 6: ThreadPool ---------------------------------------------------

_STOP = object()          # the poison pill: "no more work, you may exit"
POLICIES = ("block", "reject", "caller_runs")


class ThreadPool:
    def __init__(self, n_workers, max_queue=0, policy="block"):
        if n_workers < 1:
            raise ValueError("n_workers must be at least 1")
        if policy not in POLICIES:
            raise ValueError("policy must be one of %r" % (POLICIES,))
        self.policy = policy
        self._queue = queue.Queue(maxsize=max_queue)      # 0 means unbounded
        self._stats_lock = threading.Lock()
        self.rejected = 0           # refused by policy "reject"
        self.caller_ran = 0         # run by the submitting thread (policy "caller_runs")
        self.expired = 0            # skipped because their deadline had passed
        self._closed = False
        self._shutdown_lock = threading.Lock()
        self.threads = [threading.Thread(target=self._worker, name="pool-%d" % i, daemon=True)
                        for i in range(n_workers)]
        for t in self.threads:
            t.start()

    def submit(self, fn, *args, deadline=None):
        """Queue fn(*args) and return a Future. `deadline` is a time.monotonic() timestamp."""
        if self._closed:
            raise RuntimeError("pool is shut down")
        fut = Future()
        task = (fut, fn, args, deadline)
        if self.policy == "block":
            self._queue.put(task)                       # waits for room: the producer slows down
        else:
            try:
                self._queue.put_nowait(task)
            except queue.Full:
                if self.policy == "reject":
                    with self._stats_lock:
                        self.rejected += 1
                    raise Rejected("queue full")
                with self._stats_lock:                  # "caller_runs"
                    self.caller_ran += 1
                self._run(task)                         # the producer does the work itself
        return fut

    def _run(self, task):
        fut, fn, args, deadline = task
        if deadline is not None and time.monotonic() > deadline:
            with self._stats_lock:
                self.expired += 1
            fut.set_exception(DeadlineExceeded("deadline passed before the task started"))
            return
        try:
            fut.set_result(fn(*args))
        except Exception as e:                          # a failing task must not kill the worker
            fut.set_exception(e)

    def _worker(self):
        while True:
            task = self._queue.get()
            if task is _STOP:
                return                                   # exactly one pill per worker
            self._run(task)

    def shutdown(self, wait=True):
        """Finish everything already queued, then stop the workers."""
        with self._shutdown_lock:
            if self._closed:
                return
            self._closed = True
        for _ in self.threads:
            self._queue.put(_STOP)      # behind all queued tasks, because the queue is FIFO
        if wait:
            for t in self.threads:
                t.join()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.shutdown(wait=True)


# --- Milestone 5: measuring ----------------------------------------------------------

def percentile(values, p):
    if not values:
        return 0.0
    s = sorted(values)
    return s[min(len(s) - 1, int(p / 100.0 * len(s)))]


def run_load(arrival_rate, n_tasks, service_time, n_workers, max_queue=0, policy="block", seed=1):
    """Submit n_tasks sleep(service_time) tasks at about arrival_rate tasks/second (random
    gaps, like real traffic) to a fresh pool. Returns a dict of measurements."""
    rng = random.Random(seed)
    pool = ThreadPool(n_workers, max_queue=max_queue, policy=policy)
    lock = threading.Lock()
    latencies = []          # time in system (queue wait + service) of each finished task
    in_system = [0]         # how many accepted tasks are not finished yet
    samples = []            # periodic readings of in_system, for L
    stop = threading.Event()

    def sampler():
        while not stop.is_set():
            with lock:
                samples.append(in_system[0])
            time.sleep(0.005)

    def make_task(arrived):
        def task():
            time.sleep(service_time)
            with lock:
                latencies.append(time.monotonic() - arrived)
                in_system[0] -= 1
        return task

    threading.Thread(target=sampler, daemon=True).start()
    start = time.monotonic()
    next_arrival = start
    futures, rejected = [], 0
    for _ in range(n_tasks):
        next_arrival += rng.expovariate(arrival_rate)        # absolute schedule: no drift
        delay = next_arrival - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        arrived = time.monotonic()
        with lock:
            in_system[0] += 1
        try:
            futures.append(pool.submit(make_task(arrived)))
        except Rejected:
            rejected += 1
            with lock:
                in_system[0] -= 1
    for f in futures:
        f.result(timeout=60)
    elapsed = time.monotonic() - start
    stop.set()
    pool.shutdown()
    completed = len(latencies)
    avg = sum(latencies) / completed if completed else 0.0
    throughput = completed / elapsed
    return {
        "submitted": n_tasks, "completed": completed, "rejected": rejected,
        "avg": avg, "p95": percentile(latencies, 95),
        "throughput": throughput,
        "L": sum(samples) / len(samples) if samples else 0.0,    # measured: average number in system
        "lambda_W": throughput * avg,                            # Little's law prediction
        "elapsed": elapsed,
    }


def sweep(service_time=0.02, n_workers=4, n_tasks=300, utilisations=(0.3, 0.5, 0.7, 0.85, 0.95, 1.1)):
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
