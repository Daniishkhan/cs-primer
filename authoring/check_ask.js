/* Checks assets/js/ask.js without a browser: the request each provider
   builds, the line-by-line stream parsing, and the Markdown renderer.

     node authoring/check_ask.js                          offline checks
     OPENAI_API_KEY=… node authoring/check_ask.js --live  also streams one real answer
                                                          (ASK_MODEL picks the model)

   The live check reads the key from the environment only; it is never read
   from, or written to, a file. Prints ✔/✘ per check and a summary line;
   exit status 1 on any ✘.
*/
"use strict";
const path = require("path");
const ask = require(path.join(__dirname, "..", "assets", "js", "ask.js"));

let passed = 0, failed = 0;
function check(name, fn) {
  return Promise.resolve().then(fn).then(
    () => { passed++; console.log("✔ " + name); },
    (e) => { failed++; console.log("✘ " + name + ": " + (e && e.message ? e.message : e)); }
  );
}
function eq(got, want, what) {
  if (got !== want) throw new Error((what || "value") + "\n    expected: " + JSON.stringify(want) + "\n    got:      " + JSON.stringify(got));
}
function has(got, part, what) {
  if (String(got).indexOf(part) === -1) throw new Error((what || "value") + " should contain " + JSON.stringify(part) + "\n    got: " + JSON.stringify(got));
}
function lacks(got, part, what) {
  if (String(got).indexOf(part) !== -1) throw new Error((what || "value") + " should not contain " + JSON.stringify(part) + "\n    got: " + JSON.stringify(got));
}

// A ReadableStream of UTF-8 chunks, split where a real network would not be kind.
function streamOf(chunks) {
  const enc = new TextEncoder();
  return new ReadableStream({
    start(ctrl) { for (const c of chunks) ctrl.enqueue(enc.encode(c)); ctrl.close(); }
  });
}
async function collect(provider, chunks) {
  const p = ask.PROVIDERS[provider];
  let text = "";
  await ask.readLines(streamOf(chunks), (line) => {
    const obj = ask.parseLine(line);
    if (obj) text += p.delta(obj);
  });
  return text;
}

const system = "You are a tutor.";
const messages = [{ role: "user", content: "What is a KV cache?" }];

async function main() {
  // ---- request shapes ----
  await check("OpenAI request: chat completions, bearer key, system first, streaming, low effort", () => {
    const r = ask.PROVIDERS.openai.request({ key: "sk-test", model: "gpt-5.4-mini" }, system, messages);
    eq(r.url, "https://api.openai.com/v1/chat/completions", "url");
    eq(r.headers.Authorization, "Bearer sk-test", "auth header");
    eq(r.body.stream, true, "stream");
    eq(r.body.reasoning_effort, "low", "reasoning effort");
    eq(r.body.messages[0].role, "system", "first message");
    eq(r.body.messages[0].content, system, "system text");
    eq(r.body.messages[1].content, messages[0].content, "user text");
  });
  await check("OpenAI request: a custom base URL and a non-reasoning model", () => {
    const r = ask.PROVIDERS.openai.request({ key: "k", model: "gpt-4.1-mini", baseUrl: "http://localhost:1234/v1/" }, system, messages);
    eq(r.url, "http://localhost:1234/v1/chat/completions", "url");
    eq(r.body.reasoning_effort, undefined, "no reasoning effort");
  });
  await check("Anthropic request: messages endpoint, key and browser headers, system apart", () => {
    const r = ask.PROVIDERS.anthropic.request({ key: "sk-ant-test" }, system, messages);
    eq(r.url, "https://api.anthropic.com/v1/messages", "url");
    eq(r.headers["x-api-key"], "sk-ant-test", "key header");
    eq(r.headers["anthropic-dangerous-direct-browser-access"], "true", "browser header");
    eq(r.headers["anthropic-version"], "2023-06-01", "version header");
    eq(r.body.model, "claude-opus-5-5", "default model");
    eq(r.body.system, system, "system");
    eq(r.body.messages.length, 1, "no system message in messages");
    eq(r.body.stream, true, "stream");
  });
  await check("Ollama request: local chat endpoint, no key", () => {
    const r = ask.PROVIDERS.ollama.request({ model: "llama3.1" }, system, messages);
    eq(r.url, "http://localhost:11434/api/chat", "url");
    eq(r.headers.Authorization, undefined, "no auth header");
    eq(r.body.model, "llama3.1", "model");
    eq(r.body.messages[0].role, "system", "system message");
  });

  // ---- stream parsing ----
  await check("parseLine: data lines, [DONE], comments, event lines, junk", () => {
    eq(ask.parseLine('data: {"a":1}').a, 1, "data line");
    eq(ask.parseLine('{"a":2}').a, 2, "bare json");
    eq(ask.parseLine("data: [DONE]"), null, "[DONE]");
    eq(ask.parseLine(""), null, "blank");
    eq(ask.parseLine(": keep-alive"), null, "comment");
    eq(ask.parseLine("event: content_block_delta"), null, "event line");
    eq(ask.parseLine("data: not json"), null, "junk");
  });
  await check("OpenAI stream: text joins across chunk boundaries that split a line", async () => {
    const chunks = [
      'data: {"choices":[{"index":0,"delta":{"role":"assistant","content":""},"finish_reason":null}]}\n\n',
      'data: {"choices":[{"index":0,"delta":{"content":"A KV"},"finish_reason":null}]}\n\ndata: {"choices":[{"index":0,"del',
      'ta":{"content":" cache stores"},"finish_reason":null}]}\n\n',
      'data: {"choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n'
    ];
    eq(await collect("openai", chunks), "A KV cache stores", "text");
  });
  await check("Anthropic stream: only text deltas count", async () => {
    const chunks = [
      'event: message_start\ndata: {"type":"message_start","message":{"id":"m","usage":{"input_tokens":10}}}\n\n',
      'event: content_block_start\ndata: {"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}}\n\n',
      'event: content_block_delta\ndata: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"Hello"}}\n\n',
      'event: content_block_delta\ndata: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":" there"}}\n\n',
      'event: message_delta\ndata: {"type":"message_delta","delta":{"stop_reason":"end_turn"},"usage":{"output_tokens":2}}\n\n',
      'event: message_stop\ndata: {"type":"message_stop"}\n\n'
    ];
    eq(await collect("anthropic", chunks), "Hello there", "text");
  });
  await check("Ollama stream: NDJSON message content", async () => {
    const chunks = [
      '{"model":"llama3.1","message":{"role":"assistant","content":"Hi"},"done":false}\n',
      '{"model":"llama3.1","message":{"role":"assistant","content":" there"},"done":false}\n',
      '{"model":"llama3.1","message":{"role":"assistant","content":""},"done":true}\n'
    ];
    eq(await collect("ollama", chunks), "Hi there", "text");
  });
  await check("an error object in the stream throws with the provider's message", async () => {
    let err = null;
    try { await collect("openai", ['data: {"error":{"message":"model not found","type":"invalid_request_error"}}\n']); }
    catch (e) { err = e; }
    if (!err) throw new Error("no error thrown");
    has(err.message, "model not found", "message");
  });
  await check("requestError: HTTP status and body become one readable message", () => {
    const e = ask.requestError(401, '{"error":{"message":"Incorrect API key provided"}}');
    has(e.message, "rejected", "401 reason");
    has(e.message, "Incorrect API key", "provider text");
    eq(e.status, 401, "status");
    has(ask.requestError(429, "").message, "Rate limited", "429 reason");
    has(ask.requestError(500, "<html>oops</html>").message, "HTTP 500", "non-JSON body");
  });

  // ---- Markdown ----
  const md = ask.renderMarkdown;
  await check("Markdown: paragraphs and inline marks", () => {
    eq(md("One **two** `three` *four*.\n\nFive."), "<p>One <strong>two</strong> <code>three</code> <em>four</em>.</p><p>Five.</p>", "html");
  });
  await check("Markdown: HTML in the answer is escaped, never injected", () => {
    const out = md('<script>alert(1)</script> and `<b>x</b>` and [x](javascript:alert(1))');
    lacks(out, "<script>", "script");
    has(out, "&lt;script&gt;", "escaped");
    has(out, "<code>&lt;b&gt;x&lt;/b&gt;</code>", "escaped code span");
    lacks(out, 'href="javascript:', "javascript link");
  });
  await check("Markdown: links open in a new tab, http(s) only", () => {
    has(md("see [the paper](https://arxiv.org/abs/1706.03762)"), '<a href="https://arxiv.org/abs/1706.03762" target="_blank" rel="noopener">the paper</a>', "link");
  });
  await check("Markdown: lists, numbered lists and continuation lines", () => {
    eq(md("- a\n- b\n  continued\n\n1. x\n2. y"), "<ul><li>a</li><li>b continued</li></ul><ol><li>x</li><li>y</li></ol>", "lists");
  });
  await check("Markdown: fenced code keeps lines and escapes", () => {
    eq(md("```python\nx = a < b\nprint(x)\n```"), '<pre data-lang="python"><code>x = a &lt; b\nprint(x)</code></pre>', "code");
  });
  await check("Markdown: headings become small headings, quotes become quotes", () => {
    eq(md("## Why\n> because"), "<h4>Why</h4><blockquote><p>because</p></blockquote>", "html");
  });
  await check("Markdown: a simple table", () => {
    eq(md("| a | b |\n|---|---|\n| 1 | 2 |"), "<table><tr><th>a</th><th>b</th></tr><tr><td>1</td><td>2</td></tr></table>", "table");
  });
  await check("Markdown: maths becomes data-tex for KaTeX, prices stay prose", () => {
    has(md("so $\\sigma(z) = 1/(1+e^{-z})$ here"), '<span class="tex" data-tex="\\sigma(z) = 1/(1+e^{-z})">', "inline");
    has(md("$$\nL = -\\log p\n$$"), '<div class="eq-display" data-tex="L = -\\log p">', "display block");
    has(md("$$E = mc^2$$"), '<div class="eq-display" data-tex="E = mc^2">', "display one-liner");
    has(md("it costs $5 and $10 a month"), "<p>it costs $5 and $10 a month</p>", "prices");
  });
  await check("Markdown: \\( \\) and \\[ \\] delimiters are accepted too", () => {
    has(md("so \\(x^2\\) and\n\\[\\sum_i x_i\\]"), 'data-tex="x^2"', "inline");
    has(md("so \\(x^2\\) and\n\\[\\sum_i x_i\\]"), 'data-tex="\\sum_i x_i"', "display");
  });
  await check("Markdown: never stalls on odd input", () => {
    const odd = ["```", "$$", "|", "> ", "- ", "#", "**", "`", "\u0000", "$$\nx"];
    for (const s of odd) { const out = md(s); if (typeof out !== "string") throw new Error("not a string for " + JSON.stringify(s)); }
  });

  // ---- live ----
  if (process.argv.includes("--live")) {
    const key = process.env.OPENAI_API_KEY;
    await check("live: one streamed answer from OpenAI through streamChat", async () => {
      if (!key) throw new Error("OPENAI_API_KEY is not set");
      const settings = { provider: "openai", key, model: process.env.ASK_MODEL || ask.PROVIDERS.openai.model };
      let text = "", pieces = 0;
      await ask.streamChat(settings, "You are a tutor. Answer in one short sentence.", messages,
        (d) => { text += d; pieces++; }, AbortSignal.timeout(60000));
      if (!text.trim()) throw new Error("empty answer");
      if (pieces < 2) throw new Error("answer did not stream (" + pieces + " piece)");
      console.log("    " + settings.model + " (" + pieces + " pieces): " + text.trim().replace(/\s+/g, " ").slice(0, 160));
    });
    await check("live: a wrong key gives a readable 401", async () => {
      let err = null;
      try { await ask.streamChat({ provider: "openai", key: "sk-wrong", model: ask.PROVIDERS.openai.model }, system, messages, () => {}, AbortSignal.timeout(30000)); }
      catch (e) { err = e; }
      if (!err) throw new Error("no error");
      has(err.message, "HTTP 401", "status");
    });
  }

  console.log(passed + "/" + (passed + failed) + " checks passing");
  process.exit(failed ? 1 : 0);
}

main().catch((e) => { console.error(e); process.exit(1); });
