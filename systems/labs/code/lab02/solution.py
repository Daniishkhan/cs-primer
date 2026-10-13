"""Lab 2 solution: crash-safe storage. A checksummed append-only log, and atomic file replace.

POSIX only (macOS, Linux, WSL).

Record format on disk (all integers big-endian):

    +-----------+-----------+------------------+
    | length    | crc32     | payload          |
    | 4 bytes   | 4 bytes   | `length` bytes   |
    +-----------+-----------+------------------+

The CRC covers the 4 length bytes AND the payload, so a damaged length field is
caught too.
"""
import json
import os
import struct
import zlib

HEADER = struct.Struct(">II")          # (length, crc32): 8 bytes
MAX_RECORD = 16 * 1024 * 1024          # a "length" bigger than this is certainly garbage


# ---------------------------------------------------------------------------
# Milestone 1: the record format and an append-only log
# ---------------------------------------------------------------------------

def encode_record(payload):
    """Return the bytes to write for one record: length, crc, payload."""
    length = struct.pack(">I", len(payload))
    crc = zlib.crc32(payload, zlib.crc32(length))      # crc of length bytes, then payload
    return length + struct.pack(">I", crc) + payload


def write_all(fd, data):
    """os.write may write less than asked; loop until everything is written."""
    view = memoryview(data)
    while view:
        n = os.write(fd, view)
        view = view[n:]


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
        self.recover()                                  # Milestone 2

    def append(self, payload):
        """Append one record. Returns the offset where it starts."""
        offset = self._size
        write_all(self._fd, encode_record(payload))    # ONE write call per record
        self._size += HEADER.size + len(payload)
        self._unsynced += 1
        # Milestone 3: the durability policy decides when the data is forced to disk.
        if self.policy == "always":
            self.flush()
        elif self.policy == "batch" and self._unsynced >= self.batch_size:
            self.flush()
        return offset

    def read_all(self):
        """Return the payloads of every record, oldest first."""
        with open(self.path, "rb") as f:
            payloads, _ = scan_records(f.read())
        return payloads

    # --- Milestone 2 ---------------------------------------------------------

    def recover(self):
        """Drop a torn or corrupt tail. Returns how many bytes were removed."""
        with open(self.path, "rb") as f:
            data = f.read()
        _, good_end = scan_records(data)
        dropped = len(data) - good_end
        if dropped:
            os.ftruncate(self._fd, good_end)
            os.fsync(self._fd)                          # make the repair itself durable
            self._size = good_end
        return dropped

    # --- Milestone 3 ---------------------------------------------------------

    def flush(self):
        """Force everything appended so far to stable storage (a group commit)."""
        if self._unsynced:
            os.fsync(self._fd)
            self._unsynced = 0

    def close(self):
        if self._fd is not None:
            self.flush()
            os.close(self._fd)
            self._fd = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def scan_records(data):
    """Parse `data` as a sequence of records.

    Returns (payloads, good_end): the payloads of every valid record from the
    start, and the byte offset where the valid prefix ends. Stops at the first
    record that is incomplete or fails its checksum.
    """
    payloads = []
    pos = 0
    while pos + HEADER.size <= len(data):
        length, crc = HEADER.unpack_from(data, pos)
        start = pos + HEADER.size
        end = start + length
        if length > MAX_RECORD or end > len(data):      # absurd length, or the payload is cut short
            break
        payload = data[start:end]
        if zlib.crc32(payload, zlib.crc32(data[pos:pos + 4])) != crc:
            break                                       # bit rot or a half-written record
        payloads.append(payload)
        pos = end
    return payloads, pos


# ---------------------------------------------------------------------------
# Milestone 5: replace a config file atomically
# ---------------------------------------------------------------------------

def save_config(path, config, hook=None):
    """Write `config` (a dict) to `path` so a crash never leaves it missing or half-written.

    `hook(stage)`, if given, is called after each step. Tests raise an exception
    from it to simulate a crash at exactly that point.
    """
    def step(name):
        if hook:
            hook(name)

    data = json.dumps(config, sort_keys=True).encode("utf-8")
    tmp = path + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)   # same directory = same file system
    try:
        half = len(data) // 2
        write_all(fd, data[:half])
        step("tmp_partial")                  # a crash here leaves a half file, but only the temp one
        write_all(fd, data[half:])
        step("tmp_written")
        os.fsync(fd)                         # the new bytes are on disk BEFORE we publish them
        step("tmp_synced")
    finally:
        os.close(fd)
    os.replace(tmp, path)                    # atomic: readers see the old file or the new, never a mix
    step("replaced")
    dir_fd = os.open(os.path.dirname(os.path.abspath(path)), os.O_RDONLY)
    try:
        os.fsync(dir_fd)                     # make the rename itself durable
    finally:
        os.close(dir_fd)
    step("dir_synced")


def load_config(path):
    with open(path, "rb") as f:
        return json.loads(f.read().decode("utf-8"))
