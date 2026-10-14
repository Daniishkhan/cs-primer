"""A real judge, calibrated: a small local model grades evals lab 2's
200 labelled answers; measure agreement with the humans, Cohen's kappa with
an interval, and position bias with the swap test.

With Ollama (ollama pull qwen2.5:1.5b), from this folder:
    python real_judge.py --model qwen2.5:1.5b
Without Ollama: transformers can serve the same API (any OpenAI-compatible
server works), for example
    transformers serve Qwen/Qwen2.5-1.5B-Instruct --port 8766
    python real_judge.py --base-url http://127.0.0.1:8766/v1 \
        --model Qwen/Qwen2.5-1.5B-Instruct

Needs: lab 2's labelled.jsonl and judge_data.json (evals/labs/code/lab02).
Standard library only."""
import argparse
import json
import math
import random
import re
import sys
import urllib.request
from collections import defaultdict
from pathlib import Path

sys.dont_write_bytecode = True      # keep the lab folder clean

# ── 1. Settings ──────────────────────────────────────────────────────────
try:
    LAB = Path(__file__).resolve().parents[3] / "labs/code/lab02"
except NameError:                              # running as a notebook
    LAB = Path("../../../labs/code/lab02").resolve()
ap = argparse.ArgumentParser()
ap.add_argument("--base-url", default="http://localhost:11434/v1")
ap.add_argument("--model", default="qwen2.5:1.5b")
ap.add_argument("--lab", default=str(LAB))
ap.add_argument("--split", default="test",
                choices=["dev", "test", "all"])   # even pairs dev, odd test
ap.add_argument("--rubric", type=int, default=2, choices=[1, 2])
ap.add_argument("--errors", type=int, default=0)  # print N disagreements
ap.add_argument("--quick", action="store_true")   # reference grading only
ap.add_argument("--boot", type=int, default=2000)  # bootstrap resamples
args, _ = ap.parse_known_args()    # notebooks pass their own flags
LAB = Path(args.lab)


def ask(prompt, words):
    """One greedy reply from the model; return the first of `words` in it."""
    body = {"model": args.model, "temperature": 0, "max_tokens": 6,
            "messages": [{"role": "user", "content": prompt}]}
    req = urllib.request.Request(
        args.base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(body).encode(), headers={
            "content-type": "application/json",
            "authorization": "Bearer ollama"})
    with urllib.request.urlopen(req, timeout=120) as r:
        said = json.loads(r.read())["choices"][0]["message"]["content"]
    hit = re.search(r"\b(" + "|".join(words) + r")\b", said or "", re.I)
    return hit.group(1).upper() if hit else None     # None: not an answer


# ── 2. The data, and a reference rebuilt from the human PASS answers ─────
FILLER = json.load(open(LAB / "judge_data.json"))["filler"]
rows = [json.loads(line) for line in open(LAB / "labelled.jsonl")]


def figure(answer):
    """The one number an answer states, once filler sentences are removed."""
    for sentence in FILLER + ["Good question."]:
        answer = answer.replace(sentence, "")
    return re.findall(r"\d[\d,]*", answer)[0]


pairs = defaultdict(list)                 # "L0000" -> its two answers
for r in rows:
    pairs[r["id"][:-1]].append(r)
pairs = list(pairs.values())
if args.split != "all":                    # dev: write the rubric on this
    pairs = pairs[args.split == "test"::2]  # test: look once, at the end
for p in pairs:       # the lab data has no policy text: use the PASS figure
    good = {figure(r["answer"]) for r in p if r["human"] == "PASS"}
    p.append(good.pop() if len(good) == 1 else None)        # reference
items = [(r, p[2]) for p in pairs for r in p[:2]]
print(f"split {args.split}, rubric {args.rubric}: "
      f"{len(items)} answers in {len(pairs)} pairs; "
      f"{sum(p[2] is not None for p in pairs)} pairs have a reference")

# ── 3. The judge: a binary rubric, with and without the reference ────────
RUBRICS = {1: ("You grade answers from a customer-support assistant.\n"
               "Question: {q}\n{ref}Answer: {a}\n\n"
               "Does the answer state the correct figure? "
               "Reply with one word: PASS or FAIL."),
           2: ("You grade answers from a customer-support assistant.\n"
               "Question: {q}\n{ref}Answer: {a}\n\n"
               "Find the figure the answer gives. If it is exactly the "
               "correct figure, reply PASS. If it is any other number, "
               "reply FAIL. Reply with one word: PASS or FAIL.")}
REF = "The correct figure is {n}.\n"


def judge(row, ref):
    prompt = RUBRICS[args.rubric].format(q=row["question"], a=row["answer"],
                           ref=REF.format(n=ref) if ref else "")
    return ask(prompt, ["PASS", "FAIL"]) or "FAIL"   # unparsed counts FAIL


# ── 4. Agreement with the humans (chapters 3 and 4, 5) ───────────────────
def wilson(k, n, z=1.96):
    """95% interval for a proportion that behaves at the edges."""
    if n == 0:
        return (float("nan"),) * 2
    p, d = k / n, 1 + z * z / n
    mid = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, mid - half), min(1.0, mid + half)


def kappa(h, j):
    """Chapter 5's eq-kappa: (po - pe) / (1 - pe)."""
    n = len(h)
    po = sum(a == b for a, b in zip(h, j)) / n
    ph, pj = sum(a == "PASS" for a in h) / n, sum(b == "PASS" for b in j) / n
    pe = ph * pj + (1 - ph) * (1 - pj)
    return (po - pe) / (1 - pe) if pe < 1 else 0.0


def report(name, human, judged, groups, subset=None):
    tp = sum(h == j == "PASS" for h, j in zip(human, judged))
    tn = sum(h == j == "FAIL" for h, j in zip(human, judged))
    pos, neg = human.count("PASS"), human.count("FAIL")
    print(f"\n{name} ({len(human)} answers, judge says PASS "
          f"{judged.count('PASS') / len(judged):.0%})")
    for label, k, n in (("TPR", tp, pos), ("TNR", tn, neg),
                        ("accuracy", tp + tn, len(human))):
        lo, hi = wilson(k, n)
        print(f"  {label:<8} {k:>3}/{n:<3} = {k / n:5.1%}  "
              f"95% CI {lo:5.1%} to {hi:5.1%}")
    rng, ks = random.Random(0), []
    for _ in range(args.boot):        # resample whole pairs, not answers
        pick = [i for g in rng.choices(groups, k=len(groups)) for i in g]
        ks.append(kappa([human[i] for i in pick], [judged[i] for i in pick]))
    ks.sort()
    print(f"  kappa    {kappa(human, judged):.2f}  95% CI "
          f"{ks[int(.025 * len(ks))]:.2f} to {ks[int(.975 * len(ks))]:.2f}"
          f"  (bootstrap over {len(groups)} pairs)")

    misses = [(r, ref, h, j) for (r, ref), h, j in
              zip(subset or [], human, judged) if h != j]
    for r, ref, h, j in misses[:args.errors]:      # read the disagreements
        print(f"  miss: human {h}, judge {j}: figure {figure(r['answer'])}"
              f" vs reference {ref} | {r['answer'][:30]}")


def groups_of(subset):
    """Answers that share a question are one cluster (chapter 4)."""
    by = defaultdict(list)
    for i, (r, _) in enumerate(subset):
        by[r["id"][:-1]].append(i)
    return list(by.values())


def lab_standin(subset):
    sys.path.insert(0, str(LAB))
    import judge as standin                       # the lab's fake judge
    return [standin.judge_single(r["question"], r["answer"])
            for r, _ in subset]


with_ref = [it for it in items if it[1]]
for name, subset, use_ref in (
        ("model, WITH the reference", with_ref, True),
        ("model, WITHOUT a reference", items, False))[:1 if args.quick else 2]:
    verdicts = [judge(r, ref if use_ref else None) for r, ref in subset]
    report(name, [r["human"] for r, _ in subset], verdicts,
           groups_of(subset), subset)
if args.quick:
    sys.exit()
report("lab 2 stand-in judge, same answers as the first block",
       [r["human"] for r, _ in with_ref], lab_standin(with_ref),
       groups_of(with_ref))

# ── 5. Position bias: the swap test on pairs with one PASS, one FAIL ─────
SWAP = ("Question: {q}\nThe correct figure is {n}.\n\n"
        "Answer A: {a}\n\nAnswer B: {b}\n\n"
        "Which answer states the correct figure? Reply with one letter: "
        "A or B.")
SWAP_BLIND = SWAP.replace("The correct figure is {n}.\n", "")
mixed = [p for p in pairs if {r["human"] for r in p[:2]} == {"PASS", "FAIL"}]
print(f"\nswap test on {len(mixed)} pairs with exactly one correct answer")
for name, tmpl in (("WITH the reference", SWAP),
                   ("WITHOUT a reference", SWAP_BLIND)):
    first = right_first = right_second = consistent = wins = 0
    for p in mixed:
        good = [r for r in p[:2] if r["human"] == "PASS"][0]
        bad = [r for r in p[:2] if r["human"] == "FAIL"][0]
        pick = {}
        for order, (a, b) in (("good first", (good, bad)),
                              ("good second", (bad, good))):
            pick[order] = ask(tmpl.format(q=good["question"], n=p[2],
                                          a=a["answer"], b=b["answer"]),
                              ["A", "B"])
        first += (pick["good first"] == "A") + (pick["good second"] == "A")
        right_first += pick["good first"] == "A"
        right_second += pick["good second"] == "B"
        same = (pick["good first"] == "A") == (pick["good second"] == "B")
        consistent += same
        wins += same and pick["good first"] == "A"
    n = len(mixed)
    print(f"  {name}:")
    print(f"    picks slot A in {first / (2 * n):.0%} of {2 * n} verdicts "
          f"(no bias: 50%)")
    print(f"    right when the good answer is first {right_first}/{n}, "
          f"second {right_second}/{n}")
    print(f"    same answer in both orders {consistent}/{n}; "
          f"counted as correct {wins}/{n} = {wins / n:.0%}")
