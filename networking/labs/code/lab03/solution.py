"""Lab 3 reference solution: a DNS resolver from scratch.

Usage:
    python3 solution.py hex example.com            # show the query packet, byte by byte
    python3 solution.py dig example.com [A|AAAA|NS|MX|TXT|CNAME] [@1.1.1.1]
    python3 solution.py trace www.example.com      # iterative lookup from a root server
    python3 solution.py cache example.com          # look it up twice and time both

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
    """'www.example.com' -> b'\\x03www\\x07example\\x03com\\x00'."""
    out = b""
    for label in name.strip(".").split("."):
        if not label:
            continue                                  # the root name "." has no labels
        raw = label.encode("ascii")
        if len(raw) > 63:
            raise ValueError(f"label too long: {label!r}")
        out += bytes([len(raw)]) + raw                # length byte, then the characters
    return out + b"\x00"                              # the root's empty label ends the name


def build_query(name, qtype=TYPE_A, qid=None, recursion_desired=True):
    """Return a complete DNS query packet (header + one question) as bytes."""
    if qid is None:
        qid = random.randrange(65536)
    flags = 0x0100 if recursion_desired else 0x0000   # only the RD bit may be set
    header = struct.pack("!HHHHHH", qid, flags,
                         1,      # QDCOUNT: one question
                         0, 0, 0)  # ANCOUNT, NSCOUNT, ARCOUNT
    question = encode_name(name) + struct.pack("!HH", qtype, CLASS_IN)
    return header + question


# ---------------------------------------------------------------------------
# Milestone 2: parse a response.
# ---------------------------------------------------------------------------

def decode_name(buf, offset):
    """Read a possibly-compressed name starting at buf[offset].

    Returns (name, next_offset) where next_offset is where the bytes after this
    name begin *in the original position* (after the first pointer, if any).
    """
    labels = []
    next_offset = None           # set at the first pointer; the name "ends" there
    jumps = 0
    while True:
        if offset >= len(buf):
            raise DNSError("name runs past the end of the packet")
        length = buf[offset]
        if length == 0:                                    # end of name
            offset += 1
            break
        if length & 0xC0 == 0xC0:                          # compression pointer
            if offset + 1 >= len(buf):
                raise DNSError("truncated compression pointer")
            if next_offset is None:
                next_offset = offset + 2
            offset = ((length & 0x3F) << 8) | buf[offset + 1]
            jumps += 1
            if jumps > 20:                                 # a pointer loop
                raise DNSError("too many compression pointers (loop?)")
            continue
        if length & 0xC0:
            raise DNSError("unsupported label type")
        start = offset + 1
        if start + length > len(buf):
            raise DNSError("label runs past the end of the packet")
        labels.append(buf[start:start + length].decode("ascii", "replace"))
        offset = start + length
    return ".".join(labels), (next_offset if next_offset is not None else offset)


def parse_record(buf, offset):
    """Parse one resource record. Returns (Record, next_offset)."""
    name, offset = decode_name(buf, offset)
    if offset + 10 > len(buf):
        raise DNSError("truncated record header")
    rtype, rclass, ttl, rdlength = struct.unpack("!HHIH", buf[offset:offset + 10])
    offset += 10
    end = offset + rdlength
    if end > len(buf):
        raise DNSError("record data runs past the end of the packet")
    if rtype == TYPE_A and rdlength == 4:
        rdata = socket.inet_ntoa(buf[offset:end])
    elif rtype == TYPE_AAAA and rdlength == 16:
        rdata = str(ipaddress.IPv6Address(buf[offset:end]))
    elif rtype in (TYPE_NS, TYPE_CNAME, TYPE_PTR):
        rdata, _ = decode_name(buf, offset)               # may contain pointers into buf
    elif rtype == TYPE_MX:
        (preference,) = struct.unpack("!H", buf[offset:offset + 2])
        exchange, _ = decode_name(buf, offset + 2)
        rdata = (preference, exchange)
    elif rtype == TYPE_TXT:
        strings, i = [], offset
        while i < end:                                    # length-prefixed strings
            n = buf[i]
            strings.append(buf[i + 1:i + 1 + n].decode("utf-8", "replace"))
            i += 1 + n
        rdata = strings
    else:
        rdata = bytes(buf[offset:end])                    # unknown type: keep the raw bytes
    return Record(name, rtype, rclass, ttl, rdata), end


def parse_message(data):
    """Parse a whole DNS message into a Message."""
    if len(data) < 12:
        raise DNSError("packet shorter than the 12-byte header")
    qid, flags, qd, an, ns, ar = struct.unpack("!HHHHHH", data[:12])
    offset = 12
    questions = []
    for _ in range(qd):
        name, offset = decode_name(data, offset)
        if offset + 4 > len(data):
            raise DNSError("truncated question")
        qtype, qclass = struct.unpack("!HH", data[offset:offset + 4])
        offset += 4
        questions.append(Question(name, qtype, qclass))
    sections = []
    for count in (an, ns, ar):                            # answers, authority, additional
        records = []
        for _ in range(count):
            rec, offset = parse_record(data, offset)
            records.append(rec)
        sections.append(records)
    return Message(qid, flags, questions, *sections)


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
    """Send one query to `server` over UDP and return the parsed reply."""
    qid = random.randrange(65536)
    packet = build_query(name, qtype, qid=qid, recursion_desired=recursion_desired)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.sendto(packet, (server, port))
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise DNSTimeout(f"no reply from {server} within {timeout} s")
            sock.settimeout(remaining)
            try:
                data, addr = sock.recvfrom(4096)
            except socket.timeout:
                raise DNSTimeout(f"no reply from {server} within {timeout} s")
            if addr[0] != server:                         # not from who we asked
                continue
            if len(data) < 12 or struct.unpack("!H", data[:2])[0] != qid:
                continue                                  # wrong ID: stray or forged
            break
    if data[2] & 0x02:                                    # TC bit: the reply didn't fit in UDP
        return query_tcp(server, name, qtype, port, timeout, recursion_desired)
    return parse_message(data)


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
    """Resolve `name` by walking the DNS tree from a root server.

    query_fn(server_ip, name, qtype) -> Message. `trace(line)` is called with
    a human-readable line for each step. Returns the list of answer Records.
    """
    say = trace or (lambda line: None)
    if _depth > MAX_DEPTH:
        raise DNSError("too many nested lookups")
    label = type_name(qtype)
    servers = [ip for _, ip in roots]
    zone = "."
    for _ in range(MAX_REFERRALS):
        # Ask the servers of the current zone, one at a time, until one replies.
        msg = None
        for server in servers:
            say(f"{'  ' * _depth}ask {server} ({zone}) for {name} {label}")
            try:
                msg = query_fn(server, name, qtype)
                break
            except (DNSError, OSError) as e:
                say(f"{'  ' * _depth}  no answer from {server}: {e}")
        if msg is None:
            raise DNSError(f"no name server for {zone} answered")
        if msg.rcode == 3:
            raise DNSError(f"NXDOMAIN: {name} does not exist")
        if msg.rcode != 0:
            raise DNSError(f"server returned {RCODE_NAMES.get(msg.rcode, msg.rcode)}")

        if msg.answers:
            say(f"{'  ' * _depth}  answer: {len(msg.answers)} record(s)")
            have = [r for r in msg.answers if r.rtype == qtype]
            cnames = [r for r in msg.answers if r.rtype == TYPE_CNAME]
            if have or qtype == TYPE_CNAME or not cnames:
                return msg.answers
            # Milestone 6: only a CNAME came back. Start over for the target name.
            target = cnames[-1].rdata
            say(f"{'  ' * _depth}  {name} is an alias for {target}; resolving that")
            return msg.answers + resolve_iterative(target, qtype, query_fn, roots, trace, _depth + 1)

        # No answer: is it a referral? Look for NS records in the authority section.
        ns_records = [r for r in msg.authority if r.rtype == TYPE_NS]
        if not ns_records:
            say(f"{'  ' * _depth}  the name exists but has no {label} records")
            return []
        glue = {}
        for r in msg.additional:
            if r.rtype == TYPE_A:
                glue.setdefault(r.name.lower(), []).append(r.rdata)
        servers = [ip for r in ns_records for ip in glue.get(r.rdata.lower(), [])]
        zone = ns_records[0].name
        with_glue = sum(1 for r in ns_records if r.rdata.lower() in glue)
        say(f"{'  ' * _depth}  referral to {zone}: {len(ns_records)} name servers, "
            f"{with_glue} with glue (e.g. {ns_records[0].rdata})")
        if not servers:
            # No glue: we must look up a name server's address ourselves.
            for r in ns_records:
                say(f"{'  ' * _depth}  no glue; resolving the name server {r.rdata} first")
                try:
                    found = resolve_iterative(r.rdata, TYPE_A, query_fn, roots, trace, _depth + 1)
                except DNSError:
                    continue
                servers = [a.rdata for a in found if a.rtype == TYPE_A]
                if servers:
                    break
            if not servers:
                raise DNSError(f"could not find an address for any {zone} name server")
    raise DNSError("too many referrals (loop?)")


# ---------------------------------------------------------------------------
# Milestone 5: a TTL cache.
# ---------------------------------------------------------------------------

class TTLCache:
    """Remember lists of Records until their TTL runs out."""

    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self._items = {}                    # key -> (expires_at, records)

    def put(self, key, records):
        ttl = min((r.ttl for r in records), default=0)
        if ttl <= 0:
            return                          # TTL 0 means "do not cache"
        self._items[key] = (self.clock() + ttl, records)

    def get(self, key):
        item = self._items.get(key)
        if item is None:
            return None
        expires_at, records = item
        remaining = expires_at - self.clock()
        if remaining <= 0:
            del self._items[key]            # expired
            return None
        left = math.ceil(remaining)         # whole seconds remaining
        return [r._replace(ttl=left) for r in records]


class CachingResolver:
    """An iterative resolver that remembers answers."""

    def __init__(self, query_fn=ask_server, roots=ROOT_SERVERS, clock=time.monotonic, trace=None):
        self.query_fn, self.roots, self.trace = query_fn, roots, trace
        self.cache = TTLCache(clock)

    def resolve(self, name, qtype=TYPE_A):
        key = (name.lower().rstrip("."), qtype)
        hit = self.cache.get(key)
        if hit is not None:
            if self.trace:
                self.trace(f"cache hit for {name} {type_name(qtype)}")
            return hit
        answers = resolve_iterative(name, qtype, self.query_fn, self.roots, self.trace)
        self.cache.put(key, answers)
        return answers


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
