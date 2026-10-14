/* Gradient explorer (A0 chapter 08).
   Pick a surface and a point. The widget draws the gradient, lets you choose a
   direction u, and shows that the slope in that direction is the dot product
   grad . u, largest when u points along the gradient. */
(function () {
  "use strict";
  var root = document.getElementById("mlf08-gradient");
  if (!root) return;
  var NS = "http://www.w3.org/2000/svg";
  var map = root.querySelector(".mf8-map"), curve = root.querySelector(".mf8-curve"), out = root.querySelector(".mf8-out");
  var sel = root.querySelector("[data-act=fn]");
  var cx = root.querySelector("[data-act=x]"), cy = root.querySelector("[data-act=y]"), ca = root.querySelector("[data-act=a]"), ce = root.querySelector("[data-act=eta]");
  var ox = root.querySelector("[data-act=x-out]"), oy = root.querySelector("[data-act=y-out]"), oa = root.querySelector("[data-act=a-out]"), oe = root.querySelector("[data-act=eta-out]");
  var R = 2, N = 26, S = 300, CELL = S / N;

  var FN = {
    bowl: { f: function (x, y) { return x * x + 3 * y * y; }, g: function (x, y) { return [2 * x, 6 * y]; }, name: "x² + 3y²" },
    saddle: { f: function (x, y) { return x * x - y * y; }, g: function (x, y) { return [2 * x, -2 * y]; }, name: "x² − y²" },
    bumpy: {
      f: function (x, y) { return (x * x + y * y) / 2 + Math.sin(2 * x) * Math.sin(2 * y); },
      g: function (x, y) { return [x + 2 * Math.cos(2 * x) * Math.sin(2 * y), y + 2 * Math.sin(2 * x) * Math.cos(2 * y)]; },
      name: "(x² + y²)/2 + sin 2x sin 2y"
    }
  };
  function el(tag, attrs, text) {
    var e = document.createElementNS(NS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    return e;
  }
  function clear(n) { while (n.firstChild) n.removeChild(n.firstChild); }
  function px(x, y) { return [(x + R) / (2 * R) * S, (R - y) / (2 * R) * S]; }
  function arrow(svg, a, b, color, w) {
    var dx = b[0] - a[0], dy = b[1] - a[1], len = Math.sqrt(dx * dx + dy * dy);
    if (len < 1) return;
    svg.appendChild(el("line", { x1: a[0], y1: a[1], x2: b[0], y2: b[1], style: "stroke:" + color + ";stroke-width:" + w }));
    var ux = dx / len, uy = dy / len, h = 9;
    svg.appendChild(el("polygon", { points: b[0] + "," + b[1] + " " + (b[0] - ux * h - uy * h * 0.5) + "," + (b[1] - uy * h + ux * h * 0.5) + " " + (b[0] - ux * h + uy * h * 0.5) + "," + (b[1] - uy * h - ux * h * 0.5), style: "fill:" + color }));
  }
  function f4(v) { return (Math.abs(v) < 0.0005 ? 0 : v).toFixed(3); }

  function draw() {
    var F = FN[sel.value], x = +cx.value, y = +cy.value, deg = +ca.value;
    ox.textContent = x.toFixed(2); oy.textContent = y.toFixed(2); oa.textContent = deg + "°"; oe.textContent = (+ce.value).toFixed(2);
    var g = F.g(x, y), gn = Math.sqrt(g[0] * g[0] + g[1] * g[1]);
    var u = [Math.cos(deg * Math.PI / 180), Math.sin(deg * Math.PI / 180)];
    var slope = g[0] * u[0] + g[1] * u[1];
    var t = 1e-5, num = (F.f(x + t * u[0], y + t * u[1]) - F.f(x - t * u[0], y - t * u[1])) / (2 * t);
    clear(map);
    var lo = Infinity, hi = -Infinity, i, j, vals = [];
    for (j = 0; j < N; j++) for (i = 0; i < N; i++) {
      var v = F.f(-R + (i + 0.5) / N * 2 * R, R - (j + 0.5) / N * 2 * R);
      vals.push(v); if (v < lo) lo = v; if (v > hi) hi = v;
    }
    for (j = 0; j < N; j++) for (i = 0; i < N; i++) {
      var n = (vals[j * N + i] - lo) / (hi - lo + 1e-9);
      map.appendChild(el("rect", { x: i * CELL, y: j * CELL, width: CELL + 0.5, height: CELL + 0.5, style: "fill:var(--blue);opacity:" + (0.06 + 0.8 * n).toFixed(2) }));
    }
    map.appendChild(el("line", { x1: 0, y1: S / 2, x2: S, y2: S / 2, "class": "line-thin" }));
    map.appendChild(el("line", { x1: S / 2, y1: 0, x2: S / 2, y2: S, "class": "line-thin" }));
    var p = px(x, y), k = 46;
    if (gn > 1e-6) arrow(map, p, [p[0] + g[0] / gn * k * 1.4, p[1] - g[1] / gn * k * 1.4], "var(--yellow)", 3);
    arrow(map, p, [p[0] + u[0] * k, p[1] - u[1] * k], "var(--green)", 3);
    map.appendChild(el("circle", { cx: p[0], cy: p[1], r: 5, style: "fill:var(--text);stroke:var(--bg);stroke-width:2" }));
    map.appendChild(el("text", { x: 6, y: S - 6, "class": "t-xs t-muted" }, "darker = larger f. yellow = gradient, green = your direction u"));

    clear(curve);
    var W = 300, H = 300, m = Math.max(gn, 0.5) * 1.15;
    curve.appendChild(el("line", { x1: 30, y1: H / 2, x2: W - 6, y2: H / 2, "class": "line-thin" }));
    curve.appendChild(el("line", { x1: 30, y1: 10, x2: 30, y2: H - 20, "class": "line-thin" }));
    var pts = [], a;
    var gAng = Math.atan2(g[1], g[0]);
    for (a = 0; a <= 360; a += 4) {
      var s = gn * Math.cos((a * Math.PI / 180) - gAng);
      pts.push((30 + a / 360 * (W - 36)).toFixed(1) + "," + (H / 2 - 10 - s / m * (H / 2 - 40)).toFixed(1));
    }
    curve.appendChild(el("polyline", { points: pts.join(" "), "class": "s-blue sw-2", style: "fill:none" }));
    var mx = 30 + deg / 360 * (W - 36), my = H / 2 - 10 - slope / m * (H / 2 - 40);
    curve.appendChild(el("circle", { cx: mx, cy: my, r: 6, style: "fill:var(--green)" }));
    curve.appendChild(el("text", { x: 34, y: 18, "class": "t-xs t-muted" }, "slope of f along u, for every direction"));
    curve.appendChild(el("text", { x: W - 8, y: H - 6, "text-anchor": "end", "class": "t-xs t-muted" }, "angle of u: 0° to 360°"));
    curve.appendChild(el("text", { x: 34, y: H / 2 + 4, "class": "t-xs t-faint" }, "0"));

    clear(out);
    [["f(x, y)", f4(F.f(x, y))], ["gradient", "(" + f4(g[0]) + ", " + f4(g[1]) + ")"], ["|gradient|", f4(gn)],
     ["gradient angle", gn > 1e-6 ? (((gAng * 180 / Math.PI) + 360) % 360).toFixed(1) + "°" : "n/a"],
     ["slope along u: g·u", f4(slope)], ["slope by finite diff.", f4(num)]].forEach(function (r) {
      var d = document.createElement("div"); d.innerHTML = r[0] + " = <b></b>"; d.querySelector("b").textContent = r[1]; out.appendChild(d);
    });
  }
  function angleOf(dir) {
    var F = FN[sel.value], g = F.g(+cx.value, +cy.value);
    var a = Math.atan2(g[1], g[0]) * 180 / Math.PI + (dir < 0 ? 180 : 0);
    ca.value = Math.round(((a % 360) + 360) % 360);
    draw();
  }
  root.querySelector("[data-act=up]").addEventListener("click", function () { angleOf(1); });
  root.querySelector("[data-act=down]").addEventListener("click", function () { angleOf(-1); });
  root.querySelector("[data-act=step]").addEventListener("click", function () {
    var F = FN[sel.value], x = +cx.value, y = +cy.value, g = F.g(x, y), eta = +ce.value;
    var nx = Math.max(-R, Math.min(R, x - eta * g[0])), ny = Math.max(-R, Math.min(R, y - eta * g[1]));
    cx.value = nx.toFixed(2); cy.value = ny.toFixed(2); draw();
  });
  root.querySelector("[data-act=reset]").addEventListener("click", function () { cx.value = 1.4; cy.value = 0.7; ca.value = 45; draw(); });
  [cx, cy, ca, ce].forEach(function (c) { c.addEventListener("input", draw); });
  sel.addEventListener("change", draw);
  draw();
})();
