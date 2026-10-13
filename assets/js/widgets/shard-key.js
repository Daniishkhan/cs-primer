/* Shard key explorer (data chapter 16).

   A deterministic workload: 4,000 writes from 200 users whose popularity is Zipf-like (the busiest
   user does roughly 17% of all writes), arriving with increasing timestamps over one day.
   Older accounts (lower ids) tend to be bigger, so popularity is correlated with, but not equal
   to, the user id.

   Strategies:
   - range on timestamp: date ranges cut over the last 8 days, so today's writes all land at the top end.
   - hash(user_id): FNV-1a hash of the id, modulo the shard count.
   - range on user_id: 200 ids cut into equal contiguous ranges.
   - hash + salt: like hash(user_id), except the 5 hottest users get key "id#b" with b = write number
     modulo the shard count, so their writes fan out over several shards.

   A shard is "hot" when it takes more than 1.3x the average load. For the query, the widget lists
   the shards that must be asked. Not modelled: replication, read load, shard sizes in bytes,
   rebalancing. Counts are writes, not milliseconds. */
(function () {
  "use strict";

  var N_USERS = 200, N_WRITES = 4000, N_SALTED = 5, HOT_FACTOR = 1.3;
  var DAY = 86400, WINDOW_DAYS = 8;

  /* ---------- deterministic pieces ---------- */
  function mulberry32(a) {
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      var t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  function fnv1a(str) {
    var h = 0x811c9dc5;
    for (var i = 0; i < str.length; i++) { h ^= str.charCodeAt(i); h = Math.imul(h, 0x01000193) >>> 0; }
    return h >>> 0;
  }

  function buildWorkload() {
    var rnd = mulberry32(16);
    // popularity rank -> user id: sort ids by (id * noise), so low ids tend to be popular
    var ids = [];
    for (var u = 0; u < N_USERS; u++) ids.push({ id: u, key: (u + 1) * (0.4 + rnd() * 1.2) });
    ids.sort(function (a, b) { return a.key - b.key; });
    var userOfRank = ids.map(function (o) { return o.id; });
    var cum = [], total = 0;
    for (var r = 0; r < N_USERS; r++) { total += 1 / (r + 1); cum.push(total); }
    var writes = [];
    for (var i = 0; i < N_WRITES; i++) {
      var x = rnd() * total, lo = 0, hi = N_USERS - 1;
      while (lo < hi) { var mid = (lo + hi) >> 1; if (cum[mid] < x) lo = mid + 1; else hi = mid; }
      writes.push({ rank: lo, user: userOfRank[lo], t: Math.floor(i * DAY / N_WRITES), seq: i });
    }
    var rankOfUser = {};
    userOfRank.forEach(function (id, rk) { rankOfUser[id] = rk; });
    return { writes: writes, userOfRank: userOfRank, rankOfUser: rankOfUser };
  }

  var STRATS = [
    { id: "ts", label: "Range on timestamp",
      note: "Date ranges were cut over the last 8 days, so every new write lands in the newest range. One shard takes all the writes while the others sit idle." },
    { id: "hash", label: "hash(user_id)",
      note: "Users spread evenly across shards, but one very popular user still pins all of their writes to a single shard." },
    { id: "urange", label: "Range on user_id",
      note: "Contiguous id ranges. Older accounts have lower ids and tend to be busier, so the first ranges run hotter. Range scans by user id stay cheap." },
    { id: "salt", label: "hash(user_id) + salt for hot users",
      note: "The 5 busiest users get a salt (a suffix 0..N-1 on the key), so their writes spread over many shards. Reading one of them now means asking each salt bucket." }
  ];

  function shardOf(strat, w, n) {
    if (strat === "ts") return Math.min(n - 1, Math.floor((DAY * (WINDOW_DAYS - 1) + w.t) / (DAY * WINDOW_DAYS / n)));
    if (strat === "hash") return fnv1a("user:" + w.user) % n;
    if (strat === "urange") return Math.min(n - 1, Math.floor(w.user / (N_USERS / n)));
    if (w.rank < N_SALTED) return fnv1a("user:" + w.user + "#" + (w.seq % n)) % n;
    return fnv1a("user:" + w.user) % n;
  }

  function loads(W, strat, n) {
    var c = []; for (var i = 0; i < n; i++) c.push(0);
    W.writes.forEach(function (w) { c[shardOf(strat, w, n)]++; });
    return c;
  }

  /* shards an "all of user X's posts today" or "everything today" query must ask */
  function touched(W, strat, n, query, rank) {
    var set = {}, i;
    var user = W.userOfRank[rank];
    if (query === "day") {
      if (strat === "ts") { W.writes.forEach(function (w) { set[shardOf("ts", w, n)] = 1; }); }
      else for (i = 0; i < n; i++) set[i] = 1;
    } else if (strat === "ts") {
      W.writes.forEach(function (w) { set[shardOf("ts", w, n)] = 1; });
    } else if (strat === "hash") {
      set[fnv1a("user:" + user) % n] = 1;
    } else if (strat === "urange") {
      set[Math.min(n - 1, Math.floor(user / (N_USERS / n)))] = 1;
    } else if (rank < N_SALTED) {
      for (i = 0; i < n; i++) set[fnv1a("user:" + user + "#" + i) % n] = 1;
    } else set[fnv1a("user:" + user) % n] = 1;
    return Object.keys(set).map(Number).sort(function (a, b) { return a - b; });
  }

  var core = { buildWorkload: buildWorkload, loads: loads, touched: touched, STRATS: STRATS, shardOf: shardOf };
  if (typeof module !== "undefined" && module.exports) module.exports = core;

  /* ---------- UI ---------- */
  var root = typeof document !== "undefined" ? document.getElementById("shard-key") : null;
  if (!root) return;

  var W = buildWorkload();
  var state = { strat: 0, n: 4, rank: 0, query: "user" };
  var ui = {};

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  function pct(x) { return (Math.round(x * 1000) / 10).toFixed(1) + "%"; }
  function fmt(x) { return String(x).replace(/\B(?=(\d{3})+(?!\d))/g, ","); }

  function radioGroup(name, legend, items, checked, onChange) {
    var fs = el("fieldset", "sk-group");
    fs.appendChild(el("legend", "sk-lab", legend));
    var box = el("div", "sk-radios");
    items.forEach(function (it, i) {
      var lab = el("label", "sk-radio");
      var inp = el("input"); inp.type = "radio"; inp.name = name; inp.value = String(i);
      inp.checked = i === checked;
      inp.addEventListener("change", function () { onChange(i); });
      lab.appendChild(inp); lab.appendChild(el("span", "", it));
      box.appendChild(lab);
    });
    fs.appendChild(box);
    return fs;
  }

  function build() {
    var head = el("div", "widget-head");
    head.appendChild(el("span", "widget-tag", "Interactive"));
    head.appendChild(el("p", "widget-title", "Shard key explorer"));
    root.appendChild(head);
    root.appendChild(el("p", "widget-help", "4,000 writes arrive in one day from 200 users, a few of them very popular. Pick a shard key and a shard count. The bars show how many writes each shard receives; the red ones are hot. Then pick a query and see which shards it has to ask."));

    var row = el("div", "widget-row sk-pick");
    row.appendChild(radioGroup("sk-strat", "Shard key", STRATS.map(function (s) { return s.label; }), 0, function (i) { state.strat = i; render(); }));
    row.appendChild(radioGroup("sk-n", "Shards", ["4", "8"], 0, function (i) { state.n = i ? 8 : 4; render(); }));
    root.appendChild(row);

    ui.note = el("p", "sk-note"); root.appendChild(ui.note);
    ui.bars = el("div", "sk-bars"); root.appendChild(ui.bars);
    ui.sum = el("p", "sk-sum"); ui.sum.setAttribute("aria-live", "polite"); root.appendChild(ui.sum);

    var qrow = el("div", "widget-row sk-pick");
    var f1 = el("div", "sk-field"); var l1 = el("label", "sk-lab", "Query"); l1.htmlFor = "sk-q";
    ui.q = el("select"); ui.q.id = "sk-q";
    [["user", "Posts of user X in the last day"], ["day", "All posts in the last day (global feed)"]].forEach(function (q) {
      var o = el("option", "", q[1]); o.value = q[0]; ui.q.appendChild(o);
    });
    ui.q.addEventListener("change", function () { state.query = ui.q.value; ui.who.disabled = state.query === "day"; render(); });
    f1.appendChild(l1); f1.appendChild(ui.q);
    var f2 = el("div", "sk-field"); var l2 = el("label", "sk-lab", "User X"); l2.htmlFor = "sk-u";
    ui.who = el("select"); ui.who.id = "sk-u";
    [[0, "busiest user"], [2, "3rd busiest"], [20, "21st busiest"], [150, "a quiet user"]].forEach(function (u) {
      var o = el("option", "", "user_id " + W.userOfRank[u[0]] + " (" + u[1] + ")"); o.value = String(u[0]); ui.who.appendChild(o);
    });
    ui.who.addEventListener("change", function () { state.rank = parseInt(ui.who.value, 10); render(); });
    f2.appendChild(l2); f2.appendChild(ui.who);
    qrow.appendChild(f1); qrow.appendChild(f2);
    root.appendChild(qrow);
    ui.qout = el("p", "sk-qout"); ui.qout.setAttribute("aria-live", "polite"); root.appendChild(ui.qout);
  }

  function render() {
    var n = state.n, s = STRATS[state.strat];
    var L = loads(W, s.id, n), mean = N_WRITES / n;
    var T = touched(W, s.id, n, state.query, state.rank);
    var maxL = Math.max.apply(null, L);
    ui.note.textContent = s.note;
    ui.bars.textContent = "";
    L.forEach(function (c, i) {
      var hot = c > HOT_FACTOR * mean, asked = T.indexOf(i) >= 0;
      var row = el("div", "sk-row" + (asked ? " sk-asked" : ""));
      row.appendChild(el("span", "sk-name", "shard " + i));
      var track = el("div", "sk-track");
      var fill = el("div", "sk-fill" + (hot ? " sk-hot" : ""));
      fill.style.width = (c / N_WRITES * 100).toFixed(2) + "%";
      track.appendChild(fill);
      var tick = el("div", "sk-tick"); tick.style.left = (100 / n).toFixed(2) + "%";
      track.appendChild(tick);
      row.appendChild(track);
      var txt = fmt(c) + " (" + pct(c / N_WRITES) + ")" + (hot ? " hot" : "") + (asked ? " asked" : "");
      row.appendChild(el("span", "sk-val", txt));
      ui.bars.appendChild(row);
    });
    var idle = L.filter(function (c) { return c === 0; }).length;
    ui.sum.textContent = "Busiest shard: " + pct(maxL / N_WRITES) + " of writes (a perfect split is " + pct(1 / n) + "), " +
      (Math.round(maxL / mean * 10) / 10).toFixed(1) + "x the average." + (idle ? " " + idle + " shard" + (idle > 1 ? "s" : "") + " got no writes." : "") +
      " The tick on each bar marks the fair share.";
    var q = state.query === "day" ? "all posts in the last day" : "posts of user_id " + W.userOfRank[state.rank] + " in the last day";
    var extra = "";
    if (state.query === "user" && s.id === "ts") extra = " It is one shard, but that shard is the hot one, and the user's rows are mixed in with everyone else's.";
    else if (state.query === "user" && s.id === "salt" && state.rank < N_SALTED) extra = " The salt that tamed the write hot spot is what makes this read fan out.";
    else if (state.query === "day" && s.id === "ts") extra = " Range on time makes time-window reads cheap, and that is the same reason all the writes pile up.";
    else if (state.query === "day") extra = " Nothing in the key says when a post was made, so every shard has to be asked.";
    ui.qout.textContent = "Query: " + q + ". Must ask " + T.length + " of " + n + " shard" + (n > 1 ? "s" : "") + " (" + T.join(", ") + ")." + extra;
  }

  build();
  render();
})();
