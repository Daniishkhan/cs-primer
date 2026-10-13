"""Self-check for Lab 3: OAuth with PKCE, Simulated.

    python3 check.py                  # checks your starter.py
    python3 check.py solution         # checks the reference solution
    python3 check.py solution 5       # only milestone 5

Everything is deterministic enough to be repeatable (random codes and states are never compared with
fixed values) and everything happens in this one process: a simulated browser, authorization server,
client and API. The "attacks" in milestone 5 are aimed only at those toy objects. Runs in well under a second.
"""
import hashlib
import hmac
import importlib
import os
import sys
from urllib.parse import parse_qsl, urlencode, urlsplit

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True

args = sys.argv[1:]
target = args[0] if args and not args[0].isdigit() else "starter"
rest = [a for a in args if a.isdigit()]
ONLY = int(rest[0]) if rest else None
mod = importlib.import_module(target)
results = []

KEY = hashlib.sha256(b"lab 3 shared key").digest()
WEB_CB = "https://app.example/cb"
NATIVE_CB = "myapp://cb"
EVIL_CB = "https://app.example.evil.example/cb"
AUTH = mod.AS_ORIGIN + "/authorize?"
RFC_VERIFIER = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
RFC_CHALLENGE = "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"


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


class Spy:
    def __init__(self, obj, attr):
        self.obj, self.attr, self.calls = obj, attr, 0

    def __enter__(self):
        self.orig = getattr(self.obj, self.attr)

        def wrapper(*a, **k):
            self.calls += 1
            return self.orig(*a, **k)
        setattr(self.obj, self.attr, wrapper)
        return self

    def __exit__(self, *exc):
        setattr(self.obj, self.attr, self.orig)


def blocked(fn):
    """Run fn; return the OAuthError it raised (or None if it did not)."""
    try:
        fn()
    except mod.OAuthError as e:
        return e
    return None


class World:
    """One simulated deployment. `weak` sets switch individual defences off (control experiments only)."""
    def __init__(self, as_weak=(), client_weak=(), rs_weak=(), client_site=True, client_uri=WEB_CB,
                 client_scope="read", audience=mod.RS_AUDIENCE):
        m = mod
        self.clock = m.SimClock()
        self.clients = {
            "app-1": {"redirect_uris": [WEB_CB, NATIVE_CB], "scopes": "read write"},
            "other-app": {"redirect_uris": ["https://other.example/cb"], "scopes": "read"},
        }
        self.as_ = m.AuthorizationServer(self.clock, KEY, self.clients, audience=audience, weak=as_weak)
        self.rs = m.ResourceServer(self.clock, KEY, weak=rs_weak)
        self.client = m.Client("app-1", client_uri, self.as_, scope=client_scope, rs=self.rs, weak=client_weak)
        self.token_calls = []
        real = self.as_.token

        def logged(params):
            self.token_calls.append(dict(params))
            return real(params)
        self.as_.token = logged
        self.evil = m.Collector()
        self.evil2 = m.Collector()
        self.browser = self.new_browser("alice")
        if client_site:
            self.browser.mount(m.CLIENT_ORIGIN, self.client)

    def new_browser(self, user=None):
        b = mod.Browser()
        b.mount(mod.AS_ORIGIN, self.as_)
        b.mount("https://app.example.evil.example", self.evil)
        b.mount("https://evil.example", self.evil2)
        if user:
            self.as_.login(b, user)
        return b

    def claims(self, tok):
        return mod.open_token(KEY, tok["access_token"], self.clock.now())


def auth_query(**over):
    q = {"response_type": "code", "client_id": "app-1", "redirect_uri": WEB_CB, "scope": "read", "state": "s-1"}
    q.update(over)
    return {k: v for k, v in q.items() if v is not None}


def get_code(w, browser=None, **over):
    """Drive /authorize to the redirect without following it; return the code and the redirect URL."""
    r = (browser or w.browser).open(AUTH + urlencode(auth_query(**over)), follow=False)
    assert r.status == 302, f"/authorize did not redirect (status {r.status}, {r.body})"
    return dict(parse_qsl(urlsplit(r.location).query))["code"], r.location


def form(code, **over):
    f = {"grant_type": "authorization_code", "code": code, "redirect_uri": WEB_CB, "client_id": "app-1"}
    f.update(over)
    return f


REDIRECT_VARIANTS = [
    "https://app.example/cb/", "https://app.example/cb?x=1", "https://app.example/cb#frag", "http://app.example/cb",
    EVIL_CB, "https://app.example@evil.example/cb", "https://evil.example/cb", "HTTPS://APP.EXAMPLE/cb",
    "https://app.example/CB", "https://app.example:443/cb", "//evil.example/cb", " https://app.example/cb",
    "https://app.example/cb\n", "https://app.example/cb/../cb", "myapp://evil", "", "https://app.example",
]


# ------------------------------------------------------------------ milestone 1
def m1():
    w = World(as_weak=("pkce",), client_site=False)
    cb = mod.Collector()
    w.browser.mount(mod.CLIENT_ORIGIN, cb)
    r = w.browser.open(AUTH + urlencode(auth_query(state="a b&c=d/é")))
    assert r.status == 200 and len(cb.requests) == 1, "a valid request should end with the browser at the client's callback"
    path, params = cb.requests[0]
    assert path == "/cb" and params["state"] == "a b&c=d/é", f"state must be echoed unchanged and URL-encoded, got {params}"
    code = params["code"]
    assert len(code) >= 16, "authorization codes must be long and random"
    tok = w.as_.token(form(code))
    assert tok["token_type"] == "Bearer" and tok["access_token"] and tok["expires_in"] == 300 and tok["scope"] == "read", f"token response: {tok}"
    codes = {get_code(w)[0] for _ in range(20)}
    assert len(codes) == 20, "codes must be unique"
    # exact redirect_uri matching: an error PAGE, never a redirect
    for uri in REDIRECT_VARIANTS:
        seen = len(w.browser.history)
        r = w.browser.open(AUTH + urlencode(auth_query(redirect_uri=uri)))
        assert r.status == 400, f"redirect_uri {uri!r} must produce an error page (400), got {r.status}"
        assert len(w.browser.history) == seen + 1 and not w.evil.requests and not w.evil2.requests and len(cb.requests) == 1, \
            f"redirect_uri {uri!r}: the browser must not be sent anywhere"
        e = blocked(lambda: w.as_.authorize("alice", auth_query(redirect_uri=uri)))
        assert e is not None and e.defence == "redirect", f"redirect_uri {uri!r}: expected OAuthError with defence 'redirect'"
    r = w.browser.open(AUTH + urlencode({k: v for k, v in auth_query().items() if k != "redirect_uri"}))
    assert r.status == 400, "a missing redirect_uri must be an error in this lab"
    assert blocked(lambda: w.as_.authorize("alice", auth_query(client_id="nobody"))), "unknown client"
    assert blocked(lambda: w.as_.authorize("alice", auth_query(response_type="token"))), "implicit flow is not offered"
    assert blocked(lambda: w.as_.authorize(None, auth_query())), "nobody logged in: no code"
    bare = w.new_browser()
    assert bare.open(AUTH + urlencode(auth_query())).status == 400, "a browser with no AS session gets no code"
    # single use
    code, _ = get_code(w)
    w.as_.token(form(code))
    e = blocked(lambda: w.as_.token(form(code)))
    assert e and e.code == "invalid_grant" and e.defence == "single_use", "using a code twice must fail with invalid_grant (single_use)"
    # expiry
    code, _ = get_code(w)
    w.clock.advance(59)
    w.as_.token(form(code))
    code, _ = get_code(w)
    w.clock.advance(60)
    e = blocked(lambda: w.as_.token(form(code)))
    assert e and e.code == "invalid_grant" and e.defence == "expiry", "a code must expire after exactly 60 s"
    # binding
    for name, over in [("another client", dict(client_id="other-app")), ("another redirect_uri", dict(redirect_uri=NATIVE_CB))]:
        code, _ = get_code(w)
        assert blocked(lambda: w.as_.token(form(code, **over))), f"{name}: the code is bound to the original request"
        assert blocked(lambda: w.as_.token(form(code))), f"{name}: a failed attempt must burn the code"
    assert blocked(lambda: w.as_.token(form("no-such-code"))) and blocked(lambda: w.as_.token(form(None)))
    assert blocked(lambda: w.as_.token(form(get_code(w)[0], grant_type="password")))
    return "exact redirect_uri (%d variants refused), single-use, 60 s expiry, client and redirect binding" % len(REDIRECT_VARIANTS)


# ------------------------------------------------------------------ milestone 2
def m2():
    w = World(as_weak=("pkce",), client_weak=("pkce",))
    r = w.browser.open(mod.CLIENT_ORIGIN + "/login")
    assert r.status == 200 and r.body.get("logged_in"), f"a normal login should work: {r.status} {r.body}"
    sid = w.browser.cookies["app.example"]["app_sid"]
    assert w.client.tokens[sid]["token_type"] == "Bearer" and w.claims(w.client.tokens[sid])["sub"] == "alice"
    done_url = w.browser.history[-1]
    assert "/cb?" in done_url and "state=" in done_url, "the callback URL must carry the state"
    r = w.browser.open(done_url)
    assert r.status == 400 and r.body["defence"] == "state", "the same callback replayed must be refused (a pending login is one-shot)"
    # states are random and per session
    a = dict(parse_qsl(urlsplit(w.client.start("s1")).query))["state"]
    b = dict(parse_qsl(urlsplit(w.client.start("s2")).query))["state"]
    assert len(a) >= 16 and a != b, "state must be unguessable and different for every login"
    # CSRF login: the attacker's code arrives in the victim's browser
    attacker = w.new_browser("mallory")
    code, link = get_code(w, attacker, state="ATTACKER-STATE")
    victim = w.new_browser("alice")
    victim.mount(mod.CLIENT_ORIGIN, w.client)
    cases = {}
    victim.cookies["app.example"] = {"app_sid": "victim-1"}
    cases["victim has no login in progress"] = link
    w.client.start("victim-2")
    victim.cookies["app.example"] = {"app_sid": "victim-2"}
    cases["victim has her own login in progress (different state)"] = link
    code2, link2 = get_code(w, attacker, state=None)
    w.client.start("victim-3")
    victim.cookies["app.example"] = {"app_sid": "victim-3"}
    cases["callback without any state"] = link2
    before = len(w.token_calls)
    for name, url in cases.items():
        sid = {"victim has no login in progress": "victim-1", "victim has her own login in progress (different state)": "victim-2",
               "callback without any state": "victim-3"}[name]
        victim.cookies["app.example"] = {"app_sid": sid}
        r = victim.open(url)
        assert r.status == 400 and r.body["defence"] == "state", f"CSRF case '{name}' was not stopped by the state check: {r.status} {r.body}"
        assert sid not in w.client.tokens, f"CSRF case '{name}': the victim's session received a token for the attacker's account"
    assert len(w.token_calls) == before, "the client must reject the callback BEFORE spending the code at the token endpoint"
    victim.cookies["app.example"] = {"app_sid": "victim-4"}
    r = victim.open(f"{mod.CLIENT_ORIGIN}/cb?error=access_denied&state=x")
    assert r.status == 400, "an error callback is an error"
    with Spy(hmac, "compare_digest") as spy:
        w2 = World(as_weak=("pkce",), client_weak=("pkce",))
        w2.browser.open(mod.CLIENT_ORIGIN + "/login")
    assert spy.calls >= 1, "compare state values with hmac.compare_digest"
    return "state is random, per session and one-shot; 3 CSRF-login variants stopped before the code is spent"


# ------------------------------------------------------------------ milestone 3
def m3():
    assert mod.s256_challenge(RFC_VERIFIER) == RFC_CHALLENGE, "RFC 7636 appendix B: expected " + RFC_CHALLENGE
    vs = {mod.make_verifier() for _ in range(20)}
    assert len(vs) == 20 and all(mod.VERIFIER_RE.fullmatch(v) for v in vs), "verifiers: 43-128 unreserved characters, unique"
    w = World()
    r = w.browser.open(mod.CLIENT_ORIGIN + "/login")
    assert r.status == 200, f"the full flow with PKCE should work: {r.status} {r.body}"
    sent = w.token_calls[-1]
    verifier = sent.get("code_verifier")
    assert verifier and mod.s256_challenge(verifier), "the client must send its code_verifier to the token endpoint"
    urls = " ".join(w.browser.history)
    assert "code_challenge_method=S256" in urls, "the authorization request must say S256"
    assert verifier not in urls, "the verifier travels only on the back channel, never in a URL"
    # authorization side
    for name, over in [("missing challenge", dict(code_challenge=None)), ("plain method", dict(code_challenge_method="plain")),
                       ("no method", dict(code_challenge_method=None)), ("malformed challenge", dict(code_challenge="short"))]:
        q = auth_query(code_challenge=RFC_CHALLENGE, code_challenge_method="S256")
        q.update(over)
        q = {k: v for k, v in q.items() if v is not None}
        e = blocked(lambda: w.as_.authorize("alice", q))
        assert e and e.defence == "pkce", f"{name}: the AS must refuse the authorization request (defence 'pkce')"
    # token side
    def code_for(challenge):
        return get_code(w, code_challenge=challenge, code_challenge_method="S256")[0]
    code = code_for(RFC_CHALLENGE)
    tok = w.as_.token(form(code, code_verifier=RFC_VERIFIER))
    assert tok["access_token"], "the right verifier must work"
    for name, v in [("wrong verifier", mod.make_verifier()), ("missing verifier", None), ("empty verifier", ""),
                    ("verifier of the right length but other characters", "!" * 43)]:
        code = code_for(RFC_CHALLENGE)
        e = blocked(lambda: w.as_.token(form(code, **({"code_verifier": v} if v is not None else {}))))
        assert e and e.code == "invalid_grant" and e.defence == "pkce", f"{name}: expected invalid_grant (pkce), got {e}"
        assert blocked(lambda: w.as_.token(form(code, code_verifier=RFC_VERIFIER))), f"{name}: the code must be burned by the failed attempt"
    short = "abc"
    code = code_for(mod.s256_challenge(short))
    e = blocked(lambda: w.as_.token(form(code, code_verifier=short)))
    assert e and e.defence == "pkce", "a code_verifier shorter than 43 characters is refused even if its hash matches"
    with Spy(hmac, "compare_digest") as spy:
        w.as_.token(form(code_for(RFC_CHALLENGE), code_verifier=RFC_VERIFIER))
    assert spy.calls >= 1, "compare the challenge with hmac.compare_digest"
    return "RFC 7636 vector reproduced; S256 only, verifier on the back channel only, wrong/missing/short verifiers refused"


# ------------------------------------------------------------------ milestone 4
def claims_for(**over):
    now = 1_700_000_000.0
    c = {"iss": mod.AS_ORIGIN, "sub": "alice", "aud": mod.RS_AUDIENCE, "scope": "read", "client_id": "app-1",
         "iat": now, "exp": now + 300}
    c.update(over)
    return c


def m4():
    w = World(client_scope="read")
    assert w.browser.open(mod.CLIENT_ORIGIN + "/login").status == 200
    sid = w.browser.cookies["app.example"]["app_sid"]
    c = w.claims(w.client.tokens[sid])
    assert c["aud"] == mod.RS_AUDIENCE and c["scope"] == "read" and c["sub"] == "alice" and c["client_id"] == "app-1", f"token claims: {c}"
    assert c["exp"] - c["iat"] == 300, "access tokens live 300 s"
    r = w.client.api(sid, "GET", "/notes")
    assert r.status == 200 and r.body["user"] == "alice", f"read with a read token: {r.status} {r.body}"
    r = w.client.api(sid, "POST", "/notes", "buy milk")
    assert r.status == 403 and r.body["error"] == "insufficient_scope" and r.body["defence"] == "rs_scope", f"a read token must not write: {r.status} {r.body}"
    assert w.client.api(sid, "GET", "/admin/users").status == 403, "a read token must not reach the admin endpoint"
    # a client with write
    w2 = World(client_scope="read write")
    w2.browser.open(mod.CLIENT_ORIGIN + "/login")
    sid2 = w2.browser.cookies["app.example"]["app_sid"]
    assert w2.client.api(sid2, "POST", "/notes", "buy milk").status == 200
    assert w2.client.api(sid2, "GET", "/notes").body["notes"] == ["buy milk"]
    # resource server input handling
    now = w.clock.now()
    tokfn = lambda **o: mod.sign_token(KEY, claims_for(iat=now, exp=now + 300, **o))
    get = lambda h: w.rs.handle("GET", "/notes", h)
    bearer = lambda t: {"Authorization": "Bearer " + t}
    assert get({}).status == 401, "no credentials"
    assert get({"Authorization": "Basic YWxpY2U6cHc="}).status == 401, "wrong scheme"
    assert get({"Authorization": "Bearer"}).status == 401 and get({"Authorization": "Bearer "}).status == 401
    assert get(bearer("garbage")).status == 401 and get(bearer("a.b")).status == 401
    good = tokfn()
    assert get(bearer(good)).status == 200 and get({"Authorization": "bearer " + good}).status == 200
    forged = mod.sign_token(b"another key", claims_for(iat=now, exp=now + 300, scope="read write admin"))
    assert get(bearer(forged)).status == 401, "tokens signed with another key"
    body, sig = good.split(".")
    assert get(bearer(body + "." + sig[:-2] + ("AA" if sig[-2:] != "AA" else "BB"))).status == 401
    # audience
    r = get(bearer(tokfn(aud="https://billing.example")))
    assert r.status == 401 and r.body["defence"] == "aud", f"a token for another API must be refused (aud): {r.status} {r.body}"
    assert get(bearer(tokfn(aud=["https://billing.example", mod.RS_AUDIENCE]))).status == 200, "an audience list containing us is fine"
    assert get(bearer(tokfn(aud=None))).status == 401, "no audience"
    # scope matching is by whole word
    for sc in ("reader", "unread", "readwrite", "", "READ"):
        assert get(bearer(tokfn(scope=sc))).status == 403, f"scope {sc!r} must not satisfy 'read'"
    assert get(bearer(tokfn(scope="write read"))).status == 200
    # expiry
    w.clock.advance(300)
    r = get(bearer(good))
    assert r.status == 401 and r.body["defence"] == "expiry", "expired token"
    # authorization server: scope rules
    w3 = World()
    for sc in ("read admin", "admin", "", "write read extra"):
        e = blocked(lambda: w3.as_.authorize("alice", auth_query(scope=sc, code_challenge=RFC_CHALLENGE, code_challenge_method="S256")))
        assert e and e.code == "invalid_scope" and e.defence == "scope", f"authorization request for scope {sc!r} must be refused (invalid_scope)"
    q = dict(code_challenge=RFC_CHALLENGE, code_challenge_method="S256")
    code, _ = get_code(w3, scope="read write", **q)
    e = blocked(lambda: w3.as_.token(form(code, code_verifier=RFC_VERIFIER, scope="read write admin")))
    assert e and e.code == "invalid_scope", "a token request must not broaden the scope"
    code, _ = get_code(w3, scope="read write", **q)
    assert w3.as_.token(form(code, code_verifier=RFC_VERIFIER, scope="read"))["scope"] == "read", "a token request may narrow the scope"
    code, _ = get_code(w3, scope="write", **q)
    assert w3.as_.token(form(code, code_verifier=RFC_VERIFIER))["scope"] == "write"
    return "claims (aud, scope, 300 s), Bearer parsing, whole-word scopes, audience, expiry; AS refuses unregistered scope"


# ------------------------------------------------------------------ milestone 5
# Each attack returns (succeeded, defence_or_info). `weak` switches the named defence off.
def attack_interception(weak):
    w = World(as_weak=weak, client_weak=weak, client_site=False, client_uri=NATIVE_CB, client_scope="read")
    b = w.browser
    b.install_app("myapp", w.client.on_redirect)                    # the real app installed first
    evil = mod.MaliciousApp(w.as_, "app-1", NATIVE_CB)
    b.install_app("myapp", evil.on_redirect)                        # a second app claims the same scheme and wins
    b.open(w.client.start("native"))
    assert evil.stolen and "code" in evil.stolen, "(setup) the malicious app should have received the redirect"
    assert "native" not in w.client.tokens, "(setup) the real app never saw the code"
    e = blocked(lambda: setattr(evil, "tok", evil.redeem()))
    if e:
        return False, e.defence
    r = w.rs.handle("GET", "/notes", {"Authorization": "Bearer " + evil.tok["access_token"]})
    return r.status == 200, f"attacker calls the API as {r.body.get('user')}"


def attack_redirect(weak, uri=EVIL_CB):
    w = World(as_weak=weak)
    verifier = mod.make_verifier()
    r = w.browser.open(mod.tampered_authorize_url("app-1", uri, "read", "x", mod.s256_challenge(verifier)))
    got = [p for _, p in w.evil.requests if "code" in p]
    if r.status == 400 or not got:
        assert not w.evil.requests, "(setup) nothing may reach the attacker's site"
        return False, r.body.get("defence", "")
    tok = w.as_.token({"grant_type": "authorization_code", "code": got[0]["code"], "redirect_uri": uri,
                       "client_id": "app-1", "code_verifier": verifier})
    return True, f"attacker holds a token for {w.claims(tok)['sub']}"


def attack_csrf(as_weak, client_weak):
    w = World(as_weak=as_weak, client_weak=client_weak)
    attacker = w.new_browser("mallory")
    q = auth_query(state="ATK")
    if "pkce" not in client_weak:
        q.update(code_challenge=mod.s256_challenge(mod.make_verifier()), code_challenge_method="S256")
    r = attacker.open(AUTH + urlencode(q), follow=False)
    w.browser.cookies["app.example"] = {"app_sid": "victim-session"}
    r = w.browser.open(r.location)                                  # the victim is lured into opening the attacker's callback
    if r.status != 200:
        assert "victim-session" not in w.client.tokens and not w.token_calls, "(setup) no token may be exchanged"
        return False, r.body.get("defence", "")
    return True, f"victim's session now belongs to {w.claims(w.client.tokens['victim-session'])['sub']}"


def attack_replay(weak):
    w = World(as_weak=weak)
    assert w.browser.open(mod.CLIENT_ORIGIN + "/login").status == 200
    captured = dict(w.token_calls[-1])                              # a proxy log that recorded the whole token request
    e = blocked(lambda: setattr(w, "again", w.as_.token(captured)))
    return (False, e.defence) if e else (True, "a second access token was minted from the same code")


def escalate_authz(weak):
    w = World(as_weak=weak, client_scope="read admin")
    r = w.browser.open(mod.CLIENT_ORIGIN + "/login")
    if r.status != 200:
        return False, r.body.get("defence", "")
    sid = w.browser.cookies["app.example"]["app_sid"]
    r = w.client.api(sid, "GET", "/admin/users")
    return r.status == 200, "admin endpoint reached with a scope the client was never registered for"


def escalate_token(weak):
    w = World(as_weak=weak)
    v = mod.make_verifier()
    code, _ = get_code(w, code_challenge=mod.s256_challenge(v), code_challenge_method="S256", scope="read")
    e = blocked(lambda: setattr(w, "tok", w.as_.token(form(code, code_verifier=v, scope="read admin"))))
    if e:
        return False, e.defence
    return "admin" in w.tok["scope"].split(), "the token endpoint granted more scope than the user approved"


def escalate_rs(weak):
    w = World(rs_weak=weak, client_scope="read")
    w.browser.open(mod.CLIENT_ORIGIN + "/login")
    sid = w.browser.cookies["app.example"]["app_sid"]
    r = w.client.api(sid, "POST", "/notes", "pwned")
    return r.status == 200, r.body.get("defence", "") if r.status != 200 else "a read-only token wrote data"


def escalate_aud(weak):
    w = World(rs_weak=weak, audience="https://billing.example")
    w.browser.open(mod.CLIENT_ORIGIN + "/login")
    sid = w.browser.cookies["app.example"]["app_sid"]
    r = w.client.api(sid, "GET", "/notes")
    return r.status == 200, r.body.get("defence", "") if r.status != 200 else "a token for the billing API worked on the notes API"


def m5():
    suite = [
        ("code interception by a malicious app", attack_interception, ("pkce",), "pkce"),
        ("tampered redirect_uri", attack_redirect, ("redirect",), "redirect"),
        ("CSRF login with the attacker's code", None, None, "state"),
        ("replay of an already-used code", attack_replay, ("single_use",), "single_use"),
        ("scope escalation: unregistered scope", escalate_authz, ("scope",), "scope"),
        ("scope escalation: broaden at token request", escalate_token, ("scope",), "scope"),
        ("scope escalation: read token writes", escalate_rs, ("rs_scope",), "rs_scope"),
        ("wrong audience: token meant for another API", escalate_aud, ("aud",), "aud"),
    ]
    rows = [f"{'attack':<46}{'defence off':<14}{'all on':<10}stopped by"]
    for name, fn, weak, want in suite:
        if fn is None:                                              # CSRF needs weakness on two components
            off = attack_csrf(("pkce",), ("state", "pkce"))
            on = attack_csrf((), ())
        else:
            off, on = fn(weak), fn(())
        assert off[0], f"{name}: with '{want}' switched off the attack should SUCCEED, but it did not ({off[1]}). Is the exploit complete?"
        assert not on[0], f"{name}: the attack still works against the full solution: {on[1]}"
        assert on[1] == want, f"{name}: expected the '{want}' defence to stop it, but '{on[1]}' did"
        rows.append(f"{name:<46}{'succeeds':<14}{'fails':<10}{on[1]}")
    # variants of the redirect attack: every one must fail, and nothing may reach the attacker
    for uri in REDIRECT_VARIANTS[:-2] + ["https://app.example.evil.example/", "https://evil.example/cb?x=https://app.example/cb"]:
        ok, info = attack_redirect((), uri)
        assert not ok and info == "redirect", f"redirect_uri variant {uri!r} got through"
    # legitimate use still works with every defence on
    w = World(client_scope="read write")
    assert w.browser.open(mod.CLIENT_ORIGIN + "/login").status == 200
    sid = w.browser.cookies["app.example"]["app_sid"]
    assert w.client.api(sid, "POST", "/notes", "hello").status == 200 and w.client.api(sid, "GET", "/notes").body["notes"] == ["hello"]
    n = World(client_site=False, client_uri=NATIVE_CB)
    n.browser.install_app("myapp", n.client.on_redirect)
    assert n.browser.open(n.client.start("native")).status == 200 and "native" in n.client.tokens, "the honest native app must still log in"
    return "\n".join(rows)


print(f"Lab 3 checks against {target}.py\n")
check(1, "Milestone 1: authorization code flow, exact redirect_uri, single-use codes", m1)
check(2, "Milestone 2: state protects the callback from CSRF", m2)
check(3, "Milestone 3: PKCE with S256", m3)
check(4, "Milestone 4: scopes and audience enforced by the resource server", m4)
check(5, "Milestone 5: the attack suite", m5)
passed = sum(results)
print(f"\n{passed}/{len(results)} milestones passing" + ("  Lab complete!" if passed == len(results) else ""))
sys.exit(0 if passed == len(results) else 1)
