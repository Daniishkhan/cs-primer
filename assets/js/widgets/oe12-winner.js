/* Winner's curse explorer (A7 chapter 12).
   A search generates N candidate agent designs. Each has a true accuracy drawn from a normal spread
   around a mean. The search scores every candidate on a small search set (binomial noise), keeps the
   one that looks best, and we then ask how good that pick really is. Averaged over 300 seeded trials. */
(function () {
  "use strict";
  var root = document.getElementById("oe12-winner");
  if (!root) return;

  var NS = "http://www.w3.org/2000/svg";
  var TRIALS = 300;
  var designsIn = root.querySelector("[data-act=designs]"), designsOut = root.querySelector("[data-act=designs-out]");
  var qIn = root.querySelector("[data-act=questions]"), qOut = root.querySelector("[data-act=questions-out]");
  var spreadIn = root.querySelector("[data-act=spread]"), spreadOut = root.querySelector("[data-act=spread-out]");
  var svg = root.querySelector(".oe12-chart");
  var note = root.querySelector(".oe12-note");
  var DESIGNS = [1, 2, 5, 10, 20, 50, 100, 200];
  var QS = [10, 20, 40, 80, 160, 320, 640];

  function mulberry32(a) {
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      var t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  function gauss(rng) {
    var u = Math.max(1e-12, rng()), v = rng();
    return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
  }
  function binom(rng, n, p) {
    var k = 0, i;
    for (i = 0; i < n; i++) if (rng() < p) k++;
    return k;
  }

  function simulate(nd, nq, spread) {
    var rng = mulberry32(12345 + nd * 31 + nq), t, i;
    var seen = 0, real = 0, best = 0;
    for (t = 0; t < TRIALS; t++) {
      var bestSeen = -1, pickTrue = 0, bestTrue = 0;
      for (i = 0; i < nd; i++) {
        var p = Math.min(0.99, Math.max(0.05, 0.6 + spread * gauss(rng)));
        var s = binom(rng, nq, p) / nq;
        if (p > bestTrue) bestTrue = p;
        if (s > bestSeen) { bestSeen = s; pickTrue = p; }
      }
      seen += bestSeen; real += pickTrue; best += bestTrue;
    }
    return { seen: seen / TRIALS, real: real / TRIALS, best: best / TRIALS };
  }

  function el(tag, attrs, text) {
    var e = document.createElementNS(NS, tag), k;
    for (k in attrs) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    return e;
  }
  function pct(x) { return (100 * x).toFixed(1) + "%"; }

  function draw(series, sel) {
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    var W = 640, H = 280, L = 44, R = 14, T = 12, B = 44, pw = W - L - R, ph = H - T - B, i;
    var lo = 0.5, hi = 1.0;
    function X(idx) { return L + pw * idx / (DESIGNS.length - 1); }
    function Y(v) { return T + ph * (1 - (Math.min(hi, Math.max(lo, v)) - lo) / (hi - lo)); }
    for (i = 0; i <= 5; i++) {
      var v = lo + (hi - lo) * i / 5;
      svg.appendChild(el("line", { x1: L, y1: Y(v), x2: W - R, y2: Y(v), "class": "grid" }));
      svg.appendChild(el("text", { x: L - 6, y: Y(v) + 4, "text-anchor": "end" }, Math.round(v * 100) + "%"));
    }
    svg.appendChild(el("line", { x1: L, y1: T + ph, x2: W - R, y2: T + ph, "class": "ax" }));
    for (i = 0; i < DESIGNS.length; i++) svg.appendChild(el("text", { x: X(i), y: T + ph + 16, "text-anchor": "middle" }, String(DESIGNS[i])));
    svg.appendChild(el("text", { x: L + pw / 2, y: H - 6, "text-anchor": "middle" }, "designs tried (N)"));
    svg.appendChild(el("text", { x: 12, y: T + ph / 2, "text-anchor": "middle", transform: "rotate(-90 12 " + (T + ph / 2) + ")" }, "accuracy"));
    svg.appendChild(el("line", { x1: X(sel), y1: T, x2: X(sel), y2: T + ph, "class": "mark" }));
    ["seen", "real", "best"].forEach(function (key) {
      var d = "", j;
      for (j = 0; j < series.length; j++) d += (j ? "L" : "M") + X(j).toFixed(1) + "," + Y(series[j][key]).toFixed(1);
      svg.appendChild(el("path", { d: d, "class": "l-" + key }));
    });
    svg.setAttribute("viewBox", "0 0 " + W + " " + H);
  }

  function update() {
    var sel = parseInt(designsIn.value, 10), nq = QS[parseInt(qIn.value, 10)];
    var spread = parseFloat(spreadIn.value);
    designsOut.textContent = String(DESIGNS[sel]);
    qOut.textContent = String(nq);
    spreadOut.textContent = spread.toFixed(3).replace(/0$/, "");
    var series = DESIGNS.map(function (nd) { return simulate(nd, nq, spread); });
    draw(series, sel);
    var r = series[sel];
    note.textContent = "With " + DESIGNS[sel] + " designs scored on " + nq + " questions, the winner looks like " + pct(r.seen) +
      " on the search set but is really " + pct(r.real) + " (an over-statement of " + (100 * (r.seen - r.real)).toFixed(1) +
      " points). The best design that existed was " + pct(r.best) + ", so the search also missed " + (100 * (r.best - r.real)).toFixed(1) +
      " points on the table. More questions shrinks both gaps; more designs widens the first.";
  }

  [designsIn, qIn, spreadIn].forEach(function (inp) { inp.addEventListener("input", update); });
  update();
})();
