"""Lab 4 solution: an HTTP/1.1 server built from raw sockets.

    python3 solution.py serve                 # then open http://127.0.0.1:8080/
    python3 solution.py serve --serial        # one connection at a time (before milestone 6)

Layers, from the bottom up:
    RequestReader   bytes from the socket  ->  complete requests   (milestones 1 and 4)
    parse_request   head bytes             ->  Request             (milestone 1)
    handle_request  Request                ->  Response            (milestones 2-4)
    render_response Response               ->  bytes on the wire   (milestone 2)
    handle_connection  the loop around all of that                 (milestone 5)
    serve / spawn_handler  accept() and one thread each            (milestone 6)

Every server takes port=0 ("pick any free port") and calls ready(port) once
it is listening, so check.py can find it. Standard library only; no http.server.
"""
import argparse
import hashlib
import json
import os
import re
import socket
import threading
import time
from email.utils import formatdate
from urllib.parse import unquote

HOST = "127.0.0.1"                       # loopback: only this computer can connect
HERE = os.path.dirname(os.path.abspath(__file__))
PUBLIC_DIR = os.path.join(HERE, "public")

MAX_HEAD_BYTES = 8192                    # request line + headers must fit in this
MAX_HEADERS = 100
MAX_BODY_BYTES = 1000000                 # 1 MB
IDLE_TIMEOUT = 15.0                      # seconds a keep-alive connection may sit silent
VERBOSE = False                          # print an access log line per request

REASONS = {
    200: "OK", 201: "Created", 204: "No Content", 304: "Not Modified",
    400: "Bad Request", 403: "Forbidden", 404: "Not Found",
    405: "Method Not Allowed", 408: "Request Timeout", 413: "Payload Too Large",
    415: "Unsupported Media Type", 431: "Request Header Fields Too Large",
    500: "Internal Server Error", 501: "Not Implemented",
    505: "HTTP Version Not Supported",
}

TOKEN = re.compile(r"[!#$%&'*+\-.^_`|~0-9A-Za-z]+")   # legal characters in a header name


class HttpError(Exception):
    """Raise this anywhere to make the server answer with that status."""

    def __init__(self, status, message="", headers=None):
        super().__init__(f"{status} {message}")
        self.status = status
        self.message = message
        self.headers = headers or {}


class Request:
    def __init__(self, method, target, version, headers, body=b""):
        self.method = method                      # "GET"
        self.target = target                      # "/search?q=cats"
        self.version = version                    # "HTTP/1.1"
        self.headers = headers                    # dict, every key lower-case
        self.body = body                          # bytes
        self.path, _, self.query = target.partition("?")

    def header(self, name, default=None):
        """Case-insensitive header lookup: req.header("Content-Type")."""
        return self.headers.get(name.lower(), default)


class Response:
    def __init__(self, status=200, body=b"", headers=None):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.status = status
        self.body = body
        self.headers = headers or {}


def text_response(text, status=200, headers=None):
    h = {"Content-Type": "text/plain; charset=utf-8"}
    h.update(headers or {})
    return Response(status, text, h)


def json_response(obj, status=200, headers=None):
    h = {"Content-Type": "application/json"}
    h.update(headers or {})
    return Response(status, json.dumps(obj) + "\n", h)


# ---------------------------------------------------------------------------
# Milestone 1: read a request.
# ---------------------------------------------------------------------------

def parse_request(head):
    """Turn the head (request line + headers, without the final blank line)
    into a Request, or raise HttpError(400/431/505)."""
    lines = head.decode("latin-1").split("\r\n")      # latin-1 never fails on any byte
    parts = lines[0].split(" ")
    if len(parts) != 3 or not all(parts):
        raise HttpError(400, "malformed request line")
    method, target, version = parts
    if not re.fullmatch(r"[A-Z]+", method):
        raise HttpError(400, "malformed method")
    if not target.startswith("/"):
        raise HttpError(400, "request target must start with /")
    if not version.startswith("HTTP/"):
        raise HttpError(400, "malformed version")
    if version not in ("HTTP/1.0", "HTTP/1.1"):
        raise HttpError(505, "only HTTP/1.0 and HTTP/1.1")

    if len(lines) - 1 > MAX_HEADERS:
        raise HttpError(431, "too many headers")
    headers = {}
    for line in lines[1:]:
        if line[:1] in (" ", "\t"):
            raise HttpError(400, "obsolete header folding is not accepted")
        name, colon, value = line.partition(":")
        if not colon or not TOKEN.fullmatch(name):     # also rejects "Name : value"
            raise HttpError(400, f"malformed header line {line[:40]!r}")
        name = name.lower()                            # names are case-insensitive
        value = value.strip(" \t")
        headers[name] = f"{headers[name]}, {value}" if name in headers else value

    if version == "HTTP/1.1" and "host" not in headers:
        raise HttpError(400, "HTTP/1.1 requires a Host header")
    return Request(method, target, version, headers)


class RequestReader:
    """Pulls requests out of a socket. Bytes that belong to the NEXT request
    (pipelining!) stay in self.buf until the next call."""

    def __init__(self, sock):
        self.sock = sock
        self.buf = b""

    def _fill(self):
        chunk = self.sock.recv(4096)
        if not chunk:
            return False                   # the peer closed the connection
        self.buf += chunk
        return True

    def read_head(self):
        """Return the head bytes (without the final \\r\\n\\r\\n), or None if the
        client closed cleanly before sending anything. Raise HttpError(431) when
        the head is bigger than MAX_HEAD_BYTES and HttpError(400) if the client
        hangs up half-way through."""
        while True:
            end = self.buf.find(b"\r\n\r\n")           # may straddle two recv() chunks
            if end != -1:
                break
            if len(self.buf) > MAX_HEAD_BYTES:         # no end in sight: stop buffering
                raise HttpError(431, "request headers too large")
            if not self._fill():
                if not self.buf:
                    return None
                raise HttpError(400, "connection closed in the middle of a request")
        if end > MAX_HEAD_BYTES:
            raise HttpError(431, "request headers too large")
        head = self.buf[:end]
        self.buf = self.buf[end + 4:]                  # keep whatever follows
        return head

    def read_body(self, n):
        """Return exactly n body bytes (milestone 4)."""
        while len(self.buf) < n:
            if not self._fill():
                raise HttpError(400, "connection closed before the whole body arrived")
        body, self.buf = self.buf[:n], self.buf[n:]
        return body

    def read_request(self):
        """Head, then body. Returns a Request, or None at a clean end of stream."""
        head = self.read_head()
        if head is None:
            return None
        request = parse_request(head)
        if "transfer-encoding" in request.headers:
            raise HttpError(501, "chunked request bodies are not supported")
        length = request.header("content-length")
        n = 0
        if length is not None:
            if not re.fullmatch(r"[0-9]+", length):
                raise HttpError(400, "bad Content-Length")
            n = int(length)
            if n > MAX_BODY_BYTES:
                raise HttpError(413, "body too large")
        request.body = self.read_body(n) if n else b""
        return request


# ---------------------------------------------------------------------------
# Milestone 2: send a response.
# ---------------------------------------------------------------------------

def render_response(response, head_only=False, keep_alive=True):
    """Response -> the exact bytes to put on the wire."""
    headers = {k: v for k, v in response.headers.items()
               if k.lower() not in ("content-length", "connection", "date")}
    bodyless = response.status in (204, 304) or 100 <= response.status < 200
    if not bodyless:
        headers["Content-Length"] = str(len(response.body))      # BYTES, not characters
        if "content-type" not in {k.lower() for k in headers}:
            headers["Content-Type"] = "text/plain; charset=utf-8"
    headers["Date"] = formatdate(usegmt=True)                    # e.g. Mon, 12 Oct 2026 09:30:00 GMT
    headers["Connection"] = "keep-alive" if keep_alive else "close"
    headers["Server"] = "lab04-httpd"

    reason = REASONS.get(response.status, "Unknown")
    lines = [f"HTTP/1.1 {response.status} {reason}"]
    for name, value in headers.items():
        if "\r" in value or "\n" in value:                       # header injection
            raise ValueError(f"newline in header {name}")
        lines.append(f"{name}: {value}")
    out = ("\r\n".join(lines) + "\r\n\r\n").encode("latin-1")
    if not head_only and not bodyless:
        out += response.body                                     # HEAD: same headers, no body
    return out


def error_response(status, detail="", headers=None):
    reason = REASONS.get(status, "Error")
    body = f"{status} {reason}\n{detail}\n" if detail else f"{status} {reason}\n"
    return text_response(body, status, headers)


def require_method(request, *allowed):
    """405 Method Not Allowed, with the Allow header the spec demands."""
    if request.method not in allowed:
        raise HttpError(405, f"{request.method} is not allowed here",
                        {"Allow": ", ".join(allowed)})


def handle_request(request, public_dir):
    """The router: pick a handler by path. Handlers return a Response or raise HttpError."""
    if request.path == "/hello":
        require_method(request, "GET", "HEAD")
        return text_response("Hello from lab 4!\n")
    if request.path == "/boom":
        raise RuntimeError("deliberate bug, to exercise the 500 path")
    if request.path == "/api/echo":
        return api_echo(request)
    if request.path == "/api/guestbook":
        return api_guestbook(request)
    return serve_static(request, public_dir)


# ---------------------------------------------------------------------------
# Milestone 3: static files.
# ---------------------------------------------------------------------------

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".htm": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json",
    ".txt": "text/plain; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".ico": "image/x-icon",
}


def guess_type(path):
    ext = os.path.splitext(path)[1].lower()
    return CONTENT_TYPES.get(ext, "application/octet-stream")   # unknown: "just bytes"


def resolve_path(public_dir, url_path):
    """Map a URL path to a real file path INSIDE public_dir, or raise HttpError."""
    try:
        rel = unquote(url_path, errors="strict")        # %2e%2e is ".." too: decode FIRST
    except UnicodeDecodeError:
        raise HttpError(400, "bad percent-encoding")
    if "\x00" in rel:
        raise HttpError(400, "bad path")
    root = os.path.realpath(public_dir)
    # lstrip("/"): os.path.join(root, "/etc/passwd") would throw root away!
    candidate = os.path.realpath(os.path.join(root, rel.lstrip("/")))   # resolves .. and symlinks
    try:
        inside = os.path.commonpath([root, candidate]) == root          # not str.startswith()
    except ValueError:                                  # e.g. different drives on Windows
        inside = False
    if not inside:
        raise HttpError(403, "that path is outside the public folder")
    return candidate


def etag_for(body):
    return '"' + hashlib.sha1(body).hexdigest()[:16] + '"'


def etag_matches(header_value, etag):
    """Does an If-None-Match header list this ETag (or *)?"""
    for item in header_value.split(","):
        item = item.strip()
        if item.startswith("W/"):
            item = item[2:]
        if item == "*" or item == etag:
            return True
    return False


def serve_static(request, public_dir):
    require_method(request, "GET", "HEAD")
    path = resolve_path(public_dir, request.path)
    if os.path.isdir(path):
        path = os.path.join(path, "index.html")
    try:
        with open(path, "rb") as f:
            body = f.read()
    except (FileNotFoundError, IsADirectoryError, NotADirectoryError):
        raise HttpError(404, "no such file")
    headers = {"Content-Type": guess_type(path)}

    # --- stretch: conditional GET -------------------------------------------
    etag = etag_for(body)
    headers["ETag"] = etag
    headers["Cache-Control"] = "no-cache"               # "you may keep it, but ask me first"
    inm = request.header("if-none-match")
    if inm and etag_matches(inm, etag):
        return Response(304, b"", {"ETag": etag, "Cache-Control": "no-cache"})
    # --------------------------------------------------------------------------
    return Response(200, body, headers)


# ---------------------------------------------------------------------------
# Milestone 4: request bodies and a JSON API.
# ---------------------------------------------------------------------------

def parse_json_body(request):
    """The body as a Python object, or HttpError 415 (wrong type) / 400 (bad JSON)."""
    ctype = request.header("content-type", "").split(";")[0].strip().lower()
    if ctype != "application/json":
        raise HttpError(415, "send the header Content-Type: application/json")
    try:
        return json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise HttpError(400, "the body is not valid JSON")


def api_echo(request):
    require_method(request, "POST")
    data = parse_json_body(request)
    return json_response({"you_sent": data, "bytes": len(request.body)})


GUESTBOOK = []                       # shared by every connection thread...
GUESTBOOK_LOCK = threading.Lock()    # ...so changes to it need a lock


def api_guestbook(request):
    require_method(request, "GET", "HEAD", "POST")
    if request.method == "POST":
        data = parse_json_body(request)
        if (not isinstance(data, dict) or not isinstance(data.get("name"), str)
                or not isinstance(data.get("message"), str)):
            raise HttpError(400, 'send {"name": "...", "message": "..."}')
        entry = {"name": data["name"][:40], "message": data["message"][:200]}
        with GUESTBOOK_LOCK:
            entry["id"] = len(GUESTBOOK) + 1
            GUESTBOOK.append(entry)
        return json_response(entry, 201, {"Location": "/api/guestbook"})
    with GUESTBOOK_LOCK:
        entries = list(GUESTBOOK)
    return json_response({"entries": entries})


# ---------------------------------------------------------------------------
# Milestone 5: keep-alive.
# ---------------------------------------------------------------------------

def wants_keep_alive(request):
    """HTTP/1.1: persistent unless 'Connection: close'. HTTP/1.0: the opposite."""
    tokens = {t.strip().lower() for t in request.header("connection", "").split(",")}
    if request.version == "HTTP/1.0":
        return "keep-alive" in tokens
    return "close" not in tokens


def close_politely(conn):
    """Say 'I'm done sending' (FIN), then swallow whatever the client is still
    sending for a moment. Closing a socket that has unread data makes the OS send
    a reset (RST), which can destroy the response we just wrote before the client
    has read it."""
    try:
        conn.shutdown(socket.SHUT_WR)
        deadline = time.monotonic() + 1.0
        conn.settimeout(0.3)
        total = 0
        while total < 65536 and time.monotonic() < deadline:
            data = conn.recv(4096)
            if not data:
                break
            total += len(data)
    except OSError:
        pass
    finally:
        conn.close()


def log(addr, request, status):
    if VERBOSE:
        who = f"{addr[0]}:{addr[1]}" if addr else "-"
        print(f"[{threading.current_thread().name}] {who} {request.method} {request.target} -> {status}", flush=True)


def handle_connection(conn, public_dir=PUBLIC_DIR, idle_timeout=IDLE_TIMEOUT, addr=None):
    """Serve requests on one connection until it should close."""
    conn.settimeout(idle_timeout)                      # a silent client can't hold us forever
    reader = RequestReader(conn)
    try:
        while True:
            try:
                request = reader.read_request()
            except socket.timeout:
                if reader.buf:                          # went quiet in the middle of a request
                    conn.sendall(render_response(error_response(408), keep_alive=False))
                return
            except HttpError as e:                      # unparseable: framing is lost, so close
                response = error_response(e.status, e.message, e.headers)
                conn.sendall(render_response(response, keep_alive=False))
                return
            if request is None:                         # client closed between requests
                return

            keep_alive = wants_keep_alive(request)
            try:
                response = handle_request(request, public_dir)
            except HttpError as e:
                response = error_response(e.status, e.message, e.headers)
            except NotImplementedError:
                raise                                   # an unfinished TODO should be loud
            except Exception as e:                      # a bug in OUR code: 500, keep serving
                if VERBOSE:
                    print(f"handler crashed: {type(e).__name__}: {e}", flush=True)
                response = error_response(500)
            conn.sendall(render_response(response, head_only=(request.method == "HEAD"),
                                         keep_alive=keep_alive))
            log(addr, request, response.status)
            if not keep_alive:
                return
    except OSError:                                     # reset by peer, broken pipe, ...
        pass
    finally:
        close_politely(conn)


# ---------------------------------------------------------------------------
# Milestone 6: one thread per connection.
# ---------------------------------------------------------------------------

def spawn_handler(conn, addr, public_dir, idle_timeout):
    """Start a thread that runs handle_connection for this one client."""
    t = threading.Thread(target=handle_connection, args=(conn, public_dir, idle_timeout, addr),
                         daemon=True)                   # daemon: Ctrl+C isn't blocked by idle clients
    t.start()


def serve(port=8080, ready=None, stop=None, public_dir=PUBLIC_DIR,
          idle_timeout=IDLE_TIMEOUT, concurrent=True):
    """Listen and accept forever (or until the `stop` Event is set)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((HOST, port))
        srv.listen(128)
        srv.settimeout(0.2)                             # wake up now and then to check `stop`
        real_port = srv.getsockname()[1]
        if VERBOSE:
            print(f"Serving {public_dir} on http://{HOST}:{real_port}/  (Ctrl+C to stop)", flush=True)
        if ready:
            ready(real_port)
        while stop is None or not stop.is_set():
            try:
                conn, addr = srv.accept()
            except socket.timeout:
                continue
            if concurrent:
                spawn_handler(conn, addr, public_dir, idle_timeout)
            else:
                handle_connection(conn, public_dir, idle_timeout, addr)   # blocks everyone else


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("serve")
    sp.add_argument("--port", type=int, default=8080)
    sp.add_argument("--serial", action="store_true", help="one connection at a time (no threads)")
    sp.add_argument("--idle", type=float, default=IDLE_TIMEOUT, help="idle timeout in seconds")
    args = p.parse_args()
    global VERBOSE
    VERBOSE = True
    try:
        serve(args.port, idle_timeout=args.idle, concurrent=not args.serial)
    except KeyboardInterrupt:
        print("\nbye")
    except NotImplementedError as e:
        print(f"Not written yet: {e}")


if __name__ == "__main__":
    main()
