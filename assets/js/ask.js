/* Ask about this page: a tutor panel that answers questions about the page
   you are reading, with the whole page as context. Loaded by main.js
   (loadAsk) on every page that has an article.prose.

   Two ways in:
     - select a passage: a small "Explain" chip appears next to it and opens
       the panel with the passage quoted and a few ready-made questions;
     - the "Ask about this page" button in the sidebar (💬 on the mobile bar).

   The model is called straight from the browser with a key the reader pastes
   into the panel's settings. The key lives in this browser's localStorage and
   goes to nobody but the provider. Providers: OpenAI (or any OpenAI-compatible
   server through its base URL), Anthropic, and a local Ollama. The thread for
   each page is kept in localStorage too.

   The pure parts (provider request builders, stream parsing, the small
   Markdown renderer) are exported when loaded by node, so that
   authoring/check_ask.js can test them without a browser. */
(function () {
  "use strict";

  var IN_BROWSER = typeof document !== "undefined";

  /* ---------- providers ----------
     Each provider turns (settings, system prompt, messages) into one HTTP
     request and reads the text out of one streamed JSON object. Every one
     of them streams one JSON object per line: "data: {…}" SSE lines for
     OpenAI and Anthropic, bare NDJSON for Ollama. */

  function withSystem(system, messages) {
    return [{ role: "system", content: system }].concat(messages);
  }
  function baseUrl(s, p) { return (s.baseUrl || p.baseUrl).replace(/\/+$/, ""); }

  var PROVIDERS = {
    openai: {
      label: "OpenAI (or a compatible server)",
      baseUrl: "https://api.openai.com/v1",
      model: "gpt-5.4-mini",
      models: ["gpt-5.5", "gpt-5.4", "gpt-5.4-mini", "gpt-5.4-nano"],
      keyHint: "sk-…",
      request: function (s, system, messages) {
        var model = s.model || this.model;
        var body = { model: model, stream: true, messages: withSystem(system, messages) };
        // Reasoning models take an effort level; a tutor's answer needs little.
        if (/^(gpt-5|o\d)/.test(model)) body.reasoning_effort = "low";
        return {
          url: baseUrl(s, this) + "/chat/completions",
          headers: { "Content-Type": "application/json", "Authorization": "Bearer " + (s.key || "") },
          body: body
        };
      },
      delta: function (obj) {
        if (obj.error) throw new Error(obj.error.message || String(obj.error));
        var c = obj.choices && obj.choices[0];
        return (c && c.delta && c.delta.content) || "";
      }
    },
    anthropic: {
      label: "Anthropic",
      baseUrl: "https://api.anthropic.com/v1",
      model: "claude-opus-5-5",
      models: ["claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"],
      keyHint: "sk-ant-…",
      request: function (s, system, messages) {
        return {
          url: baseUrl(s, this) + "/messages",
          headers: {
            "Content-Type": "application/json",
            "x-api-key": s.key || "",
            "anthropic-version": "2023-06-01",
            "anthropic-dangerous-direct-browser-access": "true"
          },
          body: { model: s.model || this.model, max_tokens: 4096, stream: true, system: system, messages: messages }
        };
      },
      delta: function (obj) {
        if (obj.type === "error") throw new Error((obj.error && obj.error.message) || "provider error");
        if (obj.type === "content_block_delta" && obj.delta && obj.delta.type === "text_delta") return obj.delta.text || "";
        return "";
      }
    },
    ollama: {
      label: "Ollama (local)",
      baseUrl: "http://localhost:11434",
      model: "",
      models: [],
      needsKey: false,
      keyHint: "no key needed",
      request: function (s, system, messages) {
        return {
          url: baseUrl(s, this) + "/api/chat",
          headers: { "Content-Type": "application/json" },
          body: { model: s.model || this.model, stream: true, messages: withSystem(system, messages) }
        };
      },
      delta: function (obj) {
        if (obj.error) throw new Error(String(obj.error));
        return (obj.message && obj.message.content) || "";
      }
    }
  };

  /* ---------- streaming ---------- */

  // One streamed line to one JSON object, or null for the lines that carry
  // nothing: blanks, SSE comments, "event:" lines and the final "[DONE]".
  function parseLine(line) {
    line = line.trim();
    if (!line || line[0] === ":" || /^(event|id|retry):/.test(line)) return null;
    if (line.indexOf("data:") === 0) line = line.slice(5).trim();
    if (!line || line === "[DONE]") return null;
    try { return JSON.parse(line); } catch (e) { return null; }
  }

  // Feeds a response body to onLine, one complete line at a time.
  function readLines(stream, onLine) {
    var reader = stream.getReader(), dec = new TextDecoder(), buf = "";
    function pump() {
      return reader.read().then(function (r) {
        if (r.done) { if (buf.trim()) onLine(buf); return; }
        buf += dec.decode(r.value, { stream: true });
        var parts = buf.split("\n");
        buf = parts.pop();
        parts.forEach(onLine);
        return pump();
      });
    }
    return pump();
  }

  function requestError(status, text) {
    var msg = "";
    try {
      var j = JSON.parse(text);
      msg = (j.error && (j.error.message || j.error)) || j.message || "";
    } catch (e) { msg = String(text || "").slice(0, 200); }
    if (typeof msg !== "string") msg = JSON.stringify(msg);
    var why = status === 401 ? "The API key was rejected."
      : status === 403 ? "The key is not allowed to do this."
      : status === 404 ? "No such model or endpoint."
      : status === 429 ? "Rate limited, or the account is out of credit."
      : "The request failed.";
    var e = new Error(why + " (HTTP " + status + (msg ? ": " + msg : "") + ")");
    e.status = status;
    return e;
  }

  function networkError(e, provider) {
    var hint = provider === "ollama"
      ? "Could not reach Ollama. Is it running, and started with OLLAMA_ORIGINS set to exactly this site's origin (" + (typeof location !== "undefined" ? location.origin : "the site origin") + ") so this page may call it? Do not use *, which would let every website call it."
      : "Could not reach the provider. Check the base URL, your connection, and that the server accepts browser (CORS) requests.";
    var err = new Error(hint + " (" + e.message + ")");
    err.cause = e;
    return err;
  }

  // Streams one answer; onDelta gets each piece of text as it arrives.
  function streamChat(settings, system, messages, onDelta, signal) {
    var name = PROVIDERS[settings.provider] ? settings.provider : "openai";
    var p = PROVIDERS[name];
    var req = p.request(settings, system, messages);
    return fetch(req.url, { method: "POST", headers: req.headers, body: JSON.stringify(req.body), signal: signal })
      .catch(function (e) { if (e.name === "AbortError") throw e; throw networkError(e, name); })
      .then(function (res) {
        if (!res.ok) return res.text().then(function (t) { throw requestError(res.status, t); });
        return readLines(res.body, function (line) {
          var obj = parseLine(line);
          if (!obj) return;
          var text = p.delta(obj);
          if (text) onDelta(text);
        });
      });
  }

  /* ---------- a small Markdown renderer ----------
     Paragraphs, headings, lists, block quotes, fenced code, simple tables,
     **bold**, *italic*, `code`, links, and maths as $…$ or $$…$$ (left as
     data-tex elements for equations.js to typeset). Everything is escaped
     first, so the model's text can never inject markup. */

  function esc(s) {
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  function inline(s) {
    var holes = [];
    function hole(html) { holes.push(html); return "\u0000" + (holes.length - 1) + "\u0000"; }
    s = s.replace(/`([^`\n]+)`/g, function (_, c) { return hole("<code>" + esc(c) + "</code>"); });
    // $…$ is maths only when it looks like it: no spaces at the edges, and
    // at least one letter, backslash or operator inside ("$5 and $10" is not).
    s = s.replace(/(?<![\w$])\$(?!\s)([^$\n]*?[\\^_=a-zA-Z][^$\n]*?)(?<!\s)\$(?![\w$])/g, function (_, t) {
      return hole('<span class="tex" data-tex="' + esc(t) + '">' + esc(t) + "</span>");
    });
    s = esc(s);
    s = s.replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>");
    s = s.replace(/(^|[^*\w])\*([^*\n]+)\*(?![\w*])/g, "$1<em>$2</em>");
    s = s.replace(/\[([^\]\n]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
    return s.replace(/\u0000(\d+)\u0000/g, function (_, i) { return holes[+i]; });
  }

  var LIST = /^\s*([-*+]|\d+[.)])\s+/;
  var BLOCK_START = /^(```|#{1,6}\s|>\s?|\s*([-*+]|\d+[.)])\s+|\$\$|\|)/;

  function renderMarkdown(md) {
    md = String(md || "").replace(/\r/g, "")
      .replace(/\\\[([\s\S]+?)\\\]/g, "\n$$$$\n$1\n$$$$\n")   // \[ … \]  ->  $$ … $$
      .replace(/\\\((.+?)\\\)/g, "$$$1$$");                    // \( … \)  ->  $ … $
    var lines = md.split("\n"), out = [], i = 0, m;
    while (i < lines.length) {
      var l = lines[i];
      if (/^\s*```/.test(l)) {
        var lang = l.replace(/^\s*```/, "").trim(), code = [];
        i++;
        while (i < lines.length && !/^\s*```/.test(lines[i])) code.push(lines[i++]);
        i++;
        out.push('<pre data-lang="' + esc(lang) + '"><code>' + esc(code.join("\n")) + "</code></pre>");
        continue;
      }
      if (/^\s*\$\$/.test(l)) {
        var t = l.trim(), tex;
        if (t.length > 4 && /\$\$$/.test(t)) { tex = t.slice(2, -2); i++; }
        else {
          var parts = [t.slice(2)];
          i++;
          while (i < lines.length && !/\$\$\s*$/.test(lines[i])) parts.push(lines[i++]);
          if (i < lines.length) parts.push(lines[i++].replace(/\$\$\s*$/, ""));
          tex = parts.join("\n");
        }
        tex = tex.trim();
        out.push('<div class="eq-display" data-tex="' + esc(tex) + '">' + esc(tex) + "</div>");
        continue;
      }
      if ((m = /^\s*(#{1,6})\s+(.*)$/.exec(l))) { out.push("<h4>" + inline(m[2]) + "</h4>"); i++; continue; }
      if (LIST.test(l)) {
        var ordered = /^\s*\d/.test(l), items = [];
        while (i < lines.length && LIST.test(lines[i])) {
          var item = lines[i].replace(LIST, "");
          i++;
          while (i < lines.length && /^\s{2,}\S/.test(lines[i]) && !LIST.test(lines[i])) item += " " + lines[i++].trim();
          items.push("<li>" + inline(item) + "</li>");
        }
        out.push((ordered ? "<ol>" : "<ul>") + items.join("") + (ordered ? "</ol>" : "</ul>"));
        continue;
      }
      if (/^\s*>\s?/.test(l)) {
        var q = [];
        while (i < lines.length && /^\s*>\s?/.test(lines[i])) q.push(lines[i++].replace(/^\s*>\s?/, ""));
        out.push("<blockquote>" + renderMarkdown(q.join("\n")) + "</blockquote>");
        continue;
      }
      if (/^\s*\|/.test(l)) {
        var rows = [];
        while (i < lines.length && /^\s*\|/.test(lines[i])) {
          var row = lines[i++].trim().replace(/^\||\|$/g, "");
          if (/^\s*:?-{2,}/.test(row)) continue;                      // the |---| separator
          rows.push(row.split("|").map(function (c) { return c.trim(); }));
        }
        out.push("<table>" + rows.map(function (r, k) {
          var tag = k === 0 ? "th" : "td";
          return "<tr>" + r.map(function (c) { return "<" + tag + ">" + inline(c) + "</" + tag + ">"; }).join("") + "</tr>";
        }).join("") + "</table>");
        continue;
      }
      if (!l.trim()) { i++; continue; }
      var p = [];
      while (i < lines.length && lines[i].trim() && !BLOCK_START.test(lines[i])) p.push(lines[i++]);
      if (!p.length) p.push(lines[i++]);                               // never stall on an odd line
      out.push("<p>" + inline(p.join(" ")) + "</p>");
    }
    return out.join("");
  }

  if (!IN_BROWSER) {
    module.exports = {
      PROVIDERS: PROVIDERS, parseLine: parseLine, readLines: readLines, streamChat: streamChat,
      renderMarkdown: renderMarkdown, requestError: requestError
    };
    return;
  }

  /* ======================= browser side ======================= */

  var NZ = window.NZ = window.NZ || {};
  var ASSETS = NZ.assets || "";
  var body = document.body;
  var article = document.querySelector("article.prose");
  if (!article) return;
  var COURSES = window.CS_COURSES || [];
  var course = COURSES.find(function (c) { return c.id === body.dataset.course; }) || null;

  var SETTINGS_KEY = "cs-ask-settings";
  var THREAD_KEY = "cs-ask-thread:" + location.pathname;
  var MAX_TURNS = 12;          // messages sent back to the model with each question
  var MAX_PAGE = 60000;        // characters of page text in the system prompt
  var MAX_THREAD = 60;         // messages kept per page
  var CANNED = ["Explain this", "Why does this matter?", "Give me an analogy", "Show me with numbers", "Simpler, please"];

  function load(key, fallback) {
    try { var v = localStorage.getItem(key); return v === null ? fallback : JSON.parse(v); }
    catch (e) { return fallback; }
  }
  function save(key, value) {
    try { localStorage.setItem(key, JSON.stringify(value)); } catch (e) { /* private mode */ }
  }
  function el(tag, attrs, children) {
    var node = document.createElement(tag);
    if (attrs) Object.keys(attrs).forEach(function (k) {
      if (k === "text") node.textContent = attrs[k];
      else if (k === "html") node.innerHTML = attrs[k];
      else if (k === "class") node.className = attrs[k];
      else node.setAttribute(k, attrs[k]);
    });
    (children || []).forEach(function (c) { if (c) node.appendChild(c); });
    return node;
  }

  var settings = load(SETTINGS_KEY, {}) || {};
  if (!PROVIDERS[settings.provider]) settings.provider = "openai";

  /* ---------- the page as text ----------
     Walks the live article (so hidden things stay hidden) and writes it out
     with headings, lists and code kept, maths as its TeX source, diagrams as
     their aria-label, and the page chrome, quizzes and this panel left out. */

  var BLOCK_TAG = /^(P|DIV|H[1-6]|LI|UL|OL|PRE|BLOCKQUOTE|FIGURE|FIGCAPTION|TABLE|TR|DT|DD|DL|SECTION|HEADER|FOOTER|ARTICLE|BR|HR|DETAILS|SUMMARY)$/;
  var SKIP_TAG = /^(SCRIPT|STYLE|SVG|BUTTON|INPUT|TEXTAREA|SELECT|NAV|TEMPLATE)$/;
  var SKIP_CLASS = /\b(quiz|toc|chapter-eyebrow|complete-box|pager|crumbs|builds-on|progress-card|settings-panel|gl-card|ask-chip|ask-panel|lab-workspace)\b/;

  function textOf(node, out) {
    if (node.nodeType === 3) { out.push(node.nodeValue); return; }
    if (node.nodeType !== 1 || node.hidden) return;
    var tag = node.tagName;
    if (tag === "SVG" || tag === "svg") {
      var lab = node.getAttribute("aria-label");
      if (lab) out.push("\n[Diagram: " + lab + "]\n");
      return;
    }
    if (SKIP_TAG.test(tag) || SKIP_CLASS.test(node.className || "")) return;
    if (node.hasAttribute("data-tex")) {
      var tex = node.getAttribute("data-tex");
      var display = node.classList.contains("eq-display") || tag === "DIV" || tag === "P";
      if (tag === "LI") { out.push("\n- $" + tex + "$: "); for (var k = node.firstChild; k; k = k.nextSibling) if (k.nodeType === 3) out.push(k.nodeValue); out.push("\n"); }
      else out.push(display ? "\n$$ " + tex + " $$\n" : "$" + tex + "$");
      return;
    }
    var block = BLOCK_TAG.test(tag);
    if (block) out.push("\n");
    if (tag === "LI") out.push("- ");
    if (/^H[1-6]$/.test(tag)) out.push("#".repeat(+tag[1]) + " ");
    if (tag === "TD" || tag === "TH") out.push(" | ");
    for (var c = node.firstChild; c; c = c.nextSibling) textOf(c, out);
    if (block) out.push("\n");
  }
  function tidy(s) { return s.replace(/[ \t]+\n/g, "\n").replace(/\n{3,}/g, "\n\n").replace(/[ \t]{2,}/g, " ").trim(); }

  var pageTextCache = null;
  function pageText() {
    if (pageTextCache !== null) return pageTextCache;
    var out = [];
    textOf(article, out);
    var t = tidy(out.join(""));
    if (t.length > MAX_PAGE) t = t.slice(0, MAX_PAGE) + "\n[The rest of the page was cut to fit.]";
    pageTextCache = t;
    return t;
  }
  function pageTitle() {
    var h1 = article.querySelector("h1");
    return (h1 ? h1.textContent : document.title).replace(/\s+/g, " ").trim();
  }
  function finishedTitles() {
    if (!course) return [];
    var done = load("cs-progress:" + course.id, []) || [];
    return (course.chapters || []).filter(function (c) {
      return done.indexOf(c.id) !== -1 && c.id !== body.dataset.chapter;
    }).map(function (c) { return String(parseInt(c.id, 10)) + ". " + c.title; });
  }

  function systemPrompt() {
    var title = pageTitle(), finished = finishedTitles();
    var where = course ? " in the course \"" + course.title + "\"" : "";
    return [
      "You are a patient tutor inside \"Zero to AI Systems\", a first-principles course on building AI systems. The reader is studying the page \"" + title + "\"" + where + ". The page's text is below between <page> tags. Answer questions about it, and about anything it takes for granted.",
      "",
      "How to answer:",
      "- Plain, direct sentences in British English. Short paragraphs. No em-dashes.",
      "- Assume no prior knowledge beyond the course so far. Define any term you introduce, in one clause.",
      "- First principles: why the mechanism works, then how, then what goes wrong. Prefer a concrete example with small numbers to an abstract statement.",
      "- At most one analogy, and say where it breaks down.",
      "- Be brief: usually three to eight sentences. Go longer only when asked. Use Markdown lightly: **bold** for the key phrase, `code`, short lists, fenced code blocks. Write maths in LaTeX between $…$ (inline) or $$…$$ (display). No tables.",
      "- When the reader quotes a passage, explain that passage where it sits: what it builds on and what it is setting up. Quote the page's own words when they help.",
      "- Honest uncertainty: if the page and your knowledge disagree, say so. Do not invent numbers, papers or dates.",
      "- Do not give away quiz answers; help the reader reason their way to them.",
      "",
      "<page title=\"" + title.replace(/"/g, "'") + "\"" + (course ? " course=\"" + course.title.replace(/"/g, "'") + "\"" : "") + ">",
      pageText(),
      "</page>",
      finished.length ? "Pages the reader has already finished in this course: " + finished.join("; ") + ". You may refer back to them." : ""
    ].join("\n");
  }

  /* ---------- the selection ---------- */

  function selectionInfo() {
    var sel = window.getSelection();
    if (!sel || sel.isCollapsed || !sel.rangeCount) return null;
    var text = sel.toString().replace(/\s+/g, " ").trim();
    if (text.length < 2) return null;
    var range = sel.getRangeAt(0);
    // Where the selection starts (a triple-click can end in the next block,
    // which would make the common ancestor the whole article).
    var node = range.startContainer;
    if (node === article) node = article.childNodes[range.startOffset] || null;
    if (node && node.nodeType === 3) node = node.parentNode;
    if (!node || node === article || !article.contains(node)) return null;
    var block = node;                                   // the article child holding the selection
    while (block && block.parentNode !== article) block = block.parentNode;
    if (!block) return null;
    var heading = null;
    for (var n = block; n; n = n.previousElementSibling) {
      if (/^H[12]$/.test(n.tagName)) { heading = n.textContent.replace(/\s+/g, " ").trim(); break; }
    }
    if (!heading) heading = pageTitle();
    var around = [];
    textOf(block, around);
    around = tidy(around.join("")).slice(0, 1500);
    var rects = range.getClientRects();
    var rect = rects.length ? rects[rects.length - 1] : range.getBoundingClientRect();
    return { text: text.slice(0, 2000), heading: heading, around: around, rect: rect };
  }

  var chip = el("button", { class: "ask-chip", type: "button", text: "💬 Explain" });
  chip.hidden = true;
  body.appendChild(chip);
  chip.addEventListener("mousedown", function (e) { e.preventDefault(); });   // keep the selection
  chip.addEventListener("click", function () {
    var info = selectionInfo() || lastInfo;
    chip.hidden = true;
    open(info);
  });
  var selTimer = null, lastInfo = null;
  document.addEventListener("selectionchange", function () {
    clearTimeout(selTimer);
    selTimer = setTimeout(refreshChip, 180);
  });
  function refreshChip() {
    var info = selectionInfo();
    if (!info) { chip.hidden = true; return; }
    lastInfo = info;
    chip.hidden = false;
    var left = info.rect.right + window.scrollX + 6, top = info.rect.bottom + window.scrollY + 6;
    left = Math.max(8, Math.min(left, window.scrollX + window.innerWidth - chip.offsetWidth - 12));
    chip.style.left = left + "px";
    chip.style.top = top + "px";
  }

  /* ---------- the panel ---------- */

  var panel = null, threadBox, settingsBox, pendingBox, cannedBox, input, sendBtn, modelChip, emptyNote;
  var thread = load(THREAD_KEY, []) || [];
  var pending = null, controller = null;

  function buildPanel() {
    if (panel) return;
    modelChip = el("button", { class: "ask-model", type: "button", title: "Which model answers; click to change" });
    var newBtn = el("button", { class: "ask-icon", type: "button", title: "Start a new thread", "aria-label": "Start a new thread", text: "🗑" });
    var gear = el("button", { class: "ask-icon", type: "button", title: "Settings: provider, model, key", "aria-label": "Settings", text: "⚙" });
    var closeBtn = el("button", { class: "ask-icon", type: "button", title: "Close (Esc)", "aria-label": "Close", text: "✕" });
    threadBox = el("div", { class: "ask-thread" });
    settingsBox = el("div", { class: "ask-settings" });
    settingsBox.hidden = true;
    pendingBox = el("div", { class: "ask-pending" });
    pendingBox.hidden = true;
    cannedBox = el("div", { class: "ask-canned" });
    cannedBox.hidden = true;
    input = el("textarea", { rows: "1", placeholder: "Ask about this page…", "aria-label": "Your question" });
    sendBtn = el("button", { class: "ask-send", type: "button", text: "Send" });
    var foot = el("div", { class: "ask-foot" }, [pendingBox, cannedBox, el("div", { class: "ask-compose" }, [input, sendBtn])]);
    panel = el("aside", { class: "ask-panel", role: "dialog", "aria-label": "Ask about this page" }, [
      el("div", { class: "ask-head" }, [el("h2", { text: "Ask about this page" }), modelChip, newBtn, gear, closeBtn]),
      threadBox, settingsBox, foot
    ]);
    body.appendChild(panel);

    CANNED.forEach(function (q) {
      var b = el("button", { type: "button", text: q });
      b.addEventListener("click", function () { send(q); });
      cannedBox.appendChild(b);
    });
    modelChip.addEventListener("click", function () { showSettings(); });
    gear.addEventListener("click", function () { if (settingsBox.hidden) showSettings(); else hideSettings(); });
    closeBtn.addEventListener("click", close);
    newBtn.addEventListener("click", function () {
      if (controller) controller.abort();
      thread = [];
      save(THREAD_KEY, thread);
      renderThread();
      input.focus();
    });
    sendBtn.addEventListener("click", function () {
      if (controller) { controller.abort(); return; }
      send(input.value);
    });
    input.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); if (!controller) send(input.value); }
    });
    input.addEventListener("input", autosize);
    panel.addEventListener("keydown", function (e) { if (e.key === "Escape") close(); });
    refreshModelChip();
    renderThread();
  }

  function autosize() {
    input.style.height = "auto";
    input.style.height = Math.min(160, input.scrollHeight) + "px";
  }
  function refreshModelChip() {
    var p = PROVIDERS[settings.provider];
    modelChip.textContent = (settings.model || p.model || "model?");
    modelChip.title = p.label + " · " + (settings.model || p.model || "no model set") + ". Click to change.";
  }

  function open(sel) {
    buildPanel();
    panel.hidden = false;
    body.classList.add("ask-open");
    if (sel) setPending(sel);
    var p = PROVIDERS[settings.provider];
    if (p.needsKey !== false && !settings.key) showSettings("Paste an API key to start. It stays in this browser.");
    else if (p.needsKey === false && !settings.model) showSettings("Name the Ollama model to use.");
    else { hideSettings(); input.focus(); }
  }
  function close() {
    if (!panel) return;
    panel.hidden = true;
    body.classList.remove("ask-open");
  }
  function setPending(sel) {
    pending = sel;
    pendingBox.textContent = "";
    var drop = el("button", { class: "ask-icon", type: "button", title: "Drop the quote", "aria-label": "Drop the quote", text: "✕" });
    drop.addEventListener("click", function () { pending = null; pendingBox.hidden = true; cannedBox.hidden = true; });
    pendingBox.appendChild(el("span", { text: "“" + sel.text.slice(0, 220) + (sel.text.length > 220 ? "…" : "") + "”" }));
    pendingBox.appendChild(drop);
    pendingBox.hidden = false;
    cannedBox.hidden = false;
  }

  /* ---------- the thread ---------- */

  function renderThread() {
    threadBox.textContent = "";
    if (!thread.length) {
      emptyNote = el("p", { class: "ask-empty", html:
        "Select any passage on the page and press <b>💬 Explain</b>, or type a question below. " +
        "The whole page goes to the model as context, so you can ask about anything on it." });
      threadBox.appendChild(emptyNote);
      return;
    }
    thread.forEach(function (m) { renderMessage(m); });
    threadBox.scrollTop = threadBox.scrollHeight;
  }
  function renderMessage(m) {
    if (emptyNote && emptyNote.parentNode) emptyNote.remove();
    var node;
    if (m.role === "user") {
      node = el("div", { class: "ask-msg user" });
      if (m.quote) node.appendChild(el("blockquote", { class: "ask-quote" }, [
        el("small", { text: "From “" + m.quote.heading + "”" }),
        document.createTextNode(m.quote.text.length > 300 ? m.quote.text.slice(0, 300) + "…" : m.quote.text)
      ]));
      node.appendChild(el("div", { text: m.show || m.content }));
    } else {
      node = el("div", { class: "ask-msg bot" });
      paint(node, m.content);
      typeset(node);
    }
    threadBox.appendChild(node);
    return node;
  }
  function paint(node, text) {
    var stick = threadBox.scrollHeight - threadBox.scrollTop - threadBox.clientHeight < 48;
    node.innerHTML = renderMarkdown(text);
    if (stick) threadBox.scrollTop = threadBox.scrollHeight;
  }
  function showError(text) {
    threadBox.appendChild(el("div", { class: "ask-error", text: text }));
    threadBox.scrollTop = threadBox.scrollHeight;
  }

  function compose(q, question) {
    if (!q) return question;
    return "Selected passage (in the section \"" + q.heading + "\"):\n> " + q.text + "\n\n" +
      (q.around && q.around !== q.text ? "The paragraph it sits in:\n" + q.around + "\n\n" : "") +
      "Question: " + question;
  }

  function send(question) {
    question = String(question || "").trim();
    if (!question && pending) question = "Explain this";
    if (!question) return;
    var p = PROVIDERS[settings.provider];
    if (p.needsKey !== false && !settings.key) { showSettings("Paste an API key to start. It stays in this browser."); return; }
    var q = pending;
    pending = null;
    pendingBox.hidden = true;
    cannedBox.hidden = true;
    input.value = "";
    autosize();
    hideSettings();

    var user = { role: "user", content: compose(q, question), show: question, quote: q ? { text: q.text, heading: q.heading } : null };
    thread.push(user);
    renderMessage(user);
    var bot = { role: "assistant", content: "" };
    var node = el("div", { class: "ask-msg bot streaming" });
    threadBox.appendChild(node);
    threadBox.scrollTop = threadBox.scrollHeight;
    saveThread();

    var history = thread.slice(-MAX_TURNS).map(function (m) { return { role: m.role, content: m.content }; });
    controller = new AbortController();
    sendBtn.textContent = "Stop";
    var frame = null;
    streamChat(settings, systemPrompt(), history, function (delta) {
      bot.content += delta;
      if (!frame) frame = requestAnimationFrame(function () { frame = null; paint(node, bot.content); });
    }, controller.signal).then(function () {
      finish(null);
    }, function (e) {
      finish(e.name === "AbortError" ? null : e);
    });

    function finish(err) {
      if (frame) { cancelAnimationFrame(frame); frame = null; }
      node.classList.remove("streaming");
      controller = null;
      sendBtn.textContent = "Send";
      if (bot.content) { paint(node, bot.content); typeset(node); thread.push(bot); }
      else node.remove();
      if (err) showError(err.message || String(err));
      saveThread();
      input.focus();
    }
  }
  function saveThread() {
    if (thread.length > MAX_THREAD) thread = thread.slice(-MAX_THREAD);
    save(THREAD_KEY, thread);
  }

  /* ---------- maths in answers: equations.js typesets data-tex nodes ---------- */

  var eqPromise = null;
  function ensureEquations() {
    if (NZ.typeset) return Promise.resolve();
    if (!eqPromise) eqPromise = new Promise(function (resolve, reject) {
      if (!ASSETS) return reject(new Error("no assets path"));
      if (!document.querySelector('script[src$="js/equations.js"]')) {
        var s = document.createElement("script");
        s.src = ASSETS + "js/equations.js";
        s.onerror = function () { reject(new Error("equations.js did not load")); };
        body.appendChild(s);
      }
      var tries = 0, t = setInterval(function () {
        if (NZ.typeset) { clearInterval(t); resolve(); }
        else if (++tries > 200) { clearInterval(t); reject(new Error("KaTeX did not load")); }
      }, 50);
    });
    return eqPromise;
  }
  function typeset(node) {
    if (!node.querySelector("[data-tex]")) return;
    ensureEquations().then(function () { NZ.typeset(node); }).catch(function (e) { console.warn("ask.js:", e.message); });
  }

  /* ---------- settings ---------- */

  function showSettings(hint) {
    settingsBox.textContent = "";
    var provSel = el("select", { "aria-label": "Provider" });
    Object.keys(PROVIDERS).forEach(function (k) {
      var o = el("option", { value: k, text: PROVIDERS[k].label });
      if (k === settings.provider) o.selected = true;
      provSel.appendChild(o);
    });
    var list = el("datalist", { id: "ask-models" });
    var modelIn = el("input", { type: "text", list: "ask-models", autocomplete: "off", spellcheck: "false", "aria-label": "Model" });
    modelIn.value = settings.model || "";
    var keyIn = el("input", { type: "password", autocomplete: "off", spellcheck: "false", "aria-label": "API key" });
    keyIn.value = settings.key || "";
    var eye = el("button", { class: "ask-icon", type: "button", title: "Show or hide the key", "aria-label": "Show or hide the key", text: "👁" });
    eye.addEventListener("click", function () { keyIn.type = keyIn.type === "password" ? "text" : "password"; });
    var urlIn = el("input", { type: "url", autocomplete: "off", spellcheck: "false", "aria-label": "Base URL" });
    urlIn.value = settings.baseUrl || "";
    var keyLabel = el("label", null, [el("span", { text: "API key" }), el("div", { class: "ask-row" }, [keyIn, eye])]);
    var urlLabel = el("label", null, [el("span", { text: "Base URL (leave empty for the default)" }), urlIn]);

    function fill() {
      var p = PROVIDERS[provSel.value];
      list.textContent = "";
      (p.models || []).forEach(function (m) { list.appendChild(el("option", { value: m })); });
      modelIn.placeholder = p.model || "model name, e.g. llama3.1";
      keyIn.placeholder = p.keyHint || "API key";
      urlIn.placeholder = p.baseUrl;
      keyLabel.hidden = p.needsKey === false;
    }
    provSel.addEventListener("change", function () {
      // A model name from another provider makes no sense here; clear it.
      var others = Object.keys(PROVIDERS).filter(function (k) { return k !== provSel.value; });
      if (others.some(function (k) { return (PROVIDERS[k].models || []).indexOf(modelIn.value.trim()) !== -1; })) modelIn.value = "";
      if (provSel.value !== settings.provider) urlIn.value = "";
      fill();
    });
    fill();

    var saveBtn = el("button", { class: "ask-send", type: "button", text: "Save" });
    var cancel = el("button", { class: "theme-toggle", type: "button", text: "Cancel" });
    saveBtn.addEventListener("click", function () {
      settings = { provider: provSel.value, model: modelIn.value.trim(), key: keyIn.value.trim(), baseUrl: urlIn.value.trim() };
      save(SETTINGS_KEY, settings);
      refreshModelChip();
      hideSettings();
      input.focus();
    });
    cancel.addEventListener("click", function () { hideSettings(); input.focus(); });

    settingsBox.appendChild(el("p", { class: "ask-note", text: hint || "Where the answers come from." }));
    settingsBox.appendChild(el("label", null, [el("span", { text: "Provider" }), provSel]));
    settingsBox.appendChild(el("label", null, [el("span", { text: "Model" }), modelIn, list]));
    settingsBox.appendChild(keyLabel);
    settingsBox.appendChild(urlLabel);
    settingsBox.appendChild(el("p", { class: "ask-note", text:
      "The key is kept in this browser's localStorage and is sent only to the provider above, straight from the page. " +
      "Nothing goes through this site. For Ollama, start it with OLLAMA_ORIGINS set to exactly this site's origin (" + location.origin + ") so this page may call it; not *, which would let every website call it." }));
    settingsBox.appendChild(el("div", { class: "ask-row" }, [saveBtn, cancel]));
    settingsBox.hidden = false;
    threadBox.hidden = true;
    (keyLabel.hidden || settings.key ? modelIn : keyIn).focus();
  }
  function hideSettings() {
    settingsBox.hidden = true;
    threadBox.hidden = false;
  }

  /* ---------- hand-off to main.js ---------- */

  NZ.ask = { open: function (sel) { open(sel || null); }, close: close };
  if (NZ.askPending) { NZ.askPending = false; open(null); }
})();
