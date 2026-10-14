"""Milestone 5 experiment: shrink the cache and watch preemption and recomputation."""
from solution import DEFAULT, make_workload, simulate_continuous, summarise

w = make_workload(150, 12.0, 2)
print("continuous batching, 150 requests at 12/s, max batch 64, paged")
print(f"{'pages':>6} {'tokens':>8} {'preempts':>9} {'steps':>6} {'tok/s':>7} {'ttft p95':>9} {'tpot p95':>9} {'e2e p95':>9}")
for pages in (3070, 1500, 800, 500, 300, 200):
    sim = simulate_continuous(w, DEFAULT._replace(total_pages=pages))
    s = summarise(sim)
    print(f"{pages:6d} {pages * 16:8d} {s['preemptions']:9d} {sim.steps:6d} {s['throughput_tok_s']:7.0f} {s['ttft_p95']:9.0f} {s['tpot_p95']:9.1f} {s['e2e_p95']:9.0f}")
