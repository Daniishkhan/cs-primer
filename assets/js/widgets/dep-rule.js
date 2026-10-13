/* Dependency rule checker (architecture chapter 5).

   Four concentric rings, innermost first:
     1 domain                      (order, money)
     2 use cases                   (place_order, ports)
     3 interface adapters          (http_handler, the repository adapter, payment_adapter)
     4 frameworks & infrastructure (main, web_framework, database)
   A list of preset imports ("domain/order imports sqlite_repo", ...) can be ticked on and off.
   Each ticked import is drawn as an arrow from importer to imported module. The dependency rule:
   source-code dependencies point inward or sideways, never outward. An arrow from a lower ring
   number to a higher one (inner module importing an outer module) is a violation and is drawn red,
   with an explanation and a fix. "Apply this fix" unticks the violation and ticks the imports that
   do the job properly (a port in the use-case ring, an adapter that implements it, wiring in main).

   A toggle swaps the driven adapter (SQLite <-> in-memory). The output then reports which modules
   inside the two inner rings had to change: none, unless an active import names the adapter directly.

   Simplifications: adapters importing their own driver or framework (sqlite3, the web framework) is
   their job and is not drawn; only imports between our own modules are modelled. Same-ring imports
   are allowed. No timers, no randomness, no storage. */
(function () {
  "use strict";
  var root = document.getElementById("dep-rule");
  if (!root) return;

  var NS = "http://www.w3.org/2000/svg";
  var RINGS = [
    { n: 1, name: "Domain",                       r: { x: 40, y: 202, w: 360, h: 68 },  cls: "fs-purple s-purple sw-2", op: 0.9 },
    { n: 2, name: "Use cases",                    r: { x: 28, y: 136, w: 384, h: 146 }, cls: "fs-purple s-purple sw-1", op: 0.5 },
    { n: 3, name: "Interface adapters",           r: { x: 16, y: 70,  w: 408, h: 224 }, cls: "box", op: 1 },
    { n: 4, name: "Frameworks & infrastructure",  r: { x: 4,  y: 4,   w: 432, h: 302 }, cls: "box2", op: 1 }
  ];
  /* ring index: 0 = innermost. Drawing order is outermost first. */
  var MODS = {
    order:   { label: "order",           full: "domain/order",              ring: 0, x: 98,  y: 226, cls: "box s-purple sw-2" },
    money:   { label: "money",           full: "domain/money",              ring: 0, x: 268, y: 226, cls: "box s-purple sw-2" },
    uc:      { label: "place_order",     full: "use_cases/place_order",     ring: 1, x: 42,  y: 160, cls: "box s-purple sw-2" },
    ports:   { label: "ports",           full: "use_cases/ports",           ring: 1, x: 282, y: 160, cls: "fs-cyan s-cyan sw-2" },
    http:    { label: "http_handler",    full: "adapters/http_handler",     ring: 2, x: 30,  y: 94,  cls: "box" },
    repo:    { label: "sqlite_repo",     full: "adapters/sqlite_repo",      ring: 2, x: 162, y: 94,  cls: "box" },
    pay:     { label: "payment_adapter", full: "adapters/payment_adapter",  ring: 2, x: 294, y: 94,  cls: "box" },
    web:     { label: "web_framework",   full: "web_framework",             ring: 3, x: 18,  y: 28,  cls: "box2" },
    main:    { label: "main",            full: "main (composition root)",   ring: 3, x: 162, y: 28,  cls: "box2" },
    db:      { label: "database",        full: "database",                  ring: 3, x: 306, y: 28,  cls: "box2" }
  };
  var W = 116, H = 30;

  /* from, to: module ids. why/fix only for outward imports. fixOn: imports to tick when the fix is applied. */
  var IMPORTS = [
    { id: "http-uc",     from: "http",  to: "uc",    on: true },
    { id: "uc-order",    from: "uc",    to: "order", on: true },
    { id: "uc-ports",    from: "uc",    to: "ports", on: true },
    { id: "repo-ports",  from: "repo",  to: "ports", on: true },
    { id: "pay-ports",   from: "pay",   to: "ports", on: true },
    { id: "order-money", from: "order", to: "money", on: true },
    { id: "main-http",   from: "main",  to: "http",  on: true },
    { id: "main-repo",   from: "main",  to: "repo",  on: true },
    { id: "main-pay",    from: "main",  to: "pay",   on: true },
    { id: "order-repo",  from: "order", to: "repo",  on: false,
      why: "The domain now needs that adapter, and its database driver, just to be imported or tested. The most valuable code depends on the most replaceable code.",
      fix: "Introduce a port in the use-case ring (OrderRepository). The use case calls the port, the adapter implements it, and the domain imports neither.",
      fixOn: ["uc-ports", "repo-ports"] },
    { id: "uc-repo",     from: "uc",    to: "repo",  on: false,
      why: "The use case names a concrete adapter. Changing the database now means editing business code, and testing the use case needs a database.",
      fix: "Depend on the OrderRepository port instead. main creates the adapter and passes it in.",
      fixOn: ["uc-ports", "repo-ports", "main-repo"] },
    { id: "ports-repo",  from: "ports", to: "repo",  on: false,
      why: "The port (a promise the core makes) imports the adapter that fulfils it. That is a cycle: the interface drags in its own implementation.",
      fix: "Reverse the arrow. Ports import nothing from adapters; the adapter imports the port and implements it.",
      fixOn: ["repo-ports"] },
    { id: "uc-pay",      from: "uc",    to: "pay",   on: false,
      why: "The use case imports the concrete payment adapter, so every test either calls the real provider or patches the import.",
      fix: "Depend on a PaymentGateway port in the use-case ring. The adapter implements it and main wires it in.",
      fixOn: ["uc-ports", "pay-ports", "main-pay"] },
    { id: "repo-main",   from: "repo",  to: "main",  on: false,
      why: "The adapter reaches back out to the composition root (for example to read a global database path). Inner code now depends on the outermost module.",
      fix: "Pass the setting in through the adapter's constructor. main hands the adapter its connection.",
      fixOn: ["main-repo"] },
    { id: "order-ports", from: "order", to: "ports", on: false,
      why: "An entity imports an interface owned by the use-case ring. The domain is the centre; it must not know what the application layer asks of storage.",
      fix: "Keep repository calls in the use case and pass plain values into the domain.",
      fixOn: ["uc-ports"] }
  ];
  var BY_ID = {}; IMPORTS.forEach(function (i) { BY_ID[i.id] = i; });

  var S = { on: {}, memory: false, swapped: false, hl: null };
  function reset() { S.on = {}; IMPORTS.forEach(function (i) { S.on[i.id] = i.on; }); S.memory = false; S.swapped = false; S.hl = null; }
  reset();

  function repoName() { return S.memory ? "memory_repo" : "sqlite_repo"; }
  function modLabel(id) { return id === "repo" ? repoName() : MODS[id].label; }
  function modFull(id) { return id === "repo" ? "adapters/" + repoName() : MODS[id].full; }
  function kind(i) {
    var a = MODS[i.from].ring, b = MODS[i.to].ring;
    return b > a ? "outward" : (b === a ? "same" : "inward");
  }

  /* ---------- helpers ---------- */
  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function sv(tag, attrs, cls) {
    var e = document.createElementNS(NS, tag);
    if (attrs) Object.keys(attrs).forEach(function (k) { e.setAttribute(k, attrs[k]); });
    if (cls) e.setAttribute("class", cls);
    return e;
  }
  function btn(label, cls, fn) { var b = el("button", "btn " + (cls || ""), label); b.type = "button"; b.addEventListener("click", fn); return b; }
  function center(m) { return { x: m.x + W / 2, y: m.y + H / 2 }; }
  /* where the ray from the centre of m towards (tx, ty) leaves the rectangle of m, pushed out by pad */
  function clip(m, tx, ty, pad) {
    var c = center(m), dx = tx - c.x, dy = ty - c.y;
    var sx = dx === 0 ? Infinity : (W / 2 + pad) / Math.abs(dx);
    var sy = dy === 0 ? Infinity : (H / 2 + pad) / Math.abs(dy);
    var s = Math.min(sx, sy);
    return { x: c.x + dx * s, y: c.y + dy * s };
  }

  /* ---------- static structure ---------- */
  var svg, arrows, statusEl, listEl, outEl, btnSql, btnMem, modEls = {};

  function buildSvg() {
    svg = sv("svg", { viewBox: "0 0 440 312", role: "img", "aria-label": "Four concentric rings with modules placed in them: domain in the centre, then use cases, interface adapters, and frameworks and infrastructure outside. Arrows show the imports you have ticked." });
    svg.setAttribute("class", "dr-svg");
    var defs = sv("defs");
    ["ok", "bad"].forEach(function (k) {
      var m = sv("marker", { id: "dr-ah-" + k, viewBox: "0 0 10 10", refX: "9", refY: "5", markerWidth: "6", markerHeight: "6", orient: "auto" });
      m.appendChild(sv("path", { d: "M0,0 L10,5 L0,10 z" }, k === "bad" ? "f-red" : "arrowhead"));
      defs.appendChild(m);
    });
    svg.appendChild(defs);
    for (var r = RINGS.length - 1; r >= 0; r--) {
      var R = RINGS[r], rc = sv("rect", { x: R.r.x, y: R.r.y, width: R.r.w, height: R.r.h, rx: 12 }, R.cls);
      if (R.op < 1) rc.setAttribute("style", "fill-opacity:" + R.op);
      svg.appendChild(rc);
      svg.appendChild(sv("circle", { cx: R.r.x + 14, cy: R.r.y + 12, r: 9 }, "box"));
      var bt = sv("text", { x: R.r.x + 14, y: R.r.y + 16, "text-anchor": "middle" }, "t-xs t-bold");
      bt.textContent = String(R.n); svg.appendChild(bt);
    }
    Object.keys(MODS).forEach(function (id) {
      var m = MODS[id], g = sv("g");
      g.appendChild(sv("rect", { x: m.x, y: m.y, width: W, height: H, rx: 6 }, m.cls));
      var t = sv("text", { x: m.x + W / 2, y: m.y + H / 2 + 4, "text-anchor": "middle" }, "mono t-xs");
      g.appendChild(t); modEls[id] = { g: g, t: t };
      svg.appendChild(g);
    });
    arrows = sv("g"); svg.appendChild(arrows);
  }

  function drawArrows() {
    while (arrows.firstChild) arrows.removeChild(arrows.firstChild);
    IMPORTS.forEach(function (i) {
      if (!S.on[i.id]) return;
      var a = MODS[i.from], b = MODS[i.to], ca = center(a), cb = center(b);
      var s = clip(a, cb.x, cb.y, 1), e = clip(b, ca.x, ca.y, 3);
      var dx = e.x - s.x, dy = e.y - s.y, len = Math.sqrt(dx * dx + dy * dy) || 1;
      var off = 12;
      var qx = (s.x + e.x) / 2 - dy / len * off, qy = (s.y + e.y) / 2 + dx / len * off;
      var bad = kind(i) === "outward", hl = S.hl === i.id;
      var p = sv("path", { d: "M" + s.x.toFixed(1) + "," + s.y.toFixed(1) + " Q" + qx.toFixed(1) + "," + qy.toFixed(1) + " " + e.x.toFixed(1) + "," + e.y.toFixed(1),
        "marker-end": "url(#dr-ah-" + (bad ? "bad" : "ok") + ")" },
        "line " + (bad ? "s-red sw-3" : (hl ? "s-green sw-3" : "s-green sw-2")));
      var ti = sv("title"); ti.textContent = modFull(i.from) + " imports " + modLabel(i.to) + (bad ? " (outward: violates the rule)" : "");
      p.appendChild(ti); arrows.appendChild(p);
    });
    Object.keys(modEls).forEach(function (id) {
      var label = modLabel(id);
      if (id === "db" && S.memory) label = "db (unused)";
      modEls[id].t.textContent = label;
      modEls[id].g.setAttribute("opacity", id === "db" && S.memory ? "0.45" : "1");
    });
  }

  /* ---------- controls ---------- */
  function buildControls() {
    var head = el("div", "widget-head");
    head.appendChild(el("span", "widget-tag", "Interactive"));
    head.appendChild(el("span", "widget-title", "Dependency rule checker"));
    root.appendChild(head);
    root.appendChild(el("p", "widget-help", "Tick imports to draw them between modules. Source-code dependencies must point inward (or sideways). Any arrow that points outward turns red and explains itself. Then swap the database adapter and see what has to change."));

    root.appendChild(el("p", "dr-label", "Driven adapter"));
    var grp = el("div", "dr-btns"); grp.setAttribute("role", "group"); grp.setAttribute("aria-label", "Repository adapter");
    btnSql = btn("SQLite adapter", "", function () { setAdapter(false); });
    btnMem = btn("In-memory adapter", "", function () { setAdapter(true); });
    grp.appendChild(btnSql); grp.appendChild(btnMem); root.appendChild(grp);

    var wrap = el("div", "dr-diagram"); buildSvg(); wrap.appendChild(svg); root.appendChild(wrap);
    var leg = el("p", "dr-legend");
    ["1 Domain", "2 Use cases", "3 Interface adapters", "4 Frameworks & infrastructure"].forEach(function (t) { leg.appendChild(el("span", "dr-chip", t)); });
    root.appendChild(leg);
    var key = el("p", "dr-legend");
    key.appendChild(el("span", "dr-key dr-key-ok", "green arrow: inward or sideways, allowed"));
    key.appendChild(el("span", "dr-key dr-key-bad", "red arrow: points outward, violates the rule"));
    root.appendChild(key);

    var fs = el("fieldset", "dr-fields");
    fs.appendChild(el("legend", null, "Imports (A → B means A imports B)"));
    listEl = el("div", "dr-list"); fs.appendChild(listEl); root.appendChild(fs);

    var row = el("div", "dr-btns");
    row.appendChild(btn("Reset", "", function () { reset(); refresh(); }));
    row.appendChild(btn("Clear all arrows", "", function () { IMPORTS.forEach(function (i) { S.on[i.id] = false; }); refresh(); }));
    row.appendChild(btn("Add every mistake", "", function () { IMPORTS.forEach(function (i) { if (i.why) S.on[i.id] = true; }); refresh(); }));
    root.appendChild(row);

    statusEl = el("p", "dr-status"); statusEl.tabIndex = -1; root.appendChild(statusEl);
    outEl = el("div", "widget-out dr-out"); outEl.setAttribute("aria-live", "polite"); root.appendChild(outEl);
  }

  function setAdapter(mem) { if (S.memory !== mem) S.swapped = true; S.memory = mem; refresh(); }

  function buildList() {
    listEl.textContent = "";
    IMPORTS.forEach(function (i) {
      var k = kind(i);
      var lab = el("label", "dr-item" + (S.on[i.id] && k === "outward" ? " dr-bad" : ""));
      var cb = document.createElement("input"); cb.type = "checkbox"; cb.checked = !!S.on[i.id];
      cb.addEventListener("change", function () { S.on[i.id] = cb.checked; S.hl = i.id; refresh(true); });
      cb.addEventListener("focus", function () { S.hl = i.id; drawArrows(); });
      lab.addEventListener("mouseenter", function () { S.hl = i.id; drawArrows(); });
      lab.appendChild(cb);
      var txt = el("span", "dr-item-text");
      txt.appendChild(el("code", null, modFull(i.from)));
      txt.appendChild(document.createTextNode(" → "));
      txt.appendChild(el("code", null, modFull(i.to)));
      lab.appendChild(txt);
      var pill = el("span", "pill " + (k === "outward" ? "red" : "green"), k === "outward" ? "outward" : (k === "same" ? "sideways" : "inward"));
      lab.appendChild(pill);
      listEl.appendChild(lab);
    });
  }

  function renderOut() {
    outEl.textContent = "";
    var act = IMPORTS.filter(function (i) { return S.on[i.id]; });
    var bad = act.filter(function (i) { return kind(i) === "outward"; });
    statusEl.textContent = act.length + " import" + (act.length === 1 ? "" : "s") + " drawn, " + bad.length + " violating the dependency rule.";
    statusEl.className = "dr-status " + (bad.length ? "dr-status-bad" : "dr-status-ok");

    if (!bad.length) {
      outEl.appendChild(el("p", null, act.length ? "No violations. Every arrow points inward or sideways, so the domain and use cases can be compiled, imported and tested without any adapter or framework." : "No arrows drawn. Tick some imports above."));
    }
    bad.forEach(function (i) {
      var d = el("div", "dr-viol");
      var h = el("p", "dr-viol-h");
      h.appendChild(el("code", null, modFull(i.from) + " → " + modLabel(i.to)));
      d.appendChild(h);
      var p1 = el("p"); p1.appendChild(el("strong", null, "Why it hurts: ")); p1.appendChild(document.createTextNode(i.why.replace(/sqlite_repo/g, repoName())));
      d.appendChild(p1);
      var p2 = el("p"); p2.appendChild(el("strong", null, "Fix: ")); p2.appendChild(document.createTextNode(i.fix));
      d.appendChild(p2);
      d.appendChild(btn("Apply this fix", "small", function () {
        S.on[i.id] = false; i.fixOn.forEach(function (id) { S.on[id] = true; }); S.hl = null; refresh(); statusEl.focus();
      }));
      outEl.appendChild(d);
    });

    /* swap report */
    var sw = el("div", "dr-swap");
    if (!S.swapped) {
      sw.appendChild(el("p", null, "Swap check: press “In-memory adapter” above to replace the database adapter and see which modules have to change."));
    } else {
      var hit = Object.keys(MODS).filter(function (id) {
        return MODS[id].ring <= 1 && IMPORTS.some(function (i) { return S.on[i.id] && i.from === id && i.to === "repo"; });
      });
      var name = S.memory ? "in-memory" : "SQLite";
      if (!hit.length) {
        sw.appendChild(el("p", null, "Swapped to the " + name + " adapter: 0 modules in the domain or use-case rings had to change. Only the adapter and one wiring line in main differ. That is why the core's tests run against a fake with no database."));
        sw.className = "dr-swap dr-swap-ok";
      } else {
        sw.appendChild(el("p", null, "Swapped to the " + name + " adapter: " + hit.length + " module" + (hit.length > 1 ? "s" : "") + " inside the core had to be edited (" + hit.map(function (id) { return MODS[id].full; }).join(", ") + "), because " + (hit.length > 1 ? "they import" : "it imports") + " the adapter by name. That is the cost of an outward arrow, paid on every swap and in every test."));
        sw.className = "dr-swap dr-swap-bad";
      }
    }
    outEl.appendChild(sw);
  }

  function refresh(keepFocus) {
    btnSql.setAttribute("aria-pressed", String(!S.memory));
    btnMem.setAttribute("aria-pressed", String(S.memory));
    if (keepFocus) {
      /* update labels/pills in place so the focused checkbox keeps focus */
      var rows = listEl.querySelectorAll(".dr-item");
      IMPORTS.forEach(function (i, n) {
        rows[n].className = "dr-item" + (S.on[i.id] && kind(i) === "outward" ? " dr-bad" : "");
        rows[n].querySelector("input").checked = !!S.on[i.id];
      });
    } else buildList();
    drawArrows(); renderOut();
  }

  buildControls();
  refresh();
})();
