"""An allowlisting egress proxy: the only door out of the sandbox.

    python3 egress_proxy.py --allow pypi.org,files.pythonhosted.org \
        --log proxy.jsonl [--port 3128]

It speaks the two forms an HTTP client uses through a proxy: CONNECT
(tunnel for HTTPS) and a plain request with a full URL. Anything whose
host is not on the allowlist gets 403 and a log line; nothing is
forwarded. It sees host names, not encrypted content. Standard library
only.
"""
import argparse
import asyncio
import json
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


def log(**event):
    event["t"] = round(time.time(), 3)
    with open(args.log, "a") as f:
        f.write(json.dumps(event) + "\n")


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
    if method == "CONNECT":
        host, _, port = target.rpartition(":")
        port = int(port)
        rest = b""
    else:
        url = urlsplit(target)
        host, port = url.hostname or "", url.port or 80
        path = (url.path or "/") + ("?" + url.query if url.query else "")
        rest = (f"{method} {path} {version}\r\n"
                + "\r\n".join(h for h in header_lines
                              if not h.lower().startswith("proxy-"))
                ).encode("latin-1")
    if not allowed(host, port):
        log(method=method, host=host, port=port, verdict="deny")
        writer.write(b"HTTP/1.1 403 Forbidden\r\nContent-Length: 28\r\n"
                     b"Connection: close\r\n\r\ndenied by egress allowlist\r\n")
        await writer.drain()
        writer.close()
        return
    log(method=method, host=host, port=port, verdict="allow")
    try:
        up_r, up_w = await asyncio.open_connection(host, port)
    except OSError as e:
        writer.write(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
        log(method=method, host=host, port=port, verdict="error",
            why=str(e))
        writer.close()
        return
    if method == "CONNECT":
        writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
    else:
        up_w.write(rest + b"\r\n\r\n")
    await asyncio.gather(pipe(reader, up_w), pipe(up_r, writer))


# ── 3. Serve ──────────────────────────────────────────────────────────
async def main():
    server = await asyncio.start_server(handle, "127.0.0.1", args.port)
    print(f"egress proxy on 127.0.0.1:{args.port}, allow {sorted(ALLOW)}",
          flush=True)
    async with server:
        await server.serve_forever()

if __name__ == "__main__":
    asyncio.run(main())
