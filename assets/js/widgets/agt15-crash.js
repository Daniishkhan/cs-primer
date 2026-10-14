/* Where did it crash? (agents chapter 15)
   Replays the chapter's crash_demo.py as a timeline. The task has six atoms:
   M1 model call, T lookup (read-only), M2 model call, E refund (the side effect), R record the result, M3 final model call.
   Run 1 stops after the chosen atom; run 2 is the restart. All behaviour is the chapter's, not a measurement of any product. */
(function () {
  "use strict";

  var ATOMS = [
    { id: "M1", label: "model call 1", sub: "plan lookup", kind: "model" },
    { id: "T", label: "lookup", sub: "read-only", kind: "read" },
    { id: "M2", label: "model call 2", sub: "decide refund", kind: "model" },
    { id: "E", label: "refund", sub: "side effect", kind: "effect" },
    { id: "R", label: "record", sub: "result to journal", kind: "record" },
    { id: "M3", label: "model call 3", sub: "final answer", kind: "model" }
  ];
  var STRATS = [
    { id: "scratch", name: "Restart from scratch" },
    { id: "journal", name: "Journal, no idempotency key" },
    { id: "keys", name: "Journal + idempotency key" }
  ];

  /* crashAfter: index of the last atom that completed in run 1 (0 to 4). */
  function simulate(strategy, crashAfter) {
    var run1 = [], run2 = [], i, refunds = 0, models = 0;
    for (i = 0; i <= crashAfter; i++) run1.push(i);
    if (strategy === "scratch") {
      for (i = 0; i < ATOMS.length; i++) run2.push(i);
    } else {
      /* An atom is skipped on resume only if its outcome is in the journal. E is journalled by R. */
      for (i = 0; i < ATOMS.length; i++) {
        var recorded = i <= crashAfter && !(i === 3 && crashAfter === 3);
        if (!recorded) run2.push(i);
      }
    }
    var effectRuns = 0, deduped = false;
    for (i = 0; i < run1.length; i++) { if (run1[i] === 3) effectRuns++; if (ATOMS[run1[i]].kind === "model") models++; }
    for (i = 0; i < run2.length; i++) {
      if (run2[i] === 3) { if (strategy === "keys" && effectRuns > 0) deduped = true; else effectRuns++; }
      if (ATOMS[run2[i]].kind === "model") models++;
    }
    refunds = effectRuns;
    return { run1: run1, run2: run2, refunds: refunds, models: models, deduped: deduped };
  }

  var core = { simulate: simulate };
  if (typeof module !== "undefined" && module.exports) module.exports = core;
  if (typeof document === "undefined") return;
  var root = document.getElementById("agt15-crash");
  if (!root) return;

  function el(tag, attrs, text) {
    var e = document.createElement(tag), k;
    for (k in attrs) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    return e;
  }

  var state = { strat: "journal", crash: 3 };
  var head = el("div", { "class": "widget-head" });
  head.appendChild(el("span", { "class": "widget-tag" }, "Try it"));
  head.appendChild(el("h4", { "class": "widget-title" }, "Crash the agent, then restart it"));
  root.appendChild(head);
  root.appendChild(el("p", { "class": "widget-help" },
    "A refund task runs six steps. Pick a recovery strategy and the moment the process dies, then read what the restart did. The interesting case is a crash after the refund but before its result is recorded."));

  var row = el("div", { "class": "widget-row ag15-ctl" });
  var l1 = el("label", { "for": "agt15-strat" }, "Recovery: ");
  var sel = el("select", { id: "agt15-strat" });
  STRATS.forEach(function (s) { var o = el("option", { value: s.id }, s.name); if (s.id === state.strat) o.selected = true; sel.appendChild(o); });
  sel.addEventListener("change", function () { state.strat = sel.value; update(); });
  l1.appendChild(sel); row.appendChild(l1);
  var l2 = el("label", { "for": "agt15-crash-at" }, "Process dies after: ");
  var out2 = el("output", { id: "agt15-crash-out" });
  var rng = el("input", { type: "range", id: "agt15-crash-at", min: 0, max: 4, step: 1, value: state.crash });
  rng.addEventListener("input", function () { state.crash = parseInt(rng.value, 10); update(); });
  l2.appendChild(out2); row.appendChild(l2); row.appendChild(rng);
  root.appendChild(row);

  var lanes = el("div", { "class": "ag15-lanes" });
  root.appendChild(lanes);
  var res = el("div", { "class": "widget-out", "aria-live": "polite" });
  root.appendChild(res);

  function lane(title, ran, crashAfter, isRun1) {
    var wrap = el("div", { "class": "ag15-lane" });
    wrap.appendChild(el("div", { "class": "ag15-lane-title" }, title));
    var chips = el("div", { "class": "ag15-chips" });
    ATOMS.forEach(function (a, i) {
      var did = ran.indexOf(i) >= 0;
      var cls = "ag15-chip" + (did ? " ran ran-" + a.kind : " skipped");
      if (isRun1 && i === crashAfter) cls += " last";
      var c = el("div", { "class": cls });
      c.appendChild(el("strong", {}, a.label));
      c.appendChild(el("span", {}, did ? a.sub : (isRun1 ? "never reached" : "skipped: in journal")));
      chips.appendChild(c);
    });
    wrap.appendChild(chips);
    return wrap;
  }

  function update() {
    var r = simulate(state.strat, state.crash);
    out2.textContent = ATOMS[state.crash].label;
    lanes.innerHTML = "";
    lanes.appendChild(lane("Run 1 (dies after this step)", r.run1, state.crash, true));
    lanes.appendChild(lane("Run 2 (the restart)", r.run2, state.crash, false));
    var bad = r.refunds > 1;
    var msg = r.refunds + " refund" + (r.refunds === 1 ? "" : "s") + " issued, " + r.models + " model calls billed. ";
    if (bad) msg += "The customer was refunded twice: the restart could not tell that the refund had already happened.";
    else if (r.deduped) msg += "The restart repeated the refund call, and the bank recognised the key and returned the first answer.";
    else if (state.strat === "scratch") msg += "Correct this time only because the crash came before the refund; the restart re-paid for every model call.";
    else msg += "Correct, and the restart paid only for the steps the journal did not already hold.";
    res.textContent = msg;
    res.className = "widget-out" + (bad ? " ag15-bad" : "");
  }
  update();
})();
