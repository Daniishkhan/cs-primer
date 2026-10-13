"""Self-check for Lab 5: Find and Fix Injection.

    python3 check.py                  # checks your starter.py
    python3 check.py solution         # checks the reference solution
    python3 check.py solution 4       # only milestone 4

Every attack here is aimed at the deliberately vulnerable code inside this lab,
and only at that code. The database is in memory, files live in a temporary
directory that is deleted when the check ends, the "shell" executes nothing
real and the "network" is a table of fake servers: no socket is ever opened.
Everything is deterministic. Prints a tick, a cross, or "not implemented yet"
for each milestone. Finishes in about a second.
"""
import importlib
import io
import ipaddress
import os
import re
import sqlite3
import sys
import tempfile
import unittest
from urllib.parse import urlsplit

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True

args = sys.argv[1:]
target = args[0] if args and not args[0].isdigit() else "starter"
rest = [a for a in args if a.isdigit()]
ONLY = int(rest[0]) if rest else None
mod = importlib.import_module(target)
results = []
TMP = tempfile.TemporaryDirectory(prefix="lab05-")


def check(number, name, fn):
    if ONLY is not None and ONLY != number:
        return
    try:
        note = fn()
        print(f"  ✔ {name}")
        for line in (note or "").splitlines():
            print(f"      {line}")
        results.append(True)
    except NotImplementedError as e:
        print(f"  … {name}: not implemented yet ({e})")
        results.append(False)
    except AssertionError as e:
        print(f"  ✘ {name}: {e}")
        results.append(False)
    except Exception as e:
        import traceback
        tb = traceback.extract_tb(e.__traceback__)
        where = next((f"{f.name}() line {f.lineno}" for f in reversed(tb) if f.filename.endswith(f"{target}.py")), "?")
        print(f"  ✘ {name}: {type(e).__name__}: {e}   [in {where}]")
        results.append(False)


def world(cls):
    return mod.make_world(TMP.name, cls)


def short(x, n=70):
    s = repr(x)
    return s if len(s) <= n else s[:n] + "...'"


# ------------------------------------------------------------------ milestone 1
SQL_BATTERY = ["nobody' OR '1'='1", "' OR 1=1 --", "' OR ''='", "admin'--", "alice' AND '1'='1",
               "x' UNION SELECT name, secret FROM users --", "x' UNION SELECT 1, sqlite_version() --",
               "'; DROP TABLE users; --", "\\' OR 1=1 --", '" OR "1"="1', "' OR name LIKE '%", "%27 OR 1=1 --",
               "ʼ OR 1=1 --", "x') OR ('1'='1", "' OR 1=1 LIMIT 1 --", "nobody' OR role='admin' --"]
BAD_SORTS = ["name; DROP TABLE users", "(SELECT secret FROM users LIMIT 1)", "name DESC", "1", "role,name", "NAME", "", "name --"]
NAMES = sorted(u[0] for u in mod.USERS)


def try_search(app, payload):
    try:
        return app.search_users(payload)
    except sqlite3.Error:
        return []


def m1():
    w = world(mod.VulnerableApp)
    p1, p2 = mod.sql_dump_users(), mod.sql_steal_secrets()
    assert isinstance(p1, str) and isinstance(p2, str), "the exploits must be strings (the name to search for)"
    rows = w.app.search_users(p1)
    assert sorted(r[0] for r in rows) == NAMES, f"sql_dump_users() {short(p1)} should list ALL {len(NAMES)} users; the search returned {rows!r}"
    rows = w.app.search_users(p2)
    flat = [c for r in rows for c in r]
    assert all(s in flat for _, _, s in mod.USERS), f"sql_steal_secrets() {short(p2)} should put every user's secret in the result; got {rows!r}"
    lands = sum(1 for p in SQL_BATTERY if try_search(world(mod.VulnerableApp).app, p))
    assert lands >= 8, f"internal: only {lands} battery payloads work against the vulnerable search"
    # --- the fix
    fixed = world(mod.App)
    for p in SQL_BATTERY:
        rows = fixed.app.search_users(p)
        assert rows == [], f"payload {short(p)} still returns rows from the fixed search: {rows!r}"
    assert fixed.app.sql_log, "the fixed search ran no SQL; use self._query(sql, params)"
    for p in SQL_BATTERY:
        assert not any(p in s for s in fixed.app.sql_log), f"payload {short(p)} appears inside the SQL text: the value must travel as a parameter"
    assert len(set(fixed.app.sql_log)) == 1, f"the SQL text must be constant for the same sort; saw {len(set(fixed.app.sql_log))} different statements"
    assert mod.sql_dump_users() not in " ".join(fixed.app.sql_log)
    for p in (mod.sql_dump_users(), mod.sql_steal_secrets()):
        assert fixed.app.search_users(p) == [], "your own exploits must fail against the fixed search"
    # --- legitimate use still works, including a name with an apostrophe
    for name, want in (("alice", [("alice", "admin")]), ("O'Brien", [("O'Brien", "editor")]), ("nobody", []), ("bob", [("bob", "viewer")])):
        got = fixed.app.search_users(name)
        assert got == want, f"legitimate search for {name!r} returned {got!r}, expected {want!r}"
    assert fixed.app.search_users("carol", sort="role") == [("carol", "viewer")], "sorting by role is allowed"
    for bad in BAD_SORTS:
        try:
            fixed.app.search_users("alice", sort=bad)
        except ValueError:
            continue
        raise AssertionError(f"sort={short(bad)} should raise ValueError (an identifier cannot be a parameter: allowlist it)")
    assert fixed.db.execute("SELECT count(*) FROM users").fetchone()[0] == len(NAMES), "the users table must be intact"
    return (f"exploit works on the vulnerable search ({lands} of {len(SQL_BATTERY)} battery payloads land); "
            f"after the fix 0 of {len(SQL_BATTERY)} return rows and none appears in the SQL text\nlegitimate searches (including O'Brien) and the sort allowlist still work")


# ------------------------------------------------------------------ milestone 2
def path_battery(w):
    return [("parent directory", "../secret.txt", True), ("nested then up", "docs/../../secret.txt", True),
            ("dot then up", "./docs/../../secret.txt", True), ("absolute path", w.secret, True),
            ("sibling dir with the same prefix", "../uploads_private/data.txt", True), ("absolute sibling", w.sibling, True),
            ("doubled-dot trick", "....//secret.txt", False), ("url-encoded slash", "..%2fsecret.txt", False),
            ("null byte", "report.txt\x00../../secret.txt", False), ("backslashes", "docs/..\\..\\secret.txt", False)]


def attempt(fn, *a):
    """('data', bytes) or ('refused', exc)."""
    try:
        return "data", fn(*a)
    except (OSError, ValueError) as e:
        return "refused", e


def m2():
    w = world(mod.VulnerableApp)
    exploit = mod.path_exploit()
    got = w.app.download(exploit)
    assert got == mod.SECRET_FILE_TEXT.encode(), f"path_exploit() {short(exploit)} should make download() return secret.txt; got {short(got)}"
    lands = [label for label, p, _ in path_battery(w) if attempt(w.app.download, p)[0] == "data" and mod.leaked(attempt(w.app.download, p)[1])]
    if w.symlinks and mod.leaked(w.app.download("link.txt")):
        lands.append("symlink inside the root")
    assert len(lands) >= 5, f"internal: only {len(lands)} traversal variants leak from the vulnerable app"
    fixed = world(mod.App)
    for label, p, _ in path_battery(fixed):
        kind, val = attempt(fixed.app.download, p)
        assert kind == "refused" or not mod.leaked(val), f"{label}: download({short(p)}) returned {short(val)}"
        assert kind == "refused", f"{label}: download({short(p)}) should be refused; it returned {short(val)}"
    kind, val = attempt(fixed.app.download, exploit)
    assert kind == "refused", f"your own exploit {short(exploit)} must fail against the fixed download; it returned {short(val)}"
    if fixed.symlinks:
        kind, val = attempt(fixed.app.download, "link.txt")
        assert kind == "refused", f"a symlink inside the root that points outside it must be refused (resolve with realpath, not abspath); got {short(val)}"
    for name, want in (("report.txt", mod.REPORT), ("docs/guide.txt", "How to use the app.\n"), ("a..b.txt", "A file with two dots in its name.\n"),
                       ("docs/../report.txt", mod.REPORT)):
        kind, val = attempt(fixed.app.download, name)
        assert kind == "data" and val == want.encode(), f"legitimate download({name!r}) failed: {kind} {short(val)}"
    for name in ("docs", "missing.txt"):
        assert attempt(fixed.app.download, name)[0] == "refused", f"download({name!r}) should raise (a directory / a missing file)"
    return (f"exploit works on the vulnerable download ({len(lands)} of {len(path_battery(w)) + 1} variants leak); "
            f"after the fix all are refused\nlegitimate downloads work, including a..b.txt and docs/../report.txt")


# ------------------------------------------------------------------ milestone 3
CMD_BATTERY = ["example.test; cat /etc/app-secret", "example.test && cat /etc/app-secret", "example.test | cat /etc/app-secret",
               "-x || cat /etc/app-secret", "$(cat /etc/app-secret)", "`cat /etc/app-secret`", "example.test\ncat /etc/app-secret",
               "x'; cat /etc/app-secret; echo '", "example.test; rm /data/report.txt", "example.test\n", "ex ample.test", "",
               "--out=/data/report.txt", "-x", "--out=/etc/app-secret"]


def cmd_damage(w):
    foreign = [a for a in w.shell.history if a[0] != "nslookup"]
    changed = w.shell.files.get("/data/report.txt") != mod.REPORT or w.shell.files.get("/etc/app-secret") != mod.APP_SECRET
    return foreign, changed


def m3():
    w = world(mod.VulnerableApp)
    host = mod.cmd_exploit()
    out = w.app.lookup(host)
    assert mod.APP_SECRET.strip() in out, f"cmd_exploit() {short(host)} should make lookup() print /etc/app-secret; output was {short(out, 90)}"
    lands = 0
    for p in CMD_BATTERY:
        v = world(mod.VulnerableApp)
        o = v.app.lookup(p)
        foreign, changed = cmd_damage(v)
        lands += bool(mod.leaked(o) or foreign or changed)
    assert lands >= 8, f"internal: only {lands} battery payloads work against the vulnerable lookup"
    fixed = world(mod.App)
    for p in CMD_BATTERY + [host]:
        f = world(mod.App)
        try:
            o = f.app.lookup(p)
        except ValueError:
            o = None
        else:
            raise AssertionError(f"lookup({short(p)}) should raise ValueError: it is not a hostname (it returned {short(o)})")
        foreign, changed = cmd_damage(f)
        assert not foreign, f"lookup({short(p)}) caused {foreign!r} to run"
        assert not changed, f"lookup({short(p)}) changed a file"
    for host_ok in ("example.test", "a-b.example.org", "localhost", "192.0.2.7", "xn--bcher-kva.example", "A.B"):
        o = fixed.app.lookup(host_ok)
        assert f"Name:    {host_ok}" in o, f"legitimate lookup({host_ok!r}) returned {short(o)}"
    assert fixed.shell.history and all(a[0] == "nslookup" and a[1] == "--" for a in fixed.shell.history), \
        f"call self.shell.exec([\"nslookup\", \"--\", host]); the shell saw {fixed.shell.history[:2]!r}"
    return (f"exploit works on the vulnerable lookup ({lands} of {len(CMD_BATTERY)} battery payloads run foreign commands or change files); "
            "after the fix all raise ValueError and only nslookup ever runs\nlegitimate hostnames still work; the shell receives an argument list")


# ------------------------------------------------------------------ milestone 4
SSRF_BATTERY = [  # (label, url, lands on the vulnerable app)
    ("metadata, dotted (the blocklisted spelling)", "http://169.254.169.254/latest/meta-data/", False),
    ("metadata, one decimal integer", "http://2852039166/latest/meta-data/", True),
    ("metadata, hexadecimal", "http://0xa9fea9fe/latest/meta-data/", True),
    ("metadata, dotted octal", "http://0251.0376.0251.0376/latest/meta-data/", True),
    ("metadata, IPv4-mapped IPv6", "http://[::ffff:169.254.169.254]/latest/meta-data/", True),
    ("metadata, IPv4-mapped IPv6, hex groups", "http://[::ffff:a9fe:a9fe]/latest/meta-data/", True),
    ("loopback, short form 127.1", "http://127.1/", True),
    ("loopback, as 0", "http://0/", True),
    ("loopback, IPv6 long form", "http://[0:0:0:0:0:0:0:1]/", True),
    ("userinfo trick with a decimal host", "http://news.example.test@2852039166/", True),
    ("name that resolves to 10.x", "http://internal.attacker.test/", False),
    ("name that resolves to a private IPv6 address", "http://v6.attacker.test/", True),
    ("private ranges: router", "http://192.168.1.10/", True),
    ("private ranges: carrier-grade NAT", "http://100.64.0.9/", True),
    ("DNS rebinding", "http://rebind.attacker.test/", True),
    ("redirect to the metadata address", "http://redir.attacker.test/go", True),
    ("file: scheme", "file:///etc/app-secret", True),
]


def fetch(cls, url):
    w = world(cls)
    try:
        return w, w.app.preview(url), None
    except (ValueError, OSError) as e:
        return w, None, e


def m4():
    for fn, label in ((mod.ssrf_decimal, "decimal"), (mod.ssrf_ipv6, "IPv6"), (mod.ssrf_rebinding, "DNS rebinding")):
        url = fn()
        w, body, err = fetch(mod.VulnerableApp, url)
        assert body is not None and "LAB-IMDS-SECRET" in body, \
            f"{fn.__name__}() {short(url)} should reach the metadata service on the vulnerable preview ({label}); " + (f"it raised {err!r}" if err else f"it returned {short(body)}")
    for label, url, expect in SSRF_BATTERY:
        _, body, _ = fetch(mod.VulnerableApp, url)
        got = body is not None and mod.leaked(body)
        assert got == expect, f"internal: vulnerable preview on {label}: lands={got}, expected {expect}"
    lands = sum(1 for _, _, e in SSRF_BATTERY if e)
    for label, url, _ in SSRF_BATTERY:
        w, body, err = fetch(mod.App, url)
        assert body is None or not mod.leaked(body), f"{label}: preview({url!r}) leaked internal data: {short(body, 90)}"
        if label not in ("DNS rebinding",):
            assert err is not None, f"{label}: preview({url!r}) should be refused (raise Blocked); it returned {short(body, 90)}"
    for fn in (mod.ssrf_decimal, mod.ssrf_ipv6, mod.ssrf_rebinding):
        w, body, err = fetch(mod.App, fn())
        assert body is None or not mod.leaked(body), f"your own {fn.__name__}() exploit still works against the fixed preview"
    w, body, err = fetch(mod.App, "http://rebind.attacker.test/")
    assert body is not None and "Attacker page" in body, \
        f"DNS rebinding: the host is public on its FIRST lookup, so the fixed preview should fetch the attacker's own page from that address; got {short(body or err)}"
    n = w.net.lookups.count("rebind.attacker.test")
    assert n == 1, f"resolve each hostname ONCE and connect to the address you checked (pinning); the name was looked up {n} times"
    ok = [("https://news.example.test/article", "Daily News"), ("http://shop.example.test/item?id=3", "Item 3"),
          ("http://short.example.test/abc", "Daily News"), ("http://[2606:4700:4700::1111]/", "Public IPv6"),
          ("http://93.184.216.34/", "Default site")]
    for url, want in ok:
        w, body, err = fetch(mod.App, url)
        assert body is not None and want in body, f"legitimate preview({url!r}) failed: {short(body or err)}"
    w, body, err = fetch(mod.App, "http://short.example.test/loop")
    assert err is not None, "a redirect loop must end in Blocked after MAX_REDIRECTS hops"
    return (f"your three exploits work on the vulnerable preview ({lands} of {len(SSRF_BATTERY)} battery URLs land)\n"
            f"after the fix none leak; each name is resolved once and the connection is pinned to the checked address\n"
            f"legitimate previews (including a public IPv6 literal and a redirect) still work")


# ------------------------------------------------------------------ milestone 5
V = mod.VulnerableApp


def build_mutants():
    M = []

    def mut(label, **methods):
        M.append((label, type("Mutant", (mod.App,), methods)))

    # SQL
    mut("SQL: values pasted into the query text again", search_users=lambda self, name, sort="name": V.search_users(self, name, sort))

    def denylist(self, name, sort="name"):
        if re.search(r"\bunion\b|--|;", name, re.I):
            raise ValueError("suspicious input")
        return V.search_users(self, name, sort if sort in ("name", "role") else "name")
    mut("SQL: a keyword denylist instead of parameters", search_users=denylist)

    def sort_open(self, name, sort="name"):
        return self._query(f"SELECT name, role FROM users WHERE name = ? ORDER BY {sort}", (name,))
    mut("SQL: parameters for the value, but ORDER BY is spliced", search_users=sort_open)

    # paths
    mut("PATH: no containment check at all", download=lambda self, name: V.download(self, name))

    def prefix(self, name):
        base = os.path.realpath(self.root)
        t = os.path.realpath(os.path.join(base, name))
        if not t.startswith(base):
            raise PermissionError(name)
        with open(t, "rb") as f:
            return f.read()
    mut("PATH: startswith(root) instead of commonpath", download=prefix)

    def abspath(self, name):
        base = os.path.abspath(self.root)
        t = os.path.abspath(os.path.join(base, name))
        if os.path.commonpath([base, t]) != base:
            raise PermissionError(name)
        with open(t, "rb") as f:
            return f.read()
    mut("PATH: abspath instead of realpath (symlinks not followed)", download=abspath)
    mut("PATH: strip '../' out of the name", download=lambda self, name: V.download(self, name.replace("../", "")))

    def overblock(self, name):
        if ".." in name:
            raise PermissionError(name)
        base = os.path.realpath(self.root)
        t = os.path.realpath(os.path.join(base, name))
        if os.path.commonpath([base, t]) != base:
            raise PermissionError(name)
        with open(t, "rb") as f:
            return f.read()
    mut("PATH: rejects any '..' (breaks real file names)", download=overblock)

    # commands
    mut("CMD: the command line is built by string formatting again", lookup=lambda self, host: V.lookup(self, host))
    mut("CMD: argument list, but no validation and no '--'", lookup=lambda self, host: self.shell.exec(["nslookup", host]))

    def weak(self, host):
        if not re.match(r"[\w.-]+", host):
            raise ValueError("bad host")
        return self.shell.run(f"nslookup {host}")
    mut("CMD: validation that only checks the start, then a shell line", lookup=weak)
    mut("CMD: quotes around the pasted value", lookup=lambda self, host: self.shell.run(f"nslookup '{host}'"))

    # SSRF
    mut("SSRF: a blocklist of host strings", preview=lambda self, url: V.preview(self, url))

    def recheck(self, url):
        u = urlsplit(url)
        ip = ipaddress.ip_address(self.net.resolve(u.hostname))
        if not ip.is_global:
            raise mod.Blocked("private")
        return self.net.get(url).body[:200]           # the client looks the name up again and follows redirects itself
    mut("SSRF: checks the address, then lets the client resolve again", preview=recheck)

    def hop(app, url, ok):
        u = urlsplit(url)
        host = u.hostname
        if u.scheme not in ("http", "https") or not host or u.username:
            raise mod.Blocked("scheme or host")
        ip = ipaddress.ip_address(app.net.resolve(host))
        if ip.version == 6 and ip.ipv4_mapped:
            ip = ip.ipv4_mapped
        if not ok(ip):
            raise mod.Blocked(f"blocked {ip}")
        return app.net.request(str(ip), host, (u.path or "/") + ("?" + u.query if u.query else ""))

    def no_redirect_check(self, url):
        resp = hop(self, url, lambda ip: ip.is_global)
        if resp.status in (301, 302) and "Location" in resp.headers:
            return self.net.get(resp.headers["Location"]).body[:200]
        return resp.body[:200]
    mut("SSRF: first hop checked, redirects followed blindly", preview=no_redirect_check)

    def partial(self, url):
        for _ in range(mod.MAX_REDIRECTS + 1):
            resp = hop(self, url, lambda ip: not (ip.is_loopback or str(ip) == "169.254.169.254"))
            if resp.status in (301, 302) and "Location" in resp.headers:
                url = resp.headers["Location"]
                continue
            return resp.body[:200]
        raise mod.Blocked("redirects")
    mut("SSRF: denies only loopback and the metadata address", preview=partial)

    def file_ok(self, url):
        if urlsplit(url).scheme == "file":
            return self.net.get(url).body[:200]
        return mod.App.preview(self, url)
    mut("SSRF: file: URLs allowed again", preview=file_ok)
    return M


def run_suite(app_cls):
    cls = type("Run", (mod.RegressionTests,), {"app_cls": app_cls})
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(cls)
    res = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
    bad = [(t.id().split(" ")[0].split(".")[-1], tb) for t, tb in res.failures + res.errors]
    return res.testsRun, bad, len(res.skipped)


def m5():
    n, bad, skipped = run_suite(mod.App)
    if any("NotImplementedError" in tb for _, tb in bad):
        raise NotImplementedError("TODO milestone 5: write the regression tests")
    if bad:
        name, tb = bad[0]
        lines = [l for l in tb.strip().splitlines() if l.strip()]
        raise AssertionError(f"your suite fails on YOUR FIXED App ({len(bad)} of {n} tests; fix milestones 1-4 or the tests first). First: {name}: {lines[-1]}")
    assert n >= 10, f"write at least 10 tests (found {n}); cover SQL, paths, commands and SSRF, and legitimate use"
    survivors, notes = [], []
    mutants = build_mutants()
    skipped_m = 0
    for label, cls in mutants:
        if "abspath" in label and not world(cls).symlinks:
            skipped_m += 1
            continue
        _, bad, _ = run_suite(cls)
        if bad:
            names = sorted({b[0] for b in bad})
            notes.append(f"caught: {label}  <- {names[0]}" + (f" (+{len(names) - 1} more)" if len(names) > 1 else ""))
        else:
            survivors.append(label)
    assert not survivors, ("your tests passed on " + str(len(survivors)) + " re-broken variant(s) of the app; a test must fail for each:\n"
                           + "".join(f"        survived: {s}\n" for s in survivors).rstrip())
    caught = len(mutants) - skipped_m
    return (f"{n} tests pass on the fixed app ({skipped} skipped); all {caught} reintroduced bugs are caught"
            + (f" ({skipped_m} skipped: no symlinks here)" if skipped_m else "") + "\n" + "\n".join(notes))


print(f"Lab 5 checks against {target}.py\n")
check(1, "Milestone 1: SQL injection, exploited and fixed", m1)
check(2, "Milestone 2: path traversal, exploited and fixed", m2)
check(3, "Milestone 3: command injection, exploited and fixed", m3)
check(4, "Milestone 4: SSRF in a URL preview, exploited and fixed", m4)
check(5, "Milestone 5: a regression suite that catches reintroduced bugs", m5)
print(f"\n{sum(results)}/{len(results)} milestones passing")
TMP.cleanup()
sys.exit(0 if all(results) else 1)
