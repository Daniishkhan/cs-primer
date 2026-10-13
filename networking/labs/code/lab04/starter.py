"""Lab 4 starter: an HTTP/1.1 server built from raw sockets.

Fill in every TODO, one milestone at a time, and run `python3 check.py` after each.

    python3 starter.py serve                 # then open http://127.0.0.1:8080/
    python3 starter.py serve --serial        # one connection at a time (before milestone 6)

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
    """Turn the head (request line + headers, WITHOUT the final blank line) into
    a Request, or raise HttpError.

    Steps:
      1. head.decode("latin-1").split("\r\n") gives the lines.
      2. Line 0 is "METHOD TARGET VERSION": split(" ") must give exactly three
         non-empty parts, else HttpError(400, ...). The method is capital letters,
         the target starts with "/", the version starts with "HTTP/". A version
         other than HTTP/1.0 or HTTP/1.1 is HttpError(505, ...).
      3. Every other line is "Name: value". Use line.partition(":"). Reject (400)
         a line with no colon, a name that doesn't fully match TOKEN (that also
         catches "Name : value"), or a line starting with a space or tab.
         Store names LOWER-CASE and values stripped of spaces/tabs. If a name
         repeats, join the values with ", ".
      4. More than MAX_HEADERS header lines: HttpError(431, ...).
      5. HTTP/1.1 requires a Host header: otherwise HttpError(400, ...).
      6. return Request(method, target, version, headers)
    """
    raise NotImplementedError("TODO milestone 1: parse_request")


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
        """Return the head bytes (everything before the first \\r\\n\\r\\n) and
        keep the bytes after it in self.buf for the next call.

        Loop: look for b"\\r\\n\\r\\n" in self.buf (the whole buffer: it may
        straddle two recv() chunks). If it's missing and self.buf is already
        longer than MAX_HEAD_BYTES, raise HttpError(431, ...); otherwise call
        self._fill(). When _fill() says the peer closed: return None if
        self.buf is empty (a clean end), else raise HttpError(400, ...).
        Also raise 431 if the head you found is itself longer than MAX_HEAD_BYTES.
        """
        raise NotImplementedError("TODO milestone 1: RequestReader.read_head")

    def read_body(self, n):
        """Return exactly n body bytes (milestone 4): use what is already in
        self.buf, _fill() until you have n, keep any extra bytes in self.buf
        (they are the start of the next request). If the peer closes first,
        raise HttpError(400, ...)."""
        raise NotImplementedError("TODO milestone 4: RequestReader.read_body")

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
    """Response -> the exact bytes to put on the wire.

    HTTP/1.1 <status> <reason>\\r\\n        reason from REASONS
    Content-Length: <len(body)>\\r\\n       BYTES, not characters
    Content-Type: ...\\r\\n                 default text/plain; charset=utf-8
    Date: ...\\r\\n                         email.utils.formatdate(usegmt=True)
    Connection: keep-alive | close\\r\\n
    <any headers in response.headers>
    \\r\\n                                 the blank line ends the headers
    <body>                                 omitted when head_only is True

    Statuses 204 and 304 have no body and no Content-Length. Encode the head
    with "latin-1" and append the body bytes. Don't let a caller's headers
    override Content-Length, Date or Connection.
    """
    raise NotImplementedError("TODO milestone 2: render_response")


def error_response(status, detail="", headers=None):
    """A small plain-text Response for an error, e.g. body "404 Not Found\\n<detail>\\n".
    Hint: text_response(...) and REASONS."""
    raise NotImplementedError("TODO milestone 2: error_response")


def require_method(request, *allowed):
    """Raise HttpError(405, ..., {"Allow": "GET, HEAD"}) unless request.method
    is one of `allowed`. The Allow header is mandatory on a 405."""
    raise NotImplementedError("TODO milestone 2: require_method")


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
    """Content-Type for a file name, from CONTENT_TYPES (lower-case the extension:
    os.path.splitext). Unknown extensions: "application/octet-stream"."""
    raise NotImplementedError("TODO milestone 3: guess_type")


def resolve_path(public_dir, url_path):
    """Map a URL path such as "/css/site.css" to a real file path INSIDE public_dir.

    Raise HttpError(403, ...) if the result would be outside it, HttpError(400, ...)
    for bad percent-escapes or a NUL byte. The order matters:
      1. urllib.parse.unquote(url_path, errors="strict")  -- decode %2e%2e FIRST
      2. root = os.path.realpath(public_dir)
      3. candidate = os.path.realpath(os.path.join(root, rel.lstrip("/")))
         (strip the leading "/": os.path.join(root, "/etc/passwd") ignores root!)
      4. candidate must be root or inside it. Use os.path.commonpath([root, candidate]) == root,
         NOT candidate.startswith(root): "/site/public-old" starts with "/site/public".
    """
    raise NotImplementedError("TODO milestone 3: resolve_path")


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
    """Serve GET and HEAD for files under public_dir.

      1. require_method(request, "GET", "HEAD")
      2. path = resolve_path(public_dir, request.path)
      3. a directory means its index.html
      4. read the file in binary mode ("rb"); a missing file or folder -> HttpError(404, ...)
      5. return Response(200, body, {"Content-Type": guess_type(path)})
    HEAD needs nothing special here: render_response(head_only=True) drops the body.

    STRETCH (conditional GET): also send  ETag: etag_for(body)  and
    Cache-Control: no-cache. If the request has If-None-Match and
    etag_matches(that header, etag) is true, return Response(304, b"", {"ETag": etag}).
    """
    raise NotImplementedError("TODO milestone 3: serve_static")


# --------------------------------------------------------------------------
    return Response(200, body, headers)


# ---------------------------------------------------------------------------
# Milestone 4: request bodies and a JSON API.
# ---------------------------------------------------------------------------

def parse_json_body(request):
    """The request body as a Python object.

    HttpError(415, ...) unless the Content-Type (ignoring "; charset=...", any case)
    is application/json. HttpError(400, ...) if the body isn't valid UTF-8 / JSON
    (json.loads raises ValueError; decoding raises UnicodeDecodeError).
    """
    raise NotImplementedError("TODO milestone 4: parse_json_body")


def api_echo(request):
    """POST /api/echo: reply with json_response({"you_sent": <the parsed body>,
    "bytes": <len(request.body)>}). Other methods: require_method gives 405."""
    raise NotImplementedError("TODO milestone 4: api_echo")


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
    """Should the connection stay open after this request?
    HTTP/1.1: yes, unless the Connection header lists "close".
    HTTP/1.0: no, unless it lists "keep-alive".
    The header is a comma-separated, case-insensitive list of tokens."""
    raise NotImplementedError("TODO milestone 5: wants_keep_alive")


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
    """Serve requests on one connection.

    As given, this answers ONE request and closes. Milestone 5:
      * keep_alive = wants_keep_alive(request)  (the loop already exits when it is False)
      * conn.settimeout(idle_timeout) before the loop, and handle socket.timeout around
        read_request: if reader.buf is non-empty the client stalled mid-request, so send
        error_response(408) with keep_alive=False; either way, return (close the connection).
    """
    reader = RequestReader(conn)
    try:
        while True:
            try:
                request = reader.read_request()
            except HttpError as e:                      # unparseable: framing is lost, so close
                response = error_response(e.status, e.message, e.headers)
                conn.sendall(render_response(response, keep_alive=False))
                return
            if request is None:                         # client closed between requests
                return

            keep_alive = False                          # TODO milestone 5: wants_keep_alive(request)
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
    """Start a daemon thread that runs
    handle_connection(conn, public_dir, idle_timeout, addr), then return at once
    so serve() can go back to accept(). (threading.Thread(target=..., args=..., daemon=True))"""
    raise NotImplementedError("TODO milestone 6: spawn_handler")


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
    sp.add_argument("--serial", action="store_true", help="one connection at a time (use until milestone 6)")
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
