/* Approximate nearest-neighbour explorer (retrieval chapter 11).
   260 points in 2D. Mode "IVF": k-means cells, probe the nprobe cells nearest to the query.
   Mode "Graph": a k-nearest-neighbour graph searched best-first with a beam of size ef,
   optionally started from a sparse upper layer (the HNSW idea). Click the plot to move the query. */
(function () {
  "use strict";
  var root = document.getElementById("ret11-ann");
  if (!root) return;

  var NS = "http://www.w3.org/2000/svg";
  var W = 400, H = 300, N = 260, NCELL = 12;
  var PAL = ["var(--blue)", "var(--green)", "var(--orange)", "var(--purple)", "var(--cyan)", "var(--pink)"];

  var svg = root.querySelector(".an-plot");
  var modeSel = root.querySelector("[data-act=mode]");
  var pIn = root.querySelector("[data-act=nprobe]");
  var pOut = root.querySelector("[data-act=nprobe-out]");
  var eIn = root.querySelector("[data-act=ef]");
  var eOut = root.querySelector("[data-act=ef-out]");
  var uChk = root.querySelector("[data-act=upper]");
  var rndBtn = root.querySelector("[data-act=random]");
  var boxP = root.querySelector("[data-box=nprobe]");
  var boxE = root.querySelector("[data-box=ef]");
  var boxU = root.querySelector("[data-box=upper]");
  var out = root.querySelector(".an-out");

  function mulberry32(a) {
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      var t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  var rng = mulberry32(2024);
  function gauss() {
    var u = 1 - rng(), v = rng();
    return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
  }

  // ---- data: points in blobs
  var pts = [], i, j, c;
  var blobs = [];
  for (i = 0; i < 9; i++) blobs.push([40 + rng() * 320, 35 + rng() * 230, 14 + rng() * 14]);
  for (i = 0; i < N; i++) {
    var b = blobs[Math.floor(rng() * blobs.length)];
    pts.push([Math.max(8, Math.min(W - 8, b[0] + gauss() * b[2])), Math.max(8, Math.min(H - 8, b[1] + gauss() * b[2]))]);
  }
  function d2(a, b2) { var dx = a[0] - b2[0], dy = a[1] - b2[1]; return dx * dx + dy * dy; }

  // ---- IVF: k-means
  var cent = [];
  for (i = 0; i < NCELL; i++) cent.push(pts[Math.floor(i * N / NCELL + rng() * (N / NCELL))].slice());
  var cell = new Array(N);
  var it;
  for (it = 0; it < 10; it++) {
    for (i = 0; i < N; i++) {
      var bc = 0, bd = 1e18;
      for (c = 0; c < NCELL; c++) { var dd = d2(pts[i], cent[c]); if (dd < bd) { bd = dd; bc = c; } }
      cell[i] = bc;
    }
    for (c = 0; c < NCELL; c++) {
      var sx = 0, sy = 0, n = 0;
      for (i = 0; i < N; i++) if (cell[i] === c) { sx += pts[i][0]; sy += pts[i][1]; n++; }
      if (n) cent[c] = [sx / n, sy / n];
    }
  }

  // ---- graph layers: kNN graphs (undirected)
  function knnGraph(ids, k) {
    var adj = {}, a, b2;
    ids.forEach(function (id) { adj[id] = []; });
    ids.forEach(function (a1) {
      var arr = ids.filter(function (x) { return x !== a1; })
        .map(function (x) { return [d2(pts[a1], pts[x]), x]; })
        .sort(function (p, q) { return p[0] - q[0]; }).slice(0, k);
      arr.forEach(function (p) {
        if (adj[a1].indexOf(p[1]) < 0) adj[a1].push(p[1]);
        if (adj[p[1]].indexOf(a1) < 0) adj[p[1]].push(a1);
      });
    });
    return adj;
  }
  // k-nearest-neighbour graphs of clustered data fall apart into islands; join the islands by
  // their closest pair (real HNSW avoids this with its neighbour-selection heuristic and layers).
  function connect(adj, ids) {
    while (true) {
      var seen = {}, stack = [ids[0]], comp = [];
      seen[ids[0]] = true;
      while (stack.length) {
        var x = stack.pop(); comp.push(x);
        adj[x].forEach(function (y) { if (!seen[y]) { seen[y] = true; stack.push(y); } });
      }
      if (comp.length === ids.length) return;
      var bd = 1e18, ba = -1, bb = -1;
      comp.forEach(function (a) {
        ids.forEach(function (b) { if (!seen[b]) { var dd = d2(pts[a], pts[b]); if (dd < bd) { bd = dd; ba = a; bb = b; } } });
      });
      adj[ba].push(bb); adj[bb].push(ba);
    }
  }
  var allIds = [], upIds = [];
  for (i = 0; i < N; i++) allIds.push(i);
  for (i = 0; i < N; i += 10) upIds.push(i);
  var base = knnGraph(allIds, 4), upper = knnGraph(upIds, 3);
  connect(base, allIds); connect(upper, upIds);
  var ENTRY = 0;                                  // fixed entry point, as in HNSW

  function nearestSorted(q) {
    return allIds.map(function (x) { return [d2(pts[x], q), x]; }).sort(function (p, r) { return p[0] - r[0]; });
  }

  // ---- query
  var query = [300, 70];

  function ivfSearch(q, nprobe) {
    var order = [];
    for (c = 0; c < NCELL; c++) order.push([d2(cent[c], q), c]);
    order.sort(function (p, r) { return p[0] - r[0]; });
    var probed = {};
    for (c = 0; c < nprobe; c++) probed[order[c][1]] = true;
    var scanned = [];
    for (i = 0; i < N; i++) if (probed[cell[i]]) scanned.push(i);
    return { probed: probed, scanned: scanned, cost: NCELL + scanned.length };
  }

  function greedy(adj, start, q) {
    var cur = start, path = [start], better = true;
    var visited = {}; visited[start] = true;
    var calls = 1;
    while (better) {
      better = false;
      var cd = d2(pts[cur], q);
      adj[cur].forEach(function (nb) {
        calls++;
        var dd = d2(pts[nb], q);
        if (dd < cd - 1e-9) { cd = dd; cur = nb; better = true; }
      });
      if (better) path.push(cur);
    }
    return { node: cur, path: path, calls: calls };
  }

  function beam(adj, start, q, ef) {
    var visited = {}; visited[start] = true;
    var cand = [[d2(pts[start], q), start]], best = [[d2(pts[start], q), start]];
    var calls = 1;
    while (cand.length) {
      cand.sort(function (p, r) { return p[0] - r[0]; });
      var cur = cand.shift();
      best.sort(function (p, r) { return p[0] - r[0]; });
      if (best.length >= ef && cur[0] > best[best.length - 1][0]) break;
      adj[cur[1]].forEach(function (nb) {
        if (visited[nb]) return;
        visited[nb] = true; calls++;
        var dd = d2(pts[nb], q);
        if (best.length < ef || dd < best[best.length - 1][0]) {
          cand.push([dd, nb]); best.push([dd, nb]);
          best.sort(function (p, r) { return p[0] - r[0]; });
          if (best.length > ef) best.pop();
        }
      });
    }
    return { best: best, visited: visited, calls: calls };
  }

  function el(tag, attrs) {
    var e = document.createElementNS(NS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    return e;
  }

  function draw() {
    var mode = modeSel.value;
    var nprobe = parseInt(pIn.value, 10), ef = parseInt(eIn.value, 10);
    pOut.textContent = String(nprobe); eOut.textContent = String(ef);
    boxP.style.display = mode === "ivf" ? "" : "none";
    boxE.style.display = mode === "graph" ? "" : "none";
    boxU.style.display = mode === "graph" ? "" : "none";
    var truth = nearestSorted(query), trueNN = truth[0][1];
    var top5 = truth.slice(0, 5).map(function (p) { return p[1]; });
    while (svg.firstChild) svg.removeChild(svg.firstChild);

    var scannedSet = {}, found = [], cost = 0, extra = "";
    var path = [];
    if (mode === "ivf") {
      var r = ivfSearch(query, nprobe);
      r.scanned.forEach(function (x) { scannedSet[x] = true; });
      found = r.scanned.map(function (x) { return [d2(pts[x], query), x]; }).sort(function (p, s) { return p[0] - s[0]; }).slice(0, 5);
      cost = r.cost;
      for (c = 0; c < NCELL; c++) if (r.probed[c]) svg.appendChild(el("circle", { cx: cent[c][0], cy: cent[c][1], r: 5, fill: "none", stroke: "var(--yellow)", "stroke-width": 2 }));
    } else {
      var start = ENTRY, upCalls = 0;
      if (uChk.checked) {
        var g = greedy(upper, upIds[0], query);
        start = g.node; path = g.path; upCalls = g.calls;
      }
      var bm = beam(base, start, query, ef);
      Object.keys(bm.visited).forEach(function (x) { scannedSet[x] = true; });
      found = bm.best.slice(0, 5);
      cost = bm.calls + upCalls;
      extra = uChk.checked ? " (including " + upCalls + " on the sparse upper layer)" : "";
      // edges
      allIds.forEach(function (a) {
        base[a].forEach(function (b2) {
          if (a < b2) svg.appendChild(el("line", { x1: pts[a][0], y1: pts[a][1], x2: pts[b2][0], y2: pts[b2][1], stroke: "var(--border-strong)", "stroke-width": 0.6, opacity: 0.55 }));
        });
      });
      for (i = 0; i + 1 < path.length; i++) svg.appendChild(el("line", { x1: pts[path[i]][0], y1: pts[path[i]][1], x2: pts[path[i + 1]][0], y2: pts[path[i + 1]][1], stroke: "var(--yellow)", "stroke-width": 2.5 }));
      svg.appendChild(el("rect", { x: pts[start][0] - 5, y: pts[start][1] - 5, width: 10, height: 10, fill: "none", stroke: "var(--purple)", "stroke-width": 2 }));
    }
    for (i = 0; i < N; i++) {
      var on = !!scannedSet[i];
      svg.appendChild(el("circle", { cx: pts[i][0], cy: pts[i][1], r: on ? 3.4 : 2.3,
        fill: mode === "ivf" ? PAL[cell[i] % PAL.length] : (on ? "var(--orange)" : "var(--text-faint)"),
        opacity: on ? 1 : 0.4 }));
    }
    found.forEach(function (p) { svg.appendChild(el("circle", { cx: pts[p[1]][0], cy: pts[p[1]][1], r: 6, fill: "none", stroke: "var(--green)", "stroke-width": 2 })); });
    svg.appendChild(el("circle", { cx: pts[trueNN][0], cy: pts[trueNN][1], r: 9, fill: "none", stroke: "var(--red)", "stroke-width": 1.5, "stroke-dasharray": "3 2" }));
    var qx = query[0], qy = query[1];
    svg.appendChild(el("path", { d: "M" + (qx - 7) + "," + qy + " H" + (qx + 7) + " M" + qx + "," + (qy - 7) + " V" + (qy + 7), stroke: "var(--yellow)", "stroke-width": 3 }));

    var got = found.filter(function (p) { return top5.indexOf(p[1]) >= 0; }).length;
    var hitNN = found.length && found[0][1] === trueNN;
    out.textContent = "Distance computations: " + cost + extra + " of " + N + " for brute force (" + Math.round(100 * cost / N) + "%). " +
      "Nearest neighbour found: " + (hitNN ? "yes" : "no") + ". True top 5 recovered: " + got + " of 5.";
  }

  svg.addEventListener("click", function (ev) {
    var rc = svg.getBoundingClientRect();
    query = [(ev.clientX - rc.left) / rc.width * W, (ev.clientY - rc.top) / rc.height * H];
    draw();
  });
  [modeSel, pIn, eIn, uChk].forEach(function (e) { e.addEventListener("input", draw); e.addEventListener("change", draw); });
  rndBtn.addEventListener("click", function () { query = [10 + rng() * (W - 20), 10 + rng() * (H - 20)]; draw(); });
  draw();
})();
