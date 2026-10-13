"""Self-check for Lab 2.

    python3 check.py              # checks your starter.py
    python3 check.py solution     # checks the reference solution

Milestone 4 starts a real child process that appends records and SIGKILLs it
at a (seeded) random moment, then reopens the log. It also cuts a log file at
random byte offsets to simulate torn writes. Prints ✔ / ✘ / … (not
implemented yet) per milestone, plus a rough throughput table for milestone 3.
"""
import contextlib
import importlib
import os
import random
import select
import signal
import struct
import subprocess
import sys
import tempfile
import time
import zlib

if os.name != "posix":
    print("Lab 2 uses fsync, SIGKILL and directory descriptors, which are POSIX features.")
    print("Use macOS, Linux, or Windows with WSL (then run this inside the WSL terminal).")
    sys.exit(2)

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def payload_for(i):
    """The payload of record number i: recognisable, with a varying length."""
    return f"record-{i:06d}-".encode() + bytes([65 + i % 26]) * (i * 37 % 300)


# --- the child process used by milestone 4 ---------------------------------------
if len(sys.argv) > 3 and sys.argv[1] == "--writer":
    _mod = importlib.import_module(sys.argv[2])
    _log = _mod.RecordLog(sys.argv[3], fsync="always")
    for _i in range(10 ** 7):
        _log.append(payload_for(_i))            # returns only after the fsync
        os.write(1, b"%d\n" % _i)               # the ACK: "record _i is durable"
    sys.exit(0)

target = sys.argv[1] if len(sys.argv) > 1 else "starter"
mod = importlib.import_module(target)
results = []
notes = []                  # detail lines printed under a milestone's result


def note(text):
    notes.append(text)


class NotStarted(Exception):
    pass


def check(name, fn):
    del notes[:]
    try:
        fn()
        print(f"  ✔ {name}")
        results.append(True)
    except (NotImplementedError, NotStarted) as e:
        print(f"  … {name}: not implemented yet ({e})")
        results.append(False)
    except AssertionError as e:
        print(f"  ✘ {name}: {e}")
        results.append(False)
    except Exception as e:
        print(f"  ✘ {name}: {type(e).__name__}: {e}")
        results.append(False)
    for line in notes:
        print(line)


@contextlib.contextmanager
def counting_fsync():
    """Count calls to os.fsync (and remember whether each was on a directory)."""
    import stat
    calls = []
    real = os.fsync

    def fake(fd):
        calls.append(stat.S_ISDIR(os.fstat(fd).st_mode))
        return real(fd)

    os.fsync = fake
    try:
        yield calls
    finally:
        os.fsync = real


def encode(payload):
    """Independent encoder, so milestone 2+ checks do not depend on your encode_record."""
    length = struct.pack(">I", len(payload))
    return length + struct.pack(">I", zlib.crc32(length + payload)) + payload


def read_file(path):
    with open(path, "rb") as f:
        return f.read()


# --- Milestone 1 -----------------------------------------------------------------

def m1():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "log.bin")
        items = [b"hello", b"", b"x" * 1000, bytes(range(256))]
        assert mod.encode_record(b"hello") == encode(b"hello"), (
            "encode_record(b'hello') should be 4-byte big-endian length (5), 4-byte big-endian CRC32 "
            "of (length bytes + payload), then the payload")
        with mod.RecordLog(path, fsync="never") as log:
            offsets = [log.append(p) for p in items]
            want, pos = [], 0
            for p in items:
                want.append(pos)
                pos += 8 + len(p)
            assert offsets == want, f"append should return each record's starting offset: expected {want}, got {offsets}"
            assert log.read_all() == items, "read_all should return the payloads in order"
        assert read_file(path) == b"".join(encode(p) for p in items), "the file bytes do not match the record format"
        with mod.RecordLog(path, fsync="never") as log:         # reopen: data persists, offsets continue
            assert log.read_all() == items, "after reopening, the old records should still be there"
            assert log.append(b"more") == pos, f"after reopening, the next offset should be {pos}"
            assert log.read_all() == items + [b"more"]


# --- Milestone 2 -----------------------------------------------------------------

def m2():
    mod.scan_records(b"")                       # probe: raises NotImplementedError until you write it
    good = [b"alpha", b"bravo" * 20, b"charlie"]
    blob = b"".join(encode(p) for p in good)
    end = len(blob)
    payloads, good_end = mod.scan_records(blob)
    assert payloads == good and good_end == end, "scan_records should accept a clean log completely"
    assert mod.scan_records(b"") == ([], 0), "an empty file has no records and ends at 0"

    flipped = bytearray(encode(b"delta" * 10))
    flipped[-3] ^= 0x01                                         # one bit wrong in the payload
    bad_len = struct.pack(">II", 0xFFFFFFF0, 0) + b"zz"          # absurd length
    tails = {
        "3 stray bytes (half a header)": b"\x00\x00\x00",
        "a header with no payload": encode(b"delta" * 10)[:8],
        "a payload cut short": encode(b"delta" * 10)[:-7],
        "a record with one flipped bit": bytes(flipped),
        "an absurd length field": bad_len,
        "random garbage": random.Random(7).randbytes(37) if hasattr(random.Random, "randbytes") else bytes(range(37)),
    }
    for label, tail in tails.items():
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "log.bin")
            with open(path, "wb") as f:
                f.write(blob + tail)
            with mod.RecordLog(path, fsync="never") as log:
                assert os.path.getsize(path) == end, (
                    f"tail = {label}: opening the log should truncate the file back to {end} bytes, "
                    f"but it is {os.path.getsize(path)}")
                assert log.read_all() == good, f"tail = {label}: the good records should survive"
                assert log.append(b"after") == end, f"tail = {label}: the next append should start at {end}"
                assert log.read_all() == good + [b"after"]
    # corruption in the MIDDLE: everything from the bad record on is dropped (we cannot trust what follows)
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "log.bin")
        broken = bytearray(blob)
        broken[len(encode(good[0])) + 10] ^= 0x40               # damage the second record's payload
        with open(path, "wb") as f:
            f.write(bytes(broken))
        with mod.RecordLog(path, fsync="never") as log:
            assert log.read_all() == good[:1], "a bad record in the middle ends the valid prefix: expect only the first record"
    # a healthy file is not touched
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "log.bin")
        with open(path, "wb") as f:
            f.write(blob)
        mod.RecordLog(path, fsync="never").close()
        assert read_file(path) == blob, "opening an undamaged log must not change it"


# --- Milestone 3 -----------------------------------------------------------------

def rate(policy, n, tmp, **kw):
    path = os.path.join(tmp, f"bench-{policy}.bin")
    payload = b"p" * 100
    with mod.RecordLog(path, fsync=policy, **kw) as log:
        t = time.perf_counter()
        for _ in range(n):
            log.append(payload)
        log.flush()
        dt = time.perf_counter() - t
    return n / dt


def m3():
    with tempfile.TemporaryDirectory() as tmp:
        with mod.RecordLog(os.path.join(tmp, "a.bin"), fsync="always") as log:
            with counting_fsync() as calls:
                for i in range(5):
                    log.append(b"x")
                assert len(calls) == 5, f"fsync='always' should fsync after every append: expected 5 calls, saw {len(calls)}"
        with mod.RecordLog(os.path.join(tmp, "b.bin"), fsync="batch", batch_size=4) as log:
            with counting_fsync() as calls:
                for i in range(10):
                    log.append(b"x")
                assert len(calls) == 2, f"fsync='batch' with batch_size=4 and 10 appends: expected 2 fsyncs (after record 4 and 8), saw {len(calls)}"
                log.flush()
                assert len(calls) == 3, "flush() should fsync the 2 records still waiting"
                log.flush()
                assert len(calls) == 3, "flush() with nothing waiting should not fsync again"
        with mod.RecordLog(os.path.join(tmp, "c.bin"), fsync="never") as log:
            with counting_fsync() as calls:
                for i in range(10):
                    log.append(b"x")
                assert len(calls) == 0, f"fsync='never' should not fsync on append, saw {len(calls)} calls"
                log.flush()
                assert len(calls) == 1, "an explicit flush() always syncs what is waiting, even under 'never'"
        # Rough throughput. No pass/fail: it depends entirely on your disk.
        r_always = rate("always", 200, tmp)
        r_batch = rate("batch", 2000, tmp, batch_size=32)
        r_never = rate("never", 2000, tmp)
    note("      rough throughput on this machine (100-byte records; depends on your disk, not graded):")
    note(f"        always          {r_always:>10,.0f} appends/s")
    note(f"        batch (32)      {r_batch:>10,.0f} appends/s   ({r_batch / r_always:,.1f}x always)")
    note(f"        never           {r_never:>10,.0f} appends/s   ({r_never / r_always:,.1f}x always)")


# --- Milestone 4 -----------------------------------------------------------------

def kill_round(path, k, jitter):
    """Start a writer, SIGKILL it after k acks (plus jitter seconds). Returns (acks, killed_ok)."""
    p = subprocess.Popen([sys.executable, os.path.join(HERE, "check.py"), "--writer", target, path],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    buf = b""
    try:
        deadline = time.time() + 20
        while buf.count(b"\n") < k:
            if time.time() > deadline:
                raise AssertionError("the writer process did not reach its acks in 20 s")
            r, _, _ = select.select([p.stdout], [], [], 0.2)
            if r:
                chunk = os.read(p.stdout.fileno(), 65536)
                if not chunk:
                    err = p.stderr.read().decode()
                    if "NotImplementedError" in err:
                        raise NotStarted(err.strip().splitlines()[-1].split(": ", 1)[-1])
                    raise AssertionError("the writer process stopped by itself:\n" + err.strip()[-500:])
                buf += chunk
        time.sleep(jitter)
        os.kill(p.pid, signal.SIGKILL)          # no cleanup code runs: the process just vanishes
        while True:                              # collect acks that were already in the pipe
            chunk = os.read(p.stdout.fileno(), 65536)
            if not chunk:
                break
            buf += chunk
    finally:
        try:
            os.kill(p.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        p.wait()
        p.stdout.close()
        p.stderr.close()
    lines = buf.split(b"\n")[:-1]                # a last partial line was never a complete ack
    return [int(x) for x in lines]


def m4():
    mod.scan_records(b"")                       # probes: this milestone needs 1 and 2 first
    mod.encode_record(b"")
    rng = random.Random(20240601)
    rounds = 5
    with tempfile.TemporaryDirectory() as tmp:
        for rnd in range(1, rounds + 1):
            path = os.path.join(tmp, f"crash-{rnd}.bin")
            k = rng.randint(5, 40)
            acks = kill_round(path, k, rng.uniform(0, 0.004))
            assert acks == list(range(len(acks))), f"acks should be 0,1,2,... in order, got {acks[:10]}..."
            raw = read_file(path)
            _, good_end = mod.scan_records(raw)
            torn = len(raw) - good_end
            with mod.RecordLog(path, fsync="always") as log:        # reopening runs recovery
                records = log.read_all()
                n = len(records)
                assert n >= len(acks), (f"round {rnd}: {len(acks)} records were acknowledged (fsynced) before the kill, "
                                        f"but only {n} are in the log. An acknowledged record was lost!")
                assert records == [payload_for(i) for i in range(n)], f"round {rnd}: the records are not exactly 0..{n - 1} in order"
                assert os.path.getsize(path) == sum(8 + len(r) for r in records), f"round {rnd}: garbage left in the file after recovery"
                log.append(b"after-crash")
                assert log.read_all()[-1] == b"after-crash"
            note(f"      round {rnd}: killed after {len(acks)} acks; log held {n} records; {torn} torn bytes repaired")
    # Separate test: cut a finished log at random byte offsets, and flip random bits.
    rng = random.Random(99)
    payloads = [payload_for(i) for i in range(30)]
    ends, pos = [0], 0
    for p in payloads:
        pos += 8 + len(p)
        ends.append(pos)
    blob = b"".join(encode(p) for p in payloads)
    cuts = [0, 1, 7, 8, ends[1] - 1, ends[1], ends[1] + 1, len(blob) - 1, len(blob)]
    cuts += [rng.randint(0, len(blob)) for _ in range(40)]
    with tempfile.TemporaryDirectory() as tmp:
        for cut in cuts:
            path = os.path.join(tmp, "cut.bin")
            with open(path, "wb") as f:
                f.write(blob[:cut])
            keep = max(i for i, e in enumerate(ends) if e <= cut)    # whole records that fit before the cut
            with mod.RecordLog(path, fsync="never") as log:
                assert log.read_all() == payloads[:keep], f"file cut at byte {cut}: expected the first {keep} records to survive"
                assert os.path.getsize(path) == ends[keep], f"file cut at byte {cut}: expected truncation to {ends[keep]} bytes"
                assert log.append(b"new") == ends[keep]
        for _ in range(20):
            bad = bytearray(blob)
            at = rng.randrange(len(blob))
            bad[at] ^= 1 << rng.randrange(8)
            keep = max(i for i, e in enumerate(ends) if e <= at)     # the record containing byte `at` is the first bad one
            path = os.path.join(tmp, "flip.bin")
            with open(path, "wb") as f:
                f.write(bytes(bad))
            with mod.RecordLog(path, fsync="never") as log:
                assert log.read_all() == payloads[:keep], f"a bit flipped at byte {at}: expected exactly {keep} records to survive"
    note(f"      {len(cuts)} random cuts and 20 bit flips all recovered to a clean prefix")


# --- Milestone 5 -----------------------------------------------------------------

class Crash(Exception):
    pass


def m5():
    stages = ["tmp_partial", "tmp_written", "tmp_synced", "replaced", "dir_synced"]
    old = {"name": "old", "workers": 2, "tags": ["a", "b"]}
    new = {"name": "new", "workers": 8, "note": "héllo ✓", "nested": {"x": 1}}
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "config.json")
        seen = []
        mod.save_config(path, new, hook=seen.append)
        assert seen == stages, f"hook should be called after each step, in order {stages}; got {seen}"
        assert mod.load_config(path) == new, "load_config should return what save_config saved"
        assert not os.path.exists(path + ".tmp"), "after success the temp file should be gone (it was renamed)"
        for stage in stages:
            with open(path, "w") as f:                                  # put the OLD config in place
                f.write('{"name": "old", "workers": 2, "tags": ["a", "b"]}')

            def boom(name, stage=stage):
                if name == stage:
                    raise Crash(stage)
            try:
                mod.save_config(path, new, hook=boom)
            except Crash:
                pass
            else:
                raise AssertionError(f"the hook's exception at {stage!r} should propagate out of save_config")
            assert os.path.exists(path), f"crash after {stage!r}: the config file is MISSING"
            try:
                got = mod.load_config(path)
            except ValueError:
                raise AssertionError(f"crash after {stage!r}: the config file is half-written (invalid JSON)")
            want = new if stage in ("replaced", "dir_synced") else old
            assert got == want, (f"crash after {stage!r}: expected the {'NEW' if want is new else 'OLD'} config, got {got}. "
                                 "Only os.replace should switch from old to new")
            mod.save_config(path, {"name": "recovered"})                # leftover temp file must not break the next save
            assert mod.load_config(path) == {"name": "recovered"}
        # First-ever save, crash midway: no file at all is fine; a partial file is not.
        fresh = os.path.join(tmp, "fresh.json")
        try:
            mod.save_config(fresh, new, hook=lambda s: (_ for _ in ()).throw(Crash(s)) if s == "tmp_partial" else None)
        except Crash:
            pass
        assert not os.path.exists(fresh), "crash while writing the very first config: the real path must not exist yet"
        # Order of the durability steps
        events = []
        real_fsync, real_replace = os.fsync, os.replace

        def fs(fd):
            import stat
            events.append("fsync-dir" if stat.S_ISDIR(os.fstat(fd).st_mode) else "fsync-file")
            return real_fsync(fd)

        def rp(a, b):
            events.append("replace")
            return real_replace(a, b)
        os.fsync, os.replace = fs, rp
        try:
            mod.save_config(os.path.join(tmp, "order.json"), {"a": 1})
        finally:
            os.fsync, os.replace = real_fsync, real_replace
        assert events == ["fsync-file", "replace", "fsync-dir"], (
            f"expected: fsync the temp FILE, then os.replace, then fsync the DIRECTORY; saw {events}")


print(f"Lab 2 checks against {target}.py\n")
check("Milestone 1: record format and append-only log", m1)
check("Milestone 2: recovery from a torn or corrupt tail", m2)
check("Milestone 3: durability policies (always / batch / never)", m3)
check("Milestone 4: crash tests (SIGKILL and random cuts)", m4)
check("Milestone 5: atomic config replace", m5)
passed = sum(results)
print(f"\n{passed}/{len(results)} milestones passing" + ("  🎉 Lab complete!" if passed == len(results) else ""))
sys.exit(0 if passed == len(results) else 1)
