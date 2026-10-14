/* Risk-coverage explorer (A6 chapter 11).
   1,500 synthetic questions. Each has a true chance p of being answered correctly and a reported
   confidence = p + overconfidence + noise. The system answers only when confidence >= threshold.
   Coverage = share answered; risk = error rate among the answered; score = +1 for a right answer,
   minus the penalty for a wrong answer, 0 for "I don't know", averaged over all questions. */
(function () {
  "use strict";
  var root = document.getElementById("evl11-riskcov");
  if (!root) return;

  function q(n) { return root.querySelector("[data-act=" + n + "]"); }
  var inN = q("noise"), inO = q("over"), inP = q("pen"), inT = q("thr");
  var outN = q("noise-out"), outO = q("over-out"), outP = q("pen-out"), outT = q("thr-out");
  var chart = root.querySelector(".evl11-chart"), stats = root.querySelector(".evl11-stats"), note = root.querySelector(".evl11-note");

  function mulberry32(a) {
    return function () {
      a |= 0; a = a + 0x6D2B79F5 | 0;
      var t = Math.imul(a ^ a >>> 15, 1 | a);
      t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
      return ((t ^ t >>> 14) >>> 0) / 4294967296;
    };
  }
  var N = 1500, rnd = mulberry32(2026), P = [], G = [], U = [], i;
  function gauss() { var u = 1 - rnd(), v = rnd(); return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v); }
  for (i = 0; i < N; i++) { P.push(Math.pow(rnd(), 0.6)); G.push(gauss()); U.push(rnd()); }
  var OK = P.map(function (p, j) { return U[j] < p; });

  function pct(x) { return (x * 100).toFixed(1) + "%"; }
  function sgn(x) { return (x >= 0 ? "+" : "") + x.toFixed(3); }

  function update() {
    var sd = parseFloat(inN.value), over = parseFloat(inO.value), pen = parseFloat(inP.value), thr = parseFloat(inT.value);
    outN.textContent = (sd < 0.05 ? "sharp" : (sd > 0.2 ? "blurry" : "moderate")) + " (" + sd.toFixed(2) + ")";
    outO.textContent = over.toFixed(2);
    outP.textContent = pen.toFixed(1) + " points";
    outT.textContent = thr.toFixed(2);

    var conf = [], idx = [];
    for (i = 0; i < N; i++) { conf.push(Math.min(0.999, Math.max(0.001, P[i] + over + sd * G[i]))); idx.push(i); }
    idx.sort(function (a, b) { return conf[b] - conf[a]; });

    var pts = [], right = 0, wrong = 0, bestScore = -1e9, bestThr = 1, k;
    for (k = 0; k < N; k++) {
      if (OK[idx[k]]) right++; else wrong++;
      var sc = (right - pen * wrong) / N;
      if (sc > bestScore) { bestScore = sc; bestThr = conf[idx[k]]; }
      if (k % 10 === 9 || k === N - 1) pts.push([(k + 1) / N, wrong / (k + 1)]);
    }
    if (bestScore < 0) { bestScore = 0; bestThr = 1; }

    var ans = 0, ar = 0, aw = 0;
    for (i = 0; i < N; i++) if (conf[i] >= thr) { ans++; if (OK[i]) ar++; else aw++; }
    var cov = ans / N, risk = ans ? aw / ans : 0, score = (ar - pen * aw) / N;
    var always = (OK.filter(Boolean).length - pen * OK.filter(function (x) { return !x; }).length) / N;

    var W = 560, H = 240, L = 46, T = 12, B = 36, R = 12, YM = 0.5;
    function X(v) { return L + v * (W - L - R); }
    function Y(v) { return T + (1 - Math.min(v, YM) / YM) * (H - T - B); }
    var s = "", d = "";
    for (i = 0; i <= 5; i++) {
      s += '<line x1="' + L + '" x2="' + (W - R) + '" y1="' + Y(i * 0.1) + '" y2="' + Y(i * 0.1) + '" class="evl11-grid"/>' +
           '<text x="' + (L - 6) + '" y="' + (Y(i * 0.1) + 4) + '" text-anchor="end" class="evl11-lbl">' + (i * 10) + '%</text>';
    }
    for (i = 0; i <= 4; i++) s += '<text x="' + X(i / 4) + '" y="' + (H - 18) + '" text-anchor="middle" class="evl11-lbl">' + (i * 25) + '%</text>';
    s += '<text x="' + ((L + W - R) / 2) + '" y="' + (H - 3) + '" text-anchor="middle" class="evl11-lbl">coverage (share of questions answered)</text>' +
         '<text x="12" y="' + (T + 8) + '" class="evl11-lbl">error among answered</text>';
    pts.forEach(function (p, j) { d += (j ? "L" : "M") + X(p[0]).toFixed(1) + "," + Y(p[1]).toFixed(1); });
    s += '<path d="' + d + '" class="evl11-curve"/>';
    if (ans) s += '<circle cx="' + X(cov) + '" cy="' + Y(risk) + '" r="6" class="evl11-dot"/>';
    chart.innerHTML = s;

    stats.innerHTML =
      row("Coverage at this threshold", pct(cov)) +
      row("Error among answered questions", ans ? pct(risk) : "no answers") +
      row("Score at this threshold", sgn(score)) +
      row("Score if it always answers", sgn(always)) +
      row("Best achievable score, and its confidence cut-off", sgn(bestScore) + (bestScore > 0 ? " at " + bestThr.toFixed(2) : " (abstain on everything)"));
    if (pen > 0 && always < 0 && score > always) note.textContent = "Answering everything now loses points; abstaining on the doubtful questions turns a negative score into a positive one.";
    else if (bestScore === 0 && pen >= 3) note.textContent = "At this penalty the confidence scores cannot find a set of answers reliable enough: the best policy is to say 'I don't know' to everything.";
    else if (over > 0.2) note.textContent = "High overconfidence pushes every score towards 1, so the cut-off that works is much higher than the break-even confidence of 1 / (1 + penalty) would suggest.";
    else note.textContent = "Move the threshold: the dot slides along the curve. A lower threshold answers more questions and makes more mistakes.";
  }
  function row(a, b) { return '<div class="evl11-row"><span>' + a + '</span><b>' + b + '</b></div>'; }
  [inN, inO, inP, inT].forEach(function (el) { el.addEventListener("input", update); });
  update();
})();
