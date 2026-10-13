/* Error-budget simulator (reliability chapter 2).
   A 30-day rolling window of uniform traffic. Each minute has a "bad fraction": a steady background
   (expressed as a burn rate, so 1.0 means spending the budget exactly as fast as the window allows)
   plus any incidents that cover that minute. The budget is (1 - SLO) of all minutes' worth of
   requests, and we track how much of it is spent. Burn rate over an hour = bad fraction / (1 - SLO). */
(function () {
  "use strict";

  var DAYS = 30, MIN = DAYS * 1440;

  /* pure model: returns {perMin, cum, total, hourBurn, remaining} */
  function model(slo, bgBurn, incidents) {
    var allowed = 1 - slo, bad = new Float64Array(MIN);
    var i, m;
    for (m = 0; m < MIN; m++) bad[m] = bgBurn * allowed;
    incidents.forEach(function (inc) {
      var s = Math.round((inc.day - 1) * 1440 + (inc.startHour || 0) * 60), e = Math.min(MIN, s + inc.dur);
      for (m = Math.max(0, s); m < e; m++) bad[m] = Math.min(1, bad[m] + inc.rate);
    });
    var total = allowed * MIN, cum = new Float64Array(MIN + 1);
    for (m = 0; m < MIN; m++) cum[m + 1] = cum[m] + bad[m];
    var hourBurn = [];
    for (var h = 0; h < DAYS * 24; h++) {
      var sum = 0;
      for (i = 0; i < 60; i++) sum += bad[h * 60 + i];
      hourBurn.push(sum / 60 / allowed);
    }
    return { bad: bad, cum: cum, total: total, hourBurn: hourBurn, allowed: allowed };
  }

  var core = { model: model };
  if (typeof module !== "undefined" && module.exports) module.exports = core;

  if (typeof document === "undefined") return;
  var root = document.getElementById("error-budget");
  if (!root) return;

  var NS = "http://www.w3.org/2000/svg";
  var SLOS = [0.99, 0.995, 0.999, 0.9995, 0.9999];
  var PRESET = [
    { name: "Bad deploy, rolled back", day: 6, startHour: 10, dur: 30, rate: 0.4 },
    { name: "Dependency blip", day: 12, startHour: 2, dur: 10, rate: 0.9 },
    { name: "Slow database, partial errors", day: 18, startHour: 14, dur: 120, rate: 0.15 },
    { name: "Full outage", day: 25, startHour: 9, dur: 240, rate: 1 }
  ];
  var state = { slo: 2, bg: 0.3, incs: PRESET.map(function (p, i) { return { id: i, name: p.name, day: p.day, startHour: p.startHour, dur: p.dur, rate: p.rate, on: i < 2 }; }) };
  var nextId = 100;

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

  /* ---------- frame ---------- */
  var head = el("div", { "class": "widget-head" });
  head.appendChild(el("span", { "class": "widget-tag" }, "Try it"));
  head.appendChild(el("h4", { "class": "widget-title" }, "Spend a 30-day error budget"));
  root.appendChild(head);
  root.appendChild(el("p", { "class": "widget-help" },
    "Pick an SLO, then switch incidents on and off or add your own. The top chart is the budget left in the window; the bottom chart is the hourly burn rate on a log-style scale."));

  var ctl = el("div", { "class": "eb-ctl" });
  var sloWrap = el("div"); sloWrap.appendChild(el("label", { "for": "eb-slo" }, "SLO target"));
  var sloSel = el("select", { id: "eb-slo" });
  SLOS.forEach(function (s, i) { var o = el("option", { value: String(i) }, parseFloat((s * 100).toFixed(4)) + "%"); if (i === state.slo) o.selected = true; sloSel.appendChild(o); });
  sloWrap.appendChild(sloSel);
  var bgWrap = el("div");
  var bgLab = el("label", { "for": "eb-bg" }, "Background burn rate: ");
  var bgOut = el("output", { "class": "eb-mono", "for": "eb-bg" }, "0.3");
  bgLab.appendChild(bgOut);
  var bgIn = el("input", { type: "range", id: "eb-bg", min: "0", max: "20", step: "1", value: "3" });
  bgWrap.appendChild(bgLab); bgWrap.appendChild(bgIn);
  ctl.appendChild(sloWrap); ctl.appendChild(bgWrap);
  root.appendChild(ctl);

  var incList = el("div", { "class": "eb-incs" });
  root.appendChild(incList);

  var addRow = el("div", { "class": "eb-add" });
  function numField(id, label, min, max, val) {
    var w = el("div"); w.appendChild(el("label", { "for": id }, label));
    var i = el("input", { type: "number", id: id, min: String(min), max: String(max), value: String(val) });
    w.appendChild(i); addRow.appendChild(w); return i;
  }
  var inDay = numField("eb-day", "Day (1-30)", 1, 30, 9);
  var inDur = numField("eb-dur", "Minutes", 1, 1440, 45);
  var inRate = numField("eb-rate", "% failing", 1, 100, 50);
  var addBtn = el("button", { type: "button", "class": "btn small primary" }, "+ Add incident");
  addBtn.addEventListener("click", function () {
    function clamp(v, lo, hi, d) { v = parseFloat(v); return isNaN(v) ? d : Math.max(lo, Math.min(hi, v)); }
    if (state.incs.length >= 12) return;
    state.incs.push({ id: nextId++, name: "Custom incident", day: Math.round(clamp(inDay.value, 1, 30, 9)), startHour: 12,
      dur: Math.round(clamp(inDur.value, 1, 1440, 45)), rate: clamp(inRate.value, 1, 100, 50) / 100, on: true });
    renderIncs(); update();
  });
  addRow.appendChild(addBtn);
  root.appendChild(addRow);

  var verdict = el("p", { "class": "eb-verdict", "aria-live": "polite" });
  root.appendChild(verdict);
  var stats = el("div", { "class": "eb-stats" });
  root.appendChild(stats);
  var chart = el("div", { "class": "eb-chart" });
  root.appendChild(chart);

  sloSel.addEventListener("change", function () { state.slo = parseInt(sloSel.value, 10); update(); });
  bgIn.addEventListener("input", function () { state.bg = parseInt(bgIn.value, 10) / 10; update(); });

  function renderIncs() {
    incList.textContent = "";
    state.incs.forEach(function (inc, idx) {
      var row = el("div", { "class": "eb-inc" });
      var cb = el("input", { type: "checkbox", id: "eb-i" + inc.id });
      cb.checked = inc.on;
      cb.addEventListener("change", function () { inc.on = cb.checked; update(); });
      var lab = el("label", { "for": "eb-i" + inc.id });
      lab.textContent = inc.name + ": day " + inc.day + ", " + inc.dur + " min, " + Math.round(inc.rate * 100) + "% failing";
      row.appendChild(cb); row.appendChild(lab);
      if (inc.id >= 100) {
        var del = el("button", { type: "button", "class": "btn small danger", "aria-label": "Remove incident" }, "×");
        del.addEventListener("click", function () { state.incs.splice(idx, 1); renderIncs(); update(); });
        row.appendChild(del);
      }
      incList.appendChild(row);
    });
  }

  function fmtMin(m) {
    if (m < 1) return (m * 60).toFixed(0) + " s";
    if (m < 120) return m.toFixed(m < 10 ? 1 : 0) + " min";
    return (m / 60).toFixed(1) + " h";
  }

  function stat(label, value) {
    var d = el("div", { "class": "eb-stat" });
    d.appendChild(el("small", {}, label)); d.appendChild(el("b", {}, value));
    return d;
  }

  function update() {
    var slo = SLOS[state.slo];
    bgOut.textContent = state.bg.toFixed(1);
    var res = model(slo, state.bg, state.incs.filter(function (i) { return i.on; }));
    var used = res.cum[MIN] / res.total, left = 1 - used;
    var fullMin = res.allowed * MIN;
    stats.textContent = "";
    stats.appendChild(stat("Budget for the window", fmtMin(fullMin) + " of full outage"));
    stats.appendChild(stat("Spent", Math.round(used * 100) + "%"));
    stats.appendChild(stat("Remaining", (left >= 0 ? fmtMin(left * fullMin) : "overspent by " + fmtMin(-left * fullMin))));
    var peak = Math.max.apply(null, res.hourBurn);
    stats.appendChild(stat("Peak hourly burn", peak.toFixed(peak < 10 ? 1 : 0) + "x"));

    var cls, msg;
    if (left <= 0) { cls = "bad"; msg = "Budget exhausted. Policy: freeze feature releases; only reliability and security fixes ship until the window recovers."; }
    else if (left < 0.25) { cls = "bad"; msg = "Under 25% left. Policy: freeze risky changes, prioritise reliability work."; }
    else if (left < 0.5) { cls = "warn"; msg = "Under half left. Policy: caution, slower rollouts, review the causes of recent burn."; }
    else { cls = "ok"; msg = "Plenty left. Policy: ship normally, and consider spending budget on experiments or risky migrations."; }
    verdict.className = "eb-verdict " + cls;
    verdict.textContent = msg;
    draw(res, left);
  }

  /* ---------- charts ---------- */
  function draw(res, finalLeft) {
    chart.textContent = "";
    var W = 700, H = 380, L = 52, R = 14;
    var svg = sv("svg", { viewBox: "0 0 " + W + " " + H, role: "img", "aria-label": "Error budget remaining over 30 days, and hourly burn rate" });
    var pw = W - L - R;
    function X(day) { return L + pw * day / DAYS; }

    /* --- budget remaining --- */
    var T1 = 22, B1 = 170, ph1 = B1 - T1;
    var pts = [], minRem = 1;
    for (var h = 0; h <= DAYS * 24; h++) {
      var r = 1 - res.cum[h * 60] / res.total;
      pts.push(r); if (r < minRem) minRem = r;
    }
    var yMin = Math.min(-0.25, Math.max(minRem, -2)), yMax = 1;
    function Y1(v) { v = Math.max(yMin, v); return B1 - ph1 * (v - yMin) / (yMax - yMin); }
    svg.appendChild(sv("text", { x: 0, y: 12, "class": "t-xs t-muted" }, "Budget remaining (% of window)"));
    [1, 0.5, 0].forEach(function (v) {
      svg.appendChild(sv("line", { x1: L, y1: Y1(v), x2: W - R, y2: Y1(v), "class": v === 0 ? "line-dash s-red" : "line-thin" }));
      svg.appendChild(sv("text", { x: L - 6, y: Y1(v) + 4, "text-anchor": "end", "class": "t-xs t-faint" }, Math.round(v * 100) + "%"));
    });
    if (yMin < -0.3) {
      svg.appendChild(sv("text", { x: L - 6, y: Y1(yMin) + 4, "text-anchor": "end", "class": "t-xs t-faint" }, Math.round(yMin * 100) + "%"));
    }
    var d = "";
    pts.forEach(function (v, i) { d += (i ? "L" : "M") + X(i / 24).toFixed(1) + "," + Y1(v).toFixed(1); });
    svg.appendChild(sv("path", { d: d, fill: "none", "class": finalLeft < 0 ? "s-red sw-2" : "s-green sw-2" }));
    svg.appendChild(sv("text", { x: W - R, y: Y1(0) - 5, "text-anchor": "end", "class": "t-xs tc-red" }, "budget gone"));

    /* --- burn rate (log-style: y = log10(1 + burn)) --- */
    var T2 = 214, B2 = 340, ph2 = B2 - T2, top = 3;
    function Y2(b) { return B2 - ph2 * Math.min(top, Math.log10(1 + b)) / top; }
    svg.appendChild(sv("text", { x: 0, y: 204, "class": "t-xs t-muted" }, "Hourly burn rate (1x = sustainable pace)"));
    [0, 1, 10, 100, 1000].forEach(function (v) {
      var y = Y2(v);
      svg.appendChild(sv("line", { x1: L, y1: y, x2: W - R, y2: y, "class": "line-thin" }));
      svg.appendChild(sv("text", { x: L - 6, y: y + 4, "text-anchor": "end", "class": "t-xs t-faint" }, v + "x"));
    });
    svg.appendChild(sv("line", { x1: L, y1: Y2(1), x2: W - R, y2: Y2(1), "class": "line-dash s-green" }));
    svg.appendChild(sv("line", { x1: L, y1: Y2(14.4), x2: W - R, y2: Y2(14.4), "class": "line-dash s-yellow" }));
    svg.appendChild(sv("text", { x: W - R - 2, y: Y2(14.4) - 4, "text-anchor": "end", "class": "t-xs tc-yellow" }, "14.4x: 2% of budget gone in an hour"));
    var bw = pw / (DAYS * 24);
    res.hourBurn.forEach(function (b, i) {
      if (b < 0.02) return;
      var y = Y2(b);
      svg.appendChild(sv("rect", { x: (L + i * bw).toFixed(2), y: y.toFixed(1), width: Math.max(1, bw).toFixed(2), height: Math.max(1, B2 - y).toFixed(1), "class": b >= 14.4 ? "f-red" : (b > 1 ? "f-yellow" : "f-blue") }));
    });

    /* shared x axis */
    [0, 5, 10, 15, 20, 25, 30].forEach(function (dd) {
      svg.appendChild(sv("text", { x: X(dd), y: B2 + 16, "text-anchor": "middle", "class": "t-xs t-faint" }, String(dd)));
    });
    svg.appendChild(sv("text", { x: L + pw / 2, y: H - 6, "text-anchor": "middle", "class": "t-xs t-muted" }, "days into the window →"));
    chart.appendChild(svg);
  }

  renderIncs();
  update();
})();
