/* Resilience simulator (architecture chapter 17).

   A client service handles 40 user requests per second that each need one call to
   a dependency, plus 10 requests per second of unrelated work (say, a profile page)
   that needs no dependency but does need a thread. The client has a pool of 40
   threads. The reader controls the dependency's health:
     healthy  - answers in about 50 ms
     slow     - answers in about 2.5 s (a latency spike)
     failing  - answers in about 50 ms but 60% of calls return an error
   and can switch on, independently:
     timeout          - give up on a call after 250 / 500 / 1000 ms (otherwise: 30 s)
     retries          - up to 3 attempts, backoff 200 ms then 400 ms, optional full jitter;
                        a thread stays held while the request sleeps between attempts
     circuit breaker  - closed -> open -> half-open; opens when at least half of the last
                        20 results (minimum 10) failed; stays open 3 s, then lets ONE probe
                        through; optional "serve cached fallback" while open
     bulkhead         - at most N calls to the dependency in progress at once; extra calls
                        are rejected immediately instead of waiting

   Time advances in 100 ms ticks. Random numbers come from a seeded generator
   (mulberry32), so the same toggles and the same clicks on the same ticks give the same
   picture; the "replay" buttons run a scripted outage so you can compare settings fairly.

   Dependency model (a deliberate simplification): its latency is multiplied by a load
   factor = max(1, calls in flight / 30, calls in the last second / 60), capped at 8.
   A call the client has abandoned (timed out) still occupies the dependency until it
   finishes. In failing mode the error chance rises with the load factor, and in healthy
   or slow mode a heavily overloaded dependency also starts to fail. This is what makes
   retries hurt: they raise the load that is already causing the failures.

   Not modelled: queues inside the dependency, connection setup costs, different
   request sizes, partial responses. Numbers are illustrative, not predictions. */
(function () {
  "use strict";
  var root = document.getElementById("breaker-sim");
  if (!root) return;

  var DT = 100, THREADS = 40, ARRIVE = 4, OTHER = 1;
  var CAP_INFL = 30, CAP_RATE = 60, LF_MAX = 8;
  var FAST_MS = 50, SLOW_MS = 2500, NO_TIMEOUT = 30000;
  var MAX_ATT = 3, BACKOFF = 200;
  var BR_WIN = 20, BR_MIN = 10, BR_RATE = 0.5, BR_OPEN = 3000;
  var KEEP = 600, PTS = 300;
  var WARM = 100;

  var reduced = false;
  try { reduced = !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches); } catch (e) { reduced = false; }

  var cfg = { timeout: false, timeoutMs: 500, retries: false, jitter: false, breaker: false, fallback: false, bulkhead: false, maxConc: 10 };
  var S = null;
  var timer = null;
  var speed = 4;

  function mulberry32(a) {
    return function () {
      a |= 0; a = a + 0x6D2B79F5 | 0;
      var t = Math.imul(a ^ a >>> 15, 1 | a);
      t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
      return ((t ^ t >>> 14) >>> 0) / 4294967296;
    };
  }

  function fresh() {
    return { rand: mulberry32(20240607), tick: 0, now: 0, mode: "healthy", reqs: [], active: 0, bulk: 0,
      depFin: [], depSend: [], others: [], ticks: [], rec: null,
      brk: { state: "closed", win: [], openUntil: 0, probe: false },
      script: null, scriptDone: false, msg: "", opened: 0 };
  }

  function say(text) { S.msg = text; }
  function secs(ms) { return (ms / 1000).toFixed(1) + " s"; }

  /* ---------- circuit breaker ---------- */
  function brkOpen(t) {
    var b = S.brk;
    b.state = "open"; b.openUntil = t + BR_OPEN; b.win = []; b.probe = false; S.opened++;
    say("Breaker OPEN at " + secs(t) + ": calls now fail fast and the dependency gets a rest.");
  }
  function brkAllow(r, t) {
    if (!cfg.breaker) return true;
    var b = S.brk;
    if (b.state === "open" && t >= b.openUntil) { b.state = "half-open"; b.probe = false; say("Breaker HALF-OPEN at " + secs(t) + ": letting one probe call through."); }
    if (b.state === "open") return false;
    if (b.state === "half-open") { if (b.probe) return false; b.probe = true; r.probe = true; }
    return true;
  }
  function brkRecord(r, failed, t) {
    if (!cfg.breaker) return;
    var b = S.brk;
    if (r.probe) {
      r.probe = false; b.probe = false;
      if (failed) { brkOpen(t); } else { b.state = "closed"; b.win = []; say("Breaker CLOSED at " + secs(t) + ": the probe succeeded."); }
      return;
    }
    if (b.state !== "closed") return;
    b.win.push(failed ? 1 : 0);
    if (b.win.length > BR_WIN) b.win.shift();
    if (b.win.length >= BR_MIN) {
      var f = 0; for (var i = 0; i < b.win.length; i++) f += b.win[i];
      if (f / b.win.length >= BR_RATE) brkOpen(t);
    }
  }

  /* ---------- the dependency ---------- */
  function depLoad(t) {
    var infl = 0, i;
    for (i = 0; i < S.depFin.length; i++) if (S.depFin[i] > t) infl++;
    var rate = 0;
    for (i = 0; i < S.depSend.length; i++) if (S.depSend[i] > t - 1000) rate++;
    return Math.min(LF_MAX, Math.max(1, infl / CAP_INFL, rate / CAP_RATE));
  }

  /* ---------- requests ---------- */
  function finish(r, outcome, t) {
    r.done = true; S.active--;
    var rec = S.rec;
    if (outcome === "ok") rec.ok++; else if (outcome === "deg") rec.deg++; else rec.fail++;
    rec.latSum += t - r.start; rec.latN++;
  }

  function startAttempt(r, t) {
    r.phase = "none";
    if (!brkAllow(r, t)) { finish(r, cfg.fallback ? "deg" : "fail", t); return; }
    if (cfg.bulkhead && S.bulk >= cfg.maxConc) {
      if (r.probe) { r.probe = false; S.brk.probe = false; }
      finish(r, "fail", t); return;
    }
    S.bulk++;
    var lf = depLoad(t), base, errP, rnd = S.rand;
    if (S.mode === "slow") { base = SLOW_MS * (0.8 + 0.4 * rnd()); errP = Math.max(0, 0.4 * (lf - 1)); }
    else if (S.mode === "failing") { base = FAST_MS * (0.7 + 0.6 * rnd()); errP = Math.min(1, 0.6 + 0.4 * (lf - 1)); }
    else { base = FAST_MS * (0.7 + 0.6 * rnd()); errP = Math.max(0, 0.4 * (lf - 1)); }
    var lat = base * lf;
    var limit = cfg.timeout ? cfg.timeoutMs : NO_TIMEOUT;
    S.depSend.push(t); S.depFin.push(t + lat); S.rec.calls++;
    r.phase = "call";
    if (lat > limit) { r.end = t + limit; r.res = "timeout"; }
    else { r.end = t + lat; r.res = rnd() < errP ? "err" : "ok"; }
  }

  function attemptEnd(r) {
    var t = r.end;
    S.bulk--;
    var failed = r.res !== "ok";
    brkRecord(r, failed, t);
    if (!failed) { finish(r, "ok", t); return; }
    if (cfg.retries && r.att < MAX_ATT) {
      var d = BACKOFF * Math.pow(2, r.att - 1);
      if (cfg.jitter) d = d * S.rand();
      r.att++; r.phase = "wait"; r.wake = t + d;
      return;
    }
    finish(r, "fail", t);
  }

  function advance(r, now) {
    var guard = 0;
    while (!r.done && guard++ < 10) {
      if (r.phase === "call" && r.end <= now) attemptEnd(r);
      else if (r.phase === "wait" && r.wake <= now) startAttempt(r, r.wake);
      else break;
    }
  }

  /* ---------- one tick ---------- */
  function step() {
    var now = S.tick * DT, i;
    S.now = now;
    var rec = { ok: 0, deg: 0, fail: 0, noThread: 0, latSum: 0, latN: 0, calls: 0, firsts: 0, oOk: 0, oN: 0, mode: S.mode, brk: S.brk.state, inUse: 0, infl: 0 };
    S.rec = rec;

    if (S.script) {
      while (S.script.length && S.script[0].t <= now) {
        var ev = S.script.shift();
        if (ev.mode) { S.mode = ev.mode; say("Dependency is now " + ev.mode.toUpperCase() + " (scripted, at " + secs(now) + ")."); }
        if (ev.stop) { S.scriptDone = true; }
      }
      rec.mode = S.mode;
    }

    S.depFin = S.depFin.filter(function (x) { return x > now; });
    S.depSend = S.depSend.filter(function (x) { return x > now - 1000; });
    S.others = S.others.filter(function (x) { return x > now; });

    for (i = 0; i < S.reqs.length; i++) advance(S.reqs[i], now);
    S.reqs = S.reqs.filter(function (r) { return !r.done; });

    function threads() { return S.active + S.others.length; }
    var k;
    for (k = 0; k < ARRIVE; k++) {
      if (threads() >= THREADS) { rec.fail++; rec.noThread++; continue; }
      var r = { start: now, att: 1, phase: "none", done: false, probe: false };
      S.active++; rec.firsts++;
      S.reqs.push(r);
      startAttempt(r, now);
    }
    S.reqs = S.reqs.filter(function (r) { return !r.done; });
    for (k = 0; k < OTHER; k++) {
      rec.oN++;
      if (threads() >= THREADS) continue;
      rec.oOk++; S.others.push(now + 50);
    }

    rec.inUse = threads();
    var infl = 0; for (i = 0; i < S.depFin.length; i++) if (S.depFin[i] > now) infl++;
    rec.infl = infl;
    rec.brk = S.brk.state;
    S.ticks.push(rec);
    if (S.ticks.length > KEEP) S.ticks.shift();
    S.tick++;
  }

  /* ---------- derived numbers ---------- */
  function window10() {
    var a = S.ticks.slice(-10 * 1), ok = 0, deg = 0, fail = 0, latSum = 0, latN = 0, calls = 0, firsts = 0, oOk = 0, oN = 0, i;
    var t10 = S.ticks.slice(-100);
    for (i = 0; i < t10.length; i++) {
      var x = t10[i];
      ok += x.ok; deg += x.deg; fail += x.fail; latSum += x.latSum; latN += x.latN;
      calls += x.calls; firsts += x.firsts; oOk += x.oOk; oN += x.oN;
    }
    var lastSec = 0, lastInfl = 0;
    for (i = 0; i < a.length; i++) lastSec += a[i].calls;
    var last = S.ticks[S.ticks.length - 1];
    if (last) lastInfl = last.infl;
    var done = ok + deg + fail;
    return { ok: ok, deg: deg, fail: fail, done: done, success: done ? 100 * (ok + deg) / done : null,
      lat: latN ? latSum / latN : null, calls: calls, firsts: firsts, amp: firsts ? calls / firsts : null,
      oRate: oN ? 100 * oOk / oN : null, perSec: lastSec, infl: lastInfl,
      threads: last ? last.inUse : 0 };
  }

  /* ---------- DOM helpers ---------- */
  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function svgEl(tag, attrs) {
    var e = document.createElementNS("http://www.w3.org/2000/svg", tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    return e;
  }
  function btn(label, cls, fn) { var b = el("button", "btn " + (cls || ""), label); b.type = "button"; b.addEventListener("click", fn); return b; }
  function check(id, label, onchange) {
    var wrap = el("label", "bs-check");
    var inp = el("input"); inp.type = "checkbox"; inp.id = "bs-" + id;
    inp.addEventListener("change", function () { onchange(inp.checked); });
    wrap.appendChild(inp); wrap.appendChild(el("span", null, label));
    return { wrap: wrap, input: inp };
  }
  function select(id, label, opts, val, onchange) {
    var wrap = el("label", "bs-sel");
    wrap.appendChild(el("span", null, label));
    var s = el("select"); s.id = "bs-" + id;
    opts.forEach(function (o) {
      var op = el("option", null, o.label); op.value = String(o.value);
      if (o.value === val) op.selected = true;
      s.appendChild(op);
    });
    s.addEventListener("change", function () { onchange(+s.value); });
    wrap.appendChild(s);
    return { wrap: wrap, input: s };
  }

  /* ---------- build UI ---------- */
  root.textContent = "";
  var head = el("div", "widget-head");
  head.appendChild(el("span", "widget-tag", "Simulator"));
  head.appendChild(el("h4", "widget-title", "Protect a client from a bad dependency"));
  root.appendChild(head);

  var help = el("p", "widget-help");
  help.textContent = "A client sends 40 requests per second, each needing one call to a dependency, and also serves 10 per second of unrelated work from the same pool of 40 threads. Choose the dependency's health, switch protections on and off, and press Run. Good first experiment: pick the preset Timeout + retries, press Run, then press Slow and watch the bottom-right chart (calls reaching the dependency). Then try Everything on. Random draws are seeded; exact numbers also depend on which tick you click.";
  root.appendChild(help);

  /* dependency health */
  root.appendChild(el("div", "bs-label", "1. Dependency health"));
  var healthRow = el("div", "bs-btns");
  var healthBtns = {};
  [["healthy", "Healthy"], ["slow", "Slow (latency spike)"], ["failing", "Failing (errors)"]].forEach(function (m) {
    var b = btn(m[1], "", function () { setMode(m[0]); });
    b.setAttribute("aria-pressed", "false");
    healthBtns[m[0]] = b; healthRow.appendChild(b);
  });
  root.appendChild(healthRow);

  /* protections */
  root.appendChild(el("div", "bs-label", "2. Protections"));
  var prot = el("div", "bs-prot");
  var cTimeout = check("timeout", "Timeout", function (v) { cfg.timeout = v; sync(); });
  var sTimeout = select("timeout-ms", "after", [{ value: 250, label: "250 ms" }, { value: 500, label: "500 ms" }, { value: 1000, label: "1000 ms" }], 500, function (v) { cfg.timeoutMs = v; });
  var cRetries = check("retries", "Retries (3 attempts, backoff 200 ms, 400 ms)", function (v) { cfg.retries = v; sync(); });
  var cJitter = check("jitter", "with full jitter", function (v) { cfg.jitter = v; });
  var cBreaker = check("breaker", "Circuit breaker", function (v) {
    cfg.breaker = v; if (S) { S.brk.state = "closed"; S.brk.win = []; S.brk.probe = false; } sync();
  });
  var cFallback = check("fallback", "serve a cached fallback while open", function (v) { cfg.fallback = v; });
  var cBulk = check("bulkhead", "Bulkhead", function (v) { cfg.bulkhead = v; sync(); });
  var sBulk = select("bulk-max", "max concurrent calls", [{ value: 5, label: "5" }, { value: 10, label: "10" }, { value: 20, label: "20" }], 10, function (v) { cfg.maxConc = v; });
  [[cTimeout, sTimeout], [cRetries, cJitter], [cBreaker, cFallback], [cBulk, sBulk]].forEach(function (pair) {
    var g = el("div", "bs-group");
    g.appendChild(pair[0].wrap);
    var sub = el("div", "bs-sub"); sub.appendChild(pair[1].wrap); g.appendChild(sub);
    prot.appendChild(g);
  });
  root.appendChild(prot);

  /* presets */
  root.appendChild(el("div", "bs-label", "Presets (each also resets the run)"));
  var presetRow = el("div", "bs-btns");
  function preset(label, c) {
    presetRow.appendChild(btn(label, "small", function () {
      cfg.timeout = !!c.timeout; cfg.retries = !!c.retries; cfg.jitter = !!c.jitter; cfg.breaker = !!c.breaker; cfg.fallback = !!c.fallback; cfg.bulkhead = !!c.bulkhead;
      if (c.timeoutMs) cfg.timeoutMs = c.timeoutMs;
      sync(); reset(true); render();
    }));
  }
  preset("No protection", {});
  preset("Retries only", { retries: true });
  preset("Timeout + retries", { timeout: true, retries: true });
  preset("Timeout + jittered retries + breaker", { timeout: true, retries: true, jitter: true, breaker: true, fallback: true });
  preset("Everything on", { timeout: true, retries: true, jitter: true, breaker: true, fallback: true, bulkhead: true });
  root.appendChild(presetRow);

  /* run controls */
  root.appendChild(el("div", "bs-label", "3. Run"));
  var runRow = el("div", "bs-btns");
  var bRun = btn("Run", "primary", toggleRun);
  var bStep = btn("Step 1 s", "", function () { pause(); advanceTicks(10); render(); });
  var bReset = btn("Reset", "", function () { pause(); reset(true); render(); });
  var bSlow = btn("Replay: slow outage", "", function () { replay("slow"); });
  var bFail = btn("Replay: error outage", "", function () { replay("failing"); });
  var sSpeed = select("speed", "speed", [{ value: 1, label: "1x" }, { value: 4, label: "4x" }, { value: 10, label: "10x" }], 4, function (v) { speed = v; if (timer) { pause(); start(); } });
  [bRun, bStep, bReset, bSlow, bFail].forEach(function (b) { runRow.appendChild(b); });
  runRow.appendChild(sSpeed.wrap);
  root.appendChild(runRow);

  /* status */
  var statusLine = el("div", "bs-status");
  statusLine.setAttribute("role", "status");
  root.appendChild(statusLine);

  /* tiles */
  var tileGrid = el("div", "bs-tiles");
  var tiles = {};
  [["time", "Sim time"], ["brk", "Breaker"], ["succ", "Success rate (10 s)"], ["lat", "Mean latency (10 s)"],
   ["thr", "Threads in use"], ["calls", "Calls to dependency /s"], ["amp", "Dependency calls per request (10 s)"],
   ["infl", "In flight at dependency"], ["oth", "Unrelated endpoint OK (10 s)"]].forEach(function (d) {
    var t = el("div", "bs-tile");
    t.appendChild(el("div", "bs-tile-k", d[1]));
    var v = el("div", "bs-tile-v", "-");
    t.appendChild(v);
    tileGrid.appendChild(t); tiles[d[0]] = { box: t, v: v };
  });
  root.appendChild(tileGrid);

  /* charts */
  var chartGrid = el("div", "bs-charts");
  function chart(title, key, color, label) {
    var c = el("div", "bs-chart");
    var h = el("div", "bs-chart-h");
    h.appendChild(el("span", "bs-chart-t", title));
    var val = el("span", "bs-chart-v", "");
    h.appendChild(val);
    c.appendChild(h);
    var svg = svgEl("svg", { viewBox: "0 0 300 100", preserveAspectRatio: "none", role: "img", "aria-label": label });
    c.appendChild(svg);
    chartGrid.appendChild(c);
    return { svg: svg, val: val, key: key, color: color };
  }
  var charts = [
    chart("Client success rate", "succ", "green", "Line chart of the client success rate over the last 60 seconds. The same numbers appear in the tiles above."),
    chart("Mean latency", "lat", "blue", "Line chart of mean latency over the last 60 seconds."),
    chart("Threads in use (limit 40)", "thr", "purple", "Line chart of client threads in use over the last 60 seconds, with a dashed line at the limit of 40."),
    chart("Calls reaching the dependency /s", "calls", "orange", "Line chart of calls per second reaching the dependency over the last 60 seconds. Dashed lines mark the normal rate of 40 and the dependency's comfortable capacity of 60.")
  ];
  root.appendChild(chartGrid);
  root.appendChild(el("p", "bs-legend", "Each chart shows the last 60 seconds, one point per 0.2 s, each averaging the previous second. Top band: dependency health (green healthy, orange slow, red failing). Second band, if the breaker is on: breaker state (green closed, orange half-open, red open)."));

  /* ---------- rendering ---------- */
  function sync() {
    cTimeout.input.checked = cfg.timeout; sTimeout.input.disabled = !cfg.timeout; sTimeout.input.value = String(cfg.timeoutMs);
    cRetries.input.checked = cfg.retries; cJitter.input.disabled = !cfg.retries; cJitter.input.checked = cfg.jitter;
    cBreaker.input.checked = cfg.breaker; cFallback.input.disabled = !cfg.breaker; cFallback.input.checked = cfg.fallback;
    cBulk.input.checked = cfg.bulkhead; sBulk.input.disabled = !cfg.bulkhead; sBulk.input.value = String(cfg.maxConc);
    if (S) render();
  }

  function bandPath(svg, samples, y, h, colorOf) {
    var i = 0;
    while (i < samples.length) {
      var c = colorOf(samples[i]), j = i;
      while (j + 1 < samples.length && colorOf(samples[j + 1]) === c) j++;
      var rect = svgEl("rect", { x: i, y: y, width: j - i + 1, height: h, "class": "bs-band bs-b-" + c });
      svg.appendChild(rect);
      i = j + 1;
    }
  }

  function seriesFor(key) {
    var out = [], n = S.ticks.length, k;
    for (k = PTS - 1; k >= 0; k--) {
      var j = n - 1 - 2 * k;
      if (j < 0) { out.push({ v: null, mode: "none", brk: "none" }); continue; }
      var lo = Math.max(0, j - 9), ok = 0, deg = 0, fail = 0, latSum = 0, latN = 0, calls = 0, inUse = 0, i;
      for (i = lo; i <= j; i++) {
        var x = S.ticks[i];
        ok += x.ok; deg += x.deg; fail += x.fail; latSum += x.latSum; latN += x.latN; calls += x.calls;
        if (x.inUse > inUse) inUse = x.inUse;
      }
      var v = null, d = ok + deg + fail;
      if (key === "succ") v = d ? 100 * (ok + deg) / d : null;
      else if (key === "lat") v = latN ? latSum / latN : null;
      else if (key === "thr") v = inUse;
      else v = calls * 10 / (j - lo + 1);
      out.push({ v: v, mode: S.ticks[j].mode, brk: S.ticks[j].brk });
    }
    return out;
  }

  function drawChart(c) {
    var svg = c.svg;
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    var data = seriesFor(c.key), i, max = 100, fmt;
    var vals = data.map(function (d) { return d.v; }).filter(function (v) { return v != null; });
    var peak = vals.length ? Math.max.apply(null, vals) : 0;
    if (c.key === "succ") { max = 100; fmt = function (v) { return Math.round(v) + "%"; }; }
    else if (c.key === "lat") { max = Math.max(600, Math.ceil(peak / 500) * 500); fmt = function (v) { return v >= 1000 ? (v / 1000).toFixed(1) + " s" : Math.round(v) + " ms"; }; }
    else if (c.key === "thr") { max = 44; fmt = function (v) { return Math.round(v) + " / " + THREADS; }; }
    else { max = Math.max(120, Math.ceil(peak / 60) * 60); fmt = function (v) { return Math.round(v) + "/s"; }; }

    var top = 14, plotH = 100 - top - 2;
    function Y(v) { return top + plotH - plotH * Math.min(v, max) / max; }
    var g;
    for (g = 0; g <= 2; g++) {
      var gy = top + plotH * g / 2;
      svg.appendChild(svgEl("line", { x1: 0, x2: 300, y1: gy, y2: gy, "class": "bs-grid", "vector-effect": "non-scaling-stroke" }));
    }
    bandPath(svg, data, 0, 5, function (d) { return d.mode; });
    if (cfg.breaker) bandPath(svg, data, 6, 5, function (d) { return d.brk === "open" ? "failing" : d.brk === "half-open" ? "slow" : d.brk === "closed" ? "healthy" : "none"; });
    function ref(v, cls) {
      if (v > max) return;
      svg.appendChild(svgEl("line", { x1: 0, x2: 300, y1: Y(v), y2: Y(v), "class": "bs-ref " + cls, "vector-effect": "non-scaling-stroke" }));
    }
    if (c.key === "thr") ref(THREADS, "bs-ref-red");
    if (c.key === "calls") { ref(ARRIVE * 10, "bs-ref-grey"); ref(CAP_RATE, "bs-ref-red"); }
    var d = "", pen = false;
    for (i = 0; i < data.length; i++) {
      if (data[i].v == null) { pen = false; continue; }
      d += (pen ? "L" : "M") + i + " " + Y(data[i].v).toFixed(1) + " ";
      pen = true;
    }
    svg.appendChild(svgEl("path", { d: d || "M0 0", "class": "bs-line bs-line-" + c.color, "vector-effect": "non-scaling-stroke" }));
    var last = data[data.length - 1];
    c.val.textContent = (last && last.v != null ? fmt(last.v) : "-") + "  (axis 0 to " + (c.key === "succ" ? "100%" : c.key === "lat" ? fmt(max) : c.key === "thr" ? THREADS : max + "/s") + ")";
  }

  function setTile(t, text, cls) { t.v.textContent = text; t.box.className = "bs-tile" + (cls ? " " + cls : ""); }

  function render() {
    var w = window10(), b = S.brk;
    var i;
    for (var m in healthBtns) healthBtns[m].setAttribute("aria-pressed", String(S.mode === m));
    setTile(tiles.time, secs(S.tick * DT));
    setTile(tiles.brk, cfg.breaker ? b.state : "off", cfg.breaker ? (b.state === "open" ? "bad" : b.state === "half-open" ? "warn" : "good") : "");
    setTile(tiles.succ, w.success == null ? "-" : w.success.toFixed(0) + "%" + (w.deg ? " (" + (100 * w.deg / w.done).toFixed(0) + "% cached)" : ""), w.success == null ? "" : w.success < 60 ? "bad" : w.success < 95 ? "warn" : "good");
    setTile(tiles.lat, w.lat == null ? "-" : (w.lat >= 1000 ? (w.lat / 1000).toFixed(1) + " s" : Math.round(w.lat) + " ms"), w.lat != null && w.lat > 1000 ? "bad" : "");
    setTile(tiles.thr, w.threads + " / " + THREADS, w.threads >= THREADS ? "bad" : w.threads > 28 ? "warn" : "");
    setTile(tiles.calls, String(w.perSec), w.perSec > CAP_RATE ? "bad" : "");
    setTile(tiles.amp, w.amp == null ? "-" : w.amp.toFixed(2) + "x", w.amp != null && w.amp > 1.5 ? "bad" : "");
    setTile(tiles.infl, String(w.infl), w.infl > CAP_INFL ? "bad" : "");
    setTile(tiles.oth, w.oRate == null ? "-" : w.oRate.toFixed(0) + "%", w.oRate == null ? "" : w.oRate < 80 ? "bad" : w.oRate < 99 ? "warn" : "good");
    for (i = 0; i < charts.length; i++) drawChart(charts[i]);
    statusLine.textContent = S.msg || "Paused. Choose a health state and protections, then press Run.";
    bRun.textContent = timer ? "Pause" : "Run";
  }

  /* ---------- control ---------- */
  function advanceTicks(n) {
    for (var i = 0; i < n; i++) {
      step();
      if (S.scriptDone) { pause(); say("Scripted run finished at " + secs(S.tick * DT) + ". Change a setting and replay to compare."); S.scriptDone = false; S.script = null; break; }
    }
  }
  function pause() { if (timer) { clearInterval(timer); timer = null; } }
  function start() {
    pause();
    var perStep = reduced ? speed * 10 : speed, every = reduced ? 1000 : DT;
    timer = setInterval(function () { advanceTicks(perStep); render(); }, every);
  }
  function toggleRun() {
    if (timer) { pause(); say("Paused at " + secs(S.tick * DT) + "."); } else { start(); if (!S.msg) say("Running."); }
    render();
  }
  function setMode(m) {
    S.mode = m;
    say("Dependency set to " + m.toUpperCase() + " at " + secs(S.tick * DT) + ".");
    render();
  }
  function reset(warm) {
    var mode = "healthy";
    S = fresh();
    S.mode = mode;
    if (warm) { for (var i = 0; i < WARM; i++) step(); S.ticks = S.ticks.slice(-KEEP); }
    S.msg = "";
    S.opened = 0;
  }
  function replay(kind) {
    pause();
    reset(false);
    S.script = [{ t: 10000, mode: kind }, { t: 40000, mode: "healthy" }, { t: 70000, stop: true }];
    say("Replaying: healthy for 10 s, " + (kind === "slow" ? "slow" : "failing") + " from 10 s to 40 s, healthy again, stop at 70 s.");
    start();
    render();
  }

  reset(true);
  sync();
  render();
})();
