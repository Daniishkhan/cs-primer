"""Time a RunPod Serverless endpoint: the first request against the rest.

Against the worker running on your laptop (python handler.py --rp_serve_api):
    python client.py --url http://localhost:8000/runsync
Against a deployed endpoint (the key comes from the RunPod console):
    export RUNPOD_API_KEY=...
    python client.py --endpoint ENDPOINT_ID
    python client.py --endpoint ENDPOINT_ID --gap 30   # let it scale to 0

Needs: httpx (installed with transformers)."""
import argparse
import os
import statistics
import time

import httpx

# ── 1. Settings ──────────────────────────────────────────────────────────
ap = argparse.ArgumentParser()
ap.add_argument("--endpoint", default="")      # RunPod endpoint id
ap.add_argument("--url", default="")           # or a full /runsync URL
ap.add_argument("--n", type=int, default=6)    # requests to send
ap.add_argument("--gap", type=float, default=0)    # seconds between them
ap.add_argument("--prompt", default="Name three uses of a load balancer.")
ap.add_argument("--max-tokens", type=int, default=24)
args, _ = ap.parse_known_args()        # notebooks pass their own flags

URL = args.url or f"https://api.runpod.ai/v2/{args.endpoint}/runsync"
HEADERS = {"content-type": "application/json"}
if os.environ.get("RUNPOD_API_KEY"):
    HEADERS["authorization"] = "Bearer " + os.environ["RUNPOD_API_KEY"]
BODY = {"input": {"prompt": args.prompt, "max_tokens": args.max_tokens}}

# ── 2. Send the requests one at a time and time each ─────────────────────
print(f"POST {URL}")
print(f"{'#':>2} {'wall ms':>8} {'status':>10} {'delay ms':>9} "
      f"{'exec ms':>8} {'job on worker':>14}")
walls = []
with httpx.Client(timeout=330) as client:
    for i in range(args.n):
        if i and args.gap:
            time.sleep(args.gap)
        start = time.perf_counter()
        reply = client.post(URL, json=BODY, headers=HEADERS)
        wall = 1000 * (time.perf_counter() - start)
        reply.raise_for_status()
        job = reply.json()
        out = job.get("output") or {}
        walls.append(wall)
        print(f"{i + 1:>2} {wall:>8.0f} {job.get('status', '?'):>10} "
              f"{job.get('delayTime', '-'):>9} "
              f"{job.get('executionTime', '-'):>8} "
              f"{out.get('job_number', '?'):>14}")

# The local server leaves delayTime and executionTime out; RunPod's has them.
print("worker start-up, seconds:", out.get("start_up_s"))

# ── 3. First request against the rest ────────────────────────────────────
if len(walls) > 1:
    warm = statistics.median(walls[1:])
    print(f"\nfirst request {walls[0]:.0f} ms; median of the other "
          f"{len(walls) - 1}: {warm:.0f} ms; first / warm = "
          f"{walls[0] / warm:.1f}x")
