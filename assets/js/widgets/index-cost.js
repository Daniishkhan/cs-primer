/* Index explorer (data chapter 7).

   A 40-row table (name, city, age) and one query at a time. Pick a query and pick which index
   exists; the widget builds that index (sorted entries pointing at row ids), decides how a
   simple planner would use it, and animates what gets examined.
   Rules modelled (the same ones real B-tree indexes follow):
   - An index can be searched only through its LEFTMOST columns: equality columns first, then at
     most one range column. Anything after a range column is only filtered, not searched.
   - If the index holds every column the query needs, no table row is fetched (covering).
   - If the query's ORDER BY matches the index order, the first N entries are enough and no sort
     is needed. Otherwise every row must be read and sorted.
   - Remaining conditions the index cannot search are checked on the entry (if the column is in
     the index) or on the fetched row (if not). Many databases behave this way; details vary.
   Not modelled: pages, the cost of the tree descent, statistics, choosing between several
   indexes, writes. The counts are rows and entries, not milliseconds. */
(function () {
  "use strict";
  var root = document.getElementById("index-cost");
  if (!root) return;

  var DATA = [["Ana","Cairo",48],["Ben","Lima",24],["Chen","Quito",56],["Dara","Cairo",52],["Eli","Lima",44],["Fay","Lima",19],["Gus","Lima",47],["Hana","Oslo",54],["Ivo","Oslo",58],["Jun","Oslo",62],["Kai","Cairo",66],["Lea","Cairo",66],["Moe","Lima",30],["Nia","Lima",66],["Omar","Pune",74],["Pia","Oslo",57],["Quin","Cairo",68],["Rae","Quito",78],["Sol","Oslo",42],["Tess","Cairo",53],["Uma","Cairo",48],["Vik","Quito",48],["Wen","Oslo",63],["Xia","Lima",39],["Yara","Lima",41],["Zed","Oslo",77],["Abe","Cairo",41],["Bea","Cairo",49],["Cy","Pune",41],["Dev","Pune",40],["Eva","Pune",48],["Fin","Oslo",67],["Gia","Oslo",35],["Hal","Quito",55],["Ida","Pune",43],["Jo","Oslo",41],["Kit","Lima",76],["Liv","Cairo",23],["Max","Pune",43],["Noor","Pune",63]];
  var ROWS = DATA.map(function (d, i) { return { id: i + 1, name: d[0], city: d[1], age: d[2] }; });

  var QUERIES = [
    { id: "q1", sql: "SELECT * FROM people WHERE city = 'Lima'", city: true, age: null, all: true },
    { id: "q2", sql: "SELECT * FROM people WHERE age > 60", city: false, age: 60, all: true },
    { id: "q3", sql: "SELECT * FROM people WHERE city = 'Lima' AND age > 30", city: true, age: 30, all: true },
    { id: "q4", sql: "SELECT * FROM people ORDER BY age LIMIT 5", city: false, age: null, order: true, all: true },
    { id: "q5", sql: "SELECT city, age FROM people WHERE city = 'Lima' AND age > 30", city: true, age: 30, all: false }
  ];
  var INDEXES = [
    { id: "none", label: "No index", cols: null },
    { id: "c", label: "(city)", cols: ["city"] },
    { id: "a", label: "(age)", cols: ["age"] },
    { id: "ca", label: "(city, age)", cols: ["city", "age"] },
    { id: "ac", label: "(age, city)", cols: ["age", "city"] }
  ];
  var LIMIT = 5, STEP_MS = 110;

  var ui = {}, qi = 0, xi = 0, P = null, shown = 0, timer = null;

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  function pred(q, r) { return (!q.city || r.city === "Lima") && (q.age == null || r.age > q.age); }
  function reduced() { return window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches; }

  /* ---------- the planner ---------- */
  function buildEntries(cols) {
    var es = ROWS.map(function (r) { return { id: r.id, key: cols.map(function (c) { return r[c]; }) }; });
    es.sort(function (a, b) {
      for (var i = 0; i < a.key.length; i++) {
        if (a.key[i] < b.key[i]) return -1;
        if (a.key[i] > b.key[i]) return 1;
      }
      return a.id - b.id;
    });
    es.forEach(function (e, i) { e.pos = i; });
    return es;
  }

  function plan(q, ix) {
    var steps = [], p = { entries: null, steps: steps, sort: false, covering: false, planText: [], note: "", seekFrom: -1, seekTo: -1 };
    var cols = ix.cols, r;
    function scan(why) {
      ROWS.forEach(function (row) { steps.push({ row: row.id, hit: pred(q, row) && !q.order }); });
      p.planText = ["SCAN people"];
      p.note = why;
      if (q.order) {
        p.sort = true; p.planText.push("USE TEMP B-TREE FOR ORDER BY");
        p.note = why + " Every row has to be read and sorted before the first 5 can be returned.";
        // after sorting, the five smallest ages are the hits
        var top = ROWS.slice().sort(function (a, b) { return a.age - b.age || a.id - b.id; }).slice(0, LIMIT), ids = {};
        top.forEach(function (t) { ids[t.id] = true; });
        steps.forEach(function (s) { s.hit = !!ids[s.row]; });
      }
    }
    if (!cols) { scan("No index, so the only option is to read the whole table."); return p; }
    p.entries = buildEntries(cols);
    var idxName = "idx_" + cols.join("_");

    // ORDER BY age LIMIT n
    if (q.order) {
      if (cols[0] === "age") {
        p.entries.slice(0, LIMIT).forEach(function (e) { steps.push({ entry: e.pos, row: e.id, hit: true }); });
        p.seekFrom = 0; p.seekTo = LIMIT - 1;
        p.planText = ["SCAN people USING INDEX " + idxName];
        p.note = "The index is already sorted by age, so the first " + LIMIT + " entries are the answer: no sort, and we stop early.";
      } else {
        scan("The index on " + ix.label + " is not sorted by age, so it does not help.");
      }
      return p;
    }

    // how much of the index can be searched?
    var seek = null, indexFilter = null, text = "", used;
    if (cols[0] === "city" && q.city) {
      if (cols[1] === "age" && q.age != null) {
        seek = function (e) { return e.key[0] === "Lima" && e.key[1] > q.age; };
        text = "(city=? AND age>?)"; used = "both columns, in order: equality on city, then the range on age";
      } else {
        seek = function (e) { return e.key[0] === "Lima"; };
        text = "(city=?)"; used = "the city part";
      }
    } else if (cols[0] === "age" && q.age != null) {
      seek = function (e) { return e.key[0] > q.age; };
      text = "(age>?)"; used = "the age range";
      if (cols[1] === "city" && q.city) indexFilter = function (e) { return e.key[1] === "Lima"; };
    }
    if (!seek) {
      scan("The leftmost column of " + ix.label + " is " + cols[0] + ", and this query has no condition on " + cols[0] + ", so the index cannot be searched.");
      return p;
    }

    var need = q.all ? ["*"] : ["city", "age"];
    p.covering = !q.all && need.every(function (c) { return cols.indexOf(c) >= 0; });
    var first = -1, last = -1;
    p.entries.forEach(function (e) { if (seek(e)) { if (first < 0) first = e.pos; last = e.pos; } });
    p.seekFrom = first; p.seekTo = last;
    for (var i = first; i >= 0 && i <= last; i++) {
      var e = p.entries[i];
      r = ROWS[e.id - 1];
      if (indexFilter && !indexFilter(e)) { steps.push({ entry: e.pos, row: null, hit: false }); continue; }
      if (p.covering) { steps.push({ entry: e.pos, row: null, hit: pred(q, r) }); continue; }
      steps.push({ entry: e.pos, row: e.id, hit: pred(q, r) });
    }
    p.planText = ["SEARCH people USING " + (p.covering ? "COVERING " : "") + "INDEX " + idxName + " " + text];
    p.note = "The index can be searched through " + used + ".";
    if (indexFilter) p.note += " The city test is then made on each entry itself, so only matching rows are fetched, but every entry in the age range is still examined.";
    else if (!p.covering && q.city && cols.indexOf("age") < 0 && q.age != null) p.note += " The age test needs the row, so every Lima row is fetched and then checked.";
    else if (!p.covering && q.age != null && q.city && cols[0] === "age") p.note += " The city test needs the row, so every row in the age range is fetched and checked.";
    if (p.covering) p.note += " The index holds every column the query needs, so no table row is fetched at all (an index-only scan).";
    return p;
  }

  /* ---------- drawing ---------- */
  function buildTables() {
    ui.tbody.textContent = "";
    ROWS.forEach(function (r) {
      var tr = el("tr");
      tr.id = "ic-r" + r.id;
      [String(r.id), r.name, r.city, String(r.age)].forEach(function (t, i) { tr.appendChild(el("td", i === 3 ? "ic-num" : "", t)); });
      ui.tbody.appendChild(tr);
    });
  }
  function buildIndexList() {
    ui.entries.textContent = "";
    ui.rowEls = null;
    if (!P.entries) {
      ui.idxMsg.hidden = false; ui.idxMsg.textContent = "No index exists. The database has only the table to work with.";
      ui.idxWrap.hidden = true; return;
    }
    ui.idxMsg.hidden = true; ui.idxWrap.hidden = false;
    var cols = INDEXES[xi].cols;
    ui.idxHead.textContent = "Index " + INDEXES[xi].label + ": sorted entries → row id";
    P.entries.forEach(function (e) {
      var li = el("li", "ic-ent");
      li.id = "ic-e" + e.pos;
      li.appendChild(el("span", "ic-key", e.key.join(", ")));
      li.appendChild(el("span", "ic-ptr", "→ #" + e.id));
      ui.entries.appendChild(li);
    });
    ui.idxCols = cols;
  }

  function paint() {
    var i, n, rows = ui.tbody.children, ents = ui.entries.children;
    for (i = 0; i < rows.length; i++) rows[i].className = "";
    for (i = 0; i < ents.length; i++) ents[i].className = "ic-ent" + (i >= P.seekFrom && i <= P.seekTo && P.seekFrom >= 0 ? " ic-range" : "");
    var entriesSeen = 0, rowsRead = 0, hits = 0, now = null;
    for (n = 0; n < shown; n++) {
      var s = P.steps[n];
      if (s.entry != null) { entriesSeen++; ents[s.entry].className += " ic-seen" + (s.row == null && s.hit ? " ic-hit" : "") + (s.row == null && !s.hit ? " ic-miss" : ""); }
      if (s.row != null) { rowsRead++; rows[s.row - 1].className = s.hit ? "ic-hit" : "ic-miss"; }
      if (s.hit) hits++;
      if (n === shown - 1) now = s;
    }
    if (now) {
      if (now.row != null) rows[now.row - 1].className += " ic-now";
      else if (now.entry != null) ents[now.entry].className += " ic-now";
      var target = now.row != null ? rows[now.row - 1] : ents[now.entry];
      keepVisible(now.row != null ? ui.tblScroll : ui.entScroll, target);
    }
    var done = shown >= P.steps.length;
    ui.sEntries.textContent = String(entriesSeen);
    ui.sRows.textContent = String(rowsRead);
    ui.sRet.textContent = String(hits);
    ui.step.textContent = "Step " + shown + " of " + P.steps.length;
    ui.bStep.disabled = done;
    ui.bRun.textContent = timer ? "Pause" : (shown === 0 || done ? "Run" : "Resume");
    ui.done.hidden = !done;
  }
  function keepVisible(scroller, node) {
    if (!node || !scroller) return;
    var t = node.offsetTop, b = t + node.offsetHeight;
    if (t < scroller.scrollTop) scroller.scrollTop = Math.max(0, t - 4);
    else if (b > scroller.scrollTop + scroller.clientHeight) scroller.scrollTop = b - scroller.clientHeight + 4;
  }

  function summarise() {
    var q = QUERIES[qi], entries = 0, rows = 0, hits = 0;
    P.steps.forEach(function (s) { if (s.entry != null) entries++; if (s.row != null) rows++; if (s.hit) hits++; });
    ui.plan.textContent = P.planText.join("  +  ");
    ui.vSort.textContent = P.sort ? "Yes" : "No";
    ui.vSort.className = "pill " + (P.sort ? "red" : "green");
    var cov = P.covering ? "Yes" : (q.all ? "No (SELECT * needs the row)" : (P.entries ? "No (a needed column is missing)" : "No"));
    ui.vCov.textContent = cov;
    ui.vCov.className = "pill " + (P.covering ? "green" : "");
    ui.final.textContent = "";
    var b = el("strong", "", "Result: ");
    ui.final.appendChild(b);
    ui.final.appendChild(document.createTextNode(
      (P.entries ? entries + " index entries and " : "") + rows + " table row" + (rows === 1 ? "" : "s") + " examined to return " + hits + " row" + (hits === 1 ? "" : "s") +
      ". Reading the whole table would examine " + ROWS.length + " rows."));
    ui.note.textContent = P.note;
  }

  function select() {
    stop();
    updateSql();
    P = plan(QUERIES[qi], INDEXES[xi]);
    shown = 0;
    buildIndexList();
    summarise();
    paint();
  }
  function stop() { if (timer) { clearInterval(timer); timer = null; } }
  function advance() {
    if (shown < P.steps.length) shown++;
    if (shown >= P.steps.length) stop();
    paint();
  }
  function onRun() {
    if (timer) { stop(); paint(); return; }
    if (shown >= P.steps.length) { shown = 0; paint(); }
    if (reduced()) { shown = P.steps.length; paint(); return; }
    timer = setInterval(advance, STEP_MS);
    paint();
  }
  function onStep() { stop(); advance(); }
  function onReset() { stop(); shown = 0; paint(); }
  function onAll() { stop(); shown = P.steps.length; paint(); }

  /* ---------- UI ---------- */
  function build() {
    root.textContent = "";
    var head = el("div", "widget-head");
    head.appendChild(el("span", "widget-tag", "Interactive"));
    head.appendChild(el("p", "widget-title", "Index explorer"));
    root.appendChild(head);
    root.appendChild(el("p", "widget-help", "Pick a query and an index, then press Run (or Step) to watch what the database examines. Try the same query with different indexes, and the same index with different queries."));

    var r1 = el("div", "widget-row ic-pick");
    var f1 = el("div", "ic-field"), l1 = el("label", "ic-lab", "Query"); l1.setAttribute("for", "ic-q");
    ui.q = el("select", "mono"); ui.q.id = "ic-q";
    QUERIES.forEach(function (q, i) { var o = el("option", "", q.sql.replace("SELECT * FROM people ", "").replace("SELECT city, age FROM people ", "SELECT city, age … ")); o.value = String(i); ui.q.appendChild(o); });
    f1.appendChild(l1); f1.appendChild(ui.q);
    var f2 = el("div", "ic-field"), l2 = el("label", "ic-lab", "Index that exists"); l2.setAttribute("for", "ic-x");
    ui.x = el("select", "mono"); ui.x.id = "ic-x";
    INDEXES.forEach(function (x, i) { var o = el("option", "", x.label); o.value = String(i); ui.x.appendChild(o); });
    f2.appendChild(l2); f2.appendChild(ui.x);
    r1.appendChild(f1); r1.appendChild(f2);
    root.appendChild(r1);
    ui.q.addEventListener("change", function () { qi = parseInt(ui.q.value, 10); select(); });
    ui.x.addEventListener("change", function () { xi = parseInt(ui.x.value, 10); select(); });

    ui.sqlLine = el("pre", "ic-sql");
    var code = el("code"); ui.sqlCode = code; ui.sqlLine.appendChild(code);
    root.appendChild(ui.sqlLine);

    var r2 = el("div", "widget-row");
    ui.bRun = el("button", "btn primary small", "Run"); ui.bRun.type = "button"; ui.bRun.addEventListener("click", onRun);
    ui.bStep = el("button", "btn small", "Step"); ui.bStep.type = "button"; ui.bStep.addEventListener("click", onStep);
    var bAll = el("button", "btn small", "Show all"); bAll.type = "button"; bAll.addEventListener("click", onAll);
    var bRs = el("button", "btn small", "Reset"); bRs.type = "button"; bRs.addEventListener("click", onReset);
    ui.step = el("span", "ic-stepno", "");
    [ui.bRun, ui.bStep, bAll, bRs, ui.step].forEach(function (x) { r2.appendChild(x); });
    root.appendChild(r2);

    var panes = el("div", "ic-panes");
    var pl = el("div", "ic-pane");
    pl.appendChild(el("h5", "", "Table: 40 rows in table order"));
    ui.tblScroll = el("div", "ic-scroll"); ui.tblScroll.tabIndex = 0;
    ui.tblScroll.setAttribute("role", "region"); ui.tblScroll.setAttribute("aria-label", "Table rows");
    var tbl = el("table", "ic-tbl");
    var th = el("thead"), thr = el("tr");
    ["id", "name", "city", "age"].forEach(function (h) { thr.appendChild(el("th", "", h)); });
    th.appendChild(thr); tbl.appendChild(th);
    ui.tbody = el("tbody"); tbl.appendChild(ui.tbody);
    ui.tblScroll.appendChild(tbl); pl.appendChild(ui.tblScroll);
    panes.appendChild(pl);

    var pr = el("div", "ic-pane ic-pane-idx");
    ui.idxHead = el("h5", "", "Index");
    pr.appendChild(ui.idxHead);
    ui.idxMsg = el("p", "ic-msg", "");
    pr.appendChild(ui.idxMsg);
    ui.idxWrap = el("div");
    ui.entScroll = el("div", "ic-scroll"); ui.entScroll.tabIndex = 0;
    ui.entScroll.setAttribute("role", "region"); ui.entScroll.setAttribute("aria-label", "Index entries");
    ui.entries = el("ol", "ic-ents");
    ui.entScroll.appendChild(ui.entries); ui.idxWrap.appendChild(ui.entScroll);
    pr.appendChild(ui.idxWrap);
    panes.appendChild(pr);
    root.appendChild(panes);

    var legend = el("p", "ic-legend");
    [["ic-key-hit", "match"], ["ic-key-miss", "examined, rejected"], ["ic-key-range", "index range the planner can search"]].forEach(function (l) {
      legend.appendChild(el("span", "ic-sw " + l[0])); legend.appendChild(document.createTextNode(l[1] + "   "));
    });
    root.appendChild(legend);

    var out = el("div", "widget-out");
    var pr1 = el("p", "ic-line"); pr1.appendChild(el("span", "ic-l", "Plan: ")); ui.plan = el("code", "", ""); pr1.appendChild(ui.plan);
    out.appendChild(pr1);
    var grid = el("div", "ic-stats");
    function stat(label, cls, text) { var b = el("span", "ic-stat"); b.appendChild(el("span", "ic-stat-l", label)); var v = el("span", cls, text); b.appendChild(v); grid.appendChild(b); return v; }
    ui.sEntries = stat("Index entries examined", "pill purple", "0");
    ui.sRows = stat("Table rows read", "pill blue", "0");
    ui.sRet = stat("Rows returned so far", "pill green", "0");
    ui.vSort = stat("Sort needed?", "pill", "");
    ui.vCov = stat("Index covers query?", "pill", "");
    out.appendChild(grid);
    ui.note = el("p", "ic-note", "");
    out.appendChild(ui.note);
    root.appendChild(out);

    var fin = el("div", "widget-out ic-final"); fin.setAttribute("aria-live", "polite");
    ui.final = el("p", "", ""); ui.done = fin; fin.appendChild(ui.final); fin.hidden = true;
    root.appendChild(fin);
  }

  function updateSql() { ui.sqlCode.textContent = QUERIES[qi].sql + ";"; }
  build();
  buildTables();
  select();
})();
