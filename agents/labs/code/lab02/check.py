"""Self-check for Lab 2: Tool Design, Measured.

    python3 check.py                  # checks your starter.py
    python3 check.py solution         # checks the reference solution
    python3 check.py solution 4       # only milestone 4
    python3 check.py solution 5 12    # milestone 5, replaying ONLY the random case of seed 12

Everything is deterministic: the backend is a fixed in-memory dataset, the "agent" is a
stand-in with seeded behaviour, and the statistics take an explicit seed. No network, no
clock. The whole check takes a few seconds (the two designs are each run 60 times).
Prints a tick, a cross, or "not implemented yet" for each milestone.
"""
import importlib
import json
import math
import os
import random
import sys
import time
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True

args = sys.argv[1:]
target = args[0] if args and not args[0].isdigit() else "starter"
rest = [a for a in args if a.isdigit()]
ONLY = int(rest[0]) if rest else None
ONLY_SEED = int(rest[1]) if len(rest) > 1 else None
mod = importlib.import_module(target)
from fixtures import REFUND_CAP_CENTS, TASKS, Northwind  # noqa: E402
from llm import count_tokens  # noqa: E402

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


def task(id):
    return next(t for t in TASKS if t["id"] == id)


def raises_tool_error(fn, *a):
    try:
        fn(*a)
    except mod.ToolError as e:
        return str(e)
    raise AssertionError(f"{fn.__name__}{a[1:]} should have raised ToolError but returned normally")


# =============================================================================
# Milestone 1: lint a toolset, count its cost
# =============================================================================
def m1():
    thin = mod.lint(mod.THIN)
    assert all(isinstance(f, tuple) and len(f) == 3 for f in thin), f"each finding is a (tool, code, message) tuple; got {thin[:2]}"
    got = [(f[0], f[1]) for f in thin]
    want = [("get_customer", "thin"), ("get_customer", "generic_arg"), ("get_customer", "undescribed_arg"),
            ("list_invoices", "thin"), ("list_invoices", "undescribed_arg"),
            ("get_invoice", "thin"), ("get_invoice", "generic_arg"), ("get_invoice", "undescribed_arg"),
            ("list_payments", "thin"), ("list_payments", "undescribed_arg"),
            ("create_refund", "thin"), ("create_refund", "undescribed_arg"), ("create_refund", "undescribed_arg")]
    assert got == want, ("the thin wrappers should give these 13 findings in this order (chapter 5 prints the same list):\n"
                         f"  expected {want}\n  got      {got}")
    assert mod.lint(mod.BETTER) == [], f"the redesigned set should have no findings; got {mod.lint(mod.BETTER)}"

    long = " ".join(["get order"] * 9)
    tool = {"name": "get_order", "description": long, "input_schema": {"type": "object", "properties": {"order_id": {"type": "string", "description": "id"}}}}
    codes = [f[1] for f in mod.lint([tool])]
    assert codes == ["restates"], f"a long description that only repeats the name's words is 'restates' (and not 'thin'); got {codes}"
    short = dict(tool, description="Get order.")
    assert [f[1] for f in mod.lint([short])] == ["thin", "restates"], "a short description that restates the name gets both findings, 'thin' first"
    enum_only = {"name": "set_mode", "description": "Switch the machine into the requested running mode. " * 3,
                 "input_schema": {"type": "object", "properties": {"mode": {"type": "string", "enum": ["fast", "slow"]}}}}
    assert mod.lint([enum_only]) == [], "a property with an enum does not need a description"

    common = "alpha bravo charlie delta echo foxtrot golf".split()
    a_extra = "hotel india juliet kilo lima mike".split()
    b_extra = "november oscar papa quebec romeo sierra tango".split()
    mk = lambda name, ws: {"name": name, "description": " ".join(ws + ["is"] * 8), "input_schema": {"type": "object", "properties": {}}}
    ta, tb, tc = mk("tool_a", common + a_extra), mk("tool_b", common + b_extra), mk("tool_c", ["whiskey", "xray", "yankee", "zulu"] * 1)
    f = mod.lint([ta, tb])
    assert len(f) == 1 and f[0][0] == "tool_a" and f[0][1] == "overlap" and "tool_b" in f[0][2], \
        f"7 shared words out of 20 is a Jaccard of exactly 0.35, which counts ('at least 0.35'); the finding goes against the first tool and names the second; got {f}"
    f = mod.lint([ta, tc, tb])
    assert [x[:2] for x in f if x[1] == "overlap"] == [("tool_a", "overlap")], f"overlap compares every pair, in list order; got {f}"
    assert [x[1] for x in mod.lint([ta, tc, tb])][-1] == "overlap", "overlap findings come after all the per-tool findings"
    edge = lambda n: dict(tool, name="lookup_thing", description=" ".join(["word"] * n))
    assert [f[1] for f in mod.lint([edge(14)])] == ["thin"] and mod.lint([edge(15)]) == [], "the limit is 15 words: 14 is thin, 15 is not"
    assert mod.lint([]) == [], "no tools, no findings"

    assert mod.definition_tokens(mod.THIN) == 217, f"the five thin definitions cost 217 tokens (chapter 5); got {mod.definition_tokens(mod.THIN)}"
    assert mod.definition_tokens(mod.BETTER) == 488, f"the three redesigned definitions cost 488 tokens (chapter 5); got {mod.definition_tokens(mod.BETTER)}"
    assert mod.definition_tokens([]) == 0
    assert mod.definition_tokens(mod.THIN[:1]) == count_tokens(json.dumps(mod.THIN[0])), "one definition costs count_tokens(json.dumps(definition))"

    for s in seeds(range(60)):
        rng = random.Random(s)
        props, expect_undescribed = {}, 0
        for i in range(rng.randint(0, 6)):
            spec = {"type": "string"}
            kind = rng.choice(["plain", "described", "enum"])
            if kind == "described":
                spec["description"] = "x"
            elif kind == "enum":
                spec["enum"] = ["a"]
            else:
                expect_undescribed += 1
            props[f"param_{i}"] = spec
        t = {"name": "tool_x", "description": "Do something quite specific and useful for the person who asked, then report back clearly and briefly now.",
             "input_schema": {"type": "object", "properties": props}}
        n = sum(1 for f in mod.lint([t]) if f[1] == "undescribed_arg")
        assert n == expect_undescribed, f"seed {s}: expected {expect_undescribed} undescribed_arg findings for {props}, got {n}"
    return f"thin wrappers: {len(thin)} findings, {mod.definition_tokens(mod.THIN)} tokens of definitions;  redesigned: 0 findings, {mod.definition_tokens(mod.BETTER)} tokens"


# =============================================================================
# Milestone 2: the task-shaped tools
# =============================================================================
def m2():
    db = Northwind()
    r = mod.find_customer(db, "ana@example.com")
    assert isinstance(r, list) and len(r) == 1 and set(r[0]) == {"customer_id", "name", "email"} and r[0]["customer_id"] == "cus_1042", \
        f"find_customer by email should return a list of one {{customer_id, name, email}}; got {r!r}"
    assert len(mod.find_customer(db, "Ana Silva")) == 2, "two customers are called Ana Silva: return both and let the model ask which"
    assert [c["customer_id"] for c in mod.find_customer(db, "  BEN@EXAMPLE.COM ")] == ["cus_1043"], "email lookup ignores case and surrounding spaces"
    miss = mod.find_customer(db, "nobody@example.com")
    assert isinstance(miss, str) and miss.startswith("No customer found for") and "nobody@example.com" in miss and "email" in miss.lower(), \
        f"no match: RETURN a sentence 'No customer found for ...' that says what to try; got {miss!r}"

    def owed(cid):
        return sum(i["amount_cents"] for i in db.invoices if i["customer_id"] == cid and i["status"] in ("open", "overdue"))
    s = mod.account_summary(db, "cus_1042")
    assert set(s) == {"customer_id", "name", "plan", "owed_cents", "open_invoices", "latest_payment", "recent_payments"}, f"summary keys wrong: {sorted(s)}"
    assert s["owed_cents"] == 9800 and [i["invoice_id"] for i in s["open_invoices"]] == ["inv_3000", "inv_3002"], \
        f"Ana owes 9800 over two invoices, newest first (Apr open, Feb overdue); got {s['owed_cents']} and {[i['invoice_id'] for i in s['open_invoices']]}"
    assert set(s["open_invoices"][0]) == {"invoice_id", "status", "amount_cents", "due"} and s["open_invoices"][0]["due"] == "2026-04-15", \
        f"open invoice rows are {{invoice_id, status, amount_cents, due}}; got {s['open_invoices'][0]}"
    assert s["latest_payment"] == s["recent_payments"][0] and s["latest_payment"]["payment_id"] == "pay_88124", f"latest_payment is the newest payment; got {s['latest_payment']}"
    assert set(s["latest_payment"]) == {"payment_id", "invoice_id", "amount_cents", "paid_at"}
    assert len(s["recent_payments"]) == 5 and [p["payment_id"] for p in s["recent_payments"][:2]] == ["pay_88124", "pay_88123"], "recent_payments: the newest 5, newest first"
    for cid in db.customers:
        assert mod.account_summary(db, cid)["owed_cents"] == owed(cid), f"owed_cents for {cid} should be the sum of ALL open and overdue invoices ({owed(cid)})"
    chen = mod.account_summary(db, "cus_1044")
    assert "pay_88450" in [p["payment_id"] for p in chen["recent_payments"]], "Chen's annual payment must be visible in recent_payments (the refund task needs its id)"

    raw = count_tokens(json.dumps(db.invoices_of("cus_1042")))
    concise = count_tokens(json.dumps(s))
    detailed_s = mod.account_summary(db, "cus_1042", "detailed")
    detailed = count_tokens(json.dumps(detailed_s))
    assert concise < 450, f"the concise summary of a customer with 60 invoices should be a few hundred tokens at most; got {concise} (did you include every invoice or the addresses?)"
    assert detailed > concise and "line_items" in detailed_s["open_invoices"][0] and "line_items" not in s["open_invoices"][0], \
        "response_format='detailed' adds line_items to the open invoices; 'concise' (the default) does not"
    assert raw > 20 * concise, f"the raw invoice dump ({raw} tokens) should be more than 20 times the summary ({concise})"
    msg = raises_tool_error(mod.account_summary, db, "cus_9999")
    assert msg.startswith("No customer with id 'cus_9999'") and "billing_find_customer" in msg, f"unknown id: ToolError that points at billing_find_customer; got {msg!r}"
    bare = Northwind()
    bare.payments = {}
    e = mod.account_summary(bare, "cus_1047")
    assert e["latest_payment"] is None and e["recent_payments"] == [], f"a customer with no payments has latest_payment None and an empty list; got {e['latest_payment']}"

    db = Northwind()
    assert mod.issue_refund(db, "pay_88502", 2500, "goodwill") == "Refunded 2500 cents of pay_88502 (goodwill); 4400 cents still refundable.", "success message wrong"
    again = mod.issue_refund(db, "pay_88502", 2500, "goodwill")
    assert "no money moved again" in again and db.refunds == [("pay_88502", 2500)], f"an identical request is a repeat: say so and move nothing; got {again!r}, refunds {db.refunds}"
    mod.issue_refund(db, "pay_88502", 2500, "duplicate")
    assert len(db.refunds) == 2, "the key is payment:amount:reason, so a different reason is a different request"
    msg = raises_tool_error(mod.issue_refund, db, "pay_88502", 5000, "goodwill")
    assert "between 1 and 1900" in msg and "cents" in msg, f"5000 is more than the 1900 still refundable: name the legal range and the unit; got {msg!r}"
    assert "between 1 and" in raises_tool_error(mod.issue_refund, db, "pay_88501", 0, "goodwill")
    msg = raises_tool_error(mod.issue_refund, db, "88501", 100, "goodwill")
    assert "88501" in msg and "pay_88123" in msg and "billing_get_account_summary" in msg, f"unknown payment: show the id shape and where to get one; got {msg!r}"
    before = list(db.refunds)
    msg = raises_tool_error(mod.issue_refund, db, "pay_88450", REFUND_CAP_CENTS + 1, "goodwill")
    assert "human" in msg and str(REFUND_CAP_CENTS) in msg and "retry" in msg.lower() and db.refunds == before, f"over the cap: mention the cap, a human, and not to retry; nothing moves. Got {msg!r}"
    assert mod.issue_refund(db, "pay_88450", REFUND_CAP_CENTS, "goodwill").startswith("Refunded 10000 cents"), "exactly the cap is allowed"

    flaky = Northwind(flaky=True)
    msg = raises_tool_error(mod.issue_refund, flaky, "pay_88124", 4900, "duplicate")
    assert "timed out" in msg and "Retry" in msg and flaky.refunds == [("pay_88124", 4900)], f"the first call times out AFTER the money moved; got {msg!r}, refunds {flaky.refunds}"
    retry = mod.issue_refund(flaky, "pay_88124", 4900, "duplicate")
    assert "no money moved again" in retry and flaky.refunds == [("pay_88124", 4900)], \
        (f"the retry must reach the backend with the same idempotency key and be recognised as a repeat; got {retry!r}, refunds {flaky.refunds}. "
         "Hint: do not pre-check the amount against what is left: after the first call nothing is left.")

    for s in seeds(range(60)):
        rng = random.Random(s)
        fdb = Northwind(flaky=rng.random() < 0.7)
        pids = sorted(fdb.payments)
        reason = rng.choice(["duplicate", "goodwill"])      # one reason per scenario: the same payment+amount is then the same request
        for _ in range(rng.randint(3, 12)):
            pid = rng.choice(pids[:4] + ["pay_88502", "pay_88124", "pay_88450"])
            amt = rng.choice([100, 2500, 4900, 6900, 12000])
            for attempt in range(3):
                try:
                    mod.issue_refund(fdb, pid, amt, reason)
                    break
                except mod.ToolError as e:
                    if "timed out" not in str(e):
                        break
        moved = Counter(fdb.refunds)
        assert all(v == 1 for v in moved.values()), f"seed {s}: the same payment+amount was refunded twice: { {k: v for k, v in moved.items() if v > 1} }"
        for pid, p in fdb.payments.items():
            assert p["refunded_cents"] == sum(a for q, a in fdb.refunds if q == pid) <= p["amount_cents"], f"seed {s}: {pid} refunded more than it was paid"
        assert all(a <= REFUND_CAP_CENTS for _, a in fdb.refunds), f"seed {s}: a refund above the cap went through"
    return f"concise summary of a 60-invoice customer: {concise} tokens (the raw dump is {raw})"


# =============================================================================
# Milestone 3: grading by end state
# =============================================================================
def m3():
    db = Northwind()
    t = task("T10")
    db.refunds = [("pay_88302", 2900)]
    g = mod.grade(t, db, "I have issued the refund of £29.00.")
    assert g.success is True and g.harmful is False and g.reasons == [], f"correct refund and answer: expected success, not harmful, no reasons; got {g}"
    db.refunds = []
    g = mod.grade(t, db, "I have issued the refund of £29.00.")
    assert g.success is False and g.harmful is False and g.reasons and "refund" in g.reasons[0], \
        f"a refund that never happened fails the task (the answer claiming it is irrelevant) but is not harmful; got {g}"
    db.refunds = [("pay_88302", 29)]
    g = mod.grade(t, db, "I have issued the refund of £29.00.")
    assert g.success is False and g.harmful is True, f"the wrong amount moved real money: harmful; got {g}"
    db.refunds = [("pay_88302", 2900), ("pay_88302", 2900)]
    g = mod.grade(t, db, "refund done")
    assert g.success is False and g.harmful is True, f"a double refund is harmful; got {g}"
    db.refunds = [("pay_88302", 2900), ("pay_88301", 100)]
    g = mod.grade(t, db, "refund")
    assert g.success is False and g.harmful is True, f"the right refund plus an extra one is harmful; got {g}"

    two = dict(t, expected_refunds=[("pay_1", 5), ("pay_2", 7)], must_include=[])
    db.refunds = [("pay_2", 7), ("pay_1", 5)]
    assert mod.grade(two, db, "").success is True, "the order in which refunds happened does not matter, and an empty answer is fine when nothing is required"
    db.refunds = [["pay_2", 7], ["pay_1", 5]]
    assert mod.grade(two, db, "").success is True, "refund entries may be lists as well as tuples"

    db.refunds = []
    u = task("T17")
    assert mod.grade(u, db, "I found No Customer matching nobody@example.com.").success is True, "phrases are matched ignoring case"
    g = mod.grade(u, db, "I could not help.")
    assert g.success is False and any("no customer" in r for r in g.reasons), f"a missing phrase is a reason that quotes it; got {g.reasons}"
    forbid = dict(u, must_include=[], must_not_include=["password"])
    g = mod.grade(forbid, db, "Your PASSWORD is hunter2")
    assert g.success is False and any("password" in r.lower() for r in g.reasons), f"a forbidden phrase fails the task (any case); got {g}"
    cap = task("T15")
    db.refunds = [("pay_88450", 25000)]
    g = mod.grade(cap, db, "Refunded £250.00")
    assert g.success is False and g.harmful is True and len(g.reasons) == 2, f"refund above the cap: harmful, and two rules broken (unexpected refund, missing 'human'); got {g}"
    db.refunds = []
    assert mod.grade(cap, db, "A human colleague will review it.").success is True
    keep = [("pay_1", 1)]
    db.refunds = keep
    mod.grade(two, db, "")
    assert db.refunds is keep and keep == [("pay_1", 1)], "grade must not modify the backend"

    for s in seeds(range(60)):
        rng = random.Random(s)
        pool = [("pay_a", 100), ("pay_a", 200), ("pay_b", 100), ("pay_c", 5)]
        exp = [rng.choice(pool) for _ in range(rng.randint(0, 3))]
        act = list(exp)
        if rng.random() < 0.6:
            act = [x for x in act if rng.random() < 0.7] + [rng.choice(pool) for _ in range(rng.randint(0, 2))]
        rng.shuffle(act)
        phrases = rng.sample(["alpha", "beta", "gamma"], rng.randint(0, 2))
        answer = " ".join(rng.sample(["Alpha", "BETA", "delta"], rng.randint(0, 3)))
        tk = dict(expected_refunds=exp, must_include=phrases, must_not_include=[], id="X")
        db = Northwind()
        db.refunds = act
        g = mod.grade(tk, db, answer)
        extra = Counter(act) - Counter(exp)
        ok = Counter(act) == Counter(exp) and all(p in answer.lower() for p in phrases)
        assert g.success == ok, f"seed {s}: expected={exp} actual={act} include={phrases} answer={answer!r}: success should be {ok}, got {g.success}"
        assert g.harmful == bool(extra), f"seed {s}: expected={exp} actual={act}: harmful should be {bool(extra)} (unexpected refunds {dict(extra)}), got {g.harmful}"
        assert g.success == (not g.reasons), f"seed {s}: success must mean 'no reasons'; got {g}"
    return ""


# =============================================================================
# Milestone 4: run everything, summarise
# =============================================================================
def rec(design, task_id, trial, success, harmful=False, status="done", calls=3, tools=2, errs=0, tin=1000, tres=100):
    return mod.Record(design, task_id, trial, success, harmful, status, calls, tools, errs, tin, tres)


def m4():
    text = lambda s: {"type": "text", "text": s}
    use = lambda i, name, inp: {"type": "tool_use", "id": i, "name": name, "input": inp}
    res = lambda i, c, err=False: {"type": "tool_result", "tool_use_id": i, "content": c, "is_error": err}
    msgs = [{"role": "user", "content": "question"},
            {"role": "assistant", "content": [text("hmm"), use("a", "t", {"x": 1, "y": 2}), use("b", "u", {})]},
            {"role": "user", "content": [res("a", "x" * 400, True), res("b", "ok")]},
            {"role": "assistant", "content": [use("c", "t", {"y": 2, "x": 1})]},
            {"role": "user", "content": [res("c", "y" * 40)]},
            {"role": "assistant", "content": [text("done")]}]
    m = mod.run_metrics(msgs)
    want = {"model_calls": 3, "tool_calls": 3, "tool_errors": 1, "result_tokens": 100 + 1 + 10, "repeated_calls": 1}
    assert m == want, f"run_metrics wrong.\n  expected {want}\n  got      {m}\n  hint: tokens are count_tokens(content) per tool_result; the repeat is the same name and input (key order ignored)"
    assert mod.run_metrics([{"role": "user", "content": "hi"}]) == {"model_calls": 0, "tool_calls": 0, "tool_errors": 0, "result_tokens": 0, "repeated_calls": 0}, "string content has no blocks"

    pair = [task("T17"), task("T18")]
    recs = mod.evaluate("A", pair, trials=2)
    assert [(r.task_id, r.trial) for r in recs] == [("T17", 0), ("T17", 1), ("T18", 0), ("T18", 1)], f"one record per run, task by task, trial by trial; got {[(r.task_id, r.trial) for r in recs]}"
    r0 = recs[0]
    assert (r0.design, r0.success, r0.harmful, r0.status, r0.model_calls, r0.tool_calls, r0.tool_errors) == ("A", True, False, "done", 3, 2, 1), \
        f"design A on an unknown customer: 3 model calls, 2 tool calls, the first (get_customer) an error, and the task passes; got {r0}"
    result, db = mod.run_one("A", pair[0], 0)
    assert r0.input_tokens == result.input_tokens > 0 and r0.result_tokens == mod.run_metrics(result.messages)["result_tokens"], "input_tokens comes from the RunResult; result_tokens from run_metrics"
    assert mod.evaluate("A", [], trials=3) == [] and mod.evaluate("A", pair, trials=0) == []

    rs = [rec("A", "T1", 0, True, tin=1000), rec("A", "T1", 1, False, True, "token_budget", calls=5, tools=4, errs=2, tin=3000),
          rec("A", "T2", 0, True, tin=2000), rec("A", "T2", 1, True, tin=2000)]
    rep = mod.aggregate(rs)
    assert (rep["design"], rep["n_runs"], rep["n_tasks"]) == ("A", 4, 2), f"design/n_runs/n_tasks; got {rep['design']}, {rep['n_runs']}, {rep['n_tasks']}"
    assert rep["success_rate"] == 0.75 and rep["harm_rate"] == 0.25, f"success 3/4 and harm 1/4; got {rep['success_rate']}, {rep['harm_rate']}"
    assert (rep["mean_model_calls"], rep["mean_tool_calls"], rep["mean_tool_errors"], rep["mean_input_tokens"]) == (3.5, 2.5, 0.5, 2000.0), \
        f"means over runs wrong; got {rep['mean_model_calls']}, {rep['mean_tool_calls']}, {rep['mean_tool_errors']}, {rep['mean_input_tokens']}"
    assert rep["statuses"] == {"done": 3, "token_budget": 1}, f"statuses; got {rep['statuses']}"
    assert list(rep["per_task"]) == ["T1", "T2"] and rep["per_task"]["T1"] == {"success": 0.5, "harm": 0.5, "input_tokens": 2000.0} \
        and rep["per_task"]["T2"] == {"success": 1.0, "harm": 0.0, "input_tokens": 2000.0}, f"per_task wrong: {rep['per_task']}"
    try:
        mod.aggregate([])
        raise AssertionError("aggregate([]) should raise ValueError")
    except ValueError:
        pass

    full = mod.aggregate(mod.evaluate("A", TASKS, trials=3))
    ok = round(full["success_rate"] * 60)
    assert full["n_runs"] == 60 and full["n_tasks"] == 20, f"20 tasks x 3 trials = 60 runs; got {full['n_runs']} runs over {full['n_tasks']} tasks"
    assert ok == 43 and round(full["harm_rate"] * 60) == 13 and full["statuses"] == {"done": 55, "token_budget": 5}, \
        (f"design A over all 60 runs should have 43 successes, 13 harmful runs and 5 runs stopped by the token budget; "
         f"got {ok}, {round(full['harm_rate'] * 60)}, {full['statuses']}. Look at grade (milestone 3) and at how evaluate passes the trial number to run_one.")
    return f"design A, 20 tasks x 3 trials: success {ok}/60, harmful {round(full['harm_rate'] * 60)}/60, mean input tokens {full['mean_input_tokens']:.0f}"


# =============================================================================
# Milestone 5: from reports to a decision
# =============================================================================
def ref_boot(diffs, n_boot, seed, alpha=0.05):
    rng = random.Random(seed)
    n = len(diffs)
    means = sorted(sum(diffs[rng.randrange(n)] for _ in range(n)) / n for _ in range(n_boot))
    return sum(diffs) / n, means[int(n_boot * alpha / 2)], means[int(n_boot * (1 - alpha / 2)) - 1]


def report(per_task, harm=0.0):
    return {"per_task": {k: {"success": v[0], "input_tokens": v[1], "harm": 0.0} for k, v in per_task.items()}, "harm_rate": harm}


def m5():
    for bad in ([],):
        try:
            mod.paired_bootstrap_ci(bad)
            raise AssertionError("an empty list of differences should raise ValueError")
        except ValueError:
            pass
    assert mod.paired_bootstrap_ci([0.5] * 10) == (0.5, 0.5, 0.5), "ten identical differences have a zero-width interval"
    m, lo, hi = mod.paired_bootstrap_ci([1, 0, 0, 1, 1, 0, -1, 0], n_boot=500, seed=3)
    want = ref_boot([1, 0, 0, 1, 1, 0, -1, 0], 500, 3)
    assert (m, lo, hi) == want, (f"paired_bootstrap_ci([1, 0, 0, 1, 1, 0, -1, 0], n_boot=500, seed=3) should be {want}; got {(m, lo, hi)}.\n"
                                 "  Follow the procedure in the docstring exactly: random.Random(seed), then diffs[rng.randrange(n)] for each of n draws, in order.")
    for s in seeds(range(40)):
        rng = random.Random(s)
        d = [rng.choice([-1, 0, 0, 1, 0.5, 0.25]) for _ in range(rng.randint(2, 25))]
        nb, sd = rng.choice([200, 1000, 2000]), rng.randint(0, 99)
        got, want = mod.paired_bootstrap_ci(d, nb, sd), ref_boot(d, nb, sd)
        assert got == want, f"seed {s}: paired_bootstrap_ci({d}, {nb}, {sd}) should be {want}; got {got}"
        assert got[1] <= got[0] + 1e-12 and got[0] <= got[2] + 1e-12 or max(d) == min(d), f"seed {s}: the mean {got[0]} should lie inside its interval ({got[1]}, {got[2]})"
    a2 = mod.paired_bootstrap_ci([1, -1, 0.5, 0], 300, 1)
    assert a2 == mod.paired_bootstrap_ci([1, -1, 0.5, 0], 300, 1) and a2 != mod.paired_bootstrap_ci([1, -1, 0.5, 0], 300, 2), "same seed same answer; a different seed a different resample"

    for w, l, p in ((8, 2, 0.109375), (10, 0, 2 / 1024), (5, 5, 1.0), (0, 0, 1.0), (7, 2, 0.1796875), (0, 3, 0.25), (2, 8, 0.109375)):
        got = mod.sign_test_p(w, l)
        assert abs(got - p) < 1e-12, f"sign_test_p({w}, {l}) should be {p}; got {got}. (n = wins + losses, k = min, p = min(1, 2 * P(X <= k)) for X ~ Binomial(n, 1/2))"

    ids = [f"T{i:02d}" for i in range(20)]
    a = report({t: (0.0, 1000.0) for t in ids})
    b = report({t: ((1.0 if i < 10 else 0.0), 1000.0) for i, t in enumerate(ids)})
    d = mod.decide(a, b)
    assert d["verdict"] == "B" and (d["wins"], d["losses"], d["ties"]) == (10, 0, 10) and d["regressions"] == [], f"B wins ten tasks and loses none: verdict B; got {d}"
    assert abs(d["p_sign"] - 2 / 1024) < 1e-12 and abs(d["success_diff"] - 0.5) < 1e-12 and d["success_ci"][0] > 0, f"sign test and interval; got {d}"
    r = mod.decide(b, a)
    assert r["verdict"] == "A" and r["wins"] == 0 and r["losses"] == 10 and r["regressions"] == ids[:10], f"swap the reports: verdict A, and the 10 tasks B (now the weaker) loses are the regressions, sorted; got {r['verdict']} {r['regressions']}"

    flat = report({t: (1.0, 5000.0) for t in ids})
    cheap = report({t: (1.0, 2000.0) for t in ids})
    c = mod.decide(flat, cheap)
    assert c["verdict"] == "B" and c["wins"] == 0 and c["ties"] == 20 and "cheaper" in c["reason"].lower() and abs(c["tokens_diff"] + 3000) < 1e-9, f"equal success, B cheaper: verdict B because of cost; got {c}"
    assert mod.decide(cheap, flat)["verdict"] == "A", "equal success, A cheaper: verdict A"
    n = mod.decide(flat, report({t: (1.0, 5000.0) for t in ids}))
    assert n["verdict"] == "none", f"identical reports: no clear winner; got {n['verdict']}"
    noisy_a = report({t: (1.0 if i % 2 else 0.0, 1000.0 + 50 * ((-1) ** i)) for i, t in enumerate(ids)})
    noisy_b = report({t: (0.0 if i % 2 else 1.0, 1000.0 - 50 * ((-1) ** i)) for i, t in enumerate(ids)})
    assert mod.decide(noisy_a, noisy_b)["verdict"] == "none", "a 10 wins / 10 losses split with symmetric costs has no winner"
    sub = mod.decide(report({"T1": (0.0, 10.0), "T2": (1.0, 10.0), "X": (0.0, 10.0)}), report({"T1": (1.0, 10.0), "T2": (0.0, 10.0), "Y": (1.0, 10.0)}))
    assert (sub["wins"], sub["losses"], sub["ties"]) == (1, 1, 0) and sub["regressions"] == ["T2"], f"only the tasks both reports share are compared; got {sub}"
    h = mod.decide(report({"T1": (1.0, 1.0)}, harm=0.25), report({"T1": (1.0, 1.0)}, harm=0.0))
    assert (h["harm_a"], h["harm_b"]) == (0.25, 0.0), "harm rates are passed through from the reports"

    # the real thing: both designs, all twenty tasks, three trials each
    A, B = mod.evaluate("A", TASKS, 3), mod.evaluate("B", TASKS, 3)
    ra, rb = mod.aggregate(A), mod.aggregate(B)
    assert round(rb["success_rate"] * 60) == 54 and rb["harm_rate"] == 0.0 and round(ra["success_rate"] * 60) == 43, \
        f"expected 43/60 successes for A and 54/60 for B (no harm); got {round(ra['success_rate'] * 60)} and {round(rb['success_rate'] * 60)} (harm {rb['harm_rate']}). Check issue_refund, account_summary and grade first."
    dec = mod.decide(ra, rb)
    lo, hi = dec["success_ci"]
    assert dec["regressions"] == ["T07", "T08"], f"B should do worse than A on exactly the two history tasks T07 and T08; got {dec['regressions']}"
    assert abs(dec["success_diff"] - 0.18333333) < 1e-6 and -0.1 < lo <= 0 < hi < 0.5, \
        f"on 20 tasks B's success advantage is +0.183 with an interval that includes zero (about -0.07 to 0.42); got {dec['success_diff']:.3f} ({lo:.3f}, {hi:.3f})"
    assert dec["tokens_ci"][1] < 0 and dec["verdict"] == "B" and "cheaper" in dec["reason"].lower(), f"cost separates the designs: the token interval for B minus A is below zero; verdict B. Got {dec}"
    dev = [t["id"] for t in TASKS if t["split"] == "dev"]
    held = [t["id"] for t in TASKS if t["split"] == "held"]
    d_dev = mod.decide(mod.aggregate([r for r in A if r.task_id in dev]), mod.aggregate([r for r in B if r.task_id in dev]))
    d_held = mod.decide(mod.aggregate([r for r in A if r.task_id in held]), mod.aggregate([r for r in B if r.task_id in held]))
    assert d_dev["verdict"] == d_held["verdict"] == "B", f"the verdict chosen on the 14 development tasks should hold on the 6 held-out tasks; got {d_dev['verdict']} and {d_held['verdict']}"
    rows = [f"{'':8s}{'success':>9s}{'harmful':>9s}{'calls':>7s}{'errors':>8s}{'input tokens':>14s}"]
    for name, r in (("A thin", ra), ("B shaped", rb)):
        rows.append(f"{name:8s}{r['success_rate']:>9.1%}{r['harm_rate']:>9.1%}{r['mean_tool_calls']:>7.2f}{r['mean_tool_errors']:>8.2f}{r['mean_input_tokens']:>14,.0f}")
    rows.append(f"B minus A: success {dec['success_diff']:+.3f} (95% CI {lo:+.3f} to {hi:+.3f}),  sign test {dec['wins']} wins / {dec['losses']} losses, p = {dec['p_sign']:.2f}")
    rows.append(f"           input tokens per task {dec['tokens_diff']:+,.0f} (95% CI {dec['tokens_ci'][0]:+,.0f} to {dec['tokens_ci'][1]:+,.0f})")
    rows.append(f"verdict: {dec['verdict']}.  {dec['reason']}  Regressions: {', '.join(dec['regressions'])}")
    rows.append(f"development tasks: {d_dev['verdict']};  held-out tasks: {d_held['verdict']}")
    return "\n".join(rows)


MILESTONES = [
    (1, "Milestone 1: lint a toolset and count what it costs", m1),
    (2, "Milestone 2: the task-shaped tools", m2),
    (3, "Milestone 3: grading by end state", m3),
    (4, "Milestone 4: run all twenty tasks and summarise", m4),
    (5, "Milestone 5: from two reports to a decision", m5),
]

if __name__ == "__main__":
    t0 = time.time()
    print(f"Lab 2 checks against {target}.py\n")
    for n, name, fn in MILESTONES:
        check(n, name, fn)
    print(f"\n{sum(results)}/{len(results)} milestones passing  ({time.time() - t0:.1f} s)")
    sys.exit(0 if all(results) else 1)
