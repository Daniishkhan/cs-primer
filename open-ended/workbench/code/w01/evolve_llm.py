"""Program evolution with a real model: Lab 3's loop, with a language model
writing the new priority() functions instead of a scripted editor.

The model is any OpenAI-compatible server. Ollama on a laptop (default):
    ollama pull qwen2.5-coder:7b
    python evolve_llm.py --model qwen2.5-coder:7b
vLLM on a GPU box, or `transformers serve` (any OpenAI-compatible server):
    python evolve_llm.py --base-url http://127.0.0.1:8000/v1 \\
        --model Qwen/Qwen2.5-0.5B-Instruct

Needs: Python 3.9+ and binpack.py next to this file. No other packages."""
import argparse
import ast
import json
import random
import re
import time
import urllib.request
from collections import Counter

from binpack import (SEED_SRC, FIRST_FIT_SRC, TRAIN_SEEDS, SELECT_SEEDS,
                     TEST_SEEDS, Database, canonical, evaluate, lower_bound,
                     make_instances)

# ── 1. Settings ──────────────────────────────────────────────────────────
ap = argparse.ArgumentParser()
ap.add_argument("--base-url", default="http://localhost:11434/v1")
ap.add_argument("--model", default="qwen2.5-coder:7b")
ap.add_argument("--api-key", default="none")          # Ollama ignores it
ap.add_argument("--calls", type=int, default=100)      # model calls (budget)
ap.add_argument("--islands", type=int, default=4)
ap.add_argument("--shots", type=int, default=2)       # programs per prompt
ap.add_argument("--temperature", type=float, default=0.8)
ap.add_argument("--max-tokens", type=int, default=300)
ap.add_argument("--reseed-every", type=int, default=25)
ap.add_argument("--seed", type=int, default=0)
ap.add_argument("--log", default="evolve_llm.jsonl")
args, _ = ap.parse_known_args()        # notebooks pass their own flags

train = make_instances(TRAIN_SEEDS)    # the search set
select = make_instances(SELECT_SEEDS)  # picks among finalists, once
test = make_instances(TEST_SEEDS)      # reported once, at the very end

# ── 2. Predict: what the two classic rules score (no model involved) ─────
print(f"model {args.model} at {args.base_url}")
for name, sets in (("search", train), ("selection", select), ("test", test)):
    lb = sum(map(lower_bound, sets)) / len(sets)
    ff = evaluate(FIRST_FIT_SRC, sets).score
    bf = evaluate(SEED_SRC, sets).score
    print(f"{name:9s} ({len(sets):2d} instances)  lower bound {lb:6.1f}   "
          f"first fit {ff:6.1f} (+{ff - lb:4.1f})   "
          f"best fit {bf:6.1f} (+{bf - lb:4.1f})")


# ── 3. The sampler: one chat request, one reply ──────────────────────────
def chat(system, user):
    body = {"model": args.model, "max_tokens": args.max_tokens,
            "temperature": args.temperature,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}]}
    req = urllib.request.Request(
        args.base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(body).encode(),
        headers={"content-type": "application/json",
                 "authorization": "Bearer " + args.api_key})
    with urllib.request.urlopen(req, timeout=300) as r:
        reply = json.loads(r.read())
    return reply["choices"][0]["message"]["content"]


SYSTEM = "You are an expert Python programmer. Reply with Python code only."
TASK = """\
Online bin packing. Bins hold 100 units. Items of size 20 to 60 arrive one
at a time. priority(item, rem) scores a bin that has rem units free; the
item goes into the feasible bin with the HIGHEST score. We want few bins.

Below are versions of priority, worst first, each with the mean number of
bins it used. Each is better than the one before. Write priority_v{k}: a
new version that should use fewer bins than the last one.

Rules: use only item, rem, numbers, + - * / // %, comparisons, if, abs,
min and max. No imports, no loops, no other functions.

{versions}

Reply with one Python code block that holds only the function
priority_v{k}(item, rem).
"""


def build_prompt(parents, scores):
    """Best-shot prompt (chapter 9): numbered versions, worst first."""
    shown = []
    for v, (src, score) in enumerate(zip(parents, scores)):
        body = src.replace("def priority(", f"def priority_v{v}(", 1)
        shown.append(f"# mean bins: {score:.1f}\n{body}")
    return TASK.format(k=len(parents), versions="\n".join(shown))


# ── 4. Turn a reply into a candidate (or say why not) ────────────────────
def extract(reply):
    """The first function named priority... in the reply, renamed to
    priority, docstring removed. Returns source text, or None."""
    fenced = re.findall(r"```(?:python)?\n(.*?)```", reply, re.S)
    code = fenced[0] if fenced else reply
    code = code[code.find("def priority"):] if "def priority" in code else ""
    lines = code.splitlines()
    for end in range(len(lines), 0, -1):        # longest prefix that parses
        try:
            tree = ast.parse("\n".join(lines[:end]))
        except SyntaxError:
            continue
        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                node.name = "priority"
                first = node.body[0]
                if (isinstance(first, ast.Expr)
                        and isinstance(first.value, ast.Constant)
                        and len(node.body) > 1):
                    node.body.pop(0)            # drop a docstring
                return ast.unparse(node)
        return None
    return None


# ── 5. The loop: sample, extract, evaluate, store ────────────────────────
rng = random.Random(args.seed)
seed_src = canonical(SEED_SRC)
seed_out = evaluate(seed_src, train)
db = Database(args.islands, seed_src, seed_out)
seen, tally, why = {seed_src}, Counter(), Counter()
better = 0                           # samples that beat best fit (search set)
log = open(args.log, "w")
t0 = time.time()
print(f"\n{args.calls} calls, {args.islands} islands, temperature "
      f"{args.temperature}; search-set best fit = {seed_out.score:.1f}")
for call in range(args.calls):
    isl = call % args.islands
    parents = db.islands[isl].sample(rng, args.shots)
    scores = [evaluate(p, train).score for p in parents]
    try:
        reply = chat(SYSTEM, build_prompt(parents, scores))
    except OSError as err:
        raise SystemExit(f"cannot reach the model server: {err}")
    src = extract(reply)
    if src is None:
        status, score = "no_code", None
    elif src in seen:
        status, score = "duplicate", None
    else:
        seen.add(src)
        out = evaluate(src, train)
        status, score = out.status, out.score if out.ok else None
        if not out.ok:
            why[out.detail.split(":")[0][:44]] += 1
        better += out.ok and out.score < seed_out.score
        db.islands[isl].add(src, out)
    tally[status] += 1
    log.write(json.dumps({"call": call, "island": isl, "status": status,
                          "score": score, "src": src,
                          "reply": reply[:600]}) + "\n")
    if (call + 1) % args.reseed_every == 0:
        db.reseed(rng)
    if (call + 1) % 10 == 0:
        print(f"  call {call + 1:3d}  best search score "
              f"{-db.best()[1]:6.2f}  {time.time() - t0:5.0f} s")
log.close()
print("outcomes of the model's samples:",
      ", ".join(f"{k} {v}" for k, v in sorted(tally.items())))
print("most common reasons a sample was refused or failed:")
for reason, n in why.most_common(4):
    print(f"  {n:3d}  {reason}")
print(f"samples that beat best fit on the search set: {better}")

# ── 6. Chapter 16: three sets. Finalists, then one winner, then test ─────
finalists = {}                       # best program of each island
for isl in db.islands:
    if isl.best():
        finalists[isl.best()[0]] = None
ranked = sorted(finalists, key=lambda p: evaluate(p, select).score)
winner = ranked[0]
print("\nfinalists on the selection set:")
for p in ranked:
    print(f"  {evaluate(p, select).score:6.2f}   "
          f"(search {evaluate(p, train).score:6.2f})   "
          f"{len(p):3d} chars{'   <- winner' if p == winner else ''}")
print("\nwinner:\n" + winner)

# The test set is touched once, for the winner and the two baselines.
lb = sum(map(lower_bound, test)) / len(test)
mine = evaluate(winner, test)
bf = evaluate(SEED_SRC, test)
ff = evaluate(FIRST_FIT_SRC, test)
print(f"\nheld-out test set (30 instances), lower bound {lb:.1f} bins:")
for name, o in (("first fit", ff), ("best fit", bf), ("evolved", mine)):
    print(f"  {name:10s} {o.score:6.2f} bins   +{o.score - lb:5.2f} over "
          f"the bound")
wins = sum(m < b for m, b in zip(mine.bins, bf.bins))
losses = sum(m > b for m, b in zip(mine.bins, bf.bins))
print(f"  against best fit, instance by instance: {wins} better, "
      f"{losses} worse, {len(test) - wins - losses} tied")
verdict = "beats" if mine.score < bf.score else "does not beat"
print(f"  the evolved program {verdict} best fit on held-out instances")
