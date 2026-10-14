/* MCP wire console (agents chapter 07).
   A browser port of the small notes server written in the chapter (server.py): the same three notes, the same tool, resource and
   prompt, the same error codes. Pick a message, edit the JSON if you like, send it, and read the reply. The server enforces the
   lifecycle the way the chapter's server does (this is that toy server's choice, not a rule of the protocol): until it has seen
   "initialize" and then "notifications/initialized", other requests get error -32600. Nothing leaves the page. */
(function () {
  "use strict";

  var NOTES = {
    "1": { title: "Rotate API keys", body: "Rotate production API keys every 90 days. Owner: platform team." },
    "2": { title: "Refund policy", body: "Refunds above 10000 cents need a human. Duplicates are refunded in full." },
    "3": { title: "On-call handover", body: "Handover is at 09:00 UK time. Check the pager and the open incidents." }
  };
  var VERSIONS = ["2025-11-25", "2025-06-18"];
  var TOOLS = [{
    name: "notes_search",
    description: "Search the team's notes by keyword. Returns up to `limit` matches as id and title. Use resources/read (or the note:// link in each match) to read a whole note.",
    inputSchema: { type: "object", properties: {
      query: { type: "string", description: "A word or phrase, e.g. 'refund'." },
      limit: { type: "integer", description: "Maximum matches, 1 to 10. Default 3." } },
      required: ["query"], additionalProperties: false }
  }];

  function RpcError(code, message, data) { this.code = code; this.message = message; this.data = data; }

  function search(args) {
    var q = args.query, limit = args.hasOwnProperty("limit") ? args.limit : 3, hits = [], id;
    if (typeof q !== "string" || !q.trim()) return ["query must be a non-empty string, for example 'refund'.", true];
    if (typeof limit !== "number" || Math.floor(limit) !== limit || limit < 1 || limit > 10)
      return ["limit must be an integer from 1 to 10; got " + JSON.stringify(limit) + ".", true];
    for (id in NOTES) {
      if ((NOTES[id].title + NOTES[id].body).toLowerCase().indexOf(q.toLowerCase()) >= 0)
        hits.push(id + ": " + NOTES[id].title + " (note://" + id + ")");
    }
    return [hits.slice(0, limit).join("\n") || "No notes match '" + q + "'.", false];
  }

  function handle(method, params) {
    var note, r;
    if (method === "initialize") {
      return { protocolVersion: VERSIONS.indexOf(params.protocolVersion) >= 0 ? params.protocolVersion : VERSIONS[0],
               capabilities: { tools: {}, resources: {}, prompts: {} }, serverInfo: { name: "notes-demo", version: "0.1.0" } };
    }
    if (method === "ping") return {};
    if (method === "tools/list") return { tools: TOOLS };
    if (method === "tools/call") {
      if (params.name !== "notes_search") throw new RpcError(-32602, "Unknown tool: " + params.name);
      r = search(params.arguments || {});
      return { content: [{ type: "text", text: r[0] }], isError: r[1] };
    }
    if (method === "resources/list") {
      return { resources: Object.keys(NOTES).map(function (i) {
        return { uri: "note://" + i, name: "note-" + i, title: NOTES[i].title, mimeType: "text/plain" }; }) };
    }
    if (method === "resources/read") {
      var uri = params.uri || "";
      note = NOTES[uri.replace(/^note:\/\//, "")];
      if (!note || uri.indexOf("note://") !== 0) throw new RpcError(-32002, "Resource not found", { uri: uri });
      return { contents: [{ uri: uri, mimeType: "text/plain", text: note.title + "\n\n" + note.body }] };
    }
    if (method === "prompts/list") {
      return { prompts: [{ name: "summarise_note", title: "Summarise a note",
        arguments: [{ name: "note_id", description: "Id such as 2", required: true }] }] };
    }
    if (method === "prompts/get") {
      note = NOTES[(params.arguments || {}).note_id];
      if (params.name !== "summarise_note" || !note) throw new RpcError(-32602, "Invalid prompt name or note_id");
      return { description: "Summarise one note", messages: [{ role: "user", content: {
        type: "text", text: "Summarise in one sentence:\n" + note.title + ": " + note.body } }] };
    }
    throw new RpcError(-32601, "Method not found: " + method);
  }

  /* Server: take one line of text, return the reply line, or null for a notification. state.ready becomes true only after
     initialize and then notifications/initialized. */
  function serve(line, state) {
    var msg, reply;
    try { msg = JSON.parse(line); } catch (e) {
      return JSON.stringify({ jsonrpc: "2.0", id: null, error: { code: -32700, message: "Parse error" } });
    }
    if (msg === null || typeof msg !== "object") {
      return JSON.stringify({ jsonrpc: "2.0", id: null, error: { code: -32600, message: "Invalid Request" } });
    }
    if (msg.id === undefined || msg.id === null) {
      if (msg.method === "notifications/initialized" && state.sawInit) state.ready = true;
      return null;
    }
    try {
      if (!state.ready && msg.method !== "initialize" && msg.method !== "ping")
        throw new RpcError(-32600, "Server not initialised: send initialize first");
      reply = { jsonrpc: "2.0", id: msg.id, result: handle(msg.method, msg.params || {}) };
      if (msg.method === "initialize") state.sawInit = true;
    } catch (e) {
      if (!(e instanceof RpcError)) throw e;
      var err = { code: e.code, message: e.message };
      if (e.data) err.data = e.data;
      reply = { jsonrpc: "2.0", id: msg.id, error: err };
    }
    return JSON.stringify(reply);
  }

  var core = { serve: serve };
  if (typeof module !== "undefined" && module.exports) module.exports = core;
  if (typeof document === "undefined") return;
  var root = document.getElementById("agt07-wire");
  if (!root) return;

  function el(tag, attrs, text) {
    var e = document.createElement(tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    return e;
  }
  var nextId = 1;
  var state = { sawInit: false, ready: false };
  var PRESETS = [
    ["initialize", function (i) { return { jsonrpc: "2.0", id: i, method: "initialize", params: { protocolVersion: "2025-11-25", capabilities: {}, clientInfo: { name: "console", version: "0.1" } } }; }],
    ["notifications/initialized (a notification)", function () { return { jsonrpc: "2.0", method: "notifications/initialized" }; }],
    ["ping", function (i) { return { jsonrpc: "2.0", id: i, method: "ping" }; }],
    ["tools/list", function (i) { return { jsonrpc: "2.0", id: i, method: "tools/list" }; }],
    ["tools/call: a good search", function (i) { return { jsonrpc: "2.0", id: i, method: "tools/call", params: { name: "notes_search", arguments: { query: "refund" } } }; }],
    ["tools/call: bad argument (limit 0)", function (i) { return { jsonrpc: "2.0", id: i, method: "tools/call", params: { name: "notes_search", arguments: { query: "refund", limit: 0 } } }; }],
    ["tools/call: unknown tool", function (i) { return { jsonrpc: "2.0", id: i, method: "tools/call", params: { name: "delete_everything", arguments: {} } }; }],
    ["resources/list", function (i) { return { jsonrpc: "2.0", id: i, method: "resources/list" }; }],
    ["resources/read note://2", function (i) { return { jsonrpc: "2.0", id: i, method: "resources/read", params: { uri: "note://2" } }; }],
    ["resources/read note://99 (missing)", function (i) { return { jsonrpc: "2.0", id: i, method: "resources/read", params: { uri: "note://99" } }; }],
    ["prompts/get summarise_note 3", function (i) { return { jsonrpc: "2.0", id: i, method: "prompts/get", params: { name: "summarise_note", arguments: { note_id: "3" } } }; }],
    ["a method that does not exist", function (i) { return { jsonrpc: "2.0", id: i, method: "tools/execute" }; }]
  ];

  var head = el("div", { "class": "widget-head" });
  head.appendChild(el("span", { "class": "widget-tag" }, "Try it"));
  head.appendChild(el("h4", { "class": "widget-title" }, "Talk to the notes server"));
  root.appendChild(head);
  root.appendChild(el("p", { "class": "widget-help" },
    "This is the chapter's notes server running in your browser. Choose a message, edit the JSON if you want to break it, and press Send. " +
    "Try a request before initialising, then do the handshake, then try again. Each line is one JSON-RPC message, as on stdio."));

  var row = el("div", { "class": "ag07-row" });
  var sel = el("select", { id: "agt07-preset", "aria-label": "Message to send" });
  PRESETS.forEach(function (p, i) { sel.appendChild(el("option", { value: String(i) }, p[0])); });
  var ta = el("textarea", { id: "agt07-editor", rows: "5", spellcheck: "false", "aria-label": "JSON message to send" });
  var send = el("button", { "class": "btn", type: "button" }, "Send");
  var reset = el("button", { "class": "btn", type: "button" }, "New connection");
  var badge = el("span", { "class": "ag07-badge" });
  row.appendChild(sel); row.appendChild(send); row.appendChild(reset); row.appendChild(badge);
  root.appendChild(row);
  root.appendChild(ta);
  var log = el("pre", { "class": "ag07-log", "aria-live": "polite" });
  root.appendChild(log);

  function load() {
    var m = PRESETS[parseInt(sel.value, 10)][1](nextId);
    ta.value = JSON.stringify(m);
  }
  function show() {
    badge.textContent = state.ready ? "state: initialised" : (state.sawInit ? "state: initialize answered, waiting for notifications/initialized" : "state: new connection");
    badge.className = "ag07-badge " + (state.ready ? "ag07-ok" : "ag07-wait");
  }
  function pretty(line) {
    try { return JSON.stringify(JSON.parse(line)); } catch (e) { return line; }
  }
  sel.addEventListener("change", load);
  send.addEventListener("click", function () {
    var line = ta.value.replace(/\n/g, " ").trim(), out, m;
    if (!line) return;
    log.textContent += "--> " + line + "\n";
    out = serve(line, state);
    log.textContent += out === null ? "    (a notification: the server sends no reply)\n" : "<-- " + pretty(out) + "\n";
    try { m = JSON.parse(line); if (m && m.id !== undefined && m.id !== null) nextId = (typeof m.id === "number" ? m.id : nextId) + 1; } catch (e) { /* keep id */ }
    log.scrollTop = log.scrollHeight;
    show(); load();
  });
  reset.addEventListener("click", function () {
    state = { sawInit: false, ready: false }; nextId = 1; log.textContent = "(new connection)\n"; show(); load();
  });
  log.textContent = "(new connection)\n";
  show(); load();
})();
