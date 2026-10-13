/* "The cost of a hop" (architecture chapter 11).

   The reader builds a request path of N remote calls (1-10) and sets, for every
   hop, an availability and a latency distribution (median and p99).

   Modes
     serial    the request calls hop 1, then hop 2, ... and needs every one of them.
               Availability is the product of the hop availabilities; latency is the
               SUM of the hop latencies.
     parallel  the request calls N services at the same moment and waits for all of
               them. Availability is still the product; latency is the MAX of the
               N latencies, which is where the tail (networking chapter 13) bites.

   Model (stated in the widget as well)
     - Each hop's latency is log-normal, fitted so that exp(mu) = median and the
       99th percentile equals the p99 you typed: sigma = ln(p99 / median) / 2.3263.
     - Hops are independent: no shared load, no retries, no timeouts, no queueing.
     - The latency statistics are over requests in which every hop answered.
     - The in-process comparison uses an assumed 0.001 ms per module call and treats
       the whole monolith as ONE process, so it has one availability figure (hop 1's)
       and no partial failure.

   Deterministic: a seeded mulberry32 PRNG draws the same TRIALS x 10 random numbers
   for a given seed, and every setting is applied to those same numbers (common
   random numbers), so moving a slider changes the answer smoothly. No timers, no
   libraries, no storage. */
(function () {
  "use strict";
  var root = document.getElementById("call-chain");
  if (!root) return;

  var MAXN = 10, TRIALS = 20000, Z99 = 2.3263478740408408, MODULE_CALL_MS = 0.001;
  var AVAIL = [99, 99.5, 99.9, 99.95, 99.99];
  var S = {
    mode: "serial", n: 4, seed: 42,
    hops: []
  };
  for (var i = 0; i < MAXN; i++) S.hops.push({ avail: 99.9, median: 20, p99: 100 });

  /* ---------- seeded random numbers ---------- */
  function mulberry32(a) {
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      var t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  var Z = null, U = null, zSeed = null;
  function draw() {
    if (zSeed === S.seed) return;
    var rnd = mulberry32(S.seed >>> 0);
    Z = new Float32Array(TRIALS * MAXN); U = new Float32Array(TRIALS * MAXN);
    for (var k = 0; k < Z.length; k++) {
      var u1 = rnd() || 1e-12, u2 = rnd();
      Z[k] = Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);
      U[k] = rnd();
    }
    zSeed = S.seed;
  }

  /* ---------- the model ---------- */
  function num(v, lo, hi, dflt) {
    v = parseFloat(v); if (!isFinite(v)) v = dflt;
    return Math.min(hi, Math.max(lo, v));
  }
  function params(h) {
    var med = num(h.median, 0.1, 100000, 20), p99 = num(h.p99, 0.1, 100000, 100);
    if (p99 < med) p99 = med;
    return { mu: Math.log(med), sigma: Math.max(Math.log(p99 / med) / Z99, 1e-6) };
  }
  function pct(arr, p) {
    var c = Float64Array.from(arr).sort();
    return c[Math.floor(p * (c.length - 1))];
  }

  /* Latency arrays for depths 1..n. Returns [{p50,p99,avail}] per depth. */
  function sweep(mode, n) {
    var acc = new Float64Array(TRIALS), out = [], avail = 1, naive = 0;
    for (var d = 0; d < n; d++) {
      var h = S.hops[d], p = params(h);
      avail *= num(h.avail, 0, 100, 99.9) / 100;
      naive += Math.exp(p.mu + p.sigma * Z99);
      for (var t = 0; t < TRIALS; t++) {
        var l = Math.exp(p.mu + p.sigma * Z[t * MAXN + d]);
        if (mode === "serial") acc[t] += l; else if (l > acc[t]) acc[t] = l;
      }
      out.push({ depth: d + 1, p50: pct(acc, 0.5), p99: pct(acc, 0.99), avail: avail, naiveSum: naive });
    }
    return out;
  }
  function simulatedAvailability(n) {
    var ok = 0;
    for (var t = 0; t < TRIALS; t++) {
      var good = true;
      for (var d = 0; d < n && good; d++) {
        if (U[t * MAXN + d] >= num(S.hops[d].avail, 0, 100, 99.9) / 100) good = false;
      }
      if (good) ok++;
    }
    return ok / TRIALS;
  }

  /* ---------- formatting ---------- */
  function ms(v) { return v < 1 ? v.toFixed(3) + " ms" : v < 100 ? v.toFixed(1) + " ms" : Math.round(v) + " ms"; }
  function percent(a) {
    var p = a * 100;
    return (p >= 99.995 ? p.toFixed(4) : p.toFixed(3)) + "%";
  }
  function downtime(a) {
    var m = (1 - a) * 30 * 24 * 60;
    if (m < 1) return (m * 60).toFixed(0) + " seconds";
    if (m < 120) return m.toFixed(0) + " minutes";
    return (m / 60).toFixed(1) + " hours";
  }

  /* ---------- DOM helpers ---------- */
  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function btn(label, cls, fn) { var b = el("button", "btn " + (cls || ""), label); b.type = "button"; b.addEventListener("click", fn); return b; }
  var nId = 0;
  function labelled(text, control) {
    var id = "cc-f" + (++nId); control.id = id;
    var l = el("label", "cc-lab", text); l.htmlFor = id;
    var w = el("div", "cc-field"); w.appendChild(l); w.appendChild(control); return w;
  }

  var ui = {};
  function build() {
    root.textContent = "";
    var head = el("div", "widget-head");
    head.appendChild(el("span", "widget-tag", "Simulator"));
    head.appendChild(el("span", "widget-title", "The cost of a hop"));
    root.appendChild(head);
    root.appendChild(el("p", "widget-help", "Build a request path out of remote calls. Give each hop an availability and a latency (median and 99th percentile). The widget multiplies the availabilities and runs 20,000 simulated requests with a fixed random seed to find the end-to-end latency."));

    /* mode */
    root.appendChild(el("p", "cc-label", "1. Shape of the path"));
    var mrow = el("div", "cc-btns"); mrow.setAttribute("role", "group"); mrow.setAttribute("aria-label", "Shape of the request path");
    [["serial", "Serial chain: A calls B calls C ..."], ["parallel", "Parallel fan-out: call all N, wait for all"]].forEach(function (m) {
      var b = btn(m[1], "", function () { S.mode = m[0]; syncMode(); update(); });
      b.dataset.mode = m[0]; mrow.appendChild(b); ui["mode_" + m[0]] = b;
    });
    root.appendChild(mrow);
    ui.modeNote = el("p", "cc-desc"); root.appendChild(ui.modeNote);

    /* N */
    root.appendChild(el("p", "cc-label", "2. How many calls"));
    var r = el("input"); r.type = "range"; r.min = 1; r.max = MAXN; r.step = 1; r.value = S.n;
    var rw = labelled("Number of remote calls", r);
    ui.nOut = el("output", "pill", String(S.n)); rw.appendChild(ui.nOut);
    r.addEventListener("input", function () { S.n = parseInt(r.value, 10); ui.nOut.textContent = String(S.n); rows(); update(); });
    ui.range = r; root.appendChild(rw);

    /* per-hop settings */
    root.appendChild(el("p", "cc-label", "3. Each service"));
    var tools = el("div", "cc-btns");
    tools.appendChild(btn("Copy hop 1 to all hops", "small", function () {
      for (var i = 1; i < MAXN; i++) S.hops[i] = { avail: S.hops[0].avail, median: S.hops[0].median, p99: S.hops[0].p99 };
      rows(); update();
    }));
    tools.appendChild(btn("Reset", "small", function () {
      for (var i = 0; i < MAXN; i++) S.hops[i] = { avail: 99.9, median: 20, p99: 100 };
      S.n = 4; S.seed = 42; ui.range.value = 4; ui.nOut.textContent = "4"; ui.seed.value = "42"; rows(); update();
    }));
    root.appendChild(tools);
    ui.rows = el("div", "cc-rows"); root.appendChild(ui.rows);
    var sd = el("input"); sd.type = "number"; sd.min = 1; sd.max = 99999; sd.step = 1; sd.value = S.seed; sd.className = "mono";
    sd.addEventListener("input", function () { S.seed = Math.floor(num(sd.value, 1, 99999, 42)); update(); });
    ui.seed = sd;
    var sw = labelled("Random seed (same seed, same answer)", sd); sw.classList.add("cc-seed"); root.appendChild(sw);

    /* results */
    root.appendChild(el("p", "cc-label", "4. What the caller experiences"));
    ui.summary = el("div", "widget-out cc-summary"); ui.summary.setAttribute("aria-live", "polite"); root.appendChild(ui.summary);
    ui.stats = el("div", "cc-stats"); root.appendChild(ui.stats);
    root.appendChild(el("p", "cc-label", "5. How p99 grows as the path gets longer"));
    ui.bars = el("div", "cc-bars"); root.appendChild(ui.bars);
    ui.note = el("p", "cc-note"); root.appendChild(ui.note);
    syncMode(); rows();
  }

  function syncMode() {
    ["serial", "parallel"].forEach(function (m) { ui["mode_" + m].setAttribute("aria-pressed", String(S.mode === m)); });
    ui.modeNote.textContent = S.mode === "serial"
      ? "Each call waits for the previous one. Latencies add up and every hop must be up."
      : "All calls start together and the request waits for the slowest one. Every call must still be up, and the slowest of N draws sets the pace.";
  }

  function rows() {
    ui.rows.textContent = "";
    var hd = el("div", "cc-row cc-rowhead");
    ["", "Availability", "Median ms", "p99 ms"].forEach(function (t) { hd.appendChild(el("span", null, t)); });
    ui.rows.appendChild(hd);
    for (var i = 0; i < S.n; i++) (function (i) {
      var h = S.hops[i], row = el("div", "cc-row");
      row.appendChild(el("span", "cc-hopname", S.mode === "serial" ? "Hop " + (i + 1) : "Call " + (i + 1)));
      var sel = el("select");
      sel.setAttribute("aria-label", "Availability of hop " + (i + 1));
      AVAIL.forEach(function (a) { var o = el("option", null, a + "%"); o.value = String(a); if (a === h.avail) o.selected = true; sel.appendChild(o); });
      sel.addEventListener("change", function () { h.avail = parseFloat(sel.value); update(); });
      var med = el("input"); med.type = "number"; med.min = 0.1; med.step = "any"; med.value = h.median; med.className = "mono";
      med.setAttribute("aria-label", "Median latency of hop " + (i + 1) + " in milliseconds");
      med.addEventListener("input", function () { h.median = med.value; update(); });
      var p99 = el("input"); p99.type = "number"; p99.min = 0.1; p99.step = "any"; p99.value = h.p99; p99.className = "mono";
      p99.setAttribute("aria-label", "99th percentile latency of hop " + (i + 1) + " in milliseconds");
      p99.addEventListener("input", function () { h.p99 = p99.value; update(); });
      row.appendChild(sel); row.appendChild(med); row.appendChild(p99);
      ui.rows.appendChild(row);
    })(i);
  }

  function stat(label, value, sub, cls) {
    var c = el("div", "cc-stat" + (cls ? " " + cls : ""));
    c.appendChild(el("div", "cc-stat-l", label));
    c.appendChild(el("div", "cc-stat-v", value));
    if (sub) c.appendChild(el("div", "cc-stat-s", sub));
    return c;
  }

  function update() {
    draw();
    var n = S.n, sw = sweep(S.mode, n), last = sw[n - 1], one = sweep(S.mode, 1)[0];
    var simA = simulatedAvailability(n);
    var h0 = num(S.hops[0].avail, 0, 100, 99.9) / 100;
    var inproc = n * MODULE_CALL_MS;

    ui.summary.textContent = "";
    var strong = el("strong", null, n + (n === 1 ? " remote call" : (S.mode === "serial" ? " chained remote calls" : " parallel remote calls")));
    ui.summary.appendChild(strong);
    ui.summary.appendChild(document.createTextNode(": the request succeeds " + percent(last.avail) + " of the time (about " + downtime(last.avail) +
      " of failed requests per 30 days of continuous traffic) and half of requests finish within " + ms(last.p50) + ", but one in a hundred takes " + ms(last.p99) + " or longer."));

    ui.stats.textContent = "";
    var worseA = last.avail < 0.9995, tailX = last.p99 / one.p99;
    ui.stats.appendChild(stat("Combined availability", percent(last.avail), "product of " + n + " hop value" + (n === 1 ? "" : "s") + "; simulated " + percent(simA), worseA ? "bad" : ""));
    ui.stats.appendChild(stat("End-to-end p50", ms(last.p50), "typical request"));
    ui.stats.appendChild(stat("End-to-end p99", ms(last.p99), tailX.toFixed(1) + "x hop 1's p99 alone (" + ms(one.p99) + ")", tailX > 1.5 ? "bad" : ""));
    ui.stats.appendChild(stat(S.mode === "serial" ? "Sum of the hops' p99s" : "Slowest single p99", ms(S.mode === "serial" ? last.naiveSum : maxP99(n)),
      S.mode === "serial" ? "the naive guess; real p99 is lower, because hops are rarely all slow at once" : "the fan-out p99 is higher than this, because the max of N draws exceeds any one hop's p99 more often"));
    ui.stats.appendChild(stat("Same logic, in one process", ms(inproc), n + " module call" + (n === 1 ? "" : "s") + " at about 1 microsecond; availability " + percent(h0) + " (one process, hop 1's figure), with no partial failure", "good"));
    ui.stats.appendChild(stat("Requests with at least one slow call", ((1 - Math.pow(0.99, n)) * 100).toFixed(1) + "%", "chance that some hop exceeds its own p99: 1 - 0.99^" + n));

    ui.bars.textContent = "";
    var maxv = 0; sw.forEach(function (d) { if (d.p99 > maxv) maxv = d.p99; });
    sw.forEach(function (d) {
      var line = el("div", "cc-bar");
      line.appendChild(el("span", "cc-bar-l", d.depth + (S.mode === "serial" ? (d.depth === 1 ? " hop" : " hops") : (d.depth === 1 ? " call" : " parallel"))));
      var track = el("span", "cc-bar-t"); var fill = el("span", "cc-bar-f"); fill.style.width = Math.max(1, d.p99 / maxv * 100).toFixed(1) + "%";
      track.appendChild(fill); line.appendChild(track);
      line.appendChild(el("span", "cc-bar-v", ms(d.p99) + " / " + percent(d.avail)));
      ui.bars.appendChild(line);
    });
    ui.note.textContent = "Bars show p99 latency and combined availability for the first 1, 2, ... " + n + " calls. Remember what this model leaves out: no retries, no timeouts, no queueing, no correlated failures. Real systems usually behave worse, because load, retries and shared dependencies make failures travel together.";
  }
  function maxP99(n) {
    var m = 0; for (var i = 0; i < n; i++) { var p = params(S.hops[i]); m = Math.max(m, Math.exp(p.mu + p.sigma * Z99)); }
    return m;
  }

  build(); update();
})();
