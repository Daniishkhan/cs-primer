/* Event loop simulator (systems chapter 16).
   A deterministic model of one loop iteration: WAIT (sleep until a socket is ready or the next
   timer is due), COLLECT (move ready sockets and due timers into the ready queue), DISPATCH
   (run the callbacks one at a time, each one advancing a simulated clock). Nothing is random;
   the same clicks always give the same result. The core is pure and can be tested in Node. */
(function () {
  "use strict";

  var NAMES = ["A", "B", "C", "D", "E"];
  var SOCK_COST = 2;      /* ms a normal socket handler takes */
  var TIMER_COST = 1;     /* ms a timer callback takes */
  var BLOCK_COST = 500;   /* ms a handler takes when it blocks */
  var MAX_TIMERS = 6;
  var MAX_PENDING = 9;

  /* ---------- core (no DOM) ---------- */
  function Loop() { this.reset(); }

  Loop.prototype.reset = function () {
    this.now = 0;
    this.phase = "wait";          /* the step that runs next: wait | collect | dispatch */
    this.last = "";               /* the step that ran last, for highlighting */
    this.pending = []; this.arrival = []; this.handled = [];
    for (var i = 0; i < NAMES.length; i++) { this.pending.push(0); this.arrival.push(null); this.handled.push(0); }
    this.timers = [];
    this.nextTimerId = 1;
    this.queue = [];
    this.running = null;
    this.block = false;
    this.lastLag = null; this.maxLag = 0; this.maxWait = 0; this.fired = 0;
    this.message = "Click a client to make data arrive, add a timer, then press Next tick.";
  };

  Loop.prototype.send = function (i) {
    if (this.pending[i] >= MAX_PENDING) return false;
    this.pending[i]++;
    if (this.arrival[i] === null) this.arrival[i] = this.now;
    return true;
  };

  Loop.prototype.addTimer = function (delay) {
    if (this.timers.length >= MAX_TIMERS) return false;
    var t = { id: this.nextTimerId++, due: this.now + delay, delay: delay };
    this.timers.push(t);
    this.timers.sort(function (a, b) { return a.due - b.due || a.id - b.id; });
    return true;
  };

  Loop.prototype.anyPending = function () {
    for (var i = 0; i < this.pending.length; i++) if (this.pending[i] > 0) return true;
    return false;
  };

  /* wait timeout in ms: 0 if a socket is already readable, the gap to the next deadline,
     or null for "forever" (nothing registered that could wake us) */
  Loop.prototype.timeout = function () {
    if (this.anyPending()) return 0;
    if (this.timers.length) return Math.max(0, this.timers[0].due - this.now);
    return null;
  };

  Loop.prototype.idle = function () {
    return this.phase === "wait" && this.timeout() === null;
  };

  /* Run one step. Returns true if a full iteration finished (dispatch drained the queue). */
  Loop.prototype.step = function () {
    var t, i;
    this.running = null;
    if (this.phase === "wait") {
      t = this.timeout();
      if (t === null) {
        this.message = "select(timeout=None): no socket has data and no timer is set, so the loop sleeps. Click a client or add a timer.";
        return false;
      }
      this.now += t;
      this.last = "wait";
      this.message = t === 0
        ? "WAIT: select(timeout=0) returned at once, because a socket already has data."
        : "WAIT: select(timeout=" + t + " ms) slept until the next deadline. The clock moved forward " + t + " ms.";
      this.phase = "collect";
      return false;
    }
    if (this.phase === "collect") {
      var names = [];
      for (i = 0; i < NAMES.length; i++) {
        if (this.pending[i] > 0) { this.queue.push({ kind: "io", i: i }); names.push("read " + NAMES[i]); }
      }
      while (this.timers.length && this.timers[0].due <= this.now) {
        var tm = this.timers.shift();
        this.queue.push({ kind: "timer", t: tm });
        names.push("timer T" + tm.id);
      }
      this.last = "collect";
      this.message = names.length
        ? "COLLECT: " + names.length + " callback" + (names.length > 1 ? "s" : "") + " ready (" + names.join(", ") + "). Sockets first, then due timers."
        : "COLLECT: nothing is ready.";
      this.phase = this.queue.length ? "dispatch" : "wait";
      return !this.queue.length;
    }
    /* dispatch one callback */
    var cb = this.queue.shift();
    this.last = "dispatch";
    this.running = cb;
    if (cb.kind === "io") {
      var waited = this.now - this.arrival[cb.i];
      if (waited > this.maxWait) this.maxWait = waited;
      var n = this.pending[cb.i];
      var cost = this.block ? BLOCK_COST : SOCK_COST;
      this.pending[cb.i] = 0; this.arrival[cb.i] = null; this.handled[cb.i] += n;
      this.now += cost;
      this.message = "DISPATCH: handler for client " + NAMES[cb.i] + " read " + n + " message" + (n > 1 ? "s" : "") +
        " (that data had waited " + waited + " ms) and ran for " + cost + " ms" + (this.block ? ", blocking the whole loop." : ".");
    } else {
      var lag = this.now - cb.t.due;
      this.lastLag = lag; if (lag > this.maxLag) this.maxLag = lag;
      this.fired++;
      this.now += TIMER_COST;
      this.message = "DISPATCH: timer T" + cb.t.id + " (due at " + cb.t.due + " ms) fired at " + (this.now - TIMER_COST) +
        " ms. Loop lag: " + lag + " ms" + (lag > 20 ? ", late because something ahead of it was slow." : ".");
    }
    if (!this.queue.length) { this.phase = "wait"; return true; }
    return false;
  };

  /* Run steps until the current iteration is complete (or the loop has nothing to wait for). */
  Loop.prototype.tick = function () {
    for (var guard = 0; guard < 100; guard++) {
      if (this.step()) return true;
      if (this.idle()) return false;
    }
    return false;
  };

  var core = { Loop: Loop, NAMES: NAMES, BLOCK_COST: BLOCK_COST };
  if (typeof module !== "undefined" && module.exports) module.exports = core;

  /* ---------- UI ---------- */
  if (typeof document === "undefined") return;
  var root = document.getElementById("event-loop-sim");
  if (!root) return;

  var loop = new Loop();

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }
  function lane(title, hint) {
    var d = el("div", "evl-lane");
    var h = el("div", "evl-lane-h");
    h.appendChild(el("span", "evl-lane-t", title));
    if (hint) h.appendChild(el("span", "evl-lane-hint", hint));
    d.appendChild(h);
    return d;
  }

  root.textContent = "";
  var head = el("div", "widget-head");
  head.appendChild(el("span", "widget-tag", "Interactive"));
  head.appendChild(el("h4", "widget-title", "Event loop simulator"));
  root.appendChild(head);
  root.appendChild(el("p", "widget-help", "Make things happen with the buttons, then press Next tick. The loop does one full iteration: wait, collect, then run each callback in turn. The clock is simulated, so everything is repeatable."));

  /* controls */
  var ctl = el("div", "widget-row");
  var btnTick = el("button", "btn primary", "Next tick");
  btnTick.type = "button";
  var btnStep = el("button", "btn", "Single step");
  btnStep.type = "button";
  var btnReset = el("button", "btn", "Reset");
  btnReset.type = "button";
  ctl.appendChild(btnTick); ctl.appendChild(btnStep); ctl.appendChild(btnReset);
  root.appendChild(ctl);

  /* lane 1: the loop's step + clock */
  var l1 = lane("1. The loop", "which step just ran");
  var steps = el("div", "evl-steps");
  var stepEls = {};
  [["wait", "WAIT"], ["collect", "COLLECT"], ["dispatch", "DISPATCH"]].forEach(function (p) {
    var s = el("span", "evl-step", p[1]); stepEls[p[0]] = s; steps.appendChild(s);
  });
  var clockEl = el("span", "evl-clock", "t = 0 ms");
  steps.appendChild(clockEl);
  l1.appendChild(steps);
  var stats = el("div", "evl-stats");
  var lagEl = el("span", "evl-stat"), maxLagEl = el("span", "evl-stat"), waitEl = el("span", "evl-stat");
  stats.appendChild(lagEl); stats.appendChild(maxLagEl); stats.appendChild(waitEl);
  l1.appendChild(stats);
  root.appendChild(l1);

  /* lane 2: sockets */
  var l2 = lane("2. Client sockets", "press a client to send it data");
  var socks = el("div", "evl-socks");
  var sockBtns = [], sockInfo = [];
  NAMES.forEach(function (n, i) {
    var b = el("button", "evl-sock");
    b.type = "button";
    var nm = el("span", "evl-sock-n", "Client " + n);
    var info = el("span", "evl-sock-i", "idle");
    b.appendChild(nm); b.appendChild(info);
    b.addEventListener("click", function () {
      loop.send(i);
      loop.message = "Data arrived on client " + NAMES[i] + " at t = " + loop.now + " ms. It sits in the kernel's buffer until the loop reads it.";
      render();
    });
    sockBtns.push(b); sockInfo.push(info); socks.appendChild(b);
  });
  l2.appendChild(socks);
  root.appendChild(l2);

  /* lane 3: ready queue */
  var l3 = lane("3. Ready queue", "callbacks waiting to run, in order");
  var queueEl = el("div", "evl-chips");
  l3.appendChild(queueEl);
  root.appendChild(l3);

  /* lane 4: timers */
  var l4 = lane("4. Timer heap", "earliest deadline first");
  var trow = el("div", "widget-row");
  var delaySel = el("select", "mono");
  delaySel.setAttribute("aria-label", "Timer delay");
  [100, 250, 500, 1000].forEach(function (d) {
    var o = el("option", "", "in " + d + " ms"); o.value = String(d); if (d === 250) o.selected = true; delaySel.appendChild(o);
  });
  var btnTimer = el("button", "btn small", "Add timer");
  btnTimer.type = "button";
  trow.appendChild(delaySel); trow.appendChild(btnTimer);
  l4.appendChild(trow);
  var timerEl = el("div", "evl-chips");
  l4.appendChild(timerEl);
  root.appendChild(l4);

  /* blocking toggle */
  var tgl = el("label", "evl-toggle");
  var cb = el("input"); cb.type = "checkbox";
  tgl.appendChild(cb);
  tgl.appendChild(el("span", "", " Handlers block for 500 ms (like a slow query or a disk write inside the callback)"));
  root.appendChild(tgl);

  /* message + log */
  var msg = el("p", "widget-out evl-msg");
  msg.setAttribute("role", "status");
  msg.setAttribute("aria-live", "polite");
  root.appendChild(msg);
  var logEl = el("ol", "evl-log");
  logEl.setAttribute("aria-label", "History of loop steps");
  root.appendChild(logEl);
  var history = [];

  function chip(text, cls) { return el("span", "evl-chip" + (cls ? " " + cls : ""), text); }

  function render() {
    var k;
    ["wait", "collect", "dispatch"].forEach(function (s) {
      stepEls[s].classList.toggle("on", loop.last === s);
      stepEls[s].classList.toggle("next", loop.last !== s && loop.phase === s);
    });
    clockEl.textContent = "t = " + loop.now + " ms";
    lagEl.textContent = "Last timer lag: " + (loop.lastLag === null ? "none yet" : loop.lastLag + " ms");
    maxLagEl.textContent = "Worst timer lag: " + loop.maxLag + " ms";
    waitEl.textContent = "Longest a socket waited: " + loop.maxWait + " ms";
    lagEl.classList.toggle("bad", loop.lastLag !== null && loop.lastLag > 20);
    maxLagEl.classList.toggle("bad", loop.maxLag > 20);
    waitEl.classList.toggle("bad", loop.maxWait > 20);

    for (k = 0; k < NAMES.length; k++) {
      var p = loop.pending[k];
      var running = loop.running && loop.running.kind === "io" && loop.running.i === k;
      var queued = loop.queue.some(function (c) { return c.kind === "io" && c.i === k; });
      sockInfo[k].textContent = p ? (p + " unread" + (queued ? " (queued)" : "")) : (loop.handled[k] ? "handled " + loop.handled[k] : "idle");
      sockBtns[k].classList.toggle("has-data", p > 0);
      sockBtns[k].classList.toggle("running", !!running);
      sockBtns[k].setAttribute("aria-label", "Client " + NAMES[k] + ": " + (p ? p + " unread message" + (p > 1 ? "s" : "") : "no data") + ". Press to send it data.");
    }

    queueEl.textContent = "";
    if (loop.running) queueEl.appendChild(chip((loop.running.kind === "io" ? "running: read " + NAMES[loop.running.i] : "running: timer T" + loop.running.t.id), "run"));
    loop.queue.forEach(function (c) {
      queueEl.appendChild(chip(c.kind === "io" ? "read " + NAMES[c.i] : "timer T" + c.t.id, c.kind));
    });
    if (!queueEl.childNodes.length) queueEl.appendChild(el("span", "evl-empty", "empty"));

    timerEl.textContent = "";
    loop.timers.forEach(function (t, idx) {
      var left = t.due - loop.now;
      var c = chip("T" + t.id + " due at " + t.due + " ms" + (left < 0 ? " (late by " + (-left) + ")" : left === 0 ? " (now)" : " (in " + left + ")"), left < 0 ? "late" : "timer");
      if (idx === 0) c.classList.add("first");
      timerEl.appendChild(c);
    });
    if (!loop.timers.length) timerEl.appendChild(el("span", "evl-empty", "no timers"));

    var to = loop.phase === "wait" ? loop.timeout() : undefined;
    msg.textContent = loop.message + (to === null ? "" : (to !== undefined ? "  Next wait timeout: " + to + " ms." : ""));

    btnTimer.disabled = loop.timers.length >= MAX_TIMERS;
    logEl.textContent = "";
    history.slice(-6).forEach(function (h) { logEl.appendChild(el("li", "", h)); });
  }

  function note() {
    history.push("t=" + loop.now + " ms: " + loop.message);
    if (history.length > 40) history.shift();
  }

  btnTick.addEventListener("click", function () {
    var before = loop.now;
    loop.tick();
    note();
    render();
    if (loop.now === before && loop.idle()) { /* message already explains why nothing moved */ }
  });
  btnStep.addEventListener("click", function () { loop.step(); note(); render(); });
  btnReset.addEventListener("click", function () {
    var b = loop.block;
    loop.reset(); loop.block = b; history = []; render();
  });
  btnTimer.addEventListener("click", function () {
    var d = parseInt(delaySel.value, 10);
    if (loop.addTimer(d)) loop.message = "Timer T" + (loop.nextTimerId - 1) + " added: due at t = " + (loop.now + d) + " ms.";
    render();
  });
  cb.addEventListener("change", function () {
    loop.block = cb.checked;
    loop.message = cb.checked
      ? "Handlers now block for 500 ms each. Send data to two or three clients, add a short timer, and press Next tick."
      : "Handlers are quick again (2 ms each).";
    render();
  });

  render();
})();
