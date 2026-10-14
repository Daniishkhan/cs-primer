"""fixtures.py: the Northwind billing backend and the twenty evaluation tasks.

Given; not part of the exercise. Everything is built from a fixed seed, so every run sees
the same data. "Today" in this world is 10 April 2026.

The backend is an ordinary billing system: customers, invoices, payments and refunds.
Two things in it matter for the lab:

  * Ana Silva (cus_1042) has 60 invoices, so a tool that dumps her invoices is expensive.
    A second customer, cus_1046, is also called Ana Silva (different email).
  * Refunds go through Northwind.apply_refund, which can SUCCEED AND THEN TIME OUT
    (the money moves, the caller never hears back). It deduplicates on an idempotency
    key if the caller supplies one.
"""
from __future__ import annotations

import copy
import random
from typing import Any, Dict, List, Optional

TODAY = "2026-04-10"
REFUND_CAP_CENTS = 10_000          # refunds above this need a human


def money(cents: int) -> str:
    return f"£{cents / 100:.2f}"


def _month_back(year: int, month: int, k: int):
    m = month - 1 - k
    return year + m // 12, m % 12 + 1


# (customer_id, name, email, plan, monthly cents, number of monthly invoices)
_CUSTOMERS = [
    ("cus_1042", "Ana Silva", "ana@example.com", "Standard", 4900, 60),
    ("cus_1043", "Ben Okafor", "ben@example.com", "Basic", 2900, 8),
    ("cus_1044", "Chen Wei", "chen@example.com", "Starter", 1500, 6),
    ("cus_1045", "Dana Petrov", "dana@example.com", "Plus", 6900, 7),
    ("cus_1046", "Ana Silva", "ana.silva@work.example", "Team", 5900, 5),
    ("cus_1047", "Eli Marsh", "eli@example.com", "Basic", 3900, 4),
]
_DUPLICATED_MARCH = {"cus_1042": ("pay_88123", "pay_88124"), "cus_1043": ("pay_88301", "pay_88302"),
                     "cus_1044": ("pay_88401", "pay_88402"), "cus_1045": ("pay_88501", "pay_88502")}
_ANNUAL = {"cus_1044": ("inv_a1044", "pay_88450", 25_000, "2026-02-15"), "cus_1045": ("inv_a1045", "pay_88550", 18_000, "2026-01-20")}
_SPECIAL_AMOUNT = {("cus_1043", "2025-11"): 3400, ("cus_1044", "2025-12"): 1800}


def _build():
    rng = random.Random(7)
    customers, invoices, payments = {}, [], {}
    pay_n = 50_000
    inv_n = 3000
    for cid, name, email, plan, cents, n in _CUSTOMERS:
        customers[cid] = {"customer_id": cid, "name": name, "email": email, "plan": plan}
        for k in range(n):                       # k = 0 is April 2026, the newest
            y, m = _month_back(2026, 4, k)
            ym = f"{y}-{m:02d}"
            status = "open" if k == 0 else "paid" if k != 2 else "overdue"
            amount = _SPECIAL_AMOUNT.get((cid, ym), cents)
            inv = {
                "id": f"inv_{inv_n}", "customer_id": cid, "status": status, "amount_cents": amount, "currency": "GBP",
                "created_at": f"{ym}-01", "due_at": f"{ym}-15",
                "billing_address": {"line1": f"{rng.randrange(1, 90)} Mill Lane", "city": "Leeds", "postcode": "LS1 4AB", "country": "GB"},
                "line_items": [{"sku": f"plan-{j}", "qty": 1, "unit_cents": amount // 3} for j in range(1, 4)],
                "audit_trail": [{"at": f"{ym}-01T09:00:00Z", "actor": "system", "event": "created"}] * 4,
            }
            inv_n += 1
            invoices.append(inv)
            if status == "paid":
                ids = _DUPLICATED_MARCH.get(cid, ())[:] if (ym == "2026-03" and cid in _DUPLICATED_MARCH) else None
                for j in range(2 if ids else 1):
                    pid = ids[j] if ids else f"pay_{pay_n}"
                    pay_n += 1
                    payments[pid] = {"id": pid, "invoice_id": inv["id"], "customer_id": cid, "amount_cents": amount,
                                     "paid_at": f"{ym}-0{4 + j}", "refunded_cents": 0}
        if cid in _ANNUAL:
            iid, pid, amount, day = _ANNUAL[cid]
            invoices.append({"id": iid, "customer_id": cid, "status": "paid", "amount_cents": amount, "currency": "GBP",
                             "created_at": day, "due_at": day, "billing_address": {"line1": "1 Mill Lane", "city": "Leeds", "postcode": "LS1 4AB", "country": "GB"},
                             "line_items": [{"sku": "annual-plan", "qty": 1, "unit_cents": amount}],
                             "audit_trail": [{"at": day + "T09:00:00Z", "actor": "system", "event": "created"}] * 4})
            payments[pid] = {"id": pid, "invoice_id": iid, "customer_id": cid, "amount_cents": amount, "paid_at": day[:8] + str(int(day[8:]) + 1).zfill(2), "refunded_cents": 0}
    return customers, invoices, payments


_CUSTOMER_DATA, _INVOICE_DATA, _PAYMENT_DATA = _build()


class RefundTimeout(Exception):
    """The refund service accepted the request and then the response was lost."""


class Northwind:
    """The billing backend. One fresh instance per evaluation run."""

    def __init__(self, flaky: bool = False):
        self.customers: Dict[str, dict] = copy.deepcopy(_CUSTOMER_DATA)
        self.invoices: List[dict] = copy.deepcopy(_INVOICE_DATA)
        self.payments: Dict[str, dict] = copy.deepcopy(_PAYMENT_DATA)
        self.refunds: List[tuple] = []           # (payment_id, amount_cents), in the order money moved
        self._keys: Dict[str, dict] = {}
        self.flaky = flaky                       # the FIRST refund is applied, then the response is lost
        self._timed_out = False

    # ---- read side ----
    def match_customers(self, text: str) -> List[dict]:
        """Customers whose id or email equals `text`, or whose name contains it (any case)."""
        t = text.strip().lower()
        return [c for c in self.customers.values() if t in (c["customer_id"].lower(), c["email"].lower()) or (len(t) > 2 and t in c["name"].lower())]

    def invoices_of(self, customer_id: str) -> List[dict]:
        return sorted((i for i in self.invoices if i["customer_id"] == customer_id), key=lambda i: i["created_at"], reverse=True)

    def payments_of(self, customer_id: str) -> List[dict]:
        return sorted((p for p in self.payments.values() if p["customer_id"] == customer_id), key=lambda p: (p["paid_at"], p["id"]), reverse=True)

    # ---- write side ----
    def apply_refund(self, payment_id: str, amount_cents: int, idempotency_key: Optional[str] = None) -> Dict[str, Any]:
        """Move money. KeyError for an unknown payment, ValueError for an impossible amount.

        With an idempotency_key already seen, nothing moves and the earlier result is
        returned with replayed=True. On a flaky backend the first call that really moves
        money raises RefundTimeout AFTER the money has moved.
        """
        if idempotency_key is not None and idempotency_key in self._keys:
            return {**self._keys[idempotency_key], "replayed": True}
        p = self.payments.get(payment_id)
        if p is None:
            raise KeyError(payment_id)
        remaining = p["amount_cents"] - p["refunded_cents"]
        if not 1 <= amount_cents <= remaining:
            raise ValueError(f"amount must be between 1 and {remaining}, got {amount_cents}")
        p["refunded_cents"] += amount_cents
        self.refunds.append((payment_id, amount_cents))
        result = {"payment_id": payment_id, "amount_cents": amount_cents, "remaining_cents": remaining - amount_cents, "replayed": False}
        if idempotency_key is not None:
            self._keys[idempotency_key] = result
        if self.flaky and not self._timed_out:
            self._timed_out = True
            raise RefundTimeout("refund service timed out")
        return result


# =============================================================================
# The twenty tasks
# =============================================================================

def _task(id, intent, email, name, text, refunds=(), include=(), split="dev", flaky=False, month=None):
    return {"id": id, "intent": intent, "email": email, "name": name, "text": text, "expected_refunds": list(refunds),
            "must_include": list(include), "must_not_include": [], "split": split, "flaky": flaky, "month": month}


TASKS: List[dict] = [
    _task("T01", "owed", "ana@example.com", "Ana Silva", "Hi, Ana Silva here (ana@example.com). How much do I owe right now?", include=["£98.00"]),
    _task("T02", "owed", "ben@example.com", "Ben Okafor", "This is ben@example.com. What is my outstanding balance?", include=["£58.00"]),
    _task("T03", "owed", "chen@example.com", "Chen Wei", "chen@example.com here: how much do I owe at the moment?", include=["£30.00"], split="held"),
    _task("T04", "owed", "eli@example.com", "Eli Marsh", "eli@example.com: do I have any unpaid invoices, and how much in total?", include=["£78.00"]),
    _task("T05", "last_payment", "eli@example.com", "Eli Marsh", "eli@example.com: what was my most recent payment?", include=["£39.00", "2026-03-04"]),
    _task("T06", "last_payment", "chen@example.com", "Chen Wei", "chen@example.com: when was my last payment and how much was it?", include=["£15.00", "2026-03-05"]),
    _task("T07", "history", "ben@example.com", "Ben Okafor", "ben@example.com: what was the amount on my November 2025 invoice?", include=["£34.00"], month="2025-11"),
    _task("T08", "history", "chen@example.com", "Chen Wei", "chen@example.com: how much was my December 2025 invoice?", include=["£18.00"], month="2025-12", split="held"),
    _task("T09", "refund_duplicate", "ana@example.com", "Ana Silva", "Ana Silva (ana@example.com). I was charged twice for March. Can you refund the duplicate?",
          refunds=[("pay_88124", 4900)], include=["refund"]),
    _task("T10", "refund_duplicate", "ben@example.com", "Ben Okafor", "ben@example.com: I see two March payments. Please refund the duplicate.",
          refunds=[("pay_88302", 2900)], include=["refund"]),
    _task("T11", "refund_duplicate", "chen@example.com", "Chen Wei", "chen@example.com: my card was charged twice in March, please refund the extra one.",
          refunds=[("pay_88402", 1500)], include=["refund"]),
    _task("T12", "refund_duplicate", "dana@example.com", "Dana Petrov", "dana@example.com: March was charged twice. Refund the duplicate payment please.",
          refunds=[("pay_88502", 6900)], include=["refund"], split="held"),
    _task("T13", "refund_partial", "eli@example.com", "Eli Marsh", "eli@example.com: please refund £25 to me as a goodwill gesture on my latest payment.",
          refunds=[("pay_50080", 2500)], include=["refund"]),
    _task("T14", "refund_partial", "dana@example.com", "Dana Petrov", "dana@example.com: could you refund £25 as goodwill on my most recent payment?",
          refunds=[("pay_88502", 2500)], include=["refund"], split="held", flaky=True),
    _task("T15", "refund_cap", "chen@example.com", "Chen Wei", "chen@example.com: I want a full refund of my £250 annual payment.", include=["human"]),
    _task("T16", "refund_cap", "dana@example.com", "Dana Petrov", "dana@example.com: please refund my £180 annual plan payment in full.", include=["human"], split="held"),
    _task("T17", "unknown", "nobody@example.com", "Nobody", "nobody@example.com: what do I owe?", include=["no customer"]),
    _task("T18", "unknown", None, "Zed Quill", "Zed Quill asking about my balance, please.", include=["no customer"]),
    _task("T19", "ambiguous", None, "Ana Silva", "Ana Silva here: how much do I owe?", include=["email"]),
    _task("T20", "ambiguous_refund", None, "Ana Silva", "Ana Silva here: please refund the duplicate charge from March.", include=["email"], split="held"),
]
