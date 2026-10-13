"""ports.py: what the core needs from the outside world, written as Protocols.
The core OWNS these interfaces; adapters conform to them."""
from __future__ import annotations

from typing import Optional, Protocol

from domain import Order, Product


class OrderRepository(Protocol):
    def get_product(self, sku: str) -> Optional[Product]: ...
    def save_order(self, order: Order) -> int:
        """Store the order AND decrement stock for its lines, atomically. Returns the new id (1, 2, 3...)."""
        ...
    def get_order(self, order_id: int) -> Optional[Order]: ...


class PaymentGateway(Protocol):
    def charge(self, customer: str, amount_cents: int, card: str) -> bool:
        """True if the charge succeeded, False if the card was declined."""
        ...


class EmailSender(Protocol):
    def send(self, to: str, subject: str, body: str) -> None: ...
