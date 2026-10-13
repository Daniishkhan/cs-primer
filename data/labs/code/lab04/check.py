"""Self-check for Lab 4.

    python3 check.py              # checks your starter.py
    python3 check.py solution     # checks the reference solution
    python3 check.py --clean      # delete the cached database (it is rebuilt when needed)

The first run builds the lab database (about 10-15 s, ~45 MB) in your system's temp
folder, never in the lab folder. Every milestone then works on its own fresh copy.

For each milestone the check verifies, in this order:
  (a) the answers are identical to the slow reference's,
  (b) the query plan is right (no full SCAN of the big table, the expected kind of index,
      no leftover sort step),
  (c) it is faster. Plans are deterministic, so (b) is what decides pass or fail. A speed-up is
      only enforced where it is huge (>= 5x, best of 3 runs); elsewhere it is just reported.
"""
import importlib
import os
import re
import signal
import sqlite3
import sys
import time
import contextlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True

import dataset  # noqa: E402

if "--clean" in sys.argv:
    dataset.shutil.rmtree(dataset.CACHE_DIR, ignore_errors=True)
    print("removed", dataset.CACHE_DIR)
    sys.exit(0)

target = sys.argv[1] if len(sys.argv) > 1 else "starter"
mod = importlib.import_module(target)
results = []
notes = []
MIN_SPEEDUP = 5.0


def note(text):
    notes.append("    " + text)


class Timeout(Exception):
    pass


@contextlib.contextmanager
def time_limit(seconds):
    if not hasattr(signal, "SIGALRM"):
        yield
        return

    def boom(signum, frame):
        raise Timeout(f"took longer than {seconds} s")
    old = signal.signal(signal.SIGALRM, boom)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)


def check(name, fn):
    del notes[:]
    try:
        with time_limit(55):
            fn()
        print(f"  ✔ {name}")
        results.append(True)
    except NotImplementedError as e:
        print(f"  … {name}: not implemented yet ({e})")
        results.append(False)
    except AssertionError as e:
        print(f"  ✘ {name}: {e}")
        results.append(False)
    except sqlite3.Error as e:
        print(f"  ✘ {name}: SQLite said: {e}")
        results.append(False)
    except Exception as e:
        print(f"  ✘ {name}: {type(e).__name__}: {e}")
        results.append(False)
    for line in notes:
        print(line)


# --- helpers ------------------------------------------------------------------------

@contextlib.contextmanager
def db():
    """A fresh private copy of the database, with a guard that interrupts runaway queries."""
    with dataset.fresh_db() as con:
        deadline = time.time() + 40
        con.set_progress_handler(lambda: 1 if time.time() > deadline else 0, 200000)
        yield con


def best_of(fn, runs=3):
    best = None
    for _ in range(runs):
        t = time.perf_counter()
        fn()
        dt = time.perf_counter() - t
        best = dt if best is None or dt < best else best
    return best


def get_ddl(fn_name, allow_empty=False):
    ddl = getattr(mod, fn_name)()
    if not isinstance(ddl, str):
        raise AssertionError(f"{fn_name}() must return a string")
    if not ddl.strip() and allow_empty:
        return ""
    for stmt in (s.strip() for s in ddl.split(";") if s.strip()):
        if not re.match(r"CREATE\s+(UNIQUE\s+)?INDEX\b", stmt, re.I):
            raise AssertionError(f"{fn_name}() may only contain CREATE INDEX statements; got: {stmt[:50]!r}")
    if not ddl.strip():
        raise AssertionError(f"{fn_name}() returned an empty string: it must return a CREATE INDEX statement")
    return ddl


def get_sql(fn_name):
    sql = getattr(mod, fn_name)()
    if not isinstance(sql, str) or not sql.strip().upper().startswith(("SELECT", "WITH")):
        raise AssertionError(f"{fn_name}() must return a SELECT statement as a string")
    return sql


def show(label, lines):
    for i, line in enumerate(lines):
        note(f"{label if i == 0 else ' ' * len(label)} {line}")


def no_scan(lines, table="the table", sort_ok=False):
    scans = [l for l in lines if l.startswith("SCAN")]
    assert not scans, (f"the plan still contains `{scans[0]}`: every row of {table} is read. "
                       "Check that your index starts with the column(s) in the WHERE clause, and that the query's "
                       "condition is written so the index can be used")
    if not sort_ok:
        sorts = [l for l in lines if "TEMP B-TREE" in l]
        assert not sorts, (f"the plan still contains `{sorts[0]}`: rows are fetched and then sorted. "
                           "An index whose column order matches the ORDER BY avoids that sort")


def report_speed(base, mine, enforce, what="best of 3"):
    ratio = base / mine if mine > 0 else float("inf")
    note(f"speed: {base * 1000:.2f} ms -> {mine * 1000:.2f} ms ({what}); {ratio:,.0f}x faster")
    if enforce:
        assert ratio >= MIN_SPEEDUP, (f"the plan looks right but the speed-up is only {ratio:.1f}x (expected at least {MIN_SPEEDUP:.0f}x). "
                                      "Re-run to rule out a noisy machine; if it stays low, compare plans with explain()")


# --- Milestone 1 --------------------------------------------------------------------

Q1 = "SELECT id, name, country FROM users WHERE email = :email"


def m1():
    ddl = get_ddl("m1_index")
    with db() as con:
        emails = [r[0] for r in con.execute("SELECT email FROM users WHERE id IN (1, 9, 77, 1234, 4999, 20000, 33333, 49999)")]
        emails += ["nobody@example.com", "ADA.ABE1@EXAMPLE.COM"]
        probes = [{"email": e} for e in emails]
        want = [con.execute(Q1, p).fetchall() for p in probes]
        assert [len(w) for w in want[:8]] == [1] * 8 and want[8] == []
        before_plan = dataset.plan(con, Q1, probes[0])
        many = [{"email": e} for e in emails[:8]] * 4
        base = best_of(lambda: [con.execute(Q1, p).fetchall() for p in many])
        con.executescript(ddl)
        got = [con.execute(Q1, p).fetchall() for p in probes]
        assert got == want, "the answers changed after your index (an index must never change results)"
        after_plan = dataset.plan(con, Q1, probes[0])
        show("plan before:", before_plan)
        show("plan after: ", after_plan)
        assert any("USING" in l and "INDEX" in l and l.startswith("SEARCH") for l in after_plan), (
            f"the plan is `{after_plan[0]}`, not a SEARCH using your index")
        no_scan(after_plan, "users")
        report_speed(base, best_of(lambda: [con.execute(Q1, p).fetchall() for p in many]), True)


# --- Milestone 2 --------------------------------------------------------------------

Q2 = """SELECT id, total_cents, created_at FROM orders WHERE user_id = :uid
        ORDER BY created_at DESC, id DESC LIMIT 10"""


def m2():
    ddl = get_ddl("m2_index")
    uids = [1, 2, 3, 40, 777, 25000, 49999, 0]
    with db() as con:
        want = [con.execute(Q2, {"uid": u}).fetchall() for u in uids]
        assert len(want[0]) == 10 and want[-1] == []
        before_plan = dataset.plan(con, Q2, {"uid": 1})
        heavy = [{"uid": u} for u in (1, 2, 3, 40, 777)]
        base = best_of(lambda: [con.execute(Q2, p).fetchall() for p in heavy])
        con.executescript(ddl)
        got = [con.execute(Q2, {"uid": u}).fetchall() for u in uids]
        assert got == want, "the answers changed after your index"
        after_plan = dataset.plan(con, Q2, {"uid": 1})
        show("plan before:", before_plan)
        show("plan after: ", after_plan)
        assert any(l.startswith("SEARCH") and "INDEX" in l for l in after_plan), f"the plan is `{after_plan[0]}`: no index seek"
        no_scan(after_plan, "orders")
        report_speed(base, best_of(lambda: [con.execute(Q2, p).fetchall() for p in heavy]), True)


# --- Milestone 3 --------------------------------------------------------------------

Q3 = """SELECT COUNT(*) AS n, COALESCE(SUM(qty * price_cents), 0) AS revenue
        FROM order_items WHERE product_id = :pid"""


def m3():
    ddl = get_ddl("m3_index")
    pids = [1, 2, 3, 50, 100, 2500, 4999, 5000, 9999]
    with db() as con:
        con.execute("CREATE INDEX idx_items_product ON order_items(product_id)")     # the starting point: a plain index
        want = [con.execute(Q3, {"pid": p}).fetchall() for p in pids]
        before_plan = dataset.plan(con, Q3, {"pid": 1})
        hot = [{"pid": p} for p in (1, 2, 3, 50)]
        base = best_of(lambda: [con.execute(Q3, p).fetchall() for p in hot])
        con.executescript(ddl)
        got = [con.execute(Q3, {"pid": p}).fetchall() for p in pids]
        assert got == want, "the answers changed after your index"
        after_plan = dataset.plan(con, Q3, {"pid": 1})
        show("plan before:", before_plan)
        show("plan after: ", after_plan)
        no_scan(after_plan, "order_items")
        assert any("USING COVERING INDEX" in l for l in after_plan), (
            f"the plan is `{after_plan[0]}`: it still goes back to the table for every matching row. "
            "A covering index must contain product_id AND the columns inside SUM(...)")
        report_speed(base, best_of(lambda: [con.execute(Q3, p).fetchall() for p in hot]), False)


# --- Milestone 4 --------------------------------------------------------------------

def slow_revenue(con, country):
    out = {}
    for uid, email in con.execute("SELECT id, email FROM users WHERE country = ?", (country,)).fetchall():
        (paid,) = con.execute("SELECT COALESCE(SUM(total_cents), 0) FROM orders WHERE user_id = ? AND status = 'paid'", (uid,)).fetchone()
        out[email] = paid
    return out


def m4():
    with db() as con:
        con.execute("CREATE INDEX idx_orders_user_status_total ON orders(user_id, status, total_cents)")
        countries = ["DE", "BR", "NG"]
        seen = []
        con.set_trace_callback(seen.append)
        want, n_slow = {}, 0
        for c in countries:
            del seen[:]
            want[c] = slow_revenue(con, c)
            if c == "DE":
                n_slow = len(seen)
        base = best_of(lambda: slow_revenue(con, "DE"))
        statements = []
        con.set_trace_callback(lambda s: statements.append(s) if s.lstrip().upper().startswith(("SELECT", "WITH")) else None)
        got = {}
        counts = []
        for c in countries:
            del statements[:]
            got[c] = mod.revenue_by_email(con, c)
            counts.append(len(statements))
            if c == "DE":
                captured = list(statements)
        con.set_trace_callback(None)
        for c in countries:
            assert isinstance(got[c], dict), "revenue_by_email must return a dict {email: cents}"
            assert got[c] == want[c], (f"country {c}: the dict differs from the N+1 version "
                                       f"({len(got[c])} users vs {len(want[c])}); users with no paid orders must be present with 0")
        note(f"queries sent for one country: N+1 version {n_slow:,}, yours {counts[0]}")
        assert max(counts) <= 2, (f"your function sent {max(counts)} SELECT statements; use at most 2, however many users there are. "
                                  "One JOIN with GROUP BY does it in one")
        for s in captured:
            lines = dataset.plan(con, s)
            show("your plan:", lines)
            for l in lines:
                if l.startswith("SCAN"):
                    names = {"users"} | {m for m in re.findall(r"\busers\s+(?:AS\s+)?(\w+)", s, re.I)
                                         if m.upper() not in ("LEFT", "JOIN", "WHERE", "ON", "INNER", "GROUP", "ORDER", "AS")}
                    assert l.split()[1] in names, f"`{l}`: the big orders table is scanned. Join through the index on orders(user_id, ...)"
        mine = best_of(lambda: mod.revenue_by_email(con, "DE"))
        report_speed(base, mine, False)
        note(f"(in one process the gap is modest; with a 0.5 ms network round trip per query the N+1 version would add {n_slow * 0.5 / 1000:.1f} s)")


# --- Milestone 5 --------------------------------------------------------------------

OFFSET_SQL = """SELECT id, user_id, total_cents, created_at FROM orders
                ORDER BY created_at DESC, id DESC LIMIT :size OFFSET :offset"""
FIRST = {"last_ts": "9999-12-31 23:59:59", "last_id": 2 ** 62}


def m5():
    ddl = get_ddl("m5_index")
    sql = get_sql("m5_query")
    with db() as con:
        size = 50
        first_pages = con.execute(OFFSET_SQL, {"size": 5 * size, "offset": 0}).fetchall()
        deep_off = 250_000
        deep = con.execute(OFFSET_SQL, {"size": size + 1, "offset": deep_off - 1}).fetchall()
        anchor, deep_want = deep[0], [tuple(r) for r in deep[1:]]
        tie = con.execute("SELECT created_at, MIN(id), MAX(id) FROM orders GROUP BY created_at HAVING COUNT(*) = 2 ORDER BY created_at LIMIT 1").fetchone()
        tie_want = con.execute("""SELECT id, user_id, total_cents, created_at FROM orders
                                  WHERE created_at < :ts OR (created_at = :ts AND id < :id)
                                  ORDER BY created_at DESC, id DESC LIMIT 5""", {"ts": tie[0], "id": tie[2]}).fetchall()
        assert tie_want[0][0] == tie[1], "internal: the tie fixture is wrong"
        base = best_of(lambda: con.execute(OFFSET_SQL, {"size": size, "offset": deep_off}).fetchall())
        con.executescript(ddl)

        def page(last_ts, last_id, n=size):
            return [tuple(r) for r in con.execute(sql, {"last_ts": last_ts, "last_id": last_id, "size": n}).fetchall()]
        # walk five pages from the start, like a user clicking "next"
        walked, cursor = [], dict(FIRST)
        for _ in range(5):
            rows = page(cursor["last_ts"], cursor["last_id"])
            assert len(rows) == size, f"a page should have {size} rows, got {len(rows)}"
            walked += rows
            cursor = {"last_ts": rows[-1][3], "last_id": rows[-1][0]}
        assert walked == [tuple(r) for r in first_pages], "five pages walked with your query differ from the first 250 rows of the OFFSET version"
        assert page(anchor[3], anchor[0]) == deep_want, "the page after row 250,000 differs from the OFFSET version"
        assert page(tie[0], tie[2], 5) == [tuple(r) for r in tie_want], (
            f"two orders share the timestamp {tie[0]!r} (ids {tie[1]} and {tie[2]}); the page after the higher id must start with the lower id. "
            "Compare (created_at, id) as a pair, not created_at alone")
        deep_params = {"last_ts": anchor[3], "last_id": anchor[0], "size": size}
        for label, p in (("first page", {**FIRST, "size": size}), ("deep page", deep_params)):
            lines = dataset.plan(con, sql, p)
            show(f"plan ({label}):", lines)
            no_scan(lines, "orders")
            assert any(l.startswith("SEARCH") and "INDEX" in l for l in lines), f"the {label} plan is `{lines[0]}`: no index seek"
        mine = best_of(lambda: con.execute(sql, deep_params).fetchall())
        report_speed(base, mine, True)
        with_idx = best_of(lambda: con.execute(OFFSET_SQL, {"size": size, "offset": deep_off}).fetchall())
        note(f"for comparison, OFFSET {deep_off:,} even WITH your index: {with_idx * 1000:.2f} ms ({with_idx / mine:,.0f}x slower than keyset)")


# --- Milestone 6 (optional) ---------------------------------------------------------

Q6 = """SELECT COUNT(*) AS n, COALESCE(SUM(total_cents), 0) AS revenue FROM orders WHERE date(created_at) = :day"""
DAYS = [("2022-01-01", "2022-01-02"), ("2023-06-15", "2023-06-16"), ("2023-12-31", "2024-01-01"),
        ("2024-12-31", "2025-01-01"), ("2030-01-01", "2030-01-02")]


def m6():
    ddl = get_ddl("m6_index", allow_empty=True)
    sql = get_sql("m6_query")
    with db() as con:
        con.execute("CREATE INDEX idx_orders_created ON orders(created_at)")      # the starting point
        params = [{"day": d, "next_day": n} for d, n in DAYS]
        want = [con.execute(Q6, p).fetchall() for p in params]
        assert want[1][0][0] > 100 and want[-1] == [(0, 0)]
        before_plan = dataset.plan(con, Q6, params[1])
        base = best_of(lambda: [con.execute(Q6, params[1]).fetchall() for _ in range(2)])
        if ddl:
            con.executescript(ddl)
        got = [con.execute(sql, p).fetchall() for p in params]
        assert got == want, "your query returns different numbers from the date() version"
        lines = dataset.plan(con, sql, params[1])
        show("plan before:", before_plan)
        show("plan after: ", lines)
        no_scan(lines, "orders")
        assert any(l.startswith("SEARCH") and "INDEX" in l for l in lines), f"the plan is `{lines[0]}`: no index seek"
        report_speed(base, best_of(lambda: [con.execute(sql, params[1]).fetchall() for _ in range(2)]), True)


print(f"Lab 4 checks against {target}.py   (SQLite {sqlite3.sqlite_version})")
if not os.path.exists(dataset.BASE_DB):
    print("(first run: building the database, once)")
t0 = time.time()
dataset.ensure_base(say=lambda s: print(" ", s))
print()
check("Milestone 1: a lookup by email (single-column index)", m1)
check("Milestone 2: recent orders for a user (composite index, no sort)", m2)
check("Milestone 3: a covering index for a count/sum", m3)
check("Milestone 4: N+1 -> one JOIN / GROUP BY", m4)
check("Milestone 5: keyset pagination instead of OFFSET", m5)
check("Milestone 6 (optional): a function on an indexed column", m6)
passed = sum(results)
print(f"\n{passed}/{len(results)} milestones passing" + ("  🎉 Lab complete!" if passed == len(results) else ""))
sys.exit(0 if passed == len(results) else 1)
