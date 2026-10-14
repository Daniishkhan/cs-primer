/* Context-budget simulator (agents chapter 10).
   An agent loop appends an assistant message and a tool result each turn. Three policies are compared on the same
   seeded run: keep everything, clear old tool results once a trigger size is passed, or compact the history into a
   summary at the trigger. ALL sizes are illustrative assumptions, not measurements of any model. */
(function () {
  "use strict";

  var SYSTEM = 3000, ASSISTANT = 200, STUB = 25, SUMMARY = 1500;

  function mulberry32(a) {
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      var t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  function sum(list) { var s = 0, i; for (i = 0; i < list.length; i++) s += list[i].n; return s; }

  /* o: { turns, avg, trigger, keep, strategy, seed } -> { sizes, events, peak, total } */
  function simulate(o) {
    var rnd = mulberry32(o.seed || 7), ctx = [{ k: "sys", n: SYSTEM }], sizes = [], events = [], total = 0, peak = 0, t, i, size, r, idx;
    for (t = 0; t < o.turns; t++) {
      r = Math.round(o.avg * (0.4 + 1.2 * rnd()));
      ctx.push({ k: "a", n: ASSISTANT });
      ctx.push({ k: "r", n: r });
      size = sum(ctx);
      if (size > o.trigger && o.strategy === "clear") {
        idx = [];
        for (i = 0; i < ctx.length; i++) if (ctx[i].k === "r") idx.push(i);
        for (i = 0; i < idx.length - o.keep; i++) ctx[idx[i]] = { k: "s", n: STUB };
        events.push(t);
      } else if (size > o.trigger && o.strategy === "compact") {
        ctx = [ctx[0], { k: "m", n: SUMMARY }].concat(ctx.slice(-2 * Math.min(o.keep, 2)));
        events.push(t);
      }
      size = sum(ctx);
      sizes.push(size);
      total += size;
      if (size > peak) peak = size;
    }
    return { sizes: sizes, events: events, peak: peak, total: total };
  }

  var core = { simulate: simulate };
  if (typeof module !== "undefined" && module.exports) module.exports = core;
  if (typeof document === "undefined") return;
  var root = document.getElementById("agt10-budget");
  if (!root) return;

  var NS = "http://www.w3.org/2000/svg";
  function el(tag, attrs, text) {
    var e = document.createElement(tag), k;
    for (k in attrs) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    return e;
  }
  function sv(tag, attrs, text) {
    var e = document.createElementNS(NS, tag), k;
    for (k in attrs) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    return e;
  }
  function fmt(x) { return Math.round(x).toLocaleString("en-GB"); }

  var state = { turns: 40, avg: 1800, trigger: 40000, keep: 4, ceiling: 30000, strategy: "clear" };
  var outs = {};

  var head = el("div", { "class": "widget-head" });
  head.appendChild(el("span", { "class": "widget-tag" }, "Try it"));
  head.appendChild(el("h4", { "class": "widget-title" }, "How fast does an agent fill its window?"));
  root.appendChild(head);
  root.appendChild(el("p", { "class": "widget-help" },
    "Each turn adds a short assistant message and a tool result. Pick a policy and move the sliders. The blue line is the context " +
    "sent on each call; the orange dashed line is the trigger that fires clearing or compaction; the yellow dashed line is a " +
    "working ceiling you choose, above which you would not trust quality. All sizes are assumptions."));

  var ctl = el("div", { "class": "ag10-ctl" });
  function slider(key, label, min, max, step, show) {
    var w = el("div"), lab = el("label", { "for": "agt10-" + key }, label + ": "), out = el("output", {});
    var inp = el("input", { type: "range", id: "agt10-" + key, min: min, max: max, step: step, value: state[key] });
    lab.appendChild(out);
    inp.addEventListener("input", function () { state[key] = parseFloat(inp.value); update(); });
    w.appendChild(lab); w.appendChild(inp); ctl.appendChild(w);
    outs[key] = { el: out, show: show };
  }
  var sw = el("div");
  sw.appendChild(el("label", { "for": "agt10-strategy" }, "Policy: "));
  var sel = el("select", { id: "agt10-strategy" });
  [["none", "keep everything"], ["clear", "clear old tool results"], ["compact", "compact into a summary"]].forEach(function (p) {
    sel.appendChild(el("option", { value: p[0] }, p[1]));
  });
  sel.value = state.strategy;
  sel.addEventListener("change", function () { state.strategy = sel.value; update(); });
  sw.appendChild(sel); ctl.appendChild(sw);
  slider("turns", "Turns", 5, 80, 1, fmt);
  slider("avg", "Average tool result (tokens)", 300, 4000, 100, fmt);
  slider("trigger", "Trigger size (tokens)", 10000, 120000, 5000, fmt);
  slider("keep", "Recent results kept", 1, 8, 1, fmt);
  slider("ceiling", "Working ceiling (tokens)", 10000, 100000, 5000, fmt);
  root.appendChild(ctl);

  var svg = sv("svg", { "class": "ag10-chart", role: "img", viewBox: "0 0 700 240", "aria-label": "Line chart of context size sent on each turn of an agent loop, with a trigger line and a working ceiling line." });
  root.appendChild(svg);
  var out = el("div", { "class": "widget-out", "aria-live": "polite" });
  root.appendChild(out);

  function update() {
    var k, i, r = simulate({ turns: state.turns, avg: state.avg, trigger: state.trigger, keep: state.keep, strategy: state.strategy, seed: 7 });
    for (k in outs) outs[k].el.textContent = outs[k].show(state[k]);
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    var W = 700, H = 240, L = 54, R = 12, T = 14, B = 36, pw = W - L - R, ph = H - T - B;
    var maxY = Math.max(r.peak, state.trigger, state.ceiling) * 1.1;
    function X(t) { return L + pw * (state.turns === 1 ? 0 : t / (state.turns - 1)); }
    function Y(v) { return T + ph - ph * v / maxY; }
    svg.appendChild(sv("line", { x1: L, y1: T + ph, x2: W - R, y2: T + ph, "class": "line-thin" }));
    svg.appendChild(sv("line", { x1: L, y1: T, x2: L, y2: T + ph, "class": "line-thin" }));
    [0, 0.5, 1].forEach(function (f) {
      svg.appendChild(sv("text", { x: L - 6, y: Y(maxY / 1.1 * f) + 4, "text-anchor": "end", "class": "t-xs t-faint" }, fmt(maxY / 1.1 * f / 1000) + "k"));
    });
    svg.appendChild(sv("line", { x1: L, y1: Y(state.trigger), x2: W - R, y2: Y(state.trigger), "class": "line-dash s-orange" }));
    svg.appendChild(sv("text", { x: W - R - 4, y: Y(state.trigger) - 4, "text-anchor": "end", "class": "t-xs tc-orange" }, "trigger"));
    svg.appendChild(sv("line", { x1: L, y1: Y(state.ceiling), x2: W - R, y2: Y(state.ceiling), "class": "line-dash s-yellow" }));
    svg.appendChild(sv("text", { x: L + 4, y: Y(state.ceiling) - 4, "class": "t-xs tc-yellow" }, "working ceiling"));
    var pts = [];
    for (i = 0; i < r.sizes.length; i++) pts.push(X(i).toFixed(1) + "," + Y(r.sizes[i]).toFixed(1));
    svg.appendChild(sv("polyline", { points: pts.join(" "), fill: "none", "class": "s-blue sw-2" }));
    r.events.forEach(function (t) { svg.appendChild(sv("circle", { cx: X(t).toFixed(1), cy: Y(r.sizes[t]).toFixed(1), r: 4, "class": "f-orange" })); });
    svg.appendChild(sv("text", { x: L + pw / 2, y: H - 8, "text-anchor": "middle", "class": "t-xs t-muted" }, "turn (model call) number; orange dots mark a clear or compaction"));
    var above = r.sizes.filter(function (v) { return v > state.ceiling; }).length;
    out.textContent = "";
    [
      "Peak context sent: " + fmt(r.peak) + " tokens. Total input tokens over " + state.turns + " calls: " + fmt(r.total) + " (before any prompt-cache discount).",
      state.strategy === "none" ? "No policy: nothing is ever removed." : (r.events.length + " " + (state.strategy === "clear" ? "clearing" : "compaction") + " event(s)."),
      above ? above + " of " + state.turns + " calls are above your working ceiling." : "No call is above your working ceiling."
    ].forEach(function (t) { out.appendChild(el("p", { style: "margin:4px 0" }, t)); });
  }
  update();
})();
