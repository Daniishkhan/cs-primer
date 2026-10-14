/* Selection-pressure explorer (A7 chapter 02).
   A population of real numbers in [0,1] evolves on a landscape with a broad
   peak (left) and a narrow, taller peak (right). Tournament selection plus
   Gaussian mutation, one elite. Seeded, so a given seed replays exactly. */
(function () {
  "use strict";
  var root = document.getElementById("oe02-evolve");
  if (!root) return;

  var NS = "http://www.w3.org/2000/svg";
  var POP = 30;
  var kIn = root.querySelector("[data-act=k]"), kOut = root.querySelector("[data-act=k-out]");
  var sIn = root.querySelector("[data-act=sigma]"), sOut = root.querySelector("[data-act=sigma-out]");
  var seedIn = root.querySelector("[data-act=seed]");
  var stepBtn = root.querySelector("[data-act=step]"), runBtn = root.querySelector("[data-act=run]"), resetBtn = root.querySelector("[data-act=reset]");
  var svg = root.querySelector(".ev-chart"), out = root.querySelector(".ev-out");

  var rng, pop, gen, timer = null;

  function mulberry32(a) {
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      var t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  function f(x) {
    var a = 0.75 * Math.exp(-Math.pow((x - 0.25) / 0.12, 2));
    var b = 1.0 * Math.exp(-Math.pow((x - 0.8) / 0.012, 2));
    return a + b + 0.03 * Math.sin(60 * x);
  }
  function normal() { var u = 1 - rng(), v = rng(); return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v); }
  function clip(x) { return x < 0 ? 0 : (x > 1 ? 1 : x); }

  function reset() {
    stop();
    rng = mulberry32(parseInt(seedIn.value, 10) || 1);
    pop = []; gen = 0;
    for (var i = 0; i < POP; i++) pop.push(rng());
    draw();
  }

  function step() {
    var k = parseInt(kIn.value, 10), sigma = parseFloat(sIn.value);
    var fits = pop.map(f), best = 0, i;
    for (i = 1; i < POP; i++) if (fits[i] > fits[best]) best = i;
    var next = [pop[best]];                       // elitism: keep the best unchanged
    while (next.length < POP) {
      var w = Math.floor(rng() * POP);
      for (var j = 1; j < k; j++) { var c = Math.floor(rng() * POP); if (fits[c] > fits[w]) w = c; }
      next.push(clip(pop[w] + sigma * normal()));
    }
    pop = next; gen++;
    draw();
  }

  function stop() { if (timer) { clearInterval(timer); timer = null; runBtn.textContent = "Run 40 generations"; } }
  function run() {
    if (timer) { stop(); return; }
    var left = 40; runBtn.textContent = "Stop";
    timer = setInterval(function () { step(); if (--left <= 0) stop(); }, 120);
  }

  function el(tag, attrs, text) {
    var e = document.createElementNS(NS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    return e;
  }

  function draw() {
    kOut.textContent = kIn.value; sOut.textContent = parseFloat(sIn.value).toFixed(3);
    var W = 700, H = 230, L = 36, R = 12, T = 12, B = 30, pw = W - L - R, ph = H - T - B, maxY = 1.2;
    function X(x) { return L + pw * x; }
    function Y(y) { return T + ph - ph * Math.max(0, y + 0.05) / maxY; }
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    svg.appendChild(el("line", { x1: L, y1: T + ph, x2: W - R, y2: T + ph, "class": "line-thin" }));
    var d = "";
    for (var i = 0; i <= 400; i++) { var x = i / 400; d += (i ? "L" : "M") + X(x).toFixed(1) + "," + Y(f(x)).toFixed(1) + " "; }
    svg.appendChild(el("path", { d: d, fill: "none", "stroke-width": 2, "class": "s-purple" }));
    svg.appendChild(el("text", { x: X(0.25), y: Y(0.8) - 22, "text-anchor": "middle", "class": "t-xs t-muted" }, "broad peak"));
    svg.appendChild(el("text", { x: X(0.8), y: Y(1.0) - 14, "text-anchor": "middle", "class": "t-xs t-muted" }, "narrow, taller peak"));
    [0, 0.5, 1].forEach(function (v) { svg.appendChild(el("text", { x: X(v), y: H - 10, "text-anchor": "middle", "class": "t-xs t-faint" }, String(v))); });
    var best = -1, sum = 0, mean = 0, sd = 0, bx = 0;
    pop.forEach(function (x) { var y = f(x); sum += y; mean += x; if (y > best) { best = y; bx = x; } });
    mean /= POP; pop.forEach(function (x) { sd += (x - mean) * (x - mean); }); sd = Math.sqrt(sd / POP);
    pop.forEach(function (x) {
      svg.appendChild(el("circle", { cx: X(x).toFixed(1), cy: Y(f(x)).toFixed(1), r: 4.5, "class": "f-yellow", opacity: 0.85 }));
    });
    out.textContent = "Generation " + gen + ". Best fitness " + best.toFixed(3) + " at x = " + bx.toFixed(3) +
      ". Mean fitness " + (sum / POP).toFixed(3) + ". Spread (std of x) " + sd.toFixed(3) +
      (sd < 0.01 ? ". The population has collapsed to one spot." : ".");
  }

  kIn.addEventListener("input", draw);
  sIn.addEventListener("input", draw);
  stepBtn.addEventListener("click", function () { stop(); step(); });
  runBtn.addEventListener("click", run);
  resetBtn.addEventListener("click", reset);
  seedIn.addEventListener("change", reset);
  reset();
})();
