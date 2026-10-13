/* Queue knee explorer (reliability chapter 8).
   Plots time in system (as a multiple of the mean service time) against utilisation for
   M/M/1, M/M/c and, via the Allen-Cunneen scaling, queues with arrival and service variability.

   Formulas (all times in units of the mean service time tau = 1/mu):
     a = c * rho                      offered load, in "servers worth" of work
     Erlang C: P(wait) = probability an arrival finds all c servers busy
     Wq(M/M/c) = P(wait) / (c * (1 - rho))
     Wq(G/G/c) ~ Wq(M/M/c) * (ca2 + cs2) / 2      (Allen-Cunneen; equals Kingman's formula when c = 1)
     W = 1 + Wq,   Lq = lambda * Wq,   L = lambda * W (Little's law). */
(function () {
  "use strict";

  /* Erlang C via the numerically stable Erlang B recursion. a = offered load, c = servers. */
  function erlangC(c, a) {
    if (a >= c) return 1;
    var b = 1, k;
    for (k = 1; k <= c; k++) b = a * b / (k + a * b);
    return c * b / (c - a * (1 - b));
  }
  function wq(rho, c, ca2, cs2) {
    if (rho >= 1) return Infinity;
    return erlangC(c, c * rho) / (c * (1 - rho)) * (ca2 + cs2) / 2;
  }
  var core = { erlangC: erlangC, wq: wq };
  if (typeof module !== "undefined" && module.exports) module.exports = core;

  if (typeof document === "undefined") return;
  var root = document.getElementById("queue-knee");
  if (!root) return;

  var NS = "http://www.w3.org/2000/svg";
  function el(tag, attrs, text) {
    var e = document.createElement(tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    return e;
  }
  function sv(tag, attrs, text) {
    var e = document.createElementNS(NS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    return e;
  }

  var state = { rho: 80, c: 1, ca2: 1, cs2: 1, ms: 20 };
  var PRESETS = [
    { id: "mm1", label: "M/M/1: one server", c: 1, ca2: 1, cs2: 1 },
    { id: "pool", label: "One queue, 8 servers", c: 8, ca2: 1, cs2: 1 },
    { id: "steady", label: "Steady service times", c: 1, ca2: 1, cs2: 0 },
    { id: "bursty", label: "Bursty arrivals and service", c: 1, ca2: 4, cs2: 4 }
  ];

  var head = el("div", { "class": "widget-head" });
  head.appendChild(el("span", { "class": "widget-tag" }, "Try it"));
  head.appendChild(el("h4", { "class": "widget-title" }, "Find the knee"));
  root.appendChild(head);
  root.appendChild(el("p", { "class": "widget-help" },
    "Drag utilisation up and watch the marker climb the curve. Add servers to one shared queue, or change the variability, and see where the knee moves. The dashed grey line is always the plain single-server M/M/1 curve for comparison."));

  var presets = el("div", { "class": "op-presets", role: "group", "aria-label": "Presets" });
  var presetBtns = PRESETS.map(function (p) {
    var b = el("button", { type: "button", "class": "btn small", "aria-pressed": "false" }, p.label);
    b.addEventListener("click", function () {
      state.c = p.c; state.ca2 = p.ca2; state.cs2 = p.cs2;
      syncInputs(); update();
    });
    presets.appendChild(b);
    return b;
  });
  root.appendChild(presets);

  var ctl = el("div", { "class": "op-ctl" });
  var inputs = {};
  function slider(key, label, min, max, step, fmt) {
    var w = el("div");
    var lab = el("label", { "for": "qk-" + key }, label + ": ");
    var out = el("output", { "for": "qk-" + key });
    lab.appendChild(out);
    var inp = el("input", { type: "range", id: "qk-" + key, min: String(min), max: String(max), step: String(step), value: String(state[key]) });
    inp.addEventListener("input", function () { state[key] = parseFloat(inp.value); update(); });
    w.appendChild(lab); w.appendChild(inp); ctl.appendChild(w);
    inputs[key] = { inp: inp, out: out, fmt: fmt };
  }
  slider("rho", "Utilisation rho", 1, 98, 1, function (v) { return v + "%"; });
  slider("c", "Servers c sharing one queue", 1, 32, 1, function (v) { return String(v); });
  slider("ca2", "Arrival variability c_a squared", 0, 6, 0.25, function (v) { return v.toFixed(2); });
  slider("cs2", "Service variability c_s squared", 0, 6, 0.25, function (v) { return v.toFixed(2); });
  var msWrap = el("div");
  msWrap.appendChild(el("label", { "for": "qk-ms" }, "Mean service time (ms)"));
  var msIn = el("input", { type: "number", id: "qk-ms", min: "1", max: "5000", step: "1", value: String(state.ms) });
  msIn.addEventListener("input", function () {
    var v = parseFloat(msIn.value);
    if (isFinite(v) && v >= 1 && v <= 5000) { state.ms = v; update(); }
  });
  msWrap.appendChild(msIn); ctl.appendChild(msWrap);
  root.appendChild(ctl);

  var tiles = el("div", { "class": "op-tiles", "aria-live": "polite" });
  root.appendChild(tiles);
  var status = el("p", { "class": "op-status", "aria-live": "polite" });
  root.appendChild(status);
  var chart = el("div", { "class": "op-chart" });
  root.appendChild(chart);
  root.appendChild(el("p", { "class": "op-legend" },
    "For c = 1 the variability scaling is Kingman's formula; for c > 1 it is the Allen-Cunneen approximation. Both are approximations, accurate when the queue is busy and rough when it is nearly empty. With c_a squared = c_s squared = 1 the curves are exact."));

  function syncInputs() {
    Object.keys(inputs).forEach(function (k) {
      inputs[k].inp.value = String(state[k]);
    });
  }
  function tile(label, value, cls) {
    var d = el("div", { "class": "op-tile " + (cls || "") });
    d.appendChild(el("small", {}, label)); d.appendChild(el("b", {}, value));
    return d;
  }
  function fmtX(v) { return v >= 100 ? v.toFixed(0) + "x" : v.toFixed(v < 10 ? 2 : 1) + "x"; }
  function fmtMs(v) { return v >= 1000 ? (v / 1000).toFixed(2) + " s" : v.toFixed(v < 10 ? 1 : 0) + " ms"; }

  function update() {
    Object.keys(inputs).forEach(function (k) { inputs[k].out.textContent = inputs[k].fmt(state[k]); });
    var rho = state.rho / 100, c = state.c;
    presetBtns.forEach(function (b, i) {
      var p = PRESETS[i];
      b.setAttribute("aria-pressed", String(p.c === c && p.ca2 === state.ca2 && p.cs2 === state.cs2));
    });
    var pw = erlangC(c, c * rho);
    var q = wq(rho, c, state.ca2, state.cs2);
    var w = 1 + q;
    var lambda = rho * c * (1000 / state.ms);          /* requests per second */
    var lq = lambda * q * state.ms / 1000;
    var l = lambda * w * state.ms / 1000;
    tiles.textContent = "";
    var cls = w < 3 ? "good" : (w < 8 ? "warn" : "bad");
    tiles.appendChild(tile("Time in system", fmtX(w) + " service time = " + fmtMs(w * state.ms), cls));
    tiles.appendChild(tile("Mean wait in queue", fmtMs(q * state.ms), cls));
    tiles.appendChild(tile("P(an arrival has to wait)", (pw * 100).toFixed(0) + "%"));
    tiles.appendChild(tile("Arrival rate", lambda.toFixed(lambda < 10 ? 1 : 0) + " req/s"));
    tiles.appendChild(tile("Waiting in queue (avg)", lq.toFixed(lq < 10 ? 2 : 1)));
    tiles.appendChild(tile("In the system (L = lambda W)", l.toFixed(l < 10 ? 2 : 1)));
    var base = 1 + wq(rho, 1, 1, 1);
    status.textContent = "At " + state.rho + "% utilisation a single plain M/M/1 server would take " + fmtX(base) +
      " the service time. This configuration takes " + fmtX(w) + (w < base * 0.999 ? ": better, because of pooling or steadier work." : (w > base * 1.001 ? ": worse, because of variability." : ": the same."));
    draw(rho, w);
  }

  function draw(rho, wNow) {
    chart.textContent = "";
    var W = 700, H = 320, L = 56, R = 16, T = 14, B = 46, YMAX = 20;
    var pw = W - L - R, ph = H - T - B;
    function X(r) { return L + pw * r; }
    function Y(v) { return T + ph - ph * (Math.min(v, YMAX) - 1) / (YMAX - 1); }
    var svg = sv("svg", { viewBox: "0 0 " + W + " " + H, role: "img",
      "aria-label": "Time in system as a multiple of service time against utilisation, for the chosen configuration and for M/M/1" });
    [1, 5, 10, 15, 20].forEach(function (v) {
      svg.appendChild(sv("line", { x1: L, y1: Y(v), x2: W - R, y2: Y(v), "class": "line-thin" }));
      svg.appendChild(sv("text", { x: L - 8, y: Y(v) + 4, "text-anchor": "end", "class": "t-xs t-muted" }, v + "x"));
    });
    [0, 0.2, 0.4, 0.6, 0.8, 1].forEach(function (r) {
      svg.appendChild(sv("line", { x1: X(r), y1: T, x2: X(r), y2: T + ph, "class": "line-thin" }));
      svg.appendChild(sv("text", { x: X(r), y: T + ph + 16, "text-anchor": "middle", "class": "t-xs t-muted" }, Math.round(r * 100) + "%"));
    });
    svg.appendChild(sv("line", { x1: L, y1: T + ph, x2: W - R, y2: T + ph, "class": "line" }));
    svg.appendChild(sv("line", { x1: L, y1: T, x2: L, y2: T + ph, "class": "line" }));
    svg.appendChild(sv("text", { x: L + pw / 2, y: H - 6, "text-anchor": "middle", "class": "t-sm t-muted" }, "utilisation rho"));
    svg.appendChild(sv("text", { x: 14, y: T + ph / 2, "text-anchor": "middle", "class": "t-sm t-muted", transform: "rotate(-90 14 " + (T + ph / 2) + ")" }, "time in system / service time"));
    function path(fn) {
      var d = "";
      for (var i = 1; i <= 197; i++) {
        var r = i / 200;
        d += (i === 1 ? "M" : "L") + X(r).toFixed(1) + "," + Y(1 + fn(r)).toFixed(1);
      }
      return d;
    }
    svg.appendChild(sv("path", { d: path(function (r) { return wq(r, 1, 1, 1); }), fill: "none", "class": "line-dash" }));
    svg.appendChild(sv("path", { d: path(function (r) { return wq(r, state.c, state.ca2, state.cs2); }), fill: "none", "class": "line s-blue sw-3" }));
    svg.appendChild(sv("line", { x1: X(rho), y1: Y(1), x2: X(rho), y2: Y(wNow), "class": "line-dash s-orange" }));
    svg.appendChild(sv("circle", { cx: X(rho), cy: Y(wNow), r: 6, "class": wNow > YMAX ? "f-red" : "f-orange" }));
    var label = wNow > YMAX ? "off the chart (>" + YMAX + "x)" : fmtX(wNow);
    var left = rho > 0.7;
    svg.appendChild(sv("text", { x: X(rho) + (left ? -10 : 10), y: Y(wNow) + (wNow > YMAX ? 16 : -8), "text-anchor": left ? "end" : "start", "class": "t-sm t-bold" }, label));
    chart.appendChild(svg);
  }

  update();
})();
