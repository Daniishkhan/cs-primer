/* Geo cells (design chapter 14).

   A map window made of real geohash cells. Two modes:
   - "Cell and neighbours": click a cell to see its geohash, its 8 neighbours' geohashes and how many drivers each holds.
   - "Nearest k": click anywhere to place a rider. The query searches ring 0 (the rider's cell), then ring 1, ring 2 ...,
     and stops when it holds k candidates AND the k-th nearest is closer than (rings searched x the smallest cell side),
     the distance below which nothing outside the searched square can be. Rings are drawn as they are expanded.

   Model (simplified): geohash encoding is the real algorithm (base32, interleaved lng/lat bits); distances use an
   equirectangular approximation, fine at city scale; drivers are pseudo-random (seeded) with a downtown cluster.
   The Python in the chapter implements the same stopping rule.
   encode() is exported for testing under Node. */
(function () {
  "use strict";

  var B32 = "0123456789bcdefghjkmnpqrstuvwxyz";

  function encode(lat, lng, prec) {
    var latR = [-90, 90], lngR = [-180, 180], bits = 0, ch = 0, even = true, h = "", rng, v, mid;
    while (h.length < prec) {
      rng = even ? lngR : latR; v = even ? lng : lat; mid = (rng[0] + rng[1]) / 2;
      ch = ch << 1;
      if (v >= mid) { ch |= 1; rng[0] = mid; } else { rng[1] = mid; }
      even = !even; bits++;
      if (bits === 5) { h += B32.charAt(ch); bits = 0; ch = 0; }
    }
    return h;
  }

  function cellDeg(prec) {
    var lngBits = Math.floor((5 * prec + 1) / 2), latBits = Math.floor(5 * prec / 2);
    return { dlat: 180 / Math.pow(2, latBits), dlng: 360 / Math.pow(2, lngBits) };
  }

  function km(a, b) {
    var dlat = (b[0] - a[0]) * Math.PI / 180;
    var dlng = (b[1] - a[1]) * Math.PI / 180 * Math.cos(((a[0] + b[0]) / 2) * Math.PI / 180);
    return 6371 * Math.sqrt(dlat * dlat + dlng * dlng);
  }

  if (typeof module !== "undefined" && module.exports) { module.exports = { encode: encode, cellDeg: cellDeg }; }

  var root = typeof document !== "undefined" ? document.getElementById("geo-cells") : null;
  if (!root) return;

  var NS = "http://www.w3.org/2000/svg";
  var CENTER = [37.77, -122.42];
  var COLS = 9, ROWS = 7, VB_W = 760, CELL_PX = 76;       // 9 x 76 = 684; grid is centred in the 760 viewBox
  var VB_H = ROWS * CELL_PX + 20, X0 = (VB_W - COLS * CELL_PX) / 2, Y0 = 10;
  var prec = 5, mode = "cell", k = 5, sel = null, rider = null, drivers = [];

  function el(tag, attrs, text) {
    var e = document.createElement(tag), a;
    if (attrs) for (a in attrs) e.setAttribute(a, attrs[a]);
    if (text != null) e.textContent = text;
    return e;
  }
  function sv(tag, attrs, text) {
    var e = document.createElementNS(NS, tag), a;
    for (a in attrs) e.setAttribute(a, attrs[a]);
    if (text != null) e.textContent = text;
    return e;
  }

  var view = null;      // {lat0, lng0, dlat, dlng, origin cell indices}
  function setupView() {
    var d = cellDeg(prec);
    var ci = Math.floor(CENTER[0] / d.dlat), cj = Math.floor(CENTER[1] / d.dlng);
    view = { dlat: d.dlat, dlng: d.dlng, i0: ci - Math.floor(ROWS / 2), j0: cj - Math.floor(COLS / 2) };
    drivers = makeDrivers();
  }
  // cell (row r from top, col c from left) -> south-west corner
  function cellSW(r, c) { return [(view.i0 + (ROWS - 1 - r)) * view.dlat, (view.j0 + c) * view.dlng]; }
  function cellCentre(r, c) { var s = cellSW(r, c); return [s[0] + view.dlat / 2, s[1] + view.dlng / 2]; }
  function hashOf(r, c) { var p = cellCentre(r, c); return encode(p[0], p[1], prec); }
  function toXY(lat, lng) {
    return [X0 + (lng - view.j0 * view.dlng) / (COLS * view.dlng) * COLS * CELL_PX,
            Y0 + (ROWS - (lat - view.i0 * view.dlat) / view.dlat) * CELL_PX];
  }
  function cellOf(lat, lng) {
    var c = Math.floor(lng / view.dlng) - view.j0, rr = Math.floor(lat / view.dlat) - view.i0;
    return { r: ROWS - 1 - rr, c: c };
  }

  // seeded drivers: fixed lat/lng window independent of precision so changing precision keeps the same people
  function makeDrivers() {
    var seed = 12345, out = [], i, lat, lng;
    function rnd() { seed = (seed * 1664525 + 1013904223) % 4294967296; return seed / 4294967296; }
    function gauss() { return (rnd() + rnd() + rnd() + rnd() - 2) * 1.2; }
    var latSpan = view.dlat * ROWS / 2 * 0.98, lngSpan = view.dlng * COLS / 2 * 0.98;
    for (i = 0; i < 70; i++) {
      if (rnd() < 0.45) { lat = CENTER[0] + gauss() * latSpan * 0.25; lng = CENTER[1] + gauss() * lngSpan * 0.25; }
      else { lat = CENTER[0] + (rnd() * 2 - 1) * latSpan; lng = CENTER[1] + (rnd() * 2 - 1) * lngSpan; }
      out.push([lat, lng]);
    }
    return out.filter(function (d) { var c = cellOf(d[0], d[1]); return inGrid(c.r, c.c); });
  }

  function inGrid(r, c) { return r >= 0 && r < ROWS && c >= 0 && c < COLS; }
  function countIn(r, c) {
    var n = 0, i, cc;
    for (i = 0; i < drivers.length; i++) { cc = cellOf(drivers[i][0], drivers[i][1]); if (cc.r === r && cc.c === c) n++; }
    return n;
  }

  // ---- UI scaffold
  var head = el("div", { "class": "widget-head" });
  head.appendChild(el("span", { "class": "widget-tag" }, "Explore"));
  head.appendChild(el("h4", { "class": "widget-title" }, "Geohash cells, neighbours and ring expansion"));
  root.appendChild(head);
  root.appendChild(el("p", { "class": "widget-help" }, "Grey dots are drivers. In cell mode click a cell to see it and its eight neighbours. In nearest-k mode click to place a rider and watch the search widen ring by ring until the answer is provably right."));

  var row1 = el("div", { "class": "widget-row" });
  var bCell = el("button", { type: "button", "class": "btn small primary", "aria-pressed": "true" }, "Cell and neighbours");
  var bKnn = el("button", { type: "button", "class": "btn small", "aria-pressed": "false" }, "Nearest k");
  var precLabel = el("label", null, "Precision ");
  var precSel = el("select", { "aria-label": "Geohash precision" });
  [4, 5, 6].forEach(function (p) { precSel.appendChild(el("option", { value: String(p) }, p + " chars")); });
  precSel.value = String(prec); precLabel.appendChild(precSel);
  var kLabel = el("label", null, "k ");
  var kIn = el("input", { type: "number", min: "1", max: "20", value: String(k), "aria-label": "k, number of drivers wanted", "class": "mono", style: "width:4.5em" });
  kLabel.appendChild(kIn);
  row1.appendChild(bCell); row1.appendChild(bKnn); row1.appendChild(precLabel); row1.appendChild(kLabel);
  root.appendChild(row1);

  var wrap = el("div", { "class": "gc-wrap" });
  root.appendChild(wrap);
  var out = el("div", { "class": "widget-out", "aria-live": "polite" });
  root.appendChild(out);

  function render() {
    wrap.textContent = "";
    var s = sv("svg", { viewBox: "0 0 " + VB_W + " " + VB_H, role: "img", "aria-label": "A grid of geohash cells with drivers as dots; the selected cell, its neighbours or the search rings are highlighted." });
    var r, c, i;
    var neighbours = {}, ringOf = null, result = null;
    if (mode === "cell" && sel) { for (var dr = -1; dr <= 1; dr++) for (var dc = -1; dc <= 1; dc++) neighbours[(sel.r + dr) + "," + (sel.c + dc)] = (dr === 0 && dc === 0) ? "self" : "nb"; }
    if (mode === "knn" && rider) { result = search(); }
    for (r = 0; r < ROWS; r++) for (c = 0; c < COLS; c++) {
      var key = r + "," + c, cls = "gc-cell";
      if (mode === "cell" && neighbours[key]) cls += neighbours[key] === "self" ? " gc-self" : " gc-nb";
      if (mode === "knn" && result) {
        var rc = cellOf(rider[0], rider[1]), ring = Math.max(Math.abs(r - rc.r), Math.abs(c - rc.c));
        if (ring <= result.rings) cls += ring === 0 ? " gc-self" : (ring % 2 ? " gc-r1" : " gc-r2");
      }
      var g = sv("g", { "class": cls, tabindex: "0", role: "button", "aria-label": "Cell " + hashOf(r, c) + ", " + countIn(r, c) + " drivers", "data-r": r, "data-c": c });
      g.appendChild(sv("rect", { x: X0 + c * CELL_PX, y: Y0 + r * CELL_PX, width: CELL_PX, height: CELL_PX, "class": "gc-rect" }));
      g.appendChild(sv("text", { x: X0 + c * CELL_PX + CELL_PX / 2, y: Y0 + r * CELL_PX + 14, "text-anchor": "middle", "class": "gc-label" }, hashOf(r, c)));
      s.appendChild(g);
    }
    var hi = {};
    if (result) result.best.forEach(function (b) { hi[b.i] = true; });
    for (i = 0; i < drivers.length; i++) {
      var p = toXY(drivers[i][0], drivers[i][1]);
      s.appendChild(sv("circle", { cx: p[0], cy: p[1], r: hi[i] ? 5.5 : 3, "class": hi[i] ? "gc-hit" : "gc-dot", "pointer-events": "none" }));
    }
    if (mode === "knn" && rider) {
      var q = toXY(rider[0], rider[1]);
      s.appendChild(sv("circle", { cx: q[0], cy: q[1], r: 7, "class": "gc-rider", "pointer-events": "none" }));
      if (result.best.length) {
        var far = result.best[result.best.length - 1];
        var fp = toXY(drivers[far.i][0], drivers[far.i][1]);
        var rad = Math.sqrt(Math.pow(fp[0] - q[0], 2) + Math.pow(fp[1] - q[1], 2));
        s.appendChild(sv("circle", { cx: q[0], cy: q[1], r: rad, "class": "gc-radius", "pointer-events": "none" }));
      }
    }
    wrap.appendChild(s);
    describe(result);
    s.addEventListener("click", onClick);
    s.addEventListener("keydown", function (e) {
      if ((e.key === "Enter" || e.key === " ") && e.target.getAttribute && e.target.getAttribute("data-r") != null) {
        e.preventDefault();
        var rr = +e.target.getAttribute("data-r"), cc = +e.target.getAttribute("data-c");
        if (mode === "cell") { sel = { r: rr, c: cc }; } else { rider = cellCentre(rr, cc); }
        render();
      }
    });
  }

  function search() {
    var rc = cellOf(rider[0], rider[1]);
    var side = Math.min(view.dlat * 111.2, view.dlng * 111.2 * Math.cos(CENTER[0] * Math.PI / 180));
    var cand = [], r = 0, scanned = 0, ring, i, cc, best = [];
    while (r < 12) {
      for (i = 0; i < drivers.length; i++) {
        cc = cellOf(drivers[i][0], drivers[i][1]);
        if (Math.max(Math.abs(cc.r - rc.r), Math.abs(cc.c - rc.c)) === r) { cand.push({ i: i, d: km(rider, drivers[i]) }); scanned++; }
      }
      cand.sort(function (a, b) { return a.d - b.d; });
      best = cand.slice(0, k);
      if (best.length === k && best[k - 1].d <= r * side) break;
      r++;
    }
    if (r >= 12) r = 11;            // gave up: rings 0..11 were searched
    return { rings: r, best: best, scanned: scanned, side: side };
  }

  function describe(result) {
    var html = "", i, r, c, nbHashes = [];
    var cellKm = (view.dlat * 111.2).toFixed(2) + " km tall x " + (view.dlng * 111.2 * Math.cos(CENTER[0] * Math.PI / 180)).toFixed(2) + " km wide";
    if (mode === "cell") {
      if (!sel) { out.textContent = "Cells at this precision are about " + cellKm + ". Click a cell."; return; }
      var names = ["NW", "N", "NE", "W", "centre", "E", "SW", "S", "SE"], n = 0;
      html = "<strong>" + hashOf(sel.r, sel.c) + "</strong> holds " + countIn(sel.r, sel.c) + " drivers. Neighbours (a query must read these too): ";
      for (var dr = -1; dr <= 1; dr++) for (var dc = -1; dc <= 1; dc++, n++) {
        if (dr === 0 && dc === 0) continue;
        r = sel.r + dr; c = sel.c + dc;
        if (inGrid(r, c)) nbHashes.push(names[n] + " <code>" + hashOf(r, c) + "</code> (" + countIn(r, c) + ")");
        else { var p = cellCentre(sel.r, sel.c); var h = encode(p[0] + dr * -1 * view.dlat, p[1] + dc * view.dlng, prec); nbHashes.push(names[n] + " <code>" + h + "</code> (off-screen)"); }
      }
      html += nbHashes.join(", ") + ". Cells are " + cellKm + ". Look at the hashes: neighbours often share a prefix but not always, so you compute them geometrically (step one cell size and re-encode), you do not edit the string.";
      out.innerHTML = html;
    } else {
      if (!rider) { out.textContent = "Click the map to place a rider. Looking for k = " + k + " drivers. Cells are " + cellKm + "."; return; }
      var last = result.best[result.best.length - 1];
      out.innerHTML = "Searched <strong>" + (result.rings + 1) + "</strong> ring" + (result.rings ? "s" : "") + " (rings 0 to " + result.rings + ", a " + (2 * result.rings + 1) + " x " + (2 * result.rings + 1) + " block of cells), examined <strong>" + result.scanned + "</strong> of " + drivers.length + " drivers. " +
        (result.best.length === k && last ? "The " + k + "th nearest is " + last.d.toFixed(2) + " km away; the smallest cell side is " + result.side.toFixed(2) + " km, so after " + result.rings + " full ring" + (result.rings === 1 ? "" : "s") + " nothing outside the searched block can be closer than " + (result.rings * result.side).toFixed(2) + " km. Stopping is safe."
          : "Fewer than k drivers exist in the searched area: the search gave up at the ring limit.") +
        " Yellow ring: the distance to the k-th driver.";
    }
  }

  function onClick(e) {
    var t = e.target, g = t.closest ? t.closest("g[data-r]") : null, svg = wrap.firstChild;
    if (mode === "cell") {
      if (g) { sel = { r: +g.getAttribute("data-r"), c: +g.getAttribute("data-c") }; render(); }
    } else {
      var pt = svg.createSVGPoint(); pt.x = e.clientX; pt.y = e.clientY;
      var m = svg.getScreenCTM(); if (!m) return;
      var l = pt.matrixTransform(m.inverse());
      var cx = (l.x - X0) / CELL_PX, cy = (l.y - Y0) / CELL_PX;
      if (cx < 0 || cy < 0 || cx >= COLS || cy >= ROWS) return;
      var lat = (view.i0 + ROWS - cy) * view.dlat, lng = (view.j0 + cx) * view.dlng;
      rider = [lat, lng]; render();
    }
  }

  function setMode(m) {
    mode = m;
    bCell.className = "btn small" + (m === "cell" ? " primary" : ""); bCell.setAttribute("aria-pressed", String(m === "cell"));
    bKnn.className = "btn small" + (m === "knn" ? " primary" : ""); bKnn.setAttribute("aria-pressed", String(m === "knn"));
    render();
  }
  bCell.addEventListener("click", function () { setMode("cell"); });
  bKnn.addEventListener("click", function () { setMode("knn"); });
  precSel.addEventListener("change", function () { prec = parseInt(precSel.value, 10); sel = null; rider = null; setupView(); render(); });
  kIn.addEventListener("change", function () { var v = parseInt(kIn.value, 10); if (!(v >= 1)) v = 1; if (v > 20) v = 20; k = v; kIn.value = String(v); render(); });

  setupView();
  render();
})();
