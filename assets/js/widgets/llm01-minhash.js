/* MinHash banding explorer (A3 chapter 01).
   Two documents with Jaccard similarity s share a given band of r rows with probability s^r,
   and share at least one of b bands with probability 1 - (1 - s^r)^b. We draw that S-curve
   for the chosen b and r and read off a few probabilities. */
(function () {
  "use strict";
  var root = document.getElementById("llm01-minhash");
  if (!root) return;

  var NS = "http://www.w3.org/2000/svg";
  var bIn = root.querySelector("[data-act=bands]");
  var rIn = root.querySelector("[data-act=rows]");
  var bOut = root.querySelector("[data-act=bands-out]");
  var rOut = root.querySelector("[data-act=rows-out]");
  var preset = root.querySelector("[data-act=preset]");
  var svg = root.querySelector(".mh-chart");
  var tbody = root.querySelector(".mh-table tbody");
  var summary = root.querySelector(".mh-summary");

  var PRESETS = {
    fineweb: { b: 14, r: 8, label: "FineWeb: 14 bands of 8 rows (112 hashes)" },
    loose:   { b: 20, r: 5, label: "Looser: 20 bands of 5 rows (100 hashes)" },
    strict:  { b: 9,  r: 13, label: "Stricter: 9 bands of 13 rows (117 hashes)" },
    few:     { b: 4,  r: 4, label: "Cheap: 4 bands of 4 rows (16 hashes)" }
  };

  function p(s, b, r) { return 1 - Math.pow(1 - Math.pow(s, r), b); }

  function el(tag, attrs, text) {
    var e = document.createElementNS(NS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    return e;
  }

  function draw(b, r) {
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    var W = 700, H = 250, L = 46, R = 14, T = 14, B = 40;
    var pw = W - L - R, ph = H - T - B;
    function X(s) { return L + pw * s; }
    function Y(v) { return T + ph * (1 - v); }
    var i;
    for (i = 0; i <= 4; i++) {
      var v = i / 4;
      svg.appendChild(el("line", { x1: L, y1: Y(v), x2: W - R, y2: Y(v), "class": "line-thin" }));
      svg.appendChild(el("text", { x: L - 6, y: Y(v) + 4, "text-anchor": "end", "class": "t-xs t-faint" }, String(Math.round(v * 100)) + "%"));
      svg.appendChild(el("text", { x: X(v), y: T + ph + 16, "text-anchor": "middle", "class": "t-xs t-faint" }, v.toFixed(2)));
    }
    svg.appendChild(el("text", { x: L + pw / 2, y: H - 6, "text-anchor": "middle", "class": "t-xs t-muted" }, "true similarity (Jaccard) of the two documents"));
    svg.appendChild(el("text", { x: 12, y: T + ph / 2, "text-anchor": "middle", "class": "t-xs t-muted", transform: "rotate(-90 12 " + (T + ph / 2) + ")" }, "chance they are flagged"));
    var d = "";
    for (i = 0; i <= 100; i++) {
      var s = i / 100;
      d += (i === 0 ? "M" : "L") + X(s).toFixed(1) + "," + Y(p(s, b, r)).toFixed(1);
    }
    svg.appendChild(el("path", { d: d, fill: "none", "class": "line s-blue sw-2" }));
    var th = Math.pow(1 / b, 1 / r);
    svg.appendChild(el("line", { x1: X(th), y1: T, x2: X(th), y2: T + ph, "class": "line-dash s-yellow" }));
    svg.appendChild(el("text", { x: X(th) + (th > 0.7 ? -6 : 6), y: T + 12, "text-anchor": th > 0.7 ? "end" : "start", "class": "t-xs tc-yellow t-bold" }, "threshold about " + th.toFixed(2)));
  }

  function run() {
    var b = parseInt(bIn.value, 10), r = parseInt(rIn.value, 10);
    bOut.textContent = String(b);
    rOut.textContent = String(r);
    draw(b, r);
    tbody.textContent = "";
    [0.4, 0.5, 0.6, 0.7, 0.8, 0.9].forEach(function (s) {
      var tr = document.createElement("tr");
      var pr = p(s, b, r);
      [s.toFixed(2), (pr * 100).toFixed(1) + "%", pr < 0.05 ? "ignored" : pr > 0.95 ? "almost always caught" : "sometimes caught"].forEach(function (t) {
        var td = document.createElement("td"); td.textContent = t; tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
    summary.textContent = "Each document stores " + (b * r) + " hash values. Pairs more similar than about " +
      Math.pow(1 / b, 1 / r).toFixed(2) + " are usually flagged; much less similar pairs almost never are. " +
      "More rows per band makes the test stricter, more bands makes it looser.";
  }

  preset.addEventListener("change", function () {
    var pr = PRESETS[preset.value];
    if (!pr) return;
    bIn.value = pr.b; rIn.value = pr.r; run();
  });
  bIn.addEventListener("input", function () { preset.value = "custom"; run(); });
  rIn.addEventListener("input", function () { preset.value = "custom"; run(); });
  run();
})();
