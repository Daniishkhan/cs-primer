"""Lab 2 solution: a small LSM tree (memtable + WAL + SSTables + Bloom filters + compaction).

Directory layout:
    wal.log              the write-ahead log of the current memtable
    sst-000001.sst ...   immutable sorted files; a higher number is newer

Records (WAL and SSTable data blocks) use the same format as Lab 1, all big-endian:

    +---------+---------+---------+------------+--------------+
    | crc32   | key len | val len | key        | value        |
    +---------+---------+---------+------------+--------------+
    val len = -1 is a tombstone. crc32 covers everything after itself.

An SSTable file:

    [ data: records in key order ][ sparse index ][ bloom filter ][ footer ]

    sparse index: u32 count, then for every Nth record: u32 key len, u64 offset, key
    footer (36 bytes): magic "LSMSST01", u64 index offset, u64 bloom offset,
                       u64 record count, u32 crc32 of the previous 32 bytes
"""
import bisect
import hashlib
import heapq
import math
import os
import re
import struct
import zlib

HEADER = struct.Struct(">IIi")          # crc32, key length, value length (-1 = tombstone)
MAX_KEY = 1 << 16
MAX_VALUE = 1 << 28
MAGIC = b"LSMSST01"
FOOTER = struct.Struct(">8sQQQI")       # magic, index offset, bloom offset, record count, crc32
SST_RE = re.compile(r"^sst-(\d{6})\.sst$")

MISSING = object()                      # "this structure knows nothing about the key"
                                        # (different from None, which means "deleted")


class CorruptionError(Exception):
    pass


def write_all(fd, data):
    """os.write may write less than asked; loop until everything is written. (Given.)"""
    view = memoryview(data)
    while view:
        n = os.write(fd, view)
        view = view[n:]


def fsync_dir(path):
    """Make renames and deletions in a directory durable (POSIX; skipped elsewhere). (Given.)"""
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def encode_record(key, value):
    """(Given, same as Lab 1.) value=None encodes a tombstone."""
    vlen = -1 if value is None else len(value)
    body = struct.pack(">Ii", len(key), vlen) + key + (value or b"")
    return struct.pack(">I", zlib.crc32(body)) + body


def decode_record(buf, pos=0):
    """(Given, same as Lab 1.) Returns (key, value, next_pos) or None if torn or corrupt."""
    if pos + HEADER.size > len(buf):
        return None
    crc, klen, vlen = HEADER.unpack_from(buf, pos)
    if klen > MAX_KEY or vlen < -1 or vlen > MAX_VALUE:
        return None
    key_start = pos + HEADER.size
    val_start = key_start + klen
    end = val_start + max(vlen, 0)
    if end > len(buf) or zlib.crc32(buf[pos + 4:end]) != crc:
        return None
    return bytes(buf[key_start:val_start]), (None if vlen == -1 else bytes(buf[val_start:end])), end


# ---------------------------------------------------------------------------
# Milestone 1: the memtable and the write-ahead log
# ---------------------------------------------------------------------------

class MemTable:
    """Recent writes, in memory. A dict, sorted only when we need order.

    Trade-off: a dict gives O(1) put/get and pays O(n log n) to sort once per
    flush or scan. A sorted list with bisect.insort keeps order all the time
    but every insert shifts O(n) items. Real engines use a skip list or a tree
    (O(log n) for both).
    """

    def __init__(self):
        self._d = {}                    # key -> value, or None for a tombstone
        self.nbytes = 0                 # sum of len(key) + len(value or b"") over the entries

    def put(self, key, value):
        old = self._d.get(key, MISSING)
        if old is not MISSING:
            self.nbytes -= len(key) + len(old or b"")
        self._d[key] = value
        self.nbytes += len(key) + len(value or b"")

    def delete(self, key):
        self.put(key, None)             # a delete is a write of a tombstone

    def get(self, key):
        """The value, None if the key is deleted here (tombstone), or MISSING."""
        return self._d.get(key, MISSING)

    def items(self):
        """Every entry, tombstones included, as a list of (key, value) sorted by key."""
        return sorted(self._d.items())

    def range(self, lo=None, hi=None):
        """(Given.) Entries with lo <= key < hi, sorted."""
        return [(k, v) for k, v in self.items() if (lo is None or k >= lo) and (hi is None or k < hi)]

    def __len__(self):
        return len(self._d)


class WAL:
    """The write-ahead log: every write is appended here BEFORE it enters the memtable."""

    def __init__(self, path, sync=False):
        self.path = path
        self.sync = sync
        self.bytes_written = 0          # cumulative, for write-amplification accounting
        self._fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_BINARY", 0), 0o644)

    def append(self, key, value):
        rec = encode_record(key, value)
        write_all(self._fd, rec)
        if self.sync:
            os.fsync(self._fd)
        self.bytes_written += len(rec)

    def reset(self):
        """Forget everything: the memtable it protected is now safe in an SSTable. (Given.)"""
        os.ftruncate(self._fd, 0)
        os.fsync(self._fd)

    def close(self):
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None


def replay_wal(path):
    """Read a WAL file. Returns (records, good_end): the (key, value) pairs of the valid
    prefix, oldest first, and the byte offset where that prefix ends."""
    if not os.path.exists(path):
        return [], 0
    with open(path, "rb") as f:
        data = f.read()
    records, pos = [], 0
    while pos < len(data):
        rec = decode_record(data, pos)
        if rec is None:
            break                       # torn or corrupt tail: stop here
        key, value, pos = rec
        records.append((key, value))
    return records, pos


# ---------------------------------------------------------------------------
# Milestone 3: the Bloom filter
# ---------------------------------------------------------------------------

def bloom_fp_formula(num_bits, num_hashes, n_keys):
    """(Given.) The textbook false-positive rate: (1 - e^(-k n / m)) ^ k."""
    return (1 - math.exp(-num_hashes * n_keys / num_bits)) ** num_hashes


class BloomFilter:
    def __init__(self, num_bits, num_hashes, bits=None):
        self.num_bits = num_bits
        self.num_hashes = num_hashes
        self.bits = bits if bits is not None else bytearray((num_bits + 7) // 8)

    @classmethod
    def for_keys(cls, n_keys, bits_per_key=10):
        """Size a filter for n_keys keys: m = n * bits_per_key bits, k = round(bits_per_key * ln 2)."""
        return cls(max(8, n_keys * bits_per_key), max(1, round(bits_per_key * math.log(2))))

    def _positions(self, key):
        """k bit positions from ONE sha256 digest (double hashing: h1 + i * h2).
        Not Python's hash(): that changes from run to run, and the filter lives on disk."""
        digest = hashlib.sha256(key).digest()
        h1 = int.from_bytes(digest[:8], "big")
        h2 = int.from_bytes(digest[8:16], "big") | 1        # odd, so it never gets stuck
        return [(h1 + i * h2) % self.num_bits for i in range(self.num_hashes)]

    def add(self, key):
        for p in self._positions(key):
            self.bits[p >> 3] |= 1 << (p & 7)

    def might_contain(self, key):
        """False means DEFINITELY not added. True means maybe."""
        return all(self.bits[p >> 3] & (1 << (p & 7)) for p in self._positions(key))

    def to_bytes(self):
        return struct.pack(">II", self.num_bits, self.num_hashes) + bytes(self.bits)

    @classmethod
    def from_bytes(cls, data):
        num_bits, num_hashes = struct.unpack_from(">II", data, 0)
        return cls(num_bits, num_hashes, bytearray(data[8:]))


# ---------------------------------------------------------------------------
# Milestone 2: writing and reading SSTables
# ---------------------------------------------------------------------------

def write_sstable(path, items, sparse_every=16, bloom_bits_per_key=0):
    """Write sorted (key, value) items (value None = tombstone) as an SSTable file.

    Layout: data records, sparse index (every sparse_every-th record), bloom filter
    (empty if bloom_bits_per_key is 0), footer. fsyncs the file. Returns its size in bytes.
    """
    items = list(items)
    data, index, offset = [], [], 0
    for i, (key, value) in enumerate(items):
        if i % sparse_every == 0:
            index.append((key, offset))
        rec = encode_record(key, value)
        data.append(rec)
        offset += len(rec)
    index_blob = struct.pack(">I", len(index)) + b"".join(struct.pack(">IQ", len(k), off) + k for k, off in index)
    bloom_blob = b""
    if bloom_bits_per_key and items:
        bloom = BloomFilter.for_keys(len(items), bloom_bits_per_key)
        for key, _ in items:                    # tombstoned keys too: they must shadow older tables
            bloom.add(key)
        bloom_blob = bloom.to_bytes()
    index_offset = offset
    bloom_offset = index_offset + len(index_blob)
    head = struct.pack(">8sQQQ", MAGIC, index_offset, bloom_offset, len(items))
    footer = head + struct.pack(">I", zlib.crc32(head))
    blob = b"".join(data) + index_blob + bloom_blob + footer
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_BINARY", 0), 0o644)
    try:
        write_all(fd, blob)
        os.fsync(fd)                            # durable before anybody renames it into place
    finally:
        os.close(fd)
    return len(blob)


class SSTable:
    """Read side of an SSTable. Loads the sparse index (and Bloom filter) into memory."""

    def __init__(self, path):
        self.path = path
        self._f = open(path, "rb")
        self.size = os.fstat(self._f.fileno()).st_size
        self._f.seek(self.size - FOOTER.size)
        raw = self._f.read(FOOTER.size)
        magic, index_off, bloom_off, count, crc = FOOTER.unpack(raw)
        if magic != MAGIC or crc != zlib.crc32(raw[:-4]):
            raise CorruptionError("%s has a bad footer" % path)
        self.data_end = index_off
        self.count = count
        self._f.seek(index_off)
        index_blob = self._f.read(bloom_off - index_off)
        n, = struct.unpack_from(">I", index_blob, 0)
        pos, self.index_keys, self.index_offsets = 4, [], []
        for _ in range(n):
            klen, off = struct.unpack_from(">IQ", index_blob, pos)
            pos += 12
            self.index_keys.append(index_blob[pos:pos + klen])
            self.index_offsets.append(off)
            pos += klen
        self._f.seek(bloom_off)
        bloom_blob = self._f.read(self.size - FOOTER.size - bloom_off)
        self.bloom = BloomFilter.from_bytes(bloom_blob) if bloom_blob else None
        self.block_reads = 0                    # counters for the experiments
        self.bytes_read = 0
        self.bloom_skips = 0

    def close(self):
        self._f.close()

    def _read_block(self, i):
        """(Given.) The bytes of block i: from index entry i up to index entry i+1 (or the end of the data)."""
        start = self.index_offsets[i]
        end = self.index_offsets[i + 1] if i + 1 < len(self.index_offsets) else self.data_end
        self._f.seek(start)
        block = self._f.read(end - start)
        self.block_reads += 1
        self.bytes_read += len(block)
        return block

    def get(self, key):
        """The value, None if this table holds a tombstone for key, or MISSING."""
        if self.bloom is not None and not self.bloom.might_contain(key):      # Milestone 3
            self.bloom_skips += 1
            return MISSING
        i = bisect.bisect_right(self.index_keys, key) - 1     # last block starting at or before key
        if i < 0:
            return MISSING                                    # smaller than the table's first key
        block = self._read_block(i)
        pos = 0
        while pos < len(block):
            rec = decode_record(block, pos)
            if rec is None:
                raise CorruptionError("bad record in %s" % self.path)
            k, v, pos = rec
            if k == key:
                return v
            if k > key:
                break                                         # sorted: it would have been here
        return MISSING

    def scan(self, lo=None, hi=None):
        """Yield (key, value) in key order for lo <= key < hi. Value None = tombstone."""
        i = 0 if lo is None else max(bisect.bisect_right(self.index_keys, lo) - 1, 0)
        while i < len(self.index_keys):
            if hi is not None and self.index_keys[i] >= hi:
                return                                        # this block starts past the range
            block = self._read_block(i)
            pos = 0
            while pos < len(block):
                k, v, pos = decode_record(block, pos)
                if lo is not None and k < lo:
                    continue
                if hi is not None and k >= hi:
                    return
                yield k, v
            i += 1


# ---------------------------------------------------------------------------
# Milestone 4: merging sorted sources
# ---------------------------------------------------------------------------

def _tagged(source, age):
    for key, value in source:
        yield key, age, value


def merge_newest_wins(sources, drop_tombstones=True):
    """Merge sorted (key, value) iterables into one sorted stream.

    `sources` are ordered NEWEST FIRST. When several sources have the same key, only the
    newest one's entry is yielded. If drop_tombstones, a winning tombstone is not yielded
    at all (it hides the key); otherwise it is yielded with value None.
    """
    last = None
    merged = heapq.merge(*[_tagged(src, age) for age, src in enumerate(sources)])
    for key, age, value in merged:             # ties on key are ordered by age: newest first
        if key == last:
            continue                           # an older version of a key we already decided
        last = key
        if value is None and drop_tombstones:
            continue
        yield key, value


# ---------------------------------------------------------------------------
# The tree
# ---------------------------------------------------------------------------

class LSMTree:
    def __init__(self, directory, memtable_limit=64 * 1024, sparse_every=16, bloom_bits_per_key=10, sync=False):
        self.dir = directory
        self.memtable_limit = memtable_limit
        self.sparse_every = sparse_every
        self.bloom_bits_per_key = bloom_bits_per_key
        self.user_bytes = 0                 # bytes the caller asked us to store
        self.sst_bytes_written = 0          # bytes we wrote into SSTable files (flushes + compactions)
        os.makedirs(directory, exist_ok=True)
        for name in os.listdir(directory):  # half-written files from a crash
            if name.endswith(".tmp"):
                os.remove(os.path.join(directory, name))
        ids = sorted(int(m.group(1)) for m in map(SST_RE.match, os.listdir(directory)) if m)
        self.tables = [SSTable(self._sst_path(i)) for i in reversed(ids)]       # NEWEST FIRST
        self.next_id = (ids[-1] + 1) if ids else 1
        self.mem = MemTable()
        self._wal_path = os.path.join(directory, "wal.log")
        if os.path.exists(self._wal_path) and os.path.getsize(self._wal_path) > 0:
            self._recover_wal()             # Milestone 1
        self.wal = WAL(self._wal_path, sync=sync)

    def _sst_path(self, sst_id):
        return os.path.join(self.dir, "sst-%06d.sst" % sst_id)

    # -- writes ---------------------------------------------------------------
    def put(self, key, value):
        if value is None:
            raise ValueError("use delete() to remove a key")
        self.user_bytes += len(key) + len(value)
        self._write(key, value)

    def delete(self, key):
        self.user_bytes += len(key)
        self._write(key, None)

    def _write(self, key, value):
        """Milestone 1: log first, then the memtable. Milestone 2: flush when it is full."""
        self.wal.append(key, value)
        self.mem.put(key, value)
        if self.mem.nbytes >= self.memtable_limit:
            self.flush()

    def _recover_wal(self):
        """Milestone 1: replay wal.log into the memtable; cut a torn tail off the file."""
        records, good_end = replay_wal(self._wal_path)
        for key, value in records:
            self.mem.put(key, value)
        if good_end < os.path.getsize(self._wal_path):
            with open(self._wal_path, "r+b") as f:
                f.truncate(good_end)
                f.flush()
                os.fsync(f.fileno())

    # -- reads ----------------------------------------------------------------
    def get(self, key):
        """Memtable first, then SSTables from newest to oldest. The first answer wins;
        a tombstone is an answer (None)."""
        value = self.mem.get(key)
        if value is not MISSING:
            return value
        for table in self.tables:
            value = table.get(key)
            if value is not MISSING:
                return value
        return None

    def scan(self, lo=None, hi=None):
        """Milestone 4: yield live (key, value) pairs with lo <= key < hi, in key order."""
        sources = [iter(self.mem.range(lo, hi))] + [t.scan(lo, hi) for t in self.tables]
        return merge_newest_wins(sources, drop_tombstones=True)

    # -- flush ----------------------------------------------------------------
    def flush(self, hook=None):
        """Milestone 2: write the memtable out as a new SSTable, then empty it and the WAL.

        Order matters: write temp file + fsync -> rename -> fsync directory -> reset WAL.
        hook(stage) is called after each step so tests can "crash" there.
        """
        def step(name):
            if hook:
                hook(name)

        items = self.mem.items()
        if not items:
            return
        final = self._sst_path(self.next_id)
        tmp = final + ".tmp"
        self.sst_bytes_written += write_sstable(tmp, items, self.sparse_every, self.bloom_bits_per_key)
        step("sst_written")
        os.replace(tmp, final)
        fsync_dir(self.dir)
        step("renamed")
        self.tables.insert(0, SSTable(final))
        self.next_id += 1
        self.mem = MemTable()
        self.wal.reset()                    # only now: the data is safe in the SSTable
        step("done")

    # -- compaction -------------------------------------------------------------
    def compact(self, hook=None):
        """Milestone 5: merge ALL SSTables into one; shadowed values and tombstones disappear."""
        def step(name):
            if hook:
                hook(name)

        if len(self.tables) < 2:
            return
        inputs = list(self.tables)                              # newest first
        merged = list(merge_newest_wins([t.scan() for t in inputs], drop_tombstones=True))
        out_id = self.next_id                                   # higher than every input
        self.next_id += 1
        final, new_table = self._sst_path(out_id), None
        if merged:
            tmp = final + ".tmp"
            self.sst_bytes_written += write_sstable(tmp, merged, self.sparse_every, self.bloom_bits_per_key)
            step("tmp_written")
            os.replace(tmp, final)
            fsync_dir(self.dir)
            step("replaced")
            new_table = SSTable(final)
        else:
            step("tmp_written")
            step("replaced")
        self.tables = [new_table] if new_table else []         # reads switch to the merged file
        for n, table in enumerate(reversed(inputs)):            # delete OLDEST first
            table.close()
            os.remove(table.path)
            if n == 0:
                step("deleted_1")
        fsync_dir(self.dir)
        step("done")

    # -- reporting (given) --------------------------------------------------------
    def stats(self):
        return {
            "tables": len(self.tables),
            "block_reads": sum(t.block_reads for t in self.tables),
            "bloom_skips": sum(t.bloom_skips for t in self.tables),
            "bytes_read": sum(t.bytes_read for t in self.tables),
        }

    def write_amplification(self):
        """Bytes written to disk (WAL + SSTables) divided by bytes the user asked to store."""
        return (self.wal.bytes_written + self.sst_bytes_written) / max(1, self.user_bytes)

    def close(self):
        self.wal.close()
        for t in self.tables:
            t.close()
