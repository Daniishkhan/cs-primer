"""Speculative decoding, timed: Hugging Face assisted generation with a
small draft model, against chapter 21's expected-tokens formula.

Laptop (SmolLM2-135M drafts for SmolLM2-360M, about 0.7 GB in total):
    python spec_decode.py
GPU box (a 7B target, a 0.5B draft):
    python spec_decode.py --target Qwen/Qwen2.5-7B-Instruct \
        --draft Qwen/Qwen2.5-0.5B-Instruct --new 256

Needs: torch, transformers (workbench/requirements.txt)."""
import argparse
import time

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from transformers.generation import candidate_generator as cg

# ── 1. Settings ──────────────────────────────────────────────────────────
ap = argparse.ArgumentParser()
ap.add_argument("--target", default="HuggingFaceTB/SmolLM2-360M")
ap.add_argument("--draft", default="HuggingFaceTB/SmolLM2-135M")
ap.add_argument("--new", type=int, default=96)        # tokens per answer
ap.add_argument("--ks", default="1,2,4,8")            # draft lengths
ap.add_argument("--gpu-target-bytes", type=int, default=15231233024)
ap.add_argument("--gpu-draft-bytes", type=int, default=988097824)
ap.add_argument("--device", default="")               # cuda, mps or cpu
args, _ = ap.parse_known_args()        # notebooks pass their own flags

if torch.cuda.is_available():
    DEVICE, DTYPE = "cuda", torch.bfloat16
elif torch.backends.mps.is_available():
    DEVICE, DTYPE = "mps", torch.float32
else:
    DEVICE, DTYPE = "cpu", torch.float32
if args.device:                              # force, for example cpu
    DEVICE = args.device
    DTYPE = torch.bfloat16 if DEVICE == "cuda" else torch.float32

PROMPTS = [
    "The history of the printing press began in the fifteenth century,",
    "def fibonacci(n):\n    \"\"\"Return the n-th Fibonacci number.\"\"\"\n",
    "Q: What is the capital of France?\nA: Paris\n"
    "Q: What is the capital of Italy?\nA: Rome\n"
    "Q: What is the capital of Spain?\nA:",
]
tok = AutoTokenizer.from_pretrained(args.target)
target = AutoModelForCausalLM.from_pretrained(args.target, dtype=DTYPE)
draft = AutoModelForCausalLM.from_pretrained(args.draft, dtype=DTYPE)
target, draft = target.to(DEVICE).eval(), draft.to(DEVICE).eval()
print(f"target {args.target}, draft {args.draft}, {DEVICE}, {DTYPE}")


def sync():
    if DEVICE == "cuda":
        torch.cuda.synchronize()
    elif DEVICE == "mps":
        torch.mps.synchronize()


def nbytes(m):
    return sum(p.numel() * p.element_size() for p in m.parameters())


# ── 2. Count what the verifier decides, round by round ───────────────────
rounds = []                          # (tokens drafted, tokens accepted)
_orig = cg.AssistedCandidateGenerator.update_candidate_strategy


def spy(self, input_ids, scores, num_matches):
    rounds.append((scores[0].shape[0] - 1, num_matches))
    return _orig(self, input_ids, scores, num_matches)


cg.AssistedCandidateGenerator.update_candidate_strategy = spy


def generate(prompt, k=None, model=None):
    """Greedy answer; k=None is plain decoding, k=int speculates."""
    model = model or target
    ids = tok(prompt, return_tensors="pt").to(DEVICE)
    kw = dict(max_new_tokens=args.new, do_sample=False,
              pad_token_id=tok.eos_token_id, min_new_tokens=args.new)
    if k:
        g = draft.generation_config
        g.num_assistant_tokens, g.num_assistant_tokens_schedule = k, "constant"
        g.assistant_confidence_threshold = 0.0     # always draft k tokens
        kw["assistant_model"] = draft
    sync()
    start = time.perf_counter()
    with torch.no_grad():
        out = model.generate(**ids, **kw)
    sync()
    return out[0, ids["input_ids"].shape[1]:], time.perf_counter() - start


# ── 3. Plain decoding: the baseline, and the draft's relative cost c ─────
generate(PROMPTS[0])                                     # warm-up
generate(PROMPTS[0], 4)
generate(PROMPTS[0], model=draft)
plain = {p: generate(p) for p in PROMPTS}
t_plain = sum(t for _, t in plain.values()) / len(PROMPTS)
t_d = sum(generate(p, model=draft)[1] for p in PROMPTS) / len(PROMPTS)
c = t_d / t_plain                       # one draft step / one target step
print(f"\nplain decoding: {1000 * t_plain / args.new:.1f} ms per token on "
      f"the target, {1000 * t_d / args.new:.1f} on the draft")
print(f"c = {c:.2f}  (the weights alone say "
      f"{nbytes(draft) / nbytes(target):.2f})")



def verify_cost(n, reps=15):
    """Cost of one target pass over n new tokens, relative to one token:
    chapter 21 assumes this is 1 (decode is memory-bound)."""
    ids = tok(PROMPTS[0] * 8, return_tensors="pt").to(DEVICE)["input_ids"]
    ids = ids[:, :64]
    new = torch.randint(0, 1000, (1, n), device=DEVICE)
    times = []
    with torch.no_grad():
        past = target(ids, use_cache=True).past_key_values
        for _ in range(reps):
            sync()
            start = time.perf_counter()
            target(new, past_key_values=past, use_cache=True)
            sync()
            times.append(time.perf_counter() - start)
            past.crop(64)                  # forget the n new entries
    return sorted(times)[reps // 2]


one = verify_cost(1)
V = {k: verify_cost(k + 1) / one for k in (1, 2, 4, 8)}
print("verifying k+1 tokens in one pass costs, relative to 1 token: " +
      ", ".join(f"k={k}: {v:.2f}" for k, v in V.items()))

# ── 4. Speculate: measure acceptance, tokens per round and speed-up ──────
print(f"\n{'k':>3} {'alpha':>6} {'tok/round':>10} {'formula':>8} "
      f"{'speedup':>8} {'formula':>8} {'with v':>7} {'extra ms':>9}  same")
for k in [int(x) for x in args.ks.split(",")]:
    rounds.clear()
    t_spec, same = 0.0, True
    for p in PROMPTS:
        out, t = generate(p, k)
        t_spec += t / len(PROMPTS)
        same &= bool(torch.equal(out, plain[p][0]))
    accepted = sum(m for _, m in rounds)
    tested = sum(m + (m < d) for d, m in rounds)   # a miss is a test too
    alpha = accepted / tested                      # per-token acceptance
    per_round = sum(m + 1 for _, m in rounds) / len(rounds)
    formula = (1 - alpha ** (k + 1)) / (1 - alpha)     # chapter 21
    step = 1000 * t_plain / args.new                  # ms per target step
    round_ms = 1000 * t_spec / (len(rounds) / len(PROMPTS))
    extra = round_ms - step * (k * c + V.get(k, 1))   # not in the model
    print(f"{k:>3} {alpha:>6.2f} {per_round:>10.2f} {formula:>8.2f} "
          f"{t_plain / t_spec:>7.2f}x {formula / (1 + k * c):>7.2f}x "
          f"{formula / (k * c + V.get(k, 1)):>6.2f}x "
          f"{extra:>9.0f}  {same}")

# ── 5. The GPU case, on paper (nothing here ran on a GPU) ────────────────
c_bytes = args.gpu_draft_bytes / args.gpu_target_bytes
print(f"\nGPU prediction, k=4: draft/target weights = {c_bytes:.3f}")
cs = [("c=bytes", c_bytes), ("c=0.2", 0.2), ("c=0.4", 0.4)]
print(f"{'alpha':>6} {'E[tok]':>7}  " + "  ".join(f"{n:>8}" for n, _ in cs))
for a in (0.6, 0.7, 0.8, 0.9):
    e = (1 - a ** 5) / (1 - a)
    print(f"{a:>6.1f} {e:>7.2f}  " +
          "  ".join(f"{e / (1 + 4 * x):>7.2f}x" for _, x in cs))
