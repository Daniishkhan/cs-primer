"""swap_demo.py: replay the whole scenario through the solution once per repository and compare.

    python3 swap_demo.py            # uses solution/
    python3 swap_demo.py starter    # uses your package, once milestone 5 passes
"""
import os
import sqlite3
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, sys.argv[1] if len(sys.argv) > 1 else "solution"), HERE]
import domain                                    # noqa: E402
import harness                                   # noqa: E402
from adapters.fake_email import FakeEmail        # noqa: E402
from adapters.fake_payment import FakePayment    # noqa: E402
from adapters.http_handler import build_handler  # noqa: E402
from adapters.memory_repo import InMemoryRepo    # noqa: E402
from adapters.sqlite_repo import SqliteRepo      # noqa: E402
from app import GetOrder, PlaceOrder             # noqa: E402


def run(repo):
    for sku, price, stock in harness.PRODUCTS:
        repo.add_product(domain.Product(sku, price, stock))
    pay, mail = FakePayment(), FakeEmail()
    handle = build_handler(PlaceOrder(repo, pay, mail), GetOrder(repo))    # the composition root
    return harness.record(handle, harness.requests(), lambda: pay.charges, lambda: mail.sent,
                          lambda: {s: repo.get_product(s).stock for s, _, _ in harness.PRODUCTS})


a = run(InMemoryRepo())
b = run(SqliteRepo(sqlite3.connect(":memory:")))
print("memory == sqlite:", a == b, "| responses:", len(a["responses"]), "| emails:", len(a["emails"]))
