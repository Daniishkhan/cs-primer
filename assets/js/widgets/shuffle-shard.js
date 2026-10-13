/* Shuffle-shard explorer (reliability chapter 15).
   N workers serve 16 customers. In "classic" mode the workers are split into N/k fixed shards of k and every
   customer is pinned to one shard. In "shuffle" mode each customer gets its own pseudo-random set of k workers.
   Pick a poison customer: every worker in its shard crashes. A customer is "down" when ALL of its workers are dead,
   and "degraded" when only some are. Deterministic: a seeded PRNG (the Re-roll button changes the seed). */
(function () {
  "use strict";

  var CUSTOMERS = 16;

  function rng(seed) {
    var a = seed >>> 0;
    return function () {
      a = (a + 0x6D2B79F5) >>> 0;
      var t = a;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  function choose(n, k) {
    var r = 1, i;
    for (i = 1; i <= k; i++) r = r * (n - k + i) / i;
    return Math.round(r);
  }
  /* assign: returns an array of CUSTOMERS arrays of worker indexes */
  function assign(mode, n, k, seed) {
    var r = rng(seed), out = [], c, i;
    if (mode === "classic") {
      var shards = Math.max(1, Math.floor(n / k));
      for (c = 0; c < CUSTOMERS; c++) {
        var s = Math.floor(r() * shards), set = [];
        for (i = 0; i < k; i++) set.push(s * k + i);
        out.push(set);
      }
      return out;
    }
    var seen = {}, total = choose(n, k);
    for (c = 0; c < CUSTOMERS; c++) {
      var tries = 0, set2, key;
      do {
        var pool = [], j;
        for (j = 0; j < n; j++) pool.push(j);
        set2 = [];
        for (j = 0; j < k; j++) set2.push(pool.splice(Math.floor(r() * pool.length), 1)[0]);
        set2.sort(function (x, y) { return x - y; });
        key = set2.join(",");
        tries++;
      } while (seen[key] && tries < 50 && Object.keys(seen).length < total);
      seen[key] = true;
      out.push(set2);
    }
    return out;
  }
  function evaluate(sets, poison, n) {
    var dead = {}, res = [];
    sets[poison].forEach(function (w) { dead[w] = true; });
    sets.forEach(function (set, c) {
      var d = set.filter(function (w) { return dead[w]; }).length;
      res.push(d === 0 ? "ok" : d === set.length ? "down" : "degraded");
    });
    return { dead: dead, status: res };
  }

  var core = { assign: assign, evaluate: evaluate, choose: choose };
  if (typeof module !== "undefined" && module.exports) module.exports = core;
  if (typeof document === "undefined") return;
  var root = document.getElementById("shuffle-shard");
  if (!root) return;

  function el(tag, attrs, text) {
    var e = document.createElement(tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    return e;
  }

  var state = { mode: "shuffle", n: 8, k: 2, seed: 5, poison: 0 };

  var head = el("div", { "class": "widget-head" });
  head.appendChild(el("span", { "class": "widget-tag" }, "Try it"));
  head.appendChild(el("h4", { "class": "widget-title" }, "One poison customer, two sharding schemes"));
  root.appendChild(head);
  root.appendChild(el("p", { "class": "widget-help" },
    "Sixteen customers share the workers. Choose a poison customer: its requests crash every worker in its shard. Count who else goes down (all workers dead) or is degraded (some dead). Compare classic sharding with shuffle sharding."));

  var ctl = el("div", { "class": "ss-ctl" });
  function field(label, node, id) { var w = el("div"); w.appendChild(el("label", { "for": id }, label)); w.appendChild(node); ctl.appendChild(w); }
  var modeSel = el("select", { id: "ss-mode" });
  modeSel.appendChild(el("option", { value: "classic" }, "Classic: fixed shards"));
  modeSel.appendChild(el("option", { value: "shuffle" }, "Shuffle: each customer a different subset"));
  modeSel.value = state.mode;
  var nSel = el("select", { id: "ss-n" });
  [6, 8, 10, 12].forEach(function (v) { nSel.appendChild(el("option", { value: String(v) }, v + " workers")); });
  nSel.value = "8";
  var kSel = el("select", { id: "ss-k" });
  [2, 3, 4].forEach(function (v) { kSel.appendChild(el("option", { value: String(v) }, v + " per customer")); });
  var pSel = el("select", { id: "ss-p" });
  field("Scheme", modeSel, "ss-mode"); field("Fleet size", nSel, "ss-n"); field("Shard size", kSel, "ss-k"); field("Poison customer", pSel, "ss-p");
  root.appendChild(ctl);
  var row = el("div", { "class": "widget-row" });
  var rerollBtn = el("button", { type: "button", "class": "btn small" }, "Re-roll assignments");
  row.appendChild(rerollBtn);
  root.appendChild(row);

  var verdict = el("p", { "class": "ss-verdict", "aria-live": "polite" });
  root.appendChild(verdict);
  var workers = el("div", { "class": "ss-workers", role: "group", "aria-label": "Workers" });
  root.appendChild(workers);
  var list = el("div", { "class": "ss-list" });
  root.appendChild(list);
  var math = el("p", { "class": "ss-math" });
  root.appendChild(math);

  function name(c) { return "C" + (c + 1); }
  function render() {
    var n = state.n, k = state.k;
    var sets = assign(state.mode, n, k, state.seed), ev = evaluate(sets, state.poison, n);
    var down = 0, deg = 0, c, w;
    ev.status.forEach(function (s, i) { if (i === state.poison) return; if (s === "down") down++; else if (s === "degraded") deg++; });
    workers.textContent = "";
    for (w = 0; w < n; w++) workers.appendChild(el("span", { "class": "ss-w " + (ev.dead[w] ? "dead" : "up"), title: "worker " + w }, String(w)));
    list.textContent = "";
    sets.forEach(function (set, i) {
      var card = el("div", { "class": "ss-c " + ev.status[i] + (i === state.poison ? " poison" : "") });
      card.appendChild(el("b", {}, name(i) + (i === state.poison ? " (poison)" : "")));
      var chips = el("span", { "class": "ss-chips" });
      set.forEach(function (x) { chips.appendChild(el("span", { "class": "ss-chip " + (ev.dead[x] ? "dead" : "") }, String(x))); });
      card.appendChild(chips);
      card.appendChild(el("em", {}, ev.status[i] === "ok" ? "fine" : ev.status[i]));
      list.appendChild(card);
    });
    var others = CUSTOMERS - 1;
    verdict.textContent = "Besides the poison customer: " + down + " of " + others + " customers fully down, " + deg + " degraded, " + (others - down - deg) + " untouched.";
    verdict.className = "ss-verdict " + (down ? "bad" : deg ? "warn" : "ok");
    var shards = state.mode === "classic" ? Math.max(1, Math.floor(n / k)) : choose(n, k);
    math.textContent = state.mode === "classic"
      ? "Classic: " + shards + " fixed shards, so a random other customer shares the poison shard with probability 1/" + shards + " = " + (100 / shards).toFixed(1) + "%." + (n % k ? " (" + (n % k) + " worker" + (n % k > 1 ? "s" : "") + " left over by the split serve no one in this demo.)" : "")
      : "Shuffle: C(" + n + "," + k + ") = " + shards + " possible shards, so with purely random assignment a given other customer would hold exactly the poison customer's shard with probability 1/" + shards + " = " + (100 / shards).toFixed(1) + "%. This demo gives the 16 customers distinct shards, so none can match in full; partial overlap is far more common.";
  }
  function fillPoison() {
    pSel.textContent = "";
    for (var c = 0; c < CUSTOMERS; c++) pSel.appendChild(el("option", { value: String(c) }, name(c)));
    pSel.value = String(state.poison);
  }
  function fillK() {
    kSel.value = String(state.k);
  }
  fillPoison(); fillK();
  modeSel.addEventListener("change", function () { state.mode = modeSel.value; render(); });
  nSel.addEventListener("change", function () { state.n = parseInt(nSel.value, 10); render(); });
  kSel.addEventListener("change", function () { state.k = parseInt(kSel.value, 10); render(); });
  pSel.addEventListener("change", function () { state.poison = parseInt(pSel.value, 10); render(); });
  rerollBtn.addEventListener("click", function () { state.seed += 17; render(); });
  render();
})();
