"""Lab 6 starter: the transactional outbox, a relay, and idempotent consumers.

Fill in every TODO, one milestone at a time, and run `python3 check.py` after each
one. The lab page walks you through it.

System of record: a SQLite file. The "cache" and the "search index" are in-memory
dicts inside consumer objects: stand-ins for Redis and Elasticsearch, which are
separate systems that the database cannot make part of its transaction.

A crash is simulated by a `crash(point)` hook: the check passes a function that
raises Crash at a chosen point. Crash derives from BaseException so that an
`except Exception` in your code cannot swallow it, just as it could not swallow
a power failure.
"""
import contextlib
import json
import sqlite3
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS orders (
    id          INTEGER PRIMARY KEY,
    customer    TEXT NOT NULL,
    item        TEXT NOT NULL,
    total_cents INTEGER NOT NULL,
    status      TEXT NOT NULL,
    version     INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS outbox (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    aggregate_id INTEGER NOT NULL,
    type         TEXT NOT NULL,
    payload      TEXT NOT NULL,
    created_at   REAL NOT NULL,
    published    INTEGER NOT NULL DEFAULT 0
);
"""


def no_crash(point):
    """The default crash hook: never crashes."""


def open_db(path):
    """Open the database file. autocommit mode: we say BEGIN and COMMIT ourselves."""
    conn = sqlite3.connect(path, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


@contextlib.contextmanager
def transaction(conn):
    """BEGIN ... COMMIT, or ROLLBACK if anything (even a simulated crash) escapes."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")


def order_state(row):
    """A DB row as the plain dict that events and consumers carry."""
    return {"id": row["id"], "customer": row["customer"], "item": row["item"],
            "total_cents": row["total_cents"], "status": row["status"], "version": row["version"]}


def db_snapshot(conn):
    """The truth: {order_id: order_state} for every order in the database."""
    return {r["id"]: order_state(r) for r in conn.execute("SELECT * FROM orders ORDER BY id")}


def tokens(order):
    """The search tokens of an order: lower-cased words of item, customer and status."""
    return {w.lower() for w in ("%s %s %s" % (order["item"], order["customer"], order["status"])).split()}


# ---------------------------------------------------------------------------------------
# The two downstream systems. put() is the naive "just overwrite it" write used by the
# dual-write code; handle() (Milestone 4) is how they behave as event consumers.
# ---------------------------------------------------------------------------------------
class Consumer:
    def __init__(self):
        self.offset = 0                         # position in the log: next event to read

    # ---- Milestone 5 -------------------------------------------------------------
    def poll(self, log, crash=no_crash):
        """Handle every event from log[self.offset:] in order. Returns how many you handled.
        For each event: self.handle(event); then crash("handled"); THEN self.offset += 1.
        (Advance the offset only after the event is handled. A crash in between means the
        event is delivered again after a restart; milestone 4 makes that harmless.)"""
        raise NotImplementedError("TODO milestone 5: Consumer.poll")


class Cache(Consumer):
    def __init__(self):
        super().__init__()
        self.entries = {}                       # order_id -> order state (with version)

    def put(self, order):
        self.entries[order["id"]] = dict(order)

    # ---- Milestone 4 -------------------------------------------------------------
    def handle(self, event):
        """Apply one event (event["payload"] is the order's full state, with a version) so that
        duplicates and old events do nothing. Two ways: remember processed event ids, or compare
        versions. Think about which one survives REORDERED delivery."""
        raise NotImplementedError("TODO milestone 4: Cache.handle")


class SearchIndex(Consumer):
    def __init__(self):
        super().__init__()
        self.docs = {}                          # order_id -> order state
        self.inverted = {}                      # token -> set of order ids

    def put(self, order):
        old = self.docs.get(order["id"])
        if old is not None:
            for t in tokens(old):
                self.inverted[t].discard(order["id"])
        self.docs[order["id"]] = dict(order)
        for t in tokens(order):
            self.inverted.setdefault(t, set()).add(order["id"])

    def search(self, term):
        return sorted(self.inverted.get(term.lower(), ()))

    # ---- Milestone 4 -------------------------------------------------------------
    def handle(self, event):
        """Same contract as Cache.handle. put() already replaces the old tokens of a changed order."""
        raise NotImplementedError("TODO milestone 4: SearchIndex.handle")


# ---------------------------------------------------------------------------------------
# Milestone 1: the dual-write bug
# ---------------------------------------------------------------------------------------
def place_order_dual_write(conn, cache, index, order_id, customer, item, total_cents,
                           crash=no_crash, cache_first=False):
    """The code everyone writes first. (Given.) Three systems, no transaction across them."""
    def db():
        with transaction(conn):
            conn.execute("INSERT INTO orders VALUES (?, ?, ?, ?, 'placed', 1)",
                         (order_id, customer, item, total_cents))

    order = {"id": order_id, "customer": customer, "item": item,
             "total_cents": total_cents, "status": "placed", "version": 1}
    if not cache_first:
        db()
        crash("after_db")
        cache.put(order)
        crash("after_cache")
        index.put(order)
        crash("after_index")
    else:
        cache.put(order)
        crash("after_cache")
        index.put(order)
        crash("after_index")
        db()
        crash("after_db")


def update_status_dual_write(conn, cache, index, order_id, status, crash=no_crash):
    """Same bug for updates. (Given.)"""
    with transaction(conn):
        conn.execute("UPDATE orders SET status = ?, version = version + 1 WHERE id = ?", (status, order_id))
        row = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    order = order_state(row)
    crash("after_db")
    cache.put(order)
    crash("after_cache")
    index.put(order)
    crash("after_index")


def diagnose(conn, cache, index):
    """Compare the cache and the index with the database (the truth, see db_snapshot).
    Return a dict with six sorted lists of order ids:

        cache_missing, cache_extra, cache_stale, index_missing, index_extra, index_stale

        missing: in the DB but absent from that system
        extra:   in that system but absent from the DB (a phantom)
        stale:   in both, but the system's stored state differs from the DB's

    cache.entries and index.docs are {order_id: order state} dicts."""
    raise NotImplementedError("TODO milestone 1: diagnose")


# ---------------------------------------------------------------------------------------
# Milestone 2: the transactional outbox
# ---------------------------------------------------------------------------------------
def _emit(conn, event_type, order):
    """Insert one outbox row describing `order` (a plain dict): aggregate_id = order["id"],
    payload = json.dumps(order), created_at = time.time(). It runs inside the caller's
    transaction, so do not BEGIN or COMMIT here."""
    raise NotImplementedError("TODO milestone 2: _emit")


def place_order(conn, order_id, customer, item, total_cents, crash=no_crash):
    """Insert the order (status "placed", version 1) AND its outbox event in ONE transaction.
    Use `with transaction(conn):` and keep these hook calls exactly here:
        crash("after_order_insert")   inside the transaction, after the orders INSERT
        crash("before_commit")        inside the transaction, after the outbox INSERT
        crash("after_commit")         after the `with` block
    Event type "OrderPlaced"; use _emit for the outbox row."""
    raise NotImplementedError("TODO milestone 2: place_order")


def update_status(conn, order_id, status, crash=no_crash):
    """Change an order's status and bump its version, with its outbox event
    ("OrderStatusChanged", carrying the NEW full state), in one transaction.
    Hooks: crash("after_order_update") after the UPDATE, crash("before_commit") after the
    outbox INSERT (both inside the transaction), crash("after_commit") after it."""
    raise NotImplementedError("TODO milestone 2: update_status")


# ---------------------------------------------------------------------------------------
# Milestone 3: the relay
# ---------------------------------------------------------------------------------------
def relay_once(conn, log, crash=no_crash):
    """Publish every unpublished outbox row (published = 0) to `log`, in id order, and mark
    each one published. Returns the number of events published.

    For each row: append {"id", "aggregate_id", "type", "payload"} to `log`, where payload
    is the decoded JSON (a dict); then crash("after_publish"); THEN UPDATE ... SET published = 1
    for that row; then crash("after_mark"). Mark a row only after it is published."""
    raise NotImplementedError("TODO milestone 3: relay_once")


# ---------------------------------------------------------------------------------------
# Milestone 5: catch-up
# ---------------------------------------------------------------------------------------
def rebuild(log, consumer_cls):
    """A brand-new consumer that has never seen anything: replay the log from offset 0."""
    """Create a consumer with consumer_cls(), poll it through the whole log, return it."""
    raise NotImplementedError("TODO milestone 5: rebuild")
