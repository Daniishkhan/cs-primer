/* Entropy, cross-entropy and KL explorer (A0 chapter 14).
   Shape a "true" distribution P with five weights and a model Q with five logits and a
   temperature. The widget shows both as bars and computes H(P), H(Q), H(P,Q), both KL
   divergences and the perplexity of Q on data from P. */
(function () {
  "use strict";
  var root = document.getElementById("mlf14-entropy");
  if (!root) return;
  var NS = "http://www.w3.org/2000/svg";
  var svg = root.querySelector(".mf14-svg"), out = root.querySelector(".mf14-out");
  var pBox = root.querySelector("[data-act=pbox]"), qBox = root.querySelector("[data-act=qbox]");
  var tIn = root.querySelector("[data-act=temp]"), tOut = root.querySelector("[data-act=temp-out]");
  var NAMES = ["the", "a", "cat", "dog", "ran"], K = NAMES.length;
  var P0 = [5, 3, 1.5, 1, 0.5], Q0 = [0, 0, 0, 0, 0];
  var pIn = [], qIn = [], pOut = [], qOut = [];
  var W = 640, H = 230, L = 40, R = 10, T = 14, B = 34;

  function row(box, store, outStore, i, min, max, step, val, tag) {
    var d = document.createElement("div"); d.className = "mf14-row";
    var id = "mf14-" + tag + i;
    d.innerHTML = '<label for="' + id + '">' + NAMES[i] + '</label><input id="' + id + '" type="range" min="' + min + '" max="' + max + '" step="' + step + '" value="' + val + '"><output></output>';
    box.appendChild(d);
    var inp = d.querySelector("input"); inp.addEventListener("input", draw);
    store.push(inp); outStore.push(d.querySelector("output"));
  }
  var i;
  for (i = 0; i < K; i++) row(pBox, pIn, pOut, i, 0, 10, 0.5, P0[i], "p");
  for (i = 0; i < K; i++) row(qBox, qIn, qOut, i, -3, 3, 0.1, Q0[i], "q");
  tIn.addEventListener("input", draw);

  function el(tag, attrs, text) {
    var e = document.createElementNS(NS, tag), k;
    for (k in attrs) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    return e;
  }
  function clear(n) { while (n.firstChild) n.removeChild(n.firstChild); }
  function normalise(w) { var s = 0, j; for (j = 0; j < w.length; j++) s += w[j]; return w.map(function (x) { return s > 0 ? x / s : 1 / w.length; }); }
  function softmax(z, T) {
    var m = -Infinity, j, e = [], s = 0;
    for (j = 0; j < z.length; j++) if (z[j] / T > m) m = z[j] / T;
    for (j = 0; j < z.length; j++) { e[j] = Math.exp(z[j] / T - m); s += e[j]; }
    return e.map(function (x) { return x / s; });
  }
  function ent(p) { var s = 0, j; for (j = 0; j < p.length; j++) if (p[j] > 0) s -= p[j] * Math.log(p[j]) / Math.LN2; return s; }
  function ce(p, q) { var s = 0, j; for (j = 0; j < p.length; j++) if (p[j] > 0) s -= p[j] * Math.log(q[j]) / Math.LN2; return s; }
  function f3(v) { return isFinite(v) ? v.toFixed(3) : "infinity"; }

  function draw() {
    var temp = +tIn.value, j;
    tOut.textContent = temp.toFixed(2);
    var p = normalise(pIn.map(function (x) { return +x.value; }));
    var z = qIn.map(function (x) { return +x.value; });
    var q = softmax(z, temp);
    for (j = 0; j < K; j++) { pOut[j].textContent = p[j].toFixed(2); qOut[j].textContent = (+qIn[j].value).toFixed(1); }
    clear(svg);
    svg.appendChild(el("line", { x1: L, y1: H - B, x2: W - R, y2: H - B, "class": "line-thin" }));
    svg.appendChild(el("line", { x1: L, y1: T, x2: L, y2: H - B, "class": "line-thin" }));
    function Y(v) { return H - B - v * (H - B - 20); }
    [0, 0.5, 1].forEach(function (t) {
      svg.appendChild(el("text", { x: L - 6, y: Y(t) + 4, "text-anchor": "end", "class": "t-xs t-muted" }, String(t)));
      if (t > 0) svg.appendChild(el("line", { x1: L, y1: Y(t), x2: W - R, y2: Y(t), "class": "line-thin", style: "stroke-dasharray:2 4" }));
    });
    var gw = (W - L - R) / K;
    for (j = 0; j < K; j++) {
      var gx = L + j * gw + gw * 0.12, bw = gw * 0.34;
      svg.appendChild(el("rect", { x: gx, y: Y(p[j]), width: bw, height: Math.max(0, H - B - Y(p[j])), style: "fill:var(--blue)" }));
      svg.appendChild(el("rect", { x: gx + bw + 3, y: Y(q[j]), width: bw, height: Math.max(0, H - B - Y(q[j])), style: "fill:var(--orange)" }));
      svg.appendChild(el("text", { x: gx + bw / 2, y: Y(p[j]) - 4, "text-anchor": "middle", "class": "t-xs tc-blue" }, p[j].toFixed(2)));
      svg.appendChild(el("text", { x: gx + bw * 1.5 + 3, y: Y(q[j]) - 4, "text-anchor": "middle", "class": "t-xs tc-orange" }, q[j].toFixed(2)));
      svg.appendChild(el("text", { x: gx + bw + 1.5, y: H - B + 16, "text-anchor": "middle", "class": "t-sm" }, NAMES[j]));
    }
    svg.appendChild(el("text", { x: W - R, y: 12, "text-anchor": "end", "class": "t-xs t-muted" }, "blue: P (the truth)   orange: Q (the model)"));
    var hp = ent(p), hq = ent(q), hpq = ce(p, q), klpq = hpq - hp, klqp = ce(q, p) - hq;
    clear(out);
    [["H(P) entropy of the truth", f3(hp) + " bits"], ["H(Q) entropy of the model", f3(hq) + " bits"],
     ["H(P,Q) cross-entropy", f3(hpq) + " bits"], ["KL(P || Q) = H(P,Q) - H(P)", f3(klpq) + " bits"],
     ["KL(Q || P)", f3(klqp) + " bits"], ["perplexity of Q on P: 2^H(P,Q)", isFinite(hpq) ? Math.pow(2, hpq).toFixed(2) : "infinity"],
     ["best possible perplexity: 2^H(P)", Math.pow(2, hp).toFixed(2)], ["temperature applied to Q", temp.toFixed(2)]].forEach(function (r) {
      var d = document.createElement("div"); d.innerHTML = r[0] + " = <b></b>"; d.querySelector("b").textContent = r[1]; out.appendChild(d);
    });
  }
  function setQ(logits) { var j; for (j = 0; j < K; j++) qIn[j].value = logits[j]; tIn.value = 1; draw(); }
  root.querySelector("[data-act=match]").addEventListener("click", function () {
    var p = normalise(pIn.map(function (x) { return +x.value; }));
    setQ(p.map(function (x) { return Math.max(-3, Math.min(3, Math.round((Math.log(Math.max(x, 1e-6)) - Math.log(p[0])) * 10) / 10)); }));
  });
  root.querySelector("[data-act=uniform]").addEventListener("click", function () { setQ([0, 0, 0, 0, 0]); });
  root.querySelector("[data-act=wrong]").addEventListener("click", function () { setQ([-3, -2, 0, 1.5, 3]); });
  root.querySelector("[data-act=reset]").addEventListener("click", function () {
    var j; for (j = 0; j < K; j++) pIn[j].value = P0[j];
    setQ(Q0);
  });
  draw();
})();
