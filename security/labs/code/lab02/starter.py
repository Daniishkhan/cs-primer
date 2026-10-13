"""Lab 2 starter: build and break a token format (standard library only).

A JWT-like token: base64url(header) . base64url(claims) . base64url(HMAC-SHA256 signature).
Everything runs in one process against verifiers written for this lab. Time is simulated.
Each TODO raises NotImplementedError until you fill it in. Run:  python3 check.py
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
    """Return base64url(HMAC-SHA256(key, signing_input)) with no '=' padding. Use b64u."""
    raise NotImplementedError("TODO milestone 1: sign_hs256")


def encode(claims: dict, key: bytes, kid: str = None, header_extra: dict = None) -> str:
    """Return  b64u(header) . b64u(claims) . signature.
    Header: {"alg": "HS256", "typ": "JWT"}, plus "kid" when kid is given, plus header_extra.
    Serialise JSON compactly (separators=(",", ":"), sort_keys=True) so output is deterministic.
    The signature covers the ASCII text  "<b64u header>.<b64u claims>"  exactly as it appears in the token.
    """
    raise NotImplementedError("TODO milestone 1: encode")


def decode_unverified(token: str):
    """Return (header_dict, claims_dict) WITHOUT checking anything. For inspection and attack code only."""
    raise NotImplementedError("TODO milestone 1: decode_unverified")


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
    """Raise InvalidToken(reason, detail) for the first failing check, in this order:
    exp   missing or not a number (bool is not a number), or  now - leeway >= exp   -> reason "exp"
    nbf   present but not a number, or  now + leeway < nbf                         -> reason "nbf"
    iss   != issuer                                                                -> reason "iss"
    aud   a string or a list of strings; `audience` must be equal / a member       -> reason "aud"
    """
    raise NotImplementedError("TODO milestone 2: check_claims")


def verify(token: str, key: bytes, *, issuer: str, audience: str, now: float, leeway: float = 0,
           algs: tuple = ALLOWED_ALGS) -> dict:
    """The strict verifier. _split() is given: it rejects malformed tokens and returns
    (header, claims, signing_input_bytes, signature_bytes). Then, in this order:
    1. header["alg"] must be in `algs` (the caller's allow-list, default ALLOWED_ALGS; never taken from the
       token); also refuse any header with a "crit" member. Otherwise InvalidToken("alg", ...).
       This lab implements only HS256: if the allowed alg is something else, raise InvalidToken("alg", ...).
    2. Recompute the HMAC over signing_input with `key`, compare with hmac.compare_digest.
       Mismatch (this includes an empty signature) -> InvalidToken("signature", ...).
    3. Only now look at the claims: call check_claims. Never trust claims before the signature passed.
    Return the claims.
    """
    raise NotImplementedError("TODO milestone 2: verify")


# --------------------------------------------------------------------------- milestone 3
# The provided vulnerable code (NAIVE) lives in naive_verify below. These are the attacks.
def forge_alg_none(claims: dict) -> str:
    """Build a token whose header says {"alg":"none","typ":"JWT"}, with your claims and an EMPTY third part (the token ends in a dot)."""
    raise NotImplementedError("TODO milestone 3: forge_alg_none")


def forge_strip_signature(token: str) -> str:
    """Take a genuine token and remove its signature, keeping the trailing dot: header.claims."""
    raise NotImplementedError("TODO milestone 3: forge_strip_signature")


def forge_alg_switch(claims: dict, public_key: bytes) -> str:
    """The target is configured with a PUBLIC key (the kind of key that RS256 verifiers hold).
    Produce a token that a verifier trusting the header's alg would accept: sign HS256, using the public
    key's bytes as the HMAC secret. Anyone can do this, because the key is public.
    """
    raise NotImplementedError("TODO milestone 3: forge_alg_switch")


def forge_tamper(token: str, **changes) -> str:
    """Take a genuine token, change claims (e.g. sub, role) and keep the ORIGINAL signature part. Return the new token."""
    raise NotImplementedError("TODO milestone 3: forge_tamper")


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
    """Read the header (via _split), take its "kid", and look the key up in ring.keys.
    kid must be a str that is a key of ring.keys; otherwise InvalidToken("kid", ...). It is only ever a
    dictionary key: never a file name, a URL or a query. Then call verify(token, that_key, **kw).
    """
    raise NotImplementedError("TODO milestone 4: verify_with_keyring")


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
        """Rotate a refresh token. self.owner maps every token ever issued to its family;
        self.families[family] has "current", "revoked", "expires", "user".
        - unknown token                                    -> InvalidToken("refresh", ...)
        - family already revoked                           -> InvalidToken("refresh", ...)
        - token is not the family's current one (REUSE)    -> mark the whole family revoked, then raise InvalidToken("refresh", "reuse detected...")
        - clock.now() >= family["expires"]                 -> InvalidToken("refresh", ...)
        - otherwise: mint a new refresh token (secrets.token_urlsafe), make it "current", record it in self.owner,
          and return (new access token via self._access(user, family), new refresh token).
        """
        raise NotImplementedError("TODO milestone 5: TokenService.refresh")

    def logout(self, token: str) -> None:
        """Revoke the whole family that `token` belongs to. Unknown tokens: do nothing."""
        raise NotImplementedError("TODO milestone 5: TokenService.logout")

    def check_access(self, token: str) -> dict:
        """What an API does: signature and claims only. No database lookup."""
        return verify_with_keyring(token, self.ring, issuer=self.issuer, audience=self.audience,
                                   now=self.clock.now(), leeway=0)
