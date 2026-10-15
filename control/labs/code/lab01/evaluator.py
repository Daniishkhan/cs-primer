"""The evaluator: a separate process with its own code, data and key.

    echo '{"task": "t1000", "source": "...", "seq": 0}' | python3 evaluator.py

The signing key arrives in the EVAL_KEY environment variable, as hex, and
goes no further: the candidate runs in a grandchild process with an empty
environment. The grandchild is untrusted. It is given inputs only, never
the expected answers, so what it prints is data to compare, not a verdict.
Timing is measured here, from outside, as the wall time of the whole run.

It signs with its own few lines (not the learner's code) so that the two
sides can only agree if both follow the contract in labcore.py. Reply:

    {"envelope": {...signed...}, "diagnostics": {"stdout": "..."}}

Diagnostics are for humans and are never signed or trusted.
"""
import hashlib
import hmac
import json
import os
import subprocess
import sys

import labcore

# The grandchild: reads {"source", "inputs"}, prints one JSON line.
RUNNER = r'''
import io, json, sys
req = json.loads(sys.stdin.read())
real, buf = sys.stdout, io.StringIO()
sys.stdout = buf
res = []
try:
    ns = {}
    exec(req["source"], ns)
    for x in req["inputs"]:
        try:
            out = ns["solve"](x)
            json.dumps(out)
            res.append(["ok", out])
        except Exception as e:
            res.append(["err", type(e).__name__])
except BaseException as e:
    res = [["err", type(e).__name__]] * len(req["inputs"])
sys.stdout = real
print(json.dumps({"results": res, "stdout": buf.getvalue()[:300]}))
'''


def evaluate(task, source):
    tests = task.visible + task.hidden
    allowance = len(tests) * task.limit_s + 0.12   # startup slack
    req = json.dumps({"source": source, "inputs": [t[0] for t in tests]})
    try:
        proc = subprocess.run(
            [sys.executable, "-I", "-c", RUNNER], input=req, env={},
            capture_output=True, text=True, timeout=allowance)
    except subprocess.TimeoutExpired:
        return 0, len(tests), "timeout", ""
    try:
        reply = json.loads(proc.stdout.strip().splitlines()[-1])
        results = reply["results"]
    except Exception:
        return 0, len(tests), "error", proc.stdout[:300]
    passed, reason = 0, "ok"
    for (inp, want), (status, got) in zip(tests, results):
        if status == "ok" and type(got) is type(want) and got == want:
            passed += 1
        else:
            reason = "wrong_answer"
    return passed, len(tests), reason, reply.get("stdout", "")


def sign(key, tool, seq, payload):
    digest = labcore.sha256_hex(labcore.canonical(payload))
    msg = f"{tool}|{seq}|{digest}".encode()
    sig = hmac.new(key, msg, hashlib.sha256).hexdigest()
    return {"v": 1, "tool": tool, "seq": seq, "payload": payload,
            "sha256": digest, "sig": sig}


def main():
    key = bytes.fromhex(os.environ["EVAL_KEY"])
    req = json.loads(sys.stdin.read())
    task = labcore.Task(int(req["task"][1:]))
    passed, total, reason, out = evaluate(task, req["source"])
    payload = {
        "kind": "test_result", "task": task.task_id,
        "solution_sha256": labcore.sha256_hex(req["source"].encode()),
        "passed": passed, "total": total,
        "verdict": "pass" if passed == total else "fail",
        "reason": reason,
    }
    print(json.dumps({"envelope": sign(key, "evaluate", req["seq"], payload),
                      "diagnostics": {"stdout": out}}))


if __name__ == "__main__":
    main()
