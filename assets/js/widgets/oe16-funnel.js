/* Search, selection and test funnel (A7 chapter 16).
   N candidates have true accuracy drawn from a normal spread around 60%. Stage 1 scores all of them on a
   search set and shortlists the top K. Stage 2 re-scores the shortlist on a separate selection set and
   keeps the best. Stage 3 reports that winner on a test set. If "peek" is ticked, the test set is used to
   choose among the shortlist instead, which is the leak the chapter warns about. Scores use the normal
   approximation to a binomial. 300 seeded trials per setting. */
(function () {
  "use strict";
  var root = document.getElementById("oe16-funnel");
  if (!root) return;

  var NS = "http://www.w3.org/2000/svg", TRIALS = 300;
  var NS_LIST = [5, 10, 20, 50, 100, 200, 500, 1000];
  var SIZES = [20, 50, 100, 200, 500, 1000, 2000];
  var KS = [1, 2, 3, 5, 10, 20];
  var svg = root.querySelector(".oe16-chart"), note = root.querySelector(".oe16-note");
  function q(n) { return root.querySelector("[data-act=" + n + "]"); }
  var ctl = { n: q("n"), search: q("search"), k: q("k"), select: q("select"), test: q("test") };
  var out = { n: q("n-out"), search: q("search-out"), k: q("k-out"), select: q("select-out"), test: q("test-out") };
  var peek = q("peek");

  function mulberry32(a) {
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      var t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  function gauss(rng) {
    var u = Math.max(1e-12, rng()), v = rng();
    return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
  }
  function measure(p, n, rng) {
    return p + Math.sqrt(p * (1 - p) / n) * gauss(rng);
  }

  function simulate(N, nSearch, K, nSel, nTest, peeking) {
    var rng = mulberry32(777 + N * 13 + nSearch + K * 7), t, i, sum = { search: 0, select: 0, test: 0, truth: 0 };
    K = Math.min(K, N);
    for (t = 0; t < TRIALS; t++) {
      var cand = [];
      for (i = 0; i < N; i++) {
        var p = 0.6 + 0.03 * gauss(rng);
        cand.push({ p: p, s: measure(p, nSearch, rng) });
      }
      cand.sort(function (a, b) { return b.s - a.s; });
      var short = cand.slice(0, K), best = null;
      for (i = 0; i < short.length; i++) {
        short[i].sel = measure(short[i].p, nSel, rng);
        short[i].tst = measure(short[i].p, nTest, rng);
        var key = peeking ? short[i].tst : short[i].sel;
        if (best === null || key > best.key) best = { c: short[i], key: key };
      }
      sum.search += best.c.s; sum.select += best.c.sel; sum.test += best.c.tst; sum.truth += best.c.p;
    }
    for (var k in sum) sum[k] /= TRIALS;
    return sum;
  }

  function el(tag, attrs, text) {
    var e = document.createElementNS(NS, tag), k;
    for (k in attrs) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    return e;
  }

  function draw(r) {
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    var W = 640, H = 250, L = 46, Rm = 14, T = 14, B = 46, pw = W - L - Rm, ph = H - T - B, i;
    var vals = [r.search, r.select, r.test, r.truth];
    var lo = Math.floor((Math.min.apply(null, vals) - 0.03) * 20) / 20, hi = Math.ceil((Math.max.apply(null, vals) + 0.02) * 20) / 20;
    function Y(v) { return T + ph * (1 - (v - lo) / (hi - lo)); }
    for (i = 0; i <= 4; i++) {
      var v = lo + (hi - lo) * i / 4;
      svg.appendChild(el("line", { x1: L, y1: Y(v), x2: W - Rm, y2: Y(v), "class": "grid" }));
      svg.appendChild(el("text", { x: L - 6, y: Y(v) + 4, "text-anchor": "end" }, (100 * v).toFixed(0) + "%"));
    }
    svg.appendChild(el("line", { x1: L, y1: T + ph, x2: W - Rm, y2: T + ph, "class": "ax" }));
    var labels = ["search set", "selection set", "test set", "true skill"], cls = ["b-search", "b-select", "b-test", "b-truth"];
    var bw = pw / 4;
    for (i = 0; i < 4; i++) {
      var x = L + bw * i + bw * 0.2, h = Math.max(1, T + ph - Y(vals[i]));
      svg.appendChild(el("rect", { x: x, y: T + ph - h, width: bw * 0.6, height: h, rx: 3, "class": cls[i] }));
      svg.appendChild(el("text", { x: x + bw * 0.3, y: T + ph - h - 5, "text-anchor": "middle", "class": "val" }, (100 * vals[i]).toFixed(1) + "%"));
      svg.appendChild(el("text", { x: x + bw * 0.3, y: T + ph + 16, "text-anchor": "middle" }, labels[i]));
    }
    svg.appendChild(el("text", { x: L + pw / 2, y: H - 6, "text-anchor": "middle" }, "average score of the final pick, " + TRIALS + " trials"));
    svg.setAttribute("viewBox", "0 0 " + W + " " + H);
  }

  function update() {
    var N = NS_LIST[+ctl.n.value], ns = SIZES[+ctl.search.value], K = KS[+ctl.k.value], nsel = SIZES[+ctl.select.value], nt = SIZES[+ctl.test.value];
    out.n.textContent = String(N); out.search.textContent = String(ns); out.k.textContent = String(Math.min(K, N));
    out.select.textContent = String(nsel); out.test.textContent = String(nt);
    var r = simulate(N, ns, K, nsel, nt, peek.checked);
    draw(r);
    var f = function (x) { return (100 * x).toFixed(1); };
    note.textContent = "The search set says " + f(r.search) + "%, the selection set " + f(r.select) + "%, the test set " + f(r.test) +
      "%; the pick's true skill is " + f(r.truth) + "%. Over-statement: search set " + (100 * (r.search - r.truth)).toFixed(1) +
      " points, selection set " + (100 * (r.select - r.truth)).toFixed(1) + " points, test set " + (100 * (r.test - r.truth)).toFixed(1) +
      " points." + (peek.checked ? " Because the test set chose the finalist, it is no longer an honest measurement." : "");
  }

  Object.keys(ctl).forEach(function (k) { ctl[k].addEventListener("input", update); });
  peek.addEventListener("change", update);
  update();
})();
