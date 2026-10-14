"""A tiny OpenAI-compatible server over Hugging Face transformers, with the
tool-call parsing that Ollama and vLLM do for you.

Use it when you have no Ollama: it speaks POST /v1/chat/completions, so the
workbench script, and lab-support/llm.py, point at it with --base-url.

    python serve_local.py --model Qwen/Qwen2.5-0.5B-Instruct --port 8765

Qwen2.5 writes a tool call as text, <tool_call>{"name": ..., "arguments":
{...}}</tool_call>. This server finds those blocks and turns the ones that
are valid JSON into a "tool_calls" field. Text that fails to parse stays in
"content".

Needs: torch, transformers (workbench/requirements.txt)."""
import argparse
import json
import re
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

# ── 1. Settings and model ────────────────────────────────────────────────
ap = argparse.ArgumentParser()
ap.add_argument("--model", default="Qwen/Qwen2.5-0.5B-Instruct")
ap.add_argument("--host", default="127.0.0.1")        # local only
ap.add_argument("--port", type=int, default=8765)
args, _ = ap.parse_known_args()

if torch.cuda.is_available():
    DEVICE, DTYPE = "cuda", torch.bfloat16
elif torch.backends.mps.is_available():
    DEVICE, DTYPE = "mps", torch.float16
else:
    DEVICE, DTYPE = "cpu", torch.float32
tok = AutoTokenizer.from_pretrained(args.model)
model = AutoModelForCausalLM.from_pretrained(args.model, dtype=DTYPE)
model = model.to(DEVICE).eval()
LOCK = threading.Lock()                  # one generation at a time
TOOL_BLOCK = re.compile(r"<tool_call>\s*(.*?)\s*</tool_call>", re.S)


# ── 2. One chat completion ───────────────────────────────────────────────
def fix_history(messages):
    """The template wants tool-call arguments as objects, not JSON text."""
    out = []
    for m in messages:
        m = dict(m)
        m["content"] = m.get("content") or ""
        for tc in m.get("tool_calls") or []:
            fn = tc["function"]
            if isinstance(fn["arguments"], str):
                fn["arguments"] = json.loads(fn["arguments"] or "{}")
        out.append(m)
    return out


def parse_tool_calls(text):
    """Return (content, tool_calls). Invalid JSON is left in content."""
    calls, rest = [], text
    for raw in TOOL_BLOCK.findall(text):
        try:
            obj = json.loads(raw)
            args_json = json.dumps(obj.get("arguments", {}))
            calls.append({
                "id": "call_" + uuid.uuid4().hex[:8], "type": "function",
                "function": {"name": obj["name"], "arguments": args_json}})
            rest = rest.replace(raw, "")
        except (ValueError, KeyError, TypeError):
            pass                                  # keep it as plain text
    if calls:
        rest = TOOL_BLOCK.sub("", rest)
    return rest.strip(), calls


def complete(body):
    msgs = fix_history(body["messages"])
    prompt = tok.apply_chat_template(
        msgs, tools=body.get("tools") or None, add_generation_prompt=True,
        tokenize=False)
    ids = tok(prompt, return_tensors="pt").input_ids.to(DEVICE)
    temp = body.get("temperature", 0.0) or 0.0
    limit = body.get("max_tokens") or 512
    with LOCK, torch.no_grad():
        out = model.generate(
            ids, max_new_tokens=limit, do_sample=temp > 0,
            temperature=temp if temp > 0 else None, top_p=None, top_k=None,
            pad_token_id=tok.eos_token_id)
    new = out[0, ids.shape[1]:]
    text = tok.decode(new, skip_special_tokens=True)
    content, calls = parse_tool_calls(text)
    finish = ("tool_calls" if calls else
              "length" if len(new) >= limit else "stop")
    msg = {"role": "assistant", "content": content or None}
    if calls:
        msg["tool_calls"] = calls
    return {"id": "chatcmpl-" + uuid.uuid4().hex[:8], "object":
            "chat.completion", "model": args.model,
            "choices": [{"index": 0, "message": msg,
                         "finish_reason": finish}],
            "usage": {"prompt_tokens": ids.shape[1],
                      "completion_tokens": len(new),
                      "total_tokens": ids.shape[1] + len(new)}}


# ── 3. The HTTP layer ────────────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        size = int(self.headers.get("content-length", 0))
        try:
            reply = complete(json.loads(self.rfile.read(size)))
            code = 200
        except Exception as e:                   # report, keep serving
            reply, code = {"error": {"message": repr(e)}}, 500
        data = json.dumps(reply).encode()
        self.send_response(code)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):                            # /v1/models, /health
        data = json.dumps({"data": [{"id": args.model}]}).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


print(f"serving {args.model} on {DEVICE} at "
      f"http://{args.host}:{args.port}/v1", flush=True)
ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()
