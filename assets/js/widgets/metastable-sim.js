/* Metastable failure simulator (reliability chapter 11).
   Time advances in ticks of 0.1 s. Clients create new requests (Poisson, default 70/s). Each attempt
   must be answered within 1 s or the client gives up and, if retries remain, sends another attempt
   immediately. The server has one FIFO queue and serves 100 requests/s. A naive server cannot tell
   that a client has given up, so it still does the work: wasted effort, which is the sustaining effect.
   Trigger: for a few seconds capacity drops to 30/s. Protections (optional, from a chosen time):
   - retry budget: a retry needs a token, and each new request earns 0.1 token
   - deadline shedding: drop queued requests whose client is gone (free), and refuse new work
     when the queue already holds half a second of work (50). */
(function () {
  "use strict";

  var TICK = 0.1, CAP = 10, TIMEOUT = 1.0, HORIZON = 90;

  function mulberry32(a) {
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      var t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  function poisson(rng, mean) {
    var L = Math.exp(-mean), k = 0, p = 1;
    for (;;) { p *= rng(); if (p <= L) return k; k++; }
  }

  /* cfg: {base (req/s), retries, trigger (s), budget, shed, protectFrom (s)} -> per-second rows */
  function run(cfg, seed) {
    var rng = mulberry32(seed || 5);
    var queue = [], qh = 0, pending = [], ph = 0, tokens = 10;
    var rows = [], off = 0, good = 0, wasted = 0, shedN = 0;
    var trigStart = 20, trigEnd = 20 + cfg.trigger;
    var mean = cfg.base * TICK, steps = Math.round(HORIZON / TICK);
    for (var s = 0; s < steps; s++) {
      var t = s * TICK;
      var prot = t >= cfg.protectFrom, useB = cfg.budget && prot, useS = cfg.shed && prot;
      var nNew = poisson(rng, mean), sends = [], i;
      tokens = Math.min(10, tokens + 0.1 * nNew);
      for (i = 0; i < nNew; i++) sends.push({ sent: t, left: cfg.retries, done: false, gone: false });
      while (ph < pending.length && t - pending[ph].sent >= TIMEOUT - 1e-9) {
        var a = pending[ph++];
        if (a.done) continue;
        a.gone = true;
        if (a.left > 0 && (!useB || tokens >= 1)) {
          if (useB) tokens -= 1;
          sends.push({ sent: t, left: a.left - 1, done: false, gone: false });
        }
      }
      for (i = 0; i < sends.length; i++) {
        var b = sends[i];
        off++;
        if (useS && queue.length - qh >= 5 * CAP) { b.gone = true; shedN++; continue; }
        queue.push(b); pending.push(b);
      }
      var cap = (t >= trigStart && t < trigEnd) ? 3 : CAP;
      while (cap > 0 && qh < queue.length) {
        var r = queue[qh++];
        if (r.gone && useS) { shedN++; continue; }
        cap--;
        if (r.gone || t - r.sent >= TIMEOUT) wasted++;
        else { r.done = true; good++; }
      }
      if ((s + 1) % 10 === 0) {
        rows.push({ t: (s + 1) * TICK, offered: off, good: good, wasted: wasted, queue: queue.length - qh });
        off = 0; good = 0; wasted = 0;
      }
    }
    return rows;
  }
  var core = { run: run };
  if (typeof module !== "undefined" && module.exports) module.exports = core;

  if (typeof document === "undefined") return;
  var root = document.getElementById("metastable-sim");
  if (!root) return;

  var NS = "http://www.w3.org/2000/svg";
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

  var state = { base: 70, retries: 3, trigger: 6, budget: false, shed: false, protectFrom: 0 };
  var PRESETS = [
    { label: "Naive: retries, no protection", s: { retries: 3, budget: false, shed: false, protectFrom: 0 } },
    { label: "Protected from the start", s: { retries: 3, budget: true, shed: true, protectFrom: 0 } },
    { label: "Naive, fixed at t = 50 s", s: { retries: 3, budget: true, shed: true, protectFrom: 50 } },
    { label: "No retries at all", s: { retries: 0, budget: false, shed: false, protectFrom: 0 } }
  ];

  var head = el("div", { "class": "widget-head" });
  head.appendChild(el("span", { "class": "widget-tag" }, "Try it"));
  head.appendChild(el("h4", { "class": "widget-title" }, "Push a service into a metastable failure"));
  root.appendChild(head);
  root.appendChild(el("p", { "class": "widget-help" },
    "Capacity is 100 requests/s and clients time out after 1 s. A short capacity dip starts at t = 20 s. Choose the retry policy and the protections, and see whether the service comes back once the dip is over."));

  var presets = el("div", { "class": "op-presets", role: "group", "aria-label": "Presets" });
  var pbtns = PRESETS.map(function (p) {
    var b = el("button", { type: "button", "class": "btn small", "aria-pressed": "false" }, p.label);
    b.addEventListener("click", function () {
      for (var k in p.s) state[k] = p.s[k];
      sync(); update();
    });
    presets.appendChild(b);
    return b;
  });
  root.appendChild(presets);

  var ctl = el("div", { "class": "op-ctl" });
  var ins = {};
  function slider(key, label, min, max, step, fmt) {
    var w = el("div");
    var lab = el("label", { "for": "ms-" + key }, label + ": ");
    var out = el("output", { "for": "ms-" + key });
    lab.appendChild(out);
    var inp = el("input", { type: "range", id: "ms-" + key, min: String(min), max: String(max), step: String(step), value: String(state[key]) });
    inp.addEventListener("input", function () { state[key] = parseFloat(inp.value); update(); });
    w.appendChild(lab); w.appendChild(inp); ctl.appendChild(w);
    ins[key] = { inp: inp, out: out, fmt: fmt };
  }
  function check(key, label) {
    var w = el("div");
    var l = el("label", { "class": "op-check", "for": "ms-" + key });
    var c = el("input", { type: "checkbox", id: "ms-" + key });
    c.addEventListener("change", function () { state[key] = c.checked; update(); });
    l.appendChild(c); l.appendChild(el("span", {}, label)); w.appendChild(l); ctl.appendChild(w);
    ins[key] = { inp: c, check: true };
  }
  slider("base", "New requests per second", 40, 95, 5, function (v) { return v + "/s"; });
  slider("retries", "Retries per request", 0, 5, 1, function (v) { return String(v); });
  slider("trigger", "Length of the capacity dip", 0, 20, 1, function (v) { return v + " s"; });
  slider("protectFrom", "Protections switch on at", 0, 80, 10, function (v) { return v === 0 ? "the start" : "t = " + v + " s"; });
  check("budget", "Retry budget (10% of new requests)");
  check("shed", "Deadline shedding and queue bound");
  root.appendChild(ctl);

  var tiles = el("div", { "class": "op-tiles", "aria-live": "polite" });
  root.appendChild(tiles);
  var status = el("p", { "class": "op-status", "aria-live": "polite" });
  root.appendChild(status);
  var chart = el("div", { "class": "op-chart" });
  root.appendChild(chart);

  function sync() {
    for (var k in ins) {
      if (ins[k].check) ins[k].inp.checked = !!state[k];
      else ins[k].inp.value = String(state[k]);
    }
  }
  function tile(label, value, cls) {
    var d = el("div", { "class": "op-tile " + (cls || "") });
    d.appendChild(el("small", {}, label)); d.appendChild(el("b", {}, value));
    return d;
  }

  function update() {
    for (var k in ins) if (!ins[k].check) ins[k].out.textContent = ins[k].fmt(state[k]);
    pbtns.forEach(function (b, i) {
      var s = PRESETS[i].s, on = true;
      for (var key in s) if (state[key] !== s[key]) on = false;
      b.setAttribute("aria-pressed", String(on));
    });
    ins.protectFrom.inp.disabled = !(state.budget || state.shed);
    var rows = run(state);
    var last = rows.slice(-10), avg = 0, avgOff = 0, wastedSum = 0, peakQ = 0;
    last.forEach(function (r) { avg += r.good / last.length; avgOff += r.offered / last.length; });
    rows.forEach(function (r) { wastedSum += r.wasted; if (r.queue > peakQ) peakQ = r.queue; });
    var ok = avg >= 0.9 * state.base;
    tiles.textContent = "";
    tiles.appendChild(tile("Goodput, last 10 s", avg.toFixed(0) + " /s", ok ? "good" : "bad"));
    tiles.appendChild(tile("Offered, last 10 s", avgOff.toFixed(0) + " /s"));
    tiles.appendChild(tile("Peak queue", String(peakQ), peakQ > 100 ? "bad" : "good"));
    tiles.appendChild(tile("Wasted work", wastedSum + " requests", wastedSum > 1000 ? "bad" : ""));
    status.textContent = ok
      ? "Recovered. The dip ended and goodput returned to the offered rate" + (state.budget || state.shed ? ", helped by the protections." : ".")
      : (state.trigger === 0 ? "No dip, but the system is overloaded anyway."
        : "Metastable. The dip ended at t = " + (20 + state.trigger) + " s, capacity is back to 100/s, yet goodput is " + avg.toFixed(0) + "/s because the retries and the dead requests in the queue sustain the overload.");
    draw(rows);
  }

  function draw(rows) {
    chart.textContent = "";
    var W = 700, H = 420, L = 56, R = 16;
    var svg = sv("svg", { viewBox: "0 0 " + W + " " + H, role: "img", "aria-label": "Offered load and goodput over 90 seconds, and queue length over the same time" });
    var pw = W - L - R;
    function X(t) { return L + pw * t / HORIZON; }
    var maxOff = 0, maxQ = 1;
    rows.forEach(function (r) { if (r.offered > maxOff) maxOff = r.offered; if (r.queue > maxQ) maxQ = r.queue; });
    var yMax1 = Math.max(120, Math.ceil(maxOff / 50) * 50);
    var T1 = 12, B1 = 190, T2 = 236, B2 = 366;
    function Y1(v) { return B1 - (B1 - T1) * v / yMax1; }
    var qTop = Math.max(100, Math.ceil(maxQ / 100) * 100);
    function Y2(v) { return B2 - (B2 - T2) * v / qTop; }
    var tStart = 20, tEnd = 20 + state.trigger;
    if (state.trigger > 0) {
      svg.appendChild(sv("rect", { x: X(tStart), y: T1, width: X(tEnd) - X(tStart), height: B2 - T1, "class": "fs-purple", opacity: "0.45" }));
      svg.appendChild(sv("text", { x: X(tStart) + 3, y: T1 + 12, "class": "t-xs t-bold tc-purple" }, "capacity dip"));
    }
    if ((state.budget || state.shed) && state.protectFrom > 0) {
      svg.appendChild(sv("line", { x1: X(state.protectFrom), y1: T1, x2: X(state.protectFrom), y2: B2, "class": "line-dash s-green" }));
      svg.appendChild(sv("text", { x: X(state.protectFrom) + 4, y: T1 + 12, "class": "t-xs t-bold tc-green" }, "protections on"));
    }
    var yt = [0, Math.round(yMax1 / 2), yMax1];
    yt.forEach(function (v) {
      svg.appendChild(sv("line", { x1: L, y1: Y1(v), x2: W - R, y2: Y1(v), "class": "line-thin" }));
      svg.appendChild(sv("text", { x: L - 8, y: Y1(v) + 4, "text-anchor": "end", "class": "t-xs t-muted" }, String(v)));
    });
    [0, qTop / 2, qTop].forEach(function (v) {
      svg.appendChild(sv("line", { x1: L, y1: Y2(v), x2: W - R, y2: Y2(v), "class": "line-thin" }));
      svg.appendChild(sv("text", { x: L - 8, y: Y2(v) + 4, "text-anchor": "end", "class": "t-xs t-muted" }, String(v)));
    });
    svg.appendChild(sv("line", { x1: L, y1: B1, x2: W - R, y2: B1, "class": "line" }));
    svg.appendChild(sv("line", { x1: L, y1: B2, x2: W - R, y2: B2, "class": "line" }));
    svg.appendChild(sv("line", { x1: L, y1: T1, x2: L, y2: B1, "class": "line" }));
    svg.appendChild(sv("line", { x1: L, y1: T2, x2: L, y2: B2, "class": "line" }));
    [0, 10, 20, 30, 40, 50, 60, 70, 80, 90].forEach(function (t) {
      svg.appendChild(sv("text", { x: X(t), y: B2 + 16, "text-anchor": "middle", "class": "t-xs t-muted" }, String(t)));
    });
    svg.appendChild(sv("text", { x: L + pw / 2, y: H - 20, "text-anchor": "middle", "class": "t-sm t-muted" }, "time (s)"));
    svg.appendChild(sv("text", { x: 14, y: (T1 + B1) / 2, "text-anchor": "middle", "class": "t-sm t-muted", transform: "rotate(-90 14 " + (T1 + B1) / 2 + ")" }, "requests per second"));
    svg.appendChild(sv("text", { x: 14, y: (T2 + B2) / 2, "text-anchor": "middle", "class": "t-sm t-muted", transform: "rotate(-90 14 " + (T2 + B2) / 2 + ")" }, "queue length"));
    function line(fn, y, cls) {
      var d = "";
      rows.forEach(function (r, i) { d += (i ? "L" : "M") + X(r.t).toFixed(1) + "," + y(fn(r)).toFixed(1); });
      svg.appendChild(sv("path", { d: d, fill: "none", "class": cls }));
    }
    line(function (r) { return r.offered; }, Y1, "line s-orange sw-2");
    line(function (r) { return r.good; }, Y1, "line s-green sw-3");
    line(function (r) { return r.queue; }, Y2, "line s-blue sw-3");
    svg.appendChild(sv("text", { x: W - R - 4, y: Y1(yMax1) + 12, "text-anchor": "end", "class": "t-xs tc-orange" }, "orange: offered (new + retries)"));
    svg.appendChild(sv("text", { x: W - R - 4, y: Y1(yMax1) + 26, "text-anchor": "end", "class": "t-xs tc-green" }, "green: goodput"));
    svg.appendChild(sv("text", { x: W - R - 4, y: T2 + 12, "text-anchor": "end", "class": "t-xs tc-blue" }, "queue (requests waiting)"));
    chart.appendChild(svg);
  }

  sync();
  update();
})();
