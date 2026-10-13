"""Self-check for Lab 4.

    python3 check.py              # checks your starter.py
    python3 check.py solution     # checks the reference solution

Milestone 1 feeds your reader a fake socket that hands out bytes in awkward
pieces. The others start your server on a random free port in a background
thread and talk to it with raw sockets (and urllib where that is convenient).
Each milestone prints ✔ / ✘ / … (not implemented yet).
"""
import atexit
import importlib
import json
import os
import re
import shutil
import socket
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request

HOST = "127.0.0.1"
target = sys.argv[1] if len(sys.argv) > 1 else "starter"
mod = importlib.import_module(target)
results = []
server_errors = []      # exceptions raised inside server threads


class NotStarted(Exception):
    pass


threading.excepthook = lambda args: server_errors.append(args.exc_value)   # handler threads


def check(name, fn, counted=True):
    server_errors.clear()
    try:
        fn()
        print(f"  ✔ {name}")
        ok = True
    except (NotImplementedError, NotStarted) as e:
        print(f"  … {name}: not implemented yet ({e})")
        ok = False
    except Exception as e:   # AssertionError, or anything else worth seeing
        # A TODO that raised inside a server thread shows up as a dropped connection here.
        deadline = time.time() + 0.4
        while not server_errors and time.time() < deadline:
            time.sleep(0.02)
        inner = server_errors[0] if server_errors else None
        if isinstance(inner, NotImplementedError):
            print(f"  … {name}: not implemented yet ({inner})")
        elif inner is not None:
            print(f"  ✘ {name}: the server crashed with {type(inner).__name__}: {inner}")
        elif isinstance(e, AssertionError):
            print(f"  ✘ {name}: {e}")
        else:
            print(f"  ✘ {name}: {type(e).__name__}: {e}")
        ok = False
    if counted:
        results.append(ok)


def start(**kwargs):
    """Run mod.serve(port=0, ready=...) in a thread; return (port, stop_event)."""
    kwargs.setdefault("concurrent", False)    # milestones 1-5 don't depend on milestone 6
    got = {}
    ready = threading.Event()
    stop = threading.Event()

    def on_ready(port):
        got["port"] = port
        ready.set()

    def run():
        try:
            mod.serve(port=0, ready=on_ready, stop=stop, **kwargs)
        except BaseException as e:  # surface errors from the thread
            got["error"] = e
            server_errors.append(e)
            ready.set()

    threading.Thread(target=run, daemon=True).start()
    if not ready.wait(3):
        raise AssertionError("server did not call ready(port) within 3 s")
    if "error" in got:
        raise got["error"]
    return got["port"], stop


# --- helpers: a fake socket, a raw client, a request builder ---------------------------

class FakeSock:
    """recv() hands out the given chunks one by one, then b'' (the peer closed)."""

    def __init__(self, chunks):
        self.chunks = list(chunks)
        self.recvs = 0

    def recv(self, n):
        self.recvs += 1
        if self.recvs > 500:
            raise AssertionError("your reader keeps calling recv() forever; is there a size limit?")
        return self.chunks.pop(0) if self.chunks else b""

    def settimeout(self, t):
        pass


class Resp:
    def __init__(self, status, reason, headers, body):
        self.status, self.reason, self.headers, self.body = status, reason, headers, body

    @property
    def text(self):
        return self.body.decode("utf-8", "replace")


class Conn:
    """A raw TCP client that can read HTTP responses one after another."""

    def __init__(self, port, timeout=3.0):
        self.sock = socket.create_connection((HOST, port), timeout=timeout)
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.buf = b""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.sock.close()

    def send(self, data):
        self.sock.sendall(data)

    def _fill(self, what):
        try:
            chunk = self.sock.recv(65536)
        except socket.timeout:
            raise AssertionError(f"timed out waiting for {what}; got {self.buf[:200]!r} so far")
        except ConnectionResetError:
            raise AssertionError(f"connection reset while waiting for {what}; got {self.buf[:200]!r}")
        if not chunk:
            raise AssertionError(f"server closed the connection while we waited for {what}; got {self.buf[:200]!r}")
        self.buf += chunk

    def read_response(self, head_only=False):
        while b"\r\n\r\n" not in self.buf:
            self._fill("the response headers")
        head, _, self.buf = self.buf.partition(b"\r\n\r\n")
        lines = head.decode("latin-1").split("\r\n")
        m = re.match(r"HTTP/1\.[01] (\d{3}) ?(.*)$", lines[0])
        assert m, f"bad status line {lines[0]!r}"
        headers = {}
        for line in lines[1:]:
            name, colon, value = line.partition(":")
            assert colon, f"bad header line {line!r}"
            headers[name.strip().lower()] = value.strip()
        status = int(m.group(1))
        body = b""
        if not head_only and status not in (204, 304):
            assert "content-length" in headers, "response has no Content-Length, so a keep-alive client can't find its end"
            n = int(headers["content-length"])
            while len(self.buf) < n:
                self._fill("the response body")
            body, self.buf = self.buf[:n], self.buf[n:]
        return Resp(status, m.group(2), headers, body)

    def closed_by_server(self, wait=3.0):
        """True if the server closes the connection within `wait` seconds."""
        self.sock.settimeout(wait)
        try:
            while True:
                data = self.sock.recv(65536)
                if not data:
                    return True
                self.buf += data
        except socket.timeout:
            return False
        except ConnectionResetError:
            return True


def raw(method, path, headers=None, body=b"", version="HTTP/1.1", close=True, host=True):
    """Build the bytes of one request."""
    h = {}
    if host:
        h["Host"] = "localhost"
    if close:
        h["Connection"] = "close"
    if body or method in ("POST", "PUT"):
        h["Content-Length"] = str(len(body))
    h.update(headers or {})
    head = f"{method} {path} {version}\r\n" + "".join(f"{k}: {v}\r\n" for k, v in h.items()) + "\r\n"
    return head.encode("latin-1") + body


def once(port, data, head_only=False):
    """Send bytes on a fresh connection and read one response."""
    with Conn(port) as c:
        c.send(data)
        return c.read_response(head_only=head_only)


OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))   # never use a proxy


def fetch(port, path, data=None, headers=None):
    """urllib helper: returns (status, headers, body) even for 4xx/5xx."""
    req = urllib.request.Request(f"http://{HOST}:{port}{path}", data=data, headers=headers or {})
    try:
        with OPENER.open(req, timeout=3) as r:
            return r.status, r.headers, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers, e.read()


# --- a throw-away website with a secret OUTSIDE its public folder ------------------------

_site = {}


def site():
    if not _site:
        root = os.path.realpath(tempfile.mkdtemp(prefix="lab04-"))
        atexit.register(shutil.rmtree, root, True)
        pub = os.path.join(root, "site", "public")
        os.makedirs(os.path.join(pub, "sub"))
        os.makedirs(os.path.join(pub, "sub2"))
        os.makedirs(os.path.join(root, "site", "public-old"))
        files = {
            "secret.txt": b"TOP SECRET (outside everything)",
            "site/secret.txt": b"TOP SECRET (next to public/)",
            "site/public-old/loot.txt": b"TOP SECRET (sibling folder with the same prefix)",
            "site/public/index.html": b"<!doctype html><h1>tmp home</h1>",
            "site/public/style.css": b"body { color: red; }\n",
            "site/public/logo.svg": b"<svg xmlns='http://www.w3.org/2000/svg'/>",
            "site/public/app.js": b"console.log('hi')",
            "site/public/pic.png": b"\x89PNG\r\n\x1a\n" + bytes(range(256)) * 4,
            "site/public/my file.txt": "spaces and café\n".encode("utf-8"),
            "site/public/sub2/index.html": b"<h1>sub2 index</h1>",
        }
        for rel, data in files.items():
            with open(os.path.join(root, rel), "wb") as f:
                f.write(data)
        _site.update(root=root, public=pub, files=files)
    return _site


# --- Milestone 1 -----------------------------------------------------------------------

def m1():
    head = (b"GET /a/b?x=1&y=2 HTTP/1.1\r\nHost: localhost\r\nX-Thing:   spaced value  \r\n"
            b"ACCEPT: */*\r\nX-Dup: one\r\nx-dup: two")
    req = mod.parse_request(head)
    assert (req.method, req.path, req.query, req.version) == ("GET", "/a/b", "x=1&y=2", "HTTP/1.1"), \
        f"request line parsed wrongly: {(req.method, req.path, req.query, req.version)!r}"
    assert req.header("Host") == "localhost", "header('Host') should work"
    assert req.header("accept") == "*/*" and req.header("ACCEPT") == "*/*", "header names must be case-insensitive"
    assert req.header("x-thing") == "spaced value", f"header values should be stripped, got {req.header('x-thing')!r}"
    assert req.header("x-dup") == "one, two", f"repeated headers should be joined with ', ', got {req.header('x-dup')!r}"
    assert req.header("nope") is None and req.header("nope", "dflt") == "dflt", "missing header -> default"
    r10 = mod.parse_request(b"GET / HTTP/1.0")
    assert r10.version == "HTTP/1.0", "HTTP/1.0 requests need no Host header"

    bad = {
        b"GET /": 400, b"GET / HTTP/1.1 extra\r\nHost: x": 400, b"get / HTTP/1.1\r\nHost: x": 400,
        b"GET / HTTP/1.1\r\nHost: x\r\nNoColonHere": 400, b"GET / HTTP/1.1\r\nHost : x": 400,
        b"GET / HTTP/1.1": 400, b"GET / HTTP/1.1\r\nHost: x\r\n folded": 400,
        b"GET / HTTP/9.9\r\nHost: x": 505,
    }
    for data, want in bad.items():
        try:
            mod.parse_request(data)
        except mod.HttpError as e:
            assert e.status == want, f"{data!r}: expected HttpError({want}), got {e.status}"
        else:
            raise AssertionError(f"{data!r} should be rejected with {want}, but parse_request accepted it")

    # Chunks cut in awkward places, two pipelined requests in the last chunk, then EOF.
    chunks = [b"GET /x HT", b"TP/1.1\r\nHo", b"st: a\r", b"\n\r", b"\nGET /y HTTP/1.1\r\nHost: a\r\n\r\n"]
    reader = mod.RequestReader(FakeSock(chunks))
    first, second, third = reader.read_request(), reader.read_request(), reader.read_request()
    assert first is not None and first.path == "/x", f"first request wrong: {first and first.path!r}"
    assert second is not None and second.path == "/y", \
        "second request was lost: bytes after the first blank line must stay in the buffer"
    assert third is None, "at a clean end of stream read_request should return None"

    # The same head arriving one byte at a time.
    reader = mod.RequestReader(FakeSock([bytes([b]) for b in b"GET /slow HTTP/1.1\r\nHost: a\r\n\r\n"]))
    assert reader.read_request().path == "/slow", "byte-at-a-time delivery should work"

    # Limits.
    fake = FakeSock([b"GET / HTTP/1.1\r\nHost: x\r\nX-Pad: "] + [b"a" * 1000] * 400)
    try:
        mod.RequestReader(fake).read_request()
    except mod.HttpError as e:
        assert e.status == 431, f"endless headers should give 431, got {e.status}"
        assert fake.recvs <= 30, f"you kept reading ({fake.recvs} recv calls) long after the limit"
    else:
        raise AssertionError("an endless header should raise HttpError(431)")
    big = b"GET / HTTP/1.1\r\nHost: x\r\nX-Pad: " + b"a" * 10000 + b"\r\n\r\n"
    try:
        mod.RequestReader(FakeSock([big])).read_request()
    except mod.HttpError as e:
        assert e.status == 431, f"a {len(big)}-byte head arriving at once should give 431, got {e.status}"
    else:
        raise AssertionError("a head bigger than MAX_HEAD_BYTES should be rejected even if it arrives in one chunk")
    try:
        mod.RequestReader(FakeSock([b"GET / HT"])).read_request()
    except mod.HttpError as e:
        assert e.status == 400, f"EOF in the middle of a request should give 400, got {e.status}"
    else:
        raise AssertionError("EOF in the middle of a request should raise HttpError(400)")


# --- Milestone 2 -----------------------------------------------------------------------

DATE_RE = re.compile(r"^[A-Z][a-z]{2}, \d{2} [A-Z][a-z]{2} \d{4} \d{2}:\d{2}:\d{2} GMT$")


def split_wire(data):
    head, sep, body = data.partition(b"\r\n\r\n")
    assert sep, "a response needs a blank line (\\r\\n\\r\\n) after its headers"
    lines = head.decode("latin-1").split("\r\n")
    headers = {}
    for line in lines[1:]:
        k, _, v = line.partition(":")
        headers[k.strip().lower()] = v.strip()
    return lines[0], headers, body


def m2():
    body = "héllo ☃".encode("utf-8")
    wire = mod.render_response(mod.Response(200, body, {"Content-Type": "text/plain; charset=utf-8"}))
    status_line, h, b = split_wire(wire)
    assert status_line == "HTTP/1.1 200 OK", f"status line should be 'HTTP/1.1 200 OK', got {status_line!r}"
    assert h.get("content-length") == str(len(body)), \
        f"Content-Length must count BYTES ({len(body)}), got {h.get('content-length')!r}"
    assert b == body, "body should follow the blank line unchanged"
    assert h.get("connection") == "keep-alive", "keep_alive=True -> Connection: keep-alive"
    assert DATE_RE.match(h.get("date", "")), f"Date should look like 'Mon, 12 Oct 2026 09:30:00 GMT', got {h.get('date')!r}"
    assert h.get("content-type") == "text/plain; charset=utf-8", "Content-Type should be sent"
    status_line, h, b = split_wire(mod.render_response(mod.Response(404, b"nope"), keep_alive=False))
    assert status_line == "HTTP/1.1 404 Not Found", f"got {status_line!r}"
    assert h.get("connection") == "close", "keep_alive=False -> Connection: close"
    assert "content-type" in h, "give every response a Content-Type (default text/plain)"
    status_line, h, b = split_wire(mod.render_response(mod.Response(200, b"abcdef"), head_only=True))
    assert h.get("content-length") == "6" and b == b"", "HEAD: Content-Length of the full body, but no body bytes"
    for code, reason in [(201, "Created"), (400, "Bad Request"), (405, "Method Not Allowed"), (500, "Internal Server Error")]:
        sl, _, _ = split_wire(mod.render_response(mod.error_response(code)))
        assert sl == f"HTTP/1.1 {code} {reason}", f"expected reason phrase {reason!r}, got {sl!r}"
    e = mod.error_response(404, "no such file")
    assert e.status == 404 and b"404" in e.body, "error_response(404) should build a 404 Response with a readable body"
    req = mod.Request("DELETE", "/x", "HTTP/1.1", {"host": "a"})
    try:
        mod.require_method(req, "GET", "HEAD")
    except mod.HttpError as err:
        assert err.status == 405, f"wrong method should be 405, got {err.status}"
        allow = [t.strip() for t in err.headers.get("Allow", "").split(",")]
        assert allow == ["GET", "HEAD"], f"405 must carry Allow: GET, HEAD (got {err.headers!r})"
    else:
        raise AssertionError("require_method should raise HttpError(405) for a method that isn't allowed")
    mod.require_method(mod.Request("GET", "/x", "HTTP/1.1", {"host": "a"}), "GET", "HEAD")   # must not raise

    port, stop = start()
    try:
        r = once(port, raw("GET", "/hello"))
        assert r.status == 200 and r.text == "Hello from lab 4!\n", f"GET /hello -> {r.status} {r.body!r}"
        r = once(port, raw("POST", "/hello"))
        assert r.status == 405, f"POST /hello should be 405, got {r.status}"
        allow = {t.strip() for t in r.headers.get("allow", "").split(",")}
        assert {"GET", "HEAD"} <= allow, f"405 needs an Allow header listing GET and HEAD, got {r.headers.get('allow')!r}"
        r = once(port, raw("GET", "/boom"))
        assert r.status == 500, f"a crashing handler should become a 500, got {r.status}"
        with Conn(port) as c:                                    # garbage instead of a request
            c.send(b"THIS IS NOT HTTP\r\n\r\n")
            r = c.read_response()
            assert r.status == 400, f"garbage should get 400, got {r.status}"
        r = once(port, raw("GET", "/hello", host=False))
        assert r.status == 400, f"HTTP/1.1 without Host should be 400, got {r.status}"
        with Conn(port) as c:                                    # 505 for versions we don't speak
            c.send(b"GET /hello HTTP/3.0\r\nHost: x\r\n\r\n")
            assert c.read_response().status == 505, "unsupported HTTP version should be 505"
        with Conn(port) as c:                                    # oversized headers
            c.send(b"GET /hello HTTP/1.1\r\nHost: x\r\nX-Pad: " + b"a" * 20000 + b"\r\n\r\n")
            assert c.read_response().status == 431, "oversized headers should be answered with 431"
    finally:
        stop.set()


# --- Milestone 3 -----------------------------------------------------------------------

def m3():
    assert mod.guess_type("/x/y.html").startswith("text/html"), "html -> text/html"
    assert mod.guess_type("a.CSS").startswith("text/css"), "extensions are case-insensitive"
    assert mod.guess_type("logo.svg") == "image/svg+xml", "svg -> image/svg+xml"
    assert mod.guess_type("pic.png") == "image/png", "png -> image/png"
    assert mod.guess_type("mystery.xyz") == "application/octet-stream", "unknown -> application/octet-stream"
    s = site()
    ok = mod.resolve_path(s["public"], "/style.css")
    assert os.path.realpath(ok) == os.path.join(s["public"], "style.css"), f"resolve_path gave {ok!r}"
    for evil in ("/../secret.txt", "/%2e%2e/secret.txt", "/a/../../secret.txt"):
        try:
            got = mod.resolve_path(s["public"], evil)
        except mod.HttpError:
            continue
        raise AssertionError(f"resolve_path accepted {evil!r} and returned {got!r}")

    port, stop = start(public_dir=s["public"])
    try:
        r = once(port, raw("GET", "/"))
        assert r.status == 200 and r.body == s["files"]["site/public/index.html"], \
            f"GET / should serve index.html, got {r.status} {r.body[:60]!r}"
        assert r.headers.get("content-type", "").startswith("text/html"), f"index Content-Type: {r.headers.get('content-type')!r}"
        for path, ctype, key in [("/style.css", "text/css", "style.css"), ("/logo.svg", "image/svg+xml", "logo.svg"),
                                 ("/app.js", "javascript", "app.js"), ("/pic.png", "image/png", "pic.png")]:
            r = once(port, raw("GET", path))
            assert r.status == 200, f"GET {path} -> {r.status}"
            assert ctype in r.headers.get("content-type", ""), f"{path} Content-Type {r.headers.get('content-type')!r}"
            assert r.body == s["files"]["site/public/" + key], f"{path}: body differs (binary files must be sent as bytes)"
        r = once(port, raw("GET", "/my%20file.txt"))
        assert r.status == 200 and r.body == s["files"]["site/public/my file.txt"], \
            f"%20 should decode to a space; GET /my%20file.txt -> {r.status}"
        assert once(port, raw("GET", "/sub2/")).body == s["files"]["site/public/sub2/index.html"], "/sub2/ should serve sub2/index.html"
        r = once(port, raw("GET", "/missing.html"))
        assert r.status == 404, f"missing file should be 404, got {r.status}"
        r = once(port, raw("GET", "/sub/"))
        assert r.status == 404, f"a folder without index.html should be 404, got {r.status}"
        r = once(port, raw("POST", "/index.html"))
        assert r.status == 405 and "GET" in r.headers.get("allow", ""), f"POST to a file: 405 + Allow, got {r.status} {r.headers.get('allow')!r}"

        # HEAD: same headers as GET, no body.
        g = once(port, raw("GET", "/style.css"))
        with Conn(port) as c:
            c.send(raw("HEAD", "/style.css"))
            h = c.read_response(head_only=True)
            assert h.status == 200, f"HEAD -> {h.status}"
            assert h.headers.get("content-length") == g.headers["content-length"], "HEAD must report the same Content-Length as GET"
            assert h.headers.get("content-type") == g.headers["content-type"], "HEAD must report the same Content-Type as GET"
            assert c.closed_by_server(), "server should close after 'Connection: close'"
            assert c.buf == b"", f"HEAD responses must not contain a body, but {len(c.buf)} extra bytes arrived"

        # Path traversal: none of these may leak a secret.
        secret_abs = os.path.join(s["root"], "secret.txt")
        evil_paths = [
            "/../secret.txt", "/../../secret.txt", "/%2e%2e/secret.txt", "/%2E%2E/secret.txt",
            "/..%2fsecret.txt", "/%2e%2e%2fsecret.txt", "/a/../../secret.txt", "/sub/../../secret.txt",
            "/../public-old/loot.txt", "/%2e%2e/public-old/loot.txt", "/....//secret.txt",
            "/..%5csecret.txt", "/index.html%00.txt", secret_abs, "/" + secret_abs,
        ]
        for p in evil_paths:
            with Conn(port) as c:
                c.send(f"GET {p} HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n".encode("latin-1"))
                r = c.read_response()
            assert b"TOP SECRET" not in r.body, f"PATH TRAVERSAL: GET {p} leaked a secret file!"
            assert r.status in (400, 403, 404), f"GET {p} should be refused (400/403/404), got {r.status}"
        # Same thing through urllib (which will not send raw ".." for us, but does send %2e%2e).
        status, _, body = fetch(port, "/%2e%2e/secret.txt")
        assert status in (400, 403, 404) and b"TOP SECRET" not in body, "urllib: encoded traversal must be refused"
    finally:
        stop.set()

    # The real sample site shipped with the lab.
    pub = getattr(mod, "PUBLIC_DIR", None)
    assert pub and os.path.isfile(os.path.join(pub, "index.html")), "public/index.html should exist next to the lab files"
    port, stop = start()
    try:
        status, hdrs, body = fetch(port, "/")
        assert status == 200 and b"<html" in body.lower(), "GET / on the real public/ folder"
        assert hdrs.get("Content-Type", "").startswith("text/html"), "index.html is text/html"
        assert fetch(port, "/style.css")[1].get("Content-Type", "").startswith("text/css"), "style.css is text/css"
        assert fetch(port, "/logo.svg")[1].get("Content-Type") == "image/svg+xml", "logo.svg is image/svg+xml"
        assert fetch(port, "/nothing-here")[0] == 404, "unknown URL -> 404"
    finally:
        stop.set()


# --- Milestone 4 -----------------------------------------------------------------------

def m4():
    JSON = {"Content-Type": "application/json"}
    req = mod.Request("POST", "/api/echo", "HTTP/1.1", {"content-type": "application/json; charset=utf-8"}, b'{"a": [1, 2]}')
    assert mod.parse_json_body(req) == {"a": [1, 2]}, "parse_json_body should return the decoded object"
    for ctype, body, want in [("application/json", b"{oops", 400), ("application/json", b"\xff\xfe", 400),
                              ("text/plain", b'{"a": 1}', 415), (None, b'{"a": 1}', 415)]:
        headers = {"content-type": ctype} if ctype else {}
        try:
            mod.parse_json_body(mod.Request("POST", "/x", "HTTP/1.1", headers, body))
        except mod.HttpError as e:
            assert e.status == want, f"{ctype!r} {body!r}: expected {want}, got {e.status}"
        else:
            raise AssertionError(f"{ctype!r} {body!r} should be rejected with {want}")

    # Bodies through the reader: split across chunks, then a pipelined request right behind.
    payload = "héllo".encode("utf-8")
    head = b"POST /api/echo HTTP/1.1\r\nHost: x\r\nContent-Length: " + str(len(payload)).encode() + b"\r\n\r\n"
    nxt = b"GET /after HTTP/1.1\r\nHost: x\r\n\r\n"
    reader = mod.RequestReader(FakeSock([head + payload[:2], payload[2:3], payload[3:] + nxt]))
    r1, r2 = reader.read_request(), reader.read_request()
    assert r1.body == payload, f"body should be exactly Content-Length bytes, got {r1.body!r}"
    assert r2 is not None and r2.path == "/after" and r2.body == b"", "the request after a body was lost or got body bytes mixed in"
    for data, want in [(head + payload[:2], 400),   # EOF in the middle of the body
                       (b"POST / HTTP/1.1\r\nHost: x\r\nContent-Length: abc\r\n\r\n", 400),
                       (b"POST / HTTP/1.1\r\nHost: x\r\nContent-Length: -5\r\n\r\n", 400),
                       (b"POST / HTTP/1.1\r\nHost: x\r\nContent-Length: 99999999\r\n\r\n", 413)]:
        try:
            mod.RequestReader(FakeSock([data])).read_request()
        except mod.HttpError as e:
            assert e.status == want, f"{data[-40:]!r}: expected {want}, got {e.status}"
        else:
            raise AssertionError(f"{data[-40:]!r} should be rejected with {want}")

    port, stop = start()
    try:
        obj = {"msg": "héllo ☃", "n": [1, 2, 3]}
        body = json.dumps(obj).encode("utf-8")
        with Conn(port) as c:     # headers and body in separate TCP segments, body in two pieces
            c.send(raw("POST", "/api/echo", JSON, body)[:-len(body)])
            time.sleep(0.1)
            c.send(body[:7])
            time.sleep(0.1)
            c.send(body[7:])
            r = c.read_response()
        assert r.status == 200, f"POST /api/echo -> {r.status} {r.text!r}"
        assert r.headers.get("content-type", "").startswith("application/json"), "JSON replies need Content-Type: application/json"
        reply = json.loads(r.text)
        assert reply == {"you_sent": obj, "bytes": len(body)}, f"unexpected echo reply {reply!r}"
        assert once(port, raw("POST", "/api/echo", JSON, b"{broken")).status == 400, "invalid JSON -> 400"
        assert once(port, raw("POST", "/api/echo", {"Content-Type": "application/x-www-form-urlencoded"}, b"a=1")).status == 415, \
            "non-JSON Content-Type -> 415"
        r = once(port, raw("GET", "/api/echo"))
        assert r.status == 405 and "POST" in r.headers.get("allow", ""), f"GET /api/echo: 405 + Allow: POST, got {r.status}"
        r = once(port, raw("POST", "/hello", body=b"x" * 5000))
        assert r.status == 405, "a POST body must be read (and ignored) even when the route says 405"
        with Conn(port) as c:     # claims a huge body: refuse without reading it
            c.send(b"POST /api/echo HTTP/1.1\r\nHost: x\r\nContent-Type: application/json\r\nContent-Length: 99999999\r\nConnection: close\r\n\r\n")
            assert c.read_response().status == 413, "an enormous Content-Length should be 413"

        mod.GUESTBOOK.clear()
        status, hdrs, data = fetch(port, "/api/guestbook", json.dumps({"name": "Ada", "message": "first!"}).encode(), JSON)
        assert status == 201, f"POST /api/guestbook -> {status} {data!r}"
        status, hdrs, data = fetch(port, "/api/guestbook")
        entries = json.loads(data)["entries"]
        assert [e["name"] for e in entries] == ["Ada"] and entries[0]["message"] == "first!", f"guestbook GET gave {entries!r}"
        status, _, _ = fetch(port, "/api/guestbook", b'{"name": 5}', JSON)
        assert status == 400, f"guestbook entry without a proper name/message -> 400, got {status}"
    finally:
        stop.set()


# --- Milestone 5 -----------------------------------------------------------------------

def m5():
    def rq(version, **hdr):
        return mod.Request("GET", "/", version, {k.replace("_", "-"): v for k, v in hdr.items()})
    assert mod.wants_keep_alive(rq("HTTP/1.1")) is True, "HTTP/1.1 defaults to keep-alive"
    assert mod.wants_keep_alive(rq("HTTP/1.1", connection="Close")) is False, "'Connection: Close' (any case) ends it"
    assert mod.wants_keep_alive(rq("HTTP/1.0")) is False, "HTTP/1.0 defaults to close"
    assert mod.wants_keep_alive(rq("HTTP/1.0", connection="Keep-Alive")) is True, "HTTP/1.0 can opt in"

    port, stop = start()
    try:
        with Conn(port) as c:                    # two requests, one connection
            c.send(raw("GET", "/hello", close=False))
            r1 = c.read_response()
            assert r1.status == 200 and r1.headers.get("connection") == "keep-alive", \
                f"first response: {r1.status}, Connection: {r1.headers.get('connection')!r}"
            c.send(raw("GET", "/nothing-here", close=False))
            r2 = c.read_response()
            assert r2.status == 404, f"second request on the same connection got {r2.status}"
            c.send(raw("GET", "/hello", close=False))
            assert c.read_response().status == 200, "the connection should survive an error response"
            c.send(raw("GET", "/hello", close=True))
            r4 = c.read_response()
            assert r4.headers.get("connection") == "close", "answer 'Connection: close' with 'Connection: close'"
            assert c.closed_by_server(), "server must close the connection after 'Connection: close'"
        with Conn(port) as c:                    # HTTP/1.0 closes by default
            c.send(b"GET /hello HTTP/1.0\r\n\r\n")
            assert c.read_response().status == 200
            assert c.closed_by_server(), "HTTP/1.0 without keep-alive should be closed after one response"

        # Pipelining: five requests at once, then the same bytes dribbled out 7 at a time.
        echo = b'{"a": 1}'
        reqs = [raw("GET", "/hello", close=False),
                raw("POST", "/api/echo", {"Content-Type": "application/json"}, echo, close=False),
                raw("GET", "/definitely-missing", close=False),
                raw("HEAD", "/hello", close=False),
                raw("POST", "/hello", body=b"unread body?", close=False),
                raw("GET", "/hello", close=True)]
        expect = [200, 200, 404, 200, 405, 200]
        heads = [False, False, False, True, False, False]
        blob = b"".join(reqs)
        for mode in ("all at once", "7 bytes at a time"):
            with Conn(port) as c:
                if mode == "all at once":
                    c.send(blob)
                else:
                    for i in range(0, len(blob), 7):
                        c.send(blob[i:i + 7])
                        time.sleep(0.002)
                got = [c.read_response(head_only=h).status for h in heads]
                assert got == expect, f"pipelined requests ({mode}): expected statuses {expect}, got {got}"
                assert c.closed_by_server(), f"({mode}) closed after the last 'Connection: close' request"
    finally:
        stop.set()

    port, stop = start(idle_timeout=0.6)         # idle timeout
    try:
        with Conn(port) as c:
            t0 = time.time()
            c.send(raw("GET", "/hello", close=False))
            assert c.read_response().status == 200
            assert c.closed_by_server(wait=4), "an idle keep-alive connection should be closed by the server"
            waited = time.time() - t0
            assert 0.3 < waited < 3.5, f"idle connection closed after {waited:.2f} s; expected about 0.6 s"
        with Conn(port) as c:                    # half a request, then silence
            c.send(b"GET /hello HTT")
            assert c.closed_by_server(wait=4), "a stalled half-request should not hold the connection forever"
            if c.buf:
                assert c.buf.startswith(b"HTTP/1.1 408"), f"if you answer a stalled request, use 408; got {c.buf[:30]!r}"
    finally:
        stop.set()


# --- Milestone 6 -----------------------------------------------------------------------

def m6():
    port, stop = start(concurrent=True)
    try:
        a = Conn(port)
        try:
            a.send(b"GET /hello HTTP/1.1\r\nHo")          # client A stalls half-way through its request
            time.sleep(0.2)
            try:
                b = once(port, raw("GET", "/hello"))
            except AssertionError as e:
                raise AssertionError("a second client was not served while the first one sat idle; "
                                     f"are you still handling one connection at a time? ({e})")
            assert b.status == 200, f"client B got {b.status}"
            a.send(b"st: x\r\nConnection: close\r\n\r\n")      # now A finishes
            assert a.read_response().status == 200, "client A should still be answered after B was served"
        finally:
            a.sock.close()

        # 16 clients, all connected and kept alive at the same time.
        n = 16
        mod.GUESTBOOK.clear()
        barrier = threading.Barrier(n)
        errors = []

        def client(i):
            try:
                with Conn(port, timeout=5) as c:
                    c.send(raw("GET", "/hello", close=False))
                    assert c.read_response().status == 200
                    barrier.wait(5)                              # everyone is connected right now
                    body = json.dumps({"name": f"user{i}", "message": "hi"}).encode()
                    c.send(raw("POST", "/api/guestbook", {"Content-Type": "application/json"}, body, close=True))
                    assert c.read_response().status == 201
            except BaseException as e:
                errors.append(f"client {i}: {type(e).__name__}: {e}")

        threads = [threading.Thread(target=client, args=(i,)) for i in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(10)
        assert not errors, "concurrent clients failed: " + errors[0]
        status, _, data = fetch(port, "/api/guestbook")
        names = sorted(e["name"] for e in json.loads(data)["entries"])
        assert len(names) == n and len(set(names)) == n, f"expected {n} guestbook entries, got {len(names)}: {names}"
        ids = sorted(e["id"] for e in json.loads(data)["entries"])
        assert ids == list(range(1, n + 1)), f"entry ids should be 1..{n} with no duplicates, got {ids}"
    finally:
        stop.set()


# --- Stretch (not counted) -------------------------------------------------------------

def stretch():
    s = site()
    port, stop = start(public_dir=s["public"])
    try:
        g = once(port, raw("GET", "/style.css"))
        etag = g.headers.get("etag")
        if not etag:
            raise NotStarted("no ETag header yet")
        assert etag.startswith('"') and etag.endswith('"'), f"an ETag is a quoted string, got {etag!r}"
        r = once(port, raw("GET", "/style.css", {"If-None-Match": etag}))
        assert r.status == 304 and r.body == b"", f"matching If-None-Match should give an empty 304, got {r.status}"
        assert r.headers.get("etag") == etag, "a 304 should repeat the ETag"
        r = once(port, raw("GET", "/style.css", {"If-None-Match": '"nope", W/' + etag}))
        assert r.status == 304, "If-None-Match may list several ETags (and weak ones)"
        r = once(port, raw("GET", "/style.css", {"If-None-Match": '"stale"'}))
        assert r.status == 200 and r.body == g.body, "a non-matching ETag must get the full file"
        with open(os.path.join(s["public"], "style.css"), "wb") as f:
            f.write(b"body { color: blue; }\n")
        r = once(port, raw("GET", "/style.css", {"If-None-Match": etag}))
        assert r.status == 200 and b"blue" in r.body and r.headers.get("etag") != etag, "after the file changes, the ETag must change"
    finally:
        stop.set()


print(f"Lab 4 checks against {target}.py\n")
check("Milestone 1: read and parse a request (framing, limits)", m1)
check("Milestone 2: responses, status codes and headers", m2)
check("Milestone 3: static files, content types, HEAD, path traversal", m3)
check("Milestone 4: request bodies and a JSON endpoint", m4)
check("Milestone 5: keep-alive, Connection: close, idle timeout, pipelining", m5)
check("Milestone 6: concurrency (a thread per connection)", m6)
passed = sum(results)
print(f"\n{passed}/{len(results)} milestones passing" + ("  🎉 Lab complete!" if passed == len(results) else ""))
print("\nStretch goal (not counted):")
check("Stretch: conditional GET (ETag / 304)", stretch, counted=False)
sys.exit(0 if passed == len(results) else 1)
