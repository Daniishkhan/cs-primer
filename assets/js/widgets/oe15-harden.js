/* Evaluator hardening explorer (A7 chapter 15).
   A hill-climbing search improves an agent's honest quality q. Each child also has a small chance of
   discovering each loophole that is still open in the evaluator. A candidate that uses a loophole gets
   the loophole's proxy ceiling as its score, but its true value collapses. The search keeps whichever
   child scores best on the proxy. Defences close loopholes or audit the winners.
   Everything is seeded; "New seed" re-runs with a different random stream. */
(function () {
  "use strict";
  var root = document.getElementById("oe15-harden");
  if (!root) return;

  var NS = "http://www.w3.org/2000/svg";
  var GENS = 60, CHILDREN = 12, FOUND_P = 0.003;
  var HOLES = [
    { key: "tamper", name: "tamper with the grader", ceiling: 1.0, closedBy: "isolate" },
    { key: "lookup", name: "memorise the visible tests", ceiling: 0.95, closedBy: "fresh" },
    { key: "weak", name: "pass the weak check", ceiling: 0.8, closedBy: "check" }
  ];
  var svg = root.querySelector(".oe15-chart"), note = root.querySelector(".oe15-note");
  var newSeed = root.querySelector("[data-act=seed]");
  var boxes = {
    isolate: root.querySelector("[data-act=isolate]"),
    fresh: root.querySelector("[data-act=fresh]"),
    check: root.querySelector("[data-act=check]"),
    audit: root.querySelector("[data-act=audit]")
  };
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
    var u = Math.max(1e-12, rng()), v = rng();
    return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
  }

  function open(def) {
    return HOLES.filter(function (h) { return !def[h.closedBy]; });
  }

  function child(parent, openHoles, rng) {
    var c = { q: Math.max(0, Math.min(0.99, parent.q + gauss(rng) * 0.025 * (1 - parent.q) + 0.002)), found: parent.found.slice() };
    openHoles.forEach(function (h) {
      if (c.found.indexOf(h.key) < 0 && rng() < FOUND_P) c.found.push(h.key);
    });
    var ceil = 0, i;
    for (i = 0; i < openHoles.length; i++) {
      if (c.found.indexOf(openHoles[i].key) >= 0 && openHoles[i].ceiling > ceil) ceil = openHoles[i].ceiling;
    }
    c.hack = ceil > c.q;
    c.proxy = Math.min(1, (c.hack ? ceil : c.q) + gauss(rng) * 0.006);
    c.truth = c.hack ? c.q * 0.25 : c.q;
    return c;
  }

  function run(def, sd) {
    var rng = mulberry32(sd * 7919 + 13), openHoles = open(def);
    var cur = { q: 0.3, found: [], proxy: 0.3, truth: 0.3, hack: false };
    var series = [{ proxy: cur.proxy, truth: cur.truth }], caught = 0, firstHack = -1, g, i;
    for (g = 1; g <= GENS; g++) {
      var kids = [];
      for (i = 0; i < CHILDREN; i++) kids.push(child(cur, openHoles, rng));
      kids.sort(function (a, b) { return b.proxy - a.proxy; });
      var pick = null, rejected = false;
      for (i = 0; i < kids.length; i++) {
        if (def.audit && kids[i].hack && rng() < 0.85) { rejected = true; continue; }
        pick = kids[i]; break;
      }
      if (rejected) caught++;
      if (pick && pick.proxy >= cur.proxy - 0.01) {
        cur = pick;
        if (cur.hack && firstHack < 0) firstHack = g;
      }
      series.push({ proxy: cur.proxy, truth: cur.truth });
    }
    return { series: series, final: cur, caught: caught, firstHack: firstHack, openCount: openHoles.length };
  }

  function el(tag, attrs, text) {
    var e = document.createElementNS(NS, tag), k;
    for (k in attrs) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    return e;
  }

  function draw(res) {
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    var W = 640, H = 270, L = 44, R = 14, T = 12, B = 42, pw = W - L - R, ph = H - T - B, i;
    function X(g) { return L + pw * g / GENS; }
    function Y(v) { return T + ph * (1 - Math.min(1, Math.max(0, v))); }
    for (i = 0; i <= 5; i++) {
      var v = i / 5;
      svg.appendChild(el("line", { x1: L, y1: Y(v), x2: W - R, y2: Y(v), "class": "grid" }));
      svg.appendChild(el("text", { x: L - 6, y: Y(v) + 4, "text-anchor": "end" }, Math.round(v * 100) + "%"));
    }
    svg.appendChild(el("line", { x1: L, y1: T + ph, x2: W - R, y2: T + ph, "class": "ax" }));
    for (i = 0; i <= 6; i++) svg.appendChild(el("text", { x: X(i * 10), y: T + ph + 16, "text-anchor": "middle" }, String(i * 10)));
    svg.appendChild(el("text", { x: L + pw / 2, y: H - 6, "text-anchor": "middle" }, "generation"));
    svg.appendChild(el("text", { x: 12, y: T + ph / 2, "text-anchor": "middle", transform: "rotate(-90 12 " + (T + ph / 2) + ")" }, "score"));
    if (res.firstHack >= 0) {
      svg.appendChild(el("line", { x1: X(res.firstHack), y1: T, x2: X(res.firstHack), y2: T + ph, "class": "mark" }));
    }
    ["proxy", "truth"].forEach(function (key) {
      var d = "", j;
      for (j = 0; j < res.series.length; j++) d += (j ? "L" : "M") + X(j).toFixed(1) + "," + Y(res.series[j][key]).toFixed(1);
      svg.appendChild(el("path", { d: d, "class": key === "proxy" ? "l-proxy" : "l-truth" }));
    });
    svg.setAttribute("viewBox", "0 0 " + W + " " + H);
  }

  function update() {
    var def = { isolate: boxes.isolate.checked, fresh: boxes.fresh.checked, check: boxes.check.checked, audit: boxes.audit.checked };
    var res = run(def, seed);
    draw(res);
    var f = res.final, msg;
    msg = "After " + GENS + " generations the scorer reports " + (100 * f.proxy).toFixed(0) + "% and the agent is really worth " + (100 * f.truth).toFixed(0) + "%. ";
    if (res.openCount === 0) msg += "All three loopholes are closed, so the only way to score is to be good; the two curves stay together. ";
    else if (res.firstHack < 0) msg += "Nothing exploited the " + res.openCount + " open loophole" + (res.openCount > 1 ? "s" : "") + " in this run; try New seed, because discovery is a matter of chance. ";
    else msg += "The search first used a loophole at generation " + res.firstHack + " (dashed line): from there the red curve jumps while the blue one collapses. ";
    if (def.audit) msg += "In " + res.caught + " generations the audit threw out a hacked winner before it was kept.";
    note.textContent = msg;
  }

  Object.keys(boxes).forEach(function (k) { boxes[k].addEventListener("change", update); });
  newSeed.addEventListener("click", function () { seed += 1; update(); });
  update();
})();
