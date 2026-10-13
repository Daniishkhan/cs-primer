/* Lease & fencing timeline (distributed chapter 4).

   Client A is granted a lease with fencing token 33 at t = 0; it lasts TTL seconds.
   Shortly before it runs out (t = TTL - 1 s) A decides to write to the storage. Something
   delays that write; pick what:
     pause    A passes its own "is my lease still valid?" check and then freezes for P seconds
              (a stop-the-world GC pause, a VM migration) before the write is sent;
     delay    A checks, sends the write at once, and the network holds the packet for D seconds;
     clock    A's clock jumps back by J seconds early in the lease (a bad NTP step), so at
              t = TTL + 2 A still believes it holds the lease.
   When A's lease expires the lock service grants a new lease with token 34 to client B at
   t = TTL + 0.5. B's first request to the storage (a read) arrives 0.2 s later and carries
   token 34; B's write follows 0.8 s after that.

   The storage either ignores tokens (fencing off) or remembers the highest token seen and
   rejects any request with a smaller one (fencing on). The optional client-side check makes
   A look at its own clock before writing; the widget shows when that helps and when it is
   useless (the check can pass and the write still arrive late).

   Notes on the model: no lease renewals are shown (the interesting case is the one where the
   pause swallows the renewal); the storage records token 34 when B's read arrives, which is
   why a stale write that lands BEFORE B has touched the storage is still accepted (it is
   then visible to B's read, so no update is lost). All timings are exact; nothing is random. */
(function () {
  "use strict";
  var root = document.getElementById("lease-fence");
  if (!root) return;
  var NS = "http://www.w3.org/2000/svg";
  function h(tag, attrs, text) {
    var e = document.createElement(tag);
    if (attrs) for (var k in attrs) { if (k === "class") e.className = attrs[k]; else e.setAttribute(k, attrs[k]); }
    if (text != null) e.textContent = text;
    return e;
  }
  function s(tag, attrs, text) {
    var e = document.createElementNS(NS, tag);
    if (attrs) for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (text != null) e.textContent = text;
    return e;
  }
  function clear(e) { while (e.firstChild) e.removeChild(e.firstChild); }
  function f1(x) { return (Math.round(x * 10) / 10).toFixed(1); }

  var head = h("div", { class: "widget-head" });
  head.appendChild(h("span", { class: "widget-tag" }, "Simulator"));
  head.appendChild(h("h4", { class: "widget-title" }, "The lease that expired in the middle of a write"));
  root.appendChild(head);

  var ctl = h("div", { class: "lf-controls" });
  function field(label, node, extra) {
    var w = h("label", { class: "lf-ctl" });
    w.appendChild(h("span", { class: "lf-ctl-l" }, label));
    w.appendChild(node);
    if (extra) w.appendChild(extra);
    ctl.appendChild(w);
    return w;
  }
  var selS = h("select");
  [["pause", "A freezes (GC pause)"], ["delay", "A's packet is delayed"], ["clock", "A's clock jumps back"]].forEach(function (o) { selS.appendChild(h("option", { value: o[0] }, o[1])); });
  var rTtl = h("input", { type: "range", min: 6, max: 20, value: 10, step: 1 });
  var vTtl = h("span", { class: "lf-val" }, "10 s");
  var rX = h("input", { type: "range", min: 1, max: 20, value: 12, step: 1 });
  var vX = h("span", { class: "lf-val" }, "12 s");
  field("Scenario", selS);
  var lblX = field("Pause length", rX, vX).firstChild;
  field("Lease length", rTtl, vTtl);
  root.appendChild(ctl);
  var chk = h("div", { class: "lf-checks" });
  function check(label) {
    var w = h("label", { class: "lf-check" });
    var i = h("input", { type: "checkbox" });
    w.appendChild(i); w.appendChild(h("span", null, label));
    chk.appendChild(w);
    return i;
  }
  var cFence = check("Storage rejects stale fencing tokens");
  var cClient = check("Client A checks its own clock before writing");
  root.appendChild(chk);

  var box = h("div", { class: "lf-box" });
  var svg = s("svg", { viewBox: "0 0 720 330", role: "img", "aria-label": "Timeline of client A, the lock service, client B and the storage" });
  box.appendChild(svg);
  root.appendChild(box);
  var verdict = h("p", { class: "lf-verdict", "aria-live": "polite" });
  root.appendChild(verdict);
  var logHead = h("h5", { class: "lf-logh" }, "What happens, in order");
  root.appendChild(logHead);
  var log = h("ol", { class: "lf-log" });
  root.appendChild(log);

  var X0 = 112, X1 = 704;
  var LANES = { A: 52, L: 118, B: 184, S: 258 };
  function compute() {
    var sc = selS.value, T = parseInt(rTtl.value, 10), X = parseInt(rX.value, 10);
    var fencing = cFence.checked, cc = cClient.checked;
    var r = { sc: sc, T: T, X: X, fencing: fencing, cc: cc, ev: [] };
    var tCheck = sc === "clock" ? T + 2 : T - 1;
    var jump = sc === "clock" ? X : 0;
    var viewValid = sc === "clock" ? (T + 2 - jump) < T : tCheck < T;   // what A's own clock says
    r.tCheck = tCheck; r.viewValid = viewValid;
    r.tB = T + 0.5; r.tBread = r.tB + 0.2; r.tBwrite = r.tBread + 0.8;
    r.aWrites = true;
    if (cc && !viewValid) r.aWrites = false;
    if (sc === "pause") { r.tSend = tCheck + X; r.tArr = r.tSend + 0.1; }
    else if (sc === "delay") { r.tSend = tCheck; r.tArr = tCheck + X; }
    else { r.tSend = tCheck; r.tArr = tCheck + 0.1; }
    // storage decisions
    var seenB = r.tArr > r.tBread;                      // has the storage heard token 34 yet?
    r.late = r.tArr >= T;                               // lease expired when the write lands
    r.aAccepted = true;
    if (!r.aWrites) r.aAccepted = false;
    else if (fencing && seenB) r.aAccepted = false;
    r.bAccepted = true;
    // damage: A's late write accepted AFTER B's read
    r.damage = r.aWrites && r.aAccepted && r.late && seenB;
    r.harmless = r.aWrites && r.aAccepted && r.late && !seenB;
    r.order = r.tArr > r.tBwrite ? "after" : "between";
    return r;
  }

  function render() {
    var r = compute();
    lblX.textContent = r.sc === "pause" ? "Pause length" : r.sc === "delay" ? "Network delay" : "Clock jumps back by";
    vX.textContent = rX.value + " s";
    vTtl.textContent = rTtl.value + " s";
    var tmax = Math.max(r.T + 6, Math.ceil(r.tArr + 3), 24);
    function X(t) { return X0 + (X1 - X0) * t / tmax; }
    clear(svg);
    var defs = s("defs");
    ["blue", "green", "red", "orange"].forEach(function (c) {
      var m = s("marker", { id: "lfarr-" + c, viewBox: "0 0 10 10", refX: "9", refY: "5", markerWidth: "7", markerHeight: "7", orient: "auto" });
      m.appendChild(s("path", { d: "M0,0 L10,5 L0,10 z", class: "lf-ah lf-ah-" + c }));
      defs.appendChild(m);
    });
    svg.appendChild(defs);
    [["A", "Client A", "lf-tc-green"], ["L", "Lock service", "lf-tc-cyan"], ["B", "Client B", "lf-tc-pink"], ["S", "Storage", "lf-tc-blue"]].forEach(function (l) {
      svg.appendChild(s("line", { x1: X0, y1: LANES[l[0]], x2: X1, y2: LANES[l[0]], class: "lf-lane" }));
      svg.appendChild(s("text", { x: 6, y: LANES[l[0]] + 4, class: "lf-lab " + l[2] }, l[1]));
    });
    // time axis
    var step = tmax > 30 ? 10 : 5;
    for (var t = 0; t <= tmax; t += step) {
      svg.appendChild(s("line", { x1: X(t), y1: 296, x2: X(t), y2: 301, class: "lf-lane" }));
      svg.appendChild(s("text", { x: X(t), y: 315, "text-anchor": "middle", class: "lf-tick" }, t + " s"));
    }
    svg.appendChild(s("line", { x1: X0, y1: 298, x2: X1, y2: 298, class: "lf-lane" }));
    // lease bars on the lock lane
    svg.appendChild(s("rect", { x: X(0), y: LANES.L - 9, width: X(r.T) - X(0), height: 18, rx: 4, class: "lf-lease" }));
    svg.appendChild(s("text", { x: (X(0) + X(r.T)) / 2, y: LANES.L + 4, "text-anchor": "middle", class: "lf-tick lf-tc-orange" }, "A's lease, token 33"));
    svg.appendChild(s("rect", { x: X(r.tB), y: LANES.L - 9, width: Math.min(X1, X(r.tB + r.T)) - X(r.tB), height: 18, rx: 4, class: "lf-lease b" }));
    if (X(r.tB + r.T) - X(r.tB) > 90) svg.appendChild(s("text", { x: (X(r.tB) + Math.min(X1, X(r.tB + r.T))) / 2, y: LANES.L + 4, "text-anchor": "middle", class: "lf-tick lf-tc-orange" }, "B's lease, 34"));
    // expiry line
    svg.appendChild(s("line", { x1: X(r.T), y1: 30, x2: X(r.T), y2: 296, class: "lf-expiry" }));
    svg.appendChild(s("text", { x: X(r.T) + 3, y: 24, class: "lf-tick lf-tc-red" }, "A's lease expires (t=" + r.T + ")"));
    // A: working, check, pause
    svg.appendChild(s("rect", { x: X(0), y: LANES.A - 6, width: Math.max(2, X(r.tCheck) - X(0)), height: 12, rx: 3, class: "lf-work" }));
    svg.appendChild(s("circle", { cx: X(r.tCheck), cy: LANES.A, r: 5, class: "lf-dot" }));
    if (r.sc === "pause") {
      svg.appendChild(s("rect", { x: X(r.tCheck), y: LANES.A - 8, width: Math.max(2, X(r.tSend) - X(r.tCheck)), height: 16, rx: 3, class: "lf-pause" }));
      svg.appendChild(s("text", { x: (X(r.tCheck) + X(r.tSend)) / 2, y: LANES.A - 13, "text-anchor": "middle", class: "lf-tick lf-tc-red" }, "paused " + r.X + " s"));
    }
    if (r.sc === "clock") {
      svg.appendChild(s("path", { d: "M" + (X(3) - 5) + "," + (LANES.A - 18) + " L" + (X(3) + 5) + "," + (LANES.A - 8) + " M" + (X(3) + 5) + "," + (LANES.A - 18) + " L" + (X(3) - 5) + "," + (LANES.A - 8), class: "lf-x" }));
      svg.appendChild(s("text", { x: X(3) + 8, y: LANES.A - 14, class: "lf-tick lf-tc-red" }, "clock steps back " + r.X + " s"));
    }
    svg.appendChild(s("text", { x: X(r.tCheck), y: LANES.A + 22, "text-anchor": r.sc === "clock" ? "end" : "middle", class: "lf-tick" }, "check " + (r.viewValid ? "passes" : "fails")));
    // lock grants
    function arrow(x1, y1, x2, y2, c, dash) {
      svg.appendChild(s("line", { x1: x1, y1: y1, x2: x2, y2: y2, class: "lf-msg lf-" + c + (dash ? " dash" : ""), "marker-end": "url(#lfarr-" + c + ")" }));
    }
    arrow(X(0), LANES.L - 9, X(0) + 10, LANES.A + 6, "green");
    arrow(X(r.tB), LANES.L + 9, X(r.tB) + 8, LANES.B - 6, "green");
    // B read & write
    arrow(X(r.tBread - 0.2), LANES.B + 4, X(r.tBread), LANES.S - 5, "blue");
    arrow(X(r.tBwrite - 0.2), LANES.B + 4, X(r.tBwrite), LANES.S - 5, "blue");
    svg.appendChild(s("text", { x: X(r.tBwrite) + 6, y: LANES.B + 22, class: "lf-tick lf-tc-pink" }, "B: read, then write (tok 34)"));
    // A's write
    var aLbl = "write (tok 33)";
    if (r.aWrites) {
      arrow(X(r.tSend), LANES.A + 5, X(r.tArr), LANES.S - 5, r.aAccepted ? "blue" : "red", r.sc === "delay");
      var mx = (X(r.tSend) + X(r.tArr)) / 2 + 4, my = (LANES.A + LANES.S) / 2 - 6;
      svg.appendChild(s("text", { x: mx, y: my, class: "lf-tick lf-tc-blue" }, aLbl));
      // result glyph
      if (r.aAccepted) svg.appendChild(s("circle", { cx: X(r.tArr), cy: LANES.S, r: 6, class: r.damage ? "lf-bad" : "lf-ok" }));
      else svg.appendChild(s("path", { d: "M" + (X(r.tArr) - 6) + "," + (LANES.S - 6) + " L" + (X(r.tArr) + 6) + "," + (LANES.S + 6) + " M" + (X(r.tArr) + 6) + "," + (LANES.S - 6) + " L" + (X(r.tArr) - 6) + "," + (LANES.S + 6), class: "lf-x" }));
      svg.appendChild(s("text", { x: X(r.tArr), y: LANES.S + 24, "text-anchor": r.tArr > tmax - 6 ? "end" : "middle", class: "lf-tick " + (r.aAccepted ? (r.damage ? "lf-tc-red" : "lf-tc-green") : "lf-tc-green") }, r.aAccepted ? (r.damage ? "accepted: stale data wins" : "accepted") : "rejected"));
    } else {
      svg.appendChild(s("text", { x: X(r.tCheck), y: LANES.A + 36, "text-anchor": "end", class: "lf-tick lf-tc-green" }, "A does not write"));
    }

    // narrative
    clear(log);
    function li(t, txt) { log.appendChild(h("li", null, "t = " + f1(t) + " s: " + txt)); }
    li(0, "the lock service grants A a lease of " + r.T + " s with fencing token 33.");
    if (r.sc === "clock") li(3, "A's clock is stepped back " + r.X + " s (an NTP correction, or a VM resume). A's idea of 'now' is wrong from here on.");
    var evs = [];
    if (r.sc === "clock") {
      evs.push([r.tCheck, "A checks its lease by its own clock, which reads " + f1(r.tCheck - r.X) + " s into the lease, so it says " + (r.viewValid ? "VALID (it is wrong: the lease expired at " + r.T + ")." : "expired (correct).") ]);
      if (r.aWrites) evs.push([r.tSend, "A sends write(token 33)" + (r.cc ? " because its check said valid." : (r.viewValid ? "." : " without checking at all.")) ]);
      else evs.push([r.tCheck, "A skips the write. The client-side check saved us this time, because the clock error was small."]);
    } else {
      evs.push([r.tCheck, "A checks its lease: " + (r.viewValid ? "valid, with " + f1(r.T - r.tCheck) + " s to spare." : "expired.") ]);
      if (r.sc === "pause") evs.push([r.tCheck + 0.1, "A freezes for " + r.X + " s, with the write not yet sent. It cannot know."]);
      if (r.sc === "pause") evs.push([r.tSend, "A thaws and sends write(token 33), still believing the check it did earlier."]);
      else evs.push([r.tSend, "A sends write(token 33), and the network holds the packet for " + r.X + " s."]);
    }
    evs.push([r.T, "A's lease expires at the lock service."]);
    evs.push([r.tB, "B asks for the lock and is granted token 34."]);
    evs.push([r.tBread, "B reads from the storage, presenting token 34." + (r.fencing ? " The storage now remembers: highest token = 34." : " (The storage does not look at tokens.)")]);
    evs.push([r.tBwrite, "B writes its update, token 34: accepted."]);
    if (r.aWrites) {
      var why;
      if (!r.late) why = "arrives at t = " + f1(r.tArr) + ", before the lease expired: a legitimate write.";
      else if (r.aAccepted && !r.damage) why = "arrives at t = " + f1(r.tArr) + ", after expiry but before B touched the storage. It is accepted, and B's read will see it, so nothing is lost.";
      else if (r.aAccepted) why = "arrives at t = " + f1(r.tArr) + ", " + (r.order === "after" ? "after B's write: it silently overwrites B's newer data." : "between B's read and B's write: B's update is computed from stale data, so one of the two updates is lost.") + " The storage cannot tell it is stale.";
      else why = "arrives at t = " + f1(r.tArr) + " with token 33; the storage has seen 34 and REJECTS it.";
      evs.push([r.tArr, "A's write " + why]);
    }
    evs.sort(function (a, b) { return a[0] - b[0]; });
    evs.forEach(function (e) { li(e[0], e[1]); });

    var v;
    if (!r.aWrites) { v = ["ok", "Safe, but only because the clock error happened to be smaller than the margin. Make the jump larger and the check starts passing falsely."]; }
    else if (!r.late) { v = ["ok", "No problem: the write arrived while A's lease was still valid. Lengthen the pause or delay to see the failure."]; }
    else if (r.damage) { v = ["bad", "CORRUPTION: A's expired lease was used to change shared data after B had taken over. " + (r.cc ? "A's own check could not prevent it: " + (r.sc === "clock" ? "its clock was wrong." : "the check passed before the pause or delay.") : "") + " Turn on token checking in the storage."]; }
    else if (r.aAccepted && r.fencing) { v = ["ok", "Accepted but harmless: it landed before B's first request, so B reads it. Fencing only bites once the storage has seen the newer token."]; }
    else if (r.aAccepted) { v = ["ok", "A stale write was accepted but landed before B touched the storage, so nothing was lost (this time)."]; }
    else { v = ["ok", "PROTECTED: the storage compared tokens (33 < 34) and refused A's stale write, although A was convinced it held the lock."]; }
    verdict.className = "lf-verdict " + v[0];
    verdict.textContent = v[1];
  }
  [selS, rTtl, rX, cFence, cClient].forEach(function (c) {
    c.addEventListener("input", render); c.addEventListener("change", render);
  });
  render();
})();
