"""Lab 3 reference solution: Races & Locks.

Five milestones, one idea each:
  1. UnsafeCounter   - make a lost update happen on purpose
  2. SafeCounter     - fix it with a lock
  3. transfer_*      - bank transfers: deadlock, then lock ordering
  4. BoundedQueue    - a blocking queue built from a Condition
  5. SeatMap         - a check-then-act bug (optional)
"""
import collections
import queue
import threading
import time


def run_threads(counter, n_threads, n_incr):
    """Start n_threads daemon threads that each call counter.increment() n_incr times.
    Waits for them (at most 30 s, so a bug can never hang you) and returns the final value."""
    def work():
        for _ in range(n_incr):
            counter.increment()

    threads = [threading.Thread(target=work, daemon=True) for _ in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(30)
    return counter.value


# --- Milestone 1: a lost update, on purpose ------------------------------------------

class UnsafeCounter:
    def __init__(self):
        self.value = 0

    def increment(self):
        v = self.value          # step 1: read
        time.sleep(0)           # step 2: yield the CPU (and the GIL) right here
        self.value = v + 1      # step 3: write back a possibly stale answer


# --- Milestone 2: the same counter, fixed with a lock --------------------------------

class SafeCounter:
    def __init__(self):
        self.value = 0
        self._lock = threading.Lock()

    def increment(self):
        with self._lock:        # only one thread at a time may run the three steps
            v = self.value
            time.sleep(0)       # same yield as before: it no longer matters
            self.value = v + 1


# --- Milestone 3: bank transfers -----------------------------------------------------

class LockTimeout(Exception):
    """A lock could not be acquired in time (we suspect a deadlock)."""


class Account:
    def __init__(self, acct_id, balance):
        self.id = acct_id
        self.balance = balance
        self.lock = threading.Lock()


def transfer_naive(src, dst, amount, pause=0.0, timeout=1.0):
    """Lock src, then dst, exactly in the order given. Deadlock-prone on purpose.
    Returns True if the money moved, False if src has too little. Raises LockTimeout
    if a lock could not be acquired within `timeout` seconds."""
    if not src.lock.acquire(timeout=timeout):
        raise LockTimeout(f"could not lock account {src.id}")
    try:
        time.sleep(pause)                       # widens the window so the deadlock is reliable
        if not dst.lock.acquire(timeout=timeout):
            raise LockTimeout(f"could not lock account {dst.id} while holding {src.id}")
        try:
            if src.balance < amount:
                return False
            src.balance -= amount
            dst.balance += amount
            return True
        finally:
            dst.lock.release()
    finally:
        src.lock.release()                      # always runs, even after a LockTimeout


def transfer_ordered(src, dst, amount, pause=0.0, timeout=5.0):
    """Same job, but always lock the account with the smaller id first."""
    if src is dst:
        raise ValueError("cannot transfer to the same account")
    first, second = (src, dst) if src.id < dst.id else (dst, src)
    if not first.lock.acquire(timeout=timeout):
        raise LockTimeout(f"could not lock account {first.id}")
    try:
        time.sleep(pause)
        if not second.lock.acquire(timeout=timeout):
            raise LockTimeout(f"could not lock account {second.id} while holding {first.id}")
        try:
            if src.balance < amount:
                return False
            src.balance -= amount
            dst.balance += amount
            return True
        finally:
            second.lock.release()
    finally:
        first.lock.release()


# --- Milestone 4: a bounded blocking queue -------------------------------------------

class BoundedQueue:
    def __init__(self, maxsize):
        if maxsize < 1:
            raise ValueError("maxsize must be at least 1")
        self.maxsize = maxsize
        self._items = collections.deque()
        self._lock = threading.Lock()
        # Two conditions sharing ONE lock: producers wait on not_full, consumers on not_empty.
        self._not_full = threading.Condition(self._lock)
        self._not_empty = threading.Condition(self._lock)

    def put(self, item, timeout=None):
        deadline = None if timeout is None else time.monotonic() + timeout
        with self._lock:
            while len(self._items) >= self.maxsize:     # WHILE, not if: re-check after waking
                if deadline is None:
                    self._not_full.wait()
                else:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise queue.Full
                    self._not_full.wait(remaining)
            self._items.append(item)
            self._not_empty.notify()                    # one consumer can proceed

    def get(self, timeout=None):
        deadline = None if timeout is None else time.monotonic() + timeout
        with self._lock:
            while not self._items:
                if deadline is None:
                    self._not_empty.wait()
                else:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise queue.Empty
                    self._not_empty.wait(remaining)
            item = self._items.popleft()
            self._not_full.notify()                     # one producer can proceed
            return item

    def qsize(self):
        with self._lock:
            return len(self._items)


# --- Milestone 5 (optional): check-then-act ------------------------------------------

class SeatMap:
    def __init__(self):
        self._owners = {}
        self._lock = threading.Lock()

    def reserve_unsafe(self, seat, who):
        """BUGGY, given to you: check, pause, act."""
        if seat not in self._owners:        # check
            time.sleep(0.001)               # someone else can slip in here
            self._owners[seat] = who        # act
            return True
        return False

    def reserve(self, seat, who):
        """Fixed: the check and the act happen under one lock."""
        with self._lock:
            if seat in self._owners:
                return False
            self._owners[seat] = who
            return True

    def owner(self, seat):
        return self._owners.get(seat)


# --- A little demo: python3 solution.py ----------------------------------------------

if __name__ == "__main__":
    for cls in (UnsafeCounter, SafeCounter):
        got = run_threads(cls(), 8, 1000)
        print(f"{cls.__name__:14s} expected 8000, got {got}")
