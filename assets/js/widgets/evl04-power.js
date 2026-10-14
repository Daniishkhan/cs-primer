/* Eval power explorer (A6 chapter 4).
   Two systems are compared on the same n questions. Per-question score variance for one
   system is v = p(1-p). Following Miller (2024), v splits into the variance of the question's
   true pass rate (one third of v when difficulty is spread uniformly) and answer noise
   (two thirds). Answer noise shrinks as 1/K when each question is answered K times; a
   correlation rho between the systems' question difficulties shrinks the paired variance. */
(function () {
  "use strict";
  var root = document.getElementById("evl04-power");
  if (!root) return;

  function q(n) { return root.querySelector("[data-act=" + n + "]"); }
  var inp = { n: q("n"), p: q("p"), rho: q("rho"), k: q("k"), gap: q("gap") };
  var out = { n: q("n-out"), p: q("p-out"), rho: q("rho-out"), k: q("k-out"), gap: q("gap-out") };
  var stats = root.querySelector(".evl04-stats");
  var chart = root.querySelector(".evl04-chart");
  var note = root.querySelector(".evl04-note");

  function erf(x) {
    var s = x < 0 ? -1 : 1; x = Math.abs(x);
    var t = 1 / (1 + 0.3275911 * x);
    var y = 1 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * Math.exp(-x * x);
    return s * y;
  }
  function cdf(z) { return 0.5 * (1 + erf(z / Math.SQRT2)); }

  function pct(x, d) { return (x * 100).toFixed(d === undefined ? 1 : d) + "%"; }

  function update() {
    var n = Math.round(Math.pow(10, parseFloat(inp.n.value)));
    var p = parseFloat(inp.p.value), rho = parseFloat(inp.rho.value);
    var K = parseInt(inp.k.value, 10), gap = parseFloat(inp.gap.value) / 100;
    out.n.textContent = n.toLocaleString("en-GB");
    out.p.textContent = pct(p, 0);
    out.rho.textContent = rho.toFixed(2);
    out.k.textContent = K;
    out.gap.textContent = (gap * 100).toFixed(1) + " points";

    var v = p * (1 - p);
    var varX = v / 3, noise = 2 * v / 3;
    var seOne = Math.sqrt((varX + noise / K) / n);
    var varPaired = (2 * varX * (1 - rho) + 2 * noise / K) / n;
    var varUnpaired = (2 * varX + 2 * noise / K) / n;
    var sePaired = Math.sqrt(varPaired), seUn = Math.sqrt(varUnpaired);
    var power = cdf(gap / sePaired - 1.96) + cdf(-gap / sePaired - 1.96);
    var mde = 2.8016 * sePaired;
    var nNeed = gap > 0 ? Math.ceil(Math.pow(2.8016, 2) * (2 * varX * (1 - rho) + 2 * noise / K) / (gap * gap)) : null;

    stats.innerHTML =
      row("Standard error of one system's score", pct(seOne, 2)) +
      row("Standard error of the gap, unpaired", pct(seUn, 2)) +
      row("Standard error of the gap, paired", pct(sePaired, 2)) +
      row("Chance of detecting the true gap (alpha 0.05)", pct(power, 0)) +
      row("Smallest gap detectable with 80% power", pct(mde, 1)) +
      row("Questions needed for 80% power at this gap", nNeed === null ? "any gap: set one above 0" : nNeed.toLocaleString("en-GB"));

    // interval chart: gap +/- 1.96 SE for paired and unpaired, on a shared axis
    var lim = Math.max(0.1, Math.abs(gap) + 2.2 * seUn, 0.04);
    function X(v2) { return 20 + (v2 + lim) / (2 * lim) * 520; }
    function bar(y, se, label, cls) {
      var lo = gap - 1.96 * se, hi = gap + 1.96 * se;
      return '<line x1="' + X(lo) + '" x2="' + X(hi) + '" y1="' + y + '" y2="' + y + '" class="' + cls + '" stroke-width="5" stroke-linecap="round"/>' +
        '<circle cx="' + X(gap) + '" cy="' + y + '" r="5" class="evl04-dot"/>' +
        '<text x="20" y="' + (y - 11) + '" class="evl04-lbl">' + label + ': ' + pct(lo, 1) + ' to ' + pct(hi, 1) + '</text>';
    }
    chart.innerHTML =
      '<line x1="' + X(0) + '" x2="' + X(0) + '" y1="14" y2="104" class="evl04-zero"/>' +
      bar(48, seUn, "Unpaired 95% interval", "evl04-un") +
      bar(88, sePaired, "Paired 95% interval", "evl04-pa") +
      '<text x="' + X(0) + '" y="116" text-anchor="middle" class="evl04-lbl">no difference</text>';

    var msg;
    if (gap === 0) msg = "With no true gap, about 5% of comparisons still look significant: that is the false-positive rate you chose.";
    else if (power >= 0.8) msg = "This design would usually detect a gap of this size.";
    else msg = "This design would miss a gap of this size more often than not. Add questions, raise the correlation by comparing on the same questions, or raise K.";
    note.textContent = msg;
  }
  function row(a, b) { return '<div class="evl04-row"><span>' + a + '</span><b>' + b + '</b></div>'; }

  Object.keys(inp).forEach(function (k) { inp[k].addEventListener("input", update); });
  update();
})();
