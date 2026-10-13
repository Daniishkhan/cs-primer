/* Flame graph reader (systems chapter 22).
   Parses a small embedded set of "folded stacks" (the text format that flame
   graph tools consume: "root;caller;callee count") into a tree and draws it
   with one <button> per frame. Width = share of samples. Click a frame to
   zoom into it; the stats show its total and self share. "Shuffle order"
   reorders siblings at random to show that left-to-right position means
   nothing. All DOM text is set with textContent. No libraries, no storage. */
(function () {
  "use strict";
  var root = document.getElementById("flame-read");
  if (!root) return;

  /* Made-up samples for an imaginary web handler (5 ms apart). */
  var FOLDED = [
    "main;handle_request;parse_json;decode_str 120",
    "main;handle_request;parse_json;scan 80",
    "main;handle_request;auth;check_token;hmac_sha256 60",
    "main;handle_request;auth;check_token;load_keys 15",
    "main;handle_request;query_db;build_sql 25",
    "main;handle_request;query_db;parse_rows 60",
    "main;handle_request;render;template;escape 170",
    "main;handle_request;render;template;format_row 90",
    "main;handle_request;render;compress 110",
    "main;handle_request;log 30",
    "main;gc 20"
  ];

  function q(act) { return root.querySelector('[data-act="' + act + '"]'); }
  var graphEl = q("graph"), crumbEl = q("crumbs"), statsEl = q("stats");
  var resetBtn = q("reset"), upBtn = q("up"), shuffleBtn = q("shuffle"), sortBtn = q("sort");

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }

  /* ---- parse folded stacks into a tree ---- */
  function newNode(name, parent) {
    return { name: name, parent: parent, kids: [], map: {}, total: 0, self: 0, id: 0 };
  }
  function build() {
    var tree = newNode("all", null), nextId = 1;
    tree.id = 0;
    FOLDED.forEach(function (line) {
      var sp = line.lastIndexOf(" ");
      var n = parseInt(line.slice(sp + 1), 10);
      var frames = line.slice(0, sp).split(";");
      var node = tree;
      node.total += n;
      frames.forEach(function (f) {
        var k = node.map[f];
        if (!k) { k = newNode(f, node); k.id = nextId++; node.map[f] = k; node.kids.push(k); }
        k.total += n;
        node = k;
      });
      node.self += n;
    });
    return tree;
  }

  var tree = build();
  var view = tree;         // the frame currently filling the full width
  var selected = tree;     // the frame whose stats we show
  var alpha = true;        // siblings sorted by name (as real flame graphs do)
  var seed = 1;

  function rng() { seed = (seed * 1664525 + 1013904223) >>> 0; return seed / 4294967296; }
  function hashName(s) { var h = 0; for (var i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0; return h % 4; }
  function sortKids(node) {
    node.kids.sort(function (a, b) { return a.name < b.name ? -1 : a.name > b.name ? 1 : 0; });
    node.kids.forEach(sortKids);
  }
  function shuffleKids(node) {
    for (var i = node.kids.length - 1; i > 0; i--) {
      var j = Math.floor(rng() * (i + 1)), t = node.kids[i]; node.kids[i] = node.kids[j]; node.kids[j] = t;
    }
    node.kids.forEach(shuffleKids);
  }
  function pct(x) { return (Math.round(x * 10) / 10).toFixed(1) + "%"; }
  function path(node) {
    var p = [];
    while (node && node.parent) { p.unshift(node.name); node = node.parent; }
    return p.length ? p.join(" > ") : "all samples";
  }
  function depthOf(node) { var d = 0; node.kids.forEach(function (k) { d = Math.max(d, depthOf(k)); }); return d + 1; }

  function draw() {
    graphEl.textContent = "";
    var rows = [], levels = depthOf(view);
    for (var i = 0; i < levels; i++) { var r = el("div", "fr-row"); rows.push(r); graphEl.appendChild(r); }
    function place(node, level, left) {
      var width = node.total / view.total * 100;
      if (width >= 0.4) {
        var b = el("button", "fr-frame fr-c" + (node === tree ? 1 : hashName(node.name)), node.name);
        b.type = "button";
        b.style.left = left + "%";
        b.style.width = width + "%";
        b.title = node.name + ": " + node.total + " samples (" + pct(node.total / tree.total * 100) + " of all)";
        b.setAttribute("aria-label", node.name + ", " + node.total + " samples, " + pct(node.total / tree.total * 100) + " of all samples. Activate to zoom in.");
        if (node === selected) b.classList.add("sel");
        b.addEventListener("click", function () { selected = node; view = node; draw(); });
        rows[level].appendChild(b);
      }
      var x = left;
      node.kids.forEach(function (k) { place(k, level + 1, x); x += k.total / view.total * 100; });
    }
    place(view, 0, 0);

    crumbEl.textContent = "Zoomed into: " + path(view) + (alpha ? "" : "   (siblings shuffled)");
    var s = selected;
    statsEl.textContent = "";
    [["Frame", s === tree ? "all samples" : s.name],
     ["Total (this frame and callees)", s.total + " samples, " + pct(s.total / tree.total * 100) + " of all"],
     ["Self (this frame's own code)", s.self + " samples, " + pct(s.self / tree.total * 100) + " of all"],
     ["Share of its caller", s.parent ? pct(s.total / s.parent.total * 100) + " of " + (s.parent === tree ? "all samples" : s.parent.name) : "n/a"]
    ].forEach(function (kv) {
      var c = el("div", "fr-stat");
      c.appendChild(el("span", "fr-stat-k", kv[0]));
      c.appendChild(el("span", "fr-stat-v", kv[1]));
      statsEl.appendChild(c);
    });
    upBtn.disabled = view === tree;
    resetBtn.disabled = view === tree && selected === tree;
    sortBtn.disabled = alpha;
  }

  resetBtn.addEventListener("click", function () { view = tree; selected = tree; draw(); });
  upBtn.addEventListener("click", function () { if (view.parent) { view = view.parent; selected = view; draw(); } });
  shuffleBtn.addEventListener("click", function () { alpha = false; shuffleKids(tree); draw(); });
  sortBtn.addEventListener("click", function () { alpha = true; sortKids(tree); draw(); });

  sortKids(tree);
  draw();
})();
