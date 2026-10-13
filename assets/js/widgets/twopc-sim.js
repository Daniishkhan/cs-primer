/* Two-phase commit simulator (distributed chapter 13).

   One transaction, one coordinator (C) and three participants (P1..P3). Time runs DOWN the
   page. Each step is one row; pressing Step reveals the next row. You choose

     - a crash point (coordinator or P2), or none;
     - whether P3 votes YES or NO;
     - whether the crashed node ever comes back ("never restart" shows the blocking window).

   The whole run is precomputed from those choices by simulate(), then replayed up to the
   current step. Nothing is random.

   What the model keeps faithful to textbook 2PC with presumed abort:
     - a participant force-logs "prepared" BEFORE replying YES, and holds its locks from then
       until it learns the decision;
     - the coordinator force-logs COMMIT before telling anyone (the commit point); for an
       abort it logs nothing, and a restarted coordinator with no record answers ABORT;
     - a restarted in-doubt participant re-takes its locks and asks the coordinator (INQUIRE);
     - a participant that never logged "prepared" may abort on its own.
   Simplifications: one transaction; a single crash; the coordinator does not retry lost
   messages (a recovering node asks instead); the end record is shown but not forced.
*/
(function () {
  "use strict";
  var root = document.getElementById("twopc-sim");
  if (!root) return;

  var P = ["P1", "P2", "P3"];
  var LANE_X = { C: 62, P1: 182, P2: 302, P3: 422 };
  var ROW = 56, TOP = 58, W = 500;
  var NAMES = { C: "Coordinator", P1: "Participant 1", P2: "Participant 2", P3: "Participant 3" };
  var CRASHES = [
    ["none", "No crash"],
    ["c-before", "Coordinator: before sending PREPARE"],
    ["c-mid-prepare", "Coordinator: after PREPARE reached P1 only"],
    ["c-votes-in", "Coordinator: all votes in, nothing logged"],
    ["c-logged", "Coordinator: COMMIT logged, nothing sent"],
    ["c-mid-decision", "Coordinator: COMMIT reached P1 only"],
    ["p2-before-log", "P2: before logging its vote"],
    ["p2-after-log", "P2: logged prepared, reply lost"],
    ["p2-after-vote", "P2: just after voting YES"],
    ["p2-after-decision", "P2: got COMMIT, died before logging it"]
  ];

  /* ------------------------------------------------------------------ simulation */
  function simulate(cfg) {
    var S = [], alive = { C: 1, P1: 1, P2: 1, P3: 1 };
    var vote = {}, prepared = {}, decided = {}, clog = [], crashed = null, decision = null;
    var cr = cfg.crash;

    function step(text) { var s = { text: text, items: [] }; S.push(s); return s; }
    function msg(s, from, to, label, color, half, lost) { s.items.push({ k: "msg", from: from, to: to, label: label, color: color, half: half, lost: !!lost }); }
    function log(s, n, text, dy, extra) { s.items.push({ k: "log", n: n, text: text, dy: dy, tag: extra }); }
    function lock(s, n, on, dy) { s.items.push({ k: "lock", n: n, on: on, dy: dy }); }
    function crash(s, n, dy) { s.items.push({ k: "crash", n: n, dy: dy }); alive[n] = 0; if (!crashed) crashed = n; if (n !== "C") lock(s, n, false, dy); }
    function restart(s, n, dy) { s.items.push({ k: "restart", n: n, dy: dy }); alive[n] = 1; }
    function cLog(s, text, dy, tag) { clog.push(text); log(s, "C", text, dy, tag); }

    /* ---- phase 1: prepare and vote */
    if (cr === "c-before") {
      var s0 = step("The coordinator crashes before sending a single PREPARE. Nobody has promised anything, so there is nothing to be stuck on.");
      crash(s0, "C", 24);
    } else {
      for (var i = 0; i < P.length; i++) {
        var p = P[i], s = step(""), yes = !(p === "P3" && !cfg.p3yes);
        msg(s, "C", p, "PREPARE", "blue", 0);
        if (p === "P2" && cr === "p2-before-log") {
          s.text = "P2 receives PREPARE and crashes before writing anything. It sends no vote, and has promised nothing.";
          crash(s, "P2", 30); vote.P2 = null; continue;
        }
        if (!yes) {
          s.text = p + " cannot commit, so it logs abort and votes NO. A NO vote is final and it can release everything at once.";
          log(s, p, "abort", 24); decided[p] = "abort"; msg(s, p, "C", "NO", "red", 1); vote[p] = "NO";
        } else {
          log(s, p, "prepared", 24, "force"); lock(s, p, true, 24); prepared[p] = 1;
          if (p === "P2" && cr === "p2-after-log") {
            s.text = "P2 force-logs prepared and takes its locks, then crashes before the reply leaves. It is now bound by a vote nobody heard.";
            crash(s, "P2", 40); vote.P2 = null; continue;
          }
          s.text = p + " force-logs prepared to its write-ahead log, keeps its locks, and only then replies YES. From now on it may not abort or commit on its own.";
          msg(s, p, "C", "YES", "green", 1); vote[p] = "YES";
          if (p === "P2" && cr === "p2-after-vote") {
            s.text += " Then P2 crashes.";
            crash(s, "P2", 40);
          }
        }
        if (i === 0 && cr === "c-mid-prepare") {
          s.text += " Then the coordinator crashes: P2 and P3 never hear about the transaction.";
          crash(s, "C", 40); break;
        }
      }
    }

    /* ---- decision */
    if (alive.C) {
      var missing = P.filter(function (q) { return vote[q] === null || vote[q] === undefined; });
      var allYes = P.every(function (q) { return vote[q] === "YES"; });
      decision = allYes ? "COMMIT" : "ABORT";
      var sd;
      if (cr === "c-votes-in") {
        sd = step("The coordinator has every vote and crashes before writing the decision anywhere. The participants are all in doubt.");
        crash(sd, "C", 24);
      } else {
        if (allYes) {
          sd = step("All votes are YES. The coordinator force-logs COMMIT. That single disk write is the commit point: from here the transaction WILL commit, whatever crashes.");
          cLog(sd, "COMMIT", 24, "force"); sd.items.push({ k: "mark", label: "commit point", dy: 24 });
        } else {
          sd = step((missing.length ? missing.join(", ") + " did not answer: the coordinator times out and counts that as NO. " : "A participant voted NO. ") +
            "The decision is ABORT. Under presumed abort the coordinator writes nothing: no record means abort.");
        }
        if (cr === "c-logged") { sd.text += " Then the coordinator crashes before telling anyone."; crash(sd, "C", 40); }
      }
    }

    /* ---- phase 2 */
    if (alive.C) {
      var ackMissing = false;   /* a COMMIT whose ACK never arrives: the coordinator must not forget it */
      for (var j = 0; j < P.length; j++) {
        var q = P[j];
        if (decision === "ABORT" && vote[q] === "NO") continue;
        var d = decision.toLowerCase(), col = decision === "COMMIT" ? "blue" : "red", st = step("");
        if (!alive[q]) {
          st.text = q + " is down, so the " + decision + " message is lost. " + q + " will have to ask when it comes back.";
          msg(st, "C", q, decision, col, 0, true); if (decision === "COMMIT") ackMissing = true; continue;
        }
        msg(st, "C", q, decision, col, 0);
        if (q === "P2" && cr === "p2-after-decision" && decision === "COMMIT") {
          st.text = "P2 receives COMMIT and crashes before writing it to its log. Its locks vanish with its memory, but its log still says prepared.";
          crash(st, "P2", 34); ackMissing = true; continue;
        }
        log(st, q, d, 24); lock(st, q, false, 24); decided[q] = d;
        st.text = q + " logs " + d + ", releases its locks and acknowledges.";
        if (j === 0 && cr === "c-mid-decision") {
          st.text = q + " logs " + d + " and releases its locks. Its ACK is lost because the coordinator crashes right after sending only this one message.";
          msg(st, q, "C", "ACK", "green", 1, true); crash(st, "C", 8);
          break;
        }
        msg(st, q, "C", "ACK", "green", 1);
      }
      if (alive.C && ackMissing) {
        step("Not every ACK has arrived, so the coordinator keeps its COMMIT record and does not forget the transaction: the missing participant will have to ask, and must be told COMMIT.");
      } else if (alive.C) {
        var se = step("Every ACK is in. The coordinator writes a non-forced end record and forgets the transaction. If the transaction had left no stuck participant, it is finished.");
        cLog(se, "end", 24);
      }
    }

    /* ---- recovery */
    if (crashed && !cfg.leaveDown) {
      var sr = step(crashed === "C" ? "The coordinator restarts and reads its log." : crashed + " restarts and reads its log.");
      restart(sr, crashed, 24);
      var cAnswer = clog.indexOf("COMMIT") >= 0 ? "COMMIT" : "ABORT";
      if (crashed === "C") {
        sr.text += clog.indexOf("COMMIT") >= 0
          ? " It finds COMMIT and no end record: the decision was made, so it will answer COMMIT to anyone who asks."
          : " It finds no commit record. Presumed abort: it will answer ABORT to anyone who asks.";
      } else if (!prepared[crashed]) {
        sr.text += " There is no prepared record, so it never promised anything and may abort on its own.";
      } else {
        sr.text += " It finds prepared with no decision: it is IN DOUBT. It re-takes its locks and must ask the coordinator.";
        lock(sr, crashed, true, 24);
      }
      P.forEach(function (q) {
        if (!alive[q] || !prepared[q] || decided[q]) return;
        var sq = step(q + " is in doubt and asks the coordinator: INQUIRE. The coordinator answers " + cAnswer +
          (cAnswer === "ABORT" && clog.indexOf("COMMIT") < 0 ? " (no record, so presumed abort)" : "") + ".");
        msg(sq, q, "C", "INQUIRE", "blue", 0);
        msg(sq, "C", q, cAnswer, cAnswer === "COMMIT" ? "green" : "red", 1);
        log(sq, q, cAnswer.toLowerCase(), 50); lock(sq, q, false, 50); decided[q] = cAnswer.toLowerCase();
      });
    } else if (crashed && cfg.leaveDown) {
      S.push({ text: crashed === "C"
        ? "The coordinator stays down. Anyone who voted YES is stuck: it cannot commit (the coordinator may have decided abort) and it cannot abort (the coordinator may have decided commit). The locks stay held until the coordinator returns."
        : crashed + " stays down. The others have finished, but its locks and its in-doubt state wait on its restart.", items: [] });
    }
    return S;
  }

  /* ------------------------------------------------------------------ replay + draw */
  var cfg = { crash: "c-votes-in", p3yes: true, leaveDown: false };
  var steps = [], k = 0;

  function replay(upTo) {
    var st = { log: { C: [], P1: [], P2: [], P3: [] }, locked: { P1: 0, P2: 0, P3: 0 }, down: { C: 0, P1: 0, P2: 0, P3: 0 }, prepared: {}, decided: {} };
    for (var i = 0; i < upTo; i++) steps[i].items.forEach(function (it) {
      if (it.k === "log") { st.log[it.n].push(it.text); if (it.text === "prepared") st.prepared[it.n] = 1; if (it.text === "commit" || it.text === "abort") st.decided[it.n] = it.text; }
      if (it.k === "lock") st.locked[it.n] = it.on ? 1 : 0;
      if (it.k === "crash") st.down[it.n] = 1;
      if (it.k === "restart") st.down[it.n] = 0;
    });
    return st;
  }

  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }

  function svgHTML() {
    var n = steps.length, H = TOP + ROW * Math.max(n, 1) + 16, out = [];
    out.push('<svg viewBox="0 0 ' + W + " " + H + '" role="img" aria-label="Space-time diagram of the two-phase commit run so far. Time runs downward; each vertical line is one node.">');
    out.push('<defs>' + [["a", "blue"], ["b", "green"], ["c", "red"]].map(function (m) {
      return '<marker id="ahX13s' + m[0] + '" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" class="f-' + m[1] + '"/></marker>';
    }).join("") + "</defs>");
    ["C"].concat(P).forEach(function (nd) {
      var col = nd === "C" ? "purple" : "blue", x = LANE_X[nd];
      out.push('<line x1="' + x + '" y1="' + (TOP - 4) + '" x2="' + x + '" y2="' + (H - 8) + '" class="line-thin"/>');
      out.push('<rect x="' + (x - 48) + '" y="6" width="96" height="30" rx="7" class="fs-' + col + " s-" + col + ' sw-2"/>');
      out.push('<text x="' + x + '" y="25" text-anchor="middle" class="t-sm t-bold">' + (nd === "C" ? "Coordinator" : nd) + "</text>");
    });
    if (k > 0) out.push('<rect x="2" y="' + (TOP + (k - 1) * ROW) + '" width="' + (W - 4) + '" height="' + ROW + '" rx="6" style="fill:var(--surface-2);opacity:.55"/>');
    /* lock and down intervals, row by row */
    var lockOn = { P1: null, P2: null, P3: null }, downFrom = { C: null, P1: null, P2: null, P3: null };
    var cDown = false, segs = [];
    function yOf(i, dy) { return TOP + i * ROW + dy; }
    for (var i = 0; i < k; i++) {
      var items = steps[i].items;
      items.forEach(function (it) {
        if (it.k === "lock") {
          if (it.on && lockOn[it.n] === null) lockOn[it.n] = yOf(i, it.dy);
          if (!it.on && lockOn[it.n] !== null) { segs.push([it.n, lockOn[it.n], yOf(i, it.dy)]); lockOn[it.n] = null; }
        }
        if (it.k === "crash") downFrom[it.n] = yOf(i, it.dy);
        if (it.k === "restart" && downFrom[it.n] !== null) {
          out.push('<line x1="' + LANE_X[it.n] + '" y1="' + downFrom[it.n] + '" x2="' + LANE_X[it.n] + '" y2="' + yOf(i, it.dy) + '" class="line-dash s-red"/>');
          downFrom[it.n] = null;
        }
      });
    }
    var yEnd = TOP + k * ROW;
    Object.keys(downFrom).forEach(function (nd) { if (downFrom[nd] !== null) out.push('<line x1="' + LANE_X[nd] + '" y1="' + downFrom[nd] + '" x2="' + LANE_X[nd] + '" y2="' + yEnd + '" class="line-dash s-red"/>'); });
    Object.keys(lockOn).forEach(function (nd) { if (lockOn[nd] !== null) segs.push([nd, lockOn[nd], yEnd]); });
    /* when the coordinator is down, a held lock is drawn red (blocked) */
    var cDownRanges = [], cs = null;
    for (var r = 0; r < k; r++) steps[r].items.forEach(function (it) {
      if (it.k === "crash" && it.n === "C") cs = yOf(r, it.dy);
      if (it.k === "restart" && it.n === "C" && cs !== null) { cDownRanges.push([cs, yOf(r, it.dy)]); cs = null; }
    });
    if (cs !== null) cDownRanges.push([cs, yEnd]);
    segs.forEach(function (sg) {
      var x = LANE_X[sg[0]] + 0, a = sg[1], b = sg[2];
      out.push('<line x1="' + x + '" y1="' + a + '" x2="' + x + '" y2="' + b + '" class="s-yellow" style="stroke-width:7;opacity:.5"/>');
      cDownRanges.forEach(function (rg) {
        var lo = Math.max(a, rg[0]), hi = Math.min(b, rg[1]);
        if (hi > lo) out.push('<line x1="' + x + '" y1="' + lo + '" x2="' + x + '" y2="' + hi + '" class="s-red" style="stroke-width:7;opacity:.75"/>');
      });
    });
    /* items */
    for (var q = 0; q < k; q++) steps[q].items.forEach(function (it) {
      var cur = q === k - 1;
      if (it.k === "msg") {
        var y1 = TOP + q * ROW + (it.half ? 30 : 4), y2 = TOP + q * ROW + (it.half ? 50 : 24);
        var x1 = LANE_X[it.from], x2 = LANE_X[it.to], mk = { blue: "a", green: "b", red: "c" }[it.color];
        if (it.lost) {
          var xe = x1 + (x2 - x1) * 0.6, ye = y1 + (y2 - y1) * 0.6;
          out.push('<line x1="' + x1 + '" y1="' + y1 + '" x2="' + xe.toFixed(1) + '" y2="' + ye.toFixed(1) + '" class="line-dash s-red"/>');
          out.push('<path d="M' + (xe - 5).toFixed(1) + "," + (ye - 5).toFixed(1) + " L" + (xe + 5).toFixed(1) + "," + (ye + 5).toFixed(1) + " M" + (xe + 5).toFixed(1) + "," + (ye - 5).toFixed(1) + " L" + (xe - 5).toFixed(1) + "," + (ye + 5).toFixed(1) + '" class="s-red sw-2" fill="none"/>');
        } else out.push('<line x1="' + x1 + '" y1="' + y1 + '" x2="' + x2 + '" y2="' + y2 + '" class="line s-' + it.color + '" marker-end="url(#ahX13s' + mk + ')"/>');
        var mx = (x1 + x2) / 2, my = (y1 + y2) / 2 - 4;
        out.push('<text x="' + mx.toFixed(1) + '" y="' + my.toFixed(1) + '" text-anchor="middle" class="t-xs tc-' + it.color + (cur ? " t-bold" : "") + '" style="paint-order:stroke;stroke:var(--bg);stroke-width:4px">' + it.label + "</text>");
      } else if (it.k === "log") {
        var lx = LANE_X[it.n], ly = TOP + q * ROW + it.dy, w = it.text.length * 6.4 + 12;
        var right = lx + 8 + w > W - 2;
        var bx = right ? lx - 8 - w : lx + 8;
        out.push('<rect x="' + bx + '" y="' + (ly - 9) + '" width="' + w + '" height="18" rx="4" class="fs-orange s-orange"/>');
        out.push('<text x="' + (bx + w / 2) + '" y="' + (ly + 4) + '" text-anchor="middle" class="t-xs">' + it.text + "</text>");
        out.push('<circle cx="' + lx + '" cy="' + ly + '" r="4" class="f-orange"/>');
      } else if (it.k === "crash") {
        var cx = LANE_X[it.n], cy = TOP + q * ROW + it.dy;
        out.push('<path d="M' + (cx - 7) + "," + (cy - 7) + " L" + (cx + 7) + "," + (cy + 7) + " M" + (cx + 7) + "," + (cy - 7) + " L" + (cx - 7) + "," + (cy + 7) + '" class="s-red sw-3" fill="none"/>');
      } else if (it.k === "restart") {
        out.push('<circle cx="' + LANE_X[it.n] + '" cy="' + (TOP + q * ROW + it.dy) + '" r="5" class="f-green"/>');
      } else if (it.k === "mark") {
        var my2 = TOP + q * ROW + it.dy;
        out.push('<line x1="' + (LANE_X.C + 10) + '" y1="' + my2 + '" x2="' + (W - 6) + '" y2="' + my2 + '" class="line-dash s-yellow"/>');
        out.push('<text x="' + (W - 8) + '" y="' + (my2 - 4) + '" text-anchor="end" class="t-xs tc-yellow t-bold">' + it.label + "</text>");
      }
    });
    out.push("</svg>");
    return out.join("");
  }

  /* ------------------------------------------------------------------ UI */
  var head = el("div", "widget-head");
  head.appendChild(el("span", "widget-tag", "Simulator"));
  head.appendChild(el("h4", "widget-title", "Two-phase commit with a crash of your choice"));
  root.appendChild(head);
  root.appendChild(el("p", "widget-help", "Time runs down the page. Pick where something crashes, press Step, and watch the logs and locks. Yellow bars are held locks; they turn red when the coordinator is down and the participant is stuck."));

  var row1 = el("div", "widget-row tp-controls");
  function field(label, node) { var l = el("label", "tp-field"); l.appendChild(el("span", "tp-lab", label)); l.appendChild(node); return l; }
  var selCrash = el("select"); CRASHES.forEach(function (c) { var o = el("option", null, c[1]); o.value = c[0]; selCrash.appendChild(o); }); selCrash.value = cfg.crash;
  var selVote = el("select"); [["yes", "P3 votes YES"], ["no", "P3 votes NO"]].forEach(function (c) { var o = el("option", null, c[1]); o.value = c[0]; selVote.appendChild(o); });
  var chkDown = el("input"); chkDown.type = "checkbox";
  var lblDown = el("label", "tp-check"); lblDown.appendChild(chkDown); lblDown.appendChild(el("span", null, " Never restart the crashed node"));
  row1.appendChild(field("Crash point", selCrash)); row1.appendChild(field("Vote", selVote)); row1.appendChild(lblDown);
  root.appendChild(row1);

  var row2 = el("div", "widget-row");
  var bBack = el("button", "btn small", "Back"), bStep = el("button", "btn small primary", "Step"), bRun = el("button", "btn small", "Run to end"), bReset = el("button", "btn small", "Reset");
  [bBack, bStep, bRun, bReset].forEach(function (b) { b.type = "button"; row2.appendChild(b); });
  var count = el("span", "tp-count"); row2.appendChild(count);
  root.appendChild(row2);

  var holder = el("div", "tp-svg"); root.appendChild(holder);
  var status = el("div", "widget-out tp-status"); status.setAttribute("aria-live", "polite"); root.appendChild(status);
  var cards = el("div", "tp-cards"); root.appendChild(cards);

  function nodeStatus(nd, st) {
    if (st.down[nd]) return ["down", "bad"];
    if (nd === "C") {
      if (st.log.C.indexOf("end") >= 0) return ["finished (end record)", "good"];
      if (st.log.C.indexOf("COMMIT") >= 0) return ["decided COMMIT", "good"];
      return ["running", ""];
    }
    if (st.decided[nd]) return [st.decided[nd] === "commit" ? "committed" : "aborted", "good"];
    if (st.prepared[nd]) return [st.down.C ? "BLOCKED: in doubt, locks held" : "prepared, waiting for the decision", st.down.C ? "bad" : "warn"];
    return ["no promise made", ""];
  }

  function draw() {
    holder.innerHTML = svgHTML();
    var st = replay(k);
    count.textContent = "step " + k + " / " + steps.length;
    bBack.disabled = k === 0; bStep.disabled = k >= steps.length; bRun.disabled = k >= steps.length;
    var text = k === 0 ? "Press Step to begin. The coordinator will ask all three participants to prepare." : steps[k - 1].text;
    if (k === steps.length && k > 0) {
      var stuck = P.filter(function (p) { return st.prepared[p] && !st.decided[p]; });
      var kinds = {}; P.forEach(function (p) { if (st.decided[p]) kinds[st.decided[p]] = 1; });
      var ks = Object.keys(kinds);
      text += stuck.length ? "  End state: " + stuck.join(", ") + " still in doubt and holding locks." : "  End state: " + (ks.length ? "every participant that prepared agrees on " + ks[0].toUpperCase() + "." : "nothing was committed and nothing is stuck.");
    }
    status.textContent = text;
    cards.innerHTML = "";
    ["C"].concat(P).forEach(function (nd) {
      var c = el("div", "tp-card"), s = nodeStatus(nd, st);
      c.classList.add(s[1] || "plain");
      c.appendChild(el("div", "tp-card-h", NAMES[nd]));
      c.appendChild(el("div", "tp-card-l", "log: " + (st.log[nd].length ? st.log[nd].join(", ") : "empty")));
      if (nd !== "C") c.appendChild(el("div", "tp-card-l", "locks: " + (st.locked[nd] ? "HELD" : "free")));
      c.appendChild(el("div", "tp-card-s", s[0]));
      cards.appendChild(c);
    });
  }

  function rebuild() {
    cfg.crash = selCrash.value; cfg.p3yes = selVote.value === "yes"; cfg.leaveDown = chkDown.checked;
    steps = simulate(cfg); k = 0; draw();
  }
  selCrash.addEventListener("change", rebuild); selVote.addEventListener("change", rebuild); chkDown.addEventListener("change", rebuild);
  bStep.addEventListener("click", function () { if (k < steps.length) { k++; draw(); } });
  bBack.addEventListener("click", function () { if (k > 0) { k--; draw(); } });
  bRun.addEventListener("click", function () { k = steps.length; draw(); });
  bReset.addEventListener("click", function () { k = 0; draw(); });
  rebuild();
})();
