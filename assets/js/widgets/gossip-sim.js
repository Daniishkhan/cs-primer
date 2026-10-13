/* Gossip & SWIM simulator (distributed chapter 3).

   Two tabs, both driven by a seeded generator (mulberry32) so a given seed always
   replays the same history.

   1. Rumour spreading. n nodes in a ring; one starts with a rumour. In every round each
      node contacts `fan-out` random other nodes.
        push       an infected node tells its peer;
        pull       a node asks its peer and learns the rumour if the peer has it;
        push-pull  both directions in one exchange.
      Each message is lost independently with the chosen probability (a pull needs both
      the request and the reply to survive). Blue lines are messages that infected a new
      node, grey lines carried nothing new, red dashed lines were lost. The chart shows
      the infected count per round; compare with the textbook estimate log2(n) + ln(n)
      for push gossip with fan-out 1 and no loss.

   2. A SWIM protocol period. Prober A checks target B: a direct ping and ack; if no ack,
      k helpers are asked to ping B on A's behalf (ping-req) and relay any ack. If neither
      path yields an ack, A marks B "suspect". Every message is lost independently with
      the chosen probability. The target can be alive or crashed. "Run 2000 periods"
      measures how often a healthy B is wrongly suspected and compares with the formula
      p_direct_fail * p_indirect_fail^k  (messages independent).

   Simplifications: synchronous rounds, uniform random peer choice, independent loss.
   Real losses are correlated (a congested node loses everything), which this ignores. */
(function () {
  "use strict";
  var root = document.getElementById("gossip-sim");
  if (!root) return;
  var NS = "http://www.w3.org/2000/svg";

  function mulberry32(a) {
    return function () {
      a |= 0; a = a + 0x6D2B79F5 | 0;
      var t = Math.imul(a ^ a >>> 15, 1 | a);
      t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
      return ((t ^ t >>> 14) >>> 0) / 4294967296;
    };
  }
  function h(tag, attrs, text) {
    var e = document.createElement(tag);
    if (attrs) for (var k in attrs) { if (k === "class") e.className = attrs[k]; else e.setAttribute(k, attrs[k]); }
    if (text != null) e.textContent = text;
    return e;
  }
  function s(tag, attrs, text) {
    var e = document.createElementNS(NS, tag);
    if (attrs) for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (text != null) e.textContent = text;
    return e;
  }
  function clear(e) { while (e.firstChild) e.removeChild(e.firstChild); }

  /* ---------- frame ---------- */
  var head = h("div", { class: "widget-head" });
  head.appendChild(h("span", { class: "widget-tag" }, "Simulator"));
  head.appendChild(h("h4", { class: "widget-title" }, "Gossip and SWIM, interactively"));
  root.appendChild(head);
  var tabs = h("div", { class: "gs-tabs", role: "tablist" });
  var tabA = h("button", { class: "btn small", role: "tab", type: "button", "aria-selected": "true" }, "Rumour spreading");
  var tabB = h("button", { class: "btn small", role: "tab", type: "button", "aria-selected": "false" }, "SWIM probe");
  tabs.appendChild(tabA); tabs.appendChild(tabB);
  root.appendChild(tabs);
  var panelA = h("div", { class: "gs-panel", role: "tabpanel" });
  var panelB = h("div", { class: "gs-panel", role: "tabpanel", hidden: "" });
  root.appendChild(panelA); root.appendChild(panelB);
  function showTab(a) {
    tabA.setAttribute("aria-selected", a ? "true" : "false");
    tabB.setAttribute("aria-selected", a ? "false" : "true");
    if (a) panelB.setAttribute("hidden", ""); else panelB.removeAttribute("hidden");
    if (a) panelA.removeAttribute("hidden"); else panelA.setAttribute("hidden", "");
    if (!a) stopPlay();
  }
  tabA.addEventListener("click", function () { showTab(true); });
  tabB.addEventListener("click", function () { showTab(false); });

  function control(parent, label, node) {
    var w = h("label", { class: "gs-ctl" });
    w.appendChild(h("span", { class: "gs-ctl-l" }, label));
    w.appendChild(node);
    parent.appendChild(w);
    return w;
  }
  function range(min, max, val, step) {
    return h("input", { type: "range", min: min, max: max, value: val, step: step || 1 });
  }

  /* =====================================================================
     Tab 1: rumour spreading
     ===================================================================== */
  var G = { n: 32, fan: 1, mode: "push", loss: 0, seed: 1, rnd: null, inf: [], round: 0, hist: [], edges: [], done: false };
  var ctlA = h("div", { class: "gs-controls" });
  var selN = h("select");
  [16, 32, 64].forEach(function (v) { var o = h("option", { value: v }, v + " nodes"); if (v === 32) o.selected = true; selN.appendChild(o); });
  var selMode = h("select");
  [["push", "push"], ["pull", "pull"], ["pp", "push-pull"]].forEach(function (m) { selMode.appendChild(h("option", { value: m[0] }, m[1])); });
  var rFan = range(1, 4, 1), rLoss = range(0, 50, 0, 5);
  var vFan = h("span", { class: "gs-val" }, "1"), vLoss = h("span", { class: "gs-val" }, "0%");
  control(ctlA, "Cluster", selN);
  control(ctlA, "Style", selMode);
  var wf = control(ctlA, "Fan-out", rFan); wf.appendChild(vFan);
  var wl = control(ctlA, "Message loss", rLoss); wl.appendChild(vLoss);
  panelA.appendChild(ctlA);
  var btnsA = h("div", { class: "gs-btns" });
  var bStep = h("button", { class: "btn primary small", type: "button" }, "Next round");
  var bPlay = h("button", { class: "btn small", type: "button" }, "Play");
  var bReset = h("button", { class: "btn small", type: "button" }, "Reset (same seed)");
  var bSeed = h("button", { class: "btn small", type: "button" }, "New seed");
  [bStep, bPlay, bReset, bSeed].forEach(function (b) { btnsA.appendChild(b); });
  panelA.appendChild(btnsA);
  var gridA = h("div", { class: "gs-grid" });
  var svgRing = s("svg", { viewBox: "0 0 360 300", role: "img", "aria-label": "Nodes arranged in a ring; infected nodes are filled" });
  var svgChart = s("svg", { viewBox: "0 0 360 300", role: "img", "aria-label": "Chart of infected nodes against rounds" });
  gridA.appendChild(h("div", { class: "gs-pane" })).appendChild(svgRing);
  gridA.appendChild(h("div", { class: "gs-pane" })).appendChild(svgChart);
  panelA.appendChild(gridA);
  var statA = h("p", { class: "gs-status", "aria-live": "polite" });
  panelA.appendChild(statA);
  panelA.appendChild(h("p", { class: "gs-legend" }, "Yellow node: knows the rumour. Blue line: a message that informed someone new. Grey line: a message that told nothing new. Red dashed line: lost."));

  function gReset(newSeed) {
    if (newSeed) G.seed = (G.seed * 7 + 13) % 9973;
    G.rnd = mulberry32(G.seed * 2654435761 >>> 0);
    G.n = parseInt(selN.value, 10); G.fan = parseInt(rFan.value, 10); G.mode = selMode.value; G.loss = parseInt(rLoss.value, 10) / 100;
    G.inf = []; for (var i = 0; i < G.n; i++) G.inf.push(false);
    G.inf[0] = true; G.round = 0; G.hist = [1]; G.edges = []; G.done = false;
    drawA();
  }
  function gStep() {
    if (G.done) return;
    var n = G.n, nxt = G.inf.slice(), edges = [], i, f;
    for (i = 0; i < n; i++) {
      for (f = 0; f < G.fan; f++) {
        var p = Math.floor(G.rnd() * (n - 1)); if (p >= i) p++;
        var m = G.mode, e = { a: i, b: p, kind: "dead" };
        if (m === "push" || m === "pp") {
          if (G.rnd() < G.loss) { e.kind = "lost"; }
          else if (G.inf[i] && !nxt[p]) { nxt[p] = true; e.kind = "new"; e.to = p; }
        }
        if (m === "pull" || m === "pp") {
          var reqLost = (m === "pull") ? (G.rnd() < G.loss) : (e.kind === "lost");
          var repLost = G.rnd() < G.loss;
          if (reqLost || repLost) { if (e.kind !== "new") e.kind = "lost"; }
          else if (G.inf[p] && !nxt[i]) { nxt[i] = true; e.kind = "new"; e.to = i; }
        }
        edges.push(e);
      }
    }
    G.inf = nxt; G.round++; G.edges = edges;
    var c = 0; for (i = 0; i < n; i++) if (nxt[i]) c++;
    G.hist.push(c);
    if (c === n) G.done = true;
    drawA();
  }
  function pos(i, n, R, cx, cy) {
    var a = -Math.PI / 2 + 2 * Math.PI * i / n;
    return [cx + R * Math.cos(a), cy + R * Math.sin(a)];
  }
  function drawA() {
    var n = G.n, i;
    clear(svgRing);
    var R = 118, cx = 180, cy = 150, r = n <= 16 ? 11 : n <= 32 ? 8 : 5.5;
    var grp = s("g");
    G.edges.forEach(function (e) {
      var A = pos(e.a, n, R, cx, cy), B = pos(e.b, n, R, cx, cy);
      var cls = e.kind === "new" ? "gs-e-new" : e.kind === "lost" ? "gs-e-lost" : "gs-e-dead";
      grp.appendChild(s("line", { x1: A[0].toFixed(1), y1: A[1].toFixed(1), x2: B[0].toFixed(1), y2: B[1].toFixed(1), class: cls }));
    });
    svgRing.appendChild(grp);
    for (i = 0; i < n; i++) {
      var P = pos(i, n, R, cx, cy);
      svgRing.appendChild(s("circle", { cx: P[0].toFixed(1), cy: P[1].toFixed(1), r: r, class: G.inf[i] ? "gs-n-inf" : "gs-n" }));
    }
    svgRing.appendChild(s("text", { x: cx, y: cy - 4, "text-anchor": "middle", class: "gs-big" }, String(G.hist[G.hist.length - 1])));
    svgRing.appendChild(s("text", { x: cx, y: cy + 14, "text-anchor": "middle", class: "gs-small" }, "of " + n + " informed"));
    // chart
    clear(svgChart);
    var L = 38, Rr = 346, T = 16, Bm = 262;
    var est = Math.log(n) / Math.LN2 + Math.log(n);
    var maxR = Math.max(10, Math.ceil(est * 1.5), G.round + 2);
    function X(rd) { return L + (Rr - L) * rd / maxR; }
    function Y(v) { return Bm - (Bm - T) * v / n; }
    svgChart.appendChild(s("line", { x1: L, y1: Bm, x2: Rr, y2: Bm, class: "gs-axis" }));
    svgChart.appendChild(s("line", { x1: L, y1: T, x2: L, y2: Bm, class: "gs-axis" }));
    svgChart.appendChild(s("line", { x1: L, y1: Y(n), x2: Rr, y2: Y(n), class: "gs-ref" }));
    svgChart.appendChild(s("text", { x: L - 4, y: Y(n) + 4, "text-anchor": "end", class: "gs-small" }, String(n)));
    svgChart.appendChild(s("text", { x: L - 4, y: Bm + 4, "text-anchor": "end", class: "gs-small" }, "0"));
    var step = maxR > 24 ? 5 : 2;
    for (i = 0; i <= maxR; i += step) {
      svgChart.appendChild(s("text", { x: X(i), y: Bm + 16, "text-anchor": "middle", class: "gs-small" }, String(i)));
    }
    svgChart.appendChild(s("text", { x: (L + Rr) / 2, y: 292, "text-anchor": "middle", class: "gs-small" }, "rounds"));
    if (est < maxR) {
      svgChart.appendChild(s("line", { x1: X(est), y1: T, x2: X(est), y2: Bm, class: "gs-est" }));
      svgChart.appendChild(s("text", { x: X(est) + 3, y: T + 10, class: "gs-small gs-est-t" }, "log2 n + ln n = " + est.toFixed(1)));
    }
    var pts = G.hist.map(function (v, k) { return X(k).toFixed(1) + "," + Y(v).toFixed(1); }).join(" ");
    svgChart.appendChild(s("polyline", { points: pts, class: "gs-curve" }));
    G.hist.forEach(function (v, k) { svgChart.appendChild(s("circle", { cx: X(k).toFixed(1), cy: Y(v).toFixed(1), r: 3, class: "gs-pt" })); });
    var last = G.hist[G.hist.length - 1];
    statA.textContent = "Round " + G.round + ": " + last + " of " + n + " nodes know the rumour" +
      (G.done ? ". Everyone knows after " + G.round + " rounds (estimate for push, fan-out 1, no loss: " + est.toFixed(1) + ")." : ".") +
      (G.round === 0 ? " Press Next round." : "");
    bStep.disabled = G.done; bPlay.disabled = G.done;
  }
  var timer = null;
  function stopPlay() { if (timer) { clearInterval(timer); timer = null; } bPlay.textContent = "Play"; }
  bStep.addEventListener("click", function () { stopPlay(); gStep(); });
  bPlay.addEventListener("click", function () {
    if (timer) { stopPlay(); return; }
    bPlay.textContent = "Pause";
    timer = setInterval(function () { gStep(); if (G.done) stopPlay(); }, 700);
  });
  bReset.addEventListener("click", function () { stopPlay(); gReset(false); });
  bSeed.addEventListener("click", function () { stopPlay(); gReset(true); });
  [selN, selMode].forEach(function (c) { c.addEventListener("change", function () { stopPlay(); gReset(false); }); });
  rFan.addEventListener("input", function () { vFan.textContent = rFan.value; stopPlay(); gReset(false); });
  rLoss.addEventListener("input", function () { vLoss.textContent = rLoss.value + "%"; stopPlay(); gReset(false); });

  /* =====================================================================
     Tab 2: one SWIM protocol period
     ===================================================================== */
  var W = { seed: 5, rnd: null, loss: 0.2, k: 3, alive: true };
  var ctlB = h("div", { class: "gs-controls" });
  var selT = h("select");
  selT.appendChild(h("option", { value: "alive" }, "B is healthy"));
  selT.appendChild(h("option", { value: "dead" }, "B has crashed"));
  var rL2 = range(0, 60, 20, 5), rK = range(0, 4, 3, 1);
  var vL2 = h("span", { class: "gs-val" }, "20%"), vK = h("span", { class: "gs-val" }, "3");
  control(ctlB, "Target", selT);
  var wl2 = control(ctlB, "Message loss", rL2); wl2.appendChild(vL2);
  var wk = control(ctlB, "Helpers (k)", rK); wk.appendChild(vK);
  panelB.appendChild(ctlB);
  var btnsB = h("div", { class: "gs-btns" });
  var bOne = h("button", { class: "btn primary small", type: "button" }, "Run one protocol period");
  var bMany = h("button", { class: "btn small", type: "button" }, "Run 2000 periods");
  btnsB.appendChild(bOne); btnsB.appendChild(bMany);
  panelB.appendChild(btnsB);
  var gridB = h("div", { class: "gs-grid" });
  var svgSw = s("svg", { viewBox: "0 0 360 300", role: "img", "aria-label": "Prober A, target B and helper nodes with the messages of one SWIM period" });
  gridB.appendChild(h("div", { class: "gs-pane" })).appendChild(svgSw);
  var logPane = h("div", { class: "gs-pane" });
  logPane.appendChild(h("h5", null, "What happened"));
  var logList = h("ol", { class: "gs-log" });
  logPane.appendChild(logList);
  gridB.appendChild(logPane);
  panelB.appendChild(gridB);
  var verdict = h("p", { class: "gs-status", "aria-live": "polite" });
  panelB.appendChild(verdict);
  var stats = h("p", { class: "gs-stats" });
  panelB.appendChild(stats);
  panelB.appendChild(h("p", { class: "gs-legend" }, "Green line: delivered. Red dashed line with a cross: lost. A crashed target never answers, so every message to it is wasted. Helpers are healthy; only the network drops messages."));

  function posSw(name) {
    if (name === "A") return [50, 150];
    if (name === "B") return [310, 150];
    var idx = parseInt(name.slice(1), 10) - 1;
    return [180, 40 + idx * 68];
  }
  function resetSw() { W.rnd = mulberry32(W.seed * 40503 >>> 0); }
  function lose() { return W.rnd() < W.loss; }
  function runPeriod(draw) {
    var log = [], msgs = [], ack = false, via = null, sent = 0;
    function send(a, b, label) {
      var l = lose(); sent++; msgs.push({ a: a, b: b, lost: l, label: label });
      return !l;
    }
    var ping = send("A", "B", "ping");
    var directOk = false;
    if (ping && W.alive) { if (send("B", "A", "ack")) directOk = true; }
    log.push("A pings B directly: " + (ping ? "ping delivered" : "ping lost") + (ping && !W.alive ? ", but B is crashed and says nothing" : "") +
      (ping && W.alive ? (directOk ? ", ack came back." : ", but the ack was lost.") : "."));
    if (directOk) { ack = true; via = "directly"; }
    else {
      log.push("No ack before the timeout, so A asks " + W.k + " helper" + (W.k === 1 ? "" : "s") + " to probe B (ping-req).");
      for (var i = 1; i <= W.k; i++) {
        var hn = "H" + i, step = "";
        if (!send("A", hn, "ping-req")) { log.push(hn + ": ping-req lost on the way to the helper."); continue; }
        if (!send(hn, "B", "ping")) { log.push(hn + ": got the request, but its ping to B was lost."); continue; }
        if (!W.alive) { log.push(hn + ": pinged B, which is crashed, so nothing comes back."); continue; }
        if (!send("B", hn, "ack")) { log.push(hn + ": B answered, but the ack to the helper was lost."); continue; }
        if (!send(hn, "A", "ack")) { log.push(hn + ": the helper got B's ack, but its relay to A was lost."); continue; }
        log.push(hn + ": B answered through this helper; A hears of it.");
        ack = true; if (!via) via = "via helper " + hn;
      }
      if (W.k === 0) log.push("(k = 0: there are no helpers, so this is the plain ping-ack detector.)");
    }
    if (draw) drawSw(msgs, log, ack, via, sent);
    return ack;
  }
  function drawSw(msgs, log, ack, via, sent) {
    clear(svgSw);
    var names = ["A", "B"]; for (var i = 1; i <= W.k; i++) names.push("H" + i);
    // draw messages first
    msgs.forEach(function (m, idx) {
      var A = posSw(m.a), B = posSw(m.b);
      // offset parallel lines slightly so reply is distinct from request
      var dx = B[0] - A[0], dy = B[1] - A[1], len = Math.sqrt(dx * dx + dy * dy) || 1;
      var ox = -dy / len * 4, oy = dx / len * 4;
      var x1 = A[0] + ox, y1 = A[1] + oy, x2 = B[0] + ox, y2 = B[1] + oy;
      var f = m.lost ? 0.55 : 1;
      var xe = x1 + (x2 - x1) * f, ye = y1 + (y2 - y1) * f;
      svgSw.appendChild(s("line", { x1: x1.toFixed(1), y1: y1.toFixed(1), x2: xe.toFixed(1), y2: ye.toFixed(1), class: m.lost ? "gs-m-lost" : "gs-m-ok" }));
      if (m.lost) {
        svgSw.appendChild(s("path", { d: "M" + (xe - 4) + "," + (ye - 4) + " L" + (xe + 4) + "," + (ye + 4) + " M" + (xe - 4) + "," + (ye + 4) + " L" + (xe + 4) + "," + (ye - 4), class: "gs-x" }));
      }
    });
    names.forEach(function (nm) {
      var P = posSw(nm);
      var cls = nm === "B" ? (W.alive ? "gs-node-b" : "gs-node-dead") : nm === "A" ? "gs-node-a" : "gs-node-h";
      svgSw.appendChild(s("circle", { cx: P[0], cy: P[1], r: 16, class: cls }));
      svgSw.appendChild(s("text", { x: P[0], y: P[1] + 4, "text-anchor": "middle", class: "gs-nodelabel" }, nm));
    });
    if (!W.alive) svgSw.appendChild(s("path", { d: "M300,140 L320,160 M320,140 L300,160", class: "gs-x big" }));
    clear(logList);
    log.forEach(function (t) { logList.appendChild(h("li", null, t)); });
    verdict.className = "gs-status " + (ack === W.alive ? "ok" : "bad");
    var txt;
    if (ack) txt = "Result: B is considered alive (" + via + "). Messages sent this period: " + sent + ".";
    else txt = "Result: no ack by any path, so A marks B SUSPECT. Messages sent: " + sent + ".";
    if (ack && !W.alive) txt += " (Cannot happen: crashed nodes do not answer.)";
    if (!ack && W.alive) txt += " That is a FALSE suspicion: B is healthy. In real SWIM, B can still refute it with a higher incarnation number.";
    if (!ack && !W.alive) txt += " Correct: B really has crashed.";
    verdict.textContent = txt;
  }
  function readB() {
    W.alive = selT.value === "alive"; W.loss = parseInt(rL2.value, 10) / 100; W.k = parseInt(rK.value, 10);
  }
  function blank() {
    clear(svgSw); clear(logList); stats.textContent = "";
    readB();
    var names = ["A", "B"]; for (var i = 1; i <= W.k; i++) names.push("H" + i);
    names.forEach(function (nm) {
      var P = posSw(nm);
      svgSw.appendChild(s("circle", { cx: P[0], cy: P[1], r: 16, class: nm === "B" ? (W.alive ? "gs-node-b" : "gs-node-dead") : nm === "A" ? "gs-node-a" : "gs-node-h" }));
      svgSw.appendChild(s("text", { x: P[0], y: P[1] + 4, "text-anchor": "middle", class: "gs-nodelabel" }, nm));
    });
    if (!W.alive) svgSw.appendChild(s("path", { d: "M300,140 L320,160 M320,140 L300,160", class: "gs-x big" }));
    verdict.className = "gs-status"; verdict.textContent = "Press \"Run one protocol period\".";
  }
  bOne.addEventListener("click", function () { readB(); if (!W.rnd) resetSw(); stats.textContent = ""; runPeriod(true); });
  bMany.addEventListener("click", function () {
    readB(); resetSw();
    var N = 2000, suspects = 0;
    for (var i = 0; i < N; i++) if (!runPeriod(false)) suspects++;
    var p = W.loss, direct = 1 - Math.pow(1 - p, 2), ind = 1 - Math.pow(1 - p, 4);
    var theory = W.alive ? direct * Math.pow(ind, W.k) : 1;
    stats.textContent = W.alive
      ? "Over " + N + " periods a healthy B was wrongly suspected in " + suspects + " (" + (100 * suspects / N).toFixed(1) + "%). Formula: " + (100 * theory).toFixed(1) + "%. Without helpers it would be " + (100 * direct).toFixed(1) + "%."
      : "Over " + N + " periods the crashed B was suspected in " + suspects + " (" + (100 * suspects / N).toFixed(0) + "%): detection is certain once it is probed; the question is only when (the chapter's e/(e-1) periods).";
    verdict.className = "gs-status"; verdict.textContent = "Batch run complete. Change the loss or k and run again.";
  });
  [selT, rL2, rK].forEach(function (c) {
    c.addEventListener("input", function () { vL2.textContent = rL2.value + "%"; vK.textContent = rK.value; W.rnd = null; blank(); });
    c.addEventListener("change", function () { W.rnd = null; blank(); });
  });

  gReset(false);
  blank();
})();
