/* Reading-order explorer (chapter 18).
   Three ways to order the text blocks of a page: the order the blocks are stored in the PDF content
   stream, a sort by top edge then left edge, and a recursive XY-cut that splits on the widest empty band.
   The three layouts are constructed examples. "Right place" counts blocks whose position in the output
   equals their position in the intended reading order. */
(function () {
  "use strict";
  var root = document.getElementById("ret18-order");
  if (!root) return;
  var NS = "http://www.w3.org/2000/svg";
  var LAYOUTS = {
    two: { name: "Two columns, title and page number", blocks: [
      { id: "T", n: "Title", x: 20, y: 10, w: 460, h: 30 }, { id: "L1", n: "Left 1", x: 20, y: 60, w: 215, h: 70 },
      { id: "L2", n: "Left 2", x: 20, y: 140, w: 215, h: 70 }, { id: "L3", n: "Left 3", x: 20, y: 220, w: 215, h: 60 },
      { id: "R1", n: "Right 1", x: 255, y: 60, w: 225, h: 70 }, { id: "R2", n: "Right 2", x: 255, y: 140, w: 225, h: 70 },
      { id: "R3", n: "Right 3", x: 255, y: 220, w: 225, h: 60 }, { id: "F", n: "Page no.", x: 200, y: 292, w: 100, h: 18 } ],
      truth: ["T", "L1", "L2", "L3", "R1", "R2", "R3", "F"], stream: ["R1", "R2", "R3", "L1", "L2", "L3", "T", "F"] },
    fig: { name: "Two columns with a full-width figure", blocks: [
      { id: "T", n: "Title", x: 20, y: 10, w: 460, h: 28 }, { id: "L1", n: "Left 1", x: 20, y: 52, w: 215, h: 60 },
      { id: "R1", n: "Right 1", x: 255, y: 52, w: 225, h: 60 }, { id: "G", n: "Figure", x: 20, y: 126, w: 460, h: 70 },
      { id: "L2", n: "Left 2", x: 20, y: 210, w: 215, h: 70 }, { id: "R2", n: "Right 2", x: 255, y: 210, w: 225, h: 70 },
      { id: "F", n: "Page no.", x: 200, y: 294, w: 100, h: 18 } ],
      truth: ["T", "L1", "R1", "G", "L2", "R2", "F"], stream: ["G", "R2", "L2", "R1", "L1", "T", "F"] },
    pin: { name: "Pinwheel: four blocks round a pull-quote", blocks: [
      { id: "A", n: "A", x: 20, y: 10, w: 300, h: 100 }, { id: "B", n: "B", x: 335, y: 10, w: 145, h: 170 },
      { id: "C", n: "C", x: 180, y: 195, w: 300, h: 100 }, { id: "D", n: "D", x: 20, y: 125, w: 145, h: 170 },
      { id: "E", n: "Pull-quote", x: 180, y: 125, w: 140, h: 55 } ],
      truth: ["A", "B", "C", "D", "E"], stream: ["C", "E", "A", "D", "B"] }
  };
  var METHODS = {
    stream: "Stored order (content stream)",
    sort: "Sort by top, then left",
    xy: "XY-cut (widest gap first)"
  };

  function q(n) { return root.querySelector("[data-act=" + n + "]"); }
  var layoutSel = q("layout"), methodSel = q("method"), svg = q("page"), score = q("score"), seq = q("seq"), note = q("note");
  Object.keys(LAYOUTS).forEach(function (k) { var o = document.createElement("option"); o.value = k; o.textContent = LAYOUTS[k].name; layoutSel.appendChild(o); });
  Object.keys(METHODS).forEach(function (k) { var o = document.createElement("option"); o.value = k; o.textContent = METHODS[k]; methodSel.appendChild(o); });

  function bySortKey(a, b) { return a.y - b.y || a.x - b.x; }
  function bestCut(items, axis) {
    var lo = axis === "y" ? "y" : "x", len = axis === "y" ? "h" : "w";
    var s = items.slice().sort(function (a, b) { return a[lo] - b[lo]; });
    var reach = s[0][lo] + s[0][len], best = 0, at = -1, i;
    for (i = 1; i < s.length; i++) {
      var gap = s[i][lo] - reach;
      if (gap > best) { best = gap; at = i; }
      reach = Math.max(reach, s[i][lo] + s[i][len]);
    }
    if (best <= 4) return { gap: 0, groups: null };
    return { gap: best, groups: [s.slice(0, at), s.slice(at)] };
  }
  function xyCut(items) {
    if (items.length <= 1) return items.slice();
    var cy = bestCut(items, "y"), cx = bestCut(items, "x");
    var c = cx.gap > cy.gap ? cx : cy;                 // ties go to the horizontal cut
    if (!c.groups) return items.slice().sort(bySortKey);
    return xyCut(c.groups[0]).concat(xyCut(c.groups[1]));
  }

  function el(tag, attrs, text) {
    var e = document.createElementNS(NS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    return e;
  }

  function run() {
    var L = LAYOUTS[layoutSel.value], m = methodSel.value, byId = {}, order;
    L.blocks.forEach(function (b) { byId[b.id] = b; });
    if (m === "stream") order = L.stream.map(function (id) { return byId[id]; });
    else if (m === "sort") order = L.blocks.slice().sort(bySortKey);
    else order = xyCut(L.blocks);
    var pos = {}, right = 0;
    order.forEach(function (b, i) { pos[b.id] = i; });
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    L.blocks.forEach(function (b) {
      var ok = L.truth[pos[b.id]] === b.id;
      if (ok) right++;
      svg.appendChild(el("rect", { x: b.x, y: b.y, width: b.w, height: b.h, rx: 6, "class": "r18-blk " + (ok ? "r18-ok" : "r18-bad") }));
      svg.appendChild(el("text", { x: b.x + 8, y: b.y + 22, "class": "r18-num" }, String(pos[b.id] + 1)));
      svg.appendChild(el("text", { x: b.x + b.w - 8, y: b.y + b.h - 8, "text-anchor": "end", "class": "r18-lbl" }, b.n));
    });
    score.textContent = "Blocks in the right place: " + right + " of " + L.blocks.length;
    seq.textContent = "Produced:  " + order.map(function (b) { return b.id; }).join(" > ") + "\nIntended:  " + L.truth.join(" > ");
    seq.style.whiteSpace = "pre-wrap";
    note.textContent = m === "stream"
      ? "The stored order is whatever the producing program wrote. Here it lists the right column first and the title late, as the chapter's two_column.pdf does."
      : m === "sort"
        ? "Sorting by top edge reads straight across the page, so blocks from the two columns alternate."
        : (layoutSel.value === "pin"
            ? "No straight cut separates the blocks of a pinwheel, so XY-cut falls back to a top-then-left sort. Learned reading-order models exist for layouts like this."
            : "XY-cut splits on the widest empty band, so full-width items split off first and columns stay together.");
  }
  layoutSel.addEventListener("change", run);
  methodSel.addEventListener("change", run);
  methodSel.value = "sort";
  run();
})();
