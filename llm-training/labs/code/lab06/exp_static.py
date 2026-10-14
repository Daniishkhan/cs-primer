"""Milestone 3 experiment: static batching, batch size against throughput and waiting time."""
from solution import DEFAULT, make_workload, simulate_static, summarise

w = make_workload(300, 3.0, 1)
print("static batching, 300 requests at 3 per second")
print(f"{'max batch':>9} {'tok/s':>7} {'tok/step':>9} {'ttft p50':>9} {'ttft p95':>9} {'peak pages':>11}")
for b in (1, 4, 8, 16, 32, 64):
    s = summarise(simulate_static(w, DEFAULT._replace(max_batch=b)))
    print(f"{b:9d} {s['throughput_tok_s']:7.0f} {s['tokens_per_step']:9.1f} {s['ttft_p50']:9.0f} {s['ttft_p95']:9.0f} {s['peak_pages']:11d}")
