"""Lab 2 starter: a small LSM tree (memtable + WAL + SSTables + Bloom filters + compaction).

Directory layout:
    wal.log              the write-ahead log of the current memtable
    sst-000001.sst ...   immutable sorted files; a higher number is newer

Records (WAL and SSTable data blocks) use the same format as Lab 1, all big-endian:

    +---------+---------+---------+------------+--------------+
    | crc32   | key len | val len | key        | value        |
    +---------+---------+---------+------------+--------------+
    val len = -1 is a tombstone. crc32 covers everything after itself.

Fill in every TODO, one milestone at a time, and run `python3 check.py`
after each one. The lab page walks you through it.

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
        """Store value (None = tombstone) under key. Keep self.nbytes equal to the sum of
        len(key) + len(value or b"") over the current entries (an overwrite replaces the old size)."""
        raise NotImplementedError("TODO milestone 1: MemTable.put")

    def delete(self, key):
        """A delete is a write of a tombstone."""
        raise NotImplementedError("TODO milestone 1: MemTable.delete")

    def get(self, key):
        """The value, None if the key is deleted here (tombstone), or MISSING if unknown."""
        raise NotImplementedError("TODO milestone 1: MemTable.get")

    def items(self):
        """Every entry, tombstones included, as a list of (key, value) sorted by key."""
        raise NotImplementedError("TODO milestone 1: MemTable.items")

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
        """Append one record to the log with write_all. Add its length to self.bytes_written.
        If self.sync is set, os.fsync(self._fd) afterwards."""
        raise NotImplementedError("TODO milestone 1: WAL.append")

    def reset(self):
        """Forget everything: the memtable it protected is now safe in an SSTable. (Given.)"""
        os.ftruncate(self._fd, 0)
        os.fsync(self._fd)

    def close(self):
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None


def replay_wal(path):
    """Read a WAL file. Return (records, good_end): the (key, value) pairs of the valid
    prefix, oldest first, and the byte offset where that prefix ends.
    A missing file is ([], 0). Stop at the first record decode_record rejects."""
    raise NotImplementedError("TODO milestone 1: replay_wal")


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
        """Size a filter for n_keys keys: m = max(8, n_keys * bits_per_key) bits and
        k = max(1, round(bits_per_key * ln 2)) hash functions. Return cls(m, k)."""
        raise NotImplementedError("TODO milestone 3: BloomFilter.for_keys")

    def _positions(self, key):
        """Return the k bit positions (each in range(self.num_bits)) for key.
        Derive them from hashlib, e.g. one sha256 digest split into h1 and h2 and
        position_i = (h1 + i * h2) % num_bits. NOT Python's hash(): it changes between runs."""
        raise NotImplementedError("TODO milestone 3: BloomFilter._positions")

    def add(self, key):
        """Set the key's k bits in self.bits (a bytearray; bit p is bit p & 7 of byte p >> 3)."""
        raise NotImplementedError("TODO milestone 3: BloomFilter.add")

    def might_contain(self, key):
        """False means DEFINITELY not added. True means maybe."""
        raise NotImplementedError("TODO milestone 3: BloomFilter.might_contain")

    def to_bytes(self):
        """num_bits and num_hashes (two big-endian u32) followed by the bit array."""
        raise NotImplementedError("TODO milestone 3: BloomFilter.to_bytes")

    @classmethod
    def from_bytes(cls, data):
        """The inverse of to_bytes."""
        raise NotImplementedError("TODO milestone 3: BloomFilter.from_bytes")


# ---------------------------------------------------------------------------
# Milestone 2: writing and reading SSTables
# ---------------------------------------------------------------------------

def write_sstable(path, items, sparse_every=16, bloom_bits_per_key=0):
    """Write sorted (key, value) items (value None = tombstone) as an SSTable file at `path`.

    Layout (see the module docstring): data records, sparse index (an entry for record 0,
    sparse_every, 2*sparse_every, ...), bloom filter, footer.
      * Milestone 2: leave the bloom region empty (bloom offset == footer offset).
      * Milestone 3: if bloom_bits_per_key > 0, build a BloomFilter over EVERY key (tombstoned
        keys too) and store its to_bytes() in the bloom region.
    fsync the file before returning. Return the file's size in bytes.
    """
    raise NotImplementedError("TODO milestone 2: write_sstable")


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
        """The value, None if this table holds a tombstone for key, or MISSING.

        Milestone 2: bisect.bisect_right(self.index_keys, key) - 1 is the block that could hold
        key (-1 means key sorts before the whole table). Read that block with self._read_block(i),
        walk its records with decode_record, stop when you find the key or pass it.
        Milestone 3: first ask self.bloom (if there is one). On "definitely not", add 1 to
        self.bloom_skips and return MISSING without reading anything.
        """
        raise NotImplementedError("TODO milestone 2: SSTable.get")

    def scan(self, lo=None, hi=None):
        """Yield (key, value) in key order for lo <= key < hi (None = unbounded). Value None =
        tombstone. Use the sparse index to start at the right block and read block by block
        (self._read_block(i)); stop as soon as you pass hi, without reading further blocks."""
        raise NotImplementedError("TODO milestone 4: SSTable.scan")


# ---------------------------------------------------------------------------
# Milestone 4: merging sorted sources
# ---------------------------------------------------------------------------

def _tagged(source, age):
    for key, value in source:
        yield key, age, value


def merge_newest_wins(sources, drop_tombstones=True):
    """Merge sorted (key, value) iterables into one sorted stream.

    `sources` are ordered NEWEST FIRST. When several sources have the same key, only the
    newest one's entry counts. If drop_tombstones, a winning tombstone is not yielded at all
    (it hides the key); otherwise it is yielded with value None.

    Hint: tag each entry (key, age, value) with its source's position and give the tagged
    streams to heapq.merge: ties on key then come out newest first. Beware of building the
    generators in a loop with a closure over the loop variable: use a helper function.
    """
    raise NotImplementedError("TODO milestone 4: merge_newest_wins")


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
        """Milestone 1: append to the WAL FIRST, then update the memtable.
        Milestone 2: afterwards, if self.mem.nbytes >= self.memtable_limit, call self.flush()."""
        raise NotImplementedError("TODO milestone 1: LSMTree._write")

    def _recover_wal(self):
        """Milestone 1: replay wal.log into self.mem with replay_wal(); if the file has bytes
        past good_end (a torn tail), truncate it to good_end and fsync. (Only called when
        the file exists and is not empty.)"""
        raise NotImplementedError("TODO milestone 1: LSMTree._recover_wal")

    # -- reads ----------------------------------------------------------------
    def get(self, key):
        """Return the newest value for key, or None if it is absent or deleted.

        Milestone 1: the memtable only (a tombstone there means None).
        Milestone 2: if the memtable does not know the key (MISSING), ask self.tables, which is
        ordered NEWEST FIRST; the first answer that is not MISSING wins, and None (a tombstone) is an answer.
        """
        raise NotImplementedError("TODO milestone 1: LSMTree.get")

    def scan(self, lo=None, hi=None):
        """Milestone 4: return an iterator of live (key, value) pairs with lo <= key < hi, in
        key order. Sources, newest first: self.mem.range(lo, hi), then each table's scan(lo, hi)."""
        raise NotImplementedError("TODO milestone 4: LSMTree.scan")

    # -- flush ----------------------------------------------------------------
    def flush(self, hook=None):
        """Milestone 2: write the memtable out as a new SSTable, then empty it and the WAL.

        Steps, in this order (hook(stage), if given, is called after each; tests raise from it):
          1. items = self.mem.items(); do nothing if there are none.
          2. final = self._sst_path(self.next_id); write_sstable(final + ".tmp", ...) and add
             the returned size to self.sst_bytes_written.            -> hook("sst_written")
          3. os.replace(tmp, final); fsync_dir(self.dir)             -> hook("renamed")
          4. self.tables.insert(0, SSTable(final)); self.next_id += 1; self.mem = MemTable();
             self.wal.reset()  (only now is the WAL no longer needed)  -> hook("done")
        """
        raise NotImplementedError("TODO milestone 2: LSMTree.flush")

    # -- compaction -------------------------------------------------------------
    def compact(self, hook=None):
        """Milestone 5: merge ALL SSTables into one; shadowed values and tombstones disappear.

        Do nothing if there are fewer than 2 tables. Otherwise:
          1. merged = merge_newest_wins([t.scan() for t in self.tables], drop_tombstones=True)
          2. out_id = self.next_id (then next_id += 1): higher than every input.
          3. write_sstable(final + ".tmp", merged, ...) and add its size to self.sst_bytes_written
                                                                     -> hook("tmp_written")
          4. os.replace(tmp, final); fsync_dir(self.dir)             -> hook("replaced")
          5. self.tables = [SSTable(final)]
          6. close and os.remove the old tables, OLDEST FIRST. After the first one -> hook("deleted_1")
          7. fsync_dir(self.dir)                                     -> hook("done")
        (If everything was deleted, the merge is empty: write no file, just remove the inputs.)
        """
        raise NotImplementedError("TODO milestone 5: LSMTree.compact")

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
