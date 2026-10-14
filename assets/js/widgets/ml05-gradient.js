/* Gradient descent explorer (A1 chapter 05).
   Fits rent = b + w * area to 16 seeded points by batch gradient descent on the
   mean squared error. Left: the data and the current line. Right: the loss
   surface over (w, b) as a shaded grid with the path the optimiser takes.
   Switching "standardise" re-expresses the same problem with a rounder surface. */
(function () {
  "use strict";
  var root = document.getElementById("ml05-gradient");
  if (!root) return;
  var NS = "http://www.w3.org/2000/svg";

  function mulberry32(a) {
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      var t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  var rnd = mulberry32(6), N = 16, xs = [], ys = [];
  function gauss() { return Math.sqrt(-2 * Math.log(1 - rnd())) * Math.cos(2 * Math.PI * rnd()); }
  for (var i = 0; i < N; i++) {
    var a = 30 + 80 * rnd();
    xs.push(a); ys.push(300 + 11 * a + 60 * gauss());
  }
  var mx = 0, my = 0, sx = 0;
  for (i = 0; i < N; i++) { mx += xs[i] / N; my += ys[i] / N; }
  for (i = 0; i < N; i++) sx += (xs[i] - mx) * (xs[i] - mx) / N;
  sx = Math.sqrt(sx);

  /* closed-form optimum, for the "how close are we" message and the shading scale */
  var sxy = 0, bw, bb, best = 0;
  for (i = 0; i < N; i++) sxy += (xs[i] - mx) * (ys[i] - my) / N;
  bw = sxy / (sx * sx); bb = my - bw * mx;
  for (i = 0; i < N; i++) best += (bb + bw * xs[i] - ys[i]) * (bb + bw * xs[i] - ys[i]) / N;

  var lrIn = root.querySelector("[data-act=lr]"), lrOut = root.querySelector("[data-act=lr-out]");
  var stdIn = root.querySelector("[data-act=std]");
  var stepBtn = root.querySelector("[data-act=step]"), run20 = root.querySelector("[data-act=run20]"),
      resetBtn = root.querySelector("[data-act=reset]");
  var fitSvg = root.querySelector(".ml05g-fit"), lossSvg = root.querySelector(".ml05g-loss");
  var out = root.querySelector(".ml05g-out"), hint = root.querySelector(".ml05g-hint");

  var state;
  function feats() {
    var f = [];
    for (var j = 0; j < N; j++) f.push(stdIn.checked ? (xs[j] - mx) / sx : xs[j]);
    return f;
  }
  function loss(f, b, w) {
    var s = 0;
    for (var j = 0; j < N; j++) { var r = b + w * f[j] - ys[j]; s += r * r; }
    return s / N;
  }
  function lrValue() { return Math.pow(10, -5 + 5 * parseFloat(lrIn.value)); }
  function fmt(v) {
    if (!isFinite(v)) return "overflow";
    var av = Math.abs(v);
    if (av >= 1e6 || (av < 0.01 && av > 0)) return v.toExponential(1);
    return av >= 100 ? v.toFixed(0) : av >= 10 ? v.toFixed(1) : v.toFixed(2);
  }
  /* largest stable step size = 2 / (largest eigenvalue of the Hessian 2/n A'A) */
  function maxStable(f) {
    var sf = 0, sff = 0;
    for (var j = 0; j < N; j++) { sf += f[j]; sff += f[j] * f[j]; }
    var a = 2, b = 2 * sf / N, d = 2 * sff / N;
    var tr = a + d, det = a * d - b * b, disc = Math.sqrt(Math.max(0, tr * tr / 4 - det));
    return 2 / (tr / 2 + disc);
  }
  function range() {
    return stdIn.checked ? { w0: -100, w1: 500, b0: -100, b1: 1500 } : { w0: -4, w1: 24, b0: -600, b1: 1500 };
  }
  function reset() {
    state = { b: 0, w: 0, t: 0, path: [[0, 0]], dead: false };
    draw();
  }
  function stepOnce() {
    if (state.dead) return;
    var f = feats(), lr = lrValue(), gb = 0, gw = 0;
    for (var j = 0; j < N; j++) { var r = state.b + state.w * f[j] - ys[j]; gb += r; gw += r * f[j]; }
    state.b -= lr * 2 * gb / N; state.w -= lr * 2 * gw / N; state.t++;
    if (state.path.length < 4000) state.path.push([state.w, state.b]);
    var L = loss(f, state.b, state.w);
    if (!isFinite(L) || L > 1e12) state.dead = true;
  }
  function el(tag, attrs, parent) {
    var e = document.createElementNS(NS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
  }
  function clear(svg) { while (svg.firstChild) svg.removeChild(svg.firstChild); }

  function drawFit() {
    clear(fitSvg);
    var W = 340, H = 240, L = 46, R = 8, T = 10, B = 34;
    var X = function (v) { return L + (v - 20) / 100 * (W - L - R); };
    var Y = function (v) { return T + (1 - (v - 0) / 2000) * (H - T - B); };
    el("line", { x1: L, y1: H - B, x2: W - R, y2: H - B, "class": "line" }, fitSvg);
    el("line", { x1: L, y1: T, x2: L, y2: H - B, "class": "line" }, fitSvg);
    [0, 1000, 2000].forEach(function (v) {
      var t = el("text", { x: L - 5, y: Y(v) + 4, "text-anchor": "end", "class": "t-xs t-faint" }, fitSvg); t.textContent = v;
    });
    [20, 60, 100].forEach(function (v) {
      var t = el("text", { x: X(v), y: H - B + 14, "text-anchor": "middle", "class": "t-xs t-faint" }, fitSvg); t.textContent = v;
    });
    var tx = el("text", { x: (L + W - R) / 2, y: H - 4, "text-anchor": "middle", "class": "t-xs t-muted" }, fitSvg); tx.textContent = "floor area (m2)";
    /* current line in original units */
    var b = state.b, w = state.w;
    if (stdIn.checked) { w = state.w / sx; b = state.b - state.w * mx / sx; }
    var y0 = b + w * 20, y1 = b + w * 120;
    var clipId = "ml05gclip";
    var cp = el("clipPath", { id: clipId }, fitSvg);
    el("rect", { x: L, y: T, width: W - L - R, height: H - T - B }, cp);
    var g = el("g", { "clip-path": "url(#" + clipId + ")" }, fitSvg);
    el("line", { x1: X(20), y1: Y(y0), x2: X(120), y2: Y(y1), "class": "line s-blue sw-3" }, g);
    for (var j = 0; j < N; j++) el("circle", { cx: X(xs[j]), cy: Y(ys[j]), r: 4, "class": "f-yellow" }, fitSvg);
  }

  function drawLoss() {
    clear(lossSvg);
    var W = 340, H = 240, L = 46, R = 8, T = 10, B = 34, rg = range();
    var X = function (v) { return L + (v - rg.w0) / (rg.w1 - rg.w0) * (W - L - R); };
    var Y = function (v) { return T + (1 - (v - rg.b0) / (rg.b1 - rg.b0)) * (H - T - B); };
    var f = feats(), nx = 40, ny = 28, cw = (W - L - R) / nx, ch = (H - T - B) / ny;
    var lo = Math.log(best * 0.8), hi = Math.log(2e6);
    for (var i = 0; i < nx; i++) for (var j = 0; j < ny; j++) {
      var w = rg.w0 + (i + 0.5) / nx * (rg.w1 - rg.w0), b = rg.b0 + (1 - (j + 0.5) / ny) * (rg.b1 - rg.b0);
      var v = Math.max(0, Math.min(1, (Math.log(loss(f, b, w)) - lo) / (hi - lo)));
      el("rect", { x: L + i * cw, y: T + j * ch, width: cw + 0.5, height: ch + 0.5, "class": "f-blue", "fill-opacity": (0.9 * (1 - v) + 0.04).toFixed(3) }, lossSvg);
    }
    el("line", { x1: L, y1: H - B, x2: W - R, y2: H - B, "class": "line" }, lossSvg);
    el("line", { x1: L, y1: T, x2: L, y2: H - B, "class": "line" }, lossSvg);
    var tw = el("text", { x: (L + W - R) / 2, y: H - 4, "text-anchor": "middle", "class": "t-xs t-muted" }, lossSvg);
    tw.textContent = stdIn.checked ? "slope w (per SD of area)" : "slope w (per m2)";
    var tb = el("text", { x: 12, y: (T + H - B) / 2, "text-anchor": "middle", "class": "t-xs t-muted", transform: "rotate(-90 12 " + ((T + H - B) / 2) + ")" }, lossSvg);
    tb.textContent = "intercept b";
    var pts = state.path.map(function (p) { return X(p[0]).toFixed(1) + "," + Y(p[1]).toFixed(1); });
    el("polyline", { points: pts.join(" "), fill: "none", "class": "s-yellow sw-2", "stroke-linejoin": "round" }, lossSvg);
    var last = state.path[state.path.length - 1];
    el("circle", { cx: X(last[0]), cy: Y(last[1]), r: 5, "class": "f-red" }, lossSvg);
    el("circle", { cx: X(0), cy: Y(0), r: 3.5, "class": "f-green" }, lossSvg);
    var tl = el("text", { x: L + 4, y: T + 12, "class": "t-xs t-muted" }, lossSvg); tl.textContent = "darker = lower loss";
  }

  function draw() {
    var f = feats(), lr = lrValue(), stable = maxStable(f);
    lrOut.textContent = fmt(lr);
    drawFit(); drawLoss();
    var L = loss(f, state.b, state.w);
    var msg = "Step " + state.t + ": loss " + fmt(L) + ".";
    if (state.dead) msg += " Diverged: the step size is too big for this surface, so every step overshoots further than the last. Press Reset and lower it.";
    else if (L < best * 1.02) msg += " Within 2 percent of the best possible loss (" + fmt(best) + ", set by the noise).";
    else msg += " Best possible: " + fmt(best) + ".";
    out.textContent = msg;
    hint.textContent = "Largest step size that still converges here: about " + fmt(stable) + ". Yours is " + (lr < stable ? "below" : "above") + " it.";
  }

  lrIn.addEventListener("input", function () { reset(); });
  stdIn.addEventListener("change", function () { reset(); });
  stepBtn.addEventListener("click", function () { stepOnce(); draw(); });
  run20.addEventListener("click", function () { for (var k = 0; k < 20; k++) stepOnce(); draw(); });
  resetBtn.addEventListener("click", reset);
  /* default: raw features and a step size near the stable limit, which shows the zig-zag */
  lrIn.value = "0.20";
  reset();
})();
