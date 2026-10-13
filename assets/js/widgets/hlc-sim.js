/* Hybrid logical clock simulator (distributed course, chapter 7).

   Three nodes (A, B, C) each have a physical clock that equals true time plus a fixed
   error ("skew", in milliseconds, set with the sliders). The reader drives the run:
     - advance true time by 1, 10 or 50 ms,
     - make a node do a local event, or send a message to another node,
     - deliver each in-flight message when they choose (so they control delays and reordering).

   Every event is stamped three ways at once:
     wall    - the node's own physical clock reading (true time + skew)
     Lamport - Lamport's counter: +1 per event, max(local, received) + 1 on receive
     HLC     - a hybrid logical clock (Kulkarni et al. 2014), as l.c where
                 l = the largest physical time this node has seen (its own or via a message)
                 c = a small counter that breaks ties while l stays the same
               Send/local:  l' = max(l, wall);  c' = (l' == l) ? c + 1 : 0
               Receive m:   l' = max(l, m.l, wall)
                              c' = max(c, m.c) + 1   if l' == l == m.l
                                   c + 1             if l' == l  (and l' > m.l)
                                   m.c + 1           if l' == m.l (and l' > l)
                                   0                 otherwise

   The table flags every message whose receive is stamped NOT after its send, and the summary
   counts how many messages each kind of timestamp orders correctly. Nothing is random and
   nothing is stored. There is no animation, so prefers-reduced-motion needs no special case.
   At most 12 events fit, to keep the picture readable. */
(function () {
  "use strict";
  var root = document.getElementById("hlc-sim");
  if (!root) return;

  var NAMES = ["A", "B", "C"], MAXEV = 12;
  var T0 = 1000;
  var skew = { A: 0, B: -40, C: 25 };
  var S;

  function fresh() {
    var n = {};
    NAMES.forEach(function (x) { n[x] = { l: 0, c: 0, lam: 0 }; });
    return { t: T0, nodes: n, events: [], inflight: [], nextMsg: 1, note: "", stepped: false };
  }

  function wall(name) { return S.t + skew[name]; }

  function stampLocal(name) {
    var nd = S.nodes[name], oldL = nd.l, pt = wall(name);
    nd.l = Math.max(oldL, pt);
    nd.c = (nd.l === oldL) ? nd.c + 1 : 0;
    nd.lam += 1;
  }
  function stampReceive(name, m) {
    var nd = S.nodes[name], oldL = nd.l, pt = wall(name);
    nd.l = Math.max(oldL, m.l, pt);
    if (nd.l === oldL && oldL === m.l) nd.c = Math.max(nd.c, m.c) + 1;
    else if (nd.l === oldL) nd.c = nd.c + 1;
    else if (nd.l === m.l) nd.c = m.c + 1;
    else nd.c = 0;
    nd.lam = Math.max(nd.lam, m.lam) + 1;
  }

  function record(name, kind, extra) {
    var nd = S.nodes[name];
    var ev = { id: S.events.length, node: name, kind: kind, t: S.t, wall: wall(name), lam: nd.lam, l: nd.l, c: nd.c, peer: extra && extra.peer, msg: extra && extra.msg, from: extra && extra.from };
    S.events.push(ev);
    return ev;
  }

  function full() { return S.events.length >= MAXEV; }

  function localEvent(name) {
    if (full()) return;
    stampLocal(name);
    record(name, "local");
    S.note = "";
    render();
  }
  function send(from, to) {
    if (full()) return;
    stampLocal(from);
    var ev = record(from, "send", { peer: to });
    var m = { id: S.nextMsg++, from: from, to: to, l: S.nodes[from].l, c: S.nodes[from].c, lam: S.nodes[from].lam, sendEv: ev.id, wall: ev.wall };
    S.inflight.push(m);
    S.note = "";
    render();
  }
  function deliver(id) {
    if (full()) return;
    var k = -1, i;
    for (i = 0; i < S.inflight.length; i++) if (S.inflight[i].id === id) k = i;
    if (k < 0) return;
    var m = S.inflight.splice(k, 1)[0];
    stampReceive(m.to, m);
    var ev = record(m.to, "recv", { peer: m.from, msg: m, from: m.from });
    ev.sendEv = m.sendEv;
    S.note = "";
    render();
  }
  function advance(ms) { S.t += ms; S.note = ""; render(); }
  function reset() { S = fresh(); render(); }

  function replay() {
    skew.A = 0; skew.B = -40; skew.C = 25;
    S = fresh();
    send("A", "B");              // A writes at true time 1000
    S.t += 10;
    var m = S.inflight[0];
    deliver(m.id);               // B hears 10 ms later; its clock is 40 ms behind
    S.t += 1;
    send("B", "A");              // B replies at once
    S.t += 19;
    deliver(S.inflight[0].id);   // A receives the reply
    S.t += 1;
    localEvent("A");
    S.note = "Replayed the chapter's example (B's clock is 40 ms behind). Look at the row where B receives: B's wall clock reads earlier than A's send, but its HLC is still later.";
    render();
  }

  /* ---------- verdicts ---------- */
  function verdicts() {
    var pairs = 0, okWall = 0, okLam = 0, okHlc = 0, maxGap = 0, i;
    var byId = {};
    S.events.forEach(function (e) { byId[e.id] = e; });
    S.events.forEach(function (e) {
      if (e.kind === "recv") {
        var s = byId[e.sendEv];
        pairs++;
        e.bad = !(e.wall > s.wall);
        if (e.wall > s.wall) okWall++;
        if (e.lam > s.lam) okLam++;
        if (e.l > s.l || (e.l === s.l && e.c > s.c)) okHlc++;
      }
      maxGap = Math.max(maxGap, e.l - e.wall);
    });
    var spread = Math.max(skew.A, skew.B, skew.C) - Math.min(skew.A, skew.B, skew.C);
    return { pairs: pairs, okWall: okWall, okLam: okLam, okHlc: okHlc, maxGap: maxGap, spread: spread };
  }

  /* ---------- DOM helpers ---------- */
  var NS = "http://www.w3.org/2000/svg";
  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function sv(tag, attrs, text) {
    var e = document.createElementNS(NS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (text != null) e.textContent = text;
    return e;
  }
  function button(text, cls, fn, label) { var b = el("button", "btn " + (cls || ""), text); b.type = "button"; if (label) b.setAttribute("aria-label", label); b.addEventListener("click", fn); return b; }

  /* ---------- UI skeleton ---------- */
  root.textContent = "";
  var head = el("div", "widget-head");
  head.appendChild(el("span", "widget-tag", "Simulator"));
  head.appendChild(el("h4", "widget-title", "Hybrid logical clocks vs Lamport vs the wall clock"));
  root.appendChild(head);
  root.appendChild(el("p", "widget-help", "Each node's wall clock is true time plus its own error. Make events, send messages, and deliver them in any order you like. Watch which kind of timestamp keeps cause before effect."));

  var skewBox = el("div", "hs-skews");
  root.appendChild(skewBox);
  var skewOut = {};
  NAMES.forEach(function (n) {
    var wrap = el("label", "hs-skew");
    wrap.appendChild(el("span", "hs-skew-name", "Clock error of " + n));
    var inp = el("input"); inp.type = "range"; inp.min = "-80"; inp.max = "80"; inp.step = "5"; inp.value = String(skew[n]);
    inp.id = "hs-skew-" + n;
    var out = el("span", "hs-skew-val", "");
    inp.addEventListener("input", function () { skew[n] = +inp.value; if (S.events.length) S.stepped = true; render(); });
    skewOut[n] = { inp: inp, out: out };
    wrap.appendChild(inp); wrap.appendChild(out);
    skewBox.appendChild(wrap);
  });

  var timeRow = el("div", "widget-row hs-row");
  var timeLbl = el("span", "hs-time", "");
  timeRow.appendChild(timeLbl);
  timeRow.appendChild(button("+1 ms", "small", function () { advance(1); }));
  timeRow.appendChild(button("+10 ms", "small", function () { advance(10); }));
  timeRow.appendChild(button("+50 ms", "small", function () { advance(50); }));
  timeRow.appendChild(button("Replay chapter example", "small", replay));
  timeRow.appendChild(button("Reset", "small", reset));
  root.appendChild(timeRow);

  var nodeRows = el("div", "hs-nodes");
  root.appendChild(nodeRows);
  var nodeUI = {};
  NAMES.forEach(function (n) {
    var box = el("div", "hs-node");
    var title = el("div", "hs-node-title", "Node " + n);
    var state = el("div", "hs-node-state", "");
    var btns = el("div", "hs-node-btns");
    var bEv = button("Local event", "small", function () { localEvent(n); });
    btns.appendChild(bEv);
    var sendBtns = [];
    NAMES.forEach(function (m) {
      if (m === n) return;
      var b = button("Send to " + m, "small", function () { send(n, m); });
      btns.appendChild(b); sendBtns.push(b);
    });
    box.appendChild(title); box.appendChild(state); box.appendChild(btns);
    nodeRows.appendChild(box);
    nodeUI[n] = { state: state, buttons: [bEv].concat(sendBtns) };
  });

  var flightLabel = el("div", "hs-label", "Messages in flight (deliver in any order)");
  root.appendChild(flightLabel);
  var flightBox = el("div", "hs-flight");
  root.appendChild(flightBox);

  var figLabel = el("div", "hs-label", "Space-time diagram (one line per node, messages as arrows, events in the order you made them)");
  root.appendChild(figLabel);
  var figBox = el("div", "hs-fig");
  root.appendChild(figBox);

  var tabLabel = el("div", "hs-label", "Event log");
  root.appendChild(tabLabel);
  var tabBox = el("div", "hs-table-wrap");
  root.appendChild(tabBox);

  var sum = el("div", "hs-summary");
  sum.setAttribute("role", "status"); sum.setAttribute("aria-live", "polite");
  root.appendChild(sum);

  /* ---------- render ---------- */
  var LANEY = { A: 40, B: 90, C: 140 };
  function render() {
    var vd = verdicts();
    NAMES.forEach(function (n) {
      var v = skew[n];
      skewOut[n].out.textContent = (v > 0 ? "+" : "") + v + " ms";
      skewOut[n].inp.value = String(v);
      var nd = S.nodes[n];
      nodeUI[n].state.textContent = "wall " + wall(n) + "   Lamport " + nd.lam + "   HLC " + nd.l + "." + nd.c;
      nodeUI[n].buttons.forEach(function (b) { b.disabled = full(); });
    });
    timeLbl.textContent = "True time: " + S.t + " ms";

    // in flight
    flightBox.textContent = "";
    if (!S.inflight.length) flightBox.appendChild(el("span", "hs-empty", "(none)"));
    S.inflight.forEach(function (m) {
      var b = button("Deliver " + m.from + "→" + m.to + " (sent " + m.l + "." + m.c + ")", "small", function () { deliver(m.id); });
      b.disabled = full();
      flightBox.appendChild(b);
    });

    // space-time diagram
    var n = S.events.length, step = Math.min(60, 560 / Math.max(n, 1));
    var svg = sv("svg", { viewBox: "0 0 700 190", role: "img", "aria-label": "Space-time diagram with " + n + " events on three node timelines" });
    svg.style.minWidth = "520px";
    var defs = sv("defs", {});
    var mk = sv("marker", { id: "ahX07s", viewBox: "0 0 10 10", refX: "9", refY: "5", markerWidth: "7", markerHeight: "7", orient: "auto-start-reverse" });
    mk.appendChild(sv("path", { d: "M0,0 L10,5 L0,10 z", "class": "arrowhead" }));
    defs.appendChild(mk); svg.appendChild(defs);
    NAMES.forEach(function (nm) {
      svg.appendChild(sv("line", { x1: 50, y1: LANEY[nm], x2: 690, y2: LANEY[nm], "class": "line-thin" }));
      svg.appendChild(sv("text", { x: 12, y: LANEY[nm] + 4, "class": "t-sm t-bold " + (nm === "A" ? "tc-blue" : nm === "B" ? "tc-green" : "tc-purple") }, nm));
    });
    function xOf(idx) { return 80 + idx * step; }
    var byId = {};
    S.events.forEach(function (e) { byId[e.id] = e; });
    // arrows for delivered messages
    S.events.forEach(function (e) {
      if (e.kind === "recv") {
        var s = byId[e.sendEv];
        svg.appendChild(sv("line", { x1: xOf(s.id), y1: LANEY[s.node], x2: xOf(e.id), y2: LANEY[e.node], "class": "line s-blue", "marker-end": "url(#ahX07s)" }));
      }
    });
    // stubs for in-flight messages
    S.inflight.forEach(function (m) {
      var x = xOf(m.sendEv), y1 = LANEY[m.from], y2 = LANEY[m.to];
      var dy = y2 > y1 ? 22 : -22;
      svg.appendChild(sv("line", { x1: x, y1: y1, x2: x + 14, y2: y1 + dy, "class": "line-dash s-orange" }));
    });
    S.events.forEach(function (e) {
      var x = xOf(e.id), y = LANEY[e.node];
      var cls = e.kind === "send" ? "f-blue" : e.kind === "recv" ? (e.bad ? "f-red" : "f-green") : "f-yellow";
      svg.appendChild(sv("circle", { cx: x, cy: y, r: 6, "class": cls }));
      svg.appendChild(sv("text", { x: x, y: y - 11, "text-anchor": "middle", "class": "t-xs mono" }, e.l + "." + e.c));
    });
    svg.appendChild(sv("text", { x: 690, y: 184, "text-anchor": "end", "class": "t-xs t-faint" }, "labels are HLC values l.c; red dot = wall clock puts the receive before its send"));
    figBox.textContent = "";
    figBox.appendChild(svg);

    // table
    var table = el("table", "hs-table");
    var thead = el("thead"), hr = el("tr");
    ["#", "True t", "Node", "Event", "Wall", "Lamport", "HLC l.c", "l − wall"].forEach(function (h) { hr.appendChild(el("th", null, h)); });
    thead.appendChild(hr); table.appendChild(thead);
    var tb = el("tbody");
    S.events.forEach(function (e) {
      var tr = el("tr", e.bad ? "hs-bad" : "");
      var what = e.kind === "local" ? "local event" : e.kind === "send" ? "send to " + e.peer : "receive from " + e.peer + (e.bad ? "  (wall ≤ send!)" : "");
      [String(e.id + 1), String(e.t), e.node, what, String(e.wall), String(e.lam), e.l + "." + e.c, String(e.l - e.wall)].forEach(function (v) { tr.appendChild(el("td", null, v)); });
      tb.appendChild(tr);
    });
    if (!S.events.length) { var tr0 = el("tr"); var td0 = el("td", "hs-empty", "No events yet."); td0.colSpan = 8; tr0.appendChild(td0); tb.appendChild(tr0); }
    table.appendChild(tb);
    tabBox.textContent = "";
    tabBox.appendChild(table);

    // summary
    var parts = [];
    if (vd.pairs) {
      parts.push("Of " + vd.pairs + " delivered message" + (vd.pairs > 1 ? "s" : "") + ", the receive is stamped after its send by the wall clock in " + vd.okWall + ", by Lamport in " + vd.okLam + ", by HLC in " + vd.okHlc + ".");
    } else parts.push("Deliver a message to compare how the three stamps order it.");
    parts.push("Largest HLC lead over a node's own wall clock so far: " + vd.maxGap + " ms " + (S.stepped ? "(you moved a clock slider after events had happened, which is a clock step, so the usual bound of one clock spread no longer applies; Reset to restore it)." : "(while clocks only drift and never step, it cannot exceed the spread between clocks, now " + vd.spread + " ms)."));
    if (full()) parts.push("Event limit (" + MAXEV + ") reached. Press Reset to start again.");
    if (S.note) parts.push(S.note);
    sum.textContent = parts.join(" ");
  }

  S = fresh();
  render();
})();
