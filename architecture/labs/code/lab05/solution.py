"""Lab 5 solution: event sourcing and CQRS for bank accounts.

Write side: an append-only event store in sqlite with optimistic concurrency, and an
Account aggregate that is rebuilt by folding its events. Read side: a Projector that
turns the global event log into query tables and remembers how far it has read.
Plus snapshots, temporal queries and upcasting of old event shapes.

Everything is standard library and deterministic: no network, no real clocks in the
checks (the store takes an injectable clock).

Money is always integer cents.
"""
import json
import sqlite3
import time
from collections import namedtuple
from decimal import Decimal

LARGE_CENTS = 100_000           # a deposit or withdrawal of $1,000.00 or more is "large"

# One stored event. `seq` is the position in the global log, `version` the position in its stream.
Event = namedtuple("Event", "seq stream_id version type data recorded_at")


class ConcurrencyError(Exception):
    """append() was given a stale expected_version: someone else wrote to the stream first."""


class DomainError(Exception):
    """A command was refused because it would break a business rule."""


class AccountNotOpen(DomainError):
    pass


class AlreadyOpen(DomainError):
    pass


class InsufficientFunds(DomainError):
    pass


class InvalidAmount(DomainError):
    pass


# ======================================================================================
# Milestone 1: the event store
# ======================================================================================
class EventStore:
    def __init__(self, path=":memory:", clock=time.time):
        self.path = path
        self.clock = clock                      # recorded_at comes from here, so tests can fake time
        self.events_read = 0                    # how many events read_stream has returned (used by milestone 4)
        # isolation_level=None: we issue BEGIN/COMMIT ourselves. timeout: wait for a competing writer.
        self.conn = sqlite3.connect(path, timeout=30, isolation_level=None, check_same_thread=False)
        self._init_schema()

    def _init_schema(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                seq         INTEGER PRIMARY KEY AUTOINCREMENT,   -- global order of the whole log
                stream_id   TEXT    NOT NULL,
                version     INTEGER NOT NULL,                    -- 1, 2, 3 ... within one stream
                type        TEXT    NOT NULL,
                data        TEXT    NOT NULL,                    -- JSON
                recorded_at REAL    NOT NULL,
                UNIQUE (stream_id, version)                      -- the last line of defence
            )""")

    def append(self, stream_id, expected_version, events):
        """Append [(type, data), ...] to a stream, but only if the stream is still at
        `expected_version` (0 for a stream that does not exist yet).
        Returns the stored Events. Raises ConcurrencyError if someone got there first;
        in that case nothing at all is written."""
        now = self.clock()
        try:
            self.conn.execute("BEGIN IMMEDIATE")        # take the write lock before looking
            try:
                row = self.conn.execute(
                    "SELECT COALESCE(MAX(version), 0) FROM events WHERE stream_id = ?", (stream_id,)).fetchone()
                if row[0] != expected_version:
                    raise ConcurrencyError("stream %r is at version %d, you expected %d"
                                           % (stream_id, row[0], expected_version))
                stored = []
                for i, (etype, data) in enumerate(events, start=1):
                    version = expected_version + i
                    cur = self.conn.execute(
                        "INSERT INTO events (stream_id, version, type, data, recorded_at) VALUES (?,?,?,?,?)",
                        (stream_id, version, etype, json.dumps(data, sort_keys=True), now))
                    stored.append(Event(cur.lastrowid, stream_id, version, etype, data, now))
                self.conn.execute("COMMIT")
                return stored
            except BaseException:
                self.conn.execute("ROLLBACK")
                raise
        except sqlite3.IntegrityError as e:             # the UNIQUE constraint caught a race we did not see
            raise ConcurrencyError("version already taken: %s" % e)

    def _upcast(self, ev):
        try:
            return upcast(ev)
        except NotImplementedError:                     # milestone 6 not done yet: pass events through
            return ev

    def _event(self, row):
        seq, stream_id, version, etype, data, recorded_at = row
        return self._upcast(Event(seq, stream_id, version, etype, json.loads(data), recorded_at))

    def read_stream(self, stream_id, after_version=0):
        """The events of one stream with version > after_version, oldest first."""
        rows = self.conn.execute(
            "SELECT seq, stream_id, version, type, data, recorded_at FROM events "
            "WHERE stream_id = ? AND version > ? ORDER BY version", (stream_id, after_version)).fetchall()
        self.events_read += len(rows)
        return [self._event(r) for r in rows]

    def read_all(self, after_seq=0, limit=None):
        """The global log: events with seq > after_seq, in seq order, at most `limit` of them."""
        sql = ("SELECT seq, stream_id, version, type, data, recorded_at FROM events "
               "WHERE seq > ? ORDER BY seq")
        args = [after_seq]
        if limit is not None:
            sql += " LIMIT ?"
            args.append(limit)
        return [self._event(r) for r in self.conn.execute(sql, args).fetchall()]


# ======================================================================================
# Milestone 2: the aggregate
# ======================================================================================
class Account:
    """The write-side model. It exists only to decide whether a command is allowed.
    Its state is never stored: it is the fold of the account's events."""

    def __init__(self, account_id):
        self.id = account_id
        self.version = 0            # version of the last event folded in
        self.opened = False
        self.owner = None
        self.balance = 0            # cents

    # --- the fold ---
    def apply(self, ev):
        """Fold one event into the state. Never validates: events are facts."""
        if ev.type == "AccountOpened":
            self.opened = True
            self.owner = ev.data["owner"]
        elif ev.type == "Deposited":
            self.balance += ev.data["amount_cents"]
        elif ev.type == "Withdrawn":
            self.balance -= ev.data["amount_cents"]
        self.version = ev.version

    @classmethod
    def load(cls, store, account_id):
        acct = cls(account_id)
        for ev in store.read_stream(account_id):
            acct.apply(ev)
        return acct

    # --- commands: validate against the current state, return events (do not apply them) ---
    def open(self, owner):
        if self.opened:
            raise AlreadyOpen("account %s is already open" % self.id)
        return [("AccountOpened", {"owner": owner})]

    def deposit(self, cents):
        self._need_open()
        self._need_positive(cents)
        return [("Deposited", {"v": 2, "amount_cents": cents})]

    def withdraw(self, cents):
        self._need_open()
        self._need_positive(cents)
        if cents > self.balance:
            raise InsufficientFunds("balance %d, tried to withdraw %d" % (self.balance, cents))
        return [("Withdrawn", {"amount_cents": cents})]

    def _need_open(self):
        if not self.opened:
            raise AccountNotOpen("account %s is not open" % self.id)

    @staticmethod
    def _need_positive(cents):
        if not isinstance(cents, int) or cents <= 0:
            raise InvalidAmount("amount must be a positive whole number of cents, got %r" % (cents,))

    # --- Milestone 4: state <-> JSON, for snapshots ---
    def to_state(self):
        return {"version": self.version, "opened": self.opened, "owner": self.owner, "balance": self.balance}

    @classmethod
    def from_state(cls, account_id, state):
        acct = cls(account_id)
        acct.version = state["version"]
        acct.opened = state["opened"]
        acct.owner = state["owner"]
        acct.balance = state["balance"]
        return acct


def execute(store, account_id, decide, snapshots=None, snapshot_every=None, retries=3):
    """Load the account, let `decide(account)` return new events, append them with
    optimistic concurrency. On ConcurrencyError, reload and decide again. (Given.)"""
    for attempt in range(retries):
        acct = load_account(store, account_id, snapshots)
        before = acct.version
        new = decide(acct)                       # may raise DomainError: nothing is written
        try:
            stored = store.append(account_id, acct.version, new)
        except ConcurrencyError:
            if attempt == retries - 1:
                raise
            continue
        for ev in stored:
            acct.apply(ev)
        if snapshots is not None and snapshot_every and acct.version // snapshot_every > before // snapshot_every:
            snapshots.save(acct)
        return stored


def load_account(store, account_id, snapshots=None):
    """Milestone 2: full replay. Milestone 4: start from the latest snapshot if there is one."""
    if snapshots is not None:
        snap = snapshots.latest(account_id)
        if snap is not None:
            version, state = snap
            acct = Account.from_state(account_id, state)
            for ev in store.read_stream(account_id, after_version=version):
                acct.apply(ev)
            return acct
    return Account.load(store, account_id)


# ======================================================================================
# Milestone 3: projections (the read side)
# ======================================================================================
class Projector:
    """Builds query tables from the global log. Owns its own database, separate from the
    event store, because in a real system it would be a different one."""

    NAME = "balances"

    def __init__(self, store, path=":memory:"):
        self.store = store
        self.db = sqlite3.connect(path, isolation_level=None)
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS account_balances (
                account_id    TEXT PRIMARY KEY,
                owner         TEXT,
                balance_cents INTEGER NOT NULL,
                last_seq      INTEGER NOT NULL);        -- last event applied to THIS row
            CREATE TABLE IF NOT EXISTS large_transactions (
                seq          INTEGER PRIMARY KEY,       -- the event's global seq: a natural dedupe key
                account_id   TEXT NOT NULL,
                kind         TEXT NOT NULL,
                amount_cents INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS projector_position (
                name     TEXT PRIMARY KEY,
                last_seq INTEGER NOT NULL);""")

    def position(self):
        row = self.db.execute("SELECT last_seq FROM projector_position WHERE name = ?", (self.NAME,)).fetchone()
        return row[0] if row else 0

    def catch_up(self, limit=None, from_seq=None):
        """Apply events the projector has not seen yet and move its position. Returns how many
        events were handled. `from_seq` forces re-delivery from that position (to simulate a
        crash between updating the tables and saving the position); the position never moves back."""
        start = self.position() if from_seq is None else from_seq
        events = self.store.read_all(after_seq=start, limit=limit)
        if not events:
            return 0
        self.db.execute("BEGIN")                            # tables and position move together
        try:
            for ev in events:
                self._apply(ev)
            new_pos = max(self.position(), events[-1].seq)
            self.db.execute("INSERT OR REPLACE INTO projector_position (name, last_seq) VALUES (?,?)",
                            (self.NAME, new_pos))
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise
        return len(events)

    def _apply(self, ev):
        if ev.type == "AccountOpened":
            # idempotent: a replay finds the row already at (or past) this seq and changes nothing
            self.db.execute(
                "INSERT INTO account_balances (account_id, owner, balance_cents, last_seq) VALUES (?,?,0,?) "
                "ON CONFLICT(account_id) DO UPDATE SET owner = excluded.owner, last_seq = excluded.last_seq "
                "WHERE excluded.last_seq > account_balances.last_seq",
                (ev.stream_id, ev.data["owner"], ev.seq))
        elif ev.type in ("Deposited", "Withdrawn"):
            cents = ev.data["amount_cents"]
            delta = cents if ev.type == "Deposited" else -cents
            # the WHERE last_seq < ? guard is what makes a re-delivered event harmless
            self.db.execute(
                "UPDATE account_balances SET balance_cents = balance_cents + ?, last_seq = ? "
                "WHERE account_id = ? AND last_seq < ?", (delta, ev.seq, ev.stream_id, ev.seq))
            if cents >= LARGE_CENTS:
                self.db.execute(
                    "INSERT OR IGNORE INTO large_transactions (seq, account_id, kind, amount_cents) VALUES (?,?,?,?)",
                    (ev.seq, ev.stream_id, ev.type, cents))

    def rebuild(self):
        """Throw the read model away and recompute it from event number one."""
        self.db.execute("BEGIN")
        self.db.execute("DELETE FROM account_balances")
        self.db.execute("DELETE FROM large_transactions")
        self.db.execute("DELETE FROM projector_position")
        self.db.execute("COMMIT")
        total = 0
        while True:
            n = self.catch_up(limit=500)
            if n == 0:
                return total
            total += n

    # --- queries ---
    def balance_of(self, account_id):
        row = self.db.execute("SELECT balance_cents FROM account_balances WHERE account_id = ?",
                              (account_id,)).fetchone()
        return row[0] if row else None

    def all_balances(self):
        return {a: b for a, b in self.db.execute(
            "SELECT account_id, balance_cents FROM account_balances ORDER BY account_id")}

    def large_transactions(self):
        return self.db.execute(
            "SELECT seq, account_id, kind, amount_cents FROM large_transactions ORDER BY seq").fetchall()


# ======================================================================================
# Milestone 4: snapshots
# ======================================================================================
class SnapshotStore:
    """Keeps the latest snapshot of each stream in the same database as the events.
    A snapshot is a cache: it can always be deleted and rebuilt from the events."""

    def __init__(self, store):
        self.store = store
        store.conn.execute("""CREATE TABLE IF NOT EXISTS snapshots (
            stream_id TEXT PRIMARY KEY, version INTEGER NOT NULL, state TEXT NOT NULL)""")

    def save(self, account):
        self.store.conn.execute(
            "INSERT OR REPLACE INTO snapshots (stream_id, version, state) VALUES (?,?,?)",
            (account.id, account.version, json.dumps(account.to_state(), sort_keys=True)))

    def latest(self, stream_id):
        """(version, state_dict) of the newest snapshot, or None."""
        row = self.store.conn.execute(
            "SELECT version, state FROM snapshots WHERE stream_id = ?", (stream_id,)).fetchone()
        return (row[0], json.loads(row[1])) if row else None

    def clear(self):
        self.store.conn.execute("DELETE FROM snapshots")


# ======================================================================================
# Milestone 5: temporal queries
# ======================================================================================
def account_as_of(store, account_id, version=None, at=None):
    """The account as it was after event `version` and/or at time `at` (inclusive).
    With neither, the current state."""
    acct = Account(account_id)
    for ev in store.read_stream(account_id):
        if version is not None and ev.version > version:
            break
        if at is not None and ev.recorded_at > at:
            break
        acct.apply(ev)
    return acct


def balance_history(store, account_id):
    """[(version, recorded_at, balance_after)] for every event of the account, in one pass."""
    acct = Account(account_id)
    out = []
    for ev in store.read_stream(account_id):
        acct.apply(ev)
        out.append((ev.version, ev.recorded_at, acct.balance))
    return out


# ======================================================================================
# Milestone 6 (optional): upcasting
# ======================================================================================
def upcast(ev):
    """Upgrade old event shapes to the current one, in memory, when they are read.
    Deposited v1: {"amount": "12.50"}  (a decimal string in dollars)
    Deposited v2: {"v": 2, "amount_cents": 1250}
    The stored row is never touched."""
    if ev.type == "Deposited" and ev.data.get("v", 1) == 1:
        cents = int((Decimal(ev.data["amount"]) * 100).to_integral_value())    # Decimal: no 19.99 -> 1998 surprise
        data = {k: v for k, v in ev.data.items() if k != "amount"}
        data.update({"v": 2, "amount_cents": cents})
        return ev._replace(data=data)
    return ev
