/* pass@k versus pass^k explorer (A6 chapter 8).
   Tasks differ in how reliably the agent solves them. Model the per-task success chance p as a
   Beta(a, b) distribution with a chosen mean m and "spread" s (low s = tasks are all-or-nothing,
   high s = every task has about the same chance). For k independent trials of a task:
     pass@k = 1 - E[(1-p)^k]   (at least one success)
     pass^k = E[p^k]           (every trial succeeds)
   Expectations are computed by numerical integration over a grid of p values. */
(function () {
  "use strict";
  var root = document.getElementById("evl08-passk");
  if (!root) return;

  function q(n) { return root.querySelector("[data-act=" + n + "]"); }
  var inM = q("m"), inS = q("s"), inK = q("k"), inC = q("c");
  var outM = q("m-out"), outS = q("s-out"), outK = q("k-out"), outC = q("c-out");
  var chart = root.querySelector(".evl08-chart");
  var stats = root.querySelector(".evl08-stats");
  var note = root.querySelector(".evl08-note");
  var KMAX = 16, GRID = 400;

  function lgamma(x) {
    var c = [76.18009172947146, -86.50532032941677, 24.01409824083091, -1.231739572450155, 0.001208650973866179, -0.000005395239384953];
    var y = x, t = x + 5.5, s = 1.000000000190015, j;
    t -= (x + 0.5) * Math.log(t);
    for (j = 0; j < 6; j++) { y += 1; s += c[j] / y; }
    return -t + Math.log(2.5066282746310005 * s / x);
  }

  function weights(a, b) {
    var w = [], tot = 0, i, p, v;
    for (i = 0; i < GRID; i++) {
      p = (i + 0.5) / GRID;
      v = Math.exp((a - 1) * Math.log(p) + (b - 1) * Math.log(1 - p) + lgamma(a + b) - lgamma(a) - lgamma(b));
      w.push(v); tot += v;
    }
    for (i = 0; i < GRID; i++) w[i] /= tot;
    return w;
  }

  function curves(m, conc) {
    var a = m * conc, b = (1 - m) * conc, w = weights(a, b), res = { at: [], hat: [] }, k, i, p, e1, e2;
    for (k = 1; k <= KMAX; k++) {
      e1 = 0; e2 = 0;
      for (i = 0; i < GRID; i++) {
        p = (i + 0.5) / GRID;
        e1 += w[i] * Math.pow(1 - p, k);
        e2 += w[i] * Math.pow(p, k);
      }
      res.at.push(1 - e1); res.hat.push(e2);
    }
    return res;
  }

  function pct(x) { return (x * 100).toFixed(1) + "%"; }

  function update() {
    var m = parseFloat(inM.value), conc = Math.pow(10, parseFloat(inS.value));
    var k = parseInt(inK.value, 10), cost = parseFloat(inC.value);
    outM.textContent = pct(m);
    outS.textContent = conc < 2.5 ? "all-or-nothing tasks" : (conc > 40 ? "every task alike" : "mixed");
    outK.textContent = k;
    outC.textContent = "$" + cost.toFixed(2);
    var r = curves(m, conc);

    var W = 560, H = 230, L = 44, T = 14, B = 34, R = 12;
    function X(kk) { return L + (kk - 1) / (KMAX - 1) * (W - L - R); }
    function Y(v) { return T + (1 - v) * (H - T - B); }
    var s = "", i, d1 = "", d2 = "";
    for (i = 0; i <= 4; i++) {
      s += '<line x1="' + L + '" x2="' + (W - R) + '" y1="' + Y(i / 4) + '" y2="' + Y(i / 4) + '" class="evl08-grid"/>' +
           '<text x="' + (L - 6) + '" y="' + (Y(i / 4) + 4) + '" text-anchor="end" class="evl08-lbl">' + (i * 25) + '%</text>';
    }
    for (i = 1; i <= KMAX; i += (i === 1 ? 3 : 4)) {
      s += '<text x="' + X(i) + '" y="' + (H - 14) + '" text-anchor="middle" class="evl08-lbl">' + i + '</text>';
    }
    s += '<text x="' + ((L + W - R) / 2) + '" y="' + (H - 1) + '" text-anchor="middle" class="evl08-lbl">k (trials per task)</text>';
    for (i = 0; i < KMAX; i++) {
      d1 += (i ? "L" : "M") + X(i + 1).toFixed(1) + "," + Y(r.at[i]).toFixed(1);
      d2 += (i ? "L" : "M") + X(i + 1).toFixed(1) + "," + Y(r.hat[i]).toFixed(1);
    }
    s += '<path d="' + d1 + '" class="evl08-at"/><path d="' + d2 + '" class="evl08-hat"/>' +
         '<line x1="' + X(k) + '" x2="' + X(k) + '" y1="' + T + '" y2="' + (H - B) + '" class="evl08-mark"/>' +
         '<circle cx="' + X(k) + '" cy="' + Y(r.at[k - 1]) + '" r="4.5" class="evl08-dat"/>' +
         '<circle cx="' + X(k) + '" cy="' + Y(r.hat[k - 1]) + '" r="4.5" class="evl08-dhat"/>' +
         '<text x="' + (W - R - 4) + '" y="' + (Y(r.at[KMAX - 1]) - 7) + '" text-anchor="end" class="evl08-lbl evl08-tat">pass@k</text>' +
         '<text x="' + (W - R - 4) + '" y="' + (Y(r.hat[KMAX - 1]) - 7) + '" text-anchor="end" class="evl08-lbl evl08-that">pass^k</text>';
    chart.innerHTML = s;

    var perSuccess = cost / m;
    stats.innerHTML =
      row("pass@" + k + " (at least one success)", pct(r.at[k - 1])) +
      row("pass^" + k + " (all " + k + " succeed)", pct(r.hat[k - 1])) +
      row("Single-try success (k = 1, same for both)", pct(m)) +
      row("Cost per success with one try per task", "$" + perSuccess.toFixed(3));

    if (k === 1) note.textContent = "At k = 1 the two metrics are the same number. They only part ways when the agent gets more than one try.";
    else if (r.hat[k - 1] < 0.5 * m) note.textContent = "pass^" + k + " is below half of the single-try score: a customer who comes back " + k + " times will meet a failure far more often than the headline number suggests.";
    else note.textContent = "Tasks with similar chances make pass^k fall smoothly; tasks that are all-or-nothing keep it flat. Move the spread slider to see the difference.";
  }
  function row(a, b) { return '<div class="evl08-row"><span>' + a + '</span><b>' + b + '</b></div>'; }

  [inM, inS, inK, inC].forEach(function (el) { el.addEventListener("input", update); });
  update();
})();
