/* Consistent hashing explorer (chapter 19).
   Pure vanilla JS. Root element: #hash-ring (see chapters/19-partitioning.html).
   Deterministic: same clicks always give the same picture. */
(function () {
  "use strict";

  /* ---------- core (no DOM) ---------- */

  // 32-bit FNV-1a followed by a murmur-style mixing step, so that names that
  // differ in one character (key-01, key-02...) still land far apart.
  function hash32(str) {
    var h = 0x811c9dc5, i;
    for (i = 0; i < str.length; i++) {
      h ^= str.charCodeAt(i);
      h = Math.imul(h, 0x01000193) >>> 0;
    }
    h ^= h >>> 16; h = Math.imul(h, 0x85ebca6b) >>> 0;
    h ^= h >>> 13; h = Math.imul(h, 0xc2b2ae35) >>> 0;
    h ^= h >>> 16;
    return h >>> 0;
  }

  var NAMES = "ABCDEFGH";
  var COLORS = ["blue", "green", "orange", "purple", "pink", "cyan", "teal", "red"];
  var KEY_COUNT = 48;
  var SPACE = 4294967296;

  function makeKeys() {
    var keys = [], i;
    for (i = 1; i <= KEY_COUNT; i++) {
      var name = "key-" + (i < 10 ? "0" + i : i);
      keys.push({ name: name, pos: hash32(name) });
    }
    return keys;
  }

  function buildRing(nodes, vn) {
    var pts = [];
    nodes.forEach(function (n) {
      for (var v = 0; v < vn; v++) pts.push({ node: n, label: n + "#" + v, pos: hash32(n + "#" + v) });
    });
    pts.sort(function (a, b) { return a.pos - b.pos; });
    return pts;
  }

  // The owner is the first ring point at or after the key, going clockwise.
  function ownerOf(pos, ring) {
    for (var i = 0; i < ring.length; i++) if (ring[i].pos >= pos) return ring[i].node;
    return ring[0].node;
  }

  function assign(keys, nodes, vn) {
    var ring = buildRing(nodes, vn), out = {};
    keys.forEach(function (k) { out[k.name] = ownerOf(k.pos, ring); });
    return out;
  }

  function modAssign(keys, nodes) {
    var out = {};
    keys.forEach(function (k) { out[k.name] = nodes[k.pos % nodes.length]; });
    return out;
  }

  function diff(keys, a, b) {
    return keys.filter(function (k) { return a[k.name] !== b[k.name]; }).map(function (k) { return k.name; });
  }

  var core = { hash32: hash32, buildRing: buildRing, ownerOf: ownerOf, assign: assign, modAssign: modAssign, diff: diff, makeKeys: makeKeys };
  if (typeof module !== "undefined" && module.exports) module.exports = core;
  if (typeof document === "undefined") return;

  /* ---------- widget ---------- */

  var root = document.getElementById("hash-ring");
  if (!root) return;

  var NS = "http://www.w3.org/2000/svg";
  var CX = 180, CY = 180, R_RING = 142, R_KEY = 112;

  var svgBox = root.querySelector(".hr-svg");
  var barsBox = root.querySelector(".hr-bars");
  var statsBox = root.querySelector(".hr-stats");
  var removeSel = root.querySelector(".hr-remove");
  var lookupIn = root.querySelector(".hr-lookup");
  var lookupOut = root.querySelector(".hr-lookup-out");
  var btnAdd = root.querySelector('[data-act="add"]');
  var btnRemove = root.querySelector('[data-act="remove"]');
  var btnReset = root.querySelector('[data-act="reset"]');
  var btnV1 = root.querySelector('[data-vn="1"]');
  var btnV8 = root.querySelector('[data-vn="8"]');

  var keys = makeKeys();
  var nodes, vn, owners, moved, lookupPos;

  function el(name, attrs, parent) {
    var e = document.createElementNS(NS, name);
    for (var k in attrs) if (Object.prototype.hasOwnProperty.call(attrs, k)) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
  }
  function colorOf(n) { return COLORS[NAMES.indexOf(n)]; }
  function xy(pos, r) {
    var a = (pos / SPACE) * 2 * Math.PI - Math.PI / 2;
    return { x: CX + r * Math.cos(a), y: CY + r * Math.sin(a) };
  }
  function pct(pos) { return Math.round((pos / SPACE) * 100); }

  function draw() {
    svgBox.textContent = "";
    var svg = el("svg", { viewBox: "0 0 360 360", role: "img", "aria-label": "A hash ring with " + nodes.length + " nodes and " + KEY_COUNT + " keys, each key coloured by the node that owns it" }, svgBox);
    el("circle", { cx: CX, cy: CY, r: R_RING, "class": "line", fill: "none" }, svg);
    el("text", { x: CX, y: CY - 8, "text-anchor": "middle", "class": "t-sm t-faint" }, svg).textContent = "the ring";
    el("text", { x: CX, y: CY + 10, "text-anchor": "middle", "class": "t-xs t-faint" }, svg).textContent = "clockwise ↻";
    // 0 marker
    var z = xy(0, R_RING + 12);
    el("text", { x: z.x, y: z.y + 4, "text-anchor": "middle", "class": "t-xs t-faint" }, svg).textContent = "0";

    var ring = buildRing(nodes, vn);
    // keys
    keys.forEach(function (k) {
      var o = owners[k.name], p = xy(k.pos, R_KEY), c = colorOf(o);
      var q = xy(k.pos, R_RING - 2);
      el("line", { x1: p.x, y1: p.y, x2: q.x, y2: q.y, "class": "s-" + c + " sw-1", opacity: "0.35" }, svg);
    });
    keys.forEach(function (k) {
      var o = owners[k.name], p = xy(k.pos, R_KEY), c = colorOf(o);
      var isMoved = moved.indexOf(k.name) !== -1;
      if (isMoved) el("circle", { cx: p.x, cy: p.y, r: 9, "class": "hr-moved", fill: "none" }, svg);
      var d = el("circle", { cx: p.x, cy: p.y, r: 4.5, "class": "f-" + c }, svg);
      el("title", {}, d).textContent = k.name + " → node " + o + (isMoved ? " (moved)" : "");
    });
    // ring points (nodes / virtual nodes)
    ring.forEach(function (pt) {
      var p = xy(pt.pos, R_RING), c = colorOf(pt.node);
      if (vn === 1) {
        var g = el("circle", { cx: p.x, cy: p.y, r: 14, "class": "f-" + c }, svg);
        el("title", {}, g).textContent = "node " + pt.node + " at " + pct(pt.pos) + "% round the ring";
        el("text", { x: p.x, y: p.y + 5, "text-anchor": "middle", "class": "t-bold t-dark" }, svg).textContent = pt.node;
      } else {
        var s = el("circle", { cx: p.x, cy: p.y, r: 6, "class": "f-" + c + " hr-vpt" }, svg);
        el("title", {}, s).textContent = "virtual node " + pt.label + " (belongs to " + pt.node + ")";
      }
    });
    // lookup marker
    if (lookupPos !== null) {
      var m = xy(lookupPos, R_KEY), t = xy(lookupPos, R_RING - 2);
      el("line", { x1: m.x, y1: m.y, x2: t.x, y2: t.y, "class": "hr-look-line" }, svg);
      el("rect", { x: m.x - 5, y: m.y - 5, width: 10, height: 10, transform: "rotate(45 " + m.x + " " + m.y + ")", "class": "hr-look" }, svg);
    }
  }

  function counts() {
    var c = {};
    nodes.forEach(function (n) { c[n] = 0; });
    keys.forEach(function (k) { c[owners[k.name]]++; });
    return c;
  }

  function drawBars() {
    var c = counts(), ideal = KEY_COUNT / nodes.length, max = ideal, n;
    nodes.forEach(function (x) { if (c[x] > max) max = c[x]; });
    barsBox.textContent = "";
    nodes.forEach(function (x) {
      var row = document.createElement("div"); row.className = "hr-bar-row";
      var lab = document.createElement("span"); lab.className = "hr-bar-label"; lab.textContent = "Node " + x;
      var sw = document.createElement("span"); sw.className = "hr-swatch"; sw.style.background = "var(--" + colorOf(x) + ")";
      lab.insertBefore(sw, lab.firstChild);
      var track = document.createElement("span"); track.className = "hr-track";
      var fill = document.createElement("span"); fill.className = "hr-fill";
      fill.style.width = (c[x] / max * 100) + "%"; fill.style.background = "var(--" + colorOf(x) + ")";
      var tick = document.createElement("span"); tick.className = "hr-tick"; tick.style.left = (ideal / max * 100) + "%";
      track.appendChild(fill); track.appendChild(tick);
      var num = document.createElement("span"); num.className = "hr-num"; num.textContent = c[x];
      row.appendChild(lab); row.appendChild(track); row.appendChild(num);
      barsBox.appendChild(row);
    });
    var note = document.createElement("p"); note.className = "widget-help";
    note.textContent = "The thin vertical line marks a perfectly even share (" + (Math.round(ideal * 10) / 10) + " keys each).";
    barsBox.appendChild(note);
  }

  function say(html) { statsBox.textContent = ""; html.forEach(function (part) {
    var p = document.createElement("p"); p.style.margin = "0";
    part.forEach(function (seg) {
      if (typeof seg === "string") p.appendChild(document.createTextNode(seg));
      else { var s = document.createElement("strong"); s.textContent = seg.b; p.appendChild(s); }
    });
    statsBox.appendChild(p);
  }); }

  function syncControls() {
    removeSel.textContent = "";
    nodes.forEach(function (n) {
      var o = document.createElement("option"); o.value = n; o.textContent = "Node " + n; removeSel.appendChild(o);
    });
    btnAdd.disabled = nodes.length >= NAMES.length;
    btnRemove.disabled = nodes.length <= 1;
    removeSel.disabled = nodes.length <= 1;
    btnV1.setAttribute("aria-pressed", vn === 1 ? "true" : "false");
    btnV8.setAttribute("aria-pressed", vn === 8 ? "true" : "false");
    btnV1.classList.toggle("primary", vn === 1);
    btnV8.classList.toggle("primary", vn === 8);
  }

  function refresh() {
    owners = assign(keys, nodes, vn);
    draw(); drawBars(); syncControls();
    if (lookupPos !== null) showLookup();
  }

  // Apply a change: compute both strategies' movement, then report.
  function change(newNodes, newVn, describe) {
    var oldOwners = owners, oldNodes = nodes;
    var oldMod = modAssign(keys, oldNodes);
    nodes = newNodes; vn = newVn;
    owners = assign(keys, nodes, vn);
    moved = diff(keys, oldOwners, owners);
    var modMoved = diff(keys, oldMod, modAssign(keys, nodes)).length;
    draw(); drawBars(); syncControls();
    if (lookupPos !== null) showLookup();
    describe(moved.length, modMoved, oldOwners);
  }

  function onAdd() {
    var free = NAMES.split("").filter(function (n) { return nodes.indexOf(n) === -1; });
    if (!free.length) return;
    var nn = free[0];
    change(nodes.concat([nn]), vn, function (m, mod) {
      var toNew = 0; keys.forEach(function (k) { if (moved.indexOf(k.name) !== -1 && owners[k.name] === nn) toNew++; });
      say([
        ["Added node ", { b: nn }, ". Consistent hashing moved ", { b: m + " of " + KEY_COUNT }, " keys, and " + toNew + " of those moves went to the new node (nothing was shuffled between the old nodes)."],
        ["Plain ", { b: "hash mod N" }, " would have moved ", { b: mod + " of " + KEY_COUNT }, " (about " + Math.round(mod / KEY_COUNT * 100) + "%)."]
      ]);
    });
  }

  function onRemove() {
    var gone = removeSel.value;
    if (nodes.indexOf(gone) === -1 || nodes.length <= 1) return;
    var rest = nodes.filter(function (n) { return n !== gone; });
    change(rest, vn, function (m, mod, old) {
      var had = 0; keys.forEach(function (k) { if (old[k.name] === gone) had++; });
      say([
        ["Removed node ", { b: gone }, ". It held " + had + " keys, and consistent hashing moved exactly ", { b: m + " of " + KEY_COUNT }, ": only the keys that node owned, each passing to the next node clockwise."],
        ["Plain ", { b: "hash mod N" }, " would have moved ", { b: mod + " of " + KEY_COUNT }, " (about " + Math.round(mod / KEY_COUNT * 100) + "%)."]
      ]);
    });
  }

  function setVn(v) {
    if (v === vn) return;
    change(nodes.slice(), v, function (m) {
      say([
        ["Now ", { b: v + " point" + (v === 1 ? "" : "s") }, " per node on the ring. Each node keeps its old spot" + (v > 1 ? " and gains " + (v - 1) + " more" : " and drops the extras") + ", so the ring is redrawn and " + m + " keys changed owner."],
        ["Look at the bars: with more points per node, each node owns many small slices and the shares tend to even out. (Real systems choose this once, up front.)"]
      ]);
    });
  }

  function reset() {
    nodes = ["A", "B", "C", "D"]; vn = 1; moved = []; lookupPos = null;
    lookupIn.value = "user:42";
    lookupOut.textContent = "";
    refresh();
    say([["Four nodes, " + KEY_COUNT + " keys, one point per node. Add or remove a node and watch which keys (ringed in white) change owner."]]);
  }

  function showLookup() {
    var ring = buildRing(nodes, vn), o = ownerOf(lookupPos, ring);
    lookupOut.textContent = "hash(\"" + lookupIn.value + "\") = " + lookupPos + " → " + pct(lookupPos) + "% of the way round the ring → owned by node " + o + ".";
  }
  function onLookup() {
    var v = lookupIn.value;
    if (!v) { lookupPos = null; lookupOut.textContent = ""; draw(); return; }
    lookupPos = hash32(v);
    draw(); showLookup();
  }

  btnAdd.addEventListener("click", onAdd);
  btnRemove.addEventListener("click", onRemove);
  btnReset.addEventListener("click", reset);
  btnV1.addEventListener("click", function () { setVn(1); });
  btnV8.addEventListener("click", function () { setVn(8); });
  root.querySelector('[data-act="lookup"]').addEventListener("click", onLookup);
  lookupIn.addEventListener("keydown", function (e) { if (e.key === "Enter") { e.preventDefault(); onLookup(); } });

  reset();
})();
