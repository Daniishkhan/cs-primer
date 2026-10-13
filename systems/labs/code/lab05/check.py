"""Self-check for Lab 5.

    python3 check.py              # checks your starter.py
    python3 check.py solution     # checks the reference solution

Servers run on 127.0.0.1 with port 0 in a background thread; clients are plain
blocking sockets. Every milestone has a time limit, so a loop that never
returns is reported as a failure instead of hanging. Prints ✔ / ✘ / … (not
implemented yet) per milestone, plus a few notes (file-descriptor limit, loop lag).
"""
import contextlib
import importlib
import io
import os
import random
import signal
import socket
import sys
import threading
import time

if os.name != "posix":
    print("Lab 5 uses POSIX features (selectors on epoll/kqueue, resource limits, SIGALRM).")
    print("Use macOS, Linux, or Windows with WSL (then run this inside the WSL terminal).")
    sys.exit(2)

HOST = "127.0.0.1"
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
target = sys.argv[1] if len(sys.argv) > 1 else "starter"
mod = importlib.import_module(target)

results = []
notes = []
servers = []            # (thread, box) of every server started by the current milestone


def note(text):
    notes.append(text)


def _alarm(signum, frame):
    raise AssertionError("took too long (does run() ever return? does the selector get a timeout?)")


signal.signal(signal.SIGALRM, _alarm)


def server_error():
    """The first exception raised inside a server thread or swallowed by a loop, if any."""
    for _, box in servers:
        if box.get("error"):
            return box["error"]
        loop = box.get("loop")
        if loop is not None and getattr(loop, "errors", None):
            return loop.errors[0]
    return None


def check(name, fn, limit=30):
    servers.clear()
    notes.clear()
    signal.setitimer(signal.ITIMER_REAL, limit)
    try:
        fn()
        ok = True
        print(f"  ✔ {name}")
    except NotImplementedError as e:
        ok = False
        print(f"  … {name}: not implemented yet ({e})")
    except Exception as e:
        ok = False
        inner = server_error()
        if isinstance(inner, NotImplementedError):
            print(f"  … {name}: not implemented yet ({inner})")
        elif inner is not None and not isinstance(e, AssertionError):
            print(f"  ✘ {name}: the server crashed with {type(inner).__name__}: {inner}")
        elif inner is not None:
            print(f"  ✘ {name}: {e}  (the server raised {type(inner).__name__}: {inner})")
        elif isinstance(e, AssertionError):
            print(f"  ✘ {name}: {e}")
        else:
            print(f"  ✘ {name}: {type(e).__name__}: {e}")
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        for _, box in servers:
            box["stop"].set()
        for thread, _ in servers:
            thread.join(2)
    results.append(ok)
    for line in notes:
        print(f"      {line}")


def start(make_server, **kwargs):
    """Run a server on a fresh loop in a thread; return (port, box).

    box["server"] and box["loop"] let a check peek at the server once it is running.
    """
    box = {"stop": threading.Event(), "ready": threading.Event()}

    def make(loop, port):
        box["loop"] = loop
        box["server"] = make_server(loop, port, **kwargs)
        return box["server"]

    def run():
        try:
            mod.serve(make, port=0, ready=lambda p: (box.__setitem__("port", p), box["ready"].set()),
                      stop=box["stop"])
        except BaseException as e:       # surface errors from the thread
            box["error"] = e
        finally:
            box["ready"].set()

    thread = threading.Thread(target=run, daemon=True)
    servers.append((thread, box))
    thread.start()
    if not box["ready"].wait(3):
        raise AssertionError("server did not call ready(port) within 3 s")
    if box.get("error"):
        raise box["error"]
    return box["port"], box


def stop_server(box):
    box["stop"].set()
    for thread, b in servers:
        if b is box:
            thread.join(3)
            assert not thread.is_alive(), \
                "the loop did not finish after the server closed everything (run() should return when no work is left)"


def connect(port):
    return socket.create_connection((HOST, port), timeout=5)


def recv_exact(sock, n, what="echo"):
    got = b""
    while len(got) < n:
        try:
            chunk = sock.recv(min(65536, n - len(got)))
        except socket.timeout:
            raise AssertionError(f"timed out waiting for the {what}: got {len(got)} of {n} bytes")
        if not chunk:
            raise AssertionError(f"connection closed while waiting for the {what}: got {len(got)} of {n} bytes")
        got += chunk
    return got


def wait_until(cond, seconds, message):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if cond():
            return
        time.sleep(0.02)
    raise AssertionError(message)


# --- Milestone 1 -------------------------------------------------------------

def m1():
    loop = mod.EventLoop()
    order = []
    t0 = time.monotonic()
    loop.call_later(0.15, order.append, "late")
    loop.call_later(0.05, order.append, "early")
    loop.call_soon(order.append, "soon-1")
    loop.call_soon(order.append, "soon-2")
    when = loop.time() + 0.1
    for tag in ("same-1", "same-2", "same-3"):
        loop.call_at(when, order.append, tag)
    loop.run()
    elapsed = time.monotonic() - t0
    want = ["soon-1", "soon-2", "early", "same-1", "same-2", "same-3", "late"]
    assert order == want, f"callbacks ran in the wrong order: {order} (expected {want})"
    assert 0.14 <= elapsed < 1.0, f"run() should end when the last timer fires (~0.15 s), took {elapsed:.2f} s"

    # Callbacks can schedule more work; run() keeps going until there is none left.
    ticks = []

    def tick(n):
        ticks.append(n)
        if n < 3:
            loop.call_later(0.02, tick, n + 1)
            loop.call_soon(ticks.append, f"soon-{n}")

    loop = mod.EventLoop()
    loop.call_soon(tick, 1)
    loop.run()
    assert ticks == [1, "soon-1", 2, "soon-2", 3], f"a chain of callbacks produced {ticks}"

    # An exception in one callback must not stop the others.
    loop = mod.EventLoop()
    ran = []

    def boom():
        raise ValueError("boom")

    loop.call_soon(boom)
    loop.call_soon(ran.append, "after boom")
    with contextlib.redirect_stderr(io.StringIO()):
        loop.run()
    assert ran == ["after boom"], "a callback that raised stopped the callbacks after it"
    assert len(loop.errors) == 1 and isinstance(loop.errors[0], ValueError), \
        "the exception should be recorded in loop.errors (call self.report_error)"

    # Waiting must be done by the selector, not by spinning.
    loop = mod.EventLoop()
    loop.call_later(0.3, lambda: None)
    cpu = time.process_time()
    loop.run()
    used = time.process_time() - cpu
    assert used < 0.12, f"the loop burned {used:.2f} s of CPU waiting 0.3 s: sleep in select(timeout), do not poll"

    # Timers use the monotonic clock: a wall clock that jumps back 3 s must not delay anything.
    real_time = time.time
    calls = [0]

    def jumpy():
        calls[0] += 1
        return real_time() - (0 if calls[0] == 1 else 3.0)

    time.time = jumpy
    try:
        loop = mod.EventLoop()
        hit = []
        loop.call_later(0.1, hit.append, 1)
        t0 = time.monotonic()
        loop.run()
        elapsed = time.monotonic() - t0
    finally:
        time.time = real_time
    assert hit == [1] and elapsed < 1.5, \
        f"the wall clock jumped back and your timer waited {elapsed:.1f} s: use time.monotonic()"


# --- Milestone 2 -------------------------------------------------------------

def m2():
    # Loop level: readers and writers on one socket, independently.
    loop = mod.EventLoop()
    a, b = socket.socketpair()
    a.setblocking(False)
    b.setblocking(False)
    seen = []

    def on_read(tag):
        seen.append((tag, a.recv(100)))
        loop.remove_reader(a)

    def on_write():
        seen.append(("writer", None))
        loop.remove_writer(a)
        b.send(b"ping")

    loop.add_reader(a, on_read, "reader")
    loop.add_writer(a, on_write)
    assert loop.has_reader(a) and loop.has_writer(a), "has_reader/has_writer should report what is registered"
    loop.run()
    assert seen == [("writer", None), ("reader", b"ping")], f"readiness callbacks fired as {seen}"
    assert not loop.has_reader(a) and not loop.has_writer(a)
    assert not loop._selector.get_map(), "when both callbacks are removed the socket must leave the selector"

    # Removing only the writer must leave the reader in place.
    loop = mod.EventLoop()
    loop.add_reader(a, lambda: None)
    loop.add_writer(a, lambda: None)
    loop.remove_writer(a)
    assert loop.has_reader(a) and not loop.has_writer(a), "remove_writer must keep the reader registered"
    loop.remove_reader(a)
    loop.remove_reader(a)                      # removing twice is harmless
    loop.remove_writer(a)

    # An idle socket must not stop a timer from firing: the select() timeout is the next deadline.
    loop = mod.EventLoop()
    woke = []
    loop.add_reader(a, woke.append, "io")
    loop.call_later(0.2, loop.remove_reader, a)
    timer = threading.Timer(2.0, b.send, (b"!",))         # safety net: wake a loop that never times out
    timer.start()
    try:
        t0 = time.monotonic()
        loop.run()
    finally:
        timer.cancel()
    assert not woke and time.monotonic() - t0 < 1.0, \
        "a timer due in 0.2 s did not fire on time while a socket was idle: pass the next deadline as select()'s timeout"
    a.close()
    b.close()

    # The echo server.
    port, box = start(mod.EchoServer)
    idle = connect(port)                                   # an idle client must not block the others
    clients = [connect(port) for _ in range(20)]
    for i, c in enumerate(clients):
        msg = f"hello from client {i}\n".encode()
        c.sendall(msg[:5])
        time.sleep(0.002)
        c.sendall(msg[5:])
        assert recv_exact(c, len(msg)) == msg
    idle.sendall(b"still here")
    assert recv_exact(idle, 10) == b"still here", "the idle client was ignored"
    wait_until(lambda: len(box["server"].conns) == 21, 3,
               f"the server tracks {len(box['server'].conns)} connections, expected 21")
    for c in clients:
        c.close()
    idle.close()
    wait_until(lambda: len(box["server"].conns) == 0, 3,
               "closed clients should leave server.conns: drop a connection when recv() returns b''")
    stop_server(box)


# --- Milestone 3 -------------------------------------------------------------

def m3():
    data = random.Random(3).getrandbits(8 * 1_500_000).to_bytes(1_500_000, "little")

    # (a) A client that stops reading for a while: the server must buffer, not lose or block.
    port, box = start(mod.BufferedEchoServer, max_buffer=8 * 1024 * 1024)
    server, loop = box["server"], box["loop"]
    c = socket.socket()
    c.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4096)
    c.settimeout(5)
    c.connect((HOST, port))
    sender = threading.Thread(target=c.sendall, args=(data,), daemon=True)
    sender.start()
    time.sleep(0.6)                                        # we are not reading: echoes pile up
    assert any(loop.has_writer(s) for s in list(server.conns)), \
        "while a client is not reading, its connection should be registered for write readiness (add_writer)"
    got = recv_exact(c, len(data), "big echo")
    assert got == data, "the echo of a 1.5 MB message came back corrupted or incomplete (partial send?)"
    sender.join(3)

    # (b) Idle again: nobody is owed any data, so nobody may be registered for writing.
    time.sleep(0.3)
    stuck = [s for s in list(server.conns) if loop.has_writer(s)]
    assert not stuck, "with empty output buffers no connection may stay registered for writing (it would busy-loop)"
    assert all(loop.has_reader(s) for s in list(server.conns)), "reading must stay registered"
    c.close()
    wait_until(lambda: len(server.conns) == 0, 3, "the closed client was never dropped")
    stop_server(box)

    # (c) A slow consumer must be cut off, and must not hurt anyone else.
    port, box = start(mod.BufferedEchoServer, max_buffer=128 * 1024)
    server = box["server"]
    slow = socket.socket()
    slow.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4096)
    slow.settimeout(1)
    slow.connect((HOST, port))
    cut = threading.Event()
    sent_total = [0]

    def flood():
        chunk = b"x" * 65536
        end = time.monotonic() + 20
        while time.monotonic() < end and sent_total[0] < 64 * 1024 * 1024:
            try:
                sent_total[0] += slow.send(chunk)
            except socket.timeout:
                continue
            except OSError:
                cut.set()
                return

    threading.Thread(target=flood, daemon=True).start()
    fast = connect(port)
    t0 = time.monotonic()
    while not cut.is_set() and time.monotonic() - t0 < 12:
        fast.sendall(b"ping\n")                            # the server must stay responsive meanwhile
        assert recv_exact(fast, 5, "echo for the fast client") == b"ping\n"
        time.sleep(0.05)
    assert cut.wait(3), (f"the slow consumer was never disconnected after {sent_total[0] // 1024} KiB: "
                         "close a connection whose output buffer exceeds max_buffer")
    fast.sendall(b"ping\n")
    assert recv_exact(fast, 5, "echo after the cut-off") == b"ping\n"
    wait_until(lambda: len(server.conns) == 1, 3, f"expected only the fast client left, server has {len(server.conns)}")
    note(f"slow consumer cut off after {sent_total[0] // 1024} KiB with max_buffer = 128 KiB; the fast client never noticed")
    fast.close()
    slow.close()
    stop_server(box)


# --- Milestone 4 -------------------------------------------------------------

def m4():
    # Tasks and requests, loop level.
    loop = mod.EventLoop()
    log = []

    def worker(name, delay, value):
        log.append(f"{name} start")
        yield mod.Sleep(delay)
        log.append(f"{name} woke")
        return value

    t_slow = mod.Task(loop, worker("slow", 0.12, 7))
    t_fast = loop.create_task(worker("fast", 0.04, 9))
    t0 = time.monotonic()
    loop.run()
    assert log == ["slow start", "fast start", "fast woke", "slow woke"], f"tasks interleaved as {log}"
    assert t_slow.done and t_slow.result == 7 and t_fast.result == 9, "a finished Task must have done=True and result set"
    assert time.monotonic() - t0 < 0.5, "two sleeping tasks should overlap, not run one after the other"

    a, b = socket.socketpair()
    a.setblocking(False)
    b.setblocking(False)
    loop = mod.EventLoop()
    got = []

    def reader():
        data = yield from mod.recv(a, 100)
        got.append(data)
        yield mod.WriteWait(a)
        got.append("writable")

    def writer():
        yield mod.Sleep(0.05)
        b.send(b"later")

    loop.create_task(reader())
    loop.create_task(writer())
    loop.run()
    assert got == [b"later", "writable"], f"ReadWait/WriteWait produced {got}"
    assert not loop._selector.get_map(), "a task that has been woken must not stay registered with the selector"
    a.close()
    b.close()

    loop = mod.EventLoop()

    def crashing():
        yield mod.Sleep(0.01)
        raise KeyError("oops")

    def survivor():
        yield mod.Sleep(0.05)
        return "ok"

    bad = loop.create_task(crashing())
    good = loop.create_task(survivor())
    with contextlib.redirect_stderr(io.StringIO()):
        loop.run()
    assert isinstance(bad.error, KeyError) and bad.done, "a task that raised should end with .error set"
    assert good.result == "ok", "one crashing task must not stop the others"

    # The coroutine echo server.
    port, box = start(mod.CoroutineEchoServer)
    server = box["server"]
    idle = connect(port)
    clients = [connect(port) for _ in range(20)]
    for i, c in enumerate(clients):
        msg = f"coroutine {i}\n".encode()
        c.sendall(msg[:4])
        time.sleep(0.002)
        c.sendall(msg[4:])
        assert recv_exact(c, len(msg)) == msg
    idle.sendall(b"hi")
    assert recv_exact(idle, 2) == b"hi", "the idle client was ignored"

    big = random.Random(4).getrandbits(8 * 1_000_000).to_bytes(1_000_000, "little")
    c = socket.socket()
    c.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4096)
    c.settimeout(5)
    c.connect((HOST, port))
    sender = threading.Thread(target=c.sendall, args=(big,), daemon=True)
    sender.start()
    time.sleep(0.4)                                        # let the server hit a full kernel buffer
    idle.sendall(b"yo")
    assert recv_exact(idle, 2, "echo while another client stalls") == b"yo", \
        "one client that does not read blocked everybody: wait with WriteWait instead of blocking in send()"
    assert recv_exact(c, len(big), "big echo") == big, "the 1 MB echo came back corrupted (partial send?)"
    sender.join(3)
    c.close()
    for x in clients + [idle]:
        x.close()
    wait_until(lambda: len(server.conns) == 0, 3, "finished handlers should leave server.conns")
    stop_server(box)


# --- Milestone 5 -------------------------------------------------------------

def open_fds():
    try:
        return len(os.listdir("/dev/fd"))
    except OSError:
        return 30


def lag_run(kind):
    """Run a 10 ms ticker for 0.6 s next to one handler; return the worst lag in seconds."""
    loop = mod.EventLoop()
    monitor = mod.LagMonitor(loop, 0.01)
    monitor.start()

    def polite():
        yield mod.Sleep(0.2)               # waits without holding the loop

    if kind == "blocking":
        loop.call_later(0.15, time.sleep, 0.2)          # a "handler" that blocks the whole thread
    elif kind == "coroutine":
        loop.call_later(0.15, loop.create_task, polite())
    loop.call_later(0.6, monitor.stop)
    loop.run()
    assert len(monitor.lags) > 10, f"the ticker only fired {len(monitor.lags)} times in 0.6 s (expected about 50)"
    return monitor.max_lag


def m5():
    wanted_clients = 1000
    need = 2 * wanted_clients + 200            # our clients and the server's sockets live in one process
    soft = mod.raise_fd_limit(need)
    assert isinstance(soft, int), "raise_fd_limit must return the soft limit it ended up with"
    usable = (soft - open_fds() - 50) // 2
    n = min(wanted_clients, usable)
    assert n >= 100, (f"the open-file limit is {soft} even after raise_fd_limit({need}); "
                      "use resource.setrlimit(RLIMIT_NOFILE, (target, hard))")
    if n < wanted_clients:
        note(f"open-file limit is {soft}: scaled down from {wanted_clients} to {n} concurrent clients")
    else:
        note(f"open-file limit is {soft}: serving all {n} clients")

    monitor_box = {}

    def make(loop, port):
        server = mod.CoroutineEchoServer(loop, port)
        monitor = monitor_box["m"] = mod.LagMonitor(loop, 0.01)
        loop.call_soon(monitor.start)
        return server

    port, box = start(make)
    server = box["server"]
    socks = []
    try:
        t0 = time.monotonic()
        for batch in range(0, n, 50):
            fresh = [connect(port) for _ in range(min(50, n - batch))]
            socks.extend(fresh)
            for i, s in enumerate(fresh, batch):                   # send from every client...
                s.sendall(f"client-{i:04d} says hello\n".encode())
            for i, s in enumerate(fresh, batch):                   # ...and verify every echo
                want = f"client-{i:04d} says hello\n".encode()
                assert recv_exact(s, len(want)) == want, f"client {i} got the wrong echo"
        assert len(socks) == n
        wait_until(lambda: len(server.conns) == n, 3, f"server tracks {len(server.conns)} connections, expected {n}")
        for i, s in enumerate(socks):                              # everyone is STILL connected: go again
            s.sendall(f"round two from {i}\n".encode())
        for i, s in enumerate(socks):
            want = f"round two from {i}\n".encode()
            assert recv_exact(s, len(want)) == want, f"client {i} got the wrong echo in round two"
        took = time.monotonic() - t0
        lag = monitor_box["m"].max_lag
        note(f"{n} concurrent connections, 2 echoes each, on one server thread: {took:.2f} s total")
        note(f"worst loop lag while serving them: {lag * 1000:.1f} ms (informational)")
    finally:
        for s in socks:
            s.close()
    wait_until(lambda: len(server.conns) == 0, 5, "all clients left but the server still tracks connections")
    monitor_box["m"].stop()                    # a running ticker is "work": the loop would never finish
    stop_server(box)

    # The cardinal rule: never block the loop.
    calm = min(lag_run("none") for _ in range(3))
    blocked = lag_run("blocking")
    polite = min(lag_run("coroutine") for _ in range(3))
    note(f"worst tick lag: idle {calm * 1000:.0f} ms | handler calls time.sleep(0.2) {blocked * 1000:.0f} ms"
         f" | handler does `yield Sleep(0.2)` {polite * 1000:.0f} ms")
    assert calm < 0.08, f"an idle loop should tick on time, but the worst lag was {calm * 1000:.0f} ms"
    assert blocked > 0.1, (f"a handler that sleeps 0.2 s should make the ticker late by well over 100 ms, "
                           f"measured {blocked * 1000:.0f} ms: lag = (time it actually fired) - (time it should have fired)")
    assert polite < 0.08, f"a coroutine that waits with Sleep must not delay the ticker, measured {polite * 1000:.0f} ms"


print(f"Lab 5 checks against {target}.py\n")
check("Milestone 1: timers (call_soon, call_later, run)", m1, 15)
check("Milestone 2: I/O readiness + callback echo server", m2, 20)
check("Milestone 3: output buffers, write interest, slow consumers", m3, 40)
check("Milestone 4: coroutines from generators", m4, 20)
check("Milestone 5: a thousand connections + loop lag", m5, 40)
passed = sum(results)
print(f"\n{passed}/{len(results)} milestones passing" + ("  🎉 Lab complete!" if passed == len(results) else ""))
sys.exit(0 if passed == len(results) else 1)
