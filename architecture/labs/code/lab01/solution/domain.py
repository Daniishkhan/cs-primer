"""domain.py: the business rules, as pure functions. Imports nothing but the standard
typing helpers: no sqlite3, no json, no http, no adapters."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional

HOLD_THRESHOLD_CENTS = 50000        # orders this big are held for review, not charged yet
COUPONS = {"WELCOME5": 500}         # code -> flat discount in cents
GIFT_CARDS = {"GIFT20": 2000, "GIFT100": 10000}   # milestone 6: code -> credit in cents


# ---- errors the outside world will want to translate ---------------------------------
class ValidationError(Exception):
    """The request is well-formed but not acceptable (HTTP 422 at the edge)."""


class UnknownSku(ValidationError):
    pass


class OutOfStock(Exception):
    """HTTP 409 at the edge."""


class PaymentDeclined(Exception):
    """HTTP 402 at the edge."""


class OrderNotFound(Exception):
    """HTTP 404 at the edge."""


# ---- value objects --------------------------------------------------------------------
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
    gift_card: Optional[str] = None    # milestone 6


@dataclass(frozen=True)
class Pricing:
    subtotal_cents: int
    discount_cents: int
    shipping_cents: int
    total_cents: int


@dataclass(frozen=True)
class Order:
    id: Optional[int]
    customer: str
    lines: tuple
    total_cents: int
    status: str


# ---- rules ----------------------------------------------------------------------------
def parse_request(data: dict, gift_card: Optional[str] = None) -> OrderRequest:
    """Validate an already-decoded request body (a dict) and turn it into an OrderRequest."""
    customer = data.get("customer")
    if not isinstance(customer, str) or not customer.strip():
        raise ValidationError("customer is required")
    raw_items = data.get("items")
    if not isinstance(raw_items, list) or not raw_items:
        raise ValidationError("an order needs at least one line")
    items, seen = [], set()
    for it in raw_items:
        if (not isinstance(it, dict) or not isinstance(it.get("sku"), str)
                or not isinstance(it.get("qty"), int) or isinstance(it.get("qty"), bool)
                or it["qty"] < 1):
            raise ValidationError("invalid line")
        if it["sku"] in seen:
            raise ValidationError("duplicate sku '%s'" % it["sku"])
        seen.add(it["sku"])
        items.append((it["sku"], it["qty"]))
    coupon = data.get("coupon")
    if coupon is not None and not isinstance(coupon, str):
        raise ValidationError("invalid coupon")
    card = data.get("card", "tok_ok")
    if not isinstance(card, str):
        raise ValidationError("invalid card")
    return OrderRequest(customer, tuple(items), coupon, card, gift_card)


def build_lines(items, products: Mapping[str, Product]) -> tuple:
    """Check each (sku, qty) against the catalogue, in order, and price it."""
    lines = []
    for sku, qty in items:
        product = products.get(sku)
        if product is None:
            raise UnknownSku("unknown sku '%s'" % sku)
        if qty > product.stock:
            raise OutOfStock("insufficient stock for '%s'" % sku)
        lines.append(Line(sku, qty, product.price_cents))
    return tuple(lines)


def price(lines, request: OrderRequest) -> Pricing:
    subtotal = sum(l.qty * l.unit_price_cents for l in lines)
    bulk = sum((l.qty * l.unit_price_cents) * 10 // 100 for l in lines if l.qty >= 10)
    after = subtotal - bulk
    coupon_off = 0
    if request.coupon is not None:
        if request.coupon not in COUPONS:
            raise ValidationError("unknown coupon '%s'" % request.coupon)
        coupon_off = min(COUPONS[request.coupon], after)
    after -= coupon_off
    big_off = after * 5 // 100 if after >= 20000 else 0
    after -= big_off
    shipping = 499 if after < 5000 else 0
    total = after + shipping
    gift_off = 0
    if request.gift_card is not None:                                   # milestone 6
        if request.gift_card not in GIFT_CARDS:
            raise ValidationError("unknown gift card '%s'" % request.gift_card)
        gift_off = min(GIFT_CARDS[request.gift_card], total)
    return Pricing(subtotal, bulk + coupon_off + big_off + gift_off, shipping, total - gift_off)


def requires_hold(total_cents: int) -> bool:
    return total_cents >= HOLD_THRESHOLD_CENTS


def confirmation_email(order: Order) -> tuple:
    """(subject, body) for the customer."""
    money = "%d.%02d" % (order.total_cents // 100, order.total_cents % 100)
    if order.status == "ON_HOLD":
        return ("Order #%d is on hold" % order.id,
                "Thanks %s! Your order of %s is being reviewed." % (order.customer, money))
    return ("Order #%d confirmed" % order.id,
            "Thanks %s! We charged %s." % (order.customer, money))
