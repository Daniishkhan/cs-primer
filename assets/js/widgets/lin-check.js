/* Linearizability checker widget (distributed course, chapter 5).

   A history of operations on ONE register (initial value 0) is drawn as bars on per-client
   timelines. Each bar runs from the moment the client sent the request to the moment it
   got the answer. Operations are  w(v)  (write v)  and  r->v  (a read that returned v).

   Two ways to use it:
     1. "Build an order": click bars (or the buttons under the picture) one at a time to
        build a single sequential order. Each pick is checked at once and refused with a
        reason if it breaks the rules of the chosen model:
          Linearizable           - an operation that FINISHED before another one STARTED must
                                   come first (real-time order), and each read must return the
                                   latest value written.
          Sequentially consistent - only each client's own order is kept; real time is ignored.
        In linearizable mode every accepted pick also gets a "linearization point": a dot on
        its bar showing an instant inside the interval at which it can be said to take effect.
     2. "Search": runs the same backtracking search as the checker in the chapter (Wing and
        Gong style: try every operation that may go next, recurse, and remember dead ends) and
        either shows a legal order or explains where every attempt got stuck.

   No randomness, no network, no storage. Honours prefers-reduced-motion (there is no
   animation). Bars are real focusable controls (Enter or Space picks them). */
(function () {
  "use strict";
  var root = document.getElementById("lin-check");
  if (!root) return;

  /* ---------- presets ---------- */
  // c = client, k = "w" or "r", v = value written / value the read returned, s = start, e = end (time units 0..10)
  var PRESETS = [
    { id: "overlap", whySeq: "Without the real-time rule the same order still works, so the history is sequentially consistent as well.", title: "Overlapping write and reads",
      blurb: "One slow write overlaps three reads. Reads that overlap a write may see either the old or the new value.",
      ops: [ { c: "A", k: "w", v: 1, s: 1, e: 8 }, { c: "B", k: "r", v: 0, s: 1.5, e: 3.5 },
             { c: "C", k: "r", v: 1, s: 4, e: 6.5 }, { c: "B", k: "r", v: 1, s: 5, e: 7 } ],
      why: "A legal story exists: B's first read happens before the write takes effect, then the write, then both later reads. Nothing finished before another started in a way that contradicts it." },
    { id: "stale", whySeq: "Sequential consistency ignores real time. B and A are different clients, so B's read may be placed before A's write, and the history is allowed. This is exactly the gap between the two models.", title: "Stale read after a completed write",
      blurb: "A's write is acknowledged at time 3. B asks at time 4 and is told 0.",
      ops: [ { c: "A", k: "w", v: 1, s: 1, e: 3 }, { c: "B", k: "r", v: 0, s: 4, e: 6 } ],
      why: "The write finished before the read started, so real-time order forces the write first, and then the read must return 1. But it returned 0. Sequential consistency allows this history: it may place B's read before A's write, because B and A are different clients and real time does not count." },
    { id: "inversion", whySeq: "Sequential consistency ignores real time, so the order r\u21920 (C), w(1) (A), r\u21921 (B) is allowed: each client sees a sensible story and nobody's own order is broken.", title: "New/old inversion",
      blurb: "One long write. B reads 1 and finishes. Then C starts a read and sees 0.",
      ops: [ { c: "A", k: "w", v: 1, s: 1, e: 9 }, { c: "B", k: "r", v: 1, s: 2, e: 4 }, { c: "C", k: "r", v: 0, s: 5, e: 7 } ],
      why: "B's read returned 1, so the write took effect at or before time 4. C started at time 5, after B finished, so C must also see 1. The value went forward and then backward, which no single copy could do. (Sequential consistency allows it: put C's read first.)" },
    { id: "own", whySeq: "Still not allowed: A's own program order puts the write before the read, and nothing else ever writes. Even the weaker model forbids this.", title: "A client loses its own write",
      blurb: "A writes 1, gets the acknowledgement, and then reads 0.",
      ops: [ { c: "A", k: "w", v: 1, s: 1, e: 2 }, { c: "A", k: "r", v: 0, s: 3, e: 4 } ],
      why: "This breaks even sequential consistency: A's own program order says the write comes before the read, and nothing else ever writes, so the read must return 1. Violations like this are the 'read-your-writes' failures of the next chapter." },
    { id: "twowrites", whySeq: "Allowed here too: the same order works when real time is ignored.", title: "Two overlapping writes (legal)",
      blurb: "Writes of 1 and 2 overlap. Readers see 2, then 1, then 1.",
      ops: [ { c: "A", k: "w", v: 1, s: 0.5, e: 10 }, { c: "B", k: "w", v: 2, s: 1, e: 9 },
             { c: "C", k: "r", v: 2, s: 2, e: 4 }, { c: "D", k: "r", v: 1, s: 5, e: 7 }, { c: "E", k: "r", v: 1, s: 8, e: 9.5 } ],
      why: "Legal: the two writes overlap, so the system may choose either order. Here it chose write(2) first, then write(1), so the final value is 1. Every reader is consistent with that one choice." },
    { id: "twowrites-bad", whySeq: "Allowed under sequential consistency. Every operation is by a different client, so there are no program-order constraints at all, and an order such as w(1), r\u21921, w(2), r\u21922, r\u21922 is fine. Real time is the only thing that rules it out under linearizability.", title: "Two overlapping writes (broken)",
      blurb: "Same writes, but the last read returns 2 after an earlier read already saw 1.",
      ops: [ { c: "A", k: "w", v: 1, s: 0.5, e: 10 }, { c: "B", k: "w", v: 2, s: 1, e: 9 },
             { c: "C", k: "r", v: 2, s: 2, e: 4 }, { c: "D", k: "r", v: 1, s: 5, e: 7 }, { c: "E", k: "r", v: 2, s: 8, e: 9.5 } ],
      why: "C saw 2 before time 4, so write(2) came first. D then saw 1 (finished at 7), so write(1) came after it. E started at 8 and sees 2 again, but nothing writes 2 after write(1). The two writes would have to be ordered both ways at once." }
  ];

  /* ---------- state ---------- */
  var cur = 0;               // preset index
  var mode = "lin";          // "lin" or "seq"
  var picked = [];           // indices of ops, in the order the reader chose
  var msg = { text: "", kind: "info" };
  var found = null;          // result of the search, or null

  function ops() { return PRESETS[cur].ops; }
  function why() { return mode === "seq" ? PRESETS[cur].whySeq : PRESETS[cur].why; }

  /* ---------- the rules ---------- */
  function regAfter(order) {
    var v = 0, o = ops();
    for (var i = 0; i < order.length; i++) { var p = o[order[i]]; if (p.k === "w") v = p.v; }
    return v;
  }

  // Why may operation i NOT go next, given the set `done` of already placed indices? Returns "" if it may.
  function blocker(i, done, value) {
    var o = ops(), a = o[i], j;
    for (j = 0; j < o.length; j++) {
      if (j === i || done.indexOf(j) >= 0) continue;
      var b = o[j];
      if (mode === "lin" && b.e < a.s) return label(j) + " finished (at " + b.e + ") before " + label(i) + " started (at " + a.s + "), so " + label(j) + " must come first.";
      if (mode === "seq" && b.c === a.c && b.s < a.s) return "client " + a.c + " issued " + label(j) + " before " + label(i) + ", and a client's own order is always kept.";
    }
    if (a.k === "r" && a.v !== value) return "it returned " + a.v + ", but the register holds " + value + " at this point in the order.";
    return "";
  }

  function label(i) {
    var p = ops()[i];
    return p.c + ":" + (p.k === "w" ? "write(" + p.v + ")" : "read→" + p.v);
  }
  function short(i) { var p = ops()[i]; return p.k === "w" ? "w(" + p.v + ")" : "r→" + p.v; }

  /* ---------- search (same idea as the Python checker in the chapter) ---------- */
  function search() {
    var o = ops(), n = o.length, dead = {}, states = 0, best = [];
    function go(order, mask, value) {
      states++;
      if (order.length > best.length) best = order.slice();
      if (order.length === n) return order.slice();
      var key = mask + ":" + value;
      if (dead[key]) return null;
      for (var i = 0; i < n; i++) {
        if (mask & (1 << i)) continue;
        if (blocker(i, order, value)) continue;
        var nv = o[i].k === "w" ? o[i].v : value;
        order.push(i);
        var r = go(order, mask | (1 << i), nv);
        order.pop();
        if (r) return r;
      }
      dead[key] = true;
      return null;
    }
    var res = go([], 0, 0);
    return { order: res, states: states, best: best };
  }

  // Greedy linearization points for a valid real-time order.
  function points(order) {
    var o = ops(), t = -1, out = {};
    for (var k = 0; k < order.length; k++) {
      var p = o[order[k]];
      t = Math.max(p.s, t + 0.04);
      out[order[k]] = t;
    }
    return out;
  }

  /* ---------- actions ---------- */
  function reset(keepMsg) {
    picked = []; found = null;
    if (!keepMsg) setMsg("Pick operations one at a time, in the order they could have taken effect. Start with the one that must be first.", "info");
  }
  function setMsg(text, kind) { msg = { text: text, kind: kind || "info" }; }

  function pick(i) {
    if (picked.indexOf(i) >= 0) { setMsg(label(i) + " is already in the order. Use Undo to take it back.", "info"); render(); return; }
    found = null;
    var why = blocker(i, picked, regAfter(picked));
    if (why) { setMsg("Not allowed: " + label(i) + " cannot go next. " + why, "bad"); render(); return; }
    picked.push(i);
    if (picked.length === ops().length) {
      setMsg(mode === "lin"
        ? "Done. This is a legal linearization: one order that respects real time, in which every read returns the latest write. The dots are the linearization points."
        : "Done. This order respects each client's own order and every read returns the latest write, so the history is sequentially consistent.", "good");
    } else {
      setMsg("Accepted: " + label(i) + ". The register now holds " + regAfter(picked) + ".", "good");
    }
    render();
  }

  function undo() { if (picked.length) { picked.pop(); found = null; setMsg("Took back the last pick.", "info"); } render(); }

  function runSearch() {
    var r = search();
    found = r;
    if (r.order) {
      picked = r.order.slice();
      setMsg("Yes. Searched " + r.states + " partial orders and found a legal one: " + r.order.map(short).join(", then ") + ". " + why(), "good");
    } else {
      picked = r.best.slice();
      var value = regAfter(picked), stuck = [], o = ops(), i;
      for (i = 0; i < o.length; i++) if (picked.indexOf(i) < 0) stuck.push(label(i) + " cannot go next: " + blocker(i, picked, value));
      setMsg("No. The search tried " + r.states + " partial orders and none could place every operation. The furthest it got was " +
        (picked.length ? picked.map(short).join(", then ") : "(nothing)") + ", where it was stuck: " + stuck.join(" ") + " " + why(), "bad");
    }
    render();
  }

  /* ---------- DOM helpers ---------- */
  var NS = "http://www.w3.org/2000/svg";
  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function sv(tag, attrs, text) {
    var e = document.createElementNS(NS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (text != null) e.textContent = text;
    return e;
  }
  function button(text, cls, fn) { var b = el("button", "btn " + (cls || ""), text); b.type = "button"; b.addEventListener("click", fn); return b; }

  /* ---------- build UI ---------- */
  root.textContent = "";
  var head = el("div", "widget-head");
  head.appendChild(el("span", "widget-tag", "Checker"));
  head.appendChild(el("h4", "widget-title", "Is this history linearizable?"));
  root.appendChild(head);
  root.appendChild(el("p", "widget-help", "Bars are operations on one register that starts at 0, drawn from request sent to answer received. Build a sequential order by clicking bars, or press Search. Switch the model to see which histories sequential consistency still allows."));

  var row1 = el("div", "widget-row lc-row");
  var selLabel = el("label", "lc-sel");
  selLabel.appendChild(el("span", null, "History"));
  var sel = el("select"); sel.id = "lc-preset";
  PRESETS.forEach(function (p, i) { var op = el("option", null, p.title); op.value = String(i); sel.appendChild(op); });
  sel.addEventListener("change", function () { cur = +sel.value; reset(); render(); });
  selLabel.appendChild(sel);
  row1.appendChild(selLabel);
  var modeBox = el("div", "lc-modes");
  modeBox.setAttribute("role", "group"); modeBox.setAttribute("aria-label", "Consistency model");
  var bLin = button("Linearizable", "small", function () { mode = "lin"; reset(); render(); });
  var bSeq = button("Sequentially consistent", "small", function () { mode = "seq"; reset(); render(); });
  modeBox.appendChild(bLin); modeBox.appendChild(bSeq);
  row1.appendChild(modeBox);
  root.appendChild(row1);

  var blurb = el("p", "lc-blurb");
  root.appendChild(blurb);

  var scroll = el("div", "lc-scroll");
  var svgHost = el("div", "lc-svg");
  scroll.appendChild(svgHost);
  root.appendChild(scroll);

  var opsLabel = el("div", "lc-label", "Operations (click to add to the order)");
  root.appendChild(opsLabel);
  var opsBox = el("div", "lc-ops");
  root.appendChild(opsBox);

  var orderLabel = el("div", "lc-label", "Your order");
  root.appendChild(orderLabel);
  var orderBox = el("div", "lc-order");
  root.appendChild(orderBox);

  var row2 = el("div", "widget-row lc-row");
  row2.appendChild(button("Search", "primary small", runSearch));
  row2.appendChild(button("Undo", "small", undo));
  row2.appendChild(button("Reset", "small", function () { reset(); render(); }));
  root.appendChild(row2);

  var status = el("div", "lc-status");
  status.setAttribute("role", "status"); status.setAttribute("aria-live", "polite");
  root.appendChild(status);

  /* ---------- render ---------- */
  var X0 = 56, UNIT = 62, LANE = 50, TOP = 14;
  function xOf(t) { return X0 + t * UNIT; }

  function render() {
    var preset = PRESETS[cur], o = preset.ops, i;
    bLin.setAttribute("aria-pressed", mode === "lin" ? "true" : "false");
    bSeq.setAttribute("aria-pressed", mode === "seq" ? "true" : "false");
    blurb.textContent = preset.blurb;

    var clients = [];
    o.forEach(function (p) { if (clients.indexOf(p.c) < 0) clients.push(p.c); });
    var H = TOP + clients.length * LANE + 42;
    var svg = sv("svg", { viewBox: "0 0 700 " + H, role: "img", "aria-label": "Timeline of " + o.length + " operations by " + clients.length + " clients: " + o.map(function (p, k) { return label(k) + " from " + p.s + " to " + p.e; }).join("; ") });
    svg.style.minWidth = "560px";
    var pts = (mode === "lin") ? points(picked) : {};

    // lanes
    clients.forEach(function (c, li) {
      var y = TOP + li * LANE;
      svg.appendChild(sv("line", { x1: X0, y1: y + LANE - 6, x2: 690, y2: y + LANE - 6, "class": "line-thin" }));
      svg.appendChild(sv("text", { x: 8, y: y + 28, "class": "t-sm t-bold tc-green" }, "client " + c));
    });
    // time axis
    var ay = TOP + clients.length * LANE + 6;
    svg.appendChild(sv("line", { x1: X0, y1: ay, x2: 690, y2: ay, "class": "line" }));
    for (var t = 0; t <= 10; t += 2) {
      svg.appendChild(sv("line", { x1: xOf(t), y1: ay - 4, x2: xOf(t), y2: ay + 4, "class": "line-thin" }));
      svg.appendChild(sv("text", { x: xOf(t), y: ay + 18, "text-anchor": "middle", "class": "t-xs t-muted" }, String(t)));
    }
    svg.appendChild(sv("text", { x: 690, y: ay + 30, "text-anchor": "end", "class": "t-xs t-faint" }, "real time →"));

    // bars
    o.forEach(function (p, k) {
      var li = clients.indexOf(p.c), y = TOP + li * LANE + 6, x1 = xOf(p.s), x2 = xOf(p.e);
      var rank = picked.indexOf(k);
      var cls = rank >= 0 ? "fs-green s-green" : (p.k === "w" ? "fs-purple s-purple" : "fs-blue s-blue");
      var g = sv("g", { "class": "lc-bar", tabindex: "0", role: "button", "aria-label": label(k) + ", from " + p.s + " to " + p.e + (rank >= 0 ? ", placed number " + (rank + 1) : ", not yet placed") });
      g.appendChild(sv("rect", { x: x1, y: y, width: x2 - x1, height: 28, rx: 6, "class": cls + " sw-2" }));
      g.appendChild(sv("text", { x: (x1 + x2) / 2, y: y + 18, "text-anchor": "middle", "class": "t-sm t-bold mono" }, short(k)));
      if (rank >= 0) {
        g.appendChild(sv("circle", { cx: x1 + 2, cy: y - 2, r: 8, "class": "f-green" }));
        g.appendChild(sv("text", { x: x1 + 2, y: y + 2, "text-anchor": "middle", "class": "t-xs t-bold t-dark" }, String(rank + 1)));
      }
      if (pts[k] != null) {
        var px = xOf(pts[k]);
        g.appendChild(sv("line", { x1: px, y1: y + 28, x2: px, y2: y + 38, "class": "line" }));
        g.appendChild(sv("circle", { cx: px, cy: y + 40, r: 4, "class": "f-yellow s-yellow" }));
      }
      g.addEventListener("click", function () { pick(k); });
      g.addEventListener("keydown", function (ev) { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); pick(k); } });
      svg.appendChild(g);
    });
    svgHost.textContent = "";
    svgHost.appendChild(svg);

    // operation buttons
    opsBox.textContent = "";
    o.forEach(function (p, k) {
      var b = button(label(k), "small lc-opbtn", function () { pick(k); });
      if (picked.indexOf(k) >= 0) { b.disabled = true; }
      b.setAttribute("title", "from " + p.s + " to " + p.e);
      opsBox.appendChild(b);
    });

    // order chips
    orderBox.textContent = "";
    if (!picked.length) orderBox.appendChild(el("span", "lc-empty", "(nothing placed yet)"));
    picked.forEach(function (k, r) {
      var chip = el("span", "pill lc-chip", (r + 1) + ". " + label(k));
      orderBox.appendChild(chip);
    });
    if (mode === "lin" && picked.length) orderBox.appendChild(el("span", "lc-note", "Yellow dots on the bars mark each linearization point."));

    status.textContent = msg.text;
    status.className = "lc-status lc-" + msg.kind;
  }

  reset();
  render();
})();
