"""Lab 1 starter: sockets and a chat server.

Fill in every TODO, one milestone at a time, and run `python3 check.py`
after each one. The lab page walks you through it.

Usage (run each server in its own terminal):
    python3 starter.py udp-server              # milestone 1
    python3 starter.py udp-send "hello"
    python3 starter.py tcp-server              # milestone 2
    python3 starter.py chat-server             # milestone 4
    python3 starter.py chat-client             # or: nc 127.0.0.1 9003

Every server takes port=0 ("pick any free port") and must call ready(port)
once it is listening, so check.py can find it.
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
    """Receive datagrams and send each one straight back in upper case.

    Steps:
      1. Create a UDP socket: socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
      2. bind((HOST, port)), then read the real port with sock.getsockname()[1]
         (it differs from `port` when port is 0) and call ready(real_port) if ready.
      3. Loop (stop after max_messages if it isn't None):
         data, addr = sock.recvfrom(2048), then sock.sendto(data.upper(), addr)
    """
    raise NotImplementedError("TODO milestone 1: udp_echo_server")


def udp_send(message, port=9001, timeout=2.0):
    """Send one datagram to (HOST, port) and wait for one reply.

    Return the reply as a str, or None if nothing arrives within `timeout`
    seconds. Hints: sock.settimeout(timeout); catch socket.timeout (and
    ConnectionRefusedError, which some systems raise for a closed UDP port).
    """
    raise NotImplementedError("TODO milestone 1: udp_send")


# ---------------------------------------------------------------------------
# Milestone 2: TCP echo. A connection, and a byte stream with no boundaries.
# ---------------------------------------------------------------------------

def tcp_echo_server(port=9002, ready=None, max_clients=None):
    """Accept one client at a time and echo every byte it sends.

    Steps:
      1. TCP socket (SOCK_STREAM); setsockopt(SOL_SOCKET, SO_REUSEADDR, 1);
         bind; listen(); call ready(real_port).
      2. Loop: conn, addr = srv.accept()
         then keep calling conn.recv(4096) and conn.sendall(chunk)
         until recv returns b"" (the client closed the connection).
      3. Close conn and stop after max_clients clients if it isn't None.
    Print what each recv() returns: you'll see how TCP splits and merges data.
    """
    raise NotImplementedError("TODO milestone 2: tcp_echo_server")


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
        """Add data; return a list of complete lines (str, without \\n or \\r).

        Keep the incomplete tail in self._buf for next time. Decode each
        complete line with .decode("utf-8", "replace"), and only decode
        complete lines: a multi-byte character may be split across two feeds.
        """
        raise NotImplementedError("TODO milestone 3: LineBuffer.feed")


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
    """The event loop is written for you; you write the handlers below it."""

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
                    if key.data is None:          # the listening socket: a new client
                        self._accept(key.fileobj)
                    else:                         # a client socket: data (or a hang-up)
                        self._read(key.data)
        finally:
            for client in list(self.clients.values()):
                client.sock.close()
            self.sel.close()
            srv.close()

    def _accept(self, srv):
        """accept() the new connection, sock.settimeout(2.0), create a Client,
        store it in self.clients, register it with the selector
        (selectors.EVENT_READ, data=client), send it WELCOME, and tell everyone
        else: fmt_notice(f"{client.name} joined")."""
        raise NotImplementedError("TODO milestone 4: _accept")

    def _read(self, client):
        """recv(4096) from the client. b"" (or an OSError) means it hung up:
        call _disconnect. Otherwise feed the bytes to client.lines and call
        _handle_line for every complete line (stop if the client is gone)."""
        raise NotImplementedError("TODO milestone 4: _read")

    def _handle_line(self, client, line):
        """Ignore empty lines.
        "/nick NAME" -> rename (max 20 chars) and broadcast fmt_notice(f"{old} is now {new}") to everyone
        "/quit"      -> _disconnect(client)
        anything else -> broadcast fmt_chat(client.name, line) to everyone except the sender"""
        raise NotImplementedError("TODO milestone 4: _handle_line")

    def broadcast(self, text, exclude=None):
        """_send text to every client except `exclude`. Iterate over a copy
        (list(...)): a failed send removes a client while you loop."""
        raise NotImplementedError("TODO milestone 4: broadcast")

    def _send(self, client, text):
        """sendall the UTF-8 bytes; on OSError (including socket.timeout) _disconnect."""
        raise NotImplementedError("TODO milestone 4: _send")

    def _disconnect(self, client):
        """If the client is still known: unregister it from the selector,
        remove it from self.clients, close its socket, and broadcast
        fmt_notice(f"{client.name} left")."""
        raise NotImplementedError("TODO milestone 4: _disconnect")


def run_chat_server(port=9003, ready=None, stop=None):
    ChatServer(port).serve_forever(ready=ready, stop=stop)


def chat_client(port=9003):
    """A tiny client for systems without nc (needs your LineBuffer)."""
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
    except NotImplementedError as e:
        print(f"Not written yet: {e}")


if __name__ == "__main__":
    main()
