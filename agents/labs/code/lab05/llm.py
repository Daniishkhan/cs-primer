"""llm.py: one small interface for "a language model", shared by the Zero to AI
Systems labs. Every lab that talks to a model copies this exact file next to its
starter.py, so the lab folder stays self-contained.

Why: labs must run offline, for free, and give the same result every time, so
check.py always uses a *scripted* model whose replies are fixed in advance. The
same code also runs against a real model when you want to see the idea live.

    from llm import ScriptedModel, RuleModel, get_model, text_of, tool_calls

The message format follows the common "content blocks" shape:

    {"role": "user", "content": "plain text"}
    {"role": "assistant", "content": [{"type": "text", "text": "..."},
                                      {"type": "tool_use", "id": "t1", "name": "search",
                                       "input": {"q": "..."}}]}
    {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t1",
                                  "content": "...", "is_error": False}]}

A tool definition is {"name", "description", "input_schema" (JSON Schema)}.

Real models (optional, never used by check.py):
    LAB_MODEL=anthropic:<model-id>   needs ANTHROPIC_API_KEY
    LAB_MODEL=openai:<model-id>      needs OPENAI_API_KEY; OPENAI_BASE_URL for any
                                     OpenAI-compatible server (Ollama, vLLM, LM Studio)
    LAB_MODEL=ollama:<model-name>    shortcut for a local Ollama server
Standard library only. Python 3.9+.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Union

Block = Dict[str, Any]
Message = Dict[str, Any]

__all__ = [
    "Response", "Model", "ScriptedModel", "RuleModel", "RecordedModel", "Recorder",
    "RealModel", "get_model", "count_tokens", "text_of", "tool_calls", "text",
    "tool_use", "tool_result", "message_text",
]


# ---------------------------------------------------------------- data types

@dataclass
class Response:
    """What a model returns: content blocks, why it stopped, and token usage."""
    content: List[Block]
    stop_reason: str = "end_turn"          # "end_turn" | "tool_use" | "max_tokens"
    usage: Dict[str, int] = field(default_factory=lambda: {"input_tokens": 0, "output_tokens": 0})
    model: str = "scripted"

    def as_message(self) -> Message:
        """The assistant message to append to the conversation."""
        return {"role": "assistant", "content": list(self.content)}


def text(s: str) -> Block:
    return {"type": "text", "text": s}


def tool_use(name: str, input: Dict[str, Any], id: Optional[str] = None) -> Block:
    if id is None:
        id = "toolu_" + hashlib.sha1((name + json.dumps(input, sort_keys=True)).encode()).hexdigest()[:10]
    return {"type": "tool_use", "id": id, "name": name, "input": input}


def tool_result(tool_use_id: str, content: str, is_error: bool = False) -> Block:
    return {"type": "tool_result", "tool_use_id": tool_use_id, "content": content, "is_error": is_error}


def text_of(resp: Union[Response, Message]) -> str:
    """All text blocks of a response or message, joined."""
    blocks = resp.content if isinstance(resp, Response) else resp.get("content", "")
    if isinstance(blocks, str):
        return blocks
    return "".join(b.get("text", "") for b in blocks if b.get("type") == "text")


def tool_calls(resp: Response) -> List[Block]:
    return [b for b in resp.content if b.get("type") == "tool_use"]


def message_text(msg: Message) -> str:
    """Every piece of text in a message, including tool results (for token counts and rules)."""
    c = msg.get("content", "")
    if isinstance(c, str):
        return c
    out = []
    for b in c:
        if b.get("type") == "text":
            out.append(b["text"])
        elif b.get("type") == "tool_result":
            r = b.get("content", "")
            out.append(r if isinstance(r, str) else json.dumps(r))
        elif b.get("type") == "tool_use":
            out.append(json.dumps(b.get("input", {})))
    return "\n".join(out)


def count_tokens(s: str) -> int:
    """A deterministic stand-in for a tokeniser: about four characters per token.
    Real tokenisers differ by model; labs only need a consistent, monotone count."""
    return 0 if not s else math.ceil(len(s) / 4)


def _usage(messages: Sequence[Message], system: Optional[str], tools: Optional[Sequence[dict]], content: List[Block]) -> Dict[str, int]:
    inp = count_tokens(system or "") + sum(count_tokens(message_text(m)) for m in messages)
    inp += sum(count_tokens(json.dumps(t, sort_keys=True)) for t in (tools or []))
    out = count_tokens(message_text({"content": content}))
    return {"input_tokens": inp, "output_tokens": out}


# ---------------------------------------------------------------- the interface

class Model:
    """Anything with complete(...) -> Response is a model. Subclasses below."""
    name = "model"

    def complete(self, messages: Sequence[Message], *, system: Optional[str] = None,
                 tools: Optional[Sequence[dict]] = None, max_tokens: int = 1024,
                 temperature: float = 0.0) -> Response:
        raise NotImplementedError


def _coerce(reply: Any) -> Response:
    """Let scripts be written tersely: a str, a block, a list of blocks or a Response."""
    if isinstance(reply, Response):
        return reply
    if isinstance(reply, str):
        blocks = [text(reply)]
    elif isinstance(reply, dict):
        blocks = [reply]
    else:
        blocks = list(reply)
    stop = "tool_use" if any(b.get("type") == "tool_use" for b in blocks) else "end_turn"
    return Response(content=blocks, stop_reason=stop)


class ScriptedModel(Model):
    """Replies from a fixed script, in order, or from a function of the request.

    ScriptedModel(["first reply", [tool_use("search", {"q": "x"})], "done"])
    ScriptedModel(lambda messages, tools, system: "reply")

    Every request is kept in .calls so a test can inspect exactly what was sent.
    """
    name = "scripted"

    def __init__(self, script: Union[Sequence[Any], Callable[..., Any]]):
        self.script = script
        self.calls: List[Dict[str, Any]] = []
        self._i = 0

    def complete(self, messages, *, system=None, tools=None, max_tokens=1024, temperature=0.0):
        self.calls.append({"messages": [dict(m) for m in messages], "system": system,
                           "tools": list(tools or []), "max_tokens": max_tokens})
        if callable(self.script):
            reply = self.script(messages, tools, system)
        else:
            if self._i >= len(self.script):
                raise RuntimeError(f"ScriptedModel ran out of replies after {self._i} calls")
            reply = self.script[self._i]
            self._i += 1
        resp = _coerce(reply)
        resp.usage = _usage(messages, system, tools, resp.content)
        if count_tokens(message_text({"content": resp.content})) > max_tokens:
            resp.stop_reason = "max_tokens"
        return resp


class RuleModel(Model):
    """A tiny deterministic 'model' made of (pattern, reply) rules over the latest
    message's text. The first matching regex wins; reply may be a function of the
    match. Good for stand-ins that must respond sensibly to many inputs."""
    name = "rules"

    def __init__(self, rules: Sequence[tuple], default: Any = "I don't know."):
        self.rules = [(re.compile(p, re.I | re.S), r) for p, r in rules]
        self.default = default
        self.calls: List[Dict[str, Any]] = []

    def complete(self, messages, *, system=None, tools=None, max_tokens=1024, temperature=0.0):
        self.calls.append({"messages": [dict(m) for m in messages], "system": system, "tools": list(tools or [])})
        last = message_text(messages[-1]) if messages else ""
        reply: Any = self.default
        for pat, r in self.rules:
            m = pat.search(last)
            if m:
                reply = r(m) if callable(r) else r
                break
        resp = _coerce(reply)
        resp.usage = _usage(messages, system, tools, resp.content)
        resp.model = self.name
        return resp


def _key(messages, system, tools) -> str:
    raw = json.dumps({"m": messages, "s": system, "t": tools}, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


class RecordedModel(Model):
    """Replays responses saved by Recorder, keyed by a hash of the request."""
    name = "recorded"

    def __init__(self, path: str):
        self.path = path
        self.table: Dict[str, dict] = {}
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    row = json.loads(line)
                    self.table[row["key"]] = row["response"]

    def complete(self, messages, *, system=None, tools=None, max_tokens=1024, temperature=0.0):
        k = _key(messages, system, tools)
        if k not in self.table:
            raise KeyError(f"no recorded response for this request (key {k}); re-record it")
        r = self.table[k]
        return Response(content=r["content"], stop_reason=r["stop_reason"], usage=r["usage"], model=r.get("model", "recorded"))


class Recorder(Model):
    """Wraps any model and appends every request/response pair to a JSONL file."""

    def __init__(self, inner: Model, path: str):
        self.inner, self.path = inner, path
        self.name = "recorder(" + inner.name + ")"

    def complete(self, messages, *, system=None, tools=None, max_tokens=1024, temperature=0.0):
        resp = self.inner.complete(messages, system=system, tools=tools, max_tokens=max_tokens, temperature=temperature)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"key": _key(messages, system, tools), "response": {
                "content": resp.content, "stop_reason": resp.stop_reason, "usage": resp.usage, "model": resp.model}}) + "\n")
        return resp


# ---------------------------------------------------------------- real models (optional)

class RealModel(Model):
    """A real provider over HTTPS with urllib. Never used by check.py."""

    def __init__(self, provider: str, model: str, timeout: float = 120.0):
        self.provider, self.model, self.timeout = provider, model, timeout
        self.name = f"{provider}:{model}"

    def _post(self, url: str, headers: Dict[str, str], body: dict) -> dict:
        req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"content-type": "application/json", **headers})
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            return json.loads(r.read())

    def complete(self, messages, *, system=None, tools=None, max_tokens=1024, temperature=0.0):
        if self.provider == "anthropic":
            key = os.environ["ANTHROPIC_API_KEY"]
            body = {"model": self.model, "max_tokens": max_tokens, "temperature": temperature, "messages": list(messages)}
            if system:
                body["system"] = system
            if tools:
                body["tools"] = list(tools)
            d = self._post("https://api.anthropic.com/v1/messages",
                           {"x-api-key": key, "anthropic-version": "2023-06-01"}, body)
            return Response(content=d["content"], stop_reason=d.get("stop_reason", "end_turn"),
                            usage={"input_tokens": d["usage"]["input_tokens"], "output_tokens": d["usage"]["output_tokens"]},
                            model=d.get("model", self.model))
        # OpenAI-compatible chat completions (OpenAI, Ollama, vLLM, LM Studio ...)
        base = os.environ.get("OPENAI_BASE_URL", "http://localhost:11434/v1" if self.provider == "ollama" else "https://api.openai.com/v1")
        key = os.environ.get("OPENAI_API_KEY", "ollama")
        msgs: List[dict] = [{"role": "system", "content": system}] if system else []
        for m in messages:
            c = m["content"]
            if isinstance(c, str):
                msgs.append({"role": m["role"], "content": c})
                continue
            calls = [b for b in c if b.get("type") == "tool_use"]
            results = [b for b in c if b.get("type") == "tool_result"]
            for r in results:
                msgs.append({"role": "tool", "tool_call_id": r["tool_use_id"], "content": r["content"] if isinstance(r["content"], str) else json.dumps(r["content"])})
            words = "".join(b.get("text", "") for b in c if b.get("type") == "text")
            if calls:
                msgs.append({"role": "assistant", "content": words or None, "tool_calls": [
                    {"id": b["id"], "type": "function", "function": {"name": b["name"], "arguments": json.dumps(b["input"])}} for b in calls]})
            elif words:
                msgs.append({"role": m["role"], "content": words})
        body = {"model": self.model, "messages": msgs, "max_tokens": max_tokens, "temperature": temperature}
        if tools:
            body["tools"] = [{"type": "function", "function": {"name": t["name"], "description": t.get("description", ""),
                                                               "parameters": t.get("input_schema", {"type": "object"})}} for t in tools]
        d = self._post(base.rstrip("/") + "/chat/completions", {"authorization": "Bearer " + key}, body)
        ch = d["choices"][0]
        msg = ch["message"]
        blocks: List[Block] = [text(msg["content"])] if msg.get("content") else []
        for tc in msg.get("tool_calls") or []:
            blocks.append({"type": "tool_use", "id": tc["id"], "name": tc["function"]["name"],
                           "input": json.loads(tc["function"]["arguments"] or "{}")})
        stop = {"tool_calls": "tool_use", "length": "max_tokens"}.get(ch.get("finish_reason"), "end_turn")
        u = d.get("usage") or {}
        return Response(content=blocks, stop_reason=stop, model=d.get("model", self.model),
                        usage={"input_tokens": u.get("prompt_tokens", 0), "output_tokens": u.get("completion_tokens", 0)})


def get_model(default: Optional[Model] = None) -> Model:
    """The model named by $LAB_MODEL ("anthropic:<id>", "openai:<id>", "ollama:<name>"),
    or `default` (usually a ScriptedModel) when the variable is unset."""
    spec = os.environ.get("LAB_MODEL", "").strip()
    if not spec:
        if default is None:
            raise RuntimeError("set LAB_MODEL (e.g. anthropic:<model-id>) or pass a default model")
        return default
    provider, _, model = spec.partition(":")
    if provider not in ("anthropic", "openai", "ollama") or not model:
        raise ValueError(f"LAB_MODEL={spec!r}: expected anthropic:<id>, openai:<id> or ollama:<name>")
    return RealModel(provider, model)


if __name__ == "__main__":
    m = ScriptedModel([[tool_use("add", {"a": 2, "b": 3})], "The answer is 5."])
    msgs: List[Message] = [{"role": "user", "content": "What is 2 + 3?"}]
    r = m.complete(msgs, tools=[{"name": "add", "description": "Add two numbers.", "input_schema": {"type": "object"}}])
    print(r.stop_reason, tool_calls(r)[0]["name"], tool_calls(r)[0]["input"], r.usage)
    msgs += [r.as_message(), {"role": "user", "content": [tool_result(tool_calls(r)[0]["id"], "5")]}]
    r = m.complete(msgs)
    print(r.stop_reason, text_of(r), r.usage)
