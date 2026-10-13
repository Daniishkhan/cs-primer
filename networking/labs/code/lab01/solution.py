"""Lab 1 reference solution: sockets and a chat server.

Usage (run each server in its own terminal):
    python3 solution.py udp-server              # milestone 1
    python3 solution.py udp-send "hello"
    python3 solution.py tcp-server              # milestone 2
    python3 solution.py chat-server             # milestone 4
    python3 solution.py chat-client             # or: nc 127.0.0.1 9003

Standard library only. Every server takes port=0 ("pick any free port") and
a ready(port) callback so check.py can start it on a random port.
"""
import argparse
import selectors
import socket
import sys
import threading

HOST = "127.0.0.1"   # loopback: only this computer can connect

# Message formats for the chat server (check.py relies on these exact strings).
WELCOME = "* Welcome! Commands: /nick NAME, /quit\n"


def fmt_chat(name, text):
    return f"[{name}] {text}\n"


def fmt_notice(text):
    return f"* {text}\n"


# ---------------------------------------------------------------------------
# Milestone 1: UDP echo. One datagram in, one datagram out, no connection.
# ---------------------------------------------------------------------------

def udp_echo_server(port=9001, ready=None, max_messages=None):
    """Receive datagrams and send each one straight back in upper case."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind((HOST, port))
        port = sock.getsockname()[1]          # the real port if we asked for 0
        print(f"UDP echo server listening on {HOST}:{port}")
        if ready:
            ready(port)
        handled = 0
        while max_messages is None or handled < max_messages:
            data, addr = sock.recvfrom(2048)  # addr = (sender IP, sender port)
            print(f"  {len(data)} bytes from {addr[0]}:{addr[1]}: {data!r}")
            sock.sendto(data.upper(), addr)   # reply to whoever sent it
            handled += 1


def udp_send(message, port=9001, timeout=2.0):
    """Send one datagram and wait for one reply. Returns the reply, or None.

    UDP gives no delivery guarantee, so the only way to notice a lost
    datagram (or a server that isn't running) is to stop waiting: a timeout.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(timeout)
        sock.sendto(message.encode("utf-8"), (HOST, port))
        try:
            data, _ = sock.recvfrom(2048)
        except (socket.timeout, ConnectionRefusedError):
            # ConnectionRefusedError: some systems turn an ICMP "port
            # unreachable" (chapter 6) into an error on the next receive.
            return None
        return data.decode("utf-8")


# ---------------------------------------------------------------------------
# Milestone 2: TCP echo. A connection, and a byte stream with no boundaries.
# ---------------------------------------------------------------------------

def tcp_echo_server(port=9002, ready=None, max_clients=None):
    """Accept one client at a time and echo every byte it sends."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
        # Allow restarting the server immediately (skip waiting out TIME_WAIT, ch. 8).
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((HOST, port))
        srv.listen()
        port = srv.getsockname()[1]
        print(f"TCP echo server listening on {HOST}:{port}")
        if ready:
            ready(port)
        served = 0
        while max_clients is None or served < max_clients:
            conn, addr = srv.accept()                 # blocks until a handshake completes
            print(f"connection from {addr[0]}:{addr[1]}")
            with conn:
                while True:
                    chunk = conn.recv(4096)           # up to 4096 bytes: maybe fewer
                    if not chunk:                     # b"" means the client closed (FIN)
                        break
                    print(f"  recv() returned {len(chunk)} bytes: {chunk!r}")
                    conn.sendall(chunk)               # send() may send only part; sendall loops
            print(f"{addr[0]}:{addr[1]} disconnected")
            served += 1


# ---------------------------------------------------------------------------
# Milestone 3: framing. Turn a byte stream back into messages (lines).
# ---------------------------------------------------------------------------

class LineBuffer:
    """Collects bytes from a TCP stream and hands back complete lines.

    feed(b"hel")          -> []
    feed(b"lo\\nwor")      -> ["hello"]
    feed(b"ld\\r\\n")       -> ["world"]
    """

    def __init__(self):
        self._buf = b""

    def feed(self, data):
        self._buf += data
        *lines, self._buf = self._buf.split(b"\n")   # the last piece is incomplete
        return [line.rstrip(b"\r").decode("utf-8", "replace") for line in lines]


# ---------------------------------------------------------------------------
# Milestone 4: a chat server. Many clients, one thread, a selector.
# ---------------------------------------------------------------------------

class Client:
    def __init__(self, sock, addr):
        self.sock = sock
        self.addr = addr
        self.name = f"guest-{addr[1]}"     # the client's ephemeral port makes a handy id
        self.lines = LineBuffer()


class ChatServer:
    def __init__(self, port=9003):
        self.port = port
        self.sel = selectors.DefaultSelector()
        self.clients = {}                  # socket -> Client

    def serve_forever(self, ready=None, stop=None):
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((HOST, self.port))
        srv.listen()
        self.port = srv.getsockname()[1]
        self.sel.register(srv, selectors.EVENT_READ, data=None)
        print(f"chat server listening on {HOST}:{self.port}  (connect with: nc {HOST} {self.port})")
        if ready:
            ready(self.port)
        try:
            while stop is None or not stop.is_set():
                # Wait until at least one socket is readable (or 0.2 s passes).
                for key, _ in self.sel.select(timeout=0.2):
                    if key.data is None:
                        self._accept(key.fileobj)
                    else:
                        self._read(key.data)
        finally:
            for client in list(self.clients.values()):
                client.sock.close()
            self.sel.close()
            srv.close()

    def _accept(self, srv):
        sock, addr = srv.accept()
        # Blocking socket with a send timeout: a client that stops reading can
        # stall sendall(); after 2 s we give up on it instead of freezing everyone.
        sock.settimeout(2.0)
        client = Client(sock, addr)
        self.clients[sock] = client
        self.sel.register(sock, selectors.EVENT_READ, data=client)
        print(f"+ {client.name} connected ({len(self.clients)} online)")
        self._send(client, WELCOME)
        self.broadcast(fmt_notice(f"{client.name} joined"), exclude=client)

    def _read(self, client):
        try:
            data = client.sock.recv(4096)
        except OSError:
            data = b""
        if not data:
            self._disconnect(client)
            return
        for line in client.lines.feed(data):
            self._handle_line(client, line)
            if client.sock not in self.clients:   # /quit closed it
                return

    def _handle_line(self, client, line):
        line = line.strip()
        if not line:
            return
        if line.startswith("/nick "):
            new = line[6:].strip()[:20] or client.name
            old, client.name = client.name, new
            self.broadcast(fmt_notice(f"{old} is now {new}"))
        elif line == "/quit":
            self._disconnect(client)
        else:
            self.broadcast(fmt_chat(client.name, line), exclude=client)

    def broadcast(self, text, exclude=None):
        for client in list(self.clients.values()):
            if client is not exclude:
                self._send(client, text)

    def _send(self, client, text):
        try:
            client.sock.sendall(text.encode("utf-8"))
        except OSError:                    # includes socket.timeout
            self._disconnect(client)

    def _disconnect(self, client):
        if client.sock not in self.clients:
            return
        self.sel.unregister(client.sock)
        del self.clients[client.sock]
        client.sock.close()
        print(f"- {client.name} left ({len(self.clients)} online)")
        self.broadcast(fmt_notice(f"{client.name} left"))


def run_chat_server(port=9003, ready=None, stop=None):
    ChatServer(port).serve_forever(ready=ready, stop=stop)


def chat_client(port=9003):
    """A tiny client for systems without nc: one thread prints, the main thread types."""
    sock = socket.create_connection((HOST, port))

    def printer():
        lines = LineBuffer()
        while True:
            data = sock.recv(4096)
            if not data:
                print("(server closed the connection)")
                break
            for line in lines.feed(data):
                print(line)

    threading.Thread(target=printer, daemon=True).start()
    try:
        for line in sys.stdin:
            sock.sendall(line.encode("utf-8"))
            if line.strip() == "/quit":
                break
    finally:
        sock.close()


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, default in [("udp-server", 9001), ("tcp-server", 9002), ("chat-server", 9003), ("chat-client", 9003)]:
        sp = sub.add_parser(name)
        sp.add_argument("--port", type=int, default=default)
    sp = sub.add_parser("udp-send")
    sp.add_argument("message")
    sp.add_argument("--port", type=int, default=9001)
    args = p.parse_args()
    try:
        if args.cmd == "udp-server":
            udp_echo_server(args.port)
        elif args.cmd == "udp-send":
            reply = udp_send(args.message, args.port)
            print(reply if reply is not None else "(no reply: timed out)")
        elif args.cmd == "tcp-server":
            tcp_echo_server(args.port)
        elif args.cmd == "chat-server":
            run_chat_server(args.port)
        elif args.cmd == "chat-client":
            chat_client(args.port)
    except KeyboardInterrupt:
        print("\nbye")


if __name__ == "__main__":
    main()
