/* Bandit policy lab (A7 chapter 01).
   Three arms with fixed hidden win rates. Four policies (greedy, epsilon-greedy,
   UCB1 with a tunable constant, Thompson sampling) are each run over many seeded
   repeats; the chart shows average cumulative regret over time. */
(function () {
  "use strict";
  var root = document.getElementById("oe01-bandit");
  if (!root) return;

  var NS = "http://www.w3.org/2000/svg";
  var ARMS = [0.30, 0.45, 0.50];
  var REPEATS = 100;
  var POL = [
    { id: "greedy", label: "Greedy", color: "red" },
    { id: "eps", label: "Epsilon-greedy", color: "orange" },
    { id: "ucb", label: "UCB1", color: "blue" },
    { id: "ts", label: "Thompson", color: "green" }
  ];

  var hIn = root.querySelector("[data-act=horizon]"), hOut = root.querySelector("[data-act=horizon-out]");
  var cIn = root.querySelector("[data-act=c]"), cOut = root.querySelector("[data-act=c-out]");
  var eIn = root.querySelector("[data-act=eps]"), eOut = root.querySelector("[data-act=eps-out]");
  var svg = root.querySelector(".bd-chart");
  var tbody = root.querySelector(".bd-table tbody");

  function mulberry32(a) {
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      var t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  function normal(rng) {
    var u = 1 - rng(), v = rng();
    return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
  }
  function gamma(shape, rng) { /* Marsaglia-Tsang, shape >= 1 */
    var d = shape - 1 / 3, c = 1 / Math.sqrt(9 * d);
    for (;;) {
      var x = normal(rng), v = 1 + c * x;
      if (v <= 0) continue;
      v = v * v * v;
      var u = rng();
      if (Math.log(u) < 0.5 * x * x + d - d * v + d * Math.log(v)) return d * v;
    }
  }
  function beta(a, b, rng) { var x = gamma(a, rng), y = gamma(b, rng); return x / (x + y); }

  function argmax(f) {
    var best = 0, bv = -Infinity;
    for (var i = 0; i < ARMS.length; i++) { var v = f(i); if (v > bv) { bv = v; best = i; } }
    return best;
  }

  /* returns an array of cumulative regret sampled at ~60 checkpoints, plus the final share on the best arm */
  function simulate(policy, steps, c, eps, seed) {
    var rng = mulberry32(seed);
    var n = [0, 0, 0], s = [0, 0, 0], regret = 0, out = [], bestPulls = 0;
    var every = Math.max(1, Math.floor(steps / 60));
    for (var t = 1; t <= steps; t++) {
      var a;
      if (policy === "ts") {
        a = argmax(function (i) { return beta(1 + s[i], 1 + n[i] - s[i], rng); });
      } else if (n[0] === 0 || n[1] === 0 || n[2] === 0) {
        a = n[0] === 0 ? 0 : (n[1] === 0 ? 1 : 2);
      } else if (policy === "greedy") {
        a = argmax(function (i) { return s[i] / n[i]; });
      } else if (policy === "eps") {
        a = rng() < eps ? Math.floor(rng() * 3) : argmax(function (i) { return s[i] / n[i]; });
      } else {
        a = argmax(function (i) { return s[i] / n[i] + c * Math.sqrt(Math.log(t) / n[i]); });
      }
      var r = rng() < ARMS[a] ? 1 : 0;
      n[a]++; s[a] += r; regret += 0.5 - ARMS[a];
      if (a === 2) bestPulls++;
      if (t % every === 0) out.push(regret);
    }
    return { curve: out, share: bestPulls / steps, regret: regret };
  }

  function el(tag, attrs, text) {
    var e = document.createElementNS(NS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    return e;
  }

  function run() {
    var steps = parseInt(hIn.value, 10), c = parseFloat(cIn.value), eps = parseFloat(eIn.value);
    hOut.textContent = String(steps); cOut.textContent = c.toFixed(2); eOut.textContent = eps.toFixed(2);
    var res = POL.map(function (p) {
      var sum = null, share = 0, reg = 0;
      for (var k = 0; k < REPEATS; k++) {
        var r = simulate(p.id, steps, c, eps, 1000 + k);
        if (!sum) sum = r.curve.map(function () { return 0; });
        for (var i = 0; i < r.curve.length; i++) sum[i] += r.curve[i] / REPEATS;
        share += r.share / REPEATS; reg += r.regret / REPEATS;
      }
      return { p: p, curve: sum, share: share, regret: reg };
    });
    var W = 700, H = 240, L = 48, R = 12, T = 12, B = 34, pw = W - L - R, ph = H - T - B;
    var maxY = 1;
    res.forEach(function (r) { r.curve.forEach(function (v) { if (v > maxY) maxY = v; }); });
    maxY = Math.ceil(maxY / 10) * 10;
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    svg.setAttribute("viewBox", "0 0 " + W + " " + H);
    svg.appendChild(el("line", { x1: L, y1: T + ph, x2: W - R, y2: T + ph, "class": "line-thin" }));
    svg.appendChild(el("line", { x1: L, y1: T, x2: L, y2: T + ph, "class": "line-thin" }));
    [0, 0.5, 1].forEach(function (f) {
      svg.appendChild(el("text", { x: L - 6, y: T + ph - ph * f + 4, "text-anchor": "end", "class": "t-xs t-faint" }, String(Math.round(maxY * f))));
    });
    [0, 0.5, 1].forEach(function (f) {
      svg.appendChild(el("text", { x: L + pw * f, y: T + ph + 16, "text-anchor": "middle", "class": "t-xs t-faint" }, String(Math.round(steps * f))));
    });
    svg.appendChild(el("text", { x: L + pw / 2, y: H - 4, "text-anchor": "middle", "class": "t-xs t-muted" }, "pulls"));
    svg.appendChild(el("text", { x: 12, y: T + 8, "class": "t-xs t-muted" }, "regret"));
    res.forEach(function (r, idx) {
      var pts = r.curve.map(function (v, i) {
        var x = L + pw * (i + 1) / r.curve.length, y = T + ph - ph * v / maxY;
        return (i ? "L" : "M") + x.toFixed(1) + "," + y.toFixed(1);
      }).join(" ");
      svg.appendChild(el("path", { d: pts, fill: "none", "stroke-width": 2.2, "class": "s-" + r.p.color }));
      var lx = L + 12 + idx * 150;
      svg.appendChild(el("line", { x1: lx, y1: T + 8, x2: lx + 18, y2: T + 8, "stroke-width": 3, "class": "s-" + r.p.color }));
      svg.appendChild(el("text", { x: lx + 24, y: T + 12, "class": "t-xs" }, r.p.label));
    });
    tbody.textContent = "";
    res.forEach(function (r) {
      var tr = document.createElement("tr");
      [r.p.label, r.regret.toFixed(1), (100 * r.share).toFixed(0) + "%"].forEach(function (x) {
        var td = document.createElement("td"); td.textContent = x; tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
  }

  var timer = null;
  function schedule() { if (timer) clearTimeout(timer); timer = setTimeout(run, 60); }
  [hIn, cIn, eIn].forEach(function (x) { x.addEventListener("input", schedule); });
  run();
})();
