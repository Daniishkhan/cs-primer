/* B+ tree visualiser (data chapter 6).

   A small in-memory B+ tree, drawn as SVG, so you can watch pages split.
   - Every node stands for one disk page. "Max keys" is how many keys fit in a page (2-4 here;
     real pages hold hundreds).
   - Leaves hold the keys (a real database would hold the rows or row pointers too) and are
     linked left to right. Internal nodes hold only separator keys and child pointers.
   - Insert: descend to the leaf. If it has more than max keys, split it in two and COPY the
     first key of the right half up into the parent. If the parent overflows, split it too and
     MOVE its middle key up. If the root splits, a new root is made and the tree grows taller.
   - Search / range scan: descend from the root; a range scan then follows the leaf links.
   - "Pages touched" counts the distinct nodes read or written by the last operation.
   Everything is deterministic: the "random" key button uses a fixed pseudo-random sequence.
   Not modelled: deletes and merges, page contents beyond keys, concurrency, the buffer pool. */
(function () {
  "use strict";
  var root = document.getElementById("btree-viz");
  if (!root) return;

  var SVGNS = "http://www.w3.org/2000/svg";
  var CW = 30, PAD = 6, NH = 30, GAP = 18, LVL = 62, MARGIN = 12, MARKER = "ahD06w";

  var maxKeys = 3, tree, nextId, history = [], seed = 7, ui = {};
  var hl = { path: {}, fresh: {}, scan: {}, found: null, range: {} };

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  function sv(tag, attrs, text) {
    var e = document.createElementNS(SVGNS, tag);
    for (var k in attrs) if (Object.prototype.hasOwnProperty.call(attrs, k)) e.setAttribute(k, attrs[k]);
    if (text != null) e.textContent = text;
    return e;
  }

  /* ---------- the tree ---------- */
  function newNode(leaf) { return { id: nextId++, leaf: leaf, keys: [], kids: [], next: null }; }
  function reset() { nextId = 1; tree = { root: newNode(true), height: 1 }; clearHl(); }
  function clearHl() { hl = { path: {}, fresh: {}, scan: {}, found: null, range: {} }; }
  function childIndex(n, key) { var i = 0; while (i < n.keys.length && n.keys[i] <= key) i++; return i; }

  function descend(key, path) {
    var n = tree.root;
    path.push(n);
    while (!n.leaf) { n = n.kids[childIndex(n, key)]; path.push(n); }
    return n;
  }

  /* returns null, "dup", or a split record {sep, right} to be placed in the parent */
  function insertInto(n, key, ctx) {
    var i, res;
    ctx.path.push(n);
    if (n.leaf) {
      for (i = 0; i < n.keys.length; i++) if (n.keys[i] === key) return "dup";
      i = 0; while (i < n.keys.length && n.keys[i] < key) i++;
      n.keys.splice(i, 0, key);
      if (n.keys.length <= maxKeys) return null;
      var mid = Math.ceil(n.keys.length / 2), r = newNode(true);
      r.keys = n.keys.splice(mid);
      r.next = n.next; n.next = r;
      ctx.fresh[r.id] = true; ctx.splits++;
      ctx.msgs.push("Leaf is over-full (" + (maxKeys + 1) + " keys): split into [" + n.keys.join(" ") + "] and [" + r.keys.join(" ") +
        "]. Key " + r.keys[0] + " is copied up to the parent.");
      return { sep: r.keys[0], right: r };
    }
    i = childIndex(n, key);
    res = insertInto(n.kids[i], key, ctx);
    if (res === "dup" || res === null) return res;
    n.keys.splice(i, 0, res.sep);
    n.kids.splice(i + 1, 0, res.right);
    if (n.keys.length <= maxKeys) {
      ctx.msgs.push("Parent has room: separator " + res.sep + " added there. The split stops here.");
      return null;
    }
    var m = Math.floor(n.keys.length / 2), up = n.keys[m], r2 = newNode(false);
    r2.keys = n.keys.slice(m + 1); r2.kids = n.kids.slice(m + 1);
    n.keys = n.keys.slice(0, m); n.kids = n.kids.slice(0, m + 1);
    ctx.fresh[r2.id] = true; ctx.splits++;
    ctx.msgs.push("Internal node is over-full: split into [" + n.keys.join(" ") + "] and [" + r2.keys.join(" ") +
      "]. Middle key " + up + " moves up (it is not kept in either half).");
    return { sep: up, right: r2 };
  }

  function insertKey(key) {
    var ctx = { path: [], fresh: {}, splits: 0, msgs: [] }, res = insertInto(tree.root, key, ctx);
    if (res === "dup") return { dup: true };
    if (res) {
      var nr = newNode(false);
      nr.keys = [res.sep]; nr.kids = [tree.root, res.right];
      tree.root = nr; tree.height++;
      ctx.fresh[nr.id] = true;
      ctx.msgs.push("The old root split, so a new root was created. The tree grows by one level, at the top: every leaf stays at the same depth.");
    }
    return ctx;
  }

  function count(n) { if (n.leaf) return { nodes: 1, keys: n.keys.length }; var t = { nodes: 1, keys: 0 }; n.kids.forEach(function (k) { var c = count(k); t.nodes += c.nodes; t.keys += c.keys; }); return t; }

  /* ---------- layout and drawing ---------- */
  function nodeW(n) { return Math.max(1, n.keys.length) * CW + 2 * PAD; }

  function layout() {
    var x = MARGIN, pos = {};
    (function place(n, depth) {
      var y = 14 + depth * LVL, w = nodeW(n);
      if (n.leaf) { pos[n.id] = { x: x, y: y, w: w, n: n }; x += w + GAP; return; }
      n.kids.forEach(function (k) { place(k, depth + 1); });
      var a = pos[n.kids[0].id], b = pos[n.kids[n.kids.length - 1].id];
      var c = (a.x + a.w / 2 + b.x + b.w / 2) / 2;
      pos[n.id] = { x: c - w / 2, y: y, w: w, n: n };
    })(tree.root, 0);
    return { pos: pos, width: x - GAP + MARGIN, height: 14 + (tree.height - 1) * LVL + NH + 14 };
  }

  function draw() {
    var L = layout(), svg = ui.svg;
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    svg.setAttribute("viewBox", "0 0 " + L.width + " " + L.height);
    svg.setAttribute("aria-label", "B+ tree with " + count(tree.root).keys + " keys, " + tree.height + " levels");
    var defs = sv("defs", {});
    var mk = sv("marker", { id: MARKER, viewBox: "0 0 10 10", refX: "9", refY: "5", markerWidth: "6", markerHeight: "6", orient: "auto" });
    mk.appendChild(sv("path", { d: "M0,0 L10,5 L0,10 z", "class": "arrowhead" }));
    defs.appendChild(mk); svg.appendChild(defs);

    var id, p, n, i, g;
    // edges first, so boxes sit on top
    for (id in L.pos) {
      p = L.pos[id]; n = p.n;
      if (n.leaf) {
        if (n.next) {
          var q = L.pos[n.next.id], cls = hl.scan[n.id] && hl.scan[n.next.id] ? "line s-yellow" : "line";
          svg.appendChild(sv("line", { x1: p.x + p.w + 1, y1: p.y + NH / 2, x2: q.x - 2, y2: q.y + NH / 2, "class": cls, "marker-end": "url(#" + MARKER + ")" }));
        }
      } else {
        for (i = 0; i < n.kids.length; i++) {
          var c = L.pos[n.kids[i].id], on = hl.path[n.id] && hl.path[n.kids[i].id];
          svg.appendChild(sv("line", { x1: p.x + PAD + i * CW, y1: p.y + NH, x2: c.x + c.w / 2, y2: c.y, "class": on ? "line s-yellow sw-3" : "line" }));
        }
      }
    }
    for (id in L.pos) {
      p = L.pos[id]; n = p.n;
      var cl = "box";
      if (hl.fresh[n.id]) cl = "fs-green s-green sw-2";
      if (hl.path[n.id] || hl.scan[n.id]) cl = "fs-yellow s-yellow sw-2";
      g = sv("g", {});
      g.appendChild(sv("rect", { x: p.x, y: p.y, width: p.w, height: NH, rx: 6, "class": cl }));
      for (i = 0; i < n.keys.length; i++) {
        var kx = p.x + PAD + i * CW;
        if (i > 0) g.appendChild(sv("line", { x1: kx, y1: p.y + 4, x2: kx, y2: p.y + NH - 4, "class": "line-thin" }));
        var hit = (hl.found === n.keys[i] && n.leaf) || (n.leaf && hl.range[n.keys[i]]);
        if (hit) g.appendChild(sv("rect", { x: kx + 2, y: p.y + 4, width: CW - 4, height: NH - 8, rx: 4, "class": "f-yellow" }));
        g.appendChild(sv("text", { x: kx + CW / 2, y: p.y + NH / 2 + 4.5, "text-anchor": "middle", "class": "mono t-sm" + (hit ? " t-dark t-bold" : n.leaf ? "" : " tc-purple t-bold") }, String(n.keys[i])));
      }
      if (!n.keys.length) g.appendChild(sv("text", { x: p.x + p.w / 2, y: p.y + NH / 2 + 4, "text-anchor": "middle", "class": "t-xs t-faint" }, "empty"));
      svg.appendChild(g);
    }
    fit(L.width, L.height);
  }

  var lastW = 0, lastH = 0;
  function fit(w, h) {
    lastW = w; lastH = h;
    var avail = ui.scroll.clientWidth || w;
    var s = Math.min(1, Math.max(avail / w, 0.8));
    ui.svg.style.width = Math.round(w * s) + "px";
    ui.svg.style.height = Math.round(h * s) + "px";
  }

  /* ---------- operations and reporting ---------- */
  function setStats(touched) {
    var c = count(tree.root);
    ui.height.textContent = String(tree.height);
    ui.nodes.textContent = String(c.nodes);
    ui.keys.textContent = String(c.keys);
    ui.touched.textContent = touched == null ? "-" : String(touched);
  }
  function report(lines, bad) {
    ui.log.textContent = "";
    lines.forEach(function (t, i) {
      var li = el("li", bad && i === 0 ? "bt-bad" : "", t);
      ui.log.appendChild(li);
    });
  }
  function keyList(n) { return n.length ? "[" + n.join(" ") + "]" : "[]"; }

  function doInsert(keys) {
    var lines = [], touched = null, added = 0, dups = [];
    clearHl();
    keys.forEach(function (k) {
      var r = insertKey(k);
      if (r.dup) { dups.push(k); return; }
      added++; history.push(k);
      if (keys.length <= 3) {
        lines.push("Insert " + k + ": descended " + r.path.length + " page" + (r.path.length > 1 ? "s" : "") + " (root to leaf)" + (r.splits ? ", then " + r.splits + " split" + (r.splits > 1 ? "s" : "") + "." : ", and the leaf had room: no split."));
        r.msgs.forEach(function (m) { lines.push(m); });
      }
      // highlight only the last insert
      hl.path = {}; hl.fresh = {};
      r.path.forEach(function (p) { hl.path[p.id] = true; });
      for (var f in r.fresh) hl.fresh[f] = true;
      touched = Object.keys(hl.path).length;
      for (var f2 in r.fresh) if (!hl.path[f2]) touched++;
    });
    if (keys.length > 3) lines.unshift("Inserted " + added + " key" + (added === 1 ? "" : "s") + " one at a time. The picture shows the effect of the last one: yellow pages were read on the way down, green pages are new.");
    if (dups.length) lines.push("Skipped " + dups.join(", ") + ": already in the tree (keys here are unique).");
    if (!lines.length) lines.push("Nothing to insert.");
    draw(); setStats(touched); report(lines, !added && dups.length > 0);
  }

  function parseKeys(text) {
    var parts = text.split(/[\s,]+/).filter(Boolean), out = [];
    for (var i = 0; i < parts.length; i++) {
      if (!/^\d{1,3}$/.test(parts[i])) return null;
      out.push(parseInt(parts[i], 10));
    }
    return out;
  }
  function readOne(input, what) {
    var t = input.value.trim();
    if (!/^\d{1,3}$/.test(t)) { report(["Type a whole number from 0 to 999 for " + what + "."], true); return null; }
    return parseInt(t, 10);
  }

  function onInsert(e) {
    e.preventDefault();
    var ks = parseKeys(ui.keyIn.value);
    if (!ks || !ks.length) { report(["Type one or more whole numbers from 0 to 999, separated by spaces or commas."], true); return; }
    doInsert(ks);
    ui.keyIn.value = ""; ui.keyIn.focus();
  }
  function onRandom() {
    var have = {}, k, tries = 0;
    history.forEach(function (h) { have[h] = true; });
    do { seed = (seed * 1103515245 + 12345) % 2147483648; k = 1 + (seed >> 8) % 99; tries++; } while (have[k] && tries < 500);
    if (have[k]) { report(["All keys 1 to 99 are already in the tree."], true); return; }
    doInsert([k]);
  }
  function onSeq() {
    var have = {}, ks = [], i;
    history.forEach(function (h) { have[h] = true; });
    for (i = 1; i <= 20; i++) if (!have[i]) ks.push(i);
    doInsert(ks);
  }
  function onSearch(e) {
    e.preventDefault();
    var k = readOne(ui.sIn, "the key to search for");
    if (k == null) return;
    var path = [], leaf = descend(k, path), found = leaf.keys.indexOf(k) >= 0;
    clearHl();
    path.forEach(function (p) { hl.path[p.id] = true; });
    if (found) hl.found = k;
    draw(); setStats(path.length);
    var lines = ["Search " + k + ": read " + path.length + " page" + (path.length > 1 ? "s" : "") + " (one per level)."];
    path.forEach(function (p, i) {
      if (p.leaf) lines.push("Page " + (i + 1) + " is a leaf " + keyList(p.keys) + ": " + (found ? "key " + k + " is here." : "key " + k + " is not here, so it is not in the tree."));
      else lines.push("Page " + (i + 1) + " " + keyList(p.keys) + ": " + k + " belongs under pointer " + (childIndex(p, k) + 1) + ".");
    });
    report(lines);
  }
  function onRange(e) {
    e.preventDefault();
    var a = readOne(ui.rFrom, "the start of the range"), b = readOne(ui.rTo, "the end of the range");
    if (a == null || b == null) return;
    if (a > b) { report(["The start of the range must not be larger than the end."], true); return; }
    var path = [], leaf = descend(a, path), n = leaf, got = [], leaves = 0;
    clearHl();
    path.forEach(function (p) { hl.path[p.id] = true; });
    while (n) {
      leaves++; hl.scan[n.id] = true;
      var stop = false;
      for (var i = 0; i < n.keys.length; i++) {
        if (n.keys[i] > b) { stop = true; break; }
        if (n.keys[i] >= a) { got.push(n.keys[i]); hl.range[n.keys[i]] = true; }
      }
      if (stop) break;
      n = n.next;
    }
    var extra = leaves - 1;
    draw(); setStats(path.length + extra);
    report(["Range " + a + " to " + b + ": walked down " + path.length + " page" + (path.length > 1 ? "s" : "") + " to find the first leaf, then followed the links across " + extra + " more " + (extra === 1 ? "leaf" : "leaves") + ". Total " + (path.length + extra) + " pages.",
      got.length ? "Found " + got.length + " key" + (got.length === 1 ? "" : "s") + ": " + got.join(", ") + "." : "No keys in that range.",
      "The scan never climbed back up to a parent: that is the point of linking the leaves."]);
  }
  function onReset() {
    history = []; seed = 7; reset(); draw(); setStats(null);
    report(["Empty tree. A new tree is a single leaf that is also the root. Insert some keys."]);
  }
  function onMax() {
    maxKeys = parseInt(ui.max.value, 10);
    var keys = history.slice();
    history = []; reset();
    keys.forEach(function (k) { insertKey(k); history.push(k); });
    draw(); setStats(null);
    report(["Pages now hold at most " + maxKeys + " keys. The tree was rebuilt by inserting the same keys in the same order, so you can compare the shapes."]);
  }

  /* ---------- UI ---------- */
  function build() {
    root.textContent = "";
    var head = el("div", "widget-head");
    head.appendChild(el("span", "widget-tag", "Interactive"));
    head.appendChild(el("p", "widget-title", "B+ tree playground"));
    root.appendChild(head);
    root.appendChild(el("p", "widget-help", "Each box is one page. Insert keys and watch full pages split (green = newly created page). Search shows the root-to-leaf path in yellow; a range scan follows the arrows between leaves."));

    var r1 = el("form", "widget-row");
    var lab = el("label", "bt-lab", "Max keys per page");
    ui.max = el("select", "mono");
    [2, 3, 4].forEach(function (m) { var o = el("option", "", String(m)); o.value = String(m); if (m === maxKeys) o.selected = true; ui.max.appendChild(o); });
    ui.max.id = "bt-max"; lab.setAttribute("for", "bt-max");
    ui.max.addEventListener("change", onMax);
    r1.addEventListener("submit", function (e) { e.preventDefault(); });
    r1.appendChild(lab); r1.appendChild(ui.max);
    ui.reset = el("button", "btn small", "Reset"); ui.reset.type = "button"; ui.reset.addEventListener("click", onReset);
    r1.appendChild(ui.reset);
    root.appendChild(r1);

    var r2 = el("form", "widget-row");
    ui.keyIn = el("input", "mono bt-in"); ui.keyIn.type = "text"; ui.keyIn.setAttribute("aria-label", "Keys to insert, separated by spaces"); ui.keyIn.placeholder = "e.g. 10 20 5"; ui.keyIn.autocomplete = "off"; ui.keyIn.setAttribute("inputmode", "numeric");
    var bi = el("button", "btn primary small", "Insert"); bi.type = "submit";
    var br = el("button", "btn small", "Random key"); br.type = "button"; br.addEventListener("click", onRandom);
    var bs = el("button", "btn small", "Insert 1..20 in order"); bs.type = "button"; bs.addEventListener("click", onSeq);
    r2.addEventListener("submit", onInsert);
    [ui.keyIn, bi, br, bs].forEach(function (x) { r2.appendChild(x); });
    root.appendChild(r2);

    var r3 = el("form", "widget-row");
    ui.sIn = el("input", "mono bt-in bt-sm"); ui.sIn.type = "text"; ui.sIn.setAttribute("aria-label", "Key to search for"); ui.sIn.placeholder = "key"; ui.sIn.autocomplete = "off"; ui.sIn.setAttribute("inputmode", "numeric");
    var bf = el("button", "btn small", "Search"); bf.type = "submit";
    r3.addEventListener("submit", onSearch);
    [ui.sIn, bf].forEach(function (x) { r3.appendChild(x); });
    root.appendChild(r3);

    var r4 = el("form", "widget-row");
    ui.rFrom = el("input", "mono bt-in bt-sm"); ui.rFrom.type = "text"; ui.rFrom.setAttribute("aria-label", "Range scan from"); ui.rFrom.placeholder = "from"; ui.rFrom.autocomplete = "off"; ui.rFrom.setAttribute("inputmode", "numeric");
    ui.rTo = el("input", "mono bt-in bt-sm"); ui.rTo.type = "text"; ui.rTo.setAttribute("aria-label", "Range scan to"); ui.rTo.placeholder = "to"; ui.rTo.autocomplete = "off"; ui.rTo.setAttribute("inputmode", "numeric");
    var bg = el("button", "btn small", "Range scan"); bg.type = "submit";
    r4.addEventListener("submit", onRange);
    [ui.rFrom, ui.rTo, bg].forEach(function (x) { r4.appendChild(x); });
    root.appendChild(r4);

    var stats = el("div", "widget-row bt-stats");
    [["height", "Height (levels)"], ["nodes", "Pages (nodes)"], ["keys", "Keys"], ["touched", "Pages touched by last op"]].forEach(function (s) {
      var box = el("span", "bt-stat"); box.appendChild(el("span", "bt-stat-l", s[1]));
      ui[s[0]] = el("span", "pill blue", "0"); box.appendChild(ui[s[0]]); stats.appendChild(box);
    });
    root.appendChild(stats);

    ui.scroll = el("div", "bt-scroll");
    ui.scroll.tabIndex = 0;
    ui.scroll.setAttribute("role", "group");
    ui.scroll.setAttribute("aria-label", "Tree drawing (scrolls sideways if wide)");
    ui.svg = sv("svg", { role: "img", viewBox: "0 0 100 60", "aria-label": "B+ tree" });
    ui.scroll.appendChild(ui.svg);
    root.appendChild(ui.scroll);

    var out = el("div", "widget-out");
    out.setAttribute("aria-live", "polite");
    ui.log = el("ul", "bt-log");
    out.appendChild(ui.log);
    root.appendChild(out);

    var resizeT;
    window.addEventListener("resize", function () { clearTimeout(resizeT); resizeT = setTimeout(function () { fit(lastW, lastH); }, 80); });
  }

  build();
  reset();
  draw();
  setStats(null);
  report(["Empty tree. A new tree is a single leaf that is also the root. Try “Insert 1..20 in order” with max keys 2, then 4."]);
})();
