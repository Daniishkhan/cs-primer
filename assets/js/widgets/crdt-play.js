/* CRDT playground (distributed chapter 15).

   Three replicas (A, B, C) of one CRDT. Edits happen locally and instantly; nothing travels
   between replicas until YOU press a merge button ("B <- A" means B merges A's current
   state into its own). So you control exactly which messages arrive, and in what order.

   Four types:
     G-Counter   one slot per replica, merge = pointwise max
     PN-Counter  two G-Counters, value = increments - decrements
     LWW register  keeps the write with the largest (timestamp, replica id); you can make
                   replica B's clock slow or fast to see the clock dependence
     OR-set      every add makes a unique tag; remove deletes only the tags it has seen

   The status line says whether all three replicas hold the identical state. Whatever
   sequence of merges you press, once every replica has seen every state they converge:
   merge is commutative, associative and idempotent.

   Simplified: the replicas' "wall clock" is a counter that advances 10 s per edit; each
   replica adds its own skew (LWW only). No randomness anywhere.
*/
(function () {
  "use strict";
  var root = document.getElementById("crdt-play");
  if (!root) return;

  var R = ["A", "B", "C"];
  var TYPES = {
    gc: { label: "G-Counter" },
    pn: { label: "PN-Counter" },
    lww: { label: "LWW register" },
    or: { label: "OR-set" }
  };
  var type = "gc", S, now, skew, seq, note;

  function zero() { return { A: 0, B: 0, C: 0 }; }
  function fresh(t) {
    now = 0; seq = { A: 0, B: 0, C: 0 };
    var s = {};
    R.forEach(function (r) {
      if (t === "gc") s[r] = { slots: zero() };
      else if (t === "pn") s[r] = { p: zero(), n: zero() };
      else if (t === "lww") s[r] = { v: null, ts: -1e9, by: "" };
      else s[r] = { adds: [], tombs: [] };
    });
    return s;
  }
  function clone(x) { return JSON.parse(JSON.stringify(x)); }
  function maxInto(a, b) { R.forEach(function (r) { a[r] = Math.max(a[r], b[r]); }); }

  function merge(t, dst, src) {
    if (t === "gc") maxInto(dst.slots, src.slots);
    else if (t === "pn") { maxInto(dst.p, src.p); maxInto(dst.n, src.n); }
    else if (t === "lww") {
      if (src.ts > dst.ts || (src.ts === dst.ts && src.by > dst.by)) { dst.v = src.v; dst.ts = src.ts; dst.by = src.by; }
    } else {
      src.adds.forEach(function (a) { if (!dst.adds.some(function (b) { return b.tag === a.tag; })) dst.adds.push({ e: a.e, tag: a.tag }); });
      src.tombs.forEach(function (tg) { if (dst.tombs.indexOf(tg) < 0) dst.tombs.push(tg); });
    }
  }
  function sum(o) { return R.reduce(function (a, r) { return a + o[r]; }, 0); }
  function orElems(s) {
    var out = {};
    s.adds.forEach(function (a) { if (s.tombs.indexOf(a.tag) < 0) out[a.e] = 1; });
    return Object.keys(out).sort();
  }
  function describe(t, s) {
    if (t === "gc") return { state: "slots  A=" + s.slots.A + "  B=" + s.slots.B + "  C=" + s.slots.C, value: String(sum(s.slots)) };
    if (t === "pn") return { state: "P (adds)  A=" + s.p.A + " B=" + s.p.B + " C=" + s.p.C + "\nN (subs)  A=" + s.n.A + " B=" + s.n.B + " C=" + s.n.C, value: String(sum(s.p) - sum(s.n)) };
    if (t === "lww") return { state: s.by ? "stamp (t=" + s.ts + "s, " + s.by + ")" : "never written", value: s.v === null ? "(empty)" : '"' + s.v + '"' };
    var lines = ["x", "y"].map(function (e) {
      var tags = s.adds.filter(function (a) { return a.e === e; }).map(function (a) { return a.tag + (s.tombs.indexOf(a.tag) >= 0 ? "✗" : ""); });
      return e + ": " + (tags.length ? tags.join(" ") : "-");
    });
    var el = orElems(s);
    return { state: lines.join("\n") + "\n(✗ = tombstoned tag)", value: "{" + el.join(", ") + "}" };
  }
  function canon(t, s) {
    if (t === "or") return JSON.stringify({ a: s.adds.map(function (a) { return a.tag; }).sort(), t: s.tombs.slice().sort() });
    return JSON.stringify(s);
  }

  /* ---------- operations ---------- */
  function tick() { now += 10; }
  function op(r, name, arg) {
    var s = S[r], t = type;
    tick();
    if (t === "gc") { s.slots[r] += 1; note = r + " counts one: its own slot becomes " + s.slots[r] + "."; }
    else if (t === "pn") {
      if (name === "inc") { s.p[r] += 1; note = r + " adds one (its P slot is " + s.p[r] + ")."; }
      else { s.n[r] += 1; note = r + " subtracts one (its N slot is " + s.n[r] + ")."; }
    } else if (t === "lww") {
      var ts = now + (r === "B" ? skew : 0);
      s.v = arg; s.ts = ts; s.by = r;
      note = r + " writes \"" + arg + "\" with timestamp " + ts + "s" + (r === "B" && skew !== 0 ? " (B's clock is " + (skew < 0 ? "slow" : "fast") + " by " + Math.abs(skew) + "s)." : ".");
    } else if (name === "add") {
      seq[r] += 1; var tag = r + seq[r];
      s.adds.push({ e: arg, tag: tag });
      note = r + " adds " + arg + " with the fresh tag " + tag + ".";
    } else {
      var seen = s.adds.filter(function (a) { return a.e === arg && s.tombs.indexOf(a.tag) < 0; }).map(function (a) { return a.tag; });
      seen.forEach(function (tg) { s.tombs.push(tg); });
      note = seen.length ? r + " removes " + arg + ": it tombstones only the tags it can see (" + seen.join(", ") + ")." : r + " has no live " + arg + " to remove, so the remove does nothing.";
    }
    draw();
  }
  function sync(dst, src) {
    var before = canon(type, S[dst]);
    merge(type, S[dst], S[src]);
    note = dst + " merges " + src + "'s state" + (canon(type, S[dst]) === before ? ": no change (already knew all of it)." : ".");
    draw();
  }
  function syncAll(order) {
    for (var pass = 0; pass < 2; pass++) order.forEach(function (d) { order.forEach(function (s) { if (d !== s) merge(type, S[d], S[s]); }); });
    note = "Everyone merged everyone, in the order " + order.join(", ") + ".";
    draw();
  }

  /* ---------- presets ---------- */
  var PRE = {
    gc: [
      { label: "Counting while apart", hint: "A counted 3, B counted 2, C counted 1, all offline. Now press \"Everyone merges everyone\" in either order: the total is 6. Merge A into B twice and see that the second one changes nothing.",
        run: function () { for (var i = 0; i < 3; i++) op("A", "inc"); for (i = 0; i < 2; i++) op("B", "inc"); op("C", "inc"); } }
    ],
    pn: [
      { label: "Adds and subtracts", hint: "A adds twice, B subtracts once, C adds once. After everyone merges, the value is 2 (3 adds minus 1 subtract) in any order.",
        run: function () { op("A", "inc"); op("A", "inc"); op("B", "dec"); op("C", "inc"); } }
    ],
    lww: [
      { label: "Honest clocks", hint: "A writes red, then B writes blue later. Merge everyone: blue wins, as you would hope.", skew: 0,
        run: function () { op("A", "set", "red"); op("B", "set", "blue"); } },
      { label: "B's clock is 60 s slow", hint: "B wrote blue AFTER A wrote red, but B's clock is slow, so blue gets the older timestamp. Merge everyone: red wins and blue is silently lost.", skew: -60,
        run: function () { op("A", "set", "red"); op("B", "set", "blue"); } }
    ],
    or: [
      { label: "Concurrent add and remove", hint: "A adds x (tag A1); B receives it and removes x; meanwhile A adds x again (tag A2). Now merge everyone: x is present, because B's remove only covered A1. Add wins over a concurrent remove.",
        run: function () { op("A", "add", "x"); sync("B", "A"); op("B", "remove", "x"); op("A", "add", "x"); note = "Setup done: B removed the A1 copy of x while A added a new copy (A2). Press \"Everyone merges everyone\"."; } }
    ]
  };

  /* ---------- UI ---------- */
  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function btn(label, fn, cls) { var b = el("button", "btn small" + (cls ? " " + cls : ""), label); b.type = "button"; b.addEventListener("click", fn); return b; }

  var head = el("div", "widget-head");
  head.appendChild(el("span", "widget-tag", "Playground"));
  head.appendChild(el("h4", "widget-title", "Three replicas, you choose every merge"));
  root.appendChild(head);
  root.appendChild(el("p", "widget-help", "Edit any replica; nothing travels until you press a merge button. Try different merge orders and repeated merges, and watch whether the replicas end up identical."));

  var tabs = el("div", "widget-row cp-tabs");
  var tabBtns = {};
  Object.keys(TYPES).forEach(function (k) {
    var b = btn(TYPES[k].label, function () { switchType(k); });
    b.setAttribute("aria-pressed", "false"); tabBtns[k] = b; tabs.appendChild(b);
  });
  root.appendChild(tabs);

  var presetRow = el("div", "widget-row"); root.appendChild(presetRow);
  var skewRow = el("div", "widget-row cp-skew");
  var skewSel = el("select");
  [["0", "B's clock is accurate"], ["-60", "B's clock is 60 s slow"], ["60", "B's clock is 60 s fast"]].forEach(function (o) { var op_ = el("option", null, o[1]); op_.value = o[0]; skewSel.appendChild(op_); });
  skewSel.addEventListener("change", function () { skew = parseInt(skewSel.value, 10); });
  skewRow.appendChild(skewSel); root.appendChild(skewRow);

  var grid = el("div", "cp-grid"); root.appendChild(grid);
  var mergeRow = el("div", "cp-merges"); root.appendChild(mergeRow);
  var status = el("div", "widget-out cp-status"); status.setAttribute("aria-live", "polite"); root.appendChild(status);
  var hint = el("p", "widget-help cp-hint"); root.appendChild(hint);

  function opButtons(r) {
    var row = el("div", "cp-ops");
    if (type === "gc") row.appendChild(btn("+1", function () { op(r, "inc"); }));
    else if (type === "pn") { row.appendChild(btn("+1", function () { op(r, "inc"); })); row.appendChild(btn("−1", function () { op(r, "dec"); })); }
    else if (type === "lww") ["red", "green", "blue"].forEach(function (c) { row.appendChild(btn("write " + c, function () { op(r, "set", c); })); });
    else ["x", "y"].forEach(function (e) { row.appendChild(btn("add " + e, function () { op(r, "add", e); })); row.appendChild(btn("remove " + e, function () { op(r, "remove", e); })); });
    return row;
  }

  function buildStatic() {
    grid.innerHTML = ""; mergeRow.innerHTML = ""; presetRow.innerHTML = "";
    R.forEach(function (r) {
      var c = el("div", "cp-card"); c.dataset.r = r;
      c.appendChild(el("div", "cp-card-h", "Replica " + r));
      c.appendChild(el("pre", "cp-state"));
      var v = el("div", "cp-value"); c.appendChild(v);
      c.appendChild(opButtons(r));
      grid.appendChild(c);
    });
    var lab = el("span", "cp-lab", "Send state:"); mergeRow.appendChild(lab);
    R.forEach(function (d) { R.forEach(function (s) { if (d !== s) mergeRow.appendChild(btn(d + " ← " + s, function () { sync(d, s); })); }); });
    var all = el("div", "widget-row");
    all.appendChild(btn("Everyone merges everyone (A, B, C)", function () { syncAll(["A", "B", "C"]); }, "primary"));
    all.appendChild(btn("… in the order C, B, A", function () { syncAll(["C", "B", "A"]); }));
    mergeRow.appendChild(all);
    PRE[type].forEach(function (p) {
      presetRow.appendChild(btn("Scenario: " + p.label, function () {
        S = fresh(type); if (p.skew !== undefined) { skew = p.skew; skewSel.value = String(p.skew); }
        note = ""; p.run(); hint.textContent = p.hint; draw(true);
      }));
    });
    presetRow.appendChild(btn("Reset", function () { S = fresh(type); note = "Reset: all replicas empty."; hint.textContent = ""; draw(); }));
    skewRow.style.display = type === "lww" ? "" : "none";
  }

  function draw(keepNote) {
    var states = {};
    R.forEach(function (r) {
      var c = grid.querySelector('[data-r="' + r + '"]'), d = describe(type, S[r]);
      c.querySelector(".cp-state").textContent = d.state;
      c.querySelector(".cp-value").textContent = "value: " + d.value;
      states[r] = canon(type, S[r]);
    });
    var same = states.A === states.B && states.B === states.C;
    var vals = R.map(function (r) { return r + "=" + describe(type, S[r]).value; }).join("   ");
    status.className = "widget-out cp-status " + (same ? "ok" : "diff");
    status.textContent = (note ? note + "  " : "") + (same ? "Converged: all three replicas hold the identical state (" + vals + ")." : "Diverged: " + vals + ".");
    R.forEach(function (r) { grid.querySelector('[data-r="' + r + '"]').classList.toggle("same", same); });
  }

  function switchType(k) {
    type = k; S = fresh(k); skew = 0; skewSel.value = "0"; note = "";
    Object.keys(tabBtns).forEach(function (t) { tabBtns[t].setAttribute("aria-pressed", t === k ? "true" : "false"); });
    buildStatic(); hint.textContent = "Start with a scenario, or make your own edits."; draw();
  }
  switchType("gc");
})();
