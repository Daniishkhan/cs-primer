"""Lab 5 solution: a replicated key-value store with quorum reads and writes.

Three storage nodes (threads on 127.0.0.1) speak newline-delimited JSON.
A client library talks to them, writes to W replicas and reads from R.

    python3 solution.py shell      # a 3-node cluster you can poke at by hand
    python3 solution.py node 9101  # one stand-alone node

Every server takes port=0 ("pick any free port") and calls ready(port),
just like Lab 1, so check.py can find it.
"""
import json
import random
import socket
import sys
import threading
import time

HOST = "127.0.0.1"

# A version is a pair (counter, tag), compared like a Lamport timestamp with
# a tie-break (chapter 17): the bigger counter wins; on equal counters the
# bigger tag wins. The tag is the id of the operation that wrote it, so no
# two different writes ever have the same version.
NO_VERSION = (0, "")          # "this key has never been written"

NODE_ERRORS = []              # exceptions raised inside node threads (check.py reads this)


# ---------------------------------------------------------------------------
# Framing (the Lab 1 idea): one JSON object per line.
# ---------------------------------------------------------------------------

def encode(obj):
    return (json.dumps(obj) + "\n").encode("utf-8")


def read_line(sock):
    """Read bytes up to the first newline. Returns the line (bytes) or None if
    the peer closed the connection before sending a full line."""
    data = b""
    while not data.endswith(b"\n"):
        chunk = sock.recv(4096)
        if not chunk:
            return None
        data += chunk
    return data


class ReplicaUnavailable(Exception):
    """A replica did not give us an answer."""


class ReplicaTimeout(ReplicaUnavailable):
    """It never answered: dead, paused, or just slow. We cannot tell which."""


class ReplicaDown(ReplicaUnavailable):
    """It refused or dropped the connection: a definite 'nobody is home'."""


class QuorumNotReached(Exception):
    """Fewer than the required number of replicas answered."""

    def __init__(self, needed, got, errors=()):
        self.needed, self.got, self.errors = needed, got, list(errors)
        super().__init__(f"needed {needed} replicas, only {got} answered")


# ---------------------------------------------------------------------------
# Milestone 1: one node. A Store, and a call() that talks to it.
# ---------------------------------------------------------------------------

class Store:
    """key -> (value, version). Keeps only the newest version it has seen."""

    def __init__(self):
        self.data = {}

    def get(self, key):
        """Return (value, version); (None, NO_VERSION) if the key is unknown."""
        return self.data.get(key, (None, NO_VERSION))

    def put(self, key, value, version):
        """Store the value only if `version` is newer than what we hold.
        Return True if stored, False if ignored. Versions arrive from JSON as
        lists, so convert with tuple() before comparing."""
        version = tuple(version)
        if version > self.get(key)[1]:
            self.data[key] = (value, version)
            return True
        return False


def call(port, request, timeout=1.0):
    """Send one request to a node and return its reply as a dict.

    Raises ReplicaTimeout if no complete reply arrives within `timeout`
    seconds, and ReplicaDown if the connection is refused or dropped."""
    try:
        with socket.create_connection((HOST, port), timeout=timeout) as sock:
            sock.settimeout(timeout)
            sock.sendall(encode(request))
            line = read_line(sock)
    except socket.timeout:
        raise ReplicaTimeout(f"no reply from port {port} within {timeout}s")
    except OSError as e:                       # refused, reset, broken pipe ...
        raise ReplicaDown(f"port {port}: {e}")
    if line is None:
        raise ReplicaDown(f"port {port} closed the connection")
    return json.loads(line.decode("utf-8"))


# ---------------------------------------------------------------------------
# The node server (provided). It is plumbing: sockets, threads, and the fault
# switches that make failures reproducible. Read it, but you don't change it.
# ---------------------------------------------------------------------------

class Node:
    """One storage node: a Store behind a TCP server, plus fault injection.

    pause()/resume()     stop answering (the node looks slow or dead)
    kill()/restart()     close the server; restart may keep or wipe the data
    drop_next_replies()  do the work but swallow the reply (the nasty case)
    """

    def __init__(self, name="node"):
        self.name = name
        self.port = 0
        self.store = Store()
        self.applied = {}            # op_id -> (key, value, version): the dedup table
        self.lock = threading.Lock()
        self.paused = False
        self.drops = {}              # op name -> replies still to swallow
        self._srv = None
        self._conns = set()

    # -- lifecycle ----------------------------------------------------------
    def start(self, port=None):
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((HOST, self.port if port is None else port))
        srv.listen(16)
        srv.settimeout(0.1)
        self.port = srv.getsockname()[1]
        self._srv = srv
        threading.Thread(target=self._accept_loop, args=(srv,), daemon=True).start()
        return self.port

    def kill(self):
        """Crash: close the listener and every open connection."""
        srv, self._srv = self._srv, None
        if srv:
            srv.close()
        for c in list(self._conns):
            try:
                c.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            c.close()
        self._conns.clear()

    def restart(self, wipe=False):
        """Come back on the same port. wipe=False: the data survived (it was
        on disk). wipe=True: it lived only in memory and is gone."""
        self.kill()
        if wipe:
            self.store = Store()
            self.applied = {}
        self.paused = False
        self.start()

    @property
    def alive(self):
        return self._srv is not None

    def pause(self):
        self.paused = True

    def resume(self):
        self.paused = False

    def drop_next_replies(self, n=1, op="put"):
        """Handle the next n requests of kind `op` normally, but never reply."""
        self.drops[op] = n

    # -- server loops -------------------------------------------------------
    def _accept_loop(self, srv):
        while self._srv is srv:
            try:
                conn, _ = srv.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            self._conns.add(conn)
            threading.Thread(target=self._serve_conn, args=(conn,), daemon=True).start()

    def _serve_conn(self, conn):
        try:
            conn.settimeout(5)
            data = b""
            while True:
                try:
                    chunk = conn.recv(4096)
                except socket.timeout:
                    break
                if not chunk:
                    break
                data += chunk
                while b"\n" in data:
                    line, data = data.split(b"\n", 1)
                    if self.paused:
                        continue                    # paused: say nothing at all
                    op, reply = self._handle_line(line)
                    left = self.drops.get(op, 0)
                    if left > 0:                    # work done, reply swallowed
                        self.drops[op] = left - 1
                        continue
                    conn.sendall(encode(reply))
        except OSError:
            pass
        finally:
            self._conns.discard(conn)
            conn.close()

    def _handle_line(self, line):
        try:
            req = json.loads(line.decode("utf-8"))
            with self.lock:
                return req.get("op"), self.handle(req)
        except Exception as e:                      # a bug in a handler: record and report
            NODE_ERRORS.append(e)
            return None, {"ok": False, "error": f"{type(e).__name__}: {e}"}

    def handle(self, req):
        """Turn one request into one reply. Runs under the node's lock."""
        op = req.get("op")
        if op == "ping":
            return {"ok": True, "name": self.name}
        if op == "get":
            value, version = self.store.get(req["key"])
            done = self.applied.get(req.get("op_id"))        # "did I already do this op?"
            reply = {"ok": True, "value": value, "version": list(version), "done": None}
            if done:
                reply["done"] = {"key": done[0], "value": done[1], "version": list(done[2])}
            return reply
        if op == "put":
            op_id = req.get("op_id")
            if op_id in self.applied:                         # duplicate: don't redo, same answer
                return {"ok": True, "applied": False, "duplicate": True}
            applied = self.store.put(req["key"], req["value"], req["version"])
            if op_id:                                         # remember it atomically with the effect
                self.applied[op_id] = (req["key"], req["value"], tuple(req["version"]))
            return {"ok": True, "applied": applied}
        return {"ok": False, "error": f"unknown op {op!r}"}


def serve(port=0, ready=None, stop=None):
    """Run one node until `stop` (a threading.Event) is set. check.py uses
    this for milestone 1; the cluster below uses Node directly."""
    node = Node("solo")
    real_port = node.start(port)
    if ready:
        ready(real_port)
    stop = stop or threading.Event()
    try:
        stop.wait()
    finally:
        node.kill()


class Cluster:
    """N nodes on 127.0.0.1 (provided)."""

    def __init__(self, n=3):
        self.nodes = [Node(f"n{i}") for i in range(n)]
        for node in self.nodes:
            node.start()

    @property
    def ports(self):
        return [node.port for node in self.nodes]

    def client(self, **kwargs):
        return KVClient(self.ports, **kwargs)

    def stop(self):
        for node in self.nodes:
            node.kill()


# ---------------------------------------------------------------------------
# Milestones 2-6: the client library.
# ---------------------------------------------------------------------------

def backoff_delay(attempt, base=0.1, cap=5.0, rng=random):
    """Milestone 5. 'Full jitter': a random wait between 0 and
    min(cap, base * 2**attempt). attempt counts from 0."""
    return rng.uniform(0, min(cap, base * (2 ** attempt)))


def retry(fn, attempts=5, base=0.1, cap=5.0, rng=random, sleep=time.sleep,
          retry_on=(QuorumNotReached,)):
    """Milestone 5. Call fn(); if it raises something in retry_on, wait
    backoff_delay(...) and try again, up to `attempts` calls in total.
    Re-raise the last error when the attempts run out. Other exceptions
    propagate immediately (retrying a bug just repeats the bug)."""
    for attempt in range(attempts):
        try:
            return fn()
        except retry_on:
            if attempt == attempts - 1:
                raise
            sleep(backoff_delay(attempt, base, cap, rng))


class KVClient:
    """Talks to N replicas. A write must reach `w` of them, a read asks `r`."""

    def __init__(self, ports, w=2, r=2, client_id="c1", timeout=0.3, seed=0,
                 read_repair=False):
        self.ports, self.w, self.r = list(ports), w, r
        self.client_id, self.timeout = client_id, timeout
        self.read_repair = read_repair
        self.rng = random.Random(seed)
        self.clock = 0               # a Lamport counter: the biggest version counter we have seen or made
        self.repairs = 0             # how many replicas read repair has fixed
        self._ops = 0

    def _new_op_id(self):
        self._ops += 1
        return f"{self.client_id}-{self._ops}"

    def _order(self, prefer):
        """Which replicas to try, in order. prefer=None means a seeded shuffle."""
        return list(prefer) if prefer is not None else self.rng.sample(range(len(self.ports)), len(self.ports))

    # -- Milestones 2 and 4 -------------------------------------------------
    def _quorum_call(self, request, need, prefer=None):
        """Send `request` to replicas, one at a time in preference order, until
        `need` of them have answered. A replica that times out or is down is
        skipped (milestone 4). Returns a list of (replica_index, reply).
        Raises QuorumNotReached if we run out of replicas first."""
        replies, errors = [], []
        for i in self._order(prefer):
            if len(replies) == need:
                break
            try:
                reply = call(self.ports[i], request, self.timeout)
            except ReplicaUnavailable as e:
                errors.append((i, e))
                continue
            if reply.get("ok"):
                replies.append((i, reply))
        if len(replies) < need:
            raise QuorumNotReached(need, len(replies), errors)
        return replies

    def _write(self, key, value, version, op_id, prefer=None):
        request = {"op": "put", "key": key, "value": value,
                   "version": list(version), "op_id": op_id}
        self._quorum_call(request, self.w, prefer)

    def put(self, key, value, prefer=None, op_id=None):
        """Milestone 2: write to W replicas. Returns the version it wrote."""
        op_id = op_id or self._new_op_id()
        self.clock += 1
        version = (self.clock, op_id)
        self._write(key, value, version, op_id, prefer)
        return version

    # -- Milestones 3 and 6 -------------------------------------------------
    def get(self, key, prefer=None):
        """Milestone 3: ask R replicas, return (value, version) of the newest.
        Milestone 6: if self.read_repair, fix the replicas that were behind."""
        replies = self._quorum_call({"op": "get", "key": key}, self.r, prefer)
        i, best = max(replies, key=lambda ir: tuple(ir[1]["version"]))
        version = tuple(best["version"])
        self.clock = max(self.clock, version[0])
        if self.read_repair:
            self._repair(key, best["value"], version, replies)
        return best["value"], version

    def _repair(self, key, value, version, replies):
        """Milestone 6: write the newest (value, version) back to every replica
        among `replies` that returned something older. Returns their indexes."""
        stale = [i for i, rep in replies if tuple(rep["version"]) < version]
        for i in stale:
            try:
                call(self.ports[i], {"op": "put", "key": key, "value": value,
                                     "version": list(version)}, self.timeout)
                self.repairs += 1
            except ReplicaUnavailable:
                pass                       # best effort: it can be repaired next time
        return stale

    # -- Milestone 5 --------------------------------------------------------
    def _update(self, key, fn, op_id, prefer=None):
        """Read-modify-write that is safe to retry. `op_id` is the idempotency key:
        the caller makes it ONCE per logical operation and reuses it on retries."""
        # 1. Ask R replicas for the current value, and whether they already did op_id.
        replies = self._quorum_call({"op": "get", "key": key, "op_id": op_id}, self.r, prefer)
        done = [rep["done"] for _, rep in replies if rep.get("done")]
        if done:
            # An earlier attempt got at least as far as writing it. Don't apply again:
            # just make sure the result is on W replicas, and return it.
            rec = max(done, key=lambda d: tuple(d["version"]))
            self._write(key, rec["value"], tuple(rec["version"]), op_id, prefer)
            return rec["value"]
        # 2. First time we see this op: compute the new value from the newest copy.
        _, best = max(replies, key=lambda ir: tuple(ir[1]["version"]))
        new_value = fn(best["value"])
        self.clock = max(self.clock, best["version"][0]) + 1
        self._write(key, new_value, (self.clock, op_id), op_id, prefer)
        return new_value

    def increment(self, key, by=1, op_id=None, prefer=None):
        return self._update(key, lambda v: (v or 0) + by, op_id or self._new_op_id(), prefer)

    def append(self, key, item, op_id=None, prefer=None):
        return self._update(key, lambda v: (v or []) + [item], op_id or self._new_op_id(), prefer)


# ---------------------------------------------------------------------------
# A little shell so you can poke at a cluster by hand (provided).
# ---------------------------------------------------------------------------

def shell():
    cluster = Cluster(3)
    client = cluster.client(w=2, r=2, timeout=0.5, read_repair=False)
    print("3 nodes on ports", cluster.ports)
    print("commands: put K V | get K | incr K | w N | r N | repair on|off | pause I | resume I |")
    print("          kill I | restart I [wipe] | show | quit      (I is 0, 1 or 2)")
    try:
        while True:
            try:
                parts = input("kv> ").split()
            except EOFError:
                break
            if not parts:
                continue
            cmd, args = parts[0], parts[1:]
            try:
                if cmd == "quit":
                    break
                elif cmd == "put":
                    print("stored at version", client.put(args[0], " ".join(args[1:])))
                elif cmd == "get":
                    print(client.get(args[0]))
                elif cmd == "incr":
                    print(client.increment(args[0]))
                elif cmd == "w":
                    client.w = int(args[0])
                elif cmd == "r":
                    client.r = int(args[0])
                elif cmd == "repair":
                    client.read_repair = args[0] == "on"
                elif cmd == "pause":
                    cluster.nodes[int(args[0])].pause()
                elif cmd == "resume":
                    cluster.nodes[int(args[0])].resume()
                elif cmd == "kill":
                    cluster.nodes[int(args[0])].kill()
                elif cmd == "restart":
                    cluster.nodes[int(args[0])].restart(wipe="wipe" in args[1:])
                elif cmd == "show":
                    for node in cluster.nodes:
                        state = "up" if node.alive else "DOWN"
                        state += ", paused" if node.paused else ""
                        print(f"  {node.name} ({state}): {node.store.data}")
                else:
                    print("unknown command")
            except QuorumNotReached as e:
                print("FAILED:", e)
            except (IndexError, ValueError):
                print("usage error")
    finally:
        cluster.stop()


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "shell":
        shell()
    elif len(sys.argv) >= 2 and sys.argv[1] == "node":
        p = int(sys.argv[2]) if len(sys.argv) > 2 else 9101
        serve(port=p, ready=lambda real: print("node listening on", real))
    else:
        print(__doc__)
