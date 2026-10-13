"""Self-check for Lab 3.

    python3 check.py              # checks your starter.py
    python3 check.py solution     # checks the reference solution
    python3 check.py --offline    # (either one) skip the online section entirely

The milestones run OFFLINE. They use real DNS replies that were recorded once
and are stored below as base64, plus a few hand-built packets, so they work on
any network, including ones that block outbound UDP port 53.

After the milestones, a clearly separate ONLINE section talks to real servers.
It is skipped (not failed) when the network can't be reached.
"""
import base64
import importlib
import random
import socket
import struct
import sys
import threading
import time

args = [a for a in sys.argv[1:] if not a.startswith("--")]
OFFLINE_ONLY = "--offline" in sys.argv
target = args[0] if args else "starter"
mod = importlib.import_module(target)
results = []
online_results = []


class NotStarted(Exception):
    pass


def run(name, fn, bucket):
    try:
        note = fn()
        print(f"  ✔ {name}" + (f"  ({note})" if note else ""))
        bucket.append(True)
    except (NotImplementedError, NotStarted) as e:
        print(f"  … {name}: not implemented yet ({e})")
        bucket.append(False)
    except AssertionError as e:
        print(f"  ✘ {name}: {e}")
        bucket.append(False)
    except Exception as e:  # anything else is a bug worth seeing
        print(f"  ✘ {name}: {type(e).__name__}: {e}")
        bucket.append(False)


def check(name, fn):
    run(name, fn, results)


def run_online(name, fn):
    """Like run(), but trouble that looks like the NETWORK's fault is a skip, not a failure."""
    try:
        note = fn()
        print(f"  ✔ {name}" + (f"  ({note})" if note else ""))
        online_results.append(True)
    except (NotImplementedError, NotStarted) as e:
        print(f"  … {name}: not implemented yet ({e})")
        online_results.append(False)
    except AssertionError as e:
        print(f"  ✘ {name}: {e}")
        online_results.append(False)
    except Exception as e:
        text = f"{type(e).__name__}: {e}"
        network_trouble = (isinstance(e, (OSError, getattr(mod, "DNSTimeout", OSError)))
                           or "SERVFAIL" in text or "REFUSED" in text)
        if network_trouble:
            print(f"  – skipped {name}: the network did not cooperate ({text})")
        else:
            print(f"  ✘ {name}: {text}")
            online_results.append(False)


# ---------------------------------------------------------------------------
# Recorded data (real replies; see the comment inside).
# ---------------------------------------------------------------------------

# Recorded 2026-10-12: real replies, fetched over TCP from the real servers (so no UDP size limit),
# stored here so the offline checks need no network. Keyed by (zone of the server asked, name, type).
ZONE_SERVERS = {
    '.': ['170.247.170.2', '192.112.36.4', '192.203.230.10', '192.33.4.12', '192.36.148.17', '192.5.5.241', '192.58.128.30', '193.0.14.129', '198.41.0.4', '198.97.190.53', '199.7.83.42', '199.7.91.13', '202.12.27.33'],
    'com': ['192.12.94.30', '192.26.92.30', '192.31.80.30', '192.33.14.30', '192.35.51.30', '192.41.162.30', '192.42.93.30', '192.43.172.30', '192.48.79.30', '192.5.6.30', '192.52.178.30', '192.54.112.30', '192.55.83.30'],
    'example.com': ['108.162.192.162', '108.162.195.228', '162.159.44.228', '172.64.32.162', '172.64.35.228', '173.245.58.162'],
    'org': ['199.19.53.1', '199.19.54.1', '199.19.56.1', '199.19.57.1', '199.249.112.1', '199.249.120.1'],
    'cloudflare.com': ['162.159.0.33', '162.159.1.33', '162.159.2.9', '162.159.3.11', '162.159.4.8', '162.159.5.6', '162.159.6.6', '162.159.7.226', '162.159.8.55', '162.159.9.55'],
    'example.org': ['108.162.193.208', '108.162.194.235', '162.159.38.235', '172.64.33.208', '172.64.34.235', '173.245.59.208'],
}
RECORDED = {
    ('.', 'example.com', 1): (
        'AACAAAABAAAADQAaB2V4YW1wbGUDY29tAAABAAHAFAACAAEAAqMAABQBbAxndGxkLXNlcnZl'
        'cnMDbmV0AMAUAAIAAQACowAABAFqwCvAFAACAAEAAqMAAAQBaMArwBQAAgABAAKjAAAEAWTA'
        'K8AUAAIAAQACowAABAFiwCvAFAACAAEAAqMAAAQBZsArwBQAAgABAAKjAAAEAWvAK8AUAAIA'
        'AQACowAABAFtwCvAFAACAAEAAqMAAAQBacArwBQAAgABAAKjAAAEAWfAK8AUAAIAAQACowAA'
        'BAFhwCvAFAACAAEAAqMAAAQBY8ArwBQAAgABAAKjAAAEAWXAK8ApAAEAAQACowAABMApoh7A'
        'KQAcAAEAAqMAABAgAQUA2TcAAAAAAAAAAAAwwEkAAQABAAKjAAAEwDBPHsBJABwAAQACowAA'
        'ECABBQJwlAAAAAAAAAAAADDAWQABAAEAAqMAAATANnAewFkAHAABAAKjAAAQIAEFAgjMAAAA'
        'AAAAAAAAMMBpAAEAAQACowAABMAfUB7AaQAcAAEAAqMAABAgAQUAhW4AAAAAAAAAAAAwwHkA'
        'AQABAAKjAAAEwCEOHsB5ABwAAQACowAAECABBQMjHQAAAAAAAAACADDAiQABAAEAAqMAAATA'
        'IzMewIkAHAABAAKjAAAQIAEFA9QUAAAAAAAAAAAAMMCZAAEAAQACowAABMA0sh7AmQAcAAEA'
        'AqMAABAgAQUDDS0AAAAAAAAAAAAwwKkAAQABAAKjAAAEwDdTHsCpABwAAQACowAAECABBQGx'
        '+QAAAAAAAAAAADDAuQABAAEAAqMAAATAK6wewLkAHAABAAKjAAAQIAEFAznBAAAAAAAAAAAA'
        'MMDJAAEAAQACowAABMAqXR7AyQAcAAEAAqMAABAgAQUD7qMAAAAAAAAAAAAwwNkAAQABAAKj'
        'AAAEwAUGHsDZABwAAQACowAAECABBQOoPgAAAAAAAAACADDA6QABAAEAAqMAAATAGlwewOkA'
        'HAABAAKjAAAQIAEFA4PrAAAAAAAAAAAAMMD5AAEAAQACowAABMAMXh7A+QAcAAEAAqMAABAg'
        'AQUCHKEAAAAAAAAAAAAw'
    ),
    ('com', 'example.com', 1): (
        'AACAAAABAAAAAgAMB2V4YW1wbGUDY29tAAABAAHADAACAAEAAqMAABUEaGVyYQJucwpjbG91'
        'ZGZsYXJlwBTADAACAAEAAqMAAAoHZWxsaW90dMAuwCkAAQABAAKjAAAEbKLAosApAAEAAQAC'
        'owAABKxAIKLAKQABAAEAAqMAAASt9TqiwCkAHAABAAKjAAAQJgZHAABQAAAAAAAArfU6osAp'
        'ABwAAQACowAAECgD+AAAUAAAAAAAAGyiwKLAKQAcAAEAAqMAABAqBpjBAFAAAAAAAACsQCCi'
        'wEoAAQABAAKjAAAEbKLD5MBKAAEAAQACowAABKKfLOTASgABAAEAAqMAAASsQCPkwEoAHAAB'
        'AAKjAAAQJgZHAABYAAAAAAAAop8s5MBKABwAAQACowAAECgD+AAAUAAAAAAAAGyiw+TASgAc'
        'AAEAAqMAABAqBpjBAFAAAAAAAACsQCPk'
    ),
    ('example.com', 'example.com', 1): (
        'AACEAAABAAIAAAAAB2V4YW1wbGUDY29tAAABAAHADAABAAEAAAEsAASsQpPzwAwAAQABAAAB'
        'LAAEaBQXmg=='
    ),
    ('.', 'example.org', 1): (
        'AACAAAABAAAABgAMB2V4YW1wbGUDb3JnAAABAAHAFAACAAEAAqMAABkCYTIDb3JnC2FmaWxp'
        'YXMtbnN0BGluZm8AwBQAAgABAAKjAAAVAmIyA29yZwthZmlsaWFzLW5zdMAUwBQAAgABAAKj'
        'AAAFAmQwwFHAFAACAAEAAqMAAAUCYTDALMAUAAIAAQACowAABQJiMMBRwBQAAgABAAKjAAAF'
        'AmMwwCzAKQABAAEAAqMAAATH+XABwCkAHAABAAKjAAAQIAEFAABAAAAAAAAAAAAAAcBOAAEA'
        'AQACowAABMf5eAHATgAcAAEAAqMAABAgAQUAAEgAAAAAAAAAAAABwG8AAQABAAKjAAAExxM5'
        'AcBvABwAAQACowAAECABBQAADwAAAAAAAAAAAAHAgAABAAEAAqMAAATHEzgBwIAAHAABAAKj'
        'AAAQIAEFAAAOAAAAAAAAAAAAAcCRAAEAAQACowAABMcTNgHAkQAcAAEAAqMAABAgAQUAAAwA'
        'AAAAAAAAAAABwKIAAQABAAKjAAAExxM1AcCiABwAAQACowAAECABBQAACwAAAAAAAAAAAAE='
    ),
    ('org', 'example.org', 1): (
        'AACAAAABAAAAAgAAB2V4YW1wbGUDb3JnAAABAAHADAACAAEAAA4QABkFbWl0Y2gCbnMKY2xv'
        'dWRmbGFyZQNjb20AwAwAAgABAAAOEAAKB2thdGVseW7ALw=='
    ),
    ('.', 'mitch.ns.cloudflare.com', 1): (
        'AACAAAABAAAADQAaBW1pdGNoAm5zCmNsb3VkZmxhcmUDY29tAAABAAHAIAACAAEAAqMAABQB'
        'bAxndGxkLXNlcnZlcnMDbmV0AMAgAAIAAQACowAABAFqwDfAIAACAAEAAqMAAAQBaMA3wCAA'
        'AgABAAKjAAAEAWTAN8AgAAIAAQACowAABAFiwDfAIAACAAEAAqMAAAQBZsA3wCAAAgABAAKj'
        'AAAEAWvAN8AgAAIAAQACowAABAFtwDfAIAACAAEAAqMAAAQBacA3wCAAAgABAAKjAAAEAWfA'
        'N8AgAAIAAQACowAABAFhwDfAIAACAAEAAqMAAAQBY8A3wCAAAgABAAKjAAAEAWXAN8A1AAEA'
        'AQACowAABMApoh7ANQAcAAEAAqMAABAgAQUA2TcAAAAAAAAAAAAwwFUAAQABAAKjAAAEwDBP'
        'HsBVABwAAQACowAAECABBQJwlAAAAAAAAAAAADDAZQABAAEAAqMAAATANnAewGUAHAABAAKj'
        'AAAQIAEFAgjMAAAAAAAAAAAAMMB1AAEAAQACowAABMAfUB7AdQAcAAEAAqMAABAgAQUAhW4A'
        'AAAAAAAAAAAwwIUAAQABAAKjAAAEwCEOHsCFABwAAQACowAAECABBQMjHQAAAAAAAAACADDA'
        'lQABAAEAAqMAAATAIzMewJUAHAABAAKjAAAQIAEFA9QUAAAAAAAAAAAAMMClAAEAAQACowAA'
        'BMA0sh7ApQAcAAEAAqMAABAgAQUDDS0AAAAAAAAAAAAwwLUAAQABAAKjAAAEwDdTHsC1ABwA'
        'AQACowAAECABBQGx+QAAAAAAAAAAADDAxQABAAEAAqMAAATAK6wewMUAHAABAAKjAAAQIAEF'
        'AznBAAAAAAAAAAAAMMDVAAEAAQACowAABMAqXR7A1QAcAAEAAqMAABAgAQUD7qMAAAAAAAAA'
        'AAAwwOUAAQABAAKjAAAEwAUGHsDlABwAAQACowAAECABBQOoPgAAAAAAAAACADDA9QABAAEA'
        'AqMAAATAGlwewPUAHAABAAKjAAAQIAEFA4PrAAAAAAAAAAAAMMEFAAEAAQACowAABMAMXh7B'
        'BQAcAAEAAqMAABAgAQUCHKEAAAAAAAAAAAAw'
    ),
    ('com', 'mitch.ns.cloudflare.com', 1): (
        'AACAAAABAAAABQAUBW1pdGNoAm5zCmNsb3VkZmxhcmUDY29tAAABAAHAFQACAAEAAqMAAAYD'
        'bnMzwBXAFQACAAEAAqMAAAYDbnM1wBXAFQACAAEAAqMAAAYDbnM0wBXAFQACAAEAAqMAAAYD'
        'bnM2wBXAFQACAAEAAqMAAAYDbnM3wBXANQABAAEAAqMAAASinwAhwDUAAQABAAKjAAAEop8H'
        '4sA1ABwAAQACowAAECQAywAgSQABAAAAAKKfACHANQAcAAEAAqMAABAkAMsAIEkAAQAAAACi'
        'nwfiwEcAAQABAAKjAAAEop8CCcBHAAEAAQACowAABKKfCTfARwAcAAEAAqMAABAkAMsAIEkA'
        'AQAAAACinwIJwEcAHAABAAKjAAAQJADLACBJAAEAAAAAop8JN8BZAAEAAQACowAABKKfASHA'
        'WQABAAEAAqMAAASinwg3wFkAHAABAAKjAAAQJADLACBJAAEAAAAAop8BIcBZABwAAQACowAA'
        'ECQAywAgSQABAAAAAKKfCDfAawABAAEAAqMAAASinwMLwGsAAQABAAKjAAAEop8FBsBrABwA'
        'AQACowAAECQAywAgSQABAAAAAKKfAwvAawAcAAEAAqMAABAkAMsAIEkAAQAAAACinwUGwH0A'
        'AQABAAKjAAAEop8ECMB9AAEAAQACowAABKKfBgbAfQAcAAEAAqMAABAkAMsAIEkAAQAAAACi'
        'nwQIwH0AHAABAAKjAAAQJADLACBJAAEAAAAAop8GBg=='
    ),
    ('cloudflare.com', 'mitch.ns.cloudflare.com', 1): (
        'AACEAAABAAMAAAAABW1pdGNoAm5zCmNsb3VkZmxhcmUDY29tAAABAAHADAABAAEAAVFRAARs'
        'osHQwAwAAQABAAFRUQAErEAh0MAMAAEAAQABUVEABK31O9A='
    ),
    ('example.org', 'example.org', 1): (
        'AACEAAABAAIAAAAAB2V4YW1wbGUDb3JnAAABAAHADAABAAEAAAEsAARoFBqIwAwAAQABAAAB'
        'LAAErEKd7Q=='
    ),
    ('.', 'katelyn.ns.cloudflare.com', 1): (
        'AACAAAABAAAADQAaB2thdGVseW4CbnMKY2xvdWRmbGFyZQNjb20AAAEAAcAiAAIAAQACowAA'
        'FAFsDGd0bGQtc2VydmVycwNuZXQAwCIAAgABAAKjAAAEAWrAOcAiAAIAAQACowAABAFowDnA'
        'IgACAAEAAqMAAAQBZMA5wCIAAgABAAKjAAAEAWLAOcAiAAIAAQACowAABAFmwDnAIgACAAEA'
        'AqMAAAQBa8A5wCIAAgABAAKjAAAEAW3AOcAiAAIAAQACowAABAFpwDnAIgACAAEAAqMAAAQB'
        'Z8A5wCIAAgABAAKjAAAEAWHAOcAiAAIAAQACowAABAFjwDnAIgACAAEAAqMAAAQBZcA5wDcA'
        'AQABAAKjAAAEwCmiHsA3ABwAAQACowAAECABBQDZNwAAAAAAAAAAADDAVwABAAEAAqMAAATA'
        'ME8ewFcAHAABAAKjAAAQIAEFAnCUAAAAAAAAAAAAMMBnAAEAAQACowAABMA2cB7AZwAcAAEA'
        'AqMAABAgAQUCCMwAAAAAAAAAAAAwwHcAAQABAAKjAAAEwB9QHsB3ABwAAQACowAAECABBQCF'
        'bgAAAAAAAAAAADDAhwABAAEAAqMAAATAIQ4ewIcAHAABAAKjAAAQIAEFAyMdAAAAAAAAAAIA'
        'MMCXAAEAAQACowAABMAjMx7AlwAcAAEAAqMAABAgAQUD1BQAAAAAAAAAAAAwwKcAAQABAAKj'
        'AAAEwDSyHsCnABwAAQACowAAECABBQMNLQAAAAAAAAAAADDAtwABAAEAAqMAAATAN1MewLcA'
        'HAABAAKjAAAQIAEFAbH5AAAAAAAAAAAAMMDHAAEAAQACowAABMArrB7AxwAcAAEAAqMAABAg'
        'AQUDOcEAAAAAAAAAAAAwwNcAAQABAAKjAAAEwCpdHsDXABwAAQACowAAECABBQPuowAAAAAA'
        'AAAAADDA5wABAAEAAqMAAATABQYewOcAHAABAAKjAAAQIAEFA6g+AAAAAAAAAAIAMMD3AAEA'
        'AQACowAABMAaXB7A9wAcAAEAAqMAABAgAQUDg+sAAAAAAAAAAAAwwQcAAQABAAKjAAAEwAxe'
        'HsEHABwAAQACowAAECABBQIcoQAAAAAAAAAAADA='
    ),
    ('com', 'katelyn.ns.cloudflare.com', 1): (
        'AACAAAABAAAABQAUB2thdGVseW4CbnMKY2xvdWRmbGFyZQNjb20AAAEAAcAXAAIAAQACowAA'
        'BgNuczPAF8AXAAIAAQACowAABgNuczXAF8AXAAIAAQACowAABgNuczTAF8AXAAIAAQACowAA'
        'BgNuczbAF8AXAAIAAQACowAABgNuczfAF8A3AAEAAQACowAABKKfACHANwABAAEAAqMAAASi'
        'nwfiwDcAHAABAAKjAAAQJADLACBJAAEAAAAAop8AIcA3ABwAAQACowAAECQAywAgSQABAAAA'
        'AKKfB+LASQABAAEAAqMAAASinwIJwEkAAQABAAKjAAAEop8JN8BJABwAAQACowAAECQAywAg'
        'SQABAAAAAKKfAgnASQAcAAEAAqMAABAkAMsAIEkAAQAAAACinwk3wFsAAQABAAKjAAAEop8B'
        'IcBbAAEAAQACowAABKKfCDfAWwAcAAEAAqMAABAkAMsAIEkAAQAAAACinwEhwFsAHAABAAKj'
        'AAAQJADLACBJAAEAAAAAop8IN8BtAAEAAQACowAABKKfAwvAbQABAAEAAqMAAASinwUGwG0A'
        'HAABAAKjAAAQJADLACBJAAEAAAAAop8DC8BtABwAAQACowAAECQAywAgSQABAAAAAKKfBQbA'
        'fwABAAEAAqMAAASinwQIwH8AAQABAAKjAAAEop8GBsB/ABwAAQACowAAECQAywAgSQABAAAA'
        'AKKfBAjAfwAcAAEAAqMAABAkAMsAIEkAAQAAAACinwYG'
    ),
    ('cloudflare.com', 'katelyn.ns.cloudflare.com', 1): (
        'AACEAAABAAMAAAAAB2thdGVseW4CbnMKY2xvdWRmbGFyZQNjb20AAAEAAcAMAAEAAQABUVEA'
        'BKKfJuvADAABAAEAAVFRAASsQCLrwAwAAQABAAFRUQAEbKLC6w=='
    ),
}

IP_ZONE = {ip: zone for zone, ips in ZONE_SERVERS.items() for ip in ips}


def recorded(zone, name, qtype=1):
    return base64.b64decode(RECORDED[(zone, name, qtype)])


def patch_id(raw, qid):
    return struct.pack("!H", qid) + raw[2:]


# ---------------------------------------------------------------------------
# A tiny independent DNS packet BUILDER, used only to make test packets.
# (It is deliberately separate from your code, so a bug in yours can't hide.)
# ---------------------------------------------------------------------------

def _enc(name, out, seen):
    labels = [l for l in name.strip(".").split(".") if l]
    while labels:
        suffix = ".".join(labels).lower()
        if suffix in seen:
            out += struct.pack("!H", 0xC000 | seen[suffix])      # compression pointer
            return
        seen[suffix] = len(out)
        out.append(len(labels[0]))
        out += labels[0].encode()
        labels = labels[1:]
    out.append(0)


def build_response(qid, qname, qtype, answers=(), authority=(), additional=(),
                   rcode=0, aa=True, tc=False):
    """Records are (name, type, ttl, data); data depends on the type."""
    out, seen = bytearray(), {}
    flags = 0x8100 | (0x0400 if aa else 0) | (0x0200 if tc else 0) | rcode
    out += struct.pack("!HHHHHH", qid, flags, 1, len(answers), len(authority), len(additional))
    _enc(qname, out, seen)
    out += struct.pack("!HH", qtype, 1)
    for name, rtype, ttl, data in list(answers) + list(authority) + list(additional):
        _enc(name, out, seen)
        out += struct.pack("!HHI", rtype, 1, ttl)
        lenpos = len(out)
        out += b"\x00\x00"
        if rtype == 1:
            out += socket.inet_aton(data)
        elif rtype == 28:
            out += socket.inet_pton(socket.AF_INET6, data)
        elif rtype in (2, 5, 12):
            _enc(data, out, seen)
        elif rtype == 15:
            out += struct.pack("!H", data[0])
            _enc(data[1], out, seen)
        elif rtype == 16:
            for s in data:
                out.append(len(s.encode()))
                out += s.encode()
        else:
            out += data
        struct.pack_into("!H", out, lenpos, len(out) - lenpos - 2)
    return bytes(out)


def parse_query(packet):
    """Minimal query reader for the fake servers: (id, flags, qdcount, name, qtype)."""
    qid, flags, qd = struct.unpack("!HHH", packet[:6])
    labels, i = [], 12
    while packet[i]:
        labels.append(packet[i + 1:i + 1 + packet[i]].decode())
        i += 1 + packet[i]
    (qtype,) = struct.unpack("!H", packet[i + 1:i + 3])
    return qid, flags, qd, ".".join(labels), qtype


# ---------------------------------------------------------------------------
# Fake "networks" for the resolver tests.
# ---------------------------------------------------------------------------

class FakeNet:
    """Answers resolver queries from the recorded real replies."""

    def __init__(self, blocked=()):
        self.log = []
        self.blocked = set(blocked)

    def __call__(self, server, name, qtype=1):
        name = name.lower().rstrip(".")
        self.log.append((server, name, qtype))
        zone = IP_ZONE.get(server)
        assert zone is not None, (f"your resolver asked {server}, which no referral or "
                                  f"root list ever mentioned")
        if server in self.blocked:
            raise mod.DNSTimeout(f"simulated outage of {server}")
        key = (zone, name, qtype)
        if key not in RECORDED:
            raise mod.DNSTimeout(f"(fake network) {server} serves {zone!r}, which has no "
                                 f"recorded reply for {name}")
        return mod.parse_message(patch_id(recorded(*key), random.randrange(65536)))


class ScriptedNet:
    """Answers queries with packets built by handler(name, qtype) -> dict for build_response."""

    def __init__(self, handler):
        self.handler, self.log = handler, []

    def __call__(self, server, name, qtype=1):
        name = name.lower().rstrip(".")
        self.log.append((server, name, qtype))
        return mod.parse_message(build_response(0x4242, name, qtype, **self.handler(name, qtype)))


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


class FakeDNS:
    """A fake DNS server on 127.0.0.1 (UDP and TCP on the same port) for milestone 3."""

    def __init__(self, mode):
        self.mode, self.seen, self.errors, self.stop = mode, [], [], False
        for _ in range(50):
            self.udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp.bind(("127.0.0.1", 0))
            self.port = self.udp.getsockname()[1]
            self.tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                self.tcp.bind(("127.0.0.1", self.port))
                break
            except OSError:
                self.udp.close()
                self.tcp.close()
        self.tcp.listen()
        self.udp.settimeout(0.1)
        self.tcp.settimeout(0.1)
        threading.Thread(target=self._guard, args=(self._serve_udp,), daemon=True).start()
        threading.Thread(target=self._guard, args=(self._serve_tcp,), daemon=True).start()

    def _guard(self, fn):
        try:
            fn()
        except BaseException as e:
            self.errors.append(e)

    def _answer(self, qid):
        return patch_id(recorded("example.com", "example.com"), qid)

    def _serve_udp(self):
        while not self.stop:
            try:
                data, addr = self.udp.recvfrom(2048)
            except socket.timeout:
                continue
            except OSError:
                return
            qid, flags, qd, name, qtype = parse_query(data)
            self.seen.append((qid, flags, qd, name, qtype))
            if self.mode == "silent":
                continue
            if self.mode == "tc":
                self.udp.sendto(build_response(qid, name, qtype, tc=True), addr)
                continue
            # A stray reply with the wrong ID arrives first: a careful client ignores it.
            decoy = build_response((qid + 1) & 0xFFFF, name, qtype,
                                   answers=[(name, 1, 300, "192.0.2.99")])
            self.udp.sendto(decoy, addr)
            time.sleep(0.05)
            self.udp.sendto(self._answer(qid), addr)

    def _serve_tcp(self):
        while not self.stop:
            try:
                conn, _ = self.tcp.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            with conn:
                conn.settimeout(2)
                (length,) = struct.unpack("!H", conn.recv(2))
                query = b""
                while len(query) < length:
                    query += conn.recv(length - len(query))
                self.seen.append(("tcp",) + parse_query(query))
                reply = self._answer(parse_query(query)[0])
                conn.sendall(struct.pack("!H", len(reply)) + reply)

    def close(self):
        self.stop = True
        self.udp.close()
        self.tcp.close()


# --- Milestone 1 ----------------------------------------------------------------

def m1():
    assert mod.encode_name("example.com") == b"\x07example\x03com\x00", \
        f"encode_name('example.com') gave {mod.encode_name('example.com')!r}"
    assert mod.encode_name("example.com.") == mod.encode_name("example.com"), "a trailing dot must not matter"
    assert mod.encode_name("a.b.c") == b"\x01a\x01b\x01c\x00"
    assert mod.encode_name(".") == b"\x00", f"the root name should be a single zero byte, got {mod.encode_name('.')!r}"
    try:
        mod.encode_name("x" * 64 + ".com")
    except ValueError:
        pass
    else:
        raise AssertionError("a label longer than 63 bytes must raise ValueError")
    want = bytes.fromhex("1234 0100 0001 0000 0000 0000"
                         "07 6578616d706c65 03 636f6d 00 0001 0001")
    got = mod.build_query("example.com", mod.TYPE_A, qid=0x1234)
    assert got == want, f"query bytes differ.\n    expected {want.hex(' ')}\n    got      {got.hex(' ')}"
    aaaa = mod.build_query("example.com", mod.TYPE_AAAA, qid=0xBEEF)
    assert aaaa[:2] == b"\xbe\xef" and aaaa[-4:] == bytes.fromhex("001c 0001"), \
        "AAAA is type 28 (0x001c), class IN (1), at the end of the packet"
    norec = mod.build_query("example.com", qid=1, recursion_desired=False)
    assert norec[2:4] == b"\x00\x00", f"with recursion_desired=False the flags must be 0x0000, got {norec[2:4].hex()}"
    q1 = mod.build_query("example.com")
    assert len(q1) == 29 and 0 <= struct.unpack("!H", q1[:2])[0] < 65536, "default qid should be a random 16-bit number"


# --- Milestone 2 ----------------------------------------------------------------

def m2():
    # decode_name on hand-made bytes
    buf = b"\x03www\x07example\x03com\x00" + b"\x03ftp\xc0\x04"
    assert mod.decode_name(buf, 0) == ("www.example.com", 17), f"plain name: {mod.decode_name(buf, 0)!r}"
    got = mod.decode_name(buf, 17)
    assert got == ("ftp.example.com", 23), \
        f"label + pointer: expected ('ftp.example.com', 23), got {got!r} (the offset after a pointer is 2 bytes on)"
    buf = b"\x03abc\x00" + b"\xc0\x00" + b"\xc0\x05"
    assert mod.decode_name(buf, 7) == ("abc", 9), f"pointer to a pointer: {mod.decode_name(buf, 7)!r}"
    assert mod.decode_name(b"\x00", 0) == ("", 1), "the root name decodes to the empty string"
    for evil, why in ((b"\xc0\x00", "a pointer to itself"), (b"\xc0\x02\xc0\x00", "two pointers pointing at each other"),
                      (b"\x05ab", "a label running off the end"), (b"\xc0", "half a pointer")):
        try:
            mod.decode_name(evil, 0)
        except mod.DNSError:
            pass
        except Exception as e:
            raise AssertionError(f"{why} should raise DNSError, not {type(e).__name__}")
        else:
            raise AssertionError(f"{why} should raise DNSError (never loop forever, never return)")

    # A real root-server referral for example.com.
    raw = recorded(".", "example.com")
    msg = mod.parse_message(raw)
    assert msg.id == 0 and msg.qr == 1 and msg.aa == 0 and msg.rcode == 0, \
        f"header: id={msg.id} qr={msg.qr} aa={msg.aa} rcode={msg.rcode}"
    assert [tuple(q) for q in msg.questions] == [("example.com", 1, 1)], f"questions: {msg.questions!r}"
    assert msg.answers == [], "a referral has no answers"
    assert len(msg.authority) == 13 and all(r.rtype == 2 and r.name == "com" and r.ttl == 172800
                                            for r in msg.authority), "13 NS records for 'com', TTL 172800"
    assert all(r.rdata.endswith(".gtld-servers.net") for r in msg.authority), \
        f"NS targets should decode via compression pointers, got {msg.authority[0].rdata!r}"
    a = [r for r in msg.additional if r.rtype == 1]
    aaaa = [r for r in msg.additional if r.rtype == 28]
    assert len(a) == 13 and len(aaaa) == 13, f"expected 13 A + 13 AAAA glue records, got {len(a)} + {len(aaaa)}"
    assert all(r.rdata.count(".") == 3 for r in a), f"A rdata should look like 192.0.2.1, got {a[0].rdata!r}"
    assert all(":" in r.rdata for r in aaaa), f"AAAA rdata should look like 2001:db8::1, got {aaaa[0].rdata!r}"
    names = {r.rdata for r in msg.authority}
    assert {r.name for r in a} == names, "glue records are named after the NS targets"

    # A real authoritative answer.
    msg = mod.parse_message(recorded("example.com", "example.com"))
    assert msg.aa == 1 and msg.rcode == 0, "an authoritative answer has the AA bit set"
    got = sorted((r.name, r.rtype, r.ttl, r.rdata) for r in msg.answers)
    want = [("example.com", 1, 300, "104.20.23.154"), ("example.com", 1, 300, "172.66.147.243")]
    assert got == want, f"answers: {got!r}"

    # Hand-built answers of other types, with compressed names inside the record data.
    pkt = build_response(7, "www.example.com", 5, answers=[
        ("www.example.com", 5, 60, "web.example.com"),
        ("web.example.com", 1, 30, "192.0.2.10"),
        ("example.com", 15, 3600, (10, "mail.example.com")),
        ("example.com", 16, 120, ["v=spf1 -all", "second string"]),
        ("example.com", 28, 90, "2001:db8::1"),
    ], authority=[("example.com", 2, 86400, "ns1.example.com")],
        additional=[("ns1.example.com", 1, 86400, "192.0.2.53")])
    assert b"\xc0" in pkt, "(test bug: the packet should contain compression pointers)"
    m = mod.parse_message(pkt)
    rd = [r.rdata for r in m.answers]
    assert rd[0] == "web.example.com", f"CNAME rdata: {rd[0]!r}"
    assert rd[1] == "192.0.2.10", f"A rdata: {rd[1]!r}"
    assert rd[2] == (10, "mail.example.com"), f"MX rdata should be (preference, exchange), got {rd[2]!r}"
    assert rd[3] == ["v=spf1 -all", "second string"], f"TXT rdata should be a list of strings, got {rd[3]!r}"
    assert rd[4] == "2001:db8::1", f"AAAA rdata: {rd[4]!r}"
    assert m.authority[0].rdata == "ns1.example.com" and m.additional[0].rdata == "192.0.2.53"

    # Damaged input must give DNSError, not IndexError or struct.error.
    for cut in (0, 5, 11, 12, 20, 60, len(raw) - 1):
        try:
            mod.parse_message(raw[:cut])
        except mod.DNSError:
            pass
        except Exception as e:
            raise AssertionError(f"a packet cut to {cut} bytes should raise DNSError, not {type(e).__name__}: {e}")
        else:
            raise AssertionError(f"a packet cut to {cut} bytes should raise DNSError, but it parsed")
    return "parsed real root, TLD-style and answer packets"


# --- Milestone 3 ----------------------------------------------------------------

def m3():
    srv = FakeDNS("ok")
    try:
        t = time.time()
        msg = mod.query_udp("127.0.0.1", "example.com", mod.TYPE_A, port=srv.port, timeout=3)
        assert isinstance(msg, mod.Message), f"query_udp should return a Message, got {type(msg).__name__}"
        ips = sorted(r.rdata for r in msg.answers)
        assert ips == ["104.20.23.154", "172.66.147.243"], \
            f"got {ips!r}; a reply with the wrong transaction ID (the decoy at 192.0.2.99) must be ignored"
        assert srv.seen, "the server never saw your query"
        qid, flags, qd, name, qtype = srv.seen[0]
        assert qd == 1 and name == "example.com" and qtype == 1, f"server saw {name!r} type {qtype} (qd={qd})"
        assert flags & 0x0100, "the RD (recursion desired) bit should be set by default"
        assert msg.id == qid, "the reply's ID must be the one in your query"
        mod.query_udp("127.0.0.1", "example.com", mod.TYPE_AAAA, port=srv.port, timeout=3, recursion_desired=False)
        _, flags, _, _, qtype = srv.seen[-1]
        assert qtype == 28 and not flags & 0x0100, "recursion_desired=False must clear the RD bit; qtype 28 = AAAA"
    finally:
        srv.close()
    assert not srv.errors, f"fake server crashed: {srv.errors[0]!r}"

    srv = FakeDNS("silent")
    try:
        t = time.time()
        try:
            mod.query_udp("127.0.0.1", "example.com", port=srv.port, timeout=0.4)
        except mod.DNSTimeout:
            pass
        except mod.DNSError as e:
            raise AssertionError(f"silence should raise DNSTimeout, got {type(e).__name__}")
        else:
            raise AssertionError("no reply ever came, so query_udp must raise DNSTimeout")
        took = time.time() - t
        assert 0.3 <= took <= 1.5, f"query_udp should give up after its timeout (0.4 s), took {took:.2f} s"
    finally:
        srv.close()

    srv = FakeDNS("tc")
    try:
        msg = mod.query_udp("127.0.0.1", "example.com", port=srv.port, timeout=3)
        assert sorted(r.rdata for r in msg.answers) == ["104.20.23.154", "172.66.147.243"], \
            "the UDP reply had the TC (truncated) bit set: retry over TCP with query_tcp"
        assert any(s[0] == "tcp" for s in srv.seen), "the server never saw a TCP query"
    finally:
        srv.close()
    assert not srv.errors, f"fake server crashed: {srv.errors[0]!r}"


# --- Milestone 4 ----------------------------------------------------------------

EXAMPLE_COM = ["104.20.23.154", "172.66.147.243"]


def m4():
    net = FakeNet()
    lines = []
    answers = mod.resolve_iterative("example.com", mod.TYPE_A, query_fn=net, trace=lines.append)
    assert sorted(r.rdata for r in answers if r.rtype == 1) == EXAMPLE_COM, f"answers: {answers!r}"
    zones = [IP_ZONE[s] for s, _, _ in net.log]
    assert zones == [".", "com", "example.com"], \
        f"expected one query each to a root, a com and an example.com server, but asked zones {zones!r}"
    assert len(lines) >= 3 and all(isinstance(l, str) for l in lines), \
        f"trace(line) should be called with a string for each step; it got {len(lines)} call(s)"

    # example.org's name servers (cloudflare) come WITHOUT glue from the .org servers.
    net = FakeNet()
    answers = mod.resolve_iterative("example.org", mod.TYPE_A, query_fn=net)
    assert sorted(r.rdata for r in answers) == ["104.20.26.136", "172.66.157.237"], f"answers: {answers!r}"
    assert any(n.endswith(".ns.cloudflare.com") for _, n, _ in net.log), \
        "the .org referral had NO glue: you must resolve a name server's own name (a recursive lookup) first"
    assert len(net.log) <= 12, f"that took {len(net.log)} queries; something is looping"

    # A dead root server must not stop the lookup.
    first_root = mod.ROOT_SERVERS[0][1]
    net = FakeNet(blocked=[first_root])
    answers = mod.resolve_iterative("example.com", mod.TYPE_A, query_fn=net)
    assert sorted(r.rdata for r in answers) == EXAMPLE_COM, "when one server times out, try the next one"

    # NXDOMAIN becomes an error.
    nx = ScriptedNet(lambda name, qtype: dict(rcode=3, authority=[("test", 6, 60, b"")]))
    try:
        mod.resolve_iterative("nope.example.test", mod.TYPE_A, query_fn=nx)
    except mod.DNSError:
        pass
    else:
        raise AssertionError("an NXDOMAIN reply (rcode 3) should raise DNSError")

    # A referral loop must end with an error, not run forever.
    loop = ScriptedNet(lambda name, qtype: dict(
        aa=False, authority=[("loop.test", 2, 60, "ns1.loop.test")], additional=[("ns1.loop.test", 1, 60, "192.0.2.53")]))
    try:
        mod.resolve_iterative("a.loop.test", mod.TYPE_A, query_fn=loop)
    except mod.DNSError:
        pass
    else:
        raise AssertionError("an endless chain of referrals should raise DNSError")
    assert len(loop.log) < 100, f"gave up only after {len(loop.log)} queries; cap the number of referrals"
    return f"{len(lines)} trace lines for example.com"


# --- Milestone 5 ----------------------------------------------------------------

def m5():
    rec = mod.Record
    clock = FakeClock()
    cache = mod.TTLCache(clock=clock)
    assert cache.get(("x", 1)) is None, "an empty cache returns None"
    cache.put(("x", 1), [rec("x", 1, 1, 300, "192.0.2.1"), rec("x", 1, 1, 100, "192.0.2.2")])
    got = cache.get(("x", 1))
    assert got is not None and [r.ttl for r in got] == [100, 100], \
        f"the whole set expires with its shortest TTL (100); got {got!r}"
    clock.now += 40
    assert [r.ttl for r in cache.get(("x", 1))] == [60, 60], "TTLs shown should count down (60 s left)"
    clock.now += 60
    assert cache.get(("x", 1)) is None, "after the TTL has passed the entry must be gone"
    cache.put(("zero", 1), [rec("zero", 1, 1, 0, "192.0.2.3")])
    assert cache.get(("zero", 1)) is None, "TTL 0 means: do not cache"

    net, clock = FakeNet(), FakeClock()
    lines = []
    r = mod.CachingResolver(query_fn=net, clock=clock, trace=lines.append)
    first = r.resolve("example.com")
    assert sorted(x.rdata for x in first) == EXAMPLE_COM and len(net.log) == 3, \
        f"first lookup: 3 queries expected, saw {len(net.log)}"
    again = r.resolve("example.com")
    assert len(net.log) == 3, f"the second lookup must come from the cache, but it sent {len(net.log) - 3} more queries"
    assert sorted(x.rdata for x in again) == EXAMPLE_COM
    assert any("cache" in l.lower() for l in lines), "trace a line mentioning 'cache' on a hit"
    clock.now += 100
    later = r.resolve("EXAMPLE.com.")
    assert len(net.log) == 3, "names are case-insensitive and a trailing dot changes nothing: still a cache hit"
    assert all(x.ttl == 200 for x in later), f"300 s TTL minus 100 s elapsed should be 200, got {[x.ttl for x in later]}"
    clock.now += 201
    r.resolve("example.com")
    assert len(net.log) == 6, f"after the TTL expired it must resolve again (6 queries total), saw {len(net.log)}"
    return "2nd lookup: 0 queries; after TTL expiry: resolved again"


# --- Milestone 6 (optional) -----------------------------------------------------

def m6():
    def handler(name, qtype):
        if name == "www.shop.test" and qtype in (1, 5):
            return dict(answers=[("www.shop.test", 5, 60, "edge.cdn.test")])
        if name == "edge.cdn.test" and qtype == 1:
            return dict(answers=[("edge.cdn.test", 1, 30, "192.0.2.7")])
        if name == "alias.test" and qtype == 1:      # the server follows its own CNAME
            return dict(answers=[("alias.test", 5, 60, "real.test"), ("real.test", 1, 30, "192.0.2.8")])
        if name == "a.loop.test":
            return dict(answers=[("a.loop.test", 5, 60, "b.loop.test")])
        if name == "b.loop.test":
            return dict(answers=[("b.loop.test", 5, 60, "a.loop.test")])
        return dict(rcode=3)

    net = ScriptedNet(handler)
    answers = mod.resolve_iterative("www.shop.test", mod.TYPE_A, query_fn=net)
    kinds = [(r.rtype, r.rdata) for r in answers]
    assert kinds == [(5, "edge.cdn.test"), (1, "192.0.2.7")], \
        f"expected the CNAME record followed by the A record, got {kinds!r}"
    assert [n for _, n, _ in net.log] == ["www.shop.test", "edge.cdn.test"], f"queries: {net.log!r}"

    net = ScriptedNet(handler)
    answers = mod.resolve_iterative("alias.test", mod.TYPE_A, query_fn=net)
    assert [r.rdata for r in answers] == ["real.test", "192.0.2.8"] and len(net.log) == 1, \
        "when the reply already contains the CNAME and the final A record, don't ask again"

    net = ScriptedNet(handler)
    answers = mod.resolve_iterative("www.shop.test", mod.TYPE_CNAME, query_fn=net)
    assert [r.rdata for r in answers] == ["edge.cdn.test"] and len(net.log) == 1, \
        "if the CNAME itself was asked for, a CNAME record IS the answer"

    net = ScriptedNet(handler)
    try:
        mod.resolve_iterative("a.loop.test", mod.TYPE_A, query_fn=net)
    except mod.DNSError:
        pass
    else:
        raise AssertionError("a CNAME loop (a -> b -> a) should raise DNSError")
    assert len(net.log) < 30, "limit how many CNAMEs you follow"


print(f"Lab 3 checks against {target}.py\n")
print("Offline milestones (recorded replies and hand-built packets; no network needed)")
check("Milestone 1: build a query packet", m1)
check("Milestone 2: parse a response (names, compression, records)", m2)
check("Milestone 3: query a server over UDP (local fake server)", m3)
check("Milestone 4: iterative resolution with referrals and glue", m4)
check("Milestone 5: TTL cache", m5)
check("Milestone 6 (optional): follow CNAMEs", m6)
passed = sum(results)
print(f"\n{passed}/{len(results)} offline milestones passing")


# ---------------------------------------------------------------------------
# ONLINE section: real servers. Skipped, not failed, when unreachable.
# ---------------------------------------------------------------------------

def raw_udp_probe(server="1.1.1.1"):
    """Can we get any DNS reply over UDP 53? (Uses plain sockets, not your code.)"""
    pkt = struct.pack("!HHHHHH", 0x5151, 0x0100, 1, 0, 0, 0) + b"\x07example\x03com\x00\x00\x01\x00\x01"
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(2.5)
    try:
        s.sendto(pkt, (server, 53))
        data, _ = s.recvfrom(4096)
        return len(data) >= 12 and data[:2] == b"\x51\x51"
    except OSError:
        return False
    finally:
        s.close()


def raw_tcp_probe(server="198.41.0.4"):
    try:
        socket.create_connection((server, 53), timeout=2.5).close()
        return True
    except OSError:
        return False


def o1():
    msg = mod.query_udp("1.1.1.1", "example.com", mod.TYPE_A, timeout=3)
    ips = [r.rdata for r in msg.answers if r.rtype == 1]
    assert msg.rcode == 0 and ips, f"expected NOERROR with at least one A record, got rcode {msg.rcode} and {ips!r}"
    assert all(len(ip.split(".")) == 4 for ip in ips)
    return ", ".join(ips)


def o2():
    lines = []
    answers = mod.resolve_iterative("example.com", mod.TYPE_A, trace=lines.append)
    ips = [r.rdata for r in answers if r.rtype == 1]
    assert ips, "iterative resolution from the roots found no A record"
    return f"{len(lines)} trace lines -> {', '.join(ips)}"


def o3():
    r = mod.CachingResolver()
    t = time.perf_counter()
    first = r.resolve("example.com")
    t1 = (time.perf_counter() - t) * 1000
    t = time.perf_counter()
    second = r.resolve("example.com")
    t2 = (time.perf_counter() - t) * 1000
    assert [x.rdata for x in first] == [x.rdata for x in second]
    assert t2 < 5, f"the cached lookup should take well under 5 ms, took {t2:.2f} ms"
    return f"first {t1:.1f} ms, second {t2:.3f} ms"


def o4():
    """Same iterative algorithm, but each hop over TCP: works when UDP 53 is blocked."""
    lines = []
    net = lambda server, name, qtype=1: mod.query_tcp(server, name, qtype, recursion_desired=False)
    answers = mod.resolve_iterative("example.com", mod.TYPE_A, query_fn=net, trace=lines.append)
    ips = [r.rdata for r in answers if r.rtype == 1]
    assert ips, "no A record found"
    assert len(lines) >= 5, f"a real walk root -> com -> example.com should print several trace lines, got {len(lines)}"
    return f"{len(lines)} trace lines -> {', '.join(ips)}"


if not OFFLINE_ONLY:
    print("\nOnline checks (real DNS servers; skipped if the network is unreachable)")
    udp_ok = raw_udp_probe()
    tcp_ok = raw_tcp_probe()
    if udp_ok:
        run_online("Online 1: ask 1.1.1.1 for example.com (a mini dig)", o1)
        run_online("Online 2: iterative lookup from the root servers", o2)
        run_online("Online 3: the second lookup is served from the cache", o3)
    else:
        print("  – skipped Online 1-3: no DNS reply over UDP port 53 (your network may block it; that is fine)")
    if tcp_ok:
        run_online("Online 4: iterative lookup with each hop over TCP", o4)
    else:
        print("  – skipped Online 4: cannot reach a root server over TCP port 53")
    if online_results:
        print(f"\n{sum(online_results)}/{len(online_results)} online checks passing")

ok = all(results) and all(online_results)
print("\n" + ("🎉 Lab complete!" if ok else "Keep going: fix the ✘ and … lines above."))
sys.exit(0 if ok else 1)
