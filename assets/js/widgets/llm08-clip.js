/* PPO clipped-objective explorer (A3 chapter 08).
   Plots the per-token surrogate  min(r*A, clip(r, 1-eps, 1+eps)*A)  against the probability ratio r,
   for a chosen advantage A and clip range eps, and says whether a gradient reaches the policy at the chosen r.
   Formula: Schulman et al. (2017), equation 7. */
(function () {
  "use strict";
  var root = document.getElementById("llm08-clip");
  if (!root) return;

  var NS = "http://www.w3.org/2000/svg";
  var $ = function (s) { return root.querySelector(s); };
  var epsIn = $("[data-act=eps]"), epsOut = $("[data-act=eps-out]");
  var advIn = $("[data-act=adv]"), advOut = $("[data-act=adv-out]");
  var ratIn = $("[data-act=ratio]"), ratOut = $("[data-act=ratio-out]");
  var svg = $(".clip-chart"), out = $(".clip-out");

  function el(tag, attrs, text) {
    var e = document.createElementNS(NS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    return e;
  }
  function clamp(x, lo, hi) { return Math.min(hi, Math.max(lo, x)); }
  function surrogate(r, A, eps) { return Math.min(r * A, clamp(r, 1 - eps, 1 + eps) * A); }

  function draw(A, eps, r) {
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    var W = 700, H = 280, L = 54, R = 20, T = 20, B = 40;
    var pw = W - L - R, ph = H - T - B;
    var rMax = 2.5, yMax = Math.max(2.5, Math.abs(A) * rMax * 1.05);
    function X(v) { return L + pw * v / rMax; }
    function Y(v) { return T + ph * (0.5 - v / (2 * yMax)); }
    /* trust region band */
    svg.appendChild(el("rect", { x: X(1 - eps), y: T, width: X(1 + eps) - X(1 - eps), height: ph, "class": "f-green", opacity: 0.12 }));
    /* axes */
    svg.appendChild(el("line", { x1: L, y1: Y(0), x2: L + pw, y2: Y(0), "class": "line-thin" }));
    svg.appendChild(el("line", { x1: X(0), y1: T, x2: X(0), y2: T + ph, "class": "line-thin" }));
    svg.appendChild(el("line", { x1: X(1), y1: T, x2: X(1), y2: T + ph, "class": "line-dash" }));
    [0, 0.5, 1, 1.5, 2, 2.5].forEach(function (t) {
      svg.appendChild(el("text", { x: X(t), y: T + ph + 18, "text-anchor": "middle", "class": "t-xs t-muted" }, String(t)));
    });
    svg.appendChild(el("text", { x: L + pw / 2, y: H - 6, "text-anchor": "middle", "class": "t-xs t-muted" }, "ratio r = πθ / πold"));
    svg.appendChild(el("text", { x: 12, y: T + 10, "class": "t-xs t-muted" }, "objective"));
    /* curves */
    var raw = "", clipped = "", i, v;
    for (i = 0; i <= 250; i++) {
      v = i / 100;
      raw += (i ? "L" : "M") + X(v).toFixed(1) + "," + clamp(Y(v * A), T, T + ph).toFixed(1);
      clipped += (i ? "L" : "M") + X(v).toFixed(1) + "," + clamp(Y(surrogate(v, A, eps)), T, T + ph).toFixed(1);
    }
    svg.appendChild(el("path", { d: raw, fill: "none", "class": "line-dash s-orange", "stroke-width": 2 }));
    svg.appendChild(el("path", { d: clipped, fill: "none", "class": "s-blue", "stroke-width": 3 }));
    /* current point */
    var live = (r * A <= clamp(r, 1 - eps, 1 + eps) * A);
    svg.appendChild(el("circle", { cx: X(r), cy: clamp(Y(surrogate(r, A, eps)), T, T + ph), r: 7, "class": live ? "f-green" : "f-red" }));
    /* legend */
    svg.appendChild(el("line", { x1: L + 10, y1: T + 8, x2: L + 40, y2: T + 8, "class": "s-blue", "stroke-width": 3 }));
    svg.appendChild(el("text", { x: L + 46, y: T + 12, "class": "t-xs" }, "clipped objective"));
    svg.appendChild(el("line", { x1: L + 170, y1: T + 8, x2: L + 200, y2: T + 8, "class": "line-dash s-orange", "stroke-width": 2 }));
    svg.appendChild(el("text", { x: L + 206, y: T + 12, "class": "t-xs" }, "unclipped r × A"));
    svg.setAttribute("viewBox", "0 0 " + W + " " + H);
  }

  function run() {
    var eps = parseFloat(epsIn.value), A = parseFloat(advIn.value), r = parseFloat(ratIn.value);
    epsOut.textContent = eps.toFixed(2); advOut.textContent = A.toFixed(1); ratOut.textContent = r.toFixed(2);
    draw(A, eps, r);
    var obj = surrogate(r, A, eps);
    var live = (r * A <= clamp(r, 1 - eps, 1 + eps) * A);
    var msg = "Objective at r = " + r.toFixed(2) + ": " + obj.toFixed(2) + ". ";
    if (A === 0) msg += "Advantage is zero, so this token contributes no gradient either way.";
    else if (live) msg += "Gradient flows: the unclipped term is the smaller one, so this token still pushes the policy " + (A > 0 ? "towards" : "away from") + " its action.";
    else msg += "Gradient is zero: the ratio has already moved " + (A > 0 ? "up" : "down") + " past the clip boundary in the direction this token wanted, so it is ignored.";
    out.textContent = msg;
    out.className = "widget-out clip-out " + (A === 0 || live ? "live" : "dead");
  }
  [epsIn, advIn, ratIn].forEach(function (e) { e.addEventListener("input", run); });
  run();
})();
