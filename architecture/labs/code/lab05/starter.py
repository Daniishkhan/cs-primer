"""Lab 5 starter: event sourcing and CQRS for bank accounts.

Write side: an append-only event store in sqlite with optimistic concurrency, and an
Account aggregate that is rebuilt by folding its events. Read side: a Projector that
turns the global event log into query tables and remembers how far it has read.
Plus snapshots, temporal queries and upcasting of old event shapes.

Fill in every TODO, one milestone at a time, and run `python3 check.py` after each one.
The lab page walks you through it. Everything is standard library and deterministic.

Money is always integer cents.
"""
import json
import sqlite3
import time
from collections import namedtuple

LARGE_CENTS = 100_000           # a deposit or withdrawal of $1,000.00 or more is "large"

# One stored event. `seq` is the position in the global log, `version` the position in its stream. (Given.)
Event = namedtuple("Event", "seq stream_id version type data recorded_at")


class ConcurrencyError(Exception):
    """append() was given a stale expected_version: someone else wrote to the stream first. (Given.)"""


class DomainError(Exception):
    """A command was refused because it would break a business rule. (Given.)"""


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
        # isolation_level=None: YOU issue BEGIN / COMMIT / ROLLBACK. timeout: wait for a competing writer.
        self.conn = sqlite3.connect(path, timeout=30, isolation_level=None, check_same_thread=False)
        self._init_schema()

    def _init_schema(self):
        """Create the events table if it does not exist. Columns:
            seq          INTEGER PRIMARY KEY AUTOINCREMENT   (global order of the whole log)
            stream_id    TEXT, version INTEGER, type TEXT, data TEXT (JSON), recorded_at REAL
        and a UNIQUE (stream_id, version) constraint: the database's own guard against two writers
        creating the same version of a stream."""
        raise NotImplementedError("TODO milestone 1: EventStore._init_schema")

    def append(self, stream_id, expected_version, events):
        """Append [(type, data_dict), ...] to a stream, but only if the stream is still at
        `expected_version` (0 for a stream that does not exist yet). Return the stored Events.
        Raise ConcurrencyError if the stream is at any other version; then nothing is written.
        Steps:
        1. now = self.clock();
        2. self.conn.execute("BEGIN IMMEDIATE") so a competing writer waits for you instead of failing;
        3. current = MAX(version) of the stream (0 if none); if it differs from expected_version, ROLLBACK
           and raise ConcurrencyError;
        4. insert each event with version expected_version + 1, +2, ... and data=json.dumps(data); build
           Event(cur.lastrowid, stream_id, version, type, data, now) for each;
        5. COMMIT and return the list. On ANY exception, ROLLBACK first.
        6. Also catch sqlite3.IntegrityError (the UNIQUE constraint firing) and raise ConcurrencyError."""
        raise NotImplementedError("TODO milestone 1: EventStore.append")

    def _upcast(self, ev):
        try:
            return upcast(ev)
        except NotImplementedError:                     # milestone 6 not done yet: pass events through (Given.)
            return ev

    def _event(self, row):
        """Turn a database row (seq, stream_id, version, type, data, recorded_at) into an Event. (Given.)"""
        seq, stream_id, version, etype, data, recorded_at = row
        return self._upcast(Event(seq, stream_id, version, etype, json.loads(data), recorded_at))

    def read_stream(self, stream_id, after_version=0):
        """The events of one stream with version > after_version, oldest first, as Events.
        Add the number of rows you return to self.events_read (milestone 4 counts reads with it),
        and build each Event with self._event(row)."""
        raise NotImplementedError("TODO milestone 1: EventStore.read_stream")

    def read_all(self, after_seq=0, limit=None):
        """The global log: events with seq > after_seq in seq order, at most `limit` of them
        (no limit if None). Build each Event with self._event(row)."""
        raise NotImplementedError("TODO milestone 1: EventStore.read_all")


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
        """Fold ONE event into the state. No validation: events are facts that already happened.
        AccountOpened {"owner"}: opened = True, owner = ...
        Deposited {"v": 2, "amount_cents"}: balance += amount_cents
        Withdrawn {"amount_cents"}: balance -= amount_cents
        Always set self.version = ev.version."""
        raise NotImplementedError("TODO milestone 2: Account.apply")

    @classmethod
    def load(cls, store, account_id):
        """Build an Account by creating an empty one and applying every event of its stream in order."""
        raise NotImplementedError("TODO milestone 2: Account.load")

    # --- commands: validate against the current state, RETURN a list of [(type, data)] events.
    #     They must not change self; execute() appends the events and the next load applies them. ---
    def open(self, owner):
        """Raise AlreadyOpen if already open. Else [("AccountOpened", {"owner": owner})]."""
        raise NotImplementedError("TODO milestone 2: Account.open")

    def deposit(self, cents):
        """AccountNotOpen if not open; InvalidAmount unless cents is a positive int.
        Else [("Deposited", {"v": 2, "amount_cents": cents})]."""
        raise NotImplementedError("TODO milestone 2: Account.deposit")

    def withdraw(self, cents):
        """AccountNotOpen if not open; InvalidAmount unless cents is a positive int;
        InsufficientFunds if cents > balance (no overdraft). Else [("Withdrawn", {"amount_cents": cents})]."""
        raise NotImplementedError("TODO milestone 2: Account.withdraw")

    # --- Milestone 4: state <-> JSON, for snapshots ---
    def to_state(self):
        """A JSON-friendly dict of everything apply() maintains: version, opened, owner, balance."""
        raise NotImplementedError("TODO milestone 4: Account.to_state")

    @classmethod
    def from_state(cls, account_id, state):
        """The inverse of to_state()."""
        raise NotImplementedError("TODO milestone 4: Account.from_state")


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
    """Milestone 2: return Account.load(store, account_id).
    Milestone 4: if `snapshots` is given and has a snapshot for this account, start from it
    (Account.from_state) and apply only the events after the snapshot's version."""
    raise NotImplementedError("TODO milestone 2: load_account")


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
        self._init_schema()

    def _init_schema(self):
        """Create three tables on self.db:
            account_balances(account_id TEXT PRIMARY KEY, owner TEXT, balance_cents INTEGER, last_seq INTEGER)
            large_transactions(seq INTEGER PRIMARY KEY, account_id TEXT, kind TEXT, amount_cents INTEGER)
            projector_position(name TEXT PRIMARY KEY, last_seq INTEGER)
        `last_seq` in account_balances is the seq of the last event applied to THAT row: it is what
        will make replays harmless. `seq` as the primary key of large_transactions does the same."""
        raise NotImplementedError("TODO milestone 3: Projector._init_schema")

    def position(self):
        """last_seq stored for self.NAME in projector_position, or 0 if there is no row yet."""
        raise NotImplementedError("TODO milestone 3: Projector.position")

    def catch_up(self, limit=None, from_seq=None):
        """Apply the events the projector has not seen yet and move its position forward.
        Return how many events were handled (0 when up to date).
        - start = self.position(), or `from_seq` if given (that forces a RE-DELIVERY of old events,
          to simulate a crash between updating the tables and saving the position);
        - events = self.store.read_all(after_seq=start, limit=limit);
        - do all of it in ONE transaction (BEGIN ... COMMIT; ROLLBACK on error) so the tables and the
          position move together;
        - the new position is max(old position, seq of the last event): it must never go backwards."""
        raise NotImplementedError("TODO milestone 3: Projector.catch_up")

    def _apply(self, ev):
        """Update the tables for one event. It MUST be safe to apply the same event twice.
        AccountOpened: insert the account_balances row (balance 0) or, if it exists, only touch it
          when this event's seq is newer than the row's last_seq.
        Deposited / Withdrawn: add or subtract ev.data["amount_cents"] on the row, but only WHERE
          last_seq < ev.seq, and set last_seq = ev.seq. If the amount is >= LARGE_CENTS also
          INSERT OR IGNORE a row into large_transactions (seq, stream_id, ev.type, amount)."""
        raise NotImplementedError("TODO milestone 3: Projector._apply")

    def rebuild(self):
        """Throw the read model away (all three tables) and recompute it from event number one,
        in batches (catch_up(limit=500) until it returns 0). Return the number of events replayed."""
        raise NotImplementedError("TODO milestone 3: Projector.rebuild")

    # --- queries (these are the "read side" of CQRS) ---
    def balance_of(self, account_id):
        """The balance in cents, or None if the projector has never heard of the account."""
        raise NotImplementedError("TODO milestone 3: Projector.balance_of")

    def all_balances(self):
        """{account_id: balance_cents} for every account in the read model."""
        raise NotImplementedError("TODO milestone 3: Projector.all_balances")

    def large_transactions(self):
        """[(seq, account_id, kind, amount_cents), ...] ordered by seq."""
        raise NotImplementedError("TODO milestone 3: Projector.large_transactions")


# ======================================================================================
# Milestone 4: snapshots
# ======================================================================================
class SnapshotStore:
    """Keeps the latest snapshot of each stream in the same database as the events.
    A snapshot is a cache: it can always be deleted and rebuilt from the events."""

    def __init__(self, store):
        self.store = store
        # TODO milestone 4: create the table, using store.conn:
        #   snapshots(stream_id TEXT PRIMARY KEY, version INTEGER, state TEXT)   -- state is JSON
        raise NotImplementedError("TODO milestone 4: SnapshotStore.__init__")

    def save(self, account):
        """Store account.version and json.dumps(account.to_state()), replacing any older snapshot of that stream."""
        raise NotImplementedError("TODO milestone 4: SnapshotStore.save")

    def latest(self, stream_id):
        """(version, state_dict) of the snapshot for this stream, or None."""
        raise NotImplementedError("TODO milestone 4: SnapshotStore.latest")

    def clear(self):
        """Delete every snapshot."""
        raise NotImplementedError("TODO milestone 4: SnapshotStore.clear")


# ======================================================================================
# Milestone 5: temporal queries
# ======================================================================================
def account_as_of(store, account_id, version=None, at=None):
    """The Account as it was after event number `version` and/or at time `at` (inclusive:
    events with recorded_at <= at count). With neither argument, the current state.
    If both are given, both limits apply. Fold only the events that qualify."""
    raise NotImplementedError("TODO milestone 5: account_as_of")


def balance_history(store, account_id):
    """[(version, recorded_at, balance_after_this_event)] for every event of the account, oldest
    first, computed in a single pass over the stream."""
    raise NotImplementedError("TODO milestone 5: balance_history")


# ======================================================================================
# Milestone 6 (optional): upcasting
# ======================================================================================
def upcast(ev):
    """Return the event in its CURRENT shape, without touching the stored row or the argument.
    Deposited v1: {"amount": "12.50"}  (a decimal STRING in dollars, no "v" key)
    Deposited v2: {"v": 2, "amount_cents": 1250}
    Convert v1 to v2 (use decimal.Decimal, not float: 19.99 * 100 is 1998.9999999999998).
    Everything else is returned unchanged. Hint: ev._replace(data=new_data) makes a modified copy."""
    raise NotImplementedError("TODO milestone 6: upcast")
