"""Lab 2 reference solution: reliable delivery over UDP.

Usage:
    python3 solution.py demo        # transfer a file with both protocols and compare
    python3 solution.py measure     # stop-and-wait throughput versus RTT

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
    """Build  type | seq | checksum | payload  as bytes."""
    # The checksum covers the type, the sequence number AND the payload, so a
    # flipped bit anywhere (except in the checksum itself, which then fails to
    # match) is caught.
    covered = struct.pack("!BI", ptype, seq) + payload
    return HEADER.pack(ptype, seq, zlib.crc32(covered)) + payload


def parse_packet(raw):
    """Return (ptype, seq, payload), or None if the packet is damaged."""
    if len(raw) < HEADER_LEN:
        return None
    ptype, seq, checksum = HEADER.unpack(raw[:HEADER_LEN])
    payload = raw[HEADER_LEN:]
    if ptype not in (DATA, ACK):
        return None
    if zlib.crc32(struct.pack("!BI", ptype, seq) + payload) != checksum:
        return None                           # corrupted in transit: discard
    return ptype, seq, payload


# ---------------------------------------------------------------------------
# Milestone 2: stop-and-wait.
# ---------------------------------------------------------------------------

def stop_and_wait_send(chan, dest, data, timeout=0.05, chunk=CHUNK, max_tries=40):
    """Send `data` one packet at a time. Returns how many DATA packets were sent."""
    # The last packet has an empty payload: that is our "end of file" marker.
    pieces = split_chunks(data, chunk) + [b""]
    sent = 0
    for seq, payload in enumerate(pieces):
        packet = make_packet(DATA, seq, payload)
        for _ in range(max_tries):
            chan.sendto(packet, dest)
            sent += 1
            if _wait_for_ack(chan, seq + 1, timeout):
                break                         # acknowledged: next packet
        else:
            raise ConnectionError(f"no ACK for packet {seq} after {max_tries} tries")
    return sent


def _wait_for_ack(chan, want, timeout):
    """Wait up to `timeout` seconds for an ACK number >= want."""
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False
        chan.settimeout(remaining)
        try:
            raw, _ = chan.recvfrom()
        except socket.timeout:
            return False
        pkt = parse_packet(raw)
        if pkt and pkt[0] == ACK and pkt[1] >= want:
            return True
        # corrupted, wrong type, or an old duplicate ACK: ignore, keep waiting


def receive(chan, linger=0.3, idle_timeout=5.0):
    """Receive a file. Delivers packets in order, drops duplicates, and ACKs
    every DATA packet with the next sequence number it expects (like TCP).
    Works for both stop-and-wait and Go-Back-N senders."""
    expected = 0
    pieces = []
    finished = False
    while True:
        # After the end-of-file packet we "linger": the final ACK may have been
        # lost, and the sender will keep retrying until it hears one.
        chan.settimeout(linger if finished else idle_timeout)
        try:
            raw, addr = chan.recvfrom()
        except socket.timeout:
            if finished:
                return b"".join(pieces)
            raise TimeoutError("sender went quiet")
        pkt = parse_packet(raw)
        if pkt is None or pkt[0] != DATA:
            continue
        _, seq, payload = pkt
        if seq == expected:                   # the one we were waiting for
            expected += 1
            if payload:
                pieces.append(payload)
            else:
                finished = True               # empty payload = end of file
        # seq < expected: a duplicate. seq > expected: out of order. Either
        # way we don't deliver it; we just repeat what we're waiting for.
        chan.sendto(make_packet(ACK, expected), addr)


# ---------------------------------------------------------------------------
# Milestone 3: measuring.
# ---------------------------------------------------------------------------

def measure_throughput(send_fn, rtt, nbytes=30_000):
    """Payload bytes per second for a lossless transfer over a link with this RTT."""
    data = make_test_data(nbytes)
    # The timeout must comfortably exceed the RTT, or we would resend needlessly.
    received, _, seconds = run_transfer(send_fn, receive, data, rtt=rtt, timeout=3 * rtt)
    assert received == data, "transfer was not intact"
    return nbytes / seconds


def bandwidth_delay_product(bits_per_second, rtt):
    """Bytes that fit 'in the pipe': bandwidth x round-trip time."""
    return bits_per_second * rtt / 8


def window_for_full_pipe(bits_per_second, rtt, packet_bytes=CHUNK):
    """Packets that must be in flight to keep the link busy."""
    return math.ceil(bandwidth_delay_product(bits_per_second, rtt) / packet_bytes)


# ---------------------------------------------------------------------------
# Milestone 5 (optional): adaptive timeout, RFC 6298 style.
# ---------------------------------------------------------------------------

class RttEstimator:
    """Smoothed RTT and retransmission timeout (RFC 6298)."""
    ALPHA = 1 / 8
    BETA = 1 / 4
    K = 4

    def __init__(self, initial_rto=0.2, min_rto=0.02, max_rto=2.0):
        self.srtt = None
        self.rttvar = None
        self.min_rto, self.max_rto = min_rto, max_rto
        self.rto = initial_rto

    def update(self, sample):
        """Feed in one RTT measurement (seconds)."""
        if self.srtt is None:                 # the very first sample
            self.srtt = sample
            self.rttvar = sample / 2
        else:                                 # rttvar first, using the OLD srtt
            self.rttvar = (1 - self.BETA) * self.rttvar + self.BETA * abs(self.srtt - sample)
            self.srtt = (1 - self.ALPHA) * self.srtt + self.ALPHA * sample
        self._set_rto(self.srtt + self.K * self.rttvar)

    def backoff(self):
        """A timeout happened: double the RTO (exponential backoff)."""
        self._set_rto(self.rto * 2)

    def _set_rto(self, value):
        self.rto = min(self.max_rto, max(self.min_rto, value))


# ---------------------------------------------------------------------------
# Milestone 4: sliding window (Go-Back-N), with the M5 estimator built in.
# ---------------------------------------------------------------------------

def gbn_send(chan, dest, data, window=32, timeout=0.05, chunk=CHUNK,
             estimator=None, max_tries=40):
    """Go-Back-N sender. Returns how many DATA packets were sent in total.

    base     = oldest packet not yet acknowledged
    next_seq = next packet we have never sent
    At most `window` packets are unacknowledged at once. ONE timer covers the
    oldest unacknowledged packet; if it fires we resend everything from base.
    If `estimator` is given, its RTO replaces the fixed `timeout`.
    """
    packets = [make_packet(DATA, seq, p)
               for seq, p in enumerate(split_chunks(data, chunk) + [b""])]
    total = len(packets)
    base = next_seq = 0
    sent = 0
    send_time = {}                            # seq -> time of first send (for RTT)
    retransmitted = set()                     # Karn: don't time resent packets
    timer_start = time.monotonic()
    stalls = 0                                # timeouts in a row without progress

    while base < total:
        # 1. Fill the window.
        while next_seq < total and next_seq < base + window:
            chan.sendto(packets[next_seq], dest)
            sent += 1
            send_time[next_seq] = time.monotonic()
            if base == next_seq:
                timer_start = time.monotonic()
            next_seq += 1
        # 2. Wait for an ACK, but no longer than the timer allows.
        rto = estimator.rto if estimator else timeout
        remaining = timer_start + rto - time.monotonic()
        try:
            if remaining <= 0:
                raise socket.timeout
            chan.settimeout(remaining)
            raw, _ = chan.recvfrom()
        except socket.timeout:
            # 3. Timer fired: go back N, resend everything from base.
            stalls += 1
            if stalls > max_tries:
                raise ConnectionError(f"no progress after {max_tries} timeouts")
            if estimator:
                estimator.backoff()
            for seq in range(base, next_seq):
                chan.sendto(packets[seq], dest)
                sent += 1
                retransmitted.add(seq)
            timer_start = time.monotonic()
            continue
        pkt = parse_packet(raw)
        if pkt is None or pkt[0] != ACK:
            continue
        ack = pkt[1]                          # cumulative: "I have everything below ack"
        if base < ack <= next_seq:
            if estimator and (ack - 1) not in retransmitted:
                estimator.update(time.monotonic() - send_time[ack - 1])
            base = ack                        # slide the window
            stalls = 0
            timer_start = time.monotonic()    # restart the single timer
    return sent


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
