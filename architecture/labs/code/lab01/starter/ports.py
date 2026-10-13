"""MILESTONE 3: ports.py. What the core needs from the outside, as typing.Protocol classes.

Write three Protocols (imports allowed: typing, domain):

  OrderRepository: get_product(sku) -> Optional[Product]
                   save_order(order) -> int      (stores the order AND decrements stock
                                                   atomically; returns ids 1, 2, 3 ...)
                   get_order(order_id) -> Optional[Order]
  PaymentGateway:  charge(customer, amount_cents, card) -> bool   (False = declined)
  EmailSender:     send(to, subject, body) -> None

The core owns these interfaces. Adapters conform to them; they never import them.
"""
raise NotImplementedError("TODO milestone 3: write the three Protocols in ports.py")
