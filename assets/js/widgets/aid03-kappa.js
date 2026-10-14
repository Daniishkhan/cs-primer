/* Expert agreement explorer (A8 chapter 03).
   Two experts label items "refer" or "pay". Each is right with a chosen accuracy
   (independently, given the true label). The widget shows the expected 2x2 table,
   raw agreement, agreement expected by chance, and Cohen's kappa, then repeats a
   labelling session of N items 400 times (seeded) to show how widely kappa varies
   from one session to the next. */
(function () {
  "use strict";
  var root = document.getElementById("aid03-kappa");
  if (!root) return;

  function q(n) { return root.querySelector("[data-act=" + n + "]"); }
  var ctl = { prev: q("prev"), accA: q("acc-a"), accB: q("acc-b"), n: q("n") };
  var outs = { prev: q("prev-out"), accA: q("acc-a-out"), accB: q("acc-b-out"), n: q("n-out") };
  var tbody = root.querySelector(".aid03-table tbody");
  var summary = root.querySelector(".aid03-summary");
  var bar = root.querySelector(".aid03-range");

  function mulberry32(a) {
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      var t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  function kappaOf(c11, c10, c01, c00) {
    var n = c11 + c10 + c01 + c00;
    var po = (c11 + c00) / n;
    var pa1 = (c11 + c10) / n, pb1 = (c11 + c01) / n;
    var pe = pa1 * pb1 + (1 - pa1) * (1 - pb1);
    return { po: po, pe: pe, k: pe >= 1 ? 1 : (po - pe) / (1 - pe) };
  }

  function expected(prev, a, b) {
    // probabilities of (A says refer, B says refer) cells
    var p11 = prev * a * b + (1 - prev) * (1 - a) * (1 - b);
    var p10 = prev * a * (1 - b) + (1 - prev) * (1 - a) * b;
    var p01 = prev * (1 - a) * b + (1 - prev) * a * (1 - b);
    var p00 = 1 - p11 - p10 - p01;
    return [p11, p10, p01, p00];
  }

  function session(rng, n, p) {
    var c = [0, 0, 0, 0];
    for (var i = 0; i < n; i++) {
      var r = rng(), j = r < p[0] ? 0 : r < p[0] + p[1] ? 1 : r < p[0] + p[1] + p[2] ? 2 : 3;
      c[j]++;
    }
    return kappaOf(c[0], c[1], c[2], c[3]).k;
  }

  function cell(tr, text, head) {
    var td = document.createElement(head ? "th" : "td"); td.textContent = text; tr.appendChild(td);
  }

  function update() {
    var prev = parseFloat(ctl.prev.value), a = parseFloat(ctl.accA.value), b = parseFloat(ctl.accB.value), n = parseInt(ctl.n.value, 10);
    outs.prev.textContent = Math.round(prev * 100) + "%";
    outs.accA.textContent = Math.round(a * 100) + "%";
    outs.accB.textContent = Math.round(b * 100) + "%";
    outs.n.textContent = String(n);
    var p = expected(prev, a, b);
    var m = kappaOf(p[0], p[1], p[2], p[3]);
    tbody.textContent = "";
    var rows = [["Expert A: refer", p[0], p[1]], ["Expert A: pay", p[2], p[3]]];
    rows.forEach(function (r) {
      var tr = document.createElement("tr");
      cell(tr, r[0], true);
      cell(tr, (r[1] * 100).toFixed(1) + "% of items");
      cell(tr, (r[2] * 100).toFixed(1) + "% of items");
      tbody.appendChild(tr);
    });
    var rng = mulberry32(2024), ks = [];
    for (var i = 0; i < 400; i++) ks.push(session(rng, n, p));
    ks.sort(function (x, y) { return x - y; });
    var lo = ks[Math.floor(0.05 * ks.length)], hi = ks[Math.floor(0.95 * ks.length)];
    summary.textContent = "Raw agreement " + (m.po * 100).toFixed(1) + "%. Agreement expected by chance alone " + (m.pe * 100).toFixed(1) +
      "%. Kappa " + m.k.toFixed(2) + ". Across 400 repeat sessions of " + n + " items, kappa would land between " + lo.toFixed(2) + " and " + hi.toFixed(2) + " (5th to 95th percentile).";
    var W = 100; // percent scale for kappa from -0.2 to 1
    function pos(k) { return Math.max(0, Math.min(100, (k + 0.2) / 1.2 * W)); }
    bar.style.setProperty("--lo", pos(lo) + "%");
    bar.style.setProperty("--hi", pos(hi) + "%");
    bar.style.setProperty("--k", pos(m.k) + "%");
  }

  for (var k in ctl) ctl[k].addEventListener("input", update);
  update();
})();
