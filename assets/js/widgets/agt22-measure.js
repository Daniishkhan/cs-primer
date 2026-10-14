/* How many tasks does it take to see whether an AI tool helps? (agents chapter 22)
   A normal-approximation model of a comparison of log task times between two arms.
   delta = ln(time ratio) = -ln(1 + speedup). SE = sigma * sqrt(2 (1 - rho) / n), where rho is the
   correlation between matched tasks (0 = unmatched arms, high = good pairing).
   Every default is an ILLUSTRATIVE assumption, not a measurement of any tool. */
(function () {
  "use strict";

  function erf(x) {
    var s = x < 0 ? -1 : 1, t;
    x = Math.abs(x);
    t = 1 / (1 + 0.3275911 * x);
    return s * (1 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * Math.exp(-x * x));
  }
  function cdf(z) { return 0.5 * (1 + erf(z / Math.SQRT2)); }

  function model(o) {
    var delta = -Math.log(1 + o.speed / 100);
    var se = o.sigma * Math.sqrt(2 * (1 - o.rho) / o.n);
    var power = delta === 0 ? 0.05 : cdf(Math.abs(delta) / se - 1.96) + cdf(-Math.abs(delta) / se - 1.96);
    var need = delta === 0 ? Infinity : Math.ceil(2 * o.sigma * o.sigma * (1 - o.rho) * Math.pow(1.96 + 0.8416, 2) / (delta * delta));
    return { delta: delta, se: se, lo: Math.exp(delta - 1.96 * se), mid: Math.exp(delta), hi: Math.exp(delta + 1.96 * se), power: power, need: need };
  }

  var core = { model: model };
  if (typeof module !== "undefined" && module.exports) module.exports = core;
  if (typeof document === "undefined") return;
  var root = document.getElementById("agt22-measure");
  if (!root) return;

  function mulberry32(a) {
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      var t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
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

  var state = { speed: 10, sigma: 0.7, n: 30, rho: 0 };
  var seed = 22, observed = null, outs = {};

  var head = el("div", { "class": "widget-head" });
  head.appendChild(el("span", { "class": "widget-tag" }, "Try it"));
  head.appendChild(el("h4", { "class": "widget-title" }, "How many tasks to see a real effect?"));
  root.appendChild(head);
  root.appendChild(el("p", { "class": "widget-help" },
    "Task times vary a lot, so a small real gain is hidden by noise unless you measure many tasks. Choose a true effect and a spread, then see the interval a study of that size would give. " +
    "All numbers are assumptions. A negative speed-up means the tool slows people down."));

  var ctl = el("div", { "class": "ag22-ctl" });
  function slider(key, label, min, max, step, show) {
    var w = el("div"), lab = el("label", { "for": "agt22-" + key }), out = el("output", { id: "agt22-" + key + "-out" });
    lab.appendChild(document.createTextNode(label + ": "));
    lab.appendChild(out);
    var inp = el("input", { type: "range", id: "agt22-" + key, min: min, max: max, step: step, value: state[key] });
    inp.addEventListener("input", function () { state[key] = parseFloat(inp.value); observed = null; update(); });
    w.appendChild(lab); w.appendChild(inp); ctl.appendChild(w);
    outs[key] = { el: out, show: show };
  }
  slider("speed", "True speed-up of tasks", -30, 50, 1, function (v) { return (v > 0 ? "+" : "") + v + "%"; });
  slider("sigma", "Spread of task times (log scale)", 0.3, 1.2, 0.05, function (v) { return v.toFixed(2); });
  slider("n", "Tasks per arm", 5, 800, 5, String);
  slider("rho", "How well tasks are matched (0 to 0.9)", 0, 0.9, 0.05, function (v) { return v.toFixed(2); });
  root.appendChild(ctl);

  var btns = el("div", { "class": "ag22-btns" });
  var run = el("button", { type: "button", "class": "btn" }, "Run one simulated study");
  var reseed = el("button", { type: "button", "class": "btn" }, "Different random draw");
  run.addEventListener("click", function () {
    var m = model(state), r = mulberry32(seed), u1 = r(), u2 = r();
    var z = Math.sqrt(-2 * Math.log(u1 + 1e-12)) * Math.cos(2 * Math.PI * u2);
    observed = Math.exp(m.delta + m.se * z); update();
  });
  reseed.addEventListener("click", function () { seed += 1; if (observed !== null) run.click(); });
  btns.appendChild(run); btns.appendChild(reseed);
  root.appendChild(btns);

  var svg = sv("svg", { "class": "ag22-chart", role: "img", viewBox: "0 0 700 120", "aria-label": "A horizontal scale of the time ratio, AI divided by no AI, from 0.4 to 1.6. A marked line at 1.0 means no difference. A bar shows the 95 percent interval a study of the chosen size would give around the true ratio." });
  root.appendChild(svg);
  var out = el("div", { "class": "widget-out", "aria-live": "polite" });
  root.appendChild(out);

  var LO = Math.log(0.4), HI = Math.log(1.6);
  function px(v) { return 40 + (Math.log(Math.max(0.4, Math.min(1.6, v))) - LO) / (HI - LO) * 620; }

  function update() {
    var k, m = model(state);
    for (k in outs) outs[k].el.textContent = outs[k].show(state[k]);
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    [0.4, 0.6, 0.8, 1, 1.25, 1.6].forEach(function (t) {
      svg.appendChild(sv("line", { x1: px(t), x2: px(t), y1: 78, y2: 84, "class": "line-thin" }));
      svg.appendChild(sv("text", { x: px(t), y: 100, "text-anchor": "middle", "class": "t-xs t-muted" }, t.toFixed(t === 1.25 ? 2 : 1)));
    });
    svg.appendChild(sv("line", { x1: 40, x2: 660, y1: 78, y2: 78, "class": "line-thin" }));
    svg.appendChild(sv("line", { x1: px(1), x2: px(1), y1: 10, y2: 78, "class": "line-dash" }));
    svg.appendChild(sv("text", { x: px(1) + 6, y: 20, "class": "t-xs t-muted" }, "no difference"));
    var excl = m.hi < 1 || m.lo > 1;
    svg.appendChild(sv("rect", { x: px(m.lo), y: 34, width: Math.max(2, px(m.hi) - px(m.lo)), height: 18, rx: 3, "class": excl ? "f-green" : "f-orange" }));
    svg.appendChild(sv("circle", { cx: px(m.mid), cy: 43, r: 4, "class": "f-blue" }));
    if (observed !== null) {
      svg.appendChild(sv("path", { d: "M" + px(observed) + ",70 l-5,-10 h10 z", "class": "f-yellow" }));
    }
    out.textContent = "";
    var lines = [
      "Typical 95% interval for the time ratio: " + m.lo.toFixed(2) + " to " + m.hi.toFixed(2) + " (true ratio " + m.mid.toFixed(2) + "). " +
        (excl ? "It excludes 1.00, so the study would detect the effect." : "It contains 1.00, so a study this size usually cannot tell the tool from no effect."),
      "Chance that a study this size detects the effect: about " + Math.round(m.power * 100) + "%. Tasks per arm for 80% power: " + (isFinite(m.need) ? m.need.toLocaleString("en-GB") : "no effect to detect") + "."
    ];
    if (observed !== null) lines.push("This simulated study (yellow marker) measured a ratio of " + observed.toFixed(2) + ", which would be read as " + (observed < 1 ? Math.round((1 / observed - 1) * 100) + "% faster" : Math.round((observed - 1) * 100) + "% slower") + ". Draw again to see how much it moves.");
    lines.forEach(function (t) { out.appendChild(el("p", { style: "margin:4px 0" }, t)); });
  }
  update();
})();
