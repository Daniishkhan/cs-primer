/* Reliability-diagram lab (A1 chapter 15).
   A synthetic population where the true log-odds z of each case is known. A scorer reports sigmoid(a * z):
   a = 1 is perfectly calibrated, a > 1 is overconfident, a < 1 is underconfident. The reader picks a, a size for the
   calibration set and a recalibration method (none, Platt scaling, isotonic regression); the page draws the reliability
   diagram on 20,000 test cases and reports ECE, Brier score, log loss, AUC and expected cost per case. */
(function () {
  "use strict";
  var root = document.getElementById("ml15-reliability");
  if (!root) return;

  var NS = "http://www.w3.org/2000/svg";
  var NTEST = 20000, BINS = 10, C_FN = 100, C_FP = 5;
  var aIn = root.querySelector("[data-act=a]"), aOut = root.querySelector("[data-act=a-out]");
  var mSel = root.querySelector("[data-act=m]"), methodSel = root.querySelector("[data-act=method]");
  var svg = root.querySelector(".ml15-chart"), table = root.querySelector(".ml15-table"), note = root.querySelector(".ml15-note");

  function mulberry32(a) {
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      var t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  function gauss(r) { var u = 1 - r(), v = r(); return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v); }
  function sigmoid(z) { return 1 / (1 + Math.exp(-z)); }
  function logit(p) { p = Math.min(1 - 1e-6, Math.max(1e-6, p)); return Math.log(p / (1 - p)); }

  function draw(n, seed) {
    var r = mulberry32(seed), z = [], y = [], i;
    for (i = 0; i < n; i++) { var zi = -1.6 + 1.7 * gauss(r); z.push(zi); y.push(r() < sigmoid(zi) ? 1 : 0); }
    return { z: z, y: y };
  }
  var test = draw(NTEST, 4242);

  function plattFit(s, y) {  // logistic regression of y on logit(s): two parameters, damped Newton steps
    var A = 0, B = 1, it, i, xs = s.map(logit);
    function loss(a, b) {
      var l = 0;
      for (var k = 0; k < xs.length; k++) { var p = Math.min(1 - 1e-9, Math.max(1e-9, sigmoid(a + b * xs[k]))); l -= y[k] ? Math.log(p) : Math.log(1 - p); }
      return l;
    }
    for (it = 0; it < 30; it++) {
      var g0 = 0, g1 = 0, h00 = 1e-6, h01 = 0, h11 = 1e-6;
      for (i = 0; i < xs.length; i++) {
        var p = sigmoid(A + B * xs[i]), e = p - y[i], w = p * (1 - p);
        g0 += e; g1 += e * xs[i]; h00 += w; h01 += w * xs[i]; h11 += w * xs[i] * xs[i];
      }
      var det = h00 * h11 - h01 * h01;
      if (Math.abs(det) < 1e-12) break;
      var dA = (h11 * g0 - h01 * g1) / det, dB = (-h01 * g0 + h00 * g1) / det, step = 1, base = loss(A, B);
      while (step > 1e-4 && loss(A - step * dA, B - step * dB) > base) step /= 2;
      A -= step * dA; B -= step * dB;
      if (Math.abs(step * dA) + Math.abs(step * dB) < 1e-7) break;
    }
    return function (q) { return sigmoid(A + B * logit(q)); };
  }
  function isoFit(s, y) {  // pool adjacent violators, step function between the pooled block ends
    var idx = s.map(function (_, i) { return i; }).sort(function (a, b) { return s[a] - s[b]; });
    var vals = [], wts = [], ends = [], i;
    for (i = 0; i < idx.length; i++) {
      vals.push(y[idx[i]]); wts.push(1); ends.push(s[idx[i]]);
      while (vals.length > 1 && vals[vals.length - 2] > vals[vals.length - 1]) {
        var n = vals.length, w = wts[n - 2] + wts[n - 1], v = (vals[n - 2] * wts[n - 2] + vals[n - 1] * wts[n - 1]) / w, e = ends[n - 1];
        vals.length = n - 1; wts.length = n - 1; ends.length = n - 1;
        vals[n - 2] = v; wts[n - 2] = w; ends[n - 2] = e;
      }
    }
    return function (q) {
      var lo = 0, hi = ends.length - 1;
      if (q <= ends[0]) return vals[0];
      if (q >= ends[hi]) return vals[hi];
      while (hi - lo > 1) { var mid = (lo + hi) >> 1; if (ends[mid] < q) lo = mid; else hi = mid; }
      var t = (q - ends[lo]) / (ends[hi] - ends[lo] || 1);
      return vals[lo] + t * (vals[hi] - vals[lo]);
    };
  }

  function auc(p, y) {  // rank-sum with tie handling
    var idx = p.map(function (_, i) { return i; }).sort(function (a, b) { return p[a] - p[b]; });
    var ranks = new Array(p.length), i = 0, n1 = 0, sum = 0;
    while (i < idx.length) {
      var j = i;
      while (j + 1 < idx.length && p[idx[j + 1]] === p[idx[i]]) j++;
      var r = (i + j) / 2 + 1;
      for (var k = i; k <= j; k++) ranks[idx[k]] = r;
      i = j + 1;
    }
    for (i = 0; i < y.length; i++) if (y[i]) { n1++; sum += ranks[i]; }
    var n0 = y.length - n1;
    return (sum - n1 * (n1 + 1) / 2) / (n1 * n0);
  }

  function metrics(p, y) {
    var n = p.length, i, brier = 0, ll = 0, cost = 0, t = C_FP / (C_FP + C_FN);
    var cnt = [], sp = [], sy = [];
    for (i = 0; i < BINS; i++) { cnt.push(0); sp.push(0); sy.push(0); }
    for (i = 0; i < n; i++) {
      var pi = Math.min(1 - 1e-6, Math.max(1e-6, p[i])), b = Math.min(BINS - 1, Math.floor(p[i] * BINS));
      brier += (p[i] - y[i]) * (p[i] - y[i]); ll -= y[i] ? Math.log(pi) : Math.log(1 - pi);
      cnt[b]++; sp[b] += p[i]; sy[b] += y[i];
      if (p[i] >= t) { if (!y[i]) cost += C_FP; } else if (y[i]) cost += C_FN;
    }
    var ece = 0, pts = [];
    for (i = 0; i < BINS; i++) if (cnt[i]) { ece += cnt[i] / n * Math.abs(sp[i] / cnt[i] - sy[i] / cnt[i]); pts.push({ x: sp[i] / cnt[i], y: sy[i] / cnt[i], n: cnt[i] }); }
    return { ece: ece, brier: brier / n, ll: ll / n, auc: auc(p, y), cost: cost / n, pts: pts };
  }

  function el(tag, attrs, text) {
    var e = document.createElementNS(NS, tag), k;
    for (k in attrs) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    return e;
  }

  function update() {
    var a = parseInt(aIn.value, 10) / 100, m = parseInt(mSel.value, 10), method = methodSel.value, i;
    aOut.textContent = a.toFixed(2);
    var raw = test.z.map(function (z) { return sigmoid(a * z); });
    var cal = draw(m, 777), calRaw = cal.z.map(function (z) { return sigmoid(a * z); });
    var f = method === "platt" ? plattFit(calRaw, cal.y) : method === "iso" ? isoFit(calRaw, cal.y) : null;
    var fixed = f ? raw.map(f) : raw;
    var m0 = metrics(raw, test.y), m1 = metrics(fixed, test.y);

    var W = 360, H = 330, L = 44, T = 14, S = 280;
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    svg.setAttribute("viewBox", "0 0 " + W + " " + H);
    svg.appendChild(el("rect", { x: L, y: T, width: S, height: S, "class": "box", opacity: 0.35 }));
    [0, 0.25, 0.5, 0.75, 1].forEach(function (v) {
      svg.appendChild(el("text", { x: L + v * S, y: T + S + 14, "text-anchor": "middle", "class": "t-xs t-faint" }, v.toFixed(2).replace("0.00", "0").replace("1.00", "1")));
      svg.appendChild(el("text", { x: L - 6, y: T + S - v * S + 4, "text-anchor": "end", "class": "t-xs t-faint" }, v.toFixed(2).replace("0.00", "0").replace("1.00", "1")));
    });
    svg.appendChild(el("text", { x: L + S / 2, y: H - 4, "text-anchor": "middle", "class": "t-xs t-muted" }, "predicted probability"));
    svg.appendChild(el("text", { x: 11, y: T + S / 2, "text-anchor": "middle", "class": "t-xs t-muted", transform: "rotate(-90 11 " + (T + S / 2) + ")" }, "observed frequency"));
    svg.appendChild(el("line", { x1: L, y1: T + S, x2: L + S, y2: T, "class": "line-dash" }));
    function curve(pts, cls, dot) {
      var d = "", k;
      for (k = 0; k < pts.length; k++) d += (k ? "L" : "M") + (L + pts[k].x * S).toFixed(1) + "," + (T + S - pts[k].y * S).toFixed(1);
      svg.appendChild(el("path", { d: d, fill: "none", "class": cls }));
      pts.forEach(function (p) { svg.appendChild(el("circle", { cx: L + p.x * S, cy: T + S - p.y * S, r: Math.max(2.5, Math.min(7, Math.sqrt(p.n) / 9)), "class": dot })); });
    }
    if (f) curve(m0.pts, "line-thin s-orange", "f-orange");
    curve(m1.pts, "line s-blue sw-2", "f-blue");
    svg.appendChild(el("text", { x: L + 8, y: T + 14, "class": "t-xs t-bold tc-blue" }, f ? "after " + (method === "iso" ? "isotonic" : "Platt") : "model as it is"));
    if (f) svg.appendChild(el("text", { x: L + 8, y: T + 28, "class": "t-xs t-bold tc-orange" }, "before"));
    svg.appendChild(el("text", { x: L + S - 6, y: T + S - 8, "text-anchor": "end", "class": "t-xs t-faint" }, "dashed: perfect calibration"));

    function row(name, a1, b1, d) { return "<tr><th>" + name + "</th><td>" + a1.toFixed(d) + "</td><td>" + b1.toFixed(d) + "</td></tr>"; }
    table.innerHTML = "<table class='ml15-t'><thead><tr><th></th><th>raw scores</th><th>" + (f ? "recalibrated" : "(no change)") + "</th></tr></thead><tbody>" +
      row("ECE", m0.ece, m1.ece, 4) + row("Brier score", m0.brier, m1.brier, 4) + row("Log loss", m0.ll, m1.ll, 4) + row("ROC AUC", m0.auc, m1.auc, 4) +
      row("Cost per case at threshold 0.048", m0.cost, m1.cost, 3) + "</tbody></table>";
    var msg;
    if (Math.abs(a - 1) < 0.03 && !f) msg = "The scorer reports its true log-odds, so the points sit on the diagonal. Move the dial to see what over- and under-confidence look like.";
    else if (a > 1 && !f) msg = "Overconfident: low scores are too low and high scores too high, so the curve is a flattened S around the diagonal. Pick a recalibration method.";
    else if (a < 1 && !f) msg = "Underconfident: scores huddle near the base rate, so the curve is steeper than the diagonal.";
    else if (method === "iso" && m <= 1000) msg = "Isotonic regression has many free steps. With a small calibration set they chase noise, so the curve is jagged and the gain is smaller than Platt's. Raise the set size.";
    else msg = "Recalibration is a monotone map of the score, so ranking is unchanged (the AUC row) while the probabilities, ECE, Brier and log loss improve. Cost at the formula threshold improves because the threshold assumes honest probabilities.";
    note.textContent = msg;
  }
  aIn.addEventListener("input", update);
  mSel.addEventListener("change", update);
  methodSel.addEventListener("change", update);
  update();
})();
