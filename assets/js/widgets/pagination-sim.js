/* Offset vs cursor pagination simulator (architecture chapter 09).

   A table of 30 items, newest first, each with an id and a creation time. The
   reader pages through it five items at a time, in one of two modes:
     offset - ORDER BY created_at DESC, id DESC LIMIT 5 OFFSET (page * 5)
     cursor - WHERE (created_at, id) < (:last_created_at, :last_id)
              ORDER BY created_at DESC, id DESC LIMIT 5
   Two buttons change the table between page requests:
     "Insert a new item at the top"  - a newer row appears (like a new order)
     "Delete an item from page 1"    - the third newest row is deleted
   The widget keeps score of what the client has received:
     duplicates - an id delivered on more than one page
     skipped    - a row that existed from the start, sits before the client's
                  position, and was never delivered
   Fully deterministic: no timers, no randomness. Simplifications: one client,
   page size fixed at 5, ids and times grow together, and the cursor is shown
   as its two values rather than as an opaque base64 string. */
(function () {
  "use strict";
  var root = document.getElementById("pagination-sim");
  if (!root) return;

  var SIZE = 5, N = 30;
  var S, focusKey = null;

  function fmt(n) { // minute n after 09:00
    var m = 9 * 60 + n;
    return ("0" + Math.floor(m / 60)).slice(-2) + ":" + ("0" + (m % 60)).slice(-2);
  }
  function fresh(mode) {
    var items = [];
    for (var i = N; i >= 1; i--) items.push({ id: i, inserted: false });
    return { mode: mode, items: items, nextId: N + 1, pages: [], seen: {}, dups: 0,
             lastId: null, msg: "Press Next page to request page 1." , done: false };
  }
  S = fresh("offset");

  function ts(id) { return "2026-10-12 " + fmt(id); }

  /* ---------- SQL for the next request ---------- */
  function nextSql() {
    if (S.mode === "offset") {
      return "SELECT id, created_at FROM items\nORDER BY created_at DESC, id DESC\nLIMIT " + SIZE + " OFFSET " + (S.pages.length * SIZE) + ";";
    }
    if (S.lastId === null) {
      return "SELECT id, created_at FROM items\nORDER BY created_at DESC, id DESC\nLIMIT " + SIZE + ";";
    }
    return "SELECT id, created_at FROM items\nWHERE (created_at, id) < ('" + ts(S.lastId) + "', " + S.lastId + ")\nORDER BY created_at DESC, id DESC\nLIMIT " + SIZE + ";";
  }

  /* ---------- actions ---------- */
  function nextPage() {
    var sql = nextSql(), rows;
    if (S.mode === "offset") {
      rows = S.items.slice(S.pages.length * SIZE, S.pages.length * SIZE + SIZE);
    } else {
      rows = S.items.filter(function (it) { return S.lastId === null || it.id < S.lastId; }).slice(0, SIZE);
    }
    var n = S.pages.length + 1;
    if (!rows.length) { S.done = true; S.msg = "That query returned no rows: you have reached the end."; return; }
    var entry = { n: n, rows: [], sql: sql };
    rows.forEach(function (it) {
      var again = !!S.seen[it.id];
      if (again) S.dups++;
      S.seen[it.id] = (S.seen[it.id] || 0) + 1;
      entry.rows.push({ id: it.id, dup: again });
    });
    S.pages.push(entry);
    S.lastId = rows[rows.length - 1].id;
    S.msg = "Page " + n + " received: " + rows.map(function (r) { return "#" + r.id; }).join(", ") + ".";
  }
  function insertTop() {
    var it = { id: S.nextId++, inserted: true };
    S.items.unshift(it);
    S.msg = "A new row #" + it.id + " (" + fmt(it.id) + ") was inserted at the top of the table.";
  }
  function deleteOne() {
    if (S.items.length < 3) return;
    var gone = S.items.splice(2, 1)[0];
    S.msg = "Row #" + gone.id + " (the third newest) was deleted from page 1's range.";
  }
  function setMode(m) { S = fresh(m); S.msg = "Switched to " + m + " pagination and reset. Press Next page."; }

  /* ---------- scoring ---------- */
  function frontier(it, idx) { // has the client's position passed this row?
    if (S.mode === "offset") return idx < S.pages.length * SIZE;
    return S.lastId !== null && it.id > S.lastId;
  }
  function skippedIds() {
    var out = [];
    S.items.forEach(function (it, idx) {
      if (!it.inserted && !S.seen[it.id] && frontier(it, idx)) out.push(it.id);
    });
    return out;
  }

  /* ---------- DOM ---------- */
  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }
  function button(label, cls, fn) {
    var b = el("button", "btn " + cls, label);
    b.type = "button";
    b.dataset.k = label;
    b.addEventListener("click", function () { fn(); focusKey = label; render(); });
    return b;
  }

  function render() {
    root.textContent = "";
    var head = el("div", "widget-head");
    head.appendChild(el("span", "widget-tag", "Try it"));
    head.appendChild(el("h4", "widget-title", "Paging while the data changes"));
    root.appendChild(head);
    root.appendChild(el("p", "widget-help", "Page through 30 items, five at a time. Then change the table between requests with the two buttons and keep paging. Compare the two modes."));

    var modes = el("div", "widget-row");
    modes.setAttribute("role", "group");
    modes.setAttribute("aria-label", "Pagination mode");
    ["offset", "cursor"].forEach(function (m) {
      var b = el("button", "btn small ps-mode" + (S.mode === m ? " primary" : ""), m === "offset" ? "Offset pagination" : "Cursor (keyset) pagination");
      b.type = "button";
      b.setAttribute("aria-pressed", S.mode === m ? "true" : "false");
      b.dataset.k = m;
      b.addEventListener("click", function () { if (S.mode !== m) { setMode(m); focusKey = m; render(); } });
      modes.appendChild(b);
    });
    root.appendChild(modes);

    var acts = el("div", "widget-row");
    var nb = button("Next page", "primary", nextPage);
    if (S.done) nb.disabled = true;
    acts.appendChild(nb);
    acts.appendChild(button("Insert a new item at the top", "", insertTop));
    acts.appendChild(button("Delete an item from page 1", "danger", deleteOne));
    acts.appendChild(button("Reset", "small", function () { S = fresh(S.mode); }));
    root.appendChild(acts);

    var sqlLabel = el("p", "ps-label", "The next request would run:");
    root.appendChild(sqlLabel);
    var pre = el("pre", "ps-sql");
    var code = el("code", "", nextSql());
    pre.appendChild(code);
    root.appendChild(pre);

    var sk = skippedIds();
    var score = el("div", "widget-row ps-score");
    var p1 = el("span", "pill", "pages received: " + S.pages.length);
    var p2 = el("span", "pill " + (S.dups ? "red" : "green"), "duplicates: " + S.dups);
    var p3 = el("span", "pill " + (sk.length ? "red" : "green"), "skipped: " + sk.length);
    score.appendChild(p1); score.appendChild(p2); score.appendChild(p3);
    root.appendChild(score);

    var status = el("div", "widget-out ps-status", S.msg);
    status.setAttribute("aria-live", "polite");
    root.appendChild(status);

    root.appendChild(el("p", "ps-label", "The table right now (newest first). Chip colour shows what the client has received:"));
    var chips = el("ul", "ps-chips");
    S.items.forEach(function (it) {
      var li = el("li", "ps-chip");
      var tags = [];
      if (S.seen[it.id] > 1) { li.className += " ps-dup"; tags.push("received " + S.seen[it.id] + " times"); }
      else if (S.seen[it.id]) { li.className += " ps-seen"; tags.push("received"); }
      else if (sk.indexOf(it.id) >= 0) { li.className += " ps-skip"; tags.push("SKIPPED"); }
      else tags.push("not yet received");
      if (it.inserted) { li.className += " ps-new"; tags.push("inserted during paging"); }
      li.appendChild(el("strong", "", "#" + it.id));
      li.appendChild(el("span", "ps-time", fmt(it.id)));
      li.setAttribute("aria-label", "item " + it.id + " at " + fmt(it.id) + ": " + tags.join(", "));
      li.title = tags.join(", ");
      if (S.seen[it.id] > 1) li.appendChild(el("span", "ps-tag", "x" + S.seen[it.id]));
      else if (sk.indexOf(it.id) >= 0) li.appendChild(el("span", "ps-tag", "skip"));
      else if (it.inserted) li.appendChild(el("span", "ps-tag", "new"));
      chips.appendChild(li);
    });
    root.appendChild(chips);

    if (S.pages.length) {
      root.appendChild(el("p", "ps-label", "What the client received, page by page:"));
      var ol = el("ol", "ps-pages");
      S.pages.forEach(function (pg) {
        var li = el("li", "");
        li.appendChild(el("span", "ps-pn", "Page " + pg.n + ": "));
        pg.rows.forEach(function (r) {
          li.appendChild(el("span", "ps-id" + (r.dup ? " ps-iddup" : ""), "#" + r.id + (r.dup ? " (again)" : "")));
        });
        ol.appendChild(li);
      });
      root.appendChild(ol);
    }
    if (focusKey !== null) {
      var all = root.querySelectorAll("button");
      for (var i = 0; i < all.length; i++) {
        if (all[i].dataset.k === focusKey && !all[i].disabled) { all[i].focus(); break; }
      }
      focusKey = null;
    }
  }

  root.className = "widget";
  render();
})();
