"""app.py: the use cases. Depends only on domain and ports."""
from __future__ import annotations

from dataclasses import replace

import domain
from ports import EmailSender, OrderRepository, PaymentGateway


class PlaceOrder:
    def __init__(self, repo: OrderRepository, payments: PaymentGateway, emails: EmailSender):
        self.repo, self.payments, self.emails = repo, payments, emails

    def execute(self, request: domain.OrderRequest) -> domain.Order:
        products = {}
        for sku, _ in request.items:
            product = self.repo.get_product(sku)
            if product is not None:
                products[sku] = product
        lines = domain.build_lines(request.items, products)
        pricing = domain.price(lines, request)
        status = "ON_HOLD" if domain.requires_hold(pricing.total_cents) else "PAID"
        if status == "PAID" and not self.payments.charge(request.customer, pricing.total_cents, request.card):
            raise domain.PaymentDeclined("payment declined")
        order = domain.Order(None, request.customer, lines, pricing.total_cents, status)
        order = replace(order, id=self.repo.save_order(order))
        subject, body = domain.confirmation_email(order)
        self.emails.send(order.customer, subject, body)
        return order


class GetOrder:
    def __init__(self, repo: OrderRepository):
        self.repo = repo

    def execute(self, order_id: int) -> domain.Order:
        order = self.repo.get_order(order_id)
        if order is None:
            raise domain.OrderNotFound("order not found")
        return order
