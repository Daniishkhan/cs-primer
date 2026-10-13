"""Lab 3: A Linearizability Checker. Reference solution.

Same layout as starter.py. Try not to read this before you have had a real go.
Run `python3 check.py solution` to check it.
"""
import heapq
import itertools
import random
import sys
from collections import namedtuple

sys.setrecursionlimit(20000)          # the search below recurses once per linearized operation

# =====================================================================================
# GIVEN: the data types, two simulated stores, a workload, and two printing helpers.
# Read it, do not edit it.
# =====================================================================================

INF = float("inf")

# One line of a recorded history. type is "invoke", "ok", "fail" or "info".
#   invoke  a client (process) sent a request.      value: write -> the value, cas -> (old, new), read -> None
#   ok      it definitely happened.                 value: read -> what it returned; others -> same as the invoke
#   fail    it definitely did NOT happen.           (a cas whose compare failed, or an error reply)
#   info    no answer in time: it MAY have taken effect, at any moment after the invoke, or never.
Event = namedtuple("Event", "type process f value time")

# One operation with an interval, built from an invoke and its completion (milestone 1).
#   arg           what the client asked for: write -> the value, cas -> (old, new), read -> None
#   result        what a read returned (None for write and cas)
#   call, ret     when it was invoked and when it completed; ret is INF for an indeterminate (info) operation
#   indeterminate True if it timed out
Op = namedtuple("Op", "id process f arg result call ret indeterminate")


class Sim:
    """A tiny simulated clock plus an event queue. Everything random comes from one seeded RNG."""

    def __init__(self, seed):
        self.rng = random.Random(seed)
        self.now = 0
        self._queue = []
        self._count = 0

    def at(self, delay, fn):
        heapq.heappush(self._queue, (self.now + delay, self._count, fn))
        self._count += 1

    def run(self):
        while self._queue:
            self.now, _, fn = heapq.heappop(self._queue)
            fn()


class LeaderStore:
    """CORRECT. One leader holds the register. A request is applied atomically at the moment it
    reaches the leader, which is somewhere between the client's invoke and the client's reply:
    that moment is its linearization point."""

    def __init__(self, sim):
        self.sim = sim
        self.value = None

    def execute(self, f, arg):
        """Returns (type, value) for the completion event: ("ok", ...) or ("fail", ...)."""
        if f == "write":
            self.value = arg
            return ("ok", arg)
        if f == "read":
            return ("ok", self.value)
        old, new = arg                                  # cas
        if self.value == old:
            self.value = new
            return ("ok", arg)
        return ("fail", arg)


class LaggingFollowerStore(LeaderStore):
    """BUGGY. Writes go to the leader and are copied to a follower after a random lag (5 to 40
    ticks). To 'spread the load', half of all reads are answered by the follower. A read can
    therefore return a value that is already out of date by the time the client asks."""

    def __init__(self, sim):
        super().__init__(sim)
        self.follower = None
        self.follower_version = 0
        self.version = 0

    def execute(self, f, arg):
        if f == "read" and self.sim.rng.random() < 0.5:
            return ("ok", self.follower)                # the follower may be behind
        result = super().execute(f, arg)
        if f != "read" and result[0] == "ok":
            self.version += 1
            version, value = self.version, self.value
            self.sim.at(self.sim.rng.randint(5, 40), lambda: self._replicate(version, value))
        return result

    def _replicate(self, version, value):
        if version > self.follower_version:             # never goes backwards, only late
            self.follower_version = version
            self.follower = value


def simulate(store_cls, seed, clients=5, ops_per_client=40, loss=0.03):
    """Run `clients` concurrent clients against a fresh store and return the history: a list of
    Events in the order they happened. Same seed, same history.

    Each client does one request at a time: read (40%), write of a fresh unique value (35%) or
    cas (25%). A request or reply is lost with probability `loss`; the client then gives up after
    60 ticks and records an `info` event. Like Jepsen, it continues under a NEW process id, because
    the old request may still be in flight and one process has at most one pending operation.
    """
    sim = Sim(seed)
    store = store_cls(sim)
    events = []
    fresh = itertools.count(1)                          # unique write values: makes checking easier
    handed_out = [None]                                 # values a cas might expect
    next_process = itertools.count(clients)

    def emit(type_, process, f, value):
        events.append(Event(type_, process, f, value, sim.now))

    def client(process, remaining):
        if remaining:
            sim.at(sim.rng.randint(0, 10), lambda: begin(process, remaining))

    def begin(process, remaining):
        r = sim.rng.random()
        if r < 0.40:
            f, arg = "read", None
        elif r < 0.75:
            f, arg = "write", next(fresh)
            handed_out.append(arg)
        else:
            f, arg = "cas", (sim.rng.choice(handed_out), next(fresh))
            handed_out.append(arg[1])
        emit("invoke", process, f, arg)
        state = {"done": False}

        def reply(type_, value):
            if not state["done"]:
                state["done"] = True
                emit(type_, process, f, value)
                client(process, remaining - 1)

        def timeout():
            if not state["done"]:
                state["done"] = True
                emit("info", process, f, arg)
                client(next(next_process), remaining - 1)

        def arrive():                                   # the request reaches the server
            type_, value = store.execute(f, arg)
            if sim.rng.random() >= loss:
                sim.at(sim.rng.randint(1, 6), lambda: reply(type_, value))

        if sim.rng.random() >= loss:
            sim.at(sim.rng.randint(1, 6), arrive)
        sim.at(60, timeout)

    for c in range(clients):
        client(c, ops_per_client)
    sim.run()
    return events


def reads_are_explained(ops):
    """True if every value a read returned, and every old value a cas expected, was either the
    initial value (None) or was written by some operation in `ops`.

    You need this in milestone 5. When you shrink a history by deleting operations you must not
    delete a write that a remaining read still depends on: the history would then be 'not
    linearizable' only because it reads a value out of thin air, which is true but useless."""
    produced = {None}
    for o in ops:
        if o.f == "write":
            produced.add(o.arg)
        elif o.f == "cas":
            produced.add(o.arg[1])
    for o in ops:
        if o.f == "read" and o.result not in produced:
            return False
        if o.f == "cas" and not o.indeterminate and o.arg[0] not in produced:
            return False
    return True


def label(o):
    if o.f == "write":
        text = f"write({o.arg})"
    elif o.f == "read":
        text = f"read -> {o.result}"
    else:
        text = f"cas({o.arg[0]} -> {o.arg[1]})"
    return text + ("  (timed out)" if o.indeterminate else "")


def render(ops, width=44):
    """Draw operations as bars on a shared time axis, one line each, so overlaps are visible."""
    if not ops:
        return "(empty history)"
    lo = min(o.call for o in ops)
    finite = [o.ret for o in ops if o.ret != INF] + [o.call for o in ops]
    hi = max(finite)
    scale = (width - 1) / max(1, hi - lo)
    lines = []
    for o in sorted(ops, key=lambda o: (o.call, o.id)):
        a = int((o.call - lo) * scale)
        b = width - 1 if o.ret == INF else max(a + 1, int((o.ret - lo) * scale))
        bar = " " * a + "[" + "-" * (b - a - 1) + (">" if o.ret == INF else "]")
        end = "?" if o.ret == INF else o.ret
        lines.append(f"  p{o.process:<2} {bar:<{width + 1}} {label(o)}   t={o.call}..{end}")
    return "\n".join(lines)


# =====================================================================================
# YOUR WORK
# =====================================================================================

# ---- Milestone 1: from events to operations with intervals ----------------------------

def to_operations(events):
    """Pair every `invoke` with its completion and return a list of Op, in invocation order,
    with ids 0, 1, 2, ... in that order.

      ok    -> Op(..., ret=<completion time>, indeterminate=False); a read's result is the ok value
      fail  -> the operation did not happen: leave it out
      info  -> Op(..., ret=INF, indeterminate=True): it may take effect at any time after its call
      an invoke with no completion at all counts as info too
      an indeterminate READ has no result to check and changes nothing: leave it out

    Raise ValueError if a process invokes while it still has a pending operation, or if a
    completion has no matching invoke, or names a different `f` than its invoke."""
    pending = {}                                   # process -> (index of the invoke event, Event)
    made = []                                      # (invoke index, fields...) for the ops we keep

    def finish(index, inv, kind, ret, value):
        if kind == "fail":
            return
        if kind == "info":
            if inv.f == "read":
                return
            made.append((index, inv.process, inv.f, inv.value, None, inv.time, INF, True))
        else:
            result = value if inv.f == "read" else None
            made.append((index, inv.process, inv.f, inv.value, result, inv.time, ret, False))

    for i, e in enumerate(events):
        if e.type == "invoke":
            if e.process in pending:
                raise ValueError(f"process {e.process} invoked while it already has a pending operation")
            pending[e.process] = (i, e)
        else:
            if e.process not in pending:
                raise ValueError(f"process {e.process} completed an operation it never invoked")
            index, inv = pending.pop(e.process)
            if e.f != inv.f:
                raise ValueError(f"process {e.process} invoked {inv.f} but completed {e.f}")
            finish(index, inv, e.type, e.time, e.value)
    for index, inv in pending.values():            # never answered: same as a timeout
        finish(index, inv, "info", INF, None)
    made.sort(key=lambda m: m[0])
    return [Op(n, *m[1:]) for n, m in enumerate(made)]


# ---- Milestone 2: the sequential specification of a register --------------------------

class RegisterModel:
    """What a single register does when operations run one at a time. A model is stateless:
    the state is passed in and out, and must be hashable (milestone 4 stores it in a set)."""

    @staticmethod
    def init():
        return None                                # a fresh register holds None

    @staticmethod
    def step(state, op):
        """Apply `op` to a register holding `state`. Return (legal, new_state).

        write(v)       always legal; the register becomes v
        read -> r      legal only if the register holds r (an indeterminate read is always legal)
        cas(old, new)  legal only if the register holds `old`; it becomes `new`. (A cas that failed
                       its compare was a `fail` event and is not in the history at all.)"""
        if op.f == "write":
            return True, op.arg
        if op.f == "read":
            return (op.indeterminate or op.result == state), state
        old, new = op.arg
        if state == old:
            return True, new
        return False, state


# ---- Milestone 3: brute force over permutations ---------------------------------------

def _respects_real_time(order):
    """No operation may be placed after one that was invoked after it had already returned."""
    for i in range(len(order)):
        for j in range(i + 1, len(order)):
            if order[j].ret < order[i].call:
                return False
    return True


def _is_legal(order, model):
    state = model.init()
    for op in order:
        legal, state = model.step(state, op)
        if not legal:
            return False
    return True


def check_brute(ops, model=RegisterModel):
    """Try every order. Return a list of op ids in a legal order, or None if there is none.

    Every non-indeterminate operation must appear exactly once; each indeterminate one may appear
    once or not at all (it may never have taken effect). Raise ValueError for more than 9 ops."""
    if len(ops) > 9:
        raise ValueError("brute force is for small histories: at most 9 operations")
    required = [o for o in ops if not o.indeterminate]
    optional = [o for o in ops if o.indeterminate]
    for k in range(len(optional) + 1):
        for took_effect in itertools.combinations(optional, k):
            for order in itertools.permutations(required + list(took_effect)):
                if _respects_real_time(order) and _is_legal(order, model):
                    return [o.id for o in order]
    return None


# ---- Milestone 4: Wing & Gong search with memoization ---------------------------------

def check(ops, model=RegisterModel, stats=None):
    """Return a list of op ids in a legal order, or None. Same answer as check_brute, but fast.

    Build the order from the front. At each step the candidates are the operations nobody has to
    precede: an unlinearized op `o` may go next unless some other unlinearized required op returned
    before `o` was called. Try each candidate against the model; recurse. Remember every
    (set of linearized ops, model state) that failed, so the same dead end is never explored twice.

    `stats`, if given, is a dict: add 1 to stats["states"] each time you expand a search node
    (not for a memo hit), so the checker can see that your memo works."""
    ops = sorted(ops, key=lambda o: (o.call, o.id))     # candidates are then a prefix of the list
    n = len(ops)
    required = 0
    for i, o in enumerate(ops):
        if not o.indeterminate:
            required |= 1 << i
    dead = set()                                        # (bitmask of linearized ops, state) known to fail

    def search(done, state):
        if done & required == required:                 # all required ops placed; the rest never happened
            return []
        key = (done, state)
        if key in dead:
            return None
        if stats is not None:
            stats["states"] = stats.get("states", 0) + 1
        # the earliest return time among required ops still to place: nothing called after it can go next
        horizon = min(ops[i].ret for i in range(n) if required >> i & 1 and not done >> i & 1)
        for i in range(n):
            if done >> i & 1:
                continue
            op = ops[i]
            if op.call > horizon:
                break
            legal, new_state = model.step(state, op)
            if legal:
                rest = search(done | 1 << i, new_state)
                if rest is not None:
                    return [op.id] + rest
        dead.add(key)
        return None

    return search(0, model.init())


# ---- Milestone 5: find a violation, then make it small --------------------------------

def find_violation(store_cls, seeds):
    """Run `simulate(store_cls, seed)` for each seed, convert to operations, and check each.
    Return (seed, ops) for the first history that is NOT linearizable, or None if all are."""
    for seed in seeds:
        ops = to_operations(simulate(store_cls, seed))
        if check(ops) is None:
            return seed, ops
    return None


def minimal_counterexample(ops):
    """Return a sublist of `ops` that is still not linearizable but is as small as you can make it:
    removing any single operation from it makes it linearizable (or leaves a read that nothing
    wrote: use reads_are_explained to refuse those). Delta debugging: try dropping chunks of
    operations, halving the chunk size when nothing can be dropped."""
    def fails(candidate):
        return reads_are_explained(candidate) and check(candidate) is None

    current = list(ops)
    parts = 2
    while len(current) >= 2:
        chunk = max(1, len(current) // parts)
        for start in range(0, len(current), chunk):
            candidate = current[:start] + current[start + chunk:]
            if fails(candidate):
                current = candidate
                parts = max(parts - 1, 2)
                break
        else:                                           # nothing could be dropped at this granularity
            if chunk == 1:
                break
            parts = min(len(current), parts * 2)
    return current
