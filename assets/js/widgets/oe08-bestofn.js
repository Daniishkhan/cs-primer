/* Repeated sampling explorer (A7 chapter 8).
   A stand-in model solves 300 problems. Each problem has its own chance p that one sample is right
   (drawn from a Beta-like spread with the chosen mean). Wrong samples spread over four wrong answers,
   one of which ("the trap") takes a chosen share of them. A verifier gives every sample a noisy score:
   correct ones centre on +1/2, wrong ones on -1/2, with the chosen standard deviation.
   We plot three ways to pick one answer from n samples:
     coverage (an oracle that knows the right answer), majority vote, and best-of-n by verifier score.
   Everything is seeded (mulberry32) so a setting always draws the same picture. */
(function () {
  "use strict";
  var root = document.getElementById("oe08-bestofn");
  if (!root) return;

  var NS = "http://www.w3.org/2000/svg";
  var NS_LIST = [1, 2, 4, 8, 16, 32, 64];
  var NP = 300, REPS = 8;
  var meanIn = root.querySelector("[data-act=mean]"), meanOut = root.querySelector("[data-act=mean-out]");
  var noiseIn = root.querySelector("[data-act=noise]"), noiseOut = root.querySelector("[data-act=noise-out]");
  var trapIn = root.querySelector("[data-act=trap]"), trapOut = root.querySelector("[data-act=trap-out]");
  var nIn = root.querySelector("[data-act=n]"), nOut = root.querySelector("[data-act=n-out]");
  var svg = root.querySelector(".oe08-chart");
  var table = root.querySelector(".oe08-table tbody");
  var note = root.querySelector(".oe08-note");

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
  // Per-problem success chance: p = u^k, with k chosen so that E[p] = 1/(k+1) equals the mean.
  function problems(mean, rng) {
    var k = 1 / mean - 1, out = [], i;
    for (i = 0; i < NP; i++) out.push(Math.pow(rng(), k));
    return out;
  }

  function simulate(mean, noise, trap) {
    var rng = mulberry32(2024), ps = problems(mean, rng);
    var res = [], ni, i, r, j;
    // wrong-answer weights: trap gets `trap`, the other three share the rest
    var other = (1 - trap) / 3;
    for (ni = 0; ni < NS_LIST.length; ni++) {
      var n = NS_LIST[ni], cov = 0, vote = 0, ver = 0, total = NP * REPS;
      for (i = 0; i < NP; i++) {
        for (r = 0; r < REPS; r++) {
          var anyRight = false, counts = [0, 0, 0, 0, 0], bestScore = -1e9, bestRight = false;
          for (j = 0; j < n; j++) {
            var right = rng() < ps[i], ans, score;
            if (right) { ans = 0; score = 0.5 + noise * gauss(rng); anyRight = true; }
            else {
              var u = rng();
              ans = u < trap ? 1 : (u < trap + other ? 2 : (u < trap + 2 * other ? 3 : 4));
              score = -0.5 + noise * gauss(rng);
            }
            counts[ans]++;
            if (score > bestScore) { bestScore = score; bestRight = right; }
          }
          var top = 0, k;
          for (k = 1; k < 5; k++) if (counts[k] > counts[top]) top = k;   // ties go to the right answer's index first
          if (anyRight) cov++;
          if (top === 0 && counts[0] > 0) vote++;
          if (bestRight) ver++;
        }
      }
      res.push({ n: n, cov: cov / total, vote: vote / total, ver: ver / total });
    }
    return res;
  }

  function el(tag, attrs, text) {
    var e = document.createElementNS(NS, tag), k;
    for (k in attrs) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    return e;
  }

  function draw(res, sel) {
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    var W = 640, H = 300, L = 44, R = 14, T = 12, B = 44, pw = W - L - R, ph = H - T - B, i;
    function X(idx) { return L + pw * idx / (NS_LIST.length - 1); }
    function Y(v) { return T + ph * (1 - v); }
    for (i = 0; i <= 4; i++) {
      var v = i / 4;
      svg.appendChild(el("line", { x1: L, y1: Y(v), x2: W - R, y2: Y(v), "class": "grid" }));
      svg.appendChild(el("text", { x: L - 6, y: Y(v) + 4, "text-anchor": "end" }, String(Math.round(v * 100)) + "%"));
    }
    svg.appendChild(el("line", { x1: L, y1: T + ph, x2: W - R, y2: T + ph, "class": "ax" }));
    for (i = 0; i < NS_LIST.length; i++) svg.appendChild(el("text", { x: X(i), y: T + ph + 16, "text-anchor": "middle" }, String(NS_LIST[i])));
    svg.appendChild(el("text", { x: L + pw / 2, y: H - 6, "text-anchor": "middle" }, "samples per problem (n)"));
    svg.appendChild(el("text", { x: 12, y: T + ph / 2, "text-anchor": "middle", transform: "rotate(-90 12 " + (T + ph / 2) + ")" }, "problems solved"));
    svg.appendChild(el("line", { x1: X(sel), y1: T, x2: X(sel), y2: T + ph, "class": "mark" }));
    ["cov", "vote", "ver"].forEach(function (key) {
      var d = "", j;
      for (j = 0; j < res.length; j++) d += (j ? "L" : "M") + X(j).toFixed(1) + "," + Y(res[j][key]).toFixed(1);
      svg.appendChild(el("path", { d: d, "class": "l-" + key }));
    });
    svg.setAttribute("viewBox", "0 0 " + W + " " + H);
  }

  function pct(x) { return (100 * x).toFixed(1) + "%"; }

  function update() {
    var mean = parseFloat(meanIn.value), noise = parseFloat(noiseIn.value), trap = parseFloat(trapIn.value);
    var sel = parseInt(nIn.value, 10);
    meanOut.textContent = pct(mean).replace(".0", "");
    noiseOut.textContent = noise.toFixed(2);
    trapOut.textContent = Math.round(trap * 100) + "%";
    nOut.textContent = String(NS_LIST[sel]);
    var res = simulate(mean, noise, trap);
    draw(res, sel);
    while (table.firstChild) table.removeChild(table.firstChild);
    var tr = document.createElement("tr");
    ["n = " + NS_LIST[sel], pct(res[sel].cov), pct(res[sel].vote), pct(res[sel].ver)].forEach(function (c) {
      var td = document.createElement("td"); td.textContent = c; tr.appendChild(td);
    });
    table.appendChild(tr);
    var last = res[res.length - 1], gap = last.cov - last.ver;
    note.textContent = "At n = 64 the oracle solves " + pct(last.cov) + ", the verifier picks the right one for " + pct(last.ver) +
      " and majority vote for " + pct(last.vote) + ". The gap between coverage and the verifier (" + (100 * gap).toFixed(1) +
      " points) is the cost of an imperfect judge: more samples find answers that the verifier cannot reliably recognise.";
  }

  [meanIn, noiseIn, trapIn, nIn].forEach(function (inp) { inp.addEventListener("input", update); });
  update();
})();
