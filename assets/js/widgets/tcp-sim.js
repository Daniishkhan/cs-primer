/* TCP sliding-window / loss simulator (chapter 8).
   A sender transmits 12 numbered segments to a receiver across a link that
   takes 3 ticks one way (so RTT = 6 ticks). The link carries at most one
   segment per tick. The receiver sends a cumulative ACK for every segment it
   gets ("ACK n" = "I have everything before n; send n next"). The sender has a
   window of W unacknowledged segments and one retransmission timer (RTO = 10
   ticks). Click any packet in flight to drop it.
   Root: <div class="widget" id="tcp-sim"> ... </div> (JS fills it in). */
(function () {
  "use strict";
  var root = document.getElementById("tcp-sim");
  if (!root) return;

  var N = 12, D = 3, RTO = 10;
  var W = 4, fast = false;
  var lastCount = 0;
  var t, base, nextSeq, timer, dupCount, fastDone, expected, buf, flightD, flightA, ghosts, log, lastAck, done, uid, armed, ticking;
  var els = {};     /* id -> button element for packets in flight */
  var ui = {};
  var autoTimer = null;

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }

  function init() {
    t = 0; base = 1; nextSeq = 1; timer = null; dupCount = 0; fastDone = false;
    expected = 1; buf = {}; flightD = []; flightA = []; ghosts = []; log = [];
    lastAck = 0; done = false; uid = 0; armed = false;
    log.unshift("Press Step or Play. The sender will start sending segment 1.");
  }

  /* ---------- simulation ---------- */
  function sendAck(ev) {
    var a = { id: uid++, ack: expected, sent: t, arrive: t + D, dup: expected === lastAck };
    lastAck = expected;
    flightA.push(a);
  }

  function receive(p, ev) {
    if (p.seq === expected) {
      expected++;
      var released = [];
      while (buf[expected]) { delete buf[expected]; released.push(expected); expected++; }
      ev.push("Receiver gets segment " + p.seq + " in order and hands it to the application." +
        (released.length ? " That also fills the gap, so buffered segment" + (released.length > 1 ? "s " : " ") + released.join(", ") + " go to the application too." : "") +
        " It replies ACK " + expected + ".");
    } else if (p.seq > expected) {
      buf[p.seq] = true;
      ev.push("Receiver gets segment " + p.seq + " but is still waiting for " + expected + ". It keeps " + p.seq + " in its buffer (the app can't have it yet: order matters) and repeats ACK " + expected + ".");
    } else {
      ev.push("Receiver already had segment " + p.seq + " (a duplicate); it ignores it and re-sends ACK " + expected + ".");
    }
    sendAck(ev);
  }

  function sendData(seq, isRe, ev) {
    if (armed && !isRe) {
      armed = false;
      ghosts.push({ lane: "d", prog: 0.5, until: t + 2, seq: seq });
      ev.push("Sender sends segment " + seq + " but it is LOST in the network (the ✕). The sender can't know that yet.");
    } else {
      flightD.push({ id: uid++, seq: seq, sent: t, arrive: t + D, re: isRe });
      ev.push(isRe ? "Sender RE-SENDS segment " + seq + "." : "Sender sends segment " + seq + ".");
    }
  }

  function tick() {
    if (done) return;
    t++;
    ghosts = ghosts.filter(function (g) { return g.until > t; });
    var ev = [];

    /* 1. data arrives at the receiver */
    var arr = flightD.filter(function (p) { return p.arrive <= t; });
    flightD = flightD.filter(function (p) { return p.arrive > t; });
    arr.forEach(function (p) { receive(p, ev); });

    /* 2. ACKs arrive at the sender */
    var acks = flightA.filter(function (a) { return a.arrive <= t; });
    flightA = flightA.filter(function (a) { return a.arrive > t; });
    var fastNow = false;
    acks.forEach(function (a) {
      if (a.ack > base) {
        base = a.ack; dupCount = 0; fastDone = false;
        timer = base < nextSeq ? t : null;
        ev.push(base > N ? "ACK " + a.ack + " arrives: everything is confirmed." : "ACK " + a.ack + " arrives: segments before " + a.ack + " are safe. The window slides forward.");
      } else if (a.ack === base && base < nextSeq) {
        dupCount++;
        ev.push("Duplicate ACK " + a.ack + " arrives (" + dupCount + " in a row): the receiver is still missing segment " + base + ".");
        if (fast && dupCount >= 3 && !fastDone) { fastDone = true; fastNow = true; }
      }
    });

    if (base > N) {
      done = true;
      ev.push("All " + N + " segments delivered and acknowledged after " + t + " ticks.");
      pushLog(ev);
      return;
    }

    /* 3. retransmission (fast retransmit or timeout), else 4. send something new */
    var timedOut = timer !== null && base < nextSeq && (t - timer) >= RTO;
    if (fastNow) {
      ev.push("Three duplicate ACKs: fast retransmit! The sender doesn't wait for the timer.");
      sendData(base, true, ev); timer = t;
    } else if (timedOut) {
      ev.push("TIMEOUT: no progress for " + RTO + " ticks. The sender assumes segment " + base + " was lost.");
      sendData(base, true, ev); timer = t;
    } else if (nextSeq < base + W && nextSeq <= N) {
      sendData(nextSeq, false, ev);
      if (timer === null) timer = t;
      nextSeq++;
    } else if (nextSeq <= N) {
      ev.push("Window full (" + W + " segment" + (W > 1 ? "s" : "") + " sent and not yet acknowledged). The sender must wait.");
    }
    pushLog(ev);
  }

  function pushLog(ev) {
    if (!ev.length) ev.push("Nothing happens this tick.");
    lastCount = ev.length;
    log = ev.concat(log).slice(0, 6);
  }

  function dropPacket(kind, id) {
    var list = kind === "d" ? flightD : flightA, i;
    for (i = 0; i < list.length; i++) if (list[i].id === id) break;
    if (i === list.length) return;
    var p = list[i];
    list.splice(i, 1);
    ghosts.push({ lane: kind, prog: Math.min(1, (t - p.sent) / D), until: t + 2 });
    lastCount = 1;
    log.unshift("You dropped " + (kind === "d" ? "segment " + p.seq : "ACK " + p.ack) + " in flight. " +
      (kind === "d" ? "The receiver will never see it." : "The sender will not see that acknowledgement."));
    log = log.slice(0, 6);
    render();
  }

  /* ---------- UI ---------- */
  function build() {
    var head = root.querySelector(".widget-head");
    Array.prototype.slice.call(root.children).forEach(function (c) { if (c !== head) root.removeChild(c); });

    root.appendChild(el("p", "widget-help", "Segments 1 to 12 travel down the left lane; acknowledgements travel up the right lane. Click (or tab to and press Enter on) any packet in flight to drop it, or use \"Drop next segment\". Then watch the timer, the buffer and the window."));

    var row = el("div", "widget-row");
    var l1 = el("label", null, "Window size:"); l1.htmlFor = "ts-win";
    ui.win = el("select"); ui.win.id = "ts-win";
    [[1, "1 (stop-and-wait)"], [4, "4 segments"], [8, "8 segments"]].forEach(function (o) {
      var op = el("option", null, o[1]); op.value = o[0]; if (o[0] === W) op.selected = true; ui.win.appendChild(op);
    });
    var l2 = el("label", "ts-check");
    ui.fast = el("input"); ui.fast.type = "checkbox"; ui.fast.id = "ts-fast";
    l2.appendChild(ui.fast); l2.appendChild(document.createTextNode(" Fast retransmit (after 3 duplicate ACKs)"));
    row.appendChild(l1); row.appendChild(ui.win); row.appendChild(l2);
    root.appendChild(row);

    var stage = el("div", "ts-stage");
    /* sender */
    var snd = el("div", "ts-side ts-sender");
    snd.appendChild(el("div", "ts-title", "💻 Sender"));
    ui.sCells = el("div", "ts-cells"); snd.appendChild(ui.sCells);
    ui.sInfo = el("div", "ts-info"); snd.appendChild(ui.sInfo);
    ui.sCellEls = [];
    for (var i = 1; i <= N; i++) { var c = el("div", "ts-cell", String(i)); ui.sCells.appendChild(c); ui.sCellEls.push(c); }
    stage.appendChild(snd);
    /* link */
    ui.link = el("div", "ts-link");
    ui.link.appendChild(el("div", "ts-lane-label ts-lane-d", "data ↓"));
    ui.link.appendChild(el("div", "ts-lane-label ts-lane-a", "ACKs ↑"));
    ui.link.appendChild(el("div", "ts-lane-line ts-lane-line-d"));
    ui.link.appendChild(el("div", "ts-lane-line ts-lane-line-a"));
    ui.ghostLayer = el("div", "ts-ghosts"); ui.link.appendChild(ui.ghostLayer);
    stage.appendChild(ui.link);
    /* receiver */
    var rcv = el("div", "ts-side ts-receiver");
    rcv.appendChild(el("div", "ts-title", "🗄️ Receiver"));
    ui.rCells = el("div", "ts-cells"); rcv.appendChild(ui.rCells);
    ui.rCellEls = [];
    for (i = 1; i <= N; i++) { var c2 = el("div", "ts-cell", String(i)); ui.rCells.appendChild(c2); ui.rCellEls.push(c2); }
    ui.rInfo = el("div", "ts-info"); rcv.appendChild(ui.rInfo);
    stage.appendChild(rcv);
    root.appendChild(stage);

    var legend = el("div", "ts-legend");
    [["ts-cell acked", "acknowledged / delivered"], ["ts-cell sent", "sent, not yet acknowledged"], ["ts-cell buffered", "buffered out of order"], ["ts-cell inwin", "allowed by window, not sent yet"]].forEach(function (x) {
      var s = el("span", "ts-legend-item"); s.appendChild(el("span", x[0] + " ts-swatch")); s.appendChild(document.createTextNode(" " + x[1])); legend.appendChild(s);
    });
    root.appendChild(legend);

    var btns = el("div", "widget-row");
    ui.reset = el("button", "btn small", "⏮ Reset");
    ui.step = el("button", "btn small primary", "Step →");
    ui.play = el("button", "btn small", "▶ Play");
    ui.drop = el("button", "btn small danger", "✕ Drop next segment"); ui.drop.setAttribute("aria-pressed", "false");
    ui.stats = el("span", "ts-stats");
    [ui.reset, ui.step, ui.play, ui.drop].forEach(function (b) { b.type = "button"; btns.appendChild(b); });
    btns.appendChild(ui.stats);
    root.appendChild(btns);

    ui.log = el("div", "widget-out ts-log"); ui.log.setAttribute("aria-live", "polite");
    root.appendChild(ui.log);

    ui.win.addEventListener("change", function () { W = parseInt(ui.win.value, 10); restart(); });
    ui.fast.addEventListener("change", function () { fast = ui.fast.checked; restart(); });
    ui.reset.addEventListener("click", restart);
    ui.step.addEventListener("click", function () { stopAuto(); tick(); render(); });
    ui.play.addEventListener("click", function () { if (autoTimer) stopAuto(); else startAuto(); });
    ui.drop.addEventListener("click", function () { armed = !armed; render(); });
  }

  function stopAuto() { if (autoTimer) { clearInterval(autoTimer); autoTimer = null; } ui.play.textContent = "▶ Play"; }
  function startAuto() {
    if (done) { restart(); }
    ui.play.textContent = "⏸ Pause";
    tick(); render();
    autoTimer = setInterval(function () {
      tick(); render();
      if (done) stopAuto();
    }, 750);
  }
  function restart() { stopAuto(); init(); clearPackets(); render(); }
  function clearPackets() { Object.keys(els).forEach(function (k) { if (els[k].parentNode) els[k].parentNode.removeChild(els[k]); delete els[k]; }); }

  function pos(kind, sent) {
    var p = Math.max(0, Math.min(1, (t - sent) / D));
    return kind === "d" ? 14 + p * 72 : 86 - p * 72;
  }

  function syncPackets() {
    var live = {};
    flightD.forEach(function (p) {
      var key = "d" + p.id; live[key] = true;
      var b = els[key];
      if (!b) {
        b = el("button", "ts-pkt ts-pkt-d" + (p.re ? " re" : ""), String(p.seq)); b.type = "button";
        b.setAttribute("aria-label", "Drop segment " + p.seq + (p.re ? " (retransmission)" : ""));
        b.title = "Click to drop segment " + p.seq;
        (function (id) { b.addEventListener("click", function () { dropPacket("d", id); }); })(p.id);
        b.style.top = pos("d", p.sent) + "%";
        ui.link.appendChild(b); els[key] = b;
      }
      b.style.top = pos("d", p.sent) + "%";
    });
    flightA.forEach(function (a) {
      var key = "a" + a.id; live[key] = true;
      var b = els[key];
      if (!b) {
        b = el("button", "ts-pkt ts-pkt-a" + (a.dup ? " dup" : ""), "ACK " + a.ack); b.type = "button";
        b.setAttribute("aria-label", "Drop acknowledgement " + a.ack);
        b.title = "Click to drop ACK " + a.ack;
        (function (id) { b.addEventListener("click", function () { dropPacket("a", id); }); })(a.id);
        b.style.top = pos("a", a.sent) + "%";
        ui.link.appendChild(b); els[key] = b;
      }
      b.style.top = pos("a", a.sent) + "%";
    });
    Object.keys(els).forEach(function (k) {
      if (!live[k]) { if (els[k].parentNode) els[k].parentNode.removeChild(els[k]); delete els[k]; }
    });
  }

  function render() {
    syncPackets();
    /* ghosts (lost packets) */
    ui.ghostLayer.textContent = "";
    ghosts.forEach(function (g) {
      var s = el("span", "ts-ghost ts-ghost-" + g.lane, "✕");
      s.style.top = (g.lane === "d" ? 14 + g.prog * 72 : 86 - g.prog * 72) + "%";
      ui.ghostLayer.appendChild(s);
    });
    /* sender cells */
    ui.sCellEls.forEach(function (c, i) {
      var seq = i + 1, cls = "ts-cell";
      if (seq < base) cls += " acked";
      else if (seq < nextSeq) cls += " sent";
      else if (seq < base + W && !done) cls += " inwin";
      if (seq >= base && seq < base + W && !done) cls += " window";
      c.className = cls;
    });
    ui.sInfo.textContent = done ? "Window: done" : "Window: segments " + base + " to " + Math.min(N, base + W - 1) + " may be in flight" +
      (timer !== null ? " · timer running (" + Math.max(0, RTO - (t - timer)) + " ticks left)" : " · no timer");
    /* receiver cells */
    ui.rCellEls.forEach(function (c, i) {
      var seq = i + 1, cls = "ts-cell";
      if (seq < expected) cls += " acked";
      else if (buf[seq]) cls += " buffered";
      c.className = cls;
    });
    var bufList = Object.keys(buf).map(Number).sort(function (a, b) { return a - b; });
    ui.rInfo.textContent = "Application has received: " + (expected > 1 ? "1 to " + (expected - 1) : "nothing yet") +
      " · waiting for " + (expected > N ? "nothing" : expected) + (bufList.length ? " · buffered: " + bufList.join(", ") : "");
    /* controls */
    ui.step.disabled = done;
    ui.drop.setAttribute("aria-pressed", armed ? "true" : "false");
    ui.drop.textContent = armed ? "✕ Dropping the next segment…" : "✕ Drop next segment";
    ui.stats.textContent = "tick " + t + " · RTT = " + (2 * D) + " ticks";
    /* log */
    ui.log.textContent = "";
    log.forEach(function (line, i) {
      var p = el("div", i < lastCount ? "ts-log-new" : "ts-log-old", line);
      ui.log.appendChild(p);
    });
  }

  init();
  build();
  render();
})();
