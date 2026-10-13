/* Fan-out cost explorer (design chapter 09).
   A scaled-down social graph: U users, mean followers A, follower counts Zipf-like:
     followers of the author at rank i = min(CAP, c * i^-s), with c chosen so the mean is A.
   The skew s is the slider; the celebrity threshold T is the second slider.
   Each user posts POSTS times a day and opens the feed `loads` times a day.
     push   : every post is inserted into every follower's timeline.      writes = POSTS * sum(f)
              a feed load reads one list.                                 reads/load = 1
     pull   : a post is stored once.                                      writes = POSTS * U
              a feed load fetches the recent posts of every followee.      reads/load = sum(f) / U
     hybrid : authors with f <= T are pushed, authors with f > T are pulled at read time.
              reads/load = 1 + (follow edges pointing at pulled authors) / U
   "Total ops" = writes + reads/load * U * loads. It counts every list insert and every list fetch
   as one operation, which flatters pull and hybrid a little (celebrity lists are hot and fetched in
   one parallel multiget) and ignores that inserts into many timelines are the bursty part.
   The same numbers come out of model09.py in the chapter. Pure functions are exported for Node. */
(function () {
  "use strict";

  var U = 100000, A = 100, CAP = U / 10, POSTS = 2;
  var cache = {};

  function followers(s) {
    var key = String(s);
    if (cache[key]) return cache[key];
    var lo = 0, hi = 1e12, c, i, total, f;
    for (var it = 0; it < 60; it++) {
      c = (lo + hi) / 2; total = 0;
      for (i = 1; i <= U; i++) total += Math.min(CAP, c * Math.pow(i, -s));
      if (total < A * U) lo = c; else hi = c;
    }
    f = new Array(U);
    for (i = 1; i <= U; i++) f[i - 1] = Math.min(CAP, c * Math.pow(i, -s));
    cache[key] = f;
    return f;
  }

  function costs(f, T, loads) {
    var edges = 0, pushedEdges = 0, pulledAuthors = 0, worstPushed = 0, i;
    for (i = 0; i < f.length; i++) {
      edges += f[i];
      if (f[i] <= T) { pushedEdges += f[i]; if (f[i] > worstPushed) worstPushed = f[i]; } else pulledAuthors++;
    }
    var celebEdges = edges - pushedEdges, out = {};
    out.push = { writes: POSTS * edges, reads: 1, worst: f[0] };
    out.pull = { writes: POSTS * U, reads: edges / U, worst: 1 };
    out.hybrid = { writes: POSTS * (pushedEdges + pulledAuthors), reads: 1 + celebEdges / U, worst: worstPushed, pulled: pulledAuthors };
    ["push", "pull", "hybrid"].forEach(function (k) { out[k].total = out[k].writes + out[k].reads * U * loads; });
    return out;
  }

  var core = { followers: followers, costs: costs, U: U, A: A, CAP: CAP, POSTS: POSTS };
  if (typeof module !== "undefined" && module.exports) module.exports = core;
  if (typeof document === "undefined") return;
  var root = document.getElementById("fanout-cost");
  if (!root) return;

  var NS = "http://www.w3.org/2000/svg";
  function el(tag, attrs, text) {
    var e = document.createElement(tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    return e;
  }
  function sv(tag, attrs, text) {
    var e = document.createElementNS(NS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    return e;
  }
  function fmt(v) {
    if (v >= 1e9) return (v / 1e9).toFixed(1) + "B";
    if (v >= 1e6) return (v / 1e6).toFixed(1) + "M";
    if (v >= 1e3) return (v / 1e3).toFixed(1) + "k";
    return v < 10 ? v.toFixed(1) : String(Math.round(v));
  }

  var S_VALUES = [0.6, 0.8, 1.0, 1.2, 1.4];
  var T_VALUES = [300, 1000, 3000, 10000];
  var L_VALUES = [1, 2, 5, 10, 20];
  var state = { si: 2, ti: 1, li: 3 };

  var head = el("div", { "class": "widget-head" });
  head.appendChild(el("span", { "class": "widget-tag" }, "Try it"));
  head.appendChild(el("h4", { "class": "widget-title" }, "Push, pull or hybrid: what does a post cost?"));
  root.appendChild(head);
  root.appendChild(el("p", { "class": "widget-help" },
    "A scaled-down network of 100,000 users who follow 100 accounts each on average. Raise the skew and a few accounts hold most of the followers. Lower the threshold and more authors are pulled at read time. The three bars compare the cost of one post's worst case, a feed load, and a whole day."));

  var ctl = el("div", { "class": "op-ctl" });
  var outs = {};
  function slider(key, label, n) {
    var w = el("div");
    var lab = el("label", { "for": "fc-" + key }, label + ": ");
    var out = el("output", { "for": "fc-" + key });
    lab.appendChild(out);
    var inp = el("input", { type: "range", id: "fc-" + key, min: "0", max: String(n - 1), step: "1", value: String(state[key]) });
    inp.addEventListener("input", function () { state[key] = parseInt(inp.value, 10); update(); });
    w.appendChild(lab); w.appendChild(inp); ctl.appendChild(w);
    outs[key] = out;
  }
  slider("si", "Follower skew s", S_VALUES.length);
  slider("ti", "Celebrity threshold (followers)", T_VALUES.length);
  slider("li", "Feed loads per user per day", L_VALUES.length);
  root.appendChild(ctl);

  var tiles = el("div", { "class": "op-tiles", "aria-live": "polite" });
  root.appendChild(tiles);
  var chart = el("div", { "class": "op-chart" });
  root.appendChild(chart);
  root.appendChild(el("p", { "class": "op-legend" },
    "Bars use a log scale. A model, not a measurement: it counts every list insert and fetch as one operation and assumes follows are proportional to popularity."));

  function tile(label, value, cls) {
    var d = el("div", { "class": "op-tile " + (cls || "") });
    d.appendChild(el("small", {}, label)); d.appendChild(el("b", {}, value));
    return d;
  }

  function update() {
    var s = S_VALUES[state.si], T = T_VALUES[state.ti], loads = L_VALUES[state.li];
    outs.si.textContent = s.toFixed(1);
    outs.ti.textContent = T >= CAP ? T + " (nobody is a celebrity: pure push)" : String(T);
    outs.li.textContent = String(loads);
    var f = followers(s), c = costs(f, T, loads);
    var top1 = 0, all = 0, i;
    for (i = 0; i < f.length; i++) { all += f[i]; if (i < U / 100) top1 += f[i]; }
    tiles.textContent = "";
    tiles.appendChild(tile("Top 1% of authors hold", Math.round(100 * top1 / all) + "% of follow edges"));
    tiles.appendChild(tile("Authors pulled at read time", c.hybrid.pulled.toLocaleString("en-US")));
    tiles.appendChild(tile("Worst post, push", fmt(c.push.worst) + " inserts", c.push.worst > 5000 ? "warn" : ""));
    tiles.appendChild(tile("Worst post, hybrid", fmt(c.hybrid.worst) + " inserts", "good"));
    var best = "push";
    ["pull", "hybrid"].forEach(function (k) { if (c[k].total < c[best].total) best = k; });
    tiles.appendChild(tile("Cheapest in total ops/day", best));
    draw(c);
  }

  function draw(c) {
    chart.textContent = "";
    var W = 700, H = 250, panels = [
      { title: "Worst single post (inserts)", key: "worst" },
      { title: "List fetches per feed load", key: "reads" },
      { title: "Total ops per day", key: "total" }
    ];
    var svg = sv("svg", { viewBox: "0 0 " + W + " " + H, role: "img",
      "aria-label": "Three bar charts comparing push, pull and hybrid fan-out on worst single post, fetches per feed load and total operations per day" });
    var names = [["push", "fs-blue"], ["pull", "fs-orange"], ["hybrid", "fs-green"]];
    var pw = 210, gap = 20, top = 34, base = 190, bh = base - top;
    panels.forEach(function (p, pi) {
      var x0 = 10 + pi * (pw + gap);
      var vals = names.map(function (n) { return Math.max(1, c[n[0]][p.key]); });
      var lmax = Math.max(1, Math.ceil(Math.log(Math.max.apply(null, vals)) / Math.LN10 + 0.01));
      svg.appendChild(sv("text", { x: x0, y: 18, "class": "t-sm t-bold" }, p.title));
      svg.appendChild(sv("line", { x1: x0, y1: base, x2: x0 + pw, y2: base, "class": "line" }));
      names.forEach(function (n, ni) {
        var v = vals[ni], h = Math.max(3, bh * Math.log(v) / Math.LN10 / lmax + 3);
        var bx = x0 + 14 + ni * 66;
        svg.appendChild(sv("rect", { x: bx, y: base - h, width: 50, height: h, rx: 4, "class": n[1] + " sw-2" }));
        svg.appendChild(sv("text", { x: bx + 25, y: base - h - 6, "text-anchor": "middle", "class": "t-xs t-bold" }, fmt(c[n[0]][p.key])));
        svg.appendChild(sv("text", { x: bx + 25, y: base + 16, "text-anchor": "middle", "class": "t-xs t-muted" }, n[0]));
      });
    });
    chart.appendChild(svg);
  }

  update();
})();
