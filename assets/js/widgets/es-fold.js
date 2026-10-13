/* Event sourcing: fold, projection, snapshot (architecture chapter 16).

   A bank account stored as events. You append events one at a time and watch:
     - the aggregate's state, which is just fold(events);
     - a read model (a statement projection) that processes events separately and can lag
       behind: that is eventual consistency between the write side and the read side;
     - a snapshot, a saved (position, state) pair that lets a rebuild skip the events before
       it, shown as the number of events a rebuild must replay with and without it;
     - a time-travel slider: the balance after any event is the fold of a prefix.
   Fully deterministic: no timers, no randomness. */
(function () {
  "use strict";
  var root = document.getElementById("es-fold");
  if (!root) return;

  var EVENTS = [
    ["Opened", 0, "Jan 5"], ["Deposited", 100, "Jan 20"], ["Withdrawn", 25, "Feb 10"], ["Deposited", 50, "Feb 28"],
    ["Withdrawn", 12, "Mar 15"], ["Deposited", 3, "Mar 20"], ["Withdrawn", 40, "Apr 2"], ["Deposited", 20, "Apr 9"]
  ];
  function apply(bal, e) { return e[0] === "Deposited" ? bal + e[1] : e[0] === "Withdrawn" ? bal - e[1] : bal; }
  function fold(k) { var b = 0; for (var i = 0; i < k; i++) b = apply(b, EVENTS[i]); return b; }
  function money(v) { return "$" + v; }

  var n = 3, proj = 3, snap = 0, tt = 3;

  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function btn(label, cls, fn) { var b = el("button", "btn " + (cls || ""), label); b.type = "button"; b.addEventListener("click", fn); return b; }

  var head = el("div", "widget-head");
  head.appendChild(el("span", "widget-tag", "Simulator"));
  head.appendChild(el("span", "widget-title", "Events fold into state"));
  root.appendChild(head);
  root.appendChild(el("p", "widget-help", "Append events to the store. The account balance is never stored: it is recomputed by folding the events. The statement view is a projection that you advance separately, and a snapshot lets a rebuild skip the past."));

  var row = el("div", "es-btns");
  var bApp = btn("Append next event", "primary small", function () { if (n < EVENTS.length) { n++; tt = n; render(); } });
  var bProj = btn("Run projection", "small", function () { proj = n; render(); });
  var bSnap = btn("Take snapshot", "small", function () { snap = n; render(); });
  var bReset = btn("Reset", "small", function () { n = 3; proj = 3; snap = 0; tt = 3; render(); });
  [bApp, bProj, bSnap, bReset].forEach(function (b) { row.appendChild(b); });
  root.appendChild(row);

  root.appendChild(el("p", "es-label", "Event store (append-only)"));
  var strip = el("ol", "es-strip"); root.appendChild(strip);

  var grid = el("div", "es-grid");
  var pAgg = el("div", "es-pane agg"); pAgg.appendChild(el("h5", null, "Write side: the aggregate"));
  var aggBal = el("p", "es-big"); var aggNote = el("p", "es-note"); var aggCost = el("p", "es-note");
  pAgg.appendChild(aggBal); pAgg.appendChild(aggNote); pAgg.appendChild(aggCost);
  grid.appendChild(pAgg);
  var pProj = el("div", "es-pane proj"); pProj.appendChild(el("h5", null, "Read side: statement projection"));
  var projBal = el("p", "es-big"); var projNote = el("p", "es-note"); var projRows = el("ol", "es-rows");
  pProj.appendChild(projBal); pProj.appendChild(projNote); pProj.appendChild(projRows);
  grid.appendChild(pProj);
  root.appendChild(grid);

  root.appendChild(el("p", "es-label", "Time travel"));
  var lab = el("label", "es-range"); var rtxt = el("span", null, "State after event #");
  var rng = document.createElement("input"); rng.type = "range"; rng.min = "0"; rng.step = "1";
  rng.addEventListener("input", function () { tt = parseInt(rng.value, 10); render(); });
  lab.appendChild(rtxt); lab.appendChild(rng); root.appendChild(lab);
  var ttOut = el("p", "es-tt"); ttOut.setAttribute("aria-live", "polite"); root.appendChild(ttOut);

  function render() {
    bApp.disabled = n >= EVENTS.length;
    bProj.disabled = proj >= n;
    bSnap.disabled = snap === n;

    strip.textContent = "";
    for (var i = 0; i < n; i++) {
      var e = EVENTS[i];
      var li = el("li", "es-ev" + (i < snap ? " old" : "") + (i + 1 === tt ? " sel" : ""));
      li.appendChild(el("strong", null, e[0]));
      li.appendChild(el("span", null, e[1] ? money(e[1]) : e[2]));
      strip.appendChild(li);
      if (i + 1 === snap) { var sp = el("li", "es-snap", "snapshot " + money(fold(snap))); strip.appendChild(sp); }
    }

    aggBal.textContent = "balance " + money(fold(n));
    aggNote.textContent = "= fold of " + n + " event" + (n === 1 ? "" : "s") + ", starting from 0";
    var cost = n - snap;
    aggCost.textContent = snap
      ? "Rebuilding replays " + cost + " event" + (cost === 1 ? "" : "s") + " (snapshot covers " + snap + "); without the snapshot it would replay " + n + "."
      : "Rebuilding replays all " + n + " events. Take a snapshot to cut that.";

    var lag = n - proj;
    projBal.textContent = "balance " + money(fold(proj));
    projNote.textContent = lag
      ? "Behind by " + lag + " event" + (lag === 1 ? "" : "s") + ": a query here still says " + money(fold(proj)) + " while the store says " + money(fold(n)) + ". Eventual consistency."
      : "Caught up: matches the write side.";
    pProj.className = "es-pane proj" + (lag ? " lag" : "");
    projRows.textContent = "";
    for (var j = Math.max(0, proj - 6); j < proj; j++) {
      projRows.appendChild(el("li", null, EVENTS[j][2] + "  " + EVENTS[j][0] + (EVENTS[j][1] ? " " + money(EVENTS[j][1]) : "") + "  → " + money(fold(j + 1))));
    }
    if (!proj) projRows.appendChild(el("li", "es-none", "no rows yet"));

    if (tt > n) tt = n;
    rng.max = String(n); rng.value = String(tt);
    rng.setAttribute("aria-valuetext", "after event " + tt);
    ttOut.textContent = tt === 0
      ? "Before any event the account does not exist (balance $0)."
      : "After event " + tt + " (" + EVENTS[tt - 1][0] + ", " + EVENTS[tt - 1][2] + "): balance " + money(fold(tt)) + ". Computed by folding the first " + tt + " events; nothing was stored for that date.";
  }
  render();
})();
