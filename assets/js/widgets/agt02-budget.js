/* Agent-loop budget explorer (agents chapter 02).
   Every iteration re-sends the whole conversation, so input tokens per call grow linearly and the total grows
   quadratically with the number of iterations. Separately, if each step succeeds independently with probability p,
   an n-step task succeeds with p^n. ALL defaults are illustrative assumptions, not measurements.
   Caching model (assumption, modelled on typical published prompt-caching prices): the previous call's context is
   read at 0.1x the input price; new tokens are written at 1.25x. */
(function () {
  "use strict";

  function model(o) {
    var perCall = [], total = 0, billed = 0, k, ctx, prev = 0;
    for (k = 1; k <= o.n; k++) {
      ctx = o.base + (k - 1) * o.delta;
      perCall.push(ctx);
      total += ctx;
      if (o.cache) {
        billed += (k === 1) ? ctx * 1.25 : prev * 0.1 + (ctx - prev) * 1.25;
      } else {
        billed += ctx;
      }
      prev = ctx;
    }
    return {
      perCall: perCall, total: total, billed: billed,
      cost: billed * o.price / 1e6,
      last: perCall[perCall.length - 1],
      success: Math.pow(o.p, o.n)
    };
  }

  var core = { model: model };
  if (typeof module !== "undefined" && module.exports) module.exports = core;
  if (typeof document === "undefined") return;
  var root = document.getElementById("agt02-budget");
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

  var state = { n: 10, base: 2000, delta: 700, p: 0.97, price: 3, cache: "off", limit: 32000 };
  var inputs = {}, outs = {};

  var head = el("div", { "class": "widget-head" });
  head.appendChild(el("span", { "class": "widget-tag" }, "Try it"));
  head.appendChild(el("h4", { "class": "widget-title" }, "What does one more iteration cost?"));
  root.appendChild(head);
  root.appendChild(el("p", { "class": "widget-help" },
    "Each bar is the input a single model call sends: system prompt and tool schemas, plus everything said so far. " +
    "Move the sliders and watch the total grow faster than the number of iterations, while the chance that every step works shrinks. " +
    "All numbers are assumptions you can change."));

  var ctl = el("div", { "class": "ag02-ctl" });
  function slider(key, label, min, max, step, show) {
    var w = el("div");
    var lab = el("label", { "for": "agt02-" + key }, label + ": ");
    var out = el("output", { "id": "agt02-" + key + "-out" });
    lab.appendChild(out);
    var inp = el("input", { type: "range", id: "agt02-" + key, min: min, max: max, step: step, value: state[key] });
    inp.addEventListener("input", function () { state[key] = parseFloat(inp.value); update(); });
    w.appendChild(lab); w.appendChild(inp); ctl.appendChild(w);
    inputs[key] = inp; outs[key] = { el: out, show: show };
  }
  slider("n", "Iterations", 1, 40, 1, function (v) { return String(v); });
  slider("base", "Fixed prompt (tokens)", 500, 10000, 250, fmt);
  slider("delta", "Added per iteration (tokens)", 100, 3000, 100, fmt);
  slider("p", "Chance one step works", 0.8, 1, 0.005, function (v) { return (v * 100).toFixed(1) + "%"; });
  slider("price", "Input price ($ per million)", 0.25, 15, 0.25, function (v) { return "$" + v.toFixed(2); });
  var cw = el("div");
  cw.appendChild(el("label", { "for": "agt02-cache" }, "Prefix caching: "));
  var sel = el("select", { id: "agt02-cache" });
  sel.appendChild(el("option", { value: "off" }, "off"));
  sel.appendChild(el("option", { value: "on" }, "on (reads at 0.1x, writes at 1.25x)"));
  sel.addEventListener("change", function () { state.cache = sel.value; update(); });
  cw.appendChild(sel); ctl.appendChild(cw);
  root.appendChild(ctl);

  var svg = sv("svg", { "class": "ag02-chart", role: "img", viewBox: "0 0 700 220", "aria-label": "Bar chart of input tokens sent on each iteration of an agent loop, with a dashed line for a context limit." });
  root.appendChild(svg);
  var out = el("div", { "class": "widget-out", "aria-live": "polite" });
  root.appendChild(out);

  function update() {
    var r = model({ n: state.n, base: state.base, delta: state.delta, p: state.p, price: state.price, cache: state.cache === "on" });
    for (var k in outs) outs[k].el.textContent = outs[k].show(state[k]);
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    var W = 700, H = 220, L = 52, R = 10, T = 14, B = 34, pw = W - L - R, ph = H - T - B;
    var maxY = Math.max(r.last, state.limit) * 1.08, bw = pw / state.n;
    svg.appendChild(sv("line", { x1: L, y1: T + ph, x2: W - R, y2: T + ph, "class": "line-thin" }));
    svg.appendChild(sv("line", { x1: L, y1: T, x2: L, y2: T + ph, "class": "line-thin" }));
    [0, 0.5, 1].forEach(function (f) {
      svg.appendChild(sv("text", { x: L - 6, y: T + ph - ph * f + 4, "text-anchor": "end", "class": "t-xs t-faint" }, fmt(maxY * f / 1.08 / 1000) + "k"));
    });
    for (var i = 0; i < r.perCall.length; i++) {
      var h = ph * r.perCall[i] / maxY;
      svg.appendChild(sv("rect", { x: (L + i * bw + 1).toFixed(1), y: (T + ph - h).toFixed(1), width: Math.max(1, bw - 2).toFixed(1), height: h.toFixed(1), "class": r.perCall[i] > state.limit ? "f-red" : "f-blue" }));
    }
    var ly = T + ph - ph * state.limit / maxY;
    svg.appendChild(sv("line", { x1: L, y1: ly, x2: W - R, y2: ly, "class": "line-dash s-orange" }));
    svg.appendChild(sv("text", { x: W - R - 4, y: ly - 5, "text-anchor": "end", "class": "t-xs tc-orange t-bold" }, "assumed context limit: " + fmt(state.limit) + " tokens"));
    svg.appendChild(sv("text", { x: L + pw / 2, y: H - 6, "text-anchor": "middle", "class": "t-xs t-muted" }, "iteration (model call) number"));
    var over = r.perCall.filter(function (v) { return v > state.limit; }).length;
    out.textContent = "";
    var lines = [
      "Total input tokens sent: " + fmt(r.total) + " (the last call alone sends " + fmt(r.last) + ").",
      "Billed-equivalent input tokens: " + fmt(r.billed) + (state.cache === "on" ? " with caching." : " with no caching.") + " Cost at the chosen price: $" + r.cost.toFixed(3) + ".",
      "Chance all " + state.n + " steps succeed: " + (r.success * 100).toFixed(1) + "% (p to the power n).",
      over ? over + " call(s) exceed the assumed context limit (red): the loop needs compaction before then." : "No call exceeds the assumed context limit."
    ];
    lines.forEach(function (t) { out.appendChild(el("p", { style: "margin:4px 0" }, t)); });
  }
  update();
})();
