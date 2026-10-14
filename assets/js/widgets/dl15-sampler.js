/* Decoding explorer (A2 chapter 15).
   A fixed set of next-token logits (invented for illustration, not from a real model). The pipeline is
   logits / temperature -> softmax -> top-k -> top-p -> min-p -> renormalise -> sample.
   Hollow bars: the distribution at temperature 1. Filled bars: what is sampled from. Greyed: removed. */
(function () {
  "use strict";
  var root = document.getElementById("dl15-sampler");
  if (!root) return;
  var NS = "http://www.w3.org/2000/svg";
  var q = function (sel) { return root.querySelector(sel); };
  var sets = {
    fact: { prompt: "The capital of France is", toks: [" Paris", " the", " a", " located", " known", " not", " one", " also", " Lyon", " Marseille", " beautiful", " Berlin"],
            logits: [8.0, 4.6, 3.8, 3.4, 3.0, 2.7, 2.2, 1.9, 1.6, 1.0, 0.4, -0.4] },
    story: { prompt: "Once upon a time there lived a", toks: [" little", " young", " king", " poor", " girl", " wise", " dragon", " brave", " old", " princess", " man", " fox"],
             logits: [3.0, 2.8, 2.7, 2.5, 2.4, 2.2, 2.0, 1.9, 1.7, 1.5, 1.2, 0.6] }
  };
  var setSel = q("[data-act=set]"), tauIn = q("[data-act=tau]"), tauOut = q("[data-act=tau-out]"),
      kIn = q("[data-act=k]"), kOut = q("[data-act=k-out]"), pIn = q("[data-act=p]"), pOut = q("[data-act=p-out]"),
      mIn = q("[data-act=m]"), mOut = q("[data-act=m-out]"), sampleBtn = q("[data-act=sample]");
  var svg = q(".dl15-chart"), summary = q(".dl15-summary"), counts = q(".dl15-counts");
  var seed = 11, last = null;

  function el(tag, attrs, text) {
    var e = document.createElementNS(NS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    return e;
  }
  function mulberry32(a) {
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      var t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  function softmax(l, tau) {
    var m = Math.max.apply(null, l), e = l.map(function (v) { return Math.exp((v - m) / tau); });
    var s = e.reduce(function (a, b) { return a + b; }, 0);
    return e.map(function (v) { return v / s; });
  }
  function entropy(p) { return p.reduce(function (a, v) { return v > 0 ? a - v * Math.log(v) / Math.LN2 : a; }, 0); }

  function compute() {
    var S = sets[setSel.value], tau = Math.pow(10, parseFloat(tauIn.value)), n = S.toks.length;
    var k = parseInt(kIn.value, 10), top = parseFloat(pIn.value), mp = parseFloat(mIn.value);
    var base = softmax(S.logits, 1), p = softmax(S.logits, tau);
    var keep = p.map(function () { return true; }), order = p.map(function (_, i) { return i; });
    order.sort(function (a, b) { return p[b] - p[a]; });
    var i;
    if (k < n) order.forEach(function (idx, r) { if (r >= k) keep[idx] = false; });
    if (top < 1) {                                      // smallest set, in order, whose mass reaches top
      var cum = 0, mass = 0;
      for (i = 0; i < n; i++) if (keep[i]) mass += p[i];  // top-p works on the distribution left after top-k
      order.forEach(function (idx) {
        if (!keep[idx]) return;
        if (cum >= top) keep[idx] = false; else cum += p[idx] / mass;
      });
    }
    if (mp > 0) for (i = 0; i < n; i++) if (p[i] < mp * p[order[0]]) keep[i] = false;
    var tot = 0; for (i = 0; i < n; i++) if (keep[i]) tot += p[i];
    var fin = p.map(function (v, j) { return keep[j] ? v / tot : 0; });
    return { S: S, tau: tau, base: base, p: p, keep: keep, fin: fin, kept: tot };
  }

  function draw() {
    var r = compute(), S = r.S, n = S.toks.length, i;
    tauOut.textContent = r.tau.toFixed(2);
    kOut.textContent = parseInt(kIn.value, 10) >= n ? "off" : kIn.value;
    pOut.textContent = parseFloat(pIn.value) >= 1 ? "off" : parseFloat(pIn.value).toFixed(2);
    mOut.textContent = parseFloat(mIn.value) <= 0 ? "off" : parseFloat(mIn.value).toFixed(2);
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    var x0 = 120, bw = 430, top = 22, rowH = 24;
    svg.appendChild(el("text", { x: 10, y: 14, "class": "t-xs t-muted" }, "next token after \"" + S.prompt + "\""));
    svg.appendChild(el("text", { x: x0 + bw + 14, y: 14, "class": "t-xs t-muted" }, "probability used"));
    var order = r.p.map(function (_, j) { return j; }).sort(function (a, b) { return r.p[b] - r.p[a]; });
    order.forEach(function (j, row) {
      var y = top + row * rowH;
      svg.appendChild(el("text", { x: x0 - 8, y: y + 15, "text-anchor": "end", "class": "mono t-sm" + (r.keep[j] ? "" : " t-faint") }, JSON.stringify(S.toks[j]).slice(1, -1)));
      svg.appendChild(el("rect", { x: x0, y: y + 3, width: bw, height: 16, rx: 3, "class": "box", opacity: 0.45 }));
      svg.appendChild(el("rect", { x: x0, y: y + 3, width: Math.max(1, bw * r.base[j]), height: 16, rx: 3, fill: "none", "class": "s-cyan sw-1", "stroke-dasharray": "3 3" }));
      if (r.keep[j]) svg.appendChild(el("rect", { x: x0, y: y + 3, width: Math.max(1, bw * r.fin[j]), height: 16, rx: 3, "class": "f-blue", opacity: 0.9 }));
      else svg.appendChild(el("rect", { x: x0, y: y + 3, width: Math.max(1, bw * r.p[j]), height: 16, rx: 3, "class": "f-red", opacity: 0.25 }));
      svg.appendChild(el("text", { x: x0 + bw + 14, y: y + 15, "class": "mono t-sm" + (r.keep[j] ? "" : " t-faint") }, r.keep[j] ? r.fin[j].toFixed(3) : "removed"));
    });
    var kept = r.keep.filter(Boolean).length;
    summary.textContent = "Temperature " + r.tau.toFixed(2) + " leaves " + (entropy(r.p)).toFixed(2) + " bits of uncertainty (temperature 1: " + entropy(r.base).toFixed(2) + "). The filters keep " + kept + " of " + n +
      " tokens holding " + (100 * r.kept).toFixed(1) + "% of the temperature-adjusted mass; after renormalising, the entropy is " + entropy(r.fin).toFixed(2) + " bits.";
    counts.textContent = "";
    last = r;
  }

  function sample() {
    var r = last || compute(), rng, c = [], i, u, acc, tot = 1000;
    seed = (seed * 1103515245 + 12345) & 0x7fffffff; rng = mulberry32(seed);
    for (i = 0; i < r.fin.length; i++) c.push(0);
    for (var t = 0; t < tot; t++) {
      u = rng(); acc = 0; var pick = -1;
      for (i = 0; i < r.fin.length; i++) if (r.fin[i] > 0) { acc += r.fin[i]; pick = i; if (u < acc) break; }
      c[pick]++;
    }
    var lines = [];
    r.S.toks.forEach(function (w, j) { if (c[j] > 0) lines.push((JSON.stringify(w).slice(1, -1) + "            ").slice(0, 13) + ("     " + c[j]).slice(-5) + " / 1000"); });
    counts.textContent = "1000 samples:\n" + lines.join("\n");
  }
  [tauIn, kIn, pIn, mIn].forEach(function (c) { c.addEventListener("input", draw); });
  setSel.addEventListener("change", draw);
  sampleBtn.addEventListener("click", sample);
  draw();
})();
