/* Will the click land? (agents chapter 17)
   Same arithmetic as the chapter's scale_demo.py. A screenshot is shrunk to fit the model's image limit; the model's
   click error (an ASSUMED uniform +-e in the pixels it saw) is divided by the scale to give the error on the real screen. */
(function () {
  "use strict";

  var LIMITS = {
    earlier: { name: "Earlier models: 1568 px long edge, about 1.15 MP", edge: 1568, pixels: 1150000 },
    newer: { name: "Newer models: 2576 px long edge, 4784 visual tokens (about 3.75 MP)", edge: 2576, pixels: 4784 * 28 * 28 }
  };

  function scaleFactor(w, h, lim) {
    return Math.min(1, lim.edge / Math.max(w, h), Math.sqrt(lim.pixels / (w * h)));
  }
  function hitProbability(target, errModel, s) {
    var e = errModel / s;
    if (e <= 0) return 1;
    var p = Math.min(1, target / (2 * e));
    return p * p;
  }
  function mulberry32(a) {
    return function () {
      a |= 0; a = a + 0x6D2B79F5 | 0;
      var t = Math.imul(a ^ a >>> 15, 1 | a);
      t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
      return ((t ^ t >>> 14) >>> 0) / 4294967296;
    };
  }

  var core = { scaleFactor: scaleFactor, hitProbability: hitProbability, LIMITS: LIMITS };
  if (typeof module !== "undefined" && module.exports) module.exports = core;
  if (typeof document === "undefined") return;
  var root = document.getElementById("agt17-grounding");
  if (!root) return;

  var NS = "http://www.w3.org/2000/svg";
  function el(tag, attrs, text) {
    var e = document.createElement(tag), k;
    for (k in attrs) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    return e;
  }
  function sv(tag, attrs) {
    var e = document.createElementNS(NS, tag), k;
    for (k in attrs) e.setAttribute(k, attrs[k]);
    return e;
  }

  var SCREENS = [[1280, 800], [1920, 1080], [2560, 1440], [3024, 1964], [3840, 2160]];
  var state = { screen: 3, limit: "earlier", err: 6, target: 14 };

  var head = el("div", { "class": "widget-head" });
  head.appendChild(el("span", { "class": "widget-tag" }, "Try it"));
  head.appendChild(el("h4", { "class": "widget-title" }, "Will the click land on the target?"));
  root.appendChild(head);
  root.appendChild(el("p", { "class": "widget-help" },
    "The screenshot is shrunk to fit the model's image limit, and the model's click error is measured in the shrunken image. Dots show 60 simulated clicks around the true centre of the target. The error size is an assumption you can change."));

  var ctl = el("div", { "class": "ag17-ctl" });
  function labelled(text, id, node) {
    var w = el("div");
    var l = el("label", { "for": id }, text);
    w.appendChild(l); w.appendChild(node); ctl.appendChild(w);
    return l;
  }
  var selS = el("select", { id: "agt17-screen" });
  SCREENS.forEach(function (s, i) { var o = el("option", { value: i }, s[0] + " x " + s[1] + " physical pixels"); if (i === state.screen) o.selected = true; selS.appendChild(o); });
  selS.addEventListener("change", function () { state.screen = parseInt(selS.value, 10); update(); });
  labelled("Screen: ", "agt17-screen", selS);
  var selL = el("select", { id: "agt17-limit" });
  Object.keys(LIMITS).forEach(function (k) { var o = el("option", { value: k }, LIMITS[k].name); if (k === state.limit) o.selected = true; selL.appendChild(o); });
  selL.addEventListener("change", function () { state.limit = selL.value; update(); });
  labelled("Image limit: ", "agt17-limit", selL);
  var outs = {};
  function slider(key, text, min, max) {
    var inp = el("input", { type: "range", id: "agt17-" + key, min: min, max: max, step: 1, value: state[key] });
    inp.addEventListener("input", function () { state[key] = parseInt(inp.value, 10); update(); });
    var l = labelled(text, "agt17-" + key, inp);
    outs[key] = el("output", {}); l.appendChild(outs[key]);
  }
  slider("err", "Model click error, +- image px: ", 1, 20);
  slider("target", "Target size, physical px: ", 6, 60);
  root.appendChild(ctl);

  var svg = sv("svg", { viewBox: "0 0 280 280", "class": "ag17-plot", role: "img", "aria-label": "A square target with simulated click positions around its centre. Green dots land inside the target, red dots miss." });
  root.appendChild(svg);
  var out = el("div", { "class": "widget-out", "aria-live": "polite" });
  root.appendChild(out);

  function update() {
    var sc = SCREENS[state.screen], lim = LIMITS[state.limit];
    var s = scaleFactor(sc[0], sc[1], lim), ePhys = state.err / s;
    var p = hitProbability(state.target, state.err, s);
    outs.err.textContent = state.err; outs.target.textContent = state.target;
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    var k = Math.min(6, 120 / Math.max(ePhys, state.target / 2));
    svg.appendChild(sv("rect", { x: 140 - ePhys * k, y: 140 - ePhys * k, width: 2 * ePhys * k, height: 2 * ePhys * k, "class": "ag17-err" }));
    svg.appendChild(sv("rect", { x: 140 - state.target * k / 2, y: 140 - state.target * k / 2, width: state.target * k, height: state.target * k, "class": "ag17-target" }));
    var rnd = mulberry32(17), hits = 0, i, N = 60;
    for (i = 0; i < N; i++) {
      var dx = (rnd() * 2 - 1) * ePhys, dy = (rnd() * 2 - 1) * ePhys;
      var hit = Math.abs(dx) <= state.target / 2 && Math.abs(dy) <= state.target / 2;
      if (hit) hits++;
      svg.appendChild(sv("circle", { cx: 140 + dx * k, cy: 140 + dy * k, r: 3, "class": hit ? "ag17-hit" : "ag17-miss" }));
    }
    out.textContent = "Scale " + s.toFixed(2) + ": the model sees " + Math.round(sc[0] * s) + " x " + Math.round(sc[1] * s) +
      ". A " + state.err + " px error in that image is " + ePhys.toFixed(1) + " physical px on the screen. " +
      "Chance a click lands on a " + state.target + " px target: " + Math.round(p * 100) + "% (" + hits + " of " + N + " simulated clicks here).";
  }
  update();
})();
