"""Your own characterisation cases (milestone 1). check.py replays them against legacy.py
and, later, against your refactor, and requires identical answers."""
import json

CASES = [
    {"method": "POST", "path": "/orders",
     "body": json.dumps({"customer": "zoe@example.com", "items": [{"sku": "pen", "qty": 20}]})},   # bulk + shipping
    {"method": "POST", "path": "/orders",
     "body": json.dumps({"customer": "zoe@example.com", "items": [{"sku": "lamp", "qty": 8}],
                         "coupon": "WELCOME5"})},                                                  # big basket + coupon
    {"method": "POST", "path": "/orders",
     "body": json.dumps({"customer": "zoe@example.com", "items": [{"sku": "mug", "qty": 1}],
                         "coupon": "WELCOME5", "card": "tok_decline"})},                           # declined
    {"method": "GET", "path": "/orders/1", "body": None},
]
