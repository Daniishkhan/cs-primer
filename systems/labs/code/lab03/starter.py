"""Lab 3 starter: Races & Locks.  Fill in every TODO, then run:  python3 check.py

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
    Waits for them (at most 30 s, so a bug can never hang you) and returns the final value.
    (Already written for you.)"""
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
    """A counter that LOSES updates when several threads share it."""

    def __init__(self):
        self.value = 0

    def increment(self):
        """Add 1 to self.value in three separate steps, with a yield in the middle:
              1. read self.value into a local variable
              2. time.sleep(0)   <- hands the CPU (and the GIL) to another thread
              3. write the local variable + 1 back to self.value
        Do NOT write `self.value += 1` and do NOT use a lock: the bug is the point."""
        raise NotImplementedError("TODO milestone 1: UnsafeCounter.increment")


# --- Milestone 2: the same counter, fixed with a lock --------------------------------

class SafeCounter:
    """Same three steps, but now the answer is always exact."""

    def __init__(self):
        self.value = 0
        # TODO milestone 2: create a threading.Lock here

    def increment(self):
        """Do the same read / sleep(0) / write, but inside `with self._lock:`.
        Keep the time.sleep(0): the lock must work even when we invite a thread switch."""
        raise NotImplementedError("TODO milestone 2: SafeCounter.increment")


# --- Milestone 3: bank transfers -----------------------------------------------------

class LockTimeout(Exception):
    """A lock could not be acquired in time (we suspect a deadlock)."""


class Account:
    def __init__(self, acct_id, balance):
        self.id = acct_id
        self.balance = balance
        self.lock = threading.Lock()


def transfer_naive(src, dst, amount, pause=0.0, timeout=1.0):
    """Move `amount` from src to dst. Lock src FIRST, then dst, exactly in the order given.

    Steps:
      1. src.lock.acquire(timeout=timeout); if it returns False, raise LockTimeout.
      2. time.sleep(pause)   (a pause between the two locks; it makes the deadlock reliable)
      3. dst.lock.acquire(timeout=timeout); if it returns False, raise LockTimeout.
      4. If src.balance < amount return False; otherwise move the money and return True.
      5. Release every lock you took, in `finally:` blocks, even when you raise.
    """
    raise NotImplementedError("TODO milestone 3: transfer_naive")


def transfer_ordered(src, dst, amount, pause=0.0, timeout=5.0):
    """Same job as transfer_naive, but never deadlocks: always lock the account with the
    SMALLER id first, whichever one is the source. Same return values and exceptions.
    Raise ValueError if src is dst (a plain Lock cannot be taken twice by one thread)."""
    raise NotImplementedError("TODO milestone 3: transfer_ordered")


# --- Milestone 4: a bounded blocking queue -------------------------------------------

class BoundedQueue:
    """A FIFO queue holding at most `maxsize` items, safe for many producers and consumers."""

    def __init__(self, maxsize):
        """Store maxsize (raise ValueError if < 1), a collections.deque, ONE threading.Lock,
        and two Conditions built on that same lock: _not_full and _not_empty."""
        raise NotImplementedError("TODO milestone 4: BoundedQueue.__init__")

    def put(self, item, timeout=None):
        """Add item. While the queue is full, wait on _not_full. Use a WHILE loop, not `if`.
        timeout=None waits forever; otherwise raise queue.Full once `timeout` seconds have
        passed in total (compute a deadline with time.monotonic()). Then notify _not_empty."""
        raise NotImplementedError("TODO milestone 4: BoundedQueue.put")

    def get(self, timeout=None):
        """Remove and return the oldest item. While empty, wait on _not_empty (a WHILE loop).
        timeout works like put's but raises queue.Empty. Then notify _not_full."""
        raise NotImplementedError("TODO milestone 4: BoundedQueue.get")

    def qsize(self):
        """Number of items right now (take the lock to read it)."""
        raise NotImplementedError("TODO milestone 4: BoundedQueue.qsize")


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
        """Reserve `seat` for `who`. Return True if you got it, False if it was taken.
        Exactly ONE caller may ever get True for a given seat, even if many call at once."""
        raise NotImplementedError("TODO milestone 5: SeatMap.reserve")

    def owner(self, seat):
        return self._owners.get(seat)


# --- A little demo: python3 starter.py -----------------------------------------------

if __name__ == "__main__":
    for cls in (UnsafeCounter, SafeCounter):
        got = run_threads(cls(), 8, 1000)
        print(f"{cls.__name__:14s} expected 8000, got {got}")
