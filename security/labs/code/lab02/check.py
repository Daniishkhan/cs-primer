"""Self-check for Lab 2: Build and Break a Token Format.

    python3 check.py                  # checks your starter.py
    python3 check.py solution         # checks the reference solution
    python3 check.py solution 3       # only milestone 3

Everything is deterministic: simulated time, fixed keys, no network. The "attacks" are forged
tokens fired at verifiers inside this one process: a provided deliberately naive verifier, and yours.
Prints a tick, a cross, or "not implemented yet" for each milestone. Runs in well under a second.
"""
import base64
import hashlib
import hmac
import importlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True

args = sys.argv[1:]
target = args[0] if args and not args[0].isdigit() else "starter"
rest = [a for a in args if a.isdigit()]
ONLY = int(rest[0]) if rest else None
mod = importlib.import_module(target)
results = []

NOW = 1_700_000_000
KEY = hashlib.sha256(b"lab 2 signing key").digest()
ISS, AUD = "https://auth.example", "api.example"
GOOD = {"iss": ISS, "aud": AUD, "sub": "alice", "role": "user", "iat": NOW, "exp": NOW + 900}
KW = dict(issuer=ISS, audience=AUD, now=NOW + 60)


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


# An independent minter, so each milestone is checked on its own and does not depend on your encode().
def b64u(b):
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def unb64u(s):
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def mint(claims, key=KEY, header=None):
    header = {"alg": "HS256", "typ": "JWT"} if header is None else header
    h = b64u(json.dumps(header, separators=(",", ":")).encode())
    p = b64u(json.dumps(claims, separators=(",", ":")).encode())
    return f"{h}.{p}.{b64u(hmac.new(key, f'{h}.{p}'.encode(), hashlib.sha256).digest())}"


def outcome(fn):
    """-> ('accepted', claims) or ('rejected', reason)."""
    try:
        return "accepted", fn()
    except mod.InvalidToken as e:
        return "rejected", e.reason


def strict(token, **over):
    kw = {**KW, **over}
    return mod.verify(token, KEY, **kw)


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


# ------------------------------------------------------------------ milestone 1
def m1():
    # RFC 7515 Appendix A.1: the signature of the specification's own example
    rfc_key = base64.urlsafe_b64decode("AyM1SysPpbyDfgZld3umj1qzKObwVMkoqQ-EstJQLr_T-1qS0gZH75aKtMN3Yj0iPS4hcgUuTwjAzZr1Z9CAow==")
    rfc_input = (b"eyJ0eXAiOiJKV1QiLA0KICJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJqb2UiLA0KICJleHAiOjEzMDA4MTkzODAsDQogImh0dHA6Ly9leGFtcGxlLmNvbS9pc19yb290Ijp0cnVlfQ")
    got = mod.sign_hs256(rfc_key, rfc_input)
    assert got == "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk", f"does not match the RFC 7515 A.1 signature, got {got}"
    tok = mod.encode(GOOD, KEY)
    parts = tok.split(".")
    assert len(parts) == 3 and "=" not in tok and "+" not in tok and "/" not in tok, "three base64url parts, no padding, no + or /"
    header, claims = mod.decode_unverified(tok)
    assert header == {"alg": "HS256", "typ": "JWT"}, f"header was {header}"
    assert claims == GOOD, "claims did not round-trip"
    assert mod.encode(GOOD, KEY) == tok, "encoding must be deterministic (compact JSON, sorted keys)"
    assert mod.sign_hs256(KEY, f"{parts[0]}.{parts[1]}".encode()) == parts[2], "signature must cover 'header.claims' exactly"
    assert hmac.compare_digest(hmac.new(KEY, f"{parts[0]}.{parts[1]}".encode(), hashlib.sha256).digest(), unb64u(parts[2]))
    assert mod.encode(GOOD, b"other key") != tok, "a different key must give a different signature"
    kt = mod.encode(GOOD, KEY, kid="k1")
    assert mod.decode_unverified(kt)[0]["kid"] == "k1", "kid must appear in the header"
    assert "kid" not in mod.decode_unverified(tok)[0]
    return "RFC 7515 A.1 signature reproduced; round trip, deterministic, base64url without padding"


# ------------------------------------------------------------------ milestone 2
def m2():
    ok = strict(mint(GOOD))
    assert ok == GOOD, "a valid token must return its claims"
    R = lambda tok, **o: outcome(lambda: strict(tok, **o))
    cases = [
        ("expired", mint(GOOD), dict(now=NOW + 900), "exp"),
        ("one second before expiry", mint(GOOD), dict(now=NOW + 899), None),
        ("expired but inside leeway", mint(GOOD), dict(now=NOW + 905, leeway=10), None),
        ("expired outside leeway", mint(GOOD), dict(now=NOW + 911, leeway=10), "exp"),
        ("no exp at all", mint({k: v for k, v in GOOD.items() if k != "exp"}), {}, "exp"),
        ("exp is a string", mint({**GOOD, "exp": "9999999999"}), {}, "exp"),
        ("exp is true", mint({**GOOD, "exp": True}), {}, "exp"),
        ("not yet valid", mint({**GOOD, "nbf": NOW + 500}), {}, "nbf"),
        ("not yet valid, inside leeway", mint({**GOOD, "nbf": NOW + 65}), dict(leeway=10), None),
        ("nbf in the past", mint({**GOOD, "nbf": NOW}), {}, None),
        ("wrong issuer", mint({**GOOD, "iss": "https://evil.example"}), {}, "iss"),
        ("missing issuer", mint({k: v for k, v in GOOD.items() if k != "iss"}), {}, "iss"),
        ("wrong audience", mint({**GOOD, "aud": "billing.example"}), {}, "aud"),
        ("audience list containing ours", mint({**GOOD, "aud": ["other", AUD]}), {}, None),
        ("audience list without ours", mint({**GOOD, "aud": ["other", "another"]}), {}, "aud"),
        ("missing audience", mint({k: v for k, v in GOOD.items() if k != "aud"}), {}, "aud"),
        ("signed with another key", mint(GOOD, b"not the key"), {}, "signature"),
        ("bad signature AND expired", mint({**GOOD, "exp": NOW - 1}, b"not the key"), {}, "signature"),
        ("alg none", mint(GOOD, header={"alg": "none", "typ": "JWT"}).rsplit(".", 1)[0] + ".", {}, "alg"),
        ("alg None", mint(GOOD, header={"alg": "None"}), {}, "alg"),
        ("alg HS512", mint(GOOD, header={"alg": "HS512"}), {}, "alg"),
        ("alg RS256", mint(GOOD, header={"alg": "RS256"}), {}, "alg"),
        ("alg lower-case hs256", mint(GOOD, header={"alg": "hs256"}), {}, "alg"),
        ("no alg", mint(GOOD, header={"typ": "JWT"}), {}, "alg"),
        ("alg is a list", mint(GOOD, header={"alg": ["HS256"]}), {}, "alg"),
        ("crit header", mint(GOOD, header={"alg": "HS256", "crit": ["exp"]}), {}, "alg"),
        ("empty string", "", {}, "malformed"),
        ("two parts", "abc.def", {}, "malformed"),
        ("four parts", mint(GOOD) + ".x", {}, "malformed"),
        ("not base64url", "!!!.???.***", {}, "malformed"),
        ("claims not JSON", f"{b64u(b'{}')}.{b64u(b'nope')}.{b64u(b'x')}", {}, "malformed"),
        ("claims is a list", mint([1, 2, 3]), {}, "malformed"),
        ("not a string", None, {}, "malformed"),
    ]
    for name, tok, over, want in cases:
        got = R(tok, **over)
        if want is None:
            assert got[0] == "accepted", f"{name}: should be accepted, was rejected ({got[1]})"
        else:
            assert got == ("rejected", want), f"{name}: expected rejection '{want}', got {got}"
    with Spy(hmac, "compare_digest") as spy:
        strict(mint(GOOD))
    assert spy.calls >= 1, "compare signatures with hmac.compare_digest"
    # The claims must not even be looked at before the signature has been checked.
    boom = mint({"exp": "x"}, b"wrong")
    assert R(boom) == ("rejected", "signature"), "signature must be verified before any claim is interpreted"
    return f"{len(cases)} cases: header never trusted, signature first, then exp/nbf (with leeway), iss, aud"


# ------------------------------------------------------------------ milestone 3
ADMIN = {**GOOD, "sub": "mallory", "role": "admin"}


def noncanonical(token):
    """Same decoded signature bytes, different text: flip a bit that base64url ignores."""
    h, p, s = token.split(".")
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    v = alphabet.index(s[-1])
    return f"{h}.{p}.{s[:-1]}{alphabet[v ^ 1]}"


def m3():
    legit = mint(GOOD)
    algs_rs = lambda tok: mod.verify(tok, mod.PUBLIC_KEY, algs=("RS256",), **KW)   # a service that expects RS256
    naive = lambda tok, key=KEY: mod.naive_verify(tok, key, NOW + 60)
    assert naive(legit)["sub"] == "alice", "(setup) the naive verifier should accept legitimate tokens"
    assert strict(legit)["sub"] == "alice", "(setup) your verifier must accept legitimate tokens (milestone 2)"
    attacks = [
        ("alg none", mod.forge_alg_none(ADMIN), lambda t: naive(t), strict, "alg"),
        ("alg switch (public key as HMAC secret)", mod.forge_alg_switch(ADMIN, mod.PUBLIC_KEY),
         lambda t: naive(t, mod.PUBLIC_KEY), algs_rs, "alg"),
        ("signature stripped", mod.forge_strip_signature(legit), naive, strict, "signature"),
        ("tampered payload", mod.forge_tamper(legit, role="admin", sub="mallory"), None, strict, "signature"),
        ("expired token", mint({**GOOD, "exp": NOW - 3600}), naive, strict, "exp"),
        ("wrong audience", mint({**GOOD, "aud": "billing.example"}), naive, strict, "aud"),
        ("wrong issuer", mint({**GOOD, "iss": "https://evil.example"}), naive, strict, "iss"),
    ]
    rows = []
    for name, token, vuln, fixed, reason in attacks:
        if vuln is not None:
            kind, res = outcome(lambda: vuln(token))
            assert kind == "accepted", f"{name}: your forged token should be ACCEPTED by the naive verifier, but it was rejected ({res}). Fix the forger."
            if name.startswith("alg"):
                assert res.get("role") == "admin", f"{name}: the forged token should have granted role admin, got {res}"
        else:
            kind, res = outcome(lambda: naive(token))
            assert kind == "rejected", "(control) the naive verifier does check ordinary signatures, so plain tampering must fail even there"
        kind2, res2 = outcome(lambda: fixed(token))
        assert (kind2, res2) == ("rejected", reason), f"{name}: your strict verifier should reject it with reason '{reason}', got {(kind2, res2)}"
        rows.append(f"{name:<40} naive: {'accepted' if vuln is not None else 'rejected':<9} strict: rejected ({reason})")
    sw = mod.forge_alg_switch(ADMIN, mod.PUBLIC_KEY)
    assert outcome(lambda: strict(sw)) == ("rejected", "signature"), "an HS256 verifier holding the real secret must reject a token signed with the public key"
    # variants of the same ideas
    for alg in ("None", "NONE", "nOnE"):
        tok = mint(ADMIN, header={"alg": alg}).rsplit(".", 1)[0] + "."
        assert outcome(lambda: naive(tok))[0] == "accepted", f"(setup) naive should accept alg {alg!r}"
        assert outcome(lambda: strict(tok)) == ("rejected", "alg"), f"alg {alg!r} must be rejected by allow-list"
    h, p, s = legit.split(".")
    variants = [("signature truncated", f"{h}.{p}.{s[:20]}"), ("signature = garbage", f"{h}.{p}.{b64u(b'A' * 32)}"),
                ("signature of another token", f"{h}.{p}.{mint({**GOOD, 'sub': 'bob'}).split('.')[2]}"),
                ("payload swapped, header kept", f"{h}.{mint(ADMIN).split('.')[1]}.{s}"),
                ("two tokens glued", legit + "." + legit)]
    for name, tok in variants:
        kind, res = outcome(lambda: strict(tok))
        assert kind == "rejected", f"variant '{name}' was accepted by your verifier"
    nc = noncanonical(legit)
    assert nc != legit and outcome(lambda: naive(nc))[0] == "accepted", "(setup) naive accepts an equivalent re-encoding"
    assert outcome(lambda: strict(nc)) == ("rejected", "malformed"), "non-canonical base64url must be refused (otherwise two texts name one token)"
    return "\n".join(rows)


# ------------------------------------------------------------------ milestone 4
def m4():
    ring = mod.Keyring()
    ring.add("2026-01", hashlib.sha256(b"one").digest())
    VK = lambda t, **o: mod.verify_with_keyring(t, ring, **{**KW, **o})
    t1 = mod.issue(ring, GOOD)
    assert mod.decode_unverified(t1)[0].get("kid") == "2026-01", "issue() should put the signing kid in the header"
    assert VK(t1)["sub"] == "alice"
    ring.add("2026-07", hashlib.sha256(b"two").digest(), signing=True)
    t2 = mod.issue(ring, GOOD)
    assert mod.decode_unverified(t2)[0]["kid"] == "2026-07"
    assert VK(t1)["sub"] == VK(t2)["sub"] == "alice", "during rotation both keys must verify"
    ring.retire("2026-01")
    assert outcome(lambda: VK(t1)) == ("rejected", "kid"), "a retired key id must be refused"
    assert VK(t2)["sub"] == "alice"
    # key selection must not become key confusion
    k2 = hashlib.sha256(b"two").digest()
    wrong = mint(GOOD, hashlib.sha256(b"one").digest(), {"alg": "HS256", "kid": "2026-07"})
    assert outcome(lambda: VK(wrong)) == ("rejected", "signature"), "kid names the key, but the signature must still match it"
    hostile = ["../../etc/passwd", "k' OR '1'='1", "", "2026-07\x00", ["2026-07"], 7, None, {"a": 1}, "2026-07 "]
    for kid in hostile:
        tok = mint(GOOD, k2, {"alg": "HS256", "kid": kid})
        assert outcome(lambda: VK(tok)) == ("rejected", "kid"), f"hostile kid {kid!r} should be 'unknown key id'"
    nokid = mint(GOOD, k2)
    assert outcome(lambda: VK(nokid)) == ("rejected", "kid"), "a token with no kid is refused by a keyring verifier"
    assert outcome(lambda: VK(mint({**GOOD, "exp": NOW - 5}, k2, {"alg": "HS256", "kid": "2026-07"}))) == ("rejected", "exp")
    assert outcome(lambda: VK(mint(GOOD, k2, {"alg": "none", "kid": "2026-07"}).rsplit(".", 1)[0] + ".")) == ("rejected", "alg")
    # the naive keyring verifier falls back to an EMPTY key for an unknown kid
    forged = mint(ADMIN, b"", {"alg": "HS256", "kid": "does-not-exist"})
    kind, res = outcome(lambda: mod.naive_keyring_verify(forged, ring, NOW + 60))
    assert kind == "accepted" and res["role"] == "admin", "(setup) the naive keyring verifier should fall for the empty-key forgery"
    assert outcome(lambda: VK(forged)) == ("rejected", "kid")
    return "kid selects the key from a dict; unknown, retired, hostile and missing kids refused; the empty-key forgery stopped"


# ------------------------------------------------------------------ milestone 5
def m5():
    clock = mod.SimClock(NOW)
    ring = mod.Keyring()
    ring.add("k1", hashlib.sha256(b"svc").digest())
    svc = mod.TokenService(ring, clock)
    A = lambda t: outcome(lambda: svc.check_access(t))
    R = lambda t: outcome(lambda: svc.refresh(t))
    acc1, r1 = svc.login("alice")
    assert svc.check_access(acc1)["sub"] == "alice"
    # rotation
    acc2, r2 = svc.refresh(r1)
    assert r2 != r1 and acc2 != acc1 and svc.check_access(acc2)["sub"] == "alice", "refresh must hand out a NEW refresh token and a new access token"
    # a stolen copy of r1 is replayed: reuse detection kills the family, including the legitimate holder's r2
    assert R(r1) == ("rejected", "refresh"), "an already-used refresh token must be refused"
    assert R(r2) == ("rejected", "refresh"), "reuse detected: the WHOLE family must be revoked, including the newest token"
    # access tokens are not looked up, so they die by expiry: the exposure window is bounded by the TTL
    clock.advance(svc.access_ttl - 1)
    assert A(acc2)[0] == "accepted", "revocation of the family does not recall access tokens already issued"
    clock.advance(1)
    assert A(acc2) == ("rejected", "exp"), "...but they are short-lived: expired at issue + access_ttl"
    # other users and fresh logins are unaffected
    accb, rb = svc.login("bob")
    acc3, r3 = svc.login("alice")
    assert R(rb)[0] == "accepted" and R(r3)[0] == "accepted", "other families must be unaffected by a revocation"
    assert svc.check_access(acc3)["sid"] != svc.check_access(accb)["sid"], "each login is its own family"
    # unknown tokens
    assert R("not-a-token") == ("rejected", "refresh")
    # a long chain: tokens rotate 50 times; reusing an ANCIENT token still revokes the family
    _, cur = svc.login("carol")
    first = cur
    chain = [cur]
    for _ in range(50):
        _, cur = svc.refresh(cur)
        chain.append(cur)
    assert len(set(chain)) == 51
    assert R(chain[10]) == ("rejected", "refresh") and R(cur) == ("rejected", "refresh"), "an ancient token's reuse must still revoke the family"
    # refresh tokens have a lifetime of their own
    _, rd = svc.login("dave")
    clock.advance(svc.refresh_ttl)
    assert R(rd) == ("rejected", "refresh"), "an expired refresh token is refused"
    # explicit logout
    _, re_ = svc.login("erin")
    svc.logout(re_)
    assert R(re_) == ("rejected", "refresh"), "logout revokes the family"
    svc.logout("nonsense")
    return f"rotation, reuse detection (family revoked), access exposure bounded by {svc.access_ttl}s, expiry and logout"


print(f"Lab 2 checks against {target}.py\n")
check(1, "Milestone 1: encode and decode a JWT-like token", m1)
check(2, "Milestone 2: a strict verifier", m2)
check(3, "Milestone 3: attacks against a naive verifier, then yours", m3)
check(4, "Milestone 4: key rotation with kid", m4)
check(5, "Milestone 5: short-lived access tokens and refresh rotation", m5)
passed = sum(results)
print(f"\n{passed}/{len(results)} milestones passing" + ("  Lab complete!" if passed == len(results) else ""))
sys.exit(0 if passed == len(results) else 1)
