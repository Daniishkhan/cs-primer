/* Queue and thread-pool simulator (systems chapter 14).
   Requests arrive at random (Poisson arrivals: exponential gaps, seeded PRNG), wait in a queue
   of limited or unlimited size, and are served by W workers. Service times are exponential with
   the chosen mean (the classic M/M/c model). Everything is deterministic for a given seed. */
(function () {
  "use strict";

  /* ---------- core simulation (pure, no DOM) ---------- */
  function mulberry32(a) {
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      var t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  /* p: {lambda (req/s), workers, svcMs, bound (Infinity or integer >= 0), seed} */
  function Sim(p) {
    this.p = p;
    this.rng = mulberry32(p.seed || 12345);
    this.t = 0;
    this.meanSvc = p.svcMs / 1000;
    this.nextArr = this.expo(1 / p.lambda);
    this.fin = [];            /* finish time per worker, Infinity when idle */
    this.startedAt = [];      /* arrival time of the request each worker holds */
    for (var i = 0; i < p.workers; i++) { this.fin.push(Infinity); this.startedAt.push(0); }
    this.q = []; this.qh = 0; /* queue of arrival times; qh = head index */
    this.arrived = 0; this.admitted = 0; this.rejected = 0; this.completed = 0;
    this.sumSojourn = 0; this.soj = [];
    this.areaN = 0; this.areaBusy = 0; this.areaQ = 0;
    this.samples = [];        /* {t, q, lat} */
    this.nextSample = 0.5; this.winSum = 0; this.winCnt = 0; this.lastLat = 0;
  }
  Sim.prototype.expo = function (mean) { return -Math.log(1 - this.rng()) * mean; };
  Sim.prototype.qlen = function () { return this.q.length - this.qh; };
  Sim.prototype.busy = function () { var b = 0; for (var i = 0; i < this.fin.length; i++) if (this.fin[i] !== Infinity) b++; return b; };
  Sim.prototype.startOn = function (w, arrivalTime) {
    this.fin[w] = this.t + this.expo(this.meanSvc);
    this.startedAt[w] = arrivalTime;
  };
  Sim.prototype.accumulate = function (to) {
    var dt = to - this.t;
    if (dt <= 0) return;
    var b = this.busy(), ql = this.qlen();
    this.areaN += (b + ql) * dt; this.areaBusy += b * dt; this.areaQ += ql * dt;
    this.t = to;
  };
  Sim.prototype.sampleUpTo = function (to) {
    while (this.nextSample <= to) {
      /* queue length is constant between events, so sampling at event boundaries is exact */
      var lat = this.winCnt ? this.winSum / this.winCnt : this.lastLat;
      if (this.winCnt) this.lastLat = lat;
      this.samples.push({ t: this.nextSample, q: this.qlen(), lat: lat });
      this.winSum = 0; this.winCnt = 0;
      this.nextSample += 0.5;
    }
  };
  Sim.prototype.advance = function (to) {
    for (;;) {
      var wi = -1, ft = Infinity;
      for (var i = 0; i < this.fin.length; i++) if (this.fin[i] < ft) { ft = this.fin[i]; wi = i; }
      var ev = Math.min(this.nextArr, ft);
      if (ev > to) { this.sampleUpTo(to); this.accumulate(to); return; }
      this.sampleUpTo(ev);
      this.accumulate(ev);
      if (this.nextArr <= ft) {            /* arrival */
        this.arrived++;
        var idle = -1;
        for (var j = 0; j < this.fin.length; j++) if (this.fin[j] === Infinity) { idle = j; break; }
        if (idle !== -1) { this.admitted++; this.startOn(idle, this.t); }
        else if (this.qlen() < this.p.bound) { this.admitted++; this.q.push(this.t); }
        else this.rejected++;
        this.nextArr = this.t + this.expo(1 / this.p.lambda);
      } else {                             /* completion */
        var s = this.t - this.startedAt[wi];
        this.completed++; this.sumSojourn += s; this.soj.push(s);
        this.winSum += s; this.winCnt++;
        this.fin[wi] = Infinity;
        if (this.qlen() > 0) {
          var a = this.q[this.qh++];
          if (this.qh > 1024) { this.q = this.q.slice(this.qh); this.qh = 0; }
          this.startOn(wi, a);
        }
      }
    }
  };
  Sim.prototype.stats = function () {
    var t = this.t || 1e-9;
    var sorted = Float64Array.from(this.soj).sort();
    var p99 = sorted.length ? sorted[Math.min(sorted.length - 1, Math.floor(0.99 * sorted.length))] : 0;
    var W = this.completed ? this.sumSojourn / this.completed : 0;
    return {
      t: this.t, arrived: this.arrived, completed: this.completed, rejected: this.rejected,
      qlen: this.qlen(), busy: this.busy(),
      util: this.areaBusy / (t * this.p.workers),
      avgQ: this.areaQ / t,
      W: W, p99: p99,
      L: this.areaN / t,
      lambdaAdm: this.admitted / t,
      LW: (this.admitted / t) * W
    };
  };

  var core = { Sim: Sim, mulberry32: mulberry32 };
  if (typeof module !== "undefined" && module.exports) module.exports = core;

  /* ---------- UI ---------- */
  if (typeof document === "undefined") return;
  var root = document.getElementById("queue-sim");
  if (!root) return;

  var NS = "http://www.w3.org/2000/svg";
  var MAX_T = 300, WINDOW = 60, DT_STEP = 5;
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function $(sel) { return root.querySelector(sel); }
  var inLam = $("[data-in=lambda]"), inWrk = $("[data-in=workers]"), inSvc = $("[data-in=svc]"), inBnd = $("[data-in=bound]");
  var outLam = $("[data-out=lambda]"), outWrk = $("[data-out=workers]"), outSvc = $("[data-out=svc]"), outBnd = $("[data-out=bound]");
  var capEl = $(".qs-cap"), verdictEl = $(".qs-verdict");
  var playBtn = $("[data-act=play]"), stepBtn = $("[data-act=step]"), jumpBtn = $("[data-act=jump]"), resetBtn = $("[data-act=reset]");
  var chartBtns = root.querySelectorAll("[data-chart]");
  var svg = $(".qs-chart"), poolEl = $(".qs-pool"), qviz = $(".qs-queue");
  var statEls = {}; Array.prototype.forEach.call(root.querySelectorAll("[data-stat]"), function (e) { statEls[e.getAttribute("data-stat")] = e; });
  var littleEl = $(".qs-little");
  var clockEl = $(".qs-clock");

  var sim = null, running = false, raf = 0, lastTs = 0, chartMode = "q", lastStatTs = 0;
  var SPEED = 4; /* simulated seconds per real second */

  function readParams() {
    var b = parseInt(inBnd.value, 10);
    return { lambda: parseFloat(inLam.value), workers: parseInt(inWrk.value, 10), svcMs: parseFloat(inSvc.value),
      bound: b > parseInt(inBnd.max, 10) - 1 ? Infinity : b, seed: 12345 };
  }

  function describeParams() {
    var p = readParams();
    outLam.textContent = p.lambda + " req/s";
    outWrk.textContent = String(p.workers);
    outSvc.textContent = p.svcMs + " ms";
    outBnd.textContent = p.bound === Infinity ? "∞ (unbounded)" : String(p.bound);
    var cap = p.workers * 1000 / p.svcMs, rho = p.lambda / cap;
    capEl.textContent = "Capacity = " + p.workers + " × (1000 / " + p.svcMs + ") = " + cap.toFixed(1) + " req/s. Offered load ρ = " +
      p.lambda + " / " + cap.toFixed(1) + " = " + Math.round(rho * 100) + "%.";
    var v, cls;
    if (rho >= 1 && p.bound === Infinity) { v = "Overloaded with an unbounded queue: the queue (and the wait) grows for as long as this runs."; cls = "bad"; }
    else if (rho >= 1) { v = "Overloaded, but the bound caps the wait: the excess is rejected instead of queued."; cls = "warn"; }
    else if (rho >= 0.9) { v = "Under capacity on paper, but near the cliff: waits are long and bursts pile up."; cls = "warn"; }
    else { v = "Comfortable: queues stay short and most requests start at once."; cls = "ok"; }
    verdictEl.textContent = v;
    verdictEl.className = "qs-verdict " + cls;
  }

  function el(tag, attrs, text) {
    var e = document.createElementNS(NS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    return e;
  }

  function fmtMs(s) { return s < 1 ? Math.round(s * 1000) + " ms" : s.toFixed(2) + " s"; }

  function drawChart() {
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    var W = 420, H = 190, L = 44, R = 10, T = 12, B = 34, pw = W - L - R, ph = H - T - B;
    var t1 = Math.max(sim.t, WINDOW), t0 = t1 - WINDOW;
    var pts = sim.samples.filter(function (s) { return s.t >= t0; });
    var key = chartMode === "q" ? "q" : "lat";
    var maxV = chartMode === "q" ? 5 : 0.2;
    pts.forEach(function (s) { if (s[key] > maxV) maxV = s[key]; });
    maxV = chartMode === "q" ? Math.ceil(maxV * 1.1) : maxV * 1.1;
    svg.appendChild(el("line", { x1: L, y1: T + ph, x2: W - R, y2: T + ph, "class": "line-thin" }));
    svg.appendChild(el("line", { x1: L, y1: T, x2: L, y2: T + ph, "class": "line-thin" }));
    svg.appendChild(el("text", { x: L - 6, y: T + 10, "text-anchor": "end", "class": "t-xs t-faint" }, chartMode === "q" ? String(Math.round(maxV)) : fmtMs(maxV)));
    svg.appendChild(el("text", { x: L - 6, y: T + ph, "text-anchor": "end", "class": "t-xs t-faint" }, "0"));
    svg.appendChild(el("text", { x: L, y: T + ph + 16, "text-anchor": "start", "class": "t-xs t-faint" }, Math.round(t0) + " s"));
    svg.appendChild(el("text", { x: W - R, y: T + ph + 16, "text-anchor": "end", "class": "t-xs t-faint" }, Math.round(t1) + " s"));
    svg.appendChild(el("text", { x: L + pw / 2, y: H - 4, "text-anchor": "middle", "class": "t-xs t-muted" },
      chartMode === "q" ? "requests waiting in the queue, over time" : "average time in system of requests finishing in each 0.5 s"));
    if (pts.length > 1) {
      var d = pts.map(function (s) {
        return (L + (s.t - t0) / WINDOW * pw).toFixed(1) + "," + (T + ph - Math.min(1, s[key] / maxV) * ph).toFixed(1);
      }).join(" ");
      svg.appendChild(el("polyline", { points: d, fill: "none", "class": chartMode === "q" ? "s-blue" : "s-orange", "stroke-width": 2, "stroke-linejoin": "round" }));
    }
  }

  function drawPool() {
    var s = sim, p = s.p;
    poolEl.textContent = "";
    for (var i = 0; i < p.workers; i++) {
      var c = document.createElement("span");
      c.className = "qs-w" + (s.fin[i] !== Infinity ? " busy" : "");
      c.textContent = "W" + (i + 1);
      poolEl.appendChild(c);
    }
    qviz.textContent = "";
    var n = s.qlen(), show = Math.min(n, 36);
    for (var k = 0; k < show; k++) { var b = document.createElement("span"); b.className = "qs-item"; qviz.appendChild(b); }
    var lab = document.createElement("span");
    lab.className = "qs-qlabel";
    lab.textContent = n === 0 ? "queue empty" : (n > show ? "+" + (n - show) + " more (" + n + " waiting)" : n + " waiting");
    qviz.appendChild(lab);
  }

  function setStat(name, text) { if (statEls[name]) statEls[name].textContent = text; }

  function updateStats() {
    var st = sim.stats();
    clockEl.textContent = "t = " + st.t.toFixed(1) + " s";
    setStat("arrived", String(st.arrived));
    setStat("completed", String(st.completed));
    setStat("rejected", String(st.rejected));
    setStat("qlen", String(st.qlen));
    setStat("util", Math.round(st.util * 100) + "%");
    setStat("avg", st.completed ? fmtMs(st.W) : "n/a");
    setStat("p99", st.completed ? fmtMs(st.p99) : "n/a");
    setStat("L", st.L.toFixed(2));
    setStat("LW", st.completed ? st.LW.toFixed(2) : "n/a");
    setStat("lam", st.lambdaAdm.toFixed(1) + " /s");
    setStat("W", st.completed ? fmtMs(st.W) : "n/a");
    drawPool();
    drawChart();
  }

  function restart() {
    stop();
    describeParams();
    sim = new Sim(readParams());
    updateStats();
  }

  function stop() {
    running = false;
    if (raf) { cancelAnimationFrame(raf); raf = 0; }
    playBtn.textContent = "Run";
    playBtn.setAttribute("aria-pressed", "false");
  }

  function frame(ts) {
    if (!running) return;
    var dt = Math.min(0.1, (ts - lastTs) / 1000);
    lastTs = ts;
    sim.advance(Math.min(MAX_T, sim.t + dt * SPEED));
    if (ts - lastStatTs > 200) { updateStats(); lastStatTs = ts; }
    if (sim.t >= MAX_T) { stop(); updateStats(); clockEl.textContent += " (stopped at " + MAX_T + " s; Reset to start over)"; return; }
    raf = requestAnimationFrame(frame);
  }

  function play() {
    if (sim.t >= MAX_T) restart();
    running = true;
    playBtn.textContent = "Pause";
    playBtn.setAttribute("aria-pressed", "true");
    lastTs = performance.now(); lastStatTs = 0;
    raf = requestAnimationFrame(frame);
  }

  function advanceBy(dt) {
    stop();
    sim.advance(Math.min(MAX_T, sim.t + dt));
    updateStats();
  }

  var PRESETS = {
    comfortable: { lambda: 20, workers: 4, svc: 100, bound: 51 },
    near: { lambda: 38, workers: 4, svc: 100, bound: 51 },
    overload: { lambda: 50, workers: 4, svc: 100, bound: 51 },
    shed: { lambda: 50, workers: 4, svc: 100, bound: 10 }
  };

  function applyPreset(name) {
    var pr = PRESETS[name];
    inLam.value = pr.lambda; inWrk.value = pr.workers; inSvc.value = pr.svc; inBnd.value = pr.bound;
    restart();
    if (reduce) advanceBy(60); else play();
  }

  [inLam, inWrk, inSvc, inBnd].forEach(function (i) { i.addEventListener("input", restart); });
  Array.prototype.forEach.call(root.querySelectorAll("[data-preset]"), function (b) {
    b.addEventListener("click", function () { applyPreset(b.getAttribute("data-preset")); });
  });
  Array.prototype.forEach.call(chartBtns, function (b) {
    b.addEventListener("click", function () {
      chartMode = b.getAttribute("data-chart");
      Array.prototype.forEach.call(chartBtns, function (x) { x.setAttribute("aria-pressed", x === b ? "true" : "false"); });
      drawChart();
    });
  });
  playBtn.addEventListener("click", function () { if (running) stop(); else play(); });
  stepBtn.addEventListener("click", function () { advanceBy(DT_STEP); });
  jumpBtn.addEventListener("click", function () { advanceBy(60); });
  resetBtn.addEventListener("click", restart);

  if (reduce) {
    playBtn.disabled = true;
    playBtn.title = "Animation is off because your system asks for reduced motion. Use Step or Jump.";
  }

  restart();
})();
