/* Trace waterfall and critical path (reliability chapter 6).

   One request, "GET /checkout", handled by a gateway that calls (in this order):
     1. auth (6 ms)                                   - must finish first (its result is needed)
     2. a group of three independent calls: catalog (18 ms, calls its database for 12 ms),
        pricing (25 ms) and inventory (9 ms)           - run one after another, or all at once
     3. payments (30 ms, of which 20 ms is waiting for a bank API)  - needs the results of step 2
   The gateway spends 4 ms before the first call and 2 ms after the last.

   Controls: sequential or parallel for step 2; highlight the critical path; pick a span and make
   it 2x faster (its own time halves, children are unchanged) to see the effect on the whole
   trace. The critical path is found by walking backwards from the end of a span: follow the
   child that finishes last at or before the current time, recurse into it, then continue from
   that child's start. Spans NOT on it can be made arbitrarily fast and the trace does not change.

   Simplifications: no network time between services, exact durations, no queueing.
   Illustrative numbers. */
(function () {
  "use strict";
  var root = document.getElementById("trace-view");
  if (!root) return;
  var NS = "http://www.w3.org/2000/svg";

  /* name, service, own time before children (pre), after (post); kids: nodes or {group:[...]} */
  var TREE = {
    id: "gw", name: "GET /checkout", svc: "gateway", pre: 4, post: 2, kids: [
      { id: "auth", name: "auth.verify", svc: "auth", pre: 6, post: 0, kids: [] },
      { group: [
        { id: "cat", name: "catalog.get", svc: "catalog", pre: 3, post: 3, kids: [
          { id: "catdb", name: "SELECT items", svc: "catalog-db", pre: 12, post: 0, kids: [] }] },
        { id: "price", name: "pricing.quote", svc: "pricing", pre: 25, post: 0, kids: [] },
        { id: "inv", name: "inventory.check", svc: "inventory", pre: 9, post: 0, kids: [] }
      ] },
      { id: "pay", name: "payments.charge", svc: "payments", pre: 5, post: 5, kids: [
        { id: "bank", name: "bank API call", svc: "bank (external)", pre: 20, post: 0, kids: [] }] }
    ]
  };
  var COLORS = { gateway: "blue", auth: "purple", catalog: "teal", "catalog-db": "teal", pricing: "pink", inventory: "orange", payments: "green", "bank (external)": "yellow" };

  function h(tag, attrs, text) {
    var e = document.createElement(tag);
    if (attrs) for (var k in attrs) { if (k === "class") e.className = attrs[k]; else e.setAttribute(k, attrs[k]); }
    if (text != null) e.textContent = text;
    return e;
  }
  function s(tag, attrs, text) {
    var e = document.createElementNS(NS, tag);
    if (attrs) for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (text != null) e.textContent = text;
    return e;
  }
  function clear(e) { while (e.firstChild) e.removeChild(e.firstChild); }

  /* schedule: returns the end time; pushes span records into out */
  function schedule(node, t, parallel, speed, depth, parent, out) {
    var f = speed[node.id] ? 0.5 : 1;
    var rec = { id: node.id, name: node.name, svc: node.svc, start: t, end: 0, depth: depth, parent: parent, self: (node.pre + node.post) * f };
    out.push(rec);
    var cur = t + node.pre * f;
    node.kids.forEach(function (k) {
      if (k.group) {
        var ends = [], tt = cur;
        k.group.forEach(function (g) {
          var e = schedule(g, parallel ? cur : tt, parallel, speed, depth + 1, node.id, out);
          ends.push(e); tt = e;
        });
        cur = Math.max.apply(null, ends);
      } else {
        cur = schedule(k, cur, parallel, speed, depth + 1, node.id, out);
      }
    });
    rec.end = cur + node.post * f;
    return rec.end;
  }

  function critical(out) {
    var kids = {}, byId = {};
    out.forEach(function (r) { byId[r.id] = r; (kids[r.parent] = kids[r.parent] || []).push(r); });
    var path = {};
    function walk(r) {
      path[r.id] = true;
      var t = r.end;
      (kids[r.id] || []).slice().sort(function (a, b) { return b.end - a.end || b.start - a.start; }).forEach(function (c) {
        if (c.end <= t + 1e-9) { walk(c); t = c.start; }
      });
    }
    walk(kids["null"][0]);
    return path;
  }

  var head = h("div", { class: "widget-head" });
  head.appendChild(h("span", { class: "widget-tag" }, "Explore"));
  head.appendChild(h("h4", { class: "widget-title" }, "Read a waterfall, find the critical path"));
  root.appendChild(head);
  root.appendChild(h("p", { class: "widget-help" }, "Switch the three independent calls between sequential and parallel, then pick a span and make it 2x faster. Only spans on the critical path change the total."));

  var ctl = h("div", { class: "tv-controls" });
  var bSeq = h("button", { type: "button", class: "btn small", "aria-pressed": "false" }, "Sequential");
  var bPar = h("button", { type: "button", class: "btn small", "aria-pressed": "true" }, "Parallel");
  var grp = h("div", { class: "tv-grp" }); grp.appendChild(h("span", { class: "tv-l" }, "Catalog, pricing, inventory")); 
  var row1 = h("div", { class: "widget-row" }); row1.appendChild(bSeq); row1.appendChild(bPar); grp.appendChild(row1);
  ctl.appendChild(grp);
  var sel = h("select", { "aria-label": "Span to make 2x faster" });
  sel.appendChild(h("option", { value: "" }, "(none)"));
  var flat = [];
  (function f(n) { flat.push(n); n.kids.forEach(function (k) { if (k.group) k.group.forEach(f); else f(k); }); })(TREE);
  flat.forEach(function (n) { sel.appendChild(h("option", { value: n.id }, n.svc + ": " + n.name)); });
  var g2 = h("label", { class: "tv-grp" }); g2.appendChild(h("span", { class: "tv-l" }, "Make this span 2x faster")); g2.appendChild(sel);
  ctl.appendChild(g2);
  var cb = h("input", { type: "checkbox" }); cb.checked = true;
  var g3 = h("label", { class: "tv-check" }); g3.appendChild(cb); g3.appendChild(h("span", null, "Highlight critical path"));
  ctl.appendChild(g3);
  root.appendChild(ctl);

  var box = h("div", { class: "tv-box" });
  var svg = s("svg", { viewBox: "0 0 720 300", role: "img", "aria-label": "Waterfall chart of the spans in one checkout request" });
  box.appendChild(svg); root.appendChild(box);
  var out = h("div", { class: "widget-out tv-out", "aria-live": "polite" });
  root.appendChild(out);

  var parallel = true;
  function setMode(p) {
    parallel = p;
    bSeq.setAttribute("aria-pressed", String(!p)); bPar.setAttribute("aria-pressed", String(p));
    bSeq.className = "btn small" + (!p ? " primary" : ""); bPar.className = "btn small" + (p ? " primary" : "");
    render();
  }
  bSeq.addEventListener("click", function () { setMode(false); });
  bPar.addEventListener("click", function () { setMode(true); });
  sel.addEventListener("change", render);
  cb.addEventListener("change", render);

  function render() {
    var base = []; schedule(TREE, 0, parallel, {}, 0, null, base);
    var speed = {}; if (sel.value) speed[sel.value] = true;
    var recs = []; var total = schedule(TREE, 0, parallel, speed, 0, null, recs);
    var baseTotal = base[0].end;
    var crit = critical(recs), showCrit = cb.checked;
    var X0 = 200, X1 = 706, ROW = 30, TOP = 30;
    var span = Math.max(baseTotal, total);
    function x(t) { return X0 + (X1 - X0) * t / (Math.ceil(span / 10) * 10); }
    var axisMax = Math.ceil(span / 10) * 10;
    clear(svg);
    var step = axisMax > 100 ? 20 : 10, t;
    for (t = 0; t <= axisMax; t += step) {
      svg.appendChild(s("line", { x1: x(t), x2: x(t), y1: TOP - 6, y2: TOP + ROW * recs.length, class: "tv-grid" }));
      svg.appendChild(s("text", { x: x(t), y: 16, "text-anchor": "middle", class: "tv-tick" }, t + " ms"));
    }
    recs.forEach(function (r, i) {
      var y = TOP + i * ROW;
      var c = COLORS[r.svc] || "blue";
      var on = crit[r.id];
      svg.appendChild(s("text", { x: 8 + r.depth * 12, y: y + 17, class: "tv-name" + (on && showCrit ? " crit" : "") }, r.name));
      var w = Math.max(2, x(r.end) - x(r.start));
      svg.appendChild(s("rect", { x: x(r.start), y: y + 4, width: w, height: 20, rx: 3, class: "tv-bar f-" + c + (on && showCrit ? " crit" : (showCrit ? " dim" : "")) }));
      var lab = Math.round(r.end - r.start) + " ms";
      if (w > 44) svg.appendChild(s("text", { x: x(r.start) + w / 2, y: y + 18, "text-anchor": "middle", class: "tv-in" }, lab));
      else svg.appendChild(s("text", { x: x(r.end) + 5, y: y + 18, class: "tv-after" }, lab));
    });
    svg.setAttribute("viewBox", "0 0 720 " + (TOP + ROW * recs.length + 8));

    clear(out);
    var p = h("p", { class: "tv-line" });
    p.appendChild(h("span", { class: "pill " + (total < baseTotal ? "green" : "blue") }, "total " + Math.round(total) + " ms"));
    var note = "";
    if (sel.value) {
      var d = baseTotal - total;
      note = d > 0.01 ? " (was " + Math.round(baseTotal) + " ms: saved " + Math.round(d * 10) / 10 + " ms)" : " (was " + Math.round(baseTotal) + " ms: no change, that span is not on the critical path)";
    }
    p.appendChild(document.createTextNode(note));
    out.appendChild(p);
    var names = recs.filter(function (r) { return crit[r.id]; }).map(function (r) { return r.name; });
    out.appendChild(h("p", { class: "tv-line" }, "Critical path: " + names.join(" > ")));
    var par = base.filter(function (r) { return !crit[r.id]; });
  }
  setMode(true);
})();
