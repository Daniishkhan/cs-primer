/* Sampler lab (A0 chapter 12).
   Draw samples from a named distribution, optionally average k draws at a time, and
   compare the histogram with the exact curve (k = 1) or the Gaussian the central limit
   theorem predicts (k > 1). The Cauchy distribution shows where that prediction fails. */
(function () {
  "use strict";
  var root = document.getElementById("mlf12-sampler");
  if (!root) return;
  var NS = "http://www.w3.org/2000/svg";
  var svg = root.querySelector(".mf12-svg"), out = root.querySelector(".mf12-out");
  function q(a) { return root.querySelector("[data-act=" + a + "]"); }
  var selD = q("dist"), pA = q("a"), pB = q("b"), kIn = q("k"), nIn = q("n");
  var W = 640, H = 300, L = 44, R = 12, T = 14, B = 34;
  var seed = 12345;

  function mulberry32(a) {
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      var t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  function gauss(rng) { var u = 1 - rng(), v = rng(); return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v); }
  function lgamma1(n) { var s = 0, i; for (i = 2; i <= n; i++) s += Math.log(i); return s; }

  var D = {
    die: { name: "Fair die", discrete: true, params: [], mean: function () { return 3.5; }, sd: function () { return Math.sqrt(35 / 12); },
      sample: function (rng) { return 1 + Math.floor(6 * rng()); }, lo: function () { return 1; }, hi: function () { return 6; },
      pmf: function (x) { return x >= 1 && x <= 6 ? 1 / 6 : 0; } },
    binom: { name: "Binomial", discrete: true, params: [["trials n", 5, 50, 1, 20], ["success prob. p", 0.05, 0.95, 0.05, 0.3]],
      mean: function (a, b) { return a * b; }, sd: function (a, b) { return Math.sqrt(a * b * (1 - b)); },
      sample: function (rng, a, b) { var c = 0, i; for (i = 0; i < a; i++) if (rng() < b) c++; return c; },
      lo: function () { return 0; }, hi: function (a) { return a; },
      pmf: function (x, a, b) { if (x < 0 || x > a) return 0; return Math.exp(lgamma1(a) - lgamma1(x) - lgamma1(a - x) + x * Math.log(b) + (a - x) * Math.log(1 - b)); } },
    pois: { name: "Poisson", discrete: true, params: [["rate (mean) &lambda;", 0.5, 12, 0.5, 4]],
      mean: function (a) { return a; }, sd: function (a) { return Math.sqrt(a); },
      sample: function (rng, a) { var l = Math.exp(-a), k = 0, p = 1; do { k++; p *= rng(); } while (p > l); return k - 1; },
      lo: function () { return 0; }, hi: function (a) { return Math.ceil(a + 5 * Math.sqrt(a) + 2); },
      pmf: function (x, a) { return x < 0 ? 0 : Math.exp(-a + x * Math.log(a) - lgamma1(x)); } },
    gauss: { name: "Gaussian", discrete: false, params: [["mean &mu;", -3, 3, 0.1, 0], ["std. dev. &sigma;", 0.5, 3, 0.1, 1]],
      mean: function (a) { return a; }, sd: function (a, b) { return b; },
      sample: function (rng, a, b) { return a + b * gauss(rng); },
      pdf: function (x, a, b) { var z = (x - a) / b; return Math.exp(-0.5 * z * z) / (b * Math.sqrt(2 * Math.PI)); } },
    expo: { name: "Exponential", discrete: false, params: [["rate &lambda;", 0.25, 4, 0.05, 1]],
      mean: function (a) { return 1 / a; }, sd: function (a) { return 1 / a; },
      sample: function (rng, a) { return -Math.log(1 - rng()) / a; },
      pdf: function (x, a) { return x < 0 ? 0 : a * Math.exp(-a * x); } },
    cauchy: { name: "Cauchy (heavy tails)", discrete: false, params: [["scale &gamma;", 0.5, 3, 0.1, 1]],
      mean: function () { return NaN; }, sd: function () { return NaN; },
      sample: function (rng, a) { return a * Math.tan(Math.PI * (rng() - 0.5)); },
      pdf: function (x, a) { return a / (Math.PI * (a * a + x * x)); } }
  };
  function el(tag, attrs, text) {
    var e = document.createElementNS(NS, tag), k;
    for (k in attrs) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    return e;
  }
  function clear(n) { while (n.firstChild) n.removeChild(n.firstChild); }
  function fmt(v) { return isFinite(v) ? v.toFixed(3) : "undefined"; }

  function setParams() {
    var d = D[selD.value], i, ctl = [pA, pB];
    for (i = 0; i < 2; i++) {
      var wrap = ctl[i].parentNode, p = d.params[i];
      if (!p) { wrap.hidden = true; continue; }
      wrap.hidden = false;
      wrap.querySelector(".lbl").innerHTML = p[0];
      ctl[i].min = p[1]; ctl[i].max = p[2]; ctl[i].step = p[3]; ctl[i].value = p[4];
    }
  }
  function draw() {
    var d = D[selD.value], a = +pA.value, b = +pB.value, k = +kIn.value, n = Math.round(Math.pow(10, +nIn.value));
    q("a-out").textContent = (+pA.value).toString(); q("b-out").textContent = (+pB.value).toString();
    q("k-out").textContent = k; q("n-out").textContent = n.toLocaleString("en-GB");
    var rng = mulberry32(seed), data = new Array(n), i, j, s;
    for (i = 0; i < n; i++) { s = 0; for (j = 0; j < k; j++) s += d.sample(rng, a, b); data[i] = s / k; }
    var mu = d.mean(a, b), sd = d.sd(a, b), heavy = isNaN(mu);
    var lo, hi, nb, bw;
    if (d.discrete && k === 1) { lo = d.lo(a, b) - 0.5; hi = d.hi(a, b) + 0.5; nb = hi - lo; bw = 1; }
    else if (heavy) { lo = -12 * a; hi = 12 * a; nb = 48; bw = (hi - lo) / nb; }
    else { var span = 4 * sd / Math.sqrt(k); lo = mu - span; hi = mu + span; nb = 40; bw = (hi - lo) / nb; if (selD.value === "expo" && k === 1) { lo = 0; hi = 6 / a; bw = (hi - lo) / nb; } }
    var counts = new Array(Math.round(nb)), c; for (i = 0; i < counts.length; i++) counts[i] = 0;
    var inside = 0;
    for (i = 0; i < n; i++) { c = Math.floor((data[i] - lo) / bw); if (c >= 0 && c < counts.length) { counts[c]++; inside++; } }
    var dens = counts.map(function (x) { return x / (n * bw); }), ymax = 0;
    for (i = 0; i < dens.length; i++) if (dens[i] > ymax) ymax = dens[i];
    function theory(x) {
      if (heavy && k > 1) return 0;
      if (k === 1) return d.discrete ? d.pmf(Math.round(x), a, b) : d.pdf(x, a, b);
      var s2 = sd / Math.sqrt(k), z = (x - mu) / s2; return Math.exp(-0.5 * z * z) / (s2 * Math.sqrt(2 * Math.PI));
    }
    var tmax = 0, x;
    for (x = lo; x <= hi; x += bw / 4) { var tv = theory(x); if (tv > tmax) tmax = tv; }
    ymax = Math.max(ymax, tmax) * 1.12 || 1;
    function X(v) { return L + (v - lo) / (hi - lo) * (W - L - R); }
    function Y(v) { return H - B - v / ymax * (H - B - T); }
    clear(svg);
    svg.appendChild(el("line", { x1: L, y1: H - B, x2: W - R, y2: H - B, "class": "line-thin" }));
    svg.appendChild(el("line", { x1: L, y1: T, x2: L, y2: H - B, "class": "line-thin" }));
    for (i = 0; i < counts.length; i++) {
      svg.appendChild(el("rect", { x: X(lo + i * bw) + 0.5, y: Y(dens[i]), width: Math.max(1, X(lo + (i + 1) * bw) - X(lo + i * bw) - 1), height: Math.max(0, H - B - Y(dens[i])), style: "fill:var(--blue);opacity:0.75" }));
    }
    var pts = [], step = (hi - lo) / 160;
    if (!(heavy && k > 1)) {
      if (k === 1 && d.discrete) {
        for (x = Math.ceil(lo); x < hi; x++) svg.appendChild(el("circle", { cx: X(x), cy: Y(theory(x)), r: 4, style: "fill:var(--orange);stroke:var(--bg);stroke-width:1.5" }));
      } else {
        for (x = lo; x <= hi + 1e-9; x += step) pts.push(X(x).toFixed(1) + "," + Y(theory(x)).toFixed(1));
        svg.appendChild(el("polyline", { points: pts.join(" "), fill: "none", style: "stroke:var(--orange);stroke-width:2.5" }));
      }
    }
    var ticks = 5, t, v;
    for (t = 0; t <= ticks; t++) { v = lo + (hi - lo) * t / ticks; svg.appendChild(el("text", { x: X(v), y: H - B + 16, "text-anchor": "middle", "class": "t-xs t-muted" }, Math.abs(v) >= 100 ? v.toFixed(0) : v.toFixed(2).replace(/\.?0+$/, ""))); }
    svg.appendChild(el("text", { x: L + 4, y: T + 8, "class": "t-xs t-muted" }, k === 1 ? "bars: samples. " + (d.discrete ? "dots" : "curve") + ": exact" : (heavy ? "bars: averages of " + k + " draws" : "bars: averages of " + k + " draws. curve: Gaussian from the CLT")));
    if (heavy && k > 1) svg.appendChild(el("text", { x: L + 4, y: T + 24, "class": "t-xs tc-red" }, "no Gaussian: the mean does not exist"));
    svg.appendChild(el("text", { x: (L + W - R) / 2, y: H - 4, "text-anchor": "middle", "class": "t-xs t-muted" }, k === 1 ? "value of one draw" : "average of " + k + " draws"));
    if (inside < n) svg.appendChild(el("text", { x: W - R, y: T + 8, "text-anchor": "end", "class": "t-xs tc-orange" }, (n - inside).toLocaleString("en-GB") + " draws off-screen"));

    var m = 0, v2 = 0;
    for (i = 0; i < n; i++) m += data[i];
    m /= n;
    for (i = 0; i < n; i++) v2 += (data[i] - m) * (data[i] - m);
    v2 = Math.sqrt(v2 / n);
    clear(out);
    [["sample mean", fmt(m)], ["true mean", fmt(mu)], ["sample std. dev.", fmt(v2)], ["true std. dev. of one draw", fmt(sd)],
     ["predicted sd of the average", fmt(sd / Math.sqrt(k))], ["draws", n.toLocaleString("en-GB")]].forEach(function (r) {
      var e = document.createElement("div"); e.innerHTML = r[0] + " = <b></b>"; e.querySelector("b").textContent = r[1]; out.appendChild(e);
    });
  }
  [pA, pB, kIn, nIn].forEach(function (c) { c.addEventListener("input", draw); });
  selD.addEventListener("change", function () { setParams(); draw(); });
  q("reseed").addEventListener("click", function () { seed = (seed * 1103515245 + 12345) % 2147483647; draw(); });
  setParams(); draw();
})();
