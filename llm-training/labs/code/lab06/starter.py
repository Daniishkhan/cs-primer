"""Lab 6: A Serving Simulator.

Chapters 18, 20 and 22 explained why serving an LLM is a scheduling and memory problem: decode is
memory-bound, so batching shares the cost of reading the weights; each running request owns a KV
cache that grows by one token a step; and the engine decides who runs, where the cache lives and
what to do when it is full. This lab simulates exactly that, one GPU, one clock, no real model:

    sizing: KV bytes per token --> pages in the budget --> a paged allocator with block tables
    workload: seeded Poisson arrivals, lognormal prompt and output lengths --> metrics
    static batching --> continuous batching with paged allocation --> preemption when the cache is full
    --> capacity under a latency SLO, and what a token costs

Standard-library Python only; every random draw comes from a seeded random.Random. TIME is in
milliseconds and is advanced by the model of a forward pass in `step_time_ms`; nothing sleeps.

Notation follows chapters 18, 20 and 22: B is the batch, a "step" is one forward pass of the whole
batch, TTFT is time to first token, ITL/TPOT is time per output token, and one KV "page" holds
`page_tokens` tokens of cache for one request.

What is GIVEN: the data classes, the GPU configuration, `Live` (per-request mutable state) and a few
helpers. What YOU write is marked TODO:

    1  kv_bytes_per_token, cache_pages, PageAllocator
    2  step_time_ms, make_workload, percentile, summarise
    3  simulate_static
    4  simulate_continuous
    5  preempt_one
    6  run_sweep, max_rate_under_slo, cost_per_million
"""
import heapq
import math
import random
from collections import deque, namedtuple

# =============================================================================
# GIVEN: data classes
# =============================================================================
Request = namedtuple("Request", "rid arrival_ms prompt_len output_len max_new")
# rid: 0, 1, 2, ... in arrival order. prompt_len: tokens in the prompt. output_len: tokens the model
# will actually generate (unknown to the scheduler in advance). max_new: the client's max_tokens
# limit (>= output_len), which a reserve-everything allocator must provision for.

Config = namedtuple("Config", "total_pages page_tokens max_batch alloc base_ms kv_ms prefill_ms")
# total_pages, page_tokens: the KV cache budget is total_pages * page_tokens tokens.
# max_batch: most requests that may run in one step. alloc: "paged" (pages as the sequence grows)
# or "reserve" (prompt_len + max_new tokens up front). base_ms, kv_ms, prefill_ms: the cost model of
# step_time_ms.

Done = namedtuple("Done", "rid arrival_ms first_token_ms finish_ms output_len preemptions")
SimResult = namedtuple("SimResult", "done end_ms steps tokens preemptions peak_pages")
# done: one Done per request, sorted by rid. end_ms: the clock when the last token was emitted.
# steps: forward passes run. tokens: output tokens emitted (the sum of output_len). preemptions:
# total preemption events. peak_pages: the most pages in use at any moment.

# The lab's GPU is made up: a 24 GB card running an 8-billion-parameter model in bf16 (the Llama 3 8B
# shape of chapter 18: 32 layers, 8 KV heads of width 128, so 128 KiB of cache per token). These are
# ASSUMPTIONS in the style of chapter 22, not any product's datasheet:
#   weights 8.03e9 x 2 B = 16.06 GB; 1.5 GB of overhead; (24 - 16.06 - 1.5) GB of cache = 3,070 pages
#   of 16 tokens; 1.0 TB/s of memory bandwidth at 70% efficiency and 100 TFLOPS usable for prefill:
#   base_ms     = 16.06e9 B / 0.7e12 B/s            = 22.9 ms   (read all weights once per step)
#   kv_ms       = 131,072 B / 0.7e12 B/s            = 0.000187 ms per cached token read per step
#   prefill_ms  = 2 x 8.03e9 FLOP / 1e14 FLOP/s     = 0.1606 ms per prompt token
DEFAULT = Config(total_pages=3070, page_tokens=16, max_batch=64, alloc="paged",
                 base_ms=22.9, kv_ms=1.87e-4, prefill_ms=0.1606)
LLAMA3_8B = dict(layers=32, kv_heads=8, head_dim=128)


class Live:
    """A request in flight: the immutable Request plus what the simulator learns about it."""
    def __init__(self, req):
        self.req = req
        self.generated = 0          # output tokens emitted so far
        self.first_token_ms = None
        self.preemptions = 0

    @property
    def ctx(self):
        """Tokens currently in this request's KV cache before the next token is produced."""
        return self.req.prompt_len + self.generated


def tokens_needed(live, cfg):
    """Cache capacity (in tokens) a request must own to take part in the next step.

    "paged": its context plus the one token this step adds. "reserve": everything it might ever need,
    prompt_len + max_new, claimed once."""
    if cfg.alloc == "reserve":
        return live.req.prompt_len + live.req.max_new
    return live.ctx + 1


def to_done(live, finish_ms):
    r = live.req
    return Done(r.rid, r.arrival_ms, live.first_token_ms, finish_ms, r.output_len, live.preemptions)


def check_fits(requests, cfg, alloc):
    """Raise ValueError if some request could never run, even alone in an empty cache."""
    for r in requests:
        need = r.prompt_len + (r.max_new if cfg.alloc == "reserve" else r.output_len)
        if alloc.pages_needed(need) > cfg.total_pages:
            raise ValueError(f"request {r.rid} needs {alloc.pages_needed(need)} pages, the cache has {cfg.total_pages}")


# =============================================================================
# MILESTONE 1: sizing and paging
# =============================================================================
def kv_bytes_per_token(layers, kv_heads, head_dim, bytes_per=2):
    """Bytes of KV cache one token occupies: 2 (keys and values) x layers x kv_heads x head_dim x
    bytes_per number. Llama 3 8B in bf16: kv_bytes_per_token(32, 8, 128) == 131072."""
    raise NotImplementedError("TODO milestone 1: kv_bytes_per_token")


def cache_pages(gpu_bytes, weight_bytes, overhead_bytes, kv_bytes_tok, page_tokens):
    """How many whole pages of KV cache fit once weights and overhead are subtracted from the GPU's
    memory: floor((gpu - weights - overhead) / (kv_bytes_tok * page_tokens)), never negative.

    cache_pages(24e9, 16.06e9, 1.5e9, 131072, 16) == 3070"""
    raise NotImplementedError("TODO milestone 1: cache_pages")


class PageAllocator:
    """A pool of `total_pages` physical pages of `page_tokens` tokens each, handed out like virtual
    memory: each request owns a BLOCK TABLE, a list of physical page numbers that need not be
    contiguous.

    * Free pages are handed out lowest-numbered first (use a heap), and released pages go back.
    * reserve(rid, tokens) makes sure rid owns at least pages_needed(tokens) pages, adding pages to
      the end of its block table as needed. Pages are never taken away by reserve. If the pool cannot
      supply all the missing pages it changes NOTHING and returns False; otherwise True.
    * release(rid) returns all of rid's pages to the pool and reports how many (0 if unknown).
    * peak_pages is the largest used_pages value ever seen (update it inside reserve).
    """
    def __init__(self, total_pages, page_tokens):
        self.total_pages = total_pages
        self.page_tokens = page_tokens
        raise NotImplementedError("TODO milestone 1: PageAllocator.__init__")

    def pages_needed(self, tokens):
        """ceil(tokens / page_tokens); 0 for tokens <= 0."""
        raise NotImplementedError("TODO milestone 1: PageAllocator.pages_needed")

    @property
    def free_pages(self):
        raise NotImplementedError("TODO milestone 1: PageAllocator.free_pages")

    @property
    def used_pages(self):
        raise NotImplementedError("TODO milestone 1: PageAllocator.used_pages")

    def block_table(self, rid):
        """The physical page numbers rid owns, in logical order (a copy); [] if none."""
        raise NotImplementedError("TODO milestone 1: PageAllocator.block_table")

    def reserve(self, rid, tokens):
        """Ensure rid owns enough pages for `tokens` tokens. All or nothing. Returns True/False."""
        raise NotImplementedError("TODO milestone 1: PageAllocator.reserve")

    def release(self, rid):
        """Return all of rid's pages to the pool; the number of pages freed."""
        raise NotImplementedError("TODO milestone 1: PageAllocator.release")


# =============================================================================
# MILESTONE 2: the cost model, the workload and the metrics
# =============================================================================
def step_time_ms(cfg, kv_tokens, prefill_tokens):
    """Duration of one forward pass of the batch, in ms.

    cfg.base_ms + cfg.kv_ms * kv_tokens + cfg.prefill_ms * prefill_tokens, where kv_tokens is the
    total number of cached tokens that attention reads in this step (the contexts of the requests
    that are DECODING) and prefill_tokens the prompt tokens being processed in this step. The base
    is paid once per step however many requests run: that is the weights being read from HBM, and
    why batching is cheap (chapter 18)."""
    raise NotImplementedError("TODO milestone 2: step_time_ms")


def make_workload(n, rate_per_s, seed, max_new=1024):
    """n requests with Poisson arrivals and lognormal lengths, from random.Random(seed).

    For each request i, in this order, make exactly three draws:
        gap    = rng.expovariate(rate_per_s / 1000.0)         # ms between arrivals; t += gap
        prompt = min(2048, max(16, int(rng.lognormvariate(5.5, 0.8))))
        output = min(500, max(5, int(rng.lognormvariate(4.3, 0.9))))
    Request(i, t, prompt, output, max_new). The first arrival is at t = gap, not 0."""
    raise NotImplementedError("TODO milestone 2: make_workload")


def percentile(values, q):
    """The q-th percentile (0 <= q <= 100) by the NEAREST-RANK rule: sort ascending, take the value
    at rank ceil(q / 100 * n), with rank at least 1. percentile([15, 20, 35, 40, 50], 40) == 20.
    Raise ValueError on an empty list."""
    raise NotImplementedError("TODO milestone 2: percentile")


def summarise(sim):
    """Reduce a SimResult to the numbers an SLO talks about. Returns a dict with the keys

      completed, tokens, preemptions, peak_pages          copied or counted from sim
      throughput_tok_s    tokens / ((end_ms - earliest arrival) / 1000)
      tokens_per_step     tokens / steps
      ttft_p50, ttft_p95, ttft_p99    percentiles of first_token_ms - arrival_ms
      tpot_p50, tpot_p95, tpot_p99    percentiles of (finish_ms - first_token_ms) / (output_len - 1),
                                      over requests with output_len >= 2 (0.0 if there are none)
      e2e_p50, e2e_p95                percentiles of finish_ms - arrival_ms
    """
    raise NotImplementedError("TODO milestone 2: summarise")


# =============================================================================
# MILESTONE 3: static batching
# =============================================================================
def simulate_static(requests, cfg):
    """Static batching: take a batch, run it until EVERY request in it has finished, then the next.

    requests are served first come first served (order by arrival_ms, then rid). The clock starts
    at 0. Loop until every request is done:
      1. If the GPU is idle, jump the clock forward to the next request's arrival if it is later.
      2. Form a batch: take waiting requests in order (arrival_ms <= clock) while there are fewer
         than cfg.max_batch and allocator.reserve(rid, prompt_len + max_new) succeeds. Static
         batching cannot grow a cache mid-batch, so it always reserves the worst case up front,
         whatever cfg.alloc says. Release every reservation when the batch ends.
      3. One PREFILL step for the whole batch: step_time_ms(cfg, 0, sum of prompt_len). Every
         request emits its first token at the end of it.
      4. Then decode steps s = 1, 2, ... up to max(output_len) - 1. In step s the ACTIVE requests
         are those with output_len > s; each reads a cache of prompt_len + s tokens, so the step
         lasts step_time_ms(cfg, sum of (prompt_len + s) over active requests, 0). Each active
         request emits one token at the end of the step; a request whose output_len == s + 1
         finishes then. A finished request still holds its slot until the batch ends, and nothing
         new can join.
    A request with output_len == 1 finishes at the end of the prefill step.
    Raise ValueError (via check_fits) if a request could never fit. Return a SimResult."""
    raise NotImplementedError("TODO milestone 3: simulate_static")


# =============================================================================
# MILESTONE 4: continuous batching
# =============================================================================
def simulate_continuous(requests, cfg):
    """Continuous (iteration-level) batching with a paged or reserved KV cache.

    State: `pending` (not yet arrived), `waiting` (arrived, not running; a deque), `running` (a
    list in admission order), one PageAllocator, the clock t = 0.0, and counters. Validate with
    check_fits first. Repeat until nothing is pending, waiting or running:

      0. Move requests from pending to waiting when arrival_ms <= t. If nothing is waiting or
         running, set t to the next pending arrival and start the loop again.
      A. GROW. For each request s in `running`, in order, make sure the allocator holds
         tokens_needed(s, cfg) tokens for it. If allocator.reserve fails, call
         preempt_one(running, waiting, alloc) and count it; repeat until the reserve succeeds or
         the victim was s itself (then s is gone from `running`).
      B. ADMIT. Only if nothing was preempted in this step (or running is empty): while waiting is
         non-empty and len(running) < cfg.max_batch, try alloc.reserve(rid, tokens_needed(head,
         cfg)) for the head of the queue. On success move it to the END of `running` and remember
         it as new; on failure stop (first come first served: a big request blocks the ones behind).
      C. RUN one step. prefill_tokens = sum of ctx over the NEW requests (their whole prompt, or, for
         a request resuming after preemption, prompt plus the tokens it had already generated);
         kv_tokens = sum of ctx over the other (decoding) requests. t += step_time_ms(cfg,
         kv_tokens, prefill_tokens). EVERY running request then emits one token (generated += 1;
         the first time, first_token_ms = t). One that has emitted output_len tokens finishes at t:
         release its pages and record to_done(live, t).
    Return a SimResult (done sorted by rid; preemptions = number of preempt_one calls)."""
    raise NotImplementedError("TODO milestone 4: simulate_continuous")


# =============================================================================
# MILESTONE 5: preemption
# =============================================================================
def preempt_one(running, waiting, alloc):
    """Free cache by evicting the YOUNGEST running request (the last one in `running`).

    Remove it from `running`, release its pages, count the event on the request
    (victim.preemptions += 1), and put it at the FRONT of `waiting` (waiting.appendleft). It keeps
    `generated`: the tokens already sent to the user stay sent, and when it is admitted again its
    whole context (prompt plus generated tokens) is prefilled again, a RECOMPUTE preemption.
    Return the victim. Raise RuntimeError if `running` is empty."""
    raise NotImplementedError("TODO milestone 5: preempt_one")


# =============================================================================
# MILESTONE 6: capacity under an SLO, and what a token costs
# =============================================================================
POLICIES = {
    "static": lambda reqs, cfg: simulate_static(reqs, cfg),
    "continuous, reserve": lambda reqs, cfg: simulate_continuous(reqs, cfg._replace(alloc="reserve")),
    "continuous, paged": lambda reqs, cfg: simulate_continuous(reqs, cfg._replace(alloc="paged")),
}


def run_sweep(policy, rates, n, seed, cfg):
    """For each arrival rate (requests per second, ascending), simulate `policy` (a key of POLICIES)
    on make_workload(n, rate, seed) and return a list of dicts: summarise(...) plus the key "rate".
    All rates share the same seed, so the workloads differ only by their time scale."""
    raise NotImplementedError("TODO milestone 6: run_sweep")


def max_rate_under_slo(rows, ttft_p95_ms, tpot_p95_ms):
    """The highest arrival rate the system sustains within its SLO: scan rows in order and return
    the "rate" of the last row BEFORE the first one that violates it (ttft_p95 > ttft_p95_ms or
    tpot_p95 > tpot_p95_ms). 0.0 if the first row already violates it; the last rate if none does."""
    raise NotImplementedError("TODO milestone 6: max_rate_under_slo")


def cost_per_million(tokens_per_s, price_per_hour):
    """Dollars per million tokens for a GPU that costs `price_per_hour` and sustains `tokens_per_s`
    (chapter 22): price_per_hour / (tokens_per_s * 3600) * 1e6."""
    raise NotImplementedError("TODO milestone 6: cost_per_million")


def print_rows(name, rows):
    print(name)
    print(f"{'req/s':>6}{'tok/s':>8}{'tok/step':>9}{'ttft p95':>10}{'tpot p95':>10}{'preempt':>8}{'peak pg':>8}")
    for r in rows:
        print(f"{r['rate']:6.1f}{r['throughput_tok_s']:8.0f}{r['tokens_per_step']:9.1f}"
              f"{r['ttft_p95']:10.0f}{r['tpot_p95']:10.1f}{r['preemptions']:8d}{r['peak_pages']:8d}")


if __name__ == "__main__":
    for pol in POLICIES:
        print_rows(pol, run_sweep(pol, [4, 8, 12, 16], 300, 1, DEFAULT))
