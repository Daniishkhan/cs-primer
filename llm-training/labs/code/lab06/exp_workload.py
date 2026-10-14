"""Milestone 2 experiment: what the seeded workload looks like."""
from solution import make_workload, percentile

w = make_workload(5000, 8.0, 1)
print("5,000 requests at 8 per second, seed 1")
for name, vals in (("prompt tokens", [r.prompt_len for r in w]), ("output tokens", [r.output_len for r in w])):
    print(f"{name:<14} mean {sum(vals) / len(vals):6.1f}   p50 {percentile(vals, 50):5d}   p95 {percentile(vals, 95):5d}   p99 {percentile(vals, 99):5d}   max {max(vals):5d}")
gaps = [b.arrival_ms - a.arrival_ms for a, b in zip(w, w[1:])]
print(f"gap between arrivals: mean {sum(gaps) / len(gaps):.1f} ms (1000 / 8 = 125), p95 {percentile(gaps, 95):.0f} ms, longest {max(gaps):.0f} ms")
print(f"the client allows max_new = {w[0].max_new}; the largest output actually generated is {max(r.output_len for r in w)}")
mean_ctx = sum(r.prompt_len + r.output_len / 2 for r in w) / len(w)
print(f"average context while decoding is about {mean_ctx:.0f} tokens, but a reserve-everything allocator holds {sum(r.prompt_len + r.max_new for r in w) / len(w):.0f} tokens per request")
