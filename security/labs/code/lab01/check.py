"""Self-check for Lab 1: Passwords, MACs & Timing.

    python3 check.py                  # checks your starter.py
    python3 check.py solution         # checks the reference solution
    python3 check.py solution 3       # only milestone 3

Everything is deterministic. Time is simulated, and the "timing leak" in milestone 5 is a
counter of byte comparisons, not a stopwatch. Nothing touches a network. Prints a tick, a
cross, or "not implemented yet" for each milestone. Runs in a few seconds.
"""
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

FAST = mod.Policy(ln=10, r=8, p=1)      # cheap scrypt so the checks are quick
MEDIUM = mod.Policy(ln=11, r=8, p=1)


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
    """Count calls to a function while a block runs (used to prove compare_digest / scrypt are used)."""
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


def raises(exc, fn, *a):
    try:
        fn(*a)
    except exc:
        return True
    except Exception as e:
        raise AssertionError(f"expected {exc.__name__}, got {type(e).__name__}: {e}")
    return False


# ------------------------------------------------------------------ milestone 1
def m1():
    h1 = mod.hash_password("correct horse", FAST)
    h2 = mod.hash_password("correct horse", FAST)
    assert h1.startswith("$scrypt$ln=10,r=8,p=1$"), f"format should start with $scrypt$ln=10,r=8,p=1$, got {h1[:30]!r}"
    assert h1 != h2, "same password hashed twice gave the same string: the salt is not random per call"
    pol, salt, dk = mod.parse(h1)
    assert tuple(pol) == (10, 8, 1), f"parse() returned parameters {tuple(pol)}"
    assert len(salt) >= 16 and len(dk) == 32, f"salt {len(salt)} bytes, digest {len(dk)} bytes"
    with Spy(hmac, "compare_digest") as spy:
        assert mod.verify_password("correct horse", h1) is True, "the right password was refused"
    assert spy.calls >= 1, "verify_password must compare digests with hmac.compare_digest"
    assert mod.verify_password("correct horsf", h1) is False, "a wrong password was accepted"
    assert mod.verify_password("", h1) is False, "the empty password was accepted"
    # Parameters come from the string, not from defaults: a hash made at ln=11 verifies after the policy changes.
    h3 = mod.hash_password("pässwörd \U0001f511", MEDIUM)
    assert mod.verify_password("pässwörd \U0001f511", h3), "verification must read ln/r/p from the stored string"
    # Tampering with any field must fail, never crash.
    pre, alg, params, salt_s, dk_s = h1.split("$")
    flipped = dk_s[:-2] + ("AA" if dk_s[-2:] != "AA" else "BB")
    bad = ["", "garbage", "$scrypt$", "$scrypt$ln=10,r=8,p=1$$", "$md5$ln=10$aa$bb", f"$scrypt$ln=x,r=8,p=1${salt_s}${dk_s}",
           f"$scrypt$ln=10,r=8,p=1${salt_s}${flipped}", f"$scrypt$ln=11,r=8,p=1${salt_s}${dk_s}"]
    for b in bad:
        assert mod.verify_password("correct horse", b) is False, f"malformed or altered hash {b[:40]!r} should simply fail"
    assert raises(ValueError, mod.parse, "garbage"), "parse() should raise ValueError on malformed input"
    return "format, per-call salt, parameters read back from the string, compare_digest, tamper-resistance"


# ------------------------------------------------------------------ milestone 2
def m2():
    store = mod.PasswordStore(MEDIUM)
    store.add_legacy("alice", "hunter2")
    legacy_before = store.users["alice"]
    assert not store.login("alice", "wrong"), "wrong password accepted"
    assert store.users["alice"] == legacy_before, "a FAILED login must not change the stored hash"
    assert store.login("alice", "hunter2"), "legacy hash: the right password must still log in"
    up = store.users["alice"]
    assert up.startswith("$scrypt$ln=11,r=8,p=1$"), f"after a successful legacy login the row should be scrypt at policy cost, got {up[:30]!r}"
    assert "sha256" not in up
    assert store.login("alice", "hunter2"), "login must still work after the upgrade"
    assert store.users["alice"] == up, "an already-current hash must not be rewritten on every login"
    # Parameter upgrade works the same way.
    old = mod.hash_password("swordfish", FAST)           # weaker than policy (ln=10 < 11)
    store.users["dave"] = old
    assert store.login("dave", "swordfish")
    assert store.users["dave"].startswith("$scrypt$ln=11,"), "a weaker scrypt hash should be rehashed to the policy"
    assert store.users["dave"] != old
    store.register("carol", "tr0ub4dor")
    assert store.users["carol"].startswith("$scrypt$ln=11,"), "register() should hash at the policy cost"
    # Raising the policy later upgrades everyone, one login at a time.
    store.policy = mod.Policy(12, 8, 1)
    assert store.login("carol", "tr0ub4dor")
    assert store.users["carol"].startswith("$scrypt$ln=12,"), "policy raise should upgrade carol on next login"
    # A hash that is already stronger than policy is never downgraded.
    store.policy = FAST
    strong = store.users["carol"]
    assert store.login("carol", "tr0ub4dor") and store.users["carol"] == strong, "do not downgrade stronger hashes"
    # Unknown users cost one scrypt, like real ones (a cheap way to avoid an obvious account-existence oracle).
    with Spy(hashlib, "scrypt") as spy:
        assert not store.login("nobody", "whatever")
    assert spy.calls == 1, f"an unknown user should cost exactly one scrypt call, saw {spy.calls}"
    assert not store.login("nobody", "")
    # Rehash helper on its own.
    assert mod.needs_rehash(mod.legacy_hash("x"), FAST) and mod.needs_rehash("junk", FAST)
    assert not mod.needs_rehash(mod.hash_password("x", FAST), FAST)
    assert mod.needs_rehash(mod.hash_password("x", mod.Policy(10, 8, 1)), mod.Policy(10, 16, 1)), "weaker r counts as weaker"
    assert not mod.verify_legacy("x", mod.hash_password("x", FAST)) and mod.verify_legacy("x", mod.legacy_hash("x"))
    return "legacy -> scrypt on login, parameter upgrades, no rewrite when current, no change on failure"


# ------------------------------------------------------------------ milestone 3
def ring_with(*pairs):
    ring = mod.Keyring()
    for kid, key, *sig in pairs:
        ring.add(kid, key, signing=bool(sig and sig[0]))
    return ring


def m3():
    k1, k2 = hashlib.sha256(b"key one").digest(), hashlib.sha256(b"key two").digest()
    ring = ring_with(("2026-01", k1, True))
    t1 = mod.sign(ring, b'{"amount":100}')
    assert t1.split(".")[0] == "2026-01" and len(t1.split(".")) == 3, f"token should be kid.payload.tag, got {t1!r}"
    with Spy(hmac, "compare_digest") as spy:
        assert mod.open_message(ring, t1) == b'{"amount":100}'
    assert spy.calls >= 1, "open_message must use hmac.compare_digest"
    kid, body, tag = t1.split(".")
    other = mod.b64(b'{"amount":900}')
    for bad, why in [(f"{kid}.{other}.{tag}", "tampered payload"), (f"{kid}.{body}.{mod.b64(b'x' * 32)}", "wrong tag"),
                     (f"nokey.{body}.{tag}", "unknown kid"), (f"{kid}.{body}", "missing part"), (f"{kid}.{body}.{tag}.x", "extra part"),
                     ("", "empty"), (f"{kid}.!!!.{tag}", "bad base64")]:
        assert raises(mod.BadSignature, mod.open_message, ring, bad), f"{why} should raise BadSignature"
    # Rotation: add k2 as the new signing key; old messages still verify, new ones use k2.
    ring.add("2026-07", k2, signing=True)
    t2 = mod.sign(ring, b"new")
    assert t2.startswith("2026-07."), "after rotation, new messages must be signed with the new key"
    assert mod.open_message(ring, t1) == b'{"amount":100}', "during the overlap the old key must still verify"
    assert mod.open_message(ring, t2) == b"new"
    # The kid is part of what is authenticated: relabelling a token with another key's id must fail.
    k, b, t = t2.split(".")
    assert raises(mod.BadSignature, mod.open_message, ring, f"2026-01.{b}.{t}"), "a token relabelled with another kid must not verify"
    # Retire the old key: its messages stop verifying, the new ones do not.
    ring.retire("2026-01")
    assert raises(mod.BadSignature, mod.open_message, ring, t1), "a retired key must no longer verify"
    assert mod.open_message(ring, t2) == b"new"
    # Two independent rings with different keys never accept each other's tokens.
    other_ring = ring_with(("2026-07", hashlib.sha256(b"someone else").digest(), True))
    assert raises(mod.BadSignature, mod.open_message, other_ring, t2), "same kid, different key: must fail"
    return "kid.payload.tag, rotation overlap, retirement, relabelling and tampering all rejected"


# ------------------------------------------------------------------ milestone 4
def m4():
    key = hashlib.sha256(b"channel key").digest()
    ring = ring_with(("k1", key, True))
    clock = mod.SimClock(1000.0)
    tx = mod.Sender(ring, clock)
    rx = mod.Receiver(ring, clock, window=30.0)
    tok = tx.send({"pay": 5}, nonce="n-1")
    assert rx.receive(tok) == {"pay": 5}, "a fresh message must be accepted"
    assert raises(mod.Replay, rx.receive, tok), "the same token a second time must raise Replay"
    clock.advance(29)
    assert raises(mod.Replay, rx.receive, tok), "still inside the window: the nonce must still be remembered"
    clock.advance(1)                                   # exactly ts + window
    assert raises(mod.Replay, rx.receive, tok), "at exactly ts + window the timestamp is still acceptable, so it is a Replay"
    clock.advance(1)                                   # one second past the window
    assert raises(mod.Stale, rx.receive, tok), "after the window the timestamp check refuses it (Stale)"
    assert len(rx.seen) == 0, f"expired nonces must be forgotten, cache still holds {len(rx.seen)}"
    # A message from the future beyond the window, and a very old one.
    far = mod.Sender(ring, mod.SimClock(clock.now() + 100)).send({"x": 1})
    assert raises(mod.Stale, rx.receive, far), "timestamps too far in the future are refused"
    # Unauthenticated junk must not be able to fill the cache.
    before = len(rx.seen)
    kid, body, tag = tok.split(".")
    for i in range(50):
        evil = json.dumps({"ts": clock.now(), "nonce": f"spam-{i}", "body": {}}, sort_keys=True).encode()
        assert raises(mod.BadSignature, rx.receive, f"k1.{mod.b64(evil)}.{tag}")
    assert len(rx.seen) == before, "nonces from messages with bad signatures were stored: authenticate before touching the cache"
    # Bounded memory: 1000 messages spread over time, cache stays about window-sized.
    peak = 0
    for i in range(1000):
        clock.advance(1)
        rx.receive(tx.send({"i": i}))
        peak = max(peak, len(rx.seen))
    assert peak <= 32, f"cache grew to {peak} entries for 1 message/second with a 30 s window"
    # Replayed after the key was rotated out: authentication fails first.
    old = tx.send({"v": 1})
    ring.add("k2", hashlib.sha256(b"k2").digest(), signing=True)
    ring.retire("k1")
    assert raises(mod.BadSignature, rx.receive, old)
    return f"replay inside the window caught, stale outside it, cache peaked at {peak} entries over 1000 messages"


# ------------------------------------------------------------------ milestone 5
def m5():
    key, msg = hashlib.sha256(b"server secret").digest(), b"transfer 100 to alice"
    # (a) the leaky comparator behaves like ==, and leaks the length of the matching prefix
    m = mod.Meter()
    assert mod.leaky_equal(b"abcd", b"abcd", m) is True and m.steps == 4
    for guess, steps in [(b"abcX", 4), (b"aXcd", 2), (b"Xbcd", 1)]:
        m = mod.Meter()
        assert mod.leaky_equal(b"abcd", guess, m) is False
        assert m.steps == steps, f"leaky_equal(b'abcd', {guess!r}) should add {steps} steps, added {m.steps}"
    # (b) the exploit works against the vulnerable server
    server = mod.MacServer(key, msg, mod.leaky_equal)
    guess, queries = mod.recover_tag(server.oracle, server.tag_len)
    real = hmac.new(key, msg, hashlib.sha256).digest()[:4]
    assert guess == real, f"recovery against the leaky comparator failed: got {guess.hex()}, tag is {real.hex()}"
    assert queries <= 4 * 256, f"used {queries} queries; the leak should need at most 4 x 256 = 1024"
    server2 = mod.MacServer(hashlib.sha256(b"another secret").digest(), msg, mod.leaky_equal)
    g2, _ = mod.recover_tag(server2.oracle, 4)
    assert server2.oracle(g2)[0], "the recovered tag for a second key should be accepted"
    # (c) the constant-work comparator
    m = mod.Meter()
    assert mod.constant_equal(b"abcd", b"abcd", m) and m.steps == 4
    works = set()
    for guess in [b"Xbcd", b"aXcd", b"abXd", b"abcX", b"ab"]:
        m = mod.Meter()
        assert mod.constant_equal(b"abcd", guess, m) is False
        works.add(m.steps)
    assert len(works) <= 2 and works <= {4}, f"work must not depend on where the difference is (saw {sorted(works)})"
    # (d) the same exploit now fails, for several keys
    with Spy(hmac, "compare_digest") as spy:
        for i in range(5):
            k = hashlib.sha256(b"defended %d" % i).digest()
            safe = mod.MacServer(k, msg, mod.constant_equal)
            g, q = mod.recover_tag(safe.oracle, 4)
            real = hmac.new(k, msg, hashlib.sha256).digest()[:4]
            assert g != real, "the exploit still recovers the tag from the constant-work comparator"
            assert not safe.oracle(g)[0]
            assert q == 4 * 256, "with no accept and no leak the attacker just exhausts 1024 queries"
    assert spy.calls >= 1, "constant_equal must decide with hmac.compare_digest"
    return f"leak: tag recovered in {queries} queries (brute force: about 2^31 on average); with compare_digest: recovery fails"


print(f"Lab 1 checks against {target}.py\n")
check(1, "Milestone 1: a salted scrypt password store", m1)
check(2, "Milestone 2: transparent hash upgrade on login", m2)
check(3, "Milestone 3: HMAC-signed messages with key ids", m3)
check(4, "Milestone 4: replay protection (timestamp window + nonce cache)", m4)
check(5, "Milestone 5: a simulated timing leak, exploited and closed", m5)
passed = sum(results)
print(f"\n{passed}/{len(results)} milestones passing" + ("  Lab complete!" if passed == len(results) else ""))
sys.exit(0 if passed == len(results) else 1)
