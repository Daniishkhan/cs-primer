/* Compute-optimal calculator (A2 chapter 18).
   For a FLOP budget C = 6 N D, finds the model size and token count that minimise the parametric loss
   L(N, D) = E + A / N^alpha + B / D^beta, using either the constants printed by Hoffmann et al. (2022)
   or the refit by Besiroglu et al. (2024). Lets you pick a model size away from the optimum and see the cost. */
(function () {
  "use strict";
  var root = document.getElementById("dl18-optimal");
  if (!root) return;
  var NS = "http://www.w3.org/2000/svg";
  var q = function (sel) { return root.querySelector(sel); };
  var cIn = q("[data-act=c]"), fitSel = q("[data-act=fit]"), mIn = q("[data-act=m]"), cOut = q("[data-act=c-out]"), mOut = q("[data-act=m-out]");
  var svg = q(".dl18-chart"), tbl = q(".dl18-table");
  var FITS = { hoff: { E: 1.69, A: 406.4, B: 410.7, a: 0.34, b: 0.28 }, besi: { E: 1.8172, A: 482.01, B: 2085.43, a: 0.3478, b: 0.3658 } };

  function el(tag, attrs, text) {
    var e = document.createElementNS(NS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    return e;
  }
  function loss(f, N, D) { return f.E + f.A / Math.pow(N, f.a) + f.B / Math.pow(D, f.b); }
  function optimum(f, C) {
    var G = Math.pow(f.a * f.A / (f.b * f.B), 1 / (f.a + f.b));
    var N = G * Math.pow(C / 6, f.b / (f.a + f.b)), D = C / (6 * N);
    return { N: N, D: D, L: loss(f, N, D) };
  }
  function sci(x) { var e = Math.floor(Math.log(x) / Math.LN10); return (x / Math.pow(10, e)).toFixed(2) + "e" + e; }
  function human(x) {
    if (x >= 1e12) return (x / 1e12).toFixed(2) + " T";
    if (x >= 1e9) return (x / 1e9).toFixed(2) + " B";
    return (x / 1e6).toFixed(1) + " M";
  }
  function equivalentBudget(f, C, L) {          // the smaller budget whose optimum reaches loss L (bisection on log C)
    var lo = 15, hi = Math.log(C) / Math.LN10;
    for (var i = 0; i < 60; i++) {
      var mid = (lo + hi) / 2;
      if (optimum(f, Math.pow(10, mid)).L > L) lo = mid; else hi = mid;
    }
    return Math.pow(10, hi);
  }

  function draw() {
    var f = FITS[fitSel.value], logC = parseFloat(cIn.value), C = Math.pow(10, logC), mult = Math.pow(2, parseFloat(mIn.value));
    cOut.textContent = "10^" + logC.toFixed(1); mOut.textContent = (mult >= 1 ? mult.toFixed(2).replace(/\.?0+$/, "") : mult.toFixed(3).replace(/\.?0+$/, "")) + "x";
    var o = optimum(f, C), N = o.N * mult, D = C / (6 * N), L = loss(f, N, D);
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    var x0 = 50, w = 620, y0 = 14, h = 130, lo = Math.log(o.N / 64) / Math.LN10, hi = Math.log(o.N * 64) / Math.LN10;
    var pts = [], i, Lmax = 0, Lmin = o.L, n, l;
    for (i = 0; i <= 120; i++) { n = Math.pow(10, lo + (hi - lo) * i / 120); l = loss(f, n, C / (6 * n)); pts.push([n, l]); Lmax = Math.max(Lmax, l); }
    Lmax = Math.min(Lmax, Lmin + 0.8);
    var px = function (v) { return x0 + (Math.log(v) / Math.LN10 - lo) / (hi - lo) * w; };
    var py = function (v) { return y0 + h - (Math.min(v, Lmax) - Lmin) / (Lmax - Lmin) * h; };
    var d = "";
    pts.forEach(function (p, j) { d += (j ? "L" : "M") + px(p[0]).toFixed(1) + "," + py(p[1]).toFixed(1); });
    svg.appendChild(el("path", { d: d, fill: "none", "class": "s-blue sw-2" }));
    svg.appendChild(el("line", { x1: x0, y1: y0 + h, x2: x0 + w, y2: y0 + h, "class": "line-thin" }));
    svg.appendChild(el("circle", { cx: px(o.N), cy: py(o.L), r: 6, "class": "f-yellow" }));
    svg.appendChild(el("text", { x: px(o.N), y: y0 + h + 16, "text-anchor": "middle", "class": "t-xs" }, "optimum " + human(o.N)));
    svg.appendChild(el("circle", { cx: px(N), cy: py(L), r: 5, "class": "f-orange" }));
    svg.appendChild(el("text", { x: x0, y: y0 + h + 32, "class": "t-xs t-muted" }, "model size N at fixed compute (log scale)"));
    var Ce = equivalentBudget(f, C, L);
    var rows = [
      ["Compute-optimal model size N", human(o.N)], ["Compute-optimal tokens D", human(o.D)], ["Tokens per parameter at the optimum", (o.D / o.N).toFixed(1)],
      ["Predicted loss at the optimum", o.L.toFixed(3)], ["Your choice: N and D", human(N) + " and " + human(D)],
      ["Predicted loss for your choice", L.toFixed(3) + " (+" + (L - o.L).toFixed(3) + ")"],
      ["Budget the optimum needs to match it", mult === 1 ? "same" : sci(Ce) + " (" + (100 * Ce / C).toFixed(0) + "% of yours)"]
    ];
    tbl.innerHTML = "";
    rows.forEach(function (row) {
      var tr = document.createElement("tr"), a = document.createElement("td"), b = document.createElement("td");
      a.textContent = row[0]; b.textContent = row[1]; tr.appendChild(a); tr.appendChild(b); tbl.appendChild(tr);
    });
  }
  [cIn, mIn].forEach(function (c) { c.addEventListener("input", draw); });
  fitSel.addEventListener("change", draw);
  draw();
})();
