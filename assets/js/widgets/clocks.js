/* Space-time diagram with Lamport and vector clocks (chapter 17).

   Markup contract (see chapters/17-time.html):
     #clocks-widget
       svg.clk-svg                       diagram is drawn into this
       button[data-act="ev"][data-p]     local event on process p (0..2)
       button[data-act="send"][data-from][data-to]
       button[data-act="toggle"][data-what="lamport"|"vector"]
       button[data-act="example"] / [data-act="reset"]
       .clk-out                          explanation text (aria-live)
*/
(function () {
  "use strict";
  var root = document.getElementById("clocks-widget");
  if (!root) return;
  var svg = root.querySelector("svg.clk-svg");
  var out = root.querySelector(".clk-out");
  if (!svg || !out) return;

  var NS = "http://www.w3.org/2000/svg";
  var NAMES = ["A", "B", "C"];
  var COLS = 13, X0 = 74, DX = 50, W = 740, H = 340;
  var LANE = [62, 172, 282];
  var R = 12;

  var events, msgs, col, Lc, Vc, cnt, sel, nodes;
  var showL = true, showV = true;

  function el(name, attrs, parent) {
    var n = document.createElementNS(NS, name);
    for (var k in attrs) if (Object.prototype.hasOwnProperty.call(attrs, k)) n.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(n);
    return n;
  }
  function vstr(v) { return "[" + v.join(",") + "]"; }
  function leq(x, y) { for (var i = 0; i < x.length; i++) if (x[i] > y[i]) return false; return true; }
  function hb(a, b) { return a !== b && leq(a.v, b.v); }
  function cx(e) { return X0 + e.col * DX + DX / 2; }
  function cy(e) { return LANE[e.p]; }

  function reset() {
    events = []; msgs = []; col = 0; Lc = [0, 0, 0]; cnt = [0, 0, 0];
    Vc = [[0, 0, 0], [0, 0, 0], [0, 0, 0]];
    sel = [];
    render();
    setHint("Add some events with the buttons above, or press “Load example”.");
  }

  function mk(p, kind) {
    cnt[p]++;
    var e = { id: events.length, p: p, col: col++, kind: kind, name: NAMES[p] + cnt[p], L: Lc[p], v: Vc[p].slice() };
    events.push(e);
    return e;
  }

  function full() {
    setHint("The diagram is full (" + COLS + " columns). Press Reset to start again.");
  }

  function doLocal(p) {
    if (col + 1 > COLS) { full(); return; }
    Lc[p]++; Vc[p][p]++;
    mk(p, "local");
    afterChange();
  }

  function doSend(p, q) {
    if (col + 2 > COLS) { full(); return; }
    Lc[p]++; Vc[p][p]++;
    var s = mk(p, "send");
    var Lm = Lc[p], Vm = Vc[p].slice();
    Lc[q] = Math.max(Lc[q], Lm) + 1;
    for (var i = 0; i < 3; i++) Vc[q][i] = Math.max(Vc[q][i], Vm[i]);
    Vc[q][q]++;
    var r = mk(q, "recv");
    msgs.push({ from: s.id, to: r.id });
    afterChange();
  }

  function afterChange() {
    sel = [];
    render();
    setHint("Click any event to select it. Every other event is then coloured by how it relates to your pick.");
  }

  function loadExample() {
    reset();
    doLocal(0);      // A1
    doLocal(1);      // B1
    doSend(0, 2);    // A2 -> C1
    doLocal(1);      // B3
    doSend(1, 2);    // B4 -> C3
    doLocal(2);      // C4
    doSend(2, 0);    // C5 -> A3
    setHint("Example loaded. Try clicking B1, then A2: Lamport says 1 < 2, but they are concurrent.");
  }

  /* ---------- drawing ---------- */

  function render() {
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    nodes = {};
    svg.setAttribute("viewBox", "0 0 " + W + " " + H);

    var defs = el("defs", {}, svg);
    var mark = el("marker", { id: "ahclk", viewBox: "0 0 10 10", refX: "9", refY: "5", markerWidth: "7", markerHeight: "7", orient: "auto" }, defs);
    el("path", { d: "M0,0 L10,5 L0,10 z", "class": "clk-arrow" }, mark);

    var i;
    for (i = 0; i < 3; i++) {
      el("line", { x1: 50, x2: W - 14, y1: LANE[i], y2: LANE[i], "class": "clk-lane" }, svg);
      var t = el("text", { x: 22, y: LANE[i] + 5, "class": "clk-lane-name clk-p" + i + "-t", "text-anchor": "middle" }, svg);
      t.textContent = NAMES[i];
    }
    var axis = el("text", { x: W - 16, y: 18, "class": "clk-axis", "text-anchor": "end" }, svg);
    axis.textContent = "time flows to the right →";

    for (i = 0; i < msgs.length; i++) {
      var a = events[msgs[i].from], b = events[msgs[i].to];
      var dx = cx(b) - cx(a), dy = cy(b) - cy(a), len = Math.sqrt(dx * dx + dy * dy);
      var ux = dx / len, uy = dy / len;
      el("line", {
        x1: cx(a) + ux * (R + 1), y1: cy(a) + uy * (R + 1),
        x2: cx(b) - ux * (R + 3), y2: cy(b) - uy * (R + 3),
        "class": "clk-msg", "marker-end": "url(#ahclk)"
      }, svg);
    }

    // Events whose message arrow leaves/arrives from below get their labels above, so the arrow doesn't cross them.
    var above = {};
    for (i = 0; i < msgs.length; i++) {
      var ma = events[msgs[i].from], mb = events[msgs[i].to];
      if (mb.p > ma.p) above[ma.id] = true; else above[mb.id] = true;
    }
    for (i = 0; i < events.length; i++) drawEvent(events[i], above[events[i].id]);
    applySel();
  }

  function drawEvent(e, labelsAbove) {
    var g = el("g", {
      "class": "clk-ev clk-p" + e.p, tabindex: "0", role: "button",
      "aria-label": "Event " + e.name + ", " + (e.kind === "send" ? "message send" : e.kind === "recv" ? "message receive" : "local event") +
        ", Lamport " + e.L + ", vector " + e.v.join(" ")
    }, svg);
    el("circle", { cx: cx(e), cy: cy(e), r: R + 4, "class": "ring" }, g);
    el("circle", { cx: cx(e), cy: cy(e), r: R, "class": "dot" }, g);
    var nm = el("text", { x: cx(e), y: cy(e) + 3.6, "class": "nm" }, g);
    nm.textContent = e.name;
    var y = cy(e) + R + 17;
    if (labelsAbove) y = cy(e) - R - 10 - (showL && showV ? 13 : 0);
    if (showL) {
      var l = el("text", { x: cx(e), y: y, "class": "clk-lbl l" }, g);
      l.textContent = "L=" + e.L;
      y += 13;
    }
    if (showV) {
      var v = el("text", { x: cx(e), y: y, "class": "clk-lbl v" }, g);
      v.textContent = vstr(e.v);
    }
    g.addEventListener("click", function () { pick(e); });
    g.addEventListener("keydown", function (ev) {
      if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); pick(e); }
    });
    nodes[e.id] = g;
  }

  function relation(a, b) { // how b relates to a
    if (hb(a, b)) return "after";
    if (hb(b, a)) return "before";
    return "conc";
  }

  function applySel() {
    for (var i = 0; i < events.length; i++) {
      var e = events[i], g = nodes[e.id];
      g.setAttribute("class", "clk-ev clk-p" + e.p);
      var cls = "";
      if (sel.length && sel.indexOf(e) !== -1) cls = " clk-sel";
      else if (sel.length) cls = " clk-" + relation(sel[0], e);
      if (cls) g.setAttribute("class", "clk-ev clk-p" + e.p + cls);
    }
  }

  function pick(e) {
    if (sel.length === 2) sel = [e];
    else if (sel.length === 1 && sel[0] === e) sel = [];
    else sel.push(e);
    applySel();
    explain();
  }

  /* ---------- explanations (textContent only) ---------- */

  function setHint(msg) {
    clearOut();
    addP(msg);
  }
  function clearOut() { while (out.firstChild) out.removeChild(out.firstChild); }
  function addP(text, bold) {
    var p = document.createElement("p");
    if (bold) {
      var s = document.createElement("strong");
      s.textContent = bold;
      p.appendChild(s);
      p.appendChild(document.createTextNode(" "));
    }
    p.appendChild(document.createTextNode(text));
    out.appendChild(p);
  }

  function explain() {
    clearOut();
    if (sel.length === 0) { addP("Nothing selected. Click an event."); return; }
    if (sel.length === 1) {
      var e = sel[0];
      addP("Selected " + e.name + " (Lamport " + e.L + ", vector " + vstr(e.v) + "). Blue events are in its causal past, green in its causal future, red dashed ones are concurrent with it. Click a second event to compare.");
      return;
    }
    var a = sel[0], b = sel[1];
    var x = a, y = b;
    if (hb(b, a)) { x = b; y = a; }
    if (hb(x, y)) {
      addP(x.name + " happened-before " + y.name + " (" + x.name + " → " + y.name + ").", "Ordered.");
      addP(vstr(x.v) + " ≤ " + vstr(y.v) + " in every slot, so information could have flowed from " + x.name + " to " + y.name + " along local steps and messages.", "Vector:");
      addP("L(" + x.name + ") = " + x.L + " < L(" + y.name + ") = " + y.L + ", exactly as the Lamport guarantee promises (if a → b then L(a) < L(b)).", "Lamport:");
    } else {
      var bigA = [], bigB = [];
      for (var i = 0; i < 3; i++) {
        if (a.v[i] > b.v[i]) bigA.push(NAMES[i]);
        if (b.v[i] > a.v[i]) bigB.push(NAMES[i]);
      }
      addP(a.name + " and " + b.name + " are concurrent (" + a.name + " ∥ " + b.name + "): neither could have influenced the other.", "Concurrent.");
      addP(vstr(a.v) + " is larger than " + vstr(b.v) + " in slot " + bigA.join(",") + ", but smaller in slot " + bigB.join(",") + ". Neither vector is ≤ the other, so vector clocks correctly say “concurrent”.", "Vector:");
      if (a.L === b.L) {
        addP("Both have L = " + a.L + ". A Lamport clock gives a tie here; the total order would break it by process id, which is arbitrary.", "Lamport:");
      } else {
        var lo = a.L < b.L ? a : b, hi = lo === a ? b : a;
        addP("L(" + lo.name + ") = " + lo.L + " < L(" + hi.name + ") = " + hi.L + ", which looks like “" + lo.name + " came first”, but there is no causal link at all. Lamport clocks cannot tell “before” from “concurrent”, because the guarantee only runs one way.", "Lamport:");
      }
    }
  }

  /* ---------- controls ---------- */

  root.addEventListener("click", function (ev) {
    var btn = ev.target.closest ? ev.target.closest("button[data-act]") : null;
    if (!btn || !root.contains(btn)) return;
    var act = btn.getAttribute("data-act");
    if (act === "ev") doLocal(+btn.getAttribute("data-p"));
    else if (act === "send") doSend(+btn.getAttribute("data-from"), +btn.getAttribute("data-to"));
    else if (act === "reset") reset();
    else if (act === "example") loadExample();
    else if (act === "toggle") {
      var what = btn.getAttribute("data-what");
      var now = btn.getAttribute("aria-pressed") !== "true";
      btn.setAttribute("aria-pressed", String(now));
      if (what === "lamport") showL = now; else showV = now;
      render();
    }
  });

  reset();
})();
