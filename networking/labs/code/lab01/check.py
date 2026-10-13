"""Self-check for Lab 1.

    python3 check.py              # checks your starter.py
    python3 check.py solution     # checks the reference solution

Each milestone runs its server on a random free port in a background thread,
talks to it like a real client would, and prints ✔ / ✘ / … (not started yet).
"""
import importlib
import socket
import sys
import threading
import time

HOST = "127.0.0.1"
target = sys.argv[1] if len(sys.argv) > 1 else "starter"
mod = importlib.import_module(target)
results = []
server_errors = []      # exceptions raised inside server threads


class NotStarted(Exception):
    pass


def check(name, fn):
    server_errors.clear()
    try:
        fn()
        print(f"  ✔ {name}")
        results.append(True)
    except (NotImplementedError, NotStarted) as e:
        print(f"  … {name}: not implemented yet ({e})")
        results.append(False)
    except AssertionError as e:
        print(f"  ✘ {name}: {e}")
        results.append(False)
    except Exception as e:  # anything else is a bug worth seeing
        inner = server_errors[0] if server_errors else None
        if isinstance(inner, NotImplementedError):
            print(f"  … {name}: not implemented yet ({inner})")
        elif inner is not None:
            print(f"  ✘ {name}: the server crashed with {type(inner).__name__}: {inner}")
        else:
            print(f"  ✘ {name}: {type(e).__name__}: {e}")
        results.append(False)


def start(server_fn, **kwargs):
    """Run server_fn(port=0, ready=...) in a thread; return the port it bound."""
    got = {}
    ready = threading.Event()

    def on_ready(port):
        got["port"] = port
        ready.set()

    def run():
        try:
            server_fn(port=0, ready=on_ready, **kwargs)
        except BaseException as e:  # surface errors from the thread
            got["error"] = e
            server_errors.append(e)
            ready.set()

    threading.Thread(target=run, daemon=True).start()
    if not ready.wait(3):
        raise AssertionError("server did not call ready(port) within 3 s")
    if "error" in got:
        raise got["error"]
    return got["port"]


def read_until(sock, needle, timeout=2.0):
    """Read from sock until the received text contains needle."""
    sock.settimeout(timeout)
    text = ""
    deadline = time.time() + timeout
    while needle not in text:
        if time.time() > deadline:
            raise AssertionError(f"expected {needle!r}, got {text!r}")
        try:
            chunk = sock.recv(4096)
        except socket.timeout:
            raise AssertionError(f"timed out waiting for {needle!r}; got {text!r}")
        if not chunk:
            raise AssertionError(f"connection closed while waiting for {needle!r}; got {text!r}")
        text += chunk.decode("utf-8", "replace")
    return text


# --- Milestone 1 ----------------------------------------------------------------

def m1():
    port = start(mod.udp_echo_server, max_messages=1)
    reply = mod.udp_send("hello, udp", port=port, timeout=2)
    assert reply == "HELLO, UDP", f"expected 'HELLO, UDP', got {reply!r}"
    # Nothing listens on this port any more, so the client must give up, not hang.
    t = time.time()
    reply = mod.udp_send("anyone there?", port=port, timeout=0.5)
    assert reply is None, f"expected None when nobody answers, got {reply!r}"
    assert time.time() - t < 2, "udp_send should give up after its timeout"


# --- Milestone 2 ----------------------------------------------------------------

def m2():
    port = start(mod.tcp_echo_server, max_clients=1)
    with socket.create_connection((HOST, port), timeout=2) as s:
        s.sendall(b"abc")
        got = b""
        while len(got) < 3:
            chunk = s.recv(100)
            assert chunk, "server closed the connection early"
            got += chunk
        assert got == b"abc", f"expected b'abc', got {got!r}"
        payload = bytes(range(256)) * 200          # 51,200 bytes: needs many recv() calls
        s.sendall(payload)
        got = b""
        while len(got) < len(payload):
            chunk = s.recv(65536)
            assert chunk, f"connection closed after {len(got)} of {len(payload)} bytes"
            got += chunk
        assert got == payload, "large message did not come back identical"


# --- Milestone 3 ----------------------------------------------------------------

def m3():
    lb = mod.LineBuffer()
    cases = [
        (b"hel", []),
        (b"lo\nwor", ["hello"]),
        (b"ld\r\n", ["world"]),
        (b"a\nb\nc", ["a", "b"]),
        (b"\n", ["c"]),
        ("héllo\n".encode("utf-8")[:2], []),
        ("héllo\n".encode("utf-8")[2:], ["héllo"]),
    ]
    for data, want in cases:
        got = lb.feed(data)
        assert got == want, f"feed({data!r}) returned {got!r}, expected {want!r}"


# --- Milestone 4 ----------------------------------------------------------------

def m4():
    stop = threading.Event()
    port = start(mod.run_chat_server, stop=stop)
    try:
        a = socket.create_connection((HOST, port), timeout=2)
        read_until(a, "Welcome")
        b = socket.create_connection((HOST, port), timeout=2)
        read_until(b, "Welcome")
        read_until(a, "joined")                             # a hears that b joined
        c = socket.create_connection((HOST, port), timeout=2)
        read_until(c, "Welcome")

        a.sendall(b"/nick alice\n")
        read_until(b, "is now alice")
        read_until(c, "is now alice")

        # Send in two pieces: the server must wait for the newline (framing).
        a.sendall(b"hi every")
        time.sleep(0.1)
        a.sendall(b"one\n")
        read_until(b, "[alice] hi everyone")
        read_until(c, "[alice] hi everyone")

        a.settimeout(0.3)                                   # alice must not get her own message
        leftover = b""
        try:
            leftover = a.recv(4096)
        except socket.timeout:
            pass
        assert b"[alice] hi" not in leftover, "the sender received their own message"

        c_name = f"guest-{c.getsockname()[1]}"
        c.close()
        read_until(a, f"{c_name} left")

        b.sendall(b"/quit\n")
        b.settimeout(2)
        end = time.time() + 2
        while time.time() < end:                            # server should close b's connection
            try:
                if b.recv(4096) == b"":
                    break
            except socket.timeout:
                raise AssertionError("/quit did not close the connection")
        a.close()
        b.close()
    finally:
        stop.set()


print(f"Lab 1 checks against {target}.py\n")
check("Milestone 1: UDP echo server + client with timeout", m1)
check("Milestone 2: TCP echo server (byte stream)", m2)
check("Milestone 3: LineBuffer framing", m3)
check("Milestone 4: multi-client chat server", m4)
passed = sum(results)
print(f"\n{passed}/{len(results)} milestones passing" + ("  🎉 Lab complete!" if passed == len(results) else ""))
sys.exit(0 if passed == len(results) else 1)
