"""Lab 3 reference solution: OAuth 2.0 authorization code flow with PKCE, simulated in one process.

Four actors, all plain Python objects, no sockets:
    Browser             carries redirects, keeps cookies per site, hands custom-scheme URLs to "installed apps"
    AuthorizationServer https://auth.example   (front channel: /authorize, back channel: token())
    Client              https://app.example    (a public client: no secret, so it needs PKCE)
    ResourceServer      https://api.example    (checks tokens, scopes and audience)
Time is simulated (SimClock). Educational model: real servers add TLS, login pages, consent screens,
rate limits and much more.
"""
import base64
import hashlib
import hmac
import json
import re
import secrets
from collections import namedtuple
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit

AS_ORIGIN = "https://auth.example"
CLIENT_ORIGIN = "https://app.example"
RS_AUDIENCE = "https://api.example"


def b64u(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def unb64u(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


class SimClock:
    def __init__(self, t: float = 1_700_000_000.0):
        self.t = t

    def now(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


class OAuthError(Exception):
    """`code` follows RFC 6749 names; `defence` names the check that fired (redirect, pkce, single_use,
    expiry, state, scope, rs_scope, aud, signature, client...), so the attack suite can report it."""
    def __init__(self, code: str, detail: str = "", defence: str = ""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code, self.detail, self.defence = code, detail, defence

    def body(self):
        return {"error": self.code, "detail": self.detail, "defence": self.defence}


Response = namedtuple("Response", "status location body cookies")


def sign_token(key: bytes, claims: dict) -> str:
    body = b64u(json.dumps(claims, sort_keys=True, separators=(",", ":")).encode())
    return body + "." + b64u(hmac.new(key, body.encode(), hashlib.sha256).digest())


def open_token(key: bytes, token: str, now: float) -> dict:
    """Signature and expiry only. The audience and the scope are the resource server's job."""
    try:
        body, sig = token.split(".")
        claims = json.loads(unb64u(body))
        given = unb64u(sig)
    except Exception:
        raise OAuthError("invalid_token", "malformed", "signature") from None
    if not hmac.compare_digest(hmac.new(key, body.encode(), hashlib.sha256).digest(), given):
        raise OAuthError("invalid_token", "bad signature", "signature")
    if not isinstance(claims, dict) or not isinstance(claims.get("exp"), (int, float)) or now >= claims["exp"]:
        raise OAuthError("invalid_token", "expired", "expiry")
    return claims


# ---------------------------------------------------------------------------------- the browser
class Browser:
    """Follows redirects, keeps a cookie jar per site, and routes custom-scheme URLs to installed apps."""
    def __init__(self):
        self.sites = {}       # origin -> object with handle(path, params, cookies) -> Response
        self.apps = {}        # scheme -> [handlers]; the LAST one installed wins (the OS decides, not the app)
        self.cookies = {}     # host -> {name: value}
        self.history = []     # every URL requested, in order

    def mount(self, origin: str, site) -> None:
        self.sites[origin] = site

    def install_app(self, scheme: str, handler) -> None:
        self.apps.setdefault(scheme, []).append(handler)

    def open(self, url: str, follow: bool = True) -> Response:
        for _ in range(10):
            self.history.append(url)
            sp = urlsplit(url)
            if sp.scheme not in ("http", "https"):
                handlers = self.apps.get(sp.scheme)
                resp = handlers[-1](url) if handlers else Response(404, None, {"error": "no app for " + sp.scheme}, {})
            else:
                site = self.sites.get(f"{sp.scheme}://{sp.netloc}")
                if site is None:
                    resp = Response(502, None, {"error": "unknown site " + sp.netloc}, {})
                else:
                    jar = self.cookies.setdefault(sp.netloc, {})
                    resp = site.handle(sp.path or "/", dict(parse_qsl(sp.query, keep_blank_values=True)), dict(jar))
                    jar.update(resp.cookies)
            if follow and resp.status in (301, 302, 303) and resp.location:
                url = urljoin(url, resp.location)
                continue
            return resp
        raise RuntimeError("too many redirects")


class Collector:
    """A website the attacker runs. It records whatever is sent to it."""
    def __init__(self):
        self.requests = []

    def handle(self, path, params, cookies):
        self.requests.append((path, dict(params)))
        return Response(200, None, {"collected": True}, {})


# ---------------------------------------------------------------------------------- PKCE (RFC 7636)
VERIFIER_RE = re.compile(r"[A-Za-z0-9\-._~]{43,128}")


def make_verifier() -> str:
    return b64u(secrets.token_bytes(32))                       # 43 characters


def s256_challenge(verifier: str) -> str:
    return b64u(hashlib.sha256(verifier.encode("ascii")).digest())


# ---------------------------------------------------------------------------------- authorization server
class AuthorizationServer:
    CODE_TTL = 60
    TOKEN_TTL = 300

    def __init__(self, clock: SimClock, key: bytes, clients: dict, audience: str = RS_AUDIENCE, weak=()):
        self.clock, self.key, self.clients, self.audience = clock, key, clients, audience
        self.weak = frozenset(weak)       # defences switched OFF, for the control experiments only
        self.sessions = {}                # as_sid cookie -> user (who is logged in at the AS)
        self.codes = {}                   # code -> record

    # --- given -----------------------------------------------------------------------------
    def login(self, browser: Browser, user: str) -> None:
        sid = secrets.token_hex(8)
        self.sessions[sid] = user
        browser.cookies.setdefault("auth.example", {})["as_sid"] = sid

    def handle(self, path, params, cookies):
        if path != "/authorize":
            return Response(404, None, {"error": "not found"}, {})
        try:
            return Response(302, self.authorize(self.sessions.get(cookies.get("as_sid")), params), {}, {})
        except OAuthError as e:
            return Response(400, None, e.body(), {})      # an error PAGE: never redirected anywhere

    # --- milestone 1 -----------------------------------------------------------------------
    def redirect_ok(self, client_id: str, uri: str) -> bool:
        registered = self.clients[client_id]["redirect_uris"]
        if "redirect" in self.weak:                       # the sloppy rule: a string prefix of the origin
            return any(uri.startswith(r.rsplit("/", 1)[0]) for r in registered)
        return uri in registered                          # exact string match, nothing cleverer

    def authorize(self, user, params: dict) -> str:
        client_id, uri = params.get("client_id"), params.get("redirect_uri", "")
        if client_id not in self.clients:
            raise OAuthError("invalid_client", "unknown client", "client")
        if not self.redirect_ok(client_id, uri):
            raise OAuthError("invalid_request", "redirect_uri is not registered", "redirect")
        if params.get("response_type") != "code":
            raise OAuthError("unsupported_response_type", "only the code flow is offered", "client")
        if user is None:
            raise OAuthError("login_required", "nobody is logged in at the authorization server", "client")
        scope = self._grant_scope(client_id, params.get("scope", ""))
        challenge = self._read_challenge(params)
        code = secrets.token_urlsafe(16)
        self.codes[code] = {"client_id": client_id, "redirect_uri": uri, "user": user, "scope": scope,
                            "challenge": challenge, "expires": self.clock.now() + self.CODE_TTL, "used": False}
        query = {"code": code}
        if "state" in params:
            query["state"] = params["state"]
        return uri + ("&" if "?" in uri else "?") + urlencode(query)

    def token(self, params: dict) -> dict:
        if params.get("grant_type") != "authorization_code":
            raise OAuthError("unsupported_grant_type", "", "client")
        rec = self.codes.get(params.get("code"))
        if rec is None:
            raise OAuthError("invalid_grant", "unknown code", "code")
        if rec["used"] and "single_use" not in self.weak:
            raise OAuthError("invalid_grant", "code was already used", "single_use")
        rec["used"] = True                                # burn it on the FIRST attempt, right or wrong
        if self.clock.now() >= rec["expires"]:
            raise OAuthError("invalid_grant", "code expired", "expiry")
        if params.get("client_id") != rec["client_id"]:
            raise OAuthError("invalid_grant", "code was issued to another client", "client")
        if params.get("redirect_uri") != rec["redirect_uri"]:
            raise OAuthError("invalid_grant", "redirect_uri differs from the authorization request", "redirect")
        self._check_pkce(rec, params.get("code_verifier"))
        scope = rec["scope"]
        if "scope" in params:                             # narrowing is fine; broadening is escalation
            asked = params["scope"].split()
            if not set(asked) <= set(rec["scope"].split()) and "scope" not in self.weak:
                raise OAuthError("invalid_scope", "more than was authorized", "scope")
            scope = " ".join(asked)
        now = self.clock.now()
        claims = {"iss": AS_ORIGIN, "sub": rec["user"], "aud": self.audience, "scope": scope,
                  "client_id": rec["client_id"], "iat": now, "exp": now + self.TOKEN_TTL, "jti": secrets.token_hex(8)}
        return {"access_token": sign_token(self.key, claims), "token_type": "Bearer",
                "expires_in": self.TOKEN_TTL, "scope": scope}

    # --- milestone 3 -----------------------------------------------------------------------
    def _read_challenge(self, params: dict):
        challenge, method = params.get("code_challenge"), params.get("code_challenge_method")
        if challenge is None:
            if "pkce" in self.weak:
                return None
            raise OAuthError("invalid_request", "PKCE is required: code_challenge is missing", "pkce")
        if method != "S256":
            raise OAuthError("invalid_request", "only code_challenge_method=S256 is accepted", "pkce")
        if not re.fullmatch(r"[A-Za-z0-9_-]{43}", challenge):
            raise OAuthError("invalid_request", "malformed code_challenge", "pkce")
        return challenge

    def _check_pkce(self, rec: dict, verifier) -> None:
        if rec["challenge"] is None:
            if "pkce" in self.weak:
                return
            raise OAuthError("invalid_grant", "no challenge on record", "pkce")
        if not isinstance(verifier, str) or not VERIFIER_RE.fullmatch(verifier):
            raise OAuthError("invalid_grant", "code_verifier missing or malformed", "pkce")
        if not hmac.compare_digest(s256_challenge(verifier), rec["challenge"]):
            raise OAuthError("invalid_grant", "code_verifier does not match the challenge", "pkce")

    # --- milestone 4 -----------------------------------------------------------------------
    def _grant_scope(self, client_id: str, requested: str) -> str:
        asked = requested.split()
        allowed = set(self.clients[client_id]["scopes"].split())
        if "scope" in self.weak:
            return " ".join(asked)
        if not asked or not set(asked) <= allowed:
            raise OAuthError("invalid_scope", "scope is empty or not registered for this client", "scope")
        return " ".join(sorted(set(asked)))


# ---------------------------------------------------------------------------------- the client
class Client:
    """A public client (no secret). `sid` identifies one browser session or one app instance."""
    def __init__(self, client_id: str, redirect_uri: str, as_: AuthorizationServer, scope: str = "read",
                 rs=None, weak=()):
        self.client_id, self.redirect_uri, self.as_, self.scope, self.rs = client_id, redirect_uri, as_, scope, rs
        self.weak = frozenset(weak)
        self.pending = {}     # sid -> {"state": ..., "verifier": ...}
        self.tokens = {}      # sid -> token response

    # --- given: the wrappers around start() and finish() -----------------------------------
    def handle(self, path, params, cookies):
        sid = cookies.get("app_sid")
        if path == "/login":
            sid = sid or secrets.token_hex(8)
            return Response(302, self.start(sid), {}, {"app_sid": sid})
        if path == "/cb":
            try:
                self.finish(sid, params)
                return Response(200, None, {"logged_in": True}, {})
            except OAuthError as e:
                return Response(400, None, e.body(), {})
        return Response(404, None, {"error": "not found"}, {})

    def on_redirect(self, url: str):
        """Native-app entry point: the OS calls this when it opens our custom-scheme redirect URI."""
        try:
            self.finish("native", dict(parse_qsl(urlsplit(url).query)))
            return Response(200, None, {"logged_in": True}, {})
        except OAuthError as e:
            return Response(400, None, e.body(), {})

    def api(self, sid, method, path, body=None):
        return self.rs.handle(method, path, {"Authorization": "Bearer " + self.tokens[sid]["access_token"]}, body)

    # --- milestones 2 and 3 ----------------------------------------------------------------
    def _pkce_new(self):
        verifier = make_verifier()
        return verifier, s256_challenge(verifier)

    def start(self, sid: str) -> str:
        params = {"response_type": "code", "client_id": self.client_id, "redirect_uri": self.redirect_uri,
                  "scope": self.scope}
        pend = {}
        if "state" not in self.weak:
            pend["state"] = secrets.token_urlsafe(16)
            params["state"] = pend["state"]
        if "pkce" not in self.weak:
            pend["verifier"], challenge = self._pkce_new()
            params.update(code_challenge=challenge, code_challenge_method="S256")
        self.pending[sid] = pend
        return AS_ORIGIN + "/authorize?" + urlencode(params)

    def finish(self, sid, params: dict) -> dict:
        pend = self.pending.pop(sid, None)                 # one-shot: a callback can only be used once
        if "error" in params:
            raise OAuthError(params["error"], params.get("error_description", ""), "client")
        if "state" not in self.weak:
            if pend is None or not hmac.compare_digest(pend["state"], params.get("state", "")):
                raise OAuthError("invalid_request", "state does not match this session: possible CSRF", "state")
        pend = pend or {}
        form = {"grant_type": "authorization_code", "code": params.get("code"), "redirect_uri": self.redirect_uri,
                "client_id": self.client_id}
        if pend.get("verifier"):
            form["code_verifier"] = pend["verifier"]
        tok = self.as_.token(form)
        self.tokens[sid] = tok
        return tok


# ---------------------------------------------------------------------------------- the resource server
class ResourceServer:
    ROUTES = {("GET", "/notes"): "read", ("POST", "/notes"): "write", ("GET", "/admin/users"): "admin"}

    def __init__(self, clock: SimClock, key: bytes, audience: str = RS_AUDIENCE, weak=()):
        self.clock, self.key, self.audience, self.weak = clock, key, audience, frozenset(weak)
        self.notes = {}

    def handle(self, method, path, headers, body=None):
        needed = self.ROUTES.get((method, path))
        if needed is None:
            return Response(404, None, {"error": "not found"}, {})
        try:
            claims = self.authenticate(headers, needed)
        except OAuthError as e:
            return Response(403 if e.code == "insufficient_scope" else 401, None, e.body(), {})
        if (method, path) == ("POST", "/notes"):
            self.notes.setdefault(claims["sub"], []).append(body)
        if path == "/admin/users":
            return Response(200, None, {"users": sorted(self.notes) + ["(everyone)"]}, {})
        return Response(200, None, {"user": claims["sub"], "notes": list(self.notes.get(claims["sub"], []))}, {})

    # --- milestone 4 -----------------------------------------------------------------------
    def authenticate(self, headers: dict, needed: str) -> dict:
        auth = headers.get("Authorization", "")
        scheme, _, token = auth.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise OAuthError("invalid_token", "send  Authorization: Bearer <token>", "signature")
        claims = open_token(self.key, token, self.clock.now())
        if "aud" not in self.weak:
            aud = claims.get("aud")
            if self.audience not in (aud if isinstance(aud, list) else [aud]):
                raise OAuthError("invalid_token", "this token was issued for a different API", "aud")
        if "rs_scope" not in self.weak and needed not in str(claims.get("scope", "")).split():
            raise OAuthError("insufficient_scope", f"this endpoint needs scope '{needed}'", "rs_scope")
        return claims


# ---------------------------------------------------------------------------------- milestone 5: the attacker's side
class MaliciousApp:
    """A second app on the same device that registered the victim app's custom URL scheme.
    The OS may hand the authorization response to it. Runs only against our in-process servers."""
    def __init__(self, as_: AuthorizationServer, client_id: str, redirect_uri: str):
        self.as_, self.client_id, self.redirect_uri = as_, client_id, redirect_uri
        self.stolen = None

    def on_redirect(self, url: str):
        self.stolen = dict(parse_qsl(urlsplit(url).query))
        return Response(200, None, {"ok": "(looks like nothing happened)"}, {})

    def redeem(self) -> dict:
        """Exchange the stolen code. The attacker never saw the client's code_verifier."""
        return self.as_.token({"grant_type": "authorization_code", "code": self.stolen["code"],
                               "redirect_uri": self.redirect_uri, "client_id": self.client_id})


def tampered_authorize_url(client_id: str, evil_redirect_uri: str, scope: str, state: str = "x", challenge: str = None) -> str:
    """A link an attacker sends to a logged-in victim: a real authorization request with the redirect
    address swapped for one the attacker controls."""
    q = {"response_type": "code", "client_id": client_id, "redirect_uri": evil_redirect_uri, "scope": scope, "state": state}
    if challenge:
        q.update(code_challenge=challenge, code_challenge_method="S256")
    return AS_ORIGIN + "/authorize?" + urlencode(q)
