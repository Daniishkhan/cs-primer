/* Take-home time-box planner (A8 chapter 18).
   Seven activities, each with an hours slider, against a chosen budget. Shows the split, the share
   spent building versus proving, and the warnings a reviewer would raise. No randomness. */
(function () {
  "use strict";
  var root = document.getElementById("aid18-timebox");
  if (!root) return;
  var ACTS = [
    { id: "brief", name: "Restate the brief, list assumptions", h: 0.5, min: 0.25, kind: "prove" },
    { id: "gold", name: "Inspect the data, label a gold set", h: 1.5, min: 1.0, kind: "prove" },
    { id: "base", name: "Baseline before any framework", h: 0.5, min: 0.25, kind: "prove" },
    { id: "build", name: "Build the main system", h: 1.0, min: 0.0, kind: "build" },
    { id: "eval", name: "Evaluate: intervals, cost, latency", h: 0.5, min: 0.5, kind: "prove" },
    { id: "error", name: "Error analysis of sampled traces", h: 0.5, min: 0.5, kind: "prove" },
    { id: "write", name: "Memo, limitations, README, defence notes", h: 0.5, min: 0.5, kind: "prove" }
  ];
  var COLOURS = ["blue", "green", "cyan", "purple", "orange", "red", "yellow"];
  var budgetSel = root.querySelector("[data-act=budget]");
  var rows = root.querySelector("[data-act=rows]");
  var bar = root.querySelector("[data-act=bar]");
  var flags = root.querySelector("[data-act=flags]");
  var sums = root.querySelector("[data-act=sums]");
  var inputs = [], outs = [];

  ACTS.forEach(function (a, i) {
    var row = document.createElement("div"); row.className = "aid18-row";
    var lab = document.createElement("label"); lab.textContent = a.name; lab.setAttribute("for", "aid18-" + a.id);
    var inp = document.createElement("input"); inp.type = "range"; inp.id = "aid18-" + a.id;
    inp.min = "0"; inp.max = "3"; inp.step = "0.25"; inp.value = String(a.h);
    var out = document.createElement("span"); out.className = "aid18-h";
    inp.addEventListener("input", update);
    row.appendChild(lab); row.appendChild(inp); row.appendChild(out);
    rows.appendChild(row); inputs.push(inp); outs.push(out);
  });

  function update() {
    var budget = +budgetSel.value, total = 0, build = 0, i;
    var hours = inputs.map(function (e) { return +e.value; });
    for (i = 0; i < hours.length; i++) {
      total += hours[i]; if (ACTS[i].kind === "build") build += hours[i];
      outs[i].textContent = hours[i].toFixed(2) + " h";
    }
    bar.innerHTML = "";
    for (i = 0; i < hours.length; i++) {
      if (hours[i] <= 0) continue;
      var seg = document.createElement("div");
      seg.className = "aid18-seg f-" + COLOURS[i];
      seg.style.width = (100 * hours[i] / Math.max(total, budget)) + "%";
      seg.title = ACTS[i].name + ": " + hours[i] + " h";
      bar.appendChild(seg);
    }
    var ratio = total > 0 ? build / total : 0;
    sums.textContent = total.toFixed(2) + " h planned of " + budget + " h. Building the system: " +
      Math.round(100 * ratio) + "%. Everything that shows it works: " + Math.round(100 * (1 - ratio)) + "%.";
    var msgs = [];
    if (total > budget + 1e-9) msgs.push(["bad", "Over budget by " + (total - budget).toFixed(2) + " h. Cut scope; do not cut the evaluation or the memo."]);
    for (i = 0; i < hours.length; i++) {
      if (ACTS[i].kind === "prove" && hours[i] < ACTS[i].min) msgs.push(["bad", "\"" + ACTS[i].name + "\" has under " + ACTS[i].min + " h. Reviewers look for this artefact first, and it is the usual reason a strong build is marked down."]);
    }
    if (ratio > 0.5) msgs.push(["warn", "More than half the time goes on building. Candidates who hill-climb the system and rush the evidence tend to produce an impressive demo with no proof."]);
    if (hours[3] === 0) msgs.push(["warn", "No time on the main system: the baseline is the submission. That can be right if the baseline wins, but say so in the memo."]);
    if (total < budget - 1.0) msgs.push(["warn", "More than an hour unspent. Use it for a second pass of error analysis, not for features."]);
    if (!msgs.length) msgs.push(["ok", "A balanced plan: the evidence takes most of the time, and each artefact has enough to be real."]);
    flags.innerHTML = "";
    msgs.forEach(function (m) {
      var p = document.createElement("p"); p.className = "aid18-flag " + m[0]; p.textContent = m[1]; flags.appendChild(p);
    });
  }
  budgetSel.addEventListener("change", update);
  update();
})();
