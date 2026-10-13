"""Lab 6: Envelope Encryption & Crypto-Shredding.

    ####################################################################
    #  EDUCATIONAL ONLY. NEVER USE THIS CODE TO PROTECT REAL DATA.      #
    #  The cipher below is a TOY: a SHAKE-256 keystream with an HMAC    #
    #  (encrypt-then-MAC), built so the lab runs with the Python        #
    #  standard library alone. It has not been reviewed, is not         #
    #  constant-time end to end, and keeps keys in ordinary memory.     #
    #  Real systems call a vetted AEAD (AES-GCM, ChaCha20-Poly1305)     #
    #  from a maintained library and a real KMS or HSM.                 #
    ####################################################################

You build, in five steps, the structure real systems use to protect tenant data:

  1. A toy AEAD: seal / open_ with a nonce and associated data.
  2. A KMS simulator: master keys (KEKs) with versions; wrap and unwrap data
     keys; an audit log entry for every call.
  3. Per-tenant data keys (DEKs): records are encrypted with the tenant's DEK,
     and the tenant id is bound in as associated data.
  4. KEK rotation: re-wrap the DEKs (not the data), keep old versions
     decryptable, then retire them.
  5. Crypto-shredding: destroy a tenant's key and its records become
     unrecoverable, in backups too, while other tenants are untouched.

Everything runs in one process: no network, no files.

    python3 check.py            # checks this file (the starter)
    python3 check.py solution   # checks the reference answer
"""
import copy
import hashlib
import hmac
import secrets
from contextlib import contextmanager
from dataclasses import dataclass

NONCE_LEN, TAG_LEN, KEY_LEN = 16, 32, 32


# =========================================================================
# Milestone 1: a toy AEAD (EDUCATIONAL ONLY)
# =========================================================================
class AuthError(Exception):
    """The ciphertext failed authentication: wrong key, wrong associated data, or tampering."""


def _subkeys(key):
    """One key in, two independent keys out: never use the same key for encryption and for the MAC."""
    return (hmac.new(key, b"toy-aead/enc", hashlib.sha256).digest(),
            hmac.new(key, b"toy-aead/mac", hashlib.sha256).digest())


def seal(key, plaintext, ad=b"", nonce=None):
    """Encrypt-then-MAC. Returns  nonce || ciphertext || tag  (16 + len(plaintext) + 32 bytes).

    1. enc_key, mac_key = _subkeys(key)
    2. nonce: NONCE_LEN random bytes (secrets.token_bytes) unless the caller passes one.
       (The `nonce=` argument exists only so tests can show what happens when a nonce repeats.)
    3. keystream = hashlib.shake_256(enc_key + nonce).digest(len(plaintext)); ciphertext = plaintext XOR keystream
    4. tag = HMAC-SHA256(mac_key, MAC_INPUT). MAC_INPUT must be UNAMBIGUOUS about where the associated
       data ends and the nonce begins: put len(ad) as 8 big-endian bytes first, then ad, nonce, ciphertext.
    """
    enc_key, mac_key = _subkeys(key)
    if nonce is None:
        nonce = secrets.token_bytes(NONCE_LEN)
    if len(nonce) != NONCE_LEN:
        raise ValueError("nonce must be %d bytes" % NONCE_LEN)
    stream = hashlib.shake_256(enc_key + nonce).digest(len(plaintext))
    ct = bytes(p ^ k for p, k in zip(plaintext, stream))
    tag = hmac.new(mac_key, len(ad).to_bytes(8, "big") + ad + nonce + ct, hashlib.sha256).digest()
    return nonce + ct + tag


def open_(key, blob, ad=b""):
    """Verify, THEN decrypt. Raise AuthError (never IndexError or ValueError) for anything wrong:
    a blob too short to hold a nonce and a tag, a wrong key, wrong associated data, any changed byte.
    Compare tags with hmac.compare_digest. Do not compute the keystream until the tag has been verified."""
    if len(blob) < NONCE_LEN + TAG_LEN:
        raise AuthError("ciphertext too short")
    enc_key, mac_key = _subkeys(key)
    nonce, ct, tag = blob[:NONCE_LEN], blob[NONCE_LEN:-TAG_LEN], blob[-TAG_LEN:]
    expected = hmac.new(mac_key, len(ad).to_bytes(8, "big") + ad + nonce + ct, hashlib.sha256).digest()
    if not hmac.compare_digest(tag, expected):
        raise AuthError("authentication failed")
    stream = hashlib.shake_256(enc_key + nonce).digest(len(ct))
    return bytes(c ^ k for c, k in zip(ct, stream))


# =========================================================================
# Milestone 2: a KMS simulator with versioned master keys
# =========================================================================
class KMSError(Exception):
    """A KMS call was refused (unknown key, disabled or destroyed version, wrong context...)."""


@dataclass(frozen=True)
class Wrapped:
    """A data key encrypted under a master key. Safe to store next to the data it protects."""
    key_id: str
    version: int
    blob: bytes


class KMS:
    """Holds master keys (KEKs). Callers never see KEK bytes: they hand over a data key and get a
    Wrapped back, or hand back a Wrapped and get the data key.

    State (keep the names):
        _keys: key_id -> {"current": int, "versions": {n: {"material": bytes or None,
                                                          "state": "enabled" | "disabled" | "destroyed"}}}
        audit: list of dicts, ONE per public call, even refused ones:
               {"seq","op","key_id","version","context","caller","ok","error"}
    The audit log must never contain key material of any kind.

    Every public method runs its body inside `with self._audited(op, key_id, context, caller) as entry:`.
    That helper appends the entry first, marks it ok when the body finishes, and records the error text
    if the body raises KMSError. Set entry["version"] to the version you used.
    """

    def __init__(self):
        self._keys = {}
        self.audit = []

    @contextmanager
    def _audited(self, op, key_id, context=None, caller="app"):
        entry = {"seq": len(self.audit) + 1, "op": op, "key_id": key_id, "version": None,
                 "context": context, "caller": caller, "ok": False, "error": None}
        self.audit.append(entry)
        try:
            yield entry
            entry["ok"] = True
        except KMSError as e:
            entry["error"] = str(e)
            raise

    def _key(self, key_id):
        k = self._keys.get(key_id)
        if k is None:
            raise KMSError(f"unknown key {key_id!r}")
        return k

    def _material(self, key_id, version):
        """The key bytes of an ENABLED version; KMSError if unknown, disabled or destroyed."""
        v = self._key(key_id)["versions"].get(version)
        if v is None:
            raise KMSError(f"{key_id} has no version {version}")
        if v["state"] != "enabled":
            raise KMSError(f"{key_id} version {version} is {v['state']}")
        return v["material"]

    def versions(self, key_id):
        """{version: state} for display and tests."""
        return {n: v["state"] for n, v in self._key(key_id)["versions"].items()}

    def create_key(self, key_id, caller="app"):
        """Create a master key with version 1 (enabled, current) and 32 fresh random bytes.
        Return the version. An existing key id (even a destroyed one) -> KMSError."""
        with self._audited("create_key", key_id, caller=caller) as e:
            if key_id in self._keys:
                raise KMSError(f"key {key_id!r} already exists")
            self._keys[key_id] = {"current": 1, "versions": {1: {"material": secrets.token_bytes(KEY_LEN), "state": "enabled"}}}
            e["version"] = 1
            return 1

    def wrap(self, key_id, dek, context, caller="app"):
        """Encrypt `dek` under the CURRENT version of the key with seal(), binding `context`
        (a string, e.g. the tenant id) as associated data. Return a Wrapped(key_id, version, blob)."""
        with self._audited("wrap", key_id, context, caller) as e:
            version = self._key(key_id)["current"]
            e["version"] = version
            material = self._material(key_id, version)
            return Wrapped(key_id, version, seal(material, dek, ad=context.encode()))

    def unwrap(self, wrapped, context, caller="app"):
        """Decrypt a Wrapped with the version it names, with the same `context`. A wrong context or a
        changed blob -> KMSError (translate AuthError). A disabled or destroyed version -> KMSError."""
        with self._audited("unwrap", wrapped.key_id, context, caller) as e:
            e["version"] = wrapped.version
            material = self._material(wrapped.key_id, wrapped.version)
            try:
                return open_(material, wrapped.blob, ad=context.encode())
            except AuthError:
                raise KMSError("wrapped key does not match this context, or was altered")

    # ---- milestone 4: rotation and retirement ----
    def rotate(self, key_id, caller="app"):
        """Add a new version (highest number + 1, never reuse a number), make it current, leave
        older versions as they are. Return the new version. A fully destroyed key cannot rotate."""
        with self._audited("rotate", key_id, caller=caller) as e:
            k = self._key(key_id)
            if k["versions"][k["current"]]["state"] == "destroyed":
                raise KMSError(f"{key_id} is destroyed")
            v = max(k["versions"]) + 1
            k["versions"][v] = {"material": secrets.token_bytes(KEY_LEN), "state": "enabled"}
            k["current"] = v
            e["version"] = v
            return v

    def rewrap(self, wrapped, context, caller="app"):
        """Unwrap with the version named in `wrapped` and wrap again under the CURRENT version, all inside
        the KMS: the data key is never returned to the caller. ONE audit entry, op "rewrap", with
        entry["version"] = the new version and entry["from_version"] = the old one."""
        with self._audited("rewrap", wrapped.key_id, context, caller) as e:
            e["from_version"] = wrapped.version
            old = self._material(wrapped.key_id, wrapped.version)
            try:
                dek = open_(old, wrapped.blob, ad=context.encode())
            except AuthError:
                raise KMSError("wrapped key does not match this context, or was altered")
            current = self._key(wrapped.key_id)["current"]
            e["version"] = current
            return Wrapped(wrapped.key_id, current, seal(self._material(wrapped.key_id, current), dek, ad=context.encode()))

    def disable_version(self, key_id, version, caller="app"):
        """enabled -> disabled (reversible). The CURRENT version cannot be disabled (rotate first).
        A destroyed version -> KMSError."""
        with self._audited("disable_version", key_id, caller=caller) as e:
            k = self._key(key_id)
            e["version"] = version
            v = k["versions"].get(version)
            if v is None or v["state"] == "destroyed":
                raise KMSError(f"{key_id} version {version} cannot be disabled")
            if version == k["current"]:
                raise KMSError("cannot disable the current version; rotate first")
            v["state"] = "disabled"

    def enable_version(self, key_id, version, caller="app"):
        """disabled -> enabled: the way back if disabling broke something. A destroyed version -> KMSError."""
        with self._audited("enable_version", key_id, caller=caller) as e:
            e["version"] = version
            v = self._key(key_id)["versions"].get(version)
            if v is None or v["state"] == "destroyed":
                raise KMSError(f"{key_id} version {version} cannot be enabled")
            v["state"] = "enabled"

    def destroy_version(self, key_id, version, caller="app"):
        """disabled -> destroyed (irreversible: erase the key bytes, set material to None). Only a DISABLED
        version may be destroyed: disable first, watch for callers that still need it, then destroy."""
        with self._audited("destroy_version", key_id, caller=caller) as e:
            e["version"] = version
            v = self._key(key_id)["versions"].get(version)
            if v is None or v["state"] != "disabled":
                raise KMSError(f"{key_id} version {version} must be disabled before it can be destroyed")
            v["material"], v["state"] = None, "destroyed"

    # ---- milestone 5: shredding ----
    def destroy_key(self, key_id, caller="app"):
        """Destroy EVERY version of the key at once (irreversible). The key id stays in the registry as a
        tombstone, so it can never be created again by accident. One audit entry, op "destroy_key"."""
        with self._audited("destroy_key", key_id, caller=caller):
            for v in self._key(key_id)["versions"].values():
                v["material"], v["state"] = None, "destroyed"


# =========================================================================
# Milestone 3: per-tenant data keys
# =========================================================================
def record_ad(tenant, record_id):
    """The associated data for one record: tenant id AND record id, length-prefixed so that
    ("ab", "c") and ("a", "bc") can never produce the same bytes."""
    t, r = tenant.encode(), record_id.encode()
    return len(t).to_bytes(2, "big") + t + len(r).to_bytes(2, "big") + r


class TenantStore:
    """Per-tenant envelope encryption over a KMS.

        tenants: tenant -> Wrapped      the tenant's data key (DEK), wrapped by that tenant's master key
        records: (tenant, record_id) -> sealed blob     "the database"

    Each tenant has its own master key in the KMS, named by key_id(tenant). The DEK is wrapped with
    context=tenant. Records are sealed with the DEK and ad=record_ad(tenant, record_id).
    """

    def __init__(self, kms, dek_source=None):
        self.kms = kms
        self.dek_source = dek_source or (lambda: secrets.token_bytes(KEY_LEN))
        self.tenants = {}
        self.records = {}

    @staticmethod
    def key_id(tenant):
        return f"tenant/{tenant}"

    def _dek(self, tenant):
        wrapped = self.tenants.get(tenant)
        if wrapped is None:
            raise KeyError(f"unknown tenant {tenant!r}")
        return self.kms.unwrap(wrapped, context=tenant)

    def create_tenant(self, tenant):
        """Create the tenant's master key, make a DEK with self.dek_source(), wrap it once, store the
        Wrapped in self.tenants. An existing tenant -> ValueError."""
        if tenant in self.tenants:
            raise ValueError(f"tenant {tenant!r} exists")
        self.kms.create_key(self.key_id(tenant))
        self.tenants[tenant] = self.kms.wrap(self.key_id(tenant), self.dek_source(), context=tenant)

    def put(self, tenant, record_id, plaintext):
        """Unwrap the tenant's DEK (self._dek), seal the plaintext with ad=record_ad(...), store the blob."""
        self.records[(tenant, record_id)] = seal(self._dek(tenant), plaintext, ad=record_ad(tenant, record_id))

    def get(self, tenant, record_id):
        """Unwrap the DEK and open the record with the same associated data. Missing record -> KeyError;
        a record that fails authentication -> AuthError."""
        blob = self.records[(tenant, record_id)]
        return open_(self._dek(tenant), blob, ad=record_ad(tenant, record_id))

    # ---- milestone 4 ----
    def rotate_kek(self, tenant):
        """Rotate the tenant's master key and re-wrap the tenant's DEK under the new version. The records
        are NOT touched. Return the new key version."""
        version = self.kms.rotate(self.key_id(tenant))
        self.tenants[tenant] = self.kms.rewrap(self.tenants[tenant], context=tenant)
        return version

    # ---- milestone 5 ----
    def snapshot(self):
        """A backup: an independent copy of the database (records and wrapped keys). The KMS is NOT part of it."""
        return {"records": copy.deepcopy(self.records), "tenants": copy.deepcopy(self.tenants)}

    def restore(self, snap):
        """Replace the live database by a copy of a backup."""
        self.records = copy.deepcopy(snap["records"])
        self.tenants = copy.deepcopy(snap["tenants"])

    def shred_tenant(self, tenant):
        """Crypto-shred: destroy the tenant's master key in the KMS (every version), then remove the
        tenant's wrapped DEK from the live table. Do NOT touch the ciphertext records: wherever copies of
        them live (replicas, backups, exports), they are now noise. Unknown tenant -> KeyError."""
        if tenant not in self.tenants:
            raise KeyError(f"unknown tenant {tenant!r}")
        self.kms.destroy_key(self.key_id(tenant))
        del self.tenants[tenant]
