"""Lab 5: Find and Fix Injection.

A small web-app backend, written the way real bugs get written, runs entirely
inside this Python process:

    VulnerableApp   four features, each with a classic bug (given, do not edit)
    App             your fixed version: it subclasses VulnerableApp and overrides
                    one method per milestone

  1. SQL injection        search_users      exploit it, then parameterise it
  2. Path traversal       download          exploit it, then contain it with realpath
  3. Command injection    lookup            exploit it, then pass an argument list
  4. SSRF                 preview           exploit it, then resolve, check and PIN
  5. Regression tests     RegressionTests   tests that catch every bug if it comes back

SAFETY. Everything here is simulated. The database is an in-memory sqlite3
database; files live in a temporary directory that the checks create and delete;
the "shell" (MiniShell) is a toy interpreter that executes nothing real; the
"network" (Network) is a table of fake servers and a fake resolver. No socket
is ever opened. The exploits you write attack only this deliberately vulnerable
code. Only test what you own or are authorised to test.

Run  python3 check.py  (your starter)  or  python3 check.py solution.
"""
import ipaddress
import os
import re
import sqlite3
import tempfile
import unittest
from urllib.parse import urljoin, urlsplit


# =========================================================================
# The simulated world (given; read it, do not edit it)
# =========================================================================
USERS = [("alice", "admin", "key-alice-7f3a"), ("bob", "viewer", "key-bob-91c2"),
         ("carol", "viewer", "key-carol-5d08"), ("O'Brien", "editor", "key-obrien-33be")]

SECRET_FILE_TEXT = "TOP-SECRET-OUTSIDE-FILE: payroll.csv lives here\n"
SIBLING_FILE_TEXT = "PRIVATE-SIBLING-DATA: another service's files\n"
APP_SECRET = "DB_PASSWORD=hunter2-for-this-lab-only\n"
REPORT = "Quarterly report: all numbers are fictional.\n"
LEAK_MARKERS = ("TOP-SECRET-OUTSIDE-FILE", "PRIVATE-SIBLING-DATA", "DB_PASSWORD", "LAB-IMDS-SECRET",
                "INTERNAL-ADMIN-PANEL", "LOOPBACK-DEBUG-CONSOLE", "ROUTER-ADMIN", "CGNAT-SERVICE", "ULA-INTERNAL")


def leaked(text):
    """True if `text` contains anything a correct app must never reveal."""
    return any(m in str(text) for m in LEAK_MARKERS)


def make_db():
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, role TEXT, secret TEXT)")
    db.executemany("INSERT INTO users (name, role, secret) VALUES (?, ?, ?)", USERS)
    db.commit()
    return db


class MiniShell:
    """A toy command interpreter. NOTHING REAL IS EXECUTED: commands are Python
    functions over a virtual file system (a dict).

    run(line)   behaves like  sh -c line : it PARSES the text, so ; && || | newline,
                $( ) and backticks are all live syntax.
    exec(argv)  behaves like  subprocess.run(argv) with no shell : one command, the
                argument list taken literally, no parsing at all.

    Commands: nslookup [--out=FILE] [--] [HOST] | echo ARGS | cat FILE... | rm FILE... | id
    """

    def __init__(self, files=None):
        self.files = dict(files or {})
        self.history = []                 # every command that actually ran, as an argv list
        self.last_status = 0

    def exec(self, argv):
        argv = list(argv)
        self.history.append(argv)
        cmd, args = argv[0], argv[1:]
        self.last_status = 0
        if cmd == "nslookup":
            out = None
            while args and args[0].startswith("-") and args[0] != "--":
                opt = args.pop(0)
                if opt.startswith("--out="):
                    out = opt[len("--out="):]
                else:
                    self.last_status = 1
                    return f"nslookup: unknown option {opt}\n"
            if args and args[0] == "--":
                args.pop(0)
            if len(args) > 1:
                self.last_status = 1
                return "usage: nslookup [--out=FILE] [--] [HOST]\n"
            host = args[0] if args else "localhost"
            text = f"Name:    {host}\nAddress: 192.0.2.{sum(host.encode()) % 250 + 1}\n"
            if out is not None:
                self.files[out] = text            # an option that writes to ANY path: argument injection's prize
                return ""
            return text
        if cmd == "echo":
            return " ".join(args) + "\n"
        if cmd == "cat":
            parts = []
            for a in args:
                if a in self.files:
                    parts.append(self.files[a])
                else:
                    self.last_status = 1
                    parts.append(f"cat: {a}: No such file\n")
            return "".join(parts)
        if cmd == "rm":
            for a in args:
                if self.files.pop(a, None) is None:
                    self.last_status = 1
            return ""
        if cmd == "id":
            return "uid=1000(appsvc) gid=1000(appsvc)\n"
        self.last_status = 127
        return f"sh: {cmd}: command not found\n"

    def run(self, line):
        out, status = [], 0
        for op, text in self._segments(line):
            if (op == "&&" and status != 0) or (op == "||" and status == 0):
                continue
            argv = self._words(text)
            if not argv:
                continue
            if op == "|" and out:
                out.pop()                       # the previous command's output went into this pipe
            out.append(self.exec(argv))
            status = self.last_status
        return "".join(out)

    def _segments(self, line):
        segs, cur, op = [], [], None
        q, depth, tick, i, n = None, 0, False, 0, len(line)
        while i < n:
            c, two = line[i], line[i:i + 2]
            if q == "'":
                cur.append(c)
                if c == "'":
                    q = None
            elif c == "\\" and i + 1 < n:
                cur.append(c + line[i + 1])
                i += 2
                continue
            elif c == "$" and line[i + 1:i + 2] == "(":
                depth += 1
                cur.append("$(")
                i += 2
                continue
            elif depth and c == ")":
                depth -= 1
                cur.append(c)
            elif c == "`":
                tick = not tick
                cur.append(c)
            elif c == '"':
                q = None if q == '"' else '"'
                cur.append(c)
            elif q is None and c == "'":
                q = "'"
                cur.append(c)
            elif q is None and not depth and not tick and c == "#" and (not cur or cur[-1].isspace()):
                while i < n and line[i] != "\n":
                    i += 1
                continue
            elif q is None and not depth and not tick and (two in ("&&", "||") or c in ";\n|"):
                tok = two if two in ("&&", "||") else c
                segs.append((op, "".join(cur)))
                cur, op = [], (";" if tok == "\n" else tok)
                i += len(tok)
                continue
            else:
                cur.append(c)
            i += 1
        segs.append((op, "".join(cur)))
        return [(o, t) for o, t in segs if t.strip()]

    def _words(self, text):
        words, cur, q, i, n = [], None, None, 0, len(text)
        while i < n:
            c = text[i]
            if q == "'":
                if c == "'":
                    q = None
                else:
                    cur += c
            elif c == "'":
                q, cur = "'", cur or ""
            elif c == '"':
                q = None if q == '"' else '"'
                cur = cur or ""
            elif c == "\\" and i + 1 < n:
                cur = (cur or "") + text[i + 1]
                i += 1
            elif c == "$" and text[i + 1:i + 2] == "(":
                j, d = i + 2, 1
                while j < n and d:
                    d += (text[j] == "(") - (text[j] == ")")
                    j += 1
                cur = (cur or "") + self.run(text[i + 2:j - 1]).rstrip("\n")
                i = j - 1
            elif c == "`":
                j = text.find("`", i + 1)
                j = n if j < 0 else j
                cur = (cur or "") + self.run(text[i + 1:j]).rstrip("\n")
                i = j
            elif c.isspace() and q is None:
                if cur is not None:
                    words.append(cur)
                cur = None
            else:
                cur = (cur or "") + c
            i += 1
        if cur is not None:
            words.append(cur)
        return words


class NetError(Exception):
    pass


class Response:
    def __init__(self, status, headers, body):
        self.status, self.headers, self.body = status, headers, body


def parse_ip_literal(host):
    """How a lenient C-library resolver reads an IP written in a 'creative' spelling:
    2852039166, 0xa9fea9fe, 0251.0376.0251.0376, 127.1, 0, or an IPv6 literal.
    Returns the canonical address text, or None if `host` is not an IP literal."""
    if ":" in host:
        try:
            return str(ipaddress.IPv6Address(host))
        except ValueError:
            return None
    parts = host.split(".")
    if not 1 <= len(parts) <= 4:
        return None
    nums = []
    for p in parts:
        if not p or not p.isascii():
            return None
        try:
            if p[:2].lower() == "0x":
                v = int(p[2:], 16)
            elif len(p) > 1 and p[0] == "0":
                v = int(p, 8)
            else:
                v = int(p, 10)
        except ValueError:
            return None
        nums.append(v)
    *head, last = nums
    if any(h > 255 for h in head) or last >= 256 ** (5 - len(nums)):
        return None
    value = last
    for i, h in enumerate(head):
        value += h << (8 * (3 - i))
    return str(ipaddress.IPv4Address(value))


class Network:
    """A fake DNS plus a fake set of servers. No sockets. The addresses are
    arbitrary: nothing at any of them is ever contacted.

    resolve(host)           DNS (or a lenient IP-literal parse). Each lookup is recorded in
                            self.lookups. A host may have several answers; each lookup
                            consumes the next one (that is how DNS rebinding is replayed).
    request(ip, host, path) 'connect to this exact address' (strict: ip must be canonical text).
    get(url)                what a naive HTTP client does: resolve AGAIN, connect, follow
                            redirects, and read file: URLs from the virtual disk.
    """

    ZONES = {
        "news.example.test": ["93.184.216.34"],
        "shop.example.test": ["93.184.216.34"],
        "short.example.test": ["93.184.216.36"],
        "localhost": ["127.0.0.1"],
        "redir.attacker.test": ["93.184.216.35"],
        "rebind.attacker.test": ["93.184.216.35", "169.254.169.254"],   # public first, then the metadata address
        "internal.attacker.test": ["10.0.0.5"],
        "v6.attacker.test": ["fd00::5"],
    }

    def __init__(self, files=None):
        self.files = files if files is not None else {}
        self._zones = {h: list(a) for h, a in self.ZONES.items()}
        self.lookups = []
        self.servers = {str(ipaddress.ip_address(ip)): fn for ip, fn in {
            "93.184.216.34": self._public_site,
            "93.184.216.35": self._attacker_site,
            "93.184.216.36": self._shortener,
            "2606:4700:4700::1111": lambda h, p: Response(200, {}, "<title>Public IPv6 page</title>"),
            "169.254.169.254": lambda h, p: Response(200, {}, "LAB-IMDS-SECRET AccessKeyId=AKIA-LAB-ONLY SecretAccessKey=not-a-real-key"),
            "10.0.0.5": lambda h, p: Response(200, {}, "INTERNAL-ADMIN-PANEL: users, billing, delete-all"),
            "127.0.0.1": lambda h, p: Response(200, {}, "LOOPBACK-DEBUG-CONSOLE: /debug/vars"),
            "::1": lambda h, p: Response(200, {}, "LOOPBACK-DEBUG-CONSOLE: /debug/vars"),
            "192.168.1.10": lambda h, p: Response(200, {}, "ROUTER-ADMIN: default password page"),
            "100.64.0.9": lambda h, p: Response(200, {}, "CGNAT-SERVICE: shared carrier network"),
            "fd00::5": lambda h, p: Response(200, {}, "ULA-INTERNAL: private IPv6 service"),
        }.items()}

    @staticmethod
    def _public_site(host, path):
        if host == "news.example.test" and path == "/article":
            return Response(200, {}, "<title>Daily News</title> Local team wins the final. Read more inside.")
        if host == "shop.example.test":
            return Response(200, {}, "<title>Shop</title> Item " + path.partition("=")[2] + " is in stock.")
        return Response(200, {}, "<title>Default site</title> It works.")

    @staticmethod
    def _attacker_site(host, path):
        if path == "/go":                                     # an open redirect pointed at the metadata address
            return Response(302, {"Location": "http://169.254.169.254/latest/meta-data/"}, "")
        return Response(200, {}, "<title>Attacker page</title> Nothing to see here.")

    @staticmethod
    def _shortener(host, path):
        if path == "/abc":
            return Response(301, {"Location": "https://news.example.test/article"}, "")
        if path == "/loop":
            return Response(302, {"Location": "http://short.example.test/loop"}, "")
        return Response(404, {}, "not found")

    def resolve(self, host):
        host = host.lower().rstrip(".")
        self.lookups.append(host)
        if host in self._zones:
            answers = self._zones[host]
            return answers.pop(0) if len(answers) > 1 else answers[0]
        ip = parse_ip_literal(host)
        if ip is None:
            raise NetError(f"NXDOMAIN: {host}")
        return ip

    def request(self, ip, host, path):
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            raise NetError(f"request() connects to an IP address, not {ip!r}: resolve first")
        if addr.version == 6 and addr.ipv4_mapped:
            addr = addr.ipv4_mapped                          # a dual-stack socket reaches the IPv4 host
        if str(addr) == "0.0.0.0":
            addr = ipaddress.ip_address("127.0.0.1")         # 'this host' on most systems
        fn = self.servers.get(str(addr))
        if fn is None:
            raise NetError(f"connection to {addr} refused")
        return fn(host, path)

    def get(self, url, max_redirects=5):
        for _ in range(max_redirects + 1):
            u = urlsplit(url)
            if u.scheme == "file":
                if u.path in self.files:
                    return Response(200, {}, self.files[u.path])
                raise NetError(f"no such file: {u.path}")
            if u.scheme not in ("http", "https"):
                raise NetError(f"unsupported scheme {u.scheme!r}")
            ip = self.resolve(u.hostname)
            resp = self.request(ip, u.hostname, (u.path or "/") + ("?" + u.query if u.query else ""))
            if resp.status in (301, 302, 303, 307, 308) and "Location" in resp.headers:
                url = urljoin(url, resp.headers["Location"])
                continue
            return resp
        raise NetError("too many redirects")


class Blocked(ValueError):
    """Raised when the app refuses a request."""


class World:
    """Everything one test needs: an app and the fixtures around it."""

    def __init__(self, app, root, secret, sibling, shell, net, db, symlinks):
        self.app, self.root, self.secret, self.sibling = app, root, secret, sibling
        self.shell, self.net, self.db, self.symlinks = shell, net, db, symlinks


def make_world(tmpdir, app_cls=None):
    """Build a fresh app over a fresh in-memory db, a fresh directory under `tmpdir`,
    a fresh MiniShell and a fresh Network. Layout:
        <base>/uploads/report.txt, docs/guide.txt, a..b.txt, link.txt (symlink to ../secret.txt, if allowed)
        <base>/secret.txt            outside the upload root
        <base>/uploads_private/data.txt   a sibling directory whose name starts like the root's
    """
    base = tempfile.mkdtemp(dir=tmpdir)
    root = os.path.join(base, "uploads")
    os.makedirs(os.path.join(root, "docs"))
    os.makedirs(os.path.join(base, "uploads_private"))
    for rel, text in (("uploads/report.txt", REPORT), ("uploads/docs/guide.txt", "How to use the app.\n"),
                      ("uploads/a..b.txt", "A file with two dots in its name.\n"),
                      ("secret.txt", SECRET_FILE_TEXT), ("uploads_private/data.txt", SIBLING_FILE_TEXT)):
        with open(os.path.join(base, rel), "w") as f:
            f.write(text)
    try:
        os.symlink(os.path.join("..", "secret.txt"), os.path.join(root, "link.txt"))
        symlinks = True
    except (OSError, NotImplementedError, AttributeError):
        symlinks = False
    files = {"/etc/app-secret": APP_SECRET, "/data/report.txt": REPORT}
    shell, net, db = MiniShell(files), Network(files), make_db()
    app = (app_cls or App)(db, root, shell, net)
    return World(app, root, os.path.join(base, "secret.txt"), os.path.join(base, "uploads_private", "data.txt"),
                 shell, net, db, symlinks)


class VulnerableApp:
    """THE VULNERABLE APP. Four features, four classic bugs. Read each one; the
    comments point at the mistake. Do not edit this class: you fix the bugs by
    overriding the methods in App below."""

    def __init__(self, db, root, shell, net):
        self.db, self.root, self.shell, self.net = db, root, shell, net
        self.sql_log = []                       # the text of every SQL statement executed

    def _query(self, sql, params=()):
        """Run one statement and remember its text. Use this from your fixes so the check can see the SQL."""
        self.sql_log.append(sql)
        return self.db.execute(sql, params).fetchall()

    # ---- feature 1: look a user up by name, sorted by name or role --------------------
    def search_users(self, name, sort="name"):
        # BUG: both `name` and `sort` are pasted into the SQL text.
        return self._query(f"SELECT name, role FROM users WHERE name = '{name}' ORDER BY {sort}")

    # ---- feature 2: download a file from the uploads folder ---------------------------
    def download(self, name):
        # BUG: the name is joined onto the root and opened; nothing checks where it ended up.
        with open(os.path.join(self.root, name), "rb") as f:
            return f.read()

    # ---- feature 3: DNS lookup for a hostname the user typed (a "diagnostics" page) ----
    def lookup(self, host):
        # BUG: the hostname is pasted into a command LINE that a shell parses.
        return self.shell.run(f"nslookup {host}")

    # ---- feature 4: fetch a URL and show a preview of the page --------------------------
    BLOCKED_HOSTS = {"localhost", "127.0.0.1", "169.254.169.254", "::1"}

    def preview(self, url):
        # BUG: a blocklist of host STRINGS, a check of the resolved name, and then the HTTP
        # client resolves again and follows redirects on its own.
        u = urlsplit(url)
        host = u.hostname or ""
        if u.scheme not in ("http", "https", "file"):
            raise Blocked("scheme not allowed")
        if host.lower() in self.BLOCKED_HOSTS:
            raise Blocked(f"{host} is blocked")
        if host and not host[0].isdigit() and ":" not in host:           # looks like a NAME: resolve and check
            ip = self.net.resolve(host)
            if ip.startswith(("10.", "127.", "169.254.", "192.168.")):
                raise Blocked(f"{host} resolves to a private address")
        return self.net.get(url).body[:200]


# =========================================================================
# Milestone 1: SQL injection
# =========================================================================
def sql_dump_users():
    """Return a NAME to search for that makes VulnerableApp.search_users return EVERY user."""
    raise NotImplementedError("TODO milestone 1: sql_dump_users")


def sql_steal_secrets():
    """Return a name that makes search_users return every user's SECRET (the `secret`
    column) in the `role` position of the result, using a UNION."""
    raise NotImplementedError("TODO milestone 1: sql_steal_secrets")


# =========================================================================
# Milestone 2: path traversal
# =========================================================================
def path_exploit():
    """Return a file NAME that makes VulnerableApp.download return the contents of
    secret.txt, which sits one level above the uploads folder."""
    raise NotImplementedError("TODO milestone 2: path_exploit")


# =========================================================================
# Milestone 3: command injection
# =========================================================================
def cmd_exploit():
    """Return a HOSTNAME that makes VulnerableApp.lookup run a second command and
    print the contents of the file /etc/app-secret."""
    raise NotImplementedError("TODO milestone 3: cmd_exploit")


# =========================================================================
# Milestone 4: SSRF
# =========================================================================
def ssrf_decimal():
    """Return a URL that reaches the cloud metadata address 169.254.169.254 although
    its dotted spelling is on the blocklist: write the address as one decimal integer."""
    raise NotImplementedError("TODO milestone 4: ssrf_decimal")


def ssrf_ipv6():
    """Return a URL that reaches the same metadata address through an IPv6 spelling
    (an IPv4-mapped address in brackets)."""
    raise NotImplementedError("TODO milestone 4: ssrf_ipv6")


def ssrf_rebinding():
    """Return a URL on a host that resolves to a PUBLIC address the first time it is
    looked up and to the metadata address the second time (see Network.ZONES)."""
    raise NotImplementedError("TODO milestone 4: ssrf_rebinding")


MAX_REDIRECTS = 3


class App(VulnerableApp):
    """YOUR FIXED APP. Override one method per milestone. Anything you do not
    override is still the vulnerable version."""

    # ---- milestone 1 ----
    SORT_COLUMNS = {"name": "name", "role": "role"}

    def search_users(self, name, sort="name"):
        """Parameterise the VALUE; allowlist the IDENTIFIER (a column name cannot be a
        parameter). Unknown `sort` -> raise ValueError. Use self._query(sql, params)."""
        raise NotImplementedError("TODO milestone 1: App.search_users")

    # ---- milestone 2 ----
    def download(self, name):
        """Resolve first, judge second. Compute the real path of the root and of root/name
        (os.path.realpath follows symlinks and collapses ..), and refuse unless the target
        is the root or inside it (os.path.commonpath, not startswith). Escape -> PermissionError."""
        raise NotImplementedError("TODO milestone 2: App.download")

    # ---- milestone 3 ----
    HOSTNAME = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?")

    def lookup(self, host):
        """Validate (HOSTNAME with re.fullmatch; a leading '-' can never match), then call
        self.shell.exec(["nslookup", "--", host]). Invalid -> raise ValueError. Never self.shell.run."""
        raise NotImplementedError("TODO milestone 3: App.lookup")

    # ---- milestone 4 ----
    def preview(self, url):
        """Per hop: parse, allow only http/https, refuse credentials in the URL, RESOLVE ONCE with
        self.net.resolve, turn the answer into an ipaddress object (unwrap IPv4-mapped IPv6), refuse
        unless ip.is_global (and not multicast), then connect to THAT address with
        self.net.request(str(ip), host, path). On a redirect, repeat all of it for the new URL, at
        most MAX_REDIRECTS times. Refuse -> raise Blocked."""
        raise NotImplementedError("TODO milestone 4: App.preview")


# =========================================================================
# Milestone 5: a regression suite that catches the bugs if they come back
# =========================================================================
class RegressionBase(unittest.TestCase):
    """Gives each test a fresh `self.w` (a World). The check runs your tests against
    your fixed App (all must pass) and against deliberately re-broken variants of it
    (each must make at least one test fail). Do not edit this class."""

    app_cls = None                                   # None means App; the check substitutes broken variants

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.w = make_world(self._tmp.name, self.app_cls)

    def assertNoLeak(self, value):
        self.assertFalse(leaked(value), f"secret data came back: {str(value)[:80]!r}")

    def assertRefused(self, fn, *args):
        """fn(*args) must raise (ValueError, OSError) and must not return anything."""
        try:
            result = fn(*args)
        except (ValueError, OSError):
            return
        self.fail(f"{fn.__name__}{args!r} should have been refused but returned {str(result)[:60]!r}")


class RegressionTests(RegressionBase):
    """WRITE YOUR TESTS HERE: aim for twelve or more small tests that cover all four bugs
    AND the legitimate behaviour (a fix that breaks real users is a regression too).
    Use self.w.app, self.w.shell, self.w.net, self.w.secret, self.w.root, self.w.symlinks."""

    def test_not_written_yet(self):
        raise NotImplementedError("TODO milestone 5: write the regression tests")
