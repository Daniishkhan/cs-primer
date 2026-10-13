/* Join visualiser (data chapter 2).
   Two small tables, users and orders. The reader picks INNER or LEFT JOIN and
   steps through a nested-loop join: for each users row (outer loop) every orders
   row (inner loop) is compared on orders.user_id = users.id. Matches add a row to
   the result table. After a users row has seen every order with no match,
   INNER drops it and LEFT keeps it with NULLs for the orders columns.
   The step list is computed from the data, and the displayed state is rebuilt
   from the first `pos` events, so Back is exact. No libraries. */
(function () {
  "use strict";
  var root = document.getElementById("join-viz-widget");
  if (!root) return;

  var USERS = [
    { id: 1, name: "Asha" },
    { id: 2, name: "Ben" },
    { id: 3, name: "Chen" },
    { id: 4, name: "Dara" }
  ];
  var ORDERS = [
    { id: 101, user_id: 1, item: "book" },
    { id: 102, user_id: 1, item: "pen" },
    { id: 103, user_id: 2, item: "lamp" },
    { id: 104, user_id: 3, item: "mug" }
  ];

  var kind = "INNER";
  var events = [];
  var pos = 0;

  /* ---- build the event list (nested-loop join) ---- */
  function build() {
    events = [];
    USERS.forEach(function (u, ui) {
      var matched = 0;
      ORDERS.forEach(function (o, oi) {
        var m = o.user_id === u.id;
        if (m) matched++;
        events.push({ type: "cmp", ui: ui, oi: oi, match: m });
      });
      if (matched === 0) events.push({ type: kind === "LEFT" ? "keep" : "drop", ui: ui });
    });
  }

  /* ---- DOM helpers ---- */
  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }
  function btn(label, cls) {
    var b = el("button", "btn " + (cls || ""), label);
    b.type = "button";
    return b;
  }
  function table(cols, label) {
    var t = el("table", "jv-table");
    t.setAttribute("aria-label", label);
    var thead = el("thead");
    var tr = el("tr");
    cols.forEach(function (c) { tr.appendChild(el("th", null, c)); });
    thead.appendChild(tr);
    t.appendChild(thead);
    var tbody = el("tbody");
    t.appendChild(tbody);
    return { table: t, body: tbody };
  }
  function cell(v) {
    var td = el("td");
    if (v === null) td.appendChild(el("span", "jv-null", "NULL"));
    else td.textContent = String(v);
    return td;
  }

  var head = el("div", "widget-head");
  head.appendChild(el("span", "widget-tag", "Explore"));
  head.appendChild(el("h4", "widget-title", "Watch a join happen"));
  root.appendChild(head);
  root.appendChild(el("p", "widget-help", "Choose a join type, then press Step. For each user the join scans every order and keeps the pairs where orders.user_id = users.id. Keyboard: left and right arrow keys step back and forward."));

  var kindRow = el("div", "widget-row jv-kind");
  kindRow.setAttribute("role", "group");
  kindRow.setAttribute("aria-label", "Join type");
  var bInner = btn("INNER JOIN");
  var bLeft = btn("LEFT JOIN");
  kindRow.appendChild(bInner);
  kindRow.appendChild(bLeft);
  root.appendChild(kindRow);

  var sql = el("pre", "jv-sql");
  var sqlCode = el("code");
  sql.appendChild(sqlCode);
  root.appendChild(sql);

  var inputs = el("div", "jv-inputs");
  var usersBox = el("div", "jv-box");
  usersBox.appendChild(el("div", "jv-name", "users (left table)"));
  var uT = table(["id", "name"], "users table");
  usersBox.appendChild(uT.table);
  var ordersBox = el("div", "jv-box");
  ordersBox.appendChild(el("div", "jv-name", "orders (right table)"));
  var oT = table(["id", "user_id", "item"], "orders table");
  ordersBox.appendChild(oT.table);
  inputs.appendChild(usersBox);
  inputs.appendChild(ordersBox);
  root.appendChild(inputs);

  USERS.forEach(function (u) {
    var tr = el("tr");
    tr.appendChild(cell(u.id)); tr.appendChild(cell(u.name));
    uT.body.appendChild(tr);
  });
  ORDERS.forEach(function (o) {
    var tr = el("tr");
    tr.appendChild(cell(o.id)); tr.appendChild(cell(o.user_id)); tr.appendChild(cell(o.item));
    oT.body.appendChild(tr);
  });
  var uRows = Array.prototype.slice.call(uT.body.children);
  var oRows = Array.prototype.slice.call(oT.body.children);

  var controls = el("div", "widget-row");
  var bBack = btn("Back", "small");
  var bStep = btn("Step", "primary");
  var bUser = btn("Skip to next user", "small");
  var bEnd = btn("Run to end", "small");
  var bReset = btn("Reset", "small");
  [bBack, bStep, bUser, bEnd, bReset].forEach(function (b) { controls.appendChild(b); });
  root.appendChild(controls);

  var status = el("div", "widget-out jv-status");
  status.setAttribute("aria-live", "polite");
  root.appendChild(status);

  var resBox = el("div", "jv-box jv-result");
  var resName = el("div", "jv-name", "Result");
  resBox.appendChild(resName);
  var rT = table(["users.name", "orders.id", "orders.item"], "join result");
  resBox.appendChild(rT.table);
  var resEmpty = el("p", "widget-help jv-empty", "No rows yet.");
  resBox.appendChild(resEmpty);
  root.appendChild(resBox);

  /* ---- render: rebuild everything from events[0..pos) ---- */
  function render() {
    sqlCode.textContent = "SELECT users.name, orders.id, orders.item\nFROM users\n" + kind + " JOIN orders ON orders.user_id = users.id;";
    bInner.setAttribute("aria-pressed", kind === "INNER" ? "true" : "false");
    bLeft.setAttribute("aria-pressed", kind === "LEFT" ? "true" : "false");
    bInner.classList.toggle("primary", kind === "INNER");
    bLeft.classList.toggle("primary", kind === "LEFT");

    var result = [], dropped = [];
    for (var i = 0; i < pos; i++) {
      var e = events[i];
      if (e.type === "cmp" && e.match) result.push({ u: USERS[e.ui], o: ORDERS[e.oi], idx: i });
      else if (e.type === "keep") result.push({ u: USERS[e.ui], o: null, idx: i });
      else if (e.type === "drop") dropped.push(USERS[e.ui].name);
    }
    var cur = pos > 0 ? events[pos - 1] : null;

    uRows.forEach(function (r) { r.className = ""; });
    oRows.forEach(function (r) { r.className = ""; });
    if (cur) {
      uRows[cur.ui].className = "jv-cur-user";
      if (cur.type === "cmp") oRows[cur.oi].className = cur.match ? "jv-hit" : "jv-miss";
    }

    rT.body.textContent = "";
    result.forEach(function (r) {
      var tr = el("tr");
      tr.appendChild(cell(r.u.name));
      tr.appendChild(cell(r.o ? r.o.id : null));
      tr.appendChild(cell(r.o ? r.o.item : null));
      if (cur && r.idx === pos - 1) tr.className = "jv-new";
      rT.body.appendChild(tr);
    });
    resEmpty.hidden = result.length > 0;
    rT.table.hidden = result.length === 0;
    resName.textContent = "Result: " + result.length + (result.length === 1 ? " row" : " rows");

    var msg;
    if (!cur) {
      msg = "Ready. " + kind + " JOIN starts with the first users row and compares it with every orders row.";
    } else if (cur.type === "cmp") {
      var u = USERS[cur.ui], o = ORDERS[cur.oi];
      msg = "users.id = " + u.id + " (" + u.name + ") against orders.user_id = " + o.user_id + " (order " + o.id + "): " +
        (cur.match ? "match, so a result row is added." : "no match, skip.");
    } else if (cur.type === "keep") {
      msg = USERS[cur.ui].name + " matched no order. LEFT JOIN keeps the user anyway and fills the orders columns with NULL.";
    } else {
      msg = USERS[cur.ui].name + " matched no order. INNER JOIN keeps only pairs that match, so " + USERS[cur.ui].name + " disappears from the result.";
    }
    if (pos === events.length) {
      msg += " Done: " + result.length + " rows." + (dropped.length ? " Dropped by INNER JOIN: " + dropped.join(", ") + "." : "");
    }
    status.textContent = msg;

    bBack.disabled = pos === 0;
    bStep.disabled = pos === events.length;
    bUser.disabled = pos === events.length;
    bEnd.disabled = pos === events.length;
  }

  /* ---- actions ---- */
  function setKind(k) {
    if (k === kind) return;
    kind = k;
    build();
    pos = 0;
    render();
  }
  function forward() { if (pos < events.length) { pos++; render(); } }
  function back() { if (pos > 0) { pos--; render(); } }
  function nextUser() {
    if (pos >= events.length) return;
    var u = events[pos].ui;
    while (pos < events.length && events[pos].ui === u) pos++;
    render();
  }
  function toEnd() { pos = events.length; render(); }
  function reset() { pos = 0; render(); }

  bInner.addEventListener("click", function () { setKind("INNER"); });
  bLeft.addEventListener("click", function () { setKind("LEFT"); });
  bStep.addEventListener("click", forward);
  bBack.addEventListener("click", back);
  bUser.addEventListener("click", nextUser);
  bEnd.addEventListener("click", toEnd);
  bReset.addEventListener("click", reset);
  root.addEventListener("keydown", function (ev) {
    if (ev.target && ev.target.tagName === "BUTTON") {
      if (ev.key === "ArrowRight") { ev.preventDefault(); forward(); }
      else if (ev.key === "ArrowLeft") { ev.preventDefault(); back(); }
    }
  });

  build();
  render();
})();
