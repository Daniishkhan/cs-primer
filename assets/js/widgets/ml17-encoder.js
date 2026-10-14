/* Target-encoding explorer (A1 chapter 17).
   A categorical column with 40 levels of uneven size. Each level has a true positive rate (all equal to 0.30 when the
   signal slider is 0). Labels are drawn for a training set; the page encodes each level by its mean label, shrunk
   towards the overall rate by a smoothing weight m, in one of three ways: in-sample, leave-one-out or out-of-fold.
   It plots the training encoding of every level against the level's size and reports the AUC of the encoded
   column alone on the training rows and on 20,000 fresh rows. */
(function () {
  "use strict";
  var root = document.getElementById("ml17-encoder");
  if (!root) return;
  var NS = "http://www.w3.org/2000/svg", K = 40, NTEST = 20000;
  var nIn = root.querySelector("[data-act=n]"), nOut = root.querySelector("[data-act=n-out]");
  var mIn = root.querySelector("[data-act=m]"), mOut = root.querySelector("[data-act=m-out]");
  var sIn = root.querySelector("[data-act=s]"), sOut = root.querySelector("[data-act=s-out]");
  var methodSel = root.querySelector("[data-act=method]");
  var svg = root.querySelector(".ml17-chart"), table = root.querySelector(".ml17-table"), note = root.querySelector(".ml17-note");

  function mulberry32(a) {
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      var t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  function gauss(r) { var u = 1 - r(), v = r(); return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v); }
  function sigmoid(z) { return 1 / (1 + Math.exp(-z)); }
  function el(tag, attrs, text) {
    var e = document.createElementNS(NS, tag), k;
    for (k in attrs) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    return e;
  }
  function auc(s, y) {
    var idx = s.map(function (_, i) { return i; }).sort(function (a, b) { return s[a] - s[b]; });
    var ranks = new Array(s.length), i = 0, j, k, n1 = 0, sum = 0;
    while (i < idx.length) {
      j = i;
      while (j + 1 < idx.length && s[idx[j + 1]] === s[idx[i]]) j++;
      for (k = i; k <= j; k++) ranks[idx[k]] = (i + j) / 2 + 1;
      i = j + 1;
    }
    for (i = 0; i < y.length; i++) if (y[i]) { n1++; sum += ranks[i]; }
    var n0 = y.length - n1;
    return n1 && n0 ? (sum - n1 * (n1 + 1) / 2) / (n1 * n0) : 0.5;
  }

  function update() {
    var perLevel = parseInt(nIn.value, 10), m = parseInt(mIn.value, 10), sig = parseInt(sIn.value, 10) / 100, method = methodSel.value;
    nOut.textContent = perLevel; mOut.textContent = m; sOut.textContent = sig.toFixed(2);
    var r = mulberry32(1701), i, k, f;
    var size = [], p = [];
    for (k = 0; k < K; k++) {
      size.push(Math.max(1, Math.round(perLevel * Math.exp(0.9 * gauss(r) - 0.4))));
      p.push(sigmoid(Math.log(0.3 / 0.7) + sig * gauss(r)));
    }
    var lev = [], y = [];
    for (k = 0; k < K; k++) for (i = 0; i < size[k]; i++) { lev.push(k); y.push(r() < p[k] ? 1 : 0); }
    var n = lev.length, prior = 0, cnt = [], sum = [];
    for (i = 0; i < n; i++) prior += y[i];
    prior /= n;
    for (k = 0; k < K; k++) { cnt.push(0); sum.push(0); }
    for (i = 0; i < n; i++) { cnt[lev[i]]++; sum[lev[i]] += y[i]; }
    function enc(c, s, pr) { return c + m > 0 ? (s + m * pr) / (c + m) : pr; }

    var trainEnc = [], levelEnc = [];
    for (k = 0; k < K; k++) levelEnc.push(enc(cnt[k], sum[k], prior));
    if (method === "insample") {
      for (i = 0; i < n; i++) trainEnc.push(levelEnc[lev[i]]);
    } else if (method === "loo") {
      for (i = 0; i < n; i++) trainEnc.push(cnt[lev[i]] > 1 ? enc(cnt[lev[i]] - 1, sum[lev[i]] - y[i], prior) : prior);
    } else {
      var fc = [], fs = [], fold = [], F = 5, fp = [];
      for (f = 0; f < F; f++) { fc.push([]); fs.push([]); for (k = 0; k < K; k++) { fc[f].push(0); fs[f].push(0); } }
      for (i = 0; i < n; i++) fold.push(i % F);
      for (i = 0; i < n; i++) for (f = 0; f < F; f++) if (fold[i] === f) { fc[f][lev[i]]++; fs[f][lev[i]] += y[i]; }
      for (f = 0; f < F; f++) {
        var tc = 0, ts = 0;
        for (k = 0; k < K; k++) { tc += cnt[k] - fc[f][k]; ts += sum[k] - fs[f][k]; }
        fp.push(ts / Math.max(1, tc));
      }
      for (i = 0; i < n; i++) { f = fold[i]; trainEnc.push(enc(cnt[lev[i]] - fc[f][lev[i]], sum[lev[i]] - fs[f][lev[i]], fp[f])); }
    }
    var testEnc = [], testY = [], r2 = mulberry32(99), lv;
    for (i = 0; i < NTEST; i++) { lv = Math.floor(r2() * K); testEnc.push(levelEnc[lv]); testY.push(r2() < p[lv] ? 1 : 0); }
    var aTrain = auc(trainEnc, y), aTest = auc(testEnc, testY);

    var W = 420, H = 300, L = 46, T = 14, PW = 356, PH = 230, maxN = Math.max.apply(null, cnt), lo = 0, hi = 1;
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    svg.setAttribute("viewBox", "0 0 " + W + " " + H);
    svg.appendChild(el("rect", { x: L, y: T, width: PW, height: PH, "class": "box", opacity: 0.35 }));
    function sx(c) { return L + (Math.log(c) / Math.log(Math.max(maxN, 2))) * (PW - 16) + 8; }
    function sy(v) { return T + PH - (v - lo) / (hi - lo) * PH; }
    [0, 0.25, 0.5, 0.75, 1].forEach(function (v) {
      svg.appendChild(el("text", { x: L - 6, y: sy(v) + 4, "text-anchor": "end", "class": "t-xs t-faint" }, v === 0 ? "0" : v === 1 ? "1" : v.toFixed(2)));
    });
    svg.appendChild(el("line", { x1: L, y1: sy(0.3), x2: L + PW, y2: sy(0.3), "class": "line-dash s-yellow" }));
    svg.appendChild(el("text", { x: L + PW - 4, y: sy(0.3) - 5, "text-anchor": "end", "class": "t-xs tc-yellow" }, "overall rate 0.30"));
    // one dot per level: a mean of the encoded value over that level's training rows
    var lsum = [], lcnt = [];
    for (k = 0; k < K; k++) { lsum.push(0); lcnt.push(0); }
    for (i = 0; i < n; i++) { lsum[lev[i]] += trainEnc[i]; lcnt[lev[i]]++; }
    for (k = 0; k < K; k++) {
      svg.appendChild(el("line", { x1: sx(cnt[k]), y1: sy(p[k]), x2: sx(cnt[k]), y2: sy(lsum[k] / lcnt[k]), "class": "line-thin", opacity: 0.55 }));
      svg.appendChild(el("circle", { cx: sx(cnt[k]), cy: sy(p[k]), r: 2.5, "class": "f-green" }));
      svg.appendChild(el("circle", { cx: sx(cnt[k]), cy: sy(lsum[k] / lcnt[k]), r: 3.5, "class": "f-blue" }));
    }
    svg.appendChild(el("text", { x: L + PW / 2, y: H - 6, "text-anchor": "middle", "class": "t-xs t-muted" }, "rows in the level (log scale, 1 to " + maxN + ")"));
    svg.appendChild(el("text", { x: 11, y: T + PH / 2, "text-anchor": "middle", "class": "t-xs t-muted", transform: "rotate(-90 11 " + (T + PH / 2) + ")" }, "positive rate"));
    svg.appendChild(el("circle", { cx: L + 10, cy: T + 12, r: 3.5, "class": "f-blue" }));
    svg.appendChild(el("text", { x: L + 18, y: T + 16, "class": "t-xs" }, "encoded value (average over the level's training rows)"));
    svg.appendChild(el("circle", { cx: L + 10, cy: T + 28, r: 2.5, "class": "f-green" }));
    svg.appendChild(el("text", { x: L + 18, y: T + 32, "class": "t-xs" }, "true rate of the level"));

    table.innerHTML = "<table class='ml17-t'><tbody><tr><th>Training rows</th><td>" + n + "</td></tr>" +
      "<tr><th>AUC of the column, train</th><td>" + aTrain.toFixed(3) + "</td></tr>" +
      "<tr><th>AUC of the column, fresh data</th><td>" + aTest.toFixed(3) + "</td></tr>" +
      "<tr><th>Gap (train minus fresh)</th><td>" + (aTrain - aTest >= 0 ? "+" : "") + (aTrain - aTest).toFixed(3) + "</td></tr></tbody></table>";
    var msg;
    if (sig === 0 && method === "insample" && m < 5) msg = "No level differs from any other, yet the training AUC is well above 0.5: small levels show whatever their few labels said, and the model is trained on the same labels. This is the gap the out-of-fold method removes.";
    else if (method === "loo") msg = "Leave-one-out removes the row's own label from its encoding, but then inside a level the encoding falls when the row is positive, a reversed copy of the label. Flexible models can read it; the training AUC drifts below its honest value.";
    else if (method === "oof") msg = "Each row is encoded from the other four folds only, so the training column no longer reads its own label and the train AUC sits near the fresh AUC (with very small levels a slight reversed bias remains, because a row and its level-mates share labels). Smoothing sets how far small levels are pulled to the overall rate.";
    else if (m >= 30) msg = "Heavy smoothing pulls small levels towards 0.30, which shrinks the gap, at the price of blurring real differences when the signal slider is high.";
    else msg = "In-sample encoding: every dot (blue) is the level's own training mean. Small levels land far from the true rate (green) in both directions.";
    note.textContent = msg;
  }
  [nIn, mIn, sIn].forEach(function (e) { e.addEventListener("input", update); });
  methodSel.addEventListener("change", update);
  update();
})();
