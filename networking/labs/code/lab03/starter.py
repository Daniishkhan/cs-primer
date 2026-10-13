"""Lab 3 starter: a DNS resolver from scratch.

Fill in every TODO, one milestone at a time, and run `python3 check.py`
after each one. The lab page walks you through it. The constants, the
Message class, hexdump/print helpers and query_tcp are already written.

Usage:
    python3 starter.py hex example.com            # show the query packet, byte by byte
    python3 starter.py dig example.com [A|AAAA|NS|MX|TXT|CNAME] [@1.1.1.1]
    python3 starter.py trace www.example.com      # iterative lookup from a root server
    python3 starter.py cache example.com          # look it up twice and time both

Standard library only. Needs outbound UDP port 53 for the live commands; some
networks block that. check.py tests the parsing and building offline.
"""
import ipaddress
import math
import random
import socket
import struct
import sys
import time
from collections import namedtuple

# ---------------------------------------------------------------------------
# Constants and small types. (Provided.)
# ---------------------------------------------------------------------------

TYPE_A, TYPE_NS, TYPE_CNAME, TYPE_SOA = 1, 2, 5, 6
TYPE_PTR, TYPE_MX, TYPE_TXT, TYPE_AAAA = 12, 15, 16, 28
CLASS_IN = 1

TYPE_NAMES = {TYPE_A: "A", TYPE_NS: "NS", TYPE_CNAME: "CNAME", TYPE_SOA: "SOA",
              TYPE_PTR: "PTR", TYPE_MX: "MX", TYPE_TXT: "TXT", TYPE_AAAA: "AAAA"}
RCODE_NAMES = {0: "NOERROR", 1: "FORMERR", 2: "SERVFAIL", 3: "NXDOMAIN", 4: "NOTIMP", 5: "REFUSED"}

# The thirteen root server names and their IPv4 addresses (from IANA's root hints).
ROOT_SERVERS = [
    ("a.root-servers.net", "198.41.0.4"),
    ("b.root-servers.net", "170.247.170.2"),
    ("c.root-servers.net", "192.33.4.12"),
    ("d.root-servers.net", "199.7.91.13"),
    ("e.root-servers.net", "192.203.230.10"),
    ("f.root-servers.net", "192.5.5.241"),
    ("g.root-servers.net", "192.112.36.4"),
    ("h.root-servers.net", "198.97.190.53"),
    ("i.root-servers.net", "192.36.148.17"),
    ("j.root-servers.net", "192.58.128.30"),
    ("k.root-servers.net", "193.0.14.129"),
    ("l.root-servers.net", "199.7.83.42"),
    ("m.root-servers.net", "202.12.27.33"),
]

MAX_REFERRALS = 12   # a lookup that needs more steps than this is looping
MAX_DEPTH = 8        # nested lookups (NS names without glue, CNAME targets)


class DNSError(Exception):
    """Anything wrong with a DNS packet or a lookup."""


class DNSTimeout(DNSError):
    """No usable reply arrived in time."""


Question = namedtuple("Question", "name qtype qclass")
Record = namedtuple("Record", "name rtype rclass ttl rdata")


class Message:
    """A parsed DNS message. `flags` is the raw 16-bit flags field."""

    def __init__(self, id, flags, questions, answers, authority, additional):
        self.id, self.flags = id, flags
        self.questions, self.answers = questions, answers
        self.authority, self.additional = authority, additional

    qr = property(lambda self: (self.flags >> 15) & 1)       # 1 = this is a response
    opcode = property(lambda self: (self.flags >> 11) & 0xF)
    aa = property(lambda self: (self.flags >> 10) & 1)       # authoritative answer
    tc = property(lambda self: (self.flags >> 9) & 1)        # truncated
    rd = property(lambda self: (self.flags >> 8) & 1)        # recursion desired
    ra = property(lambda self: (self.flags >> 7) & 1)        # recursion available
    rcode = property(lambda self: self.flags & 0xF)          # 0 = no error, 3 = NXDOMAIN


def type_name(rtype):
    return TYPE_NAMES.get(rtype, f"TYPE{rtype}")


def type_number(name):
    """'A' -> 1, 'mx' -> 15, 'TYPE99' -> 99."""
    name = name.upper()
    for number, label in TYPE_NAMES.items():
        if label == name:
            return number
    if name.startswith("TYPE") and name[4:].isdigit():
        return int(name[4:])
    raise ValueError(f"unknown record type {name!r}")


def hexdump(data):
    """Classic hex dump: offset, 16 bytes of hex, then printable characters."""
    lines = []
    for i in range(0, len(data), 16):
        chunk = data[i:i + 16]
        hexpart = " ".join(f"{b:02x}" for b in chunk)
        text = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        lines.append(f"{i:04x}  {hexpart:<47}  {text}")
    return "\n".join(lines)


def format_rdata(rdata):
    if isinstance(rdata, tuple):                     # MX: (preference, exchange)
        return " ".join(str(x) for x in rdata)
    if isinstance(rdata, list):                      # TXT: list of strings
        return " ".join(f'"{s}"' for s in rdata)
    if isinstance(rdata, bytes):                     # a type we don't decode
        return rdata.hex()
    return str(rdata)


def format_record(rec):
    """One line in the style of dig:  name  TTL  IN  TYPE  value."""
    return f"{rec.name + '.':<28} {rec.ttl:<6} IN  {type_name(rec.rtype):<6} {format_rdata(rec.rdata)}"


# ---------------------------------------------------------------------------
# Milestone 1: build a query.
# ---------------------------------------------------------------------------

def encode_name(name):
    """Turn "www.example.com" into DNS wire format.

    Each label is written as one length byte followed by its characters, and
    the whole name ends with a zero byte (the empty label of the root):
        "example.com" -> b"\x07example\x03com\x00"
    Details:
      * A trailing dot ("example.com.") means the same thing; "." is just b"\x00".
      * Labels are at most 63 bytes: raise ValueError for a longer one.
      * Hint: name.strip(".").split("."), label.encode("ascii"), bytes([len(raw)]).
    """
    raise NotImplementedError("TODO milestone 1: encode_name")


def build_query(name, qtype=TYPE_A, qid=None, recursion_desired=True):
    """Return a complete DNS query packet (header + one question) as bytes.

    Header: six unsigned 16-bit numbers, struct format "!HHHHHH":
        ID       qid, or a random number in 0..65535 when qid is None
        FLAGS    0x0100 sets just the RD ("recursion desired") bit; 0x0000 for none
        QDCOUNT  1 (one question)
        ANCOUNT, NSCOUNT, ARCOUNT   0, 0, 0
    Question: encode_name(name) + struct.pack("!HH", qtype, CLASS_IN)
    """
    raise NotImplementedError("TODO milestone 1: build_query")


# ---------------------------------------------------------------------------
# Milestone 2: parse a response.
# ---------------------------------------------------------------------------

def decode_name(buf, offset):
    """Read a possibly-compressed name starting at buf[offset].

    Returns (name, next_offset), e.g. ("www.example.com", 17), where next_offset
    is where the bytes AFTER this name start in the original position.

    Loop on the byte at `offset` (call it `length`):
      * 0               end of the name; step past it and stop.
      * 1..63           a label: read that many characters, add to the list.
      * top two bits 11 (length & 0xC0 == 0xC0) a compression POINTER: the
                        next 14 bits (length & 0x3F, then the next byte) are an
                        offset into the whole packet where the rest of the name
                        continues. Jump there. The caller's next_offset is the
                        position just after the FIRST pointer (2 bytes on);
                        remember it only once.
    Safety (the network is hostile): raise DNSError if you run off the end of
    buf, and if you follow more than about 20 pointers (a loop).
    Join the labels with ".". The root name gives "".
    """
    raise NotImplementedError("TODO milestone 2: decode_name")


def parse_record(buf, offset):
    """Parse one resource record at buf[offset]. Returns (Record, next_offset).

    Layout: name (decode_name) | TYPE 2 bytes | CLASS 2 | TTL 4 | RDLENGTH 2 | RDATA.
    struct.unpack("!HHIH", ...) reads the 10 fixed bytes after the name.
    Turn RDATA into something friendly, by TYPE:
      A      4 bytes   -> "192.0.2.1"        (socket.inet_ntoa)
      AAAA   16 bytes  -> "2001:db8::1"      (str(ipaddress.IPv6Address(bytes)))
      NS, CNAME, PTR   -> a name: decode_name(buf, offset)  (it can contain
                          pointers back into the packet, so pass the WHOLE buf)
      MX     -> (preference, name): a 2-byte number, then a name
      TXT    -> list of strings: repeated (1 length byte + that many bytes)
      other  -> the raw bytes
    Raise DNSError if RDLENGTH runs past the end of buf.
    """
    raise NotImplementedError("TODO milestone 2: parse_record")


def parse_message(data):
    """Parse a whole DNS message into a Message(id, flags, questions, answers, authority, additional).

    1. The 12-byte header: struct.unpack("!HHHHHH", data[:12]) gives
       ID, FLAGS, QDCOUNT, ANCOUNT, NSCOUNT, ARCOUNT.
    2. QDCOUNT questions: decode_name, then 4 bytes (qtype, qclass) each.
       Make a Question(name, qtype, qclass).
    3. Then ANCOUNT answers, NSCOUNT authority records and ARCOUNT additional
       records, one parse_record after another, each starting where the last ended.
    Anything too short or inconsistent must raise DNSError, never IndexError or
    struct.error (wrap carefully or check lengths).
    """
    raise NotImplementedError("TODO milestone 2: parse_message")


# ---------------------------------------------------------------------------
# Milestone 3: ask a server over UDP.
# ---------------------------------------------------------------------------

def _tcp_exchange(server, packet, port=53, timeout=3.0):
    """Send one query over TCP (2-byte length prefix) and return the raw reply. (Provided.)"""
    try:
        with socket.create_connection((server, port), timeout=timeout) as s:
            s.sendall(struct.pack("!H", len(packet)) + packet)
            (length,) = struct.unpack("!H", _read_exactly(s, 2))
            return _read_exactly(s, length)
    except (OSError, struct.error) as e:
        raise DNSTimeout(f"TCP query to {server} failed: {e}")


def _read_exactly(sock, n):
    data = b""
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            raise OSError("connection closed early")
        data += chunk
    return data


def query_tcp(server, name, qtype=TYPE_A, port=53, timeout=3.0, recursion_desired=True):
    """Same as query_udp but over TCP. Used for truncated answers. (Provided.)"""
    packet = build_query(name, qtype, recursion_desired=recursion_desired)
    msg = parse_message(_tcp_exchange(server, packet, port, timeout))
    return msg


def query_udp(server, name, qtype=TYPE_A, port=53, timeout=2.0, recursion_desired=True):
    """Send one query to `server` over UDP and return the parsed reply (a Message).

    1. Pick a random 16-bit qid and build the packet with build_query(..., qid=qid).
    2. Open a UDP socket, sendto((server, port)).
    3. Wait for a reply with a DEADLINE (time.monotonic() + timeout), reading with
       sock.recvfrom(4096). Ignore a datagram that is not from `server`, is shorter
       than 12 bytes, or has a different ID: a stray or forged packet must not
       be accepted. Keep waiting for the real one.
    4. No valid reply before the deadline: raise DNSTimeout.
    5. TC bit ("truncated": the answer didn't fit in a UDP datagram) is bit 0x02
       of byte 2. When set, return query_tcp(server, name, qtype, port, timeout,
       recursion_desired) instead.
    6. Otherwise return parse_message(data).
    """
    raise NotImplementedError("TODO milestone 3: query_udp")


def print_dig(msg, server, elapsed_ms):
    """Print a reply roughly the way `dig` does. (Provided.)"""
    print(f";; status: {RCODE_NAMES.get(msg.rcode, msg.rcode)}, id: {msg.id}, "
          f"flags:{' qr' if msg.qr else ''}{' aa' if msg.aa else ''}{' tc' if msg.tc else ''}"
          f"{' rd' if msg.rd else ''}{' ra' if msg.ra else ''}")
    for q in msg.questions:
        print(f";; QUESTION: {q.name}. IN {type_name(q.qtype)}")
    for title, section in (("ANSWER", msg.answers), ("AUTHORITY", msg.authority),
                           ("ADDITIONAL", msg.additional)):
        if section:
            print(f";; {title} SECTION:")
            for rec in section:
                print(format_record(rec))
    print(f";; Query time: {elapsed_ms:.0f} msec   SERVER: {server}")


# ---------------------------------------------------------------------------
# Milestones 4 and 6: iterative resolution (and CNAMEs).
# ---------------------------------------------------------------------------

def ask_server(server, name, qtype=TYPE_A):
    """Ask one authoritative server a question *without* asking it to recurse. (Provided.)"""
    return query_udp(server, name, qtype, recursion_desired=False)


def resolve_iterative(name, qtype=TYPE_A, query_fn=ask_server, roots=ROOT_SERVERS,
                      trace=None, _depth=0):
    """Resolve `name` by walking the DNS tree from a root server, like `dig +trace`.

    query_fn(server_ip, name, qtype) -> Message. trace(line) (if given) is called
    with a readable string for every step. Return the list of answer Records.

    servers = the root IPs.  Repeat (at most MAX_REFERRALS times):
      1. Ask the servers one at a time until one replies; skip any that raise
         DNSError or OSError. If none reply, raise DNSError.
      2. msg.rcode == 3 -> raise DNSError("NXDOMAIN ..."); other nonzero rcode -> DNSError.
      3. If msg.answers is not empty -> done: return them.
      4. Otherwise it is a REFERRAL: the authority section has NS records naming
         the next zone's servers. Their addresses are the "glue" A records in the
         additional section (match the NS target name, case-insensitively).
         No NS records at all means "the name exists, but has no data of this type":
         return [].
      5. No glue? Then resolve a name server's own name first: call
         resolve_iterative(ns_name, TYPE_A, query_fn, roots, trace, _depth + 1)
         and use the A records you get. Give up with DNSError past MAX_DEPTH.

    Milestone 6 (optional): if the answers hold a CNAME for `name` but no record
    of the type you asked for (and qtype is not CNAME), the answer is an alias:
    resolve the CNAME's target (the rdata) the same way and return the CNAME
    record(s) followed by the target's records. The depth limit stops CNAME loops.
    """
    raise NotImplementedError("TODO milestone 4: resolve_iterative")


# ---------------------------------------------------------------------------
# Milestone 5: a TTL cache.
# ---------------------------------------------------------------------------

class TTLCache:
    """Remember lists of Records until their TTL runs out.

    Methods:
      put(key, records)  expires_at = self.clock() + the SMALLEST ttl among
                         the records. A TTL of 0 (or no records) means: don't cache.
      get(key)           None if missing or expired (delete expired entries).
                         Otherwise return copies of the records whose ttl shows the
                         seconds REMAINING, rounded up: r._replace(ttl=...).
    `clock` is injectable (default time.monotonic) so tests can fake time.
    """
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self._items = {}                    # key -> (expires_at, records)

    def put(self, key, records):
        raise NotImplementedError("TODO milestone 5: TTLCache.put")

    def get(self, key):
        raise NotImplementedError("TODO milestone 5: TTLCache.get")


class CachingResolver:
    """An iterative resolver that remembers answers."""

    def __init__(self, query_fn=ask_server, roots=ROOT_SERVERS, clock=time.monotonic, trace=None):
        self.query_fn, self.roots, self.trace = query_fn, roots, trace
        self.cache = TTLCache(clock)

    def resolve(self, name, qtype=TYPE_A):
        """Return the answer Records for (name, qtype), using the cache when possible.

        key = (name.lower().rstrip("."), qtype)  (names are case-insensitive).
        On a hit: call self.trace("cache hit ...") if there is a trace function,
        and return the cached records. On a miss: resolve_iterative(name, qtype,
        self.query_fn, self.roots, self.trace), put the result in the cache, return it.
        """
        raise NotImplementedError("TODO milestone 5: CachingResolver.resolve")


# ---------------------------------------------------------------------------
# Command line.
# ---------------------------------------------------------------------------

def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return
    cmd, name = argv[1], argv[2]
    if cmd == "hex":
        packet = build_query(name, qid=0x1234)
        print(f"{len(packet)} bytes:\n{hexdump(packet)}")
    elif cmd == "dig":
        qtype, server = TYPE_A, "1.1.1.1"
        for arg in argv[3:]:
            if arg.startswith("@"):
                server = arg[1:]
            else:
                qtype = type_number(arg)
        start = time.monotonic()
        msg = query_udp(server, name, qtype)
        print_dig(msg, server, (time.monotonic() - start) * 1000)
    elif cmd == "trace":
        answers = resolve_iterative(name, trace=print)
        print()
        for rec in answers:
            print(format_record(rec))
    elif cmd == "cache":
        resolver = CachingResolver()
        for attempt in (1, 2):
            start = time.monotonic()
            answers = resolver.resolve(name)
            ms = (time.monotonic() - start) * 1000
            print(f"lookup {attempt}: {ms:8.2f} ms  ->  "
                  + ", ".join(f"{r.rdata} (ttl {r.ttl})" for r in answers if r.rtype == TYPE_A))
    else:
        print(__doc__)


if __name__ == "__main__":
    main(sys.argv)
