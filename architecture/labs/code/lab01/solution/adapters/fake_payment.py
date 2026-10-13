"""A fake payment gateway that records every attempt and declines one magic card token."""


class FakePayment:
    def __init__(self, declined_cards=("tok_decline",)):
        self.declined_cards = set(declined_cards)
        self.charges = []                        # (customer, amount_cents), declined attempts included

    def charge(self, customer, amount_cents, card):
        self.charges.append((customer, amount_cents))
        return card not in self.declined_cards
