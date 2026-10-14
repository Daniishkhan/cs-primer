/* MAP-Elites archive explorer (A7 chapter 4).
   An 8-joint planar arm. Behaviour = where the hand ends up (x, y), binned on a grid.
   Quality = 1 / (1 + 5 * variance of the joint angles): smooth arms score high.
   Methods: MAP-Elites (mutate a random elite) or random sampling into the same archive.
   Everything is seeded (mulberry32) so a given setting always draws the same picture. */
(function () {
  "use strict";
  var root = document.getElementById("oe04-mapelites");
  if (!root) return;

  var NJ = 8, NS = "http://www.w3.org/2000/svg";
  var evalsIn = root.querySelector("[data-act=evals]"), evalsOut = root.querySelector("[data-act=evals-out]");
  var sigIn = root.querySelector("[data-act=sigma]"), sigOut = root.querySelector("[data-act=sigma-out]");
  var resSel = root.querySelector("[data-act=res]");
  var methSel = root.querySelector("[data-act=method]");
  var seedBtn = root.querySelector("[data-act=seed]");
  var svg = root.querySelector(".oe04-grid");
  var stats = root.querySelector(".oe04-stats");
  var note = root.querySelector(".oe04-note");
  var seed = 1;
  var EVALS = [200, 500, 1000, 2000, 5000, 10000, 20000, 50000];

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
  function evaluate(g) {
    var a = 0, x = 0, y = 0, sum = 0, i, t = [];
    for (i = 0; i < NJ; i++) { t.push((g[i] - 0.5) * 2 * Math.PI); sum += t[i]; }
    var m = sum / NJ, v = 0;
    for (i = 0; i < NJ; i++) {
      a += t[i]; x += Math.cos(a) / NJ; y += Math.sin(a) / NJ;
      v += (t[i] - m) * (t[i] - m);
    }
    return { x: x, y: y, q: 1 / (1 + 5 * v / NJ) };
  }
  function randGenome(rng) { var g = [], i; for (i = 0; i < NJ; i++) g.push(rng()); return g; }
  function mutate(g, rng, sigma) {
    var out = g.slice(), i;
    for (i = 0; i < NJ; i++) if (rng() < 0.3) out[i] = Math.min(1, Math.max(0, out[i] + sigma * gauss(rng)));
    return out;
  }

  function run(n, res, sigma, method, sd) {
    var rng = mulberry32(sd * 7919 + 13), cells = {}, keys = [], e, g, r, i, j, k, c;
    for (e = 0; e < n; e++) {
      if (method === "random" || e < 100 || keys.length === 0) g = randGenome(rng);
      else g = mutate(cells[keys[Math.floor(rng() * keys.length)]].g, rng, sigma);
      r = evaluate(g);
      i = Math.min(res - 1, Math.floor((r.x + 1) / 2 * res));
      j = Math.min(res - 1, Math.floor((r.y + 1) / 2 * res));
      k = i + "," + j; c = cells[k];
      if (!c) { cells[k] = { g: g, q: r.q, i: i, j: j }; keys.push(k); }
      else if (r.q > c.q) { cells[k] = { g: g, q: r.q, i: i, j: j }; }
    }
    return { cells: cells, keys: keys };
  }

  function el(tag, attrs) {
    var e = document.createElementNS(NS, tag), k;
    for (k in attrs) e.setAttribute(k, attrs[k]);
    return e;
  }
  function stat(label, value) {
    var d = document.createElement("div"), b = document.createElement("b"), s = document.createElement("span");
    b.textContent = value; s.textContent = label; d.appendChild(b); d.appendChild(s); return d;
  }

  function update() {
    var n = EVALS[parseInt(evalsIn.value, 10)], sigma = parseFloat(sigIn.value);
    var res = parseInt(resSel.value, 10), method = methSel.value;
    evalsOut.textContent = n.toLocaleString("en-GB");
    sigOut.textContent = sigma.toFixed(2);
    var out = run(n, res, sigma, method, seed);
    var W = 320, pad = 18, cs = (W - pad * 2) / res, i, j, key, c, qd = 0, best = 0;
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    svg.setAttribute("viewBox", "0 0 " + W + " " + (W + 6));
    for (i = 0; i < res; i++) for (j = 0; j < res; j++) {
      key = i + "," + j; c = out.cells[key];
      var rect = el("rect", { x: (pad + i * cs).toFixed(2), y: (pad + (res - 1 - j) * cs).toFixed(2),
        width: Math.max(0.5, cs - (res > 20 ? 0.3 : 0.8)).toFixed(2), height: Math.max(0.5, cs - (res > 20 ? 0.3 : 0.8)).toFixed(2) });
      if (c) { rect.setAttribute("class", "full"); rect.setAttribute("fill-opacity", (0.15 + 0.85 * c.q).toFixed(2)); qd += c.q; if (c.q > best) best = c.q; }
      else rect.setAttribute("class", "empty");
      svg.appendChild(rect);
    }
    svg.appendChild(el("rect", { "class": "frame", x: pad, y: pad, width: W - pad * 2, height: W - pad * 2 }));
    var t1 = el("text", { x: W / 2, y: 12, "text-anchor": "middle" }); t1.textContent = "hand y (up)";
    var t2 = el("text", { x: W / 2, y: W + 2, "text-anchor": "middle" }); t2.textContent = "hand x (right)";
    svg.appendChild(t1); svg.appendChild(t2);
    var total = res * res, filled = out.keys.length;
    while (stats.firstChild) stats.removeChild(stats.firstChild);
    stats.appendChild(stat("cells filled", filled + " of " + total));
    stats.appendChild(stat("coverage", (100 * filled / total).toFixed(0) + "%"));
    stats.appendChild(stat("QD-score", qd.toFixed(1)));
    stats.appendChild(stat("best quality", best.toFixed(3)));
    stats.appendChild(stat("mean quality", filled ? (qd / filled).toFixed(3) : "0"));
    note.textContent = (method === "map" ? "MAP-Elites: each new arm mutates a random elite, then competes only for the cell its hand lands in. "
      : "Random sampling: arms drawn blindly, kept if best in their cell. ") +
      "Darker purple means higher quality. About a fifth of the corners can never be filled, because the hand cannot leave the unit circle.";
  }

  evalsIn.addEventListener("input", update);
  sigIn.addEventListener("input", update);
  resSel.addEventListener("change", update);
  methSel.addEventListener("change", update);
  seedBtn.addEventListener("click", function () { seed += 1; update(); });
  update();
})();
