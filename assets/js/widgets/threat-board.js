/* Threat board (security chapter 1).

   A small data-flow diagram for an "upload a profile photo" feature: a browser (external entity),
   an upload API and an image worker (processes), a blob store and a metadata DB (data stores),
   and four data flows between them. Click any element to see its STRIDE threats. STRIDE-per-element
   applies only the categories that make sense for each element type:
     external entity : S, R          process : S T R I D E
     data store      : T, R*, I, D   data flow : T, I, D
   (* repudiation applies to a store only when it holds audit logs; the widget lists it as n/a.)
   "Show trust boundaries" draws the dashed yellow boundaries and flags the flows that cross one,
   which is where the checklist says to look first. Each threat has a "mitigated" tick; the counter
   shows how many applicable threats are still open. State is in memory only; nothing is stored.
   The threats and mitigations are examples for this feature, not an exhaustive list. */
(function () {
  "use strict";
  var root = document.getElementById("threat-board");
  if (!root) return;
  var NS = "http://www.w3.org/2000/svg";
  function h(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function s(tag, attrs, cls) {
    var e = document.createElementNS(NS, tag);
    if (attrs) Object.keys(attrs).forEach(function (k) { e.setAttribute(k, attrs[k]); });
    if (cls) e.setAttribute("class", cls);
    return e;
  }

  var CATS = [
    { k: "S", name: "Spoofing",               prop: "authenticity" },
    { k: "T", name: "Tampering",              prop: "integrity" },
    { k: "R", name: "Repudiation",            prop: "accountability (non-repudiation)" },
    { k: "I", name: "Information disclosure", prop: "confidentiality" },
    { k: "D", name: "Denial of service",      prop: "availability" },
    { k: "E", name: "Elevation of privilege", prop: "authorization" }
  ];

  /* x,y,w,h for nodes; flows reference node ids. crosses = names of boundaries crossed. */
  var NODES = {
    browser: { label: "Browser",       sub: "external entity", x: 14,  y: 110, w: 112, h: 52, cls: "fs-green s-green sw-2",  type: "entity" },
    api:     { label: "Upload API",    sub: "process",         x: 214, y: 110, w: 120, h: 52, cls: "fs-blue s-blue sw-2",    type: "process" },
    worker:  { label: "Image worker",  sub: "process",         x: 454, y: 40,  w: 130, h: 52, cls: "fs-blue s-blue sw-2",    type: "process" },
    store:   { label: "Blob store",    sub: "data store",      x: 454, y: 196, w: 130, h: 52, cls: "box",                    type: "store" },
    db:      { label: "Metadata DB",   sub: "data store",      x: 214, y: 214, w: 120, h: 44, cls: "box",                    type: "store" }
  };
  var FLOWS = {
    f1: { label: "1 upload", from: "browser", to: "api",    crosses: "internet / service" },
    f2: { label: "2 raw bytes", from: "api", to: "worker",   crosses: "sandbox" },
    f3: { label: "3 resized", from: "worker", to: "store",  crosses: "sandbox" },
    f4: { label: "4 record", from: "api", to: "db",         crosses: null }
  };

  /* threat text per element: category -> [threat, mitigation] */
  var T = {
    browser: {
      S: ["An attacker uploads while pretending to be another user (stolen or guessed session).", "Authenticate every upload with a session or token; bind the photo to the authenticated user id, never to an id in the request body."],
      R: ["A user later denies uploading an abusive image.", "Server-side audit log: user id, time, file hash, source address; keep it append-only and separate from the app's own storage."]
    },
    api: {
      S: ["A client or service impersonates the API (look-alike endpoint, stale DNS).", "TLS with certificate validation; HSTS; internal callers verify the API's identity too (mutual TLS)."],
      T: ["Request fields (filename, content type, owner id) are altered or crafted.", "Treat every field as untrusted: ignore client filename, derive the content type by sniffing the bytes, take the owner from the session."],
      R: ["No record of who uploaded what, so abuse cannot be traced.", "Structured audit events written on every accepted and rejected upload."],
      I: ["Error pages or logs leak stack traces, storage paths or other users' data.", "Generic errors to clients; detail only in logs; do not log image contents or tokens."],
      D: ["Huge uploads, or thousands of small ones, exhaust memory, disk or workers.", "Hard size limit enforced while streaming; per-user and per-address rate limits; bounded queue in front of the worker."],
      E: ["Path traversal or an object-id parameter lets a user overwrite another user's photo.", "Authorisation check on the object (does this user own it?) for every request; server-generated random object names."]
    },
    worker: {
      S: ["A malicious process posts results to the store as if it were the worker.", "Give the worker its own narrowly scoped credential; the store accepts only that identity."],
      T: ["A crafted image exploits the decoder and runs attacker code (decoders parse complicated formats).", "Run the worker in a sandbox with no network, a read-only filesystem and a tiny privilege set; keep the library patched; re-encode to a clean format."],
      R: ["Cannot tell which input produced a bad output.", "Log input hash and output hash per job."],
      I: ["A compromised worker reads other users' images or secrets from the host.", "One job per sandbox, nothing else mounted, no cloud credentials in the environment."],
      D: ["A decompression bomb (tiny file, enormous pixel dimensions) consumes memory and CPU.", "Reject by declared dimensions before decoding; memory, CPU-time and wall-clock limits per job."],
      E: ["Decoder bug becomes code execution, then escape to the host or the store.", "Defence in depth: sandbox plus least-privilege credentials, so a compromise reaches only this job's output path."]
    },
    store: {
      T: ["Someone overwrites or replaces stored photos.", "Write-only credential for the worker, read-only for the CDN; object versioning; never let clients choose the object key."],
      I: ["A mis-set public-read permission, or guessable URLs, expose private photos.", "Private by default; serve through signed, expiring URLs; encryption at rest with managed keys."],
      D: ["Storage fills with junk, or objects are deleted.", "Per-user quotas, lifecycle rules, deletion protection and backups."]
    },
    db: {
      T: ["SQL injection or a bad update rewrites ownership of a photo.", "Parameterised queries; the app's DB role can only touch its own tables; migrations run under a different role."],
      I: ["A dump or over-broad query exposes user records.", "Encrypt backups; limit which services can read the table; no production data in test environments."],
      D: ["Slow queries or connection exhaustion take the feature down.", "Connection pooling with limits, timeouts, indexes on lookup columns."]
    },
    f1: {
      T: ["A network attacker modifies the upload in transit.", "TLS 1.3 with certificate validation."],
      I: ["The image (and session cookie) is read on the network path.", "TLS everywhere; Secure and HttpOnly cookie flags."],
      D: ["Slow-send connections hold server resources open.", "Request and idle timeouts at the edge; connection limits."]
    },
    f2: {
      T: ["Bytes are altered between API and worker (shared queue, shared disk).", "Authenticated internal channel (mutual TLS or signed job messages); worker verifies a content hash."],
      I: ["Another tenant or workload on the same network reads the raw bytes.", "Private network segment, encrypted channel, no shared scratch space."],
      D: ["Queue flooded with jobs.", "Bounded queue with back-pressure and per-user fairness."]
    },
    f3: {
      T: ["Result replaced on its way to the store.", "Write through an authenticated, encrypted connection; store verifies the checksum header."],
      I: ["Processed images are readable in transit inside the service network.", "Encrypt in transit even inside the perimeter; the inside is not automatically trusted."],
      D: ["Retries storm the store after a blip.", "Exponential backoff with jitter; idempotent writes."]
    },
    f4: {
      T: ["Query text or values are altered between API and DB.", "TLS to the database; parameterised statements."],
      I: ["Credentials or rows are sniffed.", "TLS to the database; short-lived DB credentials."],
      D: ["Chatty queries saturate the link.", "Batching, timeouts, connection limits."]
    }
  };
  var APPLIES = { entity: "SR", process: "STRIDE", store: "TID", flow: "TID" };
  /* flows are keyed f1..f4 */
  function typeOf(id) { return NODES[id] ? NODES[id].type : "flow"; }
  function nameOf(id) { return NODES[id] ? NODES[id].label : "Flow " + FLOWS[id].label; }

  var S = { sel: "api", bounds: false, done: {} };

  var head = h("div", "widget-head");
  head.appendChild(h("span", "widget-tag", "Explore"));
  head.appendChild(h("h4", "widget-title", "Threat board: upload a profile photo"));
  root.appendChild(head);
  root.appendChild(h("p", "widget-help", "Click an element or a flow (or Tab to it and press Enter). Each applicable STRIDE category lists a threat and a mitigation for this feature; tick a threat once you consider it mitigated."));

  var row = h("div", "widget-row");
  var bBtn = h("button", "btn small", "Show trust boundaries"); bBtn.type = "button";
  bBtn.setAttribute("aria-pressed", "false");
  bBtn.addEventListener("click", function () { S.bounds = !S.bounds; render(); });
  var rBtn = h("button", "btn small", "Reset ticks"); rBtn.type = "button";
  rBtn.addEventListener("click", function () { S.done = {}; render(); });
  var counter = h("span", "pill");
  row.appendChild(bBtn); row.appendChild(rBtn); row.appendChild(counter);
  root.appendChild(row);

  var box = h("div", "tb-box");
  var svg = s("svg", { viewBox: "0 0 640 290", role: "img", "aria-label": "Data-flow diagram of a photo upload: browser to upload API, to an image worker in a sandbox, to a blob store; the API also writes to a metadata database. Dashed yellow lines mark trust boundaries when shown." });
  var defs = s("defs");
  var mk = s("marker", { id: "ahS01tb", viewBox: "0 0 10 10", refX: "9", refY: "5", markerWidth: "7", markerHeight: "7", orient: "auto" });
  mk.appendChild(s("path", { d: "M0,0 L10,5 L0,10 z" }, "arrowhead"));
  defs.appendChild(mk); svg.appendChild(defs);
  var gB = s("g"); svg.appendChild(gB);
  var gF = s("g"); svg.appendChild(gF);
  var gN = s("g"); svg.appendChild(gN);
  box.appendChild(svg); root.appendChild(box);

  function ctr(n) { return { x: n.x + n.w / 2, y: n.y + n.h / 2 }; }
  function edge(n, tx, ty) {
    var c = ctr(n), dx = tx - c.x, dy = ty - c.y;
    var k = Math.min(dx ? (n.w / 2 + 3) / Math.abs(dx) : 1e9, dy ? (n.h / 2 + 3) / Math.abs(dy) : 1e9);
    return { x: c.x + dx * k, y: c.y + dy * k };
  }

  var nodeEls = {}, flowEls = {};
  function pick(id) { S.sel = id; render(); }

  Object.keys(FLOWS).forEach(function (id) {
    var f = FLOWS[id], a = NODES[f.from], b = NODES[f.to];
    var p = edge(a, ctr(b).x, ctr(b).y), q = edge(b, ctr(a).x, ctr(a).y);
    var g = s("g", { tabindex: "0", role: "button", "aria-label": "Flow " + f.label });
    var hit = s("line", { x1: p.x, y1: p.y, x2: q.x, y2: q.y, "stroke-width": "16", stroke: "transparent" });
    var ln = s("line", { x1: p.x, y1: p.y, x2: q.x, y2: q.y, "marker-end": "url(#ahS01tb)" }, "line s-blue");
    var mx = (p.x + q.x) / 2, my = (p.y + q.y) / 2;
    var off = (id === "f2") ? { dx: -6, dy: -10, a: "end" } : (id === "f3") ? { dx: 14, dy: 4, a: "start" } : (id === "f4") ? { dx: 10, dy: -4, a: "start" } : { dx: 0, dy: -10, a: "middle" };
    var t = s("text", { x: mx + off.dx, y: my + off.dy, "text-anchor": off.a }, "t-xs t-bold");
    t.textContent = f.label;
    g.appendChild(hit); g.appendChild(ln); g.appendChild(t);
    g.addEventListener("click", function () { pick(id); });
    g.addEventListener("keydown", function (e) { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); pick(id); } });
    gF.appendChild(g); flowEls[id] = { g: g, ln: ln };
  });

  Object.keys(NODES).forEach(function (id) {
    var n = NODES[id];
    var g = s("g", { tabindex: "0", role: "button", "aria-label": n.label + ", " + n.sub });
    g.appendChild(s("rect", { x: n.x, y: n.y, width: n.w, height: n.h, rx: 8 }, n.cls));
    var t1 = s("text", { x: n.x + n.w / 2, y: n.y + 22, "text-anchor": "middle" }, "t-sm t-bold"); t1.textContent = n.label;
    var t2 = s("text", { x: n.x + n.w / 2, y: n.y + 39, "text-anchor": "middle" }, "t-xs t-muted"); t2.textContent = n.sub;
    g.appendChild(t1); g.appendChild(t2);
    g.addEventListener("click", function () { pick(id); });
    g.addEventListener("keydown", function (e) { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); pick(id); } });
    gN.appendChild(g); nodeEls[id] = g;
  });

  function drawBounds() {
    while (gB.firstChild) gB.removeChild(gB.firstChild);
    if (!S.bounds) return;
    gB.appendChild(s("line", { x1: 170, y1: 8, x2: 170, y2: 282 }, "line-dash s-yellow"));
    var t = s("text", { x: 164, y: 20, "text-anchor": "end" }, "t-xs t-bold"); t.textContent = "Internet (untrusted)"; gB.appendChild(t);
    var t2 = s("text", { x: 176, y: 20 }, "t-xs t-bold"); t2.textContent = "Our service"; gB.appendChild(t2);
    gB.appendChild(s("rect", { x: 420, y: 24, width: 200, height: 84, rx: 10 }, "line-dash s-yellow fs-none"));
    var t3 = s("text", { x: 430, y: 120 }, "t-xs t-bold"); t3.textContent = "Sandbox boundary"; gB.appendChild(t3);
  }

  var detail = h("div", "widget-out tb-detail");
  detail.setAttribute("aria-live", "polite");
  root.appendChild(detail);

  function render() {
    bBtn.setAttribute("aria-pressed", S.bounds ? "true" : "false");
    bBtn.textContent = S.bounds ? "Hide trust boundaries" : "Show trust boundaries";
    drawBounds();
    Object.keys(nodeEls).forEach(function (id) { nodeEls[id].setAttribute("opacity", id === S.sel ? "1" : "0.78"); nodeEls[id].firstChild.style.strokeWidth = id === S.sel ? "4px" : ""; });
    Object.keys(flowEls).forEach(function (id) {
      var cross = S.bounds && FLOWS[id].crosses;
      flowEls[id].ln.setAttribute("class", "line " + (cross ? "s-red" : "s-blue"));
      flowEls[id].ln.style.strokeWidth = id === S.sel ? "4px" : "";
    });
    // counter over all applicable threats
    var total = 0, open = 0;
    Object.keys(T).forEach(function (id) {
      Object.keys(T[id]).forEach(function (k) { total++; if (!S.done[id + k]) open++; });
    });
    counter.textContent = open + " of " + total + " threats open";

    detail.textContent = "";
    var id = S.sel, type = typeOf(id);
    var title = h("p", null); title.style.margin = "0 0 6px";
    var b = h("strong", null, nameOf(id)); title.appendChild(b);
    title.appendChild(document.createTextNode(" (" + (type === "entity" ? "external entity" : type === "store" ? "data store" : type) + ")"));
    detail.appendChild(title);
    if (FLOWS[id] && S.bounds && FLOWS[id].crosses) {
      var warn = h("p", "tb-cross", "This flow crosses the " + FLOWS[id].crosses + " trust boundary. Data on one side is controlled by a different party, so validate on arrival and authenticate the sender.");
      detail.appendChild(warn);
    } else if (FLOWS[id] && S.bounds) {
      detail.appendChild(h("p", "tb-cross", "This flow stays inside one trust zone, so it is lower priority, but not exempt."));
    }
    var tbl = h("div", "tb-rows");
    CATS.forEach(function (c) {
      var applies = APPLIES[type].indexOf(c.k) >= 0;
      var item = (T[id] || {})[c.k];
      var r = h("div", "tb-row" + (applies && item ? "" : " tb-na"));
      var lab = h("div", "tb-cat");
      lab.appendChild(h("strong", null, c.k + " " + c.name));
      lab.appendChild(h("span", "tb-prop", "violates " + c.prop));
      r.appendChild(lab);
      var body = h("div", "tb-body");
      if (!applies) body.appendChild(h("p", null, "Not applicable to this element type in STRIDE-per-element."));
      else if (!item) body.appendChild(h("p", null, "No specific threat recorded for this feature; for a real review you would still ask the question."));
      else {
        var key = id + c.k;
        var lb = h("label", "tb-tick");
        var cb = h("input"); cb.type = "checkbox"; cb.checked = !!S.done[key];
        cb.addEventListener("change", function () { S.done[key] = cb.checked; render(); });
        lb.appendChild(cb); lb.appendChild(document.createTextNode(" mitigated"));
        body.appendChild(h("p", null, item[0]));
        var m = h("p", "tb-mit"); m.appendChild(h("em", null, "Mitigation: ")); m.appendChild(document.createTextNode(item[1]));
        body.appendChild(m); body.appendChild(lb);
      }
      r.appendChild(body); tbl.appendChild(r);
    });
    detail.appendChild(tbl);
  }
  render();
})();
