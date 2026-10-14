"""Self-check for Lab 6: A Serving Simulator.

    python3 check.py                  # checks your starter.py
    python3 check.py solution         # checks the reference solution
    python3 check.py solution 4       # only milestone 4
    python3 check.py solution 4 7     # milestone 4, replaying ONLY the random cases of seed 7

Everything is seeded: the workloads, the random allocator operations and every test input. There is
no real clock and no network (the simulator advances its own clock), so every run gives identical
numbers. The whole check takes a few seconds.
Prints a tick, a cross, or "not implemented yet" for each milestone.
"""
import importlib
import math
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True

args = sys.argv[1:]
target = args[0] if args and not args[0].isdigit() else "starter"
rest = [a for a in args if a.isdigit()]
ONLY = int(rest[0]) if rest else None
ONLY_SEED = int(rest[1]) if len(rest) > 1 else None
mod = importlib.import_module(target)
results = []


def seeds(default):
    return [ONLY_SEED] if ONLY_SEED is not None else list(default)


def check(number, name, fn):
    if ONLY is not None and ONLY != number:
        return
    try:
        note = fn()
        print(f"  ✔ {name}")
        for line in (note or "").splitlines():
            print(f"      {line}")
        results.append(True)
    except NotImplementedError as e:
        print(f"  … {name}: not implemented yet ({e})")
        results.append(False)
    except AssertionError as e:
        print(f"  ✘ {name}: {e}")
        results.append(False)
    except Exception as e:
        import traceback
        tb = traceback.extract_tb(e.__traceback__)
        where = next((f"{f.name}() line {f.lineno}" for f in reversed(tb) if f.filename.endswith(f"{target}.py")), "?")
        print(f"  ✘ {name}: {type(e).__name__}: {e}   [in {where}]")
        results.append(False)


def near(a, b, tol=1e-9):
    return abs(a - b) <= tol * max(1.0, abs(a), abs(b))


def C(**kw):
    """A small round-number configuration for hand-computed scenarios."""
    base = mod.Config(total_pages=1000, page_tokens=16, max_batch=4, alloc="paged", base_ms=10.0, kv_ms=0.0, prefill_ms=1.0)
    return base._replace(**kw)


def R(rid, arrival, prompt, output, max_new=None):
    return mod.Request(rid, float(arrival), prompt, output, max_new if max_new is not None else output + 8)


def timeline(sim):
    """(first_token_ms, finish_ms) per request, by rid."""
    return [(d.first_token_ms, d.finish_ms) for d in sim.done]


def assert_timeline(sim, want, what):
    got = timeline(sim)
    assert len(got) == len(want) and all(near(a, c, 1e-9) and near(b, d, 1e-9) for (a, b), (c, d) in zip(got, want)), \
        f"{what}: expected (first token, finish) per request {want}, got {[(round(a, 3), round(b, 3)) for a, b in got]}"


# =============================================================================
# Milestone 1: sizing and paging
# =============================================================================
def m1():
    assert mod.kv_bytes_per_token(32, 8, 128) == 131072, "Llama 3 8B in bf16 is 2 x 32 x 8 x 128 x 2 = 131,072 bytes (128 KiB) per token"
    assert mod.kv_bytes_per_token(80, 8, 128) == 327680 and mod.kv_bytes_per_token(32, 32, 128) == 524288, "70B shape (80 layers) and a 32-KV-head model"
    assert mod.kv_bytes_per_token(32, 8, 128, bytes_per=1) == 65536, "bytes_per is a parameter (fp8 cache halves it)"
    assert mod.cache_pages(24e9, 16.06e9, 1.5e9, 131072, 16) == 3070, "24 GB card, 16.06 GB of weights, 1.5 GB overhead: floor(6.44e9 / 2,097,152) = 3070 pages"
    assert mod.cache_pages(24e9, 16.06e9, 1.5e9, 131072, 32) == 1535 and mod.cache_pages(10e9, 16e9, 0, 131072, 16) == 0, \
        "bigger pages, fewer of them; never negative"

    A = mod.PageAllocator
    a = A(8, 4)
    for tokens, want in [(0, 0), (-5, 0), (1, 1), (4, 1), (5, 2), (8, 2), (9, 3)]:
        assert a.pages_needed(tokens) == want, f"pages_needed({tokens}) with 4-token pages should be {want}, got {a.pages_needed(tokens)}"
    assert a.free_pages == 8 and a.used_pages == 0 and a.block_table("x") == []
    assert a.reserve("A", 12) is True and a.block_table("A") == [0, 1, 2], f"first request gets pages 0, 1, 2; got {a.block_table('A')}"
    assert a.reserve("B", 5) is True and a.block_table("B") == [3, 4]
    assert (a.free_pages, a.used_pages) == (3, 5)
    assert a.reserve("A", 13) is True and a.block_table("A") == [0, 1, 2, 5], "growing appends the lowest free page to the END of the block table"
    assert a.reserve("A", 5) is True and a.block_table("A") == [0, 1, 2, 5], "reserve never shrinks a request"
    tbl = a.block_table("A")
    tbl.append(99)
    assert a.block_table("A") == [0, 1, 2, 5], "block_table returns a copy"
    assert a.release("B") == 2 and a.free_pages == 4, "release returns the page count and frees them"
    assert a.reserve("C", 20) is False and a.block_table("C") == [] and a.free_pages == 4, "needing 5 pages with 4 free: all or nothing, nothing changes"
    assert a.reserve("A", 40) is False and a.block_table("A") == [0, 1, 2, 5] and a.free_pages == 4, "a failed GROWTH must not partially extend the table"
    assert a.reserve("C", 16) is True and a.block_table("C") == [3, 4, 6, 7], \
        f"released pages 3 and 4 are reused first (lowest number first), so C is not contiguous in order: expected [3, 4, 6, 7], got {a.block_table('C')}"
    assert a.free_pages == 0 and a.peak_pages == 8, "peak_pages tracks the most pages ever used"
    assert a.release("nobody") == 0 and a.release("C") == 4 and a.release("C") == 0, "releasing an unknown or already-released request frees 0"

    for s in seeds(range(1, 9)):
        rng = random.Random(s)
        a, own, peak = A(30, 8), {}, 0
        for step in range(300):
            rid = rng.randrange(6)
            if rng.random() < 0.25:
                got = a.release(rid)
                assert got == own.pop(rid, 0), f"seed {s} step {step}: release({rid}) freed {got} pages"
            else:
                tokens = rng.randint(1, 120)
                want = -(-tokens // 8)
                have = own.get(rid, 0)
                free = 30 - sum(own.values())
                ok = a.reserve(rid, tokens)
                expect = want <= have or want - have <= free
                assert ok == expect, f"seed {s} step {step}: reserve({rid}, {tokens}) returned {ok}, expected {expect}"
                if ok:
                    own[rid] = max(have, want)
            peak = max(peak, sum(own.values()))
            assert a.used_pages == sum(own.values()) and a.free_pages == 30 - a.used_pages, f"seed {s} step {step}: used/free pages are inconsistent"
            tables = [p for r in range(6) for p in a.block_table(r)]
            assert len(tables) == len(set(tables)), f"seed {s} step {step}: a physical page is owned twice"
            assert all(len(a.block_table(r)) == own.get(r, 0) for r in range(6)), f"seed {s} step {step}: block table lengths differ from the pages owned"
        assert a.peak_pages == peak, f"seed {s}: peak_pages should be {peak}, got {a.peak_pages}"
    return "3,070 pages of 16 tokens fit beside the weights of an 8B model on a 24 GB card; block tables of reused pages are not contiguous"


# =============================================================================
# Milestone 2: the cost model, the workload and the metrics
# =============================================================================
def oracle_workload(n, rate, seed, max_new=1024):
    rng = random.Random(seed)
    t, out = 0.0, []
    for i in range(n):
        t += rng.expovariate(rate / 1000.0)
        p = min(2048, max(16, int(rng.lognormvariate(5.5, 0.8))))
        o = min(500, max(5, int(rng.lognormvariate(4.3, 0.9))))
        out.append((i, t, p, o, max_new))
    return out


def m2():
    cfg = C(base_ms=10.0, kv_ms=0.5, prefill_ms=2.0)
    assert near(mod.step_time_ms(cfg, 100, 20), 100.0) and near(mod.step_time_ms(cfg, 0, 0), 10.0), \
        "step_time_ms = base + kv_ms * kv_tokens + prefill_ms * prefill_tokens: (100, 20) with 10 / 0.5 / 2.0 is 10 + 50 + 40 = 100"
    assert near(mod.step_time_ms(mod.DEFAULT, 1000, 0), 22.9 + 0.187), "default config, 1,000 cached tokens"

    for s in seeds(range(1, 6)):
        w = mod.make_workload(60, 8.0, s)
        want = oracle_workload(60, 8.0, s)
        assert [tuple(r) for r in w] == [tuple(x) for x in want] or all(
            r.rid == x[0] and near(r.arrival_ms, x[1]) and (r.prompt_len, r.output_len, r.max_new) == x[2:] for r, x in zip(w, want)), \
            f"seed {s}: make_workload must make three draws per request in the order gap, prompt, output (see the docstring)"
        assert all(a.arrival_ms <= b.arrival_ms for a, b in zip(w, w[1:])) and w[0].arrival_ms > 0, "arrivals increase; the first is at t = gap > 0"
        assert all(16 <= r.prompt_len <= 2048 and 5 <= r.output_len <= 500 and r.max_new == 1024 for r in w), "lengths are clamped"
        slow, fast = mod.make_workload(30, 4.0, s), mod.make_workload(30, 8.0, s)
        assert all(a.prompt_len == b.prompt_len and a.output_len == b.output_len and near(a.arrival_ms, 2 * b.arrival_ms, 1e-9) for a, b in zip(slow, fast)), \
            f"seed {s}: the same seed at twice the rate must give the same lengths and arrivals compressed by exactly 2"
    big = mod.make_workload(5000, 10.0, 3, max_new=777)
    gaps = big[-1].arrival_ms / len(big)
    assert 95 < gaps < 105 and big[0].max_new == 777, f"10 requests a second should average a gap near 100 ms; got {gaps:.1f}, and max_new is a parameter"
    mean_out = sum(r.output_len for r in big) / len(big)
    assert 90 < mean_out < 112, f"output lengths should average about 100 tokens; got {mean_out:.1f}"

    P = mod.percentile
    assert P([15, 20, 35, 40, 50], 40) == 20 and P([50, 15, 40, 20, 35], 40) == 20, "nearest rank: ceil(0.4 * 5) = 2, the second smallest; input need not be sorted"
    assert P([15, 20, 35, 40, 50], 50) == 35 and P([15, 20, 35, 40, 50], 100) == 50 and P([15, 20, 35, 40, 50], 0) == 15, "q = 50 is rank 3; q = 100 the max; q = 0 the min"
    assert P(list(range(1, 21)), 95) == 19 and P(list(range(1, 21)), 99) == 20, "n = 20: p95 is rank 19, p99 rank 20"
    assert P([7], 99) == 7
    try:
        P([], 50)
    except ValueError:
        pass
    else:
        raise AssertionError("percentile of an empty list must raise ValueError")

    Done = mod.Done
    done = [Done(0, 0.0, 10.0, 40.0, 4, 0), Done(1, 5.0, 25.0, 25.0, 1, 0), Done(2, 10.0, 50.0, 80.0, 7, 0)]
    s = mod.summarise(mod.SimResult(done, 80.0, 10, 12, 2, 7))
    want = {"completed": 3, "tokens": 12, "preemptions": 2, "peak_pages": 7, "throughput_tok_s": 150.0, "tokens_per_step": 1.2,
            "ttft_p50": 20.0, "ttft_p95": 40.0, "ttft_p99": 40.0, "tpot_p50": 5.0, "tpot_p95": 10.0, "tpot_p99": 10.0,
            "e2e_p50": 40.0, "e2e_p95": 70.0}
    for k, v in want.items():
        assert k in s and near(s[k], v), f"summarise()['{k}'] should be {v} for the crafted result, got {s.get(k)}"
    one = mod.summarise(mod.SimResult([Done(0, 0.0, 5.0, 5.0, 1, 0)], 5.0, 1, 1, 0, 1))
    assert one["tpot_p95"] == 0.0, "no request with two or more tokens: the tpot percentiles are 0.0"
    return "step cost, Poisson workload (mean output 100 tokens) and nearest-rank percentiles"


# =============================================================================
# Independent reference simulators, written differently from the lab's own code
# =============================================================================
def oracle_static(requests, cfg):
    reqs = sorted(requests, key=lambda r: (r.arrival_ms, r.rid))
    pg = lambda tok: -(-tok // cfg.page_tokens)
    t, i, used, steps, out = 0.0, 0, 0, 0, {}
    while i < len(reqs):
        t = max(t, reqs[i].arrival_ms)
        batch, used = [], 0
        while i < len(reqs) and len(batch) < cfg.max_batch and reqs[i].arrival_ms <= t \
                and used + pg(reqs[i].prompt_len + reqs[i].max_new) <= cfg.total_pages:
            used += pg(reqs[i].prompt_len + reqs[i].max_new)
            batch.append(reqs[i])
            i += 1
        t += cfg.base_ms + cfg.prefill_ms * sum(r.prompt_len for r in batch)
        steps += 1
        for r in batch:
            out[r.rid] = [t, t if r.output_len == 1 else None]
        for s in range(1, max(r.output_len for r in batch)):
            act = [r for r in batch if r.output_len > s]
            t += cfg.base_ms + cfg.kv_ms * sum(r.prompt_len + s for r in act)
            steps += 1
            for r in act:
                if r.output_len == s + 1:
                    out[r.rid][1] = t
    return out, t, steps


def oracle_continuous(requests, cfg):
    reqs = sorted(requests, key=lambda r: (r.arrival_ms, r.rid))
    by = {r.rid: r for r in reqs}
    n, P = len(reqs), cfg.page_tokens
    pg = lambda tok: -(-tok // P) if tok > 0 else 0
    owned, gen, first, fin, pre = {}, {r.rid: 0 for r in reqs}, {}, {}, {r.rid: 0 for r in reqs}
    waiting, running = [], []
    nxt, t, steps, tokens, npre, peak = 0, 0.0, 0, 0, 0, 0

    def need(rid):
        r = by[rid]
        return r.prompt_len + r.max_new if cfg.alloc == "reserve" else r.prompt_len + gen[rid] + 1

    def grab(rid):
        nonlocal peak
        want, have = pg(need(rid)), owned.get(rid, 0)
        if want <= have:
            return True
        if want - have > cfg.total_pages - sum(owned.values()):
            return False
        owned[rid] = want
        peak = max(peak, sum(owned.values()))
        return True

    ctx = lambda rid: by[rid].prompt_len + gen[rid]
    while len(fin) < n:
        while nxt < n and reqs[nxt].arrival_ms <= t:
            waiting.append(reqs[nxt].rid)
            nxt += 1
        if not waiting and not running:
            t = reqs[nxt].arrival_ms
            continue
        preempted, i = False, 0
        while i < len(running):
            rid = running[i]
            ok = grab(rid)
            while not ok:
                v = running.pop()
                owned.pop(v, None)
                pre[v] += 1
                waiting.insert(0, v)
                npre += 1
                preempted = True
                if v == rid:
                    break
                ok = grab(rid)
            if ok:
                i += 1
        new = []
        if not preempted or not running:
            while waiting and len(running) < cfg.max_batch and grab(waiting[0]):
                rid = waiting.pop(0)
                running.append(rid)
                new.append(rid)
        pf = sum(ctx(r) for r in new)
        kv = sum(ctx(r) for r in running if r not in new)
        t += cfg.base_ms + cfg.kv_ms * kv + cfg.prefill_ms * pf
        steps += 1
        for rid in list(running):
            gen[rid] += 1
            tokens += 1
            first.setdefault(rid, t)
            if gen[rid] == by[rid].output_len:
                running.remove(rid)
                owned.pop(rid, None)
                fin[rid] = t
    return first, fin, pre, t, steps, tokens, npre, peak


def same_as_oracle_static(sim, reqs, cfg, what):
    out, t, steps = oracle_static(reqs, cfg)
    assert sim.steps == steps and near(sim.end_ms, t, 1e-9), f"{what}: static batching ran {sim.steps} steps ending at {sim.end_ms:.3f} ms; the reference ran {steps} steps ending at {t:.3f} ms"
    for d in sim.done:
        f, e = out[d.rid]
        assert near(d.first_token_ms, f, 1e-9) and near(d.finish_ms, e, 1e-9), \
            f"{what}: request {d.rid} should get its first token at {f:.3f} ms and finish at {e:.3f} ms; you have {d.first_token_ms:.3f} and {d.finish_ms:.3f}"


def same_as_oracle_continuous(sim, reqs, cfg, what):
    first, fin, pre, t, steps, tokens, npre, peak = oracle_continuous(reqs, cfg)
    assert sim.steps == steps and sim.tokens == tokens and near(sim.end_ms, t, 1e-9), \
        f"{what}: {sim.steps} steps, {sim.tokens} tokens, end {sim.end_ms:.3f} ms; the reference has {steps}, {tokens}, {t:.3f}"
    assert sim.preemptions == npre, f"{what}: {sim.preemptions} preemptions, the reference has {npre}"
    assert sim.peak_pages == peak, f"{what}: peak_pages {sim.peak_pages}, the reference has {peak}"
    for d in sim.done:
        assert near(d.first_token_ms, first[d.rid], 1e-9) and near(d.finish_ms, fin[d.rid], 1e-9) and d.preemptions == pre[d.rid], \
            (f"{what}: request {d.rid} should have first token {first[d.rid]:.3f}, finish {fin[d.rid]:.3f}, {pre[d.rid]} preemptions; "
             f"you have {d.first_token_ms:.3f}, {d.finish_ms:.3f}, {d.preemptions}")


def generic_invariants(sim, reqs, cfg, what):
    assert [d.rid for d in sim.done] == sorted(r.rid for r in reqs), f"{what}: every request must appear exactly once in `done`, sorted by rid"
    assert sim.tokens == sum(r.output_len for r in reqs), f"{what}: tokens emitted ({sim.tokens}) must equal the sum of output_len ({sum(r.output_len for r in reqs)})"
    assert sim.peak_pages <= cfg.total_pages, f"{what}: peak_pages {sim.peak_pages} exceeds the cache ({cfg.total_pages})"
    by = {r.rid: r for r in reqs}
    for d in sim.done:
        r = by[d.rid]
        assert d.arrival_ms == r.arrival_ms and d.output_len == r.output_len
        assert d.arrival_ms < d.first_token_ms <= d.finish_ms, f"{what}: request {d.rid} must satisfy arrival < first token <= finish; got {d.arrival_ms}, {d.first_token_ms}, {d.finish_ms}"
        assert d.finish_ms - d.first_token_ms >= (d.output_len - 1) * cfg.base_ms - 1e-9, \
            f"{what}: request {d.rid} cannot decode {d.output_len - 1} more tokens in {d.finish_ms - d.first_token_ms:.1f} ms; each step takes at least base_ms = {cfg.base_ms}"


# =============================================================================
# Milestone 3: static batching
# =============================================================================
def m3():
    # two requests, the second arrives while the first batch runs
    reqs = [R(0, 0, 20, 3), R(1, 5, 10, 2)]
    sim = mod.simulate_static(reqs, C())
    assert_timeline(sim, [(30, 50), (70, 80)], "A (arrives 0, prompt 20, 3 tokens) and B (arrives 5, prompt 10, 2 tokens)")
    assert sim.steps == 5 and sim.tokens == 5 and sim.preemptions == 0 and near(sim.end_ms, 80.0), \
        f"hand trace: steps = 3 for batch [A] (prefill 30 ms, two decodes of 10) and 2 for batch [B]; got steps {sim.steps}, tokens {sim.tokens}, end {sim.end_ms}"
    # B had to wait for A's whole batch: time to first token 65 ms, where continuous batching gives 45 ms (milestone 4)

    # kv_ms is paid on the contexts of the ACTIVE requests only
    reqs = [R(0, 0, 4, 3), R(1, 0, 6, 1), R(2, 0, 2, 2)]
    sim = mod.simulate_static(reqs, C(max_batch=2))
    assert_timeline(sim, [(20, 40), (20, 20), (52, 62)], "max_batch 2: [R0, R1] then [R2]; a finished request keeps its slot but costs nothing")
    assert sim.steps == 5
    sim = mod.simulate_static(reqs[:2], C(max_batch=2, kv_ms=1.0))
    assert_timeline(sim, [(20, 51), (20, 20)], "kv_ms = 1: decode step 1 reads R0's 4 + 1 tokens (15 ms), step 2 reads 4 + 2 (16 ms)")

    # a cache that holds one worst-case reservation (prompt + max_new = 32 tokens = 2 pages of 16)
    reqs = [R(0, 0, 4, 2, 28), R(1, 0, 4, 2, 28)]
    sim = mod.simulate_static(reqs, C(total_pages=2, max_batch=8))
    assert_timeline(sim, [(14, 24), (38, 48)], "two pages: static batching reserves prompt + max_new, so only one request fits per batch, whatever cfg.alloc says")
    sim = mod.simulate_static(reqs, C(total_pages=2, max_batch=8, alloc="reserve"))
    assert_timeline(sim, [(14, 24), (38, 48)], "same with alloc = reserve")
    # idle gap: the clock jumps to the arrival
    sim = mod.simulate_static([R(0, 100.5, 8, 2)], C())
    assert_timeline(sim, [(118.5, 128.5)], "a lone request at t = 100.5: prefill 10 + 8 ms, then one decode of 10 ms")
    try:
        mod.simulate_static([R(0, 0, 40, 2, 100)], C(total_pages=3))
    except ValueError:
        pass
    else:
        raise AssertionError("a request needing 9 pages in a 3-page cache can never run: raise ValueError")

    worst = 0
    for s in seeds(range(1, 7)):
        w = mod.make_workload(60, 6.0, s)
        cfg = mod.DEFAULT._replace(max_batch=16)
        sim = mod.simulate_static(w, cfg)
        generic_invariants(sim, w, cfg, f"seed {s}")
        same_as_oracle_static(sim, w, cfg, f"seed {s}")
        small = cfg._replace(total_pages=250)
        sim2 = mod.simulate_static(w, small)
        generic_invariants(sim2, w, small, f"seed {s}, small cache")
        same_as_oracle_static(sim2, w, small, f"seed {s}, small cache")
        worst = max(worst, mod.summarise(sim)["ttft_p95"])
    w = mod.make_workload(300, 4.0, 1)
    s = mod.summarise(mod.simulate_static(w, mod.DEFAULT))
    return (f"hand-traced scenarios and a match with an independent reference on 12 workloads;\n"
            f"300 requests at 4/s, batch up to 64: {s['throughput_tok_s']:.0f} tokens/s, {s['tokens_per_step']:.1f} tokens per step, "
            f"TTFT p95 {s['ttft_p95'] / 1000:.1f} s")


# =============================================================================
# Milestone 4: continuous batching
# =============================================================================
def m4():
    reqs = [R(0, 0, 20, 3), R(1, 5, 10, 2)]
    sim = mod.simulate_continuous(reqs, C())
    assert_timeline(sim, [(30, 60), (50, 60)], "A (arrives 0, prompt 20, 3 tokens) and B (arrives 5, prompt 10, 2 tokens)")
    assert sim.steps == 3 and sim.tokens == 5 and sim.preemptions == 0 and near(sim.end_ms, 60.0), \
        f"hand trace: step 1 prefills A (10 + 20 = 30 ms), step 2 prefills B while A decodes (10 + 10 = 20 ms), step 3 decodes both (10 ms); got steps {sim.steps}, end {sim.end_ms}"
    sim = mod.simulate_continuous(reqs, C(kv_ms=1.0))
    assert_timeline(sim, [(30, 114), (71, 114)], "kv_ms = 1: step 2 reads A's 21 cached tokens (10 + 21 + 10 = 41 ms), step 3 reads 22 + 11 (10 + 33 = 43 ms)")

    # B waits for no one: with max_batch = 1 it must queue behind A
    sim = mod.simulate_continuous(reqs, C(max_batch=1))
    assert_timeline(sim, [(30, 50), (70, 80)], "max_batch = 1: B is admitted only after A finishes")
    # a slot is refilled in the very step after a request finishes
    reqs3 = [R(0, 0, 4, 1), R(1, 0, 4, 3), R(2, 0, 4, 2)]
    sim = mod.simulate_continuous(reqs3, C(max_batch=2))
    assert_timeline(sim, [(18, 18), (18, 42), (32, 42)], "max_batch = 2: R2 takes the slot R0 frees (output_len 1 finishes in its prefill step), and its prefill makes step 2 last 10 + 4 ms")
    # reserve mode: the worst case is claimed up front and blocks the queue in order
    reqs4 = [R(0, 0, 10, 2, 54), R(1, 0, 4, 2, 4), R(2, 0, 4, 2, 4)]
    sim = mod.simulate_continuous(reqs4, C(total_pages=4, alloc="reserve", max_batch=8))
    assert_timeline(sim, [(20, 30), (48, 58), (48, 58)],
                    "reserve: R0 reserves 64 tokens = 4 pages, so R1 and R2 wait until R0 is done, then run together")
    paged = mod.simulate_continuous(reqs4, C(total_pages=4, alloc="paged", max_batch=8))
    assert paged.done[2].first_token_ms < sim.done[2].first_token_ms, "with paged allocation the same cache admits all three at once, so R2 starts sooner"
    try:
        mod.simulate_continuous([R(0, 0, 40, 2, 100)], C(total_pages=2, alloc="reserve"))
    except ValueError:
        pass
    else:
        raise AssertionError("a request that can never fit must raise ValueError")

    cfgs = {"paged": mod.DEFAULT._replace(alloc="paged"), "reserve": mod.DEFAULT._replace(alloc="reserve")}
    for s in seeds(range(1, 7)):
        w = mod.make_workload(80, 7.0, s)
        for name, cfg in cfgs.items():
            sim = mod.simulate_continuous(w, cfg)
            generic_invariants(sim, w, cfg, f"seed {s}, {name}")
            assert sim.preemptions == 0, f"seed {s}, {name}: with this much cache nothing should be preempted (got {sim.preemptions})"
            same_as_oracle_continuous(sim, w, cfg, f"seed {s}, {name}")
        sim = mod.simulate_continuous(w, cfgs["paged"]._replace(max_batch=3))
        assert sim.tokens / sim.steps <= 3 + 1e-9, f"seed {s}: with max_batch = 3 no step can emit more than 3 tokens"
        generic_invariants(sim, w, cfgs["paged"], f"seed {s}, max_batch 3")
    w = mod.make_workload(300, 4.0, 1)
    st = mod.summarise(mod.simulate_static(w, mod.DEFAULT))
    co = mod.summarise(mod.simulate_continuous(w, mod.DEFAULT))
    assert co["throughput_tok_s"] > 1.2 * st["throughput_tok_s"] and co["ttft_p95"] < st["ttft_p95"] / 5, \
        "continuous batching should clearly beat static batching on both throughput and time to first token"
    return (f"300 requests at 4/s, same GPU and same batch limit (64):\n"
            f"  static      {st['throughput_tok_s']:5.0f} tokens/s, {st['tokens_per_step']:5.1f} tokens/step, TTFT p95 {st['ttft_p95']:7.0f} ms\n"
            f"  continuous  {co['throughput_tok_s']:5.0f} tokens/s, {co['tokens_per_step']:5.1f} tokens/step, TTFT p95 {co['ttft_p95']:7.0f} ms")


# =============================================================================
# Milestone 5: preemption
# =============================================================================
def m5():
    # preempt_one on its own
    try:
        mod.preempt_one([], mod.deque(), None)
    except NotImplementedError:
        raise
    except RuntimeError:
        pass
    else:
        raise AssertionError("preempt_one with nothing running must raise RuntimeError")
    alloc = mod.PageAllocator(10, 4)
    lives = [mod.Live(R(i, 0, 4, 4)) for i in range(3)]
    for lv in lives:
        assert alloc.reserve(lv.req.rid, 8)
    running, waiting = list(lives), mod.deque([mod.Live(R(9, 0, 4, 4))])
    lives[2].generated = 3
    victim = mod.preempt_one(running, waiting, alloc)
    assert victim is lives[2] and running == lives[:2], "the victim is the LAST (youngest) running request"
    assert waiting[0] is victim and len(waiting) == 2, "it goes to the FRONT of the waiting queue"
    assert alloc.block_table(2) == [] and alloc.free_pages == 6, "its pages are released"
    assert victim.preemptions == 1 and victim.generated == 3, "it counts the preemption and keeps the tokens it has generated"
    try:
        mod.preempt_one([], waiting, alloc)
    except NotImplementedError:
        raise
    except RuntimeError:
        pass
    else:
        raise AssertionError("preempt_one with nothing running must raise RuntimeError")

    # hand-traced: a 4-page cache of 4-token pages and two requests of 6 + 6 tokens
    reqs = [R(0, 0, 6, 6), R(1, 0, 6, 6)]
    cfg = C(total_pages=4, page_tokens=4, max_batch=4)
    sim = mod.simulate_continuous(reqs, cfg)
    assert_timeline(sim, [(22, 72), (22, 120)], (
        "hand trace: both admitted at step 1 (7 tokens = 2 pages each, 4 pages in all); at step 3 A needs a third page, "
        "the cache is full, so B (the youngest) is preempted; B waits until A finishes at 72, is prefilled again with its "
        "8-token context (10 + 8 = 18 ms) and finishes at 120"))
    assert sim.preemptions == 1 and sim.done[1].preemptions == 1 and sim.done[0].preemptions == 0 and sim.steps == 10 and sim.tokens == 12, \
        f"expected 1 preemption of B, 10 steps and 12 tokens; got {sim.preemptions} preemptions, {sim.steps} steps, {sim.tokens} tokens"
    assert sim.peak_pages == 4
    # one request that exactly fills the cache must run alone without being preempted forever
    solo = mod.simulate_continuous([R(0, 0, 8, 8)], C(total_pages=4, page_tokens=4))
    assert solo.preemptions == 0 and solo.tokens == 8, "a lone request that needs the whole cache is fine"
    # reserve mode never preempts
    sim = mod.simulate_continuous([R(0, 0, 6, 6, 6), R(1, 0, 6, 6, 6)], cfg._replace(alloc="reserve"))
    assert sim.preemptions == 0 and sim.tokens == 12, "reserve mode never preempts: the second request simply waits for the first"

    total_pre = 0
    for s in seeds(range(1, 7)):
        w = mod.make_workload(40, 30.0, s)
        cfg = mod.DEFAULT._replace(total_pages=140, max_batch=32, alloc="paged")
        sim = mod.simulate_continuous(w, cfg)
        generic_invariants(sim, w, cfg, f"seed {s}")
        assert sim.preemptions > 0, f"seed {s}: a 140-page cache (2,240 tokens) is too small for 32 running requests; preemption should happen"
        assert sim.preemptions == sum(d.preemptions for d in sim.done), f"seed {s}: the per-request counts must add up to sim.preemptions"
        same_as_oracle_continuous(sim, w, cfg, f"seed {s}")
        total_pre += sim.preemptions
        roomy = mod.simulate_continuous(w, cfg._replace(total_pages=3070))
        assert sim.end_ms >= roomy.end_ms - 1e-9, f"seed {s}: recomputing preempted requests cannot make the run finish earlier than with an ample cache"
    w = mod.make_workload(40, 30.0, 1)
    small = mod.summarise(mod.simulate_continuous(w, mod.DEFAULT._replace(total_pages=140, max_batch=32)))
    big = mod.summarise(mod.simulate_continuous(w, mod.DEFAULT._replace(max_batch=32)))
    return (f"hand-traced preemption and recompute, and a match with an independent reference under pressure;\n"
            f"40 requests at 30/s, seed 1: 3,070 pages -> {big['preemptions']} preemptions, {big['throughput_tok_s']:.0f} tokens/s, TTFT p95 {big['ttft_p95']:.0f} ms;\n"
            f"140 pages -> {small['preemptions']} preemptions, {small['throughput_tok_s']:.0f} tokens/s, TTFT p95 {small['ttft_p95']:.0f} ms")


# =============================================================================
# Milestone 6: capacity under an SLO, and what a token costs
# =============================================================================
def m6():
    assert near(mod.cost_per_million(1000, 3.6), 1.0) and near(mod.cost_per_million(800, 3.0), 3.0 / (800 * 3600) * 1e6), \
        "cost = price_per_hour / (tokens_per_s * 3600) * 1e6; 1,000 tokens/s on a $3.60 GPU is $1.00 per million"
    rows = [{"rate": r, "ttft_p95": a, "tpot_p95": b} for r, a, b in [(1, 100, 20), (2, 200, 25), (4, 900, 30), (6, 500, 90), (8, 4000, 30)]]
    assert mod.max_rate_under_slo(rows, 1000, 100) == 6, "all of the first four rows pass (ttft <= 1000, tpot <= 100): the answer is the last rate before the first failure, 6"
    assert mod.max_rate_under_slo(rows, 1000, 50) == 4, "row 4 fails the 50 ms tpot SLO, so the answer is 4 (row 5 is never reached)"
    assert mod.max_rate_under_slo(rows, 50, 100) == 0.0, "the first row already violates: 0.0"
    assert mod.max_rate_under_slo(rows[:2], 1000, 100) == 2, "if nothing violates, the last rate"
    rows2 = [dict(r) for r in rows]
    rows2[3]["ttft_p95"] = 5000
    assert mod.max_rate_under_slo(rows2, 1000, 100) == 4, "a violation stops the scan even if a later row passes"

    assert sorted(mod.POLICIES) == ["continuous, paged", "continuous, reserve", "static"]
    rates = [1, 2, 4]
    w1 = mod.run_sweep("continuous, paged", rates, 60, 3, mod.DEFAULT)
    assert [r["rate"] for r in w1] == rates and all("ttft_p95" in r and "throughput_tok_s" in r for r in w1), "one row per rate, each with 'rate' and the summarise keys"
    for r in w1:
        direct = mod.summarise(mod.simulate_continuous(mod.make_workload(60, r["rate"], 3), mod.DEFAULT))
        assert all(near(direct[k], r[k]) for k in direct), f"rate {r['rate']}: the row must equal summarise(simulate(make_workload(n, rate, seed))) for the policy"
    ws = mod.run_sweep("static", [2], 60, 3, mod.DEFAULT)[0]
    assert near(ws["throughput_tok_s"], mod.summarise(mod.simulate_static(mod.make_workload(60, 2, 3), mod.DEFAULT))["throughput_tok_s"]), "'static' runs simulate_static"
    rr = mod.run_sweep("continuous, reserve", [2], 60, 3, mod.DEFAULT)[0]
    assert near(rr["peak_pages"], mod.simulate_continuous(mod.make_workload(60, 2, 3), mod.DEFAULT._replace(alloc="reserve")).peak_pages), "'continuous, reserve' forces alloc = reserve"

    RATES = [1, 2, 3, 4, 5, 6, 8, 10, 12]
    SLO = (1000.0, 80.0)
    table, cap = {}, {}
    for name in mod.POLICIES:
        rows = mod.run_sweep(name, RATES, 300, 1, mod.DEFAULT)
        table[name] = rows
        cap[name] = mod.max_rate_under_slo(rows, *SLO)
    assert cap["static"] < cap["continuous, reserve"] < cap["continuous, paged"], \
        f"under TTFT p95 <= {SLO[0]:.0f} ms and TPOT p95 <= {SLO[1]:.0f} ms the capacities should be ordered static < continuous with reserved cache < continuous with paged cache; got {cap}"
    peaks = {n: max(r["peak_pages"] for r in table[n] if r["rate"] <= 6) for n in table}
    assert peaks["continuous, paged"] < peaks["continuous, reserve"] / 2, "up to 6 requests a second paging holds less than half the cache that reserving worst cases does"
    price = 1.0
    lines = []
    for name in mod.POLICIES:
        best = [r for r in table[name] if r["rate"] == cap[name]]
        if best:
            tok_s = best[0]["throughput_tok_s"]
            lines.append(f"  {name:<20} sustains {cap[name]:>4.0f} req/s ({tok_s:5.0f} tokens/s), ${mod.cost_per_million(tok_s, price):5.2f} per million tokens")
        else:
            lines.append(f"  {name:<20} sustains {0:>4.0f} req/s (misses the SLO even at 1 req/s)")
    return (f"SLO: TTFT p95 <= {SLO[0]:.0f} ms and TPOT p95 <= {SLO[1]:.0f} ms, 300 requests per rate, GPU at an assumed ${price:.2f} an hour:\n" + "\n".join(lines))


MILESTONES = [
    (1, "Milestone 1: sizing and paging", m1),
    (2, "Milestone 2: the cost model, the workload and the metrics", m2),
    (3, "Milestone 3: static batching", m3),
    (4, "Milestone 4: continuous batching", m4),
    (5, "Milestone 5: preemption when the cache is full", m5),
    (6, "Milestone 6: capacity under an SLO, and what a token costs", m6),
]

if __name__ == "__main__":
    t0 = time.time()
    print(f"Lab 6 checks against {target}.py\n")
    for n, name, fn in MILESTONES:
        check(n, name, fn)
    print(f"\n{sum(results)}/{len(results)} milestones passing  ({time.time() - t0:.1f} s)")
    sys.exit(0 if all(results) else 1)
