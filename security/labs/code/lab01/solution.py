"""Lab 1 reference solution: passwords, MACs and a timing leak (standard library only).

Everything runs in one process. Time is simulated (SimClock) and the "timing leak" is
modelled by a counter, so every run is identical. Educational model, not a benchmark.
"""
import base64
import hashlib
import hmac
import json
import secrets
from collections import namedtuple


def b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


# ------------------------------------------------------------------ milestone 1
Policy = namedtuple("Policy", "ln r p")          # scrypt cost: N = 2**ln, block size r, parallelism p
DEFAULT_POLICY = Policy(ln=14, r=8, p=1)
MAXMEM = 256 * 1024 * 1024


def _scrypt(password: str, salt: bytes, ln: int, r: int, p: int) -> bytes:
    return hashlib.scrypt(password.encode(), salt=salt, n=2 ** ln, r=r, p=p, maxmem=MAXMEM, dklen=32)


def hash_password(password: str, policy: Policy = DEFAULT_POLICY) -> str:
    salt = secrets.token_bytes(16)
    dk = _scrypt(password, salt, policy.ln, policy.r, policy.p)
    return f"$scrypt$ln={policy.ln},r={policy.r},p={policy.p}${b64(salt)}${b64(dk)}"


def parse(stored: str):
    """-> (Policy, salt, digest). Raises ValueError for anything that is not our format."""
    try:
        empty, alg, params, salt, dk = stored.split("$")
        if empty != "" or alg != "scrypt":
            raise ValueError("not a scrypt hash")
        kv = dict(item.split("=") for item in params.split(","))
        return Policy(int(kv["ln"]), int(kv["r"]), int(kv["p"])), unb64(salt), unb64(dk)
    except (ValueError, KeyError, TypeError) as e:
        raise ValueError(f"malformed hash: {e}") from None


def verify_password(password: str, stored: str) -> bool:
    try:
        policy, salt, expected = parse(stored)
        actual = _scrypt(password, salt, policy.ln, policy.r, policy.p)
    except ValueError:
        return False
    return hmac.compare_digest(actual, expected)


# ------------------------------------------------------------------ milestone 2
def legacy_hash(password: str) -> str:
    """The old scheme this fictional site used to use: one unsalted SHA-256."""
    return "$sha256$" + hashlib.sha256(password.encode()).hexdigest()


def verify_legacy(password: str, stored: str) -> bool:
    if not stored.startswith("$sha256$"):
        return False
    return hmac.compare_digest(legacy_hash(password).encode(), stored.encode())


def needs_rehash(stored: str, policy: Policy) -> bool:
    if stored.startswith("$sha256$"):
        return True
    try:
        have, _, _ = parse(stored)
    except ValueError:
        return True
    return have.ln < policy.ln or have.r < policy.r or have.p < policy.p


class PasswordStore:
    def __init__(self, policy: Policy = DEFAULT_POLICY):
        self.policy = policy
        self.users = {}                              # username -> stored hash string
        self._dummy = hash_password("dummy", policy)  # so unknown users cost one scrypt too

    def register(self, user: str, password: str) -> None:
        self.users[user] = hash_password(password, self.policy)

    def add_legacy(self, user: str, password: str) -> None:
        self.users[user] = legacy_hash(password)      # simulate a row written years ago

    def login(self, user: str, password: str) -> bool:
        stored = self.users.get(user)
        if stored is None:
            verify_password(password, self._dummy)   # same work as a real user; result ignored
            return False
        if stored.startswith("$sha256$"):
            ok = verify_legacy(password, stored)
        else:
            ok = verify_password(password, stored)
        if ok and needs_rehash(stored, self.policy):
            self.users[user] = hash_password(password, self.policy)   # only we know the password now
        return ok


# ------------------------------------------------------------------ milestone 3
class MessageError(Exception):
    pass


class BadSignature(MessageError):
    pass


class Stale(MessageError):
    pass


class Replay(MessageError):
    pass


class Keyring:
    def __init__(self):
        self.keys = {}                # kid -> key bytes, every key that may still VERIFY
        self.signing_kid = None       # the one key used to SIGN new messages

    def add(self, kid: str, key: bytes, signing: bool = False) -> None:
        self.keys[kid] = key
        if signing or self.signing_kid is None:
            self.signing_kid = kid

    def retire(self, kid: str) -> None:
        self.keys.pop(kid, None)


def _tag(key: bytes, kid: str, body_b64: str) -> bytes:
    return hmac.new(key, f"{kid}.{body_b64}".encode(), hashlib.sha256).digest()


def sign(ring: Keyring, payload: bytes) -> str:
    kid = ring.signing_kid
    body = b64(payload)
    return f"{kid}.{body}.{b64(_tag(ring.keys[kid], kid, body))}"


def open_message(ring: Keyring, token: str) -> bytes:
    try:
        kid, body, tag = token.split(".")
        key = ring.keys[kid]
        given = unb64(tag)
        payload = unb64(body)
    except (ValueError, KeyError, TypeError):
        raise BadSignature("malformed token or unknown key id") from None
    if not hmac.compare_digest(_tag(key, kid, body), given):
        raise BadSignature("tag does not match")
    return payload


# ------------------------------------------------------------------ milestone 4
class SimClock:
    def __init__(self, t: float = 1000.0):
        self.t = t

    def now(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


class Sender:
    def __init__(self, ring: Keyring, clock: SimClock):
        self.ring, self.clock = ring, clock

    def send(self, body: dict, nonce: str = None) -> str:
        env = {"ts": self.clock.now(), "nonce": nonce or secrets.token_hex(8), "body": body}
        return sign(self.ring, json.dumps(env, sort_keys=True).encode())


class Receiver:
    def __init__(self, ring: Keyring, clock: SimClock, window: float = 30.0):
        self.ring, self.clock, self.window = ring, clock, window
        self.seen = {}                # nonce -> time after which we may forget it

    def receive(self, token: str) -> dict:
        env = json.loads(open_message(self.ring, token))     # 1. authenticate FIRST
        now = self.clock.now()
        self.seen = {n: exp for n, exp in self.seen.items() if exp >= now}   # 2. forget the expired
        if abs(now - env["ts"]) > self.window:                # 3. freshness
            raise Stale(f"timestamp {env['ts']} is outside +/-{self.window}s of {now}")
        if env["nonce"] in self.seen:                         # 4. uniqueness inside the window
            raise Replay(f"nonce {env['nonce']} already used")
        self.seen[env["nonce"]] = env["ts"] + self.window
        return env["body"]


# ------------------------------------------------------------------ milestone 5
class Meter:
    """Counts byte comparisons. In this model, 'work done' is what an attacker can observe."""
    def __init__(self):
        self.steps = 0


def leaky_equal(a: bytes, b: bytes, meter: Meter) -> bool:
    if len(a) != len(b):
        meter.steps += 1
        return False
    for x, y in zip(a, b):
        meter.steps += 1
        if x != y:
            return False              # early exit: the amount of work reveals where they differ
    return True


def constant_equal(a: bytes, b: bytes, meter: Meter) -> bool:
    meter.steps += max(len(a), len(b))   # model: the work does not depend on the contents
    return hmac.compare_digest(a, b)


class MacServer:
    """The deliberately weak target: a 4-byte truncated MAC, checked with a pluggable comparator."""
    def __init__(self, key: bytes, message: bytes, compare, tag_len: int = 4):
        self._expected = hmac.new(key, message, hashlib.sha256).digest()[:tag_len]
        self.message, self.tag_len, self.compare = message, tag_len, compare
        self.meter = Meter()

    def oracle(self, tag: bytes):
        """What an attacker on the network sees: accept/reject, plus the work the server did."""
        before = self.meter.steps
        ok = self.compare(self._expected, tag, self.meter)
        return ok, self.meter.steps - before


def recover_tag(oracle, tag_len: int):
    """Guess the tag one byte at a time using only oracle(tag) -> (accepted, work).
    Returns (guess, queries_used)."""
    known, queries = b"", 0
    for pos in range(tag_len):
        best, best_work = 0, -1
        for cand in range(256):
            guess = known + bytes([cand]) + bytes(tag_len - pos - 1)
            ok, work = oracle(guess)
            queries += 1
            if ok:
                return guess, queries
            if work > best_work:
                best, best_work = cand, work
        known += bytes([best])
    return known, queries
