"""Lab 4 starter: make six slow queries fast with SQLite indexes and rewrites.

Fill in every TODO, one milestone at a time, and run `python3 check.py`
after each one. The lab page walks you through it.

How it works: check.py makes a private copy of the database (50,000 users,
500,000 orders, ~1,000,000 order_items, no indexes yet), calls YOUR functions,
applies what they return, and then checks three things: the answers are the same,
the query plan no longer does a full SCAN of the big table (or uses the expected
index), and it is faster.

To experiment yourself:   python3 -i starter.py     then   con = open_db()
    explain(con, LOOKUP_BY_EMAIL, {"email": "ada.abe1@example.com"})
"""
from dataset import explain, open_db   # open_db() gives you a private copy to play with


# ---------------------------------------------------------------------------
# Milestone 1: a lookup by email.   (The query is given and must not change.)
# ---------------------------------------------------------------------------

LOOKUP_BY_EMAIL = "SELECT id, name, country FROM users WHERE email = :email"


def m1_index():
    """Return a string with ONE CREATE INDEX statement that lets LOOKUP_BY_EMAIL
    seek instead of scanning all 50,000 users.

    Hint: which column is in the WHERE clause? Name the index anything you like.
    """
    raise NotImplementedError("TODO milestone 1: m1_index")


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
    """Return CREATE INDEX statement(s) so RECENT_ORDERS neither scans orders NOR
    needs a sort ("USE TEMP B-TREE FOR ORDER BY" must disappear from the plan).

    Hint: an index on user_id alone finds the user's rows but not in date order.
    Put the equality column first, then the column in ORDER BY. (SQLite adds the
    rowid, which is `id`, as a hidden last column of every index.)
    """
    raise NotImplementedError("TODO milestone 2: m2_index")


# ---------------------------------------------------------------------------
# Milestone 3: units and revenue per product. check.py has already created a
# plain index on order_items(product_id); your job is to make it COVER the query.
# ---------------------------------------------------------------------------

PRODUCT_SALES = """
SELECT COUNT(*) AS n, COALESCE(SUM(qty * price_cents), 0) AS revenue
FROM order_items
WHERE product_id = :pid
"""


def m3_index():
    """Return a CREATE INDEX statement whose plan says "USING COVERING INDEX" for PRODUCT_SALES.

    Hint: a covering index contains every column the query touches: the one in
    WHERE, then the ones inside SUM(...).
    """
    raise NotImplementedError("TODO milestone 3: m3_index")


# ---------------------------------------------------------------------------
# Milestone 4: N+1. check.py has already created a covering index on
# orders(user_id, status, total_cents), so each single query below is fast. The
# problem is how MANY queries there are.
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
    """Return {email: total paid cents} for every user in `country`, exactly like the
    function above (users with no paid orders map to 0), using at most TWO SELECT
    statements in total, however many users there are.

    Hint: LEFT JOIN orders ON the user id AND status = 'paid', then GROUP BY the user.
    """
    raise NotImplementedError("TODO milestone 4: revenue_by_email")


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
    """Return CREATE INDEX statement(s) that let the database walk orders in page order."""
    raise NotImplementedError("TODO milestone 5: m5_index")


def m5_query():
    """Return SQL for keyset pagination with the named parameters :last_ts, :last_id
    and :size. It must return the next :size rows AFTER the row (last_ts, last_id) in
    the order (created_at DESC, id DESC), with columns exactly
    id, user_id, total_cents, created_at.

    For the first page, check.py passes last_ts='9999-12-31 23:59:59' and last_id=2**62.
    Careful with ties: two orders can have the same created_at. Compare BOTH columns,
    for example with the row value (created_at, id) < (:last_ts, :last_id).
    """
    raise NotImplementedError("TODO milestone 5: m5_query")


# ---------------------------------------------------------------------------
# Milestone 6 (optional): a function on an indexed column. check.py has already
# created an index on orders(created_at). It is not used by the query below. Why?
# ---------------------------------------------------------------------------

ORDERS_ON_DAY = """
SELECT COUNT(*) AS n, COALESCE(SUM(total_cents), 0) AS revenue
FROM orders
WHERE date(created_at) = :day
"""


def m6_index():
    """Return CREATE INDEX statement(s), or "" if you fix the query instead of indexing."""
    raise NotImplementedError("TODO milestone 6: m6_index")


def m6_query():
    """Return SQL with the same two output columns for the day :day. The parameter
    :next_day (the following date, e.g. '2023-06-16') is available if you want it.
    Fix it either by rewriting the predicate on the bare column, or by indexing the
    expression the query uses."""
    raise NotImplementedError("TODO milestone 6: m6_query")
