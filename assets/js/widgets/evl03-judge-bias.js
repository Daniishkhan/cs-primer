/* Judge-bias simulator (A6 chapter 3).
   System X is truly a little better than system Y (mean quality 1.3 vs 1.0)
   but writes shorter answers. A simulated pairwise judge scores each answer as
   quality + length bonus (+ position bonus for the answer shown first) + noise.
   Every pair is judged twice, with the order swapped. */
(function () {
  "use strict";
  var root = document.getElementById("evl03-judge-bias");
  if (!root) return;

  var posIn = root.querySelector("[data-act=pos]");
  var lenIn = root.querySelector("[data-act=len]");
  var gapIn = root.querySelector("[data-act=gap]");
  var posOut = root.querySelector("[data-act=pos-out]");
  var lenOut = root.querySelector("[data-act=len-out]");
  var gapOut = root.querySelector("[data-act=gap-out]");
  var bars = root.querySelector(".evl03-bars");
  var note = root.querySelector(".evl03-note");
  var N = 3000;

  function mulberry32(a) {
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      var t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  function simulate(pos, len, gap) {
    var rng = mulberry32(2024);
    function gauss() {
      var u = Math.max(rng(), 1e-12), v = rng();
      return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
    }
    var lx = 80, ly = 80 + gap, noise = 0.6;
    function judgeFirstWins(qFirst, qSecond, lFirst, lSecond) {
      var sa = qFirst + len * lFirst / 100 + pos + noise * gauss();
      var sb = qSecond + len * lSecond / 100 + noise * gauss();
      return sa > sb;
    }
    var xFirst = 0, xSecond = 0, disagree = 0;
    for (var i = 0; i < N; i++) {
      var qx = 1.3 + gauss(), qy = 1.0 + gauss();
      var w1 = judgeFirstWins(qx, qy, lx, ly);        // X shown first
      var w2 = !judgeFirstWins(qy, qx, ly, lx);       // X shown second: X wins if the first-shown answer (Y) loses
      if (w1) xFirst++;
      if (w2) xSecond++;
      if (w1 !== w2) disagree++;
    }
    return { first: xFirst / N, second: xSecond / N, disagree: disagree / N };
  }

  function bar(label, value, cls) {
    var pct = (value * 100).toFixed(1);
    return '<div><div class="evl03-bar-label"><span>' + label + '</span><b>' + pct + '%</b></div>' +
      '<div class="evl03-track"><div class="evl03-fill ' + cls + '" style="width:' + pct + '%"></div><div class="evl03-mid"></div></div></div>';
  }

  function update() {
    var pos = parseFloat(posIn.value), len = parseFloat(lenIn.value), gap = parseInt(gapIn.value, 10);
    posOut.textContent = pos.toFixed(2);
    lenOut.textContent = len.toFixed(2);
    gapOut.textContent = gap + " words";
    var r = simulate(pos, len, gap);
    var avg = (r.first + r.second) / 2;
    bars.innerHTML =
      bar("X wins when X is shown first", r.first, "") +
      bar("X wins when X is shown second", r.second, "") +
      bar("X win rate averaged over both orders", avg, avg < 0.5 ? "low" : "avg");
    var msg = "The judge disagrees with itself on " + (r.disagree * 100).toFixed(0) + "% of pairs when the order is swapped. ";
    if (Math.abs(r.first - r.second) > 0.1) msg += "Position bias is large: a single-order comparison would mislead, while averaging both orders cancels most of it. ";
    if (avg < 0.5) msg += "Even after averaging, X looks worse than Y, although X is truly better: the judge is rewarding length, and swapping the order cannot remove that.";
    else if (len > 0.2 && gap > 0) msg += "Length bias is shrinking X's apparent edge (the true edge gives about 57% at no bias).";
    else msg += "With little bias the averaged rate sits near 57%, the true advantage of X.";
    note.textContent = msg;
  }

  [posIn, lenIn, gapIn].forEach(function (el) { el.addEventListener("input", update); });
  update();
})();
