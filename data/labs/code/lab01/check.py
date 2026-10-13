"""Self-check for Lab 1.

    python3 check.py              # checks your starter.py
    python3 check.py solution     # checks the reference solution

Everything runs in temporary directories and finishes in a few seconds. All
randomness is seeded. Milestone 2 also prints a small speed table (not graded);
milestone 4 corrupts and truncates real files to test recovery.
"""
import contextlib
import importlib
import os
import random
import shutil
import stat
import struct
import sys
import tempfile
import time
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

target = sys.argv[1] if len(sys.argv) > 1 else "starter"
mod = importlib.import_module(target)
results = []                # (required?, passed?)
notes = []                  # detail lines printed under a milestone's result


def note(text):
    notes.append(text)


def check(name, fn, required=True):
    del notes[:]
    ok = False
    try:
        fn()
        print(f"  ✔ {name}")
        ok = True
    except NotImplementedError as e:
        print(f"  … {name}: not implemented yet ({e})")
    except AssertionError as e:
        print(f"  ✘ {name}: {e}")
    except Exception as e:
        print(f"  ✘ {name}: {type(e).__name__}: {e}")
    results.append((required, ok))
    for line in notes:
        print(line)


# --- independent helpers: the checks never rely on YOUR encoder or scanner ---------------

def enc(key, value):
    vlen = -1 if value is None else len(value)
    body = struct.pack(">Ii", len(key), vlen) + key + (value or b"")
    return struct.pack(">I", zlib.crc32(body)) + body


def parse(data):
    """Independent parser: list of (key, value, offset, size) for the valid prefix, plus its end."""
    out, pos = [], 0
    while pos + 12 <= len(data):
        crc, klen, vlen = struct.unpack_from(">IIi", data, pos)
        end = pos + 12 + klen + max(vlen, 0)
        if klen > 1 << 16 or vlen < -1 or end > len(data) or zlib.crc32(data[pos + 4:end]) != crc:
            break
        key = data[pos + 12:pos + 12 + klen]
        out.append((key, None if vlen == -1 else data[pos + 12 + klen:end], pos, end - pos))
        pos = end
    return out, pos


def read_file(path):
    with open(path, "rb") as f:
        return f.read()


def seg(d, i):
    return os.path.join(d, "seg-%06d.log" % i)


def seg_ids(d):
    return sorted(int(n[4:10]) for n in os.listdir(d) if n.startswith("seg-") and n.endswith(".log"))


def hint_files(d):
    return sorted(n for n in os.listdir(d) if n.endswith(".hint"))


def snapshot(store, keys):
    return {k: store.get(k) for k in keys}


@contextlib.contextmanager
def counting_decode():
    """Count calls to mod.decode_record."""
    calls = [0]
    real = mod.decode_record

    def fake(*a, **kw):
        calls[0] += 1
        return real(*a, **kw)

    mod.decode_record = fake
    try:
        yield calls
    finally:
        mod.decode_record = real


def key_of(i):
    return b"key:%05d" % i


def value_of(i, version=0):
    return (b"v%d-%05d-" % (version, i)) + bytes([97 + i % 26]) * (10 + i * 7 % 60)


# --- Milestone 1 -----------------------------------------------------------------------------

def m1():
    assert mod.encode_record(b"name", b"ada") == enc(b"name", b"ada"), (
        "encode_record(b'name', b'ada') should be: 4-byte CRC32, 4-byte key length, 4-byte SIGNED "
        "value length, key, value (all big-endian), where the CRC covers everything after itself")
    assert mod.encode_record(b"gone", None) == enc(b"gone", None), "a tombstone has value length -1 and no value bytes"
    assert mod.encode_record(b"k", b"") != mod.encode_record(b"k", None), "an empty value is not a tombstone"
    assert mod.decode_record(mod.encode_record(b"k", b"")) == (b"k", b"", 13), "decode_record of an empty value"
    # round trips, at an offset inside a bigger buffer
    items = [(b"a", b"1"), (b"", b"empty key"), (b"big", b"x" * 5000), (b"t", None), (bytes(range(256)), bytes(range(255, -1, -1)))]
    buf = b"".join(enc(k, v) for k, v in items)
    pos = 0
    for k, v in items:
        rec = mod.decode_record(buf, pos)
        assert rec is not None, f"decode_record returned None for a good record {k[:8]!r} at offset {pos}"
        assert rec[:2] == (k, v), f"decoded {rec[:2]!r}, expected {(k, v)!r}"
        pos = rec[2]
    assert pos == len(buf), "next_pos of the last record should equal the buffer length"
    assert mod.decode_record(buf, len(buf)) is None, "at the very end of the buffer there is no record: return None"
    # every proper prefix of a record is a torn write -> None
    one = enc(b"hello", b"world")
    for cut in range(len(one)):
        assert mod.decode_record(one[:cut]) is None, f"a record cut after {cut} of {len(one)} bytes must be rejected"
    # one flipped bit anywhere -> None (CRC32 catches every single-bit error)
    rng = random.Random(1)
    for i in range(len(one)):
        bad = bytearray(one)
        bad[i] ^= 1 << rng.randrange(8)
        assert mod.decode_record(bytes(bad)) is None, f"a flipped bit in byte {i} of the record was not detected"
    # absurd lengths must not be trusted
    assert mod.decode_record(struct.pack(">IIi", 0, 0x7FFFFFF0, 5) + b"x" * 20) is None, "absurd key length"
    assert mod.decode_record(struct.pack(">IIi", 0, 3, 0x7FFFFFF0) + b"x" * 20) is None, "absurd value length"
    assert mod.decode_record(struct.pack(">IIi", 0, 3, -7) + b"x" * 20) is None, "value length below -1"
    # ScanStore
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "scan.log")
        s = mod.ScanStore(path)
        assert s.get(b"nothing") is None, "get on an empty store returns None"
        s.put(b"a", b"1")
        s.put(b"b", b"2")
        s.put(b"a", b"3")
        s.put(b"e", b"")
        assert (s.get(b"a"), s.get(b"b"), s.get(b"zzz"), s.get(b"e")) == (b"3", b"2", None, b""), (
            "get must return the LAST value written for a key, None for unknown keys, and b'' for an empty value")
        want = enc(b"a", b"1") + enc(b"b", b"2") + enc(b"a", b"3") + enc(b"e", b"")
        assert read_file(path) == want, "the file should be the records back to back; an overwrite appends, it never edits"
        assert mod.ScanStore(path).get(b"b") == b"2", "a new ScanStore on the same file sees the old data"


# --- Milestone 2 -----------------------------------------------------------------------------

def m2():
    with tempfile.TemporaryDirectory() as tmp:
        d = os.path.join(tmp, "db")
        store = mod.Store(d, max_segment_bytes=1 << 30)
        n = 1000
        want, expect_file = {}, b""
        for i in range(n):
            store.put(key_of(i), value_of(i))
        for i in range(0, n, 3):
            store.put(key_of(i), value_of(i, 1))        # overwrite every third key
        for i in range(n):
            want[key_of(i)] = value_of(i, 1 if i % 3 == 0 else 0)
        for i in range(n):
            expect_file += enc(key_of(i), value_of(i))
        for i in range(0, n, 3):
            expect_file += enc(key_of(i), value_of(i, 1))
        assert os.path.exists(seg(d, 1)), "the first segment should be called seg-000001.log in the store's directory"
        assert read_file(seg(d, 1)) == expect_file, "the segment must be the records back to back, in write order (an overwrite appends a new record)"
        assert len(store) == n, f"len(store) should count live keys: expected {n}, got {len(store)}"
        for k, v in want.items():
            assert store.get(k) == v, f"get({k!r}) returned the wrong value"
        assert store.get(b"no-such-key") is None, "get of an unknown key returns None"
        # the index entries are (segment, offset, size) of the NEWEST record for each key
        offsets = {}
        for k, v, off, size in parse(expect_file)[0]:
            offsets[k] = (1, off, size)
        for k in want:
            assert store.index.get(k) == offsets[k], (
                f"store.index[{k!r}] should be (segment id, offset, record size) = {offsets[k]}, got {store.index.get(k)}")
        # get must not scan: count decode_record calls
        with counting_decode() as calls:
            for i in range(0, n, 7):
                store.get(key_of(i))
            looked_up = len(range(0, n, 7))
        assert calls[0] <= 2 * looked_up, (
            f"{looked_up} gets made {calls[0]} decode_record calls: get() should seek straight to the record "
            "using the index and decode only that one")
        store.close()

        # a speed table (not graded): the scanning store against the indexed store
        n = 4000
        rng = random.Random(7)
        keys = [key_of(i) for i in range(n)]
        probes = [rng.choice(keys) for _ in range(60)]
        slow = mod.ScanStore(os.path.join(tmp, "slow.log"))
        fast = mod.Store(os.path.join(tmp, "fast"), max_segment_bytes=1 << 30)
        for i, k in enumerate(keys):
            slow.put(k, value_of(i))
            fast.put(k, value_of(i))
        t0 = time.perf_counter()
        for k in probes:
            slow.get(k)
        t_slow = (time.perf_counter() - t0) / len(probes)
        fast_probes = probes * 20
        t0 = time.perf_counter()
        for k in fast_probes:
            fast.get(k)
        t_fast = (time.perf_counter() - t0) / len(fast_probes)
        fast.close()
        note(f"      {n} keys, {os.path.getsize(os.path.join(tmp, 'slow.log')):,} bytes in the log (timings depend on your machine; not graded):")
        note(f"        ScanStore.get  {t_slow * 1e3:9.3f} ms per lookup")
        note(f"        Store.get      {t_fast * 1e6:9.1f} us per lookup   (about {t_slow / t_fast:,.0f}x faster)")


# --- Milestone 3 -----------------------------------------------------------------------------

def m3():
    with tempfile.TemporaryDirectory() as tmp:
        # deletes
        d = os.path.join(tmp, "del")
        s = mod.Store(d, max_segment_bytes=1 << 30)
        s.put(b"a", b"1")
        s.put(b"b", b"2")
        size_before = os.path.getsize(seg(d, 1))
        assert s.delete(b"a") is True, "delete of an existing key returns True"
        assert s.get(b"a") is None, "a deleted key reads as None"
        assert b"a" not in s.index and len(s) == 1, "a deleted key leaves the index"
        recs = parse(read_file(seg(d, 1)))[0]
        assert recs[-1][0] == b"a" and recs[-1][1] is None, (
            "delete must APPEND a tombstone record (value length -1) for the key; the log is the truth, not the index")
        size_after = os.path.getsize(seg(d, 1))
        assert size_after == size_before + len(enc(b"a", None)), "the tombstone is the only thing delete adds"
        assert s.delete(b"a") is False and s.delete(b"never-there") is False, "deleting a missing key returns False"
        assert os.path.getsize(seg(d, 1)) == size_after, "deleting a missing key must not write anything"
        s.put(b"a", b"again")
        assert s.get(b"a") == b"again", "a key can be put again after a delete"
        s.close()

        # rollover
        d = os.path.join(tmp, "roll")
        limit = 2000
        s = mod.Store(d, max_segment_bytes=limit)
        want = {}
        for i in range(300):
            s.put(key_of(i % 120), value_of(i))
            want[key_of(i % 120)] = value_of(i)
            if i == 150:
                first_seg_bytes = read_file(seg(d, 1))
                assert len(seg_ids(d)) >= 2, "after 150 writes of ~60 bytes into 2000-byte segments there should be several segments"
        ids = seg_ids(d)
        assert len(ids) >= 5, f"expected at least 5 segments after 300 writes, found {len(ids)}"
        assert ids == list(range(1, len(ids) + 1)), f"segment ids should be consecutive from 1, got {ids}"
        for i in ids:
            size = os.path.getsize(seg(d, i))
            assert size <= limit, f"segment {i} is {size} bytes, above max_segment_bytes={limit}: roll over BEFORE a record would not fit"
        assert read_file(seg(d, 1)) == first_seg_bytes, "a sealed segment must never change: segment 1 is different now"
        for k, v in want.items():
            assert s.get(k) == v, f"get({k!r}) is wrong after rollover (is the index storing the segment id?)"
        assert {loc[0] for loc in s.index.values()} > {ids[-1]}, "the index should point into more than one segment"
        # an oversized record gets a segment to itself, and is still readable
        big = b"B" * 5000
        s.put(b"big", big)
        s.put(b"after-big", b"x")
        assert s.get(b"big") == big and s.get(b"after-big") == b"x", "a record bigger than the segment limit must still work"
        s.close()

        # random operations against a dict
        rng = random.Random(3)
        d = os.path.join(tmp, "fuzz")
        s = mod.Store(d, max_segment_bytes=700)
        model = {}
        for step in range(1500):
            k = key_of(rng.randrange(40))
            if rng.random() < 0.3:
                assert s.delete(k) == (k in model), f"step {step}: delete({k!r}) returned the wrong answer"
                model.pop(k, None)
            else:
                v = value_of(rng.randrange(1000), rng.randrange(5))
                s.put(k, v)
                model[k] = v
            if step % 100 == 0 or step == 1499:
                for i in range(40):
                    assert s.get(key_of(i)) == model.get(key_of(i)), f"step {step}: get({key_of(i)!r}) disagrees with a plain dict"
                assert len(s) == len(model) and s.keys() == sorted(model), f"step {step}: the set of live keys is wrong"
        note(f"      1500 random puts/deletes across {len(seg_ids(d))} segments agree with a dict")
        s.close()


# --- Milestone 4 -----------------------------------------------------------------------------

def build_single_segment(d, rng, n_ops=120):
    """One big segment; returns (list of (end_offset, state_after) in write order, final state)."""
    s = mod.Store(d, max_segment_bytes=1 << 30)
    state, history = {}, []
    for i in range(n_ops):
        k = key_of(rng.randrange(25))
        if rng.random() < 0.25 and k in state:
            s.delete(k)
            state.pop(k)
        else:
            v = value_of(rng.randrange(500), rng.randrange(3))
            s.put(k, v)
            state[k] = v
        history.append((os.path.getsize(seg(d, 1)), dict(state)))
    s.close()
    return history, state


def expected_after_cut(history, cut):
    """The state after the last operation that ended at or before byte `cut`."""
    state = {}
    for end, st in history:
        if end <= cut:
            state = st
        else:
            break
    return state


def assert_store_equals(s, state, what):
    assert len(s) == len(state), f"{what}: expected {len(state)} live keys, found {len(s)}"
    for k in set(state) | {key_of(i) for i in range(25)}:
        assert s.get(k) == state.get(k), f"{what}: get({k!r}) = {s.get(k)!r}, expected {state.get(k)!r}"


def m4():
    with tempfile.TemporaryDirectory() as tmp:
        rng = random.Random(4)
        base = os.path.join(tmp, "base")
        history, final = build_single_segment(base, rng)
        blob = read_file(seg(base, 1))
        ends = sorted({e for e, _ in history})

        def reopen(data, what, extra=None):
            d = os.path.join(tmp, "case")
            shutil.rmtree(d, ignore_errors=True)
            os.makedirs(d)
            with open(seg(d, 1), "wb") as f:
                f.write(data)
            s = mod.Store(d, max_segment_bytes=1 << 30)
            return d, s

        # 0. a healthy log reopens untouched
        d, s = reopen(blob, "clean")
        assert_store_equals(s, final, "clean reopen")
        s.close()
        assert read_file(seg(d, 1)) == blob, "opening a healthy log must not modify it"

        # 1. truncated at interesting offsets and at seeded random ones
        cuts = set()
        for e in ends[-6:]:
            cuts.update({e - 1, e, e + 1, e + 5, e + 13})
        cuts.update({0, 1, 11, 12, 13})
        cuts.update(rng.randrange(len(blob)) for _ in range(40))
        cuts = sorted(c for c in cuts if 0 <= c <= len(blob))
        for cut in cuts:
            d, s = reopen(blob[:cut], f"cut {cut}")
            want = expected_after_cut(history, cut)
            assert_store_equals(s, want, f"file cut at byte {cut}")
            good_end = parse(blob[:cut])[1]
            assert os.path.getsize(seg(d, 1)) == good_end, (
                f"file cut at byte {cut}: after recovery the file should be {good_end} bytes (the torn tail truncated), "
                f"but it is {os.path.getsize(seg(d, 1))}")
            s.put(b"after:crash", b"fresh")
            s.close()
            s2 = mod.Store(d, max_segment_bytes=1 << 30)
            assert s2.get(b"after:crash") == b"fresh", (
                f"file cut at byte {cut}: a record written after recovery was lost on the next open "
                "(did you truncate the torn tail, so new records do not land behind garbage?)")
            s2.close()
        note(f"      {len(cuts)} truncation points all recovered to the last whole record")

        # 2. one flipped bit anywhere: the damaged record and everything after it are dropped
        flips = 0
        for _ in range(25):
            pos = rng.randrange(len(blob))
            bad = bytearray(blob)
            bad[pos] ^= 1 << rng.randrange(8)
            good_end = parse(bytes(bad))[1]
            d, s = reopen(bytes(bad), f"flip {pos}")
            assert good_end <= pos, "internal: a flip must break the record that contains it"
            assert_store_equals(s, expected_after_cut(history, good_end), f"a bit flipped at byte {pos}")
            assert os.path.getsize(seg(d, 1)) == good_end, f"bit flip at byte {pos}: the file should be cut back to {good_end} bytes"
            s.close()
            flips += 1
        note(f"      {flips} random bit flips recovered to a clean prefix")

        # 3. garbage after the last good record
        junk = [rng.randbytes(37) if hasattr(rng, "randbytes") else bytes(rng.randrange(256) for _ in range(37)),
                struct.pack(">IIi", 0, 0x7FFFFFFF, 5) + b"junk",          # impossible key length
                struct.pack(">IIi", 0, 4, -9) + b"key!",                  # impossible value length
                enc(b"half", b"a record that is never finished")[:-5],   # a real record, cut short
                b"\x00" * 100]
        for j, g in enumerate(junk):
            d, s = reopen(blob + g, f"junk {j}")
            assert_store_equals(s, final, f"garbage #{j} after the last record")
            assert os.path.getsize(seg(d, 1)) == len(blob), f"garbage #{j}: it should be truncated away"
            s.close()

        # 4. several segments: a clean reopen, then damage to the tail and to a sealed segment
        d = os.path.join(tmp, "multi")
        s = mod.Store(d, max_segment_bytes=900)
        state = {}
        for i in range(400):
            k = key_of(rng.randrange(60))
            if rng.random() < 0.2 and k in state:
                s.delete(k)
                del state[k]
            else:
                s.put(k, value_of(i))
                state[k] = value_of(i)
        s.close()
        ids = seg_ids(d)
        assert len(ids) >= 5, "internal: expected several segments"
        snap = {i: read_file(seg(d, i)) for i in ids}
        s = mod.Store(d, max_segment_bytes=900)
        assert_store_equals(s, state, "reopening a multi-segment store")
        s.put(b"new", b"value")                 # appends continue in the last segment
        s.close()
        assert all(read_file(seg(d, i)) == snap[i] for i in ids[:-1]), "reopening must not touch sealed segments"
        # tear the last record of the last segment
        last = seg(d, ids[-1])
        data = read_file(last)
        with open(last, "wb") as f:
            f.write(data[:-3])
        s = mod.Store(d, max_segment_bytes=900)
        assert s.get(b"new") is None and len(read_file(last)) < len(data), "the torn last record should have been dropped and truncated"
        assert_store_equals_partial(s, state)
        s.close()
        # damage inside a sealed segment is NOT a crash artifact
        bad = bytearray(snap[ids[1]])
        bad[len(bad) // 2] ^= 0x40
        with open(seg(d, ids[1]), "wb") as f:
            f.write(bad)
        try:
            mod.Store(d, max_segment_bytes=900).close()
        except mod.CorruptionError:
            pass
        else:
            raise AssertionError("a damaged SEALED segment should raise CorruptionError on open, not be silently truncated")
        # a store whose active segment is empty (crash right after a rollover)
        d = os.path.join(tmp, "emptytail")
        os.makedirs(d)
        with open(seg(d, 1), "wb") as f:
            f.write(enc(b"x", b"1"))
        open(seg(d, 2), "wb").close()
        s = mod.Store(d)
        assert s.get(b"x") == b"1", "an empty final segment must not hide earlier ones"
        s.put(b"y", b"2")
        assert s.get(b"y") == b"2"
        s.close()


def assert_store_equals_partial(s, state):
    """After the last record of the final segment is torn, every OTHER key must still be right."""
    diffs = [k for k, v in state.items() if s.get(k) != v]
    assert len(diffs) <= 1, f"a torn tail may lose at most the one torn record, but {len(diffs)} keys changed"


# --- Milestone 5 -----------------------------------------------------------------------------

def build_workload(d, limit=1500, seed=5):
    """Many overwrites and deletes across many segments, including a key deleted long after it
    was written (its tombstone and its old value are in different segments)."""
    rng = random.Random(seed)
    s = mod.Store(d, max_segment_bytes=limit)
    touched = set()
    s.put(b"zombie", b"I was written first and deleted later")
    s.put(b"survivor", b"I stay")
    touched |= {b"zombie", b"survivor"}
    for i in range(900):
        k = key_of(rng.randrange(50))
        touched.add(k)
        if rng.random() < 0.2:
            s.delete(k)
        else:
            s.put(k, value_of(i, rng.randrange(9)))
        if i == 300:
            s.delete(b"zombie")         # the tombstone lands several segments after the old value
    assert len(seg_ids(d)) >= 6, "internal: workload should span several segments"
    return s, touched


class Crash(Exception):
    pass


def m5():
    with tempfile.TemporaryDirectory() as tmp:
        d = os.path.join(tmp, "db")
        s, touched = build_workload(d)
        before_data = snapshot(s, touched)
        before_bytes = s.total_bytes()
        n_before = len(seg_ids(d))
        assert before_data[b"zombie"] is None and before_data[b"survivor"] == b"I stay", "internal: workload sanity"
        s.compact()
        after_data = snapshot(s, touched)
        assert after_data == before_data, (
            "after compact() some values differ from before: " +
            ", ".join(repr(k) for k in sorted(touched) if after_data[k] != before_data[k])[:200])
        after_bytes = s.total_bytes()
        assert after_bytes < before_bytes, f"compaction should shrink the log, but {before_bytes} bytes became {after_bytes}"
        ids = seg_ids(d)
        assert len(ids) <= 2, f"after compacting everything there should be at most 2 segment files (merged + fresh active), found {len(ids)}"
        recs = []
        for i in ids:
            recs += parse(read_file(seg(d, i)))[0]
        assert all(v is not None for _, v, _, _ in recs), "compacted segments must not contain tombstones"
        assert len(recs) == len(s), f"compacted files should hold exactly one record per live key: {len(recs)} records, {len(s)} live keys"
        assert len({k for k, _, _, _ in recs}) == len(recs), "a key appears twice in the compacted files"
        assert not [n for n in os.listdir(d) if n.endswith(".tmp")], "no .tmp files may be left behind"
        # the store keeps working, and survives a reopen
        s.put(b"post-compaction", b"ok")
        s.delete(b"survivor")
        s.put(key_of(3), b"changed")
        expect = dict(after_data)
        expect.update({b"post-compaction": b"ok", b"survivor": None, key_of(3): b"changed"})
        assert snapshot(s, expect) == expect, "writes after a compaction misbehave"
        s.close()
        s2 = mod.Store(d, max_segment_bytes=1500)
        assert snapshot(s2, expect) == expect, "after compaction and reopening, the data is different (is the merged file replayed in the right order?)"
        s2.compact()
        assert snapshot(s2, expect) == expect, "a second compaction changed the data"
        s2.close()
        note(f"      {n_before} segments, {before_bytes:,} bytes  ->  {len(ids)} segments, {after_bytes:,} bytes "
             f"({100 * (1 - after_bytes / before_bytes):.0f}% smaller); all {len(touched)} keys read back identically")

        # compacting an empty store is harmless
        e = mod.Store(os.path.join(tmp, "empty"))
        e.compact()
        e.put(b"k", b"v")
        assert e.get(b"k") == b"v"
        e.close()

        # the swap order: new file fsynced BEFORE the rename, directory fsynced AFTER
        d = os.path.join(tmp, "order")
        s, touched = build_workload(d)
        events = []
        real_fsync, real_replace = os.fsync, os.replace
        synced_inodes = set()

        def fs(fd):
            st = os.fstat(fd)
            if stat.S_ISDIR(st.st_mode):
                events.append("fsync-dir")
            else:
                events.append("fsync-file")
                synced_inodes.add(st.st_ino)
            return real_fsync(fd)

        def rp(a, b):
            if str(a).endswith(".tmp") and ".hint" not in str(a):
                assert os.stat(a).st_ino in synced_inodes, "the new segment must be fsynced BEFORE os.replace publishes it"
                events.append("replace")
            return real_replace(a, b)

        os.fsync, os.replace = fs, rp
        try:
            s.compact()
        finally:
            os.fsync, os.replace = real_fsync, real_replace
        assert "replace" in events, "compaction must write a .tmp file and publish it with os.replace"
        if os.name == "posix":
            assert "fsync-dir" in events[events.index("replace"):], "fsync the directory after the rename (self._fsync_dir())"
        s.close()

        # crash at every stage of the swap, then reopen
        for stage in ("tmp_synced", "replaced", "deleted_1", "done"):
            d = os.path.join(tmp, "crash-" + stage)
            s, touched = build_workload(d)
            want = snapshot(s, touched)

            def boom(name, stage=stage):
                if name == stage:
                    raise Crash(stage)
            try:
                s.compact(hook=boom)
            except Crash:
                pass
            else:
                raise AssertionError(f"compact() never called hook({stage!r}); call hook(name) at each step listed in the docstring")
            s.close()                       # free the descriptors; the files are exactly as the "crash" left them
            r = mod.Store(d, max_segment_bytes=1500)
            got = snapshot(r, touched)
            bad = [k for k in sorted(touched) if got[k] != want[k]]
            if bad:
                hint = ""
                if bad[0] == b"zombie" and want[b"zombie"] is None:
                    hint = " (the deleted key 'zombie' came back to life: delete the old segments OLDEST first, so a tombstone is never removed while an older value it hides still exists)"
                raise AssertionError(f"crash after {stage!r}: {len(bad)} keys changed after reopening, e.g. {bad[0]!r}{hint}")
            r.compact()
            assert snapshot(r, touched) == want, f"crash after {stage!r}: compacting the recovered store changed the data"
            r.close()
        note("      simulated crashes after tmp_synced / replaced / deleted_1 / done all recovered the same data")


# --- Milestone 6 (optional) ------------------------------------------------------------------

def m6():
    with tempfile.TemporaryDirectory() as tmp:
        d = os.path.join(tmp, "db")
        rng = random.Random(6)
        s = mod.Store(d, max_segment_bytes=1200, hints=True)
        touched = set()
        for i in range(700):
            k = key_of(rng.randrange(80))
            touched.add(k)
            if rng.random() < 0.2:
                s.delete(k)
            else:
                s.put(k, value_of(i))
        want = snapshot(s, touched)
        s.close()
        ids = seg_ids(d)
        sealed = ids[:-1]
        assert len(sealed) >= 5, "internal: expected several sealed segments"
        hints = hint_files(d)
        assert len(hints) >= len(sealed), f"every sealed segment should have a .hint file: {len(sealed)} sealed segments, {len(hints)} hint files"
        last_records = len(parse(read_file(seg(d, ids[-1])))[0])
        total_records = sum(len(parse(read_file(seg(d, i)))[0]) for i in ids)
        with counting_decode() as calls:
            r = mod.Store(d, max_segment_bytes=1200, hints=True)
        assert snapshot(r, touched) == want, "with hint files the rebuilt index gives different answers"
        r.close()
        assert calls[0] <= last_records + 1, (
            f"reopening decoded {calls[0]} records, but with hints only the last segment ({last_records} records) "
            f"needs scanning, out of {total_records} in all")
        note(f"      reopen decoded {calls[0]} of {total_records} records (hints covered the sealed segments)")
        # damaged, truncated and missing hints fall back to scanning
        victim = os.path.join(d, hints[len(hints) // 2])
        original = read_file(victim)
        for what, data in (("a flipped byte", original[:5] + bytes([original[5] ^ 0xFF]) + original[6:]),
                           ("a truncated file", original[:len(original) // 2]),
                           ("a stale segment size", original[:-12] + struct.pack(">Q", 1) + original[-4:])):
            with open(victim, "wb") as f:
                f.write(data)
            r = mod.Store(d, max_segment_bytes=1200, hints=True)
            assert snapshot(r, touched) == want, f"a hint file with {what} must be ignored (scan the segment instead), not trusted"
            r.close()
        os.remove(victim)
        r = mod.Store(d, max_segment_bytes=1200, hints=True)
        assert snapshot(r, touched) == want, "a missing hint file must fall back to scanning"
        # compaction writes a hint for the merged segment
        r.compact()
        r.close()
        assert snapshot(mod.Store(d, max_segment_bytes=1200, hints=True), touched) == want, "after compaction with hints, data differ"
        assert hint_files(d), "compact() should leave a .hint file for the merged segment"
        # a store opened WITHOUT hints ignores them
        r = mod.Store(d, max_segment_bytes=1200, hints=False)
        assert snapshot(r, touched) == want
        r.close()


print(f"Lab 1 checks against {target}.py\n")
check("Milestone 1: records, and the slow scanning store", m1)
check("Milestone 2: in-memory hash index (O(1) gets)", m2)
check("Milestone 3: tombstone deletes and segment rollover", m3)
check("Milestone 4: crash recovery (torn and corrupt tails)", m4)
check("Milestone 5: compaction with a safe file swap", m5)
check("Milestone 6 (optional): hint files for fast startup", m6, required=False)

required = [ok for req, ok in results if req]
optional = [ok for req, ok in results if not req]
msg = f"\n{sum(required)}/{len(required)} required milestones passing"
if optional:
    msg += f", optional milestone 6: {'passing' if all(optional) else 'not done'}"
if all(required):
    msg += "  🎉 Lab complete!"
print(msg)
sys.exit(0 if all(required) else 1)
