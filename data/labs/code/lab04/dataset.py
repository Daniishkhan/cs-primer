"""Lab 4: the dataset, and two helpers (open_db, explain). Standard library only.

    python3 dataset.py            # build the database once (about 10-15 s) and print its path
    python3 dataset.py --clean    # delete the cached database

The database has three tables and NO indexes except each table's primary key:

    users        50,000 rows   (id, email, name, country, created_at)
    orders      500,000 rows   (id, user_id, status, total_cents, created_at)
    order_items ~1,000,000     (id, order_id, product_id, qty, price_cents)

It is generated with a fixed random seed, so everybody gets the same data. The
finished file (about 100 MB) is cached in your system's temp folder, NOT in this
lab's folder, and every check works on a fresh private copy of it. Deleting it is
always safe: it is rebuilt on the next run.
"""
import contextlib
import os
import random
import shutil
import sqlite3
import sys
import tempfile
import time

VERSION = 1
N_USERS, N_ORDERS = 50_000, 500_000
CACHE_DIR = os.path.join(tempfile.gettempdir(), f"zts-lab04-v{VERSION}")
BASE_DB = os.path.join(CACHE_DIR, "base.db")

COUNTRIES = ["US", "IN", "BR", "DE", "GB", "FR", "JP", "NG", "MX", "ID", "PK", "CA"]
STATUSES = ["paid"] * 80 + ["shipped"] * 8 + ["refunded"] * 6 + ["cancelled"] * 4 + ["pending"] * 2
FIRST = ["ada", "bo", "chen", "dara", "emre", "farah", "gus", "hana", "ivo", "jun", "kofi", "lena",
         "mia", "noor", "omar", "priya", "quinn", "rosa", "sven", "tara", "uma", "vik", "wen", "yara", "zed"]
LAST = ["abe", "baker", "cruz", "diaz", "evans", "faure", "gomez", "hill", "iyer", "jones", "khan",
        "lopez", "meyer", "nasser", "ortiz", "patel", "quist", "reyes", "silva", "tran", "ueda", "vega", "wu", "xu", "yang"]
START = 1640995200            # 2022-01-01 00:00:00 UTC
SPAN = 3 * 365 * 86400        # three years of orders

SCHEMA = """
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    email TEXT NOT NULL,
    name TEXT NOT NULL,
    country TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE orders (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    status TEXT NOT NULL,
    total_cents INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE order_items (
    id INTEGER PRIMARY KEY,
    order_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    qty INTEGER NOT NULL,
    price_cents INTEGER NOT NULL
);
"""


def _stamp(t):
    return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(t))


def _users(rng):
    for i in range(1, N_USERS + 1):
        first, last = rng.choice(FIRST), rng.choice(LAST)
        yield (i, f"{first}.{last}{i}@example.com", f"{first.title()} {last.title()}",
               rng.choice(COUNTRIES), _stamp(START - rng.randrange(0, 3 * 365 * 86400)))


def _orders(rng):
    step = SPAN // N_ORDERS
    for i in range(1, N_ORDERS + 1):
        # A few "power users" (small ids) place far more orders than most.
        uid = int(N_USERS * rng.random() ** 3) + 1
        yield (i, uid, rng.choice(STATUSES), rng.randrange(500, 50_000),
               _stamp(START + i * step + rng.randrange(-step, step)))


def _items(rng):
    k = 0
    for order_id in range(1, N_ORDERS + 1):
        for _ in range(rng.choice((1, 2, 2, 3))):
            k += 1
            product = int(5000 * rng.random() ** 2) + 1          # some products sell far more than others
            yield (k, order_id, product, rng.randrange(1, 6), rng.randrange(100, 20_000))


def build(path, say=print):
    """Generate the database at `path` (about 10-15 s)."""
    t0 = time.time()
    rng = random.Random(20240601)
    if os.path.exists(path):
        os.remove(path)
    con = sqlite3.connect(path)
    con.execute("PRAGMA journal_mode = OFF")
    con.execute("PRAGMA synchronous = OFF")
    con.executescript(SCHEMA)
    for table, rows, marks in (("users", _users(rng), 5), ("orders", _orders(rng), 5), ("order_items", _items(rng), 5)):
        batch = []
        for row in rows:
            batch.append(row)
            if len(batch) == 50_000:
                con.executemany(f"INSERT INTO {table} VALUES ({','.join('?' * marks)})", batch)
                batch = []
        if batch:
            con.executemany(f"INSERT INTO {table} VALUES ({','.join('?' * marks)})", batch)
        say(f"  {table}: done ({time.time() - t0:.1f} s)")
    con.execute(f"PRAGMA user_version = {VERSION}")
    con.commit()
    con.execute("ANALYZE")                  # give the query planner honest statistics
    con.commit()
    con.close()


def ensure_base(say=print):
    """Make sure the cached database exists and is complete; return its path."""
    try:
        if os.path.exists(BASE_DB):
            con = sqlite3.connect(BASE_DB)
            ok = con.execute("PRAGMA user_version").fetchone()[0] == VERSION and \
                con.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == N_ORDERS
            con.close()
            if ok:
                return BASE_DB
    except sqlite3.Error:
        pass
    os.makedirs(CACHE_DIR, exist_ok=True)
    say(f"Building the lab database once (cached in {CACHE_DIR}) ...")
    tmp = BASE_DB + ".partial"
    build(tmp, say)
    os.replace(tmp, BASE_DB)               # a half-built file never looks finished
    return BASE_DB


@contextlib.contextmanager
def fresh_db():
    """A private copy of the database as an open connection; deleted afterwards."""
    base = ensure_base()
    d = tempfile.mkdtemp(prefix="lab04-run-")
    path = os.path.join(d, "work.db")
    try:
        shutil.copyfile(base, path)
        con = sqlite3.connect(path)
        try:
            yield con
        finally:
            con.close()
    finally:
        shutil.rmtree(d, ignore_errors=True)


def open_db():
    """Open a copy of the database for experiments: con = open_db(). The copy lives
    in your temp folder and disappears when the program exits."""
    import atexit
    cm = fresh_db()
    con = cm.__enter__()
    atexit.register(lambda: cm.__exit__(None, None, None))
    return con


def plan(con, sql, params=()):
    """EXPLAIN QUERY PLAN as a list of detail strings, e.g. 'SEARCH users USING INDEX idx (email=?)'."""
    return [row[3] for row in con.execute("EXPLAIN QUERY PLAN " + sql, params)]


def explain(con, sql, params=()):
    """Print the query plan of `sql`. Read it like this:
        SCAN t                      every row of t is visited (slow on big tables)
        SEARCH t USING INDEX i (..) a B-tree seek into index i, then the rows it points to
        SEARCH t USING COVERING INDEX i (..)   a seek, answered from the index alone
        USE TEMP B-TREE FOR ORDER BY            an extra sort step
    """
    for line in plan(con, sql, params):
        print("  QUERY PLAN:", line)


if __name__ == "__main__":
    if "--clean" in sys.argv:
        shutil.rmtree(CACHE_DIR, ignore_errors=True)
        print("removed", CACHE_DIR)
    else:
        t = time.time()
        path = ensure_base()
        c = sqlite3.connect(path)
        for tb in ("users", "orders", "order_items"):
            print(f"{tb:12} {c.execute(f'SELECT COUNT(*) FROM {tb}').fetchone()[0]:>10,} rows")
        print(f"database: {path}  ({os.path.getsize(path) / 1e6:.0f} MB, ready in {time.time() - t:.1f} s)")
        c.close()
