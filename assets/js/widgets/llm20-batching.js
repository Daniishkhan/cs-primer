/* Static versus continuous batching timeline (A3 chapter 20).
   Each request needs a number of decode steps (lognormal, seeded). A decode step produces one token for every
   running request and is assumed to take the same time whatever the number of running requests (memory-bound decode).
   Static batching: take SLOTS requests, run until the longest finishes, then take the next SLOTS.
   Continuous batching: after every step, finished requests leave and waiting ones take their slots.
   Prefill is ignored; this isolates the scheduling effect. */
(function () {
  "use strict";
  var root = document.getElementById("llm20-batching");
  if (!root) return;
  var NS = "http://www.w3.org/2000/svg";
  var COLS = ["f-blue", "f-cyan", "f-green", "f-purple", "f-orange", "f-teal"];

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
  function el(tag, attrs, text) {
    var e = document.createElementNS(NS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    return e;
  }
  var $ = function (s) { return root.querySelector(s); };
  var slotsIn = $("[data-act=slots]"), slotsOut = $("[data-act=slots-out]"),
      spreadIn = $("[data-act=spread]"), spreadOut = $("[data-act=spread-out]"),
      nIn = $("[data-act=n]"), nOut = $("[data-act=n-out]"), newBtn = $("[data-act=new]"),
      svgS = $(".l20-static"), svgC = $(".l20-cont"), statS = $(".l20-stat-s"), statC = $(".l20-stat-c");
  var seed = 21;

  function lengths(n, spread) {
    var rng = mulberry32(seed), out = [];
    for (var i = 0; i < n; i++) out.push(Math.max(3, Math.min(120, Math.round(Math.exp(3.0 + spread * normal(rng))))));
    return out;
  }
  // Each schedule is a list of segments {slot, start, len, id}; total = number of steps.
  function staticSched(len, S) {
    var segs = [], t = 0, doneAt = [];
    for (var i = 0; i < len.length; i += S) {
      var batch = len.slice(i, i + S), mx = Math.max.apply(null, batch);
      for (var j = 0; j < batch.length; j++) { segs.push({ slot: j, start: t, len: batch[j], id: i + j }); doneAt.push(t + mx); }
      t += mx;
    }
    return { segs: segs, total: t, doneAt: doneAt };
  }
  function contSched(len, S) {
    var segs = [], free = [], doneAt = [], next = 0, t = 0, run = [];
    for (var s = 0; s < S; s++) run.push(null);
    var finished = 0;
    while (finished < len.length) {
      for (var s2 = 0; s2 < S; s2++) if (run[s2] === null && next < len.length) { run[s2] = { id: next, left: len[next], start: t }; next++; }
      t++;
      for (var s3 = 0; s3 < S; s3++) {
        var r = run[s3];
        if (r) { r.left--; if (r.left === 0) { segs.push({ slot: s3, start: r.start, len: len[r.id], id: r.id }); doneAt[r.id] = t; run[s3] = null; finished++; } }
      }
    }
    return { segs: segs, total: t, doneAt: doneAt };
  }
  function draw(svg, sched, S, maxT) {
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    var W = 700, L = 34, H = S * 14 + 30, pw = W - L - 8;
    svg.setAttribute("viewBox", "0 0 " + W + " " + H);
    svg.appendChild(el("rect", { x: L, y: 4, width: pw, height: S * 14, "class": "box" }));
    for (var s = 0; s < S; s++) svg.appendChild(el("text", { x: L - 6, y: 4 + s * 14 + 11, "text-anchor": "end", "class": "t-xs t-faint" }, "" + (s + 1)));
    sched.segs.forEach(function (g) {
      svg.appendChild(el("rect", { x: (L + pw * g.start / maxT).toFixed(1), y: 5 + g.slot * 14, width: Math.max(1, pw * g.len / maxT - 1).toFixed(1), height: 12, rx: 2, "class": COLS[g.id % COLS.length] }));
    });
    svg.appendChild(el("text", { x: L, y: S * 14 + 22, "class": "t-xs t-muted" }, "step 0"));
    svg.appendChild(el("text", { x: L + pw, y: S * 14 + 22, "text-anchor": "end", "class": "t-xs t-muted" }, "step " + maxT));
  }
  function stats(box, name, sched, len, S) {
    var useful = len.reduce(function (a, b) { return a + b; }, 0), t = sched.total;
    var mean = sched.doneAt.reduce(function (a, b) { return a + b; }, 0) / len.length;
    box.innerHTML = "";
    var st = document.createElement("strong"); st.textContent = name; box.appendChild(st);
    var p = document.createElement("span");
    p.textContent = t + " steps; " + (useful / t).toFixed(1) + " tokens per step; slots busy " + Math.round(100 * useful / (t * S)) + "%; mean time to finish " + mean.toFixed(0) + " steps.";
    box.appendChild(p);
  }
  function run() {
    var S = parseInt(slotsIn.value, 10), spread = parseInt(spreadIn.value, 10) / 10, n = parseInt(nIn.value, 10);
    slotsOut.textContent = S; spreadOut.textContent = spread.toFixed(1); nOut.textContent = n;
    var len = lengths(n, spread), a = staticSched(len, S), b = contSched(len, S);
    var maxT = Math.max(a.total, b.total);
    draw(svgS, a, S, maxT); draw(svgC, b, S, maxT);
    stats(statS, "Static batching", a, len, S); stats(statC, "Continuous batching", b, len, S);
  }
  slotsIn.addEventListener("input", run); spreadIn.addEventListener("input", run); nIn.addEventListener("input", run);
  newBtn.addEventListener("click", function () { seed = (seed * 7 + 13) % 100003; run(); });
  run();
})();
