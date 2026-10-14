/* Workflow-pattern comparison (agents chapter 13).
   Six patterns, one set of assumptions. Every default is an ILLUSTRATIVE assumption, not a measurement.
   Model: each model call is correct independently with probability p, except where stated.
   - chain of n: every step must be right, so p^n.
   - route: router and handler must both be right; a misrouted item still succeeds 30% of the time (assumption).
   - sectioning into n parts: every part must be right (p^n) but the parts run at once.
   - voting with n judges: a share c of items are "hard" and fool every judge together; on the rest a judge is
     right with q = p/(1-c), so a single judge is still right with probability p overall. Majority wins.
   - orchestrator-workers with n workers: planner, n workers and synthesiser must all be right.
   - evaluator-optimiser, at most n rounds: a draft is good with probability p; the evaluator rejects a bad draft
     with probability e and never rejects a good one; after n rejected drafts the last draft is returned. */
(function () {
  "use strict";

  function choose(n, k) { var r = 1, i; for (i = 1; i <= k; i++) r = r * (n - k + i) / i; return r; }
  function majority(q, n) {
    var s = 0, k;
    for (k = Math.floor(n / 2) + 1; k <= n; k++) s += choose(n, k) * Math.pow(q, k) * Math.pow(1 - q, n - k);
    return s;
  }

  function model(o) {
    var per = o.tin + o.tout, rows = [], rej, rounds, i, good, q;
    rows.push({ name: "Single call", calls: 1, tokens: per, time: o.lat, ok: o.p });
    rows.push({ name: "Chain of n steps", calls: o.n, tokens: o.n * per, time: o.n * o.lat, ok: Math.pow(o.p, o.n) });
    rows.push({ name: "Route, then handle", calls: 2, tokens: 2 * per, time: 2 * o.lat, ok: o.p * o.p + (1 - o.p) * 0.3 });
    rows.push({ name: "Sectioning into n parts", calls: o.n, tokens: o.n * per, time: o.lat, ok: Math.pow(o.p, o.n) });
    q = Math.min(1, o.p / (1 - o.c));
    rows.push({ name: "Voting with n judges", calls: o.n, tokens: o.n * per, time: o.lat, ok: (1 - o.c) * majority(q, o.n) });
    rows.push({ name: "Orchestrator, n workers", calls: o.n + 2, tokens: (o.n + 2) * per, time: 3 * o.lat, ok: Math.pow(o.p, o.n + 2) });
    rej = (1 - o.p) * o.e; rounds = 0; good = 0;
    for (i = 0; i < o.n; i++) { rounds += Math.pow(rej, i); good += Math.pow(rej, i) * o.p; }
    rows.push({ name: "Evaluator-optimiser, n rounds", calls: 2 * rounds, tokens: 2 * rounds * per, time: 2 * rounds * o.lat, ok: good });
    return rows;
  }

  var core = { model: model, majority: majority };
  if (typeof module !== "undefined" && module.exports) module.exports = core;
  if (typeof document === "undefined") return;
  var root = document.getElementById("agt13-patterns");
  if (!root) return;

  function el(tag, attrs, text) {
    var e = document.createElement(tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    return e;
  }
  function fmt(x) { return Math.round(x).toLocaleString("en-GB"); }

  var state = { p: 0.9, n: 5, tin: 1500, tout: 300, lat: 3, c: 0.1, e: 0.8 };
  var outs = {};

  var head = el("div", { "class": "widget-head" });
  head.appendChild(el("span", { "class": "widget-tag" }, "Try it"));
  head.appendChild(el("h4", { "class": "widget-title" }, "What does each pattern cost, and what does it buy?"));
  root.appendChild(head);
  root.appendChild(el("p", { "class": "widget-help" },
    "Same task, same assumptions, six patterns. Change the chance that one model call is right and the width n, and watch calls, tokens and waiting time against the chance of a correct result. " +
    "Everything here is an assumption you can change, not a measurement."));

  var ctl = el("div", { "class": "ag13-ctl" });
  function slider(key, label, min, max, step, show) {
    var w = el("div");
    var lab = el("label", { "for": "agt13-" + key }, label + ": ");
    var out = el("output", { id: "agt13-" + key + "-out" });
    lab.appendChild(out);
    var inp = el("input", { type: "range", id: "agt13-" + key, min: min, max: max, step: step, value: state[key] });
    inp.addEventListener("input", function () { state[key] = parseFloat(inp.value); update(); });
    w.appendChild(lab); w.appendChild(inp); ctl.appendChild(w);
    outs[key] = { el: out, show: show };
  }
  var pct = function (v) { return (v * 100).toFixed(0) + "%"; };
  slider("p", "Chance one call is right", 0.5, 0.99, 0.01, pct);
  slider("n", "Width n (steps, parts, judges, workers, rounds)", 2, 9, 1, String);
  slider("tin", "Input tokens per call", 200, 6000, 100, fmt);
  slider("tout", "Output tokens per call", 50, 1500, 50, fmt);
  slider("lat", "Seconds per call", 0.5, 10, 0.5, function (v) { return v.toFixed(1); });
  slider("c", "Hard items that fool every judge", 0, 0.4, 0.05, pct);
  slider("e", "Evaluator catches a bad draft", 0.1, 1, 0.05, pct);
  root.appendChild(ctl);

  var wrap = el("div", { "class": "ag13-wrap" });
  var table = el("table", { "class": "ag13-table" });
  wrap.appendChild(table);
  root.appendChild(wrap);
  var note = el("div", { "class": "widget-out", "aria-live": "polite" });
  root.appendChild(note);

  function update() {
    var k, rows = model(state), best = 0, cheap = 0, fast = 0, i;
    for (k in outs) outs[k].el.textContent = outs[k].show(state[k]);
    while (table.firstChild) table.removeChild(table.firstChild);
    var tr = el("tr");
    ["Pattern", "Calls", "Tokens", "Seconds", "Chance correct"].forEach(function (h) { tr.appendChild(el("th", {}, h)); });
    table.appendChild(tr);
    for (i = 1; i < rows.length; i++) {
      if (rows[i].ok > rows[best].ok) best = i;
      if (rows[i].tokens < rows[cheap].tokens) cheap = i;
      if (rows[i].time < rows[fast].time) fast = i;
    }
    rows.forEach(function (r, idx) {
      var row = el("tr");
      row.appendChild(el("td", {}, r.name));
      row.appendChild(el("td", { "class": "num" }, r.calls.toFixed(r.calls % 1 ? 1 : 0)));
      row.appendChild(el("td", { "class": "num" }, fmt(r.tokens)));
      row.appendChild(el("td", { "class": "num" }, r.time.toFixed(1)));
      var cell = el("td", {});
      var bar = el("div", { "class": "ag13-bar" });
      var fill = el("div", { "class": "ag13-fill", style: "width:" + (r.ok * 100).toFixed(1) + "%" });
      bar.appendChild(fill);
      cell.appendChild(bar);
      cell.appendChild(el("span", { "class": "num" }, (r.ok * 100).toFixed(1) + "%"));
      row.appendChild(cell);
      table.appendChild(row);
    });
    note.textContent = "";
    [ "Highest chance of a correct result: " + rows[best].name + " (" + (rows[best].ok * 100).toFixed(1) + "%).",
      "Fewest tokens: " + rows[cheap].name + ". Least waiting: " + rows[fast].name + ".",
      "Try it: raise n for the chain and watch the chance fall; raise the hard-item share and watch voting stop improving." ].forEach(function (t) {
      note.appendChild(el("p", { style: "margin:4px 0" }, t));
    });
  }
  update();
})();
