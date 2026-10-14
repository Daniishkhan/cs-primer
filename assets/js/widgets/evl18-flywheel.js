/* Improvement-flywheel simulator (A6 chapter 18).
   40 failure modes with long-tailed frequencies; together they fail 8% of requests.
   Each week the team reads some traces (failing traces are 5 times more likely to be read), fixes the most
   frequent discovered modes it has capacity for, and ships. Three teams are compared over 16 weeks:
   no process (nothing is fixed); fixes without regression tests (a fixed mode returns with some chance each
   week, because a later change quietly undoes the fix); and the full flywheel (every fix gets a regression
   test that blocks the release which would bring it back). Expected values, with seeded discovery draws. */
(function () {
  "use strict";
  var root = document.getElementById("evl18-flywheel");
  if (!root) return;
  function q(n) { return root.querySelector("[data-act=" + n + "]"); }
  var inR = q("reads"), inF = q("fixes"), inB = q("back"), outR = q("reads-out"), outF = q("fixes-out"), outB = q("back-out");
  var chart = root.querySelector(".evl18-chart"), key = root.querySelector(".evl18-key"), note = root.querySelector(".evl18-note");

  function mulberry32(a) {
    return function () {
      a |= 0; a = a + 0x6D2B79F5 | 0;
      var t = Math.imul(a ^ a >>> 15, 1 | a);
      t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
      return ((t ^ t >>> 14) >>> 0) / 4294967296;
    };
  }
  var M = 40, WEEKS = 16, N = 2000, TOTAL = 0.08, E = 5, i, w, rate = [], z = 0;
  for (i = 0; i < M; i++) { rate.push(1 / (i + 1)); z += rate[i]; }
  for (i = 0; i < M; i++) rate[i] = TOTAL * rate[i] / z;
  var rnd = mulberry32(18), D = [], R = [];
  for (w = 0; w < WEEKS; w++) { D.push([]); R.push([]); for (i = 0; i < M; i++) { D[w].push(rnd()); R[w].push(rnd()); } }

  function simulate(reads, fixes, back, tests) {
    var fixed = [], series = [], last = [];
    for (i = 0; i < M; i++) fixed.push(false);
    for (w = 0; w < WEEKS; w++) {
      var f = 0, found = [];
      for (i = 0; i < M; i++) if (!fixed[i]) f += rate[i];
      series.push(f);
      var denom = E * TOTAL + (1 - TOTAL);
      for (i = 0; i < M; i++) {
        if (fixed[i]) continue;
        var seen = reads * (E * rate[i]) / denom;
        if (D[w][i] < 1 - Math.exp(-seen)) found.push(i);
      }
      var n = 0;
      for (i = 0; i < found.length && n < fixes; i++) { fixed[found[i]] = true; n++; }
      if (!tests) for (i = 0; i < M; i++) if (fixed[i] && R[w][i] < back) fixed[i] = false;
    }
    var kept = 0; for (i = 0; i < M; i++) if (fixed[i]) kept++;
    return { s: series, kept: kept };
  }

  function update() {
    var reads = parseInt(inR.value, 10), fixes = parseInt(inF.value, 10), back = parseFloat(inB.value);
    outR.textContent = reads + " traces a week";
    outF.textContent = fixes + (fixes === 1 ? " mode a week" : " modes a week");
    outB.textContent = Math.round(back * 100) + "% a week";
    var a = { s: [], kept: 0 }; for (w = 0; w < WEEKS; w++) a.s.push(TOTAL);
    var b = simulate(reads, fixes, back, false), c = simulate(reads, fixes, back, true);
    var W = 560, H = 250, L = 46, T = 12, B = 38, Rr = 12, YM = 0.09;
    function X(k) { return L + k / (WEEKS - 1) * (W - L - Rr); }
    function Y(v) { return T + (1 - v / YM) * (H - T - B); }
    var s = "", k;
    for (k = 0; k <= 4; k++) {
      var v = k * 0.02;
      s += '<line x1="' + L + '" x2="' + (W - Rr) + '" y1="' + Y(v) + '" y2="' + Y(v) + '" class="evl18-grid"/>' +
           '<text x="' + (L - 6) + '" y="' + (Y(v) + 4) + '" text-anchor="end" class="evl18-lbl">' + (k * 2) + '%</text>';
    }
    for (k = 0; k < WEEKS; k += 3) s += '<text x="' + X(k) + '" y="' + (H - 20) + '" text-anchor="middle" class="evl18-lbl">' + (k + 1) + '</text>';
    s += '<text x="' + ((L + W - Rr) / 2) + '" y="' + (H - 4) + '" text-anchor="middle" class="evl18-lbl">week</text>' +
         '<text x="10" y="' + (T + 8) + '" class="evl18-lbl">requests that fail</text>';
    function path(arr, cls) {
      var d = ""; for (k = 0; k < arr.length; k++) d += (k ? "L" : "M") + X(k).toFixed(1) + "," + Y(arr[k]).toFixed(1);
      return '<path d="' + d + '" class="' + cls + '"/>';
    }
    s += path(a.s, "evl18-l0") + path(b.s, "evl18-l1") + path(c.s, "evl18-l2");
    chart.innerHTML = s;
    function pct(x) { return (x * 100).toFixed(1) + "%"; }
    key.innerHTML =
      '<span><i style="background:var(--red)"></i>No process <b>' + pct(a.s[WEEKS - 1]) + '</b></span>' +
      '<span><i style="background:var(--orange)"></i>Fixes, no regression tests <b>' + pct(b.s[WEEKS - 1]) + '</b> (' + b.kept + ' modes still fixed)</span>' +
      '<span><i style="background:var(--green)"></i>Full flywheel <b>' + pct(c.s[WEEKS - 1]) + '</b> (' + c.kept + ' modes fixed and tested)</span>';
    if (reads === 0 || fixes === 0) note.textContent = "With no reading or no fixing there is nothing to put into the suite: the loop only turns when traces are read and fixes follow.";
    else if (back === 0) note.textContent = "If fixes never regressed, tests would add nothing here: the two lines coincide. Raise the regression rate to see what the suite protects.";
    else if (b.s[WEEKS - 1] > c.s[WEEKS - 1] * 1.5) note.textContent = "Without tests, fixed failures keep coming back after later changes, so the failure rate stays well above the flywheel's.";
    else note.textContent = "The flywheel line only goes down: each fixed failure stays fixed. Try fewer reads and notice that discovery, not fixing, becomes the limit.";
  }
  [inR, inF, inB].forEach(function (el) { el.addEventListener("input", update); });
  update();
})();
