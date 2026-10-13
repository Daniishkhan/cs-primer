"""Self-check for Lab 6: Envelope Encryption & Crypto-Shredding.

    python3 check.py                  # checks your starter.py
    python3 check.py solution         # checks the reference solution
    python3 check.py solution 4       # only milestone 4

EDUCATIONAL ONLY: the cipher under test is a toy. Everything is in one process:
no network, no files. Random keys and nonces are used, but every assertion is
independent of their values, so each run gives the same verdict. Prints a tick,
a cross, or "not implemented yet" for each milestone. Finishes in well under a second.
"""
import hashlib
import hmac
import importlib
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


def raises(exc, fn, *a, **k):
    try:
        fn(*a, **k)
    except exc:
        return True
    except Exception as e:
        raise AssertionError(f"expected {exc.__name__}, got {type(e).__name__}: {e}")
    return False


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


KEY = bytes(range(32))


# ------------------------------------------------------------------ milestone 1
def m1():
    for pt in (b"", b"x", b"hello, envelope", bytes(range(256)) * 4):
        blob = mod.seal(KEY, pt, b"ad")
        assert len(blob) == 16 + len(pt) + 32, f"layout is nonce(16) || ciphertext || tag(32); {len(pt)} bytes sealed to {len(blob)} bytes"
        assert mod.open_(KEY, blob, b"ad") == pt, f"round trip failed for {len(pt)} bytes"
    assert mod.open_(KEY, mod.seal(KEY, b"no ad given")) == b"no ad given", "associated data is optional (defaults to empty)"
    pt = b"the same message"
    a, b = mod.seal(KEY, pt), mod.seal(KEY, pt)
    assert a != b and a[:16] != b[:16], "two seals of the same message must use different random nonces"
    n = bytes(range(16))
    assert mod.seal(KEY, pt, nonce=n) == mod.seal(KEY, pt, nonce=n), "with an explicit nonce the output is deterministic"
    assert mod.seal(KEY, pt, nonce=n)[:16] == n, "the nonce is the first 16 bytes of the blob"
    zeros = mod.seal(KEY, bytes(1000))[16:-32]
    assert zeros != bytes(1000) and len(set(zeros)) > 150, "the ciphertext of 1000 zero bytes should look random (a real keystream)"
    # nonce reuse: the two-time pad. This is what a stream cipher IS, and why the nonce must never repeat.
    p1, p2 = b"attack at dawn!!", b"retreat at dusk!"
    c1, c2 = mod.seal(KEY, p1, nonce=n)[16:-32], mod.seal(KEY, p2, nonce=n)[16:-32]
    assert bytes(x ^ y for x, y in zip(c1, c2)) == bytes(x ^ y for x, y in zip(p1, p2)), \
        "with the SAME key and nonce, c1 XOR c2 must equal p1 XOR p2 (it is a keystream XOR); check that you XOR a keystream"
    # tamper detection: flip one bit in every position
    msg = b"pay alice 10 dollars"
    blob = mod.seal(KEY, msg, b"invoice:7")
    for i in range(len(blob)):
        bad = bytearray(blob)
        bad[i] ^= 1
        assert raises(mod.AuthError, mod.open_, KEY, bytes(bad), b"invoice:7"), f"flipping a bit in byte {i} of {len(blob)} was NOT detected"
    for cut in range(len(blob)):
        assert raises(mod.AuthError, mod.open_, KEY, blob[:cut], b"invoice:7"), f"a blob truncated to {cut} bytes must raise AuthError (not IndexError)"
    assert raises(mod.AuthError, mod.open_, KEY, blob + b"\x00", b"invoice:7"), "an appended byte must be detected"
    # wrong key, wrong associated data
    assert raises(mod.AuthError, mod.open_, bytes(32), blob, b"invoice:7"), "a wrong key must raise AuthError"
    for wrong in (b"invoice:8", b"", b"invoice:7 ", b"Invoice:7"):
        assert raises(mod.AuthError, mod.open_, KEY, blob, wrong), f"associated data {wrong!r} != b'invoice:7' must be rejected"
    assert raises(mod.AuthError, mod.open_, KEY, mod.seal(KEY, msg), b"anything"), "sealed without ad, opened with ad: rejected"
    # the ad/nonce boundary must be unambiguous
    sealed = mod.seal(KEY, msg, b"ab")
    shifted = sealed[1:]
    assert raises(mod.AuthError, mod.open_, KEY, shifted, b"ab" + sealed[:1]), \
        "ambiguous MAC input: moving one byte from the nonce into the associated data still verifies. Put len(ad) (8 bytes, big-endian) in front of the associated data inside the MAC."
    # verify before decrypt, constant-time compare
    bad = bytearray(blob)
    bad[20] ^= 1
    with Spy(hashlib, "shake_256") as spy:
        raises(mod.AuthError, mod.open_, KEY, bytes(bad), b"invoice:7")
    assert spy.calls == 0, "open_ computed the keystream before the tag was verified: verify first, then decrypt"
    with Spy(hmac, "compare_digest") as spy2:
        mod.open_(KEY, blob, b"invoice:7")
    assert spy2.calls >= 1, "compare tags with hmac.compare_digest, not =="
    return f"round trips, {len(blob)} single-bit flips and {len(blob)} truncations all caught, wrong key and wrong ad rejected, nonce reuse leaks p1 XOR p2 (as it should)"


# ------------------------------------------------------------------ milestone 2
def audit_text(kms):
    return repr(kms.audit)


def m2():
    kms = mod.KMS()
    dek = bytes([7]) * 32
    assert kms.create_key("kek-a") == 1, "create_key returns the new key's version (1)"
    w = kms.wrap("kek-a", dek, context="acme")
    assert isinstance(w, mod.Wrapped) and (w.key_id, w.version) == ("kek-a", 1), f"wrap returned {w!r}"
    assert dek not in w.blob and len(w.blob) == 16 + 32 + 32, "the wrapped key is a sealed blob, not the DEK"
    assert kms.unwrap(w, context="acme") == dek, "unwrap must return the original data key"
    assert kms.wrap("kek-a", dek, context="acme").blob != w.blob, "each wrap uses a fresh nonce"
    kms.create_key("kek-b")
    # refusals
    assert raises(mod.KMSError, kms.unwrap, w, "globex"), "unwrapping with a different context must raise KMSError"
    assert raises(mod.KMSError, kms.unwrap, mod.Wrapped("kek-a", 1, w.blob[:-1] + bytes([w.blob[-1] ^ 1])), "acme"), "a damaged blob must raise KMSError"
    assert raises(mod.KMSError, kms.unwrap, mod.Wrapped("kek-b", 1, w.blob), "acme"), "a blob wrapped by kek-a must not open under kek-b"
    assert raises(mod.KMSError, kms.unwrap, mod.Wrapped("kek-a", 2, w.blob), "acme"), "an unknown version must raise KMSError"
    assert raises(mod.KMSError, kms.wrap, "nope", dek, "acme"), "wrapping under an unknown key must raise KMSError"
    assert raises(mod.KMSError, kms.unwrap, mod.Wrapped("nope", 1, w.blob), "acme"), "unwrapping under an unknown key must raise KMSError"
    assert raises(mod.KMSError, kms.create_key, "kek-a"), "creating a key twice must raise KMSError"
    # the audit log: one entry per call, refused calls included, in order
    ops = [(e["op"], e["key_id"], e["ok"]) for e in kms.audit]
    expect = [("create_key", "kek-a", True), ("wrap", "kek-a", True), ("unwrap", "kek-a", True), ("wrap", "kek-a", True),
              ("create_key", "kek-b", True), ("unwrap", "kek-a", False), ("unwrap", "kek-a", False), ("unwrap", "kek-b", False),
              ("unwrap", "kek-a", False), ("wrap", "nope", False), ("unwrap", "nope", False), ("create_key", "kek-a", False)]
    assert ops == expect, "audit log should hold exactly one entry per call, in order, with ok=False for refused calls.\n        expected: " + str(expect) + "\n        got:      " + str(ops)
    assert [e["seq"] for e in kms.audit] == list(range(1, len(expect) + 1)), "audit entries carry seq = 1, 2, 3, ..."
    assert kms.audit[1]["version"] == 1 and kms.audit[1]["context"] == "acme", f"a wrap entry records the version used and the context: {kms.audit[1]}"
    assert kms.audit[5]["error"], "a refused call records why"
    assert all({"seq", "op", "key_id", "version", "context", "caller", "ok", "error"} <= set(e) for e in kms.audit), "entry fields: seq, op, key_id, version, context, caller, ok, error"
    kms.wrap("kek-a", dek, "acme", caller="billing-service")
    assert kms.audit[-1]["caller"] == "billing-service", "the caller's name is recorded"
    # no key material in the log, ever
    text = audit_text(kms)
    material = [v["material"] for k in kms._keys.values() for v in k["versions"].values()]
    assert all(m.hex() not in text and repr(m) not in text for m in material), "a KEK appeared in the audit log"
    assert dek.hex() not in text and repr(dek) not in text, "a data key appeared in the audit log"
    assert w.blob.hex() not in text, "wrapped blobs do not belong in the audit log either"
    return f"wrap/unwrap round trip, 7 kinds of refusal, {len(kms.audit)} audit entries (one per call, refusals included), no key bytes in the log"


# ------------------------------------------------------------------ milestone 3
def store_with(tenants=("acme", "globex", "initech"), n=10, **kw):
    kms = mod.KMS()
    store = mod.TenantStore(kms, **kw)
    for t in tenants:
        store.create_tenant(t)
    for t in tenants:
        for i in range(n):
            store.put(t, f"r{i}", f"{t} record {i}: confidential".encode())
    return kms, store


def m3():
    kms, store = store_with()
    for t in ("acme", "globex", "initech"):
        for i in range(10):
            assert store.get(t, f"r{i}") == f"{t} record {i}: confidential".encode(), f"round trip failed for {t}/r{i}"
    creates = [e for e in kms.audit if e["op"] == "create_key"]
    wraps = [e for e in kms.audit if e["op"] == "wrap"]
    assert len(creates) == 3 and len(wraps) == 3, f"one master key and ONE wrap per tenant at creation (the DEK is wrapped once, not per record); saw {len(creates)} create_key and {len(wraps)} wrap"
    assert sorted(e["key_id"] for e in creates) == ["tenant/acme", "tenant/globex", "tenant/initech"], "each tenant has its own master key, named tenant/<id>"
    assert all(e["context"] == e["key_id"].split("/")[1] for e in wraps), "wrap each DEK with context = the tenant id"
    assert all(b"confidential" not in blob for blob in store.records.values()), "records must be stored encrypted"
    store.put("acme", "dup1", b"same text")
    store.put("acme", "dup2", b"same text")
    assert store.records[("acme", "dup1")] != store.records[("acme", "dup2")], "the same plaintext in two records must give different ciphertexts"
    assert raises(ValueError, store.create_tenant, "acme"), "creating a tenant twice must raise ValueError"
    assert raises(KeyError, store.put, "nobody", "r", b"x"), "putting into an unknown tenant must raise KeyError"
    assert raises(KeyError, store.get, "acme", "missing"), "getting a missing record must raise KeyError"
    # damaged ciphertext
    blob = store.records[("acme", "r0")]
    store.records[("acme", "r0")] = blob[:20] + bytes([blob[20] ^ 1]) + blob[21:]
    assert raises(mod.AuthError, store.get, "acme", "r0"), "a changed ciphertext must raise AuthError"
    store.records[("acme", "r0")] = blob
    # --- swapping ciphertexts between tenants fails (different DEKs)
    store.records[("globex", "r0")] = store.records[("acme", "r0")]
    assert raises(mod.AuthError, store.get, "globex", "r0"), "acme's record copied into globex must not decrypt for globex"
    # --- swapping wrapped DEKs fails (the KMS binds the tenant as context)
    kms2, s2 = store_with(("acme", "globex"), n=2)
    s2.tenants["globex"] = s2.tenants["acme"]
    assert raises(mod.KMSError, s2.get, "globex", "r0"), "globex pointed at acme's wrapped DEK: the KMS must refuse (context mismatch / other key)"
    # --- the tenant id as associated data, proven by giving two tenants the SAME DEK on purpose
    shared = bytes([9]) * 32
    kms3 = mod.KMS()
    s3 = mod.TenantStore(kms3, dek_source=lambda: shared)
    for t in ("acme", "globex"):
        s3.create_tenant(t)
        s3.put(t, "r1", f"{t} secret".encode())
        s3.put(t, "r2", f"{t} other".encode())
    assert s3.get("acme", "r1") == b"acme secret"
    s3.records[("globex", "r1")] = s3.records[("acme", "r1")]
    assert raises(mod.AuthError, s3.get, "globex", "r1"), \
        "even with a shared DEK, a record moved to another tenant must fail: bind the tenant id as associated data (ad=record_ad(tenant, record_id))"
    s3.records[("acme", "r2")] = s3.records[("acme", "r1")]
    assert raises(mod.AuthError, s3.get, "acme", "r2"), "a record moved to another record id in the same tenant must fail too (record_ad binds the record id)"
    text = audit_text(kms3)
    assert shared.hex() not in text and repr(shared) not in text, "the plaintext DEK must not reach the audit log"
    return "round trips for 3 tenants x 10 records, 1 key + 1 wrap per tenant, cross-tenant swaps fail (separate keys AND tenant-bound ad), wrapped-DEK swap refused"


# ------------------------------------------------------------------ milestone 4
def m4():
    kms, store = store_with(("acme", "globex", "initech"), n=5)
    backup_before = store.snapshot()                                 # taken while everything is wrapped under version 1
    data_before = dict(store.records)
    keyid = store.key_id("acme")
    assert kms.versions(keyid) == {1: "enabled"}
    # --- rotate and rewrap
    old_wrapped = store.tenants["acme"]
    dek_old = kms.unwrap(old_wrapped, "acme")
    v = store.rotate_kek("acme")
    assert v == 2 and kms.versions(keyid) == {1: "enabled", 2: "enabled"}, f"rotate_kek should create version 2 and keep version 1 enabled; versions: {kms.versions(keyid)}"
    new_wrapped = store.tenants["acme"]
    assert (new_wrapped.version, new_wrapped.key_id) == (2, keyid), f"acme's DEK should now be wrapped by version 2, got {new_wrapped}"
    assert new_wrapped.blob != old_wrapped.blob, "re-wrapping produces a new blob"
    assert kms.unwrap(new_wrapped, "acme") == dek_old, "re-wrapping must not change the DEK itself"
    assert store.records == data_before, "KEK rotation must not touch a single byte of the stored records"
    assert [store.get("acme", f"r{i}") for i in range(5)] == [f"acme record {i}: confidential".encode() for i in range(5)], "acme's data still reads after rotation"
    assert store.tenants["globex"].version == 1 and store.tenants["initech"].version == 1, "rotating acme's key must not touch other tenants"
    ops = [e["op"] for e in kms.audit if e["key_id"] == keyid and e["seq"] > 6]
    assert ops.count("rewrap") == 1 and "rotate" in ops, f"expected one rotate and ONE rewrap entry for acme; ops since creation: {ops}"
    rw = next(e for e in kms.audit if e["op"] == "rewrap")
    assert rw["version"] == 2 and rw.get("from_version") == 1, f"a rewrap entry records version=2 and from_version=1: {rw}"
    # --- old copies of the wrapped key (a backup!) still work while version 1 is enabled
    assert kms.unwrap(old_wrapped, "acme") == dek_old, "version 1 stays decryptable after rotation"
    assert kms.wrap(keyid, dek_old, "acme").version == 2, "new wraps use the current version"
    assert raises(mod.KMSError, kms.rewrap, old_wrapped, "globex"), "rewrap with the wrong context must be refused"
    assert raises(mod.KMSError, kms.disable_version, keyid, 2), "the current version cannot be disabled"
    assert raises(mod.KMSError, kms.destroy_version, keyid, 1), "an ENABLED version cannot be destroyed: disable it first"
    # --- retire: disable, watch for stragglers, destroy
    kms.disable_version(keyid, 1)
    assert kms.versions(keyid)[1] == "disabled"
    assert raises(mod.KMSError, kms.unwrap, old_wrapped, "acme"), "a disabled version must refuse to unwrap: the straggler (an old wrapped copy) shows up as an error"
    assert store.get("acme", "r0"), "live reads are unaffected: they use version 2"
    kms.enable_version(keyid, 1)
    assert kms.unwrap(old_wrapped, "acme") == dek_old, "disabling is reversible"
    kms.disable_version(keyid, 1)
    kms.destroy_version(keyid, 1)
    assert kms.versions(keyid) == {1: "destroyed", 2: "enabled"}
    assert kms._keys[keyid]["versions"][1]["material"] is None, "destroying a version must erase its key bytes (set material to None), not just flip a flag"
    assert raises(mod.KMSError, kms.unwrap, old_wrapped, "acme"), "after destroy the old wrapped key is gone for good"
    assert raises(mod.KMSError, kms.enable_version, keyid, 1), "a destroyed version cannot be re-enabled"
    assert raises(mod.KMSError, kms.disable_version, keyid, 1), "a destroyed version cannot be disabled again"
    assert kms.rotate(keyid) == 3, "version numbers are never reused"
    assert store.rotate_kek("acme") == 4 and store.tenants["acme"].version == 4
    for t in ("globex", "initech"):
        store.rotate_kek(t)
    assert all(w.version == 2 for t, w in store.tenants.items() if t != "acme")
    assert store.records == data_before, "after rotating every tenant, still not one byte of data re-encrypted"
    for t in ("acme", "globex", "initech"):
        assert store.get(t, "r3") == f"{t} record 3: confidential".encode(), f"{t} unreadable after rotation"
    # --- the operational lesson: a backup taken before rotation holds version-1 wrapped keys
    store.restore(backup_before)
    assert store.tenants["acme"].version == 1
    assert raises(mod.KMSError, store.get, "acme", "r0"), "restoring a backup whose wrapped keys use a DESTROYED version fails: retire a key version only after every wrapped copy has been re-wrapped or has expired"
    return (f"rotate + rewrap changed 3 wrapped keys and 0 of {len(data_before)} records; old versions decrypt until disabled; destroy needs disable first"
            "\na backup taken before rotation cannot be restored once its key version is destroyed (acme); that is the cost of retiring")


# ------------------------------------------------------------------ milestone 5
def readable(store, tenant, n):
    ok = 0
    for i in range(n):
        try:
            store.get(tenant, f"r{i}")
            ok += 1
        except Exception:
            pass
    return ok


def m5():
    kms, store = store_with(("acme", "globex", "initech"), n=6)
    backup1 = store.snapshot()                                      # last night's backup
    store.put("globex", "r6", b"globex record 6: written after the backup")
    store.rotate_kek("globex")                                      # the wrapped key in backup1 is version 1; live is version 2
    backup2 = store.snapshot()
    assert readable(store, "globex", 6) == 6
    # --- the trap: deleting the LIVE wrapped key is not shredding
    naive = mod.TenantStore(kms)
    naive.restore(backup2)
    del naive.tenants["globex"]                                     # "destroy the key": delete the live row
    assert readable(naive, "globex", 6) == 0, "(internal) with the live wrapped key row deleted, live reads fail"
    naive.restore(backup2)                                          # ...but the backup still has the wrapped key
    assert readable(naive, "globex", 6) == 6, "(internal) a backup that still has the wrapped key must stay readable while the master key exists"
    # --- the real thing
    assert raises(KeyError, store.shred_tenant, "nobody"), "shredding an unknown tenant must raise KeyError"
    store.shred_tenant("globex")
    destroy = [e for e in kms.audit if e["op"] == "destroy_key"]
    assert len(destroy) == 1 and destroy[0]["key_id"] == "tenant/globex" and destroy[0]["ok"], f"expected one successful destroy_key audit entry for tenant/globex, got {destroy}"
    assert all(s == "destroyed" for s in kms.versions("tenant/globex").values()), f"every version must be destroyed: {kms.versions('tenant/globex')}"
    assert all(v["material"] is None for v in kms._keys["tenant/globex"]["versions"].values()), "destroy_key must erase the key bytes of every version"
    live_failures = 0
    for i in range(6):
        try:
            store.get("globex", f"r{i}")
        except (KeyError, mod.KMSError):
            live_failures += 1
    assert live_failures == 6, "after shredding, globex's records must be unreadable in the live store"
    assert any(k[0] == "globex" for k in store.records), "shredding does not need to delete the ciphertext: it only has to make it useless"
    # --- backups, old and new, hold the ciphertext AND the wrapped key, and neither helps
    for label, snap in (("last night's backup (key version 1)", backup1), ("the newer backup (key version 2)", backup2)):
        store.restore(snap)
        assert any(k[0] == "globex" for k in snap["records"]) and "globex" in snap["tenants"], "(internal) backups contain globex's ciphertext and its wrapped key"
        n = readable(store, "globex", 6)
        assert n == 0, f"{label}: {n} of 6 globex records are STILL readable after the shred"
        assert raises(mod.KMSError, store.get, "globex", "r0"), f"{label}: expected KMSError from the KMS (the key is destroyed)"
        assert raises(mod.KMSError, kms.unwrap, snap["tenants"]["globex"], "globex"), "the wrapped key from the backup cannot be unwrapped by anyone, including admins"
        assert readable(store, "acme", 6) == 6 and readable(store, "initech", 6) == 6, f"{label}: other tenants must be unaffected"
    store.restore(backup2)
    store.rotate_kek("acme")
    store.put("initech", "r99", b"still writable")
    assert store.get("initech", "r99") == b"still writable" and readable(store, "acme", 6) == 6, "other tenants can still rotate and write"
    # --- the audit trail and the tombstone
    failed = [e for e in kms.audit if e["op"] == "unwrap" and e["key_id"] == "tenant/globex" and not e["ok"]]
    assert len(failed) >= 2 and all(e["error"] for e in failed), "unwrap attempts on the destroyed key are logged as refused, with a reason"
    assert raises((mod.KMSError, ValueError), store.create_tenant, "globex"), \
        "a destroyed tenant's key id must not be creatable again (the KMS keeps a tombstone); creating the tenant again must fail"
    assert raises(mod.KMSError, kms.rotate, "tenant/globex"), "a destroyed key cannot rotate"
    assert raises(mod.KMSError, kms.wrap, "tenant/globex", bytes(32), "globex"), "a destroyed key cannot wrap"
    return ("naive shred (delete the live wrapped key): the backup still opens all 6 records\n"
            "real shred (destroy the master key in the KMS): 0 of 6 globex records readable live, in last night's backup, and in the newer one\n"
            "acme and initech: all records readable throughout, and still writable and rotatable")


print(f"Lab 6 checks against {target}.py   (the cipher is a toy: educational only)\n")
check(1, "Milestone 1: a toy AEAD with a nonce and associated data", m1)
check(2, "Milestone 2: a KMS simulator that wraps, unwraps and audits", m2)
check(3, "Milestone 3: per-tenant data keys, tenant bound as associated data", m3)
check(4, "Milestone 4: KEK rotation, rewrap without re-encrypting, retire", m4)
check(5, "Milestone 5: crypto-shredding, backups included", m5)
print(f"\n{sum(results)}/{len(results)} milestones passing")
sys.exit(0 if all(results) else 1)
