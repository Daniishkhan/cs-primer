"""Lab 2 starter: crash-safe storage. A checksummed append-only log, and atomic file replace.

Fill in every TODO, one milestone at a time, and run `python3 check.py`
after each one. The lab page walks you through it.

POSIX only (macOS, Linux, WSL).

Record format on disk (all integers big-endian):

    +-----------+-----------+------------------+
    | length    | crc32     | payload          |
    | 4 bytes   | 4 bytes   | `length` bytes   |
    +-----------+-----------+------------------+

The CRC covers the 4 length bytes AND the payload, so a damaged length field is
caught too: crc = zlib.crc32(payload, zlib.crc32(length_bytes)).
"""
import json
import os
import struct
import zlib

HEADER = struct.Struct(">II")          # (length, crc32): 8 bytes
MAX_RECORD = 16 * 1024 * 1024          # a "length" bigger than this is certainly garbage


def write_all(fd, data):
    """os.write may write less than asked; loop until everything is written. (Given.)"""
    view = memoryview(data)
    while view:
        n = os.write(fd, view)
        view = view[n:]


# ---------------------------------------------------------------------------
# Milestone 1: the record format and an append-only log
# ---------------------------------------------------------------------------

def encode_record(payload):
    """Return the bytes to write for one record: 4-byte length, 4-byte crc, payload.

    Hint: struct.pack(">I", len(payload)) gives the length bytes; zlib.crc32
    takes an optional starting value, so crc32(payload, crc32(length_bytes))
    checksums both parts.
    """
    raise NotImplementedError("TODO milestone 1: encode_record")


class RecordLog:
    def __init__(self, path, fsync="always", batch_size=8):
        if fsync not in ("always", "batch", "never"):
            raise ValueError("fsync must be 'always', 'batch' or 'never'")
        self.path = path
        self.policy = fsync
        self.batch_size = batch_size
        self._unsynced = 0                              # records written but not yet fsynced
        # Raw file descriptor, no Python-level buffer: os.write hands bytes
        # straight to the kernel (the page cache). O_APPEND = always write at the end.
        self._fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_APPEND, 0o644)
        self._size = os.fstat(self._fd).st_size
        # TODO milestone 2: call self.recover() here, before anything else touches the file.

    def append(self, payload):
        """Append one record. Returns the offset where it starts.

        Milestone 1: offset = self._size; write_all(self._fd, encode_record(payload));
                     grow self._size; count it in self._unsynced.
        Milestone 3: then apply the policy. "always": self.flush() now.
                     "batch": self.flush() once self._unsynced >= self.batch_size.
                     "never": do nothing.
        """
        raise NotImplementedError("TODO milestone 1: RecordLog.append")

    def read_all(self):
        """Return the payloads (bytes) of every valid record, oldest first.

        Milestone 1: open self.path "rb", read it, and use scan_records.
        """
        raise NotImplementedError("TODO milestone 1: RecordLog.read_all")

    # --- Milestone 2 ---------------------------------------------------------

    def recover(self):
        """Drop a torn or corrupt tail. Returns how many bytes were removed.

        Read the whole file, call scan_records to learn where the valid prefix
        ends, and if there are bytes after it: os.ftruncate(self._fd, good_end),
        os.fsync(self._fd), and update self._size.
        """
        raise NotImplementedError("TODO milestone 2: RecordLog.recover")

    # --- Milestone 3 ---------------------------------------------------------

    def flush(self):
        """Force everything appended so far to stable storage (a group commit).

        If any records are unsynced: os.fsync(self._fd) once and reset the counter.
        """
        raise NotImplementedError("TODO milestone 3: RecordLog.flush")

    def close(self):
        if self._fd is not None:
            try:
                self.flush()
            finally:
                os.close(self._fd)
                self._fd = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def scan_records(data):
    """Parse `data` (bytes) as a sequence of records.

    Returns (payloads, good_end): the payloads of every valid record from the
    start, and the byte offset where the valid prefix ends.

    Stop at the first record that is bad:
      * fewer than 8 bytes left for a header,
      * a length above MAX_RECORD, or more bytes than the data holds,
      * a checksum that does not match.
    Hint: HEADER.unpack_from(data, pos) returns (length, crc).
    """
    raise NotImplementedError("TODO milestone 2: scan_records")


# ---------------------------------------------------------------------------
# Milestone 5: replace a config file atomically
# ---------------------------------------------------------------------------

def save_config(path, config, hook=None):
    """Write `config` (a dict) to `path` so a crash never leaves it missing or half-written.

    Steps, in this order. After each one call hook(name) if hook is given
    (tests raise an exception there to simulate a crash at that exact point):

        1. data = json.dumps(config, sort_keys=True).encode()
        2. tmp = path + ".tmp": os.open(tmp, O_WRONLY | O_CREAT | O_TRUNC)
           write the FIRST HALF of data, then hook("tmp_partial")
           write the second half,         then hook("tmp_written")
        3. os.fsync(fd), then hook("tmp_synced"); close the temp file
        4. os.replace(tmp, path),         then hook("replaced")
        5. open the DIRECTORY (os.path.dirname(os.path.abspath(path))) with
           os.O_RDONLY, os.fsync it, close it, then hook("dir_synced")
    """
    raise NotImplementedError("TODO milestone 5: save_config")


def load_config(path):
    """Read the JSON config back. (Given.)"""
    with open(path, "rb") as f:
        return json.loads(f.read().decode("utf-8"))
