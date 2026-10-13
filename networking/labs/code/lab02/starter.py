"""Lab 2 starter: reliable delivery over UDP.

Fill in every TODO, one milestone at a time, and run `python3 check.py`
after each one. The lab page walks you through it. LossyChannel and the
experiment helpers are already written; read them, but you need not change them.

Usage:
    python3 starter.py demo        # transfer a file with both protocols and compare
    python3 starter.py measure     # stop-and-wait throughput versus RTT

Standard library only. Everything runs on 127.0.0.1; LossyChannel makes the
"network" misbehave in a reproducible (seeded) way.
"""
import heapq
import math
import random
import socket
import struct
import sys
import threading
import time
import zlib

HOST = "127.0.0.1"
CHUNK = 1000          # payload bytes per DATA packet

# Packet types (check.py relies on these exact names).
DATA = 1
ACK = 2

# ! = network byte order (big-endian), B = 1 byte type, I = 4-byte sequence
# number, I = 4-byte CRC-32 checksum. The payload follows the header.
HEADER = struct.Struct("!BII")
HEADER_LEN = HEADER.size      # 9 bytes


# ---------------------------------------------------------------------------
# LossyChannel: a UDP socket that behaves like a bad network. (Provided.)
# ---------------------------------------------------------------------------

class LossyChannel:
    """A UDP socket whose *outgoing* datagrams can be dropped, delayed,
    duplicated, reordered or corrupted, using a seeded random generator so a
    run is reproducible.

        loss     probability that a datagram is silently dropped
        dup      probability that a datagram is delivered twice
        reorder  probability that a datagram is held back extra, so later
                 ones overtake it
        corrupt  probability that one byte of a datagram is damaged
        delay    one-way delay in seconds added to every datagram
        jitter   extra random delay, uniform in [0, jitter] seconds
        seed     seeds the random generator (same seed, same dice rolls)

    Impairments apply when you call sendto(). Two channels talking to each
    other (one per side) therefore impair both directions independently.
    The API mirrors a socket: sendto, recvfrom, settimeout, close.
    """

    def __init__(self, loss=0.0, dup=0.0, reorder=0.0, corrupt=0.0,
                 delay=0.0, jitter=0.0, seed=0, port=0):
        self.loss, self.dup, self.reorder = loss, dup, reorder
        self.corrupt, self.delay, self.jitter = corrupt, delay, jitter
        self._rng = random.Random(seed)
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.bind((HOST, port))
        self.addr = self._sock.getsockname()
        self.stats = {"sent": 0, "dropped": 0, "duplicated": 0,
                      "reordered": 0, "corrupted": 0}
        self._queue = []                     # heap of (due_time, n, data, addr)
        self._count = 0
        self._cv = threading.Condition()
        self._closed = False
        threading.Thread(target=self._deliver_loop, daemon=True).start()

    def sendto(self, data, addr):
        """Hand a datagram to the lossy network."""
        with self._cv:
            self.stats["sent"] += 1
            r = self._rng
            if r.random() < self.loss:
                self.stats["dropped"] += 1
                return
            copies = 1
            if r.random() < self.dup:
                copies = 2
                self.stats["duplicated"] += 1
            for _ in range(copies):
                payload = data
                due = time.monotonic() + self.delay + r.uniform(0, self.jitter)
                if r.random() < self.reorder:
                    due += r.uniform(0.5, 2.0) * (self.delay + 0.005)
                    self.stats["reordered"] += 1
                if data and r.random() < self.corrupt:
                    i = r.randrange(len(data))
                    payload = data[:i] + bytes([data[i] ^ 0xFF]) + data[i + 1:]
                    self.stats["corrupted"] += 1
                self._count += 1
                heapq.heappush(self._queue, (due, self._count, payload, addr))
            self._cv.notify()

    def _deliver_loop(self):
        """Background thread: send each queued datagram when it comes due."""
        with self._cv:
            while not self._closed:
                if not self._queue:
                    self._cv.wait()
                    continue
                due = self._queue[0][0]
                now = time.monotonic()
                if due > now:
                    self._cv.wait(due - now)
                    continue
                _, _, payload, addr = heapq.heappop(self._queue)
                try:
                    self._sock.sendto(payload, addr)
                except OSError:
                    pass

    def recvfrom(self, bufsize=2048):
        return self._sock.recvfrom(bufsize)

    def settimeout(self, timeout):
        self._sock.settimeout(timeout)

    def close(self):
        with self._cv:
            self._closed = True
            self._cv.notify()
        self._sock.close()


# ---------------------------------------------------------------------------
# Helpers for the experiments. (Provided.)
# ---------------------------------------------------------------------------

def make_test_data(n, seed=2):
    """n reproducible pseudo-random bytes."""
    return random.Random(seed).getrandbits(8 * n).to_bytes(n, "little")


def split_chunks(data, size=CHUNK):
    """Cut data into pieces of at most `size` bytes."""
    return [data[i:i + size] for i in range(0, len(data), size)]


def run_transfer(send_fn, recv_fn, data, rtt=0.01, loss=0.0, dup=0.0,
                 reorder=0.0, corrupt=0.0, seed=1, deadline=25.0, **send_kwargs):
    """Send `data` from a sender to a receiver across a LossyChannel pair.

    `rtt` is the artificial round-trip time: each direction delays by rtt/2.
    Runs recv_fn(chan) in a thread and send_fn(chan, dest, data, **kw) here.
    Returns (received_bytes, packets_sent, seconds), where seconds is how long
    the *sender* took until its last packet was acknowledged.
    """
    kw = dict(loss=loss, dup=dup, reorder=reorder, corrupt=corrupt, delay=rtt / 2)
    tx = LossyChannel(seed=seed, **kw)
    rx = LossyChannel(seed=seed + 1000, **kw)
    box = {}

    def receiver():
        try:
            box["data"] = recv_fn(rx)
        except BaseException as e:           # surface errors from the thread
            box["error"] = e

    t = threading.Thread(target=receiver, daemon=True)
    t.start()
    try:
        started = time.monotonic()
        sent = send_fn(tx, rx.addr, data, **send_kwargs)
        elapsed = time.monotonic() - started
    except BaseException as e:
        t.join(0.3)                          # did the receiver fail too?
        if isinstance(box.get("error"), NotImplementedError):
            raise box["error"]
        raise e
    finally:
        tx.close()
    t.join(deadline)
    rx.close()
    if "error" in box:
        raise box["error"]
    if "data" not in box:
        raise AssertionError("the receiver never finished")
    return box["data"], sent, elapsed


# ---------------------------------------------------------------------------
# Milestone 1: the packet format.
# ---------------------------------------------------------------------------

def make_packet(ptype, seq, payload=b""):
    """Build  type | seq | checksum | payload  and return it as bytes.

    Hints:
      * HEADER is a struct.Struct("!BII"): type (1 byte), sequence number
        (4 bytes), checksum (4 bytes), all big-endian ("network order").
      * The checksum should cover the type, the sequence number AND the
        payload: zlib.crc32(struct.pack("!BI", ptype, seq) + payload).
      * Return HEADER.pack(ptype, seq, checksum) + payload.
    """
    raise NotImplementedError("TODO milestone 1: make_packet")


def parse_packet(raw):
    """Return (ptype, seq, payload), or None if the packet is damaged.

    Return None (never raise) when:
      * raw is shorter than HEADER_LEN,
      * the type is not DATA or ACK,
      * the checksum does not match the recomputed CRC-32.

    Hint: unpack raw[:HEADER_LEN] with HEADER.unpack, take the rest as the
    payload, recompute the checksum exactly as make_packet does, compare.
    """
    raise NotImplementedError("TODO milestone 1: parse_packet")


# ---------------------------------------------------------------------------
# Milestone 2: stop-and-wait.
# ---------------------------------------------------------------------------

def stop_and_wait_send(chan, dest, data, timeout=0.05, chunk=CHUNK, max_tries=40):
    """Send `data` one packet at a time. Return how many DATA packets were sent.

    Steps:
      1. pieces = split_chunks(data, chunk) + [b""]. The final empty payload
         is the end-of-file marker.
      2. For each piece, in order, with sequence number seq = its index:
         send make_packet(DATA, seq, piece) with chan.sendto(packet, dest),
         then wait up to `timeout` seconds for an ACK whose number is
         >= seq + 1 (an ACK carries the NEXT sequence number the receiver
         wants). If none arrives, send the same packet again.
      3. Count every transmission. Give up with ConnectionError after
         max_tries tries for one packet.

    Waiting: chan.settimeout(remaining); chan.recvfrom() raises socket.timeout.
    Use a deadline (time.monotonic() + timeout) and keep waiting after a
    useless packet (corrupted, or an old duplicate ACK) instead of resending
    at once. Write a small helper such as _wait_for_ack(chan, want, timeout).
    """
    raise NotImplementedError("TODO milestone 2: stop_and_wait_send")


def receive(chan, linger=0.3, idle_timeout=5.0):
    """Receive a file. Return its bytes.

    Keep `expected = 0`. Loop on chan.recvfrom():
      * parse_packet(); ignore anything that is None or not DATA.
      * If seq == expected: deliver the payload, expected += 1.
        An EMPTY payload is the end-of-file marker: remember you are finished.
      * Whatever seq was (new, duplicate or out of order), reply to the
        sender's address with make_packet(ACK, expected): "I want `expected`
        next". One rule, and it works for duplicates and gaps too.
      * After end-of-file, don't return at once: the last ACK may be lost and
        the sender will resend. Keep answering until `linger` seconds pass
        with no packet (socket.timeout), then return the joined payloads.
      * If idle_timeout passes before the end, raise TimeoutError.
    This same receiver will serve Go-Back-N in milestone 4.
    """
    raise NotImplementedError("TODO milestone 2: receive")


# ---------------------------------------------------------------------------
# Milestone 3: measuring.
# ---------------------------------------------------------------------------

def measure_throughput(send_fn, rtt, nbytes=30_000):
    """Payload bytes per second for a lossless transfer over a link with this RTT.

    Hint: data = make_test_data(nbytes); then
    run_transfer(send_fn, receive, data, rtt=rtt, timeout=3 * rtt) returns
    (received, packets_sent, seconds). Check received == data and return
    nbytes / seconds. (The timeout must be well above the RTT, or the sender
    would resend packets that were merely slow.)
    """
    raise NotImplementedError("TODO milestone 3: measure_throughput")


def bandwidth_delay_product(bits_per_second, rtt):
    """Bytes that fit 'in the pipe': bandwidth x round-trip time.

    Careful with units: bandwidth is in BITS per second, the answer in BYTES.
    """
    raise NotImplementedError("TODO milestone 3: bandwidth_delay_product")


def window_for_full_pipe(bits_per_second, rtt, packet_bytes=CHUNK):
    """Packets that must be in flight to keep the link busy (round up).

    Hint: bandwidth_delay_product(...) / packet_bytes, rounded up with math.ceil.
    """
    raise NotImplementedError("TODO milestone 3: window_for_full_pipe")


# ---------------------------------------------------------------------------
# Milestone 5 (optional): adaptive timeout, RFC 6298 style.
# ---------------------------------------------------------------------------

class RttEstimator:
    """Smoothed RTT and retransmission timeout (RFC 6298).

    Attributes: srtt (None until the first sample), rttvar, rto.
    Constants: ALPHA = 1/8, BETA = 1/4, K = 4.

    update(sample)   first sample:  srtt = R,  rttvar = R / 2
                     later samples: rttvar = (1 - BETA) * rttvar + BETA * |srtt - R|
                                    srtt   = (1 - ALPHA) * srtt + ALPHA * R
                     (compute rttvar FIRST, with the old srtt)
                     then rto = srtt + K * rttvar, clamped to [min_rto, max_rto]
    backoff()        rto = rto * 2, clamped (a timeout happened)
    """
    ALPHA = 1 / 8
    BETA = 1 / 4
    K = 4

    def __init__(self, initial_rto=0.2, min_rto=0.02, max_rto=2.0):
        self.srtt = None
        self.rttvar = None
        self.min_rto, self.max_rto = min_rto, max_rto
        self.rto = initial_rto

    def update(self, sample):
        raise NotImplementedError("TODO milestone 5: RttEstimator.update")

    def backoff(self):
        raise NotImplementedError("TODO milestone 5: RttEstimator.backoff")


# ---------------------------------------------------------------------------
# Milestone 4: sliding window (Go-Back-N), with the M5 estimator built in.
# ---------------------------------------------------------------------------

def gbn_send(chan, dest, data, window=32, timeout=0.05, chunk=CHUNK,
             estimator=None, max_tries=40):
    """Go-Back-N sender. Return how many DATA packets were sent in total.

    State: base = oldest unacknowledged packet, next_seq = next never-sent one.
    Build all packets first:  make_packet(DATA, seq, piece) for the pieces of
    split_chunks(data, chunk) + [b""].

    Loop until base == len(packets):
      1. FILL: while next_seq < total and next_seq < base + window, send
         packets[next_seq] and advance next_seq. (Start the timer when the
         first packet of an empty window goes out.)
      2. WAIT for an ACK, but only until timer_start + timeout.
      3. ACK received: parse it. If it is an ACK with base < ack <= next_seq,
         everything below `ack` arrived: base = ack (the window slides) and
         restart the timer. Anything else (corrupt, stale, duplicate): ignore.
      4. TIMEOUT: go back N. Resend every packet from base to next_seq - 1,
         and restart the timer. Raise ConnectionError after max_tries
         timeouts in a row with no progress.

    Milestone 5 (optional): if `estimator` is not None, use estimator.rto
    instead of `timeout`, call estimator.backoff() on each timeout, and call
    estimator.update(sample) with the measured round trip for the newest
    acknowledged packet. Karn's rule: never time a packet you retransmitted
    (the ACK could be for either copy).
    """
    raise NotImplementedError("TODO milestone 4: gbn_send")


# ---------------------------------------------------------------------------
# Command line.
# ---------------------------------------------------------------------------

def main(argv):
    cmd = argv[1] if len(argv) > 1 else "demo"
    if cmd == "demo":
        data = make_test_data(200_000)
        kw = dict(rtt=0.01, loss=0.10, dup=0.05, reorder=0.10, corrupt=0.02)
        for name, fn in (("stop-and-wait", stop_and_wait_send), ("go-back-n", gbn_send)):
            got, sent, secs = run_transfer(fn, receive, data, **kw)
            ok = "intact" if got == data else "CORRUPT"
            print(f"{name:14} {secs:5.2f} s  {sent} packets sent  {ok}")
    elif cmd == "measure":
        print("RTT      stop-and-wait throughput   ceiling (chunk / RTT)")
        for rtt in (0.01, 0.02, 0.04):
            bps = measure_throughput(stop_and_wait_send, rtt)
            print(f"{rtt * 1000:4.0f} ms  {bps / 1000:8.1f} KB/s            {CHUNK / rtt / 1000:8.1f} KB/s")
        print(f"\nTo fill 10 Mbit/s at 20 ms RTT you need "
              f"{window_for_full_pipe(10e6, 0.02)} packets in flight.")
    else:
        print(__doc__)


if __name__ == "__main__":
    main(sys.argv)
