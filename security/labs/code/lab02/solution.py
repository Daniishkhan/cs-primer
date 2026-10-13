"""Lab 2 reference solution: build and break a token format (standard library only).

A JWT-like token: base64url(header) . base64url(claims) . base64url(HMAC-SHA256 signature).
Everything runs in one process against verifiers written for this lab. Time is simulated.
"""
import base64
import hashlib
import hmac
import json
import re
import secrets

# --------------------------------------------------------------------------- shared helpers
_B64U = re.compile(r"[A-Za-z0-9_-]*")


def b64u(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def unb64u(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


class InvalidToken(Exception):
    """`reason` is a short machine-readable code: malformed, alg, signature, exp, nbf, iss, aud, kid, refresh."""
    def __init__(self, reason: str, detail: str = ""):
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason, self.detail = reason, detail


class SimClock:
    def __init__(self, t: float = 1_700_000_000.0):
        self.t = t

    def now(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


# --------------------------------------------------------------------------- milestone 1
def sign_hs256(key: bytes, signing_input: bytes) -> str:
    return b64u(hmac.new(key, signing_input, hashlib.sha256).digest())


def encode(claims: dict, key: bytes, kid: str = None, header_extra: dict = None) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    if kid is not None:
        header["kid"] = kid
    header.update(header_extra or {})
    h = b64u(json.dumps(header, separators=(",", ":"), sort_keys=True).encode())
    p = b64u(json.dumps(claims, separators=(",", ":"), sort_keys=True).encode())
    return f"{h}.{p}.{sign_hs256(key, f'{h}.{p}'.encode())}"


def decode_unverified(token: str):
    """-> (header, claims). NO signature check: for inspection and for the attack code only."""
    h, p, _ = token.split(".")
    return json.loads(unb64u(h)), json.loads(unb64u(p))


# --------------------------------------------------------------------------- milestone 2
ALLOWED_ALGS = ("HS256",)       # fixed in server configuration; the token never gets a vote


def _split(token):
    if not isinstance(token, str) or token.count(".") != 2:
        raise InvalidToken("malformed", "need exactly three dot-separated parts")
    h, p, s = token.split(".")
    for part in (h, p, s):
        if not _B64U.fullmatch(part) or len(part) % 4 == 1:
            raise InvalidToken("malformed", "not base64url")
        if b64u(unb64u(part)) != part:
            raise InvalidToken("malformed", "non-canonical base64url")
    try:
        header, claims = json.loads(unb64u(h)), json.loads(unb64u(p))
    except ValueError:
        raise InvalidToken("malformed", "header or claims are not JSON") from None
    if not isinstance(header, dict) or not isinstance(claims, dict):
        raise InvalidToken("malformed", "header and claims must be JSON objects")
    return header, claims, f"{h}.{p}".encode(), unb64u(s)


def _number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def check_claims(claims: dict, *, issuer: str, audience: str, now: float, leeway: float = 0) -> None:
    exp = claims.get("exp")
    if not _number(exp):
        raise InvalidToken("exp", "missing or not a number")
    if now - leeway >= exp:
        raise InvalidToken("exp", f"expired at {exp}")
    nbf = claims.get("nbf")
    if nbf is not None:
        if not _number(nbf):
            raise InvalidToken("nbf", "not a number")
        if now + leeway < nbf:
            raise InvalidToken("nbf", f"not valid before {nbf}")
    if claims.get("iss") != issuer:
        raise InvalidToken("iss", f"unexpected issuer {claims.get('iss')!r}")
    aud = claims.get("aud")
    auds = aud if isinstance(aud, list) else [aud]
    if audience not in auds:
        raise InvalidToken("aud", f"this token is not for {audience!r}")


def verify(token: str, key: bytes, *, issuer: str, audience: str, now: float, leeway: float = 0,
           algs: tuple = ALLOWED_ALGS) -> dict:
    header, claims, signing_input, sig = _split(token)
    if header.get("alg") not in algs or "crit" in header:
        raise InvalidToken("alg", f"algorithm {header.get('alg')!r} is not allowed")
    if header["alg"] != "HS256":
        raise InvalidToken("alg", "this lab only implements HS256")   # RS256 is out of scope (no RSA in the stdlib)
    expected = hmac.new(key, signing_input, hashlib.sha256).digest()
    if not hmac.compare_digest(expected, sig):
        raise InvalidToken("signature", "does not match")
    check_claims(claims, issuer=issuer, audience=audience, now=now, leeway=leeway)
    return claims


# --------------------------------------------------------------------------- milestone 3
# The provided vulnerable code (NAIVE) lives in naive_verify below. These are the attacks.
def forge_alg_none(claims: dict) -> str:
    h = b64u(b'{"alg":"none","typ":"JWT"}')
    return f"{h}.{b64u(json.dumps(claims, separators=(',', ':')).encode())}."


def forge_strip_signature(token: str) -> str:
    h, p, _ = token.split(".")
    return f"{h}.{p}."


def forge_alg_switch(claims: dict, public_key: bytes) -> str:
    """The verifier is configured with a PUBLIC key (RS256 in real life). Use it as an HMAC secret."""
    return encode(claims, public_key)


def forge_tamper(token: str, **changes) -> str:
    h, p, s = token.split(".")
    claims = json.loads(unb64u(p))
    claims.update(changes)
    return f"{h}.{b64u(json.dumps(claims, separators=(',', ':')).encode())}.{s}"


PUBLIC_KEY = b"-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkqhkiG9w0B...(published at /jwks)...\n-----END PUBLIC KEY-----\n"


def naive_verify(token: str, key: bytes, now: float) -> dict:
    """DELIBERATELY VULNERABLE. Written the way real bugs are written; do not copy."""
    h, p, s = token.split(".")
    header, claims = json.loads(unb64u(h)), json.loads(unb64u(p))
    alg = header["alg"]                                        # bug 1: the token chooses the algorithm
    if alg.lower() == "none":
        return claims
    if alg == "HS256":
        expected = hmac.new(key, f"{h}.{p}".encode(), hashlib.sha256).digest()
        if s and not hmac.compare_digest(expected, unb64u(s)):  # bug 2: an empty signature skips the check
            raise InvalidToken("signature", "does not match")
        return claims                                          # bug 3: no exp / iss / aud checks at all
    raise InvalidToken("alg", "unsupported")


# --------------------------------------------------------------------------- milestone 4
class Keyring:
    def __init__(self):
        self.keys = {}
        self.signing_kid = None

    def add(self, kid: str, key: bytes, signing: bool = False) -> None:
        self.keys[kid] = key
        if signing or self.signing_kid is None:
            self.signing_kid = kid

    def retire(self, kid: str) -> None:
        self.keys.pop(kid, None)


def issue(ring: Keyring, claims: dict) -> str:
    return encode(claims, ring.keys[ring.signing_kid], kid=ring.signing_kid)


def verify_with_keyring(token: str, ring: Keyring, **kw) -> dict:
    header, _, _, _ = _split(token)
    kid = header.get("kid")
    if not isinstance(kid, str) or kid not in ring.keys:    # a dict lookup: kid is NEVER a path or a query
        raise InvalidToken("kid", "unknown or missing key id")
    return verify(token, ring.keys[kid], **kw)


def naive_keyring_verify(token: str, ring: Keyring, now: float) -> dict:
    """DELIBERATELY VULNERABLE: an unknown kid falls back to an empty key."""
    h, p, s = token.split(".")
    header, claims = json.loads(unb64u(h)), json.loads(unb64u(p))
    key = ring.keys.get(header.get("kid"), b"")                # bug: attacker picks a kid nobody has
    expected = hmac.new(key, f"{h}.{p}".encode(), hashlib.sha256).digest()
    if not hmac.compare_digest(expected, unb64u(s)):
        raise InvalidToken("signature", "does not match")
    return claims


# --------------------------------------------------------------------------- milestone 5
class TokenService:
    """Issues short-lived access tokens and rotating refresh tokens. All state is in memory."""

    def __init__(self, ring: Keyring, clock: SimClock, issuer="https://auth.example", audience="api.example",
                 access_ttl=300, refresh_ttl=86400):
        self.ring, self.clock, self.issuer, self.audience = ring, clock, issuer, audience
        self.access_ttl, self.refresh_ttl = access_ttl, refresh_ttl
        self.families = {}       # family id -> {"user", "current", "revoked", "expires"}
        self.owner = {}          # refresh token -> family id, for EVERY token ever issued

    def _access(self, user, family):
        now = self.clock.now()
        return issue(self.ring, {"iss": self.issuer, "aud": self.audience, "sub": user, "sid": family,
                                 "jti": secrets.token_hex(8), "iat": now, "exp": now + self.access_ttl})

    def login(self, user: str):
        family, refresh = secrets.token_hex(8), secrets.token_urlsafe(24)
        self.families[family] = {"user": user, "current": refresh, "revoked": False,
                                 "expires": self.clock.now() + self.refresh_ttl}
        self.owner[refresh] = family
        return self._access(user, family), refresh

    def refresh(self, token: str):
        family = self.owner.get(token)
        if family is None:
            raise InvalidToken("refresh", "unknown refresh token")
        f = self.families[family]
        if f["revoked"]:
            raise InvalidToken("refresh", "family revoked")
        if token != f["current"]:                       # an OLD token came back: someone holds a copy
            f["revoked"] = True                         # kill the whole family, the thief's and the victim's
            raise InvalidToken("refresh", "reuse detected: family revoked")
        if self.clock.now() >= f["expires"]:
            raise InvalidToken("refresh", "refresh token expired")
        new = secrets.token_urlsafe(24)
        f["current"] = new
        self.owner[new] = family
        return self._access(f["user"], family), new

    def logout(self, token: str) -> None:
        family = self.owner.get(token)
        if family is not None:
            self.families[family]["revoked"] = True

    def check_access(self, token: str) -> dict:
        """What an API does: signature and claims only. No database lookup."""
        return verify_with_keyring(token, self.ring, issuer=self.issuer, audience=self.audience,
                                   now=self.clock.now(), leeway=0)
