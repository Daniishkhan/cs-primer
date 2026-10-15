"""Evolution at scale: many model calls in flight, islands, and a pool of
worker processes that score the candidates. Measures samples per minute.

Lab VM (a small model behind any OpenAI-compatible server; sweeps workers):
    python scale_evolve.py --base-url http://127.0.0.1:8000/v1 \\
        --model Qwen/Qwen2.5-0.5B-Instruct --workers 1,2,4,8
GPU box (vLLM serving a 7B model, 64 requests in flight):
    python scale_evolve.py --base-url http://localhost:8000/v1 \\
        --model Qwen/Qwen2.5-Coder-7B-Instruct --workers 64 \\
        --islands 16 --calls 2000 --eval-procs 8

Needs: Python 3.9+, binpack.py and sampler.py next to this file."""
import argparse
import random
import threading
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

from binpack import (SEED_SRC, TRAIN_SEEDS, TEST_SEEDS, Database, canonical,
                     evaluate, evaluate_seeds, make_instances)
from sampler import build_prompt, chat, extract


# ── 1. Settings ──────────────────────────────────────────────────────────
def get_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://localhost:11434/v1")
    ap.add_argument("--model", default="qwen2.5-coder:7b")
    ap.add_argument("--workers", default="1,2,4,8")  # in flight
    ap.add_argument("--calls", type=int, default=48)  # per setting
    ap.add_argument("--islands", type=int, default=8)
    ap.add_argument("--eval-procs", type=int, default=2)
    ap.add_argument("--shots", type=int, default=2)
    ap.add_argument("--temperature", type=float, default=0.8)
    ap.add_argument("--max-tokens", type=int, default=300)
    ap.add_argument("--reseed-every", type=int, default=24)
    ap.add_argument("--seed", type=int, default=0)
    args, _ = ap.parse_known_args()    # notebooks pass their own flags
    return args


# ── 2. One run: `workers` requests in flight until `calls` are done ──────
def run_once(args, workers, pool):
    rng = random.Random(args.seed)
    train = make_instances(TRAIN_SEEDS)
    seed_src = canonical(SEED_SRC)
    db = Database(args.islands, seed_src, evaluate(seed_src, train))
    lock = threading.Lock()              # guards db, rng, seen and stats
    seen, stats = {seed_src}, Counter()

    def one_call(call):
        with lock:                       # choose parents: fast, in memory
            isl = db.islands[call % args.islands]
            parents = isl.sample(rng, args.shots)
        scores = [evaluate(p, train).score for p in parents]
        t0 = time.time()                 # the slow part: no lock held
        reply, usage = chat(args.base_url, args.model,
                            build_prompt(parents, scores),
                            args.temperature, args.max_tokens)
        wait = time.time() - t0
        src = extract(reply)
        with lock:
            fresh = src is not None and src not in seen
            seen.add(src)
        status = "no_code" if src is None else "duplicate"
        if fresh:                        # scored in another process
            t1 = time.time()
            out = pool.submit(evaluate_seeds, src, TRAIN_SEEDS).result()
            stats["eval_s"] += time.time() - t1
            status = out.status
            with lock:
                isl.add(src, out)
        with lock:
            stats[status] += 1
            stats["wait_s"] += wait
            stats["prompt_tokens"] += usage.get("prompt_tokens", 0)
            stats["out_tokens"] += usage.get("completion_tokens", 0)
            stats["done"] += 1
            if stats["done"] % args.reseed_every == 0:
                db.reseed(rng)

    start = time.time()
    with ThreadPoolExecutor(workers) as threads:
        list(threads.map(one_call, range(args.calls)))
    return time.time() - start, stats, db


# ── 3. Sweep the number of requests in flight ────────────────────────────
def main():
    args = get_args()
    print(f"model {args.model} at {args.base_url}")
    print(f"{args.calls} calls per setting, {args.islands} islands, "
          f"{args.eval_procs} scoring processes\n")
    chat(args.base_url, args.model, "Say hi.", 0, 8)   # warm-up, not timed
    print(f"{'in flight':>9s} {'wall s':>7s} {'samples/min':>12s} "
          f"{'speed-up':>9s} {'s/request':>10s} {'out tok/s':>10s} "
          f"{'best':>7s}")
    base = None
    with ProcessPoolExecutor(args.eval_procs) as pool:
        for w in [int(x) for x in args.workers.split(",")]:
            wall, st, db = run_once(args, w, pool)
            rate = args.calls / wall * 60
            base = base or rate
            print(f"{w:9d} {wall:7.1f} {rate:12.1f} {rate / base:8.1f}x "
                  f"{st['wait_s'] / args.calls:10.1f} "
                  f"{st['out_tokens'] / wall:10.1f} {-db.best()[1]:7.2f}")
    # ── 4. What the last setting produced, and what the scoring cost ─────
    outcomes = ("ok", "rejected", "error", "timeout", "bad_value",
                "duplicate", "no_code")
    print("\nlast setting:", ", ".join(f"{k} {st[k]}" for k in outcomes
                                      if st[k]))
    n, scored = args.calls, sum(st[k] for k in outcomes[:5])
    print(f"mean tokens per call: {st['prompt_tokens'] / n:.0f} in, "
          f"{st['out_tokens'] / n:.0f} out")
    print(f"scoring wait per new candidate: "
          f"{1000 * st['eval_s'] / max(1, scored):.0f} ms")
    best, _ = db.best()
    test = make_instances(TEST_SEEDS)
    print(f"best program, held-out test: {evaluate(best, test).score:.2f} "
          f"bins (best fit {evaluate(SEED_SRC, test).score:.2f})")


if __name__ == "__main__":
    main()
