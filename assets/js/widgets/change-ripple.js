/* Change amplification explorer (architecture chapter 1).

   Nine modules of a small shop system, drawn as a dependency graph. An arrow
   A -> B means "A depends on B". A change starts in one module and ripples
   BACKWARDS along the arrows, to everything that depends on what changed.

   Each dependency has a kind:
     iface   - A uses B only through B's small public interface
     direct  - A reaches into B's internals (its tables, helpers, field names)
     global  - A and B share mutable state (a global, a shared table); treated
               as direct for the ripple, but drawn in red so it stands out

   The rule (deterministic, a breadth-first walk):
     * The module where the request starts always changes (distance 0).
     * From a module B, the ripple passes along every direct/global edge into B.
     * It passes along an iface edge into B only when B is the START module and the
       request alters that interface (a changed contract). If the request only changes
       B's insides, the interface is a firewall and the ripple stops there.
     * Distance 0 and 1 are "must change" (the change itself, plus code that must adapt);
       distance 2 and beyond are "retest" (nothing in them should need editing, but
       their behaviour may have shifted underneath them).

   Presets: tangled (many direct and global edges), modular (nine edges, all via
   interfaces) and "build your own", which starts as the modular graph and lets the
   reader cycle each possible dependency: off -> via interface -> direct -> off.

   Simplifications: this is a model of the idea, not a measurement. Real ripples depend on
   how the code is actually written. No timers other than the ripple animation, no randomness. */
(function () {
  "use strict";
  var root = document.getElementById("change-ripple");
  if (!root) return;

  var SVGNS = "http://www.w3.org/2000/svg";
  var NODE_W = 84, NODE_H = 30;
  var MODS = [
    { id: "UI",        x: 260, y: 34 },
    { id: "Reports",   x: 66,  y: 130 },
    { id: "Orders",    x: 260, y: 130 },
    { id: "Notify",    x: 454, y: 130 },
    { id: "Payments",  x: 66,  y: 236 },
    { id: "Pricing",   x: 190, y: 236 },
    { id: "Inventory", x: 454, y: 236 },
    { id: "Tax",       x: 66,  y: 338 },
    { id: "Customers", x: 260, y: 338 }
  ];
  var POS = {};
  MODS.forEach(function (m) { POS[m.id] = m; });

  /* every dependency the tangled system has: [from, to, kind] */
  var TANGLED = [
    ["UI", "Orders", "direct"], ["UI", "Payments", "direct"], ["UI", "Reports", "direct"],
    ["Orders", "Pricing", "direct"], ["Orders", "Payments", "direct"], ["Orders", "Inventory", "direct"],
    ["Orders", "Customers", "global"], ["Orders", "Notify", "direct"],
    ["Pricing", "Tax", "direct"], ["Pricing", "Customers", "global"], ["Pricing", "Payments", "direct"],
    ["Payments", "Customers", "direct"], ["Payments", "Orders", "global"],
    ["Inventory", "Orders", "global"], ["Inventory", "Customers", "global"], ["Inventory", "Pricing", "direct"],
    ["Notify", "Customers", "direct"], ["Notify", "Orders", "global"],
    ["Reports", "Orders", "global"], ["Reports", "Payments", "direct"], ["Reports", "Pricing", "direct"],
    ["Reports", "Inventory", "direct"], ["Tax", "Customers", "global"]
  ];
  var MODULAR = [
    ["UI", "Orders"], ["Orders", "Pricing"], ["Orders", "Payments"], ["Orders", "Inventory"],
    ["Orders", "Notify"], ["Pricing", "Tax"], ["Pricing", "Customers"], ["Notify", "Customers"],
    ["Reports", "Orders"]
  ];
  function key(f, t) { return f + ">" + t; }
  var CANDIDATES = TANGLED.map(function (e) { return { f: e[0], t: e[1], tangledKind: e[2] }; });

  var REQUESTS = [
    { id: "tax", label: "Change the tax rules", start: "Tax", iface: false,
      text: "New rounding and exemption rules inside Tax. Nothing about how other modules call Tax changes." },
    { id: "pay", label: "Add a payment provider", start: "Payments", iface: false,
      text: "A new provider is plugged in behind Payments. Callers still ask it to charge an amount, as before." },
    { id: "field", label: "Rename a customer field", start: "Customers", iface: true,
      text: "The customer's postcode field is renamed. Anyone who reads that field, through a public method or by reaching in, has to adapt." },
    { id: "status", label: "Change the order status values", start: "Orders", iface: true,
      text: "Orders gets a new lifecycle (new status values). That is part of Orders' public contract, so its users must adapt." },
    { id: "gift", label: "Add gift-card discounts", start: "Pricing", iface: true,
      text: "Pricing needs a new input, the gift card, so the way it is called changes: a contract change." }
  ];
  var PRESETS = [
    { id: "tangled", label: "Tangled", help: "Most modules reach into the internals of others, and a few share mutable globals (red dashed). Everything can reach almost everything." },
    { id: "modular", label: "Modular", help: "Each module is used only through a small interface (cyan). Insides can change without anyone else noticing." },
    { id: "custom", label: "Build your own", help: "Starts as the modular graph. Click a dependency below to cycle it: off, via interface, direct. Add one direct edge and watch the ripple." }
  ];

  var state = { preset: "modular", req: 0, custom: {}, stage: -1, timer: null };
  function resetCustom() {
    state.custom = {};
    CANDIDATES.forEach(function (c) { state.custom[key(c.f, c.t)] = "off"; });
    MODULAR.forEach(function (e) { state.custom[key(e[0], e[1])] = "iface"; });
  }
  resetCustom();

  function edgesFor(preset) {
    if (preset === "tangled") return TANGLED.map(function (e) { return { f: e[0], t: e[1], kind: e[2] }; });
    if (preset === "modular") return MODULAR.map(function (e) { return { f: e[0], t: e[1], kind: "iface" }; });
    var out = [];
    CANDIDATES.forEach(function (c) {
      var k = state.custom[key(c.f, c.t)];
      if (k !== "off") out.push({ f: c.f, t: c.t, kind: k });
    });
    return out;
  }

  /* breadth-first ripple: returns { dist: {id: n}, via: {id: edge}, max: n } */
  function ripple(edges, req) {
    var dist = {}, via = {}, queue = [req.start], max = 0;
    dist[req.start] = 0;
    while (queue.length) {
      var b = queue.shift();
      for (var i = 0; i < edges.length; i++) {
        var e = edges[i];
        if (e.t !== b || dist[e.f] !== undefined) continue;
        if (e.kind === "iface" && !(b === req.start && req.iface)) continue;
        dist[e.f] = dist[b] + 1; via[e.f] = e;
        if (dist[e.f] > max) max = dist[e.f];
        queue.push(e.f);
      }
    }
    return { dist: dist, via: via, max: max };
  }
  function counts(r) {
    var change = 0, retest = 0;
    Object.keys(r.dist).forEach(function (id) { if (r.dist[id] <= 1) change++; else retest++; });
    return { change: change, retest: retest, total: change + retest };
  }

  /* ---------- DOM helpers ---------- */
  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function sv(tag, attrs, cls) {
    var e = document.createElementNS(SVGNS, tag);
    if (attrs) Object.keys(attrs).forEach(function (k) { e.setAttribute(k, attrs[k]); });
    if (cls) e.setAttribute("class", cls);
    return e;
  }
  function reduced() { try { return window.matchMedia("(prefers-reduced-motion: reduce)").matches; } catch (e) { return false; } }

  /* ---------- build once ---------- */
  var head = el("div", "widget-head");
  head.appendChild(el("span", "widget-tag", "Explore"));
  head.appendChild(el("span", "widget-title", "Change amplification explorer"));
  root.appendChild(head);
  root.appendChild(el("p", "widget-help", "An arrow A → B means “A depends on B”. A change starts in one module and spreads backwards, to everything that depends on what changed. Pick an architecture and a change request, then send the change."));

  root.appendChild(el("p", "cr-label", "1. Architecture"));
  var presetRow = el("div", "cr-btns");
  presetRow.setAttribute("role", "group"); presetRow.setAttribute("aria-label", "Architecture preset");
  var presetBtns = {};
  PRESETS.forEach(function (p) {
    var b = el("button", "btn", p.label); b.type = "button";
    b.addEventListener("click", function () { state.preset = p.id; update(true); });
    presetBtns[p.id] = b; presetRow.appendChild(b);
  });
  root.appendChild(presetRow);
  var presetHelp = el("p", "cr-desc"); root.appendChild(presetHelp);

  root.appendChild(el("p", "cr-label", "2. Change request"));
  var selWrap = el("div", "cr-sel");
  var sel = el("select"); sel.id = "cr-req"; sel.setAttribute("aria-label", "Change request");
  REQUESTS.forEach(function (r, i) { var o = el("option", null, r.label); o.value = String(i); sel.appendChild(o); });
  sel.addEventListener("change", function () { state.req = parseInt(sel.value, 10); update(true); });
  selWrap.appendChild(sel);
  var sendBtn = el("button", "btn primary", "↯ Send the change"); sendBtn.type = "button";
  sendBtn.addEventListener("click", function () { play(); });
  selWrap.appendChild(sendBtn);
  root.appendChild(selWrap);
  var reqText = el("p", "cr-desc"); root.appendChild(reqText);

  /* graph */
  var fig = el("div", "cr-graph");
  var svg = sv("svg", { viewBox: "0 0 520 372", role: "img", "aria-label": "Dependency graph of nine modules: UI, Reports, Orders, Notify, Payments, Pricing, Inventory, Tax and Customers. The list below the graph states which modules are affected." }, "cr-svg");
  var defs = sv("defs");
  ["iface", "direct", "global"].forEach(function (k) {
    var m = sv("marker", { id: "ahA01rip-" + k, viewBox: "0 0 10 10", refX: "9", refY: "5", markerWidth: "6", markerHeight: "6", orient: "auto-start-reverse" });
    m.appendChild(sv("path", { d: "M0,0 L10,5 L0,10 z" }, "cr-ah cr-ah-" + k));
    defs.appendChild(m);
  });
  svg.appendChild(defs);
  var edgeLayer = sv("g"); svg.appendChild(edgeLayer);
  var nodeEls = {};
  MODS.forEach(function (m) {
    var g = sv("g", null, "cr-node");
    g.appendChild(sv("rect", { x: m.x - NODE_W / 2, y: m.y - NODE_H / 2, width: NODE_W, height: NODE_H, rx: 7 }));
    var t = sv("text", { x: m.x, y: m.y + 4, "text-anchor": "middle" }); t.textContent = m.id;
    g.appendChild(t); svg.appendChild(g); nodeEls[m.id] = g;
  });
  fig.appendChild(svg);
  root.appendChild(fig);

  var legend = el("ul", "cr-legend");
  [["iface", "through a small interface"], ["direct", "reaches into internals"], ["global", "shared mutable state"]].forEach(function (x) {
    var li = el("li"); li.appendChild(el("span", "cr-key cr-key-" + x[0])); li.appendChild(document.createTextNode(x[1])); legend.appendChild(li);
  });
  [["start", "change starts here"], ["change", "must change"], ["retest", "must be retested"]].forEach(function (x) {
    var li = el("li"); li.appendChild(el("span", "cr-swatch cr-swatch-" + x[0])); li.appendChild(document.createTextNode(x[1])); legend.appendChild(li);
  });
  root.appendChild(legend);

  /* result */
  var result = el("div", "cr-result"); result.setAttribute("aria-live", "polite");
  var big = el("p", "cr-big"); var verdict = el("p", "cr-verdict"); var compare = el("p", "cr-compare");
  result.appendChild(big); result.appendChild(verdict); result.appendChild(compare);
  root.appendChild(result);
  var modList = el("ul", "cr-list"); root.appendChild(modList);

  /* custom editor */
  var editor = el("div", "cr-editor");
  editor.appendChild(el("p", "cr-label", "Dependencies (click to cycle: off, via interface, direct)"));
  var editBtns = {};
  var grid = el("div", "cr-edge-grid");
  CANDIDATES.forEach(function (c) {
    var b = el("button", "btn small cr-edge"); b.type = "button";
    b.addEventListener("click", function () {
      var k = key(c.f, c.t), cur = state.custom[k];
      state.custom[k] = cur === "off" ? "iface" : (cur === "iface" ? "direct" : "off");
      update(false);
    });
    editBtns[key(c.f, c.t)] = b; grid.appendChild(b);
  });
  editor.appendChild(grid);
  var editRow = el("div", "cr-btns");
  var resetBtn = el("button", "btn small", "Reset to modular"); resetBtn.type = "button";
  resetBtn.addEventListener("click", function () { resetCustom(); update(false); });
  var allBtn = el("button", "btn small", "Make every dependency direct"); allBtn.type = "button";
  allBtn.addEventListener("click", function () {
    CANDIDATES.forEach(function (c) { state.custom[key(c.f, c.t)] = "direct"; }); update(false);
  });
  editRow.appendChild(resetBtn); editRow.appendChild(allBtn); editor.appendChild(editRow);
  root.appendChild(editor);

  /* ---------- drawing ---------- */
  function clip(from, to, pad) {
    var dx = to.x - from.x, dy = to.y - from.y;
    var sx = dx === 0 ? Infinity : (NODE_W / 2 + pad) / Math.abs(dx);
    var sy = dy === 0 ? Infinity : (NODE_H / 2 + pad) / Math.abs(dy);
    var s = Math.min(sx, sy);
    return { x: from.x + dx * s, y: from.y + dy * s };
  }
  function drawEdges(edges, r, stage) {
    while (edgeLayer.firstChild) edgeLayer.removeChild(edgeLayer.firstChild);
    var have = {};
    edges.forEach(function (e) { have[key(e.f, e.t)] = true; });
    edges.forEach(function (e) {
      var a = POS[e.f], b = POS[e.t];
      var p1 = clip(a, b, 2), p2 = clip(b, a, 5);
      var dx = b.x - a.x, dy = b.y - a.y, len = Math.sqrt(dx * dx + dy * dy);
      var off = have[key(e.t, e.f)] ? 6 : 0;
      var ox = (-dy / len) * off, oy = (dx / len) * off;
      var hot = r.via[e.f] === e && stage >= r.dist[e.f];
      var line = sv("line", { x1: p1.x + ox, y1: p1.y + oy, x2: p2.x + ox, y2: p2.y + oy, "marker-end": "url(#ahA01rip-" + e.kind + ")" },
        "cr-edge-line cr-e-" + e.kind + (hot ? " cr-hot" : ""));
      edgeLayer.appendChild(line);
    });
  }
  function paintNodes(r, stage) {
    MODS.forEach(function (m) {
      var d = r.dist[m.id], cls = "cr-node";
      if (d !== undefined && d <= stage) cls += d === 0 ? " cr-start" : (d === 1 ? " cr-change" : " cr-retest");
      if (d !== undefined && d === stage && stage >= 0 && !reduced()) cls += " cr-pop";
      nodeEls[m.id].setAttribute("class", cls);
    });
  }

  function update(animate) {
    if (state.timer) { clearTimeout(state.timer); state.timer = null; }
    var req = REQUESTS[state.req], edges = edgesFor(state.preset), r = ripple(edges, req), c = counts(r);
    var preset = PRESETS.filter(function (p) { return p.id === state.preset; })[0];
    PRESETS.forEach(function (p) { presetBtns[p.id].setAttribute("aria-pressed", String(p.id === state.preset)); });
    presetHelp.textContent = preset.help;
    reqText.textContent = req.text + " (" + (req.iface ? "alters the module's public interface" : "changes only the module's insides") + ".)";
    editor.hidden = state.preset !== "custom";
    CANDIDATES.forEach(function (cd) {
      var k = state.custom[key(cd.f, cd.t)], b = editBtns[key(cd.f, cd.t)];
      var word = k === "off" ? "off" : (k === "iface" ? "via interface" : "direct");
      b.textContent = cd.f + " → " + cd.t + ": " + word;
      b.setAttribute("aria-label", cd.f + " depends on " + cd.t + ": " + word + ". Activate to change.");
      b.className = "btn small cr-edge cr-edge-" + k;
    });

    /* the numbers (always the final state) */
    big.textContent = c.total + " of " + MODS.length + " modules";
    verdict.textContent = c.change + " must change" + (c.retest ? ", " + c.retest + " must be retested." : ".") +
      (c.total === 1 ? " The change stays inside one module." : "");
    var tg = counts(ripple(edgesFor("tangled"), req)), md = counts(ripple(edgesFor("modular"), req));
    compare.textContent = "The same request costs " + tg.total + " module" + (tg.total === 1 ? "" : "s") + " in the tangled preset and " + md.total + " in the modular one.";

    modList.textContent = "";
    MODS.forEach(function (m) {
      var d = r.dist[m.id], what = d === undefined ? "not affected" : (d === 0 ? "the change starts here" : (d === 1 ? "must change" : "must be retested"));
      var li = el("li", d === undefined ? "" : (d === 0 ? "cr-l-start" : (d === 1 ? "cr-l-change" : "cr-l-retest")));
      li.appendChild(el("strong", null, m.id)); li.appendChild(document.createTextNode(": " + what));
      modList.appendChild(li);
    });

    state.last = { edges: edges, r: r };
    if (animate && !reduced() && c.total > 1) { play(); }
    else { state.stage = r.max; drawEdges(edges, r, r.max); paintNodes(r, r.max); }
  }

  function play() {
    if (state.timer) { clearTimeout(state.timer); state.timer = null; }
    var edges = state.last.edges, r = state.last.r;
    if (reduced()) { state.stage = r.max; drawEdges(edges, r, r.max); paintNodes(r, r.max); return; }
    var k = 0;
    (function step() {
      state.stage = k; drawEdges(edges, r, k); paintNodes(r, k);
      if (k < r.max) { k++; state.timer = setTimeout(step, 650); } else state.timer = null;
    })();
  }

  update(false);
})();
