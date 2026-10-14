/* Attention explorers (A2 chapter 09).
   Widget 1 (#dl09-attention): six keys sit in the plane; a query arrow points somewhere.
   Weights = softmax(beta * q.k), output = weighted average of the values (the key positions).
   Optional causal mask hides keys after the query's position.
   Widget 2 (#dl09-scale): random queries and keys of width d_k; shows how the softmax
   saturates as d_k grows unless scores are divided by sqrt(d_k). */
(function () {
  "use strict";
  var NS = "http://www.w3.org/2000/svg";

  function el(tag, attrs, text) {
    var e = document.createElementNS(NS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    return e;
  }
  function clear(n) { while (n.firstChild) n.removeChild(n.firstChild); }
  function mulberry32(a) {
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      var t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  function gauss(rng) {
    var u = 1 - rng(), v = rng();
    return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
  }
  function softmax(s, allowed) {
    var m = -Infinity, i, sum = 0, p = [];
    for (i = 0; i < s.length; i++) if (allowed[i] && s[i] > m) m = s[i];
    for (i = 0; i < s.length; i++) { p[i] = allowed[i] ? Math.exp(s[i] - m) : 0; sum += p[i]; }
    for (i = 0; i < s.length; i++) p[i] /= sum;
    return p;
  }

  /* ---------- widget 1: soft lookup in the plane ---------- */
  (function () {
    var root = document.getElementById("dl09-attention");
    if (!root) return;
    var q = function (sel) { return root.querySelector(sel); };
    var angIn = q("[data-act=angle]"), betaIn = q("[data-act=beta]"), posSel = q("[data-act=pos]"), maskChk = q("[data-act=mask]");
    var angOut = q("[data-act=angle-out]"), betaOut = q("[data-act=beta-out]");
    var svg = q(".dl09-chart"), out = q(".dl09-summary");
    var words = ["the", "cat", "sat", "on", "the", "mat"];
    var radii = [1.0, 0.7, 0.9, 0.6, 1.0, 0.8];
    var angles = [25, 85, 140, 200, 255, 320];
    var keys = words.map(function (w, i) {
      var a = angles[i] * Math.PI / 180;
      return [radii[i] * Math.cos(a), radii[i] * Math.sin(a)];
    });

    function draw() {
      var deg = parseFloat(angIn.value), beta = Math.pow(10, parseFloat(betaIn.value));
      var pos = parseInt(posSel.value, 10), masked = maskChk.checked;
      angOut.textContent = deg.toFixed(0) + "°";
      betaOut.textContent = beta.toFixed(2);
      var a = deg * Math.PI / 180, qv = [Math.cos(a), Math.sin(a)];
      var scores = keys.map(function (k) { return beta * (qv[0] * k[0] + qv[1] * k[1]); });
      var allowed = keys.map(function (k, j) { return !masked || j <= pos; });
      var p = softmax(scores, allowed), ox = 0, oy = 0, j;
      for (j = 0; j < p.length; j++) { ox += p[j] * keys[j][0]; oy += p[j] * keys[j][1]; }
      clear(svg);
      var cx = 170, cy = 150, R = 110;
      svg.appendChild(el("circle", { cx: cx, cy: cy, r: R, fill: "none", "class": "line-thin" }));
      svg.appendChild(el("line", { x1: cx - R - 10, y1: cy, x2: cx + R + 10, y2: cy, "class": "line-thin" }));
      svg.appendChild(el("line", { x1: cx, y1: cy - R - 10, x2: cx, y2: cy + R + 10, "class": "line-thin" }));
      svg.appendChild(el("line", { x1: cx, y1: cy, x2: cx + R * qv[0], y2: cy - R * qv[1], "class": "s-orange sw-3" }));
      svg.appendChild(el("text", { x: cx + (R + 12) * qv[0], y: cy - (R + 12) * qv[1] + 4, "text-anchor": "middle", "class": "t-xs tc-orange t-bold" }, "q"));
      for (j = 0; j < keys.length; j++) {
        var kx = cx + R * keys[j][0], ky = cy - R * keys[j][1];
        var off = !allowed[j];
        svg.appendChild(el("circle", { cx: kx, cy: ky, r: off ? 5 : 5 + 14 * p[j], "class": off ? "box" : "f-blue", opacity: off ? 0.5 : 0.85 }));
        svg.appendChild(el("text", { x: kx, y: ky - (9 + 14 * p[j]), "text-anchor": "middle", "class": "t-xs " + (off ? "t-faint" : "") }, words[j]));
      }
      svg.appendChild(el("circle", { cx: cx + R * ox, cy: cy - R * oy, r: 7, "class": "fs-yellow s-yellow sw-2" }));
      svg.appendChild(el("text", { x: cx + R * ox + 12, y: cy - R * oy + 16, "class": "t-xs t-bold" }, "output"));
      // bars
      var bx = 360, bw = 230, rowH = 38, top = 28;
      svg.appendChild(el("text", { x: bx, y: 16, "class": "t-xs t-muted" }, "attention weight of query on each key"));
      for (j = 0; j < keys.length; j++) {
        var y = top + j * rowH;
        svg.appendChild(el("text", { x: bx, y: y + 17, "class": "t-xs" }, (j + 1) + " " + words[j]));
        svg.appendChild(el("rect", { x: bx + 62, y: y + 4, width: bw, height: 18, rx: 3, "class": "box" }));
        if (p[j] > 0) svg.appendChild(el("rect", { x: bx + 62, y: y + 4, width: Math.max(1, bw * p[j]), height: 18, rx: 3, "class": "f-blue" }));
        svg.appendChild(el("text", { x: bx + 62 + bw + 8, y: y + 18, "class": "t-xs mono" }, allowed[j] ? p[j].toFixed(2) : "masked"));
      }
      var best = 0;
      for (j = 1; j < p.length; j++) if (p[j] > p[best]) best = j;
      out.textContent = "Output = (" + ox.toFixed(2) + ", " + oy.toFixed(2) + "), a weighted average of the six values. The largest weight (" + p[best].toFixed(2) + ") is on \"" + words[best] + "\"." +
        (masked ? " With the causal mask, query position " + (pos + 1) + " cannot see tokens after itself." : "");
    }
    [angIn, betaIn].forEach(function (c) { c.addEventListener("input", draw); });
    [posSel, maskChk].forEach(function (c) { c.addEventListener("change", draw); });
    draw();
  })();

  /* ---------- widget 2: why divide by sqrt(d_k) ---------- */
  (function () {
    var root = document.getElementById("dl09-scale");
    if (!root) return;
    var q = function (sel) { return root.querySelector(sel); };
    var dkSel = q("[data-act=dk]"), scaleChk = q("[data-act=scale]");
    var svg = q(".dl09-chart"), out = q(".dl09-summary");
    var N = 10, TRIALS = 300;

    function draw() {
      var dk = parseInt(dkSel.value, 10), scaled = scaleChk.checked;
      var rng = mulberry32(7 + dk), t, i, d, sumMax = 0, sumSq = 0, cnt = 0, first = null;
      for (t = 0; t < TRIALS; t++) {
        var qv = [], s = [], ok = [];
        for (d = 0; d < dk; d++) qv.push(gauss(rng));
        for (i = 0; i < N; i++) {
          var dot = 0;
          for (d = 0; d < dk; d++) dot += qv[d] * gauss(rng);
          if (scaled) dot /= Math.sqrt(dk);
          s.push(dot); ok.push(true); sumSq += dot * dot; cnt++;
        }
        var p = softmax(s, ok), mx = 0;
        for (i = 0; i < N; i++) if (p[i] > mx) mx = p[i];
        sumMax += mx;
        if (t === 0) first = p;
      }
      clear(svg);
      var bx = 20, bw = 560, rowH = 20;
      svg.appendChild(el("text", { x: bx, y: 14, "class": "t-xs t-muted" }, "one example: attention weights of a single query over 10 keys"));
      for (i = 0; i < N; i++) {
        var y = 24 + i * rowH;
        svg.appendChild(el("text", { x: bx, y: y + 13, "class": "t-xs mono" }, "key " + (i + 1)));
        svg.appendChild(el("rect", { x: bx + 56, y: y + 2, width: bw, height: 14, rx: 3, "class": "box" }));
        svg.appendChild(el("rect", { x: bx + 56, y: y + 2, width: Math.max(1, bw * first[i]), height: 14, rx: 3, "class": scaled ? "f-blue" : "f-orange" }));
        svg.appendChild(el("text", { x: bx + 56 + bw + 8, y: y + 13, "class": "t-xs mono" }, first[i].toFixed(3)));
      }
      var sd = Math.sqrt(sumSq / cnt), avgMax = sumMax / TRIALS;
      out.textContent = "d_k = " + dk + (scaled ? ", scores divided by √d_k" : ", raw scores") +
        ". Standard deviation of a score: " + sd.toFixed(2) + ". Average largest weight over " + TRIALS + " queries: " + avgMax.toFixed(2) +
        " (uniform would be " + (1 / N).toFixed(2) + ")." +
        (avgMax > 0.8 ? " The softmax is nearly one-hot: almost no gradient reaches the other keys." : "");
    }
    dkSel.addEventListener("change", draw);
    scaleChk.addEventListener("change", draw);
    draw();
  })();
})();
