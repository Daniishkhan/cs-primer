/* Single-decree Paxos simulator (distributed chapter 09).

   Two proposers, P1 (wants value X) and P2 (wants value Y), and three acceptors A1..A3.
   Every message sits in an "in flight" list. The reader decides, message by message, whether
   it is delivered or dropped, and in which order, so the reader IS the unreliable network.

   Rules implemented (the textbook ones):
     acceptor  on prepare(n):   if n > promised: promised = n, reply promise(n, accepted pair or none)
     acceptor  on accept(n,v):  if n >= promised: promised = n, accepted = (n,v), reply accepted(n,v)
     proposer  on majority of promises for its current ballot:
                 if any promise carried an accepted pair, propose the value of the HIGHEST-numbered pair
                 (the "adoption rule"); otherwise propose its own value.
   A value is CHOSEN the moment a majority of acceptors have accepted the same ballot. The widget
   watches for that omnisciently (no node can see it) and shouts if two different values are chosen.

   A checkbox switches the adoption rule off, which is the broken variant the chapter discusses.
   Ballot numbers are (round, proposer id), shown as "1.P1"; compared as round*10 + id.
   Three presets script the interesting runs; each "Next step" performs one scripted step.
   Not modelled: acceptors crashing and restarting (their state is assumed durable), timeouts. */
(function () {
  "use strict";
  var root = document.getElementById("paxos-sim");
  if (!root) return;

  var ACC = ["A1", "A2", "A3"], MAJ = 2;
  var VALUE = { 1: "X", 2: "Y" };
  var S = null;                 // simulation state
  var adopt = true;
  var script = null, scriptIdx = 0, presetName = "";

  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function btn(label, cls, fn) { var b = el("button", "btn " + (cls || ""), label); b.type = "button"; b.addEventListener("click", fn); return b; }

  function B(n) { return n ? Math.floor(n / 10) + ".P" + (n % 10) : "none"; }
  function fresh() {
    return {
      acc: { A1: { p: 0, an: 0, av: null }, A2: { p: 0, an: 0, av: null }, A3: { p: 0, an: 0, av: null } },
      prop: { P1: { id: 1, round: 0, n: 0, phase: "idle", promises: {}, accepts: {}, sent: false, decided: null },
              P2: { id: 2, round: 0, n: 0, phase: "idle", promises: {}, accepts: {}, sent: false, decided: null } },
      msgs: [], nextId: 1, log: [], accBy: {}, chosen: {}
    };
  }
  function say(t, cls) { S.log.push({ t: t, cls: cls || "" }); }

  function describe(m) {
    if (m.type === "prepare") return "prepare(" + B(m.n) + ")";
    if (m.type === "promise") return "promise(" + B(m.n) + ", accepted " + (m.an ? "(" + B(m.an) + ", " + m.av + ")" : "none") + ")";
    if (m.type === "accept") return "accept(" + B(m.n) + ", " + m.v + ")";
    return "accepted(" + B(m.n) + ", " + m.v + ")";
  }
  function send(from, to, type, f) {
    var m = { id: S.nextId++, from: from, to: to, type: type, n: 0, an: 0, av: null, v: null };
    for (var k in f) m[k] = f[k];
    S.msgs.push(m);
  }

  /* ---------- protocol actions ---------- */
  function startProposer(name) {
    var p = S.prop[name];
    p.round++; p.n = p.round * 10 + p.id;
    p.phase = "prepare"; p.promises = {}; p.accepts = {}; p.sent = false;
    say(name + " starts ballot " + B(p.n) + " (wants " + VALUE[p.id] + "): sends prepare to all three acceptors.", "p1");
    ACC.forEach(function (a) { send(name, a, "prepare", { n: p.n }); });
  }

  function checkChosen(n, v) {
    var key = n + "|" + v, set = S.accBy[key] || (S.accBy[key] = {});
    var count = Object.keys(set).length;
    if (count >= MAJ && !S.chosen[v]) {
      S.chosen[v] = n;
      say("Value " + v + " is now CHOSEN: a majority of acceptors accepted it at ballot " + B(n) + ". (No single node can see this directly.)", "chosen");
      if (Object.keys(S.chosen).length > 1) say("SAFETY VIOLATION: two different values have been chosen.", "bad");
    }
  }

  function handle(m) {
    var a, p;
    if (m.type === "prepare") {
      a = S.acc[m.to];
      if (m.n > a.p) {
        a.p = m.n;
        say(m.to + " promises not to accept ballots below " + B(m.n) + (a.an ? "; it reports it already accepted (" + B(a.an) + ", " + a.av + ")." : "; nothing accepted yet."));
        send(m.to, m.from, "promise", { n: m.n, an: a.an, av: a.av });
      } else {
        say(m.to + " ignores prepare(" + B(m.n) + "): it already promised " + B(a.p) + ".", "warn");
      }
    } else if (m.type === "accept") {
      a = S.acc[m.to];
      if (m.n >= a.p) {
        a.p = m.n; a.an = m.n; a.av = m.v;
        say(m.to + " accepts (" + B(m.n) + ", " + m.v + ").");
        (S.accBy[m.n + "|" + m.v] = S.accBy[m.n + "|" + m.v] || {})[m.to] = true;
        send(m.to, m.from, "accepted", { n: m.n, v: m.v });
        checkChosen(m.n, m.v);
      } else {
        say(m.to + " rejects accept(" + B(m.n) + ", " + m.v + "): it promised " + B(a.p) + " and will not go backwards.", "warn");
      }
    } else if (m.type === "promise") {
      p = S.prop[m.to];
      if (p.n === m.n && p.phase !== "prepare") { say(m.from + "'s promise reaches " + m.to + ", which already has a majority and has moved to phase 2: nothing more to do."); return; }
      if (p.n !== m.n) { say(m.to + " ignores a promise for an old ballot (" + B(m.n) + ").", "warn"); return; }
      p.promises[m.from] = { an: m.an, av: m.av };
      if (Object.keys(p.promises).length >= MAJ && !p.sent) {
        p.sent = true; p.phase = "accept";
        var best = null, k;
        for (k in p.promises) if (p.promises[k].an && (!best || p.promises[k].an > best.an)) best = p.promises[k];
        var v = VALUE[p.id];
        if (best && adopt) { v = best.av; say(m.to + " has a majority of promises. One reports an accepted value, so it must propose " + v + " (from ballot " + B(best.an) + "), not its own " + VALUE[p.id] + ".", "p1"); }
        else if (best) { say(m.to + " has a majority of promises. It SKIPS the adoption rule and proposes its own " + v + ", ignoring the accepted value " + best.av + " it was just told about.", "bad"); }
        else { say(m.to + " has a majority of promises and none reports an accepted value, so it is free to propose its own " + v + ".", "p1"); }
        p.value = v;
        ACC.forEach(function (x) { send(m.to, x, "accept", { n: p.n, v: v }); });
      } else {
        say(m.to + " now holds " + Object.keys(p.promises).length + " promise(s) for " + B(p.n) + ".");
      }
    } else if (m.type === "accepted") {
      p = S.prop[m.to];
      if (p.n !== m.n) { say(m.to + " ignores an accepted reply for an old ballot.", "warn"); return; }
      p.accepts[m.from] = true;
      if (Object.keys(p.accepts).length >= MAJ && !p.decided) {
        p.decided = m.v; p.phase = "done";
        say(m.to + " has accepted-replies from a majority: it now KNOWS " + m.v + " is chosen.", "chosen");
      }
    }
  }

  function deliver(id) {
    for (var i = 0; i < S.msgs.length; i++) if (S.msgs[i].id === id) { var m = S.msgs.splice(i, 1)[0]; handle(m); return true; }
    return false;
  }
  function drop(id) {
    for (var i = 0; i < S.msgs.length; i++) if (S.msgs[i].id === id) {
      var m = S.msgs.splice(i, 1)[0];
      say("Dropped: " + m.from + " to " + m.to + " " + describe(m) + ".", "warn"); return;
    }
  }
  /* act on all messages matching a filter: from (name), to (array or null), type */
  function matching(type, from, tos) {
    return S.msgs.filter(function (m) {
      return m.type === type && (!from || m.from === from) && (!tos || tos.indexOf(m.to) >= 0);
    });
  }
  function doDeliver(type, from, tos) { matching(type, from, tos).forEach(function (m) { deliver(m.id); }); }
  function doDrop(type, from, tos) { matching(type, from, tos).forEach(function (m) { drop(m.id); }); }
  /* promises/accepted travel back to a named proposer from acceptors */
  function toP(type, p, froms) {
    S.msgs.filter(function (m) { return m.type === type && m.to === p && (!froms || froms.indexOf(m.from) >= 0); })
      .forEach(function (m) { deliver(m.id); });
  }

  /* ---------- presets ---------- */
  var PRESETS = {
    happy: {
      label: "1. Happy path",
      steps: [
        ["P1 starts a ballot and sends prepare to everyone.", function () { startProposer("P1"); }],
        ["All three prepares arrive; each acceptor promises.", function () { doDeliver("prepare", "P1"); }],
        ["The promises arrive back. After the second one P1 has a majority, nobody has accepted anything, so it proposes its own X.", function () { toP("promise", "P1"); }],
        ["The accept messages arrive; each acceptor accepts (1.P1, X). Two acceptances are enough: X is chosen.", function () { doDeliver("accept", "P1"); }],
        ["The accepted replies reach P1, which now knows the outcome.", function () { toP("accepted", "P1"); }]
      ]
    },
    overwrite: {
      label: "2. A value is chosen, then a rival arrives",
      steps: [
        ["P1 starts ballot 1.P1.", function () { startProposer("P1"); }],
        ["Prepares reach A1 and A2; the one to A3 is dropped.", function () { doDeliver("prepare", "P1", ["A1", "A2"]); doDrop("prepare", "P1", ["A3"]); }],
        ["A1 and A2 promise; P1 has a majority with no prior value and sends accept(1.P1, X) to all.", function () { toP("promise", "P1"); }],
        ["The accepts reach A1 and A2 and are dropped on the way to A3. A majority accepted X: X is CHOSEN, though no proposer knows yet.", function () { doDeliver("accept", "P1", ["A1", "A2"]); doDrop("accept", "P1", ["A3"]); }],
        ["P1's accepted replies are dropped too (the network is having a bad day). Nobody has been told.", function () { doDrop("accepted", "P1"); }],
        ["Now P2 wakes up, wanting Y, and starts ballot 1.P2 (which is higher than 1.P1).", function () { startProposer("P2"); }],
        ["P2's prepare reaches A2 and A3 (the one to A1 is dropped). A2 will report it accepted (1.P1, X).", function () { doDeliver("prepare", "P2", ["A2", "A3"]); doDrop("prepare", "P2", ["A1"]); }],
        ["The promises reach P2. Watch the log: with the adoption rule on, P2 must propose X. Switch the box off and reset to see it propose Y.", function () { toP("promise", "P2"); }],
        ["P2's accepts reach A2 and A3 (A1's is dropped). Compare the verdict banner with the adoption box on and off.", function () { doDeliver("accept", "P2", ["A2", "A3"]); doDrop("accept", "P2", ["A1"]); }]
      ]
    },
    duel: {
      label: "3. Duelling proposers",
      steps: [
        ["P1 starts ballot 1.P1 and its prepares are delivered; every acceptor promises.", function () { startProposer("P1"); doDeliver("prepare", "P1"); }],
        ["The promises reach P1, which sends accept(1.P1, X) to all. They are now in flight.", function () { toP("promise", "P1"); }],
        ["Before they land, P2 starts the higher ballot 1.P2 and its prepares are delivered. Every acceptor now promises 1.P2.", function () { startProposer("P2"); doDeliver("prepare", "P2"); }],
        ["P1's accepts finally arrive and are all rejected: the acceptors promised a higher ballot. P1 wasted its phase 2.", function () { doDeliver("accept", "P1"); }],
        ["P2's promises reach it and it sends accept(1.P2, Y). In flight again.", function () { toP("promise", "P2"); }],
        ["P1 notices the failure and retries with ballot 2.P1, higher than 1.P2. Its prepares and promises are delivered.", function () { startProposer("P1"); doDeliver("prepare", "P1"); toP("promise", "P1"); }],
        ["P2's accepts finally arrive: rejected, since the acceptors promised 2.P1. Round for round, each proposer kills the other's phase 2.", function () { doDeliver("accept", "P2"); }],
        ["P2 retries with 2.P2. If P1 does the same again, this repeats forever. Nobody is crashed, yet nothing is chosen: that is livelock. (Try finishing a round yourself with the buttons.)", function () { startProposer("P2"); doDeliver("prepare", "P2"); toP("promise", "P2"); }]
      ]
    }
  };

  /* ---------- UI ---------- */
  root.textContent = "";
  var head = el("div", "widget-head");
  head.appendChild(el("span", "widget-tag", "Simulator"));
  head.appendChild(el("h4", "widget-title", "Be the unreliable network"));
  root.appendChild(head);
  root.appendChild(el("p", "widget-help", "Two proposers want different values (P1: X, P2: Y). Three acceptors. Every message waits in the in-flight list until you deliver or drop it, in any order. Press a preset to get a scripted story, then Next step, or ignore the scripts and play freely."));

  var ctrl1 = el("div", "px-row");
  ctrl1.appendChild(btn("Start P1 (X)", "small", function () { startProposer("P1"); render(); }));
  ctrl1.appendChild(btn("Start P2 (Y)", "small", function () { startProposer("P2"); render(); }));
  var adoptWrap = el("label", "px-check");
  var adoptBox = el("input"); adoptBox.type = "checkbox"; adoptBox.checked = true;
  adoptBox.addEventListener("change", function () { adopt = adoptBox.checked; say(adopt ? "Adoption rule switched ON (correct Paxos)." : "Adoption rule switched OFF: proposers ignore previously accepted values. This is the broken variant.", adopt ? "" : "bad"); render(); });
  adoptWrap.appendChild(adoptBox);
  adoptWrap.appendChild(el("span", null, "Adoption rule on (propose the highest accepted value)"));
  ctrl1.appendChild(adoptWrap);
  ctrl1.appendChild(btn("Deliver all, oldest first", "small", function () { var n = 0; while (S.msgs.length && n++ < 60) deliver(S.msgs[0].id); render(); }));
  ctrl1.appendChild(btn("Reset", "small", function () { resetAll(); render(); }));
  root.appendChild(ctrl1);

  var ctrl2 = el("div", "px-row");
  ctrl2.appendChild(el("span", "px-lab", "Scripted stories:"));
  var presetBtns = {};
  Object.keys(PRESETS).forEach(function (k) {
    var b = btn(PRESETS[k].label, "small", function () { loadPreset(k); });
    presetBtns[k] = b; ctrl2.appendChild(b);
  });
  var nextBtn = btn("Next step", "primary small", function () { nextStep(); });
  ctrl2.appendChild(nextBtn);
  root.appendChild(ctrl2);

  var storyBox = el("div", "px-story"); storyBox.setAttribute("role", "status");
  root.appendChild(storyBox);

  var nodesBox = el("div", "px-nodes");
  root.appendChild(nodesBox);
  var verdict = el("div", "px-verdict"); verdict.setAttribute("role", "status");
  root.appendChild(verdict);
  root.appendChild(el("div", "px-h", "Messages in flight"));
  var flight = el("div", "px-flight");
  root.appendChild(flight);
  root.appendChild(el("div", "px-h", "What happened (newest first)"));
  var logBox = el("ol", "px-log");
  logBox.setAttribute("aria-live", "polite");
  root.appendChild(logBox);

  function resetAll() { S = fresh(); script = null; scriptIdx = 0; presetName = ""; storyBox.textContent = ""; }
  function loadPreset(k) {
    resetAll();
    if (k === "overwrite") { adopt = true; adoptBox.checked = true; }
    script = PRESETS[k].steps; presetName = PRESETS[k].label;
    say("Loaded story: " + presetName + ". Press Next step.");
    render();
  }
  function nextStep() {
    if (!script) { loadPreset("happy"); return; }
    if (scriptIdx >= script.length) return;
    script[scriptIdx][1]();
    scriptIdx++;
    render();
  }

  function nodeCard(name, lines, cls) {
    var c = el("div", "px-node " + cls);
    c.appendChild(el("div", "px-node-t", name));
    lines.forEach(function (l) { c.appendChild(el("div", "px-node-l", l)); });
    return c;
  }

  function render() {
    var i, k;
    /* story caption */
    if (script) {
      var done = scriptIdx >= script.length;
      storyBox.textContent = presetName + ": " + (done ? "end of script. Keep playing, or pick another story."
        : "step " + (scriptIdx + 1) + " of " + script.length + " is next. " + script[scriptIdx][0]);
    } else storyBox.textContent = "Free play. Start a proposer, then deliver or drop its messages.";
    nextBtn.disabled = !!(script && scriptIdx >= script.length);
    nextBtn.textContent = script ? "Next step" : "Start a story";

    /* nodes */
    nodesBox.textContent = "";
    ["P1", "P2"].forEach(function (name) {
      var p = S.prop[name];
      var promisesStr = Object.keys(p.promises).length + " / 3";
      nodesBox.appendChild(nodeCard(name + " (wants " + VALUE[p.id] + ")", [
        "ballot: " + (p.n ? B(p.n) : "not started"),
        "phase: " + p.phase,
        p.phase === "idle" ? "" : "promises: " + promisesStr + "  accepted-replies: " + Object.keys(p.accepts).length + " / 3",
        p.sent ? "proposing: " + p.value : "",
        p.decided ? "knows chosen: " + p.decided : ""
      ].filter(Boolean), "px-prop"));
    });
    ACC.forEach(function (name) {
      var a = S.acc[name];
      nodesBox.appendChild(nodeCard(name, [
        "promised: " + B(a.p),
        "accepted: " + (a.an ? "(" + B(a.an) + ", " + a.av + ")" : "nothing")
      ], "px-acc"));
    });

    /* verdict */
    var ch = Object.keys(S.chosen);
    verdict.className = "px-verdict" + (ch.length > 1 ? " bad" : ch.length === 1 ? " good" : "");
    verdict.textContent = ch.length > 1 ? "SAFETY VIOLATED: both " + ch.join(" and ") + " have been chosen. A decision was overwritten."
      : ch.length === 1 ? "Chosen: " + ch[0] + " (a majority accepted it at ballot " + B(S.chosen[ch[0]]) + "). From now on it can never change."
      : "Nothing chosen yet.";

    /* in flight */
    flight.textContent = "";
    if (!S.msgs.length) flight.appendChild(el("div", "px-empty", "No messages in flight."));
    S.msgs.forEach(function (m) {
      var row = el("div", "px-msg px-t-" + m.type);
      row.appendChild(el("span", "px-msg-t", m.from + " → " + m.to + "  " + describe(m)));
      var bs = el("span", "px-msg-b");
      var d = btn("Deliver", "small", function () { deliver(m.id); render(); });
      d.setAttribute("aria-label", "Deliver " + m.from + " to " + m.to + " " + describe(m));
      var x = btn("Drop", "small danger", function () { drop(m.id); render(); });
      x.setAttribute("aria-label", "Drop " + m.from + " to " + m.to + " " + describe(m));
      bs.appendChild(d); bs.appendChild(x); row.appendChild(bs);
      flight.appendChild(row);
    });

    /* log */
    logBox.textContent = "";
    for (i = S.log.length - 1, k = 0; i >= 0 && k < 40; i--, k++) {
      logBox.appendChild(el("li", "px-l " + S.log[i].cls, S.log[i].t));
    }
    if (!S.log.length) logBox.appendChild(el("li", "px-l", "Nothing yet."));
  }

  S = fresh();
  render();
})();
