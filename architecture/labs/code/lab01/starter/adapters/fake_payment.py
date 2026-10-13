"""MILESTONE 4/5: a fake PaymentGateway.

FakePayment().charge(customer, amount_cents, card) -> bool
Record EVERY attempt, declined ones included, as (customer, amount_cents) in self.charges
(legacy.py does). Decline the card token "tok_decline" and accept everything else.
"""


class FakePayment:
    def __init__(self, declined_cards=("tok_decline",)):
        self.charges = []

    def charge(self, customer, amount_cents, card):
        raise NotImplementedError("TODO milestone 5: FakePayment.charge")
