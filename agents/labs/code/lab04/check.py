"""Self-check for Lab 4: Workflow Patterns & Budgets.

    python3 check.py                  # checks your starter.py
    python3 check.py solution         # checks the reference solution
    python3 check.py solution 4       # only milestone 4
    python3 check.py solution 5 3     # milestone 5, replaying ONLY the random case of seed 3

The "model" is the deterministic stand-in in fixtures.py, so every token count, price and
simulated time is exact and identical on every run. No network and no real clock; a few seconds.
Prints a tick, a cross, or "not implemented yet" for each milestone.
"""
import importlib
import json
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
from fixtures import JUDGE_ITEMS, ORDERS, POLICY_DAYS, TICKETS, make_model  # noqa: E402
from llm import ScriptedModel, count_tokens  # noqa: E402

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


T = {t["id"]: t for t in TICKETS}


def sent(model, i=-1):
    """(system, user) of the i-th request the stand-in model received."""
    c = model.calls[i]
    assert len(c["messages"]) == 1 and c["messages"][0]["role"] == "user", f"each step sends exactly ONE user message; got {c['messages']}"
    return c["system"], c["messages"][0]["content"]


# =============================================================================
# Milestone 1: the meter
# =============================================================================
def m1():
    assert near(mod.call_cost("small", 1000, 200), 0.0005), f"call_cost('small', 1000, 200) should be (1000 x 0.25 + 200 x 1.25) / 1e6 = 0.0005; got {mod.call_cost('small', 1000, 200)}"
    assert near(mod.call_cost("large", 1_000_000, 1_000_000), 18.0), "one million tokens each way on the large tier is 3 + 15 = 18 dollars"
    assert mod.call_cost("small", 0, 0) == 0
    assert near(mod.call_seconds("large", 1000, 100), 0.8 + 1000 * 0.0005 + 100 * 0.03), f"call_seconds('large', 1000, 100) should be 4.3; got {mod.call_seconds('large', 1000, 100)}"
    assert near(mod.call_seconds("small", 0, 0), 0.3), "a call with no tokens still costs the fixed overhead"
    # a metered call
    model = ScriptedModel(["hello there world", "second reply is a little longer"])
    m = mod.Meter(model)
    out = m.ask("greet", "SYS prompt", "user message here")
    assert out == "hello there world", f"ask returns the reply text; got {out!r}"
    tin, tout = count_tokens("SYS prompt") + count_tokens("user message here"), count_tokens("hello there world")
    c = m.calls[0]
    assert (c.step, c.tier, c.tokens_in, c.tokens_out) == ("greet", "small", tin, tout), f"the Call must record step, tier and the usage of the response ({tin} in, {tout} out); got {c}"
    assert near(c.seconds, mod.call_seconds("small", tin, tout)) and near(c.cost_usd, mod.call_cost("small", tin, tout)), "a Call's seconds and cost come from call_seconds and call_cost"
    assert near(m.clock, c.seconds), "the clock advances by the call's seconds"
    m.ask("greet", "SYS", "again", tier="large")
    assert m.calls[1].tier == "large" and near(m.clock, m.calls[0].seconds + m.calls[1].seconds), "sequential calls add up on the clock"
    assert model.calls[0]["system"] == "SYS prompt" and model.calls[0]["messages"] == [{"role": "user", "content": "user message here"}], "ask sends the system prompt and ONE user message"
    # fan_out: parallel in simulated time
    model = ScriptedModel(lambda msgs, tools, system: "x" * (4 * int(msgs[-1]["content"])))
    m = mod.Meter(model)
    m.ask("first", "S", "1")
    t0 = m.clock
    res = m.fan_out([lambda n=n: m.ask("branch", "S", str(n)) for n in (5, 50, 10)])
    secs = [c.seconds for c in m.calls[1:]]
    assert res == ["x" * 20, "x" * 200, "x" * 40], f"fan_out returns each thunk's result, in order; got {[len(r) if isinstance(r, str) else r for r in res]}"
    assert near(m.clock, t0 + max(secs)), f"after a fan_out the clock should stand at start + the SLOWEST branch ({t0 + max(secs):.4f}); got {m.clock:.4f}"
    tot = m.totals()
    assert near(tot["work_seconds"], sum(c.seconds for c in m.calls)) and tot["work_seconds"] > tot["seconds"] + 1e-9, "work_seconds is the sum of all calls; seconds is the critical path and must be smaller after a fan_out"
    before = m.clock
    assert m.fan_out([]) == [] and m.clock == before, "an empty fan_out changes nothing"
    m2 = mod.Meter(model)
    m2.fan_out([lambda: m2.fan_out([lambda: m2.ask("a", "S", "1"), lambda: m2.ask("b", "S", "2")]), lambda: m2.ask("c", "S", "3")])
    assert near(m2.clock, max(c.seconds for c in m2.calls)), "nested fan-outs: the clock is the longest single path"
    # totals and by_step
    m = mod.Meter(ScriptedModel(lambda msgs, tools, system: "ok"))
    for step, tier in (("a", "small"), ("b", "large"), ("a", "small")):
        m.ask(step, "SYSTEM", "hello", tier=tier)
    tot, by = m.totals(), m.by_step()
    assert set(tot) >= {"calls", "tokens_in", "tokens_out", "cost_usd", "seconds", "work_seconds"}, f"totals() keys; got {sorted(tot)}"
    assert tot["calls"] == 3 and tot["tokens_in"] == 3 * (count_tokens("SYSTEM") + count_tokens("hello")) and tot["tokens_out"] == 3 * count_tokens("ok"), f"totals wrong: {tot}"
    assert near(tot["cost_usd"], 2 * mod.call_cost("small", 4, 1) + mod.call_cost("large", 4, 1)), "cost sums the per-call costs at each call's own tier"
    assert list(by) == ["a", "b"] and by["a"]["calls"] == 2 and by["b"]["calls"] == 1, f"by_step groups by step name in first-seen order; got {by}"
    assert sum(r["tokens_in"] for r in by.values()) == tot["tokens_in"] and near(sum(r["cost_usd"] for r in by.values()), tot["cost_usd"]), "by_step must add up to totals"
    # property: totals always equal the sum over calls, whatever the sequence
    for seed in seeds(range(1, 31)):
        rnd = random.Random(seed)
        m = mod.Meter(ScriptedModel(lambda msgs, tools, system: "y" * rnd.randint(0, 80)))
        for _ in range(rnd.randint(1, 12)):
            tier = rnd.choice(["small", "large"])
            if rnd.random() < 0.4:
                m.fan_out([lambda tier=tier: m.ask("w", "S", "z" * rnd.randint(1, 60), tier=tier) for _ in range(rnd.randint(0, 4))])
            else:
                m.ask("s", "S", "z" * rnd.randint(1, 60), tier=tier)
        tot = m.totals()
        assert tot["calls"] == len(m.calls) and tot["tokens_in"] == sum(c.tokens_in for c in m.calls), f"seed {seed}: totals disagree with the call list"
        assert near(tot["cost_usd"], sum(mod.call_cost(c.tier, c.tokens_in, c.tokens_out) for c in m.calls)), f"seed {seed}: cost disagrees with the call list"
        assert tot["seconds"] <= tot["work_seconds"] + 1e-9 and m.clock >= max((c.seconds for c in m.calls), default=0) - 1e-9, f"seed {seed}: the clock must lie between the longest call and the sum of all calls"
    return "prices, simulated time, fan-out as the slowest branch, totals and by_step (30 random call mixes)"


# =============================================================================
# Milestone 2: a chain with gates
# =============================================================================
def m2():
    model = make_model()
    m = mod.Meter(model)
    o = mod.chain(m, T["T01"]["text"])
    assert (o.status, o.reason) == ("ok", "ok") and "A-1001" in o.reply, f"T01 names a real order and should pass both gates; got {o}"
    assert o.reply == "Sorry about the wait with order A-1001. It is shipped and should arrive on Friday. Reply here if it does not.", f"reply text wrong: {o.reply!r}"
    assert [c.step for c in m.calls] == ["extract", "draft"], f"a successful chain is two model calls, named 'extract' then 'draft'; got {[c.step for c in m.calls]}"
    s0, u0 = sent(model, 0)
    s1, u1 = sent(model, 1)
    assert s0 == mod.SYSTEM_EXTRACT and u0 == T["T01"]["text"], "step 1 sends the ticket text itself with SYSTEM_EXTRACT"
    facts = json.dumps(dict(ORDERS["A-1001"], order_id="A-1001"), sort_keys=True)
    assert s1 == mod.SYSTEM_DRAFT and u1 == "FACTS:" + facts, f"step 2 must send 'FACTS:' + json.dumps(facts, sort_keys=True), with the lookup done in plain code; got {u1!r}"
    e_in = count_tokens(mod.SYSTEM_EXTRACT) + count_tokens(T["T01"]["text"])
    assert m.calls[0].tokens_in == e_in, f"token accounting for the extract call: expected {e_in} in, got {m.calls[0].tokens_in}"
    # gate 1 stops the chain before the second model call is paid for
    model = make_model()
    m = mod.Meter(model)
    o = mod.chain(m, T["T04"]["text"])
    assert (o.status, o.reply, o.reason) == ("gate1", None, "no valid order id"), f"T04 names no order: gate 1 must stop the chain; got {o}"
    assert len(m.calls) == 1 and len(model.calls) == 1, f"after gate 1 NO further model call may be made (that is the saving); the chain made {len(model.calls)} calls"
    o = mod.chain(mod.Meter(make_model()), "Where is order A-9999? It is late.")
    assert o.status == "gate1", "an id that looks right but is not in ORDERS fails gate 1 (check against the data, not the pattern)"
    # unparseable extract
    o = mod.chain(mod.Meter(ScriptedModel(["sorry, I cannot help with that"])), "anything")
    assert (o.status, o.reason) == ("gate1", "extract was not valid JSON"), f"a non-JSON extract reply is a gate 1 failure; got {o}"
    o = mod.chain(mod.Meter(ScriptedModel(['{"issue": "late"}'])), "anything")
    assert o.status == "gate1" and o.reason == "no valid order id", "JSON without an order_id is a gate 1 failure too"
    # gate 2
    def draft_bad(msgs, tools, system):
        if system.startswith("EXTRACT"):
            return '{"order_id": "A-1002", "issue": "late"}'
        return DRAFTS.pop(0)
    for what, text in (("does not name the order", "Your parcel is on its way."), ("too long", "Order A-1002 " + "word " * 40)):
        DRAFTS = [text]
        o = mod.chain(mod.Meter(ScriptedModel(draft_bad)), "x")
        assert (o.status, o.reply, o.reason) == ("gate2", None, "draft rejected"), f"a draft that {what} must fail gate 2; got {o}"
    DRAFTS = ["Order A-1002 " + "word " * 38]            # exactly 40 words
    assert len(DRAFTS[0].split()) == 40 and mod.chain(mod.Meter(ScriptedModel(draft_bad)), "x").status == "ok", "40 words is allowed; 'at most 40'"
    # every ticket: the gates give a cheaper failure than a finished chain
    ok = bad = 0
    for t in TICKETS:
        m = mod.Meter(make_model())
        o = mod.chain(m, t["text"])
        assert len(m.calls) == (2 if o.status != "gate1" else 1), f"{t['id']}: chain made {len(m.calls)} calls with status {o.status}"
        ok += o.status == "ok"
        bad += o.status != "ok"
    assert (ok, bad) == (11, 13), f"over the 24 tickets I expected 11 to pass and 13 to stop at gate 1 (tickets with no real order id); got {ok} and {bad}"
    # compounding errors
    r = mod.chain_outcomes(0.9, 5, 0.8)
    assert near(r["correct"], 0.59049) and near(r["detected"], 1 - 0.92 ** 5) and near(r["silent"], 0.92 ** 5 - 0.9 ** 5), f"chain_outcomes(0.9, 5, 0.8) should be correct 0.5905, detected 0.3409, silent 0.0686; got {r}"
    r0 = mod.chain_outcomes(0.9, 5, 0.0)
    assert near(r0["detected"], 0) and near(r0["silent"], 1 - 0.9 ** 5), "with no gates every failure is silent"
    r1 = mod.chain_outcomes(0.9, 5, 1.0)
    assert near(r1["silent"], 0) and near(r1["detected"], 1 - 0.9 ** 5), "perfect gates turn every failure into a detected one"
    for seed in seeds(range(1, 41)):
        rnd = random.Random(seed)
        p, n, c = rnd.uniform(0.5, 1), rnd.randint(1, 10), rnd.random()
        r = mod.chain_outcomes(p, n, c)
        assert near(sum(r.values()), 1.0) and min(r.values()) >= -1e-12, f"seed {seed}: the three outcomes must be probabilities summing to 1; got {r} for p={p:.3f}, n={n}, catch={c:.3f}"
        assert near(r["correct"], p ** n), f"seed {seed}: 'correct' is p^n regardless of the gates"
        assert mod.chain_outcomes(p, n, min(1, c + 0.1))["silent"] <= r["silent"] + 1e-12, f"seed {seed}: better gates must never raise the silent failure rate"
    return "gates stop early (1 call, not 2), each step sends exactly the specified message, 40-word limit, and the failure arithmetic"


# =============================================================================
# Milestone 3: a router with a threshold
# =============================================================================
def m3():
    model = make_model()
    m = mod.Meter(model)
    assert mod.classify(m, T["T01"]["text"]) == ("tracking", 0.88), "classify returns (label, confidence as a float)"
    assert sent(model, 0) == (mod.SYSTEM_CLASSIFY, T["T01"]["text"]) and m.calls[0].step == "classify" and m.calls[0].tier == "small", "one small 'classify' call with the ticket text"
    assert mod.classify(mod.Meter(ScriptedModel(["gibberish"])), "x") == ("other", 0.0), "a malformed classifier reply is ('other', 0.0)"
    assert mod.classify(mod.Meter(ScriptedModel(["refund|high"])), "x") == ("other", 0.0), "a confidence that is not a number is malformed too"
    # route
    model = make_model()
    m = mod.Meter(model)
    r = mod.route(m, T["T09"]["text"])
    assert (r.label, r.confidence, r.destination) == ("refund", 0.93, "refund") and r.reply.startswith("[refund]"), f"T09 goes to the refund handler; got {r}"
    assert [(c.step, c.tier) for c in m.calls] == [("classify", "small"), ("handle", "large")], f"refunds are handled on the LARGE tier; got {[(c.step, c.tier) for c in m.calls]}"
    assert sent(model, 1)[0] == mod.HANDLER_SYSTEMS["refund"] and sent(model, 1)[1] == T["T09"]["text"], "the handler gets its own system prompt and the ticket text"
    m = mod.Meter(make_model())
    mod.route(m, T["T15"]["text"])
    assert m.calls[1].tier == "small", "account tickets are handled on the small tier"
    m = mod.Meter(make_model())
    r = mod.route(m, T["T20"]["text"])
    assert (r.destination, r.reply) == ("human", None) and len(m.calls) == 1, f"'other' goes to a human after ONE call; got {r} with {len(m.calls)} calls"
    m = mod.Meter(make_model())
    r = mod.route(m, T["T06"]["text"], threshold=0.7)
    assert r.label == "tracking" and r.destination == "human" and len(m.calls) == 1, "a known label below the threshold (0.66 < 0.7) still goes to a human"
    m = mod.Meter(make_model())
    assert mod.route(m, T["T06"]["text"], threshold=0.66).destination == "tracking", "confidence exactly at the threshold passes (below means <)"
    m = mod.Meter(make_model())
    mod.route(m, T["T09"]["text"], tier_override="small")
    assert m.calls[1].tier == "small", "tier_override replaces the route's tier"
    # evaluation
    row = mod.evaluate_router(TICKETS, 0.7)
    assert (row["n"], row["auto"], row["misrouted"]) == (24, 17, 2), f"at 0.7, 17 of 24 tickets are handled automatically and 2 are misrouted (T23, T24: they hold two requests each); got auto {row['auto']}, misrouted {row['misrouted']}"
    assert near(row["auto_rate"], 17 / 24) and near(row["misroute_rate"], 2 / 24), "auto_rate and misroute_rate are fractions of ALL tickets"
    assert row["calls"] == 24 + 17 and row["tokens"] > 0 and row["cost_usd"] > 0, f"one classify per ticket plus one handle per automatic one: expected 41 calls; got {row['calls']}"
    sweep = [mod.evaluate_router(TICKETS, th) for th in (0.5, 0.6, 0.7, 0.8, 0.9)]
    assert [r["misrouted"] for r in sweep] == [4, 3, 2, 2, 1], f"misrouted tickets along thresholds 0.5 to 0.9 should be 4, 3, 2, 2, 1; got {[r['misrouted'] for r in sweep]}"
    for a, b in zip(sweep, sweep[1:]):
        assert a["auto_rate"] >= b["auto_rate"] and a["cost_usd"] >= b["cost_usd"] - 1e-12 and a["misroute_rate"] >= b["misroute_rate"], "a higher threshold hands more to humans: fewer automatic, fewer misrouted, cheaper"
    cheap, dear = mod.evaluate_router(TICKETS, 0.7), mod.evaluate_router(TICKETS, 0.7, tier_override="large")
    assert dear["cost_usd"] > 2.5 * cheap["cost_usd"], f"sending everything to the large tier should cost much more than routing by tier ({dear['cost_usd']:.5f} vs {cheap['cost_usd']:.5f})"
    assert dear["tokens"] == cheap["tokens"], "same calls, same tokens: only the price per token changes"
    assert mod.pick_threshold(sweep, 0.10) == 0.7 and mod.pick_threshold(sweep, 0.05) == 0.9 and mod.pick_threshold(sweep, 0.2) == 0.5, "pick_threshold: most automatic traffic within the misroute cap"
    tie = [{"threshold": 0.6, "auto_rate": 0.5, "misroute_rate": 0.0}, {"threshold": 0.8, "auto_rate": 0.5, "misroute_rate": 0.0}]
    assert mod.pick_threshold(tie, 0.1) == 0.8, "a tie goes to the higher threshold"
    try:
        mod.pick_threshold(sweep, 0.0)
        raise AssertionError("pick_threshold must raise ValueError when no threshold qualifies (every threshold misroutes at least T23)")
    except ValueError:
        pass
    note = [f"threshold  auto-handled  misrouted   cost"]
    for r in sweep:
        note.append(f"{r['threshold']:>9.1f}  {r['auto']:>7d}/24   {r['misrouted']:>8d}   ${r['cost_usd']:.5f}")
    note.append(f"all on the large tier at 0.7: ${dear['cost_usd']:.5f}  ({dear['cost_usd'] / cheap['cost_usd']:.1f}x the routed cost, same tokens)")
    return "\n".join(note)


# =============================================================================
# Milestone 4: parallel fan-out
# =============================================================================
def m4():
    text = "I want my password reset now or I will dispute the charge."
    ms, mp = mod.Meter(make_model()), mod.Meter(make_model())
    rs = mod.section(ms, text, parallel=False)
    rp = mod.section(mp, text, parallel=True)
    assert list(rp) == ["pii", "tone", "policy"], f"section returns {{name: reply}} in the order pii, tone, policy; got {list(rp)}"
    assert rp == rs == {"pii": "flag: needs a look", "tone": "flag: needs a look", "policy": "flag: needs a look"}, f"replies wrong: {rp}"
    assert [c.step for c in mp.calls] == ["check-pii", "check-tone", "check-policy"], f"step names are 'check-<name>'; got {[c.step for c in mp.calls]}"
    assert ms.totals()["tokens_in"] == mp.totals()["tokens_in"] and ms.totals()["cost_usd"] == mp.totals()["cost_usd"], "parallel and sequential cost exactly the same tokens and dollars"
    secs = [c.seconds for c in mp.calls]
    assert near(ms.clock, sum(secs)) and near(mp.clock, max(secs)), f"sequential should take the SUM of the three calls ({sum(secs):.3f}s) and parallel the SLOWEST ({max(secs):.3f}s); got {ms.clock:.3f}s and {mp.clock:.3f}s"
    assert mod.section(mod.Meter(make_model()), "Where is my parcel?") == {"pii": "ok", "tone": "ok", "policy": "ok"}
    # majority
    assert mod.majority(["yes", "no", "yes"]) == "yes" and mod.majority(["a"]) == "a"
    assert mod.majority(["a", "b"]) == "a" and mod.majority(["b", "a", "a", "b"]) == "b", "a tie goes to the vote seen first"
    try:
        mod.majority([])
        raise AssertionError("majority([]) must raise ValueError")
    except ValueError:
        pass
    # vote
    model = make_model()
    m = mod.Meter(model)
    item = JUDGE_ITEMS[1]
    label, votes = mod.vote(m, item["text"], 5)
    assert len(votes) == 5 and all(v in ("yes", "no") for v in votes) and label == mod.majority(votes), f"vote returns (majority, the 5 votes); got {(label, votes)}"
    assert [sent(model, i)[0] for i in range(5)] == [mod.judge_system(k) for k in range(5)], "judge k is called with judge_system(k), k = 0..n-1, in order"
    assert near(m.clock, max(c.seconds for c in m.calls)) and m.totals()["calls"] == 5, "the five judges run in parallel: one call's worth of waiting, five calls' worth of tokens"
    assert mod.vote(mod.Meter(make_model()), item["text"], 1)[1] == votes[:1], "judge 0 gives the same answer alone as inside a panel"
    # the binomial promise
    for p, n, want in ((0.7, 1, 0.7), (0.7, 3, 0.784), (0.7, 5, 0.83692), (0.7, 9, 0.901191), (0.5, 7, 0.5), (1.0, 3, 1.0), (0.6, 3, 0.648)):
        got = mod.majority_accuracy(p, n)
        assert abs(got - want) < 1e-5, f"majority_accuracy({p}, {n}) should be {want}; got {got:.6f}"
    try:
        mod.majority_accuracy(0.7, 4)
        raise AssertionError("an even number of judges can tie: ValueError")
    except ValueError:
        pass
    for seed in seeds(range(1, 31)):
        rnd = random.Random(seed)
        p = rnd.uniform(0.51, 0.99)
        a = [mod.majority_accuracy(p, n) for n in (1, 3, 5, 7, 9, 11)]
        assert all(x < y + 1e-12 for x, y in zip(a, a[1:])) and near(a[0], p), f"seed {seed}: with p = {p:.3f} (above one half) more independent judges must help; got {a}"
    # the experiment: independent maths versus judges that share blind spots
    rows = {n: mod.evaluate_voting(JUDGE_ITEMS, n) for n in (1, 3, 5, 9)}
    one, nine = rows[1], rows[9]
    assert 0.62 <= one["accuracy"] <= 0.78, f"a single judge should be right about 70% of the time on these items; got {one['accuracy']:.3f}"
    assert nine["accuracy"] > one["accuracy"] + 0.03, f"nine judges should beat one; got {nine['accuracy']:.3f} vs {one['accuracy']:.3f}"
    assert all(r["accuracy"] <= 0.8 + 1e-9 for r in rows.values()), "20% of the items are hard for EVERY judge, so no panel can exceed 80%"
    assert nine["accuracy"] < mod.majority_accuracy(0.7, 9) - 0.05, "the independence formula promises about 90% for nine judges; shared blind spots keep the real number well below it"
    for n in (3, 5, 9):
        assert rows[n]["calls"] == n * 200 and rows[n]["tokens"] == n * one["tokens"], f"n = {n}: tokens must scale exactly n-fold ({rows[n]['tokens']} vs {n} x {one['tokens']})"
        assert near(rows[n]["seconds"], one["seconds"]), f"n = {n}: judges run in parallel, so the waiting time must not grow with n ({rows[n]['seconds']:.2f}s vs {one['seconds']:.2f}s)"
    note = ["judges  accuracy  independent promise  tokens    cost"]
    for n, r in rows.items():
        note.append(f"{n:>6}  {r['accuracy']:>8.3f}  {mod.majority_accuracy(0.7, n):>19.3f}  {r['tokens']:>6,}  ${r['cost_usd']:.4f}")
    return "\n".join(note)


# =============================================================================
# Milestone 5: budgets and the orchestrator
# =============================================================================
def m5():
    Budget, BE = mod.Budget, mod.BudgetExceeded
    m = mod.BudgetedMeter(ScriptedModel(lambda msgs, tools, system: "reply text"), Budget(max_calls=2))
    m.ask("a", "S", "one")
    m.ask("a", "S", "two")
    try:
        m.ask("a", "S", "three")
        raise AssertionError("a third call must raise BudgetExceeded when max_calls is 2")
    except BE as e:
        assert e.reason == "calls" and len(m.calls) == 2, f"the check happens BEFORE the call (so no third call is recorded) and names the limit; got reason {e.reason!r} with {len(m.calls)} calls"
    m = mod.BudgetedMeter(ScriptedModel(lambda msgs, tools, system: "reply text"), Budget(max_tokens=30))
    n = 0
    try:
        while True:
            m.ask("a", "SYSTEM", "a user message of some length")
            n += 1
            assert n < 10, "max_tokens never triggered"
    except BE as e:
        t = m.totals()
        spent = t["tokens_in"] + t["tokens_out"]
        assert e.reason == "tokens" and spent >= 30 and spent - (m.calls[-1].tokens_in + m.calls[-1].tokens_out) < 30, \
            f"the limit stops the NEXT call once it has been reached; the last call may overshoot but the one before it must not have reached it. spent {spent}, reason {e.reason!r}"
    first = count_tokens("SYSTEM") + count_tokens("a user message") + count_tokens("reply text")
    m = mod.BudgetedMeter(ScriptedModel(lambda msgs, tools, system: "reply text"), Budget(max_tokens=first))
    m.ask("a", "SYSTEM", "a user message")
    try:
        m.ask("a", "SYSTEM", "a user message")
        raise AssertionError(f"having spent exactly max_tokens ({first}) counts as reached: the next call must be refused")
    except BE:
        pass
    m = mod.BudgetedMeter(ScriptedModel(["x"] * 5), Budget(max_usd=1e-9))
    m.ask("a", "S", "one")
    try:
        m.ask("a", "S", "two")
        raise AssertionError("once the dollar limit is reached, no further call")
    except BE as e:
        assert e.reason == "usd", f"reason should be 'usd'; got {e.reason!r}"
    m = mod.BudgetedMeter(ScriptedModel(["x"] * 3), Budget())
    for _ in range(3):
        m.ask("a", "S", "u")
    m.check_budget()
    m = mod.BudgetedMeter(ScriptedModel(["x"] * 3), Budget(max_calls=1, max_tokens=1))
    m.ask("a", "S", "u")
    try:
        m.check_budget()
        raise AssertionError("both limits are reached")
    except BE as e:
        assert e.reason == "calls", "when several limits are reached, 'calls' is reported first (then tokens, then usd)"
    # plan
    model = make_model()
    m = mod.Meter(model)
    tasks = mod.plan(m, "Compare refund windows in Leeds and Derby.")
    assert [t["city"] for t in tasks] == ["Leeds", "Derby"] and m.calls[0].step == "plan" and m.calls[0].tier == "large", f"plan: a 'plan' call on the large tier returning the parsed list; got {tasks}"
    assert mod.plan(mod.Meter(ScriptedModel(["not json"])), "x") == [] and mod.plan(mod.Meter(ScriptedModel(['{"a": 1}'])), "x") == [], "a plan that is not a JSON list is []"
    # orchestrate
    model = make_model()
    m = mod.Meter(model)
    o = mod.orchestrate(m, "Compare refund windows in Leeds and Derby.")
    assert o.answer == "Shortest window: Derby: 14 days. Longest: Leeds: 30 days." and (o.planned, o.ran, o.dropped) == (2, 2, []), f"two cities, no limit hit; got {o}"
    assert [c.step for c in m.calls] == ["plan", "worker", "worker", "synth"], f"cost shape: planner, one worker per subtask, synthesiser; got {[c.step for c in m.calls]}"
    assert [c.tier for c in m.calls] == ["large", "small", "small", "large"], "planner and synthesiser on the large tier, workers on the small one"
    assert sent(model, 1) == (mod.SYSTEM_WORK, "Find the refund window for Leeds") and sent(model, 3) == (mod.SYSTEM_SYNTH, "Leeds: 30 days\nDerby: 14 days"), "workers get the subtask text; the synthesiser gets the worker results joined by newlines"
    w = [c.seconds for c in m.calls[1:3]]
    assert near(m.clock, m.calls[0].seconds + max(w) + m.calls[3].seconds), "the workers run in parallel: plan + slowest worker + synth"
    # the limit, made visible
    req5 = "Compare refund windows in Leeds, Derby, York, Hull and Bath."
    m = mod.Meter(make_model())
    o = mod.orchestrate(m, req5, max_subtasks=3)
    assert o.planned == 5 and o.ran == 3 and [d["reason"] for d in o.dropped] == ["limit", "limit"], f"max_subtasks=3 on a five-city plan: 3 run, 2 dropped with reason 'limit'; got {o}"
    assert o.answer == "Shortest window: Derby: 14 days. Longest: York: 45 days. Not covered: Find the refund window for Hull, Find the refund window for Bath.", f"the answer must say what it left out; got {o.answer!r}"
    assert len(m.calls) == 1 + 3 + 1, "dropped subtasks cost nothing: planner, 3 workers, synthesiser"
    m = mod.Meter(make_model())
    o = mod.orchestrate(m, req5)
    assert (o.planned, o.ran, o.dropped) == (5, 5, []) and "Not covered" not in o.answer and len(m.calls) == 7, "the default limit is 6, so five cities all run (7 calls)"
    m = mod.Meter(make_model())
    o = mod.orchestrate(m, "Please summarise our policies.")
    assert (o.answer, o.planned, o.ran, o.dropped) == ("No subtasks found for this request.", 0, 0, []) and len(m.calls) == 1, "an empty plan: say so after the one planning call"
    # a budget that runs out in the middle
    m = mod.BudgetedMeter(make_model(), Budget(max_calls=4))
    o = mod.orchestrate(m, req5)
    assert len(m.calls) == 4 and o.ran == 3 and o.planned == 5, f"max_calls=4: the plan and three workers use the budget; got {len(m.calls)} calls, ran {o.ran}"
    assert [d["reason"] for d in o.dropped] == ["budget", "budget"], f"workers cut off by the budget are dropped with reason 'budget'; got {o.dropped}"
    assert o.answer == "Budget reached before synthesis: Leeds: 30 days; Derby: 14 days; York: 45 days. Not covered: Find the refund window for Hull, Find the refund window for Bath.", f"got {o.answer!r}"
    m = mod.BudgetedMeter(make_model(), Budget(max_calls=1))
    o = mod.orchestrate(m, req5)
    assert o.answer.startswith("No subtask finished: budget exhausted.") and o.ran == 0 and len(o.dropped) == 5, f"nothing ran: say so and list every subtask as not covered; got {o}"
    # property: whatever the budget, the orchestrator never raises, never exceeds it and always tells the truth about coverage
    for seed in seeds(range(1, 41)):
        rnd = random.Random(seed)
        cities = rnd.sample(list(POLICY_DAYS), rnd.randint(1, 5))
        req = "Compare refund windows in " + ", ".join(cities) + "."
        cap, limit = rnd.randint(1, 9), rnd.randint(1, 6)
        m = mod.BudgetedMeter(make_model(), Budget(max_calls=cap))
        o = mod.orchestrate(m, req, max_subtasks=limit)
        ctx = f"seed {seed}: cities {cities}, max_calls {cap}, max_subtasks {limit}"
        assert len(m.calls) <= cap, f"{ctx}: made {len(m.calls)} calls, over the budget"
        assert o.planned == len(cities) and o.ran + len(o.dropped) == o.planned, f"{ctx}: ran + dropped must equal planned; got {o}"
        assert o.ran <= limit and all(d["reason"] in ("limit", "budget") for d in o.dropped), f"{ctx}: bad result {o}"
        assert all(f"Find the refund window for {c}" in o.answer for c in cities if any(c in d["task"] for d in o.dropped)), f"{ctx}: every dropped subtask must be named in the answer"
        assert o.answer and ("Not covered" in o.answer) == bool(o.dropped), f"{ctx}: 'Not covered' appears exactly when something was dropped"
    return "budget checks before every call; planner, workers and synthesiser tiers; limits and budget cuts reported, 40 random budgets"


# =============================================================================
# Milestone 6: the whole desk
# =============================================================================
def m6():
    for vals, q, want in (([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 50, 5), ([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 95, 10), ([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 90, 9),
                          ([10, 1, 7, 3], 25, 1), ([10, 1, 7, 3], 100, 10), ([42], 50, 42), ([5, 5, 5], 99, 5)):
        assert mod.percentile(vals, q) == want, f"percentile({vals}, {q}) should be {want} (nearest rank); got {mod.percentile(vals, q)}"
    for bad in (([], 50), ([1], 0), ([1], 101)):
        try:
            mod.percentile(*bad)
            raise AssertionError(f"percentile{bad} must raise ValueError")
        except ValueError:
            pass
    # one ticket at a time
    model = make_model()
    r = mod.process_ticket(T["T01"], model)
    assert (r.ticket_id, r.status, r.reason, r.calls) == ("T01", "answered", "ok", 3), f"a tracking ticket with a real order: classify, extract, draft = 3 calls, answered; got {r}"
    ref = mod.Meter(make_model())
    mod.chain(ref, T["T01"]["text"])
    mod.classify(ref, T["T01"]["text"])
    assert r.tokens == sum(c.tokens_in + c.tokens_out for c in ref.calls) and near(r.cost_usd, ref.totals()["cost_usd"]), "TicketResult.tokens/cost must be the meter's totals for that ticket"
    expect = {"T04": ("human", "gate: no valid order id", 2), "T06": ("human", "router", 1), "T09": ("answered", "ok", 2), "T15": ("answered", "ok", 2),
              "T20": ("human", "router", 1), "T23": ("answered", "ok", 2), "T24": ("answered", "ok", 3)}
    for tid, (st, why, calls) in expect.items():
        r = mod.process_ticket(T[tid], make_model())
        assert (r.status, r.reason, r.calls) == (st, why, calls), f"{tid}: expected status {st}, reason {why!r}, {calls} calls; got {r.status}, {r.reason!r}, {r.calls}"
    assert mod.process_ticket(T["T14"], make_model(), threshold=0.6).status == "answered" and mod.process_ticket(T["T14"], make_model(), threshold=0.7).status == "human", "the threshold parameter must reach the router (T14 is a refund at confidence 0.62)"
    # budgets per ticket
    r = mod.process_ticket(T["T01"], make_model(), budget=mod.Budget(max_calls=2))
    assert (r.status, r.reason, r.calls) == ("human", "budget: calls", 2), f"a 3-call ticket with max_calls=2 stops after 2 and goes to a human; got {r}"
    r = mod.process_ticket(T["T09"], make_model(), budget=mod.Budget(max_calls=2))
    assert (r.status, r.calls) == ("answered", 2), "a 2-call ticket fits in max_calls=2"
    r = mod.process_ticket(T["T01"], make_model(), budget=mod.Budget(max_usd=1e-9))
    assert (r.status, r.reason, r.calls) == ("human", "budget: usd", 1), f"after the first call the dollar limit is reached; got {r}"
    # the desk
    d = mod.run_desk(TICKETS)
    res = d["results"]
    assert [x.ticket_id for x in res] == [t["id"] for t in TICKETS], "results come back in ticket order"
    assert (d["answered"], d["human"]) == (16, 8), f"at threshold 0.7: 16 answered, 8 to humans (7 by the router, 1 by gate 1); got {d['answered']} and {d['human']}"
    assert d["reasons"] == {"router": 7, "gate: no valid order id": 1}, f"reasons counts only the human-handled tickets; got {d['reasons']}"
    assert d["tokens_total"] == sum(x.tokens for x in res) and near(d["cost_usd"], sum(x.cost_usd for x in res)), "totals are the sums over tickets"
    toks = sorted(x.tokens for x in res)
    assert d["p50_tokens"] == toks[11] and d["p95_tokens"] == toks[22], f"p50 and p95 use nearest-rank on per-ticket tokens (rank 12 and rank 23 of 24); got {d['p50_tokens']}, {d['p95_tokens']}"
    for x in res:
        want_calls = 1 + (0 if x.reason == "router" else (1 if x.reason.startswith("gate") else (2 if T[x.ticket_id]["model_label"] == "tracking" else 1)))
        assert x.calls == want_calls, f"{x.ticket_id}: expected {want_calls} calls on its path; got {x.calls}"
    tight = mod.run_desk(TICKETS, budget=mod.Budget(max_calls=2))
    assert tight["reasons"].get("budget: calls") == 7 and tight["answered"] == 9, f"with max_calls=2 the seven 3-call tracking tickets are escalated; got {tight['reasons']}, answered {tight['answered']}"
    assert all(x.calls <= 2 for x in tight["results"]) and tight["cost_usd"] < d["cost_usd"], "a call budget caps every ticket and lowers the bill"
    loose = mod.run_desk(TICKETS, budget=mod.Budget(max_calls=10, max_tokens=10_000, max_usd=1.0))
    assert [(x.status, x.reason, x.calls) for x in loose["results"]] == [(x.status, x.reason, x.calls) for x in res], "a budget nobody reaches changes nothing"
    low = mod.run_desk(TICKETS, threshold=0.5)
    assert low["answered"] > d["answered"] and low["cost_usd"] > d["cost_usd"], "a lower threshold answers more and spends more"
    for seed in seeds(range(1, 21)):
        rnd = random.Random(seed)
        sub = rnd.sample(TICKETS, rnd.randint(1, 24))
        b = mod.Budget(max_calls=rnd.choice([None, 1, 2, 3]), max_tokens=rnd.choice([None, 60, 120]))
        th = rnd.choice([0.5, 0.7, 0.9])
        dd = mod.run_desk(sub, th, b)
        assert len(dd["results"]) == len(sub) and dd["answered"] + dd["human"] == len(sub), f"seed {seed}: every ticket ends answered or with a human"
        assert dd["p50_tokens"] <= dd["p95_tokens"] <= max(x.tokens for x in dd["results"]), f"seed {seed}: p50 <= p95 <= max"
        if b.max_calls:
            assert all(x.calls <= b.max_calls for x in dd["results"]), f"seed {seed}: a ticket exceeded max_calls={b.max_calls}"
        assert sum(dd["reasons"].values()) == dd["human"], f"seed {seed}: every human-handled ticket has a reason"
    rows = [f"{'':14s}{'answered':>9s}{'human':>7s}{'tokens':>8s}{'p50':>5s}{'p95':>5s}{'cost':>10s}"]
    for name, dd in (("threshold 0.7", d), ("threshold 0.5", low), ("max 2 calls", tight)):
        rows.append(f"{name:14s}{dd['answered']:>9d}{dd['human']:>7d}{dd['tokens_total']:>8,d}{dd['p50_tokens']:>5d}{dd['p95_tokens']:>5d}{'$' + format(dd['cost_usd'], '.5f'):>10s}")
    return "\n".join(rows)


MILESTONES = [
    (1, "Milestone 1: the meter, tokens, dollars and simulated time", m1),
    (2, "Milestone 2: a chain with gates", m2),
    (3, "Milestone 3: a router and its threshold", m3),
    (4, "Milestone 4: parallel fan-out, sectioning and voting", m4),
    (5, "Milestone 5: orchestrator-workers inside a budget", m5),
    (6, "Milestone 6: the whole desk, with per-ticket budgets", m6),
]

if __name__ == "__main__":
    t0 = time.time()
    print(f"Lab 4 checks against {target}.py\n")
    for n, name, fn in MILESTONES:
        check(n, name, fn)
    print(f"\n{sum(results)}/{len(results)} milestones passing  ({time.time() - t0:.1f} s)")
    sys.exit(0 if all(results) else 1)
