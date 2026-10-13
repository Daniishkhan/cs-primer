/* Napkin calculator (design chapter 02).

   Type in daily active users, actions per user, object sizes and a few ratios;
   the widget shows average and peak QPS, storage per year with replication,
   peak bandwidth, a cache size from the 80/20 rule, and a rough machine count.
   Then it prints sanity-check remarks, comparing each number with the
   order-of-magnitude capacities from the chapter (one relational primary, one
   cache node, one network link). Those capacities are rough rules of thumb that
   vary by an order of magnitude with hardware and workload: use them to pick
   a design direction, not to size a purchase order.

   The pure function compute() is exported for testing under Node. */
(function () {
  "use strict";

  var DAY = 86400;

  function compute(p) {
    var r = {};
    r.readsDay = p.dau * p.readsPer;
    r.writesDay = p.dau * p.writesPer;
    r.readAvg = r.readsDay / DAY;
    r.writeAvg = r.writesDay / DAY;
    r.readPeak = r.readAvg * p.peak;
    r.writePeak = r.writeAvg * p.peak;
    r.ratio = r.writesDay > 0 ? r.readsDay / r.writesDay : Infinity;
    r.newBytesDay = r.writesDay * p.writeKB * 1e3;
    r.rawYear = r.newBytesDay * 365;
    r.replYear = r.rawYear * p.repl;
    r.retained = r.replYear * p.years;
    r.rawTotal = r.rawYear * p.years;
    r.egressBps = r.readPeak * p.readKB * 1e3 * 8;
    r.originBps = r.egressBps * (1 - p.hit);
    r.cacheBytes = r.newBytesDay * p.cacheDays * p.hotFrac;
    r.servers = Math.ceil((r.readPeak + r.writePeak) / (p.boxQps * p.headroom)) + 1;
    return r;
  }

  function human(n, unit) {
    var t = [[1e15, "P"], [1e12, "T"], [1e9, "G"], [1e6, "M"], [1e3, "k"]], i;
    if (!isFinite(n)) return "n/a";
    function trim(x) { return String(parseFloat(x.toPrecision(3))); }
    for (i = 0; i < t.length; i++) if (Math.abs(n) >= t[i][0]) return trim(n / t[i][0]) + " " + t[i][1] + unit;
    return (n >= 100 ? Math.round(n) : trim(n)) + " " + unit;
  }

  function remarks(p, r) {
    var out = [];
    if (r.writePeak <= 1000) out.push("Peak writes of " + human(r.writePeak, "/s") + " are within what one relational primary handles (order of magnitude: a few thousand simple writes/s). No sharding needed for writes.");
    else if (r.writePeak <= 10000) out.push("Peak writes of " + human(r.writePeak, "/s") + " are near the limit of one well-tuned primary. Batch, queue the bursts, or plan a partition key.");
    else out.push("Peak writes of " + human(r.writePeak, "/s") + " exceed one primary. Partition the data, or use a log-structured or wide-column store, and decide the partition key early.");
    if (r.readPeak <= 20000) out.push("Reads of " + human(r.readPeak, "/s") + " could be served by a few replicas or a single cache node.");
    else if (r.readPeak <= 200000) out.push("Reads of " + human(r.readPeak, "/s") + " call for a cache tier (one in-memory node serves very roughly 100k simple ops/s) in front of the database.");
    else out.push("Reads of " + human(r.readPeak, "/s") + " need a sharded cache and likely a CDN or edge cache; a single node cannot take this.");
    if (r.rawTotal > 2e13) out.push("One copy of the retained data is " + human(r.rawTotal, "B") + ", far beyond one database host. Think object storage for blobs and partitioning for the rest.");
    else if (r.rawTotal > 2e12) out.push("One copy of the retained data is " + human(r.rawTotal, "B") + ", awkward on one host. Partition, or move cold data out.");
    else out.push("One copy of the retained data is " + human(r.rawTotal, "B") + ", which fits on one modern server's disks, so storage alone does not force sharding.");
    if (r.egressBps > 10e9) out.push("Peak egress of " + human(r.egressBps, "bit/s") + " exceeds one 10 Gbit/s link: you need many front ends, and almost certainly a CDN.");
    else if (r.egressBps > 1e9) out.push("Peak egress of " + human(r.egressBps, "bit/s") + " is more than one 1 Gbit/s link. Several servers, or a CDN to take the load.");
    else out.push("Peak egress of " + human(r.egressBps, "bit/s") + " is modest.");
    if (p.writesPer * 20 > p.readsPer && p.writesPer > 0) out.push("The read:write ratio is only " + Math.round(r.ratio) + ":1. This is not strongly read-heavy, so caching helps less and write capacity matters more.");
    return out;
  }

  var core = { compute: compute, human: human, remarks: remarks };
  if (typeof module !== "undefined" && module.exports) module.exports = core;
  if (typeof document === "undefined") return;
  var root = document.getElementById("napkin-calc");
  if (!root) return;

  var FIELDS = [
    ["dau", "Daily active users", 1e7, 1e3, null],
    ["readsPer", "Reads per user per day", 20, 0, null],
    ["writesPer", "Writes per user per day", 0.2, 0, null],
    ["peak", "Peak-to-average factor", 3, 1, null],
    ["readKB", "KB sent per read", 10, 0, null],
    ["writeKB", "KB stored per write", 10, 0, null],
    ["repl", "Replication factor", 3, 1, null],
    ["years", "Years retained", 5, 1, null],
    ["hit", "Cache / CDN hit ratio (0 to 1)", 0.9, 0, 1],
    ["hotFrac", "Hot fraction to cache (0 to 1)", 0.2, 0, 1],
    ["cacheDays", "Days of data the cache spans", 30, 1, null],
    ["boxQps", "QPS one server handles flat out", 2000, 1, null],
    ["headroom", "Target utilisation (0 to 1)", 0.5, 0.05, 1]
  ];
  var PRESETS = {
    paste: { name: "Pastebin", dau: 1e7, readsPer: 2, writesPer: 0.1, peak: 3, readKB: 10, writeKB: 10, repl: 3, years: 5, hit: 0.9, hotFrac: 0.2, cacheDays: 30, boxQps: 2000, headroom: 0.5 },
    chat: { name: "Chat (text only)", dau: 5e7, readsPer: 80, writesPer: 40, peak: 4, readKB: 0.2, writeKB: 0.2, repl: 3, years: 5, hit: 0.5, hotFrac: 0.1, cacheDays: 7, boxQps: 5000, headroom: 0.5 },
    photo: { name: "Photo sharing", dau: 2e7, readsPer: 30, writesPer: 0.2, peak: 2.5, readKB: 200, writeKB: 2600, repl: 1.5, years: 5, hit: 0.95, hotFrac: 0.2, cacheDays: 7, boxQps: 1000, headroom: 0.5 }
  };

  function el(tag, attrs, text) {
    var e = document.createElement(tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    return e;
  }

  var head = el("div", { "class": "widget-head" });
  head.appendChild(el("span", { "class": "widget-tag" }, "Try it"));
  head.appendChild(el("h4", { "class": "widget-title" }, "Napkin calculator"));
  root.appendChild(head);
  root.appendChild(el("p", { "class": "widget-help" }, "Pick a preset or type your own assumptions. Everything below recalculates as you type. Replication 1.5 stands for erasure coding. Results are orders of magnitude, not forecasts."));

  var presetRow = el("div", { "class": "widget-row" });
  var inputs = {};
  Object.keys(PRESETS).forEach(function (k) {
    var b = el("button", { type: "button", "class": "btn small" }, PRESETS[k].name);
    b.addEventListener("click", function () { load(PRESETS[k]); });
    presetRow.appendChild(b);
  });
  root.appendChild(presetRow);

  var grid = el("div", { "class": "nc-grid" });
  FIELDS.forEach(function (f) {
    var w = el("div", { "class": "nc-field" });
    w.appendChild(el("label", { "for": "nc-" + f[0] }, f[1]));
    var inp = el("input", { type: "number", id: "nc-" + f[0], step: "any", min: String(f[3]) });
    if (f[4] !== null) inp.setAttribute("max", String(f[4]));
    inp.addEventListener("input", update);
    inputs[f[0]] = inp; w.appendChild(inp); grid.appendChild(w);
  });
  root.appendChild(grid);

  var tiles = el("div", { "class": "nc-tiles", "aria-live": "polite" });
  root.appendChild(tiles);
  var notes = el("div", { "class": "widget-out nc-notes" });
  root.appendChild(notes);

  function read() {
    var p = {};
    FIELDS.forEach(function (f) {
      var v = parseFloat(inputs[f[0]].value);
      if (!isFinite(v) || v < f[3]) v = f[3];
      if (f[4] !== null && v > f[4]) v = f[4];
      p[f[0]] = v;
    });
    return p;
  }
  function load(pr) {
    FIELDS.forEach(function (f) { inputs[f[0]].value = String(pr[f[0]]); });
    update();
  }
  function tile(k, v, cls) {
    var t = el("div", { "class": "nc-tile" + (cls ? " " + cls : "") });
    t.appendChild(el("div", { "class": "nc-k" }, k));
    t.appendChild(el("div", { "class": "nc-v" }, v));
    tiles.appendChild(t);
  }
  function update() {
    var p = read(), r = compute(p);
    tiles.textContent = "";
    tile("Read QPS avg / peak", human(r.readAvg, "/s") + " / " + human(r.readPeak, "/s"));
    tile("Write QPS avg / peak", human(r.writeAvg, "/s") + " / " + human(r.writePeak, "/s"));
    tile("Read : write ratio", isFinite(r.ratio) ? Math.round(r.ratio) + " : 1" : "no writes");
    tile("New data per day", human(r.newBytesDay, "B"));
    tile("Per year, replicated", human(r.replYear, "B"));
    tile("Retained total", human(r.retained, "B"));
    tile("Peak egress", human(r.egressBps, "bit/s"));
    tile("Origin egress after hits", human(r.originBps, "bit/s"));
    tile("Cache size (80/20)", human(r.cacheBytes, "B"));
    tile("Servers (incl. 1 spare)", String(r.servers), "accent");
    notes.textContent = "";
    notes.appendChild(el("strong", {}, "Sanity checks"));
    var ul = el("ul", {});
    remarks(p, r).forEach(function (t) { ul.appendChild(el("li", {}, t)); });
    notes.appendChild(ul);
  }
  load(PRESETS.paste);
})();
