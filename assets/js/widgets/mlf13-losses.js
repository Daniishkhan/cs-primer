/* Loss and noise-model fitter (A0 chapter 13).
   Twenty points scatter around a true line. Push some of them off as outliers and fit
   the line three ways: squared error (a Gaussian noise model), absolute error (Laplace)
   and Huber (a hybrid). Squared error is dragged; the other two largely are not. */
(function () {
  "use strict";
  var root = document.getElementById("mlf13-losses");
  if (!root) return;
  var NS = "http://www.w3.org/2000/svg";
  var svg = root.querySelector(".mf13-svg"), out = root.querySelector(".mf13-out");
  function q(a) { return root.querySelector("[data-act=" + a + "]"); }
  var cnt = q("count"), size = q("size"), sd = q("sd");
  var W = 640, H = 320, L = 40, R = 12, T = 12, B = 30, N = 20, seed = 7;
  var TRUE_A = 0.8, TRUE_B = 1.0;

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
    var e = document.createElementNS(NS, tag), k;
    for (k in attrs) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    return e;
  }
  function clear(n) { while (n.firstChild) n.removeChild(n.firstChild); }

  function wls(x, y, w) {
    var sw = 0, sx = 0, sy = 0, sxx = 0, sxy = 0, i;
    for (i = 0; i < x.length; i++) { sw += w[i]; sx += w[i] * x[i]; sy += w[i] * y[i]; sxx += w[i] * x[i] * x[i]; sxy += w[i] * x[i] * y[i]; }
    var den = sw * sxx - sx * sx, a = (sw * sxy - sx * sy) / den, b = (sy - a * sx) / sw;
    return [a, b];
  }
  function irls(x, y, weightFn) {
    var w = x.map(function () { return 1; }), p = wls(x, y, w), it, i;
    for (it = 0; it < 80; it++) {
      for (i = 0; i < x.length; i++) w[i] = weightFn(Math.abs(y[i] - (p[0] * x[i] + p[1])));
      p = wls(x, y, w);
    }
    return p;
  }
  function draw() {
    var k = +cnt.value, big = +size.value, s = +sd.value;
    q("count-out").textContent = k; q("size-out").textContent = big.toFixed(1); q("sd-out").textContent = s.toFixed(2);
    var rng = mulberry32(seed), x = [], y = [], i, isOut = [];
    for (i = 0; i < N; i++) {
      x.push(0.5 + 9 * (i + 0.5 * rng()) / N);
      y.push(TRUE_A * x[i] + TRUE_B + s * gauss(rng));
    }
    // outliers: the k points nearest the right-hand end are pushed up by 'big'
    for (i = 0; i < N; i++) isOut.push(i >= N - k);
    for (i = 0; i < N; i++) if (isOut[i]) y[i] += big;
    var fits = [
      { name: "squared error (Gaussian)", col: "var(--blue)", p: wls(x, y, x.map(function () { return 1; })) },
      { name: "absolute error (Laplace)", col: "var(--orange)", p: irls(x, y, function (r) { return 1 / Math.max(r, 1e-3); }) },
      { name: "Huber, delta = 1", col: "var(--green)", p: irls(x, y, function (r) { return r <= 1 ? 1 : 1 / r; }) }
    ];
    var ymin = 0, ymax = 12, j;
    for (i = 0; i < N; i++) { if (y[i] > ymax) ymax = y[i] + 1; if (y[i] < ymin) ymin = y[i] - 1; }
    function X(v) { return L + v / 10 * (W - L - R); }
    function Y(v) { return H - B - (v - ymin) / (ymax - ymin) * (H - B - T); }
    clear(svg);
    svg.appendChild(el("line", { x1: L, y1: H - B, x2: W - R, y2: H - B, "class": "line-thin" }));
    svg.appendChild(el("line", { x1: L, y1: T, x2: L, y2: H - B, "class": "line-thin" }));
    for (i = 0; i <= 10; i += 2) svg.appendChild(el("text", { x: X(i), y: H - B + 16, "text-anchor": "middle", "class": "t-xs t-muted" }, String(i)));
    var step = ymax - ymin > 20 ? 5 : 2;
    for (j = Math.ceil(ymin / step) * step; j <= ymax; j += step) svg.appendChild(el("text", { x: L - 6, y: Y(j) + 4, "text-anchor": "end", "class": "t-xs t-muted" }, String(j)));
    svg.appendChild(el("line", { x1: X(0), y1: Y(TRUE_B), x2: X(10), y2: Y(TRUE_A * 10 + TRUE_B), "class": "line-dash" }));
    fits.forEach(function (f) {
      svg.appendChild(el("line", { x1: X(0), y1: Y(f.p[1]), x2: X(10), y2: Y(f.p[0] * 10 + f.p[1]), style: "stroke:" + f.col + ";stroke-width:2.5" }));
    });
    for (i = 0; i < N; i++) {
      svg.appendChild(el("circle", { cx: X(x[i]), cy: Y(y[i]), r: 4.5, style: "fill:" + (isOut[i] ? "var(--red)" : "var(--text-muted)") + ";stroke:var(--bg);stroke-width:1.5" }));
    }
    svg.appendChild(el("text", { x: L + 6, y: T + 10, "class": "t-xs t-muted" }, "grey dashes: the true line (slope 0.8, intercept 1). red dots: outliers."));
    clear(out);
    fits.forEach(function (f) {
      var d = document.createElement("div"), gap = (f.p[0] * 10 + f.p[1]) - (TRUE_A * 10 + TRUE_B);
      d.innerHTML = '<span class="sw"></span>' + f.name + ": slope <b></b>, intercept <b></b>, off by <b></b> at x = 10";
      d.querySelector(".sw").style.background = f.col;
      var bs = d.querySelectorAll("b");
      bs[0].textContent = f.p[0].toFixed(2); bs[1].textContent = f.p[1].toFixed(2); bs[2].textContent = (gap >= 0 ? "+" : "") + gap.toFixed(2);
      out.appendChild(d);
    });
  }
  [cnt, size, sd].forEach(function (c) { c.addEventListener("input", draw); });
  q("reseed").addEventListener("click", function () { seed = (seed * 1103515245 + 12345) % 2147483647; draw(); });
  draw();
})();
