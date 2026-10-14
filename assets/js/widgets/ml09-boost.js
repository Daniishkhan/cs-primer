/* Gradient-boosting explorer (ML chapter 9).
   40 noisy training points from y = sin(2 pi x) + noise (sd 0.3), 200 validation points.
   Each round fits a small regression tree to the residuals and adds lr * tree. */
(function () {
  "use strict";
  var root = document.getElementById("ml09-boost");
  if (!root) return;
  var NS = "http://www.w3.org/2000/svg", MAXR = 300, NOISE = 0.3;

  function mulberry32(a) {
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      var t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  function gauss(r) {
    var u = 1 - r(), v = r();
    return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
  }
  function truth(x) { return Math.sin(2 * Math.PI * x); }

  var rng = mulberry32(2026), tr = [], va = [], i;
  for (i = 0; i < 40; i++) { var x = rng(); tr.push({ x: x, y: truth(x) + NOISE * gauss(rng) }); }
  tr.sort(function (a, b) { return a.x - b.x; });
  for (i = 0; i < 200; i++) { var x2 = rng(); va.push({ x: x2, y: truth(x2) + NOISE * gauss(rng) }); }

  // regression tree on one feature; rows are {x, r}; returns a nested object
  function build(rows, depth) {
    var n = rows.length, sum = 0, k;
    for (k = 0; k < n; k++) sum += rows[k].r;
    var leaf = { v: sum / n };
    if (depth === 0 || n < 4) return leaf;
    rows = rows.slice().sort(function (a, b) { return a.x - b.x; });
    var tot = sum, left = 0, best = -1, bestI = -1;
    for (k = 0; k < n - 1; k++) {
      left += rows[k].r;
      if (rows[k].x === rows[k + 1].x) continue;
      if (k + 1 < 2 || n - k - 1 < 2) continue;
      var score = left * left / (k + 1) + (tot - left) * (tot - left) / (n - k - 1);
      if (score > best) { best = score; bestI = k; }
    }
    if (bestI < 0) return leaf;
    var t = (rows[bestI].x + rows[bestI + 1].x) / 2;
    return { t: t, l: build(rows.slice(0, bestI + 1), depth - 1), r: build(rows.slice(bestI + 1), depth - 1) };
  }
  function pred(tree, x) { while (tree.l) tree = x <= tree.t ? tree.l : tree.r; return tree.v; }

  var el = {
    lr: root.querySelector("[data-act=lr]"), lrO: root.querySelector("[data-act=lr-out]"),
    depth: root.querySelector("[data-act=depth]"),
    rounds: root.querySelector("[data-act=rounds]"), roundsO: root.querySelector("[data-act=rounds-out]"),
    main: root.querySelector(".mb-main"), curve: root.querySelector(".mb-curve"), out: root.querySelector(".mb-out")
  };
  var trees = [], base = 0, errTr = [], errVa = [], cfg = "";

  function rmse(data, tvals) {
    var s = 0; for (var k = 0; k < data.length; k++) { var d = data[k].y - tvals[k]; s += d * d; }
    return Math.sqrt(s / data.length);
  }
  function fit(lr, depth) {
    var key = lr + "/" + depth; if (key === cfg) return; cfg = key;
    trees = []; errTr = []; errVa = [];
    var ftr = [], fva = [], k, m = 0;
    for (k = 0; k < tr.length; k++) m += tr[k].y; base = m / tr.length;
    for (k = 0; k < tr.length; k++) ftr.push(base);
    for (k = 0; k < va.length; k++) fva.push(base);
    errTr.push(rmse(tr, ftr)); errVa.push(rmse(va, fva));
    for (var r = 0; r < MAXR; r++) {
      var rows = tr.map(function (p, j) { return { x: p.x, r: p.y - ftr[j] }; });
      var tree = build(rows, depth); trees.push(tree);
      for (k = 0; k < tr.length; k++) ftr[k] += lr * pred(tree, tr[k].x);
      for (k = 0; k < va.length; k++) fva[k] += lr * pred(tree, va[k].x);
      errTr.push(rmse(tr, ftr)); errVa.push(rmse(va, fva));
    }
  }
  function F(x, lr, R) { var v = base; for (var r = 0; r < R; r++) v += lr * pred(trees[r], x); return v; }

  function s(tag, attrs, text) {
    var e = document.createElementNS(NS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    return e;
  }
  function clear(n) { while (n.firstChild) n.removeChild(n.firstChild); }

  function drawMain(lr, R) {
    var svg = el.main; clear(svg);
    var W = 420, H = 260, L = 34, Rr = 10, T = 12, B = 30, pw = W - L - Rr, ph = H - T - B;
    function X(x) { return L + x * pw; }
    function Y(y) { return T + ph * (1.7 - y) / 3.4; }
    svg.setAttribute("viewBox", "0 0 " + W + " " + H);
    svg.appendChild(s("line", { x1: L, y1: T + ph, x2: W - Rr, y2: T + ph, "class": "line-thin" }));
    svg.appendChild(s("line", { x1: L, y1: T, x2: L, y2: T + ph, "class": "line-thin" }));
    [-1, 0, 1].forEach(function (v) { svg.appendChild(s("text", { x: L - 6, y: Y(v) + 4, "text-anchor": "end", "class": "t-xs t-faint" }, String(v))); });
    [0, 0.5, 1].forEach(function (v) { svg.appendChild(s("text", { x: X(v), y: T + ph + 16, "text-anchor": "middle", "class": "t-xs t-faint" }, String(v))); });
    svg.appendChild(s("text", { x: L + pw / 2, y: H - 3, "text-anchor": "middle", "class": "t-xs t-muted" }, "x"));
    var d = "", k, N = 160;
    for (k = 0; k <= N; k++) { var xx = k / N; d += (k ? "L" : "M") + X(xx).toFixed(1) + "," + Y(truth(xx)).toFixed(1); }
    svg.appendChild(s("path", { d: d, "class": "line-dash s-green", fill: "none" }));
    tr.forEach(function (p) { svg.appendChild(s("circle", { cx: X(p.x).toFixed(1), cy: Y(p.y).toFixed(1), r: 3.2, "class": "f-cyan" })); });
    d = "";
    for (k = 0; k <= N; k++) { var x3 = k / N; d += (k ? "L" : "M") + X(x3).toFixed(1) + "," + Y(F(x3, lr, R)).toFixed(1); }
    svg.appendChild(s("path", { d: d, "class": "line s-yellow sw-2", fill: "none" }));
    svg.appendChild(s("text", { x: W - Rr - 2, y: T + 10, "text-anchor": "end", "class": "t-xs tc-green" }, "dashed: true curve"));
    svg.appendChild(s("text", { x: W - Rr - 2, y: T + 24, "text-anchor": "end", "class": "t-xs tc-yellow" }, "solid: model"));
  }
  function drawCurve(R) {
    var svg = el.curve; clear(svg);
    var W = 420, H = 260, L = 38, Rr = 10, T = 12, B = 30, pw = W - L - Rr, ph = H - T - B, hi = 1.3;
    function X(r) { return L + pw * r / MAXR; }
    function Y(e) { return T + ph * (1 - Math.min(e, hi) / hi); }
    svg.setAttribute("viewBox", "0 0 " + W + " " + H);
    svg.appendChild(s("line", { x1: L, y1: T + ph, x2: W - Rr, y2: T + ph, "class": "line-thin" }));
    svg.appendChild(s("line", { x1: L, y1: T, x2: L, y2: T + ph, "class": "line-thin" }));
    [0, 0.5, 1].forEach(function (v) { svg.appendChild(s("text", { x: L - 6, y: Y(v) + 4, "text-anchor": "end", "class": "t-xs t-faint" }, String(v))); });
    [0, 100, 200, 300].forEach(function (v) { svg.appendChild(s("text", { x: X(v), y: T + ph + 16, "text-anchor": "middle", "class": "t-xs t-faint" }, String(v))); });
    svg.appendChild(s("text", { x: L + pw / 2, y: H - 3, "text-anchor": "middle", "class": "t-xs t-muted" }, "rounds (RMSE on y axis)"));
    svg.appendChild(s("line", { x1: L, y1: Y(NOISE), x2: W - Rr, y2: Y(NOISE), "class": "line-dash s-green" }));
    svg.appendChild(s("text", { x: W - Rr - 2, y: Y(NOISE) - 4, "text-anchor": "end", "class": "t-xs tc-green" }, "noise floor 0.30"));
    function path(arr, cls) {
      var d = ""; for (var r = 0; r <= MAXR; r++) d += (r ? "L" : "M") + X(r).toFixed(1) + "," + Y(arr[r]).toFixed(1);
      svg.appendChild(s("path", { d: d, "class": cls, fill: "none" }));
    }
    path(errTr, "line s-cyan sw-2"); path(errVa, "line s-red sw-2");
    svg.appendChild(s("line", { x1: X(R), y1: T, x2: X(R), y2: T + ph, "class": "line-thin s-yellow" }));
    svg.appendChild(s("text", { x: L + 120, y: T + 12, "class": "t-xs tc-cyan" }, "training"));
    svg.appendChild(s("text", { x: L + 120, y: T + 26, "class": "t-xs tc-red" }, "validation"));
  }
  function run() {
    var lr = parseFloat(el.lr.value), depth = parseInt(el.depth.value, 10), R = parseInt(el.rounds.value, 10);
    el.lrO.textContent = lr.toFixed(2); el.roundsO.textContent = String(R);
    fit(lr, depth);
    drawMain(lr, R); drawCurve(R);
    var bestR = 0, k; for (k = 1; k <= MAXR; k++) if (errVa[k] < errVa[bestR]) bestR = k;
    el.out.innerHTML = "At <strong>" + R + "</strong> rounds: training RMSE <strong>" + errTr[R].toFixed(3) +
      "</strong>, validation RMSE <strong>" + errVa[R].toFixed(3) + "</strong>. With these settings the validation error is lowest at round <strong>" +
      bestR + "</strong> (" + errVa[bestR].toFixed(3) + "). Stopping there is early stopping.";
  }
  ["input", "change"].forEach(function (ev) {
    el.lr.addEventListener(ev, run); el.depth.addEventListener(ev, run); el.rounds.addEventListener(ev, run);
  });
  run();
})();
