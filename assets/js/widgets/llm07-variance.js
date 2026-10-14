/* Gradient-variance explorer (A3 chapter 07).
   A softmax policy over 4 actions (uniform to start) with mean rewards 0.2, 0.4, 0.6, 0.8 and Gaussian
   noise (sd 0.3). The widget draws 2000 independent REINFORCE gradient estimates for the logit of the
   best action, each from a batch of B samples, and shows their spread. A baseline is subtracted from
   each reward before it multiplies the score. The true gradient is 0.075 when the reward shift is 0. */
(function () {
  "use strict";
  var root = document.getElementById("llm07-variance");
  if (!root) return;

  var NS = "http://www.w3.org/2000/svg";
  var MU = [0.2, 0.4, 0.6, 0.8], SIGMA = 0.3, K = 4, TRIALS = 2000, BINS = 41;
  var q = function (s) { return root.querySelector(s); };
  var baseSel = q("[data-act=baseline]"), shiftIn = q("[data-act=shift]"), batchIn = q("[data-act=batch]");
  var shiftOut = q("[data-act=shift-out]"), batchOut = q("[data-act=batch-out]");
  var svg = q(".llm07-chart"), out = q(".llm07-summary");

  function mulberry32(a) {
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      var t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  function gauss(rng) { var u = 1 - rng(), v = rng(); return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v); }
  function el(tag, attrs, text) {
    var e = document.createElementNS(NS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    return e;
  }

  /* Gradient estimates for the best action's logit under one baseline rule. The same seed is used for
     every rule, so the samples are identical and only the baseline differs. */
  function estimates(rule, shift, B) {
    var rng = mulberry32(4242), res = [], t, i;
    var meanR = 0; for (i = 0; i < K; i++) meanR += MU[i] / K; meanR += shift;
    for (t = 0; t < TRIALS; t++) {
      var acts = [], R = [], sum = 0;
      for (i = 0; i < B; i++) {
        var a = Math.floor(rng() * K);
        var r = MU[a] + shift + SIGMA * gauss(rng);
        acts.push(a); R.push(r); sum += r;
      }
      var g = 0;
      for (i = 0; i < B; i++) {
        var b = 0;
        if (rule === "mean") b = sum / B;
        else if (rule === "loo") b = (sum - R[i]) / (B - 1);
        else if (rule === "value") b = meanR;
        var score = (acts[i] === K - 1 ? 1 : 0) - 1 / K;      // d log pi(a) / d logit_best, uniform policy
        g += (R[i] - b) * score;
      }
      res.push(g / B);
    }
    return res;
  }
  function stats(xs) {
    var m = 0, i; for (i = 0; i < xs.length; i++) m += xs[i]; m /= xs.length;
    var v = 0, pos = 0; for (i = 0; i < xs.length; i++) { v += (xs[i] - m) * (xs[i] - m); if (xs[i] > 0) pos++; }
    return { mean: m, sd: Math.sqrt(v / xs.length), pos: pos / xs.length };
  }

  var NAMES = { none: "no baseline", mean: "batch mean", loo: "leave-one-out", value: "true value (oracle)" };

  function draw() {
    var shift = parseFloat(shiftIn.value), B = parseInt(batchIn.value, 10), rule = baseSel.value;
    shiftOut.textContent = "+" + shift.toFixed(1);
    batchOut.textContent = String(B);
    var cur = estimates(rule, shift, B), ref = estimates("none", shift, B);
    var sc = stats(cur), sr = stats(ref), truth = 0.25 * (MU[3] + shift - (MU[0] + MU[1] + MU[2] + MU[3]) / 4 - shift);
    var half = Math.max(0.15, 3.2 * sc.sd);           // axis centred on the true value, scaled to the chosen rule
    var lo = truth - half, hi = truth + half, w = (hi - lo) / BINS;
    function hist(xs) {
      var h = [], i; for (i = 0; i < BINS; i++) h.push(0);
      xs.forEach(function (x) { var k = Math.floor((x - lo) / w); if (k >= 0 && k < BINS) h[k]++; });
      return h;
    }
    var hc = hist(cur), hr = hist(ref), maxH = 1, i;
    for (i = 0; i < BINS; i++) maxH = Math.max(maxH, hc[i], hr[i]);
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    var W = 700, H = 250, L = 40, R = 12, T = 14, Bm = 40, pw = W - L - R, ph = H - T - Bm;
    function xOf(v) { return L + pw * (v - lo) / (hi - lo); }
    svg.appendChild(el("line", { x1: L, y1: T + ph, x2: W - R, y2: T + ph, "class": "line" }));
    for (i = 0; i <= 4; i++) {
      var tv = lo + (hi - lo) * i / 4;
      svg.appendChild(el("line", { x1: xOf(tv), y1: T + ph, x2: xOf(tv), y2: T + ph + 4, "class": "line-thin" }));
      svg.appendChild(el("text", { x: xOf(tv), y: T + ph + 18, "text-anchor": "middle", "class": "t-xs t-muted" }, tv.toFixed(2)));
    }
    svg.appendChild(el("text", { x: L + pw / 2, y: H - 4, "text-anchor": "middle", "class": "t-xs t-muted" }, "gradient estimate for the best action's logit"));
    svg.appendChild(el("text", { x: 12, y: T + ph / 2, "class": "t-xs t-muted", transform: "rotate(-90 12 " + (T + ph / 2) + ")", "text-anchor": "middle" }, "share of 2000 trials"));
    var bw = pw / BINS;
    for (i = 0; i < BINS; i++) {
      var hgt = ph * hc[i] / maxH;
      if (hc[i]) svg.appendChild(el("rect", { x: L + i * bw + 1, y: T + ph - hgt, width: Math.max(1, bw - 2), height: hgt, "class": "f-blue", opacity: "0.75" }));
    }
    if (rule !== "none") {
      var d = "";
      for (i = 0; i < BINS; i++) {
        var yy = T + ph - ph * hr[i] / maxH;
        d += (i ? "L" : "M") + (L + i * bw).toFixed(1) + "," + yy.toFixed(1) + "L" + (L + (i + 1) * bw).toFixed(1) + "," + yy.toFixed(1);
      }
      svg.appendChild(el("path", { d: d, fill: "none", "class": "s-red sw-2", "stroke-dasharray": "5 3" }));
    }
    var tx = xOf(truth);
    svg.appendChild(el("line", { x1: tx, y1: T, x2: tx, y2: T + ph, "class": "line s-green sw-2" }));
    svg.appendChild(el("text", { x: tx + 5, y: T + 11, "class": "t-xs tc-green t-bold" }, "true gradient " + truth.toFixed(3)));
    var msg = "Blue: " + NAMES[rule] + ", spread (sd) " + sc.sd.toFixed(3) + ", mean " + sc.mean.toFixed(3) +
      ", correct sign in " + Math.round(100 * sc.pos) + "% of trials.";
    if (rule !== "none") msg += " Dashed red: no baseline, sd " + sr.sd.toFixed(3) + ", correct sign " + Math.round(100 * sr.pos) +
      "% (drawn only where it fits the axis).";
    out.textContent = msg;
  }

  [shiftIn, batchIn].forEach(function (c) { c.addEventListener("input", draw); });
  baseSel.addEventListener("change", draw);
  draw();
})();
