/* Dot product explorer (A0 chapter 05).
   Two vectors a and b are set by length and angle. The widget shows the dot product
   computed two ways (components and |a||b|cos), the cosine, the projection of b on a
   and the Euclidean distance. */
(function () {
  "use strict";
  var root = document.getElementById("mlf05-dot");
  if (!root) return;
  var NS = "http://www.w3.org/2000/svg";
  var svg = root.querySelector(".mf5-svg");
  var out = root.querySelector(".mf5-grid");
  var ctl = {};
  ["la", "aa", "lb", "ab"].forEach(function (k) {
    ctl[k] = root.querySelector("[data-act=" + k + "]");
    ctl[k + "o"] = root.querySelector("[data-act=" + k + "-out]");
  });

  function s(tag, attrs, text) {
    var e = document.createElementNS(NS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    return e;
  }
  var K = 38, OX = 280, OY = 200; // pixels per unit, origin
  function px(v) { return [OX + v[0] * K, OY - v[1] * K]; }
  function arrow(from, to, cls, width) {
    var a = px(from), b = px(to);
    var dx = b[0] - a[0], dy = b[1] - a[1], len = Math.sqrt(dx * dx + dy * dy);
    svg.appendChild(s("line", { x1: a[0], y1: a[1], x2: b[0], y2: b[1], "class": cls, "stroke-width": width || 3 }));
    if (len > 8) {
      var ux = dx / len, uy = dy / len, h = 9;
      var p1 = [b[0] - ux * h - uy * h * 0.5, b[1] - uy * h + ux * h * 0.5];
      var p2 = [b[0] - ux * h + uy * h * 0.5, b[1] - uy * h - ux * h * 0.5];
      svg.appendChild(s("polygon", { points: b.join(",") + " " + p1.join(",") + " " + p2.join(","), "class": cls.replace("s-", "f-") }));
    }
  }
  function fmt(x) { return (Math.abs(x) < 0.005 ? 0 : x).toFixed(2); }

  function draw() {
    var la = +ctl.la.value, lb = +ctl.lb.value, aa = +ctl.aa.value, ab = +ctl.ab.value;
    ctl.lao.textContent = la.toFixed(1); ctl.lbo.textContent = lb.toFixed(1);
    ctl.aao.textContent = aa + "°"; ctl.abo.textContent = ab + "°";
    var a = [la * Math.cos(aa * Math.PI / 180), la * Math.sin(aa * Math.PI / 180)];
    var b = [lb * Math.cos(ab * Math.PI / 180), lb * Math.sin(ab * Math.PI / 180)];
    var dot = a[0] * b[0] + a[1] * b[1];
    var cos = dot / (la * lb);
    var coef = dot / (la * la);
    var proj = [coef * a[0], coef * a[1]];
    var dist = Math.sqrt(Math.pow(a[0] - b[0], 2) + Math.pow(a[1] - b[1], 2));
    var ang = Math.acos(Math.max(-1, Math.min(1, cos))) * 180 / Math.PI;
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    svg.appendChild(s("line", { x1: 10, y1: OY, x2: 550, y2: OY, "class": "line-thin" }));
    svg.appendChild(s("line", { x1: OX, y1: 10, x2: OX, y2: 390, "class": "line-thin" }));
    // projection of b on a: dashed drop and thick yellow segment
    var pb = px(b), pp = px(proj);
    svg.appendChild(s("line", { x1: pb[0], y1: pb[1], x2: pp[0], y2: pp[1], "class": "line-dash" }));
    arrow([0, 0], proj, "s-yellow", 6);
    arrow([0, 0], a, "s-blue", 3);
    arrow([0, 0], b, "s-green", 3);
    var pa = px(a);
    svg.appendChild(s("text", { x: pa[0] + 8, y: pa[1] - 6, "class": "t-sm t-bold tc-blue" }, "a"));
    svg.appendChild(s("text", { x: pb[0] + 8, y: pb[1] - 6, "class": "t-sm t-bold tc-green" }, "b"));
    svg.appendChild(s("text", { x: 548, y: 386, "text-anchor": "end", "class": "t-xs t-muted" }, "yellow = projection of b onto a"));
    out.innerHTML = "";
    [["a", "(" + fmt(a[0]) + ", " + fmt(a[1]) + ")"], ["b", "(" + fmt(b[0]) + ", " + fmt(b[1]) + ")"],
     ["a·b (components)", fmt(dot)], ["|a||b|cosθ", fmt(la * lb * cos)],
     ["cosine", fmt(cos)], ["angle", ang.toFixed(1) + "°"],
     ["proj coefficient", fmt(coef)], ["|a − b|", fmt(dist)]].forEach(function (r) {
      var d = document.createElement("div");
      d.innerHTML = r[0] + " = <b></b>";
      d.querySelector("b").textContent = r[1];
      out.appendChild(d);
    });
  }
  function set(v) { for (var k in v) ctl[k].value = v[k]; draw(); }
  root.querySelector("[data-act=same]").addEventListener("click", function () { set({ la: 3, aa: 30, lb: 4.5, ab: 30 }); });
  root.querySelector("[data-act=perp]").addEventListener("click", function () { set({ la: 3, aa: 30, lb: 4, ab: 120 }); });
  root.querySelector("[data-act=opp]").addEventListener("click", function () { set({ la: 3, aa: 30, lb: 3, ab: 210 }); });
  root.querySelector("[data-act=long]").addEventListener("click", function () { set({ lb: Math.min(5, +ctl.lb.value * 2) }); });
  ["la", "aa", "lb", "ab"].forEach(function (k) { ctl[k].addEventListener("input", draw); });
  draw();
})();
