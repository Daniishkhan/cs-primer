"""Lab 1 starter: passwords, MACs and a timing leak (standard library only).

Everything runs in one process. Time is simulated (SimClock) and the "timing leak" is
modelled by a counter, so every run is identical. Educational model, not a benchmark.

Each TODO raises NotImplementedError until you fill it in. Run:  python3 check.py
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
    """Given: scrypt with a 32-byte output."""
    return hashlib.scrypt(password.encode(), salt=salt, n=2 ** ln, r=r, p=p, maxmem=MAXMEM, dklen=32)


def hash_password(password: str, policy: Policy = DEFAULT_POLICY) -> str:
    """Return  $scrypt$ln=<ln>,r=<r>,p=<p>$<salt>$<digest>  with base64url (b64) fields.

    1. A fresh 16-byte random salt from `secrets`, every call.
    2. The digest comes from _scrypt(...).
    3. The parameters are written INTO the string so verification never has to guess them.
    """
    raise NotImplementedError("TODO milestone 1: hash_password")


def parse(stored: str):
    """-> (Policy, salt, digest) decoded from a string made by hash_password.
    Raise ValueError for anything that is not exactly our format."""
    raise NotImplementedError("TODO milestone 1: parse")


def verify_password(password: str, stored: str) -> bool:
    """True only if `password` hashes to the stored digest using the parameters and salt
    found IN the stored string. Compare with hmac.compare_digest. Malformed input -> False."""
    raise NotImplementedError("TODO milestone 1: verify_password")


# ------------------------------------------------------------------ milestone 2
def legacy_hash(password: str) -> str:
    """Given: the old scheme this fictional site used, one unsalted SHA-256."""
    return "$sha256$" + hashlib.sha256(password.encode()).hexdigest()


def verify_legacy(password: str, stored: str) -> bool:
    """True if `stored` is a legacy hash of `password` (constant-time compare). Else False."""
    raise NotImplementedError("TODO milestone 2: verify_legacy")


def needs_rehash(stored: str, policy: Policy) -> bool:
    """True for any legacy hash, any malformed hash, and any scrypt hash that is WEAKER than
    the policy in at least one of ln, r, p. A hash that is already as strong or stronger: False."""
    raise NotImplementedError("TODO milestone 2: needs_rehash")


class PasswordStore:
    def __init__(self, policy: Policy = DEFAULT_POLICY):
        self.policy = policy
        self.users = {}                              # username -> stored hash string
        self._dummy = None

    def register(self, user: str, password: str) -> None:
        self.users[user] = hash_password(password, self.policy)

    def add_legacy(self, user: str, password: str) -> None:
        """Given: simulate a row that was written years ago."""
        self.users[user] = legacy_hash(password)

    def login(self, user: str, password: str) -> bool:
        """Check the password. On SUCCESS, if needs_rehash(stored, self.policy), replace the
        stored value with hash_password(password, self.policy). On failure change nothing.
        An unknown user must cost one scrypt too (verify against a dummy hash) and return False.
        """
        raise NotImplementedError("TODO milestone 2: PasswordStore.login")


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
    """Given. `keys` holds every key that may still VERIFY; `signing_kid` is the one that SIGNS."""
    def __init__(self):
        self.keys = {}
        self.signing_kid = None

    def add(self, kid: str, key: bytes, signing: bool = False) -> None:
        self.keys[kid] = key
        if signing or self.signing_kid is None:
            self.signing_kid = kid

    def retire(self, kid: str) -> None:
        self.keys.pop(kid, None)


def sign(ring: Keyring, payload: bytes) -> str:
    """Return  <kid>.<b64 payload>.<b64 tag>  where tag = HMAC-SHA256(key, "<kid>.<b64 payload>")
    and key is the ring's signing key. Putting the kid inside the MAC input binds the tag to it."""
    raise NotImplementedError("TODO milestone 3: sign")


def open_message(ring: Keyring, token: str) -> bytes:
    """Return the payload bytes, or raise BadSignature. Look the key up BY the kid in the token.
    Unknown or retired kid, wrong number of parts, bad base64, wrong tag: all BadSignature.
    Compare tags with hmac.compare_digest."""
    raise NotImplementedError("TODO milestone 3: open_message")


# ------------------------------------------------------------------ milestone 4
class SimClock:
    def __init__(self, t: float = 1000.0):
        self.t = t

    def now(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


class Sender:
    """Given: wraps a body with a timestamp and a random nonce, then signs it."""
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
        """Return the body, or raise BadSignature, Stale or Replay. In this order:
        1. authenticate (open_message) and decode the JSON envelope;
        2. drop nonces whose expiry has passed;
        3. Stale if |now - ts| > window;
        4. Replay if the nonce is already in self.seen;
        5. only now remember the nonce, until ts + window, and return the body.
        Nothing unauthenticated may ever be written to self.seen."""
        raise NotImplementedError("TODO milestone 4: Receiver.receive")


# ------------------------------------------------------------------ milestone 5
class Meter:
    """Counts byte comparisons. In this model, 'work done' is what an attacker can observe."""
    def __init__(self):
        self.steps = 0


def leaky_equal(a: bytes, b: bytes, meter: Meter) -> bool:
    """The `==` of this model: compare left to right, stop at the first difference, and add
    1 to meter.steps for every byte pair it looks at (a length mismatch costs 1 step)."""
    raise NotImplementedError("TODO milestone 5: leaky_equal")


def constant_equal(a: bytes, b: bytes, meter: Meter) -> bool:
    """The fix: add max(len(a), len(b)) to meter.steps whatever the contents, and decide
    the answer with hmac.compare_digest."""
    raise NotImplementedError("TODO milestone 5: constant_equal")


class MacServer:
    """Given. The deliberately weak target: a 4-byte truncated MAC, checked with a pluggable comparator."""
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
    """The exploit, against our own toy server only. Use nothing but oracle(tag) -> (accepted, work).
    Fix one byte at a time: try all 256 values at this position (pad the rest with zero bytes),
    keep the value that made the server work longest. Return (guess, queries_used); if a query is
    accepted, return that guess straight away."""
    raise NotImplementedError("TODO milestone 5: recover_tag")
