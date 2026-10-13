/* Time-series cardinality explorer (design chapter 19).
   series for one metric = product of the distinct values of its labels (an upper bound: only combinations
   that actually occur create series). Memory uses an ASSUMED 4 KB per active series (labels, index entries,
   an open chunk), so the absolute numbers are illustrative; the multiplication is the point.
   A histogram metric multiplies series by its bucket count (one series per bucket, plus a sum and a count: 15 here). */
(function () {
  "use strict";

  var MEM_PER_SERIES = 4000;
  var LEVELS = {
    service:  [5, 20, 50, 200],
    endpoint: [5, 20, 40, 200],
    status:   [3, 6, 12],
    region:   [1, 3, 5, 12]
  };
  var EXTRA = [
    { name: "none", values: 1 },
    { name: "pod name (about 5,000)", values: 5000 },
    { name: "customer id (about 100,000)", values: 100000 },
    { name: "user id (about 1,000,000)", values: 1000000 }
  ];
  var LIMITS = [100000, 1000000, 10000000];

  function compute(s) {
    var base = 1;
    Object.keys(LEVELS).forEach(function (k) { base *= LEVELS[k][s[k]]; });
    var extra = EXTRA[s.extra].values;
    var buckets = s.hist ? 15 : 1;   /* 12 finite buckets + the +Inf bucket, plus a sum and a count */
    var perMetric = base * extra * buckets;
    return { base: base, extra: extra, buckets: buckets, series: perMetric * s.metrics, perMetric: perMetric,
             bytes: perMetric * s.metrics * MEM_PER_SERIES };
  }

  var core = { compute: compute, LEVELS: LEVELS, EXTRA: EXTRA, LIMITS: LIMITS };
  if (typeof module !== "undefined" && module.exports) module.exports = core;
  if (typeof document === "undefined") return;
  var root = document.getElementById("tsdb-cardinality");
  if (!root) return;

  function el(tag, attrs, text) {
    var e = document.createElement(tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    return e;
  }
  function fmt(v) {
    if (v >= 1e12) return (v / 1e12).toFixed(1) + "T";
    if (v >= 1e9) return (v / 1e9).toFixed(1) + "B";
    if (v >= 1e6) return (v / 1e6).toFixed(1) + "M";
    if (v >= 1e3) return (v / 1e3).toFixed(1) + "k";
    return String(Math.round(v));
  }
  function bytes(v) {
    if (v >= 1e12) return (v / 1e12).toFixed(1) + " TB";
    if (v >= 1e9) return (v / 1e9).toFixed(1) + " GB";
    if (v >= 1e6) return (v / 1e6).toFixed(0) + " MB";
    return Math.round(v / 1e3) + " KB";
  }

  var state = { service: 2, endpoint: 2, status: 1, region: 2, extra: 0, hist: false, metrics: 20, limit: 1 };

  var head = el("div", { "class": "widget-head" });
  head.appendChild(el("span", { "class": "widget-tag" }, "Try it"));
  head.appendChild(el("h4", { "class": "widget-title" }, "How many series does one label cost?"));
  root.appendChild(head);
  root.appendChild(el("p", { "class": "widget-help" },
    "Pick how many distinct values each label takes. The number of series is their product, multiplied by the number of metrics that carry the labels. Add an unbounded label such as a user id and watch the memory and the tenant limit."));

  var ctl = el("div", { "class": "dz-ctl" });
  var outs = {};
  function slider(key, label, n, fmtv) {
    var w = el("div");
    var lab = el("label", { "for": "tc-" + key }, label + ": ");
    var out = el("output", { "for": "tc-" + key });
    lab.appendChild(out);
    var inp = el("input", { type: "range", id: "tc-" + key, min: "0", max: String(n - 1), step: "1", value: String(state[key]) });
    inp.addEventListener("input", function () { state[key] = parseInt(inp.value, 10); update(); });
    w.appendChild(lab); w.appendChild(inp); ctl.appendChild(w);
    outs[key] = { out: out, fmt: fmtv };
  }
  Object.keys(LEVELS).forEach(function (k) {
    slider(k, "Distinct " + k + " values", LEVELS[k].length, function (i) { return String(LEVELS[k][i]); });
  });
  slider("extra", "Extra label", EXTRA.length, function (i) { return EXTRA[i].name; });
  slider("limit", "Tenant active-series limit", LIMITS.length, function (i) { return fmt(LIMITS[i]); });

  var wm = el("div");
  var lm = el("label", { "for": "tc-metrics" }, "Metrics using these labels: ");
  var om = el("output", { "for": "tc-metrics" });
  lm.appendChild(om);
  var im = el("input", { type: "range", id: "tc-metrics", min: "1", max: "100", step: "1", value: String(state.metrics) });
  im.addEventListener("input", function () { state.metrics = parseInt(im.value, 10); update(); });
  wm.appendChild(lm); wm.appendChild(im); ctl.appendChild(wm);

  var wh = el("div");
  var lh = el("label", { "class": "dz-check", "for": "tc-hist", style: "display:flex;gap:8px;align-items:center;cursor:pointer" });
  var ih = el("input", { type: "checkbox", id: "tc-hist" });
  ih.addEventListener("change", function () { state.hist = ih.checked; update(); });
  lh.appendChild(ih); lh.appendChild(document.createTextNode("These are histograms (about 15 series per label set)"));
  wh.appendChild(lh); ctl.appendChild(wh);
  root.appendChild(ctl);

  var tiles = el("div", { "class": "dz-tiles", "aria-live": "polite" });
  root.appendChild(tiles);
  var status = el("p", { "class": "dz-status", "aria-live": "polite" });
  root.appendChild(status);
  root.appendChild(el("p", { "class": "dz-legend" },
    "An upper bound: only label combinations that actually occur create series. Memory assumes about 4 KB per active series; real figures vary by system."));

  function tile(label, value, cls) {
    var d = el("div", { "class": "dz-tile " + (cls || "") });
    d.appendChild(el("small", {}, label)); d.appendChild(el("b", {}, value));
    return d;
  }

  function update() {
    Object.keys(outs).forEach(function (k) { outs[k].out.textContent = outs[k].fmt(state[k]); });
    om.textContent = String(state.metrics);
    var r = compute(state), limit = LIMITS[state.limit];
    tiles.textContent = "";
    tiles.appendChild(tile("Series per metric", fmt(r.perMetric)));
    tiles.appendChild(tile("Total active series", fmt(r.series), r.series > limit ? "bad" : "good"));
    tiles.appendChild(tile("Memory (assumed 4 KB each)", bytes(r.bytes), r.bytes > 5e11 ? "bad" : (r.bytes > 5e10 ? "warn" : "good")));
    tiles.appendChild(tile("Points per second at 10 s", fmt(r.series / 10)));
    if (r.series > limit) {
      status.textContent = "Over the limit of " + fmt(limit) + " series: new series are rejected while existing ones keep being accepted. Remove the unbounded label or move that dimension to logs or traces.";
    } else if (state.extra > 1) {
      status.textContent = "Within the limit for now, but an unbounded label means the count is set by traffic, not by design. It will keep growing.";
    } else {
      status.textContent = "Bounded labels only: the series count is a design-time number you can budget.";
    }
  }
  update();
})();
