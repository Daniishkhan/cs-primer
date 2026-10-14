/* Peeking simulator (A0 chapter 15).
   Simulate many A/B tests of a 10% conversion rate, check each at K evenly spaced looks,
   and compare four stopping rules on the same data: look once at the end; stop at the first
   p < 0.05; Bonferroni (alpha / K at every look); and a Pocock-style constant boundary.
   With no true lift, every "significant" result is a false positive. */
(function () {
  "use strict";
  var root = document.getElementById("mlf15-peeking");
  if (!root) return;
  var NS = "http://www.w3.org/2000/svg";
  function q(a) { return root.querySelector("[data-act=" + a + "]"); }
  var kIn = q("looks"), nIn = q("users"), lIn = q("lift"), paths = q("paths"), bars = q("bars"), out = q("out");
  var E = 800, BASE = 0.10, seed = 2026;
  // Constant two-sided boundary c(K) for 5% overall error with K equally spaced looks, found by simulation (K = 1 to 20).
  var POCOCK = [1.96, 2.18, 2.29, 2.36, 2.41, 2.45, 2.49, 2.51, 2.54, 2.56, 2.57, 2.59, 2.60, 2.61, 2.63, 2.64, 2.65, 2.65, 2.66, 2.67];

  function mulberry32(a) {
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      var t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  function erf(x) {
    var s = x < 0 ? -1 : 1, t; x = Math.abs(x);
    t = 1 / (1 + 0.3275911 * x);
    return s * (1 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * Math.exp(-x * x));
  }
  function cdf(z) { return 0.5 * (1 + erf(z / Math.SQRT2)); }
  function invCdf(p) { var lo = -8, hi = 8, i, mid; for (i = 0; i < 60; i++) { mid = (lo + hi) / 2; if (cdf(mid) < p) lo = mid; else hi = mid; } return (lo + hi) / 2; }
  function el(tag, attrs, text) {
    var e = document.createElementNS(NS, tag), k;
    for (k in attrs) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    return e;
  }
  function clear(n) { while (n.firstChild) n.removeChild(n.firstChild); }

  function run() {
    var K = +kIn.value, N = +nIn.value, lift = +lIn.value / 100, pB = BASE * (1 + lift), i, k, u;
    q("looks-out").textContent = K; q("users-out").textContent = N.toLocaleString("en-GB"); q("lift-out").textContent = (+lIn.value).toFixed(0) + "%";
    var rng = mulberry32(seed), block = Math.floor(N / K);
    var zB = invCdf(1 - 0.025 / K), zP = POCOCK[K - 1];
    var cnt = { end: 0, peek: 0, bonf: 0, poc: 0 }, samples = [];
    for (i = 0; i < E; i++) {
      var a = 0, b = 0, hitPeek = false, hitBonf = false, hitPoc = false, zl = 0, zs = [];
      for (k = 1; k <= K; k++) {
        for (u = 0; u < block; u++) { if (rng() < BASE) a++; if (rng() < pB) b++; }
        var n = block * k, pa = a / n, pb = b / n, pool = (pa + pb) / 2, den = Math.sqrt(2 * pool * (1 - pool) / n);
        zl = den > 0 ? (pb - pa) / den : 0; zs.push(zl);
        if (Math.abs(zl) > 1.96) hitPeek = true;
        if (Math.abs(zl) > zB) hitBonf = true;
        if (Math.abs(zl) > zP) hitPoc = true;
      }
      if (Math.abs(zl) > 1.96) cnt.end++;
      if (hitPeek) cnt.peek++; if (hitBonf) cnt.bonf++; if (hitPoc) cnt.poc++;
      if (i < 12) samples.push({ z: zs, hit: hitPeek });
    }
    drawPaths(samples, K, zP);
    drawBars(cnt, lift);
  }
  function drawPaths(samples, K, zP) {
    var W = 360, H = 250, L = 34, R = 8, T = 14, B = 30, i, k;
    function X(k) { return L + (K === 1 ? 0.5 : (k - 1) / (K - 1)) * (W - L - R); }
    function Y(z) { z = Math.max(-4, Math.min(4, z)); return T + (4 - z) / 8 * (H - T - B); }
    clear(paths);
    paths.appendChild(el("line", { x1: L, y1: H - B, x2: W - R, y2: H - B, "class": "line-thin" }));
    paths.appendChild(el("line", { x1: L, y1: T, x2: L, y2: H - B, "class": "line-thin" }));
    [-3, -2, -1, 0, 1, 2, 3].forEach(function (t) { paths.appendChild(el("text", { x: L - 5, y: Y(t) + 4, "text-anchor": "end", "class": "t-xs t-muted" }, String(t))); });
    [1.96, -1.96].forEach(function (v) { paths.appendChild(el("line", { x1: L, y1: Y(v), x2: W - R, y2: Y(v), "class": "line-dash" })); });
    [zP, -zP].forEach(function (v) { paths.appendChild(el("line", { x1: L, y1: Y(v), x2: W - R, y2: Y(v), style: "stroke:var(--green);stroke-width:2" })); });
    for (i = 0; i < samples.length; i++) {
      var pts = [];
      for (k = 1; k <= K; k++) pts.push(X(k).toFixed(1) + "," + Y(samples[i].z[k - 1]).toFixed(1));
      if (K === 1) { paths.appendChild(el("circle", { cx: X(1), cy: Y(samples[i].z[0]), r: 3.5, style: "fill:" + (samples[i].hit ? "var(--red)" : "var(--blue)") })); continue; }
      paths.appendChild(el("polyline", { points: pts.join(" "), fill: "none", style: "stroke:" + (samples[i].hit ? "var(--red)" : "var(--blue)") + ";stroke-width:" + (samples[i].hit ? 2 : 1) + ";opacity:" + (samples[i].hit ? 0.95 : 0.5) }));
    }
    paths.appendChild(el("text", { x: (L + W - R) / 2, y: H - 6, "text-anchor": "middle", "class": "t-xs t-muted" }, "look number (first 12 experiments)"));
    paths.appendChild(el("text", { x: W - R, y: T - 3, "text-anchor": "end", "class": "t-xs t-muted" }, "dashed: |z| = 1.96   green: Pocock-style " + zP.toFixed(2)));
  }
  function drawBars(cnt, lift) {
    var W = 360, H = 250, L = 150, R = 40, T = 14, i;
    var rows = [["look once, at the end", cnt.end, "var(--blue)"], ["stop at first p < 0.05", cnt.peek, "var(--red)"], ["Bonferroni, alpha / K", cnt.bonf, "var(--orange)"], ["Pocock-style boundary", cnt.poc, "var(--green)"]];
    clear(bars);
    var top = 0; rows.forEach(function (r) { if (r[1] / E > top) top = r[1] / E; });
    var maxv = Math.max(0.3, Math.ceil(top * 10 + 0.5) / 10);
    function X(v) { return L + v / maxv * (W - L - R); }
    rows.forEach(function (r, j) {
      var y = T + 10 + j * 52, v = r[1] / E;
      bars.appendChild(el("text", { x: L - 8, y: y + 20, "text-anchor": "end", "class": "t-xs" }, r[0]));
      bars.appendChild(el("rect", { x: L, y: y, width: Math.max(1, X(v) - L), height: 28, style: "fill:" + r[2] }));
      bars.appendChild(el("text", { x: X(v) + 6, y: y + 19, "class": "t-sm t-bold" }, (v * 100).toFixed(1) + "%"));
    });
    if (lift === 0) {
      bars.appendChild(el("line", { x1: X(0.05), y1: T, x2: X(0.05), y2: H - 26, "class": "line-dash" }));
      bars.appendChild(el("text", { x: X(0.05), y: H - 12, "text-anchor": "middle", "class": "t-xs t-muted" }, "5% target"));
    }
    clear(out);
    var se = 1.96 * Math.sqrt(0.05 * 0.95 / E) * 100;
    [[lift === 0 ? "false-positive rate if you peek" : "share declared significant if you peek", (cnt.peek / E * 100).toFixed(1) + "%"],
     [lift === 0 ? "false-positive rate if you look once" : "power if you look once", (cnt.end / E * 100).toFixed(1) + "%"],
     ["simulated experiments", String(E)], ["rough noise on each bar (95%)", "about ±" + se.toFixed(1) + " points"]].forEach(function (r) {
      var d = document.createElement("div"); d.innerHTML = r[0] + " = <b></b>"; d.querySelector("b").textContent = r[1]; out.appendChild(d);
    });
  }
  [kIn, nIn, lIn].forEach(function (c) { c.addEventListener("input", run); });
  q("rerun").addEventListener("click", function () { seed = (seed * 1103515245 + 12345) % 2147483647; run(); });
  run();
})();
