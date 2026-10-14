/* Threshold and cost explorer (A1 chapter 02).
   A fixed, seeded population of scored cases. The reader moves the decision threshold and the
   costs of the two kinds of mistake, and sees the confusion matrix, precision, recall, F1 and
   total cost, with the cost-minimising and F1-maximising thresholds marked. */
(function () {
  "use strict";
  var root = document.getElementById("ml02-threshold");
  if (!root) return;

  var NS = "http://www.w3.org/2000/svg";
  var N = 5000, BINS = 25;
  var thrIn = root.querySelector("[data-act=thr]"), thrOut = root.querySelector("[data-act=thr-out]");
  var prevSel = root.querySelector("[data-act=prev]");
  var fnIn = root.querySelector("[data-act=cfn]"), fnOut = root.querySelector("[data-act=cfn-out]");
  var fpIn = root.querySelector("[data-act=cfp]"), fpOut = root.querySelector("[data-act=cfp-out]");
  var svg = root.querySelector(".ml02-chart");
  var cm = root.querySelector(".ml02-cm");
  var summary = root.querySelector(".ml02-summary");

  function mulberry32(a) {
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      var t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  function gauss(rng) { var u = 1 - rng(), v = rng(); return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v); }
  function sigmoid(z) { return 1 / (1 + Math.exp(-z)); }

  // Score = sigmoid of a noisy signal; positives sit higher on average.
  function build(prev) {
    var rng = mulberry32(2026), nPos = Math.max(1, Math.round(N * prev)), data = [], i;
    for (i = 0; i < N; i++) {
      var pos = i < nPos;
      data.push({ pos: pos, s: sigmoid((pos ? 0.9 : -1.3) + 1.1 * gauss(rng)) });
    }
    return data;
  }

  function counts(data, t) {
    var tp = 0, fp = 0, fn = 0, tn = 0;
    for (var i = 0; i < data.length; i++) {
      var d = data[i], flag = d.s >= t;
      if (flag && d.pos) tp++; else if (flag) fp++; else if (d.pos) fn++; else tn++;
    }
    return { tp: tp, fp: fp, fn: fn, tn: tn };
  }
  function el(tag, attrs, text) {
    var e = document.createElementNS(NS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    return e;
  }
  function pct(x) { return isFinite(x) ? (100 * x).toFixed(1) + "%" : "n/a"; }
  function money(x) { return Math.round(x).toLocaleString("en-GB"); }

  function update() {
    var prev = parseFloat(prevSel.value), data = build(prev);
    var t = parseInt(thrIn.value, 10) / 100, cFN = parseInt(fnIn.value, 10), cFP = parseInt(fpIn.value, 10);
    thrOut.textContent = t.toFixed(2); fnOut.textContent = String(cFN); fpOut.textContent = String(cFP);

    // sweep for the best F1 and best cost thresholds
    var bestF1 = 0, bestF1T = 0.5, bestC = Infinity, bestCT = 0.5, g;
    for (g = 1; g <= 99; g++) {
      var tt = g / 100, c = counts(data, tt);
      var f1 = c.tp ? 2 * c.tp / (2 * c.tp + c.fp + c.fn) : 0, cost = c.fp * cFP + c.fn * cFN;
      if (f1 > bestF1) { bestF1 = f1; bestF1T = tt; }
      if (cost < bestC) { bestC = cost; bestCT = tt; }
    }

    // histogram of scores by class (square-root height so rare positives stay visible)
    var hp = [], hn = [], i, maxH = 0;
    for (i = 0; i < BINS; i++) { hp.push(0); hn.push(0); }
    for (i = 0; i < data.length; i++) {
      var b = Math.min(BINS - 1, Math.floor(data[i].s * BINS));
      if (data[i].pos) hp[b]++; else hn[b]++;
    }
    for (i = 0; i < BINS; i++) maxH = Math.max(maxH, hp[i], hn[i]);
    var W = 700, H = 250, L = 30, R = 10, T = 14, B = 34, pw = W - L - R, ph = H - T - B, bw = pw / BINS;
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    svg.setAttribute("viewBox", "0 0 " + W + " " + H);
    svg.appendChild(el("line", { x1: L, y1: T + ph, x2: W - R, y2: T + ph, "class": "line-thin" }));
    [0, 0.25, 0.5, 0.75, 1].forEach(function (v) {
      svg.appendChild(el("text", { x: L + v * pw, y: T + ph + 16, "text-anchor": "middle", "class": "t-xs t-faint" }, v.toFixed(2)));
    });
    svg.appendChild(el("text", { x: L + pw / 2, y: H - 3, "text-anchor": "middle", "class": "t-xs t-muted" }, "model score (higher means more suspicious)"));
    for (i = 0; i < BINS; i++) {
      var hN = ph * Math.sqrt(hn[i] / maxH), hP = ph * Math.sqrt(hp[i] / maxH);
      svg.appendChild(el("rect", { x: (L + i * bw + 1).toFixed(1), y: (T + ph - hN).toFixed(1), width: (bw / 2 - 1).toFixed(1), height: Math.max(0, hN).toFixed(1), "class": "f-blue", opacity: 0.85 }));
      svg.appendChild(el("rect", { x: (L + i * bw + bw / 2).toFixed(1), y: (T + ph - hP).toFixed(1), width: (bw / 2 - 1).toFixed(1), height: Math.max(0, hP).toFixed(1), "class": "f-red", opacity: 0.9 }));
    }
    function vline(v, cls, label, yy, anchor) {
      var x = L + v * pw;
      svg.appendChild(el("line", { x1: x, y1: T, x2: x, y2: T + ph, "class": cls }));
      svg.appendChild(el("text", { x: x + (anchor === "end" ? -4 : 4), y: yy, "text-anchor": anchor, "class": "t-xs t-bold" }, label));
    }
    vline(bestCT, "line-dash s-green", "min cost " + bestCT.toFixed(2), T + 24, bestCT > 0.8 ? "end" : "start");
    vline(bestF1T, "line-dash s-purple", "max F1 " + bestF1T.toFixed(2), T + 38, bestF1T > 0.8 ? "end" : "start");
    vline(t, "line s-yellow sw-3", "your threshold", T + 10, t > 0.8 ? "end" : "start");
    svg.appendChild(el("text", { x: L + 4, y: T + 10, "class": "t-xs tc-blue t-bold" }, "legitimate"));
    svg.appendChild(el("text", { x: L + 4, y: T + 24, "class": "t-xs tc-red t-bold" }, "fraud (bar heights on a square-root scale)"));

    var c0 = counts(data, t), prec = c0.tp / (c0.tp + c0.fp), rec = c0.tp / (c0.tp + c0.fn);
    var f1v = c0.tp ? 2 * c0.tp / (2 * c0.tp + c0.fp + c0.fn) : 0, cost0 = c0.fp * cFP + c0.fn * cFN;
    cm.innerHTML = "<table class='ml02-t'><thead><tr><th></th><th>Actually fraud</th><th>Actually legitimate</th></tr></thead><tbody>" +
      "<tr><th>Flagged</th><td>" + c0.tp + " <small>caught</small></td><td>" + c0.fp + " <small>false alarms</small></td></tr>" +
      "<tr><th>Not flagged</th><td>" + c0.fn + " <small>missed</small></td><td>" + c0.tn + " <small>correctly passed</small></td></tr></tbody></table>";
    summary.textContent = "Precision " + pct(prec) + ", recall " + pct(rec) + ", F1 " + f1v.toFixed(3) + ", accuracy " + pct((c0.tp + c0.tn) / N) +
      ". Total cost " + money(cost0) + " (minimum possible on this grid: " + money(bestC) + " at threshold " + bestCT.toFixed(2) + ").";
  }
  [thrIn, fnIn, fpIn].forEach(function (c) { c.addEventListener("input", update); });
  prevSel.addEventListener("change", update);
  update();
})();
