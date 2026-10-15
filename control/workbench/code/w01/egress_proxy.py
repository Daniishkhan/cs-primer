"""An allowlisting egress proxy: the only door out of the sandbox.

    python3 egress_proxy.py --allow pypi.org,files.pythonhosted.org \
        --log proxy.jsonl [--port 3128]

It speaks the two forms an HTTP client uses through a proxy: CONNECT
(tunnel for HTTPS) and a plain request with a full URL. Three checks stand
between a request and the network:

  1. the host name must be on the allowlist;
  2. the name is resolved once, every address must be global (not
     loopback, private, link-local such as the 169.254.169.254 cloud
     metadata service, and so on), and the proxy connects to that checked
     address, never to the name again, so DNS cannot change in between;
  3. a plain request gets its Host header rewritten to the checked host
     and "Connection: close", and only its own body is forwarded, so one
     connection carries exactly one checked request.

Anything else gets 403 and a log line; nothing is forwarded. It sees host
names, not encrypted content. Standard library only.
"""
import argparse
import asyncio
import ipaddress
import json
import socket
import time
from urllib.parse import urlsplit

# ── 1. Settings ───────────────────────────────────────────────────────
ap = argparse.ArgumentParser()
ap.add_argument("--allow", default="pypi.org")      # comma-separated hosts
ap.add_argument("--log", default="proxy.jsonl")
ap.add_argument("--port", type=int, default=3128)
args, _ = ap.parse_known_args()
ALLOW = {h.strip().lower() for h in args.allow.split(",") if h.strip()}
PORTS = {80, 443}                  # nothing else is worth tunnelling to


def allowed(host, port):
    return host.lower() in ALLOW and port in PORTS


async def resolve_checked(host, port):
    """Resolve once. Return (address, all addresses); address is None
    unless there is at least one and every one is a global address."""
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(
            host, port, type=socket.SOCK_STREAM)
    except OSError:
        return None, []
    addrs = [i[4][0].split("%")[0] for i in infos]
    ok = bool(addrs) and all(ipaddress.ip_address(a).is_global
                             for a in addrs)
    return (addrs[0] if ok else None), addrs


def log(**event):
    event["t"] = round(time.time(), 3)
    with open(args.log, "a") as f:
        f.write(json.dumps(event) + "\n")


async def reply(writer, status, text):
    body = text.encode() + b"\r\n"
    writer.write(f"HTTP/1.1 {status}\r\nContent-Length: {len(body)}\r\n"
                 "Connection: close\r\n\r\n".encode() + body)
    await writer.drain()
    writer.close()


async def pipe(reader, writer):
    try:
        while True:
            data = await reader.read(65536)
            if not data:
                break
            writer.write(data)
            await writer.drain()
    except (ConnectionError, asyncio.CancelledError):
        pass
    finally:
        writer.close()


# ── 2. One client connection ──────────────────────────────────────────
async def handle(reader, writer):
    head = await reader.readuntil(b"\r\n\r\n")
    request_line, *header_lines = head.decode("latin-1").split("\r\n")
    method, target, version = request_line.split(" ", 2)
    headers = [h for h in header_lines if h]
    if method == "CONNECT":
        host, _, port = target.rpartition(":")
        port = int(port)
    else:
        url = urlsplit(target)
        host, port = url.hostname or "", url.port or 80
        path = (url.path or "/") + ("?" + url.query if url.query else "")
    if not allowed(host, port):
        log(method=method, host=host, port=port, verdict="deny",
            why="not on the allowlist")
        return await reply(writer, "403 Forbidden",
                           "denied by egress allowlist")
    addr, addrs = await resolve_checked(host, port)
    if addr is None:
        log(method=method, host=host, port=port, verdict="deny",
            why="resolves to a non-global address", addresses=addrs)
        return await reply(writer, "403 Forbidden",
                           "denied: name resolves to an internal address")
    names = {h.split(":", 1)[0].strip().lower(): h for h in headers}
    if method != "CONNECT" and "transfer-encoding" in names:
        log(method=method, host=host, port=port, verdict="deny",
            why="chunked request body")
        return await reply(writer, "501 Not Implemented",
                           "chunked request bodies are not supported")
    try:
        up_r, up_w = await asyncio.open_connection(addr, port)  # the IP
    except OSError as e:
        log(method=method, host=host, port=port, verdict="error",
            why=str(e))
        return await reply(writer, "502 Bad Gateway", "upstream failed")
    log(method=method, host=host, port=port, verdict="allow", address=addr)
    if method == "CONNECT":
        writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
        await asyncio.gather(pipe(reader, up_w), pipe(up_r, writer))
        return
    # Plain HTTP: one request per connection, with our own Host header.
    drop = {"host", "connection", "keep-alive", "proxy-connection",
            "proxy-authorization", "proxy-authenticate"}
    kept = [h for h in headers if h.split(":", 1)[0].strip().lower()
            not in drop]
    shown = host if port == 80 else f"{host}:{port}"
    out = [f"{method} {path} {version}", f"Host: {shown}",
           "Connection: close"] + kept
    length = int(names.get("content-length", "content-length: 0")
                 .split(":", 1)[1])
    body = await reader.readexactly(length) if length else b""
    up_w.write(("\r\n".join(out) + "\r\n\r\n").encode("latin-1") + body)
    await up_w.drain()
    await pipe(up_r, writer)       # the reply; anything else the client
    up_w.close()                   # sent on this connection is ignored


# ── 3. Serve ──────────────────────────────────────────────────────────
async def main():
    server = await asyncio.start_server(handle, "127.0.0.1", args.port)
    print(f"egress proxy on 127.0.0.1:{args.port}, allow {sorted(ALLOW)}",
          flush=True)
    async with server:
        await server.serve_forever()

if __name__ == "__main__":
    asyncio.run(main())
