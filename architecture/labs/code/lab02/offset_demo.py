"""offset_demo.py: why the lab uses a cursor. Two clients page through the same table
(newest first, 4 per page); two new rows arrive after the first page."""
import sqlite3

db = sqlite3.connect(":memory:")
db.execute("CREATE TABLE orders (id INTEGER PRIMARY KEY, created_at INTEGER)")
db.executemany("INSERT INTO orders VALUES (?, ?)", [(i, 1000 + i) for i in range(1, 11)])


def ids(sql, *args):
    return [r[0] for r in db.execute(sql, args)]


newest = "SELECT id FROM orders ORDER BY created_at DESC, id DESC "
offset_pages = [ids(newest + "LIMIT 4 OFFSET 0")]
keyset_pages = [ids(newest + "LIMIT 4")]
cursor = db.execute("SELECT created_at, id FROM orders WHERE id = ?", (keyset_pages[0][-1],)).fetchone()

db.executemany("INSERT INTO orders VALUES (?, ?)", [(11, 1011), (12, 1012)])      # new rows arrive

offset_pages.append(ids(newest + "LIMIT 4 OFFSET 4"))
keyset_pages.append(ids("SELECT id FROM orders WHERE (created_at, id) < (?, ?) "
                        "ORDER BY created_at DESC, id DESC LIMIT 4", *cursor))
print("OFFSET pages:", offset_pages)
print("cursor pages:", keyset_pages)
