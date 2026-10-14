"""Milestone 6 experiment: capacity under an SLO, and how it depends on the client's max_tokens."""
from solution import DEFAULT, POLICIES, cost_per_million, make_workload, max_rate_under_slo, run_sweep, simulate_continuous, summarise

RATES = [1, 2, 3, 4, 5, 6, 8, 10, 12, 14]
SLO = (1000.0, 80.0)
print(f"SLO: TTFT p95 <= {SLO[0]:.0f} ms, TPOT p95 <= {SLO[1]:.0f} ms; 300 requests per rate; assumed price $1.00 per GPU-hour")
print(f"{'policy':<22} {'max req/s':>9} {'tok/s there':>12} {'$ per M tokens':>15}")
for name in POLICIES:
    rows = run_sweep(name, RATES, 300, 1, DEFAULT)
    cap = max_rate_under_slo(rows, *SLO)
    at = [r for r in rows if r["rate"] == cap]
    if at:
        print(f"{name:<22} {cap:9.0f} {at[0]['throughput_tok_s']:12.0f} {cost_per_million(at[0]['throughput_tok_s'], 1.0):15.2f}")
    else:
        print(f"{name:<22} {cap:9.0f} {'-':>12} {'-':>15}")

print("\nthe client's max_tokens limit decides what 'reserve' can admit; paging does not care")
print(f"{'max_new':>8} {'reserve: max req/s':>19} {'paged: max req/s':>17}")
for max_new in (256, 512, 1024, 2048):
    caps = []
    for alloc in ("reserve", "paged"):
        rows = []
        for rate in RATES:
            sim = simulate_continuous(make_workload(300, rate, 1, max_new=max_new), DEFAULT._replace(alloc=alloc))
            row = summarise(sim)
            row["rate"] = rate
            rows.append(row)
        caps.append(max_rate_under_slo(rows, *SLO))
    print(f"{max_new:8d} {caps[0]:19.0f} {caps[1]:17.0f}")
