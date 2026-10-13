/* Deadlock lab (systems chapter 13).
   2 or 3 threads, each with a planned order of lock acquisitions. The reader steps one
   thread at a time (or takes random steps). A wait-for graph is drawn live:
     lock -> thread  = "holds"      (solid)
     thread -> lock  = "waits for"  (dashed)
   A cycle of waits is drawn in red: that is a deadlock.
   "Enforce global lock order" rewrites each plan so locks are taken in A, B, C order. */
(function () {
  "use strict";

  /* ---------- core model (pure, no DOM) ---------- */
  var LOCK_NAMES = ["A", "B", "C"];

  function mulberry32(a) {
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      var t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  function makePlans(n, ordered) {
    var base = n === 2 ? [[0, 1], [1, 0]] : [[0, 1], [1, 2], [2, 0]];
    if (!ordered) return base;
    return base.map(function (p) { return p.slice().sort(function (x, y) { return x - y; }); });
  }

  function newState(plans) {
    var holder = [];
    for (var i = 0; i < plans.length; i++) holder.push(-1);
    var pc = plans.map(function () { return 0; });
    return { plans: plans, pc: pc, holder: holder };
  }

  function isDone(s, i) { return s.pc[i] > s.plans[i].length; }

  /* the lock thread i is waiting for right now, or -1 */
  function waitingFor(s, i) {
    if (isDone(s, i)) return -1;
    var k = s.pc[i];
    if (k >= s.plans[i].length) return -1;
    var l = s.plans[i][k];
    return (s.holder[l] !== -1 && s.holder[l] !== i) ? l : -1;
  }

  function canMove(s, i) { return !isDone(s, i) && waitingFor(s, i) === -1; }

  /* perform one action for thread i; returns a description or null if it cannot move */
  function step(s, i) {
    if (!canMove(s, i)) return null;
    var k = s.pc[i], plan = s.plans[i];
    if (k < plan.length) {
      s.holder[plan[k]] = i; s.pc[i] = k + 1;
      return "T" + (i + 1) + " acquired " + LOCK_NAMES[plan[k]];
    }
    var rel = [];
    for (var l = 0; l < s.holder.length; l++) if (s.holder[l] === i) { s.holder[l] = -1; rel.push(LOCK_NAMES[l]); }
    s.pc[i] = plan.length + 1;
    return "T" + (i + 1) + " did its work and released " + rel.join(" and ");
  }

  function allDone(s) {
    for (var i = 0; i < s.plans.length; i++) if (!isDone(s, i)) return false;
    return true;
  }

  function anyMovable(s) {
    for (var i = 0; i < s.plans.length; i++) if (canMove(s, i)) return true;
    return false;
  }

  /* threads on a wait-for cycle (each thread waits for at most one lock, so follow the chain) */
  function findCycle(s) {
    var n = s.plans.length;
    for (var start = 0; start < n; start++) {
      var seen = {}, cur = start, path = [];
      while (cur !== -1 && !seen[cur]) {
        seen[cur] = true; path.push(cur);
        var l = waitingFor(s, cur);
        cur = l === -1 ? -1 : s.holder[l];
      }
      if (cur !== -1) {
        var idx = path.indexOf(cur);
        return path.slice(idx);
      }
    }
    return [];
  }

  function randomMovable(s, rng) {
    var m = [];
    for (var i = 0; i < s.plans.length; i++) if (canMove(s, i)) m.push(i);
    return m.length ? m[Math.floor(rng() * m.length)] : -1;
  }

  /* run many full random schedules; count how many end in deadlock */
  function trials(n, ordered, count, seed) {
    var rng = mulberry32(seed), dead = 0;
    for (var t = 0; t < count; t++) {
      var s = newState(makePlans(n, ordered));
      for (;;) {
        var i = randomMovable(s, rng);
        if (i === -1) break;
        step(s, i);
      }
      if (!allDone(s)) dead++;
    }
    return dead;
  }

  var core = { makePlans: makePlans, newState: newState, step: step, canMove: canMove, waitingFor: waitingFor,
    findCycle: findCycle, allDone: allDone, anyMovable: anyMovable, trials: trials, mulberry32: mulberry32 };
  if (typeof module !== "undefined" && module.exports) module.exports = core;

  /* ---------- UI ---------- */
  if (typeof document === "undefined") return;
  var root = document.getElementById("deadlock-lab");
  if (!root) return;

  var NS = "http://www.w3.org/2000/svg";
  var TCOL = ["blue", "green", "pink"];
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  var cfgSel = root.querySelector("[data-act=config]");
  var orderChk = root.querySelector("[data-act=order]");
  var threadsBox = root.querySelector(".dl-threads");
  var svg = root.querySelector(".dl-graph");
  var statusEl = root.querySelector(".dl-status");
  var logEl = root.querySelector(".dl-log");
  var randBtn = root.querySelector("[data-act=random]");
  var autoBtn = root.querySelector("[data-act=auto]");
  var resetBtn = root.querySelector("[data-act=reset]");
  var trialBtn = root.querySelector("[data-act=trials]");
  var trialOut = root.querySelector(".dl-trials");
  var graphWrap = root.querySelector(".dl-graph-wrap");

  var n = 2, ordered = false, state, log = [], rng = mulberry32(2024), timer = null, trialSeed = 1;
  var cards = [];

  if (reduce) {
    autoBtn.disabled = true;
    autoBtn.title = "Auto-play is off because your system asks for reduced motion. Use Random step.";
  }

  function el(tag, attrs, text) {
    var e = document.createElementNS(NS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    return e;
  }

  function buildCards() {
    threadsBox.textContent = "";
    cards = [];
    for (var i = 0; i < n; i++) {
      (function (i) {
        var card = document.createElement("div");
        card.className = "dl-card dl-t" + i;
        var h = document.createElement("div");
        h.className = "dl-card-head";
        var name = document.createElement("strong");
        name.textContent = "Thread T" + (i + 1);
        var st = document.createElement("span");
        st.className = "pill";
        h.appendChild(name); h.appendChild(st);
        var ol = document.createElement("ol");
        ol.className = "dl-plan";
        var b = document.createElement("button");
        b.type = "button"; b.className = "btn small";
        b.addEventListener("click", function () { doStep(i); });
        card.appendChild(h); card.appendChild(ol); card.appendChild(b);
        threadsBox.appendChild(card);
        cards.push({ card: card, pill: st, ol: ol, btn: b });
      })(i);
    }
  }

  function reset() {
    stopAuto();
    state = newState(makePlans(n, ordered));
    log = [];
    render();
    statusEl.textContent = "Ready. Step a thread, or take random steps.";
  }

  function stopAuto() {
    if (timer) { clearInterval(timer); timer = null; }
    autoBtn.textContent = "Auto-play";
    autoBtn.setAttribute("aria-pressed", "false");
  }

  function summary() {
    var cyc = findCycle(state);
    if (cyc.length) {
      var names = cyc.map(function (t) { return "T" + (t + 1); }).join(", ");
      var others = !anyMovable(state) ? "" : " Other threads can still run, but " + names + " are stuck for good.";
      return { cls: "dead", text: "DEADLOCK: " + names + " wait for each other in a cycle. Nobody can ever release a lock." + others };
    }
    if (allDone(state)) return { cls: "ok", text: "Finished: every thread completed and every lock is free." };
    return { cls: "", text: "No deadlock yet." };
  }

  function render() {
    for (var i = 0; i < n; i++) {
      var c = cards[i], plan = state.plans[i], pcv = state.pc[i], w = waitingFor(state, i);
      c.ol.textContent = "";
      var items = plan.map(function (l) { return "acquire " + LOCK_NAMES[l]; });
      items.push("work, then release all");
      items.forEach(function (txt, k) {
        var li = document.createElement("li");
        var mark = k < pcv ? "✓ " : (k === pcv ? "▶ " : "· ");
        li.textContent = mark + txt;
        if (k < pcv) li.className = "dl-done";
        else if (k === pcv) li.className = w !== -1 ? "dl-now dl-wait" : "dl-now";
        c.ol.appendChild(li);
      });
      var done = isDone(state, i);
      if (done) { c.pill.textContent = "done"; c.pill.className = "pill green"; }
      else if (w !== -1) { c.pill.textContent = "blocked on " + LOCK_NAMES[w]; c.pill.className = "pill red"; }
      else { c.pill.textContent = "ready"; c.pill.className = "pill blue"; }
      c.btn.textContent = "Step T" + (i + 1);
      c.btn.disabled = done;
    }
    drawGraph();
    var sm = summary();
    graphWrap.className = "dl-graph-wrap" + (sm.cls ? " " + sm.cls : "");
    if (sm.cls) statusEl.textContent = sm.text;
    if (sm.cls === "dead" && !anyMovable(state)) stopAuto();
    if (sm.cls === "ok") stopAuto();
    var finished = (sm.cls === "ok") || (!anyMovable(state) && !allDone(state));
    randBtn.disabled = finished;
    autoBtn.disabled = finished || reduce;
    renderLog();
  }

  function renderLog() {
    logEl.textContent = "";
    log.slice(-5).forEach(function (t) {
      var li = document.createElement("li");
      li.textContent = t;
      logEl.appendChild(li);
    });
  }

  /* geometry of the little graph: viewBox 360 x 250 */
  function pos(kind, i) {
    var xs = n === 2 ? [100, 260] : [60, 180, 300];
    return kind === "t" ? { x: xs[i], y: 52 } : { x: xs[i], y: 190 };
  }
  var TR = 22, LW = 26, LH = 20; /* thread radius; lock half-width / half-height */

  function trim(a, b, aKind, bKind) {
    /* shorten a->b so it starts at a's outline and ends at b's outline */
    var dx = b.x - a.x, dy = b.y - a.y, len = Math.sqrt(dx * dx + dy * dy);
    function edge(kind, ux, uy) {
      if (kind === "t") return TR + 3;
      var tx = Math.abs(ux) > 1e-6 ? (LW + 3) / Math.abs(ux) : 1e9;
      var ty = Math.abs(uy) > 1e-6 ? (LH + 3) / Math.abs(uy) : 1e9;
      return Math.min(tx, ty);
    }
    var ux = dx / len, uy = dy / len;
    var s0 = edge(aKind, ux, uy), s1 = edge(bKind, ux, uy);
    return { x1: a.x + ux * s0, y1: a.y + uy * s0, x2: b.x - ux * s1, y2: b.y - uy * s1 };
  }

  function drawGraph() {
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    var defs = el("defs", {});
    function marker(id, cls) {
      var m = el("marker", { id: id, viewBox: "0 0 10 10", refX: 9, refY: 5, markerWidth: 7, markerHeight: 7, orient: "auto-start-reverse" });
      m.appendChild(el("path", { d: "M0,0 L10,5 L0,10 z", "class": cls }));
      defs.appendChild(m);
    }
    marker("ahS13g", "arrowhead"); marker("ahS13r", "f-red");
    svg.appendChild(defs);

    var cyc = findCycle(state);
    var inCyc = {};
    cyc.forEach(function (t) { inCyc[t] = true; });

    /* edges first (so nodes paint over them) */
    for (var l = 0; l < n; l++) {
      var h = state.holder[l];
      if (h !== -1) {
        var g = trim(pos("l", l), pos("t", h), "l", "t");
        var red = !!inCyc[h] && cyc.some(function (t) { var w = waitingFor(state, t); return w === l; });
        svg.appendChild(el("line", { x1: g.x1, y1: g.y1, x2: g.x2, y2: g.y2,
          "class": "line " + (red ? "s-red" : "s-" + TCOL[h]), "stroke-width": 3, "marker-end": "url(#" + (red ? "ahS13r" : "ahS13g") + ")" }));
      }
    }
    for (var t = 0; t < n; t++) {
      var w = waitingFor(state, t);
      if (w !== -1) {
        var g2 = trim(pos("t", t), pos("l", w), "t", "l");
        var red2 = !!inCyc[t];
        svg.appendChild(el("line", { x1: g2.x1, y1: g2.y1, x2: g2.x2, y2: g2.y2,
          "class": "line-dash " + (red2 ? "s-red" : "s-" + TCOL[t]), "stroke-width": red2 ? 3 : 2, "marker-end": "url(#" + (red2 ? "ahS13r" : "ahS13g") + ")" }));
      }
    }
    /* threads */
    for (var i = 0; i < n; i++) {
      var p = pos("t", i);
      var stat = isDone(state, i) ? "done" : (waitingFor(state, i) !== -1 ? "blocked" : "ready");
      svg.appendChild(el("text", { x: p.x, y: 17, "text-anchor": "middle", "class": "t-xs " + (stat === "blocked" ? "tc-red" : "t-muted") }, stat));
      svg.appendChild(el("circle", { cx: p.x, cy: p.y, r: TR, "class": "fs-" + TCOL[i] + (inCyc[i] ? " s-red" : " s-" + TCOL[i]), "stroke-width": inCyc[i] ? 4 : 2 }));
      svg.appendChild(el("text", { x: p.x, y: p.y + 5, "text-anchor": "middle", "class": "t-bold" }, "T" + (i + 1)));
    }
    /* locks */
    for (var k = 0; k < n; k++) {
      var q = pos("l", k);
      svg.appendChild(el("rect", { x: q.x - LW, y: q.y - LH, width: LW * 2, height: LH * 2, rx: 6, "class": "fs-orange s-orange", "stroke-width": 2 }));
      svg.appendChild(el("text", { x: q.x, y: q.y + 5, "text-anchor": "middle", "class": "t-bold" }, "Lock " + LOCK_NAMES[k]));
      var hh = state.holder[k];
      svg.appendChild(el("text", { x: q.x, y: q.y + LH + 17, "text-anchor": "middle", "class": "t-xs " + (hh === -1 ? "t-faint" : "t-muted") }, hh === -1 ? "free" : "held by T" + (hh + 1)));
    }
  }

  function doStep(i) {
    var before = state.pc[i];
    var d = step(state, i);
    if (d === null) {
      var w = waitingFor(state, i);
      if (w !== -1) statusEl.textContent = "T" + (i + 1) + " is blocked: it wants lock " + LOCK_NAMES[w] + ", held by T" + (state.holder[w] + 1) + ". Step another thread.";
      return false;
    }
    log.push(d);
    render();
    if (!summary().cls) statusEl.textContent = d + ".";
    return before !== state.pc[i];
  }

  function randomStep() {
    var i = randomMovable(state, rng);
    if (i === -1) { render(); return false; }
    doStep(i);
    return true;
  }

  cfgSel.addEventListener("change", function () { n = parseInt(cfgSel.value, 10); buildCards(); reset(); });
  orderChk.addEventListener("change", function () {
    ordered = orderChk.checked; reset();
    var changed = makePlans(n, true).some(function (p, i) { return p.join() !== makePlans(n, false)[i].join(); });
    statusEl.textContent = ordered
      ? "Plans rewritten so every thread takes locks in the order A, B, C" + (changed ? "." : " (they already were).") + " Try to deadlock it."
      : "Original plans restored.";
  });
  resetBtn.addEventListener("click", reset);
  randBtn.addEventListener("click", randomStep);
  autoBtn.addEventListener("click", function () {
    if (timer) { stopAuto(); return; }
    autoBtn.textContent = "Pause";
    autoBtn.setAttribute("aria-pressed", "true");
    timer = setInterval(function () { if (!randomStep()) stopAuto(); }, 750);
  });
  trialBtn.addEventListener("click", function () {
    var count = 500, dead = trials(n, ordered, count, 100 + trialSeed++);
    trialOut.textContent = "Ran " + count + " random schedules with " + (ordered ? "global lock order ON" : "the original plans") + ": " +
      dead + " deadlocked (" + Math.round(100 * dead / count) + "%).";
  });

  buildCards();
  reset();
})();
