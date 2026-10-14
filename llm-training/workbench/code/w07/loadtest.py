"""Load-test any OpenAI-compatible server: throughput, time to first token
and inter-token latency at rising concurrency (chapter 20's three clocks).

Laptop (any server on port 8000, for example `transformers serve`):
    python loadtest.py --model HuggingFaceTB/SmolLM2-135M-Instruct
GPU box (vLLM, longer prompts and answers, more levels):
    python loadtest.py --model Qwen/Qwen2.5-7B-Instruct --ignore-eos \
        --levels 1,2,4,8,16,32,64,128,192,256 --prompt-words 400 \
        --max-tokens 256

Needs: httpx (installed with transformers)."""
import argparse
import asyncio
import json
import random
import time

import httpx

# ── 1. Settings ──────────────────────────────────────────────────────────
ap = argparse.ArgumentParser()
ap.add_argument("--base-url", default="http://localhost:8000/v1")
ap.add_argument("--model", default="HuggingFaceTB/SmolLM2-135M-Instruct")
ap.add_argument("--levels", default="1,2,4,8,16")     # concurrency levels
ap.add_argument("--per-slot", type=int, default=3)    # requests per slot
ap.add_argument("--max-tokens", type=int, default=48)  # answer length
ap.add_argument("--prompt-words", type=int, default=60)
ap.add_argument("--ignore-eos", action="store_true")  # vLLM only
ap.add_argument("--seed", type=int, default=0)
args, _ = ap.parse_known_args()        # notebooks pass their own flags

WORDS = ("the of and to in is that it was for on are as with his they at "
         "be this have from or one had by word but not what all were we "
         "when your can said there use an each which she do how their if "
         "will up other about out many then them these so some her would "
         "make like him into time has look two more write go see number "
         "no way could people my than first water been call who oil its "
         "now find long down day did get come made may part").split()
rng = random.Random(args.seed)


def make_prompt(i):
    """A fresh prompt per request, so no server can reuse a cached prefix."""
    body = " ".join(rng.choice(WORDS) for _ in range(args.prompt_words))
    return f"Request {i}. Continue this text at length: {body}"


# ── 2. One streaming request: stamp the clock at every token ─────────────
async def one_request(client, i):
    body = {"model": args.model, "stream": True,
            "max_tokens": args.max_tokens, "temperature": 0.8,
            "messages": [{"role": "user", "content": make_prompt(i)}]}
    if args.ignore_eos:                    # vLLM extension: fixed length
        body["ignore_eos"] = True
    t0 = time.perf_counter()
    stamps = []                            # arrival time of each token
    async with client.stream("POST", args.base_url + "/chat/completions",
                             json=body) as r:
        r.raise_for_status()
        async for line in r.aiter_lines():
            if not line.startswith("data: ") or line.endswith("[DONE]"):
                continue
            chunks = json.loads(line[6:]).get("choices") or [{}]
            if chunks[0].get("delta", {}).get("content"):
                stamps.append(time.perf_counter())   # one chunk, one token
    return {"ttft": stamps[0] - t0,        # first token minus send time
            "gaps": [b - a for a, b in zip(stamps, stamps[1:])],
            "tokens": len(stamps), "end": time.perf_counter()}


# ── 3. One level: keep c requests in flight until n have finished ────────
async def run_level(client, c, first_id):
    n = c * args.per_slot
    ids = iter(range(first_id, first_id + n))

    async def worker():                    # a closed loop: one slot
        out = []
        for i in ids:
            out.append(await one_request(client, i))
        return out

    start = time.perf_counter()
    done = await asyncio.gather(*[worker() for _ in range(c)])
    wall = time.perf_counter() - start
    return [r for rs in done for r in rs], wall


def pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(p / 100 * len(xs)))]


# ── 4. Sweep the levels and print the table ──────────────────────────────
async def main():
    limits = httpx.Limits(max_connections=1000)
    async with httpx.AsyncClient(timeout=600, limits=limits) as client:
        await one_request(client, -1)      # warm-up, not counted
        print(f"{args.model} at {args.base_url}; {args.prompt_words} "
              f"prompt words, {args.max_tokens} tokens per answer")
        print(f"{'conc':>5} {'reqs':>5} {'tok/s':>8} {'gain':>6} "
              f"{'TTFT p50':>9} {'TTFT p95':>9} {'ITL p50':>8} "
              f"{'ITL p99':>8}   (ms)")
        prev, first_id = None, 0
        for c in [int(x) for x in args.levels.split(",")]:
            rs, wall = await run_level(client, c, first_id)
            first_id += len(rs)
            tps = sum(r["tokens"] for r in rs) / wall
            ttft = [r["ttft"] * 1000 for r in rs]
            itl = [g * 1000 for r in rs for g in r["gaps"]]
            gain = f"{tps / prev:.2f}x" if prev else ""
            print(f"{c:>5} {len(rs):>5} {tps:>8.1f} {gain:>6} "
                  f"{pct(ttft, 50):>9.0f} {pct(ttft, 95):>9.0f} "
                  f"{pct(itl, 50):>8.1f} {pct(itl, 99):>8.1f}")
            prev = tps


asyncio.run(main())
