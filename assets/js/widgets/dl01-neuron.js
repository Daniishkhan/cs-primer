/* Neuron playground (A2 chapter 01).
   One neuron with two inputs: output = f(w1*x1 + w2*x2 + b).
   Draws the output over the (x1, x2) plane as a grid of cells, so the viewer
   sees what a weight vector, a bias and an activation do geometrically. */
(function () {
  "use strict";
  var root = document.getElementById("dl01-neuron");
  if (!root) return;

  var NS = "http://www.w3.org/2000/svg";
  var N = 21, RANGE = 2, CELL = 14, PAD = 28;
  var ACTS = {
    linear: function (z) { return z; },
    sigmoid: function (z) { return 1 / (1 + Math.exp(-z)); },
    tanh: function (z) { return Math.tanh(z); },
    relu: function (z) { return Math.max(0, z); },
    gelu: function (z) {
      // tanh approximation of z * Phi(z)
      return 0.5 * z * (1 + Math.tanh(0.7978845608 * (z + 0.044715 * z * z * z)));
    }
  };
  var q = function (sel) { return root.querySelector(sel); };
  var w1 = q("[data-act=w1]"), w2 = q("[data-act=w2]"), bias = q("[data-act=b]"), actSel = q("[data-act=act]");
  var o1 = q("[data-act=w1-out]"), o2 = q("[data-act=w2-out]"), ob = q("[data-act=b-out]");
  var svg = q(".dl01-grid"), out = q(".dl01-summary");

  function el(tag, attrs, text) {
    var e = document.createElementNS(NS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    return e;
  }
  function fmt(v) { return (v >= 0 ? "+" : "") + v.toFixed(1); }

  function draw() {
    var a = parseFloat(w1.value), b2 = parseFloat(w2.value), b = parseFloat(bias.value);
    var f = ACTS[actSel.value];
    o1.textContent = fmt(a); o2.textContent = fmt(b2); ob.textContent = fmt(b);
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    var defs = el("defs", {}), cp = el("clipPath", { id: "dl01clip" });
    cp.appendChild(el("rect", { x: PAD, y: 8, width: N * CELL, height: N * CELL }));
    defs.appendChild(cp); svg.appendChild(defs);
    var vals = [], lo = Infinity, hi = -Infinity, i, j;
    for (j = 0; j < N; j++) {
      for (i = 0; i < N; i++) {
        var x1 = -RANGE + 2 * RANGE * i / (N - 1);
        var x2 = RANGE - 2 * RANGE * j / (N - 1);
        var v = f(a * x1 + b2 * x2 + b);
        vals.push(v);
        if (v < lo) lo = v;
        if (v > hi) hi = v;
      }
    }
    var mid = (actSel.value === "sigmoid") ? 0.5 : 0;
    var scale = Math.max(Math.abs(lo - mid), Math.abs(hi - mid), 1e-6);
    for (j = 0; j < N; j++) {
      for (i = 0; i < N; i++) {
        var val = vals[j * N + i], d = (val - mid) / scale;
        svg.appendChild(el("rect", {
          x: PAD + i * CELL, y: 8 + j * CELL, width: CELL, height: CELL,
          style: "fill:" + (d >= 0 ? "var(--blue)" : "var(--orange)") + ";opacity:" + (0.08 + 0.85 * Math.abs(d)).toFixed(2)
        }));
      }
    }
    var size = N * CELL, cx = PAD + size / 2, cy = 8 + size / 2;
    svg.appendChild(el("line", { x1: PAD, y1: cy, x2: PAD + size, y2: cy, "class": "line-thin" }));
    svg.appendChild(el("line", { x1: cx, y1: 8, x2: cx, y2: 8 + size, "class": "line-thin" }));
    svg.appendChild(el("text", { x: PAD + size + 6, y: cy + 4, "class": "t-xs t-muted" }, "x1"));
    svg.appendChild(el("text", { x: cx + 4, y: 8 + size + 14, "class": "t-xs t-muted" }, "x2 (up)"));
    // the decision line z = 0, when it passes through the plot
    if (Math.abs(a) > 0.05 || Math.abs(b2) > 0.05) {
      var pts = [], t, xs;
      if (Math.abs(b2) >= Math.abs(a)) {
        for (xs = -RANGE; xs <= RANGE; xs += 2 * RANGE) pts.push([xs, -(a * xs + b) / b2]);
      } else {
        for (xs = -RANGE; xs <= RANGE; xs += 2 * RANGE) pts.push([-(b2 * xs + b) / a, xs]);
      }
      var P = pts.map(function (p) {
        return [PAD + (p[0] + RANGE) / (2 * RANGE) * size, 8 + (RANGE - p[1]) / (2 * RANGE) * size];
      });
      svg.appendChild(el("line", { x1: P[0][0], y1: P[0][1], x2: P[1][0], y2: P[1][1], "class": "line-dash s-yellow sw-2",
        "clip-path": "url(#dl01clip)" }));
    }
    var s = fmt(a) + "·x1 " + fmt(b2) + "·x2 " + fmt(b);
    out.textContent = "z = " + s + ". The dashed line is where z = 0; the weights point across it, the bias slides it. Blue cells are positive outputs, orange negative.";
  }

  [w1, w2, bias].forEach(function (c) { c.addEventListener("input", draw); });
  actSel.addEventListener("change", draw);
  draw();
})();
