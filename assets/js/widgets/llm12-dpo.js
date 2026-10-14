/* DPO loss explorer (A3 chapter 12).
   For one preference pair, the user sets beta and the log-ratio of the chosen and the rejected response,
   log(pi_theta / pi_ref). The implicit-reward margin is m = beta * (dw - dl); the loss is -log sigmoid(m)
   and the weight that scales the gradient is sigmoid(-m) (Rafailov et al., 2023, section 4). */
(function () {
  "use strict";
  var root = document.getElementById("llm12-dpo");
  if (!root) return;

  var NS = "http://www.w3.org/2000/svg";
  var $ = function (s) { return root.querySelector(s); };
  var betaIn = $("[data-act=beta]"), betaOut = $("[data-act=beta-out]");
  var wIn = $("[data-act=dw]"), wOut = $("[data-act=dw-out]");
  var lIn = $("[data-act=dl]"), lOut = $("[data-act=dl-out]");
  var svg = $(".dpo-chart"), out = $(".dpo-out");

  function el(tag, attrs, text) {
    var e = document.createElementNS(NS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    return e;
  }
  function sigmoid(x) { return 1 / (1 + Math.exp(-x)); }
  function loss(m) { return Math.log(1 + Math.exp(-m)); }

  function draw(m) {
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    var W = 700, H = 260, L = 54, R = 20, T = 20, B = 44;
    var pw = W - L - R, ph = H - T - B, mMin = -6, mMax = 6, yMax = 6.2;
    function X(v) { return L + pw * (v - mMin) / (mMax - mMin); }
    function Y(v) { return T + ph * (1 - v / yMax); }
    svg.appendChild(el("line", { x1: L, y1: Y(0), x2: L + pw, y2: Y(0), "class": "line-thin" }));
    svg.appendChild(el("line", { x1: X(0), y1: T, x2: X(0), y2: T + ph, "class": "line-dash" }));
    [-6, -4, -2, 0, 2, 4, 6].forEach(function (t) {
      svg.appendChild(el("text", { x: X(t), y: T + ph + 18, "text-anchor": "middle", "class": "t-xs t-muted" }, String(t)));
    });
    [0, 2, 4, 6].forEach(function (t) {
      svg.appendChild(el("text", { x: L - 8, y: Y(t) + 4, "text-anchor": "end", "class": "t-xs t-muted" }, String(t)));
    });
    svg.appendChild(el("text", { x: L + pw / 2, y: H - 6, "text-anchor": "middle", "class": "t-xs t-muted" }, "implicit-reward margin m = β (Δchosen − Δrejected)"));
    var lp = "", wp = "", i, v;
    for (i = 0; i <= 120; i++) {
      v = mMin + (mMax - mMin) * i / 120;
      lp += (i ? "L" : "M") + X(v).toFixed(1) + "," + Y(Math.min(loss(v), yMax)).toFixed(1);
      wp += (i ? "L" : "M") + X(v).toFixed(1) + "," + Y(sigmoid(-v) * 4).toFixed(1);
    }
    svg.appendChild(el("path", { d: wp, fill: "none", "class": "line-dash s-orange", "stroke-width": 2 }));
    svg.appendChild(el("path", { d: lp, fill: "none", "class": "s-blue", "stroke-width": 3 }));
    var mc = Math.max(mMin, Math.min(mMax, m));
    svg.appendChild(el("circle", { cx: X(mc), cy: Y(Math.min(loss(mc), yMax)), r: 7, "class": m >= 0 ? "f-green" : "f-red" }));
    svg.appendChild(el("line", { x1: L + 10, y1: T + 8, x2: L + 40, y2: T + 8, "class": "s-blue", "stroke-width": 3 }));
    svg.appendChild(el("text", { x: L + 46, y: T + 12, "class": "t-xs" }, "loss = −log σ(m)"));
    svg.appendChild(el("line", { x1: L + 190, y1: T + 8, x2: L + 220, y2: T + 8, "class": "line-dash s-orange", "stroke-width": 2 }));
    svg.appendChild(el("text", { x: L + 226, y: T + 12, "class": "t-xs" }, "gradient weight σ(−m), drawn × 4"));
    svg.setAttribute("viewBox", "0 0 " + W + " " + H);
  }

  function run() {
    var beta = parseFloat(betaIn.value), dw = parseFloat(wIn.value), dl = parseFloat(lIn.value);
    betaOut.textContent = beta.toFixed(2); wOut.textContent = dw.toFixed(1); lOut.textContent = dl.toFixed(1);
    var m = beta * (dw - dl);
    draw(m);
    var msg = "Implicit rewards: chosen " + (beta * dw).toFixed(2) + ", rejected " + (beta * dl).toFixed(2) +
      ". Margin " + m.toFixed(2) + ", loss " + loss(m).toFixed(3) + ", gradient weight " + sigmoid(-m).toFixed(3) + ". ";
    var cls = "good";
    if (m < 0) { msg += "The model currently ranks this pair the wrong way round, so the weight is above one half and the update is large."; cls = "bad"; }
    else if (sigmoid(-m) < 0.05) { msg += "The pair is already ranked correctly by a wide margin: the weight is under 0.05, so it contributes almost nothing."; }
    else { msg += "Ranked correctly but not yet confidently: the pair still pulls with moderate weight."; }
    if (dw < 0 && m > 0) { msg += " Note that the chosen response has become less likely than under the reference (Δchosen < 0): the margin is positive only because the rejected one fell further."; cls = "warn"; }
    out.textContent = msg;
    out.className = "widget-out dpo-out " + cls;
  }
  [betaIn, wIn, lIn].forEach(function (e) { e.addEventListener("input", run); });
  run();
})();
