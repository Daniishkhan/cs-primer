"""MILESTONE 3: app.py. The use cases. Allowed imports: dataclasses, typing, domain, ports.

class PlaceOrder(repo, payments, emails) with .execute(request: OrderRequest) -> Order
    1. look the requested skus up through the repository
    2. domain.build_lines, domain.price
    3. status = ON_HOLD if domain.requires_hold(total) else PAID
    4. if PAID: charge the gateway (record it even if declined); declined -> raise PaymentDeclined("payment declined")
    5. save the order through the repository (it returns the id)
    6. send the email from domain.confirmation_email
    Return the saved Order (with its id).

class GetOrder(repo) with .execute(order_id) -> Order, raising OrderNotFound("order not found").

Note the ORDER: a declined payment must leave nothing saved and nothing emailed.
"""
raise NotImplementedError("TODO milestone 3: PlaceOrder and GetOrder")
