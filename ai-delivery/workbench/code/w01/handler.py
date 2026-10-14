"""A RunPod Serverless worker that answers a prompt with a small model.

Test it on your laptop, with no cloud account:
    python handler.py --test_input '{"input": {"prompt": "Say hi"}}'
Or serve the same handler on http://localhost:8000 and call /runsync:
    python handler.py --rp_serve_api
On RunPod the container runs `python -u handler.py` and the platform sends
jobs to it. Choose the model with the MODEL environment variable, and
set DEVICE=cpu to ignore a laptop GPU.

Needs: runpod, torch, transformers (requirements.txt)."""
import os
import time

# ── 1. Start-up work: this is the cold start (runs once per worker) ──────
T0 = time.perf_counter()
import runpod                                           # noqa: E402
import torch                                            # noqa: E402
from transformers import AutoModelForCausalLM, AutoTokenizer  # noqa: E402

T_IMPORT = time.perf_counter() - T0                     # libraries

MODEL = os.environ.get("MODEL", "HuggingFaceTB/SmolLM2-135M-Instruct")
if torch.cuda.is_available():
    DEVICE, DTYPE = "cuda", torch.bfloat16
elif torch.backends.mps.is_available():
    DEVICE, DTYPE = "mps", torch.float16
else:
    DEVICE, DTYPE = "cpu", torch.float32
if os.environ.get("DEVICE") == "cpu":                   # force the CPU
    DEVICE, DTYPE = "cpu", torch.float32

T1 = time.perf_counter()
tok = AutoTokenizer.from_pretrained(MODEL)
model = AutoModelForCausalLM.from_pretrained(MODEL, dtype=DTYPE)
model = model.to(DEVICE).eval()
T_LOAD = time.perf_counter() - T1                       # weights to memory

T2 = time.perf_counter()
with torch.no_grad():                                   # first forward pass
    model(**tok("warm up", return_tensors="pt").to(DEVICE))
T_WARM = time.perf_counter() - T2                       # kernels, caches

JOBS = 0                                                # jobs seen so far


# ── 2. The handler: runs once per job, on a worker that is already warm ──
def handler(job):
    global JOBS
    JOBS += 1
    job_input = job["input"]                            # what the client sent
    prompt = job_input.get("prompt")
    if not prompt:                                      # a clear failure
        return {"error": "input.prompt is required"}
    max_tokens = min(int(job_input.get("max_tokens", 32)), 256)

    start = time.perf_counter()
    text = tok.apply_chat_template(
        [{"role": "user", "content": prompt}],
        add_generation_prompt=True, tokenize=False)
    ids = tok(text, return_tensors="pt").to(DEVICE)
    with torch.no_grad():
        out = model.generate(**ids, max_new_tokens=max_tokens,
                             do_sample=False,
                             pad_token_id=tok.eos_token_id)
    new = out[0, ids["input_ids"].shape[1]:]
    return {
        "text": tok.decode(new, skip_special_tokens=True),
        "tokens": int(new.shape[0]),
        "gen_ms": round(1000 * (time.perf_counter() - start), 1),
        "job_number": JOBS,                             # 1 = first job
        "start_up_s": {"import": round(T_IMPORT, 2),
                       "load": round(T_LOAD, 2),
                       "warm_up": round(T_WARM, 2)},
        "device": DEVICE,
    }


# ── 3. Hand the handler to the RunPod SDK ────────────────────────────────
runpod.serverless.start({"handler": handler})
