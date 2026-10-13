/* Load-balancer simulator (chapter 14).
   Discrete time. Each tick: finished requests leave, health checks run,
   then 2 new requests arrive and the chosen algorithm assigns them.
   The request sequence is seeded, so both algorithms see identical traffic
   after a Reset. A killed server is only removed from rotation after
   2 consecutive failed health checks, so some requests are lost first. */
(function () {
  "use strict";
  var root = document.getElementById("lb-sim");
  if (!root) return;

  var N = 4, ARRIVALS = 2, FAILS_TO_REMOVE = 2, OKS_TO_RESTORE = 2;
  var grid = root.querySelector(".lb-grid");
  var statsBox = root.querySelector(".lb-stats");
  var logBox = root.querySelector(".lb-log");
  var algoSel = root.querySelector("[data-act=algo]");
  var playBtn = root.querySelector("[data-act=play]");
  var stepBtn = root.querySelector("[data-act=step]");
  var resetBtn = root.querySelector("[data-act=reset]");

  var rng, tick, rr, servers, served, lost, peak, timer = null;

  function mulberry32(a) {
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      var t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  function reset() {
    stop();
    rng = mulberry32(12345);
    tick = 0; rr = 0; served = 0; lost = 0; peak = 0;
    servers = [];
    for (var i = 0; i < N; i++) servers.push({ alive: true, inRotation: true, fails: 0, oks: 0, jobs: [] });
    logBox.textContent = "Press Step (or Play). Orange squares are slow requests, blue are quick ones.";
    render();
  }

  function newJob() {
    var long = rng() < 0.3;
    var dur = long ? 10 + Math.floor(rng() * 7) : 2 + Math.floor(rng() * 3);
    return { left: dur, long: long };
  }

  function pick(algo) {
    var cands = [];
    for (var i = 0; i < N; i++) if (servers[i].inRotation) cands.push(i);
    if (!cands.length) return -1;
    if (algo === "rr") {
      for (var k = 0; k < N; k++) {
        var idx = (rr + k) % N;
        if (servers[idx].inRotation) { rr = (idx + 1) % N; return idx; }
      }
    }
    var best = cands[0];
    cands.forEach(function (c) { if (servers[c].jobs.length < servers[best].jobs.length) best = c; });
    return best;
  }

  function step() {
    tick++;
    var msgs = [];
    servers.forEach(function (s, i) {
      s.jobs.forEach(function (j) { j.left--; });
      var before = s.jobs.length;
      s.jobs = s.jobs.filter(function (j) { return j.left > 0; });
      served += before - s.jobs.length;
      // health check
      if (!s.alive) {
        s.oks = 0; s.fails++;
        if (s.inRotation && s.fails >= FAILS_TO_REMOVE) { s.inRotation = false; msgs.push("Health check removed server " + (i + 1) + " from rotation."); }
      } else {
        s.fails = 0; s.oks++;
        if (!s.inRotation && s.oks >= OKS_TO_RESTORE) { s.inRotation = true; msgs.push("Server " + (i + 1) + " passed checks and is back in rotation."); }
      }
    });
    var algo = algoSel.value;
    var lostNow = 0;
    for (var a = 0; a < ARRIVALS; a++) {
      var job = newJob();
      var t = pick(algo);
      if (t < 0) { lostNow++; continue; }
      if (!servers[t].alive) { lostNow++; continue; }
      servers[t].jobs.push(job);
    }
    lost += lostNow;
    if (lostNow) msgs.push(lostNow + " request" + (lostNow > 1 ? "s were" : " was") + " sent to a dead server and lost (the balancer has not noticed yet).");
    servers.forEach(function (s) { if (s.jobs.length > peak) peak = s.jobs.length; });
    logBox.textContent = msgs.length ? msgs.join(" ") : "Tick " + tick + ": requests assigned.";
    render();
  }

  function toggle(i) {
    var s = servers[i];
    if (s.alive) {
      s.alive = false;
      lost += s.jobs.length;
      logBox.textContent = "Server " + (i + 1) + " crashed. Its " + s.jobs.length + " in-flight request(s) are lost. The balancer does not know yet.";
      s.jobs = [];
    } else {
      s.alive = true;
      logBox.textContent = "Server " + (i + 1) + " restarted. It must pass " + OKS_TO_RESTORE + " health checks before it gets traffic.";
    }
    render();
  }

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }

  function render() {
    grid.textContent = "";
    servers.forEach(function (s, i) {
      var box = el("div", "lb-srv" + (!s.alive ? " down" : "") + (!s.alive && s.inRotation ? " unseen" : ""));
      var head = el("div", "lb-srv-head");
      head.appendChild(el("span", "", "Server " + (i + 1)));
      var state = !s.alive ? (s.inRotation ? "crashed?" : "removed") : (s.inRotation ? "healthy" : "checking");
      head.appendChild(el("span", "lb-state", state));
      box.appendChild(head);
      box.appendChild(el("div", "lb-count", s.jobs.length + " active"));
      var dots = el("div", "lb-dots");
      s.jobs.forEach(function (j) { dots.appendChild(el("span", "lb-dot" + (j.long ? " long" : ""))); });
      box.appendChild(dots);
      var b = el("button", "btn small " + (s.alive ? "danger" : "success"), s.alive ? "Kill" : "Restart");
      b.type = "button";
      b.setAttribute("aria-label", (s.alive ? "Kill" : "Restart") + " server " + (i + 1));
      b.addEventListener("click", function () { toggle(i); });
      box.appendChild(b);
      grid.appendChild(box);
    });
    statsBox.textContent = "";
    [["Tick", tick], ["Completed", served], ["Lost", lost], ["Busiest server ever", peak]].forEach(function (p) {
      var span = el("span", "", p[0] + ": ");
      span.appendChild(el("b", "", String(p[1])));
      statsBox.appendChild(span);
    });
  }

  function stop() {
    if (timer) { clearInterval(timer); timer = null; }
    playBtn.textContent = "▶ Play";
  }
  playBtn.addEventListener("click", function () {
    if (timer) { stop(); return; }
    timer = setInterval(step, 800);
    playBtn.textContent = "⏸ Pause";
  });
  stepBtn.addEventListener("click", function () { stop(); step(); });
  resetBtn.addEventListener("click", reset);
  algoSel.addEventListener("change", reset);
  reset();
})();
