"""Lab 1 starter: a log-structured key-value store (a small Bitcask).

Fill in every TODO, one milestone at a time, and run `python3 check.py`
after each one. The lab page walks you through it.

Record format on disk (all integers big-endian):

    +---------+---------+---------+------------+--------------+
    | crc32   | key len | val len | key        | value        |
    | 4 bytes | 4 bytes | 4 bytes | klen bytes | vlen bytes   |
    +---------+---------+---------+------------+--------------+

    * val len is a SIGNED integer: -1 means "tombstone" (the key is deleted)
      and no value bytes follow. A val len of 0 is an ordinary empty value.
    * crc32 covers everything after it: key len, val len, key and value.

Files: one directory, segments named seg-000001.log, seg-000002.log, ...
Only the highest-numbered segment (the "active" one) is ever written to.
Keys and values are bytes.
"""
import os
import re
import struct
import zlib

HEADER = struct.Struct(">IIi")         # crc32, key length, value length (-1 = tombstone)
MAX_KEY = 1 << 16                      # a key length above this is certainly garbage
MAX_VALUE = 1 << 28                    # ... and so is a value length above this
SEG_RE = re.compile(r"^seg-(\d{6})\.log$")


class CorruptionError(Exception):
    """A sealed (finished) segment is damaged. That is not a crash artifact."""


def write_all(fd, data):
    """os.write may write less than asked; loop until everything is written. (Given.)"""
    view = memoryview(data)
    while view:
        n = os.write(fd, view)
        view = view[n:]


# ---------------------------------------------------------------------------
# Milestone 1: the record format, and the slow store that scans the file
# ---------------------------------------------------------------------------

def encode_record(key, value):
    """Return the bytes of one record. value=None encodes a tombstone (value length -1).

    Hint: build everything after the checksum first (key length, value length,
    key, value), then put zlib.crc32 of that in front.
    """
    raise NotImplementedError("TODO milestone 1: encode_record")


def decode_record(buf, pos=0):
    """Parse one record at buf[pos:].

    Return (key, value, next_pos), where value is None for a tombstone.
    Return None if the record is incomplete or fails its checksum.
    Never raise on garbage, and check every length against len(buf) BEFORE using it
    (also reject lengths above MAX_KEY / MAX_VALUE, and a value length below -1).
    """
    raise NotImplementedError("TODO milestone 1: decode_record")


class ScanStore:
    """The slow version: one file, and every get() scans it from the start."""

    def __init__(self, path):
        self.path = path
        open(path, "ab").close()                       # make sure the file exists (given)

    def put(self, key, value):
        """Append one record for (key, value) to the file."""
        raise NotImplementedError("TODO milestone 1: ScanStore.put")

    def get(self, key):
        """Read the whole file, walk the records with decode_record, return the LAST value for key
        (None if the key never appears)."""
        raise NotImplementedError("TODO milestone 1: ScanStore.get")


# ---------------------------------------------------------------------------
# Milestone 4 helper: parse a whole segment
# ---------------------------------------------------------------------------

def scan_segment(data):
    """Parse bytes as a run of records, using decode_record.

    Return (entries, good_end). entries is a list of
    (key, offset, size, is_tombstone), oldest first. good_end is the byte
    offset where the valid prefix ends (len(data) for a healthy segment).
    Stop at the first record that decode_record rejects.
    """
    raise NotImplementedError("TODO milestone 4: scan_segment")


# ---------------------------------------------------------------------------
# The store
# ---------------------------------------------------------------------------

class Store:
    def __init__(self, directory, max_segment_bytes=1 << 20, sync=False, hints=False):
        self.dir = directory
        self.max_segment_bytes = max_segment_bytes
        self.sync = sync                    # fsync after every write?
        self.hints = hints                  # Milestone 6
        self.index = {}                     # key -> (segment id, offset, record size)
        self._readers = {}                  # segment id -> open file, for reads
        self._fd = None                     # file descriptor of the active segment
        self.active_id = 1
        self._active_size = 0
        os.makedirs(directory, exist_ok=True)
        for name in os.listdir(directory):  # a crashed compaction can leave temp files
            if name.endswith(".tmp"):
                os.remove(os.path.join(directory, name))
        ids = self.segment_ids()
        if ids:
            self._rebuild_index(ids)        # Milestone 4 (only runs when files already exist)
        self._start_segment(ids[-1] if ids else 1)

    # -- helpers (given) ---------------------------------------------------
    def _seg_path(self, seg_id):
        return os.path.join(self.dir, "seg-%06d.log" % seg_id)

    def _hint_path(self, seg_id):
        return os.path.join(self.dir, "seg-%06d.hint" % seg_id)

    def segment_ids(self):
        """Ids of every segment file, oldest first."""
        ids = []
        for name in os.listdir(self.dir):
            m = SEG_RE.match(name)
            if m:
                ids.append(int(m.group(1)))
        return sorted(ids)

    def total_bytes(self):
        return sum(os.path.getsize(self._seg_path(i)) for i in self.segment_ids())

    def _reader(self, seg_id):
        """A cached, unbuffered read handle (buffering=0, so it always sees fresh appends)."""
        f = self._readers.get(seg_id)
        if f is None:
            f = self._readers[seg_id] = open(self._seg_path(seg_id), "rb", buffering=0)
        return f

    def _drop_reader(self, seg_id):
        f = self._readers.pop(seg_id, None)
        if f:
            f.close()

    def _start_segment(self, seg_id):
        """Make segment seg_id the active one (create it if needed)."""
        self.active_id = seg_id
        flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_BINARY", 0)
        self._fd = os.open(self._seg_path(seg_id), flags, 0o644)
        self._active_size = os.fstat(self._fd).st_size

    def _seal(self):
        """Finish the active segment: fsync it, close it, never write to it again."""
        os.fsync(self._fd)
        os.close(self._fd)
        self._fd = None
        if self.hints:
            self._write_hint(self.active_id)             # Milestone 6

    def _fsync_dir(self):
        """Make file creations, renames and deletions durable (POSIX; skipped elsewhere)."""
        try:
            fd = os.open(self.dir, os.O_RDONLY)
        except OSError:
            return
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def _remove_segment(self, seg_id):
        """Delete a segment file (and its hint file, if any)."""
        self._drop_reader(seg_id)
        for path in (self._seg_path(seg_id), self._hint_path(seg_id)):
            if os.path.exists(path):
                os.remove(path)

    # -- Milestone 2: put / get with an in-memory index ----------------------
    def _append(self, key, value):
        """Append one record to the active segment (value=None for a tombstone).

        Return (segment id, offset, size): where the record now lives.
        Use write_all(self._fd, ...), keep self._active_size up to date, and
        os.fsync(self._fd) afterwards if self.sync is set.
        Milestone 3 adds rollover here: if the record would push the active
        segment past self.max_segment_bytes, call self._roll() first.
        """
        raise NotImplementedError("TODO milestone 2: Store._append")

    def put(self, key, value):
        """Store value under key: append a record, then point the index at it."""
        raise NotImplementedError("TODO milestone 2: Store.put")

    def get(self, key):
        """Return the value for key, or None. Use the index, then ONE seek and ONE read
        (self._reader(seg_id)), then decode_record. Raise CorruptionError if the record
        fails its checksum."""
        raise NotImplementedError("TODO milestone 2: Store.get")

    # -- Milestone 3: deletes and rollover -----------------------------------
    def delete(self, key):
        """Delete a key by appending a tombstone and removing it from the index.
        Return True if the key existed, False if not (and then write nothing)."""
        raise NotImplementedError("TODO milestone 3: Store.delete")

    def _roll(self):
        """Seal the active segment and start the next one (id + 1)."""
        raise NotImplementedError("TODO milestone 3: Store._roll")

    # -- Milestone 4: crash recovery -----------------------------------------
    def _rebuild_index(self, ids):
        """Rebuild self.index by replaying every segment, oldest first.

        For each segment: read the file, scan_segment() it, and for every entry set
        self.index[key] = (seg_id, offset, size), or remove the key for a tombstone.
        If a segment has bytes after good_end:
          * the LAST segment: a torn tail from a crash. Truncate the file to good_end
            and fsync it.
          * any other segment: it was sealed and fsynced, so this is real damage.
            Raise CorruptionError.
        (Milestone 6 adds a shortcut here: use self._read_hint(seg_id) for sealed segments.)
        """
        raise NotImplementedError("TODO milestone 4: Store._rebuild_index")

    # -- Milestone 5: compaction ----------------------------------------------
    def compact(self, hook=None):
        """Merge every segment into one file holding only the live records.

        Steps (see the lab page for the reasons):
          1. inputs = self.segment_ids(); self._seal() the active segment.
          2. out_id = self.active_id + 1, then self._start_segment(out_id + 1): the output
             sorts after every input and before the new active segment.
          3. Copy every LIVE record of the inputs (live = self.index[key] == (seg, offset, size))
             into the temp file self._seg_path(out_id) + ".tmp", remembering the new location
             of each key. os.fsync it.      -> hook("tmp_synced")
          4. os.replace(tmp, final); self._fsync_dir()   -> hook("replaced")
          5. Update self.index to the new locations.
          6. Delete the input segments, OLDEST FIRST, with self._remove_segment(seg_id).
             After the first one                           -> hook("deleted_1")
          7. self._fsync_dir()                             -> hook("done")
        hook(stage), if given, is called at those points; tests raise from it to simulate a crash.
        Return a dict {"bytes_before": ..., "bytes_after": ...} (not checked).
        """
        raise NotImplementedError("TODO milestone 5: Store.compact")

    # -- Milestone 6 (optional): hint files -----------------------------------
    def _write_hint(self, seg_id):
        """Write seg-NNNNNN.hint for a sealed segment: one (key, offset, size, tombstone?)
        entry per record, plus a trailer holding the segment's size and a CRC of the entries.
        Write to a .tmp name, fsync, os.replace."""
        raise NotImplementedError("TODO milestone 6: Store._write_hint")

    def _read_hint(self, seg_id):
        """Return the hint's entries (same shape as scan_segment's), or None if the hint is
        missing, damaged (bad CRC) or stale (its recorded segment size differs from the file's)."""
        raise NotImplementedError("TODO milestone 6: Store._read_hint")

    # -- misc (given) -----------------------------------------------------------
    def __len__(self):
        return len(self.index)

    def keys(self):
        return sorted(self.index)

    def close(self):
        if self._fd is not None:
            try:
                os.fsync(self._fd)
            except OSError:
                pass
            os.close(self._fd)
            self._fd = None
        for seg_id in list(self._readers):
            self._drop_reader(seg_id)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
