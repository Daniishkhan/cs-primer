"""MILESTONE 1. Your own characterisation cases.

Add at least 3 request dicts (same shape as in harness.py: method, path, body) that make
legacy.py answer in at least 3 DIFFERENT ways. Pick cases the given scenario does not
dwell on: a bulk line plus a coupon, a basket just under or over a threshold, a declined
card on a coupon order, and so on. check.py replays them on legacy.py now and on your
refactor in milestone 5.

Tip: `import json` and write the body as json.dumps({...}).
"""
import json

CASES = [
    # TODO milestone 1: e.g.
    # {"method": "POST", "path": "/orders",
    #  "body": json.dumps({"customer": "zoe@example.com", "items": [{"sku": "pen", "qty": 20}]})},
]
