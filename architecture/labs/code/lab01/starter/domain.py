"""MILESTONE 2: domain.py. The business rules as PURE functions.

Allowed imports: dataclasses, typing. Nothing else: no sqlite3, no json, no http, no
adapters, no os. If a rule needs data, the caller passes it in.

Read domain_tests.py (in the lab folder) first; it is the specification. Copy each rule
out of legacy.py, keeping the exact error messages.

(The value objects are given so you can focus on the rules.)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional

HOLD_THRESHOLD_CENTS = 50000
COUPONS = {"WELCOME5": 500}


class ValidationError(Exception):
    """Well-formed but unacceptable request (HTTP 422 at the edge)."""


class UnknownSku(ValidationError):
    pass


class OutOfStock(Exception):
    """HTTP 409 at the edge."""


class PaymentDeclined(Exception):
    """HTTP 402 at the edge."""


class OrderNotFound(Exception):
    """HTTP 404 at the edge."""


@dataclass(frozen=True)
class Product:
    sku: str
    price_cents: int
    stock: int


@dataclass(frozen=True)
class Line:
    sku: str
    qty: int
    unit_price_cents: int


@dataclass(frozen=True)
class OrderRequest:
    customer: str
    items: tuple                      # ((sku, qty), ...)
    coupon: Optional[str] = None
    card: str = "tok_ok"


@dataclass(frozen=True)
class Pricing:
    subtotal_cents: int
    discount_cents: int               # bulk + coupon + big-basket, all discounts together
    shipping_cents: int
    total_cents: int


@dataclass(frozen=True)
class Order:
    id: Optional[int]
    customer: str
    lines: tuple
    total_cents: int
    status: str                       # "PAID" or "ON_HOLD"


def parse_request(data: dict) -> OrderRequest:
    """Validate an already-decoded body (a dict) and build an OrderRequest.

    Raise ValidationError(message) with the exact messages legacy.py uses:
    customer, items, each line, duplicate skus, coupon type, card type (default "tok_ok").
    """
    raise NotImplementedError("TODO milestone 2: parse_request")


def build_lines(items, products: Mapping[str, Product]) -> tuple:
    """For each (sku, qty) IN ORDER: unknown sku -> UnknownSku, qty > stock -> OutOfStock,
    otherwise a Line priced from the catalogue. Returns a tuple of Line."""
    raise NotImplementedError("TODO milestone 2: build_lines")


def price(lines, request: OrderRequest) -> Pricing:
    """Bulk 10% off lines of 10+ units, then the coupon (flat, never below zero), then 5%
    off if the basket is at least 20000 cents, then 499 shipping if under 5000. Use integer
    division exactly as legacy.py does."""
    raise NotImplementedError("TODO milestone 2: price")


def requires_hold(total_cents: int) -> bool:
    """True if the order must be held for review instead of charged."""
    raise NotImplementedError("TODO milestone 2: requires_hold")


def confirmation_email(order: Order) -> tuple:
    """(subject, body) exactly as legacy.py words them, for PAID and for ON_HOLD."""
    raise NotImplementedError("TODO milestone 2: confirmation_email")
