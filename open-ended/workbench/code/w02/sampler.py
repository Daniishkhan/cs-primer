"""sampler.py: ask an OpenAI-compatible server for a new priority().

This is Workbench 1's sections 3 and 4 (chat, the best-shot prompt and
extract) turned into functions, so that many threads can call them at once.
Standard library only.
"""
import ast
import json
import re
import urllib.request

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


def chat(base_url, model, user, temperature=0.8, max_tokens=300,
         api_key="none", timeout=600):
    """One chat request. Returns (reply text, usage dict). Each call opens
    its own connection, so any number of threads can call it at once."""
    body = {"model": model, "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "system", "content": SYSTEM},
                         {"role": "user", "content": user}]}
    req = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(body).encode(),
        headers={"content-type": "application/json",
                 "authorization": "Bearer " + api_key})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        reply = json.loads(r.read())
    return reply["choices"][0]["message"]["content"], reply.get("usage", {})


def build_prompt(parents, scores):
    """Best-shot prompt (chapter 9): numbered versions, worst first."""
    shown = []
    for v, (src, score) in enumerate(zip(parents, scores)):
        body = src.replace("def priority(", f"def priority_v{v}(", 1)
        shown.append(f"# mean bins: {score:.1f}\n{body}")
    return TASK.format(k=len(parents), versions="\n".join(shown))


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
