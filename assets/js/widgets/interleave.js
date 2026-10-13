/* Interleaving explorer (systems chapter 11).
   Two threads, A and B, each run `counter += 1` as three machine-like steps:
       LOAD counter -> reg      ADD reg, 1      STORE reg -> counter
   The reader decides which thread runs the next step. With "use a lock" on,
   each thread gets ACQUIRE / RELEASE around those steps, and a thread whose
   next step is ACQUIRE while the other holds the lock is blocked.
   The counts of possible interleavings (and how many lose an update) are
   computed by exhaustive search over the same step machine, not hard-coded. */
(function () {
  "use strict";
  var root = document.getElementById("interleave-widget");
  if (!root) return;

  var BODY = ["LOAD counter → reg", "ADD reg, 1", "STORE reg → counter"];
  var THREADS = ["A", "B"];

  var useLock = false;
  var st, log, msg;

  function program() {
    return useLock ? ["ACQUIRE lock"].concat(BODY, ["RELEASE lock"]) : BODY.slice();
  }

  /* ---- pure step machine (shared by the UI and the exhaustive counter) ---- */
  function fresh() { return { pc: [0, 0], reg: [null, null], counter: 0, holder: -1 }; }
  function copy(s) { return { pc: s.pc.slice(), reg: s.reg.slice(), counter: s.counter, holder: s.holder }; }
  function finished(s, t, prog) { return s.pc[t] >= prog.length; }
  function blocked(s, t, prog) {
    return useLock && !finished(s, t, prog) && prog[s.pc[t]] === "ACQUIRE lock" && s.holder !== -1 && s.holder !== t;
  }
  function runnable(s, t, prog) { return !finished(s, t, prog) && !blocked(s, t, prog); }
  function opOf(prog, s, t) {
    var name = prog[s.pc[t]];
    if (name === "ACQUIRE lock") return "acq";
    if (name === "RELEASE lock") return "rel";
    if (name.indexOf("LOAD") === 0) return "load";
    if (name.indexOf("ADD") === 0) return "add";
    return "store";
  }
  function apply(s, t, prog) {
    var op = opOf(prog, s, t);
    if (op === "acq") s.holder = t;
    else if (op === "rel") s.holder = -1;
    else if (op === "load") s.reg[t] = s.counter;
    else if (op === "add") s.reg[t] = s.reg[t] + 1;
    else s.counter = s.reg[t];
    s.pc[t]++;
  }

  /* depth-first search over every legal schedule */
  function enumerate() {
    var prog = program(), total = 0, lost = 0;
    (function go(s) {
      var any = false;
      for (var t = 0; t < 2; t++) {
        if (runnable(s, t, prog)) { any = true; var n = copy(s); apply(n, t, prog); go(n); }
      }
      if (!any) { total++; if (s.counter !== 2) lost++; }
    })(fresh());
    return { total: total, lost: lost };
  }

  /* ---- DOM ---- */
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

  var head = el("div", "widget-head");
  head.appendChild(el("span", "widget-tag", "Explore"));
  head.appendChild(el("h4", "widget-title", "The interleaving explorer"));
  root.appendChild(head);
  root.appendChild(el("p", "widget-help", "Both threads run counter += 1 on a shared counter that starts at 0. You are the scheduler: choose which thread takes the next step. Can you make an update disappear?"));

  var lockRow = el("div", "widget-row");
  var lockLabel = el("label", "il-check");
  var lockBox = el("input");
  lockBox.type = "checkbox";
  lockLabel.appendChild(lockBox);
  lockLabel.appendChild(document.createTextNode(" use a lock"));
  lockRow.appendChild(lockLabel);
  root.appendChild(lockRow);

  var board = el("div", "il-board");
  var cards = THREADS.map(function (name, t) {
    var c = el("div", "il-thread il-t" + name);
    c.appendChild(el("div", "il-name", "Thread " + name));
    var ol = el("ol", "il-steps");
    c.appendChild(ol);
    var reg = el("div", "il-reg");
    c.appendChild(reg);
    var go = btn("Step " + name, "primary");
    go.setAttribute("data-t", String(t));
    c.appendChild(go);
    return { box: c, ol: ol, reg: reg, go: go };
  });
  var mid = el("div", "il-shared");
  mid.appendChild(el("div", "il-name", "Shared memory"));
  var counterBox = el("div", "il-counter");
  var counterLabel = el("span", "il-counter-label", "counter");
  var counterVal = el("span", "il-counter-val", "0");
  counterBox.appendChild(counterLabel);
  counterBox.appendChild(counterVal);
  mid.appendChild(counterBox);
  var lockBoxEl = el("div", "il-lock");
  mid.appendChild(lockBoxEl);
  board.appendChild(cards[0].box);
  board.appendChild(mid);
  board.appendChild(cards[1].box);
  root.appendChild(board);

  var presets = el("div", "widget-row");
  presets.appendChild(el("span", "widget-help", "Presets:"));
  var pSerial = btn("A then B (serial)", "small");
  var pClassic = btn("classic lost update", "small");
  var pRandom = btn("random", "small");
  var pReset = btn("Reset", "small");
  [pSerial, pClassic, pRandom, pReset].forEach(function (b) { presets.appendChild(b); });
  root.appendChild(presets);

  var status = el("div", "widget-out il-status");
  status.setAttribute("aria-live", "polite");
  root.appendChild(status);

  var logHead = el("p", "widget-help il-loghead", "Order the steps ran in:");
  var logEl = el("ol", "il-log");
  root.appendChild(logHead);
  root.appendChild(logEl);

  var stats = el("div", "widget-out il-stats");
  root.appendChild(stats);

  /* ---- behaviour ---- */
  function reset(note) {
    st = fresh();
    log = [];
    msg = note || "Pick a thread to run its next step.";
    render();
  }

  function step(t, quiet) {
    var prog = program();
    if (finished(st, t, prog)) { msg = "Thread " + THREADS[t] + " has finished."; if (!quiet) render(); return false; }
    if (blocked(st, t, prog)) {
      msg = "Thread " + THREADS[t] + " is blocked: thread " + THREADS[1 - t] + " holds the lock. Run " + THREADS[1 - t] + " until it releases it.";
      if (!quiet) render();
      return false;
    }
    var name = prog[st.pc[t]];
    var before = { reg: st.reg[t], counter: st.counter };
    apply(st, t, prog);
    var detail = "";
    if (name.indexOf("LOAD") === 0) detail = " (reg = " + st.reg[t] + ")";
    else if (name.indexOf("ADD") === 0) detail = " (reg " + before.reg + " → " + st.reg[t] + ")";
    else if (name.indexOf("STORE") === 0) detail = " (counter " + before.counter + " → " + st.counter + ")";
    log.push(THREADS[t] + ": " + name + detail);
    msg = THREADS[t] + " ran " + name + detail + ".";
    if (!quiet) render();
    return true;
  }

  function runScript(prefs, random) {
    reset();
    var prog = program(), guard = 0, i = 0, skipped = [];
    while ((runnable(st, 0, prog) || runnable(st, 1, prog)) && guard++ < 100) {
      var t;
      if (random) {
        var opts = [0, 1].filter(function (x) { return runnable(st, x, prog); });
        t = opts[Math.floor(Math.random() * opts.length)];
      } else {
        t = prefs[i++ % prefs.length];
        if (!runnable(st, t, prog)) {
          if (blocked(st, t, prog) && skipped.indexOf(THREADS[t]) < 0) skipped.push(THREADS[t]);
          t = 1 - t;
        }
      }
      step(t, true);
    }
    msg = "";
    if (skipped.length) msg = "The lock blocked thread " + skipped.join(" and ") + " from jumping in early, so the steps could not interleave.";
    render();
  }

  function render() {
    var prog = program();
    var n = prog.length;
    cards.forEach(function (c, t) {
      c.ol.textContent = "";
      prog.forEach(function (name, k) {
        var li = el("li", null, name);
        if (k < st.pc[t]) li.className = "done";
        else if (k === st.pc[t]) li.className = "next";
        c.ol.appendChild(li);
      });
      c.reg.textContent = "";
      c.reg.appendChild(el("span", "il-reg-label", "register: "));
      c.reg.appendChild(el("strong", null, st.reg[t] === null ? "—" : String(st.reg[t])));
      var fin = finished(st, t, prog), blk = blocked(st, t, prog);
      c.go.textContent = fin ? "Thread " + THREADS[t] + " done" : blk ? "Step " + THREADS[t] + " (blocked by lock)" : "Step " + THREADS[t];
      c.go.setAttribute("aria-disabled", (fin || blk) ? "true" : "false");
      c.box.classList.toggle("is-blocked", blk);
      c.box.classList.toggle("is-done", fin);
    });
    counterVal.textContent = String(st.counter);
    lockBoxEl.textContent = "";
    if (useLock) {
      lockBoxEl.className = "il-lock " + (st.holder === -1 ? "free" : "held");
      lockBoxEl.textContent = st.holder === -1 ? "lock: free" : "lock: held by " + THREADS[st.holder];
    } else {
      lockBoxEl.className = "il-lock off";
      lockBoxEl.textContent = "no lock";
    }

    var allDone = finished(st, 0, prog) && finished(st, 1, prog);
    var out = msg;
    if (allDone) {
      var good = st.counter === 2;
      out += (out ? " " : "") + "Both threads finished. Counter = " + st.counter + " (expected 2). " +
        (good ? "No update was lost this time." : "One update was lost.");
    }
    status.textContent = out;
    status.classList.toggle("il-bad", allDone && st.counter !== 2);
    status.classList.toggle("il-good", allDone && st.counter === 2);

    logEl.textContent = "";
    log.forEach(function (line) { logEl.appendChild(el("li", null, line)); });
    logHead.style.display = log.length ? "" : "none";

    var e = enumerate();
    stats.textContent = "";
    stats.appendChild(el("p", null, useLock
      ? "With the lock there are " + e.total + " possible interleavings of these " + n + "-step threads, and " + e.lost + " of them lose an update."
      : "There are " + e.total + " possible interleavings of these two " + n + "-step threads, and " + e.lost + " of them lose an update. Only " + (e.total - e.lost) + " are safe."));
    stats.appendChild(el("p", "widget-help", useLock
      ? "Counting only schedules where a blocked thread is never chosen. The lock removes every unsafe order."
      : "Computed by trying every order, not a guess. In general, two threads of n steps have C(2n, n) orders."));
  }

  cards.forEach(function (c, t) {
    c.go.addEventListener("click", function () { step(t); });
  });
  lockBox.addEventListener("change", function () {
    useLock = lockBox.checked;
    reset(useLock ? "Lock on: each thread now acquires the lock first and releases it last." : "Lock off.");
  });
  function repeat(arr, times) { var out = []; for (var i = 0; i < times; i++) out = out.concat(arr); return out; }
  pSerial.addEventListener("click", function () {
    var n = program().length;
    runScript(repeat([0], n).concat(repeat([1], n)));
  });
  pClassic.addEventListener("click", function () { runScript(repeat([0, 1], program().length)); });
  pRandom.addEventListener("click", function () { runScript(null, true); });
  pReset.addEventListener("click", function () { reset(); });

  reset();
})();
