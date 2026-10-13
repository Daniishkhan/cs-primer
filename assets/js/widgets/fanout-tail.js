/* Fan-out tail explorer (reliability chapter 9).
   A request fans out to N servers and must wait for all of them. Each call is "slow" with
   probability p (a hiccup: GC pause, compaction, noisy neighbour...), independently.
     P(request hits at least one slow call) = 1 - (1 - p)^N
   Hedging: if the first copy of a call has not answered by the hedge delay (a high quantile q of
   normal latency), send a second copy to another replica and take whichever returns first.
   A fraction f = 1 - q of calls get hedged (that is the extra load). Slow calls are covered when
   f >= p; a covered call stays slow only if the second copy is also slow (probability p), so
     p_eff = max(0, p - f) + min(p, f) * p
   This is a model of independent hiccups. Real slowness is often correlated across replicas
   (a shared dependency, a bad deploy), and hedging helps much less then. */
(function () {
  "use strict";

  function anySlow(n, p) { return 1 - Math.pow(1 - p, n); }
  function effectiveP(p, f) { return Math.max(0, p - f) + Math.min(p, f) * p; }
  var core = { anySlow: anySlow, effectiveP: effectiveP };
  if (typeof module !== "undefined" && module.exports) module.exports = core;

  if (typeof document === "undefined") return;
  var root = document.getElementById("fanout-tail");
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
  function mulberry32(a) {
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      var t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  var NS_VALUES = [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000];
  var P_VALUES = [0.0001, 0.001, 0.005, 0.01, 0.02, 0.05];
  var Q_VALUES = [0.9, 0.95, 0.99];
  var state = { ni: 6, pi: 3, hedge: false, qi: 1, roll: 1 };

  var head = el("div", { "class": "widget-head" });
  head.appendChild(el("span", { "class": "widget-tag" }, "Try it"));
  head.appendChild(el("h4", { "class": "widget-title" }, "Fan out and wait for the slowest"));
  root.appendChild(head);
  root.appendChild(el("p", { "class": "widget-help" },
    "Each dot is one call in a single user request. Red dots hit a hiccup. The request is only as fast as its slowest dot. Raise the fan-out, then switch hedging on."));

  var ctl = el("div", { "class": "op-ctl" });
  var outs = {};
  function slider(key, label, max) {
    var w = el("div");
    var lab = el("label", { "for": "ft-" + key }, label + ": ");
    var out = el("output", { "for": "ft-" + key });
    lab.appendChild(out);
    var inp = el("input", { type: "range", id: "ft-" + key, min: "0", max: String(max), step: "1", value: String(state[key]) });
    inp.addEventListener("input", function () { state[key] = parseInt(inp.value, 10); update(); });
    w.appendChild(lab); w.appendChild(inp); ctl.appendChild(w);
    outs[key] = out;
  }
  slider("ni", "Fan-out N", NS_VALUES.length - 1);
  slider("pi", "Fraction of slow calls p", P_VALUES.length - 1);
  var hw = el("div");
  var hl = el("label", { "class": "op-check", "for": "ft-hedge" });
  var hc = el("input", { type: "checkbox", id: "ft-hedge" });
  hc.addEventListener("change", function () { state.hedge = hc.checked; update(); });
  hl.appendChild(hc); hl.appendChild(el("span", {}, "Hedged requests"));
  hw.appendChild(hl);
  ctl.appendChild(hw);
  var qw = el("div");
  var ql = el("label", { "for": "ft-qi" }, "Hedge after the leaf's latency percentile: ");
  var qo = el("output", { "for": "ft-qi" });
  ql.appendChild(qo);
  var qin = el("input", { type: "range", id: "ft-qi", min: "0", max: String(Q_VALUES.length - 1), step: "1", value: String(state.qi) });
  qin.addEventListener("input", function () { state.qi = parseInt(qin.value, 10); update(); });
  qw.appendChild(ql); qw.appendChild(qin); ctl.appendChild(qw);
  root.appendChild(ctl);

  var tiles = el("div", { "class": "op-tiles", "aria-live": "polite" });
  root.appendChild(tiles);
  var row = el("div", { "class": "widget-row" });
  var again = el("button", { type: "button", "class": "btn small primary" }, "Send another request");
  again.addEventListener("click", function () { state.roll++; update(); });
  row.appendChild(again);
  var result = el("span", { "class": "op-status", style: "flex:1 1 220px", "aria-live": "polite" });
  row.appendChild(result);
  root.appendChild(row);
  var dots = el("div", { "class": "op-dots", role: "img", "aria-label": "One dot per call in the sampled request" });
  root.appendChild(dots);
  root.appendChild(el("p", { "class": "op-legend" }, "Blue: fast. Red: slow. Green: the first copy was slow but a hedge to another replica answered in time."));
  var chart = el("div", { "class": "op-chart" });
  root.appendChild(chart);

  function tile(label, value, cls) {
    var d = el("div", { "class": "op-tile " + (cls || "") });
    d.appendChild(el("small", {}, label)); d.appendChild(el("b", {}, value));
    return d;
  }
  function pct(v) { return v >= 0.9995 ? "100%" : (v * 100).toFixed(v < 0.001 ? 3 : (v < 0.1 ? 2 : 1)) + "%"; }

  function update() {
    var n = NS_VALUES[state.ni], p = P_VALUES[state.pi], q = Q_VALUES[state.qi], f = 1 - q;
    outs.ni.textContent = String(n);
    outs.pi.textContent = (p * 100).toFixed(2).replace(/0+$/, "").replace(/\.$/, "") + "%";
    qo.textContent = "p" + (q * 100);
    qin.disabled = !state.hedge;
    var pe = state.hedge ? effectiveP(p, f) : p;
    var pAny = anySlow(n, pe), pPlain = anySlow(n, p);
    tiles.textContent = "";
    tiles.appendChild(tile("P(request is slow), no hedging", pct(pPlain), pPlain > 0.5 ? "bad" : (pPlain > 0.1 ? "warn" : "good")));
    tiles.appendChild(tile("P(request is slow), now", pct(pAny), pAny > 0.5 ? "bad" : (pAny > 0.1 ? "warn" : "good")));
    tiles.appendChild(tile("Expected slow calls per request", (n * pe).toFixed(n * pe < 10 ? 2 : 1)));
    tiles.appendChild(tile("Extra load from hedges", state.hedge ? (f * 100).toFixed(0) + "%" : "0%", state.hedge && f > 0.07 ? "warn" : ""));
    if (state.hedge && f < p) {
      tiles.appendChild(tile("Warning", "delay is inside the slow region: p" + (q * 100) + " is too late to catch every hiccup", "warn"));
    }
    drawDots(n, p, state.hedge ? f : 0);
    drawChart(n, p, f);
  }

  function drawDots(n, p, f) {
    var rng = mulberry32(state.roll * 7919 + n * 31 + Math.round(p * 1e5));
    dots.textContent = "";
    var nSlow = 0, nSaved = 0, i, slow, saved, d;
    dots.style.gridTemplateColumns = "repeat(auto-fill, minmax(" + (n > 200 ? 9 : 14) + "px, 1fr))";
    for (i = 0; i < n; i++) {
      slow = rng() < p;
      saved = false;
      if (slow && f > 0) {
        /* covered by a hedge with probability min(1, f/p); the hedge itself is slow with probability p */
        var covered = rng() < Math.min(1, f / p);
        if (covered) { if (rng() < p) { /* second copy slow too */ } else { slow = false; saved = true; } }
      }
      if (slow) nSlow++;
      if (saved) nSaved++;
      d = el("span", { "class": "op-dot" + (slow ? " slow" : (saved ? " saved" : "")) });
      dots.appendChild(d);
    }
    result.textContent = nSlow
      ? "This request waited on " + nSlow + " slow call" + (nSlow > 1 ? "s" : "") + (nSaved ? " (hedges rescued " + nSaved + ")" : "") + ": the user sees the tail."
      : "No slow call this time" + (nSaved ? " (hedges rescued " + nSaved + ")" : "") + ": the user sees the typical latency.";
  }

  function drawChart(nNow, pNow, f) {
    chart.textContent = "";
    var W = 700, H = 300, L = 56, R = 16, T = 14, B = 46;
    var pw = W - L - R, ph = H - T - B, lmax = 3;
    function X(n) { return L + pw * Math.log(n) / Math.LN10 / lmax; }
    function Y(v) { return T + ph - ph * v; }
    var svg = sv("svg", { viewBox: "0 0 " + W + " " + H, role: "img",
      "aria-label": "Probability that a request hits at least one slow call, against fan-out, with and without hedging" });
    [0, 0.25, 0.5, 0.75, 1].forEach(function (v) {
      svg.appendChild(sv("line", { x1: L, y1: Y(v), x2: W - R, y2: Y(v), "class": "line-thin" }));
      svg.appendChild(sv("text", { x: L - 8, y: Y(v) + 4, "text-anchor": "end", "class": "t-xs t-muted" }, Math.round(v * 100) + "%"));
    });
    [1, 10, 100, 1000].forEach(function (n) {
      svg.appendChild(sv("line", { x1: X(n), y1: T, x2: X(n), y2: T + ph, "class": "line-thin" }));
      svg.appendChild(sv("text", { x: X(n), y: T + ph + 16, "text-anchor": "middle", "class": "t-xs t-muted" }, String(n)));
    });
    svg.appendChild(sv("line", { x1: L, y1: T + ph, x2: W - R, y2: T + ph, "class": "line" }));
    svg.appendChild(sv("line", { x1: L, y1: T, x2: L, y2: T + ph, "class": "line" }));
    svg.appendChild(sv("text", { x: L + pw / 2, y: H - 6, "text-anchor": "middle", "class": "t-sm t-muted" }, "fan-out N (log scale)"));
    svg.appendChild(sv("text", { x: 14, y: T + ph / 2, "text-anchor": "middle", "class": "t-sm t-muted", transform: "rotate(-90 14 " + (T + ph / 2) + ")" }, "P(at least one slow call)"));
    function path(p) {
      var d = "";
      for (var i = 0; i <= 90; i++) {
        var n = Math.pow(10, i / 30);
        d += (i ? "L" : "M") + X(n).toFixed(1) + "," + Y(anySlow(n, p)).toFixed(1);
      }
      return d;
    }
    svg.appendChild(sv("path", { d: path(pNow), fill: "none", "class": "line s-red sw-3" }));
    if (state.hedge) svg.appendChild(sv("path", { d: path(effectiveP(pNow, f)), fill: "none", "class": "line s-green sw-3" }));
    var pe = state.hedge ? effectiveP(pNow, f) : pNow, yv = anySlow(nNow, pe);
    svg.appendChild(sv("circle", { cx: X(nNow), cy: Y(yv), r: 6, "class": "f-orange" }));
    var right = nNow > 200;
    svg.appendChild(sv("text", { x: X(nNow) + (right ? -10 : 10), y: Y(yv) + (yv > 0.85 ? 18 : -8), "text-anchor": right ? "end" : "start", "class": "t-sm t-bold" }, pct(yv)));
    svg.appendChild(sv("text", { x: L + 8, y: T + 14, "class": "t-xs tc-red" }, "red: no hedging"));
    if (state.hedge) svg.appendChild(sv("text", { x: L + 8, y: T + 30, "class": "t-xs tc-green" }, "green: hedged"));
    chart.appendChild(svg);
  }

  update();
})();
