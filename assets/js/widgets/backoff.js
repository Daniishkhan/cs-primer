/* Retry-storm simulator (chapter 16).
   N clients all fail at the same moment (say the server just restarted).
   The server can handle CAP requests per time slot and rejects the rest.
   Rejected clients retry according to the chosen strategy. We simulate all
   three strategies with the same seed and draw requests-per-slot as bars. */
(function () {
  "use strict";
  var root = document.getElementById("backoff-sim");
  if (!root) return;

  var CAP = 10, MAX_SLOT = 400, BACKOFF_CAP = 64, BASE = 4;
  var NS = "http://www.w3.org/2000/svg";
  var STRATS = [
    { id: "fixed", label: "Fixed delay (retry every 4 slots)" },
    { id: "exp", label: "Exponential backoff, no jitter" },
    { id: "jit", label: "Exponential backoff + full jitter" }
  ];

  var clientsIn = root.querySelector("[data-act=clients]");
  var clientsOut = root.querySelector("[data-act=clients-out]");
  var stratSel = root.querySelector("[data-act=strategy]");
  var runBtn = root.querySelector("[data-act=run]");
  var svg = root.querySelector(".bo-chart");
  var tbody = root.querySelector(".bo-table tbody");
  var summary = root.querySelector(".bo-summary");

  function mulberry32(a) {
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      var t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  function delay(strategy, attempt, rng) {
    if (strategy === "fixed") return BASE;
    var ceil = Math.min(BACKOFF_CAP, BASE * Math.pow(2, attempt)); // attempt 0 = after first failure
    if (strategy === "exp") return ceil;
    return 1 + Math.floor(rng() * ceil); // full jitter: uniform 1..ceil
  }

  function simulate(strategy, n) {
    var rng = mulberry32(777);
    var due = {}; // slot -> array of client attempt counts
    due[0] = [];
    for (var i = 0; i < n; i++) due[0].push(0);
    var perSlot = [], sent = 0, done = 0, lastSlot = 0, peak = 0;
    for (var t = 0; t < MAX_SLOT && done < n; t++) {
      var batch = due[t] || [];
      perSlot[t] = batch.length;
      if (batch.length) { sent += batch.length; if (t > 0 && batch.length > peak) peak = batch.length; }
      // random order decides who gets served
      for (var k = batch.length - 1; k > 0; k--) {
        var j = Math.floor(rng() * (k + 1)); var tmp = batch[k]; batch[k] = batch[j]; batch[j] = tmp;
      }
      for (var m = 0; m < batch.length; m++) {
        if (m < CAP) { done++; lastSlot = t; }
        else {
          var d = delay(strategy, batch[m], rng);
          var nt = t + d;
          if (!due[nt]) due[nt] = [];
          due[nt].push(batch[m] + 1);
        }
      }
    }
    return { perSlot: perSlot, sent: sent, peak: peak, finished: done === n, lastSlot: lastSlot };
  }

  function s(tag, attrs, text) {
    var e = document.createElementNS(NS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    return e;
  }

  function draw(res, n) {
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    var W = 700, H = 230, L = 44, R = 10, T = 14, B = 34;
    var slots = Math.max(20, res.lastSlot + 2);
    var maxY = Math.max(n, CAP * 2);
    var pw = W - L - R, ph = H - T - B;
    var bw = pw / slots;
    // axes
    svg.appendChild(s("line", { x1: L, y1: T + ph, x2: W - R, y2: T + ph, "class": "line-thin" }));
    svg.appendChild(s("line", { x1: L, y1: T, x2: L, y2: T + ph, "class": "line-thin" }));
    [0, 0.5, 1].forEach(function (f) {
      var v = Math.round(maxY * f), y = T + ph - ph * f;
      svg.appendChild(s("text", { x: L - 6, y: y + 4, "text-anchor": "end", "class": "t-xs t-faint" }, String(v)));
    });
    var step = slots > 60 ? 20 : 10;
    for (var x = 0; x <= slots; x += step) {
      svg.appendChild(s("text", { x: L + x * bw, y: T + ph + 16, "text-anchor": "middle", "class": "t-xs t-faint" }, String(x)));
    }
    svg.appendChild(s("text", { x: L + pw / 2, y: H - 4, "text-anchor": "middle", "class": "t-xs t-muted" }, "time slots →"));
    // bars
    for (var t = 0; t < slots; t++) {
      var v2 = res.perSlot[t] || 0;
      if (!v2) continue;
      var h = ph * v2 / maxY;
      svg.appendChild(s("rect", { x: (L + t * bw + 0.5).toFixed(1), y: (T + ph - h).toFixed(1), width: Math.max(1, bw - 1).toFixed(1), height: Math.max(1, h).toFixed(1), "class": v2 > CAP ? "f-red" : "f-blue" }));
    }
    // capacity line
    var cy = T + ph - ph * CAP / maxY;
    svg.appendChild(s("line", { x1: L, y1: cy, x2: W - R, y2: cy, "class": "line-dash s-green" }));
    svg.appendChild(s("text", { x: W - R - 4, y: cy - 5, "text-anchor": "end", "class": "t-xs tc-green t-bold" }, "server capacity: " + CAP + " per slot"));
    svg.setAttribute("viewBox", "0 0 " + W + " " + H);
  }

  function row(cells, sel) {
    var tr = document.createElement("tr");
    if (sel) tr.className = "sel";
    cells.forEach(function (c) { var td = document.createElement("td"); td.textContent = c; tr.appendChild(td); });
    return tr;
  }

  function run() {
    var n = parseInt(clientsIn.value, 10);
    clientsOut.textContent = String(n);
    var chosen = stratSel.value;
    tbody.textContent = "";
    var shown = null;
    STRATS.forEach(function (st) {
      var r = simulate(st.id, n);
      if (st.id === chosen) shown = r;
      tbody.appendChild(row([st.label, String(r.sent), String(r.peak), r.finished ? String(r.lastSlot + 1) : ">" + MAX_SLOT], st.id === chosen));
    });
    draw(shown, n);
    summary.textContent = "Showing: " + STRATS.filter(function (x) { return x.id === chosen; })[0].label +
      ". Red bars are slots where more requests arrived than the server could handle.";
  }

  clientsIn.addEventListener("input", run);
  stratSel.addEventListener("change", run);
  runBtn.addEventListener("click", run);
  run();
})();
