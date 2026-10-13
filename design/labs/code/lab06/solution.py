"""Lab 6: A Durable Job Scheduler.

A job store that survives crashes (a log-backed dict), a due-time index, workers that claim jobs with
leases and fencing tokens, retries with exponential backoff and jitter, a dead-letter queue, an effect
ledger that makes duplicate executions harmless, and cron with a leader lease. Everything runs inside
one process on SIMULATED time and a SIMULATED disk: no sleeping, no threads, no files. Every random draw
comes from a seeded random.Random, so a failing seed replays exactly.

Layout:
  * Disk, Crash, Bank, LeaseService, run_chaos, run_cron      given: the simulated world
  * milestone 1  encode_record, decode_record, LogDict, DueIndex, JobStore.submit / get / ready
  * milestone 2  JobStore.claim / heartbeat / complete   (leases and fencing tokens)
  * milestone 3  backoff_delay, JobStore.fail / dead_letters / redrive, poison jobs
  * milestone 4  EffectLedger.apply_once, Bank.deposit, handle_deposit
  * milestone 5  cron_jitter, fire_times, JobStore.fire_cron, CronReplica
"""
import hashlib
import heapq
import json
import random
import zlib


# ------------------------------------------------------------------------------------
# The simulated world (given)
# ------------------------------------------------------------------------------------
class Crash(Exception):
    """Raised by a Disk when the machine 'loses power' in the middle of an operation."""


class StoreDown(Exception):
    """What a caller sees when the store crashed during (or just after) its call: the outcome is unknown."""


class Disk:
    """An append-only file of text lines with an OS cache in front of it.

    append(line)   puts a line in the cache (NOT durable)
    fsync()        makes everything appended so far durable
    read_all()     the durable lines, in order (what a restarted process sees)
    truncate(n)    keep only the first n durable lines (recovery uses this to cut off a torn tail)
    crash(rng)     power loss: the cache is lost, except that a random prefix of it may have reached the
                   platter, possibly ending in a half-written (torn) line
    fail_at        if set to n, the n-th append/fsync from now raises Crash before doing anything
    """

    def __init__(self):
        self.durable, self.cache, self.fail_at = [], [], None

    def _tick(self):
        if self.fail_at is not None:
            self.fail_at -= 1
            if self.fail_at <= 0:
                self.fail_at = None
                raise Crash()

    def append(self, line):
        self._tick()
        self.cache.append(line)

    def fsync(self):
        self._tick()
        self.durable += self.cache
        self.cache = []

    def read_all(self):
        return list(self.durable)

    def truncate(self, n):
        del self.durable[n:]

    def crash(self, rng):
        keep = rng.randrange(len(self.cache) + 1)
        self.durable += self.cache[:keep]
        if keep < len(self.cache) and rng.random() < 0.5:
            line = self.cache[keep]
            self.durable.append(line[:rng.randrange(1, max(2, len(line)))])
        self.cache, self.fail_at = [], None


# ------------------------------------------------------------------------------------
# Milestone 1: a log-backed dict, a due-time index, a durable job store
# ------------------------------------------------------------------------------------
def encode_record(rec):
    """One log line for a record (a JSON-serialisable dict): '<crc32 as 8 hex digits> <json>'. Use
    json.dumps(rec, sort_keys=True, separators=(',', ':')) for the body and zlib.crc32 of its UTF-8 bytes."""
    body = json.dumps(rec, sort_keys=True, separators=(",", ":"))
    return f"{zlib.crc32(body.encode()):08x} {body}"


def decode_record(line):
    """The record, or None if the line is damaged (truncated, wrong checksum, not JSON). A torn write
    must never be mistaken for a record."""
    if len(line) < 10 or line[8] != " ":
        return None
    crc, body = line[:8], line[9:]
    try:
        if f"{zlib.crc32(body.encode()):08x}" != crc:
            return None
        return json.loads(body)
    except ValueError:
        return None


class LogDict:
    """A dict whose every change is first written to a Disk as one atomic record.

    A record is {"set": {key: value, ...}, "del": [key, ...]}; it is applied to the in-memory dict only
    AFTER it has been appended and fsynced, so whatever a caller was told succeeded survives a crash.
    Keys are strings, values JSON-serialisable.
    """

    def __init__(self, disk):
        self.disk = disk
        self.data = {}
        self._recover()

    def _recover(self):
        """Replay the durable lines in order. At the first damaged line stop and truncate the disk there
        (self.disk.truncate(n)), so that later appends do not follow garbage."""
        good = 0
        for line in self.disk.read_all():
            rec = decode_record(line)
            if rec is None:
                break
            self._apply(rec)
            good += 1
        self.disk.truncate(good)

    def _apply(self, rec):
        for k, v in rec.get("set", {}).items():
            self.data[k] = v
        for k in rec.get("del", []):
            self.data.pop(k, None)

    def put_many(self, sets=None, deletes=()):
        """Atomically set and delete several keys: ONE record, then fsync, then apply to memory."""
        rec = {"set": dict(sets or {}), "del": list(deletes)}
        self.disk.append(encode_record(rec))
        self.disk.fsync()
        self._apply(json.loads(json.dumps(rec)))

    def put(self, key, value):
        self.put_many({key: value})

    def delete(self, key):
        self.put_many({}, [key])

    def get(self, key, default=None):
        return self.data.get(key, default)

    def __contains__(self, key):
        return key in self.data

    def items(self):
        return sorted(self.data.items())


class DueIndex:
    """When does each job next become claimable? A min-heap of (ready_at, job_id) with lazy invalidation.

    add(job_id, t) sets (or replaces) the job's ready time; discard removes it; pop_ready(now) removes and
    returns the job with the smallest (ready_at, job_id) whose ready_at <= now (None if there is none).
    Re-adding a job leaves a STALE heap entry behind: an entry is stale unless self.at[job_id] equals its time.
    """

    def __init__(self):
        self.heap = []
        self.at = {}

    def add(self, job_id, t):
        self.at[job_id] = t
        heapq.heappush(self.heap, (t, job_id))
        if len(self.heap) > 4 * len(self.at) + 64:                 # drop stale entries now and then
            self.heap = [(tt, j) for j, tt in self.at.items()]
            heapq.heapify(self.heap)

    def discard(self, job_id):
        self.at.pop(job_id, None)

    def pop_ready(self, now):
        while self.heap:
            t, j = self.heap[0]
            if self.at.get(j) != t:
                heapq.heappop(self.heap)
                continue
            if t > now:
                return None
            heapq.heappop(self.heap)
            del self.at[j]
            return j
        return None

    def ready(self, now):
        """All job ids with ready_at <= now, in (ready_at, id) order, without removing them."""
        return [j for t, j in sorted((t, j) for j, t in self.at.items() if t <= now)]

    def __len__(self):
        return len(self.at)


def ready_at(rec):
    """When may this job be claimed? A queued job: at its due time. A running job: when its lease expires.
    Finished jobs (done, dead): never (None). Given."""
    if rec["state"] == "queued":
        return rec["due"]
    if rec["state"] == "running":
        return rec["lease_until"]
    return None


class JobStore:
    """The durable job table. Every method is one atomic, durable step; `now` is passed in (simulated time)."""

    def __init__(self, disk, seed=0):
        self.db = LogDict(disk)
        self.seed = seed
        self.index = DueIndex()
        for key, rec in self.db.items():            # rebuild the in-memory index from the durable table
            if key.startswith("job:"):
                self._reindex(rec)

    def _reindex(self, rec):
        t = ready_at(rec)
        if t is None:
            self.index.discard(rec["id"])
        else:
            self.index.add(rec["id"], t)

    def _save(self, rec):
        self.db.put("job:" + rec["id"], rec)
        self._reindex(rec)

    def get(self, job_id):
        """A copy of the job record, or None."""
        rec = self.db.get("job:" + job_id)
        return dict(rec) if rec is not None else None

    def submit(self, job_id, due, payload=None, max_attempts=5, base=1.0, cap=60.0, key=None):
        """Create a queued job. Idempotent: if job_id exists, change nothing and return False; else True.
        The record has: id, key (the stable run key, default job_id), payload, due, state='queued',
        attempts=0, fence=0, lease_until=0.0, owner=None, max_attempts, base, cap, error=None."""
        if self.db.get("job:" + job_id) is not None:
            return False
        self._save({"id": job_id, "key": key or job_id, "payload": payload, "due": due, "state": "queued",
                    "attempts": 0, "fence": 0, "lease_until": 0.0, "owner": None,
                    "max_attempts": max_attempts, "base": base, "cap": cap, "error": None})
        return True

    def ready(self, now):
        """Ids of jobs claimable at `now`, in (ready time, id) order. Does not claim anything."""
        return self.index.ready(now)

    # ---------------------------------------------------------------- milestone 2
    def claim(self, now, worker, lease_s):
        """Hand the earliest claimable job to `worker` and return a copy of its record, or None.

        Claimable: queued with due <= now, or running with lease_until <= now (its worker presumably died).
        Take the earliest by (ready time, id) from the index. Then, in ONE durable write: state='running',
        owner=worker, lease_until=now + lease_s, fence += 1 (a strictly increasing fencing token), attempts += 1.
        (Milestone 3 adds the poison-job rule here.)"""
        while True:
            jid = self.index.pop_ready(now)
            if jid is None:
                return None
            rec = self.get(jid)
            if rec is None or ready_at(rec) is None or ready_at(rec) > now:
                continue
            if rec["state"] == "running" and rec["attempts"] >= rec["max_attempts"]:
                # a poison job: every worker that took it died. Stop feeding it to workers.
                rec.update(state="dead", owner=None, error="lease expired after max_attempts claims")
                self._save(rec)
                continue
            rec.update(state="running", owner=worker, lease_until=now + lease_s,
                       fence=rec["fence"] + 1, attempts=rec["attempts"] + 1)
            self._save(rec)
            return dict(rec)

    def heartbeat(self, job_id, fence, now, lease_s):
        """Extend the lease to now + lease_s. True only if the job is running and `fence` is the current one."""
        rec = self.get(job_id)
        if rec is None or rec["state"] != "running" or rec["fence"] != fence:
            return False
        rec["lease_until"] = now + lease_s
        self._save(rec)
        return True

    def complete(self, job_id, fence):
        """Mark the job done. True only if it is running and `fence` is the current one. A worker whose lease
        expired and whose job was re-claimed has an old fence and is refused."""
        rec = self.get(job_id)
        if rec is None or rec["state"] != "running" or rec["fence"] != fence:
            return False
        rec.update(state="done", owner=None)
        self._save(rec)
        return True

    # ---------------------------------------------------------------- milestone 3
    def jitter(self, job_id, attempt):
        """A deterministic 'random' number in [0, 1) for (job, attempt): the same after a restart (given)."""
        h = hashlib.blake2b(f"{self.seed}:{job_id}:{attempt}".encode(), digest_size=8).digest()
        return int.from_bytes(h, "big") / 2.0 ** 64

    def fail(self, job_id, fence, now, error, retryable=True):
        """The worker reports that the handler failed. Returns 'fenced' (not the current fence, or not running:
        nothing changes), 'dead' (not retryable, or attempts >= max_attempts: state='dead', error kept) or
        'retry' (state='queued', owner=None, due = now + backoff_delay(attempts, base, cap, jitter(job, attempts)))."""
        rec = self.get(job_id)
        if rec is None or rec["state"] != "running" or rec["fence"] != fence:
            return "fenced"
        rec["error"] = error
        rec["owner"] = None
        if not retryable or rec["attempts"] >= rec["max_attempts"]:
            rec["state"] = "dead"
            self._save(rec)
            return "dead"
        rec["state"] = "queued"
        rec["due"] = now + backoff_delay(rec["attempts"], rec["base"], rec["cap"], self.jitter(job_id, rec["attempts"]))
        self._save(rec)
        return "retry"

    def dead_letters(self):
        """Ids of dead jobs, sorted."""
        return sorted(k[4:] for k, r in self.db.items() if k.startswith("job:") and r["state"] == "dead")

    def redrive(self, job_id, now):
        """Put a dead job back in the queue (attempts=0, error=None, due=now). True if it was dead."""
        rec = self.get(job_id)
        if rec is None or rec["state"] != "dead":
            return False
        rec.update(state="queued", attempts=0, error=None, due=now, owner=None)
        self._save(rec)
        return True

    # ---------------------------------------------------------------- milestone 5
    def cursor(self, cron_id, default):
        """The last scheduled fire time that has been turned into a job for this cron (given)."""
        return self.db.get("cursor:" + cron_id, default)

    def fire_cron(self, cron_id, fire_t, due, payload, token):
        """Create the job for ONE scheduled firing of a cron, exactly once. Returns 'fenced', 'duplicate' or 'created'.

        token is the fencing token of the leader lease. The store remembers the highest token it has seen under
        'meta:cron_token'. A token below it is a leader that has been replaced: return 'fenced' and change nothing.
        The job id is f"{cron_id}@{fire_t}": if that job already exists return 'duplicate'. Otherwise create the job
        (like submit, with key = the job id), move the cursor 'cursor:<cron_id>' to fire_t and record the token, all
        in ONE put_many, so a crash cannot leave a job without its cursor or a cursor without its job."""
        if token < self.db.get("meta:cron_token", 0):
            return "fenced"
        jid = f"{cron_id}@{fire_t}"
        if self.db.get("job:" + jid) is not None:
            return "duplicate"
        rec = {"id": jid, "key": jid, "payload": payload, "due": due, "state": "queued", "attempts": 0, "fence": 0,
               "lease_until": 0.0, "owner": None, "max_attempts": 5, "base": 1.0, "cap": 60.0, "error": None}
        self.db.put_many({"job:" + jid: rec, "cursor:" + cron_id: fire_t, "meta:cron_token": token})
        self._reindex(rec)
        return "created"


def backoff_delay(attempt, base, cap, u):
    """Exponential backoff with FULL jitter: a uniformly random delay in [0, min(cap, base * 2**(attempt - 1))],
    where `u` in [0, 1) is the random draw. attempt is 1 after the first failure."""
    return u * min(cap, base * 2.0 ** (attempt - 1))


# ------------------------------------------------------------------------------------
# Milestone 4: effects exactly once
# ------------------------------------------------------------------------------------
class EffectLedger:
    """Turns at-least-once execution into effectively-once EFFECTS. The ledger and the effect live in the same
    LogDict, so one atomic record can contain both."""

    def __init__(self, db):
        self.db = db

    def done(self, key):
        return ("ledger:" + key) in self.db

    def apply_once(self, key, writes):
        """If `key` is not in the ledger: in ONE put_many write `writes` (a dict of key -> value) plus the ledger
        entry 'ledger:<key>', and return True. If it is already there: change nothing and return False."""
        if self.done(key):
            return False
        sets = dict(writes)
        sets["ledger:" + key] = 1
        self.db.put_many(sets)
        return True


class Bank:
    """The outside world: a durable account table on its own disk (given, apart from deposit)."""

    def __init__(self, disk):
        self.db = LogDict(disk)
        self.ledger = EffectLedger(self.db)

    def balance(self, acct):
        return self.db.get("bal:" + acct, 0)

    def deposit_raw(self, acct, amount):
        """A non-idempotent deposit: running it twice pays twice (given; this is the bug the ledger prevents)."""
        self.db.put("bal:" + acct, self.balance(acct) + amount)

    def deposit(self, key, acct, amount):
        """Deposit `amount` into `acct` at most once per `key`: use the ledger so that the new balance and the
        ledger entry are written atomically. Returns True if this call paid, False if `key` had already paid."""
        return self.ledger.apply_once(key, {"bal:" + acct: self.balance(acct) + amount})


def handle_deposit(job, bank):
    """The job handler. job['payload'] = {'acct': ..., 'amount': ...}. Make the effect idempotent with a key that
    is the same on every attempt of the same job (NOT one that includes job['attempts'] or the worker)."""
    p = job["payload"]
    return bank.deposit(job["key"], p["acct"], p["amount"])


def handle_deposit_unsafe(job, bank):
    """Given: no protection at all."""
    p = job["payload"]
    bank.deposit_raw(p["acct"], p["amount"])
    return True


def handle_deposit_attempt_key(job, bank):
    """Given: a ledger, but keyed by job AND attempt: every retry looks like a new job."""
    p = job["payload"]
    return bank.deposit(f"{job['key']}#{job['attempts']}", p["acct"], p["amount"])


# ------------------------------------------------------------------------------------
# The chaos harness (given): workers that crash, stall and run jobs twice; a store that loses power
# ------------------------------------------------------------------------------------
class Transient(Exception):
    pass


class Permanent(Exception):
    pass


def run_chaos(seed, handler, n_jobs=12, n_workers=3, chaos=True, special=(), lease=3.0, t_chaos=60.0, t_end=300.0):
    """Run n_jobs deposit jobs through n_workers workers on simulated time, with faults until t_chaos and none after.

    Faults: a worker dies before running the handler, or after the effect but before complete(); a worker freezes
    (a long GC pause) for longer than its lease and then carries on as if nothing happened (a stale worker: it
    runs the handler AGAIN and tries to complete with an old fence); the job store or the bank loses power in the
    middle of a call (the caller gets StoreDown and does not know whether it happened); a few jobs are flaky.
    `special` may contain 'poison' (a job that kills every worker that runs it) and 'permanent' (a job whose handler
    raises Permanent). Returns a dict with the final store, the bank, the job specs and an event log."""
    rng = random.Random(seed)
    sdisk, bdisk = Disk(), Disk()
    S = {"store": JobStore(sdisk, seed), "bank": Bank(bdisk)}
    log, events, seqn = [], [], [0]
    specs = {}
    for i in range(n_jobs):
        jid = f"j{i}"
        specs[jid] = {"acct": f"acct{i % 4}", "amount": rng.randrange(1, 100)}
        S["store"].submit(jid, round(rng.uniform(0, 20), 3), dict(specs[jid]), max_attempts=10, base=0.5, cap=8.0)
    bad = {}
    for nm in special:
        jid = f"x-{nm}"
        specs[jid] = {"acct": "acctX", "amount": 1}
        bad[jid] = nm
        S["store"].submit(jid, 1.0, dict(specs[jid]), max_attempts=4, base=0.5, cap=4.0)
    flaky = {f"j{i}" for i in range(n_jobs) if rng.random() < 0.25}

    def at(t, fn, *a):
        seqn[0] += 1
        heapq.heappush(events, (t, seqn[0], fn, a))

    def faulty(t):
        return chaos and t < t_chaos

    def store_call(t, name, *a):
        st = S["store"]
        crash_inside = faulty(t) and rng.random() < 0.08
        if crash_inside:
            sdisk.fail_at = rng.randrange(1, 4)
        try:
            r = getattr(st, name)(*a)
            sdisk.fail_at = None
            if faulty(t) and rng.random() < 0.02:               # power loss right after the call: durable, ack lost
                raise Crash()
            return r
        except Crash:
            sdisk.fail_at = None
            sdisk.crash(rng)
            S["store"] = JobStore(sdisk, seed)
            log.append((t, "store-crash", None, None, None))
            raise StoreDown()

    class W:
        pass

    workers = []
    for n in range(n_workers):
        w = W()
        w.name, w.epoch, w.frozen, w.job, w.tries = f"w{n}", 0, 0.0, None, 0
        workers.append(w)

    def guard(fn):
        def wrapped(t, w, epoch, *a):
            if epoch != w.epoch:
                return
            if t < w.frozen:                                    # the process is frozen: nothing runs until it thaws
                at(w.frozen, wrapped, w, epoch, *a)
                return
            fn(t, w, epoch, *a)
        return wrapped

    def die(t, w, why):
        log.append((t, "worker-dies", w.job["id"] if w.job else None, w.job["fence"] if w.job else None, why))
        w.epoch += 1
        w.job = None
        at(t + rng.uniform(1.0, 3.0), poll, w, w.epoch)

    @guard
    def poll(t, w, epoch):
        try:
            rec = store_call(t, "claim", t, w.name, lease)
        except StoreDown:
            at(t + 1.0, poll, w, epoch)
            return
        if rec is None:
            at(t + 0.5 + rng.random() * 0.5, poll, w, epoch)
            return
        w.job, w.tries = rec, 0
        log.append((t, "claim", rec["id"], rec["fence"], rec["lease_until"]))
        at(t + lease / 3, beat, w, epoch, rec["fence"])
        at(t + rng.uniform(0.2, 1.5), run, w, epoch, rec["fence"])

    @guard
    def beat(t, w, epoch, fence):
        if w.job is None or w.job["fence"] != fence:
            return
        try:
            ok = store_call(t, "heartbeat", w.job["id"], fence, t, lease)
        except StoreDown:
            ok = None
        if ok is True:
            log.append((t, "heartbeat", w.job["id"], fence, t + lease))
        if ok is False:
            log.append((t, "fenced", w.job["id"], fence, "heartbeat"))
            w.job = None
            at(t + 0.5, poll, w, epoch)
            return
        at(t + lease / 3, beat, w, epoch, fence)

    @guard
    def run(t, w, epoch, fence, stalled=False):
        job = w.job
        if job is None or job["fence"] != fence:
            return
        if not stalled and faulty(t) and rng.random() < 0.10:
            w.frozen = t + rng.uniform(1.5 * lease, 3 * lease)       # a pause longer than the lease
            log.append((t, "freeze", job["id"], fence, w.frozen))
            at(w.frozen, run, w, epoch, fence, True)
            return
        kind = bad.get(job["id"])
        if kind == "poison":
            die(t, w, "poison")
            return
        if faulty(t) and rng.random() < 0.05:
            die(t, w, "before-effect")
            return
        try:
            if kind == "permanent":
                raise Permanent("bad payload")
            if job["id"] in flaky and job["attempts"] <= 2 and rng.random() < 0.5:
                raise Transient("503")
            if faulty(t) and rng.random() < 0.05:
                bdisk.fail_at = rng.randrange(1, 3)
            try:
                handler(job, S["bank"])
                bdisk.fail_at = None
            except Crash:
                bdisk.fail_at = None
                bdisk.crash(rng)
                S["bank"] = Bank(bdisk)
                log.append((t, "bank-crash", job["id"], fence, None))
                raise Transient("bank went away")
        except (Transient, Permanent) as e:
            try:
                res = store_call(t, "fail", job["id"], fence, t, str(e), not isinstance(e, Permanent))
                log.append((t, "fail", job["id"], fence, res))
            except StoreDown:
                pass
            w.job = None
            at(t + 0.3, poll, w, epoch)
            return
        log.append((t, "exec", job["id"], job["attempts"], fence))
        if faulty(t) and rng.random() < 0.06:
            die(t, w, "after-effect")
            return
        at(t + rng.uniform(0.05, 0.3), finish, w, epoch, fence)

    @guard
    def finish(t, w, epoch, fence):
        job = w.job
        if job is None or job["fence"] != fence:
            return
        try:
            ok = store_call(t, "complete", job["id"], fence)
        except StoreDown:
            w.tries += 1
            if w.tries < 3:
                at(t + 0.5, finish, w, epoch, fence)
                return
            ok = None
        log.append((t, "complete", job["id"], fence, ok))
        w.job = None
        at(t + 0.2, poll, w, epoch)

    for w in workers:
        at(rng.uniform(0, 1), poll, w, w.epoch)
    t = 0.0
    while events:
        t, _, fn, a = heapq.heappop(events)
        if t > t_end:
            break
        fn(t, *a)
        if (t > t_chaos or not chaos) and all((S["store"].get(j) or {"state": "x"})["state"] in ("done", "dead") for j in specs):
            break
    return {"store": S["store"], "bank": S["bank"], "specs": specs, "log": log, "bad": bad, "end": t}


# ------------------------------------------------------------------------------------
# Milestone 5: cron with a leader lease
# ------------------------------------------------------------------------------------
class LeaseService:
    """A tiny etcd-like lock service (given). acquire(who, now, ttl) returns a fencing TOKEN if `who` now holds the
    lease (a new holder gets token + 1; the current holder renewing keeps its token), else None."""

    def __init__(self):
        self.holder, self.expires, self.token = None, 0.0, 0

    def acquire(self, who, now, ttl):
        if self.holder == who and now < self.expires:
            self.expires = now + ttl
            return self.token
        if self.holder is None or now >= self.expires:
            self.holder, self.expires = who, now + ttl
            self.token += 1
            return self.token
        return None


def cron_jitter(cron_id, spread_s):
    """A STABLE offset in [0, spread_s) for a cron: the same every period, different between crons, so a herd of
    crons that all say '0 * * * *' is spread over `spread_s` seconds instead of starting in the same second.
    Hash the id (hashlib.blake2b) and scale. Returns 0.0 when spread_s is 0."""
    if spread_s <= 0:
        return 0.0
    h = hashlib.blake2b(cron_id.encode(), digest_size=8).digest()
    return int.from_bytes(h, "big") / 2.0 ** 64 * spread_s


def fire_times(period, offset, after, upto):
    """The scheduled fire times offset + k * period (k an integer) with after < t <= upto, ascending."""
    import math
    k = math.floor((after - offset) / period) + 1
    out = []
    while offset + k * period <= upto:
        t = offset + k * period
        if t > after:
            out.append(t)
        k += 1
    return out


class CronReplica:
    """One of several scheduler replicas. Only the replica holding the lease fires crons (efficiency); the store's
    unique job id and fencing check make a mistaken second firer harmless (safety)."""

    def __init__(self, name, lease, store, crons, spread=0.0, ttl=6.0, max_catchup=1000):
        self.name, self.lease, self.store = name, lease, store
        self.crons, self.spread, self.ttl, self.max_catchup = crons, spread, ttl, max_catchup
        self.created = 0

    def tick(self, now):
        """Called every second or so. Renew or try to take the lease; if we hold it, fire_due(now, token)."""
        token = self.lease.acquire(self.name, now, self.ttl)
        if token is None:
            return 0
        return self.fire_due(now, token)

    def fire_due(self, now, token, stale_cursors=None):
        """(`stale_cursors`, if given, replaces the store's cursors: a zombie leader that read them long ago.)
        For each cron {'id', 'period', 'offset', 'start'}: starting after the store's cursor (default start - 1e-6),
        take every scheduled fire time <= now (at most max_catchup of them: a leader that was away catches up on
        what it missed, once per period) and call store.fire_cron(id, t, t + cron_jitter(id, spread), payload, token).
        Stop at once if the store answers 'fenced'. Return how many jobs this call created."""
        made = 0
        for c in self.crons:
            after = (stale_cursors or {}).get(c["id"], c["start"] - 1e-6) if stale_cursors is not None else self.store.cursor(c["id"], c["start"] - 1e-6)
            for t in fire_times(c["period"], c["offset"], after, now)[:self.max_catchup]:
                r = self.store.fire_cron(c["id"], t, t + cron_jitter(c["id"], self.spread), {"cron": c["id"], "t": t}, token)
                if r == "fenced":
                    return made
                if r == "created":
                    made += 1
                    self.created += 1
        return made


def run_cron(seed, n_replicas=3, horizon=600.0, spread=0.0, chaos=True):
    """Three scheduler replicas ticking about once a second against one lease service and one job store, for
    `horizon` simulated seconds, with replicas that crash for a while, replicas that freeze mid-tick and fire
    LATE with an old token (zombie leaders), and a store that loses power. Returns the store, the crons and a log."""
    rng = random.Random(seed)
    disk = Disk()
    store = JobStore(disk, seed)
    lease = LeaseService()
    crons = [{"id": "c-fast", "period": 20.0, "offset": 3.0, "start": 0.0},
             {"id": "c-mid", "period": 30.0, "offset": 0.0, "start": 0.0},
             {"id": "c-slow", "period": 60.0, "offset": 10.0, "start": 15.0},
             {"id": "c-late", "period": 45.0, "offset": 7.0, "start": 100.0}]
    reps = [CronReplica(f"r{i}", lease, store, crons, spread=spread) for i in range(n_replicas)]
    down_until = [0.0] * n_replicas
    log = []
    sched = []
    for i in range(n_replicas):
        sched.append((rng.random() * 2, i))
    heapq.heapify(sched)
    zombies = []                                              # (fire_at, replica, stale_now, stale_token, stale_cursors)
    while sched:
        t, i = heapq.heappop(sched)
        if t > horizon:
            break
        while zombies and zombies[0][0] <= t:
            _, zi, znow, ztok, zsnap = heapq.heappop(zombies)
            made = reps[zi].fire_due(znow, ztok, zsnap)
            log.append((t, "zombie", reps[zi].name, ztok, made))
        r = reps[i]
        if t >= down_until[i]:
            fault = rng.random() if chaos else 1.0
            if fault < 0.02:
                down_until[i] = t + rng.uniform(5, 20)
                log.append((t, "crash", r.name, None, None))
            else:
                if fault < 0.05 and lease.holder == r.name:
                    snap = {c["id"]: store.cursor(c["id"], c["start"] - 1e-6) for c in crons}
                    zombies.append((t + rng.uniform(8, 14), i, t, lease.token, snap))      # freeze: wake up much later with a stale view
                    heapq.heapify(zombies)
                    log.append((t, "freeze", r.name, lease.token, None))
                if chaos and rng.random() < 0.03:
                    disk.fail_at = rng.randrange(1, 4)
                try:
                    made = r.tick(t)
                    disk.fail_at = None
                    log.append((t, "tick", r.name, lease.token, made))
                except Crash:
                    disk.fail_at = None
                    disk.crash(rng)
                    store = JobStore(disk, seed)
                    for rr in reps:
                        rr.store = store
                    log.append((t, "store-crash", r.name, None, None))
        heapq.heappush(sched, (t + 1.0 + rng.uniform(-0.1, 0.1), i))
    return {"store": store, "crons": crons, "log": log, "horizon": horizon, "replicas": reps, "lease": lease}
