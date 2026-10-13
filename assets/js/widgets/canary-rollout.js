/* Canary rollout simulator (reliability chapter 12).
   24 cells are updated in waves (1, 3, 8, 12). In each wave the newly updated "canary" cells are compared with a
   "baseline": the same number of fresh instances of the OLD build started at the same time. The judge is a
   Mann-Whitney U (rank-sum) test plus an effect-size rule, run on the whole bake window and on its final 10 minutes.
   Bugs: none, latency +30%, errors +2 pp, or a "leak" that only starts to hurt 20 minutes after a cell was updated
   (so a short bake time cannot see it). Deterministic: a seeded PRNG drives all noise. */
(function () {
  "use strict";

  var WAVES = [1, 3, 8, 12];
  var WAVE_NAMES = ["one cell", "one AZ", "one region", "everyone"];
  var PER_MIN = 6;               // samples per group per minute
  var TAIL = 40;                 // minutes the clock keeps running after the last wave

  function rng(seed) {
    var a = seed >>> 0;
    return function () {
      a = (a + 0x6D2B79F5) >>> 0;
      var t = a;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  function gauss(r) {
    var u = 1 - r(), v = r();
    return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
  }
  function erfc(x) {              // Numerical Recipes rational approximation, |error| < 1.2e-7
    var z = Math.abs(x), t = 1 / (1 + 0.5 * z);
    var r = t * Math.exp(-z * z - 1.26551223 + t * (1.00002368 + t * (0.37409196 + t * (0.09678418 +
      t * (-0.18628806 + t * (0.27886807 + t * (-1.13520398 + t * (1.48851587 + t * (-0.82215223 + t * 0.17087277)))))))));
    return x >= 0 ? r : 2 - r;
  }
  function median(a) {
    var s = a.slice().sort(function (x, y) { return x - y; }), n = s.length;
    return n % 2 ? s[(n - 1) / 2] : (s[n / 2 - 1] + s[n / 2]) / 2;
  }
  /* two-sided Mann-Whitney U, normal approximation with tie correction; z > 0 means a tends to exceed b */
  function rankSum(a, b) {
    var n1 = a.length, n2 = b.length, n = n1 + n2, i, j, k;
    var all = [];
    for (i = 0; i < n1; i++) all.push([a[i], 0]);
    for (i = 0; i < n2; i++) all.push([b[i], 1]);
    all.sort(function (x, y) { return x[0] - y[0]; });
    var r1 = 0, tie = 0;
    i = 0;
    while (i < n) {
      j = i;
      while (j + 1 < n && all[j + 1][0] === all[i][0]) j++;
      var avg = (i + j) / 2 + 1, t = j - i + 1;
      tie += t * t * t - t;
      for (k = i; k <= j; k++) if (all[k][1] === 0) r1 += avg;
      i = j + 1;
    }
    var u1 = r1 - n1 * (n1 + 1) / 2, mu = n1 * n2 / 2;
    var v = n1 * n2 / 12 * ((n + 1) - tie / (n * (n - 1)));
    if (v <= 0) return { z: 0, p: 1 };
    var z = (u1 - mu) / Math.sqrt(v);
    return { z: z, p: erfc(Math.abs(z) / Math.SQRT2) };
  }
  /* decision rule: fail only if significant AND the effect is big enough to matter */
  function judge(canLat, baseLat, canErr, baseErr) {
    var l = rankSum(canLat, baseLat), e = rankSum(canErr, baseErr);
    var ratio = median(canLat) / median(baseLat), dErr = median(canErr) - median(baseErr);
    var latBad = l.p < 0.01 && ratio > 1.10, errBad = e.p < 0.01 && dErr > 0.3;
    return { fail: latBad || errBad, latP: l.p, ratio: ratio, errP: e.p, dErr: dErr,
             why: latBad ? "latency " + ((ratio - 1) * 100).toFixed(0) + "% higher than baseline (p<0.01)"
                : errBad ? "error rate " + dErr.toFixed(1) + " pp higher than baseline (p<0.01)" : "" };
  }

  var core = { rankSum: rankSum, judge: judge, median: median };
  if (typeof module !== "undefined" && module.exports) module.exports = core;
  if (typeof document === "undefined") return;
  var root = document.getElementById("canary-rollout");
  if (!root) return;

  var NS = "http://www.w3.org/2000/svg";
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  function el(tag, attrs, text) {
    var e = document.createElement(tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    return e;
  }
  function sv(tag, attrs, text) {
    var e = document.createElementNS(NS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    return e;
  }

  /* ---------- state ---------- */
  var S;
  function fresh() {
    var cells = [], w = 0, c, n = 0;
    for (w = 0; w < WAVES.length; w++) for (c = 0; c < WAVES[w]; c++) cells.push({ wave: w, n: ++n, since: -1, state: "old" });
    S = { r: rng(42), t: 0, wave: 0, waveStart: 0, cells: cells, done: false, halted: false, msg: "Ready. Wave 1 will update one cell.",
          series: [], samples: null, marks: [], timer: null, tail: 0 };
    S.samples = { cl: [], bl: [], ce: [], be: [] };
  }
  fresh();

  /* ---------- controls ---------- */
  var head = el("div", { "class": "widget-head" });
  head.appendChild(el("span", { "class": "widget-tag" }, "Try it"));
  head.appendChild(el("h4", { "class": "widget-title" }, "Roll out a build in waves"));
  root.appendChild(head);
  root.appendChild(el("p", { "class": "widget-help" },
    "Choose what is wrong with the new build and how long each wave bakes. The judge compares each wave's canary cells with baseline instances started at the same time. Try the leak with a 10-minute bake, then with 30."));

  var ctl = el("div", { "class": "cr-ctl" });
  var bugWrap = el("div"); bugWrap.appendChild(el("label", { "for": "cr-bug" }, "What is wrong with the new build?"));
  var bugSel = el("select", { id: "cr-bug" });
  [["none", "Nothing (a good build)"], ["lat", "Latency +30%"], ["err", "Errors +2 percentage points"], ["leak", "Leak: slows down 20 minutes after start"]]
    .forEach(function (o) { bugSel.appendChild(el("option", { value: o[0] }, o[1])); });
  bugSel.value = "lat";
  bugWrap.appendChild(bugSel);
  var bakeWrap = el("div");
  var bakeLab = el("label", { "for": "cr-bake" }, "Bake time per wave: ");
  var bakeOut = el("output", { "class": "cr-mono", "for": "cr-bake" }, "15 min");
  bakeLab.appendChild(bakeOut);
  var bakeIn = el("input", { type: "range", id: "cr-bake", min: "5", max: "40", step: "5", value: "15" });
  bakeWrap.appendChild(bakeLab); bakeWrap.appendChild(bakeIn);
  var haltWrap = el("div", { "class": "cr-check" });
  var haltCb = el("input", { type: "checkbox", id: "cr-halt" }); haltCb.checked = true;
  haltWrap.appendChild(haltCb); haltWrap.appendChild(el("label", { "for": "cr-halt" }, "Automatic halt and rollback on a failed judgement"));
  ctl.appendChild(bugWrap); ctl.appendChild(bakeWrap); ctl.appendChild(haltWrap);
  root.appendChild(ctl);

  var btns = el("div", { "class": "widget-row" });
  var runBtn = el("button", { type: "button", "class": "btn primary" }, "Run rollout");
  var stepBtn = el("button", { type: "button", "class": "btn" }, "+1 minute");
  var resetBtn = el("button", { type: "button", "class": "btn" }, "Reset");
  btns.appendChild(runBtn); btns.appendChild(stepBtn); btns.appendChild(resetBtn);
  root.appendChild(btns);

  var status = el("p", { "class": "cr-status", "aria-live": "polite" });
  root.appendChild(status);
  var grid = el("div", { "class": "cr-grid", role: "group", "aria-label": "Cells grouped by wave" });
  root.appendChild(grid);
  var legend = el("p", { "class": "cr-legend" });
  legend.innerHTML = '<span class="cr-key old"></span> old build <span class="cr-key new"></span> new build, passing <span class="cr-key bad"></span> new build, hurting users <span class="cr-key rb"></span> rolled back';
  root.appendChild(legend);
  var stats = el("div", { "class": "cr-stats" });
  root.appendChild(stats);
  var chart = el("div", { "class": "cr-chart" });
  root.appendChild(chart);

  /* ---------- model ---------- */
  function bug() { return bugSel.value; }
  function bake() { return parseInt(bakeIn.value, 10); }
  function effect(age) {                       // latency multiplier minus 1, and error pp, for a cell of this age
    var b = bug();
    if (b === "lat") return { lat: 0.30, err: 0 };
    if (b === "err") return { lat: 0, err: 2 };
    if (b === "leak") return { lat: age > 20 ? 0.04 * (age - 20) : 0, err: 0 };
    return { lat: 0, err: 0 };
  }
  function hurting(c) {
    if (c.state !== "new") return false;
    var e = effect(S.t - c.since);
    return e.lat >= 0.10 || e.err >= 0.3;
  }

  function tick() {
    if (S.done && S.tail >= TAIL) return;
    var i, e, cells = S.cells.filter(function (c) { return c.wave === S.wave && c.state === "new"; });
    if (!S.done && S.t === S.waveStart) {      // start of wave: update this wave's cells
      S.cells.forEach(function (c) { if (c.wave === S.wave) { c.state = "new"; c.since = S.t; } });
      S.msg = "Wave " + (S.wave + 1) + " (" + WAVE_NAMES[S.wave] + "): " + WAVES[S.wave] + " cell" + (WAVES[S.wave] > 1 ? "s" : "") + " updated. Baking for " + bake() + " minutes.";
    }
    S.t++;
    if (S.done) { S.tail++; }
    else {
      var age = S.t - S.waveStart, ef = effect(age);
      var cLat = 0, bLat = 0;
      for (i = 0; i < PER_MIN; i++) {
        var cl = 100 * Math.exp(0.12 * gauss(S.r)) * (1 + ef.lat), bl = 100 * Math.exp(0.12 * gauss(S.r));
        var ce = Math.max(0, 0.1 + ef.err + 0.05 * gauss(S.r)), be = Math.max(0, 0.1 + 0.05 * gauss(S.r));
        S.samples.cl.push(cl); S.samples.bl.push(bl); S.samples.ce.push(ce); S.samples.be.push(be);
        cLat += cl; bLat += bl;
      }
      S.series.push({ t: S.t, c: cLat / PER_MIN, b: bLat / PER_MIN });
      if (age >= bake()) {
        var sm = S.samples, tailN = 10 * PER_MIN;      // judge the whole bake and its final 10 minutes, so a late trend is not diluted
        var v = judge(sm.cl, sm.bl, sm.ce, sm.be), v2 = judge(sm.cl.slice(-tailN), sm.bl.slice(-tailN), sm.ce.slice(-tailN), sm.be.slice(-tailN));
        if (!v.fail && v2.fail) v = v2;
        S.samples = { cl: [], bl: [], ce: [], be: [] };
        if (v.fail && haltCb.checked) {
          S.cells.forEach(function (c) { if (c.state === "new") c.state = "rb"; });
          S.done = true; S.halted = true;
          S.marks.push({ t: S.t, kind: "halt" });
          S.msg = "Wave " + (S.wave + 1) + " FAILED the judge: " + v.why + ". Halted and rolled back.";
        } else {
          S.marks.push({ t: S.t, kind: v.fail ? "ignored" : "pass" });
          if (S.wave === WAVES.length - 1) {
            S.done = true;
            S.msg = "Rollout complete. " + (v.fail ? "The judge objected (" + v.why + ") but halting was off." : "Every wave passed the judge.") + " The clock keeps running for " + TAIL + " more minutes.";
          } else {
            S.msg = "Wave " + (S.wave + 1) + " " + (v.fail ? "FAILED (" + v.why + ") but halting is off, so the rollout continues." : "passed (latency ratio " + v.ratio.toFixed(2) + ", p=" + v.latP.toFixed(2) + ").");
            S.wave++; S.waveStart = S.t;
          }
        }
      }
    }
  }

  /* ---------- render ---------- */
  function render() {
    grid.textContent = "";
    var w, g;
    for (w = 0; w < WAVES.length; w++) {
      g = el("div", { "class": "cr-wave" });
      g.appendChild(el("small", {}, "Wave " + (w + 1) + ": " + WAVE_NAMES[w]));
      var row = el("div", { "class": "cr-cells" });
      S.cells.forEach(function (c) {
        if (c.wave !== w) return;
        var cls = c.state === "rb" ? "rb" : c.state === "new" ? (hurting(c) ? "bad" : "new") : "old";
        row.appendChild(el("span", { "class": "cr-cell " + cls, title: "cell " + c.n + ": " + cls }, String(c.n)));
      });
      g.appendChild(row); grid.appendChild(g);
    }
    var nNew = S.cells.filter(function (c) { return c.state === "new"; }).length;
    var nBad = S.cells.filter(hurting).length;
    var pct = Math.round(100 * nBad / S.cells.length);
    status.textContent = S.msg;
    status.className = "cr-status " + (S.halted ? "warn" : nBad ? "bad" : "ok");
    stats.textContent = "";
    [["Minute", String(S.t)], ["Cells on new build", nNew + " / " + S.cells.length], ["Cells hurting users", nBad + " (" + pct + "%)"],
     ["Bake", bake() + " min"]].forEach(function (p) {
      var d = el("div", { "class": "cr-stat" }); d.appendChild(el("small", {}, p[0])); d.appendChild(el("b", {}, p[1])); stats.appendChild(d);
    });
    drawChart();
    runBtn.textContent = S.timer ? "Pause" : (S.done && S.tail >= TAIL ? "Finished" : "Run rollout");
    runBtn.disabled = S.done && S.tail >= TAIL;
    stepBtn.disabled = S.done && S.tail >= TAIL;
  }

  function drawChart() {
    var W = 700, H = 200, L = 46, R = 12, T = 14, B = 34;
    var maxT = WAVES.length * bake() + TAIL, yMax = 180;
    function X(t) { return L + (W - L - R) * t / maxT; }
    function Y(v) { return T + (H - T - B) * (1 - Math.min(v, yMax) / yMax); }
    var s = sv("svg", { viewBox: "0 0 " + W + " " + H, role: "img",
      "aria-label": "Mean latency per minute for canary cells (orange) and baseline instances (blue) across the rollout" });
    [0, 50, 100, 150].forEach(function (v) {
      s.appendChild(sv("line", { x1: L, x2: W - R, y1: Y(v), y2: Y(v), "class": "line-thin" }));
      s.appendChild(sv("text", { x: L - 6, y: Y(v) + 4, "text-anchor": "end", "class": "t-xs t-faint" }, String(v)));
    });
    s.appendChild(sv("text", { x: 4, y: 11, "class": "t-xs t-muted" }, "ms"));
    S.marks.forEach(function (m) {
      s.appendChild(sv("line", { x1: X(m.t), x2: X(m.t), y1: T, y2: H - B, "class": m.kind === "halt" ? "line-dash s-red" : "line-dash" }));
      s.appendChild(sv("text", { x: X(m.t), y: H - B + 14, "text-anchor": "middle", "class": "t-xs " + (m.kind === "halt" ? "tc-red" : "t-faint") }, m.kind === "halt" ? "halt" : m.kind === "ignored" ? "ignored" : "pass"));
    });
    s.appendChild(sv("text", { x: (L + W - R) / 2, y: H - 4, "text-anchor": "middle", "class": "t-xs t-muted" }, "minutes since the rollout started"));
    function line(key, cls) {
      if (!S.series.length) return;
      s.appendChild(sv("polyline", { points: S.series.map(function (p) { return X(p.t).toFixed(1) + "," + Y(p[key]).toFixed(1); }).join(" "), fill: "none", "class": cls + " sw-2" }));
    }
    line("b", "s-blue"); line("c", "s-orange");
    s.appendChild(sv("text", { x: W - R, y: T + 10, "text-anchor": "end", "class": "t-xs tc-orange t-bold" }, "canary"));
    s.appendChild(sv("text", { x: W - R, y: T + 24, "text-anchor": "end", "class": "t-xs t-bold", style: "fill:var(--blue)" }, "baseline"));
    chart.textContent = ""; chart.appendChild(s);
  }

  function stopTimer() { if (S.timer) { clearInterval(S.timer); S.timer = null; } }
  function finishNow() { var guard = 0; while (!(S.done && S.tail >= TAIL) && guard++ < 1000) tick(); }
  runBtn.addEventListener("click", function () {
    if (S.timer) { stopTimer(); render(); return; }
    if (reduce) { finishNow(); render(); return; }
    S.timer = setInterval(function () {
      tick();
      if (S.done && S.tail >= TAIL) stopTimer();
      render();
    }, 90);
    render();
  });
  stepBtn.addEventListener("click", function () { stopTimer(); tick(); render(); });
  resetBtn.addEventListener("click", function () { stopTimer(); fresh(); render(); });
  [bugSel, bakeIn, haltCb].forEach(function (c) {
    c.addEventListener("change", function () { bakeOut.textContent = bake() + " min"; stopTimer(); fresh(); render(); });
  });
  bakeIn.addEventListener("input", function () { bakeOut.textContent = bake() + " min"; });
  render();
})();
