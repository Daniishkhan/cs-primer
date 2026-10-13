"""Lab 6 solution: the transactional outbox, a relay, and idempotent consumers.

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
        """Handle every event from self.offset to the end of the log. Returns how many."""
        n = 0
        while self.offset < len(log):
            self.handle(log[self.offset])
            crash("handled")                    # a crash HERE: handled, but the offset was not saved
            self.offset += 1
            n += 1
        return n


class Cache(Consumer):
    def __init__(self):
        super().__init__()
        self.entries = {}                       # order_id -> order state (with version)

    def put(self, order):
        self.entries[order["id"]] = dict(order)

    # ---- Milestone 4 -------------------------------------------------------------
    def handle(self, event):
        order = event["payload"]
        have = self.entries.get(order["id"])
        if have is not None and have["version"] >= order["version"]:
            return                              # a duplicate or an older event: ignore it
        self.put(order)


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
        order = event["payload"]
        have = self.docs.get(order["id"])
        if have is not None and have["version"] >= order["version"]:
            return
        self.put(order)


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
    """Compare the cache and the index with the database. For each system report:
        missing: order ids in the DB but absent there
        extra:   order ids there but absent from the DB (phantoms)
        stale:   order ids in both whose stored state differs from the DB's
    """
    truth = db_snapshot(conn)
    report = {}
    for name, held in (("cache", cache.entries), ("index", index.docs)):
        report[name + "_missing"] = sorted(i for i in truth if i not in held)
        report[name + "_extra"] = sorted(i for i in held if i not in truth)
        report[name + "_stale"] = sorted(i for i in truth if i in held and held[i] != truth[i])
    return report


# ---------------------------------------------------------------------------------------
# Milestone 2: the transactional outbox
# ---------------------------------------------------------------------------------------
def _emit(conn, event_type, order):
    """Insert one outbox row describing `order` (a plain dict). Must run inside the caller's transaction."""
    conn.execute("INSERT INTO outbox (aggregate_id, type, payload, created_at) VALUES (?, ?, ?, ?)",
                 (order["id"], event_type, json.dumps(order, sort_keys=True), time.time()))


def place_order(conn, order_id, customer, item, total_cents, crash=no_crash):
    """Insert the order AND its outbox event in ONE transaction."""
    order = {"id": order_id, "customer": customer, "item": item,
             "total_cents": total_cents, "status": "placed", "version": 1}
    with transaction(conn):
        conn.execute("INSERT INTO orders (id, customer, item, total_cents, status, version) "
                     "VALUES (?, ?, ?, ?, ?, ?)",
                     (order_id, customer, item, total_cents, "placed", 1))
        crash("after_order_insert")
        _emit(conn, "OrderPlaced", order)
        crash("before_commit")
    crash("after_commit")


def update_status(conn, order_id, status, crash=no_crash):
    """Change an order's status and bump its version, with its outbox event, in one transaction."""
    with transaction(conn):
        conn.execute("UPDATE orders SET status = ?, version = version + 1 WHERE id = ?", (status, order_id))
        crash("after_order_update")
        row = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
        _emit(conn, "OrderStatusChanged", order_state(row))
        crash("before_commit")
    crash("after_commit")


# ---------------------------------------------------------------------------------------
# Milestone 3: the relay
# ---------------------------------------------------------------------------------------
def relay_once(conn, log, crash=no_crash):
    """Publish every unpublished outbox row to `log`, in id order, and mark each one published.
    Returns the number of events published."""
    rows = conn.execute("SELECT * FROM outbox WHERE published = 0 ORDER BY id").fetchall()
    for row in rows:
        log.append({"id": row["id"], "aggregate_id": row["aggregate_id"],
                    "type": row["type"], "payload": json.loads(row["payload"])})
        crash("after_publish")                  # a crash HERE means the row is published but not marked
        with transaction(conn):
            conn.execute("UPDATE outbox SET published = 1 WHERE id = ?", (row["id"],))
        crash("after_mark")
    return len(rows)


# ---------------------------------------------------------------------------------------
# Milestone 5: catch-up
# ---------------------------------------------------------------------------------------
def rebuild(log, consumer_cls):
    """A brand-new consumer that has never seen anything: replay the log from offset 0."""
    consumer = consumer_cls()
    consumer.poll(log)
    return consumer
