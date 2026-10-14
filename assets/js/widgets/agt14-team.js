/* One agent or a team? (agents chapter 14)
   Reproduces the arithmetic of the chapter's tokens.py. Every default is an ILLUSTRATIVE assumption.
   One agent: a loop of W+1 model calls; call k re-sends the system prompt and k-1 steps of history.
   Team: a lead plans (1 call), n sub-agents each run their own short loop in a fresh context, the lead
   synthesises (1 call) from n summaries. Prompt caching and output tokens are ignored on purpose. */
(function () {
  "use strict";

  function loop(steps, sys, per) {
    var total = 0, k;
    for (k = 1; k <= steps; k++) total += sys + (k - 1) * per;
    return { total: total, peak: sys + (steps - 1) * per };
  }

  function model(o) {
    var one = loop(o.work + 1, o.sys, o.per);
    var each = Math.round(o.work * o.breadth / o.n * (1 + o.dup));
    var sub = loop(each + 1, o.sys, o.per);
    var plan = o.sys + 500, synth = o.sys + 500 + o.n * o.summary;
    var team = plan + o.n * sub.total + synth;
    return {
      oneTotal: one.total, onePeak: one.peak, oneSec: (o.work + 1) * o.sec,
      teamTotal: team, teamPeak: Math.max(sub.peak, synth), teamSec: (2 + each + 1) * o.sec,
      perAgentSteps: each, allReport: Math.pow(o.rel, o.n)
    };
  }

  var core = { model: model };
  if (typeof module !== "undefined" && module.exports) module.exports = core;
  if (typeof document === "undefined") return;
  var root = document.getElementById("agt14-team");
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
  function fmt(x) { return Math.round(x).toLocaleString("en-GB"); }

  var state = { work: 30, n: 5, dup: 0, breadth: 1, sys: 3000, per: 1500, summary: 1500, price: 3, rel: 0.95, sec: 4 };
  var outs = {};

  var head = el("div", { "class": "widget-head" });
  head.appendChild(el("span", { "class": "widget-tag" }, "Try it"));
  head.appendChild(el("h4", { "class": "widget-title" }, "One agent or a team: what changes?"));
  root.appendChild(head);
  root.appendChild(el("p", { "class": "widget-help" },
    "A long loop re-reads its whole history on every call, so splitting independent work across short loops can cut tokens. Duplicated work and extra searching push the other way. " +
    "Set the numbers for your task. All values are assumptions, and caching is ignored."));

  var ctl = el("div", { "class": "ag14-ctl" });
  function slider(key, label, min, max, step, show) {
    var w = el("div");
    var lab = el("label", { "for": "agt14-" + key }, label + ": ");
    var out = el("output", { id: "agt14-" + key + "-out" });
    lab.appendChild(out);
    var inp = el("input", { type: "range", id: "agt14-" + key, min: min, max: max, step: step, value: state[key] });
    inp.addEventListener("input", function () { state[key] = parseFloat(inp.value); update(); });
    w.appendChild(lab); w.appendChild(inp); ctl.appendChild(w);
    outs[key] = { el: out, show: show };
  }
  var pct = function (v) { return (v * 100).toFixed(0) + "%"; };
  slider("work", "Tool calls the job needs", 6, 80, 2, String);
  slider("n", "Sub-agents", 1, 12, 1, String);
  slider("dup", "Duplicated work", 0, 1, 0.1, pct);
  slider("breadth", "Extra searching (x)", 1, 5, 0.5, function (v) { return v.toFixed(1) + "x"; });
  slider("sys", "System prompt + tool schemas (tokens)", 500, 12000, 500, fmt);
  slider("per", "History added per step (tokens)", 200, 4000, 100, fmt);
  slider("summary", "Summary each sub-agent returns (tokens)", 200, 4000, 100, fmt);
  slider("rel", "Chance one sub-agent finishes", 0.7, 1, 0.01, pct);
  slider("price", "Input price ($ per million)", 0.25, 15, 0.25, function (v) { return "$" + v.toFixed(2); });
  root.appendChild(ctl);

  var svg = sv("svg", { "class": "ag14-chart", role: "img", viewBox: "0 0 700 150", "aria-label": "Two bars compare total input tokens for one agent and for a team, and two thinner bars compare their largest single context." });
  root.appendChild(svg);
  var out = el("div", { "class": "widget-out", "aria-live": "polite" });
  root.appendChild(out);

  function bar(y, label, value, max, cls, note) {
    var x0 = 150, w = 520 * value / max;
    svg.appendChild(sv("text", { x: x0 - 8, y: y + 14, "text-anchor": "end", "class": "t-xs t-muted" }, label));
    svg.appendChild(sv("rect", { x: x0, y: y, width: Math.max(2, w).toFixed(1), height: 20, rx: 3, "class": cls }));
    svg.appendChild(sv("text", { x: Math.min(x0 + w + 6, 560), y: y + 14, "class": "t-xs" }, note));
  }

  function update() {
    var k, r = model(state);
    for (k in outs) outs[k].el.textContent = outs[k].show(state[k]);
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    var maxT = Math.max(r.oneTotal, r.teamTotal), maxP = Math.max(r.onePeak, r.teamPeak);
    bar(8, "one agent, total", r.oneTotal, maxT, "f-blue", fmt(r.oneTotal));
    bar(36, "team, total", r.teamTotal, maxT, "f-orange", fmt(r.teamTotal));
    bar(84, "one agent, peak", r.onePeak, maxP, "f-blue", fmt(r.onePeak));
    bar(112, "team, peak", r.teamPeak, maxP, "f-orange", fmt(r.teamPeak));
    out.textContent = "";
    var ratio = r.teamTotal / r.oneTotal;
    [ "Input tokens: team " + fmt(r.teamTotal) + " against " + fmt(r.oneTotal) + " for one agent (" + ratio.toFixed(2) + "x). At the chosen price: $" + (r.teamTotal * state.price / 1e6).toFixed(2) + " against $" + (r.oneTotal * state.price / 1e6).toFixed(2) + ".",
      "Largest single context: " + fmt(r.teamPeak) + " against " + fmt(r.onePeak) + " tokens. Waiting time on the critical path: about " + r.teamSec + " s against " + r.oneSec + " s.",
      "Each sub-agent runs about " + r.perAgentSteps + " tool calls. Chance that all " + state.n + " finish: " + (r.allReport * 100).toFixed(1) + "%, so the lead must handle a missing report."
    ].forEach(function (t) { out.appendChild(el("p", { style: "margin:4px 0" }, t)); });
  }
  update();
})();
