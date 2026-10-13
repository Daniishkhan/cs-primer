"""A sqlite3 OrderRepository. All the SQL in the system lives in this file."""
from domain import Line, Order, Product


class SqliteRepo:
    def __init__(self, conn):
        self._c = conn
        conn.execute("CREATE TABLE IF NOT EXISTS products (sku TEXT PRIMARY KEY, price_cents INTEGER, stock INTEGER)")
        conn.execute("CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY AUTOINCREMENT, customer TEXT, "
                     "status TEXT, total_cents INTEGER)")
        conn.execute("CREATE TABLE IF NOT EXISTS order_lines (order_id INTEGER, sku TEXT, qty INTEGER, "
                     "unit_price_cents INTEGER)")

    def add_product(self, product: Product) -> None:       # set-up helper, not part of the port
        self._c.execute("INSERT OR REPLACE INTO products VALUES (?, ?, ?)",
                        (product.sku, product.price_cents, product.stock))
        self._c.commit()

    def get_product(self, sku):
        row = self._c.execute("SELECT sku, price_cents, stock FROM products WHERE sku = ?", (sku,)).fetchone()
        return Product(*row) if row else None

    def save_order(self, order: Order) -> int:
        with self._c:                                       # one transaction: order + lines + stock
            cur = self._c.execute("INSERT INTO orders (customer, status, total_cents) VALUES (?, ?, ?)",
                                  (order.customer, order.status, order.total_cents))
            for l in order.lines:
                self._c.execute("INSERT INTO order_lines VALUES (?, ?, ?, ?)",
                                (cur.lastrowid, l.sku, l.qty, l.unit_price_cents))
                self._c.execute("UPDATE products SET stock = stock - ? WHERE sku = ?", (l.qty, l.sku))
        return cur.lastrowid

    def get_order(self, order_id):
        row = self._c.execute("SELECT id, customer, status, total_cents FROM orders WHERE id = ?",
                              (order_id,)).fetchone()
        if row is None:
            return None
        lines = self._c.execute("SELECT sku, qty, unit_price_cents FROM order_lines "
                                "WHERE order_id = ? ORDER BY rowid", (order_id,)).fetchall()
        return Order(row[0], row[1], tuple(Line(*l) for l in lines), row[3], row[2])
