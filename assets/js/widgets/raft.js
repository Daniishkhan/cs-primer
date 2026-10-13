/* Raft explainer widgets (chapter 20).
   Two scripted, deterministic step-through simulations:
     #raft-election : five servers in a circle (election, leader crash, split vote)
     #raft-log      : five servers as rows (log replication, commit, leader crash, recovery)
   Each scenario is a list of "frames" authored with a tiny Builder; the widget just
   draws frame N. Nothing is random, so every visitor sees the same story. */
(function () {
  "use strict";
  if (typeof document === "undefined") return;

  var NS = "http://www.w3.org/2000/svg";
  function el(name, attrs, parent) {
    var e = document.createElementNS(NS, name);
    for (var k in attrs) if (Object.prototype.hasOwnProperty.call(attrs, k)) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
  }
  function h(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }

  /* ---------- scenario builder ---------- */

  function Builder(n) {
    this.n = [];
    for (var i = 0; i < n; i++) this.n.push({ role: "F", term: 0, log: [], commit: 0, note: [], votes: 0 });
    this.frames = [];
    this.msgs = [];
  }
  Builder.prototype.set = function (i, props) { Object.assign(this.n[i], props); return this; };
  Builder.prototype.all = function (props, except) {
    for (var i = 0; i < this.n.length; i++) if (!except || except.indexOf(i) === -1) Object.assign(this.n[i], props);
    return this;
  };
  Builder.prototype.msg = function (from, to, kind) { this.msgs.push({ from: from, to: to, kind: kind }); return this; };
  Builder.prototype.snap = function (title, text) {
    this.frames.push({ title: title, text: text, nodes: JSON.parse(JSON.stringify(this.n)), msgs: this.msgs });
    this.msgs = [];
    return this;
  };
  function L(c, t) { return { c: c, t: t }; }

  /* ---------- scenarios: elections ---------- */

  function electionNormal() {
    var b = new Builder(5), i;
    var t1 = [240, 170, 290, 205, 260];
    b.all({}); for (i = 0; i < 5; i++) b.set(i, { note: ["timeout " + t1[i] + " ms"] });
    b.snap("Everyone starts as a follower",
      "Five servers boot up as <strong>followers</strong>. A follower is happy as long as it keeps hearing from a leader. There is no leader yet, so nobody is speaking. Each server has picked a random <strong>election timeout</strong> (here between 150 and 300 ms) and started a countdown.");

    b.set(1, { note: ["TIMER FIRED", "no leader heard"] });
    b.set(0, { note: ["70 ms left"] }).set(2, { note: ["120 ms left"] }).set(3, { note: ["35 ms left"] }).set(4, { note: ["90 ms left"] });
    b.snap("S2's countdown reaches zero first",
      "After 170 ms of silence S2 concludes that there is no working leader. Because the timeouts were <em>randomized</em>, usually exactly one server runs out first, which is the whole point of the randomness.");

    b.set(1, { role: "C", term: 1, votes: 1, note: ["voted for itself", "votes 1 of 5"] });
    b.snap("S2 becomes a candidate",
      "S2 starts an election: it <strong>adds 1 to its term</strong> (0 → 1; terms are Raft's logical clock), changes role to <strong>candidate</strong>, and votes for itself.");

    b.msg(1, 0, "req").msg(1, 2, "req").msg(1, 3, "req").msg(1, 4, "req");
    b.snap("S2 asks everyone for a vote",
      "S2 sends a <code>RequestVote</code> message to every other server: \"I'm a candidate for term 1; here is how up to date my log is.\" (All the logs are empty here, so they are equally up to date.)");

    b.all({ term: 1, note: ["voted for S2"] }, [1]);
    b.set(1, { votes: 5, note: ["votes 5 of 5"] });
    b.msg(0, 1, "grant").msg(2, 1, "grant").msg(3, 1, "grant").msg(4, 1, "grant");
    b.snap("The followers vote yes",
      "Each follower has not yet voted in term 1, and S2's log is at least as up to date as theirs, so each says yes. <strong>A server votes for at most one candidate per term.</strong> S2 now holds 5 of 5 votes; 3 would have been enough.");

    b.set(1, { role: "L", note: ["leader of term 1"] });
    b.all({ note: ["follower of S2"] }, [1]);
    b.snap("S2 wins and becomes the leader",
      "A candidate that collects votes from a <strong>majority</strong> (3 of 5) becomes the leader. Two different candidates can't both win the same term, because their majorities would have to share a voter, and each voter only votes once per term.");

    var t2 = [250, 0, 230, 180, 270];
    b.msg(1, 0, "hb").msg(1, 2, "hb").msg(1, 3, "hb").msg(1, 4, "hb");
    for (i = 0; i < 5; i++) if (i !== 1) b.set(i, { note: ["timer reset", "timeout " + t2[i] + " ms"] });
    b.set(1, { note: ["sending heartbeats", "every ~50 ms"] });
    b.snap("Heartbeats keep the peace",
      "The leader sends <strong>heartbeats</strong> (empty <code>AppendEntries</code> messages) many times per election timeout. Each heartbeat <em>resets</em> the followers' countdowns, so as long as the leader is alive, nobody starts an election.");

    b.set(1, { role: "X", note: ["CRASHED"] });
    b.all({ note: ["no heartbeat…"] }, [1]);
    b.snap("The leader crashes",
      "Now S2 dies. The followers don't get a message saying so; they just stop hearing heartbeats. Their countdowns keep running with nothing to reset them. (This is the \"slow or dead?\" problem of chapter 16: a timeout is the only evidence they have.)");

    b.set(3, { note: ["TIMER FIRED", "(180 ms of silence)"] });
    b.set(0, { note: ["70 ms left"] }).set(2, { note: ["50 ms left"] }).set(4, { note: ["90 ms left"] });
    b.snap("S4's countdown fires first",
      "S4 happened to pick the shortest timeout this round (180 ms), so it notices the silence first.");

    b.set(3, { role: "C", term: 2, votes: 1, note: ["votes 1 of 5"] });
    b.msg(3, 0, "req").msg(3, 2, "req").msg(3, 4, "req").msg(3, 1, "lost");
    b.snap("S4 starts election for term 2",
      "S4 moves to <strong>term 2</strong>, votes for itself and sends <code>RequestVote</code> to everyone. The message to the dead S2 simply vanishes (red, dashed). S4 doesn't wait for S2; it only needs a majority of the original five.");

    b.set(0, { term: 2, note: ["voted for S4"] }).set(2, { term: 2, note: ["voted for S4"] }).set(4, { term: 2, note: ["voted for S4"] });
    b.set(3, { votes: 4, note: ["votes 4 of 5"] });
    b.msg(0, 3, "grant").msg(2, 3, "grant").msg(4, 3, "grant");
    b.snap("Three votes come back",
      "S1, S3 and S5 each had not voted in term 2, so they vote yes. S4 has 4 votes, and it only needed 3. Notice a crashed machine cost us nothing: <strong>3 of 5 is still a majority</strong>.");

    b.set(3, { role: "L", note: ["leader of term 2"] });
    b.all({ note: ["follower of S4"] }, [1, 3]);
    b.msg(3, 0, "hb").msg(3, 2, "hb").msg(3, 4, "hb").msg(3, 1, "lost");
    b.snap("S4 is the new leader",
      "S4 immediately sends heartbeats to assert its leadership, and the cluster is back in business, typically within a few hundred milliseconds of the crash.");

    b.set(1, { role: "L", term: 1, note: ["back online!", "still thinks: leader", "of term 1"] });
    b.msg(1, 3, "hb").msg(3, 1, "deny").msg(1, 0, "hb").msg(0, 1, "deny");
    b.snap("The old leader comes back",
      "S2 comes back with no idea it was replaced. (Picture a long freeze or a network cut-off; a server that truly rebooted would start as a follower, because Raft never remembers being leader across a restart.) It still believes it is the leader of <strong>term 1</strong> and sends a heartbeat. The others reply: \"I'm in term 2. Your term is out of date, rejected.\"");

    b.set(1, { role: "F", term: 2, note: ["saw term 2 →", "steps down"] });
    b.snap("Higher term wins: S2 steps down",
      "The rejection tells S2 about term 2. Raft's rule: <strong>any server that sees a higher term immediately adopts it and becomes a follower.</strong> The old leader can't do any damage, and its stale messages are ignored. Terms act like a logical clock (chapter 17) that settles who is in charge.");
    return b.frames;
  }

  function electionSplit() {
    var b = new Builder(5), i;
    var t = [200, 260, 201, 270, 202];
    for (i = 0; i < 5; i++) b.set(i, { note: ["timeout " + t[i] + " ms"] });
    b.snap("Bad luck with the random timeouts",
      "A fresh cluster again, but this time three servers (S1, S3, S5) happened to pick almost the same timeout: 200, 201 and 202 ms. This is unlikely, but not impossible, and Raft has to cope with it.");

    b.set(0, { role: "C", term: 1, votes: 1, note: ["votes 1 of 5"] })
     .set(2, { role: "C", term: 1, votes: 1, note: ["votes 1 of 5"] })
     .set(4, { role: "C", term: 1, votes: 1, note: ["votes 1 of 5"] });
    b.snap("Three candidates at once",
      "All three time out within 2 ms of each other. Each moves to term 1 and <strong>votes for itself</strong>. Since a server votes only once per term, none of the three will vote for another.");

    b.msg(0, 1, "req").msg(2, 3, "req").msg(4, 0, "req").msg(4, 2, "req");
    b.snap("Requests cross in the air",
      "Each candidate asks the others for votes. S2 happens to hear S1's request first; S4 hears S3's first. S5's requests go to S1 and S3, who are candidates and have already voted for themselves.");

    b.set(1, { term: 1, note: ["voted for S1"] }).set(3, { term: 1, note: ["voted for S3"] });
    b.set(0, { votes: 2, note: ["votes 2 of 5"] }).set(2, { votes: 2, note: ["votes 2 of 5"] }).set(4, { votes: 1, note: ["votes 1 of 5", "refused by S1, S3"] });
    b.msg(1, 0, "grant").msg(3, 2, "grant").msg(0, 4, "deny").msg(2, 4, "deny");
    b.snap("The votes split 2 – 2 – 1",
      "S1 has 2 votes, S3 has 2, S5 has 1. A majority needs 3, so <strong>nobody wins</strong> term 1. That is safe (there is still no leader to disagree with), but nothing is moving forward.");

    b.set(0, { note: ["retry in 290 ms"] }).set(2, { note: ["retry in 170 ms"] }).set(4, { note: ["retry in 240 ms"] });
    b.snap("Everyone waits and picks new random timeouts",
      "Candidates also have an election timeout. When it expires without a result, they will try again. Crucially each one <strong>picks a fresh random value</strong>, so the odds of a tie again are small. Here S3 drew the shortest.");

    b.set(2, { role: "C", term: 2, votes: 1, note: ["votes 1 of 5"] });
    b.msg(2, 0, "req").msg(2, 1, "req").msg(2, 3, "req").msg(2, 4, "req");
    b.snap("S3 tries again in term 2",
      "S3's timer fires first. It moves to term 2 and asks for votes. When S1 and S5 see a request with a <em>higher term</em> than their own, they drop their own candidacy and adopt term 2.");

    b.set(0, { role: "F", term: 2, note: ["voted for S3"] }).set(4, { role: "F", term: 2, note: ["voted for S3"] })
     .set(1, { term: 2, note: ["voted for S3"] }).set(3, { term: 2, note: ["voted for S3"] });
    b.set(2, { role: "L", votes: 5, note: ["leader of term 2"] });
    b.msg(0, 2, "grant").msg(1, 2, "grant").msg(3, 2, "grant").msg(4, 2, "grant");
    b.snap("S3 wins term 2",
      "Everyone grants the vote (nobody had voted in term 2 yet), and S3 becomes the leader. Randomized timeouts turned a deadlock into a one-round delay: the same trick network cards use for backing off after a collision.");
    return b.frames;
  }

  /* ---------- scenario: log replication ---------- */

  function logStory() {
    var b = new Builder(5), i;
    b.all({ term: 1 });
    b.set(0, { role: "L", note: ["client: set x=5"] });
    b.snap("A cluster with a leader",
      "S1 is the leader of term 1; the other four are followers. A client sends the leader a command: <code>set x=5</code>. Every server keeps a <strong>log</strong> (an ordered list of commands) and a <strong>state machine</strong> (the real data, here just a few variables). Nothing is in any log yet.");

    b.set(0, { log: [L("x=5", 1)], note: ["appended to own log", "not committed yet"] });
    b.snap("The leader writes it down first",
      "The leader appends the command to its own log as entry #1, stamped with the current term. It is shown with a <strong>dashed</strong> border: stored, but <em>not committed</em>. The state machine hasn't changed.");

    b.set(0, { note: ["sends AppendEntries", "to all four followers"] });
    b.set(1, { note: ["◀ AppendEntries #1"] }).set(2, { note: ["◀ AppendEntries #1"] }).set(3, { note: ["◀ AppendEntries #1"] }).set(4, { note: ["◀ AppendEntries #1", "(slow link…)"] });
    b.snap("The leader sends it to the followers",
      "The leader sends an <code>AppendEntries</code> message carrying the new entry to every follower. It doesn't wait for all of them; one of the links happens to be slow today.");

    b.set(1, { log: [L("x=5", 1)], note: ["stored it, replied ok ▶"] }).set(2, { log: [L("x=5", 1)], note: ["stored it, replied ok ▶"] }).set(3, { log: [L("x=5", 1)], note: ["stored it, replied ok ▶"] });
    b.set(4, { note: ["message still in flight"] });
    b.set(0, { note: ["acks from S2, S3, S4", "4 of 5 copies exist"] });
    b.snap("Followers store it and acknowledge",
      "S2, S3 and S4 each check that the entry fits after what they already have (the <em>consistency check</em>), append it, and reply. S5 hasn't heard yet. The leader now knows the entry is stored on 4 of 5 servers.");

    b.set(0, { commit: 1, note: ["MAJORITY: committed", "applied; client gets OK"] });
    b.snap("Stored on a majority means committed",
      "As soon as an entry is stored on a <strong>majority</strong> (3 of 5, counting the leader), the leader marks it <strong>committed</strong> (solid green) and applies it to its state machine: <code>x = 5</code>. Committed entries are guaranteed never to be lost or undone. Only now does the client get its \"OK\".");

    b.set(1, { commit: 1, note: ["learned: committed", "applied"] }).set(2, { commit: 1, note: ["learned: committed", "applied"] }).set(3, { commit: 1, note: ["learned: committed", "applied"] });
    b.set(4, { log: [L("x=5", 1)], commit: 1, note: ["caught up, applied"] });
    b.set(0, { note: ["next heartbeat carries", "the commit index"] });
    b.snap("Followers learn it is committed",
      "The next <code>AppendEntries</code> (or heartbeat) includes the leader's commit index. Followers mark entry #1 committed and apply it. S5's delayed message finally arrives and it catches up. Every state machine now holds <code>x = 5</code>: <strong>same log in the same order gives the same state.</strong>");

    b.set(0, { log: [L("x=5", 1), L("y=7", 1)], note: ["client: set y=7", "appended as #2"] });
    b.set(1, { log: [L("x=5", 1), L("y=7", 1)], note: ["stored #2, replied ok ▶"] }).set(2, { log: [L("x=5", 1), L("y=7", 1)], note: ["stored #2, replied ok ▶"] });
    b.set(3, { note: ["message in flight…"] }).set(4, { note: ["message in flight…"] });
    b.snap("A second command arrives",
      "A new command, <code>set y=7</code>, becomes entry #2 and goes out. This time only S2 and S3 receive it quickly. S4 and S5 are still waiting for their copy.");

    b.set(0, { commit: 2, note: ["#2 is on S1, S2, S3", "= majority: committed", "client gets OK"] });
    b.snap("Entry #2 commits on three servers",
      "S1, S2 and S3 hold entry #2: 3 of 5, a majority. The leader commits and applies it (<code>y = 7</code>) and tells the client. The followers have <em>not</em> yet been told it is committed.");

    b.set(0, { role: "X", note: ["CRASHED"] });
    b.set(1, { note: ["no heartbeat…", "(has #2, thinks", "it's uncommitted)"] }).set(2, { note: ["no heartbeat…", "(has #2)"] });
    b.set(3, { note: ["no heartbeat…", "(only has #1)"] }).set(4, { note: ["no heartbeat…", "(only has #1)"] });
    b.snap("The leader crashes at the worst moment",
      "S1 dies right after telling the client \"OK\". The cluster is now in a delicate spot: a <em>committed</em> entry (#2) exists only on S2 and S3 (and the dead S1). S4 and S5 don't have it. Can a server that lacks it become the new leader and lose it?");

    b.set(3, { role: "C", term: 2, votes: 2, note: ["asks: my last entry", "is #1, term 1"] });
    b.set(4, { term: 2, note: ["grants vote"] }).set(1, { term: 2, note: ["REFUSES: my log is", "more up to date"] }).set(2, { term: 2, note: ["REFUSES: my log is", "more up to date"] });
    b.snap("A server with a short log can't win",
      "S4 times out first and asks for votes in term 2. S5 agrees (its log is no shorter than S4's). But S2 and S3 <strong>refuse</strong>: <em>\"your log is behind mine\"</em>. A server only votes for a candidate whose log is at least as up to date as its own. S4 gets 2 votes out of the 3 it needs.");

    b.set(2, { role: "L", term: 3, note: ["won term 3 with", "4 of 5 votes"] });
    b.set(3, { role: "F", term: 3, note: ["grants vote"] }).set(4, { term: 3, note: ["grants vote"] }).set(1, { term: 3, note: ["grants vote"] });
    b.snap("A server with the full log wins",
      "S3's timer fires next. In term 3 it asks for votes, and its log (#1 and #2) is at least as up to date as anyone's, so S2, S4 and S5 grant. <strong>The voting rule guarantees any winner has every committed entry</strong>, because a committed entry lives on a majority and every winner needs the votes of a majority: the two groups must overlap.");

    var full = [L("x=5", 1), L("y=7", 1), L("no-op", 3)];
    b.set(2, { log: full.slice(), note: ["adds a no-op #3, sends", "its log to everyone"] });
    b.set(3, { log: full.slice(), note: ["copied #2 and #3"] }).set(4, { log: full.slice(), note: ["copied #2 and #3"] }).set(1, { log: full.slice(), note: ["already had #2,", "added #3"] });
    b.snap("The new leader brings everyone up to date",
      "The new leader sends the entries followers are missing (S4 and S5 get #2, then #3). Raft leaders start their term by appending a blank <em>no-op</em> entry, so there is something from the current term to commit.");

    b.set(2, { commit: 3, note: ["majority has #3:", "commits #1–#3"] });
    b.set(1, { commit: 3, note: ["committed, applied"] }).set(3, { commit: 3, note: ["committed, applied"] }).set(4, { commit: 3, note: ["committed, applied"] });
    b.snap("Everything is committed, nothing was lost",
      "The no-op reaches a majority, so everything up to #3 is committed, including <code>y=7</code>, which the old leader had promised the client. The cluster survived a leader crash in mid-flight without losing or reordering anything.");

    b.set(0, { role: "L", term: 1, log: [L("x=5", 1), L("y=7", 1)], commit: 2, note: ["restarts, thinks", "it's the leader"] });
    b.snap("The old leader comes back…",
      "S1 comes back (say after a long freeze; a server that really rebooted would start as a follower). Its log is intact, but it doesn't know the world moved on to term 3.");

    b.set(0, { role: "F", term: 3, log: full.slice(), commit: 3, note: ["saw term 3 → follower", "log matches S3's"] });
    b.snap("…and quietly rejoins as a follower",
      "S3's next <code>AppendEntries</code> carries term 3. S1 sees the higher term, steps down, checks its log against the leader's (which matches) and receives what it missed. All five servers now hold identical logs and identical state.");
    return b.frames;
  }

  /* ---------- rendering: election circle ---------- */

  var KIND = {
    req:   { cls: "yellow", label: "RequestVote" },
    grant: { cls: "green",  label: "vote granted" },
    deny:  { cls: "red",    label: "rejected" },
    hb:    { cls: "blue",   label: "heartbeat" },
    lost:  { cls: "red",    label: "lost" }
  };
  var CX = 380, CY = 185, RX = 200, RY = 105, NR = 30;

  function nodePos(i) {
    var a = (-90 + i * 72) * Math.PI / 180;
    return { x: CX + RX * Math.cos(a), y: CY + RY * Math.sin(a), ux: Math.cos(a), uy: Math.sin(a) };
  }
  var ROLE_NAME = { F: "Follower", C: "Candidate", L: "Leader", X: "Crashed" };

  function drawElection(box, f) {
    box.textContent = "";
    var svg = el("svg", { viewBox: "0 0 760 350", role: "img", "aria-label": "Five Raft servers in a circle. " + f.title }, box);
    var defs = el("defs", {}, svg);
    Object.keys(KIND).forEach(function (k) {
      var m = el("marker", { id: "ah20" + k, viewBox: "0 0 10 10", refX: "9", refY: "5", markerWidth: "7", markerHeight: "7", orient: "auto" }, defs);
      el("path", { d: "M0,0 L10,5 L0,10 z", "class": "f-" + KIND[k].cls }, m);
    });
    // arrows first (under nodes)
    f.msgs.forEach(function (m) {
      var a = nodePos(m.from), b = nodePos(m.to);
      var dx = b.x - a.x, dy = b.y - a.y, len = Math.sqrt(dx * dx + dy * dy);
      var ux = dx / len, uy = dy / len, px = -uy * 6, py = ux * 6;
      var x1 = a.x + ux * (NR + 3) + px, y1 = a.y + uy * (NR + 3) + py;
      var x2 = b.x - ux * (NR + 5) + px, y2 = b.y - uy * (NR + 5) + py;
      var kind = KIND[m.kind], lost = m.kind === "lost";
      if (lost) { x2 = x1 + (x2 - x1) * 0.6; y2 = y1 + (y2 - y1) * 0.6; }
      var attrs = { x1: x1, y1: y1, x2: x2, y2: y2, "class": "line s-" + kind.cls + " sw-2" };
      if (lost) attrs["stroke-dasharray"] = "5 4"; else attrs["marker-end"] = "url(#ah20" + m.kind + ")";
      el("line", attrs, svg);
      if (lost) el("text", { x: x2 + ux * 8, y: y2 + uy * 8 + 5, "text-anchor": "middle", "class": "tc-red t-bold" }, svg).textContent = "✕";
    });
    f.nodes.forEach(function (n, i) {
      var p = nodePos(i), g = el("g", {}, svg);
      var cls = n.role === "L" ? "f-green" : n.role === "C" ? "fs-yellow s-yellow sw-3" : n.role === "X" ? "fs-red s-red sw-2" : "fs-blue s-blue sw-2";
      var c = el("circle", { cx: p.x, cy: p.y, r: NR, "class": cls }, g);
      if (n.role === "X") c.setAttribute("stroke-dasharray", "5 4");
      var dark = n.role === "L" ? " t-dark" : "";
      el("text", { x: p.x, y: p.y - 2, "text-anchor": "middle", "class": "t-bold" + dark }, g).textContent = "S" + (i + 1);
      el("text", { x: p.x, y: p.y + 15, "text-anchor": "middle", "class": "t-sm" + dark }, g).textContent = n.role === "X" ? "✕" : "term " + n.term;
      var lines = [ROLE_NAME[n.role]].concat(n.note || []);
      var side = Math.abs(p.ux) > 0.5 ? (p.ux > 0 ? "right" : "left") : (p.uy < 0 ? "top" : "bottom");
      lines.forEach(function (txt, li) {
        var x, y, anchor;
        if (side === "right") { x = p.x + NR + 8; anchor = "start"; y = p.y - (lines.length - 1) * 7 + li * 14 + 4; }
        else if (side === "left") { x = p.x - NR - 8; anchor = "end"; y = p.y - (lines.length - 1) * 7 + li * 14 + 4; }
        else if (side === "top") { x = p.x; anchor = "middle"; y = p.y - NR - 8 - (lines.length - 1 - li) * 14; }
        else { x = p.x; anchor = "middle"; y = p.y + NR + 17 + li * 14; }
        el("text", { x: x, y: y, "text-anchor": anchor, "class": "t-sm " + (li === 0 ? "t-bold" : "t-muted") }, g).textContent = txt;
      });
    });
  }

  /* ---------- rendering: log rows ---------- */

  var ROW_H = 60, ROW_Y0 = 28, CELL_X = 300, CELL_W = 78, CELL_G = 6;

  function applyState(log, commit) {
    var s = {}, order = [];
    for (var i = 0; i < commit && i < log.length; i++) {
      var m = /^(\w+)=(.+)$/.exec(log[i].c);
      if (m) { if (!(m[1] in s)) order.push(m[1]); s[m[1]] = m[2]; }
    }
    return order.length ? order.map(function (k) { return k + "=" + s[k]; }).join("  ") : "(empty)";
  }

  function drawLog(box, f) {
    box.textContent = "";
    var svg = el("svg", { viewBox: "0 0 760 " + (ROW_Y0 + 5 * ROW_H + 4), role: "img", "aria-label": "Logs of five Raft servers. " + f.title }, box);
    el("text", { x: 14, y: 16, "class": "t-sm t-faint t-bold" }, svg).textContent = "SERVER";
    el("text", { x: CELL_X, y: 16, "class": "t-sm t-faint t-bold" }, svg).textContent = "LOG  (#index · term)";
    el("text", { x: 600, y: 16, "class": "t-sm t-faint t-bold" }, svg).textContent = "STATE MACHINE";
    f.nodes.forEach(function (n, i) {
      var y = ROW_Y0 + i * ROW_H, g = el("g", { opacity: n.role === "X" ? "0.55" : "1" }, svg);
      var rcls = n.role === "L" ? "fs-green s-green sw-2" : "box";
      el("rect", { x: 4, y: y, width: 752, height: ROW_H - 6, rx: 8, "class": rcls }, g);
      el("text", { x: 14, y: y + 20, "class": "t-bold" }, g).textContent = "S" + (i + 1);
      el("text", { x: 44, y: y + 20, "class": "t-sm " + (n.role === "L" ? "tc-green t-bold" : n.role === "X" ? "tc-red t-bold" : "t-muted") }, g)
        .textContent = ROLE_NAME[n.role] + (n.role === "X" ? "" : " · term " + n.term);
      (n.note || []).forEach(function (txt, li) {
        el("text", { x: 14, y: y + 36 + li * 12, "class": "t-sm t-faint" }, g).textContent = txt;
      });
      n.log.forEach(function (e, k) {
        var x = CELL_X + k * (CELL_W + CELL_G), committed = k < n.commit;
        var r = el("rect", { x: x, y: y + 6, width: CELL_W, height: 40, rx: 6, "class": committed ? "fs-green s-green sw-2" : "box2" }, g);
        if (!committed) r.setAttribute("stroke-dasharray", "4 3");
        el("text", { x: x + CELL_W / 2, y: y + 24, "text-anchor": "middle", "class": "t-sm t-bold" }, g).textContent = e.c;
        el("text", { x: x + CELL_W / 2, y: y + 39, "text-anchor": "middle", "class": "t-sm t-faint" }, g).textContent = "#" + (k + 1) + " · t" + e.t;
      });
      el("text", { x: 600, y: y + 31, "class": "mono t-sm" }, g).textContent = applyState(n.log, n.commit);
    });
  }

  /* ---------- widget shell ---------- */

  function setup(root, kind, scenarios) {
    var stage = root.querySelector(".rf-stage"), cap = root.querySelector(".rf-caption");
    var ctl = root.querySelector(".rf-controls");
    var legend = root.querySelector(".rf-legend");
    var cur = 0, step = 0, frames = scenarios[0].frames();

    var bFirst = h("button", "btn small", "⏮"), bPrev = h("button", "btn small", "← Back"), bNext = h("button", "btn small primary", "Next →");
    [bFirst, bPrev, bNext].forEach(function (b) { b.type = "button"; });
    bFirst.setAttribute("aria-label", "First step"); bPrev.setAttribute("aria-label", "Previous step"); bNext.setAttribute("aria-label", "Next step");
    var count = h("span", "rf-count");

    if (scenarios.length > 1) {
      var lab = h("label", "widget-help", "Scenario:"); lab.setAttribute("for", root.id + "-sel");
      var sel = h("select", "rf-select"); sel.id = root.id + "-sel";
      scenarios.forEach(function (s, i) { var o = h("option", "", s.name); o.value = i; sel.appendChild(o); });
      sel.addEventListener("change", function () { cur = +sel.value; frames = scenarios[cur].frames(); step = 0; render(); });
      ctl.appendChild(lab); ctl.appendChild(sel);
    }
    ctl.appendChild(bFirst); ctl.appendChild(bPrev); ctl.appendChild(bNext); ctl.appendChild(count);

    if (legend) legend.appendChild(legendFor(kind));

    function render() {
      var f = frames[step];
      (kind === "election" ? drawElection : drawLog)(stage, f);
      cap.textContent = "";
      var t = h("p", "rf-title"); t.textContent = (step + 1) + ". " + f.title; cap.appendChild(t);
      var p = h("p", "rf-text"); p.innerHTML = f.text; cap.appendChild(p);   // text is authored in this file only
      count.textContent = (step + 1) + " / " + frames.length;
      bFirst.disabled = bPrev.disabled = step === 0;
      bNext.disabled = step === frames.length - 1;
    }
    bFirst.addEventListener("click", function () { step = 0; render(); });
    bPrev.addEventListener("click", function () { if (step > 0) { step--; render(); } });
    bNext.addEventListener("click", function () { if (step < frames.length - 1) { step++; render(); } });
    root.tabIndex = 0;
    root.addEventListener("keydown", function (e) {
      if (e.target !== root) return;
      if (e.key === "ArrowRight") { e.preventDefault(); bNext.click(); }
      if (e.key === "ArrowLeft") { e.preventDefault(); bPrev.click(); }
    });
    render();
  }

  function legendFor(kind) {
    var wrap = h("div", "rf-legend-in");
    function item(swatchCls, text) {
      var s = h("span", "rf-key"); s.appendChild(h("i", swatchCls)); s.appendChild(document.createTextNode(text)); wrap.appendChild(s);
    }
    if (kind === "election") {
      item("sw-follower", "follower"); item("sw-candidate", "candidate"); item("sw-leader", "leader"); item("sw-down", "crashed");
      item("ar-yellow", "RequestVote"); item("ar-green", "vote granted"); item("ar-red", "rejected / lost"); item("ar-blue", "heartbeat");
    } else {
      item("sw-commit", "committed entry"); item("sw-pending", "stored, not yet committed");
      item("sw-leader", "leader row");
    }
    return wrap;
  }

  var e1 = document.getElementById("raft-election");
  if (e1) setup(e1, "election", [
    { name: "Election, leader crash, old leader returns", frames: electionNormal },
    { name: "Split vote (bad luck)", frames: electionSplit }
  ]);
  var e2 = document.getElementById("raft-log");
  if (e2) setup(e2, "log", [{ name: "Log replication and a leader crash", frames: logStory }]);
})();
