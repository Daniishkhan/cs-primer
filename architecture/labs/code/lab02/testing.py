"""testing.py: call a WSGI app directly. Given; no sockets involved.

    from testing import call
    r = call(app, "POST", "/v1/orders", {"customer": "ana", "items": [...]}, {"Idempotency-Key": "k1"})
    r.status, r.headers["content-type"], r.body (bytes), r.json()
"""
import json
from io import BytesIO
from wsgiref.util import setup_testing_defaults


class Response:
    def __init__(self, status, headers, body):
        self.status, self.headers, self.body = status, headers, body

    def json(self):
        return json.loads(self.body)

    def __repr__(self):
        return "<%d %s>" % (self.status, self.body[:80])


def call(app, method, path, body=None, headers=None):
    """Build an environ dict by hand, call app(environ, start_response), collect the answer.
    `body` may be a dict/list (sent as JSON), bytes/str (sent verbatim) or None."""
    if isinstance(body, (dict, list)):
        body = json.dumps(body)
    if isinstance(body, str):
        body = body.encode()
    path, _, query = path.partition("?")
    environ = {}
    setup_testing_defaults(environ)                 # fills in wsgi.* and the other required keys
    environ.update(REQUEST_METHOD=method, PATH_INFO=path, QUERY_STRING=query)
    if body is not None:
        environ.update({"wsgi.input": BytesIO(body), "CONTENT_LENGTH": str(len(body)),
                        "CONTENT_TYPE": "application/json"})
    for name, value in (headers or {}).items():
        environ["HTTP_" + name.upper().replace("-", "_")] = value
    captured = {}

    def start_response(status, response_headers, exc_info=None):
        captured["status"] = int(status.split()[0])
        captured["headers"] = {k.lower(): v for k, v in response_headers}

    chunks = app(environ, start_response)
    return Response(captured["status"], captured["headers"], b"".join(chunks))
