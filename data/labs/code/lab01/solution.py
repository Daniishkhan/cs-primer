"""Lab 1 solution: a log-structured key-value store (a small Bitcask).

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
    """os.write may write less than asked; loop until everything is written."""
    view = memoryview(data)
    while view:
        n = os.write(fd, view)
        view = view[n:]


# ---------------------------------------------------------------------------
# Milestone 1: the record format, and the slow store that scans the file
# ---------------------------------------------------------------------------

def encode_record(key, value):
    """Bytes for one record. value=None encodes a tombstone (value length -1)."""
    vlen = -1 if value is None else len(value)
    body = struct.pack(">Ii", len(key), vlen) + key + (value or b"")
    return struct.pack(">I", zlib.crc32(body)) + body


def decode_record(buf, pos=0):
    """Parse one record at buf[pos:].

    Returns (key, value, next_pos), where value is None for a tombstone, or
    None if the record is incomplete or fails its checksum. Never raises on
    garbage and never trusts a length before checking it.
    """
    if pos + HEADER.size > len(buf):
        return None                                    # not even a whole header
    crc, klen, vlen = HEADER.unpack_from(buf, pos)
    if klen > MAX_KEY or vlen < -1 or vlen > MAX_VALUE:
        return None                                    # absurd lengths: garbage
    key_start = pos + HEADER.size
    val_start = key_start + klen
    end = val_start + max(vlen, 0)
    if end > len(buf):
        return None                                    # the record is cut short
    if zlib.crc32(buf[pos + 4:end]) != crc:
        return None                                    # damaged, or a half-written write
    key = bytes(buf[key_start:val_start])
    value = None if vlen == -1 else bytes(buf[val_start:end])
    return key, value, end


class ScanStore:
    """The slow version: one file, and every get() scans it from the start."""

    def __init__(self, path):
        self.path = path
        open(path, "ab").close()                       # make sure the file exists

    def put(self, key, value):
        with open(self.path, "ab") as f:
            f.write(encode_record(key, value))

    def get(self, key):
        with open(self.path, "rb") as f:
            data = f.read()
        found, pos = None, 0
        while True:
            rec = decode_record(data, pos)
            if rec is None:
                break
            k, v, pos = rec
            if k == key:
                found = v                              # a later record overrides an earlier one
        return found


# ---------------------------------------------------------------------------
# Milestone 4 helper: parse a whole segment
# ---------------------------------------------------------------------------

def scan_segment(data):
    """Parse bytes as a run of records.

    Returns (entries, good_end). entries is a list of
    (key, offset, size, is_tombstone), oldest first. good_end is the byte
    offset where the valid prefix ends (len(data) for a healthy segment).
    """
    entries, pos = [], 0
    while pos < len(data):
        rec = decode_record(data, pos)
        if rec is None:
            break
        key, value, nxt = rec
        entries.append((key, pos, nxt - pos, value is None))
        pos = nxt
    return entries, pos


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
            self._rebuild_index(ids)        # Milestone 4
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
        self._drop_reader(seg_id)
        for path in (self._seg_path(seg_id), self._hint_path(seg_id)):
            if os.path.exists(path):
                os.remove(path)

    # -- Milestone 2: put / get with an in-memory index ----------------------
    def _append(self, key, value):
        """Append one record to the active segment. Returns (segment id, offset, size)."""
        rec = encode_record(key, value)
        # Milestone 3: roll over to a new segment when this record would not fit.
        if self._active_size > 0 and self._active_size + len(rec) > self.max_segment_bytes:
            self._roll()
        offset = self._active_size
        write_all(self._fd, rec)
        if self.sync:
            os.fsync(self._fd)
        self._active_size += len(rec)
        return self.active_id, offset, len(rec)

    def put(self, key, value):
        if value is None:
            raise ValueError("value must be bytes; use delete() to remove a key")
        self.index[key] = self._append(key, value)

    def get(self, key):
        loc = self.index.get(key)
        if loc is None:
            return None
        seg_id, offset, size = loc
        f = self._reader(seg_id)
        f.seek(offset)
        rec = decode_record(f.read(size), 0)            # one seek, one read
        if rec is None:
            raise CorruptionError("record at segment %d offset %d failed its checksum" % (seg_id, offset))
        return rec[1]

    # -- Milestone 3: deletes and rollover -----------------------------------
    def delete(self, key):
        """Delete a key by appending a tombstone. Returns True if the key existed."""
        if key not in self.index:
            return False                    # nothing to delete: do not grow the log
        self._append(key, None)
        del self.index[key]
        return True

    def _roll(self):
        """Seal the active segment and start the next one."""
        self._seal()
        self._start_segment(self.active_id + 1)

    # -- Milestone 4: crash recovery -----------------------------------------
    def _rebuild_index(self, ids):
        """Rebuild self.index by replaying every segment, oldest first."""
        for n, seg_id in enumerate(ids):
            is_last = n == len(ids) - 1
            entries = self._read_hint(seg_id) if (self.hints and not is_last) else None   # Milestone 6
            if entries is None:
                path = self._seg_path(seg_id)
                with open(path, "rb") as f:
                    data = f.read()
                entries, good_end = scan_segment(data)
                if good_end < len(data):
                    if not is_last:
                        raise CorruptionError("sealed segment %d is damaged at byte %d" % (seg_id, good_end))
                    with open(path, "r+b") as f:          # torn tail of the active segment:
                        f.truncate(good_end)              # cut it off, then make that durable
                        f.flush()
                        os.fsync(f.fileno())
            for key, offset, size, is_tombstone in entries:
                if is_tombstone:
                    self.index.pop(key, None)             # a newer tombstone hides older values
                else:
                    self.index[key] = (seg_id, offset, size)

    # -- Milestone 5: compaction ----------------------------------------------
    def compact(self, hook=None):
        """Merge every segment into one file holding only the live records.

        Safe order: write new -> fsync -> rename -> update index -> delete old, oldest first.
        hook(stage), if given, is called after each step so tests can "crash" there.
        """
        def step(name):
            if hook:
                hook(name)

        inputs = self.segment_ids()
        if not inputs or self.total_bytes() == 0:
            return {"bytes_before": 0, "bytes_after": 0}
        before = self.total_bytes()
        self._seal()                                     # the old active segment is now an input too
        out_id = self.active_id + 1                      # sorts after every input...
        self._start_segment(out_id + 1)                  # ...and before the fresh active segment
        final = self._seg_path(out_id)
        tmp = final + ".tmp"

        new_index = {}
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_BINARY", 0), 0o644)
        try:
            offset = 0
            for seg_id in inputs:
                with open(self._seg_path(seg_id), "rb") as f:
                    data = f.read()
                entries, _ = scan_segment(data)
                for key, off, size, is_tombstone in entries:
                    if is_tombstone or self.index.get(key) != (seg_id, off, size):
                        continue                         # dead: overwritten, deleted or a tombstone
                    write_all(fd, data[off:off + size])  # copy the live record byte for byte
                    new_index[key] = (out_id, offset, size)
                    offset += size
            os.fsync(fd)                                 # the new file is on disk BEFORE we publish it
        finally:
            os.close(fd)
        step("tmp_synced")
        os.replace(tmp, final)                           # the atomic switch
        self._fsync_dir()
        step("replaced")
        self.index.update(new_index)                     # point the index at the new file
        if self.hints:
            self._write_hint(out_id)                     # Milestone 6
        for n, seg_id in enumerate(inputs):              # oldest first: never orphan a tombstone
            self._remove_segment(seg_id)
            if n == 0:
                step("deleted_1")
        self._fsync_dir()
        step("done")
        return {"bytes_before": before, "bytes_after": self.total_bytes()}

    # -- Milestone 6: hint files ----------------------------------------------
    def _write_hint(self, seg_id):
        """seg-N.hint: (key, offset, size, tombstone?) for every record of a sealed segment."""
        with open(self._seg_path(seg_id), "rb") as f:
            data = f.read()
        entries, _ = scan_segment(data)
        body = b"".join(struct.pack(">IQIB", len(k), off, size, int(t)) + k for k, off, size, t in entries)
        blob = body + struct.pack(">QI", len(data), zlib.crc32(body))   # trailer: segment size, checksum
        tmp = self._hint_path(seg_id) + ".tmp"
        with open(tmp, "wb") as f:
            f.write(blob)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self._hint_path(seg_id))

    def _read_hint(self, seg_id):
        """Entries from the hint file, or None if it is missing, damaged or stale."""
        try:
            with open(self._hint_path(seg_id), "rb") as f:
                blob = f.read()
            seg_size = os.path.getsize(self._seg_path(seg_id))
        except OSError:
            return None
        trailer = struct.Struct(">QI")
        if len(blob) < trailer.size:
            return None
        body = blob[:-trailer.size]
        size_then, crc = trailer.unpack(blob[-trailer.size:])
        if crc != zlib.crc32(body) or size_then != seg_size:
            return None                                  # corrupt, or the segment changed
        entries, pos, head = [], 0, struct.Struct(">IQIB")
        while pos < len(body):
            klen, off, size, tomb = head.unpack_from(body, pos)
            pos += head.size
            entries.append((body[pos:pos + klen], off, size, bool(tomb)))
            pos += klen
        return entries

    # -- misc ----------------------------------------------------------------
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
