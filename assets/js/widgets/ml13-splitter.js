/* Split-scheme explorer (A1 chapter 13).
   48 rows in time order, 12 patients with 4 visits each, 6 positives. The reader picks a splitting scheme and the
   number of folds; every fold is drawn as a row of cells (train, validation, or embargoed gap) and three leak counts
   are reported: patients seen on both sides, validation rows older than the newest training row, and positives per fold. */
(function () {
  "use strict";
  var root = document.getElementById("ml13-splitter");
  if (!root) return;

  var NS = "http://www.w3.org/2000/svg";
  var N = 48, G = 12;
  var schemeSel = root.querySelector("[data-act=scheme]");
  var kIn = root.querySelector("[data-act=k]"), kOut = root.querySelector("[data-act=k-out]");
  var gapIn = root.querySelector("[data-act=gap]"), gapOut = root.querySelector("[data-act=gap-out]");
  var svg = root.querySelector(".ml13-chart");
  var stats = root.querySelector(".ml13-stats");
  var tip = root.querySelector(".ml13-tip");

  function mulberry32(a) {
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      var t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  function shuffle(arr, rng) {
    var a = arr.slice(), i, j, t;
    for (i = a.length - 1; i > 0; i--) { j = Math.floor(rng() * (i + 1)); t = a[i]; a[i] = a[j]; a[j] = t; }
    return a;
  }
  function range(n) { var r = [], i; for (i = 0; i < n; i++) r.push(i); return r; }

  // fixed data: group of each row (patients return again and again over time) and which rows are positive
  var rng0 = mulberry32(1313), group = [], i;
  var pool = [];
  for (i = 0; i < N; i++) pool.push(i % G);
  group = shuffle(pool, rng0);
  var posIdx = shuffle(range(N), rng0).slice(0, 6), isPos = [];
  for (i = 0; i < N; i++) isPos.push(posIdx.indexOf(i) >= 0);

  function chunks(arr, k) {  // split into k nearly equal parts
    var out = [], p, start = 0, size;
    for (p = 0; p < k; p++) { size = Math.floor(arr.length / k) + (p < arr.length % k ? 1 : 0); out.push(arr.slice(start, start + size)); start += size; }
    return out;
  }

  function makeFolds(scheme, k, gap) {
    var rng = mulberry32(99), folds = [], f, part, p;
    if (scheme === "random") {
      part = chunks(shuffle(range(N), rng), k);
      for (f = 0; f < k; f++) folds.push({ val: part[f], gap: [] });
    } else if (scheme === "strat") {
      var buckets = [];
      for (f = 0; f < k; f++) buckets.push([]);
      var pos = shuffle(range(N).filter(function (r) { return isPos[r]; }), rng);
      var neg = shuffle(range(N).filter(function (r) { return !isPos[r]; }), rng), c = 0;
      pos.forEach(function (r) { buckets[c++ % k].push(r); });
      neg.forEach(function (r) { buckets[c++ % k].push(r); });
      for (f = 0; f < k; f++) folds.push({ val: buckets[f], gap: [] });
    } else if (scheme === "group") {
      var gids = shuffle(range(G), rng), gp = chunks(gids, k);
      for (f = 0; f < k; f++) folds.push({ val: range(N).filter(function (r) { return gp[f].indexOf(group[r]) >= 0; }), gap: [] });
    } else {  // time: expanding window, k test blocks at the end
      var test = Math.floor(N / (k + 1)), first = N - k * test;
      for (f = 0; f < k; f++) {
        var vs = first + f * test, v = [], g = [];
        for (p = vs; p < vs + test; p++) v.push(p);
        for (p = Math.max(0, vs - gap); p < vs; p++) g.push(p);
        folds.push({ val: v, gap: g, trainEnd: vs - gap });
      }
    }
    return folds;
  }

  function el(tag, attrs, text) {
    var e = document.createElementNS(NS, tag), key;
    for (key in attrs) e.setAttribute(key, attrs[key]);
    if (text !== undefined) e.textContent = text;
    return e;
  }

  function update() {
    var scheme = schemeSel.value, k = parseInt(kIn.value, 10), gap = parseInt(gapIn.value, 10);
    kOut.textContent = String(k); gapOut.textContent = String(gap);
    gapIn.disabled = scheme !== "time";
    var folds = makeFolds(scheme, k, gap);
    var L = 56, cw = 13.2, ch = 16, rowH = 24, top = 30;
    var W = L + N * cw + 8, H = top + folds.length * rowH + 30;
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    svg.setAttribute("viewBox", "0 0 " + W + " " + H);
    svg.appendChild(el("text", { x: L, y: 10, "class": "t-xs t-muted" }, "rows in time order: oldest on the left"));
    var r, f, shareTotal = 0, laterTotal = 0, posList = [], minPos = 99;
    // header: patient id of each row
    for (r = 0; r < N; r++) {
      svg.appendChild(el("text", { x: L + r * cw + cw / 2, y: top - 6, "text-anchor": "middle", "class": "t-faint", "font-size": 7.5 }, String(group[r] + 1)));
    }
    for (f = 0; f < folds.length; f++) {
      var fd = folds[f], y = top + f * rowH, valSet = {}, gapSet = {}, trainRows = [];
      fd.val.forEach(function (x) { valSet[x] = true; });
      fd.gap.forEach(function (x) { gapSet[x] = true; });
      svg.appendChild(el("text", { x: L - 8, y: y + 12, "text-anchor": "end", "class": "t-xs t-muted" }, "fold " + (f + 1)));
      for (r = 0; r < N; r++) {
        var cls, inTrain = false;
        if (valSet[r]) cls = "f-orange";
        else if (gapSet[r]) cls = "f-yellow";
        else if (scheme === "time" && r >= fd.trainEnd) cls = "box";
        else { cls = "f-blue"; inTrain = true; trainRows.push(r); }
        var rect = el("rect", { x: L + r * cw + 0.5, y: y, width: cw - 1.5, height: ch, rx: 2, "class": cls, opacity: cls === "box" ? 0.35 : (cls === "f-yellow" ? 0.55 : 0.9) });
        svg.appendChild(rect);
        if (isPos[r]) svg.appendChild(el("circle", { cx: L + r * cw + cw / 2 - 0.2, cy: y + ch / 2, r: 2.6, "class": "f-red", stroke: "var(--bg)", "stroke-width": 0.8 }));
      }
      // leak counts for this fold
      var trainGroups = {}, share = 0, later = 0, maxTrain = -1, np = 0;
      trainRows.forEach(function (x) { trainGroups[group[x]] = true; if (x > maxTrain) maxTrain = x; });
      var seen = {};
      fd.val.forEach(function (x) { if (trainGroups[group[x]] && !seen[group[x]]) { seen[group[x]] = true; share++; } if (x < maxTrain) later++; if (isPos[x]) np++; });
      shareTotal += share; laterTotal += later; posList.push(np); if (np < minPos) minPos = np;
    }
    var yl = top + folds.length * rowH + 14;
    svg.appendChild(el("rect", { x: L, y: yl - 9, width: 10, height: 10, rx: 2, "class": "f-blue" }));
    svg.appendChild(el("text", { x: L + 15, y: yl, "class": "t-xs" }, "train"));
    svg.appendChild(el("rect", { x: L + 62, y: yl - 9, width: 10, height: 10, rx: 2, "class": "f-orange" }));
    svg.appendChild(el("text", { x: L + 77, y: yl, "class": "t-xs" }, "validation"));
    svg.appendChild(el("rect", { x: L + 150, y: yl - 9, width: 10, height: 10, rx: 2, "class": "f-yellow", opacity: 0.55 }));
    svg.appendChild(el("text", { x: L + 165, y: yl, "class": "t-xs" }, "gap (dropped)"));
    svg.appendChild(el("circle", { cx: L + 262, cy: yl - 4, r: 3, "class": "f-red" }));
    svg.appendChild(el("text", { x: L + 270, y: yl, "class": "t-xs" }, "positive row"));
    svg.appendChild(el("text", { x: W - 8, y: yl, "text-anchor": "end", "class": "t-xs t-faint" }, "digits on top: patient id"));

    var nF = folds.length, msgs = [];
    msgs.push("<strong>Patients on both sides of the split</strong> (summed over folds): " + shareTotal + " of " + (nF * G) + " possible. " +
      (shareTotal === 0 ? "No patient is ever seen in training and validation: the model is scored on people it has not met." : "The model is being tested on patients it already trained on."));
    msgs.push("<strong>Validation rows older than the newest training row</strong> (summed over folds): " + laterTotal + ". " +
      (laterTotal === 0 ? "Every validation row lies in the training data's future, as it will in production." : "The model learns from the future of some rows it is scored on."));
    msgs.push("<strong>Positives per validation fold</strong>: " + posList.join(", ") + (minPos === 0 ? ". A fold with none cannot score recall, precision or AUC." : "."));
    stats.innerHTML = "<ul><li>" + msgs.join("</li><li>") + "</li></ul>";
    tip.textContent = ({
      random: "Random k-fold: every row is equally likely to land anywhere. Fine when rows are independent and the future looks like the past; leaky when patients repeat or time matters.",
      strat: "Stratified k-fold: the positives are dealt out evenly, so each fold has about the same rate. It protects the metric from empty folds but not from repeated patients or time.",
      group: "Group k-fold: all rows of a patient stay together. Validation scores now describe how the model treats patients it has never seen.",
      time: "Time-series split: train on the past, validate on the next block, then grow the training window. The gap drops rows just before the validation block, for labels that take time to arrive."
    })[scheme];
  }
  schemeSel.addEventListener("change", update);
  kIn.addEventListener("input", update);
  gapIn.addEventListener("input", update);
  update();
})();
