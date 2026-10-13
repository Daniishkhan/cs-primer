"""Lab 2: leases and fencing tokens on a simulated cluster.

One process, no threads, no sockets. Time is a simulated clock in milliseconds;
the "network" is a queue of delayed messages; randomness comes from one seeded
random.Random, so the same seed always replays the same run.

The cast:
    lock     a lock service that grants leases (YOU write its logic, milestone 1)
    store    a storage server that holds a counter, or a log (milestones 2, 3, 5)
    c0, c1.. clients that repeatedly do "read the value, work, write value + 1"
             while holding the lock. They can freeze (a GC pause), have a clock that
             runs fast or slow, and suffer slow messages.

What is GIVEN: Sim, the LockNode / StorageNode message adapters, the Client's main
loop and `build_world`. What YOU write is marked TODO:

    1  LockService         acquire / renew / release, with a monotonic token counter
    2  Client timing       on_grant, on_renewed, lease_ok  (+ the unfenced Storage)
    3  FenceGuard          the "highest token seen" check, used by Storage
    4  safety_margin       lease minus a drift bound (client side)
    5  FencedLog           a leader's log that refuses a deposed leader

`python3 check.py` runs the milestones; the lab page explains each one.
"""
import heapq
import math
import random

RPC_TIMEOUT = 20000     # a client gives up on a request after this long
RETRY = 50              # a client that is refused the lock waits this long
POINTS = ("after_read", "after_check")   # where a client can freeze


# =============================================================================
# GIVEN: the simulated world
# =============================================================================
class Sim:
    """Simulated time (ms), a delayed-message network and one clock per node.

    sim.now is TRUE time, which no node can see. A node reads sim.clock(name),
    its LOCAL clock: true time scaled by (1 + drift[name]). A drift of +0.05 is a
    clock that runs 5% fast; -0.05 runs 5% slow.
    """

    def __init__(self, seed, delay=(2, 20), slow_p=0.0, slow_max=0):
        self.seed = seed
        self.rng = random.Random(seed)
        self.now = 0
        self.q = []
        self.counter = 0
        self.nodes = {}
        self.drift = {}
        self.delay, self.slow_p, self.slow_max = delay, slow_p, slow_max
        self.trace = []                     # (time, text), for humans

    def clock(self, name):
        return int(self.now * (1 + self.drift.get(name, 0.0)))

    def schedule(self, delay, fn):
        self.counter += 1
        heapq.heappush(self.q, (self.now + delay, self.counter, fn))

    def send(self, src, dst, msg):
        d = self.rng.randint(*self.delay)
        if self.slow_p and self.rng.random() < self.slow_p:
            d += self.rng.randint(0, self.slow_max)          # a delayed packet
        self.schedule(d, lambda: self.nodes[dst].on_message(src, msg))

    def note(self, who, text):
        self.trace.append((self.now, f"{who}: {text}"))

    def run(self, until, stop=None):
        while self.q and self.q[0][0] <= until:
            time, _, fn = heapq.heappop(self.q)
            self.now = time
            fn()
            if stop and stop():
                return


class LockNode:
    """Network adapter around YOUR LockService. It reads the server's local clock,
    calls your methods, and replies. It also remembers the newest token ever issued,
    which the checker uses to recognise a stale writer."""

    def __init__(self, sim, service):
        self.sim, self.svc = sim, service
        self.latest_token = 0
        sim.nodes["lock"] = self

    def on_message(self, src, msg):
        now = self.sim.clock("lock")
        op, reply = msg["op"], {"ok": False, "token": None, "lease": self.svc.lease_ms, "rid": msg["rid"]}
        if op == "acquire":
            token = self.svc.acquire(src, now)
            if token is not None:
                reply.update(ok=True, token=token)
                self.latest_token = max(self.latest_token, token)
                self.sim.note("lock", f"grants token {token} to {src}")
        elif op == "renew":
            reply["ok"] = bool(self.svc.renew(src, msg["token"], now))
            reply["token"] = msg["token"]
        elif op == "release":
            reply["ok"] = bool(self.svc.release(src, msg["token"], now))
        self.sim.send("lock", src, reply)


class StorageNode:
    """Network adapter around YOUR storage object (a Storage or a FencedLog)."""

    def __init__(self, sim, storage, lock_node):
        self.sim, self.storage, self.lock_node = sim, storage, lock_node
        self.acked = 0              # writes the storage said yes to
        self.rejected = 0           # writes the storage said no to
        self.stale_accepted = 0     # accepted writes carrying a token LOWER than one this storage had already seen
        self.max_seen = 0
        sim.nodes["store"] = self

    def on_message(self, src, msg):
        token = msg["token"]
        seen, self.max_seen = self.max_seen, max(self.max_seen, token)
        if msg["op"] == "read":
            ok, value = self.storage.read(token)
            reply = {"ok": ok, "value": value, "rid": msg["rid"]}
        else:
            ok = self.storage.write(token, msg["value"])
            reply = {"ok": ok, "rid": msg["rid"]}
            if ok:
                self.acked += 1
                if token < seen:
                    self.stale_accepted += 1
                    self.sim.note("store", f"ACCEPTED write {msg['value']} from {src} with STALE token {token} (it has already seen {seen})")
                else:
                    self.sim.note("store", f"accepts write {msg['value']} from {src} (token {token})")
            else:
                self.rejected += 1
                self.sim.note("store", f"REJECTS write {msg['value']} from {src}: token {token} is stale (it has already seen {seen})")
        self.sim.send("store", src, reply)


class Client:
    """A client that does `jobs` times: hold the lock, read v, work, write v + 1.

    The main loop is GIVEN. It is written as a generator: `yield ("sleep", ms)` waits,
    `reply = yield ("rpc", dst, msg, timeout)` sends a request and waits for the answer.
    Your job (milestone 2) is the three small methods that decide what the client
    BELIEVES about its lease: on_grant, on_renewed and lease_ok.

    Fields you may use:
        self.token       the fencing token of the lease we hold, or None
        self.deadline    LOCAL clock time at which we stop believing we hold it
        self.sent_local  LOCAL clock reading taken when the request was SENT
        self.lease_ms    the lease length the server told us
        self.margin      safety margin in ms subtracted from the lease (milestone 4)
        self.local()     our local clock now
    """

    def __init__(self, sim, name, jobs, margin=0, script=None, pause_p=0.0, pause_max=0, work=20, start_at=0, renew=True):
        self.sim, self.name, self.jobs = sim, name, jobs
        self.renew = renew              # False: never renew, just re-acquire when the lease runs out
        self.margin, self.work = margin, work
        self.script = {k: list(v) for k, v in (script or {}).items()}
        self.pause_p, self.pause_max = pause_p, pause_max
        self.rng = random.Random(sim.seed * 7919 + sum(map(ord, name)))
        self.token = None
        self.deadline = 0
        self.sent_local = 0
        self.lease_ms = 0
        self.done = 0
        self.finished = False
        self.waiting = None
        self.rid = 0
        self.gen = self.main()
        sim.nodes[name] = self
        sim.schedule(start_at, lambda: self._resume(None))

    # ---- MILESTONE 2: what the client believes ----------------------------------
    def on_grant(self, token, lease_ms):
        """The lock service granted us `token` for `lease_ms`. Remember token and
        lease_ms. The lease is counted from the moment we SENT the request, on OUR
        clock, minus the safety margin:
            self.deadline = self.sent_local + lease_ms - self.margin"""
        raise NotImplementedError("TODO milestone 2: Client.on_grant")

    def on_renewed(self, lease_ms):
        """A renewal succeeded. Same arithmetic as on_grant, counted from the moment
        the RENEW request was sent (self.sent_local was refreshed before sending)."""
        raise NotImplementedError("TODO milestone 2: Client.on_renewed")

    def lease_ok(self):
        """Do we still believe we hold the lease? True only if we have a token and our
        LOCAL clock (self.local()) is still before self.deadline."""
        raise NotImplementedError("TODO milestone 2: Client.lease_ok")

    # ---- given: the client's life ---------------------------------------------
    def local(self):
        return self.sim.clock(self.name)

    def maybe_pause(self, point):
        """Milliseconds the client freezes at this point (a GC pause, a VM stall)."""
        if self.script.get(point):
            d = self.script[point].pop(0)
        elif self.pause_p and self.rng.random() < self.pause_p:
            d = self.rng.randint(1, self.pause_max)
        else:
            d = 0
        if d:
            self.sim.note(self.name, f"FREEZES for {d} ms {point.replace('_', ' ')} (it cannot know time passes)")
        return d

    def main(self):
        while self.done < self.jobs:
            if self.token is not None and not self.renew and not self.lease_ok():
                self.token = None
            if self.token is None:
                self.sent_local = self.local()
                reply = yield ("rpc", "lock", {"op": "acquire"}, RPC_TIMEOUT)
                if not (reply and reply["ok"]):
                    yield ("sleep", RETRY)
                    continue
                self.on_grant(reply["token"], reply["lease"])
                self.sim.note(self.name, f"holds token {self.token}, believes it holds the lease until local {self.deadline}")
            elif self.renew and self.deadline - self.local() < self.lease_ms // 2:
                self.sent_local = self.local()
                reply = yield ("rpc", "lock", {"op": "renew", "token": self.token}, RPC_TIMEOUT)
                if reply and reply["ok"]:
                    self.on_renewed(reply["lease"])
                else:
                    self.sim.note(self.name, f"renewal of token {self.token} refused: the lease is gone")
                    self.token = None
                    continue
            reply = yield ("rpc", "store", {"op": "read", "token": self.token}, RPC_TIMEOUT)
            if not (reply and reply["ok"]):
                self.sim.note(self.name, f"read refused (token {self.token}): stepping down")
                self.token = None
                continue
            value = reply["value"]
            d = self.maybe_pause("after_read")
            if d:
                yield ("sleep", d)
            yield ("sleep", self.work)
            if not self.lease_ok():                      # the naive "check right before writing"
                continue
            d = self.maybe_pause("after_check")
            if d:
                yield ("sleep", d)
            reply = yield ("rpc", "store", {"op": "write", "token": self.token, "value": value + 1}, RPC_TIMEOUT)
            if reply and reply["ok"]:
                self.done += 1
            else:
                self.sim.note(self.name, f"write refused: token {self.token} was fenced off, stepping down")
                self.token = None
        if self.token is not None:
            yield ("rpc", "lock", {"op": "release", "token": self.token}, RPC_TIMEOUT)
        self.finished = True

    # ---- given: the coroutine plumbing -----------------------------------------
    def _resume(self, value):
        try:
            req = self.gen.send(value)
        except StopIteration:
            self.finished = True
            return
        if req[0] == "sleep":
            self.sim.schedule(req[1], lambda: self._resume(None))
        else:
            _, dst, msg, timeout = req
            self.rid += 1
            rid = self.waiting = self.rid
            self.sim.send(self.name, dst, dict(msg, rid=rid))

            def expire():
                if self.waiting == rid:
                    self.waiting = None
                    self._resume(None)
            self.sim.schedule(timeout, expire)

    def on_message(self, src, msg):
        if msg["rid"] == self.waiting:
            self.waiting = None
            self._resume(msg)


# =============================================================================
# MILESTONE 1: the lock service
# =============================================================================
class LockService:
    """A lease-based lock with fencing tokens. Pure logic on explicit time: every
    method receives `now`, the server's clock reading, and never looks at a real clock.

    State to keep (names are used by the checker):
        self.holder   client id holding the lease, or None
        self.token    token of the current lease (0 before the first grant)
        self.expires  the time at which that lease runs out
        self.last_token  the highest token ever issued
    A lease granted at time t with length L is valid for  t <= now < t + L.
    """

    def __init__(self, lease_ms):
        self.lease_ms = lease_ms
        self.holder = None
        self.token = 0
        self.expires = 0
        self.last_token = 0

    def held(self, now):
        """True while somebody's lease is still valid at `now` (given)."""
        return self.holder is not None and now < self.expires

    def acquire(self, client, now):
        """Grant the lock if it is free or its lease has expired. Hand out a NEW token,
        strictly greater than every token issued before, even when the same client
        asks again. Set expires = now + lease_ms. Return the token, or None if the
        lock is held (by anyone, including the caller: it should renew instead)."""
        raise NotImplementedError("TODO milestone 1: LockService.acquire")

    def renew(self, client, token, now):
        """Extend the lease to now + lease_ms and return True, but only if `client`
        holds `token` AND the lease is still valid at `now`. An expired lease cannot
        be renewed, even if nobody else has taken the lock since. Otherwise False."""
        raise NotImplementedError("TODO milestone 1: LockService.renew")

    def release(self, client, token, now):
        """Give the lock up early (holder and token must match and be valid).
        Return True if it was released. The token counter is NOT reset."""
        raise NotImplementedError("TODO milestone 1: LockService.release")


# =============================================================================
# MILESTONES 2 AND 3: the storage and its fence
# =============================================================================
class FenceGuard:
    """Remembers the highest token seen so far (milestone 3)."""

    def __init__(self):
        self.max_seen = 0

    def admit(self, token):
        """Return False if `token` is lower than the highest token seen so far.
        Otherwise remember it as the new highest (equal is fine: the same holder
        keeps writing) and return True."""
        raise NotImplementedError("TODO milestone 3: FenceGuard.admit")


class Storage:
    """A single counter. read(token) -> (ok, value); write(token, value) -> ok.

    Milestone 2: store whatever arrives and always say yes (fenced=False).
    Milestone 3: when self.fenced, ask self.guard.admit(token) first, for reads AND
    writes; a refused request changes nothing and returns False / (False, None).
    The check and the update happen in one step, there is no gap to sneak through."""

    def __init__(self, fenced=False):
        self.fenced = fenced
        self.guard = FenceGuard()
        self.value = 0

    def read(self, token):
        raise NotImplementedError("TODO milestone 2: Storage.read (milestone 3 adds the fence)")

    def write(self, token, value):
        raise NotImplementedError("TODO milestone 2: Storage.write (milestone 3 adds the fence)")


# =============================================================================
# MILESTONE 4: the client-side safety margin
# =============================================================================
def safety_margin(lease_ms, rho, max_delay_ms):
    """How much of the lease a client should refuse to rely on, in ms.

    rho is the drift bound: any clock's rate is within a factor (1 +/- rho) of true
    time. The holder times the lease from the moment it SENT the request, so the
    worst case is a slow client clock against a fast server clock, which costs
        2 * rho * lease_ms / (1 + rho)
    on top of that, a write that passes the lease check still needs up to
    max_delay_ms to reach the storage; only (1 - rho) of it counts. Return the sum
    rounded UP to a whole millisecond."""
    raise NotImplementedError("TODO milestone 4: safety_margin")


# =============================================================================
# MILESTONE 5: a leader's log
# =============================================================================
class FencedLog:
    """The log a leader appends to. The leader's TERM is its fencing token.

    read(term)        -> (ok, length of the log); the new leader's first read announces its term
    write(term, entry) -> ok; appends (term, entry) to self.entries

    With fenced=True, reads and appends use self.guard.admit(term), so a deposed
    leader's append is refused no matter how late it arrives. (This is what Raft
    followers do with a stale term, in four lines.)"""

    def __init__(self, fenced=False):
        self.fenced = fenced
        self.guard = FenceGuard()
        self.entries = []

    def read(self, term):
        raise NotImplementedError("TODO milestone 5: FencedLog.read")

    def write(self, term, entry):
        raise NotImplementedError("TODO milestone 5: FencedLog.write")

    @property
    def value(self):
        return len(self.entries)


# =============================================================================
# GIVEN: putting a world together
# =============================================================================
class World:
    def __init__(self, sim, lock_node, store_node, clients, kind):
        self.sim, self.lock, self.store, self.clients, self.kind = sim, lock_node, store_node, clients, kind

    def run(self, limit=400000):
        self.sim.run(limit, stop=lambda: all(c.finished for c in self.clients))
        return self

    def finished(self):
        return all(c.finished for c in self.clients)

    def corrupted(self):
        """None if the storage looks right, else a sentence saying what is wrong."""
        s = self.store
        if self.kind == "counter":
            if s.storage.value != s.acked:
                return (f"LOST UPDATE: the counter ends at {s.storage.value}, but the storage acknowledged "
                        f"{s.acked} increments ({s.acked - s.storage.value} were overwritten)")
            return None
        entries = s.storage.entries
        ids = [e for _, e in entries]
        if ids != sorted(set(ids)) or ids != list(range(1, len(ids) + 1)):
            return f"BAD LOG: entry numbers are {ids} (expected 1, 2, 3, ... each exactly once)"
        terms = [t for t, _ in entries]
        if terms != sorted(terms):
            return f"BAD LOG: terms go backwards in the log: {terms}"
        return None

    def timeline(self, limit=40):
        lines = [f"  t={t:6d}  {text}" for t, text in self.sim.trace]
        return "\n".join(lines[:limit] + (["  ..."] if len(lines) > limit else []))


def build_world(seed, fenced=False, clients=3, jobs=3, lease_ms=1000, margin=0, rho=0.0,
                slow_p=0.0, slow_max=0, pause_p=0.0, pause_max=0, script=None, starts=None,
                delay=(2, 20), work=20, store="counter", renew=True):
    """Build a cluster. `jobs` may be an int or {"c0": 5, ...}; `script` maps a client
    name to {"after_check": [1300]} (a scripted freeze); `starts` maps a name to a
    start time; `renew=False` makes clients re-acquire instead of renewing; `rho` > 0 gives every node a clock that runs 100*rho % fast or slow."""
    sim = Sim(seed, delay=delay, slow_p=slow_p, slow_max=slow_max)
    names = [f"c{i}" for i in range(clients)]
    if rho:
        for who in ["lock"] + names:
            sim.drift[who] = sim.rng.choice((-rho, rho))
    lock_node = LockNode(sim, LockService(lease_ms))
    storage = Storage(fenced=fenced) if store == "counter" else FencedLog(fenced=fenced)
    store_node = StorageNode(sim, storage, lock_node)
    members = []
    for name in names:
        n_jobs = jobs[name] if isinstance(jobs, dict) else jobs
        members.append(Client(sim, name, n_jobs, margin=margin, script=(script or {}).get(name),
                              pause_p=pause_p, pause_max=pause_max, work=work,
                              start_at=(starts or {}).get(name, sim.rng.randint(0, 30)), renew=renew))
    return World(sim, lock_node, store_node, members, store)
