"""The shared 'database': one dict of tables that every module reads and writes."""

db = {"products": {}, "carts": {}, "orders": {}, "payments": {}, "shipments": {}, "wallets": {}}
_seq = {"order": 0, "payment": 0, "shipment": 0}


def next_id(kind):
    _seq[kind] += 1
    return _seq[kind]


def reset():
    for table in db.values():
        table.clear()
    for kind in _seq:
        _seq[kind] = 0
