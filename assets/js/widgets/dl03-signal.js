/* Signal-propagation lab (A2 chapter 03).
   Pushes a random batch through a stack of random layers (width 128) and plots
   the standard deviation of the activations after each layer on a log scale.
   Controls: depth, weight scale relative to the "He" value sqrt(2/fan_in),
   activation, and whether each layer is wrapped in a residual connection. */
(function () {
  "use strict";
  var root = document.getElementById("dl03-signal");
  if (!root) return;

  var NS = "http://www.w3.org/2000/svg";
  var C = 128, B = 32;
  var q = function (sel) { return root.querySelector(sel); };
  var depthIn = q("[data-act=depth]"), scaleIn = q("[data-act=scale]"), actSel = q("[data-act=act]"),
      resChk = q("[data-act=res]"), normChk = q("[data-act=norm]");
  var depthOut = q("[data-act=depth-out]"), scaleOut = q("[data-act=scale-out]");
  var svg = q(".dl03-chart"), out = q(".dl03-summary");

  function mulberry32(a) {
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      var t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  function gauss(rng) {
    var u = 1 - rng(), v = rng();
    return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
  }
  function std(arr) {
    var m = 0, i;
    for (i = 0; i < arr.length; i++) m += arr[i];
    m /= arr.length;
    var s = 0;
    for (i = 0; i < arr.length; i++) s += (arr[i] - m) * (arr[i] - m);
    return Math.sqrt(s / arr.length);
  }
  function el(tag, attrs, text) {
    var e = document.createElementNS(NS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    return e;
  }

  function simulate(depth, scale, act, residual, norm) {
    var rng = mulberry32(2024), h = [], i, j, k, b;
    for (b = 0; b < B; b++) { var row = new Float64Array(C); for (j = 0; j < C; j++) row[j] = gauss(rng); h.push(row); }
    var stds = [], sd = Math.sqrt(2 / C) * scale;
    for (var l = 0; l < depth; l++) {
      var W = new Float64Array(C * C);
      for (i = 0; i < W.length; i++) W[i] = gauss(rng) * sd;
      var next = [];
      for (b = 0; b < B; b++) {
        var inp = h[b], src = inp;
        if (norm) { // LayerNorm (no learned scale) applied to the branch input
          var mu = 0, vr = 0;
          for (j = 0; j < C; j++) mu += inp[j];
          mu /= C;
          for (j = 0; j < C; j++) vr += (inp[j] - mu) * (inp[j] - mu);
          vr /= C;
          src = new Float64Array(C);
          for (j = 0; j < C; j++) src[j] = (inp[j] - mu) / Math.sqrt(vr + 1e-5);
        }
        var o = new Float64Array(C);
        for (j = 0; j < C; j++) {
          var z = 0;
          for (k = 0; k < C; k++) z += src[k] * W[k * C + j];
          var a = act === "relu" ? Math.max(0, z) : Math.tanh(z);
          o[j] = residual ? inp[j] + a : a;
        }
        next.push(o);
      }
      h = next;
      var flat = [];
      for (b = 0; b < B; b++) for (j = 0; j < C; j++) flat.push(h[b][j]);
      stds.push(std(flat));
    }
    return stds;
  }

  function draw() {
    var depth = parseInt(depthIn.value, 10), scale = Math.pow(10, parseFloat(scaleIn.value));
    depthOut.textContent = String(depth);
    scaleOut.textContent = "x" + scale.toFixed(2);
    var stds = simulate(depth, scale, actSel.value, resChk.checked, normChk.checked);
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    var W = 700, H = 240, L = 54, R = 12, T = 12, Bm = 36, pw = W - L - R, ph = H - T - Bm;
    var LO = -8, HI = 8; // log10 axis limits
    function yOf(s) {
      var v = Math.log(Math.max(s, 1e-12)) / Math.LN10;
      v = Math.max(LO, Math.min(HI, v));
      return T + ph * (HI - v) / (HI - LO);
    }
    function xOf(l) { return L + pw * (l - 1) / Math.max(1, depth - 1); }
    var e;
    for (e = LO; e <= HI; e += 4) {
      svg.appendChild(el("line", { x1: L, y1: yOf(Math.pow(10, e)), x2: W - R, y2: yOf(Math.pow(10, e)), "class": "line-thin" }));
      svg.appendChild(el("text", { x: L - 6, y: yOf(Math.pow(10, e)) + 4, "text-anchor": "end", "class": "t-xs t-faint" }, "1e" + e));
    }
    svg.appendChild(el("line", { x1: L, y1: yOf(1), x2: W - R, y2: yOf(1), "class": "line-dash s-green" }));
    svg.appendChild(el("text", { x: W - R - 4, y: yOf(1) - 5, "text-anchor": "end", "class": "t-xs tc-green t-bold" }, "std = 1 (healthy)"));
    svg.appendChild(el("text", { x: L + pw / 2, y: H - 6, "text-anchor": "middle", "class": "t-xs t-muted" }, "layer →"));
    svg.appendChild(el("text", { x: 12, y: T + ph / 2, "class": "t-xs t-muted", transform: "rotate(-90 12 " + (T + ph / 2) + ")", "text-anchor": "middle" }, "activation std (log)"));
    var d = "";
    stds.forEach(function (s, i) { d += (i ? "L" : "M") + xOf(i + 1).toFixed(1) + "," + yOf(s).toFixed(1); });
    svg.appendChild(el("path", { d: d, fill: "none", "class": "s-blue sw-2" }));
    var last = stds[stds.length - 1];
    var verdict = last < 1e-3 ? "The signal has vanished: later layers see almost nothing." :
      last > 1e3 ? "The signal has exploded: activations grow without bound." :
      "The signal stays in a usable range.";
    out.textContent = "After layer " + depth + ": std = " + (last < 0.01 || last > 1000 ? last.toExponential(2) : last.toFixed(3)) + ". " + verdict;
  }

  [depthIn, scaleIn].forEach(function (c) { c.addEventListener("input", draw); });
  [actSel, resChk, normChk].forEach(function (c) { c.addEventListener("change", draw); });
  draw();
})();
