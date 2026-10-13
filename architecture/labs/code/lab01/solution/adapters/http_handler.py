"""The HTTP adapter: translates request dicts into use-case calls and exceptions into statuses."""
import json
import re

import domain


def _header(request, name):
    return (request.get("headers") or {}).get(name)


def build_handler(place_order, get_order):
    """Return handle(request) -> (status, body). The use cases are injected."""

    def handle(request):
        method, path = request["method"], request["path"]
        m = re.match(r"^/orders/(\d+)$", path)
        if path == "/orders":
            if method != "POST":
                return 405, {"error": "method not allowed"}
            return _create(request)
        if m:
            if method != "GET":
                return 405, {"error": "method not allowed"}
            try:
                o = get_order.execute(int(m.group(1)))
            except domain.OrderNotFound as e:
                return 404, {"error": str(e)}
            return 200, {"id": o.id, "customer": o.customer, "status": o.status, "total_cents": o.total_cents,
                         "lines": [{"sku": l.sku, "qty": l.qty, "unit_price_cents": l.unit_price_cents}
                                   for l in o.lines]}
        return 404, {"error": "no such route"}

    def _create(request):
        try:
            data = json.loads(request.get("body") or "")
        except ValueError:
            return 400, {"error": "malformed request"}
        if not isinstance(data, dict):
            return 400, {"error": "malformed request"}
        try:
            order = place_order.execute(domain.parse_request(data, gift_card=_header(request, "X-Gift-Card")))
        except domain.ValidationError as e:
            return 422, {"error": str(e)}
        except domain.OutOfStock as e:
            return 409, {"error": str(e)}
        except domain.PaymentDeclined as e:
            return 402, {"error": str(e)}
        return 201, {"id": order.id, "status": order.status, "total_cents": order.total_cents}

    return handle
