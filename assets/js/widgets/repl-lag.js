/* Replication lag lab (data chapter 15).

   One leader and two followers on a simulated clock (milliseconds, advanced only by the buttons).
   - A write ("update profile photo") gets the next LSN (log sequence number) and is the new
     photo version. The leader has it at once. A follower applies it lag ms after the write
     (the lag slider is read live; writes are applied in order, so a follower's applied LSN is
     the length of the prefix whose apply times have passed).
   - Asynchronous mode: the user is told "OK" at once. Semi-synchronous mode: the write call
     blocks until follower A has it (the clock advances by A's lag), then "OK".
   - Read policies decide which node answers the user's read:
       any follower (alternating A, B, A, B...), a sticky follower (the user is pinned to one),
       the leader during a window after a write (then any follower), and "wait until the
       replica has reached my write's LSN" (the clock advances by the wait).
   - "Kill the leader": the follower with the highest applied LSN is promoted instantly. Writes
     it never received are gone for good, although the user was told they succeeded.
   - The user session tracks its last write LSN (read-your-writes) and the highest LSN it has
     seen (monotonic reads) and flags a violation on each read.
   Not modelled: failure detection time, elections, reads that fail, per-write lag variation. */
(function () {
  "use strict";
  var root = document.getElementById("repl-lag");
  if (!root) return;

  var WINDOW_MS = 1000;
  function $(sel) { return root.querySelector(sel); }
  var lagIn = { A: $("[data-in=lagA]"), B: $("[data-in=lagB]") };
  var lagOut = { A: $("[data-out=lagA]"), B: $("[data-out=lagB]") };
  var cards = { L: $("[data-node=L]"), A: $("[data-node=A]"), B: $("[data-node=B]") };
  var modeSel = $("[data-in=mode]"), pinSel = $("[data-in=pin]");
  var policyInputs = root.querySelectorAll("input[name=repl-policy]");
  var btn = {
    write: $("[data-act=write]"), read: $("[data-act=read]"), w100: $("[data-act=w100]"), w500: $("[data-act=w500]"),
    demo: $("[data-act=demo]"), kill: $("[data-act=kill]"), reset: $("[data-act=reset]")
  };
  var clockEl = $(".rl-clock"), seeEl = $(".rl-see"), verdictEl = $(".rl-verdict"), logEl = $(".rl-log"), lostEl = $(".rl-lost");

  var S;
  function fresh() {
    return { t: 0, writes: [], leader: "L", dead: null, catchup: null, rr: 0, lastWriteLsn: 0, lastWriteT: -1e9,
      maxSeen: 0, nRyw: 0, nMono: 0, acked: 0, lost: [], log: [], lastRead: null, failed: false };
  }
  function lag(n) { return +lagIn[n].value; }
  function policy() { for (var i = 0; i < policyInputs.length; i++) if (policyInputs[i].checked) return policyInputs[i].value; return "any"; }
  function followers() { return ["A", "B"].filter(function (n) { return n !== S.dead && n !== S.leader; }); }
  function applyAt(w, n) {
    var at = w.tw + lag(n);
    if (S.catchup !== null && n !== S.leader && w.tw < S.catchup && at > S.catchup) at = S.catchup + lag(n);
    return at;
  }
  function applied(n) {
    if (n === S.leader) return S.writes.length;
    var c = 0;
    for (var i = 0; i < S.writes.length; i++) { if (applyAt(S.writes[i], n) <= S.t) c = i + 1; else break; }
    return c;
  }
  function say(text, cls) { S.log.push({ t: S.t, text: text, cls: cls || "" }); }
  function name(n) { return n === "L" ? "the leader" : (n === S.leader ? "new leader " + n : "follower " + n); }

  function write() {
    var t0 = S.t, lsn = S.writes.length + 1;
    S.writes.push({ lsn: lsn, tw: t0 });
    S.lastWriteLsn = lsn; S.lastWriteT = t0; S.acked++;
    var semi = modeSel.value === "semi" && followers().indexOf("A") !== -1;
    if (semi) {
      S.t += lag("A");
      say("WRITE photo v" + lsn + " on " + name(S.leader) + ". Semi-sync: waited " + lag("A") + " ms for follower A to confirm, then told the user OK.");
    } else {
      say("WRITE photo v" + lsn + " on " + name(S.leader) + ". Told the user OK at once (asynchronous).");
    }
  }

  function chooseReader() {
    var pol = policy(), fs = followers(), why = "";
    if (!fs.length) return { node: S.leader, why: "no follower left" };
    function rr() { var n = fs[S.rr % fs.length]; S.rr++; return n; }
    if (pol === "any") return { node: rr(), why: "any follower (alternating)" };
    if (pol === "sticky") {
      var pin = fs.indexOf(pinSel.value) !== -1 ? pinSel.value : fs[0];
      return { node: pin, why: "sticky: this user always reads from " + pin };
    }
    if (pol === "window") {
      if (S.t - S.lastWriteT < WINDOW_MS) return { node: S.leader, why: "wrote " + (S.t - S.lastWriteT) + " ms ago (< " + WINDOW_MS + " ms), so read the leader" };
      return { node: rr(), why: "last write is older than " + WINDOW_MS + " ms, so any follower" };
    }
    var n = rr();
    return { node: n, why: "wait until the replica reaches LSN " + S.lastWriteLsn };
  }

  function read() {
    var pol = policy(), ch = chooseReader(), n = ch.node, waited = 0;
    if (pol === "lsn" && n !== S.leader) {
      var need = S.lastWriteLsn;
      if (need > 0 && need <= S.writes.length && applied(n) < need) {
        waited = Math.max(0, applyAt(S.writes[need - 1], n) - S.t);
        S.t += waited;
      }
    }
    var seen = applied(n);
    var verdict = [];
    var lostMine = S.lastWriteLsn > S.writes.length;
    if (lostMine) verdict.push({ k: "lost", t: "The write you were told succeeded no longer exists anywhere." });
    else if (seen < S.lastWriteLsn) verdict.push({ k: "ryw", t: "Read-your-writes violated: you saved v" + S.lastWriteLsn + " but the page shows v" + seen + "." });
    if (seen < S.maxSeen) verdict.push({ k: "mono", t: "Monotonic reads violated: you already saw v" + S.maxSeen + ", now you see v" + seen + ". Time ran backwards." });
    verdict.forEach(function (x) { if (x.k === "mono") S.nMono++; else S.nRyw++; });
    S.maxSeen = Math.max(S.maxSeen, seen);
    S.lastRead = { node: n, seen: seen, verdict: verdict, waited: waited, why: ch.why };
    say("READ answered by " + name(n) + " (" + ch.why + (waited ? "; waited " + waited + " ms" : "") + "): photo v" + seen + (seen === 0 ? " (none yet)" : "") + ".",
      verdict.length ? "bad" : "");
  }

  function advance(ms) { S.t += ms; say("Waited " + ms + " ms."); }

  function kill() {
    if (S.failed) return;
    var cand = ["A", "B"], best = null, bestN = -1;
    cand.forEach(function (n) { var a = applied(n); if (a > bestN) { bestN = a; best = n; } });
    var lostFrom = bestN + 1, total = S.writes.length;
    S.failed = true;
    S.catchup = S.t;
    if (total > bestN) {
      for (var i = lostFrom; i <= total; i++) S.lost.push(i);
      S.writes.length = bestN;
    }
    S.dead = "L"; S.leader = best;
    say("LEADER KILLED. Follower " + best + " (applied LSN " + bestN + ") was promoted instantly. " +
      (S.lost.length ? "Writes v" + S.lost.join(", v") + " had been acknowledged but never reached it: LOST." : "It had every acknowledged write: nothing lost."), S.lost.length ? "bad" : "good");
  }

  function demo() {
    reset();
    write(); read();
    advance(300); read();
    advance(1500); read();
    render();
  }

  function reset() { S = fresh(); render(); }

  function nodeLabel(n) {
    if (S.dead === n) return "dead";
    if (S.leader === n) return "leader";
    return "follower";
  }
  function renderCard(n) {
    var c = cards[n], dead = S.dead === n, isLeader = S.leader === n;
    var a = dead ? null : applied(n), top = S.writes.length;
    c.className = "rl-node " + (dead ? "dead" : isLeader ? "leader" : "follower");
    c.querySelector(".rl-role").textContent = dead ? "dead" : isLeader ? "leader" : "follower";
    var v = c.querySelector(".rl-ver");
    if (dead) { v.textContent = "offline"; c.querySelector(".rl-sub").textContent = "its unreplicated writes died with it"; return; }
    v.textContent = "photo v" + a + (a === 0 ? " (none)" : "");
    var sub;
    if (isLeader) sub = "LSN " + a + " (accepts writes)";
    else {
      var behind = top - a;
      sub = "applied LSN " + a + (behind > 0 ? ", " + behind + " behind" : ", caught up");
    }
    c.querySelector(".rl-sub").textContent = sub;
    c.classList.toggle("stale", !isLeader && a < top);
  }

  function render() {
    ["A", "B"].forEach(function (n) {
      lagOut[n].textContent = lag(n) + " ms";
      lagIn[n].disabled = S.dead === n;
    });
    ["L", "A", "B"].forEach(renderCard);
    cards.L.querySelector(".rl-role").textContent = S.dead === "L" ? "dead" : "leader";
    clockEl.textContent = "t = " + S.t + " ms";
    btn.kill.disabled = S.failed;
    btn.write.disabled = false;
    if (S.lastRead) {
      var r = S.lastRead;
      seeEl.textContent = "Last read: " + (r.node === "L" ? "leader" : r.node === S.leader ? "new leader " + r.node : "follower " + r.node) + " showed photo v" + r.seen + (r.waited ? " (after waiting " + r.waited + " ms)" : "") + ". Violations so far: " + S.nRyw + " read-your-writes, " + S.nMono + " monotonic.";
      if (r.verdict.length) {
        verdictEl.textContent = r.verdict.map(function (x) { return x.t; }).join(" ");
        verdictEl.className = "rl-verdict bad";
      } else {
        verdictEl.textContent = "That read was consistent with everything this user has done so far.";
        verdictEl.className = "rl-verdict ok";
      }
    } else {
      seeEl.textContent = "No read yet. Write a photo, then read.";
      verdictEl.textContent = "Press Write, then Read, or run the demo.";
      verdictEl.className = "rl-verdict";
    }
    lostEl.textContent = S.failed
      ? (S.lost.length ? "Acknowledged writes lost in failover: v" + S.lost.join(", v") + "." : "Failover lost no acknowledged write.")
      : "Writes acknowledged so far: " + S.acked + ".";
    lostEl.className = "rl-lost" + (S.lost.length ? " bad" : "");
    logEl.textContent = "";
    S.log.slice(-8).reverse().forEach(function (e) {
      var li = document.createElement("li");
      li.textContent = "[" + e.t + " ms] " + e.text;
      if (e.cls) li.className = e.cls;
      logEl.appendChild(li);
    });
  }

  btn.write.addEventListener("click", function () { write(); render(); });
  btn.read.addEventListener("click", function () { read(); render(); });
  btn.w100.addEventListener("click", function () { advance(100); render(); });
  btn.w500.addEventListener("click", function () { advance(500); render(); });
  btn.demo.addEventListener("click", function () { demo(); });
  btn.kill.addEventListener("click", function () { kill(); render(); });
  btn.reset.addEventListener("click", reset);
  [lagIn.A, lagIn.B].forEach(function (i) { i.addEventListener("input", render); });
  Array.prototype.forEach.call(policyInputs, function (i) { i.addEventListener("change", function () { render(); }); });

  S = fresh();
  render();
})();
