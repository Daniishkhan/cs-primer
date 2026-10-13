/* Dual write vs outbox vs CDC simulator (data chapter 19).

   An app places orders. Each order must end up in three places: the database
   (the source of truth), a cache (a running revenue counter and order count) and
   a search index (a list of order documents). The widget compares three ways of
   getting the order into the cache and index:
     (a) dual write   - the app writes the DB, then the cache and the index itself;
     (b) outbox       - the app writes the order and an outbox row in ONE transaction;
                        a relay publishes unsent outbox rows to a log and marks them sent;
     (c) CDC          - the app writes only the order; a connector tails the database's
                        committed change log (WAL) and publishes each change to the log,
                        remembering its position.
   In (b) and (c) the cache and index are consumers of the log, each with its own offset.
   Delivery is at-least-once: a relay or connector that crashes after publishing but
   before recording progress publishes the same events again. The "idempotent
   consumers" box makes the consumers remember event ids and skip repeats.

   Failures (armed, then they fire once):
     f1  app crashes after the DB commit and before any publish / cache / index write
     f2  the cache/index update (the "publish") succeeds, then the DB transaction rolls back
     f3  the relay/connector crashes after publishing, before recording that it did
   Fully deterministic: no timers, no randomness.

   Simplifications: one DB transaction per order; the log never loses events; the
   consumers always apply an event to the cache and the index together at the same
   moment; in (a) the cache and index writes are plain increments/appends. */
(function () {
  "use strict";
  var root = document.getElementById("outbox-sim");
  if (!root) return;

  var TOTALS = [40, 15, 99, 25, 60, 10];
  var MODES = [
    { id: "a", label: "(a) Dual write", help: "The app writes the database, then writes the cache and the search index itself. Three separate writes, no shared transaction." },
    { id: "b", label: "(b) Outbox + relay", help: "The app writes the order and an outbox row in one transaction. A relay process publishes unsent outbox rows to the log, then marks them sent. Cache and index consume the log." },
    { id: "c", label: "(c) CDC from the log", help: "The app writes only the order. A connector (Debezium-style) tails the database's committed change log and publishes each change to the log, remembering its position. Cache and index consume the log." }
  ];
  var FAILS = [
    { id: "none", label: "No failure" },
    { id: "f1", label: "Crash after DB commit, before publish" },
    { id: "f2", label: "Publish succeeds, DB rollback" },
    { id: "f3", label: "Relay crashes after publish, before marking sent" }
  ];

  var S;
  function fresh(mode, idem) {
    return { mode: mode, idem: idem, armed: "none", next: 0,
      db: [], cache: { revenue: 0, count: 0 }, index: [],
      src: [], topic: [], off: { cache: 0, index: 0 }, seen: { cache: {}, index: {} },
      log: [] };
  }
  S = fresh("a", false);

  function say(text, bad) { S.log.push({ text: text, bad: !!bad }); if (S.log.length > 40) S.log.shift(); }
  function orderOf(n) { return { id: 101 + n, total: TOTALS[n % TOTALS.length] }; }

  /* ---------- actions ---------- */
  function place() {
    var o = orderOf(S.next); S.next++;
    var f = S.armed, label = "order #" + o.id + " ($" + o.total + ")";
    if (f === "f1" || f === "f2") S.armed = "none";
    if (S.mode === "a") {
      if (f === "f2") {
        S.cache.revenue += o.total; S.cache.count++; S.index.push(o.id);
        say("Placing " + label + ": the app updated the cache and the index, then COMMIT failed and the database rolled back. The order does not exist, but the cache and index say it does.", true);
      } else if (f === "f1") {
        S.db.push(o);
        say("Placing " + label + ": the database committed, then the app crashed before touching the cache or the index. The order exists only in the database. Nothing will retry.", true);
      } else {
        S.db.push(o); S.cache.revenue += o.total; S.cache.count++; S.index.push(o.id);
        say("Placing " + label + ": database, cache and index all written. Fine this time.");
      }
      return;
    }
    var pipe = S.mode === "b" ? "outbox row" : "WAL record";
    if (f === "f2") {
      say("Placing " + label + ": the transaction rolled back. " + (S.mode === "b"
        ? "The order and its outbox row were in the same transaction, so both vanished. Nothing was published."
        : "A rolled-back transaction never appears in the committed change log, so the connector never sees it. Nothing was published."));
      return;
    }
    S.db.push(o); S.src.push({ id: o.id, total: o.total, sent: false });
    if (f === "f1") {
      say("Placing " + label + ": the transaction committed (order + " + pipe + ") and then the app crashed. Nothing is lost: the " + pipe + " is already durable and waits for the " + (S.mode === "b" ? "relay" : "connector") + ".");
    } else {
      say("Placing " + label + ": committed, with its " + pipe + ". The cache and index are behind until the " + (S.mode === "b" ? "relay" : "connector") + " runs.");
    }
  }

  function applyEvent(name, ev) {
    if (S.idem && S.seen[name][ev.id]) { return "skip"; }
    S.seen[name][ev.id] = true;
    if (name === "cache") { S.cache.revenue += ev.total; S.cache.count++; }
    else S.index.push(ev.id);
    return "apply";
  }
  function consume() {
    var applied = 0, skipped = 0;
    ["cache", "index"].forEach(function (name) {
      while (S.off[name] < S.topic.length) {
        var r = applyEvent(name, S.topic[S.off[name]]);
        S.off[name]++;
        if (r === "apply") applied++; else skipped++;
      }
    });
    return { applied: applied, skipped: skipped };
  }
  function run() {
    var who = S.mode === "b" ? "relay" : "connector";
    var unsent = S.src.filter(function (e) { return !e.sent; });
    var crashed = false;
    if (unsent.length) {
      unsent.forEach(function (e) { S.topic.push({ id: e.id, total: e.total }); });
      if (S.armed === "f3") {
        S.armed = "none"; crashed = true;
        say("The " + who + " published " + unsent.length + " event" + (unsent.length > 1 ? "s" : "") + " to the log, then crashed before " + (S.mode === "b" ? "marking the outbox rows sent" : "saving its position") + ". On restart it will publish them again.", true);
      } else {
        unsent.forEach(function (e) { e.sent = true; });
        say("The " + who + " published " + unsent.length + " event" + (unsent.length > 1 ? "s" : "") + " and recorded that it did.");
      }
    } else if (S.armed === "f3") {
      say("The " + who + " had nothing to publish, so the armed failure did not fire. Place an order first.");
    } else {
      say("The " + who + " found nothing new to publish.");
    }
    var c = consume();
    if (c.applied || c.skipped) {
      say("The cache and index consumers read the log: " + c.applied + " change" + (c.applied === 1 ? "" : "s") + " applied" +
        (c.skipped ? ", " + c.skipped + " duplicate" + (c.skipped === 1 ? "" : "s") + " skipped by the idempotent check." : (crashed ? "." : ".")),
        false);
    }
  }

  /* ---------- verdict ---------- */
  function truth() {
    var rev = 0; S.db.forEach(function (o) { rev += o.total; });
    return { revenue: rev, count: S.db.length, ids: S.db.map(function (o) { return o.id; }).sort() };
  }
  function verdict() {
    var t = truth(), ix = S.index.slice().sort();
    var cacheOk = S.cache.revenue === t.revenue && S.cache.count === t.count;
    var indexOk = ix.join() === t.ids.join();
    var pending = S.src.filter(function (e) { return !e.sent; }).length;
    var unread = (S.topic.length - S.off.cache) + (S.topic.length - S.off.index);
    return { cacheOk: cacheOk, indexOk: indexOk, ok: cacheOk && indexOk, pending: pending, unread: unread, t: t };
  }

  /* ---------- rendering ---------- */
  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function btn(label, cls, fn) { var b = el("button", "btn " + (cls || ""), label); b.type = "button"; b.addEventListener("click", fn); return b; }
  function panel(title, cls, okState) {
    var p = el("div", "ob-pane " + cls + (okState === false ? " ob-bad" : ""));
    p.appendChild(el("h5", null, title)); return p;
  }
  function chips(items, empty) {
    var c = el("div", "ob-chips");
    if (!items.length) c.appendChild(el("span", "ob-none", empty));
    items.forEach(function (it) { c.appendChild(el("span", "ob-chip " + (it.cls || ""), it.text)); });
    return c;
  }

  function render() {
    var v = verdict(), m = MODES.filter(function (x) { return x.id === S.mode; })[0];
    root.textContent = "";
    var head = el("div", "widget-head");
    head.appendChild(el("span", "widget-tag", "Simulator"));
    head.appendChild(el("span", "widget-title", "Dual write vs outbox vs CDC"));
    root.appendChild(head);
    root.appendChild(el("p", "widget-help", "An app places orders. Each order must reach the database, a cache and a search index. Pick a way to keep them in sync, arm a failure, place orders, and watch whether the three agree."));

    /* mode */
    root.appendChild(el("p", "ob-label", "1. How the cache and index are kept in sync"));
    var mrow = el("div", "ob-btns"); mrow.setAttribute("role", "group"); mrow.setAttribute("aria-label", "Synchronisation method");
    MODES.forEach(function (x) {
      var b = btn(x.label, "", function () { S = fresh(x.id, S.idem); render(); });
      b.setAttribute("aria-pressed", String(x.id === S.mode)); mrow.appendChild(b);
    });
    root.appendChild(mrow);
    root.appendChild(el("p", "ob-desc", m.help));

    /* failure */
    root.appendChild(el("p", "ob-label", "2. Arm a failure (it fires once)"));
    var frow = el("div", "ob-btns"); frow.setAttribute("role", "group"); frow.setAttribute("aria-label", "Failure to inject");
    FAILS.forEach(function (x) {
      var dis = S.mode === "a" && x.id === "f3";
      var b = btn(x.label, "", function () { if (!dis) { S.armed = x.id; render(); } });
      b.setAttribute("aria-pressed", String(x.id === S.armed));
      if (dis) { b.disabled = true; b.title = "Mode (a) has no relay to crash."; }
      frow.appendChild(b);
    });
    root.appendChild(frow);
    var armedNote = S.armed === "none" ? "No failure armed: everything works."
      : S.armed === "f3" ? "Armed: fires the next time the " + (S.mode === "b" ? "relay" : "connector") + " has something to publish."
      : "Armed: fires on the next order you place.";
    root.appendChild(el("p", "ob-desc", armedNote + (S.mode === "a" ? " (Mode (a) has no relay, so the third failure is unavailable.)" : "")));

    /* actions */
    root.appendChild(el("p", "ob-label", "3. Run it"));
    var arow = el("div", "ob-btns");
    var o = orderOf(S.next);
    var pb = btn("Place order #" + o.id + " ($" + o.total + ")", "primary", function () { place(); render(); });
    arow.appendChild(pb);
    if (S.mode !== "a") arow.appendChild(btn(S.mode === "b" ? "Run relay + consumers" : "Run connector + consumers", "", function () { run(); render(); }));
    arow.appendChild(btn("Reset", "", function () { S = fresh(S.mode, S.idem); render(); }));
    root.appendChild(arow);
    var lab = el("label", "ob-check");
    var cb = document.createElement("input"); cb.type = "checkbox"; cb.checked = S.idem;
    cb.addEventListener("change", function () { S.idem = cb.checked; render(); });
    lab.appendChild(cb);
    lab.appendChild(el("span", null, "Consumers are idempotent (remember event ids and skip repeats)" + (S.mode === "a" ? " - no effect in mode (a): nothing is ever redelivered" : "")));
    root.appendChild(lab);

    /* state */
    root.appendChild(el("p", "ob-label", "State of the world"));
    var grid = el("div", "ob-grid");
    var pdb = panel("Database (truth)", "db", true);
    pdb.appendChild(chips(S.db.map(function (x) { return { text: "#" + x.id + " $" + x.total }; }), "no orders"));
    pdb.appendChild(el("p", "ob-note", "revenue $" + v.t.revenue + ", " + v.t.count + " orders"));
    grid.appendChild(pdb);

    var pc = panel("Cache", "cache", v.cacheOk);
    pc.appendChild(el("p", "ob-big", "revenue $" + S.cache.revenue));
    pc.appendChild(el("p", "ob-note", S.cache.count + " orders counted " + (v.cacheOk ? "(matches)" : "(should be $" + v.t.revenue + ", " + v.t.count + ")")));
    grid.appendChild(pc);

    var pi = panel("Search index", "index", v.indexOk);
    var cnt = {}; S.index.forEach(function (id) { cnt[id] = (cnt[id] || 0) + 1; });
    var items = Object.keys(cnt).sort().map(function (id) { return { text: "#" + id + (cnt[id] > 1 ? " x" + cnt[id] : ""), cls: cnt[id] > 1 ? "dup" : "" }; });
    pi.appendChild(chips(items, "no documents"));
    pi.appendChild(el("p", "ob-note", v.indexOk ? "matches the database" : "does not match the database"));
    grid.appendChild(pi);
    root.appendChild(grid);

    if (S.mode !== "a") {
      var pipe = el("div", "ob-grid ob-grid2");
      var ps = panel(S.mode === "b" ? "Outbox table (in the DB)" : "Database change log (WAL)", "src", true);
      ps.appendChild(chips(S.src.map(function (e) { return { text: "#" + e.id + (e.sent ? (S.mode === "b" ? " sent" : " read") : (S.mode === "b" ? " unsent" : " unread")), cls: e.sent ? "" : "wait" }; }), "empty"));
      ps.appendChild(el("p", "ob-note", S.mode === "b" ? "The relay marks a row sent only after publishing it." : "The connector saves its position only after publishing."));
      pipe.appendChild(ps);
      var pl = panel("Log (topic)", "topic", true);
      pl.appendChild(chips(S.topic.map(function (e, i) { return { text: i + ": #" + e.id }; }), "empty"));
      pl.appendChild(el("p", "ob-note", "consumer offsets: cache " + S.off.cache + ", index " + S.off.index));
      pipe.appendChild(pl);
      root.appendChild(pipe);
    }

    /* verdict */
    var vd = el("div", "ob-verdict " + (v.ok ? (v.pending ? "ob-wait" : "ob-good") : (S.mode !== "a" && (v.pending || v.unread) ? "ob-wait" : "ob-badv")));
    var title, body;
    if (v.ok && !v.pending) { title = "In sync"; body = "Database, cache and index agree."; }
    else if (v.ok) { title = "In sync, for now"; body = v.pending + " event" + (v.pending > 1 ? "s" : "") + " will be sent again (already delivered once). " + (S.idem ? "Idempotent consumers will skip the repeats." : "Without idempotent consumers the repeats will be applied twice. Run it again and see.") }
    else if (S.mode !== "a" && (v.pending || v.unread)) { title = "Behind, but it will catch up"; body = "The cache or index is missing changes that are waiting in the " + (S.mode === "b" ? "outbox" : "change log") + ". Running the " + (S.mode === "b" ? "relay" : "connector") + " delivers them."; }
    else if (S.mode !== "a" && !v.pending) { title = "DIVERGED: duplicates were applied"; body = "A redelivered event was applied twice because the consumers are not idempotent. Tick the box and reset to compare."; }
    else { title = "DIVERGED, and nothing will fix it"; body = "The three stores disagree and no process knows they should be repaired. Only a manual reconciliation job would notice."; }
    var hl = el("strong", null, title); vd.appendChild(hl); vd.appendChild(document.createTextNode(": " + body));
    root.appendChild(vd);

    /* event log */
    root.appendChild(el("p", "ob-label", "What happened"));
    var ol = el("ol", "ob-log"); ol.setAttribute("aria-live", "polite");
    if (!S.log.length) ol.appendChild(el("li", null, "Nothing yet. Try mode (a) with the first failure armed, then place an order."));
    S.log.slice().reverse().forEach(function (l) { ol.appendChild(el("li", l.bad ? "bad" : "", l.text)); });
    root.appendChild(ol);
  }

  render();
})();
