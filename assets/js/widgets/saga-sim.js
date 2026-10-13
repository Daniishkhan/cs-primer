/* Saga simulator (architecture chapter 15).

   An orchestrated order saga with four steps, each a local transaction in a different
   service, and a compensation for every step except the last:
     1 reserve stock -> 2 charge payment -> 3 book courier -> 4 confirm order
     compensations: release stock, refund payment, cancel courier (confirm has none).
   Every orchestrator action is split into two micro-steps, because that is where the
   trouble lives:
     send   the command reaches the service and the service applies its local transaction;
     record the orchestrator writes the outcome to its saga log and moves on.
   A crash between the two leaves an effect applied but unrecorded: the "unknown outcome"
   window. You can
     - choose a step at which the service fails (a business failure, so it always fails);
     - crash the orchestrator at any moment, then restart it;
     - re-deliver the last command (a duplicate message);
     - switch idempotency off (services re-apply a repeated command) or persistence off
       (the saga log lives in memory and is lost in a crash).
   Restart rebuilds the orchestrator's position by replaying its saga log; with
   persistence off the log is empty, so it starts the saga again from step 1.
   Fully deterministic: no timers, no randomness.

   Simplifications: one saga (order 42); services never crash; a failing service fails
   every time (no retry can fix it); each service's effect is a counter ("net" units),
   so a duplicated charge shows up as net 2. */
(function () {
  "use strict";
  var root = document.getElementById("saga-sim");
  if (!root) return;

  var STEPS = [
    { n: 1, svc: "stock", fwd: "Reserve stock", comp: "Release stock", cmd: "ReserveStock", ccmd: "ReleaseStock" },
    { n: 2, svc: "payment", fwd: "Charge payment", comp: "Refund payment", cmd: "ChargeCard", ccmd: "RefundCard" },
    { n: 3, svc: "courier", fwd: "Book courier", comp: "Cancel booking", cmd: "BookCourier", ccmd: "CancelCourier" },
    { n: 4, svc: "order", fwd: "Confirm order", comp: "none (last step)", cmd: "ConfirmOrder", ccmd: null }
  ];
  var PRICE = 40;
  var PRESETS = [
    { id: "p1", label: "Courier fails (safe setup)", fail: 3, idem: true, persist: true,
      hint: "Click Next micro-step repeatedly. Stock and payment succeed, booking the courier fails, and the compensations run in reverse order." },
    { id: "p2", label: "Crash in the unknown-outcome window, no idempotency", fail: 0, idem: false, persist: true,
      hint: "Step until \"Charge payment\" has been sent but not yet recorded, press Crash, then Restart. The log does not know the card was charged, so the charge is sent again." },
    { id: "p3", label: "Crash with no persistence", fail: 0, idem: true, persist: false,
      hint: "Step past step 2, press Crash, then Restart. The saga log was only in memory, so the orchestrator forgets everything. Idempotency happens to save you here; now also switch idempotency off and repeat." }
  ];

  var S;
  function fresh(opts) {
    return {
      fail: opts.fail, idem: opts.idem, persist: opts.persist,
      net: { stock: 0, payment: 0, courier: 0, order: 0 }, status: "PENDING",
      seen: {}, calls: 0,
      alive: true, m: { phase: "fwd", i: 1, c: 0, pending: null },
      log: [], trace: [], last: null, stepsRun: 0, hint: ""
    };
  }
  S = fresh({ fail: 3, idem: true, persist: true });
  S.hint = PRESETS[0].hint;

  function say(text, bad) { S.trace.push({ text: text, bad: !!bad }); if (S.trace.length > 60) S.trace.shift(); }

  /* ---------- the services ---------- */
  function deliver(kind, n, dup) {
    var st = STEPS[n - 1], key = kind + n, cmd = kind === "fwd" ? st.cmd : st.ccmd;
    S.last = { kind: kind, n: n };
    if (kind === "fwd" && S.fail === n) {
      say((dup ? "Duplicate of " : "") + cmd + " reached " + st.svc + ", which rejects it (injected failure).", true);
      return "fail";
    }
    if (S.idem && S.seen[key]) {
      say((dup ? "Duplicate " : "Repeated ") + cmd + " reached " + st.svc + ": it has already done this, so it replies OK without doing it again.");
      return "ok";
    }
    var again = !!S.seen[key];
    S.seen[key] = true;
    if (kind === "fwd") { S.net[st.svc]++; if (st.svc === "order") S.status = "CONFIRMED"; }
    else S.net[st.svc]--;
    say(cmd + (dup ? " (duplicate)" : "") + " applied by " + st.svc + "." + (again ? " It was already applied before, and the service applied it AGAIN." : ""), again);
    return "ok";
  }

  /* ---------- the orchestrator ---------- */
  function record(e) { S.log.push(e); }
  function logText(e) {
    if (e.t === "done") return "step " + e.n + " done: " + STEPS[e.n - 1].fwd;
    if (e.t === "failed") return "step " + e.n + " FAILED: " + STEPS[e.n - 1].fwd;
    if (e.t === "compensated") return "step " + e.n + " compensated: " + STEPS[e.n - 1].comp;
    return "order cancelled";
  }
  function finished() { return !!S.m && S.m.phase === "done" && !S.m.pending; }

  function step() {
    if (!S.alive || finished()) return;
    var m = S.m, p = m.pending;
    S.stepsRun++;
    if (p) {                                  /* record */
      m.pending = null;
      if (p.kind === "fwd" && p.res === "ok") {
        record({ t: "done", n: p.n });
        say("Orchestrator records: " + logText({ t: "done", n: p.n }) + ".");
        if (p.n === 4) m.phase = "done"; else m.i = p.n + 1;
      } else if (p.kind === "fwd") {
        record({ t: "failed", n: p.n });
        m.phase = "comp"; m.c = p.n - 1;
        say("Orchestrator records: step " + p.n + " failed. Switching to compensation, newest step first.", false);
      } else if (p.kind === "comp") {
        record({ t: "compensated", n: p.n });
        m.c = p.n - 1;
        say("Orchestrator records: step " + p.n + " compensated.");
      } else {
        record({ t: "cancelled" });
        m.phase = "done";
        say("Orchestrator records: order cancelled. The saga has ended.");
      }
      return;
    }
    /* send */
    if (m.phase === "fwd") {
      var res = deliver("fwd", m.i, false);
      m.pending = { kind: "fwd", n: m.i, res: res };
    } else if (m.phase === "comp") {
      if (m.c >= 1) {
        deliver("comp", m.c, false);
        m.pending = { kind: "comp", n: m.c };
      } else {
        S.status = "CANCELLED";
        say("CancelOrder applied: order status becomes CANCELLED (it was PENDING, the semantic lock).");
        m.pending = { kind: "cancel" };
      }
    }
  }

  function crash() {
    if (!S.alive || finished()) return;
    var window_ = !!S.m.pending;
    S.alive = false; S.m = null;
    if (!S.persist) { S.log = []; }
    say("CRASH. The orchestrator process dies and loses its memory" + (S.persist ? ", but its saga log is on disk." : ", and its saga log was only in memory, so that is gone too.") +
      (window_ ? " It died between sending a command and recording the reply: the outcome of that step is unknown." : ""), true);
  }

  function rebuild(log) {
    var D = {}, C = {}, failed = 0, cancelled = false;
    log.forEach(function (e) {
      if (e.t === "done") D[e.n] = 1;
      if (e.t === "failed") failed = e.n;
      if (e.t === "compensated") C[e.n] = 1;
      if (e.t === "cancelled") cancelled = true;
    });
    var m = { phase: "fwd", i: 1, c: 0, pending: null };
    if (cancelled || D[4]) { m.phase = "done"; return m; }
    if (failed) {
      m.phase = "comp";
      for (var k = 3; k >= 1; k--) if (D[k] && !C[k]) { m.c = k; break; }
      return m;
    }
    while (D[m.i]) m.i++;
    return m;
  }
  function restart() {
    if (S.alive) return;
    S.alive = true; S.m = rebuild(S.log);
    if (!S.log.length) say("Restarted. The log is empty, so the orchestrator has no idea order 42 was ever started. It begins the saga again from step 1.", !S.persist);
    else say("Restarted. It replays " + S.log.length + " log entr" + (S.log.length === 1 ? "y" : "ies") + " and resumes " +
      (S.m.phase === "comp" ? (S.m.c ? "compensating from step " + S.m.c : "by cancelling the order") : S.m.phase === "done" ? "(nothing left to do)" : "at step " + S.m.i) + ".");
  }
  function duplicate() {
    if (!S.last) return;
    deliver(S.last.kind, S.last.n, true);
  }
  function runToEnd() {
    var guard = 0;
    while (S.alive && !finished() && guard++ < 40) step();
  }

  /* ---------- verdict ---------- */
  function problems() {
    var out = [], done = finished(), want = S.status === "CONFIRMED" ? 1 : 0;
    var names = { stock: "Stock", payment: "Payment", courier: "Courier" };
    ["stock", "payment", "courier"].forEach(function (k) {
      var v = S.net[k], over = v > 1, under = v < 0;
      if (over || under || (done && v !== want)) {
        var what;
        if (k === "payment") what = v > want ? "customer charged $" + (v * PRICE) + " instead of $" + (want * PRICE) : "refunded more than was charged (net $" + (v * PRICE) + ")";
        else if (k === "stock") what = v > want ? v + " units reserved for one order" + (want || !done ? "" : ", never released") : "released more than was reserved";
        else what = v > want ? v + " courier bookings for one order" + (want || !done ? "" : ", never cancelled") : "cancelled more than was booked";
        out.push(names[k] + ": " + what + ".");
      }
    });
    return out;
  }

  /* ---------- build DOM once ---------- */
  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function btn(label, cls, fn) { var b = el("button", "btn " + (cls || ""), label); b.type = "button"; b.addEventListener("click", fn); return b; }

  var head = el("div", "widget-head");
  head.appendChild(el("span", "widget-tag", "Simulator"));
  head.appendChild(el("span", "widget-title", "Order saga: failures, crashes and duplicates"));
  root.appendChild(head);
  root.appendChild(el("p", "widget-help", "Step the orchestrator one micro-step at a time (send, then record). Inject a failure, crash it, duplicate a message, or turn off idempotency or persistence, and watch the services at the bottom."));

  root.appendChild(el("p", "sg-label", "Quick scenarios"));
  var prow = el("div", "sg-btns");
  PRESETS.forEach(function (p) {
    prow.appendChild(btn(p.label, "", function () { S = fresh(p); S.hint = p.hint; render(); }));
  });
  root.appendChild(prow);
  var hint = el("p", "sg-hint"); root.appendChild(hint);

  root.appendChild(el("p", "sg-label", "Settings (take effect immediately)"));
  var frow = el("div", "sg-btns"); frow.setAttribute("role", "group"); frow.setAttribute("aria-label", "Step at which the service fails");
  var fbtns = [];
  [0, 1, 2, 3, 4].forEach(function (n) {
    var b = btn(n ? "Fail at step " + n : "No failure", "small", function () { S.fail = n; render(); });
    fbtns.push(b); frow.appendChild(b);
  });
  root.appendChild(frow);
  function check(label, get, set) {
    var l = el("label", "sg-check"), cb = document.createElement("input"); cb.type = "checkbox";
    cb.addEventListener("change", function () { set(cb.checked); render(); });
    l.appendChild(cb); l.appendChild(el("span", null, label)); root.appendChild(l);
    return { cb: cb, get: get };
  }
  var cbIdem = check("Idempotent services (a repeated command is recognised and ignored)", function () { return S.idem; }, function (v) { S.idem = v; });
  var cbPers = check("Persistent saga log (written to disk, so it survives a crash)", function () { return S.persist; }, function (v) { S.persist = v; });

  root.appendChild(el("p", "sg-label", "Run"));
  var crow = el("div", "sg-btns");
  var bNext = btn("Next micro-step", "primary small", function () { step(); render(); });
  var bRun = btn("Run to end", "small", function () { runToEnd(); render(); });
  var bCrash = btn("Crash orchestrator", "small", function () { crash(); render(); });
  var bRestart = btn("Restart orchestrator", "small", function () { restart(); render(); });
  var bDup = btn("Duplicate last message", "small", function () { duplicate(); render(); });
  var bReset = btn("Reset", "small", function () { S = fresh({ fail: S.fail, idem: S.idem, persist: S.persist }); render(); });
  [bNext, bRun, bCrash, bRestart, bDup, bReset].forEach(function (b) { crow.appendChild(b); });
  root.appendChild(crow);
  var next = el("p", "sg-next"); next.setAttribute("aria-live", "polite"); root.appendChild(next);

  var grid = el("div", "sg-grid");
  var pSteps = el("div", "sg-pane"); pSteps.appendChild(el("h5", null, "The saga"));
  var tbl = el("table", "sg-table");
  var thead = el("thead"), trh = el("tr");
  ["Step", "Forward", "Compensation"].forEach(function (h) { var th = el("th", null, h); th.scope = "col"; trh.appendChild(th); });
  thead.appendChild(trh); tbl.appendChild(thead);
  var tbody = el("tbody"); tbl.appendChild(tbody); pSteps.appendChild(tbl);
  var orchLine = el("p", "sg-note"); pSteps.appendChild(orchLine);
  grid.appendChild(pSteps);

  var pLog = el("div", "sg-pane log"); var logH = el("h5"); pLog.appendChild(logH);
  var logOl = el("ol", "sg-logl"); pLog.appendChild(logOl);
  grid.appendChild(pLog);
  root.appendChild(grid);

  root.appendChild(el("p", "sg-label", "State of each service"));
  var sgrid = el("div", "sg-svcs"), cards = {};
  [["stock", "Stock"], ["payment", "Payment"], ["courier", "Courier"], ["order", "Order"]].forEach(function (s) {
    var c = el("div", "sg-svc"); var t = el("div", "sg-svc-name", s[1]); var v = el("div", "sg-svc-val");
    c.appendChild(t); c.appendChild(v); sgrid.appendChild(c); cards[s[0]] = { box: c, val: v };
  });
  root.appendChild(sgrid);
  var verdict = el("div", "sg-verdict"); root.appendChild(verdict);

  root.appendChild(el("p", "sg-label", "What happened (newest first)"));
  var trace = el("ol", "sg-trace"); root.appendChild(trace);

  /* ---------- render ---------- */
  function fwdState(n) {
    var m = S.m, doneIn = S.log.some(function (e) { return e.t === "done" && e.n === n; });
    var failedIn = S.log.some(function (e) { return e.t === "failed" && e.n === n; });
    if (failedIn) return ["failed", "bad"];
    if (doneIn) return ["done", "ok"];
    if (m && m.pending && m.pending.kind === "fwd" && m.pending.n === n) return [m.pending.res === "ok" ? "applied, not recorded" : "rejected, not recorded", "wait"];
    if (S.alive && m && m.phase === "fwd" && m.i === n) return ["next", "next"];
    return ["", ""];
  }
  function compState(n) {
    if (!STEPS[n - 1].ccmd) return ["", ""];
    var m = S.m;
    if (S.log.some(function (e) { return e.t === "compensated" && e.n === n; })) return ["compensated", "ok"];
    if (m && m.pending && m.pending.kind === "comp" && m.pending.n === n) return ["applied, not recorded", "wait"];
    if (S.alive && m && m.phase === "comp" && m.c === n) return ["next", "next"];
    return ["", ""];
  }
  function chip(txt, cls) { return el("span", "sg-chip " + cls, txt || "—"); }

  function render() {
    hint.textContent = S.hint; hint.hidden = !S.hint;
    fbtns.forEach(function (b, i) { b.setAttribute("aria-pressed", String(S.fail === i)); });
    cbIdem.cb.checked = S.idem; cbPers.cb.checked = S.persist;
    var fin = finished();
    bNext.disabled = !S.alive || fin; bRun.disabled = !S.alive || fin;
    bCrash.disabled = !S.alive || fin; bRestart.disabled = S.alive;
    bDup.disabled = !S.last;

    var nextText;
    if (!S.alive) nextText = "The orchestrator is down. Nothing moves until you restart it.";
    else if (fin) nextText = "The saga has ended: " + (S.status === "CONFIRMED" ? "order confirmed" : "order cancelled") + ".";
    else {
      var m = S.m;
      if (m.pending) {
        var pp = m.pending;
        nextText = "Next: the orchestrator records the reply" + (pp.kind === "fwd" ? " to " + STEPS[pp.n - 1].cmd : pp.kind === "comp" ? " to " + STEPS[pp.n - 1].ccmd : " to CancelOrder") + ". Crashing now would leave this step's outcome unknown.";
      } else if (m.phase === "fwd") nextText = "Next: send " + STEPS[m.i - 1].cmd + " to the " + STEPS[m.i - 1].svc + " service.";
      else nextText = m.c ? "Next: send " + STEPS[m.c - 1].ccmd + " (compensating step " + m.c + ")." : "Next: send CancelOrder.";
    }
    next.textContent = nextText;

    tbody.textContent = "";
    STEPS.forEach(function (st) {
      var tr = el("tr"), f = fwdState(st.n), c = compState(st.n);
      var td0 = el("td"); td0.appendChild(el("strong", null, st.n + ". " + st.fwd)); tr.appendChild(td0);
      var td1 = el("td"); td1.appendChild(chip(f[0], f[1])); tr.appendChild(td1);
      var td2 = el("td"); td2.appendChild(el("div", "sg-comp-name", st.comp)); td2.appendChild(chip(c[0], c[1])); tr.appendChild(td2);
      tbody.appendChild(tr);
    });
    orchLine.textContent = !S.alive ? "Orchestrator: DOWN (its memory is gone)." :
      "Orchestrator: running, " + (S.m.phase === "fwd" ? "going forward, at step " + S.m.i : S.m.phase === "comp" ? "compensating" + (S.m.c ? ", at step " + S.m.c : ", cancelling the order") : "finished") + ".";

    logH.textContent = S.persist ? "Saga log (persisted to disk)" : "Saga log (in memory only: lost in a crash)";
    logOl.textContent = "";
    if (!S.log.length) logOl.appendChild(el("li", "sg-none", "empty"));
    S.log.forEach(function (e) { logOl.appendChild(el("li", e.t === "failed" ? "bad" : "", logText(e))); });

    var probs = problems();
    var vals = {
      stock: S.net.stock + " unit" + (S.net.stock === 1 ? "" : "s") + " reserved",
      payment: "$" + (S.net.payment * PRICE) + " charged",
      courier: S.net.courier + " booking" + (S.net.courier === 1 ? "" : "s"),
      order: S.status
    };
    ["stock", "payment", "courier", "order"].forEach(function (k) {
      cards[k].val.textContent = vals[k];
      var bad = k !== "order" && (S.net[k] > 1 || S.net[k] < 0 || (fin && S.net[k] !== (S.status === "CONFIRMED" ? 1 : 0)));
      cards[k].box.className = "sg-svc" + (bad ? " bad" : S.net[k] > 0 || (k === "order" && S.status !== "PENDING") ? " has" : "");
    });
    if (probs.length) {
      verdict.className = "sg-verdict bad";
      verdict.textContent = "";
      verdict.appendChild(el("strong", null, "Inconsistent: "));
      verdict.appendChild(document.createTextNode(probs.join(" ")));
    } else if (fin) {
      verdict.className = "sg-verdict good";
      verdict.textContent = "";
      verdict.appendChild(el("strong", null, "Consistent: "));
      verdict.appendChild(document.createTextNode(S.status === "CONFIRMED" ? "every service did its part and the order is confirmed." : "every effect has been compensated and the order is cancelled. Nothing was charged, reserved or booked."));
    } else {
      verdict.className = "sg-verdict";
      verdict.textContent = S.alive ? "In progress. Intermediate states are visible to everyone: the order is " + S.status + " (the semantic lock)." : "Waiting for the orchestrator to restart.";
    }

    trace.textContent = "";
    if (!S.trace.length) trace.appendChild(el("li", null, "Nothing yet. Press Next micro-step."));
    S.trace.slice().reverse().forEach(function (l) { trace.appendChild(el("li", l.bad ? "bad" : "", l.text)); });
  }
  render();
})();
