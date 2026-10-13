"""Self-check for Lab 2.

    python3 check.py              # checks your starter.py
    python3 check.py solution     # checks the reference solution

Everything runs in temporary directories and finishes in well under a minute. All
randomness is seeded. Milestone 3 prints the observed Bloom-filter false-positive
rate next to the formula; milestone 5 prints write amplification (not graded).
"""
import contextlib
import hashlib
import importlib
import os
import random
import shutil
import struct
import subprocess
import sys
import tempfile
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

target = sys.argv[1] if len(sys.argv) > 1 else "starter"
mod = importlib.import_module(target)
results = []
notes = []


def note(text):
    notes.append(text)


def check(name, fn):
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
    results.append(ok)
    for line in notes:
        print(line)


# --- independent helpers (the checks never rely on YOUR encoder, scanner or reader) --------------

def enc(key, value):
    vlen = -1 if value is None else len(value)
    body = struct.pack(">Ii", len(key), vlen) + key + (value or b"")
    return struct.pack(">I", zlib.crc32(body)) + body


def parse(data):
    """Valid-prefix records as (key, value, offset, size), plus the offset where the prefix ends."""
    out, pos = [], 0
    while pos + 12 <= len(data):
        crc, klen, vlen = struct.unpack_from(">IIi", data, pos)
        end = pos + 12 + klen + max(vlen, 0)
        if klen > 1 << 16 or vlen < -1 or end > len(data) or zlib.crc32(data[pos + 4:end]) != crc:
            break
        out.append((data[pos + 12:pos + 12 + klen], None if vlen == -1 else data[pos + 12 + klen:end], pos, end - pos))
        pos = end
    return out, pos


def read_file(path):
    with open(path, "rb") as f:
        return f.read()


def sst_files(d):
    return sorted(n for n in os.listdir(d) if n.startswith("sst-") and n.endswith(".sst"))


def read_sst(path):
    """Independent SSTable reader. Returns a dict describing the file; asserts on a bad layout."""
    blob = read_file(path)
    assert len(blob) >= 36, f"{os.path.basename(path)} is too small to have a footer"
    magic, index_off, bloom_off, count, crc = struct.unpack(">8sQQQI", blob[-36:])
    assert magic == b"LSMSST01", "footer magic should be b'LSMSST01'"
    assert crc == zlib.crc32(blob[-36:-4]), "footer crc32 should cover the first 32 bytes of the footer"
    recs, end = parse(blob[:index_off])
    assert end == index_off, "the data region should be nothing but whole records, ending at the index offset"
    assert count == len(recs), f"footer says {count} records but the data region holds {len(recs)}"
    n, = struct.unpack_from(">I", blob, index_off)
    pos, index = index_off + 4, []
    for _ in range(n):
        klen, off = struct.unpack_from(">IQ", blob, pos)
        pos += 12
        index.append((blob[pos:pos + klen], off))
        pos += klen
    assert pos == bloom_off, "the bloom offset should come right after the sparse index"
    return {"records": recs, "index": index, "bloom": blob[bloom_off:len(blob) - 36], "size": len(blob), "count": count}


def key_of(i):
    return b"key:%05d" % i


def value_of(i, version=0):
    return (b"v%d-%05d-" % (version, i)) + bytes([97 + i % 26]) * (5 + i * 7 % 40)


@contextlib.contextmanager
def counting_decode():
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


def open_db(d, **kw):
    kw.setdefault("memtable_limit", 1 << 30)
    kw.setdefault("bloom_bits_per_key", 0)
    kw.setdefault("sparse_every", 4)
    return mod.LSMTree(d, **kw)


def snapshot(db, keys):
    return {k: db.get(k) for k in keys}


class Crash(Exception):
    pass


# --- Milestone 1 -----------------------------------------------------------------------------

def m1():
    # the memtable
    m = mod.MemTable()
    assert m.get(b"x") is mod.MISSING, "MemTable.get of an unknown key returns mod.MISSING (not None: None means 'deleted')"
    assert m.items() == [], "an empty memtable has no items"
    for k, v in ((b"b", b"2"), (b"a", b"1"), (b"c", b"3")):
        m.put(k, v)
    assert m.items() == [(b"a", b"1"), (b"b", b"2"), (b"c", b"3")], "items() must be sorted by key, whatever the insert order"
    m.put(b"b", b"two")
    assert m.get(b"b") == b"two" and len(m) == 3, "an overwrite replaces the old value"
    assert m.nbytes == 1 + 1 + 1 + 3 + 1 + 1, f"nbytes should be the sum of len(key)+len(value) over entries (8 here), got {m.nbytes}"
    m.delete(b"a")
    assert m.get(b"a") is None, "a deleted key reads as None (a tombstone), not MISSING"
    assert m.items()[0] == (b"a", None), "tombstones stay in items(): the flush has to write them"
    assert m.nbytes == 1 + 1 + 3 + 1 + 1, f"nbytes after a delete should count the key only, got {m.nbytes}"
    rng = random.Random(11)
    model = {}
    for _ in range(500):
        k = bytes([rng.randrange(97, 123)]) * rng.randrange(1, 4)
        v = None if rng.random() < 0.2 else bytes(rng.randrange(256) for _ in range(rng.randrange(0, 20)))
        m.put(k, v)
        model[k] = v
    assert m.items() == sorted(model.items()), "items() disagrees with a sorted dict"
    assert m.nbytes == sum(len(k) + len(v or b"") for k, v in model.items()), "nbytes drifted from the sum of entry sizes"

    with tempfile.TemporaryDirectory() as tmp:
        # the WAL
        path = os.path.join(tmp, "wal.log")
        assert mod.replay_wal(os.path.join(tmp, "missing.log")) == ([], 0), "replay_wal of a missing file is ([], 0)"
        w = mod.WAL(path)
        ops = [(key_of(i % 7), None if i % 5 == 4 else value_of(i)) for i in range(40)]
        for k, v in ops:
            w.append(k, v)
        want = b"".join(enc(k, v) for k, v in ops)
        assert read_file(path) == want, "the WAL must contain the records back to back, written as soon as append() returns"
        assert w.bytes_written == len(want), f"WAL.bytes_written should count record bytes: {len(want)}, got {w.bytes_written}"
        w.close()
        records, good_end = mod.replay_wal(path)
        assert records == ops and good_end == len(want), "replay_wal should return every (key, value) in order and good_end = file size"
        ends, pos = [], 0
        for k, v in ops:
            pos += len(enc(k, v))
            ends.append(pos)
        for cut in (0, 5, 11, 12, ends[3] - 1, ends[3], ends[3] + 7, ends[-1] - 1, rng.randrange(len(want))):
            with open(path, "wb") as f:
                f.write(want[:cut])
            records, good_end = mod.replay_wal(path)
            n = sum(1 for e in ends if e <= cut)
            assert records == ops[:n], f"WAL cut at byte {cut}: expected the first {n} records, got {len(records)}"
            assert good_end == (ends[n - 1] if n else 0), f"WAL cut at byte {cut}: good_end should be {ends[n - 1] if n else 0}, got {good_end}"
        bad = bytearray(want)
        bad[ends[9] + 3] ^= 0x10                      # a flipped bit inside record 10
        with open(path, "wb") as f:
            f.write(bytes(bad))
        records, good_end = mod.replay_wal(path)
        assert records == ops[:10] and good_end == ends[9], "a flipped bit must end the valid prefix at the damaged record"

        # the tree, memtable only
        d = os.path.join(tmp, "db")
        db = open_db(d)
        state = {}
        for i in range(300):
            k = key_of(rng.randrange(30))
            if rng.random() < 0.25:
                db.delete(k)
                state[k] = None
            else:
                v = value_of(i, rng.randrange(4))
                db.put(k, v)
                state[k] = v
        db.put(b"empty", b"")
        state[b"empty"] = b""
        for k, v in state.items():
            assert db.get(k) == v, f"get({k!r}) = {db.get(k)!r}, expected {v!r}"
        assert db.get(b"never-written") is None, "an unknown key reads as None"
        assert not sst_files(d), "with a huge memtable_limit nothing should be flushed yet"
        # "crash": abandon the object without close() or flush(); a new instance must replay the WAL
        db2 = open_db(d)
        for k, v in state.items():
            assert db2.get(k) == v, f"after a simulated crash, get({k!r}) = {db2.get(k)!r}, expected {v!r}: was it in the WAL before put() returned?"
        db2.put(b"after-restart", b"1")
        db2.close()
        assert open_db(d).get(b"after-restart") == b"1", "writes after a recovery must survive another restart"

        # torn WAL tail: cut the WAL of a fresh store at several offsets
        history = []                     # (end offset, state)
        d = os.path.join(tmp, "src")
        db = open_db(d)
        cur = {}
        for i in range(60):
            k = key_of(rng.randrange(12))
            if rng.random() < 0.3:
                db.delete(k)
                cur[k] = None
            else:
                db.put(k, value_of(i))
                cur[k] = value_of(i)
            history.append((os.path.getsize(os.path.join(d, "wal.log")), dict(cur)))
        blob = read_file(os.path.join(d, "wal.log"))
        db.close()
        cuts = sorted({0, 1, 12, 13} | {rng.randrange(len(blob)) for _ in range(25)} | {e - 1 for e, _ in history[-4:]})
        for cut in cuts:
            dd = os.path.join(tmp, "cut")
            shutil.rmtree(dd, ignore_errors=True)
            os.makedirs(dd)
            with open(os.path.join(dd, "wal.log"), "wb") as f:
                f.write(blob[:cut])
            want_state = {}
            for e, st in history:
                if e <= cut:
                    want_state = st
            good_end = max([e for e, _ in history if e <= cut] or [0])
            r = open_db(dd)
            for k in {key_of(i) for i in range(12)}:
                assert r.get(k) == want_state.get(k), f"WAL cut at byte {cut}: get({k!r}) = {r.get(k)!r}, expected {want_state.get(k)!r}"
            assert os.path.getsize(os.path.join(dd, "wal.log")) == good_end, (
                f"WAL cut at byte {cut}: the torn tail should be truncated to {good_end} bytes on open")
            r.put(b"new", b"x")
            r.close()
            assert open_db(dd).get(b"new") == b"x", f"WAL cut at byte {cut}: a write after recovery was lost on the next open"
        note(f"      memtable, WAL replay, and {len(cuts)} torn-tail recoveries OK")


# --- Milestone 2 -----------------------------------------------------------------------------

def m2():
    rng = random.Random(2)
    with tempfile.TemporaryDirectory() as tmp:
        # the file layout, checked by an independent reader
        d = os.path.join(tmp, "layout")
        db = open_db(d, sparse_every=4)
        ids = list(range(37))
        rng.shuffle(ids)
        for i in ids:
            db.put(key_of(i), value_of(i))
        for i in (3, 10, 36):
            db.delete(key_of(i))
        db.flush()
        assert sst_files(d) == ["sst-000001.sst"], f"flush should create sst-000001.sst; the directory holds {sst_files(d)}"
        info = read_sst(os.path.join(d, "sst-000001.sst"))
        keys = [r[0] for r in info["records"]]
        assert keys == [key_of(i) for i in range(37)], "the data region must hold every key exactly once, in sorted order"
        tomb = [r[0] for r in info["records"] if r[1] is None]
        assert tomb == [key_of(3), key_of(10), key_of(36)], "tombstones must be written to the SSTable too"
        want_index = [(r[0], r[2]) for r in info["records"]][::4]
        assert info["index"] == want_index, "the sparse index should hold (key, offset) for record 0, 4, 8, ... (sparse_every=4)"
        assert info["bloom"] == b"", "with bloom_bits_per_key=0 the bloom region must be empty"
        assert db.sst_bytes_written == info["size"], "sst_bytes_written should add the size of the file write_sstable returned"
        assert os.path.getsize(os.path.join(d, "wal.log")) == 0, "after a flush the WAL must be empty (reset it)"
        assert len(db.mem) == 0, "after a flush the memtable must be empty (replace it with a new MemTable)"
        db.flush()
        assert sst_files(d) == ["sst-000001.sst"], "flushing an empty memtable must not create a file"
        db.close()

        # reads across several tables: newest wins
        d = os.path.join(tmp, "multi")
        db = open_db(d, sparse_every=4)
        model = {}
        for rnd in range(6):
            for _ in range(60):
                k = key_of(rng.randrange(80))
                if rng.random() < 0.25:
                    db.delete(k)
                    model[k] = None
                else:
                    v = value_of(rng.randrange(1000), rnd)
                    db.put(k, v)
                    model[k] = v
            if rnd < 5:
                db.flush()                       # the sixth round stays in the memtable
        assert len(db.tables) == 5, f"expected 5 tables after 5 flushes, got {len(db.tables)}"
        for k in [key_of(i) for i in range(-3, 90)] + [b"", b"\xff" * 5]:
            assert db.get(k) == model.get(k), f"get({k!r}) = {db.get(k)!r}, expected {model.get(k)!r} (memtable first, then newest table to oldest)"
        db.close()
        db = open_db(d, sparse_every=4)          # reopen: tables must be found, in the right order
        assert len(db.tables) == 5
        for k in [key_of(i) for i in range(-3, 90)]:
            assert db.get(k) == model.get(k), f"after reopening, get({k!r}) = {db.get(k)!r}; the WAL and the tables should give {model.get(k)!r}"
        db.close()

        # a get reads one small block, not the whole table
        d = os.path.join(tmp, "blocks")
        db = open_db(d, sparse_every=8)
        for i in range(0, 1000, 2):
            db.put(key_of(i), value_of(i))
        db.flush()
        table = db.tables[0]
        table.block_reads = 0
        probes = [key_of(i) for i in range(0, 1000, 11)] + [key_of(i) for i in range(1, 1000, 13)] + [b"a", b"zzz"]
        with counting_decode() as calls:
            for k in probes:
                assert db.get(k) == (value_of(int(k[4:])) if k[4:].isdigit() and int(k[4:]) % 2 == 0 else None), f"get({k!r}) is wrong"
        assert table.block_reads <= len(probes), f"{len(probes)} gets read {table.block_reads} blocks: at most one block per get"
        assert calls[0] <= 8 * len(probes), (
            f"{len(probes)} gets decoded {calls[0]} records; with sparse_every=8 each get may decode at most 8. "
            "Use the sparse index to jump to one block and scan only that")
        db.close()

        # automatic flush when the memtable fills up
        d = os.path.join(tmp, "auto")
        db = open_db(d, memtable_limit=2000, sparse_every=8)
        model = {}
        for i in range(250):
            k = key_of(rng.randrange(5000))
            db.put(k, value_of(i))
            model[k] = value_of(i)
            assert db.mem.nbytes < 2000, "put() must flush as soon as the memtable reaches memtable_limit"
        assert len(db.tables) >= 3, f"250 writes of ~35 bytes with a 2000-byte memtable should flush at least 3 times, got {len(db.tables)}"
        assert all(db.get(k) == v for k, v in model.items()), "data is wrong after automatic flushes"
        note(f"      250 writes into a 2000-byte memtable made {len(db.tables)} SSTables automatically")
        db.close()

        # crashes in the middle of a flush
        for stage in ("sst_written", "renamed", "done"):
            d = os.path.join(tmp, "flushcrash-" + stage)
            db = open_db(d)
            model = {}
            for i in range(30):
                db.put(key_of(i), value_of(i))
                model[key_of(i)] = value_of(i)
            db.flush()
            for i in range(20, 50):
                db.put(key_of(i), value_of(i, 1))
                model[key_of(i)] = value_of(i, 1)
            db.delete(key_of(5))
            model[key_of(5)] = None

            def boom(name, stage=stage):
                if name == stage:
                    raise Crash(stage)
            try:
                db.flush(hook=boom)
            except Crash:
                pass
            else:
                raise AssertionError(f"flush() never called hook({stage!r}); call hook(name) after each step listed in its docstring")
            r = open_db(d)
            for k, v in model.items():
                assert r.get(k) == v, f"crash after {stage!r}: get({k!r}) = {r.get(k)!r}, expected {v!r}"
            assert not [n for n in os.listdir(d) if n.endswith(".tmp")], f"crash after {stage!r}: reopening should remove leftover .tmp files"
            r.flush()
            for k, v in model.items():
                assert r.get(k) == v, f"crash after {stage!r}: flushing the recovered store changed get({k!r})"
            r.close()
        note("      simulated crashes after sst_written / renamed / done lose nothing")


# --- Milestone 3 -----------------------------------------------------------------------------

def m3():
    f = mod.BloomFilter.for_keys(1000, 10)
    assert (f.num_bits, f.num_hashes) == (10000, 7), f"for_keys(1000, 10) should give 10000 bits and 7 hashes, got {(f.num_bits, f.num_hashes)}"
    g = mod.BloomFilter.for_keys(1000, 4)
    assert (g.num_bits, g.num_hashes) == (4000, 3), f"for_keys(1000, 4) should give 4000 bits and 3 hashes, got {(g.num_bits, g.num_hashes)}"
    pos = f._positions(b"hello")
    assert len(pos) == 7 and all(isinstance(p, int) and 0 <= p < 10000 for p in pos), "_positions must return k ints below num_bits"
    assert pos == f._positions(b"hello"), "_positions must be deterministic"
    # the filter has to give the same answers in every process: no Python hash()
    code = ("import sys, hashlib; sys.path.insert(0, %r); import %s as m; b = m.BloomFilter.for_keys(50, 10); "
            "[b.add(b'key%%d' %% i) for i in range(50)]; print(hashlib.md5(b.to_bytes()).hexdigest())") % (HERE, target)
    outs = []
    for seed in ("1", "2"):
        r = subprocess.run([sys.executable, "-c", code], env=dict(os.environ, PYTHONHASHSEED=seed), capture_output=True, text=True, timeout=30)
        assert r.returncode == 0, "could not run the reproducibility check: " + r.stderr.strip()[-200:]
        outs.append(r.stdout.strip())
    assert outs[0] == outs[1], "the filter's bits differ between runs: derive the positions from hashlib, not from Python's hash() (it is randomised per process)"

    n, probes = 2000, 100000
    note("      Bloom filter: observed vs predicted false-positive rate (2000 keys, 100,000 absent probes):")
    note("        bits/key   k    predicted    observed")
    for bpk in (4, 8, 10, 14):
        flt = mod.BloomFilter.for_keys(n, bpk)
        for i in range(n):
            flt.add(b"in:%d" % i)
        missing = [i for i in range(n) if not flt.might_contain(b"in:%d" % i)]
        assert not missing, f"FALSE NEGATIVE: key in:{missing[0]} was added but might_contain says no. That must never happen"
        hits = sum(flt.might_contain(b"out:%d" % i) for i in range(probes))
        observed = hits / probes
        predicted = mod.bloom_fp_formula(flt.num_bits, flt.num_hashes, n)
        note(f"        {bpk:5d}     {flt.num_hashes:2d}    {predicted * 100:8.4f}%    {observed * 100:8.4f}%")
        assert 0.6 * predicted <= observed <= 1.6 * predicted, (
            f"with {bpk} bits per key the false-positive rate should be near {predicted * 100:.3f}%, but you observed {observed * 100:.3f}% "
            "(are the k positions well spread? is every position set by add()?)")
        again = mod.BloomFilter.from_bytes(flt.to_bytes())
        assert all(again.might_contain(b"in:%d" % i) for i in range(0, n, 7)) and \
            [again.might_contain(b"out:%d" % i) for i in range(300)] == [flt.might_contain(b"out:%d" % i) for i in range(300)], (
            "from_bytes(to_bytes()) must give a filter with identical answers")

    with tempfile.TemporaryDirectory() as tmp:
        # SSTables store the filter, and a negative lookup skips the file
        rng = random.Random(3)
        present = list(range(5000))
        rng.shuffle(present)
        batches = [present[i * 1000:(i + 1) * 1000] for i in range(5)]
        probe_keys = [b"k%06d" % (2 * j + 1) for j in range(3000)]       # odd numbers: never stored

        def build(d, bpk):
            db = open_db(d, sparse_every=16, bloom_bits_per_key=bpk)
            for batch in batches:
                for i in batch:
                    db.put(b"k%06d" % (2 * i), b"value-%d" % i)
                db.flush()
            return db

        with_bloom = build(os.path.join(tmp, "bloom"), 10)
        without = build(os.path.join(tmp, "plain"), 0)
        info = read_sst(os.path.join(tmp, "bloom", "sst-000001.sst"))
        assert len(info["bloom"]) > 8, "an SSTable written with bloom_bits_per_key=10 must contain its filter bytes"
        assert read_sst(os.path.join(tmp, "plain", "sst-000001.sst"))["bloom"] == b"", "bloom_bits_per_key=0 must write no filter"
        for i in rng.sample(range(5000), 400):                           # no false negatives through the whole stack
            assert with_bloom.get(b"k%06d" % (2 * i)) == b"value-%d" % i, f"a stored key (k{2 * i:06d}) was not found: a Bloom filter must never hide a present key"
        for db in (with_bloom, without):
            for t in db.tables:
                t.block_reads = t.bloom_skips = t.bytes_read = 0
        for k in probe_keys:
            assert with_bloom.get(k) is None and without.get(k) is None, f"absent key {k!r} was found"
        s_with, s_without = with_bloom.stats(), without.stats()
        t = with_bloom.tables[0]
        predicted = mod.bloom_fp_formula(t.bloom.num_bits, t.bloom.num_hashes, 1000)
        lookups = len(probe_keys) * len(with_bloom.tables)
        observed = s_with["block_reads"] / lookups
        note(f"      {len(probe_keys)} lookups of absent keys across {len(with_bloom.tables)} SSTables ({lookups:,} table probes):")
        note(f"        without Bloom filters: {s_without['block_reads']:6d} block reads")
        note(f"        with Bloom filters:    {s_with['block_reads']:6d} block reads, {s_with['bloom_skips']:6d} files skipped")
        note(f"        observed false-positive rate {observed * 100:.3f}%   formula {predicted * 100:.3f}%")
        assert s_without["block_reads"] >= 0.9 * lookups, "internal: without filters nearly every probe should read a block"
        assert s_with["block_reads"] < 0.05 * lookups, "Bloom filters should let a negative lookup skip almost every file"
        assert s_with["bloom_skips"] + s_with["block_reads"] >= 0.9 * lookups, "every table probe should either be skipped by the filter or read a block"
        assert 0.5 * predicted <= observed <= 1.8 * predicted, (
            f"the observed false-positive rate ({observed * 100:.3f}%) is far from the formula ({predicted * 100:.3f}%)")
        with_bloom.close()
        without.close()
        # filters are loaded from disk when reopening
        r = mod.LSMTree(os.path.join(tmp, "bloom"), memtable_limit=1 << 30, sparse_every=16)
        for k in probe_keys[:500]:
            r.get(k)
        assert r.stats()["bloom_skips"] > 0.9 * 500 * 5, "after reopening, the filters (read from the files) should skip files again"
        r.close()

        # tombstones must be in the filter, or an older table's value would come back
        d = os.path.join(tmp, "tomb")
        db = open_db(d, bloom_bits_per_key=10)
        db.put(b"gone", b"old")
        db.put(b"stay", b"ok")
        db.flush()
        db.delete(b"gone")
        db.flush()
        assert db.get(b"gone") is None, "a deleted key came back from an older table: add tombstoned keys to the Bloom filter too"
        assert db.get(b"stay") == b"ok"
        db.close()


# --- Milestone 4 -----------------------------------------------------------------------------

def m4():
    # merge_newest_wins on its own
    new = [(b"a", b"A2"), (b"c", None), (b"e", b"E2")]
    mid = [(b"b", b"B1"), (b"c", b"C1"), (b"e", b"E1")]
    old = [(b"a", b"A0"), (b"c", b"C0"), (b"d", b"D0"), (b"e", None)]
    got = list(mod.merge_newest_wins([new, mid, old], drop_tombstones=True))
    assert got == [(b"a", b"A2"), (b"b", b"B1"), (b"d", b"D0"), (b"e", b"E2")], f"newest must win and tombstones hide keys; got {got}"
    got = list(mod.merge_newest_wins([iter(new), iter(mid), iter(old)], drop_tombstones=False))
    assert got == [(b"a", b"A2"), (b"b", b"B1"), (b"c", None), (b"d", b"D0"), (b"e", b"E2")], f"with drop_tombstones=False a winning tombstone is yielded as (key, None); got {got}"
    assert list(mod.merge_newest_wins([])) == [] and list(mod.merge_newest_wins([[], []])) == [], "no sources, or empty ones, give nothing"
    many = [[(b"k", b"%d" % age)] for age in range(5)]
    assert list(mod.merge_newest_wins(many)) == [(b"k", b"0")], "with 5 sources holding the same key, source 0 (the newest) wins"

    with tempfile.TemporaryDirectory() as tmp:
        rng = random.Random(4)
        d = os.path.join(tmp, "db")
        db = open_db(d, memtable_limit=2500, sparse_every=8, bloom_bits_per_key=10)
        model = {}
        for i in range(3000):
            k = key_of(rng.randrange(400))
            if rng.random() < 0.25:
                db.delete(k)
                model.pop(k, None)
            else:
                v = value_of(i, rng.randrange(9))
                db.put(k, v)
                model[k] = v
        assert len(db.tables) >= 4 and len(db.mem) > 0, "internal: expected several tables and a non-empty memtable"
        live = sorted(model.items())
        it = db.scan()
        assert iter(it) is it, "scan() must return an iterator (a generator is ideal), not a list"
        assert list(it) == live, "a full scan should equal the sorted live keys (newest value, no tombstones)"
        ranges = [(None, None), (key_of(100), key_of(200)), (key_of(399), None), (None, key_of(5)), (key_of(50), key_of(50)),
                  (key_of(200), key_of(100)), (b"", b"\xff"), (key_of(77), key_of(78)), (b"zzz", None)]
        for _ in range(25):
            a, b = sorted((key_of(rng.randrange(-5, 410)), key_of(rng.randrange(-5, 410))))
            ranges.append((a, b))
        for lo, hi in ranges:
            want = [(k, v) for k, v in live if (lo is None or k >= lo) and (hi is None or k < hi)]
            got = list(db.scan(lo, hi))
            assert got == want, f"scan({lo!r}, {hi!r}): expected {len(want)} pairs, got {len(got)} (lo is inclusive, hi exclusive)"
        db.close()

        # a narrow range reads only a few blocks per table
        d = os.path.join(tmp, "narrow")
        db = open_db(d, sparse_every=16, bloom_bits_per_key=10)
        for batch in range(4):
            for i in range(batch, 4000, 4):
                db.put(key_of(i), value_of(i, batch))
            db.flush()
        for t in db.tables:
            t.block_reads = 0
        got = list(db.scan(key_of(1500), key_of(1508)))
        assert [k for k, _ in got] == [key_of(i) for i in range(1500, 1508)], "narrow scan returned the wrong keys"
        reads = db.stats()["block_reads"]
        assert reads <= 3 * len(db.tables), (
            f"scanning 8 keys read {reads} blocks from {len(db.tables)} tables (each table holds 250 blocks): "
            "use the sparse index to start at the right block and stop at hi")
        note(f"      scan of 8 keys read {reads} blocks in total across {len(db.tables)} tables")
        # scan is lazy: pulling one pair must not read everything
        for t in db.tables:
            t.block_reads = 0
        first = next(iter(db.scan()))
        assert first == (key_of(0), value_of(0, 0)), "the first pair of a full scan is wrong"
        assert db.stats()["block_reads"] <= 2 * len(db.tables), "scan() must be lazy: asking for one pair should not read whole tables"
        db.close()


# --- Milestone 5 -----------------------------------------------------------------------------

def build_lsm(d, acct=None, seed=5):
    """Eight flushes of random puts and deletes, with a key ('zombie') that is written in the
    first table and deleted several tables later. The last round stays in the memtable."""
    rng = random.Random(seed)
    db = open_db(d, sparse_every=8, bloom_bits_per_key=10)
    touched = {b"zombie", b"survivor"}

    def do(k, v):
        if v is None:
            db.delete(k)
        else:
            db.put(k, v)
        if acct is not None:
            acct["wal"] += len(enc(k, v))
            acct["user"] += len(k) + len(v or b"")

    do(b"zombie", b"I was written first and deleted later")
    do(b"survivor", b"I stay")
    for rnd in range(9):
        for i in range(120):
            k = key_of(rng.randrange(70))
            touched.add(k)
            do(k, None if rng.random() < 0.25 else value_of(i, rnd))
        if rnd == 2:
            do(b"zombie", None)
        if rnd < 8:
            db.flush()
    assert len(db.tables) == 8 and len(db.mem) > 0
    return db, touched


def disk_bytes(d):
    return sum(os.path.getsize(os.path.join(d, n)) for n in sst_files(d))


def m5():
    with tempfile.TemporaryDirectory() as tmp:
        d = os.path.join(tmp, "db")
        acct = {"wal": 0, "user": 0}
        replaced_sizes = []
        real_replace = os.replace

        def spy(a, b):
            if str(a).endswith(".sst.tmp"):
                replaced_sizes.append(os.path.getsize(a))
            return real_replace(a, b)

        os.replace = spy
        try:
            db, touched = build_lsm(d, acct)
            wa_before = db.write_amplification()
            before = snapshot(db, touched)
            scan_before = list(db.scan())
            bytes_before, files_before = disk_bytes(d), len(sst_files(d))
            assert before[b"zombie"] is None and before[b"survivor"] == b"I stay", "internal: workload sanity"
            db.compact()
            after = snapshot(db, touched)
        finally:
            os.replace = real_replace
        assert after == before, "after compact() some values differ: " + ", ".join(repr(k) for k in sorted(touched) if after[k] != before[k])[:200]
        assert list(db.scan()) == scan_before, "after compact() a full scan returns different pairs"
        files = sst_files(d)
        assert len(files) == 1 and len(db.tables) == 1, f"compaction should leave exactly one SSTable (files: {files}, tables: {len(db.tables)})"
        bytes_after = disk_bytes(d)
        assert bytes_after < bytes_before, f"compaction should shrink the SSTables: {bytes_before} bytes became {bytes_after}"
        info = read_sst(os.path.join(d, files[0]))
        assert all(r[1] is not None for r in info["records"]), "the compacted table must not contain tombstones"
        keys = [r[0] for r in info["records"]]
        assert keys == sorted(set(keys)), "the compacted table must hold each key once, in order"
        assert b"zombie" not in keys, "the deleted key 'zombie' must be gone from the compacted table"
        assert not [n for n in os.listdir(d) if n.endswith(".tmp")], "no .tmp files may be left behind"
        # write amplification accounting
        assert db.wal.bytes_written == acct["wal"], f"WAL bytes written: expected {acct['wal']}, got {db.wal.bytes_written}"
        assert db.user_bytes == acct["user"], "user_bytes should count len(key)+len(value) of every put/delete"
        assert db.sst_bytes_written == sum(replaced_sizes), (
            f"sst_bytes_written should be the total size of every SSTable you wrote (flushes AND the compaction): "
            f"expected {sum(replaced_sizes)}, got {db.sst_bytes_written}")
        wa_after = db.write_amplification()
        assert wa_after > wa_before, "compaction rewrites data, so write amplification must go up"
        note(f"      {files_before} SSTables, {bytes_before:,} bytes  ->  1 SSTable, {bytes_after:,} bytes "
             f"({100 * (1 - bytes_after / bytes_before):.0f}% smaller)")
        note(f"      user data {db.user_bytes:,} bytes; written to disk {db.wal.bytes_written + db.sst_bytes_written:,} bytes")
        note(f"      write amplification: {wa_before:.2f} before compaction (WAL + flushes), {wa_after:.2f} after")
        # still correct after more writes, a flush, a reopen and a second compaction
        db.put(b"after", b"compaction")
        db.delete(b"survivor")
        db.put(key_of(3), b"changed")
        expect = dict(after)
        expect.update({b"after": b"compaction", b"survivor": None, key_of(3): b"changed"})
        assert snapshot(db, expect) == expect, "writes after a compaction misbehave"
        db.flush()
        db.close()
        r = open_db(d, sparse_every=8, bloom_bits_per_key=10)
        assert snapshot(r, expect) == expect, "after compaction and a reopen, the data differs"
        r.compact()
        assert snapshot(r, expect) == expect and len(r.tables) == 1, "a second compaction changed the data"
        r.close()

        # a single table, and all-deleted data
        one = open_db(os.path.join(tmp, "one"))
        one.put(b"a", b"1")
        one.flush()
        one.compact()
        assert one.get(b"a") == b"1" and len(one.tables) == 1, "compact() with one table should leave things alone"
        one.close()
        gone = open_db(os.path.join(tmp, "gone"))
        for rnd in range(3):
            for i in range(10):
                gone.put(key_of(i), b"x%d" % rnd)
            gone.flush()
        for i in range(10):
            gone.delete(key_of(i))
        gone.flush()
        gone.compact()
        assert all(gone.get(key_of(i)) is None for i in range(10)) and list(gone.scan()) == [], "everything was deleted: nothing may come back"
        assert sst_files(os.path.join(tmp, "gone")) == [], "when the merge result is empty there is nothing to write: no SSTable should remain"
        gone.close()

        # crash at every stage of the swap, then reopen
        for stage in ("tmp_written", "replaced", "deleted_1", "done"):
            d = os.path.join(tmp, "crash-" + stage)
            db, touched = build_lsm(d)
            want = snapshot(db, touched)

            def boom(name, stage=stage):
                if name == stage:
                    raise Crash(stage)
            try:
                db.compact(hook=boom)
            except Crash:
                pass
            else:
                raise AssertionError(f"compact() never called hook({stage!r}); call hook(name) at each step listed in the docstring")
            db.close()
            r = open_db(d, sparse_every=8, bloom_bits_per_key=10)
            got = snapshot(r, touched)
            bad = [k for k in sorted(touched) if got[k] != want[k]]
            if bad:
                extra = " (the deleted key came back to life: delete the old tables OLDEST first, so a tombstone is never removed while an older value it hides still exists)" if bad[0] == b"zombie" else ""
                raise AssertionError(f"crash after {stage!r}: {len(bad)} keys changed after reopening, e.g. {bad[0]!r}{extra}")
            r.compact()
            assert snapshot(r, touched) == want, f"crash after {stage!r}: compacting the recovered store changed the data"
            r.close()
        note("      simulated crashes after tmp_written / replaced / deleted_1 / done all recovered the same data")


print(f"Lab 2 checks against {target}.py\n")
check("Milestone 1: memtable and write-ahead log (replay on open)", m1)
check("Milestone 2: flush to an SSTable; sparse-index reads", m2)
check("Milestone 3: Bloom filters skip files", m3)
check("Milestone 4: range scans with a k-way merge", m4)
check("Milestone 5: compaction and write amplification", m5)
passed = sum(results)
print(f"\n{passed}/{len(results)} milestones passing" + ("  🎉 Lab complete!" if passed == len(results) else ""))
sys.exit(0 if passed == len(results) else 1)
