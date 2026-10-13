"""Lab 5 starter: your own event loop, from timers to coroutines.

Standard library only (selectors, heapq, socket, resource). No asyncio.
Fill in every TODO, one milestone at a time, and run `python3 check.py`
after each one. The lab page walks you through it.

Usage (each server runs until Ctrl-C and prints its port):
    python3 starter.py callback-echo      # milestone 2
    python3 starter.py buffered-echo      # milestone 3
    python3 starter.py coroutine-echo     # milestone 4
Then talk to it with:  nc 127.0.0.1 PORT

Every server takes port=0 ("pick any free port") and exposes .port, so
check.py can find it. serve() at the bottom is already written.
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
        self._timers = []                              # a heap: entries are (deadline, seq, fn, args)
        self._seq = itertools.count()                  # next(self._seq): tie-breaker for equal deadlines
        self._stopping = False
        self.errors = []                               # exceptions raised by callbacks

    # -- time and scheduling (milestone 1) ---------------------------------

    def time(self):
        """The loop's clock, in seconds.

        TODO milestone 1: return time.monotonic(). Not time.time(): the wall
        clock can jump (NTP, daylight saving, leap seconds). See case 3.
        """
        raise NotImplementedError("TODO milestone 1: EventLoop.time")

    def call_soon(self, fn, *args):
        """Run fn(*args) on the next pass of the loop.

        TODO milestone 1: append (fn, args) to self._ready.
        """
        raise NotImplementedError("TODO milestone 1: EventLoop.call_soon")

    def call_at(self, when, fn, *args):
        """Run fn(*args) at absolute loop time `when` (a value of self.time()).

        TODO milestone 1: heapq.heappush(self._timers, (when, next(self._seq), fn, args)).
        The unique sequence number breaks ties, so callbacks due at the same
        moment run in the order they were scheduled, and Python never has to
        compare two functions.
        """
        raise NotImplementedError("TODO milestone 1: EventLoop.call_at")

    def call_later(self, delay, fn, *args):
        """Run fn(*args) after `delay` seconds.

        TODO milestone 1: call_at(self.time() + delay, ...).
        """
        raise NotImplementedError("TODO milestone 1: EventLoop.call_later")

    def stop(self):
        self._stopping = True

    def report_error(self, exc):
        """A callback raised: remember it, print it, keep the loop alive. (Already written.)"""
        self.errors.append(exc)
        traceback.print_exception(type(exc), exc, exc.__traceback__)

    def run(self):
        """Run until there is no work left: no ready callbacks, no timers, no watched sockets.

        TODO milestone 1: loop while there is work, calling self._run_once().
        Work = self._ready or self._timers or self._selector.get_map().
        """
        raise NotImplementedError("TODO milestone 1: EventLoop.run")

    def _run_once(self):
        """One pass of the loop.

        TODO milestone 1 (timers) and 2 (I/O):
          1. Choose the selector timeout:
               0                    if callbacks are ready (or we are stopping),
               next deadline - now  (never negative) if there are timers,
               None                 (sleep until I/O) otherwise.
          2. events = self._selector.select(timeout). For each (key, mask):
             key.data is the (reader, writer) pair stored by _update(); each is
             a (fn, args) tuple or None. If mask & READ, queue the reader; if
             mask & WRITE, queue the writer. [milestone 2]
          3. Pop every timer whose deadline <= now off the heap and append it
             to self._ready.
          4. Run the callbacks that were ready at the start of this step
             (len(self._ready) of them, so new ones wait for the next pass).
             Wrap each call in try/except Exception and pass the error to
             self.report_error(exc): one bad callback must not kill the loop.
        """
        raise NotImplementedError("TODO milestone 1: EventLoop._run_once")

    # -- I/O readiness (milestone 2) -----------------------------------------

    def _lookup(self, sock):
        """The selector key for sock, or None. (Already written.)"""
        try:
            return self._selector.get_key(sock)
        except (KeyError, ValueError):
            return None

    def _update(self, sock, reader, writer):
        """Watch `sock` for exactly the events we have callbacks for. (Already written.)

        reader and writer are (fn, args) tuples or None. Both None = unregister.
        """
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
        """Call fn(*args) whenever sock is readable (level-triggered), until removed.

        TODO milestone 2: look up the current registration (self._lookup);
        keep its writer (key.data[1]) and replace the reader with (fn, args)
        via self._update.
        """
        raise NotImplementedError("TODO milestone 2: EventLoop.add_reader")

    def remove_reader(self, sock):
        """Stop watching sock for reading. Harmless if it wasn't being watched.

        TODO milestone 2: keep the writer, set the reader to None.
        """
        raise NotImplementedError("TODO milestone 2: EventLoop.remove_reader")

    def add_writer(self, sock, fn, *args):
        """Call fn(*args) whenever sock is writable, until removed.

        TODO milestone 2: like add_reader, but for the writer slot.
        """
        raise NotImplementedError("TODO milestone 2: EventLoop.add_writer")

    def remove_writer(self, sock):
        """TODO milestone 2: like remove_reader, for the writer slot."""
        raise NotImplementedError("TODO milestone 2: EventLoop.remove_writer")

    def has_reader(self, sock):
        """TODO milestone 2: True if a reader callback is registered for sock."""
        raise NotImplementedError("TODO milestone 2: EventLoop.has_reader")

    def has_writer(self, sock):
        """TODO milestone 2: True if a writer callback is registered for sock."""
        raise NotImplementedError("TODO milestone 2: EventLoop.has_writer")

    def create_task(self, gen):
        return Task(self, gen)

    def close(self):
        self._selector.close()


def listen_socket(port):
    """A non-blocking listening socket on (HOST, port). Port 0 = any free port. (Already written.)"""
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((HOST, port))
    srv.listen(1024)                       # a deep accept queue for connection bursts
    srv.setblocking(False)
    return srv


class EchoServer:
    """Milestone 2: callback-style echo server. Naive on purpose (see milestone 3)."""

    def __init__(self, loop, port=0):
        """TODO milestone 2:
          - self.loop = loop; self.listener = listen_socket(port)
          - self.port = the real port (self.listener.getsockname()[1])
          - self.conns = set() of open connections
          - loop.add_reader(self.listener, self._on_accept)
        """
        raise NotImplementedError("TODO milestone 2: EchoServer.__init__")

    def _on_accept(self):
        """The listener is readable: connections are waiting.

        TODO milestone 2: call self.listener.accept() in a loop until it raises
        BlockingIOError (return then). For each connection: setblocking(False),
        add it to self.conns, and loop.add_reader(conn, self._on_readable, conn).
        Also return on any other OSError (for example, out of file descriptors).
        """
        raise NotImplementedError("TODO milestone 2: EchoServer._on_accept")

    def _on_readable(self, conn):
        """conn is readable.

        TODO milestone 2:
          - if conn is no longer in self.conns, return (it was closed earlier in this pass)
          - data = conn.recv(65536); BlockingIOError -> return; other OSError -> treat as b""
          - b"" means the peer closed: self._drop(conn) and return
          - otherwise conn.send(data) (it may send fewer bytes: milestone 3 fixes that)
        """
        raise NotImplementedError("TODO milestone 2: EchoServer._on_readable")

    def _drop(self, conn):
        """TODO milestone 2: remove_reader, discard from self.conns, THEN close the socket."""
        raise NotImplementedError("TODO milestone 2: EchoServer._drop")

    def close(self):
        """Close everything so the loop runs out of work and run() returns. (Already written.)"""
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
        """TODO milestone 3: like EchoServer, but self.conns is a dict {socket: Connection}
        and we remember max_buffer (the most output we are willing to hold per client).
        """
        raise NotImplementedError("TODO milestone 3: BufferedEchoServer.__init__")

    def _on_accept(self):
        """TODO milestone 3: as in EchoServer, but create a Connection and register
        loop.add_reader(sock, self._on_readable, connection)."""
        raise NotImplementedError("TODO milestone 3: BufferedEchoServer._on_accept")

    def _on_readable(self, conn):
        """TODO milestone 3:
          - recv; on b"" / error, self._drop(conn)
          - conn.out += data
          - if len(conn.out) > self.max_buffer: this client is not keeping up.
            self._drop(conn) and return.
          - otherwise self._flush(conn)
        """
        raise NotImplementedError("TODO milestone 3: BufferedEchoServer._on_readable")

    def _flush(self, conn):
        """Send what the kernel will take, then fix up write interest.

        TODO milestone 3:
          - while conn.out: sent = conn.sock.send(conn.out); del conn.out[:sent].
            BlockingIOError -> break. Other OSError -> self._drop(conn), return.
          - if bytes remain and not conn.writing: loop.add_writer(conn.sock, self._on_writable, conn); writing = True
          - if nothing remains and conn.writing:  loop.remove_writer(conn.sock); writing = False
        """
        raise NotImplementedError("TODO milestone 3: BufferedEchoServer._flush")

    def _on_writable(self, conn):
        """TODO milestone 3: if conn is still ours, try self._flush(conn) again."""
        raise NotImplementedError("TODO milestone 3: BufferedEchoServer._on_writable")

    def _drop(self, conn):
        """TODO milestone 3: forget the connection (self.conns.pop), remove its reader AND
        writer, then close the socket. Safe to call twice."""
        raise NotImplementedError("TODO milestone 3: BufferedEchoServer._drop")

    def close(self):
        """(Already written.)"""
        for conn in list(self.conns.values()):
            self._drop(conn)
        self.loop.remove_reader(self.listener)
        self.listener.close()


# ---------------------------------------------------------------------------
# Milestone 4: coroutines built from generators.
# ---------------------------------------------------------------------------

class Sleep:
    """Yielded by a coroutine: 'wake me in `seconds`'. (Already written.)"""
    def __init__(self, seconds):
        self.seconds = seconds


class ReadWait:
    """Yielded by a coroutine: 'wake me when `sock` is readable'."""
    def __init__(self, sock):
        self.sock = sock


class WriteWait:
    """Yielded by a coroutine: 'wake me when `sock` is writable'."""
    def __init__(self, sock):
        self.sock = sock


class Task:
    """Drives a generator: each `yield` is a request; resume when it is satisfied."""

    def __init__(self, loop, gen):
        """TODO milestone 4: remember loop and gen; set done = False, result = None,
        error = None; then loop.call_soon(self._step) to start the first step."""
        raise NotImplementedError("TODO milestone 4: Task.__init__")

    def _step(self):
        """Resume the generator until its next yield.

        TODO milestone 4:
          - if self.done: return
          - request = self.gen.send(None)
          - StopIteration as stop: done = True, result = stop.value, return
          - any other Exception: done = True, error = exc, loop.report_error(exc), return
          - otherwise self._wait_for(request)
        """
        raise NotImplementedError("TODO milestone 4: Task._step")

    def _wait_for(self, request):
        """Arrange for self._step to be called when `request` is satisfied.

        TODO milestone 4:
          - Sleep      -> loop.call_later(request.seconds, self._step)
          - ReadWait   -> loop.add_reader(request.sock, self._wake, loop.remove_reader, request.sock)
          - WriteWait  -> loop.add_writer(request.sock, self._wake, loop.remove_writer, request.sock)
          - anything else: a bug in the coroutine. Mark the task done with a TypeError
            in .error and pass it to loop.report_error.
        """
        raise NotImplementedError("TODO milestone 4: Task._wait_for")

    def _wake(self, unregister, sock):
        """The socket is ready: stop watching it (one-shot), then resume.

        TODO milestone 4: unregister(sock); self._step()
        """
        raise NotImplementedError("TODO milestone 4: Task._wake")


def accept(listener):
    """Coroutine: wait for a connection on a non-blocking listener and return it. (Already written.)

    Use it as:  conn = yield from accept(listener)
    """
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
    """Coroutine: wait until readable, then return up to n bytes (b"" = closed). (Already written.)"""
    while True:
        yield ReadWait(sock)
        try:
            return sock.recv(n)
        except (BlockingIOError, InterruptedError):
            continue


def send_all(sock, data):
    """Coroutine: send every byte, waiting whenever the kernel buffer is full. (Already written.)"""
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
        """TODO milestone 4: as EchoServer (self.loop, self.listener, self.port, self.conns = set()),
        but instead of add_reader, start the acceptor: loop.create_task(self._accept_loop())."""
        raise NotImplementedError("TODO milestone 4: CoroutineEchoServer.__init__")

    def _accept_loop(self):
        """A coroutine (a generator function).

        TODO milestone 4: forever: conn = yield from accept(self.listener);
        add conn to self.conns; self.loop.create_task(self._handle(conn))
        """
        raise NotImplementedError("TODO milestone 4: CoroutineEchoServer._accept_loop")

    def _handle(self, conn):
        """A coroutine: the whole life of one connection, as straight-line code.

        TODO milestone 4: try: loop { data = yield from recv(conn, 65536); stop on b"";
        yield from send_all(conn, data) } except OSError: pass
        finally: discard conn from self.conns, remove_reader / remove_writer, conn.close()
        """
        raise NotImplementedError("TODO milestone 4: CoroutineEchoServer._handle")

    def close(self):
        """(Already written.)"""
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
    """Try to raise the soft RLIMIT_NOFILE to `wanted`; return the soft limit we ended up with.

    TODO milestone 5:
      - soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
      - if soft is RLIM_INFINITY or already >= wanted: return it (sys.maxsize for infinity)
      - target = min(wanted, hard) (RLIM_INFINITY means no hard limit)
      - try resource.setrlimit(resource.RLIMIT_NOFILE, (target, hard)). macOS can refuse
        values above its own cap (ValueError/OSError): then try a smaller target, halfway
        between soft and target, until it works or target <= soft.
      - return the soft limit you actually have (getrlimit again).
    """
    raise NotImplementedError("TODO milestone 5: raise_fd_limit")


class LagMonitor:
    """Measures how late a 10 ms ticker fires: the loop's heartbeat."""

    def __init__(self, loop, interval=0.01):
        self.loop = loop
        self.interval = interval
        self.lags = []                     # seconds late, one entry per tick
        self._running = False
        self._expected = 0.0

    def start(self):
        """TODO milestone 5: running = True; expected = loop.time() + interval;
        schedule self._tick at that time with loop.call_at."""
        raise NotImplementedError("TODO milestone 5: LagMonitor.start")

    def stop(self):
        self._running = False

    def _tick(self):
        """TODO milestone 5: if not running, return. now = loop.time(); record
        max(0, now - expected) in self.lags; expected = now + interval; schedule the
        next tick at `expected`. (A running ticker counts as work: stop() it, or run() never ends.)"""
        raise NotImplementedError("TODO milestone 5: LagMonitor._tick")

    @property
    def max_lag(self):
        return max(self.lags) if self.lags else 0.0


# ---------------------------------------------------------------------------
# Glue: run a server on a fresh loop. Already written; check.py uses it too.
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
