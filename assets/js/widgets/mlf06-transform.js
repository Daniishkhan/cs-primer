/* Matrix transformation playground (A0 chapter 06).
   Edit a 2x2 matrix M with four sliders, optionally compose it with a rotation (in
   either order) and watch the grid, the unit square and the images of the basis
   vectors. Shows the composite matrix, its determinant and its inverse. */
(function () {
  "use strict";
  var root = document.getElementById("mlf06-transform");
  if (!root) return;
  var NS = "http://www.w3.org/2000/svg";
  var svg = root.querySelector(".mf6-svg");
  var out = root.querySelector(".mf6-out");
  var names = ["m00", "m01", "m10", "m11", "rot"];
  var c = {};
  names.forEach(function (n) { c[n] = root.querySelector("[data-act=" + n + "]"); c[n + "o"] = root.querySelector("[data-act=" + n + "-out]"); });
  var order = root.querySelector("[data-act=order]");
  var K = 44, OX = 280, OY = 200;

  function s(tag, attrs) {
    var e = document.createElementNS(NS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    return e;
  }
  function mul(A, B) {
    return [[A[0][0] * B[0][0] + A[0][1] * B[1][0], A[0][0] * B[0][1] + A[0][1] * B[1][1]],
            [A[1][0] * B[0][0] + A[1][1] * B[1][0], A[1][0] * B[0][1] + A[1][1] * B[1][1]]];
  }
  function ap(M, p) { return [M[0][0] * p[0] + M[0][1] * p[1], M[1][0] * p[0] + M[1][1] * p[1]]; }
  function px(M, p) { var q = ap(M, p); return [OX + q[0] * K, OY - q[1] * K]; }
  function f(x) { var v = Math.abs(x) < 0.0005 ? 0 : x; return v.toFixed(2); }
  function line(a, b, cls, w) {
    svg.appendChild(s("line", { x1: a[0].toFixed(1), y1: a[1].toFixed(1), x2: b[0].toFixed(1), y2: b[1].toFixed(1), "class": cls, "stroke-width": w || 1 }));
  }

  function draw() {
    var M = [[+c.m00.value, +c.m01.value], [+c.m10.value, +c.m11.value]];
    var th = +c.rot.value * Math.PI / 180;
    var R = [[Math.cos(th), -Math.sin(th)], [Math.sin(th), Math.cos(th)]];
    var C = order.value === "after" ? mul(R, M) : mul(M, R);
    names.forEach(function (n) { c[n + "o"].textContent = n === "rot" ? c[n].value + "°" : (+c[n].value).toFixed(1); });
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    var defs = s("defs", {}), cp = s("clipPath", { id: "mf6clip" });
    cp.appendChild(s("rect", { x: 0, y: 0, width: 560, height: 400 }));
    defs.appendChild(cp); svg.appendChild(defs);
    var g = s("g", { "clip-path": "url(#mf6clip)" });
    svg.appendChild(g);
    var keep = svg; svg = g; // draw into the clipped group
    var i;
    for (i = -12; i <= 12; i++) {
      line(px(C, [i, -12]), px(C, [i, 12]), "line-thin", i === 0 ? 1.5 : 1);
      line(px(C, [-12, i]), px(C, [12, i]), "line-thin", i === 0 ? 1.5 : 1);
    }
    // original unit square, faint
    var o0 = [[0, 0], [1, 0], [1, 1], [0, 1]].map(function (p) { return [OX + p[0] * K, OY - p[1] * K]; });
    svg.appendChild(s("polygon", { points: o0.map(function (p) { return p.join(","); }).join(" "), fill: "none", "class": "line-dash", "stroke-width": 1 }));
    var sq = [[0, 0], [1, 0], [1, 1], [0, 1]].map(function (p) { return px(C, p); });
    svg.appendChild(s("polygon", { points: sq.map(function (p) { return p[0].toFixed(1) + "," + p[1].toFixed(1); }).join(" "), "class": "fs-yellow s-yellow", "stroke-width": 2 }));
    line(px(C, [0, 0]), px(C, [1, 0]), "s-blue", 3.5);
    line(px(C, [0, 0]), px(C, [0, 1]), "s-green", 3.5);
    var e1 = px(C, [1, 0]), e2 = px(C, [0, 1]);
    [[e1, "s-blue"], [e2, "s-green"]].forEach(function (a) {
      svg.appendChild(s("circle", { cx: a[0][0].toFixed(1), cy: a[0][1].toFixed(1), r: 5, "class": a[1].replace("s-", "f-") }));
    });
    svg = keep;
    var det = C[0][0] * C[1][1] - C[0][1] * C[1][0];
    var inv = Math.abs(det) > 1e-6 ?
      "[[" + f(C[1][1] / det) + ", " + f(-C[0][1] / det) + "], [" + f(-C[1][0] / det) + ", " + f(C[0][0] / det) + "]]" :
      "none (the matrix flattens the plane, so information is lost)";
    out.innerHTML = "";
    [["composite", "[[" + f(C[0][0]) + ", " + f(C[0][1]) + "], [" + f(C[1][0]) + ", " + f(C[1][1]) + "]]"],
     ["blue arrow (image of e1) = first column", "(" + f(C[0][0]) + ", " + f(C[1][0]) + ")"],
     ["green arrow (image of e2) = second column", "(" + f(C[0][1]) + ", " + f(C[1][1]) + ")"],
     ["determinant (area scale; negative = flipped)", f(det)],
     ["inverse", inv]].forEach(function (r) {
      var d = document.createElement("div");
      d.appendChild(document.createTextNode(r[0] + ": "));
      var b = document.createElement("b"); b.textContent = r[1]; d.appendChild(b);
      out.appendChild(d);
    });
  }
  function set(m, r) {
    c.m00.value = m[0]; c.m01.value = m[1]; c.m10.value = m[2]; c.m11.value = m[3];
    if (r !== undefined) c.rot.value = r;
    draw();
  }
  var P = { ident: [1, 0, 0, 1], scale: [2, 0, 0, 0.5], shear: [1, 0.8, 0, 1], flip: [-1, 0, 0, 1], sing: [1, 0.5, 2, 1] };
  Object.keys(P).forEach(function (k) {
    root.querySelector("[data-act=p-" + k + "]").addEventListener("click", function () { set(P[k]); });
  });
  root.querySelector("[data-act=p-rot]").addEventListener("click", function () { set(P.ident, 45); });
  names.forEach(function (n) { c[n].addEventListener("input", draw); });
  order.addEventListener("change", draw);
  draw();
})();
