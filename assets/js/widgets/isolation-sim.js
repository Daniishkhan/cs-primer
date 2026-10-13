/* Isolation anomaly simulator (data chapter 11).
   Two transactions, T1 and T2, run small programs against a tiny multi-version
   store. The reader picks a scenario and an isolation level, then chooses which
   transaction takes the next step. The engine is a pure state machine (state is
   plain data, programs live outside it), so the "how many interleavings go wrong"
   count is computed by exhaustive search over the very same engine.

   Simplifications (also stated in the widget's help text):
   - Every key holds a list of committed versions; a commit adds one version per
     written key. Dirty reads are never shown (Read Uncommitted is not offered).
   - Read Committed: each read sees the latest committed version at that moment.
     Writes take a row lock held until the transaction ends; a writer that finds
     the row locked waits, then proceeds. A write whose value the application
     computed earlier keeps that (possibly stale) value.
   - Snapshot isolation: the snapshot is taken at the first statement. A write to
     a row that another transaction committed after the snapshot aborts
     (first-updater-wins, as in Postgres: a second writer waits for the first to
     finish, then aborts if the first committed; other products may detect the
     conflict at commit instead).
   - Serializable: snapshot isolation plus read/write tracking. At commit, if this
     transaction and an already committed concurrent one each read something the
     other wrote, the committer is aborted. Real SSI tracks chains among many
     transactions and can also abort earlier or with false positives.
   - Two transactions, no deadlocks, no unique constraints, no SELECT FOR UPDATE. */
(function () {
  "use strict";
  var root = document.getElementById("isolation-sim");
  if (!root) return;

  var SKIP = { skip: true };

  /* ---------------- scenarios ---------------- */
  function read(keys, into, sql, agg) {
    return { t: "read", keys: keys, into: into, sql: sql, agg: agg || function (v) { return v[0]; } };
  }
  function write(key, sql, calc, when) { return { t: "write", key: key, sql: sql, calc: calc, when: when }; }
  var COMMIT = { t: "commit", sql: "COMMIT" };

  function count1(vals) { return vals.filter(function (v) { return v === 1; }).length; }
  function countRows(vals) { return vals.filter(function (v) { return v !== null; }).length; }

  var SCENARIOS = {
    lost: {
      label: "Lost update: two withdrawals",
      desc: "Alice's balance is 100. T1 withdraws 30 and T2 withdraws 50. By default each reads the balance, computes the new value in application code, and writes it back. Tick the box below to use one atomic UPDATE instead.",
      invariant: "Both withdrawals must count: final balance = 100 - 30 - 50 = 20.",
      keys: [["balance", 100]],
      fmt: function (v) { return String(v); },
      badOrder: [0, 1, 0, 1, 0, 1],
      hasFix: true,
      programs: function (atomic) {
        function prog(n) {
          return [
            read(["balance"], "b", "SELECT balance FROM accounts WHERE name = 'alice'"),
            atomic
              ? write("balance", "UPDATE accounts SET balance = balance - " + n + " WHERE name = 'alice'", function (l, cur) { return cur - n; })
              : write("balance", "UPDATE accounts SET balance = b - " + n + "   -- b was computed in the app", function (l) { return l.b - n; }),
            COMMIT
          ];
        }
        return [prog(30), prog(50)];
      },
      who: ["withdraw 30", "withdraw 50"],
      check: function (s, f) {
        var exp = 100 - (s.tx[0].status === "committed" ? 30 : 0) - (s.tx[1].status === "committed" ? 50 : 0);
        var bal = f.balance;
        if (bal === exp) return { ok: true, text: "Final balance " + bal + ", exactly what the committed withdrawals add up to (" + exp + ")." };
        return { ok: false, name: "Lost update", text: "Final balance " + bal + " but both withdrawals committed, so it should be " + exp + ". One withdrawal silently vanished." };
      }
    },
    skew: {
      label: "Read skew: audit during a transfer",
      desc: "Checking and savings hold 50 each (total 100). T1 moves 20 from checking to savings using atomic UPDATEs. T2 is an audit that reads both balances and adds them up.",
      invariant: "The audit must see a total of 100, because money is only moved, never created.",
      keys: [["checking", 50], ["savings", 50]],
      fmt: function (v) { return String(v); },
      badOrder: [1, 0, 0, 0, 1, 1],
      programs: function () {
        return [
          [
            write("checking", "UPDATE accounts SET balance = balance - 20 WHERE name = 'checking'", function (l, cur) { return cur - 20; }),
            write("savings", "UPDATE accounts SET balance = balance + 20 WHERE name = 'savings'", function (l, cur) { return cur + 20; }),
            COMMIT
          ],
          [
            read(["checking"], "c", "SELECT balance FROM accounts WHERE name = 'checking'"),
            read(["savings"], "s", "SELECT balance FROM accounts WHERE name = 'savings'"),
            COMMIT
          ]
        ];
      },
      who: ["transfer 20", "audit"],
      check: function (s) {
        var l = s.tx[1].locals, total = l.c + l.s;
        if (total === 100) return { ok: true, text: "The audit saw checking " + l.c + " + savings " + l.s + " = 100." };
        return { ok: false, name: "Read skew", text: "The audit saw checking " + l.c + " + savings " + l.s + " = " + total + ". It read half of the transfer's effect." };
      }
    },
    doctors: {
      label: "Write skew: doctors on call",
      desc: "Alice and Bob are both on call. Each may go off call only if at least one other doctor stays on. T1 is Alice going off, T2 is Bob going off. Each checks the count first, then updates only their own row.",
      invariant: "At least one doctor must stay on call.",
      keys: [["alice", 1], ["bob", 1]],
      fmt: function (v) { return v === 1 ? "on call" : "off"; },
      badOrder: [0, 1, 0, 1, 0, 1],
      programs: function () {
        function prog(name) {
          return [
            read(["alice", "bob"], "n", "SELECT count(*) FROM doctors WHERE on_call", count1),
            write(name, "IF n >= 2: UPDATE doctors SET on_call = false WHERE name = '" + name + "'",
              function () { return 0; }, function (l) { return l.n >= 2; }),
            COMMIT
          ];
        }
        return [prog("alice"), prog("bob")];
      },
      who: ["Alice goes off", "Bob goes off"],
      check: function (s, f) {
        var on = (f.alice === 1 ? 1 : 0) + (f.bob === 1 ? 1 : 0);
        if (on >= 1) return { ok: true, text: on + " doctor(s) still on call." };
        return { ok: false, name: "Write skew", text: "0 doctors on call. Each transaction was fine on its own snapshot, yet together they broke the rule." };
      }
    },
    phantom: {
      label: "Phantom: meeting-room booking",
      desc: "Room A is free at 10:00 (no booking rows exist). T1 and T2 each check that no booking exists, and if none does, insert their own. There is no unique constraint on (room, slot).",
      invariant: "At most one booking for room A at 10:00.",
      keys: [["booking by T1", null], ["booking by T2", null]],
      fmt: function (v) { return v === null ? "(no row)" : "booked"; },
      badOrder: [0, 1, 0, 1, 0, 1],
      programs: function () {
        function prog(key) {
          return [
            read(["booking by T1", "booking by T2"], "n", "SELECT count(*) FROM bookings WHERE room = 'A' AND slot = 10", countRows),
            write(key, "IF n = 0: INSERT INTO bookings (room, slot, who) VALUES ('A', 10, ...)",
              function () { return 1; }, function (l) { return l.n === 0; }),
            COMMIT
          ];
        }
        return [prog("booking by T1"), prog("booking by T2")];
      },
      who: ["book 10:00", "book 10:00"],
      check: function (s, f) {
        var n = (f["booking by T1"] !== null ? 1 : 0) + (f["booking by T2"] !== null ? 1 : 0);
        if (n <= 1) return { ok: true, text: n + " booking for room A at 10:00." };
        return { ok: false, name: "Phantom", text: "2 bookings for the same room and slot. Each insert created a row that the other's earlier check could not see." };
      }
    }
  };

  var LEVELS = {
    rc: { label: "Read Committed", reads: "Each statement sees the latest committed data." },
    si: { label: "Snapshot Isolation (Repeatable Read in Postgres)", reads: "Every read sees the snapshot taken at the first statement." },
    ser: { label: "Serializable (SSI)", reads: "Snapshot reads, plus tracking of read/write dependencies." }
  };

  var cfg = { scen: "lost", level: "rc", atomic: false };
  var progs, st, timer = null;

  /* ---------------- engine (pure, on plain-data state) ---------------- */
  function clone(o) { return JSON.parse(JSON.stringify(o)); }

  function fresh() {
    var s = { store: {}, seq: 0, locks: {}, log: [], blocks: 0,
      tx: [mkTx(0), mkTx(1)] };
    SCENARIOS[cfg.scen].keys.forEach(function (kv) {
      s.store[kv[0]] = [{ val: kv[1], by: "initial", cts: 0 }];
    });
    return s;
  }
  function mkTx(i) {
    return { name: "T" + (i + 1), pc: 0, status: "active", snap: null, writes: {}, reads: {},
      locals: {}, waiting: null, reason: "", last: "" };
  }

  function latest(s, key) { var v = s.store[key]; return v[v.length - 1]; }

  function visible(s, tx, key) {
    if (Object.prototype.hasOwnProperty.call(tx.writes, key)) return { val: tx.writes[key], by: "own write" };
    var vs = s.store[key], i;
    if (cfg.level === "rc" || tx.snap === null) return vs[vs.length - 1];
    for (i = vs.length - 1; i >= 0; i--) if (vs[i].cts <= tx.snap) return vs[i];
    return vs[0];
  }

  function fmtVal(key, v) { return SCENARIOS[cfg.scen].fmt(v); }

  function note(s, text) { s.log.push(text); }

  function releaseLocks(s, tx) {
    var i = s.tx.indexOf(tx);
    Object.keys(s.locks).forEach(function (k) { if (s.locks[k] === i) delete s.locks[k]; });
    s.tx.forEach(function (other, j) {
      if (j !== i && other.status === "active" && other.waiting && s.locks[other.waiting] === undefined) {
        var op = progs[j][other.pc];
        other.waiting = null;
        note(s, other.name + " is unblocked: " + tx.name + " released the lock on " + op.key + ".");
        doWrite(s, j, op);
      }
    });
  }

  function abort(s, i, msg) {
    var tx = s.tx[i];
    tx.status = "aborted";
    tx.reason = msg;
    tx.writes = {};
    tx.waiting = null;
    note(s, tx.name + " ABORTED: " + msg);
    releaseLocks(s, tx);
  }

  function doWrite(s, i, op) {
    var tx = s.tx[i];
    s.locks[op.key] = i;
    if (cfg.level !== "rc" && latest(s, op.key).cts > tx.snap) {
      abort(s, i, "could not serialize access due to concurrent update (first updater wins)");
      return;
    }
    var own = Object.prototype.hasOwnProperty.call(tx.writes, op.key);
    var cur = own ? tx.writes[op.key] : latest(s, op.key).val;
    var val = op.calc(tx.locals, cur);
    var before = fmtVal(op.key, cur);
    tx.writes[op.key] = val;
    tx.pc++;
    tx.last = "wrote " + op.key + " = " + fmtVal(op.key, val) + " (uncommitted)";
    note(s, tx.name + ": " + op.sql + "  (" + op.key + ": " + before + " -> " + fmtVal(op.key, val) + ", uncommitted)");
  }

  function doCommit(s, i) {
    var tx = s.tx[i], k, other, j;
    if (cfg.level === "ser") {
      for (j = 0; j < 2; j++) {
        if (j === i) continue;
        other = s.tx[j];
        if (other.status !== "committed" || other.cts <= tx.snap) continue;
        var meToOther = Object.keys(tx.reads).some(function (key) { return Object.prototype.hasOwnProperty.call(other.writeKeys, key); });
        var otherToMe = Object.keys(other.reads).some(function (key) { return Object.prototype.hasOwnProperty.call(tx.writes, key); });
        if (meToOther && otherToMe) {
          abort(s, i, "could not serialize access due to read/write dependencies among transactions");
          return;
        }
      }
    }
    var keys = Object.keys(tx.writes);
    if (keys.length) {
      s.seq++;
      keys.forEach(function (key) { s.store[key].push({ val: tx.writes[key], by: tx.name, cts: s.seq }); });
      tx.cts = s.seq;
    } else {
      tx.cts = s.seq;
    }
    tx.writeKeys = {};
    keys.forEach(function (key) { tx.writeKeys[key] = true; });
    tx.status = "committed";
    tx.pc++;
    tx.last = "committed";
    note(s, tx.name + ": COMMIT" + (keys.length ? " (" + keys.length + " new version" + (keys.length > 1 ? "s" : "") + ")" : " (nothing written)"));
    releaseLocks(s, tx);
  }

  /* returns true if the transaction made progress */
  function canStep(s, i) { var tx = s.tx[i]; return tx.status === "active" && !tx.waiting; }

  function step(s, i) {
    var tx = s.tx[i];
    if (!canStep(s, i)) return false;
    var op = progs[i][tx.pc];
    if (tx.snap === null && cfg.level !== "rc") tx.snap = s.seq;
    if (op.t === "read") {
      var seen = [];
      var vals = op.keys.map(function (k) {
        var v = visible(s, tx, k);
        tx.reads[k] = true;
        seen.push(k + " = " + fmtVal(k, v.val) + " [" + v.by + "]");
        return v.val;
      });
      var r = op.agg(vals);
      tx.locals[op.into] = r;
      tx.pc++;
      tx.last = "read " + op.into + " = " + r;
      note(s, tx.name + ": " + op.sql + "  -> " + op.into + " = " + r + "   sees " + seen.join(", "));
    } else if (op.t === "write") {
      if (op.when && !op.when(tx.locals)) {
        tx.pc++;
        tx.last = "condition false: no write";
        note(s, tx.name + ": condition is false, so it skips the write.");
      } else if (s.locks[op.key] !== undefined && s.locks[op.key] !== i) {
        tx.waiting = op.key;   /* a key name, so the state stays plain data */
        s.blocks++;
        tx.last = "waiting for the row lock on " + op.key;
        note(s, tx.name + ": " + op.sql + "  -> BLOCKED, " + s.tx[s.locks[op.key]].name + " holds the lock on " + op.key + ".");
      } else {
        doWrite(s, i, op);
      }
    } else {
      doCommit(s, i);
    }
    return true;
  }

  function done(s) { return s.tx.every(function (t) { return t.status !== "active"; }); }

  function finalState(s) {
    var f = {};
    Object.keys(s.store).forEach(function (k) { f[k] = latest(s, k).val; });
    return f;
  }

  function verdict(s) {
    var v = SCENARIOS[cfg.scen].check(s, finalState(s));
    var aborted = s.tx.filter(function (t) { return t.status === "aborted"; });
    v.aborted = aborted.map(function (t) { return t.name; });
    return v;
  }

  /* exhaustive search over every order of steps */
  function enumerate() {
    var out = { total: 0, bad: 0, aborts: 0 };
    (function go(s) {
      var opts = [0, 1].filter(function (i) { return canStep(s, i); });
      if (!opts.length) {
        out.total++;
        var v = verdict(s);
        if (!v.ok) out.bad++;
        else if (v.aborted.length) out.aborts++;
        return;
      }
      opts.forEach(function (i) { var n = clone(s); step(n, i); go(n); });
    })(fresh());
    return out;
  }

  /* ---------------- DOM ---------------- */
  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }
  function btn(label, cls) { var b = el("button", "btn " + (cls || ""), label); b.type = "button"; return b; }
  function field(labelText, control, id) {
    var wrap = el("div", "is-field");
    var lab = el("label", null, labelText);
    control.id = id;
    lab.setAttribute("for", id);
    wrap.appendChild(lab);
    wrap.appendChild(control);
    return wrap;
  }

  var head = el("div", "widget-head");
  head.appendChild(el("span", "widget-tag", "Explore"));
  head.appendChild(el("h4", "widget-title", "Isolation anomaly simulator"));
  root.appendChild(head);
  root.appendChild(el("p", "widget-help", "You are the scheduler. Pick a scenario and an isolation level, then choose which transaction runs its next step. Can you make the invariant break? Which levels stop you?"));

  var selScen = el("select");
  Object.keys(SCENARIOS).forEach(function (k) {
    var o = el("option", null, SCENARIOS[k].label); o.value = k; selScen.appendChild(o);
  });
  var selLevel = el("select");
  Object.keys(LEVELS).forEach(function (k) {
    var o = el("option", null, LEVELS[k].label); o.value = k; selLevel.appendChild(o);
  });
  var controls = el("div", "is-controls");
  controls.appendChild(field("Scenario", selScen, "is-scen"));
  controls.appendChild(field("Isolation level", selLevel, "is-level"));
  root.appendChild(controls);

  var fixRow = el("div", "widget-row is-fix");
  var fixLabel = el("label", "is-check");
  var fixBox = el("input"); fixBox.type = "checkbox";
  fixLabel.appendChild(fixBox);
  fixLabel.appendChild(document.createTextNode(" use one atomic UPDATE (balance = balance - n) instead of read, compute, write"));
  fixRow.appendChild(fixLabel);
  root.appendChild(fixRow);

  var descEl = el("p", "is-desc");
  var invEl = el("p", "is-inv");
  var readsEl = el("p", "widget-help");
  root.appendChild(descEl);
  root.appendChild(invEl);
  root.appendChild(readsEl);

  var board = el("div", "is-board");
  var cards = [0, 1].map(function (i) {
    var c = el("div", "is-tx is-t" + (i + 1));
    var title = el("div", "is-name");
    var snap = el("div", "is-snap");
    var ol = el("ol", "is-ops");
    var locals = el("div", "is-locals");
    var go = btn("Step T" + (i + 1), "primary");
    c.appendChild(title); c.appendChild(snap); c.appendChild(ol); c.appendChild(locals); c.appendChild(go);
    return { box: c, title: title, snap: snap, ol: ol, locals: locals, go: go };
  });
  board.appendChild(cards[0].box);
  board.appendChild(cards[1].box);
  root.appendChild(board);

  var dataHead = el("p", "is-datahead", "The data: committed versions and what each transaction sees now");
  var dataEl = el("div", "is-data");
  root.appendChild(dataHead);
  root.appendChild(dataEl);

  var presets = el("div", "widget-row");
  presets.appendChild(el("span", "widget-help", "Presets:"));
  var pBad = btn("Run the bad interleaving", "small");
  var pSerial = btn("Run T1 then T2", "small");
  var pReset = btn("Reset", "small");
  [pBad, pSerial, pReset].forEach(function (b) { presets.appendChild(b); });
  root.appendChild(presets);

  var status = el("div", "widget-out is-status");
  status.setAttribute("aria-live", "polite");
  root.appendChild(status);

  var logHead = el("p", "widget-help", "What happened, in order:");
  var logEl = el("ol", "is-log");
  root.appendChild(logHead);
  root.appendChild(logEl);

  var stats = el("div", "widget-out is-stats");
  root.appendChild(stats);

  var help = el("details", "is-modelhelp");
  help.appendChild(el("summary", null, "How faithful is this model? (simplifications)"));
  var hl = el("ul");
  [
    "Each key keeps a list of committed versions; every commit adds one version per key it wrote. Dirty reads never appear, so Read Uncommitted is not offered.",
    "Read Committed: every read sees the latest committed data. A write takes a row lock held until the transaction ends; a second writer waits, then proceeds. If the application computed its value earlier from a stale read, that stale value is written, so the lost update still happens.",
    "Snapshot isolation: the snapshot is taken at the transaction's first statement and all reads use it. A write to a row that another transaction committed after the snapshot aborts the writer (first updater wins, as in Postgres: a second writer waits for the first to finish, then aborts if the first committed; other products may detect the conflict at commit instead). Reads are not tracked, so write skew and phantoms get through.",
    "Serializable (SSI-like): snapshot isolation, plus a record of what each transaction read and wrote. At commit, if the committer and an already-committed concurrent transaction each read something the other wrote, the committer is aborted. Real SSI tracks dependency chains among many transactions, uses coarser predicate tracking, and can abort earlier or on false positives.",
    "Only two transactions, no deadlocks, no unique constraints and no SELECT ... FOR UPDATE, so you can see what the bare levels do. MySQL InnoDB's Repeatable Read behaves differently from the snapshot model here, so do not read this as a model of every product.",
    "The count at the bottom tries every order of steps by exhaustive search with the same engine. An aborted transaction would normally be retried by the application; here it simply stays aborted."
  ].forEach(function (t) { hl.appendChild(el("li", null, t)); });
  help.appendChild(hl);
  root.appendChild(help);

  /* ---------------- control ---------------- */
  var msg = "";

  function setup(note0) {
    stop();
    progs = SCENARIOS[cfg.scen].programs(cfg.atomic);
    st = fresh();
    msg = note0 || "Choose a transaction to run its next step.";
    render();
  }

  function stop() { if (timer) { clearTimeout(timer); timer = null; } }

  function doStep(i) {
    if (!st) return;
    var tx = st.tx[i];
    if (tx.status !== "active") { msg = tx.name + " has already " + tx.status + "."; render(); return; }
    if (tx.waiting) { msg = tx.name + " is waiting for a row lock. Run the other transaction until it commits or aborts."; render(); return; }
    var before = st.log.length;
    step(st, i);
    msg = st.log.slice(before).join(" ");
    render();
  }

  function pick(order, k) {
    /* choose the k-th preferred transaction, falling back to the other if it cannot move */
    var want = order[k % order.length];
    if (canStep(st, want)) return want;
    return canStep(st, 1 - want) ? 1 - want : -1;
  }

  function runOrder(order, animate) {
    setup();
    var k = 0, guard = 0;
    function one() {
      var i = pick(order, k++);
      if (i < 0 || guard++ > 60) { finish(); return false; }
      var before = st.log.length;
      step(st, i);
      msg = st.log.slice(before).join(" ");
      return true;
    }
    function finish() { stop(); render(); }
    var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (!animate || reduce) {
      while (!done(st) && one()) { /* run to the end */ }
      finish();
      return;
    }
    (function tick() {
      render();
      if (done(st)) { stop(); return; }
      if (!one()) { return; }
      timer = setTimeout(tick, 650);
    })();
  }

  cards.forEach(function (c, i) { c.go.addEventListener("click", function () { stop(); doStep(i); }); });
  selScen.addEventListener("change", function () { cfg.scen = selScen.value; setup(); });
  selLevel.addEventListener("change", function () { cfg.level = selLevel.value; setup(); });
  fixBox.addEventListener("change", function () { cfg.atomic = fixBox.checked; setup(); });
  pBad.addEventListener("click", function () { runOrder(SCENARIOS[cfg.scen].badOrder, true); });
  pSerial.addEventListener("click", function () { runOrder([0, 0, 0, 0, 1, 1, 1, 1], false); });
  pReset.addEventListener("click", function () { setup(); });

  /* ---------------- render ---------------- */
  function opStatus(tx, k) {
    if (k < tx.pc) return "done";
    if (tx.status === "aborted" && k === tx.pc) return "failed";
    if (tx.status === "active" && k === tx.pc) return tx.waiting ? "waiting" : "next";
    return "todo";
  }

  function render() {
    var sc = SCENARIOS[cfg.scen];
    descEl.textContent = sc.desc;
    invEl.textContent = "Invariant: " + sc.invariant;
    readsEl.textContent = "At " + LEVELS[cfg.level].label.split(" (")[0] + ": " + LEVELS[cfg.level].reads;
    fixRow.style.display = sc.hasFix ? "" : "none";

    cards.forEach(function (c, i) {
      var tx = st.tx[i];
      c.title.textContent = tx.name + ": " + sc.who[i];
      c.box.classList.toggle("is-blocked", !!tx.waiting);
      c.box.classList.toggle("is-aborted", tx.status === "aborted");
      c.box.classList.toggle("is-done", tx.status === "committed");
      if (cfg.level === "rc") c.snap.textContent = tx.pc === 0 && tx.status === "active" ? "not started" : "no snapshot: every statement reads fresh";
      else c.snap.textContent = tx.snap === null ? "not started" : "snapshot: commits up to #" + tx.snap;
      c.ol.textContent = "";
      progs[i].forEach(function (op, k) {
        var li = el("li", "is-op is-" + opStatus(tx, k), op.sql);
        c.ol.appendChild(li);
      });
      var parts = [];
      Object.keys(tx.locals).forEach(function (n) { parts.push(n + " = " + tx.locals[n]); });
      c.locals.textContent = "";
      c.locals.appendChild(el("span", "is-locals-label", "app variables: "));
      c.locals.appendChild(el("strong", null, parts.length ? parts.join(", ") : "none yet"));
      var state = tx.status === "active" ? (tx.waiting ? "waiting for lock" : "active") : tx.status;
      if (tx.status === "aborted") c.locals.appendChild(el("div", "is-reason", tx.reason));
      else c.locals.appendChild(el("div", "is-state", "state: " + state));
      var can = canStep(st, i);
      c.go.textContent = tx.status === "committed" ? tx.name + " committed" : tx.status === "aborted" ? tx.name + " aborted" : tx.waiting ? tx.name + " is waiting" : "Step " + tx.name;
      c.go.setAttribute("aria-disabled", can ? "false" : "true");
    });

    dataEl.textContent = "";
    sc.keys.forEach(function (kv) {
      var key = kv[0];
      var row = el("div", "is-row");
      row.appendChild(el("div", "is-key", key));
      var vers = el("div", "is-vers");
      st.store[key].forEach(function (v) {
        vers.appendChild(el("span", "is-ver", sc.fmt(v.val) + " (" + v.by + ")"));
      });
      st.tx.forEach(function (tx) {
        if (Object.prototype.hasOwnProperty.call(tx.writes, key)) {
          vers.appendChild(el("span", "is-ver is-unc is-u" + tx.name.slice(1), sc.fmt(tx.writes[key]) + " (" + tx.name + ", uncommitted)"));
        }
      });
      row.appendChild(vers);
      var views = el("div", "is-views");
      st.tx.forEach(function (tx, i) {
        var seen = tx.status === "active" || tx.status === "committed" ? visible(st, tx, key) : null;
        var t = el("span", "is-view is-v" + (i + 1), tx.name + " sees " + (seen ? sc.fmt(seen.val) : "n/a"));
        views.appendChild(t);
      });
      if (st.locks[key] !== undefined) views.appendChild(el("span", "is-lock", "row locked by T" + (st.locks[key] + 1)));
      row.appendChild(views);
      dataEl.appendChild(row);
    });

    var fin = done(st), out = msg;
    status.className = "widget-out is-status";
    if (fin) {
      var v = verdict(st);
      var f = finalState(st);
      var finalStr = sc.keys.map(function (kv) { return kv[0] + " = " + sc.fmt(f[kv[0]]); }).join(", ");
      var text;
      if (v.ok) {
        text = "No anomaly. " + v.text;
        if (v.aborted.length) text += " " + v.aborted.join(" and ") + " was aborted instead; a real application would retry it.";
        status.classList.add("is-good");
      } else {
        text = "ANOMALY: " + v.name + ". " + v.text;
        status.classList.add("is-bad");
      }
      out = (out ? out + "\n" : "") + text + "\nFinal committed data: " + finalStr + ". Invariant: " + sc.invariant;
    }
    status.textContent = out;
    status.style.whiteSpace = "pre-line";

    logEl.textContent = "";
    st.log.forEach(function (line) { logEl.appendChild(el("li", null, line)); });
    logHead.style.display = st.log.length ? "" : "none";

    var e = enumerate();
    stats.textContent = "";
    var lv = LEVELS[cfg.level].label.split(" (")[0];
    stats.appendChild(el("p", null, "At " + lv + " this scenario has " + e.total + " possible orders of steps. " +
      e.bad + " end with the invariant broken, " + e.aborts + " end with one transaction aborted (safe, but it must retry), and " + (e.total - e.bad - e.aborts) + " finish cleanly."));
    stats.appendChild(el("p", "widget-help", "Computed by trying every order of steps with the same engine. Switch the level and watch the first number change."));
  }

  selScen.value = cfg.scen; selLevel.value = cfg.level;
  setup();
})();
