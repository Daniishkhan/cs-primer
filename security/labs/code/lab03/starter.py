"""Lab 3 starter: OAuth 2.0 authorization code flow with PKCE, simulated in one process.

Four actors, all plain Python objects, no sockets:
    Browser             carries redirects, keeps cookies per site, hands custom-scheme URLs to "installed apps"
    AuthorizationServer https://auth.example   (front channel: /authorize, back channel: token())
    Client              https://app.example    (a public client: no secret, so it needs PKCE)
    ResourceServer      https://api.example    (checks tokens, scopes and audience)
Time is simulated (SimClock). Educational model: real servers add TLS, login pages, consent screens,
rate limits and much more.

Everything not marked TODO is given and finished. Each TODO raises NotImplementedError until you
fill it in. `weak` is a set of defence names that the attack suite (milestone 5) switches OFF to
prove each attack is real; a defence you write must be skipped only when its name is in `weak`.
Run:  python3 check.py
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
    """A fresh high-entropy code_verifier: 32 random bytes from `secrets`, base64url-encoded (43 characters)."""
    raise NotImplementedError("TODO milestone 3: make_verifier")


def s256_challenge(verifier: str) -> str:
    """BASE64URL-ENCODE(SHA256(ASCII(verifier))) without padding (RFC 7636 section 4.2). Use b64u."""
    raise NotImplementedError("TODO milestone 3: s256_challenge")


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
        """True if `uri` is acceptable for this client.
        Exact string equality with one of the client's registered redirect_uris: no prefixes, no
        normalisation, no wildcards. (When "redirect" is in self.weak, use the sloppy rule many real servers
        once had: any(uri.startswith(r.rsplit("/", 1)[0]) for r in registered). The control experiments need it.)
        """
        raise NotImplementedError("TODO milestone 1: AuthorizationServer.redirect_ok")

    def authorize(self, user, params: dict) -> str:
        """Front channel. `user` is who is logged in at the AS (None if nobody); `params` are the query
        parameters. Return the URL to redirect the browser to. In this order:
        1. unknown client_id                      -> OAuthError("invalid_client", ..., "client")
        2. redirect_uri not acceptable            -> OAuthError("invalid_request", ..., "redirect")
           (An error PAGE, never a redirect: the address is not trusted.)
        3. response_type != "code"                -> OAuthError("unsupported_response_type", ..., "client")
        4. user is None                           -> OAuthError("login_required", ..., "client")
        5. scope = self._grant_scope(client_id, params.get("scope", ""))      (milestone 4)
        6. challenge = self._read_challenge(params)                            (milestone 3)
        7. code = secrets.token_urlsafe(16); remember a record in self.codes[code] with: client_id, redirect_uri,
           user, scope, challenge, expires (= clock.now() + CODE_TTL), used=False.
        8. Return redirect_uri + "?" + urlencode({"code": code, "state": params["state"]})  (state only if sent;
           use "&" instead of "?" if the redirect_uri already has a query).
        """
        raise NotImplementedError("TODO milestone 1: AuthorizationServer.authorize")

    def token(self, params: dict) -> dict:
        """Back channel. `params` is the form body. Return
        {"access_token", "token_type": "Bearer", "expires_in", "scope"}. In this order:
        1. grant_type must be "authorization_code"                      -> OAuthError("unsupported_grant_type", ...)
        2. unknown code                                                 -> OAuthError("invalid_grant", ..., "code")
        3. rec["used"] already True (unless "single_use" in self.weak)  -> OAuthError("invalid_grant", ..., "single_use")
           Then set rec["used"] = True: a code is burned by its FIRST use, whether or not the rest succeeds.
        4. clock.now() >= rec["expires"]                                -> OAuthError("invalid_grant", ..., "expiry")
        5. client_id differs from the record                            -> OAuthError("invalid_grant", ..., "client")
        6. redirect_uri differs from the record's                       -> OAuthError("invalid_grant", ..., "redirect")
        7. self._check_pkce(rec, params.get("code_verifier"))           (milestone 3)
        8. scope: the record's scope; if the request has a "scope" parameter it may only NARROW it:
           asking for more -> OAuthError("invalid_scope", ..., "scope")   (skipped if "scope" in self.weak)
        9. Mint the token with sign_token(self.key, claims). Claims: iss=AS_ORIGIN, sub=user, aud=self.audience,
           scope, client_id, iat=now, exp=now + TOKEN_TTL, jti=<random>.
        """
        raise NotImplementedError("TODO milestone 1: AuthorizationServer.token")

    # --- milestone 3 -----------------------------------------------------------------------
    def _read_challenge(self, params: dict):
        """Milestone 3 (until then: no PKCE). Return the code_challenge from `params`, or None.
        - challenge missing: None if "pkce" in self.weak, else OAuthError("invalid_request", ..., "pkce")
        - code_challenge_method must be exactly "S256" ("plain" is refused)   -> OAuthError(..., "pkce")
        - the challenge must be 43 base64url characters                       -> OAuthError(..., "pkce")
        """
        return None   # TODO milestone 3

    def _check_pkce(self, rec: dict, verifier) -> None:
        """Milestone 3 (until then: no PKCE). `rec` is the code's record, `verifier` the code_verifier sent to token().
        - no challenge on record: fine if "pkce" in self.weak, else OAuthError("invalid_grant", ..., "pkce")
        - verifier missing, or not matching VERIFIER_RE (43-128 unreserved characters) -> OAuthError(..., "pkce")
        - s256_challenge(verifier) must equal rec["challenge"] (hmac.compare_digest) -> OAuthError(..., "pkce")
        """
        return   # TODO milestone 3

    # --- milestone 4 -----------------------------------------------------------------------
    def _grant_scope(self, client_id: str, requested: str) -> str:
        """Milestone 4 (until then: whatever was asked for). `requested` is the space-separated scope string.
        Return the granted scope string. The client's registered scopes are self.clients[client_id]["scopes"].
        - empty request, or any scope the client is not registered for -> OAuthError("invalid_scope", ..., "scope")
        - (when "scope" in self.weak: grant whatever was asked for)
        """
        return requested   # TODO milestone 4


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
        """Return (verifier, challenge) for a new login: make_verifier() and its S256 challenge."""
        raise NotImplementedError("TODO milestone 3: Client._pkce_new")

    def start(self, sid: str) -> str:
        """Begin a login for session `sid`; return the authorization URL (AS_ORIGIN + "/authorize?" + urlencode(...)).
        Parameters: response_type=code, client_id, redirect_uri, scope. Then:
        - unless "state" in self.weak: a fresh random state (secrets.token_urlsafe(16)), sent in the URL
        - unless "pkce" in self.weak: verifier, challenge = self._pkce_new(); send code_challenge and
          code_challenge_method=S256 (milestone 3)
        Remember what you need for the callback in self.pending[sid] (a dict).
        """
        raise NotImplementedError("TODO milestone 2: Client.start")

    def finish(self, sid, params: dict) -> dict:
        """Handle the callback for session `sid` with the redirect's query `params`. Return the token response
        and store it in self.tokens[sid].
        1. pend = self.pending.pop(sid, None)   (a pending login can be finished once)
        2. an "error" parameter in the callback -> OAuthError(params["error"], ..., "client")
        3. unless "state" in self.weak: no pending login for this session, or the callback's state differs
           (compare with hmac.compare_digest) -> OAuthError("invalid_request", ..., "state")
        4. exchange the code: self.as_.token({grant_type, code, redirect_uri, client_id}) and include
           code_verifier whenever the pending login has one.
        """
        raise NotImplementedError("TODO milestone 2: Client.finish")


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
        """Return the token's claims if this request may use an endpoint that needs scope `needed`, else raise OAuthError.
        1. Authorization header must be "Bearer <token>" (scheme case-insensitive) -> else OAuthError("invalid_token", ..., "signature")
        2. claims = open_token(self.key, token, self.clock.now())   (given: checks signature and expiry)
        3. audience: self.audience must equal claims["aud"] (or be in it, if it is a list)
           -> OAuthError("invalid_token", ..., "aud")                       (skipped if "aud" in self.weak)
        4. scope: `needed` must be one of claims["scope"].split()  -- whole words, not a substring
           -> OAuthError("insufficient_scope", ..., "rs_scope")             (skipped if "rs_scope" in self.weak)
        """
        raise NotImplementedError("TODO milestone 4: ResourceServer.authenticate")


# ---------------------------------------------------------------------------------- milestone 5: the attacker's side
class MaliciousApp:
    """A second app on the same device that registered the victim app's custom URL scheme.
    The OS may hand the authorization response to it. Runs only against our in-process servers."""
    def __init__(self, as_: AuthorizationServer, client_id: str, redirect_uri: str):
        self.as_, self.client_id, self.redirect_uri = as_, client_id, redirect_uri
        self.stolen = None

    def on_redirect(self, url: str):
        """The OS delivered the victim's authorization response to us. Parse the query of `url` into a dict, keep it
        in self.stolen, and return Response(200, None, {}, {}) so nothing looks wrong.
        """
        raise NotImplementedError("TODO milestone 5: MaliciousApp.on_redirect")

    def redeem(self) -> dict:
        """Exchange the stolen code at the token endpoint exactly as the real client would, using only what a
        second app on the device can know: the code, the public client_id and the registered redirect_uri. It never
        saw the code_verifier. Return the token response (or let OAuthError propagate).
        """
        raise NotImplementedError("TODO milestone 5: MaliciousApp.redeem")


def tampered_authorize_url(client_id: str, evil_redirect_uri: str, scope: str, state: str = "x", challenge: str = None) -> str:
    """Return AS_ORIGIN + "/authorize?" + urlencode(...) for a real authorization request (response_type=code,
    client_id, scope, state) whose redirect_uri is `evil_redirect_uri`; add code_challenge and
    code_challenge_method=S256 when `challenge` is given (the attacker chose it himself).
    """
    raise NotImplementedError("TODO milestone 5: tampered_authorize_url")
