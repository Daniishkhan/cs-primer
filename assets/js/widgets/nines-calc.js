/* Nines calculator (reliability chapter 1).
   A request passes through a chain of stages IN SERIES. Each stage is a group of N identical
   replicas IN PARALLEL (any one is enough). The beta-factor model adds correlation: a fraction
   beta of each replica's unavailability is a common cause that takes every replica of the stage
   down together.

     replica unavailability   q
     stage unavailability     U = beta*q + ((1 - beta)*q)^N
     whole chain              A = product over stages of (1 - U)

   With beta = 0 this is the textbook independent model. Pure maths first, DOM afterwards. */
(function () {
  "use strict";

  var YEAR_MIN = 365 * 24 * 60;

  function stageUnavail(q, n, beta) { return beta * q + Math.pow((1 - beta) * q, n); }

  function chain(stages, beta) {
    var avail = 1, parts = [];
    stages.forEach(function (s) {
      var u = stageUnavail(1 - s.a, s.n, beta);
      parts.push(u);
      avail *= (1 - u);
    });
    return { avail: avail, parts: parts };
  }

  function fmtDuration(min) {
    if (min < 0.0005) return "under 0.03 seconds";
    if (min < 1) return (min * 60).toFixed(min * 60 < 10 ? 1 : 0) + " seconds";
    if (min < 120) return min.toFixed(min < 10 ? 1 : 0) + " minutes";
    if (min < 2880) return (min / 60).toFixed(1) + " hours";
    return (min / 1440).toFixed(1) + " days";
  }

  function fmtPct(a) {
    var u = 1 - a;
    if (u <= 0) return "100%";
    var digits = Math.min(8, Math.max(2, Math.ceil(-Math.log10(u)) + 1 - 2));
    return (a * 100).toFixed(digits) + "%";
  }

  function nines(a) { var u = 1 - a; return u <= 0 ? Infinity : -Math.log10(u); }

  var core = { stageUnavail: stageUnavail, chain: chain, fmtDuration: fmtDuration, nines: nines };
  if (typeof module !== "undefined" && module.exports) module.exports = core;

  if (typeof document === "undefined") return;
  var root = document.getElementById("nines-calc");
  if (!root) return;

  var NS = "http://www.w3.org/2000/svg";
  var LEVELS = [0.99, 0.995, 0.999, 0.9995, 0.9999, 0.99999];
  var PRESETS = {
    web: { label: "Simple web app", beta: 0, stages: [
      { name: "Load balancer", a: 3, n: 2 }, { name: "App servers", a: 2, n: 3 }, { name: "Database", a: 3, n: 1 }] },
    ten: { label: "Ten hard dependencies", beta: 0, stages: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map(function (i) { return { name: "Dependency " + i, a: 2, n: 1 }; }) },
    pairs: { label: "Ten dependencies, all paired", beta: 0, stages: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map(function (i) { return { name: "Dependency " + i, a: 2, n: 2 }; }) },
    shared: { label: "Redundant but sharing a cause", beta: 0.2, stages: [
      { name: "Load balancer", a: 4, n: 2 }, { name: "App servers", a: 2, n: 3 }, { name: "Database", a: 3, n: 2 }] }
  };

  var stages = [], beta = 0, uid = 0;

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

  /* ---------- static frame ---------- */
  root.appendChild((function () {
    var h = el("div", { "class": "widget-head" });
    h.appendChild(el("span", { "class": "widget-tag" }, "Try it"));
    h.appendChild(el("h4", { "class": "widget-title" }, "Compose a system from nines"));
    return h;
  })());
  root.appendChild(el("p", { "class": "widget-help" },
    "Each row is a stage that every request must pass through (series). Replicas inside a stage are interchangeable (parallel). Try the presets, then raise the common-cause slider and watch redundancy stop paying."));

  var presetRow = el("div", { "class": "widget-row" });
  Object.keys(PRESETS).forEach(function (k) {
    var b = el("button", { type: "button", "class": "btn small", "data-preset": k }, PRESETS[k].label);
    b.addEventListener("click", function () { load(k); });
    presetRow.appendChild(b);
  });
  root.appendChild(presetRow);

  var list = el("div", { "class": "na-list" });
  root.appendChild(list);

  var ctlRow = el("div", { "class": "widget-row" });
  var addBtn = el("button", { type: "button", "class": "btn small primary" }, "+ Add stage");
  addBtn.addEventListener("click", function () {
    if (stages.length >= 12) return;
    stages.push({ id: ++uid, name: "Stage " + (stages.length + 1), a: 2, n: 1 });
    renderList(); update();
  });
  ctlRow.appendChild(addBtn);
  root.appendChild(ctlRow);

  var betaWrap = el("div", { "class": "na-beta" });
  var betaLab = el("label", { "for": "na-beta-in" });
  var betaOut = el("output", { "class": "na-out", "for": "na-beta-in" }, "0%");
  betaLab.appendChild(document.createTextNode("Common-cause share of failures (shared deploy, shared zone, shared bug): "));
  betaLab.appendChild(betaOut);
  var betaIn = el("input", { type: "range", id: "na-beta-in", min: "0", max: "50", step: "1", value: "0" });
  betaIn.addEventListener("input", function () { beta = parseInt(betaIn.value, 10) / 100; update(); });
  betaWrap.appendChild(betaLab); betaWrap.appendChild(betaIn);
  root.appendChild(betaWrap);

  var out = el("div", { "class": "widget-out", "aria-live": "polite" });
  root.appendChild(out);
  var chartWrap = el("div", { "class": "na-chart" });
  root.appendChild(chartWrap);

  /* ---------- rows ---------- */
  function renderList() {
    list.textContent = "";
    stages.forEach(function (s, i) {
      var row = el("div", { "class": "na-row" });
      var nameIn = el("input", { type: "text", maxlength: "24", "aria-label": "Stage " + (i + 1) + " name", value: s.name });
      nameIn.addEventListener("input", function () { s.name = nameIn.value; update(true); });
      var sel = el("select", { "aria-label": "Availability of one replica of " + s.name });
      LEVELS.forEach(function (lv, j) {
        var o = el("option", { value: String(j) }, parseFloat((lv * 100).toFixed(4)) + "%");
        if (j === s.a) o.selected = true;
        sel.appendChild(o);
      });
      sel.addEventListener("change", function () { s.a = parseInt(sel.value, 10); update(); });
      var nsel = el("select", { "aria-label": "Replicas of " + s.name });
      for (var n = 1; n <= 5; n++) {
        var o2 = el("option", { value: String(n) }, n + (n === 1 ? " replica" : " replicas"));
        if (n === s.n) o2.selected = true;
        nsel.appendChild(o2);
      }
      nsel.addEventListener("change", function () { s.n = parseInt(nsel.value, 10); update(); });
      var del = el("button", { type: "button", "class": "btn small danger", "aria-label": "Remove " + s.name }, "×");
      del.addEventListener("click", function () { stages.splice(i, 1); renderList(); update(); });
      row.appendChild(nameIn); row.appendChild(sel); row.appendChild(nsel); row.appendChild(del);
      list.appendChild(row);
    });
  }

  function load(key) {
    var p = PRESETS[key];
    stages = p.stages.map(function (s) { return { id: ++uid, name: s.name, a: s.a, n: s.n }; });
    beta = p.beta; betaIn.value = String(Math.round(beta * 100));
    renderList(); update();
  }

  /* ---------- output ---------- */
  function line(label, value) {
    var p = el("p", { "class": "na-line" });
    p.appendChild(el("span", { "class": "na-lab" }, label));
    p.appendChild(el("b", { "class": "na-val" }, value));
    return p;
  }

  function update() {
    betaOut.textContent = Math.round(beta * 100) + "%";
    var stgs = stages.map(function (s) { return { a: LEVELS[s.a], n: s.n }; });
    var res = chain(stgs, beta), ideal = chain(stgs, 0);
    out.textContent = "";
    if (!stages.length) { out.textContent = "Add a stage to begin."; chartWrap.textContent = ""; return; }
    var down = (1 - res.avail) * YEAR_MIN;
    out.appendChild(line("Whole chain", fmtPct(res.avail) + "  (" + nines(res.avail).toFixed(2) + " nines)"));
    out.appendChild(line("Downtime per year", fmtDuration(down)));
    out.appendChild(line("Per 30-day month", fmtDuration(down * 30 / 365)));
    out.appendChild(line("Per week", fmtDuration(down * 7 / 365)));
    if (beta > 0) out.appendChild(line("Without common cause", fmtPct(ideal.avail) + "  (" + fmtDuration((1 - ideal.avail) * YEAR_MIN) + " per year)"));
    drawChart(res);
  }

  function drawChart(res) {
    chartWrap.textContent = "";
    var rowH = 26, L = 150, R = 16, W = 700, H = 40 + rowH * stages.length;
    var svg = sv("svg", { viewBox: "0 0 " + W + " " + H, role: "img", "aria-label": "Share of total downtime contributed by each stage" });
    var total = res.parts.reduce(function (a, b) { return a + b; }, 0) || 1;
    var maxShare = Math.max.apply(null, res.parts) / total;
    svg.appendChild(sv("text", { x: 0, y: 16, "class": "t-xs t-muted" }, "Share of the chain's unavailability, by stage"));
    var worst = res.parts.indexOf(Math.max.apply(null, res.parts));
    stages.forEach(function (s, i) {
      var y = 28 + i * rowH, share = res.parts[i] / total, w = (W - L - R - 50) * (share / (maxShare || 1));
      var name = s.name.length > 20 ? s.name.slice(0, 19) + "…" : s.name;
      svg.appendChild(sv("text", { x: L - 8, y: y + 14, "text-anchor": "end", "class": "t-xs t-muted" }, name));
      svg.appendChild(sv("rect", { x: L, y: y + 2, width: Math.max(1, w).toFixed(1), height: 16, rx: 3, "class": i === worst ? "f-red" : "f-blue" }));
      svg.appendChild(sv("text", { x: L + Math.max(1, w) + 6, y: y + 14, "class": "t-xs t-faint" }, (share * 100).toFixed(share < 0.1 ? 1 : 0) + "%"));
    });
    chartWrap.appendChild(svg);
  }

  load("web");
})();
