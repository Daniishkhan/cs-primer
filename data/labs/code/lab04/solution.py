"""Lab 4 solution: make six slow queries fast with SQLite indexes and rewrites.

Run `python3 solution.py` to see the plans of the fixed queries (it builds the
dataset on the first run, see dataset.py).
"""
import time

from dataset import explain, open_db

# ---------------------------------------------------------------------------
# Milestone 1: a lookup by email.   (The query is given and must not change.)
# ---------------------------------------------------------------------------

LOOKUP_BY_EMAIL = "SELECT id, name, country FROM users WHERE email = :email"


def m1_index():
    """One single-column index on the column in the WHERE clause."""
    return "CREATE INDEX idx_users_email ON users(email)"


# ---------------------------------------------------------------------------
# Milestone 2: the ten most recent orders of one user.
# ---------------------------------------------------------------------------

RECENT_ORDERS = """
SELECT id, total_cents, created_at
FROM orders
WHERE user_id = :uid
ORDER BY created_at DESC, id DESC
LIMIT 10
"""


def m2_index():
    """Equality column first (user_id), then the ORDER BY column (created_at).
    Inside each user the entries are already sorted by created_at, and SQLite
    adds the rowid (= id) as a last, hidden column, so even the tie-break is free:
    no sort step is needed and LIMIT 10 stops after ten entries."""
    return "CREATE INDEX idx_orders_user_created ON orders(user_id, created_at)"


# ---------------------------------------------------------------------------
# Milestone 3: units and revenue per product, answered from the index alone.
# ---------------------------------------------------------------------------

PRODUCT_SALES = """
SELECT COUNT(*) AS n, COALESCE(SUM(qty * price_cents), 0) AS revenue
FROM order_items
WHERE product_id = :pid
"""


def m3_index():
    """Search column first, then every other column the query reads."""
    return "CREATE INDEX idx_items_product_cover ON order_items(product_id, qty, price_cents)"


# ---------------------------------------------------------------------------
# Milestone 4: N+1.
# ---------------------------------------------------------------------------

def revenue_by_email_n_plus_one(con, country):
    """GIVEN, slow: one query for the users, then one more query per user."""
    result = {}
    for uid, email in con.execute("SELECT id, email FROM users WHERE country = ?", (country,)).fetchall():
        (paid,) = con.execute(
            "SELECT COALESCE(SUM(total_cents), 0) FROM orders WHERE user_id = ? AND status = 'paid'",
            (uid,)).fetchone()
        result[email] = paid
    return result


def revenue_by_email(con, country):
    """Same answer, ONE query. LEFT JOIN keeps users who have no paid orders (their total is 0)."""
    rows = con.execute(
        """SELECT u.email, COALESCE(SUM(o.total_cents), 0)
           FROM users AS u
           LEFT JOIN orders AS o ON o.user_id = u.id AND o.status = 'paid'
           WHERE u.country = ?
           GROUP BY u.id""", (country,))
    return dict(rows.fetchall())


# ---------------------------------------------------------------------------
# Milestone 5: pagination, newest orders first.
# ---------------------------------------------------------------------------

OFFSET_PAGE = """
SELECT id, user_id, total_cents, created_at
FROM orders
ORDER BY created_at DESC, id DESC
LIMIT :size OFFSET :offset
"""


def m5_index():
    """The index walks orders in exactly the page order; id makes ties unambiguous."""
    return "CREATE INDEX idx_orders_created_id ON orders(created_at, id)"


def m5_query():
    """Keyset ('seek') pagination: ask for the rows that come AFTER the last row you showed.
    The row-value comparison is the same as
        created_at < :last_ts OR (created_at = :last_ts AND id < :last_id)
    but reads more clearly, and SQLite can seek straight into the index with it."""
    return """
SELECT id, user_id, total_cents, created_at
FROM orders
WHERE (created_at, id) < (:last_ts, :last_id)
ORDER BY created_at DESC, id DESC
LIMIT :size
"""


# ---------------------------------------------------------------------------
# Milestone 6 (optional): a function on an indexed column.
# ---------------------------------------------------------------------------

ORDERS_ON_DAY = """
SELECT COUNT(*) AS n, COALESCE(SUM(total_cents), 0) AS revenue
FROM orders
WHERE date(created_at) = :day
"""


def m6_index():
    """Rewrite instead of indexing: the harness already has an index on created_at.
    (The other fix is an expression index: CREATE INDEX ... ON orders(date(created_at)).)
    Return "" for 'no new index'."""
    return ""


def m6_query():
    """A half-open range on the bare column: [day, next_day). The index on created_at can seek into it."""
    return """
SELECT COUNT(*) AS n, COALESCE(SUM(total_cents), 0) AS revenue
FROM orders
WHERE created_at >= :day AND created_at < :next_day
"""


if __name__ == "__main__":
    con = open_db()
    con.execute(m1_index())
    row = con.execute("SELECT email FROM users WHERE id = 777").fetchone()
    print("Milestone 1 plan after your index:")
    explain(con, LOOKUP_BY_EMAIL, {"email": row[0]})
    t = time.perf_counter()
    for _ in range(1000):
        con.execute(LOOKUP_BY_EMAIL, {"email": row[0]}).fetchall()
    print(f"  1000 lookups: {(time.perf_counter() - t) * 1000:.1f} ms")
