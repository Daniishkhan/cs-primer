"""Lab 5 solution: your own event loop, from timers to coroutines.

Standard library only (selectors, heapq, socket, resource). No asyncio.

Usage (each server runs until Ctrl-C and prints its port):
    python3 solution.py callback-echo     # milestone 2
    python3 solution.py buffered-echo     # milestone 3
    python3 solution.py coroutine-echo    # milestone 4
Then talk to it with:  nc 127.0.0.1 PORT
"""
import collections
import errno
import heapq
import itertools
import selectors
import socket
import sys
import time
import traceback

try:
    import resource                    # POSIX only
except ImportError:                    # pragma: no cover
    resource = None

HOST = "127.0.0.1"                     # loopback: only this computer can connect
READ, WRITE = selectors.EVENT_READ, selectors.EVENT_WRITE


# ---------------------------------------------------------------------------
# Milestones 1 and 2: the event loop itself.
# ---------------------------------------------------------------------------

class EventLoop:
    """One thread, three kinds of work: ready callbacks, timers, I/O readiness."""

    def __init__(self):
        self._selector = selectors.DefaultSelector()   # epoll on Linux, kqueue on macOS
        self._ready = collections.deque()              # callbacks to run right now (FIFO)
        self._timers = []                              # heap of (deadline, seq, fn, args)
        self._seq = itertools.count()                  # tie-breaker: same deadline -> FIFO
        self._stopping = False
        self.errors = []                               # exceptions raised by callbacks

    # -- time and scheduling (milestone 1) ---------------------------------

    def time(self):
        # Monotonic: never jumps backwards when NTP or an admin changes the wall clock.
        return time.monotonic()

    def call_soon(self, fn, *args):
        """Run fn(*args) on the next pass of the loop."""
        self._ready.append((fn, args))

    def call_at(self, when, fn, *args):
        """Run fn(*args) at absolute loop time `when` (a value of self.time())."""
        heapq.heappush(self._timers, (when, next(self._seq), fn, args))

    def call_later(self, delay, fn, *args):
        """Run fn(*args) after `delay` seconds."""
        self.call_at(self.time() + max(0.0, delay), fn, *args)

    def stop(self):
        self._stopping = True

    def report_error(self, exc):
        """A callback raised: remember it, print it, keep the loop alive."""
        self.errors.append(exc)
        traceback.print_exception(type(exc), exc, exc.__traceback__)

    def run(self):
        """Run until there is no work left: no ready callbacks, timers or watched sockets."""
        self._stopping = False
        while not self._stopping and (self._ready or self._timers or self._selector.get_map()):
            self._run_once()

    def _run_once(self):
        # 1. How long may we sleep in the selector?
        if self._ready or self._stopping:
            timeout = 0                                    # work is waiting: just peek
        elif self._timers:
            timeout = max(0.0, self._timers[0][0] - self.time())
        else:
            timeout = None                                 # nothing timed: sleep until I/O
        # 2. Ask the OS which sockets are ready; queue their callbacks.
        for key, mask in self._selector.select(timeout):
            reader, writer = key.data
            if mask & READ and reader:
                self._ready.append(reader)
            if mask & WRITE and writer:
                self._ready.append(writer)
        # 3. Move due timers to the ready queue (heap order = deadline, then FIFO).
        now = self.time()
        while self._timers and self._timers[0][0] <= now:
            _, _, fn, args = heapq.heappop(self._timers)
            self._ready.append((fn, args))
        # 4. Run exactly the callbacks that were ready when this pass began.
        for _ in range(len(self._ready)):
            fn, args = self._ready.popleft()
            try:
                fn(*args)
            except Exception as exc:                       # one bad callback must not kill the loop
                self.report_error(exc)

    # -- I/O readiness (milestone 2) -----------------------------------------

    def _lookup(self, sock):
        try:
            return self._selector.get_key(sock)
        except (KeyError, ValueError):
            return None

    def _update(self, sock, reader, writer):
        """Make the selector watch `sock` for exactly the events we have callbacks for."""
        events = (READ if reader else 0) | (WRITE if writer else 0)
        key = self._lookup(sock)
        if events == 0:
            if key:
                self._selector.unregister(sock)
        elif key:
            self._selector.modify(sock, events, (reader, writer))
        else:
            self._selector.register(sock, events, (reader, writer))

    def add_reader(self, sock, fn, *args):
        key = self._lookup(sock)
        self._update(sock, (fn, args), key.data[1] if key else None)

    def remove_reader(self, sock):
        key = self._lookup(sock)
        if key:
            self._update(sock, None, key.data[1])

    def add_writer(self, sock, fn, *args):
        key = self._lookup(sock)
        self._update(sock, key.data[0] if key else None, (fn, args))

    def remove_writer(self, sock):
        key = self._lookup(sock)
        if key:
            self._update(sock, key.data[0], None)

    def has_reader(self, sock):
        key = self._lookup(sock)
        return bool(key and key.data[0])

    def has_writer(self, sock):
        key = self._lookup(sock)
        return bool(key and key.data[1])

    def create_task(self, gen):
        return Task(self, gen)

    def close(self):
        self._selector.close()


def listen_socket(port):
    """A non-blocking listening socket on (HOST, port). Port 0 = any free port."""
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((HOST, port))
    srv.listen(1024)                       # a deep accept queue for connection bursts
    srv.setblocking(False)
    return srv


class EchoServer:
    """Milestone 2: callback-style echo server. Naive on purpose (see milestone 3)."""

    def __init__(self, loop, port=0):
        self.loop = loop
        self.listener = listen_socket(port)
        self.port = self.listener.getsockname()[1]
        self.conns = set()
        loop.add_reader(self.listener, self._on_accept)

    def _on_accept(self):
        # Readable listener = at least one connection waiting. Take them all.
        while True:
            try:
                conn, _ = self.listener.accept()
            except (BlockingIOError, InterruptedError):
                return
            except OSError:                # e.g. out of file descriptors
                return
            conn.setblocking(False)
            self.conns.add(conn)
            self.loop.add_reader(conn, self._on_readable, conn)

    def _on_readable(self, conn):
        if conn not in self.conns:         # closed earlier in this same pass
            return
        try:
            data = conn.recv(65536)
        except (BlockingIOError, InterruptedError):
            return
        except OSError:
            data = b""
        if not data:                       # b"" = the peer closed
            self._drop(conn)
            return
        try:
            conn.send(data)                # may send FEWER bytes than len(data)!
        except OSError:
            self._drop(conn)

    def _drop(self, conn):
        self.loop.remove_reader(conn)
        self.conns.discard(conn)
        conn.close()

    def close(self):
        for conn in list(self.conns):
            self._drop(conn)
        self.loop.remove_reader(self.listener)
        self.listener.close()


# ---------------------------------------------------------------------------
# Milestone 3: partial writes, output buffers, slow consumers.
# ---------------------------------------------------------------------------

class Connection:
    def __init__(self, sock):
        self.sock = sock
        self.out = bytearray()             # bytes we still owe this client
        self.writing = False               # are we registered for write readiness?


class BufferedEchoServer:
    def __init__(self, loop, port=0, max_buffer=256 * 1024):
        self.loop = loop
        self.max_buffer = max_buffer
        self.listener = listen_socket(port)
        self.port = self.listener.getsockname()[1]
        self.conns = {}                    # socket -> Connection
        loop.add_reader(self.listener, self._on_accept)

    def _on_accept(self):
        while True:
            try:
                sock, _ = self.listener.accept()
            except (BlockingIOError, InterruptedError):
                return
            except OSError:
                return
            sock.setblocking(False)
            self.conns[sock] = Connection(sock)
            self.loop.add_reader(sock, self._on_readable, self.conns[sock])

    def _on_readable(self, conn):
        if conn.sock not in self.conns:
            return
        try:
            data = conn.sock.recv(65536)
        except (BlockingIOError, InterruptedError):
            return
        except OSError:
            data = b""
        if not data:
            self._drop(conn)
            return
        conn.out += data
        if len(conn.out) > self.max_buffer:        # the client is not keeping up: cut it off
            self._drop(conn)
            return
        self._flush(conn)

    def _flush(self, conn):
        """Send as much as the kernel will take; ask to be told when it can take more."""
        while conn.out:
            try:
                sent = conn.sock.send(conn.out)
            except (BlockingIOError, InterruptedError):
                break                              # kernel buffer full
            except OSError:
                self._drop(conn)
                return
            del conn.out[:sent]
        if conn.out and not conn.writing:
            self.loop.add_writer(conn.sock, self._on_writable, conn)
            conn.writing = True
        elif not conn.out and conn.writing:        # nothing left: stop waking up for nothing
            self.loop.remove_writer(conn.sock)
            conn.writing = False

    def _on_writable(self, conn):
        if conn.sock in self.conns:
            self._flush(conn)

    def _drop(self, conn):
        if self.conns.pop(conn.sock, None) is None:
            return
        self.loop.remove_reader(conn.sock)
        self.loop.remove_writer(conn.sock)
        conn.sock.close()

    def close(self):
        for conn in list(self.conns.values()):
            self._drop(conn)
        self.loop.remove_reader(self.listener)
        self.listener.close()


# ---------------------------------------------------------------------------
# Milestone 4: coroutines built from generators.
# ---------------------------------------------------------------------------

class Sleep:
    def __init__(self, seconds):
        self.seconds = seconds


class ReadWait:
    def __init__(self, sock):
        self.sock = sock


class WriteWait:
    def __init__(self, sock):
        self.sock = sock


class Task:
    """Drives a generator: each `yield` is a request; resume when it is satisfied."""

    def __init__(self, loop, gen):
        self.loop = loop
        self.gen = gen
        self.done = False
        self.result = None
        self.error = None
        loop.call_soon(self._step)         # first step: run to the first yield

    def _step(self):
        if self.done:
            return
        try:
            request = self.gen.send(None)  # resume the generator
        except StopIteration as stop:      # `return value` inside the generator
            self.done, self.result = True, stop.value
            return
        except Exception as exc:
            self.done, self.error = True, exc
            self.loop.report_error(exc)
            return
        self._wait_for(request)

    def _wait_for(self, request):
        loop = self.loop
        if isinstance(request, Sleep):
            loop.call_later(request.seconds, self._step)
        elif isinstance(request, ReadWait):
            loop.add_reader(request.sock, self._wake, loop.remove_reader, request.sock)
        elif isinstance(request, WriteWait):
            loop.add_writer(request.sock, self._wake, loop.remove_writer, request.sock)
        else:
            self.done = True
            self.error = TypeError(f"a task may only yield Sleep/ReadWait/WriteWait, not {request!r}")
            loop.report_error(self.error)

    def _wake(self, unregister, sock):
        unregister(sock)                   # one-shot: we only wanted to be told once
        self._step()


def accept(listener):
    """Coroutine: wait for a connection on a non-blocking listener and return it."""
    while True:
        yield ReadWait(listener)
        try:
            conn, _ = listener.accept()
        except (BlockingIOError, InterruptedError):
            continue
        except OSError as e:
            if e.errno in (errno.EMFILE, errno.ENFILE, errno.ENOBUFS, errno.ENOMEM):
                yield Sleep(0.1)           # out of descriptors: back off instead of spinning
                continue
            raise
        conn.setblocking(False)
        return conn


def recv(sock, n):
    """Coroutine: wait until readable, then return up to n bytes (b"" = closed)."""
    while True:
        yield ReadWait(sock)
        try:
            return sock.recv(n)
        except (BlockingIOError, InterruptedError):
            continue


def send_all(sock, data):
    """Coroutine: send every byte, waiting whenever the kernel buffer is full."""
    view = memoryview(data)
    while view:
        yield WriteWait(sock)
        try:
            sent = sock.send(view)
        except (BlockingIOError, InterruptedError):
            continue
        view = view[sent:]


class CoroutineEchoServer:
    def __init__(self, loop, port=0):
        self.loop = loop
        self.listener = listen_socket(port)
        self.port = self.listener.getsockname()[1]
        self.conns = set()
        loop.create_task(self._accept_loop())

    def _accept_loop(self):
        while True:
            conn = yield from accept(self.listener)
            self.conns.add(conn)
            self.loop.create_task(self._handle(conn))

    def _handle(self, conn):
        # Straight-line code: no state machine, no callbacks. This is async/await underneath.
        try:
            while True:
                data = yield from recv(conn, 65536)
                if not data:
                    break
                yield from send_all(conn, data)
        except OSError:
            pass
        finally:
            self.conns.discard(conn)
            self.loop.remove_reader(conn)
            self.loop.remove_writer(conn)
            conn.close()

    def close(self):
        for conn in list(self.conns):
            self.loop.remove_reader(conn)
            self.loop.remove_writer(conn)
            conn.close()
        self.conns.clear()
        self.loop.remove_reader(self.listener)
        self.listener.close()


# ---------------------------------------------------------------------------
# Milestone 5: scale, file descriptors and loop lag.
# ---------------------------------------------------------------------------

def raise_fd_limit(wanted):
    """Try to raise the soft RLIMIT_NOFILE to `wanted`; return the soft limit we ended up with."""
    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    if soft == resource.RLIM_INFINITY or soft >= wanted:
        return sys.maxsize if soft == resource.RLIM_INFINITY else soft
    target = wanted if hard == resource.RLIM_INFINITY else min(wanted, hard)
    while target > soft:
        try:
            resource.setrlimit(resource.RLIMIT_NOFILE, (target, hard))
            break
        except (ValueError, OSError):      # e.g. macOS refuses values above its own cap
            target = (target + soft) // 2
    return resource.getrlimit(resource.RLIMIT_NOFILE)[0]


class LagMonitor:
    """Measures how late a 10 ms ticker fires: the loop's heartbeat."""

    def __init__(self, loop, interval=0.01):
        self.loop = loop
        self.interval = interval
        self.lags = []
        self._running = False
        self._expected = 0.0

    def start(self):
        self._running = True
        self._expected = self.loop.time() + self.interval
        self.loop.call_at(self._expected, self._tick)

    def stop(self):
        self._running = False

    def _tick(self):
        if not self._running:
            return
        now = self.loop.time()
        self.lags.append(max(0.0, now - self._expected))   # how late did we fire?
        self._expected = now + self.interval
        self.loop.call_at(self._expected, self._tick)

    @property
    def max_lag(self):
        return max(self.lags) if self.lags else 0.0


# ---------------------------------------------------------------------------
# Glue: run a server on a fresh loop. check.py uses this too.
# ---------------------------------------------------------------------------

def watch_stop(loop, stop, on_stop, interval=0.05):
    """Poll a threading.Event on the loop; when set, call on_stop() so the loop can wind down."""
    def poll():
        if stop.is_set():
            on_stop()
        else:
            loop.call_later(interval, poll)
    loop.call_later(interval, poll)


def serve(make_server, port=0, ready=None, stop=None):
    loop = EventLoop()
    try:
        server = make_server(loop, port)
        if ready:
            ready(server.port)
        if stop is not None:
            watch_stop(loop, stop, server.close)
        loop.run()
    finally:
        loop.close()


def main():
    kinds = {"callback-echo": EchoServer, "buffered-echo": BufferedEchoServer,
             "coroutine-echo": CoroutineEchoServer}
    if len(sys.argv) != 2 or sys.argv[1] not in kinds:
        print(__doc__)
        return
    if resource:
        raise_fd_limit(4096)
    try:
        serve(kinds[sys.argv[1]], port=9005, ready=lambda p: print(f"listening on {HOST}:{p}"))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
