/* Seeded-simulation explorer (distributed chapter 19).

   The same tiny primary-backup store as the chapter's Python simulator, run in the
   browser inside a deterministic event loop:
     - primary P replicates each write to backups B and C; messages can be dropped or delayed;
     - P acks the client after ONE backup confirms (P + one backup is a majority of 3);
     - P crashes at a random time and a failover promotes a backup.
   Invariant: after failover the new primary holds every write that was acknowledged.
   "Buggy" failover promotes B without looking at the logs; "fixed" failover merges the
   survivors' logs.

   Everything random is derived from (seed, purpose), so a seed always produces the same
   trace. Buttons: run a seed, step to the next seed, search for a failing seed, replay it
   (re-run and compare the traces), shrink (fewest writes that still fail).
   This widget uses its own generator (mulberry32 over a string hash), so seed numbers do
   NOT match the Python version's; the behaviour is the same. */
(function () {
  "use strict";
  var root = document.getElementById("sim-seed");
  if (!root) return;

  function hash(str) {
    var h = 2166136261 >>> 0;
    for (var i = 0; i < str.length; i++) { h ^= str.charCodeAt(i); h = Math.imul(h, 16777619) >>> 0; }
    return h >>> 0;
  }
  function mulberry32(a) {
    return function () {
      a = (a + 0x6D2B79F5) >>> 0;
      var t = a;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  function rng(seed, purpose) { return mulberry32(hash(seed + ":" + purpose)); }

  function simulate(seed, writes, fixed) {
    var q = [], n = 0;
    function at(t, fn) { q.push({ t: t, n: n++, fn: fn }); }
    var logs = { B: [], C: [] }, alive = true, acked = [], trace = [], failure = null;
    var crashT = 2 + Math.floor(rng(seed, "crash")() * 24);
    function say(t, msg, bad) { trace.push({ t: t, msg: msg, bad: !!bad }); }

    function write(t, i) {
      if (!alive) { say(t, "client sends w" + i + ": primary is down, ignored"); return; }
      say(t, "client sends w" + i + " to P");
      ["B", "C"].forEach(function (b) {
        var r = rng(seed, "msg" + i + b);
        if (r() < 0.3) { say(t, "   P -> " + b + ": w" + i + " DROPPED", true); return; }
        var d = 1 + Math.floor(r() * 6), back = 1 + Math.floor(r() * 4);
        at(t + d, function () {
          logs[b].push(i);
          say(t + d, "   " + b + " stores w" + i);
          at(t + d + back, function () {
            if (alive && acked.indexOf(i) < 0) { acked.push(i); say(t + d + back, "   P acks w" + i + " to client (confirmed by " + b + ")"); }
          });
        });
      });
    }
    for (var i = 0; i < writes; i++) (function (i) { at(4 * i, function () { write(4 * i, i); }); })(i);
    at(crashT, function () { alive = false; say(crashT, "P CRASHES", true); });
    at(crashT + 3, function () {
      var t = crashT + 3, nl, who;
      if (fixed) {
        var u = {}; logs.B.concat(logs.C).forEach(function (x) { u[x] = 1; });
        nl = Object.keys(u).map(Number).sort(function (a, b) { return a - b; }); who = "B+C merged";
      } else { nl = logs.B.slice().sort(function (a, b) { return a - b; }); who = "B"; }
      say(t, "failover: " + who + " becomes primary with log [" + nl.join(", ") + "]");
      var lost = acked.filter(function (w) { return nl.indexOf(w) < 0; });
      if (lost.length) { failure = "acked write(s) [" + lost.join(", ") + "] are missing from the new primary"; say(t, "INVARIANT VIOLATED: " + failure, true); }
    });
    while (q.length) {
      q.sort(function (a, b) { return a.t - b.t || a.n - b.n; });
      q.shift().fn();
    }
    trace.sort(function (a, b) { return a.t - b.t; });   /* stable in modern engines: equal times keep order */
    return { failure: failure, trace: trace };
  }
  function sig(r) { return r.trace.map(function (x) { return x.t + x.msg; }).join("|"); }

  var S = { seed: 0, writes: 4, fixed: false, last: null };

  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function btn(label, cls, fn) { var b = el("button", "btn " + (cls || ""), label); b.type = "button"; b.addEventListener("click", fn); return b; }

  var head = el("div", "widget-head");
  head.appendChild(el("span", "widget-tag", "Simulator"));
  head.appendChild(el("span", "widget-title", "Flip seeds until the invariant breaks, then replay"));
  root.appendChild(head);
  root.appendChild(el("p", "widget-help", "Each seed is one complete, reproducible run of a primary-backup store with a random crash. Search for a seed that violates the invariant, replay it to prove it is identical, shrink it, then switch to the fixed failover and search again."));

  var row = el("div", "ss-row");
  var lab = el("label", "ss-field"); lab.appendChild(el("span", "ss-label", "Seed"));
  var inp = el("input"); inp.type = "number"; inp.min = "0"; inp.max = "999999"; inp.value = "0"; inp.className = "ss-input";
  inp.addEventListener("change", function () { var v = parseInt(inp.value, 10); S.seed = isNaN(v) || v < 0 ? 0 : v; inp.value = S.seed; run(); });
  lab.appendChild(inp); row.appendChild(lab);
  var lab2 = el("label", "ss-check");
  var cb = el("input"); cb.type = "checkbox";
  cb.addEventListener("change", function () { S.fixed = cb.checked; run(); });
  lab2.appendChild(cb); lab2.appendChild(el("span", null, "Use the fixed failover (merge logs)"));
  row.appendChild(lab2);
  root.appendChild(row);

  var btns = el("div", "ss-btns");
  btns.appendChild(btn("Next seed", "small", function () { S.seed++; inp.value = S.seed; run(); }));
  btns.appendChild(btn("Find a failing seed", "primary small", function () {
    var s = S.seed, tries = 0;
    do { s++; tries++; } while (!simulate(s, S.writes, S.fixed).failure && tries < 5000);
    S.seed = s; inp.value = s; run();
    if (!S.last.failure) msg.textContent = "No failing seed found in the next 5000 seeds.";
    else msg.textContent = "Found after " + tries + " seed" + (tries === 1 ? "" : "s") + ".";
  }));
  btns.appendChild(btn("Replay this seed", "small", function () {
    var a = sig(S.last), b = sig(simulate(S.seed, S.writes, S.fixed));
    msg.textContent = a === b ? "Replayed seed " + S.seed + ": the trace is identical, event for event." : "The traces differ (this should never happen).";
  }));
  btns.appendChild(btn("Shrink", "small", function () {
    if (!S.last.failure) { msg.textContent = "Shrink needs a failing run. Use Find a failing seed first."; return; }
    for (var k = 1; k <= S.writes; k++) {
      if (simulate(S.seed, k, S.fixed).failure) { S.writes = k; run(); msg.textContent = "Shrunk to the fewest writes that still fail: " + k + "."; return; }
    }
  }));
  btns.appendChild(btn("Reset writes to 4", "small", function () { S.writes = 4; run(); }));
  root.appendChild(btns);

  var status = el("div", "ss-status"); status.setAttribute("aria-live", "polite");
  root.appendChild(status);
  var msg = el("p", "ss-msg"); msg.setAttribute("aria-live", "polite");
  root.appendChild(msg);
  var tr = el("ol", "ss-trace");
  root.appendChild(tr);

  function run() {
    var r = simulate(S.seed, S.writes, S.fixed);
    S.last = r;
    status.className = "ss-status " + (r.failure ? "bad" : "good");
    status.textContent = "Seed " + S.seed + ", " + S.writes + " write" + (S.writes === 1 ? "" : "s") + ", " + (S.fixed ? "fixed" : "buggy") + " failover: " +
      (r.failure ? "INVARIANT VIOLATED, " + r.failure + "." : "invariant holds.");
    msg.textContent = "";
    tr.textContent = "";
    r.trace.forEach(function (x) { tr.appendChild(el("li", x.bad ? "bad" : "", "t=" + x.t + "  " + x.msg)); });
  }
  run();
})();
