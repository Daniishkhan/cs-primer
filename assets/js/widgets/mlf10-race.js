/* Optimiser race (A0 chapter 10).
   Four optimisers start from the same point on the same surface and share one
   learning rate. Watch how each handles a narrow valley, a curved valley and a saddle. */
(function () {
  "use strict";
  var root = document.getElementById("mlf10-race");
  if (!root) return;
  var NS = "http://www.w3.org/2000/svg";
  var svg = root.querySelector(".mf10-svg"), out = root.querySelector(".mf10-out");
  var sel = root.querySelector("[data-act=surf]"), lrIn = root.querySelector("[data-act=lr]"), lrOut = root.querySelector("[data-act=lr-out]");
  var muIn = root.querySelector("[data-act=mu]"), muOut = root.querySelector("[data-act=mu-out]");
  var W = 460, H = 280;

  var SURF = {
    bowl: {
      name: "narrow valley", view: [-2, 2, -0.7, 0.7], start: [-1.5, 0.5],
      f: function (x, y) { return 0.5 * (x * x + 100 * y * y); },
      g: function (x, y) { return [x, 100 * y]; }
    },
    rosen: {
      name: "Rosenbrock", view: [-2, 2, -1, 3], start: [-1.2, 1],
      f: function (x, y) { return Math.pow(1 - x, 2) + 100 * Math.pow(y - x * x, 2); },
      g: function (x, y) { return [-2 * (1 - x) - 400 * x * (y - x * x), 200 * (y - x * x)]; }
    },
    well: {
      name: "double well", view: [-2, 2, -1.5, 1.5], start: [0.02, 1.2],
      f: function (x, y) { return Math.pow(x * x - 1, 2) + 2 * y * y; },
      g: function (x, y) { return [4 * x * (x * x - 1), 4 * y]; }
    }
  };
  var NAMES = [["sgd", "SGD", "var(--blue)"], ["mom", "Momentum", "var(--green)"], ["rms", "RMSProp", "var(--orange)"], ["adam", "Adam", "var(--pink)"]];
  var state, steps, timer = null;

  function reset() {
    var S = SURF[sel.value];
    state = {};
    NAMES.forEach(function (n) {
      state[n[0]] = { w: [S.start[0], S.start[1]], path: [[S.start[0], S.start[1]]], v: [0, 0], s: [0, 0], m: [0, 0], t: 0, dead: false };
    });
    steps = 0;
    stop();
    draw();
  }
  function lr() { return Math.pow(10, +lrIn.value); }
  function stepAll() {
    var S = SURF[sel.value], eta = lr(), mu = +muIn.value;
    NAMES.forEach(function (n) {
      var o = state[n[0]];
      if (o.dead) return;
      var g = S.g(o.w[0], o.w[1]), i, nw = [0, 0];
      o.t++;
      for (i = 0; i < 2; i++) {
        if (n[0] === "sgd") nw[i] = o.w[i] - eta * g[i];
        else if (n[0] === "mom") { o.v[i] = mu * o.v[i] + g[i]; nw[i] = o.w[i] - eta * o.v[i]; }
        else if (n[0] === "rms") { o.s[i] = 0.9 * o.s[i] + 0.1 * g[i] * g[i]; nw[i] = o.w[i] - eta * g[i] / (Math.sqrt(o.s[i]) + 1e-8); }
        else {
          o.m[i] = 0.9 * o.m[i] + 0.1 * g[i]; o.s[i] = 0.999 * o.s[i] + 0.001 * g[i] * g[i];
          nw[i] = o.w[i] - eta * (o.m[i] / (1 - Math.pow(0.9, o.t))) / (Math.sqrt(o.s[i] / (1 - Math.pow(0.999, o.t))) + 1e-8);
        }
      }
      if (!isFinite(nw[0]) || !isFinite(nw[1]) || Math.abs(nw[0]) > 1e4 || Math.abs(nw[1]) > 1e4) { o.dead = true; return; }
      o.w = nw; o.path.push([nw[0], nw[1]]);
    });
    steps++;
  }
  function el(tag, attrs, text) {
    var e = document.createElementNS(NS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    return e;
  }
  function px(S, x, y) { return [(x - S.view[0]) / (S.view[1] - S.view[0]) * W, (S.view[3] - y) / (S.view[3] - S.view[2]) * H]; }
  function draw() {
    var S = SURF[sel.value], i, j, NX = 46, NY = 28;
    lrOut.textContent = lr().toPrecision(2); muOut.textContent = (+muIn.value).toFixed(2);
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    var vals = [], lo = Infinity, hi = -Infinity;
    for (j = 0; j < NY; j++) for (i = 0; i < NX; i++) {
      var x = S.view[0] + (i + 0.5) / NX * (S.view[1] - S.view[0]), y = S.view[3] - (j + 0.5) / NY * (S.view[3] - S.view[2]);
      var v = Math.log(1 + S.f(x, y)); vals.push(v); if (v < lo) lo = v; if (v > hi) hi = v;
    }
    for (j = 0; j < NY; j++) for (i = 0; i < NX; i++) {
      var n = (vals[j * NX + i] - lo) / (hi - lo + 1e-9);
      svg.appendChild(el("rect", { x: i * W / NX, y: j * H / NY, width: W / NX + 0.5, height: H / NY + 0.5, style: "fill:var(--blue);opacity:" + (0.05 + 0.5 * n).toFixed(2) }));
    }
    var st = px(S, S.start[0], S.start[1]);
    NAMES.forEach(function (n) {
      var o = state[n[0]], pts = o.path.map(function (p) { var q = px(S, p[0], p[1]); return q[0].toFixed(1) + "," + q[1].toFixed(1); });
      if (pts.length > 1) svg.appendChild(el("polyline", { points: pts.join(" "), style: "fill:none;stroke:" + n[2] + ";stroke-width:2;stroke-linejoin:round;opacity:0.95" }));
      var e = px(S, o.w[0], o.w[1]);
      if (!o.dead) svg.appendChild(el("circle", { cx: Math.max(0, Math.min(W, e[0])), cy: Math.max(0, Math.min(H, e[1])), r: 4.5, style: "fill:" + n[2] + ";stroke:var(--bg);stroke-width:1.5" }));
    });
    svg.appendChild(el("circle", { cx: st[0], cy: st[1], r: 5, style: "fill:none;stroke:var(--text);stroke-width:2" }));
    svg.appendChild(el("text", { x: 6, y: H - 6, "class": "t-xs t-muted" }, "ring = start, darker = higher loss (log scale)"));
    out.innerHTML = "";
    NAMES.forEach(function (n) {
      var o = state[n[0]], d = document.createElement("div"), f = o.dead ? "diverged" : S.f(o.w[0], o.w[1]).toExponential(2);
      d.innerHTML = '<span class="sw" style="background:' + n[2] + '"></span>' + n[1] + ": <b></b>";
      d.querySelector("b").textContent = f; out.appendChild(d);
    });
    var d = document.createElement("div"); d.textContent = "steps taken: " + steps; out.appendChild(d);
  }
  function stop() { if (timer) { clearInterval(timer); timer = null; root.querySelector("[data-act=play]").textContent = "Run"; } }
  root.querySelector("[data-act=step]").addEventListener("click", function () { stop(); stepAll(); draw(); });
  root.querySelector("[data-act=step10]").addEventListener("click", function () { stop(); for (var k = 0; k < 10; k++) stepAll(); draw(); });
  root.querySelector("[data-act=reset]").addEventListener("click", reset);
  root.querySelector("[data-act=play]").addEventListener("click", function () {
    var btn = this;
    if (timer) { stop(); return; }
    btn.textContent = "Pause";
    timer = setInterval(function () { stepAll(); draw(); if (steps >= 600) stop(); }, 40);
  });
  sel.addEventListener("change", reset);
  lrIn.addEventListener("input", function () { draw(); });
  muIn.addEventListener("input", function () { draw(); });
  reset();
})();
