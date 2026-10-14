/* Overfitting explorer (A1 chapter 01).
   Fits a polynomial of chosen degree to a small noisy sample of y = sin(2 pi x) + noise,
   and reports the error on the training points and on 300 fresh validation points. */
(function () {
  "use strict";
  var root = document.getElementById("ml01-fit");
  if (!root) return;

  var NS = "http://www.w3.org/2000/svg";
  var degIn = root.querySelector("[data-act=degree]");
  var degOut = root.querySelector("[data-act=degree-out]");
  var nIn = root.querySelector("[data-act=n]");
  var nOut = root.querySelector("[data-act=n-out]");
  var noiseIn = root.querySelector("[data-act=noise]");
  var noiseOut = root.querySelector("[data-act=noise-out]");
  var newBtn = root.querySelector("[data-act=resample]");
  var svg = root.querySelector(".ml01-chart");
  var readout = root.querySelector(".ml01-readout");
  var verdict = root.querySelector(".ml01-verdict");
  var seed = 5;

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
  function truth(x) { return Math.sin(2 * Math.PI * x); }

  function sample(n, noise, rng) {
    var xs = [], ys = [];
    for (var i = 0; i < n; i++) {
      var x = rng();
      xs.push(x); ys.push(truth(x) + noise * gauss(rng));
    }
    return { x: xs, y: ys };
  }

  // Chebyshev basis on [0,1] mapped to [-1,1]: well conditioned up to degree 12.
  function basis(x, d) {
    var u = 2 * x - 1, t = [1, u];
    for (var k = 2; k <= d; k++) t[k] = 2 * u * t[k - 1] - t[k - 2];
    return t.slice(0, d + 1);
  }

  function fit(data, d) {
    var m = d + 1, A = [], b = [], i, j, k;
    for (i = 0; i < m; i++) { A.push([]); for (j = 0; j < m; j++) A[i].push(i === j ? 1e-8 : 0); b.push(0); }
    for (k = 0; k < data.x.length; k++) {
      var phi = basis(data.x[k], d);
      for (i = 0; i < m; i++) {
        b[i] += phi[i] * data.y[k];
        for (j = 0; j < m; j++) A[i][j] += phi[i] * phi[j];
      }
    }
    // Gaussian elimination with partial pivoting
    for (i = 0; i < m; i++) {
      var p = i;
      for (k = i + 1; k < m; k++) if (Math.abs(A[k][i]) > Math.abs(A[p][i])) p = k;
      var tmp = A[i]; A[i] = A[p]; A[p] = tmp;
      var tb = b[i]; b[i] = b[p]; b[p] = tb;
      for (k = i + 1; k < m; k++) {
        var f = A[k][i] / A[i][i];
        for (j = i; j < m; j++) A[k][j] -= f * A[i][j];
        b[k] -= f * b[i];
      }
    }
    var w = new Array(m);
    for (i = m - 1; i >= 0; i--) {
      var s = b[i];
      for (j = i + 1; j < m; j++) s -= A[i][j] * w[j];
      w[i] = s / A[i][i];
    }
    return function (x) {
      var phi = basis(x, d), s2 = 0;
      for (var q = 0; q < m; q++) s2 += w[q] * phi[q];
      return s2;
    };
  }

  function mse(f, data) {
    var s = 0;
    for (var i = 0; i < data.x.length; i++) { var e = f(data.x[i]) - data.y[i]; s += e * e; }
    return s / data.x.length;
  }

  function el(tag, attrs, text) {
    var e = document.createElementNS(NS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    return e;
  }

  function fmt(v) {
    if (!isFinite(v)) return "huge";
    if (v >= 1000) return v.toExponential(1);
    return v.toFixed(3);
  }

  function draw() {
    var d = parseInt(degIn.value, 10), n = parseInt(nIn.value, 10), noise = parseInt(noiseIn.value, 10) / 100;
    degOut.textContent = String(d); nOut.textContent = String(n); noiseOut.textContent = noise.toFixed(2);
    var train = sample(n, noise, mulberry32(seed * 7919 + 1));
    var valid = sample(300, noise, mulberry32(seed * 104729 + 3));
    var f = fit(train, d);
    var trE = mse(f, train), vaE = mse(f, valid), floor = noise * noise;

    var W = 700, H = 300, L = 40, R = 12, T = 12, B = 30, pw = W - L - R, ph = H - T - B;
    function X(x) { return L + x * pw; }
    function Y(y) { var c = Math.max(-2.2, Math.min(2.2, y)); return T + ph * (1 - (c + 2.2) / 4.4); }
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    svg.setAttribute("viewBox", "0 0 " + W + " " + H);
    svg.appendChild(el("line", { x1: L, y1: T + ph, x2: W - R, y2: T + ph, "class": "line-thin" }));
    svg.appendChild(el("line", { x1: L, y1: T, x2: L, y2: T + ph, "class": "line-thin" }));
    [-2, 0, 2].forEach(function (v) {
      svg.appendChild(el("text", { x: L - 6, y: Y(v) + 4, "text-anchor": "end", "class": "t-xs t-faint" }, String(v)));
    });
    [0, 0.5, 1].forEach(function (v) {
      svg.appendChild(el("text", { x: X(v), y: T + ph + 16, "text-anchor": "middle", "class": "t-xs t-faint" }, String(v)));
    });
    svg.appendChild(el("text", { x: L + pw / 2, y: H - 3, "text-anchor": "middle", "class": "t-xs t-muted" }, "input x"));
    var pts = [], i;
    for (i = 0; i <= 120; i++) pts.push(X(i / 120).toFixed(1) + "," + Y(truth(i / 120)).toFixed(1));
    svg.appendChild(el("polyline", { points: pts.join(" "), fill: "none", "class": "line-dash s-green" }));
    pts = [];
    for (i = 0; i <= 200; i++) pts.push(X(i / 200).toFixed(1) + "," + Y(f(i / 200)).toFixed(1));
    svg.appendChild(el("polyline", { points: pts.join(" "), fill: "none", "class": "s-blue sw-2" }));
    for (i = 0; i < train.x.length; i++) {
      svg.appendChild(el("circle", { cx: X(train.x[i]).toFixed(1), cy: Y(train.y[i]).toFixed(1), r: 4, "class": "f-yellow" }));
    }
    svg.appendChild(el("text", { x: W - R - 4, y: T + 12, "text-anchor": "end", "class": "t-xs tc-green" }, "dashed: the true pattern"));
    svg.appendChild(el("text", { x: W - R - 4, y: T + 26, "text-anchor": "end", "class": "t-xs tc-blue" }, "solid: the fitted curve"));

    readout.textContent = "";
    var rows = [["Training error (MSE)", fmt(trE)], ["Validation error (MSE)", fmt(vaE)], ["Noise floor (best possible)", fmt(floor)]];
    rows.forEach(function (r) {
      var p = document.createElement("div");
      p.innerHTML = "<strong></strong> <span></span>";
      p.firstChild.textContent = r[0] + ": ";
      p.lastChild.textContent = r[1];
      readout.appendChild(p);
    });
    var msg;
    if (trE > 2.5 * floor + 0.02) msg = "Underfitting: the curve is too stiff to follow the pattern, so even the training points are poorly fitted.";
    else if (vaE > 2 * trE + 0.03 && vaE > 1.6 * floor) msg = "Overfitting: the curve chases the noise in these points. Training error is low and validation error is much higher.";
    else msg = "A reasonable fit: training and validation errors are close, and near the noise floor.";
    verdict.textContent = msg;
  }

  [degIn, nIn, noiseIn].forEach(function (c) { c.addEventListener("input", draw); });
  newBtn.addEventListener("click", function () { seed += 1; draw(); });
  draw();
})();
