/* Bias-variance explorer (A1 chapter 06).
   The truth is sin(2 pi x). For each of R fresh training sets (n evenly spaced x, noisy y)
   we fit a ridge-penalised polynomial of the chosen degree, then draw all R fits, their
   average, and decompose the expected error on new data into bias^2 + variance + noise. */
(function () {
  "use strict";
  var root = document.getElementById("ml06-biasvar");
  if (!root) return;
  var NS = "http://www.w3.org/2000/svg";
  var R = 40, GRID = 101;

  var degIn = root.querySelector("[data-act=deg]"), degOut = root.querySelector("[data-act=deg-out]");
  var lamIn = root.querySelector("[data-act=lam]"), lamOut = root.querySelector("[data-act=lam-out]");
  var nIn = root.querySelector("[data-act=n]"), nOut = root.querySelector("[data-act=n-out]");
  var sdIn = root.querySelector("[data-act=sd]"), sdOut = root.querySelector("[data-act=sd-out]");
  var newBtn = root.querySelector("[data-act=new]");
  var svg = root.querySelector(".ml06b-plot"), out = root.querySelector(".ml06b-out"), bars = root.querySelector(".ml06b-bars");
  var seed = 2024;

  function mulberry32(a) {
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      var t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  function truth(x) { return Math.sin(2 * Math.PI * x); }
  function feats(x, deg) { var u = 2 * x - 1, r = [], p = 1; for (var k = 0; k <= deg; k++) { r.push(p); p *= u; } return r; }

  /* solve (A'A + lam*D) w = A'y, D = identity except the intercept, by Gaussian elimination */
  function fit(xs, ys, deg, lam) {
    var m = deg + 1, M = [], i, j, k, rows = xs.map(function (x) { return feats(x, deg); });
    for (i = 0; i < m; i++) {
      M.push([]);
      for (j = 0; j < m; j++) {
        var s = 0; for (k = 0; k < xs.length; k++) s += rows[k][i] * rows[k][j];
        if (i === j) s += (i === 0 ? 0 : lam) + 1e-9;
        M[i].push(s);
      }
      var b = 0; for (k = 0; k < xs.length; k++) b += rows[k][i] * ys[k];
      M[i].push(b);
    }
    for (i = 0; i < m; i++) {
      var piv = i;
      for (j = i + 1; j < m; j++) if (Math.abs(M[j][i]) > Math.abs(M[piv][i])) piv = j;
      var tmp = M[i]; M[i] = M[piv]; M[piv] = tmp;
      for (j = i + 1; j < m; j++) {
        var fct = M[j][i] / M[i][i];
        for (k = i; k <= m; k++) M[j][k] -= fct * M[i][k];
      }
    }
    var w = new Array(m);
    for (i = m - 1; i >= 0; i--) {
      var acc = M[i][m]; for (j = i + 1; j < m; j++) acc -= M[i][j] * w[j];
      w[i] = acc / M[i][i];
    }
    return w;
  }
  function predict(w, x) { var f = feats(x, w.length - 1), s = 0; for (var i = 0; i < w.length; i++) s += w[i] * f[i]; return s; }
  function el(tag, attrs, parent) {
    var e = document.createElementNS(NS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
  }
  function lamValue() { var v = parseFloat(lamIn.value); return v <= 0 ? 0 : Math.pow(10, -5 + 5.5 * v); }
  function fmt(v) { return v >= 100 ? v.toFixed(0) : v >= 10 ? v.toFixed(1) : v.toFixed(3); }

  function run() {
    var deg = parseInt(degIn.value, 10), n = parseInt(nIn.value, 10), sd = parseFloat(sdIn.value), lam = lamValue();
    degOut.textContent = String(deg); nOut.textContent = String(n); sdOut.textContent = sd.toFixed(2);
    lamOut.textContent = lam === 0 ? "0 (none)" : lam.toExponential(1);
    var rnd = mulberry32(seed), xs = [], i, r;
    for (i = 0; i < n; i++) xs.push(i / (n - 1));
    function gauss() { return Math.sqrt(-2 * Math.log(1 - rnd())) * Math.cos(2 * Math.PI * rnd()); }
    var grid = [], tr = [];
    for (i = 0; i < GRID; i++) { grid.push(i / (GRID - 1)); tr.push(truth(grid[i])); }
    var preds = [];
    for (r = 0; r < R; r++) {
      var ys = xs.map(function (x) { return truth(x) + sd * gauss(); });
      var w = fit(xs, ys, deg, lam), row = [];
      for (i = 0; i < GRID; i++) row.push(predict(w, grid[i]));
      preds.push(row);
    }
    var mean = [], b2 = 0, vr = 0;
    for (i = 0; i < GRID; i++) {
      var m = 0, v = 0;
      for (r = 0; r < R; r++) m += preds[r][i] / R;
      for (r = 0; r < R; r++) v += (preds[r][i] - m) * (preds[r][i] - m) / R;
      mean.push(m); b2 += (m - tr[i]) * (m - tr[i]) / GRID; vr += v / GRID;
    }
    draw(grid, tr, preds, mean);
    var noise = sd * sd, tot = b2 + vr + noise;
    var verdict = (b2 + vr) < 0.3 * noise ? "Both reducible terms are small: the model is close to the noise floor." :
      b2 > 2 * vr ? "Bias dominates the reducible error: the model is too rigid for this curve." :
      vr > 2 * b2 ? "Variance dominates the reducible error: the fits disagree because each chases its own noise." :
      "Bias and variance are in balance.";
    out.textContent = "bias squared " + fmt(b2) + "  +  variance " + fmt(vr) + "  +  noise " + fmt(noise) + "  =  expected error " + fmt(tot) + ". " + verdict;
    drawBars(b2, vr, noise);
  }

  function draw(grid, tr, preds, mean) {
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    var W = 700, H = 280, L = 40, Rr = 10, T = 10, B = 28;
    var X = function (x) { return L + x * (W - L - Rr); }, Y = function (v) { return T + (1 - (Math.max(-2.2, Math.min(2.2, v)) + 2.2) / 4.4) * (H - T - B); };
    el("line", { x1: L, y1: Y(0), x2: W - Rr, y2: Y(0), "class": "line-thin" }, svg);
    el("line", { x1: L, y1: T, x2: L, y2: H - B, "class": "line" }, svg);
    [-2, -1, 0, 1, 2].forEach(function (v) { var t = el("text", { x: L - 6, y: Y(v) + 4, "text-anchor": "end", "class": "t-xs t-faint" }, svg); t.textContent = v; });
    [0, 0.5, 1].forEach(function (v) { var t = el("text", { x: X(v), y: H - B + 15, "text-anchor": "middle", "class": "t-xs t-faint" }, svg); t.textContent = v; });
    var tx = el("text", { x: (L + W - Rr) / 2, y: H - 2, "text-anchor": "middle", "class": "t-xs t-muted" }, svg); tx.textContent = "x";
    function line(vals, cls, op, wd) {
      var pts = vals.map(function (v, i) { return X(grid[i]).toFixed(1) + "," + Y(v).toFixed(1); }).join(" ");
      el("polyline", { points: pts, fill: "none", "class": cls, "stroke-opacity": op, "stroke-width": wd, "stroke-linejoin": "round" }, svg);
    }
    preds.forEach(function (p) { line(p, "s-blue", 0.25, 1); });
    line(tr, "s-green", 1, 3);
    line(mean, "s-yellow", 1, 3);
    var lg = el("text", { x: L + 10, y: T + 14, "class": "t-xs tc-green t-bold" }, svg); lg.textContent = "true curve";
    var lg2 = el("text", { x: L + 90, y: T + 14, "class": "t-xs tc-yellow t-bold" }, svg); lg2.textContent = "average of the fits";
    var lg3 = el("text", { x: L + 220, y: T + 14, "class": "t-xs tc-blue t-bold" }, svg); lg3.textContent = "40 individual fits";
  }

  function drawBars(b2, vr, noise) {
    while (bars.firstChild) bars.removeChild(bars.firstChild);
    var items = [["bias squared", b2, "f-orange"], ["variance", vr, "f-purple"], ["noise (fixed)", noise, "f-cyan"]];
    var maxV = Math.max(0.4, b2 + vr + noise), W = 700, x = 120, tot = 0;
    items.forEach(function (it, k) {
      var wdt = Math.max(1, (W - 140) * it[1] / maxV);
      el("rect", { x: x, y: 8, width: wdt, height: 22, "class": it[2] }, bars);
      var t = el("text", { x: x + wdt / 2, y: 52 + (k % 2) * 14, "text-anchor": "middle", "class": "t-xs t-muted" }, bars); t.textContent = it[0];
      x += wdt; tot += it[1];
    });
    var lab = el("text", { x: 114, y: 24, "text-anchor": "end", "class": "t-xs t-bold" }, bars); lab.textContent = "total " + fmt(tot);
  }

  [degIn, lamIn, nIn, sdIn].forEach(function (c) { c.addEventListener("input", run); });
  newBtn.addEventListener("click", function () { seed = (seed * 1664525 + 1013904223) | 0; run(); });
  run();
})();
