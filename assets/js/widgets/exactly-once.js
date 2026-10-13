/* Exactly-once explorer (distributed chapter 17).

   One payment record ("charge $40") travels  producer -> broker log -> consumer -> sink.
   You choose how each hop is built and where the network or a process fails, then step
   through the run and read the verdict: how many copies reached the log, and how many
   times the sink applied the charge.

   Producer:  no retry | retry | retry + idempotent producer (producer id + sequence number)
   Fault on the first send: none | request lost | ack lost
   Consumer:  commit offset then process | process then commit | process + offset in one
              transaction | process then commit, with a sink that upserts by offset
   Consumer crash: none | crash in the gap between the two consumer steps

   Simplifications: one partition, one record per send; the consumer reads whatever is in
   the log (so a duplicate in the log is two records at two offsets); after a crash the
   consumer restarts and resumes from its committed offset. Fully deterministic. */
(function () {
  "use strict";
  var root = document.getElementById("exactly-once");
  if (!root) return;

  var PRICE = 40;
  var opts = { prod: "retry", fault: "ackLost", cons: "pc", crash: "gap" };
  var events = [], shown = 0, verdict = null;

  var PROD = [
    ["none", "No retry"],
    ["retry", "Retry on timeout"],
    ["idem", "Retry + idempotent producer"]
  ];
  var FAULT = [
    ["none", "No network fault"],
    ["reqLost", "First request is lost"],
    ["ackLost", "First ack is lost"]
  ];
  var CONS = [
    ["cp", "Commit offset, then process"],
    ["pc", "Process, then commit offset"],
    ["tx", "Process + offset in ONE transaction"],
    ["up", "Process, then commit (sink upserts by offset)"]
  ];
  var CRASH = [
    ["none", "No consumer crash"],
    ["gap", "Crash between the consumer's two steps"]
  ];

  function simulate(o) {
    var ev = [];
    function add(lane, text, kind) { ev.push({ lane: lane, text: text, kind: kind || "" }); }
    var log = [];                 /* values at offsets 0.. */
    var lastSeq = -1;
    var pid = 7;

    /* ---- producer side ---- */
    var attempts = o.prod === "none" ? 1 : 3;
    var delivered = false;
    for (var a = 1; a <= attempts && !delivered; a++) {
      var seq = 0;
      add("producer", "send charge $" + PRICE + " (producer id " + pid + ", seq " + seq + ")" + (a > 1 ? " [retry " + (a - 1) + "]" : ""));
      if (a === 1 && o.fault === "reqLost") {
        add("net", "the request is lost on the way to the broker", "bad");
      } else {
        if (o.prod === "idem" && seq <= lastSeq) {
          add("broker", "already have (producer " + pid + ", seq " + seq + "): do NOT append again, just ack", "good");
        } else {
          log.push("charge $" + PRICE);
          lastSeq = seq;
          add("broker", "append to log at offset " + (log.length - 1));
        }
        if (a === 1 && o.fault === "ackLost") {
          add("net", "the ack is lost on the way back", "bad");
        } else {
          add("broker", "ack to producer");
          delivered = true;
        }
      }
      if (!delivered) {
        if (a < attempts) add("producer", "timeout: no ack, so retry");
        else add("producer", "timeout: no ack, and no retries left. Gives up", "bad");
      }
    }
    if (delivered) add("producer", "got the ack, done");

    /* ---- consumer side ---- */
    var sink = [];                 /* effects applied (one entry per application) */
    var sinkKeys = {};
    var committed = 0;
    var crashPending = o.crash === "gap";
    add("consumer", "starts reading the log (committed offset = 0)");
    function applyEffect(off) {
      if (o.cons === "up") {
        if (sinkKeys[off]) { add("sink", "upsert key offset=" + off + " already present: overwrite with same value, no change", "good"); return; }
        sinkKeys[off] = true;
      }
      sink.push(off);
      add("sink", "apply charge $" + PRICE + " for offset " + off);
    }
    function pass(startAt) {
      for (var off = startAt; off < log.length; off++) {
        add("consumer", "read offset " + off);
        if (o.cons === "cp") {
          committed = off + 1; add("consumer", "commit offset " + committed);
          if (crashPending) { crashPending = false; add("consumer", "CRASH between commit and processing", "bad"); return off + 1; }
          applyEffect(off);
        } else if (o.cons === "tx") {
          if (crashPending) {
            crashPending = false;
            add("consumer", "begin transaction: charge + offset " + (off + 1));
            add("consumer", "CRASH before the transaction commits: both are rolled back", "bad");
            return off;
          }
          add("consumer", "begin transaction: charge + offset " + (off + 1));
          applyEffect(off); committed = off + 1;
          add("consumer", "commit transaction: charge and offset " + committed + " become durable together", "good");
        } else {
          applyEffect(off);
          if (crashPending) { crashPending = false; add("consumer", "CRASH between processing and commit", "bad"); return off; }
          committed = off + 1; add("consumer", "commit offset " + committed);
        }
      }
      return -1;
    }
    var crashedAt = pass(0);
    if (crashedAt !== -1) {
      add("consumer", "restarts and resumes from the committed offset " + committed, "");
      pass(committed);
    }

    var copies = log.length, applied = sink.length, total = applied * PRICE;
    var v;
    if (applied === 0) v = { cls: "bad", text: "LOST. The sink applied the charge 0 times (total $0). The customer was never charged." };
    else if (applied === 1 && log.length !== 1) v = { cls: "bad", text: "Applied once, but only by accident. The log holds " + log.length + " copies of the record and the consumer crash happened to skip one of them: a duplicate and a loss cancelled out. That is not exactly-once." };
    else if (applied === 1) v = { cls: "good", text: "Exactly-once EFFECT. The charge was applied once (total $" + PRICE + ")." };
    else v = { cls: "bad", text: "DUPLICATED. The sink applied the charge " + applied + " times (total $" + total + "). The customer was charged twice." };
    var why = [];
    if (copies === 0) why.push("log holds 0 records");
    else if (copies > 1) why.push("the log holds " + copies + " copies of the record (producer retry without idempotence)");
    else why.push("the log holds 1 record");
    return { events: ev, verdict: v, copies: copies, applied: applied, why: why.join("; ") };
  }

  /* ---------- DOM ---------- */
  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function select(label, list, key) {
    var wrap = el("label", "xo-field");
    wrap.appendChild(el("span", "xo-label", label));
    var s = el("select"); s.className = "xo-select";
    list.forEach(function (p) { var o = el("option", null, p[1]); o.value = p[0]; s.appendChild(o); });
    s.value = opts[key];
    s.addEventListener("change", function () { opts[key] = s.value; run(); });
    wrap.appendChild(s);
    return wrap;
  }
  function btn(label, cls, fn) { var b = el("button", "btn " + (cls || ""), label); b.type = "button"; b.addEventListener("click", fn); return b; }

  var head = el("div", "widget-head");
  head.appendChild(el("span", "widget-tag", "Simulator"));
  head.appendChild(el("span", "widget-title", "Where does a duplicate (or a loss) sneak in?"));
  root.appendChild(head);
  root.appendChild(el("p", "widget-help", "Pick how the producer and consumer are built and where things fail, then step through. The verdict counts how many times the sink applied the charge. Try to find every combination that gives exactly one."));

  var grid = el("div", "xo-grid");
  grid.appendChild(select("Producer", PROD, "prod"));
  grid.appendChild(select("Network fault", FAULT, "fault"));
  grid.appendChild(select("Consumer", CONS, "cons"));
  grid.appendChild(select("Consumer crash", CRASH, "crash"));
  root.appendChild(grid);

  var ctl = el("div", "xo-btns");
  var bNext = btn("Next event", "primary small", function () { if (shown < events.length) { shown++; draw(); } });
  var bAll = btn("Run to the end", "small", function () { shown = events.length; draw(); });
  var bReset = btn("Restart", "small", function () { shown = 0; draw(); });
  ctl.appendChild(bNext); ctl.appendChild(bAll); ctl.appendChild(bReset);
  root.appendChild(ctl);

  var lanes = el("div", "xo-lanes");
  root.appendChild(lanes);
  var out = el("div", "xo-verdict"); out.setAttribute("aria-live", "polite");
  root.appendChild(out);
  var note = el("p", "xo-note");
  root.appendChild(note);

  var LANE_NAME = { producer: "Producer", net: "Network", broker: "Broker", consumer: "Consumer", sink: "Sink" };

  function draw() {
    lanes.textContent = "";
    for (var i = 0; i < shown; i++) {
      var e = events[i];
      var row = el("div", "xo-row " + e.kind + (i === shown - 1 ? " last" : ""));
      row.appendChild(el("span", "xo-lane xo-" + e.lane, LANE_NAME[e.lane]));
      row.appendChild(el("span", "xo-text", e.text));
      lanes.appendChild(row);
    }
    if (!shown) lanes.appendChild(el("p", "xo-empty", "Press Next event to start the run."));
    bNext.disabled = shown >= events.length;
    out.textContent = "";
    note.textContent = "";
    if (shown >= events.length) {
      out.className = "xo-verdict " + verdict.cls;
      out.textContent = verdict.text;
      note.textContent = "Why: " + verdict.why + ".";
    } else {
      out.className = "xo-verdict";
    }
  }
  function run() {
    var r = simulate(opts);
    events = r.events; verdict = { cls: r.verdict.cls, text: r.verdict.text, why: r.why };
    shown = 0; draw();
  }
  run();
})();
