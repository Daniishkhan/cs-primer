/* Geo-latency explorer (distributed chapter 18).

   Six regions with ROUGH round-trip times between them (order-of-magnitude figures for
   public-cloud regions; real numbers vary by provider, route and day). You choose which
   regions hold replicas, where the leader sits and which replication design is used. The
   table shows, for a client in each region, the latency of a write, a linearizable
   (up-to-date) read and a local, possibly stale read.

   Designs
     leader    one leader, writes need a majority of replicas. Client talks to the leader.
               write = rtt(client, leader) + time for the leader to hear from a majority
               linearizable read = rtt(client, leader)   (leader holds a lease; the simple case)
               stale read = nearest replica
     home      "home region" / follow the sun: each client region is the leader for its own data
               write = majority time from the client's nearest replica region, plus the hop to it
               read = local (the home replica is the leader for that data)
     leaderless  Dynamo-style: any replica coordinates; write and read each wait for a
               majority of replicas. Client uses the nearest replica as coordinator.
               stale read (read one replica) = nearest replica
     async     one leader, commits locally and replicates in the background.
               write = rtt(client, leader), but a leader-region loss can lose recent writes.

   Simplifications: processing time ignored; no queueing; a majority is floor(n/2)+1 of the
   chosen replicas, the leader counting itself at 0 ms. */
(function () {
  "use strict";
  var root = document.getElementById("geo-latency");
  if (!root) return;

  var R = [
    { id: "use", name: "us-east (Virginia)" },
    { id: "usw", name: "us-west (Oregon)" },
    { id: "eu", name: "eu-west (Ireland)" },
    { id: "sa", name: "sa-east (Sao Paulo)" },
    { id: "ap", name: "ap-southeast (Singapore)" },
    { id: "jp", name: "ap-northeast (Tokyo)" }
  ];
  /* rough round-trip times in ms */
  var M = {
    "use-usw": 65, "use-eu": 75, "use-sa": 115, "use-ap": 220, "use-jp": 150,
    "usw-eu": 130, "usw-sa": 175, "usw-ap": 170, "usw-jp": 100,
    "eu-sa": 190, "eu-ap": 170, "eu-jp": 220,
    "sa-ap": 320, "sa-jp": 255,
    "ap-jp": 70
  };
  function rtt(a, b) {
    if (a === b) return 0;
    return M[a + "-" + b] != null ? M[a + "-" + b] : M[b + "-" + a];
  }

  var state = { reps: { use: true, usw: false, eu: true, sa: false, ap: true, jp: false }, leader: "use", design: "leader" };

  var DESIGNS = [
    ["leader", "One leader, majority commit"],
    ["home", "Home region per client (follow the sun)"],
    ["leaderless", "Leaderless majority quorums"],
    ["async", "One leader, asynchronous replicas"]
  ];

  function replicas() { return R.filter(function (r) { return state.reps[r.id]; }).map(function (r) { return r.id; }); }
  function nearest(from, set) {
    var best = set[0];
    set.forEach(function (s) { if (rtt(from, s) < rtt(from, best)) best = s; });
    return best;
  }
  /* time for node `from` (itself a replica, counting 0) to hear from a majority of `set` */
  function majorityTime(from, set) {
    var maj = Math.floor(set.length / 2) + 1;
    var ds = set.map(function (s) { return rtt(from, s); }).sort(function (a, b) { return a - b; });
    return ds[maj - 1];
  }

  function compute(client) {
    var set = replicas();
    var d = state.design, L = state.leader;
    var w, rl, rs, via;
    if (d === "leader") {
      w = rtt(client, L) + majorityTime(L, set);
      rl = rtt(client, L);
      rs = rtt(client, nearest(client, set));
      via = "leader " + L;
    } else if (d === "home") {
      var h = nearest(client, set);
      w = rtt(client, h) + majorityTime(h, set);
      rl = rtt(client, h);
      rs = rl;
      via = "home " + h;
    } else if (d === "leaderless") {
      var c = nearest(client, set);
      w = rtt(client, c) + majorityTime(c, set);
      rl = w;
      rs = rtt(client, c);
      via = "coord " + c;
    } else {
      w = rtt(client, L);
      rl = rtt(client, L);
      rs = rtt(client, nearest(client, set));
      via = "leader " + L;
    }
    return { w: w, rl: rl, rs: rs };
  }

  /* ---------- DOM ---------- */
  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }

  var head = el("div", "widget-head");
  head.appendChild(el("span", "widget-tag", "Explorer"));
  head.appendChild(el("span", "widget-title", "What do your replica choices cost, from each region?"));
  root.appendChild(head);
  root.appendChild(el("p", "widget-help", "Tick the regions that hold a replica, pick the design and (for the leader designs) the leader's region. Latencies are rough round-trip times; the point is the shape, not the exact milliseconds."));

  root.appendChild(el("div", "gl-label", "1. Replica regions"));
  var repBox = el("div", "gl-checks");
  var repInputs = {};
  R.forEach(function (r) {
    var lab = el("label", "gl-check");
    var cb = el("input"); cb.type = "checkbox"; cb.checked = state.reps[r.id];
    cb.addEventListener("change", function () {
      state.reps[r.id] = cb.checked;
      if (!replicas().length) { state.reps[r.id] = true; cb.checked = true; }
      if (!state.reps[state.leader]) state.leader = replicas()[0];
      render();
    });
    repInputs[r.id] = cb;
    lab.appendChild(cb); lab.appendChild(el("span", null, r.name));
    repBox.appendChild(lab);
  });
  root.appendChild(repBox);

  root.appendChild(el("div", "gl-label", "2. Design"));
  var dsel = el("select"); dsel.className = "gl-select"; dsel.setAttribute("aria-label", "Design");
  DESIGNS.forEach(function (p) { var o = el("option", null, p[1]); o.value = p[0]; dsel.appendChild(o); });
  dsel.value = state.design;
  dsel.addEventListener("change", function () { state.design = dsel.value; render(); });
  root.appendChild(dsel);

  var lwrap = el("div", "gl-leader");
  lwrap.appendChild(el("span", "gl-label2", "Leader region: "));
  var lsel = el("select"); lsel.className = "gl-select"; lsel.setAttribute("aria-label", "Leader region");
  lsel.addEventListener("change", function () { state.leader = lsel.value; render(); });
  lwrap.appendChild(lsel);
  root.appendChild(lwrap);

  root.appendChild(el("div", "gl-label", "3. Latency seen by a client in each region (ms, round trip)"));
  var table = el("div", "gl-table");
  root.appendChild(table);
  var summary = el("p", "gl-sum"); summary.setAttribute("aria-live", "polite");
  root.appendChild(summary);

  var SCALE = 600;
  function bar(ms, cls) {
    var wrap = el("span", "gl-bar-wrap");
    var b = el("span", "gl-bar " + cls);
    b.style.width = Math.max(1, Math.min(100, ms / SCALE * 100)) + "%";
    wrap.appendChild(b);
    return wrap;
  }

  function render() {
    var set = replicas();
    /* leader selector */
    lsel.textContent = "";
    set.forEach(function (id) {
      var o = el("option", null, R.filter(function (r) { return r.id === id; })[0].name);
      o.value = id; lsel.appendChild(o);
    });
    if (set.indexOf(state.leader) < 0) state.leader = set[0];
    lsel.value = state.leader;
    var usesLeader = state.design === "leader" || state.design === "async";
    lwrap.style.display = usesLeader ? "" : "none";

    table.textContent = "";
    var hdr = el("div", "gl-row gl-hdr");
    ["Client in", "Write", "Read (up to date)", "Read (local, maybe stale)"].forEach(function (t) { hdr.appendChild(el("span", null, t)); });
    table.appendChild(hdr);
    var worstW = 0, sumW = 0;
    R.forEach(function (r) {
      var c = compute(r.id);
      worstW = Math.max(worstW, c.w); sumW += c.w;
      var row = el("div", "gl-row");
      row.appendChild(el("span", "gl-name", r.name));
      [[c.w, "w"], [c.rl, "rl"], [c.rs, "rs"]].forEach(function (p) {
        var cell = el("span", "gl-cell");
        cell.appendChild(el("span", "gl-ms", p[0] + " ms"));
        cell.appendChild(bar(p[0], p[1]));
        row.appendChild(cell);
      });
      table.appendChild(row);
    });
    var n = set.length, maj = Math.floor(n / 2) + 1;
    var msg = n + " replica" + (n === 1 ? "" : "s") + ", majority = " + maj + ". Average write " + Math.round(sumW / R.length) + " ms, worst " + worstW + " ms.";
    if (state.design === "async") msg += " Writes are fast, but a leader-region loss can lose acknowledged writes (RPO > 0).";
    else if (n === 1) msg += " With one replica there is no fault tolerance at all.";
    else if (n === 2) msg += " Two replicas need both for a majority: it tolerates no failure.";
    else if (n % 2 === 0) msg += " An even count adds cost without adding fault tolerance over n-1.";
    summary.textContent = msg;
  }
  render();
})();
