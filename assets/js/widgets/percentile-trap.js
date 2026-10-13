/* Percentile trap (reliability chapter 4).

   Three hosts serve requests. Hosts 1 and 2 are healthy (lognormal latency, median about 40 ms).
   Host 3 is sick: same body, but 8% of its requests carry an extra 400-900 ms. The reader sets
   what share of all traffic host 3 receives, picks the quantile and a bucket layout.

   Shown:
     bars   - each host's own exact quantile
     red    - the average of the three per-host quantiles (the wrong way to combine them)
     green  - the exact quantile of all requests pooled together (the truth)
     blue   - the estimate you get from merging bucketed histograms (add counts per bucket,
              then interpolate linearly inside the bucket like PromQL's histogram_quantile)
   Bucket layouts: linear 100 ms, exponential x2 from 5 ms, exponential x1.25 from 5 ms,
   and linear 10 ms.

   Data are generated once with a seeded generator (mulberry32), 20,000 requests in total; the
   slider changes how many come from each host, so a given setting always shows the same picture.
   Latencies above the last bound fall in a +Inf bucket and are reported as the last bound
   (as Prometheus does). Illustrative numbers, not measurements. */
(function () {
  "use strict";
  var root = document.getElementById("percentile-trap");
  if (!root) return;
  var NS = "http://www.w3.org/2000/svg";
  var N = 20000;

  function mulberry32(a) {
    return function () {
      a |= 0; a = a + 0x6D2B79F5 | 0;
      var t = Math.imul(a ^ a >>> 15, 1 | a);
      t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
      return ((t ^ t >>> 14) >>> 0) / 4294967296;
    };
  }
  var rnd = mulberry32(4071);
  function gauss() {
    var u = 1 - rnd(), v = rnd();
    return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
  }
  function pool(mu, sigma, slow) {
    var a = [];
    for (var i = 0; i < N; i++) {
      var x = Math.exp(mu + sigma * gauss());
      if (slow && rnd() < slow) x += 400 + 500 * rnd();
      a.push(x);
    }
    return a;
  }
  var pools = [pool(Math.log(40), 0.35, 0), pool(Math.log(42), 0.35, 0), pool(Math.log(45), 0.4, 0.08)];

  function bounds(kind) {
    var b = [], x, i;
    if (kind === "lin100") { for (i = 1; i <= 10; i++) b.push(100 * i); }
    else if (kind === "lin10") { for (i = 1; i <= 100; i++) b.push(10 * i); }
    else if (kind === "exp2") { for (x = 5; x < 1500; x *= 2) b.push(x); }
    else { for (x = 5; x < 1500; x *= 1.25) b.push(x); }
    return b;
  }
  var NAMES = { lin100: "linear, 100 ms wide (10 buckets)", lin10: "linear, 10 ms wide (100 buckets)",
    exp2: "exponential, x2 (9 buckets)", exp125: "exponential, x1.25 (~30 buckets)" };

  function exactQ(sorted, q) {
    return sorted[Math.min(sorted.length - 1, Math.ceil(q * sorted.length) - 1)];
  }
  function histQ(q, b, counts) {
    var total = 0, i;
    for (i = 0; i < counts.length; i++) total += counts[i];
    var rank = q * total, cum = 0;
    for (i = 0; i < counts.length; i++) {
      if (cum + counts[i] >= rank) {
        if (i === b.length) return b[b.length - 1];
        var lo = i ? b[i - 1] : 0;
        return lo + (b[i] - lo) * (rank - cum) / counts[i];
      }
      cum += counts[i];
    }
    return b[b.length - 1];
  }
  function bucketOf(b, v) {
    var lo = 0, hi = b.length;
    while (lo < hi) { var m = (lo + hi) >> 1; if (b[m] >= v) hi = m; else lo = m + 1; }
    return lo;
  }

  function h(tag, attrs, text) {
    var e = document.createElement(tag);
    if (attrs) for (var k in attrs) { if (k === "class") e.className = attrs[k]; else e.setAttribute(k, attrs[k]); }
    if (text != null) e.textContent = text;
    return e;
  }
  function s(tag, attrs, text) {
    var e = document.createElementNS(NS, tag);
    if (attrs) for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (text != null) e.textContent = text;
    return e;
  }
  function clear(e) { while (e.firstChild) e.removeChild(e.firstChild); }
  function r1(x) { return (Math.round(x * 10) / 10).toFixed(1); }

  var head = h("div", { class: "widget-head" });
  head.appendChild(h("span", { class: "widget-tag" }, "Explore"));
  head.appendChild(h("h4", { class: "widget-title" }, "Average of p99s versus the true p99"));
  root.appendChild(head);
  root.appendChild(h("p", { class: "widget-help" }, "Host 3 is sick (8% of its requests are 400 to 900 ms slower). Change how much traffic it gets, the quantile and the bucket layout."));

  var ctl = h("div", { class: "pt-controls" });
  function field(label, node, extra) {
    var w = h("label", { class: "pt-ctl" });
    w.appendChild(h("span", { class: "pt-ctl-l" }, label));
    w.appendChild(node);
    if (extra) w.appendChild(extra);
    ctl.appendChild(w);
  }
  var rShare = h("input", { type: "range", min: 1, max: 50, value: 2, step: 1 });
  var vShare = h("span", { class: "pt-val" }, "2%");
  var selQ = h("select");
  [["0.5", "p50"], ["0.9", "p90"], ["0.99", "p99"], ["0.999", "p99.9"]].forEach(function (o) {
    var op = h("option", { value: o[0] }, o[1]); if (o[0] === "0.99") op.selected = true; selQ.appendChild(op);
  });
  var selB = h("select");
  [["lin100", NAMES.lin100], ["lin10", NAMES.lin10], ["exp2", NAMES.exp2], ["exp125", NAMES.exp125]].forEach(function (o) {
    selB.appendChild(h("option", { value: o[0] }, o[1]));
  });
  field("Host 3 traffic share", rShare, vShare);
  field("Quantile", selQ);
  field("Bucket layout", selB);
  root.appendChild(ctl);

  var box = h("div", { class: "pt-box" });
  var svg = s("svg", { viewBox: "0 0 720 300", role: "img", "aria-label": "Bar chart of each host's quantile with lines for the average of quantiles, the true pooled quantile and the histogram estimate" });
  box.appendChild(svg);
  root.appendChild(box);
  var out = h("div", { class: "widget-out pt-out", "aria-live": "polite" });
  root.appendChild(out);

  function render() {
    var share = parseInt(rShare.value, 10) / 100;
    vShare.textContent = rShare.value + "%";
    var q = parseFloat(selQ.value), kind = selB.value, b = bounds(kind);
    var ns = [Math.round(N * (1 - share) / 2), Math.round(N * (1 - share) / 2), Math.round(N * share)];
    var all = [], per = [], hists = [], tot = new Array(b.length + 1).fill(0), i, j;
    for (i = 0; i < 3; i++) {
      var xs = pools[i].slice(0, ns[i]);
      var hc = new Array(b.length + 1).fill(0);
      for (j = 0; j < xs.length; j++) { hc[bucketOf(b, xs[j])]++; all.push(xs[j]); }
      xs.sort(function (p, r) { return p - r; });
      per.push(exactQ(xs, q));
      hists.push(hc);
      for (j = 0; j < hc.length; j++) tot[j] += hc[j];
    }
    all.sort(function (p, r) { return p - r; });
    var truth = exactQ(all, q);
    var avg = (per[0] + per[1] + per[2]) / 3;
    var est = histQ(q, b, tot);

    var ymax = Math.max(100, Math.ceil(Math.max(per[0], per[1], per[2], avg, truth, est) * 1.12 / 100) * 100);
    var X0 = 62, X1 = 700, Y0 = 250, Y1 = 22;
    function y(v) { return Y0 - (Y0 - Y1) * v / ymax; }
    clear(svg);
    var step = ymax > 600 ? 200 : 100, v;
    for (v = 0; v <= ymax; v += step) {
      svg.appendChild(s("line", { x1: X0, x2: X1, y1: y(v), y2: y(v), class: "pt-grid" }));
      svg.appendChild(s("text", { x: X0 - 8, y: y(v) + 4, "text-anchor": "end", class: "pt-tick" }, String(v)));
    }
    svg.appendChild(s("text", { x: 14, y: 140, "text-anchor": "middle", class: "pt-tick", transform: "rotate(-90 14 140)" }, "latency (ms)"));
    var labels = ["Host 1 (" + ns[0] + " req)", "Host 2 (" + ns[1] + " req)", "Host 3, sick (" + ns[2] + " req)"];
    for (i = 0; i < 3; i++) {
      var bx = X0 + 40 + i * 130, bw = 70;
      svg.appendChild(s("rect", { x: bx, y: y(per[i]), width: bw, height: Y0 - y(per[i]), class: i === 2 ? "pt-bar sick" : "pt-bar" }));
      svg.appendChild(s("text", { x: bx + bw / 2, y: y(per[i]) - 5, "text-anchor": "middle", class: "pt-val-t" }, r1(per[i])));
      svg.appendChild(s("text", { x: bx + bw / 2, y: Y0 + 16, "text-anchor": "middle", class: "pt-tick" }, labels[i].split(" (")[0]));
      svg.appendChild(s("text", { x: bx + bw / 2, y: Y0 + 30, "text-anchor": "middle", class: "pt-tick faint" }, "n = " + ns[i]));
    }
    svg.appendChild(s("line", { x1: X0, x2: X1, y1: Y0, y2: Y0, class: "pt-axis" }));
    function hline(val, cls, label, ly) {
      svg.appendChild(s("line", { x1: X0, x2: 470, y1: y(val), y2: y(val), class: "pt-ref " + cls }));
      var lx = 480;
      svg.appendChild(s("line", { x1: 470, x2: lx, y1: y(val), y2: ly, class: "pt-lead " + cls }));
      svg.appendChild(s("text", { x: lx + 4, y: ly + 4, class: "pt-reflab " + cls }, label + " " + r1(val) + " ms"));
    }
    var order = [["avg", avg], ["truth", truth], ["est", est]].sort(function (p, r) { return r[1] - p[1]; });
    var slots = [60, 120, 180];
    order.forEach(function (o, k) {
      if (o[0] === "avg") hline(avg, "red", "avg of p's", slots[k]);
      if (o[0] === "truth") hline(truth, "green", "true pooled", slots[k]);
      if (o[0] === "est") hline(est, "blue", "histogram merge", slots[k]);
    });

    clear(out);
    function line(lbl, val, cls, note) {
      var p = h("p", { class: "pt-line" });
      p.appendChild(h("span", { class: "pill " + cls }, lbl));
      p.appendChild(document.createTextNode(" " + r1(val) + " ms" + (note || "")));
      out.appendChild(p);
    }
    line("average of 3 host quantiles", avg, "red", " (" + r1(avg / truth) + "x the truth)");
    line("exact pooled quantile", truth, "green", "");
    var err = 100 * (est - truth) / truth;
    line("merged histogram estimate", est, "blue", " (" + (err >= 0 ? "+" : "") + r1(err) + "% from the truth, " + NAMES[kind] + ")");
    out.appendChild(h("p", { class: "widget-help" }, "Try: with host 3 at 2% of traffic the average of p99s is several times too large. Then switch to p50 on the 100 ms layout and watch the bucket error appear instead."));
  }
  [rShare, selQ, selB].forEach(function (e) { e.addEventListener("input", render); e.addEventListener("change", render); });
  render();
})();
